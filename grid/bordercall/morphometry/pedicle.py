"""The pedicles: width, height and area at the isthmus, the axis's two angles and the chord along
it, each side.

The pedicle is the bridge of bone from the body to the articular pillar beside the canal, and
its width and height are the least across it, where Zindrick (1987) and Panjabi read them. A
whole-vertebra label gives no pedicle subregion, so the pedicle is found as an AP radiograph
sees it, as the "pedicle eye": coronal slabs, square to the frame's y, are taken from the body's
posterior wall back to the canal's posterior wall; in each, the island on one side of the
midline nearest to it, and lying within the body's height, is the pedicle there. An island
under half the smaller of its neighbours' is a stray piece (at study 0004's L4 a 56-voxel piece
of the body below the pedicle, nearer the midline, was taken for the isthmus) and its slab is
left out.
The slabs whose island holds no more than ISTHMUS_SHARE of the fewest voxels are the isthmus,
and the width, height and area are the medians over them: the island's extent across and up,
the width times the cosine of the transverse angle, since a coronal slab cuts a converging
pedicle on the slant, and the area its voxels over the slab's thickness, times the cosine of
the axis's angle to the frame's y.

An earlier version read them in cuts square to the axis instead, and on real masks that went
wrong in the thoracic spine: behind the short thoracic pedicle the superior articular process
rises and the inferior notch deepens, so the islands' centres climb 7 mm in 6 (study 0004's
T7), the axis pitched 43 degrees and the cut square to it crossed the lamina, reading widths of
20 to 30 mm where 5 to 8 is real. The coronal slab needs no axis.

The axis runs through the run of slabs within RUN_SHARE of the fewest voxels, pointing back:
across, it follows the island's medial wall, the canal's side (walls), since toward the back the island
widens laterally into the transverse process and its middle drifts out (at study 0004's L4 the
middle's drift read the pedicles converging at 37 degrees); up, it follows the middle of the
island's height. The transverse angle is its angle to the midsagittal plane in the transverse
plane, positive where the pedicles converge
toward the front; the sagittal angle its angle to the transverse plane in the sagittal plane,
positive where the posterior end is higher. Where the run spans under SAGITTAL_SPAN_MM front to
back the sagittal angle is not read: the borders of so short a pedicle curve with the notch and
the process, and the centres' climb is theirs, not the pedicle's (study 0004's thoracic
pedicles span 4.5 to 5.3 mm and climbed 40 to 50 degrees; the phantom's span 5.8); the chord and the area then
take the axis level. The chord is the length of bone the axis line through the isthmus crosses,
from where it enters the posterior elements to where it leaves the body's anterior cortex, read
by marching along the line voxel by voxel (Zindrick's screw path).
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import ndimage

from scanimport import geometry as G

from . import body as BODY
from .anatomy import NAN, Vertebra

RUN_SHARE = 1.6
ISTHMUS_SHARE = 1.10
STRAY_SHARE = 0.5
SAGITTAL_SPAN_MM = 5.5
MARCH_MM = 0.25
SIDES = ((1, "right"), (-1, "left"))


def raster2(uv: np.ndarray, pu: float, pv: float) -> Tuple[np.ndarray, np.ndarray]:
    """Points in a plane on a padded grid of pixels pu by pv, closed over one-pixel gaps, and
    each point's pixel."""
    lo = uv.min(0)
    ij = np.floor((uv - lo) / np.array([pu, pv])).astype(int) + 1
    grid = np.zeros(tuple(ij.max(0) + 2), bool)
    grid[ij[:, 0], ij[:, 1]] = True
    grid = ndimage.binary_closing(grid, structure=np.ones((3, 3), bool), border_value=0) | grid
    return grid, ij


def islands(uv: np.ndarray, pu: float, pv: float) -> np.ndarray:
    """Each point's island (connected part of the closed raster), as a label."""
    grid, ij = raster2(uv, pu, pv)
    lab, _ = ndimage.label(grid, structure=np.ones((3, 3), bool))
    return lab[ij[:, 0], ij[:, 1]]


def coronal_sweep(v: Vertebra, side: int, zb: Tuple[float, float]) -> List[dict]:
    step = max(v.fy, 0.5)
    rows = []
    P = v.loc
    for y0 in np.arange(v.wall + 1.0, v.wall_post + 2.0, -step):
        slab = P[np.abs(P[:, 1] - y0) <= 0.5 * step]
        if len(slab) < G.MIN_CHORD_POINTS:
            continue
        lab = islands(slab[:, [0, 2]], v.fx, v.fz)
        best = None
        for k in np.unique(lab):
            pts = slab[lab == k]
            off = side * (pts[:, 0] - v.midline)
            zc = float(pts[:, 2].mean())
            if len(pts) < G.MIN_CHORD_POINTS or off.min() <= 0 or not (zb[0] <= zc <= zb[1]):
                continue
            if best is None or off.min() < best[0]:
                best = (off.min(), pts)
        if best is not None:
            rows.append(island_row(v, float(y0), best[1], step))
    return without_strays(rows)


def island_row(v: Vertebra, y0: float, pts: np.ndarray, step: float) -> dict:
    x0, x1 = G.surface(pts[:, 0], False, v.fx), G.surface(pts[:, 0], True, v.fx)
    z0, z1 = G.surface(pts[:, 2], False, v.fz), G.surface(pts[:, 2], True, v.fz)
    return {"y": y0, "n": len(pts), "c": np.array([0.5 * (x0 + x1), y0, 0.5 * (z0 + z1)]), "walls": walls(pts, v.fz),
            "w": x1 - x0, "h": z1 - z0, "area": len(pts) * v.voxel_volume / step}


def walls(pts: np.ndarray, layer: float) -> Tuple[float, float]:
    """The island's two side walls, each the median over its rows up the slab of the row's
    outermost voxel: one row's extreme moves by a voxel as the grid's turn steps it, the median
    over a pedicle's fifteen rows hardly at all."""
    rows = np.floor((pts[:, 2] - pts[:, 2].min()) / max(layer, 1e-6)).astype(int)
    order = np.argsort(rows, kind="stable")
    cut = np.flatnonzero(np.diff(rows[order])) + 1
    groups = np.split(pts[order, 0], cut)
    return float(np.median([g.min() for g in groups])), float(np.median([g.max() for g in groups]))


def without_strays(rows: List[dict]) -> List[dict]:
    """The rows less those whose island holds under STRAY_SHARE of the smaller of its neighbours'."""
    keep = []
    for i, r in enumerate(rows):
        near = [rows[j]["n"] for j in (i - 1, i + 1) if 0 <= j < len(rows)]
        if not near or r["n"] >= STRAY_SHARE * min(near):
            keep.append(r)
    return keep


def axis_from(rows: List[dict], side: int) -> Tuple[int, np.ndarray, str, str]:
    """The isthmus's row, the axis pointing back, a note where the run is too short for an axis
    or for its sagittal angle, and which of its angles were read: "both", "transverse", or
    "neither" where the axis is taken front to back and stands for nothing measured."""
    k = int(np.argmin([r["n"] for r in rows]))
    lim = RUN_SHARE * rows[k]["n"]
    lo = k
    while lo > 0 and rows[lo - 1]["n"] <= lim:
        lo -= 1
    hi = k
    while hi + 1 < len(rows) and rows[hi + 1]["n"] <= lim:
        hi += 1
    cs = np.array([r["c"] for r in rows[lo:hi + 1]])
    if len(cs) < 3 or np.ptp(cs[:, 1]) < 3.0:
        return k, np.array([0.0, -1.0, 0.0]), "the free pedicle is too short to give an axis: taken front to back", "neither"
    y = cs[:, 1]
    medial = np.array([r["walls"][0] if side > 0 else r["walls"][1] for r in rows[lo:hi + 1]])
    across = np.polyfit(y, medial, 1)[0]
    if np.ptp(y) < SAGITTAL_SPAN_MM:
        d = np.array([across, 1.0, 0.0])
        note, reads = "the free pedicle spans %.1f mm front to back: its sagittal angle is not read" % np.ptp(y), "transverse"
    else:
        d = np.array([across, 1.0, np.polyfit(y, cs[:, 2], 1)[0]])
        note, reads = "", "both"
    return k, -d / np.linalg.norm(d), note, reads


def isthmus(rows: List[dict], d: np.ndarray, side: int) -> Dict[str, float]:
    least = min(r["n"] for r in rows)
    near = [r for r in rows if r["n"] <= ISTHMUS_SHARE * least]
    level = np.array([d[0], d[1], 0.0]) / np.linalg.norm(d[:2])
    return {"pedicle_w": float(np.median([r["w"] for r in near])) * abs(level[1]),
            "pedicle_h": float(np.median([r["h"] for r in near])),
            "pedicle_area": float(np.median([r["area"] for r in near])) * abs(d[1]),
            "pedicle_angle_transverse": math.degrees(math.atan2(side * d[0], -d[1])),
            "pedicle_angle_sagittal": math.degrees(math.atan2(d[2], -d[1]))}


def chord(v: Vertebra, c0: np.ndarray, d: np.ndarray) -> float:
    """The run of the vertebra's voxels along the line through c0, voxel by voxel."""
    ts = np.arange(-150.0, 150.0 + 1e-9, MARCH_MM)
    world = v.points_world(c0[None, :] + ts[:, None] * d[None, :])
    inv = np.linalg.inv(np.asarray(v.grid.affine, float))
    inside = v.is_bone(np.rint(world @ inv[:3, :3].T + inv[:3, 3]).astype(int))
    k = int(np.argmin(np.abs(ts)))
    if not inside[k]:
        near = np.flatnonzero(inside & (np.abs(ts) <= 2.0))
        if not len(near):
            return NAN
        k = int(near[np.argmin(np.abs(ts[near]))])
    a = k
    while a > 0 and inside[a - 1]:
        a -= 1
    b = k
    while b + 1 < len(ts) and inside[b + 1]:
        b += 1
    if a == 0 or b == len(ts) - 1:
        return NAN
    return float(ts[b] - ts[a] + MARCH_MM)


def wall_slope(v: Vertebra) -> float:
    """dy/dz of the body's posterior wall (body.posterior_wall_slope), so that the sagittal angle
    is taken against the plane square to the wall, as the end-plates' inclinations are, and not
    against the column's line, which leans against a vertebra where its neighbours slip."""
    B = v.body_pts
    if len(B) < G.MIN_CHORD_POINTS:
        return 0.0
    return BODY.posterior_wall_slope(v, B, 0.5 * (B[:, 0].min() + B[:, 0].max()))


def one_side(v: Vertebra, side: int, zb: Tuple[float, float]) -> Tuple[Dict[str, float], str, Optional[dict]]:
    rows = coronal_sweep(v, side, zb)
    if len(rows) < 3:
        return {}, "no pedicle island beside the canal", None
    k, d, note, reads = axis_from(rows, side)
    c0 = rows[k]["c"]
    out = isthmus(rows, d, side)
    out["pedicle_angle_sagittal"] -= math.degrees(math.atan(wall_slope(v)))
    out["pedicle_chord"] = chord(v, c0, d)
    if reads != "both":
        out["pedicle_angle_sagittal"] = NAN
    if reads == "neither":
        out["pedicle_angle_transverse"] = out["pedicle_chord"] = NAN
    info = {"centre": c0, "axis": d, "eh": np.array([0.0, 0.0, 1.0]), "height": rows[k]["h"]}
    return out, note, info


def measures(v: Vertebra, zb: Tuple[float, float]) -> Tuple[Dict[str, float], Dict[str, str], Dict[str, dict]]:
    out: Dict[str, float] = {}
    flags: Dict[str, str] = {}
    info: Dict[str, dict] = {}
    for side, name in SIDES:
        got, note, inf = one_side(v, side, zb)
        if note:
            flags["pedicle_" + name] = note
        if inf is not None:
            info[name] = inf
        for k, val in got.items():
            out["%s_%s" % (k, name)] = val
    for k in ("pedicle_w", "pedicle_h", "pedicle_area", "pedicle_angle_transverse", "pedicle_angle_sagittal",
              "pedicle_chord"):
        vals = [out.get("%s_%s" % (k, n), NAN) for _, n in SIDES]
        fin = [x for x in vals if np.isfinite(x)]
        out[k] = float(np.mean(fin)) if len(fin) == 2 else NAN
    if v.touching.any():
        for k in list(out):
            if k.startswith("pedicle_chord"):
                out[k] = NAN
    return out, flags, info


def band(info: Dict[str, dict]) -> Optional[Tuple[float, float]]:
    """The pedicles' height along the frame's z and their centre's, for the canal's slabs."""
    if not info:
        return None
    zc = float(np.mean([i["centre"][2] for i in info.values()]))
    h = float(np.mean([i["height"] * abs(i["eh"][2]) for i in info.values()]))
    return zc, h
