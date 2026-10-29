"""Complete a full-spine CT's column with a segmenter's levels, kept as a machine arm of its own.

Confidential, like the rest of this repository: nothing here, and nothing it writes, goes to a
public place, and no mask or CT is ever copied into the repository.

The owner's words of 2026-10-29 03:32 UTC, on the CTs of the gold tier 3 dataset whose field shows C2
and the sacrum while the release masks stop short of them: "segment the c2 and sacrums which are on ct
volumes they just lack the masks and convert them all to gold tier 3 data"; and his choice that morning
to run SPINEPS's CT models in a cloud container rather than wait for the grid. SPINEPS draws every
vertebra it finds and the sacrum, each under a name of its own labelling model, and a subregion mask
that tells a vertebra's body from its arch and marks the discs; this module decides which of those
levels may stand for a level the release does not draw, and writes them as a mask of their own on the
CT's grid, beside the release's and never over it, so the two arms are never pooled.

A segmenter's name is not trusted alone, since a labelling model can be off by a level, and a count
from a level the release names is not trusted alone either, since a segmenter can merge two bodies,
split one, miss one or reach into the next, and a labeller that names its own levels in sequence then
shifts its names with the count. So a level is taken only where the count and the segmenter's name
agree, or where the release names the levels on both sides of it, and only where the segmenter's own
bodies and discs show one whole body there, read from its subregion mask and not from its names:

1. Anchors. A release level drawn with at least MIN_VOXELS voxels and a segmenter level that are each
   the other's best match by Dice, with at least MATCH_INSIDE of each lying inside the other, are one
   body; the second test refuses a segmenter level that takes in a neighbour the release leaves
   undrawn, which Dice alone lets pass (two bodies merged give 0.67). The anchors must run in the same
   order, head to foot, in both arms, or nothing is taken.
2. Between two anchors, the release's names leave a gap; where the segmenter has exactly as many levels
   between the same two bodies as the gap has names, the release draws none of them and every one of
   them passes the checks of rules 5 and 6, they take the gap's names in order; if any fails, none is
   taken, since the count that named the others ran through it.
3. Above the head-most anchor and below the foot-most, the count runs from one side only, over every
   name of the column from C2 to L5 and every name the release draws, whether asked for or not: each
   level takes the next name outwards only where the segmenter's own name for it is that name too and
   it passes the checks of rules 5 and 6, and the walk stops at the first that does not, refusing every
   name beyond it. Where the first that does not fails against the level inward of it (rule 6 says
   which checks do), that level, taken a step before, is refused too, since the two fail together: a
   level that took part of its outer neighbour leaves that neighbour short.
4. The sacrum is the segmenter's sacrum, taken only where the release's foot-most drawn level is an
   anchor, every segmenter level between that anchor and the sacrum was taken by the walk and asked
   for, the level directly above the sacrum is L5 or L6, and rule 5 and the sacrum's disc check hold:
   read along the column from the body above to the sacrum's far end, inside that body's cylinder,
   exactly one run of disc begins within SACRUM_DISC_REACH_MM of the sacrum's head end, the disc above
   it; no later run inside the sacrum holds SACRUM_DISC_SHARE of that disc's voxels or more, which a
   folded lumbar body's disc would; and no more than OVERREACH_SHARE of the sacrum lies over OVER_MM
   past that disc's far surface, read cell by cell as rule 6 reads a disc. Every run is recorded with
   where it lies and its voxels and mm3, so a person can tell an S1/S2 remnant from a folded body.
5. Every level so named holds at least MIN_VOXELS voxels outside the release's own, and no more than
   MAX_RELEASE_SHARE of it lies under another of the release's levels.
6. Every vertebra so named is one whole body in the segmenter's subregion mask, read beside its inner
   neighbour (the level the count reached it from) and its outer neighbour (the segmenter's next level
   outward, or the sacrum):
   - its instance's largest 26-connected piece holds LARGEST_SHARE of it, its body holds at least
     MIN_VOXELS voxels, and its body's own largest piece holds BODY_SHARE of the body;
   - against its inner neighbour: that neighbour's body holds MIN_VOXELS voxels; its body's height is
     within HEIGHT_BAND of the neighbour's (C2's within C2_HEIGHT_BAND, for the dens, with no lower
     bound where the field's top cuts its body); the step between their centres is within STEP_BAND of
     the step from that neighbour to the next level inwards, or, where that level is missing, small or
     the atlas, of its own step outwards; its height and step ratios do not both pass MERGED, as two
     bodies joined with no disc drawn between them read; and the disc between them reads well (below);
   - the disc in the middle third of its body holds less than MERGED_DISC_SHARE of the disc beside it;
   - against its outer neighbour: the disc between them reads well; for the sacrum the disc is looked
     for only up to SACRUM_DISC_REACH_MM past the sacrum's head end, so a disc inside the sacrum does
     not count against the level above it; a C2 needs the segmenter's C1 as a level of its own above
     it, or its body cut by the field's top, since otherwise the label may hold the atlas, and the arm
     writes the whole label; any other level with nothing beyond it, or the atlas, is refused, since
     its outer side cannot be read.
   A disc reads well when exactly one run of disc lies between the two bodies' centres, inside a
   cylinder about the line joining them as wide as the bodies, and the body read against that run in
   the run's own frame holds up. The run's plane is fitted to its voxels and cut into square cells
   CELL_MM wide; in each cell holding MIN_IN_CELL of its voxels or more, its near and far surfaces are
   its voxels' least and greatest heights along the plane's normal, so a wedge-shaped disc or a curved
   end plate is read where it stands and not against one flat plane. No more than OVERREACH_SHARE of
   the body may lie over OVER_MM past the far surface in its own cell, which is a body that took part
   of its neighbour across the disc; and over the cells holding both, the median of the near surface
   less the body's highest voxel there may be no less than -OVERLAP_MM, a body running into the disc,
   and no more than the larger of CUT_SHORT_MM and one voxel's reach along the normal plus
   CUT_SHORT_SLACK_MM, a body cut short with its end left to another label or to none.
   A body split in two halves the height and the step and leaves no disc between the halves; two merged
   double them and hold a whole disc inside or, with none drawn between them, pass MERGED; a body the
   segmenter missed doubles the step and leaves two discs between its neighbours; a body that reaches
   past the disc into its neighbour stands beyond the disc's far surface; a body cut short stops short
   of the disc.
7. The disc reading must hold on the release's own levels first. Each pair of anchors that are
   neighbours in the segmenter's column, neither the atlas, is read both ways as rule 6 reads a disc;
   with fewer than MIN_CALIBRATION pairs read, or any reading failing, every target of the study is
   refused, since the reading is not shown to hold on that CT (a child's column, whose discs SPINEPS
   draws thin or not at all, fails here).

Calibration, 2026-10-29, on SPINEPS 2.1.2's own masks of seven adult VerSe CTs (verse018, verse033,
verse255, verse531, verse558, verse559, verse593), read by this module's own side_reading and
sacrum_check, each body against each neighbour in the column, and on the same bodies altered by hand in
the ways a segmenter fails that the earlier rule let through (research_notes/fullspine-rule6-calibration/
holds the scripts, the readings and their summary):

- 546 readings of a body beside its neighbour: every one found exactly one run of disc between them,
  none had more than 0.00017 of the body past the disc's far surface, and the median gaps ran from
  0.16 to 2.94 mm (the largest on verse018's 1 x 1 x 3 mm grid). None is refused.
- a body that takes the part of its outer neighbour's body nearest it, 266 cases at each share: of 5%
  of the neighbour's height, 151 are refused by the disc reading alone; of 10%, 222; of 20%, 259; of
  30%, all 266. The body's own pieces (BODY_SHARE) refuse more of them, wherever the part taken does
  not touch the body, and an instance that took a part of the neighbour's arch is beyond this reading.
- a body cut short at its outer end, the rest dropped, 266 cases at each share kept: keeping 60% of
  its height, 256 are refused; 70%, 226; 80%, 140; 90%, 4. A body short by a tenth is not told from
  a whole one, which the record's gap_mm shows a person.
- the height and step ratios of 266 single bodies and of 252 pairs of neighbours joined with the disc
  between them deleted: no single body with a height ratio over 1.25 had a step ratio over 1.07, none
  with a step ratio over 1.12 a height ratio over 1.17, and every joined pair passed 1.29 and 1.15.
- the sacrum's disc runs: all seven sacra hold one run within 10 mm of their head ends, and verse559's
  holds a second of 5,140 voxels, 20% of its L5/S1 disc's 26,129, 31 to 40 mm below its head end, its
  S1/S2 disc, which no longer refuses it.

On five TotalSegmentator CTs of children (s1411, s1532, s1593, s1606, s2065), whose spines SPINEPS was
not trained on, 84 of 358 readings of a body as it stands are refused, and the two arms disagree on
where the bodies lie, one of SPINEPS's levels lying over two or three of the release's in s1532 and
s1606: none of the release's levels is an anchor in s1532, s1593 and s1606, no two anchors are
neighbours in the segmenter's column in s2065, so rule 7 refuses it, and in s1411 the walk toward T12
stops at the release's L1, which the segmenter does not match. Nothing is added to any of them.

A target the rules do not take is refused, with the reason, and stays undrawn: a level the field test
asked for that no rule names is left to a person, never guessed.

    python -m holdings.fullspine_complete JOBS.json OUT [--workers N]

JOBS.json holds {"segmenter": {...}, "facts": {member: FACTS.jsonl}, "studies": [{"id", "member",
"release", "machine", "spine", "input", "targets"}]}: the segmenter's record copied into every row, each
member's facts from holdings.fullspine_facts, and per study the release mask (VerSe's one file) or
folder (TotalSegmentator's vertebrae_*.nii.gz and sacrum.nii.gz), the segmenter's vertebra mask and its
subregion mask on the CT's grid and, where there is one, a JSON file saying how the CT went into the
segmenter. A study whose release, read again, differs from its facts row in any level's voxel count is
an error row, since its completed row would mix two readings. OUT receives:

    records.jsonl  one row per study: the job's digest, the files read and written, the anchors and the
                   disc reading's check on them, the segmenter's levels head to foot, and each target
                   with its state (added or refused) and the numbers it rests on; a study that could
                   not be read is a row with its error, member, segmenter and digest;
    facts.jsonl    for each study with a level added, its facts row with those levels drawn: the
                   level's facts read from its voxels in either arm, distances_mm read again, and
                   machine_levels saying which levels came from the segmenter; the ribs are left as
                   the release's levels read them;
    masks/         <id>_machine_<first 12 of its sha256>.nii.gz, the added levels in VerSe's ids on the
                   CT's grid, written byte for byte the same on every run, so a run never writes over
                   a mask an earlier record vouches for; a mask no record vouches for is removed.

A run cut short is started again with the same command and reads only the studies it has not written,
keeping a row only where its job's digest is the job's now: the digest covers this module's and its
readers' code, the job's fields and the bytes of every file it reads, so a row from other code or
other masks is read again.

A study's targets are the names it asks for, in its job's "targets": SchwingNet's field test lists
the levels each admitted study must have added (admission.json, complete), and C2 down to the head-most
drawn level where it holds the head end for a look. A name the field test does not ask for is never
added, so a body the release leaves unnamed above the sacrum (no_l5, which may be a transitional
vertebra the count is to read) is never named L5 here, and the sacrum below it is refused. With no
"targets", every name from C2 to L5 and the sacrum that the release does not draw is a target. C1, T13
and L6 are refused when asked for, since no rule here names them.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
from types import SimpleNamespace

import nibabel as nib
import numpy as np

from holdings import count_enhance_pet
from holdings import fullspine_facts as F
from holdings.count_enhance_pet import MIN_VOXELS

MATCH_INSIDE = 0.8
MAX_RELEASE_SHARE = 0.10
LARGEST_SHARE = 0.9
BODY_SHARE = 0.98        # the body's own largest piece: a single body's is 0.9999 or more on VerSe
HEIGHT_BAND = (0.6, 1.6)
C2_HEIGHT_BAND = (0.6, 2.5)
STEP_BAND = (0.6, 1.5)
MERGED = (1.25, 1.12)    # height and step ratios that, both passed, read as two bodies with no disc drawn between
DISC_FLOOR = 20          # voxels: a run of disc fewer than this is a speck, not a disc
DISC_GAP_MM = 2.5        # mm along the column that part one run of disc from the next, at least 1.5 voxels
RADIUS_PERCENTILE = 90   # a body's cylinder reaches as far from the column's axis as this share of its voxels
MERGED_DISC_SHARE = 0.2  # disc in a body's middle third, as a share of the disc beside it, that makes it two
CELL_MM = 4.0            # the side of a cell of a disc's plane, in which its two surfaces are read
MIN_IN_CELL = 3          # disc voxels a cell needs before its surfaces are read
OVER_MM = 1.0            # how far past a disc's far surface a body's voxel may lie before it is in the neighbour
OVERREACH_SHARE = 0.002  # the share of a body that may lie past it
OVERLAP_MM = 1.0         # how far a body's end may run into the disc, as the median over cells
CUT_SHORT_MM = 3.0       # how far short of the disc a body's end may stop, as the median over cells,
CUT_SHORT_SLACK_MM = 1.0  # or one voxel's reach along the disc's normal and this, where that is more
SACRUM_DISC_REACH_MM = 10.0  # how far past the sacrum's head end the disc above it may begin
SACRUM_DISC_SHARE = 0.5  # a run of disc inside the sacrum this share of the disc above it is a disc too many
MIN_CALIBRATION = 2      # pairs of anchors the disc reading must hold on before it is trusted
CORPUS, DISC = 49, 100   # SPINEPS's subregion labels for a vertebra's body and for a disc
VERSE_IDS = {name: label for label, name in F.VERSE_NAMES.items()}
TARGET_NAMES = tuple(name for name in F.COLUMN_NAMES if name not in ("C1", "T13", "L6"))
ATLAS = "C1"
SACRUM = "sacrum"
LAST_LUMBAR = ("L5", "L6")
ADDED, REFUSED = "added", "refused"
INNER = "inner"          # a failure that may be the inner neighbour's as much as the level's own
NO_POINTS = np.zeros((0, 3), np.int32)
CODE = (__file__, F.__file__, count_enhance_pet.__file__)


# ---------------------------------------------------------------- reading the two arms

def read_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def grid_of(img) -> SimpleNamespace:
    """The shape and affine of an image, all the matcher keeps of it, so the mask it was read from is
    not held in memory through the study."""
    return SimpleNamespace(shape=tuple(int(n) for n in img.shape[:3]), affine=np.array(img.affine, float))


def release_files(member: str, release: str) -> list:
    """The paths of a study's release masks: VerSe's one file, or TotalSegmentator's level files."""
    if member == "verse":
        return [release]
    return [os.path.join(release, base) for base in sorted(os.listdir(release)) if base in F.TS_LEVEL_FILES]


def release_levels(member: str, release: str):
    """(grid, {name: points}, {file: record}) of a study's release masks."""
    if member == "verse":
        data = read_bytes(release)
        img = F.image_of(data)
        found = F.voxel_points(img)
        levels = {F.VERSE_NAMES[label]: points for label, points in found.items() if label in F.VERSE_NAMES}
        return grid_of(img), levels, {os.path.basename(release): F.file_record(data)}
    grid, levels, files = None, {}, {}
    for path in release_files(member, release):
        base = os.path.basename(path)
        data = read_bytes(path)
        files[base] = F.file_record(data)
        level_img = F.image_of(data)
        if grid is None:
            grid = grid_of(level_img)
        elif not F.same_grid(grid, level_img):
            raise ValueError("%s lies on another grid" % base)
        points = F.voxel_points(level_img).get(1)
        if points is not None and len(points):
            levels[F.TS_LEVEL_FILES[base]] = points
    return grid, levels, files


def machine_levels(path: str):
    """(grid, {VerSe id: points}, record) of the segmenter's vertebra mask; its discs and endplates
    (100 and above) and any label outside VerSe's scheme are left out."""
    data = read_bytes(path)
    img = F.image_of(data)
    found = F.voxel_points(img)
    return grid_of(img), {label: points for label, points in found.items() if label in F.VERSE_NAMES}, F.file_record(data)


def subregions(path: str):
    """(grid, body points, disc points, record) of the segmenter's subregion mask."""
    data = read_bytes(path)
    img = F.image_of(data)
    found = F.voxel_points(img, {CORPUS, DISC})
    return grid_of(img), found.get(CORPUS, NO_POINTS), found.get(DISC, NO_POINTS), F.file_record(data)


def same_release(levels: dict, row: dict) -> bool:
    """The release read for the matcher is the one the facts row was read from, level by level."""
    return ({name: int(len(points)) for name, points in levels.items()}
            == {name: entry["voxels"] for name, entry in row["levels"].items()})


# ---------------------------------------------------------------- voxels as sets

def flat(points: np.ndarray, shape) -> np.ndarray:
    return np.sort(np.ravel_multi_index(points.T, shape))


def common(first: np.ndarray, second: np.ndarray) -> int:
    return int(len(np.intersect1d(first, second, assume_unique=True)))


def height(points: np.ndarray, affine) -> float:
    """The mean head-foot position of a level, superior positive."""
    return float(F.world_points(points, affine)[:, 2].mean())


# ---------------------------------------------------------------- the segmenter's bodies and discs
#
# Every check below reads the column along its own axis, the line from one body's centre to its
# neighbour's, inside a cylinder about that line as wide as the bodies, and never along the image's
# head-foot axis: in VerSe's sagittal neck and upper thoracic CTs the two part by 30 degrees and more,
# and read along the image the disc beside a body stands at the height of the body's middle.

def placed(points: np.ndarray, affine) -> dict:
    """A set of voxels as the checks read it: its voxel indices and its points in world mm."""
    return {"points": points, "world": F.world_points(points, affine)}


def bodies_of(machine: dict, corpus: np.ndarray, affine, shape) -> dict:
    """{label: placed body}: each segmenter vertebra's voxels its subregion mask calls body, and the
    whole sacrum, whose subregions are not read."""
    body = flat(corpus, shape)
    out = {}
    for label, points in machine.items():
        if label != VERSE_IDS[SACRUM]:
            points = points[np.isin(np.ravel_multi_index(points.T, shape), body)]
        out[label] = placed(points, affine)
    return out


def column_of(machine: dict, corpus: np.ndarray, disc: np.ndarray, grid, chain: list, sacrum, atlas: set):
    """The segmenter's column as the checks read it: its bodies and discs, the grid, each level's
    largest piece, its names, its vertebrae head to foot, its sacrum and the labels that are the atlas."""
    return SimpleNamespace(bodies=bodies_of(machine, corpus, grid.affine, grid.shape),
                           discs=placed(disc, grid.affine), grid=grid, cell=cell_of(grid.affine),
                           shares={label: F.pieces(points)[1] for label, points in machine.items()},
                           names={label: F.VERSE_NAMES[label] for label in machine},
                           chain=chain, sacrum=sacrum, atlas=atlas)


def cell_of(affine) -> np.ndarray:
    """The grid's three voxel edges in world mm, one per column."""
    return np.asarray(affine, float)[:3, :3]


def reach(cell: np.ndarray, axis: np.ndarray) -> float:
    """How far one voxel reaches along a unit axis: the longest of its three edges projected on it, in
    mm. The sum of the three would be the voxel's whole diagonal, which on an oblique axis overstates
    every height and gap by a voxel."""
    return float(np.abs(cell.T @ axis).max())


def axis_between(body: dict, other: dict) -> tuple:
    """(centre, unit axis, distance in mm) of the column from body's centre toward other's; the axis is
    None where the two centres meet."""
    centre = body["world"].mean(0)
    step = other["world"].mean(0) - centre
    distance = float(np.linalg.norm(step))
    return centre, (step / distance if distance else None), distance


def along(points: np.ndarray, centre: np.ndarray, axis: np.ndarray) -> tuple:
    """(position along the axis, distance from it) of each point, in mm."""
    offset = points - centre
    position = offset @ axis
    return position, np.linalg.norm(offset - np.outer(position, axis), axis=1)


def extent(body: dict, centre: np.ndarray, axis: np.ndarray) -> tuple:
    """(first, last) position of a body along the axis, in mm."""
    position = along(body["world"], centre, axis)[0]
    return float(position.min()), float(position.max())


def radius_of(body: dict, centre: np.ndarray, axis: np.ndarray) -> float:
    """How far a body reaches from the axis: the RADIUS_PERCENTILE of its voxels' distances, in mm."""
    return float(np.percentile(along(body["world"], centre, axis)[1], RADIUS_PERCENTILE))


def disc_runs(discs: dict, centre: np.ndarray, axis: np.ndarray, radius: float, low: float, high: float,
              voxel: float) -> list:
    """The runs of disc inside the cylinder of the radius about the axis, between low and high mm
    along it, each (start, end, its voxels in world mm); voxels further apart along the axis than
    DISC_GAP_MM, or 1.5 voxels, part two runs, and a run under DISC_FLOOR voxels is left out."""
    position, distance = along(discs["world"], centre, axis)
    picked = np.flatnonzero((distance <= radius) & (position > low) & (position < high))
    order = picked[np.argsort(position[picked], kind="stable")]
    if not len(order):
        return []
    cuts = np.flatnonzero(np.diff(position[order]) > max(DISC_GAP_MM, 1.5 * voxel)) + 1
    runs = [(float(position[part[0]]), float(position[part[-1]]), discs["world"][part])
            for part in np.split(order, cuts)]
    return [run for run in runs if len(run[2]) >= DISC_FLOOR]


def disc_frame(disc: np.ndarray, towards: np.ndarray) -> tuple:
    """(centre, normal, u, w) of a run of disc: the plane fitted to its voxels, its unit normal turned
    along towards, and two unit axes in the plane."""
    centre = disc.mean(0)
    normal = np.linalg.eigh(np.cov((disc - centre).T))[1][:, 0]
    if normal @ towards < 0:
        normal = -normal
    helper = np.array([1.0, 0.0, 0.0]) if abs(normal[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = np.cross(normal, helper)
    u /= np.linalg.norm(u)
    return centre, normal, u, np.cross(normal, u)


def in_cells(points: np.ndarray, frame: tuple) -> tuple:
    """(height along the frame's normal, cell key) of each point, the plane cut into CELL_MM squares."""
    centre, normal, u, w = frame
    offset = points - centre
    keys = np.floor(np.stack([offset @ u, offset @ w], axis=1) / CELL_MM).astype(np.int64)
    return offset @ normal, (keys[:, 0] << 32) + keys[:, 1]


def local_reading(body: dict, disc: np.ndarray, towards: np.ndarray, cell: np.ndarray) -> dict:
    """A body read against one run of disc in the disc's own frame, its normal toward the neighbour on
    the disc's far side: the share of the body over OVER_MM past the disc's far surface in its own cell,
    the median over cells of the disc's near surface less the body's highest voxel there, the cells
    read, and one voxel's reach along the normal."""
    frame = disc_frame(disc, towards)
    disc_height, disc_key = in_cells(disc, frame)
    body_height, body_key = in_cells(body["world"], frame)
    keys, inverse, counts = np.unique(disc_key, return_inverse=True, return_counts=True)
    near = np.full(len(keys), np.inf)
    far = np.full(len(keys), -np.inf)
    np.minimum.at(near, inverse, disc_height)
    np.maximum.at(far, inverse, disc_height)
    where = np.clip(np.searchsorted(keys, body_key), 0, len(keys) - 1)
    shared = (keys[where] == body_key) & (counts[where] >= MIN_IN_CELL)
    past = int((shared & (body_height > far[where] + OVER_MM)).sum())
    reading = {"overreach_share": past / len(body_height), "cells": 0, "gap_mm": None,
               "voxel_mm": reach(cell, frame[1]), "disc_voxels": int(len(disc))}
    if shared.any():
        cells, which = np.unique(where[shared], return_inverse=True)
        top = np.full(len(cells), -np.inf)
        np.maximum.at(top, which, body_height[shared])
        reading.update(cells=int(len(cells)), gap_mm=float(np.median(near[cells] - top)))
    return reading


def cut_short_mm(reading: dict) -> float:
    return max(CUT_SHORT_MM, reading["voxel_mm"] + CUT_SHORT_SLACK_MM)


def disc_reason(reading: dict):
    """Why a body read against the disc beside it does not hold up, or None."""
    if reading["cells"] == 0:
        return "its body shares no %g mm cell with the disc beside it" % CELL_MM
    if reading["overreach_share"] > OVERREACH_SHARE:
        return "%.2f%% of its body lies over %g mm past the disc, in its neighbour's place, over %.1f%%" % (
            100 * reading["overreach_share"], OVER_MM, 100 * OVERREACH_SHARE)
    if reading["gap_mm"] < -OVERLAP_MM:
        return "its body runs %.1f mm into the disc, over %g mm" % (-reading["gap_mm"], OVERLAP_MM)
    if reading["gap_mm"] > cut_short_mm(reading):
        return "its body stops %.1f mm short of the disc, over %.1f mm: cut short" % (
            reading["gap_mm"], cut_short_mm(reading))
    return None


def rounded_reading(reading: dict) -> dict:
    return {"overreach_share": F.rounded(reading["overreach_share"], 6), "cells": reading["cells"],
            "gap_mm": None if reading["gap_mm"] is None else F.rounded(reading["gap_mm"], 2),
            "voxel_mm": F.rounded(reading["voxel_mm"], 2), "disc_voxels": reading["disc_voxels"]}


def side_reading(body: dict, other: dict, column, high=None) -> tuple:
    """(numbers, reason or None) of the disc between body and other: exactly one run of it between their
    centres (or up to high mm along the line from body's), inside the cylinder that holds them both,
    and body read against that run."""
    centre, axis, distance = axis_between(body, other)
    if axis is None:
        return {}, "its body's centre is its neighbour's"
    radius = max(radius_of(body, centre, axis), radius_of(other, centre, axis))
    runs = disc_runs(column.discs, centre, axis, radius, 0.0, distance if high is None else high,
                     reach(column.cell, axis))
    numbers = {"discs": len(runs)}
    if len(runs) != 1:
        return numbers, "%d discs lie between its body and its neighbour's, where one should" % len(runs)
    reading = local_reading(body, runs[0][2], other["world"].mean(0) - centre, column.cell)
    numbers.update(rounded_reading(reading))
    return numbers, disc_reason(reading)


def middle_disc(body: dict, discs: dict, centre: np.ndarray, axis: np.ndarray) -> int:
    """The disc voxels in the middle third of a body's length, inside its own cylinder."""
    first, last = extent(body, centre, axis)
    third = (last - first) / 3
    position, distance = along(discs["world"], centre, axis)
    inside = (distance <= radius_of(body, centre, axis)) & (position > first + third) & (position < last - third)
    return int(inside.sum())


def tilt_deg(axis: np.ndarray) -> float:
    """The angle between the column's axis and the image's head-foot axis, in degrees."""
    return float(np.degrees(np.arccos(min(1.0, abs(float(axis[2]))))))


def within(value: float, band: tuple) -> bool:
    return band[0] <= value <= band[1]


def cut_by_field_top(body: dict, grid) -> bool:
    """The field's top cuts the body: its voxels reach the volume's head face."""
    return "S" in F.faces_touched(body["points"], grid.shape, grid.affine)


def usable(label, column) -> bool:
    """A level whose body a step or a disc can be read from: a vertebra, not the atlas, with a body."""
    return (label is not None and label != column.sacrum and label not in column.atlas
            and len(column.bodies[label]["world"]) >= MIN_VOXELS)


def step_reference(references: list, column):
    """The first pair of levels whose step a level's own step is read against, both usable."""
    return next((pair for pair in references if all(usable(label, column) for label in pair)), None)


def outer_side(name: str, label: int, outer, column, cut: bool) -> tuple:
    """(numbers, reason or None) of a level's outer side: the disc beyond it, or, for C2, the atlas."""
    body = column.bodies[label]
    if name == "C2" and outer in column.atlas:
        return {"beyond": "the atlas, a level of its own"}, None
    if name == "C2" and outer is None:
        if cut:
            return {"beyond": "the field's top, which cuts its body"}, None
        return {}, ("nothing lies above it in the segmenter's column and the field's top does not cut its body, "
                    "so its label may hold the atlas")
    if name == "C2" and outer != column.sacrum:
        return {}, "the segmenter's level above it is its %s, not an atlas of its own, so its label may hold the atlas" % (
            column.names[outer])
    if outer is None:
        return {}, "nothing lies beyond it in the segmenter's column, so its outer side cannot be read"
    if outer in column.atlas:
        return {}, "the segmenter's level beyond it is the atlas, where the count names it %s" % name
    other = column.bodies[outer]
    if outer == column.sacrum:
        centre, axis, _ = axis_between(body, other)
        if axis is None:
            return {}, "its body's centre is the sacrum's"
        return side_reading(body, other, column, extent(other, centre, axis)[0] + SACRUM_DISC_REACH_MM)
    if len(other["world"]) < MIN_VOXELS:
        return {}, "the segmenter's subregion mask gives the level beyond it fewer than %d voxels of body" % MIN_VOXELS
    return side_reading(body, other, column)


def body_check(name: str, label: int, inner: int, references: list, outer, column) -> tuple:
    """(numbers, reason or None, INNER or None) of rule 6 for the segmenter's level label, which the
    rules would name name, beside its inner neighbour inner and its outer neighbour outer (a label, the
    sacrum's, or None); references are the pairs of levels its own step may be read against, in order of
    preference. A reason that may be the inner neighbour's as much as the level's says INNER."""
    numbers = {"largest_share": F.rounded(column.shares[label], F.SHARE_DECIMALS)}
    if column.shares[label] < LARGEST_SHARE:
        return numbers, "its largest piece holds %.0f%% of it, under %.0f%%" % (
            100 * column.shares[label], 100 * LARGEST_SHARE), None
    body, near = column.bodies[label], column.bodies[inner]
    numbers["body_voxels"] = int(len(body["world"]))
    if len(body["world"]) < MIN_VOXELS:
        return numbers, "the segmenter's subregion mask gives it fewer than %d voxels of body" % MIN_VOXELS, None
    if len(near["world"]) < MIN_VOXELS:
        return numbers, "the segmenter's subregion mask gives its inner neighbour fewer than %d voxels of body" % (
            MIN_VOXELS), INNER
    share = F.pieces(body["points"])[1]
    numbers["body_share"] = F.rounded(share, F.SHARE_DECIMALS)
    if share < BODY_SHARE:
        return numbers, "its body is in pieces, the largest holding %.1f%% of it, under %.0f%%" % (
            100 * share, 100 * BODY_SHARE), None
    centre, axis, step = axis_between(body, near)
    if axis is None:
        return numbers, "its body's centre is its inner neighbour's", INNER
    voxel = reach(column.cell, axis)
    tall = np.subtract(*extent(body, centre, axis)[::-1]) + voxel
    near_tall = np.subtract(*extent(near, centre, axis)[::-1]) + voxel
    cut = name == "C2" and cut_by_field_top(body, column.grid)
    numbers.update({"body_height_mm": F.rounded(tall, F.MM_DECIMALS),
                    "height_ratio": F.rounded(tall / near_tall, F.SHARE_DECIMALS),
                    "step_mm": F.rounded(step, F.MM_DECIMALS), "tilt_deg": F.rounded(tilt_deg(axis), F.MM_DECIMALS)})
    if name == "C2":
        numbers["cut_by_field"] = cut
    band = C2_HEIGHT_BAND if name == "C2" else HEIGHT_BAND
    low = 0.0 if cut else band[0]
    if not low <= tall / near_tall <= band[1]:
        return numbers, "its body is %.2f times its inner neighbour's height, outside %.1f to %.1f" % (
            tall / near_tall, low, band[1]), INNER
    pair = step_reference(references, column)
    if pair is None:
        return numbers, "the segmenter has no pair of bodies beside it to compare its step with", None
    against = axis_between(column.bodies[pair[0]], column.bodies[pair[1]])[2]
    ratio = step / against if against else float("inf")
    numbers["step_ratio"] = F.rounded(ratio, F.SHARE_DECIMALS) if against else None
    if not within(ratio, (0.0 if cut else STEP_BAND[0], STEP_BAND[1])):
        return numbers, "its step from its neighbour is %.1f mm against %.1f mm beside it, outside %.1f to %.1f times" % (
            step, against, STEP_BAND[0], STEP_BAND[1]), INNER
    if name != "C2" and tall / near_tall > MERGED[0] and ratio > MERGED[1]:
        return numbers, ("its body is %.2f times its neighbour's height and its step %.2f times the step beside it, "
                         "over %.2f and %.2f together, as two bodies with no disc drawn between them read") % (
            tall / near_tall, ratio, MERGED[0], MERGED[1]), INNER
    numbers["inner"], reason = side_reading(body, near, column)
    if reason:
        return numbers, "toward its inner neighbour, " + reason, INNER
    middle = middle_disc(body, column.discs, centre, axis)
    numbers["disc_voxels_middle"] = middle
    if middle >= MERGED_DISC_SHARE * numbers["inner"]["disc_voxels"]:
        return numbers, "a disc lies in the middle third of its body: %d voxels against %d beside it" % (
            middle, numbers["inner"]["disc_voxels"]), None
    numbers["outer"], reason = outer_side(name, label, outer, column, cut)
    if reason:
        return numbers, "on its outer side, " + reason, None
    return numbers, None, None


def sacrum_check(sacrum: int, above: int, column) -> tuple:
    """(numbers, reason or None, INNER or None) of rule 4's disc check, read along the axis from the
    body above the sacrum to the sacrum's centre, inside that body's cylinder, out to the sacrum's far
    end."""
    body, bone = column.bodies[above], column.bodies[sacrum]
    if len(body["world"]) < MIN_VOXELS:
        return {}, "the segmenter's subregion mask gives the level above it fewer than %d voxels of body" % MIN_VOXELS, INNER
    centre, axis, _ = axis_between(body, bone)
    if axis is None:
        return {}, "its centre is the body above it's", INNER
    first, last = extent(bone, centre, axis)
    runs = disc_runs(column.discs, centre, axis, radius_of(body, centre, axis), 0.0, last, reach(column.cell, axis))
    voxel_mm3 = abs(float(np.linalg.det(column.cell)))
    numbers = {"tilt_deg": F.rounded(tilt_deg(axis), F.MM_DECIMALS),
               "discs": [{"start_mm": F.rounded(start - first, F.MM_DECIMALS), "end_mm": F.rounded(end - first, F.MM_DECIMALS),
                          "voxels": int(len(world)), "mm3": F.rounded(len(world) * voxel_mm3, F.MM_DECIMALS)}
                         for start, end, world in runs]}
    head = [run for run in runs if run[0] < first + SACRUM_DISC_REACH_MM]
    if len(head) != 1:
        return numbers, "%d discs begin within %g mm of its head end, where one, the disc above it, should" % (
            len(head), SACRUM_DISC_REACH_MM), None
    lumbosacral = head[0]
    inside = [run for run in runs if run is not lumbosacral and len(run[2]) >= SACRUM_DISC_SHARE * len(lumbosacral[2])]
    if inside:
        start, _, world = inside[0]
        return numbers, ("a disc of %d voxels, %.0f%% of the one above it, lies %.1f mm below its head end, as a body "
                         "folded into it would hold") % (len(world), 100.0 * len(world) / len(lumbosacral[2]), start - first), None
    reading = local_reading(bone, lumbosacral[2], body["world"].mean(0) - bone["world"].mean(0), column.cell)
    numbers["own"] = rounded_reading(reading)
    if reading["overreach_share"] > OVERREACH_SHARE:
        return numbers, "%.2f%% of it lies over %g mm past the disc above it, in the body above's place, over %.1f%%" % (
            100 * reading["overreach_share"], OVER_MM, 100 * OVERREACH_SHARE), INNER
    return numbers, None, None


# ---------------------------------------------------------------- the rules

def anchors(release: dict, machine: dict, overlap: dict) -> dict:
    """{release name: segmenter label} for each pair that are each other's best match by Dice, with
    at least MATCH_INSIDE of each inside the other. release and machine give each level's voxel count,
    overlap {(name, label): shared}."""
    def dice(name, label):
        return 2.0 * overlap.get((name, label), 0) / (release[name] + machine[label])

    def inside(name, label):
        shared = overlap.get((name, label), 0)
        return shared >= MATCH_INSIDE * release[name] and shared >= MATCH_INSIDE * machine[label]
    best_label = {name: max(machine, key=lambda label: dice(name, label)) for name in release} if machine else {}
    best_name = {label: max(release, key=lambda name: dice(name, label)) for label in machine} if release else {}
    return {name: label for name, label in best_label.items()
            if best_name.get(label) == name and inside(name, label)}


def in_order(pairs: dict, chain: list) -> bool:
    """The anchors run head to foot in the same order in both arms."""
    names = sorted(pairs, key=F.COLUMN_NAMES.index)
    places = [chain.index(pairs[name]) for name in names]
    return places == sorted(places) and len(set(places)) == len(places)


def calibration(pairs: dict, column) -> tuple:
    """(rows, reason or None) of rule 7: each pair of anchors that are neighbours in the segmenter's
    column, neither the atlas, read both ways as rule 6 reads a disc."""
    by_label = {label: name for name, label in pairs.items()}
    rows = []
    for upper, lower in zip(column.chain, column.chain[1:]):
        if upper not in by_label or lower not in by_label or not (usable(upper, column) and usable(lower, column)):
            continue
        row = {"upper": by_label[upper], "lower": by_label[lower]}
        for side, body, other in (("upper_read", upper, lower), ("lower_read", lower, upper)):
            row[side], reason = side_reading(column.bodies[body], column.bodies[other], column)
            if reason:
                row["reason"] = "%s against %s: %s" % (by_label[body], by_label[other], reason)
                break
        rows.append(row)
    failed = [row for row in rows if "reason" in row]
    if len(rows) < MIN_CALIBRATION:
        return rows, ("the disc reading could be checked on %d pair(s) of the release's levels, under %d, so it is "
                      "not shown to hold on this CT" % (len(rows), MIN_CALIBRATION))
    if failed:
        return rows, ("the disc reading fails on %d of %d pairs of the release's own levels (first, %s), so it is not "
                      "trusted for the levels the release lacks" % (len(failed), len(rows), failed[0]["reason"]))
    return rows, None


def refuse(name: str, reason: str, numbers=None) -> dict:
    return dict(numbers or {}, name=name, state=REFUSED, reason=reason)


def take(name: str, label: int, naming: str, machine_names: dict, numbers: dict) -> dict:
    return dict(numbers, name=name, state=ADDED, machine_label=label, machine_name=machine_names[label],
                naming=naming)


def neighbours(at: int, step: int, column) -> tuple:
    """(inner, references, outer) of the level at the column's place at, the count reaching it from the
    level step places back (step +1 when the count runs toward the foot, -1 toward the head): the inner
    neighbour, the pairs its step may be read against, and the level beyond it, the sacrum below the
    foot-most vertebra, or None."""
    chain = column.chain
    inner = chain[at - step]
    beyond = at + step
    outer = chain[beyond] if 0 <= beyond < len(chain) else (column.sacrum if step > 0 else None)
    references = []
    if 0 <= at - 2 * step < len(chain):
        references.append((inner, chain[at - 2 * step]))
    if outer is not None and outer != column.sacrum:
        references.append((chain[at], outer))
    return inner, references, outer


def between(upper: str, lower: str, names: list, top: int, foot: int, drawn: set, column, fits) -> list:
    """The gap between two anchors at the column's places top and foot: names the release's names
    between them. Each level is read with its inner neighbour above it, but C2 under the atlas, which
    is read with C3 below it as its inner neighbour and the atlas above as its outer."""
    targets = [name for name in names if name not in drawn]
    unmatched = [name for name in names if name in drawn]
    if unmatched:
        reason = "the release draws %s between %s and %s and the segmenter matches none of it" % (
            ", ".join(unmatched), upper, lower)
        return [refuse(name, reason) for name in targets]
    places = list(range(top + 1, foot))
    if len(places) != len(names):
        reason = "the segmenter has %d levels between %s and %s, where the release's names leave %d" % (
            len(places), upper, lower, len(names))
        return [refuse(name, reason) for name in targets]
    out, failed = [], None
    for name, at in zip(names, places):
        step = -1 if name == "C2" and column.chain[at - 1] in column.atlas else 1
        inner, references, outer = neighbours(at, step, column)
        numbers, reason, _ = fits(name, column.chain[at], inner, references, outer)
        out.append((name, column.chain[at], numbers))
        if reason and not failed:
            failed = "the segmenter's level the count names %s between %s and %s: %s; so no level of the gap is taken" % (
                name, upper, lower, reason)
    if failed:
        return [refuse(name, failed, numbers) for name, _, numbers in out]
    return [take(name, label, "between %s and %s" % (upper, lower), column.names, numbers)
            for name, label, numbers in out]


def outwards(anchor: str, names: list, start: int, step: int, drawn: set, column, fits) -> tuple:
    """Names beyond the end anchor at the column's place start, walked outwards one level at a time
    (step -1 toward the head, +1 toward the foot): (outcomes, [(name, label)] of the levels the walk
    took, in order). A level that fails against the level inward of it refuses that level too, where
    the walk took it."""
    side = "above" if step < 0 else "below"
    out, walked, stopped = [], [], None
    for i, name in enumerate(names):
        if stopped:
            if name not in drawn:
                out.append(refuse(name, stopped))
            continue
        if name in drawn:
            stopped = "the release draws %s %s %s and the segmenter matches none of it" % (name, side, anchor)
            continue
        at = start + step * (i + 1)
        if not 0 <= at < len(column.chain):
            stopped = "the segmenter has no level %s %s for %s" % (side, anchor, name)
            out.append(refuse(name, stopped))
            continue
        label = column.chain[at]
        if column.names[label] != name:
            stopped = "the count %s %s gives %s where the segmenter calls the level %s" % (
                side, anchor, name, column.names[label])
            out.append(refuse(name, stopped))
            continue
        inner, references, outer = neighbours(at, step, column)
        numbers, reason, against = fits(name, label, inner, references, outer)
        if reason:
            stopped = "the segmenter's level the count %s %s names %s: %s" % (side, anchor, name, reason)
            out.append(refuse(name, stopped, numbers))
            if against == INNER and walked:
                out = revisit(out, walked, name, reason)
            continue
        out.append(take(name, label, "%s %s, named alike by the count and the segmenter" % (side, anchor),
                        column.names, numbers))
        walked.append((name, label))
    return out, walked


def revisit(out: list, walked: list, name: str, reason: str) -> list:
    """The outcomes with the level the walk took last refused, since the level beyond it, which the
    count names name, failed against it; walked loses it."""
    last, _ = walked.pop()
    why = "the next level out, which the count names %s, fails against it: %s" % (name, reason)
    return [refuse(last, why, {k: v for k, v in o.items() if k not in ("name", "state", "machine_label",
                                                                          "machine_name", "naming")})
            if o["name"] == last else o for o in out]


def sacrum_outcome(pairs: dict, drawn: set, walked: list, targets: list, column, fits_sacrum) -> tuple:
    """(outcome, against) of the segmenter's sacrum, where the release's foot-most level is an anchor,
    every segmenter level from that anchor down to the sacrum was taken by the walk and asked for, and
    the level directly above it is the last lumbar."""
    sacrum = column.sacrum
    if sacrum is None:
        return refuse(SACRUM, "the segmenter draws no sacrum"), None
    column_names = [name for name in drawn if name != SACRUM]
    last = max(column_names, key=F.COLUMN_NAMES.index) if column_names else None
    if last is None or last not in pairs:
        return refuse(SACRUM, "the release's foot-most level %s is not matched by the segmenter" % last), None
    after = column.chain[column.chain.index(pairs[last]) + 1 + len(walked):]
    if after:
        return refuse(SACRUM, "the segmenter has %d level(s) between the release's %s and the sacrum that no "
                              "name accounts for" % (len(after), last)), None
    unasked = [name for name, _ in walked if name not in targets]
    if unasked:
        return refuse(SACRUM, "the count names the segmenter's level(s) below the release's %s %s, which the "
                              "field test does not ask for, so the sacrum would lie under a body no "
                              "arm draws" % (last, ", ".join(unasked))), None
    above, label = walked[-1] if walked else (last, pairs[last])
    if above not in LAST_LUMBAR:
        return refuse(SACRUM, "the sacrum would lie directly under %s, and a body the segmenter folds into "
                              "its sacrum cannot be told from a spine with fewer lumbar levels" % above), None
    numbers, reason, against = fits_sacrum(sacrum, label)
    if reason:
        return refuse(SACRUM, "the segmenter's sacrum below %s: %s" % (above, reason), numbers), against
    return take(SACRUM, sacrum, "the segmenter's sacrum, below %s" % above, {sacrum: SACRUM}, numbers), None


def plan(drawn: set, targets: list, pairs: dict, column, fits, fits_sacrum) -> list:
    """Each target's outcome: drawn is the release's drawn names, pairs the anchors, column the
    segmenter's column (column_of); fits(name, label, inner, references, outer), read as body_check
    reads them, and fits_sacrum(label, above) give (numbers, reason or None, INNER or None) of rules 5
    and 6 and of rules 4 and 5."""
    chain = column.chain
    if not pairs:
        return [refuse(name, "no release level is matched by the segmenter") for name in targets]
    if not in_order(pairs, chain):
        return [refuse(name, "the anchors run in another order in the segmenter's column") for name in targets]
    names = sorted((set(drawn) | set(TARGET_NAMES)) - {SACRUM}, key=F.COLUMN_NAMES.index)
    ends = sorted(pairs, key=F.COLUMN_NAMES.index)
    out = []
    for upper, lower in zip(ends, ends[1:]):
        gap = [n for n in names if F.COLUMN_NAMES.index(upper) < F.COLUMN_NAMES.index(n) < F.COLUMN_NAMES.index(lower)]
        if gap:
            out += between(upper, lower, gap, chain.index(pairs[upper]), chain.index(pairs[lower]), drawn, column, fits)
    first, last = ends[0], ends[-1]
    above = [n for n in names if F.COLUMN_NAMES.index(n) < F.COLUMN_NAMES.index(first)][::-1]
    head, _ = outwards(first, above, chain.index(pairs[first]), -1, drawn, column, fits)
    below = [n for n in names if F.COLUMN_NAMES.index(n) > F.COLUMN_NAMES.index(last)]
    foot, walked = outwards(last, below, chain.index(pairs[last]), 1, drawn, column, fits)
    if SACRUM in targets:
        sacrum, against = sacrum_outcome(pairs, drawn, walked, targets, column, fits_sacrum)
        if against == INNER and walked:
            foot = revisit(foot, walked, SACRUM, sacrum["reason"])
        foot.append(sacrum)
    out += head + foot
    found = {o["name"]: o for o in out}
    return [found.get(name) or refuse(name, "no rule here names %s: the count runs from C2 to L5 and over the "
                                            "release's own names, and the sacrum" % name)
            for name in targets]


def voxel_check(level: np.ndarray, release_all: np.ndarray, others: np.ndarray, fragment) -> tuple:
    """(numbers, reason or None) of rule 5: the voxels a named level adds and how much of it the
    release's other levels hold."""
    own = len(level)
    added = own - common(level, release_all)
    share = common(level, others) / own if own else 1.0
    numbers = {"voxels": int(own), "added_voxels": int(added), "release_share": F.rounded(share, F.SHARE_DECIMALS)}
    if fragment is not None:
        numbers["release_fragment_voxels"] = int(len(fragment))
        numbers["release_fragment_inside"] = common(fragment, level)
    if added < MIN_VOXELS:
        return numbers, "it adds %d voxels outside the release's, under %d" % (added, MIN_VOXELS)
    if share > MAX_RELEASE_SHARE:
        return numbers, "%.1f%% of it lies under the release's other levels, over %d%%" % (
            100 * share, 100 * MAX_RELEASE_SHARE)
    return numbers, None


# ---------------------------------------------------------------- one study

def targets_of(drawn: set, asked=None) -> list:
    """The names to add, in the column's order: those asked for, else every one from C2 to L5 and the
    sacrum; a name the release draws is never a target."""
    wanted = TARGET_NAMES if asked is None else asked
    unknown = sorted(set(wanted) - set(F.COLUMN_NAMES))
    if unknown:
        raise ValueError("targets outside the column: %s" % ", ".join(unknown))
    return [name for name in F.COLUMN_NAMES if name in wanted and name not in drawn]


def chain_of(machine: dict, affine) -> tuple:
    """The segmenter's vertebrae of at least MIN_VOXELS head to foot, its sacrum, and the levels
    left out for size."""
    kept = {label: points for label, points in machine.items() if len(points) >= MIN_VOXELS}
    heights = {label: height(points, affine) for label, points in kept.items()}
    sacrum = VERSE_IDS[SACRUM] if VERSE_IDS[SACRUM] in kept else None
    chain = sorted((label for label in kept if label != VERSE_IDS[SACRUM]), key=lambda label: -heights[label])
    small = sorted(label for label in machine if label not in kept)
    return chain, sacrum, heights, small


def others_of(sets: dict, name: str) -> np.ndarray:
    rest = [indices for other, indices in sets.items() if other != name]
    return np.unique(np.concatenate(rest)) if rest else np.zeros(0, np.int64)


def checkers(sets, machine_sets, release_all, column):
    """fits and fits_sacrum for plan(): rule 5 for every level, then rule 6 for a vertebra or rule 4's
    disc check for the sacrum."""
    def voxels(name, label):
        return voxel_check(machine_sets[label], release_all, others_of(sets, name), sets.get(name))

    def fits(name, label, inner, references, outer):
        numbers, reason = voxels(name, label)
        if reason:
            return numbers, reason, None
        body, reason, against = body_check(name, label, inner, references, outer, column)
        return dict(numbers, body=body), reason, against

    def fits_sacrum(label, above):
        numbers, reason = voxels(SACRUM, label)
        if reason:
            return numbers, reason, None
        body, reason, against = sacrum_check(label, above, column)
        return dict(numbers, body=body), reason, against
    return fits, fits_sacrum


def anchor_rows(pairs: dict, overlap: dict, sets: dict, machine_sets: dict, machine_names: dict) -> list:
    rows = []
    for name in sorted(pairs, key=F.COLUMN_NAMES.index):
        label = pairs[name]
        shared, r, m = overlap[(name, label)], len(sets[name]), len(machine_sets[label])
        rows.append({"release": name, "machine_label": label, "machine_name": machine_names[label],
                     "dice": F.rounded(2.0 * shared / (r + m), F.SHARE_DECIMALS),
                     "inside_release": F.rounded(shared / r, F.SHARE_DECIMALS),
                     "inside_machine": F.rounded(shared / m, F.SHARE_DECIMALS)})
    return rows


def complete_study(member: str, release: str, machine_path: str, spine_path: str, asked=None):
    """(record, release levels {name: points}, completed levels {name: indices}, arm {name: indices},
    grid) of one study."""
    grid, levels, release_record = release_levels(member, release)
    machine_grid, machine, machine_file = machine_levels(machine_path)
    spine_grid, corpus, disc, spine_file = subregions(spine_path)
    if not F.same_grid(grid, machine_grid) or not F.same_grid(grid, spine_grid):
        raise ValueError("the segmenter's masks lie on another grid than the release's")
    shape, affine = grid.shape, grid.affine
    sets = {name: flat(points, shape) for name, points in levels.items()}
    machine_sets = {label: flat(points, shape) for label, points in machine.items()}
    drawn = {name for name, points in levels.items() if len(points) >= MIN_VOXELS}
    chain, sacrum, heights, small = chain_of(machine, affine)
    machine_names = {label: F.VERSE_NAMES[label] for label in machine}
    overlap = {(name, label): common(sets[name], machine_sets[label])
               for name in drawn - {SACRUM} for label in chain}
    pairs = anchors({name: len(sets[name]) for name in drawn - {SACRUM}},
                    {label: len(machine_sets[label]) for label in chain}, overlap)
    atlas = {label for label in chain if machine_names[label] == ATLAS} | ({pairs[ATLAS]} if ATLAS in pairs else set())
    column = column_of(machine, corpus, disc, grid, chain, sacrum, atlas)
    del corpus, disc
    targets = targets_of(drawn, asked)
    release_all = np.unique(np.concatenate(list(sets.values()))) if sets else np.zeros(0, np.int64)
    rows, untrusted = calibration(pairs, column) if pairs and in_order(pairs, chain) else ([], None)
    if untrusted:
        outcomes = [refuse(name, untrusted) for name in targets]
    else:
        fits, fits_sacrum = checkers(sets, machine_sets, release_all, column)
        outcomes = plan(drawn, targets, pairs, column, fits, fits_sacrum)
    arm, completed = {}, {}
    for outcome in outcomes:
        if outcome["state"] == ADDED:
            name = outcome["name"]
            level = np.setdiff1d(machine_sets[outcome["machine_label"]], others_of(sets, name), assume_unique=True)
            arm[name] = np.setdiff1d(level, release_all, assume_unique=True)
            completed[name] = np.union1d(arm[name], sets[name]) if name in sets else arm[name]
    record = {"files": {"release": release_record,
                        "machine": {os.path.basename(machine_path): machine_file,
                                    os.path.basename(spine_path): spine_file}},
              "anchors": anchor_rows(pairs, overlap, sets, machine_sets, machine_names),
              "calibration": {"pairs": rows, "reason": untrusted},
              "machine_column": [{"label": label, "name": machine_names[label], "voxels": int(len(machine[label])),
                                  "height_mm": F.rounded(heights[label], F.MM_DECIMALS)}
                                 for label in chain + ([sacrum] if sacrum else [])],
              "machine_small": [{"label": label, "voxels": int(len(machine[label]))} for label in small],
              "drawn": sorted(drawn, key=F.COLUMN_NAMES.index),
              "asked": None if asked is None else [n for n in F.COLUMN_NAMES if n in asked],
              "targets": outcomes,
              "added": [o["name"] for o in outcomes if o["state"] == ADDED],
              "refused": [o["name"] for o in outcomes if o["state"] == REFUSED]}
    return record, levels, completed, arm, grid


def points_of(indices: np.ndarray, shape) -> np.ndarray:
    return np.stack(np.unravel_index(indices, shape), axis=1).astype(np.int32)


def arm_image(arm: dict, grid):
    """The added levels in VerSe's ids, on the release's grid, as an unsigned byte NIfTI."""
    shape = grid.shape
    volume = np.zeros(shape, np.uint8, order="F")
    for name, indices in arm.items():
        volume[np.unravel_index(indices, shape)] = VERSE_IDS[name]
    out = nib.Nifti1Image(volume, grid.affine)
    out.set_qform(grid.affine, code=1)
    out.set_sform(grid.affine, code=1)
    return out


def arm_bytes(arm: dict, grid) -> bytes:
    """The arm's .nii.gz bytes, the same on every run: gzip is given no time and no file name."""
    return gzip.compress(arm_image(arm, grid).to_bytes(), compresslevel=6, mtime=0)


def arm_name(sid: str, data: bytes) -> str:
    """A mask's file name, from its study and its bytes, so a run with other results writes another
    file rather than over one an earlier record vouches for."""
    return "%s_machine_%s.nii.gz" % (sid, hashlib.sha256(data).hexdigest()[:12])


def completed_row(row: dict, levels: dict, completed: dict, grid, record: dict, arm_file: dict) -> dict:
    """The facts row with the added levels drawn, each read as holdings.fullspine_facts reads a level
    from its voxels in both arms: the release's own fragment of it, if any, and the segmenter's."""
    shape, affine = grid.shape, grid.affine
    out = json.loads(json.dumps(row))
    points = dict(levels)
    for name, indices in completed.items():
        points[name] = points_of(indices, shape)
        out["levels"][name] = F.label_facts(points[name], affine, shape)
    out["levels"] = {name: out["levels"][name] for name in F.COLUMN_NAMES if name in out["levels"]}
    out["distances_mm"] = F.lumbosacral_distances(points, affine)
    out["machine_levels"] = {o["name"]: {"machine_label": o["machine_label"], "naming": o["naming"],
                                         "voxels": o["voxels"], "added_voxels": o["added_voxels"]}
                             for o in record["targets"] if o["state"] == ADDED}
    out["machine_files"] = arm_file
    return out


def study_job(job) -> dict:
    sid, member, release, machine, spine, how, asked, segmenter, row, masks, digest = job
    record, levels, completed, arm, grid = complete_study(member, release, machine, spine, asked)
    if not same_release(levels, row):
        raise ValueError("the release read here differs from the one its facts row was read from")
    out = {"id": sid, "member": member, "segmenter": segmenter, "input": how, "job_sha256": digest, **record}
    if arm:
        data = arm_bytes(arm, grid)
        name = arm_name(sid, data)
        with open(os.path.join(masks, name + ".tmp"), "wb") as f:
            f.write(data)
        os.replace(os.path.join(masks, name + ".tmp"), os.path.join(masks, name))
        out["files"]["arm"] = {name: F.file_record(data)}
        out["completed_facts"] = completed_row(row, levels, completed, grid, out, out["files"]["arm"])
    return out


def study_safe(job) -> dict:
    """A study's row, or, where it cannot be read, a row with its error that still says whose it is and
    which job made it."""
    row = F.safe(study_job)(job)
    if "error" in row:
        row.update(member=job[1], segmenter=job[7], job_sha256=job[10])
    return row


# ---------------------------------------------------------------- running

def facts_rows(path: str) -> dict:
    with open(path, encoding="ascii") as f:
        return {row["id"]: row for row in map(json.loads, f)}


def job_digest(sid, member, release, machine, spine, how, asked, segmenter, row) -> str:
    """The sha256 of what a study's row is made from: this module's and its readers' code, the job's
    fields and the bytes of every file the study reads, but none of their paths."""
    digest = hashlib.sha256()
    for path in CODE:
        digest.update(read_bytes(path))
    fields = {"id": sid, "member": member, "input": how, "targets": asked, "segmenter": segmenter, "facts": row}
    digest.update(json.dumps(fields, sort_keys=True, separators=(",", ":")).encode("ascii"))
    for path in release_files(member, release) + [machine, spine]:
        digest.update(hashlib.sha256(read_bytes(path)).digest())
    return digest.hexdigest()


def jobs_of(spec: dict, masks: str) -> list:
    facts = {member: facts_rows(path) for member, path in spec["facts"].items()}
    out = []
    for study in spec["studies"]:
        how = json.loads(read_bytes(study["input"])) if study.get("input") else None
        fields = (study["id"], study["member"], study["release"], study["machine"], study["spine"], how,
                  study.get("targets"), spec["segmenter"], facts[study["member"]][study["id"]])
        out.append(fields + (masks, job_digest(*fields)))
    return out


def keep_current(part: str, jobs: list) -> int:
    """Drop from a cut-short run's OUT.part every row whose job's digest is not its job's now, or whose
    study is no longer a job, so the run reads those studies again; returns how many were dropped."""
    rows = F.rows_written(part)
    if not rows:
        return 0
    now = {job[0]: job[10] for job in jobs}
    kept = [row for row in rows if row.get("job_sha256") is not None and now.get(row["id"]) == row["job_sha256"]]
    with open(part + ".tmp", "w", encoding="ascii", newline="\n") as f:
        f.writelines(F.row_line(row) for row in kept)
    os.replace(part + ".tmp", part)
    return len(rows) - len(kept)


def read_records(records: str) -> list:
    with open(records, encoding="ascii") as f:
        return [json.loads(line) for line in f]


def split_out(records: list, facts: str) -> int:
    """facts.jsonl from the records' completed rows, sorted by id."""
    return F.write_rows([record["completed_facts"] for record in records if "completed_facts" in record], facts)


def sweep_masks(records: list, masks: str) -> list:
    """Remove every file in masks/ that no record names as its arm, a study refused, failed or dropped
    since an earlier run among them, so masks/ holds only what records.jsonl vouches for."""
    kept = {name for record in records for name in record.get("files", {}).get("arm", {})}
    removed = sorted(name for name in os.listdir(masks) if name not in kept)
    for name in removed:
        os.remove(os.path.join(masks, name))
    return removed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("jobs")
    parser.add_argument("out")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args(argv)
    masks = os.path.join(args.out, "masks")
    os.makedirs(masks, exist_ok=True)
    spec = json.loads(read_bytes(args.jobs))
    jobs = jobs_of(spec, masks)
    records = os.path.join(args.out, "records.jsonl")
    dropped = keep_current(records + ".part", jobs)
    n = F.run(study_safe, jobs, records, args.workers)
    rows = read_records(records)
    m = split_out(rows, os.path.join(args.out, "facts.jsonl"))
    removed = sweep_masks(rows, masks)
    print("%d records (%d earlier rows read again for other code or masks), %d completed facts rows, "
          "%d stale masks removed" % (n, dropped, m, len(removed)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
