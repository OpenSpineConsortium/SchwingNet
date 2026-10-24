"""Plan a sweep over the trainer's building blocks, and compare the runs it made, on validation only.

Usage:
    python3 tools/block_sweep.py plan --catalog <catalog.sqlite> --out <runs folder> --epochs 20 \
        --seed 1 --hours 4 [--weights <file>] [--base KEY=VALUE ...] --vary KEY=V1/V2 [--vary ...]
    python3 tools/block_sweep.py compare <run dir> [<run dir> ...] [--by accuracy|balanced-accuracy]

The search an AutoML system makes over settings (docs/research/training-review.md) is, here, a
plan over the blocks of src/schwingnet/blocks.py: `plan` writes the tools/flow.py command of every
combination, the number of runs and the GPU-hours they would ask for, and starts nothing, since no
grid job is sent without the owner's word and the count. `vary` separates values with "/", so an
augment value keeps its commas: `--vary augment=none/box-jitter,intensity`.

`compare` reads each run's train/checkpoint.json and train/metrics.jsonl, never its evaluate/
folder: the runs are ranked by the validation part and its witness frames alone, so choosing among
them never reads a test person (docs/research/retraining-plan.md, section 4). The chosen run is
then evaluated once on the test part, as any run is.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from schwingnet.blocks import BlockError, from_record, sweep, words_of  # noqa: E402

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


def flow_command(args, blocks):
    words = words_of(blocks)
    return " ".join(
        ["python3 tools/flow.py run", f"--catalog {args.catalog}", f"--out {args.out}", "--mode slurm",
         f"--epochs {args.epochs}", f"--seed {args.seed}", f"--hours {args.hours}"]
        + ([f"--weights {args.weights}"] if args.weights else [])
        + [f"--block {word}" for word in words]
    )


def plan(args):
    runs = sweep(args.base, parse_vary(args.vary))
    commands = [flow_command(args, blocks) for blocks in runs]
    hours = len(runs) * (args.hours + EVALUATE_HOURS)
    return {
        "runs": len(runs),
        "jobs": 2 * len(runs),
        "gpu_hours_requested": hours,
        "note": "a plan only: nothing is submitted; each command is one run of tools/flow.py, two jobs (train, evaluate)",
        "commands": commands,
    }


def best_line(run_dir):
    """The run's blocks and the metrics line of the epoch its checkpoint names."""
    facts = json.loads((run_dir / "train" / "checkpoint.json").read_text(encoding="utf-8"))
    lines = [json.loads(line) for line in (run_dir / "train" / "metrics.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    best = next(line for line in lines if line["epoch"] == facts["epoch"])
    return from_record(facts.get("blocks")), best


def compare(run_dirs, by):
    rows = []
    for run_dir in map(Path, run_dirs):
        blocks, line = best_line(run_dir)
        witness = line.get("witness_validation")
        rows.append({
            "run": run_dir.name,
            "blocks": " ".join(words_of(blocks)) or "version 1 (no block named)",
            "epoch": line["epoch"],
            "accuracy": line["validation_accuracy"],
            "ci": line["validation_ci"],
            "n": line["validation_n"],
            "balanced_accuracy": line.get("validation_balanced_accuracy"),
            "witness": f"{witness[0]}/{witness[1]}" if witness else "not drawn",
        })
    key = "balanced_accuracy" if by == "balanced-accuracy" else "accuracy"
    rows.sort(key=lambda row: (row[key] is None, -(row[key] or 0.0)))
    return rows


def table(rows):
    out = ["| run | blocks | best epoch | validation | 95% interval | balanced | validation witness |", "|---|---|---|---|---|---|---|"]
    for row in rows:
        balanced = "not recorded" if row["balanced_accuracy"] is None else f"{row['balanced_accuracy']:.3f}"
        out.append(f"| {row['run']} | {row['blocks']} | {row['epoch']} | {row['accuracy']:.3f} (n={row['n']}) | {row['ci'][0]:.3f} to {row['ci'][1]:.3f} | {balanced} | {row['witness']} |")
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
    plan_p.add_argument("--weights", default=None)
    plan_p.add_argument("--base", action="append", default=[], metavar="KEY=VALUE")
    plan_p.add_argument("--vary", action="append", default=[], metavar="KEY=V1/V2")
    compare_p = sub.add_parser("compare")
    compare_p.add_argument("runs", nargs="+")
    compare_p.add_argument("--by", choices=["accuracy", "balanced-accuracy"], default="accuracy")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        if args.command == "plan":
            print(json.dumps(plan(args), indent=1))
        else:
            print(table(compare(args.runs, args.by)))
    except (BlockError, OSError, KeyError, StopIteration, json.JSONDecodeError) as error:
        print(f"block_sweep: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
