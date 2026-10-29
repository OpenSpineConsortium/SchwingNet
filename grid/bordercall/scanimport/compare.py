"""Every chord taken on the imports set beside Panjabi's, level by level: the check that comes
before any naming result is believed.

    python -m scanimport compare imports/verse imports/totalseg --out imports/compare

The rule assumes the imports' chords are Panjabi's chords: the same landmarks, the same scale.
Nothing in a mask guarantees that. A whole-vertebra label includes the cortex Panjabi's calipers
sat on, a segmenter can swell or shrink a body by a voxel, a film's magnification is a guess.
So before a score is read, each measure's imported mean at each level is set beside Panjabi's
mean and population SD: the difference in millimetres, the difference over Panjabi's SD (how
far the whole population is shifted, in the rule's own units), and the ratio of the imported
mean to Panjabi's, whose spread down the column says whether a difference is one scale (the
rule integrates a scale) or a change of shape (it does not).

Only bodies whose names were counted from C2 are compared by default, since a misnamed body
would be compared with the wrong level's row; --all takes every named body and says so.
"""
from __future__ import annotations

import csv
import math
import os
from typing import Dict, List, Sequence

import numpy as np

from . import RULE_LEVELS, SEVEN, archive_path
from .column import read_columns

archive_path()
import panjabi as P                                                  # noqa: E402


def compare(directories: Sequence[str], counted_only: bool = True, measures: Sequence[str] = SEVEN) -> List[Dict]:
    ref = P.load_reference(P.DEFAULT_REFERENCE, list(measures))
    got: Dict[str, Dict[str, List[float]]] = {m: {lv: [] for lv in RULE_LEVELS} for m in measures}
    studies: Dict[str, Dict[str, set]] = {m: {lv: set() for lv in RULE_LEVELS} for m in measures}
    for d in directories:
        for col in read_columns(d):
            if counted_only and not col.study.get("countable"):
                continue
            for b in col.bodies:
                if b.level not in RULE_LEVELS:
                    continue
                for m in measures:
                    v = b.values.get(m, math.nan)
                    if np.isfinite(v):
                        got[m][b.level].append(float(v))
                        studies[m][b.level].add(col.study["study_id"])
    rows = []
    for m in measures:
        for lv in RULE_LEVELS:
            pm, psd = ref[m][lv]
            xs = np.array(got[m][lv])
            row = {"measure": m, "level": lv, "panjabi_mean": pm, "panjabi_sd": round(psd, 3),
                   "bodies": int(len(xs)), "studies": len(studies[m][lv])}
            if len(xs):
                mean = float(xs.mean())
                row.update({"import_mean": round(mean, 3),
                            "import_sd": round(float(xs.std(ddof=1)), 3) if len(xs) > 1 else None,
                            "difference_mm": round(mean - pm, 3), "difference_in_sd": round((mean - pm) / psd, 3),
                            "ratio": round(mean / pm, 4)})
            rows.append(row)
    return rows


def ratio_spread(rows: List[Dict]) -> Dict[str, Dict[str, float]]:
    """Per measure, the mean and spread of log(import mean / Panjabi mean) down the column: a
    small spread is a scale the rule absorbs, a large one a change of shape it does not."""
    out = {}
    for m in sorted({r["measure"] for r in rows}):
        r = np.array([math.log(x["ratio"]) for x in rows if x["measure"] == m and x.get("ratio")])
        if len(r):
            out[m] = {"levels": int(len(r)), "mean_log_ratio": round(float(r.mean()), 4),
                      "sd_log_ratio": round(float(r.std(ddof=1)), 4) if len(r) > 1 else None}
    return out


def write(out: str, rows: List[Dict], counted_only: bool = True) -> str:
    """compare.csv, its first line saying which bodies it was taken from."""
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "compare.csv")
    fields = ["measure", "level", "bodies", "studies", "panjabi_mean", "panjabi_sd", "import_mean", "import_sd",
              "difference_mm", "difference_in_sd", "ratio"]
    with open(path, "w", newline="") as fh:
        fh.write("# bodies %s\n" % ("counted_from_c2" if counted_only else "every_named_body"))
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return path
