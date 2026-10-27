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
    python tools/domain_gap.py prepare <the flags of run>
    python tools/domain_gap.py shard --out <dir> [--task N --tasks T] [--workers W] [--device cuda]
    python tools/domain_gap.py merge --out <dir> --groups data/domain_gap/groups.json [--wandb auto|off]
    python tools/domain_gap.py progress --out <dir>

`run` does the whole study in one process. On the grid it runs as three steps instead (the owner's
word of 2026-10-27, grid/drr-gap.sbatch): `prepare` makes every stage up to the analysis and each
reading's head, and writes the list of units under <out>/analysis; `shard`, one task of a Slurm
array, claims units from that list one at a time by creating a file only it can create, runs them
in a pool of W processes and writes each one's result, taking over a claim whose holder has been
silent for STALE_SECONDS; and `merge` assembles results.json, the figures and the summary from the
units' results exactly as `run` does, refusing in words while a unit is open or failed. `progress`
prints <out>/PROGRESS.txt, the safe lines every step rewrites as it goes.

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
are not read, no folder of them, one that holds too few CTs' masks to test a group or one
--skip-masks names, is skipped with that reason and the others render, the owner's word of
2026-10-27), the plan (which files of which groups,
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
import threading
import time
import traceback
import zipfile
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
# A folder that is there and holds fewer CTs' masks than a group needs persons to be tested, as a
# segment job that stopped on one of its first CTs leaves one, is read as no masks at all:
# required, it would leave every group on the folder fewer persons than any test takes, the
# groups that read no mask among them, so leaving it out can lose no test. A folder of more is
# read and holds every render group on the folder to the CTs it covers, so a segment job cut short
# a little later can still leave too few once groups pass CTs over: the study word goes only after
# the segment job's report has been read.
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
    part = own_part(path)
    part.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(part, path)


def own_part(path):
    """The neighbour a file is written to before it is renamed into place, named by this host,
    process and thread, so two writers of one file, an array's tasks on nodes that share the folder
    or two threads of one process, never write one neighbour."""
    import socket

    path = Path(path)
    return path.with_name(f"{path.name}.{socket.gethostname()}.{os.getpid()}.{threading.get_ident()}.part")


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
    subjects, a group whose segmenter's masks are not read (no folder, one that holds too few
    CTs' masks to test a group, or --skip-masks) being skipped with that reason while the others
    render (the owner's word of 2026-10-27), and the per-view seeds take the folder's salt and not the group's, so two
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
    for number, group in enumerate(groups, 1):
        note_stage(args.out, "render", "running", f"group {number} of {len(groups)}: {group.id}")
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
    whose folder holds fewer CTs' masks than MIN_PERSONS is not read either (too_few_masks); with
    the counts the plan and the summary say. A folder that is not there is skipped with its
    reason."""
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
        choice["roots"] = states | {name: too_few_masks(n) for name, n in choice["thin"].items()}
        folders[group.folder] = choice
    return folders


def subject_choice(renderer, ct_root, named, roots, salt, count, pending):
    """One folder's choice of CTs and the record it is made from: every subject the renderer finds
    under the folder, those with masks under each segmenter required (named less pending, less
    those with no root, whose masks are not read, and less those whose root holds fewer subjects'
    masks than MIN_PERSONS, listed as thin with their counts), and the first count, in the salted
    order, of the subjects with masks under every one of them; every subject where none is
    required."""
    pure = rules()
    subjects = frozenset(subject_id(s) for s in renderer.find_subjects(ct_root))
    found = {name: masked_subjects(renderer, ct_root, name, roots) & subjects
             for name in named if name not in pending and name in roots}
    masked = {name: held for name, held in found.items() if len(held) >= MIN_PERSONS}
    chosen = pure.choose_subjects(subjects, masked, count, salt)
    return {"subjects": list(chosen), "segmenters": list(named), "pending": [n for n in named if n in pending],
            "thin": {name: len(held) for name, held in found.items() if name not in masked},
            "ct": len(subjects), "masks": {name: len(held) for name, held in masked.items()},
            "every": len(pure.with_masks(subjects, masked)), "count": count}


def too_few_masks(count):
    """Why a segmenter's folder that is there is not read: it holds no CT's masks, or fewer than a
    group needs persons to be tested."""
    if count == 0:
        return NO_MASKS
    return f"only {count} CTs have them, under {MIN_PERSONS}"


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
    """features/<space>.npz: for each image, the space's features of the image and of its inverse,
    written whole and renamed, so a job cut while it writes leaves the last whole file or none."""
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
        if features_kept(path, rows["plan"]):
            done[space] = None
            continue
        log(f"features: {space} over {len(images)} images")
        embed = ENCODERS[space](space_weights(space, args), args.device)
        stored, inverse = [], []
        for start in range(0, len(images), 64):
            batch = torch.from_numpy(np.asarray(images[start:start + 64], dtype=np.float32)).unsqueeze(1)
            stored.append(embed(batch))
            inverse.append(embed(1.0 - batch))
            if start % (64 * 20) == 0:
                note_stage(args.out, "features", "running", f"{space} {start} of {len(images)} images")
        part = folder / f"{space}.npz.part"
        with open(part, "wb") as handle:
            np.savez(handle, stored=np.concatenate(stored), inverse=np.concatenate(inverse), plan=rows["plan"])
        os.replace(part, path)
        done[space] = None
    return done


def features_kept(path, plan):
    """Whether a space's features are there whole for this plan; a file a cut job left half
    written, which np.load cannot open, counts as none."""
    import numpy as np

    if not path.is_file():
        return False
    try:
        return str(np.load(path)["plan"]) == plan
    except (OSError, ValueError, KeyError, EOFError, zipfile.BadZipFile):
        return False


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


def calibration_of(nulls):
    """The split-half nulls read together: each group with SPLIT_PERSONS persons or more split in
    two by person (null_unit), where the tests must find nothing, or the pipeline is leaking."""
    import numpy as np

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


# A reading's analysis is a list of units, each one contrast, one null, one structure measure or one
# map, which reads only the reading's head (the features, their standardised copy and its first 64
# principal components) and the plan, with its own seed. So the list gives the same result run one
# unit after another in one process (analyse_head, the run subcommand) or claimed by the tasks of a
# Slurm array (prepare, shard, merge), and the assembly puts every unit where the analysis has
# always put it, in the order it has always run them. Each unit's result passes through JSON in
# both, so a unit run here and one read back from a task's file are the same object.

MAP_METHODS = ("pca", "tsne", "umap", "lda")
SEED = 0


class Head:
    """One reading of one feature space, ready for its units: the frame, the standardised features
    and their first 64 principal components, the reading's first numbers, and the groups its units
    are planned from (the testable synthetic and real groups and each pooled real family)."""

    def __init__(self, key, frame, z, z64, base, salt):
        self.key, self.frame, self.z, self.z64, self.base, self.salt = key, frame, z, z64, base, salt
        self.invalid = base.get("invalid", "")
        self.synthetic, self.real, self.families = [], [], {}
        if not self.invalid:
            self.synthetic = frame.testable("synthetic")
            self.real = frame.testable("fluoroscopy") + frame.testable("film")
            self.families = {f: pooled(frame, f, salt) for f in ("fluoroscopy", "film")}


def space_head(key, frame, salt, seed=SEED):
    """The head of one reading: z, z64 and its first numbers, the reason it is not read among them
    where every image has the same features."""
    import numpy as np

    s = stats()
    z = s.standardise(frame.x)
    z64, explained = s.pca(z, min(64, z.shape[1], len(z) - 1), seed=seed)
    base = {"dim": int(frame.x.shape[1]), "rows": int(len(frame.x)),
            "feature_spread": float(np.mean(np.std(frame.x, axis=0))),
            "pca64_explained": float(np.sum(explained))}
    if base["feature_spread"] < 1e-6:
        base["invalid"] = "every image has the same features"
    return Head(key, frame, z, z64, base, salt)


def unit_id(key, kind, a="", b=""):
    return "/".join(part for part in (key, kind, a, b) if part)


def space_units(head):
    """The reading's units in the order the analysis has always run them: each synthetic group
    against each pooled family (with the C2ST's permutation p and PRDC) and against each real
    group, every pair of real groups, the two families against each other, the replication pairs,
    the split-half nulls, the structure measures, the nearest real corpus of each synthetic group,
    the FD64 of every pair and the four maps."""
    if head.invalid:
        return []
    frame, plan = head.frame, []
    plan += [("family", sg, f) for sg in head.synthetic for f, rows in head.families.items() if len(rows)]
    plan += [("group", sg, rg) for sg in head.synthetic for rg in head.real]
    plan += [("real", a, b) for i, a in enumerate(head.real) for b in head.real[i + 1:]]
    if both_families(head):
        plan.append(("fvf", "fluoroscopy", "film"))
    plan += [("replication", a, b) for a, b in REPLICATION_PAIRS]
    plan += [("null", g, "") for g in frame.order if frame.persons(g) >= SPLIT_PERSONS]
    plan.append(("structure", "", ""))
    if nearest_ready(head):
        plan += [("nearest", sg, "") for sg in head.synthetic]
    plan.append(("fd_all", "", ""))
    plan += [("maps", method, "") for method in MAP_METHODS]
    return [{"id": unit_id(head.key, kind, a, b), "key": head.key, "kind": kind, "a": a, "b": b}
            for kind, a, b in plan]


def both_families(head):
    return bool(len(head.families.get("fluoroscopy", ())) and len(head.families.get("film", ())))


def nearest_ready(head):
    """Whether there are two real corpora or more, so a classifier trained on them alone can name
    the nearest of them for each synthetic group."""
    import numpy as np

    real_rows = np.flatnonzero(np.isin(head.frame.group, head.real))
    return len(set(head.frame.group[real_rows])) >= 2


def run_unit(head, unit, seed=SEED):
    """One unit's result as JSON reads it back, and the arrays a map unit draws beside it."""
    piece, arrays = UNIT_RUNNERS[unit["kind"]](head, unit["a"], unit["b"], seed)
    return json.loads(json.dumps(piece)), arrays


def family_unit(head, sg, family, seed):
    frame = head.frame
    return contrast(frame, head.z64, frame.rows_of(sg), head.families[family], seed, permute=True, prdc=True), {}


def pair_unit(head, a, b, seed):
    frame = head.frame
    return contrast(frame, head.z64, frame.rows_of(a), frame.rows_of(b), seed), {}


def families_unit(head, _a, _b, seed):
    return contrast(head.frame, head.z64, head.families["fluoroscopy"], head.families["film"], seed), {}


def replication_unit(head, a, b, seed):
    """One replication pair (REPLICATION_PAIRS) with every measure a family contrast gets, the C2ST
    permutation p and PRDC among them, precision and recall being the first group's against the
    second; a pair with a group the space cannot test is listed with the reason, so a FluXray not
    fetched or a render that failed is read in the result and not guessed at."""
    frame = head.frame
    missing = [f"{g}: {frame.why_untestable(g)}" for g in (a, b) if frame.why_untestable(g)]
    if missing:
        return {"skipped": "; ".join(missing)}, {}
    return contrast(frame, head.z64, frame.rows_of(a), frame.rows_of(b), seed, permute=True, prdc=True), {}


def null_unit(head, group, _b, seed):
    """One split-half null: the group split in two by person and every test run on the halves."""
    frame = head.frame
    rows = frame.rows_of(group)
    half = stats().split_half(list(frame.person[rows]), f"{head.salt}:{group}")
    return contrast(frame, head.z64, rows[half == 1], rows[half == 0], seed), {}


def structure_unit(head, _a, _b, seed):
    """Silhouette, neighbour purity and the share of each group's neighbours in each family."""
    import numpy as np

    s, frame, z64 = stats(), head.frame, head.z64
    keep = np.isin(frame.group, frame.order)
    return {"silhouette": s.silhouette(z64[keep], frame.group[keep], seed=seed),
            "purity": s.knn_purity(z64[keep], frame.group[keep]),
            "family_share": s.neighbour_family_share(z64[keep], frame.group[keep], frame.family[keep])}, {}


def nearest_unit(head, sg, _b, seed):
    """Which real corpus a classifier trained on the real corpora alone calls one synthetic group."""
    import numpy as np

    frame = head.frame
    real_rows = np.flatnonzero(np.isin(frame.group, head.real))
    return stats().nearest_real(frame.x[real_rows], frame.group[real_rows], list(frame.person[real_rows]),
                                frame.x[frame.rows_of(sg)], seed=seed), {}


def distances_unit(head, _a, _b, seed):
    return all_distances(head.frame, head.z64, seed), {}


def map_unit(head, method, _b, seed):
    """One of the maps of up to MAP_ROWS rows a group, drawn on those rows' first 50 components,
    with its trustworthiness against them (none for LDA, which is supervised) and each group's
    centre and spread; a map that could not be drawn keeps the sentence that says why."""
    s, frame = stats(), head.frame
    rows = map_rows(frame, head.salt)
    z50, _ = s.pca(head.z[rows], min(50, head.z.shape[1], len(rows) - 1), seed=seed)
    xy = s.reductions(z50, seed=seed, groups=frame.group[rows], methods=(method,))[method]
    if not hasattr(xy, "shape"):
        return {"trust": None, "not_drawn": xy}, {"rows": rows}
    trust = float(s.trust(z50, xy, seed=seed)) if method != "lda" else None
    centres = {g: centre(xy[frame.group[rows] == g]) for g in frame.order}
    return {"trust": trust, "centres": centres}, {"rows": rows, "xy": xy}


def map_rows(frame, salt):
    import numpy as np

    return np.concatenate([capped(frame, frame.rows_of(g), MAP_ROWS, f"{salt}:map:{g}") for g in frame.order])


UNIT_RUNNERS = {"family": family_unit, "group": pair_unit, "real": pair_unit, "fvf": families_unit,
                "replication": replication_unit, "null": null_unit, "structure": structure_unit,
                "nearest": nearest_unit, "fd_all": distances_unit, "maps": map_unit}


def assemble_space(head, pieces, arrays):
    """The reading's result and maps from its units' results, each put where the analysis has
    always put it, then the steps that read them together: the nulls' summary, the gap ratios,
    Benjamini-Hochberg over the space and the replication words."""
    result = dict(head.base)
    if head.invalid:
        return result, None
    slots = {"vs_family": {sg: {} for sg in head.synthetic}, "vs_group": {sg: {} for sg in head.synthetic},
             "real_real": {}, "replication": {}, "nulls": {},
             "structure": {"nearest_real": {}} if nearest_ready(head) else {}}
    maps = {"coords": {}, "trust": {}, "centres": {}}
    for unit in space_units(head):
        piece = pieces[unit["id"]]
        if unit["kind"] == "maps":
            place_map(maps, unit["a"], piece, arrays[unit["id"]])
        else:
            place(slots, unit, piece)
    result.update(vs_family=slots["vs_family"], vs_group=slots["vs_group"], real_real=slots["real_real"])
    if "fvf" in slots:
        result["fluoroscopy_vs_film"] = slots["fvf"]
    result["replication"] = slots["replication"]
    result["calibration"] = calibration_of(slots["nulls"])
    result["ratios"] = gap_ratios(head.frame, result, head.synthetic)
    result["structure"] = slots["structure"]
    result["fd_all"] = slots["fd_all"]
    adjust(result)
    replication_words(result)
    result["maps"] = {k: v for k, v in maps.items() if k != "coords"}
    return result, maps


def place(slots, unit, piece):
    """One unit's result in its slot of the reading's result."""
    kind, a, b = unit["kind"], unit["a"], unit["b"]
    if kind in ("family", "group"):
        slots["vs_family" if kind == "family" else "vs_group"][a][b] = piece
    elif kind in ("real", "replication"):
        slots["real_real" if kind == "real" else "replication"][f"{a}|{b}"] = piece
    elif kind == "null":
        slots["nulls"][a] = piece
    elif kind == "structure":
        slots["structure"].update(piece)
    elif kind == "nearest":
        slots["structure"]["nearest_real"][a] = piece
    else:
        slots[kind] = piece


def place_map(maps, method, piece, arrays):
    """One map's coordinates, trustworthiness and centres; every map draws the same rows."""
    maps["coords"]["rows"] = arrays["rows"]
    maps["coords"][method] = arrays["xy"] if "xy" in arrays else piece["not_drawn"]
    maps["trust"][method] = piece["trust"]
    if "centres" in piece:
        maps["centres"][method] = piece["centres"]


def analyse_space(frame, salt, seed=SEED, key="space"):
    """The whole analysis of one reading of a feature space, its units run here one after another."""
    return analyse_head(space_head(key, frame, salt, seed), seed)


def analyse_head(head, seed=SEED):
    units = space_units(head)
    pieces, arrays = {}, {}
    for number, unit in enumerate(units, 1):
        started = time.time()
        pieces[unit["id"]], arrays[unit["id"]] = run_unit(head, unit, seed)
        log(f"unit {number} of {len(units)}: {unit['id']} in {time.time() - started:.1f} s")
    return assemble_space(head, pieces, arrays)


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


def centre(xy):
    import numpy as np

    return [round(float(v), 2) for v in (*np.mean(xy, axis=0), *np.std(xy, axis=0))]


def stage_analysis(args, plan, rows):
    """results.json and the figures, every available reading in turn, its units run here."""
    results, all_maps, total = new_results(plan, rows), {}, 0
    for key, head in reading_heads(args, plan, rows):
        if isinstance(head, str):
            results["spaces"][key] = {"invalid": head}
            continue
        total += len(space_units(head))
        log(f"analysis: {key}, {len(space_units(head))} units")
        result, maps = analyse_head(head)
        results["spaces"][key] = result
        if maps:
            all_maps[key] = (head.frame, maps)
    record = {"jobs": {"run": job_label()}, "gpus": {gpu_name(args.device): 1},
              "units": {"total": total, "done": total, "failed": 0}, "mmd": mmd_backend()}
    return finish_results(args, results, all_maps, record=record)


def reading_heads(args, plan, rows):
    """(key, head) for each reading in the order the analysis reads them: every space
    inversion-invariant, and FleXray's own space as stored too; a space with no features gives the
    reason in place of a head."""
    import numpy as np

    for space in SPACES:
        path = Path(args.out) / "features" / f"{space}.npz"
        if not path.is_file():
            yield space, unavailable(space, args) or "no features"
            continue
        data = np.load(path)
        stored, inverse = data["stored"], data["inverse"]
        for reading, x in (("invariant", (stored + inverse) / 2.0), ("as_stored", stored)):
            if reading == "as_stored" and space != PRIMARY_SPACE:
                continue
            key = space if reading == "invariant" else f"{space}_as_stored"
            yield key, space_head(key, Frame(x, rows["rows"], plan), plan["salt"])


def new_results(plan, rows):
    return {"plan": rows["plan"], "spaces": {}, "groups": group_rows(plan, rows), "renders": plan.get("renders", {})}


def finish_results(args, results, all_maps, record=None):
    """The study's verdict, its run record, results.json and the figures, the same whether the
    units ran here or in an array's tasks."""
    results["replication"] = replication_verdict(results)
    results["_run"] = run_block(args)
    results["_record"] = record or {}
    write_json(Path(args.out) / "results.json", results)
    tool_figures = Path(args.out) / "figures"
    tool_figures.mkdir(exist_ok=True)
    started = time.time()
    figures(all_maps, results, tool_figures)
    note_seconds(args.out, "figures", time.time() - started)
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


# --- the record: what ran, from which code, on what -----------------------------------------------

STUDY = "drr-domain-gap"
# The files a unit runs, whose digest names the units: a done unit from other code is done again,
# and a task whose copy differs from the one prepare planned with refuses (runs are named by their
# code, docs/memory/runs-are-named-by-their-code.md).
CODE_FILES = ("tools/domain_gap.py", "tools/domain_gap_stats.py", "src/schwingnet/domain_gap.py")
PREREG = ROOT / "docs" / "research" / "drr-domain-gap" / "PREREG.md"


def code_digest():
    digest = hashlib.sha256()
    for name in CODE_FILES:
        digest.update(name.encode("ascii") + b"\0" + (ROOT / name).read_bytes() + b"\0")
    return digest.hexdigest()


def prereg_digest():
    """The frozen pre-registration's sha256, or empty where this copy holds none."""
    return sha256_of(PREREG) if PREREG.is_file() else ""


def git_state():
    """(commit, dirty) of the code this process runs: the grid's step gives them, since it runs
    from a copy of the commit that is no checkout; by hand they are read from git."""
    if os.environ.get("SN_GIT_HEAD"):
        return os.environ["SN_GIT_HEAD"], os.environ.get("SN_GIT_DIRTY", "no") != "no"
    import subprocess

    def git(*words):
        done = subprocess.run(["git", "-C", str(ROOT), *words], capture_output=True, text=True)
        return done.stdout.strip() if done.returncode == 0 else ""

    head = git("rev-parse", "HEAD")
    return head or "unknown", bool(git("status", "--porcelain", "--", *CODE_FILES))


def job_label():
    """The Slurm job this process runs in, an array task as <array job>_<task>, else local."""
    array, task = os.environ.get("SLURM_ARRAY_JOB_ID"), os.environ.get("SLURM_ARRAY_TASK_ID")
    if array and task:
        return f"{array}_{task}"
    return os.environ.get("SLURM_JOB_ID", "local")


def utc_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def run_block(args):
    """The Lab Recipe's _run block (its section on code and environment): the job and task, host and
    time, the commit and whether the tree was clean, the script with its hash and arguments, the
    sha256 of every input read, and the frozen pre-registration's hash."""
    import socket

    head, dirty = git_state()
    out = Path(args.out)
    inputs = {name: sha256_of(out / name) for name in ("plan.json", "rows.json") if (out / name).is_file()}
    inputs.update({f"features/{p.name}": sha256_of(p) for p in sorted((out / "features").glob("*.npz"))})
    if getattr(args, "groups", "") and Path(args.groups).is_file():
        inputs["groups.json"] = sha256_of(args.groups)
    return {"job": os.environ.get("SLURM_ARRAY_JOB_ID") or os.environ.get("SLURM_JOB_ID", "local"),
            "task": os.environ.get("SLURM_ARRAY_TASK_ID", ""), "host": socket.gethostname(), "utc": utc_now(),
            "git_head": head, "git_dirty": dirty, "script": "tools/domain_gap.py",
            "script_sha256": sha256_of(Path(__file__)), "code_digest": code_digest(), "argv": sys.argv[1:],
            "inputs": inputs, "prereg_sha256": prereg_digest(), "seed": SEED}


# --- the stages' progress: STAGES.json and PROGRESS.txt -------------------------------------------
#
# The owner's ask of 2026-10-27 17:53 UTC: "make sure you are logging, and I want to see a visual
# representation of what is happening". Every stage says when it starts and how long it took in
# analysis/STAGES.json, and PROGRESS.txt says where the whole study stands in at most about 40
# lines of counts and group ids, each made safe for the grid's redaction, which grid/gate.sh's
# status shows and a cloud session draws; nothing in it names a file or a person.

ANALYSIS = "analysis"
PROGRESS = "PROGRESS.txt"
PROGRESS_SECONDS = 30   # a task rewrites PROGRESS.txt at most this often, since it lists folders on CephFS
STAGE_ORDER = ("render", "plan", "images", "features", "heads", "analysis", "figures", "summary")


def analysis_folder(out):
    folder = Path(out) / ANALYSIS
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def stages_of(out):
    path = Path(out) / ANALYSIS / "STAGES.json"
    try:
        return read_json(path)
    except (OSError, ValueError):
        return {}


def note_stage(out, stage, state, detail=""):
    """One stage's state (running, done, failed or skipped) with when it began and what it is on."""
    stages = stages_of(out)
    entry = stages.get(stage, {})
    if state == "running" and entry.get("state") != "running":
        entry["since"] = time.time()
    if state != "running" and "since" in entry:
        entry["seconds"] = round(time.time() - entry["since"], 1)
    entry.update(state=state, detail=detail)
    stages[stage] = entry
    write_json(analysis_folder(out) / "STAGES.json", stages)
    write_progress(out, force=True)


def note_seconds(out, stage, seconds):
    stages = stages_of(out)
    stages[stage] = {"state": "done", "seconds": round(seconds, 1), "detail": ""}
    write_json(analysis_folder(out) / "STAGES.json", stages)


def staged(out, stage, step):
    """step() run as one stage, its start, end and seconds noted, a failure noted before it rises."""
    note_stage(out, stage, "running")
    log(f"stage {stage}: started")
    try:
        result = step()
    except BaseException:
        note_stage(out, stage, "failed")
        raise
    note_stage(out, stage, "done")
    log(f"stage {stage}: done in {stages_of(out).get(stage, {}).get('seconds', 0)} s")
    return result


_LAST_PROGRESS = [0.0]


def write_progress(out, force=False):
    """PROGRESS.txt whole, renamed into place, at most every PROGRESS_SECONDS unless forced."""
    if not force and time.time() - _LAST_PROGRESS[0] < PROGRESS_SECONDS:
        return
    _LAST_PROGRESS[0] = time.time()
    try:
        lines = [rules().safe_line(line) for line in progress_lines(Path(out))]
        part = own_part(Path(out) / PROGRESS)
        part.write_text("\n".join(lines) + "\n", encoding="ascii")
        os.replace(part, Path(out) / PROGRESS)
    except (OSError, ValueError) as error:  # the progress page is a view of the run, never a reason to stop it
        log(f"PROGRESS.txt not rewritten: {type(error).__name__}: {error}")


def progress_lines(out):
    """Where the study stands: the headline, the stages, each reading's units by kind, each task,
    the rate with the time left, and the units done by five-minute step for the live view's chart."""
    stages, record = stages_of(out), units_record(out)
    state = unit_state(out, record) if record else None
    lines = [headline(stages, record, state)]
    lines += stage_lines(stages)
    if record:
        lines += reading_lines(record, state)
        lines += task_lines(out, state)
        lines += rate_lines(record, state)
    return lines[:60]


def headline(stages, record, state):
    now = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    running = [s for s in STAGE_ORDER if stages.get(s, {}).get("state") == "running"]
    stage = running[0] if running else next((s for s in reversed(STAGE_ORDER) if s in stages), "none")
    if record and not running and "figures" not in stages and len(state["done"]) < len(record["units"]):
        stage = "analysis"
    if not record:
        return f"drr-gap at {now}: stage {stage}"
    return (f"drr-gap at {now}: stage {stage}; units {len(state['done'])} of {len(record['units'])} done,"
            f" {len(state['running'])} running, {len(state['failed'])} failed")


def stage_lines(stages):
    lines = []
    for stage in STAGE_ORDER:
        entry = stages.get(stage)
        if not entry:
            continue
        if entry.get("state") == "running":
            since = time.strftime("%H:%M UTC", time.gmtime(entry.get("since", time.time())))
            minutes = (time.time() - entry.get("since", time.time())) / 60
            text = f"stage {stage}: running since {since} ({minutes:.0f} min)"
        else:
            text = f"stage {stage}: {entry.get('state')} in {entry.get('seconds', 0):.0f} s"
        lines.append(text + (f", {entry['detail']}" if entry.get("detail") else ""))
    return lines


def unit_state(out, record):
    """Which units are done, failed and claimed, from the folders' names alone (no file read)."""
    folder = Path(out) / ANALYSIS
    names = {kind: listed(folder / kind) for kind in ("done", "failed", "claims")}
    numbers = {kind: {int(n.split(".")[0]) for n in found if n.split(".")[0].isdigit()} for kind, found in names.items()}
    done = {i for i in numbers["done"] if f"{i:05d}.json" in names["done"]}
    failed = numbers["failed"] - done
    return {"done": done, "failed": failed, "running": numbers["claims"] - done - failed}


def listed(folder):
    try:
        return set(os.listdir(folder))
    except OSError:
        return set()


def reading_lines(record, state):
    lines = []
    for key in record["keys"]:
        if key in record.get("invalid", {}):
            lines.append(f"reading {key}: not read, {record['invalid'][key]}")
            continue
        indexes = [i for i, u in enumerate(record["units"]) if u["key"] == key]
        kinds = {}
        for i in indexes:
            kind = record["units"][i]["kind"]
            kinds.setdefault(kind, [0, 0])
            kinds[kind][1] += 1
            kinds[kind][0] += i in state["done"]
        parts = ", ".join(f"{kind} {d} of {t}" for kind, (d, t) in kinds.items())
        lines.append(f"reading {key}: {sum(i in state['done'] for i in indexes)} of {len(indexes)} ({parts})")
    return lines


def task_lines(out, state):
    lines = []
    for path in sorted((Path(out) / ANALYSIS / "tasks").glob("*.json")):
        try:
            task = read_json(path)
        except (OSError, ValueError):
            continue
        beat = time.strftime("%H:%M:%S", time.gmtime(task.get("beat", 0)))
        lines.append(f"task {task.get('task')} ({task.get('job')}, {task.get('host')}, {task.get('gpu')}):"
                     f" {task.get('state')}, {task.get('done', 0)} done, {task.get('held', 0)} running,"
                     f" {task.get('failed', 0)} failed, beat {beat} UTC")
    return lines


def rate_lines(record, state):
    """Units a minute over the last ten minutes, weighted by their cost for the time left, and the
    units done at each five minutes since the first was claimed."""
    times = sorted(done_times(record))
    if not times:
        return []
    now, first = time.time(), times[0][0]
    recent = [cost for at, cost in times if at > now - 600]
    left = sum(unit_cost(u) for i, u in enumerate(record["units"]) if i not in state["done"])
    speed = sum(recent) / 10.0
    lines = [f"rate: {len(recent) / 10.0:.1f} units a minute over the last 10 minutes"
             + (f", about {left / speed:.0f} min left" if speed > 0 and left else "")]
    steps = [f"{minute} min {sum(1 for at, _ in times if at <= first + 60 * minute)}"
             for minute in range(5, int((times[-1][0] - first) / 60) + 5, 5)]
    lines.append("timeline of units done: " + ", ".join(steps[-12:]))
    return lines


def done_times(record):
    """(time, cost) of every unit the tasks' event logs say is done."""
    folder = Path(record["out"]) / ANALYSIS / "events"
    found = []
    for path in sorted(folder.glob("*.jsonl")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("event") == "done":
                found.append((float(event["at"]), unit_cost(record["units"][event["index"]])))
    return found


# --- the analysis in a Slurm array: prepare, shard, merge -----------------------------------------
#
# The owner's word of 2026-10-27 17:51 UTC, after the study ran for three hours on four CPUs of a
# V100 node: "cancel and shard requesting h200 / see the beethoven protocol for doing so". The
# Beethoven protocol is the Lab Recipe (artifacts/the-lab-recipe-1t2gvp/index.md, its grid rules):
# one job prepares (every stage up to the features, then each reading's head and the list of its
# units), an array's tasks share that one list through atomic claims, beat while they work, take
# over a claim whose holder stopped beating, run a GPU self-test before the first unit and stop
# after three failures in a row (rule 8), and a join assembles the result once every unit is done.
# A unit is idempotent, so a claim taken over from a task that was only slow costs a duplicate of
# the same file and nothing else.

HEARTBEAT_SECONDS = 60
STALE_SECONDS = 1200    # twenty missed beats: a holder this quiet has died or lost its node
TAKEOVER_SETTLE = 2.0   # seconds a takeover waits before it reads back whose claim stood
WATCH_SECONDS = 60      # how often a task with nothing left to claim looks at the others' units
FAILURE_STREAK = 3
# A unit's weight in the order units are claimed in, heaviest first so the array's tail is short,
# and in the time left: a permuted C2ST refits its classifier PERMUTATIONS_C2ST times a fold.
UNIT_WEIGHT = {"family": 60, "replication": 60, "maps": 6, "structure": 4, "nearest": 4}
MAP_WEIGHT = {"tsne": 20, "umap": 10}


def unit_cost(unit):
    if unit["kind"] == "maps":
        return MAP_WEIGHT.get(unit["a"], 2)
    return UNIT_WEIGHT.get(unit["kind"], 2)


def units_record(out):
    """analysis/units.json with the run folder it is in, or None before prepare has written it."""
    path = Path(out) / ANALYSIS / "units.json"
    try:
        record = read_json(path)
    except (OSError, ValueError):
        return None
    record["out"] = str(out)
    return record


def prepared_inputs(args, out):
    """Every stage up to the features, each noted: the plan, the rows and the images."""
    table = read_table(args.groups)
    renders, folders = staged(out, "render", lambda: stage_render(args, table))
    plan = staged(out, "plan", lambda: stage_plan(args, table, renders, folders))
    rows, images = staged(out, "images", lambda: stage_images(args, plan))
    if not rows["rows"]:
        raise StageError("no image decoded")
    staged(out, "features", lambda: stage_features(args, images, rows))
    return plan, rows


def prepare(args):
    """The prepare subcommand: every stage up to the features as run makes them, then each
    reading's head under analysis/heads/ and the list of every unit in analysis/units.json, and
    last analysis/PREPARED.json, so an array task reads a whole list or none. The claims, failures
    and task records of an earlier array are cleared; its done units are kept and count where their
    stamp is this list's, the same plan, heads and code."""
    os.umask(0o077)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    folder = analysis_folder(out)
    (folder / "PREPARED.json").unlink(missing_ok=True)
    plan, rows = prepared_inputs(args, out)
    record = staged(out, "heads", lambda: write_heads(args, plan, rows))
    clear_array(folder)
    gpu = gpu_name(args.device)
    write_json(folder / "PREPARED.json", {"job": job_label(), "utc": utc_now(), "gpu": gpu, "units": len(record["units"]),
                                          "stamp": record["stamp"], "run": run_block(args)})
    write_progress(out, force=True)
    log(f"prepared {len(record['units'])} units over {len(record['keys'])} readings, stamp {record['stamp'][:16]}")
    return 0


def write_heads(args, plan, rows):
    """Each reading's head, written once for the same features, plan and code, and units.json."""
    import numpy as np

    folder = analysis_folder(args.out) / "heads"
    folder.mkdir(exist_ok=True)
    keys, units, invalid, heads = [], [], {}, {}
    for key, head in reading_heads(args, plan, rows):
        keys.append(key)
        if isinstance(head, str):
            invalid[key] = head
            continue
        heads[key] = save_head(folder, head, np)
        units += space_units(head)
    code = code_digest()
    record = {"study": STUDY, "plan": rows["plan"], "salt": plan["salt"], "seed": SEED, "keys": keys,
              "invalid": invalid, "units": units, "code": code, "heads": heads,
              "stamp": digest_of([rows["plan"], code, heads, SEED])}
    write_json(analysis_folder(args.out) / "units.json", record)
    return record


def save_head(folder, head, np):
    """A reading's head as heads/<key>.npz (the features, z and z64) and heads/<key>.json (its first
    numbers), the arrays written whole and renamed; their sha256 names the head in the units' stamp."""
    path = folder / f"{head.key}.npz"
    part = folder / f"{head.key}.npz.part"
    with open(part, "wb") as handle:
        np.savez(handle, x=head.frame.x, z=head.z, z64=head.z64)
    os.replace(part, path)
    write_json(folder / f"{head.key}.json", {"key": head.key, "base": head.base, "salt": head.salt})
    return sha256_of(path)


def load_head(out, key):
    """A reading's head as prepare wrote it, its frame rebuilt from the run's own plan and rows."""
    import numpy as np

    out = Path(out)
    folder = out / ANALYSIS / "heads"
    data = np.load(folder / f"{key}.npz")
    meta = read_json(folder / f"{key}.json")
    frame = Frame(data["x"], read_json(out / "rows.json")["rows"], read_json(out / "plan.json"))
    return Head(key, frame, data["z"], data["z64"], meta["base"], meta["salt"])


def clear_array(folder):
    """An earlier array's claims, failures and task records gone, so this one starts clean."""
    for name in ("claims", "failed", "tasks"):
        sub = folder / name
        if sub.is_dir():
            for path in sub.iterdir():
                path.unlink(missing_ok=True)
        sub.mkdir(exist_ok=True)
    for name in ("done", "events"):
        (folder / name).mkdir(exist_ok=True)


def gpu_name(device):
    """The card this process would compute on, by torch, or what stands in its place."""
    if device != "cuda":
        return "cpu"
    try:
        import torch

        return torch.cuda.get_device_name(0) if torch.cuda.is_available() else "no CUDA device"
    except Exception as error:  # torch missing or the driver refusing: said, never fatal here
        return f"no GPU ({type(error).__name__})"


def gpu_self_test(device):
    """Rule 8's self-test before the first unit: the card's name where a small product on it comes
    out right, else None and why; a CPU run passes as cpu."""
    if device != "cuda":
        return "cpu", ""
    try:
        import torch

        if not torch.cuda.is_available():
            return None, "torch sees no CUDA device"
        a = torch.ones((64, 64), dtype=torch.float64, device="cuda")
        if float((a @ a).sum().item()) != 64.0 ** 3:
            return None, "a product on the card came out wrong"
        return torch.cuda.get_device_name(0), ""
    except Exception as error:  # a card the build cannot run fails here and not on the first unit
        return None, f"{type(error).__name__}: {error}"


def claim_path(folder, index):
    return folder / "claims" / f"{index:05d}"


def done_path(folder, index):
    return folder / "done" / f"{index:05d}.json"


def failed_path(folder, index):
    return folder / "failed" / f"{index:05d}.json"


def unit_done(folder, index, stamp):
    """Whether unit index has a result from this list's plan, heads and code."""
    try:
        return read_json(done_path(folder, index)).get("stamp") == stamp
    except (OSError, ValueError):
        return False


def settled(folder, index, stamp):
    return unit_done(folder, index, stamp) or failed_path(folder, index).exists()


def try_claim(folder, index, token):
    """Whether this task now holds unit index: a claim file made new, which only one creator wins,
    or one whose holder has not beaten for STALE_SECONDS, taken over and read back."""
    path = claim_path(folder, index)
    try:
        handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return take_over(path, token)
    with os.fdopen(handle, "w", encoding="ascii") as stream:
        stream.write(token)
    return True


def take_over(path, token):
    try:
        if time.time() - path.stat().st_mtime < STALE_SECONDS:
            return False
        part = path.with_name(f"{path.name}.{os.getpid()}.take")
        part.write_text(token, encoding="ascii")
        os.replace(part, path)
        time.sleep(TAKEOVER_SETTLE)
        taken = path.read_text(encoding="ascii") == token
    except OSError:
        return False
    if taken:
        log(f"took over the stale claim on unit {int(path.name)}")
    return taken


def claim_is_stale(folder, index):
    try:
        return time.time() - claim_path(folder, index).stat().st_mtime >= STALE_SECONDS
    except OSError:
        return True


class Task:
    """One array task's record: tasks/<task>.json rewritten at each beat, and events/<task>-<pid>.jsonl
    appended at each claim, unit done and failure, which the progress reads."""

    def __init__(self, folder, task, tasks, gpu):
        import socket

        self.folder, self.task, self.tasks, self.gpu = folder, task, tasks, gpu
        self.host, self.job = socket.gethostname(), job_label()
        self.token = f"{self.job} task {task} on {self.host} pid {os.getpid()} at {utc_now()}"
        self.counts = {"done": 0, "failed": 0}
        self.held = 0
        self.events = folder / "events" / f"{task:04d}-{os.getpid()}.jsonl"

    def event(self, what, index, unit_id_, **extra):
        if what in self.counts:
            self.counts[what] += 1
        line = json.dumps({"event": what, "index": index, "id": unit_id_, "at": time.time(), "task": self.task, **extra})
        with open(self.events, "a", encoding="utf-8") as stream:
            stream.write(line + "\n")

    def beat(self, claims, state="running"):
        """Every held claim touched, so no other task takes it over, and the task's record rewritten."""
        for path in claims:
            try:
                os.utime(path)
            except OSError:
                pass
        self.held = len(claims)
        write_json(self.folder / "tasks" / f"{self.task:04d}.json",
                   {"task": self.task, "tasks": self.tasks, "job": self.job, "host": self.host, "gpu": self.gpu,
                    "state": state, "beat": time.time(), "held": self.held, **self.counts})


def shard(args):
    """The shard subcommand, one task of the array: units claimed from the list prepare wrote,
    heaviest first, run by a pool of --workers processes, each result written whole, until none is
    left to claim and no other task's claim is still beating. It exits 0 having done nothing where
    prepare wrote no list (rule 9: the merge says why), 4 where the GPU fails its self-test before
    the first unit, so a task on a card the build cannot run claims nothing, and 3 once
    FAILURE_STREAK units have failed in a row."""
    os.umask(0o077)
    out = Path(args.out)
    folder = out / ANALYSIS
    if not (folder / "PREPARED.json").is_file():
        log("shard: prepare left no analysis/PREPARED.json, so there is nothing to claim")
        return 0
    record = units_record(out)
    if record is None or record["code"] != code_digest():
        raise StageError("the code differs from the code prepare planned the units with")
    gpu, why = gpu_self_test(args.device)
    if gpu is None:
        log(f"shard: the GPU self-test failed ({why}); no unit claimed")
        return 4
    task = Task(folder, args.task, args.tasks, gpu)
    task.beat([])
    log(f"shard: task {args.task} of {args.tasks} on {task.host}, {gpu}, {args.workers} workers,"
        f" {len(record['units'])} units in the list")
    code = claim_loop(out, record, task, args.workers)
    task.beat([], state="stopped" if code else "finished")
    write_progress(out, force=True)
    return code


def claim_loop(out, record, task, workers):
    from concurrent.futures import FIRST_COMPLETED, wait

    folder, stamp, units = Path(out) / ANALYSIS, record["stamp"], record["units"]
    order = sorted(range(len(units)), key=lambda i: (-unit_cost(units[i]), i))
    todo, others, held, streak = [i for i in order if not settled(folder, i, stamp)], [], {}, 0
    with unit_pool(out, workers) as pool:
        while True:
            while streak < FAILURE_STREAK and len(held) < max(1, workers):
                index = next_unit(folder, todo, others, stamp, task.token)
                if index is None:
                    break
                held[pool.submit(unit_task, str(out), index)] = (index, time.time())
                task.event("claimed", index, units[index]["id"])
            if not held:
                if streak >= FAILURE_STREAK:
                    break
                task.beat([], state="watching")
                if not watch_others(folder, todo, others, stamp):
                    break
                continue
            finished, _ = wait(list(held), timeout=HEARTBEAT_SECONDS, return_when=FIRST_COMPLETED)
            for future in finished:
                index, started = held.pop(future)
                streak = 0 if settle(folder, task, units, index, future, started) else streak + 1
            task.beat([claim_path(folder, i) for i, _ in held.values()])
            write_progress(out)
    if streak >= FAILURE_STREAK:
        log(f"shard: stopped after {FAILURE_STREAK} failures in a row")
        return 3
    log(f"shard: nothing left to claim; {task.counts['done']} done and {task.counts['failed']} failed here")
    return 0


def next_unit(folder, todo, others, stamp, token):
    """The next unit this task claims, or None: a settled one is dropped and one another task holds
    is set aside, to be watched once nothing is left to claim."""
    while todo:
        index = todo.pop(0)
        if settled(folder, index, stamp):
            continue
        if try_claim(folder, index, token):
            return index
        others.append(index)
    return None


def watch_others(folder, todo, others, stamp):
    """With nothing left to claim, the units other tasks hold: a settled one dropped, one whose
    holder stopped beating put back to be taken over; True while any is still held."""
    still = [i for i in others if not settled(folder, i, stamp)]
    others[:] = []
    for index in still:
        (todo if claim_is_stale(folder, index) else others).append(index)
    if others and not todo:
        time.sleep(WATCH_SECONDS)
    return bool(todo or others)


def settle(folder, task, units, index, future, started):
    """A finished unit's outcome: done, logged with its seconds, or failed, recorded with the kind
    of error and where it rose; True when done."""
    unit = units[index]
    try:
        seconds, backend = future.result()
    except Exception as error:  # one unit's failure is recorded and counted toward the streak, never fatal alone
        where = traceback.extract_tb(error.__traceback__)[-1:] if error.__traceback__ else []
        write_json(failed_path(folder, index), {"id": unit["id"], "error": type(error).__name__,
                                                "where": [f"{f.name}:{f.lineno}" for f in where], "task": task.token})
        task.event("failed", index, unit["id"], seconds=round(time.time() - started, 1), error=type(error).__name__)
        log(f"unit {unit['id']} FAILED after {time.time() - started:.0f} s: {type(error).__name__}: {error}")
        return False
    task.event("done", index, unit["id"], seconds=round(seconds, 1), backend=backend)
    log(f"unit {unit['id']} done in {seconds:.1f} s ({task.counts['done']} done by this task)")
    return True


class InlinePool:
    """A pool of one: each unit run in this process when it is submitted, its future already done."""

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def submit(self, fn, *args):
        from concurrent.futures import Future

        future = Future()
        try:
            future.set_result(fn(*args))
        except Exception as error:  # carried in the future as a process pool carries it
            future.set_exception(error)
        return future


def unit_pool(out, workers):
    """workers processes, started fresh rather than forked (the self-test opened CUDA here, which a
    fork must not copy), each with one BLAS and torch thread so the node's CPUs are the pool's; or
    this process alone for one worker."""
    if workers <= 1:
        return InlinePool()
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[name] = "1"
    context = multiprocessing.get_context("spawn")
    return ProcessPoolExecutor(max_workers=workers, mp_context=context, initializer=pool_start)


def pool_start():
    try:
        import torch

        torch.set_num_threads(1)
    except ImportError:
        pass


_LOADED = {}


def loaded(key, make):
    """One object per process for key: a worker reads the list and each head once."""
    if key not in _LOADED:
        _LOADED[key] = make()
    return _LOADED[key]


def unit_task(out, index):
    """One unit in a worker: its head loaded once per process, its result written whole, then
    (seconds, the MMD's backend)."""
    folder = Path(out) / ANALYSIS
    record = units_record(out)
    unit = record["units"][index]
    head = loaded((str(out), record["stamp"], unit["key"]), lambda: load_head(out, unit["key"]))
    started = time.time()
    piece, arrays = run_unit(head, unit, record["seed"])
    seconds = time.time() - started
    backend = mmd_backend()
    save_unit(folder, index, unit, piece, arrays, record["stamp"], seconds, backend)
    return seconds, backend


def mmd_backend():
    """Which backend the MMD's permutations ran on here, as domain_gap_stats chooses it."""
    torch, device = stats().torch_device("auto")
    return f"torch-{device.type}" if torch is not None else "numpy"


def save_unit(folder, index, unit, piece, arrays, stamp, seconds, backend):
    """done/<index>.npz with a map's arrays first, then done/<index>.json, both written whole: a
    result file that is there names arrays that are there."""
    import numpy as np

    if arrays:
        part = own_part(folder / "done" / f"{index:05d}.npz")
        with open(part, "wb") as handle:
            np.savez(handle, **arrays)
        os.replace(part, folder / "done" / f"{index:05d}.npz")
    write_json(done_path(folder, index), {"id": unit["id"], "stamp": stamp, "piece": piece, "seconds": round(seconds, 3),
                                          "backend": backend, "job": job_label(), "utc": utc_now()})


def read_units(folder, record, key):
    """The results of one reading's units as prepare listed them, and a map unit's arrays."""
    import numpy as np

    pieces, arrays = {}, {}
    for index, unit in enumerate(record["units"]):
        if unit["key"] != key:
            continue
        done = read_json(done_path(folder, index))
        if done["id"] != unit["id"] or done["stamp"] != record["stamp"]:
            raise StageError(f"unit {index} holds another unit's result")
        pieces[unit["id"]] = done["piece"]
        npz = folder / "done" / f"{index:05d}.npz"
        arrays[unit["id"]] = dict(np.load(npz)) if npz.is_file() else {}
    return pieces, arrays


def open_units(folder, record):
    """(the units not done, the units failed), each as a count by kind."""
    missing, failed = {}, {}
    for index, unit in enumerate(record["units"]):
        if unit_done(folder, index, record["stamp"]):
            continue
        holder = failed if failed_path(folder, index).exists() else missing
        holder[unit["kind"]] = holder.get(unit["kind"], 0) + 1
    return missing, failed


def merge(args):
    """The merge subcommand, the array's join: every unit's result read back and each reading
    assembled as the analysis in one process assembles it, then results.json, the figures, W&B and
    summary.txt as run writes them. It refuses while any unit is not done or has failed, saying
    how many of which kind, so no part of a result is ever written; a resend of the study word then
    runs only those, the done units counting again under the same plan, heads and code."""
    os.umask(0o077)
    out = Path(args.out)
    folder = out / ANALYSIS
    if not (folder / "PREPARED.json").is_file():
        raise StageError("prepare did not finish: there is no analysis/PREPARED.json")
    record = units_record(out)
    if record["code"] != code_digest():
        raise StageError("the code differs from the code prepare planned the units with")
    missing, failed = open_units(folder, record)
    write_progress(out, force=True)
    if missing or failed:
        raise StageError(f"{sum(missing.values())} of {len(record['units'])} units not done {words_by_kind(missing)}"
                         f" and {sum(failed.values())} failed {words_by_kind(failed)}")
    joined = array_record(out, record)
    note_seconds(out, "analysis", joined["analysis_seconds"])
    plan, rows = read_json(out / "plan.json"), read_json(out / "rows.json")
    results, all_maps = new_results(plan, rows), {}
    for key in record["keys"]:
        if key in record["invalid"]:
            results["spaces"][key] = {"invalid": record["invalid"][key]}
            continue
        head = load_head(out, key)
        result, maps = assemble_space(head, *read_units(folder, record, key))
        results["spaces"][key] = result
        if maps:
            all_maps[key] = (head.frame, maps)
    results, all_maps = finish_results(args, results, all_maps, record=joined)
    write_summary(args, results, all_maps)
    return 0


def words_by_kind(counts):
    return "(" + ", ".join(f"{kind} {n}" for kind, n in sorted(counts.items())) + ")" if counts else ""


def array_record(out, record):
    """What the report says of the run as a whole: the jobs, the cards, the units and the seconds
    of every stage, read from prepare's record, the tasks' records and the units' results."""
    folder = Path(out) / ANALYSIS
    prepared = read_json(folder / "PREPARED.json")
    tasks = [read_json(p) for p in sorted((folder / "tasks").glob("*.json"))]
    seconds, backends, finished, began = 0.0, set(), [], []
    for index in range(len(record["units"])):
        done = read_json(done_path(folder, index))
        seconds += float(done.get("seconds", 0))
        backends.add(done.get("backend", "unknown"))
    for at, _ in done_times(record):
        finished.append(at)
    for path in sorted((folder / "events").glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if '"claimed"' in line:
                began.append(json.loads(line)["at"])
    gpus = {}
    for name in [prepared.get("gpu", "")] + [t.get("gpu", "") for t in tasks]:
        if name:
            gpus[name] = gpus.get(name, 0) + 1
    arrays = sorted({t["job"].split("_")[0] for t in tasks if "_" in str(t.get("job", ""))})
    return {"jobs": {"prepare": prepared.get("job", "unknown"), "array": ", ".join(arrays) or "none",
                     "tasks": len(tasks), "merge": job_label()},
            "gpus": gpus, "units": {"total": len(record["units"]), "done": len(record["units"]), "failed": 0},
            "mmd": backends.pop() if len(backends) == 1 else "mixed " + "/".join(sorted(backends)),
            "units_seconds": round(seconds), "analysis_seconds": round(max(finished) - min(began)) if finished and began else 0}


def write_summary(args, results, all_maps):
    """W&B, then summary.txt with the record's lines first, and results.json again with every
    stage's seconds in its record, which only now are all known."""
    out = Path(args.out)
    line = wandb_push(args, results, all_maps)
    results["_record"]["seconds"] = {stage: entry.get("seconds", 0) for stage, entry in stages_of(out).items()}
    write_json(out / "results.json", results)
    lines = summary_lines(results, line)
    (out / "summary.txt").write_text("\n".join(lines) + "\n", encoding="ascii")
    note_stage(out, "summary", "done")
    print("\n".join(lines))


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
    sections = [(0, [header] + record_lines(results) + verdict_lines(results.get("replication", {}))),
                (1, render_summary(results.get("renders", {})) + group_summary(results["groups"]))]
    for key, space in results["spaces"].items():
        sections += space_sections(key, space, detail_of(key))
    lines = fit_lines(sections, LINE_BUDGET)
    return [rules().safe_line(line) for line in lines][:LINE_BUDGET]


RECORD_SECONDS = ("render", "plan", "images", "features", "heads", "analysis", "figures")


def record_lines(results):
    """The run's record in five lines, which the study's CLAIM report reads from the summary
    (tools/report.py, study mode): the code and its inputs, the jobs and the cards, the units, the
    seconds of each stage, and the environment's pins as the grid's step gives them."""
    run, record = results.get("_run"), results.get("_record", {})
    if not run:
        return []
    jobs, units, seconds = record.get("jobs", {}), record.get("units", {}), record.get("seconds", {})
    cards = ", ".join(f"{name} x{count}" for name, count in sorted(record.get("gpus", {}).items())) or "none"
    if "prepare" in jobs:
        ran = f"prepare {jobs['prepare']}, array {jobs['array']} ({jobs['tasks']} tasks), merge {jobs['merge']}"
    else:
        ran = f"run {jobs.get('run', 'local')}"
    timed = [f"{stage} {seconds.get(stage, 0):.0f}" + (" (wall)" if stage == "analysis" else "") for stage in RECORD_SECONDS]
    timed.insert(-1, f"units {record.get('units_seconds', 0):.0f} (summed)")
    return [f"record: study {STUDY}; commit {run['git_head'][:7]}; tree {'dirty' if run['git_dirty'] else 'clean'};"
            f" seed {run['seed']}; plan {results['plan'][:16]}; groups.json {run['inputs'].get('groups.json', '')[:16] or 'none'};"
            f" PREREG {run['prereg_sha256'][:16] or 'none'}; code {run['code_digest'][:16]}",
            f"record: jobs {ran}; GPUs {cards}",
            f"record: units {units.get('done', 0)} of {units.get('total', 0)} done, {units.get('failed', 0)} failed;"
            f" mmd backend {record.get('mmd', 'unknown')}",
            "record: seconds " + ", ".join(timed),
            f"record: environment {os.environ.get('SN_PINS', 'not given')}"]


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
    """Every stage in this process, the analysis's units one after another: the reference the
    array's three steps (prepare, shard, merge) reproduce."""
    os.umask(0o077)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    plan, rows = prepared_inputs(args, out)
    results, all_maps = staged(out, "analysis", lambda: stage_analysis(args, plan, rows))
    write_summary(args, results, all_maps)
    return 0


def plan_subjects(args):
    """The plan subcommand: each render folder's choice of CTs, made as the run makes it but
    without the masks the segment job is yet to make (MADE_SEGMENTERS), written to
    <out>/render-subjects.json for that job; nothing is rendered or decoded. The groups on segmenter
    none require no masks, so the table's choice is the one the segment job served before they
    were added, among the CTs with SPINEPS's masks; a segmenter whose masks are not read is left
    out of it as the run leaves it out. A folder whose choice is empty fails the command, so the
    job never runs on nothing, and so does one whose mask folder holds too few CTs' masks: the run
    reads such a folder as no masks, but the masks the plan reads are ones the data root already
    holds, so a folder of them holding too few is a data root to look at, not a choice to make."""
    os.umask(0o077)
    table = read_table(args.groups)
    renderer = tool("flexray_render")
    folders = render_folders(args, table, renderer, mask_roots(args), pending=MADE_SEGMENTERS)
    for record in folders.values():
        if record.get("thin"):
            record.update(subjects=[], every=0)
    write_subjects(args.out, folders)
    for folder, record in folders.items():
        log(render_summary({folder: record})[0])
    empty = [folder + thin_reason(record) for folder, record in folders.items() if not record["subjects"]]
    if empty or not folders:
        raise StageError("no CT chosen for " + (", ".join(empty) or "any folder: the table has no render group"))
    return 0


def thin_reason(record):
    """Why the plan chose no CT of a folder whose mask folder holds too few: the masks it reads are
    ones the data root already holds."""
    thin = record.get("thin") or {}
    if not thin:
        return ""
    names = " and ".join(f"{name} {count}" for name, count in thin.items())
    return f" (too few CTs with the masks the data root should already hold: {names})"


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
    study_arguments(sub.add_parser("prepare", help="every stage up to the features, then the heads and the list of units"))
    task = sub.add_parser("shard", help="one array task: claim units from the list and run them")
    task.add_argument("--out", required=True)
    task.add_argument("--task", type=int, default=int(os.environ.get("SLURM_ARRAY_TASK_ID", "0")))
    task.add_argument("--tasks", type=int, default=int(os.environ.get("SLURM_ARRAY_TASK_COUNT", "1")))
    task.add_argument("--workers", type=int, default=1)
    task.add_argument("--device", default="cuda")
    join = sub.add_parser("merge", help="the array's join: every unit read back, results.json and summary.txt")
    join.add_argument("--out", required=True)
    join.add_argument("--groups", default=str(ROOT / "data" / "domain_gap" / "groups.json"))
    join.add_argument("--wandb", choices=("auto", "off"), default="auto")
    for name, words in (("summary", "print the summary of a finished run"), ("progress", "write and print PROGRESS.txt")):
        show = sub.add_parser(name, help=words)
        show.add_argument("--out", required=True)
    return parser.parse_args(argv)


def progress(args):
    write_progress(args.out, force=True)
    print((Path(args.out) / PROGRESS).read_text(encoding="ascii"), end="")
    return 0


COMMANDS = {"run": run, "plan": plan_subjects, "prepare": prepare, "shard": shard, "merge": merge,
            "summary": summary, "progress": progress}


def main(argv=None):
    args = parse(argv)
    try:
        return COMMANDS[args.command](args)
    except StageError as error:
        print(f"drr-gap FAILED: {error}", flush=True)
        return 2


if __name__ == "__main__":
    sys.exit(main())
