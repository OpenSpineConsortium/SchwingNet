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

from collections.abc import Callable
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


def _distinct(candidates: tuple[Candidate, ...]) -> bool:
    return len({c.sha256 for c in candidates}) == len(candidates)


@beartype
@require(lambda count: 0 <= count <= 1000, "a witness set is small")
@require(lambda candidates: _distinct(candidates), "a frame is a candidate once, by its bytes")
@ensure(lambda result, count: len(result) <= count, "no more than asked")
@ensure(lambda result: _unique(result), "no frame twice")
@ensure(lambda result, candidates: all(c in candidates for c in result), "only candidates")
def spread(
    candidates: tuple[Candidate, ...], levels: tuple[str, ...], count: int, salt: str
) -> tuple[Candidate, ...]:
    """Up to count frames, the levels taken in turn, each the least-shown person's best rank.

    Each level's frames are listed once in rank order, so a pick costs one pass over that level's
    list, never the whole catalog searched again: a real catalog has tens of thousands of frames.
    """
    order = sorted(candidates, key=lambda c: rank(salt, c.sha256))
    by_level = {level: [c for c in order if level in c.levels] for level in levels}
    chosen: list[Candidate] = []
    taken: set[str] = set()
    shown: dict[str, int] = {}
    while len(chosen) < count:
        added = False
        for level in levels:
            if len(chosen) >= count:
                break
            best = _least_shown(by_level[level], taken, shown)
            if best is None:
                continue
            chosen.append(best)
            taken.add(best.sha256)
            shown[best.person] = shown.get(best.person, 0) + 1
            added = True
        if not added:
            break
    return tuple(chosen)


def _least_shown(
    ranked: list[Candidate], taken: set[str], shown: dict[str, int]
) -> Candidate | None:
    """The first-ranked frame not taken whose person has been shown the fewest times."""
    best, fewest = None, -1
    for candidate in ranked:
        if candidate.sha256 in taken:
            continue
        times = shown.get(candidate.person, 0)
        if best is None or times < fewest:
            best, fewest = candidate, times
            if times == 0:
                break
    return best


def _of_case(candidates: tuple[Candidate, ...], case: str) -> tuple[Candidate, ...]:
    return tuple(c for c in candidates if case_of(c.person) == case)


def _small(rule: WitnessRule) -> bool:
    counts = (rule.validation_count, rule.test_count, rule.per_transitional, rule.per_sweep)
    return all(0 <= n <= 1000 for n in counts)


@beartype
@require(lambda candidates: _distinct(candidates), "a frame is a candidate once, by its bytes")
@require(lambda rule: _small(rule), "each count of a witness set is small")
@require(
    lambda rule: not set(rule.transitional_cases) & set(rule.sweep_cases),
    "a case is an L6 case or a sweep, not both",
)
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
    picked: list[tuple[str, Candidate]] = []
    missing: list[str] = []
    for role, pool, count in _general_pools(mine, rule):
        got = spread(pool, LUMBAR, count, rule.salt)
        picked.extend((role, c) for c in got)
        missing.extend(_shortfall(role, len(got), count, ""))
    for role, case, pick in _case_steps(rule):
        got = pick(_left(mine, case, picked), rule)
        picked.extend((role, c) for c in got)
        missing.extend(_shortfall(role, len(got), 1, case))
    return tuple(picked), tuple(missing)


def _case_steps(rule: WitnessRule) -> list[tuple[str, str, Callable[..., tuple[Candidate, ...]]]]:
    """Each L6 case, then each sweep, with the rule that picks its frames."""
    steps: list[tuple[str, str, Callable[..., tuple[Candidate, ...]]]] = []
    steps += [(ROLE_TRANSITIONAL, case, _transitional) for case in rule.transitional_cases]
    steps += [(ROLE_SWEEP, case, _sweep) for case in rule.sweep_cases]
    return steps


def _left(
    mine: tuple[Candidate, ...], case: str, picked: list[tuple[str, Candidate]]
) -> tuple[Candidate, ...]:
    """A case's test frames that no role has taken yet."""
    taken = {c.sha256 for _, c in picked}
    return tuple(c for c in _of_case(mine, case) if c.part == "test" and c.sha256 not in taken)


def _shortfall(role: str, got: int, wanted: int, case: str) -> list[str]:
    """The line that says a role has too few frames, or none."""
    if case:
        return [f"{role}: no test frame of {case} in the catalog"] if not got else []
    return [f"{role}: {got} of {wanted} frames with a lumbar level"] if got < wanted else []


def _general_pools(
    mine: tuple[Candidate, ...], rule: WitnessRule
) -> tuple[tuple[str, tuple[Candidate, ...], int], ...]:
    """The validation and test pools; a sweep is shown as a sweep alone, while an L6 case may
    lend frames to the general test set, since the frozen test persons may be few."""
    validation = tuple(c for c in mine if c.part == "validation")
    test = tuple(c for c in mine if c.part == "test" and case_of(c.person) not in rule.sweep_cases)
    return (
        (ROLE_VALIDATION, validation, rule.validation_count),
        (ROLE_TEST, test, rule.test_count),
    )


def _transitional(frames: tuple[Candidate, ...], rule: WitnessRule) -> tuple[Candidate, ...]:
    """An L6 case's frames that show its L6 body, or any of its frames where none does."""
    showing = tuple(c for c in frames if "L6" in c.levels) or frames
    return spread(showing, ("L6", *LUMBAR, "sacrum"), rule.per_transitional, rule.salt)


def _sweep(frames: tuple[Candidate, ...], rule: WitnessRule) -> tuple[Candidate, ...]:
    """A sweep's frames evenly along its order, the first and the last among them."""
    ordered = tuple(sorted(frames, key=lambda c: c.path))
    return tuple(ordered[i] for i in evenly_spaced(len(ordered), rule.per_sweep))
