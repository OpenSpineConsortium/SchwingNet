"""The spinal canal: its depth profile and Eisenstein's least depth, the interpedicular distance
both ways it is defined, the area, the lateral depth and the trefoil index, and Eisenstein's
lateral-film construction.

Eisenstein (1977, JBJS-B 59-B:173; the clinical reread's note eisenstein1977.md, bordercall
PR 21) measured 2,166 dry lumbar vertebrae with a caliper. His canal depth is one reading per
vertebra, taken in the midline where the front-to-back depth is least, which he found near the
top of the canal, so it is the minimum of the midline depth over the height of the ring, not
Panjabi's mid-height chord (scanimport's canal_ap, the median over the
middle half of the body). His canal width is "the greatest interpedicular distance", a maximum,
where the interpedicular distance of the radiological literature (Hinck) and of the paper-tables
vocabulary is the least distance between the pedicles' medial walls; both are written here,
interpedicular_max and interpedicular, each read in the slabs that cut the pedicles (the
central half, or the central nine tenths, of the pedicle's height at its isthmus,
pedicle.py), since above and below the pedicles the facets or the laminae bound the canal and
read narrower.

Every slab is one of anatomy.build's: a slab across the column one voxel's shadow thick, the
canal the hole the arch closes round, the walls read on the solid round it. Only full rings
count, slabs whose hole is at least half the median hole, so a slab that cuts the top or the
bottom of the ring at a slant does not set a minimum, and each extreme is read on the profile
smoothed over three slabs (smoothed).

On a lateral radiograph Eisenstein put the posterior limit of the canal, at L1 to L4, on the
line joining the apex of the superior articular process and the inverted apex of the inferior
one, opposite the cephalad half of the body, and divided by 1.23 for the film's magnification.
`lateral_film` builds that line from the mask: each superior articular process's apex is the
highest point of the bone behind the body and lateral of the spinous process, each inferior's
the lowest, the two sides averaged as a lateral view superimposes them; the canal depth is read
from the body's posterior wall at the midline to the line, at the height midway through the
cephalad half of the body, the wall taken where its line (anatomy.wall_slope) passes that height.
It is true size, as a CT is; a film reading is 1.23 times larger. Eisenstein drew it at L1 to L4,
and it is written there only.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import ndimage

from scanimport import geometry as G

from . import anatomy as A
from .anatomy import NAN, CanalSlab, Vertebra

LATERAL_SHARE = 0.75          # the lateral depth is read this far out from the midline, as a share of the half-width
SPINOUS_CLEAR_MM = 5.0        # bone this close to the midline is the spinous process or the lamina's junction
NEAR_EXTREME_MM = 1.0         # an apex is the mean of the points within this of the extreme height
EISENSTEIN_LEVELS = ("L1", "L2", "L3", "L4")


def measures(v: Vertebra, pedicle_band: Optional[Tuple[float, float]] = None) -> Tuple[Dict[str, float], Dict[str, str]]:
    rings = v.full_rings()
    out: Dict[str, float] = {}
    flags: Dict[str, str] = {}
    if not rings:
        return out, {"canal": "no full ring"}
    zb = body_span(v)
    out.update(least_depth(rings, zb))
    near, central = pedicle_slabs(rings, pedicle_band, zb)
    if pedicle_band is None:
        flags["interpedicular_band"] = "no pedicle found: read over the middle half of the body"
    out["interpedicular"] = float(smoothed(near, "width").min()) if near else NAN
    out["interpedicular_max"] = float(smoothed(central, "width").max()) if central else NAN
    areas = np.array([counted_area(v, s) for s in rings])
    out["canal_area_min"] = float(np.nanmin(ndimage.median_filter(areas, size=3, mode="nearest")))
    mid = [a for a, s in zip(areas, rings) if zb[0] + 0.25 * (zb[1] - zb[0]) <= s.z <= zb[1] - 0.25 * (zb[1] - zb[0])]
    out["canal_area"] = float(np.nanmedian(mid)) if mid else NAN
    lateral = [lateral_depth(v, s) for s in rings]
    pairs = [(d, s.ap) for d, s in zip(lateral, rings) if np.isfinite(d)]
    out["canal_ap_lateral"] = min(d for d, _ in pairs) if pairs else NAN
    out["canal_index_trefoil"] = float(np.median([d / a for d, a in pairs if a > 0])) if pairs else NAN
    if v.level in EISENSTEIN_LEVELS:
        out.update(lateral_film(v, zb))
    else:
        out["canal_ap_lateral_film"] = NAN
        flags["canal_ap_lateral_film"] = "Eisenstein's lateral construction is drawn at L1 to L4 only"
    return out, flags


def body_span(v: Vertebra) -> Tuple[float, float]:
    B = v.body_pts
    if len(B) == 0:
        return float(v.loc[:, 2].min()), float(v.loc[:, 2].max())
    return float(B[:, 2].min()), float(B[:, 2].max())


def smoothed(rings: List[CanalSlab], field: str) -> np.ndarray:
    """A profile over the rings in height order, each value the median of itself and its two
    neighbours, the ends repeated: one slab's noise does not set an extreme, and a profile that
    rises steadily keeps its end values."""
    vals = np.array([getattr(s, field) for s in rings], float)
    return ndimage.median_filter(vals, size=3, mode="nearest") if len(vals) >= 3 else vals


def least_depth(rings: List[CanalSlab], zb: Tuple[float, float]) -> Dict[str, float]:
    ap = smoothed(rings, "ap")
    k = int(np.argmin(ap))
    height = max(zb[1] - zb[0], 1e-6)
    return {"canal_ap_min": float(ap[k]), "canal_ap_min_share": (rings[k].z - zb[0]) / height}


def pedicle_slabs(rings: List[CanalSlab], band: Optional[Tuple[float, float]], zb: Tuple[float, float]):
    """The full rings that cut the pedicles: within nine tenths of the pedicle's half-height of
    its centre for the least width, within half of it for the greatest. With no pedicle found,
    the middle half of the body for both."""
    if band is None:
        q = 0.25 * (zb[1] - zb[0])
        sel = [s for s in rings if zb[0] + q <= s.z <= zb[1] - q]
        return sel, sel
    zc, h = band
    near = [s for s in rings if abs(s.z - zc) <= 0.45 * h]
    central = [s for s in rings if abs(s.z - zc) <= 0.25 * h]
    return near, central


def lateral_depth(v: Vertebra, s: CanalSlab) -> float:
    """The canal's depth front to back at LATERAL_SHARE of its half-width out from the midline,
    the mean of the two sides, read on the bone's surfaces in front of and behind the hole in a
    band across, as scanimport.geometry.canal_walls reads the midline depth."""
    hole, band = s.hole, 0.75 * v.pixel
    xm, half = s.midline, 0.5 * s.width
    slab = v.loc[np.abs(v.loc[:, 2] - s.z) <= 0.5 * v.fz]
    depths = []
    for side in (1.0, -1.0):
        x = xm + side * LATERAL_SHARE * half
        col = hole[np.abs(hole[:, 0] - x) <= 0.5 * v.pixel]
        line = slab[np.abs(slab[:, 0] - x) <= band]
        if not len(col) or not len(line):
            continue
        ym = 0.5 * (col[:, 1].min() + col[:, 1].max())
        ant, post = line[line[:, 1] > ym, 1], line[line[:, 1] < ym, 1]
        if len(ant) and len(post):
            ant = ant[ant <= col[:, 1].max() + 2.0 * v.pixel]
            post = post[post >= col[:, 1].min() - 2.0 * v.pixel]
        if len(ant) and len(post):
            depths.append(G.surface(ant, False, v.fy) - G.surface(post, True, v.fy))
    return float(np.mean(depths)) if len(depths) == 2 else NAN


def counted_area(v: Vertebra, s: CanalSlab) -> float:
    """The canal's area in one slab from the scan's own voxels: those outside the bone whose
    centres fall in the slab and in the hole, grown by one pixel so the raster's edge, which
    leaves out a pixel wherever any bone point falls in it, does not shrink it; their count
    times a voxel's volume over the slab's thickness."""
    p = v.pixel
    lo = s.hole.min(0)
    ij = np.rint((s.hole - lo) / p).astype(int) + 2
    mask = np.zeros(tuple(ij.max(0) + 3), bool)
    mask[ij[:, 0], ij[:, 1]] = True
    mask = ndimage.binary_dilation(mask, structure=np.ones((3, 3), bool))
    corners = np.array([[x, y, s.z + dz] for x in (lo[0] - 2 * p, s.hole[:, 0].max() + 2 * p)
                        for y in (lo[1] - 2 * p, s.hole[:, 1].max() + 2 * p) for dz in (-v.fz, v.fz)])
    inv = np.linalg.inv(np.asarray(v.grid.affine, float))
    cijk = v.points_world(corners) @ inv[:3, :3].T + inv[:3, 3]
    a, b = np.floor(cijk.min(0)).astype(int), np.ceil(cijk.max(0)).astype(int)
    ijk = np.stack(np.meshgrid(*[np.arange(a[k], b[k] + 1) for k in range(3)], indexing="ij"), -1).reshape(-1, 3)
    q = v.frame.local(v.grid.world(ijk.astype(float)))
    keep = np.abs(q[:, 2] - s.z) <= 0.5 * v.fz
    q, ijk = q[keep], ijk[keep]
    pix = np.rint((q[:, :2] - lo) / p).astype(int) + 2
    ok = ((pix >= 0) & (pix < np.array(mask.shape))).all(1)
    inside = np.zeros(len(q), bool)
    inside[ok] = mask[pix[ok, 0], pix[ok, 1]]
    n = int((inside & ~v.is_bone(ijk)).sum())
    return float(n) * v.voxel_volume / v.fz


def apex(pts: np.ndarray, top: bool) -> Optional[np.ndarray]:
    if len(pts) < G.MIN_CHORD_POINTS:
        return None
    z = pts[:, 2]
    edge = z.max() if top else z.min()
    near = pts[np.abs(z - edge) <= NEAR_EXTREME_MM]
    return np.array([near[:, 1].mean(), edge])


def lateral_film(v: Vertebra, zb: Tuple[float, float]) -> Dict[str, float]:
    """Eisenstein's lateral construction, read on the mask; see the module's docstring."""
    behind = v.loc[A.square_to_wall(v, v.loc)[:, 1] < v.wall_y0]
    out = {"canal_ap_lateral_film": NAN}
    sup, inf = [], []
    for side in (1.0, -1.0):
        s = behind[side * (behind[:, 0] - v.midline) >= SPINOUS_CLEAR_MM]
        a, b = apex(s, True), apex(s, False)
        if a is None or b is None:
            return out
        sup.append(a)
        inf.append(b)
    (ys, zs), (yi, zi) = np.mean(sup, axis=0), np.mean(inf, axis=0)
    if zs - zi <= 0:
        return out
    ze = zb[0] + 0.75 * (zb[1] - zb[0])
    y_line = ys + (yi - ys) * (zs - ze) / (zs - zi)
    out["canal_ap_lateral_film"] = float(v.wall_y0 + v.wall_slope * (ze - v.wall_z0) - y_line)
    out["sap_apex_height"], out["iap_apex_height"] = float(zs - ze), float(ze - zi)
    return out
