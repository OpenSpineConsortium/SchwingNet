"""Run the v1 flow, locally or as Slurm jobs, and write the record every number cites.

Usage (from the verification environment, or any python with the package on its path):
    python tools/flow.py plan --mode slurm --epochs 20 --hours 4
    python tools/flow.py run --catalog <catalog.sqlite> --out <runs folder> --mode local \
        --epochs 3 --seed 1 [--max-frames 400] [--size 64] [--weights <file>] [--slug <name>]
    python tools/flow.py record --run <runs folder>/<run id> --into docs/research/v1-demo/runs

Every run also writes PROVENANCE.json and PROVENANCE.md (tools/licences.py) before its first step:
each source of the catalog with its licence, its class and its frames in each part, and the run's
own class and the recipes it fits; `--recipe NAME` refuses a catalog with a source the recipe in
data/recipes/ does not take, so a catalog meant for a commercial network is cut first with
`python3 tools/licences.py derive`, and the ledger row names the class and the recipe.

A run is refused from a dirty tree, since its record names the commit; the run id is the hash of
the digest of the code the run executes (tools/run_code.py, kind row), the catalog's sha256 and
the run's configuration (below), so the same configuration of the same code on the same catalog
always names the same run, also on a later commit that changed none of that code, which carries
the run on; RUN.json is written before the first step, so the trainer and the evaluator stamp
their numbers from it and never type a fact of their own, and the commit it names is the one the
run started on. The steps are the split check (SQL over the catalog, here), training
and evaluation, each one process, each timed and recorded as a job with what it cost, in local
mode as a subprocess in the train-cpu environment and in slurm mode as one job each in
train-gpu, queued through hpcworker's job submit as the gpu class (issue #77), polled no faster than once a minute (grid rule 7). `record` copies the run's small
files, never the checkpoint, into the research folder with one ledger row, so the repository
holds what ran and what it cost beside the numbers. After the last step the run's report is
written beside its files (tools/report.py): the CLAIM 2024 and REFORMS items each answered from the
run's files or the declared study, and the licences of the data it read.

The run's configuration is every argument that changes what the steps compute (the stage, the
epochs, the seed, the crop size, the frame cap, the blocks, augment's changes and the sources in
one order whatever order they were named in, the sha256 of the weights or of the parent it
starts from, the recipe and the environment) and nothing that only says where or how
long it runs; it is written to CONFIGURATION.json and its sha256 names the run with the code's
digest and the catalog (schwingnet.flow.configured_run_id), so no clock enters the name. The run's folder is
<out>/<run id>, or <out>/<slug> with `--slug`, so a sweep finds each row's folder by the row's
name. Started again on a folder that holds its record, the flow runs only what is left: nothing
where the run wrote FINISHED.json, its last file, after its report; only the last push, the
ledger row where the ledger has none for the run, the report and FINISHED.json where the
evaluation ended and the run was cut after it; the evaluation alone where training wrote its
checkpoint.json and the best.pt it names by its sha256, training carried on from its last epoch
(`tools/train.py --resume`) where it left train/last.pt, else training from the start; RUN.json
keeps its first start and its earlier jobs and gains a job for each step run now. A folder that
holds another run's record is refused and left as it is. The flow writes its own files whole,
flushed to the disk, and renames them into place, so a start cut while it writes one leaves the
one before, and a folder a start left before its record, holding no more than the split check
and this configuration, is started again. A start holds the run's folder by an exclusive lock on
<run>/.lock from before it reads the folder to its end, and the trainer holds train/ the same way,
so a second start of the same run while the first still runs, which would otherwise take a run in
progress for a cut one, is refused in words that name the holder, and runs and writes nothing.

Before the first step the run's witness.json is written (tools/witness.py): the frozen list in
data/witness/ where the repository has one, checked against this catalog, else the frames chosen
from it now; a run started again keeps the list its folder holds, so every step of one run draws
the same frames. After the last step the flow pushes the steps' offline Weights and Biases files
from where it runs (tools/wandb_log.py sync; on the grid that is the login node, which has a
route out), and its last line and the ledger say whether they were pushed, never silently.
`record --freeze` makes the run's witness list the frozen one, for the first run on real frames
only.
"""

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from schwingnet.blocks import AUGMENT, BlockError, as_record, words_of  # noqa: E402
from schwingnet.blocks import parse as parse_blocks  # noqa: E402
from schwingnet.flow import JobClass, JobRecord, JobSpec, RunRecord, Stage, Step, configured_run_id, ledger_row  # noqa: E402
from schwingnet.slurm import elapsed_seconds, is_finished, sbatch_script, submitted_of  # noqa: E402


def _load_witness():
    """tools/witness.py by its file: putting this folder on the path would let tools/profile.py
    shadow the standard library for whatever imports next, as tools/train.py explains."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("schwingnet_tool_witness", ROOT / "tools" / "witness.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_witness = _load_witness()
FROZEN, WitnessError, for_run = _witness.FROZEN, _witness.WitnessError, _witness.for_run


def _load_licences():
    """tools/licences.py by its file, for the reason _load_witness gives."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("schwingnet_tool_licences", ROOT / "tools" / "licences.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_report():
    """tools/report.py by its file, for the reason _load_witness gives."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("schwingnet_tool_report", ROOT / "tools" / "report.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_run_code():
    """tools/run_code.py by its file, for the reason _load_witness gives."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("schwingnet_tool_run_code", ROOT / "tools" / "run_code.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_licences = _load_licences()
_report = _load_report()
_run_code = _load_run_code()

VERSION_NAME = re.compile(r"catalog-(\d{6})-[0-9a-f]{12}\.sqlite$")
LEDGER_HEADER = (
    "| date | run | mode | activity | commit | catalog | cost | jobs | verified |\n"
    "|---|---|---|---|---|---|---|---|---|"
)
PERSON_LEAK = "SELECT person FROM item GROUP BY person HAVING COUNT(DISTINCT part) > 1"
FRAME_LEAK = "SELECT sha256 FROM item GROUP BY sha256 HAVING COUNT(DISTINCT part) > 1"
MIN_POLL = 60
# A run folder's name where the caller gives one: a sweep's row names it, so the folder is found by
# the row; no slash, no leading dot, so it stays one folder inside --out.
SLUG = re.compile(r"[a-z0-9][a-z0-9.-]{0,79}")
FINISHED, EVALUATED, TRAINED, RESUMED, RESTARTED = "finished", "evaluated", "trained", "resumed", "restarted"
# The run's last file, written once everything after its evaluation is done (finish).
FINISHED_MARK = "FINISHED.json"
# The file a start holds the run's folder by for as long as it runs (held).
LOCK = ".lock"


class FlowError(Exception):
    """What stops the flow with a reason a person reads."""


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout.strip()


def tree_state():
    """The commit and whether the tree is clean; a dirty tree is refused by RunRecord."""
    return git("rev-parse", "HEAD"), git("status", "--porcelain") == ""


def code_state():
    """The digest of the code a run executes (tools/run_code.py, kind row), which names the run
    with its catalog and configuration, so a commit that changes none of that code names the
    same run and a start on it carries the run on."""
    try:
        return _run_code.digest("row")
    except _run_code.RunCodeError as error:
        raise FlowError(f"the run's code cannot be named: {error}") from error


def catalog_facts(catalog):
    """The catalog's sha256 and its version number, 1 for a file outside a versioned store."""
    path = Path(catalog)
    if not path.is_file():
        raise FlowError(f"{catalog}: no catalog there")
    found = VERSION_NAME.search(path.name)
    return hashlib.sha256(path.read_bytes()).hexdigest(), int(found.group(1)) if found else 1


def split_disjoint(catalog):
    """Whether no person and no frame sits in two parts; the check the run's record cites."""
    db = sqlite3.connect(f"file:{catalog}?mode=ro", uri=True)
    try:
        persons = [row[0] for row in db.execute(PERSON_LEAK)]
        frames = [row[0] for row in db.execute(FRAME_LEAK)]
    finally:
        db.close()
    return {"disjoint": not persons and not frames, "persons_in_two_parts": persons, "frames_in_two_parts": frames}


def now():
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parsed_blocks(words):
    """The trainer's blocks from the command's words, refused here before any step starts: a word
    that names no block, and any space, since the command is split on spaces; in one order
    (canonical_blocks) whatever order the words named them in."""
    if any(any(c.isspace() for c in word) for word in words):
        raise FlowError("a block is KEY=VALUE with no space in it")
    try:
        return canonical_blocks(parse_blocks(words))
    except BlockError as error:
        raise FlowError(f"blocks: {error}") from error


def canonical_blocks(blocks):
    """The blocks with augment's changes in the order schwingnet.blocks lists them, the order the
    trainer applies them in whatever order they are named, and the sources sorted, since the
    trainer keeps a crop by whether its source is named: two orders that train alike then name
    one run, and a run started with one and carried on with the other hands the trainer the same
    words, which its --resume holds to."""
    augment = tuple(name for name in AUGMENT if name in blocks.augment)
    return replace(blocks, augment=augment, sources=tuple(sorted(blocks.sources)))


def block_words(words):
    """The trainer's blocks as the command passes them: checked, in one order, and only those
    that are not version 1's (schwingnet.blocks.words_of)."""
    return "".join(f" --block {word}" for word in words_of(parsed_blocks(words)))


def file_sha256(path, what, missing="no file there"):
    """The sha256 of a file the run starts from, so the configuration names its bytes and not
    where it lies; refused in words where there is none."""
    path = Path(path)
    if not path.is_file():
        raise FlowError(f"{what} {path}: {missing}")
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def run_configuration(args):
    """What the run computes, as CONFIGURATION.json records it and its hash names the run: the
    blocks as the checkpoint writes them, keyed by block and with augment and sources in one
    order (canonical_blocks), so the order of the --block words, or of the names in one, changes
    nothing, and the files it starts from by their bytes. The mode, the partition, the hours, the CPUs and the
    poll only say where and how long it runs, so they are left out, and a run started on another
    node is still the same run."""
    return {
        "stage": args.stage,
        "epochs": args.epochs,
        "seed": args.seed,
        "size": args.size,
        "max_frames": args.max_frames,
        "blocks": as_record(parsed_blocks(args.block)),
        "weights_sha256": file_sha256(args.weights, "--weights") if args.weights else None,
        # Said as the trainer says it, which would refuse the same missing parent a step later.
        "init_sha256": file_sha256(args.init, "--init", "no parent checkpoint there") if args.init else None,
        "recipe": args.recipe,
        "environment": args.environment,
    }


def configuration_sha256(configuration):
    """The configuration's hash, over its one canonical text: sorted keys and no spaces."""
    text = json.dumps(configuration, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def configuration_text(configuration):
    """CONFIGURATION.json's text: the configuration sorted, one key a line."""
    return json.dumps(configuration, indent=1, sort_keys=True) + "\n"


def write_configuration(run_dir, configuration):
    """CONFIGURATION.json, written once: a run started again has the same configuration, since
    its hash is in the run's name."""
    path = Path(run_dir) / "CONFIGURATION.json"
    if not path.is_file():
        write_whole(path, configuration_text(configuration))


def write_whole(path, text):
    """A file written beside its place, on the disk, and renamed into it, as tools/train.py writes
    its own, so a start cut while writing it, by a kill, a full volume or the death of its node,
    leaves the one before and never half of one: RUN.json is written again after every step, and a
    half one would make the folder no run's for good."""
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    synced(temporary)
    os.replace(temporary, path)
    synced(path.parent)


def synced(*paths):
    """Each file or folder flushed to the disk, a folder for the names in it: a rename can reach
    the disk before the bytes it names, so a node that dies after it may leave the file short or
    with stretches of zeros, where a start that is killed leaves the node to write them."""
    for path in paths:
        handle = os.open(path, os.O_RDONLY)
        try:
            os.fsync(handle)
        finally:
            os.close(handle)


def job_specs(args, resume=False):
    """What each step asks for; the plan a person approves before any job is submitted. resume
    carries training on from the epoch its last.pt holds, with the same arguments otherwise."""
    train_command = (
        f"python tools/train.py --catalog {args.catalog} --out {{run_dir}} --epochs {args.epochs}"
        f" --seed {args.seed} --size {args.size}"
        + (f" --weights {args.weights}" if args.weights else "")
        + (f" --init {args.init}" if args.init else "")
        + (f" --max-frames {args.max_frames}" if args.max_frames else "")
        + block_words(args.block)
        + (" --resume" if resume else "")
    )
    evaluate_command = f"python tools/evaluate.py --catalog {args.catalog} --run {{run_dir}}"
    gpus = 1 if args.mode == "slurm" else 0
    job_class = JobClass.GPU if gpus else JobClass.CPU
    common = {"job_class": job_class, "partition": args.partition, "cpus": args.cpus, "memory_gb": args.memory_gb, "gpus": gpus, "environment": args.environment}
    return (
        JobSpec(step=Step.TRAIN, command=train_command, hours=args.hours, **common),
        JobSpec(step=Step.EVALUATE, command=evaluate_command, hours=max(0.25, args.hours / 4), **common),
    )


def run_local(job, run_dir, again=None):
    """One step as a subprocess in the locked environment; what it cost is measured, not estimated.
    A step run again in a run started before adds to its log under a line that says so, so the
    output of the attempt that was cut short is kept above the one that carries it on."""
    command = ["pixi", "run", "--locked", "-e", job.environment, *job.command.format(run_dir=run_dir).split()]
    started = time.monotonic()
    with (Path(run_dir) / f"{job.step.value}.log").open("a" if again else "w", encoding="utf-8") as log:
        if again:
            log.write(f"\n=== {job.step.value} run again at {now()}, the run's folder held: {again} ===\n")
            log.flush()
        done = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False)
    return JobRecord(step=job.step, job_id=f"local-{os.getpid()}-{job.step.value}", partition="local", qos=None, hours_requested=job.hours, seconds_used=int(time.monotonic() - started) + 1, gpus=0, preemptions=0, exit_code=done.returncode)


def sacct(job_id):
    """State, elapsed and exit code of a job's main step, from sacct."""
    out = subprocess.run(["sacct", "-j", job_id, "-n", "-P", "-X", "--format=State,Elapsed,ExitCode"], capture_output=True, text=True, check=False).stdout
    lines = [line for line in out.splitlines() if line.strip()]
    if not lines:
        return None
    state, elapsed, exit_code = lines[-1].split("|")[:3]
    return state, elapsed, int(exit_code.split(":")[0]), sum(1 for line in lines if line.startswith("REQUEUED"))


def hpcworker():
    """The hpcworker to run: HPCWORKER, as the grid gate hands it, else the one on PATH."""
    found = os.environ.get("HPCWORKER") or shutil.which("hpcworker")
    if not found:
        raise FlowError("slurm mode queues through hpcworker's job submit: set HPCWORKER or put hpcworker on PATH")
    return found


def submit_call(job, run_dir, script):
    """hpcworker's job submit for one step, in the run directory, never requeued: a requeued
    step would train a second time beside the first."""
    narrowed = ["--partition", job.partition] if job.partition else []
    gpus = ["--gpus", str(job.gpus)] if job.gpus else []
    return ["bash", hpcworker(), "job", "submit", "--project", "schwingnet", "--name", f"flow_{job.step.value}", "--class", job.job_class.value, *narrowed, *gpus, "--no-requeue", "--dir", str(run_dir), "--", str(script)]


def run_slurm(job, run_dir, poll):
    """One step as one job through hpcworker's job submit, its shape asked with --check first, then
    polled no faster than once a minute until sacct calls it finished."""
    script = Path(run_dir) / f"{job.step.value}.sbatch"
    script.write_text(sbatch_script(job.model_copy(update={"command": job.command.format(run_dir=run_dir)}), str(ROOT)), encoding="utf-8")
    call = submit_call(job, run_dir, script)
    checked = subprocess.run([*call[:4], "--check", *call[4:]], capture_output=True, text=True, check=False)
    if checked.returncode != 0:
        raise FlowError(f"hpcworker refused {script.name}: {(checked.stdout + checked.stderr).strip()}")
    submitted = subprocess.run(call, capture_output=True, text=True, check=False)
    answer = submitted_of(submitted.stdout)
    if answer is None:
        raise FlowError(f"hpcworker refused {script.name}: {(submitted.stdout + submitted.stderr).strip()}")
    job_id, partition, qos = answer
    print(json.dumps({"step": job.step.value, "job_id": job_id, "partition": partition, "submitted": now()}), flush=True)
    while True:
        time.sleep(max(MIN_POLL, poll))
        answer = sacct(job_id)
        if answer and is_finished(answer[0]):
            break
    state, elapsed, exit_code, preemptions = answer
    return JobRecord(step=job.step, job_id=job_id, partition=partition, qos=qos, hours_requested=job.hours, seconds_used=elapsed_seconds(elapsed), gpus=job.gpus, preemptions=preemptions, exit_code=exit_code if state.startswith("COMPLETED") else max(1, exit_code))


def write_record(run_dir, record):
    write_whole(Path(run_dir) / "RUN.json", record.model_dump_json(indent=1) + "\n")


def append_ledger(path, record, activity, verified):
    """One more row in a ledger, the header once, the whole text written again beside it and
    renamed into place (write_whole), so a write cut by a kill or a full volume leaves the ledger
    as it was, every earlier row with it, where writing it in place would empty it first."""
    path = Path(path)
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    write_whole(path, ledger_text(text, ledger_row(record, activity, verified)))


def ledger_text(text, row):
    """The ledger's text with one more row: the header first where the text does not begin with
    it, as a ledger the code before this one cut while writing it was left, and the row on a line
    of its own."""
    if not text.startswith(LEDGER_HEADER + "\n"):
        text = LEDGER_HEADER + "\n" + text
    if not text.endswith("\n"):
        text += "\n"
    return text + row + "\n"


@contextlib.contextmanager
def ledger_held(path):
    """The ledger beside the runs held by one writer at a time: an exclusive lock on LEDGER.md.lock
    beside it, waited for, since every row of a sweep's state finishes into one LEDGER.md, side by
    side where the sweep runs rows together, and each writer reads the ledger and writes it again.
    The lock is a file of its own, never renamed, since the ledger is renamed into place and a lock
    on it would be on the file a rename replaces; a writer holds it for one read and one write."""
    path = Path(path)
    with path.with_name(path.name + ".lock").open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def add_ledger_row(path, record, activity, verified):
    """The run's row in the ledger beside the runs, once: under the ledger's lock (ledger_held), so
    two runs that finish together each find the other's row, and only where the ledger has none
    for the run. Refused in words where the volume will not take it, the ledger left as it was, and
    since FINISHED.json is written after it, the next start writes the row."""
    try:
        with ledger_held(path):
            if not ledger_holds(path, record.run_id):
                append_ledger(path, record, activity, verified)
    except OSError as error:
        raise FlowError(f"{path}: the run's row could not be written ({error}); the ledger is kept as it was, and the next start of the run writes the row") from error


def ledger_holds(path, run_id):
    """Whether the ledger has a row for the run already, its second cell the run's id: a run cut
    after its row and started again writes none of its own."""
    path = Path(path)
    if not path.is_file():
        return False
    cells = ([cell.strip() for cell in line.strip().strip("|").split("|")] for line in path.read_text(encoding="utf-8").splitlines())
    return any(len(row) > 1 and row[1] == run_id for row in cells)


def start_record(args, configuration=None):
    """RUN.json before the first step: the facts from the tree, the catalog and the split check,
    named by the code's digest, the catalog and the configuration's hash; the commit is the one
    it starts on, which a start on a later commit with the same code keeps (run_held)."""
    configuration = run_configuration(args) if configuration is None else configuration
    commit, clean = tree_state()
    code = code_state()
    sha256, version = catalog_facts(args.catalog)
    check = split_disjoint(args.catalog)
    named = configuration_sha256(configuration)
    try:
        return RunRecord(run_id=configured_run_id(code, sha256, named), code_commit=commit, clean_tree=clean, catalog_version=version, catalog_sha256=sha256, split_disjoint=check["disjoint"], stage=Stage(args.stage), seed=args.seed, epochs=args.epochs, parent_weights=configuration["weights_sha256"], configuration_sha256=named, code_sha256=code, started_at=now(), mode=args.mode), check
    except ValueError as error:
        raise FlowError(f"refused: {error}; split check {json.dumps(check)}") from error


def checked_slug(slug):
    """The run folder's name a caller gives, refused in words unless it is one plain folder name."""
    if slug is not None and not SLUG.fullmatch(slug):
        raise FlowError(f"--slug {slug!r}: a slug is lower-case letters, digits, dots and hyphens, starts with a letter or a digit and is at most 80 characters")
    return slug


def earlier_record(run_dir, record):
    """The record the run's folder already holds, or None where it holds none: the same run,
    started before, whose name must be this run's, or the folder is another run's and is refused
    before anything in it is touched."""
    run_file = Path(run_dir) / "RUN.json"
    if not run_file.is_file():
        return None
    try:
        held = json.loads(run_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise FlowError(f"{run_file}: not a run record ({error}); nothing is touched") from error
    held_id = held.get("run_id") if isinstance(held, dict) else None
    if held_id != record.run_id:
        raise FlowError(f"{run_dir} holds run {held_id}, and this configuration of this code on this catalog names run {record.run_id}; nothing is touched")
    try:
        return RunRecord.model_validate(held)
    except ValueError as error:
        raise FlowError(f"{run_file}: {error}; nothing is touched") from error


def what_is_left(run_dir, held):
    """What a run started before still needs, from its folder, the furthest step first: nothing
    once it wrote FINISHED.json, its last file; what comes after the evaluation (finish) where the
    record holds an evaluation that ended well and its results are there; the evaluation where
    training ended (trained), training carried on where it left train/last.pt, else all of it."""
    run_dir = Path(run_dir)
    if (run_dir / FINISHED_MARK).is_file():
        return FINISHED
    evaluated = any(job.step is Step.EVALUATE and job.exit_code == 0 for job in held.jobs)
    if evaluated and (run_dir / "evaluate" / "results.json").is_file():
        return EVALUATED
    if trained(run_dir / "train"):
        return TRAINED
    if (run_dir / "train" / "last.pt").is_file():
        return RESUMED
    return RESTARTED


def trained(train_dir):
    """Whether training ended: checkpoint.json, the trainer's last file, reads as a record that
    names the sha256 of the best.pt beside it, as the evaluator holds it to (tools/train.py's
    checkpoint_facts). One a node that died left short, or one beside other weights than the ones
    it names, is no end, since taking it for one sent every start to an evaluation that refuses
    it; the run trains again instead, on from last.pt where the trainer left one, and the trainer
    sets such a record aside before it trains."""
    try:
        facts = json.loads((train_dir / "checkpoint.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    named = facts.get("checkpoint_sha256") if isinstance(facts, dict) else None
    best = train_dir / "best.pt"
    return isinstance(named, str) and best.is_file() and file_sha256(best, "best.pt") == named


# What a start leaves before it writes RUN.json, each written whole (write_whole), so a start cut
# there leaves at most these and their temporary files; CONFIGURATION.json only where it is this
# configuration's (new_folder).
BEFORE_RECORD = ("split-check.json", "CONFIGURATION.json", "RUN.json")


def new_folder(run_dir, configuration):
    """A new run's folder, there or not yet, checked before anything is written in it. One a start
    left before it wrote the record holds at most the split check and the configuration, which
    must be this run's, their temporary files and the lock, all written again; anything else there
    is no run of this flow's, so it is refused and left as it is."""
    run_dir = Path(run_dir)
    if not run_dir.exists():
        return
    strays = sorted(p.name for p in run_dir.iterdir() if not left_by_a_start(p.name)) if run_dir.is_dir() else [run_dir.name]
    if strays:
        raise FlowError(f"{run_dir} holds {', '.join(strays[:5])} and no RUN.json, so it is no run of this flow's; nothing is touched")
    held = run_dir / "CONFIGURATION.json"
    if held.is_file() and held.read_text(encoding="utf-8") != configuration_text(configuration):
        raise FlowError(f"{run_dir} holds CONFIGURATION.json of another configuration and no RUN.json, so it is no start of this run's; nothing is touched")


def left_by_a_start(name):
    """Whether a file of this name is one a start writes before RUN.json, its temporary file, or
    the lock a start holds the folder by."""
    return name == LOCK or name.removesuffix(".tmp") in BEFORE_RECORD


def holder_words():
    """Who holds the run's folder, as its lock file says it to the next start refused: the
    process, the machine, the Slurm job where there is one, and since when."""
    job = os.environ.get("SLURM_JOB_ID")
    return f"pid {os.getpid()} on {socket.gethostname()}" + (f", Slurm job {job}" if job else "") + f", since {now()}"


@contextlib.contextmanager
def held(run_dir):
    """The run's folder held for this start alone, to its end: an exclusive lock on <run>/.lock,
    taken without waiting. The run's name holds no clock, so two starts of one configuration of
    one code on one catalog name one folder, the v1 driver's and an experiment's asking for version
    1's training among them, and a run in progress would look like a cut one and be carried on
    beside itself. The kernel drops a flock when its process ends, by a kill too, so a cut start
    leaves no lock behind, and CephFS, the lab volume, honours it across nodes, as
    grid/03-catalog.sbatch's lock relies on. The folder is made here, so the lock has a place."""
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / LOCK
    with path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            holder = path.read_text(encoding="utf-8").strip() or "which has not yet written who it is"
            raise FlowError(f"{run_dir} is in progress: another start of this run holds {path} ({holder}); nothing is touched, and that start carries the run on") from error
        except OSError as error:
            raise FlowError(f"{path}: cannot be locked ({error}), so whether another start runs here cannot be told; nothing is touched") from error
        yield handle


def claim(lock):
    """The lock file says who holds it, for the next start it refuses: written only by a start
    that goes on to run something, so a finished run's folder is read and never written."""
    lock.truncate(0)
    lock.write(holder_words() + "\n")
    lock.flush()


def steps_for(args, reused):
    """The steps a run still runs, by what its folder held."""
    train, evaluate = job_specs(args, resume=reused == RESUMED)
    return (evaluate,) if reused == TRAINED else (train, evaluate)


def licence_record(catalog, recipe):
    """The run's training data provenance, before anything is written: a catalog with a source no
    licence entry covers, or one outside the recipe the run names, is refused here."""
    try:
        return _licences.run_provenance(catalog, recipe)
    except _licences.LicenceError as error:
        raise FlowError(f"licences: {error}") from error


class Start(NamedTuple):
    """What a start of the run works out before it takes the run's folder."""

    record: RunRecord
    check: dict
    configuration: dict
    licences: dict


def command_run(args):
    slug = checked_slug(args.slug)
    configuration = run_configuration(args)
    record, check = start_record(args, configuration)
    licences = licence_record(args.catalog, args.recipe)
    run_dir = Path(args.out) / (slug or record.run_id)
    # Read before the lock, so a folder that is another run's, refused here, gets no lock file of
    # this one's; what the folder holds is read again under the lock, and that reading decides.
    if earlier_record(run_dir, record) is None:
        new_folder(run_dir, configuration)
    with held(run_dir) as lock:
        return run_held(args, run_dir, Start(record, check, configuration, licences), lock)


def run_held(args, run_dir, start, lock):
    """The run, once its folder is held for this start alone (held)."""
    record, configuration, licences = start.record, start.configuration, start.licences
    held = earlier_record(run_dir, record)
    reused = what_is_left(run_dir, held) if held else None
    said = {"run_id": record.run_id, "run_dir": str(run_dir), "mode": args.mode, **({"reused": reused} if reused else {})}
    if reused == FINISHED:
        # Finished before: nothing runs, nothing is written, and no second ledger row.
        print(json.dumps(said), flush=True)
        return 0
    claim(lock)
    if reused == EVALUATED:
        # Evaluated before and cut after: only what comes after the evaluation.
        print(json.dumps(said), flush=True)
        return finish(args, run_dir, held, licences)
    if held:
        record = held
    else:
        new_folder(run_dir, configuration)
    write_whole(run_dir / "split-check.json", json.dumps(start.check, indent=1) + "\n")
    write_configuration(run_dir, configuration)
    jobs = [*record.jobs, JobRecord(step=Step.SPLIT_CHECK, job_id=f"local-{os.getpid()}-split-check", partition="runner", qos=None, hours_requested=0.01, seconds_used=1, gpus=0, preemptions=0, exit_code=0)]
    record = record.model_copy(update={"jobs": tuple(jobs)})
    write_record(run_dir, record)
    _licences.write_provenance(run_dir, licences)
    print(json.dumps({"licence": licences["run_class"], "commercial_use": licences["commercial_use"], "fits_recipes": licences["fits_recipes"]}), flush=True)
    keep_witness(run_dir, args.catalog, record.catalog_sha256)
    print(json.dumps(said), flush=True)
    for job in steps_for(args, reused):
        done = run_local(job, run_dir, reused) if args.mode == "local" else run_slurm(job, run_dir, args.poll)
        jobs.append(done)
        record = record.model_copy(update={"jobs": tuple(jobs)})
        write_record(run_dir, record)
        print(json.dumps(done.model_dump()), flush=True)
        # Each step's W&B run is pushed as soon as the step ends, so the website shows training
        # before evaluation starts, even from a node that could only log offline.
        step_push = push_wandb(run_dir, args.environment)
        print(f"{job.step.value}: {step_push}", file=sys.stderr if "NOT" in step_push else sys.stdout, flush=True)
        if done.exit_code != 0:
            where = f"{run_dir}/{job.step.value}.log" if args.mode == "local" else f"hpcworker's log of job {done.job_id}"
            raise FlowError(f"{job.step.value} exited {done.exit_code}; see {where}")
    return finish(args, run_dir, record, licences)


def finish(args, run_dir, record, licences):
    """What a run does once its evaluation is recorded: the last W&B push, its ledger row, its
    report, and last of all FINISHED.json, so a run cut anywhere before it, at a push that hung or
    by a time limit, is finished by its next start, which writes the ledger row only where the
    ledger has none for the run."""
    activity = f"{record.stage.value} stage, {record.epochs} epochs, seed {record.seed}" + (f", {args.max_frames} crops per part" if args.max_frames else "") + licence_words(licences)
    pushed = push_wandb(run_dir, args.environment)
    add_ledger_row(Path(args.out) / "LEDGER.md", record, activity, f"evaluate/results.md from the test part; split-check.json disjoint; {pushed}")
    print(pushed, file=sys.stderr if "NOT" in pushed else sys.stdout, flush=True)
    report = write_report(run_dir)
    print(report, flush=True)
    write_whole(Path(run_dir) / FINISHED_MARK, json.dumps({"run_id": record.run_id, "finished_at": now(), "wandb": pushed, "report": report}, indent=1) + "\n")
    return 0


def licence_words(licences):
    """The ledger's few words of the run's data licence: its class and the recipe that cut it."""
    recipe = licences["recipe"]
    return f", data licence {licences['run_class']}" + (f" (recipe {recipe['name']})" if recipe else "")


def write_report(run_dir):
    """The run's CLAIM, REFORMS and licence report, written after the last step (tools/report.py);
    its last line says how many items are still missing, so a gap is seen, never silent."""
    _report.write(run_dir)
    gaps = _report.missing_items(run_dir)
    return f"report: {run_dir}/REPORT.md, " + (f"{len(gaps)} items missing" if gaps else "complete")


def keep_witness(run_dir, catalog, catalog_sha256):
    """The witness list a run started before already holds is kept as it is, so a step run again
    draws the frames the steps before it drew; a new run writes its own."""
    listing = Path(run_dir) / "witness.json"
    if not listing.is_file():
        write_witness(run_dir, catalog, catalog_sha256)
        return
    try:
        document = json.loads(listing.read_text(encoding="utf-8"))
        print(json.dumps({"witness": "kept", "frames": len(document["frames"]), "missing": document["missing"]}), flush=True)
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise FlowError(f"{listing}: the run's witness list cannot be read ({error}); it is kept, not chosen again, so fix or remove it by hand") from error


def write_witness(run_dir, catalog, catalog_sha256):
    """The run's witness list, before any step, so both steps draw the same frames."""
    try:
        document, how = for_run(catalog, catalog_sha256)
    except WitnessError as error:
        raise FlowError(f"witness frames: {error}") from error
    write_whole(Path(run_dir) / "witness.json", json.dumps(document, indent=1) + "\n")
    print(json.dumps({"witness": how, "frames": len(document["frames"]), "missing": document["missing"]}), flush=True)


def push_wandb(run_dir, environment=None):
    """Push the steps' offline W&B runs from here; the one line that says whether they went."""
    # The small telemetry environment, never train-gpu, whose CUDA build the login node may refuse.
    command = ["pixi", "run", "--locked", "-e", "telemetry", "python", "tools/wandb_log.py", "sync", "--run", str(run_dir)]
    done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    lines = [line for line in done.stdout.splitlines() if line.startswith("W&B")]
    said = " ".join((done.stderr.strip().splitlines() or [""])[-1].split()).replace("|", "/")[:200]
    return lines[-1] if lines else f"W&B NOT PUSHED: the sync step exited {done.returncode}: {said}"


KEPT = ("RUN.json", "CONFIGURATION.json", "PROVENANCE.json", "PROVENANCE.md", "split-check.json", "witness.json", "wandb-sync.json", "train/metrics.jsonl", "train/checkpoint.json", "train/MODEL.md", "train/accuracy.png", "evaluate/results.json", "evaluate/results.md", "evaluate/confusion.png", "evaluate/per-level.png", "evaluate/witness-test.jsonl", "evaluate/latency.json", "REPORT.md", "claim.json", "reforms.json")
# Of each witness frame, the strip and the animation; the sheets of the first and last epoch; the
# latency thread's arms. Never a checkpoint, and never every epoch's picture, which W&B holds.
KEPT_GLOBS = ("train/witness/frames/*/strip.jpg", "train/witness/frames/*/anim.gif", "train/witness/frames/sheet-*.jpg", "evaluate/witness/frames/*/strip.jpg", "evaluate/witness/frames/*/anim.gif", "evaluate/witness/frames/sheet-*.jpg", "latency/*.json")


def command_record(args):
    """Copy a run's small files into the research folder, with one ledger row; never the checkpoint."""
    source = Path(args.run)
    record = RunRecord.model_validate_json((source / "RUN.json").read_text(encoding="utf-8"))
    target = Path(args.into) / record.run_id
    names = [*KEPT, *(str(p.relative_to(source)) for pattern in KEPT_GLOBS for p in sorted(source.glob(pattern)))]
    for name in names:
        if (source / name).is_file():
            (target / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / name, target / name)
    if args.freeze:
        freeze_witness(source / "witness.json")
    strips = sorted((source / "train" / "witness").glob("epoch-*.png"))
    for strip in (strips[:1] + strips[-1:]) if strips else []:
        (target / "train" / "witness").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(strip, target / "train" / "witness" / strip.name)
    append_ledger(Path(args.into).parent / "LEDGER.md", record, args.activity, args.verified)
    print(json.dumps({"recorded": str(target), "files": sorted(str(p.relative_to(target)) for p in target.rglob("*") if p.is_file())}))
    return 0


def freeze_witness(listing):
    """The run's witness list becomes the repository's frozen one; an existing one is kept."""
    if FROZEN.is_file():
        raise FlowError(f"{FROZEN.relative_to(ROOT)} is frozen already; a new list is a pull request that removes it first, on purpose")
    if not listing.is_file():
        raise FlowError(f"{listing}: the run has no witness list to freeze")
    FROZEN.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(listing, FROZEN)


def command_plan(args):
    for job in job_specs(args):
        print(json.dumps(job.model_dump(mode="json")))
    return 0


def add_run_arguments(parser):
    parser.add_argument("--catalog", default="<catalog>")
    parser.add_argument("--mode", choices=["local", "slurm"], default="local")
    parser.add_argument("--stage", default=Stage.LEVEL.value, choices=[s.value for s in Stage])
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--size", type=int, default=64)
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument("--weights", default=None)
    parser.add_argument("--init", default=None, help="a parent checkpoint to start the trainer from: an incremental run")
    parser.add_argument("--recipe", default=None, help="refuse the run unless every source it trains on is one this recipe in data/recipes/ takes")
    parser.add_argument("--hours", type=float, default=4.0, help="the training job's wall time")
    parser.add_argument("--block", action="append", default=[], metavar="KEY=VALUE", help="one building block for the trainer (src/schwingnet/blocks.py), passed to tools/train.py; none gives version 1's training")
    # A step names hpcworker's gpu class and never a QoS: the site profile gives the GPU partitions,
    # the first with room, and the QoS they take, without which Slurm refused a GPU job (issue #74).
    # Only slurm mode submits; local mode runs each step here.
    parser.add_argument("--partition", default=None, help="slurm mode: one of the gpu class's partitions, else any of them")
    parser.add_argument("--cpus", type=int, default=4)
    parser.add_argument("--memory-gb", type=int, default=32)
    parser.add_argument("--environment", default=None, help="train-cpu locally, train-gpu on the grid")
    parser.add_argument("--poll", type=int, default=MIN_POLL, help="seconds between sacct reads, never under 60")


def parse(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    add_run_arguments(sub.add_parser("plan"))
    run_p = sub.add_parser("run")
    add_run_arguments(run_p)
    run_p.add_argument("--out", required=True)
    run_p.add_argument("--slug", default=None, help="the run folder's name under --out, in place of the run id: lower-case letters, digits, dots and hyphens, at most 80")
    record_p = sub.add_parser("record")
    record_p.add_argument("--run", required=True)
    record_p.add_argument("--into", required=True)
    record_p.add_argument("--activity", required=True)
    record_p.add_argument("--verified", required=True)
    record_p.add_argument("--freeze", action="store_true", help="make this run's witness list the frozen one (the first run on real frames)")
    args = parser.parse_args(argv)
    if getattr(args, "environment", None) is None and hasattr(args, "mode"):
        args.environment = "train-cpu" if args.mode == "local" else "train-gpu"
    if hasattr(args, "mode") and args.mode == "local":
        args.partition = None
    return args


def main(argv=None):
    args = parse(argv)
    try:
        return {"plan": command_plan, "run": command_run, "record": command_record}[args.command](args)
    except (FlowError, subprocess.CalledProcessError) as error:
        print(f"flow: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
