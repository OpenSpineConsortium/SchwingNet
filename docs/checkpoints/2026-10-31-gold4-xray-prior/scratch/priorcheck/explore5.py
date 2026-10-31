import sys, time
sys.path.insert(0, "/tmp/claude-0/-home-claude/3a9f8f67-4b49-5dd0-98ba-d0bd1c4358ce/scratchpad/priorcheck")
import numpy as np
import kron_sim as K
L, M = K.L, K.M
obs = K.observed_targets()
e = obs["enhance_C3L5"]; e2 = obs["enhance_T1L5"]
TL, TM = K.unshrink(e.r_level), K.unshrink(e.r_measure)
sep = K.Truth("a", K.chol_psd(np.kron(TL, TM)), np.zeros(L*M))
# sampling SD of (T1..L5 fit) - (C3..L5 fit) under the separable truth: 710 spines, the first 693 complete from C3
rng = np.random.default_rng(7)
d = []
t0 = time.time()
for r in range(40):
    v = sep.sample(rng, 710)
    rl, rm = K.grid_fit(v[:693])
    rl2, rm2 = K.grid_fit(v[:, K.T1_AT:, :], K.LEVELS[K.T1_AT:])
    d.append([rm2[0,2]-rm[0,2], rm2[1,3]-rm[1,3], rm2[0,1]-rm[0,1], rm2[0,3]-rm[0,3], rm2[1,2]-rm[1,2], rm2[2,3]-rm[2,3],
              K.lag_profile(rl2)[0] - np.mean(np.diag(rl[K.T1_AT:, K.T1_AT:], 1))])
d = np.array(d)
names = ["widths", "depths", "wd_up", "upW-loD", "upD-loW", "wd_low", "lag1(T1..L5 block)"]
obsd = [e2.r_measure[0,2]-e.r_measure[0,2], e2.r_measure[1,3]-e.r_measure[1,3], e2.r_measure[0,1]-e.r_measure[0,1],
        e2.r_measure[0,3]-e.r_measure[0,3], e2.r_measure[1,2]-e.r_measure[1,2], e2.r_measure[2,3]-e.r_measure[2,3],
        K.lag_profile(e2.r_level)[0] - np.mean(np.diag(e.r_level[K.T1_AT:, K.T1_AT:], 1))]
print("separable truth, 40 reps (%.0fs): T1..L5 minus C3..L5" % (time.time()-t0))
for i, nme in enumerate(names):
    print("  %-20s sim mean %+.4f sd %.4f | observed %+.3f  (z = %.1f)" % (nme, d[:,i].mean(), d[:,i].std(ddof=1), obsd[i], (obsd[i]-d[:,i].mean())/d[:,i].std(ddof=1)))
