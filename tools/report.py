"""Write a run's report: the CLAIM 2024 and REFORMS checklists answered, and the data's licences.

Usage:
    python3 tools/report.py write --run <run folder>        # REPORT.md, claim.json, reforms.json
    python3 tools/report.py check --run <run folder> [--complete]
    python3 tools/report.py write --study drr-domain-gap --run <study run folder>
    python3 tools/report.py check --study drr-domain-gap --run <study run folder> [--complete]
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
record names; its owner's answers come from data/reporting/studies/<study>.json; an item a
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

# How the DRR domain-gap study answers each item a training run answers by code, and the two it
# hands to the owner: ("code", fact) is read from the recorded folder by STUDY_FACTS, ("declared",
# fact) is the owner's sentence in the study's answers file. Every other item is declared under its
# checklist fact, as for a training run.
DRR_GAP_ITEMS = {
    "claim": {
        "7": ("code", "sources"), "9": ("code", "transforms"), "10": ("code", "subsets"),
        "12": ("code", "missing_data"), "19": ("code", "partitions"), "20": ("code", "disjoint"),
        "22": ("code", "instruments"), "23": ("code", "software"), "24": ("code", "initialization"),
        "25": ("code", "training"), "26": ("code", "no_model_selection"), "27": ("code", "ensembling"),
        "28": ("code", "metrics"), "29": ("code", "uncertainty"), "32": ("code", "internal_evaluation"),
        "33": ("code", "no_external_model"), "35": ("code", "exclusions"), "36": ("declared", "characteristics"),
        "37": ("code", "endpoints"), "38": ("code", "no_diagnosis"), "39": ("declared", "failure_analysis"),
    },
    "reforms": {
        "2a": ("code", "sources"), "2b": ("code", "code_state"), "2c": ("code", "compute"),
        "2d": ("code", "reproduce"), "2e": ("code", "reproduce"), "3a": ("code", "sources_per_group"),
        "3d": ("code", "outcome"), "3e": ("code", "sample_size"), "3f": ("code", "missing_data"),
        "4a": ("code", "exclusions"), "4b": ("code", "undecoded"), "4c": ("code", "transforms"),
        "5a": ("code", "models_trained"), "5c": ("code", "partitions"), "5d": ("code", "no_model_selection"),
        "6b": ("code", "disjoint"), "7a": ("code", "metrics"), "7b": ("code", "uncertainty"),
    },
}

STUDIES = {
    "drr-domain-gap": {
        "answers": ROOT / "data" / "reporting" / "studies" / "drr-domain-gap.json",
        "runs": ROOT / "docs" / "research" / "drr-domain-gap" / "runs",
        "groups": ROOT / "data" / "domain_gap" / "groups.json",
        "prereg": ROOT / "docs" / "research" / "drr-domain-gap" / "PREREG.md",
        "items": DRR_GAP_ITEMS,
        # The pre-registered primary endpoints (README section 4): FleXray's physical render, the
        # same from the CT alone and FluXray, each against pooled fluoroscopy and pooled film in
        # FleXray's space, read inversion-invariant.
        "primary_space": "flexray",
        "endpoints": ("flexray_drr", "flexray_drr_ct", "fluxray"),
        "families": ("fluoroscopy", "film"),
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
                         r" auc interval above half [0-9]+")
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
            "failed": [line[2:] for line in lines if line.startswith("- FAILED")]}


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
               f" each interval the 95 percent percentile interval of a person-cluster bootstrap of 1,000 draws, the C2ST's p from 100 permutations and the MMD's from 1,000, all by person, and the q by Benjamini-Hochberg within a space ({at_commit(run)} and tools/domain_gap_stats.py, README section 4)")


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


def flagged_of(space):
    """The groups the space's calibration lines flag, and the count its first line gives, or None
    where the space has no calibration line in its form."""
    lines = space.get("lines", [])
    head = next((m for m in map(CALIBRATION.fullmatch, lines) if m), None)
    names = [name for line in lines if line.startswith(FLAGGED) for name in line[len(FLAGGED):].split()]
    return names, int(head["count"]) if head else None


def endpoint_lines(run):
    """The primary endpoints' lines in the primary space, the endpoints summary.txt lacks, and those
    not read because the space's split-half null of the group was flagged."""
    config, groups = run["config"], run["body"]["groups"]
    space = config["primary_space"]
    lines = run["body"]["spaces"].get(space, {}).get("lines", [])
    flagged, _ = flagged_of(run["body"]["spaces"].get(space, {}))
    found, absent, unread = [], [], []
    for group in config["endpoints"]:
        for family in config["families"]:
            line = next((line.strip() for line in lines if line.startswith(f" {group} vs {family} auc ")), "")
            skipped = (groups.get(group) or {}).get("reason")
            if line and group in flagged:
                unread.append(f"{group} vs {family}: the split-half null of {group} in {space} found a difference, so its contrasts are not read (DEVIATIONS.md, item 8)")
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
    return met(text + (f"; the replication verdict: {'; '.join(verdicts)}" if verdicts else ""))


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
    return met(f"{ran}, on GPUs {jobs['gpu']} x{jobs['gpus']}; seconds by stage: {stages} (summary.txt record){tail}")


@recorded("study")
def study_reproduce(run):
    """REFORMS 2d, 2e: what runs the study again."""
    study, gap = run["record"]["study"], prereg_gap(run)
    if gap:
        return missing(gap)
    prereg = f"the frozen pre-registration PREREG.md {study['prereg']}" if study["prereg"] != "none" else "no frozen pre-registration (PREREG none)"
    return met(f"at commit {study['commit']}, the gate words and local commands of docs/research/drr-domain-gap/README.md section 7, over the groups table {study['groups']} with seed {study['seed']}, the plan the run made being {study['plan']}, with {prereg} (summary.txt record)")


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
}


def study_basis(key, item, study):
    """How a study answers one item: its own rule, else the checklist's."""
    return STUDIES[study]["items"][key].get(item["id"]) or (item["basis"], item["fact"])


def study_declared_facts(study):
    """The facts the study's owner answers: every item the study does not answer by code."""
    lists = checklists()
    return {study_basis(key, item, study)[1] for key in lists for item in lists[key]["items"] if study_basis(key, item, study)[0] == "declared"}


def study_answered(key, checklist, run, answers):
    rows = []
    for item in checklist["items"]:
        basis, fact = study_basis(key, item, run["name"])
        if basis == "code":
            state, evidence = STUDY_FACTS[fact](run) if fact in STUDY_FACTS else missing(f"needs a study fact \"{fact}\" in tools/report.py: none answers it yet")
        else:
            state, evidence = declared(fact, answers, shown(run["config"]["answers"]))
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
        f"Written by `python3 tools/report.py write --study {run['name']}` from this folder's summary.txt and BENCH.md, the groups table the record names and {answers}; do not edit by hand. The study trains no network: an item about a trained model is answered for the encoders and two-sample tests it reads, or is not applicable, with the reason, where the study's design leaves out what the item asks about.",
        "",
        *bench_lines(run),
        "",
        f"Complete: **{'yes' if not missing_rows else 'no'}**" + (f"; missing {len(missing_rows)}: {', '.join(missing_rows)}." if missing_rows else "."),
        "",
        f"A met item quotes the record line, summary line or table that shows it; a declared one is the owner's sentence in {answers}, which the code checks is there but cannot judge; a missing one is work to do before the numbers are published (`python3 tools/report.py check --study {run['name']} --run <folder> --complete`).",
        "",
        *study_licence_section(run),
        "",
        *checklist_section("CLAIM 2024", claim_rows),
        "",
        *checklist_section("REFORMS", reforms_rows),
    ]
    return "\n".join(lines) + "\n"


def render_study(name, run_dir):
    """The three files of a recorded study run's report, from its folder and the study's answers."""
    run = load_study(name, run_dir)
    answers_path = Path(run["config"]["answers"])
    lists, answers = checklists(), study_answers(answers_path)
    claim_rows = study_answered("claim", lists["claim"], run, answers)
    reforms_rows = study_answered("reforms", lists["reforms"], run, answers)
    answers_sha = hashlib.sha256(answers_path.read_bytes()).hexdigest()

    def document(checklist, rows):
        return json.dumps({"study": name, "run_id": run["dir"].name, "checklist": checklist["name"], "source": checklist["source"], "study_sha256": answers_sha, "tally": tally(rows), "items": rows}, indent=1) + "\n"

    return {
        "REPORT.md": study_markdown(run, claim_rows, reforms_rows),
        "claim.json": document(lists["claim"], claim_rows),
        "reforms.json": document(lists["reforms"], reforms_rows),
    }


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
        command.add_argument("--study", choices=sorted(STUDIES), help="read the folder as a recorded run of this study (BENCH.md and summary.txt), not a training run")
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
