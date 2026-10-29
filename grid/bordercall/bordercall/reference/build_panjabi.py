"""Build the Panjabi reference table for the whole spine, and check it against itself.

    python build_panjabi.py

EVERY LINEAR DIMENSION OF ALL THREE PAPERS IS HERE. Panjabi's series is three papers, one
per region, sharing a method, an instrument and a nomenclature:

  cervical  Panjabi MM, Duranceau J, Goel V, Oxland T, Takata K.
            Cervical human vertebrae. Quantitative three-dimensional anatomy of the middle
            and lower regions.  Spine 1991;16(8):861-869.
            Table 2 p.863 (body), Table 3 p.864 (canal), Table 4 p.864 (pedicle)
  thoracic  Panjabi MM, Takata K, Goel V, Federico D, Oxland T, Duranceau J, Krag M.
            Thoracic human vertebrae. Quantitative three-dimensional anatomy.
            Spine 1991;16(8):888-901.
            Table 3 p.892 (body), Table 4 p.893 (canal), Table 5 p.894 (pedicle)
  lumbar    Panjabi MM, Goel V, Oxland T, Takata K, Duranceau J, Krag M, Price M.
            Human lumbar vertebrae. Quantitative three-dimensional anatomy.
            Spine 1992;17(3):299-306.
            Table 2 p.301 (body), Table 3 p.302 (canal), Table 4 p.302 (pedicle)

The PDFs are in `papers/`. All three are scans; the thoracic body and pedicle pages and the
whole cervical paper carry no text layer, so every value below was read from rendered page
images. Automatic text extraction of the thoracic canal table interleaves rows and columns
and yields plausible, wrong numbers -- do not parse it, read it.

EVERY DISPERSION IS A STANDARD ERROR, as each table's own note says ("the lower row shows
the standard error of the means"). The population SD is sem*sqrt(n), n=12. Drawing the
standard error as an SD gives an interval 3.5x too narrow.

WHAT IS NOT HERE. Panjabi publishes no ANTERIOR body height, so there is no `h_ant` row: the
body-height column of these papers is VBHp, posterior, and pairing it with an anterior height
measured from a segmentation would compare two different things. Surface areas, angular
dimensions, pars interarticularis, spinous and transverse process tables, rib articulations
and the uncovertebral joints are in the papers and are not transcribed here, because nothing
downstream consumes them; `papers/` carries the PDFs so they can be read when something does.

THE CHECKS. Two independent ones, and both must pass:
  1. T11 and T12 were transcribed earlier, by a different pass, into CTSpinoPelvic1K's own
     reference table. This script recomputes them and fails on a disagreement past 0.005.
  2. The lumbar paper states its own pedicle widths in prose -- "8.6 mm at L1, then decreased
     to 8.2 mm at L2" -- which the left/right mean must reproduce.

ONE CORRECTION THIS EXTRACTION FOUND. The earlier transcription carried VBHp L1 with a
standard error of 0.92. Table 2 on p.301 reads 23.8 +/- 1.03; 0.92 is SCW L1's standard
error, one row up in a different table. The mean was right, the dispersion was not, and the
reference band at L1 was 12 % too narrow. Corrected here.
"""
from __future__ import annotations

import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

CERVICAL = ["C%d" % i for i in range(2, 8)]
THORACIC = ["T%d" % i for i in range(1, 13)]
LUMBAR = ["L%d" % i for i in range(1, 6)]

N = 12          # specimens behind every mean, all three papers

# --- cervical, Spine 1991;16(8):861-869 -------------------------------------------------
# C2 prints a dash for the three upper-body rows: the dens occupies where that end-plate
# would be. A dash is not a zero and not a value to interpolate -- the row does not exist.
C = {
    "EPDu": [None, (15.0, .55), (15.3, .75), (15.2, .35), (16.4, .52), (18.1, .66)],
    "EPWu": [None, (15.8, .46), (17.2, .66), (17.5, .58), (18.5, .55), (21.8, .66)],
    "EPDl": [(15.6, .58), (15.6, .40), (15.9, .38), (17.9, .52), (18.5, .69), (16.8, .32)],
    "EPWl": [(17.5, .52), (17.2, .29), (17.0, .49), (19.4, .40), (22.0, .75), (23.4, .98)],
    "VBHp": [None, (11.6, .35), (11.4, .43), (11.4, .32), (10.9, .26), (12.8, .46)],
    "SCW":  [(24.5, .61), (22.9, 1.15), (24.7, .52), (24.9, 1.13), (25.8, .66), (24.5, .92)],
    "SCD":  [(21.0, .35), (16.2, 1.33), (17.7, .46), (17.4, .72), (18.1, .46), (15.2, 1.15)],
    "PDWr": [(7.7, .35), (5.8, .64), (5.7, .60), (6.1, .46), (6.3, .49), (6.6, .42)],
    "PDWl": [(8.3, .07), (5.4, .32), (5.1, .46), (5.1, .35), (5.6, .39), (6.5, .35)],
    "PDHr": [(9.4, .46), (7.6, .46), (7.4, .42), (6.7, .42), (7.1, .39), (7.5, .32)],
    "PDHl": [(11.1, .14), (7.2, .35), (7.3, .49), (7.3, .39), (7.5, .32), (7.5, .28)],
}
C_PAGE = {"EPDu": ("2", "863"), "EPWu": ("2", "863"), "EPDl": ("2", "863"),
          "EPWl": ("2", "863"), "VBHp": ("2", "863"), "SCW": ("3", "864"),
          "SCD": ("3", "864"), "PDWr": ("4", "864"), "PDWl": ("4", "864"),
          "PDHr": ("4", "864"), "PDHl": ("4", "864")}
C_SRC = "Panjabi MM et al. Spine 1991;16(8):861-869"

# --- thoracic, Spine 1991;16(8):888-901 -------------------------------------------------
T = {
    "EPWu": [(24.5, .85), (24.9, .59), (24.6, .43), (24.5, .58), (24.9, .77), (26.2, .79),
             (27.8, .70), (29.5, .71), (30.6, 1.06), (31.9, .67), (34.9, .97), (39.0, .58)],
    "EPDu": [(18.5, .75), (19.6, .41), (22.7, .75), (23.3, .58), (24.3, .79), (26.0, .80),
             (27.4, .54), (27.9, .52), (29.3, 1.03), (30.5, .85), (31.9, .71), (32.8, 1.21)],
    "EPWl": [(27.8, .64), (27.4, .65), (25.9, .87), (26.0, .92), (27.0, .96), (28.2, .82),
             (29.1, .69), (30.5, .70), (33.0, 1.10), (35.4, .98), (39.1, .71), (42.1, .91)],
    # T3's mean is 23.3 as Table 3 prints it on page 892 (provenance/cells/thoracic-t3/
    # r07_c02.png, read from the owner's second scan of 27 October 2026, so by both passes),
    # which the archive's records were computed with. Table 8's Present Study column restates it
    # as 23.2 (provenance/cells/thoracic-t8a/r03_c01.png): the paper's own contradiction, recorded
    # in provenance/crosstable.csv and provenance/CONTRADICTIONS.md and read by no table.
    "EPDl": [(19.7, .52), (21.6, .64), (23.3, .75), (24.5, .78), (25.8, .77), (26.9, .67),
             (28.5, .87), (29.4, .71), (31.0, .89), (31.6, 1.11), (31.8, .78), (33.4, .78)],
    "VBHp": [(14.1, .41), (15.6, .58), (15.7, .57), (16.2, .48), (16.2, .60), (17.4, .54),
             (18.2, .70), (18.7, .69), (19.3, .59), (20.2, .44), (21.3, .71), (22.7, 1.04)],
    "SCW":  [(21.8, .71), (19.5, .34), (18.3, .54), (17.0, .57), (17.1, .68), (17.3, .74),
             (17.3, .83), (17.7, .63), (17.9, 1.19), (18.2, .78), (19.4, .95), (22.2, 1.12)],
    "SCD":  [(16.4, .42), (15.3, 1.25), (15.9, 1.09), (16.2, .89), (16.3, .72), (16.5, .62),
             (16.1, .69), (15.9, .76), (15.7, .82), (15.5, .70), (16.0, .46), (18.1, .62)],
    "PDWr": [(8.2, .44), (8.4, 1.06), (7.0, .78), (5.5, .71), (6.2, .53), (6.0, .78),
             (6.5, .80), (6.7, .35), (7.6, .54), (8.3, .70), (8.8, .43), (8.8, .81)],
    "PDWl": [(8.7, .53), (7.9, .97), (6.5, .55), (7.0, .49), (5.7, .38), (6.0, .87),
             (5.2, .45), (6.7, .63), (7.7, .65), (9.7, .78), (10.7, .84), (8.6, .68)],
    "PDHr": [(9.3, .53), (11.1, .44), (11.8, .23), (11.9, .46), (11.2, .51), (12.0, .44),
             (11.8, .30), (12.5, .52), (13.9, .79), (14.7, .49), (16.9, .49), (16.5, .71)],
    "PDHl": [(9.9, .41), (11.6, .30), (12.0, .32), (12.2, .50), (11.4, .36), (11.6, .47),
             (12.2, .27), (12.5, .41), (13.8, .55), (15.0, .24), (17.8, .29), (16.8, .94)],
}
T_PAGE = {k: (("3", "892") if k.startswith("EP") or k == "VBHp" else
              ("4", "893") if k.startswith("SC") else ("5", "894")) for k in T}
T_SRC = "Panjabi MM et al. Spine 1991;16(8):888-901"

# --- lumbar, Spine 1992;17(3):299-306 ---------------------------------------------------
L = {
    "EPDu": [(34.1, 1.34), (34.6, 1.10), (35.2, 1.10), (35.5, .88), (34.7, 1.17)],
    "EPWu": [(41.2, 1.03), (42.6, .74), (44.1, .88), (46.6, 1.20), (47.3, 1.20)],
    "EPDl": [(35.3, 1.27), (34.9, .74), (34.8, 1.24), (33.9, .85), (33.2, .92)],
    "EPWl": [(43.3, .78), (45.5, 1.10), (48.0, 1.24), (49.5, 1.38), (49.4, 1.41)],
    # VBHp L1 is 1.03 here. The earlier transcription carried 0.92, which is SCW L1's
    # standard error from the next table. See the module docstring.
    "VBHp": [(23.8, 1.03), (24.3, .95), (23.8, 1.10), (24.1, 1.10), (22.9, .95)],
    "SCW":  [(23.7, .92), (23.8, .71), (24.3, .64), (25.4, .49), (27.1, .88)],
    "SCD":  [(19.0, .67), (18.2, .53), (17.5, .53), (18.6, .71), (19.7, .49)],
    "PDWr": [(8.0, .95), (7.8, .57), (10.2, .67), (13.4, .18), (18.0, 1.03)],
    "PDWl": [(9.2, .88), (8.7, .78), (10.1, .53), (14.7, .46), (19.2, 1.03)],
    "PDHr": [(15.9, .81), (15.0, .53), (14.2, .64), (15.7, .57), (19.6, .74)],
    "PDHl": [(15.8, .74), (14.9, .53), (14.6, .60), (15.2, .46), (19.5, .99)],
}
L_PAGE = {k: (("2", "301") if k.startswith("EP") or k == "VBHp" else
              ("3", "302") if k.startswith("SC") else ("4", "302")) for k in L}
L_SRC = "Panjabi MM et al. Spine 1992;17(3):299-306"

# Panjabi's mnemonic -> the name the rest of this package uses
CANON = {"EPWu": "endplate", "EPDu": "endplate_depth",
         "EPWl": "endplate_lower", "EPDl": "endplate_lower_depth",
         "VBHp": "h_post", "SCW": "canal_w", "SCD": "canal_ap",
         "PDWr": "pedicle_w_right", "PDWl": "pedicle_w_left",
         "PDHr": "pedicle_h_right", "PDHl": "pedicle_h_left"}

ROWS = []


def add(measure, level, mean, sem, mnemonic, table, page, src):
    ROWS.append({"measure": measure, "level": level, "mean": round(mean, 3),
                 "sem": round(sem, 4), "n": N, "panjabi_name": mnemonic,
                 "source_table": table, "source_page": page, "citation": src})


def emit(data, levels, pages, src):
    for mnem, series in data.items():
        for lv, cell in zip(levels, series):
            if cell is None:
                continue                      # a dash in the paper: the row does not exist
            t, p = pages[mnem]
            add(CANON[mnem], lv, cell[0], cell[1], mnem, t, p, src)
    # the two-sided measures also get a mean, which is the convention the project uses and
    # the one the lumbar paper itself quotes in prose
    for base, out in (("PDW", "pedicle"), ("PDH", "pedicle_h")):
        r, l_ = data.get(base + "r"), data.get(base + "l")
        if not (r and l_):
            continue
        t, p = pages[base + "r"]
        for lv, a, b in zip(levels, r, l_):
            if a is None or b is None:
                continue
            add(out, lv, (a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0,
                "%s (mean of l/r)" % base, t, p, src)


emit(C, CERVICAL, C_PAGE, C_SRC)
emit(T, THORACIC, T_PAGE, T_SRC)
emit(L, LUMBAR, L_PAGE, L_SRC)

# --- check 1: the earlier independent transcription of T11 and T12 ----------------------
EXPECT = {("endplate", "T11"): (34.9, .97), ("endplate", "T12"): (39.0, .58),
          ("h_post", "T11"): (21.3, .71), ("h_post", "T12"): (22.7, 1.04),
          ("canal_w", "T11"): (19.4, .95), ("canal_w", "T12"): (22.2, 1.12),
          ("canal_ap", "T11"): (16.0, .46), ("canal_ap", "T12"): (18.1, .62),
          ("pedicle", "T11"): (9.75, .635), ("pedicle", "T12"): (8.7, .745)}
bad = []
for (m, lv), (mean, sem) in EXPECT.items():
    got = [r for r in ROWS if r["measure"] == m and r["level"] == lv]
    if not got:
        bad.append("%s %s missing" % (m, lv))
    elif abs(got[0]["mean"] - mean) > .005 or abs(got[0]["sem"] - sem) > .005:
        bad.append("%s %s: built %.3f/%.4f, earlier pass %.3f/%.4f"
                   % (m, lv, got[0]["mean"], got[0]["sem"], mean, sem))

# --- check 2: the lumbar paper's own prose ----------------------------------------------
PROSE = {"L1": 8.6, "L2": 8.2, "L5": 18.9}     # "the width (PDW) was initially 8.6 mm at L1"
for lv, want in PROSE.items():
    got = [r for r in ROWS if r["measure"] == "pedicle" and r["level"] == lv]
    if got and abs(got[0]["mean"] - want) > 0.35:
        bad.append("pedicle %s: built %.2f, the paper's prose says %.1f"
                   % (lv, got[0]["mean"], want))

out = os.path.join(HERE, "panjabi_full_spine.csv")
with open(out, "w", newline="", encoding="utf-8") as fh:
    fh.write("# Panjabi's quantitative three-dimensional anatomy: cervical and thoracic\n"
             "# (1991), lumbar (1992). Every linear dimension of the body, canal and\n"
             "# pedicle tables. Dispersion is the STANDARD ERROR as printed; the\n"
             "# population SD is sem*sqrt(n), n=12. C2 carries no upper end-plate row:\n"
             "# the dens occupies it, so endplate/endplate_depth/h_post start at C3.\n"
             "# There is no anterior body height in these papers; h_post is posterior.\n")
    # An explicit LF terminator: without it csv writes CRLF on Windows and the file churns
    # every time it is rebuilt on another platform. Kept from PR #1.
    w = csv.DictWriter(fh, fieldnames=["measure", "level", "mean", "sem", "n",
                                       "panjabi_name", "source_table", "source_page",
                                       "citation"], lineterminator="\n")
    w.writeheader()
    for r in sorted(ROWS, key=lambda x: (x["measure"], x["level"])):
        w.writerow(r)

print("wrote %s  (%d rows)" % (out, len(ROWS)))
print("  measures: %s" % ", ".join(sorted({r["measure"] for r in ROWS})))
print("  levels:   C2-C7, T1-T12, L1-L5")
if bad:
    print("\nCHECK FAILED:")
    for b in bad:
        print("  " + b)
    sys.exit(1)
print("  check 1: all %d T11/T12 values match the earlier independent pass" % len(EXPECT))
print("  check 2: pedicle means reproduce the lumbar paper's own prose at L1, L2, L5")
