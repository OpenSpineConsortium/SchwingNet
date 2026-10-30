"""The oracle: per vertebra of a labelled volume, every measurement with the points that make it.

The auto-anatomist learns from an oracle, deterministic code that measures a vertebra on its mask.
The owner's premise of 29 October 2026 is that one exists for any spine and can draw how each
measurement is made; this file says what it must return, so that any implementation, the stand-in
here or the real extractors the thread "Extract morphometrics from gold tier 3 CT" builds, plugs
into the rest of the package unchanged:

- read(labels, affine, names, sub) takes a label volume, its affine into the RAS world in
  millimetres, which value names which level, and SPINEPS's subregion volume where there is one;
- it returns one Reading per named level, top down: the level, its label value, the vertebra's
  own frame, the centre a crop is taken about, and a Measurement per key, every key, its value
  NaN with the reason where the level is not measured (C1, C2, the sacrum) or the mask too small;
- a Measurement holds the value, the points it is taken between (specs.py names them, world
  millimetres), the voxels that set it for drawing, and, where the value is NaN or the points
  could not be given, why.

`check` holds a reading to the rules the rest relies on: each value is its spec's rule applied
to its points, each chord runs along its spec's axis with its named ends the right way round,
points and value are given together or withheld with a reason, and the frame is right-handed.

THE STAND-IN, ChordOracle, is scanimport.geometry, bordercall's own chord code, unchanged: its
values are what geometry.measure_whole and measure_labelled return, the same numbers the import
pipeline writes (scanimport/volume.py, measure_volume, whose per-vertebra preparation this file
repeats: the column's axis through the neighbours' centroids, the voxels touching the volume's
edge). geometry.py returns the values and the frame and not where its chords lie, so the points
are re-derived here with geometry.py's own functions on the same inputs in the same frame, and
each re-derived value is compared with geometry.py's: where the two differ by more than 1e-9 the
value is kept and the points are withheld with the reason, so a change to geometry.py that this
file does not follow withholds a line rather than drawing a wrong one. Every value is a chord
along one axis of the frame, a difference of two surface positions, so its two points share the
other two coordinates and their distance is the value; for a median over slabs or cells (h_post,
canal_w, canal_ap) the line is drawn at the median position with the median length.

What it does not do, so nobody believes more of it: it measures the seven chords and the two
record-only ones, no pedicle, angle or area; it reads whole-vertebra labels with the canal as a
hole, or SPINEPS's subregions, as geometry.py does, with geometry.py's limits (its docstring and
refine_axis's: a body tilted against its neighbours on thick slices is measured in their frame).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol, Sequence, Tuple

import numpy as np

from scanimport import LEVELS as SCAN_LEVELS, NOT_MEASURED, schemes
from scanimport import geometry as G
from scanimport import volume as V

from . import specs

NAN = float("nan")
AGREE = 1e-9                  # how near a re-derived value must be to geometry.py's for its points to be given
FRAME_ATOL = 1e-6             # how far a frame's axes may be from orthonormal (a float32 frame is off by up to about 1e-7)
WITNESS_MAX = 1500            # at most this many voxels kept per measurement for drawing
BODY_KEYS = ("endplate", "endplate_depth", "endplate_lower", "endplate_lower_depth", "h_post")


@dataclass
class Measurement:
    key: str
    value: float
    points: Dict[str, np.ndarray]
    flag: str = ""
    witness: Optional[np.ndarray] = None

    @property
    def taken(self) -> bool:
        return bool(np.isfinite(self.value))

    @property
    def drawn(self) -> bool:
        """Every point its spec names is there and finite; a measurement with no points is not
        drawn, whatever its value."""
        wanted = specs.SPECS[self.key].points if self.key in specs.SPECS else tuple(self.points)
        return bool(wanted) and all(p in self.points and bool(np.all(np.isfinite(self.points[p]))) for p in wanted)

    def array(self) -> np.ndarray:
        """The points in the spec's order, (n, 3)."""
        return np.array([self.points[p] for p in specs.SPECS[self.key].points], float)


@dataclass
class Frame:
    """A vertebra's frame in the world: an origin and three orthonormal axes, x to the patient's
    right, y anterior, z up the column (geometry.Frame's, kept apart so a reading carries no
    geometry.py object)."""
    origin: np.ndarray
    ex: np.ndarray
    ey: np.ndarray
    ez: np.ndarray

    @property
    def axes(self) -> np.ndarray:
        """The axes as columns, (3, 3): world = origin + axes @ local."""
        return np.column_stack([self.ex, self.ey, self.ez])

    def world(self, local: np.ndarray) -> np.ndarray:
        return np.asarray(local, float) @ self.axes.T + self.origin

    def local(self, world: np.ndarray) -> np.ndarray:
        return (np.asarray(world, float) - self.origin) @ self.axes


@dataclass
class Reading:
    level: str
    label: int
    frame: Frame
    centre: np.ndarray
    measurements: Dict[str, Measurement] = field(default_factory=dict)
    flags: Dict[str, str] = field(default_factory=dict)
    voxels: int = 0

    def values(self, keys: Sequence[str]) -> np.ndarray:
        return np.array([self.measurements[k].value if k in self.measurements else NAN for k in keys], float)

    def landmarks(self, keys: Sequence[str]) -> np.ndarray:
        """The points of the keys' measurements in specs.landmarks' order, (K, 3) world mm, NaN
        where a measurement was not taken or its points were withheld."""
        out = []
        for name in specs.landmarks(keys):
            key = name.split(".")[0]
            m = self.measurements.get(key)
            out.append(m.points[name] if m is not None and m.taken else np.full(3, NAN))
        return np.array(out, float)


class Oracle(Protocol):
    """What the auto-anatomist needs of any oracle."""
    keys: Sequence[str]

    def read(self, labels: np.ndarray, affine: np.ndarray, names: Dict[int, str],
             sub: Optional[np.ndarray] = None) -> List[Reading]:
        ...


def chord_sign(spec: specs.Spec) -> int:
    """Which way a chord's second point lies from its first along its axis: -1 where the first
    point is the right, anterior or superior end, the larger coordinate, else +1."""
    first = spec.points[0].split(".")[-1]
    return -1 if first in ("right", "anterior", "superior") else 1


def chord_problems(reading: Reading, k: str, spec: specs.Spec, P: np.ndarray) -> List[str]:
    """In words, where a chord's line in the frame disagrees with its spec: it runs mostly along
    another axis, or its named ends are the wrong way round."""
    if not spec.axis or spec.kind != "length":
        return []
    d = reading.frame.local(P[1][None])[0] - reading.frame.local(P[0][None])[0]
    i, along = "xyz".index(spec.axis), int(np.argmax(np.abs(d)))
    if along != i:
        return ["%s %s: the line runs along %s, not its axis %s" % (reading.level, k, "xyz"[along], spec.axis)]
    if d[i] * chord_sign(spec) < 0:
        return ["%s %s: the ends %s and %s are the wrong way round" % (reading.level, k, spec.points[0], spec.points[1])]
    return []


def check(reading: Reading, atol: float = 1e-6, keys: Optional[Sequence[str]] = None) -> List[str]:
    """In words, where a reading breaks the interface: a key it was to carry and does not (keys,
    the oracle's), a point missing from a measurement, points given in part, a value NaN beside
    points given, a value that is not its spec's rule applied to its points, a chord that does not
    run along its spec's axis or whose named ends are the wrong way round, points withheld or a
    value not taken with no reason, a frame that is not orthonormal (within FRAME_ATOL) or is
    left-handed."""
    out = []
    A = reading.frame.axes
    if not np.allclose(A.T @ A, np.eye(3), rtol=0.0, atol=FRAME_ATOL):
        out.append("%s: the frame's axes are not orthonormal" % reading.level)
    elif np.linalg.det(A) < 0:
        out.append("%s: the frame is left-handed; x is cross(y, z)" % reading.level)
    for k in keys or ():
        if k not in reading.measurements:
            out.append("%s: no measurement %s" % (reading.level, k))
    for k, m in reading.measurements.items():
        spec = specs.SPECS[k]
        if m.key != k:
            out.append("%s: the measurement under %s says it is %s" % (reading.level, k, m.key))
        missing = [p for p in spec.points if p not in m.points]
        if missing:
            out.append("%s %s: no point %s" % (reading.level, k, missing))
            continue
        given = [bool(np.all(np.isfinite(m.points[p]))) for p in spec.points]
        if any(given) and not all(given):
            out.append("%s %s: points given in part" % (reading.level, k))
        elif m.drawn and not m.taken:
            out.append("%s %s: the value is NaN though its points are given" % (reading.level, k))
        elif m.taken and m.drawn:
            P = m.array()
            got = float(spec.value(P))
            if not abs(got - m.value) <= atol:
                out.append("%s %s: the value %.9f is not its points' %.9f" % (reading.level, k, m.value, got))
            out += chord_problems(reading, k, spec, P)
        elif m.taken and not m.flag:
            out.append("%s %s: points withheld with no reason" % (reading.level, k))
        elif not m.taken and not m.flag:
            out.append("%s %s: not taken with no reason" % (reading.level, k))
    return out


# ---- the stand-in over scanimport.geometry ------------------------------------------------------

def frame_of(f: G.Frame) -> Frame:
    return Frame(np.asarray(f.origin, float), np.asarray(f.ex, float), np.asarray(f.ey, float),
                 np.asarray(f.ez, float))


def thin(pts: np.ndarray) -> np.ndarray:
    """At most WITNESS_MAX of the points, every k-th, so a drawing is deterministic and light."""
    if len(pts) <= WITNESS_MAX:
        return pts
    return pts[:: int(math.ceil(len(pts) / WITNESS_MAX))]


def body_traces(body: np.ndarray, wall: float, grid: G.VoxelGrid, frame: G.Frame,
                sup: Optional[np.ndarray] = None, inf: Optional[np.ndarray] = None) -> Dict[str, tuple]:
    """geometry.body_chords' five chords with where they lie: for each, (value, first point,
    second point, the voxels that set it), all in the frame's local coordinates. The steps are
    body_chords' own, in its order, on its inputs."""
    fx, fy, fz = grid.footprint(frame.ex), grid.footprint(frame.ey), grid.footprint(frame.ez)
    out: Dict[str, tuple] = {}
    if len(body) < G.MIN_BODY_VOXELS:
        return out
    core = body[G.central(body[:, 0], body[:, 1])]
    core = core if len(core) >= G.MIN_CHORD_POINTS else body
    height = float(core[:, 2].max() - core[:, 2].min()) + fz
    t = min(max(G.ENDPLATE_SHARE * height, G.ENDPLATE_MM[0]), G.ENDPLATE_MM[1])
    t = max(t, fz)
    inner = G.central(body[:, 0], body[:, 1])
    pixel = max(fx, fy)
    top, bot = G.plate(body, inner, pixel, t, True, fz), G.plate(body, inner, pixel, t, False, fz)
    if sup is not None and len(sup):
        top = np.concatenate([top, sup])
    if inf is not None and len(inf):
        bot = np.concatenate([bot, inf])
    for name, slab in (("endplate", top), ("endplate_lower", bot)):
        if len(slab) < G.MIN_CHORD_POINTS:
            continue
        right, left = G.surface(slab[:, 0], True, fx), G.surface(slab[:, 0], False, fx)
        yc, zc = float(np.median(slab[:, 1])), float(np.median(slab[:, 2]))
        out[name] = (right - left, [right, yc, zc], [left, yc, zc], slab)
        front = G.surface(slab[:, 1], True, fy)
        xc = 0.5 * (float(slab[:, 0].min()) + float(slab[:, 0].max()))
        out[name + "_depth"] = (front - wall, [xc, wall, zc], [xc, front, zc], slab)
    depth = G.surface(body[:, 1], True, fy) - wall
    width = G.extent(body[:, 0], fx)
    xm = 0.5 * (body[:, 0].min() + body[:, 0].max())
    post = body[(body[:, 1] <= wall + G.POSTERIOR_SHARE * depth) & (np.abs(body[:, 0] - xm) <= 0.25 * width)]
    h = G.column_height(post, pixel, fz)
    if np.isfinite(h):
        order, starts, ends = G.cells(post, pixel)
        z = post[order, 2]
        mids = [0.5 * (G.surface(z[a:b], True, fz) + G.surface(z[a:b], False, fz))
                for a, b in zip(starts, ends) if b - a >= 2]
        zc, xc, yc = float(np.median(mids)), float(post[:, 0].mean()), float(post[:, 1].mean())
        out["h_post"] = (h, [xc, yc, zc + 0.5 * h], [xc, yc, zc - 0.5 * h], post)
    return out


def canal_traces(canal: Dict[str, float]) -> Dict[str, tuple]:
    """The canal's two chords, each drawn through the canal's centre at its median slab: the
    width across, right end first, and the depth front to back, posterior end first."""
    if not canal:
        return {}
    xc, yc, zc = canal["midline_x"], 0.5 * (canal["wall_anterior"] + canal["wall_posterior"]), canal["w_mid"]
    w, d = canal["canal_w"], canal["canal_ap"]
    return {"canal_w": (w, [xc + 0.5 * w, yc, zc], [xc - 0.5 * w, yc, zc], None),
            "canal_ap": (d, [xc, yc - 0.5 * d, zc], [xc, yc + 0.5 * d, zc], None)}


def span_trace(pts: np.ndarray, foot: float) -> Optional[tuple]:
    """The transverse span, geometry.extent of the points' x, drawn at the median height and
    depth of the points within 5 mm of either end."""
    if len(pts) < G.MIN_CHORD_POINTS:
        return None
    right, left = G.surface(pts[:, 0], True, foot), G.surface(pts[:, 0], False, foot)
    x = pts[:, 0]
    tips = pts[(x >= x.max() - 5.0) | (x <= x.min() + 5.0)]
    yc, zc = float(np.median(tips[:, 1])), float(np.median(tips[:, 2]))
    return right - left, [right, yc, zc], [left, yc, zc], tips


def spinous_trace(back: np.ndarray, canal: Dict[str, float]) -> Optional[tuple]:
    """geometry.spinous's chord: from the canal's posterior wall at the midline, half way up, to
    the farthest of the points behind it."""
    if not canal or len(back) < G.MIN_CHORD_POINTS:
        return None
    start = np.array([canal["midline_x"], canal["wall_posterior"], canal["w_mid"]])
    r = np.sqrt(((back - start) ** 2).sum(1))
    i = int(np.argmax(r))
    return float(r[i]), start, back[i], back


def whole_traces(idx: np.ndarray, grid: G.VoxelGrid, ez: np.ndarray, touching: np.ndarray,
                 m: G.Measured) -> Tuple[Dict[str, tuple], Dict[str, float]]:
    """Where measure_whole's chords lie, re-derived as geometry.chords_from takes them in the
    frame measure_whole ended in: the sections at the first frame's pixel and the last frame's
    footprint along z, as measure_whole hands them to chords_from. Also the canal's walls."""
    pts = grid.world(idx.astype(float))
    first_frame = G.frame_from(pts.mean(0), ez, grid.anterior())
    pixel0 = max(grid.footprint(first_frame.ex), grid.footprint(first_frame.ey))
    frame = m.frame
    fz = grid.footprint(frame.ez)
    loc = frame.local(pts)
    secs = G.sections(loc, fz, pixel0, as_hole=True)
    if not any(s.canal is not None for s in secs):
        return {}, {}
    pixel = max(grid.footprint(frame.ex), grid.footprint(frame.ey))
    fx, fy = grid.footprint(frame.ex), grid.footprint(frame.ey)
    first = G.canal_chords(secs, pixel, (-np.inf, np.inf), fx, fy)
    if not first:
        return {}, {}
    body_sel = G.connected_front(idx, loc, first["wall_anterior"], grid.shape)
    body = loc[body_sel]
    if len(body) >= G.MIN_BODY_VOXELS:
        z0, z1 = float(body[:, 2].min()), float(body[:, 2].max())
        band = (z0 + 0.25 * (z1 - z0), z1 - 0.25 * (z1 - z0))
    else:
        band = (-np.inf, np.inf)
    canal = G.canal_chords(secs, pixel, band, fx, fy) or first
    out = body_traces(body, canal["wall_anterior"], grid, frame)
    if touching[body_sel].any():
        out = {k: v for k, v in out.items() if k not in BODY_KEYS}
    out.update(canal_traces(canal))
    if not touching.any():
        got = span_trace(loc, fx)
        if got is not None:
            out["tp_span"] = got
        back = loc[(loc[:, 1] < canal["wall_posterior"]) & (np.abs(loc[:, 0] - canal["midline_x"]) <= G.MIDLINE_MM)]
        got = spinous_trace(back, canal)
        if got is not None:
            out["spinous_length"] = got
    return out, canal


def labelled_traces(idx: np.ndarray, sub: np.ndarray, canal_idx: np.ndarray, grid: G.VoxelGrid, ez: np.ndarray,
                    touching: np.ndarray, labels: dict, m: G.Measured) -> Tuple[Dict[str, tuple], Dict[str, float]]:
    """Where measure_labelled's chords lie, re-derived by its own steps: the axis refined on the
    body's subregion (geometry.refine_axis is deterministic, so the same inputs give the same
    axis to the bit), the frame turned toward the body from the canal label, the canal's
    sections from the canal label at the unturned frame's pixel, the end-plate labels joined."""
    pts = grid.world(idx.astype(float))
    is_body = np.isin(sub, labels["body"])
    if is_body.sum() >= G.MIN_BODY_VOXELS:
        ez = G.refine_axis(pts[is_body], ez, grid)
    frame = G.frame_from(pts.mean(0), ez, grid.anterior())
    fz = grid.footprint(frame.ez)
    pixel = max(grid.footprint(frame.ex), grid.footprint(frame.ey))
    loc = frame.local(pts)
    cpts = grid.world(canal_idx.astype(float)) if len(canal_idx) else np.zeros((0, 3))
    if is_body.sum() < G.MIN_BODY_VOXELS or len(cpts) < G.MIN_CHORD_POINTS:
        return {}, {}
    cl = frame.local(cpts)
    keep = (cl[:, 2] >= loc[:, 2].min()) & (cl[:, 2] <= loc[:, 2].max()) & (np.abs(cl[:, 0]) <= 40.0)
    cl = cl[keep]
    if len(cl) >= G.MIN_CHORD_POINTS:
        frame = frame.turned_toward(loc[is_body, :2].mean(0) - cl[:, :2].mean(0))
        loc, cl = frame.local(pts), frame.local(cpts[keep])
    body = loc[is_body]
    z0, z1 = float(body[:, 2].min()), float(body[:, 2].max())
    band = (z0 + 0.25 * (z1 - z0), z1 - 0.25 * (z1 - z0))
    fx, fy = grid.footprint(frame.ex), grid.footprint(frame.ey)
    canal = (G.canal_chords(G.sections(cl, fz, pixel, as_hole=False), pixel, band, fx, fy)
             if len(cl) >= G.MIN_CHORD_POINTS else {})
    wall = canal.get("wall_anterior", float(body[:, 1].min()) - 0.5 * grid.footprint(frame.ey))
    out = body_traces(body, wall, grid, frame, loc[sub == labels["endplate_sup"]], loc[sub == labels["endplate_inf"]])
    if touching[is_body].any():
        out = {k: v for k, v in out.items() if k not in BODY_KEYS}
    out.update(canal_traces(canal))
    costal = np.isin(sub, labels["costal"])
    span_pts = loc[costal] if costal.sum() >= G.MIN_CHORD_POINTS else loc
    span_touch = touching[costal] if costal.sum() >= G.MIN_CHORD_POINTS else touching
    if not span_touch.any():
        got = span_trace(span_pts, fx)
        if got is not None:
            out["tp_span"] = got
    spin = sub == labels["spinous"]
    if canal and spin.sum() >= G.MIN_CHORD_POINTS and not touching[spin].any():
        got = spinous_trace(loc[spin], canal)
    elif canal and not touching.any():
        got = spinous_trace(loc[(loc[:, 1] < canal["wall_posterior"])
                                & (np.abs(loc[:, 0] - canal["midline_x"]) <= G.MIDLINE_MM)], canal)
    else:
        got = None
    if got is not None:
        out["spinous_length"] = got
    return out, canal


SUBREGIONS = {"body": schemes.SUB_BODY, "endplate_sup": schemes.SUB_ENDPLATE_SUP,
              "endplate_inf": schemes.SUB_ENDPLATE_INF, "costal": (schemes.SUB_COSTAL_L, schemes.SUB_COSTAL_R),
              "spinous": schemes.SUB_SPINOSUS}


class ChordOracle:
    """The stand-in oracle over scanimport.geometry (the module's docstring)."""

    def __init__(self, keys: Sequence[str] = tuple(specs.SEVEN + specs.EXTRA)):
        specs.select(keys)
        self.keys = list(keys)

    def read(self, labels: np.ndarray, affine: np.ndarray, names: Dict[int, str],
             sub: Optional[np.ndarray] = None) -> List[Reading]:
        labels = np.asarray(labels)
        grid = G.VoxelGrid(np.asarray(affine, float), labels.shape)
        vox = V.vertebra_voxels(labels, names)
        order = [lv for lv in SCAN_LEVELS if lv in vox]
        value_of = {lv: v for v, lv in names.items()}
        cents = [grid.world(vox[lv].astype(float)).mean(0) for lv in order]
        axes = G.column_axes(cents, grid.superior())
        canal_idx = np.argwhere(sub == schemes.SUB_CANAL) if sub is not None else None
        return [self.read_one(lv, value_of.get(lv, -1), vox[lv], grid, ez, c, labels.shape, sub, canal_idx)
                for lv, ez, c in zip(order, axes, cents)]

    def read_one(self, level: str, label: int, idx: np.ndarray, grid: G.VoxelGrid, ez: np.ndarray,
                 centroid: np.ndarray, shape, sub: Optional[np.ndarray], canal_idx) -> Reading:
        plain = frame_of(G.frame_from(centroid, ez, grid.anterior()))
        reading = Reading(level=level, label=int(label), frame=plain, centre=np.asarray(centroid, float),
                          voxels=int(len(idx)))
        if level in NOT_MEASURED:
            reading.flags["all"] = "named, not measured: the rule's column starts at C3 and the sacrum carries no row"
            for k in self.keys:
                reading.measurements[k] = missing(k, reading.flags["all"])
            return reading
        if len(idx) < G.MIN_BODY_VOXELS:
            reading.flags["all"] = "only %d voxels" % len(idx)
            for k in self.keys:
                reading.measurements[k] = missing(k, reading.flags["all"])
            return reading
        touch = V.touching_edge(idx, shape)
        if sub is not None:
            m = G.measure_labelled(idx, sub[tuple(idx.T)], canal_idx, grid, ez, touch, SUBREGIONS)
            traces, canal = labelled_traces(idx, sub[tuple(idx.T)], canal_idx, grid, ez, touch, SUBREGIONS, m)
        else:
            m = G.measure_whole(idx, grid, ez, touch)
            traces, canal = whole_traces(idx, grid, ez, touch, m) if m.frame is not None else ({}, {})
        frame = frame_of(m.frame) if m.frame is not None else plain
        reading.frame, reading.flags = frame, dict(m.flags)
        if canal:
            reading.centre = frame.world(np.array([canal["midline_x"],
                                                   0.5 * (canal["wall_anterior"] + canal["wall_posterior"]),
                                                   canal["w_mid"]]))
        for k in self.keys:
            reading.measurements[k] = measurement(k, float(m.values.get(k, NAN)), traces.get(k), frame, m.flags)
        return reading


def missing(key: str, why: str) -> Measurement:
    return Measurement(key, NAN, {p: np.full(3, NAN) for p in specs.SPECS[key].points}, why)


def measurement(key: str, value: float, trace: Optional[tuple], frame: Frame, flags: Dict[str, str]) -> Measurement:
    """geometry.py's value with the trace's points, or the value with its points withheld and why."""
    if not np.isfinite(value):
        return missing(key, flags.get(key, flags.get("all", flags.get("body", "not taken"))))
    names = specs.SPECS[key].points
    if trace is None:
        out = missing(key, "the value was taken but where it lies could not be re-derived")
        out.value = value
        return out
    got, a, b, voxels = trace
    if not abs(float(got) - value) <= AGREE:
        out = missing(key, "the re-derived value %.9f is not geometry.py's %.9f; the points are withheld" % (got, value))
        out.value = value
        return out
    pa, pb = frame.world(np.asarray(a, float)), frame.world(np.asarray(b, float))
    witness = frame.world(thin(np.asarray(voxels, float))) if voxels is not None and len(voxels) else None
    return Measurement(key, value, {names[0]: pa, names[1]: pb}, "", witness)


def names_of(labels: np.ndarray, scheme: str) -> Dict[int, str]:
    """Which value names which level under one of scanimport's schemes, for the values present."""
    present = np.unique(np.asarray(labels)[np.asarray(labels) > 0])
    out = {int(v): schemes.level_of(scheme, int(v)) for v in present}
    return {v: n for v, n in out.items() if n}
