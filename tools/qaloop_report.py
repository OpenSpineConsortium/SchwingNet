"""The CLAIM 2024 and REFORMS report of a chain of the QA loop, as tools/report.py's study qa-loop.

    python3 tools/report.py write --study qa-loop --run <chain folder>
    python3 tools/report.py check --study qa-loop --run <chain folder> [--complete]

A chain folder is what one send of the loop kept, <loop root>/<plan>/<chain>/ on the grid
(flows/qaloop.py): RECORD.json, which the flow's end wrote, and the files it names by their sha256,
each round's state.json, gates.json and decision.json. A code answer reads only those files and the
frozen design, never infers, and is missing where a file is absent, is no longer the bytes the
record names, or lacks a field the answer quotes; an answer that restates the frozen PREREG.md holds
only for a chain whose record names its sha256, DESIGN, so a design is never reported in another's
words. The loop's checkpoints steer the work and publish nothing, so the items no file answers, the
owner's own (the title, the abstract, the background and the rest), stay missing until the owner
writes them in data/reporting/studies/qa-loop.json; a session never writes them. What the report
quotes is what the record holds, counts, means and intervals: never a person, a frame's file name or
a value of a header. Standard library only, as tools/report.py is.
"""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STUDY = "qa-loop"
PREREG = ROOT / "docs" / "research" / "qa-loop" / "PREREG.md"
# The pre-registration the design answers restate, by its sha256: PREREG.md as frozen, the digest
# PREREG.md.sha256 beside it holds (tests/test_qaloop_report.py holds the two together).
DESIGN = "c588988049e1c983ee551f9d5c1177f0b8c7db8083bf2dfd73bea6a656e9da55"
# Every frozen PREREG a chain may run under, by its sha256, with its path: the loop's own, and the loop
# with a transformer encoder (docs/research/qa-loop-transformer/PREREG.md, the kind qaloop_tx), which
# adopts the loop's sections 1 to 6 word for word, so the answers restate both alike.
DESIGNS = {DESIGN: "docs/research/qa-loop/PREREG.md",
           "f796b662183d027080776b2c2deb33d2eec096c82df44ea56baaf1525af2b066": "docs/research/qa-loop-transformer/PREREG.md",
           "c7a04e9543bcaff8d67add3128098629752052022cf96bf5773619419fd8454f": "docs/research/qa-loop-gold/PREREG.md"}
LICENCES = ROOT / "data" / "licences.json"
SOURCE = "carmlspine"
# PREREG.md section 6's known limits, one restatement each in the section's order;
# tests/test_qaloop_report.py holds them to the section's bullets, so a limit added there and not
# here fails the check.
LIMITS = (
    "the phantoms' L6 is drawn as an L5 and a four-lumbar column lacks one, so a run that shows neither the thoracic "
    "levels above nor the count from the sacrum cannot tell those columns from a typical one",
    "a run of two or more bodies is named, a single body in the frame is not",
    "no landmark detector exists yet: the landmarks are the oracle's, placed on masks and projected, so the "
    "fingerprint says which landmarks would name the levels, and the latency is the naming path's alone",
    "the phantoms carry no sacrum, so the bottom anchor is a point 15 mm below the last disc",
    "the real arm is typical columns alone, read where the two labellers agree, so real frames say nothing of the "
    "anomalous classes",
    "the poses registered to the real frames fit them imperfectly, which lowers presence and real naming",
    "a frame mirrored against its view's usual side is read as it is stored",
    "the real gate's persons are the same in every round and steered the loop, so only the test persons, never read "
    "here, would be a test",
    "each Wilson interval counts runs, and runs of one person are not independent",
    "a row's crops end at its last level, so a crop's place in its row is a cue the network may use",
    "the 2 pixels of noise on each projected landmark, the lordosis scale of 0.3 to 1.2 and the training watch's "
    "numbers are choices, tuned on nothing, the 50 epochs of patience the owner's",
    "the watch rows are phantoms like the selection's, so the watch says the network learns the phantoms, not that it "
    "outlines a real CT",
    "the smoke runs on stand-ins where no C-ArmLSpine is at hand, which say nothing of real fluoroscopy",
)
# The gold kind's PREREG (docs/research/qa-loop-gold/PREREG.md): it adopts the loop's sections 1 to 6
# and adds the gold arm, whose own known limits (its section 7) a gold chain's report restates after
# the loop's, one restatement each in the section's order; tests/test_qaloop_report.py holds them to
# the section's bullets as LIMITS are held.
GOLD_PREREG = "docs/research/qa-loop-gold/PREREG.md"
# Where the gold design records its departures after the freeze, each dated with its reason.
GOLD_DEVIATIONS = "docs/research/qa-loop-gold/DEVIATIONS.md"
GOLD_LIMITS = (
    "the radiographs are digitally reconstructed from CTs, with no scatter, no detector and no image "
    "intensifier's distortion, so they are not fluoroscopy, and their presence is not the real frames'",
    "every gold case is read as a typical column, so the gold arm says nothing of the anomalous classes",
    "the gold persons' CTs are not yet warped onto columns drawn from the latent prior, so each tier is as many "
    "columns as it has persons",
    "the gold tiers' training persons steer the fingerprint's choice and the controller changes the loop on their "
    "held-out persons' answers, so the gold gates are asked of persons the loop was steered by",
    "gold naming reads the runs with no anchor alone, since a column that can only be typical is named by its count "
    "from the sacrum",
    "the span test's bottom anchor is the sacrum's own top on a gold CT and a point 15 mm below the last disc on a "
    "phantom",
    "gold tier 4's names are two segmenters' agreement, not a person's, and the persons whose maps disagree are "
    "left out, which may leave out the hardest spines; and a scan two collections hold under two person keys is not "
    "resolved to one person",
    "the network's reading of the held-out gold CTs crops them in the oracle's frame from their own label maps, so "
    "it measures the outline and the name, not finding the vertebra",
    "the smoke reads stand-ins where the data root holds no CT of a tier, typical phantoms in place of its CTs, "
    "which say nothing of a real CT",
)
GOLD_NAMES = {"gold3": "gold tier 3 (ENHANCE.PET's CTs, each bone annotated)",
              "gold4": "gold tier 4 (CTs where TotalSegmentator's map agrees with SPINEPS's)"}
# The gates in the order PREREG.md section 3 names them, with the words a page says them in, and the
# gold kind's three after them (docs/research/qa-loop-gold/PREREG.md), each answered tier by tier.
GATE_WORDS = {"convergence": "convergence", "anomaly": "anomaly", "fingerprint": "fingerprint", "presence": "presence",
              "real_naming": "real naming", "latency": "latency", "gold_naming": "gold naming", "gold_span": "gold span",
              "gold_presence": "gold presence"}
GOLD_GATES = ("gold_naming", "gold_span", "gold_presence")

ITEMS = {
    "claim": {
        "7": ("code", "sources"), "9": ("code", "transforms"), "10": ("code", "subsets"), "12": ("code", "missing_data"),
        "19": ("code", "partitions"), "20": ("code", "disjoint"), "22": ("code", "model"), "23": ("code", "software"),
        "24": ("code", "initialization"), "25": ("code", "training"), "26": ("code", "model_selection"),
        "27": ("code", "ensembling"), "28": ("code", "metrics"), "29": ("code", "uncertainty"),
        "32": ("code", "internal_evaluation"), "35": ("code", "exclusions"), "36": ("code", "covariates"),
        "37": ("code", "performance"), "38": ("code", "performance"), "39": ("code", "failure_analysis"),
        "40": ("code", "limitations"), "42": ("code", "protocol"),
    },
    "reforms": {
        "2a": ("code", "sources"), "2b": ("code", "code_state"), "2c": ("code", "compute"), "2d": ("code", "reproduce"),
        "2e": ("code", "reproduce"), "3a": ("code", "per_part"), "3d": ("code", "outcome_counts"),
        "3e": ("code", "sample_size"), "3f": ("code", "missing_data"), "4a": ("code", "exclusions"),
        "4b": ("code", "exclusions"), "4c": ("code", "transforms"), "5a": ("code", "models_trained"),
        "5c": ("code", "partitions"), "5d": ("code", "model_selection"), "6b": ("code", "disjoint"),
        "7a": ("code", "metrics"), "7b": ("code", "uncertainty"),
    },
}


class QaloopReportError(Exception):
    """A folder that is not a chain of the loop, said in words."""


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


def summaries(record):
    """The rounds RECORD.json says in words, those with a whole number, in order."""
    rounds = [r for r in record.get("rounds") or [] if isinstance(r, dict) and isinstance(r.get("round"), int)]
    return sorted(rounds, key=lambda r: r["round"])


def load(name, run_dir):
    """A chain folder's files as the facts read them; a folder with no RECORD.json of the loop is not
    a chain of it. Every round whose tool ended well has its gates.json read, and the last round its
    decision.json."""
    run_dir = Path(run_dir)
    record = read_json(run_dir / "RECORD.json")
    if not isinstance(record, dict) or record.get("study") != STUDY:
        raise QaloopReportError(f"{run_dir}: no RECORD.json of the study {STUDY}, so this is not a chain of the loop")
    run = {"dir": run_dir, "name": name, "record": record, "register": read_json(LICENCES) or {}, "rounds": {},
           "gaps": {}, "decision": None}
    for summary in summaries(record):
        if summary.get("exit") == 0:
            n = summary["round"]
            run["rounds"][n], run["gaps"][f"round {n}"] = checked(run_dir, record, f"rounds/{n:03d}/gates.json")
    said = summaries(record)
    if said:
        last = said[-1]["round"]
        run["decision"], run["gaps"]["decision"] = checked(run_dir, record, f"rounds/{last:03d}/decision.json")
    else:
        run["gaps"]["decision"] = "RECORD.json names no round"
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
    """Why the design's words do not hold for this chain, or empty where its record names the frozen
    design."""
    named = run["record"].get("prereg_sha256")
    return "" if named in DESIGNS else (f"RECORD.json names PREREG sha256 {str(named)[:16]}, not the frozen "
                                        f"{DESIGN[:16]}: the chain ran another design, which this report does not restate")


def design_of(run):
    """The sha256 of the frozen design the chain's record names, once design_gap holds it is one."""
    return str(run["record"].get("prereg_sha256"))


def restated(run, text):
    """An answer that restates the frozen design, for a chain that ran it."""
    gap = design_gap(run)
    return missing(gap) if gap else met(f"{text} (PREREG.md, sha256 {design_of(run)[:16]})")


def plan(run):
    return run["record"].get("plan") or {}


def is_smoke(run):
    return plan(run).get("class") == "smoke"


def answered(run):
    """The newest round whose tool ended well, (its number, its gates.json, why it cannot answer):
    the gates read whole, or None and the gap."""
    done = [r["round"] for r in summaries(run["record"]) if r.get("exit") == 0]
    if not done:
        return None, None, "needs a round whose tool ended well: RECORD.json names none"
    n = done[-1]
    gates = run["rounds"].get(n)
    return (n, gates, "") if gates else (n, None, needs(run, f"round {n}"))


def where(n, part=""):
    return f"rounds/{n:03d}/gates.json" + (f", {part}" if part else "")


def number(value, digits=3):
    """A value as the record holds it: a number to the digits, anything else as it is written."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value)
    return f"{value:.{digits}f}" if isinstance(value, float) else str(value)


def stand_in_words(gates):
    """The words a real gate's answer carries where its frames were stand-ins."""
    return "; asked of stand-ins, phantoms rendered as frames, which say nothing of real fluoroscopy" \
        if (gates or {}).get("stand_in") else ""


def gold_stand_in_words(result):
    """The words a gold gate's answer carries where its CTs were stand-ins."""
    return "; asked of stand-ins, typical phantoms in place of a tier's CTs, which say nothing of a real CT" \
        if (result or {}).get("stand_in") else ""


def gold_of(gates):
    """Each gold tier's reading in the round's gates.json, {} for a chain with no gold arm."""
    return {t: r for t, r in sorted((gates.get("gold") or {}).items()) if isinstance(r, dict)}


def gold_read_words(gates):
    """Each gold tier's cases as the round read them, counts alone."""
    said = []
    for tier, r in gold_of(gates).items():
        persons = r.get("read_persons") or {}
        what = ("stand-ins, typical phantoms in place of its CTs, which say nothing of a real CT" if r.get("stand_in")
                else "CTs")
        said.append(f"{GOLD_NAMES.get(tier, tier)}: {r.get('read')} {what} read, {persons.get('training')} training and "
                    f"{persons.get('validation')} held-out persons, {r.get('levels_unread')} levels left unread, the "
                    f"oracle having placed them nowhere or off their bone ({r.get('cases')} found under the data root)")
    return "; ".join(said)


def fact_sources(run):
    n, gates, gap = answered(run)
    if gap:
        return missing(gap)
    pairs = gates.get("pairs") or {}
    entry = (run["register"].get("sources") or {}).get(SOURCE)
    licence = f"{entry.get('licence')}, class {entry.get('class')}" if entry else "no entry in data/licences.json"
    real = {"C-ArmLSpine": f"C-ArmLSpine's CBCT-to-frame pairs ({licence}), {pairs.get('read')} of "
                           f"{pairs.get('cases')} cases read",
            "stand-ins": f"no C-ArmLSpine under the data root, so {pairs.get('read')} stand-ins, phantoms rendered as "
                         "frames, which say nothing of real fluoroscopy",
            "none": "no real pairs and no stand-ins"}.get(pairs.get("source"), f"real pairs from {pairs.get('source')!r}")
    classes = plan(run).get("classes") or []
    gold = gold_read_words(gates)
    return restated(run, f"phantoms of {len(classes)} column classes ({', '.join(classes)}) drawn by the vendored "
                         "phantom (grid/autoanatomist/autoanatomist/phantom.py) from schwingcheck's correlated column "
                         f"draw; {real}" + (f"; {gold}, each tier its own arm" if gold else "")
                         + f" ({where(n, 'pairs and gold' if gold else 'pairs')})")


def fact_transforms(run):
    rows = plan(run).get("phantom_rows") or {}
    fp = plan(run).get("fingerprint") or {}
    return restated(run, f"each phantom row of four levels from its class's start level rendered at {rows.get('spacing')} mm "
                         f"with noise {rows.get('noise')} HU and cropped as the auto-anatomist crops, 48 by 56 by 32 voxels "
                         "at 2 mm; each fingerprint person's eighteen landmarks placed exactly from its drawn shape, the "
                         f"column bent into a lordosis scaled {fp.get('lordosis')} and projected through C-arm poses about "
                         f"the anteroposterior and lateral views with {fp.get('noise_px')} pixels of noise; each real "
                         "case's CBCT masks read by the oracle on the agreed levels, the landmarks taken to the scanner's "
                         "frame and projected through each frame's registered pose, and the frame read as attenuation "
                         "for presence (PREREG.md section 2)")


def fact_subsets(run):
    n, gates, gap = answered(run)
    if gap:
        return missing(gap)
    p = plan(run)
    config, start = gates.get("config") or {}, p.get("start") or {}
    rows, fp = p.get("phantom_rows") or {}, p.get("fingerprint") or {}
    return met(f"the selection in round {n}: {config.get('phantoms_per_class')} phantom rows and "
               f"{config.get('fingerprint_persons')} fingerprint persons a class (round 0: "
               f"{start.get('phantoms_per_class')} and {start.get('fingerprint_persons')}); the gate: "
               f"{rows.get('gate_per_class')} phantom rows a class, the same every round, and {fp.get('gate_persons')} "
               "fingerprint persons a class, drawn anew each round; the real pairs dealt by data/splits/rule.json, "
               f"validation persons to the gates and training persons to the selection (RECORD.json, {where(n, 'config')})")


def fact_missing_data(run):
    return restated(run, "no imputation: a real case that cannot be read is left out and counted by the kind of its error, "
                         "a gate without its data ends the loop stopped, a measure that is not a number fails its bar, "
                         "a training check whose numbers cannot be right ends it stopped, and a round whose tool fails "
                         "twice, Metaflow's @retry running it once more, ends the loop failed (PREREG.md sections 3 to 5a)")


def split_files(run):
    """The split files the chain's start read, each by the first 16 hex of its sha256."""
    files = run["record"].get("splits") or {}
    return "; ".join(f"{path} {str(sha)[:16]}" for path, sha in sorted(files.items())) or "none recorded"


def fact_partitions(run):
    return restated(run, "a phantom is a person by its seed, the selection's and the gate's seeds a million apart and the "
                         "gate's fingerprint persons drawn anew each round; a real person is a C-ArmLSpine case, its part "
                         "the one data/splits/rule.json gives it (salt schwingnet-2026-10-21, validation share 0.1), "
                         "validation persons to the gates and training persons to the selection; no person on "
                         f"data/splits/test-persons.json is read; the files read: {split_files(run)}")


def fact_disjoint(run):
    return restated(run, "each phantom person and each real person sits in one part, and the namer is cross-validated "
                         "person-wise on the selection's runs; known limits: runs of one person are not independent, so "
                         "each Wilson interval counts runs and the persons are counted beside each cell, and the real "
                         "gate's persons are the same in every round and steered the loop (PREREG.md section 6)")


def fact_model(run):
    n, gates, gap = answered(run)
    if gap:
        return missing(gap)
    fp, config = gates.get("fingerprint") or {}, gates.get("config") or {}
    chosen, pool = fp.get("chosen") or [], fp.get("pool") or []
    return met(f"the auto-anatomist of grid/autoanatomist/ with the words {' '.join(plan(run).get('words') or [])} and "
               f"w_name {config.get('w_name')}, one network carried through every round; the namer, per view a Gaussian "
               "per column type and level over the chosen landmarks' features with a covariance pooled over the view and "
               f"shrunk 0.2 toward its diagonal; the fingerprint of round {n}: {', '.join(chosen) or 'none'} "
               f"({len(chosen)} of a pool of {len(pool)}) ({where(n, 'config and fingerprint')})")


def fact_software(run):
    n, gates, gap = answered(run)
    if gap:
        return missing(gap)
    env = gates.get("environment") or {}
    if not env:
        return missing(f"needs the environment in {where(n)}")
    packages = ", ".join(f"{k} {v or 'absent'}" for k, v in sorted((env.get("packages") or {}).items()))
    return met(f"Python {env.get('python')}, {packages} ({where(n, 'environment')})")


def seed_word(run):
    seeds = [w.split("=", 1)[1] for w in plan(run).get("words") or [] if isinstance(w, str) and w.startswith("seed=")]
    return seeds[-1] if seeds else None


def fact_initialization(run):
    seed = seed_word(run)
    said = f"seed {seed}, the plan's word" if seed is not None else "the vendored default seed, the plan naming none"
    return met(f"random initialisation from {said}, no weights from elsewhere; each round carries on the session the "
               "round before saved (RECORD.json)")


def fact_training(run):
    n, gates, gap = answered(run)
    if gap:
        return missing(gap)
    rounds = summaries(run["record"])
    changed = sum(1 for r in rounds if r.get("changes"))
    steps = ((gates.get("gates") or {}).get("convergence") or {}).get("steps")
    watch = gates.get("watch") or {}
    watched = (f"; the watch checked the held measures {watch.get('checks')} times in round {n}, which ended at epoch "
               f"{number_words(watch.get('epoch'))}, its last gain at epoch {number_words(watch.get('best_epoch'))}"
               + (", and training rested, no gain within the watch's patience" if watch.get("stalled") else "")
               if watch else "")
    return met(f"up to {plan(run).get('steps_per_round')} steps a round, stopped once the held measures gained nothing "
               f"within the watch's patience, over {len(rounds)} rounds, {steps} steps in all by round {n}, the session "
               f"carried from round to round{watched}; the controller changed the configuration after {changed} of them, to "
               f"{json.dumps(gates.get('config') or {}, sort_keys=True)} for round {n} (RECORD.json, "
               f"{where(n, 'convergence, watch and config')}; TREND.jsonl)")


def number_words(x):
    return f"{x:.1f}" if isinstance(x, (int, float)) and not isinstance(x, bool) else "none"


def fact_model_selection(run):
    return restated(run, "nothing is chosen on the gates: the network read is the last round's, and the fingerprint's "
                         "landmarks are chosen by the greedy forward search on the selection's runs alone, under three-fold "
                         "person-wise cross-validation, and judged on the gate's (PREREG.md section 3)")


def fact_ensembling(run):
    return restated(run, "none: one network carried through every round, and one namer a view")


def fact_metrics(run):
    bars = plan(run).get("bars") or {}
    c, a = bars.get("convergence") or {}, bars.get("anomaly") or {}
    f, pr, lat = bars.get("fingerprint") or {}, bars.get("presence") or {}, bars.get("latency") or {}
    return restated(run, f"convergence, the mean training loss over the last {c.get('window')} steps within "
                         f"{c.get('rel_tol')} of the {c.get('window')} before, relatively, and the held-out mean surface "
                         f"distance no more than {c.get('rise_tol')} above the best earlier round's; anomaly, per class the "
                         f"mean hard Dice of the CT-only mask (bar {a.get('dice')}), the share named right (bar "
                         f"{a.get('named_right')}) and the latent probe's recall (bar {a.get('probe_recall')}); fingerprint "
                         "and real naming, per cell the Wilson 95 per cent lower bound of the accuracy (bar "
                         f"{f.get('accuracy_low')}) and the lower median margin (bar {f.get('margin')}); presence, the "
                         "Wilson lower bound of the share of frames whose landmarks' mean edge percentile reaches "
                         f"{pr.get('frame_mean')} (bar {pr.get('share_low')}); latency, the 95th percentile of the naming "
                         f"path's time (bar {lat.get('p95_ms')} ms) (PREREG.md section 3)")


def fact_uncertainty(run):
    said = ("Wilson 95 per cent intervals on each fingerprint and real naming cell's accuracy and on presence's share of "
            "frames, counting runs and frames, not persons, the persons counted beside each cell; the convergence and "
            "anomaly measures and the latency percentile are point values with no interval; a cell's margin is its lower "
            "median, so an even cell is never flattered")
    if is_smoke(run):
        return restated(run, f"{said}; the smoke answers no question, so none of its numbers is read as a result "
                             "(PREREG.md section 5)")
    return restated(run, f"{said} (PREREG.md section 3)")


def fact_internal_evaluation(run):
    n, gates, gap = answered(run)
    if gap:
        return missing(gap)
    fp, held = gates.get("fingerprint") or {}, gates.get("held") or {}
    rows = (plan(run).get("phantom_rows") or {}).get("gate_per_class")
    gold = ""
    if gold_of(gates):
        read = "; ".join(f"{t}: Dice {number(r.get('dice'))}, distance {number(r.get('distance_mm'))} mm, named right "
                         f"{number(r.get('named_right'))} on {r.get('cases')} CTs" if not r.get("missing")
                         else f"{t}: {r.get('missing')}" for t, r in sorted((gates.get("gold_held") or {}).items()))
        gold = (f"; the gold tiers: {fp.get('gold_gate_runs')} runs of their held-out persons' radiographs, and the "
                f"network's reading of their held-out CTs, recorded and gated on by nothing ({read or 'none recorded'})")
    return met(f"round {n}'s gate: {rows} phantom rows a class ({held.get('crops')} crops) and "
               f"{fp.get('gate_runs')} fingerprint runs, {fp.get('real_gate_runs')} of them from the validation persons' "
               f"frames{stand_in_words(gates)}{gold} ({where(n, 'held and fingerprint')})")


def fact_exclusions(run):
    n, gates, gap = answered(run)
    if gap:
        return missing(gap)
    pairs = gates.get("pairs") or {}
    if pairs.get("source") != "C-ArmLSpine":
        return met(f"no real case was read ({pairs.get('source')}), so none was left out{gold_exclusions(gates)}; no "
                   f"phantom is ever left out ({where(n, 'pairs')})")
    left = ", ".join(f"{k} {v}" for k, v in sorted((pairs.get("left_out") or {}).items())) or "none"
    failed = ", ".join(f"{k} {v}" for k, v in sorted((pairs.get("failed") or {}).items())) or "none"
    return met(f"C-ArmLSpine: {pairs.get('cases')} cases taken and {pairs.get('read')} read; left out before reading, "
               f"by reason: {left}; failed while reading, by the kind of error: {failed}{gold_exclusions(gates)}; no "
               f"phantom is ever left out ({where(n, 'pairs')})")


def gold_exclusions(gates):
    """Each gold tier's cases left out before reading and failed while reading, by reason."""
    said = ""
    for tier, r in gold_of(gates).items():
        left = ", ".join(f"{k} {v}" for k, v in sorted((r.get("left_out") or {}).items())) or "none"
        failed = ", ".join(f"{k} {v}" for k, v in sorted((r.get("failed") or {}).items())) or "none"
        said += f"; {tier}: left out before reading, by reason: {left}; failed while reading: {failed}"
    return said


def fact_covariates(run):
    return missing("no demographic or clinical characteristic of a real person is read, since no header value of "
                   "C-ArmLSpine leaves the grid; the phantoms' partitions hold the plan's column classes alike")


def gate_said(name, result):
    """One gate's answer of a round in words, from its gates.json."""
    if not result:
        return f"{GATE_WORDS[name]} not asked"
    if result.get("missing"):
        return f"{GATE_WORDS[name]} without its data: {result['missing']}"
    word = "passes" if result.get("pass") else "fails"
    if name in GOLD_GATES:
        return f"{GATE_WORDS[name]} {word}: {tiers_said(name, result)}{gold_stand_in_words(result)}"
    detail = {
        "convergence": lambda r: r.get("why"),
        "anomaly": anomaly_said,
        "fingerprint": cells_said,
        "presence": lambda r: r.get("why"),
        "real_naming": cells_said,
        "latency": lambda r: (f"95th percentile {number(r.get('p95_ms'))} ms over {r.get('n')} runs, median "
                              f"{number(r.get('p50_ms'))} ms, against {r.get('budget_ms')} ms" if "p95_ms" in r else r.get("why")),
    }[name](result)
    return f"{GATE_WORDS[name]} {word}: {detail}{stand_in_words(result)}"


def tiers_said(name, result):
    """A gold gate's answer tier by tier: each tier its own arm, never pooled with the other."""
    said = []
    for tier, r in sorted((result.get("tiers") or {}).items()):
        if not r:
            said.append(f"{tier} not asked")
        elif r.get("missing"):
            said.append(f"{tier} without its data: {r['missing']}")
        else:
            detail = r.get("why") if name == "gold_presence" else cells_said(r)
            said.append(f"{tier} {'passes' if r.get('pass') else 'fails'}, {detail}")
    return "; ".join(said) or "no tier answered"


def anomaly_said(result):
    per_class = result.get("per_class") or {}
    return "; ".join(f"{c} Dice {number(r.get('dice'))}, named right {number(r.get('named_right'))}, probe recall "
                     f"{number(r.get('probe_recall'))} (n {r.get('n')})" for c, r in sorted(per_class.items())) or "no class read"


def cells_said(result):
    failing = result.get("failing_cells") or []
    beyond = result.get("beyond_ceiling") or []
    said = f"{result.get('cells', 0) - len(failing)} of {result.get('cells')} cells pass"
    if failing:
        said += f", {len(beyond)} of the {len(failing)} failing beyond the ceiling of the pool's landmarks"
    return said


def fact_performance(run):
    gap = needs(run, "decision")
    if gap:
        return missing(gap)
    n, gates, gap = answered(run)
    if gap:
        return missing(gap)
    decision = run["decision"]
    said = "; ".join(gate_said(g, (gates.get("gates") or {}).get(g)) for g in plan(run).get("gates") or [])
    return met(f"the loop ended {decision.get('verdict')} after {len(summaries(run['record']))} rounds: {decision.get('why')}; "
               f"round {n}: {said} (rounds/*/decision.json, {where(n, 'gates')})")


def fact_failure_analysis(run):
    gap = needs(run, "decision")
    if gap:
        return missing(gap)
    n, gates, gap = answered(run)
    if gap:
        return missing(gap)
    stuck = run["decision"].get("stuck") or []
    cells = []
    for name in ("fingerprint", "real_naming"):
        for c in ((gates.get("gates") or {}).get(name) or {}).get("failing_cells") or []:
            ceiling = number(c.get("ceiling")) if c.get("ceiling") is not None else "not measured"
            cells.append(f"{c.get('cell')} accuracy {number(c.get('accuracy'))}, low {number(c.get('low'))}, margin "
                         f"{number(c.get('margin'), 2)}, the whole pool's accuracy {ceiling}")
    return met(f"the gates left with no change: {'; '.join(stuck) or 'none'}; the failing cells of round {n}: "
               f"{'; '.join(cells) or 'none'} (rounds/*/decision.json, {where(n, 'failing_cells')})")


def fact_limitations(run):
    gold = ("; and the gold arm's: " + "; ".join(GOLD_LIMITS) + f" ({GOLD_PREREG} section 7)"
            if DESIGNS.get(design_of(run)) == GOLD_PREREG else "")
    return restated(run, "; ".join(LIMITS) + " (PREREG.md section 6)" + gold)


def fact_protocol(run):
    gap = design_gap(run)
    if gap:
        return missing(gap)
    after = (f"; its departures after the freeze, each dated with its reason, are {GOLD_DEVIATIONS}"
             if DESIGNS.get(design_of(run)) == GOLD_PREREG else "")
    return met(f"{DESIGNS[design_of(run)]}, frozen, sha256 {design_of(run)[:16]}, its Covers line naming the plan by its "
               f"bytes ({str(run['record'].get('prereg_part'))}){after}")


def fact_code_state(run):
    record = run["record"]
    place = record.get("where") or {}
    return met(f"commit {record.get('commit')}, run from a copy of it ({place.get('copy_of') or 'no copy named'}), "
               f"run {record.get('run')} (RECORD.json)")


def fact_compute(run):
    done = [r["round"] for r in summaries(run["record"]) if r.get("exit") == 0]
    gap = needs(run, *(f"round {n}" for n in done))
    if gap:
        return missing(gap)
    if not done:
        return missing("needs a round whose tool ended well: RECORD.json names none")
    totals = {}
    for n in done:
        for part, seconds in (run["rounds"][n].get("seconds") or {}).items():
            if isinstance(seconds, (int, float)):
                totals[part] = totals.get(part, 0.0) + seconds
    env = run["rounds"][done[-1]].get("environment") or {}
    place = run["record"].get("where") or {}
    spent = ", ".join(f"{part} {seconds:.0f} s" for part, seconds in sorted(totals.items()))
    return met(f"{place.get('host')}, Slurm job {place.get('slurm_job')}, {env.get('backend')} "
               f"{', '.join(env.get('devices') or [])}, {env.get('cpus')} CPUs; the rounds' seconds by part: {spent} "
               "(RECORD.json, rounds/*/gates.json)")


def fact_reproduce(run):
    return met(f"grid/gate.sh's word `qaloop {plan(run).get('plan')}` at commit {run['record'].get('commit')}, under the "
               "frozen PREREG and the plan its Covers line names, runs the same procedure; a chain that did not end is "
               "carried on at its own commit, one that ended 0 is not sent again, and one that ended otherwise is sent "
               "again only once the checkout's commit has moved; a GPU's sums are not the same to the bit, so a rerun's "
               "measures agree within run-to-run noise and its controller may take another path where a round's answer "
               "falls on the other side of a bar")


def fact_per_part(run):
    n, gates, gap = answered(run)
    if gap:
        return missing(gap)
    fp = gates.get("fingerprint") or {}
    return met(f"round {n}: the selection's {fp.get('selection_runs')} fingerprint runs, {fp.get('real_selection_runs')} of "
               f"them from the training persons' frames, and the gate's {fp.get('gate_runs')}, {fp.get('real_gate_runs')} "
               f"from the validation persons'; the test part not read{stand_in_words(gates)} ({where(n, 'fingerprint')})")


def fact_outcome_counts(run):
    n, gates, gap = answered(run)
    if gap:
        return missing(gap)
    cells = gates.get("cells") or {}
    if not cells:
        return missing(f"needs the gate's cells in {where(n)}: no fingerprint was judged")
    by_type = {}
    for key, c in cells.items():
        kind = key.split("/")[-1]
        by_type[kind] = by_type.get(kind, 0) + int(c.get("n") or 0)
    sizes = [int(c.get("n") or 0) for c in cells.values()]
    said = ", ".join(f"{kind} {count}" for kind, count in sorted(by_type.items()))
    return met(f"the outcome is a run's names, one placement of k consecutive levels in one column type; round {n}'s gate "
               f"held {sum(sizes)} runs in {len(cells)} cells, {min(sizes)} to {max(sizes)} a cell; by column type: {said} "
               f"({where(n, 'cells')})")


def fact_sample_size(run):
    p = plan(run)
    start, limits = p.get("start") or {}, p.get("limits") or {}
    if is_smoke(run):
        return restated(run, f"the smoke's sizes, {start.get('phantoms_per_class')} phantom rows and "
                             f"{start.get('fingerprint_persons')} fingerprint persons a class at the start, try the code "
                             "path and answer no question (PREREG.md section 5)")
    grown_by = ", ".join(f"{k} {'the memory' if v is None else v}" for k, v in sorted(limits.items()))
    return restated(run, f"the loop's sizes start at {json.dumps(start, sort_keys=True)} and grow by the controller up to "
                         f"{grown_by}; they are not powered for an effect, and each gate's interval says what its count "
                         "supports (PREREG.md section 4)")


def fact_models_trained(run):
    rounds = summaries(run["record"])
    return met(f"one network carried through {len(rounds)} rounds; in each round one namer a view fitted on the "
               "selection's runs for the chosen landmarks, one for the whole pool as the ceiling, and the "
               "cross-validated namers of the greedy search (RECORD.json)")


FACTS = {
    "sources": fact_sources, "transforms": fact_transforms, "subsets": fact_subsets, "missing_data": fact_missing_data,
    "partitions": fact_partitions, "disjoint": fact_disjoint, "model": fact_model, "software": fact_software,
    "initialization": fact_initialization, "training": fact_training, "model_selection": fact_model_selection,
    "ensembling": fact_ensembling, "metrics": fact_metrics, "uncertainty": fact_uncertainty,
    "internal_evaluation": fact_internal_evaluation, "exclusions": fact_exclusions, "covariates": fact_covariates,
    "performance": fact_performance, "failure_analysis": fact_failure_analysis, "limitations": fact_limitations,
    "protocol": fact_protocol, "code_state": fact_code_state, "compute": fact_compute, "reproduce": fact_reproduce,
    "per_part": fact_per_part, "outcome_counts": fact_outcome_counts, "sample_size": fact_sample_size,
    "models_trained": fact_models_trained,
}


def cell(text):
    """Text that stays in one cell of a Markdown table."""
    return str(text).replace("|", "/").replace("\n", " ")


def rounds_section(run):
    """Every round as RECORD.json says it: how its tool ended, each gate's word, the decision and the
    change it made."""
    gates = plan(run).get("gates") or []
    lines = ["## Rounds", "",
             "| round | exit | " + " | ".join(GATE_WORDS.get(g, g) for g in gates) + " | decision | changes |",
             "|---|---|" + "---|" * len(gates) + "---|---|"]
    for r in summaries(run["record"]):
        said = [(r.get("gates") or {}).get(g, "not asked") for g in gates]
        lines.append(f"| {r['round']} | {r.get('exit')} | " + " | ".join(cell(s) for s in said)
                     + f" | {cell(r.get('verdict'))} | {cell('; '.join(r.get('changes') or []) or 'none')} |")
    if any(r.get("stand_in") for r in summaries(run["record"])):
        lines += ["", "The real gates were asked of stand-ins, phantoms rendered as frames, so they say nothing of real "
                      "fluoroscopy."]
    return lines


def markdown(run, claim_rows, reforms_rows, checklist_section, answers_shown):
    record = run["record"]
    decision = record.get("decision") or {}
    missing_rows = [f"CLAIM {r['id']}" for r in claim_rows if r["state"] == "missing"]
    missing_rows += [f"REFORMS {r['id']}" for r in reforms_rows if r["state"] == "missing"]
    lines = [
        f"# Report of study {STUDY}, chain {record.get('chain')} of {plan(run).get('plan')}",
        "",
        f"Written by `python3 tools/report.py write --study {STUDY}` from this folder's RECORD.json and the files it names by "
        f"their sha256, and {answers_shown}; do not edit by hand. Commit {record.get('commit')}, PREREG sha256 "
        f"{str(record.get('prereg_sha256'))[:16]}, run {record.get('run')}, {record.get('started')} to {record.get('ended')} UTC.",
        "",
        f"The loop ended **{decision.get('verdict')}** after {len(summaries(record))} rounds: {decision.get('why')}.",
        "",
        *rounds_section(run),
        "",
        f"Complete: **{'yes' if not missing_rows else 'no'}**" + (f"; missing {len(missing_rows)}: {', '.join(missing_rows)}." if missing_rows else "."),
        "",
        "The loop's checkpoints steer the work and publish nothing; a missing item is work to do before any number of it is "
        f"published (`python3 tools/report.py check --study {STUDY} --run <folder> --complete`).",
        "",
        *checklist_section("CLAIM 2024", claim_rows),
        "",
        *checklist_section("REFORMS", reforms_rows),
    ]
    return "\n".join(lines) + "\n"
