"""Per level T10..L5, the sex-pooled correlation each pair of the five measures would show if
uncorrelated within sex, from the covariates report's per-sex means and SDs (job 40878978,
autoPET adults), using the exact two-group mixture variance. Aggregates in, aggregates out."""
import sys, math, itertools
want = ("endplate", "endplate_depth", "endplate_lower", "endplate_lower_depth", "h_post")
levels = ("T10", "T11", "T12", "L1", "L2", "L3", "L4", "L5")
cell = {}
for line in open(sys.argv[1]):
    f = line.split()
    if len(f) > 12 and f[0] == "-" and f[1] == "autopet" and f[2] in want and f[3] in levels:
        cell[(f[2], f[3])] = (int(f[5]), float(f[6]), float(f[7]), int(f[9]), float(f[10]), float(f[11]))
for lv in levels:
    floors = {}
    for a, b in itertools.combinations(want, 2):
        nM, mMa, sMa, nF, mFa, sFa = cell[(a, lv)]
        _, mMb, sMb, _, mFb, sFb = cell[(b, lv)]
        p = nM / (nM + nF); k = p * (1 - p)
        cov = k * (mMa - mFa) * (mMb - mFb)
        va = p * sMa ** 2 + (1 - p) * sFa ** 2 + k * (mMa - mFa) ** 2
        vb = p * sMb ** 2 + (1 - p) * sFb ** 2 + k * (mMb - mFb) ** 2
        floors[(a, b)] = cov / math.sqrt(va * vb)
    v = list(floors.values())
    print("%-4s floor min %.3f max %.3f | endplate~endplate_lower %.3f | endplate~h_post %.3f | depth~lower_depth %.3f"
          % (lv, min(v), max(v), floors[("endplate", "endplate_lower")], floors[("endplate", "h_post")],
             floors[("endplate_depth", "endplate_lower_depth")]))
