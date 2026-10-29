"""The second, independent reading of ENHANCE.PET's masks, which checks holdings/enhance_facts.py.

Written from the gold tier 3 dataset's plan alone (SchwingNet docs/research/gold3-ct/SPEC.md),
without reading enhance_facts.py or the count, so a fault in one reading shows as a disagreement
with the other (the dataset's check Q14); `compare` sets the two side by side.

    python -m holdings.enhance_facts_check --masks DIR --ribs DIR --out FACTS_B.jsonl [--workers N]
    python -m holdings.enhance_facts_check compare FACTS_A.jsonl FACTS_B.jsonl OUT.json

Confidential, like the rest of this repository. For each study it reads the vertebra mask and the rib
mask and writes one JSON line holding: the voxels of every vertebra label, the
voxels of every rib label, the contact tally of every rib present with its lead,
and the shortest 3-D distance between the spec's label pairs.

Boxes. Every distance transform runs in a crop that provably holds every voxel
that can change the answer, never the whole volume:

- Pair distance a-b: the union of the bounding boxes of a and b. Every voxel of
  b (the features) and every voxel of a (where the minimum is read) lies in it,
  so the EDT of "not b" inside it is exact at every voxel of a.
- Rib contacts: let m_i = floor(3.0 / zoom_i) + 1 voxels. A rib voxel p within
  3.0 mm of a spine voxel q differs from q by at most floor(3.0 / zoom_i) voxels
  on each axis i, so p lies in P = bbox(rib) intersected with bbox(spine)
  grown by m, and q lies in P grown by m. The EDT inside P grown by m therefore
  gives the true distance (and a true nearest voxel) for every rib voxel whose
  true distance is <= 3.0 mm, and a distance > 3.0 mm for every other rib voxel.

A second, transform-free reading (offsets enumerated inside 3.0 mm, nearest
first) recomputes every contact voxel, checks the EDT's distance and label, and
counts the voxels whose nearest spine voxels at the same distance carry
different labels, where any implementation's label is a tie-break.
"""

import argparse
import json
import math
import os
import sys
import time

import nibabel as nib
import numpy as np
from scipy import ndimage

CONTACT_MM = 3.0
CONTACT_LABELS = tuple(range(1, 26)) + (28,)
SACRUM = 28
VERTEBRA_SCHEME_MAX = 28
RIB_SCHEME_MAX = 27
STERNUM = 27
RIB_LABELS = tuple(range(1, 27))
NEIGHBOUR_PAIRS = tuple((k, k + 1) for k in range(1, 25))
SACRUM_PAIRS = tuple((k, SACRUM) for k in range(20, 26))
DISTANCE_PAIRS = NEIGHBOUR_PAIRS + SACRUM_PAIRS
# An EDT over N voxels peaks near 60 bytes a voxel (feature transform, indices,
# float64 distances); 12 M voxels keeps one worker under about 0.8 GB.
EDT_VOXEL_CAP = 12_000_000
LIMIT_EPS_MM = 1e-4


# ---------------------------------------------------------------- reading

def read_raw(path):
    """The stored integers of a NIfTI mask, never scaled, as uint8, and its image.

    Some published masks are stored as int16. Their values are narrowed to uint8
    slab by slab; a value outside 0..255 becomes 255, which keeps it outside both
    label schemes, so the outside-scheme counts stay exact.
    """
    image = nib.load(path)
    data = np.asarray(image.dataobj.get_unscaled())
    if data.dtype == np.uint8:
        return data, image
    if not np.issubdtype(data.dtype, np.integer):
        raise ValueError(f"{path}: dtype {data.dtype}, expected an integer mask")
    narrow = np.empty(data.shape, dtype=np.uint8, order="F")
    for start in range(0, data.shape[2], 32):
        slab = data[:, :, start:start + 32]
        narrow[:, :, start:start + 32] = np.where((slab < 0) | (slab > 255), 255, slab)
    del data
    return narrow, image


def count_values(data, boxes):
    """Voxels of every stored value, each counted inside its own bounding box.

    find_objects gives a box for every value from 1 to the array's maximum that
    occurs, and every voxel of a value lies in its box, so the count is exact;
    a whole-volume bincount gave the same numbers at a hundred times the cost.
    """
    counts = np.zeros(256, dtype=np.int64)
    for value, box in boxes.items():
        counts[value] = np.count_nonzero(data[box_slices(box)] == value)
    counts[0] = data.size - counts[1:].sum()
    return counts


def label_boxes(data):
    """Bounding box (starts, stops) of every label present, from find_objects."""
    # find_objects walks memory in C order; NIfTI arrays come in Fortran order,
    # so it reads the transposed view (four times faster) and the axes turn back.
    flipped = data.flags["F_CONTIGUOUS"] and not data.flags["C_CONTIGUOUS"]
    boxes = {}
    for index, found in enumerate(ndimage.find_objects(data.T if flipped else data)):
        if found is not None:
            found = tuple(reversed(found)) if flipped else found
            boxes[index + 1] = (tuple(s.start for s in found), tuple(s.stop for s in found))
    return boxes


# ---------------------------------------------------------------- boxes

def union_box(boxes):
    starts = tuple(min(b[0][i] for b in boxes) for i in range(3))
    stops = tuple(max(b[1][i] for b in boxes) for i in range(3))
    return starts, stops


def grow_box(box, margin, shape):
    starts = tuple(max(0, box[0][i] - margin[i]) for i in range(3))
    stops = tuple(min(shape[i], box[1][i] + margin[i]) for i in range(3))
    return starts, stops


def intersect_box(first, second):
    starts = tuple(max(first[0][i], second[0][i]) for i in range(3))
    stops = tuple(min(first[1][i], second[1][i]) for i in range(3))
    if any(stops[i] <= starts[i] for i in range(3)):
        return None
    return starts, stops


def shift_box(box, origin):
    return (tuple(box[0][i] - origin[i] for i in range(3)),
            tuple(box[1][i] - origin[i] for i in range(3)))


def box_slices(box):
    return tuple(slice(box[0][i], box[1][i]) for i in range(3))


def box_voxels(box):
    return int(np.prod([box[1][i] - box[0][i] for i in range(3)], dtype=np.int64))


def contact_margin(zooms):
    """Voxels per axis that a 3.0 mm reach can cross, plus one to spare."""
    return tuple(int(math.floor(CONTACT_MM / z)) + 1 for z in zooms)


# ---------------------------------------------------------------- distances

def squared_mm(delta_i, delta_j, delta_k, zooms):
    """Squared length in mm, summed in the order scipy's EDT sums its axes."""
    return ((delta_i * zooms[0]) ** 2 + (delta_j * zooms[1]) ** 2) + (delta_k * zooms[2]) ** 2


def shortest_distance(spine, boxes, a, b, zooms):
    """Shortest distance in mm from a voxel of a to a voxel of b, and the method."""
    box = union_box([boxes[a], boxes[b]])
    if box_voxels(box) <= EDT_VOXEL_CAP:
        crop = spine[box_slices(box)]
        to_b = ndimage.distance_transform_edt(crop != b, sampling=zooms)
        return float(to_b[crop == a].min()), "edt_union_box"
    return boundary_distance(spine, boxes, a, b, zooms), "boundary_pairs"


def boundary_points(spine, box, label):
    """Voxels of label with a 6-neighbour outside it; a nearest pair lies on them."""
    grown = grow_box(box, (1, 1, 1), spine.shape)
    inside = spine[box_slices(grown)] == label
    core = ndimage.binary_erosion(inside, structure=ndimage.generate_binary_structure(3, 1),
                                  border_value=0)
    points = np.nonzero(inside & ~core)
    return [points[i] + grown[0][i] for i in range(3)]


def boundary_distance(spine, boxes, a, b, zooms):
    """Exact shortest distance over boundary voxel pairs, in bounded chunks."""
    pa = boundary_points(spine, boxes[a], a)
    pb = boundary_points(spine, boxes[b], b)
    best = math.inf
    for s in range(0, pa[0].size, 256):
        ca = [p[s:s + 256, None] for p in pa]
        for t in range(0, pb[0].size, 8192):
            cb = [p[None, t:t + 8192] for p in pb]
            d2 = squared_mm((ca[0] - cb[0]).astype(np.float64), (ca[1] - cb[1]).astype(np.float64),
                            (ca[2] - cb[2]).astype(np.float64), zooms)
            best = min(best, float(d2.min()))
    return math.sqrt(best)


# ---------------------------------------------------------------- contacts

def offset_groups(zooms, limit):
    """Every voxel offset within limit mm, grouped by exact distance, nearest first."""
    reach = [int(math.floor(limit / z)) for z in zooms]
    groups = {}
    for di in range(-reach[0], reach[0] + 1):
        for dj in range(-reach[1], reach[1] + 1):
            for dk in range(-reach[2], reach[2] + 1):
                distance = math.sqrt(squared_mm(float(di), float(dj), float(dk), zooms))
                if distance <= limit:
                    groups.setdefault(distance, []).append((di, dj, dk))
    return [(d, groups[d]) for d in sorted(groups)]


def nearest_by_offsets(labels, points, groups):
    """For each point: distance to the nearest nonzero label within the groups'
    reach, and the lowest and highest label among the nearest voxels."""
    n = points[0].size
    best = np.full(n, np.inf)
    lowest = np.zeros(n, dtype=np.uint8)
    highest = np.zeros(n, dtype=np.uint8)
    todo = np.arange(n)
    shape = labels.shape
    for distance, offsets in groups:
        if todo.size == 0:
            break
        low = np.full(todo.size, 255, dtype=np.uint8)
        high = np.zeros(todo.size, dtype=np.uint8)
        for offset in offsets:
            seen = gather(labels, [points[i][todo] + offset[i] for i in range(3)], shape)
            low = np.where(seen > 0, np.minimum(low, seen), low)
            high = np.maximum(high, seen)
        found = high > 0
        hit = todo[found]
        best[hit] = distance
        lowest[hit] = low[found]
        highest[hit] = high[found]
        todo = todo[~found]
    return best, lowest, highest


def gather(labels, where, shape):
    inside = np.ones(where[0].size, dtype=bool)
    for i in range(3):
        inside &= (where[i] >= 0) & (where[i] < shape[i])
    values = np.zeros(where[0].size, dtype=np.uint8)
    values[inside] = labels[where[0][inside], where[1][inside], where[2][inside]]
    return values


def tally(labels):
    values, counts = np.unique(labels, return_counts=True)
    return {int(v): int(c) for v, c in zip(values, counts)}


def lead_of(contacts):
    """The label with most contacts, a tie going to the lowest label and marked."""
    if not contacts:
        return None, 0, False
    top = max(contacts.values())
    winners = sorted(label for label, n in contacts.items() if n == top)
    return winners[0], top, len(winners) > 1


def spine_labels(crop):
    """The crop with every label outside CONTACT_LABELS set to 0."""
    keep = ((crop >= 1) & (crop <= 25)) | (crop == SACRUM)
    return np.where(keep, crop, 0).astype(np.uint8)


def rib_contacts(spine, ribs, rib, rib_box, spine_box, zooms, groups):
    """The contact tally of one rib, its lead, and the offset reading's audit."""
    margin = contact_margin(zooms)
    near = intersect_box(rib_box, grow_box(spine_box, margin, spine.shape))
    empty = {"contacts": {}, "lead": None, "lead_n": 0, "tie": False}
    if near is None:
        return empty, {"crop_voxels": 0}
    box = grow_box(near, margin, spine.shape)
    labels = spine_labels(spine[box_slices(box)])
    points = np.nonzero(ribs[box_slices(box)] == rib)
    if points[0].size == 0 or not labels.any():
        return empty, {"crop_voxels": box_voxels(box)}
    best, lowest, highest = nearest_by_offsets(labels, points, groups)
    audit = {"crop_voxels": box_voxels(box)}
    if box_voxels(box) <= EDT_VOXEL_CAP:
        distance, nearest = ndimage.distance_transform_edt(labels == 0, sampling=zooms,
                                                           return_indices=True)
        d = distance[points]
        label = labels[nearest[0][points], nearest[1][points], nearest[2][points]]
        touching = d <= CONTACT_MM
        audit.update(check_against_offsets(d, label, touching, best, lowest, highest))
        audit["within_1e-4_mm_of_limit"] = int(np.count_nonzero(np.abs(d - CONTACT_MM) <= LIMIT_EPS_MM))
        audit["method"] = "edt_contact_box"
    else:
        touching = best <= CONTACT_MM
        label = lowest
        audit["method"] = "offsets_only"
    contacts = tally(label[touching])
    lead, lead_n, tie = lead_of(contacts)
    tied = touching & (lowest != highest)
    audit["equidistant_voxels"] = int(np.count_nonzero(tied))
    audit["at_limit_voxels"] = int(np.count_nonzero(best == CONTACT_MM))
    if audit["equidistant_voxels"]:
        audit["lead_if_ties_low"] = list(lead_of(tally(lowest[touching])))
        audit["lead_if_ties_high"] = list(lead_of(tally(highest[touching])))
    return {"contacts": {str(k): v for k, v in sorted(contacts.items())},
            "lead": lead, "lead_n": lead_n, "tie": tie}, audit


def check_against_offsets(d, label, touching, best, lowest, highest):
    """Whether the EDT and the offset reading agree on every contact voxel."""
    by_offsets = best <= CONTACT_MM
    same_set = bool(np.array_equal(touching, by_offsets))
    same_distance = bool(np.array_equal(d[touching], best[touching])) if same_set else False
    plain = touching & (lowest == highest)
    same_label = bool(np.array_equal(label[plain], lowest[plain]))
    in_range = bool(np.all((label[touching] >= lowest[touching]) & (label[touching] <= highest[touching])))
    return {"offsets_agree": same_set and same_distance and same_label and in_range}


# ---------------------------------------------------------------- one study

def grid_facts(vimage, rimage):
    zooms = tuple(float(z) for z in vimage.header.get_zooms()[:3])
    column_norms = np.sqrt((vimage.affine[:3, :3] ** 2).sum(axis=0))
    same = vimage.shape == rimage.shape and bool(np.allclose(vimage.affine, rimage.affine, atol=1e-4))
    return zooms, {"shape": [int(s) for s in vimage.shape],
                   "dtypes": [str(vimage.get_data_dtype()), str(rimage.get_data_dtype())],
                   "zooms": [round(z, 6) for z in zooms],
                   "same_grid": same,
                   "zoom_vs_affine_max_abs": float(np.abs(column_norms - np.array(zooms)).max())}


def read_vertebrae(path):
    data, image = read_raw(path)
    boxes = label_boxes(data)
    counts = count_values(data, boxes)
    spine_present = [label for label in CONTACT_LABELS if label in boxes]
    spine_box = union_box([boxes[label] for label in spine_present]) if spine_present else None
    return data, image, counts, boxes, spine_box


def study_facts(study_id, masks, ribs_dir):
    vdata, vimage, vcounts, vboxes, spine_box = read_vertebrae(os.path.join(masks, study_id + ".nii.gz"))
    rimage = nib.load(os.path.join(ribs_dir, study_id + ".nii.gz"))
    zooms, grid = grid_facts(vimage, rimage)
    row = {"id": study_id,
           "labels": {str(v): {"voxels": int(vcounts[v])} for v in range(1, VERTEBRA_SCHEME_MAX + 1)
                      if vcounts[v] > 0},
           "outside_scheme_voxels": {"vertebrae": int(vcounts[VERTEBRA_SCHEME_MAX + 1:].sum())}}
    audit = {"grid": grid}
    if spine_box is None:
        crop_box = ((0, 0, 0), tuple(vdata.shape))
    else:
        crop_box = grow_box(spine_box, contact_margin(zooms), vdata.shape)
    spine = np.ascontiguousarray(vdata[box_slices(crop_box)])
    del vdata
    rdata, _ = read_raw(os.path.join(ribs_dir, study_id + ".nii.gz"))
    rboxes = label_boxes(rdata)
    rcounts = count_values(rdata, rboxes)
    rib_crop = np.ascontiguousarray(rdata[box_slices(crop_box)]) if grid["same_grid"] else None
    del rdata
    row["sternum_voxels"] = int(rcounts[STERNUM])
    row["outside_scheme_voxels"]["ribs"] = int(rcounts[RIB_SCHEME_MAX + 1:].sum())
    local = {k: shift_box(b, crop_box[0]) for k, b in vboxes.items() if k in CONTACT_LABELS}
    row["distances_mm"], audit["distance_methods"] = pair_distances(spine, local, zooms)
    row["ribs"], audit["ribs"] = all_rib_contacts(spine, rib_crop, rcounts, rboxes, spine_box,
                                                  crop_box, zooms)
    audit["spine_crop_voxels"] = box_voxels(crop_box)
    row["b_audit"] = audit
    return row


def pair_distances(spine, boxes, zooms):
    distances, odd_methods = {}, {}
    for a, b in DISTANCE_PAIRS:
        if a in boxes and b in boxes:
            value, method = shortest_distance(spine, boxes, a, b, zooms)
            distances[f"{a}-{b}"] = round(value, 1)
            if method != "edt_union_box":
                odd_methods[f"{a}-{b}"] = method
    return distances, odd_methods


def all_rib_contacts(spine, rib_crop, rcounts, rboxes, spine_box, crop_box, zooms):
    groups = offset_groups(zooms, CONTACT_MM)
    ribs, audits = {}, {}
    for rib in RIB_LABELS:
        if rcounts[rib] == 0:
            continue
        entry = {"voxels": int(rcounts[rib])}
        if rib_crop is None:
            entry.update({"contacts": None, "lead": None, "lead_n": 0, "tie": False})
            audits[str(rib)] = {"method": "not_same_grid"}
        elif spine_box is None:
            entry.update({"contacts": {}, "lead": None, "lead_n": 0, "tie": False})
        else:
            local_rib = shift_box(rboxes[rib], crop_box[0])
            local_spine = shift_box(spine_box, crop_box[0])
            clipped = intersect_box(local_rib, ((0, 0, 0), spine.shape))
            if clipped is None:
                entry.update({"contacts": {}, "lead": None, "lead_n": 0, "tie": False})
            else:
                tally_entry, audit = rib_contacts(spine, rib_crop, rib, clipped, local_spine,
                                                  zooms, groups)
                entry.update(tally_entry)
                audits[str(rib)] = audit
        ribs[str(rib)] = entry
    return ribs, audits


# ---------------------------------------------------------------- driver

def safe_study(args):
    study_id, masks, ribs_dir = args
    start = time.time()
    try:
        row = study_facts(study_id, masks, ribs_dir)
    except Exception as error:  # a broken study is recorded, never silently dropped
        row = {"id": study_id, "error": f"{type(error).__name__}: {error}"}
    return row, time.time() - start, peak_rss_mb()


def peak_rss_mb():
    with open("/proc/self/status") as status:
        for line in status:
            if line.startswith("VmHWM:"):
                return int(line.split()[1]) // 1024
    return -1


def partial_lines(partial):
    """Each study's last whole row in a partial file, as written. A run cut short may leave its last
    line unfinished; such a line does not parse and is skipped, as the first reading skips it."""
    lines = {}
    if not os.path.exists(partial):
        return lines
    with open(partial) as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict) and "id" in row:
                lines[row["id"]] = (row, line.strip())
    return lines


def done_ids(partial):
    """The studies an earlier run read whole; a study whose row records an error is read again."""
    return {sid for sid, (row, _) in partial_lines(partial).items() if "error" not in row}


def end_last_line(partial):
    """Close a line a cut-short run left unfinished, so the next row starts a line of its own."""
    if not os.path.exists(partial) or not os.path.getsize(partial):
        return
    with open(partial, "rb") as handle:
        handle.seek(-1, os.SEEK_END)
        ended = handle.read(1) == b"\n"
    if not ended:
        with open(partial, "a") as handle:
            handle.write("\n")


def finish(partial, output):
    """Write each study's last row, sorted by id; return the rows and how many record an error."""
    lines = partial_lines(partial)
    with open(output, "w") as handle:
        for study_id in sorted(lines):
            handle.write(lines[study_id][1] + "\n")
    return len(lines), sum(1 for row, _ in lines.values() if "error" in row)


# ---------------------------------------------------------------- the comparison

# Both readings round a distance to 0.1 mm; a true distance on a rounding edge may round either way
# in two programs, so distances agree within one step of the rounding.
DISTANCE_STEP_MM = 0.1
# The one field two sound readings may differ on; any other is a fault in one of them.
ALLOWED_TO_DIFFER = ("rib_contacts",)


def read_rows(path):
    with open(path) as handle:
        return {row["id"]: row for row in (json.loads(line) for line in handle if line.strip())}


def label_voxels(row):
    return {label: facts["voxels"] for label, facts in row.get("labels", {}).items()}


def rib_field(row, field):
    return {rib: facts.get(field) for rib, facts in row.get("ribs", {}).items()}


def leads(row):
    return rib_field(row, "lead"), rib_field(row, "tie")


def distances_agree(first, second):
    return set(first) == set(second) and all(abs(first[k] - second[k]) <= DISTANCE_STEP_MM + 1e-9 for k in first)


def limit_voxels(audit):
    """How many of a rib's voxels lie at the contact limit, each counted once. at_limit_voxels counts
    the offset reading's distance at exactly CONTACT_MM, within_1e-4_mm_of_limit the distance
    transform's within LIMIT_EPS_MM of it; where the two readings agree on every contact voxel the
    first are among the second, so the larger is their union, and otherwise the union is at most
    their sum."""
    at_limit = audit.get("at_limit_voxels", 0)
    within = audit.get("within_1e-4_mm_of_limit", 0)
    return max(at_limit, within) if audit.get("offsets_agree") else at_limit + within


def contacts_moved(a, b):
    """For each rib whose two tallies differ, [counts moved, counts the second reading's audit lets
    move]: a voxel equally near two labels moves one count from one label to the other, two in all,
    and a voxel at the contact limit may fall on either side of it, one."""
    audits = b.get("b_audit", {}).get("ribs", {})
    moved = {}
    for rib in sorted(set(a.get("ribs", {})) | set(b.get("ribs", {}))):
        first = a.get("ribs", {}).get(rib, {}).get("contacts") or {}
        second = b.get("ribs", {}).get(rib, {}).get("contacts") or {}
        if first == second:
            continue
        audit = audits.get(rib, {})
        allowed = 2 * audit.get("equidistant_voxels", 0) + limit_voxels(audit)
        moved[rib] = [sum(abs(first.get(k, 0) - second.get(k, 0)) for k in set(first) | set(second)), allowed]
    return moved


def compare_row(a, b):
    """The fields on which two readings of one study differ."""
    moved = contacts_moved(a, b)
    checks = (("label_voxels", label_voxels(a) == label_voxels(b)),
              ("rib_voxels", rib_field(a, "voxels") == rib_field(b, "voxels")),
              ("rib_contacts", not moved),
              ("rib_contacts_unexplained", all(n <= allowed for n, allowed in moved.values())),
              ("rib_leads", leads(a) == leads(b)),
              ("sternum_voxels", a.get("sternum_voxels") == b.get("sternum_voxels")),
              ("distances_mm", distances_agree(a.get("distances_mm", {}), b.get("distances_mm", {}))))
    return [name for name, same in checks if not same]


def compare(path_a, path_b):
    """Study by study, the fields two readings disagree on. The calls read only the leads, so a
    study whose leads differ fails the dataset's Q14; a contact count that differs with the same
    lead is a voxel two spine labels lie at exactly the same distance from. Both readings give such
    a voxel the label scipy's distance transform names, each over its own box, and scipy's choice
    among equally near voxels can differ between boxes; this reading takes the head-most label only
    where its box passes EDT_VOXEL_CAP (b_audit's method offsets_only). A tally may differ only by as
    many counts as this reading's audit lets move (contacts_moved, kept in the result for every study
    whose tallies differ); a larger move is rib_contacts_unexplained, a fault."""
    rows_a, rows_b = read_rows(path_a), read_rows(path_b)
    common = sorted(set(rows_a) & set(rows_b))
    differ = {sid: compare_row(rows_a[sid], rows_b[sid]) for sid in common}
    fields = sorted({field for names in differ.values() for field in names})
    moved = {sid: contacts_moved(rows_a[sid], rows_b[sid]) for sid in common if "rib_contacts" in differ[sid]}
    return {"a": os.path.basename(path_a), "b": os.path.basename(path_b),
            "only_a": sorted(set(rows_a) - set(rows_b)), "only_b": sorted(set(rows_b) - set(rows_a)),
            "studies": len(common), "agree": sum(1 for names in differ.values() if not names),
            "disagree_by_field": {f: sorted(s for s, names in differ.items() if f in names) for f in fields},
            "contacts_moved": moved}


def holds(result):
    """Whether the two readings agree as the dataset needs: every study in both, but the first
    reading's repaired rows (id ending in r), which this reading never makes, and no field but a
    contact count differing, and that only as far as the audit allows (compare says why a count may)."""
    return (not result["only_b"] and all(sid.endswith("r") for sid in result["only_a"])
            and set(result["disagree_by_field"]) <= set(ALLOWED_TO_DIFFER))


def compare_main(argv):
    """Write the comparison, and exit 1 when it does not hold, so a job can stop on it."""
    path_a, path_b, out = argv
    result = compare(path_a, path_b)
    result["holds"] = holds(result)
    with open(out, "w") as handle:
        json.dump(result, handle, indent=1, sort_keys=True)
        handle.write("\n")
    print("%d studies, %d agree; only in A %d, only in B %d; %s" % (
        result["studies"], result["agree"], len(result["only_a"]), len(result["only_b"]),
        "holds" if result["holds"] else "does not hold: " + ", ".join(sorted(result["disagree_by_field"]))),
        flush=True)
    return 0 if result["holds"] else 1


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "compare":
        return compare_main(sys.argv[2:])
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--masks", default="/tmp/claude-0/enh/masks")
    parser.add_argument("--ribs", default="/tmp/claude-0/enh/ribs")
    parser.add_argument("--out", required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--only", nargs="*")
    args = parser.parse_args()
    ids = sorted(name[:-7] for name in os.listdir(args.masks) if name.endswith(".nii.gz"))
    if args.only:
        ids = [i for i in ids if i in set(args.only)]
    partial = args.out + ".partial"
    end_last_line(partial)
    todo = [i for i in ids if i not in done_ids(partial)]
    print(f"{len(ids)} studies, {len(todo)} to do, {args.workers} workers", flush=True)
    started = time.time()
    jobs = [(i, args.masks, args.ribs) for i in todo]
    with open(partial, "a") as sink:
        if args.workers > 1:
            from multiprocessing import Pool
            with Pool(args.workers, maxtasksperchild=40) as pool:
                record(pool.imap_unordered(safe_study, jobs), sink, started)
        else:
            record(map(safe_study, jobs), sink, started)
    rows, errors = finish(partial, args.out)
    print(f"rows {rows} in {time.time() - started:.0f} s", flush=True)
    if errors:
        print(f"{errors} studies could not be read; a rerun reads them again", flush=True)
        return 1
    return 0


def record(results, sink, started):
    for n, (row, seconds, rss) in enumerate(results, 1):
        sink.write(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n")
        sink.flush()
        flag = " ERROR " + row["error"] if "error" in row else ""
        print(f"{n} {row['id']} {seconds:.1f}s rss_peak={rss}MB elapsed={time.time() - started:.0f}s{flag}",
              flush=True)


if __name__ == "__main__":
    sys.exit(main())
