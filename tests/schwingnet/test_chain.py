"""The counting prior: a shifted column is put back by its anchor, a close call abstains."""

import math

from schwingnet.chain import (
    SACRUM,
    Body,
    ChainPrior,
    Spacing,
    axis_positions,
    column,
    decode,
    fit_spacing,
    hypothesis_name,
    independent,
    pair_key,
)

PRIOR = ChainPrior(
    spacing={},
    fallback=Spacing(math.log(1.3), 0.08),
    columns={"T12L5": 0.9, "T12L6": 0.05, "T13L5": 0.05},
)


def peaked(name: str, weight: float, rest: dict[str, float] | None = None) -> dict[str, float]:
    posterior = {name: weight}
    posterior.update(rest or {})
    return posterior


def lumbar_bodies(posteriors: list[dict[str, float]], gap: float = 1.3) -> list[Body]:
    return [Body(position=i * gap, height=1.0, posterior=p) for i, p in enumerate(posteriors)]


def test_columns_hold_their_counts() -> None:
    assert column(12, 5)[-6:] == ("L1", "L2", "L3", "L4", "L5", SACRUM)
    assert "L6" in column(12, 6) and "T13" in column(13, 5)
    assert hypothesis_name(12, 5) == "T12L5"
    assert pair_key("L5", SACRUM) == "L5|sacrum"


def test_a_cranially_shifted_column_is_put_back_by_its_sacrum() -> None:
    truth = ["L2", "L3", "L4", "L5", SACRUM]
    shifted = ["L1", "L2", "L3", "L4"]
    posteriors = [peaked(s, 0.55, {t: 0.4}) for s, t in zip(shifted, truth, strict=False)]
    posteriors.append(peaked(SACRUM, 0.99))
    bodies = lumbar_bodies(posteriors)
    assert independent(bodies)[:4] == tuple(shifted)
    decoded = decode(bodies, PRIOR)
    assert decoded.labels == tuple(truth)
    assert decoded.column == "T12L5"
    assert not decoded.abstain


def test_a_missed_body_is_a_step_of_two() -> None:
    names = ["L1", "L2", "L4", "L5"]
    places = [0.0, 1.3, 3.9, 5.2]
    bodies = [
        Body(position=x, height=1.0, posterior=peaked(n, 0.9))
        for n, x in zip(names, places, strict=True)
    ]
    assert decode(bodies, PRIOR).labels == tuple(names)


def test_a_close_call_between_columns_abstains() -> None:
    bodies = lumbar_bodies([peaked("L5", 0.5, {"L6": 0.5}), peaked(SACRUM, 0.99)])
    even = ChainPrior(spacing={}, fallback=PRIOR.fallback, columns={"T12L5": 0.5, "T12L6": 0.5})
    decoded = decode(bodies, even, margin=math.log(4.0))
    assert decoded.abstain


def test_no_column_with_odds_names_nothing() -> None:
    empty = ChainPrior(spacing={}, fallback=PRIOR.fallback, columns={})
    decoded = decode(lumbar_bodies([peaked("L1", 0.9)]), empty)
    assert decoded.labels == () and decoded.abstain


def test_positions_run_along_a_tilted_column_downward() -> None:
    points = [(10.0 + 2.0 * i, 5.0 + 10.0 * i) for i in range(5)]
    places = axis_positions(points)
    assert all(a < b for a, b in zip(places, places[1:], strict=False))
    assert abs((places[1] - places[0]) - math.hypot(2.0, 10.0)) < 1e-9


def test_a_single_body_has_place_zero() -> None:
    assert axis_positions([(3.0, 4.0)]) == (0.0,)


def test_fitted_spacing_is_lognormal_and_floored() -> None:
    law = fit_spacing([1.3, 1.3, 1.3])
    assert abs(law.mu - math.log(1.3)) < 1e-12 and law.sigma == 0.05
    wide = fit_spacing([1.0, math.e])
    assert abs(wide.mu - 0.5) < 1e-12 and wide.sigma > 0.05


def test_a_prior_with_a_missing_number_is_not_sound() -> None:
    from schwingnet.chain import prior_is_sound

    assert prior_is_sound(PRIOR)
    assert not prior_is_sound(ChainPrior({}, Spacing(float("nan"), 0.05), {"T12L5": 1.0}))
    assert not prior_is_sound(ChainPrior({}, PRIOR.fallback, {"T12L5": float("inf")}))
    assert not prior_is_sound(ChainPrior({"L1|L2": Spacing(0.2, 0.0)}, PRIOR.fallback, {}))
