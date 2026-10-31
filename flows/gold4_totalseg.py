"""Gold4TotalsegFlow: TotalSegmentator's vertebrae on the gold tier 4 CTs, as a launched flow.

Usage, through the launcher only (grid/totalseg-gold4.sbatch, the gate's word `totalseg gold4`):
    python flows/launch.py gold4_totalseg --max-workers 1 -- --part run --chain <array job> \\
        --out <lab volume>/gold4-totalseg --census <gold4.json> --tiers <tier lists> --weights <weights> \\
        --task <k> --tasks <n>
    python flows/launch.py gold4_totalseg --max-workers 1 -- --part merge --chain <array job> \\
        --out <lab volume>/gold4-totalseg

The owner's word of 2026-10-31 00:55 UTC, "you can start the totalsegmentator segmentation of those
scans currently on the grid", is that TotalSegmentator draws every CT the census found showing C2's
foot and the sacrum's top among the collections no release draws (tools/gold4_totalseg_grid.py says
which and why). A send is one chain: an array of GPU tasks that share the list of CTs by claiming
each, every task one run of this flow with --part run, then one CPU run with --part merge afterany
the array, which reads every unit's record and writes the counts. The chain is among the words, so
every send is a new run, while the units' own records, which outlive the chain, let a send carry on
where the last one stopped.

The rule of 2026-10-29 is kept through flows/stage.py: start holds the run to the kind's frozen
PREREG (docs/research/gold4-totalseg/PREREG.md), end holds it again, since a resume clones start,
and each step keeps its line on the run's progress page, a task's moving with its lines. The flow
runs no network itself: TotalSegmentator runs inside the tool, in the job's throwaway environment.
"""

import os
import re
import sys
from pathlib import Path

from metaflow import FlowSpec, Parameter, card, current, step
from metaflow.cards import Markdown

import stage

REPO = Path(os.environ.get("SCHWINGNET") or Path(__file__).resolve().parent.parent)
TOOL = REPO / "tools" / "gold4_totalseg_grid.py"
KIND = "gold4_totalseg"
PARTS = ("run", "merge")
REFRESH = 15
# The chain: the array job of the send, or none where a person runs a part by hand.
CHAIN = re.compile(r"[0-9]{1,12}|none")


class Gold4TotalsegFault(Exception):
    """Words a part of the segmentation cannot run with, said in words."""


def words_problem(part, chain, out, census, tiers, weights, task, tasks):
    """What keeps the words from naming one part of one chain, or None."""
    if part not in PARTS:
        return f"--part is one of {', '.join(PARTS)}, not {part!r}"
    if not CHAIN.fullmatch(chain or ""):
        return f"--chain is the send's array job or none, not {chain!r}"
    if not Path(out).is_absolute():
        return f"--out is an absolute folder on the lab volume, not {out!r}"
    if part == "merge":
        return None
    for flag, value in (("--census", census), ("--tiers", tiers), ("--weights", weights)):
        if not value or not Path(value).is_absolute():
            return f"a task reads {flag} as an absolute path, not {value!r}"
    if not 0 <= task < tasks:
        return f"--task {task} is outside the chain's {tasks} tasks"
    return None


def last_line(path):
    """The last line of a file, or nothing where it is not there yet."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return ""
    return (text.strip().splitlines() or [""])[-1][:300]


class Gold4TotalsegFlow(FlowSpec):
    """One part of the gold tier 4 segmentation: a task of the array, or the merge; held to its frozen PREREG."""

    part = Parameter("part", required=True, help="run (one task of the array) or merge")
    chain = Parameter("chain", required=True, help="the send's array job, which names the chain's folder, or none")
    out = Parameter("out", required=True, help="the run's folder on the lab volume")
    census = Parameter("census", default="", help="the census's gold4.json, which a task reads")
    tiers = Parameter("tiers", default="", help="the census's tier lists' folder, whose rows name each mask's CT")
    weights = Parameter("weights", default="", help="the folder of the unpacked weight parts (TOTALSEG_WEIGHTS_PATH)")
    task = Parameter("task", type=int, default=0, help="the task's place in the array, from 0")
    tasks = Parameter("tasks", type=int, default=1, help="how many tasks the array holds")
    commit = Parameter("commit", default="", help="the commit of the code that first started the run, which the launcher passes")

    @step
    def start(self):
        """The words checked and the run held to the kind's frozen PREREG."""
        self.label = f"task {self.task} of {self.tasks}" if self.part == "run" else "merge"
        with stage.Beat(self, f"{self.label}: the PREREG") as beat:
            fault = words_problem(self.part, self.chain, self.out, self.census, self.tiers, self.weights, self.task, self.tasks)
            if fault:
                raise Gold4TotalsegFault(fault)
            stage.hold_to_prereg(self, KIND)
            beat.say(f"{self.label} of chain {self.chain}; held to {self.prereg_path}, sha256 {self.prereg_sha256[:16]}")
        self.next(self.work)

    def command(self):
        common = ["--out", self.out, "--chain", self.chain, "--commit", self.commit]
        if self.part == "merge":
            return [sys.executable, str(TOOL), "merge", *common]
        threads = os.environ.get("SLURM_CPUS_PER_TASK") or "4"
        return [sys.executable, str(TOOL), "run", *common, "--census", self.census, "--tiers", self.tiers,
                "--weights", self.weights, "--task", str(self.task), "--tasks", str(self.tasks), "--threads", threads,
                "--device", "gpu"]

    def progress_file(self):
        chain = Path(self.out) / "chains" / self.chain
        return chain / "tasks" / f"{self.task}.txt" if self.part == "run" else chain / "REPORT.md"

    @step
    def work(self):
        """The part's tool run to its end; its exit is kept, not raised, so end always runs and says how it ended."""
        with stage.Beat(self, self.label) as beat:
            command = self.command()
            beat.say(f"{self.label}: running")
            code, out, err = stage.run_watched(command, beat, lambda: last_line(self.progress_file()) or f"{self.label}: running",
                                               every=REFRESH, cwd=REPO)
            print(out + err, end="" if (out + err).endswith("\n") else "\n", flush=True)
            self.code = code
            self.said = f"{self.label}: exit {code}"
            beat.say(self.said)
        self.next(self.end)

    @card(type="blank")
    @step
    def end(self):
        """The run held again to the PREREG start kept, and the verdict: 0 only where the part's tool ended 0."""
        with stage.Beat(self, f"{self.label}: verdict") as beat:
            stage.still_held(self, KIND)
            self.verdict = 0 if self.code == 0 else 1
            lines = [self.said, "the counts are the merge's REPORT.md, which the job script copies into logs/TOTALSEG-gold4.md"]
            for line in [*lines, f"verdict {self.verdict}"]:
                print(f"Gold4TotalsegFlow: {line}", flush=True)
            beat.say(f"verdict {self.verdict}")
            stage.finish(self.verdict, [], none_words="; ".join(lines))
        current.card.append(Markdown(f"# TotalSegmentator on the gold tier 4 CTs, {self.label}\n\nChain {self.chain}; exit {self.code}; "
                                     f"verdict {self.verdict}; progress page {stage.page_path()}."))


if __name__ == "__main__":
    Gold4TotalsegFlow()
