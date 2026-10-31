"""Same-measure correlation of adjacent levels with the sexes pooled, from the covariates
report's per-sex means, SDs and within-sex r with the level above (job 40878978, autoPET
adults): the two-group mixture's covariance p*CovM + (1-p)*CovF + p(1-p)*d*d'. Reads only the
aggregate report; prints aggregates."""
import sys, math, re
path = sys.argv[1]
want = ("endplate", "endplate_depth", "endplate_lower", "endplate_lower_depth", "h_post")
levels = ("T10", "T11", "T12", "L1", "L2", "L3", "L4", "L5")
cell = {}
for line in open(path):
    f = line.split()
    if len(f) < 20 or f[0] != "-" or f[1] != "autopet" or f[2] not in want or f[3] not in levels:
        continue
    m = dict(nM=int(f[5]), mM=float(f[6]), sM=float(f[7]), nF=int(f[9]), mF=float(f[10]), sF=float(f[11]))
    rM, rF = f[16], f[18]
    m["rM"] = float(rM) if rM != "-" else None
    m["rF"] = float(rF) if rF != "-" else None
    cell[(f[2], f[3])] = m
fitted = {"T10-T11": 0.669, "T11-T12": 0.648, "T12-L1": 0.647, "L1-L2": 0.614, "L2-L3": 0.560, "L3-L4": 0.519, "L4-L5": 0.303}
for a, b in zip(levels, levels[1:]):
    out = []
    for k in want:
        up, lo = cell[(k, a)], cell[(k, b)]
        nM, nF = lo["nM"], lo["nF"]; p = nM / (nM + nF)
        cov = p * lo["rM"] * up["sM"] * lo["sM"] + (1 - p) * lo["rF"] * up["sF"] * lo["sF"] \
              + p * (1 - p) * (up["mM"] - up["mF"]) * (lo["mM"] - lo["mF"])
        var_up = p * up["sM"] ** 2 + (1 - p) * up["sF"] ** 2 + p * (1 - p) * (up["mM"] - up["mF"]) ** 2
        var_lo = p * lo["sM"] ** 2 + (1 - p) * lo["sF"] ** 2 + p * (1 - p) * (lo["mM"] - lo["mF"]) ** 2
        out.append(cov / math.sqrt(var_up * var_lo))
    print("%-8s pooled r by measure %s  mean %.3f | prior R_level (ENHANCE C3..L5, shrunk) %.3f"
          % (a + "-" + b, " ".join("%.3f" % x for x in out), sum(out) / len(out), fitted[a + "-" + b]))
