"""Set FleXray's synthetic DRRs beside every held real X-ray corpus: maps and separation tests.

The owner's ask of 2026-10-25 (SchwingNet #391, the FleXray audit; the thread "Compare FleXray
DRRs to real X-ray corpora"): plot FleXray's synthetic DRRs alongside the held X-ray corpora, plain
film and fluoroscopy, in t-SNE and other dimension-reduction maps, and run the statistical tests
for separation a machine-learning reviewer would expect. docs/research/drr-domain-gap/README.md is
the pre-registered design; this tool is its one job, run by grid/bench.sbatch as the bench id
flexray_drr_gap, in the job's own environment (flexray, nanodrr, scikit-learn and umap-learn over
train-gpu's torch), once the owner gives the word and the count.

    python tools/domain_gap.py run --groups data/domain_gap/groups.json --data-root <data root> \\
        --index <samples.sqlite> --weights <FleXray bundle dir> --imagenet <resnet18 file> \\
        --out <dir> [--device cuda] [--workers 4] [--wandb auto|off] [--frozen <test-persons.json>] \\
        [--spineps <data root>/spineps] [--moose <data root>/moose] [--skip-masks spineps|moose ...]
    python tools/domain_gap.py plan --groups ... --data-root ... --out <dir> [the same flags less
        --weights and --imagenet]
    python tools/domain_gap.py summary --out <dir>

Stages, each written under --out and skipped when its output is there for the same inputs: the
renders (tools/flexray_render.py from held TotalSegmentator CTs, each render group a recipe of
named blocks, schwingnet.render_blocks, through this project's code or FleXray's own; the groups
on one CT folder render the same CTs, chosen once in the salted order among the CTs that have
masks under every segmenter those groups name whose masks are read, SPINEPS's existing masks
under --spineps and MOOSE's under --moose, so the seven render groups, flexray_drr,
flexray_drr_ct, flexray_replica, flexray_reference, flexray_spineps, fluxray_raw and
fluxray_raw_reference, differ only by their recipe and engine, and the replication test reads each
recipe through our blocks against the same recipe through FleXray's code; a DRR's pixels are a
projection of the CT alone, so the groups on segmenter none, flexray_drr_ct and the two FluXray
raw groups, read no mask and render wherever the CTs are, while a group whose segmenter's masks
are not read, no folder of them, one that holds no CT's masks or one --skip-masks names, is
skipped with that reason and the others render, the owner's word of 2026-10-27), the plan (which files of which groups,
data/domain_gap/groups.json, chosen by person in a
salted order, frozen test persons left out), the images (each decoded, MONOCHROME1 inverted,
windowed to its 0.5-99.5 percentiles, cut to the centre square of 0.9 of its shorter side and
resized to 256, as float16), the features (three spaces: FleXray's own encoder, an ImageNet
ResNet-18 and handcrafted physics measures, each taken on the image and on its inverse, whose mean
is the inversion-invariant feature the primary analysis reads, since fluoroscopy is often shown
bone-dark and DRRs bone-bright), and the analysis (tools/domain_gap_stats.py: PCA, t-SNE, UMAP and
LDA maps with their trustworthiness; person-grouped classifier two-sample tests with cluster
bootstrap intervals and permutation p-values; MMD with person-level permutations, a contrast of
two render groups on one CT folder read as the paired sample it is, since their views are twins
of one CT; Frechet distance and KID in each space's first 64 principal components; precision,
recall, density and coverage; silhouette and neighbour purity; split-half nulls as the
calibration; Benjamini-Hochberg within a space).

The choice of CTs is written to <out>/render-subjects.json, {folder: [subject ids]}, by `run` and
by `plan`, which makes that choice alone, rendering and decoding nothing: the grid's segment job
(tools/flexray_render.py segment, the bench id flexray_drr_seg) reads it to make MOOSE's masks for
exactly those CTs. Since that job runs before any MOOSE mask exists, `plan` chooses among the CTs
with masks under every segmenter named but the ones the segment job makes (MADE_SEGMENTERS), and
`run` among those with masks under every one, which is the same set once the segment job has done
them all and a smaller one, said in the plan and the summary, where it has not.

What leaves the grid is summary.txt, at most 80 lines of numbers and group names that the bench
report carries; results.json, the figures and the plan, which names files, stay in --out (umask 077)
and the figures and the map coordinates go to W&B where the grid's key is found. tools/ never goes
on sys.path, since tools/profile.py would shadow the standard library's profile, which torch
imports.
"""

import argparse
import fnmatch
import hashlib
import importlib.util
import io
import json
import math
import multiprocessing
import os
import re
import sqlite3
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [entry for entry in sys.path if Path(entry or ".").resolve() != ROOT / "tools"]
for folder in (ROOT / "vendor" / "beethoven-qa" / "src", ROOT / "src"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

SIDE = 256
CROP_SHARE = 0.9
WINDOW = (0.5, 99.5)
DEFAULT_FORMATS = ("png", "jpeg", "tiff", "bmp", "dicom", "jpeg2000")
PROJECTION_MODALITIES = ("CR", "DX", "RF", "XA", "DF", "RG", "PX", "OT", "SC")
SUFFIX_FORMATS = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".tif": "tiff", ".tiff": "tiff",
                  ".bmp": "bmp", ".dcm": "dicom", ".dicom": "dicom", ".jp2": "jpeg2000", ".npy": "npy"}
PLACEHOLDERS = {"", "anonymous", "anonymous^", "anonymized", "anonymised", "anon", "none", "unknown",
                "unknown_patient", "0", "00000000", "-", "na", "n/a", "null"}
WALK_LIMIT = 400_000
MAP_ROWS = 600          # rows a group gives the maps, so t-SNE stays balanced and fast
POOL_ROWS = 300         # rows a real group gives its pooled family, so no one corpus outweighs the rest
MIN_ROWS = 20           # a group with fewer decoded images is left out of everything
MIN_PERSONS = 5         # fewer persons: plotted, never tested (a grouped split needs persons)
SPLIT_PERSONS = 40      # a split-half null needs this many persons
FD_ROWS = 250           # rows a side every FD64 is taken at, so the distances compare
PERMUTATIONS_C2ST = 100
PERMUTATIONS_MMD = 1000
BOOTSTRAP = 1000
SPACES = ("flexray", "imagenet", "physics")
PRIMARY_SPACE = "flexray"
# The primary endpoints, read in most detail: FleXray's physical render, the same render from the
# CT alone with no mask read (added on 2026-10-27, before any number was seen, on the owner's word
# that the comparison with real X-rays should run without segmentation), and FluXray.
FOCUS_GROUPS = ("flexray_drr", "flexray_drr_ct", "fluxray")
# The replication test's pairs, in the order the summary reads them: FleXray's MOOSE recipe through
# this project's render blocks against the same recipe through FleXray's own code, the study's
# verdict; FluXray's raw-render recipe (the paper's 90 fixed poses) through our blocks against the
# same through FleXray's primitives; the physical render from the CT alone against the physical
# render on MOOSE's labels, which isolates what the labels' aiming does (the crops weighted by the
# structures they hold and the isocentre on a structure, the attenuation off in both; the crops,
# isocentres and poses are not shared, since the draws differ); the physical render against the
# recipe, which isolates the attenuation randomisation; the production labels (SPINEPS) against
# the replication's (MOOSE),
# which shares the CTs and the seeds with it while the crops, isocentres and poses follow the
# labels, since FleXray's recipe draws them from the label volume before the pose (so the pair
# reads the segmenter with everything the labels decide); and the raw renders against the
# FLUX-edited FluXray, which isolates the edit with the pose recipe held the same.
REPLICATION_PAIRS = (("flexray_replica", "flexray_reference"), ("fluxray_raw", "fluxray_raw_reference"),
                     ("flexray_drr_ct", "flexray_drr"), ("flexray_drr", "flexray_replica"),
                     ("flexray_spineps", "flexray_replica"), ("fluxray_raw_reference", "fluxray"))
# The pairs that get the pre-registered word: one recipe through two engines.
REPLICATION_WORDED = REPLICATION_PAIRS[:2]
# The groups that exist for the replication tests alone: their contrasts with the real corpora
# are secondary, so the summary gives them up first.
REPLICATION_ONLY = ("flexray_replica", "flexray_reference", "fluxray_raw", "fluxray_raw_reference")
# The masks the segment job (tools/flexray_render.py segment, the bench id flexray_drr_seg) makes
# for the CTs this study chooses, reading the choice from render-subjects.json: the plan subcommand
# that writes it for that job chooses without them, since none exists before the job has run.
MADE_SEGMENTERS = ("moose",)
# The segmenters whose masks a render group can read, each from --spineps and --moose or the data
# root's folder of its name; --skip-masks leaves one out for a run by hand.
MASK_SEGMENTERS = ("spineps", "moose")
LEFT_OUT = "left out by --skip-masks"
# A folder that is there and holds no CT's masks, as a segment job that stopped on its first CT
# leaves one, is read as no masks at all: required, it would leave the folder no CT to choose and
# skip the groups that read no mask with the rest.
NO_MASKS = "no CT here has them"
RENDER_SUBJECTS = "render-subjects.json"
LINE_BUDGET = 80        # lines of summary.txt, what the bench report carries off the grid
THUNDER = "thunderdb://"


class StageError(Exception):
    """A stage that cannot run, with the reason a person reads in the report."""


# --- the neighbours: the pure rules, the numerics and the renderer --------------------------------

def rules():
    """schwingnet.domain_gap, the pure rules under beethoven-qa's gate."""
    from schwingnet import domain_gap

    return domain_gap


def blocks_rules():
    """schwingnet.render_blocks, the renderer's named parts, under the same gate."""
    from schwingnet import render_blocks

    return render_blocks


def tool(name):
    """A neighbouring tool by path, since tools/ is never on sys.path."""
    spec = importlib.util.spec_from_file_location(f"{name}_tool", ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data):
    """Write a JSON file whole: to a neighbour first, then renamed, so a cut job leaves none half."""
    path = Path(path)
    part = path.with_name(path.name + ".part")
    part.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(part, path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def log(text):
    print(f"drr-gap {time.strftime('%H:%M:%S')} {text}", flush=True)


# --- the plan: which files of which groups ---------------------------------------------------------

def read_table(path):
    """The group table, held to schwingnet.domain_gap.GroupTable."""
    return rules().GroupTable.model_validate_json(Path(path).read_text(encoding="utf-8"))


def frozen_persons(path):
    """The frozen test persons as (source, case) pairs; none when no file is named."""
    if not path:
        return set()
    return {tuple(row["person"].split(":", 1)) for row in read_json(path) if ":" in row["person"]}


def is_frozen(group_id, person, frozen):
    """A frozen person names a source and a case; a group whose id begins with that source holds
    that person when its own person key is the case."""
    return any(group_id.startswith(source) and person == case for source, case in frozen)


def excluded(relative, words):
    """True when a word of the path begins with an excluded word (masks, labels, crops and the
    like), so a mask beside its film is never taken for a film."""
    tokens = [t for t in re.split(r"[^a-z0-9]+", relative.lower()) if t]
    return any(t.startswith(w) for t in tokens for w in words)


def matches(relative, globs):
    return not globs or any(fnmatch.fnmatch(relative, g) for g in globs)


def index_rows(index, sources):
    """The image rows of the sample index under the named roots. A root the index calls
    unmapped:<folder> may be named by its folder alone, so both spellings are asked for."""
    names = set(sources) | {f"unmapped:{s}" for s in sources if ":" not in s}
    marks = ",".join("?" * len(names))
    query = ("SELECT path, rel, format, CAST(width AS INTEGER), CAST(height AS INTEGER),"
             " CAST(depth AS INTEGER), modality, patient_id, study_uid FROM sample"
             f" WHERE role = 'image' AND error IS NULL AND sources IN ({marks})")
    with sqlite3.connect(f"file:{index}?mode=ro", uri=True) as connection:
        return connection.execute(query, sorted(names)).fetchall()


def keep_index_row(group, row):
    """Whether an index row is an image of the group: its format, its modality, a single plane,
    its size, its path's globs and words."""
    path, relative, form, width, height, depth, modality, _, _ = row
    formats = group.formats or DEFAULT_FORMATS
    if form not in formats or (depth or 1) > 1:
        return False
    if form == "dicom":
        allowed = group.modalities or PROJECTION_MODALITIES
        if (modality or "").upper() not in allowed:
            return False
    if group.min_side and width and height and min(width, height) < group.min_side:
        return False
    return matches(relative, group.globs) and not excluded(relative, group.exclude_words)


def index_candidates(group, index):
    """(file, relative path, patient id, study uid) of every index row the group keeps."""
    if not index or not Path(index).is_file():
        raise StageError("no sample index (samples.sqlite) to read")
    rows = [r for r in index_rows(index, group.index_sources) if keep_index_row(group, r)]
    return [(r[0], r[1], r[7] or "", r[8] or "") for r in rows]


def walk_candidates(group, data_root):
    """(file, relative path, "", "") of every image file under the group's folder."""
    base = Path(data_root) / group.folder
    if not base.is_dir():
        raise StageError(f"no folder {group.folder} under the data root")
    formats = set(group.formats or DEFAULT_FORMATS)
    found, seen = [], 0
    for folder, dirs, files in os.walk(base):
        dirs.sort()
        for name in sorted(files):
            seen += 1
            if seen > WALK_LIMIT:
                return found
            relative = os.path.relpath(os.path.join(folder, name), base)
            form = SUFFIX_FORMATS.get(Path(name).suffix.lower())
            if form in formats and matches(relative, group.globs) and not excluded(relative, group.exclude_words):
                found.append((os.path.join(folder, name), relative, "", ""))
    return found


def thunder_root(group, data_root):
    """The FluXray ThunderDB folder under the group's folder: the one holding data.mdb."""
    base = Path(data_root) / group.folder
    if not base.is_dir():
        raise StageError(f"no folder {group.folder} under the data root (flexray-data not fetched)")
    for mdb in sorted(base.rglob("data.mdb")):
        if all(fnmatch.fnmatch(str(mdb.parent.relative_to(base)), g) for g in group.globs or ("*",)):
            return mdb.parent
    raise StageError(f"no ThunderDB (data.mdb) under {group.folder}")


_THUNDER = {}


def thunder_backend(root, split):
    """FleXray's own reader of a split of a FluXray ThunderDB, opened once a process."""
    key = (str(root), split)
    if key not in _THUNDER:
        from fxr.datasets.storage import SplitThunderDBStorageBackend

        backend = None
        for grouping in ("subject", "sample"):
            try:
                backend = SplitThunderDBStorageBackend(
                    str(root), dataset_name="FluXray", modality="xray", split=split, label_key=None,
                    affine_key=None, spacing_key=None, subject_grouping=grouping, lazy_payload_refs=True)
                break
            except (KeyError, ValueError, TypeError):
                continue
        if backend is None:
            raise StageError(f"FleXray's reader could not open split {split} of the FluXray ThunderDB")
        _THUNDER[key] = (backend, {r.data_id: r for r in backend.records})
    return _THUNDER[key]


def thunder_splits(root):
    from fxr.datasets._thunderdb import open_thunderdb

    with open_thunderdb(root) as db:
        return sorted(db["_splits"].keys())


def thunder_candidates(group, data_root):
    """thunderdb://<root>|<split>|<sample> for every FluXray sample, with its subject as person."""
    root = thunder_root(group, data_root)
    found = []
    for split in thunder_splits(root):
        _, records = thunder_backend(root, split)
        for data_id, record in sorted(records.items()):
            found.append((f"{THUNDER}{root}|{split}|{data_id}", data_id, record.subject_id or "", ""))
    return found


def render_candidates(group, out, shared=None):
    """The renders of the render stage, each with its CT's subject as person; with shared given,
    the rows of those subjects alone (share_subjects), so every render group on one CT folder
    enters the analysis with the same CTs."""
    manifest = Path(out) / "renders" / group.id / "manifest.json"
    failed = manifest.with_name("FAILED")
    if failed.is_file():
        raise StageError(f"the render failed ({failed.read_text(encoding='ascii').strip()})")
    if not manifest.is_file():
        raise StageError("the render stage wrote no manifest")
    base = manifest.parent
    rows = manifest_rows(read_json(manifest))
    if shared is not None:
        keep = set(shared)
        rows = [r for r in rows if r["subject"] in keep]
    return [(str(base / r["file"]), r["file"], r["subject"], "") for r in rows]


def manifest_rows(manifest):
    """The per-view rows of a render manifest: a list, or a record keeping them under "views" or
    "renders" beside the blocks, the engine and the versions."""
    if isinstance(manifest, dict):
        for key in ("views", "renders"):
            if isinstance(manifest.get(key), list):
                return manifest[key]
        raise StageError("the render manifest lists no views")
    return manifest


def dicom_person_rule(group, candidates):
    """dicom:patient falls back to the study for the whole group when the patient ids say
    nothing: all placeholders, or one id on more than half the files."""
    if group.person != "dicom:patient":
        return group.person
    ids = [c[2].strip().lower() for c in candidates]
    real = [i for i in ids if i not in PLACEHOLDERS]
    if not real:
        return "dicom:study"
    commonest = max(set(real), key=real.count)
    return "dicom:study" if real.count(commonest) > len(ids) / 2 else group.person


def persons_of(group, candidates, rule):
    """(file, person) pairs; a file the rule names no person for is its own person."""
    pure = rules()
    pairs, fallback = [], 0
    for path, relative, patient, study in candidates:
        if group.source in ("render", "thunderdb"):
            person = patient
        else:
            person = pure.person_key(rule, relative, patient, study)
        if not person:
            fallback += 1
            person = "file:" + relative
        pairs.append((path, person))
    return pairs, fallback


def plan_group(group, args, salt, frozen, renders):
    """One group's row of the plan: what was found, what was chosen and why anything was not; a
    render group's row also records which CTs it rendered, with what blocks, engine and salt. A
    chosen file's person is <group id>:<person>, so no two corpora share a person by the accident
    of a name, except that a render's person is its CT, <CT folder>:<subject>, whichever group
    rendered it: two render groups on one folder render the same CTs from the same seeds, so their
    views are near-identical twins of one CT, and a contrast between them is a paired sample
    (contrast), never two sets of persons."""
    row = {"id": group.id, "label": group.label, "family": group.family, "source": group.source,
           "licence": group.licence, "note": group.note, "chosen": [], "skipped": ""}
    if group.source == "render":
        row["render"] = renders.get(group.id, {"skipped": "the render stage did not reach it"})
    try:
        candidates = candidate_rows(group, args, renders)
    except StageError as error:
        row["skipped"] = str(error)
        return row
    except Exception as error:  # one group's broken index or reader never stops the others
        traceback.print_exc(file=sys.stderr)
        row["skipped"] = f"its files could not be listed ({type(error).__name__})"
        return row
    rule = dicom_person_rule(group, candidates)
    pairs, fallback = persons_of(group, candidates, rule)
    kept = [(f, p) for f, p in pairs if not is_frozen(group.id, p, frozen)]
    chosen = rules().choose(tuple(kept), group.cap, group.per_person, f"{salt}:{group.id}")
    prefix = group.folder if group.source == "render" else group.id
    row.update(found=len(candidates), persons_found=len({p for _, p in pairs}), person_rule=rule,
               person_fallback=fallback, frozen_dropped=len(pairs) - len(kept),
               chosen=[[f, f"{prefix}:{p}"] for f, p in chosen])
    if not chosen:
        row["skipped"] = "nothing found under its rules"
    return row


def candidate_rows(group, args, renders):
    if group.source == "index":
        return index_candidates(group, args.index)
    if group.source == "walk":
        return walk_candidates(group, args.data_root)
    if group.source == "thunderdb":
        return thunder_candidates(group, args.data_root)
    record = renders.get(group.id, {})
    if record.get("skipped"):
        raise StageError(record["skipped"])
    if "kept" in record and not record["kept"]:
        raise StageError(f"it kept no CT, {len(record.get('passed_over', []))} passed over")
    if record.get("shared") == []:
        raise StageError("no CT kept by every render group on its folder")
    return render_candidates(group, args.out, record.get("shared"))


def stage_plan(args, table, renders=None, folders=None):
    """plan.json: every group's chosen files, made once for the same table, frozen list and
    renders (what stage_render returned: each render group's record, and each CT folder's choice
    of subjects with the mask counts it was made from), so a render that fails in one run and
    succeeds in the next is planned again."""
    renders, folders = renders or {}, folders or {}
    path = Path(args.out) / "plan.json"
    stamp = {"table": sha256_of(args.groups), "frozen": sha256_of(args.frozen) if args.frozen else "",
             "index": index_stamp(args.index), "renders": digest_of(renders), "folders": digest_of(folders)}
    if path.is_file() and read_json(path).get("stamp") == stamp:
        return read_json(path)
    frozen = frozen_persons(args.frozen)
    groups = [plan_group(g, args, table.salt, frozen, renders) for g in table.groups]
    plan = {"version": 1, "salt": table.salt, "stamp": stamp, "groups": groups, "renders": folders}
    write_json(path, plan)
    return plan


def digest_of(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def index_stamp(index):
    """The sample index as the plan's stamp reads it: its path with its size and modification
    time, so a sample index rebuilt at the same path makes the plan again rather than keeping the
    old plan's files; the path alone where none is there, or none is named."""
    if not index or not Path(index).is_file():
        return str(index or "")
    status = Path(index).stat()
    return f"{index} {status.st_size} {status.st_mtime_ns}"


# --- the renders -----------------------------------------------------------------------------------

def stage_render(args, table):
    """The synthetic X-rays of every render group, by tools/flexray_render.py: the CTs of a folder
    are chosen once (render_folders), among those with masks under every segmenter the folder's
    groups name whose masks are read, so every render group on one folder renders the same
    subjects, a group whose segmenter's masks are not read (no folder, one that holds no CT's
    masks, or --skip-masks) being skipped with that reason while the others render (the owner's
    word of 2026-10-27), and the per-view seeds take the folder's salt and not the group's, so two
    groups on one folder differ only by their blocks and engine; once every group has rendered,
    the subjects every group on a folder kept are the ones that enter the analysis
    (share_subjects), since one scheme's masks may hold nothing FleXray supervises for a CT the
    other's do. Returns what each group got and
    each folder's choice, for the plan."""
    renders = {}
    groups = [g for g in table.groups if g.source == "render"]
    if not groups:
        return renders, {}
    renderer = tool("flexray_render")
    roots = mask_roots(args)
    folders = render_folders(args, table, renderer, roots)
    write_subjects(args.out, folders)
    for group in groups:
        folder = folders[group.folder]
        subjects = folder["subjects"][:max(1, group.cap // group.per_person)]
        why = folder.get("skipped") or unread_masks(group, folder)
        if why or not subjects:
            why = why or "no CT has masks under every segmenter required, " + mask_counts(folder)
            log(f"{group.id}: {why}; its renders are skipped")
            renders[group.id] = {"skipped": why}
            continue
        ct_root = Path(args.data_root) / group.folder
        renders[group.id] = render_group(renderer, args, group, ct_root, subjects, f"{table.salt}:{group.folder}", roots)
    share_subjects(renders, groups, folders)
    return renders, folders


def share_subjects(renders, groups, folders):
    """The subjects every render group on one CT folder kept, so a CT one group passed over (its
    masks holding nothing, or nothing that group's scheme supervises: a SPINEPS mask of one L6
    alone is a volume FleXray drops whole) is in no group's rows and every pair compares the
    same CTs: the folder's record says which they are, in the chosen order, each group's which
    of its own it kept outside that set, and render_candidates reads the shared ones alone. A
    group that rendered nothing, skipped, failed or passing every CT over, takes no part in the
    intersection, so one such group empties no other group's rows, and its plan row says what it
    kept (candidate_rows)."""
    for name, folder in folders.items():
        kept = {g.id: renders[g.id]["kept"] for g in groups
                if g.folder == name and renders.get(g.id, {}).get("kept")}
        if not kept:
            continue
        shared = set.intersection(*(set(subjects) for subjects in kept.values()))
        folder["shared"] = [s for s in folder["subjects"] if s in shared]
        for group_id, subjects in kept.items():
            renders[group_id]["shared"] = [s for s in subjects if s in shared]
            renders[group_id]["unshared"] = [s for s in subjects if s not in shared]


def mask_roots(args):
    """The folder of each segmenter's masks, --spineps and --moose or <data root>/<segmenter>,
    those that are there and not named by --skip-masks: a root that is not is left out, so the
    renderer finds no mask under it, the folder's CTs are chosen without it and the groups that
    name it are skipped with the reason the folder's record gives (mask_state)."""
    roots = {}
    for name in MASK_SEGMENTERS:
        given = Path(getattr(args, name, "") or str(Path(args.data_root) / name))
        if not left_out(args, name) and given.is_dir():
            roots[name] = given
    return roots


def left_out(args, name):
    return name in (getattr(args, "skip_masks", None) or ())


def mask_state(args, name, roots):
    """Whether a segmenter's masks are read, by the roots mask_roots found: found, left out by
    --skip-masks, or no folder."""
    if name in roots:
        return "found"
    return LEFT_OUT if left_out(args, name) else "no folder"


def unread_masks(group, folder):
    """Why a render group cannot render, where its recipe's segmenter is one whose masks the run
    does not read (the folder's record of its roots says why); nothing for a group that reads
    them, or none."""
    segmenter = blocks_rules().parse(group.blocks).segmenter
    state = folder.get("roots", {}).get(segmenter, "found")
    if state == "found":
        return ""
    return f"its segmenter {segmenter}'s masks are not read ({state})"


def render_folders(args, table, renderer, roots, pending=()):
    """Each render folder's choice of CTs, made once for every render group on it: the segmenters
    its groups name (schwingnet.domain_gap.segmenters_named, which leaves segmenter none out) less
    the pending ones, the masks the segment job is yet to make, and less those whose masks are not
    read (no folder, or --skip-masks: mask_state), the subjects with masks under each one left,
    and the first of them in the salted order (schwingnet.domain_gap.choose_subjects), as many as
    the largest group needs, every subject being a candidate where none is left; a segmenter
    whose folder holds no CT's masks is not read either (NO_MASKS); with the counts the plan and
    the summary say. A folder that is not there is skipped with its reason."""
    folders = {}
    for group in (g for g in table.groups if g.source == "render"):
        if group.folder in folders:
            continue
        on_folder = [g for g in table.groups if g.source == "render" and g.folder == group.folder]
        ct_root = Path(args.data_root) / group.folder
        if not ct_root.is_dir():
            folders[group.folder] = {"skipped": f"no CT folder {group.folder} under the data root", "subjects": []}
            continue
        named = rules().segmenters_named([g.blocks for g in on_folder])
        count = max(max(1, g.cap // g.per_person) for g in on_folder)
        choice = subject_choice(renderer, ct_root, named, roots, table.salt, count, pending)
        states = {name: mask_state(args, name, roots) for name in named}
        choice["roots"] = states | {name: NO_MASKS for name in choice.pop("empty")}
        folders[group.folder] = choice
    return folders


def subject_choice(renderer, ct_root, named, roots, salt, count, pending):
    """One folder's choice of CTs and the record it is made from: every subject the renderer finds
    under the folder, those with masks under each segmenter required (named less pending, less
    those with no root, whose masks are not read, and less those whose root holds no subject's
    masks, listed as empty), and the first count, in the salted order, of the subjects with masks
    under every one of them; every subject where none is required."""
    pure = rules()
    subjects = frozenset(subject_id(s) for s in renderer.find_subjects(ct_root))
    found = {name: masked_subjects(renderer, ct_root, name, roots) & subjects
             for name in named if name not in pending and name in roots}
    masked = {name: held for name, held in found.items() if held}
    chosen = pure.choose_subjects(subjects, masked, count, salt)
    return {"subjects": list(chosen), "segmenters": list(named), "pending": [n for n in named if n in pending],
            "empty": [name for name in found if name not in masked],
            "ct": len(subjects), "masks": {name: len(held) for name, held in masked.items()},
            "every": len(pure.with_masks(subjects, masked)), "count": count}


def masked_subjects(renderer, ct_root, segmenter, roots):
    """The subjects whose masks a segmenter's scheme finds under its root, as find_subjects lists
    them with a segmenter named; none where the scheme has no root here."""
    if segmenter not in roots:
        return frozenset()
    found = renderer.find_subjects(ct_root, segmenter=segmenter, roots=roots)
    return frozenset(subject_id(s) for s in found)


def mask_counts(folder):
    """A folder's mask counts in words: how many CTs had masks under each segmenter required and
    under every one, of how many CTs, then the named segmenters that were not required: those the
    segment job is yet to make, and those whose masks were not read, with why."""
    pending = folder.get("pending", [])
    states = folder.get("roots", {})
    unread = [name for name in folder.get("segmenters", [])
              if name not in pending and states.get(name, "found") != "found"]
    parts = [f"{name} {folder['masks'].get(name, 0)}" for name in folder.get("segmenters", [])
             if name not in pending and name not in unread]
    text = f"{folder.get('every', 0)} with every mask of {folder.get('ct', 0)} CTs"
    if parts:
        text += f" ({', '.join(parts)})"
    if pending:
        text += f", {' and '.join(pending)} to be made"
    if unread:
        text += ", " + ", ".join(f"{name} not read ({states[name]})" for name in unread)
    return text


def write_subjects(out, folders):
    """<out>/render-subjects.json: each CT folder's chosen subjects, {folder: [subject ids]}, the
    file the grid's segment job reads."""
    Path(out).mkdir(parents=True, exist_ok=True)
    write_json(Path(out) / RENDER_SUBJECTS, {folder: record["subjects"] for folder, record in folders.items()})


def subject_id(item):
    """A subject as find_subjects lists it: its id, or the first of a pair (id, path)."""
    return str(item[0]) if isinstance(item, (tuple, list)) else str(item)


def render_group(renderer, args, group, ct_root, subjects, salt, roots):
    """One render group's renders, into <out>/renders/<group>, and the record the plan keeps: the
    subjects, the salt, the engine and the blocks, what was rendered or why it failed."""
    out = Path(args.out) / "renders" / group.id
    blocks = blocks_rules().parse(group.blocks)
    record = {"subjects": list(subjects), "salt": salt, "engine": group.engine,
              "blocks": blocks_rules().as_record(blocks)}
    log(f"{group.id}: rendering {len(subjects)} subjects x {blocks.views} views, engine {group.engine},"
        f" segmenter {blocks.segmenter}")
    (out / "FAILED").unlink(missing_ok=True)
    try:
        done = renderer.render_subjects(ct_root, out, len(subjects), salt, args.device, blocks=blocks,
                                        engine=group.engine, subject_ids=tuple(subjects), roots=roots)
        record.update(rendered=done.get("rendered"), kept=list(done.get("subjects", [])),
                      passed_over=done.get("skipped", []))
    except Exception as error:  # the other groups are still worth the job; the reason is kept
        traceback.print_exc(file=sys.stderr)
        out.mkdir(parents=True, exist_ok=True)
        (out / "FAILED").write_text(type(error).__name__ + "\n", encoding="ascii")
        record["failed"] = type(error).__name__
    return record


# --- the images ------------------------------------------------------------------------------------

def grey_pillow(data):
    """A PNG, JPEG, TIFF or BMP as one grey channel of floats; 16-bit frames keep their depth."""
    import numpy as np
    from PIL import Image

    with Image.open(io.BytesIO(data)) as image:
        image.load()
        if image.mode in ("I;16", "I;16L", "I;16B", "I", "F", "L"):
            return np.asarray(image, dtype=np.float64)
        return np.asarray(image.convert("L"), dtype=np.float64)


def grey_dicom(path):
    """A DICOM frame as floats after its modality LUT, MONOCHROME1 turned bone-bright; a cine
    gives its middle frame."""
    import numpy as np
    import pydicom
    from pydicom.pixels import apply_modality_lut

    dataset = pydicom.dcmread(path, force=True)
    photometric = str(dataset.get("PhotometricInterpretation", ""))
    if photometric not in ("MONOCHROME1", "MONOCHROME2"):
        raise ValueError(f"photometric {photometric or 'none'}")
    frames = int(dataset.get("NumberOfFrames", 1) or 1)
    pixels = dataset.pixel_array
    if frames > 1:
        pixels = pixels[frames // 2]
    pixels = np.asarray(apply_modality_lut(pixels, dataset), dtype=np.float64)
    if photometric == "MONOCHROME1":
        pixels = pixels.max() - pixels
    return pixels


def grey_thunder(reference):
    import numpy as np

    root, split, data_id = reference[len(THUNDER):].split("|", 2)
    backend, records = thunder_backend(root, split)
    return np.asarray(backend.load(records[data_id], "image"), dtype=np.float64).squeeze()


def grey_of(reference):
    """Any file of the plan as a two-dimensional array of floats."""
    import numpy as np

    if reference.startswith(THUNDER):
        return grey_thunder(reference)
    suffix = Path(reference).suffix.lower()
    if suffix == ".npy":
        return np.asarray(np.load(reference), dtype=np.float64).squeeze()
    data = Path(reference).read_bytes()
    if suffix in (".dcm", ".dicom") or data[128:132] == b"DICM":
        return grey_dicom(reference)
    return grey_pillow(data)


def canonical(pixels):
    """The image every space reads: windowed to its 0.5-99.5 percentiles, the centre square of 0.9
    of its shorter side, resized to 256 with an area filter, in [0, 1]. Cutting a square rather than
    padding one keeps a pad's flat border, which only non-square images would carry, from telling
    the corpora apart."""
    import numpy as np
    from PIL import Image

    if pixels.ndim != 2 or min(pixels.shape) < 16 or not np.isfinite(pixels).all():
        raise ValueError(f"an image of shape {pixels.shape}")
    low, high = np.percentile(pixels, WINDOW)
    if not high > low:
        raise ValueError("a flat image")
    unit = np.clip((pixels - low) / (high - low), 0.0, 1.0).astype(np.float32)
    side = max(16, int(round(CROP_SHARE * min(unit.shape))))
    top, left = (unit.shape[0] - side) // 2, (unit.shape[1] - side) // 2
    square = unit[top:top + side, left:left + side]
    resized = Image.fromarray(square, mode="F").resize((SIDE, SIDE), Image.Resampling.BOX)
    return np.clip(np.asarray(resized, dtype=np.float32), 0.0, 1.0)


def decode_one(reference):
    """(the 256 x 256 image as float16, None) or (None, the kind of error); never the error's
    text, which can name a file."""
    import numpy as np

    try:
        return canonical(grey_of(reference)).astype(np.float16), None
    except Exception as error:  # every decoder raises its own kinds for a broken file
        return None, type(error).__name__


def stage_images(args, plan):
    """images.npy (n x 256 x 256, float16) and rows.json (group, family, person, file index) for
    every chosen file that decodes; the failures are counted by group and kind."""
    import numpy as np

    out = Path(args.out)
    rows_path, images_path = out / "rows.json", out / "images.npy"
    if rows_path.is_file() and images_path.is_file() and read_json(rows_path).get("plan") == plan_digest(plan):
        return read_json(rows_path), np.load(images_path, mmap_mode="r")
    files = [(g["id"], g["family"], f, p) for g in plan["groups"] for f, p in g["chosen"]]
    log(f"decoding {len(files)} images with {args.workers} workers")
    decoded = decode_all([f for _, _, f, _ in files], args.workers)
    keep = [i for i, (image, _) in enumerate(decoded) if image is not None]
    failures = {}
    for (group, _, _, _), (image, why) in zip(files, decoded):
        if image is None:
            failures.setdefault(group, {}).setdefault(why, 0)
            failures[group][why] += 1
    images = np.stack([decoded[i][0] for i in keep]) if keep else np.zeros((0, SIDE, SIDE), np.float16)
    np.save(images_path, images)
    rows = {"plan": plan_digest(plan), "failures": failures,
            "rows": [{"group": files[i][0], "family": files[i][1], "person": files[i][3]} for i in keep]}
    write_json(rows_path, rows)
    return rows, np.load(images_path, mmap_mode="r")


def decode_all(references, workers):
    """decode_one over every reference, in worker processes that are started fresh rather than
    forked, since the render stage may have opened CUDA in this one, which a fork must not copy."""
    if workers <= 1:
        return [decode_one(r) for r in references]
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=workers, mp_context=context) as pool:
        return list(pool.map(decode_one, references, chunksize=16))


def plan_digest(plan):
    return hashlib.sha256(json.dumps(plan["groups"], sort_keys=True).encode()).hexdigest()


# --- the feature spaces ----------------------------------------------------------------------------

class StopForward(Exception):
    """Raised by the encoder hook once the bottleneck is read, so the decoder never runs."""


def flexray_encoder(weights, device):
    """FleXray's flagship member and a function from a batch to its bottleneck features: the
    spatial mean of the input to the last InstanceNorm2d of the deepest down block. The output of
    an affine instance norm has the norm's learned shift as its spatial mean for every input, so
    pooling the block's output would give one vector for every image; its input does not."""
    import torch
    from fxr.inference import FleXraySegmenter

    segmenter = FleXraySegmenter.from_pretrained(str(weights), subfolder="members/flux0375", device=device)
    model = segmenter.model.eval()
    norms = [m for m in model.down_blocks[-1].modules() if isinstance(m, torch.nn.InstanceNorm2d)]
    if not norms:
        raise StageError("FleXray's deepest down block holds no InstanceNorm2d to read before")
    taken = {}

    def before_norm(_module, inputs):
        taken["features"] = inputs[0].mean(dim=(2, 3))
        raise StopForward

    norms[-1].register_forward_pre_hook(before_norm)

    def embed(batch):
        prepared = segmenter.preprocess(batch).to(segmenter.device)
        with torch.inference_mode():
            try:
                model(prepared)
            except StopForward:
                pass
        return taken.pop("features").float().cpu().numpy()

    return embed


def imagenet_encoder(weights, device):
    """torchvision's ResNet-18 from the held ImageNet file, its 512 pooled features."""
    import torch
    import torch.nn.functional as F
    import torchvision

    model = torchvision.models.resnet18(weights=None)
    model.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True))
    model.fc = torch.nn.Identity()
    model = model.eval().to(device)
    mean = torch.tensor([0.485, 0.456, 0.406], device=device).view(1, 3, 1, 1)
    std = torch.tensor([0.229, 0.224, 0.225], device=device).view(1, 3, 1, 1)

    def embed(batch):
        with torch.inference_mode():
            x = F.interpolate(batch.to(device), size=(224, 224), mode="bilinear", antialias=True,
                              align_corners=False).repeat(1, 3, 1, 1)
            return model((x - mean) / std).float().cpu().numpy()

    return embed


def physics_features(image):
    """Handcrafted measures of one 256 x 256 image in [0, 1], the ones a renderer gets wrong
    first: the intensity histogram (32 bins, square-rooted), the radial power spectrum's shape
    (log-spaced bands with whole-pixel edges, log10, centred) and its total, the gradient histogram (16 bins), the
    noise (a robust spread of the Laplacian at two scales and their ratio), local contrast (7 x 7
    standard deviation: mean, median, 90th percentile), the shares near black and near white,
    and the share of strong edges."""
    import numpy as np

    x = image.astype(np.float64)
    hist = np.sqrt(np.histogram(x, bins=32, range=(0.0, 1.0))[0] / x.size)
    window = np.outer(np.hanning(SIDE), np.hanning(SIDE))
    power = np.abs(np.fft.fftshift(np.fft.fft2((x - x.mean()) * window))) ** 2
    yy, xx = np.indices(power.shape) - SIDE // 2
    radius = np.hypot(yy, xx)
    edges = np.unique(np.round(np.geomspace(1.0, SIDE // 2, 33)))  # integer edges: no band is empty
    bands = np.array([power[(radius >= a) & (radius < b)].mean() for a, b in zip(edges[:-1], edges[1:])])
    spectrum = np.log10(bands + 1e-12)
    gy, gx = np.gradient(x)
    magnitude = np.hypot(gx, gy)
    ghist = np.histogram(np.clip(magnitude, 0, 0.5), bins=16, range=(0.0, 0.5))[0] / x.size
    noise = [laplacian_sigma(x), laplacian_sigma(x[::2, ::2])]
    local = local_std(x)
    extra = [spectrum.mean(), noise[0], noise[1], noise[0] / (noise[1] + 1e-9),
             local.mean(), np.median(local), np.percentile(local, 90),
             (x < 0.01).mean(), (x > 0.99).mean(), (magnitude > 0.1).mean()]
    return np.concatenate([hist, spectrum - spectrum.mean(), ghist, np.array(extra)]).astype(np.float32)


def laplacian_sigma(x):
    """The noise's spread: 1.4826 times the median absolute Laplacian, a robust sigma."""
    import numpy as np

    lap = 4 * x[1:-1, 1:-1] - x[:-2, 1:-1] - x[2:, 1:-1] - x[1:-1, :-2] - x[1:-1, 2:]
    return float(1.4826 * np.median(np.abs(lap - np.median(lap))))


def local_std(x, size=7):
    """The standard deviation of every size x size neighbourhood, by integral images."""
    import numpy as np

    def box(a):
        c = np.cumsum(np.cumsum(np.pad(a, ((1, 0), (1, 0))), 0), 1)
        return (c[size:, size:] - c[:-size, size:] - c[size:, :-size] + c[:-size, :-size]) / size ** 2

    mean, square = box(x), box(x * x)
    return np.sqrt(np.clip(square - mean ** 2, 0, None))


def physics_encoder(_weights, _device):
    import numpy as np

    def embed(batch):
        return np.stack([physics_features(b[0].cpu().numpy()) for b in batch])

    return embed


ENCODERS = {"flexray": flexray_encoder, "imagenet": imagenet_encoder, "physics": physics_encoder}


def space_weights(space, args):
    return {"flexray": args.weights, "imagenet": args.imagenet, "physics": None}[space]


def unavailable(space, args):
    """Why a space cannot run here, or None."""
    weights = space_weights(space, args)
    if space == "flexray" and not (weights and (Path(weights) / "ensemble.json").is_file()):
        return "no FleXray bundle (ensemble.json)"
    if space == "imagenet" and not (weights and Path(weights).is_file()):
        return "no ImageNet ResNet-18 file"
    return None


def stage_features(args, images, rows):
    """features/<space>.npz: for each image, the space's features of the image and of its inverse."""
    import numpy as np
    import torch

    folder = Path(args.out) / "features"
    folder.mkdir(exist_ok=True)
    done = {}
    for space in SPACES:
        path = folder / f"{space}.npz"
        why = unavailable(space, args)
        if why:
            done[space] = why
            continue
        if path.is_file() and str(np.load(path)["plan"]) == rows["plan"]:
            done[space] = None
            continue
        log(f"features: {space} over {len(images)} images")
        embed = ENCODERS[space](space_weights(space, args), args.device)
        stored, inverse = [], []
        for start in range(0, len(images), 64):
            batch = torch.from_numpy(np.asarray(images[start:start + 64], dtype=np.float32)).unsqueeze(1)
            stored.append(embed(batch))
            inverse.append(embed(1.0 - batch))
        np.savez(path, stored=np.concatenate(stored), inverse=np.concatenate(inverse), plan=rows["plan"])
        done[space] = None
    return done


# --- the analysis ----------------------------------------------------------------------------------

def stats():
    return tool("domain_gap_stats")


class Frame:
    """One space's features with their rows: the groups, families and persons the tests read."""

    def __init__(self, x, rows, plan):
        import numpy as np

        self.x = x
        self.group = np.array([r["group"] for r in rows])
        self.family = np.array([r["family"] for r in rows])
        self.person = np.array([r["person"] for r in rows])
        self.labels = {g["id"]: g["label"] for g in plan["groups"]}
        self.skipped = {g["id"]: g.get("skipped", "") for g in plan["groups"]}
        self.order = [g["id"] for g in plan["groups"] if (self.group == g["id"]).sum() >= MIN_ROWS]

    def rows_of(self, group):
        import numpy as np

        return np.flatnonzero(self.group == group)

    def persons(self, group):
        return len(set(self.person[self.rows_of(group)]))

    def testable(self, family=None):
        return [g for g in self.order if self.persons(g) >= MIN_PERSONS
                and (family is None or self.family[self.rows_of(g)[0]] == family)]

    def family_of(self, group):
        return str(self.family[self.rows_of(group)[0]])

    def twins(self, a, b):
        """Whether rows a and rows b are of the same persons, which two render groups on one CT
        folder are (a render's person is its CT, whichever group rendered it, plan_group) and no
        two corpora are: a paired sample, every person on both sides."""
        return len(a) > 0 and len(b) > 0 and set(self.person[a]) == set(self.person[b])

    def why_untestable(self, group):
        """Why a group is not in the tests, in words, or "" when it is: not in the table, skipped
        by the plan for its reason, too few images decoded, or too few persons."""
        if group not in self.labels:
            return "not in the table"
        if group in self.testable():
            return ""
        if self.skipped.get(group):
            return self.skipped[group]
        rows = len(self.rows_of(group))
        if rows < MIN_ROWS:
            return f"{rows} images decoded, fewer than {MIN_ROWS}"
        return f"{self.persons(group)} persons, fewer than {MIN_PERSONS}"


def capped(frame, rows, limit, salt):
    """At most limit of these rows, chosen by person in the salted order (persons whole)."""
    import numpy as np

    pairs = tuple((str(i), str(frame.person[i])) for i in rows)
    per_person = max(1, int(np.ceil(limit / max(1, len(set(p for _, p in pairs))))))
    chosen = rules().choose(pairs, limit, max(per_person, 1), salt)
    return np.array(sorted(int(i) for i, _ in chosen), dtype=int)


def pooled(frame, family, salt):
    """A family's testable real groups, POOL_ROWS of each, so no one corpus outweighs the rest."""
    import numpy as np

    parts = [capped(frame, frame.rows_of(g), POOL_ROWS, f"{salt}:{g}") for g in frame.testable(family)]
    return np.concatenate(parts) if parts else np.zeros(0, dtype=int)


def contrast(frame, z64, a, b, seed, *, permute=False, prdc=False):
    """Every separation measure of rows a against rows b: the classifier two-sample tests
    (logistic and k nearest neighbours, person-grouped, with cluster bootstrap intervals and,
    when asked, a permutation p), MMD with its person-level permutation p, FD and KID in the
    first 64 components, and, when asked, precision, recall, density and coverage of a against b.
    Two sides of the same persons (Frame.twins), two render groups on one CT folder, whose views
    are near-identical twins of one CT, are a paired sample: a CT's rows fall in one fold on both
    sides, since its person is one key, and the interval, the permutations and the MMD's null
    move its two sides together (domain_gap_stats, paired). Twins analysed as independent persons
    teach the classifier each CT from the other side and hold every statistic below its own null,
    so a shift the test should see reads as none (the review of 2026-10-26, F22)."""
    import numpy as np

    s = stats()
    rows = np.concatenate([a, b])
    labels = np.concatenate([np.ones(len(a), int), np.zeros(len(b), int)])
    persons, paired = list(frame.person[rows]), frame.twins(a, b)
    result = {"n": [len(a), len(b)], "persons": [len(set(frame.person[a])), len(set(frame.person[b]))],
              "paired": paired}
    for model in ("logistic", "knn"):
        scores = s.c2st(frame.x[rows], labels, persons, seed=seed, model=model)
        result[f"auc_{model}"] = s.auc_with_interval(scores, labels, persons, boot=BOOTSTRAP, seed=seed,
                                                     paired=paired)
    if permute:
        result["auc_logistic"]["p"] = s.c2st_permutation_p(
            frame.x[rows], labels, persons, observed_auc=result["auc_logistic"]["auc"],
            perms=PERMUTATIONS_C2ST, seed=seed, paired=paired)
    result["mmd"] = s.mmd_test(z64[a], z64[b], persons[:len(a)], persons[len(a):],
                               perms=PERMUTATIONS_MMD, seed=seed, paired=paired)
    result.update(distances(frame, z64, (a, b), seed))
    if prdc:
        result["prdc"] = s.prdc(z64[b], z64[a])
    return result


def distances(frame, z64, sides, seed):
    """fd64, the Frechet distance of the two sides at equal sizes (equal_rows) with the rows a
    side it was taken at, and kid64, the first side against the second."""
    s = stats()
    a, b = sides
    fa, fb = equal_rows(frame, a, b, seed)
    return {"fd64": s.frechet_distance(z64[fa], z64[fb]), "fd_rows": len(fa),
            "kid64": s.kid(z64[a], z64[b], seed=seed)}


def equal_rows(frame, a, b, seed):
    """Equal shares of a and b, at most FD_ROWS each, chosen by person: the Frechet distance grows
    as the sample shrinks, so every FD64 the gap ratio sets beside another is taken at one size."""
    size = min(len(a), len(b), FD_ROWS)
    return capped(frame, a, size, f"fd:{seed}"), capped(frame, b, size, f"fd:{seed}")


def calibration(frame, z64, salt, seed):
    """The split-half nulls: each group with enough persons split in two by person; the tests
    must find nothing there, or the pipeline is leaking."""
    import numpy as np

    s = stats()
    nulls = {}
    for group in frame.order:
        if frame.persons(group) < SPLIT_PERSONS:
            continue
        rows = frame.rows_of(group)
        half = s.split_half(list(frame.person[rows]), f"{salt}:{group}")
        a, b = rows[half == 1], rows[half == 0]
        nulls[group] = contrast(frame, z64, a, b, seed)
    aucs = [v["auc_logistic"]["auc"] for v in nulls.values()]
    return {"groups": nulls, "auc_median": float(np.median(aucs)) if aucs else None,
            "auc_range": [float(min(aucs)), float(max(aucs))] if aucs else None,
            "flagged": flagged_nulls(nulls), "auc_above": [g for g, v in nulls.items() if v["auc_logistic"]["lo"] > 0.5]}


def flagged_nulls(nulls):
    """The split-half nulls whose MMD permutation test, Benjamini-Hochberg adjusted over the space's
    nulls, falls under 0.05. The permutation test is exact under a person-level null; the C2ST's
    bootstrap interval holds the trained classifiers fixed and is too narrow for a few dozen
    persons, so an interval above 0.5 is counted (auc_above) but flags nothing by itself."""
    if not nulls:
        return []
    groups = list(nulls)
    q = rules().benjamini_hochberg(tuple(float(nulls[g]["mmd"]["p"]) for g in groups))
    return [g for g, value in zip(groups, q) if value < 0.05]


def analyse_space(frame, salt, seed):
    """The whole analysis of one feature space."""
    import numpy as np

    s = stats()
    z = s.standardise(frame.x)
    z64, explained = s.pca(z, min(64, z.shape[1], len(z) - 1), seed=seed)
    result = {"dim": int(frame.x.shape[1]), "rows": int(len(frame.x)),
              "feature_spread": float(np.mean(np.std(frame.x, axis=0))),
              "pca64_explained": float(np.sum(explained))}
    if result["feature_spread"] < 1e-6:
        result["invalid"] = "every image has the same features"
        return result, None
    synthetic = [g for g in frame.testable("synthetic")]
    real = frame.testable("fluoroscopy") + frame.testable("film")
    families = {f: pooled(frame, f, salt) for f in ("fluoroscopy", "film")}
    result["vs_family"] = family_contrasts(frame, z64, synthetic, families, seed)
    result["vs_group"] = {sg: {rg: contrast(frame, z64, frame.rows_of(sg), frame.rows_of(rg), seed)
                               for rg in real} for sg in synthetic}
    result["real_real"] = {f"{a}|{b}": contrast(frame, z64, frame.rows_of(a), frame.rows_of(b), seed)
                           for i, a in enumerate(real) for b in real[i + 1:]}
    if len(families["fluoroscopy"]) and len(families["film"]):
        result["fluoroscopy_vs_film"] = contrast(frame, z64, families["fluoroscopy"], families["film"], seed)
    result["replication"] = replication_contrasts(frame, z64, seed)
    result["calibration"] = calibration(frame, z64, salt, seed)
    result["ratios"] = gap_ratios(frame, result, synthetic)
    result["structure"] = structure(frame, z64, real, synthetic, seed)
    result["fd_all"] = all_distances(frame, z64, seed)
    adjust(result)
    replication_words(result)
    maps = map_coordinates(frame, z, salt, seed)
    result["maps"] = {k: v for k, v in maps.items() if k != "coords"}
    return result, maps


def family_contrasts(frame, z64, synthetic, families, seed):
    return {sg: {f: contrast(frame, z64, frame.rows_of(sg), rows, seed, permute=True, prdc=True)
                 for f, rows in families.items() if len(rows)} for sg in synthetic}


def replication_contrasts(frame, z64, seed):
    """The replication test's pairs (REPLICATION_PAIRS), each with every measure a family contrast
    gets, the C2ST permutation p and PRDC among them, precision and recall being the first group's
    against the second; a pair with a group the space cannot test is listed with the reason, so a
    FluXray not fetched or a render that failed is read in the result and not guessed at."""
    out = {}
    for a, b in REPLICATION_PAIRS:
        missing = [f"{g}: {frame.why_untestable(g)}" for g in (a, b) if frame.why_untestable(g)]
        if missing:
            out[f"{a}|{b}"] = {"skipped": "; ".join(missing)}
            continue
        out[f"{a}|{b}"] = contrast(frame, z64, frame.rows_of(a), frame.rows_of(b), seed, permute=True, prdc=True)
    return out


def replication_words(result):
    """The pre-registered word beside each worded pair (REPLICATION_WORDED, one recipe through two
    engines), from its logistic AUC's lower bound and its MMD's q, once adjust has set the q over
    the space's MMD p-values; the study's verdict is the first pair's word in the primary space's
    inversion-invariant reading (replication_verdict)."""
    for pair in REPLICATION_WORDED:
        found = result.get("replication", {}).get("|".join(pair))
        if found and "skipped" not in found:
            found["word"] = rules().replication_word(float(found["auc_logistic"]["lo"]), float(found["mmd"]["q"]))


def family_pairs(frame, result, family):
    pairs = []
    for key, value in result["real_real"].items():
        a, b = key.split("|")
        if frame.family_of(a) == family and frame.family_of(b) == family:
            pairs.append(value)
    return pairs


def gap_ratios(frame, result, synthetic):
    """FD64 of a synthetic group against a family over the median FD64 of the family's own real
    pairs, and the pre-registered word from the AUC's lower bound against the family's median
    real-real AUC."""
    pure = rules()
    ratios = {}
    for family in ("fluoroscopy", "film"):
        pairs = family_pairs(frame, result, family)
        if not pairs:
            continue
        fds = tuple(float(p["fd64"]) for p in pairs)
        aucs = sorted(float(p["auc_logistic"]["auc"]) for p in pairs)
        median_auc = aucs[len(aucs) // 2] if len(aucs) % 2 else (aucs[len(aucs) // 2 - 1] + aucs[len(aucs) // 2]) / 2
        for sg in synthetic:
            cross = result["vs_family"].get(sg, {}).get(family)
            if not cross or not any(fds):
                continue
            ratios.setdefault(sg, {})[family] = {
                "fd_ratio": pure.gap_ratio(float(cross["fd64"]), fds),
                "real_real_auc_median": median_auc,
                "word": pure.gap_word(float(cross["auc_logistic"]["lo"]), median_auc)}
    return ratios


def structure(frame, z64, real, synthetic, seed):
    """Silhouette, neighbour purity, the share of each group's neighbours in each family, and which
    real corpus a classifier trained on the real corpora alone calls each synthetic group."""
    import numpy as np

    s = stats()
    keep = np.isin(frame.group, frame.order)
    out = {"silhouette": s.silhouette(z64[keep], frame.group[keep], seed=seed),
           "purity": s.knn_purity(z64[keep], frame.group[keep]),
           "family_share": s.neighbour_family_share(z64[keep], frame.group[keep], frame.family[keep])}
    real_rows = np.flatnonzero(np.isin(frame.group, real))
    if len(set(frame.group[real_rows])) >= 2:
        out["nearest_real"] = {sg: s.nearest_real(frame.x[real_rows], frame.group[real_rows],
                                                  list(frame.person[real_rows]), frame.x[frame.rows_of(sg)],
                                                  seed=seed) for sg in synthetic}
    return out


def adjust(result):
    """Benjamini-Hochberg over every MMD p of the space's contrasts, the replication pairs among
    them, and over its C2ST permutation p-values; the split-half nulls are adjusted among
    themselves (flagged_nulls)."""
    pure = rules()
    for key in ("mmd", "c2st"):
        found = list(p_values(result, key))
        if not found:
            continue
        adjusted = pure.benjamini_hochberg(tuple(p for _, p in found))
        for (holder, _), q in zip(found, adjusted):
            holder["q"] = q


def p_values(result, key):
    """(the dict holding a p, the p) for every test of one kind in the space's result."""
    blocks = [result.get("vs_group", {}), result.get("vs_family", {})]
    contrasts = [c for block in blocks for inner in block.values() for c in inner.values()]
    contrasts += list(result.get("real_real", {}).values())
    contrasts += [c for c in result.get("replication", {}).values() if "skipped" not in c]
    if "fluoroscopy_vs_film" in result:
        contrasts.append(result["fluoroscopy_vs_film"])
    for c in contrasts:
        holder = c["mmd"] if key == "mmd" else c["auc_logistic"]
        if "p" in holder:
            yield holder, float(holder["p"])


def map_coordinates(frame, z, salt, seed):
    """PCA, t-SNE, UMAP and LDA maps of up to MAP_ROWS rows a group, with each map's
    trustworthiness against the first 50 components and each group's centre and spread."""
    import numpy as np

    s = stats()
    rows = np.concatenate([capped(frame, frame.rows_of(g), MAP_ROWS, f"{salt}:map:{g}") for g in frame.order])
    z50, _ = s.pca(z[rows], min(50, z.shape[1], len(rows) - 1), seed=seed)
    maps = s.reductions(z50, seed=seed, groups=frame.group[rows])
    out = {"coords": {"rows": rows, **maps}, "trust": {}, "centres": {}}
    for name, xy in maps.items():
        if not hasattr(xy, "shape"):
            out["trust"][name] = None
            continue
        out["trust"][name] = float(s.trust(z50, xy, seed=seed)) if name != "lda" else None
        out["centres"][name] = {g: centre(xy[frame.group[rows] == g]) for g in frame.order}
    return out


def centre(xy):
    import numpy as np

    return [round(float(v), 2) for v in (*np.mean(xy, axis=0), *np.std(xy, axis=0))]


def stage_analysis(args, plan, rows):
    """results.json and the figures, every available space in turn."""
    import numpy as np

    results = {"plan": rows["plan"], "spaces": {}, "groups": group_rows(plan, rows),
               "renders": plan.get("renders", {})}
    all_maps = {}
    for space in SPACES:
        path = Path(args.out) / "features" / f"{space}.npz"
        if not path.is_file():
            results["spaces"][space] = {"invalid": unavailable(space, args) or "no features"}
            continue
        data = np.load(path)
        stored, inverse = data["stored"], data["inverse"]
        for reading, x in (("invariant", (stored + inverse) / 2.0), ("as_stored", stored)):
            if reading == "as_stored" and space != PRIMARY_SPACE:
                continue
            log(f"analysis: {space} ({reading})")
            frame = Frame(x, rows["rows"], plan)
            result, maps = analyse_space(frame, plan["salt"], seed=0)
            key = space if reading == "invariant" else f"{space}_as_stored"
            results["spaces"][key] = result
            if maps:
                all_maps[key] = (frame, maps)
    results["replication"] = replication_verdict(results)
    write_json(Path(args.out) / "results.json", results)
    tool_figures = Path(args.out) / "figures"
    tool_figures.mkdir(exist_ok=True)
    figures(all_maps, results, tool_figures)
    return results, all_maps


def replication_verdict(results):
    """The words the study reports for the replication test, each worded pair's in the primary
    space's inversion-invariant reading or why there is none, under "pairs"; the first pair's,
    FleXray's MOOSE recipe through this project's blocks against FleXray's own code, is the
    study's verdict and stands at the top."""
    pairs = {"|".join(pair): pair_verdict(results, "|".join(pair)) for pair in REPLICATION_WORDED}
    first = "|".join(REPLICATION_PAIRS[0])
    return {"space": PRIMARY_SPACE, "reading": "invariant", "pair": first, **pairs[first], "pairs": pairs}


def pair_verdict(results, pair):
    """One pair's word in the primary space's inversion-invariant reading, with the persons and
    rows a side it was read from, or why there is none."""
    verdict = {"word": None, "reason": ""}
    space = results["spaces"].get(PRIMARY_SPACE, {})
    found = space.get("replication", {}).get(pair, {})
    if space.get("invalid"):
        verdict["reason"] = f"space {PRIMARY_SPACE} not run, {space['invalid']}"
    elif "word" in found:
        verdict.update(word=found["word"], persons=found["persons"], n=found["n"])
    else:
        verdict["reason"] = found.get("skipped", "the pair was not tested")
    return verdict


def group_rows(plan, rows):
    """Each group's counts: found, chosen, decoded, persons, and why anything was left out."""
    decoded = {}
    for r in rows["rows"]:
        decoded.setdefault(r["group"], set()).add(r["person"])
    counts = {}
    for r in rows["rows"]:
        counts[r["group"]] = counts.get(r["group"], 0) + 1
    return [{"id": g["id"], "label": g["label"], "family": g["family"], "source": g.get("source", ""),
             "found": g.get("found", 0), "chosen": len(g["chosen"]), "decoded": counts.get(g["id"], 0),
             "persons": len(decoded.get(g["id"], ())), "person_rule": g.get("person_rule", ""),
             "person_fallback": g.get("person_fallback", 0), "frozen_dropped": g.get("frozen_dropped", 0),
             "failures": rows["failures"].get(g["id"], {}), "skipped": g["skipped"]} for g in plan["groups"]]


# --- the figures -----------------------------------------------------------------------------------

# The reference palette's first three categorical slots, the only ones that stay apart for every
# pair in a scatter (the dataviz skill's palette): a family is a colour and a marker; a group is a
# panel of its own in the small multiples, never a ninth colour.
FAMILY_STYLE = {"synthetic": ("#eb6834", "^"), "fluoroscopy": ("#2a78d6", "s"), "film": ("#1baf7a", "o")}
GREY = "#c9c8c2"
INK, MUTED = "#0b0b0b", "#52514e"


def figures(all_maps, results, folder):
    """Every figure as a PNG: per space, the family maps, the group small multiples, the AUC
    heatmap and the FD64 distance matrix; across spaces, the calibration."""
    import matplotlib

    matplotlib.use("Agg")
    for key, (frame, maps) in all_maps.items():
        family_maps(frame, maps, folder / f"maps-{key}.png", key)
        group_panels(frame, maps, folder / f"groups-{key}.png", key)
        auc_heatmap(frame, results["spaces"][key], folder / f"auc-{key}.png", key)
        distance_matrix(frame, results["spaces"][key], folder / f"fd64-{key}.png", key)
    calibration_figure(results, folder / "calibration.png")


def styled_axes(ax, title):
    ax.set_title(title, color=INK, fontsize=10, loc="left")
    ax.set_xticks([])
    ax.set_yticks([])
    for side in ax.spines.values():
        side.set_color(GREY)


def family_maps(frame, maps, path, key):
    import matplotlib.pyplot as plt

    coords = maps["coords"]
    rows = coords["rows"]
    names = [n for n in ("pca", "tsne", "umap", "lda") if hasattr(coords.get(n), "shape")]
    fig, axes = plt.subplots(1, len(names), figsize=(4.2 * len(names), 4.4), squeeze=False)
    for ax, name in zip(axes[0], names):
        xy = coords[name]
        for family, (colour, marker) in FAMILY_STYLE.items():
            mask = frame.family[rows] == family
            ax.scatter(xy[mask, 0], xy[mask, 1], s=9, c=colour, marker=marker, linewidths=0, alpha=0.6,
                       label=family)
        trust = maps["trust"].get(name)
        styled_axes(ax, f"{name.upper()}" + (f"  trust {trust:.2f}" if trust else "  (supervised)" if name == "lda" else ""))
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", ncol=3, fontsize=9, frameon=False, markerscale=1.8)
    fig.suptitle(f"Synthetic DRRs and real X-ray corpora, {key} features", color=INK, fontsize=11, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def group_panels(frame, maps, path, key, method="tsne"):
    import matplotlib.pyplot as plt

    coords = maps["coords"]
    method = method if hasattr(coords.get(method), "shape") else "pca"
    xy, rows = coords[method], coords["rows"]
    columns = 4
    lines = max(1, math.ceil(len(frame.order) / columns))
    fig, axes = plt.subplots(lines, columns, figsize=(3.2 * columns, 3.0 * lines), squeeze=False)
    for ax in axes.flat:
        ax.axis("off")
    for ax, group in zip(axes.flat, frame.order):
        ax.axis("on")
        mask = frame.group[rows] == group
        colour, marker = FAMILY_STYLE[frame.family_of(group)]
        ax.scatter(xy[~mask, 0], xy[~mask, 1], s=4, c=GREY, linewidths=0, alpha=0.5)
        ax.scatter(xy[mask, 0], xy[mask, 1], s=8, c=colour, marker=marker, linewidths=0, alpha=0.8)
        styled_axes(ax, f"{frame.labels[group]}  ({frame.family_of(group)})")
    fig.suptitle(f"Each corpus against all the others, {method.upper()} of {key} features", color=INK,
                 fontsize=11, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def auc_heatmap(frame, result, path, key):
    """Rows: the synthetic groups; columns: each real group, then the pooled families. A cell is
    the person-grouped logistic two-sample AUC, 0.5 where a classifier cannot tell them apart."""
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.colors import LinearSegmentedColormap

    synthetic = list(result.get("vs_group", {}))
    if not synthetic:
        return
    real = list(result["vs_group"][synthetic[0]])
    columns = real + ["fluoroscopy", "film"]
    grid = np.full((len(synthetic), len(columns)), np.nan)
    for i, sg in enumerate(synthetic):
        for j, column in enumerate(columns):
            cell = result["vs_group"][sg].get(column) or result.get("vs_family", {}).get(sg, {}).get(column)
            if cell:
                grid[i, j] = cell["auc_logistic"]["auc"]
    ramp = LinearSegmentedColormap.from_list("blue", ["#cde2fb", "#6da7ec", "#2a78d6", "#184f95", "#0d366b"])
    fig, ax = plt.subplots(figsize=(1.0 + 0.75 * len(columns), 1.2 + 0.5 * len(synthetic)))
    ax.imshow(grid, cmap=ramp, vmin=0.5, vmax=1.0, aspect="auto")
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            if not np.isnan(grid[i, j]):
                ax.text(j, i, f"{grid[i, j]:.2f}", ha="center", va="center", fontsize=8,
                        color="#ffffff" if grid[i, j] > 0.8 else INK)
    ax.set_xticks(range(len(columns)), [frame.labels.get(c, f"pooled {c}") for c in columns], rotation=45,
                  ha="right", fontsize=8, color=MUTED)
    ax.set_yticks(range(len(synthetic)), [frame.labels[s] for s in synthetic], fontsize=8, color=MUTED)
    ax.set_title(f"Two-sample AUC, synthetic against real, {key} (0.5 = indistinguishable)", fontsize=10,
                 color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def distance_matrix(frame, result, path, key):
    """FD64 between every pair of groups the space tested, ordered by average-linkage clustering."""
    import matplotlib.pyplot as plt
    import numpy as np

    groups, fd = fd_table(result)
    if len(groups) < 3:
        return
    from scipy.cluster.hierarchy import leaves_list, linkage
    from scipy.spatial.distance import squareform

    order = leaves_list(linkage(squareform(fd, checks=False), method="average"))
    fd = fd[np.ix_(order, order)]
    names = [frame.labels.get(groups[i], groups[i]) for i in order]
    side = max(5.0, 2.5 + 0.45 * len(names))
    fig, ax = plt.subplots(figsize=(side + 1.0, side))
    shown = ax.imshow(np.log10(fd + 1.0), cmap="Blues", aspect="auto")
    bar = fig.colorbar(shown, ax=ax, fraction=0.04, pad=0.02)
    bar.set_label("log10(1 + FD64), darker = farther", fontsize=8, color=MUTED)
    ax.set_xticks(range(len(names)), names, rotation=60, ha="right", fontsize=7, color=MUTED)
    ax.set_yticks(range(len(names)), names, fontsize=7, color=MUTED)
    ax.set_title(f"FD64 between corpora, {key}", fontsize=10, color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def all_distances(frame, z64, seed):
    """FD64 between every two groups the maps show, synthetic and real alike, each pair at equal
    sizes, for the distance matrix and its clustering."""
    s = stats()
    out = {}
    for i, a in enumerate(frame.order):
        for b in frame.order[i + 1:]:
            fa, fb = equal_rows(frame, frame.rows_of(a), frame.rows_of(b), seed)
            out[f"{a}|{b}"] = float(s.frechet_distance(z64[fa], z64[fb]))
    return out


def fd_table(result):
    """The groups and the symmetric FD64 matrix of every pair of the space."""
    import numpy as np

    pairs = {tuple(key.split("|")): value for key, value in result.get("fd_all", {}).items()}
    groups = sorted({g for pair in pairs for g in pair})
    index = {g: i for i, g in enumerate(groups)}
    fd = np.zeros((len(groups), len(groups)))
    for (a, b), value in pairs.items():
        fd[index[a], index[b]] = fd[index[b], index[a]] = max(0.0, float(value))
    return groups, fd


def calibration_figure(results, path):
    """Each split-half null's AUC with its interval, by space: every interval should hold 0.5."""
    import matplotlib.pyplot as plt

    spaces = [k for k, v in results["spaces"].items() if v.get("calibration", {}).get("groups")]
    if not spaces:
        return
    fig, axes = plt.subplots(1, len(spaces), figsize=(4.0 * len(spaces), 3.6), squeeze=False)
    for ax, key in zip(axes[0], spaces):
        nulls = results["spaces"][key]["calibration"]["groups"]
        for i, (group, value) in enumerate(sorted(nulls.items())):
            auc = value["auc_logistic"]
            ax.plot([auc["lo"], auc["hi"]], [i, i], color="#2a78d6", linewidth=2)
            ax.plot([auc["auc"]], [i], marker="o", color="#2a78d6", markersize=5)
        ax.axvline(0.5, color=MUTED, linewidth=1, linestyle=":")
        ax.set_yticks(range(len(nulls)), sorted(nulls), fontsize=7, color=MUTED)
        ax.set_xlim(0.3, 0.8)
        ax.set_title(f"Split-half nulls, {key}", fontsize=10, color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# --- W&B -------------------------------------------------------------------------------------------

def wandb_key_found():
    """Whether W&B can find a key here, by name only: the environment, ~/.netrc's api.wandb.ai
    entry or the grid's ~/.wandb/token.env. The key itself is never read into this process's output."""
    if os.environ.get("WANDB_API_KEY"):
        return True
    netrc = Path.home() / ".netrc"
    if netrc.is_file() and "api.wandb.ai" in netrc.read_text(encoding="utf-8", errors="replace"):
        return True
    token = Path.home() / ".wandb" / "token.env"
    if token.is_file():
        for line in token.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("WANDB_API_KEY="):
                os.environ["WANDB_API_KEY"] = line.split("=", 1)[1].strip()
                return True
    return False


def wandb_push(args, results, all_maps):
    """The figures and the map coordinates to W&B, online where the node reaches it, else offline
    under --out/wandb; the answer is a short line for the summary, never the key."""
    if args.wandb == "off":
        return "off"
    if not wandb_key_found():
        return "no key found; figures only on the grid"
    try:
        import wandb

        os.environ.setdefault("WANDB_PROJECT", "SchwingNet")
        run = start_wandb(wandb, args)
        for png in sorted((Path(args.out) / "figures").glob("*.png")):
            run.log({f"figures/{png.stem}": wandb.Image(str(png))})
        for key, (frame, maps) in all_maps.items():
            run.log({f"maps/{key}": wandb.Table(columns=map_columns(maps), data=map_table(frame, maps))})
        run.summary.update(flat_summary(results))
        url = getattr(run, "url", None) or "offline"
        run.finish()
        return f"{'online' if url != 'offline' else 'offline under the run folder'} {url}"
    except Exception as error:  # W&B raises many kinds; a failed push never fails the study
        return f"not pushed ({type(error).__name__})"


def start_wandb(wandb, args):
    name = f"drr-gap-{os.environ.get('SLURM_JOB_ID', 'local')}"
    common = dict(project=os.environ["WANDB_PROJECT"], group="drr-gap", name=name, dir=str(args.out),
                  job_type="drr-gap")
    try:
        return wandb.init(mode="online", settings=wandb.Settings(init_timeout=60), **common)
    except Exception:  # the node has no route out: log offline beside the run
        return wandb.init(mode="offline", **common)


def map_columns(maps):
    names = [n for n in ("pca", "tsne", "umap", "lda") if hasattr(maps["coords"].get(n), "shape")]
    return ["group", "family"] + [f"{n}_{axis}" for n in names for axis in ("x", "y")]


def map_table(frame, maps):
    coords = maps["coords"]
    names = [n for n in ("pca", "tsne", "umap", "lda") if hasattr(coords.get(n), "shape")]
    table = []
    for k, i in enumerate(coords["rows"]):
        line = [frame.labels[frame.group[i]], str(frame.family[i])]
        for n in names:
            line += [float(coords[n][k, 0]), float(coords[n][k, 1])]
        table.append(line)
    return table


def flat_summary(results):
    flat = {}
    for key, space in results["spaces"].items():
        for sg, inner in space.get("vs_family", {}).items():
            for family, c in inner.items():
                flat[f"{key}/{sg}/{family}/auc"] = c["auc_logistic"]["auc"]
                flat[f"{key}/{sg}/{family}/fd64"] = c["fd64"]
    return flat


# --- the summary: what the bench report carries off the grid --------------------------------------

def fmt(value, digits=2):
    return "na" if value is None or (isinstance(value, float) and math.isnan(value)) else f"{value:.{digits}f}"


def auc_text(auc):
    text = f"{fmt(auc['auc'])} [{fmt(auc['lo'])}, {fmt(auc['hi'])}]"
    if "p" in auc:
        text += f" p {fmt(auc['p'], 3)}"
    return text


def summary_lines(results, wandb_line):
    """At most LINE_BUDGET short lines, each made safe for the grid's redaction, of what the study
    found: the header and the replication verdict, the groups, then the primary space in full,
    the other spaces' family contrasts, FleXray's space as stored for FleXray's own groups, and
    last the secondary lines (the nearest real corpora, the other spaces' replication pairs and
    replication-only contrasts, the map centres). The sections carry a rank, and whole sections
    are given up from the highest rank down until the lines fit, so what is cut is the least read
    and never the middle of a table."""
    header = (f"drr gap: {sum(g['decoded'] for g in results['groups'])} images,"
              f" {sum(1 for g in results['groups'] if g['decoded'] >= MIN_ROWS)} groups, W&B {wandb_line}")
    sections = [(0, [header] + verdict_lines(results.get("replication", {}))),
                (1, render_summary(results.get("renders", {})) + group_summary(results["groups"]))]
    for key, space in results["spaces"].items():
        sections += space_sections(key, space, detail_of(key))
    lines = fit_lines(sections, LINE_BUDGET)
    return [rules().safe_line(line) for line in lines][:LINE_BUDGET]


def fit_lines(sections, budget):
    """The sections' lines in their order, whole sections dropped from the highest rank down,
    the later of two at one rank first, until at most budget lines remain."""
    kept = list(range(len(sections)))
    order = sorted(kept, key=lambda i: (sections[i][0], i), reverse=True)
    for i in order:
        if sum(len(sections[j][1]) for j in kept) <= budget:
            break
        kept.remove(i)
    return [line for i in sorted(kept) for line in sections[i][1]]


def verdict_lines(verdict):
    """One line per worded pair, the study's verdict first."""
    if not verdict:
        return ["replication: no verdict"]
    pairs = verdict.get("pairs") or {verdict["pair"]: verdict}
    return [verdict_line(pair, found, verdict) for pair, found in pairs.items()]


def verdict_line(pair, found, verdict):
    """A worded pair's line: the word with the persons and rows a side it was read from, since the
    word is a non-rejection rule (replication_word: an AUC bound at most 0.6 and an MMD q at least
    0.05) that a small sample satisfies for want of power, and the segment job may have labelled
    fewer CTs than the study asked for, so a reader of "replicated" sees at once how many CTs it
    rests on. A pair with no word gives its reason, cut to what the report's line holds."""
    a, b = pair.split("|")
    if found.get("word"):
        return (f"replication {a} vs {b} in {verdict['space']} ({verdict['reading']}): {found['word']}"
                f" ({counts_text(found)})")
    head = f"replication {a} vs {b}: no verdict, "
    return head + found["reason"][:rules().LINE_LIMIT - len(head)]


def counts_text(c):
    """A contrast's persons and rows a side, first/second."""
    return f"persons {c['persons'][0]}/{c['persons'][1]} n {c['n'][0]}/{c['n'][1]}"


def render_summary(folders):
    """One line a CT folder: how many CTs its render groups drew from, of how many with masks under
    every segmenter required, each such segmenter's count and the folder's CTs, the named
    segmenters whose masks were not read and why (mask_counts), and how many every group kept
    (share_subjects), the CTs the analysis reads; or why it was skipped."""
    lines = []
    for folder, record in folders.items():
        if record.get("skipped"):
            lines.append(f"render {folder}: skipped, {record['skipped'][:120]}")
            continue
        line = f"render {folder}: {len(record['subjects'])} CTs chosen of {mask_counts(record)}"
        if "shared" in record:
            line += f"; {len(record['shared'])} kept by every group"
        lines.append(line)
    return lines


def detail_of(key):
    """full for the primary space, focus for its as-stored reading, brief for the others."""
    if key == PRIMARY_SPACE:
        return "full"
    return "focus" if key.startswith(PRIMARY_SPACE) else "brief"


def group_summary(groups):
    """One line a group: its counts, or why it was skipped; the render groups whose counts are
    those of a render group listed before it, as the seven that render one choice of CTs are, are
    named together on one line where the first of them stands, in place of their counts, which
    keeps the lines for the tables."""
    lines, first_of, folded = [], {}, {}
    for g in groups:
        line = group_line(g)
        counts = line.split(" ", 3)[3]
        if g.get("source") != "render" or g["skipped"] and not g["decoded"]:
            lines.append(line)
        elif counts not in first_of:
            first_of[counts] = g["id"]
            lines.append(line)
        else:
            head = first_of[counts]
            if head not in folded:
                folded[head] = (len(lines), [])
                lines.append("")
            folded[head][1].append(g["id"])
    for head, (at, ids) in folded.items():
        lines[at] = f"groups counted as {head}: {' '.join(ids)}"
    return lines


def group_line(g):
    """A group's line: its counts, or why it was skipped."""
    if g["skipped"] and not g["decoded"]:
        return f"group {g['id']} {g['family']} skipped, {g['skipped'][:90]}"
    flag = " persons by file" if g["person_fallback"] and g["person_fallback"] >= g["chosen"] else ""
    fails = sum(g["failures"].values())
    return (f"group {g['id']} {g['family']} found {g['found']} chosen {g['chosen']} decoded {g['decoded']}"
            f" persons {g['persons']}{flag}" + (f" undecoded {fails}" if fails else ""))


# The rank of each section of a space's summary, by how it is read (fit_lines gives the highest
# up first): the primary space's table 2 and its real-real lines 3, the other spaces' tables 4,
# since no finding rests on one encoder's view, the primary space's heatmap rows 5, the as-stored
# reading 6, the context lines 7 (the nearest real corpora, the other spaces' real-real medians),
# the replication-only groups' contrasts with the real corpora and every replication pair outside
# the primary space 8, whose words the study's verdict never reads, the map centres 9. With the
# study's 23-group table and every space run, the centres, the secondary lines, the context lines
# and the as-stored reading are given up, and the heatmap rows too once FluXray is present; the
# tables of the three spaces stay whole (counted on 2026-10-27 from a results record in this shape
# with every group full and the render groups' equal counts on one line: 134 lines fitted to 75
# without FluXray, 150 to 79 with it; tests/test_domain_gap_run.py holds the budget).
RANK = {"full": 2, "full_real": 3, "brief": 4, "full_auc": 5, "focus": 6, "context": 7, "secondary": 8, "centres": 9}


def space_sections(key, space, detail):
    """One space's summary as ranked sections: its line and calibration, its worded replication
    pairs and the family contrasts of the groups that face the real corpora first; the primary
    space adds the later pairs, the real-real table, the heatmap rows, the nearest real corpora
    and the map centres; the as-stored reading keeps FleXray's own groups; the replication-only
    groups' contrasts are secondary in every space, and so is every pair of the other spaces,
    worded or not, since the study's verdict is read in the primary space alone."""
    if space.get("invalid"):
        return [(RANK[detail], [f"space {key} not run, {space['invalid']}"])]
    head = [f"space {key} dim {space['dim']} rows {space['rows']} spread {fmt(space['feature_spread'], 3)}"
            f" pca64 {fmt(space['pca64_explained'])}"] + calibration_summary(space)
    first, later = replication_summary(space)
    families, secondary = family_summary(space, detail)
    sections = [(RANK[detail], head + first + families)]
    if detail == "full":
        sections += [(RANK["full"], later), (RANK["full_real"], real_summary(space, detail)),
                     (RANK["full_auc"], group_auc_summary(space)), (RANK["context"], nearest_summary(space)),
                     (RANK["secondary"], secondary), (RANK["centres"], centre_summary(space))]
    elif detail == "brief":
        sections[0] = (RANK[detail], head + families)
        sections += [(RANK["context"], real_summary(space, detail)), (RANK["secondary"], first + later + secondary)]
    else:
        sections.append((RANK["secondary"], later))
    return [(rank, lines) for rank, lines in sections if lines]


def family_summary(space, detail):
    """The family contrasts' lines: FleXray's own groups for the as-stored reading, and for the
    other readings every group but the replication-only ones, whose lines come second."""
    kept, secondary = [], []
    for sg, inner in space.get("vs_family", {}).items():
        if detail == "focus" and sg not in FOCUS_GROUPS:
            continue
        lines = [family_line(space, sg, family, c) for family, c in inner.items()]
        if detail != "focus" and sg in REPLICATION_ONLY:
            secondary += lines
        else:
            kept += lines
    return kept, secondary


def replication_summary(space):
    """The replication pairs' lines in REPLICATION_PAIRS' order, the worded pairs' apart from the
    later ones."""
    found = space.get("replication", {})
    pairs = [pair for pair in ("|".join(p) for p in REPLICATION_PAIRS) if pair in found]
    worded = {"|".join(p) for p in REPLICATION_WORDED}
    lines = [(pair in worded, replication_line(pair, found[pair])) for pair in pairs]
    return [line for first, line in lines if first], [line for first, line in lines if not first]


def replication_line(pair, c):
    """A pair's line: the persons and rows a side first, since the word at its end is a
    non-rejection rule that a small sample satisfies for want of power (verdict_line), then the
    measures a family line carries with the MMD's q, the word's second input (the C2ST's q stays
    in results.json, since with it the line of a worded pair would pass the report's limit), the
    last of them left off whole where the line would still pass it, so a cut never takes the
    word."""
    a, b = pair.split("|")
    if "skipped" in c:
        return f" replication {a} vs {b} not tested, {c['skipped'][:130]}"
    prdc = c.get("prdc", {})
    numbers = [f"auc {auc_text(c['auc_logistic'])}", f"knn {fmt(c['auc_knn']['auc'])}",
               f"mmd p {fmt(c['mmd']['p'], 3)} q {fmt(c['mmd'].get('q'), 3)}",
               f"fd64 {fmt(c['fd64'], 1)}", f"kid64 {fmt(c['kid64']['kid'], 3)}",
               f"prdc {' '.join(fmt(prdc.get(k)) for k in ('precision', 'recall', 'density', 'coverage'))}"]
    return within_limit(f" replication {a} vs {b} {counts_text(c)}", numbers, c.get("word", ""))


def within_limit(head, numbers, word):
    """head, the numbers and the word as one line within the report's limit (LINE_LIMIT), the
    last numbers left off whole where they would pass it: every number is in results.json, while
    a word cut by safe_line would read as another."""
    limit = rules().LINE_LIMIT
    tail = f" {word}" if word else ""
    line = head
    for number in numbers:
        if len(line) + 1 + len(number) + len(tail) > limit:
            break
        line += f" {number}"
    return line + tail


def calibration_summary(space):
    cal = space.get("calibration", {})
    if cal.get("auc_median") is None:
        return []
    return [f" calibration split-half auc median {fmt(cal['auc_median'])} range"
            f" {fmt(cal['auc_range'][0])} to {fmt(cal['auc_range'][1])} over {len(cal['groups'])},"
            f" mmd flagged {len(cal['flagged'])}" + (f" ({' '.join(cal['flagged'])})" if cal["flagged"] else "")
            + f", auc interval above half {len(cal.get('auc_above', []))}"]


def family_line(space, sg, family, c):
    ratio = space.get("ratios", {}).get(sg, {}).get(family, {})
    prdc = c.get("prdc", {})
    return (f" {sg} vs {family} auc {auc_text(c['auc_logistic'])} knn {fmt(c['auc_knn']['auc'])}"
            f" fd64 {fmt(c['fd64'], 1)} ratio {fmt(ratio.get('fd_ratio'))} mmd p {fmt(c['mmd']['p'], 3)}"
            f" prdc {' '.join(fmt(prdc.get(k)) for k in ('precision', 'recall', 'density', 'coverage'))}"
            f" {ratio.get('word', '')}").rstrip()


def real_summary(space, detail):
    aucs = sorted(c["auc_logistic"]["auc"] for c in space.get("real_real", {}).values())
    lines = []
    if aucs:
        lines.append(f" real-real auc median {fmt(aucs[len(aucs) // 2])} min {fmt(aucs[0])}"
                     f" max {fmt(aucs[-1])} over {len(aucs)} pairs")
    if "fluoroscopy_vs_film" in space:
        lines.append(f" fluoroscopy vs film auc {auc_text(space['fluoroscopy_vs_film']['auc_logistic'])}")
    sil = space.get("structure", {}).get("silhouette", {})
    if sil and detail == "full":
        lines.append(f" silhouette {fmt(sil.get('overall'))}")
    return lines


def group_auc_summary(space):
    """For FleXray's own groups, the AUC and FD64 against each real group, the heatmap's rows."""
    lines = []
    for sg in FOCUS_GROUPS:
        inner = space.get("vs_group", {}).get(sg, {})
        parts = [f"{rg} {fmt(c['auc_logistic']['auc'])}/{fmt(c['fd64'], 0)}" for rg, c in inner.items()]
        lines += wrapped(f" {sg} vs groups auc/fd64", parts)
    return lines


def nearest_summary(space):
    """Which real corpora a classifier trained on the real corpora alone calls each synthetic
    group, its top three, several groups to a line."""
    parts = []
    for sg, shares in space.get("structure", {}).get("nearest_real", {}).items():
        top = sorted(shares.items(), key=lambda kv: -kv[1])[:3]
        parts.append(f"{sg} " + ", ".join(f"{g} {100 * v:.0f} pct" for g, v in top))
    return wrapped(" nearest real", parts)


def centre_summary(space, method="tsne"):
    """Each group's centre and spread on the t-SNE map, so a figure of ellipses can be drawn
    from the report alone."""
    centres = space.get("maps", {}).get("centres", {}).get(method, {})
    return wrapped(f" {method} centres", [f"{g} {' '.join(fmt(v, 1) for v in c)}" for g, c in centres.items()])


def wrapped(head, parts, width=180):
    """head and parts joined by "; " into lines of at most width characters, head on each."""
    lines, line = [], head
    for part in parts:
        if len(line) + len(part) + 2 > width and line != head:
            lines.append(line)
            line = head
        line += f"; {part}"
    return lines + [line] if parts else []


# --- the command line ------------------------------------------------------------------------------

def run(args):
    os.umask(0o077)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    table = read_table(args.groups)
    renders, folders = stage_render(args, table)
    plan = stage_plan(args, table, renders, folders)
    rows, images = stage_images(args, plan)
    if not rows["rows"]:
        raise StageError("no image decoded")
    stage_features(args, images, rows)
    results, all_maps = stage_analysis(args, plan, rows)
    line = wandb_push(args, results, all_maps)
    lines = summary_lines(results, line)
    (out / "summary.txt").write_text("\n".join(lines) + "\n", encoding="ascii")
    print("\n".join(lines))
    return 0


def plan_subjects(args):
    """The plan subcommand: each render folder's choice of CTs, made as the run makes it but
    without the masks the segment job is yet to make (MADE_SEGMENTERS), written to
    <out>/render-subjects.json for that job; nothing is rendered or decoded. The groups on segmenter
    none require no masks, so the table's choice is the one the segment job served before they
    were added, among the CTs with SPINEPS's masks; a segmenter whose masks are not read is left
    out of it as the run leaves it out. A folder whose choice is empty fails the command, so the
    job never runs on nothing, and so does one whose mask folder holds no CT's masks: the run
    reads such a folder as no masks, but the masks the plan reads are ones the data root already
    holds, so a folder of them holding none is a data root to look at, not a choice to make."""
    os.umask(0o077)
    table = read_table(args.groups)
    renderer = tool("flexray_render")
    folders = render_folders(args, table, renderer, mask_roots(args), pending=MADE_SEGMENTERS)
    for record in folders.values():
        if NO_MASKS in record.get("roots", {}).values():
            record["subjects"] = []
    write_subjects(args.out, folders)
    for folder, record in folders.items():
        log(render_summary({folder: record})[0])
    empty = [folder for folder, record in folders.items() if not record["subjects"]]
    if empty or not folders:
        raise StageError("no CT chosen for " + (", ".join(empty) or "any folder: the table has no render group"))
    return 0


def summary(args):
    print((Path(args.out) / "summary.txt").read_text(encoding="ascii"), end="")
    return 0


def study_arguments(parser, features=True):
    """The flags of run, and of plan, which takes the same less the feature spaces' weights."""
    parser.add_argument("--groups", default=str(ROOT / "data" / "domain_gap" / "groups.json"))
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--index", default="")
    if features:
        parser.add_argument("--weights", default="")
        parser.add_argument("--imagenet", default="")
    parser.add_argument("--out", required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--wandb", choices=("auto", "off"), default="auto")
    parser.add_argument("--frozen", default="")
    parser.add_argument("--spineps", default="", help="the SPINEPS masks' folder; <data root>/spineps")
    parser.add_argument("--moose", default="", help="the MOOSE masks' folder; <data root>/moose")
    parser.add_argument("--skip-masks", action="append", default=[], choices=MASK_SEGMENTERS, metavar="NAME",
                        help="leave a segmenter's masks out (spineps or moose, repeatable): the groups that name it"
                             " are skipped with that reason and the CTs are chosen without its masks")


def parse(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    study_arguments(sub.add_parser("run", help="every stage, each skipped when done"))
    study_arguments(sub.add_parser("plan", help="the choice of CTs alone, to render-subjects.json"), features=False)
    show = sub.add_parser("summary", help="print the summary of a finished run")
    show.add_argument("--out", required=True)
    return parser.parse_args(argv)


COMMANDS = {"run": run, "plan": plan_subjects, "summary": summary}


def main(argv=None):
    args = parse(argv)
    try:
        return COMMANDS[args.command](args)
    except StageError as error:
        print(f"drr-gap FAILED: {error}", flush=True)
        return 2


if __name__ == "__main__":
    sys.exit(main())
