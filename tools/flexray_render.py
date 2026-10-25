"""FleXray's raw DRRs from held TotalSegmentator CTs, made the way fxr-render makes them, for the
DRR domain-gap study.

The owner asked on 2026-10-25 (the thread "Compare FleXray DRRs to real X-ray corpora") for
FleXray's synthetic DRRs to be set beside every held real X-ray corpus; tools/domain_gap.py runs
the study and calls render_subjects here for its render groups. The tool calls FleXray's own
nanodrr path, fxr.drr, with the camera of the MOOSE profile of fxr's configs/training/base.yml, so
a render is what FleXray's CT branch fed its network, apart from the departures listed below.

    python tools/flexray_render.py --ct-root <dir> --out <dir> --subjects 250 --per-subject 4 \\
        --salt <s> [--device cuda] [--attenuation 0.0] [--isocenter vertebra|any] [--detector 256]

A subject is a folder under --ct-root, one to four levels down, that holds ct.nii.gz and
segmentations/ in TotalSegmentator v2.0.1's layout (segmentations/vertebrae_*.nii.gz,
sacrum.nii.gz). Subjects are taken in the order of the hash of the salt and the subject's path
relative to --ct-root, and one with fewer than three non-empty vertebra masks is passed over with
its reason, until --subjects are kept. Each CT is read as float32 HU in its own voxel order with
its affine, as fxr's NIfTI packer reads it (fxr/datasets/nifti.py), held to [-1000, 2000] HU, and
every voxel at -900 HU or below is set to -1000, fxr's air clamp (air_clamp_hu in base.yml).

Each render r seeds Python's, numpy's and torch's generators from the hash of the salt and
"<subject>:<r>", so a render is the same whatever else the run did, and draws in the order fxr's
SegmentationDRRRuntime.render draws: the isocenter (fxr.drr.sample_isocenters_from_centroids,
without replacement, as MOOSE's random_label scheme), the detector spacing delx from 1.25 to 2.25
mm with dely equal to it, the source-to-detector distance from 1150 to 1250 mm, the pose
(fxr.drr.PoseSampler("random") at MOOSE's ranges: alpha -180 to 180, beta -30 to 30 and gamma 0
degrees; x -100 to 100, y 500 to 900 and z -100 to 100 mm, the sampler writing the sorted distance
back), orthographic projection with probability 0.1, then the attenuation gate. The volume is cut
to 256 slices of its last axis around the isocenter, the affine shifted to match, since FleXray
trained on 512 x 512 x 256 axial crops taken along that axis (fxr/datasets/ct_crops.py); a shorter
volume is rendered whole, since the air fxr pads it with adds nothing to a ray. fxr.drr.render_drr
renders the cut with 500 samples a ray in the AP orientation, and fxr's own scale_rendered_images
scales the view to [0, 1], the scaling training applies before augmentation.

It writes <out>/images/<subject>__r<NN>.npy (float16, detector x detector), <out>/manifest.json
(a list, one row per render: file, subject, r, alpha, beta, gamma, x, y, z, sdd, delx,
orthographic, isocenter_mm, slices, seconds and attenuated) and <out>/RENDER.json (the counts, the
subjects passed over with their reasons, the versions of flexray, nanodrr, torch and nibabel, the
arguments and the time spent). A render whose file is on disk with its manifest row is not made
again, so a job cut short carries on where it stopped; the manifest lists the renders of the run
it was written by.

Where it departs from fxr-render (fxr/launch/render.py), and why:
- No ThunderDB pack: the CTs are read straight from the TotalSegmentator folder, since packing
  them first would copy the corpus on the grid for nothing; the reading and the air clamp match
  fxr's packer and CT loader.
- Attenuation is off by default: fxr-render applies MOOSE's per-label attenuation (probability
  0.5, multipliers from 0.1 to 4 on a lognormal of mode 1) as training augmentation, while the
  study compares the physical render with real images, so --attenuation 0 renders the CT as it
  is; a probability above 0 turns the same augmentation on over the vertebra labels.
- The isocenter is on the spine: fxr-render draws it from the centroid of every supervised label,
  which puts organs and limbs at the centre of many views, while every real group of the study is
  spine imaging, so the default draws it from the centroids of the vertebrae and the sacrum;
  --isocenter any draws it from every non-empty mask under segmentations/, as fxr-render does, at
  the price of reading every mask of a subject.
- The bound of 2000 HU above is the study's: fxr bounds HU only from below, and a metal implant
  above it would take the whole of a min-max scaled view.
- The sampling is done here rather than through SegmentationDRRRuntime, which needs a training
  config with a protocol and renders every protocol label; the constants below are the MOOSE
  profile's and the calls are the runtime's own.

numpy, torch, nibabel and fxr are imported only when a render is asked for, so the orchestrator
and the tests can load this file where they are missing. tools/ never goes on sys.path, since
tools/profile.py would shadow the standard library's profile, which torch imports.
"""

import argparse
import functools
import hashlib
import importlib.metadata
import json
import os
import random
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [entry for entry in sys.path if Path(entry or ".").resolve() != ROOT / "tools"]
for folder in (ROOT / "vendor" / "beethoven-qa" / "src", ROOT / "src"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

CT_NAME = "ct.nii.gz"
MASK_FOLDER = "segmentations"
VERTEBRA_GLOB = "vertebrae_*.nii.gz"
SACRUM_NAME = "sacrum.nii.gz"
SEARCH_DEPTH = 4
MIN_VERTEBRAE = 3
MAX_VIEWS = 100          # r is written with two digits
HU_LOW, HU_HIGH = -1000.0, 2000.0
AIR_CLAMP_HU = -900.0
SLAB = 256               # FleXray's crops are 512 x 512 x 256
DETECTOR = 256

# The MOOSE profile of fxr's configs/training/base.yml (drr_model.default merged with
# drr_model.datasets.MOOSE), which fxr-render would use for this corpus.
MOOSE_POSE_RANGES = {
    "rot_range": {"alpha": [-180.0, 180.0], "beta": [-30.0, 30.0], "gamma": [0.0, 0.0]},
    "xyz_range": {"x": [-100.0, 100.0], "y": [500.0, 900.0], "z": [-100.0, 100.0]},
}
SDD_RANGE = (1150.0, 1250.0)
DELX_RANGE = (1.25, 2.25)
ORTHOGRAPHIC_SHARE = 0.1
ORIENTATION = "AP"
RAY_SAMPLES = 500
ATTENUATION_RANGE = (0.1, 4.0)
ATTENUATION_DISTRIBUTION = {"type": "lognormal", "mode": 1.0, "sigma": 1.0}
ISOCENTER_MODES = ("vertebra", "any")


class SkipSubject(Exception):
    """A subject the renders pass over, with the reason RENDER.json records."""


# --- names and order -------------------------------------------------------------------------------

@functools.lru_cache(maxsize=1)
def pure_rank_key():
    """schwingnet.domain_gap.rank_key, the study's one rank, or None where it does not import."""
    try:
        from schwingnet.domain_gap import rank_key as pure
    except ImportError:
        return None
    return pure


def rank_key(salt, text):
    """A subject's or a render's place: the sha256 of "salt:text", as the pure module ranks."""
    pure = pure_rank_key()
    if pure is not None:
        return pure(salt, text)
    # Fallback only for an environment where schwingnet.domain_gap or its contract libraries do
    # not import: the same sha256 of "salt:text" that schwingnet.domain_gap.rank_key returns.
    return hashlib.sha256(f"{salt}:{text}".encode("utf-8", "surrogatepass")).hexdigest()


def find_subjects(ct_root):
    """Every folder one to SEARCH_DEPTH levels under ct_root that holds a CT and its masks, as a
    sorted list of paths relative to ct_root; a subject's own folders are not searched further."""
    root = Path(ct_root)
    found = []
    for folder, names, files in os.walk(root):
        here = Path(folder)
        depth = len(here.relative_to(root).parts)
        if depth >= 1 and CT_NAME in files and MASK_FOLDER in names:
            found.append(here.relative_to(root).as_posix())
            names[:] = []
            continue
        if depth >= SEARCH_DEPTH:
            names[:] = []
        names.sort()
    return sorted(found)


def image_stem(subject):
    """The subject's path as a file-name stem: anything outside letters, digits, dot, dash and
    underscore becomes a dash, so a nested subject still names one file."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", subject)


def render_file(subject, r):
    """The render's file, relative to the output folder, as the manifest names it."""
    return f"images/{image_stem(subject)}__r{r:02d}.npy"


# --- reading a subject -----------------------------------------------------------------------------

def read_nifti(path):
    """A NIfTI volume as float32 in its own voxel order and its float64 affine; trailing axes of
    length one are dropped, as fxr's packer drops them."""
    import nibabel
    import numpy as np

    image = nibabel.load(str(path))
    array = np.asarray(image.dataobj, dtype=np.float32)
    while array.ndim > 3 and array.shape[-1] == 1:
        array = array[..., 0]
    if array.ndim != 3:
        raise SkipSubject(f"{Path(path).name} is not a 3-D volume")
    return np.ascontiguousarray(array), np.asarray(image.affine, dtype=np.float64)


def clamp_hu(volume):
    """Hold HU to [HU_LOW, HU_HIGH] and set air-like voxels to HU_LOW, in place."""
    import numpy as np

    np.clip(volume, HU_LOW, HU_HIGH, out=volume)
    volume[volume <= AIR_CLAMP_HU] = HU_LOW
    return volume


def centroid(mask):
    """The mean voxel index (i, j, k) of a boolean mask, or None for an empty one, from its three
    axis profiles rather than a list of every voxel."""
    import numpy as np

    count = int(mask.sum(dtype=np.int64))
    if count == 0:
        return None
    centre = []
    for axis in range(3):
        others = tuple(a for a in range(3) if a != axis)
        profile = mask.sum(axis=others, dtype=np.int64)
        centre.append(float((profile * np.arange(mask.shape[axis])).sum()) / count)
    return tuple(centre)


def read_mask(path, shape):
    """A mask as booleans on the CT's grid; a mask on another grid passes the subject over."""
    import nibabel
    import numpy as np

    array = np.asarray(nibabel.load(str(path)).dataobj)
    while array.ndim > 3 and array.shape[-1] == 1:
        array = array[..., 0]
    if array.shape != shape:
        raise SkipSubject(f"{Path(path).name} is on another grid than the CT")
    return array > 0


def spine_centroids(folder, shape, label):
    """The centroids of the non-empty vertebra masks and of the sacrum, and the vertebra count.
    When label is an array, each non-empty vertebra is written into it as its own id from 1."""
    masks = folder / MASK_FOLDER
    centres, vertebrae = [], 0
    for path in sorted(masks.glob(VERTEBRA_GLOB)):
        mask = read_mask(path, shape)
        centre = centroid(mask)
        if centre is None:
            continue
        vertebrae += 1
        centres.append(centre)
        if label is not None:
            label[mask] = vertebrae
    sacrum = masks / SACRUM_NAME
    if sacrum.is_file():
        centre = centroid(read_mask(sacrum, shape))
        if centre is not None:
            centres.append(centre)
    return centres, vertebrae


def other_centroids(folder, shape):
    """The centroids of every non-empty mask that is neither a vertebra nor the sacrum."""
    masks = folder / MASK_FOLDER
    spine = {SACRUM_NAME} | {p.name for p in masks.glob(VERTEBRA_GLOB)}
    centres = []
    for path in sorted(masks.glob("*.nii.gz")):
        if path.name in spine:
            continue
        centre = centroid(read_mask(path, shape))
        if centre is not None:
            centres.append(centre)
    return centres


def load_subject(folder, isocenter, with_labels):
    """One subject read for rendering: the clamped CT, its affine, the centroids its isocenters
    are drawn from and, with_labels, the dense vertebra labels the attenuation reads."""
    import numpy as np

    volume, affine = read_nifti(folder / CT_NAME)
    label = np.zeros(volume.shape, dtype=np.uint8) if with_labels else None
    centres, vertebrae = spine_centroids(folder, volume.shape, label)
    if vertebrae < MIN_VERTEBRAE:
        raise SkipSubject(f"{vertebrae} non-empty vertebra masks, fewer than {MIN_VERTEBRAE}")
    if isocenter == "any":
        centres = centres + other_centroids(folder, volume.shape)
    return {
        "volume": clamp_hu(volume),
        "affine": affine,
        "centroids": np.asarray(centres, dtype=np.float64),
        "label": label,
        "vertebra_ids": list(range(1, vertebrae + 1)),
    }


# --- one render ------------------------------------------------------------------------------------

def slab_window(length, centre, slab):
    """The [lo, hi) run of slab slices of an axis of this length that holds the centre slice,
    shifted inwards at an edge; the whole axis when it is shorter than the slab."""
    lo = min(max(int(round(centre)) - slab // 2, 0), max(length - slab, 0))
    return lo, min(lo + slab, length)


def crop_slab(volume, affine, isocenter_mm, slab=SLAB):
    """The volume cut to slab slices of its last axis around the isocenter, the affine shifted so
    every kept voxel keeps its world position, and the slices kept."""
    import numpy as np

    voxel = np.linalg.inv(affine) @ np.append(np.asarray(isocenter_mm, dtype=np.float64), 1.0)
    lo, hi = slab_window(volume.shape[2], voxel[2], slab)
    shifted = affine.copy()
    shifted[:3, 3] = affine[:3, 3] + affine[:3, 2] * lo
    return volume[:, :, lo:hi], shifted, (lo, hi)


def seed_from(key):
    """Seed Python's, numpy's and torch's generators from a rank key's first 32 bits, the most
    numpy takes."""
    import numpy as np
    import torch

    seed = int(key[:8], 16)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def pose_sampler():
    """FleXray's random pose sampler at MOOSE's ranges, on torch's global generator."""
    from fxr.drr import PoseSampler

    return PoseSampler("random", sample_params=MOOSE_POSE_RANGES)


def sample_view(sampler, centroids, affine, attenuation):
    """One view's camera and gates, drawn in the order SegmentationDRRRuntime.render draws."""
    import torch
    from fxr.drr import sample_isocenters_from_centroids

    isocenter = sample_isocenters_from_centroids(
        torch.as_tensor(centroids), torch.as_tensor(affine), 1, replacement=False)
    delx = random.uniform(*DELX_RANGE)
    sdd = torch.tensor([random.uniform(*SDD_RANGE)], dtype=torch.float32)
    rot, xyz = sampler.sample(num_poses=1, sampled_sdd=sdd)
    orthographic = random.random() < ORTHOGRAPHIC_SHARE
    attenuated = random.random() < attenuation
    return {
        "rot": rot, "xyz": xyz, "isocenter_mm": [float(v) for v in isocenter[0].tolist()],
        "sdd": float(sdd[0]), "delx": float(delx), "orthographic": bool(orthographic),
        "attenuated": bool(attenuated),
    }


def render_request(view, detector):
    """The fxr.drr request of one view, with the intrinsics as the runtime passes them."""
    import torch
    from fxr.drr import DRRRenderRequest

    intrinsics = {"sdd": [view["sdd"]], "delx": [view["delx"]], "dely": [view["delx"]],
                  "x0": [0.0], "y0": [0.0], "height": detector, "width": detector}
    return DRRRenderRequest(
        rot=view["rot"], xyz=view["xyz"], intrinsics=intrinsics,
        isocenter=torch.tensor([view["isocenter_mm"]], dtype=torch.float32),
        orientation=ORIENTATION, n_samples=RAY_SAMPLES, orthographic=view["orthographic"])


def render_view(subject, view, detector, device):
    """One view rendered by fxr.drr.render_drr and scaled to [0, 1], as float16, with the slices
    of the cut it was rendered from."""
    import numpy as np
    import torch
    from fxr.drr import render_drr
    from fxr.models.camera.runtime import scale_rendered_images

    volume, affine, slices = crop_slab(subject["volume"], subject["affine"], view["isocenter_mm"])
    lo, hi = slices
    attenuation = {}
    label = None
    if view["attenuated"]:
        label = torch.from_numpy(np.ascontiguousarray(subject["label"][:, :, lo:hi])).to(device)
        attenuation = {"attenuation": ATTENUATION_RANGE,
                       "attenuated_label_ids": subject["vertebra_ids"],
                       "do_per_label_attenuation": True,
                       "attenuation_dist": ATTENUATION_DISTRIBUTION}
    with torch.inference_mode():
        result = render_drr(
            volume=torch.from_numpy(np.ascontiguousarray(volume))[None].to(device),
            label=label, affine=torch.as_tensor(affine, dtype=torch.float32).to(device),
            request=render_request(view, detector), **attenuation)
        image = scale_rendered_images(result.images)[0, 0].float().cpu().numpy()
    return image.astype(np.float16), [lo, hi]


def manifest_row(subject, r, view, slices, seconds):
    """The manifest's row of one render: its file, its subject and every draw it was made with."""
    alpha, beta, gamma = (float(v) for v in view["rot"][0].tolist())
    x, y, z = (float(v) for v in view["xyz"][0].tolist())
    return {"file": render_file(subject, r), "subject": subject, "r": r,
            "alpha": alpha, "beta": beta, "gamma": gamma, "x": x, "y": y, "z": z,
            "sdd": view["sdd"], "delx": view["delx"], "orthographic": view["orthographic"],
            "isocenter_mm": view["isocenter_mm"], "slices": slices,
            "seconds": round(seconds, 3), "attenuated": view["attenuated"]}


# --- files -----------------------------------------------------------------------------------------

def write_json(path, data):
    """Write a JSON file whole: to a neighbour first, then renamed, so a cut job leaves none half."""
    part = path.with_name(path.name + ".part")
    part.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(part, path)


def save_image(path, image):
    """Write a render's array whole, by the same neighbour and rename."""
    import numpy as np

    part = path.with_name(path.name + ".part")
    with open(part, "wb") as handle:
        np.save(handle, image)
    os.replace(part, path)


def read_json(path):
    """A JSON file's content, or None when it is missing or unreadable."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def render_settings(salt, attenuation, isocenter, detector):
    """What decides a render's pixels besides its subject and r; a render on disk is reused only
    by a run under the same."""
    found = versions()
    return {"salt": salt, "attenuation": float(attenuation), "isocenter": isocenter,
            "detector": int(detector), "slab": SLAB, "ray_samples": RAY_SAMPLES,
            "hu": [HU_LOW, HU_HIGH], "flexray": found["flexray"], "nanodrr": found["nanodrr"]}


def earlier_rows(out, settings):
    """The rows of the manifest an earlier run under the same settings wrote, by file; none when
    RENDER.json is missing or names other settings, since the renders on disk are then another
    run's, whatever their names."""
    record = read_json(out / "RENDER.json")
    if not isinstance(record, dict) or record.get("settings") != settings:
        return {}
    rows = read_json(out / "manifest.json")
    rows = rows.get("renders", []) if isinstance(rows, dict) else rows
    if not isinstance(rows, list):
        return {}
    return {row["file"]: row for row in rows if isinstance(row, dict) and "file" in row}


def versions():
    """The versions of the packages a render depends on, as the environment reports them."""
    found = {}
    for name in ("flexray", "nanodrr", "torch", "nibabel", "numpy"):
        try:
            found[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            found[name] = "absent"
    return found


def log(text):
    print(f"flexray-render {time.strftime('%H:%M:%S')} {text}", flush=True)


# --- the run ---------------------------------------------------------------------------------------

def check_arguments(subjects, per_subject, attenuation, isocenter, detector):
    if subjects < 1:
        raise ValueError("subjects must be at least 1")
    if not 1 <= per_subject <= MAX_VIEWS:
        raise ValueError(f"per_subject must be from 1 to {MAX_VIEWS}")
    if not 0.0 <= attenuation <= 1.0:
        raise ValueError("attenuation is a probability, from 0 to 1")
    if isocenter not in ISOCENTER_MODES:
        raise ValueError(f"isocenter must be one of {', '.join(ISOCENTER_MODES)}")
    if detector < 8:
        raise ValueError("detector must be at least 8 pixels")


def load_or_skip(state, subject):
    """The subject read for rendering, or None after recording why it is passed over."""
    started = time.perf_counter()
    try:
        return load_subject(state["root"] / subject, state["isocenter"], state["attenuation"] > 0)
    except SkipSubject as reason:
        state["skipped"].append({"subject": subject, "reason": str(reason)})
    except Exception as error:  # nibabel raises several unrelated error types, as fxr notes
        # A truncated download or a header nibabel refuses is named by its kind alone, so no
        # path reaches the record.
        state["skipped"].append({"subject": subject,
                                 "reason": f"unreadable ({type(error).__name__})"})
    finally:
        state["seconds_loading"] += time.perf_counter() - started
    return None


def render_missing(state, subject, loaded, missing):
    """The missing renders of one kept subject: each written to disk, its row into the run's."""
    for r in missing:
        seed_from(rank_key(state["salt"], f"{subject}:{r}"))
        view = sample_view(state["sampler"], loaded["centroids"], loaded["affine"],
                           state["attenuation"])
        started = time.perf_counter()
        image, slices = render_view(loaded, view, state["detector"], state["device"])
        seconds = time.perf_counter() - started
        state["seconds_rendering"] += seconds
        save_image(state["out"] / render_file(subject, r), image)
        state["rows"][render_file(subject, r)] = manifest_row(subject, r, view, slices, seconds)
        state["rendered_now"] += 1


def visit_subject(state, subject, per_subject):
    """Keep a subject whose renders are all on disk with their rows, or render what it lacks; a
    subject that cannot be read is passed over with its reason and gives no row."""
    files = [render_file(subject, r) for r in range(per_subject)]
    done = [f for f in files if f in state["earlier"] and (state["out"] / f).is_file()]
    missing = [r for r, f in enumerate(files) if f not in done]
    if missing:
        loaded = load_or_skip(state, subject)
        if loaded is None:
            return False
        render_missing(state, subject, loaded, missing)
    for f in done:
        state["rows"][f] = state["earlier"][f]
    state["reused"] += len(done)
    return True


def render_subjects(ct_root, out, subjects, per_subject, salt, device, attenuation, isocenter,
                    detector=DETECTOR):
    """Render per_subject views of each of the first `subjects` usable CTs under ct_root, in the
    salted order, into out; returns what RENDER.json records."""
    check_arguments(subjects, per_subject, attenuation, isocenter, detector)
    out = Path(out)
    (out / "images").mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    settings = render_settings(salt, attenuation, isocenter, detector)
    state = {"root": Path(ct_root), "out": out, "salt": salt, "device": device,
             "attenuation": float(attenuation), "isocenter": isocenter, "detector": detector,
             "settings": settings, "earlier": earlier_rows(out, settings), "rows": {},
             "skipped": [], "rendered_now": 0, "reused": 0, "seconds_loading": 0.0,
             "seconds_rendering": 0.0, "sampler": pose_sampler()}
    # The manifest first, holding only what this run may reuse, then RENDER.json naming this
    # run's settings, so a run cut at any point never leaves rows another run would trust.
    write_manifest(out, state["earlier"])
    found = find_subjects(ct_root)
    kept = []
    write_json(out / "RENDER.json", run_record(state, found, kept, subjects, per_subject,
                                               started, "running"))
    for subject in sorted(found, key=lambda name: rank_key(salt, name)):
        if len(kept) >= subjects:
            break
        if visit_subject(state, subject, per_subject):
            kept.append(subject)
            write_manifest(out, state["rows"])
            if len(kept) % 25 == 0:
                log(f"{len(kept)} subjects kept, {state['rendered_now']} rendered now")
    write_manifest(out, state["rows"])
    record = run_record(state, found, kept, subjects, per_subject, started, "done")
    write_json(out / "RENDER.json", record)
    log(f"{len(kept)} of {subjects} subjects kept, {len(state['skipped'])} passed over, "
        f"{state['rendered_now']} rendered now, {state['reused']} kept from before")
    return record


def write_manifest(out, rows):
    """manifest.json: the rows by file name, one a render."""
    write_json(out / "manifest.json", sorted(rows.values(), key=lambda row: row["file"]))


def run_record(state, found, kept, subjects, per_subject, started, status):
    """RENDER.json: the counts, the subjects passed over, the versions and the arguments."""
    return {
        "version": 1,
        "status": status,
        "settings": state["settings"],
        "arguments": {"ct_root": str(state["root"]), "subjects": subjects,
                      "per_subject": per_subject, "salt": state["salt"],
                      "device": str(state["device"]), "attenuation": state["attenuation"],
                      "isocenter": state["isocenter"], "detector": state["detector"]},
        "counts": {"subjects_found": len(found), "subjects_kept": len(kept),
                   "subjects_skipped": len(state["skipped"]), "renders": len(state["rows"]),
                   "rendered_now": state["rendered_now"], "reused": state["reused"]},
        "skipped": state["skipped"],
        "versions": versions(),
        "profile": {"pose_ranges": MOOSE_POSE_RANGES, "sdd": list(SDD_RANGE),
                    "delx": list(DELX_RANGE), "orthographic": ORTHOGRAPHIC_SHARE,
                    "orientation": ORIENTATION, "ray_samples": RAY_SAMPLES,
                    "hu": [HU_LOW, HU_HIGH], "air_clamp_hu": AIR_CLAMP_HU, "slab": SLAB,
                    "attenuation_range": list(ATTENUATION_RANGE),
                    "attenuation_distribution": ATTENUATION_DISTRIBUTION},
        "seconds": {"total": round(time.perf_counter() - started, 3),
                    "loading": round(state["seconds_loading"], 3),
                    "rendering": round(state["seconds_rendering"], 3)},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--ct-root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--subjects", type=int, default=250)
    parser.add_argument("--per-subject", type=int, default=4)
    parser.add_argument("--salt", required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--attenuation", type=float, default=0.0)
    parser.add_argument("--isocenter", choices=ISOCENTER_MODES, default="vertebra")
    parser.add_argument("--detector", type=int, default=DETECTOR)
    args = parser.parse_args(argv)
    record = render_subjects(args.ct_root, args.out, args.subjects, args.per_subject, args.salt,
                             args.device, args.attenuation, args.isocenter, args.detector)
    return 0 if record["counts"]["subjects_kept"] else 1


if __name__ == "__main__":
    sys.exit(main())
