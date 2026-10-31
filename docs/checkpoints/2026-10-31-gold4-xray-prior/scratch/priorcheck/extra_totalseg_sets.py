"""TotalSegmentator: how far apart sampling alone puts the C3..L5 fit (67 spines) and the T1..L5 fit
(69 spines, the 67 among them) under a separable truth with its published C3..L5 matrices."""
import sys, json
sys.path.insert(0, "/tmp/claude-0/-home-claude/3a9f8f67-4b49-5dd0-98ba-d0bd1c4358ce/scratchpad/priorcheck")
import numpy as np
import kron_sim as K
obs = K.observed_targets()
t, t1 = obs["totalseg_C3L5"], obs["totalseg_T1L5"]
truth = K.sigma_truth("ts_sep", np.kron(K.unshrink(t.r_level), K.unshrink(t.r_measure)))
rng = np.random.default_rng(9)
pairs = {"widths": (K.EP, K.EPL), "depths": (K.EPD, K.EPLD), "width_depth_upper": (K.EP, K.EPD),
         "width_depth_lower": (K.EPL, K.EPLD), "upperW_lowerD": (K.EP, K.EPLD), "upperD_lowerW": (K.EPD, K.EPL)}
rows = []
for _ in range(300):
    v = truth.sample(rng, 69)
    rl, rm = K.grid_fit(v[:67])
    rl1, rm1 = K.grid_fit(v[:, K.T1_AT:, :], K.LEVELS[K.T1_AT:])
    rows.append({k: rm1[a, b] - rm[a, b] for k, (a, b) in pairs.items()})
out = {}
for k, (a, b) in pairs.items():
    d = np.array([r[k] for r in rows])
    o = t1.r_measure[a, b] - t.r_measure[a, b]
    out[k] = {"sim_mean": round(float(d.mean()), 4), "sim_sd": round(float(d.std(ddof=1)), 4), "observed": round(float(o), 3),
              "z": round(float((o - d.mean()) / d.std(ddof=1)), 1)}
print(json.dumps(out, indent=1))
json.dump(out, open("/tmp/claude-0/-home-claude/3a9f8f67-4b49-5dd0-98ba-d0bd1c4358ce/scratchpad/priorcheck/results-totalseg-sets.json", "w"), indent=1)
