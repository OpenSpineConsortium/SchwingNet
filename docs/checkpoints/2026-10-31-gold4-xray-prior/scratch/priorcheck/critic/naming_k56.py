"""Critic's extension of the prior-use reader's reduced naming copy to k = 5 and 6 (typical column,
no anchor, true scorer): does the fitted R_measure against a width and depth pair of 0.8 move the
k at which top-1 reaches 0.90 at the lower Wilson bound? Reduced copy only, not the PREREG outcome."""
import importlib.util, json, sys
import numpy as np
base = "/tmp/claude-0/-home-claude/3a9f8f67-4b49-5dd0-98ba-d0bd1c4358ce/scratchpad/priorcheck/"
spec = importlib.util.spec_from_file_location("ns", base + "naming_sensitivity.py")
ns = importlib.util.module_from_spec(spec); spec.loader.exec_module(ns)
tab = json.load(open(base + "panjabi_ref.json"))
prior = json.load(open(base + "judge/prior-enhance_pet-C3-L5.json"))
levels = prior["levels"]
mu = np.array([[tab["ref"][m][l][0] for l in levels] for m in prior["measures"]])
sd = np.array([[tab["ref"][m][l][1] for l in levels] for m in prior["measures"]])
rl, rm = np.array(prior["r_level"]), np.array(prior["r_measure"])
both = rm.copy(); both[0, 2] = both[2, 0] = 0.8; both[1, 3] = both[3, 1] = 0.8
n = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
for name, r in (("fitted", rm), ("widths_and_depths_0.8", both)):
    for k in (4, 5, 6):
        rng = np.random.default_rng(1000 * k + 7)
        res = ns.accuracy(rng, mu, sd, rl, r, k, n)
        print("%-24s k=%d acc %.3f [%.3f, %.3f]" % (name, k, res["accuracy"], res["lo"], res["hi"])); sys.stdout.flush()
