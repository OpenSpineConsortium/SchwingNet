"""Synthetic labelled spines with known chords, for the tests: no scan, no patient.

A phantom vertebra is drawn in its own frame (x to the patient's right, y anterior, z up): the
body an elliptic cylinder of width W, depth D and height H; the canal an ellipse of width CW and
depth CD whose anterior wall is the body's posterior wall; an arch round the canal of thickness
T, closed over the middle of the body's height; two transverse processes reaching TP from tip to
tip; a spinous process of length LS behind the arch. Its chords are therefore known exactly:
EPWu = EPWl = W, EPDu = EPDl = D, VBHp = H, SCW = CW, SCD = CD, TPW = TP. The vertebrae are set
along a column tilted against the scanner, each turned about its own axis if asked, and drawn
into a volume whose affine has anisotropic spacing and a rotation of its own, so every chord has
to be found in the vertebra's frame and not along the volume's axes.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Sequence, Tuple

import numpy as np


@dataclass
class Shape:
    W: float = 44.0
    D: float = 34.0
    H: float = 27.0
    CW: float = 22.0
    CD: float = 16.0
    T: float = 5.0
    TP: float = 78.0
    LS: float = 26.0
    uncinate: float = 0.0        # uncinate processes rising this far above the superior end-plate
    osteophyte: float = 0.0      # an anterior marginal spur rising this far above it


def rotation(axis: Sequence[float], angle_deg: float) -> np.ndarray:
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    t = math.radians(angle_deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K


def inside(q: np.ndarray, s: Shape) -> Dict[str, np.ndarray]:
    """Which local points (N, 3) fall in each part of the phantom vertebra."""
    x, y, z = q[:, 0], q[:, 1], q[:, 2]
    yb = s.D / 2.0                                    # body centre: posterior wall at y = 0
    body = ((x / (s.W / 2)) ** 2 + ((y - yb) / (s.D / 2)) ** 2 <= 1.0) & (np.abs(z) <= s.H / 2)
    yc = -s.CD / 2.0
    canal = (x / (s.CW / 2)) ** 2 + ((y - yc) / (s.CD / 2)) ** 2 <= 1.0
    ring = ((x / (s.CW / 2 + s.T)) ** 2 + ((y - yc) / (s.CD / 2 + s.T)) ** 2 <= 1.0) & ~canal & (y <= 0.5)
    zarch = (z >= -s.H / 2 + 2.0) & (z <= s.H / 2 - 3.0)
    arch = ring & zarch
    tp = (np.abs(y - yc) <= 3.0) & (np.abs(x) <= s.TP / 2) & (np.abs(x) >= s.CW / 2) & (np.abs(z) <= 3.0)
    yback = yc - s.CD / 2 - s.T
    spin = (np.abs(x) <= 3.0) & (y <= yback + 0.5) & (y >= yback - s.LS) & (z >= -6.0) & (z <= 2.0)
    if s.uncinate > 0:
        # 2.5 mm wide at the posterolateral rims, from 1 mm in front of the posterior wall to 40 per cent
        # of the depth, as at C3 to C7
        body = body | ((np.abs(x) >= s.W / 2 - 3.0) & (np.abs(x) <= s.W / 2 - 0.5) & (y >= 1.0) & (y <= 0.4 * s.D)
                       & (z > s.H / 2) & (z <= s.H / 2 + s.uncinate))
    if s.osteophyte > 0:
        # 8 mm wide and 3 mm deep at the anterior rim of the superior end-plate
        body = body | ((np.abs(x) <= 4.0) & (y >= s.D - 3.5) & (y <= s.D - 0.5) & (z > s.H / 2) & (z <= s.H / 2 + s.osteophyte))
    return {"body": body, "canal": canal & zarch, "arch": arch, "tp": tp, "spinous": spin}


def spinous_reach(s: Shape) -> float:
    """The distance from the canal's posterior wall at the midline, half way up the body, to the
    farthest corner of the spinous process: the chord geometry.spinous takes."""
    back = s.T + s.LS
    return math.sqrt(3.0 ** 2 + back ** 2 + 6.0 ** 2)


def grid_about(lo: np.ndarray, hi: np.ndarray, spacing, grid_turn: Tuple[Sequence[float], float]):
    """A volume's grid for the world box [lo, hi]: its axes (the turn times the spacing), its shape
    and its affine, the origin and size chosen so the box fits inside it whatever the turn.
    Returns (axes, shape, affine)."""
    A = rotation(*grid_turn) @ np.diag(spacing)
    corners = np.array([[a, b, c] for a in (lo[0], hi[0]) for b in (lo[1], hi[1]) for c in (lo[2], hi[2])])
    ijk = corners @ np.linalg.inv(A).T
    i0, i1 = np.floor(ijk.min(0)), np.ceil(ijk.max(0))
    shape_v = tuple(int(v) for v in (i1 - i0 + 1))
    origin = A @ (i0 + 0.37)                         # off the half-millimetre lattice, so no centre sits on a surface
    affine = np.eye(4)
    affine[:3, :3], affine[:3, 3] = A, origin
    return A, shape_v, affine


def column(levels: Sequence[str], values: Dict[str, int], shape: Shape = Shape(), gap: float = 36.0,
           tilt: Tuple[Sequence[float], float] = ((1.0, 0.3, 0.0), 18.0), turns: Dict[str, float] = None,
           spacing=(0.9, 0.9, 1.4), grid_turn: Tuple[Sequence[float], float] = ((0.0, 0.0, 1.0), 9.0),
           margin: float = 50.0, subregions: bool = False,
           bends: Dict[str, Tuple[Sequence[float], float]] = None):
    """A labelled volume holding the levels top down, each under values[level]; with
    subregions, a SPINEPS-style subregion volume beside it. `turns` turns a level about the
    column's axis, `bends` tilts it about an axis across the column (a wedge or a slip leaves a
    body tilted against the line through its neighbours). Returns (labels, affine, subregion or
    None, the column's world direction)."""
    turns, bends = turns or {}, bends or {}
    R0 = rotation(*tilt)
    ez = R0 @ np.array([0.0, 0.0, 1.0])
    centres = [ez * (-gap * i) for i in range(len(levels))]
    frames = []
    for lv, c in zip(levels, centres):
        Ri = R0 @ rotation(*bends.get(lv, ((1.0, 0.0, 0.0), 0.0))) @ rotation((0, 0, 1), turns.get(lv, 0.0))
        frames.append((lv, c, Ri))
    allc = np.array(centres)
    reach = math.sqrt((shape.TP / 2) ** 2 + max(shape.D, shape.CD + shape.T + shape.LS) ** 2 + (shape.H / 2) ** 2)
    lo = allc.min(0) - margin - reach
    hi = allc.max(0) + margin + reach
    A, shape_v, affine = grid_about(lo, hi, spacing, grid_turn)
    Ainv, origin = np.linalg.inv(A), affine[:3, 3]
    lab = np.zeros(shape_v, np.int16)
    sub = np.zeros(shape_v, np.int16) if subregions else None
    for lv, c, Ri in frames:
        # the vertebra's bounding box in voxels, so only nearby voxels are tested
        r = math.sqrt((shape.TP / 2) ** 2 + max(shape.D, shape.CD + shape.T + shape.LS) ** 2 + (shape.H / 2) ** 2) + 2.0
        box = np.array([[c + d] for d in (np.array([-r, -r, -r]), np.array([r, r, r]))]).reshape(2, 3)
        bc = np.array([[a, b, cc] for a in box[:, 0] for b in box[:, 1] for cc in box[:, 2]])
        bi = (bc - origin) @ Ainv.T
        b0 = np.maximum(np.floor(bi.min(0)).astype(int), 0)
        b1 = np.minimum(np.ceil(bi.max(0)).astype(int) + 1, np.array(shape_v))
        g = np.stack(np.meshgrid(*[np.arange(b0[k], b1[k]) for k in range(3)], indexing="ij"), -1).reshape(-1, 3)
        world = g @ A.T + origin
        q = (world - c) @ Ri                          # local coordinates: Ri's columns are the local axes
        parts = inside(q, shape)
        solid = parts["body"] | parts["arch"] | parts["tp"] | parts["spinous"]
        sel = g[solid]
        lab[tuple(sel.T)] = values[lv]
        if subregions:
            code = np.zeros(len(g), np.int16)
            code[parts["arch"] | parts["tp"] | parts["spinous"]] = 41
            code[parts["tp"]] = 43
            code[parts["spinous"]] = 42
            code[parts["body"]] = 49
            top = parts["body"] & (q[:, 2] >= shape.H / 2 - 1.5)
            bot = parts["body"] & (q[:, 2] <= -shape.H / 2 + 1.5)
            code[top], code[bot] = 52, 53
            sub[tuple(g[code > 0].T)] = code[code > 0]
            canal_pts = g[parts["canal"]]
            sub[tuple(canal_pts.T)] = 61
    return lab, affine, sub, ez


def save(path: str, data: np.ndarray, affine: np.ndarray) -> None:
    import nibabel as nib
    nib.save(nib.Nifti1Image(data, affine), path)


# ---- a CT in Hounsfield units, for the mask-free mode -------------------------------------------

AIR, SOFT, CSF, DISC, TRABECULAR, CORTEX, ARCH = -1000.0, 40.0, 15.0, 90.0, 230.0, 800.0, 700.0
CORTEX_MM = 1.0


def tissue(q: np.ndarray, s: Shape, gap: float, trabecular: float = TRABECULAR, cortex: float = CORTEX,
           cortex_mm: float = CORTEX_MM) -> np.ndarray:
    """The HU of each local point (N, 3) of one vertebra's slab: the body a trabecular core in a
    cortical shell cortex_mm thick (wall and end-plates), the arch, processes and spinous solid,
    the canal CSF from end to end, the disc filling the body's outline between end-plates, soft
    tissue elsewhere."""
    x, y, z = q[:, 0], q[:, 1], q[:, 2]
    out = np.full(len(q), SOFT)
    yb = s.D / 2.0
    r_body = (x / (s.W / 2)) ** 2 + ((y - yb) / (s.D / 2)) ** 2
    r_core = (x / (s.W / 2 - cortex_mm)) ** 2 + ((y - yb) / (s.D / 2 - cortex_mm)) ** 2
    out[(r_body <= 1.0) & (np.abs(z) <= gap / 2.0)] = DISC
    yc = -s.CD / 2.0
    out[(x / (s.CW / 2)) ** 2 + ((y - yc) / (s.CD / 2)) ** 2 <= 1.0] = CSF
    parts = inside(q, s)
    out[parts["arch"] | parts["tp"] | parts["spinous"]] = ARCH
    body = parts["body"]
    out[body] = cortex
    out[body & (r_core <= 1.0) & (np.abs(z) <= s.H / 2 - cortex_mm)] = trabecular
    return out


def hu_column(n: int = 4, shape: Shape = Shape(), gap: float = 36.0,
              tilt: Tuple[Sequence[float], float] = ((1.0, 0.3, 0.0), 18.0),
              spacing=(0.9, 0.9, 1.4), grid_turn: Tuple[Sequence[float], float] = ((0.0, 0.0, 1.0), 9.0),
              blur_mm: float = 0.6, noise_hu: float = 0.0, margin: float = 10.0, sub: int = 2, seed: int = 7,
              trabecular: float = TRABECULAR, cortex: float = CORTEX, cortex_mm: float = CORTEX_MM):
    """A CT of n vertebrae down a tilted column, rendered at sub x sub x sub points per voxel,
    blurred by a Gaussian of blur_mm standard deviation (the scanner's point spread), with
    Gaussian noise of noise_hu from a fixed seed; the patient a cylinder of soft tissue round
    the column with air outside it. Returns (hu, affine)."""
    R0 = rotation(*tilt)
    ez = R0 @ np.array([0.0, 0.0, 1.0])
    reach = math.sqrt((shape.TP / 2) ** 2 + max(shape.D, shape.CD + shape.T + shape.LS) ** 2) + 2.0
    radius = reach + 0.5 * margin
    ends = [ez * (gap / 2.0), ez * (-gap * (n - 1) - gap / 2.0)]
    lo = np.minimum(*ends) - radius - margin
    hi = np.maximum(*ends) + radius + margin
    A, shape_v, affine = grid_about(lo, hi, spacing, grid_turn)
    origin = affine[:3, 3]
    offs = (np.stack(np.meshgrid(*[np.arange(sub)] * 3, indexing="ij"), -1).reshape(-1, 3) + 0.5) / sub - 0.5
    hu = np.empty(shape_v, np.float32)
    ii, jj = np.meshgrid(np.arange(shape_v[0]), np.arange(shape_v[1]), indexing="ij")
    plane = np.stack([ii.ravel(), jj.ravel()], axis=1).astype(float)
    for k in range(shape_v[2]):
        g = (np.column_stack([plane, np.full(len(plane), float(k))])[:, None, :] + offs[None]).reshape(-1, 3)
        world = g @ A.T + origin
        along = world @ ez
        radial = np.linalg.norm(world - along[:, None] * ez, axis=1)
        val = np.full(len(g), AIR)
        live = radial <= radius
        w, al = world[live], along[live]
        i = np.clip(np.round(-al / gap), 0, n - 1)
        q = (w - (-gap * i)[:, None] * ez) @ R0
        v = tissue(q, shape, gap, trabecular, cortex, cortex_mm)
        v[(al > gap / 2.0) | (al < -gap * (n - 1) - gap / 2.0)] = SOFT
        val[live] = v
        hu[:, :, k] = val.reshape(len(plane), len(offs)).mean(1).reshape(shape_v[0], shape_v[1])
    if blur_mm > 0:
        from scipy import ndimage
        hu = ndimage.gaussian_filter(hu, sigma=[blur_mm / s for s in spacing], mode="nearest")
    if noise_hu > 0:
        hu = hu + np.random.default_rng(seed).normal(0.0, noise_hu, hu.shape).astype(np.float32)
    return hu.astype(np.float32), affine
