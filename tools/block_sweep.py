"""List the trainer's building blocks, plan a sweep over them, and compare the runs made, on validation only.

Usage:
    python3 tools/block_sweep.py parts
    python3 tools/block_sweep.py plan --catalog <catalog.sqlite> --out <runs folder> --epochs 20 \
        --seed 1 --hours 4 [--weights [ARCHITECTURE=]<file> ...] [--base KEY=VALUE ...] \
        --vary KEY=V1/V2 [--vary ...]
    python3 tools/block_sweep.py compare <run dir> [<run dir> ...] [--by accuracy|balanced-accuracy]
    python3 tools/block_sweep.py ledger <runs folder> [--by accuracy|balanced-accuracy]

The block smoke test (#252, docs/research/block-smoke/):
    python3 tools/block_sweep.py cover --name synthetic --catalog synthetic|v1|with:<source> \
        --epochs 3 --seed 1 [--strict]
    python3 tools/block_sweep.py trials --catalog v1 --epochs 20 --seed 1
    python3 tools/block_sweep.py check --catalog <catalog.sqlite> (--plan <plan.json> | --all) \
        [--weights ARCHITECTURE=<file> ...] [--sizes 32,64,96,128] [--json]
    python3 tools/block_sweep.py synthetic --into <folder> [--frames 600 --cases 40 \
        --test-frames 100 --unlabelled-frames 200 --seed 1]
    python3 tools/block_sweep.py prepare --plan <plan.json> --catalog <catalog.sqlite> \
        --out <smoke root> [--weights ARCHITECTURE=<file> ...]
    python3 tools/block_sweep.py state --plan <plan.json> --catalog <catalog.sqlite> \
        --out <smoke root> [--epochs N]
    python3 tools/block_sweep.py row --state <state> --slug <slug> --catalog <catalog.sqlite> \
        [--environment train-gpu] [--epochs N] [--weights ARCHITECTURE=<file> ...] \
        [--keep-epoch-weights]
    python3 tools/block_sweep.py results <state>

The loop the owner asked for on 2026-10-24, optimising which samples, architecture, denoising and
augmentation a run uses as plug-and-play pieces (docs/research/experiment-framework.md), is these
four commands over the blocks of src/schwingnet/blocks.py. `parts` prints every part, its names
and version 1's choice: the one list of the plug-in points. `plan` writes the tools/flow.py
command of every combination, the number of runs and the GPU-hours they would ask for, and starts
nothing, since no grid job is sent without the owner's word and the count; `vary` separates values
with "/", so an augment value keeps its commas: `--vary augment=none/box-jitter,intensity`. An
ImageNet file is one architecture's, so `--weights` names the architecture its file is for, a bare
file being resnet18's, and a sweep in which one run would start from ImageNet and another from
nothing is refused, since its rows would compare the start and not the block.

`compare` and `ledger` read each run's train/checkpoint.json and train/metrics.jsonl, and its
latency headline where one was measured (evaluate/latency.json, a timing and no score), never
evaluate/results.json: the runs are ranked by the
validation part and its witness frames alone, so choosing among them never reads a test person
(docs/research/retraining-plan.md, section 4). The chosen run is then evaluated once on the test
part, as any run is. `ledger` finds every run under a folder by itself, so the next plan is made
from the whole record and not from the directories someone remembered to name.

The smoke test makes the owner's ask of 2026-10-24, that any combination of the blocks within the
declared incompatibilities works on any dataset held, annotated and unannotated, in two halves.
`check` decides, for one catalog and training nothing, every named combination at every crop
size from the catalog's own facts (which sources hold labelled crops, which crops carry a level
map, how many persons): it runs, or the trainer will refuse it for a stated reason. Then a plan of
a few runs, the covering set of src/schwingnet/blocks.py (`cover`) or the trials
(`trials`), runs on the GPU, each run set against what the check predicted for it; a run whose
outcome differs from its prediction is a bug in the check or in the trainer, and is flagged as
such. The plan files under grid/sweeps/ are these commands' output, and a test makes them again
byte for byte, so a plan is a function of the code. `synthetic` builds the synthetic catalog the
synthetic plan runs on. The plans are run only by the Metaflow flow flows/sweep.py, whose resume
is the one way a sweep is continued: it calls `prepare` once, which writes the plan's state folder
`<smoke root>/<plan>/<code 8>-<catalog sha256 8>/` (`-e<N>` after it for N epochs in place of
the plan's) with the plan resolved against the catalog,
the check's verdicts and the results so far, then `row` for each row, which runs tools/flow.py
with the row's slug as its folder and records what came of it, and `results` at the end. Every
file of the state is written whole and renamed into place, and the three result files under a
lock, so two rows finishing at once never lose one another's entry and the status word, which
reads PROGRESS.txt on the login node, never reads half of one.

A state is named by the code its rows and records are made by and by the plan file's bytes
(state_code), not by the commit it was prepared on: main merges many times a day, and a sweep
named by its commit, cut at its time limit after a merge that changed nothing it runs, would
train every finished row again (issue #252, finding 27). A merge that changes none of the
state's code (tools/run_code.py's kind state, which holds every file a row runs) and leaves the
plan as it was names the same state, whose finished rows tools/flow.py carries on, and any
other names a new one. PLAN.json records that code's digest and keeps the commit the state was
first prepared on, which holds the same code. `state` prints the folder `prepare` makes and
makes nothing, so grid/sweep-driver.sbatch reads the path from here rather than make it again.
"""

import argparse
import fcntl
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
# The contracts the package is written with, from the pinned copy, as tools/ingest.py takes them,
# so a python with beartype and icontract runs this tool without the environment's own path.
sys.path.insert(1, str(ROOT / "vendor" / "beethoven-qa" / "src"))

from schwingnet.blocks import (  # noqa: E402
    ARCHITECTURE,
    AUGMENT,
    CHOICES,
    DEFAULT,
    FIRST_LABELLED,
    LABELLED,
    PRIOR,
    RULES,
    SAMPLES,
    SETTING_OF,
    UNLABELLED,
    BlockError,
    cover,
    from_record,
    kept,
    parse,
    parts,
    problems,
    sweep,
    trials,
    words_of,
)

EVALUATE_HOURS = 1.0


def parse_vary(pairs):
    """{block: [values]} from KEY=V1/V2 words."""
    vary = {}
    for pair in pairs:
        key, sep, text = pair.partition("=")
        if not sep or not text:
            raise BlockError(f"{pair!r}: vary is KEY=V1/V2")
        vary[key.strip().replace("-", "_")] = [v for v in text.split("/") if v]
    return vary


def weights_files(words):
    """{architecture: ImageNet file} from the --weights words, [ARCHITECTURE=]FILE each; a bare
    file is resnet18's, version 1's start."""
    files = {}
    for word in words:
        name, sep, rest = word.partition("=")
        named = bool(sep) and "/" not in name and "." not in name
        name, file = (name, rest) if named else (DEFAULT.architecture, word)
        if name not in ARCHITECTURE or not file or name in files:
            raise BlockError(f"--weights {word!r}: one ImageNet file per architecture, as [ARCHITECTURE=]FILE ({', '.join(ARCHITECTURE)})")
        files[name] = file
    return files


def weights_for(files, blocks):
    """The run's ImageNet file, the one of its architecture; a run that would start from nothing
    in a sweep whose other runs start from ImageNet is refused, since the rows would then compare
    the start and not the block."""
    if not files:
        return None
    if blocks.architecture not in files:
        raise BlockError(f"architecture={blocks.architecture}: no --weights file for it; give --weights {blocks.architecture}=FILE, or no --weights at all")
    return files[blocks.architecture]


def flow_command(args, blocks, files):
    words = words_of(blocks)
    weights = weights_for(files, blocks)
    return " ".join(
        ["python3 tools/flow.py run", f"--catalog {args.catalog}", f"--out {args.out}", "--mode slurm",
         f"--epochs {args.epochs}", f"--seed {args.seed}", f"--hours {args.hours}"]
        + ([f"--weights {weights}"] if weights else [])
        + [f"--block {word}" for word in words]
    )


def plan(args):
    runs = sweep(args.base, parse_vary(args.vary))
    files = weights_files(args.weights)
    commands = [flow_command(args, blocks, files) for blocks in runs]
    hours = len(runs) * (args.hours + EVALUATE_HOURS)
    return {
        "runs": len(runs),
        "jobs": 2 * len(runs),
        "gpu_hours_requested": hours,
        "note": "a plan only: nothing is submitted; each command is one run of tools/flow.py, two jobs (train, evaluate)",
        "commands": commands,
    }


def best_line(run_dir):
    """The run's checkpoint facts, its blocks and the metrics line of the epoch the checkpoint names."""
    facts = json.loads((run_dir / "train" / "checkpoint.json").read_text(encoding="utf-8"))
    lines = [json.loads(line) for line in (run_dir / "train" / "metrics.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    best = next((line for line in lines if line["epoch"] == facts["epoch"]), None)
    if best is None:
        raise BlockError(f"train/metrics.jsonl holds no epoch {facts['epoch']}, the one train/checkpoint.json names")
    return facts, from_record(facts.get("blocks")), best


def parent_text(parent):
    """The parent as the ledger names it: its run id, else its file with its hash, since every
    run's checkpoint is called best.pt."""
    if not parent:
        return "none"
    if parent.get("run_id"):
        return parent["run_id"]
    digest = parent.get("sha256")
    return f"file {parent['file']}" + (f" (sha256 {digest[:12]})" if digest else "")


def latency_of(run_dir):
    """The run's latency headline, the fastest arm whose parity holds (tools/latency.py), as
    "<p95> ms (<arm>)", or "not measured"; a number, not a test score, so a ledger may read it."""
    headline = run_dir / "evaluate" / "latency.json"
    if not headline.is_file():
        return "not measured"
    arm = json.loads(headline.read_text(encoding="utf-8"))
    return f"{arm['ms_per_frame_p95']:.1f} ms ({arm['arm']})"


def row_of(run_dir):
    """One run as the ledger shows it: its blocks that differ from version 1, what it trained on,
    where it began, its best validation numbers and its latency where measured; a record that
    cannot be read as a run is refused naming the run, so one broken folder names itself."""
    try:
        return _row_of(run_dir)
    except (BlockError, OSError, ValueError, KeyError, TypeError, AttributeError, AssertionError) as error:
        raise BlockError(f"{run_dir}: not read as a run ({error})") from error


def _row_of(run_dir):
    facts, blocks, line = best_line(run_dir)
    witness = line.get("witness_validation")
    counts = facts.get("counts") or {}
    return {
        "run": run_dir.resolve().name,
        "blocks": " ".join(words_of(blocks)) or "version 1 (no block named)",
        "train_crops": counts.get("train"),
        "train_seen": counts.get("train_seen"),
        "train_offered": counts.get("train_offered"),
        "parent": parent_text(facts.get("parent")),
        "epoch": line["epoch"],
        "accuracy": line["validation_accuracy"],
        "ci": line["validation_ci"],
        "n": line["validation_n"],
        "balanced_accuracy": line.get("validation_balanced_accuracy"),
        "witness": f"{witness[0]}/{witness[1]}" if witness else "not drawn",
        "latency": latency_of(run_dir),
    }


def compare(run_dirs, by):
    """The named runs ranked by the chosen validation number, best first, unrecorded last."""
    rows = [row_of(Path(run_dir)) for run_dir in run_dirs]
    key = "balanced_accuracy" if by == "balanced-accuracy" else "accuracy"
    rows.sort(key=lambda row: (row[key] is None, -(row[key] or 0.0)))
    return rows


def runs_under(folder):
    """Every run directory under a folder: one that holds train/checkpoint.json and
    train/metrics.jsonl, however deep and behind links, since a runs folder on the grid may link
    to the lab volume, so a runs folder of a year is read whole; a folder reached twice counts
    once."""
    found, walked = {}, set()
    for path, dirs, files in os.walk(Path(folder).resolve(), followlinks=True):
        real = os.path.realpath(path)
        if real in walked:
            dirs.clear()
            continue
        walked.add(real)
        dirs.sort()
        if Path(path).name == "train" and {"checkpoint.json", "metrics.jsonl"} <= set(files):
            found[real] = Path(path).parent
    return sorted(found.values())


def ledger(folder, by):
    """compare over every run under the folder."""
    runs = runs_under(folder)
    if not runs:
        raise BlockError(f"{folder}: no run with train/checkpoint.json and train/metrics.jsonl under it")
    return compare(runs, by)


def crops_text(row):
    """The training crops as the record counts them: what the samples block kept of what the
    catalog offered, and a --max-frames cap apart, so a dry run's cut is never read as a block's;
    a record from before the counts says what it has."""
    used, offered = row["train_crops"], row["train_offered"]
    if used is None:
        return "not recorded"
    seen = used if row["train_seen"] is None else row["train_seen"]
    text = str(seen) if offered in (None, seen) else f"{seen} of {offered}"
    return text if used == seen else f"{text}, capped to {used}"


def table(rows):
    out = ["| run | blocks | training crops | parent | best epoch | validation | 95% interval | balanced | validation witness | latency p95 |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for row in rows:
        balanced = "not recorded" if row["balanced_accuracy"] is None else f"{row['balanced_accuracy']:.3f}"
        out.append(f"| {row['run']} | {row['blocks']} | {crops_text(row)} | {row['parent']} | {row['epoch']} | {row['accuracy']:.3f} (n={row['n']}) | {row['ci'][0]:.3f} to {row['ci'][1]:.3f} | {balanced} | {row['witness']} | {row['latency']} |")
    return "\n".join(out)


def parts_table():
    """Every plug-in point as a table: the part, what it may be, version 1's choice."""
    out = ["| part | choices | version 1 |", "|---|---|---|"]
    out += [f"| {row['part']} | {row['choices']} | {row['default']} |" for row in parts()]
    return "\n".join(out)


# The block smoke test (#252): the plans, the check, the synthetic catalog and the state of a
# sweep. Everything below reads a catalog or a run folder and writes plain files; the rules of
# which crops a block keeps and of what a cover is are the package's (schwingnet.blocks).

PLAN_NAME = re.compile(r"[a-z0-9_]{1,40}")
CATALOG_WORD = re.compile(r"synthetic|v1|with:[a-z0-9_]{1,40}")
# The crop sizes the check's rules were measured at on every architecture, and the only ones it
# decides: between them the rules depend on the architecture (densenet121 cannot forward at 16 or
# 24 pixels, the prior's head builds at 30 for six of the eight, and seven of the eight train on
# one 48-pixel crop), which the check, counting by the samples cut, the prior and the size alone,
# does not read, so another size is refused rather than decided wrongly.
CHECK_SIZES = (32, 64, 96, 128)
# The prior's head needs a feature map of 8 cells across the crop, which no architecture's
# shallowest named stage keeps below 32 pixels (tools/train_blocks.py PriorHead); a batch of one
# crop cannot train below 64 pixels, measured on every architecture at 32 and on densenet121 at 48
# (tools/train.py trains_on_one_crop), so a training part of exactly one crop is refused there.
SMALLEST_PRIOR_CROP = 64 // 2
SMALLEST_ONE_CROP = 64
# What a parent checkpoint must share with the run that warm-starts from it (tools/train.py
# INHERITED), beside its crop size.
INHERITED = ("architecture", "denoise", "normalise")
RUNS, REFUSED, NOT_APPLICABLE = "runs", "refused", "not applicable"
RAN, FAILED, TO_COME = "ran", "failed", "to-come"
# Each refusal the check predicts, by the words the trainer or the flow refuses it in (tools/train.py,
# tools/flow.py, tools/train_blocks.py); a row the check calls refused matches only when its log
# says the words of the code it predicted. The order is the trainer's, which is the order the
# check asks its questions in, so the first refusal predicted is the one the trainer meets.
REFUSALS = {
    "problems": "blocks:",
    "init-and-weights": "not both",
    "source-absent": "not in the catalog's train part",
    "cut-leaves-none": "leaves none of the",
    "no-validation": "no labelled train or validation crops",
    "init-mismatch": "the parent was trained",
    "no-map": "no training crop comes from a frame with a level map",
    "prior-size": "take a larger crop",
    "one-crop": "one training crop",
}
CROP_FACTS_SQL = """
SELECT i.part, i.person, i.source, {level_map} AS level_map
FROM label l
JOIN item i ON i.sha256 = l.item AND i.shard = l.shard
JOIN shard s ON s.name = i.shard
WHERE i.part IN ('train', 'validation')
ORDER BY i.sha256, l.level
"""
ITEM_FACTS_SQL = "SELECT source, part, COUNT(*), COUNT(DISTINCT person) FROM item GROUP BY source, part ORDER BY source, part"
# The facts table's labelled crops and crops with a map in every part, the test part's among them,
# counted as CROP_FACTS_SQL reads a label, so the table says what each part holds; the predictions
# read the train and validation crops alone, as the trainer does.
LABEL_FACTS_SQL = """
SELECT i.source, i.part, COUNT(*), SUM({level_map} IS NOT NULL)
FROM label l
JOIN item i ON i.sha256 = l.item AND i.shard = l.shard
JOIN shard s ON s.name = i.shard
GROUP BY i.source, i.part
"""
VERSION_NAME = re.compile(r"catalog-(\d{6})-[0-9a-f]{12}\.sqlite$")
PROGRESS_LINES = 60
# How tools/flow.py refuses a run folder that holds another run (its new_folder): within one
# state, whose code, plan, catalog and epochs are fixed, only another --environment or other
# bytes behind --weights name another run for the same slug.
HELD_FOLDER = re.compile(r"holds run \S+, and this configuration of this code on this catalog names run \S+; nothing is touched")
# The most of a row's reason a line of PROGRESS.txt carries. Status shows the reason only where
# it can quote no value (grid/report-shapes.awk judges what follows "why:"), since the tools'
# words can name a frame's file, which carries a case's number, or a run's id.
PROGRESS_WHY = 100
# The synthetic catalog stands for the routes of the real data: a labelled source with level maps
# and frozen test persons, as C-ArmLSpine brings them, a second labelled source with level maps,
# as a render's shard brings them (the VerSe projections, a train-side render source), and an
# unannotated one, as VinDr-SpineXR enters the bank; its banks are ingested under those sources'
# names. The labelled bank's last third of cases is the render's, so each source cut of the cover
# has two labelled sources to keep or drop one of.
SYNTHETIC_DATE = "2026-10-24"
LABELLED_SOURCE, RENDER_SOURCE, UNLABELLED_SOURCE = "carmlspine", "verse_2d_projections", "vindr_spinexr"
RENDER_SHARE = 3


def now():
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_whole(path, text):
    """A file written beside its place and renamed into it, so no reader sees half of it."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            out.write(text)
        os.replace(name, path)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise


def json_text(data):
    """A plan's or a record's text: sorted keys, indent 1, a newline at the end, so the same data
    is the same bytes on every machine."""
    return json.dumps(data, indent=1, sort_keys=True) + "\n"


def catalog_words(word):
    """What a plan's catalog field names, in words, for its "about" sentence."""
    if word == "synthetic":
        return ("the synthetic catalog of `block_sweep.py synthetic` (a labelled bank with level maps, its cases split between C-ArmLSpine's route and a render's,"
                " the frozen test persons and an unannotated bank)")
    if word == "v1":
        return "catalog version 1 of C-ArmLSpine, real frames"
    return f"version 1's catalog with {word.removeprefix('with:')} banked beside it"


def plan_row(row):
    """A row as a plan file holds it: the blocks as the words that name them, placeholders kept."""
    return {"slug": row["slug"], "role": row["role"], "size": row["size"], "blocks": words_of(row["blocks"]),
            "weights": row["weights"], "init": row["init"]}


def checked_plan_words(name, catalog):
    if not PLAN_NAME.fullmatch(name):
        raise BlockError(f"--name {name!r}: a plan's name is lower-case letters, digits and _, at most 40, as the grid gate's words take it")
    if not CATALOG_WORD.fullmatch(catalog):
        raise BlockError(f"--catalog {catalog!r}: a plan's catalog is synthetic, v1 or with:<source>")


def cover_plan(name, catalog, epochs, seed, strict=False):
    """The covering set as a plan file: every row of schwingnet.blocks.cover, with what it is."""
    checked_plan_words(name, catalog)
    how = "the full pairwise array of every two parts, the prior among them" if strict else "every option of every part and every pair of parts whose code meets, with the prior off and on"
    about = (f"The block smoke test's covering set on {catalog_words(catalog)}: {how}, and for each prior the two cuts to one labelled source of several"
             " (only-sources and drop-sources to @first-labelled), which train on a strict part of the labelled crops where the catalog holds two labelled"
             f" sources and are not applicable where it holds one; then a run from the ImageNet file, two warm starts and the four refusals the check predicts,"
             f" {epochs} epochs each, every row set against tools/block_sweep.py check's prediction for it (#252).")
    return {"plan": name, "about": about, "catalog": catalog, "epochs": epochs, "seed": seed, "rows": [plan_row(row) for row in cover(strict)]}


def trials_plan(catalog, epochs, seed):
    """The trials as a plan file: the six arms of schwingnet.blocks.trials, each source
    cited for what it did. Kwak, Ro and Kang's ResNet-50 (J Clin Med 14:7671, read on the journal's
    page on 2026-10-25) trained with AdamW, its decay, a warm-up and a cosine schedule at one rate,
    its first two blocks frozen, and kept the model of the highest accuracy, with no balanced
    sampling or balanced accuracy, so they are cited for the third arm's recipe, with how the arm
    differs, its tenth of the rate for the pretrained layers among those differences, and the
    balanced arms cite no one."""
    checked_plan_words("trials", catalog)
    about = (f"The six trials on {catalog_words(catalog)}, each resnet18 from its ImageNet file for {epochs} epochs: version 1's training as the control;"
             " the ImageNet scaling with every augment change, the strong one being SyntheX's strong domain randomisation (Gao, Killeen et al. 2023, Nat Mach Intell 5:294)"
             " with the transforms FluoroSAM adds (Killeen et al., MICCAI 2025); that with AdamW, its decay, a warm-up and a cosine schedule, the recipe of Kwak, Ro"
             " and Kang 2025 (J Clin Med 14:7671: AdamW with decay 0.01 and cosine annealing after a 5-epoch warm-up), here at 64 pixels for"
             f" {epochs} epochs with a 1-epoch warm-up, the trainer's own rate and a tenth of it for the pretrained layers, where theirs trained a ResNet-50 at 224 pixels"
             " for 200 epochs at 5e-6 with its first two blocks frozen;"
             " the second arm at 96 pixels; the second with balanced sampling and the checkpoint chosen by balanced accuracy, for the rare transitional levels, this"
             " project's own choice, for which no source is cited; and the third with that sampling and selection.")
    return {"plan": "trials", "about": about, "catalog": catalog, "epochs": epochs, "seed": seed, "rows": [plan_row(row) for row in trials()]}


def file_sha256(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def catalog_version(path):
    """The version a store's file names, 1 for a file outside a versioned store (tools/flow.py)."""
    found = VERSION_NAME.search(Path(path).name)
    return int(found.group(1)) if found else 1


def read_facts(catalog):
    """What the check reads from a catalog, the trainer's way (tools/train.py read_crops): each
    labelled body of the train and validation parts in the catalog's order with its source, its
    person and whether its frame has a level map, and every source's frames, labelled crops,
    crops with a map and persons in each part, the test part's too, so a source with frames and
    no labelled body is seen as the unannotated set it is and the test part as the labelled one."""
    path = Path(catalog)
    if not path.is_file():
        raise BlockError(f"{catalog}: no catalog there")
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        columns = {row[1] for row in db.execute("PRAGMA table_info(item)")}
        level_map = "i.level_map" if "level_map" in columns else "NULL"
        crops = [{"part": part, "person": person, "source": source, "map": bool(found)}
                 for part, person, source, found in db.execute(CROP_FACTS_SQL.format(level_map=level_map))]
        labels = {(source, part): (count, mapped or 0) for source, part, count, mapped in db.execute(LABEL_FACTS_SQL.format(level_map=level_map))}
        items = list(db.execute(ITEM_FACTS_SQL))
    except sqlite3.Error as error:
        raise BlockError(f"{catalog}: not read as a catalog ({error})") from error
    finally:
        db.close()
    table = []
    for source, part, frames, persons in items:
        count, mapped = labels.get((source, part), (0, 0))
        table.append({"source": source, "part": part, "frames": frames, "labelled_crops": count,
                      "crops_with_map": mapped, "persons": persons})
    in_train = {row["source"] for row in table if row["part"] == "train"}
    labelled = sorted({c["source"] for c in crops if c["part"] == "train"})
    return {"crops": crops, "table": table, "labelled": labelled, "unlabelled": sorted(in_train - set(labelled))}


def verdict(predicted, code=None, why="", train_crops=None):
    return {"predicted": predicted, "code": code, "why": why, "train_crops": train_crops}


def placeholder_sources(name, facts):
    """The sources a placeholder names on this catalog, and why where it names none: @labelled the
    train part's sources with labelled crops, @unlabelled those without, and @first-labelled the
    first by name of the labelled ones where there are two or more, since a cut to the only one
    would keep every crop or none; any other name is itself."""
    labelled = facts["labelled"]
    if name == FIRST_LABELLED:
        if len(labelled) > 1:
            return labelled[:1], None
        held = f"one source with labelled crops ({labelled[0]})" if labelled else "no source with labelled crops"
        return [], (f"{name} names no source of this catalog: its train part has {held}, and a cut to one labelled source of several needs two,"
                    " since a cut to the only one keeps every crop or none")
    if name in (LABELLED, UNLABELLED):
        group = labelled if name == LABELLED else facts["unlabelled"]
        kind = "with" if name == LABELLED else "without"
        return group, None if group else f"{name} names no source of this catalog: its train part has no source {kind} labelled crops"
    return [name], None


def resolved(blocks, facts):
    """The blocks with the placeholders named for this catalog (placeholder_sources); (None, why)
    where one names no source of it."""
    if not blocks.sources:
        return blocks, None
    names = []
    for name in blocks.sources:
        group, why = placeholder_sources(name, facts)
        if not group:
            return None, why
        names += [source for source in group if source not in names]
    return replace(blocks, sources=tuple(names)), None


def crops_verdict(blocks, size, facts, parent=None):
    """What the trainer will do with these blocks at this size on this catalog, its questions
    asked in its own order (tools/train.py run): the samples cut over the labelled train crops,
    a validation part to score, the parent's input, the level maps the prior needs, the crop the
    prior's head needs and a training part of one crop."""
    offered = [c for c in facts["crops"] if c["part"] == "train"]
    validation = [c for c in facts["crops"] if c["part"] == "validation"]
    present = {c["source"] for c in offered}
    absent = [s for s in blocks.sources if s not in present]
    if absent:
        return verdict(REFUSED, "source-absent", f"sources={','.join(absent)}: not in the catalog's train part, whose sources are {', '.join(sorted(present)) or 'none'}")
    keep = kept(blocks, [c["source"] for c in offered], [c["person"] for c in offered])
    train = [c for c, k in zip(offered, keep, strict=True) if k]
    if offered and not train:
        return verdict(REFUSED, "cut-leaves-none", f"the samples cut leaves none of the {len(offered)} training crops")
    if not train or not validation:
        return verdict(REFUSED, "no-validation", f"the catalog has no labelled train or validation crops ({len(train)} train, {len(validation)} validation)")
    if parent is not None:
        theirs, their_size = parent
        for name in INHERITED:
            if getattr(theirs, name) != getattr(blocks, name):
                return verdict(REFUSED, "init-mismatch", f"the parent was trained with {name}={getattr(theirs, name)}, this run names {name}={getattr(blocks, name)}")
        if their_size != size:
            return verdict(REFUSED, "init-mismatch", f"the parent was trained on {their_size}-pixel crops, this run on {size}")
    if blocks.prior != "none" and not any(c["map"] for c in train):
        return verdict(REFUSED, "no-map", f"prior={blocks.prior}: none of the {len(train)} training crops comes from a frame with a level map")
    if blocks.prior != "none" and size < SMALLEST_PRIOR_CROP:
        return verdict(REFUSED, "prior-size", f"prior={blocks.prior} at {size}-pixel crops: the prior's head needs {SMALLEST_PRIOR_CROP} pixels or more")
    if len(train) == 1 and size < SMALLEST_ONE_CROP:
        return verdict(REFUSED, "one-crop", f"one training crop at {size} pixels, on which batch norm cannot train; {SMALLEST_ONE_CROP} pixels or more can")
    return verdict(RUNS, None, f"{len(train)} training crops, {sum(c['map'] for c in train)} with a map, {len(validation)} validation crops", len(train))


def row_verdict(row, facts, files, earlier):
    """The check's prediction for one plan row; `earlier` holds the rows before it by slug, with
    their own predictions, since a warm start runs only once its parent has."""
    try:
        planned = parse(row["blocks"])
    except BlockError as error:
        return verdict(REFUSED, "problems", f"blocks: {error}")
    blocks, why = resolved(planned, facts)
    if blocks is None:
        return verdict(NOT_APPLICABLE, None, why)
    found = problems(blocks)
    if found:
        return verdict(REFUSED, "problems", "blocks: " + "; ".join(found))
    if row["weights"] and row["weights"] not in files:
        return verdict(NOT_APPLICABLE, None, f"no --weights file for {row['weights']}, whose ImageNet file the row starts from")
    parent = None
    if row["init"]:
        before = earlier.get(row["init"])
        if before is None:
            return verdict(NOT_APPLICABLE, None, f"its parent row {row['init']} is not a row before it in the plan")
        parent_row, parent_verdict = before
        if parent_verdict["predicted"] != RUNS:
            return verdict(NOT_APPLICABLE, None, f"its parent row {row['init']} is predicted {parent_verdict['predicted']}, so no best.pt is there to start from")
        parent = (parse(parent_row["blocks"]), parent_row["size"])
        if row["weights"]:
            return verdict(REFUSED, "init-and-weights", "a run starts from ImageNet (--weights) or from a parent (--init), not both")
    return crops_verdict(blocks, row["size"], facts, parent)


def sizes_words():
    return ", ".join(map(str, CHECK_SIZES[:-1])) + f" and {CHECK_SIZES[-1]}"


def refuse_unmeasured(size, what):
    """A crop size the rules were not measured at, refused in words (CHECK_SIZES)."""
    if size not in CHECK_SIZES:
        raise BlockError(f"{what}: crop size {size}: the check decides only the sizes its rules were measured at on every architecture, {sizes_words()} pixels")


def plan_verdicts(plan, facts, files):
    """Every row's prediction, in the plan's order, by slug; a plan with a row at a size the
    check does not decide is refused whole."""
    for row in plan["rows"]:
        refuse_unmeasured(row["size"], f"row {row['slug']}")
    earlier, verdicts = {}, {}
    for row in plan["rows"]:
        verdicts[row["slug"]] = row_verdict(row, facts, files, earlier)
        earlier[row["slug"]] = (row, verdicts[row["slug"]])
    return verdicts


def canonical_blocks(samples, prior):
    """Version 1's blocks with one samples choice and one prior, each with its canonical setting."""
    settings = {**SETTING_OF.get(("samples", samples), {}), **SETTING_OF.get(("prior", prior), {})}
    return replace(DEFAULT, samples=samples, prior=prior, **settings)


def other_combinations():
    """How many named combinations share each choice of the samples cut and the prior: the
    product of every other named part's choices, and that times every subset of the augment
    names; none of them changes what the trainer refuses, since each is a hook of its own."""
    count = math.prod(len(choices) for name, choices in CHOICES.items() if name not in ("samples", "prior"))
    return count, count * 2 ** len(AUGMENT)


def all_verdicts(facts, sizes):
    """Every named combination at each size, counted by the three parts that can change a
    verdict, the samples cut, the prior and the crop size."""
    named, with_augment = other_combinations()
    cells = []
    for size in sizes:
        for samples in SAMPLES:
            for prior in PRIOR:
                blocks, why = resolved(canonical_blocks(samples, prior), facts)
                found = verdict(NOT_APPLICABLE, None, why) if blocks is None else crops_verdict(blocks, size, facts)
                cells.append({"size": size, "samples": samples, "prior": prior, "named": named, "with_augment": with_augment, **found})
    return cells


def facts_table(facts):
    out = ["| source | part | frames | labelled crops | crops with a map | persons |", "|---|---|---|---|---|---|"]
    out += [f"| {r['source']} | {r['part']} | {r['frames']} | {r['labelled_crops']} | {r['crops_with_map']} | {r['persons']} |" for r in facts["table"]]
    return out


def sources_line(facts):
    first, why = placeholder_sources(FIRST_LABELLED, facts)
    return (f"Sources of the train part with labelled crops (@labelled): {', '.join(facts['labelled']) or 'none'}; "
            f"without (@unlabelled): {', '.join(facts['unlabelled']) or 'none'}; "
            f"the first labelled source of several (@first-labelled): {', '.join(first) or 'none, ' + why.split(': ', 1)[1]}.")


def setting_words(samples, prior):
    words = words_of(canonical_blocks(samples, prior))
    return " ".join(w for w in words if not w.startswith("prior")) or "samples=all", " ".join(w for w in words if w.startswith("prior")) or "prior=none"


def all_markdown(catalog, facts, cells):
    """`check --all` as a page: the catalog's facts, every cell of the samples cut, the prior and
    the size with its verdict and how many named combinations it stands for, the totals, and the
    incompatibilities the blocks declare."""
    named, with_augment = other_combinations()
    out = [f"# Every named combination on {Path(catalog).name}", "",
           f"Catalog {catalog} (sha256 {file_sha256(catalog)[:12]}). Each cell stands for {named:,} named combinations of the other parts"
           f" ({with_augment:,} with every subset of the {len(AUGMENT)} augment names), since only the samples cut, the prior and the crop size change"
           " what the trainer refuses; every other part is a hook that acts on whatever crops it is handed.", "", *facts_table(facts), "", sources_line(facts), "",
           "| crop | samples | prior | verdict | why | named combinations | with augment subsets |", "|---|---|---|---|---|---|---|"]
    for cell in cells:
        samples, prior = setting_words(cell["samples"], cell["prior"])
        said = cell["predicted"] + (f" ({cell['code']})" if cell["code"] else "")
        out.append(f"| {cell['size']} | {samples} | {prior} | {said} | {cell['why']} | {cell['named']:,} | {cell['with_augment']:,} |")
    out += ["", "| crop | runs | refused | not applicable | of named combinations | of combinations with augment subsets |", "|---|---|---|---|---|---|"]
    for size in sorted({cell["size"] for cell in cells}):
        mine = [cell for cell in cells if cell["size"] == size]
        tally = {kind: sum(cell["named"] for cell in mine if cell["predicted"] == kind) for kind in (RUNS, REFUSED, NOT_APPLICABLE)}
        whole = sum(cell["named"] for cell in mine)
        out.append(f"| {size} | {tally[RUNS]:,} | {tally[REFUSED]:,} | {tally[NOT_APPLICABLE]:,} | {whole:,} | {whole * 2 ** len(AUGMENT):,} |")
    out += ["", "The incompatibilities the blocks declare (schwingnet.blocks.problems), which the flow refuses before any step; every named combination above, with its"
            " canonical settings (adamw with weight_decay 0.01, the level-map prior with prior_weight 0.5, cap-per-person with per_person 1, only-sources with every"
            " labelled source, drop-sources with the first labelled source of several), holds them:", ""]
    out += [f"- {rule}" for rule in RULES]
    return "\n".join(out) + "\n"


def plan_markdown(catalog, facts, plan, verdicts):
    """`check --plan` as a page: the catalog's facts and each row's prediction."""
    out = [f"# The plan {plan['plan']} on {Path(catalog).name}", "", f"Catalog {catalog} (sha256 {file_sha256(catalog)[:12]}).", "",
           *facts_table(facts), "", sources_line(facts), "", "| row | role | crop | blocks | predicted | why |", "|---|---|---|---|---|---|"]
    for row in plan["rows"]:
        found = verdicts[row["slug"]]
        said = found["predicted"] + (f" ({found['code']})" if found["code"] else "")
        out.append(f"| {row['slug']} | {row['role']} | {row['size']} | {' '.join(row['blocks']) or 'version 1'} | {said} | {found['why']} |")
    return "\n".join(out) + "\n"


def check_document(catalog, facts, plan=None, files=None, sizes=CHECK_SIZES):
    """check's verdicts as data: for a plan, each row's; else every cell of --all."""
    document = {"catalog": str(catalog), "catalog_sha256": file_sha256(catalog), "facts": facts["table"],
                "labelled_sources": facts["labelled"], "unlabelled_sources": facts["unlabelled"]}
    if plan is None:
        cells = all_verdicts(facts, sizes)
        named, with_augment = other_combinations()
        return {**document, "all": cells, "named_per_cell": named, "with_augment_per_cell": with_augment, "rules": list(RULES)}
    verdicts = plan_verdicts(plan, facts, files or {})
    return {**document, "plan": plan["plan"], "rows": [{"slug": row["slug"], "role": row["role"], **verdicts[row["slug"]]} for row in plan["rows"]]}


def parse_sizes(text):
    try:
        sizes = tuple(int(part) for part in text.split(",") if part.strip())
    except ValueError as error:
        raise BlockError(f"--sizes {text!r}: crop sizes in pixels, comma-separated") from error
    if not sizes:
        raise BlockError(f"--sizes {text!r}: crop sizes in pixels, comma-separated, of {sizes_words()}")
    for size in sizes:
        refuse_unmeasured(size, f"--sizes {text}")
    return sizes


def command_check(args):
    facts = read_facts(args.catalog)
    files = weights_files(args.weights)
    if args.all:
        document = check_document(args.catalog, facts, sizes=parse_sizes(args.sizes))
        return json_text(document) if args.json else all_markdown(args.catalog, facts, document["all"])
    plan = read_json(args.plan)
    if args.json:
        return json_text(check_document(args.catalog, facts, plan, files))
    return plan_markdown(args.catalog, facts, plan, plan_verdicts(plan, facts, files))


# The synthetic catalog.

def run_tool(name, *words):
    """One of the repository's tools as a subprocess of this python; its JSON answer, or its own
    words where it refused."""
    done = subprocess.run([sys.executable, str(ROOT / "tools" / name), *map(str, words)], cwd=ROOT, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        said = (done.stderr.strip() or done.stdout.strip()).splitlines()[-1:] or [f"exit {done.returncode}"]
        raise BlockError(f"tools/{name} {words[0]}: {said[0]}")
    return done.stdout


def frozen_cases(source):
    """The frozen test persons of a source, by the case each names (data/splits/test-persons.json)."""
    persons = read_json(ROOT / "data" / "splits" / "test-persons.json")
    return [entry["person"].removeprefix(f"{source}:") for entry in persons if entry["person"].startswith(f"{source}:")]


def git_head():
    done = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise BlockError(f"git rev-parse HEAD in {ROOT}: {done.stderr.strip()}")
    return done.stdout.strip()


def run_code():
    """tools/run_code.py by its file, as tools/flow.py loads it, since tools/ is no package."""
    spec = importlib.util.spec_from_file_location("schwingnet_tool_run_code", ROOT / "tools" / "run_code.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# What a synthetic catalog is made by, beside its arguments: the tools that write, ingest and
# build it, this file among them, since build_synthetic and move_last_cases here split the
# labelled bank between its two sources and give the seeds and the date, the rules they import,
# the split files and the registry entries of its sources. Their hashes go into SYNTHETIC.json,
# so a catalog an older version of any of them made is made again, while a merge that changes
# none of them, which a new commit alone would say, reuses it.
SYNTHETIC_MADE_BY = ("tools/block_sweep.py", "tools/synthetic_bank.py", "tools/ingest.py", "tools/bank.py", "tools/catalog.py",
                     "src/schwingnet/catalog.py", "data/splits/rule.json", "data/splits/test-persons.json")
SYNTHETIC_SOURCES = (LABELLED_SOURCE, RENDER_SOURCE, UNLABELLED_SOURCE)


def synthetic_made_by():
    """{file: sha256} of everything a synthetic catalog is made by, the paths from the repository."""
    files = [*SYNTHETIC_MADE_BY, *(f"data/registry/{source}.json" for source in SYNTHETIC_SOURCES)]
    return {name: file_sha256(ROOT / name) for name in sorted(files)}


def recorded_build(record_file):
    """SYNTHETIC.json as the last build wrote it, or None where there is none it can be read as."""
    try:
        record = read_json(record_file)
    except (OSError, ValueError):
        return None
    return record if isinstance(record, dict) else None


def why_built_again(record, wanted, made_by):
    """Why the recorded build cannot be reused, in words; None where it can."""
    if record is None:
        return "no build is recorded"
    if record.get("arguments") != wanted:
        return f"it was built with {record.get('arguments')}, not {wanted}"
    if not isinstance(record.get("made_by"), dict):
        return "its record holds no hashes of what made it"
    if record["made_by"] != made_by:
        changed = sorted(set(made_by) ^ set(record["made_by"]) | {name for name in made_by if record["made_by"].get(name) != made_by[name]})
        return f"what makes it has changed since: {', '.join(changed)}"
    if not Path(str(record.get("catalog"))).is_file():
        return f"its catalog {record.get('catalog')} is not there"
    return None


def clear_builds(builds, keep=None):
    """Every folder under builds/ but the one named `keep`: a build cut short, which no record
    names, or the one a newer build replaced, which no sweep reads once the record names another,
    since the gate runs one sweep at a time."""
    for folder in sorted(builds.iterdir()):
        if folder.is_dir() and folder.name != keep:
            shutil.rmtree(folder)


def move_last_cases(bank, into, share):
    """The frames of the last 1/share of the bank's cases by name, with their metas and level
    maps, moved into a bank of their own: two labelled sources from one bank, no frame's bytes
    in both, since a frame the bank repeats repeats one of its own case's (tools/synthetic_bank.py)."""
    metas = {path: read_json(path) for path in sorted((bank / "meta").glob("*.json"))}
    cases = sorted({meta["case"] for meta in metas.values()})
    moved = set(cases[len(cases) - len(cases) // share:])
    for path, meta in metas.items():
        if meta["case"] not in moved:
            continue
        for name in (f"images/{meta['split']}/{path.stem}.png", f"meta/{path.name}", meta.get("level_map")):
            if name:
                (into / name).parent.mkdir(parents=True, exist_ok=True)
                os.replace(bank / name, into / name)
    return sorted(moved)


def build_synthetic(folder, wanted):
    """The banks, their shards and the store inside one build's own folder; the catalog file and
    the shards' manifests."""
    banks, commit, seed = folder / "banks", git_head(), wanted["seed"]
    run_tool("synthetic_bank.py", banks / "labelled", "--frames", wanted["frames"], "--cases", wanted["cases"], "--seed", seed)
    move_last_cases(banks / "labelled", banks / "render", RENDER_SHARE)
    run_tool("synthetic_bank.py", banks / "test", "--frames", wanted["test_frames"], "--test-cases", ",".join(frozen_cases(LABELLED_SOURCE)), "--seed", seed + 1)
    run_tool("synthetic_bank.py", banks / "unlabelled", "--frames", wanted["unlabelled_frames"], "--cases", wanted["cases"], "--seed", seed + 2, "--unlabelled")
    shards = []
    for bank, source, kind, persons in (("labelled", LABELLED_SOURCE, "train", "all"), ("render", RENDER_SOURCE, "train", "all"),
                                        ("test", LABELLED_SOURCE, "test", "frozen"), ("unlabelled", UNLABELLED_SOURCE, "train", "all")):
        report = json.loads(run_tool("ingest.py", "run", "--bank", banks / bank, "--source", source, "--kind", kind, "--persons", persons,
                                     "--date", SYNTHETIC_DATE, "--code-commit", commit, "--grid-root", folder / source))
        shards.append(str(Path(report["folder"]) / "MANIFEST.json"))
    manifests = [word for shard in shards for word in ("--manifest", shard)]
    built = json.loads(run_tool("catalog.py", "build", "--store", folder / "store", *manifests, "--root", folder, "--code-commit", commit).splitlines()[-1])
    return str(folder / "store" / "versions" / built["file"]), shards, commit


def synthetic_catalog(into, frames=600, cases=40, test_frames=100, unlabelled_frames=200, seed=1):
    """The synthetic plan's catalog, built once under `into` and reused: a labelled bank with level
    maps, two thirds of its cases ingested as C-ArmLSpine's train shard and the last third as the
    VerSe projections', a render's, a bank of the frozen test persons ingested as C-ArmLSpine's
    test shard, and an unannotated bank ingested as VinDr-SpineXR's, built into a store. Both
    labelled sources and the unannotated one have registry entries and licence entries, so the
    flow's licence record and the split check take the catalog as they take a real one; the
    licence classes they record are the real sources', borrowed, as the names are, since the
    frames hold nothing of any person. SYNTHETIC.json records the arguments, the hashes of what
    makes it (SYNTHETIC_MADE_BY) and the file, so the same arguments and code find the catalog
    built before and build nothing, and anything else builds it again.

    Each build is made in a folder of its own under builds/, fresh from tempfile, and is put in
    place by SYNTHETIC.json, renamed over the record before it only once the build is whole, so a
    build cut short, at any step, leaves a folder no record names, which the next build removes,
    and never blocks it. The folder is not renamed itself: the catalog names each shard by the
    path its manifest was read at (tools/catalog.py), where the trainer reads its frames. The
    whole build holds into/.lock, so two builds into one folder take turns."""
    into = Path(into).resolve()
    if cases < RENDER_SHARE:
        raise BlockError(f"--cases {cases}: {RENDER_SHARE} or more, so the last third of them is the render's labelled source and the rest C-ArmLSpine's")
    wanted = {"frames": frames, "cases": cases, "test_frames": test_frames, "unlabelled_frames": unlabelled_frames, "seed": seed}
    record_file, builds = into / "SYNTHETIC.json", into / "builds"
    builds.mkdir(parents=True, exist_ok=True)
    with (into / ".lock").open("a", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        record, made_by = recorded_build(record_file), synthetic_made_by()
        why = why_built_again(record, wanted, made_by)
        if why is None:
            return {"catalog": record["catalog"], "reused": True}
        print(f"block_sweep: synthetic: building it under {builds}, since {why}", file=sys.stderr)
        clear_builds(builds, keep=Path(record["build"]).name if record and record.get("build") else None)
        folder = Path(tempfile.mkdtemp(dir=builds, prefix="build-"))
        try:
            os.chmod(folder, 0o755)  # mkdtemp makes it private; the lab reads the frames
            catalog, shards, commit = build_synthetic(folder, wanted)
        except BaseException:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        write_whole(record_file, json_text({"arguments": wanted, "made_by": made_by, "build": str(folder), "catalog": catalog,
                                            "commit": commit, "built_at": now(), "shards": shards}))
        clear_builds(builds, keep=folder.name)
    return {"catalog": catalog, "reused": False}


# The state of a sweep: prepare, row and results.

def state_code(plan_file):
    """The digest of the code a state's rows and records are made by (tools/run_code.py, kind
    state), and the sha256 over it and the plan file's bytes that names the state: a merge that
    changes neither names the same state, and any other change names another."""
    tool = run_code()
    try:
        code = tool.digest("state")
    except tool.RunCodeError as error:
        raise BlockError(f"the sweep's code cannot be named: {error}") from error
    return code, hashlib.sha256(f"state {code}\nplan {file_sha256(plan_file)}\n".encode("ascii")).hexdigest()


def state_folder(out, plan_name, named, catalog, epochs=None):
    """`<out>/<plan>/<code 8>-<catalog sha256 first 8>`, the code part the first eight digits of
    state_code's name, then `-e<N>` where the rows train for N epochs in place of the plan's, so
    a sweep with another epoch count never meets the folders of the plan's own."""
    name = f"{named[:8]}-{file_sha256(catalog)[:8]}"
    return Path(out) / plan_name / (f"{name}-e{epochs}" if epochs else name)


def plan_of(path):
    """A plan file whose name a state folder can carry."""
    plan = read_json(path)
    if not isinstance(plan, dict) or not PLAN_NAME.fullmatch(str(plan.get("plan", ""))):
        raise BlockError(f"{path}: no plan name a state folder can carry")
    return plan


def own_epochs(args, plan):
    """The epochs a state's rows train for where they are not the plan's own, else None."""
    return args.epochs if args.epochs and args.epochs != plan.get("epochs") else None


def state_of(args, plan):
    """The state folder of a plan for these arguments, and the digest of the code that names it."""
    code, named = state_code(args.plan)
    return state_folder(args.out, plan["plan"], named, Path(args.catalog).resolve(), own_epochs(args, plan)), code


def first_commit(state):
    """The commit PLAN.json names where the state was prepared before, else this checkout's: the
    folder is named by its code, so the commit it was first prepared on holds the same code, and
    a prepare on a later commit leaves the files as the first wrote them."""
    try:
        held = read_json(state / "PLAN.json").get("commit")
    except (OSError, ValueError, AttributeError):
        held = None
    return held if isinstance(held, str) and re.fullmatch(r"[0-9a-f]{40}", held) else git_head()


def resolved_words(row, facts):
    """The row's block words with the placeholders named for this catalog; the plan's own where
    a placeholder names nothing here, since that row is not applicable and never runs, or where
    the words do not parse, since the check predicts the flow refuses them (problems) and the row
    runs to see it do so."""
    try:
        planned = parse(row["blocks"])
    except BlockError:
        return row["blocks"]
    blocks, _ = resolved(planned, facts)
    return row["blocks"] if blocks is None else words_of(blocks)


def write_if_changed(path, text):
    """A state file written only where its text changed, so a second prepare of the same code,
    plan and catalog leaves every file as the first wrote it."""
    if not (path.is_file() and path.read_text(encoding="utf-8") == text):
        write_whole(path, text)


def command_prepare(args):
    plan = plan_of(args.plan)
    catalog = Path(args.catalog).resolve()
    facts, files = read_facts(catalog), weights_files(args.weights)
    state, code = state_of(args, plan)
    check = check_document(catalog, facts, plan, files)
    resolved_plan = {**plan, "epochs": own_epochs(args, plan) or plan.get("epochs"),
                     "catalog_file": str(catalog), "catalog_sha256": check["catalog_sha256"], "catalog_version": catalog_version(catalog),
                     "code_sha256": code, "plan_sha256": file_sha256(args.plan), "commit": first_commit(state), "state": str(state),
                     "rows": [{**row, "planned_blocks": row["blocks"], "blocks": resolved_words(row, facts)} for row in plan["rows"]]}
    write_if_changed(state / "PLAN.json", json_text(resolved_plan))
    write_if_changed(state / "CHECK.json", json_text(check))
    write_if_changed(state / "CHECK-ALL.md", all_markdown(catalog, facts, all_verdicts(facts, CHECK_SIZES)))
    predictions = {entry["slug"]: entry for entry in check["rows"]}
    for row in resolved_plan["rows"]:
        if predictions[row["slug"]]["predicted"] == NOT_APPLICABLE and not (state / "rows" / f"{row['slug']}.json").is_file():
            write_whole(state / "rows" / f"{row['slug']}.json", json_text(entry_of(row, predictions[row["slug"]], NOT_APPLICABLE, None, predictions[row["slug"]]["why"], state)))
    rebuild(state)
    to_run = [row for row in resolved_plan["rows"] if predictions[row["slug"]]["predicted"] != NOT_APPLICABLE]
    return {"state": str(state), "first": [row["slug"] for row in to_run if not row["init"]], "second": [row["slug"] for row in to_run if row["init"]]}


def matched(prediction, outcome, code):
    """Whether a row did what the check said: ran where it said runs, refused for the code it
    said where it said refused; None for a row not run."""
    if outcome in (TO_COME, NOT_APPLICABLE):
        return None
    if prediction["predicted"] == RUNS:
        return outcome == RAN
    return prediction["predicted"] == REFUSED and outcome == REFUSED and code == prediction["code"]


def wandb_urls(run_dir):
    """The row's W&B runs, as the sync (wandb-sync.json) or a live start (wandb-mode.json) left them."""
    urls = set()
    sync, modes = run_dir / "wandb-sync.json", run_dir / "wandb-mode.json"
    with_files = [read_json(path) for path in (sync, modes) if path.is_file()]
    for found in with_files:
        urls |= set(found.get("urls", [])) | set(found.get("online_urls", []))
        urls |= {note.get("url") for note in found.values() if isinstance(note, dict) and note.get("url")}
    return sorted(url for url in urls if isinstance(url, str))


def run_numbers(run_dir):
    """What a row's folder says of it: its run id, its training crops, its best validation
    accuracy and its test accuracy over all levels, each None where the folder has none."""
    numbers = {"run_id": None, "train_crops": None, "validation_accuracy": None, "test_accuracy": None, "wandb": []}
    try:
        if (run_dir / "RUN.json").is_file():
            numbers["run_id"] = read_json(run_dir / "RUN.json").get("run_id")
        if (run_dir / "train" / "checkpoint.json").is_file():
            facts = read_json(run_dir / "train" / "checkpoint.json")
            numbers["train_crops"] = (facts.get("counts") or {}).get("train")
            numbers["validation_accuracy"] = facts.get("validation_accuracy")
        if (run_dir / "evaluate" / "results.json").is_file():
            rows = read_json(run_dir / "evaluate" / "results.json").get("rows", [])
            headline = next((r for r in rows if r.get("measure") == "accuracy" and r.get("stratum") == "all levels"), None)
            if headline and headline.get("total"):
                numbers["test_accuracy"] = headline["correct"] / headline["total"]
        numbers["wandb"] = wandb_urls(run_dir)
    except (OSError, ValueError, AttributeError, TypeError, KeyError) as error:
        print(f"block_sweep: {run_dir}: a record not read ({error})", file=sys.stderr)
    return numbers


def entry_of(row, prediction, outcome, code, why, state):
    """A row's entry of results.json: the plan's row, the check's prediction, what came of it and
    the numbers its folder holds."""
    return {"slug": row["slug"], "role": row["role"], "size": row["size"], "blocks": row["blocks"], "predicted": prediction["predicted"],
            "predicted_code": prediction["code"], "predicted_why": prediction["why"], "outcome": outcome, "code": code, "why": why,
            "matched": matched(prediction, outcome, code), **run_numbers(Path(state) / row["slug"])}


def lines_after_last_attempt(path):
    """A step's log as its last attempt wrote it: the flow marks a step run again with a line of
    ===, and only what follows the last such line is this attempt's."""
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    marks = [i for i, line in enumerate(lines) if line.startswith("=== ")]
    return lines[marks[-1] + 1:] if marks else lines


def code_of(line):
    return next((code for code, words in REFUSALS.items() if words in line), None)


def observed(state, slug, returncode):
    """What came of a row: ran where the flow finished and the evaluation wrote its results;
    refused where the trainer's own refusal (its line "train: ...", in a step the flow says
    exited) or the flow's ("flow: ...") says the words of a refusal code; failed otherwise."""
    run_dir = Path(state) / slug
    if returncode == 0 and (run_dir / "evaluate" / "results.json").is_file():
        return RAN, None, "the flow trained and evaluated it"
    flow_lines = [line for line in lines_after_last_attempt(Path(state) / f"{slug}.flow.log") if line.startswith("flow: ")]
    step_exited = any(re.match(r"flow: (train|evaluate) exited", line) for line in flow_lines)
    train_lines = [line for line in lines_after_last_attempt(run_dir / "train.log") if line.startswith("train: ")] if step_exited else []
    for line in train_lines[-1:] + flow_lines[-1:]:
        code = code_of(line)
        if code:
            return REFUSED, code, line
    said = (train_lines or flow_lines or [f"the flow exited {returncode} and wrote no evaluation"])[-1]
    return FAILED, None, said


def row_flow_command(state, plan, row, args, files):
    """tools/flow.py's command for one row, in its slug's folder under the state."""
    words = [sys.executable, str(ROOT / "tools" / "flow.py"), "run", "--catalog", str(Path(args.catalog).resolve()), "--out", str(state),
             "--slug", row["slug"], "--mode", "local", "--environment", args.environment, "--epochs", str(plan["epochs"]),
             "--seed", str(plan["seed"]), "--size", str(row["size"])]
    if row["weights"]:
        words += ["--weights", files[row["weights"]]]
    if row["init"]:
        words += ["--init", str(Path(state) / row["init"] / "train" / "best.pt")]
    return words + [word for block in row["blocks"] for word in ("--block", block)]


def drop_epoch_weights(run_dir):
    """A row that ran keeps best.pt, which a warm start reads, and drops each epoch's weights, so
    a plan of many rows stays small on the volume."""
    for weights in sorted((run_dir / "train" / "epochs").glob("*.pt")):
        weights.unlink()


class RowFault(Exception):
    """A row that could not be run or recorded: the flow treats it as a fault and retries it."""


def refuse_another_catalog(state, plan, catalog):
    """The state is named for its catalog's sha256 and PLAN.json records it, so a row given any
    other file is refused before it trains, rather than landing one catalog's result under
    another catalog's path."""
    given = Path(catalog)
    digest = file_sha256(given) if given.is_file() else None
    if digest != plan["catalog_sha256"]:
        found = f"sha256 {digest[:12]}" if digest else "no file there"
        raise RowFault(f"{state}: --catalog {catalog} ({found}) is not the catalog the state was prepared for, {plan['catalog_file']} (sha256 {plan['catalog_sha256'][:12]})")


def refuse_a_held_folder(outcome, why):
    """A row the flow would not run because its folder holds another run is a fault, not a
    result: the flow touched nothing, so the entry that run left stands rather than turning
    failed with its numbers, and the sweep stops, saying what to do."""
    if outcome == FAILED and HELD_FOLDER.search(why):
        raise RowFault(f"{why}; a sweep with another --environment or other --weights bytes takes a smoke root of its own (--out)")


def command_row(args):
    state = Path(args.state)
    try:
        plan, check = read_json(state / "PLAN.json"), read_json(state / "CHECK.json")
    except (OSError, ValueError) as error:
        raise RowFault(f"{state}: no PLAN.json and CHECK.json to run a row from ({error}); run prepare first") from error
    row = next((r for r in plan["rows"] if r["slug"] == args.slug), None)
    prediction = next((r for r in check["rows"] if r["slug"] == args.slug), None)
    if row is None or prediction is None:
        raise RowFault(f"{state}: the plan holds no row {args.slug}")
    if args.epochs and args.epochs != plan["epochs"]:
        raise RowFault(f"{state}: its rows train for {plan['epochs']} epochs, not {args.epochs}; prepare with --epochs {args.epochs} for a state of its own")
    refuse_another_catalog(state, plan, args.catalog)
    files = weights_files(args.weights)
    if prediction["predicted"] == NOT_APPLICABLE:
        entry = entry_of(row, prediction, NOT_APPLICABLE, None, prediction["why"], state)
    elif row["weights"] and row["weights"] not in files:
        raise RowFault(f"{args.slug} starts from {row['weights']}'s ImageNet file: give --weights {row['weights']}=FILE")
    else:
        with (state / f"{args.slug}.flow.log").open("w", encoding="utf-8") as log:
            done = subprocess.run(row_flow_command(state, plan, row, args, files), cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False)
        outcome, code, why = observed(state, args.slug, done.returncode)
        refuse_a_held_folder(outcome, why)
        if outcome == RAN and not args.keep_epoch_weights:
            drop_epoch_weights(state / args.slug)
        entry = entry_of(row, prediction, outcome, code, why, state)
    write_whole(state / "rows" / f"{args.slug}.json", json_text(entry))
    rebuild(state)
    return entry


def to_come(row, prediction):
    return {"slug": row["slug"], "role": row["role"], "size": row["size"], "blocks": row["blocks"], "predicted": prediction["predicted"],
            "predicted_code": prediction["code"], "predicted_why": prediction["why"], "outcome": TO_COME, "code": None, "why": "",
            "matched": None, "run_id": None, "train_crops": None, "validation_accuracy": None, "test_accuracy": None, "wandb": []}


def counts_of(entries):
    outcomes = [entry["outcome"] for entry in entries]
    return {"rows": len(entries), "ran": outcomes.count(RAN), "refused": outcomes.count(REFUSED), "not_applicable": outcomes.count(NOT_APPLICABLE),
            "failed": outcomes.count(FAILED), "to_come": outcomes.count(TO_COME), "mismatched": sum(entry["matched"] is False for entry in entries)}


def results_of(state):
    """results.json's data from PLAN.json, CHECK.json and the rows recorded under rows/."""
    plan, check = read_json(state / "PLAN.json"), read_json(state / "CHECK.json")
    predictions = {entry["slug"]: entry for entry in check["rows"]}
    recorded = {}
    for path in sorted((state / "rows").glob("*.json")):
        try:
            recorded[path.stem] = read_json(path)
        except (OSError, ValueError) as error:
            print(f"block_sweep: {path}: not read ({error}); its row counts as to come", file=sys.stderr)
    entries = [recorded.get(row["slug"]) or to_come(row, predictions[row["slug"]]) for row in plan["rows"]]
    return {"plan": plan["plan"], "state": str(state), "commit": plan["commit"], "code_sha256": plan.get("code_sha256"),
            "catalog": plan["catalog_file"], "catalog_sha256": plan["catalog_sha256"], "catalog_version": plan["catalog_version"],
            "updated_at": now(), "counts": counts_of(entries), "rows": entries}


def number_text(value):
    return "-" if value is None else f"{value:.3f}"


def matched_word(entry):
    return {True: "matched", False: "mismatched"}.get(entry["matched"], "-")


def reason_of(entry, limit=None):
    """Why a row did not run as a run does, for the pages a person reads: the check's words for a
    row not applicable, the tool's for one refused or failed, on one line and at most `limit`
    characters; "-" for a row that ran or is to come."""
    if entry["outcome"] not in (NOT_APPLICABLE, REFUSED, FAILED) or not entry.get("why"):
        return "-"
    text = " ".join(str(entry["why"]).split()).replace("|", "/")
    return text if limit is None or len(text) <= limit else text[: limit - 3] + "..."


def progress_row(entry):
    """A row's line of PROGRESS.txt: its slug, its outcome and whether it matched, the fields
    status selects on; then a refused row's code, a word of REFUSALS that quotes nothing; then, for
    a row not applicable, refused or failed, the start of why after "why:", the marker status
    judges it by."""
    why = reason_of(entry, PROGRESS_WHY)
    code = f" {entry['code']}" if entry.get("code") else ""
    return f"row {entry['slug']} {entry['outcome'].replace(' ', '-')} {matched_word(entry)}{code}" + ("" if why == "-" else f" why: {why}")


def results_markdown(results):
    counts = results["counts"]
    head = (f"{counts['rows']} rows: {counts['ran']} ran, {counts['refused']} refused, {counts['not_applicable']} not applicable, {counts['failed']} failed,"
            f" {counts['to_come']} to come; " + (f"{counts['mismatched']} DID NOT DO WHAT THE CHECK PREDICTED." if counts["mismatched"] else "every row run so far did what the check predicted."))
    out = [f"# Smoke plan {results['plan']}", "", head, "",
           f"State {results['state']}; commit {results['commit'][:12]}, code {(results.get('code_sha256') or 'not recorded')[:12]};"
           f" catalog {results['catalog']} (version {results['catalog_version']},"
           f" sha256 {results['catalog_sha256'][:12]}); updated {results['updated_at']}.", "",
           "| row | role | crop | blocks | predicted | outcome | matched | training crops | validation | test | W&B | why |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for e in results["rows"]:
        predicted = e["predicted"] + (f" ({e['predicted_code']})" if e["predicted_code"] else "")
        outcome = e["outcome"] + (f" ({e['code']})" if e["code"] else "")
        crops = "-" if e["train_crops"] is None else str(e["train_crops"])
        out.append(f"| {e['slug']} | {e['role']} | {e['size']} | {' '.join(e['blocks']) or 'version 1'} | {predicted} | {outcome} | {matched_word(e)} | {crops} |"
                   f" {number_text(e['validation_accuracy'])} | {number_text(e['test_accuracy'])} | {' '.join(e['wandb']) or '-'} | {reason_of(e)} |")
    return "\n".join(out) + "\n"


def progress_text(results):
    """PROGRESS.txt, for bash on the login node, which runs no python: the counts on one line,
    then a line a row, then the W&B links, at most PROGRESS_LINES lines in all."""
    c = results["counts"]
    lines = [f"plan {results['plan']} state {results['state']} rows {c['rows']} ran {c['ran']} refused {c['refused']} not_applicable {c['not_applicable']}"
             f" failed {c['failed']} to_come {c['to_come']} mismatched {c['mismatched']} updated {results['updated_at']}"]
    lines += [progress_row(e) for e in results["rows"]]
    lines += [f"wandb {url}" for e in results["rows"] for url in e["wandb"]]
    return "\n".join(lines[:PROGRESS_LINES]) + "\n"


def rebuild(state):
    """results.json, RESULTS.md and PROGRESS.txt again from the plan and every row recorded, under
    the state's lock, so two rows finishing together each leave the other's entry in."""
    state = Path(state)
    with (state / ".lock").open("a", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        results = results_of(state)
        write_whole(state / "results.json", json_text(results))
        write_whole(state / "RESULTS.md", results_markdown(results))
        write_whole(state / "PROGRESS.txt", progress_text(results))
    return results


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    plan_p = sub.add_parser("plan")
    plan_p.add_argument("--catalog", required=True)
    plan_p.add_argument("--out", required=True)
    plan_p.add_argument("--epochs", type=int, required=True)
    plan_p.add_argument("--seed", type=int, default=1)
    plan_p.add_argument("--hours", type=float, default=4.0)
    plan_p.add_argument("--weights", action="append", default=[], metavar="[ARCHITECTURE=]FILE",
                        help="an architecture's ImageNet file, once per architecture the sweep names; a bare file is resnet18's")
    plan_p.add_argument("--base", action="append", default=[], metavar="KEY=VALUE")
    plan_p.add_argument("--vary", action="append", default=[], metavar="KEY=V1/V2")
    compare_p = sub.add_parser("compare")
    compare_p.add_argument("runs", nargs="+")
    compare_p.add_argument("--by", choices=["accuracy", "balanced-accuracy"], default="accuracy")
    ledger_p = sub.add_parser("ledger")
    ledger_p.add_argument("folder")
    ledger_p.add_argument("--by", choices=["accuracy", "balanced-accuracy"], default="accuracy")
    sub.add_parser("parts")
    add_smoke_commands(sub)
    return parser.parse_args(argv)


def add_smoke_commands(sub):
    """The block smoke test's commands (#252)."""
    weights_help = "ARCHITECTURE=FILE, the ImageNet file of each architecture a row starts from"
    cover_p = sub.add_parser("cover", help="the covering set as a plan file")
    cover_p.add_argument("--name", required=True)
    cover_p.add_argument("--catalog", required=True, help="synthetic, v1 or with:<source>")
    cover_p.add_argument("--epochs", type=int, default=3)
    cover_p.add_argument("--seed", type=int, default=1)
    cover_p.add_argument("--strict", action="store_true", help="every pair of values of every two parts (32 cover rows)")
    trials_p = sub.add_parser("trials", help="the six trials as a plan file")
    trials_p.add_argument("--catalog", default="v1")
    trials_p.add_argument("--epochs", type=int, default=20)
    trials_p.add_argument("--seed", type=int, default=1)
    check_p = sub.add_parser("check", help="what the trainer will do with each combination, from the catalog's facts, training nothing")
    check_p.add_argument("--catalog", required=True)
    which = check_p.add_mutually_exclusive_group(required=True)
    which.add_argument("--plan", help="a plan file")
    which.add_argument("--all", action="store_true", help="every named combination of the blocks")
    check_p.add_argument("--weights", action="append", default=[], metavar="ARCHITECTURE=FILE", help=weights_help)
    check_p.add_argument("--sizes", default=",".join(map(str, CHECK_SIZES)), help="the crop sizes --all decides, comma-separated, of 32, 64, 96 and 128")
    check_p.add_argument("--json", action="store_true")
    synthetic_p = sub.add_parser("synthetic", help="build the synthetic plan's catalog once")
    synthetic_p.add_argument("--into", required=True)
    synthetic_p.add_argument("--frames", type=int, default=600)
    synthetic_p.add_argument("--cases", type=int, default=40)
    synthetic_p.add_argument("--test-frames", type=int, default=100)
    synthetic_p.add_argument("--unlabelled-frames", type=int, default=200)
    synthetic_p.add_argument("--seed", type=int, default=1)
    prepare_p = sub.add_parser("prepare", help="a plan's state folder for one code, plan and catalog")
    prepare_p.add_argument("--plan", required=True)
    prepare_p.add_argument("--catalog", required=True)
    prepare_p.add_argument("--out", required=True, help="the smoke root")
    prepare_p.add_argument("--weights", action="append", default=[], metavar="ARCHITECTURE=FILE", help=weights_help)
    prepare_p.add_argument("--epochs", type=int, default=0, help="epochs per row in place of the plan's, in a state folder of their own")
    state_p = sub.add_parser("state", help="the state folder prepare makes for these words, making nothing")
    state_p.add_argument("--plan", required=True)
    state_p.add_argument("--catalog", required=True)
    state_p.add_argument("--out", required=True, help="the smoke root")
    state_p.add_argument("--epochs", type=int, default=0, help="epochs per row in place of the plan's, as prepare takes it")
    row_p = sub.add_parser("row", help="run one row of a state's plan and record what came of it")
    row_p.add_argument("--state", required=True)
    row_p.add_argument("--slug", required=True)
    row_p.add_argument("--catalog", required=True)
    row_p.add_argument("--environment", default="train-gpu")
    row_p.add_argument("--epochs", type=int, default=0, help="the state's; another count is refused")
    row_p.add_argument("--weights", action="append", default=[], metavar="ARCHITECTURE=FILE", help=weights_help)
    row_p.add_argument("--keep-epoch-weights", action="store_true", help="keep train/epochs/*.pt of a row that ran")
    results_p = sub.add_parser("results", help="results.json, RESULTS.md and PROGRESS.txt again from a state's rows")
    results_p.add_argument("state")


def smoke_command(args):
    """The text one smoke command prints, or None where the command is not one of them."""
    if args.command == "cover":
        return json_text(cover_plan(args.name, args.catalog, args.epochs, args.seed, args.strict))
    if args.command == "trials":
        return json_text(trials_plan(args.catalog, args.epochs, args.seed))
    if args.command == "check":
        return command_check(args)
    if args.command == "synthetic":
        found = synthetic_catalog(args.into, args.frames, args.cases, args.test_frames, args.unlabelled_frames, args.seed)
        return json.dumps(found, sort_keys=True) + "\n"
    if args.command == "prepare":
        return json.dumps(command_prepare(args), sort_keys=True) + "\n"
    if args.command == "state":
        return f"{state_of(args, plan_of(args.plan))[0]}\n"
    if args.command == "results":
        return json.dumps({"results": str(Path(args.state) / "results.json"), "counts": rebuild(args.state)["counts"]}, sort_keys=True) + "\n"
    return None


def main(argv=None):
    args = parse_args(argv)
    if args.command == "row":
        return main_row(args)
    try:
        said = smoke_command(args)
        if said is not None:
            print(said, end="", flush=True)
        elif args.command == "parts":
            print(parts_table())
        elif args.command == "plan":
            print(json.dumps(plan(args), indent=1))
        elif args.command == "ledger":
            print(table(ledger(args.folder, args.by)))
        else:
            print(table(compare(args.runs, args.by)))
    except (BlockError, OSError, KeyError, StopIteration, json.JSONDecodeError) as error:
        print(f"block_sweep: {error}", file=sys.stderr)
        return 1
    return 0


def main_row(args):
    """`row`, whose exit says whether the row was recorded: 0 whatever came of it, 2 where it could
    not be run or recorded, which the sweep flow treats as a fault and retries."""
    try:
        print(json.dumps(command_row(args), sort_keys=True), flush=True)
    except (RowFault, BlockError, OSError, KeyError, ValueError) as error:
        print(f"block_sweep: row {args.slug}: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
