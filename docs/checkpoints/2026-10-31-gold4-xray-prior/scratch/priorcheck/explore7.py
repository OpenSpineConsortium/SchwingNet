import sys, time
sys.path.insert(0, "/tmp/claude-0/-home-claude/3a9f8f67-4b49-5dd0-98ba-d0bd1c4358ce/scratchpad/priorcheck")
import numpy as np
import kron_sim as K
obs = K.observed_targets(); e = obs["enhance_C3L5"]
lag = K.lag_profile(e.r_level)
for fixed in ({"a2": 0.0}, {"a2": 0.1}, {"a2": 0.2}, {"a2": 0.3}, {"k2": 0.0}, {"k2": 0.15}):
    t0 = time.time()
    p, loss = K.tune(fixed, e.r_measure, lag, starts=3)
    t = K.tuned_truth("x", p)
    ts = K.truth_stats(t.sigma())
    rl, rm = K.projected_prior(t.sigma())
    print(fixed, "loss %.5f (%.0fs)" % (loss, time.time()-t0), {k: round(v, 3) for k, v in p.items()})
    print("   true S widths %.3f depths %.3f wd_up %.3f | lag1 %.3f lag5 %.3f | disc_w %.3f | fit Rm w %.3f d %.3f wdu %.3f wdl %.3f uWlD %.3f uDlW %.3f | lag %s" % (
        ts["same_level_widths"], ts["same_level_depths"], ts["same_level_width_depth_upper"], ts["lag_same_measure"][0], ts["lag_same_measure"][4],
        ts["disc_widths"], rm[0,2], rm[1,3], rm[0,1], rm[2,3], rm[0,3], rm[1,2], np.round(K.lag_profile(rl),3)))
print("observed: w %.3f d %.3f wdu %.3f wdl %.3f uWlD %.3f uDlW %.3f lag %s" % (e.r_measure[0,2], e.r_measure[1,3], e.r_measure[0,1], e.r_measure[2,3], e.r_measure[0,3], e.r_measure[1,2], np.round(lag,3)))
