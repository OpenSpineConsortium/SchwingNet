"""The pre-registered rule on the record's own numbers (docs/research/retraining-plan.md, 2)."""

import pytest
from icontract import ViolationError

from schwingnet.measure import better, fraction


def test_the_reported_lateral_naming_is_its_recorded_fraction() -> None:
    # spine-program 01_carm_level_detection/STATUS.md, row A2.1: 595 / 617 (96.4 %).
    assert round(fraction(595, 617), 3) == 0.964


def test_a_lower_bound_above_the_baseline_is_better() -> None:
    assert better(0.970, 0.964)


def test_a_higher_point_estimate_with_an_overlapping_interval_is_not_better() -> None:
    # Wilson on effective n [92.3, 98.4] for A2.1: a new 97.0 % whose bound is 95.0 % is not better.
    assert not better(0.950, 0.964)


def test_equal_is_not_better() -> None:
    assert not better(0.964, 0.964)


def test_a_fraction_refuses_an_empty_measure() -> None:
    with pytest.raises(ViolationError):
        fraction(0, 0)


def test_a_fraction_refuses_more_correct_than_total() -> None:
    with pytest.raises(ViolationError):
        fraction(618, 617)
