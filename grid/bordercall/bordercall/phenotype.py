"""Per-case phenotype, read from the label volume and nothing else.

The point of this file is that it takes NO corpus-specific table. CTSpinoPelvic1K's own
breakout read `transition_morphometrics.csv`, which only that release has. Everything here
comes from the identifiers in the mask, so the same classes can be assigned on any corpus
segmented under the same scheme.

    python run.py phenotype --labels /path/to/labels --out phenotype.csv

WHAT IS READ

  lowest_rib_bearing   the most caudal vertebra carrying a rib, found from the labels and
                       never assumed to be T12. A rib on a lumbar body moves it down a
                       level, and that is the phenotype worth catching.
  n_lumbar             how many lumbar identifiers the column holds (4, 5 or 6).
  has_l6 / has_t13     the two enumeration anomalies the scheme can express.
  phenotype            one class per case, most specific first, thoracolumbar before
                       lumbosacral, so the groups are disjoint and a case carrying both is
                       counted at the border where it can actually be tested.

THE IDENTIFIER SCHEME IS ASSUMED, NOT DETECTED, and this is the first thing to check on a new
corpus. `scheme.py` carries the VerSe-native map this programme uses. Resolving a name against
the wrong map returns a finite, plausible, wrong answer: it has already happened here, where
pelvic incidence was computed for a whole release against a legacy map and the only symptom
was a quality flag about a structure that was plainly there. Run `python run.py scheme
--labels <dir>` first; it prints what is actually in the volumes against what the scheme
expects, and says plainly when they disagree.
"""
from __future__ import annotations

import csv
import os
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

import nibabel as nib
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scheme as S

CLASS_ORDER = ["lumbar_rib", "no_rib_T12", "six_lumbar", "four_lumbar", "typical"]
PRETTY = {"lumbar_rib": "Rib on a lumbar body",
          "no_rib_T12": "No rib on the last thoracic",
          "six_lumbar": "Six lumbar vertebrae",
          "four_lumbar": "Four lumbar identifiers",
          "typical": "Typical column"}


def read_phenotype(path):
    """One case -> its phenotype fields, from the identifiers present in the mask."""
    stem = Path(path).name
    for suffix in ("_label.nii.gz", ".nii.gz", ".nii"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    r = {"case": stem}
    try:
        lab = np.asanyarray(nib.load(path).dataobj)
    except Exception as exc:                                        # noqa: BLE001
        return {"case": stem, "error": type(exc).__name__}
    present = {int(v) for v in np.unique(lab) if v}

    lumbar = [v for v in S.LUMBAR_IDS if v in present]
    r["n_lumbar"] = len(lumbar)
    r["has_l6"] = int(S.L6_ID in present)
    r["has_t13"] = int(S.T13_ID in present)
    r["has_lumbar_rib"] = int(any(v in present for v in S.LUMBAR_RIB_IDS))

    # the lowest vertebra carrying a NUMBERED rib
    levels = [S.rib_level(v) for v in present]
    levels = [l for l in levels if l]
    rostral = None
    if levels:
        vid = S.thoracic_id(max(levels))
        if vid in present:
            rostral = vid
    # a rib on a lumbar body overrides it: that body is now the lowest rib-bearing one
    if r["has_lumbar_rib"] and lumbar:
        rostral = min(lumbar)
    r["lowest_rib_bearing"] = S.name_of(rostral) if rostral else ""
    r["lowest_rib_bearing_id"] = rostral or ""

    # CAN THIS COLUMN BE COUNTED? The whole premise of a "known ground truth" for a
    # vertebral name is a count from C2 downward. A volume without C2 cannot supply one,
    # whatever its labels say, so the name of its border vertebra is a reader's call and
    # not a verified fact. This flag is what `sweep` filters on: results are reported on
    # countable records, and the rest are set aside rather than quietly averaged in.
    r["has_c2"] = int(S.CERVICAL_FIRST + 1 in present)
    top = [v for v in S.VERTEBRA_IDS if v in present]
    r["topmost"] = S.name_of(min(top)) if top else ""
    r["countable"] = r["has_c2"]

    r["phenotype"] = classify_row(r)
    return r


def classify_row(r):
    """One class per case, most specific first, thoracolumbar before lumbosacral."""
    rb = r.get("lowest_rib_bearing") or ""
    expected = S.name_of(S.thoracic_id(S.N_THORACIC))      # T12 under the usual scheme
    if r.get("has_lumbar_rib") or (rb.startswith("L") and rb != ""):
        return "lumbar_rib"
    if rb and rb != expected:
        return "no_rib_T12"                                 # the rib stops a level early
    if r.get("has_l6") or r.get("n_lumbar") == 6:
        return "six_lumbar"
    if r.get("n_lumbar") == 4:
        return "four_lumbar"
    return "typical"


FIELDS = ["case", "phenotype", "countable", "has_c2", "topmost",
          "n_lumbar", "has_l6", "has_t13", "has_lumbar_rib",
          "lowest_rib_bearing", "lowest_rib_bearing_id", "error"]


def run(labels_dir, out, jobs=0):
    files = sorted(str(p) for p in Path(labels_dir).glob("*.nii.gz"))
    if not files:
        raise SystemExit("no *.nii.gz under %s" % labels_dir)
    jobs = jobs or max(1, (os.cpu_count() or 2) - 2)
    print("%d volumes, %d workers" % (len(files), jobs))
    rows = []
    with Pool(jobs) as pool:
        for i, r in enumerate(pool.imap_unordered(read_phenotype, files, chunksize=4), 1):
            rows.append(r)
            if i % 100 == 0:
                print("  %d/%d" % (i, len(files)), flush=True)
    rows.sort(key=lambda d: d["case"])
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print("wrote %s" % out)
    c = Counter(r.get("phenotype") for r in rows if r.get("phenotype"))
    for k in CLASS_ORDER:
        if c[k]:
            print("  %-30s %5d" % (PRETTY[k], c[k]))
    n_count = sum(1 for r in rows if r.get("countable"))
    print("  %-30s %5d of %d  (C2 present, so the column can be counted)"
          % ("countable", n_count, len(rows)))
    if n_count == 0:
        print("  NO RECORD CONTAINS C2. Every border name in this corpus is a reader's")
        print("  call rather than a verified count; `sweep` will refuse to report on it.")
    bad = [r for r in rows if r.get("error")]
    if bad:
        print("  %d volume(s) failed to read" % len(bad))
    return rows


def load(path):
    """phenotype.csv -> {case: row}"""
    out = {}
    with open(path, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        for k in ("n_lumbar", "has_l6", "has_t13", "has_lumbar_rib",
                  "countable", "has_c2"):
            try:
                r[k] = int(r[k])
            except (TypeError, ValueError):
                r[k] = 0
        out[r["case"]] = r
    return out
