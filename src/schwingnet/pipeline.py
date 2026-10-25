"""Which Metaflow run a launch of a pipeline flow continues, and the key that says it is the same.

The grid's jobs are killed from outside: a Slurm time limit or a preemption ends the whole job,
and the gate word that queued it queues it again. Metaflow carries a run that did not finish
on with `resume --origin-run-id`, which clones every step that finished and runs only the rest,
but only when it is told which run to carry on. flows/launch.py asks these two rules: the key
names a launch by the flow, the code it runs, the flow's own parameters and what it reads beyond
them, so a job queued again with the same words on the same inputs finds the run it began, and a
change of code, of configuration or of an input starts afresh; the decision then looks at the
runs carrying that key, newest first, and never resumes one that is still running, which every
launcher says by a heartbeat while its flow lasts, nor one whose parameters Metaflow never saved,
which Metaflow cannot resume. Nothing here reads a file, starts a process or asks Metaflow; the
launcher does, and hands the runs over as RunState and the beats as Beat.
"""

import hashlib
import json
from collections.abc import Sequence
from typing import NamedTuple

from beartype import beartype
from beethoven_qa.contracts import ensure, require

RUN_KEY_LENGTH = 16
HEX = frozenset("0123456789abcdef")
RUN = "run"
RESUME = "resume"
# A launcher rewrites its beat every minute; one older than this is a launcher gone with its job,
# five beats missed, room for a slow volume and for the clocks of two nodes.
LIVE_SECONDS = 300.0


def _is_hex(text: str) -> bool:
    """Hex digits only, checked on the result."""
    return all(c in HEX for c in text)


class RunState(NamedTuple):
    """What Metaflow says of one earlier run of the flow: its id, and whether it ended well;
    whether a launcher still runs it, which marked_live says; and whether Metaflow saved its
    parameters, which it does after it has registered the run and before any step runs."""

    run_id: str
    finished: bool
    successful: bool
    live: bool = False
    parameters_saved: bool = True


class Beat(NamedTuple):
    """What a launcher's heartbeat says: the run it holds, "" before Metaflow has named it; the
    Slurm job it runs in, "" outside one; and when it last beat, in seconds since the epoch."""

    run_id: str
    slurm_job: str
    beat: float


@beartype
@ensure(
    lambda result, beat, now: not result or now - beat.beat <= LIVE_SECONDS,
    "a live beat is fresh",
)
@ensure(
    lambda result, beat, job: not result or job == "" or beat.slurm_job != job,
    "no beat of this very Slurm job is live",
)
def is_live(beat: Beat, job: str, now: float) -> bool:
    """Whether a beat still speaks for a launcher: written within LIVE_SECONDS of now, a beat
    from a clock ahead of this one among them, and not by the Slurm job this launcher runs in,
    since a job Slurm queues again keeps its id, so a beat of its own id was left by its earlier
    start, which Slurm ended. Outside Slurm, job is "" and that rule names no beat."""
    return now - beat.beat <= LIVE_SECONDS and not (job != "" and beat.slurm_job == job)


@beartype
@require(lambda runs: all(len(run.run_id) > 0 for run in runs), "every run has an id")
@ensure(
    lambda result, runs: (
        [run._replace(live=False) for run in result] == [run._replace(live=False) for run in runs]
    ),
    "only whether a run is live is marked",
)
@ensure(
    lambda result, runs, beats, job, now: all(
        run.live
        for run in result
        if any(b.run_id == run.run_id and is_live(b, job, now) for b in beats)
    ),
    "a run a live beat names is live",
)
@ensure(
    lambda result, runs, beats, job, now: (
        len(result) == 0
        or result[0].live
        or not any(
            is_live(b, job, now) and all(b.run_id != run.run_id for run in runs) for b in beats
        )
    ),
    "the newest is live while a live beat names no run listed",
)
def marked_live(
    runs: Sequence[RunState], beats: Sequence[Beat], job: str, now: float
) -> list[RunState]:
    """The runs, newest first, with each one a live beat names marked live, and the newest too
    where a live beat names no run listed: a launcher whose flow Metaflow has named no run for
    yet, or named one only after the runs were listed, may be running the newest or resuming
    it, and the newest is the only one decide would resume. The launcher lists the runs before
    it reads the beats, and every launcher writes its beat before its flow makes a run, so a run
    it lists that is live has a beat it reads, and a live run it missed has a beat naming a run
    it did not list, or none."""
    listed = {run.run_id for run in runs}
    held = {beat.run_id for beat in beats if is_live(beat, job, now)}
    # "" is never listed, since every run has an id
    unlisted = any(run_id not in listed for run_id in held)
    return [
        run._replace(live=run.live or run.run_id in held or (at == 0 and unlisted))
        for at, run in enumerate(runs)
    ]


@beartype
@require(lambda flow: len(flow) > 0, "a flow has a name")
@require(
    lambda code: 7 <= len(code) <= 64 and _is_hex(code), "the code is named by 7 to 64 hex digits"
)
@ensure(lambda result: len(result) == RUN_KEY_LENGTH, "a key is sixteen hex digits")
@ensure(lambda result: _is_hex(result), "a key is hex")
def run_key(flow: str, code: str, words: Sequence[str], reads: Sequence[str] = ()) -> str:
    """The launch's name: a hash of the flow, the code it runs, the flow's parameters as given and
    what the flow reads that its parameters do not name.

    The code is the digest of the files the flow executes, 64 hex digits from tools/run_code.py,
    and not the commit, so a merge that changes none of those files keeps the key and a job
    queued again after it carries the cut run on (issue #252, finding 27); the precondition
    holds it to hex of a commit's length or a digest's, the shorter of which CrossHair meets
    within the gate's time.

    Canonical JSON of them, ASCII-escaped, so two launches name the same key exactly when they ran
    the same code with the same words on the same inputs, whatever characters a word holds. The
    reads are a line per input the launcher can look at before the run, such as each recipe's raw
    folder for bank and the plan for sweep, so a resume never clones a step made from an input that
    has changed since; with none, the key is the hash of the first three alone, and a list of four
    never hashes as a list of three. What the launcher chooses for a new run and resume keeps, such
    as the date bank is given where the words name none, is in neither.
    """
    parts = [flow, code, list(words)] + ([list(reads)] if reads else [])
    text = json.dumps(parts, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("ascii")).hexdigest()[:RUN_KEY_LENGTH]


@beartype
@require(lambda runs: all(len(run.run_id) > 0 for run in runs), "every run has an id")
@require(
    lambda runs: all(run.finished or not run.successful for run in runs),
    "a run that succeeded has finished",
)
@ensure(
    lambda result, runs: (
        (len(runs) > 0 and not runs[0].successful and not runs[0].live and runs[0].parameters_saved)
        or result == (RUN, None)
    ),
    "no run yet, or a newest run that succeeded, runs still or saved no parameters, starts anew",
)
@ensure(
    lambda result, runs: (
        len(runs) == 0
        or runs[0].successful
        or runs[0].live
        or not runs[0].parameters_saved
        or result == (RESUME, runs[0].run_id)
    ),
    "a newest run that did not succeed, runs no more and saved its parameters is resumed by its id",
)
def decide(runs: Sequence[RunState]) -> tuple[str, str | None]:
    """Run anew or resume, from the runs carrying the launch's key, newest first.

    The newest decides alone. A newest run that did not succeed, killed mid-step or failed, is
    work left, and resuming it reruns only what did not finish. A newest run that succeeded is
    done, so a launch after it is a new run on purpose, and an older failed run behind it is
    history, not work left: resuming it would undo nothing and redo what the success already did.
    A newest run still running, its launcher's beat fresh, is no work left either: resuming it
    would clone the steps it has done so far, a catalog built before the shards that landed
    since among them, so the launch runs anew beside it, as two jobs of a stage ran before
    Metaflow, the stage's own locks, catalog's BUILD.lock among them, ordering what may not overlap.
    Nor is a newest run whose parameters Metaflow never saved, killed after Metaflow registered it
    and before it saved them: it ran no step, and Metaflow refuses to resume it, after registering
    the resume as one more such run of the key, so resuming it failed every later launch of the
    key in turn (the second review of #252, finding 1); the launch runs anew instead.
    """
    newest = runs[0] if runs else None
    if newest and not newest.successful and not newest.live and newest.parameters_saved:
        return (RESUME, newest.run_id)
    return (RUN, None)
