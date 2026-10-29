"""Each study's masks read once into one row of facts in level names, whatever dataset the masks
came from: the files with their bytes and sha256, the grid, the field's head and foot edges, and
for every level the scheme names its voxels, extent, centroid, pieces and the faces of the volume
it reaches; the raw values the scheme does not name are counted, never dropped silently.

    python -m screening facts --masks DIR --scheme SCHEME --out facts.jsonl [--member NAME]
        [--persons MAP.json] [--label-map MAP.json] [--workers N] [--ids FILE]

DIR holds one study per entry: a .nii.gz (or .nii) label volume named <id>.nii.gz, read under
the scheme's id table (scanimport/schemes.py: verse, spineps, ctspinopelvic, moose, enhance), or,
for the scheme totalseg, a folder <id>/ of one binary mask per structure as TotalSegmentator's
release ships them (vertebrae_C1 ... vertebrae_L5, vertebrae_S1 or sacrum, with skull, hip_left,
hip_right and spinal_cord read as context, which the field rule needs on a padded grid). A
multilabel volume of any other scheme is read with its own class map given as JSON (--label-map,
value to TotalSegmentator's structure name or a level name).

Each row, keys sorted, mm to 0.1, the grid to 6 decimals, shares to 4:

    id, member, person, scheme, files {name: {bytes, sha256}};
    grid {shape, zooms, affine, axcodes, head_foot_axis, dtype};
    field_mm {top, bottom}: the head-most and foot-most world positions the volume covers on
        RAS's superior axis, at the outer faces of its first and last voxels;
    levels {name: {voxels, faces, top_mm, bottom_mm, centroid_mm, components, largest_share}}
        for C1 to C7, T1 to T13, L1 to L6 and the sacrum, each with a voxel: faces are the
        volume's faces its voxels reach, top and bottom the head-most and foot-most voxel centres
        on the superior axis, the centroid in RAS mm, pieces 26-connected;
    context {name: {voxels, faces, top_mm, bottom_mm}} for the structures beside the column a
        folder of masks gives (skull, hips, spinal cord);
    other_values {value: voxels}: the raw values the scheme names no level for (ENHANCE.PET's
        hips, a coccyx, a scheme's ribs), so a volume read under the wrong scheme shows it;
    problems: what scanimport's scheme check says about the values present, in words;
    distances_mm {"Lk-sacrum": mm}: the shortest distance between the voxel centres of each
        lumbar level and the sacrum, where both have a voxel.

This is the facts schema of holdings/fullspine_facts.py (VerSe, TotalSegmentator) with the scheme
made a parameter, so a row here and a row there read the same; the ribs' reach stays in holdings
as the record of that arm. A row of SchwingNet's ENHANCE.PET facts (holdings/enhance_facts.py,
by raw label) is read into the same study form by whole.study_from_enhance_facts.

The decisions are pure functions with contracts (field_edges, faces_touched, cut_flags); numpy,
nibabel, scipy and the files stay in the private functions and in read_study, the edge.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
from typing import Dict, List, Optional, Sequence, Tuple

from . import LUMBAR, ORDER
from .contracts import beartype, ensure, require

MM_DECIMALS, GRID_DECIMALS, SHARE_DECIMALS = 1, 6, 4

# the six faces of a volume, named by the way each looks in RAS; a label at the first voxel of an
# axis whose code is S reaches the I face, since the code names the direction of increasing index
OPPOSITE = {"L": "R", "R": "L", "A": "P", "P": "A", "S": "I", "I": "S"}
AXIS_OF = {"L": 0, "R": 0, "A": 1, "P": 1, "S": 2, "I": 2}
SIDE_FACES = frozenset("LRAP")

# TotalSegmentator's files, as the release ships them; vertebrae_S1 and sacrum both name the sacrum
TOTALSEG_CONTEXT = {"skull": "skull", "hip_left": "hip_left", "hip_right": "hip_right", "spinal_cord": "spinal_cord"}
# the default workers: two, since the container's CPUs and memory are shared with other work
WORKERS = 2
# a mask is read a slab of about 16 million voxels at a time, 128 MB as float64
SLAB_VOXELS = 1 << 24


# ---------------------------------------------------------------- pure decisions

@beartype
@require(lambda shape: len(shape) == 3 and all(n >= 1 for n in shape), "a grid has three axes of at least one voxel")
@require(lambda row: len(row) == 4 and all(math.isfinite(x) for x in row), "the affine's superior row has four finite numbers")
@ensure(lambda result: result[0] >= result[1], "the head edge lies at or above the foot edge")
def field_edges(shape: Sequence[int], row: Sequence[float]) -> Tuple[float, float]:
    """The head-most and foot-most superior positions of the volume's outer voxel faces, from the
    affine's superior row over the eight corners at half a voxel outside the first and last indices."""
    heights = [row[0] * i + row[1] * j + row[2] * k + row[3]
               for i in (-0.5, shape[0] - 0.5) for j in (-0.5, shape[1] - 0.5) for k in (-0.5, shape[2] - 0.5)]
    return max(heights), min(heights)


@beartype
@require(lambda axcodes: len(axcodes) == 3 and all(c in AXIS_OF for c in axcodes)
         and len({AXIS_OF[c] for c in axcodes}) == 3, "three RAS letters naming three different axes")
@require(lambda shape: len(shape) == 3 and all(n >= 1 for n in shape), "a grid has three axes of at least one voxel")
@require(lambda low, high, shape: len(low) == 3 and len(high) == 3
         and all(0 <= a <= b <= n - 1 for a, b, n in zip(low, high, shape)), "a bounding box inside the grid")
@ensure(lambda result: result == sorted(result) and len(set(result)) == len(result), "faces sorted, each once")
def faces_touched(low: Sequence[int], high: Sequence[int], shape: Sequence[int], axcodes: str) -> List[str]:
    """The faces of the volume a label's bounding box reaches, each named by the way it looks in
    RAS (S the head face, I the foot face, L, R, A, P the sides), so a level cut by the field, at
    its ends or in plane, says so."""
    out = []
    for axis, code in enumerate(axcodes):
        if low[axis] == 0:
            out.append(OPPOSITE[code])
        if high[axis] == shape[axis] - 1:
            out.append(code)
    return sorted(out)


@beartype
@require(lambda faces: all(f in OPPOSITE for f in faces), "faces are RAS letters")
def cut_flags(faces: Sequence[str]) -> Tuple[bool, bool, bool]:
    """(head_cut, foot_cut, side_cut): whether the faces reach the head face, the foot face, a side."""
    held = set(faces)
    return "S" in held, "I" in held, bool(held & SIDE_FACES)


@beartype
@require(lambda value, decimals: math.isfinite(value) and 0 <= decimals <= 12, "a finite value to a few decimals")
def rounded(value: float, decimals: int) -> float:
    """round, with -0.0 made 0.0 so a row reads the same whichever way the number came out."""
    return round(value, decimals) + 0.0


# ---------------------------------------------------------------- numpy, at the edge

def _rounded_list(values, decimals: int) -> list:
    return [rounded(float(v), decimals) for v in values]


def _world_points(points, affine):
    """RAS mm of voxel centres given as an (n, 3) array of indices."""
    import numpy as np
    affine = np.asarray(affine, float)
    return points @ affine[:3, :3].T + affine[:3, 3]


def _pieces(points) -> Tuple[int, float]:
    """The 26-connected pieces of a set of voxels, and the share the largest holds."""
    import numpy as np
    from scipy import ndimage
    low = points.min(0)
    box = np.zeros(tuple(points.max(0) - low + 1), bool)
    box[tuple((points - low).T)] = True
    labelled, n = ndimage.label(box, structure=np.ones((3, 3, 3), bool))
    if n == 0:
        return 0, 0.0
    sizes = np.bincount(labelled[box])[1:]
    return int(n), float(sizes.max()) / float(len(points))


def _boundary(points):
    """The voxels of a set with a face neighbour outside it; the nearest voxel of the set to any
    point outside lies among them, so distances are sought there alone."""
    import numpy as np
    from scipy import ndimage
    low = points.min(0) - 1
    box = np.zeros(tuple(points.max(0) - low + 2), bool)
    box[tuple((points - low).T)] = True
    edge = box & ~ndimage.binary_erosion(box, structure=ndimage.generate_binary_structure(3, 1))
    return np.argwhere(edge) + low


def _shortest_mm(first, second, affine) -> float:
    from scipy.spatial import cKDTree
    a = _world_points(_boundary(first), affine)
    b = _world_points(_boundary(second), affine)
    distances, _ = cKDTree(b).query(a, k=1)
    return float(distances.min())


def _label_facts(points, affine, shape, axcodes: str) -> dict:
    world = _world_points(points, affine)
    n, piece_share = _pieces(points)
    low = [int(v) for v in points.min(0)]
    high = [int(v) for v in points.max(0)]
    return {"voxels": int(len(points)), "faces": faces_touched(low, high, [int(s) for s in shape], axcodes),
            "top_mm": rounded(float(world[:, 2].max()), MM_DECIMALS),
            "bottom_mm": rounded(float(world[:, 2].min()), MM_DECIMALS),
            "centroid_mm": _rounded_list(world.mean(0), MM_DECIMALS),
            "components": n, "largest_share": rounded(piece_share, SHARE_DECIMALS)}


def _extent_facts(points, affine, shape, axcodes: str) -> dict:
    world = _world_points(points, affine)
    low = [int(v) for v in points.min(0)]
    high = [int(v) for v in points.max(0)]
    return {"voxels": int(len(points)), "faces": faces_touched(low, high, [int(s) for s in shape], axcodes),
            "top_mm": rounded(float(world[:, 2].max()), MM_DECIMALS),
            "bottom_mm": rounded(float(world[:, 2].min()), MM_DECIMALS)}


def _head_foot_axis(affine) -> int:
    """The voxel axis that runs most along RAS's superior axis."""
    import numpy as np
    return int(np.argmax(np.abs(np.asarray(affine, float)[2, :3])))


def _grid_facts(img) -> dict:
    import nibabel as nib
    import numpy as np
    shape = [int(n) for n in img.shape[:3]]
    return {"shape": shape, "zooms": _rounded_list(img.header.get_zooms()[:3], GRID_DECIMALS),
            "affine": [_rounded_list(row, GRID_DECIMALS) for row in np.asarray(img.affine, float)],
            "axcodes": "".join(nib.aff2axcodes(img.affine)), "head_foot_axis": _head_foot_axis(img.affine),
            "dtype": str(img.get_data_dtype())}


def _field_facts(img) -> dict:
    import numpy as np
    row = [float(v) for v in np.asarray(img.affine, float)[2]]
    top, bottom = field_edges([int(n) for n in img.shape[:3]], row)
    return {"top": rounded(top, MM_DECIMALS), "bottom": rounded(bottom, MM_DECIMALS)}


def _file_record(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _image_of(data: bytes):
    """A NIfTI image from the bytes of a .nii.gz or .nii file, read in memory."""
    import nibabel as nib
    raw = gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data
    return nib.Nifti1Image.from_bytes(raw)


def _memory_order(dataobj) -> str:
    order = getattr(dataobj, "order", None)
    if order in ("F", "C"):
        return order
    return "F" if dataobj.flags.f_contiguous and not dataobj.flags.c_contiguous else "C"


def _slabs(shape, order: str):
    """(axis, start, stop) of the slabs a volume is read in, along its slowest axis in memory."""
    import numpy as np
    axis = 2 if order == "F" else 0
    plane = max(1, int(np.prod(shape)) // max(1, shape[axis]))
    step = max(1, SLAB_VOXELS // plane)
    for start in range(0, shape[axis], step):
        yield axis, start, min(start + step, shape[axis])


def _slab_points(dataobj, order: str, axis: int, start: int, stop: int):
    import numpy as np
    index = [slice(None)] * 3
    index[axis] = slice(start, stop)
    slab = np.asanyarray(dataobj[tuple(index)])
    if slab.ndim > 3:
        slab = slab.reshape(slab.shape[:3])
    if slab.dtype.kind == "f":
        slab = np.rint(slab).astype(np.int32)
    flat = slab.ravel(order=order)
    where = np.flatnonzero(flat)
    points = np.stack(np.unravel_index(where, slab.shape, order=order), axis=1).astype(np.int32)
    points[:, axis] += start
    return flat[where], points


def _voxel_points(img) -> dict:
    """The voxel indices of each value in a mask, {value: (n, 3) array}, walked in the volume's
    memory order a slab at a time: a float64 mask of 512 x 512 x 2023 read whole took 12 GB."""
    import numpy as np
    shape = tuple(int(n) for n in img.shape[:3])
    order = _memory_order(img.dataobj)
    parts: dict = {}
    for axis, start, stop in _slabs(shape, order):
        values, points = _slab_points(img.dataobj, order, axis, start, stop)
        for value in np.unique(values):
            parts.setdefault(int(value), []).append(points[values == value])
    return {value: np.concatenate(chunks) for value, chunks in sorted(parts.items())}


def _same_grid(first, second) -> bool:
    import numpy as np
    return first.shape[:3] == second.shape[:3] and np.allclose(first.affine, second.affine, atol=1e-3)


# ---------------------------------------------------------------- a study's row

def _lumbosacral(levels: dict, affine) -> dict:
    if "sacrum" not in levels:
        return {}
    return {"%s-sacrum" % name: rounded(_shortest_mm(levels[name], levels["sacrum"], affine), MM_DECIMALS)
            for name in LUMBAR if name in levels}


def _study_row(sid: str, member: str, person: Optional[str], scheme: str, files: dict, grid_img,
               levels: dict, context: dict, other: dict, problems: list) -> dict:
    affine, shape = grid_img.affine, grid_img.shape[:3]
    axcodes = _grid_facts(grid_img)["axcodes"]
    return {"id": sid, "member": member, "person": person, "scheme": scheme,
            "files": {name: _file_record(data) for name, data in sorted(files.items())},
            "grid": _grid_facts(grid_img), "field_mm": _field_facts(grid_img),
            "levels": {name: _label_facts(levels[name], affine, shape, axcodes) for name in ORDER if name in levels},
            "context": {name: _extent_facts(points, affine, shape, axcodes) for name, points in sorted(context.items())},
            "other_values": {str(value): int(len(points)) for value, points in sorted(other.items())},
            "problems": problems, "distances_mm": _lumbosacral(levels, affine)}


def mask_folder(folder: str) -> str:
    """The folder that holds a subject's structure masks: the subject's folder itself, or its
    segmentations/ as TotalSegmentator's release lays each subject out (s0001/ct.nii.gz beside
    s0001/segmentations/vertebrae_C1.nii.gz)."""
    inner = os.path.join(folder, "segmentations")
    return inner if os.path.isdir(inner) else folder


def _read_folder(sid: str, folder: str, member: str, person: Optional[str]) -> dict:
    """A TotalSegmentator folder: one binary mask per structure, the levels by file name."""
    from scanimport import schemes
    files, levels, context, grid_img = {}, {}, {}, None
    folder = mask_folder(folder)
    for fname in sorted(os.listdir(folder)):
        if not fname.endswith((".nii.gz", ".nii")):
            continue
        stem = fname.split(".")[0]
        level, where = schemes.TOTALSEG_FILES.get(stem), TOTALSEG_CONTEXT.get(stem)
        if level is None and where is None:
            continue
        data = open(os.path.join(folder, fname), "rb").read()
        files[fname] = data
        img = _image_of(data)
        if grid_img is None:
            grid_img = img
        elif not _same_grid(grid_img, img):
            raise ValueError("%s: %s lies on another grid" % (sid, fname))
        found = _voxel_points(img).get(1)
        if found is None or not len(found):
            continue
        if level is not None:
            import numpy as np
            levels[level] = np.concatenate([levels[level], found]) if level in levels else found
        else:
            context[where] = found
    if grid_img is None:
        raise ValueError("%s: no vertebrae_*.nii.gz or sacrum file under %s" % (sid, folder))
    return _study_row(sid, member, person, "totalseg", files, grid_img, levels, context, {}, [])


def _read_volume(sid: str, path: str, scheme: str, member: str, person: Optional[str],
                 label_map: Optional[Dict[int, str]]) -> dict:
    from scanimport import schemes
    data = open(path, "rb").read()
    img = _image_of(data)
    found = _voxel_points(img)
    present = {value: int(len(points)) for value, points in found.items()}
    problems = [] if label_map is not None else schemes.problems(scheme, present)
    levels, other = {}, {}
    for value, points in found.items():
        name = schemes.level_of(scheme, value, label_map)
        if name is None:
            other[value] = points
        elif name in levels:
            import numpy as np
            levels[name] = np.concatenate([levels[name], points])
        else:
            levels[name] = points
    return _study_row(sid, member, person, scheme, {os.path.basename(path): data}, img, levels, {}, other, problems)


def read_study(sid: str, path: str, scheme: str, member: str = "", person: Optional[str] = None,
               label_map: Optional[Dict[int, str]] = None) -> dict:
    """One study's row from a label volume, or from a folder of one mask per structure (totalseg).
    The edge: everything the row holds is computed here from the file's bytes, read once."""
    if os.path.isdir(path):
        if scheme != "totalseg":
            raise ValueError("%s is a folder; only the scheme totalseg reads one mask per structure" % path)
        return _read_folder(sid, path, member, person)
    return _read_volume(sid, path, scheme, member, person, label_map)


# ---------------------------------------------------------------- the run

def studies_in(masks: str, scheme: str) -> List[Tuple[str, str]]:
    """(id, path) of every study under a masks folder: folders for totalseg, label volumes else."""
    out = []
    for name in sorted(os.listdir(masks)):
        path = os.path.join(masks, name)
        if scheme == "totalseg" and os.path.isdir(path):
            out.append((name, path))
        elif name.endswith(".nii.gz"):
            out.append((name[:-len(".nii.gz")], path))
        elif name.endswith(".nii"):
            out.append((name[:-len(".nii")], path))
    return out


def row_line(row: dict) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"


def rows_written(part: str) -> list:
    """The rows a run cut short wrote whole to OUT.part, a line each; a line cut off is read again."""
    if not os.path.exists(part):
        return []
    with open(part, encoding="ascii") as f:
        return [json.loads(line) for line in f if line.endswith("\n")]


def _safe_row(job) -> dict:
    sid, path, scheme, member, person, label_map = job
    try:
        return read_study(sid, path, scheme, member, person, label_map)
    except Exception as error:  # a study that cannot be read is a row that says so
        return {"id": sid, "member": member, "error": "%s: %s" % (type(error).__name__, error)}


def run(jobs: list, out: str, workers: int) -> int:
    """Each study's row, written to OUT.part as it comes and sorted into OUT at the end, so a run cut
    short loses no row and a second run reads only the studies the first did not write."""
    from concurrent.futures import ProcessPoolExecutor, as_completed
    part = out + ".part"
    rows = rows_written(part)
    done = {row["id"] for row in rows}
    todo = [job for job in jobs if job[0] not in done]
    with open(part, "w", encoding="ascii", newline="\n") as f:
        f.writelines(row_line(row) for row in rows)
        with ProcessPoolExecutor(workers) as pool:
            futures = [pool.submit(_safe_row, job) for job in todo]
            for future in as_completed(futures):
                row = future.result()
                f.write(row_line(row))
                f.flush()
                rows.append(row)
    rows.sort(key=lambda row: row["id"])
    with open(out + ".tmp", "w", encoding="ascii", newline="\n") as f:
        f.writelines(row_line(row) for row in rows)
    os.replace(out + ".tmp", out)
    os.remove(part)
    return len(rows)
