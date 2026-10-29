"""The statistics the screening reads, each a pure function over plain numbers with its contract:
percentiles by linear interpolation (numpy's default, so a number here equals one numpy gives),
the AUC with ties counted half, a bootstrap interval from picks the caller draws, and the
quadratic weighted kappa. Nothing here imports numpy, so CrossHair runs every function and a
test can hold each to a hand count.

Source: the helper thread's verse_genant.py of 29 October 2026 (the VerSe Genant join), whose
numbers these functions reproduce to the digit (screening/tests/test_truth.py).
"""
from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from typing import List, Sequence, Tuple

from .contracts import beartype, ensure, require

# the bootstrap's resamples and seed, the helper's; numpy's default_rng(SEED).integers(0, n, n)
# draws each resample's picks, at the edge in truth.py, so the picks are the helper's to the bit
BOOT, SEED = 2000, 20261029
# the agreement's grades, Genant's 0 to 3
GRADE_COUNT = 4


@beartype
@require(lambda values: len(values) >= 1 and all(math.isfinite(v) for v in values), "at least one finite value")
@require(lambda p: 0.0 <= p <= 100.0, "a percentile is between 0 and 100")
@ensure(lambda values, result: min(values) <= result <= max(values), "a percentile lies within the values")
def percentile(values: Sequence[float], p: float) -> float:
    """The p-th percentile by linear interpolation between order statistics (numpy's default)."""
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    at = (len(ordered) - 1) * p / 100.0
    low = int(at)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (at - low)


@beartype
@require(lambda values: len(values) >= 1 and all(math.isfinite(v) for v in values), "at least one finite value")
@ensure(lambda values, result: min(values) <= result <= max(values), "the median lies within the values")
def median(values: Sequence[float]) -> float:
    """The median, the mean of the two middle values for an even count (statistics.median)."""
    ordered = sorted(values)
    n = len(ordered)
    if n % 2 == 1:
        return ordered[n // 2]
    return (ordered[n // 2 - 1] + ordered[n // 2]) / 2.0


@beartype
@require(lambda values: all(math.isfinite(v) for v in values), "finite values")
def quartiles(values: Sequence[float]) -> dict:
    """n, q1, median and q3 to four decimals, or an empty record for no values."""
    if not values:
        return {}
    return {"n": len(values), "q1": round(percentile(values, 25.0), 4),
            "median": round(percentile(values, 50.0), 4), "q3": round(percentile(values, 75.0), 4)}


@beartype
@require(lambda neg, pos: len(neg) >= 1 and len(pos) >= 1, "both classes have a value")
@require(lambda neg, pos: all(math.isfinite(v) for v in neg) and all(math.isfinite(v) for v in pos), "finite values")
@ensure(lambda result: 0.0 <= result <= 1.0, "an AUC is a probability")
def auc(neg: Sequence[float], pos: Sequence[float]) -> float:
    """P(a positive's value lies below a negative's), a tie counted half: the area under the ROC
    curve of a measure whose lower values mean the condition, as a fracture lowers a height ratio."""
    ordered = sorted(pos)
    total = 0.0
    for value in neg:
        below = bisect_left(ordered, value)
        equal = bisect_right(ordered, value) - below
        total += below + 0.5 * equal
    return total / (len(neg) * len(pos))


@beartype
@require(lambda groups: len(groups) >= 1, "at least one group to resample")
@require(lambda groups, picks: all(len(pick) == len(groups) and all(0 <= i < len(groups) for i in pick) for pick in picks),
         "each resample picks as many groups as there are, by index")
@ensure(lambda result: result == (None, None) or 0.0 <= result[0] <= result[1] <= 1.0,
        "an interval of AUCs, or none where no resample had both classes")
def boot_interval(groups: Sequence[Tuple[Sequence[float], Sequence[float]]], picks: Sequence[Sequence[int]]
                  ) -> Tuple[float | None, float | None]:
    """The 2.5th and 97.5th percentiles of the AUC over resamples of the groups (one group a
    person, each its negatives and positives), the picks given, so the randomness stays outside."""
    out: List[float] = []
    for pick in picks:
        neg: List[float] = []
        pos: List[float] = []
        for i in pick:
            neg.extend(groups[i][0])
            pos.extend(groups[i][1])
        if neg and pos:
            out.append(auc(neg, pos))
    if not out:
        return None, None
    return percentile(out, 2.5), percentile(out, 97.5)


@beartype
@require(lambda a, b: len(a) == len(b) and len(a) >= 1, "two gradings of the same vertebrae")
@require(lambda a, b, k: all(0 <= x < k for x in a) and all(0 <= x < k for x in b), "grades within 0 to k - 1")
@require(lambda k: 2 <= k <= 16, "a handful of grades")
@ensure(lambda result: result[0] <= 1.0 and len(result[1]) > 0, "kappa is at most 1, and the matrix is given")
def weighted_kappa(a: Sequence[int], b: Sequence[int], k: int = GRADE_COUNT) -> Tuple[float, List[List[int]]]:
    """Cohen's kappa with quadratic weights, and the k by k matrix of a's grade (rows) against b's
    (columns). 1 where the gradings agree everywhere; 0 where they agree as chance would."""
    matrix = [[0] * k for _ in range(k)]
    for x, y in zip(a, b):
        matrix[x][y] += 1
    n = float(len(a))
    rows = [float(sum(row)) for row in matrix]
    cols = [float(sum(matrix[i][j] for i in range(k))) for j in range(k)]
    observed = expected = 0.0
    for i in range(k):
        for j in range(k):
            weight = (i - j) ** 2 / float((k - 1) ** 2)
            observed += weight * matrix[i][j]
            expected += weight * rows[i] * cols[j] / n
    if expected == 0.0:
        return 1.0, matrix
    return 1.0 - observed / expected, matrix


@beartype
@require(lambda count, total: 0 <= count <= total, "a share's count is within its total")
def share(count: int, total: int) -> float | None:
    """count over total to four decimals; None where there is nothing to count."""
    return round(count / total, 4) if total else None
