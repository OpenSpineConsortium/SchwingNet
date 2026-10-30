"""The CLAIM 2024 and REFORMS report of a chain of the auto-anatomist screen, as tools/report.py's
study autoanatomist-screen.

    python3 tools/report.py write --study autoanatomist-screen --run <chain folder>
    python3 tools/report.py check --study autoanatomist-screen --run <chain folder> [--complete]

A chain folder is what one send of the screen kept, <screen root>/<plan>/<chain>/ on the grid
(flows/autoanatomist.py): RECORD.json, which the join's end wrote, and the files it names by their
sha256, every trial's entry.json and environment.json (or the why.txt of a trial that wrote no
entry) and the join's DECISION.json. A code answer reads only those files and the frozen design,
never infers, and is missing where a file is absent, is no longer the bytes the record names, or
lacks a field the answer quotes; an answer that restates the frozen PREREG.md holds only for a
chain whose record names its sha256, DESIGN, so a second design is never reported in this one's
words. A screen selects arms for a longer run and publishes nothing, so the items no file answers,
the owner's own (the title, the abstract, the background and the rest), stay missing until the
owner writes them in data/reporting/studies/autoanatomist-screen.json; a session never writes them.
Standard library only, as tools/report.py is.
"""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STUDY = "autoanatomist-screen"
PREREG = ROOT / "docs" / "research" / "autoanatomist-screen" / "PREREG.md"
# The pre-registration the design answers restate, by its sha256: PREREG.md as frozen, the digest
# PREREG.md.sha256 beside it holds (tests/test_autoanatomist_report.py holds the two together).
DESIGN = "648c082994464ecb26bab977ce51a49441a6bfaa92751f562d7b8c704ee44280"
LICENCES = ROOT / "data" / "licences.json"
SOURCE = "scidb_enhance_pet_1_6k"

ITEMS = {
    "claim": {
        "7": ("code", "sources"), "9": ("code", "transforms"), "12": ("code", "missing_data"), "19": ("code", "partitions"),
        "20": ("code", "disjoint"), "22": ("code", "model"), "23": ("code", "software"), "24": ("code", "initialization"),
        "25": ("code", "training"), "26": ("code", "model_selection"), "27": ("code", "ensembling"), "28": ("code", "metrics"),
        "29": ("code", "uncertainty"), "32": ("code", "internal_evaluation"), "35": ("code", "exclusions"),
        "37": ("code", "performance"), "38": ("code", "performance"), "39": ("code", "failure_analysis"),
        "40": ("code", "limitations"), "42": ("code", "protocol"),
    },
    "reforms": {
        "2a": ("code", "sources"), "2b": ("code", "code_state"), "2c": ("code", "compute"), "2d": ("code", "reproduce"),
        "2e": ("code", "reproduce"), "3a": ("code", "per_part"), "3e": ("code", "sample_size"), "3f": ("code", "missing_data"),
        "4a": ("code", "exclusions"), "4b": ("code", "exclusions"), "4c": ("code", "transforms"), "5a": ("code", "models_trained"),
        "5c": ("code", "partitions"), "5d": ("code", "model_selection"), "6b": ("code", "disjoint"), "7a": ("code", "metrics"),
        "7b": ("code", "uncertainty"),
    },
}


class AutoanatomistReportError(Exception):
    """A folder that is not a chain of the screen, said in words."""


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def sha256_of(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def checked(folder, record, name):
    """A file the record names, read only while its bytes are those it names: (value, None), or
    (None, why not)."""
    named = (record.get("files") or {}).get(name)
    if named is None:
        return None, f"{name} is not among the files RECORD.json names"
    found = sha256_of(Path(folder) / name)
    if found is None:
        return None, f"{name} is not in the folder"
    if found != named:
        return None, f"{name} is not the file RECORD.json names (sha256 {found[:16]}, named {named[:16]})"
    value = read_json(Path(folder) / name)
    return (value, None) if isinstance(value, dict) else (None, f"{name} is not a JSON object")


def load(name, run_dir):
    """A chain folder's files as the facts read them; a folder with no RECORD.json of the screen is
    not a chain of it."""
    run_dir = Path(run_dir)
    record = read_json(run_dir / "RECORD.json")
    if not isinstance(record, dict) or record.get("study") != STUDY:
        raise AutoanatomistReportError(f"{run_dir}: no RECORD.json of the study {STUDY}, so this is not a chain of the screen")
    run = {"dir": run_dir, "name": name, "record": record, "register": read_json(LICENCES) or {}, "entries": {},
           "environments": {}, "gaps": {}}
    run["decision"], run["gaps"]["decision"] = checked(run_dir, record, "join/DECISION.json")
    for trial in record.get("trials") or []:
        tid = trial.get("id")
        run["entries"][tid], run["gaps"][f"entry {tid}"] = checked(run_dir, record, f"trials/{tid}/entry.json")
        run["environments"][tid], run["gaps"][f"environment {tid}"] = checked(run_dir, record, f"trials/{tid}/environment.json")
    return run


def met(evidence):
    return "met", evidence


def missing(why):
    return "missing", why


def needs(run, *keys):
    """Why the files under these gap keys cannot answer, or empty where each was read."""
    gaps = [run["gaps"][key] for key in keys if run["gaps"].get(key)]
    return "needs " + "; ".join(gaps) if gaps else ""


def design_gap(run):
    """Why the design's words do not hold for this chain, or empty where its record names DESIGN."""
    named = run["record"].get("prereg_sha256")
    return "" if named == DESIGN else (f"RECORD.json names PREREG sha256 {str(named)[:16]}, not the frozen "
                                      f"{DESIGN[:16]}: the chain ran another design, which this report does not restate")


def restated(run, text):
    """An answer that restates the frozen design, for a chain that ran it."""
    gap = design_gap(run)
    return missing(gap) if gap else met(f"{text} (PREREG.md, sha256 {DESIGN[:16]})")


def plan(run):
    return run["record"].get("plan") or {}


def held(run):
    """The entries read and whole, by trial."""
    return {tid: entry for tid, entry in run["entries"].items() if entry}


def fact_sources(run):
    rows = plan(run).get("rows") or {}
    entry = (run["register"].get("sources") or {}).get(SOURCE)
    licence = f"{entry.get('licence')}, class {entry.get('class')}" if entry else "no entry in data/licences.json"
    return restated(run, f"ENHANCE.PET 1.6k studies of the gold tier 3 store, read from the data root's aws_enhance_pet_ct "
                         f"and aws_enhance_pet_labels as they are; {rows.get('train')} training and {rows.get('validation')} "
                         f"validation rows in {plan(run).get('file')} (RECORD.json); licence {licence}")


def fact_transforms(run):
    return restated(run, "each level C3 to L6 one crop of 48 by 56 by 32 voxels at 2 mm about its mask's centroid with a fixed "
                         "jitter per row, every other label taken out of the label map first (PREREG.md section 2)")


def fact_missing_data(run):
    return restated(run, "no imputation: a row whose CT or label map is missing stops its trial with exit 2 before it trains, "
                         "and the trial is shown failed (PREREG.md section 5)")


def split_files(run):
    """The split files the chain's start checked its plan against, each by the first 16 hex of its sha256."""
    files = run["record"].get("splits") or {}
    return "; ".join(f"{path} {str(sha)[:16]}" for path, sha in sorted(files.items())) or "none recorded"


def fact_partitions(run):
    return restated(run, "a person is a study, its part the one data/splits/rule.json gives it (salt schwingnet-2026-10-21, "
                         "validation share 0.1), and each unit of probable repeat scans keeps the part its key's person has; "
                         "no person on a test list (data/splits/test-persons.json and the latent shape priors' reserve) is "
                         f"read and the test part is never read; the files checked: {split_files(run)}")


def fact_disjoint(run):
    return restated(run, "the flow's start refuses a plan whose rows leave the rule, stand on a test list or put a study of a "
                         "unit of probable repeat scans outside its unit's part, so each study and each unit sits in one part; "
                         "known limit: autoPET's 1,014 studies are 900 persons with no record matching them, and the units "
                         "link repeat scans by their vertebral volumes, spacings and ribs alone, so a repeat they miss can "
                         "still sit in both parts (PREREG.md section 6)")


def fact_model(run):
    trials = run["record"].get("trials") or []
    if not trials:
        return missing("needs the trials RECORD.json names")
    arms = sorted({t.get("arm") for t in trials})
    return met(f"the auto-anatomist of grid/autoanatomist/ under objective=mask, one network a trial, {len(trials)} trials, "
               f"arms {', '.join(arms)}; the words of {trials[0].get('id')}: {' '.join(trials[0].get('words') or [])}")


def fact_software(run):
    gap = needs(run, *(f"environment {tid}" for tid in run["environments"]))
    if gap:
        return missing(gap)
    first = next(iter(run["environments"].values()), None)
    if not first:
        return missing("needs a trial's environment.json")
    packages = ", ".join(f"{k} {v}" for k, v in sorted((first.get("packages") or {}).items()))
    return met(f"Python {first.get('python')}, {packages} (trials/*/environment.json)")


def fact_initialization(run):
    seeds = sorted({entry.get("seed") for entry in held(run).values()})
    if not seeds:
        return missing("needs an entry that holds")
    return met(f"random initialisation from each trial's seed ({', '.join(map(str, seeds))}), no weights from elsewhere "
               "(trials/*/entry.json)")


def fact_training(run):
    p = plan(run)
    steps = sorted({entry.get("steps") for entry in held(run).values()})
    return met(f"{p.get('epochs')} epochs at batch {p.get('batch')}, {', '.join(map(str, steps)) or 'no'} steps a trial, the "
               "anneal spanning the run in one training call (RECORD.json, trials/*/entry.json)")


def fact_model_selection(run):
    return restated(run, "none: every trial is read at its last epoch; no checkpoint, reading or seed is chosen on the "
                         "validation part")


def fact_ensembling(run):
    return restated(run, "none: each trial is one network, and no ensemble is made until one model works")


def fact_metrics(run):
    return restated(run, f"the mean symmetric surface distance of the target vertebra's mask in mm from the CT alone, "
                         f"{plan(run).get('measure')}, primary; Dice, the centroid error and the share named right beside it, "
                         f"each read every {plan(run).get('evaluate_every')} epochs")


def fact_uncertainty(run):
    return restated(run, f"{len(plan(run).get('seeds') or [])} seeds an arm and no interval: an arm beats the null only when "
                         "every one of its finals is below every one of the null's, which an arm no different passes by chance "
                         "one time in six at two seeds a side (PREREG.md section 4)")


def fact_internal_evaluation(run):
    rows = (plan(run).get("rows") or {}).get("validation")
    return met(f"the {rows} validation CTs of the plan, every level a crop, read by the CT-only path at each reading "
               "(trials/*/entry.json, epochs)")


def fact_exclusions(run):
    gap = needs(run, "decision")
    if gap:
        return missing(gap)
    failed = run["decision"].get("failed") or {}
    said = "; ".join(f"{tid}: {why}" for tid, why in sorted(failed.items())) or "none"
    return met(f"trials shown failed, never dropped: {said} (join/DECISION.json)")


def fact_performance(run):
    gap = needs(run, "decision")
    if gap:
        return missing(gap)
    d = run["decision"]
    arms = "; ".join(f"{arm} {a.get('finals')}: {a.get('why')}" for arm, a in sorted((d.get("arms") or {}).items()))
    return met(f"final {d.get('measure')}, the null {d.get('null_finals')}; {arms} (join/DECISION.json)")


def fact_failure_analysis(run):
    gap = needs(run, "decision")
    if gap:
        return missing(gap)
    return met("each failed trial's reason, from its why.txt, in join/DECISION.json's failed; the by-level figures of every "
               "reading are in each trial's readings.jsonl on the grid")


def fact_limitations(run):
    return restated(run, "crops centred on each level's true centroid, so finding a vertebra is not measured; a person is a study, "
                         "so autoPET's repeat scans may cross the parts; one population and one network size; each reading a "
                         "mean over all levels (PREREG.md section 6)")


def fact_protocol(run):
    gap = design_gap(run)
    return missing(gap) if gap else met(f"docs/research/autoanatomist-screen/PREREG.md, frozen, sha256 {DESIGN[:16]}, its "
                                        f"Covers line naming the plan by its bytes ({str(run['record'].get('prereg_part'))})")


def fact_code_state(run):
    record = run["record"]
    where = record.get("where") or {}
    return met(f"commit {record.get('commit')}, run from a copy of it ({where.get('copy_of') or 'no copy named'}), "
               f"run {record.get('run')} (RECORD.json)")


def fact_compute(run):
    lines = []
    for tid, env in sorted(run["environments"].items()):
        if env:
            lines.append(f"{tid} on {env.get('host')}, {env.get('backend')} {', '.join(env.get('devices') or [])}, "
                         f"{env.get('train_and_read_seconds')} s")
    return met("; ".join(lines) + " (trials/*/environment.json)") if lines else missing("needs a trial's environment.json")


def fact_reproduce(run):
    return met(f"grid/gate.sh's word `autoanatomist {plan(run).get('screen')}` at commit {run['record'].get('commit')}, under "
               "the frozen PREREG and the plan its Covers line names")


def fact_per_part(run):
    rows = plan(run).get("rows") or {}
    return met(f"{rows.get('train')} training and {rows.get('validation')} validation studies, the test part not read "
               "(RECORD.json)")


def fact_sample_size(run):
    return restated(run, "the screen's sizes are its budget, 96 training and 24 validation studies at two seeds an arm, chosen "
                         "to select arms for a longer run, not powered for an effect")


def fact_models_trained(run):
    return met(f"{len(run['record'].get('trials') or [])} networks, one a trial, of which {len(held(run))} wrote an entry "
               "(RECORD.json, trials/*/entry.json)")


FACTS = {
    "sources": fact_sources, "transforms": fact_transforms, "missing_data": fact_missing_data, "partitions": fact_partitions,
    "disjoint": fact_disjoint, "model": fact_model, "software": fact_software, "initialization": fact_initialization,
    "training": fact_training, "model_selection": fact_model_selection, "ensembling": fact_ensembling,
    "metrics": fact_metrics, "uncertainty": fact_uncertainty, "internal_evaluation": fact_internal_evaluation,
    "exclusions": fact_exclusions, "performance": fact_performance, "failure_analysis": fact_failure_analysis,
    "limitations": fact_limitations, "protocol": fact_protocol, "code_state": fact_code_state, "compute": fact_compute,
    "reproduce": fact_reproduce, "per_part": fact_per_part, "sample_size": fact_sample_size,
    "models_trained": fact_models_trained,
}


def markdown(run, claim_rows, reforms_rows, checklist_section, answers_shown):
    record = run["record"]
    missing_rows = [f"CLAIM {r['id']}" for r in claim_rows if r["state"] == "missing"]
    missing_rows += [f"REFORMS {r['id']}" for r in reforms_rows if r["state"] == "missing"]
    lines = [
        f"# Report of study {STUDY}, chain {record.get('chain')} of {plan(run).get('screen')}",
        "",
        f"Written by `python3 tools/report.py write --study {STUDY}` from this folder's RECORD.json and the files it names by "
        f"their sha256, and {answers_shown}; do not edit by hand. Commit {record.get('commit')}, PREREG sha256 "
        f"{str(record.get('prereg_sha256'))[:16]}, run {record.get('run')}, {record.get('started')} to {record.get('ended')} UTC.",
        "",
        f"Complete: **{'yes' if not missing_rows else 'no'}**" + (f"; missing {len(missing_rows)}: {', '.join(missing_rows)}." if missing_rows else "."),
        "",
        "A screen selects arms for a longer run and publishes nothing; a missing item is work to do before any number of it "
        f"is published (`python3 tools/report.py check --study {STUDY} --run <folder> --complete`).",
        "",
        *checklist_section("CLAIM 2024", claim_rows),
        "",
        *checklist_section("REFORMS", reforms_rows),
    ]
    return "\n".join(lines) + "\n"
