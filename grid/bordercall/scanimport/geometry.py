"""Panjabi's chords on a labelled vertebra, measured in the vertebra's own frame.

Panjabi measured named chords on dry bone (archive/bordercall/reference/papers/): the widths and
depths of the end-plates, the posterior height of the body, the width and depth of the canal. A
label volume gives each vertebra as a set of voxels. This file turns the voxels into those
chords, and into two more kept for the record only (the transverse span and a spinous length,
__init__.py says why they are never set beside Panjabi).

THE FRAME IS THE VERTEBRA'S, NOT THE SCANNER'S. The archive's spineps_map.py takes extents along
the volume's own axes, which is right only where the spine runs straight along the scanner's
long axis; a lordotic L5 or a kyphotic T8 is tilted 10 to 30 degrees, and an extent along a
tilted axis mixes width with height. Here every vertebra gets three axes: z first along the
column, through the centroids of the vertebrae above and below, then refined to the direction
along which the body is thinnest (its end-plates' rims lying across it), so a neighbour's turn
or slip does not tilt it; y from the canal toward the body, anterior; x completing a
right-handed frame. Every chord is taken in that frame from the voxels' world positions (the
volume's affine), so the spacing and the orientation of the volume enter only through the
affine.

THE BODY IS WHAT LIES IN FRONT OF THE CANAL. A whole-vertebra label (VerSe, TotalSegmentator,
MOOSE) does not separate the body from the arch. The canal does, with no threshold to tune: in a
slab across the column at the level of the pedicles the arch closes round the canal, so the
canal is the hole in the slab's cross-section, and its anterior wall is the posterior wall of
the body (the same boundary archive/bordercall/measure_levels.py uses). The body is the largest
connected part of the vertebra in front of that wall. Where SPINEPS's subregion labels exist the
body and the canal are labelled and are read directly.

WHAT EACH CHORD IS.
- endplate, endplate_depth (EPWu, EPDu): the width along x, and the depth along y from the
  body's posterior wall, of the body's top slab, the uppermost 12 per cent of its height (1 to
  3 mm, never thinner than one voxel), with the superior end-plate label joined to it where
  SPINEPS gives one.
- endplate_lower, endplate_lower_depth (EPWl, EPDl): the same at the bottom slab.
- h_post (VBHp): the median height along z of the body's columns in its posterior fifth and its
  central half across, the height at the posterior wall and not the tallest column anywhere,
  which in a wedged body is somewhere else (spineps_map.py makes the same point).
- canal_w, canal_ap (SCW, SCD): in each slab across the middle half of the body's height where
  the canal is found, the distance between the walls round it, across through its middle and
  front to back at its midline; the median over those slabs.
- tp_span, spinous_length (record only): the extent along x of the whole vertebra or of SPINEPS's
  costal labels; and from the canal's posterior wall at the midline to the farthest voxel behind
  it within 10 mm of the midline (or of the spinous label), a straight line in three dimensions.

WHERE A SURFACE LIES. A label holds the voxels whose centres fall inside the bone, so the bone's
surface lies beyond the outermost centre by up to the spacing of the centres along the chord.
Along an axis of the volume's grid the centres stack at the spacing and the surface lies half a
spacing out; along an axis oblique to the grid the projected centres crowd together and it lies
closer. `surface` reads that spacing from the distinct positions next to the end (edge_gap), so
the chords hold to about half a millimetre on tilted synthetic spines and to about one voxel's
shadow in the worst case (scanimport/tests/test_geometry.py). A chord whose voxels touch the
edge of the volume is not taken (the vertebra is cut by the field of view), and neither is one
whose voxels are too few to define it; each is NaN with its reason in the flags.

Whether these chords equal Panjabi's on real bone is a question of measurement, not of code:
`python -m scanimport compare` sets every chord taken on an import beside Panjabi's mean and
spread level by level, and that comparison comes before any naming result is believed.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy import ndimage

NAN = float("nan")
MIN_BODY_VOXELS = 40
MIN_CHORD_POINTS = 8
# This module's choice, with no source: a hole smaller than 12 mm2 (about 4 by 3 mm, far below the
# narrowest canal of Panjabi's means) or larger than 1,200 mm2 is not a canal; the mask-free mode
# takes the lower bound and a tighter upper one (intensity.py, step 2).
CANAL_AREA_MM2 = (12.0, 1200.0)
# The end-plate's slab: 12 per cent of the body's height, held to 1 to 3 mm, this module's choice.
# The share is the same as the band of 12 per cent of the body's height at its lower edge that
# Radimsky's public code takes on a 2D mask's contour (masks_corners_magnification.md, section 3),
# which the note itself finds sensitive to osteophytes; no source sets a slab for a 3D chord, and
# the report's row C16 calls these chord definitions conventional, with Panjabi's own not retrieved.
ENDPLATE_SHARE, ENDPLATE_MM = 0.12, (1.0, 3.0)
POSTERIOR_SHARE = 0.20
MIDLINE_MM = 10.0
AXIS_SEARCH_DEG = 20.0
CORE_SHARE = 0.5                       # the central half across, for the axis and the end-plates' level
BAND_LAYERS = 2.0                      # a turn of the axis under this many layers across the core is not told from them
TURNS = 4                              # at most this many turns of the frame toward the body


@dataclass
class VoxelGrid:
    """A volume's geometry: its affine, the unit vectors of its axes in world space and their
    spacing in millimetres, and its shape."""
    affine: np.ndarray
    shape: Tuple[int, int, int]

    @property
    def axes(self) -> np.ndarray:
        """Columns are the unit directions of the array axes in world space."""
        a = np.asarray(self.affine, float)[:3, :3]
        return a / np.linalg.norm(a, axis=0)

    @property
    def spacing(self) -> np.ndarray:
        return np.linalg.norm(np.asarray(self.affine, float)[:3, :3], axis=0)

    def world(self, idx: np.ndarray) -> np.ndarray:
        a = np.asarray(self.affine, float)
        return idx @ a[:3, :3].T + a[:3, 3]

    def footprint(self, e: np.ndarray) -> float:
        """The length of one voxel's shadow on the unit direction e."""
        return float(np.sum(np.abs(self.axes.T @ e) * self.spacing))

    def anterior(self) -> np.ndarray:
        """The world's anterior direction: +y in the RAS world a NIfTI affine maps into."""
        return np.array([0.0, 1.0, 0.0])

    def superior(self) -> np.ndarray:
        return np.array([0.0, 0.0, 1.0])


@dataclass
class Frame:
    origin: np.ndarray
    ex: np.ndarray
    ey: np.ndarray
    ez: np.ndarray

    def local(self, pts: np.ndarray) -> np.ndarray:
        d = pts - self.origin
        return np.stack([d @ self.ex, d @ self.ey, d @ self.ez], axis=1)

    def turned_toward(self, d: np.ndarray) -> "Frame":
        """The same frame turned about z so that y points along d, given in this frame's (x, y)."""
        ey = unit(d[0] * self.ex + d[1] * self.ey)
        return Frame(self.origin, unit(np.cross(ey, self.ez)), ey, self.ez)


def unit(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    if n < 1e-12:
        raise ValueError("a zero vector has no direction")
    return np.asarray(v, float) / n


def frame_from(origin: np.ndarray, ez: np.ndarray, toward_anterior: np.ndarray) -> Frame:
    """A right-handed frame with z along ez and y as close to toward_anterior as z allows."""
    ez = unit(ez)
    ey = toward_anterior - (toward_anterior @ ez) * ez
    if np.linalg.norm(ey) < 1e-6:                       # the column runs front to back: any y will do
        ey = np.cross(ez, [1.0, 0.0, 0.0])
    ey = unit(ey)
    ex = np.cross(ey, ez)
    return Frame(np.asarray(origin, float), unit(ex), ey, ez)


def column_axes(centroids: Sequence[np.ndarray], superior: np.ndarray) -> List[np.ndarray]:
    """The column's direction at each vertebra, given the centroids top down: through the
    neighbours above and below, or the one neighbour at an end, pointing up; the world's
    superior direction where a vertebra has no neighbour."""
    out = []
    k = len(centroids)
    for i in range(k):
        above = centroids[i - 1] if i > 0 else None
        below = centroids[i + 1] if i + 1 < k else None
        if above is not None and below is not None:
            d = above - below
        elif above is not None:
            d = above - centroids[i]
        elif below is not None:
            d = centroids[i] - below
        else:
            d = superior
        d = unit(d)
        out.append(d if d @ superior >= 0 else -d)
    return out


# ---- the canal as a hole ------------------------------------------------------------------------

@dataclass
class Section:
    """One slab across the column: where it sits along z, its points in the frame's (x, y), and
    the canal found in it, if any: the hole's pixel centres (a whole-vertebra label) or the canal
    label's own points."""
    w: float
    pts: np.ndarray
    canal: Optional[np.ndarray]
    area: float
    as_hole: bool


def raster(xy: np.ndarray, pixel: float) -> Tuple[np.ndarray, np.ndarray]:
    """Points in a plane on a padded boolean grid, and the grid's origin (the corner of pixel
    (0, 0)), so a hole touching nothing but the padding is still a hole."""
    lo = xy.min(0)
    ij = np.floor((xy - lo) / pixel).astype(int) + 1
    grid = np.zeros(tuple(ij.max(0) + 2), bool)
    grid[ij[:, 0], ij[:, 1]] = True
    return grid, lo - pixel


def holes(grid: np.ndarray) -> np.ndarray:
    """The enclosed background of a cross-section after closing one-pixel gaps between voxel
    centres: the pixels a fill would add."""
    closed = ndimage.binary_closing(grid, structure=np.ones((3, 3), bool), border_value=0)
    return ndimage.binary_fill_holes(closed) & ~closed


def largest_hole(grid: np.ndarray, origin: np.ndarray, pixel: float) -> Tuple[Optional[np.ndarray], float]:
    """The largest hole whose area is a canal's, as pixel centres in the plane, and its area."""
    h = holes(grid)
    lab, n = ndimage.label(h)
    if n == 0:
        return None, 0.0
    counts = np.bincount(lab.ravel())[1:]
    best = int(np.argmax(counts)) + 1
    area = float(counts[best - 1]) * pixel * pixel
    if not (CANAL_AREA_MM2[0] <= area <= CANAL_AREA_MM2[1]):
        return None, 0.0
    ij = np.argwhere(lab == best)
    return origin + (ij + 0.5) * pixel, area


def sections(local: np.ndarray, slab: float, pixel: float, as_hole: bool) -> List[Section]:
    """Slabs of thickness `slab` along z through the points; in each, the canal found as the
    largest hole of the cross-section (as_hole) or as the points themselves (a canal label)."""
    out = []
    w0, w1 = float(local[:, 2].min()), float(local[:, 2].max())
    for w in np.arange(w0 + 0.5 * slab, w1 - 0.5 * slab + 1e-9, slab):
        sel = np.abs(local[:, 2] - w) <= 0.5 * slab
        if sel.sum() < MIN_CHORD_POINTS:
            continue
        xy = local[sel, :2]
        if as_hole:
            grid, origin = raster(xy, pixel)
            canal, area = largest_hole(grid, origin, pixel)
        else:
            canal, area = xy, float(len(xy))
        out.append(Section(w=float(w), pts=xy, canal=canal, area=area, as_hole=as_hole))
    return out


# ---- where a surface lies between voxel centres -------------------------------------------------

def edge_gap(values: np.ndarray, top: bool, cap: float) -> float:
    """The spacing of the positions next to one end of voxel centres projected on an axis. On
    an axis along the volume's grid the centres stack in layers one spacing apart; on an axis
    turned a little off it each layer spreads into a cluster, and the outermost points of two
    neighbouring clusters are still a spacing apart; on an axis well off it the positions spread
    evenly and the spacing shrinks. So the distinct positions within 2.5 voxel shadows of the end
    are split into clusters wherever two are more than a tenth of a shadow apart. Where the empty
    step after the outermost cluster is at least as wide as that cluster, the positions are
    layers and the spacing is the distance from the end to the outermost point of the next layer
    in; where the clusters are wider than the steps between them, it is the median of those
    steps; where there is one cluster, it is their mean step. Choosing the tail by position, not by a count, keeps a
    broad face whose outer layer alone holds many positions from reading as one dense cluster.
    The surface lies about half this spacing beyond the outermost centre."""
    u = np.unique(np.round(values, 4))
    if len(u) < 2:
        return cap
    tail = u[u >= u[-1] - 2.5 * cap][::-1] if top else u[u <= u[0] + 2.5 * cap]
    steps = np.abs(np.diff(tail))
    if not len(steps):
        return cap
    breaks = np.flatnonzero(steps > 0.1 * cap)
    if len(breaks) and steps[breaks[0]] >= abs(tail[breaks[0]] - tail[0]):
        gap = float(abs(tail[breaks[0] + 1] - tail[0]))        # layers: end to the next layer's end
    elif len(breaks):
        gap = float(np.median(steps[breaks]))                   # clusters wider than their gaps
    else:
        gap = float(steps.mean())                               # an even spread
    return min(gap, cap)


def surface(values: np.ndarray, top: bool, cap: float) -> float:
    """Where the surface beyond the outermost voxel centre lies, on the side `top` names."""
    if top:
        return float(values.max() + 0.5 * edge_gap(values, True, cap))
    return float(values.min() - 0.5 * edge_gap(values, False, cap))


def extent(values: np.ndarray, foot: float) -> float:
    """The length of a set of voxels along an axis, surface to surface; `foot`, one voxel's
    shadow on the axis, bounds the half-gaps."""
    if len(values) < MIN_CHORD_POINTS:
        return NAN
    return surface(values, True, foot) - surface(values, False, foot)


# ---- the canal ----------------------------------------------------------------------------------

def canal_walls(s: Section, pixel: float, fx: float, fy: float) -> Optional[Tuple[float, ...]]:
    """One slab's canal: its width, its depth at the midline, its anterior and posterior walls
    and its midline. From a hole, the walls are the surfaces of the solid around it, read in a
    band through the hole's middle; from a canal label, the surfaces of the label itself."""
    c = s.canal
    xm = 0.5 * (c[:, 0].min() + c[:, 0].max())
    ym = 0.5 * (c[:, 1].min() + c[:, 1].max())
    band = 0.75 * pixel
    if s.as_hole:
        p = s.pts
        down = p[np.abs(p[:, 0] - xm) <= band]
        across = p[np.abs(p[:, 1] - ym) <= band]
        ant, post = down[down[:, 1] > ym, 1], down[down[:, 1] < ym, 1]
        right, left = across[across[:, 0] > xm, 0], across[across[:, 0] < xm, 0]
        if min(len(ant), len(post), len(right), len(left)) == 0:
            return None
        wa, wp = surface(ant, False, fy), surface(post, True, fy)
        w = surface(right, False, fx) - surface(left, True, fx)
    else:
        down = c[np.abs(c[:, 0] - xm) <= band]
        across = c[np.abs(c[:, 1] - ym) <= band]
        if len(down) < 2 or len(across) < 2:
            return None
        wa, wp = surface(down[:, 1], True, fy), surface(down[:, 1], False, fy)
        w = surface(across[:, 0], True, fx) - surface(across[:, 0], False, fx)
    return w, wa - wp, wa, wp, xm, s.w


def canal_chords(secs: List[Section], pixel: float, band: Tuple[float, float], fx: float, fy: float) -> Dict[str, float]:
    """Width and midline depth of the canal, the median over the slabs within `band` along z
    where a canal was found, and its anterior and posterior walls at the midline."""
    rows = []
    for s in secs:
        if s.canal is None or not (band[0] <= s.w <= band[1]):
            continue
        got = canal_walls(s, pixel, fx, fy)
        if got is not None:
            rows.append(got)
    if not rows:
        return {}
    med = np.median(np.array(rows), axis=0)
    return {"canal_w": float(med[0]), "canal_ap": float(med[1]), "wall_anterior": float(med[2]),
            "wall_posterior": float(med[3]), "midline_x": float(med[4]), "slabs": int(len(rows)),
            "w_mid": float(med[5])}


# ---- the chords of the body ---------------------------------------------------------------------

def body_chords(body: np.ndarray, wall: float, grid: VoxelGrid, frame: Frame,
                sup_label: Optional[np.ndarray] = None, inf_label: Optional[np.ndarray] = None) -> Dict[str, float]:
    """The five chords of the body from its points in the frame (x, y, z), the posterior wall at
    y = wall; the end-plate labels, where given, joined to the top and bottom slabs."""
    fx, fy, fz = grid.footprint(frame.ex), grid.footprint(frame.ey), grid.footprint(frame.ez)
    out: Dict[str, float] = {}
    if len(body) < MIN_BODY_VOXELS:
        return {k: NAN for k in ("endplate", "endplate_depth", "endplate_lower", "endplate_lower_depth", "h_post")}
    # the body's height from its central part, so a spur or an uncinate process at the rim does
    # not set the end-plates' thickness
    core = body[central(body[:, 0], body[:, 1])]
    core = core if len(core) >= MIN_CHORD_POINTS else body
    height = float(core[:, 2].max() - core[:, 2].min()) + fz
    t = min(max(ENDPLATE_SHARE * height, ENDPLATE_MM[0]), ENDPLATE_MM[1])
    t = max(t, fz)
    # each end-plate is the slab within t of the plane resting on the highest (or lowest) points
    # of the body's central part, cell by cell across the column (plate). A slab at one level
    # holds only part of a plate tilted against the frame by more than t over the body's width,
    # which the frame kept inside refine_axis's quantization band can be; the plane follows the
    # plate where its tilt can be told from the voxel layers and is level where it cannot, and
    # resting it on the central part keeps a spur or an uncinate process at the rim from lifting
    # it. An end-plate label on thick slices is a layer thinner than one voxel's shadow, which
    # samples the rim too sparsely to reach its widest point, so the label is added to the slab,
    # not put in its place
    inner = central(body[:, 0], body[:, 1])
    top, bot = plate(body, inner, max(fx, fy), t, True, fz), plate(body, inner, max(fx, fy), t, False, fz)
    if sup_label is not None and len(sup_label):
        top = np.concatenate([top, sup_label])
    if inf_label is not None and len(inf_label):
        bot = np.concatenate([bot, inf_label])
    for name, slab in (("endplate", top), ("endplate_lower", bot)):
        out[name] = extent(slab[:, 0], fx)
        out[name + "_depth"] = surface(slab[:, 1], True, fy) - wall if len(slab) >= MIN_CHORD_POINTS else NAN
    depth = surface(body[:, 1], True, fy) - wall
    width = extent(body[:, 0], fx)
    xm = 0.5 * (body[:, 0].min() + body[:, 0].max())
    post = body[(body[:, 1] <= wall + POSTERIOR_SHARE * depth) & (np.abs(body[:, 0] - xm) <= 0.25 * width)]
    out["h_post"] = column_height(post, max(fx, fy), fz)
    return out


def cells(pts: np.ndarray, pixel: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The points grouped by cells of a grid across the column: the order that groups them, and
    where each cell's run starts and ends in it."""
    ij = np.floor((pts[:, :2] - pts[:, :2].min(0)) / pixel).astype(int)
    key = ij[:, 0] * (ij[:, 1].max() + 1) + ij[:, 1]
    order = np.argsort(key, kind="stable")
    key = key[order]
    starts = np.flatnonzero(np.r_[True, key[1:] != key[:-1]])
    return order, starts, np.r_[starts[1:], len(key)]


def plate_plane(pts: np.ndarray, inner: np.ndarray, pixel: float, top: bool, layer: float) -> np.ndarray:
    """The plane z = c0 + c1 x + c2 y resting on the highest (top) or lowest points of the inner
    points' cells, as (c0, c1, c2). Each cell gives one point, its mean position across and its
    extreme height. Voxel centres stack in layers about `layer` apart along z, so on a plate
    oblique to the layers the cells' extremes form a staircase whose treads fall short of the
    plate by up to one layer while the steps' outer edges touch it. A least-squares plane runs
    through the staircase's middle and tilts with it; the plane that rests on the extremes from
    outside and lies nearest them on average (envelope) runs through the edges, and so along the
    plate, once there are edges on both sides of the middle. Where the plane's rise across the
    cells is under two layers the staircase has too few steps to tell a tilt from the layers, as
    for the axis (refine_axis), and the plane is level through the outermost extreme; so it is
    with fewer than six cells."""
    core = pts[inner] if inner.sum() >= MIN_CHORD_POINTS else pts
    order, starts, ends = cells(core, pixel)
    z, xy = core[order, 2], core[order, :2]
    ext = np.array([[*xy[a:b].mean(0), z[a:b].max() if top else z[a:b].min()] for a, b in zip(starts, ends)])
    c = envelope(ext, top, layer) if len(ext) >= 6 else None
    if c is not None and max(abs(c[1]) * np.ptp(ext[:, 0]), abs(c[2]) * np.ptp(ext[:, 1])) < 2.0 * layer:
        c = None
    if c is None:
        c = np.array([ext[:, 2].max() if top else ext[:, 2].min(), 0.0, 0.0])
    return c


def plate(pts: np.ndarray, inner: np.ndarray, pixel: float, t: float, top: bool, layer: float) -> np.ndarray:
    """The points within t of the end-plate's plane (plate_plane), and beyond it; the slab is
    never thinner than one layer, so it holds the lowest tread of the staircase."""
    c = plate_plane(pts, inner, pixel, top, layer)
    t = max(t, layer)
    d = pts[:, 2] - (c[0] + c[1] * pts[:, 0] + c[2] * pts[:, 1])
    return pts[d >= -t - 1e-6] if top else pts[d <= t + 1e-6]


def envelope(ext: np.ndarray, top: bool, layer: float) -> Optional[np.ndarray]:
    """The plane z = c0 + c1 x + c2 y resting on the points `ext` from above (top) or below with
    the least mean distance to them, or None when the programme finds none."""
    from scipy.optimize import linprog
    sign = 1.0 if top else -1.0
    A = np.column_stack([np.ones(len(ext)), ext[:, 0], ext[:, 1]])
    ls = np.linalg.lstsq(A, ext[:, 2], rcond=None)[0]
    keep = sign * (ext[:, 2] - A @ ls) <= 1.5 * layer
    if keep.sum() < 6:
        return None
    A, zk = A[keep], ext[keep, 2]
    # minimise the mean of sign * (plane - z) subject to sign * (plane - z) >= 0 at every point
    got = linprog(sign * A.mean(0), A_ub=-sign * A, b_ub=-sign * zk, bounds=[(None, None)] * 3, method="highs")
    return got.x if got.status == 0 else None


def column_height(pts: np.ndarray, pixel: float, fz: float) -> float:
    """The median, over the cells of a grid across the column, of the height along z of the
    points in each cell, surface to surface: each end lies half the spacing of the centres next
    to it beyond the outermost centre (surface), which on an oblique grid is less than half of
    one voxel's shadow."""
    if len(pts) < MIN_CHORD_POINTS:
        return NAN
    order, starts, ends = cells(pts, pixel)
    z = pts[order, 2]
    hs = [surface(z[a:b], True, fz) - surface(z[a:b], False, fz) for a, b in zip(starts, ends) if b - a >= 2]
    return float(np.median(hs)) if hs else NAN


# ---- one vertebra -------------------------------------------------------------------------------

@dataclass
class Measured:
    values: Dict[str, float]
    flags: Dict[str, str] = field(default_factory=dict)
    frame: Optional[Frame] = None


def largest_component(mask: np.ndarray) -> np.ndarray:
    lab, n = ndimage.label(mask)
    if n <= 1:
        return mask
    counts = np.bincount(lab.ravel())[1:]
    return lab == (int(np.argmax(counts)) + 1)


def tilted(ez: np.ndarray, a: float, b: float) -> np.ndarray:
    """ez tilted by angles a and b (radians) about two axes across it."""
    e1 = unit(np.cross(ez, [1.0, 0.0, 0.0]) if abs(ez[0]) < 0.9 else np.cross(ez, [0.0, 1.0, 0.0]))
    e2 = np.cross(ez, e1)
    return unit(ez + math.tan(a) * e1 + math.tan(b) * e2)


def thickness(pts: np.ndarray, n: np.ndarray) -> float:
    h = pts @ n
    lo, hi = np.percentile(h, [0.5, 99.5])
    return float(hi - lo)


def span_along(pts: np.ndarray, n: np.ndarray) -> float:
    """The full extent of points along n. The core it is taken on has no rim, so no percentile
    trim is needed, and a trim would cut the core's corners, whose share shrinks as n tilts, and
    so make a tilted direction look thinner than the axis."""
    h = pts @ n
    return float(h.max() - h.min())


def central(a: np.ndarray, b: np.ndarray, share: float = CORE_SHARE) -> np.ndarray:
    """Which points, given by two positions across the column, lie within CORE_SHARE of the
    body's middle once each position is scaled by the body's half-width along it (from the 2nd
    to the 98th percentile). The rim, where uncinate processes rise at C3 to C7 and osteophytes
    grow, is left out, so neither tilts the axis nor lifts an end-plate."""
    (a0, a1), (b0, b1) = np.percentile(a, [2, 98]), np.percentile(b, [2, 98])
    ha, hb = max(0.5 * (a1 - a0), 1e-6), max(0.5 * (b1 - b0), 1e-6)
    return ((a - 0.5 * (a0 + a1)) / ha) ** 2 + ((b - 0.5 * (b0 + b1)) / hb) ** 2 <= share ** 2


def core_of(body: np.ndarray, ez: np.ndarray) -> np.ndarray:
    """The body's central part across ez (world points)."""
    e1 = unit(np.cross(ez, [1.0, 0.0, 0.0]) if abs(ez[0]) < 0.9 else np.cross(ez, [0.0, 1.0, 0.0]))
    e2 = np.cross(ez, e1)
    return body[central(body @ e1, body @ e2)]


def refine_axis(body: np.ndarray, ez: np.ndarray, grid: Optional["VoxelGrid"] = None) -> np.ndarray:
    """The body's own axis: the direction, within AXIS_SEARCH_DEG of the column's, along which the
    central part of the body (core_of) is thinnest, its two end-plates lying across it. A body is
    a short cylinder, and its thickness along a direction tilted by t from its axis grows as its
    width times t, so the thinnest direction is the axis even where a neighbour's turn or slip
    tilts the line through the neighbours. A wedged body gives the direction between its two
    end-plates'.

    Voxel centres sit on the scan's layers, so along a direction near the layers' normal their
    spread can fall short of the true thickness by up to one voxel's shadow there, and along the
    axis by about as much; a turn smaller than the angle at which the core's width rises by two
    shadows cannot be told from that quantization, and the column's axis through the neighbours
    is kept instead (with 3 mm slices and a 22 mm core, about 15 degrees; with 1 mm voxels,
    about 5). The end-plates are then read on planes resting on the body (plate_plane), which
    follow a plate the kept axis leaves off by more than the layers hide. The cost is a body tilted
    against the line through its neighbours by less than the band on thick slices, a wedge or a
    slip at a junction: it is measured in its neighbours' frame, its end-plate slabs cut its
    plates obliquely, and nothing flags it. On the phantom with 0.7 by 0.7 by 3 mm voxels a body
    bent 10 degrees sideways reads its end-plate widths 16.5 and 15.8 mm short, and bent 10
    degrees forward its end-plate depths 7.5 and 2.3 mm short (tests/test_geometry.py,
    KnownFailure). The angle between the kept axis and the thinnest direction cannot flag it:
    it is 10.5 degrees on that sideways bend and up to 14 degrees on straight phantoms with 5 mm
    slices, each inside the band its slices cannot resolve. On 1 mm voxels an 8 degree sideways
    bend is within the bounds of tests/test_geometry.py (0.46 mm with whole-vertebra labels,
    0.63 mm with SPINEPS subregions)."""
    core = core_of(body, ez) if len(body) >= MIN_BODY_VOXELS else body
    if len(core) < MIN_BODY_VOXELS:
        return ez
    best = (span_along(core, ez), 0.0, 0.0)
    for step, span in ((2.5, AXIS_SEARCH_DEG), (0.5, 2.5)):
        a0, b0 = best[1], best[2]
        grid_deg = np.radians(np.arange(-span, span + 1e-9, step))
        for a in grid_deg:
            for b in grid_deg:
                t = span_along(core, tilted(ez, a0 + a, b0 + b))
                if t < best[0] - 1e-9:
                    best = (t, a0 + a, b0 + b)
    found = tilted(ez, best[1], best[2])
    if grid is not None:
        width = float(np.ptp(core @ unit(np.cross(ez, grid.anterior()) if abs(ez @ grid.anterior()) < 0.99
                                       else np.cross(ez, [1.0, 0.0, 0.0]))))
        resolvable = math.atan2(BAND_LAYERS * grid.footprint(ez), max(width, 1e-6))
        if math.acos(min(1.0, abs(float(found @ ez)))) < resolvable:
            return ez
    return found


def measure_whole(idx: np.ndarray, grid: VoxelGrid, ez: np.ndarray, touching: np.ndarray) -> Measured:
    """The chords of one vertebra given as whole-vertebra voxels (indices into the volume), the
    column's direction at it, and which voxels touch the volume's edge."""
    flags: Dict[str, str] = {}
    pts = grid.world(idx.astype(float))
    frame = frame_from(pts.mean(0), ez, grid.anterior())
    fz = grid.footprint(frame.ez)
    pixel = max(grid.footprint(frame.ex), grid.footprint(frame.ey))
    loc = frame.local(pts)
    secs = sections(loc, fz, pixel, as_hole=True)
    found = [s for s in secs if s.canal is not None]
    if not found:
        return Measured({k: NAN for k in ("endplate", "endplate_depth", "endplate_lower", "endplate_lower_depth",
                                          "h_post", "canal_w", "canal_ap", "tp_span", "spinous_length")},
                        {"all": "no canal: the arch never closes round a hole in any slab"}, frame)
    # turn y to point from the canal toward the body. Of what lies beyond the canal's two walls,
    # in front of its anterior wall and behind its posterior wall, the body's side is the larger
    # in every region (behind lie only the laminae and the spinous process), so the turn does not
    # depend on the patient lying supine. The first turn slices a vertebra turned about its own
    # axis obliquely, so a pedicle can join the body; each further turn aims at the centroid of
    # the body found in the last frame, and stops once the turn is under half a degree
    big = max(found, key=lambda s: s.area)
    cc = big.canal.mean(0)
    front = loc[loc[:, 1] > big.canal[:, 1].max()]
    back = loc[loc[:, 1] < big.canal[:, 1].min()]
    side = front if len(front) >= len(back) else back
    if len(side) < MIN_BODY_VOXELS:
        return chords_from(loc, idx, grid, frame, secs, touching, flags)
    frame = frame.turned_toward(side[:, :2].mean(0) - cc)
    for _ in range(TURNS):
        loc = frame.local(pts)
        secs = sections(loc, fz, pixel, as_hole=True)
        found = [s for s in secs if s.canal is not None]
        if not found:
            break
        wall = float(np.median([s.canal[:, 1].max() for s in found]))
        cc = np.median([s.canal.mean(0) for s in found], axis=0)
        body = loc[connected_front(idx, loc, wall, grid.shape)]
        if len(body) < MIN_BODY_VOXELS:
            break
        d = body[:, :2].mean(0) - cc
        if abs(math.degrees(math.atan2(d[0], d[1]))) < 0.5:
            break
        frame = frame.turned_toward(d)
    loc = frame.local(pts)
    found = [s for s in sections(loc, fz, pixel, as_hole=True) if s.canal is not None]
    if found:
        wall = float(np.median([s.canal[:, 1].max() for s in found]))
        body = pts[connected_front(idx, loc, wall, grid.shape)]
        frame = frame_from(frame.origin, refine_axis(body, frame.ez, grid), frame.ey)
        fz = grid.footprint(frame.ez)
        loc = frame.local(pts)
    secs = sections(loc, fz, pixel, as_hole=True)
    return chords_from(loc, idx, grid, frame, secs, touching, flags)


def chords_from(loc: np.ndarray, idx: np.ndarray, grid: VoxelGrid, frame: Frame, secs: List[Section],
                touching: np.ndarray, flags: Dict[str, str]) -> Measured:
    pixel = max(grid.footprint(frame.ex), grid.footprint(frame.ey))
    found = [s for s in secs if s.canal is not None]
    if not found:
        flags["all"] = "no canal after turning the frame"
        return Measured({k: NAN for k in ("endplate", "endplate_depth", "endplate_lower", "endplate_lower_depth",
                                          "h_post", "canal_w", "canal_ap", "tp_span", "spinous_length")}, flags, frame)
    fx, fy = grid.footprint(frame.ex), grid.footprint(frame.ey)
    first = canal_chords(secs, pixel, (-np.inf, np.inf), fx, fy)
    if not first:
        flags["all"] = "a hole was found but no wall around it could be read"
        return Measured({k: NAN for k in ("endplate", "endplate_depth", "endplate_lower", "endplate_lower_depth",
                                          "h_post", "canal_w", "canal_ap", "tp_span", "spinous_length")}, flags, frame)
    body_sel = connected_front(idx, loc, first["wall_anterior"], grid.shape)
    body = loc[body_sel]
    if len(body) >= MIN_BODY_VOXELS:
        z0, z1 = float(body[:, 2].min()), float(body[:, 2].max())
        band = (z0 + 0.25 * (z1 - z0), z1 - 0.25 * (z1 - z0))
    else:
        band = (-np.inf, np.inf)
    canal = canal_chords(secs, pixel, band, fx, fy) or first
    vals = body_chords(body, canal["wall_anterior"], grid, frame)
    if touching[body_sel].any():
        for k in ("endplate", "endplate_depth", "endplate_lower", "endplate_lower_depth", "h_post"):
            vals[k] = NAN
        flags["body"] = "the body touches the edge of the volume"
    vals["canal_w"], vals["canal_ap"] = canal["canal_w"], canal["canal_ap"]
    vals["tp_span"] = NAN if touching.any() else extent(loc[:, 0], grid.footprint(frame.ex))
    if touching.any():
        flags["tp_span"] = "the vertebra touches the edge of the volume"
    vals["spinous_length"] = spinous(loc, canal, touching)
    if not np.isfinite(vals["spinous_length"]):
        flags.setdefault("spinous_length", "no posterior midline voxels, or the vertebra is cut")
    return Measured(vals, flags, frame)


def connected_front(idx: np.ndarray, loc: np.ndarray, wall: float, shape) -> np.ndarray:
    """Which voxels are the body: in front of the posterior wall, and in the largest connected
    part of what is (so a transverse process that reaches forward is not counted as body)."""
    front = loc[:, 1] > wall
    if front.sum() == 0:
        return front
    sub = idx[front]
    lo = sub.min(0)
    box = np.zeros(tuple(sub.max(0) - lo + 1), bool)
    box[tuple((sub - lo).T)] = True
    keep = largest_component(box)
    out = np.zeros(len(idx), bool)
    out[np.flatnonzero(front)[keep[tuple((sub - lo).T)]]] = True
    return out


def spinous(loc: np.ndarray, canal: Dict[str, float], touching: np.ndarray) -> float:
    if not canal or touching.any():
        return NAN
    back = loc[(loc[:, 1] < canal["wall_posterior"]) & (np.abs(loc[:, 0] - canal["midline_x"]) <= MIDLINE_MM)]
    if len(back) < MIN_CHORD_POINTS:
        return NAN
    start = np.array([canal["midline_x"], canal["wall_posterior"], canal["w_mid"]])
    return float(np.sqrt(((back - start) ** 2).sum(1)).max())


def measure_labelled(idx: np.ndarray, sub: np.ndarray, canal_idx: np.ndarray, grid: VoxelGrid, ez: np.ndarray,
                     touching: np.ndarray, labels) -> Measured:
    """The chords of one vertebra with SPINEPS's subregions: idx its voxels, sub their subregion
    labels, canal_idx the voxels of the canal label near it; `labels` the subregion ids
    (schemes.SUB_*)."""
    flags: Dict[str, str] = {}
    pts = grid.world(idx.astype(float))
    is_body = np.isin(sub, labels["body"])
    if is_body.sum() >= MIN_BODY_VOXELS:
        ez = refine_axis(pts[is_body], ez, grid)
    frame = frame_from(pts.mean(0), ez, grid.anterior())
    fz = grid.footprint(frame.ez)
    pixel = max(grid.footprint(frame.ex), grid.footprint(frame.ey))
    loc = frame.local(pts)
    cpts = grid.world(canal_idx.astype(float)) if len(canal_idx) else np.zeros((0, 3))
    if is_body.sum() < MIN_BODY_VOXELS or len(cpts) < MIN_CHORD_POINTS:
        flags["all"] = "too few body or canal voxels in the subregion labels"
        return Measured({k: NAN for k in ("endplate", "endplate_depth", "endplate_lower", "endplate_lower_depth",
                                          "h_post", "canal_w", "canal_ap", "tp_span", "spinous_length")}, flags, frame)
    cl = frame.local(cpts)
    keep = (cl[:, 2] >= loc[:, 2].min()) & (cl[:, 2] <= loc[:, 2].max()) & (np.abs(cl[:, 0]) <= 40.0)
    cl = cl[keep]
    if len(cl) >= MIN_CHORD_POINTS:
        frame = frame.turned_toward(loc[is_body, :2].mean(0) - cl[:, :2].mean(0))
        loc, cl = frame.local(pts), frame.local(cpts[keep])
    body = loc[is_body]
    z0, z1 = float(body[:, 2].min()), float(body[:, 2].max())
    band = (z0 + 0.25 * (z1 - z0), z1 - 0.25 * (z1 - z0))
    fx, fy = grid.footprint(frame.ex), grid.footprint(frame.ey)
    canal = canal_chords(sections(cl, fz, pixel, as_hole=False), pixel, band, fx, fy) if len(cl) >= MIN_CHORD_POINTS else {}
    wall = canal.get("wall_anterior", float(body[:, 1].min()) - 0.5 * grid.footprint(frame.ey))
    sup = loc[sub == labels["endplate_sup"]]
    inf = loc[sub == labels["endplate_inf"]]
    vals = body_chords(body, wall, grid, frame, sup, inf)
    if touching[is_body].any():
        for k in ("endplate", "endplate_depth", "endplate_lower", "endplate_lower_depth", "h_post"):
            vals[k] = NAN
        flags["body"] = "the body touches the edge of the volume"
    vals["canal_w"], vals["canal_ap"] = canal.get("canal_w", NAN), canal.get("canal_ap", NAN)
    costal = np.isin(sub, labels["costal"])
    span_pts = loc[costal] if costal.sum() >= MIN_CHORD_POINTS else loc
    span_touch = touching[costal] if costal.sum() >= MIN_CHORD_POINTS else touching
    vals["tp_span"] = NAN if span_touch.any() else extent(span_pts[:, 0], grid.footprint(frame.ex))
    spin = sub == labels["spinous"]
    if canal and spin.sum() >= MIN_CHORD_POINTS and not touching[spin].any():
        start = np.array([canal["midline_x"], canal["wall_posterior"], canal["w_mid"]])
        vals["spinous_length"] = float(np.sqrt(((loc[spin] - start) ** 2).sum(1)).max())
    else:
        vals["spinous_length"] = spinous(loc, canal, touching)
    return Measured(vals, flags, frame)
