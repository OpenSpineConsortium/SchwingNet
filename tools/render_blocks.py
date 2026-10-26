"""The torch side of the render blocks: one function per named choice of schwingnet.render_blocks,
in a table NAMES keyed as its CHOICES are, each saying what FleXray does and where in its source
(flexray 1.0.2 from pip, src/fxr/...), so the blocks engine of tools/flexray_render.py is read
beside FleXray's own runtime step by step and tests/test_flexray_render.py holds the two tables
equal. The segmenter part is the one that reads files: label_spineps and label_moose each find a
subject's existing masks under that scheme's folder (locate_spineps, locate_moose) and write one
int16 label volume of MOOSE's stored ids through schwingnet.segmenters' maps, with a record of
what the masks carried, so both engines read the labels as FleXray's own code reads MOOSE's.

A view is made in the order FleXray's runtime draws (fxr/models/camera/runtime.py,
SegmentationDRRRuntime.render, then sample_request; then fxr/drr/rendering.py, render_drr): the
subject is prepared once (hu_window, then air_clamp, then crop plans the crops and crop_sampler
weighs them); per view, the crop is drawn, isocentre draws the target, pose draws the pixel
spacing, the distance and the camera (or, under fluxray-grid, one of FluXray's 90 fixed poses),
projection the beam, attenuation the gate and the factors, render_drr renders, scale scales and
edit edits. The draws come from Python's random and torch's
global generator, both seeded by the caller for the view, as FleXray's runtime draws from the same
two; so two configurations that differ only in attenuation, the last draw, share the crop, the
isocentre and the pose of every view.

Imported by path (tools/ is never on sys.path, since tools/profile.py would shadow the standard
library's profile, which torch imports); it needs numpy, torch and fxr.drr, and nothing of
fxr.models, whose camera package imports kornia, a training dependency a render-only environment
need not hold.
"""

import functools
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [entry for entry in sys.path if Path(entry or ".").resolve() != ROOT / "tools"]
for folder in (ROOT / "vendor" / "beethoven-qa" / "src", ROOT / "src"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from fxr.drr import (  # noqa: E402
    DRRRenderRequest,
    PoseSampler,
    compute_isocenter,
    render_drr,
    sample_attenuation,
    sample_isocenters_from_centroids,
)

from schwingnet import render_blocks as rules  # noqa: E402
from schwingnet import segmenters  # noqa: E402

AIR_HU = -1000.0
HU_WINDOW = (-1000.0, 2000.0)
AIR_CLAMP_HU = -900.0
# The MOOSE profile of fxr/configs/training/base.yml: drr_model.default merged with
# drr_model.datasets.MOOSE, as fxr.models.camera.config.resolve_ct_profiles merges them.
MOOSE_POSE = {
    "rot_range": {"alpha": [-180.0, 180.0], "beta": [-30.0, 30.0], "gamma": [0.0, 0.0]},
    "xyz_range": {"x": [-100.0, 100.0], "y": [500.0, 900.0], "z": [-100.0, 100.0]},
}
SDD_RANGE = (1150.0, 1250.0)
DELX_RANGE = (1.25, 2.25)
ORTHOGRAPHIC_SHARE = 0.1
ORIENTATION = "AP"
ATTENUATION_PROBABILITY = 0.5
ATTENUATION_RANGE = (0.1, 4.0)
ATTENUATION_DISTRIBUTION = {"type": "lognormal", "mode": 1.0, "sigma": 1.0}
# MOOSE's stored ids of vertebra_c1 to vertebra_l6 (fxr/configs/datasets/MOOSE.yml): what the
# isocentre choice "vertebra" aims at, L6 among them since a production render on SPINEPS masks
# may aim at one, though FleXray's protocol drops it (schwingnet.segmenters.MOOSE_DROPPED).
VERTEBRA_IDS = frozenset(i for i, n in segmenters.MOOSE_STORED.items() if n.startswith("vertebra_"))
# The file a SPINEPS run writes for the vertebrae (tools/chain_stats.py reads the same name), and
# the word in a moosez output's path that says which of its models wrote it.
SPINEPS_MASK = "*_seg-vert_msk.nii*"
MOOSE_REGIONS = {
    "clin_ct_organs": "organs",
    "clin_ct_cardiac": "cardiac",
    "clin_ct_peripheral_bones": "peripheral",
    "clin_ct_ribs": "ribs",
    "clin_ct_vertebrae": "vertebrae",
}
# How far a mask's voxel-to-world affine may differ from the CT's, in mm, and still be the CT's
# grid: a mask SPINEPS or moosez wrote from the CT carries the CT's affine to float32, so a
# difference above this is another placement, and its voxels would land on the wrong anatomy.
AFFINE_TOLERANCE_MM = 1e-3


class MaskProblem(Exception):
    """A subject whose masks cannot give a label volume, with the reason the render records."""


# --- the volume, once a subject -------------------------------------------------------------------

def hu_window_flexray(volume):
    """FleXray's pack clips the CT to [-1000, 2000] HU and stores it as float16
    (fxr/datasets/preprocessing.py, CTPreprocessing.apply, the hu_window of its released crops)."""
    return np.ascontiguousarray(np.clip(volume, *HU_WINDOW).astype(np.float16))


def hu_window_none(volume):
    """The CT as the scanner gave it, in float32, without the clip of
    fxr/datasets/preprocessing.py's CTPreprocessing.apply."""
    return np.ascontiguousarray(np.asarray(volume, dtype=np.float32))


def air_clamp_flexray(volume):
    """FleXray's CT loader reads a stored crop as float32, clamps it from below at -1000 HU and
    sets every voxel at or below -900 HU back to -1000, air (fxr/datasets/runtime.py,
    _apply_ct_hu_bounds, called by CTTrainingDataset.__getitem__ with hu_min -1000 and the
    air_clamp_hu -900 of every CT source in fxr/configs/training/base.yml)."""
    out = np.array(volume, dtype=np.float32)
    air = out <= AIR_CLAMP_HU
    np.maximum(out, AIR_HU, out=out)
    out[air] = AIR_HU
    return np.ascontiguousarray(out)


def air_clamp_none(volume):
    """The volume as float32, air as the scanner gave it, without the clamp of
    fxr/datasets/runtime.py's _apply_ct_hu_bounds; nanodrr's own conversion to attenuation still
    clamps HU from below at -1000 (nanodrr/data/preprocess.py, hu_to_mu)."""
    return np.ascontiguousarray(np.asarray(volume, dtype=np.float32))


def crop_flexray_axial(depth):
    """FleXray's packer cuts a CT along its last voxel axis into 256-slice crops that cover it,
    the first and last touching the ends, neighbours at most 128 slices apart, the slice plane
    the volume's own, a shorter volume one crop padded with air on both sides
    (fxr/datasets/ct_crops.py, plan_z_crops at the max_overlap 0.5 its released packs were made
    with, and crop_z); the plan is schwingnet.render_blocks.plan_crops, held equal to it. Which
    crops are dropped for holding no structure is crop_content's to say."""
    return rules.plan_crops(depth, rules.CROP_OVERLAP["flexray-axial"])


def crop_flexray_axial_min(depth):
    """The fewest such crops, neighbours up to 256 slices apart (fxr/datasets/ct_crops.py,
    plan_z_crops at its default max_overlap 0)."""
    return rules.plan_crops(depth, rules.CROP_OVERLAP["flexray-axial-min"])


def crop_whole(depth):
    """The whole volume as one crop, with no pad, in place of the 256-slice crops of
    fxr/datasets/ct_crops.py's plan_z_crops."""
    return ((0, depth, 0, 0),)


def crop_sampler_inverse_label_frequency(crops, lut):
    """FleXray draws training crops with replacement by tempered inverse label frequency: each
    model class a crop holds contributes (N / n_c) ** 0.5, the crop takes the largest, a crop
    with no supervised class weighs 0, the weights scaled to average 1
    (fxr/datasets/sampling.py, inverse_label_frequency_weights, at the tau 0.5 and
    class_aggregation max of base.yml; the draw is torch's WeightedRandomSampler over the whole
    corpus in fxr/experiment/segmentation.py, _weighted_sampler). Here the weights are over one
    CT's crops, by schwingnet.render_blocks.crop_weights, held equal to FleXray's; the native ids
    of each crop become model classes through the protocol's lookup table, as FleXray's do."""
    classes = [frozenset(int(lut[i]) for i in crop["ids"] if int(lut[i]) > 0) for crop in crops]
    return torch.tensor(rules.crop_weights(classes), dtype=torch.float64)


def crop_sampler_uniform(crops, lut):
    """Every crop alike, FleXray's sample_weighting scheme uniform (fxr/datasets/sampling.py,
    SampleWeightingSpec.parse, the scheme base.yml does not choose, under which
    fxr/experiment/segmentation.py shuffles the crops with no weights)."""
    return torch.ones(len(crops), dtype=torch.float64)


# --- the draws, once a view -----------------------------------------------------------------------

def draw_crop(weights):
    """One crop by its weight, the one draw torch's WeightedRandomSampler makes: torch.multinomial
    with replacement on the global generator, as fxr/experiment/segmentation.py's _weighted_sampler
    builds it (without replacement torch draws by another algorithm and the index would differ
    under the same seed)."""
    return int(torch.multinomial(weights.double(), 1, replacement=True).item())


def isocentre_random_label(crop, affine, volume, supervised):
    """FleXray's MOOSE profile aims each view at the centroid of one structure the crop holds,
    drawn without replacement over the crop's supervised foreground centroids, the structures
    its protocol keeps and not the ones it drops, L6 and the thirteenth ribs among them
    (fxr/drr/isocenter.py, sample_isocenters_from_centroids with replacement false, called by
    SegmentationDRRRuntime._resolve_isocenter for isocenter_cfg random_label over the centroids
    fxr-render keeps, TrainingLabelProjection's foreground; the volume's centre when the crop
    holds none)."""
    held = {i: c for i, c in crop["centroids"].items() if i in supervised}
    return aim(held, affine, volume)


def isocentre_vertebra(crop, affine, volume, supervised):
    """The same draw (fxr/drr/isocenter.py, sample_isocenters_from_centroids) over the vertebrae
    alone, MOOSE's vertebra_c1 to vertebra_l6, whether or not FleXray supervises them; the
    volume's centre when the crop holds none."""
    return aim({i: c for i, c in crop["centroids"].items() if i in VERTEBRA_IDS}, affine, volume)


def isocentre_volume_centre(crop, affine, volume, supervised):
    """The crop's centre in world coordinates, FleXray's volume_center scheme
    (fxr/drr/isocenter.py, compute_isocenter), which draws nothing; the raw FluXray renders'
    choice."""
    point = compute_isocenter(volume, None, affine, "volume_center")
    return [float(v) for v in point.tolist()], None


def aim(centroids, affine, volume):
    """The target drawn from the centroids by native id, as FleXray draws it (one call of
    sample_isocenters_from_centroids over the ids in ascending order, as its collate orders
    them), with the id whose centroid it is; the volume's centre when there is none."""
    if not centroids:
        return isocentre_volume_centre(None, affine, volume, ())
    ids = sorted(centroids)
    points = torch.tensor([centroids[i] for i in ids], dtype=torch.float32)
    chosen = sample_isocenters_from_centroids(points, affine, 1, replacement=False)[0]
    return [float(v) for v in chosen.tolist()], ids[nearest_centroid(chosen, points, affine)]


def nearest_centroid(point, points_ijk, affine):
    """Which centroid a world point is, by the shortest distance to the centroids in world
    coordinates (the same affine product fxr/drr/isocenter.py's _ijk_to_world takes)."""
    affine = torch.as_tensor(affine, dtype=torch.float32).cpu()
    ones = torch.ones(points_ijk.shape[0], 1, dtype=torch.float32)
    world = (affine @ torch.cat([points_ijk.float(), ones], dim=1).T).T[:, :3]
    return int(torch.argmin(((world - point.float().cpu()) ** 2).sum(dim=1)).item())


def pose_sampler():
    """FleXray's random pose sampler at MOOSE's ranges, drawing on torch's global generator
    (fxr/drr/poses.py, PoseSampler("random") with sample_params and no seed, as
    SegmentationDRRRuntime.__init__ builds it)."""
    return PoseSampler("random", sample_params=MOOSE_POSE)


def pose_flexray_moose(sampler):
    """FleXray's runtime draws, for a view, the detector pixel spacing delx uniformly in 1.25 to
    2.25 mm (dely following it), the source-to-detector distance uniformly in 1150 to 1250 mm,
    the principal point fixed at 0, then the camera: ZXY Euler angles alpha in -180 to 180, beta
    in -30 to 30 and gamma 0 degrees, and a translation from the isocentre of x in -100 to 100,
    y in 500 to 900 and z in -100 to 100 mm, y and the distance sorted so the source stays
    inside the distance, the sorted distance written back (the MOOSE profile of base.yml;
    fxr/models/camera/runtime.py, _sample_intrinsics then sample_request, through
    fxr/drr/poses.py, RandomPoseGenerator.generate_poses on torch's global generator). The
    spacing and the distance come from Python's random, the camera from torch's."""
    delx = random.uniform(*DELX_RANGE)
    sdd = torch.tensor([random.uniform(*SDD_RANGE)], dtype=torch.float32)
    rot, xyz = sampler.sample(num_poses=1, sampled_sdd=sdd)
    return {"rot": rot, "xyz": xyz, "sdd": float(sdd[0]), "delx": float(delx), "grid": None}


def pose_fluxray_grid(sampler):
    """One of the 90 fixed poses FluXray's raw renders were made from, drawn uniformly on torch's
    global generator (one torch.randint, as a training draw of FluXray takes one of a subject's
    poses): ZXY Euler angles (alpha, 0, 0) and a translation (0, y, z) from the isocentre in the
    units fxr/drr/rendering.py's DRRRenderRequest takes (degrees and mm), the detector 1250 mm
    from the source with 0.6 mm pixels, fixed by the choice (schwingnet.render_blocks.grid_pose,
    from the paper's enhanced-DRR appendix; FleXray's own PoseSampler, fxr/drr/poses.py, knows
    fixed presets and random ranges and no such grid, so the sampler is not used). The record
    carries the pose's index in the grid."""
    index = int(torch.randint(rules.GRID_POSES, (1,)).item())
    alpha, y, z = rules.grid_pose(index)
    return {"rot": torch.tensor([[alpha, 0.0, 0.0]], dtype=torch.float32),
            "xyz": torch.tensor([[0.0, y, z]], dtype=torch.float32),
            "sdd": rules.GRID_SDD_MM, "delx": rules.GRID_PIXEL_MM, "grid": index}


def projection_flexray_mix():
    """Orthographic with probability 0.1, else a cone beam (projection_mode cone 0.9 and
    orthographic 0.1 in the MOOSE profile; fxr/models/camera/runtime.py, sample_request,
    random.random() < ortho_prob)."""
    return random.random() < ORTHOGRAPHIC_SHARE


def projection_cone():
    """A cone beam every time, drawing nothing. FleXray's sample_request
    (fxr/models/camera/runtime.py) draws random.random() < ortho_prob whatever the share, so under
    this choice the Python draws after it, the attenuation gate's, come one earlier than under
    FleXray's own recipe."""
    return False


def attenuation_flexray_lognormal(supervised_ids, device):
    """FleXray's runtime opens the attenuation randomisation with probability 0.5 a render
    (random.random() < attenuation_cfg.prob, fxr/models/camera/runtime.py,
    SegmentationDRRRuntime.render) and, when open, has render_drr draw one factor for every
    supervised native label, present in the crop or not, from a lognormal of mode 1 and sigma 1
    kept within 0.1 to 4, and multiply each label's attenuation by its factor
    (fxr/drr/subjects.py, subject_from_tensors and sample_attenuation; the ids are the ones
    fxr-render passes, TrainingLabelProjection.native_foreground_label_ids). Returns the
    keywords render_drr takes and the factors by label, drawn ahead from the generator's state
    and the state put back, so that render_drr draws the same and the record names what it
    applied; ({}, None) when the gate is shut."""
    if not random.random() < ATTENUATION_PROBABILITY:
        return {}, None
    ids = sorted({int(i) for i in supervised_ids if int(i) > 0})
    with torch.random.fork_rng(devices=cuda_devices(device)):
        factors = sample_attenuation(
            ATTENUATION_RANGE, len(ids), device, torch.float32, ATTENUATION_DISTRIBUTION)
    keywords = {"attenuation": ATTENUATION_RANGE, "attenuated_label_ids": ids,
                "do_per_label_attenuation": True, "attenuation_dist": ATTENUATION_DISTRIBUTION}
    return keywords, dict(zip(ids, (float(f) for f in factors.tolist()), strict=True))


def attenuation_off(supervised_ids, device):
    """The physical render: no gate, no factor, nothing drawn, FleXray's attenuation_cfg at prob 0
    (fxr/models/camera/runtime.py, SegmentationDRRRuntime.render, whose gate then never opens)."""
    return {}, None


def scale_minmax(images, eps=1e-6):
    """FleXray scales each rendered view to 0 to 1 by its own minimum and maximum, NaN and the
    infinities set to 0 first and a range under 1e-6 widened to it, the scaling training applies
    before augmentation and fxr-render writes (fxr/models/camera/runtime.py,
    scale_rendered_images). The same arithmetic is written here, since that module imports
    kornia, which a render-only environment need not hold; tests/test_flexray_render.py holds the
    two equal where it imports."""
    finite = torch.nan_to_num(images, nan=0.0, posinf=0.0, neginf=0.0)
    dims = tuple(range(1, finite.ndim))
    low = finite.amin(dim=dims, keepdim=True)
    high = finite.amax(dim=dims, keepdim=True)
    return (finite - low) / (high - low).clamp_min(float(eps))


def edit_none(image):
    """The render as it is, what fxr-render writes (fxr/launch/render.py, render_dataset);
    FleXray's FLUX.2 [klein] edit is not in its code."""
    return image


# --- the labels, once a subject ------------------------------------------------------------------

def names_subject(stem, subject):
    """Whether a mask's stem names the subject: the id itself, or the id between separators or at
    either end after one (sub-s0011, s0011_ct); a nested subject (batch/s0002) by its last part."""
    name = str(subject).rsplit("/", 1)[-1]
    if stem == name:
        return True
    return re.search(r"(?:^|[-_])" + re.escape(name) + r"(?:[-_]|$)", stem) is not None


@functools.lru_cache(maxsize=8)
def spineps_index(root):
    """Every SPINEPS vertebra mask under a folder, as (stem before _seg-vert, path), sorted by
    path, read once a root since the data root's spineps folder holds thousands."""
    found = []
    for path in sorted(Path(root).rglob(SPINEPS_MASK)):
        if path.is_file():
            found.append((path.name.split("_seg-vert")[0], path))
    return tuple(found)


@functools.lru_cache(maxsize=8)
def moose_index(root):
    """Every NIfTI file under a MOOSE masks folder, sorted, read once a root: the fallback of
    locate_moose for a subject with no folder of its own."""
    return tuple(sorted(p for p in Path(root).rglob("*.nii*") if p.is_file()))


def mask_grid(path):
    """A volume's grid from its header alone: the array shape, trailing axes of length one
    dropped as read_values drops them, and the voxel-to-world affine as float64, so a mask on
    another grid, of another shape or placed elsewhere, is told apart without reading it. The
    CT's grid is read the same way, once a subject (tools/flexray_render.py, header_grid)."""
    import nibabel

    image = nibabel.load(str(path))
    shape = tuple(int(n) for n in image.shape)
    while len(shape) > 3 and shape[-1] == 1:
        shape = shape[:-1]
    return shape, np.asarray(image.affine, dtype=np.float64)


def grid_problem(found, grid):
    """Why a volume's grid (shape, affine) is not the CT's, in two words, or None when it is:
    the shape first, then the affine within AFFINE_TOLERANCE_MM, since a mask of the CT's shape
    placed elsewhere in the world would relabel the CT's voxels onto the wrong anatomy."""
    shape, affine = found
    ct_shape, ct_affine = grid
    if tuple(shape) != tuple(ct_shape):
        return "another shape"
    if not np.allclose(affine, ct_affine, rtol=0.0, atol=AFFINE_TOLERANCE_MM):
        return "another affine"
    return None


def on_grid(paths, grid):
    """The masks among paths that lie on the CT's grid (shape, affine), and the ones that do
    not, each named with its reason ("<name>: another shape" or "<name>: another affine"),
    which are skipped; every path when no grid is given, as the subject listing of
    find_subjects asks before any CT is read."""
    if grid is None:
        return list(paths), []
    kept, skipped = [], []
    for path in paths:
        problem = grid_problem(mask_grid(path), grid)
        if problem is None:
            kept.append(path)
        else:
            skipped.append(f"{path.name}: {problem}")
    return kept, skipped


def spineps_matches(subject, root):
    """Every SPINEPS mask under root whose name before _seg-vert names the subject
    (names_subject), in sorted order; the folder's layout is not recorded, so the whole folder
    is walked once and indexed."""
    if root is None:
        return []
    return [path for stem, path in spineps_index(str(root)) if names_subject(stem, subject)]


def locate_spineps(subject, root, grid=None):
    """The subject's SPINEPS mask under root: the first, in sorted order, of the files
    *_seg-vert_msk.nii* whose name before _seg-vert names the subject and, when the CT's grid
    (shape, affine) is given, whose header is on the CT's grid, a mask of another shape or
    another affine skipped (brief: the spineps folder is shared by several CT corpora, so a
    name alone may name another CT); None when there is none."""
    kept, _ = on_grid(spineps_matches(subject, root), grid)
    return kept[0] if kept else None


def ct_link(path, subject):
    """Whether a file is the CT the segment subcommand links beside moosez's outputs as
    CT_<id>.nii.gz (tools/flexray_render.py, segment_one), or any symlink, which no moosez
    output is: such a file is never a candidate, so the record's unplaced names moosez's own
    files alone."""
    name = str(subject).rsplit("/", 1)[-1]
    return path.is_symlink() or path.name == f"CT_{name}.nii.gz"


def moose_candidates(subject, root):
    """The NIfTI files that may be the subject's moosez outputs, each with its path below the
    folder the region word is read in: the files under root/<subject>/, the folder the segment
    subcommand gives moosez as its output and its input's home, below that folder; or, where
    that folder is missing, the files under root whose name holds the subject's id, below root.
    Below the subject's folder, so a region word in the subject's own id matches nothing; the
    CT link and any symlink left out (ct_link)."""
    home = Path(root) / str(subject)
    if home.is_dir():
        return [(p, p.relative_to(home)) for p in sorted(home.rglob("*.nii*"))
                if p.is_file() and not ct_link(p, subject)]
    return [(p, p.relative_to(root)) for p in moose_index(str(root))
            if names_subject(p.name.split(".")[0], subject) and not ct_link(p, subject)]


def regions_in(text, subject):
    """The models whose region word occurs in a path's text, the subject's own name taken out
    first so an id that holds a region word (ribs_case1) names no model."""
    text = text.lower().replace(str(subject).rsplit("/", 1)[-1].lower(), "")
    return [model for model, region in MOOSE_REGIONS.items() if region in text]


def model_of(below, subject):
    """The model a moosez output below the subject's folder belongs to: the one region word in
    its file name (moosez's multilabel files carry the model's region, clin_CT_<region>_...),
    else the one region word in the folders above it; None where the path names no region or
    more than one, since the CLI's output folder is named after every model of one run
    (moosez-<models>-<stamp>), so a folder with several region words decides nothing."""
    for text in (below.name, below.parent.as_posix()):
        models = regions_in(text, subject)
        if len(models) == 1:
            return models[0]
        if models:
            return None
    return None


def by_region(candidates, grid, subject):
    """Each model's file among the candidates, {model: path} in MOOSE_REGIONS' order: a file is
    a model's by model_of, the first in sorted order that lies on the CT's grid when the grid
    (shape, affine) is given; with the files on another grid, each named with its reason, and
    the names of the ones that name no model or more than one (unplaced), which the record
    keeps so a layout this reader does not know is seen and not silently dropped."""
    paths = {path: below for path, below in candidates}
    kept, skipped = on_grid(list(paths), grid)
    found, unplaced = {}, []
    for path in kept:
        model = model_of(paths[path], subject)
        if model is None:
            unplaced.append(path.name)
        elif model not in found:
            found[model] = path
    ordered = {model: found[model] for model in MOOSE_REGIONS if model in found}
    return ordered, skipped, unplaced


def locate_moose(subject, root, grid=None):
    """The subject's moosez outputs under root, one file a model, {model: path}, from
    moose_candidates by region (by_region). moosez's source (3.2.2) names its files by the
    model's region either way: its library entry moose() writes each model's multilabel file
    straight into the output_dir it is given, or beside its input when given none, as
    <prefix>segmentation_<input stem>.nii.gz, the prefix <imaging type>_<modality>_<region>_
    (moosez/__init__.py, moose: f"{model.multilabel_prefix}segmentation_{file_name}.nii.gz",
    the prefix from moosez/models.py, Model.multilabel_prefix, so clin_CT_vertebrae_ for
    clin_ct_vertebrae, and the stem the input's name before .nii, moosez/file_utilities.py,
    get_nifti_file_stem), reoriented back to the input's orientation code; its command line
    writes the same names under <subject>/moosez-<stamp>/segmentations/ (moose_subject,
    file_utilities.moose_folder_structure). So the match is by the one region word in the
    file's name, else in the folders above it, below the subject's folder; a file on another
    grid is skipped when the CT's grid (shape, affine) is given. Empty when there is none."""
    if root is None:
        return {}
    found, _, _ = by_region(moose_candidates(subject, root), grid, subject)
    return found


def read_values(path, grid):
    """A mask's values as int32 on the CT's grid (trailing axes of length one dropped, as fxr's
    NIfTI loader drops them); a mask on another grid, by its shape or by its affine
    (grid_problem), is a MaskProblem."""
    import nibabel

    image = nibabel.load(str(path))
    array = np.asarray(image.dataobj)
    while array.ndim > 3 and array.shape[-1] == 1:
        array = array[..., 0]
    problem = grid_problem((array.shape, np.asarray(image.affine, dtype=np.float64)), grid)
    if problem:
        raise MaskProblem(f"{path.name} is on another grid than the CT ({problem})")
    return np.rint(array).astype(np.int32)


def grid_note(skipped):
    """The tail of a reason naming the masks skipped for lying on another grid, each with its
    reason, or nothing."""
    return f" on the CT's grid ({'; '.join(skipped)})" if skipped else ""


def label_record(scheme, files, label, skipped, reachable):
    """What a label volume holds, as the manifest records it: the scheme, the files read (names
    only, keyed as they were written, a later one winning where two overlap, which precedence
    repeats as a list) and the ones skipped for lying on another grid, each named with its
    reason, another shape or another affine (on_grid), the MOOSE ids present
    with their names, the names present that FleXray's protocol drops (vertebra_l6, the
    thirteenth ribs), which its remap drops at render time (fxr/datasets/remap.py,
    compile_training_label_remap_by_name), and absent, the names FleXray supervises that the
    files read could have carried (reachable, the ids their relabel tables land on) and did
    not, in MOOSE's id order, so a reader tells a structure the masks lack from one no file
    could hold. unsupervised, models_missing and unplaced are filled by the caller."""
    present = [int(i) for i in np.unique(label) if i != 0]
    names = {str(i): segmenters.MOOSE_STORED[i] for i in present}
    dropped = [n for n in names.values() if n in segmenters.MOOSE_DROPPED]
    absent = [segmenters.MOOSE_STORED[i] for i in sorted(set(reachable) - set(present))
              if segmenters.MOOSE_STORED[i] not in segmenters.MOOSE_DROPPED]
    return {"scheme": scheme, "files": files, "precedence": list(files), "skipped": list(skipped),
            "labels": names, "dropped": dropped, "absent": absent, "unsupervised": {},
            "models_missing": [], "unplaced": []}


def relabel(values, table, label):
    """Write each raw value's MOOSE stored id into the label volume where the mask holds it;
    returns the raw values the table has no id for, which stay out of the volume, a negative
    one among them, since a mask holds no negative structure."""
    outside = []
    for value in (int(v) for v in np.unique(values) if v != 0):
        if value in table:
            label[values == value] = table[value]
        else:
            outside.append(value)
    return outside


def label_spineps(subject, grid, roots):
    """The subject's SPINEPS mask (the VerSe alphabet, schwingnet.segmenters.VERSE) on the CT's
    grid (shape, affine) relabelled into MOOSE's stored ids (segmenters.to_moose_ids), which
    FleXray's own code reads (fxr/experiment/label_projection.py, TrainingLabelProjection over
    the dataset's stored_labels): L1 to L5 and L6 to vertebra_l1 to vertebra_l6, the sacrum to
    sacrum; T13 and the coccyx have no MOOSE id, so they are left out of the volume and
    recorded as unsupervised, as is any value outside the alphabet. One int16 volume and its
    record."""
    kept, skipped = on_grid(spineps_matches(subject, roots.get("spineps")), grid)
    if not kept:
        raise MaskProblem("no SPINEPS mask found under its folder" + grid_note(skipped))
    values = read_values(kept[0], grid)
    label = np.zeros(grid[0], dtype=np.int16)
    table = segmenters.to_moose_ids("spineps")
    outside = relabel(values, table, label)
    names = segmenters.unsupervised_in("spineps")
    record = label_record("spineps", {"spineps": kept[0].name}, label, skipped, table.values())
    record["unsupervised"] = {str(v): names.get(v, "outside the VerSe alphabet") for v in outside}
    return label, record


def label_moose(subject, grid, roots):
    """The subject's moosez outputs on the CT's grid (shape, affine) merged into one volume of
    MOOSE's stored ids, as FleXray's own MOOSE dataset was labelled (its CTs were run through
    moosez; the volume is what fxr/experiment/label_projection.py's TrainingLabelProjection
    reads): each model's file in the order of segmenters.MOOSEZ_MODELS, soft tissue first and
    the vertebrae last so a bone wins where two models overlap, its values to stored ids by
    segmenters.moosez_to_moose_ids; a value MOOSE never stored (the organs model's trachea) or
    outside the model's table is left out and recorded as unsupervised; a missing model's file
    is recorded, and at least one must be there (the subject listing of tools/flexray_render.py
    asks for all five, so a render on fewer is one the caller named). One int16 volume and its
    record."""
    root = roots.get("moose")
    candidates = moose_candidates(subject, root) if root else []
    found, skipped, unplaced = by_region(candidates, grid, subject)
    if not found:
        raise MaskProblem("no MOOSE masks found under its folder" + grid_note(skipped))
    label = np.zeros(grid[0], dtype=np.int16)
    unsupervised, missing, reachable = {}, [], set()
    for model, names in segmenters.MOOSEZ_MODELS.items():
        if model not in found:
            missing.append(model)
            continue
        table = segmenters.moosez_to_moose_ids(model)
        reachable |= set(table.values())
        for value in relabel(read_values(found[model], grid), table, label):
            unsupervised[f"{model}:{value}"] = names.get(value, "outside the model's table")
    files = {m: found[m].name for m in segmenters.MOOSEZ_MODELS if m in found}
    record = label_record("moose", files, label, skipped, reachable)
    record.update(unsupervised=unsupervised, models_missing=missing, unplaced=unplaced)
    return label, record


NAMES = {
    "hu_window": {"flexray": hu_window_flexray, "none": hu_window_none},
    "air_clamp": {"flexray": air_clamp_flexray, "none": air_clamp_none},
    "crop": {"flexray-axial": crop_flexray_axial, "flexray-axial-min": crop_flexray_axial_min,
             "whole": crop_whole},
    "crop_sampler": {
        "inverse-label-frequency": crop_sampler_inverse_label_frequency,
        "uniform": crop_sampler_uniform,
    },
    "pose": {"flexray-moose": pose_flexray_moose, "fluxray-grid": pose_fluxray_grid},
    "isocentre": {
        "random-label": isocentre_random_label,
        "vertebra": isocentre_vertebra,
        "volume-centre": isocentre_volume_centre,
    },
    "projection": {"flexray-mix": projection_flexray_mix, "cone": projection_cone},
    "attenuation": {"flexray-lognormal": attenuation_flexray_lognormal, "off": attenuation_off},
    "scale": {"minmax": scale_minmax},
    "edit": {"none": edit_none},
    "segmenter": {"spineps": label_spineps, "moose": label_moose},
}


# --- the helpers the engine shares ----------------------------------------------------------------

def cuda_devices(device):
    """The CUDA device whose generator a fork must keep, or none on the CPU."""
    device = torch.device(device)
    if device.type != "cuda":
        return []
    return [device.index if device.index is not None else torch.cuda.current_device()]


def crop_content(label, plan):
    """What each planned crop holds: the native ids present and their centroids in the crop's own
    voxel frame, the pad before counted in, as FleXray's packer records them
    (fxr/datasets/ct_crops.py, crop_metadata: the mean voxel index of each id over the padded
    crop); a crop holding no structure is left out, as the packer drops it. One pass over the
    volume, the rows of each id in the C order np.argwhere gives, so the means are the packer's."""
    foreground = label > 0
    rows = np.argwhere(foreground)
    values = label[foreground]
    by_id = {int(i): rows[values == i] for i in np.unique(values)}
    crops = []
    for start, stop, before, after in plan:
        centroids = {}
        for i, found in by_id.items():
            inside = found[(found[:, 2] >= start) & (found[:, 2] < stop)]
            if len(inside):
                shifted = inside.astype(np.float64)
                shifted[:, 2] += before - start
                centroids[i] = tuple(float(v) for v in shifted.mean(axis=0))
        if centroids:
            crops.append({"z_start": int(start), "z_stop": int(stop), "pad_before": int(before),
                          "pad_after": int(after), "ids": sorted(centroids),
                          "centroids": centroids})
    return crops


def cut(array, crop, fill):
    """One crop of an array along its last axis, padded with fill as planned (the arithmetic of
    fxr/datasets/ct_crops.py, crop_z)."""
    window = array[..., crop["z_start"]:crop["z_stop"]]
    if crop["pad_before"] or crop["pad_after"]:
        pad = [(0, 0)] * (array.ndim - 1) + [(crop["pad_before"], crop["pad_after"])]
        window = np.pad(window, pad, constant_values=fill)
    return np.ascontiguousarray(window)


def crop_affine(affine, crop):
    """The voxel-to-world affine moved to the crop's first voxel, as float32 (the arithmetic of
    fxr/datasets/ct_crops.py, offset_affine: the origin shifted by the crop's z offset)."""
    shifted = np.array(affine, dtype=np.float64)
    offset = float(crop["z_start"] - crop["pad_before"])
    shifted[:3, 3] += shifted[:3, :3] @ np.array([0.0, 0.0, offset])
    return shifted.astype(np.float32)


def request(pose, point, orthographic, detector, ray_samples):
    """The render request of one view, the intrinsics as FleXray's runtime passes them
    (fxr/models/camera/runtime.py, sample_request: per-view lists, dely following delx, the
    principal point at 0, the AP orientation)."""
    intrinsics = {"sdd": [pose["sdd"]], "delx": [pose["delx"]], "dely": [pose["delx"]],
                  "x0": [0.0], "y0": [0.0], "height": int(detector), "width": int(detector)}
    return DRRRenderRequest(
        rot=pose["rot"], xyz=pose["xyz"], intrinsics=intrinsics,
        isocenter=torch.tensor([point], dtype=torch.float32), orientation=ORIENTATION,
        n_samples=int(ray_samples), orthographic=bool(orthographic))


def render(volume, label, affine, view_request, keywords):
    """fxr.drr.render_drr: the subject built from the HU volume and the labels (nanodrr's
    attenuation from HU, the factors applied), the camera from the request, nanodrr's ray
    marching, the image the sum over the label channels (fxr/drr/rendering.py, render_drr)."""
    with torch.inference_mode():
        return render_drr(volume=volume, label=label, affine=affine, request=view_request,
                          **keywords).images
