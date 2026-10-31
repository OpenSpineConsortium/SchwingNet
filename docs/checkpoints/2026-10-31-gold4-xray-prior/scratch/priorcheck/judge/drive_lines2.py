import sys, time, re
import numpy as np
import truths as T
import lines_proto2 as LP
from drive_lines import population

name, kind, nw, npart, hw, hp, B, with_repeat = sys.argv[1], sys.argv[2], *map(int, sys.argv[3:8]), sys.argv[8] == "1"
rng = np.random.default_rng(7)
fit, held, units, facts, repeat = population(rng, kind, nw, npart, hw, hp)
t = time.time()
lines = ["- " + l for l in LP.report("%s C3..L5 check" % name, T.LEVELS, fit, held, units, facts, repeat if with_repeat else [], B=B)]
for line in lines:
    print(line)
long = [l for l in lines if len(l) > 196]
print("## lines %d, longest %d, over 196: %d, seconds %.0f" % (len(lines), max(len(l) for l in lines), len(long), time.time() - t), file=sys.stderr)
for l in long:
    print("##   %d %s" % (len(l), l[:120]), file=sys.stderr)
pat = [r"\b[a-z][a-z0-9_]*:[A-Za-z0-9]", r"/[A-Za-z0-9._~+-]", r"(^|[^0-9])(19|20)[0-9]{2}(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])([^0-9]|$)",
       r"(?i)(patient|accession|institution|physician|operators|stationname|studyid|studydate)", r"[0-9]{5}"]
for p in pat:
    hits = [l for l in lines if re.search(p, l)]
    print("## pattern %s: %d lines" % (p[:30], len(hits)), file=sys.stderr)
    for l in hits[:3]:
        print("##   " + l[:150], file=sys.stderr)
