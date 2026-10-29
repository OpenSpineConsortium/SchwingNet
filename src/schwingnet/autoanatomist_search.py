"""The auto-anatomist's search as pure logic: the plan, the split, the halving, the controller, the
objective and the ledger (docs/checkpoints/2026-10-29-autoanatomist-flow/HANDOFF.md, section 4).

The search is flows/autoanatomist.py, one launched flow run per controller round over bordercall's
auto-anatomist (grid/autoanatomist/, the pinned copy): a plan under grid/searches/ names the data,
the split, the block space, the rungs and the controller; each round samples trials from a factored
policy over the space, trains them rung by rung with successive halving on the validation objective,
rewards the controller and reads the test part once for the best trial. Everything the flow decides
is a function here, so that the gate proves it and the flow only carries it out: a plan that does
not hold is said in words (plan_problems), never guessed at; the split is the salted hash of
data/splits/rule.json's form, so a phantom or a person lands in one part whatever else is in the
plan; the halving keeps a fixed share by score; the reward is bodies named right less the weighted
landmark distance and the coverage's departure from its nominal, latency recorded and never
rewarded; the controller is REINFORCE on one categorical per block with an exponential-moving-
average baseline and an entropy floor; and the ledger, the one file a continued search reads, is
checked whole before a round builds on it.

Standard library with beartype and beethoven-qa's contracts, as the package's rules ask; nothing
here reads a file, renders a phantom or trains a network. A plan and a ledger are read as the JSON
they are, dicts and lists, so a mapping of another kind is refused rather than read. The bounds (a
reward within REWARD_BOUND, a learning rate at most LR_BOUND) are what keeps every sum here
finite, so the contracts can say so; a plan outside them is refused in words.
"""

import hashlib
import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import TypedDict, cast

from beartype import beartype
from beethoven_qa.contracts import ensure, require

LEDGER_VERSION = 1
ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_")
WORD_KEY_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz_")
JOB_CLASSES = ("batch", "gpu")
ROW_KINDS = ("phantom",)
PARTS = ("train", "validation", "test")
MAX_RUNGS = 3
HASH_SPAN = 2**64
# A reward, a baseline or a measure the contracts take, so that a mean or a weighted sum of them
# stays finite; and the largest learning rate, so that a step on the logits stays finite too.
REWARD_BOUND = 1e6
LR_BOUND = 1e3
# The keys a plan holds, every one required, so a plan is read the same way twice.
PLAN_KEYS = (
    "search",
    "class",
    "rows",
    "split",
    "space",
    "fixed",
    "seeds",
    "rungs",
    "keep",
    "trials",
    "controller",
    "objective",
    "latency_crops",
    "wandb_project",
)
SPLIT_KEYS = ("salt", "validation_share", "test_share")
CONTROLLER_KEYS = ("lr", "baseline_decay", "entropy_floor", "seed")
OBJECTIVE_KEYS = ("w_distance", "w_coverage")
LEDGER_KEYS = (
    "version",
    "search",
    "plan_sha256",
    "manifest",
    "policy",
    "baseline",
    "trials",
    "rounds",
    "best",
    "runs",
)
NO_DISTANCE = "no landmark distance measured (the evaluation gave none), so the trial has no reward"
NO_NAMING = (
    "no bodies named (the naming layer is off, or the spines hold unequal counts), "
    "counted as 0.0 named right"
)
NO_COVERAGE = "no coverage measured (no calibration was fit), counted as 0.0 coverage"

Scalar = str | int | float
Row = dict[str, Scalar]
Logits = dict[str, list[float]]
Pair = tuple[Sequence[str], float]


@dataclass(frozen=True)
class Split:
    """How the rows are dealt into parts: the salt and the shares, by the hash data/splits/rule.json
    names (the first 8 bytes, big-endian, of sha256 over 'schwingnet-split|<salt>|<person>')."""

    salt: str
    validation_share: float
    test_share: float


@dataclass(frozen=True)
class Controller:
    """REINFORCE's settings: the step on the logits, the baseline's decay, the floor under every
    value's probability, and the seed the round's draws come from."""

    lr: float
    baseline_decay: float
    entropy_floor: float
    seed: int


@dataclass(frozen=True)
class Objective:
    """The reward's weights: what a millimetre of landmark distance and a unit of coverage
    departure cost against a body named right."""

    w_distance: float
    w_coverage: float


@dataclass(frozen=True)
class Plan:
    """One search as its file holds it, every value typed and checked (plan_of)."""

    search: str
    job_class: str
    rows: tuple[Row, ...]
    split: Split
    space: dict[str, tuple[str, ...]]
    fixed: tuple[str, ...]
    seeds: tuple[tuple[str, ...], ...]
    rungs: tuple[int, ...]
    keep: float
    trials: int
    controller: Controller
    objective: Objective
    latency_crops: int
    wandb_project: str


@dataclass(frozen=True)
class Measures:
    """What a trial's evaluation on a part gives the objective, None where the evaluation lacks
    it; a trial with no distance has no reward (measure_notes says so)."""

    named_right: float | None
    distance_mm: float | None
    coverage_at_1: float | None


class ManifestRow(TypedDict):
    """One row of the plan with the part the split dealt it."""

    id: str
    part: str


class Rung(TypedDict):
    """One rung a trial finished: the steps it had trained by then, its validation measures
    and the reward they gave."""

    steps: int
    reward: float
    distance_mm: float
    named_right: float | None
    coverage_at_1: float | None
    sigma_mm: float | None


class Trial(TypedDict):
    """One configuration tried: its chosen words, the round that drew it, the rungs it finished,
    its latency a crop where it was measured, and the seconds it trained."""

    words: list[str]
    round: int
    rungs: list[Rung]
    latency_ms: float | None
    seconds: float


class RoundRecord(TypedDict):
    """One controller round: its number, the run that made it, its trials, what each rung kept,
    and the mean reward the controller was stepped by."""

    number: int
    run: str
    trials: list[str]
    kept: list[list[str]]
    mean_reward: float | None


class Best(TypedDict):
    """The best trial when the test part was last read for it: its id, its validation reward, its
    words, its measures on the test part (None where the part is empty), the part's rows and the
    run that read it."""

    id: str
    reward: float
    words: list[str]
    test: dict[str, float | None] | None
    test_rows: int
    run: str


class Ledger(TypedDict):
    """The one file a continued search reads (ledger_problems says what it holds). The flow reads
    it as JSON and passes the dict; the typed form is what new_ledger writes and what the keys
    mean."""

    version: int
    search: str
    plan_sha256: str
    manifest: list[ManifestRow]
    policy: Logits
    baseline: float | None
    trials: dict[str, Trial]
    rounds: list[RoundRecord]
    best: Best | None
    runs: list[str]


# --- names and words ------------------------------------------------------------------------------


def _is_id(text: object) -> bool:
    """A search's, a row's or a trial's name: lower-case letters, digits and _, 1 to 40 of them."""
    return isinstance(text, str) and 0 < len(text) <= 40 and set(text) <= ID_CHARS


def _is_number(value: object) -> bool:
    """A finite int or float that is not a bool; an int is finite however large, and asking
    math.isfinite of one beyond float's range raises instead of answering."""
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return isinstance(value, float) and math.isfinite(value)


def _is_share(value: object) -> bool:
    """A number strictly between 0 and 1."""
    return _is_number(value) and 0 < cast(float, value) < 1


def _is_count(value: object, low: int = 0) -> bool:
    """A whole number of at least low, never a bool."""
    return isinstance(value, int) and not isinstance(value, bool) and value >= low


def _is_weight(value: object) -> bool:
    """A finite number of at least 0."""
    return _is_number(value) and cast(float, value) >= 0


def _is_scalar(value: object) -> bool:
    """What a row's field holds: a string or a finite number, as JSON spells one."""
    return isinstance(value, str) or _is_number(value)


def _is_word(text: object) -> bool:
    """One block as the auto-anatomist spells it, KEY=VALUE, the key lower-case letters and _."""
    if not isinstance(text, str) or "=" not in text:
        return False
    key, value = text.split("=", 1)
    return bool(key) and set(key) <= WORD_KEY_CHARS and bool(value) and " " not in value


def _word_key(word: str) -> str:
    return word.split("=", 1)[0]


def _word_value(word: str) -> str:
    return word.split("=", 1)[1]


def _within(value: float) -> bool:
    """A number the contracts sum or weigh: finite and within REWARD_BOUND either way; an int is
    compared as it is, since math.isfinite of one beyond float's range raises."""
    if isinstance(value, int):
        return abs(value) <= REWARD_BOUND
    return math.isfinite(value) and abs(value) <= REWARD_BOUND


def _controller_holds(controller: Controller) -> bool:
    """The settings every step of the controller is proven under."""
    return (
        0 < controller.lr <= LR_BOUND
        and 0 < controller.baseline_decay < 1
        and 0 <= controller.entropy_floor < 0.5
    )


# --- the plan -------------------------------------------------------------------------------------


def _row_problems(row: object, seen: set[str]) -> list[str]:
    """What keeps one row of the plan from holding: its kind, its id and its values; the
    auto-anatomist reads the rest (autoanatomist.rows.canonical) when the row is rendered."""
    if not isinstance(row, dict):
        return [f"rows: {row!r} is not a row"]
    if row.get("kind") not in ROW_KINDS:
        return [f"rows: a row's kind is one of {', '.join(ROW_KINDS)}, not {row.get('kind')!r}"]
    identity = row.get("id")
    if not isinstance(identity, str) or not _is_id(identity):
        return [f"rows: a row's id is lower-case letters, digits and _, 1 to 40, not {identity!r}"]
    if identity in seen:
        return [f"rows: the id {identity} is listed twice"]
    seen.add(identity)
    if any(not _is_scalar(value) for value in row.values()):
        return [f"rows: {identity} holds a value that is no string and no finite number"]
    return []


def _split_problems(split: object) -> list[str]:
    if not isinstance(split, dict) or set(split) != set(SPLIT_KEYS):
        return [f"split: {', '.join(SPLIT_KEYS)}, and nothing else"]
    if not isinstance(split["salt"], str) or not split["salt"]:
        return ["split: the salt is a string that is not empty"]
    for name in ("validation_share", "test_share"):
        if not _is_share(split[name]):
            return [f"split: {name} is a share strictly between 0 and 1, not {split[name]!r}"]
    if split["validation_share"] + split["test_share"] >= 1:
        return ["split: the validation and test shares leave nothing to train on"]
    return []


def _values_problems(key: object, values: object) -> list[str]:
    """What keeps one block of the space from holding: its name and its values."""
    if not isinstance(key, str) or not key or not set(key) <= WORD_KEY_CHARS:
        return [f"space: a block's name is lower-case letters and _, not {key!r}"]
    if not isinstance(values, list) or len(values) < 2:
        return [f"space: the block {key} needs at least two values to choose from"]
    if any(not isinstance(v, str) or not v or " " in v or "=" in v for v in values):
        return [f"space: the values of {key} are words without spaces or =, not {values!r}"]
    if len(set(values)) != len(values):
        return [f"space: the block {key} lists a value twice"]
    return []


def _space_problems(space: object) -> list[str]:
    if not isinstance(space, dict) or not space:
        return ["space: at least one block, each with the values the controller may choose"]
    for key, values in space.items():
        found = _values_problems(key, values)
        if found:
            return found
    return []


def _words_problems(what: str, words: object, space: Mapping[str, object]) -> list[str]:
    """What keeps the fixed words from holding: each a block word, none a block of the space."""
    if not isinstance(words, list):
        return [f"{what}: a list of KEY=VALUE words"]
    for word in words:
        if not _is_word(word):
            return [f"{what}: {word!r} is not a KEY=VALUE word"]
        if _word_key(word) in space:
            return [
                f"{what}: {_word_key(word)} is a block of the space, which the controller chooses"
            ]
    keys = [_word_key(w) for w in words]
    if len(set(keys)) != len(keys):
        return [f"{what}: a block is named twice"]
    return []


def _seed_problems(seeds: object, space: Mapping[str, object]) -> list[str]:
    """What keeps the round-0 seeds from holding: each one value of every block of the space."""
    if not isinstance(seeds, list):
        return ["seeds: a list of configurations, each one value of every block of the space"]
    blocks = ", ".join(sorted(space))
    for seed in seeds:
        if not isinstance(seed, dict) or set(seed) != set(space):
            return [f"seeds: each seed names every block of the space ({blocks}) and no other"]
        for key, value in seed.items():
            if value not in cast(Sequence[str], space[key]):
                return [f"seeds: {key}={value!r} is not a value of the space"]
    return []


def _rung_problems(rungs: object) -> list[str]:
    if not isinstance(rungs, list) or not 1 <= len(rungs) <= MAX_RUNGS:
        return [f"rungs: 1 to {MAX_RUNGS} step counts, each the steps a trial has trained by it"]
    rising = all(b > a for a, b in zip(rungs, rungs[1:], strict=False))
    if any(not _is_count(r, 1) for r in rungs) or not rising:
        return ["rungs: whole numbers of at least 1, each above the one before"]
    return []


def _controller_problems(controller: object) -> list[str]:
    if not isinstance(controller, dict) or set(controller) != set(CONTROLLER_KEYS):
        return [f"controller: {', '.join(CONTROLLER_KEYS)}, and nothing else"]
    if not _is_number(controller["lr"]) or not 0 < controller["lr"] <= LR_BOUND:
        return [f"controller: lr is a number above 0 and at most {LR_BOUND:g}"]
    if not _is_share(controller["baseline_decay"]):
        return ["controller: baseline_decay is a share strictly between 0 and 1"]
    if not _is_share(controller["entropy_floor"]) or controller["entropy_floor"] >= 0.5:
        return ["controller: entropy_floor is a share strictly between 0 and 0.5"]
    if not _is_count(controller["seed"]):
        return ["controller: the seed is a whole number of at least 0"]
    return []


def _objective_problems(objective: object) -> list[str]:
    if not isinstance(objective, dict) or set(objective) != set(OBJECTIVE_KEYS):
        return [f"objective: {', '.join(OBJECTIVE_KEYS)}, and nothing else"]
    weights = [objective[k] for k in OBJECTIVE_KEYS]
    if any(not _is_weight(w) or w > REWARD_BOUND for w in weights):
        return [f"objective: the weights are numbers from 0 to {REWARD_BOUND:g}"]
    return []


def _mapping_at(record: Mapping[str, object], key: str) -> Mapping[str, object]:
    """The dict a key holds, read after the key's own check (an empty one where it holds none)."""
    value = record[key]
    return value if isinstance(value, dict) else {}


def _list_at(record: Mapping[str, object], key: str) -> list[object]:
    """The list a key holds, read after the key's own check (an empty one where it holds none)."""
    value = record[key]
    return value if isinstance(value, list) else []


def _head_problems(record: Mapping[str, object]) -> list[str]:
    if not _is_id(record["search"]):
        return ["search: lower-case letters, digits and _, 1 to 40 of them"]
    if record["class"] not in JOB_CLASSES:
        return [f"class: one of {', '.join(JOB_CLASSES)}"]
    rows = record["rows"]
    if not isinstance(rows, list) or len(rows) < 3:
        return ["rows: at least three rows, so that each part can hold one"]
    seen: set[str] = set()
    for row in rows:
        found = _row_problems(row, seen)
        if found:
            return found
    return []


def _parts_problems(record: Mapping[str, object]) -> list[str]:
    return _split_problems(record["split"]) or _space_problems(record["space"])


def _choice_problems(record: Mapping[str, object]) -> list[str]:
    space = _mapping_at(record, "space")
    return (
        _words_problems("fixed", record["fixed"], space)
        or _seed_problems(record["seeds"], space)
        or _rung_problems(record["rungs"])
        or _controller_problems(record["controller"])
        or _objective_problems(record["objective"])
    )


def _tail_problems(record: Mapping[str, object]) -> list[str]:
    if not _is_share(record["keep"]):
        return ["keep: the share of trials kept at each rung, strictly between 0 and 1"]
    if not _is_count(record["trials"], 2):
        return ["trials: at least 2 a round"]
    if len(_list_at(record, "seeds")) > cast(int, record["trials"]):
        return ["seeds: no more seeds than trials a round"]
    if not _is_count(record["latency_crops"], 1):
        return ["latency_crops: a whole number of at least 1"]
    if not isinstance(record["wandb_project"], str) or not record["wandb_project"]:
        return ["wandb_project: a name that is not empty"]
    return []


@beartype
@ensure(
    lambda result, record: bool(result) or all(k in record for k in PLAN_KEYS),
    "no problem only where every key is there",
)
@ensure(lambda result: all(line for line in result), "each problem said in words")
def plan_problems(record: object) -> list[str]:
    """What keeps a plan file from holding, one line each; none where it holds. Said in words so
    the flow and the gate word refuse before anything runs, and so a plan is never read two ways."""
    if not isinstance(record, dict):
        return ["a plan is a JSON object"]
    missing = [k for k in PLAN_KEYS if k not in record]
    extra = sorted(str(k) for k in record if k not in PLAN_KEYS)
    if missing or extra:
        keys = ", ".join(PLAN_KEYS)
        lost, odd = ", ".join(missing) or "none", ", ".join(extra) or "none"
        return [f"a plan holds {keys}: missing {lost}, unknown {odd}"]
    found: list[str] = []
    for check in (_head_problems, _parts_problems, _choice_problems, _tail_problems):
        found = found or check(record)
    return found


def _number(value: object) -> float:
    """A JSON number a check has already seen, as a float."""
    return float(cast(float, value))


def _split_of(split: Mapping[str, object]) -> Split:
    return Split(
        str(split["salt"]), _number(split["validation_share"]), _number(split["test_share"])
    )


def _controller_of(controller: Mapping[str, object]) -> Controller:
    return Controller(
        _number(controller["lr"]),
        _number(controller["baseline_decay"]),
        _number(controller["entropy_floor"]),
        int(_number(controller["seed"])),
    )


@beartype
@require(lambda record: not plan_problems(record), "a plan that holds (plan_problems)")
@ensure(
    lambda result, record: (
        result.search == record["search"]
        and len(result.rows) == len(record["rows"])
        and set(result.space) == set(record["space"])
    ),
    "the plan read whole",
)
def plan_of(record: Mapping[str, object]) -> Plan:
    """The plan a file holds, typed, from a record plan_problems finds nothing wrong with."""
    space_in = cast(Mapping[str, Sequence[str]], record["space"])
    space = {key: tuple(values) for key, values in space_in.items()}
    seeds_in = cast(Sequence[Mapping[str, str]], record["seeds"])
    objective = cast(Mapping[str, float], record["objective"])
    return Plan(
        search=str(record["search"]),
        job_class=str(record["class"]),
        rows=tuple(dict(row) for row in cast(Sequence[Row], record["rows"])),
        split=_split_of(_mapping_at(record, "split")),
        space=space,
        fixed=tuple(cast(Sequence[str], record["fixed"])),
        seeds=tuple(tuple(f"{key}={seed[key]}" for key in sorted(space)) for seed in seeds_in),
        rungs=tuple(int(r) for r in cast(Sequence[int], record["rungs"])),
        keep=_number(record["keep"]),
        trials=int(_number(record["trials"])),
        controller=_controller_of(_mapping_at(record, "controller")),
        objective=Objective(_number(objective["w_distance"]), _number(objective["w_coverage"])),
        latency_crops=int(_number(record["latency_crops"])),
        wandb_project=str(record["wandb_project"]),
    )


@beartype
@ensure(lambda result, plan: result["search"] == plan.search, "the plan's own name")
def as_record(plan: Plan) -> dict[str, object]:
    """The plan as plain JSON, for the ledger's page and the run's record."""
    return asdict(plan)


# --- the split ------------------------------------------------------------------------------------


@beartype
@ensure(lambda result: 0 <= result < HASH_SPAN, "a 64-bit value")
def hash_value(salt: str, person: str) -> int:
    """data/splits/rule.json's hash: the first 8 bytes, big-endian, of sha256 over the UTF-8 of
    'schwingnet-split|' + salt + '|' + person, so a person's part never depends on the other
    rows."""
    text = f"schwingnet-split|{salt}|{person}".encode()
    return int.from_bytes(hashlib.sha256(text).digest()[:8], "big")


@beartype
@ensure(lambda result: result in PARTS, "one of the three parts")
def part_of(split: Split, person: str) -> str:
    """validation where the hash is below the validation share, test where it is below the two
    shares together, train otherwise: the rule's form with a test share by hash, since a phantom
    has no frozen test list and is its own person."""
    value = hash_value(split.salt, person) / HASH_SPAN
    if value < split.validation_share:
        return "validation"
    if value < split.validation_share + split.test_share:
        return "test"
    return "train"


@beartype
@require(lambda rows: all("id" in row for row in rows), "rows with ids")
@ensure(
    lambda result, rows: [row["id"] for row in result] == [str(row["id"]) for row in rows],
    "every row, in order",
)
@ensure(lambda result: all(row["part"] in PARTS for row in result), "each in a part")
def manifest_of(rows: Sequence[Mapping[str, Scalar]], split: Split) -> list[ManifestRow]:
    """The manifest: each row's id and part, in the plan's order; a row's person is its id."""
    return [{"id": str(row["id"]), "part": part_of(split, str(row["id"]))} for row in rows]


@beartype
@ensure(
    lambda result, manifest, part: result == [r["id"] for r in manifest if r["part"] == part],
    "the ids of that part, in the manifest's order",
)
def part_ids(manifest: Sequence[ManifestRow], part: str) -> list[str]:
    """The rows a part holds, in the manifest's order."""
    return [row["id"] for row in manifest if row["part"] == part]


@beartype
@ensure(
    lambda result, manifest: (
        bool(result) == (not part_ids(manifest, "train") or not part_ids(manifest, "validation"))
    ),
    "a problem exactly where a part trained or validated on is empty",
)
def manifest_problems(manifest: Sequence[ManifestRow]) -> list[str]:
    """What keeps a manifest from training: a train or a validation part with no row. The test
    part may be empty, in which case the best trial's test reading is recorded as none."""
    return [
        f"the {part} part holds no row: more rows, or other shares, before any trial trains"
        for part in ("train", "validation")
        if not part_ids(manifest, part)
    ]


# --- the halving ----------------------------------------------------------------------------------


@beartype
@require(lambda share: 0 < share < 1, "a share strictly between 0 and 1")
@require(lambda scores: all(math.isfinite(v) for v in scores.values()), "finite scores")
@ensure(
    lambda result, scores: (
        set(result) <= set(scores) and (not scores or 1 <= len(result) <= len(scores))
    ),
    "kept trials among the scored, at least one",
)
@ensure(lambda result: result == sorted(result), "in a fixed order")
def kept(scores: Mapping[str, float], share: float) -> list[str]:
    """The trials that go on to the next rung: the highest-scoring share of them, rounded up, at
    least one, ties broken by id so two runs keep the same trials."""
    if not scores:
        return []
    count = max(1, math.ceil(len(scores) * share))
    order = sorted(scores, key=lambda trial: (-scores[trial], trial))
    return sorted(order[:count])


# --- the objective --------------------------------------------------------------------------------


def _number_or_none(value: object) -> float | None:
    return float(cast(float, value)) if _is_number(value) else None


@beartype
@ensure(
    lambda result, evaluation: result.distance_mm == _number_or_none(evaluation.get("distance_mm")),
    "the distance as the evaluation gave it, or none",
)
def measures_of(evaluation: Mapping[str, object]) -> Measures:
    """What the objective reads of a session's evaluate: the share named right, the landmark
    distance and the coverage at one calibrated spread, each None where the evaluation lacks it
    or gives no finite number."""
    return Measures(
        named_right=_number_or_none(evaluation.get("named_right")),
        distance_mm=_number_or_none(evaluation.get("distance_mm")),
        coverage_at_1=_number_or_none(evaluation.get("coverage_at_1")),
    )


@beartype
@ensure(
    lambda result, measures: (
        len(result)
        == (measures.distance_mm is None)
        + (measures.named_right is None)
        + (measures.coverage_at_1 is None)
    ),
    "one note a measure the reward lacked",
)
def measure_notes(measures: Measures) -> list[str]:
    """What the reward counted as 0 for want of a number, or what keeps it from being given at
    all, said beside it."""
    lacking = (
        (measures.distance_mm, NO_DISTANCE),
        (measures.named_right, NO_NAMING),
        (measures.coverage_at_1, NO_COVERAGE),
    )
    return [note for value, note in lacking if value is None]


def _measures_within(measures: Measures) -> bool:
    return all(
        value is None or _within(value)
        for value in (measures.named_right, measures.distance_mm, measures.coverage_at_1)
    )


@beartype
@require(lambda measures: measures.distance_mm is not None, "a landmark distance to score")
@require(lambda measures: _measures_within(measures), "measures within the bound")
@require(
    lambda objective: _within(objective.w_distance) and _within(objective.w_coverage),
    "weights within the bound",
)
@require(lambda nominal_coverage: 0 < nominal_coverage < 1, "a nominal coverage between 0 and 1")
@ensure(lambda result: math.isfinite(result), "a finite reward")
def reward(measures: Measures, objective: Objective, nominal_coverage: float) -> float:
    """Bodies named right (a share, 0 where none were named) less w_distance times the landmark
    distance in millimetres, less w_coverage times how far the coverage at one calibrated spread
    sits from its nominal (the whole nominal where no coverage was measured); latency is never in
    it."""
    named = measures.named_right or 0.0
    coverage = measures.coverage_at_1 or 0.0
    distance = measures.distance_mm or 0.0
    departure = abs(coverage - nominal_coverage)
    return named - objective.w_distance * distance - objective.w_coverage * departure


@beartype
@require(lambda words: all(_is_word(w) for w in words), "block words")
@require(lambda default: 0 < default < 1, "a default coverage between 0 and 1")
@ensure(lambda result: 0 < result < 1, "a coverage strictly between 0 and 1")
def nominal_coverage_of(words: Sequence[str], default: float = 0.68) -> float:
    """The coverage the trial's quantile calibration aims at, from its coverage word, else the
    auto-anatomist's default."""
    for word in words:
        if _word_key(word) == "coverage":
            value = _parsed(_word_value(word))
            if value is not None and 0 < value < 1:
                return value
    return default


def _parsed(text: str) -> float | None:
    try:
        value = float(text)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


# --- the controller -------------------------------------------------------------------------------


@beartype
@ensure(
    lambda result, logits, space: not result or set(logits) == set(space),
    "fits only over the same blocks",
)
def policy_fits(logits: Mapping[str, Sequence[float]], space: Mapping[str, Sequence[str]]) -> bool:
    """Whether a policy is over the space: one finite logit a value of every block, at least one
    value a block, and no other block."""
    return set(logits) == set(space) and all(
        len(logits[key]) == len(space[key]) >= 1 and all(math.isfinite(v) for v in logits[key])
        for key in space
    )


@beartype
@ensure(
    lambda result, space: (
        set(result) == set(space) and all(result[k] == [0.0] * len(space[k]) for k in space)
    ),
    "a zero logit a value",
)
def uniform_policy(space: Mapping[str, Sequence[str]]) -> Logits:
    """Round 0's policy: every value of every block as likely as the others."""
    return {key: [0.0] * len(values) for key, values in space.items()}


@beartype
@require(
    lambda logits: len(logits) >= 1 and all(math.isfinite(v) for v in logits),
    "finite logits, at least one",
)
@require(lambda floor: 0 <= floor < 0.5, "a floor below one half")
@ensure(
    lambda result, logits: len(result) == len(logits) and abs(sum(result) - 1.0) < 1e-9,
    "a distribution",
)
@ensure(
    lambda result, logits, floor: all(p >= floor / len(logits) - 1e-12 for p in result),
    "no value below the floor's share",
)
def probabilities(logits: Sequence[float], floor: float) -> list[float]:
    """The softmax of the logits, mixed with the uniform by the floor, so no value is ever certain
    and every value is drawn now and then."""
    top = max(logits)
    weights = [math.exp(v - top) for v in logits]
    total = sum(weights)
    return [(1.0 - floor) * w / total + floor / len(logits) for w in weights]


@beartype
@require(lambda logits, plan: policy_fits(logits, plan.space), "a policy over the plan's space")
@require(lambda plan: _controller_holds(plan.controller), "a controller within its bounds")
@require(lambda count: count >= 0, "a count")
@ensure(lambda result, count: len(result) == count, "one configuration a draw")
@ensure(
    lambda result, plan: all(len(words) == len(plan.space) for words in result),
    "every block chosen",
)
def sample(
    logits: Mapping[str, Sequence[float]], plan: Plan, count: int, seed: int
) -> list[tuple[str, ...]]:
    """count configurations drawn from the policy, block by block, by Python's own generator from
    the seed, so a round drawn twice is the same round; each a tuple of KEY=VALUE words in the
    blocks' sorted order."""
    draw = random.Random(seed)
    found = []
    for _ in range(count):
        words = []
        for key in sorted(plan.space):
            weights = probabilities(logits[key], plan.controller.entropy_floor)
            words.append(f"{key}={draw.choices(list(plan.space[key]), weights=weights, k=1)[0]}")
        found.append(tuple(words))
    return found


@beartype
@require(lambda logits, plan: policy_fits(logits, plan.space), "a policy over the plan's space")
@require(lambda plan: _controller_holds(plan.controller), "a controller within its bounds")
@require(lambda advantage: _within(advantage), "an advantage within the bound")
@ensure(
    lambda result, logits: (
        set(result) == set(logits) and all(len(result[k]) == len(logits[k]) for k in logits)
    ),
    "the same blocks and values",
)
def stepped(
    logits: Mapping[str, Sequence[float]], plan: Plan, words: Sequence[str], advantage: float
) -> Logits:
    """One REINFORCE step: for each block the words choose a value of, the chosen value's logit
    rises by lr times the advantage times one less its probability, and every other value's falls
    by lr times the advantage times its probability, the gradient of the log probability of the
    choice; a block the words leave unchosen is left as it is."""
    chosen = {_word_key(w): _word_value(w) for w in words if "=" in w}
    out: Logits = {}
    for key, block in logits.items():
        values = list(plan.space[key])
        if chosen.get(key) not in values:
            out[key] = list(block)
            continue
        picked = values.index(chosen[key])
        step = plan.controller.lr * advantage
        probs = probabilities(block, plan.controller.entropy_floor)
        pairs = enumerate(zip(block, probs, strict=True))
        out[key] = [v + step * ((1.0 if i == picked else 0.0) - p) for i, (v, p) in pairs]
    return out


@beartype
@require(lambda logits, plan: policy_fits(logits, plan.space), "a policy over the plan's space")
@require(lambda plan: _controller_holds(plan.controller), "a controller within its bounds")
@require(lambda pairs: all(_within(r) for _, r in pairs), "rewards within the bound")
@require(lambda baseline: baseline is None or _within(baseline), "a baseline within the bound")
@ensure(
    lambda result, logits: (
        set(result[0]) == set(logits) and (result[1] is None or _within(result[1]))
    ),
    "the policy over the same blocks and a baseline within the bound",
)
def updated(
    logits: Mapping[str, Sequence[float]], plan: Plan, pairs: Sequence[Pair], baseline: float | None
) -> tuple[Logits, float | None]:
    """The policy after a round's (configuration, reward) pairs, each stepped against the baseline
    before the round, and the baseline moved toward the round's mean reward by one minus the decay;
    the first round sets the baseline to its mean, since there is nothing to average with. No pair
    leaves both as they were."""
    if not pairs:
        return {key: list(v) for key, v in logits.items()}, baseline
    mean = sum(r for _, r in pairs) / len(pairs)
    before = mean if baseline is None else baseline
    policy: Logits = {key: list(v) for key, v in logits.items()}
    for words, value in pairs:
        policy = stepped(policy, plan, words, value - before)
    decay = plan.controller.baseline_decay
    return policy, mean if baseline is None else decay * baseline + (1.0 - decay) * mean


# --- the trials -----------------------------------------------------------------------------------


@beartype
@ensure(lambda result: len(result) == 64 and set(result) <= set("0123456789abcdef"), "a sha256")
def words_digest(words: Sequence[str]) -> str:
    """The configuration's name: sha256 over its words, sorted, one a line."""
    return hashlib.sha256(("\n".join(sorted(words)) + "\n").encode()).hexdigest()


@beartype
@require(lambda round_number, index: round_number >= 0 and index >= 0, "a round and a place in it")
@ensure(lambda result: _is_id(result), "an id the gate and the folders take")
def trial_id(round_number: int, index: int, words: Sequence[str]) -> str:
    """r<round>t<index>_<8 hex of the words' digest>: readable in a folder listing, unique in a
    search as long as a round draws no configuration twice."""
    return f"r{round_number:02d}t{index:02d}_{words_digest(words)[:8]}"


@beartype
@require(lambda plan: len(plan.rungs) >= 1, "a plan with rungs")
@ensure(
    lambda result, plan: len(result) == len(plan.rungs) and sum(result) == plan.rungs[-1],
    "the steps of each rung, summing to the last",
)
def rung_steps(plan: Plan) -> list[int]:
    """The steps a trial trains at each rung: the rungs are cumulative, so each rung trains the
    difference from the one before."""
    return [b - a for a, b in zip((0, *plan.rungs), plan.rungs, strict=False)]


@beartype
@require(lambda logits, plan: policy_fits(logits, plan.space), "a policy over the plan's space")
@require(lambda plan: _controller_holds(plan.controller), "a controller within its bounds")
@require(lambda plan: len(plan.seeds) <= plan.trials, "no more seeds than trials")
@require(lambda round_number: round_number >= 0, "a round")
@ensure(lambda result, plan: len(result) == plan.trials, "one configuration a trial")
def round_configurations(
    plan: Plan, logits: Mapping[str, Sequence[float]], round_number: int
) -> list[tuple[str, ...]]:
    """The round's configurations: round 0 starts from the plan's seeds and draws the rest; a later
    round draws every trial from the policy. The draw's seed is the controller's and the round's."""
    given = list(plan.seeds) if round_number == 0 else []
    seed = plan.controller.seed * 1000 + round_number
    return given + sample(logits, plan, plan.trials - len(given), seed)


@beartype
@ensure(
    lambda result, plan, words: result == [*plan.fixed, *words], "the fixed words, then the chosen"
)
def trial_words(plan: Plan, words: Sequence[str]) -> list[str]:
    """What the session is built from: the plan's fixed words, then the trial's chosen ones, so a
    chosen block never overrides a fixed one by order alone (plan_problems keeps them apart)."""
    return [*plan.fixed, *words]


# --- the ledger -----------------------------------------------------------------------------------


def _manifest_holds(value: object) -> bool:
    return isinstance(value, list) and all(
        isinstance(row, dict) and isinstance(row.get("id"), str) and row.get("part") in PARTS
        for row in value
    )


def _logits_hold(value: object) -> bool:
    return isinstance(value, list) and all(_is_number(x) for x in value)


def _policy_holds(value: object) -> bool:
    return isinstance(value, dict) and all(_logits_hold(v) for v in value.values())


def _trials_hold(value: object) -> bool:
    return isinstance(value, dict) and all(isinstance(t, dict) for t in value.values())


def _ledger_key_problems(ledger: Mapping[str, object]) -> list[str]:
    if ledger.get("version") != LEDGER_VERSION:
        return [
            f"the ledger's version is {ledger.get('version')!r}; this code reads {LEDGER_VERSION}"
        ]
    missing = [k for k in LEDGER_KEYS if k not in ledger]
    if missing:
        return [f"the ledger lacks {', '.join(missing)}"]
    return []


def _ledger_value_problems(ledger: Mapping[str, object]) -> list[str]:
    if not _is_id(ledger["search"]) or not isinstance(ledger["plan_sha256"], str):
        return ["the ledger's search is no id, or its plan's sha256 no string"]
    if not _manifest_holds(ledger["manifest"]):
        return ["the ledger's manifest is a list of rows, each with its id and its part"]
    if not _policy_holds(ledger["policy"]):
        return ["the ledger's policy is one list of finite logits a block"]
    if ledger["baseline"] is not None and not _is_number(ledger["baseline"]):
        return ["the ledger's baseline is a finite number, or null before the first round"]
    lists = all(isinstance(ledger[k], list) for k in ("rounds", "runs"))
    if not _trials_hold(ledger["trials"]) or not lists:
        return ["the ledger's trials are a mapping by id, each a record; its rounds and runs lists"]
    if ledger["best"] is not None and not isinstance(ledger["best"], dict):
        return ["the ledger's best is a record, or null before a test reading"]
    return []


@beartype
@ensure(
    lambda result, ledger: bool(result) or all(k in ledger for k in LEDGER_KEYS),
    "no problem only where every key is there",
)
@ensure(lambda result: all(line for line in result), "each problem said in words")
def ledger_problems(ledger: object) -> list[str]:
    """What keeps a ledger from being read: its version, its keys and the shapes a round builds on.
    A continued search reads nothing of a ledger that does not hold."""
    if not isinstance(ledger, dict):
        return ["a ledger is a JSON object"]
    return _ledger_key_problems(ledger) or _ledger_value_problems(ledger)


@beartype
@require(lambda plan: _is_id(plan.search), "a plan with a name")
@require(
    lambda manifest: all("id" in row and row.get("part") in PARTS for row in manifest),
    "a manifest of rows in parts",
)
@ensure(lambda result: not ledger_problems(result), "a ledger that holds")
def new_ledger(plan: Plan, plan_sha256: str, manifest: Sequence[Mapping[str, str]]) -> Ledger:
    """The ledger before any round: the plan's name and sha256, the manifest with each row's part,
    the uniform policy, no baseline, no trial, no round, no best, no run."""
    return {
        "version": LEDGER_VERSION,
        "search": plan.search,
        "plan_sha256": plan_sha256,
        "manifest": [{"id": row["id"], "part": row["part"]} for row in manifest],
        "policy": uniform_policy(plan.space),
        "baseline": None,
        "trials": {},
        "rounds": [],
        "best": None,
        "runs": [],
    }


def _policy_over(logits: Mapping[str, Sequence[float]], space: Mapping[str, Sequence[str]]) -> bool:
    """Whether a policy has the space's blocks with the space's counts of values."""
    return set(logits) == set(space) and all(len(logits[k]) == len(space[k]) for k in space)


@beartype
@ensure(
    lambda result, ledger, plan, plan_sha256: (
        bool(result)
        or (ledger.get("search") == plan.search and ledger.get("plan_sha256") == plan_sha256)
    ),
    "no problem only where the name and the bytes agree",
)
@ensure(lambda result: len(result) <= 3 and all(line for line in result), "at most three, in words")
def ledger_fits(ledger: Mapping[str, object], plan: Plan, plan_sha256: str) -> list[str]:
    """What keeps a ledger from carrying this plan on: another search, another plan's bytes, or a
    policy over other blocks. A plan that changed is another design (the PREREG covers the plan's
    bytes), so a continued search never mixes two. Read after ledger_problems found nothing."""
    found = []
    if ledger.get("search") != plan.search:
        found.append(
            f"the ledger is the search {ledger.get('search')}'s, and the plan is {plan.search}"
        )
    if ledger.get("plan_sha256") != plan_sha256:
        was, now = str(ledger.get("plan_sha256"))[:16], plan_sha256[:16]
        found.append(
            f"the ledger was begun under the plan of sha256 {was}, and this plan's is {now}"
        )
    policy = ledger.get("policy")
    if not _policy_holds(policy) or not _policy_over(cast(Logits, policy), plan.space):
        found.append("the ledger's policy is over other blocks or values than the plan's space")
    return found


@beartype
@ensure(
    lambda result, trials: set(result) <= set(trials) and all(_within(v) for v in result.values()),
    "a reward within the bound for some of the trials",
)
def last_rewards(trials: Mapping[str, object]) -> dict[str, float]:
    """Each trial's validation reward at the last rung it finished; a trial that is no record,
    with no rung finished, or whose last rung carries no reward within the bound, has none."""
    found = {}
    for name, trial in trials.items():
        rungs = trial.get("rungs") if isinstance(trial, dict) else None
        if not isinstance(rungs, list) or not rungs or not isinstance(rungs[-1], dict):
            continue
        value = rungs[-1].get("reward")
        if _is_number(value) and _within(cast(float, value)):
            found[name] = float(cast(float, value))
    return found


@beartype
@require(lambda scores: all(math.isfinite(v) for v in scores.values()), "finite scores")
@ensure(lambda result, scores: (result is None) == (not scores), "none only with no score")
@ensure(
    lambda result, scores: result is None or all(scores[result] >= v for v in scores.values()),
    "the highest score",
)
def best_trial(scores: Mapping[str, float]) -> str | None:
    """The trial with the highest score, ties by id; None with no trial scored."""
    if not scores:
        return None
    return min(scores, key=lambda name: (-scores[name], name))


def _best_lines(best: Mapping[str, object]) -> list[str]:
    """The best trial's lines: its validation reward and its words, then its test reading."""
    words = best.get("words")
    blocks = " ".join(str(w) for w in words) if isinstance(words, list) else "none"
    value = best.get("reward")
    shown = f"{cast(float, value):.4f}" if _is_number(value) else repr(value)
    lines = [f"best {best.get('id')}: validation reward {shown}, blocks {blocks}"]
    test = best.get("test")
    if test is None:
        lines.append(f"test: no row in the test part, so nothing was read for {best.get('id')}")
    elif isinstance(test, dict):
        numbers = ", ".join(
            f"{key} {cast(float, number):.3f}" if _is_number(number) else f"{key} none"
            for key, number in sorted(test.items(), key=lambda item: str(item[0]))
        )
        lines.append(f"test ({best.get('test_rows')} rows): {numbers}")
    return lines


@beartype
@ensure(lambda result: len(result) >= 2, "the search's line and the parts' line at least")
def summary_lines(ledger: Mapping[str, object]) -> list[str]:
    """The ledger in a few lines, for the page and the job's report; a ledger that does not hold
    is summarised as far as it reads."""
    trials, rounds, manifest = ledger.get("trials"), ledger.get("rounds"), ledger.get("manifest")
    count = len(trials) if isinstance(trials, dict) else 0
    # only the trials named by a string are read, since last_rewards takes no other key
    items = trials.items() if isinstance(trials, dict) else []
    named = {k: v for k, v in items if isinstance(k, str)}
    scored = len(last_rewards(named))
    rows = cast(list[ManifestRow], manifest) if _manifest_holds(manifest) else []
    parts = ", ".join(f"{part} {len(part_ids(rows, part))}" for part in PARTS)
    made = len(rounds) if isinstance(rounds, list) else 0
    lines = [
        f"search {ledger.get('search')}: {made} rounds, {count} trials, "
        f"{scored} with a rung scored",
        f"parts: {parts}",
    ]
    best = ledger.get("best")
    if isinstance(best, dict):
        lines.extend(_best_lines(best))
    return lines
