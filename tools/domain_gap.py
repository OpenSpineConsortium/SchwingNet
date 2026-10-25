"""Set FleXray's synthetic DRRs beside every held real X-ray corpus: maps and separation tests.

The owner's ask of 2026-10-25 (SchwingNet #391, the FleXray audit; the thread "Compare FleXray
DRRs to real X-ray corpora"): plot FleXray's synthetic DRRs alongside the held X-ray corpora, plain
film and fluoroscopy, in t-SNE and other dimension-reduction maps, and run the statistical tests
for separation a machine-learning reviewer would expect. docs/research/drr-domain-gap/README.md is
the pre-registered design; this tool is its one job, run by grid/bench.sbatch as the bench id
flexray_drr_gap, in the job's own environment (flexray, nanodrr, scikit-learn and umap-learn over
train-gpu's torch), once the owner gives the word and the count.

    python tools/domain_gap.py run --groups data/domain_gap/groups.json --data-root <data root> \\
        --index <samples.sqlite> --weights <FleXray bundle dir> --imagenet <resnet18 file> \\
        --out <dir> [--device cuda] [--workers 4] [--wandb auto|off] [--frozen <test-persons.json>]
    python tools/domain_gap.py summary --out <dir>

Stages, each written under --out and skipped when its output is there for the same inputs: the
FleXray renders (tools/flexray_render.py, FleXray's own nanodrr path from held TotalSegmentator
CTs), the plan (which files of which groups, data/domain_gap/groups.json, chosen by person in a
salted order, frozen test persons left out), the images (each decoded, MONOCHROME1 inverted,
windowed to its 0.5-99.5 percentiles, cut to the centre square of 0.9 of its shorter side and
resized to 256, as float16), the features (three spaces: FleXray's own encoder, an ImageNet
ResNet-18 and handcrafted physics measures, each taken on the image and on its inverse, whose mean
is the inversion-invariant feature the primary analysis reads, since fluoroscopy is often shown
bone-dark and DRRs bone-bright), and the analysis (tools/domain_gap_stats.py: PCA, t-SNE, UMAP and
LDA maps with their trustworthiness; person-grouped classifier two-sample tests with cluster
bootstrap intervals and permutation p-values; MMD with person-level permutations; Frechet distance
and KID in each space's first 64 principal components; precision, recall, density and coverage;
silhouette and neighbour purity; split-half nulls as the calibration; Benjamini-Hochberg within a
space).

What leaves the grid is summary.txt, at most 80 lines of numbers and group names that the bench
report carries; results.json, the figures and the plan, which names files, stay in --out (umask 077)
and the figures and the map coordinates go to W&B where the grid's key is found. tools/ never goes
on sys.path, since tools/profile.py would shadow the standard library's profile, which torch
imports.
"""

import argparse
import fnmatch
import hashlib
import importlib.util
import io
import json
import math
import multiprocessing
import os
import re
import sqlite3
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [entry for entry in sys.path if Path(entry or ".").resolve() != ROOT / "tools"]
for folder in (ROOT / "vendor" / "beethoven-qa" / "src", ROOT / "src"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

SIDE = 256
CROP_SHARE = 0.9
WINDOW = (0.5, 99.5)
DEFAULT_FORMATS = ("png", "jpeg", "tiff", "bmp", "dicom", "jpeg2000")
PROJECTION_MODALITIES = ("CR", "DX", "RF", "XA", "DF", "RG", "PX", "OT", "SC")
SUFFIX_FORMATS = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".tif": "tiff", ".tiff": "tiff",
                  ".bmp": "bmp", ".dcm": "dicom", ".dicom": "dicom", ".jp2": "jpeg2000", ".npy": "npy"}
PLACEHOLDERS = {"", "anonymous", "anonymous^", "anonymized", "anonymised", "anon", "none", "unknown",
                "unknown_patient", "0", "00000000", "-", "na", "n/a", "null"}
WALK_LIMIT = 400_000
MAP_ROWS = 600          # rows a group gives the maps, so t-SNE stays balanced and fast
POOL_ROWS = 300         # rows a real group gives its pooled family, so no one corpus outweighs the rest
MIN_ROWS = 20           # a group with fewer decoded images is left out of everything
MIN_PERSONS = 5         # fewer persons: plotted, never tested (a grouped split needs persons)
SPLIT_PERSONS = 40      # a split-half null needs this many persons
FD_ROWS = 250           # rows a side every FD64 is taken at, so the distances compare
PERMUTATIONS_C2ST = 100
PERMUTATIONS_MMD = 1000
BOOTSTRAP = 1000
SPACES = ("flexray", "imagenet", "physics")
PRIMARY_SPACE = "flexray"
FOCUS_GROUPS = ("flexray_drr", "fluxray")  # FleXray's own groups, read in most detail
THUNDER = "thunderdb://"


class StageError(Exception):
    """A stage that cannot run, with the reason a person reads in the report."""


# --- the neighbours: the pure rules, the numerics and the renderer --------------------------------

def rules():
    """schwingnet.domain_gap, the pure rules under beethoven-qa's gate."""
    from schwingnet import domain_gap

    return domain_gap


def tool(name):
    """A neighbouring tool by path, since tools/ is never on sys.path."""
    spec = importlib.util.spec_from_file_location(f"{name}_tool", ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data):
    """Write a JSON file whole: to a neighbour first, then renamed, so a cut job leaves none half."""
    path = Path(path)
    part = path.with_name(path.name + ".part")
    part.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(part, path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def log(text):
    print(f"drr-gap {time.strftime('%H:%M:%S')} {text}", flush=True)


# --- the plan: which files of which groups ---------------------------------------------------------

def read_table(path):
    """The group table, held to schwingnet.domain_gap.GroupTable."""
    return rules().GroupTable.model_validate_json(Path(path).read_text(encoding="utf-8"))


def frozen_persons(path):
    """The frozen test persons as (source, case) pairs; none when no file is named."""
    if not path:
        return set()
    return {tuple(row["person"].split(":", 1)) for row in read_json(path) if ":" in row["person"]}


def is_frozen(group_id, person, frozen):
    """A frozen person names a source and a case; a group whose id begins with that source holds
    that person when its own person key is the case."""
    return any(group_id.startswith(source) and person == case for source, case in frozen)


def excluded(relative, words):
    """True when a word of the path begins with an excluded word (masks, labels, crops and the
    like), so a mask beside its film is never taken for a film."""
    tokens = [t for t in re.split(r"[^a-z0-9]+", relative.lower()) if t]
    return any(t.startswith(w) for t in tokens for w in words)


def matches(relative, globs):
    return not globs or any(fnmatch.fnmatch(relative, g) for g in globs)


def index_rows(index, sources):
    """The image rows of the sample index under the named roots. A root the index calls
    unmapped:<folder> may be named by its folder alone, so both spellings are asked for."""
    names = set(sources) | {f"unmapped:{s}" for s in sources if ":" not in s}
    marks = ",".join("?" * len(names))
    query = ("SELECT path, rel, format, CAST(width AS INTEGER), CAST(height AS INTEGER),"
             " CAST(depth AS INTEGER), modality, patient_id, study_uid FROM sample"
             f" WHERE role = 'image' AND error IS NULL AND sources IN ({marks})")
    with sqlite3.connect(f"file:{index}?mode=ro", uri=True) as connection:
        return connection.execute(query, sorted(names)).fetchall()


def keep_index_row(group, row):
    """Whether an index row is an image of the group: its format, its modality, a single plane,
    its size, its path's globs and words."""
    path, relative, form, width, height, depth, modality, _, _ = row
    formats = group.formats or DEFAULT_FORMATS
    if form not in formats or (depth or 1) > 1:
        return False
    if form == "dicom":
        allowed = group.modalities or PROJECTION_MODALITIES
        if (modality or "").upper() not in allowed:
            return False
    if group.min_side and width and height and min(width, height) < group.min_side:
        return False
    return matches(relative, group.globs) and not excluded(relative, group.exclude_words)


def index_candidates(group, index):
    """(file, relative path, patient id, study uid) of every index row the group keeps."""
    if not index or not Path(index).is_file():
        raise StageError("no sample index (samples.sqlite) to read")
    rows = [r for r in index_rows(index, group.index_sources) if keep_index_row(group, r)]
    return [(r[0], r[1], r[7] or "", r[8] or "") for r in rows]


def walk_candidates(group, data_root):
    """(file, relative path, "", "") of every image file under the group's folder."""
    base = Path(data_root) / group.folder
    if not base.is_dir():
        raise StageError(f"no folder {group.folder} under the data root")
    formats = set(group.formats or DEFAULT_FORMATS)
    found, seen = [], 0
    for folder, dirs, files in os.walk(base):
        dirs.sort()
        for name in sorted(files):
            seen += 1
            if seen > WALK_LIMIT:
                return found
            relative = os.path.relpath(os.path.join(folder, name), base)
            form = SUFFIX_FORMATS.get(Path(name).suffix.lower())
            if form in formats and matches(relative, group.globs) and not excluded(relative, group.exclude_words):
                found.append((os.path.join(folder, name), relative, "", ""))
    return found


def thunder_root(group, data_root):
    """The FluXray ThunderDB folder under the group's folder: the one holding data.mdb."""
    base = Path(data_root) / group.folder
    if not base.is_dir():
        raise StageError(f"no folder {group.folder} under the data root (flexray-data not fetched)")
    for mdb in sorted(base.rglob("data.mdb")):
        if all(fnmatch.fnmatch(str(mdb.parent.relative_to(base)), g) for g in group.globs or ("*",)):
            return mdb.parent
    raise StageError(f"no ThunderDB (data.mdb) under {group.folder}")


_THUNDER = {}


def thunder_backend(root, split):
    """FleXray's own reader of a split of a FluXray ThunderDB, opened once a process."""
    key = (str(root), split)
    if key not in _THUNDER:
        from fxr.datasets.storage import SplitThunderDBStorageBackend

        backend = None
        for grouping in ("subject", "sample"):
            try:
                backend = SplitThunderDBStorageBackend(
                    str(root), dataset_name="FluXray", modality="xray", split=split, label_key=None,
                    affine_key=None, spacing_key=None, subject_grouping=grouping, lazy_payload_refs=True)
                break
            except (KeyError, ValueError, TypeError):
                continue
        if backend is None:
            raise StageError(f"FleXray's reader could not open split {split} of the FluXray ThunderDB")
        _THUNDER[key] = (backend, {r.data_id: r for r in backend.records})
    return _THUNDER[key]


def thunder_splits(root):
    from fxr.datasets._thunderdb import open_thunderdb

    with open_thunderdb(root) as db:
        return sorted(db["_splits"].keys())


def thunder_candidates(group, data_root):
    """thunderdb://<root>|<split>|<sample> for every FluXray sample, with its subject as person."""
    root = thunder_root(group, data_root)
    found = []
    for split in thunder_splits(root):
        _, records = thunder_backend(root, split)
        for data_id, record in sorted(records.items()):
            found.append((f"{THUNDER}{root}|{split}|{data_id}", data_id, record.subject_id or "", ""))
    return found


def render_candidates(group, out):
    """The FleXray renders of the render stage, each with its CT's subject as person."""
    manifest = Path(out) / "renders" / group.id / "manifest.json"
    failed = manifest.with_name("FAILED")
    if failed.is_file():
        raise StageError(f"the render failed ({failed.read_text(encoding='ascii').strip()})")
    if not manifest.is_file():
        raise StageError("the render stage wrote no manifest")
    rows = read_json(manifest)
    rows = rows["renders"] if isinstance(rows, dict) else rows
    base = manifest.parent
    return [(str(base / r["file"]), r["file"], r["subject"], "") for r in rows]


def dicom_person_rule(group, candidates):
    """dicom:patient falls back to the study for the whole group when the patient ids say
    nothing: all placeholders, or one id on more than half the files."""
    if group.person != "dicom:patient":
        return group.person
    ids = [c[2].strip().lower() for c in candidates]
    real = [i for i in ids if i not in PLACEHOLDERS]
    if not real:
        return "dicom:study"
    commonest = max(set(real), key=real.count)
    return "dicom:study" if real.count(commonest) > len(ids) / 2 else group.person


def persons_of(group, candidates, rule):
    """(file, person) pairs; a file the rule names no person for is its own person."""
    pure = rules()
    pairs, fallback = [], 0
    for path, relative, patient, study in candidates:
        if group.source in ("render", "thunderdb"):
            person = patient
        else:
            person = pure.person_key(rule, relative, patient, study)
        if not person:
            fallback += 1
            person = "file:" + relative
        pairs.append((path, person))
    return pairs, fallback


def plan_group(group, args, salt, frozen):
    """One group's row of the plan: what was found, what was chosen and why anything was not."""
    row = {"id": group.id, "label": group.label, "family": group.family, "source": group.source,
           "licence": group.licence, "note": group.note, "chosen": [], "skipped": ""}
    try:
        candidates = candidate_rows(group, args)
    except StageError as error:
        row["skipped"] = str(error)
        return row
    except Exception as error:  # one group's broken index or reader never stops the others
        traceback.print_exc(file=sys.stderr)
        row["skipped"] = f"its files could not be listed ({type(error).__name__})"
        return row
    rule = dicom_person_rule(group, candidates)
    pairs, fallback = persons_of(group, candidates, rule)
    kept = [(f, p) for f, p in pairs if not is_frozen(group.id, p, frozen)]
    chosen = rules().choose(tuple(kept), group.cap, group.per_person, f"{salt}:{group.id}")
    row.update(found=len(candidates), persons_found=len({p for _, p in pairs}), person_rule=rule,
               person_fallback=fallback, frozen_dropped=len(pairs) - len(kept),
               chosen=[[f, f"{group.id}:{p}"] for f, p in chosen])
    if not chosen:
        row["skipped"] = "nothing found under its rules"
    return row


def candidate_rows(group, args):
    if group.source == "index":
        return index_candidates(group, args.index)
    if group.source == "walk":
        return walk_candidates(group, args.data_root)
    if group.source == "thunderdb":
        return thunder_candidates(group, args.data_root)
    return render_candidates(group, args.out)


def stage_plan(args, table):
    """plan.json: every group's chosen files, made once for the same table and frozen list."""
    path = Path(args.out) / "plan.json"
    stamp = {"table": sha256_of(args.groups), "frozen": sha256_of(args.frozen) if args.frozen else "",
             "index": str(args.index or "")}
    if path.is_file() and read_json(path).get("stamp") == stamp:
        return read_json(path)
    frozen = frozen_persons(args.frozen)
    groups = [plan_group(g, args, table.salt, frozen) for g in table.groups]
    plan = {"version": 1, "salt": table.salt, "stamp": stamp, "groups": groups}
    write_json(path, plan)
    return plan


# --- the renders -----------------------------------------------------------------------------------

def stage_render(args, table):
    """FleXray's raw DRRs for every render group, by tools/flexray_render.py."""
    for group in table.groups:
        if group.source != "render":
            continue
        out = Path(args.out) / "renders" / group.id
        ct_root = Path(args.data_root) / group.folder
        if not ct_root.is_dir():
            log(f"{group.id}: no CT folder {group.folder}; its renders are skipped")
            continue
        subjects = max(1, group.cap // group.per_person)
        log(f"{group.id}: rendering {subjects} subjects x {group.per_person} views")
        (out / "FAILED").unlink(missing_ok=True)
        try:
            tool("flexray_render").render_subjects(
                ct_root, out, subjects, group.per_person, f"{table.salt}:{group.id}", args.device,
                0.0, "vertebra")
        except Exception as error:  # the other groups are still worth the job; the reason is kept
            traceback.print_exc(file=sys.stderr)
            out.mkdir(parents=True, exist_ok=True)
            (out / "FAILED").write_text(type(error).__name__ + "\n", encoding="ascii")


# --- the images ------------------------------------------------------------------------------------

def grey_pillow(data):
    """A PNG, JPEG, TIFF or BMP as one grey channel of floats; 16-bit frames keep their depth."""
    import numpy as np
    from PIL import Image

    with Image.open(io.BytesIO(data)) as image:
        image.load()
        if image.mode in ("I;16", "I;16L", "I;16B", "I", "F", "L"):
            return np.asarray(image, dtype=np.float64)
        return np.asarray(image.convert("L"), dtype=np.float64)


def grey_dicom(path):
    """A DICOM frame as floats after its modality LUT, MONOCHROME1 turned bone-bright; a cine
    gives its middle frame."""
    import numpy as np
    import pydicom
    from pydicom.pixels import apply_modality_lut

    dataset = pydicom.dcmread(path, force=True)
    photometric = str(dataset.get("PhotometricInterpretation", ""))
    if photometric not in ("MONOCHROME1", "MONOCHROME2"):
        raise ValueError(f"photometric {photometric or 'none'}")
    frames = int(dataset.get("NumberOfFrames", 1) or 1)
    pixels = dataset.pixel_array
    if frames > 1:
        pixels = pixels[frames // 2]
    pixels = np.asarray(apply_modality_lut(pixels, dataset), dtype=np.float64)
    if photometric == "MONOCHROME1":
        pixels = pixels.max() - pixels
    return pixels


def grey_thunder(reference):
    import numpy as np

    root, split, data_id = reference[len(THUNDER):].split("|", 2)
    backend, records = thunder_backend(root, split)
    return np.asarray(backend.load(records[data_id], "image"), dtype=np.float64).squeeze()


def grey_of(reference):
    """Any file of the plan as a two-dimensional array of floats."""
    import numpy as np

    if reference.startswith(THUNDER):
        return grey_thunder(reference)
    suffix = Path(reference).suffix.lower()
    if suffix == ".npy":
        return np.asarray(np.load(reference), dtype=np.float64).squeeze()
    data = Path(reference).read_bytes()
    if suffix in (".dcm", ".dicom") or data[128:132] == b"DICM":
        return grey_dicom(reference)
    return grey_pillow(data)


def canonical(pixels):
    """The image every space reads: windowed to its 0.5-99.5 percentiles, the centre square of 0.9
    of its shorter side, resized to 256 with an area filter, in [0, 1]. Cutting a square rather than
    padding one keeps a pad's flat border, which only non-square images would carry, from telling
    the corpora apart."""
    import numpy as np
    from PIL import Image

    if pixels.ndim != 2 or min(pixels.shape) < 16 or not np.isfinite(pixels).all():
        raise ValueError(f"an image of shape {pixels.shape}")
    low, high = np.percentile(pixels, WINDOW)
    if not high > low:
        raise ValueError("a flat image")
    unit = np.clip((pixels - low) / (high - low), 0.0, 1.0).astype(np.float32)
    side = max(16, int(round(CROP_SHARE * min(unit.shape))))
    top, left = (unit.shape[0] - side) // 2, (unit.shape[1] - side) // 2
    square = unit[top:top + side, left:left + side]
    resized = Image.fromarray(square, mode="F").resize((SIDE, SIDE), Image.Resampling.BOX)
    return np.clip(np.asarray(resized, dtype=np.float32), 0.0, 1.0)


def decode_one(reference):
    """(the 256 x 256 image as float16, None) or (None, the kind of error); never the error's
    text, which can name a file."""
    import numpy as np

    try:
        return canonical(grey_of(reference)).astype(np.float16), None
    except Exception as error:  # every decoder raises its own kinds for a broken file
        return None, type(error).__name__


def stage_images(args, plan):
    """images.npy (n x 256 x 256, float16) and rows.json (group, family, person, file index) for
    every chosen file that decodes; the failures are counted by group and kind."""
    import numpy as np

    out = Path(args.out)
    rows_path, images_path = out / "rows.json", out / "images.npy"
    if rows_path.is_file() and images_path.is_file() and read_json(rows_path).get("plan") == plan_digest(plan):
        return read_json(rows_path), np.load(images_path, mmap_mode="r")
    files = [(g["id"], g["family"], f, p) for g in plan["groups"] for f, p in g["chosen"]]
    log(f"decoding {len(files)} images with {args.workers} workers")
    decoded = decode_all([f for _, _, f, _ in files], args.workers)
    keep = [i for i, (image, _) in enumerate(decoded) if image is not None]
    failures = {}
    for (group, _, _, _), (image, why) in zip(files, decoded):
        if image is None:
            failures.setdefault(group, {}).setdefault(why, 0)
            failures[group][why] += 1
    images = np.stack([decoded[i][0] for i in keep]) if keep else np.zeros((0, SIDE, SIDE), np.float16)
    np.save(images_path, images)
    rows = {"plan": plan_digest(plan), "failures": failures,
            "rows": [{"group": files[i][0], "family": files[i][1], "person": files[i][3]} for i in keep]}
    write_json(rows_path, rows)
    return rows, np.load(images_path, mmap_mode="r")


def decode_all(references, workers):
    """decode_one over every reference, in worker processes that are started fresh rather than
    forked, since the render stage may have opened CUDA in this one, which a fork must not copy."""
    if workers <= 1:
        return [decode_one(r) for r in references]
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=workers, mp_context=context) as pool:
        return list(pool.map(decode_one, references, chunksize=16))


def plan_digest(plan):
    return hashlib.sha256(json.dumps(plan["groups"], sort_keys=True).encode()).hexdigest()


# --- the feature spaces ----------------------------------------------------------------------------

class StopForward(Exception):
    """Raised by the encoder hook once the bottleneck is read, so the decoder never runs."""


def flexray_encoder(weights, device):
    """FleXray's flagship member and a function from a batch to its bottleneck features: the
    spatial mean of the input to the last InstanceNorm2d of the deepest down block. The output of
    an affine instance norm has the norm's learned shift as its spatial mean for every input, so
    pooling the block's output would give one vector for every image; its input does not."""
    import torch
    from fxr.inference import FleXraySegmenter

    segmenter = FleXraySegmenter.from_pretrained(str(weights), subfolder="members/flux0375", device=device)
    model = segmenter.model.eval()
    norms = [m for m in model.down_blocks[-1].modules() if isinstance(m, torch.nn.InstanceNorm2d)]
    if not norms:
        raise StageError("FleXray's deepest down block holds no InstanceNorm2d to read before")
    taken = {}

    def before_norm(_module, inputs):
        taken["features"] = inputs[0].mean(dim=(2, 3))
        raise StopForward

    norms[-1].register_forward_pre_hook(before_norm)

    def embed(batch):
        prepared = segmenter.preprocess(batch).to(segmenter.device)
        with torch.inference_mode():
            try:
                model(prepared)
            except StopForward:
                pass
        return taken.pop("features").float().cpu().numpy()

    return embed


def imagenet_encoder(weights, device):
    """torchvision's ResNet-18 from the held ImageNet file, its 512 pooled features."""
    import torch
    import torch.nn.functional as F
    import torchvision

    model = torchvision.models.resnet18(weights=None)
    model.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True))
    model.fc = torch.nn.Identity()
    model = model.eval().to(device)
    mean = torch.tensor([0.485, 0.456, 0.406], device=device).view(1, 3, 1, 1)
    std = torch.tensor([0.229, 0.224, 0.225], device=device).view(1, 3, 1, 1)

    def embed(batch):
        with torch.inference_mode():
            x = F.interpolate(batch.to(device), size=(224, 224), mode="bilinear", antialias=True,
                              align_corners=False).repeat(1, 3, 1, 1)
            return model((x - mean) / std).float().cpu().numpy()

    return embed


def physics_features(image):
    """Handcrafted measures of one 256 x 256 image in [0, 1], the ones a renderer gets wrong
    first: the intensity histogram (32 bins, square-rooted), the radial power spectrum's shape
    (log-spaced bands with whole-pixel edges, log10, centred) and its total, the gradient histogram (16 bins), the
    noise (a robust spread of the Laplacian at two scales and their ratio), local contrast (7 x 7
    standard deviation: mean, median, 90th percentile), the shares near black and near white,
    and the share of strong edges."""
    import numpy as np

    x = image.astype(np.float64)
    hist = np.sqrt(np.histogram(x, bins=32, range=(0.0, 1.0))[0] / x.size)
    window = np.outer(np.hanning(SIDE), np.hanning(SIDE))
    power = np.abs(np.fft.fftshift(np.fft.fft2((x - x.mean()) * window))) ** 2
    yy, xx = np.indices(power.shape) - SIDE // 2
    radius = np.hypot(yy, xx)
    edges = np.unique(np.round(np.geomspace(1.0, SIDE // 2, 33)))  # integer edges: no band is empty
    bands = np.array([power[(radius >= a) & (radius < b)].mean() for a, b in zip(edges[:-1], edges[1:])])
    spectrum = np.log10(bands + 1e-12)
    gy, gx = np.gradient(x)
    magnitude = np.hypot(gx, gy)
    ghist = np.histogram(np.clip(magnitude, 0, 0.5), bins=16, range=(0.0, 0.5))[0] / x.size
    noise = [laplacian_sigma(x), laplacian_sigma(x[::2, ::2])]
    local = local_std(x)
    extra = [spectrum.mean(), noise[0], noise[1], noise[0] / (noise[1] + 1e-9),
             local.mean(), np.median(local), np.percentile(local, 90),
             (x < 0.01).mean(), (x > 0.99).mean(), (magnitude > 0.1).mean()]
    return np.concatenate([hist, spectrum - spectrum.mean(), ghist, np.array(extra)]).astype(np.float32)


def laplacian_sigma(x):
    """The noise's spread: 1.4826 times the median absolute Laplacian, a robust sigma."""
    import numpy as np

    lap = 4 * x[1:-1, 1:-1] - x[:-2, 1:-1] - x[2:, 1:-1] - x[1:-1, :-2] - x[1:-1, 2:]
    return float(1.4826 * np.median(np.abs(lap - np.median(lap))))


def local_std(x, size=7):
    """The standard deviation of every size x size neighbourhood, by integral images."""
    import numpy as np

    def box(a):
        c = np.cumsum(np.cumsum(np.pad(a, ((1, 0), (1, 0))), 0), 1)
        return (c[size:, size:] - c[:-size, size:] - c[size:, :-size] + c[:-size, :-size]) / size ** 2

    mean, square = box(x), box(x * x)
    return np.sqrt(np.clip(square - mean ** 2, 0, None))


def physics_encoder(_weights, _device):
    import numpy as np

    def embed(batch):
        return np.stack([physics_features(b[0].cpu().numpy()) for b in batch])

    return embed


ENCODERS = {"flexray": flexray_encoder, "imagenet": imagenet_encoder, "physics": physics_encoder}


def space_weights(space, args):
    return {"flexray": args.weights, "imagenet": args.imagenet, "physics": None}[space]


def unavailable(space, args):
    """Why a space cannot run here, or None."""
    weights = space_weights(space, args)
    if space == "flexray" and not (weights and (Path(weights) / "ensemble.json").is_file()):
        return "no FleXray bundle (ensemble.json)"
    if space == "imagenet" and not (weights and Path(weights).is_file()):
        return "no ImageNet ResNet-18 file"
    return None


def stage_features(args, images, rows):
    """features/<space>.npz: for each image, the space's features of the image and of its inverse."""
    import numpy as np
    import torch

    folder = Path(args.out) / "features"
    folder.mkdir(exist_ok=True)
    done = {}
    for space in SPACES:
        path = folder / f"{space}.npz"
        why = unavailable(space, args)
        if why:
            done[space] = why
            continue
        if path.is_file() and str(np.load(path)["plan"]) == rows["plan"]:
            done[space] = None
            continue
        log(f"features: {space} over {len(images)} images")
        embed = ENCODERS[space](space_weights(space, args), args.device)
        stored, inverse = [], []
        for start in range(0, len(images), 64):
            batch = torch.from_numpy(np.asarray(images[start:start + 64], dtype=np.float32)).unsqueeze(1)
            stored.append(embed(batch))
            inverse.append(embed(1.0 - batch))
        np.savez(path, stored=np.concatenate(stored), inverse=np.concatenate(inverse), plan=rows["plan"])
        done[space] = None
    return done


# --- the analysis ----------------------------------------------------------------------------------

def stats():
    return tool("domain_gap_stats")


class Frame:
    """One space's features with their rows: the groups, families and persons the tests read."""

    def __init__(self, x, rows, plan):
        import numpy as np

        self.x = x
        self.group = np.array([r["group"] for r in rows])
        self.family = np.array([r["family"] for r in rows])
        self.person = np.array([r["person"] for r in rows])
        self.labels = {g["id"]: g["label"] for g in plan["groups"]}
        self.order = [g["id"] for g in plan["groups"] if (self.group == g["id"]).sum() >= MIN_ROWS]

    def rows_of(self, group):
        import numpy as np

        return np.flatnonzero(self.group == group)

    def persons(self, group):
        return len(set(self.person[self.rows_of(group)]))

    def testable(self, family=None):
        return [g for g in self.order if self.persons(g) >= MIN_PERSONS
                and (family is None or self.family[self.rows_of(g)[0]] == family)]

    def family_of(self, group):
        return str(self.family[self.rows_of(group)[0]])


def capped(frame, rows, limit, salt):
    """At most limit of these rows, chosen by person in the salted order (persons whole)."""
    import numpy as np

    pairs = tuple((str(i), str(frame.person[i])) for i in rows)
    per_person = max(1, int(np.ceil(limit / max(1, len(set(p for _, p in pairs))))))
    chosen = rules().choose(pairs, limit, max(per_person, 1), salt)
    return np.array(sorted(int(i) for i, _ in chosen), dtype=int)


def pooled(frame, family, salt):
    """A family's testable real groups, POOL_ROWS of each, so no one corpus outweighs the rest."""
    import numpy as np

    parts = [capped(frame, frame.rows_of(g), POOL_ROWS, f"{salt}:{g}") for g in frame.testable(family)]
    return np.concatenate(parts) if parts else np.zeros(0, dtype=int)


def contrast(frame, z64, a, b, seed, *, permute=False, prdc=False):
    """Every separation measure of rows a against rows b: the classifier two-sample tests
    (logistic and k nearest neighbours, person-grouped, with cluster bootstrap intervals and,
    when asked, a permutation p), MMD with its person-level permutation p, FD and KID in the
    first 64 components, and, when asked, precision, recall, density and coverage of a against b."""
    import numpy as np

    s = stats()
    rows = np.concatenate([a, b])
    labels = np.concatenate([np.ones(len(a), int), np.zeros(len(b), int)])
    persons = list(frame.person[rows])
    result = {"n": [len(a), len(b)], "persons": [len(set(frame.person[a])), len(set(frame.person[b]))]}
    for model in ("logistic", "knn"):
        scores = s.c2st(frame.x[rows], labels, persons, seed=seed, model=model)
        result[f"auc_{model}"] = s.auc_with_interval(scores, labels, persons, boot=BOOTSTRAP, seed=seed)
    if permute:
        result["auc_logistic"]["p"] = s.c2st_permutation_p(
            frame.x[rows], labels, persons, observed_auc=result["auc_logistic"]["auc"],
            perms=PERMUTATIONS_C2ST, seed=seed)
    result["mmd"] = s.mmd_test(z64[a], z64[b], list(frame.person[a]), list(frame.person[b]),
                               perms=PERMUTATIONS_MMD, seed=seed)
    fa, fb = equal_rows(frame, a, b, seed)
    result["fd64"] = s.frechet_distance(z64[fa], z64[fb])
    result["fd_rows"] = len(fa)
    result["kid64"] = s.kid(z64[a], z64[b], seed=seed)
    if prdc:
        result["prdc"] = s.prdc(z64[b], z64[a])
    return result


def equal_rows(frame, a, b, seed):
    """Equal shares of a and b, at most FD_ROWS each, chosen by person: the Frechet distance grows
    as the sample shrinks, so every FD64 the gap ratio sets beside another is taken at one size."""
    size = min(len(a), len(b), FD_ROWS)
    return capped(frame, a, size, f"fd:{seed}"), capped(frame, b, size, f"fd:{seed}")


def calibration(frame, z64, salt, seed):
    """The split-half nulls: each group with enough persons split in two by person; the tests
    must find nothing there, or the pipeline is leaking."""
    import numpy as np

    s = stats()
    nulls = {}
    for group in frame.order:
        if frame.persons(group) < SPLIT_PERSONS:
            continue
        rows = frame.rows_of(group)
        half = s.split_half(list(frame.person[rows]), f"{salt}:{group}")
        a, b = rows[half == 1], rows[half == 0]
        nulls[group] = contrast(frame, z64, a, b, seed)
    aucs = [v["auc_logistic"]["auc"] for v in nulls.values()]
    return {"groups": nulls, "auc_median": float(np.median(aucs)) if aucs else None,
            "auc_range": [float(min(aucs)), float(max(aucs))] if aucs else None,
            "flagged": flagged_nulls(nulls), "auc_above": [g for g, v in nulls.items() if v["auc_logistic"]["lo"] > 0.5]}


def flagged_nulls(nulls):
    """The split-half nulls whose MMD permutation test, Benjamini-Hochberg adjusted over the space's
    nulls, falls under 0.05. The permutation test is exact under a person-level null; the C2ST's
    bootstrap interval holds the trained classifiers fixed and is too narrow for a few dozen
    persons, so an interval above 0.5 is counted (auc_above) but flags nothing by itself."""
    if not nulls:
        return []
    groups = list(nulls)
    q = rules().benjamini_hochberg(tuple(float(nulls[g]["mmd"]["p"]) for g in groups))
    return [g for g, value in zip(groups, q) if value < 0.05]


def analyse_space(frame, salt, seed):
    """The whole analysis of one feature space."""
    import numpy as np

    s = stats()
    z = s.standardise(frame.x)
    z64, explained = s.pca(z, min(64, z.shape[1], len(z) - 1), seed=seed)
    result = {"dim": int(frame.x.shape[1]), "rows": int(len(frame.x)),
              "feature_spread": float(np.mean(np.std(frame.x, axis=0))),
              "pca64_explained": float(np.sum(explained))}
    if result["feature_spread"] < 1e-6:
        result["invalid"] = "every image has the same features"
        return result, None
    synthetic = [g for g in frame.testable("synthetic")]
    real = frame.testable("fluoroscopy") + frame.testable("film")
    families = {f: pooled(frame, f, salt) for f in ("fluoroscopy", "film")}
    result["vs_family"] = family_contrasts(frame, z64, synthetic, families, seed)
    result["vs_group"] = {sg: {rg: contrast(frame, z64, frame.rows_of(sg), frame.rows_of(rg), seed)
                               for rg in real} for sg in synthetic}
    result["real_real"] = {f"{a}|{b}": contrast(frame, z64, frame.rows_of(a), frame.rows_of(b), seed)
                           for i, a in enumerate(real) for b in real[i + 1:]}
    if len(families["fluoroscopy"]) and len(families["film"]):
        result["fluoroscopy_vs_film"] = contrast(frame, z64, families["fluoroscopy"], families["film"], seed)
    result["calibration"] = calibration(frame, z64, salt, seed)
    result["ratios"] = gap_ratios(frame, result, synthetic)
    result["structure"] = structure(frame, z64, real, synthetic, seed)
    result["fd_all"] = all_distances(frame, z64, seed)
    adjust(result)
    maps = map_coordinates(frame, z, salt, seed)
    result["maps"] = {k: v for k, v in maps.items() if k != "coords"}
    return result, maps


def family_contrasts(frame, z64, synthetic, families, seed):
    return {sg: {f: contrast(frame, z64, frame.rows_of(sg), rows, seed, permute=True, prdc=True)
                 for f, rows in families.items() if len(rows)} for sg in synthetic}


def family_pairs(frame, result, family):
    pairs = []
    for key, value in result["real_real"].items():
        a, b = key.split("|")
        if frame.family_of(a) == family and frame.family_of(b) == family:
            pairs.append(value)
    return pairs


def gap_ratios(frame, result, synthetic):
    """FD64 of a synthetic group against a family over the median FD64 of the family's own real
    pairs, and the pre-registered word from the AUC's lower bound against the family's median
    real-real AUC."""
    pure = rules()
    ratios = {}
    for family in ("fluoroscopy", "film"):
        pairs = family_pairs(frame, result, family)
        if not pairs:
            continue
        fds = tuple(float(p["fd64"]) for p in pairs)
        aucs = sorted(float(p["auc_logistic"]["auc"]) for p in pairs)
        median_auc = aucs[len(aucs) // 2] if len(aucs) % 2 else (aucs[len(aucs) // 2 - 1] + aucs[len(aucs) // 2]) / 2
        for sg in synthetic:
            cross = result["vs_family"].get(sg, {}).get(family)
            if not cross or not any(fds):
                continue
            ratios.setdefault(sg, {})[family] = {
                "fd_ratio": pure.gap_ratio(float(cross["fd64"]), fds),
                "real_real_auc_median": median_auc,
                "word": pure.gap_word(float(cross["auc_logistic"]["lo"]), median_auc)}
    return ratios


def structure(frame, z64, real, synthetic, seed):
    """Silhouette, neighbour purity, the share of each group's neighbours in each family, and which
    real corpus a classifier trained on the real corpora alone calls each synthetic group."""
    import numpy as np

    s = stats()
    keep = np.isin(frame.group, frame.order)
    out = {"silhouette": s.silhouette(z64[keep], frame.group[keep], seed=seed),
           "purity": s.knn_purity(z64[keep], frame.group[keep]),
           "family_share": s.neighbour_family_share(z64[keep], frame.group[keep], frame.family[keep])}
    real_rows = np.flatnonzero(np.isin(frame.group, real))
    if len(set(frame.group[real_rows])) >= 2:
        out["nearest_real"] = {sg: s.nearest_real(frame.x[real_rows], frame.group[real_rows],
                                                  list(frame.person[real_rows]), frame.x[frame.rows_of(sg)],
                                                  seed=seed) for sg in synthetic}
    return out


def adjust(result):
    """Benjamini-Hochberg over every MMD p of the space's contrasts, and over its C2ST permutation
    p-values; the split-half nulls are adjusted among themselves (flagged_nulls)."""
    pure = rules()
    for key in ("mmd", "c2st"):
        found = list(p_values(result, key))
        if not found:
            continue
        adjusted = pure.benjamini_hochberg(tuple(p for _, p in found))
        for (holder, _), q in zip(found, adjusted):
            holder["q"] = q


def p_values(result, key):
    """(the dict holding a p, the p) for every test of one kind in the space's result."""
    blocks = [result.get("vs_group", {}), result.get("vs_family", {})]
    contrasts = [c for block in blocks for inner in block.values() for c in inner.values()]
    contrasts += list(result.get("real_real", {}).values())
    if "fluoroscopy_vs_film" in result:
        contrasts.append(result["fluoroscopy_vs_film"])
    for c in contrasts:
        holder = c["mmd"] if key == "mmd" else c["auc_logistic"]
        if "p" in holder:
            yield holder, float(holder["p"])


def map_coordinates(frame, z, salt, seed):
    """PCA, t-SNE, UMAP and LDA maps of up to MAP_ROWS rows a group, with each map's
    trustworthiness against the first 50 components and each group's centre and spread."""
    import numpy as np

    s = stats()
    rows = np.concatenate([capped(frame, frame.rows_of(g), MAP_ROWS, f"{salt}:map:{g}") for g in frame.order])
    z50, _ = s.pca(z[rows], min(50, z.shape[1], len(rows) - 1), seed=seed)
    maps = s.reductions(z50, seed=seed, groups=frame.group[rows])
    out = {"coords": {"rows": rows, **maps}, "trust": {}, "centres": {}}
    for name, xy in maps.items():
        if not hasattr(xy, "shape"):
            out["trust"][name] = None
            continue
        out["trust"][name] = float(s.trust(z50, xy, seed=seed)) if name != "lda" else None
        out["centres"][name] = {g: centre(xy[frame.group[rows] == g]) for g in frame.order}
    return out


def centre(xy):
    import numpy as np

    return [round(float(v), 2) for v in (*np.mean(xy, axis=0), *np.std(xy, axis=0))]


def stage_analysis(args, plan, rows):
    """results.json and the figures, every available space in turn."""
    import numpy as np

    results = {"plan": rows["plan"], "spaces": {}, "groups": group_rows(plan, rows)}
    all_maps = {}
    for space in SPACES:
        path = Path(args.out) / "features" / f"{space}.npz"
        if not path.is_file():
            results["spaces"][space] = {"invalid": unavailable(space, args) or "no features"}
            continue
        data = np.load(path)
        stored, inverse = data["stored"], data["inverse"]
        for reading, x in (("invariant", (stored + inverse) / 2.0), ("as_stored", stored)):
            if reading == "as_stored" and space != PRIMARY_SPACE:
                continue
            log(f"analysis: {space} ({reading})")
            frame = Frame(x, rows["rows"], plan)
            result, maps = analyse_space(frame, plan["salt"], seed=0)
            key = space if reading == "invariant" else f"{space}_as_stored"
            results["spaces"][key] = result
            if maps:
                all_maps[key] = (frame, maps)
    write_json(Path(args.out) / "results.json", results)
    tool_figures = Path(args.out) / "figures"
    tool_figures.mkdir(exist_ok=True)
    figures(all_maps, results, tool_figures)
    return results, all_maps


def group_rows(plan, rows):
    """Each group's counts: found, chosen, decoded, persons, and why anything was left out."""
    decoded = {}
    for r in rows["rows"]:
        decoded.setdefault(r["group"], set()).add(r["person"])
    counts = {}
    for r in rows["rows"]:
        counts[r["group"]] = counts.get(r["group"], 0) + 1
    return [{"id": g["id"], "label": g["label"], "family": g["family"], "found": g.get("found", 0),
             "chosen": len(g["chosen"]), "decoded": counts.get(g["id"], 0),
             "persons": len(decoded.get(g["id"], ())), "person_rule": g.get("person_rule", ""),
             "person_fallback": g.get("person_fallback", 0), "frozen_dropped": g.get("frozen_dropped", 0),
             "failures": rows["failures"].get(g["id"], {}), "skipped": g["skipped"]} for g in plan["groups"]]


# --- the figures -----------------------------------------------------------------------------------

# The reference palette's first three categorical slots, the only ones that stay apart for every
# pair in a scatter (the dataviz skill's palette): a family is a colour and a marker; a group is a
# panel of its own in the small multiples, never a ninth colour.
FAMILY_STYLE = {"synthetic": ("#eb6834", "^"), "fluoroscopy": ("#2a78d6", "s"), "film": ("#1baf7a", "o")}
GREY = "#c9c8c2"
INK, MUTED = "#0b0b0b", "#52514e"


def figures(all_maps, results, folder):
    """Every figure as a PNG: per space, the family maps, the group small multiples, the AUC
    heatmap and the FD64 distance matrix; across spaces, the calibration."""
    import matplotlib

    matplotlib.use("Agg")
    for key, (frame, maps) in all_maps.items():
        family_maps(frame, maps, folder / f"maps-{key}.png", key)
        group_panels(frame, maps, folder / f"groups-{key}.png", key)
        auc_heatmap(frame, results["spaces"][key], folder / f"auc-{key}.png", key)
        distance_matrix(frame, results["spaces"][key], folder / f"fd64-{key}.png", key)
    calibration_figure(results, folder / "calibration.png")


def styled_axes(ax, title):
    ax.set_title(title, color=INK, fontsize=10, loc="left")
    ax.set_xticks([])
    ax.set_yticks([])
    for side in ax.spines.values():
        side.set_color(GREY)


def family_maps(frame, maps, path, key):
    import matplotlib.pyplot as plt

    coords = maps["coords"]
    rows = coords["rows"]
    names = [n for n in ("pca", "tsne", "umap", "lda") if hasattr(coords.get(n), "shape")]
    fig, axes = plt.subplots(1, len(names), figsize=(4.2 * len(names), 4.4), squeeze=False)
    for ax, name in zip(axes[0], names):
        xy = coords[name]
        for family, (colour, marker) in FAMILY_STYLE.items():
            mask = frame.family[rows] == family
            ax.scatter(xy[mask, 0], xy[mask, 1], s=9, c=colour, marker=marker, linewidths=0, alpha=0.6,
                       label=family)
        trust = maps["trust"].get(name)
        styled_axes(ax, f"{name.upper()}" + (f"  trust {trust:.2f}" if trust else "  (supervised)" if name == "lda" else ""))
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", ncol=3, fontsize=9, frameon=False, markerscale=1.8)
    fig.suptitle(f"Synthetic DRRs and real X-ray corpora, {key} features", color=INK, fontsize=11, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def group_panels(frame, maps, path, key, method="tsne"):
    import matplotlib.pyplot as plt

    coords = maps["coords"]
    method = method if hasattr(coords.get(method), "shape") else "pca"
    xy, rows = coords[method], coords["rows"]
    columns = 4
    lines = max(1, math.ceil(len(frame.order) / columns))
    fig, axes = plt.subplots(lines, columns, figsize=(3.2 * columns, 3.0 * lines), squeeze=False)
    for ax in axes.flat:
        ax.axis("off")
    for ax, group in zip(axes.flat, frame.order):
        ax.axis("on")
        mask = frame.group[rows] == group
        colour, marker = FAMILY_STYLE[frame.family_of(group)]
        ax.scatter(xy[~mask, 0], xy[~mask, 1], s=4, c=GREY, linewidths=0, alpha=0.5)
        ax.scatter(xy[mask, 0], xy[mask, 1], s=8, c=colour, marker=marker, linewidths=0, alpha=0.8)
        styled_axes(ax, f"{frame.labels[group]}  ({frame.family_of(group)})")
    fig.suptitle(f"Each corpus against all the others, {method.upper()} of {key} features", color=INK,
                 fontsize=11, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def auc_heatmap(frame, result, path, key):
    """Rows: the synthetic groups; columns: each real group, then the pooled families. A cell is
    the person-grouped logistic two-sample AUC, 0.5 where a classifier cannot tell them apart."""
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.colors import LinearSegmentedColormap

    synthetic = list(result.get("vs_group", {}))
    if not synthetic:
        return
    real = list(result["vs_group"][synthetic[0]])
    columns = real + ["fluoroscopy", "film"]
    grid = np.full((len(synthetic), len(columns)), np.nan)
    for i, sg in enumerate(synthetic):
        for j, column in enumerate(columns):
            cell = result["vs_group"][sg].get(column) or result.get("vs_family", {}).get(sg, {}).get(column)
            if cell:
                grid[i, j] = cell["auc_logistic"]["auc"]
    ramp = LinearSegmentedColormap.from_list("blue", ["#cde2fb", "#6da7ec", "#2a78d6", "#184f95", "#0d366b"])
    fig, ax = plt.subplots(figsize=(1.0 + 0.75 * len(columns), 1.2 + 0.5 * len(synthetic)))
    ax.imshow(grid, cmap=ramp, vmin=0.5, vmax=1.0, aspect="auto")
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            if not np.isnan(grid[i, j]):
                ax.text(j, i, f"{grid[i, j]:.2f}", ha="center", va="center", fontsize=8,
                        color="#ffffff" if grid[i, j] > 0.8 else INK)
    ax.set_xticks(range(len(columns)), [frame.labels.get(c, f"pooled {c}") for c in columns], rotation=45,
                  ha="right", fontsize=8, color=MUTED)
    ax.set_yticks(range(len(synthetic)), [frame.labels[s] for s in synthetic], fontsize=8, color=MUTED)
    ax.set_title(f"Two-sample AUC, synthetic against real, {key} (0.5 = indistinguishable)", fontsize=10,
                 color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def distance_matrix(frame, result, path, key):
    """FD64 between every pair of groups the space tested, ordered by average-linkage clustering."""
    import matplotlib.pyplot as plt
    import numpy as np

    groups, fd = fd_table(result)
    if len(groups) < 3:
        return
    from scipy.cluster.hierarchy import leaves_list, linkage
    from scipy.spatial.distance import squareform

    order = leaves_list(linkage(squareform(fd, checks=False), method="average"))
    fd = fd[np.ix_(order, order)]
    names = [frame.labels.get(groups[i], groups[i]) for i in order]
    side = max(5.0, 2.5 + 0.45 * len(names))
    fig, ax = plt.subplots(figsize=(side + 1.0, side))
    shown = ax.imshow(np.log10(fd + 1.0), cmap="Blues", aspect="auto")
    bar = fig.colorbar(shown, ax=ax, fraction=0.04, pad=0.02)
    bar.set_label("log10(1 + FD64), darker = farther", fontsize=8, color=MUTED)
    ax.set_xticks(range(len(names)), names, rotation=60, ha="right", fontsize=7, color=MUTED)
    ax.set_yticks(range(len(names)), names, fontsize=7, color=MUTED)
    ax.set_title(f"FD64 between corpora, {key}", fontsize=10, color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def all_distances(frame, z64, seed):
    """FD64 between every two groups the maps show, synthetic and real alike, each pair at equal
    sizes, for the distance matrix and its clustering."""
    s = stats()
    out = {}
    for i, a in enumerate(frame.order):
        for b in frame.order[i + 1:]:
            fa, fb = equal_rows(frame, frame.rows_of(a), frame.rows_of(b), seed)
            out[f"{a}|{b}"] = float(s.frechet_distance(z64[fa], z64[fb]))
    return out


def fd_table(result):
    """The groups and the symmetric FD64 matrix of every pair of the space."""
    import numpy as np

    pairs = {tuple(key.split("|")): value for key, value in result.get("fd_all", {}).items()}
    groups = sorted({g for pair in pairs for g in pair})
    index = {g: i for i, g in enumerate(groups)}
    fd = np.zeros((len(groups), len(groups)))
    for (a, b), value in pairs.items():
        fd[index[a], index[b]] = fd[index[b], index[a]] = max(0.0, float(value))
    return groups, fd


def calibration_figure(results, path):
    """Each split-half null's AUC with its interval, by space: every interval should hold 0.5."""
    import matplotlib.pyplot as plt

    spaces = [k for k, v in results["spaces"].items() if v.get("calibration", {}).get("groups")]
    if not spaces:
        return
    fig, axes = plt.subplots(1, len(spaces), figsize=(4.0 * len(spaces), 3.6), squeeze=False)
    for ax, key in zip(axes[0], spaces):
        nulls = results["spaces"][key]["calibration"]["groups"]
        for i, (group, value) in enumerate(sorted(nulls.items())):
            auc = value["auc_logistic"]
            ax.plot([auc["lo"], auc["hi"]], [i, i], color="#2a78d6", linewidth=2)
            ax.plot([auc["auc"]], [i], marker="o", color="#2a78d6", markersize=5)
        ax.axvline(0.5, color=MUTED, linewidth=1, linestyle=":")
        ax.set_yticks(range(len(nulls)), sorted(nulls), fontsize=7, color=MUTED)
        ax.set_xlim(0.3, 0.8)
        ax.set_title(f"Split-half nulls, {key}", fontsize=10, color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# --- W&B -------------------------------------------------------------------------------------------

def wandb_key_found():
    """Whether W&B can find a key here, by name only: the environment, ~/.netrc's api.wandb.ai
    entry or the grid's ~/.wandb/token.env. The key itself is never read into this process's output."""
    if os.environ.get("WANDB_API_KEY"):
        return True
    netrc = Path.home() / ".netrc"
    if netrc.is_file() and "api.wandb.ai" in netrc.read_text(encoding="utf-8", errors="replace"):
        return True
    token = Path.home() / ".wandb" / "token.env"
    if token.is_file():
        for line in token.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("WANDB_API_KEY="):
                os.environ["WANDB_API_KEY"] = line.split("=", 1)[1].strip()
                return True
    return False


def wandb_push(args, results, all_maps):
    """The figures and the map coordinates to W&B, online where the node reaches it, else offline
    under --out/wandb; the answer is a short line for the summary, never the key."""
    if args.wandb == "off":
        return "off"
    if not wandb_key_found():
        return "no key found; figures only on the grid"
    try:
        import wandb

        os.environ.setdefault("WANDB_PROJECT", "SchwingNet")
        run = start_wandb(wandb, args)
        for png in sorted((Path(args.out) / "figures").glob("*.png")):
            run.log({f"figures/{png.stem}": wandb.Image(str(png))})
        for key, (frame, maps) in all_maps.items():
            run.log({f"maps/{key}": wandb.Table(columns=map_columns(maps), data=map_table(frame, maps))})
        run.summary.update(flat_summary(results))
        url = getattr(run, "url", None) or "offline"
        run.finish()
        return f"{'online' if url != 'offline' else 'offline under the run folder'} {url}"
    except Exception as error:  # W&B raises many kinds; a failed push never fails the study
        return f"not pushed ({type(error).__name__})"


def start_wandb(wandb, args):
    name = f"drr-gap-{os.environ.get('SLURM_JOB_ID', 'local')}"
    common = dict(project=os.environ["WANDB_PROJECT"], group="drr-gap", name=name, dir=str(args.out),
                  job_type="drr-gap")
    try:
        return wandb.init(mode="online", settings=wandb.Settings(init_timeout=60), **common)
    except Exception:  # the node has no route out: log offline beside the run
        return wandb.init(mode="offline", **common)


def map_columns(maps):
    names = [n for n in ("pca", "tsne", "umap", "lda") if hasattr(maps["coords"].get(n), "shape")]
    return ["group", "family"] + [f"{n}_{axis}" for n in names for axis in ("x", "y")]


def map_table(frame, maps):
    coords = maps["coords"]
    names = [n for n in ("pca", "tsne", "umap", "lda") if hasattr(coords.get(n), "shape")]
    table = []
    for k, i in enumerate(coords["rows"]):
        line = [frame.labels[frame.group[i]], str(frame.family[i])]
        for n in names:
            line += [float(coords[n][k, 0]), float(coords[n][k, 1])]
        table.append(line)
    return table


def flat_summary(results):
    flat = {}
    for key, space in results["spaces"].items():
        for sg, inner in space.get("vs_family", {}).items():
            for family, c in inner.items():
                flat[f"{key}/{sg}/{family}/auc"] = c["auc_logistic"]["auc"]
                flat[f"{key}/{sg}/{family}/fd64"] = c["fd64"]
    return flat


# --- the summary: what the bench report carries off the grid --------------------------------------

def fmt(value, digits=2):
    return "na" if value is None or (isinstance(value, float) and math.isnan(value)) else f"{value:.{digits}f}"


def auc_text(auc):
    text = f"{fmt(auc['auc'])} [{fmt(auc['lo'])}, {fmt(auc['hi'])}]"
    if "p" in auc:
        text += f" p {fmt(auc['p'], 3)}"
    return text


def summary_lines(results, wandb_line):
    """At most 80 short lines, each made safe for the grid's redaction, of what the study found: the
    groups, then the primary space in full, FleXray's space as stored for FleXray's own groups, and
    the other spaces' family contrasts, so the most read numbers come first if a line is lost."""
    lines = [f"drr gap: {sum(g['decoded'] for g in results['groups'])} images,"
             f" {sum(1 for g in results['groups'] if g['decoded'] >= MIN_ROWS)} groups, W&B {wandb_line}"]
    lines += group_summary(results["groups"])
    for key, space in results["spaces"].items():
        lines += space_summary(key, space, detail_of(key))
    return [rules().safe_line(line) for line in lines][:80]


def detail_of(key):
    """full for the primary space, focus for its as-stored reading, brief for the others."""
    if key == PRIMARY_SPACE:
        return "full"
    return "focus" if key.startswith(PRIMARY_SPACE) else "brief"


def group_summary(groups):
    lines = []
    for g in groups:
        if g["skipped"] and not g["decoded"]:
            lines.append(f"group {g['id']} {g['family']} skipped, {g['skipped'][:90]}")
            continue
        flag = " persons by file" if g["person_fallback"] and g["person_fallback"] >= g["chosen"] else ""
        fails = sum(g["failures"].values())
        lines.append(f"group {g['id']} {g['family']} found {g['found']} chosen {g['chosen']} decoded {g['decoded']}"
                     f" persons {g['persons']}{flag}" + (f" undecoded {fails}" if fails else ""))
    return lines


def space_summary(key, space, detail):
    if space.get("invalid"):
        return [f"space {key} not run, {space['invalid']}"]
    lines = [f"space {key} dim {space['dim']} rows {space['rows']} spread {fmt(space['feature_spread'], 3)}"
             f" pca64 {fmt(space['pca64_explained'])}"]
    lines += calibration_summary(space)
    for sg, inner in space.get("vs_family", {}).items():
        if detail == "focus" and sg not in FOCUS_GROUPS:
            continue
        lines += [family_line(space, sg, family, c) for family, c in inner.items()]
    if detail == "focus":
        return lines
    lines += real_summary(space, detail)
    if detail == "full":
        lines += group_auc_summary(space)
        lines += nearest_summary(space)
        lines += centre_summary(space)
    return lines


def calibration_summary(space):
    cal = space.get("calibration", {})
    if cal.get("auc_median") is None:
        return []
    return [f" calibration split-half auc median {fmt(cal['auc_median'])} range"
            f" {fmt(cal['auc_range'][0])} to {fmt(cal['auc_range'][1])} over {len(cal['groups'])},"
            f" mmd flagged {len(cal['flagged'])}" + (f" ({' '.join(cal['flagged'])})" if cal["flagged"] else "")
            + f", auc interval above half {len(cal.get('auc_above', []))}"]


def family_line(space, sg, family, c):
    ratio = space.get("ratios", {}).get(sg, {}).get(family, {})
    prdc = c.get("prdc", {})
    return (f" {sg} vs {family} auc {auc_text(c['auc_logistic'])} knn {fmt(c['auc_knn']['auc'])}"
            f" fd64 {fmt(c['fd64'], 1)} ratio {fmt(ratio.get('fd_ratio'))} mmd p {fmt(c['mmd']['p'], 3)}"
            f" prdc {' '.join(fmt(prdc.get(k)) for k in ('precision', 'recall', 'density', 'coverage'))}"
            f" {ratio.get('word', '')}").rstrip()


def real_summary(space, detail):
    aucs = sorted(c["auc_logistic"]["auc"] for c in space.get("real_real", {}).values())
    lines = []
    if aucs:
        lines.append(f" real-real auc median {fmt(aucs[len(aucs) // 2])} min {fmt(aucs[0])}"
                     f" max {fmt(aucs[-1])} over {len(aucs)} pairs")
    if "fluoroscopy_vs_film" in space:
        lines.append(f" fluoroscopy vs film auc {auc_text(space['fluoroscopy_vs_film']['auc_logistic'])}")
    sil = space.get("structure", {}).get("silhouette", {})
    if sil and detail == "full":
        lines.append(f" silhouette {fmt(sil.get('overall'))}")
    return lines


def group_auc_summary(space):
    """For FleXray's own groups, the AUC and FD64 against each real group, the heatmap's rows."""
    lines = []
    for sg in FOCUS_GROUPS:
        inner = space.get("vs_group", {}).get(sg, {})
        parts = [f"{rg} {fmt(c['auc_logistic']['auc'])}/{fmt(c['fd64'], 0)}" for rg, c in inner.items()]
        lines += wrapped(f" {sg} vs groups auc/fd64", parts)
    return lines


def nearest_summary(space):
    lines = []
    for sg, shares in space.get("structure", {}).get("nearest_real", {}).items():
        top = sorted(shares.items(), key=lambda kv: -kv[1])[:3]
        lines.append(f" nearest real for {sg}: " + ", ".join(f"{g} {100 * v:.0f} pct" for g, v in top))
    return lines


def centre_summary(space, method="tsne"):
    """Each group's centre and spread on the t-SNE map, so a figure of ellipses can be drawn
    from the report alone."""
    centres = space.get("maps", {}).get("centres", {}).get(method, {})
    return wrapped(f" {method} centres", [f"{g} {' '.join(fmt(v, 1) for v in c)}" for g, c in centres.items()])


def wrapped(head, parts, width=180):
    """head and parts joined by "; " into lines of at most width characters, head on each."""
    lines, line = [], head
    for part in parts:
        if len(line) + len(part) + 2 > width and line != head:
            lines.append(line)
            line = head
        line += f"; {part}"
    return lines + [line] if parts else []


# --- the command line ------------------------------------------------------------------------------

def run(args):
    os.umask(0o077)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    table = read_table(args.groups)
    stage_render(args, table)
    plan = stage_plan(args, table)
    rows, images = stage_images(args, plan)
    if not rows["rows"]:
        raise StageError("no image decoded")
    stage_features(args, images, rows)
    results, all_maps = stage_analysis(args, plan, rows)
    line = wandb_push(args, results, all_maps)
    lines = summary_lines(results, line)
    (out / "summary.txt").write_text("\n".join(lines) + "\n", encoding="ascii")
    print("\n".join(lines))
    return 0


def summary(args):
    print((Path(args.out) / "summary.txt").read_text(encoding="ascii"), end="")
    return 0


def parse(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    go = sub.add_parser("run", help="every stage, each skipped when done")
    go.add_argument("--groups", default=str(ROOT / "data" / "domain_gap" / "groups.json"))
    go.add_argument("--data-root", required=True)
    go.add_argument("--index", default="")
    go.add_argument("--weights", default="")
    go.add_argument("--imagenet", default="")
    go.add_argument("--out", required=True)
    go.add_argument("--device", default="cuda")
    go.add_argument("--workers", type=int, default=4)
    go.add_argument("--wandb", choices=("auto", "off"), default="auto")
    go.add_argument("--frozen", default="")
    show = sub.add_parser("summary", help="print the summary of a finished run")
    show.add_argument("--out", required=True)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse(argv)
    try:
        return run(args) if args.command == "run" else summary(args)
    except StageError as error:
        print(f"drr-gap FAILED: {error}", flush=True)
        return 2


if __name__ == "__main__":
    sys.exit(main())
