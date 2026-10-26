"""The torch side of the render blocks: one function per named choice of schwingnet.render_blocks,
in a table NAMES keyed as its CHOICES are, each saying what FleXray does and where in its source
(flexray 1.0.2 from pip, src/fxr/...), so the blocks engine of tools/flexray_render.py is read
beside FleXray's own runtime step by step and tests/test_flexray_render.py holds the two tables
equal.

A view is made in the order FleXray's runtime draws (fxr/models/camera/runtime.py,
SegmentationDRRRuntime.render, then sample_request; then fxr/drr/rendering.py, render_drr): the
subject is prepared once (hu_window, then air_clamp, then crop plans the crops and crop_sampler
weighs them); per view, the crop is drawn, isocentre draws the target, pose draws the pixel
spacing, the distance and the camera, projection the beam, attenuation the gate and the factors,
render_drr renders, scale scales and edit edits. The draws come from Python's random and torch's
global generator, both seeded by the caller for the view, as FleXray's runtime draws from the same
two; so two configurations that differ only in attenuation, the last draw, share the crop, the
isocentre and the pose of every view.

Imported by path (tools/ is never on sys.path, since tools/profile.py would shadow the standard
library's profile, which torch imports); it needs numpy, torch and fxr.drr, and nothing of
fxr.models, whose camera package imports kornia, a training dependency a render-only environment
need not hold.
"""

import random
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
# MOOSE's stored ids of vertebra_c1 to vertebra_l5 (fxr/configs/datasets/MOOSE.yml); vertebra_l6,
# 83, is dropped by the protocol and never written.
VERTEBRA_IDS = frozenset(range(59, 83))


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
    """FleXray's packer cuts a CT along its last voxel axis into the fewest 256-slice crops that
    cover it, the first and last touching the ends, the slice plane the volume's own, a shorter
    volume one crop padded with air on both sides (fxr/datasets/ct_crops.py, plan_z_crops at
    max_overlap 0 and crop_z); the plan is schwingnet.render_blocks.plan_crops, held equal to
    it. Which crops are dropped for holding no structure is crop_content's to say."""
    return rules.plan_crops(depth)


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


def isocentre_random_label(crop, affine, volume):
    """FleXray's MOOSE profile aims each view at the centroid of one structure the crop holds,
    drawn without replacement over the crop's supervised foreground centroids
    (fxr/drr/isocenter.py, sample_isocenters_from_centroids with replacement false, called by
    SegmentationDRRRuntime._resolve_isocenter for isocenter_cfg random_label; the volume's
    centre when the crop holds none)."""
    return aim(crop["centroids"], affine, volume)


def isocentre_vertebra(crop, affine, volume):
    """The same draw (fxr/drr/isocenter.py, sample_isocenters_from_centroids) over the vertebrae
    alone, MOOSE's vertebra_c1 to vertebra_l5; the volume's centre when the crop holds none."""
    return aim({i: c for i, c in crop["centroids"].items() if i in VERTEBRA_IDS}, affine, volume)


def isocentre_volume_centre(crop, affine, volume):
    """The crop's centre in world coordinates, FleXray's volume_center scheme
    (fxr/drr/isocenter.py, compute_isocenter), which draws nothing."""
    point = compute_isocenter(volume, None, affine, "volume_center")
    return [float(v) for v in point.tolist()], None


def aim(centroids, affine, volume):
    """The target drawn from the centroids by native id, as FleXray draws it (one call of
    sample_isocenters_from_centroids over the ids in ascending order, as its collate orders
    them), with the id whose centroid it is; the volume's centre when there is none."""
    if not centroids:
        return isocentre_volume_centre(None, affine, volume)
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
    return {"rot": rot, "xyz": xyz, "sdd": float(sdd[0]), "delx": float(delx)}


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


NAMES = {
    "hu_window": {"flexray": hu_window_flexray, "none": hu_window_none},
    "air_clamp": {"flexray": air_clamp_flexray, "none": air_clamp_none},
    "crop": {"flexray-axial": crop_flexray_axial, "whole": crop_whole},
    "crop_sampler": {
        "inverse-label-frequency": crop_sampler_inverse_label_frequency,
        "uniform": crop_sampler_uniform,
    },
    "pose": {"flexray-moose": pose_flexray_moose},
    "isocentre": {
        "random-label": isocentre_random_label,
        "vertebra": isocentre_vertebra,
        "volume-centre": isocentre_volume_centre,
    },
    "projection": {"flexray-mix": projection_flexray_mix, "cone": projection_cone},
    "attenuation": {"flexray-lognormal": attenuation_flexray_lognormal, "off": attenuation_off},
    "scale": {"minmax": scale_minmax},
    "edit": {"none": edit_none},
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
