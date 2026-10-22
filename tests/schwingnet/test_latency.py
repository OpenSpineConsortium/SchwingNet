"""The latency rules of docs/research/demo-plan.md, sections 1 and W6, on numbers a reader checks by hand."""

import pytest
from icontract import ViolationError

from schwingnet.latency import (
    BUDGET_MS,
    frame_interval_ms,
    nearest_rank,
    parity_holds,
    summarise,
    within_budget,
)


def test_the_p95_of_twenty_frames_is_the_nineteenth_fastest() -> None:
    values = [float(n) for n in range(1, 21)]
    assert nearest_rank(values, 0.95) == 19.0
    assert nearest_rank(values, 0.50) == 10.0
    assert nearest_rank(values, 1.0) == 20.0


def test_a_percentile_is_a_measured_frame_in_any_order() -> None:
    assert nearest_rank([30.0, 10.0, 20.0], 0.5) == 20.0


def test_the_summary_orders_its_percentiles_and_counts_every_frame() -> None:
    summary = summarise([5.0, 1.0, 3.0, 2.0, 4.0])
    assert summary["frames"] == 5
    assert summary["p50"] == 3.0
    assert summary["p95"] == summary["p99"] == summary["max"] == 5.0
    assert summary["min"] == 1.0
    assert summary["mean"] == 3.0


def test_the_budget_is_one_frame_of_the_sweep() -> None:
    # C-ArmLSpine's sweeps run at 10.3 frames per second: 97.1 ms a frame, the budget rounded down.
    assert 97.0 <= frame_interval_ms(10.3) < 97.1
    assert BUDGET_MS == 97.0


def test_real_time_means_strictly_under_the_budget() -> None:
    assert within_budget(96.9)
    assert not within_budget(97.0)


def test_parity_needs_equal_labels_and_close_probabilities() -> None:
    assert parity_holds(2e-6, True, 64)
    assert not parity_holds(2e-6, False, 64)
    assert not parity_holds(1e-5, True, 64)


def test_parity_on_no_frame_is_refused() -> None:
    with pytest.raises(ViolationError):
        parity_holds(0.0, True, 0)


def test_a_summary_of_nothing_is_refused() -> None:
    with pytest.raises(ViolationError):
        summarise([])


def test_a_negative_time_is_refused() -> None:
    with pytest.raises(ViolationError):
        summarise([1.0, -0.5])
