"""Paired synthetic CTs and masks whose vertebrae are sized from schwingcheck's generator.

scanimport/tests/phantom.py draws every vertebra of a column with one shape. A network that is to
learn measuring needs the measures to vary, from level to level and from patient to patient, as
the table says they do, so this phantom sizes each level from one column of schwingcheck's
generator (columns.draw_columns, the table's means and spreads, the patient's size and offsets,
the phenotypes): the body a frustum of an elliptic cylinder whose top and bottom ellipses are the
drawn end-plate widths and depths and whose height is the drawn posterior height, the canal an
ellipse of the drawn width and depth, the arch, the transverse processes and the spinous process
as scanimport's phantom draws them (the processes' lengths from the drawn transverse width and,
scaled by SPINOUS_SHARE, spinous length). The drawn values are the anatomy, drawn with no
measurement error; what the oracle reads off the mask is a measurement of it.

The mask and the CT are drawn on one grid in one pass, so they are paired voxel for voxel: the
mask at voxel centres, the CT in Hounsfield units averaged over sub x sub x sub points per voxel,
blurred by the scanner's point spread and given noise from a fixed seed, with scanimport's tissue
values (a cortical shell round a trabecular core, the disc between end-plates, CSF in the canal,
soft tissue in a cylinder of air). The labels are VerSe's (scanimport.schemes.VERSE), which name
an L6 and a T13.

Nothing here is a patient, and the shapes are idealised: no end-plate concavity, no osteophyte, no
facet joints, straight processes; a network trained only on them has learnt the phantom.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from scanimport import schemes
from scanimport.tests.phantom import ARCH, AIR, CORTEX, CORTEX_MM, CSF, DISC, SOFT, TRABECULAR, rotation, grid_about
from schwingcheck import columns as C
from schwingcheck import measures as SM

SHAPE_MEASURES = ["endplate", "endplate_depth", "endplate_lower", "endplate_lower_depth", "h_post", "canal_w",
                  "canal_ap", "transverse_width", "spinous_length"]
SPINOUS_SHARE = 0.45          # the phantom's process behind the arch, as a share of Panjabi's spinous length (a choice)
DISC_SHARE = 0.35             # a disc's height as a share of the mean of its two bodies' heights (a choice)
ARCH_MM = 5.0                 # the arch's thickness round the canal, scanimport's phantom's T
VERSE_ID = {name: v for v, name in schemes.VERSE.items()}


@dataclass(frozen=True)
class Level:
    """One vertebra's shape in millimetres, in its own frame: x to the right, y anterior with the
    body's posterior wall at y = 0, z up."""
    name: str
    W_top: float
    W_bot: float
    D_top: float
    D_bot: float
    H: float
    CW: float
    CD: float
    TP: float = 78.0
    LS: float = 26.0
    T: float = ARCH_MM

    @classmethod
    def from_values(cls, name: str, v: Dict[str, float]) -> "Level":
        return cls(name, W_top=v["endplate"], W_bot=v["endplate_lower"], D_top=v["endplate_depth"],
                   D_bot=v["endplate_lower_depth"], H=v["h_post"], CW=v["canal_w"], CD=v["canal_ap"],
                   TP=max(v.get("transverse_width", 78.0), v["canal_w"] + 8.0),
                   LS=max(SPINOUS_SHARE * v.get("spinous_length", 58.0), 8.0))

    def truth(self) -> Dict[str, float]:
        """The chords as drawn: what a perfect measurement of this shape would read."""
        return {"endplate": self.W_top, "endplate_depth": self.D_top, "endplate_lower": self.W_bot,
                "endplate_lower_depth": self.D_bot, "h_post": self.H, "canal_w": self.CW, "canal_ap": self.CD}

    @property
    def reach(self) -> float:
        return math.sqrt((self.TP / 2) ** 2 + max(self.D_top, self.D_bot, self.CD + self.T + self.LS) ** 2
                         + (self.H / 2) ** 2)


def draw_levels(phenotype: str = "typical", seed: int = 0, start: str = "L1", count: int = 4) -> List[Level]:
    """`count` consecutive levels from `start` down one column of the generator's, with no
    measurement error: the anatomy of one synthetic patient."""
    ms = SM.select(SHAPE_MEASURES)
    ref = SM.reference(ms)
    cols = C.draw_columns(ref, [phenotype], seed, 1, SHAPE_MEASURES, noise_mm=0.0, power=SM.powers(ms))
    names = cols.levels[0]
    if start not in names:
        raise ValueError("a %s column has no %s; its levels are %s" % (phenotype, start, ", ".join(names)))
    i = names.index(start)
    if i + count > len(names):
        raise ValueError("%d levels from %s run past the %s column's end at %s" % (count, start, phenotype, names[-1]))
    return [Level.from_values(names[j], dict(zip(SHAPE_MEASURES, cols.values[0, j]))) for j in range(i, i + count)]


@dataclass
class Phantom:
    """A paired CT and mask: hu and labels on one grid with its affine, each level's centre and
    rotation (its local axes as columns), and the levels' shapes and label values."""
    hu: Optional[np.ndarray]
    labels: np.ndarray
    affine: np.ndarray
    centres: np.ndarray
    rotations: np.ndarray
    levels: List[Level]
    ids: List[int]
    meta: dict = field(default_factory=dict)

    @property
    def names(self) -> Dict[int, str]:
        return {i: lv.name for i, lv in zip(self.ids, self.levels)}


def semi_axes(z: np.ndarray, lv: Level) -> Tuple[np.ndarray, np.ndarray]:
    """The body's half-width and half-depth at heights z, from the bottom end-plate's to the top's."""
    f = np.clip((z + lv.H / 2) / lv.H, 0.0, 1.0)
    return 0.5 * (lv.W_bot + f * (lv.W_top - lv.W_bot)), 0.5 * (lv.D_bot + f * (lv.D_top - lv.D_bot))


def body_inside(q: np.ndarray, lv: Level, shrink: float = 0.0) -> np.ndarray:
    """Inside the body, or, with shrink, inside it by that many millimetres from every surface:
    the elliptic outline at each height, its posterior wall at y = 0, between the end-plates."""
    x, y, z = q[:, 0], q[:, 1], q[:, 2]
    a, b = semi_axes(z, lv)
    return ((x / (a - shrink)) ** 2 + ((y - b) / (b - shrink)) ** 2 <= 1.0) & (np.abs(z) <= lv.H / 2 - shrink)


def plate_ellipse(q: np.ndarray, lv: Level) -> np.ndarray:
    """Inside the outline of the end-plate nearer each point (the top one above the middle), the
    disc's outline beyond it."""
    x, y, z = q[:, 0], q[:, 1], q[:, 2]
    a, b = semi_axes(np.where(z > 0, lv.H / 2, -lv.H / 2), lv)
    return (x / a) ** 2 + ((y - b) / b) ** 2 <= 1.0


def parts(q: np.ndarray, lv: Level) -> Dict[str, np.ndarray]:
    """Which local points fall in each part of the vertebra (scanimport's phantom's parts, with a
    frustum for a body)."""
    x, y, z = q[:, 0], q[:, 1], q[:, 2]
    body = body_inside(q, lv)
    yc = -lv.CD / 2.0
    canal = (x / (lv.CW / 2)) ** 2 + ((y - yc) / (lv.CD / 2)) ** 2 <= 1.0
    ring = ((x / (lv.CW / 2 + lv.T)) ** 2 + ((y - yc) / (lv.CD / 2 + lv.T)) ** 2 <= 1.0) & ~canal & (y <= 0.5)
    arch = ring & (z >= -lv.H / 2 + 2.0) & (z <= lv.H / 2 - 3.0)
    tp = (np.abs(y - yc) <= 3.0) & (np.abs(x) <= lv.TP / 2) & (np.abs(x) >= lv.CW / 2) & (np.abs(z) <= 3.0)
    yback = yc - lv.CD / 2 - lv.T
    spin = (np.abs(x) <= 3.0) & (y <= yback + 0.5) & (y >= yback - lv.LS) & (z >= -6.0) & (z <= 2.0)
    return {"body": body, "canal": canal, "arch": arch, "tp": tp, "spinous": spin}


def tissue(q: np.ndarray, lv: Level, half_gaps: Tuple[float, float]) -> np.ndarray:
    """Hounsfield units at local points of one vertebra's segment: soft tissue, the disc inside the
    nearer end-plate's outline out to the segment's edge, CSF in the canal, the processes, the body
    a cortical shell round a trabecular core."""
    out = np.full(len(q), SOFT)
    z = q[:, 2]
    up, down = half_gaps
    disc = plate_ellipse(q, lv) & (z <= lv.H / 2 + up) & (z >= -lv.H / 2 - down) & (np.abs(z) > lv.H / 2)
    out[disc] = DISC
    p = parts(q, lv)
    out[p["canal"]] = CSF
    out[p["arch"] | p["tp"] | p["spinous"]] = ARCH
    out[p["body"]] = CORTEX
    out[body_inside(q, lv, CORTEX_MM)] = TRABECULAR
    return out


def solid(q: np.ndarray, lv: Level) -> np.ndarray:
    p = parts(q, lv)
    return p["body"] | p["arch"] | p["tp"] | p["spinous"]


def layout(levels: Sequence[Level], tilt, bends: Optional[Sequence[Tuple[Sequence[float], float]]]
           ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """The column: its axis, each level's centre (top down, each body a disc below the one above),
    its rotation, the positions along the axis of the planes half way across each disc, and each
    segment's half-gaps above and below."""
    R0 = rotation(*tilt)
    ez = R0 @ np.array([0.0, 0.0, 1.0])
    s = [0.0]
    gaps = []
    for a, b in zip(levels, levels[1:]):
        disc = DISC_SHARE * 0.5 * (a.H + b.H)
        gaps.append(disc)
        s.append(s[-1] - (a.H / 2 + disc + b.H / 2))
    s = np.array(s)
    cuts = np.array([s[i] - (levels[i].H / 2 + gaps[i] / 2) for i in range(len(gaps))])
    end = DISC_SHARE * levels[0].H / 2
    half = np.array([[gaps[i - 1] / 2 if i > 0 else end, gaps[i] / 2 if i < len(gaps) else end]
                     for i in range(len(levels))])
    bends = bends or [((1.0, 0.0, 0.0), 0.0)] * len(levels)
    rots = np.array([R0 @ rotation(*bends[i]) for i in range(len(levels))])
    return ez, s[:, None] * ez[None, :], rots, cuts, half


def render(levels: Sequence[Level], spacing=(1.0, 1.0, 1.0), tilt=((1.0, 0.3, 0.0), 12.0),
           bends: Optional[Sequence[Tuple[Sequence[float], float]]] = None,
           grid_turn=((0.0, 0.0, 1.0), 9.0), margin: float = 10.0, sub: int = 2, blur_mm: float = 0.6,
           noise_hu: float = 0.0, seed: int = 7, with_ct: bool = True) -> Phantom:
    """The column's mask and, unless with_ct is False, its CT, on one grid (the module's
    docstring); bends tilt each level about an axis across the column, (axis, degrees)."""
    levels = list(levels)
    ez, centres, rots, cuts, half = layout(levels, tilt, bends)
    reach = max(lv.reach for lv in levels) + 2.0
    radius = reach + 0.5 * margin
    top = centres[0] + ez * (levels[0].H / 2 + half[0, 0])
    bottom = centres[-1] - ez * (levels[-1].H / 2 + half[-1, 1])
    lo = np.minimum(top, bottom) - radius - margin
    hi = np.maximum(top, bottom) + radius + margin
    A, shape_v, affine = grid_about(lo, hi, spacing, grid_turn)
    origin = affine[:3, 3]
    ids = [VERSE_ID[lv.name] for lv in levels]
    labels = np.zeros(shape_v, np.int16)
    hu = np.empty(shape_v, np.float32) if with_ct else None
    offs = (np.stack(np.meshgrid(*[np.arange(sub)] * 3, indexing="ij"), -1).reshape(-1, 3) + 0.5) / sub - 0.5
    ii, jj = np.meshgrid(np.arange(shape_v[0]), np.arange(shape_v[1]), indexing="ij")
    plane = np.stack([ii.ravel(), jj.ravel()], axis=1).astype(float)
    s_top, s_bottom = float(top @ ez), float(bottom @ ez)
    for k in range(shape_v[2]):
        centre_pts = np.column_stack([plane, np.full(len(plane), float(k))])
        labels[:, :, k] = slice_labels(centre_pts @ A.T + origin, ez, centres, rots, cuts, levels, ids,
                                       (s_bottom, s_top)).reshape(shape_v[0], shape_v[1])
        if hu is None:
            continue
        g = (centre_pts[:, None, :] + offs[None]).reshape(-1, 3)
        val = slice_hu(g @ A.T + origin, ez, centres, rots, cuts, half, levels, radius, (s_bottom, s_top))
        hu[:, :, k] = val.reshape(len(plane), len(offs)).mean(1).reshape(shape_v[0], shape_v[1])
    if hu is not None and blur_mm > 0:
        from scipy import ndimage
        hu = ndimage.gaussian_filter(hu, sigma=[blur_mm / s for s in spacing], mode="nearest")
    if hu is not None and noise_hu > 0:
        hu = hu + np.random.default_rng(seed).normal(0.0, noise_hu, hu.shape).astype(np.float32)
    return Phantom(hu=None if hu is None else hu.astype(np.float32), labels=labels, affine=affine, centres=centres,
                   rotations=rots, levels=levels, ids=ids,
                   meta=dict(spacing=list(map(float, spacing)), tilt=[list(map(float, tilt[0])), float(tilt[1])],
                             sub=sub, blur_mm=blur_mm, noise_hu=noise_hu, seed=seed))


def segment_of(world: np.ndarray, ez: np.ndarray, cuts: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    along = world @ ez
    return (along[:, None] < cuts[None, :]).sum(1), along


def slice_labels(world, ez, centres, rots, cuts, levels, ids, span) -> np.ndarray:
    seg, along = segment_of(world, ez, cuts)
    out = np.zeros(len(world), np.int16)
    live = (along >= span[0]) & (along <= span[1])
    for i, lv in enumerate(levels):
        here = live & (seg == i)
        if not here.any():
            continue
        q = (world[here] - centres[i]) @ rots[i]
        out[np.flatnonzero(here)[solid(q, lv)]] = ids[i]
    return out


def slice_hu(world, ez, centres, rots, cuts, half, levels, radius, span) -> np.ndarray:
    seg, along = segment_of(world, ez, cuts)
    radial = np.linalg.norm(world - along[:, None] * ez[None, :] - (centres[0] - (centres[0] @ ez) * ez)[None, :], axis=1)
    out = np.full(len(world), AIR)
    inside = radial <= radius
    out[inside] = SOFT
    live = inside & (along >= span[0]) & (along <= span[1])
    for i, lv in enumerate(levels):
        here = live & (seg == i)
        if not here.any():
            continue
        q = (world[here] - centres[i]) @ rots[i]
        out[here] = tissue(q, lv, tuple(half[i]))
    return out
