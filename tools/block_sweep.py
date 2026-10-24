"""List the trainer's building blocks, plan a sweep over them, and compare the runs made, on validation only.

Usage:
    python3 tools/block_sweep.py parts
    python3 tools/block_sweep.py plan --catalog <catalog.sqlite> --out <runs folder> --epochs 20 \
        --seed 1 --hours 4 [--weights [ARCHITECTURE=]<file> ...] [--base KEY=VALUE ...] \
        --vary KEY=V1/V2 [--vary ...]
    python3 tools/block_sweep.py compare <run dir> [<run dir> ...] [--by accuracy|balanced-accuracy]
    python3 tools/block_sweep.py ledger <runs folder> [--by accuracy|balanced-accuracy]

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
"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from schwingnet.blocks import ARCHITECTURE, DEFAULT, BlockError, from_record, parts, sweep, words_of  # noqa: E402

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
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        if args.command == "parts":
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


if __name__ == "__main__":
    raise SystemExit(main())
