"""The auto-anatomist screen as a Metaflow flow (docs/research/autoanatomist-screen/PREREG.md).

Usage, through the launcher only (grid/autoanatomist.sbatch, the gate's word `autoanatomist <plan>`):
    python flows/launch.py autoanatomist --max-workers 1 -- --part trial \\
        --plan grid/screens/<plan>.json --chain <job> --out <screen root> --data <data root> \\
        --task <n> --tasks <trials>
    python flows/launch.py autoanatomist --max-workers 1 -- --part join \\
        --plan grid/screens/<plan>.json --chain <job> --out <screen root> --tasks <trials>

A screen is a plan under grid/screens/ (schwingnet.autoanatomist_screen): every arm trained at
every seed on the plan's rows, each trial one run of this flow on one card, then the join, one run
on a CPU node that reads every trial's entry and decides each arm against the null. A run is one
part, trial or join, of one chain, the Slurm job the gate's send made (the trials' array job, or
the series job of a plan whose trials run one after another on one card), and every part of a
chain works in one folder, <out>/<screen>/<chain>/: a trial in trials/<trial>/ of it
(tools/autoanatomist_trial.py), the join in join/ (tools/autoanatomist_join.py), and the join's end
at the folder's top, where it writes RECORD.json, SUMMARY.md and the CLAIM 2024 and REFORMS report
(tools/report.py --study autoanatomist-screen), whose check decides the verdict with the join's
exit. The chain is among the words, so every send is a new run and a new folder, and a failed trial
is never carried into another send; a trial that fails is shown failed by the join, never dropped.

The rule of 2026-10-29 is kept through flows/stage.py: start holds the run to the kind's frozen
PREREG and to the part of it that covers the plan by its bytes, as the sweep's plans are, and then
refuses a plan that does not hold or whose rows leave the frozen split or stand on a test list;
end holds it again, since a resume clones start; each step keeps its line on the run's progress
page, a trial's moving with its PROGRESS.txt.
"""

import hashlib
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
for _path in (REPO / "vendor" / "beethoven-qa" / "src", REPO / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from schwingnet import autoanatomist_screen as screen  # noqa: E402

KIND = "autoanatomist"
STUDY = "autoanatomist-screen"
PARTS = ("trial", "join")
TRIAL_TOOL = REPO / "tools" / "autoanatomist_trial.py"
JOIN_TOOL = REPO / "tools" / "autoanatomist_join.py"
RULE = REPO / "data" / "splits" / "rule.json"
REFRESH = 15
# The chain: the Slurm job the gate's send made, or none where a person runs a part by hand.
CHAIN = re.compile(r"[0-9]{1,12}|none")
# What the join's end writes once the record is written, and the record: none of it is the work.
END_WRITES = ("RECORD.json", "ENDED.json", "SUMMARY.md", *stage.REPORT_OUTPUTS)
# The join's exits that leave a decision to report: every trial held (0), or some did not (3).
JOIN_DECIDED = (0, 3)


class AutoanatomistFault(Exception):
    """Words or a plan a part of the screen cannot run with, said in words."""


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
    """The plan's name, grid/screens/<name>.json, the part of the screen's PREREG a run of it is."""
    return Path(plan_file).stem if plan_file else ""


def prereg_part(words, folder):
    """The part a run of these words is, for the launcher: the plan's name and the sha256 of its
    bytes, whatever --part says, since a trial and the join of one plan are one design; a plan made
    again or edited since the freeze is another design under the same name."""
    plan_file = from_launcher(word_value(words, "--plan"), folder)
    return plan_part(plan_file), file_sha256(plan_file)


def key_reads(words, folder):
    """What a run of these words reads that the words do not name, for the launcher's key: the plan
    file's bytes, since start checks the plan and resume clones start."""
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


def test_persons():
    """Every person on a list a screen never reads (schwingnet.autoanatomist_screen.TEST_LISTS)."""
    persons = set()
    for path in screen.TEST_LISTS:
        entries = read_json(REPO / path)
        if not isinstance(entries, list):
            raise AutoanatomistFault(f"{path} cannot be read as a list of persons")
        persons |= {entry["person"] for entry in entries}
    return frozenset(persons)


def plan_in_force(plan_file):
    """The plan a file holds, checked whole and against the frozen split and the test lists."""
    record = read_json(plan_file)
    if record is None:
        raise AutoanatomistFault(f"the plan {plan_file} cannot be read as JSON")
    found = screen.plan_problems(record)
    rule = read_json(RULE) or {}
    if not found and record["screen"] != plan_part(plan_file):
        # The job script keeps its step files in <out>/<plan>/<chain>/, the folder the run works in.
        found = [f"screen: the plan's own name, {plan_part(plan_file)}, not {record['screen']!r}"]
    if not found:
        found = screen.rows_problems(record, str(rule.get("salt")), float(rule.get("validation_share", 0.0)),
                                     test_persons())
    if found:
        raise AutoanatomistFault(f"the plan {Path(plan_file).name} does not hold: {found[0]}")
    return screen.plan_of(record)


def words_problems(flow, plan):
    """What keeps the words from naming one part of the plan's screen, or None."""
    if flow.part not in PARTS:
        return f"--part is one of {', '.join(PARTS)}, not {flow.part!r}"
    if not CHAIN.fullmatch(flow.chain or ""):
        return f"--chain is the send's Slurm job or none, not {flow.chain!r}"
    if not Path(flow.out).is_absolute():
        return f"--out is an absolute folder on the lab volume, not {flow.out!r}"
    count = len(screen.trials(plan))
    if flow.part == "join":
        return None if flow.tasks == count else f"--tasks is the plan's {count} trials, not {flow.tasks}"
    if not flow.data or not Path(flow.data).is_absolute():
        return "a trial reads the data root, an absolute --data"
    found = screen.task_problems(plan, flow.task, flow.tasks)
    return found[0] if found else None


class AutoanatomistFlow(FlowSpec):
    part = Parameter("part", required=True, help="trial or join")
    plan = Parameter("plan", required=True, help="the plan, grid/screens/<plan>.json")
    chain = Parameter("chain", required=True, help="the send's Slurm job, the trials' array or the series job, or none")
    out = Parameter("out", required=True, help="the screen root, under which each chain keeps <screen>/<chain>/")
    data = Parameter("data", default="", help="the data root a trial reads the plan's CTs and label maps under")
    task = Parameter("task", type=int, default=0, help="a trial's place in the plan's order, from 0")
    tasks = Parameter("tasks", type=int, default=1, help="how many trials the plan holds")
    commit = Parameter("commit", default="", help="the commit of the code that first started the run, which the launcher passes")

    @step
    def start(self):
        """The run held to the frozen PREREG and the plan's part of it, the plan checked against the
        frozen split, the words against the plan, and the chain's folder made."""
        with stage.Beat(self, f"{self.part}: the PREREG and the plan") as beat:
            self.plan_file = from_launcher(self.plan)
            stage.hold_to_prereg(self, KIND, plan_part(self.plan_file), file_sha256(self.plan_file))
            plan = plan_in_force(self.plan_file)
            fault = words_problems(self, plan)
            if fault:
                raise AutoanatomistFault(fault)
            self.screen_name, self.key = plan.screen, run_key()
            self.trial = screen.trials(plan)[self.task].id if self.part == "trial" else None
            self.label = f"trial {self.trial}" if self.trial else "join"
            self.folder = str(Path(self.out) / plan.screen / self.chain)
            Path(self.folder).mkdir(parents=True, exist_ok=True)
            self.started = utc_now()
            self.where = {"host": socket.gethostname(), "slurm_job": os.environ.get("SLURM_JOB_ID") or "none",
                          "run": f"{current.flow_name}/{current.run_id}", "datastore": stage.datastore_root(), **code_state()}
            beat.say(f"{self.label} of {plan.screen}, chain {self.chain}; held to {self.prereg_path}, "
                     f"sha256 {self.prereg_sha256[:16]}; folder {self.folder}")
        self.next(self.work)

    def command(self):
        if self.part == "trial":
            return [sys.executable, str(TRIAL_TOOL), "--plan", self.plan_file, "--task", str(self.task), "--tasks",
                    str(self.tasks), "--data", self.data, "--out", self.folder]
        return [sys.executable, str(JOIN_TOOL), "--plan", self.plan_file, "--out", self.folder]

    def progress_file(self):
        return Path(self.folder) / "trials" / self.trial / "PROGRESS.txt" if self.trial else Path(self.folder) / "join.txt"

    @step
    def work(self):
        """The part's tool run to its end, its output kept in the folder's logs/; its exit is kept,
        not raised, so end always runs and says how the part ended."""
        with stage.Beat(self, self.label) as beat:
            command = self.command()
            beat.say(f"{self.label}: running")
            code, out, err = stage.run_watched(command, beat, lambda: last_line(self.progress_file()) or f"{self.label}: running",
                                               every=REFRESH, cwd=REPO)
            logs = Path(self.folder) / "logs"
            logs.mkdir(parents=True, exist_ok=True)
            with open(logs / f"{self.trial or 'join'}.log", "a", encoding="utf-8") as log:
                log.write(f"$ {' '.join(command)}\n{out}{err}\n")
            print(out + err, end="" if (out + err).endswith("\n") else "\n", flush=True)
            self.code = code
            self.said = f"{self.label}: exit {code}"
            beat.say(self.said)
        self.next(self.end)

    def record(self, ended):
        """The join's record: the run, the design it ran under, the plan's trials and every file
        the report reads, each by its sha256."""
        folder = Path(self.folder)
        names = [p for p in sorted(folder.glob("trials/*/*")) if p.name in ("entry.json", "environment.json", "why.txt")]
        names += [folder / "join" / name for name in ("DECISION.json", "SUMMARY.md") if (folder / "join" / name).is_file()]
        plan = screen.plan_of(read_json(self.plan_file))
        return {"study": STUDY, "part": "join", "run": self.where["run"], "key": self.key, "commit": self.commit,
                "prereg": self.prereg_path, "prereg_sha256": self.prereg_sha256, "prereg_part": self.prereg_part,
                "prereg_part_sha256": self.prereg_part_sha256, "chain": self.chain, "started": self.started,
                "ended": ended["ended"], "where": self.where, "ended_in": ended,
                "plan": {"file": f"grid/screens/{Path(self.plan_file).name}", "screen": plan.screen,
                         "rows": {part: sum(1 for r in plan.rows if r["part"] == part) for part in ("train", "validation")},
                         "epochs": plan.epochs, "evaluate_every": plan.evaluate_every, "batch": plan.batch,
                         "measure": plan.measure, "null": plan.null, "seeds": list(plan.seeds)},
                "trials": [{"id": t.id, "arm": t.arm, "seed": t.seed, "words": list(t.words)} for t in screen.trials(plan)],
                "files": {str(path.relative_to(folder)): file_sha256(path) for path in names},
                "progress_page": str(stage.page_path())}

    def join_end(self, beat):
        """RECORD.json and SUMMARY.md at the folder's top, then the report written and checked."""
        folder = Path(self.folder)
        for name in END_WRITES:
            (folder / name).unlink(missing_ok=True)
        decision = read_json(folder / "join" / "DECISION.json") or {}
        lines = [self.said] + [f"{arm}: {'beats the null' if d.get('beats_null') else 'undecided' if d.get('beats_null') is None else 'does not beat the null'}"
                               for arm, d in sorted((decision.get("arms") or {}).items())]
        lines += [f"{trial} failed: {why}" for trial, why in sorted((decision.get("failed") or {}).items())]
        (folder / "SUMMARY.md").write_text("\n".join(f"- {line}" for line in lines) + "\n", encoding="utf-8")
        ended = {"run": f"{current.flow_name}/{current.run_id}", "host": socket.gethostname(),
                 "slurm_job": os.environ.get("SLURM_JOB_ID") or "none", "ended": utc_now(), **code_state()}
        write_json(folder / "RECORD.json", self.record(ended))
        ok, line = stage.claim_report(folder, study=STUDY, began=stage.run_began())
        beat.say(f"report {line}")
        return lines, [(ok, line)]

    @card(type="blank")
    @step
    def end(self):
        """The run held again to the PREREG start kept; for the join, the record and the report
        when it decided, and the verdict: 0 only where the part's tool ended 0 and the report holds."""
        with stage.Beat(self, "the record and the report" if self.part == "join" else self.label) as beat:
            stage.still_held(self, KIND)
            lines, reports = [self.said], []
            if self.part == "join" and self.code in JOIN_DECIDED:
                lines, reports = self.join_end(beat)
            elif self.part == "join":
                lines.append("the join did not decide, so it leaves no record to report")
            else:
                lines.append("the screen's CLAIM and REFORMS report is the join's")
            self.verdict = 0 if self.code == 0 and all(ok for ok, _ in reports) else 1
            ended = {"folder": self.folder, "part": self.part, "trial": self.trial, "run": f"{current.flow_name}/{current.run_id}",
                     "started": self.started, "ended": utc_now(), "code": self.code, "verdict": self.verdict}
            write_json(Path(self.folder) / ("ENDED.json" if self.part == "join" else f"trials/{self.trial}/ENDED.json"), ended)
            for line in [*lines, *(f"report: {r}" for _, r in reports), f"verdict {self.verdict}"]:
                print(f"AutoanatomistFlow: {line}", flush=True)
            beat.say(f"verdict {self.verdict}")
            stage.finish(self.verdict, reports, none_words="; ".join(lines))
        current.card.append(Markdown(f"# Auto-anatomist screen, {self.label}\n\nChain {self.chain}, folder {self.folder}; "
                                     f"verdict {self.verdict}; progress page {stage.page_path()}.\n\n"
                                     + "\n".join(f"- {line}" for line in lines)))


if __name__ == "__main__":
    AutoanatomistFlow()
