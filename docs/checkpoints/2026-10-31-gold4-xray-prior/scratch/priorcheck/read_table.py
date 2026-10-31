"""Read Panjabi's mean and population SD (sem * sqrt(n)) for the five measures at C3..L5 from
bordercall's schwingcheck/data/panjabi_long.csv, side 'whole', as schwingcheck.table does."""
import csv, json, math, sys
path = sys.argv[1]
out_path = sys.argv[2]
MEASURES = ["endplate", "endplate_depth", "endplate_lower", "endplate_lower_depth", "h_post"]
LEVELS = ["C%d" % i for i in range(3, 8)] + ["T%d" % i for i in range(1, 13)] + ["L%d" % i for i in range(1, 6)]
cells = {}
with open(path, newline="") as f:
    rows = csv.DictReader(line for line in f if not line.startswith("#"))
    for r in rows:
        if r["measure"] in MEASURES and r["side"] == "whole" and r["level"] in LEVELS and r["statistic"] in ("mean", "sem") and r["value"] != "":
            cells.setdefault((r["measure"], r["level"]), {})[r["statistic"]] = float(r["value"])
            cells[(r["measure"], r["level"])]["n"] = int(r["n"])
ref = {}
for m in MEASURES:
    ref[m] = {}
    for l in LEVELS:
        c = cells[(m, l)]
        ref[m][l] = [c["mean"], c["sem"] * math.sqrt(c["n"]), c["n"]]
json.dump(dict(levels=LEVELS, measures=MEASURES, ref=ref, source=path), open(out_path, "w"), indent=1)
for l in LEVELS:
    print(l, "  ".join("%s %5.1f sd %4.2f cv %.3f n %d" % (m[:10], ref[m][l][0], ref[m][l][1], ref[m][l][1] / ref[m][l][0], ref[m][l][2]) for m in MEASURES))
