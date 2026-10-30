"""A CT's label volume to a column: every vertebra's chords, top down, in its own frame.

    python -m scanimport ingest-ct --labels seg.nii.gz --scheme verse --study s0001 \
        --source verse --annotation human --out imports/verse
    python -m scanimport ingest-ct --labels inst.nii.gz --subregion sub.nii.gz --scheme spineps ...
    python -m scanimport ingest-ct --labels s0001/segmentations --scheme totalseg ...

The label volume is read with nibabel, whose affine maps voxels into the RAS world a NIfTI file
is defined in; the chords are taken in that world (geometry.py), so nothing is resampled or
reoriented and the file is never written back. Each vertebra is found by its label under the
scheme (schemes.py), its voxels taken from its bounding box, and measured whole
(geometry.measure_whole) or, for SPINEPS with its subregion volume, by its labelled parts
(geometry.measure_labelled). C1 and C2 are named and not measured: Panjabi gives C2 no upper
end-plate row (the dens occupies it) and the rule's column starts at C3. The sacrum is named, so
the study can be called gold, and not measured.

`annotation` is the caller's statement of who drew the labels: human for a release's reader-drawn
or reader-corrected masks (VerSe, TotalSegmentator's release), machine for a segmenter's output
(SPINEPS, MOOSE). It is recorded and never inferred, and a machine mask never raises a tier
(tiers.py).
"""
from __future__ import annotations

import json
import math
import os
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import ndimage

from . import CERVICAL, LEVELS, MEASURES, NOT_MEASURED, SEVEN, schemes
from . import geometry as G
from .column import Body, Column, facts_from_levels



def load(path: str):
    import nibabel as nib
    img = nib.load(path)
    return np.asanyarray(img.dataobj), np.asarray(img.affine, float)


def spineps_parts(vol: np.ndarray) -> Tuple[np.ndarray, Dict[str, int], List[str]]:
    """A SPINEPS instance volume with its end-plates joined to their vertebrae and its discs left
    out. SPINEPS writes the disc below vertebra X as 100 + X and that vertebra's end-plate as
    200 + X (archive/bordercall/SPINEPS_MAPPING.md); an end-plate read as nothing would take the
    end-plate rim off the body and shorten every end-plate chord, so each 200 + X becomes X, and
    each 100 + X becomes background, a disc being no part of a vertebra. An end-plate whose
    vertebra is absent from the volume is left out and named."""
    out = vol.astype(np.int32, copy=True)
    plates = (out > 200) & (out < 300)
    discs = (out > 100) & (out < 200)
    counts = {"endplate_voxels_joined": 0, "disc_voxels_left_out": int(discs.sum())}
    problems: List[str] = []
    vertebrae = set(np.unique(out[(out > 0) & (out < 100)]).tolist())
    for v in np.unique(out[plates]).tolist():
        here = out == v
        if v - 200 in vertebrae:
            out[here] = v - 200
            counts["endplate_voxels_joined"] += int(here.sum())
        else:
            out[here] = 0
            problems.append("end-plate label %d has no vertebra %d in the volume; its %d voxels are left out"
                            % (v, v - 200, int(here.sum())))
    out[discs] = 0
    return out, counts, problems


def read_labels(labels: str, scheme: str, label_map: Optional[Dict[int, str]] = None
                ) -> Tuple[np.ndarray, G.VoxelGrid, Dict[int, str], List[str], Dict[str, int]]:
    """The label volume as integers, its grid, which value names which level, any problems in
    words, and what was joined or left out before naming (SPINEPS's end-plates and discs). A
    TotalSegmentator folder of one mask per structure is stacked into one volume, each level
    under its index in LEVELS plus one."""
    problems: List[str] = []
    merged: Dict[str, int] = {}
    if scheme == "totalseg" and os.path.isdir(labels):
        vol, affine, names = None, None, {}
        for fname in sorted(os.listdir(labels)):
            stem = fname.split(".")[0]
            level = schemes.TOTALSEG_FILES.get(stem)
            if level is None:
                continue
            data, aff = load(os.path.join(labels, fname))
            if vol is None:
                vol, affine = np.zeros(data.shape, np.int16), aff
            elif data.shape != vol.shape or not np.allclose(aff, affine, atol=1e-4):
                problems.append("%s is on another grid; left out" % fname)
                continue
            v = LEVELS.index(level) + 1
            m = np.asarray(data) > 0
            if (vol[m] > 0).any():
                problems.append("%s overlaps another structure in %d voxels" % (fname, int((vol[m] > 0).sum())))
            vol[m & (vol == 0)] = v
            names[v] = level
        if vol is None:
            raise SystemExit("no vertebrae_*.nii.gz or sacrum file under %s" % labels)
        return vol, G.VoxelGrid(affine, vol.shape), names, problems, merged
    data, affine = load(labels)
    vol = np.asarray(data)
    if not np.issubdtype(vol.dtype, np.integer):
        if not np.allclose(vol, np.round(vol)):
            raise SystemExit("%s holds non-integer values; it is not a label volume" % labels)
        vol = np.round(vol).astype(np.int32)
    if scheme == "spineps" and label_map is None:
        vol, merged, problems = spineps_parts(vol)
    present = {int(v): int(c) for v, c in zip(*np.unique(vol[vol > 0], return_counts=True))}
    if label_map is None:
        problems += schemes.problems(scheme, present)
    names = {v: schemes.level_of(scheme, v, label_map) for v in present}
    return vol, G.VoxelGrid(affine, vol.shape), {v: n for v, n in names.items() if n}, problems, merged


def vertebra_voxels(vol: np.ndarray, names: Dict[int, str]) -> Dict[str, np.ndarray]:
    """Each named level's voxel indices, found inside its bounding box."""
    out: Dict[str, np.ndarray] = {}
    boxes = ndimage.find_objects(np.where(np.isin(vol, list(names)), vol, 0).astype(np.int32))
    for v, level in names.items():
        if v - 1 >= len(boxes) or boxes[v - 1] is None:
            continue
        sl = boxes[v - 1]
        idx = np.argwhere(vol[sl] == v) + np.array([s.start for s in sl])
        if level in out:                                 # two values for one level (sacrum and S1)
            out[level] = np.concatenate([out[level], idx])
        else:
            out[level] = idx
    return out


def touching_edge(idx: np.ndarray, shape) -> np.ndarray:
    return ((idx == 0) | (idx == np.asarray(shape) - 1)).any(1)


def measure_volume(vol: np.ndarray, grid: G.VoxelGrid, names: Dict[int, str],
                   sub: Optional[np.ndarray] = None) -> List[Body]:
    """Every named level as a body, top down, measured where it can be."""
    vox = vertebra_voxels(vol, names)
    order = [lv for lv in LEVELS if lv in vox]
    cents = [grid.world(vox[lv].astype(float)).mean(0) for lv in order]
    axes = G.column_axes(cents, grid.superior())
    canal_idx = np.argwhere(sub == schemes.SUB_CANAL) if sub is not None else None
    labels = {"body": schemes.SUB_BODY, "endplate_sup": schemes.SUB_ENDPLATE_SUP,
              "endplate_inf": schemes.SUB_ENDPLATE_INF, "costal": (schemes.SUB_COSTAL_L, schemes.SUB_COSTAL_R),
              "spinous": schemes.SUB_SPINOSUS}
    bodies = []
    for lv, ez in zip(order, axes):
        b = Body(level=lv)
        if lv in NOT_MEASURED:
            b.flags = {"all": "named, not measured: %s" % ("the rule's column starts at C3" if lv in CERVICAL else "the sacrum carries no row")}
            bodies.append(b)
            continue
        idx = vox[lv]
        touch = touching_edge(idx, vol.shape)
        if len(idx) < G.MIN_BODY_VOXELS:
            b.flags = {"all": "only %d voxels" % len(idx)}
        elif sub is not None:
            got = G.measure_labelled(idx, sub[tuple(idx.T)], canal_idx, grid, ez, touch, labels)
            b.values, b.flags = got.values, got.flags
            b.methods = {m: "spineps subregions, vertebra frame" for m in MEASURES}
        else:
            got = G.measure_whole(idx, grid, ez, touch)
            b.values, b.flags = got.values, got.flags
            b.methods = {m: "whole-vertebra label, canal as a hole, vertebra frame" for m in MEASURES}
        for m in MEASURES:
            v = b.values.get(m, math.nan)
            if not np.isfinite(v):
                b.flags.setdefault(m, b.flags.get("all", b.flags.get("body", "not taken")))
        bodies.append(b)
    return bodies


def ingest(labels: str, scheme: str, study_id: str, source: str, annotation: str, made_by: str,
           subject_id: Optional[str] = None, subregion: Optional[str] = None,
           label_map_path: Optional[str] = None) -> Column:
    if annotation not in ("human", "machine"):
        raise SystemExit("--annotation is human or machine, the caller's statement of who drew the labels")
    label_map = None
    if label_map_path:
        with open(label_map_path) as fh:
            label_map = {int(k): v for k, v in json.load(fh).items()}
    vol, grid, names, problems, merged = read_labels(labels, scheme, label_map)
    sub = None
    if subregion:
        sdata, saff = load(subregion)
        if sdata.shape != vol.shape or not np.allclose(saff, grid.affine, atol=1e-4):
            raise SystemExit("the subregion volume is on another grid than the labels")
        sub = np.asarray(sdata).astype(np.int32)
    bodies = measure_volume(vol, grid, names, sub)
    levels = [b.level for b in bodies]
    expresses = dict(schemes.EXPRESSES.get(scheme, {}))
    if label_map is not None:
        expresses = {"L6": False, "T13": False, "ribs": False}
    study = {"study_id": study_id, "subject_id": subject_id or study_id, "source": source, "modality": "ct",
             "views": ["ct"], "annotation": annotation, "made_by": made_by, "scheme": scheme,
             "expresses": expresses, "scale_log_mean": 0.0, "scale_log_sd": 0.0,
             "spacing_mm": [round(float(s), 4) for s in grid.spacing], "problems": problems,
             "labels_merged": merged,
             "measured": sorted(m for m in SEVEN if any(np.isfinite(b.values.get(m, math.nan)) for b in bodies))}
    study.update(facts_from_levels(levels, expresses))
    return Column(study=study, bodies=bodies)
