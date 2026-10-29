"""The oracle's constructions in a radiograph: FleXray's and FluXray's exact camera, a 3-D
measure's two ends carried into the view that rendered the image, and what each measure keeps
there.

The owner's asks of 29 October 2026: at 14:59 UTC, pair the CT volumes with their synthetic
X-rays, FluXray's among them, and make the same thing work in 2-D; at 15:16 UTC, the corners and
landmarks come from the morphometry engine (the thread "Extract morphometrics from gold tier 3
CT", bordercall draft pull request 30), projected, and never from a fit to the silhouette.

Nothing here finds a landmark in an image. A 2-D truth is a 3-D construction projected: the
world-millimetre ends of a measure's line as the engine draws it (morphoview.lines.Line: key,
level, a, b and extra lines), or an oracle Reading's landmarks (oracle.py), carried through the
same camera that rendered the image, so the truth lands on the pixel the structure fell on. That
is the one thing kept from XRSpinoPelvic1K (spine-program's 07_plain_film_level_id,
docs/xrspinopelvic1k/README.md): the S1 plate fitted from a lateral silhouette was 26 to 32
degrees wrong at every slab fraction, since the ala superimposes on the body, and the same plate
fitted in 3-D and projected landed within 0.6; its corner finder is not used, and nothing here
imports it. The engine's own constructions give the points: the posterior corner where the
body's posterior wall meets the end-plate on the midline (column.wall_corner), the plate's line
rim to rim from caliper bands 2.5 mm inside the corners (body.plate_rims, rim_plane), Panjabi's
plate slabs for the lateral ends, Zindrick's coronal slabs for the pedicle eye, Eisenstein's
apex line for the lateral canal limit. This module takes any of them as a pair of points and
imports nothing of the engine, so it runs before that pull request lands.

The camera is nanodrr 0.1.7's, which FleXray's renderer and SchwingNet's render blocks drive
(the wheel's camera/extrinsics.py, camera/intrinsics.py and drr/renderer.py, read on 29 October
2026):

- camera-to-world is pose @ reorient, with pose = [R | R t + iso]: R the ZXY intrinsic Euler
  rotation of (alpha, beta, gamma) in degrees, Rz(alpha) Rx(beta) Ry(gamma); t the source's
  position relative to the isocentre; iso the volume's centre, the affine at (shape - 1) / 2,
  torchio's get_center. reorient for "AP" sends the camera's x to -x, y to -z and z to -y of the
  pose's frame; "PA" sends z to +y; None keeps z and flips x and y.
- The source sits at the camera's origin and the detector is the plane z = SDD; pixel (u, v),
  column u and row v, is centred at x = (u + 1/2 - cx) delx and y = (v + 1/2 - cy) dely with
  cx = x0 / delx + W / 2 and cy = y0 / dely + H / 2.
- An orthographic render moves each ray's source to its target less SDD along z, so the rays
  run parallel to z and nothing is magnified.

So at alpha 0 the source stands in front of the patient, t = (0, SOD, 0) in the RAS world a NIfTI
affine maps into, and the beam runs front to back: an AP projection with the head up and the
patient's left on the image's right, as a film is hung. alpha +90 puts the source at the
patient's left, a lateral with the front of the body on the image's left; alpha -90 the reverse;
beta tilts the beam up or down the column. FluXray's 90 poses (SchwingNet's
src/schwingnet/render_blocks.py: GRID_Y_MM, GRID_Z_MM, GRID_ALPHA_DEG, grid_pose) are the
Cartesian product of y, then z, then alpha, in that order, with x, beta and gamma 0, the detector
1250 mm from the source with 0.6 mm pixels on 1024 of them, the stored images 256 pixels across.

What a measure keeps in a view is geometry first and visibility second. The geometry is computed
here: a length keeps the share of itself that lies across the beam (foreshortening), an angle
keeps its value where its plane faces the detector (plane_tilt_deg), an area keeps the share
|n . r| of itself times the magnification squared (area_factor); the magnification is the source
to detector distance over the point's depth, so it differs from point to point and from view to
view. Whether the projected landmark can be seen through what else the beam crosses is not
geometry: it is the reading per measure of the clinical reread's recipes (bordercall
research_notes/clinical-reread/synthesis/measures.md, the radiograph part of each) and, in the
end, a measured agreement on renders, which spine-program's 05_ct_morphometry_parity names
PAR-2. research_notes/measures-to-2d/ holds both for every key of the reread's vocabulary.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

NAN = float("nan")

# nanodrr's reorientation of the camera's axes into the pose's frame (camera/extrinsics.py).
REORIENT: Dict[Optional[str], np.ndarray] = {
    "AP": np.array([[-1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, -1.0, 0.0]]),
    "PA": np.array([[-1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]]),
    None: np.array([[-1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, 1.0]]),
}

# FluXray's fixed poses (SchwingNet src/schwingnet/render_blocks.py), in the paper's order.
FLUXRAY_Y_MM = (650.0, 900.0, 1150.0)
FLUXRAY_Z_MM = (-300.0, -200.0, -100.0, 0.0, 100.0, 200.0)
FLUXRAY_ALPHA_DEG = (0.0, 45.0, -45.0, 90.0, -90.0)
FLUXRAY_POSES = len(FLUXRAY_Y_MM) * len(FLUXRAY_Z_MM) * len(FLUXRAY_ALPHA_DEG)
FLUXRAY_SDD_MM = 1250.0
FLUXRAY_PIXEL_MM = 0.6
FLUXRAY_DETECTOR_PX = 1024
FLUXRAY_STORED_PX = 256

# FleXray's MOOSE profile (SchwingNet tools/render_blocks.py: MOOSE_POSE, SDD_RANGE, DELX_RANGE),
# kept here so a sampled pose can be checked against the range it came from.
FLEXRAY_ALPHA_DEG = (-180.0, 180.0)
FLEXRAY_BETA_DEG = (-30.0, 30.0)
FLEXRAY_X_MM = (-100.0, 100.0)
FLEXRAY_Y_MM = (500.0, 900.0)
FLEXRAY_Z_MM = (-100.0, 100.0)
FLEXRAY_SDD_MM = (1150.0, 1250.0)
FLEXRAY_PIXEL_MM = (1.25, 2.25)
FLEXRAY_DETECTOR_PX = 256

# Where a measure's geometry stops being readable in a view: a length that keeps under
# FORESHORTENING_FLOOR of itself (a chord tilted more than 26 degrees out of the detector's
# plane), an angle whose plane leans more than PLANE_TILT_MAX_DEG off the detector's, an area
# whose face shows under AREA_FACTOR_FLOOR of itself. The thresholds are the module's own and
# are set beside each verdict, not hidden in it.
FORESHORTENING_FLOOR = 0.9
PLANE_TILT_MAX_DEG = 15.0
AREA_FACTOR_FLOOR = 0.9


def unit(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    if n < 1e-12:
        raise ValueError("a zero vector has no direction")
    return np.asarray(v, float) / n


def rotation_x(deg: float) -> np.ndarray:
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])


def rotation_y(deg: float) -> np.ndarray:
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])


def rotation_z(deg: float) -> np.ndarray:
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def rotation_zxy(alpha: float, beta: float, gamma: float) -> np.ndarray:
    """roma's intrinsic "ZXY" rotation of the three angles in degrees: about z, then about the
    turned x, then about the turned y, which as matrices is Rz(alpha) Rx(beta) Ry(gamma)."""
    return rotation_z(alpha) @ rotation_x(beta) @ rotation_y(gamma)


def volume_centre(affine: np.ndarray, shape: Sequence[int]) -> np.ndarray:
    """The isocentre nanodrr takes when none is given: the world point at the voxel index
    (shape - 1) / 2, torchio's get_center of the volume as loaded."""
    a = np.asarray(affine, float)
    idx = (np.asarray(shape[:3], float) - 1.0) / 2.0
    return a[:3, :3] @ idx + a[:3, 3]


def fluxray_pose(index: int) -> Tuple[float, float, float]:
    """One of FluXray's 90 poses as (alpha in degrees, y in mm, z in mm), the same index as
    schwingnet.render_blocks.grid_pose: index 0 is y 650, z -300, alpha 0; index 1 the same at
    alpha 45; index 5 z -200."""
    if not 0 <= index < FLUXRAY_POSES:
        raise ValueError("FluXray has %d poses; %d is none of them" % (FLUXRAY_POSES, index))
    y_index, rest = divmod(index, len(FLUXRAY_Z_MM) * len(FLUXRAY_ALPHA_DEG))
    z_index, alpha_index = divmod(rest, len(FLUXRAY_ALPHA_DEG))
    return FLUXRAY_ALPHA_DEG[alpha_index], FLUXRAY_Y_MM[y_index], FLUXRAY_Z_MM[z_index]


@dataclass(frozen=True)
class Projected:
    """Points in a view: u and v the pixel coordinates (a point imaged at the centre of pixel
    (u, v) has exactly those values, so 0 is the first column's middle and W - 1 the last's),
    mm_u and mm_v the same from the detector's centre in millimetres, depth the distance from
    the source along the central axis, magnification the source to detector distance over the
    depth (1 under parallel rays), visible where the point lies between the source and the
    detector and inside it. A point with a NaN coordinate stays NaN and is not visible."""
    u: np.ndarray
    v: np.ndarray
    mm_u: np.ndarray
    mm_v: np.ndarray
    depth: np.ndarray
    magnification: np.ndarray
    visible: np.ndarray

    @property
    def uv(self) -> np.ndarray:
        return np.stack([self.u, self.v], axis=-1)

    @property
    def mm(self) -> np.ndarray:
        return np.stack([self.mm_u, self.mm_v], axis=-1)


@dataclass(frozen=True)
class Camera:
    """nanodrr's cone-beam (or parallel-beam) camera, built from the pose a render records.

    rotation is (alpha, beta, gamma) in degrees, translation the source relative to the
    isocentre in mm, both as the render was asked for; isocentre is the world point they are
    about; sdd the source to detector distance; delx and dely the pixel pitch on the detector;
    x0 and y0 the principal point's offset; height and width the detector in pixels;
    orthographic whether the rays ran parallel; orientation nanodrr's reorientation key."""
    rotation: Tuple[float, float, float]
    translation: Tuple[float, float, float]
    isocentre: Tuple[float, float, float]
    sdd: float
    delx: float
    dely: float
    height: int
    width: int
    x0: float = 0.0
    y0: float = 0.0
    orthographic: bool = False
    orientation: Optional[str] = "AP"

    def __post_init__(self) -> None:
        if self.orientation not in REORIENT:
            raise ValueError("orientation must be 'AP', 'PA' or None, not %r" % (self.orientation,))
        if not (self.sdd > 0 and self.delx > 0 and self.dely > 0 and self.height > 0 and self.width > 0):
            raise ValueError("a camera needs a positive detector distance, pixel pitch and size")

    # ---- the frames ----------------------------------------------------------------------------

    @property
    def pose_rotation(self) -> np.ndarray:
        return rotation_zxy(*self.rotation)

    @property
    def source(self) -> np.ndarray:
        """The source in the world: R t + iso, where the camera's origin lands."""
        return self.pose_rotation @ np.asarray(self.translation, float) + np.asarray(self.isocentre, float)

    @property
    def camera_axes(self) -> np.ndarray:
        """Columns are the camera's x, y and z in the world: R @ reorient."""
        return self.pose_rotation @ REORIENT[self.orientation]

    @property
    def rt_inv(self) -> np.ndarray:
        """The 4 by 4 camera-to-world matrix nanodrr renders with."""
        m = np.eye(4)
        m[:3, :3] = self.camera_axes
        m[:3, 3] = self.source
        return m

    @property
    def cx(self) -> float:
        return self.x0 / self.delx + self.width / 2.0

    @property
    def cy(self) -> float:
        return self.y0 / self.dely + self.height / 2.0

    def to_camera(self, points: np.ndarray) -> np.ndarray:
        """World points (..., 3) in the camera's frame: x across the detector, y down it, z
        along the central ray."""
        P = np.asarray(points, float)
        return (P - self.source) @ self.camera_axes

    def to_world(self, local: np.ndarray) -> np.ndarray:
        L = np.asarray(local, float)
        return L @ self.camera_axes.T + self.source

    # ---- projecting --------------------------------------------------------------------------

    def project(self, points: np.ndarray) -> Projected:
        p = self.to_camera(points)
        depth = p[..., 2]
        with np.errstate(divide="ignore", invalid="ignore"):
            if self.orthographic:
                scale = np.ones_like(depth)
            else:
                scale = self.sdd / depth
            mm_u = p[..., 0] * scale
            mm_v = p[..., 1] * scale
        U = mm_u / self.delx + self.cx
        V = mm_v / self.dely + self.cy
        u, v = U - 0.5, V - 0.5
        finite = np.isfinite(u) & np.isfinite(v) & np.isfinite(depth)
        with np.errstate(invalid="ignore"):
            inside = (U >= 0.0) & (U < self.width) & (V >= 0.0) & (V < self.height)
            between = (depth > 0.0) & (depth < self.sdd)
        visible = finite & inside & between
        return Projected(u, v, mm_u, mm_v, depth, scale, visible)

    def back_project(self, u: np.ndarray, v: np.ndarray, depth: np.ndarray) -> np.ndarray:
        """The world point that projects to pixel (u, v) at the given depth: project's inverse."""
        U, V, d = np.asarray(u, float) + 0.5, np.asarray(v, float) + 0.5, np.asarray(depth, float)
        scale = 1.0 if self.orthographic else d / self.sdd
        local = np.stack([(U - self.cx) * self.delx * scale, (V - self.cy) * self.dely * scale, d], axis=-1)
        return self.to_world(local)

    def beam(self, points: np.ndarray) -> np.ndarray:
        """The unit direction the ray through each point travels in, source to detector, in the
        world; under parallel rays the camera's z for every point."""
        P = np.asarray(points, float)
        if self.orthographic:
            return np.broadcast_to(self.camera_axes[:, 2], P.shape).copy()
        d = P - self.source
        return d / np.linalg.norm(d, axis=-1, keepdims=True)

    def magnification_at(self, points: np.ndarray) -> np.ndarray:
        return self.project(points).magnification

    # ---- the renders' cameras ------------------------------------------------------------------

    @classmethod
    def flexray(cls, alpha: float, beta: float, gamma: float, xyz: Sequence[float], sdd: float, delx: float,
                dely: float, height: int, width: int, isocentre: Sequence[float], orthographic: bool = False,
                orientation: Optional[str] = "AP") -> "Camera":
        """The camera of one FleXray render, from the pose it recorded."""
        return cls((float(alpha), float(beta), float(gamma)), tuple(float(t) for t in xyz),
                   tuple(float(c) for c in isocentre), float(sdd), float(delx), float(dely), int(height), int(width),
                   0.0, 0.0, bool(orthographic), orientation)

    @classmethod
    def fluxray(cls, index: int, isocentre: Sequence[float], width: int = FLUXRAY_DETECTOR_PX) -> "Camera":
        """FluXray's pose `index` about the volume's centre. The paper rendered 1024 pixels of
        0.6 mm and stored 256, so a stored image's camera is the same detector with pixels four
        times as wide: pass width 256 for it, and a projected coordinate u on the stored image
        is (u_1024 + 1/2) / 4 - 1/2."""
        alpha, y, z = fluxray_pose(index)
        pitch = FLUXRAY_PIXEL_MM * FLUXRAY_DETECTOR_PX / float(width)
        return cls((alpha, 0.0, 0.0), (0.0, y, z), tuple(float(c) for c in isocentre), FLUXRAY_SDD_MM, pitch, pitch,
                   int(width), int(width), 0.0, 0.0, False, "AP")

    def record(self) -> Dict[str, object]:
        """The pose as a plain record, to write beside a render's truth."""
        return {"alpha": self.rotation[0], "beta": self.rotation[1], "gamma": self.rotation[2],
                "x": self.translation[0], "y": self.translation[1], "z": self.translation[2],
                "isocentre": list(self.isocentre), "sdd": self.sdd, "delx": self.delx, "dely": self.dely,
                "x0": self.x0, "y0": self.y0, "height": self.height, "width": self.width,
                "orthographic": self.orthographic, "orientation": self.orientation}

    @classmethod
    def from_record(cls, r: Dict[str, object]) -> "Camera":
        return cls((float(r["alpha"]), float(r["beta"]), float(r["gamma"])),
                   (float(r["x"]), float(r["y"]), float(r["z"])), tuple(float(c) for c in r["isocentre"]),
                   float(r["sdd"]), float(r["delx"]), float(r["dely"]), int(r["height"]), int(r["width"]),
                   float(r.get("x0", 0.0)), float(r.get("y0", 0.0)), bool(r.get("orthographic", False)),
                   r.get("orientation", "AP"))


# ---- the view against a vertebra's frame ------------------------------------------------------

@dataclass(frozen=True)
class View:
    """How the beam crosses a vertebra, in the vertebra's own frame (x to the patient's right, y
    anterior, z up the column, as scanimport.geometry's Frame and the engine's anatomy.build
    have it): the axis it runs nearest, a name for the view, the beam's angle off that axis, and
    the beam's direction in the frame, so a view angle is expressed against the same frame the
    measures were taken in (the clinical reread's recipe F, measures.md 2.2)."""
    axis: str
    name: str
    obliquity_deg: float
    beam: Tuple[float, float, float]

    @property
    def lateral(self) -> bool:
        return self.axis == "x"

    @property
    def frontal(self) -> bool:
        return self.axis == "y"


def view_in_frame(cam: Camera, frame, at: Optional[np.ndarray] = None) -> View:
    """The view of `frame` (anything with ex, ey, ez and origin) from `cam`, read on the ray
    through `at`, the frame's origin unless given."""
    X = np.asarray(frame.origin if at is None else at, float)
    d = cam.beam(X[None, :])[0]
    comps = (float(d @ frame.ex), float(d @ frame.ey), float(d @ frame.ez))
    k = int(np.argmax(np.abs(comps)))
    axis = "xyz"[k]
    sign = comps[k]
    if axis == "y":
        name = "AP" if sign < 0 else "PA"
    elif axis == "x":
        name = "lateral from the left" if sign > 0 else "lateral from the right"
    else:
        name = "axial from above" if sign < 0 else "axial from below"
    obliquity = math.degrees(math.acos(min(1.0, abs(sign))))
    return View(axis, name, obliquity, comps)


def beam_angles(cam: Camera, frame, at: Optional[np.ndarray] = None) -> Dict[str, float]:
    """The beam's angle, in degrees, to each axis of the frame, 0 along it either way."""
    v = view_in_frame(cam, frame, at)
    return {ax: math.degrees(math.acos(min(1.0, abs(c)))) for ax, c in zip("xyz", v.beam)}


# ---- what a measure keeps --------------------------------------------------------------------

def plane_tilt_deg(cam: Camera, normal_world: np.ndarray, at: np.ndarray) -> float:
    """Degrees between a plane's normal and the ray through `at`: 0 where the plane faces the
    detector, so an angle drawn in it keeps its value, 90 where it is seen edge on."""
    n = unit(np.asarray(normal_world, float))
    d = cam.beam(np.asarray(at, float)[None, :])[0]
    return math.degrees(math.acos(min(1.0, abs(float(n @ d)))))


def area_factor(cam: Camera, normal_world: np.ndarray, at: np.ndarray) -> float:
    """The share of a planar patch's area that reaches the detector, before magnification:
    |n . r|, the cosine of plane_tilt_deg."""
    return math.cos(math.radians(plane_tilt_deg(cam, normal_world, at)))


def readable_length(foreshortening: float, floor: float = FORESHORTENING_FLOOR) -> bool:
    return bool(np.isfinite(foreshortening)) and foreshortening >= floor


def readable_angle(tilt_deg: float, limit: float = PLANE_TILT_MAX_DEG) -> bool:
    return bool(np.isfinite(tilt_deg)) and tilt_deg <= limit


def readable_area(factor: float, floor: float = AREA_FACTOR_FLOOR) -> bool:
    return bool(np.isfinite(factor)) and factor >= floor


# ---- segments: a measure as two world points ----------------------------------------------------

@dataclass
class Segment:
    """A measure as the engine draws it: its key, its level, its two ends in world millimetres,
    the value the engine measured (NaN where it did not) and any further lines drawn with it."""
    key: str
    level: str
    a: np.ndarray
    b: np.ndarray
    value: float = NAN
    extra: Dict[str, Tuple[np.ndarray, np.ndarray]] = field(default_factory=dict)

    @property
    def length(self) -> float:
        return float(np.linalg.norm(np.asarray(self.b, float) - np.asarray(self.a, float)))


def segments_from(lines: Iterable[object]) -> List[Segment]:
    """Segments from the engine's lines, or from anything with key, level, a and b (value and
    extra where it has them), or from tuples (key, level, a, b[, value])."""
    out = []
    for ln in lines:
        if isinstance(ln, Segment):
            out.append(ln)
        elif isinstance(ln, (tuple, list)):
            key, level, a, b = ln[:4]
            value = float(ln[4]) if len(ln) > 4 else NAN
            out.append(Segment(str(key), str(level), np.asarray(a, float), np.asarray(b, float), value))
        else:
            extra = {str(k): (np.asarray(p, float), np.asarray(q, float))
                     for k, (p, q) in dict(getattr(ln, "extra", {}) or {}).items()}
            value = getattr(ln, "value", NAN)
            out.append(Segment(str(ln.key), str(ln.level), np.asarray(ln.a, float), np.asarray(ln.b, float),
                               float(value) if value is not None else NAN, extra))
    return out


@dataclass
class SegmentImage:
    """A segment in a view: its ends in pixels, its length on the detector in millimetres, the
    same brought back to the object by the magnification at its middle, its share of the true
    length (foreshortening), whether both ends are visible, the magnification and depth at each
    end, and its extra lines projected the same way."""
    key: str
    level: str
    a_uv: np.ndarray
    b_uv: np.ndarray
    true_mm: float
    detector_mm: float
    object_mm: float
    foreshortening: float
    visible: bool
    magnification: Tuple[float, float]
    depth: Tuple[float, float]
    extra: Dict[str, "SegmentImage"] = field(default_factory=dict)

    @property
    def readable(self) -> bool:
        return self.visible and readable_length(self.foreshortening)

    def row(self) -> Dict[str, object]:
        return {"key": self.key, "level": self.level, "u_a": float(self.a_uv[0]), "v_a": float(self.a_uv[1]),
                "u_b": float(self.b_uv[0]), "v_b": float(self.b_uv[1]), "true_mm": self.true_mm,
                "detector_mm": self.detector_mm, "object_mm": self.object_mm, "foreshortening": self.foreshortening,
                "visible": self.visible, "magnification": float(np.mean(self.magnification)), "readable": self.readable}


def project_pair(cam: Camera, key: str, level: str, a: np.ndarray, b: np.ndarray) -> SegmentImage:
    P = cam.project(np.stack([np.asarray(a, float), np.asarray(b, float)]))
    true = float(np.linalg.norm(np.asarray(b, float) - np.asarray(a, float)))
    det = float(np.linalg.norm(P.mm[1] - P.mm[0]))
    mid = cam.project(0.5 * (np.asarray(a, float) + np.asarray(b, float))[None, :]).magnification[0]
    obj = det / float(mid) if np.isfinite(mid) and mid > 0 else NAN
    short = obj / true if true > 0 else NAN
    return SegmentImage(key, level, P.uv[0], P.uv[1], true, det, obj, short, bool(P.visible.all()),
                        (float(P.magnification[0]), float(P.magnification[1])), (float(P.depth[0]), float(P.depth[1])))


def project_segments(cam: Camera, segments: Iterable[object]) -> List[SegmentImage]:
    """Every segment in the view, its extra lines with it."""
    out = []
    for s in segments_from(segments):
        img = project_pair(cam, s.key, s.level, s.a, s.b)
        for name, (p, q) in s.extra.items():
            img.extra[name] = project_pair(cam, name, s.level, p, q)
        out.append(img)
    return out


def truth_rows(images: Iterable[SegmentImage]) -> List[Dict[str, object]]:
    """One plain row per segment, the truth written beside a render; the extra lines follow
    their segment with the segment's key before their name."""
    rows = []
    for im in images:
        rows.append(im.row())
        for name, ex in im.extra.items():
            r = ex.row()
            r["key"] = "%s: %s" % (im.key, name)
            rows.append(r)
    return rows


# ---- an oracle reading in a view ----------------------------------------------------------------

@dataclass
class MeasureImage:
    """One measurement of a Reading in a view: its landmarks in pixels, the value the
    measurement's own rule (specs.py) gives on the projected points, in the object's
    millimetres (a length over the magnification, an area over its square, an angle as it
    stands), the oracle's 3-D value, their ratio, and whether every landmark is visible."""
    key: str
    kind: str
    points_uv: np.ndarray
    value_2d: float
    value_3d: float
    ratio: float
    visible: bool
    magnification: float

    @property
    def readable(self) -> bool:
        if not self.visible or not np.isfinite(self.value_2d):
            return False
        if self.kind == "length":
            return readable_length(self.ratio)
        if self.kind == "area":
            return readable_area(self.ratio)
        return True


def project_reading(cam: Camera, reading, keys: Sequence[str]) -> Dict[str, MeasureImage]:
    """An oracle Reading's measurements in the view, each valued by specs.py's own rule on the
    projected landmarks, so the 2-D number and the 2-D line never disagree either."""
    from . import specs as S
    keys = list(keys)
    L = np.asarray(reading.landmarks(keys), float)
    P = cam.project(L)
    flat = np.concatenate([P.mm, np.zeros((len(L), 1))], axis=1)
    values_2d = np.asarray(S.values(flat[None, :, :], keys))[0]
    values_3d = np.asarray(reading.values(keys), float)
    names = S.landmarks(keys)
    out: Dict[str, MeasureImage] = {}
    for j, key in enumerate(keys):
        spec = S.select([key])[0]
        rows = [names.index(p) for p in spec.points]
        mags = P.magnification[rows]
        mag = float(np.mean(mags)) if np.isfinite(mags).all() else NAN
        v2 = float(values_2d[j]) / (mag ** spec.size_power) if np.isfinite(mag) and mag > 0 else NAN
        v3 = float(values_3d[j])
        ratio = v2 / v3 if np.isfinite(v2) and np.isfinite(v3) and v3 != 0 else NAN
        out[key] = MeasureImage(key, spec.kind, P.uv[rows], v2, v3, ratio, bool(P.visible[rows].all()), mag)
    return out


def camera_from_pose_record(record: Dict[str, object], isocentre: Sequence[float], height: int, width: int,
                            orientation: Optional[str] = "AP") -> Camera:
    """The camera of a render SchwingNet's tools/flexray_render.py recorded (pose_record:
    rot_deg, xyz_mm, orthographic, sdd, delx and the grid index), given the isocentre the
    render used, which that record does not carry: the crop's centre (volume_centre) under the
    volume-centre scheme, and under the random-label scheme the drawn label's centroid, which
    is read back from the render's own label record and not from the pose."""
    rot = [float(v) for v in record["rot_deg"]]
    xyz = [float(v) for v in record["xyz_mm"]]
    delx = float(record["delx"])
    return Camera.flexray(rot[0], rot[1], rot[2], xyz, float(record["sdd"]), delx, float(record.get("dely", delx)),
                          height, width, isocentre, bool(record.get("orthographic", False)), orientation)
