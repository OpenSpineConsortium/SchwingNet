"""DrrGapFlow: one part of the DRR domain-gap study as a launched flow (the owner's rule of 2026-10-29).

The study (tools/domain_gap.py, docs/research/drr-domain-gap/README.md) runs as three kinds of
Slurm job, which the gate word `bench flexray_drr_gap` queues: prepare, an array of shards and the
merge. Each job, and each task of the array, is the driver of grid/drr-gap.sbatch, which does what
must be done on the node before any flow (prepare copies the code at its commit, every part checks
its input and makes the study's environment) and then starts this flow through flows/launch.py
from that copy of the code:

    python flows/launch.py drr_gap --max-workers 1 -- --part shard --prepare-job 40859208 \\
        --out <bench root>/flexray_drr_gap --task 3 --tasks 16

The launcher names the run by its words and by tools/run_code.py's digest of the code the kind
runs, read from the copy's COPY.txt where the copy holds no .git, and resumes the newest run of the
same key that did not finish: a part sent again with the same words carries its run on, and every
part of one chain names its prepare job, so a new chain is always a new run. A resume runs inside
the job that was sent and queues nothing; this flow retries nothing itself, since each part's work
keeps its own state on the lab volume (the shards' claims, prepare's PREPARED.json) and a part
started again goes on from there.

start holds the run to the study's frozen PREREG.md (flows/stage.py, hold_to_prereg; the PREREG
covers the whole study, so no part is named). work runs the job script again with
SCHWINGNET_FLOW_STEP=1, the part's body, which writes the part's own lines under
<out>/analysis/steps/ and, for the merge, the bench report in the checkout's grid/logs; the step's
line on the run's page follows the last line of the study's <out>/PROGRESS.txt while it runs. The
body's exit is kept, not raised, so end always runs. end gives the verdict: for the merge, whose
body leaves the run's record under <out>/runs/<prepare job>/ (BENCH.md and summary.txt, as a
recorded run of the study holds them), the study's CLAIM and REFORMS report is written and checked
there (tools/report.py --study drr-domain-gap, through stage.claim_report) and the verdict is 0
only where the merge ended 0 and that report is current; prepare's and a shard's runs report their
part's own exit and make no study report, since the study's numbers are the merge's. The job ends
with the body's exit line, unless the body ended 0 and the flow did not, when the driver ends it
with the launcher's code and says why in the part's file and, for the merge, in the report.
"""

import json
import os
import re
from pathlib import Path

from metaflow import FlowSpec, Parameter, card, current, step
from metaflow.cards import Markdown

import stage

REPO = Path(os.environ.get("SCHWINGNET") or Path(__file__).resolve().parent.parent)
STUDY_SCRIPT = REPO / "grid" / "drr-gap.sbatch"
KIND = "drr_gap"
STUDY = "drr-domain-gap"
PARTS = ("prepare", "shard", "merge")
REFRESH = 15
# A prepare job as the driver names it: Slurm's number, or none outside Slurm.
JOB_WORD = re.compile(r"[0-9]{1,12}|none")


class DrrGapFault(Exception):
    """Words a part of the study cannot run with."""


def part_label(part, task, tasks):
    """The part as the run's page names its step."""
    return f"shard {task} of {tasks}" if part == "shard" else part


def check_words(part, prepare_job, task, tasks, out):
    """The words a run takes, refused in words before any work: a part the study has, a prepare job
    that names a folder, a shard's task within its array, and an absolute folder for the study."""
    if part not in PARTS:
        raise DrrGapFault(f"--part is one of {', '.join(PARTS)}, not {part!r}")
    if not JOB_WORD.fullmatch(prepare_job or ""):
        raise DrrGapFault(f"--prepare-job is the chain's prepare job as Slurm numbers it, not {prepare_job!r}")
    if part == "shard" and not 0 <= task < tasks:
        raise DrrGapFault(f"a shard's --task lies from 0 to --tasks less one, not {task} of {tasks}")
    if tasks < 0:
        raise DrrGapFault(f"--tasks counts the array's tasks, not {tasks}")
    if not Path(out).is_absolute():
        raise DrrGapFault(f"--out is the study's folder on the lab volume, an absolute path, not {out!r}")


def record_folder(out, prepare_job):
    """Where the merge leaves the run's record, as a recorded run of the study is kept: under its
    prepare job's number."""
    return Path(out) / "runs" / prepare_job


def body_env(flow):
    """The part's body: the job script again, told it is the flow's step and given the words."""
    env = dict(os.environ, SCHWINGNET_FLOW_STEP="1", STEP=flow.part, PREPARE_JOB=flow.prepare_job, DRR_GAP_OUT=flow.out)
    if flow.part == "shard":
        env.update(DRR_GAP_TASK=str(flow.task), DRR_GAP_TASK_COUNT=str(flow.tasks))
    if flow.part == "merge":
        env.update(SHARD_TASKS=str(flow.tasks), SN_STUDY_RECORD=str(record_folder(flow.out, flow.prepare_job)))
    return env


def last_line(path):
    """A file's last line that says something, for the step's line on the page; None where there is none yet."""
    try:
        lines = [line.strip() for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines()]
    except OSError:
        return None
    lines = [line for line in lines if line]
    return lines[-1] if lines else None


def part_words(part, code):
    """The part's own line for the page and the job's log, from its body's exit."""
    if code == 0:
        return f"{part}: exit 0"
    return f"{part}: exit {code}, as its line under analysis/steps/ says"


def verdict_of(code, report_ok):
    """0 where the part's body ended 0 and, for the merge, the study's report is current; else 1."""
    return 0 if code == 0 and report_ok else 1


def finish(verdict, reports, lines):
    """The verdict and the lines on the run's page: the reports as stage.claim_report gives them, and
    the part's own lines where no report was checked."""
    stage.finish(verdict, reports, none_words="; ".join(lines) if lines else None)


class DrrGapFlow(FlowSpec):
    """One part of the DRR domain-gap study: held to its PREREG, run by the job script's body, reported."""

    part = Parameter("part", required=True, help="the study's part: prepare, shard or merge")
    prepare_job = Parameter("prepare-job", required=True, help="the chain's prepare job, which names its record")
    task = Parameter("task", type=int, default=0, help="a shard's task in the array")
    tasks = Parameter("tasks", type=int, default=1, help="the array's count of tasks, for a shard and the merge")
    out = Parameter("out", required=True, help="the study's folder on the lab volume")
    commit = Parameter("commit", default="", help="the commit of the code that first started the run, which the launcher passes")

    @step
    def start(self):
        """The words checked and the run held to the study's frozen PREREG."""
        self.label = part_label(self.part, self.task, self.tasks)
        with stage.Beat(self, self.label) as beat:
            check_words(self.part, self.prepare_job, self.task, self.tasks, self.out)
            stage.hold_to_prereg(self, KIND)
            beat.say(f"{self.label} of the chain of prepare job {self.prepare_job}")
        self.next(self.work)

    @step
    def work(self):
        """The part's body, its exit kept; the page follows the study's PROGRESS.txt."""
        progress = Path(self.out) / "PROGRESS.txt"
        with stage.Beat(self, self.label) as beat:
            code, out, err = stage.run_watched(["bash", str(STUDY_SCRIPT)], beat, lambda: last_line(progress), every=REFRESH,
                                               env=body_env(self), cwd=REPO)
            print(out + err, end="" if (out + err).endswith("\n") else "\n", flush=True)
            self.code = code
            self.said = part_words(self.label, code)
            beat.say(self.said)
        self.next(self.end)

    @card(type="blank")
    @step
    def end(self):
        """The verdict: the part's exit, and for the merge the study's CLAIM and REFORMS report."""
        with stage.Beat(self, "report") as beat:
            stage.still_held(self, KIND)
            reports, report_ok = [], True
            lines = [self.said]
            if self.part == "merge" and self.code == 0:
                record = record_folder(self.out, self.prepare_job)
                reports = [stage.claim_report(record, STUDY, began=stage.run_began())]
                report_ok = reports[0][0]
                pathspec = f"{current.flow_name}/{current.run_id}"
                note = {"flow": "DrrGapFlow", "run": pathspec, "root": stage.datastore_root(), "page": str(stage.page_path())}
                try:
                    (record / "METAFLOW.json").write_text(json.dumps(note, indent=1, sort_keys=True) + "\n", encoding="utf-8")
                except OSError as error:
                    print(f"DrrGapFlow: METAFLOW.json could not be written in the record ({error})", flush=True)
            else:
                lines.append("the study's CLAIM and REFORMS report is the merge's" if self.part != "merge"
                             else "the merge did not end 0, so it left no record to report")
            self.verdict = verdict_of(self.code, report_ok)
            for _, line in reports:
                print(f"DrrGapFlow: report {line}", flush=True)
            print(f"DrrGapFlow: {self.said}; verdict {self.verdict}", flush=True)
            beat.say(f"verdict {self.verdict}")
            finish(self.verdict, reports, lines)
        current.card.append(Markdown(f"# DRR domain-gap study, {self.label}\n\n{self.said}; verdict {self.verdict}. "
                                     f"Progress page: {stage.page_path()}."))


if __name__ == "__main__":
    DrrGapFlow()
