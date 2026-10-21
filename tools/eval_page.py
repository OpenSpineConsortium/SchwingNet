"""Write the evaluation page from the recorded runs, so the page and the records never disagree.

Usage:
    python3 tools/eval_page.py write   # docs/research/evaluation/README.md from the runs
    python3 tools/eval_page.py check   # fails when the page is not what the runs give

The page of docs/research/retraining-plan.md, section 4: every version in one table with its
intervals and its latency, then each run with its numbers over the epochs and its witness frames
drawn at every checkpoint from the untrained network on, each frame as a strip that links to its
animation. Every number is read from a file tools/flow.py record copied into
docs/research/v1-demo/runs/<run id>/ (RUN.json, train/metrics.jsonl, train/checkpoint.json,
evaluate/results.json, evaluate/witness-test.jsonl, evaluate/latency.json, wandb-sync.json,
witness.json), none is typed here, and a fact a run does not hold is written as not measured,
never left out. Standard library only, so the required check runs it.

The page lives in this private repository and is read on GitHub, where only members see it. It is
not put on the Pages site: whether Pages keeps a private repository's site to members on this
plan is not measured, and nothing of the method or its numbers leaves before the provisional is
filed (docs/project.md).
"""

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "docs" / "research" / "v1-demo" / "runs"
PAGE = ROOT / "docs" / "research" / "evaluation" / "README.md"
ROLES = ("validation", "test", "transitional", "sweep")
INTRO = """# SchwingNet evaluation, every version

Source: the thread "SchwingNet witness frames and W&B", 2026-10-21, issue #12; the plan is docs/research/retraining-plan.md, section 4. Confidential, this repository only, read on GitHub by its members: nothing here is public until the provisional is filed. Written by `python3 tools/eval_page.py write` from the recorded runs under docs/research/v1-demo/runs/; the required check fails when this page is not what the runs give, so do not edit it by hand.

How to read it: every fraction is correct/n with its 95 percent Wilson interval. The validation part chose the checkpoint; the test part was read once, at the version boundary. The witness frames are the same real frames at every checkpoint, epoch 0 being the untrained network: validation frames are drawn by the trainer every epoch, test, transitional (L6) and sweep frames by the evaluator over every epoch's weights after training, and they choose nothing. A green box names the body right, a red box shows truth>prediction. Each strip below links to its animation over all epochs. A run made on the synthetic bank measures the workflow, not SchwingNet, and says so in its note.
"""


def wilson(correct, total, z=1.96):
    """The same interval as schwingnet.flow.wilson, restated so this page needs no package."""
    if total <= 0:
        return 0.0, 1.0
    p = correct / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, centre - half), min(1.0, centre + half)


def fraction(correct, total):
    if not total:
        return "not measured"
    low, high = wilson(correct, total)
    return f"{correct}/{total} = {correct / total:.3f} ({low:.3f} to {high:.3f})"


def read_json(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def read_lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.is_file() else []


def load_run(folder):
    """Everything the page says of one run, from its recorded files."""
    return {
        "id": folder.name,
        "folder": folder,
        "record": read_json(folder / "RUN.json", {}),
        "metrics": read_lines(folder / "train" / "metrics.jsonl"),
        "checkpoint": read_json(folder / "train" / "checkpoint.json", {}),
        "results": read_json(folder / "evaluate" / "results.json", {}),
        "test_witness": read_lines(folder / "evaluate" / "witness-test.jsonl"),
        "latency": read_json(folder / "evaluate" / "latency.json"),
        "wandb": read_json(folder / "wandb-sync.json"),
        "witness": read_json(folder / "witness.json"),
        "note": (folder / "NOTE.md").read_text(encoding="utf-8").strip() if (folder / "NOTE.md").is_file() else "",
    }


def runs():
    """The recorded runs, oldest first by their start."""
    found = [load_run(f) for f in sorted(RUNS.iterdir()) if (f / "RUN.json").is_file()] if RUNS.is_dir() else []
    return sorted(found, key=lambda r: (r["record"].get("started_at", ""), r["id"]))


def row_of(run, stratum):
    for row in run["results"].get("rows", []):
        if row["stratum"] == stratum:
            return row
    return None


def cell(run, stratum):
    row = row_of(run, stratum)
    return fraction(row["correct"], row["total"]) + f", {row['persons']} persons" if row else "not measured"


def latency_cell(run):
    lat = run["latency"]
    if not lat:
        return "not measured"
    return f"{lat['ms_per_frame_median']:.1f} / {lat['ms_per_frame_p95']:.1f} ms ({lat['device']}, batch {lat.get('batch', 1)}, {lat['frames']} frames)"


def wandb_cell(run):
    sync = run["wandb"]
    if not sync:
        return "not logged (run made before W&B)"
    if sync.get("synced"):
        urls = sync.get("urls") or []
        return " ".join(f"[{n + 1}]({u})" for n, u in enumerate(urls)) or "pushed"
    return "not pushed: " + sync.get("why", "unknown").replace("|", "/")


def best_test_witness(run):
    best = run["checkpoint"].get("epoch")
    for line in run["test_witness"]:
        if line["epoch"] == best:
            right = sum(line[r][0] for r in ROLES[1:] if r in line)
            total = sum(line[r][1] for r in ROLES[1:] if r in line)
            return fraction(right, total)
    return "not drawn"


def change(run, previous):
    """What changed from the version before: the all-levels test fraction, both intervals."""
    now, before = row_of(run, "all levels"), previous and row_of(previous, "all levels")
    if not now or not before:
        return "first version" if not previous else "not comparable"
    delta = now["correct"] / now["total"] - before["correct"] / before["total"]
    shards = "same catalog" if run["record"].get("catalog_sha256") == previous["record"].get("catalog_sha256") else f"catalog {previous['record'].get('catalog_version')} to {run['record'].get('catalog_version')}"
    return f"{delta:+.3f} ({shards})"


def versions_table(all_runs):
    lines = [
        "## Every version",
        "",
        "| run | started | catalog | epochs, best | validation at best | test, all levels | transitional (T13, L6) | test witness at best | latency median / p95 | W&B | change from the version before |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    previous = None
    for run in all_runs:
        rec, best = run["record"], run["checkpoint"]
        validation = fraction(round(best["validation_accuracy"] * best["validation_n"]), best["validation_n"]) if best else "not measured"
        lines.append(
            f"| [{run['id']}](#run-{run['id']}) | {rec.get('started_at', '')[:16]} | {rec.get('catalog_version', '?')} {rec.get('catalog_sha256', '')[:12]} | {rec.get('epochs', '?')}, {best.get('epoch', '?')} | {validation} | {cell(run, 'all levels')} | {cell(run, 'transitional (T13, L6)')} | {best_test_witness(run)} | {latency_cell(run)} | {wandb_cell(run)} | {change(run, previous)} |"
        )
        previous = run
    return lines


def epochs_table(run):
    lines = ["| epoch | train loss | validation | validation witness frames |", "|---|---|---|---|"]
    for m in run["metrics"]:
        loss = "untrained" if m.get("train_loss") is None else f"{m['train_loss']:.4f}"
        right = round(m["validation_accuracy"] * m["validation_n"])
        witness = fraction(*m["witness_validation"]) if m.get("witness_validation") else "not drawn"
        lines.append(f"| {m['epoch']} | {loss} | {fraction(right, m['validation_n'])} | {witness} |")
    return lines


def strata_table(run, prefix):
    rows = [r for r in run["results"].get("rows", []) if r["stratum"].startswith(prefix)]
    if not rows:
        return []
    lines = ["| stratum | test | persons |", "|---|---|---|"]
    lines += [f"| {r['stratum']} | {fraction(r['correct'], r['total'])} | {r['persons']} |" for r in rows]
    return lines


def test_witness_table(run):
    if not run["test_witness"]:
        return ["Not drawn in this run."]
    lines = ["| epoch | test | transitional | sweep |", "|---|---|---|---|"]
    for line in run["test_witness"]:
        lines.append(f"| {line['epoch']} | " + " | ".join(fraction(*line.get(r, [0, 0])) for r in ROLES[1:]) + " |")
    return lines


def rel(path):
    return Path("..") / path.relative_to(ROOT / "docs" / "research")


def frames_section(run):
    """Per role, each witness frame's strip linking to its animation; the sheets first."""
    witness = run["witness"]
    if not witness:
        return ["No witness frames in this run (it was made before them)."]
    lines = []
    for line in witness.get("missing", []):
        lines.append(f"- Not shown: {line}.")
    for step in ("train", "evaluate"):
        sheets = sorted((run["folder"] / step / "witness" / "frames").glob("sheet-epoch-*.png"))
        for sheet in sheets:
            lines.append(f"![{step} {sheet.stem}]({rel(sheet).as_posix()})")
    for role in ROLES:
        frames = [f for f in witness["frames"] if f["role"] == role]
        if not frames:
            continue
        step = "train" if role == "validation" else "evaluate"
        lines += ["", f"<details><summary>{role}: {len(frames)} frames, strips over the epochs (each links to its animation)</summary>", ""]
        for frame in frames:
            base = run["folder"] / step / "witness" / "frames" / frame["key"]
            if (base / "strip.png").is_file():
                link = rel(base / "anim.gif").as_posix() if (base / "anim.gif").is_file() else rel(base / "strip.png").as_posix()
                lines.append(f"[![{frame['key']} {frame['person']} {','.join(frame['levels'])}]({rel(base / 'strip.png').as_posix()})]({link})")
                lines.append("")
        lines += ["</details>"]
    return lines


def run_section(run):
    rec, folder = run["record"], run["folder"]
    lines = [f'<a id="run-{run["id"]}"></a>', "", f"## Run {run['id']}", ""]
    lines.append(f"Commit {rec.get('code_commit', '')[:12]}, catalog {rec.get('catalog_version', '?')} ({rec.get('catalog_sha256', '')[:12]}), {rec.get('stage', '?')} stage, seed {rec.get('seed', '?')}, {rec.get('mode', '?')} mode. Files: [{rel(folder).as_posix()}]({rel(folder).as_posix()}).")
    if run["note"]:
        lines += ["", run["note"]]
    lines += ["", "### Over the epochs", "", *epochs_table(run)]
    for name in ("train/accuracy.png", "evaluate/per-level.png", "evaluate/confusion.png"):
        if (folder / name).is_file():
            lines += ["", f"![{name}]({rel(folder / name).as_posix()})"]
    for title, prefix in (("Per level", "level "), ("Per source", "source ")):
        table = strata_table(run, prefix)
        if table:
            lines += ["", f"### {title}, on the test part", "", *table]
    lines += ["", "### Test witness frames over the epochs (read at the version boundary)", "", *test_witness_table(run)]
    lines += ["", "### The witness frames", "", *frames_section(run)]
    return lines


def page():
    all_runs = runs()
    lines = [INTRO.rstrip(), "", *versions_table(all_runs)]
    for run in reversed(all_runs):
        lines += ["", *run_section(run)]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["write", "check"])
    args = parser.parse_args(argv)
    text = page()
    if args.command == "write":
        PAGE.parent.mkdir(parents=True, exist_ok=True)
        PAGE.write_text(text, encoding="utf-8")
        print(f"wrote {PAGE.relative_to(ROOT)} from {len(runs())} runs")
        return 0
    if not PAGE.is_file() or PAGE.read_text(encoding="utf-8") != text:
        print(f"eval_page: {PAGE.relative_to(ROOT)} is not what the runs give; run python3 tools/eval_page.py write", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
