import sys, time, json, numpy as np
import check_proto as P, truths as T
from schwingcheck import correlation as CORR

KEYS = ["same plate all", "long cross C x L", "long cross core lag6", "facing minus far widths",
        "facing minus far depths", "contrast size minus differences", "lag1 range core",
        "refit T1..L5 width pair", "refit C3..C7 width pair", "refit T2..L4 width pair"]


def run(kind, n_fit, n_held, B, seed, gross=0.0):
    rl0, rm0 = T.published()
    cov = T.truth(kind if kind != "gross" else "separable", rl0, rm0)
    rng = np.random.default_rng(seed)
    fit = T.draw(rng, cov, n_fit, gross)
    held = T.draw(rng, cov, n_held, gross)
    z, _, _ = CORR.standardise(fit)
    obs = P.observed(z, T.LEVELS)
    nl = P.null(obs["rl"], obs["rm"], n_fit, T.LEVELS, B=B, seed=seed + 1)
    units = ["u%d" % i for i in range(n_fit)]
    cv = P.cv_scores(fit, units)
    ho = P.held_scores(fit, held, cv["w"])
    out = {"kind": kind, "n": n_fit}
    for k in KEYS:
        if k in obs["misfit"]:
            m, (mu, sd) = obs["misfit"][k], nl[k]
            out[k] = (round(m, 3), round(mu, 3), round(sd, 3), round((m - mu) / sd, 1))
    w = P.PAIRS.index((0, 2)); d = P.PAIRS.index((1, 3))
    out["raw widths C/T/all"] = [round(obs["raw"]["same %d %s" % (w, r)], 3) for r in ("C3-C7", "T2-T12", "all")]
    out["raw depths C/T/all"] = [round(obs["raw"]["same %d %s" % (d, r)], 3) for r in ("C3-C7", "T2-T12", "all")]
    out["drawn widths/depths"] = [round(obs["drawn"]["same %d all" % w], 3), round(obs["drawn"]["same %d all" % d], 3)]
    vs, _, _ = CORR.standardise(P.normal_scores(fit))
    _, rmc = CORR.flip_flop(vs)
    out["copula rm widths vs pearson"] = [round(rmc[0, 2], 3), round(obs["rm"][0, 2], 3)]
    out["cv"] = cv
    out["held"] = ho
    return out


if __name__ == "__main__":
    kinds = sys.argv[1].split(",")
    n_fit, n_held, B = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    for i, kind in enumerate(kinds):
        t = time.time()
        r = run(kind, n_fit, n_held, B, 100 + i, gross=0.03 if kind == "gross" else 0.0)
        r["seconds"] = round(time.time() - t, 1)
        print(json.dumps(r))
        sys.stdout.flush()
