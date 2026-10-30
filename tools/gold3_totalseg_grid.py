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
own CT, so the masks come out on the CT's grid and nothing is resampled. What it draws is a third
machine arm beside the release's masks and the SPINEPS arm, recorded by segmenter, version and
sha256, never pooled with either and never raising a tier, as the completion rule says
(data/gold3-ct/members.json, completion). The job is grid/totalseg-complete.sbatch, the gate word
`totalseg complete`, one GPU job on the owner's count, run as the launched flow totalseg
(flows/totalseg.py) under docs/research/gold3-ct/completion/PREREG.md, in four steps:

1. prepare: the studies whose admission asks for C2 or the sacrum (complete lists C2 or sacrum,
   admitted or held for a look), each with its CT on the data root (a VerSe series by its census
   row's CT path, a TotalSegmentator subject by its folder under totalsegmentator_v300 wherever the
   release nests it, ENHANCE.PET's by its id under aws_enhance_pet_ct) and its release masks (VerSe's
   int16 copies, the subject's segmentations/ folder, the Vertebrae file under aws_enhance_pet_labels),
   into OUT/jobs.json; a study with no CT or no release on the grid is listed with its reason.
2. run: TotalSegmentator's Python entry on each CT with roi_subset vertebrae_C2 and sacrum, which
   crops with the 6 mm model and runs the vertebrae part alone, the weights read from the folder
   TOTALSEG_WEIGHTS_PATH names, never downloaded; the masks under OUT/ts/<id>/, a run.json beside
   them, and a study whose masks are already there is not run again, so a job cut short carries on.
3. check: each target's mask against the release's own labels on the same grid: drawn at all
   (MIN_VOXELS), lying on the release's levels no more than OVERLAP_SHARE of its voxels, and on the
   right side of them along the world's vertical, C2 above the release's topmost level and the
   sacrum below its lowest; a target that passes is written as the arm file
   OUT/arm/<id>_totalseg_<target>_<sha256 prefix>.nii.gz and recorded in OUT/records.jsonl with the
   gap in mm to the release's nearest level, the levels still undrawn between them, and the
   segmenter's name and version; one that fails is recorded with its reason and no file.
4. report: the counts, a line per study and every refusal's reason into OUT/REPORT.md, which the
   gate prints; no path under the data root, only store names and file names.

Standard library here; numpy and nibabel are imported where a mask is read, and totalsegmentator
where it runs, so the parts that need none of them are tested without them
(tests/test_gold3_totalseg_grid.py).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

TARGETS = ("C2", "sacrum")
TS_NAMES = {"C2": "vertebrae_C2", "sacrum": "sacrum"}
MIN_VOXELS = 200                # drawn at all, as the field test and the matcher count a level
OVERLAP_SHARE = 0.05            # at most this share of a target's voxels on the release's own levels
ORDER = (*[f"C{i}" for i in range(1, 8)], *[f"T{i}" for i in range(1, 14)], *[f"L{i}" for i in range(1, 7)], "sacrum")
TIER_FILES = ("tier1.tsv", "tier2.tsv")
VERSE_IN_PATH = re.compile(r"scan-([A-Za-z0-9]+)_ct\b")
TS_SUBJECT = re.compile(r"^s\d{4}$")
REASON_CHARS = 160
SEGMENTER = "TotalSegmentator"
TASK = {"task": "total", "roi_subset": ["vertebrae_C2", "sacrum"], "fast": False}


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
                          "complete": list(row.get("complete") or [])})
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


def file_named(root, name):
    """The first file called NAME under ROOT, found by a walk made once per root; None where there is none."""
    if root not in _FILES:
        found = {}
        for folder, _, files in os.walk(root):
            for file in files:
                found.setdefault(file, os.path.join(folder, file))
        _FILES[root] = found
    return _FILES[root].get(name)


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
        ct = file_named(enhance_ct, sid + ".nii.gz") if os.path.isdir(enhance_ct) else None
        if ct is None:
            return None, None, "no CT of the study's id under aws_enhance_pet_ct"
        release = file_named(enhance_labels, sid + ".nii.gz") if os.path.isdir(enhance_labels) else None
        release = release if release and os.path.basename(os.path.dirname(release)) == "Vertebrae" else None
        if release is None:
            vertebrae = [p for p in (_FILES.get(enhance_labels) or {}).values()
                         if os.path.basename(p) == sid + ".nii.gz" and os.path.basename(os.path.dirname(p)) == "Vertebrae"]
            release = vertebrae[0] if vertebrae else None
        if release is None:
            return None, None, "no Vertebrae mask of the study's id under aws_enhance_pet_labels"
        return ct, release, None
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
    record = {"segmenter": SEGMENTER, "task": TASK, "asked": len(studies), "prepared": len(jobs), "not_prepared": len(left_out),
              "studies": jobs, "left_out": left_out, "prepared_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    with open(os.path.join(args.out, "jobs.json"), "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(f"prepare: {len(studies)} studies asked; {len(jobs)} prepared for TotalSegmentator; {len(left_out)} not (jobs.json says why)")
    return 0


# ---- TotalSegmentator on each CT ---------------------------------------------------------------

def read_jobs(out):
    with open(os.path.join(out, "jobs.json"), encoding="utf-8") as fh:
        return json.load(fh)


def segmenter_version():
    try:
        from importlib.metadata import version
        return version("TotalSegmentator")
    except Exception:                                           # noqa: BLE001
        return "not read"


def run(args):
    """TotalSegmentator on every prepared CT whose masks are not there yet; its exit is 0 only where
    every study has its masks, drawn now or before."""
    if args.weights:
        os.environ["TOTALSEG_WEIGHTS_PATH"] = args.weights
    jobs = read_jobs(args.out)
    failed = 0
    for study in jobs["studies"]:
        folder = os.path.join(args.out, "ts", study["id"])
        done = os.path.join(folder, "run.json")
        if os.path.exists(done):
            continue
        os.makedirs(folder, exist_ok=True)
        began = time.time()
        record = {"id": study["id"], "member": study["member"], "segmenter": SEGMENTER, "version": segmenter_version(),
                  "task": TASK, "began": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(began))}
        try:
            from totalsegmentator.python_api import totalsegmentator
            totalsegmentator(study["ct"], folder, task=TASK["task"], roi_subset=list(TASK["roi_subset"]), fast=TASK["fast"],
                             device=args.device, quiet=True, nr_thr_resamp=args.threads, nr_thr_saving=args.threads)
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


def check(args):
    jobs = read_jobs(args.out)
    arm = os.path.join(args.out, "arm")
    os.makedirs(arm, exist_ok=True)
    records = []
    for study in jobs["studies"]:
        folder = os.path.join(args.out, "ts", study["id"])
        run_path = os.path.join(folder, "run.json")
        record = {"id": study["id"], "member": study["member"], "verdict": study["verdict"], "targets": {},
                  "segmenter": SEGMENTER, "task": TASK, "ct_store": study["ct_store"], "release_store": study["release_store"]}
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
                digest = sha256_of(mask_path)
                name = f"{study['id']}_totalseg_{target}_{digest[:12]}.nii.gz"
                with open(mask_path, "rb") as src, open(os.path.join(arm, name), "wb") as dst:
                    dst.write(src.read())
                found.update(file=name, sha256=digest)
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
    kept = [(r["id"], t) for r in records for t, found in r["targets"].items() if found.get("kept")]
    refused = [(r["id"], t, found["reason"]) for r in records for t, found in r["targets"].items() if not found.get("kept") and "reason" in found]
    errors = [(r["id"], r["error"]) for r in records if "error" in r]
    versions = sorted({r.get("version") for r in records if r.get("version")}) or ["not read"]
    lines = [f"- studies asked: {jobs['asked']} ({', '.join(f'{m} {n}' for m, n in sorted(by_member.items()))}); "
             f"prepared: {jobs['prepared']}; not prepared: {jobs['not_prepared']}",
             f"- segmenter: {SEGMENTER} {', '.join(versions)}, task {TASK['task']}, roi_subset {' '.join(TASK['roi_subset'])}, run on each CT's own grid",
             f"- targets kept: {len(kept)} ({sum(1 for _, t in kept if t == 'C2')} C2, {sum(1 for _, t in kept if t == 'sacrum')} sacrum) "
             f"in {len({i for i, _ in kept})} studies; targets refused: {len(refused)}; studies in error: {len(errors)}",
             "", "| id | member | ct store | asked | C2 | sacrum | arm files |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in records:
        cells = []
        for t in TARGETS:
            found = r["targets"].get(t)
            cells.append("-" if found is None else ("kept" if found.get("kept") else "refused"))
        files = " ".join(found["file"] for found in r["targets"].values() if found.get("file")) or ("error" if "error" in r else "-")
        asked = " ".join(t for t in TARGETS if t in r["targets"]) or "-"
        lines.append(f"| {r['id']} | {r['member']} | {r['ct_store']} | {asked} | {cells[0]} | {cells[1]} | {files} |")
    recorded = {r["id"] for r in records}
    for study in jobs["studies"]:
        if study["id"] not in recorded:
            lines.append(f"| {study['id']} | {study['member']} | {study['ct_store']} | {' '.join(study['targets'])} | - | - | not run |")
    for study in jobs["left_out"]:
        lines.append(f"| {study['id']} | {study['member']} | - | {' '.join(study['targets'])} | - | - | not prepared |")
    if kept:
        lines += ["", "kept (each target's gap in mm to the release's nearest level, and the levels still undrawn between them):"]
        for r in records:
            for t, found in r["targets"].items():
                if found.get("kept"):
                    undrawn = " ".join(found.get("undrawn_between") or []) or "none"
                    lines.append(f"- {r['id']} {t}: {found['voxels']} voxels, gap {found.get('gap_mm')} mm to {found.get('nearest_release_level')}, "
                                 f"undrawn between: {undrawn}")
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
    s.add_argument("--device", default="gpu")
    s.add_argument("--threads", type=int, default=4)
    s.set_defaults(go=run)
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
