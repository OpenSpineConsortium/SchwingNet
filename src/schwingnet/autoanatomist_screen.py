"""The auto-anatomist's screen as pure logic: the plan, its trials, the steps an epoch takes, the
rows' parts under the project's frozen split and the decision against the null
(docs/research/autoanatomist-screen/README.md).

A screen trains every arm of a plan at every seed for the same number of epochs, each trial on a
card of its own, and reads each on the validation persons alone; the join then asks of each arm
whether every one of its seeds ends below every seed of the null on the plan's measure, the mean
symmetric surface distance in millimetres. The first screen holds the network at the fully latent
objective and varies only the anneal, so its null is the schedule that never anneals: the CT alone
from the first step, the network with no privileged information. Everything the flow decides is a
function here, so that the gate proves it and the flow (flows/autoanatomist.py) only carries it
out: a plan that does not hold is said in words (plan_problems), never guessed at; a row whose part
is not the one data/splits/rule.json gives its person, or whose person is on the test list, is
refused (rows_problems), so a screen never reads a test person; and the decision is the same
however the trials are ordered.

Standard library with beartype and beethoven-qa's contracts, as the package's rules ask; nothing
here reads a file, renders a crop or trains a network. A plan, an entry and a decision are read as
the JSON they are, dicts and lists, so a mapping of another kind is refused rather than read.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from beartype import beartype
from beethoven_qa.contracts import ensure, require

from schwingnet.autoanatomist_search import HASH_SPAN, hash_value

ENTRY_VERSION = 1
ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_")
ITEM_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_:.-")
WORD_KEY_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz_")
JOB_CLASSES = ("batch", "gpu")
LAYOUTS = ("array", "series")
READ_PARTS = ("train", "validation")
MEASURES = ("distance_mm",)
# The level names the vendored network's name head knows (autoanatomist.naming.NAMES, which is
# schwingcheck.chain's order): C3 to L5, then L6 and T13. A label the data map names otherwise is
# refused here, before any crop is cut; the trial checks the same against the package itself.
NAMES = (
    *(f"C{i}" for i in range(3, 8)),
    *(f"T{i}" for i in range(1, 13)),
    *(f"L{i}" for i in range(1, 6)),
    "L6",
    "T13",
)
# The words a plan sets from its own keys, so that neither the fixed words nor an arm may set them:
# the seed from seeds, the batch from batch and the anneal's length from epochs and the rows.
PLAN_WORDS = ("seed", "batch", "anneal")
MAX_EPOCHS = 1000
MAX_BATCH = 64
MAX_SEEDS = 16
MAX_ARMS = 16
MAX_ROWS = 20000
# The packages a GPU trial's environment holds beside train-gpu's (grid/autoanatomist.sbatch's
# AUTOANATOMIST_PIN, one line; tests/test_gate.py holds the two equal): the newest JAX, Flax and
# optax that run on the grid's Python 3.11, with which bordercall's 86 tests passed on 2026-10-30,
# JAX's CUDA 12 wheels, and the readers the vendored package needs that train-gpu lacks. The trial
# records what it found installed and refuses versions other than these.
PINS = (
    "jax[cuda12]==0.10.2",
    "flax==0.12.8",
    "optax==0.2.8",
    "orbax-checkpoint==0.12.8",
    "numpy==2.4.6",
    "scipy==1.17.1",
    "nibabel==5.3.2",
)
# The lists of persons a screen never reads, each a JSON list of {person, why}: the project's test
# part, and the reserve the latent shape priors' plan holds back for its own test.
TEST_LISTS = ("data/splits/test-persons.json", "data/splits/latent-prior-test-reserve.json")
# The lists of units of probable repeat scans, each a JSON list of {unit, persons, outside_export,
# why}: a unit is one patient's studies as far as their vertebral volumes, spacings and ribs say,
# keyed by the person of its lowest study, and its rows keep the part the rule gives that key.
UNIT_LISTS = ("data/splits/latent-prior-repeat-groups.json",)
# The keys a plan holds, every one required, so a plan is read the same way twice.
SCREEN_KEYS = (
    "screen",
    "purpose",
    "class",
    "layout",
    "data",
    "rows",
    "split",
    "test",
    "fixed",
    "arms",
    "null",
    "seeds",
    "epochs",
    "evaluate_every",
    "batch",
    "measure",
)
ROW_KEYS = ("item", "person", "part", "source")
DATA_KEYS = ("ct", "labels", "labels_folder", "names")
SPLIT_KEYS = ("salt", "validation_share")
# What a trial writes when it ends, the join's one input (entry_problems says what each holds).
ENTRY_KEYS = (
    "version",
    "screen",
    "trial",
    "arm",
    "seed",
    "words",
    "steps",
    "epochs",
    "final",
    "seconds",
    "seconds_per_crop",
    "train_rows",
    "validation_rows",
)
# What each evaluation point holds, read on the validation CTs alone, and the last point's
# measures again as the entry's final ones (train.evaluate_masks says what each is).
MEASURE_KEYS = ("dice", "distance_mm", "surface_missing", "centroid_mm", "name_accuracy")
EPOCH_KEYS = ("epoch", "steps", "loss", *MEASURE_KEYS)
FINAL_KEYS = MEASURE_KEYS


@dataclass(frozen=True)
class Plan:
    """One screen as its file holds it, every value typed and checked (plan_of)."""

    screen: str
    purpose: str
    job_class: str
    layout: str
    data: dict[str, dict[str, object]]
    rows: tuple[dict[str, str], ...]
    salt: str
    validation_share: float
    fixed: tuple[str, ...]
    arms: dict[str, tuple[str, ...]]
    null: str
    seeds: tuple[int, ...]
    epochs: int
    evaluate_every: int
    batch: int
    measure: str


@dataclass(frozen=True)
class TrialSpec:
    """One trial of a screen: its id, its arm, its seed and every block word it trains under."""

    id: str
    arm: str
    seed: int
    words: tuple[str, ...]


# --- names, numbers and words ---------------------------------------------------------------------


def _is_id(text: object) -> bool:
    """A screen's, an arm's or a trial's name: lower-case letters, digits and _, 1 to 40 of them."""
    return isinstance(text, str) and 0 < len(text) <= 40 and set(text) <= ID_CHARS


def _is_item(text: object) -> bool:
    """A row's item or person, as the gold 3 store spells one (enhance_pet:0001)."""
    return isinstance(text, str) and 0 < len(text) <= 80 and set(text) <= ITEM_CHARS


def _is_count(value: object, low: int, high: int) -> bool:
    """A whole number from low to high, never a bool."""
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def _is_share(value: object) -> bool:
    """A finite number strictly between 0 and 1, never a bool."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value) and 0 < value < 1


def _is_word(text: object) -> bool:
    """One block as the auto-anatomist spells it, KEY=VALUE, the key lower-case letters and _."""
    if not isinstance(text, str) or "=" not in text:
        return False
    key, value = text.split("=", 1)
    return bool(key) and set(key) <= WORD_KEY_CHARS and bool(value) and " " not in value


def _word_key(word: str) -> str:
    return word.split("=", 1)[0]


def _is_relative(path: object) -> bool:
    """A folder under the data root: relative, with no part that climbs out of it."""
    if not isinstance(path, str) or not path or path.startswith("/") or "\\" in path:
        return False
    return all(part not in ("", ".", "..") for part in path.split("/"))


def _is_finite(value: object) -> bool:
    """A finite int or float that is not a bool."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return isinstance(value, int) or math.isfinite(value)


# --- the plan -------------------------------------------------------------------------------------


def _head_problems(record: Mapping[str, object]) -> list[str]:
    if not _is_id(record["screen"]):
        return ["screen: lower-case letters, digits and _, 1 to 40 of them"]
    if not isinstance(record["purpose"], str) or not record["purpose"].strip():
        return ["purpose: a sentence saying what the screen asks"]
    if record["class"] not in JOB_CLASSES:
        return [f"class: one of {', '.join(JOB_CLASSES)}"]
    if record["layout"] not in LAYOUTS:
        return [f"layout: one of {', '.join(LAYOUTS)}"]
    if record["test"] != "off":
        return ["test: off, the only value: a screen reads validation persons, never the test part"]
    if record["measure"] not in MEASURES:
        return [f"measure: one of {', '.join(MEASURES)}"]
    return []


def _names_problems(source: str, names: object) -> list[str]:
    if not isinstance(names, dict) or not names:
        return [f"data: {source}'s names map each label it reads to a level name"]
    for label, name in names.items():
        if not isinstance(label, str) or not label.isdigit() or label.startswith("0"):
            return [f"data: {source}'s labels are whole numbers from 1, as strings, not {label!r}"]
        if name not in NAMES:
            return [f"data: {source} names label {label} {name!r}, which the name head lacks"]
    if len(set(names.values())) != len(names):
        return [f"data: {source} gives one level name to two labels"]
    return []


def _data_problems(data: object) -> list[str]:
    if not isinstance(data, dict) or not data:
        return ["data: one entry a source: where its CTs and label maps are, what each label is"]
    for source, entry in data.items():
        if not _is_id(source):
            return [f"data: a source is lower-case letters, digits and _, not {source!r}"]
        if not isinstance(entry, dict) or set(entry) != set(DATA_KEYS):
            return [f"data: {source} holds {', '.join(DATA_KEYS)}, and nothing else"]
        for key in ("ct", "labels"):
            if not _is_relative(entry[key]):
                return [f"data: {source}'s {key} is a folder under the data root: {entry[key]!r}"]
        folder = entry["labels_folder"]
        if not isinstance(folder, str) or not folder or "/" in folder or folder in (".", ".."):
            return [f"data: {source}'s labels_folder is one folder's name, not {folder!r}"]
        found = _names_problems(source, entry["names"])
        if found:
            return found
    return []


def _row_problems(row: object, sources: Sequence[str], seen: set[str]) -> list[str]:
    if not isinstance(row, dict) or set(row) != set(ROW_KEYS):
        return [f"rows: a row holds {', '.join(ROW_KEYS)}, and nothing else, not {row!r}"]
    item = row["item"]
    if not _is_item(item) or not _is_item(row["person"]):
        return [f"rows: an item and a person are as the gold 3 store spells them, not {row!r}"]
    if item in seen:
        return [f"rows: {item} is listed twice"]
    seen.add(cast(str, item))
    if row["part"] not in READ_PARTS:
        return [f"rows: {item}'s part is train or validation; a screen holds no test row"]
    if row["source"] not in sources:
        return [f"rows: {item}'s source {row['source']!r} has no entry under data"]
    return []


def _rows_problems(record: Mapping[str, object]) -> list[str]:
    rows = record["rows"]
    if not isinstance(rows, list) or not 2 <= len(rows) <= MAX_ROWS:
        return [f"rows: from 2 to {MAX_ROWS} rows, at least one to train on and one to read"]
    sources = list(cast(Mapping[str, object], record["data"]))
    seen: set[str] = set()
    for row in rows:
        found = _row_problems(row, sources, seen)
        if found:
            return found
    parts = {cast(Mapping[str, object], row)["part"] for row in rows}
    if parts != set(READ_PARTS):
        return ["rows: at least one train row and one validation row"]
    return []


def _split_problems(split: object) -> list[str]:
    if not isinstance(split, dict) or set(split) != set(SPLIT_KEYS):
        return [f"split: {', '.join(SPLIT_KEYS)}, data/splits/rule.json's, and nothing else"]
    if not isinstance(split["salt"], str) or not split["salt"]:
        return ["split: the salt is a string that is not empty"]
    if not _is_share(split["validation_share"]):
        return ["split: validation_share is a share strictly between 0 and 1"]
    return []


def _words_problems(what: str, words: object) -> list[str]:
    if not isinstance(words, list):
        return [f"{what}: a list of KEY=VALUE words"]
    for word in words:
        if not _is_word(word):
            return [f"{what}: {word!r} is no KEY=VALUE word"]
        if _word_key(cast(str, word)) in PLAN_WORDS:
            keys = ", ".join(PLAN_WORDS)
            return [f"{what}: {word} is set by the plan itself ({keys} come from its keys)"]
    given = [_word_key(cast(str, word)) for word in words]
    if len(set(given)) != len(given):
        return [f"{what}: a key is given twice"]
    return []


def _arms_problems(record: Mapping[str, object]) -> list[str]:
    arms = record["arms"]
    if not isinstance(arms, dict) or not 2 <= len(arms) <= MAX_ARMS:
        return [f"arms: from 2 to {MAX_ARMS} arms, the null among them"]
    fixed_keys = {_word_key(word) for word in cast(list[str], record["fixed"])}
    for arm, words in arms.items():
        if not _is_id(arm):
            return [f"arms: an arm's name is lower-case letters, digits and _, not {arm!r}"]
        found = _words_problems(f"arms: {arm}", words)
        if found:
            return found
        clash = sorted(fixed_keys & {_word_key(word) for word in cast(list[str], words)})
        if clash:
            return [f"arms: {arm} sets {', '.join(clash)}, which the fixed words set already"]
    signatures = [tuple(sorted(cast(list[str], words))) for words in arms.values()]
    if len(set(signatures)) != len(signatures):
        return ["arms: two arms train under the same words"]
    if record["null"] not in arms:
        return ["null: one of the arms, the one every other arm is read against"]
    return []


def _tail_problems(record: Mapping[str, object]) -> list[str]:
    seeds = record["seeds"]
    if not isinstance(seeds, list) or not 1 <= len(seeds) <= MAX_SEEDS:
        return [f"seeds: from 1 to {MAX_SEEDS} seeds, every arm trained at each"]
    if not all(_is_count(seed, 0, 2**31 - 1) for seed in seeds) or len(set(seeds)) != len(seeds):
        return ["seeds: distinct whole numbers from 0 to 2**31 - 1"]
    if not _is_count(record["epochs"], 1, MAX_EPOCHS):
        return [f"epochs: a whole number from 1 to {MAX_EPOCHS}"]
    if not _is_count(record["evaluate_every"], 1, cast(int, record["epochs"])):
        return ["evaluate_every: the epochs between two readings, a whole number from 1 to epochs"]
    if not _is_count(record["batch"], 1, MAX_BATCH):
        return [f"batch: whole spines a step, from 1 to {MAX_BATCH}"]
    return []


@beartype
@ensure(lambda result: all(isinstance(line, str) and line for line in result), "lines in words")
def plan_problems(record: object) -> list[str]:
    """What keeps a plan file from holding, one line each; none where it holds. Said in words so
    the flow and the gate word refuse before anything runs, and so a plan is never read two ways.
    The rows' parts against the frozen rule are rows_problems', which needs the test list."""
    if not isinstance(record, dict):
        return ["a plan is a JSON object"]
    missing = [k for k in SCREEN_KEYS if k not in record]
    extra = sorted(str(k) for k in record if k not in SCREEN_KEYS)
    if missing or extra:
        keys = ", ".join(SCREEN_KEYS)
        lost, odd = ", ".join(missing) or "none", ", ".join(extra) or "none"
        return [f"a plan holds {keys}: missing {lost}, unknown {odd}"]
    found = _head_problems(record) or _data_problems(record["data"])
    found = found or _rows_problems(record) or _split_problems(record["split"])
    found = found or _words_problems("fixed", record["fixed"])
    return found or _arms_problems(record) or _tail_problems(record)


@beartype
@require(lambda record: not plan_problems(record), "a plan that holds (plan_problems)")
@ensure(
    lambda result, record: (
        result.screen == record["screen"]
        and len(result.rows) == len(record["rows"])
        and set(result.arms) == set(record["arms"])
    ),
    "the plan read whole",
)
def plan_of(record: Mapping[str, object]) -> Plan:
    """The plan a file holds, typed, from a record plan_problems finds nothing wrong with."""
    split = cast(Mapping[str, object], record["split"])
    data = cast(Mapping[str, Mapping[str, object]], record["data"])
    arms = cast(Mapping[str, Sequence[str]], record["arms"])
    return Plan(
        screen=str(record["screen"]),
        purpose=str(record["purpose"]),
        job_class=str(record["class"]),
        layout=str(record["layout"]),
        data={source: dict(entry) for source, entry in data.items()},
        rows=tuple(
            {key: str(row[key]) for key in ROW_KEYS}
            for row in cast(Sequence[Mapping[str, object]], record["rows"])
        ),
        salt=str(split["salt"]),
        validation_share=float(cast(float, split["validation_share"])),
        fixed=tuple(cast(Sequence[str], record["fixed"])),
        arms={arm: tuple(words) for arm, words in arms.items()},
        null=str(record["null"]),
        seeds=tuple(int(seed) for seed in cast(Sequence[int], record["seeds"])),
        epochs=int(cast(int, record["epochs"])),
        evaluate_every=int(cast(int, record["evaluate_every"])),
        batch=int(cast(int, record["batch"])),
        measure=str(record["measure"]),
    )


# --- the split ------------------------------------------------------------------------------------


@beartype
@require(lambda validation_share: 0 < validation_share < 1, "a share strictly between 0 and 1")
@ensure(lambda result: result in ("train", "validation", "test"), "one of the three parts")
@ensure(
    lambda result, person, test_persons: (result == "test") == (person in test_persons),
    "test exactly for a person on the test list",
)
def rule_part(salt: str, validation_share: float, test_persons: frozenset[str], person: str) -> str:
    """data/splits/rule.json's part of a person: test for a person on data/splits/test-persons.json
    whatever the hash says, validation where the hash is below the validation share, training
    otherwise; the same hash the search uses (autoanatomist_search.hash_value)."""
    if person in test_persons:
        return "test"
    if hash_value(salt, person) < validation_share * HASH_SPAN:
        return "validation"
    return "train"


@beartype
@require(lambda record: not plan_problems(record), "a plan that holds (plan_problems)")
@ensure(lambda result: all(isinstance(line, str) and line for line in result), "lines in words")
def rows_problems(
    record: Mapping[str, object], salt: str, validation_share: float, test_persons: frozenset[str]
) -> list[str]:
    """What keeps a plan's rows from the frozen split: a salt or a share other than the rule
    file's, a person on the test list, or a row whose part is not the one the rule gives its
    person. The flow, the gate's check and scripts/check.sh pass the rule and the test list."""
    split = cast(Mapping[str, object], record["split"])
    if split["salt"] != salt or split["validation_share"] != validation_share:
        said = f"{split['salt']!r} at {split['validation_share']!r}"
        return [f"split: the plan says {said}, and the rule {salt!r} at {validation_share!r}"]
    if not 0 < validation_share < 1:
        return ["split: the rule's validation share is not strictly between 0 and 1"]
    for row in cast(Sequence[Mapping[str, str]], record["rows"]):
        part = rule_part(salt, validation_share, test_persons, row["person"])
        item, person = row["item"], row["person"]
        if part == "test":
            return [f"rows: {item}'s person {person} is on a test list, which a screen never reads"]
        if part != row["part"]:
            return [f"rows: {item} is in {row['part']}, and the rule puts {person} in {part}"]
    return []


@beartype
@require(lambda validation_share: 0 < validation_share < 1, "a share strictly between 0 and 1")
@ensure(lambda result: all(isinstance(line, str) and line for line in result), "lines in words")
def unit_problems(
    rows: Sequence[Mapping[str, object]],
    units: Mapping[str, Sequence[str]],
    salt: str,
    validation_share: float,
    test_persons: frozenset[str],
) -> list[str]:
    """What keeps a plan's rows from keeping each unit of probable repeat scans in one part: a row
    whose person is in a unit and whose part is not the one the rule gives the unit's key, so no
    patient's two scans sit in training and in validation as far as the units know (UNIT_LISTS).
    units maps each unit's key to its persons; a row in no unit is the rule's alone. Units that do
    not hold together, a key outside its own unit or a person in two, are a problem first, since
    either would leave a person's part to whichever unit came last."""
    unit_of: dict[str, str] = {}
    for key, persons in units.items():
        if key not in persons:
            return [f"units: the unit {key} does not hold its own key"]
        for person in persons:
            if person in unit_of:
                return [f"units: {person} is in two units, {unit_of[person]} and {key}"]
            unit_of[person] = key
    for row in rows:
        person = str(row.get("person"))
        unit = unit_of.get(person)
        if unit is None:
            continue
        part = rule_part(salt, validation_share, test_persons, unit)
        if row.get("part") != part:
            item, given = row.get("item"), row.get("part")
            where = f"is in the unit {unit}, whose part is {part}, not {given}"
            return [f"rows: {item}'s person {person} {where}"]
    return []


# --- the trials -----------------------------------------------------------------------------------


@beartype
@require(lambda batch: batch >= 1, "at least one spine a step")
@require(lambda train_rows: train_rows >= 0, "a count of rows")
@ensure(
    lambda result, train_rows, batch: (result - 1) * batch < train_rows <= result * batch,
    "ceil(rows / batch)",
)
def steps_per_epoch(train_rows: int, batch: int) -> int:
    """The steps an epoch takes: the training columns over the batch, rounded up, the definition
    the screen and the latent shape priors' plan agreed; the session draws whole spines batch at a
    time, so an epoch shows every column once in expectation. No rows take no steps, which
    plan_problems never lets a plan reach. The contracts below do not ask a plan for a training
    row, since CrossHair does not always build a plan holding one within its bound: the gate found
    total_steps' and trials' preconditions unmet under load on 2026-10-30."""
    return -(-train_rows // batch)


@beartype
@ensure(
    lambda result, plan: result == sum(1 for row in plan.rows if row.get("part") == "train"),
    "the train rows",
)
def train_count(plan: Plan) -> int:
    """How many rows the trials train on; a row that names no part, which plan_of never returns,
    is not one of them."""
    return sum(1 for row in plan.rows if row.get("part") == "train")


@beartype
@require(lambda plan: plan.batch >= 1 and plan.epochs >= 1, "a batch and epochs")
@ensure(
    lambda result, plan: result == plan.epochs * steps_per_epoch(train_count(plan), plan.batch),
    "epochs times an epoch's steps",
)
def total_steps(plan: Plan) -> int:
    """Every step a trial takes, which the anneal spans whole: epochs times an epoch's steps."""
    return plan.epochs * steps_per_epoch(train_count(plan), plan.batch)


@beartype
@ensure(lambda result, arm, seed: result == f"{arm}_s{seed}", "the arm and the seed")
def trial_id(arm: str, seed: int) -> str:
    """A trial's name: its arm and its seed."""
    return f"{arm}_s{seed}"


@beartype
@require(lambda plan: plan.batch >= 1 and plan.epochs >= 1, "a batch and epochs")
@require(lambda plan: len(set(plan.seeds)) == len(plan.seeds), "each seed once (plan_problems)")
@ensure(
    lambda result, plan: len(result) == len(plan.arms) * len(plan.seeds), "every arm at every seed"
)
@ensure(lambda result: [t.id for t in result] == sorted(t.id for t in result), "in a fixed order")
@ensure(lambda result: len({t.id for t in result}) == len(result), "no trial twice")
def trials(plan: Plan) -> list[TrialSpec]:
    """Every trial of the screen, in the order the array's task numbers count them: by arm, then
    by seed, so a task number names one trial on every node. A trial's words are the fixed words,
    its arm's, its seed, the plan's batch and the anneal spanning every step it takes."""
    steps = total_steps(plan)
    found = []
    for arm in sorted(plan.arms):
        for seed in sorted(plan.seeds):
            plan_words = (f"seed={seed}", f"batch={plan.batch}", f"anneal={steps}")
            words = (*plan.fixed, *plan.arms[arm], *plan_words)
            found.append(TrialSpec(trial_id(arm, seed), arm, seed, words))
    return sorted(found, key=lambda t: t.id)


@beartype
@ensure(lambda result, plan: all(isinstance(line, str) for line in result), "lines in words")
def task_problems(plan: Plan, task: int, tasks: int) -> list[str]:
    """What keeps an array task from naming one trial: a count other than the plan's trials, every
    arm at every seed as trials counts them, or a task outside it. The gate submits exactly that
    many tasks (grid/gate.sh counts the plan's arms and seeds the same way)."""
    count = len(plan.arms) * len(plan.seeds)
    if tasks != count:
        return [f"the array has {tasks} tasks and the plan {count} trials"]
    if not 0 <= task < count:
        return [f"task {task} is outside the array's 0 to {count - 1}"]
    return []


# --- the entries and the decision -----------------------------------------------------------------


def _is_measure(key: str, value: object) -> bool:
    """A measure an evaluation wrote: a finite number, or a null where it read nothing; the count
    of crops with no surface a whole number of at least 0."""
    if value is None:
        return True
    if key == "surface_missing":
        return _is_count(value, 0, MAX_ROWS * 64)
    return _is_finite(value)


def _point_problems(trial: str, record: object, epoch: int, per_epoch: int) -> list[str]:
    if type(record) is not dict or set(record) != set(EPOCH_KEYS):
        keys = ", ".join(EPOCH_KEYS)
        return [f"{trial}: the reading after epoch {epoch} holds {keys}, and nothing else"]
    if record["epoch"] != epoch or record["steps"] != epoch * per_epoch:
        named = f"epoch {record['epoch']!r} at {record['steps']!r} steps"
        return [f"{trial}: a reading names {named}, not epoch {epoch} at {epoch * per_epoch}"]
    if not all(_is_measure(key, record[key]) for key in ("loss", *MEASURE_KEYS)):
        return [f"{trial}: the reading after epoch {epoch} holds a measure no number and no null"]
    return []


def _epochs_problems(trial: str, points: object, plan: Plan) -> list[str]:
    expected = evaluation_epochs(plan)
    if type(points) is not list or len(points) != len(expected):
        return [f"{trial}: epochs holds a reading after each of epochs {_spelled(expected)}"]
    per_epoch = steps_per_epoch(train_count(plan), plan.batch)
    for record, epoch in zip(points, expected, strict=True):
        found = _point_problems(trial, record, epoch, per_epoch)
        if found:
            return found
    return []


def _spelled(epochs: Sequence[int]) -> str:
    """A list of epochs in words, shortened where it is long."""
    if len(epochs) <= 6:
        return ", ".join(str(e) for e in epochs)
    return f"{epochs[0]}, {epochs[1]}, ..., {epochs[-1]}"


def _final_problems(trial: str, final: object, points: Sequence[object]) -> list[str]:
    if type(final) is not dict or set(final) != set(FINAL_KEYS):
        return [f"{trial}: final holds {', '.join(FINAL_KEYS)}, and nothing else"]
    last = cast(Mapping[str, object], points[-1])
    if any(final[key] != last[key] for key in FINAL_KEYS):
        return [f"{trial}: final is not the reading after the last epoch"]
    return []


def _counts_problems(entry: Mapping[str, object], plan: Plan, trial: str) -> list[str]:
    reads = len(plan.rows) - train_count(plan)
    if entry["steps"] != total_steps(plan):
        return [f"{trial}: steps is the plan's {total_steps(plan)}, not {entry['steps']!r}"]
    if (entry["train_rows"], entry["validation_rows"]) != (train_count(plan), reads):
        return [f"{trial}: the entry trained on or read other rows than the plan's"]
    for key in ("seconds", "seconds_per_crop"):
        if not _is_finite(entry[key]) or cast(float, entry[key]) < 0:
            return [f"{trial}: {key} is a finite number of at least 0"]
    return []


@beartype
@require(lambda plan: 1 <= plan.evaluate_every <= plan.epochs, "readings within the epochs")
@ensure(lambda result, plan: result[-1] == plan.epochs, "the last epoch read")
@ensure(lambda result: result == sorted(set(result)), "each epoch once, in order")
@ensure(lambda result, plan: all(1 <= e <= plan.epochs for e in result), "within the epochs")
def evaluation_epochs(plan: Plan) -> list[int]:
    """The epochs after which a trial reads its validation CTs: every evaluate_every epochs, and
    the last epoch whatever evaluate_every says, so a trial's final reading is its last epoch's."""
    every = plan.evaluate_every
    return [e for e in range(1, plan.epochs + 1) if e % every == 0 or e == plan.epochs]


@beartype
@require(lambda plan: plan.batch >= 1 and plan.epochs >= 1, "a batch and epochs")
@require(lambda plan: 1 <= plan.evaluate_every <= plan.epochs, "readings within the epochs")
@ensure(lambda result: all(isinstance(line, str) and line for line in result), "lines in words")
def entry_problems(entry: object, trial: TrialSpec, plan: Plan) -> list[str]:
    """What keeps a trial's entry from being read by the join: its keys, its names and words
    against the trial it should be, its steps and rows against the plan's, a reading after each
    epoch evaluation_epochs names, every measure a finite number or a null, and the final measures
    the last reading's. An entry is read from JSON, which gives plain dicts and lists, so the reader
    takes those types exactly: a subclass may answer a lookup its own way, as the contracts gate's
    dict subclass did on 2026-10-30, raising where a plain dict reads."""
    if type(entry) is not dict or set(entry) != set(ENTRY_KEYS):
        return [f"{trial.id}: an entry holds {', '.join(ENTRY_KEYS)}, and nothing else"]
    if entry["version"] != ENTRY_VERSION or entry["screen"] != plan.screen:
        return [f"{trial.id}: an entry of version {ENTRY_VERSION} for the screen {plan.screen}"]
    if (entry["trial"], entry["arm"], entry["seed"]) != (trial.id, trial.arm, trial.seed):
        return [f"{trial.id}: the entry is the trial {entry['trial']!r}'s"]
    if entry["words"] != list(trial.words):
        return [f"{trial.id}: the entry trained under other words than the plan gives"]
    found = _counts_problems(entry, plan, trial.id)
    found = found or _epochs_problems(trial.id, entry["epochs"], plan)
    return found or _final_problems(trial.id, entry["final"], cast(list[object], entry["epochs"]))


def _final_of(entry: object, measure: str) -> float | None:
    """The entry's final value of the measure, or None where the trial wrote none."""
    if type(entry) is not dict:
        return None
    final = entry.get("final")
    if type(final) is not dict:
        return None
    value = final.get(measure)
    return float(cast(float, value)) if _is_finite(value) else None


def _verdict(
    arm_values: Sequence[float | None], null_values: Sequence[float | None]
) -> bool | None:
    """Whether every one of the arm's values is below every one of the null's; None where a value
    on either side is missing, since a failed trial decides nothing either way."""
    if any(v is None for v in arm_values) or any(v is None for v in null_values):
        return None
    return max(cast(Sequence[float], arm_values)) < min(cast(Sequence[float], null_values))


@beartype
@require(lambda plan: plan.batch >= 1 and plan.epochs >= 1, "a batch and epochs")
@require(lambda plan: plan.null in plan.arms and len(plan.seeds) >= 1, "the null an arm; a seed")
@require(lambda plan: len(set(plan.seeds)) == len(plan.seeds), "each seed once (plan_problems)")
@ensure(
    lambda result, plan: set(result["arms"]) == set(plan.arms) - {plan.null},
    "every arm but the null",
)
@ensure(
    lambda result: all(arm["beats_null"] in (True, False, None) for arm in result["arms"].values()),
    "a verdict or none for each arm",
)
def decide(plan: Plan, entries: Mapping[str, object]) -> dict[str, object]:
    """The join's decision: for each arm but the null, whether every seed's final value of the
    plan's measure is below every null seed's (the measure is a distance, so lower is better);
    None where a trial on either side has no final value, said in its why. entries maps a trial's
    id to the entry it wrote, a trial that wrote none being absent or None; an entry that does not
    hold should be refused before it reaches here (entry_problems)."""
    by_arm: dict[str, list[float | None]] = {}
    for trial in trials(plan):
        by_arm.setdefault(trial.arm, []).append(_final_of(entries.get(trial.id), plan.measure))
    null_values = by_arm[plan.null]
    arms: dict[str, dict[str, object]] = {}
    for arm in sorted(set(plan.arms) - {plan.null}):
        verdict = _verdict(by_arm[arm], null_values)
        why = {
            True: f"every seed of {arm} ends below every seed of {plan.null}",
            False: f"some seed of {arm} ends at or above some seed of {plan.null}",
            None: (
                f"a trial of {arm} or of {plan.null} wrote no final {plan.measure}, "
                "so nothing is decided"
            ),
        }[verdict]
        arms[arm] = {"finals": by_arm[arm], "beats_null": verdict, "why": why}
    return {
        "screen": plan.screen,
        "measure": plan.measure,
        "null": plan.null,
        "null_finals": null_values,
        "seeds": sorted(plan.seeds),
        "rule": (
            f"an arm beats {plan.null} when every one of its seeds' final validation "
            f"{plan.measure} is below every one of {plan.null}'s"
        ),
        "arms": arms,
    }
