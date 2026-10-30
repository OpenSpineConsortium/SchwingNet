"""The pedicles: width, height and area at the isthmus, the axis's two angles and the chord along
it, each side; and between them the interpedicular distance both ways it is defined, read on
the same walls.

The pedicle is the bridge of bone from the body to the articular pillar beside the canal, and
its width and height are the least across it, where Zindrick (1987) and Panjabi read them, each
on the cut that shows it: the width on an axial cut through the pedicle's middle height, the
height on a sagittal cut through its middle across. A whole-vertebra label gives no pedicle
subregion, so the pedicle is found from the canal. In a row front to back at a height, the
first bone outward from the canal's midline on a side is the canal's wall there, and the bone
from that wall outward as far as the first gap wider than GAP_VOXELS voxels is the section of
what stands beside the canal in that row (SideMap.chord). Over the rows from the body's
posterior wall back to the canal's posterior wall that section is wide where the body's
posterolateral corner stands beside the canal, narrow along the pedicle's free length, and wide
again where the transverse process, the articular pillar or the lamina joins: lateral of a
cervical pedicle lies the foramen transversarium, lateral of a thoracic or a lumbar one air up
to the transverse process's root behind it, so the row through the isthmus ends at a gap on
every level. Each row is read at three heights, the body's median and ANCHOR_SHARE of its
height above and below it, since a thoracic pedicle stands on the upper part of the body and a
lumbar one about its middle, and each reading is settled: the column of bone at the middle of
its section (height_run) gives the pedicle's top and bottom in that row, and the section is
read again at their middle, the pedicle's own middle height there, so a pitched pedicle is
followed row by row; the row keeps the reading of least area, width times height, since the
pedicle is the smallest thing beside the canal in any row through it (profile). The isthmus is
the least of that area profile, smoothed over three rows (canal.smoothed_values) and sought in
the front FRONT_SHARE of the canal's depth, where the pedicle stands, since behind it the
lamina's inner surface bounds the canal and a row through the lamina on the slant reads as
narrow as a pedicle; never the row at the body's wall itself, whose band catches the wall's own
voxels. The rows about it within ISTHMUS_SHARE of it are the isthmus rows, Zindrick's narrowest
part of the pedicle, less the rows that are not the pedicle's (pedicle_rows): one whose medial
wall stands more than CORNER_MM nearer the midline than the others', the body's posterolateral
corner in front or the lamina behind, which curve in toward the midline (at study 0004's L4 the
corner's row turned the left axis to 47 degrees), and one whose width or height is more than
OUTLIER_SHARE from the others', a cut through the articular process's edge (on the phantoms one
such row, 4 mm wide and 28 tall, pitched the sagittal angle 16 degrees). The width is the
median of their sections, the height the median of their columns; what joins the pedicle above
or below at the pillar does not stand in that column at the isthmus. A section wider than the
level's PEDICLE_MAX_MM is the pedicle with what joins it laterally, the transverse process's
root at L5 or the lateral mass in the neck, and is not read; nor is a cervical pedicle whose
lateral border, the foramen transversarium, the mask does not close (anatomy's body_foramina
flag), since the march then runs into the lateral mass (study 0004's C5 read 15 mm wide and
the band between the pedicles nothing).

Why the canal's hole is not used, as the readings of 2026-10-29 used it: a hole needs the ring
closed, laminae and pedicles in one slab, and on the masks the ring closes in two to eight
slabs only (study 0004: eight at L3, five at L5, one at C5), where the pedicles stand higher or
lower than the laminae's overlap or the frame lies 30 degrees against the scan's layers, so C3
to C7, L4 and L5 had no slab at the pedicle's height. The coronal island's extent, the run's
first reading, took the lateral mass and the transverse process's root with the pedicle (12 to
22 mm where 5 to 9 is real), and its fewest-voxel seed landed 5 to 9 mm from the pedicle at L5
and C5, since on real masks every coronal island holds a process's root. A reading in cuts
square to the axis crossed the lamina behind the short thoracic pedicle (widths of 20 to 30 mm
at study 0004's T7). The march needs no ring and no island: a wall is wherever bone first
stands beside the canal.

An axial cut through the pedicle's middle crosses a converging pedicle on the slant, so the
width is the section times the cosine of the transverse angle, and a sagittal column crosses a
pitched pedicle the same way, so the height is the run times the cosine of the sagittal angle
where that angle is read. The area is the ellipse's on the width and the height, pi w h / 4,
the shape a pedicle's section is taken to have, since no cut of a whole-vertebra label gives the
pedicle's own outline where a process joins it.

The axis runs through the isthmus rows, pointing back. Across, it follows the medial wall, the
canal's edge, each row's wall the median of its section's medial surface over the layers in the
middle half of its height (medial_wall), since one layer's edge steps with the raster. The
lateral surface is free only along the isthmus rows and flares into the transverse process's
root behind them and the body's corner in front, so the sections' middles read the pedicles
converging more than they do (at study 0004's L4 27 to 42 degrees where the walls read 15, and
at L3 17 where the wall read 5, the root joining in the lower layers two rows behind the
isthmus); the wall is the one surface read the same in every row. The wall's line is extended
row by row forward and back while the next row's wall lies within WALL_FIT_MM of the line
through the isthmus rows' walls, or of their median where they are too few for a line, and does
not jut in (CORNER_MM), so that a short pedicle still gets a baseline, and the transverse angle
is the line's angle to the midsagittal plane, positive where the pedicles converge toward the
front, read where the rows taken span AXIS_SPAN_MM. It is the angle of the canal's wall along
the pedicle, which under-reads the pedicle's bisector where the lateral cortex flares, so the
research note sets the level medians beside the papers'. Up, the axis follows the pedicle's top and
bottom surfaces over the isthmus rows, each parted from the scan's own lattice (climb): in
every isthmus row the columns across the middle half of the section whose run is the pedicle's,
within HEIGHT_SHARE of the isthmus's height, say to a layer where each surface lies (columns),
and the voxel centres within SURFACE_LAYERS of it under those columns, bone and air, are parted
by the surface z = a + b y + c x' + d x'^2 of widest margin (parting, a linear program), x' the
place across the section from its middle, so that the ellipse's crown goes into the quadratic
and b is the climb along the pedicle's centre line; the pedicle's climb is the mean of its two
surfaces'. One column's surfaces step with the raster: the fourth pass read the middle of one
column a row and fitted the middles' line, which on the phantoms' 7.5 mm baseline, with layers
of 1.24 mm, read 3 and 8 degrees where 0 and 6 are drawn, one layer over that baseline being 9
degrees; the centres on both sides of a surface bracket it wherever the layers cut it at another
phase, and under the columns of a tilted grid they do. The rows beyond the isthmus are not taken
for the climb: under them the pillar's and the body's corner's bone stands about the surface and
no one surface parts it (on the straight phantom the margin went negative and the climb read 10
degrees). The climb is not read (climb, which lists every reason) under fewer than MIN_COLUMNS
columns or with fewer than MIN_PARTED centres of bone or of air about a surface; where the lattice
does not part a surface, more than VIOLATED_SHARE of its centres lying across the best one or one
lying further across than SURFACE_LAYERS layers; where the surfaces that still part the lattice
leave the climb free over more than FREEDOM_DEG (slope_range), as on 2.5 mm slices, whose layers
the surfaces cross too rarely over the span to pin them and where the widest margin lies parallel
to the layers and reads the vertebra's tilt in the scanner (on the thick phantoms the ranges ran
10.6 to 33 degrees and the readings up to 9.7 off, on the 1 mm ones 0.2 to 7.7 and within 1.8, but
for the grids aligned with the frame, below, and one reading of the overhang phantom at 2.1); and where
the top's and the bottom's climbs lie more than APART_DEG apart (on the 1 mm phantoms at most 3.2).
The sagittal angle is the climb's angle in the sagittal projection, atan2(d[2], -d[1]) for the
axis d, as Zindrick read it on a sagittal cut and as the phantom draws it, positive where the
posterior end is higher, taken against the plane square to the body's posterior wall
(wall_slope), read where the columns span SAGITTAL_SPAN_MM front to back, the rows' own width of
half a pixel counted: the borders of so short a pedicle curve with the notch and the process, and
their climb is theirs, not the pedicle's (study 0004's thoracic pedicles spanned 4.5 to 5.3 mm
between the rows' places, a fifth of a millimetre or so less than this span counts, and climbed 40
to 50 degrees); the chord then takes the axis level, and where the rows are too few for an axis at
all the chord and the transverse angle are not read. The posterior wall is read on the scan's own
lattice from the vertebra's label (body.posterior_wall, which says how): on the clean phantom
vertebrae that function names, whose labels part bone from air as a clean digitisation does, it
read within 0.35 degrees on 1 mm slices and 0.79 on 2.5 mm, and its fit alone, which is all that
stands where a label does not part, within 1.24 and 1.18; the reading it replaced, the hindmost
body voxel of each layer, traced the lattice's staircase and erred up to 4.14 and 5.66, worst on
grids within 2 degrees of the vertebra's frame, and the sagittal angle took that error with it.
Where the wall is not read the sagittal angle is not either, with a note saying why. The canal
line the body is cut from the arch along (anatomy.wall_slope) still traces that staircase and is
the next to be fixed. The chord is the length of bone the axis line
through the isthmus crosses, from where it enters the posterior elements to where it leaves the
body's anterior cortex, read by marching along the line voxel by voxel (Zindrick's screw path).

The interpedicular distance, the least between the pedicles' medial walls (Hinck, the
paper-tables vocabulary), and Eisenstein's greatest interpedicular distance, the canal's width
at its widest between the pedicles, are read on the same walls (canal_between): at the
isthmus's place front to back, the mean of the two sides', the gap between the two walls in
every layer over the central half of the pedicles' height, its least; and over the rows from
the body's wall back to the isthmus in the same layers, its greatest, where at L4 and L5 the
walls flare into the lateral recesses and a caliper between the pedicles opens widest. A row
where bone stands within MIDLINE_CLEAR_MM of the midline on either side, the body's posterior
wall or the lamina crossing it, gives no gap (at study 0004's C5 the wall's rows read the
distance as nothing). Neither is read across the hole's middle, where scanimport reads a slab's
width: a lumbar canal is widest between the pedicles, and at its middle, behind them, the
laminae's junction bounds it, so the width through the middle read 2 to 3 mm under the papers'
at L4 and L5 and in the neck (the run of 2026-10-29, canal-shape.csv). canal.measures writes
both, and where a pedicle is not found on both sides reads the hole's width through the middle
for them, flagged.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import linprog

from scanimport import geometry as G

from . import body as BODY
from . import canal as CANAL
from .anatomy import NAN, Vertebra

ISTHMUS_SHARE = 1.2           # the isthmus: the rows whose section's area is within this share of the least
FRONT_SHARE = 0.6             # the isthmus is sought in this share of the canal's depth from the body's wall
ANCHOR_SHARE = 0.25           # each row is read at the body's median height and this share of its height above and below
OUTLIER_SHARE = 0.25          # an isthmus row whose width or height is further than this share from the others' is not the pedicle's
CORNER_MM = 1.0               # a row whose medial wall stands this much nearer the midline than the isthmus rows' is the body's corner or the lamina
HEIGHT_SHARE = 0.35           # a column whose height is further than this share from the isthmus's is not the pedicle's
SURFACE_LAYERS = 1.5          # a surface is parted from the voxel centres within this many layers of it under each column
MIN_COLUMNS = 6               # the surfaces are parted under no fewer columns
MIN_PARTED = 4                # a surface is parted from at least this many centres of bone and as many of air
VIOLATED_SHARE = 0.1          # a surface more of whose centres than this share lie across the best one is not read
FREEDOM_DEG = 9.0             # the climb is not read where the lattice leaves its angle free over more than this
APART_DEG = 5.0               # nor where the top's and the bottom's climbs lie further apart than this
WALL_FIT_MM = 1.0             # the axis takes a row whose medial wall lies within this of the line through the isthmus rows' walls
AXIS_SPAN_MM = 2.0            # the transverse angle needs the walls to span this front to back
SAGITTAL_SPAN_MM = 5.5        # the sagittal angle needs the columns to span this front to back, the rows' own width counted
PEDICLE_MAX_MM = {"C": 12.0, "T": 16.0, "L": 20.0}   # a section wider than the level's is the pedicle with what joins it laterally
MARCH_MM = 0.25
GAP_VOXELS = 2.0              # a step between voxel centres wider than this many voxels is a gap
REACH_MM = 30.0               # bone that first stands further out than this holds nothing of the pedicle
MIDLINE_CLEAR_MM = 4.0        # bone that first stands within this of the midline is the body's or the lamina's
SIDES = ((1, "right"), (-1, "left"))


class SideMap:
    """One side's sections of bone beside the canal, read on demand and kept: at a row y and a
    layer z, the voxels within three quarters of a pixel of the row and half a layer of the
    height, each at u = side (x - midline) out from the canal's midline, and the first run of
    bone outward, from the first voxel beyond the midline to the first gap of GAP_VOXELS, as
    (medial surface, lateral surface); None where no bone stands within REACH_MM of the
    midline, or one voxel alone."""

    def __init__(self, v: Vertebra, side: int):
        self.v, self.side = v, side
        self.u = side * (v.loc[:, 0] - v.midline)
        self.kept: Dict[Tuple[int, int], Optional[Tuple[float, float]]] = {}

    def chord(self, y0: float, z0: float) -> Optional[Tuple[float, float]]:
        v = self.v
        key = (int(round(10.0 * y0 / v.pixel)), int(round(10.0 * z0 / v.fz)))
        if key not in self.kept:
            self.kept[key] = self.read(y0, z0)
        return self.kept[key]

    def read(self, y0: float, z0: float) -> Optional[Tuple[float, float]]:
        v = self.v
        P = v.loc
        sel = (np.abs(P[:, 1] - y0) <= 0.75 * v.pixel) & (np.abs(P[:, 2] - z0) <= 0.5 * v.fz)
        u = np.sort(self.u[sel])
        u = u[u > 0]
        if len(u) < 2 or u[0] > REACH_MM:
            return None
        gaps = np.flatnonzero(np.diff(u) > GAP_VOXELS * v.fx)
        run = u[:gaps[0] + 1] if len(gaps) else u
        if len(run) < 2:
            return None
        return G.surface(run, False, v.fx), G.surface(run, True, v.fx)

    def x_of(self, u: float) -> float:
        return self.v.midline + self.side * u


# ---- the rows and their columns ----------------------------------------------------------------

def row_places(v: Vertebra) -> np.ndarray:
    """The rows' places front to back: from the body's posterior wall back to the canal's
    posterior wall, half a pixel apart, so that a short pedicle still gives rows enough."""
    return np.arange(v.wall, v.wall_post - 0.25 * v.pixel, -0.5 * v.pixel)


def anchors(v: Vertebra, zb: Tuple[float, float]) -> List[float]:
    """The heights every row is read at first: the body's median, and ANCHOR_SHARE of its
    height above and below it, since a thoracic pedicle stands on the upper part of the body
    and a lumbar one about its middle; each reading settles on its own column, and the row
    keeps the section with the least area (profile)."""
    B = v.body_pts
    z0 = float(np.median(B[:, 2])) if len(B) else 0.5 * (zb[0] + zb[1])
    step = ANCHOR_SHARE * (zb[1] - zb[0])
    return [z0, z0 + step, z0 - step]


def height_run(v: Vertebra, x0: float, y0: float, zc: float) -> Optional[Tuple[float, float]]:
    """The run of bone up the frame's z through (x0, y0) that holds zc: its bottom and top
    surfaces; None where no bone lies within a layer of zc there."""
    P = v.loc
    col = P[(np.abs(P[:, 0] - x0) <= 0.75 * v.pixel) & (np.abs(P[:, 1] - y0) <= 0.75 * v.pixel)]
    if len(col) < 2:
        return None
    z = np.sort(col[:, 2])
    k = int(np.argmin(np.abs(z - zc)))
    if abs(z[k] - zc) > v.fz:
        return None
    steps = np.diff(z)
    lo = k
    while lo > 0 and steps[lo - 1] <= GAP_VOXELS * v.fz:
        lo -= 1
    hi = k
    while hi + 1 < len(z) and steps[hi] <= GAP_VOXELS * v.fz:
        hi += 1
    run = z[lo:hi + 1]
    return G.surface(run, False, v.fz), G.surface(run, True, v.fz)


def section_at(m: SideMap, y0: float, z0: float) -> Optional[dict]:
    """The row's section at z0 and the column at its middle: the medial and lateral surfaces,
    the width between, the column's bottom and top, their middle and the height; None where
    nothing stands there, or where the first bone stands within MIDLINE_CLEAR_MM of the
    midline: that band catches the body's posterior wall, which curves forward from the
    midline, or the lamina, and no canal is so narrow (at the straight phantom the wall's row
    read a section 5.6 mm wide on the body's own wall, and with it in the run the axis turned
    55 degrees)."""
    ch = m.chord(y0, z0)
    if ch is None or ch[0] < MIDLINE_CLEAR_MM:
        return None
    x = m.x_of(0.5 * (ch[0] + ch[1]))
    run = height_run(m.v, x, y0, z0)
    if run is None:
        return None
    return {"y": y0, "u0": ch[0], "u1": ch[1], "w": ch[1] - ch[0], "x": x, "run": run,
            "z": 0.5 * (run[0] + run[1]), "h": run[1] - run[0]}


def settled(m: SideMap, y0: float, z0: float) -> Optional[dict]:
    """The row's section read at z0 and settled once on its own column's middle where that
    lies more than half a layer off."""
    r = section_at(m, y0, z0)
    if r is not None and abs(r["z"] - z0) > 0.5 * m.v.fz:
        r = section_at(m, y0, r["z"]) or r
    return r


def profile(m: SideMap, zs: List[float]) -> List[dict]:
    """Every row's section: read from each anchor height and settled, the one with the least
    area (width times height) kept, since the pedicle is the smallest thing beside the canal
    in any row through it, and a reading that lands on the body's posterolateral corner below
    it or on the articular process above it is taller or wider."""
    rows = []
    for y0 in row_places(m.v):
        found = [r for r in (settled(m, float(y0), z0) for z0 in zs) if r is not None]
        if found:
            rows.append(min(found, key=lambda r: r["w"] * r["h"]))
    return rows


def layers_of(v: Vertebra, run: Tuple[float, float]) -> np.ndarray:
    """The layers over the middle half of a column's run."""
    z0, z1 = run
    zs = np.arange(z0 + 0.25 * (z1 - z0), z1 - 0.25 * (z1 - z0) + 1e-9, v.fz)
    return zs if len(zs) else np.array([0.5 * (z0 + z1)])


def medial_wall(m: SideMap, y: float, layers: np.ndarray) -> float:
    """A row's medial wall for the axis: the median of its section's medial surface over the
    layers, since one layer's surface steps with the raster; not a number where none is read
    or where bone stands within MIDLINE_CLEAR_MM of the midline in one."""
    got = [m.chord(y, float(z)) for z in layers]
    walls = [c[0] for c in got if c is not None]
    if not walls or min(walls) < MIDLINE_CLEAR_MM:
        return NAN
    return float(np.median(walls))


def pedicle_rows(rows: List[dict], near: List[int], walls: Dict[int, float]) -> List[int]:
    """The isthmus rows less those that are not the pedicle's: a row whose wall is not read or
    stands more than CORNER_MM nearer the midline than the rows' median wall, the body's
    corner or the lamina, and a row whose width or height is further than OUTLIER_SHARE from
    the rest's medians, a cut through a process's edge; the rest where that would leave none."""
    kept = [i for i in near if np.isfinite(walls[i])]
    if not kept:
        return []
    wall = float(np.median([walls[i] for i in kept]))
    kept = [i for i in kept if walls[i] >= wall - CORNER_MM]
    w = float(np.median([rows[i]["w"] for i in kept]))
    h = float(np.median([rows[i]["h"] for i in kept]))
    typical = [i for i in kept
               if abs(rows[i]["w"] - w) <= OUTLIER_SHARE * w and abs(rows[i]["h"] - h) <= OUTLIER_SHARE * h]
    return typical or kept


def isthmus(rows: List[dict], v: Vertebra, m: SideMap) -> Optional[Tuple[int, List[int], Dict[int, float]]]:
    """The isthmus: on the profile of the sections' areas (width times height, the ellipse's
    up to a constant) smoothed over three rows (canal.smoothed_values), the least within the
    front FRONT_SHARE of the canal's depth and behind the row at the body's wall, and the rows
    about it within ISTHMUS_SHARE of it, less the rows that are not the pedicle's
    (pedicle_rows), with each row's medial wall; the row nearest the middle of those stands for
    the isthmus, since on a pedicle of even section the least is one row's noise. None with
    too few rows."""
    if len(rows) < 3:
        return None
    a = CANAL.smoothed_values(np.array([r["w"] * r["h"] for r in rows], float))
    depth = v.wall - v.wall_post
    front = [i for i, r in enumerate(rows)
             if 0.5 * v.pixel < v.wall - r["y"] <= FRONT_SHARE * depth and np.isfinite(a[i])]
    if not front:
        return None
    k = min(front, key=lambda i: a[i])
    lim = ISTHMUS_SHARE * a[k]
    lo = k
    while lo > 0 and a[lo - 1] <= lim:
        lo -= 1
    hi = k
    while hi + 1 < len(a) and a[hi + 1] <= lim:
        hi += 1
    about = list(range(lo, hi + 1))
    walls = {i: medial_wall(m, rows[i]["y"], layers_of(v, rows[i]["run"])) for i in about}
    near = pedicle_rows(rows, about, walls)
    if not near:
        return None
    mid = float(np.median([rows[i]["y"] for i in near]))
    return min(near, key=lambda i: abs(rows[i]["y"] - mid)), near, walls


# ---- the axis and the chord --------------------------------------------------------------------

def wall_line(rows: List[dict], near: List[int], walls: Dict[int, float]) -> np.ndarray:
    """The line (slope, intercept in y) through the isthmus rows' walls, or the flat line at
    their median where they are too few or too close for a slope."""
    ys = np.array([rows[i]["y"] for i in near])
    ws = np.array([walls[i] for i in near])
    if len(near) >= 3 and np.ptp(ys) >= AXIS_SPAN_MM:
        return np.polyfit(ys, ws, 1)
    return np.array([0.0, float(np.median(ws))])


def axis_rows(m: SideMap, rows: List[dict], near: List[int], k: int,
              walls: Dict[int, float]) -> Tuple[List[int], Dict[int, float]]:
    """The rows the axis is read across on, and their medial walls: the isthmus rows, each
    with its own wall, extended forward and back row by row while the next row's wall, read
    over the isthmus row's layers, lies within WALL_FIT_MM of the isthmus rows' line
    (wall_line) and stands no further in than CORNER_MM from their median, up to the body's
    posterolateral corner in front and the lamina or the articular process behind, where the
    wall steps off the line or juts in."""
    v = m.v
    taken = list(near)
    walls = dict(walls)
    line = wall_line(rows, near, walls)
    floor = float(np.median([walls[i] for i in near])) - CORNER_MM
    layers = layers_of(v, rows[k]["run"])
    for step in (-1, 1):
        i = (min(near) if step < 0 else max(near)) + step
        while 0 <= i < len(rows):
            wall = walls[i] if i in near else medial_wall(m, rows[i]["y"], layers)
            if not np.isfinite(wall) or wall < floor or abs(wall - np.polyval(line, rows[i]["y"])) > WALL_FIT_MM:
                break
            taken.append(i)
            walls[i] = wall
            i += step
    return sorted(taken), walls


def columns(m: SideMap, rows: List[dict], near: List[int], sec: float, hgt: float) -> np.ndarray:
    """The columns the pedicle's surfaces are read under: in each isthmus row, from the row's
    own wall out over the middle half of the isthmus's median section, sec, a pixel apart, those
    whose run through the row's middle is the pedicle's, within HEIGHT_SHARE of the isthmus's
    height, as (x, y, bottom, top); the others stand under the articular process or the body's
    corner, whose bone joins the pedicle's run. The median section and not the row's own is taken
    so that the columns and x' in lattice_under, which runs from the wall line out by half of sec,
    share one middle, and so that a row the cleaning kept at a quarter wider or narrower than the
    rest puts its columns where the others' are."""
    v = m.v
    out = []
    for i in near:
        r = rows[i]
        for u in np.arange(r["u0"] + 0.25 * sec, r["u0"] + 0.75 * sec + 1e-9, v.fx):
            x = m.x_of(float(u))
            run = height_run(v, x, r["y"], r["z"])
            if run is not None and abs((run[1] - run[0]) - hgt) <= HEIGHT_SHARE * hgt:
                out.append((x, r["y"], run[0], run[1]))
    return np.array(out, float).reshape(-1, 4)


def lattice_under(m: SideMap, cols: np.ndarray, line: np.ndarray, sec: float,
                  top: bool) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The scan's voxel centres under the columns within SURFACE_LAYERS of each column's own
    surface, the top or the bottom: their frame coordinates, their place across the section
    from its middle, and whether each is the vertebra's bone. A centre belongs to the nearest
    column, within half a pixel across and a quarter of a pixel front to back, the rows being
    half a pixel apart; a centre beyond the volume counts as air, as is_bone reads it."""
    v = m.v
    xs, ys = cols[:, 0], cols[:, 1]
    zs = cols[:, 3] if top else cols[:, 2]
    pad = (SURFACE_LAYERS + 1.0) * v.fz
    corners = np.array([[x, y, z] for x in (xs.min() - v.pixel, xs.max() + v.pixel)
                        for y in (ys.min() - v.pixel, ys.max() + v.pixel) for z in (zs.min() - pad, zs.max() + pad)])
    inv = np.linalg.inv(np.asarray(v.grid.affine, float))
    cijk = v.points_world(corners) @ inv[:3, :3].T + inv[:3, 3]
    lo, hi = np.floor(cijk.min(0)).astype(int) - 1, np.ceil(cijk.max(0)).astype(int) + 1
    ijk = np.stack(np.meshgrid(*[np.arange(lo[a], hi[a] + 1) for a in range(3)], indexing="ij"), -1).reshape(-1, 3)
    q = v.frame.local(v.grid.world(ijk.astype(float)))
    apart = np.maximum(np.abs(q[:, :1] - xs[None, :]) / (0.5 * v.pixel),
                       np.abs(q[:, 1:2] - ys[None, :]) / (0.25 * v.pixel + 1e-6))
    j = np.argmin(apart, axis=1)
    keep = (apart[np.arange(len(q)), j] <= 1.0) & (np.abs(q[:, 2] - zs[j]) <= SURFACE_LAYERS * v.fz)
    q, ijk = q[keep], ijk[keep]
    across = m.side * (q[:, 0] - v.midline) - (np.polyval(line, q[:, 1]) + 0.5 * sec)
    return q, across, v.is_bone(ijk)


def parting(y: np.ndarray, across: np.ndarray, z: np.ndarray, bone: np.ndarray, top: bool) -> Optional[dict]:
    """The surface z = a + b y + c x' + d x'^2 that parts the bone from the air with the widest
    margin, bone below it and air above for the top and the other way for the bottom, as a
    linear program over the margin; where no such surface parts them, the widest margin being
    negative, the surface with the least total crossing instead (a linear program over the
    crossings), and how many centres lie across it. Returns the coefficients of the surface
    taken, the widest-margin program's margin (negative where the coefficients are the
    least-crossing program's), the count of centres across, and the range of slopes b of every
    surface that parts the centres the surface taken parts (freedom), or None where the programs
    find no surface, as for a set whose bone and air are told apart without z. That range is
    what says whether the lattice pins the climb: where the layers cut the surface at several
    phases across the columns it is narrow; where the surface lies between two layers over the
    whole span, as on 2.5 mm slices whose layers run within about 20 degrees of it, every surface
    between them parts the lattice and the widest-margin one lies parallel to the layers, so its
    slope is the vertebra's tilt in the scanner, with a positive margin and nothing across."""
    F = np.column_stack([np.ones_like(y), y, across, across ** 2])
    sign = np.where(bone, -1.0, 1.0) if top else np.where(bone, 1.0, -1.0)
    n = len(y)
    res = linprog(c=[0.0, 0.0, 0.0, 0.0, -1.0], A_ub=np.column_stack([sign[:, None] * F, np.ones(n)]),
                  b_ub=sign * z, bounds=[(None, None)] * 5, method="highs")
    if not res.success:
        return None
    coef, margin = np.asarray(res.x[:4], float), float(res.x[4])
    parted = np.ones(n, bool)
    across_n = 0
    if margin < 0.0:
        res = linprog(c=np.concatenate([np.zeros(4), np.ones(n)]),
                      A_ub=np.column_stack([sign[:, None] * F, -np.eye(n)]), b_ub=sign * z,
                      bounds=[(None, None)] * 4 + [(0.0, None)] * n, method="highs")
        if not res.success:
            return None
        coef = np.asarray(res.x[:4], float)
        crossing = np.asarray(res.x[4:], float)
        parted = crossing <= 1e-9
        across_n = int((~parted).sum())
    return {"coefficients": coef, "margin": margin, "across": across_n,
            "freedom": slope_range(F[parted], sign[parted], z[parted])}


def slope_range(F: np.ndarray, sign: np.ndarray, z: np.ndarray) -> Tuple[float, float]:
    """The least and the greatest slope b of a surface that parts these centres, two linear
    programs over the same constraints as parting's with no margin; an end the lattice does not
    bound is infinite."""
    ends = []
    for c, unbounded in (([0.0, 1.0, 0.0, 0.0], -math.inf), ([0.0, -1.0, 0.0, 0.0], math.inf)):
        res = linprog(c=c, A_ub=sign[:, None] * F, b_ub=sign * z, bounds=[(None, None)] * 4, method="highs")
        ends.append(float(res.x[1]) if res.success else unbounded)
    return ends[0], ends[1]


def climb_angle(b: float) -> float:
    """The angle in degrees of a climb dz per mm of y, positive where the posterior end is
    higher, as the sagittal angle is read before the wall's tilt is taken off."""
    return -math.degrees(math.atan(b))


def climb(m: SideMap, rows: List[dict], near: List[int], walls: Dict[int, float], sec: float,
          hgt: float) -> Tuple[float, str, dict]:
    """The pedicle's climb front to back along its centre line, dz per mm of y, the mean of
    its top and bottom surfaces' (parting); NAN with a note where it is not read: fewer than
    MIN_COLUMNS columns, columns spanning less than SAGITTAL_SPAN_MM, fewer than MIN_PARTED
    centres of bone or of air about a surface, no surface found, a surface more of whose
    centres than VIOLATED_SHARE lie across the best one or whose worst centre lies further
    across than SURFACE_LAYERS layers (another structure's bone in the box, since a surface the
    layers cut at another phase is bracketed within a layer), a lattice that leaves the angle
    free over more than FREEDOM_DEG (the mean of the two surfaces' ranges, slope_range), or two
    surfaces whose climbs lie more than APART_DEG apart, since over the isthmus rows the
    pedicle's top and bottom run nearly parallel and two that do not have been read off
    different things. The record carries the columns, their span and each surface's
    coefficients, margin, counts and range, for the trace."""
    v = m.v
    cols = columns(m, rows, near, sec, hgt)
    record: dict = {"columns": cols, "span": float(np.ptp(cols[:, 1])) + 0.5 * v.pixel if len(cols) else 0.0}
    if len(cols) < MIN_COLUMNS:
        return NAN, "the pedicle's surfaces stand under %d columns, too few to part them from the lattice" % len(cols), record
    if record["span"] < SAGITTAL_SPAN_MM:
        return NAN, "the free pedicle spans %.1f mm front to back: its sagittal angle is not read" % record["span"], record
    line = wall_line(rows, near, walls)
    slopes, widths = [], []
    for top, name in ((True, "top"), (False, "bottom")):
        q, across, bone = lattice_under(m, cols, line, sec, top)
        n_bone, n_air = int(bone.sum()), int((~bone).sum())
        record[name] = {"bone": n_bone, "air": n_air}
        if min(n_bone, n_air) < MIN_PARTED:
            return NAN, ("the pedicle's %s surface has %d centres of bone and %d of air about it: not parted"
                         % (name, n_bone, n_air)), record
        got = parting(q[:, 1], across, q[:, 2], bone, top)
        if got is None:
            return NAN, "no surface parts the bone from the air about the pedicle's %s" % name, record
        record[name].update(got)
        if got["across"] > VIOLATED_SHARE * len(q):
            return NAN, ("the bone and the air about the pedicle's %s are not parted by one surface: %d of %d centres "
                         "lie across the best" % (name, got["across"], len(q))), record
        if got["margin"] < -SURFACE_LAYERS * v.fz:
            return NAN, ("a centre about the pedicle's %s lies %.1f mm across the surface that parts it best, more "
                         "than %.1f layers: another structure's bone stands there" % (name, -got["margin"], SURFACE_LAYERS)), record
        lo, hi = got["freedom"]
        widths.append(abs(climb_angle(lo) - climb_angle(hi)) if math.isfinite(lo) and math.isfinite(hi) else math.inf)
        slopes.append(float(got["coefficients"][1]))
    freedom = 0.5 * (widths[0] + widths[1])
    apart = abs(climb_angle(slopes[0]) - climb_angle(slopes[1]))
    record["freedom_deg"], record["apart_deg"] = freedom, apart
    if freedom > FREEDOM_DEG:
        return NAN, ("the lattice leaves the pedicle's climb free over %.0f degrees, more than %.0f: the layers do not "
                     "cut its surfaces at phases enough to pin it" % (freedom, FREEDOM_DEG)), record
    if apart > APART_DEG:
        return NAN, ("the pedicle's top climbs %.1f degrees and its bottom %.1f, more than %.0f apart: not read"
                     % (climb_angle(slopes[0]), climb_angle(slopes[1]), APART_DEG)), record
    return 0.5 * (slopes[0] + slopes[1]), "", record


def axis_from(rows: List[dict], taken: List[int], walls: Dict[int, float], rise: float,
              side: int) -> Tuple[np.ndarray, str, str]:
    """The axis pointing back through the rows taken: across, the walls' line; up, the climb
    where it was read (climb), else level. With it a note where the rows are too few for an
    axis, which is then taken front to back and stands for nothing measured, and which of its
    angles were read: "both", "transverse", or "neither"."""
    y = np.array([rows[i]["y"] for i in taken])
    if len(taken) < 3 or np.ptp(y) < AXIS_SPAN_MM:
        return np.array([0.0, -1.0, 0.0]), "the free pedicle is too short to give an axis: taken front to back", "neither"
    across = np.polyfit(y, side * np.array([walls[i] for i in taken]), 1)[0]
    d = np.array([across, 1.0, rise if np.isfinite(rise) else 0.0])
    return -d / np.linalg.norm(d), "", "both" if np.isfinite(rise) else "transverse"


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
    """dy/dz of the body's posterior wall (body.posterior_wall), so that the sagittal angle is
    taken against the plane square to the wall, as the end-plates' inclinations are, and not
    against the column's line, which leans against a vertebra where its neighbours slip; NAN
    where the wall is not read (wall_reading)."""
    return wall_reading(v)[0]


def wall_reading(v: Vertebra) -> Tuple[float, str]:
    """The posterior wall's dy/dz, read on the scan's lattice on the body's points and the middle
    of their x range, as body.inclinations reads it, so the vertebra keeps one reading for both
    sides, the end-plates and the spinous process; and why it is not read, empty where it is. The
    canal's line (anatomy.wall_slope), which the body's cut follows, still traces the lattice's
    staircase and is the next to read this way."""
    B = v.body_pts
    if len(B) < G.MIN_CHORD_POINTS:
        return NAN, "too few body points to read the posterior wall on"
    slope, info = BODY.posterior_wall(v, B, 0.5 * (B[:, 0].min() + B[:, 0].max()))
    return slope, info.get("why", "")


# ---- one side, both sides ----------------------------------------------------------------------

def nearest(rows: List[dict], chosen: List[int], value_of, target: float) -> int:
    """Of the chosen rows, the one whose value lies nearest the target."""
    return min(chosen, key=lambda i: abs(value_of(rows[i]) - target))


def one_side(v: Vertebra, side: int, zb: Tuple[float, float]) -> Tuple[Dict[str, float], str, Optional[dict]]:
    if v.level.startswith("C") and "body_foramina" in v.flags:
        return {}, ("the foramen transversarium is not closed in the mask, so the pedicle's lateral border is not "
                    "there: the pedicle is not read"), None
    m = SideMap(v, side)
    rows = profile(m, anchors(v, zb))
    got = isthmus(rows, v, m)
    if got is None:
        return {}, "no bone stands beside the canal in the rows through the pedicle", None
    k, near, walls = got
    sec = float(np.median([rows[i]["w"] for i in near]))
    hgt = float(np.median([rows[i]["h"] for i in near]))
    if sec > PEDICLE_MAX_MM.get(v.level[:1], 20.0):
        return {}, ("no row shows the pedicle free of what joins it laterally, the transverse process's root or "
                    "the lateral mass: its section reads %.0f mm" % sec), None
    taken, walls = axis_rows(m, rows, near, k, walls)
    rise, why, parted = climb(m, rows, near, walls, sec, hgt)
    d, note, reads = axis_from(rows, taken, walls, rise, side)
    wall, wall_why = wall_reading(v)
    if reads == "transverse":
        note = why
    elif reads == "both" and not math.isfinite(wall):
        note = "the body's posterior wall is not read (%s): the sagittal angle, taken against it, is not" % wall_why
    level = np.array([d[0], d[1], 0.0]) / np.linalg.norm(d[:2])
    # A column up the frame's z crosses the pedicle's elliptic cylinder on the slant of the axis's
    # elevation, so the height is the run times its cosine, hypot(d[0], d[1]) for the unit axis;
    # the sagittal angle, as Zindrick and the papers read it on a sagittal cut and as the phantom
    # draws it, is the climb in the sagittal projection, atan2(d[2], -d[1]), a little steeper
    # than the elevation where the pedicles converge (6.00 against 5.87 degrees at 12 degrees of
    # convergence, 15 against 13.1 at 30).
    pitch = math.hypot(d[0], d[1])
    width = sec * abs(level[1])
    height = hgt * (pitch if reads == "both" else 1.0)
    out = {"pedicle_w": width, "pedicle_h": height, "pedicle_area": math.pi * width * height / 4.0,
           "pedicle_angle_transverse": math.degrees(math.atan2(side * d[0], -d[1])),
           "pedicle_angle_sagittal": math.degrees(math.atan2(d[2], -d[1])) - math.degrees(math.atan(wall))}
    c0 = np.array([rows[k]["x"], rows[k]["y"], rows[k]["z"]])
    out["pedicle_chord"] = chord(v, c0, d)
    if reads != "both":
        out["pedicle_angle_sagittal"] = NAN
    if reads == "neither":
        out["pedicle_angle_transverse"] = out["pedicle_chord"] = NAN
    info = {"centre": c0, "axis": d, "eh": np.array([0.0, 0.0, 1.0]), "height": hgt, "rows": rows, "isthmus": k,
            "near": near, "taken": taken,
            "walls": walls, "parted": parted, "map": m,
            "width_row": nearest(rows, near, lambda r: r["w"], sec),
            "height_row": nearest(rows, near, lambda r: r["h"], hgt)}
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
    if "right" in info and "left" in info:
        info["band"] = canal_between(v, info["right"], info["left"])
    return out, flags, info


def band(info: Dict[str, dict]) -> Optional[dict]:
    """What canal.measures takes from the pedicles: the band between them (canal_between), or
    None where a pedicle was not found on both sides."""
    return info.get("band") if info else None


# ---- between the pedicles ----------------------------------------------------------------------

def gap_between(right: SideMap, left: SideMap, y: float, z: float) -> Tuple[float, float, float]:
    """The canal's width between the two sides' medial walls at (y, z), with the walls' x; not
    a number where a wall is not read on either side, or where bone stands within
    MIDLINE_CLEAR_MM of the midline on one, the body's wall or the lamina crossing it."""
    a, b = right.chord(y, z), left.chord(y, z)
    if a is None or b is None or a[0] < MIDLINE_CLEAR_MM or b[0] < MIDLINE_CLEAR_MM:
        return NAN, NAN, NAN
    return a[0] + b[0], left.x_of(b[0]), right.x_of(a[0])


def picked_layer(vals: np.ndarray, within: np.ndarray, pick) -> Optional[Tuple[float, int]]:
    """The value picked (nanmin or nanmax) over the layers `within` on the profile smoothed
    over three layers (canal.smoothed_values), and the layer of the three whose raw value it
    came from; None where none was read."""
    smooth = CANAL.smoothed_values(vals)
    held = np.where(within, smooth, NAN)
    if not np.isfinite(held).any():
        return None
    k = int(pick(held))
    near = [j for j in (k - 1, k, k + 1) if 0 <= j < len(vals) and np.isfinite(vals[j])]
    return float(smooth[k]), (min(near, key=lambda j: abs(vals[j] - smooth[k])) if near else k)


def least_gap(mr: SideMap, ml: SideMap, ys: List[float], z: float) -> Tuple[float, Optional[Tuple[float, float, float, float]]]:
    """The gap at a layer for the least distance: the median over the rows about the isthmus,
    since one row's walls step with the raster, and where the row nearest the median was read."""
    found = [(gap_between(mr, ml, y, z), y) for y in ys]
    found = [(g, y) for g, y in found if np.isfinite(g[0])]
    if not found:
        return NAN, None
    med = float(np.median([g[0] for g, _ in found]))
    (g, xl, xr), y = min(found, key=lambda t: abs(t[0][0] - med))
    return med, (y, z, xl, xr)


def widest_gap(mr: SideMap, ml: SideMap, ys: List[float], z: float) -> Tuple[float, Optional[Tuple[float, float, float, float]]]:
    """The gap at a layer for the greatest distance: the widest over the rows from the body's
    wall back to the isthmus, and where it was read."""
    found = [(gap_between(mr, ml, y, z), y) for y in ys]
    found = [(g, y) for g, y in found if np.isfinite(g[0])]
    if not found:
        return NAN, None
    (g, xl, xr), y = max(found, key=lambda t: t[0][0])
    return g, (y, z, xl, xr)


def canal_between(v: Vertebra, right: dict, left: dict) -> dict:
    """The interpedicular distance, least and greatest, between the two sides' walls over the
    layers of the central half of the pedicles' height, where the walls bulge furthest into
    the canal and above and below which the body's posterolateral corner or the articular
    process stands in a wall's place (at study 0004's T8 the layers below the pedicles read
    the body's corners 2 mm nearer the midline); with where each was read for the drawing:
    (y, z, left wall x, right wall x). A layer counts in the band when its slab, half a layer
    either way, reaches into it."""
    mr, ml = right["map"], left["map"]
    yc = 0.5 * (right["centre"][1] + left["centre"][1])
    zc = 0.5 * (right["centre"][2] + left["centre"][2])
    h = 0.5 * (right["height"] + left["height"])
    n = int(math.ceil(0.25 * h / v.fz)) + 2
    zs = zc + v.fz * np.arange(-n, n + 1)
    central = np.abs(zs - zc) <= 0.25 * h + 0.5 * v.fz
    out = {"zc": zc, "h": h, "yc": yc, "interpedicular": NAN, "interpedicular_max": NAN}
    about = [float(y) for y in row_places(v) if abs(y - yc) <= 1.5 * v.pixel]
    least = [least_gap(mr, ml, about, float(z)) for z in zs]
    got = picked_layer(np.array([g for g, _ in least], float), central, np.nanargmin)
    if got is not None:
        out["interpedicular"], j = got
        out["interpedicular_at"] = least[j][1]
    front = [float(y) for y in row_places(v) if y >= yc - 0.5 * v.pixel]
    widest = [widest_gap(mr, ml, front, float(z)) for z in zs]
    got = picked_layer(np.array([g for g, _ in widest], float), central, np.nanargmax)
    if got is not None:
        out["interpedicular_max"], j = got
        out["interpedicular_max_at"] = widest[j][1]
    return out
