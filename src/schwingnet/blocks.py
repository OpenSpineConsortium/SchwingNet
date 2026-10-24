"""The trainer's building blocks: each way of doing one part of training, chosen by name.

The owner's ask of 2026-10-24: build what the training review found as pieces that can be swapped,
so a better way of doing one part replaces that part and nothing else. A run names one choice per
part (docs/research/training-review.md, section 1):

- normalise: how a crop is scaled before the network, "none" (grey 0..1, as version 1 trained)
  or "imagenet" (ImageNet's mean and spread, which the ImageNet weights were trained on);
- augment: which training-time changes a batch gets, any of "box-jitter" (the box moved and
  resized a little, as a tracker's or detector's box is), "intensity" (gamma, contrast,
  brightness), "blur" and "noise" (dose-like), in that order, or none;
- optimiser: "adam" or "adamw", with weight_decay, and backbone_lr_scale for the pretrained
  layers' rate beside the new head's;
- schedule: "constant" or "cosine", after warmup_epochs of a linear warm-up;
- sampler: "uniform" (every crop once an epoch) or "balanced" (drawn so every level present is
  as likely as any other);
- loss_weights: "none" or "inverse-frequency" over the levels the training part holds;
- select: what chooses the checkpoint, "accuracy" or "balanced-accuracy" over the validation part.

DEFAULT is version 1's training exactly, so a run that names no block trains as before and the
recorded runs stay reproducible. The choices are kept here, with the arithmetic that needs no
torch (the schedule's factor, the class weights, the balanced accuracy); tools/train_blocks.py
holds the torch side, one function per name, and its tests hold the two lists equal. A new way of
doing a part is one name added to its tuple here and one function there.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, fields, replace
from typing import Any

from beartype import beartype
from beethoven_qa.contracts import ensure, require

NORMALISE = ("none", "imagenet")
AUGMENT = ("box-jitter", "intensity", "blur", "noise")
OPTIMISER = ("adam", "adamw")
SCHEDULE = ("constant", "cosine")
SAMPLER = ("uniform", "balanced")
LOSS_WEIGHTS = ("none", "inverse-frequency")
SELECT = ("accuracy", "balanced-accuracy")


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


DEFAULT = Blocks()
CHOICES = {
    "normalise": NORMALISE,
    "optimiser": OPTIMISER,
    "schedule": SCHEDULE,
    "sampler": SAMPLER,
    "loss_weights": LOSS_WEIGHTS,
    "select": SELECT,
}


FIELDS = tuple(f.name for f in fields(Blocks))


def _plain(value: object) -> bool:
    # A value a checkpoint's record can hold for a block: a word, a number or a list of words.
    if isinstance(value, list):
        return all(isinstance(part, str) for part in value)
    return isinstance(value, (str, int, float))


@beartype
@ensure(lambda result: all(isinstance(line, str) and line for line in result), "each said in words")
@ensure(lambda result, blocks: blocks != DEFAULT or not result, "version 1's training holds")
def problems(blocks: Blocks) -> list[str]:
    """Every way the choices fall outside what exists, in words; empty when they hold."""
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
    return found


def _value(name: str, text: str) -> object:
    """One KEY=VALUE's value as its field's type."""
    if name == "augment":
        return tuple(part for part in text.split(",") if part and part != "none")
    if name in ("weight_decay", "backbone_lr_scale"):
        try:
            return float(text)
        except ValueError as error:
            raise BlockError(f"{name}={text!r} is not a number") from error
    if name == "warmup_epochs":
        if not (text.isascii() and text.isdigit() and len(text) <= 4):
            raise BlockError(f"warmup_epochs={text!r} is not a whole number of at most 4 digits")
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
@ensure(lambda result: isinstance(result["augment"], list), "augment as a list, as JSON keeps it")
def as_record(blocks: Blocks) -> dict[str, object]:
    """The blocks as the checkpoint and the card write them, augment as a list."""
    record = asdict(blocks)
    record["augment"] = list(blocks.augment)
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
