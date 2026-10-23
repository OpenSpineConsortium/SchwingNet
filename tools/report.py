"""Write a run's report: the CLAIM 2024 and REFORMS checklists answered, and the data's licences.

Usage:
    python3 tools/report.py write --run <run folder>        # REPORT.md, claim.json, reforms.json
    python3 tools/report.py check --run <run folder> [--complete]
    python3 tools/report.py write-recorded                   # every run under docs/research/v1-demo/runs/
    python3 tools/report.py check-recorded

The owner's ask of 2026-10-23 (issue #153): before training, every run leaves a record that says,
item by item, how far it meets CLAIM 2024 and REFORMS, and which datasets it trained on under which
licence, so a network meant for commercial use can be told from one that needs non-commercial
terms. data/reporting/checklists.json lists the items; each is answered by code from the run's own
files (RUN.json, split-check.json, train/, evaluate/, PROVENANCE.json) or, where only a person can
answer, from data/reporting/study.json. An item is met with its evidence quoted, declared with the
owner's sentence, not applicable with the owner's reason, or missing; nothing is inferred, and a
file a run does not hold makes its items missing, never left out. The licences are read from the
PROVENANCE.json that tools/licences.py provenance writes into the run folder and are never worked
out here. tools/flow.py run writes the report after its last step and tools/flow.py record keeps
it; `check --complete` is the gate for a run whose numbers are to be published, and fails while
any item is missing. Standard library only, so the required check runs it.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKLISTS = ROOT / "data" / "reporting" / "checklists.json"
STUDY = ROOT / "data" / "reporting" / "study.json"
RUNS = ROOT / "docs" / "research" / "v1-demo" / "runs"
OUTPUTS = ("REPORT.md", "claim.json", "reforms.json")
NOT_APPLICABLE = "not applicable:"
STATES = ("met", "declared", "not applicable", "missing")


class ReportError(Exception):
    """What stops the report with a reason a person reads."""


def read_json(path):
    """A JSON file of the run, or None where the run holds none."""
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def read_text(path):
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def model_line(model_md, field):
    """The value of one '- Field: value' line of train/MODEL.md, or empty."""
    prefix = f"- {field}:"
    for line in model_md.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return ""


def load_run(run_dir):
    """Every file of the run the report reads, by role; a missing one is None or empty."""
    run_dir = Path(run_dir)
    record = read_json(run_dir / "RUN.json")
    if record is None:
        raise ReportError(f"{run_dir}: no RUN.json, so this is not a run folder")
    return {
        "dir": run_dir,
        "record": record,
        "split": read_json(run_dir / "split-check.json"),
        "checkpoint": read_json(run_dir / "train" / "checkpoint.json"),
        "model_md": read_text(run_dir / "train" / "MODEL.md"),
        "results": read_json(run_dir / "evaluate" / "results.json"),
        "provenance": read_json(run_dir / "PROVENANCE.json"),
        "exclusions": read_json(run_dir / "exclusions.json"),
        "missing": read_json(run_dir / "missing.json"),
        "covariates": read_json(run_dir / "covariates.json"),
        "has": {name: (run_dir / name).is_file() for name in ("evaluate/confusion.png", "evaluate/per-level.png")},
    }


def short(digest):
    return (digest or "")[:12]


def frames_by_part(source):
    parts = source.get("frames") or {}
    return ", ".join(f"{part} {parts[part]}" for part in sorted(parts)) or "no frames"


# Each code fact answers from the run's files: its evidence, or empty where the run holds none.


def fact_data_sources(run):
    provenance = run["provenance"]
    if not provenance or not provenance.get("sources"):
        return ""
    names = "; ".join(f"{s.get('source')} ({s.get('licence') or 'licence not recorded'})" for s in provenance["sources"])
    return f"PROVENANCE.json, catalog {short(provenance.get('catalog_sha256'))}: {names}"


def fact_data_per_split(run):
    provenance = run["provenance"]
    if not provenance or not provenance.get("sources"):
        return ""
    return "PROVENANCE.json: " + "; ".join(f"{s.get('source')}: {frames_by_part(s)}" for s in provenance["sources"])


def fact_recipe(run):
    provenance = run["provenance"]
    if not provenance:
        return ""
    recipe = provenance.get("recipe")
    if not recipe:
        return f"the whole catalog {short(provenance.get('catalog_sha256'))}, no licence recipe applied (PROVENANCE.json)"
    allowed = ", ".join(recipe.get("allow") or [])
    return f"licence recipe {recipe.get('name')} (classes {allowed}) cut from catalog {short(recipe.get('parent_catalog_sha256'))} (PROVENANCE.json)"


def fact_transforms(run):
    architecture = model_line(run["model_md"], "Architecture")
    return f"train/MODEL.md: {architecture}" if architecture else ""


def fact_split_rule(run):
    record = run["record"]
    return f"persons assigned to train, validation and test by the catalog's salted person hash, catalog {short(record.get('catalog_sha256'))} version {record.get('catalog_version')} (RUN.json); the test part is read only by the evaluator"


def fact_split_disjoint(run):
    split = run["split"]
    if split is None:
        return ""
    if not split.get("disjoint"):
        return ""
    return "disjoint by person and by frame sha256: no person and no frame in two parts (split-check.json)"


def fact_model(run):
    return fact_transforms(run)


def fact_software(run):
    commit = run["record"].get("code_commit")
    return f"the locked pixi environments of pixi.lock at commit {short(commit)}" if commit else ""


def fact_initialization(run):
    weights = run["record"].get("parent_weights")
    initial = model_line(run["model_md"], "Initial weights")
    if weights:
        return f"from weights sha256 {short(weights)} (RUN.json parent_weights)"
    return f"from scratch, no parent weights (RUN.json){'; MODEL.md: ' + initial if initial else ''}"


def fact_training(run):
    record, checkpoint = run["record"], run["checkpoint"]
    if checkpoint is None:
        return ""
    counts = checkpoint.get("counts") or {}
    return f"stage {record.get('stage')}, {record.get('epochs')} epochs, seed {record.get('seed')}; {counts.get('train')} training crops from {counts.get('train_persons')} persons (train/checkpoint.json)"


def fact_model_selection(run):
    checkpoint = run["checkpoint"]
    if checkpoint is None:
        return ""
    accuracy, interval = checkpoint.get("validation_accuracy"), checkpoint.get("validation_ci") or []
    if accuracy is None or len(interval) < 2:
        return ""
    return f"the epoch of best validation accuracy, epoch {checkpoint.get('epoch')}: {accuracy:.3f} ({interval[0]:.3f} to {interval[1]:.3f}, n={checkpoint.get('validation_n')}); no test row read in training (train/checkpoint.json)"


def fact_ensembling(run):
    stage = run["record"].get("stage")
    return f"none: one network for the {stage} stage (RUN.json)" if stage else ""


def result_rows(run):
    results = run["results"]
    return (results or {}).get("rows") or []


def fact_metrics(run):
    rows = result_rows(run)
    if not rows:
        return ""
    measures = sorted({row.get("measure") for row in rows})
    return f"{', '.join(measures)} over {len(rows)} strata on the {run['results'].get('part')} part (evaluate/results.json)"


def fact_uncertainty(run):
    if not result_rows(run):
        return ""
    return "a 95 percent Wilson interval on every row from its correct and n, persons counted per row (evaluate/results.json, evaluate/results.md)"


def fact_internal_evaluation(run):
    results = run["results"]
    if not results:
        return ""
    counts = results.get("counts") or {}
    return f"held-out {results.get('part')} part of the same catalog: {counts.get('crops')} crops, {counts.get('frames')} frames, {counts.get('persons')} persons (evaluate/results.json)"


def fact_performance(run):
    rows = [row for row in result_rows(run) if row.get("stratum") == "all levels"]
    if not rows:
        return ""
    row = rows[0]
    return f"{row.get('measure')} {row.get('correct')}/{row.get('total')} on all levels with its interval, and every stratum beside it (evaluate/results.md)"


def fact_failure_analysis(run):
    found = [name for name, there in run["has"].items() if there]
    return f"the confusion matrix and the per-level accuracy ({', '.join(found)})" if found else ""


def fact_from_file(key, what):
    """A fact whose producer writes a file of its own into the run; none is built yet for some."""

    def answer(run):
        document = run[key]
        if not document:
            return ""
        return f"{key}.json: {document.get('summary') or what}"

    return answer


def fact_code_state(run):
    record = run["record"]
    if not record.get("clean_tree"):
        return ""
    return f"commit {record.get('code_commit')} from a clean tree (RUN.json); the run is refused from a dirty one"


def fact_compute(run):
    jobs = run["record"].get("jobs") or []
    if not jobs:
        return ""
    parts = [f"{j.get('step')} on {j.get('partition')}, {j.get('gpus')} GPU, {j.get('seconds_used')} s, exit {j.get('exit_code')}" for j in jobs]
    return f"{run['record'].get('mode')} mode: " + "; ".join(parts) + " (RUN.json jobs)"


def fact_reproduce(run):
    record = run["record"]
    if not record.get("code_commit"):
        return ""
    weights = " --weights <parent weights>" if record.get("parent_weights") else ""
    return f"at commit {short(record.get('code_commit'))}: python tools/flow.py run --catalog <catalog sha256 {short(record.get('catalog_sha256'))}> --mode {record.get('mode')} --stage {record.get('stage')} --epochs {record.get('epochs')} --seed {record.get('seed')}{weights} --out <runs>"


def fact_outcome_counts(run):
    results = run["results"]
    levels = ((results or {}).get("counts") or {}).get("levels") or {}
    if not levels:
        return ""
    return "test crops per level: " + ", ".join(f"{level} {levels[level]}" for level in sorted(levels)) + " (evaluate/results.json)"


def fact_sample_size(run):
    checkpoint, results = run["checkpoint"], run["results"]
    if checkpoint is None or results is None:
        return ""
    counts, test = checkpoint.get("counts") or {}, results.get("counts") or {}
    return f"train {counts.get('train')} crops from {counts.get('train_persons')} persons, validation {counts.get('validation')} from {counts.get('validation_persons')}, test {test.get('crops')} from {test.get('persons')} (train/checkpoint.json, evaluate/results.json)"


def fact_models_trained(run):
    return f"run {run['record'].get('run_id')}; every run of the flow, failed ones too, has its row in LEDGER.md beside the runs"


CODE_FACTS = {
    "data_sources": fact_data_sources,
    "data_per_split": fact_data_per_split,
    "recipe": fact_recipe,
    "transforms": fact_transforms,
    "split_rule": fact_split_rule,
    "split_disjoint": fact_split_disjoint,
    "model": fact_model,
    "software": fact_software,
    "initialization": fact_initialization,
    "training": fact_training,
    "model_selection": fact_model_selection,
    "ensembling": fact_ensembling,
    "metrics": fact_metrics,
    "uncertainty": fact_uncertainty,
    "internal_evaluation": fact_internal_evaluation,
    "performance": fact_performance,
    "failure_analysis": fact_failure_analysis,
    "exclusions": fact_from_file("exclusions", "the excluded samples with their reasons"),
    "missing_data": fact_from_file("missing", "the missing fields by class"),
    "covariates": fact_from_file("covariates", "the characteristics of each part"),
    "code_state": fact_code_state,
    "compute": fact_compute,
    "reproduce": fact_reproduce,
    "outcome_counts": fact_outcome_counts,
    "sample_size": fact_sample_size,
    "models_trained": fact_models_trained,
}


# What would give a code fact its evidence, said where a run has none, so a gap names its work.
PRODUCERS = {
    "data_sources": "PROVENANCE.json, from tools/licences.py provenance",
    "data_per_split": "PROVENANCE.json, from tools/licences.py provenance",
    "recipe": "PROVENANCE.json, from tools/licences.py provenance",
    "exclusions": "exclusions.json, which no step writes yet: the ingest and bank builders' excluded and unreadable samples with their reasons",
    "missing_data": "missing.json, which no step writes yet: missing fields per class from the catalog",
    "covariates": "covariates.json, which no step writes yet: age, sex, pathology and device per part (tools/covariates.py's census)",
    "split_disjoint": "split-check.json saying disjoint",
    "code_state": "RUN.json from a clean tree",
}


def answer(item, run, study):
    """One item's state and evidence: what the code finds, or what the owner declared."""
    if item["basis"] == "code":
        evidence = CODE_FACTS[item["fact"]](run)
        if evidence:
            return "met", evidence
        return "missing", f"needs {PRODUCERS.get(item['fact'], 'the step that writes it: this run holds none')}"
    text = (study.get(item["fact"]) or "").strip()
    if not text:
        return "missing", f"needs the owner's answer under \"{item['fact']}\" in data/reporting/study.json"
    if text.lower().startswith(NOT_APPLICABLE):
        return "not applicable", text
    return "declared", text


def answered(checklist, run, study):
    rows = []
    for item in checklist["items"]:
        state, evidence = answer(item, run, study)
        rows.append({"id": item["id"], "section": item["section"], "asks": item["asks"], "basis": item["basis"], "fact": item["fact"], "state": state, "evidence": evidence})
    return rows


def tally(rows):
    return {state: sum(1 for row in rows if row["state"] == state) for state in STATES}


def checklists():
    return json.loads(CHECKLISTS.read_text(encoding="utf-8"))


def study_answers():
    return {key: value for key, value in json.loads(STUDY.read_text(encoding="utf-8")).items() if not key.startswith("_")}


def cell(text):
    """Text that cannot break a table row."""
    return " ".join(str(text).split()).replace("|", "/") or "-"


def licence_section(provenance):
    """The licences of every source the run read, as PROVENANCE.json gives them."""
    if not provenance:
        return [
            "## Data and licences",
            "",
            "Not recorded: the run folder holds no PROVENANCE.json (tools/licences.py provenance writes it), so which sources the run read and under which licence is unknown, and so is whether the network may be used commercially.",
        ]
    recipe = provenance.get("recipe")
    lines = [
        "## Data and licences",
        "",
        f"- Commercial use of this network: **{provenance.get('commercial_use', 'unknown')}**; the least permissive class among the sources it trained or chose on: {provenance.get('run_class', 'unknown')}.",
        f"- Recipe: {recipe.get('name') + ' (' + ', '.join(recipe.get('allow') or []) + ')' if recipe else 'none, the whole catalog'}; the recipes this data fits: {', '.join(provenance.get('fits_recipes') or []) or 'none'}.",
        f"- Sources whose licence is not yet classified: {', '.join(provenance.get('unclassified') or []) or 'none'}.",
        *([f"- Caveat: {provenance['caveat']}"] if provenance.get("caveat") else []),
        "",
        "| source | licence | class | commercial | reviewed | frames by part |",
        "|---|---|---|---|---|---|",
    ]
    for source in provenance.get("sources") or []:
        lines.append(f"| {cell(source.get('source'))} | {cell(source.get('licence'))} | {cell(source.get('class'))} | {cell(source.get('commercial'))} | {cell(source.get('reviewed'))} | {cell(frames_by_part(source))} |")
    return lines


def checklist_section(name, rows):
    counts = tally(rows)
    lines = [f"## {name}", "", f"{len(rows)} items: {counts['met']} met by the run's files, {counts['declared']} declared, {counts['not applicable']} not applicable, {counts['missing']} missing.", "", "| item | section | asks | answered by | state | evidence |", "|---|---|---|---|---|---|"]
    for row in rows:
        lines.append(f"| {row['id']} | {cell(row['section'])} | {cell(row['asks'])} | {row['basis']} ({row['fact']}) | {row['state']} | {cell(row['evidence'])} |")
    return lines


def report_markdown(run, claim_rows, reforms_rows):
    record = run["record"]
    missing = [f"CLAIM {r['id']}" for r in claim_rows if r["state"] == "missing"] + [f"REFORMS {r['id']}" for r in reforms_rows if r["state"] == "missing"]
    lines = [
        f"# Report of run {record.get('run_id')}",
        "",
        f"Written by `python3 tools/report.py write` from this folder's files and data/reporting/study.json; do not edit by hand. Commit {short(record.get('code_commit'))}, {'clean tree' if record.get('clean_tree') else 'DIRTY tree'}, catalog {short(record.get('catalog_sha256'))} version {record.get('catalog_version')}, stage {record.get('stage')}, seed {record.get('seed')}, {record.get('epochs')} epochs, started {record.get('started_at')} in {record.get('mode')} mode.",
        "",
        f"Complete: **{'yes' if not missing else 'no'}**" + (f"; missing {len(missing)}: {', '.join(missing)}." if missing else "."),
        "",
        "A met item quotes the file that shows it; a declared one is the owner's sentence in data/reporting/study.json, which the code checks is there but cannot judge; a missing one is work to do before the numbers are published (`python3 tools/report.py check --run <folder> --complete`).",
        "",
        *licence_section(run["provenance"]),
        "",
        *checklist_section("CLAIM 2024", claim_rows),
        "",
        *checklist_section("REFORMS", reforms_rows),
    ]
    return "\n".join(lines) + "\n"


def render(run_dir):
    """The three files of the report, by name, from the run and the study."""
    run = load_run(run_dir)
    lists, study = checklists(), study_answers()
    claim_rows = answered(lists["claim"], run, study)
    reforms_rows = answered(lists["reforms"], run, study)
    run_id = run["record"].get("run_id")
    study_sha = hashlib.sha256(STUDY.read_bytes()).hexdigest()

    def document(checklist, rows):
        return json.dumps({"run_id": run_id, "checklist": checklist["name"], "source": checklist["source"], "study_sha256": study_sha, "tally": tally(rows), "items": rows}, indent=1) + "\n"

    return {
        "REPORT.md": report_markdown(run, claim_rows, reforms_rows),
        "claim.json": document(lists["claim"], claim_rows),
        "reforms.json": document(lists["reforms"], reforms_rows),
    }


def write(run_dir):
    for name, text in render(run_dir).items():
        (Path(run_dir) / name).write_text(text, encoding="utf-8")
    return 0


def stale(run_dir):
    """The report files that are not what the run and the study give now."""
    return [name for name, text in render(run_dir).items() if read_text(Path(run_dir) / name) != text]


def missing_items(run_dir):
    found = []
    for name in ("claim.json", "reforms.json"):
        document = json.loads(read_text(Path(run_dir) / name) or "{}")
        found += [f"{document.get('checklist')} {row['id']}" for row in document.get("items", []) if row["state"] == "missing"]
    return found


def shown(run_dir):
    """A run folder as a person reads it: relative to the repository where it lies inside it."""
    path = Path(run_dir).resolve()
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(run_dir)


def check(run_dir, complete=False):
    behind = stale(run_dir)
    if behind:
        print(f"{shown(run_dir)}: {', '.join(behind)} not what the run gives; run python3 tools/report.py write --run {shown(run_dir)}", file=sys.stderr)
        return 1
    if complete:
        gaps = missing_items(run_dir)
        if gaps:
            print(f"{shown(run_dir)}: incomplete, {len(gaps)} items missing: {', '.join(gaps)}", file=sys.stderr)
            return 1
    print(f"{shown(run_dir)}: report current" + (", complete" if complete else ""))
    return 0


def recorded_runs():
    return sorted(path.parent for path in RUNS.glob("*/RUN.json"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("write", "check"):
        command = sub.add_parser(name)
        command.add_argument("--run", required=True)
        if name == "check":
            command.add_argument("--complete", action="store_true", help="fail while any item is missing")
    sub.add_parser("write-recorded")
    sub.add_parser("check-recorded")
    args = parser.parse_args(argv)
    try:
        if args.command == "write":
            return write(args.run)
        if args.command == "check":
            return check(args.run, args.complete)
        runs = recorded_runs()
        if args.command == "write-recorded":
            return max([write(run) for run in runs], default=0)
        return max([check(run) for run in runs], default=0)
    except ReportError as error:
        print(f"report: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
