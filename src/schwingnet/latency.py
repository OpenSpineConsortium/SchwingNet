"""What a latency number is, and when one may be written at all.

docs/research/demo-plan.md, section 1, fixes the claim a slide may make: per-frame compute on a
named device, models resident, batch one frame at a time, excluding acquisition, decode and
display, as p50 and p95; "real-time" only where the p95 is under the sweep's own frame interval,
97 ms at C-ArmLSpine's 10.3 frames per second. Section W6 adds the order: no latency number for a
runtime whose outputs differ from PyTorch's on the same frames. These functions are those two
rules, so the rule is code the gate proves and every latency file cites, never a sentence applied
by hand.
"""

import math

from beartype import beartype
from beethoven_qa.contracts import ensure, require

# One frame interval of the recorded sweeps: 1000 ms / 10.3 frames per second, rounded down, so a
# p95 under it keeps up with the C-arm (docs/research/demo-plan.md, section 1).
BUDGET_MS = 97.0
# The parity tolerance on softmax probabilities, the plan's W6: "posterior difference below 1e-5".
PARITY_TOLERANCE = 1e-5


@beartype
@require(lambda values: len(values) > 0, "a percentile needs at least one value")
@require(lambda values: all(math.isfinite(v) for v in values), "every value is a finite number")
@require(lambda share: 0.0 < share <= 1.0, "the share is a fraction above zero")
@ensure(lambda result, values: result in values, "the nearest rank is one of the values")
@ensure(lambda result, values: min(values) <= result <= max(values), "within the values' range")
def nearest_rank(values: list[float], share: float) -> float:
    """The nearest-rank percentile: the smallest value with at least that share at or below it.

    Nearest rank, not interpolation, so every percentile a slide shows is a frame that was
    measured, and the p95 of 300 frames is the 285th fastest.
    """
    ordered = sorted(values)
    rank = max(1, math.ceil(share * len(ordered)))
    return ordered[rank - 1]


@beartype
@require(lambda samples_ms: len(samples_ms) > 0, "a summary needs at least one frame")
@require(
    lambda samples_ms: all(math.isfinite(v) and v >= 0.0 for v in samples_ms),
    "times are finite and not negative",
)
@ensure(
    lambda result: result["p50"] <= result["p95"] <= result["p99"] <= result["max"],
    "percentiles are ordered",
)
@ensure(lambda result, samples_ms: result["frames"] == len(samples_ms), "every frame is counted")
def summarise(samples_ms: list[float]) -> dict[str, float | int]:
    """p50, p95, p99, the mean, the fastest and the slowest frame, and how many frames."""
    return {
        "frames": len(samples_ms),
        "p50": nearest_rank(samples_ms, 0.50),
        "p95": nearest_rank(samples_ms, 0.95),
        "p99": nearest_rank(samples_ms, 0.99),
        "mean": sum(samples_ms) / len(samples_ms),
        "min": min(samples_ms),
        "max": max(samples_ms),
    }


@beartype
@require(
    lambda p95_ms: math.isfinite(p95_ms) and p95_ms >= 0.0, "a time is finite and not negative"
)
@require(lambda budget_ms: budget_ms > 0.0, "a budget is above zero")
@ensure(
    lambda result, p95_ms, budget_ms: result == (p95_ms < budget_ms), "strictly under the budget"
)
def within_budget(p95_ms: float, budget_ms: float = BUDGET_MS) -> bool:
    """Whether a runtime keeps up with the sweep: its p95 strictly under one frame interval."""
    return p95_ms < budget_ms


@beartype
@require(
    lambda max_abs_difference: math.isfinite(max_abs_difference) and max_abs_difference >= 0.0,
    "a difference is finite and not negative",
)
@require(lambda frames: frames > 0, "parity is shown on at least one frame")
@require(lambda tolerance: tolerance > 0.0, "a tolerance is above zero")
@ensure(
    lambda result, max_abs_difference, labels_equal, tolerance: (
        result == (labels_equal and max_abs_difference < tolerance)
    ),
    "same labels and probabilities within the tolerance",
)
def parity_holds(
    max_abs_difference: float, labels_equal: bool, frames: int, tolerance: float = PARITY_TOLERANCE
) -> bool:
    """Whether a runtime gives PyTorch's outputs: equal labels, probabilities within tolerance.

    `frames` is how many crops the comparison read; it is a precondition, not a factor, since
    parity on nothing would hold vacuously and say nothing.
    """
    return labels_equal and max_abs_difference < tolerance


@beartype
@require(lambda fps: fps > 0.0, "a rate is above zero")
@ensure(lambda result: result > 0.0, "an interval is above zero")
def frame_interval_ms(fps: float) -> float:
    """The time between two frames at a rate, in milliseconds."""
    return 1000.0 / fps
