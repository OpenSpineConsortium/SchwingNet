"""Reproduce the FLUX.2 edit that made FluXray, finetune an edit adapter, and measure the gap.

Usage (inside grid/realism.sbatch's throwaway environment, which holds diffusers, flexray and the
trainer; every subcommand but the GPU ones runs on numpy alone):
    python tools/realism.py inputs --samples <csv> --db <ThunderDB> --ct <dir> --truth <dir> --klein <dir> --bundle <dir> --imagenet <pth> --out <json>
    python tools/realism.py poses --samples <FluXray samples.csv> --out <poses.json> [--inputs <inputs.json>]
    python tools/realism.py split --poses <poses.json> --out <dir> [--eligible <inputs.json>] [--limit N] [--shard-size N]
    python tools/realism.py render --ct <CT dir> --truth <ground-truth dir> --poses <poses.json> --out <dir> [--only <file>] [--per-subject N]
    python tools/realism.py edit --raw <render dir> --weights <klein dir> --out <dir> [--model klein-9b] [--lora <file>] [--arms 1]
    python tools/realism.py score --raw <render dir> --edited <edit dir> --weights <FleXray bundle> --out <csv> [--only <file>]
    python tools/realism.py keep --scores <dir of csv> --edited <edit dir> --out <dir>
    python tools/realism.py filter --raw <render dir> --edited <edit dir> --weights <FleXray bundle> --out <dir>
    python tools/realism.py fluxray-export --db <FluXray thunder_dbs/1.0> --out <dir> [--samples <render dir>] [--subjects <file>]
    python tools/realism.py stats --a <dir> --b <dir> --out <dir> [--index <render dir>] [--weights <bundle>] [--imagenet-weights <pth>]
    python tools/realism.py pairs --control <render dir> --target <dir> --out <pairs dir> [--only <file>]
    python tools/realism.py lora-config --pairs <pairs dir> --out <file> [--base klein-base-4b] [--rank 16] [--seed N]
    python tools/realism.py measure --masks <render dir> --out <dir>

The recipe, the poses, the filter rule, the resolution arithmetic, the verdict words and the LoRA
plan are schwingnet.realism, proven by the gate; this file is the side that reads files and runs
models. docs/research/flux-realism/README.md is the programme. Nothing here starts a job: the
grid runs each stage on the owner's word through grid/gate.sh's word `realism <stage>`.

The comparison is pre-registered in schwingnet.realism and read here in three feature spaces,
each over images brought to FleXray's own 256-pixel canvas (zero-padded to a square, Pillow's
bilinear resize, the 0.5 and 99.5 percentile window) when sizes differ: physics features that a
radiographer would read (the intensity histogram, the radial power spectrum, gradients, noise,
local contrast), FleXray's own reading (the flux000 member's channel probabilities), and an
ImageNet ResNet-18's pooled features. Each space gives a two-sample classifier's AUC with its
bootstrap interval over subjects, an RBF MMD with its permutation p-value, and Frechet and
kernel distances on 64 principal components; the second set's split halves give the null every
number is read against, and realism.verdict turns the interval and the p-value into one word.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# As in tools/train.py: this folder leaves the path so tools/profile.py never shadows the
# standard library's profile module, which torch imports.
sys.path[0] = str(ROOT / "src")
if str(ROOT / "vendor" / "beethoven-qa" / "src") not in sys.path:
    sys.path.insert(1, str(ROOT / "vendor" / "beethoven-qa" / "src"))

import argparse  # noqa: E402
import csv  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import os  # noqa: E402
import struct  # noqa: E402
import time  # noqa: E402
import zlib  # noqa: E402

from schwingnet import realism  # noqa: E402

# Every size the statistics and the render use is the frozen plan's (schwingnet.realism.REPLICATION,
# docs/research/flux-realism/PREREG.md), named here once for the functions below.
PLAN = realism.REPLICATION
PHYSICS_BINS = PLAN.physics_bins
RADIAL_BANDS = PLAN.radial_bands
PCA_COMPONENTS = PLAN.pca_components
KNN = PLAN.knn
BOOTSTRAPS = PLAN.bootstraps
PERMUTATIONS = PLAN.permutations
KID_SUBSET = PLAN.kid_subset
KID_REPEATS = PLAN.kid_repeats
CANVAS = PLAN.canvas
PERCENTILES = (PLAN.percentile_low, PLAN.percentile_high)
# ENHANCE.PET's ground-truth folders that FleXray's MOOSE labels are packed from, with the key of
# each in the bucket's labels.json, and the two names the two tables spell differently.
TRUTH_FOLDERS = {
    "Peripheral-Bones": "clin_ct_peripheral_bones",
    "Ribs": "clin_ct_ribs",
    "Vertebrae": "clin_ct_vertebrae",
}
NAME_FIXES = {"fingers_left": "phalange_left", "fingers_right": "phalange_right",
              "toes_left": "toe_left", "toes_right": "toe_right"}
HU_LOW, HU_HIGH, AIR_CLAMP_HU = PLAN.hu_low, PLAN.hu_high, PLAN.air_clamp_hu
RAY_SAMPLES = PLAN.ray_samples
LUMBAR = ("vertebra_l1", "vertebra_l2", "vertebra_l3", "vertebra_l4", "vertebra_l5")
# ENHANCE.PET 1.6k's label dictionary, a verbatim copy of the public bucket's labels.json (sha256
# 19e319b8f73aaec8a956d741fc30bb1ccff4be1d65cdba5f0c418c4ed8d29459), so a render needs no file
# beyond the CTs and the truth; the fetch of the truth lands the ground-truth prefix alone.
ENHANCE_LABELS = ROOT / "grid" / "enhance-pet-labels.json"
TRAIN_FRACTION = 0.7


class Refused(Exception):
    """An input the tool will not read, said in words."""


# --- small files -------------------------------------------------------------------------------------

def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_rows(path, rows, columns):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def write_png(path, array):
    """An 8-bit grey PNG from values in [0, 1], with the standard library alone."""
    import numpy as np

    pixels = np.clip(np.rint(np.asarray(array, dtype=np.float64) * 255.0), 0, 255).astype(np.uint8)
    height, width = pixels.shape
    raw = b"".join(b"\x00" + pixels[row].tobytes() for row in range(height))

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(data)


def read_png(path):
    """An 8- or 16-bit grey PNG written without filters or interlace, as float32 in [0, 1]."""
    import numpy as np

    data = Path(path).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise Refused(f"{path} is not a PNG")
    position, width = 8, None
    body = b""
    while position < len(data):
        length, kind = struct.unpack(">I", data[position:position + 4])[0], data[position + 4:position + 8]
        chunk = data[position + 8:position + 8 + length]
        position += 12 + length
        if kind == b"IHDR":
            width, height, depth, colour, _, _, interlace = struct.unpack(">IIBBBBB", chunk)
            if colour != 0 or interlace != 0 or depth not in (8, 16):
                raise Refused(f"{path}: only 8- or 16-bit grey PNGs without interlace are read here")
        elif kind == b"IDAT":
            body += chunk
    if width is None:
        raise Refused(f"{path} has no header")
    rows = zlib.decompress(body)
    step = width * depth // 8 + 1
    dtype = np.uint8 if depth == 8 else ">u2"
    lines = [np.frombuffer(rows[r * step + 1:(r + 1) * step], dtype=dtype) for r in range(height)]
    if any(rows[r * step] != 0 for r in range(height)):
        raise Refused(f"{path} uses a PNG row filter this reader does not undo")
    return np.stack(lines).astype(np.float32) / (255.0 if depth == 8 else 65535.0)


def read_grey(path):
    """One image as float32 in [0, 1]: a .npy of any float or integer dtype, or a grey PNG."""
    import numpy as np

    path = Path(path)
    if path.suffix == ".png":
        return read_png(path)
    array = np.load(path)
    while array.ndim > 2 and array.shape[0] == 1:
        array = array[0]
    if array.ndim != 2:
        raise Refused(f"{path} is not one grey image")
    if np.issubdtype(array.dtype, np.integer):
        return array.astype(np.float32) / float(np.iinfo(array.dtype).max)
    return np.nan_to_num(array.astype(np.float32))


def images_in(folder):
    """Every .npy and .png under a folder, by stem, so two folders pair by name."""
    folder = Path(folder)
    found = {}
    for path in sorted(folder.rglob("*")):
        if path.suffix in (".npy", ".png") and path.is_file() and "mask" not in path.parent.name:
            found.setdefault(path.stem, path)
    return found


def subject_filter(path):
    """The subject ids a file lists, one per line or a CSV's first column; None when no file is named."""
    if not path:
        return None
    found = set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        head = line.split(",")[0].strip()
        if head and head.lower() not in ("subject", "subject_id"):
            found.add(head)
    if not found:
        raise Refused(f"{path} names no subject")
    return found


def subject_of(stem):
    """The subject a sample's name begins with, <subject>_<pose>, where no index of the samples says
    it; the run's own sets are read through their index (sample_index), which names it."""
    return stem.split("_")[0]


# An edit's name is its sample's and the seed arm's: <sample_id>__a<arm>.
ARM_MARK = "__a"


def edit_name(sample_id, arm):
    return f"{sample_id}{ARM_MARK}{arm}"


def arm_of(stem):
    """The seed arm an edit's name ends with, or None for an image that is no edit."""
    head, mark, tail = stem.rpartition(ARM_MARK)
    return int(tail) if mark and head and tail.isascii() and tail.isdigit() and len(tail) <= 4 else None


def sample_of(stem):
    """The sample an image is of: its name, less the arm where it is an edit."""
    return stem.rpartition(ARM_MARK)[0] if arm_of(stem) is not None else stem


def manifest_rows(render_dir):
    """The render's manifest, one row per sample, the last written for a sample kept, since a
    shard run again after a cut appends what it renders again."""
    rows = {}
    path = Path(render_dir) / "manifest.jsonl"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                rows[row["sample_id"]] = row
    return rows


def sample_index(path):
    """sample_id -> subject_id from a render manifest (a folder holding manifest.jsonl, or the
    file) or a CSV with those two columns; None where no index is named."""
    if not path:
        return None
    path = Path(path)
    if path.is_dir() or path.suffix == ".jsonl":
        rows = manifest_rows(path if path.is_dir() else path.parent)
        return {sample: row["subject_id"] for sample, row in rows.items()}
    return {row["sample_id"]: row["subject_id"] for row in read_rows(path)}


def subject_in(index, stem):
    """An image's subject: by the index where one is named, else by its name."""
    if index is None:
        return subject_of(sample_of(stem))
    sample = sample_of(stem)
    if sample not in index:
        raise Refused(f"{stem} is of no sample the index names")
    return index[sample]


def file_sha256(path):
    import hashlib

    with open(path, "rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def volumes_under(root):
    """Every .nii.gz under a folder by its name less .nii.gz, as the fetch lands ENHANCE.PET's keys
    (images/CT/<subject>.nii.gz) however deep; a name found twice is refused, since which of the
    two a render read would be a guess."""
    found = {}
    for path in sorted(Path(root).rglob("*.nii.gz")):
        name = path.name[:-len(".nii.gz")]
        if name in found:
            raise Refused(f"{name}.nii.gz is under {root} twice ({found[name]} and {path})")
        found[name] = path
    return found


def truth_under(root):
    """ENHANCE.PET's ground truth by (folder, subject), the folder the nearest of TRUTH_FOLDERS
    above the file, however deep the fetch landed the ground-truth prefix."""
    found = {}
    for path in sorted(Path(root).rglob("*.nii.gz")):
        folder = next((part for part in reversed(path.parent.parts) if part in TRUTH_FOLDERS), None)
        if folder is not None:
            found[(folder, path.name[:-len(".nii.gz")])] = path
    return found


# --- the canvas ---------------------------------------------------------------------------------------

def pad_to_square(array):
    """Zero padding to a square, the image centred, as FleXray's preprocessing pads."""
    import numpy as np

    height, width = array.shape
    side = max(height, width)
    top, left = (side - height) // 2, (side - width) // 2
    canvas = np.zeros((side, side), dtype=np.float32)
    canvas[top:top + height, left:left + width] = array
    return canvas


def resize(array, size):
    """A square image at `size` pixels: Pillow's bilinear where Pillow is here, as FleXray resizes,
    else the block mean for a whole factor down and nearest otherwise."""
    import numpy as np

    if array.shape == (size, size):
        return array.astype(np.float32)
    try:
        from PIL import Image
    except ImportError:
        Image = None
    if Image is not None:
        resized = Image.fromarray(array.astype(np.float32)).resize((size, size), resample=Image.Resampling.BILINEAR)
        return np.asarray(resized, dtype=np.float32)
    factor = array.shape[0] / size
    if factor > 1 and factor == int(factor):
        factor = int(factor)
        return array.reshape(size, factor, size, factor).mean(axis=(1, 3)).astype(np.float32)
    rows = np.minimum((np.arange(size) * factor).astype(int), array.shape[0] - 1)
    return array[rows][:, rows].astype(np.float32)


def percentile_window(array, percentiles=PERCENTILES):
    """The window FleXray's percentile_minmax applies: clipped to the two percentiles, then 0 to 1."""
    import numpy as np

    low, high = np.percentile(array, percentiles)
    span = max(float(high - low), 1e-7)
    return np.clip((array - low) / span, 0.0, 1.0).astype(np.float32)


def canvas(array, size=CANVAS):
    """FleXray's inference canvas of one image: pad to a square, resize, window."""
    return percentile_window(resize(pad_to_square(array), size))


def block_majority(mask, factor):
    """A binary mask shrunk by a whole factor, a block set where at least half its pixels are."""
    import numpy as np

    side = mask.shape[0] // factor
    blocks = mask[:side * factor, :side * factor].reshape(side, factor, side, factor).mean(axis=(1, 3))
    return blocks >= 0.5


# --- poses and labels -----------------------------------------------------------------------------------

def poses_from_samples(rows):
    """FluXray's samples grouped by subject, each pose checked against the paper's grid.

    Returns the samples kept with their pose, the subjects, and the rows whose recorded pose is
    none of the grid's, which are reported and left out rather than rendered at a pose the paper
    did not use.
    """
    grid = {pose: index for index, pose in enumerate(realism.pose_grid())}
    kept, mismatches = [], []
    for row in rows:
        pose = (int(round(float(row["y"]))), int(round(float(row["z"]))), int(round(float(row["alpha_deg"]))))
        off_axis = any(abs(float(row.get(key, 0.0) or 0.0)) > 1e-6 for key in ("x", "beta_deg", "gamma_deg"))
        if pose not in grid or off_axis:
            mismatches.append(row["sample_id"])
            continue
        kept.append({"sample_id": row["sample_id"], "subject_id": row["subject_id"], "split": row.get("split", ""),
                     "pose_id": int(row["pose_id"]), "grid_pose": grid[pose], "y": pose[0], "z": pose[1], "alpha": pose[2]})
    subjects = sorted({sample["subject_id"] for sample in kept})
    return {"samples": kept, "subjects": subjects, "mismatches": mismatches}


def moose_dense_ids(enhance_labels, stored_labels):
    """Which dense MOOSE id each (ENHANCE.PET folder, its label id) becomes, by name.

    ENHANCE.PET ships one label file per class (Peripheral-Bones, Ribs, Vertebrae) with ids of its
    own; FleXray's MOOSE profile packs them into one dense label whose names stored_labels lists.
    The names match after lowercasing and two spellings (fingers, toes); a name with no dense id is
    left out, so a label FleXray never trained on projects nothing.
    """
    by_name = {name: int(dense) for dense, name in stored_labels.items()}
    mapping = {}
    for folder, key in TRUTH_FOLDERS.items():
        for enhance_id, name in enhance_labels.get(key, {}).items():
            lowered = NAME_FIXES.get(name.lower(), name.lower())
            if lowered in by_name:
                mapping[(folder, int(enhance_id))] = by_name[lowered]
    return mapping


def channel_targets(stored_labels, label_names, aliases, dropped):
    """FleXray's model channel (1-based, background 0) for each dense id from 1 to the largest."""
    largest = max(int(dense) for dense in stored_labels)
    targets = []
    for dense in range(1, largest + 1):
        name = stored_labels.get(str(dense), stored_labels.get(dense, ""))
        name = aliases.get(name, name)
        targets.append(0 if name in dropped or name not in label_names else 1 + label_names.index(name))
    return targets


def load_labels_json(path):
    """ENHANCE.PET's labels.json, which carries trailing commas JSON refuses."""
    import re

    text = Path(path).read_text(encoding="utf-8")
    return json.loads(re.sub(r",(\s*[}\]])", r"\1", text))


# --- features --------------------------------------------------------------------------------------------

def physics_features(image):
    """What a radiographer would read of one image on the canvas, as a fixed vector of numbers.

    The intensity histogram (32 bins), the radial power spectrum in 16 log bands, gradient
    magnitude statistics, a Laplacian noise estimate, local contrast over 16 by 16 blocks, the
    zero share (collimation or burnt-in text) and the saturated share.
    """
    import numpy as np

    image = np.asarray(image, dtype=np.float64)
    histogram, _ = np.histogram(image, bins=PHYSICS_BINS, range=(0.0, 1.0))
    histogram = histogram / max(image.size, 1)
    spectrum = np.abs(np.fft.fftshift(np.fft.fft2(image - image.mean()))) ** 2
    side = image.shape[0]
    centre = side // 2
    yy, xx = np.ogrid[:side, :side]
    radius = np.sqrt((yy - centre) ** 2 + (xx - centre) ** 2)
    edges = np.linspace(0, centre, RADIAL_BANDS + 1)
    bands = np.array([spectrum[(radius >= lo) & (radius < hi)].mean() if ((radius >= lo) & (radius < hi)).any() else 0.0
                      for lo, hi in zip(edges[:-1], edges[1:])])
    bands = np.log10(bands + 1e-12)
    gy, gx = np.gradient(image)
    magnitude = np.hypot(gx, gy)
    laplacian = image[1:-1, 1:-1] * 4 - image[:-2, 1:-1] - image[2:, 1:-1] - image[1:-1, :-2] - image[1:-1, 2:]
    noise = float(np.median(np.abs(laplacian - np.median(laplacian)))) * 1.4826
    block = max(side // 16, 1)
    trimmed = image[:block * 16, :block * 16].reshape(16, block, 16, block).mean(axis=(1, 3))
    return np.concatenate([
        histogram, bands,
        [magnitude.mean(), magnitude.std(), np.percentile(magnitude, 90), noise, trimmed.std(),
         float((image <= 1e-3).mean()), float((image >= 1 - 1e-3).mean()), image.mean(), image.std()],
    ]).astype(np.float64)


def flexray_features(images, segmenter):
    """FleXray's reading of each image: every channel's mean probability and its area at 0.5."""
    import numpy as np
    import torch

    rows = []
    for image in images:
        with torch.inference_mode():
            probabilities = segmenter.predict(np.asarray(image, dtype=np.float32)).probabilities[0].float().cpu().numpy()
        rows.append(np.concatenate([probabilities.mean(axis=(1, 2)), (probabilities >= 0.5).mean(axis=(1, 2))]))
    return np.stack(rows)


def imagenet_features(images, weights, device):
    """An ImageNet ResNet-18's pooled features of each image, the grey repeated to three channels."""
    import numpy as np
    import torch
    import torchvision

    model = torchvision.models.resnet18()
    model.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True))
    model.fc = torch.nn.Identity()
    model.eval().to(device)
    mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1).to(device)
    std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1).to(device)
    rows = []
    with torch.inference_mode():
        for image in images:
            tensor = torch.from_numpy(np.asarray(image, dtype=np.float32))[None, None].repeat(1, 3, 1, 1).to(device)
            rows.append(model((tensor - mean) / std)[0].float().cpu().numpy())
    return np.stack(rows)


# --- the tests ---------------------------------------------------------------------------------------------

def standardise(a, b):
    """Both sets z-scored by the pooled mean and spread, a constant column left at 0."""
    import numpy as np

    pooled = np.concatenate([a, b])
    mean, spread = pooled.mean(axis=0), pooled.std(axis=0)
    spread[spread < 1e-12] = 1.0
    return (a - mean) / spread, (b - mean) / spread


def principal(a, b, components=PCA_COMPONENTS):
    """Both sets on the pooled principal components, as many as the data has up to `components`."""
    import numpy as np

    pooled = np.concatenate([a, b])
    centred = pooled - pooled.mean(axis=0)
    _, _, vt = np.linalg.svd(centred, full_matrices=False)
    axes = vt[:min(components, vt.shape[0])].T
    return (a - pooled.mean(axis=0)) @ axes, (b - pooled.mean(axis=0)) @ axes


def auc_of(scores, labels):
    """The area under the curve of scores for labels in {0, 1}, by rank (Mann-Whitney), ties halved."""
    import numpy as np

    scores, labels = np.asarray(scores, dtype=np.float64), np.asarray(labels)
    positives, negatives = int(labels.sum()), int((1 - labels).sum())
    if positives == 0 or negatives == 0:
        return 0.5
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores), dtype=np.float64)
    position = 0
    sorted_scores = scores[order]
    while position < len(scores):
        end = position
        while end + 1 < len(scores) and sorted_scores[end + 1] == sorted_scores[position]:
            end += 1
        ranks[order[position:end + 1]] = (position + end) / 2.0 + 1.0
        position = end + 1
    return float((ranks[labels == 1].sum() - positives * (positives + 1) / 2.0) / (positives * negatives))


def nearest_elsewhere(features, subjects, k=KNN):
    """Each sample's k nearest neighbours among the samples of other subjects. A subject is left out
    whole, in both sets, since the edit, the raw DRR and FluXray's image of one CT are one person:
    a neighbour of the same CT in the other set would tell the classifier nothing about the sets."""
    import numpy as np

    squared = (features ** 2).sum(axis=1)
    distances = squared[:, None] + squared[None, :] - 2.0 * features @ features.T
    distances[subjects[:, None] == subjects[None, :]] = np.inf
    return np.argsort(distances, axis=1)[:, :k]


def strata(labels, subjects):
    """How the labels may be shuffled when the two sets are alike: the samples of a subject seen in
    both sets among themselves, and the subjects seen in one set only whole, among each other."""
    import numpy as np

    mixed, single = [], []
    for subject in np.unique(subjects):
        where = np.flatnonzero(subjects == subject)
        (mixed if labels[where].min() != labels[where].max() else single).append(where)
    return mixed, single


def permuted_labels(labels, layers, rng):
    """One shuffle of the labels within the strata: the permutation test's draw under the null."""
    mixed, single = layers
    permuted = labels.copy()
    for where in mixed:
        permuted[where] = labels[where][rng.permutation(len(where))]
    if single:
        shuffled = [single[i] for i in rng.permutation(len(single))]
        for where, source in zip(single, shuffled):
            permuted[where] = labels[source[0]]
    return permuted


def c2st(a, b, groups_a, groups_b, seed, bootstraps=BOOTSTRAPS, permutations=PERMUTATIONS):
    """The classifier two-sample test: the AUC of a k-nearest-neighbour vote with each sample's own
    subject left out in both sets, its bootstrap interval over subjects, and the permutation
    p-value with the labels shuffled within the strata. The neighbours do not depend on the labels,
    so they are found once and every permutation only votes again."""
    import numpy as np

    rng = np.random.default_rng(seed)
    features = np.concatenate([a, b])
    labels = np.concatenate([np.zeros(len(a), dtype=int), np.ones(len(b), dtype=int)])
    subjects = np.concatenate([np.asarray(groups_a, dtype=str), np.asarray(groups_b, dtype=str)])
    nearest = nearest_elsewhere(features, subjects)
    scores = labels[nearest].mean(axis=1)
    auc = auc_of(scores, labels)
    members = [np.flatnonzero(subjects == s) for s in np.unique(subjects)]
    draws = []
    for _ in range(bootstraps):
        index = np.concatenate([members[c] for c in rng.integers(0, len(members), len(members))])
        draws.append(auc_of(scores[index], labels[index]))
    low, high = np.percentile(draws, [2.5, 97.5])
    layers = strata(labels, subjects)
    beaten = 0
    for _ in range(permutations):
        permuted = permuted_labels(labels, layers, rng)
        beaten += auc_of(permuted[nearest].mean(axis=1), permuted) >= auc
    return {"auc": auc, "low": float(low), "high": float(high), "p": (beaten + 1) / (permutations + 1)}


def mmd_of_kernel(kernel, labels):
    """The unbiased squared RBF MMD between the samples labelled 0 and 1, from the kernel of all of
    them, whose diagonal is 1."""
    import numpy as np

    x, y = (labels == 0).astype(np.float64), (labels == 1).astype(np.float64)
    n, m = x.sum(), y.sum()
    kx, ky = kernel @ x, kernel @ y
    return float((x @ kx - n) / (n * (n - 1)) + (y @ ky - m) / (m * (m - 1)) - 2.0 * (x @ ky) / (n * m))


def mmd_test(a, b, groups_a, groups_b, seed, permutations=PERMUTATIONS):
    """The RBF maximum mean discrepancy at the median-distance bandwidth, with its permutation
    p-value, the labels shuffled within the strata as the classifier's are."""
    import numpy as np

    rng = np.random.default_rng(seed)
    pooled = np.concatenate([a, b])
    labels = np.concatenate([np.zeros(len(a), dtype=int), np.ones(len(b), dtype=int)])
    subjects = np.concatenate([np.asarray(groups_a, dtype=str), np.asarray(groups_b, dtype=str)])
    squared = (pooled ** 2).sum(axis=1)
    distances = np.sqrt(np.maximum(squared[:, None] + squared[None, :] - 2.0 * pooled @ pooled.T, 0.0))
    bandwidth = max(float(np.median(distances[np.triu_indices(len(pooled), 1)])), 1e-6)
    kernel = np.exp(-(distances ** 2) / (2.0 * bandwidth ** 2))
    statistic = mmd_of_kernel(kernel, labels)
    layers = strata(labels, subjects)
    beaten = 0
    for _ in range(permutations):
        beaten += mmd_of_kernel(kernel, permuted_labels(labels, layers, rng)) >= statistic
    return {"mmd2": statistic, "bandwidth": bandwidth, "p": (beaten + 1) / (permutations + 1)}


def frechet(a, b):
    """The Frechet distance between the Gaussians fitted to two sets, by eigenvalues alone."""
    import numpy as np

    mean_a, mean_b = a.mean(axis=0), b.mean(axis=0)
    cov_a = np.atleast_2d(np.cov(a, rowvar=False))
    cov_b = np.atleast_2d(np.cov(b, rowvar=False))
    values, vectors = np.linalg.eigh(cov_a)
    root_a = (vectors * np.sqrt(np.maximum(values, 0.0))) @ vectors.T
    product = np.linalg.eigvalsh(root_a @ cov_b @ root_a)
    trace_root = np.sqrt(np.maximum(product, 0.0)).sum()
    return float(((mean_a - mean_b) ** 2).sum() + np.trace(cov_a) + np.trace(cov_b) - 2.0 * trace_root)


def kid(a, b, seed, subset=KID_SUBSET, repeats=KID_REPEATS):
    """The kernel inception distance's form: the unbiased polynomial-kernel MMD squared, averaged over subsets."""
    import numpy as np

    rng = np.random.default_rng(seed)
    dims = a.shape[1]

    def kernel(x, y):
        return (x @ y.T / dims + 1.0) ** 3

    size = min(subset, len(a), len(b))
    values = []
    for _ in range(repeats):
        x = a[rng.choice(len(a), size, replace=False)]
        y = b[rng.choice(len(b), size, replace=False)]
        kxx, kyy, kxy = kernel(x, x), kernel(y, y), kernel(x, y)
        values.append((kxx.sum() - np.trace(kxx)) / (size * (size - 1)) + (kyy.sum() - np.trace(kyy)) / (size * (size - 1))
                      - 2.0 * kxy.mean())
    return float(np.mean(values))


def compare(a, b, groups_a, groups_b, seed):
    """Every test of one feature space between two sets, standardised together."""
    za, zb = standardise(a, b)
    pa, pb = principal(za, zb)
    return {"n_a": int(len(a)), "n_b": int(len(b)), "c2st": c2st(za, zb, groups_a, groups_b, seed),
            "mmd": mmd_test(pa, pb, groups_a, groups_b, seed), "frechet64": frechet(pa, pb), "kid64": kid(pa, pb, seed)}


def split_half(features, groups, seed):
    """One set against itself: its subjects dealt into two halves, the null every comparison is read against."""
    import numpy as np

    rng = np.random.default_rng(seed)
    subjects = np.unique(groups)
    rng.shuffle(subjects)
    first = set(subjects[: len(subjects) // 2])
    mask = np.array([g in first for g in groups])
    if mask.sum() < 2 or (~mask).sum() < 2:
        return None
    return compare(features[mask], features[~mask], groups[mask], groups[~mask], seed)


def paired_metrics(a_images, b_images):
    """Where two sets share sample names: PSNR, a global SSIM and the phase-correlation shift of each pair."""
    import numpy as np

    rows = []
    for x, y in zip(a_images, b_images):
        mse = float(((x - y) ** 2).mean())
        psnr = 99.0 if mse < 1e-12 else 10.0 * math.log10(1.0 / mse)
        mu_x, mu_y = x.mean(), y.mean()
        var_x, var_y, cov = x.var(), y.var(), ((x - mu_x) * (y - mu_y)).mean()
        c1, c2 = (0.01) ** 2, (0.03) ** 2
        ssim = ((2 * mu_x * mu_y + c1) * (2 * cov + c2)) / ((mu_x ** 2 + mu_y ** 2 + c1) * (var_x + var_y + c2))
        spectrum = np.fft.fft2(x - x.mean()) * np.conj(np.fft.fft2(y - y.mean()))
        correlation = np.fft.ifft2(spectrum / (np.abs(spectrum) + 1e-12)).real
        peak = np.unravel_index(np.argmax(correlation), correlation.shape)
        shift = [int(p if p <= s // 2 else p - s) for p, s in zip(peak, correlation.shape)]
        rows.append({"psnr": float(psnr), "ssim": float(ssim), "shift_px": shift})
    return rows


def summarise_pairs(rows):
    import numpy as np

    if not rows:
        return None
    psnr = np.array([r["psnr"] for r in rows])
    ssim = np.array([r["ssim"] for r in rows])
    shift = np.array([math.hypot(*r["shift_px"]) for r in rows])
    return {"pairs": len(rows), "psnr_median": float(np.median(psnr)), "ssim_median": float(np.median(ssim)),
            "shift_px_median": float(np.median(shift)), "shift_px_p90": float(np.percentile(shift, 90))}


# --- stats ---------------------------------------------------------------------------------------------------

def load_set(folder, size, limit=None, only=None, index=None):
    """A folder's images on the canvas, with their stems and subjects, in name order; the subjects
    by the index of the samples where one is named (sample_index)."""
    import numpy as np

    found = images_in(folder)
    subjects = {stem: subject_in(index, stem) for stem in found}
    stems = sorted(stem for stem in found if only is None or subjects[stem] in only)
    stems = stems[:limit] if limit else stems
    if len(stems) < 4:
        raise Refused(f"{folder} holds {len(stems)} images; the tests need at least 4")
    images = np.stack([canvas(read_grey(found[stem]), size) for stem in stems])
    return stems, [subjects[stem] for stem in stems], images


def feature_spaces(args, sets):
    """Each feature space's matrix for each set, computed once."""
    import numpy as np

    spaces = {"physics": {name: np.stack([physics_features(image) for image in images]) for name, (_, _, images) in sets.items()}}
    if args.weights:
        from fxr import FleXraySegmenter

        segmenter = FleXraySegmenter.from_pretrained(args.weights, subfolder=args.member, device=args.device)
        spaces["flexray"] = {name: flexray_features(images, segmenter) for name, (_, _, images) in sets.items()}
    if args.imagenet_weights:
        spaces["imagenet"] = {name: imagenet_features(images, args.imagenet_weights, args.device)
                              for name, (_, _, images) in sets.items()}
    return spaces


def benjamini_hochberg(ps):
    """Benjamini-Hochberg q-values over several tests, so that one MMD rejection among several feature
    spaces is read at the family's level and not at each space's own."""
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    qs, running = [0.0] * len(ps), 1.0
    for rank, i in reversed(list(enumerate(order, start=1))):
        running = min(running, ps[i] * len(ps) / rank)
        qs[i] = min(1.0, running)
    return qs


def worst(verdicts):
    """The one word for several spaces: the least favourable of them."""
    order = {"separable": 3, "undecided": 2, "indistinguishable": 1, "matched": 0}
    return max(verdicts, key=lambda word: order[word]) if verdicts else "undecided"


def arm_comparisons(matrices, stems_a, groups_a, groups_b, seed):
    """Where set a holds edits in several seed arms: each arm alone against set b, and the first two
    arms against each other, the second null, which says how far the edit's own noise moves a set."""
    import numpy as np

    arms = sorted({arm_of(stem) for stem in stems_a} - {None})
    if len(arms) < 2:
        return None, None
    masks = {arm: np.array([arm_of(stem) == arm for stem in stems_a]) for arm in arms}
    each = {f"a{arm}": compare(matrices["a"][mask], matrices["b"], groups_a[mask], groups_b, seed)
            for arm, mask in masks.items()}
    first, second = masks[arms[0]], masks[arms[1]]
    null = compare(matrices["a"][first], matrices["a"][second], groups_a[first], groups_a[second], seed)
    return each, null


def paired_with(sets):
    """Set a's images paired with set b's of the same sample, an edit's arm set aside, as PSNR, SSIM
    and shift; None where no sample is in both."""
    stems_b = {stem: i for i, stem in enumerate(sets["b"][0])}
    pairs = [(i, stems_b[sample_of(stem)]) for i, stem in enumerate(sets["a"][0]) if sample_of(stem) in stems_b]
    if not pairs:
        return None
    return summarise_pairs(paired_metrics([sets["a"][2][i] for i, _ in pairs], [sets["b"][2][j] for _, j in pairs]))


def run_stats(args):
    import numpy as np

    index = sample_index(args.index)
    only = subject_filter(args.only)
    sets = {"a": load_set(args.a, args.size, args.limit, only, index), "b": load_set(args.b, args.size, args.limit, only, index)}
    spaces = feature_spaces(args, sets)
    absent = [name for name in args.require_spaces.split(",") if name and name not in spaces]
    if absent:
        raise Refused(f"the spaces {', '.join(absent)} were asked for and could not be read (their weights not named)")
    report = {"size": args.size, "seed": args.seed, "sets": {name: {"n": len(stems), "subjects": len(set(groups))}
                                                           for name, (stems, groups, _) in sets.items()}, "spaces": {}}
    groups_a, groups_b = np.array(sets["a"][1]), np.array(sets["b"][1])
    for space, matrices in spaces.items():
        entry = {"a_vs_b": compare(matrices["a"], matrices["b"], groups_a, groups_b, args.seed),
                 "b_split_half": split_half(matrices["b"], groups_b, args.seed)}
        each, null = arm_comparisons(matrices, sets["a"][0], groups_a, groups_b, args.seed)
        if each:
            entry["arms"], entry["arm_null"] = each, null
        report["spaces"][space] = entry
    report["verdict"] = worst(judge_spaces(report["spaces"]))
    report["paired"] = paired_with(sets)
    write_json(Path(args.out) / "stats.json", report)
    (Path(args.out) / "stats.md").write_text(stats_markdown(report), encoding="utf-8")
    print(stats_markdown(report))


def word_of(entry, q, reference_high):
    """One comparison's word from its classifier interval and its MMD q (schwingnet.realism.verdict)."""
    entry["mmd"]["q"] = round(q, 4)
    c = entry["c2st"]
    entry["verdict"] = realism.verdict(c["low"], c["high"], q, reference_high)
    return entry["verdict"]


def judge_spaces(spaces):
    """Each space's verdict, MMD read at its Benjamini-Hochberg q over the spaces, written into the
    entries. Where the edits come in seed arms, each arm alone is judged too, with its own q over the
    spaces, and a space whose arms disagree is undecided (schwingnet.realism.arm_verdict), as is
    one whose split-half null or arm null is itself separable (schwingnet.realism.through_nulls)."""
    names = list(spaces)
    qs = benjamini_hochberg([spaces[name]["a_vs_b"]["mmd"]["p"] for name in names])
    arm_keys = sorted(spaces[names[0]].get("arms", {})) if names else []
    arm_qs = {key: benjamini_hochberg([spaces[name]["arms"][key]["mmd"]["p"] for name in names]) for key in arm_keys}
    words = []
    for position, (name, q) in enumerate(zip(names, qs)):
        entry = spaces[name]
        null = entry["b_split_half"]
        reference_high = null["c2st"]["high"] if null else realism.CHANCE_AUC
        pooled = word_of(entry["a_vs_b"], q, reference_high)
        per_arm = [word_of(entry["arms"][key], arm_qs[key][position], reference_high) for key in arm_keys]
        null_lows = [n["c2st"]["low"] for n in (null, entry.get("arm_null")) if n]
        entry["nulls_separable"] = any(low > realism.INDISTINGUISHABLE_AUC for low in null_lows)
        entry["verdict"] = realism.through_nulls(realism.arm_verdict(pooled, per_arm), null_lows)
        words.append(entry["verdict"])
    return words


def stats_markdown(report):
    lines = [f"## realism stats at {report['size']} px: {report['verdict']}", ""]
    lines.append("| space | AUC (95% interval) | null AUC high | MMD p | MMD q | FD64 | KID64 | arms | arm null AUC | verdict |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for space, entry in report["spaces"].items():
        c, m = entry["a_vs_b"]["c2st"], entry["a_vs_b"]["mmd"]
        null = entry["b_split_half"]["c2st"]["high"] if entry["b_split_half"] else float("nan")
        arms = ", ".join(f"{key} {value['verdict']}" for key, value in sorted(entry.get("arms", {}).items())) or "-"
        arm_null = f"{entry['arm_null']['c2st']['auc']:.3f}" if entry.get("arm_null") else "-"
        lines.append(f"| {space} | {c['auc']:.3f} ({c['low']:.3f} to {c['high']:.3f}) | {null:.3f} | {m['p']:.3f} | "
                     f"{m.get('q', m['p']):.3f} | {entry['a_vs_b']['frechet64']:.3f} | "
                     f"{entry['a_vs_b']['kid64']:.4f} | {arms} | {arm_null} | {entry['verdict']}"
                     f"{' (a null is separable)' if entry.get('nulls_separable') else ''} |")
    if report.get("paired"):
        p = report["paired"]
        lines += ["", f"paired ({p['pairs']} images of a sample in both): PSNR median {p['psnr_median']:.2f} dB, SSIM median "
                  f"{p['ssim_median']:.3f}, shift median {p['shift_px_median']:.1f} px, p90 {p['shift_px_p90']:.1f} px"]
    sets = ", ".join(f"{name} {v['n']} images of {v['subjects']} subjects" for name, v in report["sets"].items())
    lines += ["", f"sets: {sets}; seed {report['seed']}", ""]
    return "\n".join(lines)


# --- inputs, poses, the draw, render, edit, filter, export ---------------------------------------------------------

def folder_files(folder):
    """A folder's files with their bytes and sha256, read once at the start of a run, so the record
    names the weights and the data the run read and not only where they lay."""
    folder = Path(folder)
    return [{"path": str(path.relative_to(folder)), "bytes": path.stat().st_size, "sha256": file_sha256(path)}
            for path in sorted(folder.rglob("*")) if path.is_file()]


def folder_digest(files):
    """One sha256 over a folder's files, each by its path and its own sha256."""
    import hashlib

    lines = "".join(f"{f['path']}\t{f['sha256']}\n" for f in files)
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()


def thunder_ids(db_root):
    """Every FluXray sample in its ThunderDB with its subject and split, by FleXray's own reader of
    each split (the reader the DRR study read FluXray through, tools/domain_gap.py)."""
    from fxr.datasets._thunderdb import open_thunderdb
    from fxr.datasets.storage import SplitThunderDBStorageBackend

    found = {}
    db = open_thunderdb(db_root)
    for split in sorted(db["_splits"].keys()):
        backend = None
        for grouping in ("subject", "sample"):
            try:
                backend = SplitThunderDBStorageBackend(db, dataset_name="FluXray", modality="xray", split=split,
                                                       label_key=None, affine_key=None, spacing_key=None,
                                                       subject_grouping=grouping, lazy_payload_refs=True, owns_database=False)
                break
            except (KeyError, ValueError, TypeError):
                continue
        if backend is None:
            raise Refused(f"FleXray's reader could not open split {split} of the FluXray ThunderDB {db_root}")
        for record in backend.records:
            found[record.data_id] = {"subject_id": record.subject_id or "", "split": split, "backend": backend,
                                     "record": record}
    return found


def eligible_subjects(sample_rows, volumes, truth):
    """The subjects FluXray holds whose CT and vertebra truth both landed, which the draw is made from."""
    return sorted({row["subject_id"] for row in sample_rows
                   if row["subject_id"] in volumes and ("Vertebrae", row["subject_id"]) in truth})


def environment_record():
    """The versions the run's python holds, each pinned package against its pin, torch and the GPU."""
    from importlib import metadata

    found, wrong = {}, []
    for pin in realism.PINS:
        name, _, wanted = pin.partition("==")
        try:
            found[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            found[name] = "absent"
        if found[name] != wanted:
            wrong.append(f"{name} {found[name]}, pinned {wanted}")
    try:
        import torch

        found["torch"] = torch.__version__
        found["cuda"] = torch.version.cuda or "none"
        found["gpu"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "none"
    except ImportError:
        found["torch"] = "absent"
    return found, wrong


def run_inputs(args):
    """Every input checked before a GPU second is spent, and recorded: the pins, the klein the recipe
    names and no other, FluXray's samples against its ThunderDB, the CTs and truth that landed, the
    FleXray bundle and the ImageNet weights, each with its sha256."""
    environment, wrong = environment_record()
    if wrong and not args.no_pins:
        raise Refused("the environment differs from the frozen pins: " + "; ".join(wrong))
    model = realism.FLUXRAY.model
    if not (Path(args.klein) / "model_index.json").is_file():
        raise Refused(f"no model_index.json in {args.klein}: the recipe's {model} has not landed, and no other klein stands in")
    rows = read_rows(args.samples)
    ids = thunder_ids(args.db)
    unknown = [row["sample_id"] for row in rows if row["sample_id"] not in ids]
    if len(unknown) == len(rows):
        raise Refused(f"no sample of samples.csv is in the ThunderDB (samples.csv names {rows[0]['sample_id'] if rows else 'nothing'}, "
                      f"the ThunderDB {next(iter(ids), 'nothing')}), so FluXray's image of a drawn sample could not be read")
    moved = [row["sample_id"] for row in rows if row["sample_id"] in ids and ids[row["sample_id"]]["subject_id"] not in ("", row["subject_id"])]
    if moved:
        raise Refused(f"{len(moved)} samples have another subject in the ThunderDB than in samples.csv, {moved[0]} among them")
    volumes, truth = volumes_under(args.ct), truth_under(args.truth)
    eligible = eligible_subjects([row for row in rows if row["sample_id"] in ids], volumes, truth)
    if len(eligible) < realism.REPLICATION.subjects:
        raise Refused(f"{len(eligible)} FluXray subjects have a landed CT and vertebra truth, fewer than the "
                      f"{realism.REPLICATION.subjects} the plan draws (FluXray names {rows[0]['subject_id'] if rows else 'none'}, "
                      f"the CTs {next(iter(volumes), 'none')})")
    for path in (Path(args.bundle) / "ensemble.json", Path(args.imagenet)):
        if not path.is_file():
            raise Refused(f"no {path}")
    klein, bundle, thunder = folder_files(args.klein), folder_files(args.bundle), folder_files(args.db)
    record = {"model": model, "klein": str(args.klein), "klein_sha256": folder_digest(klein), "klein_files": klein,
              "bundle": str(args.bundle), "bundle_sha256": folder_digest(bundle), "db_sha256": folder_digest(thunder),
              "imagenet": str(args.imagenet), "imagenet_sha256": file_sha256(args.imagenet),
              "samples": str(args.samples), "samples_sha256": file_sha256(args.samples), "db": str(args.db),
              "samples_rows": len(rows), "samples_not_in_db": len(unknown), "not_in_db": sorted(unknown),
              "ct": str(args.ct), "truth": str(args.truth),
              "eligible": eligible, "environment": environment, "pins_differ": wrong}
    write_json(args.out, record)
    print(f"inputs: {model} ({len(klein)} files), {len(rows)} FluXray samples ({len(unknown)} not in the ThunderDB), "
          f"{len(eligible)} subjects with CT and truth; environment as pinned: {'no' if wrong else 'yes'}")


def split_subjects(subjects, limit, seed, train_fraction=TRAIN_FRACTION):
    """The subjects drawn, limit of them by the seed (schwingnet.realism.draw, so neither the order of
    the names nor which others landed decides who is in), in the order drawn, and dealt by the same
    seed into a training and an evaluation split by subject, never by image, so no person is on both
    sides of the LoRA."""
    import numpy as np

    taken = realism.draw(sorted(subjects), limit, seed, "subject") if limit else sorted(subjects)
    if len(taken) < 2:
        raise Refused(f"{len(taken)} subject(s); a split needs at least 2")
    order = list(np.random.default_rng(seed).permutation(len(taken)))
    cut = max(1, min(len(taken) - 1, round(train_fraction * len(taken))))
    train = sorted(taken[i] for i in order[:cut])
    return taken, train, sorted(set(taken) - set(train))


def shards_of(taken, size):
    """The drawn subjects in runs of size, in the order drawn: the flow's foreach, one GPU task each."""
    return [taken[i:i + size] for i in range(0, len(taken), size)]


def run_split(args):
    subjects = read_json(args.poses)["subjects"]
    if args.eligible:
        allowed = set(read_json(args.eligible)["eligible"])
        subjects = [s for s in subjects if s in allowed]
    taken, train, evaluation = split_subjects(subjects, args.limit, args.seed, args.train_fraction)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in (("all", taken), ("train", train), ("eval", evaluation)):
        (out / f"{name}.txt").write_text("".join(f"{s}\n" for s in rows), encoding="utf-8")
    shards = shards_of(taken, args.shard_size) if args.shard_size else []
    for number, shard in enumerate(shards):
        (out / "shards").mkdir(exist_ok=True)
        (out / "shards" / f"{number:03d}.txt").write_text("".join(f"{s}\n" for s in shard), encoding="utf-8")
    write_json(out / "split.json", {"seed": args.seed, "train_fraction": args.train_fraction, "from": len(subjects),
                                    "all": len(taken), "train": len(train), "eval": len(evaluation), "shards": len(shards)})
    print(f"{len(taken)} of {len(subjects)} subjects drawn (seed {args.seed}): {len(train)} train, {len(evaluation)} eval, "
          f"{len(shards)} shards")


def run_poses(args):
    rows = read_rows(args.samples)
    absent = set(read_json(args.inputs)["not_in_db"]) if args.inputs else set()
    found = poses_from_samples([row for row in rows if row["sample_id"] not in absent])
    found["not_in_db"] = sum(row["sample_id"] in absent for row in rows)
    write_json(args.out, found)
    print(f"{len(found['samples'])} samples of {len(found['subjects'])} subjects at the paper's poses; "
          f"{len(found['mismatches'])} rows at other poses and {found['not_in_db']} not in the ThunderDB left out")


def load_subject(ct_path, truth_paths, mapping):
    """One ENHANCE.PET study: the clamped CT, its affine and FleXray's dense labels from the truth
    files by folder."""
    import nibabel
    import numpy as np

    image = nibabel.load(str(ct_path))
    volume = np.asarray(image.dataobj, dtype=np.float32)
    while volume.ndim > 3 and volume.shape[-1] == 1:
        volume = volume[..., 0]
    np.clip(volume, HU_LOW, HU_HIGH, out=volume)
    volume[volume <= AIR_CLAMP_HU] = HU_LOW
    dense = np.zeros(volume.shape, dtype=np.uint8)
    for folder, path in truth_paths.items():
        labels = np.asarray(nibabel.load(str(path)).dataobj).astype(np.int32)
        if labels.shape != volume.shape:
            raise Refused(f"{path.name} in {folder} is {labels.shape}, the CT {volume.shape}")
        for (where, enhance_id), dense_id in mapping.items():
            if where == folder:
                dense[labels == enhance_id] = dense_id
    return np.ascontiguousarray(volume), np.asarray(image.affine, dtype=np.float64), dense


def volume_centre_mm(shape, affine):
    import numpy as np

    centre = np.array([(s - 1) / 2.0 for s in shape] + [1.0])
    return (affine @ centre)[:3].tolist()


def render_one(volume, affine, dense, pose, recipe, targets, channels, device):
    """One raw DRR and its projected channel masks at one of the paper's poses."""
    import numpy as np
    import torch
    from fxr.drr import DRRRenderRequest, render_drr
    from fxr.models.camera.runtime import scale_rendered_images

    y, z, alpha = pose
    intrinsics = {"sdd": [recipe.render_sdd_mm], "delx": [recipe.render_spacing_mm], "dely": [recipe.render_spacing_mm],
                  "x0": [0.0], "y0": [0.0], "height": recipe.render_pixels, "width": recipe.render_pixels}
    request = DRRRenderRequest(rot=torch.tensor([[float(alpha), 0.0, 0.0]]), xyz=torch.tensor([[0.0, float(y), float(z)]]),
                               intrinsics=intrinsics, isocenter=torch.tensor([volume_centre_mm(volume.shape, affine)], dtype=torch.float32),
                               orientation="AP", n_samples=RAY_SAMPLES, orthographic=False)
    with torch.inference_mode():
        result = render_drr(volume=torch.from_numpy(volume)[None].to(device), label=torch.from_numpy(dense).to(device),
                            affine=torch.as_tensor(affine, dtype=torch.float32).to(device), request=request,
                            max_label=len(targets), foreground_collapse_map=targets, output_num_label_channels=channels + 1)
        image = scale_rendered_images(result.images)[0, 0].float().cpu().numpy()
        masks = result.labels[0, 1:].cpu().numpy() > 0.5
    return image.astype(np.float16), masks


def drawn_samples(poses, subjects, per_subject, seed):
    """Each subject's samples, per_subject of them drawn by the seed among the subject's recorded
    poses (schwingnet.realism.draw), so the poses rendered span the grid across subjects rather than
    the same few positions in every subject's list."""
    by_subject = {}
    for sample in poses["samples"]:
        by_subject.setdefault(sample["subject_id"], {})[sample["sample_id"]] = sample
    chosen = {}
    for subject in subjects:
        rows = by_subject.get(subject, {})
        names = realism.draw(sorted(rows), per_subject, seed, f"pose|{subject}") if per_subject and rows else sorted(rows)
        chosen[subject] = [rows[name] for name in names]
    return chosen


def run_render(args):
    import numpy as np
    import yaml
    from fxr import FleXraySegmenter
    from fxr.configs import datasets as dataset_configs

    poses = read_json(args.poses)
    recipe = realism.EditRecipe(render_pixels=args.pixels)
    enhance = load_labels_json(args.labels or ENHANCE_LABELS)
    moose = yaml.safe_load((Path(dataset_configs.__file__).parent / "MOOSE.yml").read_text(encoding="utf-8"))
    stored = {str(k): v for k, v in moose["stored_labels"].items()}
    mapping = moose_dense_ids(enhance, stored)
    segmenter = FleXraySegmenter.from_pretrained(args.weights, subfolder=args.member, device="cpu")
    label_names = list(segmenter.label_names)
    protocol = next(iter(moose.get("protocol_label_aliases", {}).values()), {})
    dropped = set(next(iter(moose.get("protocol_drop_labels", {}).values()), []))
    targets = channel_targets(stored, label_names, protocol, dropped)
    out = Path(args.out)
    (out / "raw").mkdir(parents=True, exist_ok=True)
    (out / "masks").mkdir(exist_ok=True)
    write_json(out / "label_names.json", label_names)
    write_json(out / "recipe.json", realism.as_record(recipe))
    only = subject_filter(args.only)
    subjects = [s for s in poses["subjects"] if only is None or s in only]
    subjects = subjects[:args.limit] if args.limit else subjects
    chosen = drawn_samples(poses, subjects, args.per_subject, args.draw_seed)
    volumes, truth = volumes_under(args.ct), truth_under(args.truth)
    rows, started = [], time.time()
    with open(out / "manifest.jsonl", "a", encoding="utf-8") as manifest:
        for subject in subjects:
            todo = [s for s in chosen[subject] if not (out / "raw" / f"{s['sample_id']}.npy").exists()]
            if not todo:
                continue
            if subject not in volumes or ("Vertebrae", subject) not in truth:
                raise Refused(f"{subject} was drawn but its CT or vertebra truth is not under the data root")
            truth_paths = {folder: truth[(folder, subject)] for folder in TRUTH_FOLDERS if (folder, subject) in truth}
            volume, affine, dense = load_subject(volumes[subject], truth_paths, mapping)
            digests = {"ct_sha256": file_sha256(volumes[subject]),
                       "truth_sha256": {folder: file_sha256(path) for folder, path in truth_paths.items()}}
            for sample in todo:
                tick = time.time()
                image, masks = render_one(volume, affine, dense, (sample["y"], sample["z"], sample["alpha"]), recipe, targets,
                                          len(label_names), args.device)
                np.save(out / "raw" / f"{sample['sample_id']}.npy", image)
                np.save(out / "masks" / f"{sample['sample_id']}.npy", np.packbits(masks, axis=-1))
                row = dict(sample, pixels=args.pixels, seconds=round(time.time() - tick, 3), **digests)
                manifest.write(json.dumps(row, sort_keys=True) + "\n")
                manifest.flush()
                rows.append(row)
    print(f"rendered {len(rows)} views of {len(subjects)} subjects in {time.time() - started:.0f} s to {out}")


def run_edit(args):
    import numpy as np
    import torch
    from diffusers import Flux2KleinPipeline
    from PIL import Image

    recipe = realism.EditRecipe(model=args.model, steps=args.steps, guidance=args.guidance, lora=args.lora or "")
    problems = realism.recipe_problems(recipe)
    if problems:
        raise Refused("; ".join(problems))
    samples = manifest_rows(args.raw)
    found = images_in(Path(args.raw) / "raw")
    only = subject_filter(args.only)
    stems = sorted(stem for stem in found if stem in samples and (only is None or samples[stem]["subject_id"] in only))
    stems = stems[:args.limit] if args.limit else stems
    out = Path(args.out)
    (out / "edited").mkdir(parents=True, exist_ok=True)
    write_json(out / "recipe.json", dict(realism.as_record(recipe), weights=str(args.weights), arms=args.arms))
    todo = [(stem, arm) for stem in stems for arm in range(args.arms)
            if not (out / "edited" / f"{edit_name(stem, arm)}.npy").exists()]
    if not todo:
        print(f"edited 0 raw DRRs: all {len(stems)} were edited in {args.arms} arm(s) before")
        return
    dtype = {"bfloat16": torch.bfloat16, "float16": torch.float16, "float32": torch.float32}[recipe.dtype]
    pipe = Flux2KleinPipeline.from_pretrained(args.weights, torch_dtype=dtype).to(args.device)
    if args.lora:
        pipe.load_lora_weights(args.lora)
    with open(out / "edits.jsonl", "a", encoding="utf-8") as log:
        for stem, arm in todo:
            raw = read_grey(found[stem])
            sample = samples[stem]
            seed = realism.seed_for(sample["subject_id"], int(sample["grid_pose"]), arm)
            tick = time.time()
            picture = Image.fromarray(np.clip(np.rint(raw * 255), 0, 255).astype(np.uint8)).convert("RGB")
            result = pipe(image=picture, prompt=recipe.prompt, height=raw.shape[0], width=raw.shape[1],
                          num_inference_steps=recipe.steps, guidance_scale=recipe.guidance,
                          generator=torch.Generator(args.device).manual_seed(seed)).images[0]
            edited = np.asarray(result.convert("L"), dtype=np.float32) / 255.0
            edited[raw < recipe.foreground_floor] = 0.0
            np.save(out / "edited" / f"{edit_name(stem, arm)}.npy", edited.astype(np.float16))
            if args.png:
                write_png(out / "png" / f"{edit_name(stem, arm)}.png", edited)
            log.write(json.dumps({"sample_id": stem, "arm": arm, "seed": seed, "seconds": round(time.time() - tick, 3)}) + "\n")
            log.flush()
    print(f"edited {len(todo)} views ({len(stems)} raw DRRs, {args.arms} arm(s) each) to {out}")


def soft_dice(probabilities, truth):
    """FluXray's filter statistic: the soft Dice averaged over the channels with any truth and over the
    background, read as what no channel claims (the paper: empty labels ignored, background included)."""
    import numpy as np

    channels = truth.reshape(truth.shape[0], -1).astype(np.float64)
    present = channels.any(axis=1)
    p = probabilities.reshape(probabilities.shape[0], -1).astype(np.float64)[present]
    t = channels[present]
    background_t = (~truth.any(axis=0)).reshape(1, -1).astype(np.float64)
    background_p = (1.0 - probabilities.max(axis=0)).reshape(1, -1).astype(np.float64)
    p, t = np.concatenate([p, background_p]), np.concatenate([t, background_t])
    return float(np.mean(2.0 * (p * t).sum(axis=1) / ((p ** 2).sum(axis=1) + (t ** 2).sum(axis=1) + 1e-7)))


def filter_rows(scores):
    """FluXray's paired filter over scored samples: rows of (sample, pose, raw, flux, delta, kept), per pose group."""
    groups = {}
    for row in scores:
        groups.setdefault(row["pose_id"], []).append(row)
    out = []
    for pose_id, rows in sorted(groups.items()):
        deltas = [r["flux_soft_dice"] - r["raw_soft_dice"] for r in rows]
        bound = realism.keep_cutoff(deltas)
        for row, delta, keep in zip(rows, deltas, realism.kept(deltas)):
            out.append(dict(row, delta=round(delta, 6), bound=round(bound, 6), kept=keep))
    return out


SCORE_COLUMNS = ["sample_id", "subject_id", "pose_id", "raw_soft_dice", "flux_soft_dice"]


def score_edits(args, only):
    """The flux000 member's soft Dice of each edit and of its raw DRR against the exact masks at
    FleXray's 256 pixels, the pose group the filter compares within being the grid pose the render
    recorded."""
    import numpy as np
    import torch
    from fxr import FleXraySegmenter

    segmenter = FleXraySegmenter.from_pretrained(args.weights, subfolder=args.member, device=args.device)
    samples = manifest_rows(args.raw)
    raw_found = images_in(Path(args.raw) / "raw")
    edited_found = images_in(Path(args.edited) / "edited")
    masks_dir = Path(args.raw) / "masks"
    scores = []
    for name in sorted(edited_found):
        stem = sample_of(name)
        if stem not in raw_found or stem not in samples or not (masks_dir / f"{stem}.npy").exists():
            continue
        if only is not None and samples[stem]["subject_id"] not in only:
            continue
        raw, edited = read_grey(raw_found[stem]), read_grey(edited_found[name])
        truth = np.unpackbits(np.load(masks_dir / f"{stem}.npy"), axis=-1)[:, :raw.shape[0], :raw.shape[1]].astype(bool)
        factor = raw.shape[0] // CANVAS
        truth_small = np.stack([block_majority(channel, factor) for channel in truth]) if factor > 1 else truth
        with torch.inference_mode():
            raw_p = segmenter.predict(raw).probabilities[0].float().cpu().numpy()
            flux_p = segmenter.predict(edited).probabilities[0].float().cpu().numpy()
        scores.append({"sample_id": name, "subject_id": samples[stem]["subject_id"], "pose_id": int(samples[stem]["grid_pose"]),
                       "raw_soft_dice": soft_dice(raw_p, truth_small), "flux_soft_dice": soft_dice(flux_p, truth_small)})
    return scores


def run_score(args):
    scores = score_edits(args, subject_filter(args.only))
    write_rows(args.out, scores, SCORE_COLUMNS)
    print(f"scored {len(scores)} edits against their raw DRRs")


def keep_scores(scores, edited_dir, out):
    """The paired filter over every score at once, since a pose group spans subjects and arms."""
    edited_found = images_in(Path(edited_dir) / "edited")
    rows = filter_rows([s for s in scores if not math.isnan(s["raw_soft_dice"])])
    columns = [*SCORE_COLUMNS, "delta", "bound", "kept"]
    write_rows(Path(out) / "filter_kept.csv", [r for r in rows if r["kept"]], columns)
    write_rows(Path(out) / "filter_dropped.csv", [r for r in rows if not r["kept"]], columns)
    link_kept(Path(out) / "kept", {r["sample_id"]: edited_found[r["sample_id"]] for r in rows if r["kept"]})
    return rows


def run_keep(args):
    scores = []
    for path in sorted(Path(args.scores).glob("*.csv")):
        for row in read_rows(path):
            scores.append(dict(row, pose_id=int(row["pose_id"]), raw_soft_dice=float(row["raw_soft_dice"]),
                               flux_soft_dice=float(row["flux_soft_dice"])))
    rows = keep_scores(scores, args.edited, args.out)
    kept = sum(r["kept"] for r in rows)
    print(f"{kept} of {len(rows)} edits kept ({100.0 * kept / max(len(rows), 1):.1f}%); the paper kept about 96%")


def run_filter(args):
    rows = keep_scores(score_edits(args, None), args.edited, args.out)
    kept = sum(r["kept"] for r in rows)
    print(f"{kept} of {len(rows)} edits kept ({100.0 * kept / max(len(rows), 1):.1f}%); the paper kept about 96%")


def link_kept(folder, found):
    """The kept edits as one folder of links, so stats reads the filtered set as it reads any other."""
    folder.mkdir(parents=True, exist_ok=True)
    for stem, path in found.items():
        link = folder / path.name
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(Path(os.path.relpath(path, folder)))
    return len(found)


def run_fluxray_export(args):
    """FluXray's images of exactly the samples rendered (the render's manifest), so the comparison
    holds the CT and the pose the same on both sides; or, with no manifest, every sample of the
    subjects named."""
    import numpy as np

    ids = thunder_ids(args.db)
    if args.samples:
        wanted = sorted(manifest_rows(args.samples) if Path(args.samples).is_dir() else subject_filter(args.samples))
    else:
        subjects = subject_filter(args.subjects) if args.subjects else None
        wanted = sorted(s for s, row in ids.items() if subjects is None or row["subject_id"] in subjects)
    missing = [s for s in wanted if s not in ids]
    if missing:
        raise Refused(f"{len(missing)} of {len(wanted)} samples are not in the ThunderDB, {missing[0]} among them")
    out = Path(args.out)
    (out / "img").mkdir(parents=True, exist_ok=True)
    rows = []
    for sample_id in wanted[:args.limit] if args.limit else wanted:
        entry = ids[sample_id]
        image = np.asarray(entry["backend"].load(entry["record"], "image"), dtype=np.float32).squeeze()
        if image.ndim != 2:
            raise Refused(f"FluXray's {sample_id} is {image.shape}, not one grey image")
        np.save(out / "img" / f"{sample_id}.npy", image.astype(np.float16))
        rows.append({"sample_id": sample_id, "subject_id": entry["subject_id"], "split": entry["split"], "pixels": image.shape[-1]})
    write_rows(out / "index.csv", rows, ["sample_id", "subject_id", "split", "pixels"])
    print(f"exported {len(rows)} FluXray samples to {out}")


# --- pairs, the LoRA configuration, the measurement study -----------------------------------------------------

def build_pairs(control_found, target_found, out, size):
    """Matching stems of two folders written as the trainer's control/ and target/ with the prompt as caption."""
    out = Path(out)
    shared = sorted(set(control_found) & set(target_found))
    for stem in shared:
        control = canvas(read_grey(control_found[stem]), size)
        target = canvas(read_grey(target_found[stem]), size)
        write_png(out / "control" / f"{stem}.png", control)
        write_png(out / "target" / f"{stem}.png", target)
        (out / "target" / f"{stem}.txt").write_text(realism.PROMPT + "\n", encoding="utf-8")
    write_json(out / "manifest.json", {"pairs": len(shared), "pixels": size, "prompt": realism.PROMPT})
    return len(shared)


def target_pixels(target_found):
    """The smallest side among the targets: the honest size to train at, never upsampled."""
    sizes = [read_grey(path).shape[0] for path in list(target_found.values())[:8]]
    return min(sizes) if sizes else 0


def run_pairs(args):
    control = images_in(Path(args.control) / "raw" if (Path(args.control) / "raw").exists() else args.control)
    target_dir = Path(args.target)
    for sub in ("edited", "img", "raw"):
        if (target_dir / sub).exists():
            target_dir = target_dir / sub
            break
    target = images_in(target_dir)
    target = {sample_of(stem): path for stem, path in target.items()}
    only = subject_filter(args.only)
    if only is not None:
        control = {stem: path for stem, path in control.items() if subject_of(stem) in only}
        target = {stem: path for stem, path in target.items() if subject_of(stem) in only}
    size = min(args.size, target_pixels(target) or args.size)
    count = build_pairs(control, target, args.out, size)
    print(f"{count} pairs at {size} px under {args.out}")


def run_lora_config(args):
    manifest = read_json(Path(args.pairs) / "manifest.json")
    plan = realism.LoraPlan(base=args.base, rank=args.rank, alpha=args.alpha, learning_rate=args.lr, steps=args.steps,
                            resolution=min(args.resolution, int(manifest["pixels"])), seed=args.seed, target=args.target)
    problems = realism.lora_problems(plan)
    if problems:
        raise Refused("; ".join(problems))
    config = realism.lora_config(plan, str(Path(args.pairs).resolve()), str(Path(args.training_folder).resolve()))
    write_json(args.out, config)
    print(f"{args.out}: {plan.base}, rank {plan.rank}, {plan.steps} steps at {plan.resolution} px, seed {plan.seed}, "
          f"{manifest['pairs']} pairs")


def endplate_angle_deg(mask):
    """The angle of a body's superior endplate: a line fitted to the top edge over the middle 60% of
    its width, in degrees from horizontal; None for a mask too thin to read."""
    import numpy as np

    columns = np.flatnonzero(mask.any(axis=0))
    if len(columns) < 5:
        return None
    lo, hi = columns[0] + int(0.2 * len(columns)), columns[0] + int(0.8 * len(columns))
    xs, ys = [], []
    for column in range(lo, hi + 1):
        rows = np.flatnonzero(mask[:, column])
        if len(rows):
            xs.append(column)
            ys.append(rows[0])
    if len(xs) < 3:
        return None
    slope = np.polyfit(xs, ys, 1)[0]
    return float(math.degrees(math.atan(slope)))


def measure_rows(masks_dir, label_names, limit=None):
    """Each lumbar body's endplate angle read from the exact 1024 mask and from its 256 copy."""
    import numpy as np

    rows = []
    paths = sorted(Path(masks_dir).glob("*.npy"))
    for path in paths[:limit] if limit else paths:
        packed = np.load(path)
        full = np.unpackbits(packed, axis=-1).astype(bool)
        side = full.shape[1]
        full = full[:, :side, :side]
        factor = side // CANVAS
        for name in LUMBAR:
            if name not in label_names:
                continue
            channel = full[label_names.index(name)]
            if channel.sum() < 64:
                continue
            fine = endplate_angle_deg(channel)
            coarse = endplate_angle_deg(block_majority(channel, factor)) if factor > 1 else fine
            if fine is None or coarse is None:
                continue
            rows.append({"sample_id": path.stem, "level": name, "angle_1024": round(fine, 3), "angle_256": round(coarse, 3),
                         "difference": round(abs(fine - coarse), 3)})
    return rows


def run_measure(args):
    import numpy as np

    label_names = read_json(Path(args.masks) / "label_names.json")
    rows = measure_rows(Path(args.masks) / "masks", label_names, args.limit)
    write_rows(Path(args.out) / "endplate_angles.csv", rows, ["sample_id", "level", "angle_1024", "angle_256", "difference"])
    differences = np.array([r["difference"] for r in rows]) if rows else np.array([0.0])
    summary = {"bodies": len(rows), "difference_median_deg": float(np.median(differences)),
               "difference_p90_deg": float(np.percentile(differences, 90)), "table": realism.measurement_rows()}
    write_json(Path(args.out) / "measure.json", summary)
    (Path(args.out) / "measure.md").write_text(measure_markdown(summary), encoding="utf-8")
    print(f"{len(rows)} lumbar endplates: |angle at 1024 - angle at 256| median {summary['difference_median_deg']:.2f} deg, "
          f"p90 {summary['difference_p90_deg']:.2f} deg")


def measure_markdown(summary):
    """The measurement as the job's report prints it: the endplate angles read from the exact masks
    at both sizes, then the resolution table the recipe's geometry fixes."""
    lines = [f"## realism measure: {summary['bodies']} lumbar endplates", "",
             f"|angle at 1024 - angle at 256|: median {summary['difference_median_deg']:.2f} deg, "
             f"p90 {summary['difference_p90_deg']:.2f} deg", "",
             "| source to object (mm) | pixels | pixel at isocentre (mm) | endplate (px) | angle quantum (deg) |",
             "| --- | --- | --- | --- | --- |"]
    for row in summary["table"]:
        lines.append(f"| {row['sod_mm']} | {row['pixels']} | {row['pixel_mm']:.3f} | {row['endplate_px']:.1f} | "
                     f"{row['angle_quantum_deg']:.2f} |")
    return "\n".join(lines) + "\n"


# --- the command line ---------------------------------------------------------------------------------------------

def parser():
    top = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = top.add_subparsers(dest="command", required=True)
    p = sub.add_parser("inputs", help="every input checked and recorded with its sha256 before a GPU second is spent")
    for name in ("--samples", "--db", "--ct", "--truth", "--klein", "--bundle", "--imagenet", "--out"):
        p.add_argument(name, required=True)
    p.add_argument("--no-pins", action="store_true", help="record pins that differ instead of refusing, for a test")
    p.set_defaults(run=run_inputs)
    p = sub.add_parser("poses", help="FluXray's samples.csv checked against the paper's pose grid")
    p.add_argument("--samples", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--inputs", default="", help="the inputs record, whose samples missing from the ThunderDB are left out")
    p.set_defaults(run=run_poses)
    p = sub.add_parser("split", help="the subjects dealt into a training and an evaluation split, by subject")
    p.add_argument("--poses", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--eligible", default="", help="the inputs record, whose eligible subjects the draw is made from")
    p.add_argument("--limit", type=int, default=0, help="subjects drawn by the seed; 0 takes every one")
    p.add_argument("--seed", type=int, default=PLAN.draw_seed)
    p.add_argument("--train-fraction", type=float, default=TRAIN_FRACTION)
    p.add_argument("--shard-size", type=int, default=0, help="subjects a shard; 0 writes no shards")
    p.set_defaults(run=run_split)
    p = sub.add_parser("render", help="raw DRRs at the recorded poses from ENHANCE.PET CTs, with exact masks")
    for name in ("--ct", "--truth", "--poses", "--out", "--weights"):
        p.add_argument(name, required=True)
    p.add_argument("--labels", default="", help="ENHANCE.PET's labels.json; default: the copy grid/enhance-pet-labels.json")
    p.add_argument("--member", default="members/flux000")
    p.add_argument("--pixels", type=int, default=1024)
    p.add_argument("--limit", type=int, default=0, help="subjects")
    p.add_argument("--per-subject", type=int, default=0, help="poses drawn per subject; 0 renders every recorded one")
    p.add_argument("--draw-seed", type=int, default=PLAN.draw_seed, help="the seed the poses are drawn by")
    p.add_argument("--only", default="", help="a file of subject ids to keep")
    p.add_argument("--device", default="cuda")
    p.set_defaults(run=run_render)
    p = sub.add_parser("edit", help="the FLUX.2 klein edit, zero-shot or through a LoRA, at the render's size")
    for name in ("--raw", "--weights", "--out"):
        p.add_argument(name, required=True)
    p.add_argument("--model", default=realism.FLUXRAY.model, choices=sorted(realism.MODELS))
    p.add_argument("--lora", default="")
    p.add_argument("--steps", type=int, default=realism.FLUXRAY.steps)
    p.add_argument("--guidance", type=float, default=realism.FLUXRAY.guidance)
    p.add_argument("--arms", type=int, default=1, help="seeds per raw DRR")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--only", default="", help="a file of subject ids to keep")
    p.add_argument("--png", action="store_true")
    p.add_argument("--device", default="cuda")
    p.set_defaults(run=run_edit)
    p = sub.add_parser("filter", help="FluXray's paired soft-Dice filter with the flux000 member: score, then keep")
    for name in ("--raw", "--edited", "--weights", "--out"):
        p.add_argument(name, required=True)
    p.add_argument("--member", default="members/flux000")
    p.add_argument("--device", default="cuda")
    p.set_defaults(run=run_filter)
    p = sub.add_parser("score", help="the flux000 soft Dice of each edit and its raw DRR, one shard's, as a CSV")
    for name in ("--raw", "--edited", "--weights", "--out"):
        p.add_argument(name, required=True)
    p.add_argument("--only", default="", help="a file of subject ids to keep")
    p.add_argument("--member", default="members/flux000")
    p.add_argument("--device", default="cuda")
    p.set_defaults(run=run_score)
    p = sub.add_parser("keep", help="the paired filter over every shard's scores at once, since a pose group spans them")
    for name in ("--scores", "--edited", "--out"):
        p.add_argument(name, required=True)
    p.set_defaults(run=run_keep)
    p = sub.add_parser("fluxray-export", help="FluXray's images out of its ThunderDB as .npy")
    p.add_argument("--db", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--samples", default="", help="a render folder (its manifest) or a file of sample ids: exactly those")
    p.add_argument("--subjects", default="", help="with no --samples, a file of subject ids: every sample of theirs")
    p.add_argument("--limit", type=int, default=0)
    p.set_defaults(run=run_fluxray_export)
    p = sub.add_parser("stats", help="the metric suite between two image folders, with the second's split-half null")
    for name in ("--a", "--b", "--out"):
        p.add_argument(name, required=True)
    p.add_argument("--weights", default="", help="FleXray's bundle, for the flexray feature space")
    p.add_argument("--member", default="members/flux000")
    p.add_argument("--imagenet-weights", default="", help="torchvision's resnet18 .pth, for the imagenet space")
    p.add_argument("--size", type=int, default=CANVAS)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--only", default="", help="a file of subject ids to keep, in every set")
    p.add_argument("--index", default="", help="the render folder whose manifest names each sample's subject")
    p.add_argument("--require-spaces", default="", help="comma-separated spaces whose absence refuses the run")
    p.add_argument("--seed", type=int, default=PLAN.stats_seed)
    p.add_argument("--device", default="cuda")
    p.set_defaults(run=run_stats)
    p = sub.add_parser("pairs", help="control/ and target/ folders for the trainer from two image folders")
    for name in ("--control", "--target", "--out"):
        p.add_argument(name, required=True)
    p.add_argument("--size", type=int, default=1024)
    p.add_argument("--only", default="", help="a file of subject ids to keep, the training split")
    p.set_defaults(run=run_pairs)
    p = sub.add_parser("lora-config", help="the trainer's configuration from the pre-registered plan")
    p.add_argument("--pairs", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--training-folder", default="lora")
    p.add_argument("--base", default=realism.DEFAULT_BASE, choices=sorted(realism.MODELS))
    p.add_argument("--rank", type=int, default=realism.LoraPlan().rank)
    p.add_argument("--alpha", type=int, default=realism.LoraPlan().alpha)
    p.add_argument("--lr", type=float, default=realism.LoraPlan().learning_rate)
    p.add_argument("--steps", type=int, default=realism.LoraPlan().steps)
    p.add_argument("--resolution", type=int, default=realism.LoraPlan().resolution)
    p.add_argument("--seed", type=int, default=realism.LoraPlan().seed)
    p.add_argument("--target", default=realism.LoraPlan().target, choices=realism.LORA_TARGETS)
    p.set_defaults(run=run_lora_config)
    p = sub.add_parser("measure", help="endplate angles from the exact masks at 1024 and at 256")
    p.add_argument("--masks", required=True, help="a render folder (its masks/ and label_names.json)")
    p.add_argument("--out", required=True)
    p.add_argument("--limit", type=int, default=0)
    p.set_defaults(run=run_measure)
    return top


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        args.run(args)
    except Refused as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
