"""TotalSegmentator's vertebrae on the gold tier 4 CTs, the census's studies that no release draws.

    python3 tools/gold4_totalseg_grid.py run --census FILE --tiers DIR --out DIR --chain JOB --task K --tasks N \\
        [--commit SHA] [--code DIGEST] [--weights DIR] [--threads N] [--device gpu] [--stop-after SECONDS]
    python3 tools/gold4_totalseg_grid.py merge --out DIR --chain JOB [--commit SHA] [--code DIGEST]

Why this exists. The gold tier 3 releases, VerSe, TotalSegmentator and ENHANCE.PET, are the CTs whose
masks someone drew; the census (tools/gold3_census.py, part gold4, job 40870542) read every SPINEPS
mask of the other collections on the grid through rule 3's field test and found some 1,300 more CTs
whose image shows C2's foot and the sacrum's top. The census admitted them by SPINEPS's masks alone,
one machine's reading. TotalSegmentator 2.18.0 drew most of them in September, as the ruleclass
census's arm A, whose code is kept on the grid and in no repository; this run reads none of those
maps and makes its own, so that each is reproduced by a command from a record here (the PREREG's
opening). The owner's word of 2026-10-31 00:55 UTC, "you can start the totalsegmentator segmentation
of those scans currently on the grid", is that TotalSegmentator draws them: its total task with
every vertebra, S1 and the sacrum in roi_subset, run on each CT as it lies, so the label map comes
out on the CT's own grid and nothing is resampled. The two machines' maps side by side say where
they agree on which bone is which, which the population priors and the owner's own decoder need
before they read a CT that no person drew (the gold tier is for population priors only, his word of
2026-10-30 21:44 UTC). What is drawn is a machine arm of its own, never pooled with a release's
masks or with SPINEPS's (docs/research/gold4-totalseg/PREREG.md).

The units. Every census row of gold4.json whose verdict is admitted or look, less the releases' own
studies (VerSe, and TotalSegmentator's subjects, the census's collection "ts" among them, whose rows
the census counted as new for want of its prefix, each known by its collection, its case, its mask's
name or its CT's path as the gold tier 3 completion reads them), FDG-PET-CT-Lesions (ENHANCE.PET's autoPET under
TCIA's names, its collection tcia_fdg_pet_ct_lesions and no other), a row whose CT no tier list names,
whose CT is not a NIfTI file on the data root or whose SPINEPS mask is not on the lab volume, and a
second mask of a CT already taken, each counted by its reason; both tier lists are read, or the run
stops. A unit is one CT, named by the sha256 of its path. C-ArmLSpine's, SchwingNet's held out
measurement, and every CT whose person the tier lists mark test only (real_frames 1, a person with
real fluoroscopy, kept for validation and test by the owner's word of 2026-10-31 01:43 UTC) is
segmented and marked held_out so that nothing trains on it.

run, one task of a Slurm array of N: the units in a fixed order, each task starting at its own
place and going round, each unit claimed by creating chains/<chain>/claims/<unit> exclusively, so
the tasks share the list with no plan and a task that ends early leaves its units to the others.
A unit whose run.json records a run that ended 0 with its label map there is passed over, so a send
again carries on where the last stopped; so is one that failed in GIVE_UP_AFTER chains at this
code, whose failure is then the report's to show. The code is tools/run_code.py's digest of the kind
gold4_totalseg, the one the launcher names the run by, read from the copy the job runs: a merge to
main that changes none of the kind's files keeps it, so the gate's sends, each at main's newest
commit, still give a unit up, while a change to them, the segmenter's pin (SEGMENTER) among them,
gives every unit its chances again. For each unit TotalSegmentator writes its
multilabel file to a scratch folder under TMPDIR (/dev/shm on the grid); its labels are turned into
VerSe's ids (C1 to C7 at 1 to 7, T1 to T12 at 8 to 19, L1 to L5 at 20 to 24, and its S1 and sacrum
both at 26, since the owner trusts no segmenter's S1 class and keeps the sacrum one full mask, his
word of 2026-10-30 22:58 UTC) and written as labels/<unit>.nii.gz, int16 as VerSe's copies are,
on the CT's grid, with no label table of TotalSegmentator's own in its header, renamed into place
whole; then each level's voxels and centre in world mm, beside the SPINEPS mask's, its end plates
(200 + X) read as their vertebra X and its discs (100 + X) left out, give the unit's kind (judge)
and, where both maps share one lattice (one grid, or SPINEPS's reoriented, which moves no voxel),
each level's Dice. run.json is written before the segmenter starts (exit null) and again at the
end, so a process killed mid-run leaves a record the next chain counts as that chain's failure,
and an exit TotalSegmentator calls on one CT fails that CT alone. A task stops
after FAILS_IN_A_ROW failures in a row, and takes no new unit once --stop-after seconds have passed,
an hour short of the job's time limit. Its lines go to chains/<chain>/tasks/<task>.txt.

merge, once the array has ended: every unit's record into records.jsonl, under the chain and at the
top, and the counts into chains/<chain>/REPORT.md, which the job script prints into the gate's
report: counts by reason, by kind, by collection and by region, and the PREREG's three bars read from
them, never a path, a case or a person.

Exits: run 0 where every unit it took ended 0, 1 where any failed, 2 where an input is missing, the
code cannot be named or the environment holds another version than SEGMENTER, 4 where torch sees no
GPU; merge 0 where every unit is segmented or given up, 3 where some are not yet, 2 where the chain
has no jobs.json or the code cannot be named. Standard library here; numpy and nibabel are imported where
a map is read, torch and totalsegmentator where they run, so the rest is tested without them
(tests/test_gold4_totalseg_grid.py). tools/ leaves sys.path before anything else, since
tools/profile.py would shadow the standard library's profile, which torch's imports reach.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import socket
import statistics
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:] = [entry for entry in sys.path if Path(entry or ".").resolve() != ROOT / "tools"]

KIND = "gold4_totalseg"
# The version the job's environment installs (grid/totalseg-gold4.sbatch's TS_PIN, which
# tests/test_gold4_totalseg_grid.py holds equal to this): kept here too so that a new version is a
# change to this file, which names a new code (tools/run_code.py) and so gives every unit its chances again.
SEGMENTER = "TotalSegmentator==2.18.0"
TIER_FILES = ("tier1.tsv", "tier2.tsv")
VERDICTS = ("admitted", "look")
# The releases' own studies: the census's reading of a collection (tools/gold3_census.py,
# MEMBER_OF_COLLECTION), the collection "ts" it missed, and the ids a case, a mask's name or a CT's
# path carries, as the gold tier 3 completion reads them (tools/gold3_complete_grid.py): VerSe's
# series as VerSeFusion lays them out, scan-<id>/scan-<id>_ct.nii.gz, and TotalSegmentator's
# subjects as its release does, <s>/ct.nii.gz.
RELEASE_PREFIXES = ("verse", "totalseg", "ts_")
RELEASE_COLLECTIONS = ("ts",)
TS_IN_CASE = re.compile(r"^ts:(s\d{4})$")
TS_IN_MASK = re.compile(r"TSV3C?_(s\d{4})_")
TS_IN_PATH = re.compile(r"/(s\d{4})/ct\.nii(\.gz)?$")
VERSE_IN_MASK = re.compile(r"VERSE_([A-Za-z0-9]+)_")
VERSE_IN_PATH = re.compile(r"scan-([A-Za-z0-9]+)_ct\b")
# SchwingNet's held out measurement: its CTs are segmented and marked, and nothing trains on them; so
# is every CT whose person a tier list marks test only (TEST_ONLY in its column real_frames), since
# that person's real fluoroscopy is kept for validation and test and a render inherits its CT's person.
HELD_OUT = ("carmlspine",)
TEST_ONLY = "1"
# FDG-PET-CT-Lesions by the collection the tier lists and the census spell it with, and no other: a
# collection whose name only holds "fdg", as IDC's ACRIN-NSCLC-FDG-PET, is no autoPET.
FDG_COLLECTIONS = ("tcia_fdg_pet_ct_lesions",)
NIFTI = (".nii.gz", ".nii")
WHY = {
    "release": "a release's own study (VerSe or TotalSegmentator), drawn by hand already",
    "fdg": "FDG-PET-CT-Lesions, ENHANCE.PET's autoPET under TCIA's names",
    "no_tier_row": "no tier list row names its CT",
    "second_mask": "a second SPINEPS mask of a CT already taken",
    "not_nifti": "its CT is not a NIfTI file",
    "no_ct": "its CT is not on the data root",
    "no_spineps": "its SPINEPS mask is not on the lab volume",
}

TS_VERTEBRAE = (*[f"C{i}" for i in range(1, 8)], *[f"T{i}" for i in range(1, 13)], *[f"L{i}" for i in range(1, 6)])
# TotalSegmentator's class to VerSe's id; its S1 and its sacrum are the one sacrum, 26.
VERSE_ID = {**{f"vertebrae_{name}": i + 1 for i, name in enumerate(TS_VERTEBRAE)}, "vertebrae_S1": 26, "sacrum": 26}
# VerSe's ids read as names, as the census reads SPINEPS's masks: 26 and 29 are both the sacrum.
VERSE_NAMES = {**{i: f"C{i}" for i in range(1, 8)}, **{7 + i: f"T{i}" for i in range(1, 13)},
               **{19 + i: f"L{i}" for i in range(1, 7)}, 26: "sacrum", 28: "T13", 29: "sacrum"}
IDS_OF = {}
for _id, _name in VERSE_NAMES.items():
    IDS_OF.setdefault(_name, []).append(_id)
ORDER = (*[f"C{i}" for i in range(1, 8)], *[f"T{i}" for i in range(1, 14)], *[f"L{i}" for i in range(1, 7)], "sacrum")
# SPINEPS's instance mask labels vertebra X's end plates 200 + X and the disc below it 100 + X (its
# README, the instance mask's labels): an end plate is bone of its vertebra, which TotalSegmentator's
# class holds whole, while a disc is no bone and stays outside VerSe's ids.
END_PLATES = 200
# The levels both segmenters can name in the field the census admitted, C2's foot to the sacrum's top.
SPAN = tuple(name for name in TS_VERTEBRAE if name not in ("C1",))
VARIANTS = ("T13", "L6")
# C1 is a region of its own: it lies above the field the census admitted, so how much of it a field
# holds, and so its Dice, moves with where the field ends, and its median is reported with no bar.
REGIONS = ("C1", "C", "T", "L", "sacrum")
# The PREREG's bars (docs/research/gold4-totalseg/PREREG.md, part 4), which the merge reads from the records;
# C1's and the sacrum's Dice have none, the sacrum's since the two machines' sacrum masks are not drawn to
# one definition, and the cervical bar, C2 to C7, is lower, since one boundary voxel weighs more in a
# smaller bone's Dice.
BARS = {"H1": 0.90, "H2": 0.80}
DICE_BARS = {"C": 0.80, "T": 0.85, "L": 0.85}
NOT_WHOLE = ("no_c2", "no_sacrum", "sacrum_above")
COMPARED = ("concordant", "name_shift", "unmatched")
TASK = {"task": "total", "roi_subset": list(VERSE_ID), "fast": False, "ml": True}
KINDS = ("concordant", "variant", "name_shift", "unmatched", "no_c2", "no_sacrum", "sacrum_above", "no_comparison")
MIN_VOXELS = 200                # drawn at all, as the field test and the matcher count a level
MATCH_MM = 10.0                 # two centres this close are one bone
AFFINE_SLACK_MM = 0.01          # two grids whose corner voxels lie this close are one grid
FAILS_IN_A_ROW = 3
GIVE_UP_AFTER = 2               # chains at one code in which a unit failed before it is left to the report
STOP_AFTER = 39600              # seconds after which a task takes no new unit: an hour short of 12 hours
REASON_CHARS = 160
COLLECTION_LINES = 25
# TotalSegmentator 2.18.0 asks for all five parts of the total task (Dataset291 to 295) before it
# applies roi_subset, and downloads any it lacks; every vertebra and the sacrum are part 292, and the
# 6 mm model (298) crops, so the other four are never computed for this roi_subset (as for the gold
# tier 3 completion, tools/gold3_totalseg_grid.py) and the guard passes over them; any other missing
# part is refused, so the job downloads nothing.
PARTS_NEEDED = (292, 298)
PARTS_NOT_COMPUTED = (291, 293, 294, 295)


class InputsMissing(Exception):
    """An input the run cannot start without, said in words."""


# ---- small helpers ---------------------------------------------------------------------------------

def utc(seconds=None):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(seconds))


def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def part_beside(path, suffix=".part"):
    """A file of its own beside path, made exclusively, for a write that is renamed into place: the
    tasks of an array run on several nodes, where two processes may hold one pid."""
    handle, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=suffix, dir=path.parent)
    os.close(handle)
    return Path(name)


def write_json(path, value):
    """A JSON file written whole under a name of its own and renamed into place, so a reader never sees
    half of one and two tasks writing the same bytes never meet."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    part = part_beside(path)
    part.write_text(json.dumps(value, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(part, path)


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def short(text, chars=REASON_CHARS):
    text = " ".join(str(text).split())
    return text if len(text) <= chars else text[:chars - 3] + "..."


def n(value):
    return f"{value:,}"


# ---- which CTs ---------------------------------------------------------------------------------------

def read_census(path):
    """The census's gold4 rows, as part gold4 wrote them."""
    if not os.path.isfile(path):
        raise InputsMissing(f"no census detail at {path} (the gate word census gold3 writes it)")
    rows = (read_json(path) or {}).get("rows")
    if not isinstance(rows, list):
        raise InputsMissing(f"the census detail {os.path.basename(path)} holds no list of rows")
    return rows


def read_tiers(folder):
    """({SPINEPS mask: its CT}, the CTs and persons the lists mark test only, and the sha256 of each list
    read), the first row of a mask keeping its place. Both lists are read, or the run stops: one alone
    would leave most units out as rows no tier list names, and the run would still end 0."""
    ct_of, test_only, read = {}, {"ct": set(), "person": set()}, {}
    for name in TIER_FILES:
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            raise InputsMissing(f"no census tier list {name} under {folder} (both of {' and '.join(TIER_FILES)} are read)")
        read[name] = sha256_of(path)
        with open(path, encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh, delimiter="\t"):
                mask, ct = row.get("spineps_vert") or "", row.get("ct_path") or ""
                if mask and ct:
                    ct_of.setdefault(mask, ct)
                if (row.get("real_frames") or "").strip() == TEST_ONLY:
                    test_only["ct"].add(ct)
                    test_only["person"].add(row.get("person_key") or "")
    test_only["ct"].discard("")
    test_only["person"].discard("")
    return ct_of, test_only, read


def folded(collection):
    return "idc" if collection.lower().startswith("idc_") else collection


def release_study(row, ct=""):
    """Whether the row is a release's own study, by its collection, its case, its mask's name or its CT's path."""
    collection = (row.get("collection") or "").lower()
    if collection in RELEASE_COLLECTIONS or collection.startswith(RELEASE_PREFIXES):
        return True
    case, mask = row.get("case_id") or "", row.get("spineps_vert") or ""
    return bool(TS_IN_CASE.match(case) or TS_IN_MASK.search(mask) or VERSE_IN_MASK.search(mask)
                or TS_IN_PATH.search(ct) or VERSE_IN_PATH.search(ct))


def left_out_reason(row, ct_of, taken, exists):
    """Why a candidate row is no unit, as a key of WHY, or None."""
    ct = ct_of.get(row.get("spineps_vert") or "")
    if release_study(row, ct or ""):
        return "release"
    if (row.get("collection") or "").lower() in FDG_COLLECTIONS:
        return "fdg"
    if not ct:
        return "no_tier_row"
    if ct in taken:
        return "second_mask"
    if not ct.endswith(NIFTI):
        return "not_nifti"
    if not exists(ct):
        return "no_ct"
    if not exists(row["spineps_vert"]):
        return "no_spineps"
    return None


def unit_id(ct):
    return hashlib.sha256(ct.encode("utf-8")).hexdigest()[:16]


def held_out(collection, ct, person, test_only):
    """Whether nothing may train on the CT: SchwingNet's held out measurement, or a CT or person the tier
    lists mark test only."""
    test_only = test_only or {}
    return (folded(collection).lower() in HELD_OUT or ct in test_only.get("ct", ())
            or bool(person) and person in test_only.get("person", ()))


def unit_of(row, ct, test_only=None):
    collection, person = row.get("collection") or "", row.get("person_key") or ""
    return {"id": unit_id(ct), "collection": collection, "group": folded(collection), "case_id": row.get("case_id") or "",
            "person_key": person, "tier": row.get("tier") or "", "ct": ct, "spineps": row["spineps_vert"],
            "census": {k: row.get(k) for k in ("verdict", "head", "foot", "complete", "flags")},
            "held_out": held_out(collection, ct, person, test_only)}


def select(rows, ct_of, exists=os.path.isfile, test_only=None):
    """(units, left out by reason, left out by reason and collection, candidates): one unit per CT, in
    a fixed order whatever order the census lists its rows in."""
    candidates = sorted((r for r in rows if isinstance(r, dict) and r.get("verdict") in VERDICTS),
                        key=lambda r: (r.get("collection") or "", r.get("case_id") or "", r.get("spineps_vert") or ""))
    units, left_out, by_collection, taken = [], Counter(), {}, set()
    for row in candidates:
        why = left_out_reason(row, ct_of, taken, exists)
        if why:
            left_out[why] += 1
            group = by_collection.setdefault(why, Counter())
            group[folded(row.get("collection") or "")] += 1
            continue
        ct = ct_of[row["spineps_vert"]]
        taken.add(ct)
        units.append(unit_of(row, ct, test_only))
    return units, left_out, by_collection, len(candidates)


def selection(census, tiers, exists=os.path.isfile):
    """What a chain runs, as jobs.json holds it: the same bytes from every task of the chain."""
    rows = read_census(census)
    ct_of, test_only, tier_sums = read_tiers(tiers)
    units, left_out, by_collection, candidates = select(rows, ct_of, exists, test_only)
    return {"census": census, "census_sha256": sha256_of(census), "tiers": tier_sums, "verdicts": list(VERDICTS),
            "segmenter": "TotalSegmentator", "task": TASK, "label_ids": "VerSe (C1 to C7 1 to 7, T1 to T12 8 to 19, "
            "L1 to L5 20 to 24, S1 and sacrum 26)", "candidates": candidates, "units": units,
            "left_out": dict(sorted(left_out.items())),
            "left_out_by_collection": {why: dict(sorted(c.items())) for why, c in sorted(by_collection.items())}}


# ---- sharing the units among the tasks ---------------------------------------------------------------

def rotated(units, task, tasks):
    """The units from this task's own place, going round, so each task starts on a part of its own."""
    start = (task * len(units)) // tasks if units and tasks else 0
    return units[start:] + units[:start]


def claim(folder, uid, task):
    """The unit taken for this task where no task of the chain has taken it, by an exclusive create."""
    folder.mkdir(parents=True, exist_ok=True)
    try:
        handle = os.open(folder / uid, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(handle, "w", encoding="utf-8") as fh:
        fh.write(f"task {task} at {utc()}\n")
    return True


def labels_path(out, uid):
    return Path(out) / "labels" / f"{uid}.nii.gz"


def record_path(out, uid):
    return Path(out) / "units" / uid / "run.json"


def segmented(out, uid, ran=None):
    """Whether the unit's last run ended 0 and its label map stands."""
    ran = read_json(record_path(out, uid)) if ran is None else ran
    return isinstance(ran, dict) and ran.get("exit") == 0 and labels_path(out, uid).is_file()


def earlier_failures(ran, running=None):
    """Every failure the unit's record holds, at whatever code: those its failed list keeps, and the
    record's own run where its process ended mid-run (exit null) in a chain that is not one still
    running, at the commit and code that run had."""
    if not isinstance(ran, dict) or ran.get("exit") == 0:
        return []
    found = [dict(f) for f in ran.get("failed") or [] if isinstance(f, dict) and f.get("chain")]
    if ran.get("exit") is None and ran.get("chain") not in (None, running):
        found.append({"chain": ran["chain"], "commit": ran.get("commit"), "code": ran.get("code")})
    return found


def failures_of(ran, code, running=None):
    """The chains whose run of the unit failed at this code, tools/run_code.py's digest of the kind."""
    return {f["chain"] for f in earlier_failures(ran, running) if code and f.get("code") == code}


def given_up(ran, code, running=None):
    return len(failures_of(ran, code, running)) >= GIVE_UP_AFTER


def code_digest(root=ROOT):
    """tools/run_code.py's digest of this kind's files under root, the copy the job runs: the code the
    launcher names the run by and a unit's failures are counted at. Loaded by its path, as
    flows/launch.py loads it, since tools/ is off sys.path."""
    spec = importlib.util.spec_from_file_location("gold4_run_code", Path(root) / "tools" / "run_code.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.digest(KIND, root)


def code_problem(args):
    """None once args.code holds the code, read from the copy where the words name none; else why it
    cannot be named, which stops the part, since no failure could be counted at it."""
    if getattr(args, "code", ""):
        return None
    try:
        args.code = code_digest()
    except Exception as exc:                                    # noqa: BLE001 - said in words, and the part stops
        return f"the code cannot be named by tools/run_code.py ({type(exc).__name__}: {short(exc)})"
    return None


# ---- the segmenter -----------------------------------------------------------------------------------

def gpu_name():
    """The first card torch sees, or None, so a task never segments on the CPU unawares."""
    try:
        import torch
    except ImportError:
        return None
    return torch.cuda.get_device_name(0) if torch.cuda.is_available() else None


def segmenter_version():
    try:
        from importlib.metadata import version
        return version("TotalSegmentator")
    except Exception:                                           # noqa: BLE001
        return "not read"


def version_problem(version):
    """Why the environment's TotalSegmentator is not the one SEGMENTER pins, or None; a version that
    could not be read passes, since every record says it."""
    pinned = SEGMENTER.split("==", 1)[1]
    if version in ("not read", pinned):
        return None
    return f"the environment holds TotalSegmentator {version}, not {pinned} as SEGMENTER and the job's TS_PIN say"


def has_part(weights, part, whole=False):
    """Whether the weights folder holds the unpacked Dataset folder of this part, marked whole where asked."""
    prefix = f"Dataset{int(part):03d}_"
    if not weights or not os.path.isdir(weights):
        return False
    return any(name.startswith(prefix) and (not whole or os.path.isfile(os.path.join(weights, name, "UNPACKED")))
               for name in os.listdir(weights))


def weights_guard(weights):
    """What stands in for TotalSegmentator's download_pretrained_weights: a part the folder holds needs
    nothing, a part this roi_subset never computes is passed over, and any other is refused."""
    def guard(*given, **words):
        part = given[0] if given else words.get("task_id")
        if has_part(weights, part) or int(part) in PARTS_NOT_COMPUTED:
            return None
        raise RuntimeError(f"TotalSegmentator asked for weight part {part}, which the weights folder lacks; the job downloads nothing")
    return guard


def run_totalseg(ct, dest, args):
    """TotalSegmentator's Python entry on one CT, its multilabel file written to dest."""
    import totalsegmentator.python_api as api
    held = api.download_pretrained_weights
    api.download_pretrained_weights = weights_guard(args.weights)
    try:
        api.totalsegmentator(str(ct), str(dest), ml=TASK["ml"], task=TASK["task"], roi_subset=list(TASK["roi_subset"]),
                             fast=TASK["fast"], device=args.device, quiet=True, nr_thr_resamp=args.threads,
                             nr_thr_saving=args.threads)
    finally:
        api.download_pretrained_weights = held


def ts_ids():
    """{class name: TotalSegmentator's id} of the classes asked, from its own class map."""
    from totalsegmentator.map_to_binary import class_map
    ids = {name: int(value) for value, name in class_map["total"].items()}
    missing = [name for name in VERSE_ID if name not in ids]
    if missing:
        raise RuntimeError(f"TotalSegmentator's total task names no {', '.join(missing)}, so its labels cannot be read as VerSe's")
    return {name: ids[name] for name in VERSE_ID}


def home_for(out, task):
    """The task's own TOTALSEG_HOME_DIR, usage statistics off: TotalSegmentator rewrites its config
    after every CT, and tasks sharing one would read each other's half-written file."""
    home = Path(out) / "home" / f"task-{task}"
    home.mkdir(parents=True, exist_ok=True)
    config = home / "config.json"
    if not config.is_file():
        config.write_text(json.dumps({"totalseg_id": f"schwingnet-gold4-{task}", "send_usage_stats": False,
                                      "prediction_counter": 0}) + "\n", encoding="utf-8")
    return home


# ---- reading the maps (numpy and nibabel) --------------------------------------------------------------

def load_map(path):
    """(the label voxels as a 3-D array, the affine, the image) of a NIfTI file."""
    import nibabel as nib
    import numpy as np
    image = nib.load(str(path))
    data = np.asanyarray(image.dataobj)
    if data.ndim == 4 and data.shape[3] == 1:
        data = data[..., 0]
    if data.ndim != 3:
        raise ValueError(f"{os.path.basename(str(path))} holds a {data.ndim}-D image, not a 3-D label map")
    return data, np.asarray(image.affine, dtype=float), image


def as_labels(values):
    """Integer labels of a map that may hold them as floats."""
    import numpy as np
    return np.rint(values).astype(np.int64) if values.dtype.kind == "f" else values


def bounding_box(mask):
    """The smallest box holding every True voxel, as slices, or None where there is none."""
    import numpy as np
    box = []
    for axis in range(mask.ndim):
        rest = tuple(a for a in range(mask.ndim) if a != axis)
        hit = np.flatnonzero(mask.any(axis=rest))
        if hit.size == 0:
            return None
        box.append(slice(int(hit[0]), int(hit[-1]) + 1))
    return tuple(box)


def to_verse(values, ids):
    """(VerSe's map of TotalSegmentator's labels, int16, and the voxels it drew of each class asked,
    with "other" for any label it was not asked for)."""
    import numpy as np
    values = as_labels(np.asarray(values))
    verse = np.zeros(values.shape, dtype=np.int16)
    box = bounding_box(values != 0)
    counts = {name: 0 for name in ids}
    counts["other"] = 0
    if box is None:
        return verse, counts
    crop = values[box]
    if crop.min() < 0 or crop.max() > 255:
        raise ValueError(f"its output holds labels outside 0 to 255 ({int(crop.min())} to {int(crop.max())})")
    crop = crop.astype(np.uint8, copy=False)
    table = np.zeros(256, dtype=np.int16)
    for name, value in ids.items():
        table[value] = VERSE_ID[name]
    verse[box] = table[crop]
    drawn = np.bincount(crop.ravel(), minlength=256)
    asked = set(ids.values())
    counts = {name: int(drawn[value]) for name, value in ids.items()}
    counts["other"] = int(sum(int(drawn[v]) for v in range(1, 256) if v not in asked))
    return verse, counts


def with_end_plates(values):
    """(SPINEPS's map with each end plate read as its vertebra, the end-plate voxels so read): 200 + X
    becomes X for each id X that names a level; the discs, 100 + X, are left as they are, outside VerSe's ids."""
    import numpy as np
    labels = as_labels(np.asarray(values))
    where = np.nonzero((labels > END_PLATES) & (labels <= END_PLATES + max(VERSE_NAMES)))
    vertebra = labels[where] - END_PLATES
    named = np.isin(vertebra, list(VERSE_NAMES))
    if not named.any():
        return labels, 0
    # A copy, so a map nibabel memory-mapped from its file is never written into.
    labels = labels.copy()
    labels[tuple(axis[named] for axis in where)] = vertebra[named]
    return labels, int(named.sum())


def level_facts(labels, affine):
    """({level name: {voxels, centroid in world mm}} of a map in VerSe's ids, two ids of one name as one
    level, and how many ids it holds that name nothing)."""
    import numpy as np
    box = bounding_box(labels != 0)
    if box is None:
        return {}, 0
    crop = as_labels(labels[box])
    offset = np.array([s.start for s in box], dtype=float)
    sums, outside = {}, 0
    for value in np.unique(crop):
        if value == 0:
            continue
        name = VERSE_NAMES.get(int(value))
        if name is None:
            outside += 1
            continue
        where = np.nonzero(crop == value)
        count = int(where[0].size)
        total = np.array([float(w.sum()) for w in where]) + offset * count
        before = sums.get(name, (0, np.zeros(3)))
        sums[name] = (before[0] + count, before[1] + total)
    facts = {}
    for name, (count, total) in sums.items():
        world = affine[:3, :3] @ (total / count) + affine[:3, 3]
        facts[name] = {"voxels": count, "centroid": [round(float(v), 2) for v in world]}
    return facts, outside


def corners(shape, affine):
    """The world points, in mm, of a grid's corner voxels."""
    import itertools
    import numpy as np
    affine = np.asarray(affine, float)
    ends = np.array(list(itertools.product(*[(0, max(int(size) - 1, 0)) for size in shape[:3]])), float)
    return ends @ affine[:3, :3].T + affine[:3, 3]


def same_grid(a_shape, a_affine, b_shape, b_affine):
    """Whether two grids are one: one shape, and every corner voxel within AFFINE_SLACK_MM of its twin.
    Two affines differ by an affine map, whose largest move over the box lies at a corner, so no voxel
    of the grid lies further from its twin than the corners do."""
    import numpy as np
    if tuple(a_shape) != tuple(b_shape):
        return False
    return bool(np.abs(corners(a_shape, a_affine) - corners(b_shape, b_affine)).max() <= AFFINE_SLACK_MM)


def on_our_lattice(theirs, theirs_affine, shape, affine):
    """(SPINEPS's map on TotalSegmentator's grid, how) where the two maps share one lattice: "same" where the
    grids are one, "reoriented" where only the axes' order or sign differs, which moves no voxel; (None,
    "another lattice") where only a resampling would bridge them, which would put its own error into the
    Dice, so the centres alone compare the two (docs/research/gold4-totalseg/PREREG.md, part 3)."""
    import nibabel as nib
    if same_grid(theirs.shape, theirs_affine, shape, affine):
        return theirs, "same"
    try:
        turn = nib.orientations.ornt_transform(nib.io_orientation(theirs_affine), nib.io_orientation(affine))
        moved = nib.orientations.apply_orientation(theirs, turn)
        moved_affine = theirs_affine @ nib.orientations.inv_ornt_aff(turn, theirs.shape)
    except Exception:                                           # noqa: BLE001 - an affine no axis order fits
        return None, "another lattice"
    if same_grid(moved.shape, moved_affine, shape, affine):
        return moved, "reoriented"
    return None, "another lattice"


def dice_by_level(ours, theirs, names):
    """Each named level's Dice between two maps of one grid in VerSe's ids, the sacrum as 26 or 29."""
    import numpy as np
    box = bounding_box((ours != 0) | (theirs != 0))
    if box is None:
        return {}
    a, b = as_labels(ours[box]), as_labels(theirs[box])
    found = {}
    for name in names:
        in_a, in_b = np.isin(a, IDS_OF[name]), np.isin(b, IDS_OF[name])
        total = int(in_a.sum()) + int(in_b.sum())
        if total:
            found[name] = round(2.0 * int((in_a & in_b).sum()) / total, 4)
    return found


def save_labels(verse, affine, header, dest):
    """The map written whole: a part file under a name of its own, renamed into place, or removed where
    the write fails. TotalSegmentator's header carries its own label table as an extension (its
    nifti_ext_header), whose names are its ids' and not VerSe's, so the map keeps no extension."""
    import nibabel as nib
    import numpy as np
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    image = nib.Nifti1Image(verse.astype(np.int16, copy=False), affine, header)
    image.header.extensions.clear()
    image.set_data_dtype(np.int16)
    image.header.set_slope_inter(1, 0)
    part = part_beside(dest, suffix=".part.nii.gz")
    try:
        nib.save(image, str(part))
        os.replace(part, dest)
    except BaseException:
        part.unlink(missing_ok=True)
        raise


# ---- the unit's kind (standard library) ----------------------------------------------------------------

def drawn_levels(facts):
    """{name: centre} of the levels drawn at all."""
    return {name: f["centroid"] for name, f in (facts or {}).items() if f.get("voxels", 0) >= MIN_VOXELS}


def distance(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def matched(ours, theirs):
    """(pairs of names, one bone each, and the levels of either left with no partner), within SPAN: the
    nearest centres first, each level in one pair at most, no pair further apart than MATCH_MM."""
    a = {name: c for name, c in ours.items() if name in SPAN}
    b = {name: c for name, c in theirs.items() if name in SPAN}
    near = sorted((distance(ca, cb), na, nb) for na, ca in a.items() for nb, cb in b.items())
    pairs, used_a, used_b = [], set(), set()
    for gap, na, nb in near:
        if gap > MATCH_MM:
            break
        if na in used_a or nb in used_b:
            continue
        pairs.append((na, nb))
        used_a.add(na)
        used_b.add(nb)
    alone = sorted([("totalseg", name) for name in a if name not in used_a] + [("spineps", name) for name in b if name not in used_b])
    return pairs, alone


def lowest_below_c2(drawn):
    """The lowest level drawn below C2 and above the sacrum, or None."""
    below_c2 = [name for name in ORDER[ORDER.index("C2") + 1:-1] if name in drawn]
    return below_c2[-1] if below_c2 else None


def place_down(drawn):
    """A point's place down the column of a map whose C2 is drawn, in mm along the line from C2's centre to
    the lowest level's below it; None where no such level gives the line a length."""
    low = lowest_below_c2(drawn)
    if low is None:
        return None
    c2 = drawn["C2"]
    axis = [l - c for l, c in zip(drawn[low], c2)]
    length = math.sqrt(sum(v * v for v in axis))
    if length == 0:
        return None
    return lambda point: sum((p - c) * a for p, c, a in zip(point, c2, axis)) / length


def sacrum_above(drawn):
    """Whether the sacrum's centre lies no lower than the lowest level above it, along the column: an anatomy
    no spine has."""
    place = place_down(drawn)
    return place is not None and place(drawn["sacrum"]) <= place(drawn[lowest_below_c2(drawn)])


def above_the_other(point, other, place):
    """Whether a level's centre lies above every vertebra the other map draws, C1 to L5: a level one map draws
    past the top of the other's field, which is coverage, since the census admitted fields that show only
    C2's foot, and no disagreement on any bone's name. A C1 the other draws counts in its top, since a level
    that lies below the other's C1 is inside its field, not past it. Below the top no level is passed over:
    the foot of the column is where the count's variants lie."""
    places = [place(c) for name, c in other.items() if name in TS_VERTEBRAE]
    return bool(places) and place(point) < min(places)


def judge(ours, theirs):
    """The unit's kind, the first that holds: no_c2 and no_sacrum where TotalSegmentator drew no C2 or no
    sacrum; sacrum_above where its sacrum lies above its lowest level; no_comparison where SPINEPS's map
    could not be read; variant where SPINEPS draws a T13 or an L6, which TotalSegmentator has no class
    for, so their names below it cannot agree; name_shift where one bone has two names; unmatched where
    no bone pairs, or where a level of either has no partner and lies below the top of the other's
    levels (above_the_other); else concordant."""
    drawn = drawn_levels(ours)
    if "C2" not in drawn:
        return "no_c2"
    if "sacrum" not in drawn:
        return "no_sacrum"
    if sacrum_above(drawn):
        return "sacrum_above"
    if theirs is None:
        return "no_comparison"
    others = drawn_levels(theirs)
    if any(name in others for name in VARIANTS):
        return "variant"
    pairs, alone = matched(drawn, others)
    if any(a != b for a, b in pairs):
        return "name_shift"
    if not pairs:
        return "unmatched"
    place = place_down(drawn)
    maps = {"totalseg": (drawn, others), "spineps": (others, drawn)}
    inside = [name for who, name in alone if place is None or not above_the_other(maps[who][0][name], maps[who][1], place)]
    return "unmatched" if inside else "concordant"


# ---- one unit --------------------------------------------------------------------------------------------

def measure(raw, dest, spineps, ids):
    """TotalSegmentator's multilabel file turned into VerSe's map and written to dest, its levels, and
    SPINEPS's beside them, its end plates read as their vertebrae; the facts for run.json."""
    values, affine, image = load_map(raw)
    verse, counts = to_verse(values, ids)
    del values
    save_labels(verse, affine, image.header, dest)
    ours, _ = level_facts(verse, affine)
    found = {"totalseg_voxels": counts, "levels": ours, "shape": list(verse.shape), "labels_sha256": sha256_of(dest)}
    try:
        theirs_map, theirs_affine, _ = load_map(spineps)
        theirs_map, plates = with_end_plates(theirs_map)
        theirs, outside = level_facts(theirs_map, theirs_affine)
    except Exception as exc:                                    # noqa: BLE001 - the segmentation stands without its comparison
        found.update(spineps_error=f"{type(exc).__name__}: {short(exc)}", kind=judge(ours, None))
        return found
    aligned, grid = on_our_lattice(theirs_map, theirs_affine, verse.shape, affine)
    found.update(spineps=theirs, spineps_end_plate_voxels=plates, spineps_outside_ids=outside, grid=grid, kind=judge(ours, theirs))
    if aligned is not None:
        both = [name for name in drawn_levels(ours) if name in drawn_levels(theirs)]
        found["dice"] = dice_by_level(verse, aligned, both)
    return found


def segment_one(unit, out, args, segment=run_totalseg, ids=None):
    """One unit run and recorded: run.json written before the segmenter starts and again at its end,
    every failure it had before kept with the code it failed at."""
    uid = unit["id"]
    failed = earlier_failures(read_json(record_path(out, uid)), running=args.chain)
    began = time.time()
    record = {"unit": uid, "exit": None, "chain": args.chain, "task": args.task, "commit": args.commit, "code": args.code,
              "host": socket.gethostname(), "gpu": args.gpu, "version": segmenter_version(), "began": utc(began)}
    if failed:
        record["failed"] = failed
    write_json(record_path(out, uid), record)
    scratch = Path(tempfile.mkdtemp(prefix=f"gold4-{uid}-"))
    try:
        raw = scratch / "totalseg.nii.gz"
        segment(unit["ct"], raw, args)
        record.update(measure(raw, labels_path(out, uid), unit["spineps"], ids or ts_ids()))
        record["exit"] = 0
        record.pop("failed", None)
    except (Exception, SystemExit) as exc:                     # noqa: BLE001 - one CT never stops the others
        # TotalSegmentator calls sys.exit where its input is not there (nnunet.py), which would end the task.
        record["exit"] = 1
        record["error"] = f"{type(exc).__name__}: {short(exc)}"
        record["failed"] = failed + [{"chain": args.chain, "commit": args.commit, "code": args.code}]
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    record["seconds"] = round(time.time() - began, 1)
    record["ended"] = utc()
    write_json(record_path(out, uid), record)
    return record


class TaskLines:
    """The task's lines, kept in chains/<chain>/tasks/<task>.txt for the flow's page and the gate."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def say(self, line):
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(f"{utc()} {line}\n")
        print(line, flush=True)


def run(args, segment=run_totalseg, ids=None, clock=time.monotonic):
    out, chain = Path(args.out), Path(args.out) / "chains" / args.chain
    lines = TaskLines(chain / "tasks" / f"{args.task}.txt")
    try:
        jobs = selection(args.census, args.tiers)
    except InputsMissing as missing:
        lines.say(f"task {args.task}: stopped before any CT: {missing}")
        return 2
    write_json(chain / "jobs.json", jobs)
    units = jobs["units"]
    lacking = [str(part) for part in PARTS_NEEDED if not has_part(args.weights, part, whole=True)]
    if lacking:
        lines.say(f"task {args.task}: stopped before any CT: no whole Dataset{' or Dataset'.join(lacking)} folder in the weights folder")
        return 2
    problem = code_problem(args) or version_problem(segmenter_version())
    if problem:
        lines.say(f"task {args.task}: stopped before any CT: {problem}")
        return 2
    args.gpu = gpu_name() if args.device == "gpu" else args.device
    if not args.gpu:
        lines.say(f"task {args.task}: stopped before any CT: torch sees no GPU")
        return 4
    os.environ["TOTALSEG_WEIGHTS_PATH"] = str(args.weights)
    os.environ["TOTALSEG_HOME_DIR"] = str(home_for(out, args.task))
    lines.say(f"task {args.task} of {args.tasks}: {n(len(units))} units in the chain's list; code {args.code[:12]}; GPU {args.gpu}")
    began, tally, in_a_row = clock(), Counter(), 0
    for unit in rotated(units, args.task, args.tasks):
        ran = read_json(record_path(out, unit["id"]))
        if segmented(out, unit["id"], ran) or given_up(ran, args.code, running=args.chain):
            tally["passed over"] += 1
            continue
        if clock() - began > args.stop_after:
            lines.say(f"task {args.task}: {args.stop_after} s have passed, so it takes no new unit")
            break
        if not claim(chain / "claims", unit["id"], args.task):
            continue
        record = segment_one(unit, out, args, segment, ids)
        tally["segmented" if record["exit"] == 0 else "failed"] += 1
        in_a_row = 0 if record["exit"] == 0 else in_a_row + 1
        said = record.get("kind") if record["exit"] == 0 else record["error"].split(":")[0]
        # No unit's id: the job copies a task's last line into the report, which carries counts alone.
        lines.say(f"task {args.task}: a CT ended exit {record['exit']} ({said}) in {record['seconds']} s; "
                  f"{tally['segmented']} segmented, {tally['failed']} failed, {tally['passed over']} passed over")
        if in_a_row >= FAILS_IN_A_ROW:
            lines.say(f"task {args.task}: stopped after {FAILS_IN_A_ROW} failures in a row")
            return 1
    lines.say(f"task {args.task}: ended: {tally['segmented']} segmented, {tally['failed']} failed, {tally['passed over']} passed over")
    return 1 if tally["failed"] else 0


# ---- the merge and its report ------------------------------------------------------------------------------

def status_of(out, uid, ran, code):
    if segmented(out, uid, ran):
        return "segmented"
    if not isinstance(ran, dict):
        return "not run"
    return "given up" if given_up(ran, code) else "failed"


def error_kind(ran):
    if ran.get("exit") is None:
        return "ended mid-run (killed, out of memory or out of time)"
    return (ran.get("error") or "no error said").split(":")[0]


def merged_record(unit, ran, status):
    """One unit's line of records.jsonl, which stays on the lab volume: who and where it is, with the
    CT's and the SPINEPS mask's paths that a later reader joins on, and what its last run found."""
    record = {k: unit[k] for k in ("id", "collection", "group", "case_id", "person_key", "tier", "held_out", "census", "ct")}
    record["spineps_mask"] = unit["spineps"]
    record["status"] = status
    if isinstance(ran, dict):
        for key in ("exit", "chain", "commit", "code", "seconds", "version", "gpu", "kind", "levels", "spineps", "grid", "dice",
                    "totalseg_voxels", "spineps_end_plate_voxels", "spineps_outside_ids", "labels_sha256", "error",
                    "spineps_error", "failed"):
            if key in ran:
                record[key] = ran[key]
    if status == "segmented":
        record["labels"] = f"labels/{unit['id']}.nii.gz"
    return record


def region_of(name):
    return name if name in ("C1", "sacrum") else name[0]


def concordant_dice(records):
    """({region: the Dice of each level} over the concordant units whose two maps share a lattice, and how
    many units those are by how the lattice was shared)."""
    dice, lattice = {region: [] for region in REGIONS}, Counter()
    for r in records:
        if r["status"] == "segmented" and r.get("kind") == "concordant" and r.get("grid") in ("same", "reoriented"):
            lattice[r["grid"]] += 1
            for name, value in (r.get("dice") or {}).items():
                dice[region_of(name)].append(value)
    return dice, lattice


def share_line(name, what, hits, total, bar):
    if not total:
        return f"  - {name}, {what}: not tested, no unit to read it on; bar {bar:.0%}"
    share = hits / total
    return f"  - {name}, {what}: {n(hits)} of {n(total)} ({share:.1%}); bar {bar:.0%}; {'met' if share >= bar else 'not met'}"


def both_ends_drawn(record):
    """Whether the census's SPINEPS mask draws C2 and the sacrum, rather than showing either only in view."""
    census = record.get("census") or {}
    return census.get("head") == "drawn" and census.get("foot") == "drawn"


def bar_lines(records):
    """The PREREG's three hypotheses (part 4) read from the records, each with its bar and whether it is
    met, and the units no bar reads; provisional while any unit is neither segmented nor given up."""
    done = [r for r in records if r["status"] == "segmented"]
    drawn_ends = [r for r in done if both_ends_drawn(r)]
    in_view = [r for r in done if not both_ends_drawn(r)]
    kinds = Counter(r.get("kind") for r in done)
    still = sum(1 for r in records if r["status"] not in ("segmented", "given up"))
    whole_in_view = sum(1 for r in in_view if r.get("kind") not in NOT_WHOLE)
    lines = ["- the PREREG's bars (part 4)" + (f", provisional, units neither segmented nor given up: {n(still)}" if still else "") + ":",
             share_line("H1", "C2 and the sacrum drawn, the sacrum below the lowest level, of the units segmented whose SPINEPS mask "
                        "draws both", sum(1 for r in drawn_ends if r.get("kind") not in NOT_WHOLE), len(drawn_ends), BARS["H1"]),
             f"  - with no bar, the units segmented whose SPINEPS mask shows an end only in view or as a border case: "
             f"{n(whole_in_view)} of {n(len(in_view))} drawn whole by TotalSegmentator"
             + (f" ({whole_in_view / len(in_view):.1%})" if in_view else ""),
             share_line("H2", "every bone named as SPINEPS names it, of the units compared with no T13 or L6 in SPINEPS's map",
                        kinds["concordant"], sum(kinds[k] for k in COMPARED), BARS["H2"])]
    dice, lattice = concordant_dice(records)
    medians = {region: statistics.median(dice[region]) for region in DICE_BARS if dice[region]}
    lacking = [region for region in DICE_BARS if region not in medians]
    if lacking:
        verdict = f"not tested, no level of {' or '.join(lacking)} on a shared lattice"
    else:
        verdict = "met" if all(medians[region] >= bar for region, bar in DICE_BARS.items()) else "not met"
    lines.append("  - H3, the median Dice of each region at least its bar (" + ", ".join(f"{r} {b:.2f}" for r, b in DICE_BARS.items())
                 + "; C from C2, C1 and the sacrum with no bar"
                 + f"), over the {n(sum(lattice.values()))} concordant units on a shared lattice: "
                 + ", ".join(f"{region} {value:.3f}" for region, value in medians.items()) + ("; " if medians else "") + verdict)
    return lines


def report_lines(jobs, records, chain):
    units = jobs["units"]
    status = Counter(r["status"] for r in records)
    here = Counter(r["status"] for r in records if r.get("chain") == chain)
    kinds = Counter(r.get("kind") for r in records if r["status"] == "segmented")
    errors = Counter(error_kind(r) for r in records if r["status"] in ("failed", "given up"))
    verdicts = Counter(u["census"].get("verdict") for u in units)
    versions = sorted({r.get("version") or "not read" for r in records if r["status"] == "segmented"}) or ["none ran"]
    lines = [f"- units: {n(len(units))} CTs ({n(verdicts['admitted'])} admitted, {n(verdicts['look'])} look by the census's field test) "
             f"of {n(jobs['candidates'])} candidate rows; left out: "
             + (", ".join(f"{WHY[why]} {n(count)}" for why, count in jobs["left_out"].items()) or "none")]
    for why, groups in jobs.get("left_out_by_collection", {}).items():
        if why in ("release", "fdg"):
            lines.append(f"  - {WHY[why]}, by collection: " + ", ".join(f"{g} {n(c)}" for g, c in sorted(groups.items(), key=lambda x: (-x[1], x[0]))))
    lines.append(f"- segmented {n(status['segmented'])} ({n(here['segmented'])} by this chain, {n(status['segmented'] - here['segmented'])} before it); "
                 f"failed {n(status['failed'])}; given up {n(status['given up'])} (failed in {GIVE_UP_AFTER} chains at this code); "
                 f"not run {n(status['not run'])}")
    if errors:
        lines.append("- failures by kind: " + ", ".join(f"{k} {n(c)}" for k, c in errors.most_common()))
    lines.append(f"- TotalSegmentator {', '.join(versions)}, task total, roi_subset every vertebra C1 to L5, S1 and the sacrum, fast off; "
                 "each map on its CT's own grid in VerSe's ids, the sacrum one mask (26)")
    lines.append("- against the census's SPINEPS masks: " + ", ".join(f"{k} {n(kinds[k])}" for k in KINDS if kinds[k]) if kinds else
                 "- against the census's SPINEPS masks: no unit segmented yet")
    dice, lattice = concordant_dice(records)
    grids = Counter(r.get("grid") for r in records if r["status"] == "segmented" and r.get("grid"))
    lines.append(f"- Dice of the concordant units whose two maps share a lattice ({n(sum(lattice.values()))}: "
                 f"{n(lattice['same'])} on one grid, {n(lattice['reoriented'])} reoriented), median by region: "
                 + ", ".join(f"{region} {statistics.median(v):.3f} ({n(len(v))} levels)" if v else f"{region} none"
                             for region, v in dice.items())
                 + f"; {n(grids['another lattice'])} segmented units' maps lie on another lattice than SPINEPS's, compared by their centres alone")
    lines.extend(bar_lines(records))
    groups = {}
    for r in records:
        g = groups.setdefault(r["group"], Counter())
        g["units"] += 1
        g["segmented"] += r["status"] == "segmented"
        g["concordant"] += r.get("kind") == "concordant" and r["status"] == "segmented"
    ordered = sorted(groups.items(), key=lambda x: (-x[1]["units"], x[0]))
    lines.append("- by collection (units, segmented, concordant): "
                 + "; ".join(f"{g} {n(c['units'])} {n(c['segmented'])} {n(c['concordant'])}" for g, c in ordered[:COLLECTION_LINES])
                 + (f"; {n(len(ordered) - COLLECTION_LINES)} more collections, {n(sum(c['units'] for _, c in ordered[COLLECTION_LINES:]))} units"
                    if len(ordered) > COLLECTION_LINES else ""))
    seconds = [r["seconds"] for r in records if r["status"] == "segmented" and r.get("chain") == chain and r.get("seconds") is not None]
    spent = sum(r.get("seconds") or 0 for r in records if r.get("chain") == chain)
    lines.append(f"- time: {'median ' + format(statistics.median(seconds), '.0f') + ' s a CT' if seconds else 'no CT segmented by this chain'}, "
                 f"{spent / 3600:.1f} GPU hours of TotalSegmentator by this chain")
    held = [r for r in records if r.get("held_out")]
    if held:
        lines.append(f"- held out: {n(len(held))} CTs, C-ArmLSpine's and those whose person the tier lists mark test only, "
                     f"{n(sum(1 for r in held if r['status'] == 'segmented'))} segmented, "
                     "marked held_out in the records so that nothing trains on them")
    lines.append("- the label maps and records are under the lab volume's gold4-totalseg/ (labels/, units/, records.jsonl)")
    return lines


def write_records(path, records):
    path = Path(path)
    part = part_beside(path)
    with open(part, "w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
    os.replace(part, path)


def merge(args):
    out, chain = Path(args.out), Path(args.out) / "chains" / args.chain
    jobs = read_json(chain / "jobs.json")
    if not isinstance(jobs, dict) or not isinstance(jobs.get("units"), list):
        print(f"merge: chain {args.chain} has no jobs.json: no task of it read the census")
        return 2
    problem = code_problem(args)
    if problem:
        print(f"merge: {problem}, and a unit is given up by its failures at it")
        return 2
    records = []
    for unit in jobs["units"]:
        ran = read_json(record_path(out, unit["id"]))
        records.append(merged_record(unit, ran, status_of(out, unit["id"], ran, args.code)))
    write_records(chain / "records.jsonl", records)
    write_records(out / "records.jsonl", records)
    text = "\n".join(report_lines(jobs, records, args.chain)) + "\n"
    (chain / "REPORT.md").write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if all(r["status"] in ("segmented", "given up") for r in records) else 3


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("run", help="one task of the array: TotalSegmentator on the units it claims")
    s.add_argument("--census", required=True, help="the census's gold4.json")
    s.add_argument("--tiers", required=True, help="the census's tier lists' folder, whose rows name each mask's CT")
    s.add_argument("--out", required=True, help="the run's folder on the lab volume")
    s.add_argument("--chain", required=True, help="the send's array job")
    s.add_argument("--task", type=int, required=True)
    s.add_argument("--tasks", type=int, required=True)
    s.add_argument("--commit", default="", help="the commit of the code that runs, kept in each record")
    s.add_argument("--code", default="", help="the code a unit's failures are counted at; by default tools/run_code.py's "
                   "digest of the kind, read from the files beside this tool")
    s.add_argument("--weights", default=os.environ.get("TOTALSEG_WEIGHTS_PATH", ""), help="the unpacked Dataset folders")
    s.add_argument("--threads", type=int, default=4)
    s.add_argument("--device", default="gpu")
    s.add_argument("--stop-after", type=int, default=STOP_AFTER, help="seconds after which no new unit is taken")
    s.set_defaults(go=run)
    s = sub.add_parser("merge", help="every unit's record and the counts, once the array has ended")
    s.add_argument("--out", required=True)
    s.add_argument("--chain", required=True)
    s.add_argument("--commit", default="")
    s.add_argument("--code", default="", help="as for run")
    s.set_defaults(go=merge)
    args = p.parse_args(argv)
    if args.command == "run" and not (0 <= args.task < args.tasks):
        p.error(f"--task {args.task} is outside the {args.tasks} tasks")
    return args.go(args)


if __name__ == "__main__":
    sys.exit(main())
