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

from . import calibrate, crops, ladder, naming, phantom
from .model import Config, Model
from .oracle import ChordOracle

LOSS_WEIGHTS = {"landmark": 1.0, "spread": 0.1, "value": 1.0, "feature": 1.0, "naming": 0.1}
HUBER_KNEE_MM = 2.0
SPREAD_FLOOR_MM = 0.5


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


def naming_term(nm: naming.Naming, out, batch, fields: int):
    """naming.body_loss on the batch's phantoms, each one field of nm.n_bodies crops in order."""
    B = nm.n_bodies
    X = jnp.transpose(out["values"].reshape(fields, B, -1), (0, 2, 1))       # (fields, M, B)
    s = jax.lax.stop_gradient(jnp.transpose(out["sigma"].reshape(fields, B, -1), (0, 2, 1)))
    noise = jnp.sqrt(jnp.asarray(nm.noise, X.dtype)[None, :, None] ** 2 + s ** 2)
    return naming.body_loss(nm, X, batch["names"].reshape(fields, B), noise)


def losses(model: Model, batch, w, lam, nm: Optional[naming.Naming] = None, fields: int = 0,
           weights: Dict[str, float] = LOSS_WEIGHTS, knee: float = HUBER_KNEE_MM, floor: float = SPREAD_FLOOR_MM,
           rungs: Optional[Dict[str, float]] = None):
    """The total loss and its terms for one batch at fusion weight w and ladder rung lam; the
    encoder reads batch["input"] where the batch carries one, the ladder always batch["hu"]."""
    masks = ladder.degrade(batch["masks"], batch["hu"], lam, spacing_mm=model.cfg.spacing, **(rungs or {}))
    out = model(batch.get("input", batch["hu"]), masks, w)
    lm, spread, dist = landmark_terms(out, batch["targets"], knee, floor)
    ok = jnp.isfinite(batch["values"])
    value = masked_mean(jnp.abs(out["values"] - jnp.where(ok, batch["values"], 0.0)), ok)
    terms = {"landmark": lm, "spread": spread, "value": value, "feature": feature_term(out)}
    if nm is not None and fields > 0:
        terms["naming"] = naming_term(nm, out, batch, fields)
    total = sum(weights[k] * v for k, v in terms.items())
    return total, dict(terms, distance_mm=dist)


def make_step(nm: Optional[naming.Naming], fields: int, weights: Dict[str, float] = LOSS_WEIGHTS,
              knee: float = HUBER_KNEE_MM, floor: float = SPREAD_FLOOR_MM, rungs: Optional[Dict[str, float]] = None):
    """One jitted step of the optimizer it is given on the total loss, w and lambda traced so that
    changing them does not compile again."""
    @nnx.jit
    def step(model, opt, batch, w, lam):
        (total, terms), grads = nnx.value_and_grad(
            lambda m: losses(m, batch, w, lam, nm, fields, weights, knee, floor, rungs), has_aux=True)(model)
        opt.update(model, grads)
        return total, terms
    return step


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
            print("step %d w %.2f lam %.2f total %.3f distance %.2f mm" % (s, w, lam, row["total"], row["distance_mm"]))
    return Run(model=model, schedule=schedule, record=record)


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
    shares can differ widely."""
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


def error_curve(model: Model, batch, lams: Sequence[float], w: float = 1.0) -> Tuple[np.ndarray, np.ndarray]:
    """E(lambda), the mean landmark distance in millimetres of the fused pass at weight w with the
    mask taken down the ladder to lambda, and dE/dlambda, by automatic differentiation through
    the ladder's soft gates, at each lambda given."""
    def E(m, lam):
        masks = ladder.degrade(batch["masks"], batch["hu"], lam, spacing_mm=m.cfg.spacing)
        return landmark_terms(m(batch["hu"], masks, w), batch["targets"])[2]

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
