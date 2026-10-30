"""World points onto the synthetic X-rays FleXray renders from the same CT, through FleXray's own
camera, so a line or a shape drawn in the mask's world lands on the render where the render put
the bone it was drawn on.

FleXray 1.0.2 renders a view through fxr.drr.render_drr on nanoDRR 0.1.5, and its camera is
three pieces of arithmetic this module copies. The camera-to-world matrix is the pose, the ZXY
Euler angles' rotation R with the translation R xyz + isocentre, times a fixed turn for the
acquisition's orientation (nanodrr/camera/extrinsics.py, make_rt_inv, through nanodrr's
geometry.convert, which rotates about the isocentre). The intrinsics are the focal lengths
sdd / delx and sdd / dely and the principal point x0 / delx + W / 2, y0 / dely + H / 2
(fxr/drr/intrinsics.py, build_render_intrinsics, as nanodrr/camera/intrinsics.py, make_k_inv).
And one ray a pixel runs from the source at the camera's origin, or under parallel rays from the
source's plane, to the pixel's centre on the detector at depth sdd, the pixel in row r and column
c centred at u = c + 0.5, v = r + 0.5 (nanodrr/drr/renderer.py, _make_tgt and _make_src); the
render's image is that grid of rays, row by row, which SchwingNet writes as it is
(tools/flexray_render.py, save_png). The world is the CT's, a voxel's place by the CT's affine
(fxr/drr/subjects.py, subject_from_tensors), which a crop moves to its first voxel without moving
the world (fxr/datasets/ct_crops.py, offset_affine). A mask read with its own affine from the
same scan, as morphometry reads it (scanimport.volume.load), shares that world, so a point's
pixel is the pixel whose ray passes through the point. What a view rendered of the CT is a Crop of
its slices; a point outside it has its pixel all the same, with nothing of the CT there to cast a
shadow.

Under the AP orientation the camera's x runs to the patient's left, its y to the feet and its z,
the beam, from the front to the back, so a render with no rotation shows the patient's right on
the left of the image and the head at the top, as a radiograph is read.

A point is on the render where the render sampled it: between the source and the detector and on
the detector (Projected.in_beam). A length parallel to the detector is magnified by sdd over its
depth under a cone beam and not at all under parallel rays (Camera.magnification), so a length
drawn on the render, times the pixel spacing over that magnification, is the length in the
patient as far as the line lies parallel to the detector.

FleXray's segmentation reads an image on the canvas its model's preprocessing.json names, at
FleXray's defaults, which its training renders keep, a square of 256 pixels, the image padded to a
square at its centre and resized (fxr/inference/preprocessing.py, ImagePreprocessing.from_metadata,
content_box and _pad_to_square; scanimport.film, CANVAS); to_canvas and from_canvas carry a point
between the render and a square canvas so padded, of any side.

tests/test_projection.py holds the copy to FleXray's own matrices and rays and to what FleXray
rendered of a phantom, recorded from FleXray 1.0.2 by tests/flexray_record.py in
tests/fixtures/flexray.json, and to FleXray itself where it is installed.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Optional, Sequence, Tuple

import numpy as np

# nanoDRR's fixed turn from the camera's axes to the world's, by acquisition orientation
# (nanodrr/camera/extrinsics.py, _ORIENTATION_MATRICES), applied after the pose
ORIENTATIONS = {
    "AP": ((-1.0, 0.0, 0.0), (0.0, 0.0, -1.0), (0.0, -1.0, 0.0)),
    "PA": ((-1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0)),
    None: ((-1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, 1.0)),
}
CANVAS = 256                    # the side of FleXray's inference canvas, in pixels
# the releases whose camera this module copies and whose renders tests/fixtures/flexray.json holds
CHECKED = {"flexray": "1.0.2", "nanodrr": "0.1.5"}


def zxy(degrees: Sequence[float]) -> np.ndarray:
    """The rotation of ZXY Euler angles in degrees: about z, then about the turned x, then about
    the twice-turned y, Rz(a) Rx(b) Ry(c), as nanoDRR turns them (roma.euler_to_rotmat("ZXY"),
    upper case being roma's intrinsic convention)."""
    a, b, c = (math.radians(float(d)) for d in degrees)
    rz = np.array([[math.cos(a), -math.sin(a), 0.0], [math.sin(a), math.cos(a), 0.0], [0.0, 0.0, 1.0]])
    rx = np.array([[1.0, 0.0, 0.0], [0.0, math.cos(b), -math.sin(b)], [0.0, math.sin(b), math.cos(b)]])
    ry = np.array([[math.cos(c), 0.0, math.sin(c)], [0.0, 1.0, 0.0], [-math.sin(c), 0.0, math.cos(c)]])
    return rz @ rx @ ry


@dataclass(frozen=True)
class View:
    """One render's camera as FleXray's request gives it (fxr.drr.DRRRenderRequest): the ZXY Euler
    angles in degrees, the source's place from the isocentre in mm before the rotation, the
    isocentre in the world's mm, the source-to-detector distance, the pixel spacing, the principal
    point's offset from the detector's centre in mm, the detector's size in pixels, the beam and
    the orientation."""
    rot_deg: Tuple[float, float, float]
    xyz_mm: Tuple[float, float, float]
    isocentre_mm: Tuple[float, float, float]
    sdd: float
    delx: float
    height: int
    width: int
    dely: Optional[float] = None
    x0: float = 0.0
    y0: float = 0.0
    orthographic: bool = False
    orientation: Optional[str] = "AP"

    def __post_init__(self):
        for name in ("rot_deg", "xyz_mm", "isocentre_mm"):
            value = tuple(float(x) for x in getattr(self, name))
            if len(value) != 3:
                raise ValueError("%s takes three numbers" % name)
            object.__setattr__(self, name, value)
        if self.orientation not in ORIENTATIONS:
            raise ValueError("no orientation %r; nanoDRR knows AP, PA and none" % (self.orientation,))
        if not (self.sdd > 0 and self.delx > 0 and self.pixel_y > 0 and self.height > 0 and self.width > 0):
            raise ValueError("a view's distance, pixels and size are positive")

    @classmethod
    def from_manifest(cls, row: dict, detector: int, orientation: Optional[str] = "AP") -> "View":
        """A view of SchwingNet's render manifest (tools/flexray_render.py, the row's pose with its
        rot_deg, xyz_mm, orthographic, sdd and delx, and its isocentre's point_mm) on the square
        detector of `detector` pixels its render blocks name, dely following delx and the principal
        point at the centre, as FleXray's runtime and SchwingNet's request pass them
        (fxr/models/camera/runtime.py, sample_request; tools/render_blocks.py, request and
        ORIENTATION)."""
        pose = row["pose"]
        return cls(rot_deg=pose["rot_deg"], xyz_mm=pose["xyz_mm"], isocentre_mm=row["isocentre"]["point_mm"],
                   sdd=float(pose["sdd"]), delx=float(pose["delx"]), height=int(detector), width=int(detector),
                   orthographic=bool(pose["orthographic"]), orientation=orientation)

    @property
    def pixel_y(self) -> float:
        return float(self.delx if self.dely is None else self.dely)

    def as_record(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Crop:
    """The slices of the CT a view rendered: FleXray's crop of the volume along its last voxel
    axis, the source slices z_start up to z_stop, with air slices padded before and after where
    the volume is shorter than a crop (fxr/datasets/ct_crops.py, CropSpec and crop_z), to which
    SchwingNet's render cuts the CT and its labels for each view and which its manifest's row
    records (tools/render_blocks.py, cut; tools/flexray_render.py). Bone outside it is not on the
    render, though the beam passes where it lay. The crop moves the voxels' origin and not the
    world (offset_affine), so a world point is among the slices rendered where its nearest voxel
    of the uncut CT is."""
    z_start: int
    z_stop: int
    pad_before: int = 0
    pad_after: int = 0

    def __post_init__(self):
        if not (0 <= self.z_start < self.z_stop and self.pad_before >= 0 and self.pad_after >= 0):
            raise ValueError("a crop runs from slice z_start up to z_stop, with no pad or more")

    @classmethod
    def from_record(cls, record: Optional[dict]) -> Optional["Crop"]:
        """A manifest row's crop, or a view file's, as tools/flexray_render.py writes it; none
        where it names none."""
        if not record:
            return None
        return cls(int(record["z_start"]), int(record["z_stop"]), int(record.get("pad_before", 0)),
                   int(record.get("pad_after", 0)))

    def holds(self, world: np.ndarray, affine: np.ndarray, shape: Sequence[int]) -> np.ndarray:
        """Whether each world point lies in what the view rendered of the CT whose voxel-to-world
        affine and shape are given: its nearest voxel, rounding half to even as nanoDRR's nearest
        sampling does, within the volume and among the crop's slices."""
        world = np.atleast_2d(np.asarray(world, float))
        to_voxel = np.linalg.inv(np.asarray(affine, float))
        with np.errstate(invalid="ignore"):
            idx = np.rint(world @ to_voxel[:3, :3].T + to_voxel[:3, 3])
            inside = np.all((idx >= 0) & (idx < np.asarray(shape[:3], float)), axis=1)
            return inside & (idx[:, 2] >= self.z_start) & (idx[:, 2] < self.z_stop)

    def cut(self, labels: np.ndarray) -> np.ndarray:
        """The labels on the CT's grid with every slice outside the crop made background, which is
        what the render's labels hold of them."""
        if self.z_stop > labels.shape[2]:
            raise ValueError("the crop runs to slice %d of a volume of %d" % (self.z_stop, labels.shape[2]))
        out = np.array(labels, copy=True)
        out[..., :self.z_start] = 0
        out[..., self.z_stop:] = 0
        return out

    def as_record(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, eq=False)
class Projected:
    """Points on a render: uv[:, 0] along a row (the column, u) and uv[:, 1] down the image (the
    row, v), in pixels from the image's top left corner, the pixel [r, c] covering c <= u < c + 1
    and r <= v < r + 1; depth along the beam in mm, from the source under a cone beam and from the
    source's plane under parallel rays; and whether the render sampled the point, between the
    source and the detector and on the detector."""
    uv: np.ndarray
    depth: np.ndarray
    in_beam: np.ndarray

    def pixels(self) -> np.ndarray:
        """Each point's pixel as (row, column), the cell of the image array it falls in."""
        return np.floor(self.uv[:, ::-1]).astype(int)


class Camera:
    """FleXray's camera for one view: world points to pixels, and pixels to the rays the render
    casts through them."""

    def __init__(self, view: View):
        self.view = view
        pose = np.eye(4)
        rot = zxy(view.rot_deg)
        pose[:3, :3] = rot
        pose[:3, 3] = rot @ np.asarray(view.xyz_mm, float) + np.asarray(view.isocentre_mm, float)
        turn = np.eye(4)
        turn[:3, :3] = np.asarray(ORIENTATIONS[view.orientation], float)
        self.to_world = pose @ turn
        self.to_camera = np.linalg.inv(self.to_world)
        self.fx, self.fy = view.sdd / view.delx, view.sdd / view.pixel_y
        self.cx = view.x0 / view.delx + view.width / 2.0
        self.cy = view.y0 / view.pixel_y + view.height / 2.0

    @property
    def intrinsics(self) -> np.ndarray:
        """K, whose inverse is the k_inv FleXray passes nanoDRR."""
        return np.array([[self.fx, 0.0, self.cx], [0.0, self.fy, self.cy], [0.0, 0.0, 1.0]])

    @property
    def source(self) -> np.ndarray:
        """The source in the world: the camera's origin, under parallel rays the point of the
        source's plane whose ray meets the detector at the principal point, the plane's centre
        where the principal point is the detector's."""
        return self.to_world[:3, 3].copy()

    @property
    def beam(self) -> np.ndarray:
        """The beam's direction in the world, the camera's z."""
        return self.to_world[:3, 2].copy()

    def camera_points(self, world: np.ndarray) -> np.ndarray:
        world = np.atleast_2d(np.asarray(world, float))
        return world @ self.to_camera[:3, :3].T + self.to_camera[:3, 3]

    def project(self, world: np.ndarray) -> Projected:
        """Each world point's place on the render, its depth and whether the render sampled it."""
        cam = self.camera_points(world)
        depth = cam[:, 2]
        if self.view.orthographic:
            scale = np.full(len(cam), 1.0 / self.view.sdd)
        else:
            with np.errstate(divide="ignore", invalid="ignore"):
                scale = 1.0 / depth
        with np.errstate(invalid="ignore"):
            uv = np.stack([self.fx * cam[:, 0] * scale + self.cx, self.fy * cam[:, 1] * scale + self.cy], axis=1)
            on = (uv[:, 0] >= 0) & (uv[:, 0] < self.view.width) & (uv[:, 1] >= 0) & (uv[:, 1] < self.view.height)
        return Projected(uv=uv, depth=depth, in_beam=(depth > 0) & (depth < self.view.sdd) & on)

    def magnification(self, depth) -> np.ndarray:
        """How much the render enlarges a length parallel to the detector at a depth."""
        depth = np.asarray(depth, float)
        if self.view.orthographic:
            return np.ones_like(depth)
        with np.errstate(divide="ignore"):
            return self.view.sdd / depth

    def ray_direction(self, world: np.ndarray) -> np.ndarray:
        """The unit direction of the ray through each world point, from the source towards the
        detector."""
        world = np.atleast_2d(np.asarray(world, float))
        if self.view.orthographic:
            return np.repeat(self.beam[None, :], len(world), axis=0)
        d = world - self.source
        return d / np.linalg.norm(d, axis=1, keepdims=True)

    def rays(self, uv: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """The world's source and detector ends of the rays through pixel places uv, as nanoDRR
        casts them: the detector end sdd K^-1 (u, v, 1) in the camera, the source the camera's
        origin, or that end moved back by sdd under parallel rays."""
        uv = np.atleast_2d(np.asarray(uv, float))
        sdd = self.view.sdd
        detector = np.stack([(uv[:, 0] - self.cx) * sdd / self.fx, (uv[:, 1] - self.cy) * sdd / self.fy,
                             np.full(len(uv), sdd)], axis=1)
        source = detector - [0.0, 0.0, sdd] if self.view.orthographic else np.zeros_like(detector)
        rot, t = self.to_world[:3, :3], self.to_world[:3, 3]
        return source @ rot.T + t, detector @ rot.T + t

    def pixel_centres(self) -> np.ndarray:
        """Every pixel's centre as (u, v), row by row, the order of the render's rays."""
        v, u = np.meshgrid(np.arange(self.view.height) + 0.5, np.arange(self.view.width) + 0.5, indexing="ij")
        return np.stack([u.ravel(), v.ravel()], axis=1)


def canvas_geometry(height: int, width: int, canvas: int = CANVAS) -> Tuple[float, float, float]:
    """FleXray's canvas of an image: the scale and the padding left and on top, the image padded
    to a square at its centre and resized to `canvas` pixels a side."""
    side = max(int(height), int(width))
    return canvas / side, float((side - int(width)) // 2), float((side - int(height)) // 2)


def to_canvas(uv: np.ndarray, height: int, width: int, canvas: int = CANVAS) -> np.ndarray:
    """Places on an image of height by width pixels to the same places on FleXray's canvas."""
    scale, left, top = canvas_geometry(height, width, canvas)
    return (np.atleast_2d(np.asarray(uv, float)) + [left, top]) * scale


def from_canvas(uv: np.ndarray, height: int, width: int, canvas: int = CANVAS) -> np.ndarray:
    """Places on FleXray's canvas back to the image's."""
    scale, left, top = canvas_geometry(height, width, canvas)
    return np.atleast_2d(np.asarray(uv, float)) / scale - [left, top]
