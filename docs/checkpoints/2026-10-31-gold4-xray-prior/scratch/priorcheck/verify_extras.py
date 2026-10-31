"""Re-derive the secondary numbers of the report from the scratch modules alone: per-person shares,
the depth pair, the width pair at 0.9, the implied SD of log(top/bottom width), and a paired
naming difference on fresh seeds. Imports only scratch modules (plate_mismatch, naming_sensitivity)."""
import json, math, sys
import numpy as np
sys.path.insert(0, sys.argv[1])
import plate_mismatch as PM
import naming_sensitivity as NS

tab = json.load(open(sys.argv[2])); prior = json.load(open(sys.argv[3]))
levels = prior["levels"]
mu, sd = PM.margins(tab["ref"], levels)
rl, rm = np.array(prior["r_level"]), np.array(prior["r_measure"])
w08 = rm.copy(); w08[0, 2] = w08[2, 0] = 0.8
out = {}
rng = np.random.default_rng(31)
n = 200_000
fields = {"fitted": PM.draw_prior_fields(rng, rl, rm, n), "width_0.8": PM.draw_prior_fields(rng, rl, w08, n),
          "no_prior": PM.draw_assumed_fields(rng, 5, len(levels), n)}
i14 = [levels.index(l) for l in ("L1", "L2", "L3", "L4")]
for name, f in fields.items():
    v = PM.values(rng, mu, sd, f, 0.0)
    _, ex = PM.mismatch(v[:, 0], v[:, 2], mu[0][None], mu[2][None])
    out["person_any_excess20|" + name] = dict(L1_L4=float((ex[:, i14] > 0.2).any(1).mean()),
                                              C3_L5=float((ex > 0.2).any(1).mean()))
def pair_share(a, b, r, m=200_000, seed=7):
    g = np.random.default_rng(seed)
    z1 = g.normal(size=(m, len(levels))); z2 = r * z1 + math.sqrt(1 - r * r) * g.normal(size=(m, len(levels)))
    s = np.exp(g.normal(0, 0.07, size=(m, 1)))
    x = np.maximum(s * (mu[a] + sd[a] * z1), 0.5); y = np.maximum(s * (mu[b] + sd[b] * z2), 0.5)
    ex = np.abs((x / y) / (mu[a] / mu[b]) - 1)
    return {"0.1": float((ex > 0.1).mean()), "0.2": float((ex > 0.2).mean())}
out["depth_pair_excess"] = {str(r): pair_share(1, 3, r) for r in (0.0, float(rm[1, 3]), 0.8, 0.9)}
out["width_pair_excess"] = {str(r): pair_share(0, 2, r) for r in (0.0, float(rm[0, 2]), 0.8, 0.9)}
cva, cvb = sd[0] / mu[0], sd[2] / mu[2]
out["sd_log_ratio_widths"] = {}
for r in (0.0, float(rm[0, 2]), 0.8):
    s = np.sqrt(cva ** 2 + cvb ** 2 - 2 * r * cva * cvb)
    out["sd_log_ratio_widths"][str(r)] = dict(median=float(np.median(s)), lo=float(s.min()), hi=float(s.max()))
out["width_cv"] = dict(median=float(np.median(np.r_[cva, cvb])), lo=float(np.r_[cva, cvb].min()), hi=float(np.r_[cva, cvb].max()))
both = w08.copy(); both[1, 3] = both[3, 1] = 0.8
t = np.linspace(-6 * 0.07, 6 * 0.07, 81); logw = -0.5 * (t / 0.07) ** 2; logw -= np.logaddexp.reduce(logw); sizes = np.exp(t)
for k in (2, 3):
    hits = {}
    for name, r in (("fitted", rm), ("widths_0.8", w08), ("widths_and_depths_0.8", both)):
        g = np.random.default_rng(9000 + k)
        X, truth = NS.draw_fields(g, mu, sd, rl, r, k, 4000)
        ll = np.stack([NS.loglik(X, mu, sd, rl, r, p, k, sizes, logw) for p in range(len(levels) - k + 1)], 1)
        hits[name] = (ll.argmax(1) == truth).astype(float)
    for name in ("widths_0.8", "widths_and_depths_0.8"):
        d = hits[name] - hits["fitted"]
        out["paired_naming|k%d|%s_minus_fitted" % (k, name)] = dict(diff=float(d.mean()), se=float(d.std(ddof=1) / math.sqrt(len(d))),
                                                                  acc=float(hits[name].mean()), acc_fitted=float(hits["fitted"].mean()))
json.dump(out, open(sys.argv[4], "w"), indent=1)
print(json.dumps(out, indent=1))
