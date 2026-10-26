"""A spine drawn from Panjabi's published numbers, and anomalous spines drawn beside it.

    from panjabi import load_reference, synthesize, PHENOTYPES
    ref = load_reference()                       # reference/panjabi_full_spine.csv
    col = synthesize(ref, "six_lumbar", rng)     # one column, levels named by count

WHY A GENERATOR AT ALL. The question the junction predictor answers is whether the
cervico-thoracic and thoraco-lumbar junctions can be placed from the shape of the bone
alone, with no count from C2, and whether that placement survives an anomaly at the other
end of the spine. The only whole-spine morphometry with a published mean and dispersion
at every level is Panjabi's three cadaveric papers (twelve spines, C2 to L5), so the
predictor is trained on columns drawn from those numbers and nothing else. A column drawn
here is realistic in the one sense that matters for the question: every level carries the
published mean, the published spread, a patient's own size and a measurement error.

WHAT IS DRAWN, PER COLUMN. For every measure m and level i:

    value = s * (mu[m][i] + sd[m][i] * (rho * z[m] + sqrt(1 - rho^2) * e[m][i])) + n[m][i]

s is the patient's size (one log-normal factor for the whole column), z[m] the patient's
own offset in that measure shared by every level (a person with wide canals has them at
every level), e the per-level draw, and n a measurement error in millimetres. sd is the
population SD, sem * sqrt(12), never the printed standard error (reference/build_panjabi.py).

THE ANOMALIES ARE DEFINED BY THE COUNT, as a radiologist with C2 in view would define
them, and the truth every table scores against follows from the count, not from the shape:

  four_lumbar   L5 is absorbed into the sacrum and is not a free vertebra: the column ends
                at L4. Both junctions are where they always were.
  six_lumbar    S1 is lumbarised: an L6 below L5, its morphology the lumbar trend carried
                one level on. Both junctions are where they always were.
  t13           a thirteenth rib-bearing vertebra between T12 and L1, its body T12's in
                shape at blend 0 and L1's at blend 1. The count from C2 names it L1, so by
                the count the thoraco-lumbar junction is above it; by the ribs it is below.
  lumbar_rib    a rib on L1. L1 is lumbar by count; its body leans toward T12 in shape; by
                the ribs the junction is below it.
  no_rib_t12    the twelfth rib is absent. T12 is thoracic by count; its body leans toward
                L1 in shape; by the ribs the junction is above it.

TWO TRUTHS AT THE THORACOLUMBAR JUNCTION. Column.cut gives the count's answer, the one
bordercall scores against everywhere; Column.cut(..., truth="ribs") gives the rib reading's,
one level apart on the three thoracolumbar phenotypes and the same elsewhere, and the
evaluation reports both side by side, since on a real spine a rib on L1 can be a rudimentary
rib or a thirteenth thoracic vertebra and only the count tells them apart. The t13 column and
the lumbar_rib column are one anatomy (a rib-bearing body the count names L1) drawn from the
two ends of the blend.

The blend, how far the transitional body leans, is a parameter (default one half) and is
swept by the evaluation, because nothing published measures it: it is the one assumption
here that the data do not supply, and the hard case lives in it.

C2 IS LEFT OUT. The dens occupies the upper end-plate, so Panjabi prints no end-plate width
or posterior height for it; a column here runs C3 to L5, twenty-two levels. C2 is the
anchor a count starts from, not a level whose shape needs naming.
"""
from __future__ import annotations

import csv
import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REFERENCE = os.path.join(HERE, "reference", "panjabi_full_spine.csv")

CERVICAL = ["C%d" % i for i in range(3, 8)]
THORACIC = ["T%d" % i for i in range(1, 13)]
LUMBAR = ["L%d" % i for i in range(1, 6)]
LEVELS = CERVICAL + THORACIC + LUMBAR
MEASURES = ["endplate", "h_post", "canal_w", "canal_ap", "pedicle"]
PRETTY_MEASURE = {"endplate": "End-plate width", "h_post": "Posterior body height",
                  "canal_w": "Canal width", "canal_ap": "Canal depth",
                  "pedicle": "Pedicle width"}

PHENOTYPES = ["typical", "four_lumbar", "six_lumbar", "t13", "lumbar_rib", "no_rib_t12"]
PRETTY = {"typical": "Typical column",
          "four_lumbar": "Four lumbar (sacralised L5)",
          "six_lumbar": "Six lumbar (lumbarised S1)",
          "t13": "Thirteenth rib-bearing vertebra",
          "lumbar_rib": "Rib on L1",
          "no_rib_t12": "No rib on T12"}
LUMBOSACRAL = ("four_lumbar", "six_lumbar")
THORACOLUMBAR = ("t13", "lumbar_rib", "no_rib_t12")
# how far the rib reading moves the thoracolumbar cut from the count's, by phenotype
RIB_SHIFT = {"t13": 1, "lumbar_rib": 1, "no_rib_t12": -1}


def region_of(level: str) -> str:
    """C, T or L, by the name the count gives the level: a thirteenth rib-bearing body is L1."""
    return "L" if level == "T13" else level[0]


def load_reference(path: str = DEFAULT_REFERENCE, measures: Sequence[str] = MEASURES):
    """{measure: {level: (mean, population SD)}} from the Panjabi table."""
    ref: Dict[str, Dict[str, tuple]] = {m: {} for m in measures}
    with open(path) as fh:
        rows = csv.DictReader(l for l in fh if not l.startswith("#"))
        for r in rows:
            m = (r.get("measure") or "").strip()
            if m not in ref:
                continue
            n = float(r.get("n") or 12)
            sd = r.get("sd")
            try:
                sd = float(sd)
            except (TypeError, ValueError):
                sd = float(r["sem"]) * math.sqrt(n)
            ref[m][(r.get("level") or "").strip()] = (float(r["mean"]), sd)
    for m in measures:
        missing = [l for l in LEVELS if l not in ref[m]]
        if missing:
            raise SystemExit("reference lacks %s at %s" % (m, ", ".join(missing)))
    return ref


@dataclass
class Column:
    """One synthetic spine: levels named by the count, one value per measure per level."""
    levels: List[str]
    values: Dict[str, np.ndarray]
    phenotype: str = "typical"
    blend: float = 0.0
    # which position holds the transitional body, when there is one
    transitional_at: Optional[int] = None
    meta: dict = field(default_factory=dict)

    def __len__(self):
        return len(self.levels)

    @property
    def regions(self) -> List[str]:
        return [region_of(l) for l in self.levels]

    def cut(self, junction: str, truth: str = "count") -> int:
        """How many levels sit above the junction (ct or tl): the count's answer, or with
        truth="ribs" the rib reading's, one level apart at T12/L1 when the transitional body
        is in view (RIB_SHIFT) and the same everywhere else."""
        regs = self.regions
        if junction == "ct":
            k = sum(1 for r in regs if r == "C")
        elif junction == "tl":
            k = sum(1 for r in regs if r in ("C", "T"))
        else:
            raise ValueError(junction)
        if truth == "ribs" and junction == "tl" and self.transitional_at is not None:
            k = min(max(k + RIB_SHIFT.get(self.phenotype, 0), 0), len(self.levels))
        elif truth not in ("count", "ribs"):
            raise ValueError(truth)
        return k

    def window(self, start: int, stop: int) -> "Column":
        """Levels start..stop-1, as a field of view would hold them."""
        sub = Column(levels=self.levels[start:stop],
                     values={m: v[start:stop] for m, v in self.values.items()},
                     phenotype=self.phenotype, blend=self.blend,
                     meta=dict(self.meta, start=start, stop=stop))
        if self.transitional_at is not None and start <= self.transitional_at < stop:
            sub.transitional_at = self.transitional_at - start
        return sub


def _profile(ref, measure, levels, blend_at=None, blend=0.0, extra_l6=False):
    """Means and SDs along the column, with the anomalies' edits applied."""
    mu = np.array([ref[measure][l][0] for l in levels], float)
    sd = np.array([ref[measure][l][1] for l in levels], float)
    if extra_l6:
        # the lumbar trend carried one level on: L5 plus half of the L4 -> L5 step
        m4, m5 = ref[measure]["L4"][0], ref[measure]["L5"][0]
        mu = np.append(mu, m5 + 0.5 * (m5 - m4))
        sd = np.append(sd, ref[measure]["L5"][1])
    if blend_at is not None:
        t12, l1 = ref[measure]["T12"], ref[measure]["L1"]
        base, toward = blend_at
        a, b = (t12, l1) if base == "T12" else (l1, t12)
        mu[toward] = (1 - blend) * a[0] + blend * b[0]
        sd[toward] = (1 - blend) * a[1] + blend * b[1]
    return mu, sd


def synthesize(ref, phenotype: str, rng: np.random.Generator, scale_sd: float = 0.07,
               rho: float = 0.5, noise_mm: float = 1.0, blend: float = 0.5,
               measures: Sequence[str] = MEASURES, draws: Optional[dict] = None) -> Column:
    """One column of the given phenotype.

    `draws` lets a caller make twins: the same patient size, offsets and per-level draws
    reused across phenotypes, so that a six-lumbar twin differs from its typical twin in
    nothing but the extra level. The dict is filled on the first call and read on the next.
    """
    if phenotype not in PHENOTYPES:
        raise ValueError(phenotype)
    levels = list(LEVELS)
    transitional_at = None
    blend_at = None
    extra_l6 = False
    if phenotype == "four_lumbar":
        levels = levels[:-1]
    elif phenotype == "six_lumbar":
        levels = levels + ["L6"]
        extra_l6 = True
    elif phenotype == "t13":
        i = levels.index("L1")
        levels = levels[:i] + ["T13"] + levels[i:]
        transitional_at = i
    elif phenotype == "lumbar_rib":
        transitional_at = levels.index("L1")
        blend_at = ("L1", transitional_at)
    elif phenotype == "no_rib_t12":
        transitional_at = levels.index("T12")
        blend_at = ("T12", transitional_at)

    n = len(levels)
    draws = draws if draws is not None else {}
    if "scale" not in draws:
        draws["scale"] = float(np.exp(rng.normal(0.0, scale_sd)))
        draws["offset"] = {m: float(rng.normal()) for m in measures}
        # per-level draws are keyed by level name, so a twin reuses them level for level
        draws["level"] = {m: {l: float(rng.normal()) for l in LEVELS + ["L6", "T13"]}
                          for m in measures}
        draws["noise"] = {m: {l: float(rng.normal()) for l in LEVELS + ["L6", "T13"]}
                          for m in measures}
    s = draws["scale"]
    values = {}
    for m in measures:
        if phenotype == "t13":
            base = [l for l in levels if l != "T13"]
            mu, sd = _profile(ref, m, base)
            i = transitional_at
            t12, l1 = ref[m]["T12"], ref[m]["L1"]
            mu = np.insert(mu, i, (1 - blend) * t12[0] + blend * l1[0])
            sd = np.insert(sd, i, (1 - blend) * t12[1] + blend * l1[1])
        else:
            mu, sd = _profile(ref, m, [l for l in levels if l != "L6"],
                              blend_at=blend_at, blend=blend, extra_l6=extra_l6)
        e = np.array([draws["level"][m][l] for l in levels])
        nz = np.array([draws["noise"][m][l] for l in levels])
        z = draws["offset"][m]
        v = s * (mu + sd * (rho * z + math.sqrt(1 - rho * rho) * e)) + noise_mm * nz
        values[m] = np.maximum(v, 0.5)
    return Column(levels=levels, values=values, phenotype=phenotype,
                  blend=blend if transitional_at is not None else 0.0,
                  transitional_at=transitional_at, meta={"scale": s})


def twins(ref, rng, phenotypes: Sequence[str], **kw) -> Dict[str, Column]:
    """The same patient drawn under each phenotype."""
    draws: dict = {}
    return {p: synthesize(ref, p, rng, draws=draws, **kw) for p in phenotypes}
