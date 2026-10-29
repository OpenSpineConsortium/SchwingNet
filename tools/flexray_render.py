"""Synthetic X-rays from held CTs and their existing masks through the render blocks, by one of two
engines, for the DRR domain-gap study's replication test of FleXray's renderer; and the segment
subcommand that makes MOOSE's masks for the replication's CTs with moosez.

The owner asked on 2026-10-25 (the thread "Compare FleXray DRRs to real X-ray corpora") for
FleXray's synthetic DRRs to be set beside every held real X-ray corpus, and for FleXray's recipe
to be rendered both through this project's blocks and through FleXray's own code, so the two can
be compared; and on 2026-10-26 that the CTs' labels come from SPINEPS's existing masks for the
production renders and from MOOSE, moosez's masks, only when replicating FleXray's own dataset,
never from TotalSegmentator, the segmenter being a block of its own (schwingnet.segmenters); and on
2026-10-27 that the tests comparing DRRs with real X-rays run without masks at all, since a DRR's
pixels are the CT's projection alone: segmenter none reads no mask and renders every CT, for a
recipe that reads no labels (schwingnet.render_blocks.reads_labels: crop_sampler uniform,
isocentre volume-centre, attenuation off, as the presets physical-ct and, but for its segmenter,
fluxray-raw are). tools/domain_gap.py runs the study and calls render_subjects here for each
render group. A render is a configuration of schwingnet.render_blocks (FleXray's released MOOSE
recipe on SPINEPS masks when no block is named) run by an engine:

- "blocks" calls tools/render_blocks.py, one function per named choice, FleXray's primitives
  (fxr.drr) underneath for the pose draw and the rendering;
- "flexray-runtime" calls FleXray's own functions for every step: its pack's HU window
  (CTPreprocessing), its CT loader's air clamp, its crop planner and packer (ct_crops.plan_z_crops
  at the recipe's overlap, crop_z, crop_metadata, offset_affine), its crop weights
  (sampling.inverse_label_frequency_weights) and torch's WeightedRandomSampler for the draw, its
  label remap (compile_training_label_remap_by_name("all_structures_flexray_v4", "MOOSE") at the
  released model's 61 labels, TrainingLabelProjection), its SegmentationDRRRuntime built from the
  MOOSE effective profile of its base training config at one view a call, since each view draws
  its own crop, and its scale_rendered_images; under pose fluxray-grid, which its PoseSampler
  cannot draw, the request with the explicit pose through fxr.drr's primitives (compute_isocenter
  at the volume's centre, DRRRenderRequest, render_drr) and the same scaling. It takes only the
  blocks FleXray's code can honour (schwingnet.render_blocks.engine_problems) and refuses the rest
  in words before rendering. It needs kornia, which FleXray's camera package imports for its
  training-time label smoothing (flexray's train extra); the blocks engine needs fxr.drr alone.

Both read the same CT once (nibabel) and one label volume of MOOSE's stored ids built by the
segmenter block (tools/render_blocks.py, NAMES["segmenter"]: SPINEPS's mask relabelled from the
VerSe alphabet, or moosez's model outputs merged), which is what FleXray's own code reads, L6 and
the thirteenth ribs in it and dropped by FleXray's remap as in its own training, T13 and the
coccyx left out and recorded as unsupervised, or under segmenter none no label volume at all, every
planned crop then kept with no structure in it; and they write the same layout. The seed of a view
comes from the salt, the subject and the view alone, not from the engine or the group, so two
render groups on one folder that differ only by their attenuation block share every crop,
isocentre and pose, and the reference engine seeds FleXray's own generators from the same number
(its draws differ where its code differs; that is the point of the test).

    python tools/flexray_render.py --ct-root <dir> --out <dir> --subjects 250 --salt <s> \\
        [--spineps <dir>] [--moose <dir>] [--device cuda] [--engine blocks|flexray-runtime] \\
        [--blocks KEY=VALUE]... [--subject ID]...
    python tools/flexray_render.py segment --segmenter moose --ct-root <dir> \\
        --subjects <out>/render-subjects.json --weights <dir> --out <dir> [--device cuda] [--plan]

A render needs the CTs, and the masks folder of its segmenter unless that is none. A subject is a
folder under --ct-root, one to four levels down, that holds ct.nii.gz; its masks are found under the
segmenter's folder (--spineps, --moose; a render whose segmenter has no folder is refused in words
before anything is written, and segmenter none asks for none): SPINEPS's by the file
*_seg-vert_msk.nii* whose name before _seg-vert names the subject, moosez's under
<moose>/<subject>/ by the model's region in each file's path (tools/render_blocks.py,
locate_spineps and locate_moose), each on the CT's grid, the shape and the affine its header
gives, read once a subject (header_grid); a mask of another shape or another affine is skipped by
name with that reason. Without --subject, subjects are taken in the order of
rank_key("<salt>:subjects", id) until --subjects are kept, a subject with no mask, no structure
FleXray supervises or an unreadable file passed over with its reason (under segmenter none only
an unreadable file); with --subject the named ones alone are rendered, in that order. Each CT is
read as float32 HU in its own voxel order with its affine, as FleXray's NIfTI packer reads it.

Per view, in FleXray's order of draws: one crop by the crop sampler's weights, one isocentre, one
pose, one gate and the attenuation factors, one render, scaled to 0 to 1 and written as a 16-bit
grey PNG, <out>/images/<subject>_v<k>.png (65535 is 1; tools/domain_gap.py reads 16-bit PNGs at
their depth). <out>/manifest.json holds the blocks record, the engine, the segmenter, FleXray's
version, each kept subject's label record (the scheme, the mask files by name, the MOOSE ids
present, the dropped names present, the unsupervised values seen, the moosez models missing; under
segmenter none the scheme none, nothing read and a note saying so) and per view the subject, the
crop (z_start, z_stop, the pads), the isocentre (the MOOSE label and the
point in mm), the pose (rot_deg, xyz_mm, orthographic, sdd, delx, and grid, the pose's index under
fluxray-grid, else null), the attenuation factors drawn for the labels the crop holds or null, and
the seed. <out>/RENDER.json records the settings, the subjects kept and passed over, the versions
and the time; a second call under the same settings reuses every view already on disk with its
row, so a job cut short carries on where it stopped.

The segment subcommand prepares CTs for segmenter=moose only: for each subject of the list (the
study's <out>/render-subjects.json, {folder: [subject ids]}, read at the CT folder's name, or a
plain list) that lacks a model's masks under --out/<subject>/, it calls moosez's Python entry
`moose(input, models, output_dir, accelerator)` with the five CT models whose labels MOOSE.yml
stores (schwingnet.segmenters.MOOSEZ_MODELS: organs, cardiac, peripheral bones, ribs, vertebrae;
the lungs, muscles and digestive models label nothing MOOSE stores) on a link to the CT named
CT_<id>.nii.gz inside that folder, so moosez's outputs land under it whether it writes beside its
input or under its output folder, in moosez's own layout, which the locator reads. The weights
are the model zips the fetch row moose_weights landed under --weights by their release names,
never downloaded: a model whose zip is missing, or is not a whole zip (a part the fetch left
under the zip's final name, which a resend of fetch moose_weights resumes), refuses the whole run
before moosez is imported and before any model is unpacked; when the run starts, each zip is
unpacked into moosez's own models directory as moosez's download would unpack it, with the
model_version.json naming the release URL that moosez reads before downloading, a model already
there under that URL left as it is, and moosez's metadata is held equal to this tool's copy of
it first, since moosez downloads a model whose URL differs; then each unpacked model's
dataset.json, the labels moosez itself reads (moosez/models.py, Model.__get_organ_indices), is
held equal to this tool's table (schwingnet.segmenters.MOOSEZ_MODELS, the README's), the four
renamed bones read as one name, and a model whose labels differ refuses the run, since the
relabel tables would land its values on the wrong structures; SEGMENT.json records both checks.
--plan prints the plan (the subjects, what each lacks, the zips found and whether each is whole,
the refusals) and stops. A run prints the plan, then {"done": [...]}, then one plain line, the
tail the bench report takes: "segment: N subjects run, M models, F files found, G not found,
written under <out>". SPINEPS is never run here: --segmenter spineps is refused with the owner's
reason, its production array is not approved; its existing masks are read under --spineps.
moosez's source (3.2.2) says what its library entry writes: moose() reads the input by its path,
through a link as through any file, and writes each model's multilabel file straight into the
output_dir it is given as <prefix>segmentation_<input stem>.nii.gz, the prefix clin_CT_<region>_
(moosez/__init__.py, moose; models.py, Model.multilabel_prefix), reoriented back to the input's
orientation code, so for CT_s0001.nii.gz under the vertebrae model the file is
clin_CT_vertebrae_segmentation_CT_s0001.nii.gz beside the link, which the locator reads by its
region word; the tests hold both that layout and the command line's.

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
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [entry for entry in sys.path if Path(entry or ".").resolve() != ROOT / "tools"]
for folder in (ROOT / "vendor" / "beethoven-qa" / "src", ROOT / "src"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

CT_NAME = "ct.nii.gz"
SEARCH_DEPTH = 4
AIR_HU = -1000.0
HU_WINDOW = (-1000.0, 2000.0)
AIR_CLAMP_HU = -900.0
CROP_DEPTH = 256
CROP_TAU = 0.5
PROTOCOL = "all_structures_flexray_v4"
DATASET = "MOOSE"
TRAINING_BASE = "base"
# moosez 3.2's weights for the five models the segment subcommand runs (its models.py,
# MODEL_METADATA): the folder each zip unpacks to under moosez's models directory, and the
# release asset, which the fetch row moose_weights of grid/run-platform-fetch.sh lands under
# moose_weights/raw by its file name. Copied here so the plan needs no moosez; where moosez
# imports, its own metadata is held equal before anything runs, since moosez downloads a model
# whose recorded URL differs from its own.
MOOSEZ_RELEASE = "https://github.com/ENHANCE-PET/MOOSE/releases/download/moosez-v.3.1.3/"
MOOSEZ_WEIGHTS = {
    "clin_ct_organs": ("Dataset123_Organs", "clin_ct_organs_ras_07052025.zip"),
    "clin_ct_cardiac": ("Dataset888_Cardiac", "clin_ct_cardiac_ras_21052025.zip"),
    "clin_ct_peripheral_bones": ("Dataset666_Peripheral-Bones",
                                 "clin_ct_peripheral_bones_ras_07052025.zip"),
    "clin_ct_ribs": ("Dataset444_Ribs", "clin_ct_ribs_ras_08052025.zip"),
    "clin_ct_vertebrae": ("Dataset111_Vertebrae", "clin_ct_vertebrae_ras_21052025.zip"),
}
MODEL_VERSION_FILE = "model_version.json"
SPINEPS_REFUSAL = ("SPINEPS is never run here: its production array is not approved (the owner's "
                   "word); its existing masks are read under --spineps")


class SkipSubject(Exception):
    """A subject the renders pass over, with the reason RENDER.json records."""


class SegmentError(Exception):
    """A segment run refused before anything is written, with the reason."""


# --- names and order ------------------------------------------------------------------------------

@functools.lru_cache(maxsize=1)
def rules():
    """schwingnet.render_blocks, the pure rules of the blocks and the engines."""
    from schwingnet import render_blocks

    return render_blocks


@functools.lru_cache(maxsize=1)
def schemes():
    """schwingnet.segmenters, the names, the alphabets and the maps of the two segmenters."""
    from schwingnet import segmenters

    return segmenters


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


def ct_subjects(ct_root):
    """Every folder one to SEARCH_DEPTH levels under ct_root that holds a CT, as a sorted list of
    paths relative to ct_root; a subject's own folders are not searched further."""
    root = Path(ct_root)
    found = []
    for folder, names, files in os.walk(root):
        here = Path(folder)
        depth = len(here.relative_to(root).parts)
        if depth >= 1 and CT_NAME in files:
            found.append(here.relative_to(root).as_posix())
            names[:] = []
            continue
        if depth >= SEARCH_DEPTH:
            names[:] = []
        names.sort()
    return sorted(found)


def header_grid(ct_root, subject):
    """The CT's grid, its shape and its affine, from one read of its header, as
    tools/render_blocks.py reads a mask's (mask_grid), so a subject is listed by masks on its
    own grid; None for a header that cannot be read, which lists the subject by name alone and
    leaves the render to pass it over as unreadable."""
    try:
        return blocks_tool().mask_grid(Path(ct_root) / subject / CT_NAME)
    except Exception:  # nibabel raises several unrelated error types, as fxr notes
        return None


def has_masks(subject, segmenter, roots, grid):
    """Whether the segmenter's locator finds the subject's masks on the CT's grid under its
    folder: one SPINEPS mask, or under moose every model's file, since the segment job makes
    all five for each chosen CT and a render that read fewer would label less than the
    replication's, with no word in the manifest but models_missing; always under none, which
    reads no mask."""
    parts = blocks_tool()
    root = roots.get(segmenter)
    if segmenter == rules().NO_SEGMENTER:
        return True
    if segmenter == "spineps":
        return parts.locate_spineps(subject, root, grid) is not None
    found = parts.locate_moose(subject, root, grid)
    return all(model in found for model in schemes().MOOSEZ_MODELS)


def find_subjects(ct_root, segmenter=None, roots=None):
    """The subjects under ct_root (ct_subjects), as ids; with a segmenter named, only those
    whose masks that scheme's locator finds, on the CT's grid, under roots[segmenter], which
    must be given, as load_subject will find them, so the subject choice of tools/domain_gap.py
    and the render agree on which CTs have masks; with segmenter none, which reads no mask,
    every CT, no masks folder asked for."""
    found = ct_subjects(ct_root)
    if segmenter is None or segmenter == rules().NO_SEGMENTER:
        return found
    problems = schemes().scheme_problems(segmenter)
    if problems:
        raise ValueError("; ".join(problems))
    if not roots or roots.get(segmenter) is None:
        raise ValueError(f"segmenter={segmenter}: no masks folder given (roots[{segmenter!r}])")
    return [subject for subject in found
            if has_masks(subject, segmenter, roots, header_grid(ct_root, subject))]


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


def moose_names():
    """MOOSE's stored label names by id, from schwingnet.segmenters' copy of FleXray's
    fxr/configs/datasets/MOOSE.yml, background left out."""
    return {i: name for i, name in schemes().MOOSE_STORED.items() if i > 0}


def load_subject(folder, subject, blocks, roots, supervised):
    """One subject read for rendering: the CT as read, its affine, the label volume of MOOSE's
    stored ids the segmenter block builds from its masks, and that volume's record; passed over
    when no mask is found, when the masks hold nothing, or nothing FleXray's protocol supervises,
    since such a subject gives FleXray's sampler no crop to draw. Under segmenter none the label
    is None and no subject is passed over for its labels, since the render reads none."""
    import numpy as np

    parts = blocks_tool()
    volume, affine = read_nifti(Path(folder) / CT_NAME)
    grid = (volume.shape, affine)
    try:
        label, record = parts.NAMES["segmenter"][blocks.segmenter](subject, grid, roots)
    except parts.MaskProblem as problem:
        raise SkipSubject(str(problem)) from problem
    if label is None:
        return {"id": subject, "volume": volume, "affine": affine, "label": None, "record": record}
    if not label.any():
        raise SkipSubject("no structure in its masks")
    if not np.isin(np.unique(label), np.asarray(supervised)).any():
        raise SkipSubject("no structure FleXray supervises in its masks")
    return {"id": subject, "volume": volume, "affine": affine, "label": label, "record": record}


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
        self.names = moose_names()

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

    def no_supervised_crop(self, weights):
        """Passed over when no crop weighs anything: FleXray's sampler would draw nothing."""
        if float(weights.sum()) <= 0.0:
            raise SkipSubject("no crop holds a structure FleXray supervises")


def pose_record(pose, orthographic):
    """A pose as the manifest records it: degrees, mm, the beam, the distance, the pixel and the
    grid index under fluxray-grid."""
    return {"rot_deg": [float(v) for v in pose["rot"][0].tolist()],
            "xyz_mm": [float(v) for v in pose["xyz"][0].tolist()],
            "orthographic": bool(orthographic), "sdd": float(pose["sdd"]),
            "delx": float(pose["delx"]), "grid": pose.get("grid")}


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
                "crop_overlap": rules().CROP_OVERLAP.get(self.blocks.crop),
                "attenuation_probability": parts.ATTENUATION_PROBABILITY,
                "attenuation_range": list(parts.ATTENUATION_RANGE),
                "attenuation_distribution": parts.ATTENUATION_DISTRIBUTION,
                "grid": grid_record()}

    def prepare(self, subject):
        """The volume windowed and clamped, the crops planned with what they hold (every planned
        crop, holding nothing, when no label was read), and weighed."""
        parts, blocks = self.parts, self.blocks
        volume = parts.NAMES["hu_window"][blocks.hu_window](subject["volume"])
        volume = parts.NAMES["air_clamp"][blocks.air_clamp](volume)
        plan = parts.NAMES["crop"][blocks.crop](int(volume.shape[2]))
        crops = parts.crop_content(subject["label"], plan)
        if not crops:
            raise SkipSubject("no crop holds a structure")
        weights = parts.NAMES["crop_sampler"][blocks.crop_sampler](crops, self.lut)
        self.no_supervised_crop(weights)
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
        aim = parts.NAMES["isocentre"][blocks.isocentre]
        point, label_id = aim(crop, affine, volume, self.supervised)
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
        row = self.row(crop, point, label_id, pose_record(pose, orthographic), factors, crop["ids"])
        return image.float().cpu().numpy(), row


class RuntimeEngine(Engine):
    """FleXray's own code for every step: its packer's window and crops, its loader's air clamp,
    its crop weights and sampler, its label projection, its SegmentationDRRRuntime at the MOOSE
    effective profile with the detector, the ray samples and the attenuation gate the blocks
    name, one view a call; under pose fluxray-grid, its primitives with the explicit pose."""

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
        self.grid = blocks.pose == "fluxray-grid"
        self.runtime = None
        self.attenuation_probability = 0.0
        if not self.grid:
            self.runtime = SegmentationDRRRuntime.from_effective_config(
                {"protocol": self.protocol, "drr_model": self.profile}, device=self.device)
            self.attenuation_probability = float(self.runtime.render_config.attenuation_prob)

    def profile_record(self):
        return {"effective_profile": None if self.grid else self.profile,
                "protocol": self.protocol["name"], "hu_window": list(HU_WINDOW),
                "air_clamp_hu": AIR_CLAMP_HU, "crop_depth": CROP_DEPTH, "crop_tau": CROP_TAU,
                "crop_overlap": rules().CROP_OVERLAP.get(self.blocks.crop),
                "grid": grid_record() if self.grid else None}

    def crop_specs(self, depth):
        """The crops as FleXray's packer plans them (plan_z_crops at the recipe's overlap), or
        the whole volume as one crop (a CropSpec with no pad, what crop_z and offset_affine take)
        under crop=whole."""
        from fxr.datasets.ct_crops import CropSpec, plan_z_crops

        if self.blocks.crop == "whole":
            return (CropSpec(0, 0, depth, 0, 0),)
        overlap = rules().CROP_OVERLAP[self.blocks.crop]
        return plan_z_crops(depth, CROP_DEPTH, max_overlap=overlap)

    def prepare(self, subject):
        """The pack and the loader: the HU window to float16 (CTPreprocessing.apply), the air clamp
        the loader applies (_apply_ct_hu_bounds), the crops planned and described as the packer
        describes them (plan_z_crops, crop_z, crop_metadata), the background-only ones dropped
        (every one kept, holding nothing, when no label was read), and the weights of the
        training sampler (inverse_label_frequency_weights), or every crop alike under
        crop_sampler=uniform."""
        import numpy as np
        import torch
        from fxr.datasets.preprocessing import CTPreprocessing
        from fxr.datasets.runtime import _apply_ct_hu_bounds
        from fxr.datasets.sampling import inverse_label_frequency_weights

        stored = CTPreprocessing(hu_window=HU_WINDOW).apply(subject["volume"])
        loaded = _apply_ct_hu_bounds(torch.from_numpy(stored.astype(np.float32)),
                                     hu_min=AIR_HU, air_clamp_hu=AIR_CLAMP_HU)
        crops = []
        for spec in self.crop_specs(int(subject["volume"].shape[-1])):
            crop = packed_crop(spec, subject)
            if crop is not None:
                crops.append(crop)
        if not crops:
            raise SkipSubject("no crop holds a structure")
        if self.blocks.crop_sampler == "uniform":
            weights = torch.ones(len(crops), dtype=torch.float64)
        else:
            weights = inverse_label_frequency_weights([c["ids"] for c in crops], self.lut,
                                                      tau=CROP_TAU, class_aggregation="max")
        self.no_supervised_crop(weights)
        return {"volume": loaded.numpy(), "label": subject["label"], "affine": subject["affine"],
                "crops": crops, "weights": weights}

    def draw_crop(self, weights):
        """The training loader's draw: one item of torch's WeightedRandomSampler with replacement
        (fxr/experiment/segmentation.py, _weighted_sampler), on the global generator."""
        from torch.utils.data import WeightedRandomSampler

        return int(next(iter(WeightedRandomSampler(weights, num_samples=1, replacement=True))))

    def cut(self, prepared, subject):
        """The drawn crop of the volume and the labels as FleXray's loader hands them to its
        renderer: the crop, the volume with air in the pads, the native labels validated by the
        projection (the pack's label item carries a channel axis and the loader batches one
        subject, so the projection reads (1, 1, D, H, W) and gives back (1, D, H, W), as it does
        for fxr-render), or None when no label was read, and the affine moved to the crop."""
        import torch
        from fxr.datasets.ct_crops import crop_z, offset_affine

        crop = prepared["crops"][self.draw_crop(prepared["weights"])]
        spec = crop["spec"]
        volume = torch.from_numpy(crop_z(prepared["volume"], spec, fill_value=AIR_HU))[None]
        native = self.native_labels(prepared["label"], spec, subject)
        affine = torch.from_numpy(offset_affine(prepared["affine"], spec))
        return crop, volume.to(self.device), native, affine

    def native_labels(self, label, spec, subject):
        """The crop's labels validated by FleXray's projection as its loader hands them on, or
        None when no label was read (segmenter none, which only the explicit-pose path takes)."""
        import numpy as np
        import torch
        from fxr.datasets.ct_crops import crop_z

        if label is None:
            return None
        cropped = torch.from_numpy(crop_z(label, spec, fill_value=0).astype(np.int64))
        return self.projection.validated_native_ids(cropped[None, None].to(self.device),
                                                    source=f"CT {subject}", require_mapped=True)

    def view(self, prepared, subject):
        """One view through SegmentationDRRRuntime.render, as fxr-render calls it
        (fxr/launch/render.py, render_dataset): the native labels validated by the projection,
        the supervised centroids, the collapse map and the native attenuated ids; or, under pose
        fluxray-grid, through the explicit-pose primitives (view_grid)."""
        import torch
        from fxr.models.camera.runtime import scale_rendered_images

        if self.grid:
            return self.view_grid(prepared, subject)
        crop, volume, native, affine = self.cut(prepared, subject)
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
        pose = {"rot": torch.as_tensor(request.rot), "xyz": torch.as_tensor(request.xyz),
                "sdd": request.intrinsics["sdd"][0], "delx": request.intrinsics["delx"][0]}
        row = self.row(crop, point, label_id, pose_record(pose, request.orthographic), factors,
                       crop["ids"])
        return image.float().cpu().numpy(), row

    def view_grid(self, prepared, subject):
        """One of FluXray's raw renders through FleXray's primitives, since its PoseSampler
        (fxr/drr/poses.py) draws presets and ranges and no grid: the isocentre at the volume's
        centre (fxr.drr.compute_isocenter, volume_center), the pose drawn as the blocks engine
        draws it (one torch.randint over the 90), the request with that pose, the fixed distance
        and pixel and a cone beam (fxr.drr.DRRRenderRequest, the intrinsics as sample_request
        lays them out), render_drr with no attenuation factors, and scale_rendered_images."""
        import torch
        from fxr.drr import DRRRenderRequest, compute_isocenter, render_drr
        from fxr.models.camera.runtime import scale_rendered_images

        blocks = self.blocks
        crop, volume, _, affine = self.cut(prepared, subject)
        affine = affine.to(self.device)
        point = compute_isocenter(volume, None, affine, "volume_center")
        pose = self.parts.pose_fluxray_grid(None)
        intrinsics = {"sdd": [pose["sdd"]], "delx": [pose["delx"]], "dely": [pose["delx"]],
                      "x0": [0.0], "y0": [0.0], "height": int(blocks.detector),
                      "width": int(blocks.detector)}
        request = DRRRenderRequest(
            rot=pose["rot"], xyz=pose["xyz"], intrinsics=intrinsics,
            isocenter=point.reshape(1, 3).to(torch.float32), orientation=self.parts.ORIENTATION,
            n_samples=int(blocks.ray_samples), orthographic=False)
        with torch.inference_mode():
            result = render_drr(volume=volume, label=None, affine=affine, request=request)
            image = scale_rendered_images(result.images)[0, 0]
        centre = [float(v) for v in point.reshape(-1)[:3].tolist()]
        row = self.row(crop, centre, None, pose_record(pose, False), None, crop["ids"])
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


def packed_crop(spec, subject):
    """One planned crop as FleXray's packer describes it (crop_z, crop_metadata): the spec, its
    z range and pads, the native ids it holds and their centroids; None for a crop whose labels
    are background alone, which the packer drops; every crop, holding nothing, when no label
    was read."""
    import numpy as np
    from fxr.datasets.ct_crops import crop_metadata, crop_z

    crop = {"spec": spec, "z_start": spec.z_start, "z_stop": spec.z_stop,
            "pad_before": spec.z_pad_before, "pad_after": spec.z_pad_after, "ids": [],
            "centroids": []}
    if subject["label"] is None:
        return crop
    label_crop = crop_z(subject["label"], spec, fill_value=0)
    if not np.any(label_crop != 0):
        return None
    meta = crop_metadata(spec, label_crop, subject_id=subject["id"],
                         source_sample_id=subject["id"])
    crop["ids"] = [int(i) for i in meta["crop_foreground_label_ids"]]
    crop["centroids"] = [tuple(c) for c in meta["fg_centroids_ijk"]]
    return crop


def grid_record():
    """FluXray's grid as RENDER.json records it, from the pure rules."""
    found = rules()
    return {"poses": found.GRID_POSES, "y_mm": list(found.GRID_Y_MM),
            "z_mm": list(found.GRID_Z_MM), "alpha_deg": list(found.GRID_ALPHA_DEG),
            "sdd": found.GRID_SDD_MM, "pixel_mm": found.GRID_PIXEL_MM}


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
    by a run under the same. The blocks record carries the segmenter."""
    found = versions()
    return {"blocks": rules().as_record(blocks), "engine": engine, "salt": salt,
            "flexray": found["flexray"], "nanodrr": found["nanodrr"]}


def earlier_manifest(out, settings):
    """The rows by file and the label records by subject that an earlier run under the same
    settings wrote; none when RENDER.json is missing or names other settings, since the renders
    on disk are then another run's, whatever their names."""
    record = read_json(out / "RENDER.json")
    if not isinstance(record, dict) or record.get("settings") != settings:
        return {}, {}
    manifest = read_json(out / "manifest.json")
    if not isinstance(manifest, dict) or not isinstance(manifest.get("views"), list):
        return {}, {}
    rows = {row["file"]: row for row in manifest["views"]
            if isinstance(row, dict) and "file" in row}
    labels = manifest.get("labels")
    return rows, dict(labels) if isinstance(labels, dict) else {}


def write_manifest(out, settings, rows, labels):
    """manifest.json: the blocks, the engine, the segmenter, FleXray's version, each subject's
    label record and the rows by file name."""
    write_json(out / "manifest.json", {
        "blocks": settings["blocks"], "engine": settings["engine"],
        "segmenter": settings["blocks"]["segmenter"], "flexray": settings["flexray"],
        "labels": {subject: labels[subject] for subject in sorted(labels)},
        "views": sorted(rows.values(), key=lambda row: row["file"])})


def log(text):
    print(f"flexray-render {time.strftime('%H:%M:%S')} {text}", flush=True)


# --- the run --------------------------------------------------------------------------------------

def check_arguments(subjects, salt, device, blocks, engine, roots):
    """The arguments held to what the engines take, the blocks' faults in engine_problems' words
    and a segmenter with no masks folder refused, before anything is written; segmenter none
    reads no mask, so it asks for no folder."""
    found = rules().engine_problems(engine, blocks)
    if found:
        raise rules().RenderBlockError("; ".join(found))
    if subjects < 1:
        raise ValueError("subjects must be at least 1")
    if not isinstance(salt, str) or not salt:
        raise ValueError("salt must be a non-empty string")
    if str(device).split(":")[0] not in ("cpu", "cuda"):
        raise ValueError("device must be cpu or cuda")
    if blocks.segmenter == rules().NO_SEGMENTER:
        return
    root = roots.get(blocks.segmenter)
    if root is None:
        raise ValueError(f"segmenter={blocks.segmenter}: no masks folder given "
                         f"(roots[{blocks.segmenter!r}], --{blocks.segmenter} on the command line)")
    if not Path(root).is_dir():
        raise ValueError(f"segmenter={blocks.segmenter}: its masks folder is not a folder")


def ordered_subjects(found, subject_ids, salt):
    """The subjects to visit, in order: the ids given, each found or passed over, else every
    subject found in the salted order."""
    if subject_ids is None:
        return sorted(found, key=lambda name: rank_key(f"{salt}:subjects", name))
    return [str(subject) for subject in subject_ids]


def load_or_skip(state, subject):
    """The subject read and prepared for its engine, its label record kept, or None after
    recording why it is passed over."""
    started = time.perf_counter()
    folder = state["root"] / subject
    engine = state["engine"]
    try:
        if subject not in state["found"]:
            raise SkipSubject("not found under the CT folder")
        loaded = load_subject(folder, subject, engine.blocks, state["roots"], engine.supervised)
        prepared = engine.prepare(loaded)
        state["labels"][subject] = loaded["record"]
        return prepared
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
    elif subject in state["earlier_labels"]:
        state["labels"][subject] = state["earlier_labels"][subject]
    for f in done:
        state["rows"][f] = state["earlier"][f]
    state["reused"] += len(done)
    return True


def render_subjects(ct_root, out, subjects, salt, device, *, blocks, engine="blocks",
                    subject_ids=None, roots=None):
    """Render blocks.views views of each of the first `subjects` usable CTs under ct_root, in the
    salted order, or of the subject_ids given, into out, by the engine named, the masks under
    roots[blocks.segmenter] (none read under segmenter none); returns what was rendered, the
    subjects kept and the ones passed over with their reasons."""
    roots = {name: Path(path) for name, path in (roots or {}).items() if path is not None}
    check_arguments(subjects, salt, device, blocks, engine, roots)
    started = time.perf_counter()
    # The engine first: one that cannot be built writes nothing.
    built = ENGINE_CLASSES[engine](blocks, device)
    out = Path(out)
    (out / "images").mkdir(parents=True, exist_ok=True)
    settings = render_settings(blocks, engine, salt)
    earlier, earlier_labels = earlier_manifest(out, settings)
    state = {"root": Path(ct_root), "out": out, "salt": salt, "views": blocks.views,
             "settings": settings, "earlier": earlier, "earlier_labels": earlier_labels,
             "rows": {}, "labels": {}, "roots": roots, "skipped": [], "rendered_now": 0,
             "reused": 0, "seconds_loading": 0.0, "seconds_rendering": 0.0, "engine": built}
    # The manifest first, holding only what this run may reuse, then RENDER.json naming this
    # run's settings, so a run cut at any point never leaves rows another run would trust.
    write_manifest(out, settings, state["earlier"], state["earlier_labels"])
    state["found"] = set(find_subjects(ct_root))
    kept = []
    arguments = {"ct_root": str(ct_root), "subjects": subjects, "salt": salt, "device": str(device),
                 "engine": engine, "subject_ids": list(subject_ids) if subject_ids else None,
                 "roots": {name: str(path) for name, path in sorted(roots.items())}}
    write_json(out / "RENDER.json", run_record(state, kept, arguments, started, "running"))
    for subject in ordered_subjects(sorted(state["found"]), subject_ids, salt):
        if len(kept) >= subjects:
            break
        if visit_subject(state, subject):
            kept.append(subject)
            write_manifest(out, settings, state["rows"], state["labels"])
            if len(kept) % 25 == 0:
                log(f"{len(kept)} subjects kept, {state['rendered_now']} rendered now")
    write_manifest(out, settings, state["rows"], state["labels"])
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
        "version": 3,
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


# --- the segment subcommand -----------------------------------------------------------------------

def segment_models():
    """The moosez models the segment subcommand runs: the five whose labels MOOSE.yml stores, in
    schwingnet.segmenters' order."""
    return tuple(schemes().MOOSEZ_MODELS)


def moosez_metadata():
    """Each model's weights folder and release URL, from the copy above, so the plan imports
    nothing of moosez (the fetch row's URLs are the same, by tests/test_flexray_render.py)."""
    return {m: (f, MOOSEZ_RELEASE + z) for m, (f, z) in MOOSEZ_WEIGHTS.items()}


def zip_of(url):
    """The file name a release URL's zip lands under, as the fetch row names it."""
    return url.rsplit("/", 1)[-1]


def moosez_disagreements(metadata):
    """Where moosez's own metadata (moosez/models.py, MODEL_METADATA) names another folder or
    URL than the copy, in words: moosez would download such a model, so the run refuses first.
    Called only where moosez imports."""
    from moosez.constants import KEY_FOLDER_NAME, KEY_URL
    from moosez.models import MODEL_METADATA

    found = []
    for model, (folder, url) in metadata.items():
        entry = MODEL_METADATA.get(model, {})
        theirs = (str(entry.get(KEY_FOLDER_NAME)), str(entry.get(KEY_URL)))
        if theirs != (folder, url):
            found.append(f"{model}: moosez names {theirs[0]} at {theirs[1]}, this tool {folder} "
                         f"at {url}")
    return found


def read_subject_list(path, ct_root):
    """The subjects the segment subcommand works on: render-subjects.json's list under the CT
    folder's name (or its one folder), or a plain list of ids."""
    data = read_json(path)
    if isinstance(data, list):
        return [str(s) for s in data]
    if not isinstance(data, dict) or not data:
        raise SegmentError("the subjects file is not render-subjects.json ({folder: [ids]}) "
                           "or a list of subject ids")
    key = Path(ct_root).name
    if key in data:
        return [str(s) for s in data[key]]
    if len(data) == 1:
        return [str(s) for s in next(iter(data.values()))]
    raise SegmentError(f"the subjects file names the folders {', '.join(sorted(data))} and none "
                       f"is the CT folder's name {key!r}")


def weights_plan(weights, metadata):
    """Each model's zip under --weights, by the file name of its release URL, as the fetch row
    lands it: whether it is there, how many bytes it holds and whether it is a whole zip
    (zipfile.is_zipfile, which reads the central directory at the end), since the fetch lands
    a zip under its final name while it is still downloading and a part cut short stays there."""
    found = {}
    for model, (folder, url) in metadata.items():
        path = Path(weights) / zip_of(url)
        present = path.is_file()
        found[model] = {"zip": path.name, "folder": folder, "present": present,
                        "bytes": path.stat().st_size if present else 0,
                        "whole": present and zipfile.is_zipfile(path)}
    return found


RESEND = "resend fetch moose_weights, which resumes it"


def zip_refusals(weights_found):
    """The model zips not under --weights, and the ones there that are not whole zips, in words,
    each a refusal before any model is unpacked: the weights are fetched by their row and never
    downloaded here, and a resend of the row resumes a part."""
    found = []
    for model, w in weights_found.items():
        if not w["present"]:
            found.append(f"MOOSE's model zip {w['zip']} ({model}) is not under --weights (fetch "
                         "moose_weights first); never downloaded here")
        elif not w["whole"]:
            found.append(f"MOOSE's model zip {w['zip']} ({model}) under --weights is not a whole "
                         f"zip ({w['bytes']} bytes, a part the fetch left): {RESEND}; never "
                         "downloaded here")
    return found


def segment_plan(args):
    """What a segment run would do, decided without moosez: the subjects of the list, what each
    lacks under --out, the zips found under --weights, and the refusals."""
    parts = blocks_tool()
    metadata = moosez_metadata()
    models = segment_models()
    subjects = []
    for subject in read_subject_list(args.subjects, args.ct_root):
        found = parts.locate_moose(subject, args.out)
        missing = [m for m in models if m not in found]
        ct = (Path(args.ct_root) / subject / CT_NAME).is_file()
        action = "done" if not missing else ("run" if ct else "no CT")
        subjects.append({"id": subject, "ct": ct, "found": sorted(found), "missing": missing,
                         "action": action})
    weights = weights_plan(args.weights, metadata)
    return {"segmenter": "moose", "ct_root": str(args.ct_root), "out": str(args.out),
            "weights": str(args.weights), "models": list(models), "weights_found": weights,
            "models_directory": "moosez's own (moosez.system.MODELS_DIRECTORY_PATH), where the "
                                "zips are unpacked when the run starts",
            "refusals": zip_refusals(weights), "subjects": subjects,
            "to_run": sum(s["action"] == "run" for s in subjects),
            "moosez": "importable" if importlib.util.find_spec("moosez") else "absent"}


def check_weights(plan):
    """Every model's zip must be under --weights and whole: a missing one or a part refuses the
    run before moosez is imported, so no model is half-unpacked."""
    if plan["refusals"]:
        raise SegmentError("; ".join(plan["refusals"]))


def safe_members(archive):
    """A zip's members, refused when one would land outside the folder it is unpacked into."""
    for member in archive.namelist():
        path = Path(member)
        if path.is_absolute() or ".." in path.parts:
            raise SegmentError(f"{archive.filename} holds a member outside its folder: {member}")
    return archive.namelist()


def unpack_model(zip_path, models_dir, folder, url):
    """One model's zip unpacked into moosez's models directory as moosez's own download unpacks
    it (moosez/models.py, Model.__download: the members into the base directory, then
    model_version.json naming the URL, which it reads before downloading), so moosez finds the
    model there and fetches nothing; left as it is when its version file already names the
    URL. A zip that is not whole, a part the fetch left or a member it cannot read, is refused
    in words naming the zip and the resend that resumes it, never a traceback that spends the
    job. Returns what was done."""
    home = models_dir / folder
    version = home / MODEL_VERSION_FILE
    if (read_json(version) or {}).get("url") == url:
        return "kept"
    try:
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(models_dir, members=safe_members(archive))
    except zipfile.BadZipFile as error:
        raise SegmentError(f"{zip_path.name} is not a whole zip ({error}): {RESEND}") from error
    if not home.is_dir():
        raise SegmentError(f"{zip_path.name} did not unpack to {folder} under moosez's models "
                           "directory, where moosez looks for it")
    version.write_text(json.dumps({"url": url}) + "\n", encoding="utf-8")
    return "unpacked"


def models_directory():
    """moosez's own models directory, the default of Model.__init__ (moosez/system.py,
    MODELS_DIRECTORY_PATH), made where it is missing."""
    from moosez import system

    models_dir = Path(system.MODELS_DIRECTORY_PATH)
    models_dir.mkdir(parents=True, exist_ok=True)
    return models_dir


def unpack_weights(weights, metadata, models_dir):
    """Every model's zip from --weights unpacked into moosez's models directory; returns what
    was done to each."""
    return {model: unpack_model(Path(weights) / zip_of(url), models_dir, folder, url)
            for model, (folder, url) in metadata.items()}


def dataset_labels(models_dir, folder):
    """The labels of an unpacked model's dataset.json, {value: name} as moosez reads them
    (moosez/models.py, Model.__get_model_data and __get_organ_indices: the first configuration
    folder under the model's, one named trainer__planner__resolution, its dataset.json's
    "labels" of name to value, background left out), with the file's path below the models
    directory; a SegmentError where moosez could not read them either."""
    home = models_dir / folder
    configs = sorted(p for p in home.iterdir()
                     if p.is_dir() and p.name.count("__") == 2 and not p.name.startswith("."))
    if not configs:
        raise SegmentError(f"{folder} holds no configuration folder "
                           "(trainer__planner__resolution) for moosez to read")
    path = configs[0] / "dataset.json"
    data = read_json(path)
    labels = data.get("labels") if isinstance(data, dict) else None
    if not isinstance(labels, dict):
        raise SegmentError(f"{path.relative_to(models_dir)} has no labels for moosez to read")
    try:
        found = {int(value): str(name) for name, value in labels.items() if str(value) != "0"}
    except (TypeError, ValueError) as error:
        raise SegmentError(f"{path.relative_to(models_dir)}: a label's value is no integer "
                           f"({error})") from error
    return found, path.relative_to(models_dir).as_posix()


def label_disagreements(model, labels):
    """Where a model's dataset.json names a value otherwise than this tool's table
    (schwingnet.segmenters.MOOSEZ_MODELS, moosez's README), in words, the names lowercased and
    the four renamed bones read as one name on either side (MOOSEZ_RENAMED); empty when they
    agree, so the relabel tables land every value on the structure moosez labelled."""
    renamed = schemes().MOOSEZ_RENAMED
    theirs = {v: renamed.get(n.lower(), n.lower()) for v, n in labels.items()}
    ours = {v: renamed.get(n, n) for v, n in schemes().MOOSEZ_MODELS[model].items()}
    found = []
    for value in sorted(set(theirs) | set(ours)):
        if theirs.get(value) != ours.get(value):
            found.append(f"{model}: value {value} is {theirs.get(value, 'absent')} in its "
                         f"dataset.json and {ours.get(value, 'absent')} in this tool's table")
    return found


def check_labels(models_dir, metadata):
    """Every unpacked model's dataset.json held equal to this tool's table before any CT runs:
    a model whose labels differ refuses the run in words, since the relabel tables would land
    its values on the wrong structures; returns the record SEGMENT.json keeps of the check."""
    record, problems = {}, []
    for model, (folder, _) in metadata.items():
        labels, path = dataset_labels(models_dir, folder)
        differs = label_disagreements(model, labels)
        problems.extend(differs)
        record[model] = {"dataset_json": path, "values": len(labels), "agrees": not differs}
    if problems:
        raise SegmentError("a model's dataset.json names its labels otherwise than this tool's "
                           "table (schwingnet.segmenters.MOOSEZ_MODELS), so the relabel tables "
                           "would land on the wrong structures: " + "; ".join(problems))
    return record


def segment_one(subject, args, models):
    """moosez on one CT: a link named CT_<id>.nii.gz to the CT inside --out/<subject>/, which
    is also moosez's output folder, so its outputs land there whichever side of its input it
    writes on; the models' files found afterwards, and the ones the locator did not find."""
    from moosez import moose

    home = Path(args.out) / subject
    home.mkdir(parents=True, exist_ok=True)
    name = str(subject).rsplit("/", 1)[-1]
    link = home / f"CT_{name}.nii.gz"
    if not link.exists():
        link.symlink_to((Path(args.ct_root) / subject / CT_NAME).resolve())
    moose(str(link), list(models), str(home), args.device)
    found = blocks_tool().locate_moose(subject, args.out)
    return {"id": subject, "found": sorted(found),
            "not_found": [m for m in models if m not in found]}


def run_segment(plan, args):
    """The segment run after its plan: the zips checked, moosez imported and its metadata held
    equal to the copy, the zips unpacked where moosez looks, each model's dataset.json held
    equal to this tool's table, then each subject that lacks a model's masks; the record
    written to --out/SEGMENT.json."""
    check_weights(plan)
    if plan["moosez"] != "importable":
        raise SegmentError("moosez is not installed here; the plan above says what it would do")
    metadata = moosez_metadata()
    differs = moosez_disagreements(metadata)
    if differs:
        raise SegmentError("moosez's own metadata differs from this tool's copy, so it would "
                           "download: " + "; ".join(differs))
    models_dir = models_directory()
    record = {"plan": plan, "weights": unpack_weights(args.weights, metadata, models_dir),
              "labels": check_labels(models_dir, metadata), "done": []}
    for entry in plan["subjects"]:
        if entry["action"] != "run":
            continue
        record["done"].append(segment_one(entry["id"], args, entry["missing"]))
        write_json(Path(args.out) / "SEGMENT.json", record)
    write_json(Path(args.out) / "SEGMENT.json", record)
    return record


def summary_line(plan, record, out):
    """The one plain line a run ends with, after the JSON: the subjects run, the models, the
    model files the locator found and did not find afterwards, and where they were written.
    grid/bench.sbatch's report takes the last lines of the job's stdout, so this line is what a
    reader sees first, and tests/test_gate.py's stand-in prints the same shape."""
    done = record["done"]
    found = sum(len(d["found"]) for d in done)
    not_found = sum(len(d["not_found"]) for d in done)
    return (f"segment: {len(done)} subjects run, {len(plan['models'])} models, {found} files "
            f"found, {not_found} not found, written under {out}")


def segment_main(argv):
    parser = argparse.ArgumentParser(prog="flexray_render.py segment",
                                     description="MOOSE's masks for the replication's CTs")
    parser.add_argument("--segmenter", required=True)
    parser.add_argument("--ct-root", required=True, type=Path)
    parser.add_argument("--subjects", required=True, type=Path,
                        help="render-subjects.json ({folder: [ids]}) or a list of ids")
    parser.add_argument("--weights", required=True, type=Path,
                        help="the folder the fetch row landed moosez's model zips in "
                             "(moose_weights/raw)")
    parser.add_argument("--out", required=True, type=Path, help="the moose masks folder")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--plan", action="store_true", help="print the plan and stop")
    args = parser.parse_args(argv)
    try:
        if args.segmenter == "spineps":
            raise SegmentError(SPINEPS_REFUSAL)
        problems = schemes().scheme_problems(args.segmenter)
        if problems:
            raise SegmentError("; ".join(problems))
        plan = segment_plan(args)
        print(json.dumps(plan, indent=1, sort_keys=True))
        if args.plan:
            return 0
        record = run_segment(plan, args)
    except SegmentError as error:
        print(f"segment: refused: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"done": record["done"]}, indent=1, sort_keys=True))
    print(summary_line(plan, record, args.out))
    return 0


# --- the command line -----------------------------------------------------------------------------

def render_main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--ct-root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--subjects", type=int, default=250)
    parser.add_argument("--salt", required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--engine", default="blocks", choices=rules().ENGINES)
    parser.add_argument("--blocks", action="append", default=[], metavar="KEY=VALUE",
                        help="a render block, repeatable; none is FleXray's released recipe on "
                             "SPINEPS masks; segmenter=none reads no masks, with a recipe that "
                             "reads no labels")
    parser.add_argument("--subject", action="append", default=None, metavar="ID",
                        help="a subject to render, repeatable; none takes the salted order")
    parser.add_argument("--spineps", type=Path, default=None, help="the SPINEPS masks folder")
    parser.add_argument("--moose", type=Path, default=None, help="the MOOSE masks folder")
    args = parser.parse_args(argv)
    blocks = rules().parse(args.blocks)
    roots = {name: path for name, path in (("spineps", args.spineps), ("moose", args.moose))
             if path is not None}
    done = render_subjects(args.ct_root, args.out, args.subjects, args.salt, args.device,
                           blocks=blocks, engine=args.engine,
                           subject_ids=tuple(args.subject) if args.subject else None, roots=roots)
    return 0 if done["subjects"] else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "segment":
        return segment_main(argv[1:])
    if argv and argv[0] == "render":
        argv = argv[1:]
    return render_main(argv)


if __name__ == "__main__":
    sys.exit(main())
