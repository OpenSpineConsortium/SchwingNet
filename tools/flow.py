"""Run the v1 flow, locally or as Slurm jobs, and write the record every number cites.

Usage (from the verification environment, or any python with the package on its path):
    python tools/flow.py plan --mode slurm --epochs 20 --hours 4
    python tools/flow.py run --catalog <catalog.sqlite> --out <runs folder> --mode local \
        --epochs 3 --seed 1 [--max-frames 400] [--size 64] [--weights <file>]
    python tools/flow.py record --run <runs folder>/<run id> --into docs/research/v1-demo/runs

A run is refused from a dirty tree, since its record names the commit; the run id is the hash of
the commit, the catalog's sha256 and the start, so no two runs share one; RUN.json is written
before the first step, so the trainer and the evaluator stamp their numbers from it and never
type a fact of their own. The steps are the split check (SQL over the catalog, here), training
and evaluation, each one process, each timed and recorded as a job with what it cost, in local
mode as a subprocess in the train-cpu environment and in slurm mode as one sbatch each in
train-gpu, polled no faster than once a minute (grid rule 7). `record` copies the run's small
files, never the checkpoint, into the research folder with one ledger row, so the repository
holds what ran and what it cost beside the numbers.

Before the first step the run's witness.json is written (tools/witness.py): the frozen list in
data/witness/ where the repository has one, checked against this catalog, else the frames chosen
from it now. After the last step the flow pushes the steps' offline Weights and Biases files from
where it runs (tools/wandb_log.py sync; on the grid that is the login node, which has a route
out), and its last line and the ledger say whether they were pushed, never silently. `record
--freeze` makes the run's witness list the frozen one, for the first run on real frames only.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from schwingnet.flow import JobRecord, JobSpec, RunRecord, Stage, Step, ledger_row, run_id  # noqa: E402
from schwingnet.slurm import elapsed_seconds, is_finished, job_id_of, sbatch_script  # noqa: E402
from witness import FROZEN, WitnessError, for_run  # noqa: E402

VERSION_NAME = re.compile(r"catalog-(\d{6})-[0-9a-f]{12}\.sqlite$")
LEDGER_HEADER = (
    "| date | run | mode | activity | commit | catalog | cost | jobs | verified |\n"
    "|---|---|---|---|---|---|---|---|---|"
)
PERSON_LEAK = "SELECT person FROM item GROUP BY person HAVING COUNT(DISTINCT part) > 1"
FRAME_LEAK = "SELECT sha256 FROM item GROUP BY sha256 HAVING COUNT(DISTINCT part) > 1"
MIN_POLL = 60


class FlowError(Exception):
    """What stops the flow with a reason a person reads."""


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout.strip()


def tree_state():
    """The commit and whether the tree is clean; a dirty tree is refused by RunRecord."""
    return git("rev-parse", "HEAD"), git("status", "--porcelain") == ""


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


def job_specs(args):
    """What each step asks for; the plan a person approves before any job is submitted."""
    train_command = (
        f"python tools/train.py --catalog {args.catalog} --out {{run_dir}} --epochs {args.epochs}"
        f" --seed {args.seed} --size {args.size}"
        + (f" --weights {args.weights}" if args.weights else "")
        + (f" --max-frames {args.max_frames}" if args.max_frames else "")
    )
    evaluate_command = f"python tools/evaluate.py --catalog {args.catalog} --run {{run_dir}}"
    gpus = 1 if args.mode == "slurm" else 0
    return (
        JobSpec(step=Step.TRAIN, command=train_command, partition=args.partition, qos=args.qos, cpus=args.cpus, memory_gb=args.memory_gb, gpus=gpus, hours=args.hours, environment=args.environment),
        JobSpec(step=Step.EVALUATE, command=evaluate_command, partition=args.partition, qos=args.qos, cpus=args.cpus, memory_gb=args.memory_gb, gpus=gpus, hours=max(0.25, args.hours / 4), environment=args.environment),
    )


def run_local(job, run_dir):
    """One step as a subprocess in the locked environment; what it cost is measured, not estimated."""
    command = ["pixi", "run", "--locked", "-e", job.environment, *job.command.format(run_dir=run_dir).split()]
    started = time.monotonic()
    with (Path(run_dir) / f"{job.step.value}.log").open("w", encoding="utf-8") as log:
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


def run_slurm(job, run_dir, poll):
    """One step as one sbatch, polled no faster than once a minute until sacct calls it finished."""
    script = Path(run_dir) / f"{job.step.value}.sbatch"
    script.write_text(sbatch_script(job.model_copy(update={"command": job.command.format(run_dir=run_dir)}), str(run_dir), str(ROOT)), encoding="utf-8")
    submitted = subprocess.run(["sbatch", str(script)], capture_output=True, text=True, check=False)
    job_id = job_id_of(submitted.stdout)
    if job_id is None:
        raise FlowError(f"sbatch refused {script.name}: {submitted.stderr.strip()}")
    print(json.dumps({"step": job.step.value, "job_id": job_id, "submitted": now()}), flush=True)
    while True:
        time.sleep(max(MIN_POLL, poll))
        answer = sacct(job_id)
        if answer and is_finished(answer[0]):
            break
    state, elapsed, exit_code, preemptions = answer
    return JobRecord(step=job.step, job_id=job_id, partition=job.partition, qos=job.qos, hours_requested=job.hours, seconds_used=elapsed_seconds(elapsed), gpus=job.gpus, preemptions=preemptions, exit_code=exit_code if state.startswith("COMPLETED") else max(1, exit_code))


def write_record(run_dir, record):
    (Path(run_dir) / "RUN.json").write_text(record.model_dump_json(indent=1) + "\n", encoding="utf-8")


def append_ledger(path, record, activity, verified):
    """One row per run in the ledger beside the runs; the header once."""
    path = Path(path)
    text = path.read_text(encoding="utf-8") if path.is_file() else LEDGER_HEADER + "\n"
    path.write_text(text + ledger_row(record, activity, verified) + "\n", encoding="utf-8")


def start_record(args):
    """RUN.json before the first step: the facts from the tree, the catalog and the split check."""
    commit, clean = tree_state()
    sha256, version = catalog_facts(args.catalog)
    check = split_disjoint(args.catalog)
    started = now()
    try:
        return RunRecord(run_id=run_id(commit, sha256, started), code_commit=commit, clean_tree=clean, catalog_version=version, catalog_sha256=sha256, split_disjoint=check["disjoint"], stage=Stage(args.stage), seed=args.seed, epochs=args.epochs, parent_weights=hashlib.sha256(Path(args.weights).read_bytes()).hexdigest() if args.weights else None, started_at=started, mode=args.mode), check
    except ValueError as error:
        raise FlowError(f"refused: {error}; split check {json.dumps(check)}") from error


def command_run(args):
    record, check = start_record(args)
    run_dir = Path(args.out) / record.run_id
    run_dir.mkdir(parents=True)
    (run_dir / "split-check.json").write_text(json.dumps(check, indent=1) + "\n", encoding="utf-8")
    write_record(run_dir, record)
    write_witness(run_dir, args.catalog, record.catalog_sha256)
    print(json.dumps({"run_id": record.run_id, "run_dir": str(run_dir), "mode": args.mode}), flush=True)
    jobs = [JobRecord(step=Step.SPLIT_CHECK, job_id=f"local-{os.getpid()}-split-check", partition="runner", qos=None, hours_requested=0.01, seconds_used=1, gpus=0, preemptions=0, exit_code=0)]
    for job in job_specs(args):
        done = run_local(job, run_dir) if args.mode == "local" else run_slurm(job, run_dir, args.poll)
        jobs.append(done)
        record = record.model_copy(update={"jobs": tuple(jobs)})
        write_record(run_dir, record)
        print(json.dumps(done.model_dump()), flush=True)
        if done.exit_code != 0:
            print(push_wandb(run_dir, args.environment), file=sys.stderr, flush=True)
            raise FlowError(f"{job.step.value} exited {done.exit_code}; see {run_dir}/{job.step.value}.log")
    activity = f"{record.stage.value} stage, {record.epochs} epochs, seed {record.seed}" + (f", {args.max_frames} crops per part" if args.max_frames else "")
    pushed = push_wandb(run_dir, args.environment)
    append_ledger(Path(args.out) / "LEDGER.md", record, activity, f"evaluate/results.md from the test part; split-check.json disjoint; {pushed}")
    print(pushed, file=sys.stderr if "NOT" in pushed else sys.stdout, flush=True)
    return 0


def write_witness(run_dir, catalog, catalog_sha256):
    """The run's witness list, before any step, so both steps draw the same frames."""
    try:
        document, how = for_run(catalog, catalog_sha256)
    except WitnessError as error:
        raise FlowError(f"witness frames: {error}") from error
    (Path(run_dir) / "witness.json").write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"witness": how, "frames": len(document["frames"]), "missing": document["missing"]}), flush=True)


def push_wandb(run_dir, environment):
    """Push the steps' offline W&B runs from here; the one line that says whether they went."""
    command = ["pixi", "run", "--locked", "-e", environment, "python", "tools/wandb_log.py", "sync", "--run", str(run_dir)]
    done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    lines = [line for line in done.stdout.splitlines() if line.startswith("W&B")]
    return lines[-1] if lines else f"W&B NOT PUSHED: the sync step exited {done.returncode}: {done.stderr.strip()[-200:]}"


KEPT = ("RUN.json", "split-check.json", "witness.json", "wandb-sync.json", "train/metrics.jsonl", "train/checkpoint.json", "train/MODEL.md", "train/accuracy.png", "evaluate/results.json", "evaluate/results.md", "evaluate/confusion.png", "evaluate/per-level.png", "evaluate/witness-test.jsonl", "evaluate/latency.json")
# Of each witness frame, the strip and the animation; the sheets of the first and last epoch; the
# latency thread's arms. Never a checkpoint, and never every epoch's picture, which W&B holds.
KEPT_GLOBS = ("train/witness/frames/*/strip.png", "train/witness/frames/*/anim.gif", "train/witness/frames/sheet-*.png", "evaluate/witness/frames/*/strip.png", "evaluate/witness/frames/*/anim.gif", "evaluate/witness/frames/sheet-*.png", "latency/*.json")


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
    parser.add_argument("--hours", type=float, default=4.0, help="the training job's wall time")
    parser.add_argument("--partition", default="gmsap")
    parser.add_argument("--qos", default=None)
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
        args.partition = "local"
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
