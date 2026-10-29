"""Every label volume of a dataset written once as int16, so the readers (facts.py, morphometry)
never hold a float64 temporary: VerSe writes 365 of its 374 masks as float64, and a 512 x 512 x
2023 mask read whole took 12 GB (facts._voxel_points). The owner's word of 29 October 2026, 15:20
UTC: "do total segmentator wtf? and if it makes sense conver all the masks to int16".

    python -m screening int16 --labels PATH --scheme SCHEME --out OUT.nii.gz [--manifest OUT.json]

What is converted. A label volume whose voxels are stored as floats, or as an integer wider than
two bytes, is written again as int16 with the same affine and header, losslessly or not at all:
every voxel must be a whole number within int16's range, checked exactly a slab at a time, and
the saved file is reloaded and compared in shape, affine and voxels before it replaces the
output; a failure raises ValueError and leaves no output file. The header's dtype is set to
int16 with scl_slope 1 and scl_inter 0 (so on disk; nibabel reads that pair back as no scaling
at all), and the qform and sform are carried over with their codes. This is the port of the
VerSe helper tools/to_int16.py (the morphometry run verse-2026-10-29) with its checks kept.

What is kept. A mask already in an integer type of at most two bytes (uint8, int8, int16,
uint16) is not rewritten: its record says "kept", its out is the source itself, and where the
caller's output path differs from the source the output is made a symlink to it, so a folder of
outputs is complete.

What is stacked. A TotalSegmentator subject's folder of one binary mask per structure
(vertebrae_C1 ... vertebrae_L5, vertebrae_S1 or sacrum, with the skull, hips, ribs and the rest
left out; the subject's folder itself or its segmentations/ subfolder, facts.mask_folder) becomes
one int16 volume in VerSe's ids, the one alphabet every other scheme is read into: C1 to C7 =
1 to 7, T1 to T12 = 8 to 19, L1 to L5 = 20 to 24, L6 = 25, sacrum = 26, T13 = 28
(scanimport/schemes.py: VERSE, and TOTALSEG_FILES for the file stems; no second table here). A
voxel two structures both claim goes to the first in the column's order, C1 first and the sacrum
last, and such voxels are counted (overlap_voxels), never hidden.

The manifest record, written as JSON when --manifest is given: action (converted, kept,
stacked), scheme, source {files {name: {bytes, sha256}}}, out {path, bytes, sha256, dtype,
values: the nonzero values present}, and for a folder overlap_voxels and levels {level: value},
for a volume problems, what scanimport's scheme check says of the values present; a kept file's
out carries copy: none and, where one was made, symlink: the output path.

The decisions are pure functions with contracts (verse_value, kept_as_is, lossless, action_for);
numpy, nibabel and the files stay in the private functions and in convert, the edge.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Dict, List, Optional, Tuple

from scanimport import schemes

from . import ORDER
from .contracts import beartype, ensure, require
from .facts import mask_folder

ACTIONS = ("converted", "kept", "stacked")
INT16_LOW, INT16_HIGH = -32768, 32767
# numpy's dtype.kind letters for a signed and an unsigned integer
INTEGER_KINDS = ("i", "u")
# an integer stored in at most this many bytes fits int16's reading and is kept as it is
KEPT_ITEMSIZE = 2
# a volume is checked and written sixteen planes of its last axis at a time, as the helper did
SLAB_PLANES = 16
# the level each VerSe id names, inverted: the level's id
VALUE_OF: Dict[str, int] = {level: value for value, level in schemes.VERSE.items()}
# a bound beyond int16's range standing in for an infinite voxel, so the check stays in integers
BEYOND = 1 << 40


# ---------------------------------------------------------------- pure decisions

@beartype
@require(lambda level: level in ORDER, "a level the column's order names")
@ensure(lambda result: 1 <= result <= 28, "a VerSe id, 1 to 28")
@ensure(lambda level, result: schemes.VERSE[result] == level, "the id VerSe gives that level")
def verse_value(level: str) -> int:
    """The VerSe id of a level name (C1 to C7, T1 to T13, L1 to L6, the sacrum)."""
    return VALUE_OF[level]


@beartype
@require(lambda kind: len(kind) == 1, "numpy's dtype.kind, one letter")
@require(lambda itemsize: itemsize >= 1, "a stored value takes at least one byte")
@ensure(lambda kind, itemsize, result: result == (kind in INTEGER_KINDS and itemsize <= KEPT_ITEMSIZE),
        "kept exactly when the values are integers of at most two bytes")
def kept_as_is(kind: str, itemsize: int) -> bool:
    """Whether a mask stored in this dtype is left as it is: an integer of at most two bytes."""
    return kind in INTEGER_KINDS and itemsize <= KEPT_ITEMSIZE


@beartype
@require(lambda non_integer: non_integer >= 0, "a count of voxels that are not whole numbers")
@require(lambda low, high: low <= high, "the least whole value is at most the greatest")
@ensure(lambda non_integer, low, high, result: result == (non_integer == 0 and INT16_LOW <= low and high <= INT16_HIGH),
        "lossless exactly when every voxel is a whole number within int16's range")
def lossless(non_integer: int, low: int, high: int) -> bool:
    """Whether a volume with this many non-whole voxels and these least and greatest whole values
    is written as int16 without losing a voxel."""
    return non_integer == 0 and INT16_LOW <= low and high <= INT16_HIGH


@beartype
@require(lambda kind: len(kind) == 1, "numpy's dtype.kind, one letter")
@require(lambda itemsize: itemsize >= 1, "a stored value takes at least one byte")
@ensure(lambda result: result in ACTIONS, "one of the three actions")
@ensure(lambda is_folder, result: (result == "stacked") == is_folder, "a folder is stacked, a file never")
@ensure(lambda kind, itemsize, is_folder, result: is_folder or (result == "kept") == kept_as_is(kind, itemsize),
        "a file is kept when its dtype is, converted otherwise")
def action_for(kind: str, itemsize: int, is_folder: bool) -> str:
    """What the converter does with a source: a folder of masks is stacked, a file in a small
    integer type kept, any other file converted."""
    if is_folder:
        return "stacked"
    return "kept" if kept_as_is(kind, itemsize) else "converted"


# ---------------------------------------------------------------- numpy and nibabel, at the edge

def _slabs(shape) -> List[Tuple[int, int]]:
    """(start, stop) along the last axis, SLAB_PLANES planes at a time."""
    return [(start, min(start + SLAB_PLANES, shape[-1])) for start in range(0, shape[-1], SLAB_PLANES)]


def _bound(value) -> int:
    """A voxel value as a Python int, an infinite one standing beyond int16's range."""
    import math
    if not math.isfinite(float(value)):
        return -BEYOND if value < 0 else BEYOND
    return int(value)


def _whole_slab(dataobj, start: int, stop: int):
    """A slab's voxels rounded to whole numbers, with how many were not whole and its bounds."""
    import numpy as np
    slab = np.asanyarray(dataobj[..., start:stop])
    if slab.ndim > 3:
        slab = slab.reshape(slab.shape[:3])
    whole = np.rint(slab) if slab.dtype.kind == "f" else slab
    non_integer = int(np.count_nonzero(slab != whole)) if slab.dtype.kind == "f" else 0
    if whole.size == 0:
        return whole, non_integer, 0, 0
    return whole, non_integer, _bound(whole.min()), _bound(whole.max())


def _int16_copy(img):
    """The volume's voxels as int16, or ValueError naming why the copy would lose a voxel."""
    import numpy as np
    shape = tuple(int(n) for n in img.shape[:3])
    out = np.empty(shape, np.int16)
    non_integer, low, high = 0, INT16_HIGH, INT16_LOW
    for start, stop in _slabs(shape):
        whole, bad, lo, hi = _whole_slab(img.dataobj, start, stop)
        non_integer, low, high = non_integer + bad, min(low, lo), max(high, hi)
        if lossless(bad, lo, hi):  # a slab that would lose a voxel is never cast
            out[..., start:stop] = whole.astype(np.int16)
    if not lossless(non_integer, min(low, high), max(low, high)):
        raise ValueError("%d voxels are not whole numbers, and the whole values span %d to %d; int16 holds %d to %d"
                         % (non_integer, low, high, INT16_LOW, INT16_HIGH))
    return out


def _int16_image(out, like):
    """An int16 image on the grid of another, its header carried over with dtype, slope and
    intercept set for int16 and the qform and sform kept with their codes."""
    import nibabel as nib
    import numpy as np
    header = like.header.copy()
    header.set_data_dtype(np.int16)
    header["scl_slope"], header["scl_inter"] = 1.0, 0.0
    new = nib.Nifti1Image(out, np.asarray(like.affine, float), header=header)
    new.set_qform(like.get_qform(), code=int(like.header["qform_code"]))
    new.set_sform(like.get_sform(), code=int(like.header["sform_code"]))
    return new


def _same_volume(back, out, affine) -> bool:
    """Whether a reloaded file holds the shape, affine and every voxel of the array saved."""
    import numpy as np
    if tuple(back.shape[:3]) != out.shape or not np.array_equal(np.asarray(back.affine, float), affine):
        return False
    return all(np.array_equal(np.asarray(back.dataobj[..., start:stop]), out[..., start:stop])
               for start, stop in _slabs(out.shape))


def _save_checked(out, like, path: str) -> None:
    """Save an int16 volume beside its output path, reload it, and replace the output only when
    the reloaded copy is the array saved; a failed check leaves no output file."""
    import nibabel as nib
    import numpy as np
    tmp = path + ".tmp.nii.gz"
    try:
        nib.save(_int16_image(out, like), tmp)
        same = _same_volume(nib.load(tmp), out, np.asarray(like.affine, float))
    except Exception:
        _remove(tmp)
        raise
    if not same:
        _remove(tmp)
        raise ValueError("the reloaded copy of %s differs in shape, affine or voxels" % path)
    os.replace(tmp, path)


def _remove(path: str) -> None:
    if os.path.lexists(path):
        os.remove(path)


def _values_present(dataobj, shape) -> List[int]:
    """The nonzero values a volume holds, read a slab at a time, as sorted Python ints."""
    import numpy as np
    found: set = set()
    for start, stop in _slabs(shape):
        whole = _whole_slab(dataobj, start, stop)[0]
        found.update(int(v) for v in np.unique(whole) if v != 0)
    return sorted(found)


def _file_record(path: str) -> dict:
    """bytes and sha256 of a file, read in chunks so a large mask is never held whole."""
    digest, size = hashlib.sha256(), 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
            size += len(chunk)
    return {"bytes": size, "sha256": digest.hexdigest()}


def _out_record(path: str, dtype: str, values: List[int]) -> dict:
    return {"path": path, "dtype": dtype, "values": values, **_file_record(path)}


# ---------------------------------------------------------------- the three actions

def _convert_volume(labels: str, out: str) -> dict:
    """A float or wide-integer volume written again as int16, losslessly or not at all."""
    import nibabel as nib
    img = nib.load(labels)
    copy = _int16_copy(img)
    _save_checked(copy, img, out)
    back = nib.load(out)
    return {"action": "converted", "source": {"files": {os.path.basename(labels): _file_record(labels)}},
            "out": _out_record(out, "int16", _values_present(back.dataobj, copy.shape))}


def _keep_volume(labels: str, out: str) -> dict:
    """A small-integer volume left as it is; out made a symlink to it where the paths differ."""
    import nibabel as nib
    img = nib.load(labels)
    source = os.path.abspath(labels)
    record = {"action": "kept", "source": {"files": {os.path.basename(labels): _file_record(labels)}},
              "out": {**_out_record(labels, str(img.get_data_dtype()),
                                    _values_present(img.dataobj, tuple(int(n) for n in img.shape[:3]))),
                      "copy": "none: the source is kept as it is"}}
    if os.path.abspath(out) != source:
        _remove(out)
        os.symlink(source, out)
        record["out"]["symlink"] = out
    return record


def _level_files(folder: str) -> List[Tuple[str, str]]:
    """(level, file name) of the folder's vertebra and sacrum masks, in the column's order, so a
    voxel two masks claim goes to the first; vertebrae_S1 and sacrum both name the sacrum."""
    names = sorted(n for n in os.listdir(folder) if n.endswith((".nii.gz", ".nii")))
    stems = {n: schemes.TOTALSEG_FILES.get(n.split(".")[0]) for n in names}
    return [(level, name) for level in ORDER for name in names if stems[name] == level]


def _stack_mask(stacked, img, value: int, first) -> int:
    """Write a binary mask's voxels into the stacked volume where nothing claimed them yet, and
    count the voxels something already did; ValueError for a mask on another grid."""
    import numpy as np
    if tuple(img.shape[:3]) != stacked.shape or not np.allclose(img.affine, first.affine, atol=1e-3):
        raise ValueError("a mask lies on another grid than the first (%s against %s)" % (img.shape, stacked.shape))
    overlap = 0
    for start, stop in _slabs(stacked.shape):
        on = _whole_slab(img.dataobj, start, stop)[0] != 0
        slab = stacked[..., start:stop]
        overlap += int(np.count_nonzero(on & (slab != 0)))
        slab[on & (slab == 0)] = value
    return overlap


def _stack_folder(labels: str, out: str) -> dict:
    """A TotalSegmentator subject's masks stacked into one int16 volume in VerSe's ids."""
    import nibabel as nib
    import numpy as np
    folder = mask_folder(labels)
    pairs = _level_files(folder)
    if not pairs:
        raise ValueError("no vertebrae_*.nii.gz or sacrum file under %s" % folder)
    files, levels, overlap, stacked, first = {}, {}, 0, None, None
    for level, name in pairs:
        img = nib.load(os.path.join(folder, name))
        if stacked is None:
            first = img
            stacked = np.zeros(tuple(int(n) for n in img.shape[:3]), np.int16)
        levels[level] = verse_value(level)
        overlap += _stack_mask(stacked, img, levels[level], first)
        files[name] = _file_record(os.path.join(folder, name))
    _save_checked(stacked, first, out)
    return {"action": "stacked", "source": {"files": files}, "overlap_voxels": overlap, "levels": levels,
            "out": _out_record(out, "int16", _values_present(nib.load(out).dataobj, stacked.shape))}


# ---------------------------------------------------------------- the edge and the command

def _volume_action(labels: str, scheme: str) -> str:
    """The action for a label volume, from its stored dtype; a folder's scheme is totalseg alone,
    and a totalseg volume needs the label map facts takes, which this converter does not."""
    import nibabel as nib
    if scheme == "totalseg":
        raise ValueError("%s is a file; the scheme totalseg reads a folder of one mask per structure" % labels)
    dtype = nib.load(labels).get_data_dtype()
    return action_for(dtype.kind, int(dtype.itemsize), False)


def convert(labels: str, scheme: str, out: str, manifest: Optional[str] = None) -> dict:
    """The edge: a volume converted or kept, or a folder stacked, with the manifest record
    returned and written as JSON where a manifest path is given. ValueError names a failure, and
    a failure leaves no output file."""
    if os.path.isdir(labels):
        if scheme != "totalseg":
            raise ValueError("%s is a folder; only the scheme totalseg stacks one mask per structure" % labels)
        record = _stack_folder(labels, out)
    else:
        action = _volume_action(labels, scheme)
        record = _keep_volume(labels, out) if action == "kept" else _convert_volume(labels, out)
        record["problems"] = schemes.problems(scheme, {v: 1 for v in record["out"]["values"]})
    record["scheme"] = scheme
    if manifest is not None:
        with open(manifest, "w", encoding="ascii", newline="\n") as f:
            json.dump(record, f, sort_keys=True, indent=1)
            f.write("\n")
    return record


def command(sub) -> None:
    """The int16 subcommand on a subparsers object, as __main__.py wires it."""
    p = sub.add_parser("int16", help="write a label volume as int16, losslessly or not at all; keep one already "
                                     "in a small integer type; stack a TotalSegmentator folder into one volume")
    p.add_argument("--labels", required=True, help="a .nii.gz label volume, or a TotalSegmentator subject's folder")
    p.add_argument("--scheme", default="verse", help="the volume's label scheme (default verse); totalseg for a folder")
    p.add_argument("--out", required=True, help="the int16 .nii.gz to write (a symlink to a kept source)")
    p.add_argument("--manifest", default=None, help="where to write the JSON record of what was done")
    p.set_defaults(run=run)


def run(args) -> int:
    """Convert as the arguments say and print one line, the action and the output path."""
    import sys
    try:
        record = convert(args.labels, args.scheme, args.out, args.manifest)
    except ValueError as error:
        print("failed %s: %s" % (args.out, error), file=sys.stderr)
        return 1
    print("%s %s" % (record["action"], args.out))
    return 0
