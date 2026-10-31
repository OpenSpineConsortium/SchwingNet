"""The gold tier's own cell means and SDs for the five measures at C3..L5, from bordercall
records/morphometry-2026-10-29/compare-229.csv (columns ours_n, ours_mean, ours_sd: aggregates of
the 228 ENHANCE.PET thin-slice studies measured by the engine before #44)."""
import csv, json, sys
MEASURES = ["endplate", "endplate_depth", "endplate_lower", "endplate_lower_depth", "h_post"]
LEVELS = ["C%d" % i for i in range(3, 8)] + ["T%d" % i for i in range(1, 13)] + ["L%d" % i for i in range(1, 6)]
ref = {m: {} for m in MEASURES}
for r in csv.DictReader(open(sys.argv[1])):
    if r["ours_key"] in ref and r["level"] in LEVELS:
        cell = [float(r["ours_mean"]), float(r["ours_sd"]), int(r["ours_n"])]
        prev = ref[r["ours_key"]].get(r["level"])
        assert prev is None or prev == cell, (r["ours_key"], r["level"], prev, cell)
        ref[r["ours_key"]][r["level"]] = cell
assert all(len(ref[m]) == len(LEVELS) for m in MEASURES)
json.dump(dict(levels=LEVELS, measures=MEASURES, ref=ref, source=sys.argv[1]), open(sys.argv[2], "w"), indent=1)
print("ok")
