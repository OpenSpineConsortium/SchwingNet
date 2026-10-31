import sys, json, numpy as np
import check_proto as P, truths as T
from schwingcheck import correlation as CORR
rl0, rm0 = T.published()
reg = P.level_regions(T.LEVELS)
W, D = (0, 2), (1, 3)
def regional(S, pair):
    return [round(P.same_level(S, reg[r], *pair), 2) for r in ("C3-C7", "T2-T12", "L1-L4")]
for i, kind in enumerate(sys.argv[1].split(",")):
    cov = T.truth(kind, rl0, rm0)
    rng = np.random.default_rng(500 + i)
    fit = T.draw(rng, cov, 693)
    z, _, _ = CORR.standardise(fit)
    Kd = P.kron_drawn(z)
    Pd = P.person_drawn(z)
    a, B, CL, CM, pc = P.person_effect(z)
    share = np.mean([(a[l] ** 2) * B[m, m] / pc[l * 5 + m, l * 5 + m] for l in range(22) for m in range(5)])
    print(kind, "truth W", regional(cov, W), "D", regional(cov, D),
          "| kron W", regional(Kd, W), "D", regional(Kd, D),
          "| person W", regional(Pd, W), "D", regional(Pd, D), "| person share %.2f" % share,
          "| raw W", regional(P.sample_corr(z), W))
