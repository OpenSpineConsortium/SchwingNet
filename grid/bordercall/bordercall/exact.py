"""Name a run of consecutive vertebrae exactly: the generator's own Bayes rule, by enumeration.

    python run.py exact --outdir ../records/exact-2026-10-26
    python run.py exact-figures --json ../records/exact-2026-10-26/exact.json --outdir ...

The owner's ask of 2026-10-26 10:43 UTC: "so essentially i want to know if there are any
formulas or functions possible neural network which takes any number of sequential vertebral
measurements from 1 to n such that this function unambiguously identifies a vertebra? please
rely on any of the ideas from the [solver survey] particularly the 'exactness by construction
(no relaxation, big-M, tolerance or optimality gap) plus the entire ranked score distribution'
im fishing for some positive result, and im willing to let you tell me what i can say with this
panjabi synthetic data".

THE RULE NEEDS NO FITTING. A field of n consecutive bodies can sit at only 23 - n places in a
column of twenty-two (C3 to L5), and naming the field is choosing the place: once the place is
known, every body in the field has its name. Given the place, the generator (panjabi.py) says
exactly how the field's values are distributed. For one measure, given the patient's size s,

    x_i = s (mu_i + sd_i (rho z + sqrt(1 - rho^2) e_i)) + noise_i,      i = 1..n,

so, given s, the n values are jointly normal with mean s mu and covariance

    Delta + u u',    Delta = diag(s^2 (1 - rho^2) sd_i^2 + noise^2),    u = s rho sd,

a diagonal plus a rank-one matrix, whose inverse and determinant have closed forms
(Sherman-Morrison: no matrix is inverted), and the measures are independent of each other at
r = 0. The likelihood of the field at a place is the product over measures, integrated over
log s, which is normal with SD scale_sd, by Gauss-Hermite quadrature. Scoring every place and
normalising under a uniform prior gives the posterior over places (`log_evidence`,
`posterior`). That is the solver survey's "exactness by construction" applied to naming
(research/solver-survey-2026-10-26/REPORT.md, the paragraph on enumeration): every alternative
is enumerated, there is no relaxation, big-M, tolerance or optimality gap, the one numerical
step is a one-dimensional quadrature whose error is measured (`quadrature_check`), and the
answer is the entire ranked distribution over places, not an argmax.

WHAT FOLLOWS FROM THAT, BY CONSTRUCTION, WHILE THE GENERATOR IS THE TRUTH: typical columns,
every place equally likely (the prior of the rule and of the score alike).
1. No function of the same measurements, formula or neural network, names fields correctly
   more often than this rule: it is the Bayes rule. Its error is the floor for any network.
2. No function names every field correctly for n below 22: given the size, the generator's
   values are normal (marginally a scale mixture of normals), so every place gives every field a
   positive density, and the Bayes error is positive.
3. The posterior of the named place is the probability the name is right. A rule that answers
   only when that posterior reaches 1 - eps is right at least 1 - eps of the times it answers
   (the selective guarantee): E[correct | p >= 1 - eps] = E[p | p >= 1 - eps] >= 1 - eps. The
   set of places holding 99 per cent of the posterior holds the truth at least 99 per cent of
   the time. A claim about a border is a sum of the same posterior, so a claim made at 0.99 is
   right at least 99 per cent of the times it is made, and two claims made about one field are
   both right at least 98 per cent of the time (the union bound).
4. All three hold for any n, so one function takes 1 to n bodies, as the owner asked.
Each guarantee is an average over fields and holds within any group of fields chosen by their
measurements alone (the fields the rule calls lumbar, say: `selective_099_by_called_region`);
it does not hold within a group chosen by the truth (the fields whose true place is one level,
or whose middle body is within two levels of a border), so the rates the record gives per
true place, per true centre level, per landmark window and near each border are measurements,
not guarantees. Under another prior over places, a real series' commoner lumbar fields say,
the rule must carry that prior or its posteriors are about a different population.

WHAT IS MEASURED, each under its key in the record.
A. `widths`: for every n from 1 to 22, the rule on fresh typical columns, every place of every
   column scored (uniform over places, standard errors clustered by column): exact and within
   one, the Bayes error the posterior itself predicts beside the error counted, the log loss,
   the share answered and the precision reached at posterior 0.9, 0.99 and 0.999 (overall and
   by the region the rule calls), the 99 per cent set's size and coverage, the mapping quality
   (-10 log10 of one minus the posterior, as a read aligner reports it), per place and per
   centre level, and the landmark windows (those holding C7 and T1, those inside T3 to T10,
   those holding T12 and L1), for both planes, AP and lateral; and the claims about the middle
   body at every border, overall and within two levels of it.
B. `subsets`: every one of the 127 subsets of the seven SPINEPS-measurable measures at every n,
   scored on the same columns (common random numbers), and ranked: the whole distribution.
C. `formula` and `challengers`: the same likelihood linearised in the log measures, with the
   size integrated in closed form -- one quadratic discriminant per place, no quadrature and no
   fitting, an approximation to the exact rule and not the rule -- and, as the outside check of
   the ceiling, rules fitted on 5,000 columns from the fitting seed: a quadratic rule in the log
   measures and in the raw ones, and a network with one hidden layer stopped early on 1,000
   columns from the selection seed, each beside the exact rule on the same fields with the
   paired difference and its standard error; and the fitted classifiers of the earlier studies.
D. `robust`: what survives when the generator is not the truth. The table's own twelve-spine
   error (the rule built on a table re-estimated from twelve specimens drawn from the generator,
   scored on columns from the published table; and the published table scored on columns from
   a table redrawn level by level from its standard errors); the rule's rho, size spread,
   measurement error (up to 3 mm, past what any rule assumes) and between-measure correlation r
   set wrong; a size trend down the column and both canal measures 8 per cent low; and the
   twelve-spine table together with r 0.4 and a 1.5 mm error. Each world is scored for three
   rules on the same columns (RULES): the nominal rule; a predictive one that takes a new
   spine's spread about a twelve-spine mean and SD, with no constant chosen on any draw; and an
   honest one that takes the means' error and a 2 mm measurement error, the 2 mm chosen on a
   pilot of sixteen specimen worlds from a seed of their own, recorded with every variant it
   compared (`robust.pilot`). For each: the rate, the precision reached at the posterior
   thresholds, which is the selective guarantee tested where its premise fails, and the
   precision of the border claims, overall and within two levels of each border, with standard
   errors clustered by world.

Every number is about synthetic columns drawn from Panjabi's tables; nothing here is a patient.
Only the typical column is drawn. The generator's floor at 0.5 mm is the one thing the
likelihood leaves out; the record counts the values it touched.
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

MEASURES7 = list(CV.SPINEPS_7)
LEVELS = list(P.LEVELS)
L = len(LEVELS)
WIDTHS = tuple(range(1, L + 1))
REGIMES = {name: list(ms) for name, ms in NB.REGIMES.items()}
THRESHOLDS = (0.9, 0.99, 0.999)
CREDIBLE = 0.99
GH_NODES = 161
TRAPEZOID_NODES = 1801
TRAPEZOID_HALF_WIDTH = 9.0
N_SCORE = 2000
SCORE_SEED = NB.SCORE_SEED
CHUNK = 100
PROCESSES = 4
MAPQ_CAP = 60.0
ROBUST_WIDTHS = (1, 3, 5, 9, 15)
ROBUST_WORLDS = 40
ROBUST_COLUMNS = 100
LANDMARKS = {"cervicothoracic": ("C7", "T1"), "mid_thoracic": ("T3", "T10"), "thoracolumbar": ("T12", "L1")}
LOG2PI = math.log(2.0 * math.pi)


# ---- the likelihood ----------------------------------------------------------------------------

def quadrature(scale_sd: float, n_nodes: int = GH_NODES) -> Tuple[np.ndarray, np.ndarray]:
    """Sizes and log weights for integrating over log s ~ N(0, scale_sd^2); one node when there is
    no size spread, since then s is 1."""
    if scale_sd <= 0:
        return np.ones(1), np.zeros(1)
    x, w = np.polynomial.hermite.hermgauss(n_nodes)
    return np.exp(math.sqrt(2.0) * scale_sd * x), np.log(w / math.sqrt(math.pi))


def table_arrays(ref, measures: Sequence[str]) -> Tuple[np.ndarray, np.ndarray]:
    """The table's means and population SDs, measures by levels."""
    mu = np.array([[ref[m][lv][0] for lv in LEVELS] for m in measures], float)
    sd = np.array([[ref[m][lv][1] for lv in LEVELS] for m in measures], float)
    return mu, sd


def place_loglik(X: np.ndarray, mu: np.ndarray, sd: np.ndarray, start: int, sizes: np.ndarray,
                 rho: float, noise_mm: float) -> np.ndarray:
    """log density of each field's values, measure by measure, at the place `start`, for each
    quadrature size: (fields, measures, nodes). X is (fields, measures, n). The covariance of one
    measure's n values given s is Delta + u u' (module docstring), so with d = 1/Delta,
    quad = sum r^2 d - (sum r u d)^2 / (1 + sum u^2 d) and logdet = sum log Delta + log(1 + sum
    u^2 d); the residual r = x - s mu is expanded so every sum is a matrix product."""
    nf, nm, n = X.shape
    out = np.empty((nf, nm, len(sizes)))
    s = sizes[:, None]
    for m in range(nm):
        mw, sw = mu[m, start:start + n], sd[m, start:start + n]
        delta = s * s * (1.0 - rho * rho) * sw * sw + noise_mm * noise_mm      # (J, n)
        d = 1.0 / delta
        u = s * rho * sw
        a = (u * u * d).sum(1)                                                 # (J,)
        x = X[:, m, :]
        q1 = (x * x) @ d.T - 2.0 * x @ (s * mw * d).T + (s * s * mw * mw * d).sum(1)
        q2 = x @ (u * d).T - (s * mw * u * d).sum(1)
        quad = q1 - q2 * q2 / (1.0 + a)
        logdet = np.log(delta).sum(1) + np.log1p(a)
        out[:, m, :] = -0.5 * (quad + logdet + n * LOG2PI)
    return out


def logsumexp(a: np.ndarray, axis: int) -> np.ndarray:
    top = np.max(a, axis=axis, keepdims=True)
    return np.squeeze(top, axis) + np.log(np.exp(a - top).sum(axis))


def field_loglik(X: np.ndarray, mu: np.ndarray, sd: np.ndarray, synth: dict,
                 n_nodes: int = GH_NODES) -> np.ndarray:
    """Per-measure log likelihood at every place: (fields, places, measures, nodes)."""
    n = X.shape[2]
    sizes, _ = quadrature(synth["scale_sd"], n_nodes)
    return np.stack([place_loglik(X, mu, sd, k, sizes, synth["rho"], synth["noise_mm"])
                     for k in range(L - n + 1)], axis=1)


def log_evidence(LL: np.ndarray, logw: np.ndarray, measures: Optional[Sequence[int]] = None) -> np.ndarray:
    """log p(field | place) over the measures named (all by default), the size integrated out:
    (fields, places)."""
    part = LL if measures is None else LL[:, :, list(measures), :]
    return logsumexp(part.sum(2) + logw, axis=2)


def posterior(logev: np.ndarray, log_prior: Optional[np.ndarray] = None) -> np.ndarray:
    """The posterior over places, uniform beforehand unless a prior is given."""
    a = logev if log_prior is None else logev + log_prior
    p = np.exp(a - a.max(1, keepdims=True))
    return p / p.sum(1, keepdims=True)


def joint_place_loglik(X: np.ndarray, mu: np.ndarray, sd: np.ndarray, start: int, sizes: np.ndarray,
                       rho: float, noise_mm: float, r_between: float) -> np.ndarray:
    """The joint log density over all measures at once, (fields, nodes), with the patient's
    offsets correlated r_between across measures (covariance.py): given s the covariance is
    s^2 (d d') o [rho^2 (R kron 11') + (1 - rho^2) I] + noise^2 I, with d the stacked SDs and R
    the exchangeable correlation of the measures. Dense and slow; used where r is not zero and to
    check place_loglik at r = 0."""
    nf, nm, n = X.shape
    R = CV.exchangeable(nm, r_between) if abs(r_between) > 1e-12 else np.eye(nm)
    shape = rho * rho * np.kron(R, np.ones((n, n))) + (1.0 - rho * rho) * np.eye(nm * n)
    dvec = sd[:, start:start + n].reshape(-1)
    mvec = mu[:, start:start + n].reshape(-1)
    x = X.reshape(nf, nm * n)
    out = np.empty((nf, len(sizes)))
    for j, s in enumerate(sizes):
        C = s * s * np.outer(dvec, dvec) * shape + noise_mm * noise_mm * np.eye(nm * n)
        Lc = np.linalg.cholesky(C)
        Z = np.linalg.solve(Lc, (x - s * mvec).T)
        out[:, j] = -0.5 * ((Z * Z).sum(0) + 2.0 * np.log(np.diag(Lc)).sum() + nm * n * LOG2PI)
    return out


def joint_log_evidence(X: np.ndarray, mu: np.ndarray, sd: np.ndarray, synth: dict, r_between: float,
                       n_nodes: int = GH_NODES) -> np.ndarray:
    n = X.shape[2]
    sizes, logw = quadrature(synth["scale_sd"], n_nodes)
    return np.stack([logsumexp(joint_place_loglik(X, mu, sd, k, sizes, synth["rho"], synth["noise_mm"],
                                                  r_between) + logw, axis=1)
                     for k in range(L - n + 1)], axis=1)


# ---- the closed-form formula in the log measures -------------------------------------------------

def log_moments(mu: np.ndarray, sd: np.ndarray, start: int, n: int, synth: dict) -> Tuple[np.ndarray, np.ndarray]:
    """The mean and covariance of the field's log values to second order in the spreads: with
    c = sd / mu and e = noise / mu, log x = log s + log mu + c (rho z + sqrt(1 - rho^2) e_i) + e n_i
    - (c^2 + e^2) / 2 on average, so the covariance is scale_sd^2 on every pair (the size), c c'
    rho^2 within a measure (its offset) and (1 - rho^2) c^2 + e^2 on the diagonal."""
    nm = mu.shape[0]
    rho, noise, ssd = synth["rho"], synth["noise_mm"], synth["scale_sd"]
    mw, sw = mu[:, start:start + n], sd[:, start:start + n]
    c, e = sw / mw, noise / mw
    mean = (np.log(mw) - 0.5 * (c * c + e * e)).reshape(-1)
    cov = np.full((nm * n, nm * n), ssd * ssd)
    for m in range(nm):
        b = slice(m * n, (m + 1) * n)
        cov[b, b] += rho * rho * np.outer(c[m], c[m]) + np.diag((1.0 - rho * rho) * c[m] ** 2 + e[m] ** 2)
    return mean, cov


def formula_log_evidence(X: np.ndarray, mu: np.ndarray, sd: np.ndarray, synth: dict) -> np.ndarray:
    """One quadratic discriminant per place in the log measures, nothing fitted and nothing
    integrated numerically: (fields, places)."""
    nf, nm, n = X.shape
    y = np.log(X.reshape(nf, nm * n))
    out = np.empty((nf, L - n + 1))
    for k in range(L - n + 1):
        mean, cov = log_moments(mu, sd, k, n, synth)
        Lc = np.linalg.cholesky(cov)
        Z = np.linalg.solve(Lc, (y - mean).T)
        # the Jacobian of the log is the same at every place, so it is left out
        out[:, k] = -0.5 * ((Z * Z).sum(0) + 2.0 * np.log(np.diag(Lc)).sum())
    return out


# ---- fields and their scores ---------------------------------------------------------------------

def column_values(columns: Sequence[P.Column], measures: Sequence[str]) -> np.ndarray:
    """(columns, measures, 22)"""
    return np.array([[col.values[m] for m in measures] for col in columns], float)


def fields(V: np.ndarray, n: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Every field of n consecutive bodies of every column: X (fields, measures, n), the true
    place, and the column each came from."""
    nc = V.shape[0]
    K = L - n + 1
    X = np.concatenate([V[:, :, k:k + n] for k in range(K)])
    return X, np.repeat(np.arange(K), nc), np.tile(np.arange(nc), K)


def mapq(p: np.ndarray, cap: float = MAPQ_CAP) -> np.ndarray:
    """-10 log10 of the probability the named place is wrong, as a read aligner reports a read's
    mapping quality; capped, since one minus a posterior rounds to zero."""
    return np.minimum(-10.0 * np.log10(np.maximum(1.0 - p, 10.0 ** (-cap / 10.0))), cap)


def credible_sets(post: np.ndarray, level: float = CREDIBLE) -> Tuple[np.ndarray, np.ndarray]:
    """The smallest set of places holding `level` of the posterior: its size, and each place's
    membership (fields, places)."""
    order = np.argsort(-post, axis=1)
    sp = np.take_along_axis(post, order, axis=1)
    before = np.cumsum(sp, axis=1) - sp
    keep_sorted = before < level
    member = np.zeros_like(post, bool)
    np.put_along_axis(member, order, keep_sorted, axis=1)
    return keep_sorted.sum(1), member


def summary(post: np.ndarray, truth: np.ndarray, group: np.ndarray, n: int, detail: bool) -> dict:
    """What one rule did on every field of one width."""
    call = post.argmax(1)
    top = post.max(1)
    hit = (call == truth).astype(float)
    out = {"n_fields": int(len(truth)), "places": int(post.shape[1]),
           "exact": float(hit.mean()), "se_cluster": NB.clustered_se(hit, group),
           "within_one": float((np.abs(call - truth) <= 1).mean()),
           "errors": int((hit == 0).sum()),
           "bayes_error_predicted": float((1.0 - top).mean()),
           "bayes_error_counted": float(1.0 - hit.mean()),
           "log_loss": float(-np.log(np.maximum(post[np.arange(len(truth)), truth], 1e-300)).mean()),
           "selective": {}, "selective_099_by_called_region": {}}
    # the guarantee holds given anything the measurements decide, such as the region the call puts
    # the middle body in; it does not hold given the true level (by_start, by_centre, landmarks)
    called_region = REGION_INDEX[call + target_offset(n)]
    for r, name in enumerate(REGION_NAMES):
        a = (top >= 0.99) & (called_region == r)
        out["selective_099_by_called_region"][name] = {"n_answered": int(a.sum()), "errors": int((hit[a] == 0).sum())}
    groups = np.unique(group, return_inverse=True)[1]
    for t in THRESHOLDS:
        ans = top >= t
        out["selective"][repr(t)] = {
            "answered": float(ans.mean()), "n_answered": int(ans.sum()),
            "errors": int((hit[ans] == 0).sum()),
            "precision": float(hit[ans].mean()) if ans.any() else float("nan"),
            "precision_se": ratio_se(np.bincount(groups, weights=ans & (hit == 0)), np.bincount(groups, weights=ans))}
    size, member = credible_sets(post)
    out["credible"] = {"level": CREDIBLE, "mean_size": float(size.mean()),
                       "share_singleton": float((size == 1).mean()),
                       "coverage": float(member[np.arange(len(truth)), truth].mean())}
    if not detail:
        return out
    q = mapq(top)
    out["mapq"] = {"median": float(np.median(q)), "share_ge_20": float((q >= 20).mean()),
                   "share_ge_30": float((q >= 30).mean())}
    out["calibration"] = calibration(top, hit)
    out["by_start"] = {}
    for k in range(post.shape[1]):
        sel = truth == k
        out["by_start"][LEVELS[k]] = {"exact": float(hit[sel].mean()),
                                      "answered_099": float((top[sel] >= 0.99).mean()),
                                      "precision_099": float(hit[sel & (top >= 0.99)].mean())
                                      if (sel & (top >= 0.99)).any() else float("nan")}
    if n % 2 == 1:
        h = n // 2
        out["by_centre"] = {LEVELS[k + h]: out["by_start"][LEVELS[k]] for k in range(post.shape[1])}
    out["landmarks"] = {}
    for name, (a, b) in LANDMARKS.items():
        ia, ib = LEVELS.index(a), LEVELS.index(b)
        sel = (truth <= ia) & (truth + n - 1 >= ib) if name != "mid_thoracic" else \
            (truth >= ia) & (truth + n - 1 <= ib)
        if sel.any():
            out["landmarks"][name] = {"n_fields": int(sel.sum()), "exact": float(hit[sel].mean()),
                                      "answered_099": float((top[sel] >= 0.99).mean()),
                                      "errors": int((hit[sel] == 0).sum())}
    out["confusion_offsets"] = {str(d): int(c) for d, c in
                                zip(*np.unique(call - truth, return_counts=True))}
    return out


def calibration(top: np.ndarray, hit: np.ndarray, edges=(0.0, 0.5, 0.7, 0.9, 0.99, 0.999, 1.0001)) -> List[dict]:
    """The posterior of the named place against how often it was right, by bins of the posterior:
    the outside check of the selective guarantee on fresh draws."""
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = (top >= lo) & (top < hi)
        rows.append({"lo": lo, "hi": min(hi, 1.0), "n": int(sel.sum()),
                     "mean_posterior": float(top[sel].mean()) if sel.any() else float("nan"),
                     "correct": float(hit[sel].mean()) if sel.any() else float("nan")})
    return rows


# ---- coarse claims: "below L1", "above T4", "lumbar" ---------------------------------------------

CLAIM_WIDTHS = (1, 2, 3, 5, 9)
CLAIM_SUBSET_WIDTHS = (1, 3)
CLAIM_LEVEL = 0.99
REGION_INDEX = np.array(["CTL".index(P.region_of(lv)) for lv in LEVELS])
REGION_NAMES = ("cervical", "thoracic", "lumbar")
CUT_NAMES = ["%s/%s" % (LEVELS[c - 1], LEVELS[c]) for c in range(1, L)]


def target_offset(n: int) -> int:
    """Which body of the field a claim is about: the middle one, the upper of the two middle ones
    when n is even."""
    return (n - 1) // 2


def target_posterior(post: np.ndarray, n: int) -> np.ndarray:
    """The posterior over the target body's level, (fields, 22): the place posterior moved along by
    the target's position in the field."""
    t = target_offset(n)
    out = np.zeros((post.shape[0], L))
    out[:, t:t + post.shape[1]] = post
    return out


def cut_decisions(tp: np.ndarray, level: float = CLAIM_LEVEL) -> Tuple[np.ndarray, np.ndarray]:
    """For every boundary c (between LEVELS[c-1] and LEVELS[c]): +1 where the field says the target
    is at or below LEVELS[c] with probability at least `level`, -1 where it says at or above
    LEVELS[c-1], 0 where it says neither; and P(at or below LEVELS[c]). Both (fields, 21)."""
    below = 1.0 - np.cumsum(tp, axis=1)[:, :-1]
    say = np.where(below >= level, 1, np.where(below <= 1.0 - level, -1, 0))
    return say, below


def region_decisions(tp: np.ndarray, level: float = CLAIM_LEVEL) -> np.ndarray:
    """The region the field says the target is in with probability at least `level`, -1 for none."""
    mass = np.stack([tp[:, REGION_INDEX == r].sum(1) for r in range(3)], axis=1)
    return np.where(mass.max(1) >= level, mass.argmax(1), -1)


def shortest_intervals(tp: np.ndarray, level: float = CLAIM_LEVEL) -> Tuple[np.ndarray, np.ndarray]:
    """The shortest run of consecutive levels holding `level` of the target's posterior: its first
    level and its width, (fields,) each; the most specific claim of that kind the field supports."""
    cs = np.concatenate([np.zeros((tp.shape[0], 1)), np.cumsum(tp, axis=1)], axis=1)
    start = np.full(tp.shape[0], -1)
    width = np.zeros(tp.shape[0], int)
    for w in range(1, L + 1):
        mass = cs[:, w:] - cs[:, :-w]
        best = mass.argmax(1)
        ok = (width == 0) & (mass[np.arange(len(tp)), best] >= level - 1e-12)
        start[ok], width[ok] = best[ok], w
    return start, width


def open_cuts(n: int) -> List[int]:
    """The boundaries the target can fall on either side of. The middle body of a field of n can
    only be a level with (n - 1) // 2 bodies above it in the column and n // 2 below, so a boundary
    outside that range is settled by the field's size alone and is left out of every rate."""
    t = target_offset(n)
    return [c for c in range(1, L) if t < c < t + (L - n + 1)]


def claims_summary(post: np.ndarray, truth: np.ndarray, n: int, detail: bool = True) -> dict:
    """What a field of n bodies lets one say about its middle body at probability 0.99, for every
    boundary, every region and the shortest interval, against the truth."""
    tp = target_posterior(post, n)
    lev = truth + target_offset(n)
    say, _ = cut_decisions(tp)
    out: dict = {"target": "body %d of %d" % (target_offset(n) + 1, n), "level": CLAIM_LEVEL, "cuts": {}}
    present = np.unique(lev)
    for c in open_cuts(n):
        truly_below = lev >= c
        dec = say[:, c - 1] != 0
        wrong = dec & ((say[:, c - 1] == 1) != truly_below)
        near = np.abs(lev - (c - 0.5)) <= 2.0
        nd, ne = int((dec & near).sum()), int((wrong & near).sum())
        row = {"decided": float(dec.mean()), "n_decided": int(dec.sum()), "errors": int(wrong.sum()),
               "precision": float(1.0 - wrong.sum() / dec.sum()) if dec.any() else float("nan"),
               "n_within_two": int(near.sum()), "n_decided_within_two": nd, "errors_within_two": ne,
               "decided_within_two": float(dec[near].mean()) if near.any() else float("nan"),
               "precision_within_two": float(1.0 - ne / nd) if nd else float("nan")}
        if detail:
            row["decided_by_level"] = {LEVELS[i]: float(dec[lev == i].mean()) for i in present}
        out["cuts"][CUT_NAMES[c - 1]] = row
    reg = region_decisions(tp)
    true_reg = REGION_INDEX[lev]
    dec = reg >= 0
    out["regions"] = {"decided": float(dec.mean()), "errors": int((dec & (reg != true_reg)).sum()),
                      "n_decided": int(dec.sum())}
    if detail:
        out["regions"]["decided_by_level"] = {LEVELS[i]: float(dec[lev == i].mean()) for i in present}
    a, w = shortest_intervals(tp)
    cover = (lev >= a) & (lev < a + w)
    out["interval"] = {"coverage": float(cover.mean()), "mean_width": float(w.mean()),
                       "share_width": {str(k): float((w == k).mean()) for k in (1, 2, 3)},
                       "share_width_le_5": float((w <= 5).mean())}
    if detail:
        out["interval"]["median_width_by_level"] = {LEVELS[i]: float(np.median(w[lev == i])) for i in present}
    return out


# ---- A and B: every width, every measure subset -------------------------------------------------

def subset_list(nm: int) -> List[Tuple[int, ...]]:
    return [c for k in range(1, nm + 1) for c in itertools.combinations(range(nm), k)]


def width_study(V: np.ndarray, mu: np.ndarray, sd: np.ndarray, synth: dict, n: int,
                measures: Sequence[str], keep: Dict[str, Sequence[int]], chunk: int = CHUNK) -> dict:
    """Every subset of the measures at one width, on the same fields, chunk by chunk of columns;
    the named subsets in `keep` (the three regimes) scored in full detail."""
    _, logw = quadrature(synth["scale_sd"])
    subs = subset_list(len(measures))
    K = L - n + 1
    nc = V.shape[0]
    with_claims = n in CLAIM_SUBSET_WIDTHS
    tallies = {s: {"hit": np.zeros(nc), "w1": 0, "top": 0.0, "n": 0,
                   "ans": {t: [0, 0] for t in THRESHOLDS}, "size": 0.0, "cover": 0,
                   "cut_dec": np.zeros(L - 1), "cut_err": np.zeros(L - 1), "reg_dec": 0, "reg_err": 0,
                   "near_dec": np.zeros(L - 1), "near_n": np.zeros(L - 1), "near_err": np.zeros(L - 1),
                   "width": 0.0} for s in subs}
    kept = {name: [] for name in keep}
    truths, groups = [], []
    for c0 in range(0, nc, chunk):
        X, truth, grp = fields(V[c0:c0 + chunk], n)
        grp = grp + c0
        LL = field_loglik(X, mu, sd, synth)
        # subsets walked depth first, each sum the parent's plus one measure, so at most seven
        # partial sums are alive at once
        stack: List[Tuple[Tuple[int, ...], np.ndarray]] = [((m,), LL[:, :, m, :]) for m in reversed(range(len(measures)))]
        while stack:
            s, acc = stack.pop()
            post = posterior(logsumexp(acc + logw, axis=2))
            call, top = post.argmax(1), post.max(1)
            hit = call == truth
            t = tallies[s]
            np.add.at(t["hit"], grp, hit)
            t["w1"] += int((np.abs(call - truth) <= 1).sum())
            t["top"] += float(top.sum())
            t["n"] += len(truth)
            for th in THRESHOLDS:
                a = top >= th
                t["ans"][th][0] += int(a.sum())
                t["ans"][th][1] += int(hit[a].sum())
            size, member = credible_sets(post)
            t["size"] += float(size.sum())
            t["cover"] += int(member[np.arange(len(truth)), truth].sum())
            if with_claims:
                tp = target_posterior(post, n)
                lev = truth + target_offset(n)
                say, _ = cut_decisions(tp)
                below = lev[:, None] >= np.arange(1, L)[None, :]
                wrong = (say != 0) & ((say == 1) != below)
                t["cut_dec"] += (say != 0).sum(0)
                t["cut_err"] += wrong.sum(0)
                # the bodies the border is hard for: the middle body within two levels of it
                near = np.abs(lev[:, None] - (np.arange(1, L)[None, :] - 0.5)) <= 2.0
                t["near_dec"] += ((say != 0) & near).sum(0)
                t["near_n"] += near.sum(0)
                t["near_err"] += (wrong & near).sum(0)
                # boundaries the field's size settles are dropped when the tallies are written
                reg = region_decisions(tp)
                t["reg_dec"] += int((reg >= 0).sum())
                t["reg_err"] += int(((reg >= 0) & (reg != REGION_INDEX[lev])).sum())
                t["width"] += float(shortest_intervals(tp)[1].sum())
            for name, idx in keep.items():
                if tuple(idx) == s:
                    kept[name].append(post)
            for m in reversed(range(s[-1] + 1, len(measures))):
                stack.append((s + (m,), acc + LL[:, :, m, :]))
        truths.append(truth)
        groups.append(grp)
    truth = np.concatenate(truths)
    group = np.concatenate(groups)
    out = {"n": n, "places": K, "subsets": [], "regimes": {}}
    for s in subs:
        t = tallies[s]
        rates = t["hit"] / K
        out["subsets"].append({
            "measures": [measures[i] for i in s], "k": len(s),
            "exact": float(t["hit"].sum() / t["n"]),
            "se_cluster": float(rates.std(ddof=1) / math.sqrt(nc)) if nc > 1 else float("nan"),
            "within_one": t["w1"] / t["n"],
            "bayes_error_predicted": 1.0 - t["top"] / t["n"],
            "answered_099": t["ans"][0.99][0] / t["n"],
            "precision_099": (t["ans"][0.99][1] / t["ans"][0.99][0]) if t["ans"][0.99][0] else float("nan"),
            "answered_0999": t["ans"][0.999][0] / t["n"],
            "precision_0999": (t["ans"][0.999][1] / t["ans"][0.999][0]) if t["ans"][0.999][0] else float("nan"),
            "credible_mean_size": t["size"] / t["n"], "credible_coverage": t["cover"] / t["n"]})
        if with_claims:
            out["subsets"][-1]["claims"] = {
                "cuts_decided": {CUT_NAMES[c - 1]: float(t["cut_dec"][c - 1] / t["n"]) for c in open_cuts(n)},
                "cuts_errors": {CUT_NAMES[c - 1]: int(t["cut_err"][c - 1]) for c in open_cuts(n)},
                "cuts_decided_within_two": {CUT_NAMES[c - 1]: float(t["near_dec"][c - 1] / t["near_n"][c - 1])
                                            for c in open_cuts(n) if t["near_n"][c - 1]},
                "cuts_errors_within_two": {CUT_NAMES[c - 1]: int(t["near_err"][c - 1]) for c in open_cuts(n)},
                "regions_decided": t["reg_dec"] / t["n"], "regions_errors": t["reg_err"],
                "interval_mean_width": t["width"] / t["n"]}
    out["subsets"].sort(key=lambda r: (-r["exact"], r["k"]))
    for rank, r in enumerate(out["subsets"], 1):
        r["rank"] = rank
    for name, posts in kept.items():
        post = np.concatenate(posts)
        out["regimes"][name] = summary(post, truth, group, n, detail=True)
        out["regimes"][name]["measures"] = [measures[i] for i in keep[name]]
        if n in CLAIM_WIDTHS:
            out["regimes"][name]["claims"] = claims_summary(post, truth, n)
    return out


# ---- C: the formula and the classifiers ----------------------------------------------------------

def formula_study(V: np.ndarray, mu: np.ndarray, sd: np.ndarray, synth: dict, widths: Sequence[int],
                  regime_idx: Sequence[int]) -> Dict[str, dict]:
    out = {}
    for n in widths:
        X, truth, grp = fields(V[:, list(regime_idx), :], n)
        post = posterior(formula_log_evidence(X, mu[list(regime_idx)], sd[list(regime_idx)], synth))
        out[str(n)] = summary(post, truth, grp, n, detail=False)
    return out


def classifier_rates(identify_json: Optional[str]) -> Dict[str, dict]:
    """The earlier study's fitted linear classifier on the same scoring seed, read from its record
    (odd widths, both planes and each plane), so the exact rule is set beside what was fitted."""
    if not identify_json or not os.path.exists(identify_json):
        return {}
    with open(identify_json) as fh:
        d = json.load(fh)
    out: Dict[str, dict] = {}
    for c in d.get("cells", []):
        out.setdefault(c["regime"], {})[str(c.get("visible_bodies", 2 * c["half"] + 1))] = {
            "exact": c["exact"], "se_cluster": c["se_cluster"], "within_one": c["within_one"]}
    return out


CHALLENGER_WIDTHS = (1, 3, 5, 9)
CHALLENGER_FIT = 5000
CHALLENGER_SELECT = 1000
CHALLENGER_HIDDEN = 64
NETWORK_MAX_STEPS = 3000
NETWORK_CHECK_EVERY = 100


def fitted_qda(Yfit: np.ndarray, tfit: np.ndarray, places: int, ridge: float = 1e-6):
    """One Gaussian per place in the features given, its mean and covariance estimated from the fit
    columns."""
    stats = []
    for k in range(places):
        z = Yfit[tfit == k]
        cov = np.cov(z.T) + ridge * np.eye(z.shape[1])
        stats.append((z.mean(0), np.linalg.cholesky(cov)))
    return stats


def qda_log_evidence(stats, Y: np.ndarray) -> np.ndarray:
    out = np.empty((len(Y), len(stats)))
    for k, (m, Lc) in enumerate(stats):
        Z = np.linalg.solve(Lc, (Y - m).T)
        out[:, k] = -0.5 * ((Z * Z).sum(0) + 2.0 * np.log(np.diag(Lc)).sum())
    return out


def train_network(Yf: np.ndarray, tf: np.ndarray, Ys: np.ndarray, ts: np.ndarray, k: int,
                  hidden: int = CHALLENGER_HIDDEN, max_steps: int = NETWORK_MAX_STEPS,
                  check_every: int = NETWORK_CHECK_EVERY, lr: float = 0.01, l2: float = 1e-4, seed: int = 0):
    """neighbour_more's solution H (standardised features, one tanh layer, a softmax over the
    places) trained by full-batch Adam with the same settings, kept at the step whose log loss on
    the selection columns is lowest: a network this size learns the fit columns' noise before it
    stops learning the rule, so without early stopping it is held back by overfitting, not by its
    size. Returns the probability function, the step kept and the selection losses."""
    t0 = time.perf_counter()
    rng = np.random.default_rng(seed)
    mu, sdv = Yf.mean(0), Yf.std(0)
    sdv[sdv == 0] = 1.0
    X, Xs = (Yf - mu) / sdv, (Ys - mu) / sdv
    n, p = X.shape
    Y = np.zeros((n, k))
    Y[np.arange(n), tf] = 1.0
    params = [rng.normal(0, 1.0 / math.sqrt(p), (p, hidden)), np.zeros(hidden),
              rng.normal(0, 1.0 / math.sqrt(hidden), (hidden, k)), np.zeros(k)]
    m1 = [np.zeros_like(q) for q in params]
    m2 = [np.zeros_like(q) for q in params]
    b1_, b2_, eps = 0.9, 0.999, 1e-8

    def probs(A, prm):
        return NB.softmax(np.tanh(A @ prm[0] + prm[1]) @ prm[2] + prm[3])

    best, best_step, losses = None, 0, []
    for t in range(1, max_steps + 1):
        W1, b1, W2, b2 = params
        H = np.tanh(X @ W1 + b1)
        dZ = (NB.softmax(H @ W2 + b2) - Y) / n
        dH = (dZ @ W2.T) * (1.0 - H * H)
        grads = [X.T @ dH + l2 * W1, dH.sum(0), H.T @ dZ + l2 * W2, dZ.sum(0)]
        for j in range(4):
            m1[j] = b1_ * m1[j] + (1 - b1_) * grads[j]
            m2[j] = b2_ * m2[j] + (1 - b2_) * grads[j] * grads[j]
            params[j] = params[j] - lr * (m1[j] / (1 - b1_ ** t)) / (np.sqrt(m2[j] / (1 - b2_ ** t)) + eps)
        if t % check_every == 0:
            ps = probs(Xs, params)
            loss = float(-np.log(np.maximum(ps[np.arange(len(ts)), ts], 1e-300)).mean())
            losses.append(loss)
            if best is None or loss < min(losses[:-1], default=np.inf):
                best, best_step = [q.copy() for q in params], t
    seconds = time.perf_counter() - t0
    return (lambda A: probs((A - mu) / sdv, best)), best_step, losses, seconds


def chunked_posterior(X: np.ndarray, mu: np.ndarray, sd: np.ndarray, synth: dict, n: int) -> np.ndarray:
    """The exact rule's posterior over many fields, CHUNK columns' fields at a time."""
    _, logw = quadrature(synth["scale_sd"])
    step = CHUNK * (L - n + 1)
    return np.concatenate([posterior(log_evidence(field_loglik(X[i:i + step], mu, sd, synth), logw))
                           for i in range(0, len(X), step)])


def challenger_study(ref, measures: Sequence[str], synth: dict, V: np.ndarray, mu: np.ndarray, sd: np.ndarray,
                     widths: Sequence[int] = CHALLENGER_WIDTHS, n_fit: int = CHALLENGER_FIT,
                     n_select: int = CHALLENGER_SELECT) -> Dict[str, dict]:
    """The outside check of the ceiling: rules fitted on many more columns than the earlier studies
    used, from the fitting seed (and, for the network's early stopping, the selection seed), never
    the scoring one, scored on the same fields as the exact rule: a quadratic rule in the log
    measures (whose limit with unlimited data is one Gaussian per place, the log values' true mean
    and covariance, which the closed form of C approximates), the same in the raw measures, and a network with one hidden layer. Each is set beside the exact rule
    with the paired difference and its standard error clustered by column. If any named the
    fields better than the exact rule beyond that error, the exact rule would be wrong; that none
    does is a weaker check than the calibration of section A, since a fitted rule falls short for
    reasons of its own. The closed form of C is set beside it the same way, with its paired error."""
    fit = column_values(NB.draw_columns(ref, ["typical"], NB.FIT_SEED, n_fit, measures), measures)
    sel = column_values(NB.draw_columns(ref, ["typical"], NB.SELECT_SEED, n_select, measures), measures)
    out = {"n_fit": n_fit, "n_select": n_select, "fit_seed": NB.FIT_SEED, "select_seed": NB.SELECT_SEED,
           "hidden": CHALLENGER_HIDDEN, "max_steps": NETWORK_MAX_STEPS, "check_every": NETWORK_CHECK_EVERY}
    for n in widths:
        Xf, tf, _ = fields(fit, n)
        Xs, ts, _ = fields(sel, n)
        X, truth, grp = fields(V, n)
        places = L - n + 1
        flat = lambda A: A.reshape(len(A), -1)                          # noqa: E731
        posts = {"exact": chunked_posterior(X, mu, sd, synth, n),
                 "closed_form": posterior(formula_log_evidence(X, mu, sd, synth)),
                 "qda_log": posterior(qda_log_evidence(fitted_qda(np.log(flat(Xf)), tf, places), np.log(flat(X)))),
                 "qda_raw": posterior(qda_log_evidence(fitted_qda(flat(Xf), tf, places), flat(X)))}
        net, step, losses, secs = train_network(np.log(flat(Xf)), tf, np.log(flat(Xs)), ts, places)
        posts["network"] = net(np.log(flat(X)))
        row = {name: summary(p, truth, grp, n, False) for name, p in posts.items()}
        row["network"].update({"step_kept": step, "selection_log_loss": losses, "fit_seconds": round(secs, 1)})
        hit_e = (posts["exact"].argmax(1) == truth).astype(float)
        ll_e = -np.log(np.maximum(posts["exact"][np.arange(len(truth)), truth], 1e-300))
        for name in ("closed_form", "qda_log", "qda_raw", "network"):
            hit = (posts[name].argmax(1) == truth).astype(float)
            ll = -np.log(np.maximum(posts[name][np.arange(len(truth)), truth], 1e-300))
            row[name]["minus_exact"] = float((hit - hit_e).mean())
            row[name]["minus_exact_se"] = NB.clustered_se(hit - hit_e, grp)
            row[name]["log_loss_minus_exact"] = float((ll - ll_e).mean())
            row[name]["log_loss_minus_exact_se"] = NB.clustered_se(ll - ll_e, grp)
        out[str(n)] = row
    return out


def _challenger_job(args) -> Dict[str, dict]:
    return challenger_study(*args)


# ---- D: when the generator is not the truth ------------------------------------------------------

def redrawn_table(ref, measures: Sequence[str], rng, mode: str, synth: dict) -> dict:
    """A table the rule might have been built on instead of the published one. "levels": each
    level's mean redrawn from N(mean, SD / sqrt 12) and its SD as the SD a twelve-spine estimate
    could have come from, the printed SD over sqrt(chi^2_11 / 11), independently across levels
    (a real table's errors are shared across levels by its twelve specimens); "specimens": twelve
    columns drawn from the generator with no size spread and no measurement error (the generator
    adds both to the table's SD, so the SD is re-estimated without them), and the table
    re-estimated from them, so the errors are shared across levels by each specimen's own
    offsets, as a real table's are. A real table's SDs hold its cadavers' own spread of size too,
    which a rule then counts twice, on the safe side; the specimens here hold none."""
    out = {m: dict(ref[m]) for m in ref}
    if mode == "levels":
        for m in measures:
            for lv in LEVELS:
                a, b = ref[m][lv]
                out[m][lv] = (max(a + rng.normal(0.0, b / math.sqrt(12)), 0.5),
                              b / math.sqrt(rng.chisquare(11) / 11.0))
        return out
    if mode == "specimens":
        # no size spread and no error in the specimens: the table's SD is the generator's sd,
        # the spread the size and the error are added to, so it is re-estimated without them
        spec = NB.draw_columns(ref, ["typical"], int(rng.integers(1 << 30)), 12, measures,
                               **dict(synth, noise_mm=0.0, scale_sd=0.0))
        vals = column_values(spec, measures)
        for i, m in enumerate(measures):
            for j, lv in enumerate(LEVELS):
                out[m][lv] = (float(vals[:, i, j].mean()), float(vals[:, i, j].std(ddof=1)))
        return out
    raise ValueError(mode)


def biased_table(ref, measures: Sequence[str], kind: str) -> dict:
    """A population, or a segmenter, whose means differ systematically from the printed table's:
    "gradient" scales every mean by 1 + 0.05 j / 21 from C3 (j = 0) to L5 (j = 21), a size trend
    down the column; "canal_low" puts both canal measures 8 per cent low. The columns are drawn
    from this table and the rule is built on the printed one."""
    out = {m: dict(ref[m]) for m in ref}
    for m in measures:
        for j, lv in enumerate(LEVELS):
            a, b = ref[m][lv]
            if kind == "gradient":
                f = 1.0 + 0.05 * j / (L - 1)
            elif kind == "canal_low":
                f = 0.92 if m.startswith("canal") else 1.0
            else:
                raise ValueError(kind)
            out[m][lv] = (a * f, b * f)
    return out


# The rules scored where their premise fails, each built on the same table and scored on the same
# columns. "nominal" is the rule of A to C, built on the table as printed. "predictive" knows its
# table is the mean and SD of twelve spines: the spread of a new spine about a twelve-spine mean
# and SD is a Student t on eleven degrees of freedom whose variance is (1 + 1/12) 11/9 times the
# SD squared, and this rule takes that variance (a Gaussian, so the closed form still holds) and
# no constant chosen on any draw. "honest" takes the mean's share of it, (1 + 1/12), which is exact
# for the means, and meets the SDs' error with a floor instead, the measurement error taken at
# 2 mm where the generator draws 1 mm; the 2 mm was chosen on the pilot (robust.pilot: sixteen
# specimen worlds from PILOT_SEED, the variants of PILOT_RULES), so its worlds from seed 29 test
# the choice against fresh draws of the same model, not against a different one, and the 3 mm
# world tests it past the error it assumes.
RULES = {"nominal": {}, "predictive": {"table_n": 12, "t_df": 11}, "honest": {"table_n": 12, "noise_mm": 2.0}}
PILOT_SEED = 5
PILOT_WORLDS = 16
PILOT_WIDTHS = (1, 3, 9)
PILOT_RULES = {"nominal": {}, "table_error": {"table_n": 12}, "table_error_1.5mm": {"table_n": 12, "noise_mm": 1.5},
               "table_error_2mm": {"table_n": 12, "noise_mm": 2.0}, "table_error_smoothed": {"table_n": 12, "smooth": True},
               "predictive": {"table_n": 12, "t_df": 11}}
MISSPEC = {"rho": (0.3, 0.7), "scale_sd": (0.035, 0.14), "noise_mm": (0.5, 2.0, 3.0), "r_between": (0.4, 0.8)}
MISSPEC_COLUMNS = 5            # times ROBUST_COLUMNS, one draw each
BIASES = ("gradient", "canal_low")
COMBINED_WORLDS = 20
COMBINED = {"r_between": 0.4, "noise_mm": 1.5}


def rule_table(ref, measures: Sequence[str], spec: dict) -> dict:
    """The table a rule variant is built on: its SDs smoothed and inflated as `spec` says."""
    out = {m: dict(ref[m]) for m in ref}
    f = math.sqrt(1.0 + 1.0 / spec["table_n"]) if spec.get("table_n") else 1.0
    if spec.get("t_df"):
        f *= math.sqrt(spec["t_df"] / (spec["t_df"] - 2.0))
    for m in measures:
        var = np.array([ref[m][lv][1] ** 2 for lv in LEVELS])
        if spec.get("smooth"):
            var = np.array([var[max(0, j - 1):j + 2].mean() for j in range(L)])
        for j, lv in enumerate(LEVELS):
            out[m][lv] = (ref[m][lv][0], math.sqrt(var[j]) * f)
    return out


def rule_synth(synth: dict, spec: dict) -> dict:
    return dict(synth, noise_mm=spec.get("noise_mm", synth["noise_mm"]))


def cut_tally(post: np.ndarray, truth: np.ndarray, n: int) -> Dict[str, List[int]]:
    """At every open border: [decided, errors, fields, decided within two, errors within two,
    fields within two], within two meaning the middle body lies within two levels of the border,
    where a claim is hard."""
    say, _ = cut_decisions(target_posterior(post, n))
    lev = truth + target_offset(n)
    out = {}
    for c in open_cuts(n):
        dec = say[:, c - 1] != 0
        wrong = dec & ((say[:, c - 1] == 1) != (lev >= c))
        near = np.abs(lev - (c - 0.5)) <= 2.0
        out[CUT_NAMES[c - 1]] = [int(dec.sum()), int(wrong.sum()), int(len(truth)),
                                 int((dec & near).sum()), int((wrong & near).sum()), int(near.sum())]
    return out


def near_claims_by_group(post: np.ndarray, truth: np.ndarray, group: np.ndarray, n: int) -> Tuple[np.ndarray, np.ndarray]:
    """Claims made and claims wrong within two levels of their border, summed over the open
    borders, for each group of fields (a column), so the precision near the border has a
    standard error within one world."""
    say, _ = cut_decisions(target_posterior(post, n))
    lev = truth + target_offset(n)
    g = np.unique(group, return_inverse=True)[1]
    made, wrong = np.zeros(g.max() + 1), np.zeros(g.max() + 1)
    for c in open_cuts(n):
        near = np.abs(lev - (c - 0.5)) <= 2.0
        dec = (say[:, c - 1] != 0) & near
        bad = dec & ((say[:, c - 1] == 1) != (lev >= c))
        made += np.bincount(g, weights=dec, minlength=len(made))
        wrong += np.bincount(g, weights=bad, minlength=len(made))
    return made, wrong


def robust_cell(rule_ref, data_ref, measures: Sequence[str], rule_synth_: dict, data_synth: dict,
                widths: Sequence[int], n_columns: int, seed: int, r_data: float = 0.0,
                r_rule: float = 0.0, subsets: Sequence[Tuple[int, ...]] = ()) -> Dict[str, dict]:
    """The rule built on one table and generator, scored on columns drawn from another; with
    `subsets`, the border claims of each subset of the measures too, at the claim widths of B."""
    cols = NB.draw_columns(data_ref, ["typical"], seed, n_columns, measures, r_between=r_data,
                           **{k: data_synth[k] for k in ("rho", "noise_mm", "scale_sd")})
    V = column_values(cols, measures)
    mu, sd = table_arrays(rule_ref, measures)
    _, logw = quadrature(rule_synth_["scale_sd"])
    out = {}
    for n in widths:
        posts, sub_posts, truths, groups = [], {s: [] for s in subsets}, [], []
        # chunk by chunk of columns, as width_study does, so four processes fit in memory
        for c0 in range(0, len(V), CHUNK):
            X, truth, grp = fields(V[c0:c0 + CHUNK], n)
            if abs(r_rule) > 1e-12:
                posts.append(posterior(joint_log_evidence(X, mu, sd, rule_synth_, r_rule)))
            else:
                LL = field_loglik(X, mu, sd, rule_synth_)
                posts.append(posterior(log_evidence(LL, logw)))
                if n in CLAIM_SUBSET_WIDTHS:
                    for s in subsets:
                        sub_posts[s].append(posterior(log_evidence(LL, logw, s)))
            truths.append(truth)
            groups.append(grp + c0)
        post, truth, grp = np.concatenate(posts), np.concatenate(truths), np.concatenate(groups)
        out[str(n)] = summary(post, truth, grp, n, detail=False)
        if n in CLAIM_WIDTHS:
            cl = claims_summary(post, truth, n, detail=False)
            made, wrong = near_claims_by_group(post, truth, grp, n)
            out[str(n)]["claims"] = {"cuts": cut_tally(post, truth, n),
                                     "within_two_se_by_column": ratio_se(wrong, made),
                                     "regions_decided": cl["regions"]["n_decided"],
                                     "regions_errors": cl["regions"]["errors"], "fields": len(truth),
                                     "interval_coverage": cl["interval"]["coverage"],
                                     "interval_mean_width": cl["interval"]["mean_width"]}
        if subsets and abs(r_rule) <= 1e-12 and n in CLAIM_SUBSET_WIDTHS:
            out[str(n)]["subset_cuts"] = {"+".join(measures[i] for i in s): cut_tally(np.concatenate(sub_posts[s]), truth, n)
                                          for s in subsets}
    return out


def ratio_se(errors: Sequence[int], answered: Sequence[int]) -> float:
    """The standard error of a pooled error rate whose fields come in worlds that share a table:
    the ratio estimator's, clustered by world."""
    e, a = np.asarray(errors, float), np.asarray(answered, float)
    w = len(a)
    if w < 2 or a.sum() == 0:
        return float("nan")
    r = e - (e.sum() / a.sum()) * a
    return float(math.sqrt(w / (w - 1.0) * (r * r).sum()) / a.sum())


def _sum_cuts(dicts: List[Dict[str, List[int]]]) -> Dict[str, dict]:
    out = {}
    for cut in dicts[0]:
        t = np.array([d[cut] for d in dicts])
        dec, err, nf, nd, ne, nn = t.sum(0)
        out[cut] = {"decided": dec / nf, "n_decided": int(dec), "errors": int(err),
                    "precision": (1.0 - err / dec) if dec else float("nan"),
                    "n_within_two": int(nn), "n_decided_within_two": int(nd), "errors_within_two": int(ne),
                    "decided_within_two": nd / nn if nn else float("nan"),
                    "precision_within_two": (1.0 - ne / nd) if nd else float("nan"),
                    "precision_within_two_se": ratio_se(t[:, 4], t[:, 3])}
    return out


def _pool_claims(rows: List[dict]) -> dict:
    per_world = [np.array(list(r["claims"]["cuts"].values())).sum(0) for r in rows]
    T = np.array(per_world)                                       # worlds by the six counts
    cuts = _sum_cuts([r["claims"]["cuts"] for r in rows])
    dec, err, nf, nd, ne, nn = T.sum(0)
    rd = sum(r["claims"]["regions_decided"] for r in rows)
    re_ = sum(r["claims"]["regions_errors"] for r in rows)
    nfi = sum(r["claims"]["fields"] for r in rows)
    return {"cuts": cuts, "cuts_decided": dec / nf, "cuts_precision": (1.0 - err / dec) if dec else float("nan"),
            "cuts_errors": int(err), "cuts_precision_se": ratio_se(T[:, 1], T[:, 0]),
            "cuts_decided_within_two": nd / nn if nn else float("nan"),
            "cuts_precision_within_two": (1.0 - ne / nd) if nd else float("nan"),
            "cuts_errors_within_two": int(ne), "cuts_n_decided_within_two": int(nd),
            "cuts_precision_within_two_se": ratio_se(T[:, 4], T[:, 3]) if len(rows) > 1
            else rows[0]["claims"].get("within_two_se_by_column", float("nan")),
            "regions_decided": rd / nfi, "regions_precision": (1.0 - re_ / rd) if rd else float("nan"),
            "regions_errors": int(re_),
            "interval_coverage": float(np.mean([r["claims"]["interval_coverage"] for r in rows])),
            "interval_mean_width": float(np.mean([r["claims"]["interval_mean_width"] for r in rows]))}


def pool_cells(cells: List[Dict[str, dict]]) -> Dict[str, dict]:
    """Worlds pooled: the mean rate with its spread over worlds, and the precision reached at each
    threshold over every answered field of every world, with its standard error clustered by
    world (by column where there is one world). The pooled precision averages over worlds; it is
    not a promise about any one table."""
    out = {}
    for n in cells[0]:
        rows = [c[n] for c in cells]
        ex = np.array([r["exact"] for r in rows])
        d = {"worlds": len(rows), "exact_mean": float(ex.mean()), "exact_p05": float(np.percentile(ex, 5)),
             "exact_p95": float(np.percentile(ex, 95)),
             "bayes_error_predicted_mean": float(np.mean([r["bayes_error_predicted"] for r in rows])),
             "log_loss_mean": float(np.mean([r["log_loss"] for r in rows])), "selective": {}}
        for t in THRESHOLDS:
            sel = [r["selective"][repr(t)] for r in rows]
            na = sum(x["n_answered"] for x in sel)
            ne = sum(x["errors"] for x in sel)
            d["selective"][repr(t)] = {"answered": float(np.mean([x["answered"] for x in sel])), "n_answered": na,
                                       "errors": ne, "precision": (1.0 - ne / na) if na else float("nan"),
                                       "precision_se": ratio_se([x["errors"] for x in sel], [x["n_answered"] for x in sel])
                                       if len(sel) > 1 else sel[0].get("precision_se", float("nan"))}
        d["selective_099_by_called_region"] = {}
        for name in REGION_NAMES:
            sel = [r["selective_099_by_called_region"][name] for r in rows]
            na = sum(x["n_answered"] for x in sel)
            ne = sum(x["errors"] for x in sel)
            d["selective_099_by_called_region"][name] = {
                "n_answered": na, "errors": ne, "precision": (1.0 - ne / na) if na else float("nan"),
                "precision_se": ratio_se([x["errors"] for x in sel], [x["n_answered"] for x in sel])}
        d["credible_coverage_mean"] = float(np.mean([r["credible"]["coverage"] for r in rows]))
        if all("claims" in r for r in rows):
            d["claims"] = _pool_claims(rows)
        if all("subset_cuts" in r for r in rows):
            d["subset_cuts"] = {k: _sum_cuts([r["subset_cuts"][k] for r in rows]) for k in rows[0]["subset_cuts"]}
        out[n] = d
    return out


ROBUST_SUBSETS = [s for s in subset_list(len(MEASURES7)) if len(s) <= 2]


def robust_tasks(n_worlds: int = ROBUST_WORLDS, seed: int = 29) -> List[tuple]:
    """Every robustness cell as a task, its seeds drawn here, each kind from a stream of its own
    (the single settings and the biases share one, as do the specimen and level worlds), so the
    record depends neither on which process runs which task nor, for one kind, on how many tasks
    another kind has. The single large draws come first, so no process is left with one at the
    end."""
    s_mis, s_tab, s_com, s_r = (np.random.default_rng([seed, k]) for k in range(4))
    s_pil = np.random.default_rng(PILOT_SEED)
    tasks = []
    for key, values in [("none", (0.0,))] + list(MISSPEC.items()):
        for v in values:
            tasks.append(("misspecified", key, v, int(s_mis.integers(1 << 30))))
    for kind in BIASES:
        tasks.append(("bias", kind, 0.0, int(s_mis.integers(1 << 30))))
    for v in MISSPEC["r_between"]:
        tasks.append(("r_known", "r_between", v, int(s_r.integers(1 << 30))))
    for mode in ("specimens", "levels"):
        for w in range(n_worlds):
            tasks.append(("table", mode, w, int(s_tab.integers(1 << 30)), int(s_tab.integers(1 << 30))))
    for w in range(COMBINED_WORLDS):
        tasks.append(("combined", "specimens", w, int(s_com.integers(1 << 30)), int(s_com.integers(1 << 30))))
    for w in range(PILOT_WORLDS):
        tasks.append(("pilot", "specimens", w, int(s_pil.integers(1 << 30)), int(s_pil.integers(1 << 30))))
    return tasks


def robust_task(task: tuple, ref, measures: Sequence[str], synth: dict, widths=ROBUST_WIDTHS,
                n_columns: int = ROBUST_COLUMNS) -> Tuple[tuple, Dict[str, dict]]:
    """One task, every rule variant on the same columns (common random numbers)."""
    kind = task[0]
    out = {}
    if kind in ("table", "combined", "pilot"):
        _, mode, _, world_seed, col_seed = task
        drawn = redrawn_table(ref, measures, np.random.default_rng(world_seed), mode, synth)
        # specimens: the rule is built on the re-estimated table, the columns come from the
        # published one; levels: the rule is the published table's, the columns a redrawn one's
        rule_ref, data_ref = (drawn, ref) if mode == "specimens" else (ref, drawn)
        data_synth, r_data = dict(synth), 0.0
        if kind == "combined":
            data_synth["noise_mm"], r_data = COMBINED["noise_mm"], COMBINED["r_between"]
        rules = PILOT_RULES if kind == "pilot" else RULES
        ws = PILOT_WIDTHS if kind == "pilot" else widths
        subs = ROBUST_SUBSETS if kind == "table" and mode == "specimens" else ()
        for name, spec in rules.items():
            out[name] = robust_cell(rule_table(rule_ref, measures, spec), data_ref, measures, rule_synth(synth, spec),
                                    data_synth, ws, n_columns, col_seed, r_data=r_data, subsets=subs)
        return task, out
    _, key, v, col_seed = task
    data_ref, data_synth, r_data = ref, dict(synth), 0.0
    if kind == "bias":
        data_ref = biased_table(ref, measures, key)
    elif key == "r_between":
        r_data = v
    elif key != "none":
        data_synth[key] = v
    if kind == "r_known":
        # the correlation known to the rule: the joint likelihood at the data's r
        out["nominal"] = robust_cell(ref, ref, measures, synth, synth, widths, n_columns * 4, col_seed,
                                     r_data=v, r_rule=v)
        return task, out
    for name, spec in RULES.items():
        out[name] = robust_cell(rule_table(ref, measures, spec), data_ref, measures, rule_synth(synth, spec),
                                data_synth, widths, n_columns * MISSPEC_COLUMNS, col_seed, r_data=r_data)
    return task, out


def gather_robust(results: List[Tuple[tuple, Dict[str, dict]]], n_worlds: int,
                  widths=ROBUST_WIDTHS, n_columns: int = ROBUST_COLUMNS) -> dict:
    """Every kind of world in one shape, pooled over its worlds by rule: [kind][world][rule][n]
    for single draws, [kind][rule][n] for the pooled ones."""
    out: Dict[str, dict] = {"widths": list(widths), "worlds": n_worlds, "columns_per_world": n_columns,
                            "misspecified_columns": n_columns * MISSPEC_COLUMNS, "rules": RULES,
                            "pilot_rules": PILOT_RULES, "pilot_seed": PILOT_SEED, "pilot_widths": list(PILOT_WIDTHS),
                            "combined": COMBINED, "subsets_scored_in_specimen_worlds": len(ROBUST_SUBSETS)}
    results = sorted(results, key=lambda r: tuple(str(x) for x in r[0]))

    def pooled(kind, mode=None):
        cells = [r for t, r in results if t[0] == kind and (mode is None or t[1] == mode)]
        return {name: pool_cells([c[name] for c in cells]) for name in cells[0]} if cells else {}

    out["table_specimens"] = pooled("table", "specimens")
    out["table_levels"] = pooled("table", "levels")
    out["combined_worlds"] = pooled("combined")
    out["pilot"] = pooled("pilot")
    out["misspecified"], out["bias"], out["r_known"] = {}, {}, {}
    for t, r in results:
        if t[0] == "misspecified":
            out["misspecified"]["none" if t[1] == "none" else "%s=%g" % (t[1], t[2])] = \
                {name: pool_cells([c]) for name, c in r.items()}
        elif t[0] == "bias":
            out["bias"][t[1]] = {name: pool_cells([c]) for name, c in r.items()}
        elif t[0] == "r_known":
            out["r_known"]["r_between=%g" % t[2]] = pool_cells([r["nominal"]])
    return out


# ---- checks -------------------------------------------------------------------------------------

def trapezoid(scale_sd: float, n_nodes: int = TRAPEZOID_NODES, half_width: float = TRAPEZOID_HALF_WIDTH):
    """An independent rule for the same integral: the trapezoid on an even grid in log s out to
    half_width SDs, the prior density folded into the weights."""
    t = np.linspace(-half_width * scale_sd, half_width * scale_sd, n_nodes)
    h = t[1] - t[0]
    logw = math.log(h) - 0.5 * (t / scale_sd) ** 2 - math.log(scale_sd * math.sqrt(2.0 * math.pi))
    logw[[0, -1]] += math.log(0.5)
    return np.exp(t), logw


def evidence_lean(X: np.ndarray, mu: np.ndarray, sd: np.ndarray, synth: dict, sizes: np.ndarray,
                  logw: np.ndarray) -> np.ndarray:
    """log_evidence over all measures, one place at a time, so a rule with many nodes fits in
    memory: (fields, places)."""
    n = X.shape[2]
    return np.stack([logsumexp(place_loglik(X, mu, sd, k, sizes, synth["rho"], synth["noise_mm"]).sum(1) + logw,
                               axis=1) for k in range(L - n + 1)], axis=1)


def quadrature_check(V: np.ndarray, mu: np.ndarray, sd: np.ndarray, synth: dict,
                     widths=(1, 3, 5, 9, 15, 21), nodes=(41, 81, GH_NODES)) -> dict:
    """The one numerical step measured: the posterior with Gauss-Hermite rules of several sizes
    against the trapezoid rule on a fine grid, an independent rule for the same integral."""
    out = {"used": GH_NODES, "reference": "trapezoid, %d nodes over +-%g SD" % (TRAPEZOID_NODES, TRAPEZOID_HALF_WIDTH),
           "max_abs_posterior_difference": {}, "calls_changed": {}}
    tz = trapezoid(synth["scale_sd"])
    for n in widths:
        X, _, _ = fields(V, n)
        b = posterior(evidence_lean(X, mu, sd, synth, *tz))
        out["max_abs_posterior_difference"][str(n)] = {}
        out["calls_changed"][str(n)] = {}
        for J in nodes:
            a = posterior(evidence_lean(X, mu, sd, synth, *quadrature(synth["scale_sd"], J)))
            out["max_abs_posterior_difference"][str(n)][str(J)] = float(np.abs(a - b).max())
            out["calls_changed"][str(n)][str(J)] = int((a.argmax(1) != b.argmax(1)).sum())
    return out


def joint_check(V: np.ndarray, mu: np.ndarray, sd: np.ndarray, synth: dict, widths=(1, 4, 9)) -> dict:
    """The closed form against the dense joint density at r = 0: the largest difference in the log
    evidence, which must be rounding."""
    out = {}
    for n in widths:
        X, _, _ = fields(V, n)
        _, logw = quadrature(synth["scale_sd"])
        a = log_evidence(field_loglik(X, mu, sd, synth), logw)
        b = joint_log_evidence(X, mu, sd, synth, 0.0)
        out[str(n)] = float(np.abs(a - b).max())
    return out


def floor_hits(V: np.ndarray, measures: Sequence[str]) -> dict:
    hits = np.argwhere(V <= 0.5 + 1e-12)
    return {"values": int(len(hits)), "of": int(V.size),
            "columns": int(len(np.unique(hits[:, 0]))) if len(hits) else 0,
            "where": sorted({"%s %s" % (measures[h[1]], LEVELS[h[2]]) for h in hits})}


# ---- the run ------------------------------------------------------------------------------------

def _width_job(args) -> Tuple[int, dict]:
    V, mu, sd, synth, n, measures, keep = args
    t = time.time()
    out = width_study(V, mu, sd, synth, n, measures, keep)
    out["seconds"] = round(time.time() - t, 1)
    return n, out


def _robust_job(args) -> Tuple[tuple, Dict[str, dict]]:
    task, ref, measures, synth, n_columns = args
    return robust_task(task, ref, measures, synth, n_columns=n_columns)


def save(rec: dict, outdir: Optional[str]) -> None:
    """Write the record as it stands, through a temporary file, so a run cut short leaves every
    part it finished and never a half-written file; `complete` says whether it is the last write."""
    if not outdir:
        return
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "exact.json")
    with open(path + ".tmp", "w", newline="\n") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True, default=NB._jsonable)
        fh.write("\n")
    os.replace(path + ".tmp", path)


def _result(job, what: str):
    """A part's result, or a record of why it failed: one part's failure costs that part alone."""
    try:
        return job.result()
    except Exception as exc:                                     # noqa: BLE001 - recorded, not hidden
        print("exact: %s failed: %s: %s" % (what, type(exc).__name__, exc), flush=True)
        return {"error": "%s: %s" % (type(exc).__name__, exc)}


def run(outdir: Optional[str] = None, n_score: int = N_SCORE, widths: Sequence[int] = WIDTHS,
        robust: bool = True, n_worlds: int = ROBUST_WORLDS, identify_json: Optional[str] = None,
        processes: int = PROCESSES, quick: bool = False, robust_columns: int = ROBUST_COLUMNS) -> dict:
    """The widths are independent of each other and of the robustness worlds, so they run side by
    side in separate processes (set OMP_NUM_THREADS=1 so they do not fight over the cores); every
    draw is seeded, so the record does not depend on the order they finish in. The record is
    written after the widths and after each later part, with `complete` false until the last."""
    from concurrent.futures import ProcessPoolExecutor
    t0 = time.time()
    measures = list(MEASURES7)
    synth = dict(rho=NB.SYNTH["rho"], noise_mm=NB.SYNTH["noise_mm"], scale_sd=NB.SYNTH["scale_sd"])
    ref = P.load_reference(measures=measures)
    mu, sd = table_arrays(ref, measures)
    cols = NB.draw_columns(ref, ["typical"], SCORE_SEED, n_score, measures)
    V = column_values(cols, measures)
    keep = {name: sorted(measures.index(m) for m in ms) for name, ms in REGIMES.items()}
    rec: dict = {"study": "exact", "measures": measures, "levels": LEVELS, "synth": synth,
                 "score_seed": SCORE_SEED, "n_columns": n_score, "gh_nodes": GH_NODES,
                 "thresholds": list(THRESHOLDS), "credible": CREDIBLE, "claim_level": CLAIM_LEVEL,
                 "regimes": {k: list(v) for k, v in REGIMES.items()}, "quick": bool(quick), "complete": False,
                 "python": sys.version.split()[0], "numpy": np.__version__,
                 "floor": floor_hits(V, measures), "widths": {}, "finished_after_seconds": {}}

    def done(part: str) -> None:
        rec["finished_after_seconds"][part] = round(time.time() - t0, 1)
        rec["seconds"] = round(time.time() - t0, 1)
        save(rec, outdir)

    cw = [n for n in CHALLENGER_WIDTHS if n in widths]
    with ProcessPoolExecutor(max_workers=max(1, processes)) as pool:
        jobs = {n: pool.submit(_width_job, (V, mu, sd, synth, n, measures, keep)) for n in sorted(widths)}
        chal = pool.submit(_challenger_job, (ref, measures, synth, V, mu, sd, cw, 500 if quick else CHALLENGER_FIT,
                                             200 if quick else CHALLENGER_SELECT))
        rob = [pool.submit(_robust_job, (t, ref, measures, synth, robust_columns)) for t in robust_tasks(n_worlds)] \
            if robust else []
        rec["formula"] = {name: formula_study(V, mu, sd, synth, widths, keep[name]) for name in keep}
        rec["classifier"] = classifier_rates(identify_json)
        rec["quadrature_check"] = quadrature_check(V[:100], mu, sd, synth)
        rec["joint_check"] = joint_check(V[:50], mu, sd, synth)
        done("checks")
        for n, job in jobs.items():
            got = _result(job, "width %d" % n)
            out = got[1] if isinstance(got, tuple) else got
            rec["widths"][str(n)] = out
            if "error" not in out:
                print("exact: n=%d done in %.0f s (both planes %.4f)" % (n, out["seconds"], out["regimes"]["both"]["exact"]),
                      flush=True)
        done("widths")
        if rob:
            got = [_result(j, "robustness task") for j in rob]
            failed = [g for g in got if isinstance(g, dict)]
            try:
                rec["robust"] = gather_robust([g for g in got if isinstance(g, tuple)], n_worlds,
                                              n_columns=robust_columns)
            except Exception as exc:                             # noqa: BLE001 - recorded, not hidden
                rec["robust"] = {"error": "%s: %s" % (type(exc).__name__, exc)}
            rec["robust"]["failed_tasks"] = [g["error"] for g in failed]
            print("exact: robustness done, %d tasks, %d failed" % (len(rob), len(failed)), flush=True)
            done("robust")
        rec["challengers"] = _result(chal, "challengers")
        print("exact: challengers done", flush=True)
        done("challengers")
    rec["complete"] = True
    done("all")
    return rec
