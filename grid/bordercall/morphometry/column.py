"""Between vertebrae: disc heights, the segmental angles, the slip, the foramen's height, and the
regional curves over the column.

A disc is read in the frame of the vertebra below it (L), whose z is the direction the disc's
height is taken along. In L's frame the upper vertebra's body (U) is brought in through the
world, and at three places front to back on the midline the disc height is the gap along z from
L's upper surface to U's lower surface, each plate read in a band 3 mm deep and 6 mm wide set at
its own corners (body.plate_rims): 2.5 mm inside the anterior corners, half-way, and 2.5 mm
inside the posterior corners, as body.band_surface reads a height's ends. Bands set at L's
corners for both plates would miss U's when U has slipped: at a 4 mm slip U's plate holds no
point in the posterior band. disc_h_mean is the mean of the three.

The segmental angles compare U's lower end-plate with L's upper end-plate, each drawn from rim to
rim (body.rim_plane), in L's frame: sagittal positive where the disc opens in front (lordosis),
coronal positive where it opens to the patient's right, and the axial turn of U's front against
L's, positive toward the right. The slip is how far U's posterior-inferior corner stands in
front of L's posterior-superior corner, along L's upper end-plate, as Meyerding measured it,
each corner read in its own end-plate's frame (wall_corner): read along L's y, whose frame
follows the column's line through the neighbours, the phantom's 4.2 mm slip came out 2.0 mm,
since a slipped neighbour tilts that line 8 degrees against L's own axis. listhesis_pct is the
slip as a share of L's upper end-plate depth, as Meyerding graded it. The foramen's height is
the distance along L's axis from the lowest point of U's pedicle at its isthmus to the highest
point of L's (pedicle.py), each side.

The regional curves are angles between end-plates in the plane the vertebrae involved share, its
left-right direction the mean of their frames' x: lordosis from L1's upper plate to S1's
(pelvis.py), kyphosis from T4's upper plate to T12's lower plate, the cervical curve from C2's
lower plate to C7's lower plate, and the coronal Cobb angle, the greatest angle in the coronal
plane between an upper plate and a lower plate below it from T1 to L5.
"""
from __future__ import annotations

import math
from typing import Dict, Optional, Sequence, Tuple

import numpy as np

from scanimport import geometry as G

from . import anatomy as A
from . import body as BODY
from .anatomy import NAN, Vertebra

ACROSS_HALF_MM = BODY.ACROSS_HALF_MM
WALL_END_MM = 4.0


def in_frame(of: Vertebra, frame: G.Frame, local: np.ndarray) -> np.ndarray:
    return frame.local(of.points_world(local))


def disc_heights(U: Vertebra, L: Vertebra) -> Dict[str, float]:
    Lb = L.body_pts
    Ub = in_frame(U, L.frame, U.body_pts)
    xl = 0.5 * (Lb[:, 0].min() + Lb[:, 0].max())
    xu = 0.5 * (Ub[:, 0].min() + Ub[:, 0].max())
    low_plane = BODY.plate_slopes(Lb, L.pixel, L.fz)[True]
    up_plane = BODY.plate_slopes(Ub, L.pixel, L.fz)[False]
    lb, la = BODY.plate_rims(L, Lb, True, xl)
    ub, ua = BODY.plate_rims(L, Ub, False, xu)
    out = {}
    for name, yl, yu in (("disc_h_ant", la, ua), ("disc_h_mid", 0.5 * (lb + la), 0.5 * (ub + ua)),
                         ("disc_h_post", lb, ub)):
        out[name] = (BODY.band_surface(Ub, xu, yu, up_plane, False, L.fz)
                     - BODY.band_surface(Lb, xl, yl, low_plane, True, L.fz))
    vals = [out[k] for k in ("disc_h_ant", "disc_h_mid", "disc_h_post")]
    out["disc_h_mean"] = float(np.mean(vals)) if all(np.isfinite(vals)) else NAN
    return out


def plate_normal(v: Vertebra, top: bool) -> Optional[np.ndarray]:
    """The end-plate's upward normal in the world, from its rim-to-rim plane (body.rim_plane)."""
    B = v.body_pts
    if len(BODY.plate_points(B, v.pixel, top)) < 6:
        return None
    xc = 0.5 * (B[:, 0].min() + B[:, 0].max())
    c = BODY.rim_plane(v, B, top, xc)
    n = v.to_world(np.array([-c[1], -c[2], 1.0]))
    return n / np.linalg.norm(n)


def plate_centre(v: Vertebra, top: bool) -> np.ndarray:
    """A world point on the end-plate at the middle of the body's central part."""
    B = v.body_pts
    inner = BODY.plate_core(B, top)
    core = B[inner] if inner.sum() >= G.MIN_CHORD_POINTS else B
    c = BODY.plane_robust(BODY.plate_extremes(core, v.pixel, top), v.fz)
    x, y = core[:, 0].mean(), core[:, 1].mean()
    return v.points_world(np.array([[x, y, c[0] + c[1] * x + c[2] * y]]))[0]


def slope_angle(n: np.ndarray, along: np.ndarray, up: np.ndarray) -> float:
    """The angle (radians) at which the plane with normal n rises along `along`, in the plane of
    `along` and `up`."""
    a, u = float(n @ along), float(n @ up)
    return math.atan2(-a, u)


def segment_angles(U: Vertebra, L: Vertebra) -> Dict[str, float]:
    nu, nl = plate_normal(U, False), plate_normal(L, True)
    out = {"segment_sagittal": NAN, "segment_coronal": NAN, "segment_axial": NAN}
    if nu is None or nl is None:
        return out
    f = L.frame
    out["segment_sagittal"] = math.degrees(slope_angle(nu, f.ey, f.ez) - slope_angle(nl, f.ey, f.ez))
    out["segment_coronal"] = math.degrees(slope_angle(nu, f.ex, f.ez) - slope_angle(nl, f.ex, f.ez))
    ey = U.frame.ey
    out["segment_axial"] = math.degrees(math.atan2(float(ey @ f.ex), float(ey @ f.ey)))
    return out


def plate_frame(v: Vertebra, top: bool) -> G.Frame:
    """v's frame tilted so that z is the end-plate's normal, y still toward the body; v's own
    frame where the plate is not found."""
    n = plate_normal(v, top)
    return v.frame if n is None else G.frame_from(v.frame.origin, n, v.frame.ey)


def wall_corner(v: Vertebra, top: bool) -> Optional[np.ndarray]:
    """The world point where the body's posterior wall meets its upper (or lower) end-plate on
    the midline, read in the end-plate's own frame: the wall the surface of v's voxels in the
    band across the middle, in front of the canal's middle and within WALL_END_MM of the plate,
    and the plate the body's extreme along the plate's normal. All of v's voxels there and not
    only the body's: the body is cut from the arch along a line the canal's slabs give, which on
    the joint phantom leans half as far as the wall does, and so still shaves the wall's end
    where the column's line tilts against the vertebra's own axis."""
    f = plate_frame(v, top)
    ap = float(np.median([s.ap for s in v.full_rings()]))
    near = A.square_to_wall(v, v.loc)[:, 1] > v.wall_y0 - 0.5 * ap
    P = f.local(v.grid.world(v.idx[near].astype(float)))
    B = f.local(v.points_world(v.body_pts))
    xc = 0.5 * (B[:, 0].min() + B[:, 0].max())
    mid = P[np.abs(P[:, 0] - xc) <= ACROSS_HALF_MM]
    zb = B[:, 2].max() if top else B[:, 2].min()
    end = mid[np.abs(mid[:, 2] - zb) <= WALL_END_MM]
    end = end[end[:, 2] <= zb + v.fz] if top else end[end[:, 2] >= zb - v.fz]
    if len(end) < 2:
        return None
    y = G.surface(end[:, 1], False, v.grid.footprint(f.ey))
    return f.origin + xc * f.ex + y * f.ey + G.surface(B[:, 2], top, v.grid.footprint(f.ez)) * f.ez


def slip(U: Vertebra, L: Vertebra, depth: float) -> Dict[str, float]:
    """U's posterior-inferior corner against L's posterior-superior corner, along L's upper
    end-plate."""
    cu, cl = wall_corner(U, False), wall_corner(L, True)
    if cu is None or cl is None:
        return {"listhesis": NAN, "listhesis_pct": NAN}
    s = float((cu - cl) @ plate_frame(L, True).ey)
    return {"listhesis": s, "listhesis_pct": 100.0 * s / depth if np.isfinite(depth) and depth > 0 else NAN}


def foramen(U: Vertebra, L: Vertebra, pu: Dict[str, dict], pl: Dict[str, dict]) -> Dict[str, float]:
    out = {}
    for name in ("right", "left"):
        if name not in pu or name not in pl:
            out["foramen_h_" + name] = NAN
            continue
        a, b = pu[name], pl[name]
        down = a["eh"] if a["eh"][2] < 0 else -a["eh"]
        up = b["eh"] if b["eh"][2] > 0 else -b["eh"]
        lo = U.points_world((a["centre"] + 0.5 * a["height"] * down)[None, :])[0]
        hi = L.points_world((b["centre"] + 0.5 * b["height"] * up)[None, :])[0]
        out["foramen_h_" + name] = float((lo - hi) @ L.frame.ez)
    r, l = out["foramen_h_right"], out["foramen_h_left"]
    out["foramen_h"] = 0.5 * (r + l) if np.isfinite(r) and np.isfinite(l) else NAN
    return out


def disc(U: Vertebra, L: Vertebra, pu: Dict[str, dict], pl: Dict[str, dict], depth_l: float) -> Dict[str, float]:
    out = disc_heights(U, L)
    out.update(segment_angles(U, L))
    out.update(slip(U, L, depth_l))
    out.update(foramen(U, L, pu, pl))
    return out


# ---- regional curves ---------------------------------------------------------------------------

def shared_plane(vs: Sequence[Vertebra]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Left-right, anterior and up, shared by the vertebrae: x the mean of theirs, up the mean
    of their axes made square to it."""
    ex = np.mean([v.frame.ex for v in vs], axis=0)
    ex /= np.linalg.norm(ex)
    ez = np.mean([v.frame.ez for v in vs], axis=0)
    ez = ez - (ez @ ex) * ex
    ez /= np.linalg.norm(ez)
    return ex, np.cross(ez, ex), ez


def sagittal_between(upper: np.ndarray, lower: np.ndarray, frame) -> float:
    """Degrees by which the upper plate rises toward the front more than the lower plate does:
    positive where the column between them is lordotic."""
    ex, ey, ez = frame
    return math.degrees(slope_angle(upper, ey, ez) - slope_angle(lower, ey, ez))


def regional(verts: Dict[str, Vertebra], s1_normal: Optional[np.ndarray]) -> Dict[str, object]:
    out: Dict[str, object] = {}
    lumbar = [verts[k] for k in ("L1", "L2", "L3", "L4", "L5", "L6") if k in verts]
    if "L1" in verts and s1_normal is not None and lumbar:
        n1 = plate_normal(verts["L1"], True)
        if n1 is not None:
            out["lordosis_L1_S1"] = sagittal_between(n1, s1_normal, shared_plane(lumbar))
    thor = [verts["T%d" % i] for i in range(4, 13) if "T%d" % i in verts]
    if "T4" in verts and "T12" in verts:
        a, b = plate_normal(verts["T4"], True), plate_normal(verts["T12"], False)
        if a is not None and b is not None:
            out["kyphosis_T4_T12"] = -sagittal_between(a, b, shared_plane(thor))
    cerv = [verts["C%d" % i] for i in range(2, 8) if "C%d" % i in verts]
    if "C2" in verts and "C7" in verts:
        a, b = plate_normal(verts["C2"], False), plate_normal(verts["C7"], False)
        if a is not None and b is not None:
            out["lordosis_C2_C7"] = sagittal_between(a, b, shared_plane(cerv))
    out.update(coronal_cobb(verts))
    return out


def coronal_cobb(verts: Dict[str, Vertebra]) -> Dict[str, object]:
    names = ["T%d" % i for i in range(1, 13)] + ["L%d" % i for i in range(1, 6)]
    vs = [(k, verts[k]) for k in names if k in verts]
    if len(vs) < 3:
        return {}
    ex, ey, ez = shared_plane([v for _, v in vs])
    tops = [(k, plate_normal(v, True)) for k, v in vs]
    bots = [(k, plate_normal(v, False)) for k, v in vs]
    best = (NAN, None, None)                    # not a number where no pair of plates was found
    for i, (ka, na) in enumerate(tops):
        for kb, nb in bots[i:]:
            if na is None or nb is None:
                continue
            ang = abs(math.degrees(slope_angle(na, ex, ez) - slope_angle(nb, ex, ez)))
            if not ang <= best[0]:
                best = (ang, ka, kb)
    return {"coronal_cobb": best[0], "coronal_cobb_upper": best[1], "coronal_cobb_lower": best[2]}
