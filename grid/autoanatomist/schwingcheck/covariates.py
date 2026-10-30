"""A patient's height, weight, age and sex, and how the models take them.

The owner, 27 October 2026, 11:06 UTC: "you should also include the Table 1 data: age, sex,
weight (kg), height (cm) as a variable for modelling and use how appropriate, particularly in my
opinion height should statistically and measurable increase the size of all vertebra in most
dimensions, while body weight should should predictably compress the disc spaces and affect
facet articulation in some degree, similarly age should affect the facet articulation, and
those statistics should be used in the model with future direction being multiple populations
from multiple studies which will need to account for these to avoid confounding factors".

What the papers allow. Panjabi prints each level's mean and standard error over twelve spines
and no measurement of one spine (table.SPECIMENS_NOTE), so no coefficient below is estimated
from them. What is here is the place each covariate enters the model, with a prior where
anatomy gives one and a hook fixed at zero where it does not, so that item 5's data (a CT and a
height, weight, age and sex per patient) estimates them without changing the model's shape:

- Height scales the patient's size s, which multiplies every length (and, in step e, every
  area by s^2): log s = beta_height * log(height / HEIGHT_REF) + eps, eps ~ N(0, scale_sd^2). The
  prior beta_height ~ N(1, 0.5^2) is isometric scaling, every length in proportion to stature,
  as a starting belief and not a measurement. Integrated over that prior, a patient of known
  height has log s ~ N(log(h / HEIGHT_REF), scale_sd^2 + 0.5^2 log(h / HEIGHT_REF)^2); a patient
  of unknown height has the archive's log s ~ N(0, scale_sd^2) exactly, so every record is
  reproduced. The residual SD is kept at the archive's 0.07, which overstates it once height is
  known: conservative until item 5 estimates it.
- Sex shifts log s by `sex_size` (male against female), a hook at 0.
- Weight and age shift a measure's mean by a factor exp(gamma_weight * w + gamma_age * a), w and
  a the patient's weight and age standardised on Panjabi's twelve specimens, each gamma one
  coefficient per measure (`weight_effects`, `age_effects`), every one 0 today. The owner's expectations, weight on the disc spaces and the
  facets and age on the facets, are where item 5 will look first: the facet measures enter in
  step e, and no disc space is in Panjabi's tables.

Pooling populations from several studies (the owner's future direction) then means adjusting
each study's table for its specimens' covariates through these terms, so that a difference in
stature between series is not read as a difference in anatomy.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence

import numpy as np


def _specimen_reference():
    """The means and SDs of Panjabi's twelve specimens (thoracic Table 1), the reference every
    covariate is measured from, read from the committed specimens CSV."""
    from . import table as T
    rows = T.read_specimens_csv()
    h = np.array([float(r["height_cm"]) for r in rows])
    w = np.array([float(r["weight_kg"]) for r in rows])
    a = np.array([float(r["age_years"]) for r in rows])
    male = np.array([r["sex"] == "M" for r in rows], float)
    return {"height_cm": (float(h.mean()), float(h.std(ddof=1))), "weight_kg": (float(w.mean()), float(w.std(ddof=1))),
            "age_years": (float(a.mean()), float(a.std(ddof=1))), "male": (float(male.mean()), float(male.std(ddof=1)))}


REFERENCE = _specimen_reference()
HEIGHT_REF = REFERENCE["height_cm"][0]          # 167.75 cm, the twelve specimens' mean


@dataclass(frozen=True)
class Covariates:
    """One patient's covariates, NaN (or an empty sex) where unknown."""
    height_cm: float = float("nan")
    weight_kg: float = float("nan")
    age_years: float = float("nan")
    sex: str = ""                               # "M", "F" or "" for unknown


@dataclass(frozen=True)
class CovariateModel:
    """How the covariates enter: the size prior and the hooks. The defaults are the archive's
    size prior for a patient of unknown height, isometric scaling for one of known height, and
    every hook at zero."""
    scale_sd: float = 0.07
    beta_height: float = 1.0                    # prior mean of d log s / d log height: isometric
    beta_height_sd: float = 0.5                 # prior SD, integrated into the size prior
    height_ref: float = HEIGHT_REF
    sex_size: float = 0.0                       # hook: log s, male against female
    weight_effects: Dict[str, float] = field(default_factory=dict)     # hook: measure -> gamma per SD of weight
    age_effects: Dict[str, float] = field(default_factory=dict)        # hook: measure -> gamma per SD of age

    def size_prior(self, covs: Sequence[Covariates]):
        """The normal prior of log s for each patient: (mean, SD) arrays, the archive's (0, 0.07)
        where nothing is known."""
        dlogh = np.array([0.0 if not np.isfinite(c.height_cm) else math.log(c.height_cm / self.height_ref)
                          for c in covs])
        male = sex_centred(covs)
        mean = self.beta_height * dlogh + self.sex_size * male
        sd = np.sqrt(self.scale_sd ** 2 + (self.beta_height_sd * dlogh) ** 2)
        return mean, sd

    def mean_factors(self, covs: Sequence[Covariates], measures: Sequence[str]) -> np.ndarray:
        """exp(gamma_weight w + gamma_age a) for each patient and measure (P, M), w and a the
        weight and age standardised: all ones while the hooks are zero."""
        zw = standardised(covs, "weight_kg")
        za = standardised(covs, "age_years")
        gw = np.array([self.weight_effects.get(m, 0.0) for m in measures])
        ga = np.array([self.age_effects.get(m, 0.0) for m in measures])
        return np.exp(zw[:, None] * gw[None, :] + za[:, None] * ga[None, :])

    @property
    def hooks_off(self) -> bool:
        return self.sex_size == 0.0 and not any(self.weight_effects.values()) and not any(self.age_effects.values())


def standardised(covs: Sequence[Covariates], name: str) -> np.ndarray:
    """(value - the specimens' mean) / their SD, 0 where unknown."""
    mean, sd = REFERENCE[name]
    v = np.array([getattr(c, name) for c in covs], float)
    return np.where(np.isfinite(v), (v - mean) / sd, 0.0)


def sex_centred(covs: Sequence[Covariates]) -> np.ndarray:
    """1 for a man, 0 for a woman, centred on the specimens' share of men; 0 where unknown."""
    share = REFERENCE["male"][0]
    return np.array([(1.0 if c.sex == "M" else 0.0) - share if c.sex in ("M", "F") else 0.0 for c in covs])


def unknown(n: int) -> list:
    return [Covariates() for _ in range(n)]


def from_specimens() -> list:
    """Panjabi's twelve specimens as Covariates, in Table 1's order."""
    from . import table as T
    return [Covariates(height_cm=float(r["height_cm"]), weight_kg=float(r["weight_kg"]),
                       age_years=float(r["age_years"]), sex=r["sex"]) for r in T.read_specimens_csv()]
