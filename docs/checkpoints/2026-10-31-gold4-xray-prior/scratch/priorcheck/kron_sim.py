#!/usr/bin/env python3
"""Does the Kronecker flip-flop MLE of the gold tier 3 correlation prior understate the
same-level cross-measure correlation when the truth is not separable?

Scratch study for the thread on the prior of bordercall records/prior-2026-10-31 (job 40902475).
Nothing here reads a morphometry row: the rows are on the grid only. Every truth below is
simulated; the only real numbers used are the published aggregates (the four prior JSON files and
the report's held-out gains).

The fit's math (to_correlation, standardise, complete, flip_flop, shrunk, fit, assumed_cov,
mvn_loglik) is copied verbatim from SchwingNet grid/prior/schwingcheck/correlation.py (vendored
from bordercall schwingcheck/correlation.py; bordercall main 2cc9971 holds the same functions);
`check_copy` reads that file as text and fails if any copied function differs. The repository is
not imported.

Run:  python3 kron_sim.py all        (or one part: sanity, forward, matched, heldout, grid, phantom)
Writes results-<part>.json beside this script.
"""
from __future__ import annotations

import inspect
import json
import math
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

HERE = "/tmp/claude-0/-home-claude/3a9f8f67-4b49-5dd0-98ba-d0bd1c4358ce/scratchpad/priorcheck"
PRIOR_DIR = "/home/claude/bordercall/records/prior-2026-10-31"
VENDORED_SOURCE = "/home/claude/SchwingNet/grid/prior/schwingcheck/correlation.py"

LEVELS_C2 = ["C%d" % i for i in range(2, 8)] + ["T%d" % i for i in range(1, 13)] + ["L%d" % i for i in range(1, 6)]
LEVELS = LEVELS_C2[1:]                      # C3..L5, 22
MEASURES = ["endplate", "endplate_depth", "endplate_lower", "endplate_lower_depth", "h_post"]
SHORT = ["EPWu", "EPDu", "EPWl", "EPDl", "VBHp"]
EP, EPD, EPL, EPLD, HP = range(5)
L, M = len(LEVELS), len(MEASURES)
T1_AT = LEVELS.index("T1")                  # 5: T1..L5 is LEVELS[5:]
CERV = list(range(0, T1_AT))                # C3..C7
SHRINK = 0.05

# ---------------------------------------------------------------------------------------------
# Copied verbatim from grid/prior/schwingcheck/correlation.py (SchwingNet 59ef820 / bordercall 2cc9971)
# ---------------------------------------------------------------------------------------------

FLIP_FLOP_STEPS = 100
FLIP_FLOP_TOL = 1e-9


@dataclass
class Prior:
    levels: List[str]
    measures: List[str]
    r_level: np.ndarray
    r_measure: np.ndarray
    n: int = 0
    shrink: float = 0.0
    note: str = ""


def to_correlation(cov: np.ndarray) -> np.ndarray:
    d = np.sqrt(np.diag(cov))
    r = cov / np.outer(d, d)
    np.fill_diagonal(r, 1.0)
    return (r + r.T) / 2


def standardise(values: np.ndarray, mean: Optional[np.ndarray] = None,
                sd: Optional[np.ndarray] = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """values (spines, levels, measures) to z scores by each cell's mean and SD, the training
    spines' own where none are given."""
    if mean is None:
        mean = np.nanmean(values, axis=0)
    if sd is None:
        sd = np.nanstd(values, axis=0, ddof=1)
    if np.any(~np.isfinite(sd)) or np.any(sd <= 0):
        raise ValueError("every cell needs a positive SD; a cell with one value or none has none")
    return (values - mean) / sd, mean, sd


def complete(values: np.ndarray) -> np.ndarray:
    keep = np.isfinite(values).all(axis=(1, 2))
    return values[keep]


def flip_flop(z: np.ndarray, steps: int = FLIP_FLOP_STEPS, tol: float = FLIP_FLOP_TOL) -> Tuple[np.ndarray, np.ndarray]:
    """The maximum likelihood row and column covariances of a zero-mean matrix normal sample
    z (n, L, M), Dutilleul's alternation; returned as correlations, which is all the product
    identifies once the margins are fixed."""
    n, L, M = z.shape
    if n * M <= L or n * L <= M:
        raise ValueError("%d complete spines are too few for %d levels and %d measures" % (n, L, M))
    sl, sm = np.eye(L), np.eye(M)
    for _ in range(steps):
        im = np.linalg.inv(sm)
        sl_new = np.einsum("nlm,mk,njk->lj", z, im, z) / (n * M)
        il = np.linalg.inv(sl_new)
        sm_new = np.einsum("nlm,lk,nkj->mj", z, il, z) / (n * L)
        done = np.abs(sl_new - sl).max() < tol and np.abs(sm_new - sm).max() < tol
        sl, sm = sl_new, sm_new
        if done:
            break
    return to_correlation(sl), to_correlation(sm)


def shrunk(r: np.ndarray, share: float) -> np.ndarray:
    return (1 - share) * r + share * np.eye(len(r))


def fit(values: np.ndarray, levels: Sequence[str], measures: Sequence[str], shrink: float = 0.05,
        note: str = "") -> Prior:
    """The prior from whole spines, values (spines, levels, measures) with NaN where missing;
    only spines with every cell are used."""
    whole = complete(values)
    z, _, _ = standardise(whole)
    rl, rm = flip_flop(z)
    return Prior(list(levels), list(measures), shrunk(rl, shrink), shrunk(rm, shrink), n=len(whole),
                 shrink=shrink, note=note)


def assumed_cov(L: int, M: int, rho: float = 0.5, r_between: float = 0.0) -> np.ndarray:
    """The generator's own correlation of one spine's standardised values, levels-major as
    vec(X): rho * z[m] + sqrt(1 - rho^2) * e[m, l] gives rho^2 * C_z[m, m'] between any two
    cells and 1 on the diagonal, C_z the exchangeable correlation at r_between."""
    cz = np.full((M, M), r_between)
    np.fill_diagonal(cz, 1.0)
    cov = rho * rho * np.kron(np.ones((L, L)), cz)
    cov += (1 - rho * rho) * np.eye(L * M)
    return cov


def mvn_loglik(z: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """Log density of each spine's vec(z) under N(0, cov); z (n, L, M)."""
    n = len(z)
    x = z.reshape(n, -1)
    chol = np.linalg.cholesky(cov)
    sol = np.linalg.solve(chol, x.T)
    logdet = 2 * np.log(np.diag(chol)).sum()
    return -0.5 * (x.shape[1] * math.log(2 * math.pi) + logdet + (sol * sol).sum(axis=0))


COPIED = [to_correlation, standardise, complete, flip_flop, shrunk, fit, assumed_cov, mvn_loglik]


def check_copy() -> dict:
    """Each copied function's source must appear, character for character, in the vendored file."""
    text = open(VENDORED_SOURCE).read()
    out = {}
    for f in COPIED:
        out[f.__name__] = inspect.getsource(f) in text
    out["FLIP_FLOP_STEPS = 100"] = "FLIP_FLOP_STEPS = 100" in text
    out["FLIP_FLOP_TOL = 1e-9"] = "FLIP_FLOP_TOL = 1e-9" in text
    return out

# ---------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------


def cell(l: int, m: int) -> int:
    """levels-major index of vec(X), as correlation.py's reshape(n, -1) lays it out"""
    return l * M + m


def load_prior(population: str, levels: str) -> Prior:
    d = json.load(open("%s/prior-%s-%s.json" % (PRIOR_DIR, population, levels)))
    return Prior(d["levels"], d["measures"], np.array(d["r_level"], float), np.array(d["r_measure"], float),
                 n=int(d["n"]), shrink=float(d["shrink"]), note=d["note"])


def unshrink(r: np.ndarray, share: float = SHRINK) -> np.ndarray:
    u = (r - share * np.eye(len(r))) / (1 - share)
    np.fill_diagonal(u, 1.0)
    return u


def lag_profile(r: np.ndarray, kmax: int = 5) -> List[float]:
    return [float(np.mean(np.diag(r, k))) for k in range(1, kmax + 1)]


def chol_psd(k: np.ndarray) -> np.ndarray:
    w, v = np.linalg.eigh((k + k.T) / 2)
    return v * np.sqrt(np.clip(w, 0, None))


def ar_kernel(n: int, phi: float, floor: float = 0.0) -> np.ndarray:
    idx = np.arange(n)
    return floor + (1 - floor) * phi ** np.abs(idx[:, None] - idx[None, :])


def kron_cov(rl: np.ndarray, rm: np.ndarray) -> np.ndarray:
    return np.kron(rl, rm)


def sub_levels(sigma: np.ndarray, keep: Sequence[int], m: int = M) -> np.ndarray:
    idx = np.array([cell(l, k) for l in keep for k in range(m)])
    return sigma[np.ix_(idx, idx)]

# ---------------------------------------------------------------------------------------------
# the population limit of the fit: the flip-flop run on a known covariance (n -> infinity),
# which is the Kronecker product nearest the truth in Kullback-Leibler divergence
# ---------------------------------------------------------------------------------------------


def project(sigma: np.ndarray, nl: int, nm: int = M, steps: int = 5000, tol: float = 1e-12,
            start: Optional[Tuple[np.ndarray, np.ndarray]] = None) -> Tuple[np.ndarray, np.ndarray, int]:
    s4 = sigma.reshape(nl, nm, nl, nm)
    sl, sm = (np.eye(nl), np.eye(nm)) if start is None else start
    used = steps
    for i in range(steps):
        im = np.linalg.inv(sm)
        sl_new = np.einsum("lmjk,mk->lj", s4, im) / nm
        il = np.linalg.inv(sl_new)
        sm_new = np.einsum("lmkj,lk->mj", s4, il) / nl
        done = np.abs(sl_new - sl).max() < tol and np.abs(sm_new - sm).max() < tol
        sl, sm = sl_new, sm_new
        if done:
            used = i + 1
            break
    return to_correlation(sl), to_correlation(sm), used


def projected_prior(sigma: np.ndarray, nl: int = L, shrink: float = SHRINK) -> Tuple[np.ndarray, np.ndarray]:
    rl, rm, _ = project(sigma, nl)
    return shrunk(rl, shrink), shrunk(rm, shrink)

# ---------------------------------------------------------------------------------------------
# truths: z = Lambda f + sqrt(psi) e, f ~ N(0, I), every cell scaled to unit variance
# ---------------------------------------------------------------------------------------------


@dataclass
class Truth:
    name: str
    lam: np.ndarray                 # (L*M, F)
    psi: np.ndarray                 # (L*M,) noise variance, after scaling
    noise: str = "gauss"            # gauss, or t<df>
    outlier: str = ""               # "", "cell" or "vertebra"
    outlier_p: float = 0.0
    outlier_sd: float = 0.0
    note: str = ""

    def sigma(self) -> np.ndarray:
        """the clean correlation of the cells (what the anatomy plus ordinary noise gives)"""
        s = self.lam @ self.lam.T + np.diag(self.psi)
        return to_correlation(s)

    def sigma_observed(self) -> np.ndarray:
        """the correlation of what a Pearson estimate sees, gross outliers included"""
        s = self.lam @ self.lam.T + np.diag(self.psi)
        if self.outlier == "cell":
            s = s + self.outlier_p * self.outlier_sd ** 2 * np.eye(L * M)
        elif self.outlier == "vertebra":
            s = s + self.outlier_p * self.outlier_sd ** 2 * np.kron(np.eye(L), np.ones((M, M)))
        elif self.outlier == "spine":
            s = s + self.outlier_p * self.outlier_sd ** 2 * np.ones((L * M, L * M))
        return to_correlation(s)

    def sample(self, rng: np.random.Generator, n: int) -> np.ndarray:
        f = rng.standard_normal((n, self.lam.shape[1]))
        x = f @ self.lam.T
        if self.noise.startswith("t"):
            df = float(self.noise[1:])
            e = rng.standard_t(df, size=(n, L * M)) / math.sqrt(df / (df - 2))
        else:
            e = rng.standard_normal((n, L * M))
        x = x + e * np.sqrt(self.psi)
        if self.outlier == "cell":
            hit = rng.random((n, L * M)) < self.outlier_p
            x = x + hit * rng.normal(0, self.outlier_sd, (n, L * M))
        elif self.outlier == "vertebra":
            hit = rng.random((n, L)) < self.outlier_p
            shift = rng.normal(0, self.outlier_sd, (n, L)) * hit
            x = x + np.repeat(shift, M, axis=1)
        elif self.outlier == "spine":
            hit = rng.random(n) < self.outlier_p
            x = x + (rng.normal(0, self.outlier_sd, n) * hit)[:, None]
        return x.reshape(n, L, M)


def scaled(name: str, cols: List[np.ndarray], psi: np.ndarray, **kw) -> Truth:
    lam = np.concatenate(cols, axis=1) if cols else np.zeros((L * M, 0))
    var = (lam * lam).sum(axis=1) + psi
    lam = lam / np.sqrt(var)[:, None]
    return Truth(name=name, lam=lam, psi=psi / var, **kw)


def comp_global(a: Sequence[float]) -> np.ndarray:
    col = np.zeros((L * M, 1))
    for l in range(L):
        for m in range(M):
            col[cell(l, m), 0] = a[m]
    return col


def comp_measure_fields(b: Sequence[float], k: np.ndarray) -> np.ndarray:
    c = chol_psd(k)
    cols = np.zeros((L * M, M * L))
    for m in range(M):
        for l in range(L):
            cols[cell(l, m), m * L:(m + 1) * L] = b[m] * c[l]
    return cols


def comp_vertebra(c: Sequence[float], k: Optional[np.ndarray] = None, levels: Optional[Sequence[int]] = None) -> np.ndarray:
    """one person factor per level shared by the measures loading on it (c[m]); k its level kernel"""
    ch = np.eye(L) if k is None else chol_psd(k)
    cols = np.zeros((L * M, L))
    at = range(L) if levels is None else levels
    for l in at:
        for m in range(M):
            cols[cell(l, m)] = c[m] * ch[l]
    return cols


def comp_disc(kw: float, kd: float) -> np.ndarray:
    """one factor per disc for the facing end plates: level l's lower and level l+1's upper"""
    cols = np.zeros((L * M, 2 * (L - 1)))
    for l in range(L - 1):
        cols[cell(l, EPL), 2 * l] = kw
        cols[cell(l + 1, EP), 2 * l] = kw
        cols[cell(l, EPLD), 2 * l + 1] = kd
        cols[cell(l + 1, EPD), 2 * l + 1] = kd
    return cols

# ---------------------------------------------------------------------------------------------
# statistics of a correlation matrix (truth) and of a fitted prior
# ---------------------------------------------------------------------------------------------

PAIRS = {"widths": (EP, EPL), "depths": (EPD, EPLD), "width_depth_upper": (EP, EPD),
         "width_depth_lower": (EPL, EPLD), "upperW_lowerD": (EP, EPLD), "upperD_lowerW": (EPD, EPL)}


def same_level(sigma: np.ndarray, levels: Optional[Sequence[int]] = None) -> np.ndarray:
    at = range(L) if levels is None else levels
    blocks = [sigma[l * M:(l + 1) * M, l * M:(l + 1) * M] for l in at]
    return np.mean(blocks, axis=0)


def truth_stats(sigma: np.ndarray, nl: int = L) -> dict:
    s4 = sigma.reshape(nl, M, nl, M)
    sl = np.mean([s4[l, :, l, :] for l in range(nl)], axis=0)
    out = {"same_level_" + k: float(sl[a, b]) for k, (a, b) in PAIRS.items()}
    out["same_level_hpost_mean"] = float(np.mean([sl[HP, m] for m in range(4)]))
    out["same_level_wd4_mean"] = float(np.mean([sl[a, b] for a in range(4) for b in range(a + 1, 4)]))
    lag_same = []
    for k in range(1, 6):
        lag_same.append(float(np.mean([s4[l, m, l + k, m] for l in range(nl - k) for m in range(M)])))
    out["lag_same_measure"] = lag_same
    out["lag_same_measure_wd4"] = [float(np.mean([s4[l, m, l + k, m] for l in range(nl - k) for m in range(4)]))
                                   for k in range(1, 6)]
    out["lag_same_measure_hpost"] = [float(np.mean([s4[l, HP, l + k, HP] for l in range(nl - k)])) for k in range(1, 6)]
    cross1 = [s4[l, m, l + 1, mm] for l in range(nl - 1) for m in range(M) for mm in range(M) if m != mm]
    out["lag1_cross_measure_all"] = float(np.mean(cross1))
    disc = {(EPL, EP), (EPLD, EPD)}
    nondisc = [s4[l, m, l + 1, mm] for l in range(nl - 1) for m in range(4) for mm in range(4)
               if m != mm and (m, mm) not in disc]
    out["lag1_cross_wd4_not_facing"] = float(np.mean(nondisc))
    out["disc_widths"] = float(np.mean([s4[l, EPL, l + 1, EP] for l in range(nl - 1)]))
    out["disc_depths"] = float(np.mean([s4[l, EPLD, l + 1, EPD] for l in range(nl - 1)]))
    out["lag1_upperW_to_next_lowerW"] = float(np.mean([s4[l, EP, l + 1, EPL] for l in range(nl - 1)]))
    out["lag5_cross_wd4"] = float(np.mean([s4[l, m, l + 5, mm] for l in range(nl - 5) for m in range(4)
                                           for mm in range(4) if m != mm]))
    return out


def prior_stats(rl: np.ndarray, rm: np.ndarray) -> dict:
    out = {"R_measure_" + k: float(rm[a, b]) for k, (a, b) in PAIRS.items()}
    out["R_measure_hpost_mean"] = float(np.mean([rm[HP, m] for m in range(4)]))
    out["R_measure_wd4_mean"] = float(np.mean([rm[a, b] for a in range(4) for b in range(a + 1, 4)]))
    out["R_level_lag"] = lag_profile(rl)
    k = kron_cov(rl, rm)
    implied = truth_stats(k, len(rl))
    out["implied_disc_widths"] = implied["disc_widths"]
    out["implied_lag1_cross_all"] = implied["lag1_cross_measure_all"]
    return out


def observed_targets() -> dict:
    e = load_prior("enhance_pet", "C3-L5")
    e2 = load_prior("enhance_pet", "T1-L5")
    t = load_prior("totalsegmentator", "C3-L5")
    t2 = load_prior("totalsegmentator", "T1-L5")
    return {"enhance_C3L5": e, "enhance_T1L5": e2, "totalseg_C3L5": t, "totalseg_T1L5": t2}

# ---------------------------------------------------------------------------------------------
# fitting simulated spines exactly as the grid did
# ---------------------------------------------------------------------------------------------


def grid_fit(values: np.ndarray, levels: Sequence[str] = LEVELS) -> Tuple[np.ndarray, np.ndarray]:
    p = fit(values, levels, MEASURES, SHRINK)
    return p.r_level, p.r_measure


def summarize(xs: List[dict]) -> dict:
    """mean and SD over replicates of every scalar or list entry"""
    out = {}
    for k in xs[0]:
        a = np.array([x[k] for x in xs], float)
        out[k] = {"mean": np.round(a.mean(axis=0), 4).tolist(), "sd": np.round(a.std(axis=0, ddof=1), 4).tolist()}
    return out


def fit_reps(truth: Truth, n: int, reps: int, seed: int, also_t1: bool = False) -> dict:
    rng = np.random.default_rng(seed)
    rows, rows_t1, diffs = [], [], []
    for _ in range(reps):
        v = truth.sample(rng, n)
        rl, rm = grid_fit(v)
        rows.append(prior_stats(rl, rm))
        if also_t1:
            rl2, rm2 = grid_fit(v[:, T1_AT:, :], LEVELS[T1_AT:])
            rows_t1.append(prior_stats(rl2, rm2))
            diffs.append({"widths": float(rm2[EP, EPL] - rm[EP, EPL]), "depths": float(rm2[EPD, EPLD] - rm[EPD, EPLD]),
                          "width_depth_upper": float(rm2[EP, EPD] - rm[EP, EPD])})
    out = {"n": n, "reps": reps, "fit": summarize(rows)}
    if also_t1:
        out["fit_T1L5"] = summarize(rows_t1)
        out["T1L5_minus_C3L5"] = summarize(diffs)
    return out

# ---------------------------------------------------------------------------------------------
# alternatives for held-out scoring
# ---------------------------------------------------------------------------------------------


def corr_of(z: np.ndarray) -> np.ndarray:
    x = z.reshape(len(z), -1)
    return to_correlation(x.T @ x / len(x))


def shrink_cv(z: np.ndarray, target: str, grid=(0.02, 0.05, 0.1, 0.2, 0.3, 0.45, 0.6, 0.8, 0.9, 0.95, 1.0), folds: int = 5,
              seed: int = 0) -> float:
    """the share toward the target (identity, or the Kronecker fit of the training folds)
    that scores the held folds best"""
    n = len(z)
    rng = np.random.default_rng(seed)
    order = rng.permutation(n)
    parts = np.array_split(order, folds)
    scores = np.zeros(len(grid))
    for f in range(folds):
        test = parts[f]
        train = np.concatenate([parts[g] for g in range(folds) if g != f])
        zt = z[train]
        s = corr_of(zt)
        if target == "kron":
            rl, rm = flip_flop(zt)
            t = np.kron(shrunk(rl, SHRINK), shrunk(rm, SHRINK))
        else:
            t = np.eye(z.shape[1] * z.shape[2])
        for i, lam in enumerate(grid):
            c = (1 - lam) * s + lam * t
            try:
                scores[i] += mvn_loglik(z[test], c).sum()
            except np.linalg.LinAlgError:
                scores[i] += -np.inf
    return float(grid[int(np.argmax(scores))])


def fit_kw(z: np.ndarray, iters: int = 400, tol: float = 1e-7) -> Tuple[np.ndarray, dict]:
    """Kronecker plus a within-vertebra term, Sigma = A kron B + I_L kron W, by EM (one flip-flop
    sweep per M step); returns the fitted correlation and its parts"""
    n, nl, nm = z.shape
    x = z.reshape(n, -1)
    s = x.T @ x / n
    rl, rm = flip_flop(z)
    a, b, w = rl.copy(), 0.8 * rm, 0.2 * np.eye(nm)
    last = -np.inf
    eye_l = np.eye(nl)
    for it in range(iters):
        kx = np.kron(a, b)
        ky = np.kron(eye_l, w)
        sig = kx + ky
        si = np.linalg.inv(sig)
        sign, logdet = np.linalg.slogdet(sig)
        ll = -0.5 * n * (logdet + np.trace(si @ s))
        if ll - last < tol * abs(ll) and it > 5:
            break
        last = ll
        sx = kx @ si @ s @ si @ kx + kx - kx @ si @ kx
        sy = ky @ si @ s @ si @ ky + ky - ky @ si @ ky
        sx4 = sx.reshape(nl, nm, nl, nm)
        for _ in range(2):
            a = np.einsum("lmjk,mk->lj", sx4, np.linalg.inv(b)) / nm
            b = np.einsum("lmkj,lk->mj", sx4, np.linalg.inv(a)) / nl
        sy4 = sy.reshape(nl, nm, nl, nm)
        w = np.mean([sy4[l, :, l, :] for l in range(nl)], axis=0)
        w = (w + w.T) / 2
    sig = np.kron(a, b) + np.kron(eye_l, w)
    corr = to_correlation(sig)
    da = np.sqrt(np.diag(a))
    parts = {"iters": it + 1, "W_over_total_diag": float(np.mean(np.diag(w)) / np.mean(np.diag(sig))),
             "B_corr": to_correlation(b).round(3).tolist(), "W_corr": to_correlation(w).round(3).tolist(),
             "A_lag": lag_profile(a / np.outer(da, da))}
    return corr, parts


def heldout(truth: Truth, n_fit: int, n_test: int, reps: int, seed: int, with_kw: bool = True) -> dict:
    """mean held-out log likelihood per spine of each structure minus the Kronecker fit's, all on
    the training spines' cell means and SDs as compare() does"""
    rng = np.random.default_rng(seed)
    rows = []
    for r in range(reps):
        train = truth.sample(rng, n_fit)
        test = truth.sample(rng, n_test)
        rl, rm = grid_fit(train)
        z, mean, sd = standardise(train)
        zt, _, _ = standardise(test, mean, sd)
        kron = np.kron(rl, rm)
        ll_k = mvn_loglik(zt, kron)
        out = {}
        ll_o = mvn_loglik(zt, truth.sigma_observed())
        out["oracle_minus_kron"] = ll_o - ll_k
        ll_a = mvn_loglik(zt, assumed_cov(L, M, 0.5, 0.0))
        out["kron_minus_assumed"] = ll_k - ll_a
        s = corr_of(z)
        lam_i = shrink_cv(z, "identity", seed=r)
        out["unstructured_toI_minus_kron"] = mvn_loglik(zt, (1 - lam_i) * s + lam_i * np.eye(L * M)) - ll_k
        lam_k = shrink_cv(z, "kron", seed=r)
        out["unstructured_toKron_minus_kron"] = mvn_loglik(zt, (1 - lam_k) * s + lam_k * kron) - ll_k
        if with_kw:
            kw, _ = fit_kw(z)
            out["kw_minus_kron"] = mvn_loglik(zt, kw) - ll_k
        row = {}
        for k, v in out.items():
            row[k] = float(v.mean())
            row[k + "_se"] = float(v.std(ddof=1) / math.sqrt(len(v)))
            row[k + "_share_better"] = float((v > 0).mean())
        row["lambda_toI"] = lam_i
        row["lambda_toKron"] = lam_k
        rows.append(row)
    keys = rows[0].keys()
    return {k: {"mean": round(float(np.mean([x[k] for x in rows])), 3),
                "sd_over_reps": round(float(np.std([x[k] for x in rows], ddof=1)), 3) if reps > 1 else None}
            for k in keys}


def population_gain_over_assumed(sigma: np.ndarray, rl: np.ndarray, rm: np.ndarray) -> float:
    """expected held-out log likelihood per spine of the prior minus the assumed structure's,
    n -> infinity, spines drawn from sigma"""
    def expected_ll(c):
        sign, logdet = np.linalg.slogdet(c)
        return -0.5 * (len(c) * math.log(2 * math.pi) + logdet + np.trace(np.linalg.solve(c, sigma)))
    return expected_ll(np.kron(rl, rm)) - expected_ll(assumed_cov(len(rl), M, 0.5, 0.0))


def population_kl_gap(sigma: np.ndarray, rl: np.ndarray, rm: np.ndarray) -> float:
    """expected per-spine log likelihood of the truth minus the prior's: the most any better
    structure could gain, n -> infinity"""
    def expected_ll(c):
        sign, logdet = np.linalg.slogdet(c)
        return -0.5 * (len(c) * math.log(2 * math.pi) + logdet + np.trace(np.linalg.solve(c, sigma)))
    return expected_ll(sigma) - expected_ll(np.kron(rl, rm))



# ---------------------------------------------------------------------------------------------
# matched truths: Sigma = (1 - theta) A kron B + theta Delta, the core (A, B) solved so that the
# fit's population limit equals the published C3..L5 prior exactly (both unshrunk)
# ---------------------------------------------------------------------------------------------


def delta_kind(kind: str) -> np.ndarray:
    """a unit-diagonal correlation matrix for one kind of structure a Kronecker product cannot hold"""
    n = L * M
    if kind == "noise":                 # independent error in every cell
        return np.eye(n)
    if kind == "size":                  # one person factor shared by every cell
        return np.ones((n, n))
    if kind == "size_wd":               # one person factor shared by the widths and depths only
        v = np.array([1.0 if m < 4 else 0.0 for l in range(L) for m in range(M)])
        d = np.outer(v, v)
        np.fill_diagonal(d, 1.0)
        return d
    if kind == "vertebra":              # one factor per vertebra shared by its five measures
        return np.kron(np.eye(L), np.ones((M, M)))
    if kind == "vertebra_wd":           # one factor per vertebra shared by its widths and depths
        w = np.eye(M)
        w[:4, :4] = 1.0
        return np.kron(np.eye(L), w)
    if kind == "disc":                  # the facing end plates across each disc move together
        d = np.eye(n)
        for l in range(L - 1):
            for a, b in ((EPL, EP), (EPLD, EPD)):
                i, j = cell(l, a), cell(l + 1, b)
                d[i, j] = d[j, i] = 1.0
        return d
    if kind == "cervical_widths":       # upper and lower width of one cervical vertebra move together
        d = np.eye(n)
        for l in CERV:
            i, j = cell(l, EP), cell(l, EPL)
            d[i, j] = d[j, i] = 1.0
        return d
    raise ValueError(kind)


def match_core(delta: np.ndarray, theta: float, target_l: np.ndarray, target_m: np.ndarray,
               iters: int = 3000, tol: float = 1e-7) -> dict:
    nl = len(target_l)
    a, b = target_l.copy(), target_m.copy()
    eta, err = 1.0, np.inf
    for it in range(iters):
        sig = (1 - theta) * np.kron(a, b) + theta * delta
        pl, pm, _ = project(sig, nl)
        el, em = target_l - pl, target_m - pm
        err = max(np.abs(el).max(), np.abs(em).max())
        if err < tol:
            return {"ok": True, "a": a, "b": b, "sigma": sig, "iters": it, "err": err}
        while True:
            a2, b2 = a + eta * el, b + eta * em
            np.fill_diagonal(a2, 1.0)
            np.fill_diagonal(b2, 1.0)
            if np.linalg.eigvalsh(a2).min() > 1e-4 and np.linalg.eigvalsh(b2).min() > 1e-4 \
                    and np.abs(a2).max() <= 1 and np.abs(b2).max() <= 1:
                break
            eta /= 2
            if eta < 1e-5:
                return {"ok": False, "a": a, "b": b, "sigma": sig, "iters": it, "err": err}
        a, b = a2, b2
        eta = min(1.0, eta * 1.25)
    return {"ok": False, "a": a, "b": b, "sigma": sig, "iters": iters, "err": err}


def max_feasible(delta: np.ndarray, target_l: np.ndarray, target_m: np.ndarray, hi: float = 0.9,
                 steps: int = 12) -> float:
    lo_ok, hi_bad = 0.0, hi
    r = match_core(delta, hi, target_l, target_m)
    if r["ok"]:
        return hi
    for _ in range(steps):
        mid = (lo_ok + hi_bad) / 2
        if match_core(delta, mid, target_l, target_m)["ok"]:
            lo_ok = mid
        else:
            hi_bad = mid
    return lo_ok


def sqrtm_psd(r: np.ndarray) -> np.ndarray:
    w, v = np.linalg.eigh((r + r.T) / 2)
    return (v * np.sqrt(np.clip(w, 0, None))) @ v.T


def regional_sigma(rl: np.ndarray, rm_by_level: List[np.ndarray]) -> np.ndarray:
    """cov((l, m), (l', m')) = rl[l, l'] (S_l S_l'^T)[m, m'], S_l the symmetric root of the measure
    correlation of level l's region: a Kronecker product inside each region, joined across"""
    roots = [sqrtm_psd(r) for r in rm_by_level]
    nl = len(rl)
    sig = np.zeros((nl * M, nl * M))
    for l in range(nl):
        for j in range(nl):
            sig[l * M:(l + 1) * M, j * M:(j + 1) * M] = rl[l, j] * roots[l] @ roots[j].T
    return sig


def match_regional(target_l: np.ndarray, target_m: np.ndarray, rm_thoracolumbar: np.ndarray,
                   iters: int = 4000, tol: float = 1e-7, gain_m: float = 3.0) -> dict:
    """the regional truth whose fit over C3..L5 is the published C3..L5 prior, with the measure
    correlation of T1..L5 held at rm_thoracolumbar and the cervical one solved for"""
    a, bc = target_l.copy(), target_m.copy()
    eta, err = 1.0, np.inf
    for it in range(iters):
        sig = regional_sigma(a, [bc if l in CERV else rm_thoracolumbar for l in range(L)])
        pl, pm, _ = project(sig, L)
        el, em = target_l - pl, target_m - pm
        err = max(np.abs(el).max(), np.abs(em).max())
        if err < tol:
            return {"ok": True, "a": a, "b_cervical": bc, "sigma": sig, "iters": it, "err": err}
        while True:
            a2, b2 = a + eta * el, bc + eta * gain_m * em
            np.fill_diagonal(a2, 1.0)
            np.fill_diagonal(b2, 1.0)
            if np.linalg.eigvalsh(a2).min() > 1e-4 and np.linalg.eigvalsh(b2).min() > 1e-4 \
                    and np.abs(b2).max() <= 1:
                break
            eta /= 2
            if eta < 1e-6:
                return {"ok": False, "a": a, "b_cervical": bc, "sigma": sig, "iters": it, "err": err}
        a, bc = a2, b2
        eta = min(1.0, eta * 1.25)
    return {"ok": False, "a": a, "b_cervical": bc, "sigma": sig, "iters": iters, "err": err}


def match_regional_mixed(target_l: np.ndarray, target_m: np.ndarray, target_m_t1: np.ndarray, delta: np.ndarray,
                         theta: float, iters: int = 4000, tol: float = 1e-7, gain_m: float = 3.0) -> dict:
    """(1 - theta) regional + theta Delta, solved so that the C3..L5 fit's population limit is the
    published C3..L5 prior and the T1..L5 fit's measure correlation is the published T1..L5 one"""
    a, bc, bt = target_l.copy(), target_m.copy(), target_m_t1.copy()
    eta, err = 1.0, np.inf
    t1 = list(range(T1_AT, L))
    for it in range(iters):
        sig = (1 - theta) * regional_sigma(a, [bc if l in CERV else bt for l in range(L)]) + theta * delta
        pl, pm, _ = project(sig, L)
        _, pm1, _ = project(sub_levels(sig, t1), len(t1))
        el, em, em1 = target_l - pl, target_m - pm, target_m_t1 - pm1
        err = max(np.abs(el).max(), np.abs(em).max(), np.abs(em1).max())
        if err < tol:
            return {"ok": True, "a": a, "b_cervical": bc, "b_thoracolumbar": bt, "sigma": sig, "iters": it, "err": err}
        while True:
            a2, b2, b3 = a + eta * el, bc + eta * gain_m * em, bt + eta * em1
            for x in (a2, b2, b3):
                np.fill_diagonal(x, 1.0)
            if min(np.linalg.eigvalsh(x).min() for x in (a2, b2, b3)) > 1e-4 and np.abs(b2).max() <= 1:
                break
            eta /= 2
            if eta < 1e-6:
                return {"ok": False, "a": a, "b_cervical": bc, "b_thoracolumbar": bt, "sigma": sig, "iters": it, "err": err}
        a, bc, bt = a2, b2, b3
        eta = min(1.0, eta * 1.25)
    return {"ok": False, "a": a, "b_cervical": bc, "b_thoracolumbar": bt, "sigma": sig, "iters": iters, "err": err}


def sigma_truth(name: str, sig: np.ndarray, note: str = "") -> Truth:
    """a Gaussian truth with a known correlation"""
    return Truth(name=name, lam=chol_psd(sig), psi=np.zeros(L * M), note=note)


def factor_truth(name: str, a2: float, b2: float, c2: float, disc: float = 0.0, floor: float = 0.4,
                 phi: float = 0.6, flat: bool = False, hp_a2: float = 0.0, hp_c2: float = 0.0, **kw) -> Truth:
    """person size (a2, every cell), a field per measure along the spine (b2; AR(phi) with a floor,
    or flat: one person factor per measure shared by every level), one factor per vertebra shared
    by its measures (c2), the facing end plates across each disc (disc, from the noise of the four
    end-plate measures) and independent noise (the rest); h_post takes hp_a2 and hp_c2"""
    k = np.ones((L, L)) if flat else ar_kernel(L, phi, floor)
    a = [math.sqrt(a2)] * 4 + [math.sqrt(hp_a2)]
    c = [math.sqrt(c2)] * 4 + [math.sqrt(hp_c2)]
    b = [math.sqrt(b2)] * M
    cols = [comp_global(a), comp_measure_fields(b, k), comp_vertebra(c)]
    psi = np.zeros(L * M)
    for l in range(L):
        for m in range(M):
            used = a[m] ** 2 + b[m] ** 2 + c[m] ** 2
            facing = (m == EPL and l < L - 1) or (m == EPLD and l < L - 1) or (m == EP and l > 0) or (m == EPD and l > 0)
            used += disc if facing else 0.0
            if used > 1 + 1e-9:
                raise ValueError("shares above 1 in %s" % name)
            psi[cell(l, m)] = max(1 - used, 1e-6)
    if disc:
        cols.append(comp_disc(math.sqrt(disc), math.sqrt(disc)))
    params = dict(a2=a2, b2=b2, c2=c2, disc=disc, floor=floor, phi=phi, flat=flat, hp_a2=hp_a2, hp_c2=hp_c2)
    t = scaled(name, cols, psi, **kw)
    t.note = json.dumps(params)
    return t


def normal_scores(v: np.ndarray) -> np.ndarray:
    """each cell's values over spines to normal scores by rank (a Gaussian copula), for a robust fit"""
    from statistics import NormalDist
    n = len(v)
    ranks = np.argsort(np.argsort(v, axis=0), axis=0) + 1.0
    p = (ranks - 0.5) / n
    q = NormalDist().inv_cdf
    table = np.array([q((i + 0.5) / n) for i in range(n)])
    return table[(ranks - 1).astype(int)]


def spearman_as_pearson(v: np.ndarray) -> np.ndarray:
    """Spearman's correlation of every pair of cells, mapped to the normal-scale correlation
    2 sin(pi rho_s / 6), so that it reads on Pearson's scale under normality"""
    n = len(v)
    x = v.reshape(n, -1)
    ranks = np.argsort(np.argsort(x, axis=0), axis=0).astype(float)
    rs = np.corrcoef(ranks.T)
    return 2 * np.sin(np.pi * rs / 6)

# ---------------------------------------------------------------------------------------------
# what a grid job could compute from the rows, simulated
# ---------------------------------------------------------------------------------------------


def grid_statistics(v: np.ndarray, with_t1: bool = True) -> dict:
    """v (n, 22, 5) whole spines: the statistics that separate the hypotheses"""
    n = len(v)
    z, _, _ = standardise(v)
    s = corr_of(z)
    sp = spearman_as_pearson(v)
    rl, rm = grid_fit(v)
    k = np.kron(rl, rm)
    out = {}
    for tag, mat in (("pearson", s), ("spearman", sp)):
        st = truth_stats(mat)
        for key in ("same_level_widths", "same_level_depths", "same_level_width_depth_upper", "same_level_hpost_mean",
                    "same_level_wd4_mean", "disc_widths", "disc_depths", "lag1_upperW_to_next_lowerW",
                    "lag1_cross_wd4_not_facing", "lag5_cross_wd4"):
            out["%s_%s" % (tag, key)] = st[key]
        out["%s_lag1_same" % tag] = st["lag_same_measure"][0]
        out["%s_lag5_same" % tag] = st["lag_same_measure"][4]
        out["%s_same_level_widths_cervical" % tag] = float(same_level(mat, CERV)[EP, EPL])
        out["%s_same_level_widths_T1L5" % tag] = float(same_level(mat, range(T1_AT, L))[EP, EPL])
    kst = truth_stats(k)
    out["kron_R_measure_widths"] = float(rm[EP, EPL])
    out["kron_R_measure_depths"] = float(rm[EPD, EPLD])
    out["kron_R_measure_wd_upper"] = float(rm[EP, EPD])
    out["kron_lag1"] = lag_profile(rl)[0]
    # misfit of the Kronecker fit by cell group: Pearson minus what the fitted product implies
    for key in ("same_level_widths", "same_level_depths", "same_level_wd4_mean", "disc_widths", "disc_depths",
                "lag1_cross_wd4_not_facing", "lag5_cross_wd4"):
        out["misfit_" + key] = out["pearson_" + key] - kst[key]
    out["misfit_lag1_same"] = out["pearson_lag1_same"] - kst["lag_same_measure"][0]
    # cross-region, cross-measure: cervical cells against lumbar cells, the four end-plate measures
    lum = [LEVELS.index(x) for x in ("L1", "L2", "L3", "L4", "L5")]
    pairs_s = [s[cell(a, m), cell(b, mm)] for a in CERV for b in lum for m in range(4) for mm in range(4) if m != mm]
    pairs_k = [k[cell(a, m), cell(b, mm)] for a in CERV for b in lum for m in range(4) for mm in range(4) if m != mm]
    out["pearson_cerv_lumbar_cross_measure"] = float(np.mean(pairs_s))
    out["misfit_cerv_lumbar_cross_measure"] = float(np.mean(pairs_s) - np.mean(pairs_k))
    # the fit on normal scores (Gaussian copula), robust to tails and gross outliers
    rl_ns, rm_ns = grid_fit(normal_scores(v))
    out["copula_R_measure_widths"] = float(rm_ns[EP, EPL])
    out["copula_R_measure_depths"] = float(rm_ns[EPD, EPLD])
    out["copula_lag1"] = lag_profile(rl_ns)[0]
    if with_t1:
        rl1, rm1 = grid_fit(v[:, T1_AT:, :], LEVELS[T1_AT:])
        out["T1L5_minus_C3L5_widths"] = float(rm1[EP, EPL] - rm[EP, EPL])
        out["T1L5_minus_C3L5_wd_upper"] = float(rm1[EP, EPD] - rm[EP, EPD])
        rlc, rmc = grid_fit(v[:, :T1_AT, :], LEVELS[:T1_AT])
        out["cervical_fit_R_measure_widths"] = float(rmc[EP, EPL])
    return out


def grid_stat_reps(truth: Truth, n: int, reps: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    rows = [grid_statistics(truth.sample(rng, n), with_t1=True) for _ in range(reps)]
    return summarize(rows)

# ---------------------------------------------------------------------------------------------
# an anatomy-like factor truth tuned so that the fit's population limit reproduces the published
# C3..L5 summaries (R_measure's ten pairs, the lag profile of R_level)
# ---------------------------------------------------------------------------------------------


def tuned_truth(name: str, p: Dict[str, float]) -> Truth:
    """size (a2) on the four end-plate measures; a field per measure along the spine (b2, AR(phi)
    with a floor); a width factor and a depth factor per vertebra (gw2, gd2); a vertebra factor on
    the four (c2); the facing end plates across each disc (k2); noise the rest. h_post: its field
    (b2) and noise only."""
    k = ar_kernel(L, p["phi"], p["floor"])
    cols = [comp_global([math.sqrt(p["a2"])] * 4 + [0.0]),
            comp_measure_fields([math.sqrt(p["b2"])] * M, k),
            comp_vertebra([math.sqrt(p["gw2"]), 0, math.sqrt(p["gw2"]), 0, 0]),
            comp_vertebra([0, math.sqrt(p["gd2"]), 0, math.sqrt(p["gd2"]), 0]),
            comp_vertebra([math.sqrt(p["c2"])] * 4 + [0.0])]
    psi = np.zeros(L * M)
    for l in range(L):
        for m in range(M):
            if m == HP:
                used = p["b2"]
            else:
                used = p["a2"] + p["b2"] + p["c2"] + (p["gw2"] if m in (EP, EPL) else p["gd2"])
                facing = (m in (EPL, EPLD) and l < L - 1) or (m in (EP, EPD) and l > 0)
                used += p["k2"] if facing else 0.0
            psi[cell(l, m)] = 1 - used
    if p["k2"] > 0:
        cols.append(comp_disc(math.sqrt(p["k2"]), math.sqrt(p["k2"])))
    t = scaled(name, cols, np.clip(psi, 1e-6, None))
    t.note = json.dumps({k2: round(v, 4) for k2, v in p.items()})
    return t


TUNE_KEYS = ["a2", "b2", "phi", "floor", "gw2", "gd2", "c2", "k2"]


def tune_loss(p: Dict[str, float], target_rm: np.ndarray, target_lag: List[float]) -> float:
    if min(p.values()) < 0 or p["phi"] >= 0.99 or p["floor"] >= 0.99:
        return 1e6
    wd = p["a2"] + p["b2"] + p["c2"] + max(p["gw2"], p["gd2"]) + p["k2"]
    if wd > 0.98 or p["b2"] > 0.98:
        return 1e6
    t = tuned_truth("tune", p)
    rl, rm = projected_prior(t.sigma())
    iu = np.triu_indices(M, 1)
    return float(((rm[iu] - target_rm[iu]) ** 2).sum() + ((np.array(lag_profile(rl)) - np.array(target_lag)) ** 2).sum())


def nelder_mead(f, x0: np.ndarray, step: float = 0.05, iters: int = 600, tol: float = 1e-10) -> Tuple[np.ndarray, float]:
    n = len(x0)
    pts = [x0] + [x0 + step * np.eye(n)[i] for i in range(n)]
    vals = [f(x) for x in pts]
    for _ in range(iters):
        order = np.argsort(vals)
        pts = [pts[i] for i in order]
        vals = [vals[i] for i in order]
        if abs(vals[-1] - vals[0]) < tol:
            break
        centroid = np.mean(pts[:-1], axis=0)
        xr = centroid + (centroid - pts[-1])
        fr = f(xr)
        if fr < vals[0]:
            xe = centroid + 2 * (centroid - pts[-1])
            fe = f(xe)
            pts[-1], vals[-1] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < vals[-2]:
            pts[-1], vals[-1] = xr, fr
        else:
            xc = centroid + 0.5 * (pts[-1] - centroid)
            fc = f(xc)
            if fc < vals[-1]:
                pts[-1], vals[-1] = xc, fc
            else:
                pts = [pts[0]] + [pts[0] + 0.5 * (x - pts[0]) for x in pts[1:]]
                vals = [vals[0]] + [f(x) for x in pts[1:]]
    i = int(np.argmin(vals))
    return pts[i], vals[i]


def tune(fixed: Dict[str, float], target_rm: np.ndarray, target_lag: List[float], seed: int = 0,
         starts: int = 4) -> Tuple[Dict[str, float], float]:
    free = [k for k in TUNE_KEYS if k not in fixed]
    rng = np.random.default_rng(seed)
    best, best_loss = None, np.inf
    for s in range(starts):
        base = {"a2": 0.1, "b2": 0.4, "phi": 0.6, "floor": 0.4, "gw2": 0.1, "gd2": 0.2, "c2": 0.05, "k2": 0.05}
        if "a2" in fixed:                   # start feasible: the field gives way to a fixed size share
            base["b2"] = min(base["b2"], 0.9 - fixed["a2"] - base["c2"] - base["gd2"] - base["k2"])
        x0 = np.array([base[k] * (1 + 0.3 * rng.standard_normal()) if s else base[k] for k in free])
        x0 = np.clip(x0, 0.0, 0.9)

        def f(x):
            p = dict(fixed)
            p.update({k: float(v) for k, v in zip(free, x)})
            return tune_loss(p, target_rm, target_lag)
        x, val = nelder_mead(f, x0)
        x, val = nelder_mead(f, x, step=0.02)
        if val < best_loss:
            best_loss = val
            best = dict(fixed)
            best.update({k: float(v) for k, v in zip(free, x)})
    return best, best_loss

# ---------------------------------------------------------------------------------------------
# the parts
# ---------------------------------------------------------------------------------------------


def r3(x):
    if isinstance(x, (list, tuple)):
        return [r3(v) for v in x]
    if isinstance(x, np.ndarray):
        return np.round(x, 3).tolist()
    if isinstance(x, (float, np.floating)):
        return round(float(x), 4)
    return x


def describe(truth: Truth, fitted: Optional[Tuple[np.ndarray, np.ndarray]] = None) -> dict:
    """the truth's own numbers, and the fit's population limit where the truth is Gaussian"""
    clean, seen = truth.sigma(), truth.sigma_observed()
    out = {"name": truth.name, "note": truth.note, "true_clean": {k: r3(v) for k, v in truth_stats(clean).items()}}
    if truth.outlier:
        out["true_with_outliers"] = {k: r3(v) for k, v in truth_stats(seen).items()}
    rl, rm = projected_prior(seen) if fitted is None else fitted
    out["fit_limit"] = {k: r3(v) for k, v in prior_stats(rl, rm).items()}
    out["kl_gap_nats_per_spine"] = r3(population_kl_gap(seen, rl, rm))
    out["gain_over_assumed_limit"] = r3(population_gain_over_assumed(seen, rl, rm))
    sub = sub_levels(seen, range(T1_AT, L))
    rl1, rm1 = projected_prior(sub, L - T1_AT)
    out["fit_limit_T1L5"] = {"R_measure_widths": r3(rm1[EP, EPL]), "R_measure_depths": r3(rm1[EPD, EPLD]),
                             "R_measure_width_depth_upper": r3(rm1[EP, EPD]), "R_level_lag": r3(lag_profile(rl1))}
    return out


def part_sanity() -> dict:
    out = {"copy_check": check_copy()}
    obs = observed_targets()
    e, t = obs["enhance_C3L5"], obs["totalseg_C3L5"]
    for tag, pr, ns in (("enhance_separable", e, (693, 67)), ("totalseg_separable", t, (67, 693))):
        rl_u, rm_u = unshrink(pr.r_level), unshrink(pr.r_measure)
        truth = sigma_truth(tag, np.kron(rl_u, rm_u))
        prl, prm, used = project(np.kron(rl_u, rm_u), L)
        res = {"published": prior_stats(pr.r_level, pr.r_measure),
               "limit_recovers_published_max_abs_err": r3(max(np.abs(shrunk(prl, SHRINK) - pr.r_level).max(),
                                                           np.abs(shrunk(prm, SHRINK) - pr.r_measure).max()))}
        for n in ns:
            res["n%d" % n] = fit_reps(truth, n, 40 if n == 693 else 200, seed=11 + n)
        out[tag] = res
    # the two published ENHANCE.PET level sets fitted on the same simulated spines (710, the first
    # 693 whole from C3), separable truth: how far apart sampling alone puts them
    rl_u, rm_u = unshrink(e.r_level), unshrink(e.r_measure)
    truth = sigma_truth("enhance_separable", np.kron(rl_u, rm_u))
    rng = np.random.default_rng(5)
    rows = []
    for _ in range(60):
        v = truth.sample(rng, 710)
        rl, rm = grid_fit(v[:693])
        rl1, rm1 = grid_fit(v[:, T1_AT:, :], LEVELS[T1_AT:])
        rows.append({"widths": rm1[EP, EPL] - rm[EP, EPL], "depths": rm1[EPD, EPLD] - rm[EPD, EPLD],
                     "width_depth_upper": rm1[EP, EPD] - rm[EP, EPD], "width_depth_lower": rm1[EPL, EPLD] - rm[EPL, EPLD],
                     "upperW_lowerD": rm1[EP, EPLD] - rm[EP, EPLD], "upperD_lowerW": rm1[EPD, EPL] - rm[EPD, EPL],
                     "lag1_T1L5_block": lag_profile(rl1)[0] - float(np.mean(np.diag(rl[T1_AT:, T1_AT:], 1)))})
    e1 = obs["enhance_T1L5"]
    observed = {"widths": e1.r_measure[EP, EPL] - e.r_measure[EP, EPL], "depths": e1.r_measure[EPD, EPLD] - e.r_measure[EPD, EPLD],
                "width_depth_upper": e1.r_measure[EP, EPD] - e.r_measure[EP, EPD],
                "width_depth_lower": e1.r_measure[EPL, EPLD] - e.r_measure[EPL, EPLD],
                "upperW_lowerD": e1.r_measure[EP, EPLD] - e.r_measure[EP, EPLD],
                "upperD_lowerW": e1.r_measure[EPD, EPL] - e.r_measure[EPD, EPL],
                "lag1_T1L5_block": lag_profile(e1.r_level)[0] - float(np.mean(np.diag(e.r_level[T1_AT:, T1_AT:], 1)))}
    sim = summarize(rows)
    out["T1L5_minus_C3L5_separable"] = {k: {"sim_mean": sim[k]["mean"], "sim_sd": sim[k]["sd"], "observed": r3(observed[k]),
                                            "z": r3((observed[k] - sim[k]["mean"]) / sim[k]["sd"])} for k in observed}
    return out


FORWARD = [
    # (b) literal: one person factor per measure shared by every level (no decay along the spine)
    ("b_flat_c0", dict(a2=0.15, b2=0.35, c2=0.0, flat=True)),
    ("b_flat_c2", dict(a2=0.15, b2=0.35, c2=0.2, flat=True)),
    ("b_flat_c4", dict(a2=0.15, b2=0.35, c2=0.4, flat=True)),
    # (b) the measure's field decays along the spine, AR(0.6) over a floor of 0.4
    ("b_a0_c2", dict(a2=0.0, b2=0.45, c2=0.2)),
    ("b_a0_c4", dict(a2=0.0, b2=0.45, c2=0.4)),
    ("b_a15_c0", dict(a2=0.15, b2=0.45, c2=0.0)),
    ("b_a15_c1", dict(a2=0.15, b2=0.45, c2=0.1)),
    ("b_a15_c2", dict(a2=0.15, b2=0.45, c2=0.2)),
    ("b_a15_c3", dict(a2=0.15, b2=0.45, c2=0.3)),
    ("b_a15_c4", dict(a2=0.15, b2=0.45, c2=0.4)),
    ("b_a3_c0", dict(a2=0.3, b2=0.45, c2=0.0)),
    ("b_a3_c2", dict(a2=0.3, b2=0.45, c2=0.2)),
    # (c) (b) plus the facing end plates across each disc
    ("c_a15_c2_k1", dict(a2=0.15, b2=0.45, c2=0.2, disc=0.1)),
    ("c_a15_c2_k2", dict(a2=0.15, b2=0.45, c2=0.2, disc=0.2)),
    ("c_a15_c0_k3", dict(a2=0.15, b2=0.45, c2=0.0, disc=0.3)),
    # (d) (b) with heavy tails or gross outliers
    ("d_t3", dict(a2=0.15, b2=0.45, c2=0.2, noise="t3")),
    ("d_cell2", dict(a2=0.15, b2=0.45, c2=0.2, outlier="cell", outlier_p=0.02, outlier_sd=5.0)),
    ("d_cell5", dict(a2=0.15, b2=0.45, c2=0.2, outlier="cell", outlier_p=0.05, outlier_sd=5.0)),
    ("d_vert2", dict(a2=0.15, b2=0.45, c2=0.2, outlier="vertebra", outlier_p=0.02, outlier_sd=3.0)),
    ("d_spine2", dict(a2=0.15, b2=0.45, c2=0.2, outlier="spine", outlier_p=0.02, outlier_sd=3.0)),
]


def forward_truth(name: str, spec: dict) -> Truth:
    spec = dict(spec)
    kw = {k: spec.pop(k) for k in ("noise", "outlier", "outlier_p", "outlier_sd") if k in spec}
    return factor_truth(name, **spec, **kw)


def part_forward() -> dict:
    out = {}
    for name, spec in FORWARD:
        t = forward_truth(name, spec)
        res = describe(t)
        res["n693"] = fit_reps(t, 693, 12, seed=101)
        res["n67"] = fit_reps(t, 67, 60, seed=102)
        if t.noise != "gauss" or t.outlier:
            rng = np.random.default_rng(103)
            rows = []
            for _ in range(12):
                v = t.sample(rng, 693)
                rl, rm = grid_fit(normal_scores(v))
                rows.append(prior_stats(rl, rm))
            res["n693_copula_fit"] = summarize(rows)
        out[name] = res
    return out


def matched_truths() -> Dict[str, Tuple[Truth, dict]]:
    obs = observed_targets()
    e, e1 = obs["enhance_C3L5"], obs["enhance_T1L5"]
    tl, tm, tm1 = unshrink(e.r_level), unshrink(e.r_measure), unshrink(e1.r_measure)
    out = {}
    feasible = {}
    for kind in ("noise", "size", "size_wd", "vertebra", "vertebra_wd", "disc", "cervical_widths"):
        d = delta_kind(kind)
        top = max_feasible(d, tl, tm)
        feasible[kind] = top
        for theta in (0.1, 0.2, round(0.98 * top, 3)):
            if theta > 0.98 * top + 1e-9:
                continue
            r = match_core(d, theta, tl, tm)
            if r["ok"]:
                out["e_%s_%.3f" % (kind, theta)] = (sigma_truth("e_%s_%.3f" % (kind, theta), r["sigma"]),
                                                    {"kind": kind, "theta": theta, "max_feasible_theta": round(top, 3)})
    r = match_regional(tl, tm, tm1)
    out["e_regional"] = (sigma_truth("e_regional", r["sigma"]),
                         {"kind": "regional", "ok": r["ok"], "b_cervical": r3(r["b_cervical"]), "b_thoracolumbar": r3(tm1)})
    for kind, theta in (("size", 0.1), ("size", 0.2), ("disc", 0.1), ("noise", 0.1), ("vertebra_wd", 0.1)):
        rr = match_regional_mixed(tl, tm, tm1, delta_kind(kind), theta)
        if rr["ok"]:
            nm = "e_regional+%s_%.2f" % (kind, theta)
            out[nm] = (sigma_truth(nm, rr["sigma"]), {"kind": "regional+" + kind, "theta": theta,
                                                       "b_cervical": r3(rr["b_cervical"]), "b_thoracolumbar": r3(rr["b_thoracolumbar"])})
        else:
            out["e_regional+%s_%.2f_INFEASIBLE" % (kind, theta)] = (None, {"kind": "regional+" + kind, "theta": theta, "ok": False})
    out["_feasible"] = (None, {k: round(v, 3) for k, v in feasible.items()})
    return out


def part_matched() -> dict:
    obs = observed_targets()
    e = obs["enhance_C3L5"]
    out = {}
    for name, (t, meta) in matched_truths().items():
        if t is None:
            out[name] = meta
            continue
        res = describe(t, fitted=(e.r_level, e.r_measure))
        res["meta"] = meta
        out[name] = res
    # anatomy-like factor truths tuned to the published summaries, at fixed size shares
    tuned = {}
    lag = lag_profile(e.r_level)
    for fixed in ({"a2": 0.0}, {"a2": 0.1}, {"a2": 0.2}, {"a2": 0.25}, {"k2": 0.0}, {"k2": 0.1}, {"k2": 0.2}):
        p, loss = tune(fixed, e.r_measure, lag, starts=3)
        t = tuned_truth("tuned_" + "_".join("%s%.2f" % kv for kv in fixed.items()), p)
        res = describe(t)
        res["params"] = {k: round(v, 4) for k, v in p.items()}
        res["loss"] = r3(loss)
        tuned[t.name] = res
    out["tuned"] = tuned
    return out


HELDOUT_SET = ["a_sep", "b_a15_c0", "b_a15_c2", "b_a15_c4", "c_a15_c2_k2", "d_cell5", "d_t3",
               "e_size_0.200", "e_noise_0.200", "e_vertebra_wd_0.200", "e_disc_0.100", "e_regional",
               "e_regional+size_0.20", "e_regional+disc_0.10"]


def named_truths() -> Dict[str, Truth]:
    obs = observed_targets()
    e = obs["enhance_C3L5"]
    out = {"a_sep": sigma_truth("a_sep", np.kron(unshrink(e.r_level), unshrink(e.r_measure)))}
    for name, spec in FORWARD:
        out[name] = forward_truth(name, spec)
    for name, (t, meta) in matched_truths().items():
        if t is not None:
            out[name] = t
    return out


def part_heldout() -> dict:
    truths = named_truths()
    out = {}
    for name in HELDOUT_SET:
        if name not in truths:
            out[name] = "not built"
            continue
        t0 = time.time()
        out[name] = {"n693_test158": heldout(truths[name], 693, 158, reps=8, seed=201)}
        if name in ("a_sep", "e_size_0.200", "e_disc_0.100", "e_regional", "b_a15_c4"):
            out[name]["n67_test13"] = heldout(truths[name], 67, 13, reps=24, seed=202, with_kw=True)
        out[name]["seconds"] = round(time.time() - t0, 1)
        print("heldout", name, out[name]["seconds"], flush=True)
    return out


def part_grid() -> dict:
    truths = named_truths()
    out = {}
    for name in HELDOUT_SET:
        if name not in truths:
            continue
        t0 = time.time()
        out[name] = {"n693": grid_stat_reps(truths[name], 693, 20, seed=301),
                     "n67": grid_stat_reps(truths[name], 67, 40, seed=302)}
        print("grid", name, round(time.time() - t0, 1), flush=True)
    return out


PANJABI_CSV = "/home/claude/bordercall/schwingcheck/data/panjabi_long.csv"
MNEMONIC = {"endplate": "EPWu", "endplate_depth": "EPDu", "endplate_lower": "EPWl", "endplate_lower_depth": "EPDl",
            "h_post": "VBHp"}


def panjabi_table() -> Dict[str, Dict[str, Tuple[float, float]]]:
    """{measure: {level: (mean, SD)}} read as text from bordercall's checked table, SD = SEM sqrt(n),
    the first row of each cell (the file repeats rows)"""
    import csv
    vals: Dict[Tuple[str, str, str], Tuple[float, float]] = {}
    with open(PANJABI_CSV, newline="") as fh:
        for r in csv.DictReader(line for line in fh if not line.startswith("#")):
            if r["side"] != "whole" or r["measure"] not in MNEMONIC:
                continue
            key = (r["measure"], r["level"], r["statistic"])
            if key not in vals:
                vals[key] = (float(r["value"]), float(r["n"]))
    out: Dict[str, Dict[str, Tuple[float, float]]] = {}
    for m in MNEMONIC:
        out[m] = {}
        for lv in LEVELS:
            if (m, lv, "mean") in vals and (m, lv, "sem") in vals:
                mean, _ = vals[(m, lv, "mean")]
                sem, n = vals[(m, lv, "sem")]
                out[m][lv] = (mean, sem * math.sqrt(n))
    return out


def phantom_corr(rl: np.ndarray, rm: np.ndarray, table, scale_sd: float = 0.07, noise_mm: float = 1.0) -> np.ndarray:
    """the correlation of drawn phantom values, v = g (mu + sd field) + noise_mm e, g = exp(N(0, scale_sd^2)),
    field ~ MN(0, R_level, R_measure), as columns.draw_columns draws with correlation=prior"""
    var_g = math.exp(scale_sd ** 2) * (math.exp(scale_sd ** 2) - 1)
    g2 = math.exp(2 * scale_sd ** 2)
    mu = np.array([[table[m][lv][0] for m in MEASURES] for lv in LEVELS]).reshape(-1)
    sd = np.array([[table[m][lv][1] for m in MEASURES] for lv in LEVELS]).reshape(-1)
    k = np.kron(rl, rm)
    cov = np.outer(mu, mu) * var_g + np.outer(sd, sd) * g2 * k + noise_mm ** 2 * np.eye(len(mu))
    return to_correlation(cov)


def part_phantom() -> dict:
    """how the published prior reads in drawn phantoms: the generator's size factor and noise
    sit on top of R_measure, so a phantom's within-vertebra correlation is not R_measure"""
    table = panjabi_table()
    missing = {m: [lv for lv in LEVELS if lv not in table[m]] for m in MEASURES}
    obs = observed_targets()
    e = obs["enhance_C3L5"]
    out = {"table_missing_levels": missing}
    if any(missing.values()):
        return out
    for tag, scale_sd, noise in (("generator_default", 0.07, 1.0), ("no_size_no_noise", 0.0, 0.0),
                                 ("size_only", 0.07, 0.0), ("noise_only", 0.0, 1.0)):
        c = phantom_corr(e.r_level, e.r_measure, table, scale_sd, noise)
        st = truth_stats(c)
        out[tag] = {k: r3(st[k]) for k in ("same_level_widths", "same_level_depths", "same_level_width_depth_upper",
                                            "same_level_hpost_mean", "disc_widths", "disc_depths", "lag_same_measure",
                                            "lag1_cross_wd4_not_facing")}
        out[tag]["same_level_widths_cervical"] = r3(same_level(c, CERV)[EP, EPL])
        out[tag]["same_level_widths_T1L5"] = r3(same_level(c, range(T1_AT, L))[EP, EPL])
    out["size_share_of_variance_mean"] = r3(float(np.mean([
        (table[m][lv][0] ** 2 * math.exp(0.07 ** 2) * (math.exp(0.07 ** 2) - 1)) /
        (table[m][lv][0] ** 2 * math.exp(0.07 ** 2) * (math.exp(0.07 ** 2) - 1) + table[m][lv][1] ** 2 * math.exp(2 * 0.07 ** 2) + 1.0)
        for m in MEASURES[:4] for lv in LEVELS])))
    out["table_sd_over_mean_mean"] = r3(float(np.mean([table[m][lv][1] / table[m][lv][0] for m in MEASURES for lv in LEVELS])))
    return out


PARTS = {"sanity": part_sanity, "forward": part_forward, "matched": part_matched, "heldout": part_heldout,
         "grid": part_grid, "phantom": part_phantom}


def main(argv: Sequence[str]) -> int:
    which = list(PARTS) if not argv or argv[0] == "all" else list(argv)
    for name in which:
        t0 = time.time()
        res = PARTS[name]()
        res["_seconds"] = round(time.time() - t0, 1)
        with open("%s/results-%s.json" % (HERE, name), "w") as f:
            json.dump(res, f, indent=1, default=lambda o: r3(o) if isinstance(o, (np.ndarray, np.floating)) else str(o))
        print("part %s done in %.1fs" % (name, time.time() - t0), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
