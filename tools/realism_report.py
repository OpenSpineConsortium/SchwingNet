"""The CLAIM 2024 and REFORMS report of a run of the FluXray reproduction, as tools/report.py's study
flux-realism.

    python3 tools/report.py write --study flux-realism --run <run folder>
    python3 tools/report.py check --study flux-realism --run <run folder> [--complete]

A run folder is what flows/realism.py's run kept, <realism root>/<stage>-<key>-<run id>/ on the grid
or a copy of its small files under docs/research/flux-realism/runs/: RECORD.json, the record the
flow's end wrote, and the files it names, each by its sha256. A stats run holds the edit's small
files under edit/, copied when it began, so one folder answers the whole report; an edit run
answers what the edit made and leaves the statistics missing, saying they wait for the stats stage.
The two stages are two GPU jobs, which may run on other nodes, cards and commits, so what a job ran
on is said job by job, each from the files that job wrote: the edit's from its record and its
inputs.json, the stats job's from its own record and environment.json.

A code answer reads only those files and the frozen design, never infers, and is missing where a
file is absent, is no longer the bytes the record names, or lacks a field the answer quotes. The
owner asked on 2026-10-29 at 03:35 UTC, of the DRR study's report, "why would I answer these
question instead of having a real meta flow run generate them?", so every item the study's own
files answer is answered here; an answer that restates the frozen design (PREREG.md, DEVIATIONS.md,
README.md) holds only for a run whose records name that design's bytes, DESIGN, so a second design
is never reported in this one's words. What no file says is the owner's, in
data/reporting/studies/flux-realism.json, into which a session copies only the owner's own words.
The study trains no network: an item about a trained model is answered for the released models it
uses as they are, or is not applicable, with the reason quoted. Standard library only, as
tools/report.py is.
"""

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STUDY = "flux-realism"
COMPARISONS = ("kept", "raw")
PREREG = ROOT / "docs" / "research" / "flux-realism" / "PREREG.md"
# The pre-registration the design answers restate, by its sha256: PREREG.md as frozen on
# 2026-10-29, the digest PREREG.md.sha256 beside it holds. A run whose records name other bytes
# ran another design, and every answer that restates this one is missing for it.
DESIGN = "580c45288aff4097e97e24369739f41a1ddf285b7e8ffea6d7e8919202b4dbdd"
LICENCES = ROOT / "data" / "licences.json"
# The register's entry for each source of the study, where it has one, by the fetch row's name.
SOURCES = {
    "hf_flexray_data": "FluXray, the folder FluXray/ of the Hugging Face dataset VictorButoi/flexray-data",
    "scidb_enhance_pet_1_6k": "ENHANCE.PET 1.6k, Science Data Bank doi:10.57760/sciencedb.34150, the bucket enhance-pet-1-6k",
    "hf_flux2_klein_9b": "FLUX.2 klein-9B, black-forest-labs/FLUX.2-klein-9B",
    "hf_flexray_weights": "FleXray's weights, VictorButoi/flexray, member flux000",
}
# How the departures after the freeze are cited beside the PREREG section they change.
AFTER_FREEZE = 'DEVIATIONS.md, "From PREREG.md, after the freeze"'
FROM_PAPER = "DEVIATIONS.md, \"From the paper's recipe, fixed at the freeze\""
NO_TRAINING = "not applicable: the study trains no network; it edits with released weights and tests two sets apart (PREREG.md, section 6)"
NO_COMPONENTS = ("needs the number of principal components each space was read on, \"components\" in each comparison of "
                 "kept/stats.json and raw/stats.json, which tools/realism.py stats writes")
NO_STRATA = ("needs the strata each permutation test shuffled within, \"strata\" in each test of kept/stats.json and "
             "raw/stats.json, which tools/realism.py stats writes")

# How the study answers each item: ("code", fact) is read from the run folder by FACTS, ("declared",
# fact) is the owner's sentence in the study's answers file, as is every item listed in neither.
# Since the owner's ask of 2026-10-29 at 03:35 UTC every item the study's files or its frozen
# design answer is code; what is left for the owner is what no file of the study says: the
# paper's title, abstract and background, the data's de-identification, the implications, what
# will be made available, the funding, and how far the findings reach beyond FluXray.
ITEMS = {
    "claim": {
        "4": ("code", "aims"), "5": ("code", "study_design"), "6": ("code", "study_goal"), "7": ("code", "sources"),
        "8": ("code", "inclusion_exclusion"), "9": ("code", "transforms"), "10": ("code", "subsets"),
        "12": ("code", "missing_data"), "13": ("code", "acquisition"), "14": ("code", "no_reference_standard"),
        "15": ("code", "no_reference_standard"), "16": ("code", "no_annotation"), "17": ("code", "no_annotation"),
        "18": ("code", "no_raters"), "19": ("code", "partitions"), "20": ("code", "disjoint"),
        "21": ("code", "intended_sample_size"), "22": ("code", "instruments"), "23": ("code", "software"),
        "24": ("code", "initialization"), "25": ("code", "training"), "26": ("code", "no_model_selection"),
        "27": ("code", "ensembling"), "28": ("code", "metrics"), "29": ("code", "uncertainty"), "30": ("code", "robustness"),
        "31": ("code", "explainability"), "32": ("code", "internal_evaluation"), "33": ("code", "no_external_model"),
        "34": ("code", "no_trial"), "35": ("code", "exclusions"), "36": ("code", "characteristics"), "37": ("code", "endpoints"),
        "38": ("code", "no_diagnosis"), "39": ("code", "failure_analysis"), "40": ("code", "limitations"),
        "42": ("code", "protocol"),
    },
    "reforms": {
        "1a": ("code", "population"), "1b": ("code", "population_rationale"), "1c": ("code", "ml_rationale"),
        "2a": ("code", "sources"), "2b": ("code", "code_state"), "2c": ("code", "compute"), "2d": ("code", "reproduce"),
        "2e": ("code", "reproduce"), "3a": ("code", "sources_per_set"), "3b": ("code", "sampling_frame"),
        "3c": ("code", "fitness_rationale"), "3d": ("code", "outcome"), "3e": ("code", "sample_size"),
        "3f": ("code", "missing_data"), "3g": ("code", "representativeness"), "4a": ("code", "exclusions"),
        "4b": ("code", "corrupt"), "4c": ("code", "transforms"), "5a": ("code", "models_trained"),
        "5b": ("code", "model_rationale"), "5c": ("code", "partitions"), "5d": ("code", "no_model_selection"),
        "5e": ("code", "no_tuning"), "5f": ("code", "baselines"), "6a": ("code", "preprocessing_fit"),
        "6b": ("code", "disjoint"), "6c": ("code", "feature_legitimacy"), "7a": ("code", "metrics"),
        "7b": ("code", "uncertainty"), "7c": ("code", "statistical_tests"),
    },
}


class RealismReportError(Exception):
    """A folder that is not a run of the reproduction, said in words."""


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


def rows_of(path):
    try:
        with open(path, newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    except OSError:
        return None


def checked(folder, record, name, shown_as=""):
    """A file of the folder the record names, read only while its bytes are the ones it names:
    (path, None), or (None, why not), the file named as shown_as says where it lies."""
    path, said = Path(folder) / name, shown_as or name
    named = (record.get("files") or {}).get(name)
    if named is None:
        return None, f"{said} is not among the files the record names"
    found = sha256_of(path)
    if found is None:
        return None, f"{said} is not in the folder"
    if found != named:
        return None, f"{said} is not the file the record names (sha256 {found[:16]}, named {named[:16]})"
    return path, None


def copied_edit_record(run_dir, record):
    """The edit's record a stats run copied under edit/, read only where the stats record vouches
    for it, so the edit the facts describe is the edit whose files the stats run read: by its own
    sha256 where the stats record names edit/RECORD.json, else by what the stats record does name
    (unvouched). (record, None), or (None, why not)."""
    name = "edit/RECORD.json"
    if name in (record.get("files") or {}):
        path, why = checked(run_dir, record, name)
        if path is None:
            return None, f"{why}, so the edit the statistics read is not known"
        edit = read_json(path)
    else:
        edit = read_json(Path(run_dir) / name)
        why = unvouched(run_dir, record, edit) if isinstance(edit, dict) else f"{name} is not in the folder"
        if why:
            return None, f"{why}, so the edit the statistics read is not known"
    return (edit, None) if isinstance(edit, dict) else (None, f"{name} is not a record")


def unvouched(run_dir, record, edit):
    """Why a copied edit record the stats record does not name is not the edit's, or empty. The
    flow's record names every small file of its folder but those called RECORD.json, so the copy is
    held to what it does name: every edit file both records name has the same bytes, and the copied
    ENDED.json, which the edit's end wrote beside its record, names the same runs, key and times."""
    copied = {key[len("edit/"):]: digest for key, digest in (record.get("files") or {}).items() if key.startswith("edit/")}
    named = edit.get("files") or {}
    shared = [key for key in copied if key in named]
    if not shared:
        return "edit/RECORD.json names none of the edit files the stats record names"
    differ = [key for key in shared if named[key] != copied[key]]
    if differ:
        return f"edit/RECORD.json names other bytes for {', '.join(differ)} than the stats record"
    path, why = checked(run_dir, record, "edit/ENDED.json")
    if path is None:
        return why
    ended, finished = read_json(path) or {}, edit.get("ended_in") or {}
    said = {"run": finished.get("run"), "started_run": (edit.get("where") or {}).get("run"), "key": edit.get("key"),
            "started": edit.get("started"), "ended": finished.get("ended")}
    differ = [field for field, value in said.items() if ended.get(field) != value]
    return f"edit/RECORD.json and edit/ENDED.json name another {', '.join(differ)}" if differ else ""


def load(name, run_dir):
    """A run folder's files as the facts read them; a folder with no RECORD.json of this study is
    not a run of it."""
    run_dir = Path(run_dir)
    record = read_json(run_dir / "RECORD.json")
    if not isinstance(record, dict) or record.get("study") != STUDY:
        raise RealismReportError(f"{run_dir}: no RECORD.json of the study {STUDY}, so this is not a run of it")
    stats_run = record.get("stage") == "stats"
    run = {"dir": run_dir, "name": name, "record": record, "edit": record, "edit_dir": run_dir, "gaps": {},
           "register": read_json(LICENCES) or {}}
    if stats_run:
        edit, run["gaps"]["edit"] = copied_edit_record(run_dir, record)
        run["edit"], run["edit_dir"] = edit or {}, run_dir / "edit"
    shown = "edit/" if stats_run else ""
    for key, file in (("inputs", "inputs.json"), ("split", "split/split.json")):
        path, why = checked(run["edit_dir"], run["edit"], file, shown + file)
        run[key] = read_json(path) if path else None
        run["gaps"][key] = why
    run["filter"], run["gaps"]["filter"] = filter_counts(run, shown)
    path, why = checked(run_dir, record, "environment.json") if stats_run else (None, None)
    run["environment"], run["gaps"]["environment"] = read_json(path) if path else None, why
    run["stats"] = {}
    for comparison in COMPARISONS if stats_run else ():
        path, why = checked(run_dir, record, f"{comparison}/stats.json")
        run["stats"][comparison] = read_json(path) if path else None
        run["gaps"][f"stats {comparison}"] = why
    return run


def filter_counts(run, shown):
    """How many edits the paired filter kept and dropped, by its two lists' rows: (counts, None),
    or (None, why not)."""
    found = {}
    for word in ("kept", "dropped"):
        file = f"filter/filter_{word}.csv"
        path, why = checked(run["edit_dir"], run["edit"], file, shown + file)
        if path is None:
            return None, why
        found[word] = len(rows_of(path) or [])
    return found, None


# --- the facts: each reads the folder and gives a state and its evidence ---------------------------------------------

def met(evidence):
    return "met", evidence


def missing(why):
    return "missing", why


def not_applicable(reason):
    return "not applicable", reason


def is_stats(run):
    return run["record"].get("stage") == "stats"


def needs(run, *keys):
    """Why the files these facts read cannot answer, or empty where every one was read."""
    if not is_stats(run) and any(key.startswith("stats") for key in keys):
        return "needs the stats stage's run (`realism stats`), which reads this edit; this folder is the edit's"
    gaps = [run["gaps"][key] for key in keys if run["gaps"].get(key)]
    return "needs " + "; ".join(gaps) if gaps else ""


def reads(*keys):
    """A fact that reads these files: missing, naming what is absent, until each is read, and
    missing too where a file read lacks a field the fact quotes, which a fact never guesses."""

    def wrap(fact):
        def answer(run):
            gap = needs(run, *keys)
            if gap:
                return missing(gap)
            try:
                return fact(run)
            except (KeyError, TypeError) as error:
                return missing(f"needs a field the files it reads do not hold ({type(error).__name__}: {error})")

        answer.__doc__ = fact.__doc__
        return answer

    return wrap


def design_records(run):
    """Every record the folder holds, with the words that name it: a stats run's own and the edit's."""
    records = [("the record (RECORD.json)", run["record"])]
    if is_stats(run) and run["edit"]:
        records.append(("the edit's record (edit/RECORD.json)", run["edit"]))
    return records


def design_gap(run):
    """Why the answers that restate the frozen design do not hold for this run, or empty where every
    record of the folder names that design's bytes."""
    for said, record in design_records(run):
        named = record.get("prereg_sha256")
        if not named:
            return f"{said} names no PREREG sha256, so the design the run ran under is not known"
        if named != DESIGN:
            return (f"{said} names PREREG sha256 {str(named)[:16]}, and these answers restate PREREG.md {DESIGN[:16]} "
                    "(PREREG.md.sha256), so they are not this run's design")
    return ""


def frozen(fact):
    """A fact that restates the frozen design: missing, saying why, unless the run ran under it."""

    def answer(run):
        gap = design_gap(run)
        return missing(gap) if gap else fact(run)

    answer.__doc__ = fact.__doc__
    return answer


def counts(run):
    return run["edit"].get("counts") or {}


def plan_of(run):
    return run["edit"].get("plan") or {}


def recipe_of(run):
    return run["edit"].get("recipe") or {}


def edit_file(run, name):
    """A file of the edit as this folder holds it: at its root in an edit run, under edit/ in a stats run."""
    return name if run["edit_dir"] == run["dir"] else f"edit/{name}"


def dropped_share(found):
    return f"{100.0 * found['dropped'] / max(found['kept'] + found['dropped'], 1):.1f}"


# --- the jobs: each stage is one GPU job, said from its own files ----------------------------------------------------

def stages(run):
    """The jobs whose numbers this folder holds, each with its record and the environment file its
    start wrote: the edit alone in an edit run; in a stats run the edit, from the files it copied
    under edit/, then the stats job itself, since the two are separate GPU jobs that may run on
    other nodes, cards and commits."""
    edit = {"name": "edit", "record": run["edit"], "record_file": edit_file(run, "RECORD.json"),
            "environment": run["inputs"] or {}, "environment_file": edit_file(run, "inputs.json")}
    if not is_stats(run):
        return [edit]
    return [edit, {"name": "stats", "record": run["record"], "record_file": "RECORD.json",
                   "environment": run["environment"] or {}, "environment_file": "environment.json"}]


def runs_said(record):
    """Which run started the folder and which ended it, as the record names them: one where they are
    one, both where a resume, which clones start, made them two."""
    started, ended = (record.get("where") or {}).get("run") or record.get("run"), (record.get("ended_in") or {}).get("run")
    if ended in (None, started):
        return f"run {started}"
    return f"started by run {started} and, resumed, ended by run {ended}"


def resumed(where, ended):
    """Whether the run that ended the folder is another than the one that began it, both named."""
    return bool(where.get("run")) and bool(ended.get("run")) and where.get("run") != ended.get("run")


def same_job(where, ended):
    """Whether the run that ended the folder ran in the job that began it: the one run, or a resume
    in the same Slurm job on the same host. A job named none, run outside Slurm, says nothing of
    where a resume ran, so two such are not taken for one job."""
    if where.get("run") and where.get("run") == ended.get("run"):
        return True
    job = where.get("slurm_job")
    return job not in (None, "", "none") and (where.get("host"), job) == (ended.get("host"), ended.get("slurm_job"))


def said(value):
    """A field a record holds, or "not recorded" where it holds none."""
    return "not recorded" if value in (None, "") else value


def job_said(place):
    return f"Slurm job {said(place.get('slurm_job'))} on host {said(place.get('host'))}"


def resumed_elsewhere(stage):
    """Why the stage's environment file does not speak for every job that ran the stage, or empty
    where it does. Start measures the environment and a resume clones start, so a stage ended in
    another job than the one that began it ran its last steps on what no file records."""
    record = stage["record"]
    where, ended = record.get("where") or {}, record.get("ended_in")
    if not ended:
        return f"{stage['record_file']} names no ended_in, so the job that ended the {stage['name']} is not known"
    if same_job(where, ended):
        return ""
    return (f"the {stage['name']} was begun by run {said(where.get('run'))} in {job_said(where)} and resumed to its end by run "
            f"{said(ended.get('run'))} in {job_said(ended)}, whose environment no file records ({stage['record_file']}; "
            f"{stage['environment_file']} is the first job's)")


def job_lines(run):
    """Each job whose numbers the folder holds, as its own record names it, for the page's head."""
    lines = []
    for stage in stages(run):
        record = stage["record"]
        if not record:
            lines.append(f"- The {stage['name']} job: not read, {run['gaps'].get('edit')}.")
            continue
        where, ended = record.get("where") or {}, record.get("ended_in") or {}
        lines.append(f"- The {stage['name']} job ({stage['record_file']}): {runs_said(record)}, key {said(record.get('key'))}; "
                     f"begun {said(record.get('started'))} UTC in {job_said(where)} on {code_said(where)}, ended "
                     f"{said(ended.get('ended'))} UTC in {job_said(ended)} on {code_said(ended)}.")
    return lines


def code_said(place):
    """The commit a run began or ended on and the state of its tree, as its record names them."""
    commit = place.get("commit")
    if not commit:
        return "a commit not recorded"
    tree = {True: "a clean tree", False: "a DIRTY tree"}.get(place.get("clean_tree"), "a tree whose state is not recorded")
    return f"commit {str(commit)[:7]} from {tree}"


# --- what the statistics recorded ------------------------------------------------------------------------------------

def tests_of(entry):
    """The comparisons of one space's entry that the permutation tests ran on, by their words."""
    named = (("a_vs_b", "a against b"), ("b_split_half", "b's split halves"), ("arm_null", "the arm null"))
    found = [(words, entry[key]) for key, words in named if entry.get(key)]
    return found + [(f"arm {arm.removeprefix('a')} against b", test) for arm, test in sorted((entry.get("arms") or {}).items())]


def components_said(run, comparison):
    """Each space's number of principal components as the comparison's stats.json recorded it
    ("physics 57, flexray 64"), or None where a space records none."""
    spaces = run["stats"][comparison].get("spaces") or {}
    found = {space: (entry.get("a_vs_b") or {}).get("components") for space, entry in spaces.items()}
    if not found or None in found.values():
        return None
    return ", ".join(f"{space} {k}" for space, k in found.items())


def components_line(run):
    """The components of both comparisons in one clause, or None where either records none."""
    said = {comparison: components_said(run, comparison) for comparison in COMPARISONS}
    if None in said.values():
        return None
    if len(set(said.values())) == 1:
        return f"k by space {said['kept']}"
    return "k by space, " + "; ".join(f"{comparison} {line}" for comparison, line in said.items())


def strata_said(run, comparison):
    """What each permutation test of a comparison shuffled within, as its stats.json recorded it,
    the same for every space ("a against b by sample, b's split halves by subject"); None where a
    test records none, or the spaces differ, which one line cannot say."""
    lines = set()
    for entry in (run["stats"][comparison].get("spaces") or {}).values():
        said = []
        for words, test in tests_of(entry):
            kinds = {(test.get(name) or {}).get("strata") for name in ("c2st", "mmd")}
            if None in kinds or len(kinds) != 1:
                return None
            said.append(f"{words} by {kinds.pop()}")
        lines.add(", ".join(said))
    return lines.pop() if len(lines) == 1 else None


def strata_line(run):
    """Both comparisons' strata, or None where either is not recorded whole."""
    said = {comparison: strata_said(run, comparison) for comparison in COMPARISONS}
    if None in said.values():
        return None
    if len(set(said.values())) == 1:
        return f"in both comparisons alike, {said['kept']}"
    return "; ".join(f"{comparison}: {line}" for comparison, line in said.items())


def stats_words(run, comparison):
    """Each space's word of a comparison as its stats.json holds it."""
    return ", ".join(f"{space} {entry.get('verdict')}" for space, entry in (run["stats"][comparison].get("spaces") or {}).items())


# --- the facts that read the run's files ------------------------------------------------------------------------------

@frozen
@reads("edit", "inputs", "environment")
def fact_sources(run):
    """CLAIM 7, REFORMS 2a: the sources PREREG.md section 2 names, each by the sha256 the run read."""
    i = run["inputs"]
    return met(f"as PREREG.md section 2 names them, each by the sha256 the run read: FluXray (VictorButoi/flexray-data, "
               f"FluXray/): samples.csv sha256 {i['samples_sha256'][:16]}, {i['samples_rows']} rows, "
               f"its ThunderDB by its files' sha256 {i['db_sha256'][:16]}; ENHANCE.PET 1.6k (doi:10.57760/sciencedb.34150): the CT "
               f"and truth of each drawn subject by its sha256 in render/manifest.jsonl (sha256 "
               f"{str((run['edit'].get('files') or {}).get('render/manifest.jsonl'))[:16]}); {i['model']} by its files' sha256 "
               f"{i['klein_sha256'][:16]}; {weights_said(run)}")


def weights_said(run):
    """FleXray's bundle and the ResNet-18 weights by their sha256, job by job: the edit's filter read
    the bundle its inputs step hashed, and the statistics read the weights the stats job hashed."""
    i, file = run["inputs"], edit_file(run, "inputs.json")
    if not is_stats(run):
        return f"FleXray's bundle {i['bundle_sha256'][:16]} ({file})"
    e = run["environment"]
    return (f"FleXray's bundle {i['bundle_sha256'][:16]} for the edit's filter ({file}); FleXray's bundle {e['bundle_sha256'][:16]} "
            f"and ResNet-18 {e['imagenet_sha256'][:16]} for the statistics' flexray and imagenet spaces (environment.json)")


@frozen
@reads("edit")
def fact_transforms(run):
    """CLAIM 9, REFORMS 4c: every step from a CT to the compared image, the numbers as recorded."""
    plan, recipe = plan_of(run), recipe_of(run)
    return met(f"render: CT clamped to {plan['hu_low']} to {plan['hu_high']} HU, air at or below {plan['air_clamp_hu']} HU "
               f"set to {plan['hu_low']}, {plan['ray_samples']} samples a ray, {recipe['render_pixels']} pixels at "
               f"{recipe['render_spacing_mm']} mm, SDD {recipe['render_sdd_mm']} mm; edit: {recipe['model']}, "
               f"{recipe['steps']} steps, guidance {recipe['guidance']}, {recipe['dtype']}, pixels zeroed where the render "
               f"is below {recipe['foreground_floor']}; compared: zero-padded to a square, resized by Pillow's bilinear filter "
               f"to {plan['canvas']}, windowed to its own {plan['percentile_low']} and {plan['percentile_high']} percentiles "
               "(RECORD.json plan and recipe; PREREG.md section 3)")


@frozen
@reads("edit", "split")
def fact_subsets(run):
    """CLAIM 10: how the subjects and their samples were drawn."""
    plan, split = plan_of(run), run["split"]
    return met(f"{split['all']} of {split['from']} eligible subjects drawn by schwingnet.realism.draw with the seed "
               f"{split['seed']} ({edit_file(run, 'split/split.json')}), and {plan['poses_per_subject']} of each subject's samples "
               f"on the paper's pose grid by the same seed, each edit in {plan['arms']} seed arms; worked in shards of "
               f"{plan['shard_subjects']} subjects, which changes no number (RECORD.json plan; PREREG.md section 2)")


@frozen
@reads("edit", "inputs")
def fact_missing_data(run):
    """CLAIM 12, REFORMS 3f: nothing imputed; what could not be read is left out, counted."""
    c, plan = counts(run), plan_of(run)
    return met(f"no value is imputed: {c['not_in_db']} samples samples.csv names are not in the ThunderDB and {c['off_grid']} "
               f"are off the paper's pose grid, each left out before the draw; a subject without {plan['poses_per_subject']} such "
               "samples, a landed CT "
               f"and a landed vertebra truth file is not eligible, {c['eligible_subjects']} eligible (RECORD.json counts; "
               f"PREREG.md section 2, and {AFTER_FREEZE}, entry 3, which asks for {plan['poses_per_subject']} where section 2 asked for one)")


@frozen
@reads("edit")
def fact_partitions(run):
    """CLAIM 19, REFORMS 5c: no training partition; what each comparison sets against what."""
    return met("no partition for training: the sets compared are the kept edits, the raw renders and FluXray's images of the "
               "same drawn samples, each image's set known by construction; the nulls deal FluXray's images into two halves "
               "by subject and set the two seed arms against each other (PREREG.md section 3); the 70/30 split by subject "
               "that tools/realism.py split writes is for a later adapter and changes nothing here (PREREG.md section 6)")


@reads("stats kept", "stats raw")
def fact_disjoint(run):
    """CLAIM 20, REFORMS 6b: how the tests keep a subject's and a sample's images together."""
    rules, strata = run["stats"]["kept"]["rules"], strata_line(run)
    if strata is None:
        return missing(NO_STRATA)
    return met(f"the classifier's neighbours: {rules['neighbours']}; the AUC's interval: {rules['auc_interval']}; the "
               f"permutations: {rules['permutation']}; the strata each test recorded, {strata} (kept/stats.json, raw/stats.json)")


@frozen
@reads("edit")
def fact_intended_sample_size(run):
    """CLAIM 21: the sample the design fixed, and that it is not a powered size."""
    plan = plan_of(run)
    return met(f"{plan['subjects']} subjects, {plan['poses_per_subject']} samples each, {plan['arms']} seed arms (RECORD.json "
               "plan), fixed in PREREG.md's frozen block before the run (sections 2 and 7); not a powered size, and no file of "
               f"the study records a power calculation (section 4; {FROM_PAPER}, entries 3 and 5)")


@frozen
@reads("edit", "inputs")
def fact_instruments(run):
    """CLAIM 22: the released models the study uses, none trained."""
    recipe, i = recipe_of(run), run["inputs"]
    return met(f"no model is trained; used as released: {i['model']} for the edit ({recipe['steps']} steps, guidance "
               f"{recipe['guidance']}), FleXray's member flux000 for the paired filter and the flexray space, ResNet-18's 512 "
               "pooled features for the imagenet space, and handcrafted physics features (inputs.json, RECORD.json recipe; "
               "PREREG.md sections 2 and 3)")


def environment_said(stage):
    """One job's packages as its own environment file measured them, the GPU left to the compute item."""
    env = stage["environment"]
    found = ", ".join(f"{name} {version}" for name, version in sorted(env["environment"].items()) if name != "gpu")
    return (f"the {stage['name']} job, as {stage['environment_file']} measured them at its start: {found}; pins that differ: "
            f"{'; '.join(env.get('pins_differ') or []) or 'none'}")


@reads("edit", "inputs", "environment")
def fact_software(run):
    """CLAIM 23, job by job: the packages each job's own start measured."""
    gaps = [resumed_elsewhere(stage) for stage in stages(run)]
    if any(gaps):
        return missing("; ".join(gap for gap in gaps if gap))
    return met("; ".join(environment_said(stage) for stage in stages(run)))


@reads("edit", "inputs", "environment")
def fact_initialization(run):
    """CLAIM 24: no parameter is trained; every model is its released weights, named by sha256."""
    i, file = run["inputs"], edit_file(run, "inputs.json")
    said = (f"no parameter is trained or changed: every model is its released weights, named by its files' sha256; the edit "
            f"job ({file}): klein {i['klein_sha256'][:16]}, FleXray's bundle {i['bundle_sha256'][:16]} for the paired filter")
    if not is_stats(run):
        return met(f"{said}; the statistics' weights are hashed by the stats job's own start")
    e = run["environment"]
    same = "the same bundle the edit's filter read" if e["bundle_sha256"] == i["bundle_sha256"] else "other bundle bytes than the edit's filter read"
    return met(f"{said}; the stats job (environment.json): FleXray's bundle {e['bundle_sha256'][:16]} for the flexray space, {same}, "
               f"and ResNet-18 {e['imagenet_sha256'][:16]} for the imagenet space")


@frozen
@reads("stats kept", "stats raw")
def fact_metrics(run):
    """CLAIM 28, REFORMS 7a: every measure, with the components each space was read on."""
    k = components_line(run)
    if k is None:
        return missing(NO_COMPONENTS)
    spaces = ", ".join(run["stats"]["kept"]["spaces"])
    return met(f"in each of {spaces}: the nearest-neighbour two-sample classifier's AUC, the MMD with its p and its "
               "Benjamini-Hochberg q, and FD and KID (stored under the keys frechet64 and kid64), the MMD, FD and KID on the "
               f"space's first k principal components, {k} (PREREG.md section 3, and {AFTER_FREEZE}, entry 2, which makes k the "
               "smaller of 64 and the space's dimension); paired PSNR, SSIM and the phase-correlation shift where a sample is "
               "in both sets; the word of schwingnet.realism.verdict per space (kept/stats.json, raw/stats.json)")


@reads("stats kept")
def fact_uncertainty(run):
    """CLAIM 29, REFORMS 7b: the interval, the p and the multiplicity, as the run's rules say."""
    stats = run["stats"]["kept"]
    rules = stats["rules"]
    return met(f"AUC interval: {rules['auc_interval']}; p: {rules['permutation']}; {rules['multiplicity']}; seed "
               f"{stats['seed']} (kept/stats.json)")


@reads("stats kept")
def fact_internal_evaluation(run):
    """CLAIM 32: the nulls every comparison is read against."""
    lines = []
    for space, entry in run["stats"]["kept"]["spaces"].items():
        null, arm = entry.get("b_split_half") or {}, entry.get("arm_null") or {}
        half = (null.get("c2st") or {}).get("auc")
        arms = (arm.get("c2st") or {}).get("auc")
        lines.append(f"{space}: FluXray split-half AUC {half}, arm null AUC {arms}, a null separable: {entry.get('nulls_separable')}")
    return met("; ".join(lines) + " (kept/stats.json)") if lines else missing("needs the spaces of kept/stats.json")


@frozen
@reads("edit", "filter")
def fact_exclusions(run):
    """CLAIM 35, REFORMS 4a: what was left out and why, counted."""
    c, f = counts(run), run["filter"]
    return met(f"{c['off_grid']} FluXray samples off the pose grid and {c['not_in_db']} not in its ThunderDB left out; "
               f"{c['eligible_subjects']} subjects eligible, {c['drawn_subjects']} drawn (RECORD.json counts); of "
               f"{f['kept'] + f['dropped']} edits the paired filter dropped {f['dropped']} ({dropped_share(f)} percent, the "
               f"paper about 4 percent, PREREG.md section 3; {edit_file(run, 'filter/')})")


@reads("edit")
def fact_corrupt(run):
    """REFORMS 4b: whether every drawn sample was made, by the PREREG's draw and by the record's own."""
    c, plan, short = counts(run), plan_of(run), run["edit"].get("short")
    if short is None:
        return missing(f"needs short, what the edit made short of its own draw, in {edit_file(run, 'RECORD.json')}, which "
                       "flows/realism.py's end writes")
    expected = plan["subjects"] * plan["poses_per_subject"]
    wanted = {"renders": expected, "edits": expected * plan["arms"], "fluxray_exported": expected}
    gaps = [f"{name} {c.get(name)} of {want}" for name, want in wanted.items() if c.get(name) != want]
    gaps += [f"short of the draw: {', '.join(short)}"] if short else []
    if gaps:
        return missing("; ".join(gaps) + ": the run did not make every drawn sample (RECORD.json counts and short)")
    return met(f"none: every drawn sample was rendered and edited, renders {c['renders']} of {expected}, edits {c['edits']} of "
               f"{expected * plan['arms']}, and FluXray's image of each exported ({c['fluxray_exported']}); short of the draw: "
               "nothing (RECORD.json counts and short)")


@reads("stats kept", "stats raw")
def fact_endpoints(run):
    """CLAIM 37: every number of the two comparisons, each MMD with the components it was read on."""
    if components_line(run) is None:
        return missing(NO_COMPONENTS)
    record = run["record"]
    parts = [f"replication: {record['replication']}; geometry: {record['geometry']} (raw median shift "
             f"{(record.get('shifts') or {}).get('raw')} px)"]
    for comparison in COMPARISONS:
        for space, entry in run["stats"][comparison]["spaces"].items():
            c, m = entry["a_vs_b"]["c2st"], entry["a_vs_b"]["mmd"]
            parts.append(f"{comparison} {space}: AUC {c['auc']:.3f} [{c['low']:.3f}, {c['high']:.3f}], MMD q {m.get('q', m['p'])} on "
                         f"{entry['a_vs_b']['components']} components, {entry.get('verdict')}")
    return met("; ".join(parts) + " (RECORD.json, kept/stats.json, raw/stats.json)")


@frozen
@reads("edit")
def fact_protocol(run):
    """CLAIM 42: the full protocol, by the digest the record names."""
    record = run["record"]
    return met(f"the full protocol is the pre-registration {record['prereg']}, sha256 {str(record['prereg_sha256'])[:16]} as "
               "this record names it, frozen on 2026-10-29 before any image was rendered or any number read (its section 7), "
               "with DEVIATIONS.md beside it recording every departure, from the paper's recipe and from PREREG.md after its "
               "freeze, and README.md section 9 how the stages run; the flow's start refused to run under any other bytes or "
               "under a frozen block other than schwingnet.realism.frozen_lines() (RECORD.json prereg, prereg_sha256 and frozen)")


@reads("edit")
def fact_code_state(run):
    """REFORMS 2b, job by job: the commit each job began on and the one it ended on, each from a
    clean tree, and the run that started its folder and the run that ended it. A dirty tree, or a
    commit not read, leaves the commit unable to say which code ran; a resume may end on a later
    commit than its start, which the run key, a digest of the code the stage runs, holds to the same
    code."""
    problems, parts = [], []
    for stage in stages(run):
        record, file = stage["record"], stage["record_file"]
        where, ended = record.get("where") or {}, record.get("ended_in")
        if not ended:
            problems.append(f"{file} names no ended_in, the run that ended the folder, which flows/realism.py's end writes")
            continue
        unsure = [f"{side} on {code_said(place)}" for side, place in (("began", where), ("ended", ended))
                  if not place.get("commit") or place.get("clean_tree") is not True]
        if unsure:
            problems.append(f"the {stage['name']} job ({file}) {' and '.join(unsure)}")
            continue
        if where["commit"] != ended["commit"] and not resumed(where, ended):
            # Only a resume is held to the same code by its run key, which the launcher reads anew;
            # one run whose checkout moved under it may have run the newer code in its later steps.
            problems.append(f"the {stage['name']} job ({file}) began on commit {str(where['commit'])[:7]} and ended on commit "
                            f"{str(ended['commit'])[:7]} in the same run {said(where.get('run'))}, the checkout moved under it")
            continue
        commits = f"commit {str(where['commit'])[:7]} from a clean tree" if where["commit"] == ended["commit"] else \
            f"commit {str(where['commit'])[:7]}, resumed to its end on commit {str(ended['commit'])[:7]} of the same run key, each from a clean tree"
        parts.append(f"{stage['name']}: {commits}, key {record.get('key')}, {runs_said(record)} ({file})")
    if problems:
        return missing("; ".join(problems) + ", so the commit does not say which code ran")
    return met("; ".join(parts))


@reads("edit", "inputs", "environment")
def fact_compute(run):
    """REFORMS 2c, job by job: where each job began and ended, and the GPU and CUDA its own start
    measured. A stage resumed in another job measured no GPU of that job, so its card is not known
    and the item is missing, naming both jobs."""
    unknown, parts = [], []
    for stage in stages(run):
        record = stage["record"]
        where, ended = record.get("where") or {}, record.get("ended_in") or {}
        env = stage["environment"]["environment"]
        gpu = f"GPU {env['gpu']}, CUDA {env['cuda']} ({stage['environment_file']}, measured at its start)"
        gap = resumed_elsewhere(stage)
        if gap:
            unknown.append(f"{gap}; the first job's {gpu}")
            continue
        parts.append(f"{stage['name']}: run {said(where.get('run'))} in {job_said(where)}, begun {said(record.get('started'))} UTC and ended "
                     f"in the same job at {said(ended.get('ended'))} UTC; {gpu}")
    if unknown:
        return missing("; ".join(unknown))
    return met("; ".join(parts) + " (" + ", ".join(stage["record_file"] for stage in stages(run)) + ")")


@frozen
def fact_reproduce(run):
    """REFORMS 2d, 2e: where the instructions are and what runs the stages."""
    return met("docs/research/flux-realism/README.md sections 6 and 9, and flows/README.md: the gate's word `realism edit`, then "
               "`realism stats`, each one GPU job of grid/realism.sbatch, which runs `flows/launch.py realism --max-workers 1 -- "
               "--stage <stage> ...`, the launcher resuming a run cut short")


@reads("stats kept", "stats raw")
def fact_sources_per_set(run):
    """REFORMS 3a: how many images of how many subjects each set of each comparison holds."""
    parts = [f"{comparison}: " + ", ".join(f"{name} {s['n']} images of {s['subjects']} subjects"
                                           for name, s in run["stats"][comparison]["sets"].items())
             for comparison in COMPARISONS]
    return met("; ".join(parts) + "; set a is the kept edits or the raw renders, set b FluXray's images of the drawn samples "
               "(kept/stats.json, raw/stats.json)")


@reads("stats kept")
def fact_outcome(run):
    """REFORMS 3d: the label the tests separate."""
    sets = run["stats"]["kept"]["sets"]
    return met(f"the label the two-sample tests separate is which set an image is from: a, the kept edits ({sets['a']['n']} "
               f"images), and b, FluXray ({sets['b']['n']} images) (kept/stats.json)")


@reads("stats kept", "stats raw")
def fact_sample_size(run):
    """REFORMS 3e: each comparison's sets."""
    return met("; ".join(f"{comparison}: " + ", ".join(f"{name} {s['n']} images of {s['subjects']} subjects"
                                                       for name, s in run["stats"][comparison]["sets"].items())
                         for comparison in COMPARISONS) + " (kept/stats.json, raw/stats.json)")


# --- the answers that restate the frozen design, each with the section it restates ------------------------------------

@frozen
def fact_training(run):
    return not_applicable(NO_TRAINING)


@frozen
def fact_models_trained(run):
    return not_applicable(NO_TRAINING)


@frozen
def fact_no_model_selection(run):
    return not_applicable("not applicable: no model is chosen; the edit model is the one the paper names, klein-9B, and the "
                          "run refuses where it has not landed (PREREG.md section 2)")


@frozen
def fact_ensembling(run):
    return not_applicable("not applicable: no ensemble; FleXray's flux000 member is used alone, as the filter's stand-in "
                          f"(PREREG.md section 2; {FROM_PAPER}, entry 1)")


@frozen
def fact_no_external_model(run):
    return not_applicable("not applicable: no model is trained, so none is tested on external data; FluXray is the set the "
                          "edits are compared with, not a test of a model (PREREG.md section 6)")


@frozen
def fact_no_diagnosis(run):
    return not_applicable("not applicable: no diagnosis is estimated; the study tests whether two image sets can be told apart "
                          "(PREREG.md section 1)")


@frozen
def fact_aims(run):
    """CLAIM 4: the question and the hypotheses, as the pre-registration fixed them."""
    return met("the question, PREREG.md section 1: when this project renders FluXray's own CTs at FluXray's own recorded poses "
               "and edits each render zero-shot with FLUX.2 klein-9B by the paper's recipe and filter, are the kept edits "
               "indistinguishable from FluXray's released images of the same CT and pose; the hypotheses and their bars, its "
               "section 4: the kept edits are separable from FluXray in no space of three, each space worded by "
               "schwingnet.realism.verdict over its AUC interval and its MMD q (separable where the AUC's lower bound is above "
               "0.6; matched where the q is at least 0.05 and the upper bound no higher than the larger of 0.5 and FluXray's "
               "split-half upper bound; indistinguishable where the q is at least 0.05 and the lower bound at most 0.6; "
               "undecided where the tests disagree); the raw renders are separable in at least one space, the positive "
               "control; the replication's one word follows from the two; and the geometry holds where the raw renders' "
               "median phase-correlation shift from FluXray is at most 1 pixel at 256")


@frozen
def fact_study_design(run):
    """CLAIM 5: retrospective, on public sets, under a design frozen first."""
    return met("retrospective: the CTs and their truth (ENHANCE.PET 1.6k) and FluXray's images are public sets made before "
               "the study (PREREG.md section 2), the renders and edits are made in the run from those CTs at FluXray's recorded "
               "poses, and no image is acquired from a person for the study; the design was frozen on 2026-10-29 before any "
               "image was rendered or edited and before any number of the study was read (PREREG.md, opening and section 7)")


@frozen
def fact_study_goal(run):
    """CLAIM 6: a replication under pre-registered hypotheses, not a model."""
    return met("a replication under pre-registered hypotheses: whether the FleXray paper's zero-shot edit, as read here, "
               "reproduces FluXray from the CTs it was made from (PREREG.md sections 1 and 4); the primary is the replication "
               "word and the kept edits' table, every other number description (its section 6); no network is trained and no "
               "model is built for use")


@frozen
@reads("edit")
def fact_inclusion_exclusion(run):
    """CLAIM 8: who is in and who is out, as the design says and the record counts."""
    c, plan = counts(run), plan_of(run)
    return met(f"in: a FluXray subject with {plan['poses_per_subject']} samples in the ThunderDB at a pose on the paper's "
               f"90-pose grid, a landed CT and a landed vertebra truth file (PREREG.md section 2, where one such sample "
               f"sufficed, and {AFTER_FREEZE}, entry 3, which asks for {plan['poses_per_subject']}); out, each counted: samples off "
               f"the grid or off axis ({c['off_grid']}), samples samples.csv names that the ThunderDB lacks ({c['not_in_db']}), "
               f"and subjects without those samples or with no landed CT or truth; fewer than {plan['subjects']} eligible "
               f"subjects refuses the run before any GPU work; this run: {c['eligible_subjects']} subjects eligible, "
               f"{c['drawn_subjects']} drawn (RECORD.json counts)")


@frozen
@reads("edit")
def fact_acquisition(run):
    """CLAIM 13: how each set's images came to be."""
    plan, recipe = plan_of(run), recipe_of(run)
    return met("no image is acquired from a person: the renders are made in the run by fxr.drr.render_drr at each sample's "
               f"recorded pose, SDD {recipe['render_sdd_mm']} mm, {recipe['render_spacing_mm']} mm pixels, "
               f"{recipe['render_pixels']} pixels, the isocentre at the volume's centre ({recipe['isocentre']}), "
               f"{plan['ray_samples']} samples a ray, and the edits by {recipe['model']}, {recipe['steps']} steps, guidance "
               f"{recipe['guidance']}, {recipe['dtype']} (RECORD.json recipe and plan; PREREG.md section 3); FluXray's images "
               "were made by the paper's authors by its appendix's recipe and stored at 256 (PREREG.md section 2); the CTs' "
               "own acquisition is ENHANCE.PET's, which no file of the study records")


@frozen
def fact_no_reference_standard(run):
    """CLAIM 14, 15: the label is the set, known by construction."""
    return not_applicable("not applicable: the study scores no case against a reference standard; the one label its "
                          "two-sample tests read is which set an image is from, the kept edits, the raw renders or FluXray, "
                          "known for every image by construction (PREREG.md section 3); the only truth any step reads is the "
                          "paired filter's, each CT's released MOOSE labels projected as exact masks at the sample's pose, a "
                          "step of the paper's recipe and never a standard a result is scored against")


@frozen
def fact_no_annotation(run):
    """CLAIM 16, 17: nothing is annotated."""
    return not_applicable("not applicable: the study annotates no image, in its test sets or anywhere; the label every test "
                          "reads is the set an image is from, and the filter's masks are ENHANCE.PET's released MOOSE labels "
                          "(the fetch row aws_enhance_pet_labels), packed into FleXray's MOOSE profile by "
                          "grid/enhance-pet-labels.json and projected at each pose (PREREG.md sections 2 and 3), never drawn by "
                          "a person")


@frozen
def fact_no_raters(run):
    """CLAIM 18: no rater reads an image."""
    return not_applicable("not applicable: the study has no rater, so no inter- or intrarater variability; no person reads "
                          "an image, and every word is computed from the numbers by schwingnet.realism and printed by the "
                          "report, so no reader chooses it (PREREG.md section 6, Blind)")


@frozen
@reads("edit")
def fact_robustness(run):
    """CLAIM 30: every comparison read several ways, by design."""
    return met("no finding rests on one view (PREREG.md sections 3 and 4): every comparison is read in three feature spaces, "
               "physics, flexray and imagenet, by a classifier test and a kernel test beside FD and KID; the edits come in "
               f"{plan_of(run)['arms']} seed arms (RECORD.json plan), each read alone with its own q, and a space whose arms "
               "give different words is undecided, as is one whose split-half or arm null is separable; the raw renders are a "
               "positive control; and the kept edits' word is the worst over the spaces")


@frozen
@reads("edit")
def fact_explainability(run):
    """CLAIM 31: what the study shows of how the sets differ."""
    plan = plan_of(run)
    return met("no per-image explanation, saliency or attribution map is made; what the study shows of how the sets differ is "
               f"description (PREREG.md sections 3 and 6): the physics space's named features, a {plan['physics_bins']}-bin "
               f"intensity histogram, a {plan['radial_bands']}-band radial power spectrum, gradient statistics, noise and "
               "local contrast (RECORD.json plan); the flexray space's channel probabilities and areas; the paired PSNR, global "
               "SSIM and phase-correlation shift where a sample is in both sets; the filter's dropped share against the paper's; "
               f"and each lumbar body's superior endplate angle at 1024 and at 256 ({edit_file(run, 'measure/measure.md')}, "
               "tools/realism.py measure)")


@frozen
def fact_no_trial(run):
    """CLAIM 34: no clinical trial; the design is registered in the project."""
    return not_applicable(f"not applicable: the study is no clinical trial and is in no trial registry; its design is "
                          f"registered inside the project as {run['record'].get('prereg')}, sha256 {DESIGN[:16]}, frozen on "
                          "2026-10-29 before any image was rendered or edited and before any number was read (its section 7), "
                          "the pre-registration this record names")


@frozen
@reads("edit")
def fact_characteristics(run):
    """CLAIM 36: no demographic or clinical field is read; how many images of how many subjects."""
    c = counts(run)
    sets = [f"{comparison}/stats.json " + ", ".join(f"{name} {s.get('n')} images of {s.get('subjects')} subjects"
                                                    for name, s in ((run["stats"][comparison] or {}).get("sets") or {}).items())
            for comparison in COMPARISONS if run["stats"].get(comparison)]
    return not_applicable("not applicable: the study reads and records no demographic or clinical characteristic of any "
                          "subject or image, and the population it names is FluXray's samples and ENHANCE.PET's CTs as images "
                          "(PREREG.md section 2); what it records of each set is how many images of how many subjects: "
                          f"{c['drawn_subjects']} subjects drawn, {c['renders']} renders, {c['edits']} edits, {c['kept']} kept "
                          "(RECORD.json counts)" + "".join(f"; {line}" for line in sets))


@frozen
@reads("stats kept", "stats raw")
def fact_failure_analysis(run):
    """CLAIM 39: no case is classified against a truth; the failures the design defines."""
    record = run["record"]
    separable = [f"{comparison} {space}" for comparison in COMPARISONS
                 for space, entry in run["stats"][comparison]["spaces"].items() if entry.get("nulls_separable")]
    return not_applicable("not applicable: no case is classified against a truth, so no case is incorrectly classified; the "
                          "failures the design defines are PREREG.md section 5's, of the replication (the word not reproduced), "
                          "of the test (untestable), of the pipeline (a separable null, whose space is then undecided and its "
                          "numbers not read) and of the geometry (a median shift above 1 pixel); this run: replication "
                          f"{record['replication']}, geometry {record['geometry']}, a separable null in "
                          f"{', '.join(separable) or 'no space'} (RECORD.json, kept/stats.json, raw/stats.json)")


@frozen
@reads("edit", "filter")
def fact_limitations(run):
    """CLAIM 40: the limits listed before the run, and this run's own."""
    f, short = run["filter"], run["edit"].get("short") or []
    return met("the limits listed before the run are PREREG.md section 6's: the paper's filter used a U-Net trained on raw DRRs "
               "alone, which was not released, and flux000 stands in; the paper gives no seeds; the filter's pose groups hold "
               "about 9 edits here against about 1,534 in FluXray, so its q0.98 cut-off is noisier; FluXray's images were stored "
               "at 256, so every comparison is at 256 although the edit runs at 1024; and 100 subjects is not a powered size "
               "(section 4); every departure from the paper is under DEVIATIONS.md's first heading and every departure from "
               "PREREG.md after its freeze under its second, dated with its reason; of this run: the filter dropped "
               f"{f['dropped']} of {f['kept'] + f['dropped']} edits ({dropped_share(f)} percent, the paper about 4 percent; "
               f"{edit_file(run, 'filter/')})" + (f"; short of the draw: {', '.join(short)} (RECORD.json short)" if short else ""))


@frozen
@reads("edit")
def fact_population(run):
    """REFORMS 1a: what the claim is about."""
    c, plan = counts(run), plan_of(run)
    return met("the claim is about FluXray, the FleXray paper's enhanced DRRs, and this project's renders and edits of the "
               f"same CTs at the same poses: {c['drawn_subjects']} subjects drawn of {c['eligible_subjects']} eligible, "
               f"{plan['poses_per_subject']} samples each, {c['renders']} renders and {c['edits']} edits in {plan['arms']} seed "
               "arms (RECORD.json counts and plan; PREREG.md section 2); a claim about a published recipe and its dataset, not "
               "about patients")


@frozen
def fact_population_rationale(run):
    """REFORMS 1b: why FluXray and its own CTs."""
    return met("FluXray is what the paper's recipe made from these CTs (PREREG.md section 2), so rendering the same CTs at "
               "FluXray's own recorded poses pairs every comparison by sample and leaves the edit as the one thing the kept "
               "edits and FluXray can differ by, with the raw renders as the control that shows the edit is what FluXray adds "
               "(sections 1 and 4); 100 subjects of 4 samples is the plan's figure of 2026-10-26, not a powered size (section "
               f"4; {FROM_PAPER}, entry 3)")


@frozen
def fact_ml_rationale(run):
    """REFORMS 1c: why a classifier, beside tests that learn nothing."""
    return met("the question is whether two sets of images can be told apart, which no single measure answers (README.md "
               "section 4, the owner's 'numerically indistinguishable' made a pre-registered test): a classifier two-sample "
               "test, a nearest-neighbour score with an AUC and its interval, learns to tell the sets apart, beside an MMD "
               "kernel test and FD and KID, which learn nothing (PREREG.md section 3); the edit is the paper's own diffusion "
               "model, FLUX.2 klein-9B, run zero-shot as released (section 2), and no network is trained")


@frozen
@reads("edit")
def fact_sampling_frame(run):
    """REFORMS 3b: what the subjects and samples were drawn from."""
    c, plan = counts(run), plan_of(run)
    return met(f"FluXray's samples.csv ({c['fluxray_samples']} rows, RECORD.json counts) read through its ThunderDB, each "
               f"sample's subject and pose; a subject is in the frame where {plan['poses_per_subject']} of its samples are in "
               "the ThunderDB at a pose on the paper's grid and its CT and vertebra truth landed (PREREG.md section 2, and "
               f"{AFTER_FREEZE}, entry 3), {c['eligible_subjects']} here; from it {plan['subjects']} subjects and "
               f"{plan['poses_per_subject']} samples each are drawn by schwingnet.realism.draw with the seed {plan['draw_seed']} "
               "(RECORD.json plan)")


@frozen
def fact_fitness_rationale(run):
    """REFORMS 3c: why the sets fit the question, and what limits the fit."""
    return met("FluXray is the paper's own output of the recipe on ENHANCE.PET's CTs (PREREG.md section 2), so the same CTs "
               "rendered at the same recorded poses differ from FluXray's images by the edit alone where the geometry holds, "
               "which the raw renders' phase-correlation shift checks (sections 3 and 4); what limits the fit was listed "
               "before the run (section 6): the stand-in filter, the unknown seeds, the noisier cut-off of small pose groups "
               "and the comparison at 256")


@frozen
@reads("edit")
def fact_representativeness(run):
    """REFORMS 3g: how the subjects were drawn, and what they stand for."""
    c = counts(run)
    return met("the drawn subjects are a seeded draw of FluXray's eligible subjects, a rank by sha256 that no other subject's "
               "presence moves, and each subject's samples a draw by the same seed (PREREG.md section 2), chosen by no reader: "
               f"{c['drawn_subjects']} of {c['eligible_subjects']} (RECORD.json counts); they stand for FluXray's eligible "
               "subjects and the paper's pose grid, not for a clinical population, and the comparison is at FleXray's canvas of "
               "256 though the edit runs at 1024 (section 6)")


@frozen
def fact_model_rationale(run):
    """REFORMS 5b: why these tests, spaces and models."""
    return met("PREREG.md section 3 sets the tests and README.md section 4 their reasons: the classifier test scores each image "
               "by its 5 nearest neighbours with every image of its own subject left out, so a CT's own views never make two "
               "sets look alike (PREREG.md section 6, Held out); the MMD is a kernel test with a permutation p read at its "
               "Benjamini-Hochberg q over the three spaces, as the DRR domain-gap study reads it; FD and KID are distances on "
               f"the same principal components, the smaller of 64 and the space's dimension ({AFTER_FREEZE}, entry 2); three spaces, "
               "so no finding rests on one encoder's view; the edit model is the one the paper names, klein-9B, and no other "
               f"stands in (PREREG.md section 2); and flux000 stands in for the paper's unreleased raw-only U-Net in the filter "
               f"({FROM_PAPER}, entry 1)")


@frozen
@reads("edit")
def fact_no_tuning(run):
    """REFORMS 5e: nothing is tuned."""
    plan, recipe = plan_of(run), recipe_of(run)
    return not_applicable("not applicable: no hyperparameter is tuned; every setting was fixed in PREREG.md's frozen block "
                          f"before any number (section 7), and the record holds them as run: {plan['knn']} neighbours, "
                          f"{plan['bootstraps']} bootstrap draws, {plan['permutations']} permutations, at most "
                          f"{plan['pca_components']} principal components ({AFTER_FREEZE}, entry 2), KID over {plan['kid_repeats']} "
                          f"subsets of {plan['kid_subset']}, the draw seed {plan['draw_seed']} and the statistics' seed "
                          f"{plan['stats_seed']}, and the edit's {recipe['steps']} steps and guidance {recipe['guidance']}, the "
                          "paper's (RECORD.json plan and recipe)")


@frozen
@reads("edit")
def fact_baselines(run):
    """REFORMS 5f: the positive control and the nulls."""
    plan = plan_of(run)
    raw = f"; raw/stats.json: {stats_words(run, 'raw')}" if run["stats"].get("raw") else ""
    return met(f"the raw renders of the same {plan['subjects'] * plan['poses_per_subject']} samples against the same FluXray "
               "images, the positive control, which must be separable in at least one space for the test to say anything "
               "(PREREG.md section 4), and the nulls, FluXray's split halves and arm 0 against arm 1, where every test must find "
               "nothing (section 3); a matched word is read against FluXray's split-half upper bound" + raw)


@frozen
@reads("edit")
def fact_preprocessing_fit(run):
    """REFORMS 6a: what is fit on which rows."""
    plan = plan_of(run)
    k = components_line(run) if run["stats"].get("kept") and run["stats"].get("raw") else None
    return met(f"each image is windowed to its own {plan['percentile_low']} and {plan['percentile_high']} percentiles; in "
               "each space the two sets' features are standardised together and the principal components the MMD, FD and KID "
               "read are fit on both sets pooled without their labels, so they are the same under every permutation of the "
               f"labels (PREREG.md section 3, and {AFTER_FREEZE}, entry 2, for how many; tools/realism.py compare); the classifier "
               "test's nearest-neighbour score fits nothing; the paired filter's cut-off is fit within each pose group on the "
               "edits' own soft Dice against the exact masks, before any comparison with FluXray (PREREG.md section 3)"
               + (f"; {k} (kept/stats.json, raw/stats.json)" if k else ""))


@frozen
def fact_feature_legitimacy(run):
    """REFORMS 6c: what keeps a set's files from telling it apart."""
    return met("every feature is computed from one image's pixels alone (PREREG.md section 3), and every set is brought to "
               "FleXray's canvas alike before it, zero-padded to a square, resized to 256 by Pillow's bilinear filter and "
               "windowed to its own percentiles, so its size, its border and its range do not mark a set; the edited pixels "
               "are zeroed where the raw render is below 0.05, as the paper's were (section 3); what still marks FluXray "
               "besides the edit was listed before the run (section 6): its images were stored at 256, while the edits are "
               "brought to 256 from 1024")


@frozen
@reads("stats kept", "stats raw")
def fact_statistical_tests(run):
    """REFORMS 7c: the tests, what each assumes, and the strata each recorded."""
    strata = strata_line(run)
    if strata is None:
        return missing(NO_STRATA)
    return met("the classifier test's and the MMD's permutation p each hold under the null that images are exchangeable within "
               "the strata the shuffle keeps: where two sets hold the same samples, each sample's own images, a sample in one "
               "set keeping its label, and between FluXray's split halves, which share no subject, whole subjects "
               f"({AFTER_FREEZE}, entry 1, which replaces PREREG.md section 3's shuffle within each subject); the strata each "
               "test recorded, "
               f"{strata}; the AUC's interval is a {plan_of(run)['bootstraps']}-draw bootstrap over subjects; "
               "Benjamini-Hochberg over the three spaces controls the false-discovery rate where the p-values are independent "
               "or positively dependent, while the spaces read the same images and so are not independent (kept/stats.json, "
               "raw/stats.json)")


FACTS = {
    "sources": fact_sources, "transforms": fact_transforms, "subsets": fact_subsets, "missing_data": fact_missing_data,
    "partitions": fact_partitions, "disjoint": fact_disjoint, "intended_sample_size": fact_intended_sample_size,
    "instruments": fact_instruments, "software": fact_software, "initialization": fact_initialization,
    "training": fact_training, "no_model_selection": fact_no_model_selection, "ensembling": fact_ensembling,
    "metrics": fact_metrics, "uncertainty": fact_uncertainty, "internal_evaluation": fact_internal_evaluation,
    "exclusions": fact_exclusions, "corrupt": fact_corrupt, "endpoints": fact_endpoints, "no_external_model": fact_no_external_model,
    "no_diagnosis": fact_no_diagnosis, "protocol": fact_protocol, "code_state": fact_code_state, "compute": fact_compute,
    "reproduce": fact_reproduce, "sources_per_set": fact_sources_per_set, "outcome": fact_outcome, "sample_size": fact_sample_size,
    "models_trained": fact_models_trained, "aims": fact_aims, "study_design": fact_study_design, "study_goal": fact_study_goal,
    "inclusion_exclusion": fact_inclusion_exclusion, "acquisition": fact_acquisition,
    "no_reference_standard": fact_no_reference_standard, "no_annotation": fact_no_annotation, "no_raters": fact_no_raters,
    "robustness": fact_robustness, "explainability": fact_explainability, "no_trial": fact_no_trial,
    "characteristics": fact_characteristics, "failure_analysis": fact_failure_analysis, "limitations": fact_limitations,
    "population": fact_population, "population_rationale": fact_population_rationale, "ml_rationale": fact_ml_rationale,
    "sampling_frame": fact_sampling_frame, "fitness_rationale": fact_fitness_rationale,
    "representativeness": fact_representativeness, "model_rationale": fact_model_rationale, "no_tuning": fact_no_tuning,
    "baselines": fact_baselines, "preprocessing_fit": fact_preprocessing_fit, "feature_legitimacy": fact_feature_legitimacy,
    "statistical_tests": fact_statistical_tests,
}


# --- the page -----------------------------------------------------------------------------------------------------------

def licence_lines(run):
    """Each source as the register holds it, copied as written, or the plain word that it has none."""
    register = run["register"].get("sources") or {}
    lines = ["## Data and licences", "", "The study trains no network. Each source below is quoted from data/licences.json where it "
             "has an entry, and named as having none where it has not; no licence is worked out here (README section 8 says "
             "what the owner decides).", ""]
    for source, what in SOURCES.items():
        entry = register.get(source)
        lines.append(f"- {what}: " + (f"{entry.get('licence')}; class {entry.get('class')}" if entry else "no entry in data/licences.json"))
    return lines


def markdown(run, claim_rows, reforms_rows, checklist_section, answers_shown):
    record = run["record"]
    missing_rows = [f"CLAIM {r['id']}" for r in claim_rows if r["state"] == "missing"]
    missing_rows += [f"REFORMS {r['id']}" for r in reforms_rows if r["state"] == "missing"]
    lines = [
        f"# Report of study {STUDY}, {record.get('stage')} run {run['dir'].name}",
        "",
        f"Written by `python3 tools/report.py write --study {STUDY}` from this folder's RECORD.json and the files it names by their "
        f"sha256, and {answers_shown}; do not edit by hand. PREREG sha256 {str(record.get('prereg_sha256'))[:16]}. The jobs "
        "whose numbers this folder holds, each as its own record names it:",
        "",
        *job_lines(run),
        "",
        f"Complete: **{'yes' if not missing_rows else 'no'}**" + (f"; missing {len(missing_rows)}: {', '.join(missing_rows)}." if missing_rows else "."),
        "",
        f"A met item quotes the file that shows it, and an item that restates the frozen design holds only for a run whose "
        f"records name its sha256, {DESIGN[:16]}; a declared one is the owner's sentence in {answers_shown}, which the code "
        f"checks is there but cannot judge; a missing one is work to do before the numbers are published (`python3 "
        f"tools/report.py check --study {STUDY} --run <folder> --complete`).",
        "",
        *licence_lines(run),
        "",
        *checklist_section("CLAIM 2024", claim_rows),
        "",
        *checklist_section("REFORMS", reforms_rows),
    ]
    return "\n".join(lines) + "\n"
