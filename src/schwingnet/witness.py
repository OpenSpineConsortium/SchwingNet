"""The witness frames: the fixed real frames every checkpoint is drawn on, chosen once and frozen.

docs/research/retraining-plan.md, section 4: evaluation is visible from the first frame, so the
same real frames are scored and drawn at every checkpoint from the untrained network onward, and
the improvement is a sequence of pictures a person reads rather than a curve they trust. There
are two sets. The validation set, frames of validation persons across the lumbar levels, is drawn
at every epoch by the trainer. The test set, frames of test persons, the three L6 cases and a few
frames of each demo sweep, is drawn over every epoch's checkpoint by the evaluator, at a version
boundary, and never chooses a checkpoint, since choosing on test persons counts as seeing them.

What is here is the choosing, pure, so the gate proves it: frames are ranked by a salted hash of
their bytes' sha256, so the choice depends on no order of reading and no clock; the lumbar levels
are taken in turn and, within a level, the person shown least so far, so the set spans levels and
persons rather than repeating the one person with the most frames; a sweep is sampled evenly
along its frames' order. Reading the catalog and drawing live in tools/witness.py.
"""

from dataclasses import dataclass
from hashlib import sha256

from beartype import beartype
from beethoven_qa.contracts import ensure, require

ROLE_VALIDATION = "validation"
ROLE_TEST = "test"
ROLE_TRANSITIONAL = "transitional"
ROLE_SWEEP = "sweep"
ROLES: tuple[str, ...] = (ROLE_VALIDATION, ROLE_TEST, ROLE_TRANSITIONAL, ROLE_SWEEP)
LUMBAR: tuple[str, ...] = ("L1", "L2", "L3", "L4", "L5")


@dataclass(frozen=True)
class Candidate:
    """A catalog frame that may be a witness: its bytes' name, its person, its part, its levels."""

    sha256: str
    person: str
    part: str
    source: str
    levels: tuple[str, ...]
    path: str


@dataclass(frozen=True)
class WitnessRule:
    """How many frames of which kind; the defaults are the plan's (section 4)."""

    source: str = "carmlspine"
    validation_count: int = 24
    test_count: int = 24
    transitional_cases: tuple[str, ...] = ("case42", "case121", "case136")
    per_transitional: int = 2
    sweep_cases: tuple[str, ...] = ("case134", "case39")
    per_sweep: int = 8
    salt: str = "schwingnet-witness-v1"


@beartype
@ensure(lambda result: len(result) == 64, "a rank is a sha256 hex digest")
def rank(salt: str, frame_sha256: str) -> str:
    """The frame's place in the choosing order: a hash of the salt and its bytes' name."""
    return sha256(f"{salt}:{frame_sha256}".encode()).hexdigest()


@beartype
@ensure(lambda result, person: result == person.rsplit(":", 1)[-1], "the case is after the colon")
def case_of(person: str) -> str:
    """The bank's case name of a person key such as carmlspine:case42."""
    return person.rsplit(":", 1)[-1]


@beartype
@require(lambda count: 0 <= count <= 1000, "a witness set is small")
@require(lambda total: 0 <= total <= 10**6, "a sweep has at most a million frames")
@ensure(lambda result, total, count: len(result) == min(total, count), "as many as asked or all")
@ensure(lambda result: list(result) == sorted(set(result)), "the indices rise, none twice")
@ensure(lambda result, total: all(0 <= i < total for i in result), "each index is a frame")
def evenly_spaced(total: int, count: int) -> tuple[int, ...]:
    """Indices of count frames spread evenly from the first to the last of total."""
    if count == 0 or total == 0:
        return ()
    if count >= total:
        return tuple(range(total))
    if count == 1:
        return (0,)
    return tuple(round(n * (total - 1) / (count - 1)) for n in range(count))


def _unique(chosen: tuple[Candidate, ...]) -> bool:
    return len({c.sha256 for c in chosen}) == len(chosen)


@beartype
@require(lambda count: 0 <= count <= 1000, "a witness set is small")
@ensure(lambda result, count: len(result) <= count, "no more than asked")
@ensure(lambda result: _unique(result), "no frame twice")
@ensure(lambda result, candidates: all(c in candidates for c in result), "only candidates")
def spread(
    candidates: tuple[Candidate, ...], levels: tuple[str, ...], count: int, salt: str
) -> tuple[Candidate, ...]:
    """Up to count frames, the levels taken in turn, each the least-shown person's best rank."""
    order = sorted(candidates, key=lambda c: rank(salt, c.sha256))
    chosen: list[Candidate] = []
    shown: dict[str, int] = {}
    while len(chosen) < count:
        added = False
        for level in levels:
            if len(chosen) >= count:
                break
            left = [c for c in order if level in c.levels and c not in chosen]
            if not left:
                continue
            best = min(left, key=lambda c: (shown.get(c.person, 0), order.index(c)))
            chosen.append(best)
            shown[best.person] = shown.get(best.person, 0) + 1
            added = True
        if not added:
            break
    return tuple(chosen)


def _of_case(candidates: tuple[Candidate, ...], case: str) -> tuple[Candidate, ...]:
    return tuple(c for c in candidates if case_of(c.person) == case)


@beartype
@ensure(lambda result: _unique(tuple(c for _, c in result[0])), "no frame in two roles")
@ensure(lambda result: all(role in ROLES for role, _ in result[0]), "every role is named")
def choose(
    candidates: tuple[Candidate, ...], rule: WitnessRule
) -> tuple[tuple[tuple[str, Candidate], ...], tuple[str, ...]]:
    """The witness frames with their roles, and a line for each kind the catalog cannot fill.

    Nothing missing is silent: a sweep with no frames in the catalog, an L6 case with none, or a
    set short of its count is named, so the page says what it does not show.
    """
    mine = tuple(c for c in candidates if c.source == rule.source)
    # A sweep is shown as a sweep alone; an L6 case may lend frames to the general test set too,
    # since the frozen test persons may be few, and its own frames are then chosen from the rest.
    validation = tuple(c for c in mine if c.part == "validation")
    test = tuple(c for c in mine if c.part == "test" and case_of(c.person) not in rule.sweep_cases)
    picked: list[tuple[str, Candidate]] = []
    missing: list[str] = []
    for role, pool, count in (
        (ROLE_VALIDATION, validation, rule.validation_count),
        (ROLE_TEST, test, rule.test_count),
    ):
        got = spread(pool, LUMBAR, count, rule.salt)
        picked.extend((role, c) for c in got)
        if len(got) < count:
            missing.append(f"{role}: {len(got)} of {count} frames with a lumbar level")
    for case in rule.transitional_cases:
        taken = {c.sha256 for _, c in picked}
        frames = tuple(
            c for c in _of_case(mine, case) if c.part == "test" and c.sha256 not in taken
        )
        showing = tuple(c for c in frames if "L6" in c.levels) or frames
        got = spread(showing, ("L6", *LUMBAR, "sacrum"), rule.per_transitional, rule.salt)
        picked.extend((ROLE_TRANSITIONAL, c) for c in got)
        if not got:
            missing.append(f"{ROLE_TRANSITIONAL}: no test frame of {case} in the catalog")
    for case in rule.sweep_cases:
        frames = tuple(
            sorted((c for c in _of_case(mine, case) if c.part == "test"), key=lambda c: c.path)
        )
        got = tuple(frames[i] for i in evenly_spaced(len(frames), rule.per_sweep))
        picked.extend((ROLE_SWEEP, c) for c in got)
        if not got:
            missing.append(f"{ROLE_SWEEP}: no test frame of {case} in the catalog")
    return tuple(picked), tuple(missing)
