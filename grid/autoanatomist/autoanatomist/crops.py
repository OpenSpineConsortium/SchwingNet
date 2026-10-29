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
the second lies from the first; that is not measured yet.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

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


def sample(volume: np.ndarray, affine: np.ndarray, cf: CropFrame, order: int = 1, fill: float = 0.0) -> np.ndarray:
    """The volume at the crop's voxels, (nx, ny, nz), by its affine: linear for a CT, nearest for
    labels; `fill` outside the volume."""
    world = cf.world(cf.grid().reshape(-1, 3))
    inv = np.linalg.inv(np.asarray(affine, float))
    ijk = world @ inv[:3, :3].T + inv[:3, 3]
    out = ndimage.map_coordinates(np.asarray(volume, np.float32), ijk.T, order=order, mode="constant", cval=fill)
    return out.reshape(cf.shape).astype(np.float32)


def mask_channels(labels: np.ndarray, affine: np.ndarray, cf: CropFrame, target: int) -> np.ndarray:
    """The privileged channels of a crop: the target vertebra's mask and every vertebra's, each
    resampled linearly from its 0-1 volume so its edge falls between voxels, (nx, ny, nz, 2)."""
    lab = np.asarray(labels)
    near = sample((lab == target).astype(np.float32), affine, cf, order=1)
    every = sample((lab > 0).astype(np.float32), affine, cf, order=1)
    return np.stack([near, every], -1)


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
