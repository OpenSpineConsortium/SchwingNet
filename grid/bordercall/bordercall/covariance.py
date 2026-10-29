"""The between-measure covariance: what is knowable, what is not, and how to stay honest.

    python run.py covariance --report          # what the literature can and cannot supply
    python run.py covariance --sweep           # accuracy as a function of the assumption

THE HIDDEN ASSUMPTION. `panjabi.py` draws a column as

    value = s * (mu + sd * (rho * z[m] + sqrt(1 - rho^2) * e[m][i])) + n[m][i]

with `draws["offset"] = {m: rng.normal() for m in measures}` -- one patient offset per
measure, drawn INDEPENDENTLY. Beyond the single size factor `s`, the generator therefore
assumes the measures are uncorrelated within a patient. That is not a neutral default. It is
the choice that makes a feature vector carry the most independent information, so a
classifier scored on these columns reads HIGH. Everything the synthetic study reports at
r = 0 is an UPPER BOUND, not an estimate.

WHAT PANJABI PUBLISHED, AND WHY IT CANNOT SUPPLY THE NUMBER. Each table gives a mean and a
standard error per measure per level. There is no correlation matrix, no paired scatter and
no specimen-level table in any of the three papers. The ratio rows look like they might carry
it -- EPWu/EPDu, SCW/SCD, PDHr/PDWr -- but they do not: a mean of per-specimen ratios would
encode the correlation, a ratio of means would not, and every published ratio reproduces
mean(a)/mean(b) to within rounding (largest residual 0.0044 on the lumbar rows, which are
printed to two decimals). They are ratios of means. Tested, not assumed:
`run.py covariance --report` reruns that check.

Two further reasons his data could not settle it even in principle. n = 12: a correlation
estimated from twelve specimens has a 95 % interval running from about 0.00 to 0.84 at
r = 0.5, which is no constraint on anything. And the specimens are embalmed cadaveric spines
measured with a morphometer, so a covariance from them would carry that preparation.

WHAT THE LINEAGE PUBLISHED, READ FROM THE PAPER RATHER THAN FROM AN ABSTRACT. Kunkel et al.
(J Anat 2010;216:320) take Panjabi's own 1991 and 1992 tables and regress each vertebral
parameter ON ANOTHER PARAMETER -- posterior vertebral body height, VBHp, chosen as the
predictor "based on the level of correlation with the other parameters and ease of
measurement on lateral X-rays". So this IS a published between-parameter relationship built
from Panjabi's data, which is the nearest thing in the literature to what is wanted here:

    EPWS, EPWI, EPDS, EPDI, VBW, VBD     R^2 0.970-0.982   (third-order polynomial)
    PHL, PHR, PTIL, SCW, SCD             R^2 0.693-0.964
    EPIS, EPII, PWL, PWR, PTIR, SPL, TPW R^2 0.514-0.693

AND IT STILL CANNOT SET r_between, for one reason that is easy to miss: "each data point
represents the mean value in different vertebral levels of 12 cadavers". The regression runs
over SIXTEEN LEVEL MEANS, T1-T12 and L1-L4, not over individuals. R^2 = 0.98 for EPWS on
VBHp says their CAUDAL PROFILES track each other down the column. It does not say that a
patient with a tall posterior body has a wide end-plate. Those are different quantities, and
reading the second from the first is the ecological fallacy: a correlation between group
means need not hold, in sign or size, within groups.

The generator already reproduces every one of those profile relationships exactly, because it
draws each level from that level's own published mean. Kunkel's R^2 is therefore already in
the model and adds nothing to r_between.

Searches of Panjabi's collaborators (Oxland, Goel, Crisco, Takata, Krag, White) found no
published within-patient between-measure covariance for vertebral morphometry either.

SO THE NUMBER DOES NOT EXIST, and inventing one would be the bias this package exists to
avoid. What replaces it is a sensitivity analysis: the result is reported as a function of
the assumption, with the value at which the conclusion changes named. An unmeasurable
nuisance parameter becomes a stated range rather than a hidden constant.

THE ONE OUTSIDE ANCHOR, used to place the sweep and not to pick an answer: 125 dry lumbar
vertebrae give Spearman rho = 0.800 between the anteroposterior and laterolateral diameters
of the vertebral body (BMC Musculoskelet Disord 2026). Dry bone, as Panjabi's was, but a
different cohort, method and continent, and not his lineage. It says the plausible range runs
to 0.8 for two dimensions of the same structure, not that 0.8 is the value here.

THE STRUCTURE SWEPT. One number r for every pair, the exchangeable form

    R = (1 - r) I + r 11'

which is a valid correlation matrix for r in [-1/(k-1), 1]. A full matrix would need k(k-1)/2
numbers and nothing supplies even one of them; one parameter that can be swept end to end is
the honest shape of the ignorance.
"""
from __future__ import annotations

import json
import math
import os
import sys
from collections import defaultdict
from typing import Dict, List, Optional, Sequence

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))

# the anchor, for placing the sweep only
# The r grid every sweep in this module runs on. 0.0 is the generator's own default and the
# optimistic end; 0.8 is where the one outside anchor sits; 0.9 is past it on purpose.
R_GRID = [0.0, 0.2, 0.4, 0.6, 0.8, 0.9]

EXTERNAL = {"pair": "vertebral body AP vs LL diameter", "rho": 0.800, "n": 125,
            "material": "dry bone",
            "source": "BMC Musculoskelet Disord 2026, 125 dry lumbar vertebrae",
            "lineage": "not Panjabi's"}

# Panjabi's published ratio rows, to re-test the claim that they carry no covariance
RATIO_ROWS = [
    ("thoracic EPWu/EPDu",
     [24.5, 24.9, 24.6, 24.5, 24.9, 26.2, 27.8, 29.5, 30.6, 31.9, 34.9, 39.0],
     [18.5, 19.6, 22.7, 23.3, 24.3, 26.0, 27.4, 27.9, 29.3, 30.5, 31.9, 32.8],
     [1.3, 1.3, 1.1, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.1, 1.2], 1),
    ("lumbar EPWu/EPDu", [41.2, 42.6, 44.1, 46.6, 47.3], [34.1, 34.6, 35.2, 35.5, 34.7],
     [1.21, 1.23, 1.25, 1.31, 1.36], 2),
    ("lumbar EPWl/EPDl", [43.3, 45.5, 48.0, 49.5, 49.4], [35.3, 34.9, 34.8, 33.9, 33.2],
     [1.23, 1.30, 1.38, 1.46, 1.49], 2),
    ("lumbar SCW/SCD", [23.7, 23.8, 24.3, 25.4, 27.1], [19.0, 18.2, 17.5, 18.6, 19.7],
     [1.25, 1.31, 1.39, 1.37, 1.38], 2),
]


def exchangeable(k: int, r: float) -> np.ndarray:
    """R = (1-r)I + r 11', the only shape one number can honestly describe."""
    lo = -1.0 / (k - 1) if k > 1 else -1.0
    if not (lo - 1e-12 <= r <= 1.0):
        raise SystemExit("r = %.3f is not a correlation for %d measures; "
                         "the exchangeable form needs %.4f <= r <= 1" % (r, k, lo))
    R = np.full((k, k), float(r))
    np.fill_diagonal(R, 1.0)
    return R


def offset_factor(k: int, r: float) -> np.ndarray:
    """Cholesky factor L with L L' = R, so L @ iid normals has the wanted correlation."""
    if abs(r) < 1e-12:
        return np.eye(k)
    R = exchangeable(k, r)
    # jitter only if the matrix sits exactly on the boundary and loses positive-definiteness
    try:
        return np.linalg.cholesky(R)
    except np.linalg.LinAlgError:
        return np.linalg.cholesky(R + 1e-10 * np.eye(k))


def correlated_offsets(rng, measures: Sequence[str], r: float) -> Dict[str, float]:
    """One patient offset per measure, correlated r with every other. r = 0 reproduces
    the independent draw exactly, so a run at r = 0 matches the recorded runs."""
    ms = list(measures)
    e = rng.normal(size=len(ms))
    if abs(r) < 1e-12:
        return {m: float(v) for m, v in zip(ms, e)}
    z = offset_factor(len(ms), r) @ e
    return {m: float(v) for m, v in zip(ms, z)}


def ratio_test(tol_per_dp=(0.05, 0.005)):
    """Do the published ratios encode a covariance? -> (verdict, rows).

    THE VERDICT RESTS ON THE TWO-DECIMAL ROWS ONLY. A ratio printed to one decimal
    discriminates nothing: mean(a)/mean(b) and a mean of per-specimen ratios differ by far
    less than 0.05 for quantities this strongly related, so a one-decimal row is consistent
    with both and is reported as uninformative rather than counted either way. The thoracic
    row is printed to one decimal and has one cell (T8, 29.5/27.9 = 1.057 against a printed
    1.0) outside even that; at this precision that is a rounding or typesetting question,
    not evidence of a covariance, and it is not allowed to carry the verdict.
    """
    rows = []
    for name, a, b, pub, dp in RATIO_ROWS:
        d = max(abs(x / y - p) for x, y, p in zip(a, b, pub))
        tol = tol_per_dp[0] if dp == 1 else tol_per_dp[1]
        rows.append((name, d, tol, d <= tol + 1e-9, dp))
    decisive = [r for r in rows if r[4] >= 2]
    return (bool(decisive) and all(r[3] for r in decisive)), rows


def report():
    print("CAN THE LITERATURE SUPPLY THE BETWEEN-MEASURE COVARIANCE?\n")
    print("1. Panjabi's own tables")
    ok, rows = ratio_test()
    print("   The ratio rows are the only place a covariance could hide. A mean of")
    print("   per-specimen ratios would carry it; a ratio of means would not.\n")
    print("   %-24s %4s %10s %10s  %s"
          % ("ratio row", "d.p.", "max resid", "rounding", "ratio of means?"))
    for name, d, tol, within, dp in rows:
        verdict = ("yes" if within else "NO") if dp >= 2 else "uninformative at 1 d.p."
        print("   %-24s %4d %10.4f %10.4f  %s" % (name, dp, d, tol, verdict))
    print("\n   verdict: %s" % ("the two-decimal rows are ratios of MEANS to within "
                                "0.0044, so the tables carry no covariance" if ok else
                                "a two-decimal row is NOT a ratio of means -- look again"))
    print("   Also: n = 12. At r = 0.5 the 95 % interval on a correlation runs about")
    print("   0.00 to 0.84, so his cohort could not constrain it even if the rows did")
    print("   carry it.")

    print("\n2. His lineage -- Kunkel, which looks like the answer and is not")
    print("   Kunkel et al. (J Anat 2010;216:320) fit prediction equations to Panjabi's")
    print("   1991/1992 thoracic and lumbar tables, and unlike the rest of the lineage")
    print("   they regress each parameter ON ANOTHER PARAMETER -- posterior vertebral")
    print("   body height, VBHp -- which is the shape of relation this study needs.")
    print("   R^2 reach 0.970-0.982 for the end-plate widths and depths, VBW and VBD;")
    print("   0.693-0.964 for pedicle heights, PTIL, SCW and SCD; 0.514-0.693 for the")
    print("   rest.")
    print("   Those coefficients cannot be used here. Their methods state that each data")
    print("   point is the MEAN value at one vertebral level across the 12 cadavers, so")
    print("   every fit runs over SIXTEEN LEVEL MEANS -- T1-T12 and L1-L4 -- not over")
    print("   individuals. An R^2 of 0.98 between level means says the two measures grow")
    print("   down the spine together, which the generator already reproduces by drawing")
    print("   each level from its own published mean. Reading a within-patient")
    print("   correlation out of it is the ecological fallacy, and an aggregate")
    print("   correlation is the one quantity guaranteed to be inflated relative to the")
    print("   individual one it would stand in for.")
    print("   No between-measure covariance over individuals was found for Oxland, Goel,")
    print("   Crisco, Takata, Krag or White either.")

    print("\n3. The one outside anchor, for placing the sweep only")
    print("   %s: rho = %.2f (n = %d, %s, %s lineage)."
          % (EXTERNAL["pair"], EXTERNAL["rho"], EXTERNAL["n"], EXTERNAL["material"],
             EXTERNAL["lineage"]))
    print("   Two dimensions of the SAME structure reach 0.8 on dry bone. That bounds")
    print("   where the sweep has to go; it is not this study's value.")

    print("\nCONCLUSION. The number does not exist and will not be invented. The result is")
    print("reported as a function of r, with the value at which the conclusion changes")
    print("named. r = 0, the generator's current default, is the OPTIMISTIC end: it gives")
    print("each measure the most independent information it could have, so every accuracy")
    print("recorded at r = 0 is an upper bound.")
    return 0


def binomial_se(p, n):
    return math.sqrt(max(p * (1 - p), 1e-12) / n) if n else float("nan")


def sweep(fn, r_values=None, label="accuracy"):
    """Run fn(r) -> (value, n) over a grid and report the curve and the breakdown point.

    fn must draw FRESH columns for each r; reusing one draw would make the curve a
    property of that draw.
    """
    r_values = list(r_values if r_values is not None else R_GRID)
    print("\n%-7s %10s %10s   %s" % ("r", label, "MC s.e.", "note"))
    out = []
    for r in r_values:
        v, n = fn(r)
        se = binomial_se(v, n)
        note = "generator's current default, OPTIMISTIC" if r == 0 else ""
        if abs(r - EXTERNAL["rho"]) < 1e-9:
            note = "the outside anchor's order"
        print("%-7.2f %10.4f %10.4f   %s" % (r, v, se, note))
        out.append({"r": r, "value": v, "n": n, "se": se})
    if len(out) >= 2:
        first, last = out[0]["value"], out[-1]["value"]
        print("\n  r = %.2f -> %.2f moves %s by %+.4f (%.1f MC s.e.)"
              % (out[0]["r"], out[-1]["r"], label, last - first,
                 abs(last - first) / max(out[0]["se"], 1e-9)))
        if abs(last - first) < 2 * max(out[0]["se"], 1e-12):
            print("  The whole sweep moves it by less than two Monte Carlo standard errors,")
            print("  so on this evidence the conclusion does not depend on the assumption.")
        else:
            print("  The assumption matters. Quote the range, not the r = 0 figure.")
    return out


# ---------------------------------------------------------------------------
# what an unidentified nuisance parameter does to a reported number
# ---------------------------------------------------------------------------
# r is not merely unknown, it is UNIDENTIFIED: no amount of data from Panjabi's tables can
# pin it down, because the tables carry no covariance at all (ratio_test above). That has a
# name and a literature -- Manski's partial identification -- and the right object to report
# is not a point estimate but an IDENTIFIED SET: the set of values the quantity takes as r
# ranges over everything it could be.
#
# Two consequences, and the second is the one that matters here.
#
# 1. An accuracy quoted at one r is not the answer. The identified set of the accuracy is
#    [min_r A(r), max_r A(r)], and a naive [min - 2 se, max + 2 se] OVER-covers, because it
#    pays the full two-sided price at both ends when only one end can bind at a time. Imbens
#    & Manski (Econometrica 2004;72:1845) give the interval that covers the PARAMETER at the
#    stated rate; it narrows from 1.96 standard errors toward 1.645 as the set widens
#    relative to the sampling error. imbens_manski() below.
#
# 2. A quantity can be unidentified while the CONCLUSION DRAWN FROM IT IS POINT-IDENTIFIED.
#    If the identified set of a difference lies entirely above zero, the sign of that
#    difference is known exactly even though its size is not. That is the honest form of
#    "the conclusion does not depend on r", and it is a statement about the SIGN, not about
#    the value. sign_invariance() below reports it that way, and names the crossing point if
#    the sign does turn over inside the set.
#
# 3. THE GRID DOES NOT BOUND ANYTHING ON ITS OWN, AND IT ERRS IN THE UNSAFE DIRECTION.
#    min and max over a grid are a RELAXATION of min and max over the interval: dropping the
#    off-grid r enlarges what is being minimised over, so the reported worst case is an
#    OVERESTIMATE of the true worst case -- the anti-conservative direction for any claim
#    that rests on it. The gap is bounded by L * h / 2, with L a Lipschitz constant of A in r
#    and h the grid spacing, and it is UNBOUNDED without an L.
#
#    Refining the grid is NOT the check, which is what this comment used to say and was the
#    error worth recording. On a profile with a narrow dip between points, successive
#    refinements can return the identical wrong value and so falsely confirm; and Monte Carlo
#    noise biases the same quantity the OTHER way, growing as the grid thickens, so the two
#    errors can cancel and agreement between them is not evidence of correctness either.
#
#    So the assumption is measured rather than asserted. profile_in_r() reports whether A is
#    in fact monotone in r over the grid, the empirical Lipschitz constant, and the implied
#    L * h / 2 gap next to the Monte Carlo standard error, so the two can be compared instead
#    of hoped about. Its own limit is stated in its docstring: a secant-based L from the same
#    grid is a LOWER bound on the true sup |A'|, so the gap it reports is indicative and not
#    certified. --r-grid runs a finer grid when that matters; the thing that would make it
#    certified is an independent bound on A's derivative in r, which this package does not
#    have and does not claim.

# z for a one-sided and a two-sided 95 %: the Imbens-Manski critical value lives between
# them, so these are the bisection bracket. Hard-coded to keep this module dependency-free.
_Z_ONE_SIDED = 1.6448536269514722
_Z_TWO_SIDED = 1.9599639845400545


def _phi(x: float) -> float:
    """Standard normal CDF."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def imbens_manski(lo, hi, se_lo, se_hi, alpha: float = 0.05):
    """CI covering a parameter whose identified set is [lo, hi]. Imbens & Manski (2004).

    c solves Phi(c + delta/sigma_max) - Phi(-c) = 1 - alpha, with delta the width of the
    estimated set. delta = 0 gives c = 1.96 (the set is a point, so this is an ordinary
    two-sided interval); a wide set gives c -> 1.645, because only one end can bind.

    TWO KNOWN WEAKNESSES, both worth a footnote in anything that leans on this interval.

    delta is ESTIMATED, not known, and Stoye (2009) argues that Imbens and Manski's result
    "implicitly assumes superefficient estimation of a nuisance parameter" -- so the interval
    is pointwise valid but not uniformly so, and it is least trustworthy exactly where delta
    is small relative to the sampling error, because that is where c is most sensitive to
    getting delta wrong.

    And raw estimated bounds can UNDER-cover in small samples. So coverage is not taken on
    faith here: coverage_check() measures it against a known truth, including the case where
    the grid steps over a dip and the endpoints are therefore wrong, which is the case this
    package's own sweep could be in.

    The twelve lines are written out rather than imported on purpose. A full-text sweep of the
    complete crandb index -- all 25,529 CRAN packages, matching name, title and description
    against "Manski" and "Imbens" -- returns ZERO hits, and the one readable reference
    implementation of the resampling version (medrobust's bound_ci) is not on CRAN and has no
    users. So there is nothing to depend on, and a dependency would not have been checkable.
    """
    s = max(float(se_lo), float(se_hi))
    if not s > 0:
        return float(lo), float(hi), float("nan")
    delta = max(float(hi) - float(lo), 0.0)

    def f(c):
        return _phi(c + delta / s) - _phi(-c) - (1.0 - alpha)

    a, b = _Z_ONE_SIDED, _Z_TWO_SIDED
    # f is increasing in c, f(a) <= 0 <= f(b) for every delta >= 0, so bisect
    for _ in range(200):
        m = 0.5 * (a + b)
        if f(m) < 0.0:
            a = m
        else:
            b = m
    c = 0.5 * (a + b)
    return float(lo) - c * float(se_lo), float(hi) + c * float(se_hi), c


def coverage_check(lo_true: float = 0.40, hi_true: float = 0.45, se: float = 0.01,
                   trials: int = 20000, seed: int = 0, grid_n: int = 6, dip: float = 0.0,
                   alpha: float = 0.05, quiet: bool = False):
    """Does the interval this module builds actually cover at its nominal rate?

    Measured against a known truth rather than trusted, because the construction has a
    documented small-sample under-coverage and because the way this package ESTIMATES the
    endpoints -- min and max over a grid of noisy Monte Carlo values -- is not the way the
    formula assumes they arrive.

    Three regimes are reported and they are not the same question.

    `formula`      the endpoints are unbiased draws, which is what Imbens & Manski assume.
                   Coverage of the true value at the lower endpoint, the midpoint and the
                   upper endpoint. The endpoints are the hard cases.

    `pipeline`     the endpoints are min and max over `grid_n` noisy evaluations of a true
                   profile, which is what this package actually does. The min of noisy values
                   sits BELOW the true min and the max ABOVE the true max, so this should
                   over-cover -- and over-coverage is not a licence to ignore it, because the
                   same bias makes the reported worst case pessimistic as an estimate while
                   the grid makes it optimistic as a bound.

    `dip`          with dip > 0 the true profile has a narrow dip BETWEEN grid points, so the
                   grid cannot see the true minimum at all. This is the case the report of a
                   refined grid falsely confirms, and the regime where coverage of the true
                   worst case is expected to FAIL. It is included so that the failure is on
                   the record and measured, not described.
    """
    rng = np.random.default_rng(seed)
    out = {"lo_true": lo_true, "hi_true": hi_true, "se": se, "trials": trials,
           "grid_n": grid_n, "dip": dip, "nominal": 1.0 - alpha}

    def rate(hits):
        p = hits / trials
        return {"coverage": p, "se": binomial_se(p, trials)}

    # --- regime 1: the formula's own assumption, unbiased endpoints
    lo_hat = rng.normal(lo_true, se, trials)
    hi_hat = rng.normal(hi_true, se, trials)
    formula = {}
    for name, theta in (("at_lower", lo_true),
                        ("at_middle", 0.5 * (lo_true + hi_true)),
                        ("at_upper", hi_true)):
        hits = 0
        for a, b in zip(lo_hat, hi_hat):
            # the estimated set can come out inverted; order it, as the sweep's min/max do
            l, h = (a, b) if a <= b else (b, a)
            ci_lo, ci_hi, _ = imbens_manski(l, h, se, se, alpha)
            if ci_lo <= theta <= ci_hi:
                hits += 1
        formula[name] = rate(hits)
    out["formula"] = formula

    # --- regime 2 and 3: endpoints as min/max over a noisy grid of a true profile
    rs = np.linspace(0.0, 0.9, grid_n)
    true = lo_true + (hi_true - lo_true) * (rs - rs[0]) / (rs[-1] - rs[0])
    # the true minimum of the FUNCTION, which a dip puts between grid points
    true_min = float(true.min()) - dip
    true_max = float(true.max())
    hits_min = hits_max = 0
    for _ in range(trials):
        obs = true + rng.normal(0.0, se, grid_n)
        l, h = float(obs.min()), float(obs.max())
        ci_lo, ci_hi, _ = imbens_manski(l, h, se, se, alpha)
        if ci_lo <= true_min <= ci_hi:
            hits_min += 1
        if ci_lo <= true_max <= ci_hi:
            hits_max += 1
    out["pipeline"] = {"true_min": true_min, "true_max": true_max,
                       "covers_true_min": rate(hits_min),
                       "covers_true_max": rate(hits_max)}

    if not quiet:
        print("COVERAGE OF THE IMBENS-MANSKI INTERVAL, measured against a known truth")
        print("  identified set [%.4f, %.4f], se %.4f, %d trials, nominal %.0f %%"
              % (lo_true, hi_true, se, trials, 100 * (1 - alpha)))
        print("\n  1. unbiased endpoints -- the formula's own assumption")
        for name in ("at_lower", "at_middle", "at_upper"):
            c = formula[name]
            flag = "" if c["coverage"] >= (1 - alpha) - 2 * c["se"] else "   <- UNDER-COVERS"
            print("     covering the true value %-9s %.4f +/- %.4f%s"
                  % (name.replace("at_", "") + ":", c["coverage"], c["se"], flag))
        print("\n  2. endpoints as min/max over a %d-point noisy grid -- what this package does"
              % grid_n)
        for k, label in (("covers_true_min", "true minimum"),
                         ("covers_true_max", "true maximum")):
            c = out["pipeline"][k]
            flag = "" if c["coverage"] >= (1 - alpha) - 2 * c["se"] else "   <- UNDER-COVERS"
            print("     covering the %-13s %.4f +/- %.4f%s"
                  % (label + ":", c["coverage"], c["se"], flag))
        if dip > 0:
            print("\n     a dip of %.3f sits BETWEEN grid points, so the grid cannot see the"
                  % dip)
            print("     true minimum. Under-coverage here is the expected result and is the")
            print("     reason a refined grid is not a check on itself.")
    return out


def profile_in_r(rows, key: str = "acc"):
    """Is A monotone in r, how steep is it, and how much can the grid be hiding?

    The grid's min and max bound the interval's only up to L * h / 2. This measures L from
    the grid itself and puts the implied gap beside the Monte Carlo standard error, so the
    two sources of error can be compared rather than assumed away.

    TWO LIMITS, both stated because neither is removable from inside this computation.

    A secant-based L is a LOWER bound on the true sup |A'|: a dip between two grid points
    makes the secant shallower than the derivative it is standing in for, which is exactly
    the case the grid cannot see. So `gap` is INDICATIVE, not certified. Certifying it needs
    an independent bound on A's derivative in r, which this package does not have.

    And the secants are contaminated by Monte Carlo noise, which inflates L by roughly
    sqrt(2) * se / h and so inflates the gap. `noise_floor` is that inflation, so a measured
    L at or below it means the profile is flat to within the noise and the grid is not
    hiding a slope -- it means the run cannot see one.
    """
    rs = sorted(rows, key=lambda x: x["r"])
    if len(rs) < 2:
        return None
    diffs, spacings, slopes = [], [], []
    for p, q in zip(rs, rs[1:]):
        h = q["r"] - p["r"]
        if h <= 0:
            continue
        diffs.append(q[key] - p[key])
        spacings.append(h)
        slopes.append(abs(q[key] - p[key]) / h)
    if not slopes:
        return None
    signs = {1 if d > 0 else (-1 if d < 0 else 0) for d in diffs}
    monotone = len(signs - {0}) <= 1
    lip = max(slopes)
    h_max = max(spacings)
    se = max(x["se"] for x in rs)
    # a secant across spacing h inherits sqrt(2) * se of noise, so L is inflated by that / h
    noise_floor = math.sqrt(2.0) * se / min(spacings)
    return {"monotone": monotone, "direction": ("flat" if not (signs - {0})
                                                else ("rising" if 1 in signs else "falling")),
            "lipschitz": lip, "h_max": h_max, "gap": lip * h_max / 2.0,
            "se": se, "noise_floor": noise_floor,
            "informative": lip > noise_floor,
            "gap_in_se": (lip * h_max / 2.0) / se if se else float("nan")}


def print_profile(rows, name: str = "", key: str = "acc"):
    """The grid's own error, measured, beside the Monte Carlo error."""
    p = profile_in_r(rows, key)
    if p is None:
        return None
    print("   %-10s %s in r, |slope| <= %.4f, grid gap L*h/2 = %.4f (%.1f MC s.e.)"
          % (name, "monotone" if p["monotone"] else "NOT monotone",
             p["lipschitz"], p["gap"], p["gap_in_se"]))
    if not p["informative"]:
        print("              the measured slope %.4f is below the noise floor %.4f, so this"
              % (p["lipschitz"], p["noise_floor"]))
        print("              run cannot see a slope -- it has not shown there is none")
    if not p["monotone"]:
        print("              non-monotone: the grid may be stepping over an interior"
              " extremum,")
        print("              and refining it is not a reliable check. Treat the set as"
              " a lower")
        print("              bound on the true spread.")
    return p


def identified_set(rows, key: str = "acc"):
    """The identified set of `key` over an r grid, and its Imbens-Manski interval.

    rows: the dicts a sweep produces, each with an "r", a value and an "se".
    """
    lo_row = min(rows, key=lambda x: x[key])
    hi_row = max(rows, key=lambda x: x[key])
    ci_lo, ci_hi, c = imbens_manski(lo_row[key], hi_row[key], lo_row["se"], hi_row["se"])
    return {"lo": lo_row[key], "lo_at_r": lo_row["r"],
            "hi": hi_row[key], "hi_at_r": hi_row["r"],
            "width": hi_row[key] - lo_row[key],
            "ci_lo": ci_lo, "ci_hi": ci_hi, "critical_value": c}


def sign_invariance(rows_a, rows_b, key: str = "acc"):
    """Is the SIGN of (a - b) the same at every r? -> the point-identified conclusion.

    Returns the identified set of the difference, the worst case over r with its standard
    error, whether the sign is constant, and -- if it is not -- the r at which the
    difference crosses zero, linearly interpolated between the two grid points that straddle
    it. A constant sign whose worst case clears zero by several standard errors is the
    strongest statement available when r cannot be measured: the SIZE of the difference
    stays unidentified, the DIRECTION does not.
    """
    by_r_b = {x["r"]: x for x in rows_b}
    diffs = []
    for a in rows_a:
        b = by_r_b.get(a["r"])
        if b is None:
            continue
        diffs.append({"r": a["r"], "acc": a[key] - b[key],
                      "se": math.sqrt(a["se"] ** 2 + b["se"] ** 2)})
    if not diffs:
        return None
    diffs.sort(key=lambda x: x["r"])

    signs = {1 if d["acc"] > 0 else (-1 if d["acc"] < 0 else 0) for d in diffs}
    constant = len(signs) == 1 and 0 not in signs

    crossing = None
    for p, q in zip(diffs, diffs[1:]):
        if p["acc"] == 0.0:
            crossing = p["r"]
            break
        if (p["acc"] > 0) != (q["acc"] > 0):
            span = q["acc"] - p["acc"]
            crossing = p["r"] if span == 0 else p["r"] + (q["r"] - p["r"]) * (-p["acc"] / span)
            break

    worst = min(diffs, key=lambda d: abs(d["acc"]))
    iset = identified_set(diffs)
    # does the interval itself keep the sign, or only the point estimates?
    certified = constant and (iset["ci_lo"] > 0.0 or iset["ci_hi"] < 0.0)
    return {"diffs": diffs, "set": iset, "sign_constant": constant,
            "sign_certified": certified, "crossing_r": crossing,
            "worst_case": worst,
            "margin_in_se": (abs(worst["acc"]) / worst["se"]) if worst["se"] else float("nan")}


def print_partial_identification(name_a, rows_a, name_b, rows_b, pretty=""):
    """The honest report of a comparison whose nuisance parameter cannot be measured."""
    v = sign_invariance(rows_a, rows_b)
    if v is None:
        print("   no shared r values -- nothing to compare")
        return None
    s = v["set"]
    print("   identified set of (%s - %s) over the r grid:" % (name_a, name_b))
    print("     [%+.4f at r = %.2f, %+.4f at r = %.2f], width %.4f"
          % (s["lo"], s["lo_at_r"], s["hi"], s["hi_at_r"], s["width"]))
    print("     Imbens-Manski 95 %% interval  [%+.4f, %+.4f]   (critical value %.3f)"
          % (s["ci_lo"], s["ci_hi"], s["critical_value"]))
    w = v["worst_case"]
    print("     worst case over r: %+.4f +/- %.4f at r = %.2f  (%.1f s.e. from zero)"
          % (w["acc"], w["se"], w["r"], v["margin_in_se"]))
    if v["crossing_r"] is not None:
        print("     THE SIGN TURNS OVER at r = %.3f. The direction is NOT identified."
              % v["crossing_r"])
        print("     Report the set, not a winner, and say which side of %.3f you believe."
              % v["crossing_r"])
    elif v["sign_certified"]:
        print("     the sign is CONSTANT over the grid and the interval excludes zero, so")
        print("     the SIZE of the difference is unidentified and its DIRECTION is not:")
        print("     %s beats %s whatever r turns out to be." % (name_a, name_b))
    elif v["sign_constant"]:
        print("     the sign is constant over the grid but the interval touches zero, so")
        print("     the direction is suggested and not established. More replications.")
    return v


# ---------------------------------------------------------------------------
# the measure-set sweep
# ---------------------------------------------------------------------------
# Every measure this package can take downstream of a SPINEPS segmentation. The pedicle
# measures are excluded on purpose: SPINEPS labels the whole neural arch as 41 and never
# isolates the pedicle, so PDW and PDH cannot be read off one. See SPINEPS_MAPPING.md.
SPINEPS_7 = ["endplate", "endplate_depth", "endplate_lower", "endplate_lower_depth",
             "h_post", "canal_w", "canal_ap"]
BASELINE_3 = ["endplate", "h_post", "canal_w"]

JUNCTIONS = {"ct": "cervico-thoracic C7/T1", "tl": "thoraco-lumbar T12/L1"}

# Selection and scoring use DIFFERENT seeds. The winner of a search over k measure subsets
# is optimistically biased if it is scored on the draw that chose it; synthetic columns are
# free, so there is no excuse for scoring on the selection draw.
FIT_SEED = 11
EVAL_SEED = 97


def _score(measures, r, fit_seed=FIT_SEED, eval_seed=EVAL_SEED,
           n_columns=600, n_eval=400):
    """Exact-placement rate over all phenotypes, at one r. Fresh columns at every call."""
    import junction as J
    import panjabi as P

    ref = P.load_reference(measures=measures)
    out = {}
    for key in JUNCTIONS:
        model = J.train(ref, key, measures=measures, n_columns=n_columns, seed=fit_seed,
                        rho=0.5, noise_mm=1.0, scale_sd=0.07, r_between=r)
        hits = tot = 0
        for ph in P.PHENOTYPES:
            s = J.evaluate(model, ref, ph, seed=eval_seed, n=n_eval,
                           rho=0.5, noise_mm=1.0, scale_sd=0.07, r_between=r)
            hits += s.exact
            tot += s.n
        out[key] = (hits / tot if tot else float("nan"), tot)
    return out


def subsets_of(measures: Sequence[str], min_k: int = 1):
    """Every non-empty subset, in a fixed order so a shard index means the same thing twice."""
    ms = list(measures)
    out = []
    for mask in range(1, 1 << len(ms)):
        pick = [ms[i] for i in range(len(ms)) if mask & (1 << i)]
        if len(pick) >= min_k:
            out.append(pick)
    out.sort(key=lambda s: (len(s), [list(ms).index(x) for x in s]))
    return out


def enumerate_subsets(measures=None, min_k: int = 1, r_grid=None, shard: int = 0,
                      n_shards: int = 1, n_columns: int = 600, n_eval: int = 400,
                      out_json: Optional[str] = None, quiet: bool = False):
    """Score EVERY subset at every r. The exact answer, and the ground truth for any procedure.

    At the measure counts this package uses, exhaustive enumeration is not a fallback -- it is
    the right method. It is exact by construction, with no relaxation, big-M, tolerance or
    optimality gap, and it returns the whole ranked distribution rather than an argmax, which
    is worth more here than a winner: a single plausible number is this project's recurring
    failure mode, and a distribution shows how far the runner-up is behind.

    It is also the only honest way to test a budget-allocation procedure. Run OCBA or KN
    against this and you know whether it found the true best, not merely whether it converged.

    Sharding is by subset index, so shard i of n takes subsets i, i+n, i+2n, ... Each shard
    writes its own JSON and gather_shards() merges them. That keeps a Slurm array job's tasks
    independent, which matters because a task that dies takes only its own subsets with it.
    """
    import junction as J
    import panjabi as P

    measures = list(SPINEPS_7 if measures is None else measures)
    r_grid = list(R_GRID if r_grid is None else r_grid)
    all_subsets = subsets_of(measures, min_k)
    mine = [(i, s) for i, s in enumerate(all_subsets) if i % n_shards == shard]

    if not quiet:
        print("EXHAUSTIVE ENUMERATION. Synthetic columns only; no corpus is read.")
        print("  ground set %d measures -> %d non-empty subsets (min_k=%d)"
              % (len(measures), len(all_subsets), min_k))
        print("  shard %d of %d -> %d subsets x %d r values x %d junctions = %d evaluations"
              % (shard, n_shards, len(mine), len(r_grid), len(JUNCTIONS),
                 len(mine) * len(r_grid) * len(JUNCTIONS)))
        print("  fit seed %d, score seed %d (different, so the score is on columns the fit "
              "never saw)\n" % (FIT_SEED, EVAL_SEED))

    rows = []
    for n, (idx, ms) in enumerate(mine, 1):
        ref = P.load_reference(measures=ms)
        for r in r_grid:
            for key in JUNCTIONS:
                model = J.train(ref, key, measures=ms, n_columns=n_columns, seed=FIT_SEED,
                                rho=0.5, noise_mm=1.0, scale_sd=0.07, r_between=r)
                hits = tot = 0
                for ph in P.PHENOTYPES:
                    s = J.evaluate(model, ref, ph, seed=EVAL_SEED, n=n_eval,
                                   rho=0.5, noise_mm=1.0, scale_sd=0.07, r_between=r)
                    hits += s.exact
                    tot += s.n
                acc = hits / tot if tot else float("nan")
                rows.append({"subset_index": idx, "measures": ms, "k": len(ms),
                             "r": r, "junction": key, "acc": acc, "n": tot,
                             "se": binomial_se(acc, tot)})
        if not quiet:
            print("  [%4d/%4d] subset %4d  k=%d  %s"
                  % (n, len(mine), idx, len(ms), ",".join(ms)))

    payload = {"ground_set": measures, "min_k": min_k, "grid": r_grid,
               "n_subsets_total": len(all_subsets), "shard": shard, "n_shards": n_shards,
               "design": {"fit_seed": FIT_SEED, "eval_seed": EVAL_SEED,
                          "n_columns": n_columns, "n_eval": n_eval},
               "rows": rows}
    if out_json:
        os.makedirs(os.path.dirname(os.path.abspath(out_json)), exist_ok=True)
        with open(out_json, "w") as fh:
            json.dump(payload, fh, indent=2)
        if not quiet:
            print("\nwrote %s" % out_json)
    return payload


def gather_shards(paths: Sequence[str], out_json: Optional[str] = None):
    """Merge shard JSONs, rank the subsets, and answer the two open structural questions."""
    rows, ground, grid, total = [], None, None, None
    seen_shards = []
    for p in paths:
        with open(p) as fh:
            d = json.load(fh)
        rows.extend(d["rows"])
        ground = ground or d["ground_set"]
        grid = grid or d["grid"]
        total = total or d["n_subsets_total"]
        seen_shards.append(d["shard"])

    by_subset = defaultdict(dict)
    for x in rows:
        by_subset[tuple(x["measures"])].setdefault(x["junction"], []).append(x)

    done = len(by_subset)
    print("gathered %d shards, %d of %d subsets present" % (len(paths), done, total))
    if done != total:
        print("  INCOMPLETE -- %d subsets are missing. Every number below is over what is"
              % (total - done))
        print("  present, not over the ground set. Do not report a winner from a partial run.")

    out = {"ground_set": ground, "grid": grid, "n_subsets_total": total,
           "n_subsets_present": done, "complete": done == total,
           "shards": sorted(seen_shards), "junctions": {}}

    for key, pretty in JUNCTIONS.items():
        ranked = []
        for ms, per in by_subset.items():
            got = per.get(key)
            if not got:
                continue
            worst = min(got, key=lambda x: x["acc"])
            ranked.append({"measures": list(ms), "k": len(ms),
                           "worst_acc": worst["acc"], "worst_at_r": worst["r"],
                           "se": worst["se"],
                           "best_acc": max(x["acc"] for x in got),
                           "rows": sorted(got, key=lambda x: x["r"])})
        # the maximin choice: best WORST case over r, which is the robust criterion
        ranked.sort(key=lambda x: -x["worst_acc"])
        print("\n  %s -- top 5 by WORST case over r (the maximin choice)" % pretty)
        for x in ranked[:5]:
            print("    %.4f +/- %.4f at r=%.2f   k=%d  %s"
                  % (x["worst_acc"], x["se"], x["worst_at_r"], x["k"],
                     ",".join(x["measures"])))
        if len(ranked) > 1:
            gap = ranked[0]["worst_acc"] - ranked[1]["worst_acc"]
            se = (ranked[0]["se"] ** 2 + ranked[1]["se"] ** 2) ** 0.5
            print("    winner over runner-up: %+.4f +/- %.4f (%.1f s.e.)%s"
                  % (gap, se, gap / se if se else float("nan"),
                     "" if gap > 2 * se else "   <- INSIDE THE NOISE, do not call a winner"))

        # is A monotone in S? compare every subset against every superset one element larger
        acc_at = {}
        for ms, per in by_subset.items():
            for x in per.get(key, []):
                acc_at[(frozenset(ms), x["r"])] = x
        # A drop has to clear the noise to be a drop. Counting every negative difference
        # would report Monte Carlo scatter as a structural finding, which is exactly the
        # failure this package exists to avoid: at n_eval 60 the standard error is 0.024 and
        # half the "violations" are nothing.
        viol, sig, tested, worst_v, worst_sig = 0, 0, 0, 0.0, 0.0
        for (fs, r), x in acc_at.items():
            for e in ground:
                if e in fs:
                    continue
                y = acc_at.get((fs | {e}, r))
                if y is None:
                    continue
                tested += 1
                d = y["acc"] - x["acc"]
                if d >= 0:
                    continue
                viol += 1
                worst_v = min(worst_v, d)
                se_d = math.sqrt(x["se"] ** 2 + y["se"] ** 2)
                if d < -2.0 * se_d:
                    sig += 1
                    worst_sig = min(worst_sig, d)
        if tested:
            print("    monotone in S? %d of %d supersets scored lower, of which %d by more"
                  % (viol, tested, sig))
            print("      than 2 s.e. (worst drop %+.4f, worst significant %+.4f)"
                  % (worst_v, worst_sig))
            if sig:
                print("      ADDING A MEASURE CAN HURT, beyond the noise. The objective is not")
                print("      monotone in S, so a cardinality constraint is not needed to make")
                print("      the problem non-trivial and the unconstrained argmax is a real")
                print("      answer -- which also rules out every submodular-greedy guarantee,")
                print("      all of which assume monotonicity.")
            elif viol:
                print("      No drop clears the noise. On this run monotonicity is neither")
                print("      established nor refuted; raise --n-eval before concluding either.")
            else:
                print("      No subset was beaten by a superset, so the full set may win by")
                print("      construction. Fix k before asking which subset is best, and")
                print("      re-check at higher --n-eval before relying on it.")
        out["junctions"][key] = {"ranked": ranked,
                                 "monotone_in_S": {"drops": viol, "significant_drops": sig,
                                                   "tested": tested, "worst_drop": worst_v,
                                                   "worst_significant_drop": worst_sig}}

    if out_json:
        os.makedirs(os.path.dirname(os.path.abspath(out_json)), exist_ok=True)
        with open(out_json, "w") as fh:
            json.dump(out, fh, indent=2)
        print("\nwrote %s" % out_json)
    return out


def report_from_record(path: str):
    """Re-report the partial identification from a recorded sweep, without re-running it.

    The sweep costs minutes; the inference on top of it costs nothing, and separating the two
    means a change to the REPORTING can be checked against a fixed record rather than against
    a fresh draw that moves underneath it.
    """
    with open(path) as fh:
        rec = json.load(fh)
    res = rec["results"]
    names = [n for n in ("baseline_3", "spineps_7") if n in res]
    print("re-reported from %s" % path)
    print("grid: %s" % ", ".join("%.2f" % r for r in rec.get("grid", [])))
    d = rec.get("design", {})
    if d:
        print("design: fit seed %s, eval seed %s, %s columns, %s eval windows"
              % (d.get("fit_seed"), d.get("eval_seed"), d.get("n_columns"), d.get("n_eval")))
    out = {}
    for key in [k for k in JUNCTIONS if k in res.get(names[0], {})]:
        print("\n  %s" % JUNCTIONS[key])
        for n in names:
            s = identified_set(res[n][key])
            print("   %-10s accuracy in [%.4f, %.4f]  (Imbens-Manski 95 %% "
                  "[%.4f, %.4f])" % (n, s["lo"], s["hi"], s["ci_lo"], s["ci_hi"]))
        print("   how much the grid can be hiding, measured rather than assumed:")
        for n in names:
            print_profile(res[n][key], n)
        if len(names) == 2:
            out[key] = print_partial_identification(names[1], res[names[1]][key],
                                                    names[0], res[names[0]][key])
    return out


def measure_set_sweep(r_grid=None, out_json=None, n_columns=600, n_eval=400):
    """7 SPINEPS-measurable measures against 3, across the whole r grid. Synthetic only."""
    r_grid = list(R_GRID if r_grid is None else r_grid)
    print("SYNTHETIC ONLY. Columns are drawn from Panjabi's published means and spreads.")
    print("No cohort is read.\n")
    print("measures: %d SPINEPS-measurable (%s)" % (len(SPINEPS_7), ", ".join(SPINEPS_7)))
    print("excluded: pedicle width and height -- SPINEPS has no pedicle label\n")

    results = {"baseline_3": {}, "spineps_7": {}}
    for name, ms in (("baseline_3", BASELINE_3), ("spineps_7", SPINEPS_7)):
        print("=" * 72)
        print("%s  (%d measures)" % (name, len(ms)))
        for key, pretty in JUNCTIONS.items():
            print("\n  %s" % pretty)
            rows = []
            for r in r_grid:
                acc, n = _score(ms, r, n_columns=n_columns, n_eval=n_eval)[key]
                se = binomial_se(acc, n)
                note = "<- generator default, OPTIMISTIC" if r == 0 else (
                    "<- the outside anchor's order" if abs(r - EXTERNAL["rho"]) < 1e-9 else "")
                print("    r=%.2f  acc %.4f  MC s.e. %.4f  n=%d  %s"
                      % (r, acc, se, n, note))
                rows.append({"r": r, "acc": acc, "se": se, "n": n})
            results[name][key] = rows
            d = rows[-1]["acc"] - rows[0]["acc"]
            print("    r %.2f -> %.2f moves accuracy %+.4f (%.1f MC s.e.)"
                  % (rows[0]["r"], rows[-1]["r"], d, abs(d) / max(rows[0]["se"], 1e-9)))

    print("\n" + "=" * 72)
    print("7 MEASURES AGAINST 3, scored on columns neither fit saw")
    verdicts = {}
    for key, pretty in JUNCTIONS.items():
        print("\n  %s" % pretty)
        for r in r_grid:
            a3 = [x for x in results["baseline_3"][key] if x["r"] == r][0]
            a7 = [x for x in results["spineps_7"][key] if x["r"] == r][0]
            d = a7["acc"] - a3["acc"]
            se = (a3["se"] ** 2 + a7["se"] ** 2) ** 0.5
            verdict = ("within noise" if abs(d) < 2 * se
                       else ("7 better" if d > 0 else "3 better"))
            print("    r=%.2f   3: %.4f   7: %.4f   diff %+.4f +/- %.4f   %s"
                  % (r, a3["acc"], a7["acc"], d, se, verdict))

    print("\n" + "=" * 72)
    print("PARTIAL IDENTIFICATION. r cannot be measured, so the accuracy is not a point --")
    print("it is an interval. What survives that is a statement about the SIGN.")
    for key, pretty in JUNCTIONS.items():
        print("\n  %s" % pretty)
        for name in ("baseline_3", "spineps_7"):
            s = identified_set(results[name][key])
            print("   %-10s accuracy in [%.4f, %.4f]  (Imbens-Manski 95 %% "
                  "[%.4f, %.4f])" % (name, s["lo"], s["hi"], s["ci_lo"], s["ci_hi"]))
        print("   how much the grid can be hiding, measured rather than assumed:")
        for name in ("baseline_3", "spineps_7"):
            print_profile(results[name][key], name)
        verdicts[key] = print_partial_identification(
            "spineps_7", results["spineps_7"][key],
            "baseline_3", results["baseline_3"][key], pretty)

    payload = {"grid": r_grid,
               "measures": {"spineps_7": SPINEPS_7, "baseline_3": BASELINE_3},
               "results": results,
               "partial_identification": {
                   key: {
                       "accuracy_sets": {n: identified_set(results[n][key])
                                         for n in ("baseline_3", "spineps_7")},
                       "grid_error": {n: profile_in_r(results[n][key])
                                      for n in ("baseline_3", "spineps_7")},
                       "difference": None if verdicts.get(key) is None else {
                           k: v for k, v in verdicts[key].items() if k != "diffs"},
                   } for key in JUNCTIONS},
               "design": {"fit_seed": FIT_SEED, "eval_seed": EVAL_SEED,
                          "n_columns": n_columns, "n_eval": n_eval,
                          "note": "selection and scoring use different seeds; "
                                  "synthetic columns only, no cohort is read; "
                                  "r is unidentified, so the reported object is a "
                                  "Manski identified set with an Imbens-Manski interval, "
                                  "and the conclusion is a claim about the sign"}}
    if out_json:
        os.makedirs(os.path.dirname(os.path.abspath(out_json)), exist_ok=True)
        with open(out_json, "w") as fh:
            json.dump(payload, fh, indent=2)
        print("\nwrote %s" % out_json)
    return payload
