"""Which vertebrae of a normal spine can be identified best, and by what.

    python run.py identify --outdir ../records/identify-2026-10-26

The owner's ask of 2026-10-26 08:21 UTC, with Kunkel et al. 2010 (J Anat 216:320-328) attached:
"On Fig 2A T12 appears to be the most isolated point along the x axis. Please do a similarly
thorough evaluation of whether there are certain vertebra in the synthetic data that you can
maximize the identification of, assuming normal anatomic spine, please rely on the prior
research to formulate this problem most truthfully."

THE PRIOR RESEARCH. Kunkel took Panjabi's cadaveric means (twelve spines, T1 to T12 and L1 to L4;
L5 left out as morphologically distinct, the cervical spine not included) and regressed twenty
parameters per level on one predictor, the posterior vertebral body height (VBHP, read off a
lateral X-ray), by cubic polynomials y = C1 + C2 x + C3 x^2 + C4 x^3 (their Table 1). The body
and end-plate dimensions follow VBHP with R^2 0.92 to 0.995, the canal width 0.96, the canal
depth 0.81. Fig 2A plots the level MEANS of the upper end-plate width against the level means of
VBHP: T1 to T11 run from 14 to 21 mm, T12 sits near 22.7 mm, L1 to L4 cluster at 23.8 to
24.3 mm. The table this package draws from is the same data: refitting Kunkel's curves on it
gives their printed coefficients and R^2 (kunkel_fits, checked by tests/test_identify.py).

WHAT THAT MEANS FOR NAMING A LEVEL. Three things, each of which the record below measures.

1. The level means of the body measures lie close to one curve parameterised by VBHP, so across
   levels the measures move together, mostly along one direction. What tells one level from
   another is where along the curve the body sits and its small, level-specific departure from
   the curve (Kunkel's residual pattern, positive at the first thoracic and last lumbar levels
   and negative in the transition zone).
2. Fig 2A shows means, not spreads. A mean that is isolated among sixteen is not thereby
   identifiable: identifiability is the gap to the nearest other level in units of the
   within-level spread (Panjabi's population SD is 2.5 to 3.8 mm at T12 for VBHP, against a gap
   of 1.1 mm to L1 and 1.4 mm to T11), plus the measurement error and the patient's size. Along
   VBHP alone T12's nearest rival over the whole column is L5, 0.2 mm away, a level Kunkel left
   out.
3. The x axis of Fig 2A is absolute millimetres: one body's absolute size confounds its level
   with the patient's size (a large person's T11 is a small person's T12). Kunkel's equations
   reconstruct a vertebra GIVEN its level; naming the level is the inverse problem, and an
   honest per-level answer is stated with the size unknown (one body, nothing else in view),
   with the size known, and with the size profiled out by the other bodies in the field.

THE MEASURES OF IDENTIFIABILITY, each in the record with its key.

A. `one_measure`: along each measure alone, as Fig 2A invites, the gap from each level to its
   nearest other level in millimetres, in pooled table-SD units (Kunkel's frame) and in units of
   the single-body spread the generator gives (the table's SD, the 1 mm error and the 7 per cent
   size spread added), over Kunkel's sixteen levels and over all twenty-two.
B. `isolation`: in the full space of the seven SPINEPS-measurable measures, the nearest-rival
   Mahalanobis distance of each level under the within-level covariance of the log measures,
   read off a draw of 10,000 typical columns, with the size unknown, known (a draw with no size
   spread), and profiled out (shape only, the contrasts a common factor cannot reach), both
   planes, AP and lateral; `isolation_analytic`, the first-order formula for the same (the size
   spread on every pair, the population SD and the error on the diagonal), kept because it says
   what drives the distance, with its error against the draw in `covariance_check`; and over
   every subset of the measures (`subsets`), the subset and the single measure that isolate
   each level most.
C. `cells`: the classifier of the continued study (C on the field) fitted on typical columns and
   scored on fresh typical columns, per level: the recall (named exactly when it is that level),
   the precision (that level when the model says so), the confusion with every other level, the
   one-against-the-rest detector's AUC from the model's posterior, at every field width and in
   every regime; `detectors`, a binary classifier fitted for each level on its own, beside it;
   `abstain`, the precision and the share of true bodies kept when the model names a level only
   above a confidence chosen on another seed to reach 95 and 99 per cent precision.
D. `size`: the classifier at one body with the size spread removed (size known), doubled, and
   with shape-only features (contrasts of the log measures, which the size cannot reach), and the
   published means with nothing fitted; and `r_sweep`, the unidentified correlation between a
   patient's offsets swept, since r = 0 is the upper bound.

Every number is about synthetic columns drawn from Panjabi's tables; nothing here is a patient.
Only the typical column is drawn, on the owner's words "assuming normal anatomic spine".
"""
from __future__ import annotations

import itertools
import json
import math
import os
import sys
import time
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import panjabi as P                                                  # noqa: E402
import covariance as CV                                              # noqa: E402
import neighbour as NB                                               # noqa: E402
import neighbour_more as NM                                          # noqa: E402

MEASURES7 = list(CV.SPINEPS_7)
K = NB.K
CLASSES = list(NB.CLASSES)
HALVES = (0, 1, 2, 3, 4)
DETECTOR_HALVES = (0, 1, 2)
PRECISION_TARGETS = (0.95, 0.99)
SCALE_SDS = (0.0, 0.07, 0.14)
R_GRID = (0.0, 0.4, 0.8)
N_FIT, N_SELECT, N_SCORE = 1000, 500, 1000
# The table's pedicle rows (Panjabi's PDW and PDH, each the mean of left and right), which no
# SPINEPS label gives (SPINEPS_MAPPING.md): the synthetic data's own ceiling, beyond what the
# segmenter can measure.
TABLE_EXTRA = ("pedicle", "pedicle_h")
MEASURES_TABLE = MEASURES7 + list(TABLE_EXTRA)
GAUSS_HERMITE_NODES = 41
N_MOMENTS = 10000
N_BOOTSTRAP = 400

# Kunkel 2010, Table 1: y = C1 + C2 x + C3 x^2 + C4 x^3 with x the posterior body height, the
# residual SD and R^2 as printed, for the measures this package holds under Panjabi's names.
KUNKEL = {
    "endplate": ("EPWS", (121.650, -15.403, 0.742, -0.010), 1.195, 0.982),
    "endplate_lower": ("EPWI", (300.140, -43.509, 2.206, -0.035), 1.454, 0.976),
    "endplate_depth": ("EPDS", (-60.076, 8.983, -0.293, 0.004), 0.852, 0.981),
    "endplate_lower_depth": ("EPDI", (-63.590, 9.473, -0.300, 0.003), 0.769, 0.981),
    "canal_w": ("SCW", (206.750, -26.838, 1.218, -0.017), 0.634, 0.964),
    "canal_ap": ("SCD", (-2.449, 3.8232, -0.254, 0.006), 0.573, 0.811),
}
# Fig 2A's stated linear fit of EPWS on VBHP: y = 2.20 x - 10.51, R^2 0.94; the cubic's R^2 0.98
KUNKEL_LINEAR_EPWS = (2.20, -10.51, 0.94)
KUNKEL_CUBIC_R2_EPWS = 0.98
KUNKEL_LEVELS = P.THORACIC + ["L1", "L2", "L3", "L4"]


# ---- A. one measure at a time, as Fig 2A invites -----------------------------------------------

def single_body_sd(ref, measure: str, level: str, noise_mm: float, scale_sd: float) -> float:
    """The spread of one body's measure in the generator: the population SD, the measurement
    error and the size spread (scale_sd of the log, so scale_sd times the mean in millimetres)."""
    mu, sd = ref[measure][level]
    return math.sqrt(sd * sd + noise_mm * noise_mm + (scale_sd * mu) ** 2)


def one_measure_isolation(ref, measure: str, levels: Sequence[str], noise_mm: float, scale_sd: float) -> Dict[str, dict]:
    """Each level's nearest other level along one measure, with the gap in millimetres, in pooled
    table-SD units and in pooled single-body-SD units."""
    out = {}
    for lv in levels:
        mu = ref[measure][lv][0]
        best = None
        for other in levels:
            if other == lv:
                continue
            gap = abs(mu - ref[measure][other][0])
            if best is None or gap < best[0]:
                best = (gap, other)
        gap, other = best
        table = math.sqrt(0.5 * (ref[measure][lv][1] ** 2 + ref[measure][other][1] ** 2))
        body = math.sqrt(0.5 * (single_body_sd(ref, measure, lv, noise_mm, scale_sd) ** 2
                                + single_body_sd(ref, measure, other, noise_mm, scale_sd) ** 2))
        out[lv] = {"rival": other, "gap_mm": gap, "gap_table_sd": gap / table, "gap_body_sd": gap / body,
                   "mean_mm": mu, "table_sd_mm": ref[measure][lv][1],
                   "body_sd_mm": single_body_sd(ref, measure, lv, noise_mm, scale_sd)}
    return out


# ---- Kunkel's curves refitted on this table ------------------------------------------------------

def polyfit_r2(x: np.ndarray, y: np.ndarray, degree: int) -> Tuple[List[float], float, float, List[float]]:
    """Coefficients C1..C(degree+1) in Kunkel's order, R^2, the residual SD on n - degree - 1 degrees
    of freedom (Kunkel's SD column) and the residuals by level."""
    c = np.polyfit(x, y, degree)
    yh = np.polyval(c, x)
    res = y - yh
    r2 = 1.0 - float((res * res).sum() / ((y - y.mean()) ** 2).sum())
    sd = math.sqrt(float((res * res).sum()) / max(len(y) - degree - 1, 1))
    return [float(v) for v in c[::-1]], r2, sd, [float(v) for v in res]


def kunkel_fits(ref) -> dict:
    """Kunkel's regressions of each measure on the posterior body height, refitted on this table's
    means over the sixteen levels Kunkel used, beside the printed coefficients; and over all
    twenty-two levels, where the cervical bodies and L5 join the curve or leave it."""
    out = {"levels": KUNKEL_LEVELS, "predictor": "h_post", "measures": {},
           "left_out": [lv for lv in P.LEVELS if lv not in KUNKEL_LEVELS]}
    x16 = np.array([ref["h_post"][lv][0] for lv in KUNKEL_LEVELS])
    x22 = np.array([ref["h_post"][lv][0] for lv in P.LEVELS])
    for m, (name, printed, sd_printed, r2_printed) in KUNKEL.items():
        y16 = np.array([ref[m][lv][0] for lv in KUNKEL_LEVELS])
        y22 = np.array([ref[m][lv][0] for lv in P.LEVELS])
        lin_c, lin_r2, lin_sd, lin_res = polyfit_r2(x16, y16, 1)
        cub_c, cub_r2, cub_sd, cub_res = polyfit_r2(x16, y16, 3)
        pred_printed = np.polyval(list(printed)[::-1], x16)
        cub22_c, cub22_r2, cub22_sd, cub22_res = polyfit_r2(x22, y22, 3)
        # the levels Kunkel left out, set against the curve fitted without them: how far each
        # table mean sits from the T1-L4 cubic, in millimetres and in that level's own table SD
        departures = {}
        for lv in out["left_out"]:
            predicted = float(np.polyval(cub_c[::-1], ref["h_post"][lv][0]))
            residual = float(ref[m][lv][0] - predicted)
            departures[lv] = {"residual_mm": residual, "in_table_sd": residual / float(ref[m][lv][1])}
        out["measures"][m] = {
            "kunkel_name": name,
            "printed": {"coefficients": list(printed), "sd": sd_printed, "r2": r2_printed,
                        "rms_mm_at_this_table": float(np.sqrt(((y16 - pred_printed) ** 2).mean())),
                        "max_mm_at_this_table": float(np.abs(y16 - pred_printed).max())},
            "linear_16": {"coefficients": lin_c, "r2": lin_r2, "sd": lin_sd,
                          "residuals": dict(zip(KUNKEL_LEVELS, lin_res))},
            "cubic_16": {"coefficients": cub_c, "r2": cub_r2, "sd": cub_sd,
                         "residuals": dict(zip(KUNKEL_LEVELS, cub_res))},
            "cubic_22": {"coefficients": cub22_c, "r2": cub22_r2, "sd": cub22_sd,
                         "residuals": dict(zip(P.LEVELS, cub22_res))},
            "departures_from_cubic_16": departures}
    out["fig2a_linear_stated"] = {"slope": KUNKEL_LINEAR_EPWS[0], "intercept": KUNKEL_LINEAR_EPWS[1],
                                  "r2": KUNKEL_LINEAR_EPWS[2]}
    out["fig2a_cubic_r2_stated"] = KUNKEL_CUBIC_R2_EPWS
    return out


# ---- B. the closed-form isolation in the full space ----------------------------------------------

def helmert(p: int) -> np.ndarray:
    """p - 1 orthonormal contrasts, each summing to zero: the directions the size cannot reach."""
    H = np.zeros((p - 1, p))
    for k in range(1, p):
        H[k - 1, :k] = 1.0 / math.sqrt(k * (k + 1))
        H[k - 1, k] = -k / math.sqrt(k * (k + 1))
    return H


def level_moments(ref, measures: Sequence[str], constant, scale_sd: float, noise_mm: float,
                  rho: float, r_between: float) -> Tuple[np.ndarray, np.ndarray]:
    """The mean and covariance of one body's log measures at each level, by the delta method: the
    mean is the log of the table's mean less half the relative variance, since log(1 + x) for x
    normal with SD cv has mean -cv^2 / 2 to that order (the size is exp of a normal and shifts
    nothing); the patient's size scale_sd^2 on every pair, the population SD and the error on the
    diagonal with the second-order term of the log (2.5 cv^4, the variance of log(1 + x) to that
    order), and the correlated part of the patient's offsets, rho^2 r cv_m cv_k, off the diagonal. The draw's own moments (level_moments_empirical) still
    run above this where cv reaches a quarter, since the log's lower tail is heavier than any
    polynomial order and the generator floors a value at 0.5 mm."""
    p = len(measures)
    M = np.zeros((K, p))
    S = np.zeros((K, p, p))
    for i, lv in enumerate(CLASSES):
        mu = np.array([ref[m][lv][0] for m in measures])
        sd = np.array([ref[m][lv][1] for m in measures])
        cv = sd / mu
        relative_var = cv * cv + (noise_mm / mu) ** 2
        M[i] = np.log(mu / np.array([constant[m] for m in measures])) - 0.5 * relative_var
        cov = np.full((p, p), scale_sd * scale_sd)
        cov += rho * rho * r_between * np.outer(cv, cv) * (1.0 - np.eye(p))
        cov += np.diag(cv * cv + 2.5 * cv ** 4 + (noise_mm / mu) ** 2)
        S[i] = cov
    return M, S


def mahalanobis_matrix(M: np.ndarray, S: np.ndarray) -> np.ndarray:
    """The distance between every pair of levels under their pooled covariance."""
    k = len(M)
    D = np.zeros((k, k))
    for i in range(k):
        for j in range(i + 1, k):
            d = M[i] - M[j]
            D[i, j] = D[j, i] = math.sqrt(float(d @ np.linalg.solve(0.5 * (S[i] + S[j]), d)))
    return D


def bhattacharyya_matrix(M: np.ndarray, S: np.ndarray) -> np.ndarray:
    """The Bhattacharyya distance between every pair of levels: the pooled Mahalanobis term and
    the term the pooled distance drops, half the log of the pooled determinant over the geometric
    mean of the two, which is the separation two levels get from spreads of different size."""
    k = len(M)
    B = np.zeros((k, k))
    logdet = [float(np.linalg.slogdet(S[i])[1]) for i in range(k)]
    for i in range(k):
        for j in range(i + 1, k):
            pooled = 0.5 * (S[i] + S[j])
            d = M[i] - M[j]
            B[i, j] = B[j, i] = (0.125 * float(d @ np.linalg.solve(pooled, d))
                                 + 0.5 * (float(np.linalg.slogdet(pooled)[1]) - 0.5 * (logdet[i] + logdet[j])))
    return B


def nearest_rivals(D: np.ndarray, B: Optional[np.ndarray] = None) -> Dict[str, dict]:
    """Each level's nearest other level by the pooled Mahalanobis distance, with the second, the
    pairwise error two equally likely levels at that distance would have, and, where B is given,
    the nearest by the Bhattacharyya distance with the bound it puts on the pairwise error."""
    out = {}
    for i, lv in enumerate(CLASSES):
        order = [j for j in np.argsort(D[i]) if j != i]
        out[lv] = {"rival": CLASSES[order[0]], "d": float(D[i, order[0]]),
                   "second": CLASSES[order[1]], "d_second": float(D[i, order[1]]),
                   "pair_error": float(0.5 * math.erfc(D[i, order[0]] / (2 * math.sqrt(2))))}
        if B is not None:
            ob = [j for j in np.argsort(B[i]) if j != i]
            out[lv]["rival_bhattacharyya"] = CLASSES[ob[0]]
            out[lv]["bhattacharyya"] = float(B[i, ob[0]])
            out[lv]["bhattacharyya_error_bound"] = float(0.5 * math.exp(-B[i, ob[0]]))
            out[lv]["mahalanobis_to_that_rival"] = float(D[i, ob[0]])
    return out


def level_moments_empirical(ref, measures: Sequence[str], constant, synth: dict, n: int, seed: int,
                            scale_sd: Optional[float] = None, r_between: float = 0.0) -> Tuple[np.ndarray, np.ndarray]:
    """The same moments read off a draw of n typical columns, which is what the isolation below
    uses: the log of a measure whose spread is a quarter of its mean has a heavier lower tail
    than the first-order formula allows, and the draw carries the generator's clipping too."""
    kw = dict(synth)
    if scale_sd is not None:
        kw["scale_sd"] = scale_sd
    cols = NB.draw_columns(ref, ("typical",), seed, n, measures, r_between=r_between, **kw)
    rows = NM.self_rows(cols, measures, constant)
    p = len(measures)
    M = np.zeros((K, p))
    S = np.zeros((K, p, p))
    for i in range(K):
        X = rows.X[rows.y == i]
        M[i] = X.mean(0)
        S[i] = np.cov(X.T)
    return M, S


def isolation_of(M: np.ndarray, S: np.ndarray, M0: np.ndarray, S0: np.ndarray, measures: Sequence[str]) -> dict:
    """The nearest-rival distance of every level with the size unknown (the generator as it is,
    moments M and S), known (the moments of a draw with no size spread, M0 and S0) and profiled
    out (shape only: the Helmert contrasts of the first, which a common factor cannot reach)."""
    H = helmert(len(measures))
    Mh = M @ H.T
    Sh = np.einsum("ab,kbc,dc->kad", H, S, H)
    out = {}
    for name, (Mx, Sx) in (("size_unknown", (M, S)), ("size_known", (M0, S0)), ("shape_only", (Mh, Sh))):
        D = mahalanobis_matrix(Mx, Sx)
        out[name] = {"nearest": nearest_rivals(D, bhattacharyya_matrix(Mx, Sx)), "matrix": D.tolist()}
    out["measures"] = list(measures)
    return out


def isolation_in_r(ref, measures: Sequence[str], constant, synth: dict, grid=(0.0, 0.3, 0.6, 0.9)) -> dict:
    """The formula's nearest-rival distance with the unidentified r swept: per level the interval
    over the grid and whether the distance rises or falls with r, since the direction differs by
    level (a pair whose mean steps have mixed signs across the measures separates further as the
    offsets correlate), so r = 0 is the favourable end for some levels and the unfavourable for
    others."""
    rows = {}
    for r in grid:
        M, S = level_moments(ref, measures, constant, synth["scale_sd"], synth["noise_mm"], synth["rho"], r)
        near = nearest_rivals(mahalanobis_matrix(M, S))
        rows[str(r)] = {lv: near[lv]["d"] for lv in CLASSES}
    out = {"grid": list(grid), "by_r": rows, "by_level": {}}
    for lv in CLASSES:
        ds = [rows[str(r)][lv] for r in grid]
        out["by_level"][lv] = {"lo": min(ds), "hi": max(ds), "at_r0": ds[0], "at_r_max": ds[-1],
                               "rises_with_r": bool(ds[-1] > ds[0])}
    return out


def field_moments(ref, measures: Sequence[str], constant, synth: dict, offs: Sequence[int], c: int,
                  r_between: float = 0.0) -> Tuple[np.ndarray, np.ndarray]:
    """The joint mean and covariance of a field's log measures when the target is level c, by the
    formula: each visible body's own moments on the diagonal blocks, and between two bodies of
    one patient the size on every pair and the shared offset rho^2 cv_a cv_b on the same measure
    (times r across measures). This is what a field can profile out and one body cannot."""
    p = len(measures)
    D = len(offs)
    M1, S1 = level_moments(ref, measures, constant, synth["scale_sd"], synth["noise_mm"], synth["rho"], r_between)
    cvs = []
    for d in offs:
        lv = CLASSES[c + d]
        cvs.append(np.array([ref[m][lv][1] / ref[m][lv][0] for m in measures]))
    mean = np.concatenate([M1[c + d] for d in offs])
    cov = np.zeros((D * p, D * p))
    R = np.full((p, p), r_between) + (1.0 - r_between) * np.eye(p)
    for a in range(D):
        for b in range(D):
            if a == b:
                block = S1[c + offs[a]]
            else:
                block = synth["scale_sd"] ** 2 + synth["rho"] ** 2 * np.outer(cvs[a], cvs[b]) * R
            cov[a * p:(a + 1) * p, b * p:(b + 1) * p] = block
    return mean, cov


def field_isolation(ref, measures: Sequence[str], constant, synth: dict, half: int, r_between: float = 0.0) -> dict:
    """The nearest-rival distance of each level named through a field of the given half-width, by
    the formula: the field's joint Gaussian under each candidate name, the pooled Mahalanobis
    distance between candidates. At half 0 this is the one-body isolation with the size unknown;
    wider, the shared size and offsets are in the covariance, so the field profiles them out as
    far as the formula allows."""
    offs = NM.field_offsets(half, True)
    cands = [int(c) for c in NM.candidates(offs)]
    moments = {c: field_moments(ref, measures, constant, synth, offs, c, r_between) for c in cands}
    out = {}
    for c in cands:
        best = None
        for c2 in cands:
            if c2 == c:
                continue
            d = moments[c][0] - moments[c2][0]
            dist = math.sqrt(float(d @ np.linalg.solve(0.5 * (moments[c][1] + moments[c2][1]), d)))
            if best is None or dist < best[0]:
                best = (dist, c2)
        out[CLASSES[c]] = {"rival": CLASSES[best[1]], "d": best[0],
                           "pair_error": float(0.5 * math.erfc(best[0] / (2 * math.sqrt(2))))}
    return {"half": half, "visible_bodies": len(offs), "levels": [CLASSES[c] for c in cands], "nearest": out}


def table_bootstrap(ref, measures: Sequence[str], constant, synth: dict, n_draws: int, seed: int = 17) -> dict:
    """The reference table's own sampling error carried through: each level's means redrawn from
    N(mean, SEM) and each SD from its chi distribution on eleven degrees of freedom (twelve
    spines), the one-measure gap along the posterior body height and the formula's seven-measure
    nearest-rival distance recomputed on each draw; per level the interval, how often its nearest
    rival is the point estimate's, its rank among the 22 and how often it is the most isolated."""
    rng = np.random.default_rng(seed)
    n = 12
    point_h = one_measure_isolation(ref, "h_post", P.LEVELS, synth["noise_mm"], synth["scale_sd"])
    M, S = level_moments(ref, measures, constant, synth["scale_sd"], synth["noise_mm"], synth["rho"], 0.0)
    point_7 = nearest_rivals(mahalanobis_matrix(M, S))
    gaps = {lv: [] for lv in CLASSES}
    ds = {lv: [] for lv in CLASSES}
    same_h = {lv: 0 for lv in CLASSES}
    same_7 = {lv: 0 for lv in CLASSES}
    rank_7 = {lv: [] for lv in CLASSES}
    top_7 = {lv: 0 for lv in CLASSES}
    top_h = {lv: 0 for lv in CLASSES}
    for _ in range(n_draws):
        drawn = {m: {} for m in measures}
        for m in measures:
            for lv in P.LEVELS:
                mu, sd = ref[m][lv]
                mu2 = mu + rng.normal(0.0, sd / math.sqrt(n))
                sd2 = sd * math.sqrt(rng.chisquare(n - 1) / (n - 1))
                drawn[m][lv] = (max(mu2, 0.5), sd2)
        h = one_measure_isolation(drawn, "h_post", P.LEVELS, synth["noise_mm"], synth["scale_sd"])
        Mb, Sb = level_moments(drawn, measures, constant, synth["scale_sd"], synth["noise_mm"], synth["rho"], 0.0)
        near = nearest_rivals(mahalanobis_matrix(Mb, Sb))
        order = sorted(CLASSES, key=lambda lv: -near[lv]["d"])
        top_7[order[0]] += 1
        top_h[max(CLASSES, key=lambda lv: h[lv]["gap_body_sd"])] += 1
        for lv in CLASSES:
            gaps[lv].append(h[lv]["gap_body_sd"])
            ds[lv].append(near[lv]["d"])
            same_h[lv] += int(h[lv]["rival"] == point_h[lv]["rival"])
            same_7[lv] += int(near[lv]["rival"] == point_7[lv]["rival"])
            rank_7[lv].append(order.index(lv) + 1)
    out = {"n_draws": n_draws, "seed": seed, "spines": n, "by_level": {}}
    for lv in CLASSES:
        g, d, rk = np.asarray(gaps[lv]), np.asarray(ds[lv]), np.asarray(rank_7[lv])
        out["by_level"][lv] = {
            "gap_body_sd_point": point_h[lv]["gap_body_sd"], "gap_body_sd_lo": float(np.percentile(g, 2.5)),
            "gap_body_sd_hi": float(np.percentile(g, 97.5)), "same_rival_h_post": same_h[lv] / n_draws,
            "most_isolated_h_post": top_h[lv] / n_draws,
            "d_point": point_7[lv]["d"], "d_lo": float(np.percentile(d, 2.5)), "d_hi": float(np.percentile(d, 97.5)),
            "same_rival_7": same_7[lv] / n_draws, "rank_7_point": sorted(CLASSES, key=lambda x: -point_7[x]["d"]).index(lv) + 1,
            "rank_7_lo": int(np.percentile(rk, 2.5)), "rank_7_hi": int(np.percentile(rk, 97.5)),
            "most_isolated_7": top_7[lv] / n_draws}
    return out


def isolation_analytic(ref, measures: Sequence[str], constant, synth: dict, r_between: float = 0.0) -> dict:
    """The first-order moments, kept as the formula that says what drives the distance."""
    M, S = level_moments(ref, measures, constant, synth["scale_sd"], synth["noise_mm"], synth["rho"], r_between)
    M0, S0 = level_moments(ref, measures, constant, 0.0, synth["noise_mm"], synth["rho"], r_between)
    return isolation_of(M, S, M0, S0, measures)


def isolation(ref, measures: Sequence[str], constant, synth: dict, n: int, seed: int = 5) -> dict:
    """The main isolation: from the moments of a draw, size unknown and known, shape only."""
    M, S = level_moments_empirical(ref, measures, constant, synth, n, seed)
    M0, S0 = level_moments_empirical(ref, measures, constant, synth, n, seed, scale_sd=0.0)
    out = isolation_of(M, S, M0, S0, measures)
    out["n_columns"] = n
    out["seed"] = seed
    return out


def subset_isolation(M: np.ndarray, S: np.ndarray) -> dict:
    """Every subset of the seven measures, size unknown, from the moments of the draw: the subset
    that isolates each level most, the best single measure, and the full set, the AP set and the
    lateral set for comparison."""
    best: Dict[str, dict] = {lv: {"d": -1.0} for lv in CLASSES}
    single: Dict[str, dict] = {lv: {"d": -1.0} for lv in CLASSES}
    per_measure: Dict[str, Dict[str, float]] = {}
    named = {}
    for k in range(1, len(MEASURES7) + 1):
        for idx in itertools.combinations(range(len(MEASURES7)), k):
            idx = list(idx)
            D = mahalanobis_matrix(M[:, idx], S[:, idx][:, :, idx])
            near = nearest_rivals(D)
            ms = [MEASURES7[j] for j in idx]
            key = frozenset(ms)
            if key in (frozenset(MEASURES7), frozenset(NB.REGIMES["ap"]), frozenset(NB.REGIMES["lateral"])):
                named[key] = {lv: near[lv]["d"] for lv in CLASSES}
            for lv in CLASSES:
                d = near[lv]["d"]
                if d > best[lv]["d"]:
                    best[lv] = {"d": d, "measures": ms, "rival": near[lv]["rival"]}
                if k == 1:
                    per_measure.setdefault(ms[0], {})[lv] = d
                    if d > single[lv]["d"]:
                        single[lv] = {"d": d, "measure": ms[0], "rival": near[lv]["rival"]}
    return {"best_subset": best, "best_single": single, "per_measure": per_measure,
            "full": named[frozenset(MEASURES7)], "ap": named[frozenset(NB.REGIMES["ap"])],
            "lateral": named[frozenset(NB.REGIMES["lateral"])],
            "n_subsets": 2 ** len(MEASURES7) - 1}


def covariance_check(ref, measures: Sequence[str], constant, synth: dict, n: int, seed: int = 5) -> dict:
    """The first-order moments against the draw's: the largest relative error of a variance, with
    the level and measure it is at and its coefficient of variation, and the largest absolute
    error of a covariance and of a mean, over every level."""
    M, S = level_moments(ref, measures, constant, synth["scale_sd"], synth["noise_mm"], synth["rho"], 0.0)
    Me, Se = level_moments_empirical(ref, measures, constant, synth, n, seed)
    worst = {"relative_error_variance": 0.0}
    worst_cov, worst_mean = 0.0, 0.0
    off = ~np.eye(len(measures), dtype=bool)
    for i in range(K):
        rel = np.diag(Se[i]) / np.diag(S[i]) - 1.0
        j = int(np.abs(rel).argmax())
        if abs(rel[j]) > worst["relative_error_variance"]:
            worst = {"relative_error_variance": float(abs(rel[j])), "level": CLASSES[i], "measure": measures[j],
                     "cv": ref[measures[j]][CLASSES[i]][1] / ref[measures[j]][CLASSES[i]][0],
                     "variance_draw": float(Se[i][j, j]), "variance_formula": float(S[i][j, j])}
        worst_mean = max(worst_mean, float(np.abs(Me[i] - M[i]).max()))
        worst_cov = max(worst_cov, float(np.abs(Se[i][off] - S[i][off]).max()))
    return {"n_columns": n, "seed": seed, "worst_variance": worst,
            "max_abs_error_covariance": worst_cov, "max_abs_error_mean": worst_mean}


# ---- C. the classifier, level by level -----------------------------------------------------------

def average_ranks(v: np.ndarray) -> np.ndarray:
    order = np.argsort(v, kind="mergesort")
    ranks = np.empty(len(v), float)
    sv = v[order]
    i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and sv[j + 1] == sv[i]:
            j += 1
        ranks[order[i:j + 1]] = 0.5 * (i + j) + 1.0
        i = j + 1
    return ranks


def auc(score: np.ndarray, positive: np.ndarray) -> float:
    """The one-against-the-rest detector's area under the ROC curve, by the rank statistic."""
    n_pos = int(positive.sum())
    n_neg = len(positive) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    r = average_ranks(score)
    return float((r[positive].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def level_table(prob: np.ndarray, rows: NB.Rows, levels: Sequence[int]) -> Tuple[Dict[str, dict], List[List[int]]]:
    """Per level: recall, precision, F1, within one, the detector's AUC; and the confusion matrix,
    rows the true level, columns the name given."""
    pred = prob.argmax(1)
    conf = np.zeros((K, K), int)
    for t, p in zip(rows.y, pred):
        conf[t, p] += 1
    out = {}
    for c in levels:
        true = rows.y == c
        called = pred == c
        tp = int((true & called).sum())
        n_true, n_called = int(true.sum()), int(called.sum())
        recall = tp / n_true if n_true else float("nan")
        precision = tp / n_called if n_called else float("nan")
        lo, hi = NB.wilson(tp, n_true)
        f1 = 2 * tp / (n_true + n_called) if n_true + n_called else float("nan")
        within = float((np.abs(pred[true] - c) <= 1).mean()) if n_true else float("nan")
        pair = {}
        for other in (c - 1, c + 1):
            if other in levels:
                sel = true | (rows.y == other)
                lp = np.log(prob[sel][:, [c, other]] + 1e-300)
                pair[CLASSES[other]] = auc(lp[:, 0] - lp[:, 1], rows.y[sel] == c)
        out[CLASSES[c]] = {"n": n_true, "n_called": n_called, "tp": tp, "recall": recall,
                           "recall_wilson": [lo, hi], "precision": precision, "f1": f1,
                           "within_one": within, "auc": auc(prob[:, c], true), "auc_vs_adjacent": pair,
                           "mean_confidence_when_true": float(prob[true, c].mean()) if n_true else float("nan"),
                           "se_cluster": NB.clustered_se((pred[true] == c).astype(float), rows.group[true]) if n_true else float("nan")}
    return out, conf.tolist()


def abstain_thresholds(prob: np.ndarray, rows: NB.Rows, levels: Sequence[int], targets: Sequence[float]) -> Dict[str, Dict[str, Optional[float]]]:
    """For each level and precision target, the lowest confidence above which naming the level
    keeps that precision on these rows, so the share of true bodies kept is the largest; None
    where no confidence reaches it."""
    out: Dict[str, Dict[str, Optional[float]]] = {}
    for c in levels:
        s = prob[:, c]
        order = np.argsort(-s, kind="mergesort")
        hits = (rows.y[order] == c).astype(float)
        precision = np.cumsum(hits) / np.arange(1, len(hits) + 1)
        out[CLASSES[c]] = {}
        for t in targets:
            ok = np.nonzero(precision >= t)[0]
            out[CLASSES[c]][str(t)] = float(s[order[ok[-1]]]) if len(ok) else None
    return out


def abstain_apply(prob: np.ndarray, rows: NB.Rows, levels: Sequence[int], thresholds, targets: Sequence[float]) -> Dict[str, dict]:
    out = {}
    for c in levels:
        out[CLASSES[c]] = {}
        true = rows.y == c
        for t in targets:
            th = thresholds[CLASSES[c]][str(t)]
            if th is None:
                out[CLASSES[c]][str(t)] = {"threshold": None, "precision": float("nan"), "kept": 0.0, "n_called": 0}
                continue
            called = prob[:, c] >= th
            tp = int((true & called).sum())
            out[CLASSES[c]][str(t)] = {"threshold": th, "n_called": int(called.sum()),
                                       "precision": tp / int(called.sum()) if called.any() else float("nan"),
                                       "kept": tp / int(true.sum()) if true.any() else float("nan")}
    return out


def fit_binary(X: np.ndarray, positive: np.ndarray, l2: float = 1e-3) -> np.ndarray:
    """One level against the rest, by the same Newton solver with two classes."""
    mu, sd = X.mean(0), X.std(0)
    sd[sd == 0] = 1.0
    y = np.where(positive, 0, 1)
    W = NB.fit_softmax((X - mu) / sd, y, k=2, l2=l2)
    return np.r_[W[:-1, 0] / sd, W[-1, 0] - float((W[:-1, 0] / sd * mu).sum())]


def binary_score(w: np.ndarray, X: np.ndarray) -> np.ndarray:
    return X @ w[:-1] + w[-1]


COMMON_LEVELS = [lv for lv in CLASSES if CLASSES.index("C7") <= CLASSES.index(lv) <= CLASSES.index("L1")]
THORACOLUMBAR_FIELD = ["T10", "T11", "T12", "L1", "L2", "L3", "L4", "L5"]


def chance_by_level(levels: Sequence[int]) -> Dict[str, dict]:
    """What a guess gets at each level: 1/k over the k levels the field can name, and 1 over the
    number of those in the level's own region, for a guesser that knows the region alone."""
    names = [CLASSES[c] for c in levels]
    out = {}
    for lv in names:
        same_region = [x for x in names if P.region_of(x) == P.region_of(lv)]
        out[lv] = {"uniform": 1.0 / len(names), "region_known": 1.0 / len(same_region)}
    return out


def precision_under_prior(conf: List[List[int]], levels: Sequence[int], prior: Dict[str, float]) -> Dict[str, float]:
    """The precision of each name under another prior over the true levels: the row-normalised
    confusion reweighted, since the scoring columns hold every level once."""
    C = np.asarray(conf, float)
    share = C / np.maximum(C.sum(1, keepdims=True), 1)
    w = np.zeros(K)
    for lv, pr in prior.items():
        w[CLASSES.index(lv)] = pr
    joint = share * w[:, None]
    called = joint.sum(0)
    out = {}
    for c in levels:
        lv = CLASSES[c]
        out[lv] = float(joint[c, c] / called[c]) if called[c] > 0 and w[c] > 0 else float("nan")
    return out


def cell(ref, regime: str, half: int, fit_cols, sel_cols, sco_cols, constant, with_detectors: bool,
         measures: Optional[Sequence[str]] = None) -> dict:
    measures = list(NB.REGIMES[regime] if measures is None else measures)
    offs = NM.field_offsets(half, True)
    levels = [int(c) for c in NM.candidates(offs)]
    fit = NM.field_rows(fit_cols, offs, measures, constant)
    sel = NM.field_rows(sel_cols, offs, measures, constant)
    sco = NM.field_rows(sco_cols, offs, measures, constant)
    model = NB.train_softmax(fit, "field", measures)
    prob = model.probabilities(sco.X)
    table, conf = level_table(prob, sco, levels)
    thresholds = abstain_thresholds(model.probabilities(sel.X), sel, levels, PRECISION_TARGETS)
    hit = (prob.argmax(1) == sco.y).astype(float)
    common = np.isin(sco.y, [CLASSES.index(lv) for lv in COMMON_LEVELS])
    tl_levels = [lv for lv in THORACOLUMBAR_FIELD if CLASSES.index(lv) in levels]
    tl_prior = {lv: 1.0 / len(tl_levels) for lv in tl_levels}
    out = {"regime": regime, "measures": measures, "half": half, "offsets": list(offs), "visible_bodies": len(offs),
           "levels": [CLASSES[c] for c in levels], "n_fit_rows": len(fit.y), "n_score_rows": len(sco.y),
           "fit_seconds": model.fit_seconds, "chance": NB.chance(sco), "chance_by_level": chance_by_level(levels),
           "exact": float(hit.mean()), "se_cluster": NB.clustered_se(hit, sco.group),
           "exact_common_levels": float(hit[common].mean()), "common_levels": COMMON_LEVELS,
           "within_one": float((np.abs(prob.argmax(1) - sco.y) <= 1).mean()),
           "by_level": table, "confusion": conf,
           "precision_thoracolumbar_prior": precision_under_prior(conf, levels, tl_prior),
           "thoracolumbar_prior": tl_prior,
           "abstain": abstain_apply(prob, sco, levels, thresholds, PRECISION_TARGETS),
           "shuffle": NM.field_shuffle_invariance(ref, offs, measures, model, constant)}
    if with_detectors:
        det = {}
        for c in levels:
            t0 = time.perf_counter()
            w = fit_binary(fit.X, fit.y == c)
            s = binary_score(w, sco.X)
            det[CLASSES[c]] = {"auc": auc(s, sco.y == c), "auc_from_posterior": table[CLASSES[c]]["auc"],
                               "fit_seconds": time.perf_counter() - t0}
        out["detectors"] = det
    return out


# ---- D. the size, and the unidentified r --------------------------------------------------------

def shape_only(rows: NB.Rows, offs: Sequence[int], p: int) -> NB.Rows:
    """The features with the size removed: within each visible body, the Helmert contrasts of its
    log measures, which a common factor on every measure cannot reach."""
    H = helmert(p)
    n = len(rows.X)
    Xb = rows.X.reshape(n, len(offs), p)
    Xh = np.einsum("ndp,cp->ndc", Xb, H).reshape(n, len(offs) * (p - 1))
    return NB.Rows(X=Xh, y=rows.y, rib=rows.rib, group=rows.group, phenotype=rows.phenotype,
                   n_columns=rows.n_columns, names=["contrast %d(%+d)" % (c, d) for d in offs for c in range(p - 1)])


def size_study(ref, constant, n_fit: int, n_score: int, halves=(0, 2)) -> dict:
    measures = NB.REGIMES["both"]
    p = len(measures)
    pub = NM.build_published_self(ref, measures, constant)
    out = {"halves": list(halves), "scale_sds": list(SCALE_SDS), "variants": []}
    for half in halves:
        offs = NM.field_offsets(half, True)
        levels = [int(c) for c in NM.candidates(offs)]
        for scale_sd in SCALE_SDS:
            fit_cols = NB.draw_columns(ref, ("typical",), NB.FIT_SEED, n_fit, measures, scale_sd=scale_sd)
            sco_cols = NB.draw_columns(ref, ("typical",), NB.SCORE_SEED, n_score, measures, scale_sd=scale_sd)
            fit = NM.field_rows(fit_cols, offs, measures, constant)
            sco = NM.field_rows(sco_cols, offs, measures, constant)
            variants = [("absolute", fit, sco)]
            if scale_sd == NB.SYNTH["scale_sd"]:
                variants.append(("shape_only", shape_only(fit, offs, p), shape_only(sco, offs, p)))
            for name, f, s in variants:
                model = NB.train_softmax(f, "field", measures)
                prob = model.probabilities(s.X)
                table, _ = level_table(prob, s, levels)
                hit = (prob.argmax(1) == s.y).astype(float)
                out["variants"].append({"half": half, "visible_bodies": len(offs), "scale_sd": scale_sd, "features": name,
                                        "exact": float(hit.mean()), "se_cluster": NB.clustered_se(hit, s.group),
                                        "recall_by_level": {lv: table[lv]["recall"] for lv in table},
                                        "precision_by_level": {lv: table[lv]["precision"] for lv in table}})
            if scale_sd == NB.SYNTH["scale_sd"]:
                G = NM.Field(offs=offs, p=p, published=pub)
                prob = G.probabilities(sco.X)
                table, _ = level_table(prob, sco, levels)
                hit = (prob.argmax(1) == sco.y).astype(float)
                out["variants"].append({"half": half, "visible_bodies": len(offs), "scale_sd": scale_sd, "features": "published_means",
                                        "exact": float(hit.mean()), "se_cluster": NB.clustered_se(hit, sco.group),
                                        "recall_by_level": {lv: table[lv]["recall"] for lv in table},
                                        "precision_by_level": {lv: table[lv]["precision"] for lv in table}})
    return out


def axes_study(ref, constant, fit_cols, sco_cols) -> dict:
    """One body named along the axes of Fig 2A: the posterior body height alone, the upper
    end-plate width alone, and the two together, by the same classifier; what the figure's plane
    can do by itself."""
    out = {}
    for name, measures in (("h_post", ["h_post"]), ("endplate", ["endplate"]), ("h_post+endplate", ["h_post", "endplate"])):
        offs = NM.field_offsets(0, True)
        fit = NM.field_rows(fit_cols, offs, measures, constant)
        sco = NM.field_rows(sco_cols, offs, measures, constant)
        model = NB.train_softmax(fit, "field", measures)
        prob = model.probabilities(sco.X)
        table, conf = level_table(prob, sco, list(range(K)))
        hit = (prob.argmax(1) == sco.y).astype(float)
        out[name] = {"measures": measures, "exact": float(hit.mean()), "se_cluster": NB.clustered_se(hit, sco.group),
                     "recall_by_level": {lv: table[lv]["recall"] for lv in table},
                     "precision_by_level": {lv: table[lv]["precision"] for lv in table}, "confusion": conf}
    return out


def bayes_study(ref, constant, synth: dict, sco_cols, n_moments: int, seed: int = 5) -> dict:
    """The quadratic rule under the generator's own moments at one body: each level's mean and
    covariance from the draw, the log density of each level at the body, the largest wins. The
    ceiling the linear classifier is held to: where it is no better, the shortfall is the
    information and not the classifier."""
    measures = NB.REGIMES["both"]
    M, S = level_moments_empirical(ref, measures, constant, synth, n_moments, seed)
    offs = NM.field_offsets(0, True)
    sco = NM.field_rows(sco_cols, offs, measures, constant)
    logp = np.zeros((len(sco.X), K))
    for i in range(K):
        R = sco.X - M[i]
        logp[:, i] = -0.5 * np.einsum("nj,nj->n", R @ np.linalg.inv(S[i]), R) - 0.5 * float(np.linalg.slogdet(S[i])[1])
    prob = NB.softmax(logp)
    table, conf = level_table(prob, sco, list(range(K)))
    hit = (prob.argmax(1) == sco.y).astype(float)
    return {"n_moment_columns": n_moments, "exact": float(hit.mean()), "se_cluster": NB.clustered_se(hit, sco.group),
            "recall_by_level": {lv: table[lv]["recall"] for lv in table},
            "precision_by_level": {lv: table[lv]["precision"] for lv in table}, "confusion": conf}


def bayes_exact_one_body(ref, measures: Sequence[str], synth: dict, sco_cols, n_nodes: int = GAUSS_HERMITE_NODES) -> dict:
    """The Bayes rate at one body under the generator exactly, with no fitting: given the patient's
    size s, each measure of a body at level i is normal with mean s mu and variance s^2 sd^2 plus
    the error's, independent of the others at r = 0, so the likelihood of the body under level i is
    the product of those normals integrated over log s, normal with SD scale_sd, by Gauss-Hermite
    quadrature; the level with the largest integrated likelihood wins, every level equally likely
    beforehand. The generator's floor at 0.5 mm is the one thing left out. This is the ceiling no
    classifier of one body can pass, and the quadratic rule from the draw's moments is held to it."""
    x, w = np.polynomial.hermite.hermgauss(n_nodes)
    sizes = np.exp(math.sqrt(2.0) * synth["scale_sd"] * x)
    logw = np.log(w / math.sqrt(math.pi))
    mu = np.array([[ref[m][lv][0] for m in measures] for lv in CLASSES])
    sd = np.array([[ref[m][lv][1] for m in measures] for lv in CLASSES])
    noise2 = synth["noise_mm"] ** 2
    V = np.array([[col.values[m][c] for m in measures] for col in sco_cols for c in range(K)])
    truth = np.array([c for _ in sco_cols for c in range(K)])
    groups = np.array([g for g in range(len(sco_cols)) for _ in range(K)])
    logp = np.zeros((len(V), K))
    for i in range(K):
        acc = np.full((len(V), n_nodes), -np.inf)
        for k, s in enumerate(sizes):
            var = s * s * sd[i] ** 2 + noise2
            acc[:, k] = logw[k] - 0.5 * np.sum((V - s * mu[i]) ** 2 / var + np.log(2 * math.pi * var), axis=1)
        top = acc.max(1, keepdims=True)
        logp[:, i] = top[:, 0] + np.log(np.exp(acc - top).sum(1))
    call = logp.argmax(1)
    hit = (call == truth).astype(float)
    out = {"n_nodes": n_nodes, "n_bodies": int(len(V)), "exact": float(hit.mean()),
           "se_cluster": NB.clustered_se(hit, groups), "within_one": float((np.abs(call - truth) <= 1).mean()),
           "recall_by_level": {}, "precision_by_level": {}}
    for i, lv in enumerate(CLASSES):
        called = call == i
        out["recall_by_level"][lv] = float(hit[truth == i].mean())
        out["precision_by_level"][lv] = float((truth[called] == i).mean()) if called.any() else float("nan")
    return out


def table_study(n_fit: int, n_select: int, n_score: int, n_moments: int, halves=(0, 2)) -> dict:
    """The synthetic data's own ceiling: the seven SPINEPS measures with the table's pedicle rows
    added, which the segmenter cannot read, so that the owner sees what the table holds beyond
    what is measurable. The isolation at one body from a draw with the nine measures, and C on the
    field at the given widths, columns drawn afresh with the nine measures on the same seeds."""
    measures = list(MEASURES_TABLE)
    ref = P.load_reference(measures=measures)
    constant = NB.external_constant(ref, measures)
    synth = dict(NB.SYNTH)
    M, S = level_moments_empirical(ref, measures, constant, synth, n_moments, 5)
    near = nearest_rivals(mahalanobis_matrix(M, S))
    fit_cols = NB.draw_columns(ref, ("typical",), NB.FIT_SEED, n_fit, measures)
    sel_cols = NB.draw_columns(ref, ("typical",), NB.SELECT_SEED, n_select, measures)
    sco_cols = NB.draw_columns(ref, ("typical",), NB.SCORE_SEED, n_score, measures)
    cells = [cell(ref, "table", h, fit_cols, sel_cols, sco_cols, constant, False, measures=measures) for h in halves]
    return {"measures": measures, "extra": list(TABLE_EXTRA),
            "note": "the pedicle rows are Panjabi's PDW and PDH; no SPINEPS label gives them",
            "isolation_size_unknown": near, "cells": cells}


def r_sweep(ref, constant, n_fit: int, n_score: int, grid=R_GRID, halves=(0, 2)) -> dict:
    measures = NB.REGIMES["both"]
    out = {"grid": list(grid), "halves": list(halves), "cells": [], "identified_by_level": {}}
    for half in halves:
        offs = NM.field_offsets(half, True)
        levels = [int(c) for c in NM.candidates(offs)]
        per_r = []
        for r in grid:
            fit_cols = NB.draw_columns(ref, ("typical",), NB.FIT_SEED, n_fit, measures, r_between=r)
            sco_cols = NB.draw_columns(ref, ("typical",), NB.SCORE_SEED, n_score, measures, r_between=r)
            fit = NM.field_rows(fit_cols, offs, measures, constant)
            sco = NM.field_rows(sco_cols, offs, measures, constant)
            model = NB.train_softmax(fit, "field", measures)
            prob = model.probabilities(sco.X)
            table, _ = level_table(prob, sco, levels)
            hit = (prob.argmax(1) == sco.y).astype(float)
            row = {"half": half, "visible_bodies": len(offs), "r": r, "acc": float(hit.mean()),
                   "se": NB.clustered_se(hit, sco.group), "recall_by_level": {lv: table[lv]["recall"] for lv in table}}
            out["cells"].append(row)
            per_r.append(row)
        out["identified_by_level"][str(half)] = {
            lv: {"lo": min(x["recall_by_level"][lv] for x in per_r), "hi": max(x["recall_by_level"][lv] for x in per_r)}
            for lv in per_r[0]["recall_by_level"]}
        out["identified_by_level"][str(half)]["overall"] = CV.identified_set(per_r)
    return out


# ---- the run -------------------------------------------------------------------------------------

def ranked(d: Dict[str, float], reverse: bool = True) -> List[str]:
    return sorted(d, key=lambda lv: d[lv], reverse=reverse)


def run(outdir: Optional[str] = None, n_fit: int = N_FIT, n_select: int = N_SELECT, n_score: int = N_SCORE,
        quick: bool = False) -> dict:
    t_start = time.perf_counter()
    ref = P.load_reference(measures=MEASURES7)
    constant = NB.external_constant(ref, MEASURES7)
    synth = dict(NB.SYNTH)
    halves = list(HALVES)
    det_halves = list(DETECTOR_HALVES)
    n_cov, n_boot = N_MOMENTS, N_BOOTSTRAP
    if quick:
        n_fit, n_select, n_score, n_cov, n_boot = min(n_fit, 80), min(n_select, 40), min(n_score, 60), 300, 20
        halves, det_halves = [0, 1], [0]
    rec = {"study": "which vertebrae of a normal spine can be identified best, and by what (Kunkel 2010 framing)",
           "phenotype": "typical", "synth": dict(synth, r_between=0.0), "measures": MEASURES7,
           "regimes": {k: list(v) for k, v in NB.REGIMES.items()},
           "seeds": {"fit": NB.FIT_SEED, "select": NB.SELECT_SEED, "score": NB.SCORE_SEED},
           "n_columns": {"fit_typical": n_fit, "select_typical": n_select, "score_typical": n_score},
           "halves": halves, "detector_halves": det_halves, "precision_targets": list(PRECISION_TARGETS),
           "classes": CLASSES, "kunkel_levels": KUNKEL_LEVELS, "external_constant": constant,
           "python": sys.version.split()[0], "numpy": np.__version__}
    print("identify: typical columns only; %d fit, %d selection, %d scoring" % (n_fit, n_select, n_score))

    rec["kunkel"] = kunkel_fits(ref)
    e = rec["kunkel"]["measures"]["endplate"]
    print("  Kunkel's EPWS on VBHP refitted: linear R2 %.3f (stated %.2f), cubic R2 %.3f (stated %.2f)"
          % (e["linear_16"]["r2"], KUNKEL_LINEAR_EPWS[2], e["cubic_16"]["r2"], KUNKEL_CUBIC_R2_EPWS))
    rec["one_measure"] = {m: {"all_22": one_measure_isolation(ref, m, P.LEVELS, synth["noise_mm"], synth["scale_sd"])}
                          for m in MEASURES7}
    rec["one_measure"]["h_post"]["kunkel_16"] = one_measure_isolation(ref, "h_post", KUNKEL_LEVELS, synth["noise_mm"], synth["scale_sd"])
    t12 = rec["one_measure"]["h_post"]
    print("  along VBHP alone, T12's nearest rival: %s at %.1f mm (%.2f body SD) over 22 levels; %s at %.1f mm (%.2f) over Kunkel's 16"
          % (t12["all_22"]["T12"]["rival"], t12["all_22"]["T12"]["gap_mm"], t12["all_22"]["T12"]["gap_body_sd"],
             t12["kunkel_16"]["T12"]["rival"], t12["kunkel_16"]["T12"]["gap_mm"], t12["kunkel_16"]["T12"]["gap_body_sd"]))

    rec["isolation"] = {regime: isolation(ref, NB.REGIMES[regime], constant, synth, n_cov) for regime in NB.REGIMES}
    rec["isolation_analytic"] = isolation_analytic(ref, MEASURES7, constant, synth)
    rec["isolation_in_r"] = isolation_in_r(ref, MEASURES7, constant, synth)
    rec["field_isolation"] = [field_isolation(ref, MEASURES7, constant, synth, h) for h in halves]
    rec["table_bootstrap"] = table_bootstrap(ref, MEASURES7, constant, synth, n_boot)
    M, S = level_moments_empirical(ref, MEASURES7, constant, synth, n_cov, 5)
    rec["subsets"] = subset_isolation(M, S)
    rec["covariance_check"] = covariance_check(ref, MEASURES7, constant, synth, n_cov)
    tb = rec["table_bootstrap"]["by_level"]
    print("  the table's own sampling error: most isolated along VBHP in %.0f%% of draws %s; in seven measures %s"
          % (100 * max(tb[lv]["most_isolated_h_post"] for lv in tb), max(tb, key=lambda lv: tb[lv]["most_isolated_h_post"]),
             ", ".join("%s %.0f%%" % (lv, 100 * tb[lv]["most_isolated_7"]) for lv in sorted(tb, key=lambda lv: -tb[lv]["most_isolated_7"])[:3])))
    near = rec["isolation"]["both"]["size_unknown"]["nearest"]
    top = ranked({lv: near[lv]["d"] for lv in near})
    cc = rec["covariance_check"]
    print("  isolation, seven measures, size unknown: most isolated %s; least %s; the formula's worst variance %.2f off at %s %s (cv %.2f)"
          % (", ".join("%s %.2f" % (lv, near[lv]["d"]) for lv in top[:5]),
             ", ".join("%s %.2f" % (lv, near[lv]["d"]) for lv in top[-3:]),
             cc["worst_variance"]["relative_error_variance"], cc["worst_variance"]["level"], cc["worst_variance"]["measure"],
             cc["worst_variance"]["cv"]))

    fit_cols = NB.draw_columns(ref, ("typical",), NB.FIT_SEED, n_fit, MEASURES7)
    sel_cols = NB.draw_columns(ref, ("typical",), NB.SELECT_SEED, n_select, MEASURES7)
    sco_cols = NB.draw_columns(ref, ("typical",), NB.SCORE_SEED, n_score, MEASURES7)
    rec["cells"] = []
    for regime in NB.REGIMES:
        for half in halves:
            c = cell(ref, regime, half, fit_cols, sel_cols, sco_cols, constant, with_detectors=(regime == "both" and half in det_halves))
            rec["cells"].append(c)
            rec_by = {lv: c["by_level"][lv]["recall"] for lv in c["by_level"]}
            best = ranked(rec_by)[:4]
            kept = {lv: c["abstain"][lv]["0.95"]["kept"] for lv in c["abstain"]}
            print("  %-8s %d bodies: exact %.3f; best recall %s; most kept at 95%% precision %s; shuffle %d/%d; fit %.1f s"
                  % (regime, len(c["offsets"]), c["exact"],
                     ", ".join("%s %.2f" % (lv, rec_by[lv]) for lv in best),
                     ", ".join("%s %.2f" % (lv, kept[lv]) for lv in ranked(kept)[:3]),
                     c["shuffle"]["identical"], c["shuffle"]["trials"], c["fit_seconds"]))
    rec["axes"] = axes_study(ref, constant, fit_cols, sco_cols)
    for name, v in rec["axes"].items():
        print("  one body along %-16s exact %.3f; best recall %s" % (name, v["exact"],
              ", ".join("%s %.2f" % (lv, v["recall_by_level"][lv]) for lv in ranked(v["recall_by_level"])[:4])))
    rec["bayes"] = {"quadratic_from_moments": bayes_study(ref, constant, synth, sco_cols, n_cov),
                    "exact_likelihood": bayes_exact_one_body(ref, MEASURES7, synth, sco_cols)}
    print("  one body, the ceiling: exact likelihood %.3f, the quadratic rule from the draw's moments %.3f"
          % (rec["bayes"]["exact_likelihood"]["exact"], rec["bayes"]["quadratic_from_moments"]["exact"]))
    rec["table"] = table_study(n_fit, n_select, n_score, n_cov, halves=(0, 2) if not quick else (0,))
    for c in rec["table"]["cells"]:
        rec_by = {lv: c["by_level"][lv]["recall"] for lv in c["by_level"]}
        print("  with the table's pedicle rows, %d bodies: exact %.3f; best recall %s"
              % (len(c["offsets"]), c["exact"], ", ".join("%s %.2f" % (lv, rec_by[lv]) for lv in ranked(rec_by)[:4])))
    rec["size"] = size_study(ref, constant, n_fit, n_score, halves=(0, 2) if not quick else (0,))
    for v in rec["size"]["variants"]:
        print("  size: %d bodies, scale_sd %.2f, %-15s exact %.3f" % (v["visible_bodies"], v["scale_sd"], v["features"], v["exact"]))
    rec["r_sweep"] = r_sweep(ref, constant, n_fit, n_score, halves=(0, 2) if not quick else (0,))
    for row in rec["r_sweep"]["cells"]:
        print("  r %.1f, %d bodies: exact %.3f" % (row["r"], row["visible_bodies"], row["acc"]))
    rec["seconds"] = time.perf_counter() - t_start
    print("identify: %.0f s" % rec["seconds"])
    if outdir:
        os.makedirs(outdir, exist_ok=True)
        path = os.path.join(outdir, "identify.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rec, fh, indent=1, sort_keys=True, default=NB._jsonable)
        print("wrote %s" % path)
    return rec
