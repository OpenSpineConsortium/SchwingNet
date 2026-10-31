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
import os
import re
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from metaflow import FlowSpec, Parameter, card, current, step
from metaflow.cards import Markdown

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
# A round's tool is run at most this many times in its task before the loop ends failed.
ROUND_TRIES = 2
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
    return {"round": n, "exit": code, "tries": tries, "gates": said, "verdict": decision["verdict"],
            "why": decision["why"], "changes": decision.get("changes", []), "stuck": decision.get("stuck", []),
            "config": (record or {}).get("config"), "held_distance_mm": held.get("distance_mm"),
            "held_dice": held.get("dice"), "chosen": fingerprint.get("chosen"),
            "seconds": (record or {}).get("seconds"), "stand_in": (record or {}).get("stand_in")}


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


class QaloopFlow(FlowSpec):
    KIND = KIND
    STUDY = STUDY
    plan = Parameter("plan", required=True, help="the plan, grid/qaloop/<plan>.json")
    chain = Parameter("chain", required=True, help="the send's Slurm job, or none")
    out = Parameter("out", required=True, help="the loop root, under which each chain keeps <plan>/<chain>/")
    data = Parameter("data", default="", help="the data root the real pairs are read under (carmlspine/)")
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
            self.state = {"round": 0, "config": dict(plan["start"]), "held": [], "space": {}, "session": ""}
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

    def run_tool(self, n, beat):
        """The round's tool run to its end, at most ROUND_TRIES times; (exit, tries)."""
        folder = self.round_folder(n)
        command = [sys.executable, str(ROUND_TOOL), "--plan", self.plan_file, "--state", str(folder / "state.json"),
                   "--out", str(folder), "--work", str(Path(self.folder) / "work"), "--data", self.data,
                   "--workers", str(self.workers)]
        logs = Path(self.folder) / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        code, tries = 1, 0
        while tries < ROUND_TRIES:
            tries += 1
            (folder / "gates.json").unlink(missing_ok=True)
            code, out, err = stage.run_watched(command, beat, lambda: last_line(folder / "PROGRESS.txt") or f"round {n}: running",
                                               every=REFRESH, cwd=REPO)
            with open(logs / f"round-{n:03d}.log", "a", encoding="utf-8") as log:
                log.write(f"$ {' '.join(command)}\n{out}{err}\n")
            if code == 0 or code == 2:
                break
            beat.say(f"round {n}: exit {code}" + ("; running it once more" if tries < ROUND_TRIES else ""))
        return code, tries

    @step
    def round(self):
        """One round: the tool trains and asks every gate, the controller decides, and the loop goes
        round again or ends."""
        plan = read_json(self.plan_file)
        n = int(self.state["round"])
        with stage.Beat(self, f"round {n}") as beat:
            folder = self.round_folder(n)
            folder.mkdir(parents=True, exist_ok=True)
            self.drop_old_session(n)
            write_json(folder / "state.json", self.state)
            code, tries = self.run_tool(n, beat)
            record = read_json(folder / "gates.json") if code == 0 else None
            if record is None:
                why = last_line(folder / "why.txt") or "no why.txt"
                decision = {"branch": "done", "verdict": "failed", "why": f"round {n}'s tool exited {code}: {why}",
                            "changes": [], "stuck": [], "passing": [], "failing": []}
            else:
                decision = G.controller(record, self.state, plan)
            write_json(folder / "decision.json", decision)
            self.rounds = self.rounds + [round_summary(n, record, decision, code, tries)]
            self.decision = decision
            if decision["branch"] == "again":
                held = (record.get("held") or {}).get("distance_mm")
                self.state = {"round": n + 1, "config": decision["config"], "held": self.state["held"] + [held],
                              "space": record.get("space") or {}, "session": str(folder / "session")}
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
        current.card.append(Markdown(f"# QA loop, {self.plan_name}\n\nChain {self.chain}, folder {self.folder}; "
                                     f"verdict {self.verdict}; progress page {stage.page_path()}.\n\n"
                                     + "\n".join(f"- {said}" for said in lines)))


if __name__ == "__main__":
    QaloopFlow()
