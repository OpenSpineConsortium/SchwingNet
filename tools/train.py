"""Train the level stage of SchwingNet v1 from a catalog, in the open, one epoch at a time.

Usage (inside the train-cpu or train-gpu environment):
    python tools/train.py --catalog <catalog.sqlite> --out <run dir> --epochs N --seed S
        [--weights <imagenet state_dict of the architecture>] [--size 64] [--batch 64] [--max-frames N]
        [--witness 12] [--device cpu|cuda] [--keep-epochs 1]

The stage is the level classifier of docs/research/retraining-plan.md, section 3.4: a vertebral
body crop in, one of the 27 level names out. The crops come from the catalog's labels, so the
detector stage is not in this run and every number says so (docs/research/v1-demo). The trainer
reads frames through the catalog alone, train and validation parts only, never a test row, and
writes everything a reader needs to see the run rather than trust it: metrics.jsonl with one line
per epoch, a witness strip of the same fixed validation crops at every epoch with truth and
prediction on each, the accuracy curve, the best checkpoint with its sha256 and a model card. The
seed fixes every source of randomness torch exposes, and the run is refused unless its RUN.json
is there, since tools/flow.py writes that record from a clean tree before any step starts.

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
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Run as a script, this folder is first on the path, and tools/profile.py would then shadow the
# standard library's profile module, which torch imports; the package under src/ takes its place.
sys.path[0] = str(ROOT / "src")

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import random  # noqa: E402
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
TRAIN_PARTS = ("train", "validation")
SAMPLE_WORDS = ("samples", "sources", "per_person")
CROP_SQL = """
SELECT l.level, l.x0, l.y0, l.x1, l.y1, i.sha256, i.part, i.person, i.source, i.path, s.manifest
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


def read_crops(catalog, parts):
    """Every labelled body in the named parts: level, unit box, frame path, person, source."""
    db = sqlite3.connect(f"file:{catalog}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    marks = ", ".join("?" for _ in parts)
    rows = db.execute(CROP_SQL.format(marks=marks), parts).fetchall()
    db.close()
    crops = []
    for row in rows:
        frame = Path(row["manifest"]).parent / row["path"]
        crops.append(
            {
                "level": row["level"],
                "box": (row["x0"], row["y0"], row["x1"], row["y1"]),
                "frame": str(frame),
                "part": row["part"],
                "person": row["person"],
                "source": row["source"],
                "sha256": row["sha256"],
            }
        )
    return crops


def crop_pixels(frame, box, size):
    """The body's crop as a size-by-size float array in 0..1, padded a little around the box."""
    return crop_of_image(Image.open(frame).convert("L"), box, size)


def crop_of_image(image, box, size):
    """crop_pixels on a frame already decoded, so a frame's bodies share one decode."""
    width, height = image.size
    x0, y0, x1, y1 = box
    pad_x, pad_y = (x1 - x0) * PAD, (y1 - y0) * PAD
    pixels = (
        max(0, int((x0 - pad_x) * width)),
        max(0, int((y0 - pad_y) * height)),
        min(width, int((x1 + pad_x) * width) + 1),
        min(height, int((y1 + pad_y) * height) + 1),
    )
    crop = image.crop(pixels).resize((size, size), Image.BILINEAR)
    return np.asarray(crop, dtype=np.float32) / 255.0


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
    <run>/train/best.pt or <run>/train/epochs/epoch-NN.pt, that run's id and blocks."""
    path = Path(path)
    if not path.is_file():
        raise TrainError(f"{path}: no parent checkpoint there")
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


def predict(model, inputs, device, batch):
    """Predicted level indices for a tensor of crops, in batches, with no gradient."""
    model.eval()
    guesses = []
    with torch.no_grad():
        for start in range(0, len(inputs), batch):
            logits = model(inputs[start : start + batch].to(device))
            guesses.append(logits.argmax(dim=1).cpu())
    return torch.cat(guesses) if guesses else torch.zeros(0, dtype=torch.long)


def train_epoch(model, optimiser, inputs, targets, device, batch, generator, blocks=None, loss_fn=None):
    """One pass over the training crops in an order the sampler draws; returns the mean loss.

    With no blocks, version 1's epoch: every crop once in a seeded order, no change to a crop,
    plain cross-entropy. The run's blocks choose the sampler, the changes made to each batch and
    the loss (tools/train_blocks.py)."""
    model.train()
    blocks = blocks or from_record(None)
    loss_fn = loss_fn or nn.CrossEntropyLoss()
    order = BLOCKS.SAMPLERS[blocks.sampler](targets, generator)
    total = 0.0
    for start in range(0, len(order), batch):
        index = order[start : start + batch]
        optimiser.zero_grad()
        crops = inputs[index].to(device)
        if blocks.augment:
            crops = BLOCKS.augment(crops, blocks.augment, generator)
        loss = loss_fn(model(crops), targets[index].to(device))
        loss.backward()
        optimiser.step()
        total += float(loss) * len(index)
    return total / max(1, len(order))


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


def model_card(out, args, run, counts, best, elapsed, blocks, parent=None):
    """MODEL.md: what the checkpoint is, what it saw, what it scored, and what it is not."""
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
        f"- Best epoch {best['epoch']}: validation accuracy {best['validation_accuracy']:.3f} ({best['validation_ci'][0]:.3f} to {best['validation_ci'][1]:.3f}, n={best['validation_n']}).",
        f"- Checkpoint best.pt sha256 {best['checkpoint_sha256']}; wall time {elapsed:.0f} s.",
        "- Levels: " + ", ".join(LEVELS) + f"; transitional {', '.join(TRANSITIONAL)}.",
        "",
        "Every number above is reproduced by tools/flow.py run with the same catalog, commit and seed.",
    ]
    (out / "MODEL.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


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


def epoch_line(epoch, loss, guesses, val_y, val_crops, started, witness_score, learning_rate=None):
    """One line of metrics.jsonl: the whole validation part, its strata and the witness score."""
    correct = int((guesses == val_y).sum())
    low, high = wilson(correct, len(val_y))
    strata = strata_of(val_crops, guesses)
    return {
        "epoch": epoch,
        "train_loss": loss,
        "learning_rate": learning_rate,
        "validation_accuracy": correct / len(val_y),
        "validation_balanced_accuracy": balanced_accuracy(strata["level"]),
        "validation_ci": [low, high],
        "validation_n": len(val_y),
        "validation_strata": strata,
        "witness_validation": witness_score,
        "seconds": round(time.monotonic() - started, 1),
    }


def wandb_values(line):
    """The epoch's numbers as flat W&B keys."""
    values = {"train/loss": line["train_loss"], "train/learning_rate": line.get("learning_rate"), "validation/balanced_accuracy": line.get("validation_balanced_accuracy"), "validation/accuracy": line["validation_accuracy"], "validation/ci_low": line["validation_ci"][0], "validation/ci_high": line["validation_ci"][1]}
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


def run(args):
    out = Path(args.out)
    run_file = out / "RUN.json"
    if not run_file.is_file():
        raise TrainError(f"{run_file}: no run record; start the run with tools/flow.py")
    record = json.loads(run_file.read_text(encoding="utf-8"))
    if args.epochs < 1:
        raise TrainError("a run trains at least one epoch; epoch 0 is the untrained network, drawn before it")
    try:
        blocks = parse_blocks(args.block)
    except BlockError as error:
        raise TrainError(f"blocks: {error}") from error
    if args.init and args.weights:
        raise TrainError("a run starts from ImageNet (--weights) or from a parent (--init), not both")
    parent = parent_of(args.init) if args.init else None
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
    folder = out / "train"
    (folder / "witness").mkdir(parents=True, exist_ok=True)
    model = build_model(args.weights, args.device, blocks.normalise, blocks.architecture, blocks.denoise)
    if parent:
        warm_start(model, args.init, parent, blocks, args.size)
    optimiser = BLOCKS.OPTIMISERS[blocks.optimiser](model, args.lr, blocks)
    base_rates = [group["lr"] for group in optimiser.param_groups]
    loss_fn = BLOCKS.loss_function(blocks, train_y, LEVELS).to(args.device)
    generator = torch.Generator().manual_seed(args.seed)
    telemetry = load_tool("wandb_log").Telemetry(out, record, "train", {"epochs": args.epochs, "seed": args.seed, "size": args.size, "batch": args.batch, "lr": args.lr, "weights": bool(args.weights), "train_crops": len(train_crops), "validation_crops": len(val_crops), "witness_frames": len(frames.frames), "blocks": as_record(blocks), "parent": parent_record(parent)})
    history, best, started = [], None, time.monotonic()
    with (folder / "metrics.jsonl").open("w", encoding="utf-8") as metrics:
        for epoch in range(0, args.epochs + 1):
            rate = None
            if epoch:
                rate = set_rate(optimiser, base_rates, lr_factor(epoch, args.epochs, blocks.warmup_epochs, blocks.schedule))
            loss = train_epoch(model, optimiser, train_x, train_y, args.device, args.batch, generator, blocks, loss_fn) if epoch else None
            guesses = predict(model, val_x, args.device, args.batch)
            line = epoch_line(epoch, loss, guesses, val_y, val_crops, started, frames.draw(model, args.device, args.batch, epoch), rate)
            witness_strip([val_crops[i] for i in witness], val_x[witness], guesses[witness], folder / "witness" / f"epoch-{epoch:02d}.png")
            checkpoint(model, folder, epoch, args.keep_epochs)
            if epoch and (best is None or chosen_by(line, blocks) > chosen_by(best, blocks)):
                torch.save(model.state_dict(), folder / "best.pt")
                best = dict(line, checkpoint_sha256=sha256_of(folder / "best.pt"))
            history.append(line)
            metrics.write(json.dumps(line) + "\n")
            print(json.dumps({k: v for k, v in line.items() if k != "validation_strata"}), flush=True)
            telemetry.log(dict(wandb_values(line), **telemetry.images(frames.media(epoch)), **telemetry.images({"witness/crops": folder / "witness" / f"epoch-{epoch:02d}.png"})), step=epoch)
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
    }
    (folder / "checkpoint.json").write_text(json.dumps(dict(best, counts=counts, levels=list(LEVELS), size=args.size, blocks=as_record(blocks), parent=parent_record(parent)), indent=1) + "\n", encoding="utf-8")
    model_card(folder, args, record, counts, best, time.monotonic() - started, blocks, parent)
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
