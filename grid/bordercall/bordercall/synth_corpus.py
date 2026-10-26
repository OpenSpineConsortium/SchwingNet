"""A made-up corpus in the layout the grid's job writes, so every command downstream of
`measure` can be run end to end anywhere, with no CT.

    python run.py synth-corpus --out out/synth --n 300 --seed 0

The columns come from panjabi.py's generator (Panjabi's means and spreads, a patient size, a
spine-wide tilt and per-level noise), named as the count from C2 names them, which is what
tools/bordercall_corpus.py in SchwingNet does on a real mask: a thirteenth rib-bearing body is
L1 with a rib and the lumbar count is six, a column of four lumbar bodies ends at L4. The two
measures Panjabi's tables lack but border.py's model needs, the anterior body height and the
transverse-process span, are fabricated from the measures that are there with a shape of their
own by region, so the published model has something to fit; nothing fabricated is a finding.
The phenotype file carries the rib reading the grid's job takes from the census's rib table,
which is what disagree.py's independent arm reads.

Fabricated, not validated: numbers from this corpus prove that the commands run and agree with
each other, never anything about a spine.
"""
from __future__ import annotations

import csv
import os
import sys
from typing import Dict, List

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import panjabi as P  # noqa: E402

MEASURES = ["endplate", "h_post", "canal_w", "canal_ap"]
COLUMN = {"endplate": "endplate_width_{}_mm", "h_post": "body_height_post_{}_mm",
          "canal_w": "canal_width_{}_mm", "canal_ap": "canal_ap_{}_mm",
          "body_height": "body_height_{}_mm", "tp_span": "tp_span_{}_mm"}
# how often each of the generator's phenotypes is drawn; the shares are made up
SHARES = {"typical": 0.64, "four_lumbar": 0.07, "six_lumbar": 0.10, "t13": 0.05,
          "lumbar_rib": 0.06, "no_rib_t12": 0.08}
# the generator's phenotype -> bordercall's five classes and the rib reading the census gives
CLASS_OF = {"typical": "typical", "four_lumbar": "four_lumbar", "six_lumbar": "six_lumbar",
            "t13": "lumbar_rib", "lumbar_rib": "lumbar_rib", "no_rib_t12": "no_rib_T12"}
LOWEST_RIB = {"typical": "T12", "four_lumbar": "T12", "six_lumbar": "T12", "t13": "L1",
              "lumbar_rib": "L1", "no_rib_t12": "T11"}
# the transverse-process span over the end-plate width, by region, a shape of its own
TP_OVER_ENDPLATE = {"C": 1.9, "T": 1.5, "L": 1.75}


def count_names(column: P.Column) -> List[str]:
    """The names a count from C2 gives the generator's column: thirteen thoracic bodies become
    twelve and a first lumbar, since the count knows no T13."""
    names = list(column.levels)
    if "T13" in names:
        i = names.index("T13")
        names = names[:i] + ["L%d" % k for k in range(1, len(names) - i + 1)]
    return names


def shape_factor(level: str) -> float:
    """The transverse-process span over the end-plate width of a body of this shape: the region's
    factor, the thoracic span narrowing down the column and the lumbar widening to L3 then
    narrowing. Keyed to the generator's own level name, the shape it drew, never to the count's
    name, so a transitional body carries its shape's span and the count arm has nothing to read
    the count off."""
    region, k = level[0], int(level[1:])
    f = TP_OVER_ENDPLATE[region]
    if region == "T":
        return f * (1.0 - 0.02 * (k - 1))
    if region == "L":
        return f * (1.0 + 0.04 * min(k - 1, 2) - 0.03 * max(k - 3, 0))
    return f


def fabricate(column: P.Column, rng: np.random.Generator) -> Dict[str, np.ndarray]:
    """The two measures the table lacks, from the ones it has, by the shape the generator drew:
    the transitional body's span is blended between its two shapes as its end-plate is."""
    ep = column.values["endplate"]
    hp = column.values["h_post"]
    factor = np.array([shape_factor(l) for l in column.levels])
    i = column.transitional_at
    if i is not None:
        own, other = {"t13": ("T12", "L1"), "lumbar_rib": ("L1", "T12"), "no_rib_t12": ("T12", "L1")}[column.phenotype]
        factor[i] = (1 - column.blend) * shape_factor(own) + column.blend * shape_factor(other)
    tilt = rng.normal(0.0, 0.04)
    tp = factor * ep * np.exp(tilt + rng.normal(0, 0.05, len(ep)))
    body = hp * np.exp(rng.normal(0.03, 0.03, len(hp)))
    return {"tp_span": tp, "body_height": body}


def write(outdir: str, n: int = 300, seed: int = 0) -> Dict[str, int]:
    os.makedirs(outdir, exist_ok=True)
    rng = np.random.default_rng(seed)
    ref = P.load_reference(measures=MEASURES)
    phenotypes = list(SHARES)
    shares = np.array([SHARES[k] for k in phenotypes]) / sum(SHARES.values())
    levels_rows, phen_rows, counts = [], [], {}
    all_levels = ["C2"] + P.CERVICAL + P.THORACIC + P.LUMBAR + ["L6"]
    for i in range(n):
        ph = phenotypes[rng.choice(len(phenotypes), p=shares)]
        column = P.synthesize(ref, ph, rng, measures=MEASURES)
        names = count_names(column)
        values = dict(column.values, **fabricate(column, rng))
        case = "synthetic__%04d" % i
        row = {"case": case}
        for m, template in COLUMN.items():
            for name, v in zip(names, values[m]):
                row[template.format(name)] = "%.2f" % v
        levels_rows.append(row)
        n_lumbar = sum(1 for nm in names if nm[0] == "L")
        low = LOWEST_RIB[ph]
        phen_rows.append({
            "case": case, "phenotype": CLASS_OF[ph], "countable": 1, "has_c2": 1, "topmost": "C2",
            "n_lumbar": n_lumbar, "has_l6": int(n_lumbar == 6), "has_t13": 0,
            "has_lumbar_rib": int(low.startswith("L")), "lowest_rib_bearing": low,
            "lowest_rib_bearing_id": "", "first_rib_bearing": "T1", "n_from_c2": len(names) + 1,
            "has_sacrum": 1, "phenotype_known": 1, "collection": "synthetic", "error": ""})
        counts[CLASS_OF[ph]] = counts.get(CLASS_OF[ph], 0) + 1
    columns = ["case"] + [COLUMN[m].format(lv) for lv in all_levels for m in COLUMN]
    with open(os.path.join(outdir, "levels.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=columns, restval="")
        w.writeheader()
        w.writerows(levels_rows)
    with open(os.path.join(outdir, "phenotype.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(phen_rows[0]))
        w.writeheader()
        w.writerows(phen_rows)
    print("wrote %d made-up columns to %s/levels.csv and phenotype.csv; by class: %s"
          % (n, outdir, ", ".join("%s %d" % kv for kv in sorted(counts.items()))))
    return counts
