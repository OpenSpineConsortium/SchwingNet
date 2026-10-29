"""Per-study facts of ENHANCE.PET 1.6k's published masks, one JSON line per study.

Confidential, like the rest of this repository: nothing here, and nothing it writes, goes to a
public place, and no mask or CT is ever copied into the repository.

The gold tier 3 CT dataset in SchwingNet makes its column calls and quality checks in the
standard library alone, so it cannot read a mask. This module reads each study's published
vertebra and rib masks once, here where numpy, scipy and nibabel are allowed, and writes what
those calls and checks need as plain facts: each label's voxels, head-foot extent, centroid and
connected pieces; the contact tally of every rib, not only the lowest; the shortest distances
between neighbouring column labels and from each lumbar label to the sacrum; and each mask's
bytes, hash and grid, beside the study table's scanner columns.

    python -m holdings.enhance_facts facts MASKDIR RIBDIR TABLE OUT.jsonl
        [--listing VERT.json RIB.json] [--repair-record DIR] [--workers N] [--ids FILE]

Everything the count already defines is taken from holdings/count_enhance_pet.py, not written
again, so that the facts and the count cannot drift: the label schemes, the head-foot axis and
its slice-centre convention, the slab reader, the contact tally with its reach and its box, the
rule that a tie goes to the head-most label, the study table reader, and the repair record with
its hash check. The slice centres alone are taken before the count's rounding (slice_centres
says why). The three repaired masks are read as extra rows keyed 1134r, 1283r and 1347r:
the repaired vertebrae beside the published ribs.

A mask is read from its file once, a slab at a time, and held as its labelled voxels alone
(LabelledVoxels), never as a whole volume: the finest studies hold 700 million voxels, and other
work shares the container. The labelled voxels hand out dense blocks as nibabel's dataobj does,
so count_enhance_pet.rib_contacts runs on them unchanged and gives the count's own tally.

Each row, keys sorted, ints where counts, mm to 0.1, the grid to 6 decimals, shares to 4:

    id, site, scanner {manufacturer, model, kvp, kernel, pixel_spacing, slice_thickness}
        (the study table's cells as given), and repaired_from on a repaired row;
    mask {bytes, listed_bytes, sha256, shape, zooms, affine, axcodes, head_foot_axis, dtype};
    ribs_mask {bytes, listed_bytes, sha256, same_grid};
    labels {label: {voxels, top_mm, bottom_mm, centroid_mm, components, largest_share}}
        for every vertebra label 1 to 28 with a voxel: top and bottom are the head-most and
        foot-most slice centres in head-foot mm, as the count's extents step reads them; the
        centroid is in the affine's world, nibabel's RAS; pieces are 26-connected;
    ribs {label: {voxels, components, contacts {vertebra label: voxels}, lead, lead_n, tie}}
        for every rib label 1 to 26 with a voxel, contacts the count's tally of that rib;
    sternum_voxels, distances_mm {"a-b": mm}, outside_scheme_voxels {vertebrae, ribs}; a distance
        is the shortest between the voxel centres of labels a and b, for the pairs of
        DISTANCE_PAIRS whose two labels both have a voxel.

listed_bytes is the bucket listing's size of the same object, null where no listing is given or
the listing does not hold it (a repaired mask is not in the bucket). contacts, lead and tie are
null, null and false where the two masks lie on different grids, which ribs_mask.same_grid says.

A run writes each row as it finishes to OUT.jsonl.partial and the sorted rows to OUT.jsonl at the
end, so a run cut short carries on from the rows it wrote, each reused only where its masks'
hashes and its study table and listing cells are still the same, and only by the same code: the
partial file's first line names the code that wrote it (code_digest).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from multiprocessing import Pool

import nibabel as nib
import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

from holdings import count_enhance_pet
from holdings.count_enhance_pet import (
    L1, L6, MASK_ENDINGS, MAX_WORKERS, REPAIR_RECORD, REPAIRED, RIBS_PER_SIDE, RIGHT_RIB_BASE,
    SACRUM, TOP_RIB_LABEL, TOP_VERTEBRA_LABEL, UNKNOWN_SITE, RepairRecordError, file_sha256,
    head_foot_axis, mask_files, mask_path, meeting, read_ids, read_sha256sums, repaired_mask,
    rib_contacts, same_grid, sheet_rows, short_site, slice_counts, storage_slabs, study_id)

# Rows carry mm to a tenth, below any voxel of the release; the grid to six decimals, enough to
# tell two grids apart at count_enhance_pet's GRID_TOLERANCE_MM; shares to four.
MM_DECIMALS, GRID_DECIMALS, SHARE_DECIMALS = 1, 6, 4

# Two processes unless told otherwise: the container's four CPUs and its memory are shared with
# other work, and the distance map over the largest rib's box takes about a gigabyte.
FACTS_WORKERS = 2
# A process is replaced after this many studies, so memory a large study leaves scattered goes
# back to the system before the next large one.
STUDIES_PER_PROCESS = 50
PROGRESS_EVERY = 50

# The rib labels: left ribs 1 to 13, right ribs 14 to 26; the sternum is the rib mask's top label.
TOP_RIB = RIGHT_RIB_BASE + RIBS_PER_SIDE
STERNUM = TOP_RIB_LABEL

# Pieces are 26-connected, as the repair record's components.py splits a label: on 5 mm slices
# the slices of one body often meet only at an edge or a corner.
PIECES = np.ones((3, 3, 3), bool)

# The nearest voxel of one label to another lies on its boundary among its six face neighbours:
# from a voxel inside, one step toward the other label's voxel stays in the label and is strictly
# nearer. So the shortest distance is sought among boundary voxels alone, and is the same as the
# least of the distance map over the label that the repair record's touch.py takes.
FACES = ndimage.generate_binary_structure(3, 1)

# The distances the column calls and checks read: each neighbouring pair of column labels from
# C1-C2 to L5-L6, and each lumbar label to the sacrum ("23-28" is L4 to the sacrum).
NEIGHBOUR_PAIRS = [(label, label + 1) for label in range(1, L6)]
SACRUM_PAIRS = [(label, SACRUM) for label in range(L1, L6 + 1)]
DISTANCE_PAIRS = NEIGHBOUR_PAIRS + SACRUM_PAIRS

# The study table's columns a row carries, found by their headers without the unit.
SCANNER_COLUMNS = (("manufacturer", "Manufacturer"), ("model", "Model"), ("kvp", "kVp"),
                   ("kernel", "Convolutional Kernel"), ("pixel_spacing", "Pixel Spacing"),
                   ("slice_thickness", "Slice Thickness"))
STUDY_COLUMN, SITE_COLUMN = "A", "B"

# A repaired mask's row is its study's id with this ending, so it sorts beside the published row.
REPAIRED_ENDING = "r"
PARTIAL_ENDING = ".partial"
# The key of the partial file's first line, which names the code that wrote the file's rows.
CODE_KEY = "code"


# ---------------------------------------------------------------- numbers

def rounded(value, decimals: int) -> float:
    """A float rounded for the row; adding 0.0 turns a rounded -0.0 into 0.0."""
    return round(float(value), decimals) + 0.0


def rounded_list(values, decimals: int) -> list:
    return [rounded(value, decimals) for value in values]


# ---------------------------------------------------------------- a mask as its labelled voxels

class LabelledVoxels:
    """A mask held as its labelled voxels, read from the file a slab at a time, which hands out
    dense blocks of any box as nibabel's dataobj does, zero where no label is."""

    def __init__(self, img):
        self.shape = tuple(int(n) for n in img.shape[:3])
        self.affine = np.asarray(img.affine, float)
        self.dataobj = self
        points, values, dtype = [], [], img.dataobj.dtype
        for start, block in storage_slabs(img):
            where = np.nonzero(block)
            points.append(np.stack([where[0], where[1], where[2] + start], axis=1).astype(np.int32))
            values.append(block[where])
            dtype = block.dtype
        self.dtype = dtype
        points = np.concatenate(points) if points else np.zeros((0, 3), np.int32)
        values = np.concatenate(values) if values else np.zeros(0, dtype)
        # Held in order along the file's last axis, so a box's voxels are found by two searches.
        order = np.argsort(points[:, 2], kind="stable")
        self.points, self.values = points[order], values[order]
        self.last = np.ascontiguousarray(self.points[:, 2])

    def __getitem__(self, index) -> np.ndarray:
        bounds = [box_bounds(part, n) for part, n in zip(index, self.shape)]
        low = np.array([b[0] for b in bounds])
        high = np.array([b[1] for b in bounds])
        block = np.zeros(tuple(int(n) for n in high - low), self.dtype)
        first, end = np.searchsorted(self.last, [low[2], high[2]])
        points, values = self.points[first:end], self.values[first:end]
        inside = np.all((points >= low) & (points < high), axis=1)
        block[tuple((points[inside] - low).T)] = values[inside]
        return block

    def label_points(self, label: int) -> np.ndarray:
        return self.points[self.values == label]


def box_bounds(part, n: int) -> tuple:
    """The start and stop of one axis of a box, which must be a plain slice."""
    if not isinstance(part, slice):
        raise TypeError("a block is asked for with slices, not %r" % (part,))
    start, stop, step = part.indices(n)
    if step != 1:
        raise ValueError("a block is asked for with a step of 1, not %d" % step)
    return start, max(stop, start)


def read_mask(path: str, top_label: int) -> tuple:
    """The image, its labelled voxels, its voxels per head-foot slice and label (the count's own
    table), its voxels outside the scheme, and its head-foot axis."""
    img = nib.load(path, keep_file_open=True)
    axis = head_foot_axis(img.affine)
    counts, outside = slice_counts(img, axis, top_label)
    voxels = LabelledVoxels(img)
    check_reads_agree(path, counts, voxels, top_label)
    return img, voxels, counts, outside, axis


def check_reads_agree(path: str, counts: np.ndarray, voxels: LabelledVoxels, top_label: int) -> None:
    """The two reads of one file must count every label alike; a difference is a bug here."""
    held = np.bincount(voxels.values[(voxels.values > 0) & (voxels.values <= top_label)].astype(np.int64),
                       minlength=top_label + 1)
    if not np.array_equal(held[1:], counts.sum(0)[1:]):
        raise RuntimeError("%s: the labelled voxels and the slab counts disagree" % path)


def grid_facts(path: str, img, axis: int, listed) -> dict:
    affine = np.asarray(img.affine, float)
    return {"bytes": os.path.getsize(path), "listed_bytes": listed, "sha256": file_sha256(path),
            "shape": [int(n) for n in img.shape[:3]],
            "zooms": rounded_list(img.header.get_zooms()[:3], GRID_DECIMALS),
            "affine": [rounded_list(row, GRID_DECIMALS) for row in affine],
            "axcodes": "".join(nib.aff2axcodes(affine)), "head_foot_axis": int(axis),
            "dtype": str(img.get_data_dtype())}


def file_zooms(img) -> np.ndarray:
    return np.array(img.header.get_zooms()[:3], float)


def block_zooms(img, axis: int) -> np.ndarray:
    """The voxel sizes in the order read_block hands a block out, the head-foot axis last, as
    count_enhance_pet.lowest_rib_contacts orders them for rib_contacts."""
    zooms = file_zooms(img)
    return np.concatenate([np.delete(zooms, axis), zooms[axis:axis + 1]])


# ---------------------------------------------------------------- labels

def crop_of(points: np.ndarray) -> tuple:
    """The voxels as a boolean box just holding them, and the box's first corner."""
    low = points.min(axis=0)
    box = np.zeros(tuple(int(n) for n in points.max(axis=0) - low + 1), bool)
    box[tuple((points - low).T)] = True
    return box, low


def pieces_of(points: np.ndarray) -> tuple:
    """How many connected pieces the voxels make, and the largest piece's share of them."""
    box, _ = crop_of(points)
    pieces, n = ndimage.label(box, structure=PIECES)
    sizes = np.bincount(pieces.ravel())[1:]
    return int(n), rounded(sizes.max() / len(points), SHARE_DECIMALS)


def world_centroid(points: np.ndarray, affine: np.ndarray) -> list:
    centre = points.mean(axis=0)
    return rounded_list(affine[:3, :3] @ centre + affine[:3, 3], MM_DECIMALS)


def slice_centres(present: np.ndarray, origin: float, step: float) -> dict:
    """Each label's foot-most and head-most slice centre in head-foot mm, as
    count_enhance_pet.label_extents places them, but not rounded.

    label_extents rounds the centres to 0.001 mm for the count's own output. Rounded again to
    0.1 mm, a centre within 0.0005 mm of a twentieth can go the wrong way: -118.0505 reads -118.050
    and then -118.0, where it is -118.1. 38 of the release's 86,100 extents did so, all in
    Careggi studies on 2.81 mm slices, whose single-precision grids put centres a few
    ten-thousandths of a millimetre off a twentieth, so a row rounds each centre once."""
    out = {}
    for label in range(1, present.shape[1]):
        rows = np.flatnonzero(present[:, label])
        if len(rows):
            out[label] = sorted([float(origin + step * rows[0]), float(origin + step * rows[-1])])
    return out


def label_facts(voxels: LabelledVoxels, counts: np.ndarray, affine: np.ndarray, axis: int) -> dict:
    """Every vertebra label with a voxel: its voxels, its head-most and foot-most slice centres in
    head-foot mm (count_enhance_pet's extents), its centroid, and its pieces."""
    totals = counts.sum(axis=0)
    centres = slice_centres(counts > 0, float(affine[2, 3]), float(affine[2, axis]))
    out = {}
    for label in range(1, TOP_VERTEBRA_LABEL + 1):
        if not totals[label]:
            continue
        points = voxels.label_points(label)
        bottom, top = centres[label]
        pieces, largest = pieces_of(points)
        out[str(label)] = {"voxels": int(totals[label]), "top_mm": rounded(top, MM_DECIMALS),
                           "bottom_mm": rounded(bottom, MM_DECIMALS),
                           "centroid_mm": world_centroid(points, affine), "components": pieces,
                           "largest_share": largest}
    return out


# ---------------------------------------------------------------- distances

def boundary_of(points: np.ndarray) -> np.ndarray:
    """The voxels with a face neighbour outside the label."""
    box, low = crop_of(points)
    inner = ndimage.binary_erosion(box, structure=FACES, border_value=0)
    return np.argwhere(box & ~inner) + low


def shortest_mm(first: np.ndarray, second: np.ndarray, zooms: np.ndarray) -> float:
    """The shortest distance between the voxel centres of two labels, given their boundary voxels.

    Each voxel of the first is paired with its nearest voxel of the second, and the distance of
    the pair is then taken as scipy's distance map takes it, steps times voxel sizes, squared and
    summed axis by axis, so the least is the number touch.py read off the map."""
    _, nearest = cKDTree(second * zooms).query(first * zooms)
    steps = (second[nearest] - first).astype(np.float64) * zooms
    return rounded(np.sqrt(np.add.reduce(steps * steps, axis=1)).min(), MM_DECIMALS)


def distance_facts(voxels: LabelledVoxels, zooms: np.ndarray, present: set) -> dict:
    boundaries = {}
    out = {}
    for first, second in DISTANCE_PAIRS:
        if first in present and second in present:
            for label in (first, second):
                if label not in boundaries:
                    boundaries[label] = boundary_of(voxels.label_points(label))
            out["%d-%d" % (first, second)] = shortest_mm(boundaries[first], boundaries[second], zooms)
    return out


# ---------------------------------------------------------------- ribs

def tally_facts(tally) -> dict:
    """The contact tally of one rib, the label it leads on, that label's contacts, and a tie."""
    if tally is None:
        return {"contacts": None, "lead": None, "lead_n": 0, "tie": False}
    lead, tie = meeting(tally)
    return {"contacts": {str(label): int(n) for label, n in sorted(tally.items())}, "lead": lead,
            "lead_n": int(tally.get(lead, 0)), "tie": bool(tie)}


def rib_facts(vert: LabelledVoxels, rib: LabelledVoxels, counts: np.ndarray, axis: int,
              zooms: np.ndarray, same: bool) -> dict:
    """Every rib label with a voxel: its voxels, its pieces, and count_enhance_pet's contact tally."""
    totals = counts.sum(axis=0)
    out = {}
    for label in range(1, TOP_RIB + 1):
        if not totals[label]:
            continue
        pieces, _ = pieces_of(rib.label_points(label))
        tally = rib_contacts(vert, rib, axis, counts[:, label], label, zooms) if same else None
        out[str(label)] = dict(tally_facts(tally), voxels=int(totals[label]), components=pieces)
    return out


# ---------------------------------------------------------------- one study

def study_facts(job) -> tuple:
    """(row id, row) for one vertebra mask and its study's rib mask."""
    row_id, vert_path, rib_path, extra = job
    vert_img, vert, vert_counts, vert_outside, axis = read_mask(vert_path, TOP_VERTEBRA_LABEL)
    rib_img, rib, rib_counts, rib_outside, rib_axis = read_mask(rib_path, TOP_RIB_LABEL)
    same = bool(same_grid(vert_img, rib_img))
    labels = label_facts(vert, vert_counts, np.asarray(vert_img.affine, float), axis)
    row = {
        "id": row_id,
        "mask": grid_facts(vert_path, vert_img, axis, extra["listed_bytes"]),
        "ribs_mask": {"bytes": os.path.getsize(rib_path), "listed_bytes": extra["ribs_listed_bytes"],
                      "sha256": file_sha256(rib_path), "same_grid": same},
        "labels": labels,
        "ribs": rib_facts(vert, rib, rib_counts, rib_axis, block_zooms(rib_img, rib_axis), same),
        "sternum_voxels": int(rib_counts.sum(axis=0)[STERNUM]),
        "distances_mm": distance_facts(vert, file_zooms(vert_img), {int(label) for label in labels}),
        "outside_scheme_voxels": {"vertebrae": int(vert_outside), "ribs": int(rib_outside)},
    }
    row.update(extra["cells"])
    return row_id, row


# ---------------------------------------------------------------- the jobs

def header_name(text) -> str:
    """A header without its unit: "Pixel Spacing [mm]" reads "Pixel Spacing"."""
    return (text or "").split(" [")[0].strip()


def table_rows(path: str) -> list:
    """CT-details.xlsx's rows as {column letters: value}, from the workbook or from SchwingNet's
    committed copy of the same rows (data/gold3-ct/enhance-pet/ct-details.json), so a run on the
    grid needs no second fetch for one small table."""
    if path.endswith(".json"):
        with open(path) as handle:
            return json.load(handle)["rows"]
    return sheet_rows(path)


def study_sites(rows: list) -> dict:
    """The short site of every study, as count_enhance_pet.sites_step reads column B."""
    return {(cells.get(STUDY_COLUMN) or "").strip(): short_site((cells.get(SITE_COLUMN) or "").strip())
            for cells in rows[1:] if (cells.get(STUDY_COLUMN) or "").strip()}


def study_table(path: str) -> tuple:
    """The short site of every study and its scanner cells as given."""
    rows = table_rows(path)
    letters = {header_name(name): letter for letter, name in rows[0].items()}
    missing = [header for _, header in SCANNER_COLUMNS if header not in letters]
    if missing:
        raise ValueError("%s has no column %s" % (path, ", ".join(missing)))
    scanners = {}
    for cells in rows[1:]:
        sid = (cells.get(STUDY_COLUMN) or "").strip()
        if sid:
            scanners[sid] = {key: cells.get(letters[header]) for key, header in SCANNER_COLUMNS}
    return study_sites(rows), scanners


def listed_bytes(path) -> dict:
    """Each study's object size in a bucket listing, a JSON list of [key, bytes]."""
    if not path:
        return {}
    with open(path) as handle:
        entries = json.load(handle)
    sizes = {}
    for key, size in entries:
        name = str(key).rsplit("/", 1)[-1]
        if name.endswith(MASK_ENDINGS):
            sizes[study_id(name)] = int(size)
    return sizes


def run_ids(maskdir: str, ids_file) -> list:
    found = [study_id(name) for name in mask_files(maskdir)]
    if not ids_file:
        return found
    wanted = sorted({sid for group in read_ids(ids_file, maskdir).values() for sid in group})
    unknown = sorted(set(wanted) - set(found))
    if unknown:
        raise ValueError("%s holds no mask for %s" % (maskdir, ", ".join(unknown)))
    return wanted


def study_cells(sid: str, sites: dict, scanners: dict) -> dict:
    blank = {key: None for key, _ in SCANNER_COLUMNS}
    return {"site": sites.get(sid, UNKNOWN_SITE), "scanner": scanners.get(sid, blank)}


def repaired_jobs(ids: list, ribdir: str, record: str, cells: dict, rib_sizes: dict) -> list:
    """The repaired masks of the record whose studies are in the run, each checked against the
    record's SHA256SUMS, beside the study's published ribs."""
    in_run = set(ids)
    wanted = [sid for sid in sorted(REPAIRED) if sid in in_run]
    if not wanted or not record:
        return []
    sums_path = os.path.join(record, "SHA256SUMS")
    if not os.path.exists(sums_path):
        raise RepairRecordError("the repair record %s has no SHA256SUMS" % record)
    sums = read_sha256sums(sums_path)
    jobs = []
    for sid in wanted:
        extra = {"cells": dict(cells[sid], repaired_from=sid), "listed_bytes": None,
                 "ribs_listed_bytes": rib_sizes.get(sid)}
        jobs.append((sid + REPAIRED_ENDING, os.path.join(record, repaired_mask(record, sums, sid)),
                     mask_path(ribdir, sid), extra))
    return jobs


def study_jobs(maskdir: str, ribdir: str, xlsx: str, listing=None, record: str = REPAIR_RECORD,
               ids_file=None) -> list:
    ids = run_ids(maskdir, ids_file)
    sites, scanners = study_table(xlsx)
    vert_sizes, rib_sizes = (listed_bytes(path) for path in (listing or (None, None)))
    cells = {sid: study_cells(sid, sites, scanners) for sid in ids}
    jobs = [(sid, mask_path(maskdir, sid), mask_path(ribdir, sid),
             {"cells": cells[sid], "listed_bytes": vert_sizes.get(sid), "ribs_listed_bytes": rib_sizes.get(sid)})
            for sid in ids]
    return jobs + repaired_jobs(ids, ribdir, record, cells, rib_sizes)


# ---------------------------------------------------------------- running and writing

def row_line(row: dict) -> str:
    return json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n"


def fits(row: dict, job) -> bool:
    """Whether a row written by an earlier run still stands for this job's files and cells."""
    row_id, vert_path, rib_path, extra = job
    mask, ribs_mask = row.get("mask", {}), row.get("ribs_mask", {})
    return (row.get("id") == row_id
            and all(row.get(key) == value for key, value in extra["cells"].items())
            and mask.get("listed_bytes") == extra["listed_bytes"]
            and ribs_mask.get("listed_bytes") == extra["ribs_listed_bytes"]
            and mask.get("sha256") == file_sha256(vert_path)
            and ribs_mask.get("sha256") == file_sha256(rib_path))


def code_digest() -> str:
    """The hashes of this module and of the count, the code every row is computed by.

    fits sees a row's files and cells, never the code that read them, so a run resumed after a
    fix would keep rows the fixed code no longer writes; the partial file's first line names the
    code, and a partial file other code wrote is not read (partial_code)."""
    return file_sha256(os.path.abspath(__file__)) + file_sha256(os.path.abspath(count_enhance_pet.__file__))


def parsed_line(line: str):
    """A line of the partial file as JSON, or None for a line a run cut short."""
    try:
        return json.loads(line)
    except ValueError:
        return None


def partial_code(partial: str):
    """The code digest the partial file's first line names, or None where it names none."""
    if not os.path.exists(partial):
        return None
    with open(partial) as handle:
        first = parsed_line(handle.readline())
    return first.get(CODE_KEY) if isinstance(first, dict) else None


def resumed_rows(partial: str, jobs: list) -> dict:
    """The rows an earlier run of the same jobs wrote that still stand; a line cut short is skipped."""
    if not os.path.exists(partial):
        return {}
    by_id = {job[0]: job for job in jobs}
    rows = {}
    with open(partial) as handle:
        for line in handle:
            row = parsed_line(line)
            job = by_id.get(row.get("id")) if isinstance(row, dict) else None
            if job is not None and fits(row, job):
                rows[row["id"]] = row
    return rows


def open_partial(partial: str, code: str, resumed: bool):
    """The partial file to append rows to: the one an earlier run of the same code left, its line
    cut short ended first so the next row starts a line of its own, or a new one naming the code."""
    if resumed:
        with open(partial, "rb") as handle:
            handle.seek(-1, os.SEEK_END)
            ended = handle.read(1) == b"\n"
        handle = open(partial, "a", newline="\n")
        if not ended:
            handle.write("\n")
        return handle
    handle = open(partial, "w", newline="\n")
    handle.write(json.dumps({CODE_KEY: code}) + "\n")
    return handle


def run_unordered(function, jobs: list, workers: int):
    """Yield `function` over `jobs` as each finishes, in at most MAX_WORKERS processes."""
    workers = max(1, min(workers, MAX_WORKERS))
    if workers == 1:
        for job in jobs:
            yield function(job)
        return
    with Pool(workers, maxtasksperchild=STUDIES_PER_PROCESS) as pool:
        yield from pool.imap_unordered(function, jobs)


def largest_first(jobs: list) -> list:
    """The jobs by their vertebra mask's bytes, largest first, so no large study finishes last."""
    return sorted(jobs, key=lambda job: (-os.path.getsize(job[1]), job[0]))


def write_rows(rows: dict, out: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    written = out + ".tmp"
    with open(written, "w", newline="\n") as handle:
        for row_id in sorted(rows):
            handle.write(row_line(rows[row_id]))
    os.replace(written, out)


def facts_step(maskdir: str, ribdir: str, xlsx: str, out: str, listing=None, record: str = REPAIR_RECORD,
               workers: int = FACTS_WORKERS, ids_file=None) -> dict:
    jobs = study_jobs(maskdir, ribdir, xlsx, listing, record, ids_file)
    partial, code = out + PARTIAL_ENDING, code_digest()
    resumed = partial_code(partial) == code
    rows = resumed_rows(partial, jobs) if resumed else {}
    todo = largest_first([job for job in jobs if job[0] not in rows])
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    started = time.time()
    with open_partial(partial, code, resumed) as handle:
        for done, (row_id, row) in enumerate(run_unordered(study_facts, todo, workers), 1):
            handle.write(row_line(row))
            handle.flush()
            rows[row_id] = row
            if done % PROGRESS_EVERY == 0:
                print("%d of %d in %.0f s" % (done, len(todo), time.time() - started), file=sys.stderr, flush=True)
    write_rows(rows, out)
    os.remove(partial)
    return rows


def listing_differences(rows: dict) -> list:
    """Rows whose published masks are missing from the listing or differ from it in bytes."""
    out = []
    for row_id, row in sorted(rows.items()):
        masks = [row["ribs_mask"]] + ([] if "repaired_from" in row else [row["mask"]])
        if any(mask["listed_bytes"] != mask["bytes"] for mask in masks):
            out.append(row_id)
    return out


# ---------------------------------------------------------------- the command line

def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(prog="python -m holdings.enhance_facts", description=__doc__.split("\n")[0])
    steps = command.add_subparsers(dest="step", required=True)
    step = steps.add_parser("facts", help="one JSON line of facts per study, and per repaired mask")
    step.add_argument("maskdir"), step.add_argument("ribdir")
    step.add_argument("xlsx", metavar="TABLE",
                      help="CT-details.xlsx, or SchwingNet's data/gold3-ct/enhance-pet/ct-details.json")
    step.add_argument("out")
    step.add_argument("--listing", nargs=2, metavar=("VERT", "RIB"),
                      help="the bucket listings of the vertebra and rib masks, JSON lists of [key, bytes]")
    step.add_argument("--repair-record", default=REPAIR_RECORD,
                      help="the folder holding repaired/ and SHA256SUMS (default %(default)s); "
                           "empty reads no repaired mask, as on the grid, which holds no repair record")
    step.add_argument("--workers", type=int, default=FACTS_WORKERS)
    step.add_argument("--ids", help="read only these studies: a JSON list, an object of lists or a count's output")
    return command


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    started = time.time()
    rows = facts_step(args.maskdir, args.ribdir, args.xlsx, args.out, args.listing, args.repair_record,
                      args.workers, args.ids)
    repaired = sum(1 for row in rows.values() if "repaired_from" in row)
    print("%d rows (%d studies, %d repaired masks) in %.0f s" % (len(rows), len(rows) - repaired, repaired,
                                                                 time.time() - started))
    if args.listing:
        differ = listing_differences(rows)
        print("%d rows whose masks are missing from the listing or differ from it in bytes%s"
              % (len(differ), ": " + ", ".join(differ) if differ else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
