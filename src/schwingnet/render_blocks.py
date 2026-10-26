"""The renderer's building blocks: each part of making a synthetic X-ray from a CT, chosen by name.

The owner's ask of 2026-10-25 (the thread "Compare FleXray DRRs to real X-ray corpora"): rendering
fits the block schema the trainer has (schwingnet.blocks), so a DRR dataset is a configuration of
named parts, and FleXray's published workflow is one configuration of them. An integration test
then renders a sample of FleXray's dataset from the same raw CTs through these blocks and sets it
beside FleXray's own renderer and its released FluXray set (tools/domain_gap.py, the bench id
flexray_drr_gap). The owner's two words of 2026-10-26 fix one more part: "WHEN REPLICATING THEIR
DATA SET YOU SHOULD USE MOOSE BUT FOR MY PRODUCTION RUNS I WANT SPINEPS, FURTHER THE SEGMENTATION
MODEL ON THE UNANNOTATED DATA SHOULD DEFINITELY BE A CONFIGURABLE BLOCK! MAKE SURE THE DIFFERNCE IN
THE LABELS IS HANDLED CORRECTLY EVERYWHERE!", and "MAKE SURE THESE USE SPINEPS SEGMENTATIONS AS
WELL NOT TOTAL SEGMENTATOR! EXISTING ONES IF POSSIBLE". A render names one choice per part:

- hu_window: "flexray" clips the CT to -1000 to 2000 HU and stores it as float16, as FleXray's
  packs do, or "none";
- air_clamp: "flexray" sets every voxel at or below -900 HU to -1000, as FleXray's CT loader does
  before rendering, or "none";
- crop: "flexray-axial" cuts the volume along its last voxel axis into 256-slice axial crops that
  cover it, the first and last touching its ends, neighbours at most 128 slices apart, the 50
  percent overlap FleXray's released packs were made with (the paper: "we divided each volume into
  overlapping 512 x 512 x 256 crops ... and limited crop-overlap to 50%"; src/fxr/datasets/
  ct_crops.py, plan_z_crops at max_overlap 0.5), each in the volume's own slice plane (the
  released crops are 512 x 512 x 256 only because MOOSE's CTs are 512 x 512 in-plane), a shorter
  volume being one crop padded with air on both sides and a crop holding no structure being
  dropped, as its packer drops it; "flexray-axial-min" the fewest such crops, plan_z_crops at its
  default max_overlap 0; or "whole";
- crop_sampler: "inverse-label-frequency" draws crops with FleXray's weights, each model class a
  crop holds contributing (N / n_c) ** 0.5 and the crop taking the largest, or "uniform";
- pose: "flexray-moose" draws the gantry angle over the full orbit, the tilt within 30 degrees,
  the source within 100 mm of the isocentre across and 500 to 900 mm away, a detector 1150 to
  1250 mm away with 1.25 to 2.25 mm pixels (FleXray's MOOSE profile, the online training
  renders; its default profile alone names no distance, pixel size or translation, so it is no
  choice); "fluxray-grid" draws one of the 90 fixed poses FluXray's raw renders were made from,
  uniformly, as a training draw of FluXray takes one of a subject's poses: y in 650, 900 and
  1150 mm, z in -300 to 200 mm by 100, alpha in 0, 45, -45, 90 and -90 degrees, x 0, beta and
  gamma 0, with the detector 1250 mm away and 0.6 mm pixels fixed by the choice (the paper's
  enhanced-DRR appendix; GRID_Y_MM, GRID_Z_MM, GRID_ALPHA_DEG, grid_pose);
- isocentre: "random-label" aims at the centroid of a structure the crop holds, drawn without
  replacement (FleXray's random_label), "vertebra" at a vertebra's, or "volume-centre" (the raw
  FluXray renders' choice);
- projection: "flexray-mix" is a cone beam nine times in ten and orthographic otherwise, "cone"
  always a cone beam;
- attenuation: "flexray-lognormal" multiplies each supervised structure's attenuation by a
  lognormal factor (mode 1, sigma 1, kept within 0.1 to 4) on half the renders, as FleXray's
  training does, or "off", the physical render and the raw FluXray renders' "fixed (default)
  attenuation";
- scale: "minmax", each render scaled to 0 to 1 on its own (FleXray's scale_rendered_images);
- edit: "none". FleXray's realism edit (FLUX.2 [klein]) is not in its code; it gets a name here
  when one exists to run;
- segmenter: which segmentation model's masks label the CTs, "spineps" (the default: the
  production runs, SPINEPS masks in the VerSe alphabet) or "moose" (moosez's masks, the model
  FleXray's own dataset was labelled with, so only when replicating it); the names, the
  alphabets and the maps are schwingnet.segmenters, and a label volume of either scheme holds
  MOOSE's stored ids, which is what FleXray's own code reads, L6 and the thirteenth ribs in it
  and dropped by FleXray's remap, T13 and the coccyx left out and recorded as unsupervised.

The settings: views a CT, the detector's side in pixels and the samples along each ray. The
detector is a count; the pixel size comes with the pose choice, drawn under flexray-moose and
0.6 mm under fluxray-grid, and the manifest records both.

The presets: DEFAULT is FleXray's released recipe for MOOSE 3.0 in every part but the segmenter,
the project's own (spineps), the configuration a production render takes; FLEXRAY is DEFAULT
with segmenter moose, FleXray's recipe to the bit, the replication's; PHYSICAL is DEFAULT with
the attenuation randomisation off, the render a comparison with real X-rays reads; FLUXRAY_RAW
is the raw render stream FluXray was edited from, by the paper: segmenter moose, the whole
volume, drawn uniformly, pose fluxray-grid, the volume's centre as the isocentre, a cone beam,
the attenuation randomisation off, min-max scaling, 4 views at a 1024-pixel detector. Every
image of the study, X-ray or DRR, is then clipped to its own 0.5 and 99.5 percentiles and
min-max scaled by tools/domain_gap.py's decoding, as the paper did to every image.

ENGINES names what runs a configuration: "blocks" is tools/render_blocks.py, one function per
choice above, and "flexray-runtime" is FleXray's own code for every step. Under pose
flexray-moose that is its crop planner, its crop weights, its label remap and its
SegmentationDRRRuntime, which honours only the choices FleXray's code makes, RUNTIME_CHOICES,
attenuation on or off being its gate's probability 0.5 or 0, and both segmenters, since each
hands it MOOSE stored ids. Under pose fluxray-grid FleXray's runtime cannot draw the grid, whose
PoseSampler knows fixed presets and random ranges, so the engine builds the request with the
explicit pose through fxr.drr's primitives (compute_isocenter at the volume's centre,
DRRRenderRequest with rot, xyz, the fixed sdd and delx, render_drr, scale_rendered_images), which
honours exactly FLUXRAY_RAW's parts, GRID_CHOICES. engine_problems says in words where a
configuration asks an engine for what it cannot do. The replication test of tools/domain_gap.py
renders the same CTs with FleXray's recipe through both engines and sets them beside each other.

The choices and the arithmetic that needs no torch (the crop plan, the crop weights, the grid's
poses) are kept here, under the gate's contracts; tools/render_blocks.py holds the torch side,
one function per name, and tests/test_flexray_render.py holds the two tables equal and this
module's crop plan and crop weights equal to FleXray's own.
"""

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, fields, replace
from typing import Any

from beartype import beartype
from beethoven_qa.contracts import ensure, require

from schwingnet import segmenters

HU_WINDOW = ("flexray", "none")
AIR_CLAMP = ("flexray", "none")
CROP = ("flexray-axial", "flexray-axial-min", "whole")
CROP_SAMPLER = ("inverse-label-frequency", "uniform")
POSE = ("flexray-moose", "fluxray-grid")
ISOCENTRE = ("random-label", "vertebra", "volume-centre")
PROJECTION = ("flexray-mix", "cone")
ATTENUATION = ("flexray-lognormal", "off")
SCALE = ("minmax",)
EDIT = ("none",)
SEGMENTER = segmenters.SEGMENTERS

# FleXray's packing: 256 slices a crop, along the volume's last voxel axis, in its own plane, and
# the overlap each axial choice plans with (plan_z_crops's max_overlap): the released packs' 50
# percent, or the fewest crops.
CROP_DEPTH = 256
CROP_OVERLAP = {"flexray-axial": 0.5, "flexray-axial-min": 0.0}
AXIAL_CROPS = tuple(CROP_OVERLAP)
# FleXray's crop weights: the tempering exponent, and the largest class weight is the crop's.
CROP_TAU = 0.5

# FluXray's raw render stream (the paper's enhanced-DRR appendix): the 90 fixed poses a CT as
# the Cartesian product of y, z and alpha in this order, x 0, beta and gamma 0, the detector
# 1250 mm from the source with 0.6 mm pixels.
GRID_Y_MM = (650.0, 900.0, 1150.0)
GRID_Z_MM = (-300.0, -200.0, -100.0, 0.0, 100.0, 200.0)
GRID_ALPHA_DEG = (0.0, 45.0, -45.0, 90.0, -90.0)
GRID_POSES = len(GRID_Y_MM) * len(GRID_Z_MM) * len(GRID_ALPHA_DEG)
GRID_SDD_MM = 1250.0
GRID_PIXEL_MM = 0.6

ENGINES = ("blocks", "flexray-runtime")
# The choices FleXray's own runtime makes under its MOOSE profile, so the only ones the
# flexray-runtime engine honours with pose flexray-moose.
RUNTIME_CHOICES = {
    "hu_window": ("flexray",),
    "air_clamp": ("flexray",),
    "crop": AXIAL_CROPS,
    "crop_sampler": ("inverse-label-frequency",),
    "pose": ("flexray-moose",),
    "isocentre": ("random-label",),
    "projection": ("flexray-mix",),
    "attenuation": ("flexray-lognormal", "off"),
    "scale": ("minmax",),
    "edit": ("none",),
    "segmenter": SEGMENTER,
}
# The choices FleXray's primitives honour with pose fluxray-grid: the raw FluXray stream's parts
# alone, since the explicit-pose path goes through no crop planner, no isocentre sampler and no
# attenuation gate of FleXray's.
GRID_CHOICES = {
    "hu_window": ("flexray",),
    "air_clamp": ("flexray",),
    "crop": ("whole",),
    "crop_sampler": ("uniform",),
    "pose": ("fluxray-grid",),
    "isocentre": ("volume-centre",),
    "projection": ("cone",),
    "attenuation": ("off",),
    "scale": ("minmax",),
    "edit": ("none",),
    "segmenter": SEGMENTER,
}


class RenderBlockError(ValueError):
    """A render block named that does not exist, or a setting outside its range, said in words."""


@dataclass(frozen=True)
class RenderBlocks:
    """One choice for each part of rendering; the defaults are FleXray's released MOOSE recipe
    with the project's own segmenter."""

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
    segmenter: str = segmenters.DEFAULT_SEGMENTER
    views: int = 4
    detector: int = 256
    ray_samples: int = 500


DEFAULT = RenderBlocks()
FLEXRAY = replace(DEFAULT, segmenter=segmenters.FLEXRAY_SEGMENTER)
PHYSICAL = replace(DEFAULT, attenuation="off")
FLUXRAY_RAW = RenderBlocks(
    crop="whole",
    crop_sampler="uniform",
    pose="fluxray-grid",
    isocentre="volume-centre",
    projection="cone",
    attenuation="off",
    scale="minmax",
    segmenter=segmenters.FLEXRAY_SEGMENTER,
    views=4,
    detector=1024,
)
PRESETS = {
    "default": DEFAULT,
    "flexray": FLEXRAY,
    "physical": PHYSICAL,
    "fluxray-raw": FLUXRAY_RAW,
}
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
    "segmenter": SEGMENTER,
}
# Each count with its inclusive range, for the checks and the listing.
COUNTS = {"views": (1, 100), "detector": (32, 1024), "ray_samples": (16, 4000)}
FIELDS = tuple(f.name for f in fields(RenderBlocks))

RULES = (
    "each part names one of its choices",
    "views is 1 to 100 renders a CT, detector 32 to 1024 pixels, ray_samples 16 to 4000",
    "crop_sampler=inverse-label-frequency weighs crops, so it goes with an axial crop choice",
    "segmenter=spineps is the production label scheme, segmenter=moose the replication's",
    "the flexray-runtime engine takes only the choices FleXray's own code makes, by the pose",
)


def _count_problems(blocks: RenderBlocks) -> list[str]:
    found = []
    for name, (low, high) in COUNTS.items():
        if not low <= getattr(blocks, name) <= high:
            found.append(f"{name} is a whole number from {low} to {high}")
    return found


@beartype
@ensure(lambda result: all(isinstance(line, str) and line for line in result), "each said in words")
@ensure(lambda result, blocks: blocks not in PRESETS.values() or not result, "every preset holds")
def problems(blocks: RenderBlocks) -> list[str]:
    """Every way the choices fall outside what exists, in words; empty when they hold."""
    found = [
        f"{name}={getattr(blocks, name)!r} is not one of {', '.join(allowed)}"
        for name, allowed in CHOICES.items()
        if getattr(blocks, name) not in allowed
    ]
    found += _count_problems(blocks)
    if blocks.crop_sampler == "inverse-label-frequency" and blocks.crop not in AXIAL_CROPS:
        found.append(
            "crop_sampler=inverse-label-frequency goes with crop=" + " or ".join(AXIAL_CROPS)
        )
    return found


@beartype
@ensure(lambda result: all(name in FIELDS for name in result), "each key is a render part")
@ensure(lambda result: all(allowed for allowed in result.values()), "each part keeps a choice")
def runtime_choices(blocks: RenderBlocks) -> dict[str, tuple[str, ...]]:
    """The choices FleXray's code honours for the pose named: its runtime's under flexray-moose,
    its primitives' under fluxray-grid."""
    return GRID_CHOICES if blocks.pose == "fluxray-grid" else RUNTIME_CHOICES


def _runtime_problems(blocks: RenderBlocks) -> list[str]:
    found = []
    grid = blocks.pose == "fluxray-grid"
    path = "with pose=fluxray-grid its explicit-pose path" if grid else "it"
    for name, allowed in runtime_choices(blocks).items():
        choice = getattr(blocks, name)
        if choice not in allowed:
            found.append(
                f"FleXray's runtime cannot honour {name}={choice!r}: {path} runs only "
                f"{', '.join(allowed)}"
            )
    return found


@beartype
@ensure(lambda result: all(isinstance(line, str) and line for line in result), "each said in words")
@ensure(
    lambda result, engine, blocks: engine != "blocks" or result == problems(blocks),
    "the blocks engine runs every configuration that holds",
)
@ensure(
    lambda result, engine, blocks: (
        engine not in ENGINES or blocks not in PRESETS.values() or not result
    ),
    "every preset runs in every engine",
)
def engine_problems(engine: str, blocks: RenderBlocks) -> list[str]:
    """Every way an engine cannot run the choices, in words, after the choices' own problems: an
    engine that does not exist, or a choice FleXray's code does not make under the pose named;
    empty when it can."""
    found = problems(blocks)
    if engine not in ENGINES:
        return found + [f"engine {engine!r} is not one of {', '.join(ENGINES)}"]
    if engine == "flexray-runtime":
        found += _runtime_problems(blocks)
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
@ensure(lambda result, pairs: bool(pairs) or result == DEFAULT, "no word is the default recipe")
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
@ensure(lambda result: all("=" in word for word in result), "each word is KEY=VALUE")
@ensure(lambda result, blocks: blocks != DEFAULT or not result, "the default needs no word")
def words_of(blocks: RenderBlocks) -> list[str]:
    """The KEY=VALUE words that name these blocks, only those that differ from DEFAULT."""
    record, default = as_record(blocks), as_record(DEFAULT)
    return [f"{name}={value}" for name, value in record.items() if value != default[name]]


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
    """Every plug-in point: the part, what it may be, and the default recipe's choice."""
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
@require(lambda overlap: 0.0 <= overlap < 1.0, "an overlap target from 0 up to but not 1")
@ensure(lambda result, depth: _crop_covers(depth, result), "the crops cover every slice")
@ensure(lambda result: result[0][0] == 0, "the first crop starts at the first slice")
def plan_crops(
    depth: int, overlap: float = CROP_OVERLAP["flexray-axial"]
) -> tuple[tuple[int, int, int, int], ...]:
    """FleXray's axial crops of CROP_DEPTH slices that cover a volume, as (start, stop, pad
    before, pad after), the arithmetic of fxr.datasets.ct_crops.plan_z_crops at max_overlap
    `overlap`: the first and last touch the ends, neighbours are at most
    ceil(CROP_DEPTH * (1 - overlap)) slices apart and the starts between are spread evenly (a
    700-slice volume starts at 0, 222 and 444 at overlap 0, the fewest crops, and at 0, 111,
    222, 333 and 444 at 0.5, the released packs' plan), and a volume shorter than a crop is one
    crop padded with air on both sides, the shorter pad first. The default overlap is the
    recipe's (crop=flexray-axial, 0.5), so a caller that names none plans the packs' crops;
    crop=flexray-axial-min names 0, FleXray's own default. Which crops are dropped for holding
    no structure is the engine's to say, since it reads the labels."""
    if depth <= CROP_DEPTH:
        before = (CROP_DEPTH - depth) // 2
        return ((0, depth, before, CROP_DEPTH - depth - before),)
    last = depth - CROP_DEPTH
    step = math.ceil(CROP_DEPTH * (1.0 - overlap))
    if last < step:
        starts = [0, last]
    else:
        intervals = math.ceil(last / step)
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
    """FleXray's crop sampling weights, the arithmetic of
    fxr.datasets.sampling.inverse_label_frequency_weights at tau 0.5 and class_aggregation max:
    each model class a crop holds contributes (N / n_c) ** tau, N the crops and n_c the crops
    holding the class, and the crop takes the largest; a crop with no model class weighs 0; the
    weights are scaled to average 1, as FleXray scales them."""
    holding: dict[int, int] = {}
    for crop in classes:
        for name in crop:
            holding[name] = holding.get(name, 0) + 1
    total = float(len(classes))
    raw = [max(((total / holding[c]) ** CROP_TAU for c in crop), default=0.0) for crop in classes]
    mean = sum(raw) / len(raw)
    return tuple(w / mean for w in raw)


@beartype
@require(lambda index: 0 <= index < GRID_POSES, "one of the 90 poses")
@ensure(lambda result: result[0] in GRID_ALPHA_DEG, "alpha from the grid")
@ensure(lambda result: result[1] in GRID_Y_MM and result[2] in GRID_Z_MM, "y and z from the grid")
def grid_pose(index: int) -> tuple[float, float, float]:
    """One of FluXray's 90 fixed poses as (alpha in degrees, y in mm, z in mm): the Cartesian
    product of y, then z, then alpha, in the paper's order, so index 0 is y 650, z -300, alpha
    0, index 1 the same at alpha 45, and index 5 z -200; x, beta and gamma are 0 for every pose,
    the detector GRID_SDD_MM from the source with GRID_PIXEL_MM pixels."""
    y_index, rest = divmod(index, len(GRID_Z_MM) * len(GRID_ALPHA_DEG))
    z_index, alpha_index = divmod(rest, len(GRID_ALPHA_DEG))
    return GRID_ALPHA_DEG[alpha_index], GRID_Y_MM[y_index], GRID_Z_MM[z_index]


@beartype
@require(lambda record: all(isinstance(v, (str, int)) for v in record.values()), "words and counts")
@ensure(lambda result: not problems(result), "the blocks returned hold")
def from_record(record: Mapping[str, object]) -> RenderBlocks:
    """The blocks a render's record names; a record written before the segmenter was a part
    names none and takes the default, spineps.

    :raises RenderBlockError: a record naming a block that does not exist, or choices that do not
        hold.
    """
    return parse([f"{key}={value}" for key, value in record.items()])
