import sys, time
sys.path.insert(0, "/tmp/claude-0/-home-claude/3a9f8f67-4b49-5dd0-98ba-d0bd1c4358ce/scratchpad/priorcheck")
import numpy as np
import kron_sim as K
L, M = K.L, K.M
obs = K.observed_targets()
e = obs["enhance_C3L5"]; e2 = obs["enhance_T1L5"]
TL, TM = K.unshrink(e.r_level), K.unshrink(e.r_measure)

def delta_of(kind):
    if kind == "noise": return np.eye(L*M)
    if kind == "size": return np.ones((L*M, L*M))
    if kind == "vertebra": return np.kron(np.eye(L), np.ones((M, M)))
    if kind == "vertebra_wd":  # widths+depths of one vertebra move together, h_post alone
        w = np.eye(M); w[:4,:4] = 1.0
        return np.kron(np.eye(L), w)
    if kind == "disc":
        d = np.eye(L*M)
        for l in range(L-1):
            for a, b in ((K.EPL, K.EP), (K.EPLD, K.EPD)):
                i, j = K.cell(l, a), K.cell(l+1, b)
                d[i, j] = d[j, i] = 1.0
        return d
    raise ValueError(kind)

def match(delta, theta, iters=3000, eta=1.0, tol=1e-7):
    A, B = TL.copy(), TM.copy()
    start = None
    for it in range(iters):
        sig = (1-theta)*np.kron(A, B) + theta*delta
        pl, pm, _ = K.project(sig, L, start=start)
        el, em = TL - pl, TM - pm
        err = max(np.abs(el).max(), np.abs(em).max())
        if err < tol: return A, B, sig, it, err, True
        A = A + eta*el; B = B + eta*em
        np.fill_diagonal(A, 1); np.fill_diagonal(B, 1)
        if np.linalg.eigvalsh(A).min() < 1e-6 or np.linalg.eigvalsh(B).min() < 1e-6:
            return A, B, sig, it, err, False
    return A, B, sig, it, err, False

for kind in ["noise", "size", "vertebra", "vertebra_wd", "disc"]:
    d = delta_of(kind)
    for theta in [0.05, 0.1, 0.2, 0.3]:
        t0 = time.time()
        A, B, sig, it, err, ok = match(d, theta)
        ts = K.truth_stats(sig)
        # T1..L5 subset projection
        sub = K.sub_levels(sig, range(K.T1_AT, L))
        rl2, rm2 = K.projected_prior(sub, L-K.T1_AT)
        print("%-11s th=%.2f ok=%s it=%4d err=%.1e %.1fs | true S widths %.3f depths %.3f wd_up %.3f hp %.3f | lag1 %.3f lag5 %.3f | disc_w %.3f | T1L5 Rm widths %.3f depths %.3f wd_up %.3f lag1 %.3f" % (
            kind, theta, ok, it, err, time.time()-t0, ts["same_level_widths"], ts["same_level_depths"], ts["same_level_width_depth_upper"], ts["same_level_hpost_mean"],
            ts["lag_same_measure"][0], ts["lag_same_measure"][4], ts["disc_widths"], rm2[0,2], rm2[1,3], rm2[0,1], K.lag_profile(rl2)[0]))
print("observed T1L5: widths %.3f depths %.3f wd_up %.3f lag1 %.3f" % (e2.r_measure[0,2], e2.r_measure[1,3], e2.r_measure[0,1], K.lag_profile(e2.r_level)[0]))
print("separable truth (theta 0): fitted C3L5 widths %.3f depths %.3f wd_up %.3f" % (e.r_measure[0,2], e.r_measure[1,3], e.r_measure[0,1]))
