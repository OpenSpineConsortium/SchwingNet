"""Scratch prototype of the prior check the grid job would run (not a repository file).

Everything is computed from z, the fit part's whole spines standardised per cell exactly as
correlation.fit does, and from the fitted prior as drawn (shrunk). C is the sample correlation of
the L x M cells (levels-major, as vec(X)); K is kron(r_level, r_measure) as drawn. Each statistic is
a mean of entries of C, compared with the same mean of K, and judged against a parametric bootstrap
that draws n spines from the unshrunk fitted Kronecker and runs the same pipeline (fit, shrink).
"""
from __future__ import annotations

import hashlib
import math
import statistics
import time

import numpy as np

from schwingcheck import correlation as CORR

MEASURES = ["endplate", "endplate_depth", "endplate_lower", "endplate_lower_depth", "h_post"]
EP, EPD, EPL, EPLD, HP = range(5)
PAIRS = [(i, j) for i in range(5) for j in range(i + 1, 5)]
PLATE = [k for k, (i, j) in enumerate(PAIRS) if j < 4]          # the six end-plate pairs
SHRINK = 0.05


def level_regions(levels):
    named = [("C3-C7", ["C%d" % i for i in range(3, 8)]), ("T1", ["T1"]),
             ("T2-T12", ["T%d" % i for i in range(2, 13)]), ("L1-L4", ["L%d" % i for i in range(1, 5)]), ("L5", ["L5"])]
    out = {}
    for name, names in named:
        idx = [levels.index(l) for l in names if l in levels]
        if idx:
            out[name] = idx
    return out


def adjacent_regions(levels):
    """Adjacent pairs (l, l+1) grouped: inside the neck, across C7-T1-T2, the thorax, T12 to L4, L4-L5."""
    groups = {"C3-C7": [], "C7-T2": [], "T2-T12": [], "T12-L4": [], "L4-L5": []}
    for i in range(len(levels) - 1):
        a, b = levels[i], levels[i + 1]
        if a.startswith("C") and b.startswith("C"):
            groups["C3-C7"].append(i)
        elif a in ("C7", "T1"):
            groups["C7-T2"].append(i)
        elif a.startswith("T") and b.startswith("T"):
            groups["T2-T12"].append(i)
        elif a == "L4":
            groups["L4-L5"].append(i)
        else:
            groups["T12-L4"].append(i)
    return {k: v for k, v in groups.items() if v}


def cell(l, m, M=5):
    return l * M + m


def sample_corr(z):
    n = len(z)
    flat = z.reshape(n, -1)
    return flat.T @ flat / (n - 1)


def drawn_prior(z):
    """(r_level, r_measure) unshrunk, and K as drawn (both factors shrunk), from standardised z."""
    rl, rm = CORR.flip_flop(z)
    return rl, rm, np.kron(CORR.shrunk(rl, SHRINK), CORR.shrunk(rm, SHRINK))


# ---- the statistics, each a function of a correlation matrix S (C or K) over the cells ----

def same_level(S, idx, i, j, M=5):
    return float(np.mean([S[cell(l, i, M), cell(l, j, M)] for l in idx]))


def lag1(S, adj, i, j, M=5):
    """mean over adjacent pairs (l, l+1) of S[(l,i),(l+1,j)]"""
    return float(np.mean([S[cell(l, i, M), cell(l + 1, j, M)] for l in adj]))


def contrast_lag1(S, adj, c, M=5):
    c = np.asarray(c, float)
    out = []
    for l in adj:
        a = S[l * M:(l + 1) * M, l * M:(l + 1) * M]
        b = S[(l + 1) * M:(l + 2) * M, (l + 1) * M:(l + 2) * M]
        x = S[l * M:(l + 1) * M, (l + 1) * M:(l + 2) * M]
        out.append(c @ x @ c / math.sqrt((c @ a @ c) * (c @ b @ c)))
    return float(np.mean(out))


def long_range(S, A, B, cross, M=5, measures=range(5)):
    vals = []
    for l in A:
        for k in B:
            for i in measures:
                for j in measures:
                    if (i != j) == cross:
                        vals.append(S[cell(l, i, M), cell(k, j, M)])
    return float(np.mean(vals))


def statistics_of(S, levels):
    """Every statistic the report prints, as a flat dict name -> value, for one correlation matrix."""
    reg, adj = level_regions(levels), adjacent_regions(levels)
    out = {}
    every = list(range(len(levels)))
    for k, (i, j) in enumerate(PAIRS):
        for r, idx in list(reg.items()) + [("all", every)]:
            out["same %d %s" % (k, r)] = same_level(S, idx, i, j)
    out["same plate all"] = float(np.mean([out["same %d all" % k] for k in PLATE]))
    core_adj = [i for r in ("T2-T12", "T12-L4") for i in adj.get(r, [])]
    for m in range(5):
        for r, a in list(adj.items()) + [("core", core_adj)]:
            out["lag1 %d %s" % (m, r)] = lag1(S, a, m, m)
    if core_adj:
        vals = [out["lag1 %d core" % m] for m in range(5)]
        out["lag1 range core"] = max(vals) - min(vals)
        out["facing widths"] = lag1(S, core_adj, EPL, EP)
        out["far widths"] = lag1(S, core_adj, EP, EPL)
        out["facing depths"] = lag1(S, core_adj, EPLD, EPD)
        out["far depths"] = lag1(S, core_adj, EPD, EPLD)
        out["facing minus far widths"] = out["facing widths"] - out["far widths"]
        out["facing minus far depths"] = out["facing depths"] - out["far depths"]
        out["contrast size"] = contrast_lag1(S, core_adj, [1, 1, 1, 1, 0])
        out["contrast width difference"] = contrast_lag1(S, core_adj, [1, 0, -1, 0, 0])
        out["contrast depth difference"] = contrast_lag1(S, core_adj, [0, 1, 0, -1, 0])
        out["contrast size minus differences"] = out["contrast size"] - 0.5 * (
            out["contrast width difference"] + out["contrast depth difference"])
    if "C3-C7" in reg and "L1-L4" in reg:
        out["long cross C x L"] = long_range(S, reg["C3-C7"], reg["L1-L4"], True)
        out["long same C x L"] = long_range(S, reg["C3-C7"], reg["L1-L4"], False)
    core = [i for r in ("T2-T12", "L1-L4") for i in reg.get(r, [])]
    if core:
        far = [(a, b) for a in core for b in core if b - a >= 6]
        if far:
            out["long cross core lag6"] = float(np.mean([S[cell(a, i), cell(b, j)] for a, b in far for i in range(5) for j in range(5) if i != j]))
    return out


# ---- refits over sub-ranges of the same spines ----

def refit_measure(z, idx):
    _, rm = CORR.flip_flop(z[:, idx, :])
    return np.array([rm[i, j] for i, j in PAIRS])


def subsets(levels):
    out = {}
    for name, (a, b) in (("T1..L5", ("T1", "L5")), ("C3..C7", ("C3", "C7")), ("T2..L4", ("T2", "L4"))):
        if a in levels and b in levels:
            idx = list(range(levels.index(a), levels.index(b) + 1))
            if len(idx) < len(levels):
                out[name] = idx
    return out


# ---- normal scores ----

_ND = statistics.NormalDist()


def normal_scores(values):
    """Each cell's values (n spines) replaced by Blom normal scores of their ranks."""
    n = values.shape[0]
    ranks = values.argsort(axis=0).argsort(axis=0).astype(float) + 1.0
    q = (ranks - 0.375) / (n + 0.25)
    table = np.array([_ND.inv_cdf(p) for p in ((np.arange(1, n + 1) - 0.375) / (n + 0.25))])
    return table[(ranks - 1).astype(int)]


# ---- the person effect plus Kronecker model, by EM ----

def person_effect(z, steps=400, tol=1e-8):
    """x_n = a u_n^T + E_n with u_n ~ N(0, B) over measures and E_n ~ MN(0, CL, CM), by EM;
    returns (a, B, CL, CM, cov), a scaled to unit root mean square and CL to unit mean diagonal."""
    n, L, M = z.shape
    rl, rm = CORR.flip_flop(z)
    a, B = np.ones(L), 0.2 * np.eye(M)
    CL, CM = 0.8 * rl, rm.copy()
    last = -np.inf
    for it in range(steps):
        iL, iM = np.linalg.inv(CL), np.linalg.inv(CM)
        V = np.linalg.inv(np.linalg.inv(B) + float(a @ iL @ a) * iM)
        mu = np.einsum("mk,kj,nlj,lq,q->nm", V, iM, z, iL, a, optimize=True)
        e = np.einsum("nm,mk,nk->n", mu, iM, mu, optimize=True) + np.trace(iM @ V)
        a_new = np.einsum("nlm,mk,nk->l", z, iM, mu, optimize=True) / e.sum()
        B_new = mu.T @ mu / n + V
        R = z - np.einsum("l,nm->nlm", a_new, mu)
        CL_new = (np.einsum("nlm,mk,njk->lj", R, iM, R, optimize=True) + n * np.outer(a_new, a_new) * np.trace(iM @ V)) / (n * M)
        iLn = np.linalg.inv(CL_new)
        CM_new = (np.einsum("nlm,lk,nkj->mj", R, iLn, R, optimize=True) + n * float(a_new @ iLn @ a_new) * V) / (n * L)
        s = math.sqrt(float(np.mean(a_new * a_new)))
        a, B = a_new / s, B_new * s * s
        t = float(np.trace(CL_new)) / L
        CL, CM = CL_new / t, CM_new * t
        if it % 10 == 9:
            cov = np.kron(np.outer(a, a), B) + np.kron(CL, CM)
            ll = float(CORR.mvn_loglik(z, cov).mean())
            if ll - last < tol * abs(ll):
                break
            last = ll
    cov = np.kron(np.outer(a, a), B) + np.kron(CL, CM)
    return a, B, CL, CM, cov


def as_correlation(cov):
    return CORR.to_correlation(cov)


# ---- held-out comparisons ----

def unit_fold(unit, k=5):
    return int(hashlib.sha256(("gold3-prior-check:" + unit).encode()).hexdigest()[:8], 16) % k


def kron_drawn(z):
    rl, rm = CORR.flip_flop(z)
    return np.kron(CORR.shrunk(rl, SHRINK), CORR.shrunk(rm, SHRINK))


def blended(z, w):
    return w * kron_drawn(z) + (1 - w) * sample_corr(z)


def person_drawn(z):
    cov = person_effect(z)[4]
    return (1 - SHRINK) * as_correlation(cov) + SHRINK * np.eye(cov.shape[0])


WEIGHTS = [round(0.05 * i, 2) for i in range(1, 21)]


def cv_scores(values, units, k=5):
    """Five-fold CV on the fit part (folds by unit): mean held-fold loglik per spine of K, P and the blend at each weight."""
    folds = np.array([unit_fold(u, k) for u in units])
    rows = []
    for f in range(k):
        tr, te = values[folds != f], values[folds == f]
        ztr, mean, sd = CORR.standardise(tr)
        zte, _, _ = CORR.standardise(te, mean, sd)
        Kd = kron_drawn(ztr)
        S = sample_corr(ztr)
        lk = CORR.mvn_loglik(zte, Kd)
        lp = CORR.mvn_loglik(zte, person_drawn(ztr))
        lb = [CORR.mvn_loglik(zte, w * Kd + (1 - w) * S) for w in WEIGHTS]
        rows.append((lk, lp, lb))
    lk = np.concatenate([r[0] for r in rows])
    lp = np.concatenate([r[1] for r in rows])
    lb = [np.concatenate([r[2][i] for r in rows]) for i in range(len(WEIGHTS))]
    best = int(np.argmax([x.mean() for x in lb]))
    def gain(x):
        d = x - lk
        return float(d.mean()), float(d.std(ddof=1) / math.sqrt(len(d)))
    return dict(w=WEIGHTS[best], blend=gain(lb[best]), person=gain(lp))


def held_scores(fit, held, w):
    zf, mean, sd = CORR.standardise(fit)
    zh, _, _ = CORR.standardise(held, mean, sd)
    Kd = kron_drawn(zf)
    lk = CORR.mvn_loglik(zh, Kd)
    out = {}
    for name, cov in (("blend", w * Kd + (1 - w) * sample_corr(zf)), ("person", person_drawn(zf))):
        d = CORR.mvn_loglik(zh, cov) - lk
        out[name] = (float(d.mean()), float(d.std(ddof=1) / math.sqrt(len(d))))
    return out


# ---- the null by parametric bootstrap ----

def draw_kron(rng, rl, rm, n):
    al, am = np.linalg.cholesky(rl), np.linalg.cholesky(rm)
    e = rng.normal(size=(n, len(rl), len(rm)))
    return np.einsum("lk,nkj,mj->nlm", al, e, am)


def null(rl0, rm0, n, levels, B=200, seed=20261031):
    rng = np.random.default_rng(seed)
    subs = subsets(levels)
    rows = []
    for b in range(B):
        x = draw_kron(rng, rl0, rm0, n)
        z, _, _ = CORR.standardise(x)
        rl, rm, K = drawn_prior(z)
        C = sample_corr(z)
        sc, sk = statistics_of(C, levels), statistics_of(K, levels)
        row = {k: sc[k] - sk[k] for k in sc}
        full = np.array([rm[i, j] for i, j in PAIRS])
        for name, idx in subs.items():
            d = refit_measure(z, idx) - full
            row["refit %s width pair" % name] = float(d[PAIRS.index((EP, EPL))])
            row["refit %s mean abs" % name] = float(np.mean(np.abs(d)))
        rows.append(row)
    keys = rows[0].keys()
    return {k: (float(np.mean([r[k] for r in rows])), float(np.std([r[k] for r in rows], ddof=1))) for k in keys}


def observed(z, levels):
    rl, rm, K = drawn_prior(z)
    C = sample_corr(z)
    sc, sk = statistics_of(C, levels), statistics_of(K, levels)
    row = {k: sc[k] - sk[k] for k in sc}
    raw = dict(sc)
    full = np.array([rm[i, j] for i, j in PAIRS])
    refits = {}
    for name, idx in subsets(levels).items():
        r = refit_measure(z, idx)
        refits[name] = r
        d = r - full
        row["refit %s width pair" % name] = float(d[PAIRS.index((EP, EPL))])
        row["refit %s mean abs" % name] = float(np.mean(np.abs(d)))
    return dict(misfit=row, raw=raw, drawn=sk, rl=rl, rm=rm, refits=refits)
