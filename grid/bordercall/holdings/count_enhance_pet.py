"""Count ENHANCE.PET 1.6k's whole C2-to-sacrum studies from its published masks.

Confidential, like the rest of this repository: nothing here, and nothing it writes, goes to a
public place, and no mask or CT is ever copied into the repository.

holdings/gold-tier-3.md asks how many ENHANCE.PET studies are gold tier 3: a whole spine, C2 to
the sacrum in one study, with a person's annotation. MOOSE drew the masks and four readers checked
and corrected them, so a published mask that holds C2 to the sacrum is a person's whole spine.
Each step reads what the one before it wrote and writes JSON, so a step can be checked and run
again alone:

    python -m holdings.count_enhance_pet extents MASKDIR OUT
    python -m holdings.count_enhance_pet sites XLSX OUT
    python -m holdings.count_enhance_pet count EXTENTS SITES OUT [--repair-record DIR]
    python -m holdings.count_enhance_pet ribs MASKDIR RIBDIR IDS OUT [--pairs-only]
    python -m holdings.count_enhance_pet report COUNT [RIBS ...]

The tests run from the repository's root with `python -m unittest discover -s holdings/tests -t .`,
or with a plain `python -m unittest discover` there, which reaches them through holdings/__init__.py.

The rules of the count, each threshold a named constant below with its reason:

- strict: C2 to L5 and the sacrum each hold at least MIN_VOXELS voxels, so no level label from C2
  to L5 is missing, and no space between consecutive labels is wider than UNLABELLED_GAP_MM. That
  does not prove every body carries a label: neighbouring levels overlap head to foot, so a body
  with no label above T11 leaves no space that wide, and the lowest-rib tally is the check there;
- no L5: C2 to L4 and the sacrum are labelled, L5 is not, and every label from L4 down overlaps
  the next as deeply as an L5 overlaps the sacrum (NO_L5_MEETS_MM);
- lumbar look: a lumbar label missing in any other way, or a space wider than UNLABELLED_GAP_MM
  below T12. The owner's rule of 27 October 2026, 17:10 UTC: a whole spine is never dropped for a
  missing or extra lumbar label; it is counted and reported as a variant. So these are whole, and
  listed for a look, since a lumbar body there may carry no label;
- whole: strict, no L5 or lumbar look;
- left out: a level from C2 to T12 with no label, or a space wider than UNLABELLED_GAP_MM above
  T12, which holds a body with no label. On the three the release leaves out the owner said at
  17:42 UTC "try to repair these with whatever segmentation model generated the spinal masks dont
  just throw them away": the repair record (REPAIR_RECORD) holds their repaired masks, which the
  count reads, checks against the record's hashes and classifies by the same rules, and each that
  reads as the record says is counted whole after repair.

Whole studies are also listed for a look, never left out, where the L5 label is a fragment over an
L4 that meets the sacrum (FRAGMENT_SHARE), or a space between neighbours is wider than LOOK_GAP_MM.

Extents are read slice by slice along the head-foot axis, so the numbers rest on head-foot
positions in world millimetres, as the scratch scripts that first made the count did.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from multiprocessing import Pool

import nibabel as nib
import numpy as np
from scipy import ndimage

# The vertebra masks' labels: C1 to C7 are 1 to 7, T1 to T12 are 8 to 19, L1 to L6 are 20 to 25,
# the two hips 26 and 27, the sacrum 28.
LEVEL_NAMES = (["C%d" % i for i in range(1, 8)] + ["T%d" % i for i in range(1, 13)]
               + ["L%d" % i for i in range(1, 7)])
LABEL_NAMES = {i + 1: name for i, name in enumerate(LEVEL_NAMES)}
LABEL_NAMES.update({26: "hip 26", 27: "hip 27", 28: "sacrum"})
C2, T12, L1, L4, L5, L6, SACRUM = 2, 19, 20, 23, 24, 25, 28
TOP_VERTEBRA_LABEL = 28
# Head to foot. The hips stand beside the column, not in it.
COLUMN = list(range(C2, L6 + 1)) + [SACRUM]
STRICT_LEVELS = list(range(C2, L5 + 1)) + [SACRUM]
# What a rib can meet: every vertebra and the sacrum, never a hip.
CONTACT_LABELS = list(range(1, L6 + 1)) + [SACRUM]

# The rib masks' labels: left rib k is k, right rib k is 13 + k, the sternum 27.
RIBS_PER_SIDE = 13
LEFT_RIB_BASE, RIGHT_RIB_BASE = 0, RIBS_PER_SIDE
TOP_RIB_LABEL = 27
SIDES = ("left", "right")
# Rib k's own vertebra is label k + 7: T1 to T12 are 8 to 19, and a thirteenth rib's own body is
# the one this scheme names L1, label 20, since it has no T13.
OWN_VERTEBRA_OFFSET = 7

# A level counts as labelled at 200 voxels or more, the floor of TotalSegmentator's whole-spine
# count (holdings/gold-tier-3.md), so the two counts read alike. The floor drops specks a reader
# left behind; it cannot tell a body from a fragment. A body cut by the field's top edge can hold
# fewer (the release has three, of 131 to 176 voxels, all in studies with no C2), and a fragment of
# a label can hold far more (FRAGMENT_SHARE). No C2 or sacrum label in the release holds 1 to 199
# voxels, so the floor moves no study into or out of the whole count.
MIN_VOXELS = 200

# A clear space wider than 20 mm between consecutive labels, more than any disc, holds a body that
# carries no label. The bound only keeps false alarms out: the widest space between consecutive
# labels in the release's whole spines is 5 mm, yet a body dropped from a strict spine leaves a
# space over 20 mm in 2% of cases, and never above T11, because neighbouring levels overlap head to
# foot. A label shift that hides a body above T11 is caught by the rib tally (rib k leads on Tk).
UNLABELLED_GAP_MM = 20.0
# Below this label a space lies where lumbar bodies are (a thirteenth rib-bearing body is named L1
# by this scheme), so a body in it is a missing or extra lumbar label, which the owner's rule keeps.
LUMBAR_SPACE_FROM = T12

# A space wider than this, too narrow to leave a study out, lists a whole study for a look: twice
# the widest space between neighbours in the release's whole spines, and below what a dropped body
# leaves in a fifth of the cases where it can be seen at all.
LOOK_GAP_MM = 10.0

# Where L5 has no label, every label from L4 down must overlap the next head to foot by at least
# 5 mm, as an L5 overlaps the sacrum: the shallowest L5-to-sacrum overlap among the release's
# 1,450 strict spines with no L6 is 5.0 mm, while the 40 no-L5 spines overlap by 9 mm or more. The
# rule leaks: were the L5 label taken off a strict spine whose body stays, 74 of those 1,450 would
# still pass, because L4 often reaches past a short L5 into the sacrum (count_step reports the leak
# as gaps.no_l5_rule_leak). A no-L5 spine that fails the bound is still whole, by the owner's rule,
# and is listed as one that may hold an unlabelled L5.
NO_L5_MEETS_MM = -5.0

# An L5 label under a quarter of L4's voxels, over an L4 that overlaps the sacrum as an L5 would, is
# the no-L5 pattern with a sliver of a body left behind (a whole L5 holds about as much as L4). Such
# a spine stays strict, as the reference count of 1,517 and 40 has it, and is listed for a look.
FRAGMENT_SHARE = 0.25

# A rib counts as present at 50 voxels or more, the rule of the first rib count. A rib is thin,
# and a short twelfth rib on 5 mm slices holds a few hundred voxels, so the 200-voxel floor of a
# body would drop real ribs: 27 rib labels in the release hold 50 to 199 voxels, none fewer.
RIB_MIN_VOXELS = 50

# The lowest rib on each side is tallied, not touched once. A rib's head sits on the disc between
# two bodies, so the body nearest one point of the head is off by one as often as not. Every rib
# voxel within 3 mm of the spine is tallied instead by the label of the spine voxel nearest it, and
# the costotransverse joint tips the tally to the rib's own vertebra (the repair record's compare.py).
CONTACT_MM = 3.0
# The distance map is taken over a box this far around the rib: wide enough to hold every spine
# voxel within CONTACT_MM of the rib, small enough to keep memory low on the 1 mm studies.
MARGIN_MM = 30.0
# A study's two masks lie on one grid when their affines agree to a micrometre: the release writes
# both from one CT, so a real difference is far larger, while a float written twice may differ in
# its last digits.
GRID_TOLERANCE_MM = 1e-3

# At most three processes: the container has four CPUs, and other work runs beside this.
MAX_WORKERS = 3
# Masks go to the processes two at a time: one at a time costs a round trip per mask, and more lets
# one process gather several of the largest masks while the others wait.
JOBS_PER_HANDOFF = 2
# Slices read at a time along the file's last axis, which a NIfTI file stores slowest, so a mask's
# voxels are counted a slab at a time and the mask is never held whole in memory.
SLAB_SLICES = 32

# autoPET's 1,014 studies are 900 persons (Gatidis S et al., Scientific Data 2022;9:601).
AUTOPET_PERSONS = 900
# The first strict studies with no variant, read beside the variants as their reference.
CONTROLS = 100

# The table spells Careggi's name "Azienda Ospedalierio Universitaria Careggi", so sites are
# matched by one word each.
SITE_WORDS = (("autopet", "autoPET"), ("leipzig", "Leipzig"), ("careggi", "Careggi"))
SITE_ORDER = ["autoPET", "Leipzig", "Careggi"]
UNKNOWN_SITE = "unknown"

# The three studies the rules leave out, all Leipzig's, and what the repair of 27 October 2026
# found. "voxels" says whose voxels the repaired mask holds: the readers' own under names a rule
# the ribs settle moved, or a machine's (MOOSE's rerun, checked by rule), and "expect" what the
# rules must read in the repaired mask for it to be the record's truth. Neither kind raises a tier
# until a person checks it, so all three stay gold 4.
REPAIR_RECORD = "/mnt/project-files/enhance-pet-repair"
REPAIRED = {
    "1134": {"published": "no T1 label: the column reads C7, T2 to T12, L1 to L5",
             "truth": "11 rib-bearing vertebrae, T1 to T11, then L1 to L5: a count variant, not a slip",
             "voxels": "readers", "names": "the readers' voxels, names moved by a rule the ribs settle",
             "expect": {"class": "skipped_label", "missing": ["T12"],
                        "reads": "T12 absent: an 11-thoracic count variant"}},
    "1283": {"published": "labels T3 to T11 scrambled, leaving a 39 mm space between labelled T6 and T7",
             "truth": "T1 to T12 in order, then L1 to L5 and the sacrum",
             "voxels": "machine", "names": "MOOSE's rerun, a machine's mask checked by rule",
             "expect": {"class": "strict", "missing": [], "reads": "strict"}},
    "1347": {"published": "no T9 label: its body carries T1 as a second piece",
             "truth": "the lower T1 piece is T9; the lumbosacral junction stays open",
             "voxels": "readers", "names": "the readers' voxels, names moved by a rule the ribs settle",
             "expect": {"class": "strict", "missing": [], "reads": "strict"}},
}
REPAIR_TIER = "gold 4 until a person checks it"


# ---------------------------------------------------------------- reading masks

MASK_ENDINGS = (".nii.gz", ".nii")


def study_id(filename: str) -> str:
    return filename.split(".")[0]


def mask_files(folder: str) -> list:
    files = sorted(f for f in os.listdir(folder) if f.endswith(MASK_ENDINGS))
    twice = sorted(sid for sid, n in Counter(study_id(f) for f in files).items() if n > 1)
    if twice:
        raise ValueError("%s holds more than one mask for %s" % (folder, ", ".join(twice)))
    return files


def mask_path(folder: str, sid: str) -> str:
    for ending in MASK_ENDINGS:
        path = os.path.join(folder, sid + ending)
        if os.path.exists(path):
            return path
    raise FileNotFoundError("%s holds no mask for study %s" % (folder, sid))


def head_foot_axis(affine) -> int:
    """The voxel axis that moves most along the patient's head-foot (world z) axis."""
    return int(np.argmax(np.abs(np.asarray(affine)[2, :3])))


def read_block(img, axis: int, start: int, stop: int) -> np.ndarray:
    """Slices start to stop along `axis`, with that axis moved last. Along the file's last axis
    nibabel reads only the slab; along another it may read more of the file than the block, which
    no mask of the release needs, since every one has its head-foot axis last."""
    index = [slice(None)] * 3
    index[axis] = slice(start, stop)
    return np.moveaxis(np.asanyarray(img.dataobj[tuple(index)]), axis, 2)


def storage_slabs(img):
    """Yield (first slice, block) along the file's last axis, a slab of SLAB_SLICES at a time."""
    n = img.shape[2]
    for start in range(0, n, SLAB_SLICES):
        index = (slice(None), slice(None), slice(start, min(start + SLAB_SLICES, n)))
        yield start, np.asanyarray(img.dataobj[index])


def plane_counts(plane, top_label: int):
    """Voxels of each label 0..top_label in one plane, and how many lie outside the scheme."""
    flat = np.asarray(plane).ravel()
    if flat.dtype.kind == "f":
        flat = np.rint(flat).astype(np.int64)
    outside = 0
    if flat.dtype.kind == "i" and flat.size and flat.min() < 0:
        keep = flat >= 0
        outside = int(flat.size - np.count_nonzero(keep))
        flat = flat[keep]
    counts = np.bincount(flat, minlength=top_label + 1)
    return counts[: top_label + 1], outside + int(counts[top_label + 1:].sum())


def slice_counts(img, axis: int, top_label: int):
    """A table of voxels per slice along `axis` and label, and the voxels outside the scheme.

    The file is read in slabs along its last axis whatever the head-foot axis is: each slab holds
    a share of every head-foot slice when that axis is another, and those shares add up."""
    counts = np.zeros((img.shape[axis], top_label + 1), np.int64)
    outside = 0
    for start, block in storage_slabs(img):
        planes = np.moveaxis(block, axis, 0)
        first = start if axis == 2 else 0
        for j in range(planes.shape[0]):
            plane, extra = plane_counts(planes[j], top_label)
            counts[first + j] += plane
            outside += extra
    return counts, outside


def label_extents(present: np.ndarray, origin: float, step: float) -> dict:
    """Each label's lowest and highest slice centre in head-foot mm, and its number of slices."""
    out = {}
    for label in range(1, present.shape[1]):
        rows = np.flatnonzero(present[:, label])
        if len(rows):
            low, high = sorted([float(origin + step * rows[0]), float(origin + step * rows[-1])])
            out[str(label)] = [round(low, 3), round(high, 3), int(len(rows))]
    return out


def tilt_mm(affine, shape, axis: int) -> float:
    """How far head-foot position moves across one slice; zero for an axial grid."""
    others = [j for j in range(3) if j != axis]
    return round(float(sum(abs(affine[2, j]) * (shape[j] - 1) for j in others)), 3)


def labels_in(present_row: np.ndarray) -> list:
    return [int(label) for label in np.flatnonzero(present_row) if label]


def mask_extents(path: str) -> dict:
    img = nib.load(path, keep_file_open=True)
    affine = np.asarray(img.affine, float)
    axis = head_foot_axis(affine)
    counts, outside = slice_counts(img, axis, TOP_VERTEBRA_LABEL)
    step, origin = float(affine[2, axis]), float(affine[2, 3])
    present = counts > 0
    top = counts.shape[0] - 1 if step > 0 else 0
    bottom = counts.shape[0] - 1 - top
    voxels = counts.sum(0)
    return {
        "shape": [int(n) for n in img.shape[:3]],
        "zooms": [round(float(z), 4) for z in img.header.get_zooms()[:3]],
        "dtype": str(img.get_data_dtype()),
        "slice_axis": axis,
        "slice_mm": round(abs(step), 3),
        "tilt_mm": tilt_mm(affine, img.shape, axis),
        "voxels": {str(label): int(voxels[label]) for label in range(1, TOP_VERTEBRA_LABEL + 1)
                   if voxels[label]},
        "outside_scheme_voxels": outside,
        "extent_mm": label_extents(present, origin, step),
        "top_labels": labels_in(present[top]),
        "bottom_labels": labels_in(present[bottom]),
    }


def _extents_job(job):
    folder, name = job
    return study_id(name), mask_extents(os.path.join(folder, name))


def run_jobs(function, jobs: list, workers: int) -> list:
    """Run `function` over `jobs` in order, in at most MAX_WORKERS processes."""
    workers = max(1, min(workers, MAX_WORKERS))
    if workers == 1:
        return [function(job) for job in jobs]
    out = []
    with Pool(workers) as pool:
        for i, result in enumerate(pool.imap(function, jobs, chunksize=JOBS_PER_HANDOFF)):
            out.append(result)
            if (i + 1) % 100 == 0:
                print("%d of %d" % (i + 1, len(jobs)), file=sys.stderr, flush=True)
    return out


def extents_step(maskdir: str, workers: int = MAX_WORKERS) -> dict:
    jobs = [(maskdir, name) for name in mask_files(maskdir)]
    studies = dict(run_jobs(_extents_job, jobs, workers))
    return {"maskdir": os.path.abspath(maskdir), "label_names": LABEL_NAMES, "studies": studies}


# ---------------------------------------------------------------- the study table

XLSX = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
OFFICE_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PACKAGE_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def shared_strings(book: zipfile.ZipFile) -> list:
    if "xl/sharedStrings.xml" not in book.namelist():
        return []
    root = ET.fromstring(book.read("xl/sharedStrings.xml"))
    # A string is its own text or its runs' text; phonetic runs (rPh) are not part of it.
    return ["".join(t.text or "" for t in item.findall(XLSX + "t") + item.findall("%sr/%st" % (XLSX, XLSX)))
            for item in root.findall(XLSX + "si")]


def first_sheet_path(book: zipfile.ZipFile) -> str:
    workbook = ET.fromstring(book.read("xl/workbook.xml"))
    sheet = workbook.find("%ssheets/%ssheet" % (XLSX, XLSX))
    rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
    target = next(rel.get("Target") for rel in rels.findall(PACKAGE_REL + "Relationship")
                  if rel.get("Id") == sheet.get(OFFICE_REL + "id"))
    return target.lstrip("/") if target.startswith("/") else "xl/" + target


def cell_value(cell, strings: list):
    kind, value = cell.get("t"), cell.find(XLSX + "v")
    if kind == "inlineStr":
        return "".join(t.text or "" for t in cell.iter(XLSX + "t"))
    if value is None or value.text is None:
        return None
    return strings[int(value.text)] if kind == "s" else value.text


def sheet_rows(path: str) -> list:
    """Each row of the first sheet as {column letters: value}."""
    with zipfile.ZipFile(path) as book:
        strings = shared_strings(book)
        root = ET.fromstring(book.read(first_sheet_path(book)))
    rows = []
    for row in root.iter(XLSX + "row"):
        cells = {re.match(r"[A-Z]+", cell.get("r")).group(0): cell_value(cell, strings)
                 for cell in row.findall(XLSX + "c")}
        rows.append(cells)
    return rows


def short_site(raw) -> str:
    text = (raw or "").lower()
    return next((short for word, short in SITE_WORDS if word in text), UNKNOWN_SITE)


def sites_step(xlsx: str) -> dict:
    """Column A the study id, column B the site; rows with no id (UC Davis's 86) are counted."""
    rows = sheet_rows(xlsx)
    header, body = rows[0], rows[1:]
    sites, blank = {}, 0
    for cells in body:
        sid = (cells.get("A") or "").strip()
        if not sid:
            blank += 1
            continue
        sites[sid] = (cells.get("B") or "").strip()
    return {"xlsx": os.path.abspath(xlsx), "header": [header.get("A"), header.get("B")],
            "blank_rows": blank, "sites": sites,
            "short": {sid: short_site(raw) for sid, raw in sites.items()}}


# ---------------------------------------------------------------- the rules

def present_levels(voxels: dict) -> set:
    return {int(label) for label, n in voxels.items() if n >= MIN_VOXELS}


def gap_mm(extent: dict, upper: int, lower: int) -> float:
    """mm from the lower edge of `upper` to the upper edge of `lower`; negative where they overlap."""
    return round(extent[str(upper)][0] - extent[str(lower)][1], 1)


def column_labels(present: set) -> list:
    return [label for label in COLUMN if label in present]


def column_links(study: dict, present: set) -> list:
    labels = column_labels(present)
    return [[upper, lower, gap_mm(study["extent_mm"], upper, lower)] for upper, lower in zip(labels, labels[1:])]


def named_links(links) -> list:
    return [[LABEL_NAMES[upper], LABEL_NAMES[lower], gap] for upper, lower, gap in links]


def out_of_order(study: dict, present: set) -> list:
    """Consecutive labels whose lower level's top lies above the upper level's top."""
    labels, extent = column_labels(present), study["extent_mm"]
    return [[upper, lower] for upper, lower in zip(labels, labels[1:]) if extent[str(upper)][1] < extent[str(lower)][1]]


def names(labels) -> list:
    return [LABEL_NAMES[label] for label in labels]


def lumbar_tail_meets(links: list) -> bool:
    """Whether every link from L4 down overlaps as deeply as an L5 overlaps the sacrum."""
    return all(gap <= NO_L5_MEETS_MM for upper, _, gap in links if upper >= L4)


def l5_fragment(study: dict, present: set) -> bool:
    """An L5 label under FRAGMENT_SHARE of L4's voxels, over an L4 that meets the sacrum."""
    if not {L4, L5, SACRUM} <= present:
        return False
    voxels = study["voxels"]
    small = voxels[str(L5)] < FRAGMENT_SHARE * voxels[str(L4)]
    return bool(small and gap_mm(study["extent_mm"], L4, SACRUM) <= NO_L5_MEETS_MM)


def spans_missing(link: list, missing: list) -> bool:
    """Whether a link between two labels passes over a label that is missing, whose body may fill it."""
    upper, lower, _ = link
    return any(upper < label < lower for label in missing)


def class_of(missing: list, wide: list, links: list) -> str:
    if any(label < L1 for label in missing):
        return "skipped_label"
    if any(upper < LUMBAR_SPACE_FROM for upper, _, _ in wide):
        return "unlabelled_body"
    if not missing and not wide:
        return "strict"
    if missing == [L5] and not wide and lumbar_tail_meets(links):
        return "no_l5"
    return "lumbar_look"


def classify(study: dict) -> dict:
    """One study's class by the rules in the module's docstring, with what decided it."""
    present = present_levels(study["voxels"])
    if C2 not in present:
        return {"class": "no_c2"}
    if SACRUM not in present:
        return {"class": "no_sacrum"}
    missing = [label for label in STRICT_LEVELS if label not in present]
    links = column_links(study, present)
    wide = [link for link in links if link[2] > UNLABELLED_GAP_MM]
    extent = study["extent_mm"]
    return {
        "class": class_of(missing, wide, links),
        "missing": names(missing),
        "wide_gaps": named_links(wide),
        "look_gaps": named_links(link for link in links if LOOK_GAP_MM < link[2] <= UNLABELLED_GAP_MM
                                 and not spans_missing(link, missing)),
        "lumbosacral_gap_mm": links[-1][2],
        "l4_to_sacrum_mm": gap_mm(extent, L4, SACRUM) if L4 in present else None,
        "l6": L6 in present,
        "l5_fragment": l5_fragment(study, present),
        "links_from_l4": named_links(link for link in links if link[0] >= L4),
        "c2_in_top_slice": C2 in study["top_labels"],
        "out_of_order": [names(pair) for pair in out_of_order(study, present)],
    }


def lumbar_look_tags(row: dict) -> list:
    tags = []
    if row["missing"] == [LABEL_NAMES[L5]]:
        tags.append("no L5 label, L4-to-sacrum gap %s mm: may hold an unlabelled L5, look"
                    % row["l4_to_sacrum_mm"])
    elif row["missing"]:
        tags.append("%s label missing: look" % ", ".join(row["missing"]))
    tags += ["a space of %s mm between %s and %s: may hold an unlabelled body, look" % (gap, upper, lower)
             for upper, lower, gap in row["wide_gaps"]]
    return tags


def variants_of(row: dict) -> list:
    """What a whole study is listed for, beside being counted: a lumbar variant or a look."""
    tags = []
    if row["class"] == "no_l5":
        tags.append("no L5 label, an L6 in its place" if row["l6"] else "no L5 label, L4 meeting the sacrum")
    elif row["l6"]:
        tags.append("L6 named")
    if row["class"] == "lumbar_look":
        tags += lumbar_look_tags(row)
    if row["l5_fragment"]:
        tags.append("L5 label a fragment, L4 meeting the sacrum: look")
    tags += ["a space of %s mm between %s and %s: look" % (gap, upper, lower)
             for upper, lower, gap in row["look_gaps"]]
    return tags


# ---------------------------------------------------------------- the repair record

class RepairRecordError(RuntimeError):
    """The repair record is missing a mask, or a mask is not the one its hashes name."""


def file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_sha256sums(path: str) -> dict:
    sums = {}
    with open(path) as handle:
        for line in handle:
            if line.strip():
                digest, name = line.split(None, 1)
                sums[name.strip().lstrip("*")] = digest.lower()
    return sums


def repaired_mask(record: str, sums: dict, sid: str) -> str:
    name = "repaired/%s.nii.gz" % sid
    path = os.path.join(record, name)
    if not os.path.exists(path):
        raise RepairRecordError("the repair record %s has no %s" % (record, name))
    if name not in sums:
        raise RepairRecordError("%s/SHA256SUMS lists no %s" % (record, name))
    if file_sha256(path) != sums[name]:
        raise RepairRecordError("%s is not the mask %s/SHA256SUMS names" % (path, record))
    return name


def read_repairs(record: str = REPAIR_RECORD) -> dict:
    """Each repaired mask of the record, checked against its hash and classified by the rules."""
    sums_path = os.path.join(record, "SHA256SUMS")
    if not os.path.exists(sums_path):
        raise RepairRecordError("the repair record %s has no SHA256SUMS" % record)
    sums = read_sha256sums(sums_path)
    studies = {}
    for sid in sorted(REPAIRED):
        name = repaired_mask(record, sums, sid)
        row = classify(mask_extents(os.path.join(record, name)))
        expect = REPAIRED[sid]["expect"]
        found = {"class": row["class"], "missing": row.get("missing", [])}
        studies[sid] = dict(found, file=name, sha256=sums[name], wide_gaps=row.get("wide_gaps", []),
                            matches_record=found == {"class": expect["class"], "missing": expect["missing"]})
    return {"record": os.path.abspath(record), "studies": studies}


# ---------------------------------------------------------------- the count

CLASSES = ("strict", "no_l5", "lumbar_look", "unlabelled_body", "skipped_label", "no_c2", "no_sacrum")


def by_site(ids, short: dict) -> dict:
    counts = Counter(short.get(sid, UNKNOWN_SITE) for sid in ids)
    order = SITE_ORDER + sorted(site for site in counts if site not in SITE_ORDER)
    return {site: counts.get(site, 0) for site in order}


def spread(values: list) -> dict:
    if not values:
        return {"n": 0}
    return {"n": len(values), "min": min(values), "max": max(values),
            "median": round(statistics.median(values), 1)}


def autopet_persons(whole_autopet: int, autopet_studies: int) -> list:
    """The fewest and most persons a number of autoPET studies can be: each repeat is one study."""
    repeats = max(autopet_studies - AUTOPET_PERSONS, 0)
    return [max(whole_autopet - repeats, 0), min(whole_autopet, AUTOPET_PERSONS)]


def class_lists(rows: dict) -> dict:
    lists = {key: [] for key in CLASSES}
    for sid in sorted(rows):
        lists[rows[sid]["class"]].append(sid)
    return lists


def repair_lists(left_out: list, repairs: dict) -> dict:
    studies = repairs["studies"]
    repaired = [sid for sid in left_out if sid in studies and studies[sid]["matches_record"]]
    return {
        "repaired": repaired,
        "repair_does_not_match_record": [sid for sid in left_out if sid in studies and sid not in repaired],
        "left_out_not_repaired": [sid for sid in left_out if sid not in repaired],
        "repair_record_not_left_out": sorted(sid for sid in REPAIRED if sid not in left_out),
    }


def derived_lists(rows: dict, lists: dict, repairs: dict) -> dict:
    whole = sorted(lists["strict"] + lists["no_l5"] + lists["lumbar_look"])
    left_out = sorted(lists["skipped_label"] + lists["unlabelled_body"])
    repair = repair_lists(left_out, repairs)
    after = sorted(whole + repair["repaired"])
    return dict(repair, **{
        "whole": whole,
        "gold_3": whole,
        "l6": [sid for sid in whole if rows[sid]["l6"]],
        "variants": [sid for sid in whole if variants_of(rows[sid])],
        "l5_fragment": [sid for sid in whole if rows[sid]["l5_fragment"]],
        "look_gaps": [sid for sid in whole if rows[sid]["look_gaps"]],
        "left_out": left_out,
        "whole_after_repair": after,
        "whole_after_repair_readers_voxels": [sid for sid in after
                                              if REPAIRED.get(sid, {}).get("voxels", "readers") == "readers"],
        "c2_in_top_slice": [sid for sid in whole if rows[sid]["c2_in_top_slice"]],
        "out_of_order": [sid for sid in whole if rows[sid]["out_of_order"]],
        "out_of_order_left_out": [sid for sid in left_out if rows[sid]["out_of_order"]],
    })


def gap_summaries(extents: dict, rows: dict, lists: dict) -> dict:
    studies = extents["studies"]
    no_l5_direct = [sid for sid in lists["no_l5"] if not rows[sid]["l6"]]
    strict_no_l6 = [sid for sid in lists["strict"] if not rows[sid]["l6"]]
    l4_to_sacrum = [rows[sid]["l4_to_sacrum_mm"] for sid in strict_no_l6]
    return {
        "no_l5_l4_to_sacrum_mm": {sid: rows[sid]["lumbosacral_gap_mm"] for sid in no_l5_direct},
        "no_l5_l4_to_sacrum": spread([rows[sid]["lumbosacral_gap_mm"] for sid in no_l5_direct]),
        "no_l5_l6_in_its_place": [sid for sid in lists["no_l5"] if rows[sid]["l6"]],
        "strict_l4_to_l5": spread([gap_mm(studies[sid]["extent_mm"], L4, L5) for sid in lists["strict"]]),
        "strict_l5_to_sacrum": spread([gap_mm(studies[sid]["extent_mm"], L5, SACRUM) for sid in lists["strict"]]),
        "strict_no_l6_l5_to_sacrum": spread([rows[sid]["lumbosacral_gap_mm"] for sid in strict_no_l6]),
        # How many strict spines with no L6 would pass the no-L5 rule were their L5 body to lose its
        # label: the rule's known leak.
        "no_l5_rule_leak": {"passing": sum(1 for gap in l4_to_sacrum if gap <= NO_L5_MEETS_MM),
                            "of": len(strict_no_l6)},
    }


def contact_ids(lists: dict, derived: dict) -> dict:
    variants = derived["variants"]
    is_variant = set(variants)
    controls = [sid for sid in lists["strict"] if sid not in is_variant][:CONTROLS]
    return {"variants": variants, "left_out": derived["left_out"], "controls": controls}


def rules() -> dict:
    return {"min_voxels": MIN_VOXELS, "unlabelled_gap_mm": UNLABELLED_GAP_MM,
            "lumbar_space_from": LABEL_NAMES[LUMBAR_SPACE_FROM], "look_gap_mm": LOOK_GAP_MM,
            "no_l5_meets_mm": NO_L5_MEETS_MM, "fragment_share": FRAGMENT_SHARE,
            "rib_min_voxels": RIB_MIN_VOXELS, "contact_mm": CONTACT_MM, "margin_mm": MARGIN_MM,
            "autopet_persons": AUTOPET_PERSONS, "controls": CONTROLS, "repair_record": REPAIR_RECORD}


def person_bounds(derived: dict, short: dict, autopet_studies: int) -> dict:
    """autoPET's persons, the other sites' at most (they carry no person id), and the set's."""
    whole = by_site(derived["whole"], short)
    autopet = autopet_persons(whole.get("autoPET", 0), autopet_studies)
    others = sum(n for site, n in whole.items() if site != "autoPET")
    return {"autopet_whole": autopet, "other_sites_whole_at_most": others,
            "gold_3": [autopet[0], autopet[1] + others],
            "autopet_after_repair": autopet_persons(by_site(derived["whole_after_repair"], short).get("autoPET", 0),
                                                    autopet_studies)}


def repaired_rows(rows: dict, derived: dict, repairs: dict) -> dict:
    out = {}
    for sid in derived["repaired"] + derived["repair_does_not_match_record"]:
        record = {key: value for key, value in REPAIRED[sid].items() if key != "expect"}
        out[sid] = dict(record, found=rows[sid]["class"], missing=rows[sid]["missing"],
                        wide_gaps=rows[sid]["wide_gaps"], expect=REPAIRED[sid]["expect"],
                        repaired_mask=repairs["studies"][sid])
    return out


def count_step(extents: dict, sites: dict, repairs: dict) -> dict:
    short = sites["short"]
    rows = {sid: classify(extents["studies"][sid]) for sid in sorted(extents["studies"])}
    for sid, row in rows.items():
        row["site"] = short.get(sid, UNKNOWN_SITE)
        if "missing" in row:
            row["variants"] = variants_of(row)
    lists = class_lists(rows)
    derived = derived_lists(rows, lists, repairs)
    all_lists = dict(lists, **derived)
    # Every list but the record's ids the rules did not leave out, which may name no study at all.
    study_lists = {key: ids for key, ids in all_lists.items() if key != "repair_record_not_left_out"}
    autopet_studies = sum(1 for site in short.values() if site == "autoPET")
    return {
        "rules": rules(),
        "studies_read": len(rows),
        "no_site": sorted(sid for sid in rows if sid not in short),
        "studies_by_site": by_site(rows, short),
        "lists": all_lists,
        "by_site": {key: by_site(ids, short) for key, ids in study_lists.items()},
        "autopet_studies": autopet_studies,
        "persons": person_bounds(derived, short, autopet_studies),
        "repair_record": repairs["record"],
        "repaired": repaired_rows(rows, derived, repairs),
        "gaps": gap_summaries(extents, rows, lists),
        "rib_contact_ids": contact_ids(lists, derived),
        "studies": rows,
    }


# ---------------------------------------------------------------- ribs

def rib_sides(voxels) -> tuple:
    left = [k for k in range(1, RIBS_PER_SIDE + 1) if voxels[LEFT_RIB_BASE + k] >= RIB_MIN_VOXELS]
    right = [k for k in range(1, RIBS_PER_SIDE + 1) if voxels[RIGHT_RIB_BASE + k] >= RIB_MIN_VOXELS]
    return left, right


def contact_tally(vert: np.ndarray, rib: np.ndarray, zooms) -> dict:
    """Rib voxels within CONTACT_MM of the spine, tallied by the label of the spine voxel nearest each."""
    spine = np.isin(vert, CONTACT_LABELS)
    if not spine.any():
        return {}
    dist, near = ndimage.distance_transform_edt(~spine, sampling=zooms, return_indices=True)
    points = np.argwhere(rib & (dist <= CONTACT_MM))
    if not len(points):
        return {}
    nearest = near[:, points[:, 0], points[:, 1], points[:, 2]]
    labels, counts = np.unique(vert[nearest[0], nearest[1], nearest[2]], return_counts=True)
    return {int(label): int(n) for label, n in zip(labels, counts)}


def rib_box(rib_slices: np.ndarray, pad: np.ndarray, n: int) -> tuple:
    rows = np.flatnonzero(rib_slices)
    return max(int(rows[0]) - int(pad[2]), 0), min(int(rows[-1]) + int(pad[2]) + 1, n)


def rib_contacts(vert_img, rib_img, axis: int, rib_slices: np.ndarray, label: int, zooms) -> dict:
    """The contact tally of one rib, over a box MARGIN_MM around it."""
    pad = np.ceil(MARGIN_MM / zooms).astype(int)
    z0, z1 = rib_box(rib_slices, pad, rib_img.shape[axis])
    rib = read_block(rib_img, axis, z0, z1) == label
    xy = np.argwhere(rib.any(axis=2))
    x0, y0 = np.maximum(xy.min(0) - pad[:2], 0)
    x1, y1 = np.minimum(xy.max(0) + pad[:2] + 1, rib.shape[:2])
    vert = read_block(vert_img, axis, z0, z1)[x0:x1, y0:y1]
    return contact_tally(vert, rib[x0:x1, y0:y1], zooms)


def meeting(tally: dict):
    """The label with the most contacts; a tie goes to the head-most label, and is marked."""
    if not tally:
        return None, False
    best = max(tally.values())
    leaders = sorted(label for label, n in tally.items() if n == best)
    return leaders[0], len(leaders) > 1


def same_grid(first, second) -> bool:
    return first.shape[:3] == second.shape[:3] and np.allclose(first.affine, second.affine, atol=GRID_TOLERANCE_MM)


def lowest_rib_contacts(mask_file: str, rib_img, axis: int, counts: np.ndarray, sides: tuple) -> dict:
    vert_img = nib.load(mask_file, keep_file_open=True)
    if not same_grid(vert_img, rib_img):
        return {"error": "the vertebra and rib masks lie on different grids"}
    zooms = np.array(rib_img.header.get_zooms()[:3], float)
    zooms = np.concatenate([np.delete(zooms, axis), zooms[axis:axis + 1]])
    out = {}
    for side, have, base in (("left", sides[0], LEFT_RIB_BASE), ("right", sides[1], RIGHT_RIB_BASE)):
        if have:
            rib = max(have)
            tally = rib_contacts(vert_img, rib_img, axis, counts[:, base + rib], base + rib, zooms)
            meets, tie = meeting(tally)
            out[side] = {"lowest_rib": rib, "contacts": {str(label): n for label, n in sorted(tally.items())},
                         "meets": meets, "meets_name": LABEL_NAMES.get(meets), "tie": tie}
    return out


def rib_study(job) -> tuple:
    sid, maskdir, ribdir, with_contacts = job
    rib_img = nib.load(mask_path(ribdir, sid), keep_file_open=True)
    axis = head_foot_axis(rib_img.affine)
    counts, outside = slice_counts(rib_img, axis, TOP_RIB_LABEL)
    voxels = counts.sum(0)
    left, right = rib_sides(voxels)
    row = {"voxels": {str(label): int(voxels[label]) for label in range(1, TOP_RIB_LABEL + 1) if voxels[label]},
           "outside_scheme_voxels": outside, "left": left, "right": right,
           "pairs": len(set(left) & set(right)), "asymmetric": left != right,
           "lowest": {"left": max(left) if left else None, "right": max(right) if right else None}}
    if with_contacts:
        row["contacts"] = lowest_rib_contacts(mask_path(maskdir, sid), rib_img, axis, counts, (left, right))
    return sid, row


def read_ids(spec: str, ribdir: str) -> dict:
    """Named groups of study ids: `all`, or a JSON list, an object of lists, or a count's output."""
    if spec == "all":
        return {"all": [study_id(f) for f in mask_files(ribdir)]}
    with open(spec) as handle:
        data = json.load(handle)
    if isinstance(data, dict) and "rib_contact_ids" in data:
        data = data["rib_contact_ids"]
    if isinstance(data, list):
        data = {"ids": data}
    return {group: [str(sid) for sid in ids] for group, ids in sorted(data.items())}


def ribs_step(maskdir: str, ribdir: str, ids_spec: str, pairs_only: bool = False,
              workers: int = MAX_WORKERS) -> dict:
    groups = read_ids(ids_spec, ribdir)
    ids = sorted({sid for members in groups.values() for sid in members})
    jobs = [(sid, maskdir, ribdir, not pairs_only) for sid in ids]
    return {"rules": rules(), "groups": groups, "contacts_read": not pairs_only,
            "studies": dict(run_jobs(rib_study, jobs, workers))}


# ---------------------------------------------------------------- the report

def merge_ribs(files: list) -> dict:
    """Studies from several rib outputs; a later file's fields fill in or replace an earlier one's,
    so a pairs-only file never wipes a contact tally another file holds."""
    merged, groups = {}, {}
    for data in files:
        for sid, row in data["studies"].items():
            merged[sid] = dict(merged.get(sid, {}), **row)
        groups.update(data["groups"])
    return {"studies": merged, "groups": groups}


def thousands(n: int) -> str:
    return "{:,}".format(n)


def site_columns(count: dict) -> list:
    """The three sites, and any other a printed row holds (an id the study table lacks reads unknown)."""
    seen = set()
    for _, counts in count_rows(count["by_site"], count["studies_by_site"]):
        seen.update(site for site, n in counts.items() if n)
    return SITE_ORDER + sorted(seen - set(SITE_ORDER))


def site_row(label: str, counts: dict, columns: list) -> str:
    cells = [thousands(counts.get(site, 0)) for site in columns]
    return "| %s | %s | %s |" % (label, " | ".join(cells), thousands(sum(counts.values())))


def readers_voxels_label() -> str:
    moved = [sid for sid in sorted(REPAIRED) if REPAIRED[sid]["voxels"] == "readers"]
    return "of which keep the readers' voxels (%s under names a rule moved)" % " and ".join(moved)


def count_rows(by_site_lists: dict, studies_by_site: dict) -> list:
    return [
        ("Studies read", studies_by_site),
        ("Whole by the strict rule (C2 to L5 and the sacrum)", by_site_lists["strict"]),
        ("Whole with no L5 label, L4 meeting the sacrum (or an L6 in L5's place)", by_site_lists["no_l5"]),
        ("Whole with a lumbar label missing or a lumbar space, listed for a look", by_site_lists["lumbar_look"]),
        ("**Whole C2 to sacrum, published labels**", by_site_lists["whole"]),
        ("of which name an L6", by_site_lists["l6"]),
        ("**Gold 3: the readers' labels as published**", by_site_lists["gold_3"]),
        ("Left out by the rules, repaired (counted whole after repair)", by_site_lists["repaired"]),
        ("Left out by the rules, not repaired", by_site_lists["left_out_not_repaired"]),
        ("**Whole after repair**", by_site_lists["whole_after_repair"]),
        (readers_voxels_label(), by_site_lists["whole_after_repair_readers_voxels"]),
        ("No C2 label", by_site_lists["no_c2"]),
        ("No sacrum label", by_site_lists["no_sacrum"]),
        ("Whole with C2 in the field's top slice", by_site_lists["c2_in_top_slice"]),
        ("Whole with out-of-order extents, not excluded", by_site_lists["out_of_order"]),
        ("Left out, out of order in the published mask", by_site_lists["out_of_order_left_out"]),
        ("Strict, but the L5 label a fragment over an L4 meeting the sacrum, for a look",
         by_site_lists["l5_fragment"]),
        ("Whole with a space over %s mm between neighbours, for a look" % LOOK_GAP_MM, by_site_lists["look_gaps"]),
    ]


def count_table(count: dict) -> list:
    columns = site_columns(count)
    head = ["| | %s | All |" % " | ".join(columns), "| --- |%s --- |" % (" --- |" * len(columns))]
    rows = count_rows(count["by_site"], count["studies_by_site"])
    return head + [site_row(label, counts, columns) for label, counts in rows]


def person_lines(count: dict) -> list:
    persons, whole = count["persons"], count["by_site"]["whole"]
    low, high = persons["autopet_whole"]
    others = persons["other_sites_whole_at_most"]
    other_sites = " and ".join(site + "'s" for site in site_columns(count) if site != "autoPET" and whole.get(site))
    return [
        "- autoPET's whole studies are %s to %s persons (its %s studies are %s persons, so at most %s repeat a person)."
        % (thousands(low), thousands(high), thousands(count["autopet_studies"]), thousands(AUTOPET_PERSONS),
           thousands(max(count["autopet_studies"] - AUTOPET_PERSONS, 0))),
        "- %s %s whole studies carry no person id, so they are at most %s persons."
        % (other_sites or "The other sites'", thousands(others), thousands(others)),
        "- Gold 3 from this set: %s to %s persons (the lower bound counts autoPET's persons alone)."
        % tuple(thousands(n) for n in persons["gold_3"]),
    ]


def ids_line(label: str, ids: list) -> list:
    return ["- %s: %s." % (label, ", ".join(ids))] if ids else []


def no_l5_line(gaps: dict) -> list:
    no_l5, l4_to_l5 = gaps["no_l5_l4_to_sacrum"], gaps["strict_l4_to_l5"]
    l5_to_sacrum, adjacent = gaps["strict_l5_to_sacrum"], gaps["strict_no_l6_l5_to_sacrum"]
    if not no_l5["n"]:
        return []
    return ["- No L5 label, L4 meeting the sacrum: %d studies, L4-to-sacrum gaps from %s to %s mm (median %s). "
            "In the strict studies L5 to the sacrum has a median of %s mm (%s to %s mm where no L6 lies between, "
            "median %s), and L4 to L5 a median of %s mm."
            % (no_l5["n"], no_l5["min"], no_l5["max"], no_l5["median"], l5_to_sacrum.get("median"),
               adjacent.get("min"), adjacent.get("max"), adjacent.get("median"), l4_to_l5.get("median"))]


def gap_lines(count: dict) -> list:
    gaps, lists = count["gaps"], count["lists"]
    leak = gaps["no_l5_rule_leak"]
    lines = no_l5_line(gaps)
    lines.append("- The no-L5 rule asks every label from L4 down to overlap the next by at least %s mm. It leaks: "
                 "%s of the %s strict spines with no L6 would pass it were their L5 body to lose its label."
                 % (-NO_L5_MEETS_MM, thousands(leak["passing"]), thousands(leak["of"])))
    lines += ids_line("No L5 label, an L6 in its place, meeting L4 above and the sacrum below",
                      gaps["no_l5_l6_in_its_place"])
    lines += ["- %s: %s." % (sid, "; ".join(count["studies"][sid]["variants"])) for sid in lists["lumbar_look"]]
    lines += ids_line("L5 label under a quarter of L4's voxels, L4 meeting the sacrum (strict, for a look)",
                      lists["l5_fragment"])
    lines += ids_line("A space over %s mm between neighbours (whole, for a look)" % LOOK_GAP_MM, lists["look_gaps"])
    lines += ids_line("Whole with out-of-order extents", lists["out_of_order"])
    lines += ids_line("Left out, out of order in the published mask", lists["out_of_order_left_out"])
    return lines


def found_text(row: dict) -> str:
    detail = ", ".join(row["missing"]) or "; ".join("%s to %s: %s mm" % tuple(space) for space in row["wide_gaps"])
    return "%s (%s)" % (row["found"].replace("_", " "), detail) if detail else row["found"].replace("_", " ")


def repaired_reading(row: dict, ribs: dict) -> str:
    mask = row["repaired_mask"]
    text = row["expect"]["reads"] if mask["matches_record"] else "%s, not what the record says" % (
        mask["class"].replace("_", " ") + (" (%s)" % ", ".join(mask["missing"]) if mask["missing"] else ""))
    pairs = ribs["studies"].get(row["sid"], {}).get("pairs")
    return text if pairs is None else "%s; %d rib pairs" % (text, pairs)


def repaired_table(count: dict, ribs: dict) -> list:
    out = ["| Study | Site | The rules found | Published mask | Truth | The repaired mask reads | Its labels | Tier |",
           "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for sid, row in sorted(count["repaired"].items()):
        out.append("| %s | %s | %s | %s | %s | %s | %s | %s |"
                   % (sid, count["studies"][sid]["site"], found_text(row), row["published"], row["truth"],
                      repaired_reading(dict(row, sid=sid), ribs), row["names"], REPAIR_TIER))
    return out


def rib_span(ribs: list) -> str:
    """Rib numbers as runs: [1, 2, 3, 5] reads 1-3, 5."""
    runs, start = [], None
    for i, rib in enumerate(ribs):
        start = rib if start is None else start
        if i + 1 == len(ribs) or ribs[i + 1] != rib + 1:
            runs.append(str(start) if start == rib else "%d-%d" % (start, rib))
            start = None
    return ", ".join(runs) or "none"


def pairs_table(count: dict, ribs: dict) -> list:
    studies, after = ribs["studies"], set(count["lists"]["whole_after_repair"])
    every = Counter(row["pairs"] for row in studies.values())
    whole = Counter(row["pairs"] for sid, row in studies.items() if sid in after)
    out = ["| Rib pairs | Studies read (%s) | Whole after repair (%s) |"
           % (thousands(len(studies)), thousands(sum(whole.values()))), "| --- | --- | --- |"]
    return out + ["| %d | %s | %s |" % (pairs, thousands(every[pairs]), thousands(whole.get(pairs, 0)))
                  for pairs in sorted(every)]


def asymmetric_line(ribs: dict) -> list:
    rows = [(sid, row) for sid, row in sorted(ribs["studies"].items()) if row["left"] != row["right"]]
    if not rows:
        return []
    listed = "; ".join("%s (left %s, right %s)" % (sid, rib_span(row["left"]), rib_span(row["right"]))
                       for sid, row in rows)
    counted = "1 study has" if len(rows) == 1 else "%d studies have" % len(rows)
    return ["", "%s different ribs on the two sides, so a rib missing from one side's labels counts as a missing "
            "pair above: %s." % (counted, listed)]


# The contact table's rows. A study is read from the sides whose lowest rib touches the spine: its
# own vertebra (rib k on Tk, rib 13 on L1), one level off, or further; nothing where neither touches.
ONE_OFF, FURTHER_OFF = "a label one level off", "a label further off"
NOTHING, NO_RIB, UNREADABLE = "no spine label within %s mm" % CONTACT_MM, "no rib on either side", "masks unreadable"
FIXED_ROWS = (ONE_OFF, FURTHER_OFF, NOTHING, NO_RIB, UNREADABLE)
# The lowest ribs most spines have come first, as the holdings note lays the table out.
COMMON_LOWEST = (12, 11, 13)


def own_vertebra(rib: int) -> int:
    return rib + OWN_VERTEBRA_OFFSET


def side_reading(side: dict) -> str:
    if side["meets"] is None:
        return "nothing"
    off = abs(side["meets"] - own_vertebra(side["lowest_rib"]))
    return "own" if off == 0 else "one off" if off == 1 else "further off"


def own_row(ribs: list) -> tuple:
    if len(ribs) == 1:
        rib = ribs[0]
        rank = COMMON_LOWEST.index(rib) if rib in COMMON_LOWEST else len(COMMON_LOWEST) + rib
        return (0, rank), "rib %d on %s" % (rib, LABEL_NAMES[own_vertebra(rib)])
    return (1, ribs[0], ribs[1]), "rib %d on %s on one side, rib %d on %s on the other" % (
        ribs[0], LABEL_NAMES[own_vertebra(ribs[0])], ribs[1], LABEL_NAMES[own_vertebra(ribs[1])])


def contact_class(contacts: dict) -> tuple:
    """(sort key, row name) of one study in the contact table."""
    if "error" in contacts:
        return (2, FIXED_ROWS.index(UNREADABLE)), UNREADABLE
    sides = [contacts[side] for side in SIDES if side in contacts]
    touching = [side for side in sides if side["meets"] is not None]
    readings = {side_reading(side) for side in touching}
    for reading, row in (("one off", ONE_OFF), ("further off", FURTHER_OFF)):
        if reading in readings:
            return (2, FIXED_ROWS.index(row)), row
    if not touching:
        row = NOTHING if sides else NO_RIB
        return (2, FIXED_ROWS.index(row)), row
    return own_row(sorted({side["lowest_rib"] for side in touching}))


def side_text(name: str, side) -> str:
    if side is None:
        return "%s no rib" % name
    if side["meets"] is None:
        return "%s rib %d meets nothing within %s mm" % (name, side["lowest_rib"], CONTACT_MM)
    return "%s rib %d on %s%s" % (name, side["lowest_rib"], side["meets_name"], ", a tie" if side["tie"] else "")


def plainly_own(contacts: dict) -> bool:
    """Both sides have a lowest rib, each on its own level, with no tie."""
    sides = [contacts.get(name) for name in SIDES]
    return all(side is not None and side["meets"] is not None and not side["tie"]
               and side_reading(side) == "own" for side in sides)


def study_detail(sid: str, contacts: dict) -> str:
    if "error" in contacts:
        return "%s (%s)" % (sid, contacts["error"])
    return "%s (%s)" % (sid, ", ".join(side_text(name, contacts.get(name)) for name in SIDES))


def contact_groups(count: dict) -> list:
    """The variants split by kind, beside the left out and the controls, in the order they are read."""
    lists, rows = count["lists"], count["studies"]
    return [
        ("controls", count["rib_contact_ids"]["controls"]),
        ("no L5 label, L4 meeting the sacrum", [sid for sid in lists["no_l5"] if not rows[sid]["l6"]]),
        ("no L5 label, an L6 in its place", [sid for sid in lists["no_l5"] if rows[sid]["l6"]]),
        ("L6 named below an L5", [sid for sid in lists["l6"] if rows[sid]["class"] == "strict"]),
        ("lumbar label missing or lumbar space, look", lists["lumbar_look"]),
        ("L5 label a fragment, L4 meeting the sacrum", lists["l5_fragment"]),
        ("left out, repaired", lists["repaired"]),
        ("left out, not repaired", lists["left_out_not_repaired"]),
    ]


def read_groups(count: dict, ribs: dict) -> tuple:
    """The groups whose every study has a contact tally, and a line for each read only in part."""
    full, partial = [], []
    for group, ids in contact_groups(count):
        contacts = [ribs["studies"].get(sid, {}).get("contacts") for sid in ids]
        read = [c for c in contacts if c is not None]
        if ids and len(read) == len(ids):
            full.append((group, ids, contacts))
        elif read:
            partial.append("- %s: %d of %d studies tallied, so the group is left out of the table."
                           % (group, len(read), len(ids)))
    return full, partial


def contacts_table(count: dict, ribs: dict) -> list:
    """Rows by where the lowest rib meets the spine, a column per group whose every study was
    tallied, and below it every study not plainly on its own level on both sides, named with both."""
    full, partial = read_groups(count, ribs)
    if not full:
        return partial
    classes = [{sid: contact_class(c) for sid, c in zip(ids, contacts)} for _, ids, contacts in full]
    rows = sorted({key_and_name for per_group in classes for key_and_name in per_group.values()})
    out = ["| Lowest rib meets | %s |" % " | ".join(group for group, _, _ in full),
           "| --- |%s" % (" --- |" * len(full))]
    for key_and_name in rows:
        cells = [str(sum(1 for c in per_group.values() if c == key_and_name)) for per_group in classes]
        out.append("| %s | %s |" % (key_and_name[1], " | ".join(cells)))
    out.append("| Studies | %s |" % " | ".join(str(len(ids)) for _, ids, _ in full))
    notes = contact_details(full, classes) + partial
    return out + ([""] + notes if notes else [])


def contact_details(full: list, classes: list) -> list:
    lines = []
    for (group, ids, contacts), per_group in zip(full, classes):
        named = [study_detail(sid, c) for sid, c in zip(ids, contacts)
                 if "error" in c or per_group[sid][0][0] != 0 or not plainly_own(c)]
        if named:
            lines.append("- %s, every study not plainly on its own level on both sides: %s."
                         % (group, "; ".join(named)))
    return lines


def report(count: dict, ribs: dict) -> str:
    lines = ["## ENHANCE.PET 1.6k: whole spines counted from the published masks", ""]
    lines += count_table(count)
    lines += [""] + person_lines(count) + gap_lines(count)
    lines += ids_line("Studies the study table does not name, counted under unknown", count["no_site"])
    lines += ["", "Left out by the rules and repaired (record: %s/README.md; each repaired mask checked against "
              "its SHA256SUMS and read by the same rules):" % count["repair_record"], ""]
    lines += repaired_table(count, ribs)
    lines += ids_line("Repaired masks that do not read as the record says, not counted whole",
                      count["lists"]["repair_does_not_match_record"])
    if ribs["studies"]:
        lines += ["", "Rib pairs (a rib present at %d voxels or more on both sides):" % RIB_MIN_VOXELS, ""]
        lines += pairs_table(count, ribs) + asymmetric_line(ribs)
        table = contacts_table(count, ribs)
        if table:
            lines += ["", "Where the lowest rib on each side meets the published masks, by the contact tally "
                      "(a study is read from its sides whose lowest rib touches the spine):", ""] + table
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- the command line

def load(path: str) -> dict:
    with open(path) as handle:
        return json.load(handle)


def write(data: dict, path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as handle:
        json.dump(data, handle, indent=1, sort_keys=True)
        handle.write("\n")


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(prog="python -m holdings.count_enhance_pet",
                                      description=__doc__.split("\n")[0])
    steps = command.add_subparsers(dest="step", required=True)
    step = steps.add_parser("extents", help="per mask: voxels and head-foot extents of every label")
    step.add_argument("maskdir"), step.add_argument("out")
    step.add_argument("--workers", type=int, default=MAX_WORKERS)
    step = steps.add_parser("sites", help="the site of every study, from CT-details.xlsx")
    step.add_argument("xlsx"), step.add_argument("out")
    step = steps.add_parser("count", help="the whole C2-to-sacrum count by the rules")
    step.add_argument("extents"), step.add_argument("sites"), step.add_argument("out")
    step.add_argument("--repair-record", default=REPAIR_RECORD,
                      help="the folder holding repaired/ and SHA256SUMS (default %(default)s)")
    step = steps.add_parser("ribs", help="rib pairs and the lowest rib's contacts")
    step.add_argument("maskdir"), step.add_argument("ribdir"), step.add_argument("ids"), step.add_argument("out")
    step.add_argument("--pairs-only", action="store_true", help="count ribs only, with no contact tally")
    step.add_argument("--workers", type=int, default=MAX_WORKERS)
    step = steps.add_parser("report", help="print the Markdown table the holdings note quotes")
    step.add_argument("count"), step.add_argument("ribs", nargs="*")
    return command


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    if args.step == "extents":
        out = extents_step(args.maskdir, args.workers)
        write(out, args.out)
        print("%d masks read" % len(out["studies"]))
    elif args.step == "sites":
        out = sites_step(args.xlsx)
        write(out, args.out)
        print("%d studies, %d blank rows" % (len(out["sites"]), out["blank_rows"]))
    elif args.step == "count":
        out = count_step(load(args.extents), load(args.sites), read_repairs(args.repair_record))
        write(out, args.out)
        print("%d whole, %d after repair" % (len(out["lists"]["whole"]), len(out["lists"]["whole_after_repair"])))
    elif args.step == "ribs":
        out = ribs_step(args.maskdir, args.ribdir, args.ids, args.pairs_only, args.workers)
        write(out, args.out)
        print("%d rib masks read" % len(out["studies"]))
    else:
        sys.stdout.write(report(load(args.count), merge_ribs([load(path) for path in args.ribs])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
