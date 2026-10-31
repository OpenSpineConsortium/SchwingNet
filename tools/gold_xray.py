#!/usr/bin/env python3
"""The QA loop's gold arm: the gold tier CTs as a C-arm sees them, for the kind qaloop_gold
(docs/research/qa-loop-gold/PREREG.md).

The loop names lumbar levels from landmarks projected into a C-arm's frame. Its phantoms are drawn
spines and its real pairs are C-ArmLSpine's typical columns; the gold tiers are CTs of whole spines
whose bones are named: gold tier 3 by a person's annotation (ENHANCE.PET's masks, the rows the
auto-anatomist screen planned, grid/screens/), gold tier 4 by TotalSegmentator where its map agrees
with SPINEPS's on which bone is which (tools/gold4_totalseg_grid.py, the kind concordant). The two
tiers are kept apart: every sample carries its tier in its view's name, so no cell, gate or measure
pools them. This module reads each CT once into a case:

- the oracle's eighteen landmarks of each level of the column (T12 to L5 for a typical column) on the
  CT's own label map, in the CT's world millimetres, a level with a landmark more than OFF_BONE_MM
  from its own bone read as one the oracle could not place (DEVIATIONS.md, item 2); the sacrum's
  top, the mean of its body's voxels within SACRUM_TOP_MM of the head-most along the column, its body
  the voxels within SACRUM_BODY_MM of the nearest it comes to the column's line through the lowest
  level read, since its wings and the processes that meet L5 rise beside and behind L5 above the top
  of its body (DEVIATIONS.md, item 1); and the column's axes, the mean of the oracle's level frames
  (x to the right, y anterior, z up), as the phantoms' are laid out;
- drr_per_view radiographs a view and field (digitally reconstructed): a C-arm pose drawn about the
  anteroposterior or the lateral view as the phantoms' are, the detector's field one of fields_mm (an
  image intensifier's 23 or 30 cm across), its pixels the field over the frame's size, and the CT's
  attenuation (HU + 1000 over 1000: water 1, air 0) summed along each pixel's ray from the source,
  bone bright as the loop reads a real frame, and dark outside the field's circle.

The fingerprint's samples are then drawn from a case: frames_per_view projections a view, each a pose
and a field, the landmarks projected with noise_px of noise, a body seen where its ten body points
fall inside the field's circle, the sacrum in view where its top does. The poses are drawn from the
person alone, so a person's frames are the same in every round and a measure read off them moves only
with the fingerprint. The landmarks' presence is read on the radiographs as the loop reads it on real
frames.

Stand-ins: where the data root holds no case of a tier and the plan allows them (the smoke), typical
phantoms rendered by the vendored phantom and read the same way, with the sacrum's top 15 mm below
their last disc, as the phantoms' anchor is; every case of a stand-in says so.

What leaves this module is arrays in memory and one cache file a case under the folder the caller
names, on the grid. The persons on the test lists are never read, and no path, case or person goes
into the round's record, which holds counts by tier and part and the reasons a case was left out.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# As in tools/train.py: this folder leaves the path so tools/profile.py never shadows the standard
# library's profile; the package, the pinned beethoven-qa and the vendored auto-anatomist join it.
sys.path[0] = str(ROOT / "src")
for _folder in (ROOT / "vendor" / "beethoven-qa" / "src", ROOT / "grid" / "autoanatomist"):
    if str(_folder) not in sys.path:
        sys.path.insert(1, str(_folder))

import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
from collections import Counter  # noqa: E402

import numpy as np  # noqa: E402


def load_tool(name):
    """A module of tools/ by its path, since tools/ is not on the path."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


S = load_tool("qaloop_samples")
G = S.G

TIERS = ("gold3", "gold4")
# The lists of persons nothing here reads (schwingnet.autoanatomist_screen.TEST_LISTS): the project's
# test part and the reserve the latent shape priors hold back for their own test.
TEST_LISTS = ("data/splits/test-persons.json", "data/splits/latent-prior-test-reserve.json")
# Every case is read as a typical column, T12 to L5 over the sacrum: the screen's rows are the gold
# store's normal class, and TotalSegmentator's map has no label for an L6 or a T13. The screen's
# parts, in the words the loop's samples use.
PARTS = {"train": "training", "training": "training", "validation": "validation"}
SACRUM_TOP_MM = 10.0                  # the sacrum's top: its body's voxels within this of the head-most, along the column
SACRUM_BODY_MM = 15.0                 # its body: its voxels within this of the nearest it comes to the column's line
OFF_BONE_MM = 8.0                     # a level with a landmark farther than this from its own bone is read as unplaced
FIELD_MARGIN = 4.0                    # a point counts as seen this many pixels inside the field's circle
DRR_STEP_MM = 2.0                     # the step along each ray
DRR_VOXEL_MM = 2.0                    # the CT brought down by whole blocks to about this before the rays are cast
DRR_ROWS = 16                         # image rows cast at once, which bounds the memory a radiograph takes
KEYS = None                           # the oracle's keys, specs.SEVEN + specs.EXTRA, read where the oracle runs


class CaseRefused(Exception):
    """A case that cannot be read, in words that name no file."""


# ---------------------------------------------------------------- the cases a plan reads

def test_persons():
    """Every person on a test list, which no tier ever reads."""
    out = set()
    for name in TEST_LISTS:
        path = ROOT / name
        if path.is_file():
            out |= {str(r["person"]) for r in json.loads(path.read_text()) if isinstance(r, dict) and r.get("person")}
    return out


def files_named(root):
    """Every NIfTI under root by its name less .nii.gz: {name: [paths]}."""
    found = {}
    for path in sorted(Path(root).rglob("*.nii.gz")):
        found.setdefault(path.name[: -len(".nii.gz")], []).append(path)
    return found


def gold3_rows(spec):
    """The rows of the screen plan gold tier 3 reads its persons and parts from."""
    return json.loads((ROOT / spec["rows_of"]).read_text())["rows"]


def gold3_cases(spec, data_root, tests):
    """Gold tier 3's cases: the rows of the screen plan spec['rows_of'] names (ENHANCE.PET's normal
    class, confirmed by its masks, the test lists and the repeat-scan units already kept apart), each
    CT and label map found once under the data root, else left out with its reason."""
    rows = gold3_rows(spec)
    left = Counter()
    cts = files_named(Path(data_root) / spec["ct"]) if data_root else {}
    labels = {name: [p for p in paths if p.parent.name == spec["labels_folder"]]
              for name, paths in (files_named(Path(data_root) / spec["labels"]) if data_root else {}).items()}
    cases = []
    for row in rows:
        name = row["item"].split(":", 1)[-1]
        found_ct, found_labels = cts.get(name, []), labels.get(name, [])
        if row["person"] in tests:
            left["test list"] += 1
        elif row.get("part") not in PARTS:
            left["no part"] += 1
        elif len(found_ct) != 1 or len(found_labels) != 1:
            left["CT or label map not found once"] += 1
        else:
            cases.append({"tier": "gold3", "item": row["item"], "person": row["person"], "part": PARTS[row["part"]],
                          "type": "typical", "ct": str(found_ct[0]), "labels": str(found_labels[0]),
                          "ids": dict(spec["ids"]), "stand_in": False})
    return cases, left


def gold4_cases(spec, gold4_root, tests, rule, gold3_persons=frozenset()):
    """Gold tier 4's cases: the units of the TotalSegmentator run's records.jsonl that it segmented
    and whose map agrees with SPINEPS's (spec['kinds']), never one marked held_out, never a person on
    a test list or with no person key (unknown is not clean), never a person gold tier 3 reads, so no
    person is in both tiers, each person's part by the split rule."""
    path = Path(gold4_root) / spec["records"] if gold4_root else None
    if path is None or not path.is_file():
        return [], Counter({"no records.jsonl": 1})
    left, cases = Counter(), []
    for line in path.read_text().splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            left["unreadable line"] += 1
            continue
        person = str(r.get("person_key") or "")
        why = "a gold tier 3 person" if person in gold3_persons else gold4_left_out(r, person, spec, tests, Path(gold4_root))
        if why:
            left[why] += 1
            continue
        cases.append({"tier": "gold4", "item": str(r["id"]), "person": person,
                      "part": S.split_part(person, rule, tests), "type": "typical", "ct": str(r["ct"]),
                      "labels": str(Path(gold4_root) / r["labels"]), "ids": dict(spec["ids"]), "stand_in": False})
    return cases, left


def gold4_left_out(r, person, spec, tests, root):
    """Why a gold 4 record is not read, or None."""
    if r.get("status") != "segmented" or not r.get("labels"):
        return "not segmented"
    if r.get("kind") not in spec["kinds"]:
        return f"kind {r.get('kind')}"
    if r.get("held_out"):
        return "held out"
    if not person:
        return "no person key"
    if person in tests:
        return "test list"
    if not os.path.isfile(r.get("ct") or "") or not (root / r["labels"]).is_file():
        return "CT or label map not on disk"
    return None


def person_order(person):
    """A person's place in a tier's cap, from the person alone, so a cap never depends on the others."""
    return hashlib.sha256(f"schwingnet-qaloop-gold|{person}".encode()).hexdigest()


def capped(cases, caps):
    """The cases of the first caps[part] persons of each part, persons in person_order; every case of
    a person kept together. A part caps names no number for is kept whole."""
    out, left = [], Counter()
    for part in sorted({c["part"] for c in cases}):
        mine = [c for c in cases if c["part"] == part]
        persons = sorted({c["person"] for c in mine}, key=person_order)
        cap = (caps or {}).get(part)
        kept = set(persons if cap is None else persons[: int(cap)])
        out += [c for c in mine if c["person"] in kept]
        left[f"over the {part} cap"] += sum(1 for c in mine if c["person"] not in kept)
    return out, +left


def cases_for(spec, data_root, gold4_root):
    """Each tier's cases, {tier: [case]}, and what was left out of each and why: test persons and the
    test part never, every other part as the plan's caps allow."""
    tests = test_persons()
    rule, carm_tests = S.split_rule()
    tests |= carm_tests
    gold3_persons = frozenset(str(r["person"]) for r in gold3_rows(spec["gold3"])) if "gold3" in spec else frozenset()
    out, record = {}, {}
    for tier in TIERS:
        if tier not in spec:
            continue
        if tier == "gold3":
            cases, left = gold3_cases(spec[tier], data_root, tests)
        else:
            cases, left = gold4_cases(spec[tier], gold4_root, tests, rule, gold3_persons)
        left["test part"] += sum(1 for c in cases if c["part"] == "test")
        cases = [c for c in cases if c["part"] in ("training", "validation")]
        cases, over = capped(cases, spec[tier].get("max_persons"))
        out[tier] = cases
        record[tier] = {"cases": len(cases), "persons": {p: len({c["person"] for c in cases if c["part"] == p})
                                                         for p in ("training", "validation")},
                        "left_out": dict(+(left + over))}
    return out, record


# ---------------------------------------------------------------- reading a case

def oracle_keys():
    from autoanatomist import specs
    return tuple(specs.SEVEN + specs.EXTRA)


def as_labels(array):
    """A label map's voxels as whole numbers, rounded where they were stored as floats."""
    a = np.asarray(array)
    return a.astype(np.int16) if np.issubdtype(a.dtype, np.integer) else np.rint(a).astype(np.int16)


def column_levels(kind):
    """The levels a column of the type is named over, as the fingerprint names them."""
    return list(S.TYPE_LEVELS[G.NAMED_AS[kind]])


def read_column(labels, affine, ids, levels):
    """The oracle's landmarks of each level, (levels, 18, 3) in world mm, NaN for a level it did not
    place, and the frames of the levels it placed. A level whose body it placed only in part can
    never show its ten body points in a frame, so it breaks every run at it as an unplaced level does
    and is counted with them (DEVIATIONS.md, item 3); on a twisted column the oracle can take a
    level's frame askew and place its landmarks well off the bone, a misreading no less (item 2)."""
    from autoanatomist.oracle import ChordOracle
    keys = oracle_keys()
    names = {int(ids[lv]): lv for lv in levels if lv in ids}
    readings = {r.level: r for r in ChordOracle(keys).read(labels, affine, names)}
    marks, frames = [], []
    for lv in levels:
        got = readings[lv].landmarks(keys) if lv in readings else None
        if got is not None and not placed(labels, affine, ids[lv], got):
            got = None
        marks.append(np.full((len(G.LANDMARKS), 3), np.nan) if got is None else got)
        if got is not None:
            frames.append(readings[lv].frame)
    return np.array(marks), frames


def placed(labels, affine, label, points):
    """Whether the oracle placed a level: its ten body points all placed, and every point it placed
    on the level's own bone."""
    points = np.asarray(points, float)
    return bool(np.isfinite(points[:S.BODY_POINTS]).all()) and on_bone(labels, affine, label, points)


def on_bone(labels, affine, label, points, within_mm=OFF_BONE_MM):
    """Whether every placed point lies within within_mm of the nearest voxel of its bone. Only the
    voxels within reach of the points are searched, which is all the answer needs: a whole map of
    fine voxels takes seconds a level to search."""
    points = np.asarray(points, float)
    points = points[np.isfinite(points).all(axis=1)]
    if not len(points):
        return True
    A = np.asarray(affine, float)
    inv = np.linalg.inv(A)
    ijk = points @ inv[:3, :3].T + inv[:3, 3]
    reach = within_mm / np.linalg.norm(A[:3, :3], axis=0) + 1.0
    lo = np.maximum(np.floor(ijk.min(axis=0) - reach).astype(int), 0)
    hi = np.minimum(np.ceil(ijk.max(axis=0) + reach).astype(int) + 1, np.asarray(labels.shape[:3]))
    if (hi <= lo).any():
        return False
    near = np.argwhere(labels[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]] == int(label)) + lo
    if not len(near):
        return False
    bone = near @ A[:3, :3].T + A[:3, 3]
    return all(float(((bone - p) ** 2).sum(axis=1).min()) <= within_mm ** 2 for p in points)


def unit(v):
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    if not np.isfinite(n) or n == 0:
        raise CaseRefused("the column's axes cannot be read")
    return v / n


def column_axes(frames):
    """The column's axes as columns (right, anterior, up), from the mean of the levels' frames, made
    orthonormal and right-handed with up kept as read."""
    if not frames:
        raise CaseRefused("the oracle read no level of the column")
    ez = unit(np.mean([f.ez for f in frames], axis=0))
    ex = unit(np.mean([f.ex for f in frames], axis=0) - ez * (np.mean([f.ex for f in frames], axis=0) @ ez))
    ey = np.cross(ez, ex)
    if ey @ np.mean([f.ey for f in frames], axis=0) <= 0:
        raise CaseRefused("the oracle's right and anterior make a mirrored frame")
    return np.column_stack([ex, ey, ez])


def sacrum_top(labels, affine, sacrum_id, ez, through, top_mm=SACRUM_TOP_MM, body_mm=SACRUM_BODY_MM):
    """The sacrum's top: the mean of its body's voxels within top_mm of the head-most, along the
    column. Its body is its voxels within body_mm of the nearest it comes to the column's line through
    the point given, the centre of the lowest level read: on a CT the sacrum's wings and the processes
    that meet L5 rise beside and behind L5 above the top of its body, and the head-most of the whole
    mask is one of them."""
    idx = np.argwhere(labels == int(sacrum_id))
    if not len(idx):
        raise CaseRefused("the label map draws no sacrum")
    world = idx @ np.asarray(affine, float)[:3, :3].T + np.asarray(affine, float)[:3, 3]
    off = world - np.asarray(through, float)
    along = off @ ez
    apart = np.linalg.norm(off - np.outer(along, ez), axis=1)
    body = apart <= apart.min() + body_mm
    along = along[body]
    return world[body][along >= along.max() - top_mm].mean(axis=0)


def lowest_centre(marks):
    """The centre of the lowest level whose body the oracle placed."""
    centres = level_centres(marks)
    placed = np.flatnonzero(np.isfinite(centres).all(axis=1))
    if not len(placed):
        raise CaseRefused("the oracle placed no body of the column")
    return centres[placed[-1]]


def coarse(volume, affine, target_mm=DRR_VOXEL_MM):
    """The volume brought down by whole blocks to about target_mm a voxel along each axis, each block
    its mean, with the affine that places it: a radiograph's rays then cross a few hundred voxels."""
    A = np.asarray(affine, float)
    spacing = np.linalg.norm(A[:3, :3], axis=0)
    f = [max(1, int(round(target_mm / s))) for s in spacing]
    shape = [n // k for n, k in zip(volume.shape[:3], f)]
    if min(shape) < 1:
        raise CaseRefused("the CT is smaller than one block")
    v = np.asarray(volume[: shape[0] * f[0], : shape[1] * f[1], : shape[2] * f[2]], np.float32)
    v = v.reshape(shape[0], f[0], shape[1], f[1], shape[2], f[2]).mean(axis=(1, 3, 5))
    B = A.copy()
    B[:3, :3] = A[:3, :3] * np.asarray(f, float)[None, :]
    B[:3, 3] = A[:3, :3] @ ((np.asarray(f, float) - 1) / 2) + A[:3, 3]
    return v, B


def attenuation(hu):
    """Attenuation relative to water from HU: water 1, air 0, nothing below air."""
    return np.clip((np.asarray(hu, np.float32) + 1000.0) / 1000.0, 0.0, None)


def coarse_attenuation(image, target_mm=DRR_VOXEL_MM, slab=16):
    """A CT file's attenuation brought down by whole blocks as coarse() does, slab outputs of the
    slowest axis at a time from the stored values, so a whole-body CT never stands in memory as
    floats: the stored volume and one slab of floats at once."""
    A = np.asarray(image.affine, float)
    proxy = image.dataobj
    raw = proxy.get_unscaled() if hasattr(proxy, "get_unscaled") else np.asarray(proxy)
    slope = float(getattr(proxy, "slope", 1.0) or 1.0)
    inter = float(getattr(proxy, "inter", 0.0) or 0.0)
    spacing = np.linalg.norm(A[:3, :3], axis=0)
    f = [max(1, int(round(target_mm / s))) for s in spacing]
    shape = [n // k for n, k in zip(raw.shape[:3], f)]
    if min(shape) < 1:
        raise CaseRefused("the CT is smaller than one block")
    out = np.empty(shape, np.float32)
    for k0 in range(0, shape[2], slab):
        k1 = min(k0 + slab, shape[2])
        part = raw[: shape[0] * f[0], : shape[1] * f[1], k0 * f[2]: k1 * f[2]].astype(np.float32) * slope + inter
        out[:, :, k0:k1] = attenuation(part).reshape(shape[0], f[0], shape[1], f[1], k1 - k0, f[2]).mean(axis=(1, 3, 5))
    B = A.copy()
    B[:3, :3] = A[:3, :3] * np.asarray(f, float)[None, :]
    B[:3, 3] = A[:3, :3] @ ((np.asarray(f, float) - 1) / 2) + A[:3, 3]
    return out, B


def ray_span(shape, affine, source, axis):
    """The stretch of the central ray, from the source, that crosses the volume's box, widened so the
    frame's off-axis rays cross it whole too."""
    corners = np.array([[i, j, k] for i in (0, shape[0]) for j in (0, shape[1]) for k in (0, shape[2])], float) - 0.5
    world = corners @ np.asarray(affine, float)[:3, :3].T + np.asarray(affine, float)[:3, 3]
    along = (world - source) @ axis
    return max(float(along.min()) * 0.9, 1.0), float(along.max()) * 1.1


def drr(mu, affine, P, size, step_mm=DRR_STEP_MM, rows=DRR_ROWS):
    """A radiograph through P: each pixel the sum along its ray from the source of the attenuation,
    sampled every step_mm by trilinear interpolation, times the step; (size, size) float32, rows
    running down the frame as G.carm_camera lays them out."""
    from scipy import ndimage
    P = np.asarray(P, float)
    M = np.linalg.inv(P[:, :3])
    source = -M @ P[:, 3]
    centre = M @ np.array([size / 2.0, size / 2.0, 1.0])
    s0, s1 = ray_span(mu.shape, affine, source, centre / np.linalg.norm(centre))
    s = np.arange(s0, s1, step_mm, dtype=np.float32)
    inv = np.linalg.inv(np.asarray(affine, float))
    image = np.zeros((size, size), np.float32)
    cols = np.arange(size, dtype=float) + 0.5
    for r0 in range(0, size, rows):
        rr = np.arange(r0, min(r0 + rows, size), dtype=float) + 0.5
        u, v = np.meshgrid(cols, rr)
        d = np.stack([u.ravel(), v.ravel(), np.ones(u.size)], axis=1) @ M.T
        d /= np.linalg.norm(d, axis=1, keepdims=True)
        start = (source @ inv[:3, :3].T + inv[:3, 3]).astype(np.float32)
        step = (d @ inv[:3, :3].T).astype(np.float32)
        ijk = start[None, None, :] + s[None, :, None] * step[:, None, :]
        vals = ndimage.map_coordinates(mu, ijk.reshape(-1, 3).T, order=1, mode="constant", cval=0.0)
        image[r0:r0 + len(rr)] = vals.reshape(len(rr), size, len(s)).sum(axis=2) * step_mm
    return image


def field_mask(size):
    """The frame's pixels inside the field's circle."""
    c = np.arange(size) + 0.5 - size / 2.0
    return (c[None, :] ** 2 + c[:, None] ** 2) <= (size / 2.0) ** 2


def in_field(uv, size, margin=FIELD_MARGIN):
    """Which points fall inside the field's circle, margin pixels in from its edge."""
    uv = np.asarray(uv, float)
    with np.errstate(invalid="ignore"):
        r = np.linalg.norm(uv - size / 2.0, axis=-1)
        return np.isfinite(r) & (r <= size / 2.0 - margin)


def level_centres(marks):
    """Each level's centre, the mean of its body's landmarks that were read."""
    body = np.asarray(marks, float)[:, :S.BODY_POINTS]
    ok = np.isfinite(body).all(axis=2)
    return np.array([body[i][ok[i]].mean(axis=0) if ok[i].any() else np.full(3, np.nan) for i in range(len(body))])


def draw_frame(rng, case, view, fields_mm, size, pose):
    """One C-arm frame of the case: its projection and its field, the beam aimed at a level the case
    read, with the pose's turns and distances drawn about the view as the phantoms' are."""
    centres = level_centres(case["landmarks"])
    seen = np.flatnonzero(np.isfinite(centres).all(axis=1))
    aim = centres[seen[int(rng.integers(0, len(seen)))]] + rng.normal(0, pose["centre_mm"], 3)
    p = S.draw_pose(rng, pose)
    field = float(fields_mm[int(rng.integers(0, len(fields_mm)))])
    ex, ey, ez = (case["axes"][:, i] for i in range(3))
    K, R, t = G.carm_camera(aim, ex, ey, ez, view, p["yaw"], p["tilt"], p["roll"], p["sod"], p["sdd"], field / size, size)
    return G.projection_matrix(K, R, t), field


def person_rng(person, salt):
    return np.random.default_rng(int(hashlib.sha256(f"{salt}|{person}".encode()).hexdigest()[:16], 16))


def radiographs(case, mu, mu_affine, spec):
    """The case's radiographs: drr_per_view frames a view and field, from poses its person draws."""
    size, pose = int(spec["size"]), dict(S.DEFAULT_POSE, **(spec.get("pose") or {}))
    rng = person_rng(case["person"], "drr")
    out = []
    for view in G.VIEWS:
        for field in spec["fields_mm"]:
            for _ in range(int(spec["drr_per_view"])):
                P, _ = draw_frame(rng, case, view, [field], size, pose)
                image = drr(mu, mu_affine, P, size) * field_mask(size)
                out.append({"view": view, "field": float(field), "P": P, "image": image})
    return out


def read_case(case, spec):
    """One case read: its column's landmarks, sacrum and axes from its label map, then its
    radiographs from its CT."""
    import nibabel as nib
    image = nib.load(case["labels"])
    labels, affine = as_labels(image.dataobj), np.asarray(image.affine, float)
    levels = column_levels(case["type"])
    marks, frames = read_column(labels, affine, case["ids"], levels)
    axes = column_axes(frames)
    sacrum = sacrum_top(labels, affine, case["ids"]["sacrum"], axes[:, 2], lowest_centre(marks))
    del labels
    mu, mu_affine = coarse_attenuation(nib.load(case["ct"]))
    out = dict(case, levels=levels, landmarks=marks, sacrum=sacrum, axes=axes)
    out["frames"] = radiographs(out, mu, mu_affine, spec)
    return out


def stand_in_case(seed, tier, part, spec):
    """A stand-in case: a typical phantom from T12 to L5 rendered and read by the oracle, its sacrum's
    top 15 mm below its last disc, its radiographs cast through the phantom's CT."""
    from autoanatomist import phantom
    rng = np.random.default_rng(seed)
    levels = S.column_of("typical", seed)
    tilt = (tuple(float(v) for v in rng.normal(size=3)), float(rng.uniform(0.0, 10.0)))
    ph = phantom.render(levels, spacing=(1.25,) * 3, tilt=tilt, sub=1, noise_hu=0.0, seed=seed)
    names = [lv.name for lv in levels]
    ids = {name: int(i) for i, name in ph.names.items()}
    marks, frames = read_column(ph.labels, ph.affine, ids, names)
    axes = column_axes(frames)
    last = levels[-1]
    bottom = level_centres(marks)[-1] - axes[:, 2] * (last.H / 2 + phantom.DISC_SHARE * last.H + S.SACRUM_BELOW_MM)
    person = f"standin:{tier}:{seed}"
    case = {"tier": tier, "item": person, "person": person, "part": part, "type": "typical", "levels": names,
            "landmarks": marks, "sacrum": bottom, "axes": axes, "stand_in": True}
    mu, mu_affine = coarse(attenuation(ph.hu), ph.affine)
    case["frames"] = radiographs(case, mu, mu_affine, spec)
    return case


def stand_in_cases(spec):
    """Each tier's stand-ins where the plan names them: one person in three is a validation person."""
    count = int(spec.get("stand_ins", 0))
    out = {}
    for t, tier in enumerate(TIERS):
        if tier not in spec:
            continue
        seeds = [8_000_000 + 10_000 * t + i for i in range(count)]
        out[tier] = [{"seed": seed, "tier": tier, "item": f"standin:{tier}:{seed}", "person": f"standin:{tier}:{seed}",
                      "part": "validation" if i % 3 == 2 else "training", "type": "typical", "stand_in": True}
                     for i, seed in enumerate(seeds)]
    return out


# ---------------------------------------------------------------- the cache

def case_key(case, spec):
    """The name of a case's file: its tier, item and inputs with the radiographs' settings."""
    drawn = {k: spec.get(k) for k in ("size", "fields_mm", "drr_per_view", "pose")}
    what = {k: case.get(k) for k in ("tier", "item", "person", "type", "ct", "labels", "ids", "seed", "part")}
    return hashlib.sha256(json.dumps({"case": what, "drawn": drawn, "step": DRR_STEP_MM, "voxel": DRR_VOXEL_MM},
                                     sort_keys=True).encode()).hexdigest()[:32]


def save_case(path, case):
    tmp = f"{path}.tmp-{os.getpid()}"
    frames = case["frames"]
    with open(tmp, "wb") as f:
        np.savez(f, levels=np.asarray(case["levels"], dtype=str), landmarks=case["landmarks"], sacrum=case["sacrum"],
                 axes=case["axes"], views=np.asarray([fr["view"] for fr in frames], dtype=str),
                 fields=np.asarray([fr["field"] for fr in frames], float),
                 P=np.asarray([fr["P"] for fr in frames]).reshape(-1, 3, 4),
                 images=np.asarray([fr["image"] for fr in frames], np.float16).reshape(-1, *(frames[0]["image"].shape if frames else (0, 0))),
                 stand_in=np.asarray(bool(case["stand_in"])))
    os.replace(tmp, path)


def load_case(path, case):
    """The case's file read back into the case it was made from."""
    with np.load(path) as z:
        frames = [{"view": str(v), "field": float(fd), "P": P, "image": img.astype(np.float32)}
                  for v, fd, P, img in zip(z["views"], z["fields"], z["P"], z["images"])]
        return dict(case, levels=[str(x) for x in z["levels"]], landmarks=z["landmarks"], sacrum=z["sacrum"],
                    axes=z["axes"], frames=frames, stand_in=bool(z["stand_in"]))


def case_job(args):
    """One case read and cached, for a pool that never touches the card: (cache file, None), or
    (None, why) in words that name no file."""
    S.cpu_only()
    case, spec, cache = args
    path = os.path.join(cache, f"{case_key(case, spec)}.npz")
    if os.path.exists(path):
        return path, None
    try:
        if case.get("stand_in"):
            made = stand_in_case(case["seed"], case["tier"], case["part"], spec)
        else:
            made = read_case(case, spec)
        save_case(path, made)
        return path, None
    except CaseRefused as why:
        return None, str(why)
    except Exception as error:          # one case's failure is counted, never fatal to the rest
        return None, type(error).__name__


# ---------------------------------------------------------------- what the round reads of a case

def case_samples(case, spec, anchors=("none", "bottom")):
    """The case's fingerprint samples: frames_per_view frames a view, each a pose and a field drawn
    from its person alone, the landmarks projected with noise_px of noise and kept only inside the
    field's circle; each run's view carries the tier."""
    size, pose = int(spec["size"]), dict(S.DEFAULT_POSE, **(spec.get("pose") or {}))
    rng = person_rng(case["person"], "frames")
    names = list(case["levels"])
    out = []
    for view in G.VIEWS:
        for _ in range(int(spec["frames_per_view"])):
            P, _ = draw_frame(rng, case, view, spec["fields_mm"], size, pose)
            uv = G.project(P, case["landmarks"]) + rng.normal(0, float(spec["noise_px"]), case["landmarks"].shape[:2] + (2,))
            uv[~in_field(uv, size)] = np.nan
            sacrum_in = bool(in_field(G.project(P, np.asarray(case["sacrum"], float)[None])[0], size))
            out += S.frame_samples(uv, names, names[-1], sacrum_in, size, int(spec["k_max"]), rng,
                                   f"{view}_{case['tier']}", case["type"], case["person"], anchors)
    return out


def case_presence(case, presence, size):
    """Each radiograph's evidence for every landmark, as the loop reads a real frame's: (frames, 18),
    NaN where no body is wholly inside the field."""
    rows = []
    for i, fr in enumerate(case["frames"]):
        uv = G.project(fr["P"], case["landmarks"])
        uv[~in_field(uv, size)] = np.nan
        block = S.visible_block(uv, size)
        if not block:
            rows.append(np.full(len(G.LANDMARKS), np.nan))
            continue
        pct, _ = G.presence_percentiles(fr["image"], [uv[j] for j in block], range(len(G.LANDMARKS)),
                                        presence.get("radius", 8), presence.get("sigma", 1.5),
                                        presence.get("null_per_body", 200), seed=i)
        rows.append(S.column_means(pct))
    return np.asarray(rows).reshape(-1, len(G.LANDMARKS))


def without_images(case):
    """The case with its radiographs' pixels dropped, once its presence is read: the round keeps the
    poses and the landmarks of every case and the pixels of none."""
    return dict(case, frames=[{k: v for k, v in fr.items() if k != "image"} for fr in case["frames"]])


# ---------------------------------------------------------------- the network's reading of the CTs

def spine_only_copy(source, target, ids):
    """A copy of a label map holding only the label values ids names, every other label zeroed (the
    sacrum, the hips, the ribs and the rest of the column), on the same grid with the same header, for
    the crops alone: the crops' second channel is every named vertebra, as the phantoms' rows draw only
    their column. target ends in .nii.gz: a whole-body map is some 300 MB as int16 and almost all of it
    zeros, and it is read once, when its crops are cut into the cache."""
    import nibabel as nib
    image = nib.load(source)
    labels = as_labels(image.dataobj)
    kept = np.where(np.isin(labels, [int(v) for v in ids]), labels, 0).astype(np.int16)
    header = image.header.copy()
    header.set_data_dtype(np.int16)
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    tmp = f"{str(target)[:-len('.nii.gz')]}.tmp-{os.getpid()}.nii.gz"
    nib.save(nib.Nifti1Image(kept, image.affine, header), tmp)
    os.replace(tmp, target)


def row_seed(item):
    """The seed of a row's one jitter draw, from its item alone, as the screen's trials draw it."""
    return int.from_bytes(hashlib.sha256(item.encode("utf-8")).digest()[:4], "big")


def network_row(case, work):
    """The auto-anatomist's row for the network's reading of one held-out case: a volume row of its CT
    and the spine-only copy of its label map, its typical levels named, in the oracle's frame as the
    loop's own rows are cut; a stand-in's phantom row, its column from T12 down."""
    if case.get("stand_in"):
        return {"kind": "phantom", "id": f"gold-{case['person']}", "phenotype": "typical", "start": "T12",
                "count": len(S.TYPE_LEVELS["typical"]), "seed": int(case["seed"]), "spacing": 1.25, "sub": 1,
                "noise": 20.0}
    names = {str(int(case["ids"][lv])): lv for lv in case["levels"]}
    digest = hashlib.sha256(f"{case['tier']}|{case['item']}|{case['labels']}".encode()).hexdigest()[:24]
    return {"kind": "volume", "id": f"{case['tier']}:{case['item']}", "ct": case["ct"],
            "labels": str(Path(work) / "labels" / f"{case['tier']}-{digest}.nii.gz"), "names": names,
            "seed": row_seed(f"{case['tier']}:{case['item']}"), "frame": "oracle"}


def network_row_job(args):
    """One held-out case's row made ready and its crops rendered into the cache, for a pool that
    never touches the card: (row, None), or (None, why) in words that name no file."""
    S.cpu_only()
    case, work, cfg_record, cache = args
    try:
        from autoanatomist import rows as R
        from autoanatomist.model import Config
        cfg = Config(**cfg_record)
        row = network_row(case, work)
        if row["kind"] == "volume" and not os.path.exists(row["labels"]):
            spine_only_copy(case["labels"], row["labels"], [int(v) for v in row["names"]])
        path = os.path.join(cache, R.row_digest(row, cfg, True) + ".npz")
        if not os.path.exists(path):
            R.save_part(path, R.render_row(row, cfg, True))
        return row, None
    except Exception as error:          # one case's failure is counted, never fatal to the reading
        return None, str(error) if isinstance(error, CaseRefused) else type(error).__name__
