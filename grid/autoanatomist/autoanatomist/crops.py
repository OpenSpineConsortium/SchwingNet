"""A vertebra's neighbourhood resampled into a crop of its own, and points carried both ways.

The network sees each vertebra in a crop: a box of `shape` voxels `spacing` millimetres apart, its
axes along the vertebra's frame (x to the right, y anterior, z up the column), its centre in front
of the canal's centre by `shift` millimetres so the box holds the body and the canal. Voxel
(i, j, k) of a crop lies at local ((i - (nx - 1) / 2) h, (j - (ny - 1) / 2) h, (k - (nz - 1) / 2) h)
and in the world at origin + axes @ local, so a landmark is carried into the crop and back by one
rotation and one shift, and a prediction in the crop is a point in the world.

Where the frame comes from differs between training and use, on purpose and stated: in training,
from the oracle's reading of the mask (the canal's centre at its median slab, the vertebra's own
axes), perturbed by a random turn and shift so the network does not learn the oracle's frame; in
use on a raw CT, from the mask-free mode (scanimport.intensity.find: the canal's centreline and
the discs along it), each vertebra's centre the centreline's point half way between its two
discs and its z the centreline's tangent there. The perturbation's size is meant to cover how far
the second lies from the first; that is not measured yet. The fully latent objective (blocks.py's
objective=mask) trains with no oracle at all: its frame is the centroid frame (centroids,
from_centroid), the crop's axes the world's and its centre the mask's centroid, jittered the same
way, so the mask gives the frame and the privileged channels and nothing is measured.

Only the box of a volume under a crop is read (window): a crop of one vertebra is a small part of
a CT, and casting or thresholding the whole CT once a crop was most of the time a CT took to render.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy import ndimage

from .oracle import Reading

SHIFT_MM = 16.0                     # the crop's centre this far in front of the canal's centre
SHAPE = (48, 56, 32)                # 96 by 112 by 64 mm at 2 mm: the body, the canal and the arch of a lumbar vertebra
SPACING_MM = 2.0
AIR_HU = -1000.0


@dataclass(frozen=True)
class CropFrame:
    origin: np.ndarray               # world millimetres of the crop's centre
    axes: np.ndarray                 # (3, 3), columns the crop's x, y and z in the world
    spacing: float = SPACING_MM
    shape: Tuple[int, int, int] = SHAPE

    def local(self, world: np.ndarray) -> np.ndarray:
        return (np.asarray(world, float) - self.origin) @ self.axes

    def world(self, local: np.ndarray) -> np.ndarray:
        return np.asarray(local, float) @ self.axes.T + self.origin

    def grid(self) -> np.ndarray:
        """The local millimetres of every voxel's centre, (nx, ny, nz, 3)."""
        ticks = [(np.arange(n) - (n - 1) / 2.0) * self.spacing for n in self.shape]
        return np.stack(np.meshgrid(*ticks, indexing="ij"), -1)

    def axis_ticks(self) -> List[np.ndarray]:
        return [(np.arange(n) - (n - 1) / 2.0) * self.spacing for n in self.shape]


def unit(v: np.ndarray) -> np.ndarray:
    return np.asarray(v, float) / np.linalg.norm(v)


def frame_toward(ez: np.ndarray, anterior: np.ndarray = np.array([0.0, 1.0, 0.0])) -> np.ndarray:
    """Axes (columns x, y, z) with z along ez and y as near `anterior` as z allows, right-handed."""
    ez = unit(ez)
    ey = anterior - (anterior @ ez) * ez
    if np.linalg.norm(ey) < 1e-6:
        ey = np.cross(ez, [1.0, 0.0, 0.0])
    ey = unit(ey)
    return np.column_stack([np.cross(ey, ez), ey, ez])


def from_reading(r: Reading, shift: float = SHIFT_MM, spacing: float = SPACING_MM,
                 shape: Tuple[int, int, int] = SHAPE) -> CropFrame:
    axes = r.frame.axes
    return CropFrame(np.asarray(r.centre, float) + shift * axes[:, 1], axes, spacing, tuple(shape))


def turn(axis: np.ndarray, deg: float) -> np.ndarray:
    a = unit(axis)
    t = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K


def perturbed(cf: CropFrame, rng: np.random.Generator, shift_mm: float = 4.0, turn_deg: float = 8.0) -> CropFrame:
    """The crop turned about a random axis by up to turn_deg and moved by up to shift_mm in each
    direction, both uniform: the augmentation that keeps the network from learning the frame."""
    R = turn(rng.normal(size=3), rng.uniform(-turn_deg, turn_deg))
    return CropFrame(cf.origin + rng.uniform(-shift_mm, shift_mm, 3), R @ cf.axes, cf.spacing, cf.shape)


def voxel_coordinates(affine: np.ndarray, cf: CropFrame) -> np.ndarray:
    """The volume's voxel coordinates of every crop voxel's centre, (N, 3), by the volume's affine."""
    world = cf.world(cf.grid().reshape(-1, 3))
    inv = np.linalg.inv(np.asarray(affine, float))
    return world @ inv[:3, :3].T + inv[:3, 3]


def window(volume: np.ndarray, ijk: np.ndarray, margin: int) -> Tuple[np.ndarray, np.ndarray]:
    """The box of the volume the voxel coordinates ijk (N, 3) fall in, `margin` voxels wider each
    way and clipped to the volume, with the box's first voxel; empty where every coordinate misses
    the volume."""
    shape = np.array(volume.shape[:3])
    lo = np.maximum(np.floor(ijk.min(0)).astype(int) - margin, 0)
    hi = np.minimum(np.ceil(ijk.max(0)).astype(int) + margin, shape - 1)
    if np.any(hi < lo):
        return volume[0:0, 0:0, 0:0], lo
    return volume[lo[0]:hi[0] + 1, lo[1]:hi[1] + 1, lo[2]:hi[2] + 1], lo


def sample(volume: np.ndarray, affine: np.ndarray, cf: CropFrame, order: int = 1, fill: float = 0.0,
           values: Optional[Callable[[np.ndarray], np.ndarray]] = None) -> np.ndarray:
    """The volume at the crop's voxels, (nx, ny, nz), by its affine: linear for a CT, nearest for
    labels; `fill` outside the volume. Only the box under the crop is read (window), to the same
    values as the whole volume would give, since map_coordinates in its constant mode interpolates
    between the voxels at hand alone, which the box holds, and gives `fill` beyond the volume's
    edge, which the box's edge is wherever it is the volume's; an order above 1 would prefilter
    the whole volume and is refused. `values`, where given, maps the box to the values sampled (a
    label box to one mask's 0-1 box, mask_channels), so the whole volume is never cast or compared."""
    if order > 1:
        raise ValueError("sample takes order 0 or 1; a spline's prefilter reads the whole volume")
    ijk = voxel_coordinates(affine, cf)
    box, lo = window(np.asarray(volume), ijk, order + 1)
    if box.size == 0:
        return np.full(cf.shape, fill, np.float32)
    if values is not None:
        box = values(box)
    out = ndimage.map_coordinates(np.asarray(box, np.float32), (ijk - lo).T, order=order, mode="constant", cval=fill)
    return out.reshape(cf.shape).astype(np.float32)


def mask_channels(labels: np.ndarray, affine: np.ndarray, cf: CropFrame, target: int) -> np.ndarray:
    """The privileged channels of a crop: the target vertebra's mask and every vertebra's, each
    resampled linearly from its 0-1 volume so its edge falls between voxels, (nx, ny, nz, 2)."""
    near = sample(labels, affine, cf, order=1, values=lambda box: (box == target).astype(np.float32))
    every = sample(labels, affine, cf, order=1, values=lambda box: (box > 0).astype(np.float32))
    return np.stack([near, every], -1)


def centroids(labels: np.ndarray, affine: np.ndarray, values: Sequence[int]) -> Dict[int, np.ndarray]:
    """The centroid of each label value's voxels in world millimetres, by the affine, for the values
    that have a voxel; one pass over the volume a slab at a time, summing only the foreground."""
    lab = np.asarray(labels)
    want = sorted({int(v) for v in values})
    sums = {v: np.zeros(3) for v in want}
    counts = {v: 0 for v in want}
    for i in range(lab.shape[0]):
        j, k = np.nonzero(lab[i])
        if len(j) == 0:
            continue
        v = lab[i][j, k]
        for value in want:
            m = v == value
            n = int(m.sum())
            if n:
                counts[value] += n
                sums[value] += (n * i, j[m].sum(), k[m].sum())
    A = np.asarray(affine, float)
    return {v: (sums[v] / counts[v]) @ A[:3, :3].T + A[:3, 3] for v in want if counts[v]}


def from_centroid(centre: np.ndarray, shift: float = 0.0, spacing: float = SPACING_MM,
                  shape: Tuple[int, int, int] = SHAPE) -> CropFrame:
    """The centroid frame, with no oracle in it: the crop's axes the world's (x right, y anterior, z
    up, as a NIfTI affine gives them), its centre the mask's centroid moved `shift` millimetres
    along world y. A whole vertebra's centroid, body and arch together, lies in the back of the
    body, so with no shift the crop holds the body in front of its centre and the arch behind; the
    column's tilt against the world's z is left to the jitter and the network."""
    return CropFrame(np.asarray(centre, float) + shift * np.array([0.0, 1.0, 0.0]), np.eye(3), spacing, tuple(shape))


def ct_channel(hu: np.ndarray, affine: np.ndarray, cf: CropFrame) -> np.ndarray:
    return sample(hu, affine, cf, order=1, fill=AIR_HU)[..., None]


def from_found(found, shift: float = SHIFT_MM, spacing: float = SPACING_MM,
               shape: Tuple[int, int, int] = SHAPE) -> List[CropFrame]:
    """Crop frames for the bodies the mask-free mode found between consecutive discs, top down:
    each centred `shift` in front of the centreline's point half way between its discs, z along
    the centreline's tangent there. The discs are millimetres from the centreline's lower end,
    and the centreline is sampled every millimetre (scanimport.intensity.Centreline)."""
    line = found.centreline
    if line is None or len(found.discs) < 2:
        return []
    out = []
    for a, b in zip(found.discs, found.discs[1:]):
        i = int(round(0.5 * (a + b)))
        i = min(max(i, 0), len(line.points) - 1)
        axes = frame_toward(line.tangents[i])
        out.append(CropFrame(line.points[i] + shift * axes[:, 1], axes, spacing, tuple(shape)))
    return out[::-1]


def targets(r: Reading, cf: CropFrame, keys: Sequence[str]) -> np.ndarray:
    """The reading's landmarks in the crop's local millimetres, (K, 3), NaN where not taken."""
    return cf.local(r.landmarks(keys))
