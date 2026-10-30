"""TotalsegFlow: the C2 and the sacrum TotalSegmentator draws for the gold tier 3 completion, as a launched flow.

The gate word `totalseg complete` queues one GPU job, grid/totalseg-complete.sbatch, on the owner's
word of 2026-10-30 08:54 UTC ("Add sacrum and c2 w total seg") and his count. Its driver holds the
checkout (grid/logs/HOLD), checks the fetched weight zips and the data root, makes the environment
and starts this flow through flows/launch.py:

    python flows/launch.py totalseg --max-workers 1 -- --out <lab volume>/gold3-totalseg --weights <...>/weights

segment runs the job script again with SCHWINGNET_FLOW_STEP=1, its body: the frozen PREREG checked
against its hash, then tools/gold3_totalseg_grid.py prepare, run, check and report (the tool's
docstring says what each does). The body appends its lines to the report the driver began and leaves
its exit in <out>/COMPLETE_RC; the driver ends the report with it. A study whose masks are already
under <out>/ts/<id>/ is not run again, so a job cut short and sent again, which the launcher resumes,
carries on where it stopped; the check and the report read every study anew each time.

The flow runs no network itself: TotalSegmentator runs inside the body, in the job's throwaway
environment. It is held to docs/research/gold3-ct/completion/PREREG.md all the same, since a
segmenter is a network and what it draws is a machine arm of the dataset.
"""

import json
import os
import time
from pathlib import Path

from metaflow import FlowSpec, Parameter, card, current, step
from metaflow.cards import Markdown

import stage

REPO = Path(os.environ.get("SCHWINGNET") or Path(__file__).resolve().parent.parent)
JOB_SCRIPT = REPO / "grid" / "totalseg-complete.sbatch"
KIND = "totalseg"
REFRESH = 15


class TotalsegFault(Exception):
    """Words the segmentation cannot run with."""


def check_words(out, weights):
    for flag, value in (("--out", out), ("--weights", weights)):
        if not Path(value).is_absolute():
            raise TotalsegFault(f"{flag} is a folder on the lab volume, an absolute path, not {value!r}")


def segment_words(out, since):
    """Where the segmenter stands: the studies prepared, from jobs.json, and those with a run.json
    written since this step began."""
    jobs = Path(out) / "jobs.json"
    try:
        if jobs.stat().st_mtime < since:
            return "preparing the studies, then TotalSegmentator on each CT"
        prepared = len(json.loads(jobs.read_text(encoding="utf-8")).get("studies") or [])
    except (OSError, ValueError):
        return "preparing the studies, then TotalSegmentator on each CT"
    done = sum(1 for p in (Path(out) / "ts").glob("*/run.json") if p.stat().st_mtime >= since) if (Path(out) / "ts").is_dir() else 0
    return f"TotalSegmentator: {done} of {prepared} studies run this job"


def finish(verdict, lines):
    """The verdict and the lines on the run's page, where no report is checked."""
    stage.finish(verdict, [], none_words="; ".join(lines) if lines else None)


class TotalsegFlow(FlowSpec):
    """TotalSegmentator's C2 and sacrum for the gold tier 3 studies that lack them: held to the completion's PREREG, run by the job script's body."""

    out = Parameter("out", required=True, help="the job's folder on the lab volume, where the masks, the records and the log are kept")
    weights = Parameter("weights", required=True, help="the folder the weight zips were unpacked into (TOTALSEG_WEIGHTS_PATH)")
    commit = Parameter("commit", default="", help="the commit of the checkout that first started the run, which the launcher passes")

    @step
    def start(self):
        """The words checked and the run held to the completion's frozen PREREG."""
        with stage.Beat(self, "prepare") as beat:
            check_words(self.out, self.weights)
            stage.hold_to_prereg(self, KIND)
            beat.say("TotalSegmentator's C2 and sacrum for the gold tier 3 studies that lack them")
        self.next(self.segment)

    @step
    def segment(self):
        """The body: prepare, run, check and report; its exit kept."""
        since = time.time()
        with stage.Beat(self, "TotalSegmentator") as beat:
            code, out, err = stage.run_watched(["bash", str(JOB_SCRIPT)], beat, lambda: segment_words(self.out, since),
                                               every=REFRESH, env=dict(os.environ, SCHWINGNET_FLOW_STEP="1"), cwd=REPO)
            print(out + err, end="" if (out + err).endswith("\n") else "\n", flush=True)
            self.code = code
            beat.say(f"segment: exit {self.code}")
        self.next(self.end)

    @card(type="blank")
    @step
    def end(self):
        """The verdict, the body's exit."""
        with stage.Beat(self, "verdict") as beat:
            stage.still_held(self, KIND)
            self.verdict = 0 if self.code == 0 else 1
            line = f"segment: exit {self.code}; the report is logs/TOTALSEG-complete.md, which the gate word prints"
            print(f"TotalsegFlow: {line}; verdict {self.verdict}", flush=True)
            beat.say(f"verdict {self.verdict}")
            finish(self.verdict, [line])
        current.card.append(Markdown(f"# TotalSegmentator's C2 and sacrum for the gold tier 3 completion\n\nsegment exited {self.code}; "
                                     f"verdict {self.verdict}. Progress page: {stage.page_path()}."))


if __name__ == "__main__":
    TotalsegFlow()
