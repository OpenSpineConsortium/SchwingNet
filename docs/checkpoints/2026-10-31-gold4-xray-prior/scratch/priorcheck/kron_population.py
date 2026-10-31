"""What Dutilleul's flip-flop (as in SchwingNet grid/prior/schwingcheck/correlation.py) returns
when handed a known population covariance that is, or is not, a Kronecker product. Synthetic
structures only; no data is read. The flip-flop's sums over spines are replaced by the
population covariance itself, so this is the fit's large-sample limit."""
import numpy as np

def to_corr(c):
    d = np.sqrt(np.diag(c)); r = c / np.outer(d, d); np.fill_diagonal(r, 1.0); return (r + r.T) / 2

def flip_flop_pop(S4, steps=2000, tol=1e-12):
    L, M = S4.shape[0], S4.shape[1]
    sl, sm = np.eye(L), np.eye(M)
    for _ in range(steps):
        im = np.linalg.inv(sm)
        sl_new = np.einsum("lmjk,mk->lj", S4, im) / M
        il = np.linalg.inv(sl_new)
        sm_new = np.einsum("lmkj,lk->mj", S4, il) / L
        done = np.abs(sl_new - sl).max() < tol and np.abs(sm_new - sm).max() < tol
        sl, sm = sl_new, sm_new
        if done: break
    return to_corr(sl), to_corr(sm)

def corr4(cov, L, M):
    return to_corr(cov).reshape(L, M, L, M)

def report(name, cov, L, M):
    S4 = corr4(cov, L, M)
    rl, rm = flip_flop_pop(S4)
    same_level = np.mean([S4[l, 0, l, 1] for l in range(L)])
    lag1_same_measure = np.mean([S4[l, 0, l + 1, 0] for l in range(L - 1)])
    lag1_cross = np.mean([S4[l, 0, l + 1, 1] for l in range(L - 1)])
    print("%-58s true: same-level r(m0,m1) %.3f, lag-1 same measure %.3f, lag-1 cross %.3f | fit: R_measure[0,1] %.3f, R_level lag-1 %.3f"
          % (name, same_level, lag1_same_measure, lag1_cross, rm[0, 1], np.mean(np.diag(rl, 1))))

L, M = 22, 5   # C3..L5 and the five measures
idx = np.arange(L)
ar = lambda rho: rho ** np.abs(idx[:, None] - idx[None, :])

# 1. A true Kronecker product: the fit should give it back.
RL = 0.35 + 0.65 * ar(0.6); RM = np.full((M, M), 0.6); np.fill_diagonal(RM, 1)
report("1 Kronecker (R_level 0.35+0.65*AR0.6, R_measure 0.6)", np.kron(RL, RM), L, M)

# 2. One person-size factor on every cell, nothing else: every pair r = c.
for c in (0.3, 0.5):
    cov = (1 - c) * np.eye(L * M) + c * np.ones((L * M, L * M))
    report("2 one shared factor, every pair r=%.1f" % c, cov, L, M)

# 3. A person factor (loading a) on every cell, a per-vertebra factor (loading b) shared by
#    the vertebra's five measures and correlated AR(0.6) along the column, and cell noise.
for a2, b2 in ((0.25, 0.35), (0.15, 0.45), (0.30, 0.20)):
    e2 = 1 - a2 - b2
    cov = a2 * np.ones((L * M, L * M)) + b2 * np.kron(ar(0.6), np.ones((M, M))) + e2 * np.eye(L * M)
    report("3 person a2=%.2f + vertebra b2=%.2f (AR0.6) + noise %.2f" % (a2, b2, e2), cov, L, M)

# 4. Case 3 plus a measure-specific level factor (same measure, AR along the column),
#    which is what makes same-measure correlations exceed cross-measure ones across levels.
for a2, b2, s2 in ((0.15, 0.25, 0.25), (0.10, 0.35, 0.20)):
    e2 = 1 - a2 - b2 - s2
    cov = (a2 * np.ones((L * M, L * M)) + b2 * np.kron(ar(0.6), np.ones((M, M)))
           + s2 * np.kron(0.4 + 0.6 * ar(0.7), np.eye(M)) + e2 * np.eye(L * M))
    report("4 person %.2f + vertebra %.2f + measure-own %.2f + noise %.2f" % (a2, b2, s2, e2), cov, L, M)
