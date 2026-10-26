"""Synthetic X-rays from held TotalSegmentator CTs through the render blocks, by one of two
engines, for the DRR domain-gap study's replication test of FleXray's renderer.

The owner asked on 2026-10-25 (the thread "Compare FleXray DRRs to real X-ray corpora") for
FleXray's synthetic DRRs to be set beside every held real X-ray corpus, and for FleXray's recipe
to be rendered both through this project's blocks and through FleXray's own code, so the two can
be compared: tools/domain_gap.py runs the study and calls render_subjects here for each render
group. A render is a configuration of schwingnet.render_blocks (FleXray's released MOOSE recipe
when no block is named) run by an engine:

- "blocks" calls tools/render_blocks.py, one function per named choice, FleXray's primitives
  (fxr.drr) underneath for the pose draw and the rendering;
- "flexray-runtime" calls FleXray's own functions for every step: its pack's HU window
  (CTPreprocessing), its CT loader's air clamp, its crop planner and packer (ct_crops.plan_z_crops,
  crop_z, crop_metadata, offset_affine), its crop weights (sampling.inverse_label_frequency_weights)
  and torch's WeightedRandomSampler for the draw, its label remap
  (compile_training_label_remap_by_name("all_structures_flexray_v4", "MOOSE") at the released
  model's 61 labels, TrainingLabelProjection), its SegmentationDRRRuntime built from the MOOSE
  effective profile of its base training config at one view a call, since each view draws its own
  crop, and its scale_rendered_images; it takes only the blocks FleXray's code can honour
  (schwingnet.render_blocks.engine_problems) and refuses the rest in words before rendering. It
  needs kornia, which FleXray's camera package imports for its training-time label smoothing
  (flexray's train extra); the blocks engine needs fxr.drr alone.

Both read the same CT once (nibabel), build one label volume of MOOSE's stored ids from the
TotalSegmentator masks (TOTALSEG_TO_MOOSE below; every name written is one FleXray's protocol
supervises) and write the same layout. The seed of a view comes from the salt, the subject and the
view alone, not from the engine or the group, so two render groups on one folder that differ only
by their attenuation block share every crop, isocentre and pose, and the reference engine seeds
FleXray's own generators from the same number (its draws differ where its code differs; that is
the point of the test).

    python tools/flexray_render.py --ct-root <dir> --out <dir> --subjects 250 --salt <s> \\
        [--device cuda] [--engine blocks|flexray-runtime] [--blocks KEY=VALUE]... [--subject ID]...

A subject is a folder under --ct-root, one to four levels down, that holds ct.nii.gz and
segmentations/ in TotalSegmentator v2.0.1's layout, one binary mask a structure. Without
--subject, subjects are taken in the order of rank_key("<salt>:subjects", id) until --subjects
are kept, a subject with no supervised structure or an unreadable file passed over with its
reason; with --subject the named ones alone are rendered, in that order. Each CT is read as
float32 HU in its own voxel order with its affine, as FleXray's NIfTI packer reads it.

Per view, in FleXray's order of draws: one crop by the crop sampler's weights, one isocentre, one
pose, one gate and the attenuation factors, one render, scaled to 0 to 1 and written as a 16-bit
grey PNG, <out>/images/<subject>_v<k>.png (65535 is 1; tools/domain_gap.py reads 16-bit PNGs at
their depth). <out>/manifest.json holds the blocks record, the engine, FleXray's version and per
view the subject, the crop (z_start, z_stop, the pads), the isocentre (the MOOSE label and the
point in mm), the pose (rot_deg, xyz_mm, orthographic, sdd, delx), the attenuation factors drawn
for the labels the crop holds or null, and the seed. <out>/RENDER.json records the settings, the
subjects kept and passed over, the versions and the time; a second call under the same settings
reuses every view already on disk with its row, so a job cut short carries on where it stopped.

numpy, torch, nibabel, Pillow and fxr are imported only when a render is asked for, so the
orchestrator and the tests can load this file where they are missing. tools/ never goes on
sys.path, since tools/profile.py would shadow the standard library's profile, which torch imports.
"""

import argparse
import functools
import hashlib
import importlib.metadata
import importlib.util
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
SEARCH_DEPTH = 4
AIR_HU = -1000.0
HU_WINDOW = (-1000.0, 2000.0)
AIR_CLAMP_HU = -900.0
CROP_DEPTH = 256
CROP_TAU = 0.5
PROTOCOL = "all_structures_flexray_v4"
DATASET = "MOOSE"
TRAINING_BASE = "base"


def _structure_map():
    """TotalSegmentator v2.0.1's structure names to MOOSE's stored label names, in the order the
    masks are written into the label volume (a later mask wins where two overlap). Everything
    else TotalSegmentator segments is unsupervised by FleXray's protocol and stays out."""
    pairs = {"skull": "skull", "clavicula_left": "clavicle_left",
             "clavicula_right": "clavicle_right"}
    pairs.update({name: name for name in (
        "scapula_left", "scapula_right", "humerus_left", "humerus_right", "femur_left",
        "femur_right", "hip_left", "hip_right", "sacrum")})
    pairs["vertebrae_S1"] = "sacrum"
    pairs["sternum"] = "sternum"
    levels = [f"C{n}" for n in range(1, 8)] + [f"T{n}" for n in range(1, 13)]
    levels += [f"L{n}" for n in range(1, 6)]
    pairs.update({f"vertebrae_{level}": f"vertebra_{level.lower()}" for level in levels})
    pairs.update({f"rib_{side}_{n}": f"rib_{side}_{n}"
                  for side in ("left", "right") for n in range(1, 13)})
    pairs.update({name: name for name in (
        "kidney_left", "kidney_right", "liver", "spleen", "lung_upper_lobe_left",
        "lung_lower_lobe_left", "lung_upper_lobe_right", "lung_middle_lobe_right",
        "lung_lower_lobe_right")})
    pairs["heart"] = "heart_myocardium"
    return pairs


TOTALSEG_TO_MOOSE = _structure_map()


class SkipSubject(Exception):
    """A subject the renders pass over, with the reason RENDER.json records."""


# --- names and order ------------------------------------------------------------------------------

@functools.lru_cache(maxsize=1)
def rules():
    """schwingnet.render_blocks, the pure rules of the blocks and the engines."""
    from schwingnet import render_blocks

    return render_blocks


@functools.lru_cache(maxsize=1)
def pure_rank_key():
    """schwingnet.domain_gap.rank_key, the study's one rank, or None where it does not import."""
    try:
        from schwingnet.domain_gap import rank_key as pure
    except ImportError:
        return None
    return pure


def rank_key(salt, text):
    """A subject's or a view's place: the sha256 of "salt:text", as the pure module ranks."""
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


def render_file(subject, view):
    """The view's file, relative to the output folder, as the manifest names it."""
    return f"images/{image_stem(subject)}_v{view:02d}.png"


def view_seed(salt, subject, view):
    """The seed of one view: the first 32 bits of rank_key("<salt>:render", "<subject>:<view>"),
    the most numpy takes; the same whatever the engine or the group."""
    return int(rank_key(f"{salt}:render", f"{subject}:{view}")[:8], 16)


# --- reading a subject ----------------------------------------------------------------------------

def read_nifti(path):
    """A NIfTI volume as float32 in its own voxel order and its float64 affine; trailing axes of
    length one are dropped, as fxr's packer drops them (fxr/datasets/nifti.py, load_nifti)."""
    import nibabel
    import numpy as np

    image = nibabel.load(str(path))
    array = np.asarray(image.dataobj, dtype=np.float32)
    while array.ndim > 3 and array.shape[-1] == 1:
        array = array[..., 0]
    if array.ndim != 3:
        raise SkipSubject(f"{Path(path).name} is not a 3-D volume")
    return np.ascontiguousarray(array), np.asarray(image.affine, dtype=np.float64)


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


@functools.lru_cache(maxsize=1)
def moose_labels():
    """MOOSE's stored label names by id, from FleXray's own dataset spec
    (fxr/configs/datasets/MOOSE.yml)."""
    from fxr.protocols import load_dataset_spec_by_name

    stored = load_dataset_spec_by_name(DATASET).stored_labels
    return {int(i): str(name) for i, name in stored.items()}


def label_volume(folder, shape):
    """One label volume of MOOSE's stored ids from the subject's TotalSegmentator masks, uint8,
    each structure of TOTALSEG_TO_MOOSE written where its mask is set; a mask that is missing is
    passed over, since TotalSegmentator writes an empty one for an absent structure."""
    import numpy as np

    ids = {name: i for i, name in moose_labels().items()}
    label = np.zeros(shape, dtype=np.uint8)
    for structure, name in TOTALSEG_TO_MOOSE.items():
        path = Path(folder) / MASK_FOLDER / f"{structure}.nii.gz"
        if not path.is_file():
            continue
        mask = read_mask(path, shape)
        if mask.any():
            label[mask] = ids[name]
    return label


def load_subject(folder, subject):
    """One subject read for rendering: the CT as read, its affine and its MOOSE label volume."""
    volume, affine = read_nifti(Path(folder) / CT_NAME)
    label = label_volume(folder, volume.shape)
    if not label.any():
        raise SkipSubject("no supervised structure in its masks")
    return {"id": subject, "volume": volume, "affine": affine, "label": label}


# --- the engines ----------------------------------------------------------------------------------

@functools.lru_cache(maxsize=1)
def blocks_tool():
    """tools/render_blocks.py, loaded by path, since tools/ is never on sys.path."""
    path = ROOT / "tools" / "render_blocks.py"
    spec = importlib.util.spec_from_file_location("render_blocks_tool", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@functools.lru_cache(maxsize=1)
def training_base():
    """FleXray's packaged base training config, the one behind its released weights
    (fxr/configs/training/base.yml, through fxr.launch.cli.load_training_base)."""
    from fxr.launch.cli import load_training_base

    return load_training_base(TRAINING_BASE)


@functools.lru_cache(maxsize=1)
def label_remap():
    """FleXray's remap of MOOSE's stored ids to the released model's labels, the dense lookup
    table the crop weights, the attenuated ids and the runtime's collapse map read
    (fxr.datasets.remap.compile_training_label_remap_by_name at the protocol's model_labels of
    base.yml, as FleXrayTrainExperiment._label_projection compiles it)."""
    from fxr.datasets.remap import compile_training_label_remap_by_name

    names = training_base()["protocol"]["model_labels"]["names"]
    return compile_training_label_remap_by_name(PROTOCOL, DATASET, names)


def label_lut():
    """The lookup table as a list, native id to model id, -1 for an id the dataset never declares
    and 0 for one the protocol drops (TrainingLabelProjection.from_label_remap's reading of it)."""
    return [int(v) for v in label_remap().label_lut.tolist()]


def supervised_ids(lut):
    """The native ids above 0 whose model id is above 0, the ids fxr-render attenuates
    (TrainingLabelProjection.native_foreground_label_ids)."""
    return tuple(i for i, model_id in enumerate(lut) if i > 0 and model_id > 0)


def peek_random(count):
    """The next draws of Python's random, read without taking them, so the engine knows what
    FleXray's runtime is about to draw."""
    state = random.getstate()
    values = [random.random() for _ in range(count)]
    random.setstate(state)
    return values


class Engine:
    """What the two engines share: the blocks, the device, FleXray's label projection (the lookup
    table from MOOSE's ids to the model's, the supervised ids) and the label names."""

    name = ""

    def __init__(self, blocks, device):
        import torch

        self.blocks = blocks
        self.device = torch.device(device)
        self.lut = label_lut()
        self.supervised = supervised_ids(self.lut)
        self.names = moose_labels()

    def row(self, crop, point, label_id, pose, factors, ids_held):
        """A view's manifest row but its file, subject, view, seed and time."""
        attenuation = None
        if factors is not None:
            attenuation = {str(i): factors[i] for i in ids_held if i in factors}
        return {
            "crop": {key: int(crop[key])
                     for key in ("z_start", "z_stop", "pad_before", "pad_after")},
            "isocentre": {"label": label_id, "name": self.names.get(label_id) if label_id else None,
                          "point_mm": [float(v) for v in point]},
            "pose": pose,
            "attenuation": attenuation,
        }


class BlocksEngine(Engine):
    """The blocks engine: each part through its named function of tools/render_blocks.py."""

    name = "blocks"

    def __init__(self, blocks, device):
        super().__init__(blocks, device)
        self.parts = blocks_tool()
        self.sampler = self.parts.pose_sampler()

    def profile_record(self):
        parts = self.parts
        return {"pose": parts.MOOSE_POSE, "sdd": list(parts.SDD_RANGE),
                "delx": list(parts.DELX_RANGE), "orthographic": parts.ORTHOGRAPHIC_SHARE,
                "orientation": parts.ORIENTATION, "hu_window": list(parts.HU_WINDOW),
                "air_clamp_hu": parts.AIR_CLAMP_HU, "crop_depth": CROP_DEPTH,
                "attenuation_probability": parts.ATTENUATION_PROBABILITY,
                "attenuation_range": list(parts.ATTENUATION_RANGE),
                "attenuation_distribution": parts.ATTENUATION_DISTRIBUTION}

    def prepare(self, subject):
        """The volume windowed and clamped, the crops planned with what they hold, and weighed."""
        parts, blocks = self.parts, self.blocks
        volume = parts.NAMES["hu_window"][blocks.hu_window](subject["volume"])
        volume = parts.NAMES["air_clamp"][blocks.air_clamp](volume)
        plan = parts.NAMES["crop"][blocks.crop](int(volume.shape[2]))
        crops = parts.crop_content(subject["label"], plan)
        if not crops:
            raise SkipSubject("no crop holds a supervised structure")
        weights = parts.NAMES["crop_sampler"][blocks.crop_sampler](crops, self.lut)
        return {"volume": volume, "label": subject["label"], "affine": subject["affine"],
                "crops": crops, "weights": weights}

    def view(self, prepared, subject):
        """One view, the generators seeded by the caller: the draws in FleXray's order."""
        import numpy as np
        import torch

        parts, blocks = self.parts, self.blocks
        crop = prepared["crops"][parts.draw_crop(prepared["weights"])]
        affine = torch.from_numpy(parts.crop_affine(prepared["affine"], crop))
        volume = torch.from_numpy(parts.cut(prepared["volume"], crop, AIR_HU))[None].to(self.device)
        point, label_id = parts.NAMES["isocentre"][blocks.isocentre](crop, affine, volume)
        pose = parts.NAMES["pose"][blocks.pose](self.sampler)
        orthographic = parts.NAMES["projection"][blocks.projection]()
        attenuate = parts.NAMES["attenuation"][blocks.attenuation]
        keywords, factors = attenuate(self.supervised, self.device)
        label = None
        if keywords:
            label = torch.from_numpy(parts.cut(prepared["label"], crop, 0).astype(np.int64))
            label = label.to(self.device)
        view_request = parts.request(pose, point, orthographic, blocks.detector, blocks.ray_samples)
        images = parts.render(volume, label, affine.to(self.device), view_request, keywords)
        image = parts.NAMES["edit"][blocks.edit](parts.NAMES["scale"][blocks.scale](images)[0, 0])
        pose_row = {"rot_deg": [float(v) for v in pose["rot"][0].tolist()],
                    "xyz_mm": [float(v) for v in pose["xyz"][0].tolist()],
                    "orthographic": bool(orthographic), "sdd": pose["sdd"], "delx": pose["delx"]}
        row = self.row(crop, point, label_id, pose_row, factors, crop["ids"])
        return image.float().cpu().numpy(), row


class RuntimeEngine(Engine):
    """FleXray's own code for every step: its packer's window and crops, its loader's air clamp,
    its crop weights and sampler, its label projection, its SegmentationDRRRuntime at the MOOSE
    effective profile with the detector, the ray samples and the attenuation gate the blocks
    name, one view a call."""

    name = "flexray-runtime"

    def __init__(self, blocks, device):
        try:
            from fxr.experiment.label_projection import TrainingLabelProjection
            from fxr.models.camera.runtime import SegmentationDRRRuntime
        except ImportError as error:
            raise RuntimeError(f"FleXray's runtime does not import here ({error}); the blocks "
                               "engine runs without it") from error

        super().__init__(blocks, device)
        self.parts = blocks_tool()
        self.projection = TrainingLabelProjection.from_label_remap(label_remap())
        self.protocol, self.profile = runtime_profile(blocks)
        self.runtime = SegmentationDRRRuntime.from_effective_config(
            {"protocol": self.protocol, "drr_model": self.profile}, device=self.device)
        self.attenuation_probability = float(self.runtime.render_config.attenuation_prob)

    def profile_record(self):
        return {"effective_profile": self.profile, "protocol": self.protocol["name"],
                "hu_window": list(HU_WINDOW), "air_clamp_hu": AIR_CLAMP_HU,
                "crop_depth": CROP_DEPTH, "crop_tau": CROP_TAU}

    def prepare(self, subject):
        """The pack and the loader: the HU window to float16 (CTPreprocessing.apply), the air clamp
        the loader applies (_apply_ct_hu_bounds), the crops planned and described as the packer
        describes them (plan_z_crops, crop_z, crop_metadata), the background-only ones dropped,
        and the weights of the training sampler (inverse_label_frequency_weights)."""
        import numpy as np
        import torch
        from fxr.datasets.ct_crops import crop_metadata, crop_z, plan_z_crops
        from fxr.datasets.preprocessing import CTPreprocessing
        from fxr.datasets.runtime import _apply_ct_hu_bounds
        from fxr.datasets.sampling import inverse_label_frequency_weights

        stored = CTPreprocessing(hu_window=HU_WINDOW).apply(subject["volume"])
        loaded = _apply_ct_hu_bounds(torch.from_numpy(stored.astype(np.float32)),
                                     hu_min=AIR_HU, air_clamp_hu=AIR_CLAMP_HU)
        crops = []
        for spec in plan_z_crops(int(subject["volume"].shape[-1]), CROP_DEPTH):
            label_crop = crop_z(subject["label"], spec, fill_value=0)
            if not np.any(label_crop != 0):
                continue
            meta = crop_metadata(spec, label_crop, subject_id=subject["id"],
                                 source_sample_id=subject["id"])
            crops.append({"spec": spec, "z_start": spec.z_start, "z_stop": spec.z_stop,
                          "pad_before": spec.z_pad_before, "pad_after": spec.z_pad_after,
                          "ids": [int(i) for i in meta["crop_foreground_label_ids"]],
                          "centroids": [tuple(c) for c in meta["fg_centroids_ijk"]]})
        if not crops:
            raise SkipSubject("no crop holds a supervised structure")
        weights = inverse_label_frequency_weights([c["ids"] for c in crops], self.lut,
                                                  tau=CROP_TAU, class_aggregation="max")
        return {"volume": loaded.numpy(), "label": subject["label"], "affine": subject["affine"],
                "crops": crops, "weights": weights}

    def draw_crop(self, weights):
        """The training loader's draw: one item of torch's WeightedRandomSampler with replacement
        (fxr/experiment/segmentation.py, _weighted_sampler), on the global generator."""
        from torch.utils.data import WeightedRandomSampler

        return int(next(iter(WeightedRandomSampler(weights, num_samples=1, replacement=True))))

    def view(self, prepared, subject):
        """One view through SegmentationDRRRuntime.render, as fxr-render calls it
        (fxr/launch/render.py, render_dataset): the native labels validated by the projection,
        the supervised centroids, the collapse map and the native attenuated ids."""
        import numpy as np
        import torch
        from fxr.datasets.ct_crops import crop_z, offset_affine
        from fxr.models.camera.runtime import scale_rendered_images

        crop = prepared["crops"][self.draw_crop(prepared["weights"])]
        spec = crop["spec"]
        volume = torch.from_numpy(crop_z(prepared["volume"], spec, fill_value=AIR_HU))[None]
        volume = volume.to(self.device)
        # The pack's label item carries a channel axis and the loader batches one subject, so the
        # projection reads (1, 1, D, H, W) and gives back (1, D, H, W), as it does for fxr-render.
        label = torch.from_numpy(crop_z(prepared["label"], spec, fill_value=0).astype(np.int64))
        native = self.projection.validated_native_ids(label[None, None].to(self.device),
                                                      source=f"CT {subject}", require_mapped=True)
        affine = torch.from_numpy(offset_affine(prepared["affine"], spec))
        kept = [n for n, i in enumerate(crop["ids"]) if i in self.supervised]
        ids_kept = [crop["ids"][n] for n in kept]
        centroids = torch.tensor([crop["centroids"][n] for n in kept], dtype=torch.float32)
        centroids = centroids.reshape(-1, 3)
        factors = self.factors_ahead(len(ids_kept))
        with torch.inference_mode():
            result = self.runtime.render(
                volume=volume, label=native, affine=affine.to(self.device),
                fg_centroids_ijk=centroids,
                foreground_collapse_map=self.projection.foreground_collapse_map(),
                attenuated_label_ids=self.projection.native_foreground_label_ids())
            image = scale_rendered_images(result.images)[0, 0]
        request = result.request
        point = [float(v) for v in torch.as_tensor(request.isocenter).reshape(-1)[:3].tolist()]
        label_id = None
        if ids_kept:
            chosen = torch.as_tensor(request.isocenter).reshape(-1)[:3]
            label_id = ids_kept[self.parts.nearest_centroid(chosen, centroids, affine)]
        pose_row = {"rot_deg": [float(v) for v in torch.as_tensor(request.rot)[0].tolist()],
                    "xyz_mm": [float(v) for v in torch.as_tensor(request.xyz)[0].tolist()],
                    "orthographic": bool(request.orthographic),
                    "sdd": float(request.intrinsics["sdd"][0]),
                    "delx": float(request.intrinsics["delx"][0])}
        row = self.row(crop, point, label_id, pose_row, factors, crop["ids"])
        return image.float().cpu().numpy(), row

    def factors_ahead(self, centroid_count):
        """The attenuation factors FleXray's runtime is about to draw, or None when its gate will
        be shut, read ahead so the record names what the render applied: the gate is the fourth
        draw of Python's random in SegmentationDRRRuntime.render (after delx, sdd and the
        projection), and the factors follow, on torch's generator, the isocentre's randperm and
        the pose's two rand(1, 3) (fxr 1.0.2's order; tests/test_flexray_render.py checks the
        factors against what render_drr drew). The generators are put back as they were."""
        import torch
        from fxr.drr import sample_attenuation

        if self.attenuation_probability <= 0.0:
            return None
        if not peek_random(4)[3] < self.attenuation_probability:
            return None
        config = self.runtime.render_config
        with torch.random.fork_rng(devices=self.parts.cuda_devices(self.device)):
            if centroid_count:
                torch.randperm(centroid_count)
            torch.rand(1, 3)
            torch.rand(1, 3)
            drawn = sample_attenuation(config.attenuation_range, len(self.supervised), self.device,
                                       torch.float32, config.attenuation_dist)
        return dict(zip(self.supervised, (float(f) for f in drawn.tolist()), strict=True))


def runtime_profile(blocks):
    """FleXray's MOOSE effective profile (drr_model.default merged with drr_model.datasets.MOOSE
    by fxr.models.camera.config.resolve_ct_profiles, as fxr-render merges them) at one view a
    call, the blocks' detector and ray samples, and the attenuation gate shut when the blocks say
    off; with the protocol block the runtime derives its label space from."""
    import copy

    from fxr.models.camera.config import resolve_ct_profiles

    base = training_base()
    drr = base["drr_model"]
    config = {"data": {"CT": {DATASET: {}}},
              "drr_model": {"default": drr["default"],
                            "datasets": {DATASET: drr["datasets"][DATASET]}}}
    profile = resolve_ct_profiles(config)[DATASET]
    profile["num_views"] = 1
    profile["intrinsics_cfg"]["height"] = int(blocks.detector)
    profile["intrinsics_cfg"]["width"] = int(blocks.detector)
    profile["num_samples"] = int(blocks.ray_samples)
    if blocks.attenuation == "off":
        profile["attenuation_cfg"]["prob"] = 0.0
    return copy.deepcopy(base["protocol"]), profile


ENGINE_CLASSES = {BlocksEngine.name: BlocksEngine, RuntimeEngine.name: RuntimeEngine}


def seed_generators(seed):
    """Seed Python's, numpy's and torch's generators, the three FleXray's runtime draws from."""
    import numpy as np
    import torch

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


# --- files ----------------------------------------------------------------------------------------

def write_json(path, data):
    """Write a JSON file whole: to a neighbour first, then renamed, so a cut job leaves none
    half-written."""
    part = path.with_name(path.name + ".part")
    part.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(part, path)


def save_png(path, image):
    """A render in 0 to 1 as a 16-bit grey PNG, 65535 for 1, written whole by the same neighbour
    and rename."""
    import numpy as np
    from PIL import Image

    unit = np.clip(np.asarray(image, dtype=np.float64), 0.0, 1.0)
    data = np.round(unit * 65535.0).astype(np.uint16)
    part = path.with_name(path.name + ".part")
    Image.fromarray(data).save(part, format="PNG")
    os.replace(part, path)


def read_json(path):
    """A JSON file's content, or None when it is missing or unreadable."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def versions():
    """The versions of the packages a render depends on, as the environment reports them."""
    found = {}
    for name in ("flexray", "nanodrr", "torch", "nibabel", "numpy", "pillow"):
        try:
            found[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            found[name] = "absent"
    return found


def render_settings(blocks, engine, salt):
    """What decides a view's pixels besides its subject and index; a view on disk is reused only
    by a run under the same."""
    found = versions()
    return {"blocks": rules().as_record(blocks), "engine": engine, "salt": salt,
            "flexray": found["flexray"], "nanodrr": found["nanodrr"]}


def earlier_rows(out, settings):
    """The rows of the manifest an earlier run under the same settings wrote, by file; none when
    RENDER.json is missing or names other settings, since the renders on disk are then another
    run's, whatever their names."""
    record = read_json(out / "RENDER.json")
    if not isinstance(record, dict) or record.get("settings") != settings:
        return {}
    manifest = read_json(out / "manifest.json")
    rows = manifest.get("views") if isinstance(manifest, dict) else manifest
    if not isinstance(rows, list):
        return {}
    return {row["file"]: row for row in rows if isinstance(row, dict) and "file" in row}


def write_manifest(out, settings, rows):
    """manifest.json: the blocks, the engine, FleXray's version and the rows by file name."""
    write_json(out / "manifest.json", {
        "blocks": settings["blocks"], "engine": settings["engine"], "flexray": settings["flexray"],
        "views": sorted(rows.values(), key=lambda row: row["file"])})


def log(text):
    print(f"flexray-render {time.strftime('%H:%M:%S')} {text}", flush=True)


# --- the run --------------------------------------------------------------------------------------

def check_arguments(subjects, salt, device, blocks, engine):
    """The arguments held to what the engines take, the blocks' faults in engine_problems' words
    before anything is written."""
    found = rules().engine_problems(engine, blocks)
    if found:
        raise rules().RenderBlockError("; ".join(found))
    if subjects < 1:
        raise ValueError("subjects must be at least 1")
    if not isinstance(salt, str) or not salt:
        raise ValueError("salt must be a non-empty string")
    if str(device).split(":")[0] not in ("cpu", "cuda"):
        raise ValueError("device must be cpu or cuda")


def ordered_subjects(found, subject_ids, salt):
    """The subjects to visit, in order: the ids given, each found or passed over, else every
    subject found in the salted order."""
    if subject_ids is None:
        return sorted(found, key=lambda name: rank_key(f"{salt}:subjects", name))
    return [str(subject) for subject in subject_ids]


def load_or_skip(state, subject):
    """The subject read and prepared for its engine, or None after recording why it is passed
    over."""
    started = time.perf_counter()
    folder = state["root"] / subject
    try:
        if subject not in state["found"]:
            raise SkipSubject("not found under the CT folder")
        return state["engine"].prepare(load_subject(folder, subject))
    except SkipSubject as reason:
        state["skipped"].append(f"{subject}: {reason}")
    except Exception as error:  # nibabel raises several unrelated error types, as fxr notes
        # A truncated download or a header nibabel refuses is named by its kind alone, so no
        # path reaches the record.
        state["skipped"].append(f"{subject}: unreadable ({type(error).__name__})")
    finally:
        state["seconds_loading"] += time.perf_counter() - started
    return None


def render_missing(state, subject, prepared, missing):
    """The missing views of one kept subject: each written to disk, its row into the run's."""
    for view in missing:
        seed = view_seed(state["salt"], subject, view)
        seed_generators(seed)
        started = time.perf_counter()
        image, row = state["engine"].view(prepared, subject)
        seconds = time.perf_counter() - started
        state["seconds_rendering"] += seconds
        file = render_file(subject, view)
        save_png(state["out"] / file, image)
        state["rows"][file] = {"file": file, "subject": subject, "view": view, "seed": seed,
                               **row, "seconds": round(seconds, 3)}
        state["rendered_now"] += 1


def visit_subject(state, subject):
    """Keep a subject whose views are all on disk with their rows, or render what it lacks; a
    subject that cannot be read is passed over with its reason and gives no row."""
    files = [render_file(subject, view) for view in range(state["views"])]
    done = [f for f in files if f in state["earlier"] and (state["out"] / f).is_file()]
    missing = [view for view, f in enumerate(files) if f not in done]
    if missing:
        prepared = load_or_skip(state, subject)
        if prepared is None:
            return False
        render_missing(state, subject, prepared, missing)
    for f in done:
        state["rows"][f] = state["earlier"][f]
    state["reused"] += len(done)
    return True


def render_subjects(ct_root, out, subjects, salt, device, *, blocks, engine="blocks",
                    subject_ids=None):
    """Render blocks.views views of each of the first `subjects` usable CTs under ct_root, in the
    salted order, or of the subject_ids given, into out, by the engine named; returns what was
    rendered, the subjects kept and the ones passed over with their reasons."""
    check_arguments(subjects, salt, device, blocks, engine)
    started = time.perf_counter()
    # The engine first: one that cannot be built writes nothing.
    built = ENGINE_CLASSES[engine](blocks, device)
    out = Path(out)
    (out / "images").mkdir(parents=True, exist_ok=True)
    settings = render_settings(blocks, engine, salt)
    state = {"root": Path(ct_root), "out": out, "salt": salt, "views": blocks.views,
             "settings": settings, "earlier": earlier_rows(out, settings), "rows": {},
             "skipped": [], "rendered_now": 0, "reused": 0, "seconds_loading": 0.0,
             "seconds_rendering": 0.0, "engine": built}
    # The manifest first, holding only what this run may reuse, then RENDER.json naming this
    # run's settings, so a run cut at any point never leaves rows another run would trust.
    write_manifest(out, settings, state["earlier"])
    state["found"] = set(find_subjects(ct_root))
    kept = []
    arguments = {"ct_root": str(ct_root), "subjects": subjects, "salt": salt, "device": str(device),
                 "engine": engine, "subject_ids": list(subject_ids) if subject_ids else None}
    write_json(out / "RENDER.json", run_record(state, kept, arguments, started, "running"))
    for subject in ordered_subjects(sorted(state["found"]), subject_ids, salt):
        if len(kept) >= subjects:
            break
        if visit_subject(state, subject):
            kept.append(subject)
            write_manifest(out, settings, state["rows"])
            if len(kept) % 25 == 0:
                log(f"{len(kept)} subjects kept, {state['rendered_now']} rendered now")
    write_manifest(out, settings, state["rows"])
    record = run_record(state, kept, arguments, started, "done")
    write_json(out / "RENDER.json", record)
    log(f"{engine}: {len(kept)} of {subjects} subjects kept, {len(state['skipped'])} passed over, "
        f"{state['rendered_now']} rendered now, {state['reused']} kept from before")
    return {"rendered": len(state["rows"]), "rendered_now": state["rendered_now"],
            "reused": state["reused"], "subjects": kept, "skipped": list(state["skipped"])}


def run_record(state, kept, arguments, started, status):
    """RENDER.json: the settings, the arguments, the counts, the subjects, the profile and the
    versions."""
    return {
        "version": 2,
        "status": status,
        "settings": state["settings"],
        "arguments": arguments,
        "counts": {"subjects_found": len(state["found"]), "subjects_kept": len(kept),
                   "subjects_skipped": len(state["skipped"]), "renders": len(state["rows"]),
                   "rendered_now": state["rendered_now"], "reused": state["reused"]},
        "subjects": list(kept),
        "skipped": list(state["skipped"]),
        "profile": state["engine"].profile_record(),
        "versions": versions(),
        "seconds": {"total": round(time.perf_counter() - started, 3),
                    "loading": round(state["seconds_loading"], 3),
                    "rendering": round(state["seconds_rendering"], 3)},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--ct-root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--subjects", type=int, default=250)
    parser.add_argument("--salt", required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--engine", default="blocks", choices=rules().ENGINES)
    parser.add_argument("--blocks", action="append", default=[], metavar="KEY=VALUE",
                        help="a render block, repeatable; none is FleXray's released recipe")
    parser.add_argument("--subject", action="append", default=None, metavar="ID",
                        help="a subject to render, repeatable; none takes the salted order")
    args = parser.parse_args(argv)
    blocks = rules().parse(args.blocks)
    done = render_subjects(args.ct_root, args.out, args.subjects, args.salt, args.device,
                           blocks=blocks, engine=args.engine,
                           subject_ids=tuple(args.subject) if args.subject else None)
    return 0 if done["subjects"] else 1


if __name__ == "__main__":
    sys.exit(main())
