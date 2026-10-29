"""The CLAIM 2024 and REFORMS report of a run of the FluXray reproduction, as tools/report.py's study
flux-realism.

    python3 tools/report.py write --study flux-realism --run <run folder>
    python3 tools/report.py check --study flux-realism --run <run folder> [--complete]

A run folder is what flows/realism.py's run kept, <realism root>/<stage>-<key>/ on the grid or a
copy of its small files under docs/research/flux-realism/runs/: RECORD.json, the record the flow's
end wrote, and the files it names, each by its sha256. A stats run holds the edit's small files
under edit/, copied when it began, so one folder answers the whole report; an edit run answers
what the edit made and leaves the statistics missing, saying they wait for the stats stage. A code
answer reads only those files, never infers, and is missing where a file is absent or no longer
the bytes the record names. The owner's answers come from data/reporting/studies/flux-realism.json,
which no session fills. The study trains no network: an item about a trained model is answered for
the released models it uses as they are, or is not applicable, with the reason quoted. Standard
library only, as tools/report.py is.
"""

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STUDY = "flux-realism"
COMPARISONS = ("kept", "raw")
PREREG = ROOT / "docs" / "research" / "flux-realism" / "PREREG.md"
LICENCES = ROOT / "data" / "licences.json"
# The register's entry for each source of the study, where it has one, by the fetch row's name.
SOURCES = {
    "hf_flexray_data": "FluXray, the folder FluXray/ of the Hugging Face dataset VictorButoi/flexray-data",
    "scidb_enhance_pet_1_6k": "ENHANCE.PET 1.6k, Science Data Bank doi:10.57760/sciencedb.34150, the bucket enhance-pet-1-6k",
    "hf_flux2_klein_9b": "FLUX.2 klein-9B, black-forest-labs/FLUX.2-klein-9B",
    "hf_flexray_weights": "FleXray's weights, VictorButoi/flexray, member flux000",
}
NO_TRAINING = "not applicable: the study trains no network; it edits with released weights and tests two sets apart (PREREG.md, section 6)"

# How the study answers each item the checklists give to code: ("code", fact) is read from the run
# folder by FACTS, ("declared", fact) is the owner's sentence in the study's answers file, as is
# every item listed in neither.
ITEMS = {
    "claim": {
        "7": ("code", "sources"), "9": ("code", "transforms"), "10": ("code", "subsets"), "12": ("code", "missing_data"),
        "19": ("code", "partitions"), "20": ("code", "disjoint"), "21": ("code", "intended_sample_size"),
        "22": ("code", "instruments"), "23": ("code", "software"), "24": ("code", "initialization"),
        "25": ("code", "training"), "26": ("code", "no_model_selection"), "27": ("code", "ensembling"),
        "28": ("code", "metrics"), "29": ("code", "uncertainty"), "32": ("code", "internal_evaluation"),
        "33": ("code", "no_external_model"), "35": ("code", "exclusions"), "36": ("declared", "characteristics"), "37": ("code", "endpoints"),
        "38": ("code", "no_diagnosis"), "39": ("declared", "failure_analysis"), "42": ("code", "protocol"),
    },
    "reforms": {
        "2a": ("code", "sources"), "2b": ("code", "code_state"), "2c": ("code", "compute"), "2d": ("code", "reproduce"),
        "2e": ("code", "reproduce"), "3a": ("code", "sources_per_set"), "3d": ("code", "outcome"),
        "3e": ("code", "sample_size"), "3f": ("code", "missing_data"), "4a": ("code", "exclusions"),
        "4b": ("code", "corrupt"), "4c": ("code", "transforms"), "5a": ("code", "models_trained"),
        "5c": ("code", "partitions"), "5d": ("code", "no_model_selection"), "6b": ("code", "disjoint"),
        "7a": ("code", "metrics"), "7b": ("code", "uncertainty"),
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


def checked(folder, record, name):
    """A file of the folder the record names, read only while its bytes are the ones it names:
    (path, None), or (None, why not)."""
    path = Path(folder) / name
    named = (record.get("files") or {}).get(name)
    if named is None:
        return None, f"{name} is not among the files the record names"
    found = sha256_of(path)
    if found is None:
        return None, f"{name} is not in the folder"
    if found != named:
        return None, f"{name} is not the file the record names (sha256 {found[:16]}, named {named[:16]})"
    return path, None


def load(name, run_dir):
    """A run folder's files as the facts read them; a folder with no RECORD.json of this study is
    not a run of it."""
    run_dir = Path(run_dir)
    record = read_json(run_dir / "RECORD.json")
    if not isinstance(record, dict) or record.get("study") != STUDY:
        raise RealismReportError(f"{run_dir}: no RECORD.json of the study {STUDY}, so this is not a run of it")
    edit_dir = run_dir if record.get("stage") == "edit" else run_dir / "edit"
    edit = record if edit_dir == run_dir else read_json(edit_dir / "RECORD.json")
    run = {"dir": run_dir, "name": name, "record": record, "edit": edit or {}, "edit_dir": edit_dir, "gaps": {},
           "register": read_json(LICENCES) or {}}
    if edit is None:
        run["gaps"]["edit"] = "edit/RECORD.json, the edit's record the stats run copied, is not in the folder"
    for key, folder, owner, file in (("inputs", edit_dir, run["edit"], "inputs.json"), ("split", edit_dir, run["edit"], "split/split.json")):
        path, why = checked(folder, owner, file)
        run[key] = read_json(path) if path else None
        run["gaps"][key] = why
    kept, why_kept = checked(edit_dir, run["edit"], "filter/filter_kept.csv")
    dropped, why_dropped = checked(edit_dir, run["edit"], "filter/filter_dropped.csv")
    run["filter"] = {"kept": len(rows_of(kept)), "dropped": len(rows_of(dropped))} if kept and dropped else None
    run["gaps"]["filter"] = why_kept or why_dropped
    run["stats"] = {}
    for comparison in COMPARISONS if record.get("stage") == "stats" else ():
        path, why = checked(run_dir, record, f"{comparison}/stats.json")
        run["stats"][comparison] = read_json(path) if path else None
        run["gaps"][f"stats {comparison}"] = why
    return run


# --- the facts: each reads the folder and gives a state and its evidence ---------------------------------------------

def met(evidence):
    return "met", evidence


def missing(why):
    return "missing", why


def not_applicable(reason):
    return "not applicable", reason


def needs(run, *keys):
    """Why the files these facts read cannot answer, or empty where every one was read."""
    gaps = [run["gaps"][key] for key in keys if run["gaps"].get(key)]
    if run["record"].get("stage") != "stats" and any(key.startswith("stats") for key in keys):
        return "needs the stats stage's run (`realism stats`), which reads this edit; this folder is the edit's"
    return "needs " + "; ".join(gaps) if gaps else ""


def reads(*keys):
    """A fact that reads these files: missing, naming what is absent, until each is read."""

    def wrap(fact):
        def answer(run):
            gap = needs(run, *keys)
            return missing(gap) if gap else fact(run)

        answer.__doc__ = fact.__doc__
        return answer

    return wrap


def counts(run):
    return run["edit"].get("counts") or {}


@reads("edit", "inputs")
def fact_sources(run):
    i = run["inputs"]
    return met(f"FluXray (VictorButoi/flexray-data, FluXray/): samples.csv sha256 {i['samples_sha256'][:16]}, {i['samples_rows']} rows, "
               f"its ThunderDB by its files' sha256 {i['db_sha256'][:16]}; ENHANCE.PET 1.6k (doi:10.57760/sciencedb.34150): the CT "
               f"and truth of each drawn subject by its sha256 in render/manifest.jsonl (sha256 "
               f"{str((run['edit'].get('files') or {}).get('render/manifest.jsonl'))[:16]}); {i['model']} by its files' sha256 "
               f"{i['klein_sha256'][:16]}; FleXray's bundle {i['bundle_sha256'][:16]}; ResNet-18 {i['imagenet_sha256'][:16]} (inputs.json)")


@reads("edit")
def fact_transforms(run):
    plan, recipe = run["edit"].get("plan") or {}, run["edit"].get("recipe") or {}
    return met(f"render: CT clamped to {plan.get('hu_low')} to {plan.get('hu_high')} HU, air at or below {plan.get('air_clamp_hu')} HU "
               f"set to {plan.get('hu_low')}, {plan.get('ray_samples')} samples a ray, {recipe.get('render_pixels')} pixels at "
               f"{recipe.get('render_spacing_mm')} mm, SDD {recipe.get('render_sdd_mm')} mm; edit: {recipe.get('model')}, "
               f"{recipe.get('steps')} steps, guidance {recipe.get('guidance')}, {recipe.get('dtype')}, pixels zeroed where the render "
               f"is below {recipe.get('foreground_floor')}; compared: zero-padded to a square, bilinear to {plan.get('canvas')}, "
               f"windowed to the {plan.get('percentile_low')} and {plan.get('percentile_high')} percentiles (RECORD.json plan and recipe)")


@reads("edit", "split")
def fact_subsets(run):
    plan, split = run["edit"].get("plan") or {}, run["split"]
    return met(f"{split['all']} of {split['from']} eligible subjects drawn by seed {split['seed']} (split/split.json), "
               f"{plan.get('poses_per_subject')} poses each by the same seed among the subject's FluXray samples, "
               f"each edit in {plan.get('arms')} seed arms; shards of {plan.get('shard_subjects')} subjects")


@reads("edit", "inputs")
def fact_missing_data(run):
    c = counts(run)
    return met(f"no value is imputed: {c.get('not_in_db')} samples samples.csv names are not in the ThunderDB and "
               f"{c.get('off_grid')} are off the paper's pose grid, each left out before the draw; subjects without a landed CT or "
               f"vertebra truth are not eligible ({c.get('eligible_subjects')} eligible); counted in RECORD.json")


@reads("edit")
def fact_partitions(run):
    return met("no partition for training: the sets compared are the kept edits, the raw renders and FluXray's images of the "
               "same drawn samples; the nulls split FluXray's images by subject and set the seed arms apart (PREREG.md, section 3)")


@reads("stats kept")
def fact_disjoint(run):
    rules = run["stats"]["kept"].get("rules") or {}
    if not rules:
        return missing("needs the rules block of kept/stats.json, which tools/realism.py stats writes")
    return met(f"by subject: neighbours, {rules['neighbours']}; permutations, {rules['permutation']} (kept/stats.json)")


@reads("edit")
def fact_intended_sample_size(run):
    plan = run["edit"].get("plan") or {}
    return met(f"{plan.get('subjects')} subjects, {plan.get('poses_per_subject')} poses each, {plan.get('arms')} seed arms, fixed in "
               "PREREG.md's frozen block before the run; not a powered size (DEVIATIONS.md, item 5)")


@reads("edit", "inputs")
def fact_instruments(run):
    recipe, i = run["edit"].get("recipe") or {}, run["inputs"]
    return met(f"no model is trained; used as released: {i['model']} for the edit ({recipe.get('steps')} steps, guidance "
               f"{recipe.get('guidance')}), FleXray's flux000 for the paired filter and the flexray space, ResNet-18's pooled "
               "features for the imagenet space, and handcrafted physics features (inputs.json, RECORD.json)")


@reads("inputs")
def fact_software(run):
    environment = run["inputs"].get("environment") or {}
    found = ", ".join(f"{name} {version}" for name, version in sorted(environment.items()) if name != "gpu")
    differ = run["inputs"].get("pins_differ") or []
    return met(f"{found}; pins that differ: {'; '.join(differ) or 'none'} (inputs.json)")


@reads("inputs")
def fact_initialization(run):
    i = run["inputs"]
    return met(f"no parameter is trained or changed: every model is its released weights, named by its files' sha256 "
               f"(klein {i['klein_sha256'][:16]}, FleXray {i['bundle_sha256'][:16]}, ResNet-18 {i['imagenet_sha256'][:16]})")


def fact_training(run):
    return not_applicable(NO_TRAINING)


def fact_no_model_selection(run):
    return not_applicable("not applicable: no model is chosen; the edit model is the one the paper names, klein-9B, and the "
                          "run refuses where it has not landed (PREREG.md, section 2)")


def fact_ensembling(run):
    return not_applicable("not applicable: no ensemble; FleXray's flux000 member is used alone, as the filter's stand-in")


@reads("stats kept", "stats raw")
def fact_metrics(run):
    spaces = ", ".join(run["stats"]["kept"].get("spaces") or {})
    return met(f"in each of {spaces}: the nearest-neighbour two-sample classifier's AUC, the MMD with its p and its "
               "Benjamini-Hochberg q, FD64 and KID64; paired PSNR, SSIM and the phase-correlation shift where a sample is in both "
               "sets; the word of schwingnet.realism.verdict per space (kept/stats.json, raw/stats.json)")


@reads("stats kept")
def fact_uncertainty(run):
    rules = run["stats"]["kept"].get("rules") or {}
    if not rules:
        return missing("needs the rules block of kept/stats.json, which tools/realism.py stats writes")
    return met(f"AUC interval: {rules['auc_interval']}; p: {rules['permutation']}; {rules['multiplicity']}; seed "
               f"{run['stats']['kept'].get('seed')} (kept/stats.json)")


@reads("stats kept")
def fact_internal_evaluation(run):
    lines = []
    for space, entry in (run["stats"]["kept"].get("spaces") or {}).items():
        null, arm = entry.get("b_split_half") or {}, entry.get("arm_null") or {}
        half = (null.get("c2st") or {}).get("auc")
        arms = (arm.get("c2st") or {}).get("auc")
        lines.append(f"{space}: FluXray split-half AUC {half}, arm null AUC {arms}, a null separable: {entry.get('nulls_separable')}")
    return met("; ".join(lines) + " (kept/stats.json)") if lines else missing("needs the spaces of kept/stats.json")


@reads("edit", "filter")
def fact_exclusions(run):
    c, f = counts(run), run["filter"]
    total = f["kept"] + f["dropped"]
    return met(f"{c.get('off_grid')} FluXray samples off the pose grid and {c.get('not_in_db')} not in its ThunderDB left out; "
               f"{c.get('eligible_subjects')} subjects eligible, {c.get('drawn_subjects')} drawn; of {total} edits the paired filter "
               f"dropped {f['dropped']} ({100.0 * f['dropped'] / max(total, 1):.1f} percent, the paper about 4 percent) "
               "(RECORD.json, filter/)")


@reads("edit")
def fact_corrupt(run):
    c, plan = counts(run), run["edit"].get("plan") or {}
    expected = (plan.get("subjects") or 0) * (plan.get("poses_per_subject") or 0)
    if c.get("renders") != expected or c.get("edits") != expected * (plan.get("arms") or 0):
        return missing(f"renders {c.get('renders')} of {expected} and edits {c.get('edits')} of {expected * (plan.get('arms') or 0)}: "
                       "the run did not make every drawn sample")
    return met(f"none: every drawn sample was rendered and edited, renders {c.get('renders')} of {expected}, edits {c.get('edits')} "
               f"of {expected * plan.get('arms')}, and FluXray's image of each exported ({c.get('fluxray_exported')}) (RECORD.json)")


@reads("stats kept", "stats raw")
def fact_endpoints(run):
    record = run["record"]
    parts = [f"replication: {record.get('replication')}; geometry: {record.get('geometry')} (raw median shift "
             f"{(record.get('shifts') or {}).get('raw')} px)"]
    for comparison in COMPARISONS:
        for space, entry in (run["stats"][comparison].get("spaces") or {}).items():
            c, m = entry["a_vs_b"]["c2st"], entry["a_vs_b"]["mmd"]
            parts.append(f"{comparison} {space}: AUC {c['auc']:.3f} [{c['low']:.3f}, {c['high']:.3f}], MMD q {m.get('q', m['p'])}, "
                         f"{entry.get('verdict')}")
    return met("; ".join(parts) + " (RECORD.json, kept/stats.json, raw/stats.json)")


def fact_no_external_model(run):
    return not_applicable("not applicable: no model is trained, so none is tested on external data; FluXray is the set the "
                          "edits are compared with, not a test of a model")


def fact_no_diagnosis(run):
    return not_applicable("not applicable: no diagnosis is estimated; the study tests whether two image sets can be told apart")


@reads("edit")
def fact_protocol(run):
    record = run["record"]
    return met(f"{record.get('prereg')}, sha256 {str(record.get('prereg_sha256'))[:16]} as frozen, with DEVIATIONS.md beside it; "
               "the flow refused to start under any other bytes")


@reads("edit")
def fact_code_state(run):
    record = run["record"]
    return met(f"commit {str(record.get('commit'))[:7]}, {'clean' if record.get('clean_tree') else 'DIRTY'} tree, run {record.get('run')}, "
               f"key {record.get('key')} (RECORD.json)")


@reads("inputs")
def fact_compute(run):
    where, environment = run["record"].get("where") or {}, run["inputs"].get("environment") or {}
    return met(f"host {where.get('host')}, Slurm job {where.get('slurm_job')}, GPU {environment.get('gpu')}, CUDA "
               f"{environment.get('cuda')}, from {run['record'].get('started')} UTC (RECORD.json, inputs.json)")


def fact_reproduce(run):
    return met("docs/research/flux-realism/README.md and flows/README.md: the gate's word `realism edit`, then `realism stats`, "
               "each one GPU job of grid/realism.sbatch, which runs `python flows/launch.py realism -- --stage <stage> ...`")


@reads("stats kept", "stats raw")
def fact_sources_per_set(run):
    parts = [f"{comparison}: " + ", ".join(f"{name} {s['n']} images of {s['subjects']} subjects"
                                           for name, s in (run["stats"][comparison].get("sets") or {}).items())
             for comparison in COMPARISONS]
    return met("; ".join(parts) + "; set b is FluXray's images of the drawn samples (kept/stats.json, raw/stats.json)")


@reads("stats kept")
def fact_outcome(run):
    sets = run["stats"]["kept"].get("sets") or {}
    return met(f"the label the two-sample tests separate is which set an image is from: a, the kept edits ({sets.get('a', {}).get('n')} "
               f"images), and b, FluXray ({sets.get('b', {}).get('n')} images) (kept/stats.json)")


@reads("stats kept")
def fact_sample_size(run):
    sets = run["stats"]["kept"].get("sets") or {}
    return met(", ".join(f"{name}: {s['n']} images of {s['subjects']} subjects" for name, s in sets.items()) + " (kept/stats.json)")


def fact_models_trained(run):
    return not_applicable(NO_TRAINING)


FACTS = {
    "sources": fact_sources, "transforms": fact_transforms, "subsets": fact_subsets, "missing_data": fact_missing_data,
    "partitions": fact_partitions, "disjoint": fact_disjoint, "intended_sample_size": fact_intended_sample_size,
    "instruments": fact_instruments, "software": fact_software, "initialization": fact_initialization,
    "training": fact_training, "no_model_selection": fact_no_model_selection, "ensembling": fact_ensembling,
    "metrics": fact_metrics, "uncertainty": fact_uncertainty, "internal_evaluation": fact_internal_evaluation,
    "exclusions": fact_exclusions, "corrupt": fact_corrupt, "endpoints": fact_endpoints, "no_external_model": fact_no_external_model, "no_diagnosis": fact_no_diagnosis,
    "protocol": fact_protocol, "code_state": fact_code_state, "compute": fact_compute, "reproduce": fact_reproduce,
    "sources_per_set": fact_sources_per_set, "outcome": fact_outcome, "sample_size": fact_sample_size,
    "models_trained": fact_models_trained,
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
        f"sha256, and {answers_shown}; do not edit by hand. Run {record.get('run')}, key {record.get('key')}, commit "
        f"{str(record.get('commit'))[:7]}, PREREG sha256 {str(record.get('prereg_sha256'))[:16]}, started {record.get('started')} UTC.",
        "",
        f"Complete: **{'yes' if not missing_rows else 'no'}**" + (f"; missing {len(missing_rows)}: {', '.join(missing_rows)}." if missing_rows else "."),
        "",
        f"A met item quotes the file that shows it; a declared one is the owner's sentence in {answers_shown}, which the code checks "
        f"is there but cannot judge; a missing one is work to do before the numbers are published (`python3 tools/report.py check "
        f"--study {STUDY} --run <folder> --complete`).",
        "",
        *licence_lines(run),
        "",
        *checklist_section("CLAIM 2024", claim_rows),
        "",
        *checklist_section("REFORMS", reforms_rows),
    ]
    return "\n".join(lines) + "\n"
