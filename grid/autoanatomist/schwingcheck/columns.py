"""Columns as arrays: (column, body, measure), NaN where a column has no body, and the fields
cut from them with integer offsets.

The generator is the archive's (archive/bordercall/panjabi.py, synthesize, and neighbour.py,
draw_columns) drawn here from the long table: for every measure m and level i,

    value = s^p * (mu[m][i] + sd[m][i] * (rho * z[m] + sqrt(1 - rho^2) * e[m][i])) + noise[m] * n[m][i]

with s the patient's size, p the measure's power of it (1 for a length, the archive's only kind,
2 for an area, 0 for an angle; step e), z the patient's offset in that measure, e the level's
draw and n the measurement error's draw, scaled by the measure's own error (1 mm for every one in
the archive), floored at 0.5 where the measure scales with the size (an angle, which may be
negative, has no floor), and the six phenotypes (typical, four_lumbar, six_lumbar,
t13, lumbar_rib, no_rib_t12) edited into the column as the archive edits them. It consumes the
random stream in the archive's order, the size, then one offset per measure, then 24 level
draws per measure in turn, then 24 noise draws per measure in turn, so the same seed gives the
same columns to the last bit (tests/test_schwingcheck_columns.py). The draws of one column are
made at once as arrays; the one loop is over columns, since each column's draws must follow
the one before it in the stream.

Given the patients' sizes (`scale`), no size is drawn and the stream starts at the offsets, so
further measures can be drawn for the same patients from a stream of their own, leaving the first
measures' columns as they were (the build-up study of step e draws the record's seven so and adds
the rest). That holds at r_between 0, the default: at any other, the further measures' offsets are
drawn apart from the first measures' and do not correlate with them as one call's would. With
`floor` False no value is floored, as the build-up study's specimens are drawn
(curve.estimated_table), the stream unchanged.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import LEVELS
from . import correlation as CORR

PHENOTYPES = ["typical", "four_lumbar", "six_lumbar", "t13", "lumbar_rib", "no_rib_t12"]
DRAW_LEVELS = LEVELS + ["L6", "T13"]           # the level draws are keyed by name, 24 per measure
SYNTH = dict(rho=0.5, noise_mm=1.0, scale_sd=0.07, blend=0.5)
FLOOR = 0.5


def exchangeable(k: int, r: float) -> np.ndarray:
    lo = -1.0 / (k - 1) if k > 1 else -1.0
    if not (lo - 1e-12 <= r <= 1.0):
        raise ValueError("r = %.3f is not a correlation for %d measures" % (r, k))
    R = np.full((k, k), float(r))
    np.fill_diagonal(R, 1.0)
    return R


def offset_factor(k: int, r: float) -> np.ndarray:
    """Cholesky factor of the exchangeable correlation, as covariance.py's."""
    if abs(r) < 1e-12:
        return np.eye(k)
    R = exchangeable(k, r)
    try:
        return np.linalg.cholesky(R)
    except np.linalg.LinAlgError:
        return np.linalg.cholesky(R + 1e-10 * np.eye(k))


@dataclass
class Columns:
    """N synthetic columns: values (column, body, measure) with NaN past a column's last body,
    the level name of every body, the phenotype, the size and the transitional position."""
    values: np.ndarray
    levels: List[List[str]]
    measures: List[str]
    phenotype: List[str]
    scale: np.ndarray
    transitional_at: List[Optional[int]]
    blend: float = 0.0
    seed: Optional[int] = None
    meta: dict = field(default_factory=dict)

    def __len__(self) -> int:
        return self.values.shape[0]

    @property
    def n_bodies(self) -> np.ndarray:
        return np.array([len(lv) for lv in self.levels])


def _profile(ref: Dict[str, Dict[str, tuple]], measure: str, levels: Sequence[str], blend_at=None,
             blend: float = 0.0, extra_l6: bool = False) -> Tuple[np.ndarray, np.ndarray]:
    """Means and SDs along the column with the anomalies' edits, as panjabi._profile."""
    mu = np.array([ref[measure][l][0] for l in levels], float)
    sd = np.array([ref[measure][l][1] for l in levels], float)
    if extra_l6:
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


def phenotype_levels(phenotype: str) -> Tuple[List[str], Optional[int], Optional[tuple], bool]:
    if phenotype not in PHENOTYPES:
        raise ValueError(phenotype)
    levels = list(LEVELS)
    transitional_at, blend_at, extra_l6 = None, None, False
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
    return levels, transitional_at, blend_at, extra_l6


def profiles(ref: Dict[str, Dict[str, tuple]], measures: Sequence[str], phenotype: str,
             blend: float) -> Tuple[List[str], Optional[int], np.ndarray, np.ndarray]:
    """The column's level names and its (measures, bodies) means and SDs under the phenotype."""
    levels, transitional_at, blend_at, extra_l6 = phenotype_levels(phenotype)
    mus, sds = [], []
    for m in measures:
        if phenotype == "t13":
            base = [l for l in levels if l != "T13"]
            mu, sd = _profile(ref, m, base)
            i = transitional_at
            t12, l1 = ref[m]["T12"], ref[m]["L1"]
            mu = np.insert(mu, i, (1 - blend) * t12[0] + blend * l1[0])
            sd = np.insert(sd, i, (1 - blend) * t12[1] + blend * l1[1])
        else:
            mu, sd = _profile(ref, m, [l for l in levels if l != "L6"], blend_at=blend_at, blend=blend, extra_l6=extra_l6)
        mus.append(mu)
        sds.append(sd)
    return levels, transitional_at, np.array(mus), np.array(sds)


def draw_columns(ref: Dict[str, Dict[str, tuple]], phenotypes: Sequence[str], seed: int, n: int,
                 measures: Sequence[str], r_between: float = 0.0, rho: float = SYNTH["rho"],
                 noise_mm=SYNTH["noise_mm"], scale_sd: float = SYNTH["scale_sd"],
                 blend: float = SYNTH["blend"], power=None, scale: Optional[np.ndarray] = None,
                 floor: bool = True, correlation: Optional[CORR.Prior] = None) -> Columns:
    """n columns, the phenotypes cycled in turn, from one seeded stream in the archive's order.
    noise_mm is one error for every measure, as the archive's, or each measure's own; the stream
    is the same either way, and the same error for every measure gives the archive's columns.
    power is each measure's power of the size, 1 for every one, a length's, when not given; scale,
    when given, is each column's size, drawn by an earlier call, and no size is drawn from the
    stream. Every column is padded with NaN to the widest phenotype listed, drawn or not, so the
    layout depends on the phenotypes and not on how many columns are drawn. floor False leaves
    out the floor at 0.5, as for the build-up study's specimens, which carry no error and estimate
    the table itself; the stream is the same either way. correlation, a prior fitted from real
    spines (correlation.py), replaces the assumed structure, the shared offset at rho and
    r_between, with its own correlation between levels and between measures; the size is drawn as
    before, then one standard normal per measure and level, then the noise, so a draw with a
    prior is a stream of its own, and without one the stream is the archive's to the bit."""
    measures = list(measures)
    M = len(measures)
    noise = np.broadcast_to(np.asarray(noise_mm, float), (M,))
    powers = np.ones(M) if power is None else np.asarray(power, float)
    if powers.shape != (M,):
        raise ValueError("power is one power of the size per measure, %d of them; got %r" % (M, powers))
    floored = (powers > 0) & bool(floor)
    given = None if scale is None else np.asarray(scale, float)
    if given is not None and given.shape != (n,):
        raise ValueError("scale is one size per column, %d of them; got %r" % (n, given.shape))
    rng = np.random.default_rng(seed)
    factor = offset_factor(M, r_between)
    draw_index = {l: i for i, l in enumerate(DRAW_LEVELS)}
    prof = {p: profiles(ref, measures, p, blend) for p in set(phenotypes)}
    width = max(len(prof[p][0]) for p in prof)
    values = np.full((n, width, M), np.nan)
    levels, phen, scale, trans = [], [], np.empty(n), []
    for c in range(n):
        p = phenotypes[c % len(phenotypes)]
        lv, transitional_at, mu, sd = prof[p]
        s = float(np.exp(rng.normal(0.0, scale_sd))) if given is None else float(given[c])
        g = np.where(powers == 1.0, s, np.where(powers == 2.0, s * s, np.where(powers == 0.0, 1.0, s ** powers)))
        if correlation is None:
            z = rng.normal(size=M)
            if abs(r_between) >= 1e-12:
                z = factor @ z
            e = rng.normal(size=(M, len(DRAW_LEVELS)))
            nz = rng.normal(size=(M, len(DRAW_LEVELS)))
            at = np.array([draw_index[l] for l in lv])
            v = g[:, None] * (mu + sd * (rho * z[:, None] + math.sqrt(1 - rho * rho) * e[:, at])) + noise[:, None] * nz[:, at]
        else:
            field_ = CORR.draw_field(rng, correlation, lv, measures)
            nz = rng.normal(size=(M, len(lv)))
            v = g[:, None] * (mu + sd * field_) + noise[:, None] * nz
        values[c, :len(lv), :] = np.where(floored[:, None], np.maximum(v, FLOOR), v).T
        levels.append(list(lv))
        phen.append(p)
        scale[c] = s
        trans.append(transitional_at)
    meta = dict(r_between=r_between, rho=rho, noise_mm=noise_mm if np.ndim(noise_mm) == 0 else noise.tolist(),
                scale_sd=scale_sd, n=n, power=powers.tolist(), scale_given=given is not None, floor=bool(floor))
    if correlation is not None:
        meta["correlation"] = dict(n=correlation.n, shrink=correlation.shrink, note=correlation.note)
    return Columns(values=values, levels=levels, measures=measures, phenotype=phen, scale=scale,
                   transitional_at=trans, blend=blend, seed=seed, meta=meta)


def floor_hits(cols: Columns) -> dict:
    """The values the floor touched, as the archive's exact.floor_hits counts them: how many of
    the values of the measures that scale with the size sit at the floor, of how many, in how many
    columns, and at which measure and level, with the count at each. The likelihood has no floor,
    so these are the values at which the rule is not the generator's posterior; columns drawn with
    no floor have none."""
    floored = (np.asarray(cols.meta["power"], float) > 0) & bool(cols.meta.get("floor", True))
    at = (cols.values == FLOOR) & floored[None, None, :]
    where: Dict[str, int] = {}
    for c, b, m in np.argwhere(at):
        key = "%s %s" % (cols.measures[m], cols.levels[c][b])
        where[key] = where.get(key, 0) + 1
    return {"values": int(at.sum()), "of": int(np.isfinite(cols.values[:, :, floored]).sum()),
            "columns": int(at.any(axis=(1, 2)).sum()),
            "where": dict(sorted(where.items(), key=lambda kv: (-kv[1], kv[0])))}


def fields(values: np.ndarray, offsets: Sequence[int]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Every field with these offsets of every column: X (fields, measures, bodies), the true
    place of each, and the column it came from. values is (columns, bodies, measures); a column
    shorter than the array (NaN past its end) gives only the fields that fit it."""
    values = np.asarray(values, float)
    N, W, M = values.shape
    offsets = np.asarray(offsets, int)
    K = W - int(offsets[-1])
    if K <= 0:
        raise ValueError("the offsets %r do not fit a column of %d bodies" % (list(offsets), W))
    idx = np.arange(K)[:, None] + offsets[None, :]                              # (K, B)
    X = values[:, idx, :]                                                       # (N, K, B, M)
    X = np.transpose(X, (1, 0, 3, 2)).reshape(N * K, M, len(offsets))          # place-major, as the archive
    truth = np.repeat(np.arange(K), N)
    group = np.tile(np.arange(N), K)
    has_body = np.isfinite(values).any(2)                                       # (N, W)
    fits = has_body[:, idx].all(2)                                              # (N, K)
    keep = np.transpose(fits).reshape(-1)
    return X[keep], truth[keep], group[keep]
