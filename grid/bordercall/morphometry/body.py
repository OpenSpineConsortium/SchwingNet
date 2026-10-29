"""The vertebral body: heights front, middle and back, the waist, the end-plates' areas, slopes
and concavity, and the volumes.

Every measure is read on the body found in front of the canal (anatomy.build), in the vertebra's
frame. A height is read from corner to corner, as a reader's caliper on a midsagittal slice is
set just inside the cortex: each end-plate's surface is read in a band 3 mm deep and 6 mm wide on
the midline, centred 2.5 mm inside that plate's own anterior corner, 2.5 mm inside its posterior
corner, or half-way between (plate_rims), and the height is the distance between the two plates'
points, which is the gap along z where the body stands square to the frame and the corner-to-corner
length where it leans. In the band every point is carried along its end-plate's slope to the
band's centre and each plate's surface is read on all of them together (band_surface); one cell
of the grid that
scanimport.geometry.column_height reads holds too few points next to a plate to place it to
better than a few tenths of a millimetre, which a height survives, its two errors cancelling,
and a disc does not, its two errors adding. Panjabi's posterior height (h_post) is scanimport's and
is passed through unchanged; the inset posterior height here is the one the ratios use, so that
the anterior and the posterior heights are read alike.

The waist is the slab across the body half-way between its end-plates: its width is the
transverse extent there across the body's mid-depth (Eisenstein's "greatest mid-waist
distance", which a body's oval reaches near its mid-depth), its depth the midline extent from
the anterior to the posterior surface (his body A.P.).

An end-plate's area is the area of the body's section parallel to the end-plate, from voxel
counts: N voxels in a slab of thickness T hold N times a voxel's volume over T of area, whatever
the slab's slant to the scan, which a traced outline does not. The slab starts half a
millimetre deeper than the plate's measured concavity, so it cuts the whole outline and not a
ring round the depression, and is 2 mm thick or one voxel's shadow on the plate's normal if that
is more. Its cost is that it lies a few millimetres inside the rim, where a waisted body is
already narrower.

An end-plate's inclination is its slope, in the sagittal plane, from the anterior height's band
to the posterior height's, rim to rim as a reader draws it, measured against the transverse
plane, the plane square to the body's posterior wall (Panjabi's frontal plane); positive where
the plate descends anteriorly. The wedge is the angle between the two plates in
the sagittal plane, positive where the body is taller in front. The concavity is how far the
centre of the plate (the median of the cells within a quarter of its half-width and
half-depth) lies below the least-squares plane through its rim (the cells between 85 and 95 per
cent of them). A plane resting on the rim from outside would sit at the top of the voxels'
scatter and the centre's median in its middle, so a flat plate would read concave by half that
scatter; two planes of the same kind cancel it.
"""
from __future__ import annotations

import math
from typing import Dict, Tuple

import numpy as np

from scanimport import geometry as G

from .anatomy import NAN, Vertebra

INSET_MM = 2.5
BAND_HALF_MM = 1.5
ACROSS_HALF_MM = 3.0
RIM = (0.85, 0.95)
CENTRE = 0.25
AREA_SLAB_MM = 2.0
AREA_BEYOND_MM = 0.5
END_SHARE = 0.2


def measures(v: Vertebra) -> Tuple[Dict[str, float], Dict[str, str]]:
    B = v.body_pts
    out: Dict[str, float] = {}
    flags: Dict[str, str] = {}
    if len(B) < G.MIN_BODY_VOXELS:
        return out, {"body": "no body"}
    xc = 0.5 * (B[:, 0].min() + B[:, 0].max())
    out.update(heights(v, B, xc))
    out.update(waist(v, B, xc))
    cells = plate_cells(B, v.pixel)
    for top, name in ((True, "endplate"), (False, "endplate_lower")):
        out[name + "_concavity"] = concavity(cells, top, v.fz)
        out[name + "_area"] = plate_area(v, B, top, out[name + "_concavity"])
    out.update(inclinations(v, B, xc))
    out["body_volume"] = float(len(B)) * v.voxel_volume
    out["vertebra_volume"] = float(len(v.loc)) * v.voxel_volume
    if v.touching[v.body].any():
        for k in list(out):
            out[k] = NAN
        flags["body"] = "the body touches the edge of the volume"
    return out, flags


def band(B: np.ndarray, xc: float, y0: float) -> np.ndarray:
    return B[(np.abs(B[:, 1] - y0) <= BAND_HALF_MM) & (np.abs(B[:, 0] - xc) <= ACROSS_HALF_MM)]


def plate_core(B: np.ndarray, top: bool) -> np.ndarray:
    """Which of the body's points lie within CORE_SHARE of the end-plate's middle, the middle
    and the half-axes those of the points in the END_SHARE of the body's height next to the
    plate. scanimport.geometry.central takes them from all the body's points, whose spread a
    waist pulls toward the posterior wall, since a body narrows at mid-height in front and at the
    sides but not behind; the core then sits behind the plate's middle, and over a concave plate
    its plane tilts: on the phantom with a 2 mm concavity and a waist of 0.92 the wedge read 2.8
    degrees where it is 5.1."""
    z = B[:, 2]
    z0, z1 = np.percentile(z, [2, 98])
    reach = END_SHARE * (z1 - z0)
    end = B[z >= z1 - reach] if top else B[z <= z0 + reach]
    if len(end) < G.MIN_CHORD_POINTS:
        return G.central(B[:, 0], B[:, 1])
    (a0, a1), (b0, b1) = np.percentile(end[:, 0], [2, 98]), np.percentile(end[:, 1], [2, 98])
    ha, hb = max(0.5 * (a1 - a0), 1e-6), max(0.5 * (b1 - b0), 1e-6)
    return ((B[:, 0] - 0.5 * (a0 + a1)) / ha) ** 2 + ((B[:, 1] - 0.5 * (b0 + b1)) / hb) ** 2 <= G.CORE_SHARE ** 2


def plate_points(B: np.ndarray, pixel: float, top: bool) -> np.ndarray:
    """The extremes of the cells of the plate's central part (plate_core, plate_extremes)."""
    inner = plate_core(B, top)
    return plate_extremes(B[inner] if inner.sum() >= G.MIN_CHORD_POINTS else B, pixel, top)


def plate_slopes(B: np.ndarray, pixel: float, layer: float) -> Dict[bool, np.ndarray]:
    """Each end-plate's plane (c0, c1, c2) through the extremes of its central cells."""
    out = {}
    for top in (True, False):
        ext = plate_points(B, pixel, top)
        out[top] = plane_robust(ext, layer) if len(ext) >= 6 else np.zeros(3)
    return out


def band_surface(pts: np.ndarray, x0: float, y0: float, plane: np.ndarray, top: bool, layer: float) -> float:
    """Where a plate lies over the band centred at (x0, y0): every point of the band is carried
    along the plate's slope to the band's centre, and the surface is read on all of them at once,
    whose many positions next to the end tell the layers' spacing (scanimport.geometry.edge_gap)
    better than the few in one cell.

    Counting the voxels beyond a level inside the body, over the band's area, was tried in its
    place and set aside: on the phantom with 0.86 by 0.86 by 2.5 mm voxels over tilts from 0 to
    25 degrees its heights erred by 0.5 to 1.0 mm on average (standard deviation 1.0 to 1.3,
    largest 3.3) against this rule's 0.6 to 0.7 (0.8 to 1.0, largest 2.3), since a 3 by 6 mm
    band holds three or four pixels across and the count of lattice points in it swings by a
    column. Either rule errs by about a millimetre on 2.5 mm slices, so heights and discs are
    compared with the literature on thin slices first."""
    sel = band(pts, x0, y0)
    if len(sel) < G.MIN_CHORD_POINTS:
        return NAN
    z = sel[:, 2] - plane[1] * (sel[:, 0] - x0) - plane[2] * (sel[:, 1] - y0)
    return G.surface(z, top, layer)


def heights(v: Vertebra, B: np.ndarray, xc: float) -> Dict[str, float]:
    planes = plate_slopes(B, v.pixel, v.fz)
    rims = {top: plate_rims(v, B, top, xc) for top in (True, False)}
    h = {}
    for name, at in (("h_ant", lambda r: r[1]), ("h_post_inset", lambda r: r[0]),
                     ("h_mid", lambda r: 0.5 * (r[0] + r[1]))):
        yt, yb = at(rims[True]), at(rims[False])
        zt = band_surface(B, xc, yt, planes[True], True, v.fz)
        zb = band_surface(B, xc, yb, planes[False], False, v.fz)
        h[name] = math.hypot(zt - zb, yt - yb)
    hp = h["h_post_inset"]
    h["body_index_ant_post"] = h["h_ant"] / hp if hp > 0 else NAN
    h["body_index_mid_post"] = h["h_mid"] / hp if hp > 0 else NAN
    return h


def plane_lsq(ext: np.ndarray) -> np.ndarray:
    A = np.column_stack([np.ones(len(ext)), ext[:, 0], ext[:, 1]])
    return np.linalg.lstsq(A, ext[:, 2], rcond=None)[0]


def plate_extremes(pts: np.ndarray, pixel: float, top: bool) -> np.ndarray:
    """One row per cell across the column: the cell's mean position and its extreme height. A
    cell at the edge of the points holds a few of them scattered over the body's height, whose
    highest need not be near the plate, so cells holding under half the median count are left
    out."""
    order, starts, ends = G.cells(pts, pixel)
    z, xy = pts[order, 2], pts[order, :2]
    counts = ends - starts
    full = counts >= 0.5 * np.median(counts)
    pick = np.max if top else np.min
    return np.array([[*xy[a:b].mean(0), pick(z[a:b])] for a, b, ok in zip(starts, ends, full) if ok]).reshape(-1, 3)


def plane_robust(ext: np.ndarray, layer: float) -> np.ndarray:
    """The least-squares plane, fitted again without the cells more than two layers off it."""
    c = plane_lsq(ext)
    for _ in range(3):
        res = np.abs(ext[:, 2] - (c[0] + c[1] * ext[:, 0] + c[2] * ext[:, 1]))
        keep = res <= 2.0 * layer
        if keep.all() or keep.sum() < 6:
            break
        ext = ext[keep]
        c = plane_lsq(ext)
    return c


def plate_cells(B: np.ndarray, pixel: float) -> Dict[str, np.ndarray]:
    """Both plates' cell extremes, with each cell's radius as a share of the half-width and
    half-depth of the cells' own spread."""
    top, bot = plate_extremes(B, pixel, True), plate_extremes(B, pixel, False)
    lo, hi = top[:, :2].min(0), top[:, :2].max(0)
    c, half = 0.5 * (lo + hi), np.maximum(0.5 * (hi - lo), 1e-6)
    rho = np.sqrt((((top[:, :2] - c) / half) ** 2).sum(1))
    return {"top": top, "bottom": bot, "rho": rho}


def concavity(cells: Dict[str, np.ndarray], top: bool, layer: float) -> float:
    ext, rho = cells["top" if top else "bottom"], cells["rho"]
    ring, centre = ext[(rho >= RIM[0]) & (rho <= RIM[1])], ext[rho <= CENTRE]
    if len(ring) < 6 or len(centre) < 3:
        return NAN
    c = plane_robust(ring, layer)
    plane = c[0] + c[1] * centre[:, 0] + c[2] * centre[:, 1]
    depth = plane - centre[:, 2] if top else centre[:, 2] - plane
    return float(np.median(depth))


def plate_area(v: Vertebra, B: np.ndarray, top: bool, cdepth: float) -> float:
    c = G.plate_plane(B, plate_core(B, top), v.pixel, top, v.fz)
    n_local = np.array([-c[1], -c[2], 1.0])
    norm = float(np.linalg.norm(n_local))
    inside = (c[0] + c[1] * B[:, 0] + c[2] * B[:, 1] - B[:, 2]) / norm
    if not top:
        inside = -inside
    a = (cdepth if np.isfinite(cdepth) else 0.0) + AREA_BEYOND_MM
    t = max(AREA_SLAB_MM, v.footprint(n_local / norm))
    n = int(((inside >= a) & (inside < a + t)).sum())
    return float(n) * v.voxel_volume / t if n >= G.MIN_CHORD_POINTS else NAN


def mid_slab(v: Vertebra, B: np.ndarray, xc: float) -> np.ndarray:
    """The slab across the body half-way between its end-plates, at the body's middle."""
    inner = G.central(B[:, 0], B[:, 1])
    ct = G.plate_plane(B, plate_core(B, True), v.pixel, True, v.fz)
    cb = G.plate_plane(B, plate_core(B, False), v.pixel, False, v.fz)
    yc = float(np.median(B[inner, 1])) if inner.any() else float(B[:, 1].mean())
    zc = 0.5 * ((ct[0] + ct[1] * xc + ct[2] * yc) + (cb[0] + cb[1] * xc + cb[2] * yc))
    return B[np.abs(B[:, 2] - zc) <= max(0.5 * v.fz, 1.0)]


def waist(v: Vertebra, B: np.ndarray, xc: float) -> Dict[str, float]:
    """The waist's depth on the midline and its width across the body's mid-depth. Read across
    the whole slab the width took in the transverse processes where they spring from the body,
    as L5's do: 76 mm at study 0004's L5."""
    slab = mid_slab(v, B, xc)
    mid = slab[np.abs(slab[:, 0] - xc) <= ACROSS_HALF_MM]
    if len(mid) < 2:
        return {"body_w_mid": NAN, "body_d_mid": NAN}
    y0, y1 = G.surface(mid[:, 1], False, v.fy), G.surface(mid[:, 1], True, v.fy)
    across = slab[np.abs(slab[:, 1] - 0.5 * (y0 + y1)) <= max(BAND_HALF_MM, 0.5 * v.fy)]
    return {"body_w_mid": G.extent(across[:, 0], v.fx), "body_d_mid": y1 - y0}


def posterior_wall_slope(v: Vertebra, B: np.ndarray, xc: float) -> float:
    """dy/dz of the body's posterior surface at the midline, over the middle 60 per cent of its
    height, from the most posterior point of each layer."""
    mid = B[np.abs(B[:, 0] - xc) <= ACROSS_HALF_MM]
    if len(mid) < G.MIN_CHORD_POINTS:
        return 0.0
    z0, z1 = mid[:, 2].min(), mid[:, 2].max()
    lo, hi = z0 + 0.2 * (z1 - z0), z1 - 0.2 * (z1 - z0)
    step = max(v.fz, 0.5)
    rows = []
    for z in np.arange(lo, hi + 1e-9, step):
        layer = mid[np.abs(mid[:, 2] - z) <= 0.5 * step]
        if len(layer):
            rows.append((z, layer[:, 1].min()))
    if len(rows) < 3:
        return 0.0
    rows = np.array(rows)
    return float(np.polyfit(rows[:, 0], rows[:, 1], 1)[0])


def plate_rims(v: Vertebra, B: np.ndarray, top: bool, xc: float) -> Tuple[float, float]:
    """Where an end-plate's bands lie front to back, (behind, ahead): INSET_MM inside its own
    posterior and anterior corners, the midline's extent in the END_SHARE of the body's height
    next to the plate; not a number where that holds too few points. Bands set from the body's
    extremes or its waist miss the corners: the body's most anterior point at study 0004's L5,
    which leans 17 degrees against the column's line, is a lip of its lower rim, and a band set
    there read an anterior height of 15 mm on a body 32 mm tall; the waist's front lies behind a
    waisted plate's corner, and over a concave plate that tilted the plate's line, on the phantom
    with a 2 mm concavity and a waist of 0.92, so that the wedge read 2.7 degrees where it is 5.1."""
    z = B[:, 2]
    z0, z1 = np.percentile(z, [2, 98])
    reach = END_SHARE * (z1 - z0)
    end = B[z >= z1 - reach] if top else B[z <= z0 + reach]
    mid = end[np.abs(end[:, 0] - xc) <= ACROSS_HALF_MM]
    if len(mid) < G.MIN_CHORD_POINTS:
        return NAN, NAN
    return G.surface(mid[:, 1], False, v.fy) + INSET_MM, G.surface(mid[:, 1], True, v.fy) - INSET_MM


def rim_plane(v: Vertebra, B: np.ndarray, top: bool, xc: float) -> np.ndarray:
    """The end-plate's plane (c0, c1, c2), its slope across (c1) that of the plane through the
    extremes of its central cells, its slope front to back (c2) from rim to rim: the line through
    the plate's surface in the anterior and the posterior height's bands (heights), as a reader
    draws it from corner to corner. The central plane's own slope front to back follows the
    concavity: at study 0004's L2 the lower plate's deepest point lies a third of the way from its
    back, so the plate's middle slopes 13 degrees where the plate slopes 5 from corner to corner,
    and the lumbar wedges read 11 to 21 degrees where their heights differ by 1 to 4 mm. The
    central plane stands in where a band holds too little."""
    ext = plate_points(B, v.pixel, top)
    c = plane_robust(ext, v.fz) if len(ext) >= 6 else np.zeros(3)
    back, ahead = plate_rims(v, B, top, xc)
    zb = band_surface(B, xc, back, c, top, v.fz)
    za = band_surface(B, xc, ahead, c, top, v.fz)
    if not (np.isfinite(za) and np.isfinite(zb)) or not ahead - back > 0:
        return c
    c2 = (za - zb) / (ahead - back)
    return np.array([zb - c[1] * xc - c2 * back, c[1], c2])


def inclinations(v: Vertebra, B: np.ndarray, xc: float) -> Dict[str, float]:
    b = math.atan(posterior_wall_slope(v, B, xc))
    out = {}
    slopes = {}
    for top, name in ((True, "endplate_incl"), (False, "endplate_lower_incl")):
        if len(plate_points(B, v.pixel, top)) < 6:
            out[name] = NAN
            continue
        slopes[top] = math.atan(rim_plane(v, B, top, xc)[2])
        out[name] = -math.degrees(slopes[top] + b)
    out["wedge"] = math.degrees(slopes[True] - slopes[False]) if len(slopes) == 2 else NAN
    return out
