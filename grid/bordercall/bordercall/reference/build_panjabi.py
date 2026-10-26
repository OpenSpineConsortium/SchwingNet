"""Build the Panjabi reference table for the whole spine, and check it against itself.

    python build_panjabi.py

WHERE THE NUMBERS COME FROM. Every value below was read off the printed tables of

  Panjabi MM, Takata K, Goel V, Federico D, Oxland T, Duranceau J, Krag M.
  Thoracic human vertebrae. Quantitative three-dimensional anatomy.
  Spine 1991;16(8):888-901.      Table 3 p.892, Table 4 p.893, Table 5 p.894

  Panjabi MM, Goel V, Oxland T, Takata K, Duranceau J, Krag M, Price M.
  Human lumbar vertebrae. Quantitative three-dimensional anatomy.
  Spine 1992;17(3):299-306.      Tables 2-5

Pages 892 and 894 are IMAGE ONLY in the publisher's scan, which is what every library's
Ovid subscription serves, so the thoracic body and pedicle tables cannot be extracted as
text and were read from the page images instead. That is also why the automatic text
extraction of Table 4 comes out scrambled: do not parse it, read it.

THE CHECK THAT MAKES THIS TRUSTWORTHY. T11 and T12 were already transcribed into
CTSpinoPelvic1K's own reference table from the same printed tables, by a different pass.
This script recomputes them from the values below and fails if any disagrees. A misread
digit in a column of twelve is invisible; a disagreement at the overlap is not.

EVERY DISPERSION IS A STANDARD ERROR, as the papers print it ("the lower row shows the
standard error of the means"). The population SD is sem*sqrt(n), n=12. Drawing the SEM as
if it were an SD gives an interval sqrt(12) = 3.5x too narrow.

PEDICLE WIDTH IS THE MEAN OF LEFT AND RIGHT, with the two standard errors averaged, which
is the convention the existing table already used and is kept here so the two agree.

STILL MISSING: the cervical companion paper, Panjabi MM, Duranceau J, Goel V, Oxland T,
Takata K. Cervical human vertebrae. Quantitative three-dimensional anatomy of the middle
and lower regions. Spine 1991;16(8):861-869 (PMID 1948369,
doi:10.1097/00007632-199108000-00001). Same journal and issue as the thoracic paper, 27
pages earlier. Until it is on hand there is NO cervical reference here, and a cervical
border plotted with --reference will simply have no interval drawn rather than a wrong one.
"""
from __future__ import annotations

import csv
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
THORACIC = ["T%d" % i for i in range(1, 13)]

# Table 3, p.892: EPWu = upper end-plate width, VBHp = posterior vertebral body height
EPWu = [(24.5, 0.85), (24.9, 0.59), (24.6, 0.43), (24.5, 0.58), (24.9, 0.77), (26.2, 0.79),
        (27.8, 0.70), (29.5, 0.71), (30.6, 1.06), (31.9, 0.67), (34.9, 0.97), (39.0, 0.58)]
VBHp = [(14.1, 0.41), (15.6, 0.58), (15.7, 0.57), (16.2, 0.48), (16.2, 0.60), (17.4, 0.54),
        (18.2, 0.70), (18.7, 0.69), (19.3, 0.59), (20.2, 0.44), (21.3, 0.71), (22.7, 1.04)]
# Table 4, p.893: SCW = canal width (transverse), SCD = canal depth (anteroposterior)
SCW = [(21.8, 0.71), (19.5, 0.34), (18.3, 0.54), (17.0, 0.57), (17.1, 0.68), (17.3, 0.74),
       (17.3, 0.83), (17.7, 0.63), (17.9, 1.19), (18.2, 0.78), (19.4, 0.95), (22.2, 1.12)]
SCD = [(16.4, 0.42), (15.3, 1.25), (15.9, 1.09), (16.2, 0.89), (16.3, 0.72), (16.5, 0.62),
       (16.1, 0.69), (15.9, 0.76), (15.7, 0.82), (15.5, 0.70), (16.0, 0.46), (18.1, 0.62)]
# Table 5, p.894: PDW = pedicle width, right and left kept separate in the paper
PDWr = [(8.2, 0.44), (8.4, 1.06), (7.0, 0.78), (5.5, 0.71), (6.2, 0.53), (6.0, 0.78),
        (6.5, 0.80), (6.7, 0.35), (7.6, 0.54), (8.3, 0.70), (8.8, 0.43), (8.8, 0.81)]
PDWl = [(8.7, 0.53), (7.9, 0.97), (6.5, 0.55), (7.0, 0.49), (5.7, 0.38), (6.0, 0.87),
        (5.2, 0.45), (6.7, 0.63), (7.7, 0.65), (9.7, 0.78), (10.7, 0.84), (8.6, 0.68)]

# Panjabi MM, Duranceau J, Goel V, Oxland T, Takata K. Cervical human vertebrae.
# Quantitative three-dimensional anatomy of the middle and lower regions.
# Spine 1991;16(8):861-869.  Table 2 p.863, Tables 3 and 4 p.864.
# Twelve specimens, 72 vertebrae, C2-C7. The whole paper is a scan with no text layer, so
# every value here was read from the page images.
#
# C2 HAS NO UPPER END-PLATE ROW. The paper prints a dash for EPWu, EPDu and VBHp at C2,
# because the dens occupies where that end-plate would be. A dash is not a zero and not a
# missing value to be filled: those rows do not exist, so endplate and h_post start at C3
# while canal and pedicle run from C2.
CERVICAL = ["C%d" % i for i in range(2, 8)]
C_EPWu = [None, (15.8, 0.46), (17.2, 0.66), (17.5, 0.58), (18.5, 0.55), (21.8, 0.66)]
C_VBHp = [None, (11.6, 0.35), (11.4, 0.43), (11.4, 0.32), (10.9, 0.26), (12.8, 0.46)]
C_SCW = [(24.5, 0.61), (22.9, 1.15), (24.7, 0.52), (24.9, 1.13), (25.8, 0.66), (24.5, 0.92)]
C_SCD = [(21.0, 0.35), (16.2, 1.33), (17.7, 0.46), (17.4, 0.72), (18.1, 0.46), (15.2, 1.15)]
C_PDWr = [(7.7, 0.35), (5.8, 0.64), (5.7, 0.60), (6.1, 0.46), (6.3, 0.49), (6.6, 0.42)]
C_PDWl = [(8.3, 0.07), (5.4, 0.32), (5.1, 0.46), (5.1, 0.35), (5.6, 0.39), (6.5, 0.35)]
CERV_SRC = "Panjabi MM et al. Spine 1991;16(8):861-869"

# the lumbar paper, 1992, as already transcribed and verified in CTSpinoPelvic1K
LUMBAR = {
    "endplate": [("L1", 41.2, 1.03), ("L2", 42.6, 0.74), ("L3", 44.1, 0.88),
                 ("L4", 46.6, 1.2), ("L5", 47.3, 1.2)],
    "h_post":   [("L1", 23.8, 0.92), ("L2", 24.3, 0.95), ("L3", 23.8, 1.1),
                 ("L4", 24.1, 1.1), ("L5", 22.9, 0.95)],
    "canal_w":  [("L1", 23.7, 0.92), ("L2", 23.8, 0.71), ("L3", 24.3, 0.64),
                 ("L4", 25.4, 0.49), ("L5", 27.1, 0.88)],
    "canal_ap": [("L1", 19.0, 0.67), ("L2", 18.2, 0.53), ("L3", 17.5, 0.53),
                 ("L4", 18.6, 0.71), ("L5", 19.7, 0.49)],
    # Table 4: the mean of the right and left pedicle widths, the two standard errors
    # averaged, as panjabi_1992.csv already carries them and as the thoracic rows above
    # are built. The first build of this table left the lumbar pedicle out, so a
    # whole-spine model had no pedicle below T12.
    "pedicle":  [("L1", 8.6, 0.915), ("L2", 8.25, 0.675), ("L3", 10.15, 0.600),
                 ("L4", 14.05, 0.320), ("L5", 18.6, 1.030)],
}
LUMBAR_SRC = ("Panjabi MM et al. Spine 1992;17(3):299-306", "2-5", "301")
THOR_SRC = "Panjabi MM et al. Spine 1991;16(8):888-901"

# what the earlier, independent pass recorded for the overlap
EXPECT = {("endplate", "T11"): (34.9, 0.97), ("endplate", "T12"): (39.0, 0.58),
          ("h_post", "T11"): (21.3, 0.71), ("h_post", "T12"): (22.7, 1.04),
          ("canal_w", "T11"): (19.4, 0.95), ("canal_w", "T12"): (22.2, 1.12),
          ("canal_ap", "T11"): (16.0, 0.46), ("canal_ap", "T12"): (18.1, 0.62),
          ("pedicle", "T11"): (9.75, 0.635), ("pedicle", "T12"): (8.7, 0.745)}

ROWS = []


def add(measure, level, mean, sem, name, table, page, src):
    ROWS.append({"measure": measure, "level": level, "mean": round(mean, 3),
                 "sem": round(sem, 4), "n": 12, "panjabi_name": name,
                 "source_table": table, "source_page": page, "citation": src})


for i, lv in enumerate(THORACIC):
    add("endplate", lv, EPWu[i][0], EPWu[i][1], "EPWu", "3", "892", THOR_SRC)
    add("h_post", lv, VBHp[i][0], VBHp[i][1], "VBHp", "3", "892", THOR_SRC)
    add("canal_w", lv, SCW[i][0], SCW[i][1], "SCW", "4", "893", THOR_SRC)
    add("canal_ap", lv, SCD[i][0], SCD[i][1], "SCD", "4", "893", THOR_SRC)
    # the paper prints the two sides separately; the project's convention is their mean
    add("pedicle", lv, (PDWr[i][0] + PDWl[i][0]) / 2.0,
        (PDWr[i][1] + PDWl[i][1]) / 2.0, "PDW (mean of l/r)", "5", "894", THOR_SRC)

for i, lv in enumerate(CERVICAL):
    if C_EPWu[i]:
        add("endplate", lv, C_EPWu[i][0], C_EPWu[i][1], "EPWu", "2", "863", CERV_SRC)
    if C_VBHp[i]:
        add("h_post", lv, C_VBHp[i][0], C_VBHp[i][1], "VBHp", "2", "863", CERV_SRC)
    add("canal_w", lv, C_SCW[i][0], C_SCW[i][1], "SCW", "3", "864", CERV_SRC)
    add("canal_ap", lv, C_SCD[i][0], C_SCD[i][1], "SCD", "3", "864", CERV_SRC)
    add("pedicle", lv, (C_PDWr[i][0] + C_PDWl[i][0]) / 2.0,
        (C_PDWr[i][1] + C_PDWl[i][1]) / 2.0, "PDW (mean of l/r)", "4", "864", CERV_SRC)

for measure, rows in LUMBAR.items():
    for lv, mean, sem in rows:
        add(measure, lv, mean, sem, measure, LUMBAR_SRC[1], LUMBAR_SRC[2], LUMBAR_SRC[0])

bad = []
for (measure, lv), (mean, sem) in EXPECT.items():
    got = [r for r in ROWS if r["measure"] == measure and r["level"] == lv]
    if not got:
        bad.append("%s %s missing" % (measure, lv))
        continue
    g = got[0]
    if abs(g["mean"] - mean) > 0.005 or abs(g["sem"] - sem) > 0.005:
        bad.append("%s %s: built %.3f/%.4f, earlier pass %.3f/%.4f"
                   % (measure, lv, g["mean"], g["sem"], mean, sem))

out = os.path.join(HERE, "panjabi_full_spine.csv")
with open(out, "w", newline="", encoding="utf-8") as fh:
    fh.write("# Panjabi's quantitative three-dimensional anatomy, thoracic (1991) and\n"
             "# lumbar (1992). Dispersion is the STANDARD ERROR as printed; the population\n"
             "# SD is sem*sqrt(n). Cervical levels are absent: see build_panjabi.py.\n")
    w = csv.DictWriter(fh, fieldnames=["measure", "level", "mean", "sem", "n",
                                       "panjabi_name", "source_table", "source_page",
                                       "citation"], lineterminator="\n")
    w.writeheader()
    for r in sorted(ROWS, key=lambda x: (x["measure"], x["level"])):
        w.writerow(r)

print("wrote %s  (%d rows)" % (out, len(ROWS)))
levels = sorted({r["level"] for r in ROWS})
print("  measures: %s" % ", ".join(sorted({r["measure"] for r in ROWS})))
print("  levels:   C2-C7, T1-T12, L1-L5  (%d)" % len(levels))
if bad:
    print("\nOVERLAP CHECK FAILED:")
    for b in bad:
        print("  " + b)
    sys.exit(1)
print("  overlap check: all %d T11/T12 values match the earlier independent pass" % len(EXPECT))
