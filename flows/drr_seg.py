"""DrrSegFlow: MOOSE's masks for the DRR domain-gap study's CTs as a launched flow (the owner's rule of 2026-10-29).

The gate word `bench flexray_drr_seg` queues one GPU job, grid/drr-seg.sbatch, sent before the
study's prepare where MOOSE's masks are missing. Its driver holds the checkout (grid/logs/HOLD),
checks the CTs, SPINEPS's masks and MOOSE's fetched model zips, makes the environment and then
starts this flow through flows/launch.py:

    python flows/launch.py drr_seg --max-workers 1 -- --out <bench root>/flexray_drr_seg --masks <data root>/moose

segment runs the job script again with SCHWINGNET_FLOW_STEP=1, its body: the frozen PREREG checked
against its hash, the study's choice of CTs (tools/domain_gap.py plan, rendering nothing) and MOOSE
on exactly those (tools/flexray_render.py segment, moosez's Python entry on the fetched zips, never a
download), the masks written under the data root's moose in moosez's own layout. The body appends
its lines to the bench report the driver began and leaves its exit in <out>/SEGMENT_RC; the driver
ends the report with it, or with the launcher's code where the body ended 0 and the flow did not.
A job cut short after segment ended, in end, is resumed by the next send with segment cloned and
not run again, so it leaves no SEGMENT_RC, and the driver takes the flow's 0, which only a segment
that ended 0 gives, as the masks' exit.

No mask that exists is written again. The choice of CTs ignores MOOSE's masks, so the same inputs
give the same choice on every start, and the segment subcommand's plan marks a subject done when a
file of every model is there, found by the region word in its name, and runs only the models a
subject lacks, writing their files beside the others. So a job cut short and sent again, which the
launcher resumes with start cloned and segment run again, segments no subject whose files are all
there. A file moosez was writing when the job was cut is there by its name too, and is not written
again: such a file fails a test of its gzip stream (gzip -t), which nothing here runs. The
subcommand writes its own record, SEGMENT.json, beside the masks, so the driver keeps the record an
earlier job left there in its own folder first.

The flow runs no network itself and makes no study report: its masks are an input of the study,
whose report is the merge's (flows/drr_gap.py). It is held to the study's frozen PREREG all the
same, since MOOSE is a network and the choice of CTs is the study's.
"""

import inspect
import json
import os
import time
from pathlib import Path

from metaflow import FlowSpec, Parameter, card, current, step
from metaflow.cards import Markdown

import stage

REPO = Path(os.environ.get("SCHWINGNET") or Path(__file__).resolve().parent.parent)
SEG_SCRIPT = REPO / "grid" / "drr-seg.sbatch"
KIND = "drr_seg"
REFRESH = 15


class DrrSegFault(Exception):
    """Words the segmentation cannot run with."""


def check_words(out, masks):
    for flag, value in (("--out", out), ("--masks", masks)):
        if not Path(value).is_absolute():
            raise DrrSegFault(f"{flag} is a folder on the lab volume, an absolute path, not {value!r}")


def segment_words(masks, since):
    """Where MOOSE stands, from the record the segment subcommand rewrites after each subject; the
    record an earlier run left says nothing of this one."""
    record = Path(masks) / "SEGMENT.json"
    try:
        if record.stat().st_mtime < since:
            return "choosing the CTs, then MOOSE on those that lack masks"
        said = json.loads(record.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "choosing the CTs, then MOOSE on those that lack masks"
    plan = said.get("plan") or {}
    return f"MOOSE: {len(said.get('done') or [])} of {plan.get('to_run', '?')} subjects segmented"


def finish(verdict, lines):
    """The verdict and the lines on the run's page, by flows/stage.py's finish in whichever form it has."""
    if "none_words" in inspect.signature(stage.finish).parameters:
        stage.finish(verdict, [], none_words="; ".join(lines) if lines else None)
    else:
        stage.finish(verdict, lines)


class DrrSegFlow(FlowSpec):
    """MOOSE's masks for the study's CTs: held to the study's PREREG, run by the job script's body."""

    out = Parameter("out", required=True, help="the job's folder, where the choice of CTs and its log are kept")
    masks = Parameter("masks", required=True, help="the data root's moose folder, where the masks are written")
    commit = Parameter("commit", default="", help="the commit of the checkout that first started the run, which the launcher passes")

    @step
    def start(self):
        """The words checked and the run held to the study's frozen PREREG."""
        with stage.Beat(self, "prepare") as beat:
            check_words(self.out, self.masks)
            stage.hold_to_prereg(self, KIND)
            beat.say("MOOSE's masks for the study's CTs")
        self.next(self.segment)

    @step
    def segment(self):
        """The body: the choice of CTs and MOOSE on those that lack masks; its exit kept."""
        since = time.time()
        with stage.Beat(self, "MOOSE") as beat:
            code, out, err = stage.run_watched(["bash", str(SEG_SCRIPT)], beat, lambda: segment_words(self.masks, since),
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
            still_held = getattr(stage, "still_held", None)
            if still_held:
                still_held(self, KIND)
            self.verdict = 0 if self.code == 0 else 1
            line = f"segment: exit {self.code}; the study's report is its merge's, which reads these masks"
            print(f"DrrSegFlow: {line}; verdict {self.verdict}", flush=True)
            beat.say(f"verdict {self.verdict}")
            finish(self.verdict, [line])
        current.card.append(Markdown(f"# MOOSE masks for the DRR domain-gap study\n\nsegment exited {self.code}; "
                                     f"verdict {self.verdict}. Progress page: {stage.page_path()}."))


if __name__ == "__main__":
    DrrSegFlow()
