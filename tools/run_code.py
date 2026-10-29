"""The code each kind of run executes, and the digest that names a run by it.

Usage:
    python3 tools/run_code.py digest KIND     the kind's digest, 64 hex digits
    python3 tools/run_code.py files KIND      the files it covers, one a line

A run is named by the code it runs and not by the commit it started on (issue #252, finding 27). The
grid's gate brings main in before every word it takes, main merges many times a day, and most merges
change nothing a run executes: of the 88 merges from 2026-10-22 to 2026-10-25, 10 changed a file a
sweep runs and 6 one a bank or catalog build runs, against 51 that changed something under tools/,
src/, grid/ or flows/, or pixi.lock. A run named by its commit could not be carried on once main had
moved, so a sweep cut at its time limit and sent again trained every row it had finished a second
time, and a bank or catalog job sent again started over. Named by this digest, a run started again
after a merge that changes none of its files is the same run and is carried on, while a change to
any of them names a new one.

KINDS lists, for each kind, the files whose bytes the digest covers: what its steps run, the rules
they import and the locked environment, for bank and catalog the wrappers every tool of their steps
runs through on the grid, and for the stages that read them the registry and the split files,
whole folders where a name ends in "/". The files are the tracked ones, read from the
working tree; a run refuses a dirty tree elsewhere (schwingnet.flow.RunRecord), so for a run that
is the code git holds. LEFT_OUT names, file by file, what a kind's code reaches and its digest
leaves out, with the reason. tests/test_run_code.py follows each kind's imports, the tools it
loads and the scripts it names and fails on a file in neither list, so a new import is a choice
someone made and never an accident.

The kinds: `row` is one run of tools/flow.py, named by schwingnet.flow.configured_run_id; `state`
is a sweep's state folder, tools/block_sweep.py's with the rows it starts; `sweep`, `v1`,
`experiment`, `latency`, `bank`, `catalog`, `drr_gap` and `drr_seg` are the Metaflow flows of
flows/, named by the launcher's key (schwingnet.pipeline.run_key), `v1` the version 1 run of
tools/flow.py as a launched flow, `experiment` one requested combination of it, `latency` one job
of the latency word on a run's checkpoint, the last two the DRR domain-gap study's parts and its
MOOSE masks.

A copy of the code that `git archive` made, as the DRR domain-gap study's prepare makes one so that
no later step reads the checkout while the gate moves it, holds no .git; it holds COPY_RECORD
instead, the commit on its first line and then every file the copy holds, one a line, as
`git ls-tree -r --name-only` lists them. Where a folder holds that record and no .git, its files
are read from the record in place of `git ls-files`, so the copy's digest is that of its commit's
files, the one the checkout gives at that commit, and flows/launch.py reads the commit from it.
"""

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# A copy's record (above): flows/launch.py's COPY_RECORD is the same name.
COPY_RECORD = "COPY.txt"
COMMIT = re.compile(r"[0-9a-f]{40}")

ENVIRONMENT = ("pixi.toml", "pixi.lock")
CONTRACTS = ("vendor/beethoven-qa/src/beethoven_qa/__init__.py", "vendor/beethoven-qa/src/beethoven_qa/contracts.py")
ROW = (*ENVIRONMENT, *CONTRACTS,
       "src/schwingnet/__init__.py", "src/schwingnet/blocks.py", "src/schwingnet/catalog.py", "src/schwingnet/flow.py",
       "src/schwingnet/slurm.py", "src/schwingnet/witness.py",
       "tools/evaluate.py", "tools/flow.py", "tools/train.py", "tools/train_blocks.py", "tools/witness.py")
STATE = (*ROW, "tools/block_sweep.py")
# What a bank or catalog build reads besides its words: tools/catalog.py loads the registry and the
# frozen test persons and the split rule, which decide each frame's part.
SPLIT_RULES = ("data/registry/", "data/splits/")
# On the grid every tool a bank or catalog step runs goes through the PYDRV grid/gate.sh exports,
# grid/bin/train-cpu-python, which picks the environment the tool runs in and execs grid/box.sh,
# which runs it in the container or, inside it already, as it is (the second review of #252,
# finding 4).
PYDRV = ("grid/bin/train-cpu-python", "grid/box.sh")
STAGE = (*ENVIRONMENT, *CONTRACTS, *SPLIT_RULES, *PYDRV, "src/schwingnet/__init__.py", "src/schwingnet/catalog.py", "tools/catalog.py")
# The DRR domain-gap study's code (tools/domain_gap.py, docs/research/drr-domain-gap/), which its
# parts and its MOOSE masks run: the tool, the neighbours it loads by path (tool("..."): the
# statistics and the renderer, which loads tools/render_blocks.py by path in turn), the package
# modules they import, the groups table it reads and the two wrappers every call goes through,
# grid/box.sh and grid/venv.sh, which make and enter the study's environment.
DRR_STUDY = (*ENVIRONMENT, *CONTRACTS, "src/schwingnet/__init__.py", "src/schwingnet/domain_gap.py",
             "src/schwingnet/render_blocks.py", "src/schwingnet/segmenters.py", "tools/domain_gap.py",
             "tools/domain_gap_stats.py", "tools/flexray_render.py", "tools/render_blocks.py", "data/domain_gap/",
             "grid/box.sh", "grid/venv.sh")
KINDS = {
    "row": ROW,
    "state": STATE,
    "sweep": (*STATE, "flows/sweep.py", "flows/stage.py", "flows/stage_registry.py"),
    "v1": (*ROW, "flows/v1.py", "flows/flow_tool.py", "flows/stage.py", "flows/stage_registry.py"),
    "experiment": (*ROW, "flows/experiment.py", "flows/flow_tool.py", "flows/stage.py", "flows/stage_registry.py"),
    # One job of the latency word on a run's checkpoint: tools/latency.py loads tools/train.py for the
    # model and its crops, so it reaches every file a row runs, and the two tools and their rules.
    "latency": (*ROW, "flows/latency.py", "flows/flow_tool.py", "flows/stage.py", "flows/stage_registry.py",
                "tools/latency.py", "tools/sweep.py", "src/schwingnet/latency.py", "src/schwingnet/sweep.py"),
    "bank": (*STAGE, "flows/bank.py", "grid/02-bank-ingest.sbatch", "tools/bank.py", "tools/ingest.py"),
    "catalog": (*STAGE, "flows/catalog.py", "grid/03-catalog.sbatch"),
    "drr_gap": (*DRR_STUDY, "data/splits/test-persons.json", "grid/drr-gap.sbatch", "flows/drr_gap.py", "flows/stage.py",
                "flows/stage_registry.py"),
    "drr_seg": (*DRR_STUDY, "data/splits/test-persons.json", "grid/drr-seg.sbatch", "flows/drr_seg.py", "flows/stage.py",
                "flows/stage_registry.py"),
    # The FluXray reproduction's stages (docs/research/flux-realism/PREREG.md): the flow, the tool
    # each step runs, the rules it imports and the label names the render reads.
    "realism": (*ENVIRONMENT, *CONTRACTS, "src/schwingnet/__init__.py", "src/schwingnet/realism.py", "flows/realism.py",
                "flows/stage.py", "flows/stage_registry.py", "tools/realism.py", "grid/enhance-pet-labels.json"),
}

NAMES_THE_RUN = "names the run: the files it lists are the digest, so a change to the lists changes the digest by itself"
LAUNCHES = "starts or carries on the flow's run, which it names by this digest, and computes nothing the run keeps"
ROW_LEFT_OUT = {
    "tools/run_code.py": NAMES_THE_RUN,
    "tools/licences.py": "writes the run's provenance, again at every start before its first step, so a start runs the version it has",
    "tools/report.py": "writes the run's report from its files after the last step, at every start that gets there",
    "tools/wandb_log.py": "sends the steps' telemetry to Weights and Biases and records nothing a number is computed from",
    "tools/ingest.py": "is named only in the trainer's words; the catalog a run reads is named by its own sha256",
    "src/schwingnet/segmenters.py": "names the segmenter block's values and the label alphabets the pack stage reads;"
    " no training step reads it, and the catalog a run reads is named by its own sha256",
}
STATE_LEFT_OUT = {
    **ROW_LEFT_OUT,
    "tools/synthetic_bank.py": "makes the synthetic catalog, which the state names by its sha256 beside this digest",
    "tools/bank.py": "banks the synthetic catalog's frames, which the state names by its sha256",
    "tools/catalog.py": "builds the synthetic catalog, which the state names by its sha256",
}
# A stage's job script starts the launcher when Slurm runs it, and the flow's steps run the same
# script again for its body.
STAGE_LEFT_OUT = {
    "flows/launch.py": LAUNCHES,
    "grid/00-setup.sbatch": "is named only in grid/box.sh's refusal on a node with no container, which it builds once, before any job",
}
# What a launched flow keeps beside its work for the owner's rule of 2026-10-29 (flows/stage.py):
# the page it draws, and the launcher the registry's check names. The registry itself, which
# flows/stage_registry.py reads, is no part of a digest: the PREREG it names for the kind is in the
# launcher's key by its path and sha256, and a line added for another kind changes nothing a flow runs.
STAGE_PAGE_LEFT_OUT = {
    "flows/launch.py": LAUNCHES,
    "flows/stage_progress.py": "draws the run's progress page from the files the steps write; no step reads it back and no number comes from it",
}
# The study's parts and its masks: what the job script's driver and the flow's end run beside the work.
DRR_LEFT_OUT = {**STAGE_LEFT_OUT, **STAGE_PAGE_LEFT_OUT}
REPORTS_THE_STUDY = ("writes and checks the study's CLAIM and REFORMS report from the merge's record of the run, after its "
                     "last step, at every start that gets there; it computes nothing the study's numbers come from")
LEFT_OUT = {
    "row": ROW_LEFT_OUT,
    "state": STATE_LEFT_OUT,
    "sweep": {**STATE_LEFT_OUT, **STAGE_PAGE_LEFT_OUT},
    "v1": {**ROW_LEFT_OUT, **STAGE_PAGE_LEFT_OUT},
    "experiment": {**ROW_LEFT_OUT, **STAGE_PAGE_LEFT_OUT},
    "latency": {**ROW_LEFT_OUT, **STAGE_PAGE_LEFT_OUT},
    "bank": {**STAGE_LEFT_OUT, "grid/size-rule.sh": "admits the job under the size rule before the launcher starts, and no step of the flow runs it"},
    "catalog": STAGE_LEFT_OUT,
    "drr_gap": {**DRR_LEFT_OUT, "tools/report.py": REPORTS_THE_STUDY},
    "drr_seg": {**DRR_LEFT_OUT, "grid/run-platform-fetch.sh": "names MOOSE's model zips for the job's check of them before "
                "the launcher starts; no step of the flow runs it, and the zips are read by their bytes",
                "tools/report.py": "is named by flows/stage.py for a run's report, which the masks' flow never makes; the "
                "study's report is its merge's"},
    "realism": {**STAGE_PAGE_LEFT_OUT,
                "tools/report.py": "writes the run's CLAIM 2024 and REFORMS report from its files in the end step, after every number"},
}


class RunCodeError(Exception):
    """What stops a digest with a reason a person reads."""


def is_copy(root):
    """Whether the folder is a copy git archive made, with its record and no .git."""
    return (Path(root) / COPY_RECORD).is_file() and not (Path(root) / ".git").exists()


def copied(root):
    """A copy's record: the commit it was made at and the files it holds."""
    record = Path(root) / COPY_RECORD
    try:
        lines = record.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise RunCodeError(f"{record} cannot be read ({error}), so the copy's code cannot be named") from error
    if not lines or not COMMIT.fullmatch(lines[0]):
        raise RunCodeError(f"{record} names no commit on its first line, so the copy's code cannot be named")
    return lines[0], [line for line in lines[1:] if line]


def git_tracked(root, names):
    """The files git tracks under the names, in a checkout."""
    try:
        done = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--", *names], capture_output=True, text=True, check=False)
    except OSError as error:
        raise RunCodeError(f"git could not be run in {root}: {error}") from error
    if done.returncode != 0:
        raise RunCodeError(f"git ls-files in {root}: {done.stderr.strip()}")
    return [name for name in done.stdout.split("\0") if name]


def named_by(names, path):
    """Whether a path is one of the names, or lies under one that ends in "/", as git's pathspec reads them."""
    return any(path == name or (name.endswith("/") and path.startswith(name)) for name in names)


def files(kind, root=ROOT):
    """The tracked files a kind's digest covers, in path order; refused where a file the kind
    names alone is not tracked, so a renamed or deleted file never silently leaves a digest. In a
    copy (is_copy) the tracked files are those its record lists."""
    if kind not in KINDS:
        raise RunCodeError(f"no kind {kind!r}; the kinds are {', '.join(KINDS)}")
    names = KINDS[kind]
    listed = [path for path in copied(root)[1] if named_by(names, path)] if is_copy(root) else git_tracked(root, names)
    tracked = sorted(set(listed))
    missing = [name for name in names if not (name.endswith("/") or name in tracked)]
    if missing:
        raise RunCodeError(f"{kind}: {', '.join(missing)} not tracked in {root}, so its code cannot be named")
    return tracked


def digest(kind, root=ROOT):
    """The sha256 over the kind's name and each file's path and the sha256 of its bytes."""
    lines = [f"{kind}\n"]
    for name in files(kind, root):
        try:
            with (Path(root) / name).open("rb") as handle:
                lines.append(f"{name}\t{hashlib.file_digest(handle, 'sha256').hexdigest()}\n")
        except OSError as error:
            raise RunCodeError(f"{name}: cannot be read ({error}), so its code cannot be named") from error
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def parse(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("what", choices=("digest", "files"))
    parser.add_argument("kind", choices=tuple(KINDS))
    return parser.parse_args(argv)


def main(argv=None):
    args = parse(argv)
    try:
        print(digest(args.kind) if args.what == "digest" else "\n".join(files(args.kind)))
    except RunCodeError as error:
        print(f"run_code: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
