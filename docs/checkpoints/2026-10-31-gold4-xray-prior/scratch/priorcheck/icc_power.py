#!/usr/bin/env python3
"""How precisely the 85 probable repeat groups (63 pairs, 14 triples, 5 of four, 3 of five; SchwingNet
data/splits/latent-prior-repeat-groups.json) estimate one measure's repeat agreement, the one-way
ICC(1), and the share of a z score's variance that is error (1 - ICC). Simulation only."""
import json
import numpy as np

SIZES = [2] * 63 + [3] * 14 + [4] * 5 + [5] * 3
OUT = "/tmp/claude-0/-home-claude/3a9f8f67-4b49-5dd0-98ba-d0bd1c4358ce/scratchpad/priorcheck/results-icc.json"


def icc1(groups):
    k = np.array([len(g) for g in groups], float)
    N, n = k.sum(), len(groups)
    grand = np.concatenate(groups).mean()
    means = np.array([g.mean() for g in groups])
    msb = np.sum(k * (means - grand) ** 2) / (n - 1)
    msw = sum(((g - g.mean()) ** 2).sum() for g in groups) / (N - n)
    k0 = (N - (k ** 2).sum() / N) / (n - 1)
    return (msb - msw) / (msb + (k0 - 1) * msw)


def run(rho, reps, rng):
    est = np.empty(reps)
    for r in range(reps):
        person = rng.normal(0, np.sqrt(rho), len(SIZES))
        groups = [person[i] + rng.normal(0, np.sqrt(1 - rho), s) for i, s in enumerate(SIZES)]
        est[r] = icc1(groups)
    return dict(mean=round(float(est.mean()), 4), sd=round(float(est.std(ddof=1)), 4),
                p05=round(float(np.quantile(est, 0.05)), 4), p95=round(float(np.quantile(est, 0.95)), 4))


def main():
    rng = np.random.default_rng(20261031)
    out = {"groups": len(SIZES), "scans": sum(SIZES)}
    for rho in (0.6, 0.7, 0.8, 0.9, 0.95):
        out["icc_%.2f" % rho] = run(rho, 4000, rng)
    json.dump(out, open(OUT, "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
