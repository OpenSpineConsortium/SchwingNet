"""Draw ENHANCE.PET's vertebra and rib masks as two flat views a reader can count on.

Confidential, like the rest of this repository: the pictures are of published masks, never of a CT,
and they go only to the owner's private dataset page.

The gold tier 3 dataset calls each spine's column from two masks the same readers checked: the
level names of the vertebra mask and the ribs of the rib mask. Where the two agree the call is
consistent, which is not the same as a person having counted the bodies. These views put both masks
in front of a reader, so a person can count the presacral bodies and the rib pairs and say whether
the call stands. A front view shows every label as its own colour with its name beside it and the
ribs in grey, each rib numbered at its outer end; a side view shows the column alone, where a body
fused into the sacrum or a missing disc is easiest to see.

    python -m holdings.enhance_views MASKDIR RIBDIR IDS OUTDIR

IDS is a file of study ids, one per line, or a JSON list. Each study gives OUTDIR/<id>-front.png and
OUTDIR/<id>-side.png.
"""
from __future__ import annotations

import json
import os
import sys

import nibabel as nib
import numpy as np
from PIL import Image, ImageDraw

# The vertebra masks' labels: C1 to C7 are 1 to 7, T1 to T12 are 8 to 19, L1 to L6 are 20 to 25,
# the hips 26 and 27, the sacrum 28. The rib masks': left rib k is k, right rib k is 13 + k.
LEVEL_NAMES = (["C%d" % i for i in range(1, 8)] + ["T%d" % i for i in range(1, 13)]
               + ["L%d" % i for i in range(1, 7)])
NAMES = {i + 1: name for i, name in enumerate(LEVEL_NAMES)}
NAMES[28] = "S"
HIPS = (26, 27)
SACRUM = 28
RIBS_PER_SIDE = 13

# Neighbouring levels must never share a colour, or two bodies read as one; six hues repeated down
# the column keep any two labels within five levels apart. Lumbar labels take warmer hues so an L6
# stands out, and the sacrum is its own colour.
COLUMN_HUES = [(66, 133, 244), (52, 168, 83), (171, 71, 188), (0, 172, 193), (124, 179, 66), (92, 107, 192)]
LUMBAR_HUES = [(251, 140, 0), (229, 57, 53), (255, 193, 7), (216, 27, 96), (255, 112, 67), (198, 40, 40)]
SACRUM_RGB = (141, 110, 99)
RIB_RGB = (176, 176, 176)
BACKGROUND = (20, 20, 24)
TEXT_RGB = (240, 240, 240)

# Pixels per millimetre in the drawn views: a whole spine runs about 650 mm head to foot, so the
# front view is about 1,000 pixels tall, enough to read each label's name at the default font.
SCALE = 1.5
# Clear space around the masks in the views, in millimetres, so a rib's outer end and its number
# stay inside the picture.
MARGIN_MM = 25.0


def colour_of(label: int):
    if label == SACRUM:
        return SACRUM_RGB
    if 20 <= label <= 25:
        return LUMBAR_HUES[label - 20]
    return COLUMN_HUES[(label - 1) % len(COLUMN_HUES)]


def canonical(path: str):
    """The mask turned to RAS axes, so every view is drawn the same way up whatever the file's order.

    The stored integers are read as they are: nibabel's scaled read would give a float64 copy, eight
    bytes a voxel, which on a 1 mm whole-body study runs to gigabytes."""
    img = nib.load(path)
    raw = np.asarray(img.dataobj.get_unscaled())
    if raw.dtype.kind not in "ui" or raw.max() > 255:
        raise ValueError("%s: a label mask must hold small integers" % path)
    ornt = nib.orientations.io_orientation(img.affine)
    data = nib.orientations.apply_orientation(raw, ornt).astype(np.uint8, copy=False)
    zooms_in = np.array(img.header.get_zooms()[:3], float)
    zooms = np.empty(3)
    zooms[ornt[:, 0].astype(int)] = zooms_in
    return data, zooms


def crop_box(*volumes) -> tuple:
    """The smallest box holding every labelled voxel of the volumes, so projections touch less memory."""
    present = np.zeros(volumes[0].shape, bool)
    for volume in volumes:
        present |= volume > 0
    idx = np.argwhere(present)
    lo, hi = idx.min(0), idx.max(0) + 1
    return tuple(slice(int(a), int(b)) for a, b in zip(lo, hi))


def dominant_label(volume: np.ndarray, labels, axis: int):
    """For each ray along the axis, the label with the most voxels on it, and how many it holds;
    a tie goes to the lower label. One pass over the labelled voxels counts every label on every
    ray at once, which a pass per label took 28 times as long to do."""
    labels = np.asarray(sorted(int(l) for l in labels), np.int64)
    rays = [n for i, n in enumerate(volume.shape) if i != axis]
    best = np.zeros(rays, np.uint8)
    most = np.zeros(rays, np.int32)
    if not len(labels):
        return best, most
    slot = np.zeros(256, np.int64)
    slot[labels] = np.arange(1, len(labels) + 1)
    moved = np.moveaxis(volume, axis, -1)
    where = np.nonzero(np.isin(moved, labels))
    ray = np.ravel_multi_index(where[:2], rays)
    width = len(labels) + 1
    counts = np.bincount(ray * width + slot[moved[where]], minlength=rays[0] * rays[1] * width)
    counts = counts.reshape(rays[0], rays[1], width)[:, :, 1:]
    pick = counts.argmax(axis=2)
    most[:] = np.take_along_axis(counts, pick[..., None], axis=2)[..., 0]
    best[:] = np.where(most > 0, labels[pick], 0)
    return best, most


def stretch(plane: np.ndarray, zooms_2d) -> np.ndarray:
    """A 2-D plane resampled to SCALE pixels per millimetre on both axes (nearest neighbour)."""
    rows = max(1, int(round(plane.shape[0] * zooms_2d[0] * SCALE)))
    cols = max(1, int(round(plane.shape[1] * zooms_2d[1] * SCALE)))
    r = np.minimum((np.arange(rows) / (zooms_2d[0] * SCALE)).astype(int), plane.shape[0] - 1)
    c = np.minimum((np.arange(cols) / (zooms_2d[1] * SCALE)).astype(int), plane.shape[1] - 1)
    return plane[np.ix_(r, c)]


def paint(labels: np.ndarray, colours: dict) -> np.ndarray:
    rgb = np.zeros(labels.shape + (3,), np.uint8)
    rgb[:] = BACKGROUND
    for label, colour in colours.items():
        rgb[labels == label] = colour
    return rgb


def to_picture(plane: np.ndarray) -> np.ndarray:
    """RAS planes have the head at the highest index; pictures have it at the top, so flip rows."""
    return plane.T[::-1]


def centre_of(plane: np.ndarray, label: int):
    pts = np.argwhere(plane == label)
    if not len(pts):
        return None
    return int(np.median(pts[:, 1])), int(np.median(pts[:, 0]))


def name_labels(draw, plane: np.ndarray, labels, x_offset: int) -> None:
    for label in labels:
        at = centre_of(plane, label)
        if at is not None:
            draw.text((at[0] + x_offset, at[1] - 5), NAMES.get(label, str(label)), fill=TEXT_RGB)


def rib_ends(draw, ribs_plane: np.ndarray) -> None:
    """Each rib's number at its outer end: the leftmost point of a left rib, the rightmost of a right."""
    for label in np.unique(ribs_plane):
        if label == 0:
            continue
        pts = np.argwhere(ribs_plane == label)
        right = label > RIBS_PER_SIDE
        k = label - RIBS_PER_SIDE if right else label
        row, col = pts[pts[:, 1].argmax()] if right else pts[pts[:, 1].argmin()]
        draw.text((int(col) + (4 if right else -16), int(row) - 5), str(int(k)), fill=TEXT_RGB)


def padded(rgb: np.ndarray) -> np.ndarray:
    pad = int(MARGIN_MM * SCALE)
    out = np.zeros((rgb.shape[0] + 2 * pad, rgb.shape[1] + 2 * pad, 3), np.uint8)
    out[:] = BACKGROUND
    out[pad:pad + rgb.shape[0], pad:pad + rgb.shape[1]] = rgb
    return out


def front_view(vert: np.ndarray, rib: np.ndarray, zooms) -> Image.Image:
    """Seen from the front (projected along anterior-posterior): the column over the ribs."""
    column = [l for l in np.unique(vert) if l and l not in HIPS]
    vplane, vcount = dominant_label(vert, column, axis=1)
    rplane, rcount = dominant_label(rib, [l for l in np.unique(rib) if 0 < l <= 2 * RIBS_PER_SIDE], axis=1)
    vplane = stretch(to_picture(vplane), (zooms[2], zooms[0]))
    rplane = stretch(to_picture(np.where(vcount > 0, 0, rplane)), (zooms[2], zooms[0]))
    rgb = paint(vplane, {l: colour_of(l) for l in column})
    rgb[rplane > 0] = RIB_RGB
    pad = int(MARGIN_MM * SCALE)
    picture = Image.fromarray(padded(rgb))
    draw = ImageDraw.Draw(picture)
    name_labels(draw, np.pad(vplane, pad), column, 0)
    rib_ends(draw, np.pad(rplane, pad))
    return picture


def side_view(vert: np.ndarray, zooms) -> Image.Image:
    """Seen from the side (projected left-right): the column alone, front to the left."""
    column = [l for l in np.unique(vert) if l and l not in HIPS]
    plane, _ = dominant_label(vert, column, axis=0)
    plane = stretch(to_picture(plane), (zooms[2], zooms[1]))[:, ::-1]
    pad = int(MARGIN_MM * SCALE)
    picture = Image.fromarray(padded(paint(plane, {l: colour_of(l) for l in column})))
    draw = ImageDraw.Draw(picture)
    name_labels(draw, np.pad(plane, pad), column, 18)
    return picture


def draw_study(maskdir: str, ribdir: str, sid: str, outdir: str) -> None:
    vert, zooms = canonical(os.path.join(maskdir, sid + ".nii.gz"))
    rib, rib_zooms = canonical(os.path.join(ribdir, sid + ".nii.gz"))
    if vert.shape != rib.shape or not np.allclose(zooms, rib_zooms, atol=1e-3):
        raise ValueError("%s: the vertebra and rib masks lie on different grids" % sid)
    box = crop_box(vert, rib)
    vert, rib = vert[box], rib[box]
    front_view(vert, rib, zooms).save(os.path.join(outdir, sid + "-front.png"), optimize=True)
    side_view(vert, zooms).save(os.path.join(outdir, sid + "-side.png"), optimize=True)


def read_ids(path: str) -> list:
    text = open(path).read().strip()
    if text.startswith("["):
        return [str(s) for s in json.loads(text)]
    return [line.strip() for line in text.splitlines() if line.strip()]


def main(argv) -> int:
    maskdir, ribdir, ids_file, outdir = argv
    os.makedirs(outdir, exist_ok=True)
    for sid in read_ids(ids_file):
        draw_study(maskdir, ribdir, sid, outdir)
        print(sid, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
