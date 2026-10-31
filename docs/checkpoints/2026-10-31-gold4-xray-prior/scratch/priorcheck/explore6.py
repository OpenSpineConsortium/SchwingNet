import sys, time
sys.path.insert(0, "/tmp/claude-0/-home-claude/3a9f8f67-4b49-5dd0-98ba-d0bd1c4358ce/scratchpad/priorcheck")
import numpy as np
import kron_sim as K
L, M = K.L, K.M
obs = K.observed_targets()
e = obs["enhance_C3L5"]; e2 = obs["enhance_T1L5"]
TL, TM = K.unshrink(e.r_level), K.unshrink(e.r_measure)
TM2 = K.unshrink(e2.r_measure)
t0 = time.time()
r = K.match_regional(TL, TM, TM2)
print("regional ok", r["ok"], "iters", r["iters"], "err %.1e" % r["err"], "%.1fs" % (time.time()-t0))
np.set_printoptions(precision=3, suppress=True)
print("cervical measure correlation needed (unshrunk):\n", r["b_cervical"])
print("thoracolumbar (= T1..L5 fit, unshrunk):\n", TM2)
sig = r["sigma"]
ts = K.truth_stats(sig)
print({k: (np.round(v, 3) if isinstance(v, float) else np.round(v, 3).tolist()) for k, v in ts.items()})
sub = K.sub_levels(sig, range(K.T1_AT, L))
rl2, rm2 = K.projected_prior(sub, L-K.T1_AT)
print("T1L5 projection R_M:\n", rm2, "\nobserved T1L5:\n", e2.r_measure)
print("T1L5 lag", np.round(K.lag_profile(rl2), 3), "observed", np.round(K.lag_profile(e2.r_level), 3))
print("C3L5 fitted check:", np.abs(K.projected_prior(sig)[1] - e.r_measure).max())
print("gain %.2f gap %.2f" % (K.population_gain_over_assumed(sig, e.r_level, e.r_measure), K.population_kl_gap(sig, e.r_level, e.r_measure)))
# same-level by region
sl_c = K.same_level(sig, K.CERV); sl_t = K.same_level(sig, range(K.T1_AT, L))
print("same-level cervical:\n", sl_c, "\nsame-level T1..L5:\n", sl_t)
