"""The trainer's building blocks: each way of doing one part of training, chosen by name.

The owner's ask of 2026-10-24: build what the training review found as pieces that can be swapped,
so a better way of doing one part replaces that part and nothing else. A run names one choice per
part (docs/research/training-review.md, section 1):

- normalise: how a crop is scaled before the network, "none" (grey 0..1, as version 1 trained)
  or "imagenet" (ImageNet's mean and spread, which the ImageNet weights were trained on);
- augment: which training-time changes a batch gets, any of "box-jitter" (the box moved and
  resized a little, as a tracker's or detector's box is), "intensity" (gamma, contrast,
  brightness), "blur", "noise" (dose-like) and "strong" (SyntheX's strong domain randomisation,
  up to two of its heavy image changes a crop, with the ones FluoroSAM adds), in that order, or
  none;
- optimiser: "adam" or "adamw", with weight_decay, and backbone_lr_scale for the pretrained
  layers' rate beside the new head's;
- schedule: "constant" or "cosine", after warmup_epochs of a linear warm-up;
- sampler: "uniform" (every crop once an epoch) or "balanced" (drawn so every level present is
  as likely as any other);
- loss_weights: "none" or "inverse-frequency" over the levels the training part holds;
- select: what chooses the checkpoint, "accuracy" or "balanced-accuracy" over the validation part;
- samples: which training crops the run sees (#207), "all", "only-sources" or "drop-sources" with
  sources=a,b naming the catalog's sources, or "cap-per-person" with per_person=N keeping the
  first N crops of each person in the catalog's order; the validation part is never cut, so every
  run of a comparison scores the same crops;
- architecture: the backbone, "resnet18" (version 1), "resnet34", "resnet50",
  "mobilenet-v3-small" or "efficientnet-b0" from torchvision, or "densenet121", "se-resnet50" or
  "se-resnext50" from MONAI (#211), each with its own head and, where one is read, its own
  ImageNet file;
- denoise: a filter on the crop inside the model, before the scaling, "none", "gaussian" or
  "median", so the evaluator, the latency measurement and the ONNX export carry it;
- prior: a second supervision from 3D (#228), "none" or "level-map", where a head on the
  backbone's last feature map predicts the frame's projected level map, the segmented CT's
  voxels mapped onto the X-ray by the render's geometry or a registered pose, and its loss is
  added with prior_weight; the head is training-only, so the exported classifier is unchanged.

DEFAULT is version 1's training exactly, so a run that names no block trains as before and the
recorded runs stay reproducible. The choices are kept here, with the arithmetic that needs no
torch (the schedule's factor, the class weights, the balanced accuracy, which crops a samples
block keeps); tools/train_blocks.py holds the torch side, one function per name, and its tests
hold the two lists equal. A new way of doing a part is one name added to its tuple here and one
function there, plus the entry the part keys by name where it has one (HEADS and FEATURES for
an architecture, AUGMENT_ORDER for an augment change, a branch in _keeps for a samples choice); a
new part is a field with version 1's default and its entry in CHOICES or SETTINGS, which
`problems` checks and `parts` reads to list every part with its names for tools/block_sweep.py.

The smoke test of every block (#252) is two pieces of data made here: `cover`, the rows of a
covering set that runs every option of every part and every pair of parts that meet in the code,
and `trials`, the six arms of the literature trials; tools/block_sweep.py writes each as a plan
file, checks it against a catalog and runs it row by row. A row's slug is made from its
configuration alone, so a plan read again, or reordered, names every row's folder as before.
"""

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, fields, replace
from itertools import combinations
from typing import Any, TypedDict

from beartype import beartype
from beethoven_qa.contracts import ensure, require

NORMALISE = ("none", "imagenet")
AUGMENT = ("box-jitter", "intensity", "blur", "noise", "strong")
OPTIMISER = ("adam", "adamw")
SCHEDULE = ("constant", "cosine")
SAMPLER = ("uniform", "balanced")
LOSS_WEIGHTS = ("none", "inverse-frequency")
SELECT = ("accuracy", "balanced-accuracy")
SAMPLES = ("all", "only-sources", "drop-sources", "cap-per-person")
ARCHITECTURE = (
    "resnet18",
    "resnet34",
    "resnet50",
    "mobilenet-v3-small",
    "efficientnet-b0",
    "densenet121",
    "se-resnet50",
    "se-resnext50",
)
DENOISE = ("none", "gaussian", "median")
PRIOR = ("none", "level-map")
# The samples choices that take a list of sources, and the one that takes a count per person.
BY_SOURCE = ("only-sources", "drop-sources")
BY_PERSON = "cap-per-person"


class BlockError(ValueError):
    """A block named that does not exist, or a setting outside its range, said in words."""


@dataclass(frozen=True)
class Blocks:
    """One choice for each part of training; the defaults are version 1's training."""

    normalise: str = "none"
    augment: tuple[str, ...] = ()
    optimiser: str = "adam"
    weight_decay: float = 0.0
    schedule: str = "constant"
    warmup_epochs: int = 0
    backbone_lr_scale: float = 1.0
    sampler: str = "uniform"
    loss_weights: str = "none"
    select: str = "accuracy"
    samples: str = "all"
    sources: tuple[str, ...] = ()
    per_person: int = 0
    architecture: str = "resnet18"
    denoise: str = "none"
    prior: str = "none"
    prior_weight: float = 0.0


DEFAULT = Blocks()
CHOICES = {
    "normalise": NORMALISE,
    "optimiser": OPTIMISER,
    "schedule": SCHEDULE,
    "sampler": SAMPLER,
    "loss_weights": LOSS_WEIGHTS,
    "select": SELECT,
    "samples": SAMPLES,
    "architecture": ARCHITECTURE,
    "denoise": DENOISE,
    "prior": PRIOR,
}
# The settings a choice takes, each with its range in words, for `parts` and the command line.
SETTINGS = {
    "augment": "any of " + ", ".join(AUGMENT) + ", comma-separated, or none",
    "weight_decay": "a finite number, 0 or more, with optimiser=adamw",
    "warmup_epochs": "whole epochs, 0 or more",
    "backbone_lr_scale": "above 0 and at most 1",
    "sources": "the catalog's sources, comma-separated, with samples=only-sources or drop-sources",
    "per_person": "crops kept per person, 1 or more, with samples=cap-per-person",
    "prior_weight": "the prior loss's weight beside the level loss, above 0, with prior=level-map",
}
LISTS = ("augment", "sources")
NUMBERS = ("weight_decay", "backbone_lr_scale", "prior_weight")
COUNTS = ("warmup_epochs", "per_person")


FIELDS = tuple(f.name for f in fields(Blocks))


def _plain(value: object) -> bool:
    # A value a checkpoint's record can hold for a block: a word, a number or a list of words.
    if isinstance(value, list):
        return all(isinstance(part, str) for part in value)
    return isinstance(value, (str, int, float))


def _choice_problems(blocks: Blocks) -> list[str]:
    found = []
    for name, allowed in CHOICES.items():
        value = getattr(blocks, name)
        if value not in allowed:
            found.append(f"{name}={value!r} is not one of {', '.join(allowed)}")
    for change in blocks.augment:
        if change not in AUGMENT:
            found.append(f"augment {change!r} is not one of {', '.join(AUGMENT)}")
    if len(set(blocks.augment)) != len(blocks.augment):
        found.append("augment names a change twice")
    return found


def _number_problems(blocks: Blocks) -> list[str]:
    found = []
    if not (math.isfinite(blocks.weight_decay) and blocks.weight_decay >= 0.0):
        found.append("weight_decay is a finite number, 0 or more")
    if blocks.warmup_epochs < 0:
        found.append("warmup_epochs is 0 or more")
    if not (math.isfinite(blocks.backbone_lr_scale) and 0.0 < blocks.backbone_lr_scale <= 1.0):
        found.append("backbone_lr_scale is above 0 and at most 1")
    if blocks.weight_decay > 0.0 and blocks.optimiser == "adam":
        found.append(
            "weight_decay is for adamw; adam's would be L2 in the gradient,"
            " which this trainer does not offer"
        )
    # The prior's weight goes with the prior and nowhere else, as a setting that would act on
    # nothing is most likely a mistake; a prior with no weight would train its head for nothing.
    if not (math.isfinite(blocks.prior_weight) and blocks.prior_weight >= 0.0):
        found.append("prior_weight is a finite number, 0 or more")
    elif (blocks.prior != "none") != (blocks.prior_weight > 0.0):
        found.append("prior_weight above 0 goes with prior=level-map, and only there")
    return found


def _sample_problems(blocks: Blocks) -> list[str]:
    # A setting that would act on nothing is refused too, since it is most likely a mistake: the
    # sources go with only-sources or drop-sources, the count with cap-per-person, and nowhere else.
    found = []
    if (blocks.samples in BY_SOURCE) != bool(blocks.sources):
        found.append("sources=a,b goes with samples=only-sources or drop-sources, and only there")
    if len(set(blocks.sources)) != len(blocks.sources):
        found.append("sources names a source twice")
    if (blocks.samples == BY_PERSON) != (blocks.per_person > 0):
        found.append("per_person of 1 or more goes with samples=cap-per-person, and only there")
    if blocks.per_person < 0:
        found.append("per_person is 0 or more")
    return found


# The rules `problems` holds a run's blocks to, in words, for the smoke test's check of every named
# combination (tools/block_sweep.py check --all), which prints them beside what it reads from a
# catalog: these are the incompatibilities declared here, the rest are the catalog's.
RULES = (
    "each part names one of its choices, and augment names each change at most once",
    "weight_decay is a finite number, 0 or more, and above 0 only with optimiser=adamw",
    "warmup_epochs is a whole number of epochs, 0 or more",
    "backbone_lr_scale is above 0 and at most 1",
    "prior_weight is above 0 with prior=level-map, and only there",
    "sources names each source once, with samples=only-sources or drop-sources, and only there",
    "per_person is 1 or more with samples=cap-per-person, and only there",
)


@beartype
@ensure(lambda result: all(isinstance(line, str) and line for line in result), "each said in words")
@ensure(lambda result, blocks: blocks != DEFAULT or not result, "version 1's training holds")
def problems(blocks: Blocks) -> list[str]:
    """Every way the choices fall outside what exists, in words; empty when they hold."""
    return _choice_problems(blocks) + _number_problems(blocks) + _sample_problems(blocks)


def _value(name: str, text: str) -> object:
    """One KEY=VALUE's value as its field's type."""
    if name in LISTS:
        parts_named = (part.strip() for part in text.split(","))
        return tuple(part for part in parts_named if part and part != "none")
    if name in NUMBERS:
        try:
            return float(text)
        except ValueError as error:
            raise BlockError(f"{name}={text!r} is not a number") from error
    if name in COUNTS:
        if not (text.isascii() and text.isdigit() and len(text) <= 6):
            raise BlockError(f"{name}={text!r} is not a whole number of at most 6 digits")
        return int(text)
    return text


@beartype
@ensure(lambda result: not problems(result), "the blocks returned hold")
@ensure(lambda result, pairs: pairs or result == DEFAULT, "no word is version 1's training")
def parse(pairs: Sequence[str]) -> Blocks:
    """The run's blocks from KEY=VALUE words, each key at most once, refused whole on any fault.

    :raises BlockError: a word that names no block, a block named twice, or choices that do not
        hold, said in words.
    """
    names = set(FIELDS)
    # Any, since each key's value has its own field's type, which _value checked by name.
    chosen: dict[str, Any] = {}
    for pair in pairs:
        key, sep, text = pair.partition("=")
        name = key.strip().replace("-", "_")
        if not sep or name not in names:
            raise BlockError(
                f"{pair!r}: a block is KEY=VALUE with KEY one of {', '.join(sorted(names))}"
            )
        if name in chosen:
            raise BlockError(f"{name} is named twice")
        chosen[name] = _value(name, text.strip())
    blocks = replace(DEFAULT, **chosen)
    found = problems(blocks)
    if found:
        raise BlockError("; ".join(found))
    return blocks


@beartype
@ensure(lambda result: set(result) == set(FIELDS), "every block, and nothing else")
@ensure(lambda result: all(isinstance(result[n], list) for n in LISTS), "lists, as JSON keeps them")
def as_record(blocks: Blocks) -> dict[str, object]:
    """The blocks as the checkpoint and the card write them, augment and sources as lists."""
    record = asdict(blocks)
    for name in LISTS:
        record[name] = list(getattr(blocks, name))
    return record


@beartype
@require(
    lambda record: record is None or all(_plain(v) for v in record.values()),
    "a record as JSON gives it: words, numbers and lists of words",
)
@ensure(lambda result: not problems(result), "the blocks returned hold")
@ensure(lambda result, record: record or result == DEFAULT, "no record is version 1's training")
def from_record(record: Mapping[str, object] | None) -> Blocks:
    """The blocks a checkpoint names; a checkpoint written before blocks existed is DEFAULT.

    :raises BlockError: a record naming a block that does not exist or choices that do not hold.
    """
    if not record:
        return DEFAULT
    words = [f"{k}={','.join(v) if isinstance(v, list) else v}" for k, v in record.items()]
    return parse(words)


@beartype
@require(lambda epochs: 1 <= epochs <= 100_000, "a run trains 1 to 100,000 epochs")
@require(lambda epoch, epochs: 1 <= epoch <= epochs, "epochs count from 1")
@require(lambda warmup: 0 <= warmup <= 100_000, "warm-up is 0 or more epochs")
@require(lambda schedule: schedule in SCHEDULE, "a schedule that exists")
@ensure(lambda result: 0.0 < result <= 1.0, "a factor on the base rate, above 0 and at most 1")
def lr_factor(epoch: int, epochs: int, warmup: int, schedule: str) -> float:
    """The share of the base learning rate epoch `epoch` trains at.

    A linear warm-up over the first `warmup` epochs, then either the full rate or a cosine from
    the full rate down, never reaching 0 on the last epoch, so every epoch learns something.
    """
    if epoch <= warmup:
        return epoch / (warmup + 1)
    if schedule == "constant":
        return 1.0
    span = max(1, epochs - warmup)
    return 0.5 * (1.0 + math.cos(math.pi * (epoch - warmup - 1) / span))


def _keeps(blocks: Blocks, source: str, nth: int) -> bool:
    """Whether the nth crop of its person, from the named source, is one the run trains on."""
    if blocks.samples == "only-sources":
        return source in blocks.sources
    if blocks.samples == "drop-sources":
        return source not in blocks.sources
    if blocks.samples == BY_PERSON:
        return nth <= blocks.per_person
    return True


@beartype
@require(lambda sources, persons: len(sources) == len(persons), "one source and one person a crop")
@ensure(lambda result, sources: len(result) == len(sources), "one answer a crop, in order")
@ensure(lambda result, blocks: blocks.samples != "all" or all(result), "all keeps every crop")
def kept(blocks: Blocks, sources: Sequence[str], persons: Sequence[str]) -> list[bool]:
    """Which training crops the run sees, one answer per crop in the catalog's order.

    The crops come in the catalog's order, by frame hash and then level, which is fixed and
    arbitrary, so cap-per-person keeps the same first crops of each person in every run and a
    comparison between runs changes one thing at a time. The validation part never comes here.
    """
    seen: dict[str, int] = {}
    answers = []
    for source, person in zip(sources, persons, strict=True):
        seen[person] = seen.get(person, 0) + 1
        answers.append(_keeps(blocks, source, seen[person]))
    return answers


@beartype
@ensure(lambda result: [row["part"] for row in result] == list(FIELDS), "every part once, in order")
@ensure(lambda result: all(set(r) == {"part", "choices", "default"} for r in result), "3 columns")
def parts() -> list[dict[str, str]]:
    """Every plug-in point: the part, what it may be, and version 1's choice; what the owner reads
    before planning a sweep, and what a new block must appear in."""
    default = as_record(DEFAULT)
    rows = []
    for name in FIELDS:
        choices = ", ".join(CHOICES[name]) if name in CHOICES else SETTINGS[name]
        value = default[name]
        shown = (",".join(value) or "none") if isinstance(value, list) else str(value)
        rows.append({"part": name, "choices": choices, "default": shown})
    return rows


@beartype
@require(lambda counts: all(n >= 0 for n in counts.values()), "counts are 0 or more")
@require(lambda counts: any(n > 0 for n in counts.values()), "at least one level is present")
@ensure(lambda result, counts: set(result) == set(counts), "a weight for every level named")
@ensure(lambda result: all(w >= 0.0 for w in result.values()), "weights are 0 or more")
def inverse_frequency(counts: Mapping[str, int]) -> dict[str, float]:
    """Each present level weighted by the inverse of its count, the weights averaging 1 over the
    present levels; an absent level weighs 0, since it has nothing to weigh."""
    present = {name: n for name, n in counts.items() if n > 0}
    raw = {name: 1.0 / n for name, n in present.items()}
    mean = sum(raw.values()) / len(raw)
    return {name: raw[name] / mean if name in raw else 0.0 for name in counts}


@beartype
@require(
    lambda per_level: all(
        len(cell) == 2 and 0 <= cell[0] <= cell[1] for cell in per_level.values()
    ),
    "each level is right and total, right at most total",
)
@ensure(lambda result: 0.0 <= result <= 1.0, "a share")
def balanced_accuracy(per_level: Mapping[str, Sequence[int]]) -> float:
    """The mean of each level's accuracy over the levels with at least one crop; 0 with none."""
    shares = [cell[0] / cell[1] for cell in per_level.values() if cell[1] > 0]
    return sum(shares) / len(shares) if shares else 0.0


# How many runs one sweep may plan: a grid of choices grows fast, and every run is a job the owner
# counts before it is sent.
SWEEP_LIMIT = 64


@beartype
@ensure(lambda result: 1 <= len(result) <= SWEEP_LIMIT, "one run at least, never past the limit")
@ensure(lambda result: all(not problems(b) for b in result), "every run planned holds")
def sweep(base: Sequence[str], vary: Mapping[str, Sequence[str]]) -> list[Blocks]:
    """Every combination of the varied blocks over the base, each checked, in a fixed order.

    `vary` maps a block to the values to try (augment values are comma lists, as on the command
    line). A combination that does not hold, such as adam with weight decay, is refused with the
    rest, never skipped, so the plan the owner approves is the plan that runs.

    :raises BlockError: a varied block with no value, a plan of more than SWEEP_LIMIT runs, or a
        combination that does not hold.
    """
    plans: list[list[str]] = [list(base)]
    for name in sorted(vary):
        values = list(vary[name])
        if not values:
            raise BlockError(f"{name}: a varied block needs at least one value")
        plans = [words + [f"{name}={value}"] for words in plans for value in values]
        if len(plans) > SWEEP_LIMIT:
            raise BlockError(f"the sweep plans more than {SWEEP_LIMIT} runs; vary fewer blocks")
    return [parse(words) for words in plans]


@beartype
@ensure(lambda result: all("=" in word for word in result), "each word is KEY=VALUE")
@ensure(lambda result, blocks: blocks != DEFAULT or not result, "version 1 needs no word")
def words_of(blocks: Blocks) -> list[str]:
    """The KEY=VALUE words that name these blocks, only those that differ from DEFAULT."""
    record, default = as_record(blocks), as_record(DEFAULT)
    out = []
    for name, value in record.items():
        if value != default[name]:
            out.append(f"{name}={','.join(value) if isinstance(value, list) else value}")
    return out


# The smoke test's covering set (#252). Each part is a factor with the values the cover runs, in
# the order given, each value a choice with its canonical setting (SETTING_OF): adamw takes
# weight_decay 0.01, the level-map prior prior_weight 0.5, cap-per-person per_person 1, and the
# two source cuts take the placeholders LABELLED and UNLABELLED, the catalog's train-part sources
# with and without labelled crops, which the check resolves against a catalog. Each augment name
# is a factor of its own, off or on, since a run may name any subset of them.
LABELLED, UNLABELLED = "@labelled", "@unlabelled"
SIZES = (64, 32, 96, 128)
AUGMENT_FACTOR = "augment:"
COVER_FACTORS: tuple[tuple[str, tuple[object, ...]], ...] = (
    ("architecture", ARCHITECTURE),
    ("size", SIZES),
    ("denoise", DENOISE),
    ("normalise", NORMALISE),
    ("samples", SAMPLES),
    ("optimiser", OPTIMISER),
    ("schedule", SCHEDULE),
    ("warmup_epochs", (0, 1)),
    ("backbone_lr_scale", (1.0, 0.1)),
    ("sampler", SAMPLER),
    ("loss_weights", LOSS_WEIGHTS),
    ("select", SELECT),
    *((AUGMENT_FACTOR + name, (False, True)) for name in AUGMENT),
)
PRIOR_FACTOR: tuple[str, tuple[object, ...]] = ("prior", PRIOR)
# The parts whose code meets inside one half of the cover, so every pair of their values runs: the
# filter runs before the scaling inside the model, the class weights act on what the sampler
# draws, the optimiser carries the schedule's rate, and the warm-up is the schedule's first part.
# Every other part is a hook of its own that acts on whatever it is handed. The prior's meetings
# (with the architecture, the size, the box jitter, the samples cut and the backbone rate) are
# covered by running each half once with the prior off and once with it on.
COVER_PAIRS = (
    ("denoise", "normalise"),
    ("sampler", "loss_weights"),
    ("optimiser", "schedule"),
    ("schedule", "warmup_epochs"),
)
SETTING_OF: dict[tuple[str, object], dict[str, Any]] = {
    ("optimiser", "adamw"): {"weight_decay": 0.01},
    ("prior", "level-map"): {"prior_weight": 0.5},
    ("samples", "cap-per-person"): {"per_person": 1},
    ("samples", "only-sources"): {"sources": (LABELLED,)},
    ("samples", "drop-sources"): {"sources": (UNLABELLED,)},
}
# The cut drop-sources takes the unannotated sources (UNLABELLED), and the trainer refuses a cut
# that names a source holding no labelled crop (tools/train.py training_crops), so a row with it
# never trains, whatever its other parts are. The array is built over the cuts that train, and
# each half gains one row more, version 1's training with drop-sources, so the cut is still in
# each half and no option of another part is spent on a row that never trains.
TRAINING_CUTS = tuple(name for name in SAMPLES if name != "drop-sources")
# What a row is for: a row of the cover, the run from an ImageNet file, a warm start, a refusal the
# check predicts, or an arm of the literature trials. Every role but the cover's starts the slug.
ROLES = ("cover", "imagenet", "init", "refuse", "trial")


class Row(TypedDict):
    """One run of a plan: what it is for, its folder's name, its blocks, its crop size, the
    architecture whose ImageNet file it starts from, and the slug of the row whose best.pt it
    starts from; None where it starts from neither."""

    role: str
    slug: str
    blocks: Blocks
    size: int
    weights: str | None
    init: str | None


# A cell of the covering array is a value's place in its factor (or None while the cell is
# free), so values of different types never compare; a requirement is (the earlier column, its
# value's place, this column's value's place), with -1 -1 for a value that must appear at all.
Cells = list[int | None]
Requirement = tuple[int, int, int]


@dataclass(frozen=True)
class _Column:
    """The column the array grows by: its place among the factors, how many values its factor
    has, and the earlier columns it must meet in every pair of values."""

    index: int
    size: int
    partners: tuple[int, ...]


@dataclass(frozen=True)
class _Start:
    """Where a row's training starts: the architecture whose ImageNet file it loads, the slug of
    the row whose best.pt it loads, both or neither."""

    weights: str | None = None
    init: str | None = None


FROM_SCRATCH = _Start()


def _partners(names: Sequence[str], pairs: Sequence[tuple[str, str]]) -> dict[int, list[int]]:
    """For each column, the earlier columns it must meet in every pair of values."""
    found: dict[int, list[int]] = {column: [] for column in range(len(names))}
    for a, b in pairs:
        early, late = sorted((names.index(a), names.index(b)))
        found[late].append(early)
    return {column: sorted(set(earlier)) for column, earlier in found.items()}


def _needed(sizes: Sequence[int], column: _Column) -> set[Requirement]:
    """What a column must cover: each of its values once, and each pair with a partner's values."""
    needed = {(-1, -1, b) for b in range(column.size)}
    needed |= {
        (i, a, b) for i in column.partners for a in range(sizes[i]) for b in range(column.size)
    }
    return needed


def _met(row: Cells, column: _Column, value: int) -> set[Requirement]:
    """The requirements this value in this row's column meets, with the row's cells so far."""
    met = {(-1, -1, value)}
    for i in column.partners:
        earlier = row[i]
        if earlier is not None:
            met.add((i, earlier, value))
    return met


def _across(rows: list[Cells], column: _Column, needed: set[Requirement]) -> None:
    """IPOG's horizontal growth: each row in turn takes the value that meets the most requirements
    still open, a tie going to the value used least so far in the column and then to the one
    declared first, so the array is the same on every run and on every machine."""
    used = [0] * column.size
    for row in rows:
        best = max(
            range(column.size),
            key=lambda v: (len(_met(row, column, v) & needed), -used[v], -v),
        )
        row[column.index] = best
        used[best] += 1
        needed -= _met(row, column, best)


def _redundant(rows: list[Cells], row: Cells, column: _Column) -> bool:
    """Whether every requirement this row's cell in the column meets is met by another row too, so
    the cell may take another value and the array lose nothing."""
    value = row[column.index]
    if value is None:
        return True
    others: set[Requirement] = set()
    for other in rows:
        cell = other[column.index]
        if other is not row and cell is not None:
            others |= _met(other, column, cell)
    return _met(row, column, value) <= others


def _into_free_cell(rows: list[Cells], column: _Column, requirement: Requirement) -> Cells | None:
    """The first row whose column already holds the value and whose earlier cell is still free,
    that cell then taking the earlier value; None for a requirement of one value alone."""
    i, a, b = requirement
    if i < 0:
        return None
    row = next((r for r in rows if r[column.index] == b and r[i] is None), None)
    if row is not None:
        row[i] = a
    return row


def _into_spare_cell(rows: list[Cells], column: _Column, requirement: Requirement) -> Cells | None:
    """The first row that holds the earlier value, if any is asked for, and whose cell in the
    column meets nothing no other row meets, that cell then taking the value."""
    i, a, b = requirement
    row = next(
        (r for r in rows if (i < 0 or r[i] == a) and _redundant(rows, r, column)),
        None,
    )
    if row is not None:
        row[column.index] = b
    return row


def _into_new_row(
    rows: list[Cells], column: _Column, requirement: Requirement, width: int
) -> Cells:
    """A new row of free cells but the column's value and, if one is asked for, the earlier one."""
    i, a, b = requirement
    row: Cells = [None] * width
    row[column.index] = b
    if i >= 0:
        row[i] = a
    rows.append(row)
    return row


def _down(rows: list[Cells], column: _Column, needed: set[Requirement], width: int) -> None:
    """IPOG's vertical growth: each requirement the rows left open goes into a row whose earlier
    cell is still free and whose column holds the value, else into a row whose cell in the column
    meets nothing no other row meets, else into a new row of free cells; the second is what lets
    the strict array close in as few rows as any array can have."""
    for requirement in sorted(needed):
        if requirement not in needed:
            continue
        row = _into_free_cell(rows, column, requirement)
        if row is None:
            row = _into_spare_cell(rows, column, requirement)
        if row is None:
            row = _into_new_row(rows, column, requirement, width)
        needed -= _met(row, column, requirement[2])


def _fill(rows: list[Cells], sizes: Sequence[int]) -> None:
    """The cells left free take the value used least in their column, then the first declared:
    a free cell covers nothing, so any value only adds to what the array covers."""
    for column, size in enumerate(sizes):
        used = [0] * size
        for row in rows:
            cell = row[column]
            if cell is not None:
                used[cell] += 1
        for row in rows:
            if row[column] is None:
                pick = min(range(size), key=lambda v: (used[v], v))
                row[column] = pick
                used[pick] += 1


def _covering(
    factors: Sequence[tuple[str, tuple[object, ...]]], pairs: Sequence[tuple[str, str]]
) -> list[tuple[object, ...]]:
    """A covering array, one tuple of values per row in the factors' order: every value of every
    factor at least once and every pair of values of each pair of factors named, built by IPOG
    (Lei and Tai's in-parameter-order growth): a row for each value of the first factor, or for
    each pair of values of the first two where they are paired, then each factor in turn across
    the rows and, where they leave a requirement open, down into new ones. Starting from every
    pair of the first two, in order, is what lets the strict array close in 32 rows, the
    architecture's 8 values times the size's 4, as few as any array can have."""
    names = [name for name, _ in factors]
    sizes = [len(values) for _, values in factors]
    partners = _partners(names, pairs)
    width = len(factors)
    rows: list[Cells] = [[v] + [None] * (width - 1) for v in range(sizes[0])]
    first = 1
    if width > 1 and 0 in partners[1]:
        rows = [[a, b] + [None] * (width - 2) for a in range(sizes[0]) for b in range(sizes[1])]
        first = 2
    for index in range(first, width):
        column = _Column(index, sizes[index], tuple(partners[index]))
        needed = _needed(sizes, column)
        _across(rows, column, needed)
        _down(rows, column, needed, width)
    _fill(rows, sizes)
    return [tuple(factors[c][1][v] for c, v in enumerate(row) if v is not None) for row in rows]


def _canonical(blocks: Blocks, size: int, start: _Start) -> str:
    """A row's configuration as one text: what its slug is the hash of."""
    record = {
        "blocks": as_record(blocks),
        "size": size,
        "weights": start.weights,
        "init": start.init,
    }
    return json.dumps(record, sort_keys=True, separators=(",", ":"))


def _row(role: str, blocks: Blocks, size: int, start: _Start = FROM_SCRATCH) -> Row:
    """A plan's row with its slug: the architecture, the size and the first 8 hex of the hash of
    its configuration, after its role unless it is a cover row, so the slug follows from the
    configuration alone and reordering the rows renames none of them."""
    digest = hashlib.sha256(_canonical(blocks, size, start).encode("ascii")).hexdigest()
    prefix = "" if role == "cover" else f"{role}-"
    slug = f"{prefix}{blocks.architecture}-{size}px-{digest[:8]}"
    return {
        "role": role,
        "slug": slug,
        "blocks": blocks,
        "size": size,
        "weights": start.weights,
        "init": start.init,
    }


def _cover_row(chosen: Mapping[str, object]) -> Row:
    """The cover row a choice of every factor's value names, each with its canonical setting."""
    settings: dict[str, Any] = {}
    augment = []
    for name, value in chosen.items():
        if name.startswith(AUGMENT_FACTOR):
            if value:
                augment.append(name.removeprefix(AUGMENT_FACTOR))
        elif name != "size":
            settings[name] = value
            settings.update(SETTING_OF.get((name, value), {}))
    size = chosen["size"]
    assert isinstance(size, int)
    return _row("cover", replace(DEFAULT, augment=tuple(augment), **settings), size)


def _factors(strict: bool) -> tuple[tuple[str, tuple[object, ...]], ...]:
    """The factors the array is built over: the samples cut held to the cuts that train, and the
    prior a factor of its own in the strict array."""
    held = tuple(
        (name, TRAINING_CUTS if name == "samples" else values) for name, values in COVER_FACTORS
    )
    return (*held, PRIOR_FACTOR) if strict else held


def _pairs(strict: bool) -> list[tuple[str, str]]:
    """The pairs of factors whose every pair of values the array holds."""
    names = [name for name, _ in _factors(strict)]
    return list(combinations(names, 2)) if strict else list(COVER_PAIRS)


def _dropping_row(prior: str) -> Row:
    """Version 1's training at 64 pixels with the cut to every source but the unannotated ones,
    which the trainer refuses wherever a catalog has one and which names no source where it has
    none, so the row runs nothing else and costs the cover no option."""
    return _cover_row(
        {
            "architecture": DEFAULT.architecture,
            "size": 64,
            "samples": "drop-sources",
            "prior": prior,
        }
    )


def _cover_rows(strict: bool) -> list[Row]:
    """The cover itself: the two halves, the prior off then on, each closed by its dropping row;
    or the strict pairwise array with a dropping row for each prior."""
    names = [name for name, _ in _factors(strict)]
    array = [
        dict(zip(names, values, strict=True))
        for values in _covering(_factors(strict), _pairs(strict))
    ]
    if strict:
        return [_cover_row(chosen) for chosen in array] + [_dropping_row(p) for p in PRIOR]
    return [
        row
        for prior in PRIOR
        for row in [
            *(_cover_row({**chosen, "prior": prior}) for chosen in array),
            _dropping_row(prior),
        ]
    ]


def _route_rows(parent: Row) -> list[Row]:
    """The routes the cover alone does not take, from a cover row of version 1's architecture
    with no prior: a run from the ImageNet file, two warm starts (one adding the prior), and the
    four refusals the check predicts: a cut that leaves no crop, a cut to the unannotated sources
    alone, a warm start across architectures and a warm start that also names weights."""
    base, size, init = parent["blocks"], parent["size"], parent["slug"]
    other = next(name for name in ARCHITECTURE if name != base.architecture)
    return [
        _row(
            "imagenet",
            replace(DEFAULT, normalise="imagenet"),
            64,
            _Start(weights=DEFAULT.architecture),
        ),
        _row("init", base, size, _Start(init=init)),
        _row("init", replace(base, prior="level-map", prior_weight=0.5), size, _Start(init=init)),
        _row(
            "refuse", replace(base, samples="drop-sources", sources=(LABELLED,), per_person=0), size
        ),
        _row(
            "refuse",
            replace(base, samples="only-sources", sources=(UNLABELLED,), per_person=0),
            size,
        ),
        _row("refuse", replace(base, architecture=other), size, _Start(init=init)),
        _row("refuse", base, size, _Start(weights=base.architecture, init=init)),
    ]


def _value_of(row: Row, name: str) -> object:
    """A row's value of one factor of the cover, read back from its blocks and size."""
    if name == "size":
        return row["size"]
    if name.startswith(AUGMENT_FACTOR):
        return name.removeprefix(AUGMENT_FACTOR) in row["blocks"].augment
    return getattr(row["blocks"], name)


def _holds(
    rows: Sequence[Row],
    factors: Sequence[tuple[str, tuple[object, ...]]],
    pairs: Sequence[tuple[str, str]],
) -> bool:
    """Whether the rows take every value of every factor and every pair of values of each pair."""
    seen = [{name: _value_of(row, name) for name, _ in factors} for row in rows]
    values = dict(factors)
    singles = all(
        any(cells[name] == value for cells in seen)
        for name, choices in factors
        for value in choices
    )
    met = all(
        any(cells[a] == x and cells[b] == y for cells in seen)
        for a, b in pairs
        for x in values[a]
        for y in values[b]
    )
    return singles and met


def _halves(rows: Sequence[Row], strict: bool) -> list[list[Row]]:
    """The cover rows the promise is kept in: all of them when strict, else each prior's half."""
    cover_rows = [row for row in rows if row["role"] == "cover"]
    if strict:
        return [cover_rows]
    return [[row for row in cover_rows if row["blocks"].prior == prior] for prior in PRIOR]


def _priors_dropped(group: Sequence[Row], strict: bool) -> set[str]:
    """The priors a group needs a dropping row for: every prior when strict, else its half's own,
    and the prior off for a half with no row, which then holds none and fails."""
    if strict:
        return set(PRIOR)
    if not group:
        return {"none"}
    return {group[0]["blocks"].prior}


def _whole(group: Sequence[Row], strict: bool) -> bool:
    """One group's promise: every option and pair among its rows whose cut trains, and a dropping
    row for each prior it needs one for."""
    training = [row for row in group if row["blocks"].samples in TRAINING_CUTS]
    dropping = {row["blocks"].prior for row in group if row["blocks"].samples == "drop-sources"}
    holds = _holds(training, _factors(strict), _pairs(strict))
    return holds and dropping == _priors_dropped(group, strict)


def _covered(rows: Sequence[Row], strict: bool) -> bool:
    """The cover's promise: in each half, among the rows whose cut trains, every option of every
    part and every pair asked for, and a row with the cut that does not; strict, every pair of
    values of every two parts, the prior among them, and a dropping row for each prior."""
    return all(_whole(group, strict) for group in _halves(rows, strict))


def _routes_follow(rows: Sequence[Row]) -> bool:
    """The route rows come after the cover, and every warm start names a row before it."""
    roles = [row["role"] for row in rows]
    first_route = next((i for i, role in enumerate(roles) if role != "cover"), len(roles))
    before = [{row["slug"] for row in rows[:i]} for i in range(len(rows))]
    return all(role != "cover" for role in roles[first_route:]) and all(
        row["init"] is None or row["init"] in before[i] for i, row in enumerate(rows)
    )


@beartype
@ensure(
    lambda result: all(not problems(row["blocks"]) for row in result), "every row's blocks hold"
)
@ensure(lambda result: len({row["slug"] for row in result}) == len(result), "every slug once")
@ensure(lambda result, strict: _covered(result, strict), "every option and pair asked for is run")
@ensure(lambda result: _routes_follow(result), "the routes follow the cover, each parent before")
@ensure(
    lambda result: (
        [row["role"] for row in result if row["role"] != "cover"]
        == ["imagenet", "init", "init", "refuse", "refuse", "refuse", "refuse"]
    ),
    "one ImageNet start, two warm starts and four refusals after the cover",
)
def cover(strict: bool = False) -> list[Row]:
    """The smoke test's covering set as rows: the cover, then the routes it does not take.

    Running every named combination of the blocks is neither possible nor needed: a part whose
    code meets no other part's acts on whatever crops it is handed, so a run of each of its
    options shows it works with every other, and only parts whose code meets must run in every
    pair. So the cover is two halves, the prior off and the level-map prior on, each a covering
    array over the factors of COVER_FACTORS that holds every value of every factor and every
    pair of values of COVER_PAIRS (8 rows a half, the architecture's 8 values being the most
    any factor has and no pair asked for having more than 6), built over the samples cuts that
    train and closed by one row of the cut that cannot (TRAINING_CUTS), 9 rows a half. Every
    factor then meets both values of the prior, which are the prior's meetings in the code.
    `strict` gives the full pairwise array instead, every pair of values of every two factors,
    the prior among them (32 rows and the two dropping rows), for when the owner asks for it.

    The route rows follow, from the first cover row with the prior off whose architecture is
    version 1's (the first row, which is version 1's training at 64 pixels): the run from the
    ImageNet file, two warm starts and the four refusals of _route_rows.
    """
    rows = _cover_rows(strict)
    parent = next(
        row
        for row in rows
        if row["blocks"].prior == "none" and row["blocks"].architecture == DEFAULT.architecture
    )
    return rows + _route_rows(parent)


@beartype
@ensure(lambda result: [row["size"] for row in result] == [64, 64, 64, 96, 64, 64], "six arms")
@ensure(lambda result: all(row["role"] == "trial" for row in result), "every row a trial")
@ensure(lambda result: all(row["weights"] == "resnet18" for row in result), "all from ImageNet")
@ensure(lambda result: all(not problems(row["blocks"]) for row in result), "every arm holds")
@ensure(lambda result: len({row["slug"] for row in result}) == len(result), "every slug once")
@ensure(lambda result: result[0]["blocks"] == DEFAULT, "the control is version 1's training")
def trials() -> list[Row]:
    """The six arms of the literature trials, each resnet18 from its ImageNet file, in order: the
    control (version 1's training at 64 pixels); the ImageNet scaling with every augment change,
    the strong one among them (SyntheX's and FluoroSAM's randomisation); that with AdamW, its
    decay, a warm-up, a cosine schedule and a tenth of the rate for the pretrained layers; the
    second arm at 96 pixels; the second with the balanced sampler and the checkpoint chosen by
    balanced accuracy; and the third with those two."""
    strong = replace(DEFAULT, normalise="imagenet", augment=AUGMENT)
    tuned = replace(
        strong,
        optimiser="adamw",
        weight_decay=0.01,
        warmup_epochs=1,
        schedule="cosine",
        backbone_lr_scale=0.1,
    )
    arms = (
        (DEFAULT, 64),
        (strong, 64),
        (tuned, 64),
        (strong, 96),
        (replace(strong, sampler="balanced", select="balanced-accuracy"), 64),
        (replace(tuned, sampler="balanced", select="balanced-accuracy"), 64),
    )
    return [
        _row("trial", blocks, size, _Start(weights=blocks.architecture)) for blocks, size in arms
    ]
