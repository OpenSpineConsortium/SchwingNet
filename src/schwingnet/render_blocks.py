"""The renderer's building blocks: each part of making a synthetic X-ray from a CT, chosen by name.

The owner's ask of 2026-10-25 (the thread "Compare FleXray DRRs to real X-ray corpora"): rendering
fits the block schema the trainer has (schwingnet.blocks), so a DRR dataset is a configuration of
named parts, and FleXray's published workflow is one configuration of them. An integration test
then renders a sample of FleXray's dataset from the same raw CTs through these blocks and sets it
beside FleXray's own renderer and its released FluXray set (tools/domain_gap.py, the bench id
flexray_drr_gap). A render names one choice per part:

- hu_window: "flexray" clips the CT to -1000 to 2000 HU and stores it as float16, as FleXray's
  packs do, or "none";
- air_clamp: "flexray" sets every voxel at or below -900 HU to -1000, as FleXray's CT loader does
  before rendering, or "none";
- crop: "flexray-axial" pads or cuts the slice plane to 512 x 512 around its centre and cuts the
  volume into the fewest 256-slice axial crops that cover it, the first and last touching its ends
  (FleXray's packing, src/fxr/datasets/ct_crops.py), or "whole";
- crop_sampler: "inverse-label-frequency" draws crops with FleXray's weights, each model class a
  crop holds contributing (N / n_c) ** 0.5 and the crop taking the largest, or "uniform";
- pose: "flexray-moose" draws the gantry angle over the full orbit, the tilt within 30 degrees,
  the source within 100 mm of the isocentre across and 500 to 900 mm away, a detector 1150 to
  1250 mm away with 1.25 to 2.25 mm pixels (FleXray's MOOSE profile), or "flexray-default", the
  same orbit at the default profile's geometry;
- isocentre: "random-label" aims at the centroid of a structure the crop holds, drawn without
  replacement (FleXray's random_label), "vertebra" at a vertebra's, or "volume-centre";
- projection: "flexray-mix" is a cone beam nine times in ten and orthographic otherwise, "cone"
  always a cone beam;
- attenuation: "flexray-lognormal" multiplies each supervised structure's attenuation by a
  lognormal factor (mode 1, sigma 1, kept within 0.1 to 4) on half the renders, as FleXray's
  training does, or "off", the physical render;
- scale: "minmax", each render scaled to 0 to 1 on its own (FleXray's scale_rendered_images);
- edit: "none". FleXray's realism edit (FLUX.2 [klein]) is not in its code; it gets a name here
  when one exists to run.

The settings: views a CT, the detector's side in pixels and the samples along each ray.

DEFAULT is FleXray's released recipe for MOOSE 3.0, the largest share of its online CT stream and
the renders FluXray was edited from; PHYSICAL is the same with the attenuation randomisation off,
the render a comparison with real X-rays reads. The choices and the arithmetic that needs no torch
(the crop plan, the crop weights) are kept here, under the gate's contracts; tools/render_blocks.py
holds the torch side, one function per name, and its tests hold the two lists equal and this
module's crop plan equal to FleXray's own.
"""

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, fields, replace
from typing import Any

from beartype import beartype
from beethoven_qa.contracts import ensure, require

HU_WINDOW = ("flexray", "none")
AIR_CLAMP = ("flexray", "none")
CROP = ("flexray-axial", "whole")
CROP_SAMPLER = ("inverse-label-frequency", "uniform")
POSE = ("flexray-moose", "flexray-default")
ISOCENTRE = ("random-label", "vertebra", "volume-centre")
PROJECTION = ("flexray-mix", "cone")
ATTENUATION = ("flexray-lognormal", "off")
SCALE = ("minmax",)
EDIT = ("none",)

# FleXray's packing: 512 x 512 in the slice plane, 256 slices a crop.
CROP_SIDE = 512
CROP_DEPTH = 256
# FleXray's crop weights: the tempering exponent, and the largest class weight is the crop's.
CROP_TAU = 0.5


class RenderBlockError(ValueError):
    """A render block named that does not exist, or a setting outside its range, said in words."""


@dataclass(frozen=True)
class RenderBlocks:
    """One choice for each part of rendering; the defaults are FleXray's released MOOSE recipe."""

    hu_window: str = "flexray"
    air_clamp: str = "flexray"
    crop: str = "flexray-axial"
    crop_sampler: str = "inverse-label-frequency"
    pose: str = "flexray-moose"
    isocentre: str = "random-label"
    projection: str = "flexray-mix"
    attenuation: str = "flexray-lognormal"
    scale: str = "minmax"
    edit: str = "none"
    views: int = 4
    detector: int = 256
    ray_samples: int = 500


DEFAULT = RenderBlocks()
PHYSICAL = replace(DEFAULT, attenuation="off")
CHOICES = {
    "hu_window": HU_WINDOW,
    "air_clamp": AIR_CLAMP,
    "crop": CROP,
    "crop_sampler": CROP_SAMPLER,
    "pose": POSE,
    "isocentre": ISOCENTRE,
    "projection": PROJECTION,
    "attenuation": ATTENUATION,
    "scale": SCALE,
    "edit": EDIT,
}
# Each count with its inclusive range, for the checks and the listing.
COUNTS = {"views": (1, 100), "detector": (32, 1024), "ray_samples": (16, 4000)}
FIELDS = tuple(f.name for f in fields(RenderBlocks))

RULES = (
    "each part names one of its choices",
    "views is 1 to 100 renders a CT, detector 32 to 1024 pixels, ray_samples 16 to 4000",
    "crop_sampler=inverse-label-frequency weighs crops, so it goes with crop=flexray-axial",
)


def _count_problems(blocks: RenderBlocks) -> list[str]:
    found = []
    for name, (low, high) in COUNTS.items():
        if not low <= getattr(blocks, name) <= high:
            found.append(f"{name} is a whole number from {low} to {high}")
    return found


@beartype
@ensure(lambda result: all(isinstance(line, str) and line for line in result), "each said in words")
@ensure(lambda result, blocks: blocks != DEFAULT or not result, "FleXray's recipe holds")
def problems(blocks: RenderBlocks) -> list[str]:
    """Every way the choices fall outside what exists, in words; empty when they hold."""
    found = [
        f"{name}={getattr(blocks, name)!r} is not one of {', '.join(allowed)}"
        for name, allowed in CHOICES.items()
        if getattr(blocks, name) not in allowed
    ]
    found += _count_problems(blocks)
    if blocks.crop_sampler == "inverse-label-frequency" and blocks.crop != "flexray-axial":
        found.append("crop_sampler=inverse-label-frequency goes with crop=flexray-axial")
    return found


def _value(name: str, text: str) -> object:
    """One KEY=VALUE's value as its field's type."""
    if name not in COUNTS:
        return text
    if not (text.isascii() and text.isdigit() and len(text) <= 4):
        raise RenderBlockError(f"{name}={text!r} is not a whole number of at most 4 digits")
    return int(text)


@beartype
@ensure(lambda result: not problems(result), "the blocks returned hold")
@ensure(lambda result, pairs: bool(pairs) or result == DEFAULT, "no word is FleXray's recipe")
def parse(pairs: Sequence[str]) -> RenderBlocks:
    """A render's blocks from KEY=VALUE words, each key at most once, refused whole on any fault.

    :raises RenderBlockError: a word that names no block, a block named twice, or choices that do
        not hold, said in words.
    """
    names = set(FIELDS)
    chosen: dict[str, Any] = {}
    for pair in pairs:
        key, sep, text = pair.partition("=")
        name = key.strip().replace("-", "_")
        if not sep or name not in names:
            raise RenderBlockError(
                f"{pair!r}: a render block is KEY=VALUE with KEY one of {', '.join(sorted(names))}"
            )
        if name in chosen:
            raise RenderBlockError(f"{name} is named twice")
        chosen[name] = _value(name, text.strip())
    blocks = replace(DEFAULT, **chosen)
    found = problems(blocks)
    if found:
        raise RenderBlockError("; ".join(found))
    return blocks


@beartype
@ensure(lambda result: set(result) == set(FIELDS), "every block, and nothing else")
def as_record(blocks: RenderBlocks) -> dict[str, object]:
    """The blocks as a render's record writes them."""
    return asdict(blocks)


@beartype
@ensure(lambda result: len(result) == 12, "twelve hex digits")
@ensure(lambda result: all(c in "0123456789abcdef" for c in result), "hex digits")
def slug(blocks: RenderBlocks) -> str:
    """A short name for the configuration alone, so the same blocks name the same folder."""
    text = json.dumps(as_record(blocks), sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


@beartype
@ensure(lambda result: [row["part"] for row in result] == list(FIELDS), "every part once, in order")
def parts() -> list[dict[str, str]]:
    """Every plug-in point: the part, what it may be, and FleXray's choice."""
    default = as_record(DEFAULT)
    rows = []
    for name in FIELDS:
        if name in CHOICES:
            choices = ", ".join(CHOICES[name])
        else:
            choices = "a whole number from {} to {}".format(*COUNTS[name])
        rows.append({"part": name, "choices": choices, "default": str(default[name])})
    return rows


def _crop_covers(depth: int, plan: Sequence[tuple[int, int, int, int]]) -> bool:
    # Every slice of the volume lies in some crop, and every crop is CROP_DEPTH deep with its pads.
    covered: set[int] = set()
    for start, stop, before, after in plan:
        covered.update(range(start, stop))
        if stop - start + before + after != CROP_DEPTH:
            return False
    return covered == set(range(depth))


@beartype
@require(lambda depth: 1 <= depth <= 100_000, "a volume of 1 to 100,000 slices")
@ensure(lambda result, depth: _crop_covers(depth, result), "the crops cover every slice")
@ensure(lambda result: result[0][0] == 0, "the first crop starts at the first slice")
def plan_crops(depth: int) -> tuple[tuple[int, int, int, int], ...]:
    """FleXray's fewest axial crops of CROP_DEPTH slices that cover a volume, as (start, stop, pad
    before, pad after): the first and last touch the ends and the starts between are spread evenly,
    and a volume shorter than a crop is one crop padded with air on both sides."""
    if depth <= CROP_DEPTH:
        before = (CROP_DEPTH - depth) // 2
        return ((0, depth, before, CROP_DEPTH - depth - before),)
    last = depth - CROP_DEPTH
    if last < CROP_DEPTH:
        starts = [0, last]
    else:
        intervals = math.ceil(last / CROP_DEPTH)
        starts = [round(i * last / intervals) for i in range(intervals + 1)]
        starts[0], starts[-1] = 0, last
    return tuple((s, s + CROP_DEPTH, 0, 0) for s in starts)


@beartype
@require(lambda classes: len(classes) >= 1, "at least one crop")
@require(lambda classes: any(classes), "some crop holds a model class")
@ensure(lambda result, classes: len(result) == len(classes), "one weight a crop")
@ensure(lambda result: all(w >= 0.0 for w in result), "weights are 0 or more")
@ensure(lambda result: abs(sum(result) / len(result) - 1.0) < 1e-9, "weights average 1")
def crop_weights(classes: Sequence[frozenset[int]]) -> tuple[float, ...]:
    """FleXray's crop sampling weights: each model class a crop holds contributes (N / n_c) ** tau,
    N the crops and n_c the crops holding the class, and the crop takes the largest; a crop with no
    model class weighs 0; the weights are scaled to average 1."""
    holding: dict[int, int] = {}
    for crop in classes:
        for name in crop:
            holding[name] = holding.get(name, 0) + 1
    total = float(len(classes))
    raw = [max(((total / holding[c]) ** CROP_TAU for c in crop), default=0.0) for crop in classes]
    mean = sum(raw) / len(raw)
    return tuple(w / mean for w in raw)


@beartype
@require(lambda record: all(isinstance(v, (str, int)) for v in record.values()), "words and counts")
@ensure(lambda result: not problems(result), "the blocks returned hold")
def from_record(record: Mapping[str, object]) -> RenderBlocks:
    """The blocks a render's record names.

    :raises RenderBlockError: a record naming a block that does not exist, or choices that do not
        hold.
    """
    return parse([f"{key}={value}" for key, value in record.items()])
