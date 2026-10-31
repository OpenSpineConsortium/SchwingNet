"""Fields drawn with a stronger within-vertebra correlation (widths and depths of one vertebra at
0.8, the rest of the fitted ENHANCE.PET C3..L5 prior unchanged) and scored by the fitted prior and by
the matched one: accuracy, mean probability of the truth, and the expected calibration error of the
top answer (10 bins), as run_naming scores. Reduced copy: typical column only, no anchor."""
import json, math, sys
import numpy as np
sys.path.insert(0, sys.argv[1])
import naming_sensitivity as NS

def ece(conf, right, bins=10):
    e = 0.0
    edges = np.linspace(0, 1, bins + 1)
    for a, b in zip(edges[:-1], edges[1:]):
        inside = (conf > a) & (conf <= b)
        if inside.any():
            e += inside.mean() * abs(right[inside].mean() - conf[inside].mean())
    return e

tab = json.load(open(sys.argv[2])); prior = json.load(open(sys.argv[3]))
levels = prior["levels"]
mu = np.array([[tab["ref"][m][l][0] for l in levels] for m in prior["measures"]])
sd = np.array([[tab["ref"][m][l][1] for l in levels] for m in prior["measures"]])
rl, rm = np.array(prior["r_level"]), np.array(prior["r_measure"])
truth_rm = rm.copy(); truth_rm[0, 2] = truth_rm[2, 0] = 0.8; truth_rm[1, 3] = truth_rm[3, 1] = 0.8
t = np.linspace(-6 * 0.07, 6 * 0.07, 81); logw = -0.5 * (t / 0.07) ** 2; logw -= np.logaddexp.reduce(logw); sizes = np.exp(t)
out = {}
for k in (1, 2, 3, 4):
    rng = np.random.default_rng(500 + k)
    X, truth = NS.draw_fields(rng, mu, sd, rl, truth_rm, k, 4000)
    for scorer, r in (("matched_0.8", truth_rm), ("fitted_0.30", rm)):
        ll = np.stack([NS.loglik(X, mu, sd, rl, r, p, k, sizes, logw) for p in range(22 - k + 1)], 1)
        post = np.exp(ll - np.logaddexp.reduce(ll, axis=1, keepdims=True))
        right = post.argmax(1) == truth
        conf = post.max(1)
        res = dict(accuracy=float(right.mean()), p_true=float(post[np.arange(len(truth)), truth].mean()),
                   mean_conf=float(conf.mean()), ece=float(ece(conf, right)))
        out["k%d|%s" % (k, scorer)] = res
        print("k=%d scorer %-12s acc %.3f p_true %.3f mean top conf %.3f ECE %.3f" % (k, scorer, res["accuracy"], res["p_true"], res["mean_conf"], res["ece"]))
json.dump(out, open(sys.argv[4], "w"), indent=1)
