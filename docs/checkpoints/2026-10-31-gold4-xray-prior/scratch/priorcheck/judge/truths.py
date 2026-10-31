"""Synthetic truths over the 22 x 5 cells of C3..L5 for the prototype (scratch)."""
import json
import numpy as np
from schwingcheck import correlation as CORR

LEVELS = CORR.expand_levels("C3..L5")
L, M = 22, 5
EP, EPD, EPL, EPLD, HP = range(5)


def published(name="prior-enhance_pet-C3-L5.json"):
    p = json.load(open(name))
    rl, rm = np.array(p["r_level"]), np.array(p["r_measure"])
    unshrink = lambda r: (r - 0.05 * np.eye(len(r))) / 0.95
    return unshrink(rl), unshrink(rm)


def corr(cov):
    d = np.sqrt(np.diag(cov))
    return cov / np.outer(d, d)


def c(l, m):
    return l * M + m


def truth(kind, rl0, rm0):
    base = np.kron(rl0, rm0)
    if kind == "separable":
        return base
    if kind == "shared":
        return corr(0.85 * base + 0.15 * np.ones_like(base))
    if kind == "person":
        a = np.ones(L)
        B = np.full((M, M), 0.8)
        B[HP, :] = B[:, HP] = 0.5
        np.fill_diagonal(B, 1.0)
        cm = 0.6 * rm0 + 0.4 * np.eye(M)
        return corr(np.kron(np.outer(a, a), 0.35 * B) + 0.65 * np.kron(rl0, cm))
    if kind == "regional":
        rm = rm0.copy()
        rm[EP, EPL] = rm[EPL, EP] = 0.15
        cov = np.kron(rl0, rm)
        for l in range(5):
            for i, j in ((EP, EP), (EPL, EPL), (EP, EPL), (EPL, EP)):
                cov[c(l, i), c(l, j)] += 1.5
        return corr(cov)
    if kind == "disc":
        cov = base.copy()
        for l in range(L - 1):
            for lo, up in ((EPL, EP), (EPLD, EPD)):
                i, j = c(l, lo), c(l + 1, up)
                cov[i, j] += 0.4
                cov[j, i] += 0.4
                cov[i, i] += 0.4
                cov[j, j] += 0.4
        return corr(cov)
    if kind == "vertebra":
        W = np.full((M, M), 0.8)
        W[HP, :] = W[:, HP] = 0.3
        np.fill_diagonal(W, 1.0)
        return corr(base + 0.4 * np.kron(np.eye(L), W))
    raise ValueError(kind)


def draw(rng, cov, n, gross=0.0):
    x = rng.multivariate_normal(np.zeros(len(cov)), cov, size=n, method="cholesky").reshape(n, L, M)
    if gross:
        hit = rng.random(x.shape) < gross
        x = np.where(hit, x + 6.0 * np.sign(rng.normal(size=x.shape)), x)
    return 30.0 + 3.0 * x
