"""Which Metaflow run a launch of a pipeline flow continues, and the key that says it is the same.

The grid's jobs are killed from outside: a Slurm time limit or a preemption ends the whole job,
and the gate word that queued it queues it again. Metaflow carries a run that did not finish
on with `resume --origin-run-id`, which clones every step that finished and runs only the rest,
but only when it is told which run to carry on. flows/launch.py asks these two rules: the key
names a launch by the flow, the commit, the flow's own parameters and what it reads beyond them,
so a job queued again with the same words on the same inputs finds the run it began, and a
change of code, of configuration or of an input starts afresh; the decision then looks at the
runs carrying that key, newest first. Nothing here reads a file, starts a process or asks
Metaflow; the launcher does, and hands the runs over as RunState.
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


def _is_hex(text: str) -> bool:
    """Hex digits only, checked on the result."""
    return all(c in HEX for c in text)


class RunState(NamedTuple):
    """What Metaflow says of one earlier run of the flow: its id, and whether it ended well."""

    run_id: str
    finished: bool
    successful: bool


@beartype
@require(lambda flow: len(flow) > 0, "a flow has a name")
@require(
    lambda commit: 7 <= len(commit) <= 40 and _is_hex(commit), "a commit is 7 to 40 hex digits"
)
@ensure(lambda result: len(result) == RUN_KEY_LENGTH, "a key is sixteen hex digits")
@ensure(lambda result: _is_hex(result), "a key is hex")
def run_key(flow: str, commit: str, words: Sequence[str], reads: Sequence[str] = ()) -> str:
    """The launch's name: a hash of the flow, the commit, the flow's parameters as given and
    what the flow reads that its parameters do not name.

    Canonical JSON of them, ASCII-escaped, so two launches name the same key exactly when they
    ran the same code with the same words on the same inputs, whatever characters a word holds.
    The reads are a line per input the launcher can look at before the run, such as each
    recipe's raw folder for bank, so a resume never clones a step made from an input that has
    changed since; with none, the key is the hash of the first three alone, and a list of four
    never hashes as a list of three. What the launcher chooses for a new run and resume keeps,
    such as the date bank is given where the words name none, is in neither.
    """
    parts = [flow, commit, list(words)] + ([list(reads)] if reads else [])
    text = json.dumps(parts, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("ascii")).hexdigest()[:RUN_KEY_LENGTH]


@beartype
@require(lambda runs: all(len(run.run_id) > 0 for run in runs), "every run has an id")
@require(
    lambda runs: all(run.finished or not run.successful for run in runs),
    "a run that succeeded has finished",
)
@ensure(
    lambda result, runs: (len(runs) > 0 and not runs[0].successful) or result == (RUN, None),
    "no run yet, or a newest run that succeeded, starts a new run",
)
@ensure(
    lambda result, runs: len(runs) == 0 or runs[0].successful or result == (RESUME, runs[0].run_id),
    "a newest run that did not succeed is resumed by its id",
)
def decide(runs: Sequence[RunState]) -> tuple[str, str | None]:
    """Run anew or resume, from the runs carrying the launch's key, newest first.

    The newest decides alone. A newest run that did not succeed, killed mid-step or failed, is
    work left, and resuming it reruns only what did not finish. A newest run that succeeded is
    done, so a launch after it is a new run on purpose, and an older failed run behind it is
    history, not work left: resuming it would undo nothing and redo what the success already did.
    """
    if runs and not runs[0].successful:
        return (RESUME, runs[0].run_id)
    return (RUN, None)
