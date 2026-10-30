"""The calibration of the values' spreads: fit on validation crops only and applied unchanged
afterwards, so that a reported spread is a statement about the error and the naming layer's
posterior is not flattened by a spread that is only wide (the owner's pasted diagnosis of 29 October
2026, 17:09 UTC: the smoke run's 25 mm uncalibrated spread named 0 of 12 held-out bodies).

Per measure k, with s = sqrt(sigma^2 + Z_FLOOR_MM^2) the delta-method spread floored and
z = |error| / s over the validation crops, the calibration is one factor c_k that multiplies s:

- scale: c = sqrt(mean z^2), the Gaussian likelihood's closed form, the factor that makes the mean
  squared standardised error one (temperature scaling for a regression, Guo et al., ICML 2017;
  Kendall and Gal, NeurIPS 2017, for the heteroscedastic likelihood it rescales);
- quantile: c = quantile(z, coverage) / Phi^-1((1 + coverage) / 2), split-conformal in the
  quantile and Gaussian in the scale: the calibrated spread is the standard deviation whose
  Gaussian interval at `coverage` holds `coverage` of the validation errors, so at the default
  0.68 plus or minus one calibrated spread covers 0.68 of them (Phi^-1(0.84) is 0.99), and at
  0.9 plus or minus 1.645 of them (Angelopoulos and Bates, 2021; Schobs, Swift and Lu, IEEE TMI
  2023, for landmark quantiles);
- none: c = 1, the floored spread as it is.

The factors are numbers in a session's record (session.py); evaluate (train.py) reports the raw and
the calibrated spreads and the coverage at one and two calibrated spreads on whatever set it is
given, which on a test set is the check that the calibration carried.
"""
from __future__ import annotations

from statistics import NormalDist
from typing import Dict, Sequence

import numpy as np

Z_FLOOR_MM = 0.1
KINDS = ("none", "scale", "quantile")


def floored(sigma) -> np.ndarray:
    """s = sqrt(sigma^2 + Z_FLOOR_MM^2): no spread is zero, so no z is infinite."""
    return np.sqrt(np.square(np.asarray(sigma, float)) + Z_FLOOR_MM ** 2)


def z_scores(error, sigma) -> np.ndarray:
    """|error| / s, (N, M), NaN where the error is NaN (a value the oracle did not give)."""
    return np.abs(np.asarray(error, float)) / floored(sigma)


def fit(error, sigma, kind: str = "scale", coverage: float = 0.68) -> np.ndarray:
    """The factors (M,), one per measure (the columns of error and sigma, (N, M) over the
    validation crops), by the kind's rule above."""
    if kind not in KINDS:
        raise ValueError("calibrate takes %s, not %r" % (", ".join(KINDS), kind))
    z = z_scores(error, sigma)
    if kind == "none":
        return np.ones(z.shape[1])
    if kind == "scale":
        return np.sqrt(np.nanmean(np.square(z), axis=0))
    if not 0.0 < coverage < 1.0:
        raise ValueError("coverage must be between 0 and 1, not %r" % coverage)
    return np.nanquantile(z, coverage, axis=0) / NormalDist().inv_cdf((1.0 + coverage) / 2.0)


def apply(sigma, factors) -> np.ndarray:
    """The calibrated spreads: the floored spreads times their measure's factor."""
    return floored(sigma) * np.asarray(factors, float)[None, :]


def coverage_at(error, spread, k: float = 1.0) -> float:
    """The share of the finite errors within k calibrated spreads, pooled over measures."""
    e, s = np.asarray(error, float), np.asarray(spread, float)
    ok = np.isfinite(e)
    if not ok.any():
        return float("nan")
    return float(np.mean(np.abs(e[ok]) <= k * s[ok]))


def record(kind: str, coverage: float, factors, keys: Sequence[str], rows: int) -> Dict[str, object]:
    """The calibration as plain numbers for a session's record."""
    return {"kind": kind, "coverage": float(coverage), "rows": int(rows),
            "factors": {k: float(f) for k, f in zip(keys, np.asarray(factors, float))}}
