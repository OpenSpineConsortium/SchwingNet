"""The project's own vertebral segmenter: nnU-Net trained on the gold tier 3 CTs, judged on held-out human masks.

    python3 tools/gold3_segmenter.py prepare --admission data/gold3-ct/admission.json --tiers DIR \\
        --ts-root DIR --enhance-ct DIR --enhance-labels DIR --verse-masks DIR --out DIR
    python3 tools/gold3_segmenter.py train --out DIR [--fold 0] [--workers N]
    python3 tools/gold3_segmenter.py evaluate --out DIR [--device cuda]
    python3 tools/gold3_segmenter.py postmortem --out DIR --cts DIR [--looks 20]
    python3 tools/gold3_segmenter.py report --out DIR
    python3 tools/gold3_segmenter.py predict --model DIR --ct FILE --mask FILE [--device cuda]

Why this exists. The owner asked on 2026-10-31 at 01:16 UTC whether to "TRAIN MY OWN SEGMENTER ON THE GOLD
TIER DATA TO USE ON THE NMDID DATASET", and said yes at 01:20 UTC to building it with the rolling NMDID
pipeline (docs/research/whole-spine-ct-online/README.md, section 7). Every source the gold tier and NMDID
add then carries one label scheme from one network trained on persons' masks, instead of SPINEPS for one
source, TotalSegmentator for another and MOOSE for a third. The design is frozen in
docs/research/gold3-segmenter/PREREG.md, which governs where this docstring differs; the job is
grid/segmenter.sbatch, the gate word `segmenter train`, run as the launched flow segmenter
(flows/segmenter.py).

What each part does:

1. prepare: every study the field test admits (data/gold3-ct/admission.json, verdict admitted), found on
   the data root as tools/gold3_totalseg_grid.py locate finds it, given a role (roles): held out where its
   person, or anyone in its repeat-scan unit, is on data/splits/test-persons.json or on the latent shape
   priors' reserve (data/splits/latent-prior-test-reserve.json, 584 studies); else validation or training
   by data/splits/rule.json's hash of its unit's key, so a patient's repeat scans never sit on both sides.
   A training or validation study's CT and release masks are cut to the column's box with a margin
   (MARGIN_MM) and written as an nnU-Net v2 raw dataset (DATASET) under OUT/nnUNet_raw: the CT as int16,
   the mask on the 28 canonical ids of tools/anomaly_pack.py (0 background, C1 to C7, T1 to T12, T13, L1
   to L5, L6, sacrum 27), the sacrum always one union with S1 (the owner's rule of 2026-10-30 22:58 UTC).
   A study whose release lacks C2 or the sacrum (its admission's complete list) has the background beyond
   its last drawn level on that side set to the ignore label, so the network is never taught that the
   undrawn level is background; a study that lacks a level between two drawn ones is left out. OUT/
   cases.json records every study, its role, its unit, what was ignored and every file's sha256;
   splits_final.json gives nnU-Net's fold 0 the rule's training and validation parts exactly.
2. train: nnU-Net's own plan and preprocessing once, then nnUNetv2_train fold 0 of 3d_fullres, carried on
   with --c from its last checkpoint whenever the job is sent again, until checkpoint_final.pth stands.
3. evaluate: the trained network run on every held-out study's whole CT, uncut, as the NMDID pipeline
   runs it, and compared with the release's masks on the CT's grid: Dice per level over the voxels not
   ignored, and the level's identification, whether the label the network gives most of a drawn level's
   voxels is that level's (evaluate.jsonl).
4. postmortem: the network run on post-mortem CTs with no masks (VSDFullBody), each judged by the column
   rule (column_verdict): every level from C2 to the sacrum drawn, in order from head to foot, no name
   twice; a few overlays written for a person's look (looks/).
5. report: OUT/REPORT.md, the hypotheses of the PREREG against their bars with Wilson intervals, by member;
   counts and store names only, no path under the data root and no person key beyond the study ids the
   releases publish.

predict is the one call the rolling pipeline (tools/rolling_ct.py) makes on each converted series.

The standard library here; numpy and nibabel are imported where a volume is read, nnunetv2 and torch
where the network runs, so the parts that need none of them are tested without them
(tests/test_gold3_segmenter.py). tools/ leaves sys.path first, since tools/profile.py would shadow the
standard library's profile, which torch's imports reach.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:] = [entry for entry in sys.path if Path(entry or ".").resolve() != ROOT / "tools"]


def sibling(name):
    """A module of tools/ loaded by its path, since tools/ is off sys.path."""
    spec = importlib.util.spec_from_file_location(f"_seg_{name}", ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


locator = sibling("gold3_totalseg_grid")

DATASET_ID = 801
DATASET = f"Dataset{DATASET_ID:03d}_SchwingGold3"
CONFIGURATION = "3d_fullres"
TRAINER = "nnUNetTrainer"
PLANS = "nnUNetPlans"
FOLD = 0
# The 28 canonical ids of tools/anomaly_pack.py, in order, and the ignore label nnU-Net v2 reads as the
# highest id named "ignore".
CANONICAL = (["background"] + [f"vertebra_c{i}" for i in range(1, 8)] + [f"vertebra_t{i}" for i in range(1, 13)]
             + ["vertebra_t13"] + [f"vertebra_l{i}" for i in range(1, 6)] + ["vertebra_l6", "sacrum"])
T13, L6, SACRUM = 20, 26, 27
IGNORE = 28
LEVEL_NAME = {**{i: f"C{i}" for i in range(1, 8)}, **{7 + i: f"T{i}" for i in range(1, 13)}, T13: "T13",
              **{20 + i: f"L{i}" for i in range(1, 6)}, L6: "L6", SACRUM: "sacrum"}
ID_OF_NAME = {name: i for i, name in LEVEL_NAME.items()}
# Each release's raw ids to the canonical ones. ENHANCE.PET: C1 to T12 1 to 19, L1 to L6 20 to 25, the
# hips 26 and 27 (background here), the sacrum 28 (tools/gold3_ct.py ENHANCE_TO_CANONICAL). VerSe: its
# alphabet, T13 at 28 and the retired S1 29 folded into the sacrum (tools/anomaly_pack.py). A
# TotalSegmentator subject: one file per structure, S1 folded into the sacrum.
ENHANCE_TO_CANONICAL = {**{i: i for i in range(1, 20)}, **{19 + i: 20 + i for i in range(1, 7)}, 28: SACRUM}
VERSE_TO_CANONICAL = {**{i: i for i in range(1, 20)}, 28: T13, **{20 + i: 21 + i for i in range(5)}, 25: L6, 26: SACRUM, 29: SACRUM}
TOTALSEG_FILES = {**{f"vertebrae_C{i}": i for i in range(1, 8)}, **{f"vertebrae_T{i}": 7 + i for i in range(1, 13)},
                  **{f"vertebrae_L{i}": 20 + i for i in range(1, 6)}, "vertebrae_S1": SACRUM, "sacrum": SACRUM}
MAPS = {"enhance_pet": ENHANCE_TO_CANONICAL, "verse": VERSE_TO_CANONICAL}
# The ends a release may lack and still train, with the ignore label beyond its last drawn level.
ENDS = ("C2", "sacrum")
MARGIN_MM = 60.0                # in every direction around the column's box: the ribs, the pelvis and the soft tissue
MIN_VOXELS = 200                # a level counts as drawn, as the field test counts it (tools/gold3_field.py)
TEST_LISTS = ("data/splits/test-persons.json", "data/splits/latent-prior-test-reserve.json")
UNITS = "data/splits/latent-prior-repeat-groups.json"
RULE = "data/splits/rule.json"
ADMITTED = ("admitted",)
WILSON_Z = 1.959963984540054


class SegmenterFault(Exception):
    """What stops a part with a reason a person reads."""


# ---- who is in which part --------------------------------------------------------------------------

def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def person_of(row):
    """The study's person key, as the splits name it: the admission's, else member:id."""
    return row.get("person") or f"{row['member']}:{row['id']}"


def person_hash(salt, key):
    """data/splits/rule.json's hash, as tools/gold3_ct.py person_hash has it."""
    return int.from_bytes(hashlib.sha256(f"schwingnet-split|{salt}|{key}".encode()).digest()[:8], "big")


def unit_index(units):
    """{person: unit key} for every person a repeat-scan unit lists."""
    index = {}
    for unit in units:
        for person in unit["persons"]:
            index[person] = unit["unit"]
    return index


def roles(rows, rule, held_out, units):
    """{person: (role, unit)}: held_out where the person or anyone of its unit is on a held-out list,
    else validation below the rule's share of the hash space for the unit's key, training above."""
    index = unit_index(units)
    members = {}
    for unit in units:
        members[unit["unit"]] = set(unit["persons"])
    found = {}
    for row in rows:
        person = person_of(row)
        unit = index.get(person, person)
        together = members.get(unit, {person}) | {person}
        if together & held_out:
            role = "held_out"
        elif person_hash(rule["salt"], unit) < rule["validation_share"] * 2**64:
            role = "validation"
        else:
            role = "train"
        found[person] = (role, unit)
    return found


def held_out_persons(repo=ROOT):
    """Every person a held-out list names."""
    persons = set()
    for rel in TEST_LISTS:
        persons |= {entry["person"] for entry in read_json(Path(repo) / rel)}
    return persons


def admitted(admission):
    return [row for row in admission["studies"] if row.get("verdict") in ADMITTED]


def ends_missing(row):
    """(the ends the release lacks, the levels it lacks between two drawn ones)."""
    complete = list(row.get("complete") or [])
    ends = [name for name in ENDS if name in complete]
    inside = [name for name in complete if name not in ENDS]
    return ends, inside


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def case_name(row):
    """nnU-Net's case identifier: letters, digits and _ alone."""
    return f"{row['member']}_{row['id']}".replace("-", "_")


# ---- the masks on the canonical ids ---------------------------------------------------------------

def to_canonical(member, raw):
    """A release's label array on the canonical ids, numpy uint8; what no map names is background."""
    import numpy as np
    table = np.zeros(max(256, int(raw.max()) + 1), dtype=np.uint8)
    for source, target in MAPS[member].items():
        if source < len(table):
            table[source] = target
    return table[np.clip(raw, 0, len(table) - 1).astype(np.int64)]


def totalseg_canonical(folder):
    """A TotalSegmentator subject's segmentations/ folder as one canonical array, with the grid's
    affine; each structure's file is laid on in head-to-foot order, so a voxel two files claim takes
    the lower level's id, the sacrum's union with S1 last of all."""
    import nibabel as nib
    import numpy as np
    out, affine = None, None
    for name, value in sorted(TOTALSEG_FILES.items(), key=lambda item: item[1]):
        path = Path(folder) / f"{name}.nii.gz"
        if not path.exists():
            continue
        img = nib.load(str(path))
        data = np.asanyarray(img.dataobj) > 0
        if out is None:
            out, affine = np.zeros(data.shape, dtype=np.uint8), img.affine
        out[data] = value
    if out is None:
        raise SegmenterFault("no vertebrae_*.nii.gz or sacrum.nii.gz in the subject's segmentations/")
    return out, affine


def release_canonical(member, release):
    """(canonical array, affine) of a study's release masks."""
    if member == "totalsegmentator":
        return totalseg_canonical(release)
    import nibabel as nib
    import numpy as np
    img = nib.load(str(release))
    return to_canonical(member, np.asanyarray(img.dataobj).astype(np.int32)), img.affine


def vertical_axis(affine):
    """(voxel axis nearest the world's head-foot line, +1 where the index runs to the head, else -1)."""
    column = [abs(affine[2][k]) for k in range(3)]
    axis = column.index(max(column))
    return axis, (1 if affine[2][axis] > 0 else -1)


def drawn_levels(mask):
    """{canonical id: voxels} of the levels drawn at MIN_VOXELS or more."""
    import numpy as np
    counts = np.bincount(mask.ravel(), minlength=IGNORE + 1)
    return {i: int(counts[i]) for i in range(1, SACRUM + 1) if counts[i] >= MIN_VOXELS}


def index_extent(mask, value, axis):
    """(lowest, highest) index along AXIS of the voxels holding VALUE."""
    import numpy as np
    where = np.nonzero(np.any(mask == value, axis=tuple(k for k in range(3) if k != axis)))[0]
    return int(where.min()), int(where.max())


def ignore_ends(mask, affine, ends):
    """The background beyond the release's last drawn level on each missing end set to IGNORE, in place:
    above the highest drawn level below C1 where C2 is missing (C1, drawn or not, keeps its label), below
    the lowest drawn level where the sacrum is. Returns {end: voxels ignored}."""
    import numpy as np
    axis, sign = vertical_axis(affine)
    levels = sorted(drawn_levels(mask))
    said = {}
    for end in ends:
        if end == "C2":
            below_c1 = [i for i in levels if i > 1]
            if not below_c1:
                raise SegmenterFault("C2 is missing and no level below C1 is drawn")
            lo, hi = index_extent(mask, below_c1[0], axis)
            cut = slice(hi + 1, None) if sign > 0 else slice(0, lo)
        else:
            above = [i for i in levels if i < SACRUM]
            if not above:
                raise SegmenterFault("the sacrum is missing and no level above it is drawn")
            lo, hi = index_extent(mask, above[-1], axis)
            cut = slice(0, lo) if sign > 0 else slice(hi + 1, None)
        index = [slice(None)] * 3
        index[axis] = cut
        region = mask[tuple(index)]
        hit = region == 0
        said[end] = int(hit.sum())
        region[hit] = IGNORE
    return said


def column_box(mask, shape, spacing, margin_mm=MARGIN_MM):
    """The column's box with MARGIN_MM on every side, as one slice per axis, held inside the volume."""
    import numpy as np
    where = np.nonzero((mask > 0) & (mask != IGNORE))
    if not where[0].size:
        raise SegmenterFault("no level is drawn")
    box = []
    for k in range(3):
        pad = int(math.ceil(margin_mm / max(float(spacing[k]), 1e-3)))
        box.append(slice(max(0, int(where[k].min()) - pad), min(shape[k], int(where[k].max()) + 1 + pad)))
    return tuple(box)


def cropped_affine(affine, box):
    import numpy as np
    out = np.array(affine, dtype=float)
    start = np.array([box[k].start for k in range(3)] + [1.0])
    out[:3, 3] = (np.array(affine) @ start)[:3]
    return out


def write_case(study, ct_path, release, images, labels):
    """The study's CT and canonical mask cut to the column's box, written as nnU-Net's case; a dict of
    what was written and ignored."""
    import nibabel as nib
    import numpy as np
    mask, affine = release_canonical(study["member"], release)
    ct = nib.load(str(ct_path))
    if tuple(ct.shape[:3]) != tuple(mask.shape) or not np.allclose(ct.affine, affine, atol=1e-3):
        raise SegmenterFault("the release's masks are not on the CT's grid")
    ignored = ignore_ends(mask, affine, study["ends"])
    spacing = [float(np.linalg.norm(np.asarray(affine)[:3, k])) for k in range(3)]
    box = column_box(mask, mask.shape, spacing)
    image = np.asanyarray(ct.dataobj)[box].astype(np.int16)
    out_affine = cropped_affine(affine, box)
    name = case_name(study)
    image_path = Path(images) / f"{name}_0000.nii.gz"
    label_path = Path(labels) / f"{name}.nii.gz"
    nib.save(nib.Nifti1Image(image, out_affine), str(image_path))
    label = nib.Nifti1Image(mask[box].astype(np.uint8), out_affine)
    label.set_data_dtype(np.uint8)
    nib.save(label, str(label_path))
    return {"case": name, "shape": list(image.shape), "levels": sorted(drawn_levels(mask[box])), "ignored": ignored,
            "image_sha256": sha256_of(image_path), "label_sha256": sha256_of(label_path)}


def dataset_json(count):
    labels = {name: i for i, name in enumerate(CANONICAL)}
    labels["ignore"] = IGNORE
    return {"channel_names": {"0": "CT"}, "labels": labels, "numTraining": count, "file_ending": ".nii.gz",
            "name": DATASET, "description": "SchwingNet gold tier 3, the 28 canonical vertebral ids, the sacrum one union with S1; confidential"}


# ---- prepare ---------------------------------------------------------------------------------------

def plan_studies(admission, rule, held_out, units):
    """Every admitted study with its person, unit, role, the ends it lacks and why it is left out, if
    it is. Standard library, so the split is tested where no volume is read."""
    rows = admitted(admission)
    assigned = roles(rows, rule, held_out, units)
    studies = []
    for row in rows:
        person = person_of(row)
        role, unit = assigned[person]
        ends, inside = ends_missing(row)
        study = {"member": row["member"], "id": row["id"], "person": person, "unit": unit, "role": role,
                 "ends": ends, "complete": list(row.get("complete") or [])}
        if inside and role != "held_out":
            study["left_out"] = "the release lacks a level between two drawn ones: " + ", ".join(inside)
        studies.append(study)
    return studies


def splits_final(cases):
    train = sorted(c["case"] for c in cases if c["role"] == "train")
    val = sorted(c["case"] for c in cases if c["role"] == "validation")
    return [{"train": train, "val": val}]


def raw_folder(out):
    return Path(out) / "nnUNet_raw" / DATASET


def prepare(args):
    repo = Path(args.repo)
    admission = read_json(args.admission)
    studies = plan_studies(admission, read_json(repo / RULE), held_out_persons(repo), read_json(repo / UNITS))
    verse_ct = locator.verse_cts(locator.read_tiers(args.tiers)) if args.tiers else {}
    raw = raw_folder(args.out)
    images, labels = raw / "imagesTr", raw / "labelsTr"
    images.mkdir(parents=True, exist_ok=True)
    labels.mkdir(parents=True, exist_ok=True)
    done = {c["case"]: c for c in read_cases(args.out)}
    cases = []
    for study in studies:
        ct, release, why = locator.locate(study, verse_ct, args.ts_root, args.enhance_ct, args.enhance_labels, args.verse_masks)
        record = dict(study, ct=ct, release=str(release) if release else None)
        if why:
            record["left_out"] = why
        elif study["role"] != "held_out" and "left_out" not in study:
            name = case_name(study)
            earlier = done.get(name)
            if earlier and earlier.get("written") and (images / f"{name}_0000.nii.gz").exists() and (labels / f"{name}.nii.gz").exists():
                record["written"] = earlier["written"]
            else:
                try:
                    record["written"] = write_case(study, ct, release, images, labels)
                except (SegmenterFault, OSError, ValueError) as error:
                    record["left_out"] = f"not written: {str(error)[:160]}"
        cases.append(record)
    trained = [dict(c["written"], role=c["role"]) for c in cases if c.get("written")]
    write_json(raw / "dataset.json", dataset_json(len(trained)))
    write_json(Path(args.out) / "splits_final.json", splits_final(trained))
    write_json(Path(args.out) / "cases.json", {"dataset": DATASET, "prepared_at": utc_now(), "cases": cases})
    counts = role_counts(cases)
    print(f"prepare: {len(cases)} admitted studies; {counts}")
    return 0


def role_counts(cases):
    words = []
    for role in ("train", "validation", "held_out"):
        group = [c for c in cases if c["role"] == role]
        kept = [c for c in group if c.get("written") or (role == "held_out" and not c.get("left_out"))]
        words.append(f"{role} {len(kept)} of {len(group)}")
    return "; ".join(words)


def read_cases(out):
    path = Path(out) / "cases.json"
    if not path.exists():
        return []
    return read_json(path).get("cases", [])


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def utc_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---- train -----------------------------------------------------------------------------------------

def nnunet_environment(out):
    env = dict(os.environ)
    env.update({"nnUNet_raw": str(Path(out) / "nnUNet_raw"), "nnUNet_preprocessed": str(Path(out) / "nnUNet_preprocessed"),
                "nnUNet_results": str(Path(out) / "nnUNet_results")})
    return env


def fold_folder(out, fold=FOLD):
    return Path(out) / "nnUNet_results" / DATASET / f"{TRAINER}__{PLANS}__{CONFIGURATION}" / f"fold_{fold}"


def training_state(out, fold=FOLD):
    """finished, carry_on (a checkpoint to continue from) or fresh."""
    folder = fold_folder(out, fold)
    if (folder / "checkpoint_final.pth").exists():
        return "finished"
    if (folder / "checkpoint_latest.pth").exists() or (folder / "checkpoint_best.pth").exists():
        return "carry_on"
    return "fresh"


def train_commands(out, fold, workers, state, planned):
    """The commands train runs, in order, for the state it finds: nnU-Net's plan once, then the fold."""
    commands = []
    if not planned:
        commands.append(["nnUNetv2_plan_and_preprocess", "-d", str(DATASET_ID), "-c", CONFIGURATION,
                         "--verify_dataset_integrity", "-np", str(workers)])
    if state != "finished":
        command = ["nnUNetv2_train", str(DATASET_ID), CONFIGURATION, str(fold), "-tr", TRAINER, "-p", PLANS]
        if state == "carry_on":
            command.append("--c")
        commands.append(command)
    return commands


def planned_marker(out):
    return Path(out) / "nnUNet_preprocessed" / DATASET / "PLANNED"


def train(args):
    env = nnunet_environment(args.out)
    env["nnUNet_n_proc_DA"] = str(args.workers)
    preprocessed = Path(env["nnUNet_preprocessed"]) / DATASET
    marker = planned_marker(args.out)
    state = training_state(args.out, args.fold)
    commands = train_commands(args.out, args.fold, args.workers, state, marker.exists())
    if not commands:
        print(f"train: fold {args.fold} is finished (checkpoint_final.pth)")
        return 0
    for command in commands:
        print("train: " + " ".join(command), flush=True)
        code = subprocess.call(command, env=env)
        if code != 0:
            print(f"train: {command[0]} ended {code}")
            return code
        if command[0] == "nnUNetv2_plan_and_preprocess":
            # The fold is the rule's, never nnU-Net's own random five: its splits file is replaced by ours.
            shutil.copyfile(Path(args.out) / "splits_final.json", preprocessed / "splits_final.json")
            marker.write_text(utc_now() + "\n", encoding="utf-8")
    print(f"train: fold {args.fold} {training_state(args.out, args.fold)}")
    return 0


# ---- predict ---------------------------------------------------------------------------------------

def predictor(model, device="cuda", fold=FOLD):
    """nnU-Net's predictor with the trained fold, loaded once."""
    import torch
    from nnunetv2.inference.predict_from_raw_data import nnUNetPredictor
    runner = nnUNetPredictor(tile_step_size=0.5, use_gaussian=True, use_mirroring=True, perform_everything_on_device=True,
                             device=torch.device(device), verbose=False, verbose_preprocessing=False, allow_tqdm=False)
    runner.initialize_from_trained_model_folder(str(model), use_folds=(fold,), checkpoint_name="checkpoint_final.pth")
    return runner


def model_folder(out):
    return fold_folder(out).parent


def predict_file(runner, ct, mask):
    """The network's canonical mask for the CT at CT, written to MASK on the CT's own grid."""
    Path(mask).parent.mkdir(parents=True, exist_ok=True)
    stem = str(mask)[:-len(".nii.gz")] if str(mask).endswith(".nii.gz") else str(mask)
    runner.predict_from_files([[str(ct)]], [stem], save_probabilities=False, overwrite=True,
                              num_processes_preprocessing=1, num_processes_segmentation_export=1)
    return Path(stem + ".nii.gz")


def predict(args):
    runner = predictor(args.model, args.device)
    print(f"predict: {predict_file(runner, args.ct, args.mask)}")
    return 0


# ---- evaluate --------------------------------------------------------------------------------------

def level_scores(truth, guess):
    """[(id, dice, identified)] for each level the truth draws: Dice over the voxels not ignored, and
    whether the label the network gives most of the level's voxels is the level's own."""
    import numpy as np
    keep = truth != IGNORE
    scores = []
    for level in sorted(drawn_levels(np.where(keep, truth, 0).astype(np.uint8))):
        mine = (truth == level) & keep
        theirs = (guess == level) & keep
        dice = 2.0 * float((mine & theirs).sum()) / float(mine.sum() + theirs.sum())
        given = np.bincount(guess[mine].ravel(), minlength=SACRUM + 1)
        given[0] = 0
        top = int(given.argmax()) if given.sum() else 0
        scores.append((level, round(dice, 4), top == level))
    return scores


def evaluate(args):
    import nibabel as nib
    import numpy as np
    runner = predictor(model_folder(args.out), args.device)
    rows_path = Path(args.out) / "evaluate.jsonl"
    done = {json.loads(line)["case"] for line in rows_path.read_text(encoding="utf-8").splitlines() if line.strip()} if rows_path.exists() else set()
    held = [c for c in read_cases(args.out) if c["role"] == "held_out" and not c.get("left_out")]
    with open(rows_path, "a", encoding="utf-8") as fh:
        for study in held:
            name = case_name(study)
            if name in done:
                continue
            row = {"case": name, "member": study["member"], "id": study["id"]}
            try:
                truth, affine = release_canonical(study["member"], study["release"])
                ignore_ends(truth, affine, study["ends"])
                out = predict_file(runner, study["ct"], Path(args.out) / "held_out" / f"{name}.nii.gz")
                guess = np.asanyarray(nib.load(str(out)).dataobj).astype(np.uint8)
                if guess.shape != truth.shape:
                    raise SegmenterFault("the prediction is not on the CT's grid")
                row["levels"] = [{"level": LEVEL_NAME[i], "dice": d, "identified": ok} for i, d, ok in level_scores(truth, guess)]
                row["column"] = column_verdict(guess, nib.load(str(out)).affine)
            except (SegmenterFault, OSError, ValueError) as error:
                row["error"] = str(error)[:160]
            fh.write(json.dumps(row, sort_keys=True) + "\n")
            fh.flush()
    print(f"evaluate: {len(held)} held-out studies; rows in evaluate.jsonl")
    return 0


# ---- the column rule, for CTs with no masks ---------------------------------------------------------

def column_order(levels):
    """What keeps a set of drawn levels, {id: head-foot centre in mm, larger to the head}, from being a
    whole column from C2 to the sacrum: [] where nothing does. T13 and L6 are variants, so their
    absence is no gap."""
    problems = []
    needed = [i for i in range(2, SACRUM + 1) if i not in (T13, L6)]
    missing = [LEVEL_NAME[i] for i in needed if i not in levels]
    if missing:
        problems.append("not drawn: " + ", ".join(missing))
    present = sorted(levels)
    heights = [levels[i] for i in present]
    if any(lower >= upper for upper, lower in zip(heights, heights[1:])):
        problems.append("the drawn levels are not in order from head to foot")
    return problems


def centres(mask, affine):
    """{id: the level's centre along the world's head-foot line, mm} of each drawn level."""
    import numpy as np
    out = {}
    for level in drawn_levels(mask):
        where = np.nonzero(mask == level)
        ijk = np.column_stack([*where, np.ones(len(where[0]))])
        out[level] = float((ijk @ np.asarray(affine)[2]).mean())
    return out


def column_verdict(mask, affine):
    problems = column_order(centres(mask, affine))
    return {"whole": not problems, "problems": problems}


def postmortem(args):
    import nibabel as nib
    import numpy as np
    runner = predictor(model_folder(args.out), args.device)
    rows_path = Path(args.out) / "postmortem.jsonl"
    done = {json.loads(line)["ct"] for line in rows_path.read_text(encoding="utf-8").splitlines() if line.strip()} if rows_path.exists() else set()
    cts = sorted(p for p in Path(args.cts).rglob("*.nii.gz"))
    looks = Path(args.out) / "looks"
    with open(rows_path, "a", encoding="utf-8") as fh:
        for number, ct in enumerate(cts):
            name = ct.name[:-len(".nii.gz")]
            if name in done:
                continue
            row = {"ct": name}
            try:
                out = predict_file(runner, ct, Path(args.out) / "postmortem" / f"{name}.nii.gz")
                img = nib.load(str(out))
                row.update(column_verdict(np.asanyarray(img.dataobj).astype(np.uint8), img.affine))
                if number < args.looks:
                    write_look(ct, out, looks / f"{name}.png")
            except (SegmenterFault, OSError, ValueError) as error:
                row["error"] = str(error)[:160]
            fh.write(json.dumps(row, sort_keys=True) + "\n")
            fh.flush()
    print(f"postmortem: {len(cts)} CTs; rows in postmortem.jsonl")
    return 0


def write_look(ct, mask, png):
    """A coronal maximum projection of the CT with the levels in alternating colours over it, for a
    person's look at whether the network named the column right."""
    import nibabel as nib
    import numpy as np
    from PIL import Image
    image = np.asanyarray(nib.as_closest_canonical(nib.load(str(ct))).dataobj).astype(np.float32)
    labels = np.asanyarray(nib.as_closest_canonical(nib.load(str(mask))).dataobj).astype(np.uint8)
    bone = np.clip((image.max(axis=1) + 200.0) / 1700.0, 0, 1)
    drawn = labels.max(axis=1)
    rgb = np.stack([bone, bone, bone], axis=-1)
    palette = np.array([[1.0, 0.3, 0.3], [0.3, 0.6, 1.0], [0.3, 0.9, 0.4]])
    for level in range(1, SACRUM + 1):
        hit = drawn == level
        rgb[hit] = 0.5 * rgb[hit] + 0.5 * palette[level % 3]
    out = (np.rot90(rgb, 1) * 255).astype(np.uint8)
    png.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(out).save(png)


# ---- report ----------------------------------------------------------------------------------------

def wilson(hits, n, z=WILSON_Z):
    """The Wilson interval of HITS of N, (low, high); (0, 1) where N is 0."""
    if n == 0:
        return 0.0, 1.0
    p = hits / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def median(values):
    ordered = sorted(values)
    if not ordered:
        return None
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def read_rows(path):
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def summary(rows, post):
    """The PREREG's measures from the rows: H1 the median of the per-study median Dice, H2 the share of
    drawn levels identified, H3 the share of held-out studies whose predicted column is whole, H4 the
    share of post-mortem CTs whose column is whole; with counts and Wilson intervals."""
    scored = [r for r in rows if r.get("levels")]
    study_dice = [median([lv["dice"] for lv in r["levels"]]) for r in scored]
    levels = [lv for r in scored for lv in r["levels"]]
    named = sum(1 for lv in levels if lv["identified"])
    whole = sum(1 for r in scored if r.get("column", {}).get("whole"))
    post_read = [r for r in post if "whole" in r]
    post_whole = sum(1 for r in post_read if r["whole"])
    by_member = {}
    for r in scored:
        group = by_member.setdefault(r["member"], {"studies": 0, "levels": 0, "identified": 0})
        group["studies"] += 1
        group["levels"] += len(r["levels"])
        group["identified"] += sum(1 for lv in r["levels"] if lv["identified"])
    return {"studies": len(scored), "errors": sum(1 for r in rows if r.get("error")),
            "h1_median_dice": median(study_dice), "h2_identified": [named, len(levels), *wilson(named, len(levels))],
            "h3_whole": [whole, len(scored), *wilson(whole, len(scored))],
            "h4_postmortem_whole": [post_whole, len(post_read), *wilson(post_whole, len(post_read))],
            "postmortem_errors": sum(1 for r in post if r.get("error")), "by_member": by_member}


BARS = {"h1_median_dice": 0.90, "h2_identified": 0.95, "h3_whole": 0.90}


def share_words(value):
    hits, n, low, high = value
    return f"{hits} of {n} ({hits / n:.3f}, 95% {low:.3f} to {high:.3f})" if n else "none read"


def report_text(data, cases):
    lines = ["# The gold tier 3 segmenter: report", "",
             f"Written {utc_now()} by tools/gold3_segmenter.py report under docs/research/gold3-segmenter/PREREG.md. Confidential.", "",
             f"- Studies: {role_counts(cases)}.",
             f"- Held-out studies scored: {data['studies']}, in error {data['errors']}."]
    h1 = data["h1_median_dice"]
    lines.append(f"- H1, median Dice per study, median over studies: {h1:.4f} against the bar {BARS['h1_median_dice']}: "
                 f"{'met' if h1 >= BARS['h1_median_dice'] else 'not met'}." if h1 is not None else "- H1: no study scored.")
    for key, label in (("h2_identified", "H2, drawn levels named right"), ("h3_whole", "H3, held-out columns predicted whole")):
        value = data[key]
        met = value[1] and value[2] >= BARS[key]
        lines.append(f"- {label}: {share_words(value)} against the bar {BARS[key]} on the low end of the interval: {'met' if met else 'not met'}.")
    lines.append(f"- H4, post-mortem columns predicted whole (an estimate, no bar): {share_words(data['h4_postmortem_whole'])}; "
                 f"in error {data['postmortem_errors']}; overlays under looks/ for a person's look.")
    lines += ["", "| Member | Studies | Levels | Named right |", "| --- | --- | --- | --- |"]
    for member, group in sorted(data["by_member"].items()):
        lines.append(f"| {member} | {group['studies']} | {group['levels']} | {group['identified']} |")
    return "\n".join(lines) + "\n"


def report(args):
    data = summary(read_rows(Path(args.out) / "evaluate.jsonl"), read_rows(Path(args.out) / "postmortem.jsonl"))
    write_json(Path(args.out) / "summary.json", data)
    text = report_text(data, read_cases(args.out))
    (Path(args.out) / "REPORT.md").write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


# ---- the command line ------------------------------------------------------------------------------

def parser():
    top = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parts = top.add_subparsers(dest="part", required=True)
    one = parts.add_parser("prepare")
    for flag in ("--admission", "--tiers", "--ts-root", "--enhance-ct", "--enhance-labels", "--verse-masks", "--out"):
        one.add_argument(flag, required=flag in ("--admission", "--out"), default="")
    one.add_argument("--repo", default=str(ROOT))
    one = parts.add_parser("train")
    one.add_argument("--out", required=True)
    one.add_argument("--fold", type=int, default=FOLD)
    one.add_argument("--workers", type=int, default=8)
    for name in ("evaluate", "postmortem"):
        one = parts.add_parser(name)
        one.add_argument("--out", required=True)
        one.add_argument("--device", default="cuda")
        if name == "postmortem":
            one.add_argument("--cts", required=True)
            one.add_argument("--looks", type=int, default=20)
    one = parts.add_parser("report")
    one.add_argument("--out", required=True)
    one = parts.add_parser("predict")
    one.add_argument("--model", required=True)
    one.add_argument("--ct", required=True)
    one.add_argument("--mask", required=True)
    one.add_argument("--device", default="cuda")
    return top


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        return {"prepare": prepare, "train": train, "evaluate": evaluate, "postmortem": postmortem,
                "report": report, "predict": predict}[args.part](args)
    except SegmenterFault as error:
        print(f"{args.part}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
