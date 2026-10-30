"""Write a run's report: the CLAIM 2024 and REFORMS checklists answered, and the data's licences.

Usage:
    python3 tools/report.py write --run <run folder>        # REPORT.md, claim.json, reforms.json
    python3 tools/report.py check --run <run folder> [--complete]
    python3 tools/report.py write --study drr-domain-gap --run <study run folder>
    python3 tools/report.py check --study drr-domain-gap --run <study run folder> [--complete]
    python3 tools/report.py write --study flux-realism --run <realism run folder>
    python3 tools/report.py write --study autoanatomist-screen --run <screen chain folder>
    python3 tools/report.py write-recorded                   # every run under docs/research/v1-demo/runs/,
                                                             # every study run under docs/research/drr-domain-gap/runs/
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

Study mode, the owner's ask of 2026-10-27 for a report of the DRR domain-gap study that satisfies
these standards: a study that trains no network is reported from its recorded folder,
docs/research/<study>/runs/<prepare job>/, which holds BENCH.md, the bench report as the grid's
gate printed it, and summary.txt, whose first lines are the record lines the study writes. Its code
answers read those record lines, the summary's own lines and the groups table whose digest the
record names, the frozen pre-registration where the record names the one the study's design
answers restate, and the README's record of what each run does not support; its owner's answers come from data/reporting/studies/<study>.json; an item a
training run answers by code is answered for the study's encoders and two-sample tests, or is not
applicable, with the reason quoted, where the study's design leaves out what it asks about.
"""

import argparse
import hashlib
import json
import re
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
    return declared(item["fact"], study, "data/reporting/study.json")


def declared(fact, answers, where):
    """The owner's sentence for a fact, or missing while the field in that file is empty."""
    text = (answers.get(fact) or "").strip()
    if not text:
        return "missing", f"needs the owner's answer under \"{fact}\" in {where}"
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


def study_answers(path=None):
    """The owner's answers of a study file, the training study's unless another is named."""
    path = STUDY if path is None else Path(path)
    return {key: value for key, value in json.loads(path.read_text(encoding="utf-8")).items() if not key.startswith("_")}


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


def rendered(run_dir, study=None):
    """The report's files for a training run, or for a recorded run of the study named."""
    return render_study(study, run_dir) if study else render(run_dir)


def write(run_dir, study=None):
    for name, text in rendered(run_dir, study).items():
        (Path(run_dir) / name).write_text(text, encoding="utf-8")
    return 0


def stale(run_dir, study=None):
    """The report files that are not what the run and the study give now."""
    return [name for name, text in rendered(run_dir, study).items() if read_text(Path(run_dir) / name) != text]


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


def check(run_dir, complete=False, study=None):
    behind = stale(run_dir, study)
    if behind:
        named = f" --study {study}" if study else ""
        print(f"{shown(run_dir)}: {', '.join(behind)} not what the run gives; run python3 tools/report.py write{named} --run {shown(run_dir)}", file=sys.stderr)
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


# --- study mode: a recorded study that trains no network ------------------------------------------
#
# The DRR domain-gap study (tools/domain_gap.py, docs/research/drr-domain-gap/README.md) reads fixed
# encoders and fits two-sample classifiers as test statistics; what leaves the grid is its bench
# report and its summary. A recorded run of it is a folder under the study's runs/, named by its
# prepare job, holding BENCH.md and summary.txt, and groups.json too where the recorder kept the
# table the run read because the repository's has moved on since. A code answer reads only the
# record lines at the head of summary.txt, the summary's own lines in the shapes
# tools/domain_gap.py's summary_lines writes, the table whose digest the record names, and BENCH.md;
# a record line that is absent or not in its exact form makes the items it answers missing.

LICENCES = ROOT / "data" / "licences.json"
STUDY_FILES = ("BENCH.md", "summary.txt")
SUMMARY_LINES = 85  # what the bench report carries of a summary (tools/domain_gap.py, RECORD_LINES + LINE_BUDGET)

# How the DRR domain-gap study answers each item: ("code", fact) is read from the recorded folder,
# the groups table it names and the frozen design by STUDY_FACTS, ("declared", fact) is the owner's
# sentence in the study's answers file. The owner's ask of 2026-10-29 at 03:35 UTC, "why would I
# answer these question instead of having a real meta flow run generate them?", moved to code every
# item the study's own files answer; what is left for the owner is what no file of the study says,
# the paper's title, abstract and background, the study's design in the checklist's terms (whether
# it is retrospective, which no file of the study says), how the real corpora were acquired (the
# files record the render groups' recipe and no real corpus's protocol), why the study's classifiers
# are the ones it uses, the data's de-identification, the demographic and clinical characteristics
# of the cases, which the study does not record, so that whether the item applies is the owner's to
# say, the implications, what will be made available, the funding, and how far the findings reach
# beyond the groups read. Every item not listed takes the checklist's basis, as for a training run.
DRR_GAP_ITEMS = {
    "claim": {
        "4": ("code", "aims"), "5": ("declared", "study_design"), "6": ("code", "goal"),
        "7": ("code", "sources"), "8": ("code", "inclusion"), "9": ("code", "transforms"), "10": ("code", "subsets"),
        "12": ("code", "missing_data"), "13": ("declared", "acquisition"),
        "14": ("code", "no_reference_standard"), "15": ("code", "no_reference_standard"),
        "16": ("code", "no_annotation"), "17": ("code", "no_annotation"), "18": ("code", "no_raters"),
        "19": ("code", "partitions"), "20": ("code", "disjoint"), "21": ("code", "intended_size"),
        "22": ("code", "instruments"), "23": ("code", "software"), "24": ("code", "initialization"),
        "25": ("code", "training"), "26": ("code", "no_model_selection"), "27": ("code", "ensembling"),
        "28": ("code", "metrics"), "29": ("code", "uncertainty"), "30": ("code", "robustness"),
        "31": ("code", "explainability"), "32": ("code", "internal_evaluation"),
        "33": ("code", "no_external_model"), "34": ("code", "no_trial"), "35": ("code", "exclusions"),
        "36": ("declared", "characteristics"), "37": ("code", "endpoints"), "38": ("code", "no_diagnosis"),
        "39": ("code", "failure_analysis"), "40": ("code", "limitations"), "42": ("code", "protocol"),
    },
    "reforms": {
        "1a": ("code", "population"), "1b": ("code", "population_rationale"), "1c": ("code", "ml_rationale"),
        "2a": ("code", "sources"), "2b": ("code", "code_state"), "2c": ("code", "compute"),
        "2d": ("code", "reproduce"), "2e": ("code", "reproduce"), "3a": ("code", "sources_per_group"),
        "3b": ("code", "sampling_frame"), "3c": ("code", "fitness"),
        "3d": ("code", "outcome"), "3e": ("code", "sample_size"), "3f": ("code", "missing_data"),
        "3g": ("code", "representativeness"),
        "4a": ("code", "exclusions"), "4b": ("code", "undecoded"), "4c": ("code", "transforms"),
        "5a": ("code", "models_trained"), "5b": ("declared", "model_rationale"), "5c": ("code", "partitions"),
        "5d": ("code", "no_model_selection"), "5e": ("code", "no_tuning"), "5f": ("code", "baselines"),
        "6a": ("code", "preprocessing_fit"), "6b": ("code", "disjoint"), "6c": ("code", "feature_legitimacy"),
        "7a": ("code", "metrics"), "7b": ("code", "uncertainty"), "7c": ("code", "statistical_tests"),
    },
}

def tool_module(name):
    """A module of tools/ loaded from its file, so the report finds it whether it runs as a script
    or a test loads it by its path."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(f"schwingnet_tool_{name}", ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The FluXray reproduction (docs/research/flux-realism/PREREG.md) keeps its items, its facts, how its
# run folder is read and its page in a module of its own, since its folder is flows/realism.py's
# RECORD.json and the files it names, not a bench report and a summary.
REALISM = tool_module("realism_report")
# The auto-anatomist screen (docs/research/autoanatomist-screen/PREREG.md) the same way: its folder is a
# chain of flows/autoanatomist.py, RECORD.json and the trials' and the join's files it names.
AUTOANATOMIST = tool_module("autoanatomist_report")

STUDIES = {
    "drr-domain-gap": {
        "answers": ROOT / "data" / "reporting" / "studies" / "drr-domain-gap.json",
        "runs": ROOT / "docs" / "research" / "drr-domain-gap" / "runs",
        "groups": ROOT / "data" / "domain_gap" / "groups.json",
        "prereg": ROOT / "docs" / "research" / "drr-domain-gap" / "PREREG.md",
        # The pre-registration the design answers restate, by the first 16 hex of its sha256: the
        # file frozen on 2026-10-27, which both recorded runs read.
        "design": "3ca1-b6b7-aea6-0f00",
        "items": DRR_GAP_ITEMS,
        # The pre-registered primary endpoints (README section 4): FleXray's physical render, the
        # same from the CT alone and FluXray, each against pooled fluoroscopy and pooled film in
        # FleXray's space, read inversion-invariant.
        "primary_space": "flexray",
        "endpoints": ("flexray_drr", "flexray_drr_ct", "fluxray"),
        "families": ("fluoroscopy", "film"),
        # The pair whose word is the study's verdict (tools/domain_gap.py, REPLICATION_PAIRS[0]).
        "verdict_pair": ("flexray_replica", "flexray_reference"),
        # The spaces and readings the design reads (PREREG.md section 3), as the summary names them.
        "readings": ("flexray", "flexray_as_stored", "imagenet", "physics"),
        # Where each recorded run's review writes what the run does not support (section 6).
        "readme": ROOT / "docs" / "research" / "drr-domain-gap" / "README.md",
    },
    "flux-realism": {
        "answers": ROOT / "data" / "reporting" / "studies" / "flux-realism.json",
        "runs": ROOT / "docs" / "research" / "flux-realism" / "runs",
        "prereg": REALISM.PREREG,
        "items": REALISM.ITEMS,
        "load": REALISM.load,
        "facts": REALISM.FACTS,
        "markdown": REALISM.markdown,
        "error": REALISM.RealismReportError,
    },
    "autoanatomist-screen": {
        "answers": ROOT / "data" / "reporting" / "studies" / "autoanatomist-screen.json",
        "runs": ROOT / "docs" / "research" / "autoanatomist-screen" / "runs",
        "prereg": AUTOANATOMIST.PREREG,
        "items": AUTOANATOMIST.ITEMS,
        "load": AUTOANATOMIST.load,
        "facts": AUTOANATOMIST.FACTS,
        "markdown": AUTOANATOMIST.markdown,
        "error": AUTOANATOMIST.AutoanatomistReportError,
    },
}

# The record lines, in the forms the study writes them after grid/redact.sed's rules
# (schwingnet.domain_gap.safe_line): one form for each kind, two for the jobs, since a serial run
# writes the one job it ran where the grid's array writes its three. A digest is its first 16 hex
# digits in four groups of four (tools/domain_gap.py, short_digest), since the filter would split
# a run of eight digits that reads as a date; it is compared with its dashes taken out. A job is
# its Slurm number, or local where a step ran outside Slurm; the array is none where no task
# reported, or every array job a task ran under.
HEX7, COUNT, SECONDS = "[0-9a-f]{7}", "[0-9]+", "[0-9]+(?:[.][0-9]+)?"
HEX16 = "[0-9a-f]{4}(?:-[0-9a-f]{4}){3}"
JOB = rf"{COUNT}(?:_{COUNT})?|local|unknown"
ARRAY = rf"{COUNT}(?:, {COUNT})*|none"
GPUS = r"GPUs (?P<gpu>\S(?:.*\S)?) x(?P<gpus>[0-9]+)"
SECONDS_PARTS = ("render", "plan", "images", "features", "heads", "analysis", "units", "figures")
SECONDS_TAILS = {"analysis": " [(]wall[)]", "units": " [(]summed[)]"}
RECORD_FORMS = {
    "study": (rf"study (?P<study>[a-z0-9-]+); commit (?P<commit>{HEX7}); tree (?P<tree>clean|dirty); seed (?P<seed>{COUNT});"
              rf" plan (?P<plan>{HEX16}); groups[.]json (?P<groups>{HEX16}|none); PREREG (?P<prereg>{HEX16}|none); code (?P<code>{HEX16})",),
    "jobs": (rf"jobs prepare (?P<prepare>{JOB}), array (?P<array>{ARRAY}) [(](?P<tasks>{COUNT}) tasks[)], merge (?P<merge>{JOB}); {GPUS}",
             rf"jobs run (?P<run>{JOB}); {GPUS}"),
    "units": (rf"units (?P<done>{COUNT}) of (?P<total>{COUNT}) done, (?P<failed>{COUNT}) failed; mmd backend (?P<backend>torch-cuda|numpy|mixed [a-z/-]+)",),
    "seconds": ("seconds " + ", ".join(f"{part} (?P<{part}>{SECONDS}){SECONDS_TAILS.get(part, '')}" for part in SECONDS_PARTS),),
    "environment": (r"environment (?P<pins>\S(?:.*\S)?)",),
}
RECORD_LINES = {kind: tuple(re.compile(form) for form in forms) for kind, forms in RECORD_FORMS.items()}
RECORD_HEAD = "record: "

# The summary's own lines, in the shapes tools/domain_gap.py's summary_lines writes them.
SUMMARY = {
    "header": re.compile(r"drr gap: (?P<images>[0-9]+) images, (?P<groups>[0-9]+) groups, W&B (?P<wandb>.*)"),
    "group": re.compile(r"group (?P<id>\S+) (?P<family>\S+) found (?P<found>[0-9]+) chosen (?P<chosen>[0-9]+)"
                        r" decoded (?P<decoded>[0-9]+) persons (?P<persons>[0-9]+)(?P<by_file> persons by file)?"
                        r"(?: undecoded (?P<undecoded>[0-9]+))?"),
    "skipped": re.compile(r"group (?P<id>\S+) (?P<family>\S+) skipped, (?P<reason>.*)"),
    "folded": re.compile(r"groups counted as (?P<head>\S+): (?P<ids>\S+(?: \S+)*)"),
    "space": re.compile(r"space (?P<key>\S+) dim (?P<dim>[0-9]+) rows (?P<rows>[0-9]+) spread \S+ pca64 \S+"),
    "space_not_run": re.compile(r"space (?P<key>\S+) not run, (?P<reason>.*)"),
}
INTERVAL = re.compile(r" auc \S+ \[\S+, \S+\]")
BASELINE = re.compile(r" (?:calibration split-half auc median |real-real auc median |fluoroscopy vs film auc )")
# A space's split-half nulls: the counts on one line, the flagged groups' names on lines after it
# (tools/domain_gap.py, calibration_summary); a flagged group's contrasts in the space are not read
# (docs/research/drr-domain-gap/DEVIATIONS.md, item 8).
CALIBRATION = re.compile(r" calibration split-half auc median \S+ range \S+ to \S+ over [0-9]+, mmd flagged (?P<count>[0-9]+),"
                         r" auc interval above half (?P<above>[0-9]+)(?P<nulls_in_family>, nulls in the mmd q family)?")
FLAGGED = " calibration flagged "
# The measures a contrast line can carry, each by the words that show it.
MEASURES = (
    ("the logistic two-sample AUC with its interval", INTERVAL),
    ("its permutation p", re.compile(r"\] p \S")),
    ("the 15-nearest-neighbour AUC", re.compile(r" knn \S")),
    ("the MMD's permutation p", re.compile(r" mmd p \S")),
    ("its Benjamini-Hochberg q", re.compile(r" mmd p \S+ q \S")),
    ("FD64", re.compile(r" fd64 \S")),
    ("KID64", re.compile(r" kid64 \S")),
    ("the gap ratio", re.compile(r" ratio \S")),
    ("precision, recall, density and coverage", re.compile(r" prdc \S+ \S+ \S+ \S+")),
)
BENCH_HEAD = re.compile(r"# bench (?P<bench>\S+): job (?P<job>[0-9]+) on (?P<host>\S+), commit (?P<commit>[0-9a-f]{7}), (?P<began>.+) UTC")
BENCH_EXIT = re.compile(r"- exit (?P<rc>[0-9]+) at (?P<at>.+) UTC")
# The run log the merge writes into BENCH.md since 2026-10-28 (grid/drr-gap.sbatch, run_log): a line
# that opens it, then its lines indented by two spaces, each a date and time UTC and what a step
# noted then; or one line saying why there is none.
BENCH_RUNLOG = "- run log, UTC: "
BENCH_NO_RUNLOG = re.compile(r"- run log: (?P<why>.+)")
RUNLOG_FROM = "2026-10-28"  # the day the study began writing its run log, as BENCH.md's header dates a run
RUNLOG_TIME = re.compile(r"(?P<at>[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}) \S.*")


def record_of(lines, study):
    """The record lines at the head of summary.txt: each kind's fields where its one line reads in
    its form, why not where it does not (absent, given twice, not in its form, another study's),
    the kinds the report does not read, and the summary's lines after them."""
    head = 0
    while head < len(lines) and lines[head].startswith(RECORD_HEAD):
        head += 1
    given = {}
    for line in lines[:head]:
        text = line[len(RECORD_HEAD):]
        given.setdefault(text.split(" ", 1)[0], []).append(text)
    fields, problems = {}, {}
    for kind, forms in RECORD_LINES.items():
        found = given.get(kind, [])
        match = next((m for m in (form.fullmatch(found[0]) for form in forms) if m), None) if len(found) == 1 else None
        if match:
            fields[kind] = match.groupdict()
        else:
            problems[kind] = "absent" if not found else f"given {len(found)} times" if len(found) > 1 else "not in its form"
    if "study" in fields and fields["study"]["study"] != study:
        problems["study"] = f"names study {fields.pop('study')['study']}"
    return fields, problems, sorted(set(given) - set(RECORD_LINES)), lines[head:]


def summary_of(lines):
    """The summary's own lines: the header, the verdict and render lines, every group's counts (a
    group counted as another taking that group's) and each space's indented lines under it."""
    found = {"header": None, "verdicts": [], "renders": [], "groups": {}, "folded": {}, "spaces": {}}
    space = None
    for line in lines:
        if line.startswith(" "):
            if space is not None:
                space["lines"].append(line)
            continue
        space = read_top_line(line, found)
    for member, head in found["folded"].items():
        if head in found["groups"]:
            found["groups"][member] = dict(found["groups"][head], id=member, counted_as=head)
    return found


def read_top_line(line, found):
    """One unindented summary line into found; the space it opens, or None."""
    shapes = {name: SUMMARY[name].fullmatch(line) for name in SUMMARY}
    if shapes["header"]:
        found["header"] = shapes["header"].groupdict()
    elif line.startswith("replication"):
        found["verdicts"].append(line)
    elif line.startswith("render "):
        found["renders"].append(line)
    elif shapes["group"] or shapes["skipped"]:
        match = shapes["group"] or shapes["skipped"]
        found["groups"][match["id"]] = match.groupdict()
    elif shapes["folded"]:
        found["folded"].update(dict.fromkeys(shapes["folded"]["ids"].split(), shapes["folded"]["head"]))
    elif shapes["space"] or shapes["space_not_run"]:
        match = shapes["space"] or shapes["space_not_run"]
        found["spaces"][match["key"]] = space = {**match.groupdict(), "lines": []}
        return space
    return None


def bench_of(text):
    """BENCH.md read for what the report quotes: the job's first line, its FAILED lines and its
    exit; a report in another shape gives none of them and refuses nothing."""
    lines = text.splitlines()
    heads = [m.groupdict() for m in map(BENCH_HEAD.fullmatch, lines) if m]
    ends = [m.groupdict() for m in map(BENCH_EXIT.fullmatch, lines) if m]
    return {"header": heads[0] if heads else None, "exit": ends[-1] if ends else None,
            "failed": [line[2:] for line in lines if line.startswith("- FAILED")],
            **run_log_of(lines, heads[0] if heads else None)}


def run_log_of(lines, header=None):
    """BENCH.md's run log: its indented lines under its opening line, the last such section where
    a report holds two, with the times of its first and last timed lines; or why it has none, a
    report from before the study logged as it ran saying nothing of one."""
    opens = [i for i, line in enumerate(lines) if line.startswith(BENCH_RUNLOG)]
    if not opens:
        said = [m["why"] for m in map(BENCH_NO_RUNLOG.fullmatch, lines) if m]
        return {"runlog": None, "runlog_span": None, "runlog_why": said[-1].rstrip(".") if said else no_run_log_why(header)}
    body = []
    for line in lines[opens[-1] + 1:]:
        if not line.startswith("  "):
            break
        body.append(line[2:])
    times = [m["at"] for m in map(RUNLOG_TIME.fullmatch, body) if m]
    return {"runlog": body, "runlog_why": "", "runlog_span": (times[0], times[-1]) if times else None}


def no_run_log_why(header):
    """Why a BENCH.md that says nothing of a run log has none, as far as its header tells: a run
    begun before the study wrote one, or, where the header dates it later or gives no date, that
    the report carries no run log line, and no more."""
    if header and header["began"] < RUNLOG_FROM:
        return f"BENCH.md carries no run log: the run began {header['began']} UTC, before the study wrote one ({RUNLOG_FROM})"
    return "BENCH.md carries no run log line" + (f", though the run began {header['began']} UTC" if header else "")


def load_study(name, run_dir):
    """Every file of a recorded study run the report reads; a folder without BENCH.md and
    summary.txt is not one, and a summary longer than the bench report carries is not as the grid
    printed it."""
    run_dir, config = Path(run_dir), STUDIES[name]
    for file in STUDY_FILES:
        if not (run_dir / file).is_file():
            raise ReportError(f"{run_dir}: no {file}, so this is not a recorded {name} run (it holds BENCH.md and summary.txt)")
    lines = read_text(run_dir / "summary.txt").splitlines()
    if len(lines) > SUMMARY_LINES:
        raise ReportError(f"{run_dir}: summary.txt holds {len(lines)} lines, more than the {SUMMARY_LINES} the bench report carries")
    fields, problems, unknown, body = record_of(lines, name)
    run = {"dir": run_dir, "name": name, "config": config, "record": fields, "problems": problems, "unknown": unknown,
           "body": summary_of(body), "bench": bench_of(read_text(run_dir / "BENCH.md")), "register": read_json(LICENCES) or {}}
    run["table"], run["table_note"] = table_of(run)
    return run


def table_of(run):
    """The groups table the run read and where it was read: this folder's groups.json where the
    recorder kept one, else the repository's, either only with the digest the record names; else
    None and why."""
    gap = needs_lines(run, ("study",))
    if gap:
        return None, gap
    named = run["record"]["study"]["groups"]
    if named == "none":
        return None, "needs the groups table the run read: the record names none (groups.json none)"
    own = run["dir"] / "groups.json"
    path = own if own.is_file() else Path(run["config"]["groups"])
    where = "this folder's groups.json" if own.is_file() else shown(path)
    if not path.is_file():
        return None, f"needs the groups table the record names, {named}: {where} is not there"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    if digest != undashed(named):
        return None, f"needs the groups table the record names, {named}: {where} is {dashed(digest)}, so the table the run read is not here (keep it in the run folder as groups.json)"
    table = json.loads(path.read_text(encoding="utf-8"))
    return table, f"{where}, version {table.get('version')}, sha256 {named} as the record names it"


def undashed(digest):
    """A record's digest as the hex it stands for, its four groups joined."""
    return digest.replace("-", "")


def dashed(digest):
    """Sixteen hex digits in the record's four groups of four."""
    return "-".join(digest[i:i + 4] for i in range(0, len(digest), 4))


def sources_of(group):
    """The source ids a group of the table reads: its index sources, else the first part of its
    folder, the name the data root keeps a source under."""
    if group.get("index_sources"):
        return list(group["index_sources"])
    folder = group.get("folder") or ""
    return [folder.split("/")[0]] if folder else []


def register_entry(source, register):
    """A source id's entry in data/licences.json through its alias, as text, or that it has none."""
    key = (register.get("aliases") or {}).get(source, source)
    entry = (register.get("sources") or {}).get(key)
    if entry is None:
        return None
    name = source if key == source else f"{source} as {key}"
    return f"{name}: {entry.get('class')}, reviewed {entry.get('reviewed')}"


# Each study fact answers one or more items from the recorded folder: a state and its evidence.


def met(evidence):
    return "met", evidence


def missing(why):
    return "missing", why


def needs_lines(run, kinds):
    """Why the record lines of these kinds cannot answer, or empty where every one was read."""
    gaps = [f"'record: {kind} ...' ({run['problems'][kind]})" for kind in kinds if kind in run["problems"]]
    if not gaps:
        return ""
    return f"needs summary.txt's record line{'s' if len(gaps) > 1 else ''} " + " and ".join(gaps)


def recorded(*kinds):
    """A study fact that reads these record lines: missing, naming the lines, until each is read."""

    def wrap(fact):
        def answer(run):
            gap = needs_lines(run, kinds)
            return missing(gap) if gap else fact(run)

        answer.__doc__ = fact.__doc__
        return answer

    return wrap


def at_commit(run):
    return f"tools/domain_gap.py at commit {run['record']['study']['commit']}"


def prereg_gap(run):
    """Why the pre-registration the record names is not the study's frozen PREREG.md, or empty
    where it is (the first 16 hex of the file's sha256) or the record names none, which the
    answers that read it say in their own words."""
    named, path = run["record"]["study"]["prereg"], Path(run["config"]["prereg"])
    if named == "none":
        return ""
    if not path.is_file():
        return f"the record names PREREG {named}, and {shown(path)} is not there to hold it to"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    if digest != undashed(named):
        return f"the record names PREREG {named}, which is not the frozen {shown(path)} ({dashed(digest)}): the run read another design"
    return ""


def not_applicable(run, reason):
    """An item whose object the study's design leaves out, with the reason and the record it is read for."""
    study = run["record"]["study"]
    return "not applicable", f"Not applicable: {reason} (summary.txt record: study {study['study']}, commit {study['commit']}, code {study['code']})"


def no_group_lines():
    return missing("needs summary.txt's group lines: it holds none")


def unfinished(run):
    """Why the study's results are partial, or empty where the record says every unit is done."""
    gap = needs_lines(run, ("units",))
    if gap:
        return gap
    units = run["record"]["units"]
    if int(units["done"]) != int(units["total"]) or int(units["failed"]):
        return f"the record says units {units['done']} of {units['total']} done, {units['failed']} failed, so the results are partial"
    return ""


def contrast_lines(run):
    """Every contrast line of every space, (space, line): an AUC with its interval."""
    return [(key, line) for key, space in run["body"]["spaces"].items() for line in space["lines"] if INTERVAL.search(line)]


def counted(number, noun):
    return f"{number} {noun}" + ("" if number == 1 else "s")


def ordered_groups(run):
    """The summary's groups in the table's order where the table is read, the rest after them."""
    groups, table = run["body"]["groups"], run["table"]
    order = [g["id"] for g in table["groups"] if g["id"] in groups] if table else []
    return [groups[group] for group in order + [group for group in groups if group not in order]]


def undecoded_counts(groups):
    return [(g["id"], int(g["undecoded"])) for g in groups.values() if g.get("undecoded")]


def numbers_of(groups, key):
    return sorted({int(g[key]) for g in groups if isinstance(g.get(key), int)})


@recorded("study")
def study_sources(run):
    """CLAIM 7, REFORMS 2a: the groups table the record names and the sources its groups read."""
    table = run["table"]
    if table is None:
        return missing(run["table_note"])
    ids = sorted({source for group in table["groups"] for source in sources_of(group)})
    return met(f"{run['table_note']}: {len(table['groups'])} groups over {len(ids)} sources, {', '.join(ids)}; each group's licence, as the table records it, is in the data and licences section")


@recorded("study")
def study_transforms(run):
    """CLAIM 9, REFORMS 4c: every image's one path from its file to the encoders' input."""
    return met("every image, synthetic or real, decoded to floats (DICOM through its modality LUT, MONOCHROME1 turned bone-bright, a cine's middle frame), windowed to its own 0.5 and 99.5 percentiles, cut to the centre square of 0.9 of its shorter side and resized to 256 by area; each feature space reads the mean of its features of the image and of its inverse, and FleXray's space also the image as stored"
               f" ({at_commit(run)}, README section 3)")


@recorded("study")
def study_subsets(run):
    """CLAIM 10: how each group's images were chosen."""
    table = run["table"]
    if table is None:
        return missing(run["table_note"])
    caps, per_person = numbers_of(table["groups"], "cap"), numbers_of(table["groups"], "per_person")
    text = (f"each group at most its cap of images ({', '.join(map(str, reversed(caps)))}), chosen person by person in the salted order of salt {table.get('salt')}"
            f" with at most {per_person[0] if per_person else '?'} to {per_person[-1] if per_person else '?'} images a person by group, the frozen test persons of data/splits/test-persons.json left out ({run['table_note']}; README section 2)")
    renders = "; ".join(run["body"]["renders"])
    return met(text + (f"; summary.txt: {renders}" if renders else ""))


def study_missing_data(run):
    """CLAIM 12, REFORMS 3f: the groups left out, with their reasons, and the images not decoded."""
    groups = run["body"]["groups"]
    if not groups:
        return no_group_lines()
    skipped = [f"{g['id']} ({g['reason']})" for g in groups.values() if g.get("reason") is not None]
    undecoded = undecoded_counts(groups)
    left_out = f"{counted(len(skipped), 'group')} skipped, each with its reason, {'; '.join(skipped)}" if skipped else "no group skipped"
    failed = (f"{counted(sum(n for _, n in undecoded), 'chosen image')} undecoded in {counted(len(undecoded), 'group')}"
              if undecoded else "no chosen image undecoded")
    return met(f"summary.txt: {left_out}; {failed}; a group with fewer than 20 decoded images is left out of every test and one with fewer than five persons is plotted and never tested (README section 4)")


@recorded("study")
def study_partitions(run):
    """CLAIM 19, REFORMS 5c: how every test's rows were split."""
    return met(f"every two-sample test scored out of fold over at most five folds grouped by person and stratified by label, so a person is wholly on one side of each split; the split-half nulls split each group of at least 40 persons in two by person; every draw from seed {run['record']['study']['seed']} (summary.txt record; {at_commit(run)}, README sections 1 and 4)")


@recorded("study")
def study_disjoint(run):
    """CLAIM 20, REFORMS 6b: the level at which every test's folds are disjoint."""
    groups = run["body"]["groups"]
    if not groups:
        return no_group_lines()
    by_file = [g["id"] for g in groups.values() if g.get("by_file")]
    files = (f"in the {counted(len(by_file), 'group')} whose persons are their files (summary.txt, persons by file: {', '.join(by_file)}) only files are held apart"
             if by_file else "no group's persons are its files (summary.txt)")
    return met(f"by person: every test's folds are grouped by person, so no person is on both sides of a split, and two render groups on one CT folder are read as a paired sample whose two views of a CT fall in one fold ({at_commit(run)}); {files}")


@recorded("study")
def study_instruments(run):
    """CLAIM 22: the encoders and classifiers the study measures with, since it trains no network."""
    spaces = run["body"]["spaces"]
    ran = [f"{key} dim {s['dim']} over {s['rows']} rows" for key, s in spaces.items() if s.get("dim")]
    not_run = [f"{key} not run ({s['reason']})" for key, s in spaces.items() if s.get("reason") is not None]
    if not ran:
        return missing("needs a feature space that ran: summary.txt names none" + (f" ({'; '.join(not_run)})" if not_run else ""))
    return met(f"no network is trained; the instruments are the feature spaces summary.txt names, {'; '.join(ran + not_run)}: FleXray's flagship member flux0375 at the input of the last instance norm of its deepest encoder block, torchvision's ResNet-18 with ImageNet weights and handcrafted physics measures; and on each two two-sample classifiers, logistic regression (scaler, PCA to 64, C 1) and 15 nearest neighbours ({at_commit(run)}, README sections 3 and 4)")


@recorded("study", "environment", "units")
def study_software(run):
    """CLAIM 23: the packages the study ran on."""
    record = run["record"]
    if record["environment"]["pins"] == "not given":
        return missing("needs the environment's pins in summary.txt's record line 'record: environment ...': the step gave none (SN_PINS), so the packages the study ran on are not recorded")
    return met(f"the pins {record['environment']['pins']} over train-gpu's locked pixi environment (pixi.lock) at commit {record['study']['commit']}; the MMD computed on {record['units']['backend']} (summary.txt record)")


@recorded("study")
def study_initialization(run):
    """CLAIM 24: where the parameters the study reads come from."""
    return met(f"no parameter is trained from an initial state: FleXray's encoder and the ResNet-18 are read with their published weights, unchanged, and the two-sample classifiers are fit afresh in each fold; every draw is seeded from {run['record']['study']['seed']} (summary.txt record; {at_commit(run)})")


@recorded("study")
def study_training(run):
    """CLAIM 25: the only fitting the study does."""
    return met(f"no network is trained; the one fitting is each two-sample test's classifiers, logistic regression and 15 nearest neighbours, each with its scaler and PCA fit inside the fold, every row scored by a fit that held none of its person's rows ({at_commit(run)} and tools/domain_gap_stats.py, README section 4)")


@recorded("study")
def study_no_model_selection(run):
    """CLAIM 26, REFORMS 5d: the study selects no model."""
    prereg, gap = run["record"]["study"]["prereg"], prereg_gap(run)
    if gap:
        return missing(gap)
    frozen = f"by the frozen pre-registration the run read, PREREG.md {prereg}" if prereg != "none" else "in its code, and the record names no frozen pre-registration (PREREG none)"
    return not_applicable(run, f"the study selects no model: its encoders, its two-sample classifiers and their settings are fixed {frozen}, as docs/research/drr-domain-gap/README.md section 4 sets them out with the primary endpoints")


@recorded("study")
def study_ensembling(run):
    """CLAIM 27: none, each space apart."""
    spaces = run["body"]["spaces"]
    if not spaces:
        return missing("needs summary.txt's space lines: it holds none")
    return met(f"none: FleXray's flagship member alone is read, not its ensemble, and each feature space is tested apart and never pooled (summary.txt spaces {', '.join(spaces)}; {at_commit(run)})")


def study_metrics(run):
    """CLAIM 28, REFORMS 7a: the measures summary.txt's contrast lines carry."""
    lines = contrast_lines(run)
    if not lines:
        return missing("needs summary.txt's contrast lines, an AUC with its interval: it holds none")
    spaces = list(dict.fromkeys(key for key, _ in lines))
    found = [name for name, pattern in MEASURES if any(pattern.search(line) for _, line in lines)]
    baselines = sum(1 for space in run["body"]["spaces"].values() if any(BASELINE.match(line) for line in space["lines"]))
    return met(f"summary.txt, {len(lines)} contrast lines in the spaces {', '.join(spaces)}: {', '.join(found)}; the split-half calibration or the real-real baselines in {baselines} spaces")


@recorded("study")
def study_uncertainty(run):
    """CLAIM 29, REFORMS 7b: the intervals and tests on the contrast lines, and how they were made."""
    lines = [line for _, line in contrast_lines(run)]
    if not lines:
        return missing("needs summary.txt's contrast lines, an AUC with its interval: it holds none")
    count = {name: sum(1 for line in lines if pattern.search(line)) for name, pattern in MEASURES[:5]}
    return met(f"summary.txt: {count[MEASURES[0][0]]} AUCs with an interval, {count[MEASURES[1][0]]} with a C2ST permutation p, {count[MEASURES[3][0]]} MMD permutation p and {count[MEASURES[4][0]]} Benjamini-Hochberg q;"
               f" each interval the 95 percent percentile interval of a person-cluster bootstrap of 1,000 draws, the C2ST's p from 100 permutations and the MMD's from 1,000, all by person, and the q by Benjamini-Hochberg within a space{mmd_family(run, lines)} ({at_commit(run)} and tools/domain_gap_stats.py, README section 4)")


def mmd_family(run, lines):
    """Which family the run's MMD q was taken over, where a contrast line prints one: since
    DEVIATIONS.md item 11 a space's calibration line ends by saying its split-half nulls are in
    the MMD's family, and a run before it, or a space with no null tested, took the q over the
    contrasts alone."""
    if not any(MEASURES[4][1].search(line) for line in lines):
        return ""
    calibrations = [m for space in run["body"]["spaces"].values() for m in map(CALIBRATION.fullmatch, space["lines"]) if m]
    if any(m["nulls_in_family"] for m in calibrations):
        return ", the MMD's over its contrasts and its split-half nulls as PREREG.md section 3 says, the worded pairs' q over the contrasts alone on their verdict lines (DEVIATIONS.md, item 11)"
    return ", the MMD's over its contrasts alone, the split-half nulls adjusted among themselves (DEVIATIONS.md, items 8 and 11)"


def study_internal_evaluation(run):
    """CLAIM 32: the split-half nulls and the real-against-real baselines."""
    partial = unfinished(run)
    if partial:
        return missing(partial)
    quoted = [f"{key}: {line.strip()}" for key, space in run["body"]["spaces"].items() for line in space["lines"] if BASELINE.match(line)]
    if not quoted:
        return missing("needs summary.txt's calibration or real-real lines: it holds none")
    return met("the split-half nulls, every test run on two halves of one group split by person, where it must find nothing, and the real-against-real baselines (summary.txt): " + "; ".join(quoted))


@recorded("study")
def study_no_external_model(run):
    """CLAIM 33: no model, so no external test of one."""
    return not_applicable(run, "the study trains no model, so no model is tested on external data; every held corpus enters the comparison as a group of its own")


def group_counts(group):
    """A group's found/chosen/decoded/persons, or why it was skipped."""
    if group is None:
        return "no line in summary.txt"
    if group.get("reason") is not None:
        return f"skipped ({group['reason']})"
    shared = f" (the counts of {group['counted_as']})" if group.get("counted_as") else ""
    return f"{group['found']}/{group['chosen']}/{group['decoded']}/{group['persons']}{shared}"


def study_exclusions(run):
    """CLAIM 35, REFORMS 4a: every group's counts from found to decoded, or why it was skipped; a
    group of the table the summary has no line for leaves the item missing."""
    groups, table = run["body"]["groups"], run["table"]
    if not groups:
        return no_group_lines()
    absent = [g["id"] for g in table["groups"] if g["id"] not in groups] if table else []
    if absent:
        return missing(f"summary.txt has no line for the table's groups {', '.join(absent)}")
    return met("summary.txt, found/chosen/decoded/persons of each group: " + "; ".join(f"{g['id']} {group_counts(g)}" for g in ordered_groups(run)))


def calibration_of(space):
    """The space's first calibration line in its form, or None."""
    return next((m for m in map(CALIBRATION.fullmatch, space.get("lines", [])) if m), None)


def flagged_of(space):
    """The groups the space's calibration lines flag, and the count its first line gives, or None
    where the space has no calibration line in its form."""
    head = calibration_of(space)
    names = [name for line in space.get("lines", []) if line.startswith(FLAGGED) for name in line[len(FLAGGED):].split()]
    return names, int(head["count"]) if head else None


def endpoint_lines(run):
    """The primary endpoints' lines in the primary space, the endpoints summary.txt lacks, and those
    not read because a split-half null of a group on one of their sides was flagged in the space:
    the endpoint's own group, or a tested real group of the family it is read against, which the
    pooled family takes in (DEVIATIONS.md, item 8: every contrast the group is a side of in that
    space is not read)."""
    config, groups = run["config"], run["body"]["groups"]
    space = config["primary_space"]
    lines = run["body"]["spaces"].get(space, {}).get("lines", [])
    flagged, _ = flagged_of(run["body"]["spaces"].get(space, {}))
    found, absent, unread = [], [], []
    for group in config["endpoints"]:
        for family in config["families"]:
            line = next((line.strip() for line in lines if line.startswith(f" {group} vs {family} auc ")), "")
            skipped = (groups.get(group) or {}).get("reason")
            sides = [name for name in flagged if name == group or (tested(groups.get(name) or {}) and groups[name].get("family") == family)]
            if line and sides:
                unread.append(f"{group} vs {family}: the split-half null of {', '.join(sides)} in {space} found a difference, so its contrasts are not read (DEVIATIONS.md, item 8)")
                continue
            (found if line else absent).append(line or f"{group} vs {family}" + (f" (group skipped, {skipped})" if skipped else ""))
    return found, absent, unread


def study_endpoints(run):
    """CLAIM 37: the pre-registered primary endpoints with their intervals, and the verdict; an
    endpoint whose split-half null is flagged is reported as not read."""
    partial = unfinished(run)
    if partial:
        return missing(partial)
    config = run["config"]
    names, count = flagged_of(run["body"]["spaces"].get(config["primary_space"], {}))
    if count is not None and count != len(names):
        return missing(f"needs the names of the flagged split-half nulls in the {config['primary_space']} space: its calibration line counts {count} and names {len(names)}, so which endpoints are read cannot be told")
    found, absent, unread = endpoint_lines(run)
    if not found and not unread:
        return missing(f"needs the primary endpoints' lines, {', '.join(config['endpoints'])} against {' and '.join(config['families'])} in the {config['primary_space']} space: summary.txt holds none")
    text = f"the primary endpoints in the {config['primary_space']} space's inversion-invariant reading (summary.txt): {'; '.join(found) or 'none read'}"
    text += f"; not read: {'; '.join(unread)}" if unread else ""
    text += f"; not in summary.txt: {', '.join(absent)}" if absent else ""
    verdicts = run["body"]["verdicts"]
    return met(text + (f"; the replication verdict: {'; '.join(verdicts)}" if verdicts else "") + f"; read here, {verdict_said(run)}")


@recorded("study")
def study_no_diagnosis(run):
    """CLAIM 38: no diagnosis is made."""
    return not_applicable(run, "the study makes no diagnosis: its AUCs say how well two sets of images can be told apart, and no case is scored against a clinical truth")


@recorded("study")
def study_code_state(run):
    """REFORMS 2b: the commit and the digest of the code that ran, from a clean tree, and the bench
    report naming the same commit."""
    study, bench = run["record"]["study"], run["bench"]
    if study["tree"] != "clean":
        return missing(f"commit {study['commit']} from a DIRTY tree (summary.txt record), so the commit does not say which code ran")
    moved = [line for line in bench["failed"] if "checkout moved" in line]
    if moved:
        return missing(f"BENCH.md says the checkout moved during the run: {moved[0]}")
    header = bench["header"]
    if header and header["commit"] != study["commit"]:
        return missing(f"BENCH.md names commit {header['commit']} and the record {study['commit']}, so which code ran is not one answer")
    seen = "BENCH.md names the same commit" if header else "BENCH.md names no commit, so the commit is the record's alone"
    return met(f"commit {study['commit']} from a clean tree and the digest of the code the study runs, {study['code']} (summary.txt record); {seen}")


@recorded("jobs", "seconds")
def study_compute(run):
    """REFORMS 2c: the jobs, the GPUs and the seconds by stage."""
    jobs, seconds = run["record"]["jobs"], run["record"]["seconds"]
    if jobs.get("run"):
        ran = f"one job, run {jobs['run']}"
    else:
        ran = f"jobs prepare {jobs['prepare']}, an array {jobs['array']} of {jobs['tasks']} tasks and merge {jobs['merge']}"
    stages = ", ".join(f"{part} {seconds[part]}" + {"analysis": " wall", "units": " summed"}.get(part, "") for part in SECONDS_PARTS)
    ended = run["bench"]["exit"]
    tail = f"; BENCH.md: exit {ended['rc']} at {ended['at']} UTC" if ended else ""
    return met(f"{ran}, on GPUs {jobs['gpu']} x{jobs['gpus']}; seconds by stage: {stages} (summary.txt record){tail}; {run_log_said(run['bench'])}")


def run_log_said(bench):
    """One clause on the run log the report's section Run log shows: how many lines, from when to when."""
    if bench["runlog"] is None:
        return f"run log: none ({bench['runlog_why']})"
    span = bench["runlog_span"]
    when = f", {span[0]} to {span[1]} UTC" if span else ""
    return f"run log: {len(bench['runlog'])} lines in BENCH.md{when}, shown in the section Run log"


@recorded("study")
def study_reproduce(run):
    """REFORMS 2d, 2e: what runs the study again."""
    study, gap = run["record"]["study"], prereg_gap(run)
    if gap:
        return missing(gap)
    prereg = f"the frozen pre-registration PREREG.md {study['prereg']}" if study["prereg"] != "none" else "no frozen pre-registration (PREREG none)"
    return met(f"at commit {study['commit']}, the gate words and local commands of docs/research/drr-domain-gap/README.md section 7, over the groups table {study['groups']} with seed {study['seed']}, the plan the run ran on being {study['plan']}, with {prereg} (summary.txt record)")


@recorded("study")
def study_sources_per_group(run):
    """REFORMS 3a: each group's sources and what it decoded."""
    table, groups = run["table"], run["body"]["groups"]
    if table is None:
        return missing(run["table_note"])
    if not groups:
        return no_group_lines()
    parts = [f"{g['id']} from {', '.join(sources_of(g)) or 'no source named'}: {group_counts(groups.get(g['id']))}" for g in table["groups"]]
    return met(f"each group is one side of its tests and is read whole into each test's folds ({run['table_note']}; summary.txt, found/chosen/decoded/persons): " + "; ".join(parts))


def family_totals(groups):
    """Decoded images and groups by family, over the groups with counts."""
    totals = {}
    for group in groups.values():
        if group.get("decoded") is not None:
            images, count = totals.get(group["family"], (0, 0))
            totals[group["family"]] = (images + int(group["decoded"]), count + 1)
    return totals


def study_outcome(run):
    """REFORMS 3d: the label every test reads, and its counts."""
    groups = run["body"]["groups"]
    if not groups:
        return no_group_lines()
    totals = ", ".join(f"{family} {images} in {counted(count, 'group')}" for family, (images, count) in family_totals(groups).items())
    return met(f"the outcome of every test is which of its two sets an image came from, a group or a pooled family, known for every image by its group in the table; decoded images by family (summary.txt): {totals}")


def study_sample_size(run):
    """REFORMS 3e: the images in all and each group's share."""
    header, groups = run["body"]["header"], run["body"]["groups"]
    if header is None:
        return missing("needs summary.txt's line 'drr gap: <n> images, <n> groups, W&B ...': it holds none")
    if not groups:
        return no_group_lines()
    shares = "; ".join(f"{g['id']} {g['decoded']}" for g in ordered_groups(run) if g.get("decoded") is not None)
    return met(f"summary.txt: {header['images']} images decoded, {header['groups']} groups with at least 20 of them; decoded images by group: {shares}")


def study_undecoded(run):
    """REFORMS 4b: the chosen images that did not decode."""
    groups = run["body"]["groups"]
    if not groups:
        return no_group_lines()
    counts = undecoded_counts(groups)
    if not counts:
        return met("summary.txt: no group line counts a chosen image undecoded")
    return met(f"summary.txt: {counted(sum(n for _, n in counts), 'chosen image')} undecoded, by group {'; '.join(f'{group} {n}' for group, n in counts)}; the failures by kind stay in results.json on the grid")


@recorded("study", "units")
def study_models_trained(run):
    """REFORMS 5a: every model the study fits."""
    units = run["record"]["units"]
    return met(f"no network is trained; the models fit are the two-sample classifiers, logistic regression and 15 nearest neighbours, in each fold of every contrast, every contrast kept in results.json on the grid and {len(contrast_lines(run))} of them in summary.txt's lines; units {units['done']} of {units['total']} done, {units['failed']} failed (summary.txt record)")


# The study's design answers restate its frozen pre-registration, which never changes once frozen
# (PREREG.md, section 7), so each holds only for a run whose record names that pre-registration by
# the digest the study's config gives and whose file is still it; any other run has them missing.


def design_gap(run):
    """Why the design answers do not hold for this run, or empty where they do."""
    named, design = run["record"]["study"]["prereg"], run["config"]["design"]
    if named == "none":
        return "needs the frozen pre-registration the run read: the record names none (PREREG none)"
    gap = prereg_gap(run)
    if gap:
        return gap
    if undashed(named) != undashed(design):
        return f"the record names PREREG {named}, and these answers restate PREREG.md {design}, so they are not this run's design"
    return ""


def frozen(fact):
    """A study fact that restates the frozen design: missing, saying why, unless the run read it."""

    @recorded("study")
    def answer(run):
        gap = design_gap(run)
        return missing(gap) if gap else fact(run)

    answer.__doc__ = fact.__doc__
    return answer


def needs_table(fact):
    """A study fact that reads the groups table: missing, with the table's note, where it is not read."""

    def answer(run):
        return missing(run["table_note"]) if run["table"] is None else fact(run)

    answer.__doc__ = fact.__doc__
    return answer


def by_family(table):
    """The table's group ids under each family, in the table's order."""
    families = {}
    for group in table["groups"]:
        families.setdefault(group.get("family"), []).append(group["id"])
    return families


def skipped_groups(run):
    return [f"{g['id']} ({g['reason']})" for g in run["body"]["groups"].values() if g.get("reason") is not None]


def skips_said(run):
    """The summary's skipped groups as one clause, or that none was skipped."""
    skipped = skipped_groups(run)
    return f"{counted(len(skipped), 'group')} skipped, {'; '.join(skipped)}" if skipped else "no group skipped"


def tested(group):
    """Whether a summary group was read with the 20 decoded images and five persons a test takes
    (PREREG.md section 2)."""
    return group.get("reason") is None and group.get("decoded") is not None and int(group["decoded"]) >= 20 and int(group["persons"]) >= 5


def untested_groups(run):
    """The groups read and never tested, for want of images or persons."""
    return [g["id"] for g in ordered_groups(run) if g.get("reason") is None and not tested(g)]


def groups_without_null(run):
    """The tested groups of fewer than 40 persons, with their persons: none has a split-half null
    (PREREG.md section 3)."""
    return [f"{g['id']} {g['persons']}" for g in ordered_groups(run) if tested(g) and int(g["persons"]) < 40]


def without_null_said(run):
    without = groups_without_null(run)
    return f"so these tested groups, by their persons in summary.txt, have none of their own: {', '.join(without)}" if without else "and every tested group has 40 persons or more (summary.txt)"


def real_pairs(run, family):
    """The pairs of tested real groups of one family, the family's own real pairs."""
    ids = [g["id"] for g in ordered_groups(run) if g.get("family") == family and tested(g)]
    pairs = [f"{a} against {b}" for i, a in enumerate(ids) for b in ids[i + 1:]]
    listed = f", {'; '.join(pairs)}" if 0 < len(pairs) <= 3 else ""
    return f"{family} {counted(len(pairs), 'pair')}{listed}"


def calibration_said(run):
    """Each space's split-half nulls as its calibration lines give them: the nulls its MMD flags, by
    name, and the AUC intervals above one half, which flag nothing (DEVIATIONS.md, item 8); a count
    its names do not match is said as it stands."""
    parts = []
    for key, space in run["body"]["spaces"].items():
        head = calibration_of(space)
        if head is None:
            continue
        names, count = flagged_of(space)
        flagged = (", ".join(names) or "none") if count == len(names) else f"{count}, its lines naming {len(names)}"
        parts.append(f"{key} mmd flagged {flagged}, auc interval above half {head['above']}")
    return "; ".join(parts) or "no space carries a calibration line"


VERDICT_LINE = re.compile(r"replication (?P<a>\S+) vs (?P<b>\S+) in (?P<space>\S+) \(invariant\): (?P<word>replicated|not replicated) \(")
NO_VERDICT = re.compile(r"replication (?P<a>\S+) vs (?P<b>\S+): no verdict, (?P<reason>.*)")
PAIR_NUMBERS = re.compile(r" auc \S+ \[(?P<lo>[0-9.]+), [0-9.]+\].* mmd p \S+ q (?P<q>[0-9.]+)")


def verdict_of(run):
    """The verdict pair's line in summary.txt, read in its form, or why there is none: the pair's
    own reason where its line says it has no word."""
    a, b = run["config"]["verdict_pair"]
    space = run["config"]["primary_space"]
    lines = run["body"]["verdicts"]
    verdict = next((m for m in map(VERDICT_LINE.match, lines) if m and (m["a"], m["b"], m["space"]) == (a, b, space)), None)
    if verdict is not None:
        return verdict, None
    none = next((m for m in map(NO_VERDICT.fullmatch, lines) if m and (m["a"], m["b"]) == (a, b)), None)
    if none is not None:
        return None, f"the verdict pair, {a} against {b}, has no word, summary.txt giving its reason: {none['reason']}"
    return None, f"the verdict: summary.txt holds no line of the verdict pair, {a} against {b} in the {space} space, in its form"


def q_family(run, space):
    """Which family the space's MMD q was taken over, by its calibration line: frozen where the
    split-half nulls are in it (PREREG.md section 3), alone where the contrasts alone are, unread
    where the space has no calibration line in its form."""
    head = calibration_of(run["body"]["spaces"].get(space, {}))
    return "unread" if head is None else "frozen" if head["nulls_in_family"] else "alone"


def family_caveat(family):
    """What a word read on the MMD's q can say where the q's family is not the frozen one."""
    if family == "alone":
        return ("; that q was taken over the space's contrasts alone, where PREREG.md section 3 takes the split-half nulls into its family (DEVIATIONS.md, item 11),"
                " so the frozen rule's word on the MMD is not read in this run")
    if family == "unread":
        return "; the space holds no calibration line in its form, so which family that q was taken over, and so whether the frozen rule's word on the MMD is read in this run, is not told"
    return ""


def bar_side(printed, bar, tells_above):
    """Which side of its bar a printed number lies: told, the pair told apart by it; passed; or at,
    where it equals the bar to the digits the summary prints, so that the word, worked out on the
    unrounded number (src/schwingnet/domain_gap.py, replication_word), may lie on either side."""
    value = float(printed)
    if abs(value - bar) < 1e-9:
        return "at"
    return "told" if (value > bar) == tells_above else "passed"


def verdict_said(run):
    """The study's verdict, the verdict pair's word, and which of the replication's two bars the
    pair's line passes or fails, in PREREG.md section 5's words where the word stands under the
    frozen rule; or why summary.txt does not tell. The MMD's bar is read under the frozen rule only
    where the q's family is the frozen one (DEVIATIONS.md, item 11), and a number printed at its bar
    places nothing; a word the classifier decides stands under either family."""
    verdict, why = verdict_of(run)
    if verdict is None:
        return why
    a, b, space = verdict["a"], verdict["b"], verdict["space"]
    pair = f"the verdict, {a} against {b} in the {space} space read inversion-invariant,"
    unread = pair_not_read(run, a, b, space)
    if unread:
        return f"{pair} reads {verdict['word']}, but {unread}"
    line = next((line for line in run["body"]["spaces"].get(space, {}).get("lines", []) if line.startswith(f" replication {a} vs {b} ")), "")
    numbers = PAIR_NUMBERS.search(line)
    if numbers is None:
        return f"{pair} reads {verdict['word']}, and its space holds no line of the pair with its AUC interval and MMD q, so which bars it passed or failed is not read here"
    lo, q, family = numbers["lo"], numbers["q"], q_family(run, space)
    auc, mmd = bar_side(lo, 0.6, True), bar_side(q, 0.05, False)
    if verdict["word"] == "replicated":
        return f"{pair} reads replicated, the AUC's lower bound of {lo} at most the bar of 0.6 and the MMD's q of {q} at least 0.05" + family_caveat(family)
    if auc == "told":
        return failure_in_design_words(pair, [f"the classifier told them apart (AUC lower bound {lo})"] + [f"the MMD told them apart (q {q})"] * (mmd == "told" and family == "frozen"), beside_the_classifier(q, mmd, family))
    if mmd == "told" and family == "frozen":
        rests = f", the AUC's lower bound of {lo} being at most the bar of 0.6, so the word rests on the MMD alone" if auc == "passed" else f", the AUC's lower bound printed as {lo}, the bar of 0.6 to the digits the summary prints, so whether the classifier told them apart too is not read here"
        return failure_in_design_words(pair, [f"the MMD told them apart (q {q})"], rests)
    if mmd == "told":
        rests = f"the AUC's lower bound of {lo} at most the bar of 0.6, so the word rests on the MMD alone" if auc == "passed" else f"the AUC's lower bound printed as {lo}, the bar of 0.6 to the digits the summary prints, so which bar the word rests on is not read here"
        return f"{pair} reads not replicated, the MMD's q of {q} being under the bar of 0.05 and {rests}" + family_caveat(family)
    if {auc, mmd} == {"at", "passed"}:
        return failed_at_its_bar(pair, lo, q, auc == "at", family)
    at = " and at least one of them at its bar to the digits the summary prints" if "at" in (auc, mmd) else ""
    return f"{pair} reads not replicated on an AUC lower bound of {lo} and an MMD q of {q}{at}, which as printed do not show which bar it failed"


def pair_not_read(run, a, b, space):
    """Why the verdict pair's contrast is not read, or None: a split-half null of either side flagged
    in the space, every contrast that group is a side of being then not read (DEVIATIONS.md, item 8),
    or a calibration line whose count of flagged nulls its names do not match, which leaves it untold."""
    names, count = flagged_of(run["body"]["spaces"].get(space, {}))
    if count is not None and count != len(names):
        return f"the {space} space's calibration line counts {counted(count, 'flagged split-half null')} and names {len(names)}, so whether the pair's contrast is read cannot be told"
    sides = [name for name in (a, b) if name in names]
    if sides:
        nulls, their = ("split-half null", "its") if len(sides) == 1 else ("split-half nulls", "their")
        return f"the {nulls} of {' and '.join(sides)} in {space} found a difference, so {their} contrasts are not read (DEVIATIONS.md, item 8), the verdict pair's among them"
    return None


def failed_at_its_bar(pair, lo, q, by_the_classifier, family):
    """A not-replicated word where one bar is passed and the other printed at it: the number at its
    bar is the one that failed, unrounded, since the word is replicated exactly when both bars pass
    (src/schwingnet/domain_gap.py, replication_word)."""
    shows = "the word showing the unrounded number on the failing side, since the other bar is passed (src/schwingnet/domain_gap.py, replication_word)"
    if by_the_classifier:
        return failure_in_design_words(pair, [f"the classifier told them apart (AUC lower bound printed as {lo}, the bar of 0.6, {shows})"], beside_the_classifier(q, "passed", family))
    alone = f"the AUC's lower bound of {lo} at most the bar of 0.6, so the word rests on the MMD alone"
    if family == "frozen":
        return failure_in_design_words(pair, [f"the MMD told them apart (q printed as {q}, the bar of 0.05, {shows})"], f", {alone}")
    return f"{pair} reads not replicated, the MMD's q printed as {q}, the bar of 0.05, {shows}, and {alone}" + family_caveat(family)


def failure_in_design_words(pair, failed, tail):
    """A not-replicated verdict in PREREG.md section 5's sentence, with the bars it failed."""
    return (f"{pair} reads not replicated, and in PREREG.md section 5's words this project's blocks did not reproduce FleXray's own renders of its recipe: {' and '.join(failed)}{tail};"
            " every comparison read through the blocks is then a comparison of this project's renders, not FleXray's")


def beside_the_classifier(q, mmd, family):
    """What the MMD says beside a classifier that told the pair apart, which decides the word alone."""
    if family != "frozen":
        return f", which decides the word whichever family the MMD's q is taken over (DEVIATIONS.md, item 11); the MMD's q is {q}" + family_caveat(family)
    if mmd == "passed":
        return f", the MMD's q of {q} being at least 0.05, so the word rests on the classifier alone"
    if mmd == "at":
        return f", the MMD's q printed as {q}, the bar of 0.05 to the digits the summary prints, so whether the MMD told them apart too is not read here"
    return ""


# The words a contrast line ends with where the design words it (PREREG.md section 4); a line of a
# family with no real pair to read against carries none.
WORDS = (" indistinguishable", " closer than two real corpora", " separable")


def endpoints_said(run):
    """The primary endpoints worded separable, PREREG.md section 5's failure of realism, where the
    endpoints are read."""
    state, why = study_endpoints(run)
    if state != "met":
        return f"the primary endpoints are not read here ({why})"
    found, absent, unread = endpoint_lines(run)
    worded = [line for line in found if line.endswith(WORDS)]
    separable = [line.split(" auc ")[0] for line in worded if line.endswith(" separable")]
    text = f"of the primary endpoints' {counted(len(worded), 'worded line')} read, " + (f"{len(separable)} worded separable, {', '.join(separable)}" if separable else "none worded separable")
    unworded = len(found) - len(worded)
    return (text + (f", {unworded} printed with no word" if unworded else "")
            + (f", {len(unread)} not read" if unread else "") + (f", {len(absent)} not in summary.txt" if absent else ""))


def section_six_parts(run):
    """README section 6 in its parts, the first and then each ### part, up to and including the part
    that records this run's folder; None where none records it."""
    path = Path(run["config"]["readme"])
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    start, end = text.find("\n## 6."), text.find("\n## 7.")
    if start < 0:
        return None
    parts = text[start:end if end > start else len(text)].split("\n### ")
    at = next((i for i, part in enumerate(parts) if f"runs/{run['dir'].name}/" in part), None)
    return None if at is None else parts[:at + 1]


def limit_paragraphs(part):
    """A part's paragraphs that say what a run does not support, each on one line."""
    paragraphs = [" ".join(p.split()) for p in part.split("\n\n")]
    return [p for p in paragraphs if p.startswith("What the ") and "does not support" in p]


def speaks_for(run):
    """What README section 6 says for this run: its own part whole, its own limits paragraphs, and
    the earlier parts' limits paragraphs where its own say that they hold for it, as the second
    run's does of the first's; None where section 6 records no part for this run."""
    parts = section_six_parts(run)
    if parts is None:
        return None
    own = parts[-1]
    limits = limit_paragraphs(own)
    carried = [p for part in parts[:-1] for p in limit_paragraphs(part)] if any(" holds for " in p for p in limits) else []
    return {"own": " ".join(own.split()), "limits": limits, "carried": carried}


def recorded_limits(run):
    """What README section 6 says this run does not support: its own part's paragraphs, after the
    earlier parts' that its own say still hold, quoted whole; an empty list where its own part says
    nothing of it, whatever an earlier part says, and None where section 6 records no part for it."""
    said = speaks_for(run)
    if said is None:
        return None
    return said["carried"] + said["limits"] if said["limits"] else []


def section_six_says(run, words):
    """Whether README section 6 says these words for this run: in its own part, or in an earlier
    part's limits that its own say hold for it."""
    said = speaks_for(run)
    return said is not None and any(words in text for text in [said["own"], *said["carried"]])


def answers_it(fact, run):
    """Whether another fact answers its item for this run, so a pointer to it points at an answer."""
    return fact(run)[0] != "missing"


@frozen
def study_aims(run):
    """CLAIM 4: the question and the hypotheses, as the pre-registration fixed them."""
    return met("the question, PREREG.md section 1: how far FleXray's synthetic DRRs are from real X-rays, plain film and intra-operative fluoroscopy, whether that distance is larger than the distance between two real corpora, and whether this project's rendering of FleXray's recipe reproduces FleXray's own;"
               " the hypotheses and their bars, its section 4: the primary endpoints, in the flexray space read inversion-invariant, the logistic C2ST AUC of flexray_drr, of flexray_drr_ct and of fluxray where fetched against pooled fluoroscopy and against pooled film, each with its interval, and FD64 of each against each family divided by the median FD64 between that family's own real corpora, the gap ratio, 1 meaning as far as two real corpora are from each other;"
               " the words beside each primary number, indistinguishable where the AUC's lower bound is at most 0.6, closer than two real corpora where it is below the median AUC of the family's real pairs and separable otherwise;"
               " and the replication, replicated for each of the two worded pairs, flexray_replica against flexray_reference and fluxray_raw against fluxray_raw_reference, where the logistic AUC's lower bound is at most 0.6 and the MMD's q at least 0.05, and not replicated otherwise, the first pair's word in that space and reading being the study's verdict")


@frozen
def study_goal(run):
    """CLAIM 6: a measurement under pre-registered hypotheses, not a model."""
    return met("a measurement under pre-registered hypotheses: the primary endpoints and the replication verdict of PREREG.md section 4, every other number read as description (its section 6); the study trains no network and builds no model for use")


def noted_out(table):
    """What the groups table's notes say is left out, each note quoted whole."""
    noted = [f"{g['id']}, \"{g['note']}\"" for g in table["groups"] if "left out" in (g.get("note") or "")]
    return f"; and what the table's notes say is left out: {'; '.join(noted)}" if noted else ""


@frozen
@needs_table
def study_inclusion(run):
    """CLAIM 8: who is in, who is out, and why."""
    table = run["table"]
    if not run["body"]["groups"]:
        return no_group_lines()
    frames = "; ".join(f"for a group read from {source}, {frame}" for source, frame in FRAMES.items())
    return met(f"in: the {len(table['groups'])} groups of the table ({run['table_note']}), a group's images being, by its source, {frames}; each group at most its cap of images chosen person by person, with the five frozen test persons of data/splits/test-persons.json left out of every group;"
               " out before the run, each with its reason in README section 2, the corpora PREREG.md section 2 names: fluoro_video_clips, fluorocap, carmlspine_sweeps, spinesac, mendeley_5jdfdgp762, COBRA, ljubljana_2d3d_gs, the undecodable videos and the archives never unpacked"
               + noted_out(table)
               + f"; in the run, a group with fewer than 20 decoded images is left out and one with fewer than five persons is plotted and never tested; summary.txt: {skips_said(run)}"
               + "".join(f"; {line}" for line in run["body"]["renders"]))


@recorded("study")
def study_no_reference_standard(run):
    """CLAIM 14, 15: the label is the group, known by construction."""
    return not_applicable(run, "the study has no reference standard: the one label its tests read is which group or pooled family an image belongs to, known for every image by construction from the groups table, and no image is scored against a clinical truth")


@recorded("study")
def study_no_annotation(run):
    """CLAIM 16, 17: no reference-standard annotation; the one labelling is a segmenter's."""
    return not_applicable(run, "the study makes no reference-standard annotation and no person reads an image: the label every test reads is the image's group or pooled family, which the groups table sets, or, in a split-half null, its half of one group split by person;"
                               " the only labels made for the study are moosez's segmentations of the render CTs, made in the segment job, which the render recipes read to weight and drop crops, to aim the isocentre and, where the attenuation randomisation is on, to draw each structure's attenuation factor, and which the study's own code reads to choose the CTs, and no test reads them (README section 2.1; src/schwingnet/render_blocks.py, reads_labels)")


@recorded("study")
def study_no_raters(run):
    """CLAIM 18: no rater reads an image."""
    return not_applicable(run, "the study has no rater, so no inter- or intrarater variability: no person reads an image, and the words beside the numbers are computed from them by src/schwingnet/domain_gap.py and printed by the summary, so no reader chooses them")


@frozen
@needs_table
def study_intended_size(run):
    """CLAIM 21: the caps the design fixed, in place of a target."""
    table = run["table"]
    caps, per_person = numbers_of(table["groups"], "cap"), numbers_of(table["groups"], "per_person")
    renders = "; ".join(run["body"]["renders"])
    return met(f"the design fixes caps, not a target: each group at most its cap of images ({', '.join(map(str, reversed(caps)))}) and at most {per_person[0] if per_person else '?'} to {per_person[-1] if per_person else '?'} a person by group, 300 images from each testable real group in a pooled family, at most 600 a group in the maps, and a group tested only with at least 20 decoded images and five persons (PREREG.md sections 2 and 3; {run['table_note']});"
               " the render groups were planned on 250 CTs and stand on the CTs the segmentation job covered (DEVIATIONS.md, item 1)"
               + (f", summary.txt: {renders}" if renders else "")
               + "; no file of the study records a power calculation for any size, and the bar of 0.6 is by the design's own account neither a published value nor a power calculation's (PREREG.md section 4)")


def spaces_said(run):
    """The spaces summary.txt names: those that ran with their size, those not run with why."""
    spaces = run["body"]["spaces"]
    ran = [f"{key} dim {s['dim']}" for key, s in spaces.items() if s.get("dim")]
    not_run = [f"{key} not run ({s['reason']})" for key, s in spaces.items() if s.get("reason") is not None]
    return ran, not_run


# Why a space has no features, the reasons tools/domain_gap.py's reading_heads gives where it makes
# neither of the space's readings (unavailable, or no features file); a space that ran and whose
# inversion-invariant head alone is invalid ("every image has the same features", space_head) still
# has its as-stored reading made.
NO_FEATURES = ("no features", "no FleXray bundle (ensemble.json)", "no ImageNet ResNet-18 file")


def given_up_said(run):
    """The design's spaces and readings summary.txt does not name: a reading of a space that had no
    features was never made (tools/domain_gap.py, reading_heads), and the rest its line budget gave up."""
    spaces = run["body"]["spaces"]
    absent = [key for key in run["config"]["readings"] if key not in spaces]
    never = [key for key in absent if key.endswith("_as_stored") and spaces.get(key[:-len("_as_stored")], {}).get("reason") in NO_FEATURES]
    given_up = [key for key in absent if key not in never]
    text = ""
    if given_up:
        text += (f", and of the design's spaces and readings it does not name {', '.join(given_up)}, which its 80-line budget gave up, the summary giving up whole sections from the highest rank down"
                 " (tools/domain_gap.py, RANK and fit_lines; README section 6), so what results.json on the grid holds of them is not read here")
    if never:
        text += f", and {', '.join(never)} {'was' if len(never) == 1 else 'were'} never made, since the space it reads had no features (tools/domain_gap.py, reading_heads)"
    return text


@frozen
def study_robustness(run):
    """CLAIM 30: the one view the verdict is read in, and every other view as description."""
    ran, not_run = spaces_said(run)
    if not ran:
        return missing("needs a feature space that ran: summary.txt names none" + (f" ({'; '.join(not_run)})" if not_run else ""))
    both = any("without nulls" in line for line in run["body"]["verdicts"])
    return met("the primary words and the study's verdict are read in one view, FleXray's space read inversion-invariant (PREREG.md section 4); as secondary description (its section 6) the design reads every contrast again in the imagenet and physics spaces and in FleXray's space as stored, by two classifiers, logistic regression and 15 nearest neighbours, beside the MMD, FD64 and KID64, with PRDC only for each synthetic group against each pooled family and for the replication pairs (tools/domain_gap.py, contrast, family_unit and replication_unit),"
               f" and runs a split-half null on each group of 40 persons or more (its section 3), {without_null_said(run)}; PREREG.md plans no analysis of how a word moves with the bar of 0.6 or with the seed, every draw being from one seed;"
               f" summary.txt carries {'; '.join(ran + not_run)}{given_up_said(run)}; {verdict_said(run)}"
               + ("; and the verdict lines print each worded pair's MMD q with the split-half nulls in its family and without them (DEVIATIONS.md, item 11)" if both else ""))


# The descriptive lines a space's summary can carry (tools/domain_gap.py, real_summary,
# nearest_summary, centre_summary and the contrast lines), each by the words that show it.
DESCRIPTION_LINES = (
    ("PRDC", lambda line: bool(MEASURES[-1][1].search(line))),
    ("the silhouette", lambda line: line.startswith(" silhouette ")),
    ("the nearest real corpora", lambda line: line.startswith(" nearest real")),
    ("the t-SNE map's group centres", lambda line: line.startswith(" tsne centres")),
)


def in_words(items):
    """Items as a list in English: a, b and c."""
    return " and ".join(items) if len(items) < 3 else ", ".join(items[:-1]) + " and " + items[-1]


def description_printed(run):
    """Which of the descriptive measures summary.txt prints, in DESCRIPTION_LINES' order."""
    lines = [line for space in run["body"]["spaces"].values() for line in space.get("lines", [])]
    return [name for name, shows in DESCRIPTION_LINES if any(map(shows, lines))]


@frozen
def study_explainability(run):
    """CLAIM 31: what the study shows of how the groups differ, and which of it this record prints."""
    printed = description_printed(run)
    said = (f" of these summary.txt prints {in_words(printed)}, and the rest are on the grid and not in this record"
            if printed else " of these summary.txt prints none, so all are on the grid and none in this record")
    return met("no per-image explanation, no saliency or attribution map, is made; what the study shows of how the groups differ is description (PREREG.md sections 3 and 6): the maps, PCA, t-SNE, UMAP and LDA, each but LDA with its trustworthiness; the silhouette, each group's neighbour purity and its neighbours' share in each family; the nearest real corpus that a classifier of the real corpora alone calls each synthetic group; and PRDC; and the physics space's features are named measures, the intensity histogram, the radial power spectrum's shape, the gradient histogram, the noise, the local contrast, the shares near black and white and the share of strong edges (README section 3);"
               + said)


@frozen
def study_no_trial(run):
    """CLAIM 34: no clinical trial; the design is registered in the project."""
    return not_applicable(run, f"the study is no clinical trial and is in no trial registry; its design is registered inside the project as PREREG.md {run['record']['study']['prereg']}, frozen on 2026-10-27 before any number of the study was read (its section 7), the pre-registration this record names")


@frozen
def study_failure_analysis(run):
    """CLAIM 39: no case is scored against a clinical truth; the failures the design defines."""
    return not_applicable(run, "the study scores no case against a clinical truth (CLAIM 38): its classifier two-sample tests score each image out of fold for its side of a contrast, its group, its pooled family or its half of a split group, and read the scores only in aggregate, as the AUC by its pure rule of ranks, the share of pairs across the two sides ranked the right way round with ties counted half (tools/domain_gap_stats.py, rank_auc), with its interval; no threshold sorts an image to a side, so no file of the study analyses an image as misclassified;"
                        " the failures its design defines are PREREG.md section 5's: of the pipeline, a split-half null whose AUC interval excludes 0.5, which the study flags by its MMD instead and counts the AUC interval beside it (DEVIATIONS.md, item 8), summary.txt's calibration lines reading "
                        + calibration_said(run) + f"; of the replication, the verdict not replicated: {verdict_said(run)}; of realism, a primary endpoint worded separable, {endpoints_said(run)}")


@frozen
def study_limitations(run):
    """CLAIM 40: the limits listed before the run, those its review found after it, and this run's own."""
    groups = run["body"]["groups"]
    if not groups:
        return no_group_lines()
    found = recorded_limits(run)
    if not found:
        why = "section 6 records no part for it" if found is None else "its part says nothing of what the run does not support"
        return missing(f"needs README section 6's record of this run (runs/{run['dir'].name}/), where a run's review writes what it does not support: {why}")
    by_file = [g["id"] for g in groups.values() if g.get("by_file")]
    quoted = " ".join(f'"{paragraph}"' for paragraph in found)
    return met("before the run, README section 5's eight limits, to which PREREG.md section 6 points: the corpora differ in more than their realism, in anatomy, devices, eras and formats; the renders follow their own pose profiles where the real spot frames are narrow and centred; the replication's CTs are TotalSegmentator v2.0.1's, not the ENHANCE-PET volumes of FleXray's dataset; its MOOSE masks are merged in this project's own precedence; the SPINEPS masks are matched by name in a layout not recorded; flexray_drr_ct aims at the crop's centre and draws its crops uniformly; persons are files in seven groups; DeepFluoro has six specimens;"
               f" after the run, what README section 6 says the recorded runs do not support, in its words: {quoted};"
               f" every departure from the design is in DEVIATIONS.md, dated with its reason; of this run, summary.txt: {skips_said(run)}"
               + (f"; persons by file in {', '.join(by_file)}" if by_file else "")
               + f"; split-half nulls on each group of 40 persons or more, {without_null_said(run)}, the calibration lines reading {calibration_said(run)}; {verdict_said(run)}")


@frozen
def study_protocol(run):
    """CLAIM 42: where the full protocol is."""
    return met(f"the full text of the protocol is docs/research/drr-domain-gap/README.md, sections 1 to 5, at commit 6658f3a, which the pre-registration PREREG.md beside it, sha256 {run['record']['study']['prereg']} as this record names it, restates in seven parts and freezes (PREREG.md, its opening and section 7); DEVIATIONS.md beside them records every departure, and README section 7 gives the commands that run the study")


@frozen
@needs_table
def study_population(run):
    """REFORMS 1a: the groups the claims are about."""
    table = run["table"]
    families = by_family(table)
    listed = "; ".join(f"{family}, {', '.join(ids)}" for family, ids in families.items())
    rendered = [f"{g['id']}: {g.get('label')}" for g in table["groups"] if g.get("source") == "render"]
    untested = untested_groups(run)
    groups = run["body"]["groups"]
    read = (f"; of them, summary.txt: {skips_said(run)}" + (f", and {', '.join(untested)} read and never tested, for want of 20 decoded images or five persons (PREREG.md section 2)" if untested else "")) if groups else "; summary.txt holds no group line, so which of them were read is not told here"
    return met(f"the images of the table's {len(table['groups'])} groups in {len(families)} families (PREREG.md section 2; {run['table_note']}): {listed};"
               f" the render groups are renders of held TotalSegmentator v2.0.1 CTs, each by the recipe and engine the table names (README sections 2.2 and 2.3): {'; '.join(rendered) or 'none'}; every other group stands for the held set it is read from{read}")


def edit_alone(run):
    """What README section 6 finds of the FLUX-edit pair, where it finds it for this run."""
    return "; README section 6 finds that the FLUX-edit pair measures the edit together with what else differs between its two sides, not the edit alone" if section_six_says(run, "not the edit alone") else ""


@frozen
def study_population_rationale(run):
    """REFORMS 1b: why every held corpus of both kinds but those left out."""
    listed = " (CLAIM 8 lists them)" if answers_it(study_inclusion, run) else ""
    return met("the question is how far FleXray's renders are from real X-rays of both kinds, plain film and intra-operative fluoroscopy, and whether that distance passes the distance between two real corpora (PREREG.md section 1), so every held corpus of the two kinds is a group but those README section 2 and the groups table's notes leave out, each with its reason" + listed + ", the real-against-real pairs giving the scale;"
               " and README section 2.2 names six pairs, each meant to isolate one thing: the engine in the two worded replication pairs, one part of the recipe in three pairs of render groups on the same CTs (the labels' aiming, the attenuation randomisation and the segmenter), and the FLUX edit in fluxray_raw_reference against fluxray"
               + edit_alone(run) + ";"
               " the owner asked on 2026-10-25 for \"all the other Xray corpuses both plain film and fluoro\" (README, opening)")


@frozen
def study_ml_rationale(run):
    """REFORMS 1c: why a classifier, beside tests that train nothing, and what each claim carries."""
    return met("a map alone answers neither question, since t-SNE draws clusters for any two sets with a consistent difference, however small, and its distances between clusters mean nothing (README section 1), so README section 1 means every claim to be carried by a test with an interval and a calibration: a classifier two-sample test, which learns to tell the two sets apart, beside a kernel test and distances that learn nothing (PREREG.md section 3);"
               " as the design gives them, the C2ST AUC carries a person-cluster bootstrap interval and, against each family and in the replication pairs, a permutation p, the MMD a permutation p and no interval (tools/domain_gap_stats.py, mmd_test), and FD64 and its gap ratio, a primary endpoint, neither a test nor an interval (PREREG.md sections 3 and 4 give them none);"
               f" the split-half nulls calibrate each group of 40 persons or more (PREREG.md section 3), {without_null_said(run)};"
               " the owner asked on 2026-10-25 for \"other statistical tests for separation that machine learning experts would do\" (README, opening)")


# What a group of each source is drawn from (tools/domain_gap.py, the listing of a group's files).
FRAMES = {
    "index": "the image rows the sample index lists with no read error under its sources (grid/run-samples.sh) that its rules keep: the table's formats and globs, a least side, the table's or 256, a single plane, for a DICOM a projection modality, the table's or CR, DX, RF, XA, DF, RG, PX, OT and SC, and no exclude word in the path, the table's or the study's (src/schwingnet/domain_gap.py, GroupSpec; tools/domain_gap.py, refusal)",
    "walk": "the files seen under its folder on the data root, up to the walk's limit, that the table's formats and globs and its exclude words, the table's or the study's, keep (tools/domain_gap.py, walk_candidates)",
    "thunderdb": "the records of its ThunderDB as FleXray's reader lists them",
    "render": "the held TotalSegmentator v2.0.1 CTs with masks under every segmenter its folder's groups read (README section 2.1), of which the analysis reads only those every render group on the folder kept (README section 7)",
}


@frozen
@needs_table
def study_sampling_frame(run):
    """REFORMS 3b: what each group was drawn from."""
    by_source = {}
    for group in run["table"]["groups"]:
        by_source.setdefault(group.get("source"), []).append(group["id"])
    frames = [f"{FRAMES.get(source, f'its source {source}, which the report has no words for')}: {', '.join(ids)}" for source, ids in by_source.items()]
    return met("each group's frame, by its source in the table (PREREG.md section 2): " + "; ".join(frames)
               + f"; within its frame each group's images are chosen person by person in the salted order of salt {run['table'].get('salt')} up to its caps, the frozen test persons left out ({run['table_note']})")


@frozen
def study_fitness(run):
    """REFORMS 3c: why the groups fit the question, and what limits the fit."""
    later = " and README section 6 records what the recorded runs do not support (CLAIM 40 quotes it)" if answers_it(study_limitations, run) else ""
    edit = edit_alone(run)
    return met("each real group is a held corpus of plain film or of fluoroscopy (README section 2), the families of the question's two kinds (PREREG.md section 1), the fluoroscopy family holding beside one mobile C-arm's spot frames DeepFluoro's vendor fluoroscopy of cadaver pelves, six specimens plus phantoms by the table's note, and a resin hip phantom (README section 2; data/domain_gap/groups.json); each group is capped by person so that a corpus with many images of few persons cannot outweigh the others (README section 2);"
               " the render groups render the same CTs and differ only by their recipe and engine (PREREG.md section 2), and README section 2.2 names six pairs, each meant to isolate one thing" + edit + ";"
               " what limits the fit was listed before the run, README section 5: the corpora differ in anatomy (cervical films, a hip phantom, cephalograms, abdomen), devices, eras and formats as well as in realism, and the renders follow their own pose profiles where the real spot frames are narrow and centred on the lumbar spine;" + later)


@frozen
@needs_table
def study_representativeness(run):
    """REFORMS 3g: how each group was drawn, and what no file says of the corpora."""
    renders = "; ".join(run["body"]["renders"])
    return met(f"within its corpus each group is a salted draw of persons up to its cap (salt {run['table'].get('salt')}), chosen by no reader; the corpora are the held corpora the groups table names (PREREG.md section 2), and no file of the study says how any corpus was drawn from its population or how far it stands for one; README section 5 lists before the run how they differ in anatomy, devices, eras and formats;"
               " the render groups stand on the CTs the segmentation job covered, not the 250 planned (DEVIATIONS.md, item 1)" + (f", summary.txt: {renders}" if renders else ""))


@frozen
def study_no_tuning(run):
    """REFORMS 5e: nothing is tuned."""
    commit = run["record"]["study"]["commit"]
    return not_applicable(run, "the study tunes no hyperparameter: the settings PREREG.md section 3 names, the logistic regression's scaler, PCA to 64 and C 1, the 15 neighbours, the five folds, the 1,000 bootstrap draws, the 100 and 1,000 permutations and the seed of 0, were fixed there before any number;"
                               f" the code's other settings, among them the rows a side FD64 is taken at, KID's subsets, PRDC's and neighbour purity's neighbours and the classifiers' iteration limits, are not in PREREG.md: they are set in the study's code (tools/domain_gap.py and tools/domain_gap_stats.py at commit {commit}), and the study chooses none of them by a score on its data")


@frozen
def study_baselines(run):
    """REFORMS 5f: the real-real scale and the split-half nulls."""
    spaces = [key for key, space in run["body"]["spaces"].items() if any(BASELINE.match(line) for line in space["lines"])]
    primary = run["config"]["primary_space"]
    scale = next((line.strip() for line in run["body"]["spaces"].get(primary, {}).get("lines", []) if line.startswith(" real-real auc median ")), "")
    quoted = "; CLAIM 32 quotes them" if answers_it(study_internal_evaluation, run) else ""
    text = ("the baselines are the real-against-real contrasts, every pair of tested real groups and pooled fluoroscopy against pooled film, the median AUC and median FD64 of a family's own real pairs being what each primary word and gap ratio is read against (PREREG.md sections 3 and 4), and the split-half nulls, where every test must find nothing (README section 1" + quoted + ");"
            + (f" summary.txt carries such lines in the spaces {', '.join(spaces)}" if spaces else " summary.txt carries no such line"))
    if scale:
        text += f"; in the {primary} space it reads \"{scale}\""
    if run["body"]["groups"]:
        text += f"; the families' own real pairs, among the tested real groups of summary.txt: {real_pairs(run, 'fluoroscopy')}; {real_pairs(run, 'film')}"
    if section_six_says(run, "says nothing of realism"):
        text += "; README section 6 finds that, with two real corpora themselves told apart almost perfectly, the word \"closer than two real corpora\" says nothing of realism"
    return met(text)


@recorded("study")
def study_preprocessing_fit(run):
    """REFORMS 6a: what is fit on which rows."""
    return met("every classifier fits its scaler and PCA inside its own pipeline on the rows it is trained on: the C2ST's in each fold on the folds that hold none of the scored rows' persons, and the classifier that calls each synthetic group on the real rows alone (tools/domain_gap_stats.py, classifier, c2st and nearest_real), so no row shapes its own score; each image is windowed by its own percentiles, so decoding fits nothing across images (README section 3);"
               f" the standardised features and first 64 components that the MMD, FD64, KID64, PRDC and the structure measures read are fit on every row of the reading without its labels, so they are the same under every permutation of a test's labels ({at_commit(run)}, space_head)")


@frozen
def study_feature_legitimacy(run):
    """REFORMS 6c: what keeps some of a corpus's file properties from telling it apart, and what not."""
    return met("every feature is computed from one image's pixels alone, by the encoders and the physics measures (tools/domain_gap.py, stage_features), and two steps before them keep file properties from telling corpora apart (README section 3): each image is cut to its centre square, so no pad's flat border marks a corpus of non-square images, and resized to 256 alike, so the resolution step is the same for every group;"
               " each is also windowed to its own percentiles, and the primary reading is invariant to inversion, so polarity alone separates nothing in it; what still tells corpora apart besides realism, their anatomy, devices, eras and formats (JPEG re-exports, 16-bit scans, DICOM) among them, was listed before the run in README section 5")


@frozen
def study_statistical_tests(run):
    """REFORMS 7c: the tests and what each assumes."""
    family = "; CLAIM 29 says which family this run's MMD q took" if answers_it(study_uncertainty, run) else ""
    persons = "; README section 6 finds DeepFluoro's persons are DICOM patient ids over six specimens and two phantoms, so its p-values and intervals are narrower than they should be, and that the paired bootstrap counts each CT's twin comparisons about twice" if section_six_says(run, "counts each CT's twin comparisons about twice") else ""
    return met("the C2ST's 100 permutations, run against each family and in the replication pairs, and the MMD's 1,000 relabel the rows by person, every row of a person moving together, so each p holds under the null that persons are exchangeable between the two sets;"
               " where both sides hold the same persons, as two render groups on one CT folder do, the two worded replication pairs among them, the sample is paired: each person's two sides are swapped between the sets or left, so the p holds under the null that a person's two sides are exchangeable (tools/domain_gap_stats.py, twin_swaps; tools/domain_gap.py, contrast and Frame.twins), and the bootstrap draws a person with both its sides;"
               " the AUC's 95 percent interval is a person-cluster bootstrap that holds the scores of each fold's trained classifiers fixed and so leaves out the variance of fitting them, which on Gaussian clouds of one law ran about two-thirds as wide as the AUC's spread and covered 0.5 in 15 of 20 (tools/domain_gap_stats.py, auc_with_interval); DEVIATIONS.md item 8 calls it too narrow for a few dozen persons and flags a split-half null by its MMD instead, while the primary words and the replication word read its lower bound (PREREG.md section 4);"
               f" Benjamini-Hochberg runs over a space's MMD p-values and over its C2ST permutation p-values (PREREG.md section 3{family}), and no file of the study states the dependence among those p-values under which it controls the false-discovery rate{persons}")


STUDY_FACTS = {
    "sources": study_sources,
    "transforms": study_transforms,
    "subsets": study_subsets,
    "missing_data": study_missing_data,
    "partitions": study_partitions,
    "disjoint": study_disjoint,
    "instruments": study_instruments,
    "software": study_software,
    "initialization": study_initialization,
    "training": study_training,
    "no_model_selection": study_no_model_selection,
    "ensembling": study_ensembling,
    "metrics": study_metrics,
    "uncertainty": study_uncertainty,
    "internal_evaluation": study_internal_evaluation,
    "no_external_model": study_no_external_model,
    "exclusions": study_exclusions,
    "endpoints": study_endpoints,
    "no_diagnosis": study_no_diagnosis,
    "code_state": study_code_state,
    "compute": study_compute,
    "reproduce": study_reproduce,
    "sources_per_group": study_sources_per_group,
    "outcome": study_outcome,
    "sample_size": study_sample_size,
    "undecoded": study_undecoded,
    "models_trained": study_models_trained,
    "aims": study_aims,
    "goal": study_goal,
    "inclusion": study_inclusion,
    "no_reference_standard": study_no_reference_standard,
    "no_annotation": study_no_annotation,
    "no_raters": study_no_raters,
    "intended_size": study_intended_size,
    "robustness": study_robustness,
    "explainability": study_explainability,
    "no_trial": study_no_trial,
    "failure_analysis": study_failure_analysis,
    "limitations": study_limitations,
    "protocol": study_protocol,
    "population": study_population,
    "population_rationale": study_population_rationale,
    "ml_rationale": study_ml_rationale,
    "sampling_frame": study_sampling_frame,
    "fitness": study_fitness,
    "representativeness": study_representativeness,
    "no_tuning": study_no_tuning,
    "baselines": study_baselines,
    "preprocessing_fit": study_preprocessing_fit,
    "feature_legitimacy": study_feature_legitimacy,
    "statistical_tests": study_statistical_tests,
}


def study_basis(key, item, study):
    """How a study answers one item: its own rule, else the checklist's."""
    return STUDIES[study]["items"][key].get(item["id"]) or (item["basis"], item["fact"])


def study_declared_facts(study):
    """The facts the study's owner answers: every item the study does not answer by code."""
    lists = checklists()
    return {study_basis(key, item, study)[1] for key in lists for item in lists[key]["items"] if study_basis(key, item, study)[0] == "declared"}


def study_answered(key, checklist, run, answers, where=None):
    config = STUDIES[run["name"]]
    facts = config.get("facts", STUDY_FACTS)
    where = where or shown(config["answers"])
    rows = []
    for item in checklist["items"]:
        basis, fact = study_basis(key, item, run["name"])
        if basis == "code":
            state, evidence = facts[fact](run) if fact in facts else missing(f"needs a study fact \"{fact}\" in the study's facts: none answers it yet")
        else:
            state, evidence = declared(fact, answers, where)
        rows.append({"id": item["id"], "section": item["section"], "asks": item["asks"], "basis": basis, "fact": fact, "state": state, "evidence": evidence})
    return rows


def study_licence_section(run):
    """Each group's licence as groups.json records it, beside data/licences.json's entry for each of
    its source ids or the plain word that there is none; no licence is worked out here."""
    lines = ["## Data and licences", ""]
    table = run["table"]
    if table is None:
        return lines + [f"Not recorded: the report {run['table_note']}, so which sources the study read, and under which licence, is not shown."]
    register = run["register"]
    rows = [(group, sources_of(group)) for group in table["groups"]]
    unlisted = sorted({source for _, sources in rows for source in sources if register_entry(source, register) is None})
    lines += [
        f"The study trains no network, so this section names no network's commercial use. Each group's licence is its text in the groups table ({run['table_note']}), copied as written; beside it is the entry data/licences.json holds for each of its source ids, through the register's alias where it has one. A group read from a folder is looked up by the folder's first part, the name the data root keeps a source under. Nothing here maps a group's text to a licence class.",
        "",
        f"- Source ids with no entry in data/licences.json: {', '.join(unlisted) or 'none'}.",
        "",
        "| group | family | source ids | licence as the groups table records it | data/licences.json |",
        "|---|---|---|---|---|",
    ]
    for group, sources in rows:
        entries = "; ".join(register_entry(source, register) or f"{source}: no entry" for source in sources) or "no source named"
        lines.append(f"| {cell(group.get('id'))} | {cell(group.get('family'))} | {cell(', '.join(sources))} | {cell(group.get('licence') or 'not recorded')} | {cell(entries)} |")
    return lines


def bench_lines(run):
    """What BENCH.md and the record lines say of the run, for the report's head."""
    bench, record = run["bench"], run["record"]
    head = bench["header"]
    lines = [f"- BENCH.md: bench {head['bench']}, job {head['job']} on {head['host']}, commit {head['commit']}, began {head['began']} UTC" if head
             else "- BENCH.md: no line of the form '# bench <name>: job <id> on <host>, commit <7 hex>, <time> UTC'"]
    lines += [f"- BENCH.md says: {line}" for line in bench["failed"]]
    if bench["exit"]:
        lines.append(f"- BENCH.md: exit {bench['exit']['rc']} at {bench['exit']['at']} UTC")
    lines.append(f"- BENCH.md's {run_log_said(bench)}.")
    states = ", ".join(f"{kind} {'read' if kind in record else run['problems'][kind]}" for kind in RECORD_LINES)
    lines.append(f"- summary.txt's record lines: {states}" + (f"; lines of kinds the report does not read: {', '.join(run['unknown'])}" if run["unknown"] else "") + ".")
    if "study" in record:
        s = record["study"]
        lines.append(f"- Study record: commit {s['commit']}, {'clean tree' if s['tree'] == 'clean' else 'DIRTY tree'}, seed {s['seed']}, plan {s['plan']}, groups.json {s['groups']}, PREREG {s['prereg']}, code {s['code']}.")
    return lines


def study_markdown(run, claim_rows, reforms_rows):
    missing_rows = [f"CLAIM {r['id']}" for r in claim_rows if r["state"] == "missing"] + [f"REFORMS {r['id']}" for r in reforms_rows if r["state"] == "missing"]
    answers = shown(run["config"]["answers"])
    lines = [
        f"# Report of study {run['name']}, run {run['dir'].name}",
        "",
        f"Written by `python3 tools/report.py write --study {run['name']}` from this folder's summary.txt and BENCH.md, the groups table the record names, the frozen pre-registration the record names with the README sections and DEVIATIONS.md items it cites, and {answers}; do not edit by hand. The study trains no network: an item about a trained model is answered for the encoders and two-sample tests it reads, or is not applicable, with the reason, where the study's design leaves out what the item asks about.",
        "",
        *bench_lines(run),
        "",
        f"Complete: **{'yes' if not missing_rows else 'no'}**" + (f"; missing {len(missing_rows)}: {', '.join(missing_rows)}." if missing_rows else "."),
        "",
        f"A met item quotes the record line, summary line or table that shows it, or restates by section the frozen pre-registration the record names and the study's README; a declared one is the owner's sentence in {answers}, which the code checks is there but cannot judge; a missing one is work to do before the numbers are published (`python3 tools/report.py check --study {run['name']} --run <folder> --complete`).",
        "",
        *study_licence_section(run),
        "",
        *checklist_section("CLAIM 2024", claim_rows),
        "",
        *checklist_section("REFORMS", reforms_rows),
        "",
        *run_log_section(run["bench"]),
    ]
    return "\n".join(lines) + "\n"


def run_log_section(bench):
    """The run's own log as BENCH.md carries it: what each step wrote, line by line with its time, as
    it ran (the owner's ask of 2026-10-28 00:23 UTC, "make sure there is realtime logging in the
    CLAIMS/REPORT"), copied whole, or why there is none."""
    lines = ["## Run log", ""]
    if bench["runlog"] is None:
        return lines + [f"None: {bench['runlog_why']}."]
    return lines + [
        "What each step of the run wrote while it ran, each line with its date and time UTC: prepare's stages, the array's tasks with their nodes and cards, every unit that failed (by the kind of error alone), every claim taken over from a task that stopped beating, every pool a dead worker broke, every unit whose MMD a full card sent to the CPU, how each task ended, Slurm's TERM among the ends, and the merge's reading back; the units by their first done and each quarter of the list. Copied from BENCH.md, which the merge wrote from the run folder's run log (tools/domain_gap.py runlog): the tasks' routine starts and finishes folded into one line each, and the units a full card sent to the CPU into one, and, where more than 50 lines were left, lines left out with one line saying how many: never a quarter mark, and a line of something gone wrong only where more of them were left than the 50 lines hold, the first and the last of them kept; the run folder's RUNLOG.txt keeps every line the run log took, at most 400 a step, and every unit this chain's tasks did, and stays on the grid.",
        "",
        *fenced(bench["runlog"]),
    ]


def fenced(lines):
    """lines as a Markdown code block whose fence is longer than any run of backticks in them, so
    no line of the log can close it early."""
    longest = max((len(run) for line in lines for run in re.findall(r"`+", line)), default=0)
    fence = "`" * max(3, longest + 1)
    return [f"{fence}text", *lines, fence]


def study_run(name, run_dir):
    """A recorded run of the study as its facts read it, by the study's own reader where it has
    one; a folder its reader refuses is refused here in the report's words."""
    config = STUDIES[name]
    try:
        return config.get("load", load_study)(name, run_dir)
    except config.get("error", ReportError) as error:
        raise ReportError(str(error)) from error


def answers_for(path, run):
    """The owner's answers that hold for this run, and where the report says they are: every field
    where the file names no run, and none where its _run names another, since an abstract written
    from one run's numbers is not another run's."""
    if not path.is_file():
        raise ReportError(f"{shown(path)}: the study's answers file is not there")
    for_run = json.loads(path.read_text(encoding="utf-8")).get("_run")
    if for_run is not None and not (isinstance(for_run, str) and for_run):
        raise ReportError(f"{shown(path)}: _run names a run folder and must be a string that is not empty, not {for_run!r}")
    if for_run in (None, run["dir"].resolve().name):
        return study_answers(path), shown(path)
    return {}, f"{shown(path)}, whose answers are run {for_run}'s, not this run's"


def render_study(name, run_dir):
    """The three files of a recorded study run's report, from its folder and the study's answers."""
    config = STUDIES[name]
    run = study_run(name, run_dir)
    run.setdefault("config", config)
    answers_path = Path(config["answers"])
    lists, (answers, where) = checklists(), answers_for(answers_path, run)
    claim_rows = study_answered("claim", lists["claim"], run, answers, where)
    reforms_rows = study_answered("reforms", lists["reforms"], run, answers, where)
    answers_sha = hashlib.sha256(answers_path.read_bytes()).hexdigest()

    def document(checklist, rows):
        return json.dumps({"study": name, "run_id": run["dir"].name, "checklist": checklist["name"], "source": checklist["source"], "study_sha256": answers_sha, "tally": tally(rows), "items": rows}, indent=1) + "\n"

    return {
        "REPORT.md": study_page(name, run, claim_rows, reforms_rows, answers_path),
        "claim.json": document(lists["claim"], claim_rows),
        "reforms.json": document(lists["reforms"], reforms_rows),
    }


def study_page(name, run, claim_rows, reforms_rows, answers_path):
    """REPORT.md of a study run: the study's own page where it writes one, else the DRR study's."""
    page = STUDIES[name].get("markdown")
    return page(run, claim_rows, reforms_rows, checklist_section, shown(answers_path)) if page else study_markdown(run, claim_rows, reforms_rows)


def recorded_studies():
    """Every recorded study run, (study, folder): each folder under a study's runs/."""
    found = []
    for name, config in STUDIES.items():
        runs = Path(config["runs"])
        found += [(name, folder) for folder in sorted(runs.iterdir()) if folder.is_dir()] if runs.is_dir() else []
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("write", "check"):
        command = sub.add_parser(name)
        command.add_argument("--run", required=True)
        command.add_argument("--study", choices=sorted(STUDIES), help="read the folder as a recorded run of this study (drr-domain-gap: BENCH.md and summary.txt; flux-realism: flows/realism.py's RECORD.json; autoanatomist-screen: flows/autoanatomist.py's RECORD.json), not a training run")
        if name == "check":
            command.add_argument("--complete", action="store_true", help="fail while any item is missing")
    sub.add_parser("write-recorded")
    sub.add_parser("check-recorded")
    args = parser.parse_args(argv)
    try:
        if args.command == "write":
            return write(args.run, args.study)
        if args.command == "check":
            return check(args.run, args.complete, args.study)
        runs = [(None, run) for run in recorded_runs()] + recorded_studies()
        if args.command == "write-recorded":
            return max([write(run, study) for study, run in runs], default=0)
        return max([check(run, study=study) for study, run in runs], default=0)
    except ReportError as error:
        print(f"report: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
