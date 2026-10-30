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
the plate descends anteriorly. The wall's slope is read on the scan's own lattice from the
vertebra's label (posterior_wall, which says why), and where it is not read neither inclination
is, with a flag. The wedge is the angle between the two plates in the sagittal plane, positive
where the body is taller in front. The concavity is how far the centre of the plate (the median
of the cells within a quarter of its half-width and half-depth) lies below the least-squares
plane through its rim (the cells between 85 and 95 per cent of them). A plane resting on the rim
from outside would sit at the top of the voxels' scatter and the centre's median in its middle,
so a flat plate would read concave by half that scatter; two planes of the same kind cancel it.
"""
from __future__ import annotations

import math
from typing import Dict, Optional, Tuple

import numpy as np
from scipy.optimize import linprog

from scanimport import geometry as G

from .anatomy import NAN, Vertebra, square_to_wall

INSET_MM = 2.5
BAND_HALF_MM = 1.5
ACROSS_HALF_MM = 3.0
RIM = (0.85, 0.95)
CENTRE = 0.25
AREA_SLAB_MM = 2.0
AREA_BEYOND_MM = 0.5
END_SHARE = 0.2

# The posterior wall (posterior_wall):
WALL_HEIGHT_SHARE = 0.6       # the middle share of the height the body's points in the band span, clear of the rims
                              # and their lips
WALL_BAND_SHARE = 0.25        # the band reaches this share of the canal's width either side of the midline, half the
                              # canal's width in all, so the canal stands behind it
WALL_BAND_MAX_MM = 6.0        # and no more than this either side, so a wide lumbar canal's band stops short of the
                              # pedicles; on the cervical phantom (body 17 mm wide, canal 24) it is the whole 6 mm
WALL_GATE_SHARE = 0.25        # an edge lies within this share of the canal's depth of the canal's line: past that
                              # line's error on a clean wall (up to 3.7 degrees on 1 mm slices, 7.7 on 2.5 mm), short of
                              # the lamina; a notch leans the line (18.7 degrees through the suite's at mid-height) and
                              # the gate with it, and WALL_DROPPED_SHARE refuses what that leaves off the fit
WALL_RUN_MM = 3.0             # an edge stands at the back of this much solid bone, so a speck in the canal is no edge
WALL_TRIM_KEEP = 0.75         # the trimmed fit keeps this share: a notch or a lip holding more of the edges is not told
                              # from the wall
WALL_DROPPED_SHARE = 0.4      # not read where more of the band's edges than this lie more than a step off the fit: an
                              # 8 by 6 by 5 mm notch left 66 and 69 per cent and read 29 degrees off, and no reading
                              # of the cache, clean or altered, left more than 26 (1 mm slices) or 36 (2.5 mm)
WALL_BIWEIGHT_STEPS = 2.0     # the biweight's scale in lattice steps along y; a clean digitisation's edges lie within
                              # half a step
WALL_PART_MM = 1e-6           # a surface parts two centres only by more than this, so a centre on it parts nothing
WALL_ACROSS_MAX = 3           # the clamp sets aside at most this many edges the fit leaves furthest across, as specks
                              # behind the wall are, and no more
WALL_FREEDOM_DEG = 9.0        # not read where the lattice leaves the slope freer than this: pedicle.FREEDOM_DEG, kept
                              # here since pedicle imports this module
WALL_FREE_FLAG_DEG = 3.0      # flagged where freer than this, twice the suite's 1.5 degrees on the angles taken
                              # against it, since a reading may lie anywhere in its range
WALL_TRIM_STEPS = 30          # the trimmed fit's concentration steps at most; each lowers its cost, and they stop once
                              # it repeats
WALL_BIWEIGHT_ROUNDS = 50     # the biweight's rounds at most; they stop once the fit repeats
WALL_CROSSING_STEPS = 6       # Newton steps to where the fitted surface crosses an edge's scan line, straight along it
                              # but for the x^2 term


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
    flags.update(wall_flags(posterior_wall(v, B, xc)[1]))
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


def band_typical(pts: np.ndarray, x0: float, y0: float, plane: np.ndarray, top: bool, layer: float,
                 pixel: float) -> float:
    """Where a plate typically lies over the band: the points carried to the band's centre as
    band_surface carries them, then the median over the band's cells (scanimport.geometry.cells)
    of each cell's outermost point, plus half a layer. A disc is the gap between two such
    surfaces, and band_surface's outermost point of the whole band is set by any one cell a lip,
    an osteophyte or a voxel the mask gives the wrong label stands proud in: on the three CTs of
    2026-10-29 the discs read 1.35 mm under the gap the masks leave in the neck (the research
    note's disc test), a few tenths more than the masks themselves take in. The median takes
    the band's typical cell. Half a layer is added because a cell's outermost centre lies
    anywhere from flush with the surface to one layer below it: on a plate the lattice's layers
    lie along, every cell's does the same, and the surface is half a layer beyond, as `surface`
    puts it; on a plate they cross, the cells' outermost centres spread evenly over a layer, and
    their median lies half a layer in. Heights keep band_surface: their two plates are read on
    one body, where a lip is a part of the body, and the comparison with the papers stands on
    them."""
    sel = band(pts, x0, y0)
    if len(sel) < G.MIN_CHORD_POINTS:
        return NAN
    z = sel[:, 2] - plane[1] * (sel[:, 0] - x0) - plane[2] * (sel[:, 1] - y0)
    order, starts, ends = G.cells(sel, pixel)
    zs = z[order]
    pick = np.max if top else np.min
    ext = np.array([pick(zs[a:b]) for a, b in zip(starts, ends)])
    typical = float(np.median(ext))
    return typical + 0.5 * layer if top else typical - 0.5 * layer


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
    """dy/dz of the body's posterior wall at the midline (posterior_wall); NAN where it is not
    read."""
    return posterior_wall(v, B, xc)[0]


def posterior_wall(v: Vertebra, B: np.ndarray, xc: float) -> Tuple[float, dict]:
    """dy/dz of the body's posterior wall at the midline, in v's frame, and a record of the
    reading; NAN, with the reason under "why", where it is not read. Every angle taken against the
    plane square to the wall reads it here: the end-plates' inclinations (inclinations), the
    pedicles' sagittal angle (pedicle.wall_reading, once a side) and the spinous process's
    (posterior.spinous_angle). Each passes the body's points and the middle of their x range, so
    the reading is kept on the vertebra and read once; another B, another xc, or a vertebra read
    again in another frame or from another label reads it anew (kept_wall).

    The wall was read as the most posterior point of each layer of the body over the middle 60
    per cent of its height, a line fitted through them, and two things bent it where the scan's
    grid lies within a few degrees of the vertebra's frame, as on most supine lumbar studies.
    The wall on the lattice is a binary staircase, its last row of voxels stepping back a pixel
    every so many layers, and a layer's most posterior point follows the treads, not the
    surface; and the body is cut from the arch along the canal's line (anatomy.body_in_front,
    whose anatomy.wall_slope traces the same staircase in the slabs' walls), which leans on its
    own and so shaved the wall's first row at one end. Over the 98 phantom vertebrae of the
    cache of 30 October (four phantoms, the wall upright, leaned 5 degrees either way or 4
    forward, on seven grids from aligned with the frame to 25 degrees off, at 1 and 2.5 mm
    slices; research_notes/morphometry/handoff.md, its section of 30 October, records how it was
    built) that reading erred by up to 4.14 degrees on 1 mm slices and 5.66 on 2.5 mm, the worst
    on the grid tilted 2 degrees against the vertebra, and the angles taken against it carried
    the error one for one.

    It is now read on the scan's own lattice from the vertebra's whole label, not from the cut
    body, which gives only the window. Along the scan axis nearest the frame's y, stepping back
    (scan_step_back), a voxel of the label is the wall's last bone on its scan line where air
    lies one step behind it, bone fills WALL_RUN_MM in front of it and it lies within
    WALL_GATE_SHARE of the canal's depth of the canal's line (4.0 to 4.6 mm on the cache); the
    edge is half a step behind its centre, where a clean digitisation's surface lies on the mean;
    and of each scan line in the band (WALL_BAND_SHARE of the canal's width either side of the
    midline, at most WALL_BAND_MAX_MM either side) and the window (the middle WALL_HEIGHT_SHARE of
    the height the body's points in the band span) the most posterior edge is kept (wall_edges).
    At C2 the window ends at the top of the canal's full rings, so that the dens above the body
    does not reach it: on a cervical phantom on a grid 2 degrees off, with a dens whose back stood
    1.5 mm in front of the wall, the window run up the dens read the wall 8.1 degrees off on 1 mm
    slices and 7.8 on 2.5 mm, and ended there 0.02 and 0.05 (wall_window).

    The edges are fitted by the surface y = a + b z + c x + d x^2, x from the midline, by least
    trimmed squares, keeping WALL_TRIM_KEEP of them, from the whole set and from the window's
    lower, middle and upper halves (trimmed_start), polished by Tukey's biweight at a scale of
    WALL_BIWEIGHT_STEPS lattice steps along y (biweight), so that a notch or a hole's rim holding
    fewer than a quarter of the edges, at mid-height or off it, does not pull it; b is the wall's
    slope, and the edges more than a step off the fitted surface are left out of what follows. A
    notch holding more does pull it, and then leaves many edges off: one 8 mm wide, 6 tall and 5
    deep at mid-height read 29.2 degrees off on 1 mm slices and 29.5 on 2.5 mm, with 66 and 69 per
    cent of the band's edges more than a step off, so the wall is not read where more than
    WALL_DROPPED_SHARE are (fit_refused). No reading of the cache, clean or altered as below, left
    more than 26 per cent off on 1 mm slices or 36 on 2.5 mm; the rule refuses some sound
    readings too, as a notch 5 mm wide, 10 tall and 4 deep on 1 mm slices, which left 51 per cent
    off and which the fit read 0.19 degrees off.

    The clamp: where some surface of that family keeps every edge's bone centre in front of it and
    its air centre behind it, by more than WALL_PART_MM, the label parts, and the slopes b of the
    surfaces that part it form a range (wall_slope_range: a program for the widest margin, then
    two for the range's ends) in which the true wall lies if the label is its clean digitisation;
    b is clamped into it. One voxel of bone behind the wall keeps the whole label from parting, so
    where it does not part, the one, two or at most WALL_ACROSS_MAX edges the fitted surface
    leaves furthest across (fit_crossing) are set aside in turn and the rest asked again
    (wall_freedom): with one such speck behind one of six edges spread up the window, each in
    turn on each of the cache's vertebrae, 3 of the 294 labels so altered no longer parted on 1 mm
    slices and 1 of 294 on 2.5 mm, against 169 of 288 and 155 of 294 with none set aside, and the
    largest error with a speck was 1.30 degrees; on the leaned wall of the tests, one, two, three
    or five specks at once leave the reading as it was, and eight leave the label unparted. The clean phantoms'
    labels all part, one of the 98 with an edge set aside, and the truth lies in the range on 97
    of them; there the clamped reading errs by at most 0.35 degrees on 1 mm slices and 0.79 on 2.5
    mm (medians 0.07 and 0.19), where the fit alone erred by up to 1.24 and 1.18 (medians 0.10 and
    0.19). With the boundary's voxels flipped at random, or a ragged edge, the labels mostly do not
    part, and there the fit stands alone.

    The freedom is the range's width in degrees, or where the label does not part, the width of
    the range a clean digitisation of the fitted surface would leave on the same scan lines
    (clean_digitisation): how far the lattice pins the slope. Where the label parts it bounds the
    reading, which may lie anywhere in the range; where it does not, it bounds nothing, since the
    truth lay inside that range on only 21 of the 49 readings with flipped voxels on 1 mm slices
    and 31 of 49 on 2.5 mm, and 7 of 49 and 16 of 47 with the 0.3 mm ragged edge. Nor does it rank
    readings: over the cache's phantoms altered as below the rank correlation of the error with it
    was 0.18 on 1 mm slices and 0.12 on 2.5 mm, so a tight bound would refuse good readings with
    the bad. The wall is not read where the freedom passes WALL_FREEDOM_DEG, the bound
    pedicle.FREEDOM_DEG sets on the pedicle's climb, and measures flags a wall whose freedom
    passes WALL_FREE_FLAG_DEG (wall_flags), as on 3 of the 49 clean phantoms at 2.5 mm and none
    at 1 mm. Nor is it read without a full ring of the canal to place it, with fewer than
    G.MIN_CHORD_POINTS (eight) body points at the midline, edges in the band or edges within a
    step of the fitted surface, or where those edges span less than half the window.

    Over alterations of the cache's labels that keep the wall's slope (three notches, holes, an
    osteophyte, an axial scallop, a sagittal bow, flipped boundary voxels, the volume's edge across
    the body) the reading errs by at most 1.64 and 3.03 degrees, both on the bow; two readings
    with the volume's edge across the body on 2.5 mm slices are refused for their freedom, and
    none for its dropped share. Two alterations go further. A segmenter's ragged edge leans the
    label's own wall, which no reader of the label tells from the wall: an edge rough by 0.3 mm
    over 3 mm moved the reading up to 2.56 and 3.97 degrees, and 0.74 and 1.67 less that lean;
    one rough by 0.5 mm over 4 mm up to 5.43 and 6.97, and 1.05 and 2.57 less its lean. A lip
    standing 1.5 mm proud of the wall from 3 mm inside the window's top, on 2.5 mm slices one or
    two of its six or seven layers, is told by none of the fit's statistics and reads up to 11.7
    degrees off there, 1.61 on 1 mm slices. On the cervical phantom (canal 24 mm wide over a body
    17 mm wide) the band is the whole WALL_BAND_MAX_MM either side, 12 of the body's 17 mm, and the
    wall read within 1.47 degrees on 1 mm slices and 1.32 on 2.5 mm; a band of a quarter of the
    body's width either side read within 0.92 and 1.72, better on one thickness and worse on the
    other, and was not taken. The canal's line shares the staircase, up to 3.7 degrees off the
    clean wall on 1 mm slices and 7.7 on 2.5 mm over the cache, and is the next to read on the
    lattice, since it still sets the body's cut, Panjabi's depths, canal_ap_lateral_film and the
    drawn lines, though here it only gates the edges."""
    kept = kept_wall(v, B, xc)
    if kept is None:
        kept = read_wall(v, B, xc)
        v._posterior_wall = (v.frame, v.loc, xc, B, kept)
    return kept[0], dict(kept[1])


def kept_wall(v: Vertebra, B: np.ndarray, xc: float) -> Optional[Tuple[float, dict]]:
    """The reading posterior_wall kept on v, where it was read on these points and this xc in v's
    present frame and label; None otherwise. The frame and the label are told by identity, since
    anatomy.read_in gives a turned frame a new Frame and new local points."""
    kept = getattr(v, "_posterior_wall", None)
    if kept is None:
        return None
    frame, loc, x0, B0, reading = kept
    if frame is v.frame and loc is v.loc and x0 == xc and np.array_equal(B0, B):
        return reading
    return None


def read_wall(v: Vertebra, B: np.ndarray, xc: float) -> Tuple[float, dict]:
    """The reading posterior_wall keeps: the slope and its record, or NAN and why."""
    place, why = wall_window(v, B, xc)
    if place is None:
        return NAN, {"why": why}
    half, reach, lo, hi = place
    bone, d = wall_edges(v, xc, half, lo, hi, reach)
    if len(bone) < G.MIN_CHORD_POINTS:
        return NAN, {"why": "%d edges of the wall in the band" % len(bone)}
    e = bone + 0.5 * d
    coef = fitted_wall(e, d, xc)
    step_y = abs(d[1])
    r = e[:, 1] - wall_design(e, xc) @ coef
    good = np.abs(r) <= step_y
    why = fit_refused(e, good, lo, hi)
    if why:
        return NAN, {"why": why, "edges": int(good.sum()), "dropped": int((~good).sum())}
    b_lo, b_hi, parted, across = wall_freedom(bone[good], d, coef, xc)
    b = min(max(float(coef[1]), b_lo), b_hi) if parted else float(coef[1])
    free = degrees_of(b_hi) - degrees_of(b_lo) if not math.isnan(b_lo) else math.inf
    info = {"edges": int(good.sum()), "dropped": int((~good).sum()), "half_band_mm": half,
            "span_mm": float(np.ptp(e[good, 2])), "parted": parted, "across": across,
            "fitted_deg": degrees_of(coef[1]), "free_lo_deg": degrees_of(b_lo), "free_hi_deg": degrees_of(b_hi),
            "free_deg": free, "rms_over_step": float(np.sqrt(np.mean(r[good] ** 2)) / step_y)}
    if not free <= WALL_FREEDOM_DEG:
        return NAN, dict(info, why="the lattice leaves the wall's slope free over %.1f degrees, more than %.0f"
                         % (free, WALL_FREEDOM_DEG))
    return b, info


def fitted_wall(e: np.ndarray, d: np.ndarray, xc: float) -> np.ndarray:
    """The wall's surface through the edges: least trimmed squares, then the biweight."""
    X = wall_design(e, xc)
    return biweight(X, e[:, 1], trimmed_start(X, e[:, 1], e[:, 2]), WALL_BIWEIGHT_STEPS * abs(d[1]))


def fit_refused(e: np.ndarray, good: np.ndarray, lo: float, hi: float) -> str:
    """Why the fitted surface is not taken for the wall, empty where it is: too few edges within a
    step of it, more than WALL_DROPPED_SHARE of them further off, or those within it spanning less
    than half the window."""
    if good.sum() < G.MIN_CHORD_POINTS:
        return "%d edges near the wall's surface" % good.sum()
    if (~good).mean() > WALL_DROPPED_SHARE:
        return ("%.0f per cent of the band's edges lie more than a step off the fitted surface, more than %.0f: "
                "a notch or a lip that holds so many is not told from the wall" % (100 * (~good).mean(),
                                                                                    100 * WALL_DROPPED_SHARE))
    span = float(np.ptp(e[good, 2]))
    if span < 0.5 * (hi - lo):
        return "the wall's edges span %.1f mm of a %.1f mm window" % (span, hi - lo)
    return ""


def degrees_of(slope: float) -> float:
    """A slope's angle in degrees; an unbounded slope is 90 degrees."""
    return math.degrees(math.atan(slope))


def wall_window(v: Vertebra, B: np.ndarray, xc: float) -> Tuple[Optional[Tuple[float, float, float, float]], str]:
    """Where the wall is read: the band's half-width, how far it reaches either side of the
    midline, and the gate's reach about the canal's line, both set by the canal's full rings, and
    the window's bottom and top, the middle WALL_HEIGHT_SHARE of the height the body's points in
    the band span, at C2 of that height below the top of the canal's full rings, so that the dens
    is left out; None and why where there is no full ring or the band holds too few of the body's
    points."""
    rings = v.full_rings()
    if not rings:
        return None, "no full ring of the canal gives the wall's place"
    half = min(WALL_BAND_MAX_MM, WALL_BAND_SHARE * float(np.median([s.width for s in rings])))
    reach = WALL_GATE_SHARE * float(np.median([s.ap for s in rings]))
    mid = B[np.abs(B[:, 0] - xc) <= half]
    if len(mid) < G.MIN_CHORD_POINTS:
        return None, "too few body points at the midline"
    z0, z1 = mid[:, 2].min(), mid[:, 2].max()
    if v.level == "C2":
        z1 = min(z1, max(s.z for s in rings))
    trim = 0.5 * (1.0 - WALL_HEIGHT_SHARE) * (z1 - z0)
    return (half, reach, z0 + trim, z1 - trim), ""


def scan_step_back(v: Vertebra) -> Tuple[int, np.ndarray, np.ndarray]:
    """The scan's axis nearest the frame's y, and one step along it toward the back: the axis,
    the step in voxel indices and the step in the frame."""
    axes, spacing, f = v.grid.axes, v.grid.spacing, v.frame
    w = int(np.argmax(np.abs(axes.T @ f.ey)))
    sign = -1 if axes[:, w] @ f.ey > 0 else 1
    step = np.zeros(3, int)
    step[w] = sign
    d = sign * spacing[w] * axes[:, w]
    return w, step, np.array([d @ f.ex, d @ f.ey, d @ f.ez])


def wall_edges(v: Vertebra, xc: float, half: float, lo: float, hi: float,
               reach: float) -> Tuple[np.ndarray, np.ndarray]:
    """The wall's last bone on each scan line through the band and the window, its most
    posterior where a line holds several: their centres in the frame, and the step back (the
    edge lies half of it behind each)."""
    w, step, d = scan_step_back(v)
    loc = v.loc
    near = ((np.abs(square_to_wall(v, loc)[:, 1] - v.wall_y0) <= reach) & (np.abs(loc[:, 0] - xc) <= half + v.pixel)
            & (loc[:, 2] >= lo - v.fz) & (loc[:, 2] <= hi + v.fz))
    P, q = v.idx[near], loc[near]
    keep = backmost_bone(v, P, step, v.grid.spacing[w])
    bone, line = q[keep], np.delete(P[keep], w, axis=1)
    e = bone + 0.5 * d
    inside = (np.abs(e[:, 0] - xc) <= half) & (e[:, 2] >= lo) & (e[:, 2] <= hi)
    return most_posterior_per_line(bone[inside], line[inside]), d


def backmost_bone(v: Vertebra, P: np.ndarray, step: np.ndarray, pitch: float) -> np.ndarray:
    """Which voxels have air one step behind them and bone over WALL_RUN_MM in front, the steps
    pitch mm apart."""
    keep = ~v.is_bone(P + step)
    for m in range(1, int(math.ceil(WALL_RUN_MM / pitch)) + 1):
        keep &= v.is_bone(P - m * step)
    return keep


def most_posterior_per_line(bone: np.ndarray, line: np.ndarray) -> np.ndarray:
    """Of the centres on each scan line, the line given by its two other voxel indices, the one
    with the least y."""
    order = np.lexsort((bone[:, 1], line[:, 1], line[:, 0]))
    bone, line = bone[order], line[order]
    first = np.ones(len(bone), bool)
    first[1:] = (line[1:] != line[:-1]).any(1)
    return bone[first]


def wall_design(p: np.ndarray, xc: float) -> np.ndarray:
    """The columns of the wall's surface y = a + b z + c x + d x^2, x from the midline."""
    x = p[:, 0] - xc
    return np.column_stack([np.ones(len(p)), p[:, 2], x, x * x])


def trimmed_start(X: np.ndarray, y: np.ndarray, z: np.ndarray) -> np.ndarray:
    """Least trimmed squares: the fit to the WALL_TRIM_KEEP share of the edges with the least
    squared residuals, never fewer than G.MIN_CHORD_POINTS, by concentration steps from the whole
    set and from the window's lower, middle and upper halves, the start of least trimmed cost
    kept; outliers bunched at one end or on one side of mid-height then pull no start they do
    not hold."""
    n = len(y)
    h = max(int(WALL_TRIM_KEEP * n), G.MIN_CHORD_POINTS)
    order = np.argsort(z)
    best = None
    for sub in [order] + [order[i * n // 4:(i + 2) * n // 4] for i in range(3)]:
        coef = np.linalg.lstsq(X[sub], y[sub], rcond=None)[0]
        for _ in range(WALL_TRIM_STEPS):
            idx = np.argsort((y - X @ coef) ** 2)[:h]
            new = np.linalg.lstsq(X[idx], y[idx], rcond=None)[0]
            done = np.allclose(new, coef, atol=1e-10)
            coef = new
            if done:
                break
        cost = np.sort((y - X @ coef) ** 2)[:h].sum()
        if best is None or cost < best[0]:
            best = (cost, coef)
    return best[1]


def biweight(X: np.ndarray, y: np.ndarray, coef: np.ndarray, scale: float) -> np.ndarray:
    """Tukey's biweight from the start given: each edge weighted by (1 - u^2)^2, u its residual
    over the scale, none beyond it."""
    for _ in range(WALL_BIWEIGHT_ROUNDS):
        u = (y - X @ coef) / scale
        w = np.where(np.abs(u) < 1.0, (1.0 - u * u) ** 2, 0.0)
        if (w > 0).sum() < X.shape[1]:
            break
        sw = np.sqrt(w)
        new = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)[0]
        done = np.allclose(new, coef, atol=1e-9)
        coef = new
        if done:
            break
    return coef


def wall_freedom(bone: np.ndarray, d: np.ndarray, coef: np.ndarray,
                 xc: float) -> Tuple[float, float, bool, int]:
    """The range of slopes the lattice leaves the wall, whether the label parts and how many edges
    were set aside for it: the range of the surfaces that part the edges' bone centres from their
    air centres, a step behind, all of them or all but the one, two or at most WALL_ACROSS_MAX
    that the fitted surface leaves furthest across (fit_crossing), as a speck behind the wall is;
    or where no such set parts, that of the clean digitisation of the fitted surface on the same
    scan lines."""
    air = bone + d
    cross = fit_crossing(bone, air, coef, xc)
    order = np.argsort(-cross)
    for k in range(WALL_ACROSS_MAX + 1):
        if k and cross[order[k - 1]] <= 0.0:
            break
        keep = np.ones(len(bone), bool)
        keep[order[:k]] = False
        b_lo, b_hi = wall_slope_range(bone[keep], air[keep], xc)
        if not math.isnan(b_lo):
            return b_lo, b_hi, True, k
    b_lo, b_hi = wall_slope_range(*clean_digitisation(bone, d, coef, xc), xc)
    return b_lo, b_hi, False, 0


def fit_crossing(bone: np.ndarray, air: np.ndarray, coef: np.ndarray, xc: float) -> np.ndarray:
    """How far the fitted surface leaves each edge's pair of centres across, its bone centre behind
    it or its air centre in front, in mm along y; nought for a pair it parts."""
    behind = wall_design(bone, xc) @ coef - bone[:, 1]
    ahead = air[:, 1] - wall_design(air, xc) @ coef
    return np.maximum(np.maximum(behind, ahead), 0.0)


def wall_programme(bone: np.ndarray, air: np.ndarray, xc: float) -> Tuple[np.ndarray, np.ndarray]:
    """The constraints of a surface of the wall's family keeping the bone centres in front of it
    and the air centres behind, as A x <= b over its four coefficients."""
    F = wall_design(np.vstack([bone, air]), xc)
    sign = np.concatenate([np.ones(len(bone)), -np.ones(len(air))])
    y = np.concatenate([bone[:, 1], air[:, 1]])
    return sign[:, None] * F, sign * y


def wall_slope_range(bone: np.ndarray, air: np.ndarray, xc: float) -> Tuple[float, float]:
    """The least and the greatest b of a surface of the wall's family keeping every bone centre in
    front of it and every air centre behind, by more than WALL_PART_MM; an end the centres do not
    bound is infinite, and NAN, NAN where no surface parts them. Whether one does is the widest
    margin's to say, a program of its own, as pedicle.parting asks it: where the margin is under
    WALL_PART_MM only within the solver's own tolerance, as one speck behind the wall leaves it,
    HiGHS answers the range's programs with no verdict (status 4) or with a point a hair across.
    Of posterior_wall's 294 speck labels on 1 mm slices, two left margins of 7e-8 and 8e-8 mm and
    drew status 4, one on both programs, which read as unbounded ends left that wall free over 180
    degrees and refused it."""
    A, b = wall_programme(bone, air, xc)
    widest = linprog(c=[0.0, 0.0, 0.0, 0.0, -1.0], A_ub=np.column_stack([A, np.ones(len(b))]), b_ub=b,
                     bounds=[(None, None)] * 5, method="highs")
    if widest.status not in (0, 3) or (widest.status == 0 and widest.x[4] <= WALL_PART_MM):
        return NAN, NAN
    ends = []
    for c, unbounded in (([0.0, 1.0, 0.0, 0.0], -math.inf), ([0.0, -1.0, 0.0, 0.0], math.inf)):
        res = linprog(c=c, A_ub=A, b_ub=b - WALL_PART_MM, bounds=[(None, None)] * 4, method="highs")
        if res.status not in (0, 3):
            return NAN, NAN
        ends.append(float(res.x[1]) if res.status == 0 else unbounded)
    return ends[0], ends[1]


def clean_digitisation(bone: np.ndarray, d: np.ndarray, coef: np.ndarray,
                       xc: float) -> Tuple[np.ndarray, np.ndarray]:
    """The centres either side of where the fitted surface crosses each edge's scan line, bone in
    front and air behind: the label a clean digitisation of that surface would give on the same
    lines."""
    a, b, c, dd = coef
    x = bone[:, 0] - xc
    t = np.zeros(len(bone))
    for _ in range(WALL_CROSSING_STEPS):
        px, pz = x + t * d[0], bone[:, 2] + t * d[2]
        g = bone[:, 1] + t * d[1] - (a + b * pz + c * px + dd * px * px)
        dg = d[1] - (b * d[2] + c * d[0] + 2.0 * dd * px * d[0])
        t = t - g / dg
    k = np.floor(t)[:, None]
    return bone + k * d, bone + (k + 1.0) * d


def wall_flags(info: dict) -> Dict[str, str]:
    """What measures says of the wall: why it was not read, so that the end-plates' inclinations
    are not either; or that the lattice leaves its slope free over more than WALL_FREE_FLAG_DEG.
    Where the label parts, the reading lies somewhere in that range, so every angle taken against
    the wall may be off by up to its width; where it does not, the width is that of a clean
    digitisation of the fitted surface and bounds nothing (posterior_wall)."""
    if "why" in info:
        return {"posterior_wall": "the body's posterior wall is not read, so neither end-plate's inclination is: "
                                  + info["why"]}
    if info["free_deg"] > WALL_FREE_FLAG_DEG:
        return {"posterior_wall_free": "the lattice leaves the posterior wall's slope free over %.1f degrees, more "
                                       "than %.0f: %s" % (info["free_deg"], WALL_FREE_FLAG_DEG, free_meaning(info))}
    return {}


def free_meaning(info: dict) -> str:
    """What the freedom says of the angles taken against the wall: a bound where the label parts,
    nothing where it does not (wall_flags)."""
    if info["parted"]:
        return "the angles taken against the wall may be off by up to that"
    return ("the label does not part bone from air along the wall, so that width is a clean digitisation's and "
            "bounds nothing")


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
    """Each end-plate's inclination against the plane square to the posterior wall, not a number
    where the wall is not read (posterior_wall, whose reason measures flags), and the wedge, which
    needs no wall."""
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
