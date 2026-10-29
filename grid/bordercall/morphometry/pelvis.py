"""The pelvis: the S1 end-plate, the hip joints' centres, pelvic incidence with the supine sacral
slope and pelvic tilt, the iliac crests' line, and the gaps from the lowest lumbar vertebra's
transverse processes to the sacrum and the ilium.

ENHANCE.PET's masks label the sacrum (28) and each hip bone (26 left, 27 right) and no femur, so
the hip joint's centre is the centre of the acetabulum, the one deep spherical socket of the hip
bone. It is found by voting: at each voxel on the hip bone's surface the outward normal (from the
gradient of the smoothed mask) points into whatever cavity the surface bounds, and every radius
from 18 to 32 mm along it casts a vote for a centre there; the socket's surface points at one
centre from every side, a flat or a gently curved surface spreads its votes, so the densest bin
is the socket's centre. A least-squares sphere through the surface points that voted near it,
and whose normals face it, refines the centre and gives the radius.

The S1 end-plate is the top of the sacrum under the lowest lumbar body: in that vertebra's frame,
the highest sacral point of each cell of a grid across its body's footprint, a least-squares
plane through them, and its centre the middle of the cells within 2 mm of that plane. Pelvic
incidence is the angle, in the plane square to the line through the two hip centres, between the
S1 plate's normal turned into the pelvis and the line from the plate's centre to the midpoint of
the hip centres (Duval-Beaupere and Legaye). It does not depend on posture. The sacral slope and
the pelvic tilt are posture's, and a CT is taken supine: here they are read against the scanner's
long axis, the vertical of a sagittal reconstruction, so they are the supine values, not the
standing ones, and pelvic incidence equals their sum.

The crests' line joins the highest point of each hip bone along the scanner's long axis; the
level it crosses is the vertebra, or the disc, whose span along its own axis holds the line's
midpoint, and its offset is the midpoint's height along the column above the middle of the
L4-L5 disc. The transverse processes' gaps are the least distances from the voxels of each
process of the lowest lumbar vertebra to the sacrum's and the hip bone's voxels, centre to
centre, so a process that touches the other bone reads about one voxel; Castellvi grades contact
and fusion from these and from the process's height.
"""
from __future__ import annotations

import math
from typing import Dict, Iterable, Optional, Tuple

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

from scanimport import geometry as G

from . import column as COL
from .anatomy import NAN, Vertebra

HIP_LEFT, HIP_RIGHT, SACRUM = 26, 27, 28
SOCKET_MM = (18.0, 32.0)
VOTE_BIN_MM = 2.0
S1_FOOT = 0.35
TP_SHARE = 0.6


def world_points(grid: G.VoxelGrid, idx: np.ndarray) -> np.ndarray:
    return grid.world(idx.astype(float))


def surface_normals(mask_idx: np.ndarray, grid: G.VoxelGrid) -> Tuple[np.ndarray, np.ndarray]:
    """The bone's surface voxels in the world and their outward unit normals."""
    lo = mask_idx.min(0) - 3
    box = np.zeros(tuple(mask_idx.max(0) - lo + 4), bool)
    box[tuple((mask_idx - lo).T)] = True
    shell = box & ~ndimage.binary_erosion(box)
    smooth = ndimage.gaussian_filter(box.astype(float), 1.0)
    grads = np.stack(np.gradient(smooth), axis=-1)
    ijk = np.argwhere(shell)
    g = grads[tuple(ijk.T)]
    A = np.asarray(grid.affine, float)[:3, :3]
    n = -(g @ np.linalg.inv(A))                      # a gradient turns with the inverse transpose
    norm = np.linalg.norm(n, axis=1)
    keep = norm > 1e-6
    return grid.world((ijk[keep] + lo).astype(float)), n[keep] / norm[keep, None]


def fit_sphere(p: np.ndarray) -> Tuple[np.ndarray, float]:
    A = np.column_stack([2.0 * p, np.ones(len(p))])
    b = (p ** 2).sum(1)
    sol = np.linalg.lstsq(A, b, rcond=None)[0]
    c = sol[:3]
    return c, float(math.sqrt(max(sol[3] + c @ c, 0.0)))


def socket_centre(mask_idx: np.ndarray, grid: G.VoxelGrid) -> Optional[Dict[str, object]]:
    if len(mask_idx) < 1000:
        return None
    p, n = surface_normals(mask_idx, grid)
    radii = np.arange(SOCKET_MM[0], SOCKET_MM[1] + 1e-9, 1.0)
    votes = (p[:, None, :] + radii[None, :, None] * n[:, None, :]).reshape(-1, 3)
    lo = votes.min(0)
    keys = np.floor((votes - lo) / VOTE_BIN_MM).astype(np.int64)
    dims = keys.max(0) + 1
    flat = (keys[:, 0] * dims[1] + keys[:, 1]) * dims[2] + keys[:, 2]
    best = int(np.argmax(np.bincount(flat)))
    k = np.array([best // (dims[1] * dims[2]), (best // dims[2]) % dims[1], best % dims[2]])
    c0 = lo + (k + 0.5) * VOTE_BIN_MM
    to_c = c0 - p
    dist = np.linalg.norm(to_c, axis=1)
    facing = (to_c * n).sum(1) / np.maximum(dist, 1e-9)
    near = (dist >= SOCKET_MM[0] - 3) & (dist <= SOCKET_MM[1] + 3) & (facing > 0.9)
    if near.sum() < 50:
        return None
    c, r = fit_sphere(p[near])
    for _ in range(3):                               # keep the points on the fitted sphere and fit again
        on = near & (np.abs(np.linalg.norm(p - c, axis=1) - r) <= 2.0)
        if on.sum() < 50:
            break
        c, r = fit_sphere(p[on])
    return {"centre": c, "radius": r, "points": int(near.sum())}


def s1_plate(sacrum_idx: np.ndarray, grid: G.VoxelGrid, low: Vertebra) -> Optional[Dict[str, np.ndarray]]:
    B = low.body_pts
    q = low.frame.local(world_points(grid, sacrum_idx))
    xc = 0.5 * (B[:, 0].min() + B[:, 0].max())
    half = 0.5 * (B[:, 0].max() - B[:, 0].min())
    zbot = B[:, 2].min()
    sel = q[(np.abs(q[:, 0] - xc) <= S1_FOOT * 2 * half) & (q[:, 1] >= low.wall + 2.0) & (q[:, 1] <= B[:, 1].max() - 2.0)
            & (q[:, 2] < zbot) & (q[:, 2] > zbot - 45.0)]
    if len(sel) < 6 * G.MIN_CHORD_POINTS:
        return None
    from .body import plane_lsq, plate_extremes
    ext = plate_extremes(sel, low.pixel, True)
    if len(ext) < 6:
        return None
    c = plane_lsq(ext)
    on = ext[np.abs(ext[:, 2] - (c[0] + c[1] * ext[:, 0] + c[2] * ext[:, 1])) <= 2.0]
    x, y = on[:, 0].mean(), on[:, 1].mean()
    centre = low.points_world(np.array([[x, y, c[0] + c[1] * x + c[2] * y]]))[0]
    n = low.to_world(np.array([-c[1], -c[2], 1.0]))
    return {"centre": centre, "normal": n / np.linalg.norm(n)}


def angle_in_plane(a: np.ndarray, b: np.ndarray, normal: np.ndarray) -> float:
    """The signed angle (degrees) from a to b, both projected into the plane square to normal,
    positive turning about normal."""
    pa, pb = a - (a @ normal) * normal, b - (b @ normal) * normal
    return math.degrees(math.atan2(float(np.cross(pa, pb) @ normal), float(pa @ pb)))


def incidence(s1: Dict[str, np.ndarray], hips: Dict[str, Dict[str, object]], grid: G.VoxelGrid) -> Dict[str, float]:
    cr, cl = hips["right"]["centre"], hips["left"]["centre"]
    e = (cr - cl) / np.linalg.norm(cr - cl)                 # toward the patient's right
    up = grid.superior() - (grid.superior() @ e) * e
    up /= np.linalg.norm(up)
    ant = np.cross(up, e)
    o, n = s1["centre"], s1["normal"]
    hip_mid = 0.5 * (cr + cl)
    pi = abs(angle_in_plane(-n, hip_mid - o, e))
    ss = math.degrees(math.atan2(float(n @ ant), float(n @ up)))
    rise = o - hip_mid                                       # from the hip axis up to the plate
    pt = -math.degrees(math.atan2(float(rise @ ant), float(rise @ up)))
    return {"pelvic_incidence": pi, "sacral_slope_supine": ss, "pelvic_tilt_supine": pt,
            "hip_axis_width": float(np.linalg.norm(cr - cl)),
            "acetabulum_radius_right": float(hips["right"]["radius"]),
            "acetabulum_radius_left": float(hips["left"]["radius"])}


def crest_top(idx: np.ndarray, grid: G.VoxelGrid) -> np.ndarray:
    p = world_points(grid, idx)
    h = p @ grid.superior()
    return p[h >= h.max() - 1.0].mean(0)


def crest_level(mid: np.ndarray, verts: Dict[str, Vertebra]) -> Tuple[str, float]:
    order = [k for k in ("L1", "L2", "L3", "L4", "L5", "L6") if k in verts]
    prev = None
    for k in order:
        v = verts[k]
        z = float(v.frame.local(mid[None, :])[0, 2])
        B = v.body_pts
        if B[:, 2].min() <= z <= B[:, 2].max():
            return k, z
        if z > B[:, 2].max():
            return ("%s-%s" % (prev, k) if prev else "above " + k), z
        prev = k
    return ("below " + prev) if prev else "", NAN


def crests(hip_idx: Dict[str, np.ndarray], grid: G.VoxelGrid, verts: Dict[str, Vertebra]) -> Dict[str, object]:
    if "L4" not in verts or "L5" not in verts:
        return {}
    mid = 0.5 * (crest_top(hip_idx["right"], grid) + crest_top(hip_idx["left"], grid))
    level, _ = crest_level(mid, verts)
    a = COL.plate_centre(verts["L4"], False)
    b = COL.plate_centre(verts["L5"], True)
    axis = verts["L5"].frame.ez + verts["L4"].frame.ez
    axis /= np.linalg.norm(axis)
    return {"intercristal_level": level, "intercristal_above_l4l5": float((mid - 0.5 * (a + b)) @ axis)}


def tp_gaps(low: Vertebra, sacrum_idx: np.ndarray, hip_idx: Dict[str, np.ndarray], grid: G.VoxelGrid) -> Dict[str, float]:
    out = {}
    sac = cKDTree(world_points(grid, sacrum_idx))
    for side, name in ((1, "right"), (-1, "left")):
        off = side * (low.loc[:, 0] - low.midline)
        reach = off.max() if (off > 0).any() else 0.0
        tip = low.loc[off >= TP_SHARE * reach]
        if len(tip) < G.MIN_CHORD_POINTS or name not in hip_idx:
            out["tp_sacrum_gap_" + name] = out["tp_ilium_gap_" + name] = NAN
            continue
        w = low.points_world(tip)
        out["tp_sacrum_gap_" + name] = float(sac.query(w)[0].min())
        out["tp_ilium_gap_" + name] = float(cKDTree(world_points(grid, hip_idx[name])).query(w)[0].min())
    return out


def measures(vol: np.ndarray, grid: G.VoxelGrid, verts: Dict[str, Vertebra],
             present: Optional[Iterable[str]] = None) -> Tuple[Dict[str, object], Dict[str, str]]:
    """The pelvis under the lowest lumbar vertebra the mask names (present, else verts). Where
    that vertebra was not measured, nothing: the one above it does not stand on the sacrum, and
    an L6 too small or cut by the edge would otherwise pass its place to L5."""
    out: Dict[str, object] = {}
    flags: Dict[str, str] = {}
    idx = {name: np.argwhere(vol == value) for name, value in (("left", HIP_LEFT), ("right", HIP_RIGHT), ("sacrum", SACRUM))}
    named = set(verts if present is None else present)
    lows = [k for k in ("L6", "L5") if k in named]
    if lows and lows[0] not in verts:
        return out, {"pelvis": "the lowest lumbar vertebra the mask names, %s, was not measured" % lows[0]}
    if not lows or len(idx["sacrum"]) < 1000:
        return out, {"pelvis": "no lowest lumbar vertebra measured, or no sacrum"}
    low = verts[lows[0]]
    s1 = s1_plate(idx["sacrum"], grid, low)
    if s1 is None:
        flags["s1"] = "no S1 end-plate under the lowest lumbar body"
    else:
        out["s1_normal"] = s1["normal"]
    hips = {}
    for name in ("right", "left"):
        got = socket_centre(idx[name], grid) if len(idx[name]) else None
        if got is not None:
            hips[name] = got
    if s1 is not None and len(hips) == 2:
        out.update(incidence(s1, hips, grid))
    elif len(hips) < 2:
        flags["hips"] = "an acetabulum was not found"
    hip_idx = {k: idx[k] for k in ("right", "left") if len(idx[k])}
    if len(hip_idx) == 2:
        out.update(crests(hip_idx, grid, verts))
    out.update(tp_gaps(low, idx["sacrum"], hip_idx, grid))
    out["lowest_lumbar"] = lows[0]
    return out, flags
