"""The posterior elements: the transverse processes, the spinous process's angle, the laminae's
thickness and angle, and the articular processes' orientation, spacing and tropism.

- transverse_width (Panjabi's TPW) is scanimport's tp_span, tip to tip; transverse_length is each
  process's reach from the canal's midline to its tip, right and left. transverse_h is the
  craniocaudal height of the outer quarter of each process's reach, where Castellvi's type I
  (a dysplastic process at least 19 mm high) is read.
- spinous_angle is the inclination of the spinous process below the transverse plane square to
  the body's posterior wall (as the end-plates' inclinations are taken, body.posterior_wall; not
  read, and flagged, where the wall is not), along the line its middle follows from base to tip
  in the midline: the bone in the midline strip more than 6 mm behind the canal's posterior wall
  is cut into slabs 1 mm deep front to back, and the line is fitted to the middle of each slab's
  height over the middle half of the strip's depth; nearer in, the laminae's lower edges join
  it, and at the back the tip's blunt end. Two other lines were set aside: the principal
  direction of the bone, since a lumbar or cervical process is nearly as tall as it is long and
  that direction turns toward the vertical whatever its line from base to tip; and the line from
  the centroid of its front 3 mm to that of its back 3 mm, since the tip's end holds its upper
  corner furthest back, and on the phantom the line read 11 and 22 degrees where the processes
  fall 20 and 32.
- lamina_thickness: each lamina, between the spinous process's base and the canal's lateral
  edge, is a plate. Its medial sheet is the voxels whose distance to the outside of the vertebra
  is a local maximum (the distance transform's ridge), and the sheet's direction of least spread
  is the plate's normal; the thickness square to the plate is the extent along that normal of
  the bone within 3 mm of the normal through the sheet's centre, as calipers set across it. It
  is then turned into the thickness across the lamina in the transverse plane, as a reader
  measures it on an axial slice. lamina_angle is
  the angle between the two laminae's traces in the transverse plane, the trace of each pointing
  out to its own side, so that laminae meeting behind the canal in a V that opens forward read
  under 180 degrees.
- The superior articular processes are the bone behind the body rising more than 3 mm above the
  top of its posterior wall, lateral of the spinous process; the inferior ones hang more than
  3 mm below its bottom. In the transverse slab half-way up each, the principal direction of its
  section is the facet's line; facet_angle_axial is that line's angle to the midsagittal plane
  (0 sagittal, 90 coronal), facet_tropism the difference between the sides, and interfacet_w the
  distance across between the two sections' centroids (Panjabi's IFWs and IFWi, from the centre
  of one facet to the centre of the other). A real facet is curved, a C or a J at L4 and L5, so the
  section's long axis is its chord, as the line from its anteromedial to its posterolateral
  margin that Noren and others drew is.
"""
from __future__ import annotations

import math
from typing import Dict, Optional, Tuple

import numpy as np
from scipy import ndimage

from scanimport import geometry as G

from .anatomy import NAN, Vertebra
from .pedicle import wall_reading, wall_slope

SPINOUS_BEHIND_MM = 6.0
SPINOUS_HALF_MM = 3.0
SPINOUS_SLAB_MM = 1.0
PROCESS_CLEAR_MM = 5.0
FACET_RISE_MM = 3.0
TIP_SHARE = 0.25
CALIPER_MM = 3.0
SIDES = ((1, "right"), (-1, "left"))


def principal(pts: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """The principal directions of the points, largest spread first, as rows; and the centroid."""
    c = pts.mean(0)
    return np.linalg.svd(pts - c, full_matrices=False)[2], c


def measures(v: Vertebra) -> Tuple[Dict[str, float], Dict[str, str]]:
    out: Dict[str, float] = {"transverse_width": v.panjabi.get("tp_span", NAN)}
    flags: Dict[str, str] = {}
    out.update(transverse(v))
    out["spinous_angle"] = spinous_angle(v)
    wall, why = wall_reading(v)
    if not math.isfinite(wall):
        flags["spinous"] = ("the body's posterior wall is not read (%s): the spinous process's inclination, taken "
                            "against it, is not" % why)
    out.update(laminae(v))
    got, note = facets(v)
    out.update(got)
    if note:
        flags["facets"] = note
    if v.touching.any():
        for k in ("transverse_length_right", "transverse_length_left", "transverse_length",
                  "transverse_h_right", "transverse_h_left", "transverse_h", "spinous_angle"):
            out[k] = NAN
        flags["processes"] = "the vertebra touches the edge of the volume"
    return out, flags


def transverse(v: Vertebra) -> Dict[str, float]:
    out = {}
    for side, name in SIDES:
        off = side * (v.loc[:, 0] - v.midline)
        reach = G.surface(off[off > 0], True, v.fx) if (off > 0).sum() >= G.MIN_CHORD_POINTS else NAN
        out["transverse_length_" + name] = reach
        tip = v.loc[off >= (1.0 - TIP_SHARE) * reach] if np.isfinite(reach) else v.loc[:0]
        out["transverse_h_" + name] = G.extent(tip[:, 2], v.fz) if len(tip) >= G.MIN_CHORD_POINTS else NAN
    for k in ("transverse_length", "transverse_h"):
        a, b = out[k + "_right"], out[k + "_left"]
        out[k] = 0.5 * (a + b) if np.isfinite(a) and np.isfinite(b) else NAN
    return out


def spinous_angle(v: Vertebra) -> float:
    back = v.loc[(np.abs(v.loc[:, 0] - v.midline) <= SPINOUS_HALF_MM) & (v.loc[:, 1] < v.wall_post - SPINOUS_BEHIND_MM)]
    if len(back) < G.MIN_CHORD_POINTS:
        return NAN
    y, z = back[:, 1], back[:, 2]
    lo, hi = y.min() + 0.25 * np.ptp(y), y.max() - 0.25 * np.ptp(y)
    step = max(SPINOUS_SLAB_MM, v.fy)
    mids = []
    for y0 in np.arange(lo, hi, step):
        slab = z[(y >= y0) & (y < y0 + step)]
        if len(slab) >= 2:
            mids.append((y0 + 0.5 * step, 0.5 * (G.surface(slab, False, v.fz) + G.surface(slab, True, v.fz))))
    if len(mids) < 3:
        return NAN
    mids = np.array(mids)
    return math.degrees(math.atan(np.polyfit(mids[:, 0], mids[:, 1], 1)[0]) + math.atan(wall_slope(v)))


def medial_sheet(v: Vertebra) -> np.ndarray:
    """Which voxels lie on the vertebra's medial sheet: those whose distance in mm to the
    nearest voxel outside it is the greatest among their neighbours."""
    lo = v.idx.min(0) - 1
    box = np.zeros(tuple(v.idx.max(0) - lo + 2), bool)
    box[tuple((v.idx - lo).T)] = True
    edt = ndimage.distance_transform_edt(box, sampling=v.grid.spacing)
    ridge = (edt >= ndimage.maximum_filter(edt, size=3) - 1e-9) & box
    return ridge[tuple((v.idx - lo).T)]


def caliper(v: Vertebra, c: np.ndarray, n: np.ndarray) -> float:
    """The plate's thickness along n through c: the extent along n of the vertebra's points
    within 3 mm of the line through c along n and 10 mm of c, as calipers set across it."""
    r = v.loc - c
    along = r @ n
    off = np.linalg.norm(r - along[:, None] * n[None, :], axis=1)
    sel = along[(off <= CALIPER_MM) & (np.abs(along) <= 10.0)]
    return G.extent(sel, v.footprint(n)) if len(sel) >= G.MIN_CHORD_POINTS else NAN


def lamina_sheet(v: Vertebra, side: int, ridge: np.ndarray) -> np.ndarray:
    """Which voxels are one lamina's medial sheet: behind the body, between the spinous process
    and the canal's lateral edge, within the canal ring's middle heights."""
    rings = v.full_rings()
    if not rings:
        return np.zeros(len(v.loc), bool)
    zlo, zhi = np.percentile([s.z for s in rings], [25, 75])
    half = 0.5 * float(np.median([s.width for s in rings]))
    off = side * (v.loc[:, 0] - v.midline)
    y, z = v.loc[:, 1], v.loc[:, 2]
    return (ridge & (off >= SPINOUS_HALF_MM + 1.0) & (off <= half) & (y < v.wall - 2.0)
            & (y > v.wall_post - 15.0) & (z >= zlo - 1.0) & (z <= zhi + 1.0))


def laminae(v: Vertebra) -> Dict[str, float]:
    out = {"lamina_thickness": NAN, "lamina_angle": NAN}
    ridge = medial_sheet(v)
    traces, thick = {}, {}
    for side, name in SIDES:
        sheet = lamina_sheet(v, side, ridge)
        if sheet.sum() < G.MIN_CHORD_POINTS:
            continue
        axes, c = principal(v.loc[sheet])
        n = axes[2]
        perp = caliper(v, c, n)
        across = math.hypot(n[0], n[1])
        thick[name] = perp / across if across > 1e-6 else NAN
        t = np.array([n[1], -n[0]]) / max(across, 1e-9)
        traces[name] = t if side * t[0] > 0 else -t           # pointing out to its own side
        out["lamina_thickness_" + name] = thick[name]
    if len(thick) == 2:
        out["lamina_thickness"] = 0.5 * (thick["right"] + thick["left"])
        a, b = traces["right"], traces["left"]
        out["lamina_angle"] = math.degrees(math.acos(float(np.clip(a @ b, -1.0, 1.0))))
    return out


def facet_section(pts: np.ndarray, layer: float) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """The section half-way up (or down) the process: its long axis in (x, y) and its centroid."""
    if len(pts) < G.MIN_CHORD_POINTS:
        return None
    zmid = 0.5 * (pts[:, 2].min() + pts[:, 2].max())
    sec = pts[np.abs(pts[:, 2] - zmid) <= max(0.5 * layer, 1.0)]
    if len(sec) < G.MIN_CHORD_POINTS:
        return None
    axes, c = principal(sec[:, :2])
    return axes[0], c


def facets(v: Vertebra) -> Tuple[Dict[str, float], str]:
    B = v.body_pts
    out: Dict[str, float] = {}
    if len(B) < G.MIN_BODY_VOXELS:
        return out, "no body to set the facets' heights by"
    post = B[B[:, 1] <= v.wall + 3.0]
    top, bottom = G.surface(post[:, 2], True, v.fz), G.surface(post[:, 2], False, v.fz)
    behind = v.loc[v.loc[:, 1] < v.wall]
    notes = []
    for which, sel in (("sup", behind[:, 2] > top + FACET_RISE_MM), ("inf", behind[:, 2] < bottom - FACET_RISE_MM)):
        cents, angles = {}, {}
        for side, name in SIDES:
            pts = behind[sel & (side * (behind[:, 0] - v.midline) >= PROCESS_CLEAR_MM)]
            got = facet_section(pts, v.fz)
            if got is None:
                continue
            line, c = got
            cents[name] = c
            angles[name] = math.degrees(math.acos(min(1.0, abs(float(line[1])))))
            out["facet_angle_axial_%s_%s" % (which, name)] = angles[name]
        if len(cents) == 2:
            out["interfacet_w_" + which] = float(abs(cents["right"][0] - cents["left"][0]))
            out["facet_angle_axial_" + which] = 0.5 * (angles["right"] + angles["left"])
            out["facet_tropism_" + which] = abs(angles["right"] - angles["left"])
        else:
            notes.append("no pair of %s articular processes found" % ("superior" if which == "sup" else "inferior"))
    return out, "; ".join(notes)
