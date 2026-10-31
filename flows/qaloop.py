"""The QA loop as a Metaflow flow that drives itself (docs/research/qa-loop/PREREG.md).

Usage, through the launcher only (grid/qaloop.sbatch, the gate's word `qaloop <plan>`):
    python flows/launch.py qaloop --max-workers 1 -- --plan grid/qaloop/<plan>.json \\
        --chain <job> --out <loop root> --data <data root>

The owner asked on 2026-10-31 for a pipeline with quality-assurance checkpoints that propels itself
until they are met: convergence, the anomaly classes encoded and decoded, the 3-D landmarks whose
2-D projections fingerprint each level uniquely, that fingerprint present in real fluoroscopy, and
the latency. This flow is that loop. A run is one chain, the Slurm job the gate's send made, and
works in <out>/<plan>/<chain>/: start holds the run to the frozen PREREG and the part of it that
covers the plan by its bytes, checks the plan and makes the folder; round runs one round of
tools/qaloop_round.py, which trains the auto-anatomist further and asks every gate of what it has,
and the controller (tools/qaloop_gates.py) reads the round's answers and decides: again, with one
change for each failing gate that has one, or done, when every gate passes, when a gate could not
be asked for want of data, when no failing gate has a change left (the plan's ranges searched and
the data grown as far as the measured memory holds), or when the plan's rounds run out. Again is
the step itself (Metaflow's recursive switch), so the loop is one run, and a run cut short by a
time limit or a preemption is resumed by the next job of the same words at the round it was cut
in, every earlier round cloned. end writes RECORD.json, SUMMARY.md and the CLAIM 2024 and REFORMS
report (tools/report.py --study qa-loop) and the verdict.

Each round works in rounds/<n>/ (its state.json, PROGRESS.txt, gates.json, decision.json, its
session, and why.txt where it failed) and the rounds share work/ (the crops' and the pairs'
caches); a round loads the session the round before it saved and saves its own, so a round run
again starts where the round before it ended, and the session of the round two back is dropped
once the next round starts. A round whose tool fails is run once more in the same task; a second
failure ends the loop failed, and end still writes the record. What leaves the grid is the
record's aggregates: counts, means and intervals, never a person, a frame's file name or a value
of a header.
"""

import hashlib
import importlib.util
import json
import math
import os
import re
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from metaflow import FlowSpec, Parameter, Run, card, current, namespace, retry, step
from metaflow.cards import EventsTimeline, Markdown, ProgressBar, Table, ValueBox, VegaChart

import stage

REPO = Path(os.environ.get("SCHWINGNET") or Path(__file__).resolve().parent.parent)
KIND = "qaloop"
STUDY = "qa-loop"
ROUND_TOOL = REPO / "tools" / "qaloop_round.py"
REFRESH = 15
# The chain: the Slurm job the gate's send made, or none where a person runs the loop by hand.
CHAIN = re.compile(r"[0-9]{1,12}|none")
# What end writes once the rounds are done, and the record: none of it is a round's work.
END_WRITES = ("RECORD.json", "ENDED.json", "SUMMARY.md", *stage.REPORT_OUTPUTS)
# A round whose tool fails, its exit no answer of the round's, is run once more by Metaflow's own
# @retry; on that last attempt the failure is the round's answer and the loop ends failed.
ROUND_RETRIES = 1
# The round tool's exits that are answers, never run again: 0 the round's record, 2 a plan or state
# the tool refuses, and INSANE_EXIT below.
ANSWERS = (0, 2)
# The round tool's exit for a check whose numbers cannot be right (tools/qaloop_round.py,
# INSANE_EXIT): run again it would train the same steps into the same numbers, so it is not.
INSANE_EXIT = 3
# The loop's trend, every round's checks in order, gathered from rounds/<n>/TREND.jsonl.
TREND = "TREND.jsonl"
# The files of the frozen split the pairs are dealt by, kept by their sha256 for the record.
SPLIT_FILES = ("data/splits/rule.json", "data/splits/test-persons.json")


def gates_module():
    """tools/qaloop_gates.py, numpy alone, loaded by its path, since tools/ is not on the path and
    the round tool, which trains, must not be imported into the flow."""
    spec = importlib.util.spec_from_file_location("qaloop_gates", REPO / "tools" / "qaloop_gates.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


G = gates_module()


class QaloopFault(Exception):
    """Words or a plan the loop cannot run with, said in words."""


def launcher_folder():
    """The folder the launcher was started in, which a relative path parameter is read from."""
    return Path(os.environ.get("SCHWINGNET_WORKDIR") or os.getcwd())


def from_launcher(path, folder=None):
    """A path parameter as the caller meant it: a relative one is read from the launcher's folder."""
    return str((folder or launcher_folder()) / path) if path and not Path(path).is_absolute() else path


def file_sha256(path):
    """The file's sha256, or None where it cannot be read."""
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def word_value(words, flag):
    """The value the words give a flag, the last one as click takes it; '' where they give none."""
    value, rest = "", list(words)
    while rest:
        word = rest.pop(0)
        if word == flag and rest:
            value = rest.pop(0)
        elif word.startswith(flag + "="):
            value = word[len(flag) + 1:]
    return value


def plan_part(plan_file):
    """The plan's name, grid/qaloop/<name>.json, the part of the loop's PREREG a run of it is."""
    return Path(plan_file).stem if plan_file else ""


def prereg_part(words, folder):
    """The part a run of these words is, for the launcher: the plan's name and the sha256 of its
    bytes; a plan edited since the freeze is another design under the same name."""
    plan_file = from_launcher(word_value(words, "--plan"), folder)
    return plan_part(plan_file), file_sha256(plan_file)


def key_reads(words, folder):
    """What a run of these words reads that the words do not name, for the launcher's key: the plan
    file's bytes, since start checks the plan and a resume clones start."""
    return [f"plan {file_sha256(from_launcher(word_value(words, '--plan'), folder)) or 'unreadable'}"]


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def write_json(path, value):
    """A JSON file written whole or not at all, so a reader never sees half of one."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    part.write_text(json.dumps(value, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(part, path)


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def code_state():
    """The checkout's commit and whether its tree is clean, read where the step runs: a copy of the
    code that is no git checkout says neither, and its COPY.txt names the commit instead."""
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True)
    tree = subprocess.run(["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True)
    commit = head.stdout.strip() if head.returncode == 0 else ""
    copied = (REPO / "COPY.txt").read_text(encoding="utf-8").split("\n", 1)[0] if (REPO / "COPY.txt").is_file() else None
    return {"commit": commit or None, "clean_tree": bool(commit) and tree.returncode == 0 and not tree.stdout.strip(),
            "copy_of": copied}


def run_key():
    """The launcher's key for this run, from its tag; the run id where the flow ran without it."""
    for tag in current.tags or ():
        if str(tag).startswith("key:"):
            return str(tag)[4:]
    return f"run{current.run_id}"


def last_line(path):
    """The last line of a file, or nothing where it is not there yet."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return ""
    return (text.strip().splitlines() or [""])[-1][:300]


def plan_in_force(plan_file):
    """The plan a file holds, checked whole (tools/qaloop_gates.py, plan_problems) and against its
    own name, the folder the job script keeps its steps in."""
    plan = read_json(plan_file)
    found = G.plan_problems(plan) if plan is not None else [f"the plan {plan_file} cannot be read as JSON"]
    if not found and plan["plan"] != plan_part(plan_file):
        found = [f"plan: the plan's own name, {plan_part(plan_file)}, not {plan['plan']!r}"]
    if found:
        raise QaloopFault(f"the plan {Path(plan_file).name} does not hold: {found[0]}")
    return plan


def words_problems(flow, plan):
    """What keeps the words from running the plan's loop, or None."""
    if not CHAIN.fullmatch(flow.chain or ""):
        return f"--chain is the send's Slurm job or none, not {flow.chain!r}"
    if not Path(flow.out).is_absolute():
        return f"--out is an absolute folder on the lab volume, not {flow.out!r}"
    if plan["class"] == "loop" and (not flow.data or not Path(flow.data).is_absolute()):
        return "a loop plan reads the real pairs under the data root, an absolute --data"
    if plan["class"] == "loop" and "gold4" in (plan.get("gold") or {}) and not Path(flow.gold4 or "").is_absolute():
        return "a loop plan whose gold block names gold4 reads its records under an absolute --gold4"
    if flow.gold4 and not Path(flow.gold4).is_absolute():
        return f"--gold4 is the gold tier 4 run's absolute folder, not {flow.gold4!r}"
    if flow.workers < 0:
        return f"--workers is 0 (as many as the space plan allows) or more, not {flow.workers}"
    return None


def round_summary(n, record, decision, code, tries):
    """One round in the record's words: how its tool ended, each gate's answer, the decision and the
    change it made, every value an aggregate."""
    gates = (record or {}).get("gates") or {}
    said = {g: ("pass" if r and r.get("pass") else "missing" if not r or r.get("missing") else "fail")
            for g, r in gates.items()}
    held = (record or {}).get("held") or {}
    fingerprint = (record or {}).get("fingerprint") or {}
    watch = (record or {}).get("watch") or {}
    progress = decision.get("progress") or {}
    return {"round": n, "exit": code, "tries": tries, "gates": said, "verdict": decision["verdict"],
            "why": decision["why"], "changes": decision.get("changes", []), "stuck": decision.get("stuck", []),
            "config": (record or {}).get("config"), "held_distance_mm": held.get("distance_mm"),
            "held_dice": held.get("dice"), "chosen": fingerprint.get("chosen"), "objective": fingerprint.get("objective"),
            "epoch": watch.get("epoch"), "trained_steps": watch.get("trained_steps"), "checks": watch.get("checks"),
            "training_stalled": watch.get("stalled"), "best_distance_mm": watch.get("best_distance_mm"),
            "best_dice": watch.get("best_dice"), "best_epoch": watch.get("best_epoch"),
            "raised": progress.get("raised"), "flat_rounds": progress.get("flat_rounds"),
            "seconds": (record or {}).get("seconds"), "stand_in": (record or {}).get("stand_in")}


def gather_trend(folder):
    """The loop's TREND.jsonl drawn again from every round's, in the rounds' order, so a round run
    again after a cut never adds its checks twice."""
    lines = []
    for path in sorted(Path(folder).glob("rounds/*/" + TREND)):
        lines += [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    target = Path(folder) / TREND
    tmp = target.with_suffix(".tmp")
    tmp.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    os.replace(tmp, target)
    return len(lines)


def plain_number(x):
    return f"{x:.3f}" if isinstance(x, (int, float)) else "none"


def smoke_holds(plan, rounds, decision):
    """Whether a smoke did what a smoke is for: the loop decided (met, or not met with its reason),
    every gate it asks had its data in every round, and it went round at least twice unless the
    first round met every gate. Empty where it holds, else why not."""
    why = []
    if decision["verdict"] not in ("met", "not met"):
        why.append(f"the loop ended {decision['verdict']}: {decision['why']}")
    gaps = [f"round {r['round']} {g}" for r in rounds for g, said in r["gates"].items() if said == "missing"]
    if gaps:
        why.append(f"gates without their data: {', '.join(gaps)}")
    if len(rounds) < 2 and decision["verdict"] != "met":
        why.append(f"{len(rounds)} round run, and a smoke goes round at least twice")
    return why


# ---------------------------------------------------------------- the cards
# Metaflow's own pages for the run (its cards, `card view` and the Metaflow UI show them): the round's
# card moves while its tool trains (real-time cards, refreshed every REFRESH seconds through the
# watcher), and end's holds the whole loop. Every value drawn is an aggregate of the record's.

TREND_FIELDS = (("loss", "loss, the check's mean"), ("held_dice", "held Dice"), ("held_distance_mm", "held distance, mm"))


def read_points(path):
    """The checks a TREND.jsonl holds, in order; a line not yet whole is left for the next read."""
    points = []
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return points
    for line in lines:
        try:
            point = json.loads(line)
        except ValueError:
            continue
        if isinstance(point, dict):
            points.append(point)
    return points


def loop_points(folder, upto):
    """Every check of the rounds before round `upto`, in order."""
    return [p for n in range(upto) for p in read_points(Path(folder) / "rounds" / f"{n:03d}" / TREND)]


def trend_spec(points):
    """A Vega-Lite chart of the loss, the held Dice and the held distance by step, one line a round."""
    values = [{"step": p.get("step"), "round": p.get("round"), **{k: p.get(k) for k, _ in TREND_FIELDS}}
              for p in points if isinstance(p.get("step"), (int, float))]

    def panel(field, title):
        return {"mark": {"type": "line", "point": True}, "width": 560, "height": 130,
                "encoding": {"x": {"field": "step", "type": "quantitative", "title": "step"},
                             "y": {"field": field, "type": "quantitative", "title": title, "scale": {"zero": False}},
                             "color": {"field": "round", "type": "ordinal", "title": "round"},
                             "tooltip": [{"field": "round"}, {"field": "step"}, {"field": field, "format": ".4f"}]}}

    return {"$schema": "https://vega.github.io/schema/vega-lite/v5.json", "data": {"values": values},
            "vconcat": [panel(field, title) for field, title in TREND_FIELDS]}


def numbers_of(points, field):
    """A field's finite values over the points; a check that was not sane wrote words or nothing."""
    return [float(p[field]) for p in points if isinstance(p.get(field), (int, float)) and not isinstance(p.get(field), bool)
            and math.isfinite(p[field])]


def number(x, digits=4):
    return f"{x:.{digits}g}" if isinstance(x, (int, float)) and not isinstance(x, bool) else "none"


class RoundCard:
    """The round's real-time card: the watch's latest and best values, the round's steps, the loop's
    trend so far and each check as an event, moved by line() while the tool runs."""

    def __init__(self, flow, n, plan):
        self.card, self.n = current.card["round"], n
        self.watch, self.steps = plan["watch"], int(plan["steps_per_round"])
        self.folder = flow.round_folder(n)
        self.before = loop_points(flow.folder, n)
        self.seen = 0
        config = flow.state.get("config") or {}
        self.card.append(Markdown(f"# QA loop {flow.plan_name}, round {n}\n\nChain {flow.chain}; config "
                                  + ", ".join(f"{k} {v}" for k, v in sorted(config.items())) + "."))
        self.boxes = {"loss": ValueBox(title="Loss", value="none", subtitle="the latest check's mean"),
                      "dice": ValueBox(title="Held Dice", value="none", subtitle="the watch rows"),
                      "distance": ValueBox(title="Held distance, mm", value="none", subtitle="the watch rows"),
                      "patience": ValueBox(title="Epochs since the last gain", value="none",
                                           subtitle=f"training stops at {self.watch['patience_epochs']}")}
        for box in self.boxes.values():
            self.card.append(box)
        self.bar = ProgressBar(max=self.steps, label="steps this round", unit="steps")
        self.chart = VegaChart(trend_spec(self.before), show_controls=False)
        self.events = EventsTimeline(title="checks and decisions", max_events=200)
        for part in (self.bar, self.chart, self.events):
            self.card.append(part)
        self.card.refresh()

    def line(self):
        """The round's line for the page, the card moved with every check the tool wrote since."""
        points = read_points(self.folder / TREND)
        for p in points[self.seen:]:
            self.events.update({"check": f"step {p.get('step')}", "epoch": number(p.get("epoch"), 3),
                                "loss": number(p.get("loss")), "held Dice": number(p.get("held_dice"), 3),
                                "held distance mm": number(p.get("held_distance_mm"), 3),
                                "gained": "yes" if p.get("gained") else "no"},
                               style_theme="success" if p.get("gained") else "default")
        if len(points) > self.seen and points:
            self.seen, last = len(points), points[-1]
            best_dice = max(numbers_of(self.before + points, "held_dice"), default=None)
            best_distance = min(numbers_of(self.before + points, "held_distance_mm"), default=None)
            self.boxes["loss"].update(value=number(last.get("loss")))
            self.boxes["dice"].update(value=number(last.get("held_dice"), 3), subtitle=f"best {number(best_dice, 3)}")
            self.boxes["distance"].update(value=number(last.get("held_distance_mm"), 3),
                                          subtitle=f"best {number(best_distance, 3)}")
            self.boxes["patience"].update(value=number(last.get("since_best"), 3))
            self.bar.update(min(self.steps, max(int(last.get("round_steps") or 0), 0)))
            self.chart.update(trend_spec(self.before + points))
        self.card.refresh()
        return last_line(self.folder / "PROGRESS.txt") or f"round {self.n}: running"

    def ended(self, decision, record):
        """The round's gates and the decision as the timeline's last events, the timeline finished."""
        for gate, result in ((record or {}).get("gates") or {}).items():
            said = "pass" if result and result.get("pass") else "missing" if not result or result.get("missing") else "fail"
            self.events.update({"gate": gate, "answer": said}, style_theme={"pass": "success", "fail": "warning"}.get(said, "error"))
        self.events.update({"decision": decision["verdict"], "why": decision["why"][:400]}, priority="high",
                           style_theme="primary" if decision["branch"] == "again" else "info", finished=True)
        self.card.refresh()


def loop_card(flow, lines, points):
    """end's card: the verdict, the loop's trend whole and every round's gates and decision."""
    parts = [Markdown(f"# QA loop {flow.plan_name}: {flow.decision['verdict']}\n\nChain {flow.chain}, folder "
                      f"{flow.folder}; verdict {flow.verdict}; progress page {stage.page_path()}."),
             ValueBox(title="Loop", value=flow.decision["verdict"], subtitle=f"{len(flow.rounds)} rounds",
                      theme="success" if flow.decision["verdict"] == "met" else "warning"),
             ValueBox(title="Best held Dice", value=number(max(numbers_of(points, "held_dice"), default=None), 3),
                      subtitle="the watch rows"),
             ValueBox(title="Best held distance, mm",
                      value=number(min(numbers_of(points, "held_distance_mm"), default=None), 3), subtitle="the watch rows"),
             VegaChart(trend_spec(points), show_controls=False),
             Table([[str(r["round"]), ", ".join(f"{g} {said}" for g, said in r["gates"].items()) or "none",
                     r["verdict"], "; ".join(r["changes"]) or "none", number(r.get("held_dice"), 3),
                     number(r.get("held_distance_mm"), 3)] for r in flow.rounds],
                   headers=["round", "gates", "decision", "changes", "held Dice", "held distance mm"]),
             Markdown("\n".join(f"- {said}" for said in lines))]
    for part in parts:
        current.card.append(part)


def tag_run(words):
    """Metaflow tags on this run, so the client finds it by its plan, chain and ending
    (Flow('QaloopFlow').runs('loop:met')); a metadata service that refuses them changes nothing."""
    try:
        namespace(None)
        Run(f"{current.flow_name}/{current.run_id}").add_tags(words)
    except Exception as error:  # noqa: BLE001 (a tag is an index, never the record)
        print(f"QaloopFlow: the tags were not added: {type(error).__name__}", flush=True)


class QaloopRoundFault(Exception):
    """A round whose tool ended with no answer, which Metaflow's @retry runs once more."""


class QaloopFlow(FlowSpec):
    KIND = KIND
    STUDY = STUDY
    plan = Parameter("plan", required=True, help="the plan, grid/qaloop/<plan>.json")
    chain = Parameter("chain", required=True, help="the send's Slurm job, or none")
    out = Parameter("out", required=True, help="the loop root, under which each chain keeps <plan>/<chain>/")
    data = Parameter("data", default="", help="the data root the real pairs are read under (carmlspine/)")
    gold4 = Parameter("gold4", default="", help="the gold tier 4 TotalSegmentator run's folder, for a plan whose gold block names gold4")
    workers = Parameter("workers", type=int, default=0, help="the round tool's processes, 0 for as many as the space plan allows")
    commit = Parameter("commit", default="", help="the commit of the code that first started the run, which the launcher passes")

    @step
    def start(self):
        """The run held to the frozen PREREG and the plan's part of it, the plan and the words checked,
        the chain's folder made and the loop's first state set."""
        with stage.Beat(self, "the PREREG and the plan") as beat:
            self.plan_file = from_launcher(self.plan)
            stage.hold_to_prereg(self, self.KIND, plan_part(self.plan_file), file_sha256(self.plan_file))
            plan = plan_in_force(self.plan_file)
            fault = words_problems(self, plan)
            if fault:
                raise QaloopFault(fault)
            self.plan_name, self.plan_class, self.key = plan["plan"], plan["class"], run_key()
            self.splits = {path: file_sha256(REPO / path) for path in SPLIT_FILES}
            self.folder = str(Path(self.out) / plan["plan"] / self.chain)
            Path(self.folder).mkdir(parents=True, exist_ok=True)
            for name in END_WRITES:
                (Path(self.folder) / name).unlink(missing_ok=True)
            self.started = utc_now()
            self.where = {"host": socket.gethostname(), "slurm_job": os.environ.get("SLURM_JOB_ID") or "none",
                          "run": f"{current.flow_name}/{current.run_id}", "datastore": stage.datastore_root(), **code_state()}
            self.state = {"round": 0, "config": dict(plan["start"]), "held": [], "space": {}, "session": "",
                          "watch": {}, "progress": {}, "wandb_group": f"qaloop-{plan['plan']}-{self.chain}",
                          "commit": self.where.get("commit") or self.commit or "unknown"}
            self.rounds = []
            beat.say(f"{plan['plan']} ({plan['class']}), chain {self.chain}; held to {self.prereg_path}, "
                     f"sha256 {str(self.prereg_sha256)[:16]}; up to {plan['rounds']} rounds; folder {self.folder}")
        self.next(self.round)

    def round_folder(self, n):
        return Path(self.folder) / "rounds" / f"{n:03d}"

    def drop_old_session(self, n):
        """The state of the session two rounds back, which no round or resume reads any more: round n
        loads round n-1's, and round n-1 has ended, since this task runs. Its record.jsonl stays."""
        if n >= 2:
            (self.round_folder(n - 2) / "session" / "state.npz").unlink(missing_ok=True)

    def run_tool(self, n, beat, line_of):
        """The round's tool run to its end, its card and its line on the page moving while it runs;
        its exit."""
        folder = self.round_folder(n)
        command = [sys.executable, str(ROUND_TOOL), "--plan", self.plan_file, "--state", str(folder / "state.json"),
                   "--out", str(folder), "--work", str(Path(self.folder) / "work"), "--data", self.data,
                   "--workers", str(self.workers)]
        if self.gold4:
            command += ["--gold4", self.gold4]
        logs = Path(self.folder) / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        (folder / "gates.json").unlink(missing_ok=True)
        code, out, err = stage.run_watched(command, beat, line_of, every=REFRESH, cwd=REPO)
        with open(logs / f"round-{n:03d}.log", "a", encoding="utf-8") as log:
            log.write(f"$ {' '.join(command)}  (attempt {current.retry_count})\n{out}{err}\n")
        return code

    @retry(times=ROUND_RETRIES, minutes_between_retries=0)
    @card(type="blank", id="round", refresh_interval=REFRESH)
    @step
    def round(self):
        """One round: the tool trains and asks every gate, the controller decides, and the loop goes
        round again or ends. A tool that ends with no answer raises, so Metaflow runs the round again;
        on the last attempt the failure is the round's answer and the loop ends failed."""
        plan = read_json(self.plan_file)
        n = int(self.state["round"])
        with stage.Beat(self, f"round {n}") as beat:
            folder = self.round_folder(n)
            folder.mkdir(parents=True, exist_ok=True)
            self.drop_old_session(n)
            write_json(folder / "state.json", self.state)
            live = RoundCard(self, n, plan)
            code = self.run_tool(n, beat, live.line)
            tries = current.retry_count + 1
            why = last_line(folder / "why.txt") or "no why.txt"
            if code not in ANSWERS + (INSANE_EXIT,) and current.retry_count < ROUND_RETRIES:
                raise QaloopRoundFault(f"round {n}'s tool exited {code}: {why}")
            record = read_json(folder / "gates.json") if code == 0 else None
            checks = gather_trend(self.folder)
            if record is None:
                if code == INSANE_EXIT:
                    decision = {"branch": "done", "verdict": "stopped", "why": f"round {n} stopped: {why}",
                                "changes": [], "stuck": [], "passing": [], "failing": []}
                else:
                    decision = {"branch": "done", "verdict": "failed", "why": f"round {n}'s tool exited {code}: {why}",
                                "changes": [], "stuck": [], "passing": [], "failing": []}
            else:
                decision = G.controller(record, self.state, plan)
            write_json(folder / "decision.json", decision)
            self.rounds = self.rounds + [round_summary(n, record, decision, code, tries)]
            self.decision = decision
            # The round's checks and gates as artifacts of its task, for Metaflow's client.
            self.round_trend = read_points(folder / TREND)
            self.round_gates = (record or {}).get("gates") or {}
            if decision["branch"] == "again":
                held = (record.get("held") or {}).get("distance_mm")
                self.state = {**self.state, "round": n + 1, "config": decision["config"],
                              "held": self.state["held"] + [held], "space": record.get("space") or {},
                              "session": str(folder / "session"), "watch": record.get("watch") or {},
                              "progress": decision.get("progress") or {}}
            live.line()
            live.ended(decision, record)
            beat.say(f"round {n}: {checks} checks in the loop's trend")
            self.branch = decision["branch"]
            beat.say(f"round {n}: {decision['verdict']}; {decision['why']}")
        self.next({"again": self.round, "done": self.end}, condition="branch")

    def record(self, ended):
        """The loop's record: the run, the design it ran under, the plan whole, every round in words and
        every file the report reads, each by its sha256."""
        folder = Path(self.folder)
        plan = read_json(self.plan_file) or {}
        names = sorted(p for p in folder.glob("rounds/*/*") if p.name in ("gates.json", "decision.json", "state.json"))
        return {"study": self.STUDY, "run": self.where["run"], "key": self.key, "commit": self.commit,
                "prereg": self.prereg_path, "prereg_sha256": self.prereg_sha256, "prereg_part": self.prereg_part,
                "prereg_part_sha256": self.prereg_part_sha256, "chain": self.chain, "started": self.started,
                "ended": ended["ended"], "where": self.where, "ended_in": ended,
                "plan": {**plan, "file": f"grid/qaloop/{Path(self.plan_file).name}"},
                "rounds": self.rounds, "decision": self.decision, "splits": self.splits,
                "files": {str(path.relative_to(folder)): file_sha256(path) for path in names},
                "progress_page": str(stage.page_path())}

    def summary_lines(self, smoke_why):
        lines = [f"loop {self.decision['verdict']} after {len(self.rounds)} round{'s' if len(self.rounds) != 1 else ''}: "
                 f"{self.decision['why']}"]
        if self.plan_class == "smoke":
            lines.append("smoke: " + ("holds" if not smoke_why else "does not hold, " + "; ".join(smoke_why)))
        for r in self.rounds:
            gates = ", ".join(f"{g} {said}" for g, said in r["gates"].items()) or "no gates"
            lines.append(f"round {r['round']}: {gates}; {r['verdict']}" + (f"; changes: {'; '.join(r['changes'])}" if r["changes"] else ""))
            if r.get("epoch") is not None:
                lines.append(f"round {r['round']} training: {r.get('trained_steps')} steps to epoch {r['epoch']:.1f}, "
                             f"{r.get('checks')} checks; last gain at epoch {plain_number(r.get('best_epoch'))} "
                             f"(held distance {plain_number(r.get('best_distance_mm'))} mm, Dice {plain_number(r.get('best_dice'))})"
                             + ("; training rests, no gain within the watch's patience" if r.get("training_stalled") else ""))
        if any(r.get("stand_in") for r in self.rounds):
            lines.append("the real gates were asked of stand-ins, phantoms rendered as frames, so they say nothing of real fluoroscopy")
        return lines

    @card(type="blank")
    @step
    def end(self):
        """The run held again to the PREREG start kept, the record, the summary and the report, and the
        verdict: for a loop, 0 only where every gate was met and the report holds; for a smoke, 0 where
        the smoke held (smoke_holds) and the report holds."""
        with stage.Beat(self, "the record and the report") as beat:
            stage.still_held(self, self.KIND)
            folder = Path(self.folder)
            plan = read_json(self.plan_file) or {}
            smoke_why = smoke_holds(plan, self.rounds, self.decision) if self.plan_class == "smoke" else []
            lines = self.summary_lines(smoke_why)
            (folder / "SUMMARY.md").write_text("\n".join(f"- {line}" for line in lines) + "\n", encoding="utf-8")
            gather_trend(self.folder)
            ended = {"run": f"{current.flow_name}/{current.run_id}", "host": socket.gethostname(),
                     "slurm_job": os.environ.get("SLURM_JOB_ID") or "none", "ended": utc_now(), **code_state()}
            write_json(folder / "RECORD.json", self.record(ended))
            ok, line = stage.claim_report(folder, study=self.STUDY, began=stage.run_began())
            beat.say(f"report {line}")
            if self.plan_class == "smoke":
                self.verdict = 0 if not smoke_why and ok else 1
            else:
                self.verdict = 0 if self.decision["verdict"] == "met" and ok else 1
            write_json(folder / "ENDED.json", {"folder": self.folder, "run": f"{current.flow_name}/{current.run_id}",
                                               "started": self.started, "ended": utc_now(), "loop": self.decision["verdict"],
                                               "rounds": len(self.rounds), "verdict": self.verdict})
            for said in [*lines, f"report: {line}", f"verdict {self.verdict}"]:
                print(f"QaloopFlow: {said}", flush=True)
            beat.say(f"verdict {self.verdict}")
            stage.finish(self.verdict, [(ok, line)], none_words="; ".join(lines))
        self.trend = read_points(folder / TREND)
        loop_card(self, lines, self.trend)
        tag_run([f"plan:{self.plan_name}", f"chain:{self.chain}", f"loop:{self.decision['verdict'].replace(' ', '_')}"])


if __name__ == "__main__":
    QaloopFlow()
