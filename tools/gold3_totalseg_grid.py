"""The C2 and the sacrum the gold tier 3 releases do not draw, drawn by TotalSegmentator on the grid.

    python3 tools/gold3_totalseg_grid.py prepare --admission data/gold3-ct/admission.json --tiers DIR \\
        --ts-root DIR --enhance-ct DIR --enhance-labels DIR --verse-masks DIR --out DIR
    python3 tools/gold3_totalseg_grid.py run --out DIR [--weights DIR]
    python3 tools/gold3_totalseg_grid.py check --out DIR
    python3 tools/gold3_totalseg_grid.py report --out DIR

Why this exists. The field test (tools/gold3_field.py) admits a CT whose volume shows C2's foot
and the sacrum's top whatever its masks hold, and the gold tier 3 completion's first arm, the
census's SPINEPS masks read by bordercall's matcher (tools/gold3_complete_grid.py, job 40870822),
could add no sacrum to any VerSe series, since those masks draw none, and no C2 to most. The owner's
word of 2026-10-30 08:54 UTC, "Add sacrum and c2 w total seg", is that TotalSegmentator draws them:
its total task, the vertebrae part (vertebrae_C2 and sacrum among its classes), run on each study's
own CT, so the masks come out on the CT's grid and nothing is resampled. His word of 09:33 UTC keeps each
release's segmentations consistent: ENHANCE.PET's masks were made by MOOSE, so MOOSE's vertebrae
model (moosez clin_ct_vertebrae, the weights `fetch moose_weights` landed) draws its C2 and sacrum,
and TotalSegmentator draws them for the VerSe series and the TotalSegmentator subjects; and every
arm file carries the level in its release's own label id (VerSe 2 and 26, ENHANCE.PET's MOOSE ids
2 and 28, TotalSegmentator one file per structure with value 1), so a reader of the release reads
the arm the same way. What is drawn is a third machine arm beside the release's masks and the
SPINEPS arm, recorded by segmenter, version and sha256, never pooled with either and never raising
a tier, as the completion rule says (data/gold3-ct/members.json, completion). The job is grid/totalseg-complete.sbatch, the gate word
`totalseg complete`, one GPU job on the owner's count, run as the launched flow totalseg
(flows/totalseg.py) under docs/research/gold3-ct/completion/PREREG.md, in four steps:

1. prepare: the studies whose admission asks for C2 or the sacrum (complete lists C2 or sacrum,
   admitted or held for a look), each with its CT on the data root (a VerSe series by its census
   row's CT path, a TotalSegmentator subject by its folder under totalsegmentator_v300 wherever the
   release nests it, ENHANCE.PET's by its id under aws_enhance_pet_ct) and its release masks (VerSe's
   int16 copies, the subject's segmentations/ folder, the Vertebrae file under aws_enhance_pet_labels),
   into OUT/jobs.json; a study with no CT or no release on the grid is listed with its reason.
2. run: TotalSegmentator's Python entry on each VerSe or TotalSegmentator CT with roi_subset
   vertebrae_C2 and sacrum, which crops with the 6 mm model and runs the vertebrae part alone, the
   weights read from the folder TOTALSEG_WEIGHTS_PATH names, never downloaded; on each ENHANCE.PET
   CT the subcommand moose-one in MOOSE's own environment (--moose-python), which unpacks the
   vertebrae model's fetched zip where moosez looks, as tools/flexray_render.py segment does, runs
   moosez's entry and leaves the multilabel file, from which run cuts vertebrae_C2 and sacrum by
   MOOSE's ids; the masks under OUT/ts/<id>/, a run.json beside them, and a study whose run.json
   records a run that ended 0 is not run again while one whose run failed is, so a job cut short,
   or sent again after a fault, carries on.
3. check: each target's mask against the release's own labels on the same grid: drawn at all
   (MIN_VOXELS), lying on the release's levels no more than OVERLAP_SHARE of its voxels, and on the
   right side of them along the world's vertical, C2 above the release's topmost level and the
   sacrum below its lowest; a target that passes is written as the arm file
   OUT/arm/<id>_<segmenter>_<target>_<sha256 prefix>.nii.gz, its voxels at the release's own id for
   the level, and recorded in OUT/records.jsonl with that id, the gap in mm to the release's nearest level, the levels still undrawn between them, and the
   segmenter's name and version; one that fails is recorded with its reason and no file.
4. report: the counts, a line per study and every refusal's reason into OUT/REPORT.md, which the
   gate prints; no path under the data root, only store names and file names.

Standard library here; numpy and nibabel are imported where a mask is read, totalsegmentator and
moosez where they run, so the parts that need none of them are tested without them
(tests/test_gold3_totalseg_grid.py). tools/ leaves sys.path before anything else, since
tools/profile.py would shadow the standard library's profile, which cProfile imports and torch's
imports reach: the first job, 40882547, failed on all 37 studies it ran with "module 'profile' has
no attribute 'run'" for want of it.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:] = [entry for entry in sys.path if Path(entry or ".").resolve() != ROOT / "tools"]
TARGETS = ("C2", "sacrum")
TS_NAMES = {"C2": "vertebrae_C2", "sacrum": "sacrum"}
# Which segmenter draws for which member (the owner, 2026-10-30 09:33 UTC): the one its release was
# made with, where it draws C2 and the sacrum at all.
SEGMENTER_OF = {"verse": "TotalSegmentator", "totalsegmentator": "TotalSegmentator", "enhance_pet": "MOOSE"}
MOOSE_MODEL = "clin_ct_vertebrae"
MOOSE_NAMES = {"C2": "vertebra_C2", "sacrum": "sacrum"}
# MOOSE's ids in its vertebrae model's multilabel file (grid/enhance-pet-labels.json, the bucket's
# labels.json, and schwingnet.segmenters.MOOSEZ_MODELS), which are ENHANCE.PET's release ids too.
MOOSE_IDS = {"C2": 2, "sacrum": 28}
# The id each release writes the level under, which the arm file carries so that its reader reads
# it as the release: VerSe's scheme (C2 at 2, the sacrum at 26), ENHANCE.PET's MOOSE ids, and
# TotalSegmentator's one file per structure, whose voxels are 1.
RELEASE_IDS = {"verse": {"C2": 2, "sacrum": 26}, "enhance_pet": dict(MOOSE_IDS), "totalsegmentator": {"C2": 1, "sacrum": 1}}
RELEASE_SCHEME = {"verse": "VerSe label ids", "enhance_pet": "MOOSE clin_ct_vertebrae ids, ENHANCE.PET's", "totalsegmentator": "one file per structure, value 1"}
MIN_VOXELS = 200                # drawn at all, as the field test and the matcher count a level
OVERLAP_SHARE = 0.05            # at most this share of a target's voxels on the release's own levels
ORDER = (*[f"C{i}" for i in range(1, 8)], *[f"T{i}" for i in range(1, 14)], *[f"L{i}" for i in range(1, 7)], "sacrum")
TIER_FILES = ("tier1.tsv", "tier2.tsv")
VERSE_IN_PATH = re.compile(r"scan-([A-Za-z0-9]+)_ct\b")
TS_SUBJECT = re.compile(r"^s\d{4}$")
REASON_CHARS = 160
SEGMENTER = "TotalSegmentator"
TASK = {"task": "total", "roi_subset": ["vertebrae_C2", "sacrum"], "fast": False}
MOOSE_TASK = {"model": MOOSE_MODEL, "targets": MOOSE_NAMES}


# ---- which studies, with which targets ------------------------------------------------------

def studies_asked(admission_path):
    """Every admitted or held study whose completion list names C2 or the sacrum, with its targets."""
    with open(admission_path, encoding="utf-8") as fh:
        rows = json.load(fh)["studies"]
    asked = []
    for row in rows:
        if row.get("verdict") not in ("admitted", "look"):
            continue
        targets = [t for t in TARGETS if t in (row.get("complete") or [])]
        if targets:
            asked.append({"member": row["member"], "id": row["id"], "verdict": row["verdict"], "targets": targets,
                          "complete": list(row.get("complete") or []), "segmenter": SEGMENTER_OF.get(row["member"], SEGMENTER)})
    return asked


# ---- where the CT and the release are on the grid --------------------------------------------

def read_tiers(tiers_dir):
    rows = []
    for name in TIER_FILES:
        path = os.path.join(tiers_dir, name)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8", newline="") as fh:
            rows.extend(csv.DictReader(fh, delimiter="\t"))
    return rows


def verse_cts(rows):
    """{series id: its CT path} from the census's rows, the first row of a series keeping its place."""
    found = {}
    for row in rows:
        match = VERSE_IN_PATH.search(row.get("ct_path") or "")
        if match:
            found.setdefault(match.group(1), row["ct_path"])
    return found


_TS_FOLDERS = {}


def ts_subject_folder(ts_root, sid):
    """The subject's folder under totalsegmentator_v300, <root>/<id>/ first, else wherever the
    release nests it, found by a walk made once per root (as tools/gold3_complete_grid.py finds it)."""
    direct = os.path.join(ts_root, sid)
    if os.path.isfile(os.path.join(direct, "ct.nii.gz")):
        return direct
    if ts_root not in _TS_FOLDERS:
        found = {}
        for folder, dirs, files in os.walk(ts_root):
            if TS_SUBJECT.match(os.path.basename(folder)) and "ct.nii.gz" in files:
                found.setdefault(os.path.basename(folder), folder)
                dirs[:] = []
        _TS_FOLDERS[ts_root] = found
    return _TS_FOLDERS[ts_root].get(sid)


_FILES = {}


def files_named(root, name):
    """Every file called NAME under ROOT, in the order a walk made once per root finds them; [] where there is none."""
    if root not in _FILES:
        found = {}
        for folder, _, files in os.walk(root):
            for file in files:
                found.setdefault(file, []).append(os.path.join(folder, file))
        _FILES[root] = found
    return _FILES[root].get(name, [])


def locate(study, verse_ct, ts_root, enhance_ct, enhance_labels, verse_masks):
    """(ct path, release, reason): the study's CT and release masks on the grid, or why not. The
    release is a file (VerSe's int16 copy, ENHANCE.PET's Vertebrae file) or a folder of one file per
    level (a TotalSegmentator subject's segmentations/)."""
    member, sid = study["member"], study["id"]
    if member == "verse":
        ct = verse_ct.get(sid)
        if not ct or not os.path.exists(ct):
            return None, None, "no census row names the series' CT on the data root"
        release = os.path.join(verse_masks, sid + ".nii.gz")
        if not os.path.exists(release):
            return None, None, "no int16 copy of the VerSe mask on the data root (verse_masks_2026_10_29)"
        return ct, release, None
    if member == "totalsegmentator":
        folder = ts_subject_folder(ts_root, sid)
        if folder is None:
            return None, None, "no folder of the subject's name with a ct.nii.gz under totalsegmentator_v300"
        release = os.path.join(folder, "segmentations")
        if not os.path.isdir(release) or not any(n.startswith("vertebrae_") for n in os.listdir(release)):
            return None, None, "no segmentations/ folder with vertebrae_*.nii.gz for the subject under totalsegmentator_v300"
        return os.path.join(folder, "ct.nii.gz"), release, None
    if member == "enhance_pet":
        cts = files_named(enhance_ct, sid + ".nii.gz") if os.path.isdir(enhance_ct) else []
        if not cts:
            return None, None, "no CT of the study's id under aws_enhance_pet_ct"
        # The ground truth is seven folders of label maps, each holding a file of the study's name, so
        # the Vertebrae folder's is taken from all of them, whichever folder the walk lists first: the
        # first job took only the first file of the name and left 1379 out.
        labels = files_named(enhance_labels, sid + ".nii.gz") if os.path.isdir(enhance_labels) else []
        release = next((p for p in labels if os.path.basename(os.path.dirname(p)) == "Vertebrae"), None)
        if release is None:
            return None, None, "no Vertebrae mask of the study's id under aws_enhance_pet_labels"
        return cts[0], release, None
    return None, None, "a member this tool does not know"


def short_store(path, roots):
    """The data root's folder a path lies in, named without the path above it."""
    for root in roots:
        if root and path.startswith(root.rstrip("/") + "/"):
            return os.path.basename(root.rstrip("/"))
    return os.path.basename(os.path.dirname(path)) or "-"


def prepare(args):
    studies = studies_asked(args.admission)
    verse_ct = verse_cts(read_tiers(args.tiers)) if args.tiers else {}
    os.makedirs(args.out, exist_ok=True)
    roots = [args.ts_root, args.enhance_ct, args.enhance_labels, args.verse_masks, os.path.dirname(args.verse_masks.rstrip("/"))]
    jobs, left_out = [], []
    for study in studies:
        ct, release, why = locate(study, verse_ct, args.ts_root, args.enhance_ct, args.enhance_labels, args.verse_masks)
        if why:
            left_out.append(dict(study, reason=why))
            continue
        jobs.append(dict(study, ct=ct, release=release, ct_store=short_store(ct, roots), release_store=short_store(release, roots)))
    record = {"segmenter": SEGMENTER, "task": TASK, "moose_task": MOOSE_TASK, "segmenter_of": SEGMENTER_OF, "asked": len(studies), "prepared": len(jobs), "not_prepared": len(left_out),
              "studies": jobs, "left_out": left_out, "prepared_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    with open(os.path.join(args.out, "jobs.json"), "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1, sort_keys=True)
        fh.write("\n")
    by = {}
    for study in jobs:
        by[study["segmenter"]] = by.get(study["segmenter"], 0) + 1
    print(f"prepare: {len(studies)} studies asked; {len(jobs)} prepared ({', '.join(f'{n} for {k}' for k, n in sorted(by.items())) or 'none'}); "
          f"{len(left_out)} not (jobs.json says why)")
    return 0


# ---- TotalSegmentator on each CT ---------------------------------------------------------------

def read_jobs(out):
    with open(os.path.join(out, "jobs.json"), encoding="utf-8") as fh:
        return json.load(fh)


def segmenter_version(package="TotalSegmentator"):
    try:
        from importlib.metadata import version
        return version(package)
    except Exception:                                           # noqa: BLE001
        return "not read"


def run_totalseg(study, folder, args):
    from totalsegmentator.python_api import totalsegmentator
    totalsegmentator(study["ct"], folder, task=TASK["task"], roi_subset=list(TASK["roi_subset"]), fast=TASK["fast"],
                     device=args.device, quiet=True, nr_thr_resamp=args.threads, nr_thr_saving=args.threads)
    return {}


def cut_targets(multilabel, folder, ids=MOOSE_IDS):
    """Each target's own file beside the multilabel MOOSE wrote, by MOOSE's ids, under the names
    TotalSegmentator writes, so the check reads either segmenter's output alike."""
    import nibabel as nib
    import numpy as np
    img = nib.load(multilabel)
    data = np.asanyarray(img.dataobj)
    for target, value in ids.items():
        out = nib.Nifti1Image((data == value).astype(np.uint8), img.affine, img.header)
        out.set_data_dtype(np.uint8)
        nib.save(out, os.path.join(folder, TS_NAMES[target] + ".nii.gz"))


def run_moose(study, folder, args):
    """MOOSE in its own environment (the subcommand moose-one under --moose-python), then the two
    targets cut out of its multilabel file by MOOSE's ids."""
    if not args.moose_python:
        raise RuntimeError("no --moose-python: MOOSE's environment was not given, so an ENHANCE.PET study cannot run")
    words = [args.moose_python, os.path.abspath(__file__), "moose-one", "--ct", study["ct"], "--folder", folder,
             "--weights", args.moose_weights, "--device", args.device]
    said = subprocess.run(words, capture_output=True, text=True, timeout=4 * 3600)
    lines = [line for line in said.stdout.splitlines() if line.startswith("{")]
    if said.returncode != 0 or not lines:
        tail = (said.stderr or said.stdout).strip().splitlines()[-3:]
        raise RuntimeError(f"moose-one ended {said.returncode}: {' | '.join(tail)[:REASON_CHARS]}")
    found = json.loads(lines[-1])
    cut_targets(found["multilabel"], folder)
    return {"version": found.get("version"), "multilabel": os.path.basename(found["multilabel"]), "models": found.get("models")}


def moose_one(args):
    """Inside MOOSE's environment: the vertebrae model's zip unpacked where moosez looks, as
    tools/flexray_render.py segment unpacks it (its metadata and labels held equal to the tool's
    tables first, so moosez downloads nothing), moosez's entry on the CT through a link in the
    study's folder, and the multilabel file it wrote found by its region word; one JSON line last."""
    sys.path.insert(0, str(ROOT / "tools"))
    import flexray_render as fr
    from moosez import moose
    metadata = {MOOSE_MODEL: fr.moosez_metadata()[MOOSE_MODEL]}
    folder, url = metadata[MOOSE_MODEL]
    zip_path = Path(args.weights) / fr.zip_of(url)
    if not zip_path.is_file():
        raise SystemExit(f"no {zip_path.name} under {args.weights} (fetch moose_weights first)")
    differs = fr.moosez_disagreements(metadata)
    if differs:
        raise SystemExit("moosez's own metadata differs from the tool's copy, so it would download: " + "; ".join(differs))
    models_dir = fr.models_directory()
    unpacked = fr.unpack_weights(args.weights, metadata, models_dir)
    labels = fr.check_labels(models_dir, metadata)
    theirs, _ = fr.dataset_labels(models_dir, folder)
    for target, value in MOOSE_IDS.items():
        if theirs.get(value, "").lower() != MOOSE_NAMES[target].lower():
            raise SystemExit(f"MOOSE's dataset.json names value {value} {theirs.get(value)!r}, not {MOOSE_NAMES[target]}; the ids this tool cuts by would be wrong")
    home = Path(args.folder)
    home.mkdir(parents=True, exist_ok=True)
    link = home / f"CT_{home.name}.nii.gz"
    if not link.exists():
        link.symlink_to(Path(args.ct).resolve())
    before = {p for p in home.rglob("*.nii.gz")}
    moose(str(link), [MOOSE_MODEL], str(home), args.device)
    written = sorted(p for p in home.rglob("*.nii.gz") if p not in before and "vertebrae" in p.name.lower())
    if not written:
        raise SystemExit("moosez wrote no vertebrae file under the study's folder")
    print(json.dumps({"multilabel": str(written[-1]), "version": segmenter_version("moosez"), "models": {"unpacked": unpacked, "labels": labels}}))
    return 0


def ran_cleanly(done):
    """Whether a study's run.json records a run that ended 0, whose masks stand; a failed run's
    record says only why it failed, so that study is run again."""
    try:
        with open(done, encoding="utf-8") as fh:
            return json.load(fh).get("exit") == 0
    except (OSError, ValueError, AttributeError):
        return False


def run(args):
    """TotalSegmentator or MOOSE on every prepared CT whose last run did not end 0; its exit is 0
    only where every study has its masks, drawn now or before."""
    if args.weights:
        os.environ["TOTALSEG_WEIGHTS_PATH"] = args.weights
    jobs = read_jobs(args.out)
    failed = 0
    for study in jobs["studies"]:
        folder = os.path.join(args.out, "ts", study["id"])
        done = os.path.join(folder, "run.json")
        if ran_cleanly(done):
            continue
        os.makedirs(folder, exist_ok=True)
        began = time.time()
        segmenter = study.get("segmenter", SEGMENTER)
        record = {"id": study["id"], "member": study["member"], "segmenter": segmenter,
                  "version": segmenter_version() if segmenter == SEGMENTER else None,
                  "task": TASK if segmenter == SEGMENTER else MOOSE_TASK, "began": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(began))}
        try:
            found = (run_totalseg if segmenter == SEGMENTER else run_moose)(study, folder, args)
            record.update({k: v for k, v in found.items() if v is not None})
            record["exit"] = 0
        except Exception as exc:                                # noqa: BLE001
            record["exit"] = 1
            record["error"] = f"{type(exc).__name__}: {str(exc)[:REASON_CHARS]}"
            failed += 1
        record["seconds"] = round(time.time() - began, 1)
        record["files"] = sorted(n for n in os.listdir(folder) if n.endswith(".nii.gz"))
        with open(done, "w", encoding="utf-8") as fh:
            json.dump(record, fh, indent=1, sort_keys=True)
            fh.write("\n")
        print(f"run: {study['id']} exit {record['exit']} in {record['seconds']} s", flush=True)
    print(f"run: {len(jobs['studies'])} studies, {failed} failed this run")
    return 1 if failed else 0


# ---- the check against the release's own levels ----------------------------------------------

def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def release_levels(release):
    """[(name, boolean array)] of the release's drawn levels on its grid, with the grid's affine:
    one file per level in a TotalSegmentator folder, one label per level in a VerSe or ENHANCE.PET
    file (the label ids read as names, since their maps differ by member and only the voxels count here)."""
    import nibabel as nib
    import numpy as np
    levels = []
    if os.path.isdir(release):
        affine = None
        for name in sorted(os.listdir(release)):
            if name.startswith("vertebrae_") or name == "sacrum.nii.gz":
                img = nib.load(os.path.join(release, name))
                affine = img.affine if affine is None else affine
                data = np.asanyarray(img.dataobj) > 0
                if data.any():
                    levels.append((name[:-7], data))
        return levels, affine
    img = nib.load(release)
    data = np.asanyarray(img.dataobj)
    for label in sorted(int(v) for v in np.unique(data) if v != 0):
        levels.append((f"label {label}", data == label))
    return levels, img.affine


def world_z(affine, voxels):
    """The world's vertical (RAS's S) of each voxel index triple, as the affine places it."""
    import numpy as np
    ijk = np.column_stack([*voxels, np.ones(len(voxels[0]))])
    return ijk @ affine[2]


def z_extent(mask, affine):
    import numpy as np
    where = np.nonzero(mask)
    z = world_z(affine, where)
    return float(z.min()), float(z.max()), float(z.mean())


def between(target, drawn_names, complete):
    """The levels the admission still lists as undrawn between the target and the release's nearest level."""
    listed = [n for n in complete if n != target]
    if target == "C2":
        return [n for n in listed if n in ORDER and ORDER.index(n) < 24]
    return [n for n in listed if n in ORDER and ORDER.index(n) >= 7]


def check_target(target, mask_path, levels, release_affine, complete):
    """The record of one target: its voxels, overlap share, its place against the release's levels, and
    the verdict kept or refused with the reason."""
    import nibabel as nib
    import numpy as np
    img = nib.load(mask_path)
    data = np.asanyarray(img.dataobj) > 0
    record = {"voxels": int(data.sum()), "grid": "ct"}
    if record["voxels"] < MIN_VOXELS:
        record.update(kept=False, reason=f"TotalSegmentator drew {record['voxels']} voxels of it, under {MIN_VOXELS}")
        return record
    if any(level.shape != data.shape for _, level in levels) or not np.allclose(img.affine, release_affine, atol=0.01):
        record.update(kept=False, reason="the CT's grid is not the release masks' grid, so the check cannot be made")
        return record
    on_release = np.zeros_like(data)
    for _, level in levels:
        on_release |= level
    share = float((data & on_release).sum()) / float(data.sum())
    record["overlap_share"] = round(share, 4)
    if share > OVERLAP_SHARE:
        record.update(kept=False, reason=f"{share:.0%} of its voxels lie on the release's own levels, over {OVERLAP_SHARE:.0%}")
        return record
    lo, hi, mid = z_extent(data, img.affine)
    extents = [(name, *z_extent(level, release_affine)) for name, level in levels]
    if not extents:
        record.update(kept=False, reason="the release draws no level to set it against")
        return record
    if target == "C2":
        name, nlo, nhi, nmid = max(extents, key=lambda e: e[3])
        right_side = mid > nmid
        gap = round(lo - nhi, 1)
    else:
        name, nlo, nhi, nmid = min(extents, key=lambda e: e[3])
        right_side = mid < nmid
        gap = round(nlo - hi, 1)
    record.update(nearest_release_level=name, gap_mm=gap, undrawn_between=between(target, [n for n, *_ in extents], complete))
    if not right_side:
        record.update(kept=False, reason=f"its centre lies on the wrong side of the release's {'topmost' if target == 'C2' else 'lowest'} level ({name})")
        return record
    record["kept"] = True
    return record


def write_arm(mask_path, out_path, value):
    """The arm file: the segmenter's voxels of the level at the release's own id, int16 as the
    release files are, on the mask's grid."""
    import nibabel as nib
    import numpy as np
    img = nib.load(mask_path)
    data = (np.asanyarray(img.dataobj) > 0).astype(np.int16) * np.int16(value)
    out = nib.Nifti1Image(data, img.affine, img.header)
    out.set_data_dtype(np.int16)
    nib.save(out, out_path)


def check(args):
    jobs = read_jobs(args.out)
    arm = os.path.join(args.out, "arm")
    os.makedirs(arm, exist_ok=True)
    records = []
    for study in jobs["studies"]:
        folder = os.path.join(args.out, "ts", study["id"])
        run_path = os.path.join(folder, "run.json")
        segmenter = study.get("segmenter", SEGMENTER)
        record = {"id": study["id"], "member": study["member"], "verdict": study["verdict"], "targets": {},
                  "segmenter": segmenter, "task": TASK if segmenter == SEGMENTER else MOOSE_TASK,
                  "label_scheme": RELEASE_SCHEME.get(study["member"], "-"), "ct_store": study["ct_store"], "release_store": study["release_store"]}
        if not os.path.exists(run_path):
            record["error"] = "not run"
            records.append(record)
            continue
        with open(run_path, encoding="utf-8") as fh:
            ran = json.load(fh)
        record["version"] = ran.get("version")
        if ran.get("exit") != 0:
            record["error"] = ran.get("error") or "TotalSegmentator failed"
            records.append(record)
            continue
        try:
            levels, release_affine = release_levels(study["release"])
        except Exception as exc:                                # noqa: BLE001
            record["error"] = f"the release masks could not be read: {type(exc).__name__}: {str(exc)[:REASON_CHARS]}"
            records.append(record)
            continue
        for target in study["targets"]:
            mask_path = os.path.join(folder, TS_NAMES[target] + ".nii.gz")
            if not os.path.exists(mask_path):
                record["targets"][target] = {"kept": False, "reason": "TotalSegmentator wrote no file for it"}
                continue
            try:
                found = check_target(target, mask_path, levels, release_affine, study["complete"])
            except Exception as exc:                            # noqa: BLE001
                found = {"kept": False, "reason": f"the check failed: {type(exc).__name__}: {str(exc)[:REASON_CHARS]}"}
            if found.get("kept"):
                value = RELEASE_IDS.get(study["member"], {}).get(target, 1)
                staged = os.path.join(arm, f".{study['id']}_{target}.part.nii.gz")
                write_arm(mask_path, staged, value)
                digest = sha256_of(staged)
                name = f"{study['id']}_{segmenter.lower()}_{target}_{digest[:12]}.nii.gz"
                os.replace(staged, os.path.join(arm, name))
                found.update(file=name, sha256=digest, label_value=value)
            record["targets"][target] = found
        records.append(record)
    with open(os.path.join(args.out, "records.jsonl"), "w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
    kept = sum(1 for r in records for t in r["targets"].values() if t.get("kept"))
    print(f"check: {len(records)} studies, {kept} targets kept as arm files under {arm}")
    return 0


# ---- the report that leaves the grid -------------------------------------------------------------

def short(text, chars=REASON_CHARS):
    text = " ".join(str(text).split())
    return text if len(text) <= chars else text[:chars - 3] + "..."


def report(args):
    jobs = read_jobs(args.out)
    records = []
    path = os.path.join(args.out, "records.jsonl")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            records = [json.loads(line) for line in fh if line.strip()]
    by_member = {}
    for study in jobs["studies"] + jobs["left_out"]:
        by_member[study["member"]] = by_member.get(study["member"], 0) + 1
    for r in records:
        r.setdefault("targets", {})
    kept = [(r["id"], t) for r in records for t, found in r["targets"].items() if found.get("kept")]
    refused = [(r["id"], t, found["reason"]) for r in records for t, found in r["targets"].items() if not found.get("kept") and "reason" in found]
    errors = [(r["id"], r["error"]) for r in records if "error" in r]
    versions = {}
    for r in records:
        versions.setdefault(r.get("segmenter", SEGMENTER), set()).add(r.get("version") or "not read")
    ran = {s.get("segmenter", SEGMENTER) for s in jobs["studies"]}
    said = []
    if SEGMENTER in ran or SEGMENTER in versions:
        said.append(f"{SEGMENTER} {', '.join(sorted(versions.get(SEGMENTER, {'not read'})))} (task {TASK['task']}, roi_subset {' '.join(TASK['roi_subset'])}) "
                    f"for {', '.join(m for m, s in SEGMENTER_OF.items() if s == SEGMENTER)}")
    if "MOOSE" in ran or "MOOSE" in versions:
        said.append(f"MOOSE {', '.join(sorted(versions.get('MOOSE', {'not read'})))} ({MOOSE_MODEL}) for enhance_pet")
    lines = [f"- studies asked: {jobs['asked']} ({', '.join(f'{m} {n}' for m, n in sorted(by_member.items()))}); "
             f"prepared: {jobs['prepared']}; not prepared: {jobs['not_prepared']}",
             f"- segmenters: {'; '.join(said) or 'none ran'}; each on the CT's own grid, each arm file in its release's own label id",
             f"- targets kept: {len(kept)} ({sum(1 for _, t in kept if t == 'C2')} C2, {sum(1 for _, t in kept if t == 'sacrum')} sacrum) "
             f"in {len({i for i, _ in kept})} studies; targets refused: {len(refused)}; studies in error: {len(errors)}",
             "", "| id | member | segmenter | ct store | asked | C2 | sacrum | arm files |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in records:
        cells = []
        for t in TARGETS:
            found = r["targets"].get(t)
            cells.append("-" if found is None else ("kept" if found.get("kept") else "refused"))
        files = " ".join(found["file"] for found in r["targets"].values() if found.get("file")) or ("error" if "error" in r else "-")
        asked = " ".join(t for t in TARGETS if t in r["targets"]) or "-"
        lines.append(f"| {r['id']} | {r['member']} | {r.get('segmenter', SEGMENTER)} | {r['ct_store']} | {asked} | {cells[0]} | {cells[1]} | {files} |")
    recorded = {r["id"] for r in records}
    for study in jobs["studies"]:
        if study["id"] not in recorded:
            lines.append(f"| {study['id']} | {study['member']} | {study.get('segmenter', SEGMENTER)} | {study['ct_store']} | {' '.join(study['targets'])} | - | - | not run |")
    for study in jobs["left_out"]:
        lines.append(f"| {study['id']} | {study['member']} | {study.get('segmenter', SEGMENTER)} | - | {' '.join(study['targets'])} | - | - | not prepared |")
    if kept:
        lines += ["", "kept (each target's gap in mm to the release's nearest level, and the levels still undrawn between them):"]
        for r in records:
            for t, found in r["targets"].items():
                if found.get("kept"):
                    undrawn = " ".join(found.get("undrawn_between") or []) or "none"
                    lines.append(f"- {r['id']} {t}: {found['voxels']} voxels, gap {found.get('gap_mm')} mm to {found.get('nearest_release_level')}, "
                                 f"undrawn between: {undrawn}; written at id {found.get('label_value')} ({r.get('label_scheme', '-')})")
    if refused:
        lines += ["", "refused (each target's reason, cut to 160 characters; the records hold them whole):"]
        lines += [f"- {i} {t}: {short(why)}" for i, t, why in refused]
    if errors:
        lines += ["", "in error:"] + [f"- {i}: {short(why)}" for i, why in errors]
    if jobs["left_out"]:
        lines += ["", "not prepared:"] + [f"- {s['id']} ({s['member']}): {short(s['reason'])}" for s in jobs["left_out"]]
    text = "\n".join(lines) + "\n"
    with open(os.path.join(args.out, "REPORT.md"), "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text, end="")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("prepare")
    s.add_argument("--admission", required=True)
    s.add_argument("--tiers", default="", help="the census's tier1.tsv and tier2.tsv, whose rows name each VerSe series' CT")
    s.add_argument("--ts-root", required=True, help="totalsegmentator_v300")
    s.add_argument("--enhance-ct", required=True, help="aws_enhance_pet_ct/raw")
    s.add_argument("--enhance-labels", required=True, help="aws_enhance_pet_labels/raw")
    s.add_argument("--verse-masks", required=True, help="verse_masks_2026_10_29, the int16 copies")
    s.add_argument("--out", required=True)
    s.set_defaults(go=prepare)
    s = sub.add_parser("run")
    s.add_argument("--out", required=True)
    s.add_argument("--weights", default="", help="the folder holding the unpacked Dataset folders (TOTALSEG_WEIGHTS_PATH)")
    s.add_argument("--moose-python", default="", help="the python of MOOSE's environment, which runs the subcommand moose-one")
    s.add_argument("--moose-weights", default="", help="the data root's moose_weights/raw, the fetched zips")
    s.add_argument("--device", default="gpu")
    s.add_argument("--threads", type=int, default=4)
    s.set_defaults(go=run)
    s = sub.add_parser("moose-one", help="inside MOOSE's environment: the vertebrae model on one CT")
    s.add_argument("--ct", required=True)
    s.add_argument("--folder", required=True)
    s.add_argument("--weights", required=True)
    s.add_argument("--device", default="gpu")
    s.set_defaults(go=moose_one)
    s = sub.add_parser("check")
    s.add_argument("--out", required=True)
    s.set_defaults(go=check)
    s = sub.add_parser("report")
    s.add_argument("--out", required=True)
    s.set_defaults(go=report)
    args = p.parse_args(argv)
    return args.go(args)


if __name__ == "__main__":
    sys.exit(main())
