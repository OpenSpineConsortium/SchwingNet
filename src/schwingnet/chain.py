"""The counting prior: name the vertebrae of a frame as one ordered column, not box by box.

docs/research/ct-priors-for-2d-detection.md, item 1. The record's largest error is a whole-column
shift: AP naming at 43.7 %, one level cranial (demo-plan.md section 0.3). A crop classifier names
each body alone, so nothing stops it calling every body one level too high. The segmented CTs say
what a column is: the levels come in order, a level's gap to the next stands in a known ratio to
the bodies' heights, and the column holds 12 thoracic and 5 lumbar bodies or, rarely, 13 or 6.

Here a frame's bodies, sorted along the column, are given the labels of one stretch of one column
hypothesis, chosen by a Viterbi pass that adds three log terms: each body's posterior for its
label, the spacing likelihood of each neighbouring pair under the CT prior, and the hypothesis's
prior. A body the detector missed is a step of two levels, paid for by a miss penalty and judged
by the two gaps it spans. The decoder abstains when the best labelling beats the best different
one by less than a margin, so a close call between "standard" and "L6" shows as "?" and is never
forced. The prior's numbers come from tools/chain_stats.py over the CTs on the grid; the weights
and the margin are chosen on validation frames only.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from beartype import beartype
from beethoven_qa.contracts import ensure, require

SACRUM = "sacrum"
# Floor on a posterior before its log, so one zero never vetoes a whole column.
POSTERIOR_FLOOR = 1e-6
# Spread below which a fitted spacing is not trusted, as a log-ratio.
SIGMA_FLOOR = 0.05


@beartype
@require(lambda thoracic: 11 <= thoracic <= 13, "a column has 11 to 13 thoracic bodies")
@require(lambda lumbar: 4 <= lumbar <= 6, "a column has 4 to 6 lumbar bodies")
@ensure(
    lambda result, thoracic, lumbar: len(result) == 7 + thoracic + lumbar + 1,
    "cervical, thoracic, lumbar and the sacrum",
)
@ensure(lambda result: result[0] == "C1" and result[-1] == SACRUM, "C1 first, the sacrum last")
def column(thoracic: int, lumbar: int) -> tuple[str, ...]:
    """The level names of one column hypothesis, cranial to caudal."""
    return (
        *(f"C{i}" for i in range(1, 8)),
        *(f"T{i}" for i in range(1, thoracic + 1)),
        *(f"L{i}" for i in range(1, lumbar + 1)),
        SACRUM,
    )


@beartype
@require(lambda thoracic: 11 <= thoracic <= 13, "a column has 11 to 13 thoracic bodies")
@require(lambda lumbar: 4 <= lumbar <= 6, "a column has 4 to 6 lumbar bodies")
@ensure(lambda result: result.startswith("T") and "L" in result, "a name says both counts")
def hypothesis_name(thoracic: int, lumbar: int) -> str:
    """A column's name as the prior's file writes it, "T12L5" for the standard one."""
    return f"T{thoracic}L{lumbar}"


@dataclass(frozen=True)
class Spacing:
    """The log of a neighbouring pair's gap over their mean height: its mean and spread."""

    mu: float
    sigma: float


@dataclass(frozen=True)
class ChainPrior:
    """What the CTs say: each pair's spacing, a fallback for unseen pairs, each column's odds."""

    spacing: Mapping[str, Spacing]
    fallback: Spacing
    columns: Mapping[str, float]
    miss_log: float = math.log(0.05)


@dataclass(frozen=True)
class Body:
    """One detected body: its place along the column, its height there, its level posterior."""

    position: float
    height: float
    posterior: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Decoded:
    """The labels in the bodies' order, the column chosen, and how far ahead of the next it is."""

    labels: tuple[str, ...]
    column: str
    score: float
    margin: float
    abstain: bool


@beartype
@require(lambda upper, lower: upper != lower, "a pair is two levels")
@ensure(lambda result: "|" in result, "a pair key joins two names")
def pair_key(upper: str, lower: str) -> str:
    """The prior's key for the gap from one level to the next caudal one."""
    return f"{upper}|{lower}"


@beartype
@require(lambda sigma: sigma > 0.0, "a spread is positive")
@require(lambda value, mu: math.isfinite(value) and math.isfinite(mu), "finite numbers")
def gaussian_log(value: float, mu: float, sigma: float) -> float:
    """The log-density of a normal law, the part that depends on the value and the spread."""
    z = (value - mu) / sigma
    return -0.5 * z * z - math.log(sigma)


@dataclass(frozen=True)
class _Column:
    """One column hypothesis as the Viterbi pass reads it: its names, the prior, the weight."""

    names: Sequence[str]
    prior: ChainPrior
    weight: float


def _spacing_of(column_: _Column, start: int, steps: int) -> Spacing:
    """The spacing law of the gap from names[start] across steps levels, summing the pairs'."""
    mu = 0.0
    variance = 0.0
    for k in range(start, start + steps):
        key = pair_key(column_.names[k], column_.names[k + 1])
        law = column_.prior.spacing.get(key, column_.prior.fallback)
        mu += math.exp(law.mu)
        variance += max(law.sigma, SIGMA_FLOOR) ** 2
    return Spacing(math.log(mu), max(math.sqrt(variance), SIGMA_FLOOR))


def _gap_log(column_: _Column, pair: tuple[Body, Body], start: int, steps: int) -> float:
    """How well the gap between two bodies fits the levels they are given."""
    upper, lower = pair
    height = 0.5 * (upper.height + lower.height)
    gap = lower.position - upper.position
    if height <= 0.0 or gap <= 0.0:
        return math.log(POSTERIOR_FLOOR)
    law = _spacing_of(column_, start, steps)
    return gaussian_log(math.log(gap / height), law.mu, law.sigma)


def _emission(body: Body, name: str) -> float:
    return math.log(max(body.posterior.get(name, 0.0), POSTERIOR_FLOOR))


def _arrive(
    column_: _Column, best: list[float], pair: tuple[Body, Body], j: int
) -> tuple[float, int]:
    """The best way into level j for the lower body: from one level up, or two with a miss."""
    found, came = -math.inf, -1
    for steps in (1, 2):
        k = j - steps
        if k < 0 or best[k] == -math.inf:
            continue
        miss = column_.prior.miss_log if steps == 2 else 0.0
        total = best[k] + column_.weight * _gap_log(column_, pair, k, steps) + miss
        if total > found:
            found, came = total, k
    return found, came


def _step(
    column_: _Column, best: list[float], pair: tuple[Body, Body]
) -> tuple[list[float], list[int]]:
    """One body further down: each level's best score and the level it came from."""
    row = [-math.inf] * len(column_.names)
    back = [-1] * len(column_.names)
    for j, name in enumerate(column_.names):
        score, came = _arrive(column_, best, pair, j)
        if came >= 0:
            row[j], back[j] = score + _emission(pair[1], name), came
    return row, back


def _backtrack(best: list[float], back: list[list[int]]) -> tuple[float, tuple[int, ...]]:
    end = max(range(len(best)), key=lambda j: best[j])
    if best[end] == -math.inf:
        return -math.inf, ()
    path = [end]
    for came in reversed(back):
        path.append(came[path[-1]])
    return best[end], tuple(reversed(path))


def _viterbi(
    column_: _Column, bodies: Sequence[Body], banned_start: int
) -> tuple[float, tuple[int, ...]]:
    """The best path of level indices for the bodies, the first body never at banned_start."""
    best = [
        -math.inf if j == banned_start else _emission(bodies[0], name)
        for j, name in enumerate(column_.names)
    ]
    back: list[list[int]] = []
    for i in range(1, len(bodies)):
        best, came = _step(column_, best, (bodies[i - 1], bodies[i]))
        back.append(came)
    return _backtrack(best, back)


def _hypotheses(prior: ChainPrior) -> list[tuple[str, tuple[str, ...], float]]:
    found = []
    for t in (11, 12, 13):
        for lumbar in (4, 5, 6):
            name = hypothesis_name(t, lumbar)
            odds = prior.columns.get(name, 0.0)
            if odds > 0.0:
                found.append((name, column(t, lumbar), math.log(odds)))
    return found


def _law_is_sound(law: Spacing) -> bool:
    return math.isfinite(law.mu) and math.isfinite(law.sigma) and law.sigma > 0.0


@beartype
@ensure(
    lambda result, prior: not result or _law_is_sound(prior.fallback),
    "a sound prior has a usable fallback",
)
def prior_is_sound(prior: ChainPrior) -> bool:
    """Whether every law has a finite mean and positive spread, and every odds a finite share."""
    laws = [prior.fallback, *prior.spacing.values()]
    odds = list(prior.columns.values())
    return (
        all(_law_is_sound(law) for law in laws)
        and all(math.isfinite(o) and o >= 0.0 for o in odds)
        and math.isfinite(prior.miss_log)
    )


def _body_is_sound(body: Body) -> bool:
    finite = math.isfinite(body.position) and math.isfinite(body.height)
    shares = all(math.isfinite(p) and 0.0 <= p <= 1.0 for p in body.posterior.values())
    return finite and shares


@beartype
@require(lambda bodies: len(bodies) >= 1, "a frame with no body has nothing to name")
@require(
    lambda bodies: all(_body_is_sound(b) for b in bodies), "places, heights and shares are finite"
)
@require(lambda prior: prior_is_sound(prior), "the prior's laws and odds are finite")
@require(
    lambda bodies: all(a.position < b.position for a, b in zip(bodies, bodies[1:], strict=False)),
    "bodies come sorted cranial to caudal, at distinct places",
)
@require(lambda weight: weight >= 0.0, "the spacing weight is not negative")
@require(lambda margin: margin >= 0.0, "the abstain margin is not negative")
@ensure(
    lambda result, bodies: len(result.labels) in (0, len(bodies)),
    "one label per body, or none when no column fits",
)
def decode(
    bodies: Sequence[Body], prior: ChainPrior, weight: float = 1.0, margin: float = 0.0
) -> Decoded:
    """Name a frame's bodies as one stretch of the most likely column."""
    candidates: list[tuple[float, tuple[str, ...], str]] = []
    for name, names, log_odds in _hypotheses(prior):
        column_ = _Column(names, prior, weight)
        score, path = _viterbi(column_, bodies, banned_start=-1)
        if not path:
            continue
        labels = tuple(names[j] for j in path)
        candidates.append((score + log_odds, labels, name))
        shifted, other = _viterbi(column_, bodies, banned_start=path[0])
        if other:
            candidates.append((shifted + log_odds, tuple(names[j] for j in other), name))
    if not candidates:
        return Decoded((), "", -math.inf, 0.0, True)
    candidates.sort(key=lambda c: c[0], reverse=True)
    top_score, top_labels, top_column = candidates[0]
    runner = next((c[0] for c in candidates[1:] if c[1] != top_labels), -math.inf)
    lead = top_score - runner
    return Decoded(top_labels, top_column, top_score, lead, lead < margin)


@beartype
@require(lambda bodies: len(bodies) >= 1, "a frame with no body has nothing to name")
@ensure(lambda result, bodies: len(result) == len(bodies), "one label per body")
def independent(bodies: Sequence[Body]) -> tuple[str, ...]:
    """Each body's own most likely level, the crop classifier's answer, to compare against."""
    return tuple(
        max(b.posterior, key=lambda k: b.posterior[k]) if b.posterior else "" for b in bodies
    )


@beartype
@require(lambda points: len(points) >= 1, "a column needs a body")
@ensure(lambda result, points: len(result) == len(points), "one place per body")
def axis_positions(points: Sequence[tuple[float, float]]) -> tuple[float, ...]:
    """Each centre's place along the line that best fits the centres, increasing downward.

    The first principal direction of the centres, from the closed form of a 2x2 covariance, so a
    tilted or rotated column is read along itself; its sign is chosen so that the image's y grows
    with the place, cranial to caudal on a frame shown head up.
    """
    n = len(points)
    mx = sum(p[0] for p in points) / n
    my = sum(p[1] for p in points) / n
    sxx = sum((p[0] - mx) ** 2 for p in points)
    syy = sum((p[1] - my) ** 2 for p in points)
    sxy = sum((p[0] - mx) * (p[1] - my) for p in points)
    angle = 0.5 * math.atan2(2.0 * sxy, sxx - syy)
    dx, dy = math.cos(angle), math.sin(angle)
    if dy < 0.0 or (dy == 0.0 and dx < 0.0):
        dx, dy = -dx, -dy
    if sxx == 0.0 and syy == 0.0:
        dx, dy = 0.0, 1.0
    return tuple((p[0] - mx) * dx + (p[1] - my) * dy for p in points)


@beartype
@require(lambda ratios: len(ratios) >= 2, "a spread needs two values")
@require(lambda ratios: all(r > 0.0 for r in ratios), "a ratio of lengths is positive")
@ensure(lambda result: result.sigma >= SIGMA_FLOOR, "the spread is floored")
def fit_spacing(ratios: Sequence[float]) -> Spacing:
    """The log-normal law of a pair's gap-to-height ratios measured on the CTs."""
    logs = [math.log(r) for r in ratios]
    mu = sum(logs) / len(logs)
    variance = sum((x - mu) ** 2 for x in logs) / (len(logs) - 1)
    return Spacing(mu, max(math.sqrt(variance), SIGMA_FLOOR))


@beartype
@require(lambda offset: math.isfinite(offset), "an offset is a finite number")
@require(lambda prior: prior_is_sound(prior), "the prior's laws and odds are finite")
@ensure(
    lambda result, prior: result.columns == prior.columns and result.miss_log == prior.miss_log,
    "only the spacing laws move",
)
def shifted(prior: ChainPrior, offset: float) -> ChainPrior:
    """The prior with every spacing law moved by one log-ratio, fitted on validation frames.

    The CTs measure a gap against a whole vertebra's craniocaudal extent, the frames against a
    detector's box, so the level-to-level pattern comes from the CTs and the one scale between
    the two from 2D (tools/chain_eval.py fits it on the validation part, never on test).
    """
    moved = {key: Spacing(law.mu + offset, law.sigma) for key, law in prior.spacing.items()}
    fallback = Spacing(prior.fallback.mu + offset, prior.fallback.sigma)
    return ChainPrior(moved, fallback, dict(prior.columns), prior.miss_log)
