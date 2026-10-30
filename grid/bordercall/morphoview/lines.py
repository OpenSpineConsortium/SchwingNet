"""The measures as lines with two ends, built again from the measuring modules' own functions.

Every builder takes a vertebra as morphometry.anatomy.build left it and returns Lines whose ends
are world points in millimetres; `checked` sets each line's value beside the measured one and
withholds what differs. The ends are taken where the measure takes them: a height between its two
plates' band surfaces (body.heights), a width between the surfaces scanimport.geometry.surface
reads beyond the outermost voxel centres, a depth from the canal's wall line (anatomy.square_to_wall)
to the body's front, a chord where the march along the pedicle's axis enters and leaves the bone.
A measure that is a median over rows, cells or sections (rule "median") is drawn in the one
nearest the median, with the median as its value, so its drawn length need not equal it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from morphometry import anatomy as A
from morphometry import body as BODY
from morphometry import canal as CANAL
from morphometry import column as COL
from morphometry import pedicle as PED
from scanimport import geometry as G

NAN = float("nan")
AGREE = 1e-6                    # a line's value may differ from the measured one by this share of it
ROWS_PLACES = 4                 # morphometry's rows.csv writes each value to this many decimals

# what each line's two ends are, a first and b second, in the frame of the vertebra it is drawn in
# (a disc's, the vertebra below); x runs to the patient's right, y from the canal to the body, z up
ENDS: Dict[str, Tuple[str, str]] = {
    **{k: ("inferior", "superior") for k in ("h_ant", "h_post_inset", "h_mid", "h_post", "disc_h_ant",
                                             "disc_h_mid", "disc_h_post")},
    **{k: ("posterior", "anterior") for k in ("wedge", "body_d_mid", "endplate_depth", "endplate_lower_depth",
                                              "canal_ap_min", "canal_ap", "canal_ap_lateral_film")},
    **{k: ("left", "right") for k in ("body_w_mid", "endplate", "endplate_lower", "canal_w", "tp_span",
                                      "interpedicular", "interpedicular_max")},
    "spinous_length": ("canal", "tip"),
    **{"pedicle_w_" + s: ("medial", "lateral") for s in ("right", "left")},
    **{"pedicle_h_" + s: ("inferior", "superior") for s in ("right", "left")},
    **{"pedicle_chord_" + s: ("anterior", "posterior") for s in ("right", "left")},
}
# the further segments a line carries, by the part's name
PART_ENDS: Dict[str, Tuple[str, str]] = {"lower plate": ("posterior", "anterior"), "apex to apex": ("superior", "inferior")}
# the measures a vertebra's and a disc's lines are drawn for; every other key the rows hold has none
VERTEBRA_KEYS = tuple(k for k in ENDS if not k.startswith("disc_"))
DISC_KEYS = ("disc_h_ant", "disc_h_mid", "disc_h_post")


@dataclass
class Line:
    key: str
    level: str
    value: float
    a: np.ndarray
    b: np.ndarray
    rule: str
    panel: str
    extra: Dict[str, Tuple[np.ndarray, np.ndarray]] = field(default_factory=dict)
    measured: float = NAN
    status: str = ""

    @property
    def drawn(self) -> float:
        return float(np.linalg.norm(self.b - self.a))


def world(v: A.Vertebra, *local) -> List[np.ndarray]:
    return list(v.points_world(np.array(local, float)))


def from_wall(v: A.Vertebra, x: float, y_sq: float, z: float) -> np.ndarray:
    """A point given with y measured from the canal's wall line, back in the frame."""
    return np.array([x, y_sq + v.wall_slope * (z - v.wall_z0), z])


def centre_x(B: np.ndarray) -> float:
    return 0.5 * (B[:, 0].min() + B[:, 0].max())


# ---- the body ----------------------------------------------------------------------------------

def heights(v: A.Vertebra) -> List[Line]:
    B = v.body_pts
    xc = centre_x(B)
    planes = BODY.plate_slopes(B, v.pixel, v.fz)
    rims = {top: BODY.plate_rims(v, B, top, xc) for top in (True, False)}
    out = []
    for name, at in (("h_ant", lambda r: r[1]), ("h_post_inset", lambda r: r[0]),
                     ("h_mid", lambda r: 0.5 * (r[0] + r[1]))):
        yt, yb = at(rims[True]), at(rims[False])
        zt = BODY.band_surface(B, xc, yt, planes[True], True, v.fz)
        zb = BODY.band_surface(B, xc, yb, planes[False], False, v.fz)
        a, b = world(v, (xc, yb, zb), (xc, yt, zt))
        out.append(Line(name, v.level, math.hypot(zt - zb, yt - yb), a, b, "length", "sagittal"))
    return out


def plate_line(v: A.Vertebra, B: np.ndarray, top: bool, xc: float) -> Tuple[np.ndarray, np.ndarray, float]:
    """The end-plate rim to rim (body.rim_plane) at the midline, and its slope's angle."""
    c = BODY.rim_plane(v, B, top, xc)
    back, ahead = BODY.plate_rims(v, B, top, xc)
    if not (np.isfinite(back) and np.isfinite(ahead)):
        back, ahead = float(B[:, 1].min()), float(B[:, 1].max())
    z = lambda y: c[0] + c[1] * xc + c[2] * y  # noqa: E731
    a, b = world(v, (xc, back, z(back)), (xc, ahead, z(ahead)))
    return a, b, math.atan(c[2])


def wedge(v: A.Vertebra) -> List[Line]:
    B = v.body_pts
    xc = centre_x(B)
    if any(len(BODY.plate_points(B, v.pixel, top)) < 6 for top in (True, False)):
        return []
    ta, tb, st = plate_line(v, B, True, xc)
    ba, bb, sb = plate_line(v, B, False, xc)
    return [Line("wedge", v.level, math.degrees(st - sb), ta, tb, "angle", "sagittal", {"lower plate": (ba, bb)})]


def waist(v: A.Vertebra) -> List[Line]:
    B = v.body_pts
    xc = centre_x(B)
    slab = BODY.mid_slab(v, B, xc)
    mid = slab[np.abs(slab[:, 0] - xc) <= BODY.ACROSS_HALF_MM]
    if len(mid) < 2:
        return []
    y0, y1 = G.surface(mid[:, 1], False, v.fy), G.surface(mid[:, 1], True, v.fy)
    across = slab[np.abs(slab[:, 1] - 0.5 * (y0 + y1)) <= max(BODY.BAND_HALF_MM, 0.5 * v.fy)]
    zs = float(np.median(slab[:, 2]))
    out = [Line("body_d_mid", v.level, y1 - y0, *world(v, (xc, y0, zs), (xc, y1, zs)), "length", "sagittal")]
    if len(across) >= G.MIN_CHORD_POINTS:
        x0, x1 = G.surface(across[:, 0], False, v.fx), G.surface(across[:, 0], True, v.fx)
        ym = 0.5 * (y0 + y1)
        out.append(Line("body_w_mid", v.level, x1 - x0, *world(v, (x0, ym, zs), (x1, ym, zs)), "length",
                        "coronal_body"))
    return out


def plate_slabs(v: A.Vertebra) -> Dict[bool, np.ndarray]:
    """Panjabi's end-plate slabs as scanimport.geometry.body_chords takes them, on the body with y
    measured from the wall line (anatomy.panjabi_body)."""
    Q = A.square_to_wall(v, v.body_pts)
    inner = G.central(Q[:, 0], Q[:, 1])
    core = Q[inner] if inner.sum() >= G.MIN_CHORD_POINTS else Q
    height = float(core[:, 2].max() - core[:, 2].min()) + v.fz
    t = max(min(max(G.ENDPLATE_SHARE * height, G.ENDPLATE_MM[0]), G.ENDPLATE_MM[1]), v.fz)
    return {top: G.plate(Q, inner, max(v.fx, v.fy), t, top, v.fz) for top in (True, False)}


def panjabi_plates(v: A.Vertebra) -> List[Line]:
    if v.touching[v.body].any() or v.body.sum() < G.MIN_BODY_VOXELS:
        return []
    out = []
    for top, name in ((True, "endplate"), (False, "endplate_lower")):
        slab = plate_slabs(v)[top]
        if len(slab) < G.MIN_CHORD_POINTS:
            continue
        x0, x1 = G.surface(slab[:, 0], False, v.fx), G.surface(slab[:, 0], True, v.fx)
        ym, zm = float(np.median(slab[:, 1])), float(np.median(slab[:, 2]))
        a, b = v.points_world(np.array([from_wall(v, x0, ym, zm), from_wall(v, x1, ym, zm)]))
        out.append(Line(name, v.level, x1 - x0, a, b, "length", "coronal_body"))
        y1 = G.surface(slab[:, 1], True, v.fy)
        xm = 0.5 * (x0 + x1)
        a, b = v.points_world(np.array([from_wall(v, xm, v.wall_y0, zm), from_wall(v, xm, y1, zm)]))
        out.append(Line(name + "_depth", v.level, y1 - v.wall_y0, a, b, "length", "sagittal"))
    return out


def panjabi_height(v: A.Vertebra) -> List[Line]:
    """Panjabi's posterior height (h_post) as scanimport.geometry.body_chords takes it on the body
    anatomy.panjabi_body reads it from, with y measured from the wall line: the median, over the
    cells of a grid across the column, of the height surface to surface of the body's points
    within POSTERIOR_SHARE of its depth from the wall and a quarter of its width from its middle
    (column_height). Drawn in the cell whose height is nearest the median, the cell nearest the
    body's middle among those as near to the rows' rounding, at the cell's mean place across and
    up the wall line, so the ends lie the cell's height apart along z."""
    if v.touching[v.body].any() or v.body.sum() < G.MIN_BODY_VOXELS:
        return []
    Q = A.square_to_wall(v, v.body_pts)
    depth = G.surface(Q[:, 1], True, v.fy) - v.wall_y0
    width = G.extent(Q[:, 0], v.fx)
    xm = 0.5 * (Q[:, 0].min() + Q[:, 0].max())
    post = Q[(Q[:, 1] <= v.wall_y0 + G.POSTERIOR_SHARE * depth) & (np.abs(Q[:, 0] - xm) <= 0.25 * width)]
    value = G.column_height(post, v.pixel, v.fz)
    if not np.isfinite(value):
        return []
    order, starts, ends = G.cells(post, v.pixel)
    P = post[order]
    runs = [(P[a:b], G.surface(P[a:b, 2], False, v.fz), G.surface(P[a:b, 2], True, v.fz))
            for a, b in zip(starts, ends) if b - a >= 2]
    cell, lo, hi = min(runs, key=lambda r: (round(abs((r[2] - r[1]) - value), ROWS_PLACES),
                                            abs(float(r[0][:, 0].mean()) - xm)))
    x, y = float(cell[:, 0].mean()), float(cell[:, 1].mean())
    a, b = v.points_world(np.array([from_wall(v, x, y, lo), from_wall(v, x, y, hi)]))
    return [Line("h_post", v.level, value, a, b, "median", "sagittal")]


# ---- the canal ---------------------------------------------------------------------------------

def median_of_three(rings: List[A.CanalSlab], field_: str, k: int, value: float) -> int:
    """Which ring of the three the smoothed profile's value at k came from (canal.smoothed)."""
    near = [j for j in (k - 1, k, k + 1) if 0 <= j < len(rings)]
    return min(near, key=lambda j: abs(getattr(rings[j], field_) - value))


def least_depth(v: A.Vertebra) -> List[Line]:
    rings = v.full_rings()
    if not rings:
        return []
    ap = CANAL.smoothed(rings, "ap")
    k = int(np.argmin(ap))
    s = rings[median_of_three(rings, "ap", k, float(ap[k]))]
    a, b = world(v, (s.midline, s.posterior, s.z), (s.midline, s.anterior, s.z))
    return [Line("canal_ap_min", v.level, float(ap[k]), a, b, "length", "sagittal")]


def section_walls(sec: G.Section, pixel: float, fx: float) -> Optional[Tuple[float, float, float]]:
    """The canal's two side walls through the hole's middle in one section, where
    scanimport.geometry.canal_walls reads the width: (left, right, y)."""
    c, p = sec.canal, sec.pts
    xm, ym = 0.5 * (c[:, 0].min() + c[:, 0].max()), 0.5 * (c[:, 1].min() + c[:, 1].max())
    across = p[np.abs(p[:, 1] - ym) <= 0.75 * pixel]
    right, left = across[across[:, 0] > xm, 0], across[across[:, 0] < xm, 0]
    if not (len(right) and len(left)):
        return None
    return G.surface(left, True, fx), G.surface(right, False, fx), ym


def across_walls(v: A.Vertebra, s: A.CanalSlab) -> Optional[Tuple[float, float, float]]:
    """The canal's two side walls in the section of one of anatomy's slabs: (left, right, y)."""
    for sec in G.sections(v.loc, v.fz, v.pixel, as_hole=True):
        if sec.canal is not None and abs(sec.w - s.z) <= 1e-9:
            walls = section_walls(sec, v.pixel, v.fx)
            if walls is not None:
                return walls
    return None


def canal_reading(v: A.Vertebra) -> Optional[Tuple[List[G.Section], Tuple[float, float], Dict[str, float]]]:
    """The sections, the band along z and the canal scanimport.geometry.chords_from reads
    Panjabi's canal and the spinous length from: the band the middle half of the body cut at the
    canal's median wall, or every section where that band holds no canal it can read."""
    secs = G.sections(v.loc, v.fz, v.pixel, as_hole=True)
    first = G.canal_chords(secs, v.pixel, (-np.inf, np.inf), v.fx, v.fy)
    if not first:
        return None
    body = v.loc[G.connected_front(v.idx, v.loc, first["wall_anterior"], v.grid.shape)]
    band = (-np.inf, np.inf)
    if len(body) >= G.MIN_BODY_VOXELS:
        z0, z1 = float(body[:, 2].min()), float(body[:, 2].max())
        band = (z0 + 0.25 * (z1 - z0), z1 - 0.25 * (z1 - z0))
    canal = G.canal_chords(secs, v.pixel, band, v.fx, v.fy)
    if not canal:
        return secs, (-np.inf, np.inf), first
    return secs, band, canal


def panjabi_canal(v: A.Vertebra) -> List[Line]:
    """Panjabi's canal width and depth (canal_w, canal_ap) as scanimport.geometry.chords_from
    takes them: each the median, over the sections of the band canal_reading gives, of one
    section's reading (canal_walls). Each is drawn in the section whose reading is nearest the
    median, the one nearest the band's middle among those as near to the rows' rounding, the
    width through the hole's middle and the depth down its midline, so neither drawn length
    need equal the median."""
    got = canal_reading(v)
    if got is None:
        return []
    secs, band, canal = got
    rows = [(s, G.canal_walls(s, v.pixel, v.fx, v.fy)) for s in secs
            if s.canal is not None and band[0] <= s.w <= band[1]]
    rows = [(s, r) for s, r in rows if r is not None]
    mid = float(np.median([s.w for s, _ in rows]))
    nearest = lambda k, value: min(rows, key=lambda sr: (round(abs(sr[1][k] - value), ROWS_PLACES),  # noqa: E731
                                                         abs(sr[0].w - mid)))
    out = []
    s, _ = nearest(0, canal["canal_w"])
    walls = section_walls(s, v.pixel, v.fx)
    if walls is not None:
        x0, x1, ym = walls
        out.append(Line("canal_w", v.level, canal["canal_w"], *world(v, (x0, ym, s.w), (x1, ym, s.w)), "median",
                        "axial_canal"))
    _, (_, _, wa, wp, xm, z) = nearest(1, canal["canal_ap"])
    out.append(Line("canal_ap", v.level, canal["canal_ap"], *world(v, (xm, wp, z), (xm, wa, z)), "median", "sagittal"))
    return out


def interpedicular(v: A.Vertebra, ped: Dict[str, dict]) -> List[Line]:
    """The least and the greatest width between the pedicles (canal.measures): between the
    pedicles' own walls where both were found (pedicle.canal_between), in the layer of the three
    its smoothed value came from and the row nearest the median there, drawn as a median since
    the least is the median over the rows about the isthmus and no one row's gap need equal it
    (on the straight phantom the row drawn reads 0.06 mm over the median); else the hole's width
    through its middle over the middle rings, in the ring of the three the least came from, whose
    width is the value itself."""
    band = PED.band(ped)
    if band is not None and np.isfinite(band.get("interpedicular", NAN)):
        out = []
        for key in ("interpedicular", "interpedicular_max"):
            at = band.get(key + "_at")
            if at is None or not np.isfinite(band[key]):
                continue
            y, z, x0, x1 = at
            a, b = world(v, (x0, y, z), (x1, y, z))
            out.append(Line(key, v.level, float(band[key]), a, b, "median", "axial_canal"))
        return out
    sel = CANAL.middle_rings(v.full_rings(), CANAL.body_span(v))
    if not sel:
        return []
    smooth = CANAL.smoothed(sel, "width")
    k = int(np.argmin(smooth))
    s = sel[median_of_three(sel, "width", k, float(smooth[k]))]
    walls = across_walls(v, s)
    if walls is None:
        return []
    x0, x1, ym = walls
    a, b = world(v, (x0, ym, s.z), (x1, ym, s.z))
    return [Line("interpedicular", v.level, float(smooth[k]), a, b, "length", "axial_canal")]


def lateral_film(v: A.Vertebra) -> List[Line]:
    """Eisenstein's lateral construction (canal.lateral_film) with the apexes it joins."""
    if v.level not in CANAL.EISENSTEIN_LEVELS:
        return []
    behind = v.loc[A.square_to_wall(v, v.loc)[:, 1] < v.wall_y0]
    sup, inf = [], []
    for side in (1.0, -1.0):
        s = behind[side * (behind[:, 0] - v.midline) >= CANAL.SPINOUS_CLEAR_MM]
        top, bottom = CANAL.apex(s, True), CANAL.apex(s, False)
        if top is None or bottom is None:
            return []
        sup.append(top)
        inf.append(bottom)
    (ys, zs), (yi, zi) = np.mean(sup, axis=0), np.mean(inf, axis=0)
    if zs - zi <= 0:
        return []
    zb = CANAL.body_span(v)
    ze = zb[0] + 0.75 * (zb[1] - zb[0])
    y_line = ys + (yi - ys) * (zs - ze) / (zs - zi)
    y_wall = v.wall_y0 + v.wall_slope * (ze - v.wall_z0)
    xm = v.midline
    a, b = world(v, (xm, y_line, ze), (xm, y_wall, ze))
    joins = tuple(world(v, (xm, ys, zs), (xm, yi, zi)))
    return [Line("canal_ap_lateral_film", v.level, float(y_wall - y_line), a, b, "length", "sagittal",
                 {"apex to apex": joins})]


def spinous(v: A.Vertebra) -> List[Line]:
    """Panjabi's spinous length from the canal's posterior wall at mid-body to the farthest bone
    behind it on the midline, as scanimport.geometry.chords_from and spinous take it."""
    if v.touching.any():
        return []
    got = canal_reading(v)
    if got is None:
        return []
    canal = got[2]
    back = v.loc[(v.loc[:, 1] < canal["wall_posterior"]) & (np.abs(v.loc[:, 0] - canal["midline_x"]) <= G.MIDLINE_MM)]
    if len(back) < G.MIN_CHORD_POINTS:
        return []
    start = np.array([canal["midline_x"], canal["wall_posterior"], canal["w_mid"]])
    d = np.sqrt(((back - start) ** 2).sum(1))
    a, b = world(v, start, back[int(np.argmax(d))])
    return [Line("spinous_length", v.level, float(d.max()), a, b, "length", "sagittal")]


def tp_span(v: A.Vertebra) -> List[Line]:
    if v.touching.any():
        return []
    x = v.loc[:, 0]
    x0, x1 = G.surface(x, False, v.fx), G.surface(x, True, v.fx)
    lo, hi = v.loc[int(np.argmin(x))], v.loc[int(np.argmax(x))]
    y, z = 0.5 * (lo[1] + hi[1]), 0.5 * (lo[2] + hi[2])
    return [Line("tp_span", v.level, x1 - x0, *world(v, (x0, y, z), (x1, y, z)), "length", "axial_pedicle")]


# ---- the pedicles ------------------------------------------------------------------------------

def march(v: A.Vertebra, c0: np.ndarray, d: np.ndarray) -> Optional[Tuple[float, float]]:
    """Where the line through c0 along d enters and leaves the bone (pedicle.chord), as offsets."""
    ts = np.arange(-150.0, 150.0 + 1e-9, PED.MARCH_MM)
    w = v.points_world(c0[None, :] + ts[:, None] * d[None, :])
    inv = np.linalg.inv(np.asarray(v.grid.affine, float))
    inside = v.is_bone(np.rint(w @ inv[:3, :3].T + inv[:3, 3]).astype(int))
    k = int(np.argmin(np.abs(ts)))
    if not inside[k]:
        near = np.flatnonzero(inside & (np.abs(ts) <= 2.0))
        if not len(near):
            return None
        k = int(near[np.argmin(np.abs(ts[near]))])
    a, b = k, k
    while a > 0 and inside[a - 1]:
        a -= 1
    while b + 1 < len(ts) and inside[b + 1]:
        b += 1
    if a == 0 or b == len(ts) - 1:
        return None
    return ts[a] - 0.5 * PED.MARCH_MM, ts[b] + 0.5 * PED.MARCH_MM


def side_reading(v: A.Vertebra, side: int, name: str, zb: Tuple[float, float],
                 ped: Optional[Dict[str, dict]], vals: Optional[Dict[str, float]]) -> Tuple[Dict[str, float], Optional[dict]]:
    """One side's values and the reading they came from: pedicle.one_side read again, or, where
    the measure's own reading and values are given, those, since one_side is the measure itself
    and reading it again took five sixths of a study's drawing on the phantoms (3.5 of 4.2 s of
    CPU on L2 to L4 at 0.8 by 0.8 by 1 mm, where the drawing on the measure's own reading takes
    a tenth of the measuring's time). On a vertebra the volume's edge touches the measure blanks
    its pedicles' values after reading them (measure.cut_by_the_edge, pedicle.measures), so the
    side is read again there and its lines carry the construction's values, every one of them not
    measured."""
    if ped is None or vals is None or v.touching.any():
        got, _, info = PED.one_side(v, side, zb)
        return got, info
    keys = ("pedicle_w", "pedicle_h", "pedicle_chord")
    return {k: vals.get("%s_%s" % (k, name), NAN) for k in keys}, ped.get(name)


def pedicles(v: A.Vertebra, ped: Optional[Dict[str, dict]] = None, vals: Optional[Dict[str, float]] = None) -> List[Line]:
    """Each side's width across its section at the pedicle's own middle height in that row, its
    height up the column at the middle of the section (pedicle.one_side), each in the row of
    the isthmus rows nearest the median the measure takes, and the chord along the axis, marched
    again here whichever reading the side's values come from (side_reading)."""
    zb = CANAL.body_span(v)
    out = []
    for side, name in PED.SIDES:
        got, info = side_reading(v, side, name, zb, ped, vals)
        if info is None:
            continue
        m = info["map"]
        r = info["rows"][info["width_row"]]
        a, b = world(v, (m.x_of(r["u0"]), r["y"], r["z"]), (m.x_of(r["u1"]), r["y"], r["z"]))
        out.append(Line("pedicle_w_" + name, v.level, got["pedicle_w"], a, b, "median", "coronal_pedicle"))
        r = info["rows"][info["height_row"]]
        a, b = world(v, (r["x"], r["y"], r["run"][0]), (r["x"], r["y"], r["run"][1]))
        out.append(Line("pedicle_h_" + name, v.level, got["pedicle_h"], a, b, "median", "coronal_pedicle"))
        c0, d = info["centre"], info["axis"]
        ends = march(v, c0, d) if np.isfinite(got.get("pedicle_chord", NAN)) else None
        if ends is not None:
            a, b = world(v, c0 + ends[0] * d, c0 + ends[1] * d)
            out.append(Line("pedicle_chord_" + name, v.level, ends[1] - ends[0], a, b, "length", "axial_pedicle"))
    return out


# ---- the discs ---------------------------------------------------------------------------------

def discs(U: A.Vertebra, L: A.Vertebra) -> List[Line]:
    """A disc's three heights in the frame of the vertebra below (column.disc_heights)."""
    Lb = L.body_pts
    Ub = COL.in_frame(U, L.frame, U.body_pts)
    xl, xu = centre_x(Lb), centre_x(Ub)
    low_plane = BODY.plate_slopes(Lb, L.pixel, L.fz)[True]
    up_plane = BODY.plate_slopes(Ub, L.pixel, L.fz)[False]
    lb, la = BODY.plate_rims(L, Lb, True, xl)
    ub, ua = BODY.plate_rims(L, Ub, False, xu)
    level = "%s-%s" % (U.level, L.level)
    out = []
    for name, yl, yu in (("disc_h_ant", la, ua), ("disc_h_mid", 0.5 * (lb + la), 0.5 * (ub + ua)),
                         ("disc_h_post", lb, ub)):
        zu = BODY.band_typical(Ub, xu, yu, up_plane, False, L.fz, L.pixel)
        zl = BODY.band_typical(Lb, xl, yl, low_plane, True, L.fz, L.pixel)
        a, b = world(L, (xl, yl, zl), (xu, yu, zu))
        out.append(Line(name, level, zu - zl, a, b, "dz", "sagittal"))
    return out


# ---- all of them, checked ----------------------------------------------------------------------

def vertebra_builders(v: A.Vertebra, ped: Dict[str, dict],
                      vals: Optional[Dict[str, float]] = None) -> List[Tuple[str, Callable[[], List[Line]]]]:
    """Each builder of the vertebra's lines by its name, as a call that draws its lines, so a
    caller can keep the lines of the others where one fails; with the values
    morphometry.measure.vertebra_values gave, the pedicles' lines are drawn on the reading those
    values came from (side_reading)."""
    alone = (("heights", heights), ("wedge", wedge), ("waist", waist), ("panjabi_plates", panjabi_plates),
             ("panjabi_height", panjabi_height), ("least_depth", least_depth), ("panjabi_canal", panjabi_canal),
             ("lateral_film", lateral_film), ("spinous", spinous), ("tp_span", tp_span))
    out = [(name, (lambda f=f: f(v))) for name, f in alone]
    out += [("pedicles", lambda: pedicles(v, ped, vals)), ("interpedicular", lambda: interpedicular(v, ped))]
    return out


def vertebra_lines(v: A.Vertebra, ped: Dict[str, dict], vals: Optional[Dict[str, float]] = None) -> List[Line]:
    """Every line of the vertebra, builder by builder (vertebra_builders)."""
    out: List[Line] = []
    for _, draw in vertebra_builders(v, ped, vals):
        out += draw()
    return out


def checked(lines: List[Line], measured: Dict[str, float], places: Optional[int] = None) -> List[Line]:
    """Each line with the measured value beside it, and its status: drawn, or withheld and why.
    A value read back from a file written to `places` decimals may differ by half its last place."""
    rounding = 0.5 * 10.0 ** -places if places is not None else 0.0
    for ln in lines:
        m = measured.get(ln.key, NAN)
        ln.measured = float(m) if isinstance(m, (int, float)) else NAN
        if not math.isfinite(ln.measured):
            ln.status = "not measured"
        elif not math.isfinite(ln.value) or abs(ln.value - ln.measured) > rounding + AGREE * max(1.0, abs(ln.measured)):
            ln.status = "withheld: the construction gives %.4g where the rows hold %.4g" % (ln.value, ln.measured)
        else:
            ln.status = "drawn"
    return lines
