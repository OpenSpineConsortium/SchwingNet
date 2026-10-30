"""Every training part of the auto-anatomist as a block: a KEY=VALUE word, parsed and refused in
words, spelled canonically and digested, so that a configuration has one name wherever it is
written (a search's ledger, a session's record, a W&B run) and no block named is the smoke run to
the bit.

    blocks.parse(["optimiser=sgd", "lr=0.001", "widths=8:16:32"])
    blocks.parse("schedule=joint anneal=900")
    blocks.DEFAULTS.words()                  # every key with its canonical value, in the table's order
    blocks.parse([]).digest() == blocks.DEFAULTS.digest()

The keys, their kinds and their bounds are the table TABLE, one row each, which is also the help a
caller prints (describe); the defaults are the dataclass Blocks' own, one source. A value is spelled
back canonically (0.00200 reads as 0.002, a pair as a:b, a switch as on or off), so two spellings of
one configuration have one digest. The defaults are the smoke run's numbers (train.LOSS_WEIGHTS,
HUBER_KNEE_MM and SPREAD_FLOOR_MM, smoke.LR and SPINES_PER_BATCH, ladder.Schedule's spans,
ladder.BLUR_MAX_MM and THRESHOLD_WIDTH_HU, gates.BONE_HU, model.Config's widths and groups,
optax.adamw's weight decay; and, for the second screen's arms, which the smoke run leaves off,
ladder.CYCLE_LAM, CYCLE_W, ADAPT_EVERY and RUNG_SPANS), spelled here as literals so that this
module imports no JAX; tests/test_autoanatomist_blocks.py holds the two apart.

What each block steers, in the order a session meets them (session.py):

- the optimiser: optimiser, lr, weight_decay, clip (a global-norm clip of the gradient, 0 for none),
  warmup (steps of linear warm-up of lr from 0, 0 for none), batch (whole phantoms a batch);
- the loss: knee (the pseudo-Huber knee of the landmark term, in millimetres), spread_floor (the
  floor under the heatmap's spread in the spread term), w_landmark, w_spread, w_value, w_feature,
  w_naming, w_mask and w_name (the terms' weights), naming (whether the naming term is in the loss at all),
  objective (landmarks, the oracle's landmarks as the decoder's target, every term above; mask, the
  fully latent objective of the owner's ask of 2026-10-30: the decoder gives the privileged channels
  themselves back, the target vertebra's mask and every vertebra's, from the fused features, so
  nothing is measured anywhere and the terms are mask, feature and name, the last the cross-entropy
  of a head that reads each crop's level name off the network's bottleneck, the latent a later
  shape prior is fit on; it takes naming=off and calibrate=none, since it has no value and no
  spread, and never the probe, whose decoder reads landmarks);
- the schedule of lambda and w: schedule (lambda-then-w, the smoke run's, lambda over lam_span and
  w over w_span; joint, both over lam_span; w-first, the spans swapped, so the earlier span is w's;
  fixed, lam_fixed and w_fixed throughout; cyclic, lambda-then-w twice in half the steps each, going
  back between the passes to lambda cycle_lam and w cycle_w; adaptive, w as lambda-then-w's and
  lambda moved every adapt_every steps by the error's own slope, never behind a floor; ladder.py
  says how), lam_span and w_span (shares of the anneal's steps), lam_fixed and w_fixed, cycle_lam,
  cycle_w and adapt_every, anneal (the steps the shares are shares of; 0 takes the first training
  budget the session is given);
- the encoder's input: intensity (off; gain-offset, a gain and an offset in HU on the CT the
  encoder reads; gain-offset-noise, Gaussian noise added), drawn on the host for the encoder's
  input only and never for the HU the ladder thresholds; normalise (clip, the smoke run's; clip-zscore,
  each crop standardised after the clip; model.Config's field);
- the network: architecture (which network the model spot takes, model.ARCHITECTURES: residual-unet,
  the smoke run's; plain-unet; probe, the framework's test piece whose answer is known), widths (the
  three scales' channels), groups (group norm's groups);
- the ladder: blur_mm (the blur rung's largest sigma), threshold_hu and threshold_width_hu (the
  soft threshold of the CT the last rung ends on), ladder (in-turn, the rungs one after another, a
  third of lambda each; overlapping, half of lambda each, a quarter apart; together, all of it);
- the restraint: restraint (off; abf, ABF's mean force on a collective variable, mid-anneal,
  train.py says how) and abf_weight, its weight;
- the calibration of the spread: calibrate (none; scale; quantile; calibrate.py), coverage (the
  quantile calibration's target coverage);
- seed, for the network's initialisation and the session's own random numbers.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, fields
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


@dataclass(frozen=True)
class Key:
    """One row of the table: the block's name, its kind (choice, switch, int, float, pair or triple),
    its choices where it is a choice, its bounds where it is a number (low and high inclusive,
    above and below strict) and one line on what it steers."""
    name: str
    kind: str
    what: str
    choices: Tuple[str, ...] = ()
    low: Optional[float] = None
    high: Optional[float] = None
    above: Optional[float] = None
    below: Optional[float] = None


TABLE: Tuple[Key, ...] = (
    Key("optimiser", "choice", "the optimiser", choices=("adamw", "adam", "sgd")),
    Key("lr", "float", "the learning rate", above=0.0),
    Key("weight_decay", "float", "adamw's decoupled weight decay; for adam and sgd an L2 term added to the gradient", low=0.0),
    Key("clip", "float", "the gradient's global-norm clip; 0 is none", low=0.0),
    Key("warmup", "int", "steps of linear warm-up of lr from 0; 0 is none", low=0),
    Key("batch", "int", "whole phantoms a batch", low=1),
    Key("knee", "float", "the pseudo-Huber knee of the landmark term, mm", above=0.0),
    Key("spread_floor", "float", "the floor under the heatmap's spread in the spread term, mm", above=0.0),
    Key("w_landmark", "float", "the landmark term's weight", low=0.0),
    Key("w_spread", "float", "the spread term's weight", low=0.0),
    Key("w_value", "float", "the value term's weight", low=0.0),
    Key("w_feature", "float", "the feature-matching term's weight", low=0.0),
    Key("w_naming", "float", "the naming term's weight", low=0.0),
    Key("w_mask", "float", "the mask term's weight, under objective=mask", low=0.0),
    Key("w_name", "float", "the name head's weight, under objective=mask: the cross-entropy of each crop's level name "
        "read off the network's bottleneck", low=0.0),
    Key("naming", "switch", "whether the naming term is in the loss"),
    Key("objective", "choice", "what the decoder is trained to give: the oracle's landmarks, or the privileged "
        "mask channels themselves (the fully latent objective, with no measurement anywhere)",
        choices=("landmarks", "mask")),
    Key("schedule", "choice", "how lambda's and w's ramps are placed",
        choices=("lambda-then-w", "joint", "w-first", "fixed", "cyclic", "adaptive")),
    Key("lam_span", "pair", "lambda's ramp, as shares of the anneal's steps"),
    Key("w_span", "pair", "w's ramp, as shares of the anneal's steps"),
    Key("lam_fixed", "float", "lambda under schedule=fixed", low=0.0, high=1.0),
    Key("w_fixed", "float", "w under schedule=fixed", low=0.0, high=1.0),
    Key("cycle_lam", "float", "the lambda schedule=cyclic goes back to between its passes", low=0.0, high=1.0),
    Key("cycle_w", "float", "the w schedule=cyclic goes back to between its passes", low=0.0, high=1.0),
    Key("adapt_every", "int", "the steps between two checks of schedule=adaptive", low=1),
    Key("anneal", "int", "the steps the spans are shares of; 0 takes the first training budget", low=0),
    Key("intensity", "choice", "a gain, an offset and noise on the encoder's input", choices=("off", "gain-offset", "gain-offset-noise")),
    Key("normalise", "choice", "how the encoder's CT channel is scaled", choices=("clip", "clip-zscore")),
    Key("architecture", "choice", "the network the model spot takes (model.ARCHITECTURES)",
        choices=("residual-unet", "plain-unet", "probe")),
    Key("widths", "triple", "the encoders' channels at the three scales"),
    Key("groups", "int", "group norm's groups", low=1),
    Key("blur_mm", "float", "the blur rung's largest sigma, mm", low=0.0),
    Key("threshold_hu", "float", "the soft threshold of the CT the ladder ends on, HU"),
    Key("threshold_width_hu", "float", "that threshold's width, HU", above=0.0),
    Key("ladder", "choice", "how much of lambda each rung spans: a third in turn, half overlapping, or all of it together",
        choices=("in-turn", "overlapping", "together")),
    Key("restraint", "choice", "an adaptive biasing force on a collective variable, mid-anneal (train.py)", choices=("off", "abf")),
    Key("abf_weight", "float", "the restraint's weight", low=0.0),
    Key("calibrate", "choice", "the calibration of the values' spreads", choices=("none", "scale", "quantile")),
    Key("coverage", "float", "the quantile calibration's target coverage", above=0.0, below=1.0),
    Key("seed", "int", "the network's initialisation and the session's draws", low=0),
)
KEYS: Dict[str, Key] = {k.name: k for k in TABLE}
RUNG_SPANS = {"in-turn": None, "overlapping": 0.5, "together": 1.0}     # ladder.RUNG_SPANS, spelled here to import no JAX


@dataclass(frozen=True)
class Blocks:
    """One configuration: every block with its value, the defaults the smoke run's."""
    optimiser: str = "adamw"
    lr: float = 0.002
    weight_decay: float = 0.0001
    clip: float = 0.0
    warmup: int = 0
    batch: int = 2
    knee: float = 2.0
    spread_floor: float = 0.5
    w_landmark: float = 1.0
    w_spread: float = 0.1
    w_value: float = 1.0
    w_feature: float = 1.0
    w_naming: float = 0.1
    w_mask: float = 1.0
    w_name: float = 0.1
    naming: bool = True
    objective: str = "landmarks"
    schedule: str = "lambda-then-w"
    lam_span: Tuple[float, float] = (0.15, 0.55)
    w_span: Tuple[float, float] = (0.45, 0.85)
    lam_fixed: float = 0.0
    w_fixed: float = 1.0
    cycle_lam: float = 0.5
    cycle_w: float = 0.3
    adapt_every: int = 20
    anneal: int = 0
    intensity: str = "off"
    normalise: str = "clip"
    architecture: str = "residual-unet"
    widths: Tuple[int, int, int] = (16, 32, 64)
    groups: int = 8
    blur_mm: float = 4.0
    threshold_hu: float = 200.0
    threshold_width_hu: float = 60.0
    ladder: str = "in-turn"
    restraint: str = "off"
    abf_weight: float = 1.0
    calibrate: str = "none"
    coverage: float = 0.68
    seed: int = 0

    def words(self) -> List[str]:
        """Every block as its canonical KEY=VALUE, in the table's order."""
        return ["%s=%s" % (k.name, spell(k, getattr(self, k.name))) for k in TABLE]

    def changed(self) -> List[str]:
        """The words that differ from the defaults, which name a configuration briefly."""
        return [w for w, d in zip(self.words(), DEFAULTS.words()) if w != d]

    def digest(self) -> str:
        """The sha256 of the canonical words, the configuration's name."""
        return hashlib.sha256(("\n".join(self.words()) + "\n").encode("ascii")).hexdigest()

    def record(self) -> dict:
        return {"words": self.words(), "changed": self.changed(), "digest": self.digest()}

    def weights(self) -> Dict[str, float]:
        """The loss terms' weights in train.LOSS_WEIGHTS' form."""
        return {"landmark": self.w_landmark, "spread": self.w_spread, "value": self.w_value,
                "feature": self.w_feature, "naming": self.w_naming, "mask": self.w_mask, "name": self.w_name}

    def rungs(self) -> Dict[str, float]:
        """The ladder's settings in ladder.degrade's keyword form, the rungs' span among them where
        they do not go in turn."""
        out = {"bone_hu": self.threshold_hu, "width_hu": self.threshold_width_hu, "blur_max_mm": self.blur_mm}
        if self.ladder != "in-turn":
            out["rung_span"] = RUNG_SPANS[self.ladder]
        return out


DEFAULTS = Blocks()
assert tuple(f.name for f in fields(Blocks)) == tuple(k.name for k in TABLE), "the table and the dataclass name the same blocks in the same order"


def number(v: float) -> str:
    """A float's canonical spelling: the shortest that reads back as the same float."""
    return repr(float(v))


def spell(key: Key, value: Any) -> str:
    """A value's canonical spelling for its key."""
    if key.kind == "switch":
        return "on" if value else "off"
    if key.kind == "int":
        return str(int(value))
    if key.kind == "float":
        return number(value)
    if key.kind in ("pair", "triple"):
        return ":".join(number(v) if key.kind == "pair" else str(int(v)) for v in value)
    return str(value)


def choices_in_words(choices: Sequence[str]) -> str:
    return ", ".join(choices[:-1]) + " or " + choices[-1]


def bounded(key: Key, v: float) -> float:
    if key.low is not None and v < key.low:
        raise ValueError("%s must be at least %s, not %s" % (key.name, number(key.low), number(v)))
    if key.above is not None and v <= key.above:
        raise ValueError("%s must be above %s, not %s" % (key.name, number(key.above), number(v)))
    if key.high is not None and v > key.high:
        raise ValueError("%s must be at most %s, not %s" % (key.name, number(key.high), number(v)))
    if key.below is not None and v >= key.below:
        raise ValueError("%s must be below %s, not %s" % (key.name, number(key.below), number(v)))
    return v


def read(key: Key, text: str) -> Any:
    """The value a word's text means for its key, refused in words when it means none."""
    text = text.strip()
    if key.kind == "choice":
        if text not in key.choices:
            raise ValueError("%s takes %s, not %r" % (key.name, choices_in_words(key.choices), text))
        return text
    if key.kind == "switch":
        if text not in ("on", "off"):
            raise ValueError("%s takes on or off, not %r" % (key.name, text))
        return text == "on"
    if key.kind == "int":
        try:
            v = int(text)
        except ValueError:
            raise ValueError("%s takes a whole number, not %r" % (key.name, text)) from None
        return int(bounded(key, v))
    if key.kind == "float":
        try:
            v = float(text)
        except ValueError:
            raise ValueError("%s takes a number, not %r" % (key.name, text)) from None
        if v != v or v in (float("inf"), float("-inf")):
            raise ValueError("%s takes a finite number, not %r" % (key.name, text))
        return bounded(key, v)
    if key.kind == "pair":
        parts = text.split(":")
        try:
            a, b = (float(p) for p in parts)
        except ValueError:
            raise ValueError("%s takes two shares a:b with 0 <= a < b <= 1, not %r" % (key.name, text)) from None
        if not (0.0 <= a < b <= 1.0):
            raise ValueError("%s takes two shares a:b with 0 <= a < b <= 1, not %r" % (key.name, text))
        return (a, b)
    if key.kind == "triple":
        parts = text.split(":")
        try:
            v = tuple(int(p) for p in parts)
        except ValueError:
            raise ValueError("%s takes three whole numbers a:b:c, not %r" % (key.name, text)) from None
        if len(v) != 3 or min(v) < 1:
            raise ValueError("%s takes three whole numbers a:b:c, each at least 1, not %r" % (key.name, text))
        return v
    raise ValueError("no such kind of block: %s" % key.kind)


def split_word(word: str) -> Tuple[str, str]:
    if word.count("=") != 1:
        raise ValueError("a block is written KEY=VALUE, not %r" % word)
    name, text = word.split("=")
    return name.strip(), text


def problems(b: Blocks) -> List[str]:
    """What keeps the blocks from holding together, each in words: the mask objective trains no
    landmark, so it has no value for the naming layer and no spread to calibrate, and the probe's
    decoder reads landmarks."""
    out = []
    if b.objective == "mask":
        if b.naming:
            out.append("objective=mask gives no value for the naming layer, so it takes naming=off")
        if b.calibrate != "none":
            out.append("objective=mask gives no spread to calibrate, so it takes calibrate=none")
        if b.architecture == "probe":
            out.append("objective=mask takes no probe, whose decoder reads landmarks; the probe is the landmark framework's test piece")
    return out


def parse(words: Union[str, Sequence[str], Dict[str, str], None] = None) -> Blocks:
    """The Blocks the words name: a string of words, a sequence of KEY=VALUE words or a dict of key
    to text; a key not in the table, a key named twice, a value its key refuses or blocks that do
    not hold together (problems) are refused in words, and a key not named takes its default."""
    if words is None:
        words = []
    if isinstance(words, str):
        words = words.split()
    items = list(words.items()) if isinstance(words, dict) else [split_word(w) for w in words]
    values: Dict[str, Any] = {}
    for name, text in items:
        key = KEYS.get(name)
        if key is None:
            raise ValueError("no block is named %r; the blocks are %s" % (name, ", ".join(k.name for k in TABLE)))
        if name in values:
            raise ValueError("%s is named twice" % name)
        values[name] = read(key, str(text))
    b = Blocks(**values)
    bad = problems(b)
    if bad:
        raise ValueError("; ".join(bad))
    return b


def describe() -> str:
    """The table in words, one block a line: name, kind, default and what it steers."""
    lines = []
    for k in TABLE:
        kind = k.kind if k.kind != "choice" else choices_in_words(k.choices)
        lines.append("%s (%s, default %s): %s" % (k.name, kind, spell(k, getattr(DEFAULTS, k.name)), k.what))
    return "\n".join(lines)
