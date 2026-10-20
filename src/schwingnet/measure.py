"""The pre-registered comparison of a new number with the reported one.

docs/research/retraining-plan.md, section 2, states each measure as a fraction on a held-out
set with a Wilson interval, and its success criterion as the new interval's lower bound
standing above the reported point estimate. These functions are that rule, so the rule is
code the gate proves and the result rows cite, not a sentence a person applies by hand.
"""

from beartype import beartype
from beethoven_qa.contracts import ensure, require


@beartype
@require(lambda correct, total: total > 0, "a measure needs at least one case")
@require(lambda correct, total: 0 <= correct <= total, "correct cases are a part of the total")
@ensure(lambda result: 0.0 <= result <= 1.0, "a fraction lies between 0 and 1")
def fraction(correct: int, total: int) -> float:
    """The point estimate of a measure, as the record prints it (595 / 617 is 0.964)."""
    return correct / total


@beartype
@require(lambda lower_bound: 0.0 <= lower_bound <= 1.0, "a bound is a fraction")
@require(lambda baseline: 0.0 <= baseline <= 1.0, "a baseline is a fraction")
@ensure(
    lambda result, lower_bound, baseline: result == (lower_bound > baseline),
    "better means the new interval's lower bound stands above the old point estimate",
)
def better(lower_bound: float, baseline: float) -> bool:
    """Whether a new measure beats the reported one under the pre-registered rule.

    The new number's lower confidence bound must exceed the old point estimate: a new point
    estimate above the old one proves nothing when the intervals overlap.
    """
    return lower_bound > baseline
