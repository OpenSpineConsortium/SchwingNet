import sys, time
sys.path.insert(0, "/tmp/claude-0/-home-claude/3a9f8f67-4b49-5dd0-98ba-d0bd1c4358ce/scratchpad/priorcheck")
import numpy as np
import kron_sim as K
obs = K.observed_targets()
e = obs["enhance_C3L5"]; e2 = obs["enhance_T1L5"]
TL, TM = K.unshrink(e.r_level), K.unshrink(e.r_measure)
for kind in ["noise", "size", "size_wd", "vertebra", "vertebra_wd", "disc", "cervical_widths"]:
    d = K.delta_kind(kind)
    t0 = time.time()
    th = K.max_feasible(d, TL, TM)
    print("%-16s max feasible theta %.3f (%.1fs)" % (kind, th, time.time()-t0))
    for theta in sorted(set([round(x,3) for x in (0.1, 0.2, th*0.98) if x <= th*0.98+1e-9])):
        r = K.match_core(d, theta, TL, TM)
        if not r["ok"]:
            print("   theta %.3f not matched err %.2e" % (theta, r["err"])); continue
        sig = r["sigma"]
        ts = K.truth_stats(sig)
        sub = K.sub_levels(sig, range(K.T1_AT, K.L))
        rl2, rm2 = K.projected_prior(sub, K.L-K.T1_AT)
        gain = K.population_gain_over_assumed(sig, e.r_level, e.r_measure)
        gap = K.population_kl_gap(sig, e.r_level, e.r_measure)
        print("   theta %.3f | S widths %.3f depths %.3f wd_up %.3f hp %.3f | lag1 %.3f lag5 %.3f | xboth1 %.3f disc_w %.3f disc_d %.3f | T1L5 Rm w %.3f d %.3f wdu %.3f lag1 %.3f | gain %.2f gap %.2f" % (
            theta, ts["same_level_widths"], ts["same_level_depths"], ts["same_level_width_depth_upper"], ts["same_level_hpost_mean"],
            ts["lag_same_measure"][0], ts["lag_same_measure"][4], ts["lag1_cross_wd4_not_facing"], ts["disc_widths"], ts["disc_depths"],
            rm2[0,2], rm2[1,3], rm2[0,1], K.lag_profile(rl2)[0], gain, gap))
sep = np.kron(TL, TM)
print("separable: gain %.2f" % K.population_gain_over_assumed(sep, e.r_level, e.r_measure))
print("observed T1L5: widths %.3f depths %.3f wd_up %.3f lag1 %.3f; observed gain 13.78 (SE 1.34)" % (e2.r_measure[0,2], e2.r_measure[1,3], e2.r_measure[0,1], K.lag_profile(e2.r_level)[0]))
