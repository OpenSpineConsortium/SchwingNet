"""Train the level stage of SchwingNet v1 from a catalog, in the open, one epoch at a time.

Usage (inside the train-cpu or train-gpu environment):
    python tools/train.py --catalog <catalog.sqlite> --out <run dir> --epochs N --seed S
        [--weights <imagenet state_dict of the architecture>] [--size 64] [--batch 64] [--max-frames N]
        [--witness 12] [--device cpu|cuda] [--keep-epochs 1] [--resume]

The stage is the level classifier of docs/research/retraining-plan.md, section 3.4: a vertebral
body crop in, one of the 27 level names out. The crops come from the catalog's labels, so the
detector stage is not in this run and every number says so (docs/research/v1-demo). The trainer
reads frames through the catalog alone, train and validation parts only, never a test row, and
writes everything a reader needs to see the run rather than trust it: metrics.jsonl with one line
per epoch, a witness strip of the same fixed validation crops at every epoch with truth and
prediction on each, the accuracy curve, the best checkpoint with its sha256 and a model card. The
seed fixes every source of randomness torch exposes, and the run is refused unless its RUN.json
is there, since tools/flow.py writes that record from a clean tree before any step starts, and
unless --catalog has the sha256 that record names, since every number is stamped with it.

Evaluation is visible from the first frame (docs/research/retraining-plan.md, section 4): epoch 0
is the untrained network, scored and drawn like every other; every epoch's weights are kept under
train/epochs/ so the evaluator can draw the test witness frames over the same checkpoints at the
version boundary without the trainer ever reading a test row; the validation witness frames of
the run's witness.json (tools/witness.py) are drawn whole, every body boxed and named, at every
epoch, with each frame's strip and animation at the end; each epoch's line carries the
validation numbers per level, per source and for the transitional stratum; and the same lines
and pictures go to Weights and Biases offline (tools/wandb_log.py), pushed by the flow once the
step is done. The checkpoint is chosen on the whole validation part, never on the witness frames
alone, which are a small subset of it, and never on epoch 0.

A run that is cut, a Slurm job timed out or preempted, goes on where it stopped. After every
epoch, epoch 0 included, train/last.pt holds the weights, the optimiser's state, the prior head,
every random state the run draws from (its own generator, torch's, CUDA's, numpy's and python's)
and the lines so far, written whole, flushed to the disk and renamed into place, its sha256 in
train/last.pt.sha256 beside it; --resume, given with the arguments the run was started with (the
catalog, the ImageNet file and the parent held to their bytes, not to their paths, as
tools/flow.py names the run), builds the run as a fresh start does and then takes those states
back, so on the CPU a resumed run ends on the same lines, best.pt and checkpoint.json as one that
went through, the seconds apart. best.pt and prior_head.pt are written under train/pending/ and
moved into place only once last.pt records them, so a cut between the two never leaves weights
the record does not name. last.pt goes once checkpoint.json is written, the step's last file and
the one tools/flow.py takes as its end where it names the sha256 of the best.pt beside it
(checkpoint_facts), since last.pt holds the optimiser's state and is only for resuming; a
checkpoint.json that does not, for which the flow sends the run to train again, is moved aside to
checkpoint.json.unsound before the run trains. A last.pt the run cannot go on from, cut short,
emptied or with stretches of zeros a node that died left in it, which torch reads without a word,
so any whose bytes last.pt.sha256 does not name, or whose best line names weights best.pt does
not hold, is moved aside to last.pt.unreadable and the run trains from epoch 0 in the same call,
saying so in its log and on its card, since the flow resumes wherever last.pt is and a refusal
would come back on every start. Every file the run writes whole, best.pt and prior_head.pt among
them, is on the disk before the rename that puts it in place, so a node that dies leaves the old
file or the new one whole, never one in between. A run holds train/ by an exclusive lock on
train/.lock from before it reads a file there to its end, so a second trainer sent into the same
folder while the first still trains, as a flow started again after the flow of a live Slurm job
died would send one, is refused in words and touches nothing.

Batch norm in training needs more than one value per channel, and a batch of one small crop ends
on a map that gives it one: no architecture here can take a step on one 32-pixel crop, nor
densenet121 on one 48-pixel crop, while every one of them can on one 64-pixel crop. An epoch's last batch holds one crop whenever the
training crops are one more than a whole number of batches, so the run asks once whether its
model trains on one crop at its size (trains_on_one_crop) and, where it cannot, joins such a last
batch to the batch before it; checkpoint.json then says "single_crop_batch": "joined" and the card
says so. Where it can, the batches are as they always were, so a run that trained before trains
to the same weights; a run of exactly one training crop that cannot train on one is refused, and
so is --batch 1, whose every batch holds one crop.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Run as a script, this folder is first on the path, and tools/profile.py would then shadow the
# standard library's profile module, which torch imports; the package under src/ takes its place.
sys.path[0] = str(ROOT / "src")

import argparse  # noqa: E402
import contextlib  # noqa: E402
import copy  # noqa: E402
import fcntl  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import random  # noqa: E402
import re  # noqa: E402
import socket  # noqa: E402
import sqlite3  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
from schwingnet.blocks import BlockError, as_record, balanced_accuracy, from_record, kept, lr_factor, words_of  # noqa: E402
from schwingnet.blocks import parse as parse_blocks  # noqa: E402
from schwingnet.catalog import LEVELS, TRANSITIONAL  # noqa: E402
from schwingnet.flow import wilson  # noqa: E402
from schwingnet.witness import ROLE_VALIDATION  # noqa: E402
from torch import nn  # noqa: E402

PAD = 0.15
# What --resume reads (written after every epoch, deleted once checkpoint.json is written), the
# record of the bytes it may hold (save_last), and the folder best.pt and prior_head.pt wait in
# until last.pt records them.
LAST = "last.pt"
DIGESTS = f"{LAST}.sha256"
SHA256 = re.compile(r"[0-9a-f]{64}")
PENDING = "pending"
# The file a run holds train/ by for as long as it trains (held).
LOCK = ".lock"
STAGED = (("best.pt", "checkpoint_sha256"), ("prior_head.pt", "prior_head_sha256"))
TRAIN_PARTS = ("train", "validation")
SAMPLE_WORDS = ("samples", "sources", "per_person")
CROP_SQL = """
SELECT l.level, l.x0, l.y0, l.x1, l.y1, i.sha256, i.part, i.person, i.source, i.path, s.manifest,
       {level_map} AS level_map
FROM label l
JOIN item i ON i.sha256 = l.item AND i.shard = l.shard
JOIN shard s ON s.name = i.shard
WHERE i.part IN ({marks})
ORDER BY i.sha256, l.level
"""


def load_tool(name):
    """A sibling tool by its file, since this folder is off the path (above)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(f"schwingnet_tool_{name}", ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BLOCKS = load_tool("train_blocks")


class TrainError(Exception):
    """What stops a training run with a reason a person reads, not a traceback."""


def has_column(db, table, column):
    return any(row[1] == column for row in db.execute(f"PRAGMA table_info({table})"))


def read_crops(catalog, parts):
    """Every labelled body in the named parts: level, unit box, frame path, person, source, and
    the frame's level map's path where the frame has one (None otherwise, and in every crop of a
    catalog built before the column existed, which reads as before)."""
    db = sqlite3.connect(f"file:{catalog}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    marks = ", ".join("?" for _ in parts)
    level_map = "i.level_map" if has_column(db, "item", "level_map") else "NULL"
    rows = db.execute(CROP_SQL.format(marks=marks, level_map=level_map), parts).fetchall()
    db.close()
    crops = []
    for row in rows:
        shard = Path(row["manifest"]).parent
        crops.append(
            {
                "level": row["level"],
                "box": (row["x0"], row["y0"], row["x1"], row["y1"]),
                "frame": str(shard / row["path"]),
                "part": row["part"],
                "person": row["person"],
                "source": row["source"],
                "sha256": row["sha256"],
                "map": str(shard / row["level_map"]) if row["level_map"] else None,
            }
        )
    return crops


def crop_pixels(frame, box, size):
    """The body's crop as a size-by-size float array in 0..1, padded a little around the box."""
    return crop_of_image(Image.open(frame).convert("L"), box, size)


def crop_box(image_size, box):
    """The pixel box a unit box cuts from a frame of this size, padded a little around it."""
    width, height = image_size
    x0, y0, x1, y1 = box
    pad_x, pad_y = (x1 - x0) * PAD, (y1 - y0) * PAD
    return (
        max(0, int((x0 - pad_x) * width)),
        max(0, int((y0 - pad_y) * height)),
        min(width, int((x1 + pad_x) * width) + 1),
        min(height, int((y1 + pad_y) * height) + 1),
    )


def crop_of_image(image, box, size):
    """crop_pixels on a frame already decoded, so a frame's bodies share one decode."""
    crop = image.crop(crop_box(image.size, box)).resize((size, size), Image.BILINEAR)
    return np.asarray(crop, dtype=np.float32) / 255.0


def map_of_image(image, box, size):
    """The crop's level map, cut as crop_of_image cuts the crop and resized nearest, so every
    pixel stays a level's code and no code is blended with its neighbour's."""
    crop = image.crop(crop_box(image.size, box)).resize((size, size), Image.NEAREST)
    return np.asarray(crop, dtype=np.int64)


def load_crops(crops, size, frames_cache):
    """A tensor of crops and a tensor of level indices.

    A frame is decoded once for a run of its bodies: read_crops orders the crops by frame, and a
    frame holds several bodies, so decoding it per body did the same work several times over.
    Only the last frame is kept, so a shuffled list (pick's dry-run cap) costs no more memory
    than before. frames_cache counts the crops read and the frames decoded.
    """
    arrays, targets = [], []
    current, image = None, None
    for crop in crops:
        if crop["frame"] != current:
            current, image = crop["frame"], Image.open(crop["frame"]).convert("L")
            frames_cache["decoded"] = frames_cache.get("decoded", 0) + 1
        arrays.append(crop_of_image(image, crop["box"], size))
        targets.append(LEVELS.index(crop["level"]))
    stack = torch.from_numpy(np.stack(arrays)).unsqueeze(1).repeat(1, 3, 1, 1)
    frames_cache["opened"] = frames_cache.get("opened", 0) + len(crops)
    return stack, torch.tensor(targets, dtype=torch.long)


def read_map(crop):
    """The frame's level map decoded, refused where it is not a map of this frame: the ingest
    checked the shard's maps, and a map from anywhere else is checked here the same way."""
    image = Image.open(crop["map"])
    if image.mode != "L":
        raise TrainError(f"{crop['map']}: a level map is an 8-bit greyscale PNG, not mode {image.mode}")
    with Image.open(crop["frame"]) as frame:
        frame_size = frame.size
    if image.size != frame_size:
        raise TrainError(f"{crop['map']}: the level map is {image.size}, the frame {frame_size}")
    highest = image.getextrema()[1]
    if highest > len(LEVELS):
        raise TrainError(f"{crop['map']}: the level map holds the value {highest}; a level's code is 1 to {len(LEVELS)}")
    return image


def load_maps(crops, size):
    """The crops' level maps as one tensor of level codes, 0 for no vertebra and 1 to 27 for
    LEVELS in order, and IGNORED at every pixel of a crop whose frame has no map, which the
    prior's loss leaves out; a map is decoded once for a run of its frame's bodies, as load_crops
    decodes a frame once. The codes are held in a byte each, since 100,000 crops at 64 pixels
    would hold 3 GB of maps as eight-byte integers; a batch is widened on the device."""
    maps = np.full((len(crops), size, size), BLOCKS.IGNORED, dtype=np.int8)
    current, image = None, None
    for n, crop in enumerate(crops):
        if not crop.get("map"):
            continue
        if crop["map"] != current:
            current, image = crop["map"], read_map(crop)
        maps[n] = map_of_image(image, crop["box"], size)
    return torch.from_numpy(maps)


def with_map(crops):
    """How many of the crops come from a frame with a level map."""
    return sum(1 for crop in crops if crop.get("map"))


# cuBLAS gives the same sums run to run only with a fixed workspace, set before CUDA starts; without
# it use_deterministic_algorithms, here only warning, lets a GPU run differ in its last bits.
CUBLAS_WORKSPACE = ":4096:8"


def seed_everything(seed):
    """One seed for python, numpy and torch, and deterministic kernels where torch has them.

    Called before the model reaches the device, so the cuBLAS workspace is fixed before CUDA
    starts; a value the caller's environment already sets is kept. cuDNN's benchmark search,
    which may pick a different kernel each run, stays off.
    """
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", CUBLAS_WORKSPACE)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.backends.cudnn.benchmark = False
    torch.use_deterministic_algorithms(True, warn_only=True)


def build_model(weights, device, normalise="none", architecture="resnet18", denoise="none"):
    """The named backbone with a 27-way head; ImageNet weights come from a file, never a download.

    The three are the run's blocks of those names (src/schwingnet/blocks.py): the architecture's
    table entry builds the network, and denoise and normalise are hooks inside the model, in that
    order, so whatever calls the model filters and scales the input the same way."""
    try:
        model = BLOCKS.ARCHITECTURES[architecture](len(LEVELS), weights)
    except BLOCKS.ArchitectureError as error:
        raise TrainError(str(error)) from error
    model = BLOCKS.DENOISERS[denoise](model)
    return BLOCKS.NORMALISERS[normalise](model).to(device)


def model_for(facts, device):
    """An untrained model shaped as a run's checkpoint.json says, its weights to be loaded; a
    checkpoint from before the blocks existed names none and gets version 1's model."""
    blocks = from_record(facts.get("blocks"))
    return build_model(None, device, blocks.normalise, blocks.architecture, blocks.denoise)


# What a parent checkpoint must share with the run that starts from it: its weights are only right
# for the network they were trained in and for the input that network saw.
INHERITED = ("architecture", "denoise", "normalise")


def parent_of(path):
    """What a parent checkpoint is: its sha256, and, where it sits in a run directory as
    <run>/train/best.pt or <run>/train/epochs/epoch-NN.pt, that run's id and blocks. The path is
    read where it leads, so a link to the file finds the run it is in, as its real path does,
    where read beside the link it named no run and warm_start checked none of the parent's blocks."""
    typed = Path(path)
    if not typed.is_file():
        raise TrainError(f"{typed}: no parent checkpoint there")
    path = typed.resolve()
    folder = path.parent.parent if path.parent.name == "epochs" else path.parent
    run_file, facts_file = folder.parent / "RUN.json", folder / "checkpoint.json"
    run_id = json.loads(run_file.read_text(encoding="utf-8")).get("run_id") if run_file.is_file() else None
    facts = json.loads(facts_file.read_text(encoding="utf-8")) if facts_file.is_file() else None
    return {"file": path.name, "sha256": sha256_of(path), "run_id": run_id, "facts": facts}


def warm_start(model, path, parent, blocks, size):
    """The parent's weights in place of ImageNet's, refused where the parent was trained to see
    its input differently: another scaling or another crop size would make its features wrong."""
    facts = parent["facts"]
    if facts is not None:
        theirs = from_record(facts.get("blocks"))
        for name in INHERITED:
            if getattr(theirs, name) != getattr(blocks, name):
                raise TrainError(f"the parent was trained with {name}={getattr(theirs, name)}, this run names {name}={getattr(blocks, name)}")
        if int(facts.get("size", size)) != size:
            raise TrainError(f"the parent was trained on {facts['size']}-pixel crops, this run on {size}")
    state = torch.load(path, map_location="cpu", weights_only=True)
    try:
        model.load_state_dict(state)
    except RuntimeError as error:
        raise TrainError(f"{path}: not a level stage of this shape ({str(error).splitlines()[0]})") from error


def predict(model, inputs, device, batch, after_batch=None):
    """Predicted level indices for a tensor of crops, in batches, with no gradient; after_batch,
    where given, is called with each batch's first and last index once the model has seen it,
    which is how the prior head scores its maps on the same forward (MapTally)."""
    model.eval()
    guesses = []
    with torch.no_grad():
        for start in range(0, len(inputs), batch):
            logits = model(inputs[start : start + batch].to(device))
            guesses.append(logits.argmax(dim=1).cpu())
            if after_batch is not None:
                after_batch(start, start + len(logits))
    return torch.cat(guesses) if guesses else torch.zeros(0, dtype=torch.long)


def batch_loss(model, loss_fn, crops, labels, maps, generator, blocks, prior):
    """One batch's loss: the level loss, and with the prior block on, prior_weight times the
    head's loss against the crops' level maps, the maps moved with the crops by the jitter."""
    if blocks.augment and prior is None:
        crops = BLOCKS.augment(crops, blocks.augment, generator)
    elif blocks.augment:
        crops, maps = BLOCKS.augment_with_maps(crops, maps, blocks.augment, generator)
    loss = loss_fn(model(crops), labels)
    if prior is not None:
        loss = loss + blocks.prior_weight * prior.loss(maps)
    return loss


def trains_on_one_crop(model, size):
    """Whether the model takes a training step on a batch of one crop of this size.

    Batch norm in training needs more than one value per channel, and one small crop's deepest map
    is 1 by 1, which gives it one: measured on CPU, every architecture here raises on one 32-pixel
    crop and densenet121 on one 48-pixel crop too, while all of them train on one 64-pixel crop. Asked
    of a deep copy in training mode, with no gradient and inside fork_rng, since a dropout draws in
    training, so neither the model nor any random state the run draws from moves. A model that
    cannot forward a crop of this size at all is not this question: it fails where it failed
    before, in the prior head's words or at its first batch."""
    device = next(model.parameters()).device
    devices = [device.index if device.index is not None else torch.cuda.current_device()] if device.type == "cuda" else []
    probe = copy.deepcopy(model).train()
    try:
        with torch.random.fork_rng(devices=devices), torch.no_grad():
            probe(torch.zeros(1, 3, size, size, device=device))
    except ValueError:
        return False
    except RuntimeError:
        return True
    return True


def ends_on_one(count, batch):
    """Whether an epoch over count crops ends on a batch of one: one more than whole batches."""
    return count > batch and count % batch == 1


def batch_bounds(count, batch, join_single=False):
    """Each training batch's first and past-last place in the sampler's order: batch crops at a
    time and the rest last, as version 1 cut them, and where join_single, a last batch of one crop
    joined to the batch before it, for a model that cannot train on one (trains_on_one_crop)."""
    starts = list(range(0, count, batch))
    if join_single and ends_on_one(count, batch):
        starts.pop()
    stops = [*starts[1:], count] if starts else []
    return list(zip(starts, stops, strict=True))


def refuse_one_crop(count, batch, join_single, why):
    """A training part of exactly one crop, or --batch 1, where the model cannot train on one is
    refused before any epoch, since there is no batch to join the crop to and the first step would
    fail; why is the model's reason (one_crop_words), the same in both refusals."""
    if not join_single:
        return
    if count == 1:
        raise TrainError(f"one training crop: {why}; take more crops, or 64-pixel crops, on which every architecture here trains on one")
    if batch == 1:
        raise TrainError(f"--batch 1: every batch holds one crop, and {why}; take a batch of 2 or more, or 64-pixel crops, on which every architecture here trains on one")


def one_crop_words(architecture, size):
    """Why the model cannot train on one crop, in the words both refusals give."""
    return f"{architecture} cannot take a training step on a batch of one {size}-pixel crop, since batch norm needs more than one value per channel there"


def train_epoch(model, optimiser, inputs, targets, device, batch, generator, blocks=None, loss_fn=None, maps=None, prior=None, join_single=False):
    """One pass over the training crops in an order the sampler draws; returns the mean loss.

    With no blocks, version 1's epoch: every crop once in a seeded order, no change to a crop,
    plain cross-entropy. The run's blocks choose the sampler, the changes made to each batch and
    the loss (tools/train_blocks.py); with the prior block on, maps are the crops' level maps
    (load_maps) and prior the head that scores the backbone against them. join_single joins a last
    batch of one crop to the one before (batch_bounds); without it the batches are version 1's."""
    model.train()
    blocks = blocks or from_record(None)
    loss_fn = loss_fn or nn.CrossEntropyLoss()
    order = BLOCKS.SAMPLERS[blocks.sampler](targets, generator)
    total = 0.0
    for start, stop in batch_bounds(len(order), batch, join_single):
        index = order[start:stop]
        optimiser.zero_grad()
        crops = inputs[index].to(device)
        batch_maps = maps[index].to(device).long() if prior is not None else None
        loss = batch_loss(model, loss_fn, crops, targets[index].to(device), batch_maps, generator, blocks, prior)
        loss.backward()
        optimiser.step()
        total += float(loss.detach()) * len(index)
    return total / max(1, len(order))


class MapTally:
    """The prior head's score over the validation maps, counted batch by batch on the forward
    predict makes, so the validation tensor is forwarded once an epoch for the prediction and the
    tally (the witness frames, validation crops the Witness holds as tensors of its own, are the
    one other forward): the share of the labelled pixels
    the head names right, and the share of the vertebral pixels, codes 1 to 27, it names right,
    which a head that says background at every pixel scores 0 on while its pixel accuracy is the
    background's share, so the two together tell learning from collapse. Numbers for the curve,
    choosing nothing; None where no crop carries a map."""

    def __init__(self, prior, maps, device):
        self.prior, self.maps, self.device = prior, maps, device
        self.right = self.total = self.body_right = self.body_total = 0

    def __call__(self, start, stop):
        labels = self.maps[start:stop].to(self.device).long()
        mask = labels != BLOCKS.IGNORED
        if not bool(mask.any()):
            return
        hit = self.prior.logits().argmax(dim=1) == labels
        body = labels > 0
        self.right += int(hit[mask].sum())
        self.total += int(mask.sum())
        self.body_right += int(hit[body].sum())
        self.body_total += int(body.sum())

    def numbers(self):
        return {
            "validation_map_pixel_accuracy": self.right / self.total if self.total else None,
            "validation_map_body_accuracy": self.body_right / self.body_total if self.body_total else None,
        }


def witness_strip(crops, inputs, guesses, path):
    """The same validation crops every epoch, truth over prediction, so a reader sees learning."""
    size = inputs.shape[-1]
    cell = size + 4
    strip = Image.new("L", (cell * len(crops), size + 30), 255)
    draw = ImageDraw.Draw(strip)
    for n, crop in enumerate(crops):
        tile = Image.fromarray((inputs[n, 0].numpy() * 255).astype(np.uint8))
        strip.paste(tile, (n * cell + 2, 0))
        guess = LEVELS[int(guesses[n])]
        mark = "" if guess == crop["level"] else " x"
        draw.text((n * cell + 2, size + 2), crop["level"], fill=0)
        draw.text((n * cell + 2, size + 15), guess + mark, fill=0)
    strip.save(path)


def accuracy_curve(history, path):
    """Validation accuracy with its interval, epoch by epoch, as one figure."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    epochs = [h["epoch"] for h in history]
    acc = [h["validation_accuracy"] for h in history]
    low = [h["validation_ci"][0] for h in history]
    high = [h["validation_ci"][1] for h in history]
    figure, axis = plt.subplots(figsize=(6, 3.5))
    axis.fill_between(epochs, low, high, alpha=0.2, label="95% Wilson interval")
    axis.plot(epochs, acc, marker="o", label="validation accuracy")
    trained = [h for h in history if h["train_loss"] is not None]
    peak = max([1e-9, *(h["train_loss"] for h in trained)])
    axis.plot([h["epoch"] for h in trained], [h["train_loss"] / peak for h in trained], linestyle="--", label="train loss (scaled)")
    axis.set_xlabel("epoch")
    axis.set_ylim(0, 1)
    axis.legend(loc="lower right")
    figure.tight_layout()
    figure.savefig(path, dpi=120)
    plt.close(figure)


def seen_words(counts, blocks):
    """The training crops the samples block kept of those the catalog offered, and what a
    --max-frames cap then cut, apart, so the record never credits the block with a dry run's
    cut."""
    text = f"{counts['train_seen']} of the {counts['train_offered']} the catalog's train part holds (samples {blocks.samples})"
    if counts["train"] < counts["train_seen"]:
        text += f", capped to {counts['train']} by --max-frames"
    return text + f", from {counts['train_persons']} persons"


def validation_words(counts):
    """The validation crops read: the whole part, or what --max-frames left of it."""
    if counts["validation"] == counts["validation_offered"]:
        part = "the whole part"
    else:
        part = f"of the {counts['validation_offered']} the part holds, capped by --max-frames"
    return f"{counts['validation']}, {part}, from {counts['validation_persons']} persons"


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parent_record(parent):
    """The parent as checkpoint.json keeps it, None for a run from ImageNet or from scratch."""
    return None if parent is None else {"file": parent["file"], "sha256": parent["sha256"], "run_id": parent["run_id"]}


def start_line(args, parent):
    """Where the weights began: a parent run (an incremental run), ImageNet or nothing."""
    if parent:
        named = f"run {parent['run_id']}, " if parent["run_id"] else ""
        return f"parent checkpoint ({named}{parent['file']}, sha256 {parent['sha256'][:12]}): an incremental run"
    if args.weights:
        return "ImageNet file " + sha256_of(args.weights)[:12] + ": a rebase"
    return "none (from scratch): a rebase"


def model_card(out, args, run, counts, best, elapsed, blocks, parent=None, notes=()):
    """MODEL.md: what the checkpoint is, what it saw, what it scored, and what it is not; notes are
    the lines on how this run's training differed in its batches or was resumed (batch_lines,
    resume_lines)."""
    lines = [
        "# SchwingNet v1, level stage",
        "",
        f"- Run: {run['run_id']} (commit {run['code_commit']}, catalog sha256 {run['catalog_sha256'][:12]})",
        f"- Stage: level classifier over truth boxes; the detector stage is not in this checkpoint.",
        f"- Architecture: {BLOCKS.architecture_words(blocks.architecture)}, {len(LEVELS)}-way head, crops {args.size}x{args.size}, pad {PAD}.",
        f"- Initial weights: {start_line(args, parent)}.",
        f"- Seed {args.seed}; epochs {args.epochs}; batch {args.batch}; learning rate {args.lr}; device {args.device}.",
        "- Blocks: " + "; ".join(f"{k} {','.join(v) if isinstance(v, list) else v}" for k, v in as_record(blocks).items()) + ".",
        f"- Training crops {seen_words(counts, blocks)}; validation crops {validation_words(counts)}; no test row was read.",
        *prior_lines(blocks, counts, best, args.size, parent),
        *notes,
        f"- Best epoch {best['epoch']}: validation accuracy {best['validation_accuracy']:.3f} ({best['validation_ci'][0]:.3f} to {best['validation_ci'][1]:.3f}, n={best['validation_n']}).",
        f"- Checkpoint best.pt sha256 {best['checkpoint_sha256']}; wall time {elapsed:.0f} s.",
        "- Levels: " + ", ".join(LEVELS) + f"; transitional {', '.join(TRANSITIONAL)}.",
        "",
        "Every number above is reproduced by tools/flow.py run with the same catalog, commit and seed.",
    ]
    (out / "MODEL.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def prior_lines(blocks, counts, best, size, parent=None):
    """The card's line on the prior block where the run used it: what the head read and how many
    cells it kept across the crop, its weight, how many crops carried a map, since a crop without
    one taught the head nothing, that train_loss holds the map loss too, so the column is not the
    control run's, and under --init that the head began from scratch, since warm_start reads the
    parent's best.pt alone and a parent's prior_head.pt is not read."""
    if blocks.prior == "none":
        return []
    cells = best["prior_cells"]
    fresh = "; the head began from scratch, since a parent's prior_head.pt is not read" if parent else ""
    return [
        f"- Prior: level-map head on {best['prior_stage']} ({cells[0]} by {cells[1]} cells of the {size}-pixel crop,"
        f" {len(LEVELS) + 1} classes at every pixel, weight {blocks.prior_weight}); {counts['train_with_map']} of the"
        f" {counts['train']} training crops and {counts['validation_with_map']} of the {counts['validation']} validation"
        " crops carried a map; the head is not in best.pt (prior_head.pt beside it); train_loss is the level loss plus"
        f" {blocks.prior_weight} times the map loss, not the control run's level loss alone{fresh}."
    ]


def batch_lines(joined, blocks, args):
    """The card's line on a joined batch where the run joined one: why its last batch is larger."""
    if not joined:
        return []
    return [
        f"- Batches: {blocks.architecture} cannot train on one {args.size}-pixel crop (batch norm needs more than one"
        f" value per channel), so each epoch's last batch of one crop joined the batch before it, which then held {args.batch + 1}."
    ]


def restart_lines(why):
    """The card's line on a resume that could not go on from last.pt and started again, with why
    (read_last)."""
    if not why:
        return []
    return [
        f"- Restarted from epoch 0: train/last.pt could not be resumed from ({why}), so it was moved aside to"
        f" train/{LAST}.unreadable and the run trained from the start, as a fresh start trains."
    ]


def resume_lines(resumed):
    """The card's line on the cuts the run was resumed after, where it was."""
    if not resumed:
        return []
    word = "epoch" if len(resumed) == 1 else "epochs"
    return [
        f"- Resumed after {word} {', '.join(str(epoch) for epoch in resumed)}: continued from train/last.pt (the weights,"
        " the optimiser's state, the prior head and every random state the run draws from), so the epochs after a cut"
        " drew what an uncut run draws."
    ]


def person_count(crops):
    return len({c["person"] for c in crops})


def parse(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--out", required=True, help="the run directory tools/flow.py made")
    parser.add_argument("--epochs", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--weights", default=None, help="an ImageNet state_dict file of the run's architecture block (resnet18 unless --block architecture=... says otherwise)")
    parser.add_argument("--size", type=int, default=64)
    parser.add_argument("--batch", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--max-frames", type=int, default=0, help="cap the crops per part, for a dry run")
    parser.add_argument("--witness", type=int, default=12)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--keep-epochs", type=int, default=1, help="1 keeps every epoch's weights for the evaluator's test witness frames")
    parser.add_argument("--init", default=None, help="a parent checkpoint (best.pt or an epoch's weights) to start from instead of ImageNet: an incremental run (docs/research/retraining-plan.md, section 3.4)")
    parser.add_argument("--block", action="append", default=[], metavar="KEY=VALUE", help="one choice of a building block (src/schwingnet/blocks.py), such as normalise=imagenet or augment=box-jitter,intensity; none gives version 1's training")
    parser.add_argument("--resume", action="store_true", help="go on from train/last.pt where a cut run stopped, given the arguments the run was started with")
    return parser.parse_args(argv)


def pick(crops, part, cap, seed):
    """The crops of one part, capped in a seeded order so a dry run reads a fixed subset."""
    chosen = [c for c in crops if c["part"] == part]
    if cap and len(chosen) > cap:
        random.Random(seed).shuffle(chosen)
        chosen = chosen[:cap]
    return chosen


def training_crops(crops, blocks):
    """The train part as the samples block leaves it, in the catalog's order, with the count the
    part held before, so the record says what the run saw of what it could have seen. A source
    the part does not hold is refused, since a cut named for it would be recorded and never
    made (kept cannot know the catalog; here the offered crops are in hand)."""
    offered = [c for c in crops if c["part"] == "train"]
    present = {c["source"] for c in offered}
    absent = [s for s in blocks.sources if s not in present]
    if absent:
        raise TrainError(f"sources={','.join(absent)}: not in the catalog's train part, whose sources are {', '.join(sorted(present)) or 'none'}")
    keep = kept(blocks, [c["source"] for c in offered], [c["person"] for c in offered])
    return [c for c, k in zip(offered, keep, strict=True) if k], len(offered)


def strata_of(crops, guesses):
    """Correct and total per level, per source and for the transitional stratum, apart."""
    out = {"level": {}, "source": {}, "transitional": [0, 0]}
    for crop, guess in zip(crops, guesses, strict=True):
        right = int(LEVELS[int(guess)] == crop["level"])
        for kind, name in (("level", crop["level"]), ("source", crop["source"])):
            cell = out[kind].setdefault(name, [0, 0])
            cell[0] += right
            cell[1] += 1
        if crop["level"] in TRANSITIONAL:
            out["transitional"][0] += right
            out["transitional"][1] += 1
    return out


def marks_of(crops, guesses):
    """Per frame, each body's unit box with its true and predicted name, for drawing."""
    marks = {}
    for crop, guess in zip(crops, guesses, strict=True):
        marks.setdefault(crop["sha256"], []).append((crop["box"], crop["level"], LEVELS[int(guess)]))
    return marks


class Witness:
    """The run's validation witness frames: their crops loaded once, drawn at every epoch."""

    def __init__(self, out, crops, size):
        self.folder = out / "train" / "witness" / "frames"
        listing = out / "witness.json"
        document = json.loads(listing.read_text(encoding="utf-8")) if listing.is_file() else {"frames": []}
        self.frames = [f for f in document["frames"] if f["role"] == ROLE_VALIDATION]
        keys = {f["sha256"] for f in self.frames}
        self.crops = [c for c in crops if c["sha256"] in keys]
        self.inputs = load_crops(self.crops, size, {})[0] if self.crops else None
        self.tool = load_tool("witness") if self.crops else None
        self.epochs = []

    def draw(self, model, device, batch, epoch):
        """Each frame at this epoch, and the witness frames' own score, which chooses nothing."""
        if self.inputs is None:
            return None
        guesses = predict(model, self.inputs, device, batch)
        scores = self.tool.draw_checkpoint(self.frames, marks_of(self.crops, guesses), epoch, self.folder)
        self.epochs.append(epoch)
        return [sum(v[0] for v in scores.values()), sum(v[1] for v in scores.values())]

    def finish(self):
        if self.epochs:
            self.tool.finish(self.folder, self.frames, self.epochs)

    def media(self, epoch):
        """The epoch's sheet path and each frame's file, by W&B name."""
        named = {f"witness/validation/{f['key']}": self.folder / f["key"] / f"epoch-{epoch:02d}.png" for f in self.frames}
        return named


def epoch_line(epoch, loss, guesses, val_y, val_crops, started, witness_score, learning_rate=None, prior_numbers=None):
    """One line of metrics.jsonl: the whole validation part, its strata and the witness score,
    and with the prior block on its two numbers (prior_numbers, from prior_line)."""
    correct = int((guesses == val_y).sum())
    low, high = wilson(correct, len(val_y))
    strata = strata_of(val_crops, guesses)
    return {
        "epoch": epoch,
        "train_loss": loss,
        "learning_rate": learning_rate,
        **(prior_numbers or {}),
        "validation_accuracy": correct / len(val_y),
        "validation_balanced_accuracy": balanced_accuracy(strata["level"]),
        "validation_ci": [low, high],
        "validation_n": len(val_y),
        "validation_strata": strata,
        "witness_validation": witness_score,
        "seconds": round(time.monotonic() - started, 1),
    }


def prior_line(prior, tally):
    """The prior block's numbers for the epoch's line: the mean prior loss of the training batches
    that carried a map (None at epoch 0 and where none did) and the head's pixel and vertebral-pixel
    accuracy over the validation crops' maps (MapTally); nothing where the run has no prior."""
    if prior is None:
        return None
    return {"train_prior_loss": prior.mean_and_reset(), **tally.numbers()}


def wandb_values(line):
    """The epoch's numbers as flat W&B keys."""
    values = {"train/loss": line["train_loss"], "train/learning_rate": line.get("learning_rate"), "validation/balanced_accuracy": line.get("validation_balanced_accuracy"), "validation/accuracy": line["validation_accuracy"], "validation/ci_low": line["validation_ci"][0], "validation/ci_high": line["validation_ci"][1], "train/prior_loss": line.get("train_prior_loss"), "validation/map_pixel_accuracy": line.get("validation_map_pixel_accuracy"), "validation/map_body_accuracy": line.get("validation_map_body_accuracy")}
    for kind in ("level", "source"):
        for name, (right, total) in line["validation_strata"][kind].items():
            values[f"validation/{kind}/{name}"] = right / total
    if line["witness_validation"]:
        right, total = line["witness_validation"]
        values["witness/validation_correct"] = right / max(1, total)
    return {k: v for k, v in values.items() if v is not None}


def set_rate(optimiser, base_rates, factor):
    """Each group's rate at its base times the schedule's factor; returns the head's rate, the
    last group's, which is the base rate itself before the factor."""
    for group, base in zip(optimiser.param_groups, base_rates, strict=True):
        group["lr"] = base * factor
    return optimiser.param_groups[-1]["lr"]


def chosen_by(line, blocks):
    """The number the select block chooses the checkpoint by; ties keep the earlier epoch."""
    if blocks.select == "balanced-accuracy":
        return line["validation_balanced_accuracy"]
    return line["validation_accuracy"]


def checkpoint(model, folder, epoch, keep):
    """Every epoch's weights under epochs/ where kept, so the test witness frames replay them."""
    if keep:
        (folder / "epochs").mkdir(exist_ok=True)
        torch.save(model.state_dict(), folder / "epochs" / f"epoch-{epoch:02d}.pt")


def prior_of(blocks, model, train_crops, val_crops, args):
    """The prior block's tensors and head where the run names it: the training and validation
    crops' level maps and the head on the model, or three Nones. A run whose training crops carry
    no map is refused, since the head would learn from nothing and the record would say the prior
    was on."""
    if blocks.prior == "none":
        return None, None, None
    if not with_map(train_crops):
        raise TrainError("prior=level-map: no training crop comes from a frame with a level map; a map rides in a render's or a registered frame's shard (tools/ingest.py, docs/research/experiment-framework.md)")
    maps, val_maps = load_maps(train_crops, args.size), load_maps(val_crops, args.size)
    try:
        prior = BLOCKS.PriorHead(model, blocks.architecture, args.size, len(LEVELS) + 1).to(args.device)
    except BLOCKS.ArchitectureError as error:
        raise TrainError(str(error)) from error
    return maps, val_maps, prior


def head_checkpoint(prior, folder):
    """The prior head's weights beside best.pt, with their digest, the stage it read and the cells
    it kept for the record; nothing with no prior."""
    if prior is None:
        return {}
    torch.save(prior.state_dict(), folder / "prior_head.pt")
    return {"prior_head_sha256": sha256_of(folder / "prior_head.pt"), "prior_stage": prior.stage, "prior_cells": list(prior.cells)}


def stage_best(model, prior, folder, line):
    """The epoch's line as the new best, its weights and the prior head's saved under pending/ by
    the names they will have in place, so their bytes and digests are those best.pt and
    prior_head.pt will hold (torch.save names its archive after the file); settle moves them in
    once last.pt records them. They are on the disk before last.pt, which names their digests, is
    renamed into place, so a node that dies after that rename leaves them whole (synced)."""
    pending = folder / PENDING
    pending.mkdir(exist_ok=True)
    torch.save(model.state_dict(), pending / "best.pt")
    best = dict(line, checkpoint_sha256=sha256_of(pending / "best.pt"), **head_checkpoint(prior, pending))
    synced(*(pending / name for name, _ in STAGED if (pending / name).is_file()), pending, folder)
    return best


def settle(folder, best):
    """Each staged file moved into place where the best line names its digest, and dropped where
    it does not: a run cut after staging and before last.pt landed redoes that epoch, and one cut
    after last.pt landed and before the move finds the move still to make. The moves are on the
    disk before the run goes on, so checkpoint.json, written last, never names a best.pt a node
    that died left under pending/."""
    touched = False
    for name, key in STAGED:
        staged = folder / PENDING / name
        if not staged.is_file():
            continue
        if best is not None and best.get(key) == sha256_of(staged):
            os.replace(staged, folder / name)
        else:
            staged.unlink()
        touched = True
    if touched:
        synced(folder / PENDING, folder)


def best_mismatch(folder, best):
    """Why best.pt is not the weights last.pt's best line names, or None where it is: a run that
    went on from last.pt would end on a checkpoint.json that names weights it does not have."""
    path = folder / "best.pt"
    if best is None:
        return None
    named = best["checkpoint_sha256"]
    if not path.is_file():
        return f"best.pt is not there, though last.pt's best line names sha256 {named[:12]}"
    digest = file_digest(path, "best.pt")
    return None if digest == named else f"best.pt's sha256 {digest[:12]} is not {named[:12]}, the one last.pt's best line names"


def checkpoint_facts(folder):
    """train/checkpoint.json's facts where it is the record of the best.pt beside it, refused in
    words where it is not: not there, not a record a run wrote, as a node that died may leave it,
    or beside a best.pt of other bytes than the ones it names, whose numbers would be other
    weights'. tools/flow.py takes training as ended only where this reading holds (trained)."""
    path = folder / "checkpoint.json"
    try:
        facts = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise TrainError(f"{path}: not there, so the run has not finished training") from error
    except (OSError, ValueError) as error:
        raise TrainError(f"{path}: cannot be read as a run's checkpoint record ({error})") from error
    named = facts.get("checkpoint_sha256") if isinstance(facts, dict) else None
    if not isinstance(named, str):
        raise TrainError(f"{path}: names no checkpoint_sha256, so it is no run's checkpoint record")
    best = folder / "best.pt"
    if not best.is_file():
        raise TrainError(f"{best}: not there, though {path} names it")
    digest = file_digest(best, "best.pt")
    if digest != named:
        raise TrainError(f"{best}: its sha256 {digest[:12]} is not {named[:12]}, the one {path} records")
    return facts


def unsound_set_aside(folder):
    """A checkpoint.json that is no record of the best.pt beside it (checkpoint_facts), as the flow
    sends a run to train again for, moved to checkpoint.json.unsound before the run trains, so no
    reader takes it for this run's end while the run trains again."""
    path = folder / "checkpoint.json"
    if not path.exists():
        return
    try:
        checkpoint_facts(folder)
    except TrainError as error:
        aside = path.with_name("checkpoint.json.unsound")
        os.replace(path, aside)
        print(json.dumps({"set_aside": str(aside), "why": str(error)}), flush=True)


def drop_pending(folder):
    """The emptied pending/ folder, once the run is done."""
    try:
        (folder / PENDING).rmdir()
    except OSError:
        pass


def file_digest(path, what):
    """The sha256 of a file the run reads, streamed, since a catalog may be gigabytes; refused in
    words where there is no file."""
    path = Path(path)
    if not path.is_file():
        raise TrainError(f"{what} {path}: no file there")
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def arguments_of(args, blocks, parent):
    """What a resumed run must share with the run it goes on from: everything that shapes what it
    trains on and how, the schedule's length among them, and the files it reads by their bytes, the
    catalog, the ImageNet file and the parent (parent_of), as tools/flow.py names the run by them, so
    the same file reached by another path resumes and a file replaced at its path is refused. The
    device is left out, since a job put back in the queue may land on another card."""
    return {
        "epochs": args.epochs, "seed": args.seed, "size": args.size, "batch": args.batch, "lr": args.lr,
        "max_frames": args.max_frames, "witness": args.witness, "keep_epochs": args.keep_epochs,
        "catalog_sha256": file_digest(args.catalog, "--catalog"),
        "weights_sha256": file_digest(args.weights, "--weights") if args.weights else None,
        "init_sha256": parent["sha256"] if parent else None,
        "blocks": as_record(blocks),
    }


def numpy_state():
    """numpy's global state in plain numbers, which torch's weights-only loader reads back."""
    name, keys, position, has_gauss, cached = np.random.get_state()
    return [name, keys.tolist(), int(position), int(has_gauss), float(cached)]


def set_numpy_state(saved):
    name, keys, position, has_gauss, cached = saved
    np.random.set_state((name, np.array(keys, dtype=np.uint32), position, has_gauss, cached))


def last_state(epoch, model, optimiser, prior, generator, progress):
    """train/last.pt after an epoch: the weights, the optimiser's state, the prior head, every
    random state the run draws from, and progress, the best line, the lines so far, the epochs the
    witness frames were drawn at, the arguments the run was started with and the epochs it was
    resumed after."""
    return {
        "epoch": epoch,
        "model": model.state_dict(),
        "optimiser": optimiser.state_dict(),
        "prior": prior.state_dict() if prior is not None else None,
        "generator": generator.get_state(),
        "torch_rng": torch.get_rng_state(),
        "cuda_rng": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None,
        "numpy_rng": numpy_state(),
        "python_rng": random.getstate(),
        **progress,
    }


def save_last(folder, state):
    """train/last.pt written whole beside its place, on the disk before it is renamed into it, and
    bound to its bytes by its sha256 in last.pt.sha256, so a run cut while writing it keeps the one
    before, and a file a node that died left short or with stretches of zeros, which torch reads
    without a word since it checks no tensor's bytes, is one no line of the record names
    (read_last). The record names the new file and the ones it may replace while the rename is to
    be made and the new one alone once it is made, so a cut anywhere leaves the file in place
    named. The flushes and the hash added about half a second an epoch to the save of v1's 134 MB
    last.pt (resnet18 with Adam) on a CPU with no SHA instructions, measured on 2026-10-25."""
    temporary = folder / f"{LAST}.tmp"
    torch.save(state, temporary)
    synced(temporary)
    digest = file_digest(temporary, LAST)
    bind_last(folder, [digest, *bound_digests(folder)])
    os.replace(temporary, folder / LAST)
    synced(folder)
    bind_last(folder, [digest])


def bind_last(folder, digests):
    """train/last.pt.sha256: the sha256 a last.pt in place may have, one a line, written whole."""
    write_whole(folder / DIGESTS, "".join(f"{digest}\n" for digest in dict.fromkeys(digests)))


def bound_digests(folder):
    """The digests train/last.pt.sha256 names, none where it is not there or cannot be read."""
    try:
        text = (folder / DIGESTS).read_text(encoding="ascii")
    except (OSError, ValueError):
        return []
    return [line for line in text.splitlines() if SHA256.fullmatch(line)]


def unbound(path):
    """Why last.pt is no file save_last wrote whole, or None where the record names its bytes."""
    digests = bound_digests(path.parent)
    if not digests:
        return f"no {DIGESTS} names its bytes"
    try:
        with path.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
    except OSError as error:
        return f"it cannot be read ({error.strerror or error})"
    return None if digest in digests else f"its sha256 {digest[:12]} is not one {DIGESTS} names"


def refuse_nothing_to_resume(folder):
    """--resume where there is no train/last.pt, refused in words before anything is read."""
    path = folder / LAST
    if not path.is_file():
        raise TrainError(f"--resume: {path} is not there, so there is nothing to resume (a run writes it after every epoch and deletes it once checkpoint.json is written); start the run without --resume")


# The keys last_state writes, without which a file torch did read is no run's state.
LAST_KEYS = ("epoch", "model", "optimiser", "prior", "generator", "torch_rng", "cuda_rng", "numpy_rng", "python_rng",
             "best", "history", "witness_epochs", "arguments", "resumed_after")


def read_last(path):
    """last.pt as torch reads it and None, or None and why the run cannot go on from it: bytes its
    record does not name (unbound), a file cut short, emptied or with stretches of zeros, as a node
    that died before its bytes reached the disk may leave it, or one torch cannot read. Such a file
    is moved aside (set_aside), and the run starts again from epoch 0 in this call, since refusing
    it would be refused again on every start the flow makes, which resumes wherever last.pt is."""
    why = unbound(path)
    if why is None:
        try:
            state = torch.load(path, map_location="cpu", weights_only=True)
        except Exception as error:
            # Any error, since what a spoiled pickle makes torch raise has no list: the eight kinds
            # a file cut at 400 places, random bytes and overwritten bytes raised (2026-10-25)
            # left out three that changed bytes in the pickle raise, a TypeError, an AttributeError
            # and an AssertionError (#252), and a file torch cannot read is no state to go on from.
            why = type(error).__name__
        else:
            if isinstance(state, dict) and all(key in state for key in LAST_KEYS):
                return state, None
            why = f"a {type(state).__name__} that is not a run's state"
    return None, set_aside(path, why)


def set_aside(path, why):
    """last.pt moved to last.pt.unreadable, its record beside it, kept for a person to look at, and
    the restart said in the log with why; returns why for the card."""
    os.replace(path, path.with_name(f"{LAST}.unreadable"))
    record = path.with_name(DIGESTS)
    if record.exists():
        os.replace(record, path.with_name(f"{DIGESTS}.unreadable"))
    print(json.dumps({"restarted_from_epoch": 0, "unreadable": str(path.with_name(f"{LAST}.unreadable")), "why": why}), flush=True)
    return why


def load_last(folder, arguments):
    """train/last.pt for --resume and None, refused in words where there is none or where the run
    that wrote it was started with other arguments, or None and why the run starts again where it
    cannot go on from it (read_last); the files staged under pending/ are then settled as its best
    line says, before anything of the run starts, and a best.pt other than the one that line names
    leaves no state to go on from either (best_mismatch)."""
    refuse_nothing_to_resume(folder)
    path = folder / LAST
    state, why = read_last(path)
    if state is None:
        return None, why
    theirs = state.get("arguments") or {}
    changed = [f"{name} was {theirs.get(name)!r}, now {value!r}" for name, value in arguments.items() if theirs.get(name) != value]
    if changed:
        raise TrainError(f"--resume: {path} was written by a run started otherwise ({'; '.join(changed)}); resume with the arguments the run was started with")
    settle(folder, state["best"])
    why = best_mismatch(folder, state["best"])
    if why is not None:
        # The run cannot go on to a checkpoint.json that names weights it does not have, and the
        # flow passes --resume wherever last.pt is, so a refusal would come back on every start.
        return None, set_aside(path, why)
    return state, None


def restore(saved, model, optimiser, prior, generator):
    """The cut run's weights, optimiser state and random states in place of the fresh run's."""
    model.load_state_dict(saved["model"])
    optimiser.load_state_dict(saved["optimiser"])
    if prior is not None:
        prior.load_state_dict(saved["prior"])
    generator.set_state(saved["generator"])
    torch.set_rng_state(saved["torch_rng"])
    if saved["cuda_rng"] is not None and torch.cuda.is_available():
        torch.cuda.set_rng_state_all(saved["cuda_rng"])
    set_numpy_state(saved["numpy_rng"])
    random.setstate(saved["python_rng"])


def resume_into(saved, model, optimiser, prior, generator, frames):
    """A cut run taken back into the one built afresh, after everything a fresh start builds and
    draws, so the next epoch draws what it would have drawn had the run gone through; returns the
    epoch to go on from, the lines so far, the best line and the epochs it was resumed after."""
    restore(saved, model, optimiser, prior, generator)
    frames.epochs = list(saved["witness_epochs"])
    print(json.dumps({"resumed_after_epoch": saved["epoch"]}), flush=True)
    return saved["epoch"] + 1, list(saved["history"]), saved["best"], [*saved["resumed_after"], saved["epoch"]]


def holder_words():
    """Who holds a lock, as the lock file says it to the next one refused: the process, the node,
    the Slurm job where there is one, and since when."""
    job = os.environ.get("SLURM_JOB_ID")
    return f"pid {os.getpid()} on {socket.gethostname()}" + (f", Slurm job {job}" if job else "") + time.strftime(", since %Y-%m-%dT%H:%M:%SZ", time.gmtime())


@contextlib.contextmanager
def held(folder):
    """train/ held for this run alone, from before any file in it is read to the end: an exclusive
    lock on train/.lock, taken without waiting, so a second trainer sent into the same folder, as a
    flow started again after the flow of a live Slurm job died sends one, is refused in words
    before it settles pending/ or opens a file. The kernel drops a flock when its process ends, by
    a kill too, so a cut run leaves no lock behind, and CephFS, the lab volume, honours it across
    nodes, as grid/03-catalog.sbatch's lock relies on."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / LOCK
    with path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            holder = path.read_text(encoding="utf-8").strip() or "which has not yet written who it is"
            raise TrainError(f"{folder} is in progress: another trainer holds {path} ({holder}); this one stops before it touches anything") from error
        except OSError as error:
            raise TrainError(f"{path}: cannot be locked ({error}), so whether another trainer works here cannot be told; nothing is touched") from error
        handle.truncate(0)
        handle.write(holder_words() + "\n")
        handle.flush()
        yield


def write_whole(path, text):
    """A file written beside its place, on the disk, and renamed into it, so no reader sees half of
    it, even after the node it was written on died: tools/flow.py takes checkpoint.json as the end
    of the training step."""
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    synced(temporary)
    os.replace(temporary, path)
    synced(path.parent)


def synced(*paths):
    """Each file or folder flushed to the disk, a folder for the names in it: a rename can reach
    the disk before the bytes it names, so a node that dies after it may leave the file short or
    with stretches of zeros, where a job that is killed leaves the node to write them."""
    for path in paths:
        handle = os.open(path, os.O_RDONLY)
        try:
            os.fsync(handle)
        finally:
            os.close(handle)


def run_record(out):
    """The run's RUN.json, which tools/flow.py writes from a clean tree before any step and every
    number a step writes is stamped from, refused in words where it is not there or is no record."""
    run_file = Path(out) / "RUN.json"
    if not run_file.is_file():
        raise TrainError(f"{run_file}: no run record; start the run with tools/flow.py")
    try:
        record = json.loads(run_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise TrainError(f"{run_file}: cannot be read as a run record ({error})") from error
    if not isinstance(record, dict):
        raise TrainError(f"{run_file}: not a run record")
    return record


def refuse_another_catalog(record, catalog, catalog_sha256):
    """A step reads the catalog the run was started on and no other: RUN.json names it by its
    sha256, which every number the step writes is stamped with, so a step on another, run by hand
    or after the catalog's path was given other bytes, would stamp one catalog's numbers with
    another's name."""
    named = str(record.get("catalog_sha256"))
    if catalog_sha256 != named:
        raise TrainError(f"--catalog {catalog}: its sha256 {catalog_sha256[:12]} is not {named[:12]}, the catalog the run's RUN.json names; every number a step writes is stamped with that catalog, so the step reads no other")


def run(args):
    out = Path(args.out)
    record = run_record(out)
    if args.epochs < 1:
        raise TrainError("a run trains at least one epoch; epoch 0 is the untrained network, drawn before it")
    try:
        blocks = parse_blocks(args.block)
    except BlockError as error:
        raise TrainError(f"blocks: {error}") from error
    if args.init and args.weights:
        raise TrainError("a run starts from ImageNet (--weights) or from a parent (--init), not both")
    with held(out / "train"):
        return train_held(args, out, record, blocks)


def train_held(args, out, record, blocks):
    """The run itself, once train/ is held for it alone (held)."""
    folder = out / "train"
    parent = parent_of(args.init) if args.init else None
    if args.resume:
        refuse_nothing_to_resume(folder)
    arguments = arguments_of(args, blocks, parent)
    refuse_another_catalog(record, args.catalog, arguments["catalog_sha256"])
    unsound_set_aside(folder)
    saved, restarted = load_last(folder, arguments) if args.resume else (None, None)
    seed_everything(args.seed)
    crops = read_crops(args.catalog, TRAIN_PARTS)
    seen, offered = training_crops(crops, blocks)
    train_crops = pick(seen, "train", args.max_frames, args.seed)
    val_crops = pick(crops, "validation", args.max_frames, args.seed + 1)
    if offered and not seen:
        raise TrainError(f"the samples block ({' '.join(w for w in words_of(blocks) if w.split('=')[0] in SAMPLE_WORDS)}) leaves none of the {offered} training crops")
    if not train_crops or not val_crops:
        raise TrainError("the catalog has no labelled train or validation crops")
    cache = {}
    train_x, train_y = load_crops(train_crops, args.size, cache)
    val_x, val_y = load_crops(val_crops, args.size, cache)
    witness = list(range(min(args.witness, len(val_crops))))
    frames = Witness(out, [c for c in crops if c["part"] == "validation"], args.size)
    (folder / "witness").mkdir(parents=True, exist_ok=True)
    model = build_model(args.weights, args.device, blocks.normalise, blocks.architecture, blocks.denoise)
    if parent:
        warm_start(model, args.init, parent, blocks, args.size)
    join_single = not trains_on_one_crop(model, args.size)
    maps, val_maps, prior = prior_of(blocks, model, train_crops, val_crops, args)
    refuse_one_crop(len(train_crops), args.batch, join_single, one_crop_words(blocks.architecture, args.size))
    optimiser = BLOCKS.OPTIMISERS[blocks.optimiser](model, args.lr, blocks, prior.parameters() if prior else ())
    base_rates = [group["lr"] for group in optimiser.param_groups]
    loss_fn = BLOCKS.loss_function(blocks, train_y, LEVELS).to(args.device)
    generator = torch.Generator().manual_seed(args.seed)
    telemetry = load_tool("wandb_log").Telemetry(out, record, "train", {"epochs": args.epochs, "seed": args.seed, "size": args.size, "batch": args.batch, "lr": args.lr, "weights": bool(args.weights), "train_crops": len(train_crops), "validation_crops": len(val_crops), "witness_frames": len(frames.frames), "blocks": as_record(blocks), "parent": parent_record(parent)}, resume=args.resume)
    history, best, resumed, first, started = [], None, [], 0, time.monotonic()
    if saved is not None:
        # Last of all, after the telemetry's start, so whatever a fresh start draws is drawn over.
        first, history, best, resumed = resume_into(saved, model, optimiser, prior, generator, frames)
        started -= history[-1]["seconds"]
    joined = join_single and ends_on_one(len(train_y), args.batch)
    with (folder / "metrics.jsonl").open("w", encoding="utf-8") as metrics:
        # Flushed after every write, so the lines are on disk while the run goes on: the sweep's
        # card reads the last one as the row's progress, and a killed job flushes nothing.
        metrics.writelines(json.dumps(line) + "\n" for line in history)
        metrics.flush()
        for epoch in range(first, args.epochs + 1):
            rate = None
            if epoch:
                rate = set_rate(optimiser, base_rates, lr_factor(epoch, args.epochs, blocks.warmup_epochs, blocks.schedule))
            loss = train_epoch(model, optimiser, train_x, train_y, args.device, args.batch, generator, blocks, loss_fn, maps, prior, join_single=join_single) if epoch else None
            tally = MapTally(prior, val_maps, args.device) if prior is not None else None
            guesses = predict(model, val_x, args.device, args.batch, tally)
            numbers = prior_line(prior, tally)
            line = epoch_line(epoch, loss, guesses, val_y, val_crops, started, frames.draw(model, args.device, args.batch, epoch), rate, numbers)
            witness_strip([val_crops[i] for i in witness], val_x[witness], guesses[witness], folder / "witness" / f"epoch-{epoch:02d}.png")
            checkpoint(model, folder, epoch, args.keep_epochs)
            if epoch and (best is None or chosen_by(line, blocks) > chosen_by(best, blocks)):
                best = stage_best(model, prior, folder, line)
            history.append(line)
            metrics.write(json.dumps(line) + "\n")
            metrics.flush()
            print(json.dumps({k: v for k, v in line.items() if k != "validation_strata"}), flush=True)
            telemetry.log(dict(wandb_values(line), **telemetry.images(frames.media(epoch)), **telemetry.images({"witness/crops": folder / "witness" / f"epoch-{epoch:02d}.png"})), step=epoch)
            progress = {"best": best, "history": history, "witness_epochs": frames.epochs, "arguments": arguments, "resumed_after": resumed}
            save_last(folder, last_state(epoch, model, optimiser, prior, generator, progress))
            settle(folder, best)
    frames.finish()
    accuracy_curve(history, folder / "accuracy.png")
    counts = {
        "train": len(train_crops),
        "train_seen": len(seen),
        "train_offered": offered,
        "validation": len(val_crops),
        "validation_offered": sum(c["part"] == "validation" for c in crops),
        "train_persons": person_count(train_crops),
        "validation_persons": person_count(val_crops),
        "train_with_map": with_map(train_crops),
        "validation_with_map": with_map(val_crops),
    }
    notes = batch_lines(joined, blocks, args) + restart_lines(restarted) + resume_lines(resumed)
    model_card(folder, args, record, counts, best, time.monotonic() - started, blocks, parent, notes)
    joins = {"single_crop_batch": "joined"} if joined else {}
    facts = dict(best, counts=counts, levels=list(LEVELS), size=args.size, blocks=as_record(blocks), parent=parent_record(parent), **joins)
    # The step's last file, since tools/flow.py takes it as the step's end; last.pt goes after it.
    write_whole(folder / "checkpoint.json", json.dumps(facts, indent=1) + "\n")
    for name in (LAST, f"{LAST}.tmp", DIGESTS, f"{DIGESTS}.tmp"):
        (folder / name).unlink(missing_ok=True)
    drop_pending(folder)
    telemetry.log(telemetry.images({"accuracy": folder / "accuracy.png"}) | telemetry.videos({f"witness/validation_video/{f['key']}": frames.folder / f["key"] / "anim.gif" for f in frames.frames}))
    telemetry.summary({"best_epoch": best["epoch"], "best_validation_accuracy": best["validation_accuracy"], "checkpoint_sha256": best["checkpoint_sha256"]})
    telemetry.finish()
    return 0


def main(argv=None):
    try:
        return run(parse(argv))
    except TrainError as error:
        print(f"train: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
