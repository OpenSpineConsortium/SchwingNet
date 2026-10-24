"""The experiments panel: every recorded run by its data input, its blocks and its outcome, as chapter 35's figure.

Source: issue #242, the owner's ask of 2026-10-24 20:34 UTC for "an interactive artefact correlating a
data input, workflow blocks chosen, and loss/accuracy/model/reproducibility report/WandDB online
records", from which "new combinations of data and blocks" can be triggered "either by drop down ui,
or claude prompt"; the thread "Textbook: Claude integration and artifact edition", and the note
docs/research/experiments-panel.md.

The inputs are committed files only: every recorded run (each folder with a RUN.json under
docs/research/, the ledger's docs/research/v1-demo/runs/ among them, with train/checkpoint.json,
train/metrics.jsonl, train/MODEL.md, evaluate/results.json, evaluate/latency.json, split-check.json,
reforms.json, claim.json, REPORT.md, wandb-sync.json, PROVENANCE.json and NOTE.md where each exists),
the ledger docs/research/v1-demo/LEDGER.md, the recipes under data/recipes/ and the blocks of
src/schwingnet/blocks.py, read from the source with ast so that this tool needs nothing beyond the
standard library (the package imports beartype, which the required check's environment has not).

    python3 tools/experiments_panel.py write   # docs/textbook/figures/35/experiments.{html,json,svg}
    python3 tools/experiments_panel.py check   # exit 1 when a written file is not what the records give
    python3 tools/experiments_panel.py runs    # the rows the page is drawn from, as JSON
    python3 tools/experiments_panel.py check --request FILE   # exit 1 with why when a request does not hold

The page inlines its data as JSON and loads nothing, since the textbook shows a figure inside an
iframe sandboxed to scripts alone: it can neither fetch nor open another origin, so a link it offers
is posted to the page that embeds it (window.parent.postMessage, type schwingnet.open), and so is the
combination its "Run a new combination" panel names (type schwingnet.experiment), which the textbook
site turns into a bar with the link and the artifact edition into "Run as me" (the protocol is in the
note). A new combination is requested as an issue labelled experiment whose body carries the lines
`issue_body` writes, the form the experiment workflow reads; nothing here runs anything, since a grid
job waits for the owner's word and the number of jobs.

A request is checked here and nowhere else (`check --request`): the experiment workflow
(.github/workflows/experiment.yml, tools/experiment_run.py) runs it on main's code before it answers an
issue, and grid/experiment-driver.sbatch runs it again inside the container before anything trains,
so a value outside data/recipes/ and src/schwingnet/blocks.py never reaches the trainer. The
Experiment issue form, .github/ISSUE_TEMPLATE/experiment.yml, is written from the same lists by
`write` and held current by `check`, so its dropdowns are the trainer's choices.
"""

import argparse
import ast
import json
import math
import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = "OpenSpineConsortium/SchwingNet"
BLOB = f"https://github.com/{REPO}/blob/main/"
TREE = f"https://github.com/{REPO}/tree/main/"
RESEARCH = "docs/research"
LEDGER = "docs/research/v1-demo/LEDGER.md"
RUNS = "docs/research/v1-demo/runs"
RECIPES = "data/recipes"
BLOCKS_PY = "src/schwingnet/blocks.py"
CHAPTER = "docs/textbook/35-how-the-workflow-is-built.md"
OUT = "docs/textbook/figures/35"
FIGURE = "experiments"
FIGURE_ID = "35/experiments"
# The marker line of a requested combination's issue body, and the bounds the panel and the workflow
# hold a request to: a run trains at least one epoch and at most this many, since one grid job is
# the unit the owner counts.
ISSUE_MARKER = "<!-- schwingnet-experiment -->"
ISSUE_LABEL = "experiment"
EPOCHS_MOST = 200
FLOW_HEAD = "python3 tools/flow.py run --catalog <catalog> --out <runs> --mode slurm"
# What grid/experiment-driver.sbatch runs for a request, inside the container on the GPU Slurm gave it,
# on the catalog version grid/v1-version.sh chooses and with the ImageNet weights, as v1-driver.sbatch does.
DRIVER_HEAD = "python3 tools/flow.py run --catalog <catalog> --out <runs> --mode local --environment train-gpu"
DRIVER_TAIL = "--weights <weights>"
# A request's four settings beside its blocks, and the bounds the validator holds them to: the hours are
# the training job's wall time, which flow.py takes, and a job on the grid's GPU partitions ends within two days.
REQUEST_KEYS = ("recipe", "epochs", "seed", "hours")
HOURS_MOST = 48.0
FORM = ".github/ISSUE_TEMPLATE/experiment.yml"
# A source trained or validated on counts as the run's data; a test-only source is listed, not counted
# (tools/licences.py TRAINING_PARTS).
TRAINING_PARTS = ("train", "validation")
# The evaluator's z (schwingnet.flow.wilson), so the panel's intervals are the recorded ones to the digit.
Z95 = 1.96


def read_json(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def read_lines(path):
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def text_of(path):
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def wilson(correct, total, z=Z95):
    """The 95 percent Wilson interval of correct out of total, as every ResultRow carries it."""
    if not total:
        return [0.0, 1.0]
    p, n = correct / total, total
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [max(0.0, centre - half), min(1.0, centre + half)]


def _literal(node, space):
    """A module-level value of blocks.py as the source spells it: constants, tuples, lists, dicts,
    names assigned before it, strings added together and ", ".join(NAME); anything else is refused,
    so the reader never runs code."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Tuple):
        return tuple(_literal(e, space) for e in node.elts)
    if isinstance(node, ast.List):
        return [_literal(e, space) for e in node.elts]
    if isinstance(node, ast.Dict):
        return {_literal(k, space): _literal(v, space) for k, v in zip(node.keys, node.values)}
    if isinstance(node, ast.Name) and node.id in space:
        return space[node.id]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _literal(node.left, space) + _literal(node.right, space)
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "join"
            and len(node.args) == 1):
        return _literal(node.func.value, space).join(_literal(node.args[0], space))
    raise ValueError("not a plain value")


def block_catalog(root=ROOT):
    """The parts of training as src/schwingnet/blocks.py defines them, read from the source: the
    fields in order with version 1's default of each, the choices of each part that has a list, the
    settings' ranges in words, the list, number and count fields, and the samples choices that take
    sources or a count per person."""
    path = Path(root) / BLOCKS_PY
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    space = {}
    fields, defaults = [], {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                space[node.targets[0].id] = _literal(node.value, space)
            except (ValueError, KeyError, TypeError):
                continue
        if isinstance(node, ast.ClassDef) and node.name == "Blocks":
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and item.value is not None and isinstance(item.target, ast.Name):
                    value = ast.literal_eval(item.value)
                    fields.append(item.target.id)
                    defaults[item.target.id] = list(value) if isinstance(value, tuple) else value
    if not fields or "CHOICES" not in space:
        raise ValueError(f"{path}: no Blocks dataclass or no CHOICES read")
    return {
        "fields": fields,
        "defaults": defaults,
        "choices": {name: list(values) for name, values in space["CHOICES"].items()},
        "settings": dict(space.get("SETTINGS", {})),
        "options": {"augment": list(space.get("AUGMENT", ()))},
        "lists": list(space.get("LISTS", ())),
        "numbers": list(space.get("NUMBERS", ())),
        "counts": list(space.get("COUNTS", ())),
        "by_source": list(space.get("BY_SOURCE", ())),
        "by_person": space.get("BY_PERSON", "cap-per-person"),
    }


def recipes(root=ROOT):
    """Every licence recipe under data/recipes/, by name, with the classes it allows and why."""
    out = []
    for path in sorted((Path(root) / RECIPES).glob("*.json")):
        recipe = read_json(path, {})
        out.append({"name": recipe.get("name") or path.stem, "allow": list(recipe.get("allow", [])),
                    "reviewed_only": bool(recipe.get("reviewed_only")), "why": recipe.get("why", ""),
                    "path": path.relative_to(root).as_posix()})
    return sorted(out, key=lambda r: r["name"])


def ledger_rows(root=ROOT):
    """The ledger's rows by run id: the date, the activity, the cost and what was verified."""
    rows = {}
    for line in text_of(Path(root) / LEDGER).splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 9 and re.fullmatch(r"[0-9a-f]{12}", cells[1]):
            rows[cells[1]] = dict(zip(("date", "run", "mode", "activity", "commit", "catalog", "cost", "jobs", "verified"), cells))
    return rows


def run_folders(root=ROOT):
    """Every run folder under docs/research/: one that holds a RUN.json, the ledger's among them."""
    base = Path(root) / RESEARCH
    found = {}
    for path in sorted(base.rglob("RUN.json")) if base.is_dir() else []:
        found[path.parent.resolve()] = path.parent
    return sorted(found.values(), key=lambda p: p.relative_to(Path(root)).as_posix())


def fill_blocks(record, catalog):
    """Every part with its value: the checkpoint's record where the run has one, version 1's default
    where it names none, since a checkpoint from before the blocks records nothing and trained as
    version 1 (schwingnet.blocks.from_record); a list is a list, empty for none."""
    record = record or {}
    blocks = {}
    for name in catalog["fields"]:
        value = record.get(name, catalog["defaults"][name])
        if name in catalog["lists"]:
            if isinstance(value, (list, tuple)):
                value = [str(part) for part in value]
            else:
                value = [part for part in str(value).split(",") if part and part != "none"]
        blocks[name] = value
    for name, value in record.items():
        if name not in blocks:
            blocks[name] = value
    return blocks


def word_of(value):
    """A block's value as the command line spells it."""
    if isinstance(value, list):
        return ",".join(value) or "none"
    if isinstance(value, float) and value == int(value) and abs(value) < 1e15:
        return str(value)
    return str(value)


def named_words(blocks, catalog):
    """The KEY=VALUE words that name these blocks, only those that differ from version 1, in the
    fields' order (schwingnet.blocks.words_of)."""
    words = []
    for name in catalog["fields"]:
        value, default = blocks.get(name), catalog["defaults"][name]
        if isinstance(value, list):
            differs = list(value) != list(default)
        elif isinstance(value, (int, float)) and isinstance(default, (int, float)):
            differs = float(value) != float(default)
        else:
            differs = value != default
        if differs:
            words.append(f"{name}={word_of(value)}")
    return words


def trained_on(source):
    return any(source.get("frames", {}).get(part) for part in TRAINING_PARTS)


def data_input(record, provenance, results, note, ledger_row):
    """What the run was given: the catalog by version and hash, the recipe and the sources from
    PROVENANCE.json where the run has one, else the sources the result rows name, and the bank the
    notes name; a run on the synthetic bank is marked, since it measures the workflow and not the
    spine."""
    version, sha = record.get("catalog_version"), record.get("catalog_sha256") or ""
    catalog = f"catalog {version} {sha[:12]}" if version is not None else "catalog not recorded"
    words = f"{note} {ledger_row.get('activity', '')}".lower()
    synthetic = "synthetic bank" in words
    if provenance:
        recipe = provenance.get("recipe") or "none"
        datasets = sorted(s["source"] for s in provenance.get("sources", []) if trained_on(s))
        basis = "PROVENANCE.json"
    else:
        recipe = "none"
        datasets = sorted(row["stratum"][len("source "):] for row in results.get("rows", []) if str(row.get("stratum", "")).startswith("source "))
        basis = "the result rows' source strata (no PROVENANCE.json was recorded)"
    if synthetic:
        bank = "the synthetic bank (tools/synthetic_bank.py): learnable frames of no person, so the run measures the workflow and not SchwingNet"
    else:
        bank = "real frames" if provenance else "not recorded"
    kind = "synthetic bank" if synthetic else (f"recipe {recipe}" if recipe != "none" else "the catalog as it stands")
    return {"catalog": catalog, "catalog_version": version, "catalog_sha256": sha, "recipe": recipe,
            "datasets": datasets, "datasets_from": basis, "bank": bank, "synthetic": synthetic,
            "label": f"{kind}, {catalog}", "provenance": bool(provenance)}


def result_rows(results):
    rows = []
    for row in results.get("rows", []):
        correct, total = row.get("correct", 0), row.get("total", 0)
        rows.append({"measure": row.get("measure"), "stratum": row.get("stratum"), "correct": correct, "total": total,
                     "persons": row.get("persons"), "accuracy": (correct / total) if total else None,
                     "ci": wilson(correct, total) if total else None})
    return rows


def headline(rows):
    """The all-levels accuracy row, the one number a run is summarised by."""
    return next((row for row in rows if row["measure"] == "accuracy" and row["stratum"] == "all levels"), None)


def card_facts(card, blocks):
    """The model as its card gives it: the architecture line, the parameter count where the card
    has one (none does yet), else not recorded."""
    architecture = re.search(r"^- Architecture: (.*)$", card, re.M)
    parameters = re.search(r"^- Parameters?: (.*)$", card, re.M)
    return {"architecture": architecture.group(1).rstrip(".") if architecture else f"{blocks.get('architecture')} (no card recorded)",
            "parameters": parameters.group(1).rstrip(".") if parameters else "not recorded"}


def report_verdict(report):
    """Whether REPORT.md calls the run's reporting complete, and how many checklist items are missing."""
    found = re.search(r"Complete: \*\*(yes|no)\*\*(?:; missing (\d+))?", report)
    if not found:
        return {"complete": None, "missing": None}
    return {"complete": found.group(1) == "yes", "missing": int(found.group(2)) if found.group(2) else 0}


def reproduce_command(record, named, recipe):
    """The flow command that reproduces the run, from what RUN.json records: the commit, the catalog
    by version and hash (its file lives on the grid, so the catalog is named, not pathed), the mode,
    the epochs, the seed, the recipe and the blocks. Its environment and a dry run's --max-frames
    cap are not in RUN.json, so the command names what the record names."""
    commit = (record.get("code_commit") or "")[:12]
    catalog = f"<catalog {record.get('catalog_version')}, sha256 {(record.get('catalog_sha256') or '')[:12]}>"
    words = ["python3 tools/flow.py run", f"--catalog {catalog}", "--out <runs>", f"--mode {record.get('mode', 'local')}",
             f"--epochs {record.get('epochs')}", f"--seed {record.get('seed')}"]
    if recipe and recipe != "none":
        words.append(f"--recipe {recipe}")
    words += [f"--block {word}" for word in named]
    return (f"git checkout {commit} && " if commit else "") + " ".join(words)


def wandb_of(sync):
    """Where the run is on Weights and Biases: online with its links, offline with why, or not
    logged for a run made before W&B."""
    if not sync:
        return {"status": "not logged", "urls": [], "why": "the run was made before W&B logging"}
    urls = sorted(set(sync.get("urls") or []) | set(sync.get("online_urls") or []))
    if urls:
        return {"status": "online", "urls": urls, "why": ""}
    return {"status": "offline", "urls": [], "why": " ".join(str(sync.get("why") or "not pushed").split())}


def parent_of(checkpoint, record):
    parent = checkpoint.get("parent")
    if isinstance(parent, dict) and parent:
        if parent.get("run_id"):
            return f"run {parent['run_id']}"
        digest = parent.get("sha256") or ""
        return f"file {parent.get('file')}" + (f" (sha256 {digest[:12]})" if digest else "")
    if record.get("parent_weights"):
        return f"weights sha256 {str(record['parent_weights'])[:12]}"
    return "none (from scratch)"


def load_run(root, folder, catalog, ledger):
    """Everything the panel says of one run, from its recorded files."""
    record = read_json(folder / "RUN.json", {})
    run_id = record.get("run_id") or folder.name
    rel = folder.relative_to(root).as_posix()
    checkpoint = read_json(folder / "train" / "checkpoint.json", {})
    metrics = read_lines(folder / "train" / "metrics.jsonl")
    results = read_json(folder / "evaluate" / "results.json", {})
    latency = read_json(folder / "evaluate" / "latency.json")
    split = read_json(folder / "split-check.json")
    reforms = read_json(folder / "reforms.json") or {}
    claim = read_json(folder / "claim.json") or {}
    provenance = read_json(folder / "PROVENANCE.json")
    note = text_of(folder / "NOTE.md").strip()
    card = text_of(folder / "train" / "MODEL.md")
    row = ledger.get(run_id, {})
    blocks = fill_blocks(checkpoint.get("blocks"), catalog)
    named = named_words(blocks, catalog)
    given = data_input(record, provenance, results, note, row)
    rows = result_rows(results)
    best_loss = checkpoint.get("train_loss")
    jobs = record.get("jobs") or []
    seconds = sum(j.get("seconds_used") or 0 for j in jobs)
    counts = checkpoint.get("counts") or {}
    return {
        "id": run_id,
        "folder": rel,
        "folder_url": TREE + rel,
        "run_json": f"{rel}/RUN.json",
        "report_url": BLOB + f"{rel}/REPORT.md",
        "card_url": BLOB + f"{rel}/train/MODEL.md",
        "started": record.get("started_at", ""),
        "date": (record.get("started_at") or row.get("date") or "")[:10],
        "mode": record.get("mode", ""),
        "stage": record.get("stage", ""),
        "input": given,
        "blocks": blocks,
        "named": named,
        "blocks_recorded": bool(checkpoint.get("blocks")),
        "training": {"epochs": record.get("epochs"), "seed": record.get("seed"), "parent": parent_of(checkpoint, record),
                     "crops_train": counts.get("train"), "crops_validation": counts.get("validation"),
                     "persons_train": counts.get("train_persons"), "persons_validation": counts.get("validation_persons"),
                     "train_seen": counts.get("train_seen"), "train_offered": counts.get("train_offered"),
                     "size": checkpoint.get("size")},
        "metrics": [{"epoch": m.get("epoch"), "train_loss": m.get("train_loss"), "validation_accuracy": m.get("validation_accuracy"),
                     "validation_ci": m.get("validation_ci"), "validation_n": m.get("validation_n"),
                     "witness": m.get("witness_validation"), "seconds": m.get("seconds")} for m in metrics],
        "best": ({"epoch": checkpoint.get("epoch"), "accuracy": checkpoint.get("validation_accuracy"), "ci": checkpoint.get("validation_ci"),
                  "n": checkpoint.get("validation_n"), "loss": best_loss, "witness": checkpoint.get("witness_validation")}
                 if checkpoint.get("validation_accuracy") is not None else None),
        "test": headline(rows),
        "results": rows,
        "test_counts": results.get("counts") or {},
        "latency": ({"median": latency.get("ms_per_frame_median"), "p95": latency.get("ms_per_frame_p95"), "device": latency.get("device"),
                     "batch": latency.get("batch", 1), "frames": latency.get("frames"), "arm": latency.get("arm")} if latency else None),
        "model": dict(card_facts(card, blocks), checkpoint_sha256=checkpoint.get("checkpoint_sha256"), size=checkpoint.get("size"),
                      card=f"{rel}/train/MODEL.md" if card else None),
        "repro": {"commit": record.get("code_commit"), "commit_short": (record.get("code_commit") or "")[:12], "clean_tree": record.get("clean_tree"),
                  "split_disjoint": record.get("split_disjoint"), "split_check": split.get("disjoint") if split else None,
                  "reforms": reforms.get("tally"), "claim": claim.get("tally"), "report": report_verdict(text_of(folder / "REPORT.md")),
                  "command": reproduce_command(record, named, given["recipe"]), "run_json": f"{rel}/RUN.json"},
        "wandb": wandb_of(read_json(folder / "wandb-sync.json")),
        "cost": {"jobs": len(jobs), "wall_hours": round(seconds / 3600, 3), "gpu_hours": round(sum((j.get("seconds_used") or 0) * (j.get("gpus") or 0) for j in jobs) / 3600, 3),
                 "ledger": row.get("cost", "")},
        "activity": row.get("activity", ""),
        "verified": row.get("verified", ""),
        "note": note,
    }


def panel_data(root=ROOT):
    """Everything the page is drawn from: the runs oldest first, the parts, the recipes and where a
    request goes."""
    catalog = block_catalog(root)
    ledger = ledger_rows(root)
    runs = sorted((load_run(Path(root), folder, catalog, ledger) for folder in run_folders(root)), key=lambda r: (r["started"], r["id"]))
    return {
        "runs": runs,
        "blocks": catalog,
        "recipes": recipes(root),
        "repo": REPO,
        "blob": BLOB,
        "issue": {"new": f"https://github.com/{REPO}/issues/new", "label": ISSUE_LABEL, "marker": ISSUE_MARKER},
        "workflow": "experiment.yml",
        "epochs_most": EPOCHS_MOST,
        "flow": FLOW_HEAD,
        "dry_runs_only": bool(runs) and all(r["input"]["synthetic"] for r in runs),
        "synthetic_runs": sum(1 for r in runs if r["input"]["synthetic"]),
    }


def request_title(named, epochs):
    return f"Experiment: {' '.join(named) if named else 'version 1 (no block named)'}, {epochs} epochs"


def flow_command(named, epochs, seed, hours, recipe, head=FLOW_HEAD, tail=""):
    words = [head, f"--epochs {epochs}", f"--seed {seed}", f"--hours {hours}"]
    if tail:
        words.append(tail)
    if recipe and recipe != "none":
        words.append(f"--recipe {recipe}")
    words += [f"--block {word}" for word in named]
    return " ".join(words)


def issue_body(named, epochs, seed, hours, recipe):
    """The body of a requested combination's issue: the marker, then one `key: value` line each for
    the recipe, the epochs, the seed and the hours and one `block: KEY=VALUE` line per block that
    differs from version 1, the lines the experiment workflow reads; then the command they name."""
    lines = [ISSUE_MARKER, f"recipe: {recipe or 'none'}", f"epochs: {epochs}", f"seed: {seed}", f"hours: {hours}"]
    lines += [f"block: {word}" for word in named]
    return "\n".join(lines) + (
        "\n\nRequested from the textbook's experiments panel (chapter 35). The workflow reads only the lines above, "
        "checks each value against data/recipes/ and src/schwingnet/blocks.py, and answers with the exact flow command "
        "and the gate word that queues it; nothing runs on the grid without the owner's word and the number of jobs.\n\n"
        f"The command this names:\n\n    {flow_command(named, epochs, seed, hours, recipe)}\n")


def issue_url(named, epochs, seed, hours, recipe):
    query = urllib.parse.urlencode({"title": request_title(named, epochs), "labels": ISSUE_LABEL, "body": issue_body(named, epochs, seed, hours, recipe)})
    return f"https://github.com/{REPO}/issues/new?{query}"


# A request as the workflow and the driver read it: the panel's and the Claude box's `key: value` lines,
# or the issue form's `### key` sections. Each value is letters, digits and . _ , - and at most 80
# characters, since it becomes one word of a command line on the grid; a whole number has at most nine
# digits, so no reader meets a number it cannot hold (docs/memory, the int() bound).
LINE = re.compile(r"^(recipe|epochs|seed|hours|block):[ \t]*(\S.*?)[ \t]*$")
SECTION = re.compile(r"^### ([a-z][a-z0-9_]{0,31})[ \t]*$")
VALUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._,-]{0,79}$")
WORD = re.compile(r"^([a-z][a-z0-9_]{0,31})=(.+)$")
SOURCE = re.compile(r"^[a-z0-9_]{1,40}$")
WHOLE = re.compile(r"^[0-9]{1,9}$")
NUMBER = re.compile(r"^[0-9]{1,9}(\.[0-9]{1,6})?$")
NO_RESPONSE = "_No response_"
MOST_LINES = 400


def parse_request(text, catalog):
    """The request a body carries, as (fields, words, problems): the `recipe:`, `epochs:`, `seed:` and
    `hours:` lines and the `block: KEY=VALUE` lines the panel writes, read before any `### ` heading,
    or the issue form's sections, `### key` with the value below it, a checkbox list as its ticked
    boxes and `_No response_` as nothing; a setting given twice is a problem, and a heading that is
    neither a setting nor a block (the form's note) is prose."""
    fields, words, problems = {}, [], []
    lines = (text or "").replace("\r\n", "\n").split("\n")
    if len(lines) > MOST_LINES:
        problems.append(f"the body has more than {MOST_LINES} lines")
        lines = lines[:MOST_LINES]
    section, sections = None, {}
    for line in lines:
        heading = SECTION.match(line)
        if heading:
            section = heading.group(1)
            sections.setdefault(section, [])
            continue
        if section is not None:
            if line.strip():
                sections[section].append(line.strip())
            continue
        found = LINE.match(line)
        if not found:
            continue
        key, value = found.groups()
        if key == "block":
            words.append(value)
        elif key in fields:
            problems.append(f"{key} is given twice")
        else:
            fields[key] = value
    for key, values in sections.items():
        if any(v.startswith("- [") for v in values):
            value = ",".join(v[5:].strip() for v in values if v[:5] in ("- [x]", "- [X]"))
        else:
            value = " ".join(v for v in values if v != NO_RESPONSE)
        if not value:
            continue
        if key in REQUEST_KEYS:
            if key in fields:
                problems.append(f"{key} is given twice")
            fields[key] = value
        elif key in catalog["fields"]:
            words.append(f"{key}={value}")
    return fields, words, problems


def whole(text):
    """A whole number of at most nine digits, else None."""
    return int(text) if isinstance(text, str) and WHOLE.match(text) else None


def number(text):
    """A plain decimal number, no sign and no exponent, else None."""
    return float(text) if isinstance(text, str) and NUMBER.match(text) else None


def block_value(name, value, catalog):
    """One block's value as the trainer would take it, and the problem when it would not."""
    if not VALUE.match(value):
        return None, f"{name}={value[:40]} holds a character outside letters, digits and . _ , - or is over 80 characters"
    if name in catalog["choices"]:
        if value not in catalog["choices"][name]:
            return None, f"{name}={value} is not one of {', '.join(catalog['choices'][name])}"
        return value, None
    if name in catalog["lists"]:
        parts = [] if value == "none" else value.split(",")
        allowed = catalog["options"].get(name)
        for part in parts:
            if allowed is not None and part not in allowed:
                return None, f"{name} {part} is not one of {', '.join(allowed)}"
            if allowed is None and not SOURCE.match(part):
                return None, f"{name} {part} is not a source's name (lower-case letters, digits and _)"
        if len(set(parts)) != len(parts):
            return None, f"{name} names one part twice"
        return parts, None
    if name in catalog["counts"]:
        count = whole(value)
        if count is None:
            return None, f"{name} is a whole number, 0 or more, not {value}"
        return count, None
    if name in catalog["numbers"]:
        amount = number(value)
        if amount is None:
            return None, f"{name} is a plain number, 0 or more, not {value}"
        if name == "backbone_lr_scale" and not 0 < amount <= 1:
            return None, "backbone_lr_scale is above 0 and at most 1"
        return amount, None
    return None, f"{name} is a block this reader does not know how to check"


def block_rules(blocks, catalog):
    """The ways a whole choice of blocks does not hold, in the trainer's words (schwingnet.blocks.problems),
    each rule applied only where blocks.py has both of its parts."""
    problems = []
    has = blocks.__contains__
    if has("weight_decay") and has("optimiser") and blocks["weight_decay"] > 0 and blocks["optimiser"] == "adam":
        problems.append("weight_decay is for adamw; adam's would be L2 in the gradient, which this trainer does not offer")
    if has("prior") and has("prior_weight") and (blocks["prior"] != "none") != (blocks["prior_weight"] > 0):
        problems.append("prior_weight above 0 goes with prior=level-map, and only there")
    if has("samples") and has("sources") and (blocks["samples"] in catalog["by_source"]) != bool(blocks["sources"]):
        problems.append("sources=a,b goes with samples=only-sources or drop-sources, and only there")
    if has("samples") and has("per_person") and (blocks["samples"] == catalog["by_person"]) != (blocks["per_person"] > 0):
        problems.append("per_person of 1 or more goes with samples=cap-per-person, and only there")
    return problems


def request_problems(fields, words, catalog, recipe_names):
    """The request as (record, problems): the record normalised, its blocks only those that differ from
    version 1 in the fields' order, and every way the request does not hold, one line each, so a person
    reads them all at once; a record is given only when nothing is wrong."""
    problems = [f"{key} is missing" for key in REQUEST_KEYS if key not in fields]
    recipe = fields.get("recipe")
    if recipe is not None and recipe != "none" and recipe not in recipe_names:
        problems.append(f"recipe {recipe[:40]} is not none nor one of data/recipes/: {', '.join(recipe_names)}")
    epochs = whole(fields.get("epochs", ""))
    if "epochs" in fields and not (epochs is not None and 1 <= epochs <= EPOCHS_MOST):
        problems.append(f"epochs is a whole number from 1 to {EPOCHS_MOST}, not {fields['epochs'][:40]}")
    seed = whole(fields.get("seed", ""))
    if "seed" in fields and seed is None:
        problems.append(f"seed is a whole number, 0 or more, not {fields['seed'][:40]}")
    hours = number(fields.get("hours", ""))
    if "hours" in fields and not (hours is not None and 0 < hours <= HOURS_MOST):
        problems.append(f"hours is a number above 0 and at most {HOURS_MOST:g}, not {fields['hours'][:40]}")
    blocks = fill_blocks(None, catalog)
    named = set()
    for word in words:
        found = WORD.match(word)
        if not found:
            problems.append(f"block {word[:40]} is not KEY=VALUE")
            continue
        name, value = found.groups()
        if name not in catalog["fields"]:
            problems.append(f"{name} is not a block; the blocks are {', '.join(catalog['fields'])}")
            continue
        if name in named:
            problems.append(f"block {name} is named twice")
            continue
        named.add(name)
        parsed, problem = block_value(name, value, catalog)
        if problem:
            problems.append(problem)
        else:
            blocks[name] = parsed
    if not problems:
        problems += block_rules(blocks, catalog)
    if problems:
        return None, problems
    return {"recipe": recipe, "epochs": epochs, "seed": seed, "hours": hours, "blocks": named_words(blocks, catalog)}, []


def check_request(text, root=ROOT):
    """A body's request against this checkout's recipes and blocks: (record, problems)."""
    catalog = block_catalog(root)
    fields, words, problems = parse_request(text, catalog)
    record, more = request_problems(fields, words, catalog, [r["name"] for r in recipes(root)])
    return (None if problems else record), problems + more


def hours_word(hours):
    return f"{hours:g}"


def request_lines(record):
    """The normalised request as the file on the branch experiments and the lines the answer quotes."""
    lines = [f"recipe: {record['recipe']}", f"epochs: {record['epochs']}", f"seed: {record['seed']}", f"hours: {hours_word(record['hours'])}"]
    return "\n".join(lines + [f"block: {word}" for word in record["blocks"]]) + "\n"


def request_command(record):
    """The flow command the request names, as the panel shows it."""
    return flow_command(record["blocks"], record["epochs"], record["seed"], hours_word(record["hours"]), record["recipe"])


def driver_command(record):
    """What grid/experiment-driver.sbatch runs for the request, with the catalog, the runs folder and the
    weights as the grid holds them."""
    return flow_command(record["blocks"], record["epochs"], record["seed"], hours_word(record["hours"]), record["recipe"], DRIVER_HEAD, DRIVER_TAIL)


def yaml_text(value):
    """A scalar as the issue form's YAML takes it: JSON's double-quoted string is a YAML string."""
    return json.dumps(str(value))


def form_text(catalog, recipe_names):
    """The Experiment issue form, written from the recipes and the blocks so that its lists are the
    trainer's own: a dropdown with version 1's choice preselected for each part that has a list, the
    augmentations as checkboxes, an input for a number, a count or the sources, and the four settings;
    each field's label is the key the validator reads under its `### key` heading."""
    lines = [
        "name: Experiment",
        'description: ' + yaml_text("A new combination of data and blocks for one run on the grid: the workflow checks every value, "
                                     "answers with the exact flow command and the gate word that queues it, and the owner's click runs it."),
        '# Written by `python3 tools/experiments_panel.py write` from data/recipes/ and src/schwingnet/blocks.py and held',
        '# current by `check`; change those files, not this one. The workflow reads each field under its heading.',
        'title: "Experiment: "',
        'labels: ["experiment"]',
        "body:",
        "  - type: markdown",
        "    attributes:",
        "      value: " + yaml_text("Each field is one part of training (src/schwingnet/blocks.py); leave a field as it is for version 1's "
                                    "choice. Nothing runs from this form: the workflow answers with the command and the gate word, and the "
                                    "owner's click queues the one job."),
        "  - type: dropdown",
        "    id: recipe",
        "    attributes:",
        "      label: recipe",
        "      description: " + yaml_text("The licence cut of the catalog (data/recipes/); none is the catalog as it stands."),
        "      options:",
    ]
    lines += [f"        - {name}" for name in ["none"] + list(recipe_names)]
    lines += ["      default: 0", "    validations:", "      required: true"]
    settings = (("epochs", f"1 to {EPOCHS_MOST}", "20"), ("seed", "0 or more", "1"), ("hours", f"the training job's wall time, above 0 and at most {HOURS_MOST:g}", "4"))
    for key, description, value in settings:
        lines += ["  - type: input", f"    id: {key}", "    attributes:", f"      label: {key}", f"      description: {yaml_text(description)}",
                  f"      value: {yaml_text(value)}", "    validations:", "      required: true"]
    for name in catalog["fields"]:
        default = catalog["defaults"][name]
        note = catalog["settings"].get(name, "")
        if name in catalog["choices"]:
            choices = catalog["choices"][name]
            lines += ["  - type: dropdown", f"    id: {name}", "    attributes:", f"      label: {name}"]
            if note:
                lines.append(f"      description: {yaml_text(note)}")
            lines += ["      options:"] + [f"        - {choice}" for choice in choices] + [f"      default: {choices.index(default)}"]
        elif catalog["options"].get(name):
            lines += ["  - type: checkboxes", f"    id: {name}", "    attributes:", f"      label: {name}",
                      f"      description: {yaml_text(note or 'any of these, in this order; none is version 1')}", "      options:"]
            lines += [f"        - label: {option}" for option in catalog["options"][name]]
        else:
            if name in catalog["lists"]:
                description = note or "comma-separated source names; empty is version 1"
            else:
                description = note or ("a whole number, 0 or more" if name in catalog["counts"] else "a plain number, 0 or more")
            lines += ["  - type: input", f"    id: {name}", "    attributes:", f"      label: {name}", f"      description: {yaml_text(description)}"]
            if name not in catalog["lists"]:
                lines.append(f"      value: {yaml_text(word_of(default))}")
    lines += ["  - type: textarea", "    id: note", "    attributes:", "      label: note",
              "      description: " + yaml_text("Why this combination, in a sentence or two (optional)."), "    validations:", "      required: false"]
    return "\n".join(lines) + "\n"


def esc(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


STYLE = """
:root{color-scheme:light;--bg:#fcfcfb;--panel:#f3f2ee;--ink:#0b0b0b;--ink2:#52514e;--ink3:#7d7c77;--rule:#e1e0db;
--accent:#2a78d6;--accent2:#c2410c;--ok:#1a8f5a;--warn:#b7791f;--bad:#c53030;
--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#9f5fd6;--s5:#eda100;--s6:#e87ba4}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){color-scheme:dark;--bg:#1a1a19;--panel:#242422;--ink:#f0efec;--ink2:#c3c2b7;
--ink3:#8f8e87;--rule:#36352f;--accent:#5b9cf0;--accent2:#f08a5a;--ok:#4cc38a;--warn:#e0a84c;--bad:#f07171;
--s1:#5b9cf0;--s2:#f08a5a;--s3:#36c993;--s4:#b98cf0;--s5:#e7b84a;--s6:#f09ab8}}
:root[data-theme=dark]{color-scheme:dark;--bg:#1a1a19;--panel:#242422;--ink:#f0efec;--ink2:#c3c2b7;--ink3:#8f8e87;--rule:#36352f;
--accent:#5b9cf0;--accent2:#f08a5a;--ok:#4cc38a;--warn:#e0a84c;--bad:#f07171;
--s1:#5b9cf0;--s2:#f08a5a;--s3:#36c993;--s4:#b98cf0;--s5:#e7b84a;--s6:#f09ab8}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--ink)}
body{font:14px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;overflow-x:hidden}
main{max-width:1100px;margin:0 auto;padding:12px 16px 32px}
h1{font-size:20px;margin:0 0 4px}h2{font-size:16px;margin:24px 0 6px}
p{margin:6px 0}.sub,.note,.small{color:var(--ink2)}.small{font-size:12px}.note{font-size:13px}
a{color:var(--accent)}code,pre{font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
pre{background:var(--panel);border:1px solid var(--rule);border-radius:6px;padding:8px 10px;white-space:pre-wrap;word-break:break-word;margin:6px 0}
.notice{border-left:4px solid var(--warn);background:var(--panel);padding:8px 12px;border-radius:0 6px 6px 0;margin:10px 0}
.controls{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;margin:8px 0}
.controls label,.req label{display:inline-flex;flex-direction:column;gap:2px;font-size:12px;color:var(--ink2)}
select,input[type=number],input[type=text]{font:13px system-ui,sans-serif;color:var(--ink);background:var(--bg);border:1px solid var(--rule);border-radius:5px;padding:4px 6px;min-width:120px;max-width:100%}
input[type=number]{min-width:84px;width:110px}
.tiles{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0}.tile{background:var(--panel);border:1px solid var(--rule);border-radius:6px;padding:6px 10px;font-size:13px}
.tile b{font-size:16px;display:block}
.wrap{overflow-x:auto;max-width:100%}svg{display:block;width:100%;height:auto}
svg text{fill:var(--ink);font-size:11px}svg .ink3{fill:var(--ink3)}svg .rule{stroke:var(--rule)}svg .mean{stroke:var(--ink2);stroke-width:2}
svg .test{fill:var(--accent);stroke:var(--accent);stroke-width:2}svg .val{fill:var(--bg);stroke:var(--accent2);stroke-width:2}
.legend{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:12px;color:var(--ink2);margin:4px 0}
.legend i,.key i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;vertical-align:top;padding:6px 8px;border-bottom:1px solid var(--rule)}
th{color:var(--ink2);font-weight:600;font-size:12px;white-space:nowrap}
tr.details{display:none}tr.details.open{display:table-row}tr.details td{background:var(--panel)}
button.link{background:none;border:0;padding:0;color:var(--accent);font:inherit;cursor:pointer;text-decoration:underline}
dl{display:grid;grid-template-columns:max-content 1fr;gap:3px 12px;margin:4px 0}dt{color:var(--ink2)}dd{margin:0;word-break:break-word}
.req{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:8px 14px;margin:8px 0}
.req fieldset{border:1px solid var(--rule);border-radius:6px;padding:6px 8px;margin:0;grid-column:1/-1}
.req fieldset label{flex-direction:row;align-items:center;gap:6px;margin-right:12px}
.chip{display:inline-block;white-space:nowrap;border:1px solid var(--rule);border-radius:999px;padding:1px 8px;font-size:12px;color:var(--ink2);margin:0 4px 4px 0}
.chip.ok{border-color:var(--ok);color:var(--ok)}.chip.warn{border-color:var(--warn);color:var(--warn)}.chip.bad{border-color:var(--bad);color:var(--bad)}
.problems{color:var(--bad);font-size:13px;margin:4px 0}.problems:empty{display:none}
.button{display:inline-block;background:var(--accent);color:#fff;border-radius:6px;padding:7px 12px;text-decoration:none;font-weight:600;border:0;font:inherit;cursor:pointer}
.button[aria-disabled=true]{opacity:.5;pointer-events:none}
.tip{position:fixed;display:none;pointer-events:none;background:var(--panel);color:var(--ink);border:1px solid var(--rule);border-radius:6px;padding:6px 8px;font-size:12px;max-width:320px;z-index:5;box-shadow:0 2px 8px rgba(0,0,0,.15)}
@media (max-width:480px){h1{font-size:18px}.controls label{width:100%}select{width:100%}.req{grid-template-columns:1fr}input[type=number]{width:100%}}
"""

BODY = """
<h1>The experiments panel</h1>
<p class="sub" id="sub"></p>
<div class="notice" id="dry"></div>
<h2>Which runs</h2>
<div class="controls" id="filters"></div>
<div class="tiles" id="tiles"></div>
<h2>Accuracy, with its interval</h2>
<div class="wrap"><svg id="acc" width="100%"></svg></div>
<p class="note">Filled: the test part's accuracy over all levels, read once after training. Hollow: the best epoch's validation accuracy, which chose the checkpoint. Each with its 95 percent Wilson interval; a dry run on the synthetic bank measures the workflow, not the spine.</p>
<h2>Training loss by epoch</h2>
<div class="legend" id="loss-legend"></div>
<div class="wrap"><svg id="loss" width="100%"></svg></div>
<p class="note">The training loss of each epoch on a logarithmic axis; hover a point for its validation accuracy. A loss that keeps falling while the witness frames break is the case for the witness frames (chapter 18).</p>
<h2>Accuracy by block</h2>
<div class="controls"><label>Block <select id="c-part"></select></label><label>Measure <select id="c-measure"><option value="test">test accuracy</option><option value="validation">best validation accuracy</option><option value="loss">training loss at the best epoch</option></select></label></div>
<div class="wrap"><svg id="corr" width="100%"></svg></div>
<p class="note" id="c-note"></p>
<h2>Every run</h2>
<div class="wrap"><table><thead><tr><th>Run</th><th>Data input</th><th>Blocks</th><th>Epochs</th><th>Best epoch</th><th>Validation</th><th>Test accuracy</th><th>Latency</th><th>Reproducibility</th><th>W&amp;B</th><th>Report</th></tr></thead><tbody id="rows"></tbody></table></div>
<p class="note">Click a run's id for everything recorded of it: its data input, every block spelled out, the model, the result rows by stratum, the checklists and the exact command that reproduces it. Links open outside this figure.</p>
<h2>Run a new combination</h2>
<p class="note">Choose a recipe, a value for each block and the epochs; the exact command appears below, with any way the choice does not hold. Request this run opens a prefilled issue labelled experiment, which the workflow answers with the command, the gate word that queues it and the owner's click; nothing runs on the grid without the owner's word and the number of jobs.</p>
<div class="req" id="req"></div>
<pre id="cmd"></pre>
<div class="problems" id="problems"></div>
<p><a class="button" id="request" href="#" target="_blank" rel="noopener">Request this run</a> <span class="small" id="req-note"></span></p>
"""

SCRIPT = r"""
const D=DATA,B=D.blocks,$=id=>document.getElementById(id);
const esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const pct=v=>v==null?"not measured":(100*v).toFixed(1)+"%";
const ci=c=>c?(100*c[0]).toFixed(1)+" to "+(100*c[1]).toFixed(1)+"%":"";
const NS="http://www.w3.org/2000/svg";
function el(n,a,p){const e=document.createElementNS(NS,n);for(const k in a)e.setAttribute(k,a[k]);if(p)p.appendChild(e);return e}
function txt(p,x,y,s,a){const t=el("text",Object.assign({x:x,y:y},a||{}),p);t.textContent=s;return t}
const tip=$("tip");
function showTip(e,html){tip.innerHTML=html;tip.style.display="block";const w=tip.offsetWidth,h=tip.offsetHeight;let x=e.clientX+14,y=e.clientY+14;
if(x+w>innerWidth-8)x=e.clientX-w-14;if(y+h>innerHeight-8)y=e.clientY-h-14;tip.style.left=x+"px";tip.style.top=y+"px"}
function hideTip(){tip.style.display="none"}
const framed=(()=>{try{return window.parent&&window.parent!==window}catch(e){return true}})();
function post(payload){try{if(framed)window.parent.postMessage(payload,"*")}catch(e){}}
// A link opened from inside the textbook's sandbox cannot leave it, so when framed the link is posted to the
// page that embeds this figure (type schwingnet.open), which shows it; opened on its own, a link is a link.
document.addEventListener("click",e=>{const a=e.target.closest("a[href]");if(!a||!framed||a.id==="request")return;
if(/^https?:/.test(a.getAttribute("href"))){e.preventDefault();post({type:"schwingnet.open",href:a.href,label:a.textContent})}});
const FILTER_PARTS=B.fields.filter(f=>B.choices[f]||f==="augment");
function blockText(r,f){const v=r.blocks[f];return Array.isArray(v)?(v.join(",")||"none"):String(v)}
function namedText(r){return r.named.length?r.named.join(" "):"version 1 (no block named)"}
function label(r,width){const s=r.id+" "+namedText(r);const most=Math.max(12,Math.floor(width/6.2));return s.length>most?s.slice(0,most-3)+"...":s}
$("sub").textContent=D.runs.length+" recorded run"+(D.runs.length===1?"":"s")+" under docs/research/, each read from its own files: what it was given, the blocks it chose and what came out. Every number here is a record, not a final value.";
$("dry").textContent=D.dry_runs_only?"Every run recorded so far is a dry run on the synthetic bank (tools/synthetic_bank.py): learnable frames of no person, made to test the workflow end to end. Nothing on this page is a measurement of SchwingNet on real frames; the first run on the real catalog waits for the owner's word.":(D.synthetic_runs?D.synthetic_runs+" of the "+D.runs.length+" runs are dry runs on the synthetic bank and measure the workflow, not the spine; their data input says so.":"");
if(!$("dry").textContent)$("dry").style.display="none";
const F={input:"",blocks:{}};
function addSelect(box,text,id,options,cb){const l=document.createElement("label");l.textContent=text;const s=document.createElement("select");s.id=id;
options.forEach(o=>{const op=document.createElement("option");op.value=o;op.textContent=o;s.appendChild(op)});s.onchange=()=>cb(s.value);l.appendChild(s);box.appendChild(l);return s}
(function buildFilters(){const box=$("filters");const inputs=[...new Set(D.runs.map(r=>r.input.label))].sort();
addSelect(box,"Data input","f-input",["any"].concat(inputs),v=>{F.input=v==="any"?"":v;draw()});
FILTER_PARTS.forEach(f=>{const vals=[...new Set(D.runs.map(r=>blockText(r,f)))].sort();
addSelect(box,f,"f-"+f,["any"].concat(vals),v=>{if(v==="any")delete F.blocks[f];else F.blocks[f]=v;draw()})})})();
function shown(){return D.runs.filter(r=>(!F.input||r.input.label===F.input)&&Object.keys(F.blocks).every(f=>blockText(r,f)===F.blocks[f]))}
function width(svg){return Math.max(svg.clientWidth||svg.parentNode.clientWidth||800,320)}
function accTip(r){return "<b>"+esc(r.id)+"</b> "+esc(namedText(r))+"<br>"+esc(r.input.label)+"<br>test: "+(r.test?pct(r.test.accuracy)+" ("+ci(r.test.ci)+", "+r.test.correct+"/"+r.test.total+", "+r.test.persons+" persons)":"not measured")+
"<br>validation, best epoch "+(r.best?r.best.epoch+": "+pct(r.best.accuracy)+" ("+ci(r.best.ci)+", n="+r.best.n+")":"not recorded")}
function drawAccuracy(rows){const svg=$("acc");svg.innerHTML="";const W=width(svg),L=W<560?130:260,R=16,rowH=30,top=26,H=top+Math.max(1,rows.length)*rowH+30;
svg.setAttribute("viewBox","0 0 "+W+" "+H);svg.setAttribute("height",H);const x=v=>L+(W-L-R)*v;
[0,.25,.5,.75,1].forEach(v=>{el("line",{x1:x(v),x2:x(v),y1:top-6,y2:H-26,class:"rule"},svg);txt(svg,x(v),top-10,(100*v)+"%",{"text-anchor":"middle",class:"ink3"})});
if(!rows.length){txt(svg,L,top+16,"No recorded run matches the filters.");return}
rows.forEach((r,i)=>{const y=top+i*rowH+rowH/2;txt(svg,L-8,y+4,label(r,L-12),{"text-anchor":"end"});
if(r.test){el("line",{x1:x(r.test.ci[0]),x2:x(r.test.ci[1]),y1:y-6,y2:y-6,class:"test"},svg);el("circle",{cx:x(r.test.accuracy),cy:y-6,r:4.5,class:"test"},svg)}
if(r.best&&r.best.ci){el("line",{x1:x(r.best.ci[0]),x2:x(r.best.ci[1]),y1:y+7,y2:y+7,class:"val"},svg);el("circle",{cx:x(r.best.accuracy),cy:y+7,r:4.5,class:"val"},svg)}
const hit=el("rect",{x:0,y:y-rowH/2,width:W,height:rowH,fill:"transparent"},svg);hit.onmousemove=e=>showTip(e,accTip(r));hit.onmouseleave=hideTip});
if(W>=560)txt(svg,x(0),H-8,"accuracy, test (filled) and best validation (hollow), 95% Wilson intervals",{class:"ink3"})}
const fmtLoss=v=>v>=1?v.toFixed(2):v.toPrecision(2);
function drawLoss(rows){const svg=$("loss");svg.innerHTML="";const W=width(svg),L=58,R=16,top=16,H=260,bottom=H-40;svg.setAttribute("viewBox","0 0 "+W+" "+H);svg.setAttribute("height",H);
const series=rows.map(r=>({r:r,m:r.metrics.filter(m=>m.train_loss!=null&&m.train_loss>0)})).filter(s=>s.m.length);
const all=series.flatMap(s=>s.m);$("loss-legend").innerHTML=series.map((s,i)=>'<span><i style="background:var(--s'+(i%6+1)+')"></i>'+esc(s.r.id)+" "+esc(namedText(s.r))+"</span>").join("");
if(!all.length){txt(svg,L,40,"No training loss is recorded for the runs shown.");return}
const minE=Math.min.apply(null,all.map(m=>m.epoch)),maxE=Math.max.apply(null,all.map(m=>m.epoch));
const lo=Math.min.apply(null,all.map(m=>m.train_loss)),hi=Math.max.apply(null,all.map(m=>m.train_loss));
const lg=Math.log10,span=Math.max(1e-9,lg(hi)-lg(lo));const y=v=>bottom-(bottom-top)*((lg(v)-lg(lo))/span);const x=e=>L+(W-L-R)*((e-minE)/Math.max(1,maxE-minE));
for(let k=Math.ceil(lg(lo));k<=Math.floor(lg(hi));k++){const v=Math.pow(10,k);el("line",{x1:L,x2:W-R,y1:y(v),y2:y(v),class:"rule"},svg);txt(svg,L-6,y(v)+4,fmtLoss(v),{"text-anchor":"end",class:"ink3"})}
txt(svg,L-6,y(hi)+4,fmtLoss(hi),{"text-anchor":"end",class:"ink3"});txt(svg,L-6,y(lo)+4,fmtLoss(lo),{"text-anchor":"end",class:"ink3"});
const step=Math.max(1,Math.ceil((maxE-minE+1)/16));for(let e=minE;e<=maxE;e+=step)txt(svg,x(e),H-22,String(e),{"text-anchor":"middle",class:"ink3"});
txt(svg,(L+W-R)/2,H-6,"epoch",{"text-anchor":"middle",class:"ink3"});
series.forEach((s,i)=>{const c="var(--s"+(i%6+1)+")";if(s.m.length>1)el("polyline",{points:s.m.map(m=>x(m.epoch)+","+y(m.train_loss)).join(" "),fill:"none",stroke:c,"stroke-width":2},svg);
s.m.forEach(m=>{const d=el("circle",{cx:x(m.epoch),cy:y(m.train_loss),r:4,fill:c},svg);
d.onmousemove=e=>showTip(e,"<b>"+esc(s.r.id)+"</b> epoch "+m.epoch+"<br>training loss "+m.train_loss.toPrecision(3)+"<br>validation accuracy "+pct(m.validation_accuracy)+(m.validation_ci?" ("+ci(m.validation_ci)+", n="+m.validation_n+")":"")+(m.witness?"<br>validation witness bodies "+m.witness[0]+"/"+m.witness[1]:""));d.onmouseleave=hideTip})})}
const measureWords={test:"test accuracy",validation:"best validation accuracy",loss:"training loss at the best epoch"};
(function buildCorr(){const s=$("c-part");FILTER_PARTS.forEach(f=>{const o=document.createElement("option");o.value=f;o.textContent=f;s.appendChild(o)});s.value="architecture";s.onchange=()=>drawCorr(shown());$("c-measure").onchange=()=>drawCorr(shown())})();
function drawCorr(rows){const part=$("c-part").value,measure=$("c-measure").value,svg=$("corr");svg.innerHTML="";const W=width(svg),L=58,R=16,top=16,H=250,bottom=H-44;
svg.setAttribute("viewBox","0 0 "+W+" "+H);svg.setAttribute("height",H);
const val=r=>measure==="test"?(r.test?r.test.accuracy:null):measure==="validation"?(r.best?r.best.accuracy:null):(r.best?r.best.loss:null);
const groups={};rows.forEach(r=>{const k=blockText(r,part);(groups[k]=groups[k]||[]).push(r)});const keys=Object.keys(groups).sort();
const vals=rows.map(val).filter(v=>v!=null&&v>0||v===0);
if(!vals.length){txt(svg,L,40,"No value of this measure is recorded for the runs shown.");$("c-note").textContent="";return}
const isLoss=measure==="loss";let y;
if(isLoss){const lo=Math.min.apply(null,vals.filter(v=>v>0)),hi=Math.max.apply(null,vals);const span=Math.max(1e-9,Math.log10(hi)-Math.log10(lo));
y=v=>bottom-(bottom-top)*((Math.log10(Math.max(v,lo))-Math.log10(lo))/span);
[lo,hi].forEach(v=>{el("line",{x1:L,x2:W-R,y1:y(v),y2:y(v),class:"rule"},svg);txt(svg,L-6,y(v)+4,fmtLoss(v),{"text-anchor":"end",class:"ink3"})})}
else{y=v=>bottom-(bottom-top)*v;[0,.25,.5,.75,1].forEach(v=>{el("line",{x1:L,x2:W-R,y1:y(v),y2:y(v),class:"rule"},svg);txt(svg,L-6,y(v)+4,(100*v)+"%",{"text-anchor":"end",class:"ink3"})})}
const slot=(W-L-R)/Math.max(1,keys.length);
keys.forEach((k,i)=>{const cx=L+slot*(i+.5),g=groups[k],vs=g.map(val).filter(v=>v!=null);const most=Math.max(6,Math.floor(slot/6.5));
txt(svg,cx,H-26,k.length>most?k.slice(0,most-3)+"...":k,{"text-anchor":"middle"});txt(svg,cx,H-10,"n="+vs.length,{"text-anchor":"middle",class:"ink3"});
if(vs.length){const mean=vs.reduce((a,b)=>a+b,0)/vs.length;el("line",{x1:cx-slot*.3,x2:cx+slot*.3,y1:y(mean),y2:y(mean),class:"mean"},svg)}
g.forEach((r,j)=>{const v=val(r);if(v==null)return;const d=el("circle",{cx:cx+(j-(g.length-1)/2)*9,cy:y(v),r:5,class:"test"},svg);
d.onmousemove=e=>showTip(e,"<b>"+esc(r.id)+"</b><br>"+esc(part)+" = "+esc(k)+"<br>"+measureWords[measure]+": "+(isLoss?v.toPrecision(3):pct(v)));d.onmouseleave=hideTip})});
$("c-note").textContent=keys.length<2?"Every run shown uses one value of "+part+" ("+(keys[0]||"none")+"), so there is nothing to compare yet; a comparison needs recorded runs that differ in it, and the panel below requests one.":keys.length+" values of "+part+" among the runs shown; each dot is one run, the bar its group's mean. Runs that differ in other blocks too are not a controlled comparison.";}
function chip(ok,text,cls){return '<span class="chip '+(ok===true?"ok":ok===false?(cls||"bad"):"")+'">'+esc(text)+"</span>"}
function reproCell(r){const p=r.repro;return chip(p.clean_tree,"clean tree: "+(p.clean_tree==null?"not recorded":p.clean_tree?"yes":"no"))+chip(p.split_disjoint,"split disjoint: "+(p.split_disjoint==null?"not recorded":p.split_disjoint?"yes":"no"))+
(p.reforms?chip(p.reforms.missing===0,"REFORMS "+p.reforms.met+" met, "+p.reforms.missing+" missing","warn"):chip(null,"REFORMS: not recorded"))+'<div class="small">commit '+esc(p.commit_short||"not recorded")+"</div>"}
function wandbCell(r){const w=r.wandb;if(w.status==="online")return w.urls.map((u,i)=>'<a href="'+esc(u)+'">W&amp;B '+(i+1)+"</a>").join(" ");return '<span class="chip warn">'+esc(w.status)+'</span><div class="small">'+esc(w.why)+"</div>"}
function dl(pairs){return "<dl>"+pairs.filter(p=>p[1]!=null&&p[1]!=="").map(p=>"<dt>"+esc(p[0])+"</dt><dd>"+p[1]+"</dd>").join("")+"</dl>"}
function details(r){const t=r.training,p=r.repro,m=r.model;
const blocks=B.fields.map(f=>esc(f)+"="+esc(blockText(r,f))+(r.named.some(w=>w.split("=")[0]===f)?"":' <span class="small">(version 1)</span>')).join("<br>");
const rows=r.results.map(x=>"<tr><td>"+esc(x.measure)+"</td><td>"+esc(x.stratum)+"</td><td>"+x.correct+"/"+x.total+"</td><td>"+pct(x.accuracy)+"</td><td>"+(x.ci?ci(x.ci):"")+"</td><td>"+esc(x.persons)+"</td></tr>").join("");
return "<h3 class=\"small\">Data input</h3>"+dl([["Catalog",esc(r.input.catalog)+(r.input.catalog_sha256?' <span class="small">sha256 '+esc(r.input.catalog_sha256)+"</span>":"")],["Recipe",esc(r.input.recipe)],["Sources",esc(r.input.datasets.join(", ")||"none named")+' <span class="small">from '+esc(r.input.datasets_from)+"</span>"],["Bank",esc(r.input.bank)]])+
"<h3 class=\"small\">Blocks"+(r.blocks_recorded?"":" (the checkpoint names none, so every part is version 1's)")+"</h3><div class=\"small\">"+blocks+"</div>"+
"<h3 class=\"small\">Training and model</h3>"+dl([["Stage",esc(r.stage)],["Epochs",esc(t.epochs)],["Seed",esc(t.seed)],["Parent",esc(t.parent)],["Crops",t.crops_train!=null?esc(t.crops_train)+" training from "+esc(t.persons_train)+" persons; "+esc(t.crops_validation)+" validation from "+esc(t.persons_validation)+" persons":"not recorded"],
["Architecture",esc(m.architecture)],["Parameters",esc(m.parameters)],["Checkpoint sha256",esc(m.checkpoint_sha256||"not recorded")],["Crop size",esc(m.size||"not recorded")],["Model card",m.card?'<a href="'+esc(r.card_url)+'">MODEL.md</a>':"none"]])+
"<h3 class=\"small\">Outcome</h3>"+dl([["Best epoch",r.best?r.best.epoch+": validation "+pct(r.best.accuracy)+" ("+ci(r.best.ci)+", n="+r.best.n+"), training loss "+(r.best.loss==null?"not recorded":r.best.loss.toPrecision(3)):"not recorded"],
["Latency",r.latency?esc(r.latency.median)+" / "+esc(r.latency.p95)+" ms median / p95 ("+esc(r.latency.device)+", batch "+esc(r.latency.batch)+", "+esc(r.latency.frames)+" frames, arm "+esc(r.latency.arm)+")":"not measured"],["Cost",esc(r.cost.ledger||(r.cost.wall_hours+" h wall, "+r.cost.gpu_hours+" GPU h, "+r.cost.jobs+" jobs"))]])+
(rows?'<div class="wrap"><table><thead><tr><th>Measure</th><th>Stratum</th><th>Correct</th><th>Share</th><th>95% interval</th><th>Persons</th></tr></thead><tbody>'+rows+"</tbody></table></div>":"<p class=\"small\">No result rows are recorded.</p>")+
"<h3 class=\"small\">Reproducibility</h3>"+dl([["Commit",esc(p.commit||"not recorded")],["Clean tree",p.clean_tree==null?"not recorded":p.clean_tree?"yes":"no"],["Split disjoint",(p.split_disjoint==null?"not recorded":p.split_disjoint?"yes":"no")+(p.split_check==null?"":" (split-check.json: "+(p.split_check?"disjoint":"NOT disjoint")+")")],
["REFORMS",p.reforms?p.reforms.met+" met, "+p.reforms.declared+" declared, "+p.reforms.missing+" missing":"not recorded"],["CLAIM 2024",p.claim?p.claim.met+" met, "+p.claim.declared+" declared, "+p.claim.missing+" missing":"not recorded"],
["Report complete",p.report.complete==null?"not recorded":p.report.complete?"yes":"no, "+p.report.missing+" items missing"],["Command",'<pre>'+esc(p.command)+"</pre>"],["RUN.json",'<a href="'+esc(D.blob+p.run_json)+'">'+esc(p.run_json)+"</a>"],["Folder",'<a href="'+esc(r.folder_url)+'">'+esc(r.folder)+"</a>"],
["W&amp;B",r.wandb.status==="online"?r.wandb.urls.map(u=>'<a href="'+esc(u)+'">'+esc(u)+"</a>").join("<br>"):esc(r.wandb.status)+": "+esc(r.wandb.why)]])+
(r.note?"<h3 class=\"small\">Note</h3><p class=\"small\">"+esc(r.note)+"</p>":"")+(r.verified?"<p class=\"small\">Verified: "+esc(r.verified)+"</p>":"")}
const open=new Set();
function drawTable(rows){const tb=$("rows");tb.innerHTML="";rows.forEach(r=>{const tr=document.createElement("tr");
tr.innerHTML='<td><button class="link" type="button">'+esc(r.id)+'</button><div class="small">'+esc(r.date)+" "+esc(r.mode)+"</div></td><td>"+esc(r.input.label)+"</td><td>"+esc(namedText(r))+"</td><td>"+esc(r.training.epochs)+"</td><td>"+(r.best?r.best.epoch:"-")+"</td>"+
"<td>"+(r.best?pct(r.best.accuracy)+'<div class="small">'+ci(r.best.ci)+", n="+r.best.n+"</div>":"not recorded")+"</td><td>"+(r.test?pct(r.test.accuracy)+'<div class="small">'+ci(r.test.ci)+", "+r.test.correct+"/"+r.test.total+", "+r.test.persons+" persons</div>":"not measured")+"</td>"+
"<td>"+(r.latency?esc(r.latency.p95)+" ms p95":"not measured")+"</td><td>"+reproCell(r)+"</td><td>"+wandbCell(r)+'</td><td><a href="'+esc(r.report_url)+'">REPORT.md</a></td>';
tb.appendChild(tr);const det=document.createElement("tr");det.className="details"+(open.has(r.id)?" open":"");det.innerHTML='<td colspan="11">'+details(r)+"</td>";tb.appendChild(det);
tr.querySelector("button").onclick=()=>{open.has(r.id)?open.delete(r.id):open.add(r.id);det.classList.toggle("open",open.has(r.id))}})}
function tiles(rows){const tests=rows.filter(r=>r.test),bests=rows.filter(r=>r.best);const top=tests.slice().sort((a,b)=>b.test.accuracy-a.test.accuracy)[0];
$("tiles").innerHTML='<div class="tile"><b>'+rows.length+"</b>of "+D.runs.length+" runs shown</div>"+'<div class="tile"><b>'+(top?pct(top.test.accuracy):"none")+"</b>best test accuracy"+(top?" ("+esc(top.id)+", "+ci(top.test.ci)+")":"")+"</div>"+
'<div class="tile"><b>'+(bests.length?pct(Math.max.apply(null,bests.map(r=>r.best.accuracy))):"none")+"</b>best validation accuracy</div>"+'<div class="tile"><b>'+rows.filter(r=>r.wandb.status==="online").length+"</b>runs online on W&amp;B</div>"}
function draw(){const rows=shown();tiles(rows);drawAccuracy(rows);drawLoss(rows);drawCorr(rows);drawTable(rows)}
// The request panel: one control per part, the recipe and the run's size; the command and the issue follow every change.
const R={};
function control(f){const d=B.defaults[f];let c;
if(B.choices[f]){c=document.createElement("select");B.choices[f].forEach(v=>{const o=document.createElement("option");o.value=v;o.textContent=v+(v===d?" (version 1)":"");c.appendChild(o)});c.value=d}
else if(f==="augment"){c=document.createElement("fieldset");const lg=document.createElement("legend");lg.className="small";lg.textContent="augment: any of these, in this order; none is version 1";c.appendChild(lg);
B.options.augment.forEach(v=>{const l=document.createElement("label");const b=document.createElement("input");b.type="checkbox";b.value=v;b.onchange=update;l.appendChild(b);l.appendChild(document.createTextNode(v));c.appendChild(l)});c.id="r-augment";return c}
else if(B.lists.includes(f)){c=document.createElement("input");c.type="text";c.placeholder="comma-separated";c.value=""}
else if(B.counts.includes(f)){c=document.createElement("input");c.type="number";c.min="0";c.step="1";c.value=String(d)}
else{c=document.createElement("input");c.type="number";c.step="any";c.value=String(d)}
c.id="r-"+f;c.onchange=update;c.oninput=update;return c}
(function buildRequest(){const box=$("req");const rl=document.createElement("label");rl.textContent="recipe (data/recipes/)";const rs=document.createElement("select");rs.id="r-recipe";
[{name:"none",why:"the catalog as it stands, no licence cut"}].concat(D.recipes).forEach(x=>{const o=document.createElement("option");o.value=x.name;o.textContent=x.name;o.title=x.why;rs.appendChild(o)});rs.onchange=update;rl.appendChild(rs);box.appendChild(rl);
[["epochs","1 to "+D.epochs_most,"20","1",String(D.epochs_most)],["seed","0 or more","1","0",""],["hours","the training job's wall time","4","0.1",""]].forEach(x=>{const l=document.createElement("label");l.textContent=x[0]+" ("+x[1]+")";const i=document.createElement("input");i.type="number";i.id="r-"+x[0];i.value=x[2];i.min=x[3];if(x[4])i.max=x[4];i.step=x[0]==="hours"?"any":"1";i.onchange=update;i.oninput=update;l.appendChild(i);box.appendChild(l)});
B.fields.forEach(f=>{const c=control(f);if(c.tagName==="FIELDSET"){box.appendChild(c);return}const l=document.createElement("label");l.textContent=f+(B.settings[f]?" ("+B.settings[f]+")":"");l.appendChild(c);box.appendChild(l)})})();
function chosen(){const b={};B.fields.forEach(f=>{const c=$("r-"+f);if(f==="augment")b[f]=[...c.querySelectorAll("input:checked")].map(i=>i.value);
else if(B.lists.includes(f))b[f]=c.value.split(",").map(s=>s.trim()).filter(s=>s&&s!=="none");else if(B.choices[f])b[f]=c.value;else b[f]=c.value===""?NaN:Number(c.value)});return b}
function words(b){const out=[];B.fields.forEach(f=>{const v=b[f],d=B.defaults[f];const same=Array.isArray(v)?v.join(",")===(d||[]).join(","):(typeof d==="number"?Number(v)===Number(d):v===d);if(!same)out.push(f+"="+(Array.isArray(v)?(v.join(",")||"none"):String(v)))});return out}
function problemsOf(b,epochs,seed,hours){const p=[];B.fields.forEach(f=>{if(B.choices[f]&&!B.choices[f].includes(b[f]))p.push(f+"="+b[f]+" is not one of "+B.choices[f].join(", "))});
(b.augment||[]).forEach(a=>{if(!B.options.augment.includes(a))p.push("augment "+a+" is not one of "+B.options.augment.join(", "))});
B.numbers.concat(B.counts).forEach(f=>{if(!(f in b)||!isFinite(b[f]))p.push(f+" is not a number")});
if("weight_decay" in b&&!(b.weight_decay>=0))p.push("weight_decay is a finite number, 0 or more");
if("warmup_epochs" in b&&!(b.warmup_epochs>=0&&Number.isInteger(b.warmup_epochs)))p.push("warmup_epochs is a whole number of epochs, 0 or more");
if("backbone_lr_scale" in b&&!(b.backbone_lr_scale>0&&b.backbone_lr_scale<=1))p.push("backbone_lr_scale is above 0 and at most 1");
if(b.weight_decay>0&&b.optimiser==="adam")p.push("weight_decay is for adamw; adam's would be L2 in the gradient, which this trainer does not offer");
if("prior" in b){if(!(b.prior_weight>=0))p.push("prior_weight is a finite number, 0 or more");else if((b.prior!=="none")!==(b.prior_weight>0))p.push("prior_weight above 0 goes with prior=level-map, and only there")}
if(B.by_source.includes(b.samples)!==((b.sources||[]).length>0))p.push("sources=a,b goes with samples=only-sources or drop-sources, and only there");
if(new Set(b.sources||[]).size!==(b.sources||[]).length)p.push("sources names a source twice");
if((b.samples===B.by_person)!==(b.per_person>0))p.push("per_person of 1 or more goes with samples=cap-per-person, and only there");
if("per_person" in b&&!(b.per_person>=0&&Number.isInteger(b.per_person)))p.push("per_person is a whole number, 0 or more");
if(!(Number.isInteger(epochs)&&epochs>=1&&epochs<=D.epochs_most))p.push("epochs is a whole number from 1 to "+D.epochs_most);
if(!(Number.isInteger(seed)&&seed>=0))p.push("seed is a whole number, 0 or more");if(!(hours>0))p.push("hours is above 0");return p}
function update(event){const b=chosen(),epochs=Number($("r-epochs").value),seed=Number($("r-seed").value),hours=Number($("r-hours").value),recipe=$("r-recipe").value;
const w=words(b),p=problemsOf(b,epochs,seed,hours);const command=D.flow+" --epochs "+epochs+" --seed "+seed+" --hours "+hours+(recipe!=="none"?" --recipe "+recipe:"")+w.map(x=>" --block "+x).join("");
const title="Experiment: "+(w.length?w.join(" "):"version 1 (no block named)")+", "+epochs+" epochs";
const body=[D.issue.marker,"recipe: "+recipe,"epochs: "+epochs,"seed: "+seed,"hours: "+hours].concat(w.map(x=>"block: "+x)).join("\n")+
"\n\nRequested from the textbook's experiments panel (chapter 35). The workflow reads only the lines above, checks each value against data/recipes/ and src/schwingnet/blocks.py, and answers with the exact flow command and the gate word that queues it; nothing runs on the grid without the owner's word and the number of jobs.\n\nThe command this names:\n\n    "+command+"\n";
const url=D.issue.new+"?"+new URLSearchParams({title:title,labels:D.issue.label,body:body}).toString();
$("cmd").textContent=command;$("problems").innerHTML=p.map(x=>"<div>"+esc(x)+"</div>").join("");const a=$("request");a.href=url;a.setAttribute("aria-disabled",p.length?"true":"false");
$("req-note").textContent=p.length?"The choice does not hold yet; fix the lines above.":(framed?"Opens outside this figure, on the page that embeds it.":"Opens a prefilled issue on GitHub.");
R.payload={type:"schwingnet.experiment",command:command,recipe:recipe,blocks:b,named:w,epochs:epochs,seed:seed,hours:hours,issueUrl:url,title:title,body:body,ok:!p.length,problems:p,
repo:D.repo,workflow:D.workflow,ref:"main",inputs:{recipe:recipe,epochs:String(epochs),seed:String(seed),hours:String(hours),blocks:w.join(" ")},label:title,fallbackUrl:url};
// posted on a person's change and on Request, never on the first draw, so a page that embeds the figure offers nothing until asked
if(event)post(R.payload)}
$("request").addEventListener("click",e=>{if(framed){e.preventDefault();post(Object.assign({},R.payload,{type:"schwingnet.open",href:R.payload.issueUrl,label:"Request this run: "+R.payload.title}))}});
// The page that embeds this figure answers a dispatch it made for the viewer (docs/research/experiments-panel.md, section 4).
addEventListener("message",e=>{let d=e.data;if(!framed||e.source!==window.parent||!d||d.type!=="schwingnet.dispatch.result")return;
$("req-note").textContent=d.ok?"Dispatched as you: the workflow opens the issue, checks the lines and answers with the gate word.":"Not dispatched ("+(d.error||"no reason given")+"); Request this run still works."});
update();draw();addEventListener("resize",draw);
"""


def html_page(data):
    """The self-contained page: the data inlined as JSON, the styles with both themes, the markup
    and the script; no external script, no fetch."""
    blob = json.dumps(data, sort_keys=True, separators=(",", ":")).replace("</", "<\\/")
    return ("<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>The experiments panel</title>"
            f"<style>{STYLE}</style></head><body><main>{BODY}</main><div class=\"tip\" id=\"tip\"></div>"
            f"<script>const DATA={blob};\n{SCRIPT}</script></body></html>\n")


SVG_STYLE = ("text{font:11px system-ui,sans-serif;fill:#0b0b0b}.ink3{fill:#7d7c77}.rule{stroke:#e1e0db}"
             ".test{fill:#2a78d6;stroke:#2a78d6;stroke-width:2}.val{fill:#fcfcfb;stroke:#c2410c;stroke-width:2}.bg{fill:#fcfcfb}"
             "@media (prefers-color-scheme:dark){text{fill:#f0efec}.ink3{fill:#8f8e87}.rule{stroke:#36352f}"
             ".test{fill:#5b9cf0;stroke:#5b9cf0}.val{fill:#1a1a19;stroke:#f08a5a}.bg{fill:#1a1a19}}")


def svg_chart(data):
    """The static drawing beside the page, for the chapter's image line and a reader with no
    script: each run's test accuracy (filled) and best validation accuracy (hollow) with their 95
    percent Wilson intervals."""
    runs = data["runs"]
    W, L, R, row_h, top = 760, 300, 24, 30, 48
    H = top + max(1, len(runs)) * row_h + 44
    x = lambda v: L + (W - L - R) * v
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
           'aria-label="Accuracy of every recorded run with its interval">', f"<style>{SVG_STYLE}</style>",
           f'<rect class="bg" x="0" y="0" width="{W}" height="{H}"/>',
           f'<text x="{L}" y="18" font-weight="600">Every recorded run: accuracy with its 95% Wilson interval</text>',
           f'<text x="{L}" y="32" class="ink3">{"every run is a dry run on the synthetic bank: a record of the workflow, not of SchwingNet" if data["dry_runs_only"] else "a record, not a final value"}</text>']
    for v in (0, 0.25, 0.5, 0.75, 1):
        out.append(f'<line class="rule" x1="{x(v):.1f}" x2="{x(v):.1f}" y1="{top - 4}" y2="{H - 28}"/>')
        out.append(f'<text class="ink3" x="{x(v):.1f}" y="{top - 8}" text-anchor="middle">{int(v * 100)}%</text>')
    if not runs:
        out.append(f'<text x="{L}" y="{top + 18}">No run is recorded yet.</text>')
    for i, run in enumerate(runs):
        y = top + i * row_h + row_h / 2
        words = " ".join(run["named"]) or "version 1"
        text = f"{run['id']} {words}"
        out.append(f'<text x="{L - 8}" y="{y + 4:.1f}" text-anchor="end">{esc(text if len(text) <= 44 else text[:41] + "...")}</text>')
        if run["test"]:
            lo, hi = run["test"]["ci"]
            out.append(f'<line class="test" x1="{x(lo):.1f}" x2="{x(hi):.1f}" y1="{y - 6:.1f}" y2="{y - 6:.1f}"/>')
            out.append(f'<circle class="test" cx="{x(run["test"]["accuracy"]):.1f}" cy="{y - 6:.1f}" r="4.5"/>')
        if run["best"] and run["best"].get("ci"):
            lo, hi = run["best"]["ci"]
            out.append(f'<line class="val" x1="{x(lo):.1f}" x2="{x(hi):.1f}" y1="{y + 7:.1f}" y2="{y + 7:.1f}"/>')
            out.append(f'<circle class="val" cx="{x(run["best"]["accuracy"]):.1f}" cy="{y + 7:.1f}" r="4.5"/>')
    out.append(f'<text class="ink3" x="{L}" y="{H - 10}">test accuracy over all levels (filled) and the best epoch\'s validation accuracy (hollow); '
               f'the interactive figure has the loss curves, the blocks and the request panel</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def figure_record(data):
    """The figure's record in the convention tools/textbook_site.py reads: where it came from, what
    it is drawn from, how to explore it and how it is drawn again."""
    runs = data["runs"]
    synthetic = data["synthetic_runs"]
    notes = (f"Drawn new from committed files by tools/experiments_panel.py: the {len(runs)} recorded run{'s' if len(runs) != 1 else ''} under docs/research/ "
             "(RUN.json, train/checkpoint.json, train/metrics.jsonl, train/MODEL.md, evaluate/results.json, split-check.json, reforms.json, claim.json, "
             "REPORT.md, wandb-sync.json, PROVENANCE.json and NOTE.md where each exists), the ledger, the recipes under data/recipes/ and the blocks of "
             f"src/schwingnet/blocks.py. {'Every one of them is' if synthetic == len(runs) else f'{synthetic} of them are'} "
             f"{'a dry run' if synthetic == len(runs) else 'dry runs'} on the synthetic bank (tools/synthetic_bank.py), "
             "which measures the workflow and not SchwingNet, so every number drawn is a record, not a final value. The blocks of a run recorded before the "
             "blocks existed are version 1's defaults, spelled out as schwingnet.blocks.from_record reads them. A run's W&B column says offline where no key "
             "was found when it ran. The page requests a new combination as an issue labelled experiment and runs nothing: a grid job waits for the owner's "
             "word and the number of jobs. The rendering is tested (tests/test_experiments_panel.py); the loop that fills the panel with runs is a plan.")
    return {
        "id": FIGURE_ID,
        "title": "The experiments panel: every recorded run by its data input, its blocks and its outcome",
        "caption": ("Every recorded run with what it was given (the catalog, the recipe, the sources, the bank), the blocks it chose with version 1's "
                    "defaults spelled out, its loss by epoch, its accuracy with its interval, its model, its reproducibility record and its W&B link; filters by data "
                    "input and by block, a correlation view that groups accuracy by a block's value, and a panel that names a new combination's exact command and "
                    "opens its request."),
        "chapter": "35",
        "grade": "Measured",
        "status": "a record, not a final value",
        "source": {
            "kind": "script",
            "artifact": None,
            "artifact_url": None,
            "made_by": "tools/experiments_panel.py",
            "commit": None,
            "data": [LEDGER, RUNS + "/", RECIPES + "/", BLOCKS_PY],
            "run": None,
            "notes": notes,
        },
        "explore": [
            {"label": "The script", "href": "tools/experiments_panel.py"},
            {"label": "The recorded runs", "href": RUNS + "/"},
            {"label": "The ledger", "href": LEDGER},
            {"label": "The evaluation page, drawn from the same runs", "href": "docs/research/evaluation/README.md"},
            {"label": "The blocks", "href": BLOCKS_PY},
            {"label": "The recipes", "href": RECIPES + "/"},
            {"label": "The loop the panel serves", "href": "docs/research/experiment-framework.md"},
            {"label": "The note on this panel", "href": "docs/research/experiments-panel.md"},
            {"label": "The chapter", "href": CHAPTER},
        ],
        "rerun": {"where": "actions", "command": "python3 tools/experiments_panel.py write", "cost": "CPU, a second", "needs_owner_word": False},
    }


def outputs(root=ROOT):
    """Every file the tool writes, by name, as text."""
    data = panel_data(root)
    return {f"{FIGURE}.html": html_page(data), f"{FIGURE}.json": json.dumps(figure_record(data), indent=1) + "\n", f"{FIGURE}.svg": svg_chart(data)}


def written(root=ROOT):
    """Every file the tool writes, by path from the root: the figure's three files and the issue form."""
    files = {f"{OUT}/{name}": text for name, text in outputs(root).items()}
    files[FORM] = form_text(block_catalog(root), [r["name"] for r in recipes(root)])
    return files


def stale(root=ROOT):
    """The written files that are not what the records give now, or are missing: the figure's files by
    name and the issue form by its path."""
    old = []
    for rel, text in written(root).items():
        path = Path(root) / rel
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            old.append(rel[len(OUT) + 1:] if rel.startswith(OUT + "/") else rel)
    return old


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["write", "check", "runs"])
    parser.add_argument("--root", default=str(ROOT), help="the repository to read and write (a worktree, for a test)")
    parser.add_argument("--request", help="check: a file holding an issue's body or a request's lines; prints the normalised lines and the command, or exits 1 with why")
    args = parser.parse_args(argv)
    root = Path(args.root)
    if args.command == "check" and args.request:
        record, problems = check_request(Path(args.request).read_text(encoding="utf-8"), root)
        for problem in problems:
            print(f"refused: {problem}", file=sys.stderr)
        if problems:
            return 1
        sys.stdout.write(request_lines(record))
        print(request_command(record))
        return 0
    if args.command == "runs":
        print(json.dumps(panel_data(root)["runs"], indent=1, sort_keys=True))
        return 0
    if args.command == "write":
        for rel, text in written(root).items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text, encoding="utf-8")
            print(f"wrote {rel}")
        return 0
    old = stale(root)
    if old:
        print(f"{', '.join(old)}: not what the records give; run python3 tools/experiments_panel.py write", file=sys.stderr)
        return 1
    print(f"{OUT}/{FIGURE}: current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
