"""Evaluate a trained level stage on the catalog's test part and write every number with its stamp.

Usage (inside the train-cpu or train-gpu environment):
    python tools/evaluate.py --catalog <catalog.sqlite> --run <run dir> [--part test] [--device cpu]

The eval gate's rules (spine-program rule 5 and 6, beethoven-research REFORMS): a number is a
fraction with n, a 95 percent Wilson interval and the persons behind it, stamped with the run id,
the commit, the clean-tree flag and the catalog's sha256, all read from the run's RUN.json, which
tools/flow.py wrote from a clean tree. The test part is read once, here, after training is over;
the trainer never saw it. Beside the table the figures a reader checks: the confusion matrix and
the per-level accuracy with its intervals. The transitional stratum (T13, L6) is reported apart,
never pooled, as docs/research/retraining-plan.md asks.

The evaluator is the version boundary, so it is where the test witness frames are read
(docs/research/retraining-plan.md, section 4): the test, transitional and sweep frames of the
run's witness.json are drawn over every epoch's weights the trainer kept, from the untrained
network on, with each frame's strip and animation and witness-test.jsonl holding each epoch's
score; none of it chooses anything, since the checkpoint was chosen before this step began. The
table, the figures and the pictures go to Weights and Biases offline beside the run
(tools/wandb_log.py), pushed by the flow once the step is done.
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# As in tools/train.py: this folder leaves the path so tools/profile.py never shadows the
# standard library; the trainer's readers are loaded from their file instead.
sys.path[0] = str(ROOT / "src")

import argparse  # noqa: E402
import json  # noqa: E402
from collections import Counter, defaultdict  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402
from schwingnet.catalog import LEVELS, TRANSITIONAL  # noqa: E402
from schwingnet.flow import ResultRow, result_line, wilson  # noqa: E402


def load_trainer():
    spec = importlib.util.spec_from_file_location("schwingnet_train", ROOT / "tools" / "train.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


train = load_trainer()
TrainError, build_model, load_crops, predict, read_crops = (
    train.TrainError, train.build_model, train.load_crops, train.predict, train.read_crops,
)
TEST_ROLES = ("test", "transitional", "sweep")

HEADER = (
    "| measure | stratum | correct/n | fraction | 95% interval | persons | run | commit | tree |\n"
    "|---|---|---|---|---|---|---|---|---|"
)


def tally(crops, guesses):
    """Correct and total counts, with the persons behind them, overall and per stratum."""
    strata = defaultdict(lambda: {"correct": 0, "total": 0, "persons": set()})

    def add(key, crop, right):
        strata[key]["correct"] += int(right)
        strata[key]["total"] += 1
        strata[key]["persons"].add(crop["person"])

    for crop, guess in zip(crops, guesses, strict=True):
        right = LEVELS[int(guess)] == crop["level"]
        add(("accuracy", "all levels"), crop, right)
        add(("accuracy", f"level {crop['level']}"), crop, right)
        add(("accuracy", f"source {crop['source']}"), crop, right)
        if crop["level"] in TRANSITIONAL:
            add(("accuracy", "transitional (T13, L6)"), crop, right)
    return strata


def rows_of(strata, record):
    """The tallies as result rows, each refusing to exist without a clean tree."""
    rows = []
    for (measure, stratum), tally_ in sorted(strata.items()):
        rows.append(
            ResultRow(
                measure=measure,
                stratum=stratum,
                correct=tally_["correct"],
                total=tally_["total"],
                persons=len(tally_["persons"]),
                run_id=record["run_id"],
                code_commit=record["code_commit"],
                clean_tree=record["clean_tree"],
                catalog_sha256=record["catalog_sha256"],
            )
        )
    return rows


def confusion_figure(crops, guesses, path):
    """Truth against prediction over the levels that occur, counts in the cells."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    present = sorted({c["level"] for c in crops} | {LEVELS[int(g)] for g in guesses}, key=LEVELS.index)
    index = {level: n for n, level in enumerate(present)}
    matrix = np.zeros((len(present), len(present)), dtype=int)
    for crop, guess in zip(crops, guesses, strict=True):
        matrix[index[crop["level"]], index[LEVELS[int(guess)]]] += 1
    figure, axis = plt.subplots(figsize=(1 + 0.5 * len(present), 1 + 0.5 * len(present)))
    axis.imshow(matrix, cmap="Greys")
    axis.set_xticks(range(len(present)), present, rotation=90)
    axis.set_yticks(range(len(present)), present)
    axis.set_xlabel("predicted")
    axis.set_ylabel("truth")
    for (r, c), value in np.ndenumerate(matrix):
        if value:
            axis.text(c, r, str(value), ha="center", va="center", color="red", fontsize=7)
    figure.tight_layout()
    figure.savefig(path, dpi=120)
    plt.close(figure)


def per_level_figure(rows, path):
    """Accuracy per level with its interval, the levels in anatomical order."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    levels = [r for r in rows if r.stratum.startswith("level ")]
    levels.sort(key=lambda r: LEVELS.index(r.stratum.split(" ", 1)[1]))
    names = [r.stratum.split(" ", 1)[1] for r in levels]
    points = [r.correct / r.total for r in levels]
    intervals = [wilson(r.correct, r.total) for r in levels]
    errors = [[p - lo for p, (lo, _) in zip(points, intervals, strict=True)], [hi - p for p, (_, hi) in zip(points, intervals, strict=True)]]
    figure, axis = plt.subplots(figsize=(1 + 0.6 * len(names), 3.5))
    axis.bar(names, points, yerr=errors, capsize=3, color="0.6")
    axis.set_ylim(0, 1)
    axis.set_ylabel("accuracy (95% Wilson)")
    for n, row in enumerate(levels):
        axis.text(n, 0.02, f"n={row.total}", ha="center", fontsize=7)
    figure.tight_layout()
    figure.savefig(path, dpi=120)
    plt.close(figure)


def write_results(folder, rows, record, part, counts):
    """results.json and results.md, the table every reader of the demo starts from."""
    data = {
        "run_id": record["run_id"],
        "code_commit": record["code_commit"],
        "catalog_sha256": record["catalog_sha256"],
        "part": part,
        "counts": counts,
        "rows": [row.model_dump() for row in rows],
    }
    (folder / "results.json").write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    lines = [
        f"# Results of run {record['run_id']} on the {part} part",
        "",
        f"Level stage over truth boxes; {counts['crops']} crops from {counts['persons']} persons, "
        f"{counts['frames']} frames. Commit {record['code_commit'][:12]}, catalog "
        f"{record['catalog_sha256'][:12]}, clean tree. Chance is 1/{len(LEVELS)}.",
        "",
        HEADER,
        *(result_line(row) for row in rows),
        "",
    ]
    (folder / "results.md").write_text("\n".join(lines), encoding="utf-8")


def parse(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--part", default="test")
    parser.add_argument("--batch", type=int, default=64)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    return parser.parse_args(argv)


def epoch_files(out):
    """The epochs the trainer kept, in order, as (epoch, path)."""
    files = ((int(f.stem.split("-")[1]), f) for f in (out / "train" / "epochs").glob("epoch-*.pt"))
    return sorted(files)


def test_witness(out, args, size):
    """The test witness frames drawn over every kept epoch; each epoch's score per role."""
    listing = out / "witness.json"
    if not listing.is_file():
        return [], None
    tool = train.load_tool("witness")
    document = json.loads(listing.read_text(encoding="utf-8"))
    frames = [f for f in document["frames"] if f["role"] in TEST_ROLES]
    keys = {f["sha256"] for f in frames}
    crops = [c for c in read_crops(args.catalog, ("test",)) if c["sha256"] in keys]
    epochs = epoch_files(out)
    if not crops or not epochs:
        return [], None
    folder = out / "evaluate" / "witness" / "frames"
    inputs, _ = load_crops(crops, size, {})
    roles = {f["key"]: f["role"] for f in frames}
    lines = []
    for epoch, path in epochs:
        model = build_model(None, args.device)
        model.load_state_dict(torch.load(path, map_location=args.device, weights_only=True))
        scores = tool.draw_checkpoint(frames, train.marks_of(crops, predict(model, inputs, args.device, args.batch)), epoch, folder)
        line = {"epoch": epoch}
        for role in TEST_ROLES:
            mine = [v for k, v in scores.items() if roles[k] == role]
            line[role] = [sum(v[0] for v in mine), sum(v[1] for v in mine)]
        lines.append(line)
    tool.finish(folder, frames, [e for e, _ in epochs])
    with (out / "evaluate" / "witness-test.jsonl").open("w", encoding="utf-8") as handle:
        handle.writelines(json.dumps(line) + "\n" for line in lines)
    return lines, (folder, frames)


def log_to_wandb(out, record, rows, folder, lines, drawn):
    """The table, the figures and the test witness pictures as one W&B run of this step."""
    telemetry = train.load_tool("wandb_log").Telemetry(out, record, "evaluate", {"part": "test"})
    columns = ("measure", "stratum", "correct", "total", "fraction", "ci_low", "ci_high", "persons")
    table = telemetry.table(columns, [(r.measure, r.stratum, r.correct, r.total, r.correct / r.total, *wilson(r.correct, r.total), r.persons) for r in rows])
    for line in lines:
        telemetry.log({f"test_witness/{role}": v[0] / v[1] for role, v in line.items() if role != "epoch" and v[1]}, step=line["epoch"])
    media = telemetry.images({"confusion": folder / "confusion.png", "per_level": folder / "per-level.png"})
    if drawn:
        frames_folder, frames = drawn
        media |= telemetry.images({f"witness/test/{f['key']}": frames_folder / f["key"] / "strip.jpg" for f in frames})
        media |= telemetry.videos({f"witness/test_video/{f['key']}": frames_folder / f["key"] / "anim.gif" for f in frames})
    telemetry.log(dict(media, **({"results": table} if table is not None else {})))
    overall = next((r for r in rows if r.stratum == "all levels"), None)
    if overall:
        telemetry.summary({"test_accuracy": overall.correct / overall.total, "test_ci": list(wilson(overall.correct, overall.total)), "test_persons": overall.persons})
    telemetry.finish()


def run(args):
    out = Path(args.run)
    record = json.loads((out / "RUN.json").read_text(encoding="utf-8"))
    checkpoint = json.loads((out / "train" / "checkpoint.json").read_text(encoding="utf-8"))
    crops = read_crops(args.catalog, (args.part,))
    if not crops:
        raise TrainError(f"the catalog has no labelled crops in the {args.part} part")
    model = build_model(None, args.device)
    state = torch.load(out / "train" / "best.pt", map_location=args.device, weights_only=True)
    model.load_state_dict(state)
    size = int(checkpoint["size"])
    inputs, _ = load_crops(crops, size, {})
    guesses = predict(model, inputs, args.device, args.batch)
    strata = tally(crops, guesses)
    rows = rows_of(strata, record)
    folder = out / "evaluate"
    folder.mkdir(parents=True, exist_ok=True)
    counts = {"crops": len(crops), "persons": len({c["person"] for c in crops}), "frames": len({c["sha256"] for c in crops}), "levels": dict(Counter(c["level"] for c in crops))}
    write_results(folder, rows, record, args.part, counts)
    confusion_figure(crops, guesses, folder / "confusion.png")
    per_level_figure(rows, folder / "per-level.png")
    lines, drawn = test_witness(out, args, size) if args.part == "test" else ([], None)
    log_to_wandb(out, record, rows, folder, lines, drawn)
    for row in rows:
        print(result_line(row))
    return 0


def main(argv=None):
    try:
        return run(parse(argv))
    except TrainError as error:
        print(f"evaluate: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
