"""Per-study facts of VerSe's and TotalSegmentator's published spine masks, one JSON line per study.

Confidential, like the rest of this repository: nothing here, and nothing it writes, goes to a
public place, and no mask or CT is ever copied into the repository.

The owner's rule of 2026-10-28 23:00 UTC for the gold tier CT dataset in SchwingNet: a CT is
admitted when the whole spine, C2 to the sacrum, is in view in its volume, whatever its masks hold;
a mask or two missing is completed with a segmenter, never a reason to leave the spine out. Which
of VerSe's 374 series and TotalSegmentator's 1,939 subjects show the whole spine is a question of
the field each volume covers, so this module reads every published mask once and writes what the
field test needs as plain facts: the field's head and foot edges, and each level's voxels, extent,
centroid and pieces, in level names rather than a release's label numbers, so one reader in
SchwingNet's standard library takes both members. A mask lies on its CT's grid, so the field read
from the mask's header is the CT's field; no CT is read.

    python -m holdings.fullspine_facts totalsegmentator SPANS OUT.jsonl [--workers N]
    python -m holdings.fullspine_facts verse MASKDIR OUT.jsonl [--workers N]

Each row is written to OUT.part as it comes; a run cut short is started again with the same command
and reads only the studies it has not written.

SPANS is a folder of byte ranges of TotalSegmentator's release zip, one file <subject>.span per
subject, with index.json beside them giving each span's first byte and the zip entries inside it
(the central directory's name, method, sizes and offset). MASKDIR holds VerSe's release masks as
published on OSF, one folder a release, verse19/ and verse20/, in MICCAI's spellings or BIDS's
(verse_series). A series in both releases is read from verse20, the copy VerSeFusion's unify stage
chooses, and the row says what the verse19 copy holds beside it (other_release).

Each row, keys sorted, mm to 0.1, the grid to 6 decimals, shares to 4:

    id, member, files {name: {bytes, sha256}} (the .nii.gz files read, as published);
    grid {shape, zooms, affine, axcodes, head_foot_axis, dtype};
    field_mm {top, bottom}: the head-most and foot-most world positions the volume covers, on the
        head-foot axis (RAS's superior axis), at the outer faces of its first and last voxels;
    levels {name: {voxels, faces, top_mm, bottom_mm, centroid_mm, components, largest_share}} for
        C1 to C7, T1 to T12, T13, L1 to L6 and the sacrum, each with a voxel: faces are the volume's
        faces its voxels reach (faces_touched), top and bottom the head-most and foot-most voxel
        centres on the head-foot axis, the centroid in RAS mm, pieces 26-connected;
    context {name: {voxels, faces, top_mm, bottom_mm}} for TotalSegmentator's skull, hips and spinal cord,
        which the field test reads beside the column;
    ribs {side_k: {voxels, reach_mm {level: mm}, lead, lead_margin_mm, tie}} for TotalSegmentator's
        ribs: the shortest distance from the rib to each level within RIB_REACH_MM, the nearest
        level its lead and how much nearer it is than the next its margin (RIB_REACH_MM says why
        a distance and not ENHANCE.PET's 3 mm contact tally);
    distances_mm {"a-b": mm}: the shortest distance between voxel centres of each lumbar level and
        the sacrum, where both have a voxel;
    for VerSe, release, patient_in_name (the patient a multi-series file names, else null) and,
        where the series is in both releases, other_release {release, file, same_grid, same_levels,
        voxels_differ}.

The rows are facts, never calls: what the field test makes of them is SchwingNet's
tools/gold3_field.py and what the column calls make of them its tools/gold3_ct.py, so the
thresholds live in one place.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import struct
import sys
import zlib
from concurrent.futures import ProcessPoolExecutor, as_completed

import nibabel as nib
import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

from holdings.count_enhance_pet import head_foot_axis

MM_DECIMALS, GRID_DECIMALS, SHARE_DECIMALS = 1, 6, 4
PIECES = np.ones((3, 3, 3), bool)
FACES = ndimage.generate_binary_structure(3, 1)

COLUMN_NAMES = (*[f"C{i}" for i in range(1, 8)], *[f"T{i}" for i in range(1, 14)],
                *[f"L{i}" for i in range(1, 7)], "sacrum")
LUMBAR_NAMES = tuple(f"L{i}" for i in range(1, 7))

# VerSe's scheme (github.com/anjany/verse): C1-C7 1-7, T1-T12 8-19, L1-L6 20-25, the sacrum 26
# and the coccyx 27 in the scheme but drawn in no scan, T13 28.
VERSE_NAMES = {**{i: f"C{i}" for i in range(1, 8)}, **{7 + i: f"T{i}" for i in range(1, 13)},
               **{19 + i: f"L{i}" for i in range(1, 7)}, 26: "sacrum", 28: "T13"}

# TotalSegmentator v3's files: one binary mask per structure, named by level.
TS_LEVEL_FILES = {f"vertebrae_{name}.nii.gz": name for name in COLUMN_NAMES if name not in ("sacrum",)}
TS_LEVEL_FILES["sacrum.nii.gz"] = "sacrum"
TS_CONTEXT_FILES = {"skull.nii.gz": "skull", "hip_left.nii.gz": "hip_left", "hip_right.nii.gz": "hip_right",
                    "spinal_cord.nii.gz": "spinal_cord"}
TS_RIB_FILE = re.compile(r"^rib_(left|right)_(\d+)\.nii\.gz$")

# Two processes unless told otherwise: the container's CPUs and memory are shared with other work.
WORKERS = 2
# A mask is read a slab of about 16 million voxels at a time (voxel_points), 128 MB as float64.
SLAB_VOXELS = 1 << 24


# ---------------------------------------------------------------- numbers

def rounded(value, decimals: int) -> float:
    return round(float(value), decimals) + 0.0


def rounded_list(values, decimals: int) -> list:
    return [rounded(v, decimals) for v in values]


# ---------------------------------------------------------------- one volume's grid and field

def superior_of(affine) -> np.ndarray:
    """The row of the affine that gives a voxel's position on the head-foot axis, superior positive
    in RAS, for voxel indices (i, j, k, 1)."""
    return np.asarray(affine, float)[2]


def field_edges(shape, affine) -> tuple:
    """The head-most and foot-most superior positions of the volume's outer voxel faces."""
    row = superior_of(affine)
    corners = np.array([[i, j, k, 1.0] for i in (-0.5, shape[0] - 0.5) for j in (-0.5, shape[1] - 0.5)
                        for k in (-0.5, shape[2] - 0.5)])
    heights = corners @ row
    return float(heights.max()), float(heights.min())


def grid_facts(img) -> dict:
    shape = [int(n) for n in img.shape[:3]]
    return {"shape": shape,
            "zooms": rounded_list(img.header.get_zooms()[:3], GRID_DECIMALS),
            "affine": [rounded_list(row, GRID_DECIMALS) for row in np.asarray(img.affine, float)],
            "axcodes": "".join(nib.aff2axcodes(img.affine)),
            "head_foot_axis": head_foot_axis(img.affine),
            "dtype": str(img.get_data_dtype())}


def field_facts(img) -> dict:
    top, bottom = field_edges(img.shape[:3], img.affine)
    return {"top": rounded(top, MM_DECIMALS), "bottom": rounded(bottom, MM_DECIMALS)}


# ---------------------------------------------------------------- one label's facts

def world_points(points: np.ndarray, affine) -> np.ndarray:
    """RAS mm of voxel centres given as an (n, 3) array of indices."""
    affine = np.asarray(affine, float)
    return points @ affine[:3, :3].T + affine[:3, 3]


def pieces(points: np.ndarray) -> tuple:
    """The 26-connected pieces of a set of voxels, and the share the largest holds."""
    low = points.min(0)
    box = np.zeros(tuple(points.max(0) - low + 1), bool)
    box[tuple((points - low).T)] = True
    labelled, n = ndimage.label(box, structure=PIECES)
    if n == 0:
        return 0, 0.0
    sizes = np.bincount(labelled[box])[1:]
    return int(n), float(sizes.max()) / float(len(points))


OPPOSITE = {"L": "R", "R": "L", "A": "P", "P": "A", "S": "I", "I": "S"}


def faces_touched(points: np.ndarray, shape, affine) -> list:
    """The faces of the volume a label's voxels reach, each named by the way it looks in RAS (S the
    head face, I the foot face, L, R, A, P the sides), so a level cut by the field, at its ends or
    in plane, says so."""
    codes = nib.aff2axcodes(affine)
    out = []
    for axis, code in enumerate(codes):
        if points[:, axis].min() == 0:
            out.append(OPPOSITE[code])
        if points[:, axis].max() == shape[axis] - 1:
            out.append(code)
    return sorted(out)


def label_facts(points: np.ndarray, affine, shape) -> dict:
    world = world_points(points, affine)
    n, share = pieces(points)
    return {"voxels": int(len(points)), "faces": faces_touched(points, shape, affine),
            "top_mm": rounded(world[:, 2].max(), MM_DECIMALS),
            "bottom_mm": rounded(world[:, 2].min(), MM_DECIMALS),
            "centroid_mm": rounded_list(world.mean(0), MM_DECIMALS),
            "components": n,
            "largest_share": rounded(share, SHARE_DECIMALS)}


def extent_facts(points: np.ndarray, affine, shape) -> dict:
    world = world_points(points, affine)
    return {"voxels": int(len(points)), "faces": faces_touched(points, shape, affine),
            "top_mm": rounded(world[:, 2].max(), MM_DECIMALS),
            "bottom_mm": rounded(world[:, 2].min(), MM_DECIMALS)}


def boundary(points: np.ndarray) -> np.ndarray:
    """The voxels of a set with a face neighbour outside it; the nearest voxel of the set to any
    point outside lies among them, so distances are sought there alone."""
    low = points.min(0) - 1
    box = np.zeros(tuple(points.max(0) - low + 2), bool)
    box[tuple((points - low).T)] = True
    edge = box & ~ndimage.binary_erosion(box, structure=FACES)
    return np.argwhere(edge) + low


def shortest_mm(first: np.ndarray, second: np.ndarray, affine) -> float:
    a = world_points(boundary(first), affine)
    b = world_points(boundary(second), affine)
    distances, _ = cKDTree(b).query(a, k=1)
    return float(distances.min())


def lumbosacral_distances(levels: dict, affine) -> dict:
    """The shortest distance from each lumbar level to the sacrum, where both are drawn."""
    if "sacrum" not in levels:
        return {}
    return {f"{name}-sacrum": rounded(shortest_mm(levels[name], levels["sacrum"], affine), MM_DECIMALS)
            for name in LUMBAR_NAMES if name in levels}


# ---------------------------------------------------------------- ribs

# TotalSegmentator's masks leave the costovertebral joint unlabelled: on six thoracic subjects of
# v3 a rib lay 1.5 to 16 mm from its own vertebra, with the next level 5 mm or more further, so the
# 3 mm contact tally of ENHANCE.PET's masks finds nothing here. A rib is read instead by the
# shortest distance to each level within RIB_REACH_MM, the nearest being its lead.
RIB_REACH_MM = 25.0


def level_trees(levels: dict, affine) -> dict:
    return {name: cKDTree(world_points(boundary(points), affine)) for name, points in levels.items()}


def rib_reach(rib: np.ndarray, trees: dict, affine) -> dict:
    """The shortest distance from a rib to each level within RIB_REACH_MM."""
    edge = world_points(boundary(rib), affine)
    out = {}
    for name, tree in trees.items():
        distances, _ = tree.query(edge, k=1, distance_upper_bound=RIB_REACH_MM)
        nearest = distances[np.isfinite(distances)]
        if len(nearest):
            out[name] = rounded(nearest.min(), MM_DECIMALS)
    return out


def lead_of(reach: dict) -> tuple:
    """The nearest level and how much nearer it is than the next; a tie goes to the head-most."""
    if not reach:
        return None, None, False
    order = sorted(reach, key=lambda name: (reach[name], COLUMN_NAMES.index(name)))
    lead = order[0]
    margin = rounded(reach[order[1]] - reach[lead], MM_DECIMALS) if len(order) > 1 else None
    return lead, margin, margin == 0.0


def rib_facts(ribs: dict, levels: dict, affine) -> dict:
    trees = level_trees(levels, affine)
    out = {}
    for name, points in sorted(ribs.items()):
        reach = rib_reach(points, trees, affine)
        lead, margin, tie = lead_of(reach)
        out[name] = {"voxels": int(len(points)),
                     "reach_mm": {k: reach[k] for k in sorted(reach, key=COLUMN_NAMES.index)},
                     "lead": lead, "lead_margin_mm": margin, "tie": tie}
    return out


# ---------------------------------------------------------------- a study's row

def file_record(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def image_of(data: bytes):
    """A NIfTI image from the bytes of a .nii.gz file, read in memory."""
    raw = gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data
    return nib.Nifti1Image.from_bytes(raw)


def memory_order(dataobj) -> str:
    """The order a mask's voxels lie in: a NIfTI file's proxy says (Fortran's), an array its flags."""
    order = getattr(dataobj, "order", None)
    if order in ("F", "C"):
        return order
    return "F" if dataobj.flags.f_contiguous and not dataobj.flags.c_contiguous else "C"


def slabs(shape, order: str):
    """(axis, start, stop) of the slabs a volume is read in, along its slowest axis in memory, each of
    at most SLAB_VOXELS voxels or one plane."""
    axis = 2 if order == "F" else 0
    plane = max(1, int(np.prod(shape)) // max(1, shape[axis]))
    step = max(1, SLAB_VOXELS // plane)
    for start in range(0, shape[axis], step):
        yield axis, start, min(start + step, shape[axis])


def slab_points(dataobj, order: str, axis: int, start: int, stop: int):
    """(values, indices) of one slab's labelled voxels, its indices in the whole volume."""
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


def voxel_points(img, labels=None) -> dict:
    """The voxel indices of each label in a mask: {label: (n, 3) array}; a binary mask is label 1.
    The volume is walked in its memory order (a NIfTI's is Fortran's), which is several times faster
    than numpy's nonzero over a Fortran-ordered volume, a slab at a time along its slowest axis: 462
    of VerSe's 473 masks are stored as float64, and the largest, 512 x 512 x 2023, read whole took
    12 GB and was killed. The points come out in the same order as a whole read, so the facts are the
    same to the bit."""
    shape = tuple(int(n) for n in img.shape[:3])
    order = memory_order(img.dataobj)
    parts = {}
    for axis, start, stop in slabs(shape, order):
        values, points = slab_points(img.dataobj, order, axis, start, stop)
        for label in np.unique(values):
            if labels is None or int(label) in labels:
                parts.setdefault(int(label), []).append(points[values == label])
    return {label: np.concatenate(chunks) for label, chunks in sorted(parts.items())}


def study_row(member: str, sid: str, files: dict, grid_img, levels: dict, context: dict, ribs: dict) -> dict:
    affine, shape = grid_img.affine, grid_img.shape[:3]
    row = {"id": sid, "member": member,
           "files": {name: file_record(data) for name, data in sorted(files.items())},
           "grid": grid_facts(grid_img), "field_mm": field_facts(grid_img),
           "levels": {name: label_facts(levels[name], affine, shape) for name in COLUMN_NAMES if name in levels},
           "context": {name: extent_facts(points, affine, shape) for name, points in sorted(context.items())},
           "ribs": rib_facts(ribs, levels, affine) if ribs else {},
           "distances_mm": lumbosacral_distances(levels, affine)}
    return row


def same_grid(first, second) -> bool:
    return first.shape[:3] == second.shape[:3] and np.allclose(first.affine, second.affine, atol=1e-3)


# ---------------------------------------------------------------- TotalSegmentator

def zip_member(span: bytes, first: int, entry: dict) -> bytes:
    """One member's bytes from a span of the release zip that starts at byte `first`."""
    at = entry["offset"] - first
    if span[at:at + 4] != b"PK\x03\x04":
        raise ValueError("no local header at %s" % entry["name"])
    name_length, extra_length = struct.unpack("<HH", span[at + 26:at + 30])
    start = at + 30 + name_length + extra_length
    data = span[start:start + entry["csize"]]
    if entry["method"] == 8:
        data = zlib.decompress(data, -15)
    if len(data) != entry["usize"]:
        raise ValueError("%s: %d bytes, the directory says %d" % (entry["name"], len(data), entry["usize"]))
    return data


def ts_row(job) -> dict:
    sid, path, first, entries = job
    span = open(path, "rb").read()
    files, levels, context, ribs, grid_img = {}, {}, {}, {}, None
    for entry in entries:
        base = entry["name"].split("/")[-1]
        data = zip_member(span, first, entry)
        files[base] = data
        img = image_of(data)
        if grid_img is None:
            grid_img = img
        elif not same_grid(grid_img, img):
            raise ValueError("%s: %s lies on another grid" % (sid, base))
        found = voxel_points(img).get(1)
        if found is None or not len(found):
            continue
        if base in TS_LEVEL_FILES:
            levels[TS_LEVEL_FILES[base]] = found
        elif base in TS_CONTEXT_FILES:
            context[TS_CONTEXT_FILES[base]] = found
        elif TS_RIB_FILE.match(base):
            side, k = TS_RIB_FILE.match(base).groups()
            ribs[f"{side}_{int(k)}"] = found
    return study_row("totalsegmentator", sid, files, grid_img, levels, context, ribs)


def ts_jobs(spans: str) -> list:
    index = json.load(open(os.path.join(spans, "index.json")))
    return [(sid, os.path.join(spans, sid + ".span"), item["lo"], item["entries"])
            for sid, item in sorted(index.items())]


# ---------------------------------------------------------------- VerSe

VERSE_MASK = re.compile(r"^(?:sub-)?(?P<first>verse\d+|gl\d+)(?:_(?:split-)?(?P<second>verse\d+|gl\d+))?"
                        r"(?:_[A-Za-z][A-Za-z0-9]*[-_][A-Za-z0-9]+)*_(?:seg|msk)\.nii\.gz$", re.IGNORECASE)
VERSE_RELEASES = ("verse20", "verse19")  # the preferred release first, as VerSeFusion's unify stage chooses


def verse_series(name: str):
    """(series, patient named in the file or None) from a VerSe mask's file name, in either of the
    release's spellings: MICCAI's verse014_seg.nii.gz, verse512_CT-iso_seg.nii.gz, GL017_CT_ax_seg.nii.gz
    and verse400_verse090_CT-iso_seg.nii.gz (patient verse400, series verse090), or BIDS's
    sub-verse500_dir-iso_seg-vert_msk.nii.gz. The series is the scan's own id, the second where two
    are given; the wireframe and snapshot files never match."""
    if name.endswith("_seg-subreg_msk.nii.gz"):
        return None
    match = VERSE_MASK.match(name)
    if not match:
        return None
    first, second = match.group("first").lower(), match.group("second")
    return (second.lower(), first) if second else (first, None)


def label_voxels(found: dict) -> dict:
    return {VERSE_NAMES[label]: int(len(points)) for label, points in found.items() if label in VERSE_NAMES}


def other_release(release: str, path: str, img, found: dict) -> dict:
    """What a series' copy in the release not chosen holds beside the chosen copy (img, whose labels
    are found): the same grid, the same levels and the levels whose voxel counts differ, so a
    correction between releases is seen rather than lost."""
    data = open(path, "rb").read()
    other = image_of(data)
    mine, theirs = label_voxels(found), label_voxels(voxel_points(other))
    return {"release": release, "file": {os.path.basename(path): file_record(data)},
            "same_grid": bool(same_grid(img, other)), "same_levels": sorted(mine) == sorted(theirs),
            "voxels_differ": sorted(name for name in set(mine) | set(theirs) if mine.get(name) != theirs.get(name))}


def verse_row(job) -> dict:
    sid, patient, copies = job
    release = next(name for name in VERSE_RELEASES if name in copies)
    path = copies[release]
    data = open(path, "rb").read()
    img = image_of(data)
    found = voxel_points(img)
    levels = {VERSE_NAMES[label]: points for label, points in found.items() if label in VERSE_NAMES}
    row = study_row("verse", sid, {os.path.basename(path): data}, img, levels, {}, {})
    row["release"] = release
    row["patient_in_name"] = patient
    others = [other_release(name, copies[name], img, found) for name in VERSE_RELEASES
              if name in copies and name != release]
    if others:
        row["other_release"] = others[0]
    outside = sorted(label for label in found if label not in VERSE_NAMES)
    if outside:
        row["outside_scheme"] = outside
    return row


def verse_jobs(folder: str) -> list:
    """One job a series, from MASKDIR/<release>/ for each release present: (series, patient named
    in a file or None, {release: path})."""
    copies, patients = {}, {}
    for release in VERSE_RELEASES:
        where = os.path.join(folder, release)
        if not os.path.isdir(where):
            continue
        for name in sorted(os.listdir(where)):
            parsed = verse_series(name)
            if not parsed:
                continue
            series, patient = parsed
            if release in copies.setdefault(series, {}):
                raise ValueError("%s holds two masks for %s" % (where, series))
            copies[series][release] = os.path.join(where, name)
            if patient:
                patients[series] = patient
    return [(series, patients.get(series), copies[series]) for series in sorted(copies)]


# ---------------------------------------------------------------- running

def safe(function):
    def run(job):
        try:
            return function(job)
        except Exception as error:  # a study that cannot be read is a row that says so
            return {"id": job[0], "error": "%s: %s" % (type(error).__name__, error)}
    return run


def ts_safe(job):
    return safe(ts_row)(job)


def verse_safe(job):
    return safe(verse_row)(job)


def row_line(row: dict) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"


def write_rows(rows, out: str) -> int:
    rows = sorted(rows, key=lambda row: row["id"])
    with open(out + ".tmp", "w", encoding="ascii", newline="\n") as f:
        for row in rows:
            f.write(row_line(row))
    os.replace(out + ".tmp", out)
    return len(rows)


def rows_written(part: str) -> list:
    """The rows a run cut short wrote whole to OUT.part, a line each; a line cut off is read again."""
    if not os.path.exists(part):
        return []
    with open(part, encoding="ascii") as f:
        return [json.loads(line) for line in f if line.endswith("\n")]


def run(function, jobs, out: str, workers: int) -> int:
    """Each study's row, written to OUT.part as it comes and sorted into OUT at the end, so a run cut
    short (a worker killed for its memory, a container stopped) loses no row and a second run reads
    only the studies the first did not write. A worker that dies stops the run with an error rather
    than leaving it waiting: on 2026-10-29 the multiprocessing pool this replaced waited more than
    20 minutes for a VerSe worker the kernel had killed."""
    part = out + ".part"
    rows = rows_written(part)
    done = {row["id"] for row in rows}
    todo = [job for job in jobs if job[0] not in done]
    with open(part, "w", encoding="ascii", newline="\n") as f:
        f.writelines(row_line(row) for row in rows)
        with ProcessPoolExecutor(workers) as pool:
            futures = [pool.submit(function, job) for job in todo]
            for n, future in enumerate(as_completed(futures), len(rows) + 1):
                row = future.result()
                f.write(row_line(row))
                f.flush()
                rows.append(row)
                if n % 100 == 0:
                    print(n, file=sys.stderr, flush=True)
    count = write_rows(rows, out)
    os.remove(part)
    return count


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="member", required=True)
    ts = sub.add_parser("totalsegmentator")
    ts.add_argument("spans")
    ts.add_argument("out")
    ts.add_argument("--workers", type=int, default=WORKERS)
    verse = sub.add_parser("verse")
    verse.add_argument("maskdir")
    verse.add_argument("out")
    verse.add_argument("--workers", type=int, default=WORKERS)
    args = parser.parse_args(argv)
    if args.member == "totalsegmentator":
        n = run(ts_safe, ts_jobs(args.spans), args.out, args.workers)
    else:
        n = run(verse_safe, verse_jobs(args.maskdir), args.out, args.workers)
    print("%d rows" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
