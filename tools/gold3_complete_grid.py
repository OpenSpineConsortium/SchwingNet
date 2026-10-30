"""The gold tier 3 completion on the grid: the census's SPINEPS masks brought onto each study's release
grid, the matcher run over them, and the report that leaves the grid.

    python3 tools/gold3_complete_grid.py prepare --admission data/gold3-ct/admission.json --facts data/gold3-ct \\
        --tiers DIR --verse-masks DIR --ts-root DIR --out DIR [--ssn DIR] [--python PY]
    python3 tools/gold3_complete_grid.py report --out DIR

Why this exists. The field test (tools/gold3_field.py) admits a CT whose volume shows C2's foot and
the sacrum's top whatever its masks hold, and lists the levels its release does not draw
(admission.json, complete). The owner's rule is that those levels come from SPINEPS's masks already
on the grid, never a new run and never TotalSegmentator, kept as a machine arm beside the release's
masks and never pooled with them; on 2026-10-29 at 15:22 UTC he gave the count for it, one CPU job
that reads the census's masks and segments nothing. The matcher that decides which of SPINEPS's
levels may stand for a missing one is bordercall's holdings/fullspine_complete.py, vendored under
grid/bordercall/; this tool does the grid's part around it, in three steps of one job
(grid/bordercall-complete.sbatch, the word `bordercall complete`):

1. prepare: for every study the admission asks to complete, or holds for a look at its head end, find
   the census's row for the same CT (tier1.tsv, then tier2.tsv, of 06_transitional_ct_census's
   TIERS.md: a VerSe row by its series id in the CT's path, a TotalSegmentator row by its v300 id),
   take the SPINEPS vertebra mask, subregion mask and centroid file the row prefers, relabel a mask
   that carries SPINEPS's raw instance ids through its centroid file with spinesurg-ct-nnunet's guard,
   as the census does, and bring both masks onto the release's grid: left as they are where the grids
   agree, reoriented where only the axes' order or sign differs (no voxel moves), and resampled
   nearest-neighbour where the lattices differ, each recorded in the study's input record, which the
   matcher copies into its row and folds into its digest. The release is VerSe's int16 copies on the
   data root (verse_masks_2026_10_29, lossless, SchwingNet #460) or TotalSegmentator v3's
   segmentations/ folder, found wherever the release nests the subject under totalsegmentator_v300,
   as the census finds it. A study with no row, no mask, no subregion mask or no release on the grid
   is listed with its reason and not run; ENHANCE.PET's one study is among them, since its masks are
   not on the grid and the census holds no SPINEPS mask of it.
2. the matcher itself, over jobs.json, into OUT/matcher/ (records.jsonl, facts.jsonl, masks/).
3. report: the counts, one line per study (its store, how its ids were read, how its grid related to
   the release's, what was asked, added and refused, and the arm's file name, which carries its own
   sha256) and every refusal's reason, short, so the report the gate prints is the record a person
   reads; the records and masks stay on the lab volume. No path under the data root is written into
   the report, only store names and file names.

The segmenter record copied into every row names SPINEPS, the version the grid's environment holds
and that these masks were made by the census before this job, not by it; the container's arm
(SPINEPS 2.1.2, holdings/spineps_run/) is another arm and is never pooled with this one.

Standard library here; numpy, nibabel and scipy are imported where a mask is read, so the parts that
need none of them are tested without them (tests/test_gold3_complete_grid.py).
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

MEMBERS = ("verse", "totalsegmentator")
ORDER = (*[f"C{i}" for i in range(1, 8)], *[f"T{i}" for i in range(1, 14)], *[f"L{i}" for i in range(1, 7)], "sacrum")
MIN_VOXELS = 200                # a release level drawn, as the field test and the matcher count it
AFFINE_SLACK_MM = 0.01          # an affine this close to the release's is header noise, not another grid
TIER_FILES = ("tier1.tsv", "tier2.tsv")
VERSE_IN_PATH = re.compile(r"scan-([A-Za-z0-9]+)_ct\b")
VERSE_IN_MASK = re.compile(r"VERSE_([A-Za-z0-9]+)_")
TS_IN_CASE = re.compile(r"^ts:(s\d{4})$")
TS_IN_PATH = re.compile(r"/(s\d{4})/ct\.nii(\.gz)?$")
TS_IN_MASK = re.compile(r"TSV3C?_(s\d{4})_")
REASON_CHARS = 160


# ---- which studies, with which targets ------------------------------------------------------

def rows_of(path):
    with open(path, encoding="ascii") as f:
        return {row["id"]: row for row in map(json.loads, f)}


def drawn(row):
    return [n for n in ORDER if n in row["levels"] and row["levels"][n]["voxels"] >= MIN_VOXELS]


def head_targets(row):
    """C2 and every undrawn name down to the head-most drawn level, which the field test would ask
    for were the head end in view (bordercall holdings/spineps_run/make_complete_jobs.py)."""
    names = [n for n in drawn(row) if n != "sacrum"]
    if not names:
        return []
    top = names[0]
    if top == "C1":
        return ["C2"]
    return [n for n in ORDER[1:ORDER.index(top)] if n not in names]


def studies_to_complete(admission_path, facts_dir):
    """Every study the admission asks to complete or holds for a look, with its targets in column order."""
    with open(admission_path, encoding="ascii") as f:
        admission = json.load(f)
    facts = {}
    for member in MEMBERS:
        path = os.path.join(facts_dir, member, "facts.jsonl")
        facts[member] = rows_of(path) if os.path.exists(path) else {}
    out = []
    for s in admission["studies"]:
        if not (s["complete"] or s["verdict"] == "look"):
            continue
        targets = list(s["complete"])
        row = facts.get(s["member"], {}).get(s["id"])
        if s["verdict"] == "look" and s["head"] == "border" and row is not None:
            targets += head_targets(row)
        targets = [n for n in ORDER if n in targets]
        out.append({"id": s["id"], "member": s["member"], "targets": targets, "verdict": s["verdict"],
                    "head": s["head"], "foot": s["foot"], "has_facts": row is not None})
    return out


# ---- the census's rows ----------------------------------------------------------------------

def read_tiers(tiers_dir):
    """Every row of tier1.tsv then tier2.tsv, as the census wrote it."""
    rows = []
    for name in TIER_FILES:
        path = os.path.join(tiers_dir, name)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh, delimiter="\t"):
                rows.append(dict(r, tier_file=name))
    return rows


def verse_sid(row):
    for text, pattern in ((row.get("ct_path") or "", VERSE_IN_PATH), (row.get("spineps_vert") or "", VERSE_IN_MASK)):
        found = pattern.search(text)
        if found:
            return found.group(1)
    return None


def ts_id(row):
    found = TS_IN_CASE.match(row.get("case_id") or "")
    if found:
        return found.group(1)
    for text, pattern in ((row.get("ct_path") or "", TS_IN_PATH), (row.get("spineps_vert") or "", TS_IN_MASK)):
        found = pattern.search(text)
        if found:
            return found.group(1)
    return None


def index_rows(rows):
    """{member: {study id: row}}, the first row of a CT keeping its place (tier 1 before tier 2), and
    the ids that had more than one row."""
    index = {member: {} for member in MEMBERS}
    doubled = []
    for row in rows:
        for member, key in (("verse", verse_sid(row)), ("totalsegmentator", ts_id(row))):
            if key is None:
                continue
            if key in index[member]:
                doubled.append((member, key))
            else:
                index[member][key] = row
    return index, doubled


def short_store(value):
    """A store's name without any path above it: the census may write the folder."""
    value = (value or "").strip().rstrip("/")
    if "/" in value:
        return "/".join(value.split("/")[-2:])
    return value or "unnamed"


# ---- the release on the grid ----------------------------------------------------------------

TS_SUBJECT = re.compile(r"^s\d{4}$")
_TS_FOLDERS = {}


def ts_subject_folder(ts_root, sid):
    """The subject's folder under totalsegmentator_v300, wherever the release nests it.

    The data root's copy keeps the subjects under the release's own folder, not at the root, and the
    first completion job (40870822) left 14 TotalSegmentator studies unprepared by looking only at
    <root>/<id>/. So <root>/<id>/ is tried first and then the root is walked once, as the census
    finds the subjects (tools/gold3_census.py ts_subjects): the first folder of the subject's name
    that holds a ct.nii.gz."""
    direct = os.path.join(ts_root, sid)
    if os.path.isdir(os.path.join(direct, "segmentations")):
        return direct
    if ts_root not in _TS_FOLDERS:
        found = {}
        for folder, dirs, files in os.walk(ts_root):
            if TS_SUBJECT.match(os.path.basename(folder)) and "ct.nii.gz" in files:
                found.setdefault(os.path.basename(folder), folder)
                dirs[:] = []
        _TS_FOLDERS[ts_root] = found
    return _TS_FOLDERS[ts_root].get(sid)


def release_of(member, sid, verse_masks, ts_root):
    """(path, reason): the study's release masks on the grid, or why they are not there."""
    if member == "verse":
        path = os.path.join(verse_masks, sid + ".nii.gz")
        return (path, None) if os.path.exists(path) else (None, "no int16 copy of the VerSe mask on the data root (verse_masks_2026_10_29)")
    if member == "totalsegmentator":
        subject = ts_subject_folder(ts_root, sid)
        if subject is None:
            return None, "no folder of the subject's name with a ct.nii.gz under totalsegmentator_v300"
        folder = os.path.join(subject, "segmentations")
        if not os.path.isdir(folder):
            return None, "no segmentations/ folder for the subject under totalsegmentator_v300"
        if not any(name.startswith("vertebrae_") for name in os.listdir(folder)):
            return None, "the subject's segmentations/ folder holds no vertebrae_*.nii.gz"
        return folder, None
    return None, "the member's release masks are not on the grid, and the census holds no SPINEPS mask of it"


# ---- the masks, read and brought onto the release grid ----------------------------------------

def load_guard(ssn):
    """spinesurg-ct-nnunet's spineps_ids, where the grid has it; None elsewhere."""
    tools = os.path.join(ssn, "tools")
    if not os.path.exists(os.path.join(tools, "spineps_ids.py")):
        return None
    if tools not in sys.path:
        sys.path.append(tools)
    try:
        import spineps_ids                                      # noqa: F401
        return spineps_ids
    except Exception:                                           # noqa: BLE001
        return None


class NotPrepared(Exception):
    """A study left out of the matcher's jobs, with its reason."""


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def release_grid(member, release):
    """(shape, affine) of the release's masks, from the first file."""
    import nibabel as nib
    path = release
    if member == "totalsegmentator":
        names = sorted(n for n in os.listdir(release) if n.startswith("vertebrae_") or n == "sacrum.nii.gz")
        path = os.path.join(release, names[0])
    img = nib.load(path)
    return tuple(int(n) for n in img.shape[:3]), img.affine.copy()


def named_vertebrae(row, guard):
    """The SPINEPS vertebra mask as a NIfTI image in VerSe's ids, and a note on how its ids were read:
    as written for a verse_coded or relabelled mask; through the centroid file with the guard for a raw
    one, as the census reads it (tools/bordercall_corpus.py does the same)."""
    import nibabel as nib
    import numpy as np
    vert = row["spineps_vert"]
    if (row.get("spineps_ids") or "") != "raw":
        return nib.load(vert), row.get("spineps_ids") or "as written"
    if guard is None:
        raise NotPrepared("raw ids and no spineps_ids.py to relabel them through the centroid file")
    ctd = row.get("spineps_ctd") or ""
    if not ctd or not os.path.exists(ctd):
        raise NotPrepared("raw ids and no centroid file")
    points = guard.read_ctd(ctd)
    if not points:
        raise NotPrepared("raw ids and an empty centroid file")
    a0, A0, _ = guard.load_mask(vert)
    semantic = None
    spine = row.get("spineps_spine") or ""
    if spine and os.path.exists(spine):
        sa, sA, _ = guard.load_mask(spine)
        semantic = (sa, sA)
    try:
        arr, _ = guard.relabel_by_ctd(a0, A0, points, semantic=semantic)
    except Exception as exc:                                    # noqa: BLE001
        raise NotPrepared("relabel_by_ctd refused: %s" % str(exc)[:REASON_CHARS]) from exc
    return nib.Nifti1Image(np.asarray(arr).astype(np.int16), A0), "relabelled in memory through the centroid file"


def onto_release_grid(img, shape, affine):
    """(image on the release's grid, how): the mask as it is where its grid is the release's, reoriented
    where only the axes' order or sign differs, which moves no voxel, resampled nearest-neighbour where
    the lattices differ; the image written carries the release's affine exactly, so header noise under
    AFFINE_SLACK_MM never reads as another grid downstream."""
    import nibabel as nib
    import numpy as np
    how = {"source_shape": [int(n) for n in img.shape[:3]],
           "source_zooms_mm": [round(float(z), 4) for z in img.header.get_zooms()[:3]],
           "source_axcodes": "".join(nib.aff2axcodes(img.affine))}
    same_shape = tuple(int(n) for n in img.shape[:3]) == tuple(shape)
    if same_shape and np.allclose(img.affine, affine, atol=AFFINE_SLACK_MM):
        how.update(grid="same", max_affine_difference_mm=round(float(np.abs(img.affine - affine).max()), 5))
        return nib.Nifti1Image(np.asanyarray(img.dataobj), affine), how
    transform = nib.orientations.ornt_transform(nib.io_orientation(img.affine), nib.io_orientation(affine))
    moved = img.as_reoriented(transform)
    if tuple(int(n) for n in moved.shape[:3]) == tuple(shape) and np.allclose(moved.affine, affine, atol=AFFINE_SLACK_MM):
        how.update(grid="reoriented", max_affine_difference_mm=round(float(np.abs(moved.affine - affine).max()), 5))
        return nib.Nifti1Image(np.asanyarray(moved.dataobj), affine), how
    from nibabel.processing import resample_from_to
    data = np.asanyarray(img.dataobj)
    labels_before = {int(v): int(c) for v, c in zip(*np.unique(data, return_counts=True)) if v != 0}
    resampled = resample_from_to(nib.Nifti1Image(data, img.affine), (tuple(shape), affine), order=0)
    out = np.asanyarray(resampled.dataobj).astype(data.dtype)
    labels_after = {int(v): int(c) for v, c in zip(*np.unique(out, return_counts=True)) if v != 0}
    how.update(grid="resampled_nearest", voxels_by_label_before=labels_before, voxels_by_label_after=labels_after)
    return nib.Nifti1Image(out, affine), how


def label_counts(img, labels):
    import numpy as np
    data = np.asanyarray(img.dataobj)
    return {str(label): int(np.count_nonzero(data == label)) for label in labels}


def prepare_study(study, row, release, out_dir, guard):
    """Write OUT/prepared/<id>/vert.nii.gz, spine.nii.gz and input.json; return the input record."""
    import nibabel as nib
    spine = row.get("spineps_spine") or ""
    if not spine or not os.path.exists(spine):
        raise NotPrepared("the census row names no subregion mask (spineps_spine), which rule 6 reads")
    if not os.path.exists(row["spineps_vert"]):
        raise NotPrepared("the census row's vertebra mask is not there")
    shape, affine = release_grid(study["member"], release)
    vert, ids_note = named_vertebrae(row, guard)
    vert_out, vert_how = onto_release_grid(vert, shape, affine)
    spine_out, spine_how = onto_release_grid(nib.load(spine), shape, affine)
    record = {"arm": "grid",
              "source": {"store": short_store(row.get("spineps_store")), "tier_file": row.get("tier_file"),
                         "ids": row.get("spineps_ids") or "", "ids_read": ids_note,
                         "vertebrae": {"file": os.path.basename(row["spineps_vert"]), "sha256": sha256_of(row["spineps_vert"])},
                         "subregions": {"file": os.path.basename(spine), "sha256": sha256_of(spine)},
                         "centroids": ({"file": os.path.basename(row["spineps_ctd"]), "sha256": sha256_of(row["spineps_ctd"])}
                                       if row.get("spineps_ctd") and os.path.exists(row["spineps_ctd"]) else None)},
              "vertebrae_grid": vert_how, "subregions_grid": spine_how,
              "subregion_labels": label_counts(spine_out, (49, 100)),
              "release": {"grid": "the release's masks on the data root", "shape": list(shape)}}
    folder = os.path.join(out_dir, "prepared", study["id"])
    os.makedirs(folder, exist_ok=True)
    for name, img in (("vert.nii.gz", vert_out), ("spine.nii.gz", spine_out)):
        target = os.path.join(folder, name)
        nib.save(img, target + ".tmp.nii.gz")
        os.replace(target + ".tmp.nii.gz", target)
    with open(os.path.join(folder, "input.json"), "w", encoding="ascii") as f:
        json.dump(record, f, indent=1, sort_keys=True)
    return record


def segmenter_record(python):
    """What the grid's SPINEPS environment says of itself, read with the job's own interpreter."""
    version, python_version = "not read", "not read"
    if python:
        try:
            out = subprocess.run([python, "-c", "import importlib.metadata as m, sys\n"
                                  "print(m.version('spineps'))\nprint(sys.version.split()[0])"],
                                 capture_output=True, text=True, timeout=120, check=False)
            if out.returncode == 0:
                version, python_version = out.stdout.split()[:2]
            else:
                version = "not importable in the job's environment"
        except (OSError, subprocess.TimeoutExpired, ValueError):
            version = "not read"
    return {"name": "SPINEPS", "version_in_environment": version, "python": python_version, "arm": "grid",
            "masks": "the transitional census's SPINEPS masks on the grid, made before this job and never re-run "
                     "(spine-program 06_transitional_ct_census, docs/ruleclass/TIERS.md section 4); each row names its store",
            "note": "the version is the environment's, which the census ran its harvest with where it says so; the masks' own "
                    "run is the census's record, not this job's"}


def prepare(args):
    studies = studies_to_complete(args.admission, args.facts)
    index, doubled = index_rows(read_tiers(args.tiers))
    guard = load_guard(args.ssn)
    os.makedirs(args.out, exist_ok=True)
    inventory, jobs = [], []
    for study in studies:
        entry = dict(study, state="not_prepared", reason=None, source=None, grid=None)
        row = index.get(study["member"], {}).get(study["id"])
        release, why = release_of(study["member"], study["id"], args.verse_masks, args.ts_root)
        if study["member"] not in MEMBERS:
            entry["reason"] = "member %s: %s" % (study["member"], why)
        elif row is None:
            entry["reason"] = "no census row for this CT in tier1.tsv or tier2.tsv"
        elif not (row.get("spineps_vert") or ""):
            entry["reason"] = "the census row names no SPINEPS mask"
        elif release is None:
            entry["reason"] = why
        elif not study["has_facts"]:
            entry["reason"] = "no facts row for the study in data/gold3-ct"
        else:
            try:
                record = prepare_study(study, row, release, args.out, guard)
            except NotPrepared as exc:
                entry["reason"] = str(exc)
            except Exception as exc:                            # noqa: BLE001
                entry["reason"] = "%s: %s" % (type(exc).__name__, str(exc)[:REASON_CHARS])
            else:
                entry.update(state="prepared", source=record["source"],
                             grid={"vertebrae": record["vertebrae_grid"]["grid"], "subregions": record["subregions_grid"]["grid"]})
                folder = os.path.join(args.out, "prepared", study["id"])
                jobs.append({"id": study["id"], "member": study["member"], "release": release,
                             "machine": os.path.join(folder, "vert.nii.gz"), "spine": os.path.join(folder, "spine.nii.gz"),
                             "input": os.path.join(folder, "input.json"), "targets": study["targets"],
                             "verdict": study["verdict"], "head": study["head"], "foot": study["foot"]})
        inventory.append(entry)
    spec = {"segmenter": segmenter_record(args.python),
            "facts": {member: os.path.join(args.facts, member, "facts.jsonl") for member in MEMBERS},
            "studies": jobs}
    with open(os.path.join(args.out, "jobs.json"), "w", encoding="ascii") as f:
        json.dump(spec, f, indent=1)
    with open(os.path.join(args.out, "inventory.json"), "w", encoding="ascii") as f:
        json.dump({"studies": inventory, "doubled_rows": sorted(set(doubled)), "guard": guard is not None,
                   "segmenter": spec["segmenter"]}, f, indent=1, sort_keys=True)
    prepared = sum(e["state"] == "prepared" for e in inventory)
    print("%d studies asked; %d prepared for the matcher; %d not (inventory.json says why)"
          % (len(inventory), prepared, len(inventory) - prepared))
    return 0


# ---- the report -----------------------------------------------------------------------------

def read_jsonl(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="ascii") as f:
        return [json.loads(line) for line in f if line.strip()]


def short(text, chars=REASON_CHARS):
    text = " ".join(str(text).split())
    return text if len(text) <= chars else text[:chars - 3] + "..."


def refusal_lines(record):
    out = []
    for outcome in record.get("targets", []):
        if outcome.get("state") == "refused":
            out.append("%s %s: %s" % (record["id"], outcome["name"], short(outcome.get("reason", ""))))
    return out


def study_line(entry, record):
    source = entry.get("source") or {}
    grid = entry.get("grid") or {}
    cells = [entry["id"], entry["member"], source.get("store", "-"), source.get("ids", "-") or "-",
             "/".join(dict.fromkeys([grid.get("vertebrae", "-"), grid.get("subregions", "-")])),
             " ".join(entry["targets"]) or "-"]
    if record is None:
        cells += ["-", "-", "not run"]
    elif "error" in record:
        cells += ["-", "-", "error: " + short(record["error"], 80)]
    else:
        arm = " ".join(record.get("files", {}).get("arm", {}).keys()) or "-"
        cells += [" ".join(record.get("added", [])) or "-", " ".join(record.get("refused", [])) or "-", arm]
    return "| " + " | ".join(cells) + " |"


def report(args):
    with open(os.path.join(args.out, "inventory.json"), encoding="ascii") as f:
        inventory = json.load(f)
    records = {r["id"]: r for r in read_jsonl(os.path.join(args.out, "matcher", "records.jsonl"))}
    studies = inventory["studies"]
    by_member = {}
    for entry in studies:
        by_member[entry["member"]] = by_member.get(entry["member"], 0) + 1
    prepared = [e for e in studies if e["state"] == "prepared"]
    done = [records.get(e["id"]) for e in prepared]
    added = [r for r in done if r and r.get("added")]
    errors = [r for r in done if r and "error" in r]
    lines = ["- studies asked: %d (%s); prepared for the matcher: %d; not prepared: %d"
             % (len(studies), ", ".join("%s %d" % kv for kv in sorted(by_member.items())), len(prepared), len(studies) - len(prepared)),
             "- matcher rows: %d; studies with a level added: %d; levels added: %d; studies refused whole: %d; error rows: %d"
             % (sum(r is not None for r in done), len(added), sum(len(r["added"]) for r in added),
                sum(1 for r in done if r and "error" not in r and not r.get("added")), len(errors)),
             "- segmenter: %s %s (%s)" % (inventory["segmenter"]["name"], inventory["segmenter"]["version_in_environment"],
                                        "the census's masks, never re-run"),
             "- raw-id guard importable: %s; census rows doubled: %d" % ("yes" if inventory.get("guard") else "no", len(inventory.get("doubled_rows", []))),
             "", "| id | member | store | ids | grid | asked | added | refused | arm file |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    lines += [study_line(e, records.get(e["id"])) for e in studies]
    refusals = [line for e in prepared for line in refusal_lines(records.get(e["id"]) or {})]
    if refusals:
        lines += ["", "refusals (each target's reason, cut to %d characters; the records hold them whole):" % REASON_CHARS]
        lines += ["- " + line for line in refusals]
    left = [e for e in studies if e["state"] != "prepared"]
    if left:
        lines += ["", "not prepared:"] + ["- %s (%s): %s" % (e["id"], e["member"], e["reason"]) for e in left]
    if errors:
        lines += ["", "error rows:"] + ["- %s: %s" % (r["id"], short(r["error"])) for r in errors]
    print("\n".join(lines))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare", help="the census's masks onto the release grids, and jobs.json for the matcher")
    p.add_argument("--admission", required=True)
    p.add_argument("--facts", required=True, help="data/gold3-ct, holding <member>/facts.jsonl")
    p.add_argument("--tiers", required=True, help="the census's tier1.tsv and tier2.tsv")
    p.add_argument("--verse-masks", required=True, help="the int16 copies of VerSe's masks, <sid>.nii.gz")
    p.add_argument("--ts-root", required=True, help="totalsegmentator_v300, <id>/segmentations/")
    p.add_argument("--out", required=True)
    p.add_argument("--ssn", default=os.path.expanduser("~/spinesurg-ct-nnunet"))
    p.add_argument("--python", default=sys.executable, help="the interpreter whose SPINEPS the record names")
    p.set_defaults(run=prepare)
    r = sub.add_parser("report", help="the report's lines from inventory.json and the matcher's records")
    r.add_argument("--out", required=True)
    r.set_defaults(run=report)
    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
