"""Training the auto-anatomist on phantoms read by the oracle: the examples, the losses, one step,
a smoke run, the error as a function of the ladder's lambda with its derivative, and the timing
of the CT-only path.

Nothing here is a trained model or a result. The runs this module makes are seconds to minutes
long on the cloud container's CPU, on phantoms (phantom.py) whose anatomy is drawn from the
generator's columns, and no weight is written anywhere: a run's model lives in memory and goes
with the process. Training on real CTs waits for the owner's word and count, as every training
does in this project.

The examples. Each phantom is a short column, its CT and its mask on one grid; the oracle reads
the mask (oracle.ChordOracle), and each reading gives a vertebra's crop frame (crops.from_reading,
jittered by crops.perturbed so the network does not learn the oracle's frame), the crop's CT and
mask channels, and the landmarks in the crop's millimetres (crops.targets) with the values. A
batch holds whole phantoms, every vertebra of each, so that the vertebrae of one phantom make a
field of consecutive bodies for the naming layer.

The losses, each named in the returned record:

- landmark: the pseudo-Huber distance of each predicted landmark from the oracle's, with a 2 mm
  knee, over the landmarks the oracle gave;
- spread: the Gaussian negative log likelihood of the landmark's error under its heatmap's spread
  (tr S / 3 plus a floor), the error's gradient stopped, so the term teaches the spread to match
  the error and does not pull the position toward the target; it still reaches the heatmap, whose
  weights give the spread and the position both, so the position is moved by the landmark term
  and, through the spread, by this one;
- value: the mean absolute error of the values, which the landmarks give by the measurements' own
  rules;
- feature: ||F_ct - stopgrad(F_mask)||^2 at each scale, the generalized distillation term that
  pulls the CT's features toward the mask's;
- naming: naming.body_loss on each phantom's predicted values as one field, the values' errors
  the measures' own with each value's delta-method spread added, its gradient stopped so the
  network cannot lower the loss by claiming more doubt.

Under the mask objective (model.Config.objective, blocks.py's objective=mask; the owner's ask of
2026-10-30 for a fully latent approach that depends on no measurement code) the decoder gives the
privileged channels back and the loss has two terms, each named in the record:

- mask: the binary cross-entropy of the two logits against the clean channels averaged onto the
  logits' grid (pooled; a soft target, each voxel the share of its crop voxels the channel covers)
  plus one minus their soft Dice, over the crops and the two channels; the target is always the
  clean mask, however far down the ladder the branch's input is;
- feature: as above.

The record then carries dice and dice_every, the hard Dice of the target channel and of every
vertebra's on the logits' grid, in place of distance_mm; evaluate reads the CT-only path's logits
back on the crop's grid and gives the hard Dice, the mean symmetric surface distance of the target
mask in millimetres (distance_mm, an empty prediction or truth counting as the crop's longest side)
and the feature gap, and error_curve gives one minus the target's soft Dice as E(lambda).

The restraint (blocks.py's restraint=abf, the fourth arm of the second screen, from the owner's
question of 30 October 2026 whether an adaptive biasing force can act on what the network learns):
ABF's estimator of the mean force on a collective variable, a running mean per bin of the
variable's value, applied mid-anneal with the weight (1 - cos 2 pi lambda) / 2, so it is zero at
both ends and the network the run ends with is trained as before at lambda 1. The variable is the
target vertebra's volume, as a share of the crop on the logits' grid, under the mask objective,
and each measure's value under the landmarks objective (the width first among them); the force on
it is that of a squared loss on its error in units of ABF_SCALE, (reference - value) / scale^2,
whose mean in a bin is the calibration gap there. ABF in free energy work applies minus the mean
force, to flatten the path; here it is applied with its own sign, a restraint that pushes each bin
of the variable towards its reference's mean, mid-path, while the mask is taken away. A bin's mean
is a running mean of its first ABF_FULL samples and then a moving mean with that weight, since
the network moves under it, and acts in proportion to its samples until it has ABF_FULL
(Forces). The term's value, logged as restraint, is minus the weight times the mean of the force
times the variable, its gradient the force alone; it is not an error and may be negative.

The weights of the terms (LOSS_WEIGHTS), the knee and the floor are this module's choices and the
defaults; losses, landmark_terms and make_step take others as arguments (blocks.py's w_*, knee and
spread_floor, which session.py passes), with the ladder's settings (rungs, ladder.degrade's keyword
arguments) and, under the key "input" of a batch, an augmented CT for the encoder to read in place
of the HU, which the ladder still thresholds unaugmented. With nothing passed, every number here
is the smoke run's.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import jax
import jax.numpy as jnp
import numpy as np
import optax
from flax import nnx
from schwingcheck import chain as CH

from . import calibrate, crops, ladder, naming, phantom
from .model import Config, Model
from .oracle import ChordOracle

LOSS_WEIGHTS = {"landmark": 1.0, "spread": 0.1, "value": 1.0, "feature": 1.0, "naming": 0.1, "mask": 1.0, "name": 0.1}
HUBER_KNEE_MM = 2.0
SPREAD_FLOOR_MM = 0.5
MASK_THRESHOLD = 0.5                # a pooled or resampled channel at or above it is the mask, for the hard Dice and the surfaces
DICE_EPS = 1.0                      # keeps the soft Dice defined, and 1, where a channel is empty in both
# The restraint's collective variable by objective: its scale (the error one unit of the squared
# loss's force stands for: 5 per cent of a crop's volume, the landmark term's knee in a measure's
# own units) and its bins (low, high, count): fifty of a crop's volume, four hundred a measure.
ABF_SCALE = {"mask": 0.05, "landmarks": HUBER_KNEE_MM}
ABF_BINS = {"mask": (0.0, 1.0, 50), "landmarks": (-200.0, 200.0, 400)}
ABF_FULL = 100                      # samples a bin needs before its mean force acts in full (ABF's full_samples)


@dataclass
class Examples:
    """Crops of whole phantoms, in phantom order and top down within each: hu (N, X, Y, Z, 1),
    masks (N, X, Y, Z, 2), targets (N, K, 3) in the crop's millimetres with NaN where the oracle
    gave no point, values (N, M), names (N,) indices into naming.NAMES, and spine (N,) the
    phantom each crop is of; with each crop its frame and the oracle's reading, and the phantoms
    themselves when they were kept (for drawing)."""
    hu: np.ndarray
    masks: np.ndarray
    targets: np.ndarray
    values: np.ndarray
    names: np.ndarray
    spine: np.ndarray
    meta: List[dict] = field(default_factory=list)
    frames: List[crops.CropFrame] = field(default_factory=list)
    readings: list = field(default_factory=list)
    phantoms: list = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.spine)

    def spines(self) -> List[np.ndarray]:
        """The crops of each phantom, as index arrays."""
        return [np.flatnonzero(self.spine == s) for s in np.unique(self.spine)]


def make_examples(cfg: Config, n_spines: int, count: int = 3, seed: int = 0,
                  phenotypes: Sequence[str] = ("typical",), starts: Sequence[str] = ("T12", "L1", "L2"),
                  spacing_mm: float = 1.25, sub: int = 1, noise_hu: float = 20.0, jitter: bool = True,
                  keep: bool = False) -> Examples:
    """n_spines phantoms of `count` consecutive levels each, their phenotypes and first levels
    taken in turn from those given, each tilted by a random turn, read by the oracle and cropped;
    the phantoms are kept in the examples when `keep` is set."""
    rng = np.random.default_rng(seed)
    oracle = ChordOracle(cfg.keys)
    hu, masks, targets, vals, names, spine, meta = [], [], [], [], [], [], []
    frames, readings, kept = [], [], []
    for i in range(n_spines):
        kind, start = phenotypes[i % len(phenotypes)], starts[i % len(starts)]
        levels = phantom.draw_levels(kind, seed=seed * 1000 + i, start=start, count=count)
        tilt = (tuple(rng.normal(size=3)), float(rng.uniform(0.0, 15.0)))
        ph = phantom.render(levels, spacing=(spacing_mm,) * 3, tilt=tilt, sub=sub, noise_hu=noise_hu,
                            seed=seed * 1000 + i)
        for r in oracle.read(ph.labels, ph.affine, ph.names):
            cf = crops.from_reading(r, spacing=cfg.spacing, shape=cfg.shape)
            if jitter:
                cf = crops.perturbed(cf, rng)
            hu.append(crops.ct_channel(ph.hu, ph.affine, cf))
            masks.append(crops.mask_channels(ph.labels, ph.affine, cf, r.label))
            targets.append(crops.targets(r, cf, cfg.keys))
            vals.append(r.values(list(cfg.keys)))
            names.append(naming.NAME_INDEX[r.level])
            spine.append(i)
            frames.append(cf)
            readings.append(r)
        meta.append(dict(phenotype=kind, levels=[lv.name for lv in levels],
                         tilt=[[float(v) for v in tilt[0]], tilt[1]], seed=seed * 1000 + i))
        if keep:
            kept.append(ph)
    return Examples(hu=np.stack(hu), masks=np.stack(masks), targets=np.stack(targets), values=np.stack(vals),
                    names=np.array(names), spine=np.array(spine), meta=meta, frames=frames, readings=readings,
                    phantoms=kept)


def batch_of(ex: Examples, idx: np.ndarray) -> Dict[str, jnp.ndarray]:
    return {"hu": jnp.asarray(ex.hu[idx]), "masks": jnp.asarray(ex.masks[idx]),
            "targets": jnp.asarray(ex.targets[idx]), "values": jnp.asarray(ex.values[idx]),
            "names": jnp.asarray(ex.names[idx])}


def pseudo_huber(d2, knee: float = HUBER_KNEE_MM):
    return knee * knee * (jnp.sqrt(1.0 + d2 / (knee * knee)) - 1.0)


def masked_mean(x, ok):
    ok = ok.astype(x.dtype)
    return jnp.sum(x * ok) / jnp.maximum(jnp.sum(ok), 1.0)


def landmark_terms(out, targets, knee: float = HUBER_KNEE_MM, floor: float = SPREAD_FLOOR_MM):
    """The landmark and spread terms, and the mean distance in millimetres, over the points given."""
    ok = jnp.all(jnp.isfinite(targets), -1)                                   # (B, K)
    t = jnp.where(ok[..., None], targets, 0.0)
    d2 = jnp.sum((out["points"] - t) ** 2, -1)
    var = jnp.trace(out["cov"], axis1=-2, axis2=-1) / 3.0 + floor ** 2
    nll = jax.lax.stop_gradient(d2) / (2.0 * var) + 1.5 * jnp.log(var)
    return masked_mean(pseudo_huber(d2, knee), ok), masked_mean(nll, ok), masked_mean(jnp.sqrt(d2 + 1e-12), ok)


def feature_term(out):
    return sum(jnp.mean((a - jax.lax.stop_gradient(b)) ** 2) for a, b in zip(out["f_ct"], out["f_mask"])) / len(out["f_ct"])


def pooled(masks, shape: Sequence[int]):
    """The privileged channels (B, X, Y, Z, C) averaged onto the decoder's grid (B, x, y, z, C): each
    voxel the share of its crop voxels the channel covers, a soft target in [0, 1]. The crop's
    sides must be whole multiples of the grid's, as the encoders' strides make them."""
    B, X, Y, Z, C = masks.shape
    x, y, z = (int(n) for n in shape)
    if X % x or Y % y or Z % z:
        raise ValueError("the crop %r is no whole multiple of the logits' grid %r" % ((X, Y, Z), (x, y, z)))
    return masks.reshape(B, x, X // x, y, Y // y, z, Z // z, C).mean(axis=(2, 4, 6))


def soft_dice(p, t, eps: float = DICE_EPS):
    """2 sum(p t) over sum(p) + sum(t), per crop and channel, (B, C); eps keeps it 1 where both are empty."""
    axes = tuple(range(1, p.ndim - 1))
    return (2.0 * jnp.sum(p * t, axes) + eps) / (jnp.sum(p, axes) + jnp.sum(t, axes) + eps)


def hard_dice(pred, truth, eps: float = 1e-6) -> np.ndarray:
    """The Dice of two binary masks per crop and channel, (B, C), on numpy arrays; 1 where both are empty."""
    pred, truth = np.asarray(pred, bool), np.asarray(truth, bool)
    axes = tuple(range(1, pred.ndim - 1))
    inter = np.sum(pred & truth, axes)
    return (2.0 * inter + eps) / (np.sum(pred, axes) + np.sum(truth, axes) + eps)


def mask_terms(logits, masks):
    """The mask term of the mask objective on one batch, and its two metrics: the binary cross-entropy
    of the logits against the clean channels pooled onto the logits' grid plus one minus their soft
    Dice, over the crops and both channels; the hard Dice of the target channel and of every
    vertebra's, the logits above 0 against the pooled channel at MASK_THRESHOLD or above."""
    t = pooled(masks, logits.shape[1:4])
    bce = jnp.mean(optax.sigmoid_binary_cross_entropy(logits, t))
    dice = soft_dice(jax.nn.sigmoid(logits), t)
    loss = bce + jnp.mean(1.0 - dice)
    hard = hard_dice_jnp(logits > 0.0, t >= MASK_THRESHOLD)
    return loss, jnp.mean(hard[:, 0]), jnp.mean(hard[:, 1])


def hard_dice_jnp(pred, truth, eps: float = 1e-6):
    axes = tuple(range(1, pred.ndim - 1))
    p, t = pred.astype(jnp.float32), truth.astype(jnp.float32)
    return (2.0 * jnp.sum(p * t, axes) + eps) / (jnp.sum(p, axes) + jnp.sum(t, axes) + eps)


def mask_error(logits, masks):
    """One minus the target channel's mean soft Dice: the mask objective's E for error_curve."""
    t = pooled(masks, logits.shape[1:4])
    return 1.0 - jnp.mean(soft_dice(jax.nn.sigmoid(logits), t)[:, 0])


def name_terms(logits, names):
    """The name head's term on one batch and its metric: the cross-entropy of each crop's name logits
    against its level name (an index into naming.NAMES), and the share of crops whose best logit
    is their name."""
    ce = jnp.mean(optax.softmax_cross_entropy_with_integer_labels(logits, names))
    right = jnp.mean((jnp.argmax(logits, -1) == names).astype(jnp.float32))
    return ce, right


def adjacent_names() -> set:
    """The pairs of level names that stand next to each other in some column: consecutive in the
    chain's level sequence of any column type (schwingcheck.chain.type_levels), so T12 and L1, T12
    and T13, T13 and L1 and L5 and L6 are all neighbours; pairs of indices into naming.NAMES."""
    pairs = set()
    for kind in CH.TYPES:
        seq = CH.type_levels(kind)
        pairs.update(frozenset((naming.NAME_INDEX[a], naming.NAME_INDEX[b])) for a, b in zip(seq, seq[1:]))
    return pairs


def within_one(pred: np.ndarray, truth: np.ndarray) -> np.ndarray:
    """Whether each predicted name is the true one or its neighbour in some column (adjacent_names)."""
    pairs = adjacent_names()
    return np.array([int(p) == int(t) or frozenset((int(p), int(t))) in pairs for p, t in zip(pred, truth)], bool)


def centroid_error_mm(pred: np.ndarray, truth: np.ndarray, spacing: float, bound: float) -> float:
    """The distance in millimetres between a crop's predicted mask's centroid and its truth's, or
    `bound` where either is empty."""
    p, t = np.argwhere(pred), np.argwhere(truth)
    if len(p) == 0 or len(t) == 0:
        return bound
    return float(np.linalg.norm((p.mean(0) - t.mean(0)) * spacing))


def longest_side_mm(cfg: Config) -> float:
    return float(max(cfg.shape) * cfg.spacing)


def surface_distance_mm(pred: np.ndarray, truth: np.ndarray, spacing: float, bound: float) -> float:
    """The mean symmetric surface distance in millimetres of two binary masks on one grid of
    `spacing` mm: each surface voxel's distance to the other mask's surface, averaged over both
    surfaces (a surface voxel is one of the mask with a neighbour outside it, the grid's edge
    counting as outside); `bound` where either mask has no surface, an empty prediction or truth."""
    from scipy import ndimage
    pred, truth = np.asarray(pred, bool), np.asarray(truth, bool)
    sp = pred & ~ndimage.binary_erosion(pred)
    st = truth & ~ndimage.binary_erosion(truth)
    if not sp.any() or not st.any():
        return float(bound)
    to_truth = ndimage.distance_transform_edt(~st, sampling=spacing)
    to_pred = ndimage.distance_transform_edt(~sp, sampling=spacing)
    return float((to_truth[sp].sum() + to_pred[st].sum()) / (sp.sum() + st.sum()))


def naming_term(nm: naming.Naming, out, batch, fields: int):
    """naming.body_loss on the batch's phantoms, each one field of nm.n_bodies crops in order."""
    B = nm.n_bodies
    X = jnp.transpose(out["values"].reshape(fields, B, -1), (0, 2, 1))       # (fields, M, B)
    s = jax.lax.stop_gradient(jnp.transpose(out["sigma"].reshape(fields, B, -1), (0, 2, 1)))
    noise = jnp.sqrt(jnp.asarray(nm.noise, X.dtype)[None, :, None] ** 2 + s ** 2)
    return naming.body_loss(nm, X, batch["names"].reshape(fields, B), noise)


def collective(out, batch, objective: str):
    """The restraint's collective variables of a batch, (B, K), with their references and which of
    those the batch gives: under the mask objective the target channel's volume as a share of the
    logits' grid, against the clean mask pooled onto it (K 1); under landmarks the measures' values."""
    if objective == "mask":
        logits = out["logits"]
        axes = tuple(range(1, logits.ndim - 1))
        cv = jnp.mean(jax.nn.sigmoid(logits[..., 0]), axes)[:, None]
        ref = jnp.mean(pooled(batch["masks"], logits.shape[1:4])[..., 0], axes)[:, None]
        return cv, ref, jnp.ones_like(cv, dtype=bool)
    ok = jnp.isfinite(batch["values"])
    return out["values"], jnp.where(ok, batch["values"], 0.0), ok


def restraint_weight(lam):
    """The restraint's weight along the anneal, (1 - cos 2 pi lambda) / 2: 0 at both ends, 1 at lambda 1/2."""
    return 0.5 * (1.0 - jnp.cos(2.0 * jnp.pi * lam))


def bin_of(cv, objective: str):
    """Each variable's bin, clipped into the objective's bins."""
    lo, hi, n = ABF_BINS[objective]
    return jnp.clip(jnp.floor((cv - lo) / (hi - lo) * n), 0, n - 1).astype(jnp.int32)


def restraint_term(cv, bias, lam, objective: str):
    """Minus the restraint's weight at lambda times the mean over the batch of each variable's bin's
    mean force (bias, (K, bins), held fixed) times the variable: its gradient on a variable is the
    weight times its bin's mean force over the batch's count, a push towards the bin's reference."""
    force = jax.lax.stop_gradient(bias)[jnp.arange(cv.shape[1])[None, :], bin_of(cv, objective)]
    return -restraint_weight(lam) * jnp.mean(force * cv)


@dataclass
class Forces:
    """The restraint's estimate, ABF's: for each variable and bin the mean force (reference - value)
    / scale^2 of the samples whose value fell in it, a running mean of the first ABF_FULL and a
    moving mean of weight 1 / ABF_FULL after, and the count of samples; bias is the mean scaled by
    the share of ABF_FULL samples a bin holds, at most 1."""
    objective: str
    mean: np.ndarray
    count: np.ndarray

    @classmethod
    def empty(cls, objective: str, k: int) -> "Forces":
        n = ABF_BINS[objective][2]
        return cls(objective, np.zeros((k, n), np.float64), np.zeros((k, n), np.int64))

    def update(self, cv: np.ndarray, ref: np.ndarray, ok: np.ndarray) -> None:
        """The batch's samples added in order, each to its variable's bin."""
        scale = ABF_SCALE[self.objective]
        bins = np.asarray(bin_of(jnp.asarray(cv), self.objective))
        for i, j in zip(*np.nonzero(np.asarray(ok))):
            b = bins[i, j]
            self.count[j, b] += 1
            force = (float(ref[i, j]) - float(cv[i, j])) / scale ** 2
            self.mean[j, b] += (force - self.mean[j, b]) / min(self.count[j, b], ABF_FULL)

    def bias(self) -> np.ndarray:
        return (self.mean * np.minimum(self.count / ABF_FULL, 1.0)).astype(np.float32)


def losses(model: Model, batch, w, lam, nm: Optional[naming.Naming] = None, fields: int = 0,
           weights: Dict[str, float] = LOSS_WEIGHTS, knee: float = HUBER_KNEE_MM, floor: float = SPREAD_FLOOR_MM,
           rungs: Optional[Dict[str, float]] = None, bias=None, restraint: float = 0.0):
    """The total loss and its terms for one batch at fusion weight w and ladder rung lam; the
    encoder reads batch["input"] where the batch carries one, the ladder always batch["hu"]. With a
    bias (Forces.bias) the restraint at weight `restraint` joins the total, and the record carries
    the batch's collective variables (cv, cv_ref, cv_ok) for the estimate."""
    masks = ladder.degrade(batch["masks"], batch["hu"], lam, spacing_mm=model.cfg.spacing, **(rungs or {}))
    out = model(batch.get("input", batch["hu"]), masks, w)
    if model.cfg.objective == "mask":
        mask_loss, dice, dice_every = mask_terms(out["logits"], batch["masks"])
        name_loss, named = name_terms(out["name_logits"], batch["names"])
        terms = {"mask": mask_loss, "feature": feature_term(out), "name": name_loss}
        total = sum(weights[k] * v for k, v in terms.items())
        total, extra = restrained(total, out, batch, lam, bias, restraint, "mask")
        return total, dict(terms, dice=dice, dice_every=dice_every, named_right=named, **extra)
    lm, spread, dist = landmark_terms(out, batch["targets"], knee, floor)
    ok = jnp.isfinite(batch["values"])
    value = masked_mean(jnp.abs(out["values"] - jnp.where(ok, batch["values"], 0.0)), ok)
    terms = {"landmark": lm, "spread": spread, "value": value, "feature": feature_term(out)}
    if nm is not None and fields > 0:
        terms["naming"] = naming_term(nm, out, batch, fields)
    total = sum(weights[k] * v for k, v in terms.items())
    total, extra = restrained(total, out, batch, lam, bias, restraint, "landmarks")
    return total, dict(terms, distance_mm=dist, **extra)


def restrained(total, out, batch, lam, bias, restraint: float, objective: str):
    """The total with the restraint added where a bias is given, and what the record carries of it."""
    if bias is None:
        return total, {}
    cv, ref, ok = collective(out, batch, objective)
    term = restraint_term(cv, bias, lam, objective)
    return total + restraint * term, {"restraint": term, "cv": cv, "cv_ref": ref, "cv_ok": ok}


def make_step(nm: Optional[naming.Naming], fields: int, weights: Dict[str, float] = LOSS_WEIGHTS,
              knee: float = HUBER_KNEE_MM, floor: float = SPREAD_FLOOR_MM, rungs: Optional[Dict[str, float]] = None,
              restraint: Optional[float] = None):
    """One jitted step of the optimizer it is given on the total loss, w and lambda traced so that
    changing them does not compile again. With a restraint's weight the step takes the bias too,
    step(model, opt, batch, w, lam, bias), traced as well."""
    if restraint is not None:
        @nnx.jit
        def restrained_step(model, opt, batch, w, lam, bias):
            (total, terms), grads = nnx.value_and_grad(
                lambda m: losses(m, batch, w, lam, nm, fields, weights, knee, floor, rungs, bias, restraint),
                has_aux=True)(model)
            opt.update(model, grads)
            return total, terms
        return restrained_step

    @nnx.jit
    def step(model, opt, batch, w, lam):
        (total, terms), grads = nnx.value_and_grad(
            lambda m: losses(m, batch, w, lam, nm, fields, weights, knee, floor, rungs), has_aux=True)(model)
        opt.update(model, grads)
        return total, terms
    return step


def make_error_slope(rungs: Optional[Dict[str, float]] = None):
    """One jitted function, (model, batch, w, lam) -> (E, dE/dlambda), error_curve's E on a batch at
    the ladder's settings given, compiled once for schedule=adaptive's checks; the encoder reads
    batch["input"] where the batch carries one, as in training."""
    def error(m, batch, w, lam):
        masks = ladder.degrade(batch["masks"], batch["hu"], lam, spacing_mm=m.cfg.spacing, **(rungs or {}))
        out = m(batch.get("input", batch["hu"]), masks, w)
        if m.cfg.objective == "mask":
            return mask_error(out["logits"], batch["masks"])
        return landmark_terms(out, batch["targets"])[2]

    return nnx.jit(lambda m, batch, w, lam: jax.value_and_grad(lambda l: error(m, batch, w, l))(lam))


@dataclass
class Run:
    """What a run leaves in memory: its model, its schedule and its record, one row per step."""
    model: Model
    schedule: ladder.Schedule
    record: List[dict]


def train(ex: Examples, cfg: Config, steps: int, spines_per_batch: int = 2, lr: float = 2e-3, seed: int = 0,
          use_naming: bool = True, schedule: Optional[ladder.Schedule] = None, log_every: int = 0) -> Run:
    """A run of `steps` steps over whole phantoms, `spines_per_batch` at a time, lambda and w on
    the schedule (ladder.Schedule over the steps unless given). Every phantom must have the same
    number of crops, the naming layer's field."""
    groups = ex.spines()
    count = len(groups[0])
    if any(len(g) != count for g in groups):
        raise ValueError("every phantom needs the same number of crops for the naming layer: %r" % [len(g) for g in groups])
    nm = naming.prepare(cfg.keys, n_bodies=count) if use_naming else None
    model = Model(cfg, nnx.Rngs(seed))
    opt = nnx.Optimizer(model, optax.adamw(lr), wrt=nnx.Param)
    schedule = schedule or ladder.Schedule(steps)
    step = make_step(nm, spines_per_batch if use_naming else 0)
    rng = np.random.default_rng(seed)
    record = []
    for s in range(steps):
        pick = rng.choice(len(groups), size=spines_per_batch, replace=len(groups) < spines_per_batch)
        batch = batch_of(ex, np.concatenate([groups[g] for g in pick]))
        w, lam = schedule.at(s)
        t0 = time.time()
        total, terms = step(model, opt, batch, jnp.float32(w), jnp.float32(lam))
        row = {"step": s, "w": w, "lam": lam, "total": float(total), "seconds": time.time() - t0}
        row.update({k: float(v) for k, v in terms.items()})
        record.append(row)
        if log_every and (s % log_every == 0 or s == steps - 1):
            print(progress_words(row))
    return Run(model=model, schedule=schedule, record=record)


def progress_words(row: dict) -> str:
    """One step's row in a line: its distance in millimetres, or under the mask objective its Dice
    and the share of crops named right."""
    head = "step %d w %.2f lam %.2f total %.3f" % (row["step"], row["w"], row["lam"], row["total"])
    if "distance_mm" in row:
        return head + " distance %.2f mm" % row["distance_mm"]
    return head + " dice %.3f named %.2f" % (row.get("dice", float("nan")), row.get("named_right", float("nan")))


def predict(model: Model, hu: np.ndarray, batch: int = 16) -> Dict[str, np.ndarray]:
    """The CT-only path on every crop given, in batches, as numpy arrays."""
    f = nnx.jit(lambda m, hu: m.ct_only(hu))
    parts = [f(model, jnp.asarray(hu[i:i + batch])) for i in range(0, len(hu), batch)]
    return {k: np.concatenate([np.asarray(p[k]) for p in parts]) for k in parts[0]}


def evaluate(model: Model, ex: Examples, use_naming: bool = True, calibration=None) -> Dict[str, object]:
    """The CT-only path on every crop: the mean landmark distance in millimetres, each value's mean
    absolute error, the mean delta-method spread of the values and, given a calibration (the
    factors calibrate.fit returns, one per measure), the mean calibrated spread and the coverage at
    one and two calibrated spreads; and, where the phantoms make fields, the naming layer's share
    of bodies named right from the predicted values, twice: with each value's spread added to the
    measure's error, as train.py's loss adds it, the calibrated spread where there is one, and from
    the values alone, with the measures' own errors, beside the share the oracle's own values name
    right. An untrained or briefly trained spread is wide and uncalibrated, and a wide spread
    flattens each body's posterior over the neighbouring levels, short of the prior, so the two
    shares can differ widely. Under the mask objective, evaluate_masks."""
    if model.cfg.objective == "mask":
        return evaluate_masks(model, ex)
    out = predict(model, ex.hu)
    _, _, dist = landmark_terms(jax.tree.map(jnp.asarray, out), jnp.asarray(ex.targets))
    signed = out["values"] - ex.values
    err = np.abs(signed)
    res = {"distance_mm": float(dist), "value_mae": dict(zip(model.cfg.keys, np.nanmean(err, 0).round(3).tolist())),
           "sigma_mm": float(np.mean(out["sigma"]))}
    spread = out["sigma"]
    if calibration is not None:
        spread = calibrate.apply(out["sigma"], calibration)
        res["calibrated_sigma_mm"] = float(np.mean(spread))
        res["coverage_at_1"] = calibrate.coverage_at(signed, spread, 1.0)
        res["coverage_at_2"] = calibrate.coverage_at(signed, spread, 2.0)
    groups = ex.spines()
    if use_naming and len({len(g) for g in groups}) == 1:
        B = len(groups[0])
        nm = naming.prepare(model.cfg.keys, n_bodies=B)
        order = np.concatenate(groups)
        X = np.transpose(np.asarray(out["values"])[order].reshape(len(groups), B, -1), (0, 2, 1))
        s = np.transpose(np.asarray(spread)[order].reshape(len(groups), B, -1), (0, 2, 1))
        noise = np.sqrt(nm.noise[None, :, None] ** 2 + s ** 2)
        truth = ex.names[order].reshape(len(groups), B)
        oracle_X = np.transpose(ex.values[order].reshape(len(groups), B, -1), (0, 2, 1))
        named = lambda X, noise=None: float((np.asarray(naming.posteriors(nm, jnp.asarray(X), noise)["body"]).argmax(-1) == truth).mean())
        res["named_right"] = named(X, jnp.asarray(noise))
        res["named_right_values_alone"] = named(X)
        res["named_right_from_oracle"] = named(oracle_X)
    return res


def feature_gap(model: Model, ex: Examples, batch: int = 16) -> float:
    """The feature term between the CT's features and the clean mask's over every crop, in batches:
    how far the CT branch stands from the mask branch it was pulled toward."""
    f = nnx.jit(lambda m, hu, masks: feature_term(dict(zip(("f_ct", "f_mask"), m.features(hu, masks)))))
    total, count = 0.0, 0
    for i in range(0, len(ex), batch):
        n = len(ex.hu[i:i + batch])
        total += float(f(model, jnp.asarray(ex.hu[i:i + batch]), jnp.asarray(ex.masks[i:i + batch]))) * n
        count += n
    return total / max(count, 1)


def evaluate_masks(model: Model, ex: Examples) -> Dict[str, object]:
    """The CT-only path on every crop under the mask objective: its logits brought back onto the
    crop's grid trilinearly and read at 0, against the clean channels at MASK_THRESHOLD or above:
    the hard Dice of the target vertebra's mask (dice) and of every vertebra's (dice_every), the
    mean symmetric surface distance of the target's in millimetres (distance_mm; a crop whose
    prediction or truth has no surface counts as the crop's longest side, and surface_missing says
    how many did), the distance between the predicted target's centroid and the truth's
    (centroid_mm, the same bound where either is empty), the share of crops the name head names
    right (named_right) and right or by a neighbouring level (named_within_one, adjacent_names), the
    feature gap (feature_gap), and the same figures by level (by_level, keyed by the level's name)."""
    out = predict(model, ex.hu)
    logits = out["logits"]
    shape = (len(logits),) + tuple(model.cfg.shape) + (logits.shape[-1],)
    up = np.asarray(jax.image.resize(jnp.asarray(logits), shape, "trilinear"))
    pred, truth = up > 0.0, ex.masks >= MASK_THRESHOLD
    dice = hard_dice(pred, truth)
    bound = longest_side_mm(model.cfg)
    distances = np.array([surface_distance_mm(pred[i, ..., 0], truth[i, ..., 0], model.cfg.spacing, bound) for i in range(len(pred))])
    centroids = np.array([centroid_error_mm(pred[i, ..., 0], truth[i, ..., 0], model.cfg.spacing, bound) for i in range(len(pred))])
    named = np.argmax(out["name_logits"], -1)
    right, near = named == ex.names, within_one(named, ex.names)
    by_level = {}
    for name in sorted(set(int(n) for n in ex.names)):
        m = ex.names == name
        by_level[naming.NAMES[name]] = {"crops": int(m.sum()), "dice": float(dice[m, 0].mean()),
                                        "distance_mm": float(distances[m].mean()), "centroid_mm": float(centroids[m].mean()),
                                        "named_right": float(right[m].mean()), "named_within_one": float(near[m].mean())}
    return {"dice": float(dice[:, 0].mean()), "dice_every": float(dice[:, 1].mean()),
            "distance_mm": float(distances.mean()), "surface_missing": int((distances == bound).sum()),
            "surface_bound_mm": bound, "centroid_mm": float(centroids.mean()),
            "named_right": float(right.mean()), "named_within_one": float(near.mean()),
            "feature_gap": feature_gap(model, ex), "crops": int(len(pred)), "by_level": by_level}


def error_curve(model: Model, batch, lams: Sequence[float], w: float = 1.0) -> Tuple[np.ndarray, np.ndarray]:
    """E(lambda), the mean landmark distance in millimetres of the fused pass at weight w with the
    mask taken down the ladder to lambda (under the mask objective, one minus the target channel's
    soft Dice, mask_error), and dE/dlambda, by automatic differentiation through the ladder's soft
    gates, at each lambda given."""
    def E(m, lam):
        masks = ladder.degrade(batch["masks"], batch["hu"], lam, spacing_mm=m.cfg.spacing)
        out = m(batch["hu"], masks, w)
        if m.cfg.objective == "mask":
            return mask_error(out["logits"], batch["masks"])
        return landmark_terms(out, batch["targets"])[2]

    f = nnx.jit(lambda m, lam: jax.value_and_grad(lambda l: E(m, l))(lam))
    vals, grads = [], []
    for lam in lams:
        v, g = f(model, jnp.float32(lam))
        vals.append(float(v))
        grads.append(float(g))
    return np.array(vals), np.array(grads)


def timing(model: Model, n: int = 8, repeats: int = 3, seed: int = 0) -> Dict[str, float]:
    """Seconds per crop of the jitted CT-only path on this machine, batches of n, after the
    first call, the best of `repeats`; and the first call's seconds, the compile and one batch's
    run together."""
    cfg = model.cfg
    hu = jnp.asarray(np.random.default_rng(seed).normal(0.0, 300.0, (n,) + tuple(cfg.shape) + (1,)), jnp.float32)
    f = nnx.jit(lambda m, hu: m.ct_only(hu))
    t0 = time.time()
    jax.block_until_ready(f(model, hu))
    first_call_s = time.time() - t0
    best = np.inf
    for _ in range(repeats):
        t0 = time.time()
        jax.block_until_ready(f(model, hu))
        best = min(best, time.time() - t0)
    return {"seconds_per_crop": best / n, "first_call_seconds": first_call_s, "batch": n,
            "device": str(jax.devices()[0])}


def as_reading(reading, cf: crops.CropFrame, points: np.ndarray, vals: np.ndarray, keys: Sequence[str]):
    """The network's answer for one crop in the oracle's form: a Reading of the same vertebra and
    frame whose measurements carry the network's points, carried from the crop into the world, and
    its values, so render.draw draws the network's lines as it draws the oracle's."""
    from .oracle import Measurement, Reading
    from .specs import landmarks
    world = cf.world(np.asarray(points, float))
    at = {name: world[i] for i, name in enumerate(landmarks(keys))}
    out = Reading(level=reading.level, label=reading.label, frame=reading.frame, centre=reading.centre,
                  voxels=reading.voxels)
    for j, k in enumerate(keys):
        names = [n for n in at if n.split(".")[0] == k]
        out.measurements[k] = Measurement(k, float(vals[j]), {n: at[n] for n in names})
    return out
