"""A training session of the auto-anatomist built from blocks, which trains from its step, saves
itself as plain arrays and is restored from them, so that a search's trial, a continued annealing
and a run on more data are one session taken further (the owner's ask of 29 October 2026, 15:30
UTC: "ensure i have the ability to simplely continue training/annealing/ect, and I can add more
training data without needed to restart").

    s = Session.new(blocks.parse("lr=0.001"))
    s.train(examples, steps=300)            # from step 0; the anneal spans 300 steps unless anneal says
    s.save(folder)                          # state.npz, session.json, record.jsonl
    s = Session.load(folder)                # the same session, at step 300
    s.continue_anneal(until=600)
    s.train(examples, steps=300)            # both ramps carry on from where they stood to their ends by 600
    s.calibrate(validation)                 # the spread's factors, on validation only
    s.evaluate(validation)                  # train.evaluate's report with the calibrated figures

What is saved: every leaf of the model's and the optimizer's state as one array under its path
(nnx.state, nnx.to_flat_state; "model/ct/b1/conv1/kernel", "optimizer/opt_state/0/mu/..."), in
state.npz; the step, the anneal (ladder.Anneal), the numpy generator's bit-generator state, the
calibration, the naming field's size, the crop and the blocks' record in session.json; and the
rows of every step trained in record.jsonl, appended, which nothing reads back. A load rebuilds
the model and the optimizer from the blocks and puts the arrays in by path, refusing a file whose
paths are not the rebuilt structure's, so a session restored and trained one step more is the
session trained one step more without the save, to the bit (tests/test_autoanatomist_session.py).

With no block named the session is train.train's smoke run to the bit: the same optimizer, the
same loss, the same schedule (an Anneal over the first budget's steps gives Schedule's numbers)
and the same draws from the same generator. The intensity blocks draw a gain, an offset and noise
on the host with the session's generator and put the augmented CT under the batch's key "input",
which the encoder reads while the ladder thresholds the HU as they are (train.losses).
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import jax.numpy as jnp
import numpy as np
import optax
from flax import nnx

from . import calibrate, crops, ladder, naming, train
from .blocks import Blocks, parse
from .model import Config, Model
from .specs import SEVEN

INTENSITY = {"gain": 0.1, "offset_hu": 50.0, "noise_hu": 20.0}   # the augmentation's sizes: this module's choices
STATE, META, RECORD = "state.npz", "session.json", "record.jsonl"


def optimiser(b: Blocks, model: Model) -> nnx.Optimizer:
    """The optimizer the blocks name: adamw with its decoupled decay, or adam or sgd with the decay
    as an L2 term added to the gradient; a global-norm clip in front where clip is above 0, and a
    linear warm-up of the learning rate where warmup is; nothing wrapped where neither is, so the
    state's paths are train.train's."""
    lr = b.lr if b.warmup == 0 else optax.linear_schedule(0.0, b.lr, b.warmup)
    if b.optimiser == "adamw":
        tx = optax.adamw(lr, weight_decay=b.weight_decay)
    else:
        tx = optax.adam(lr) if b.optimiser == "adam" else optax.sgd(lr)
        if b.weight_decay > 0:
            tx = optax.chain(optax.add_decayed_weights(b.weight_decay), tx)
    if b.clip > 0:
        tx = optax.chain(optax.clip_by_global_norm(b.clip), tx)
    return nnx.Optimizer(model, tx, wrt=nnx.Param)


def anneal_of(b: Blocks, steps: Optional[int] = None) -> Optional[ladder.Anneal]:
    """The blocks' anneal over `anneal` steps, or over `steps` where anneal is 0, or none yet."""
    n = b.anneal or steps
    if not n:
        return None
    return ladder.Anneal(kind=b.schedule, steps=int(n), lam_span=b.lam_span, w_span=b.w_span,
                         lam_fixed=b.lam_fixed, w_fixed=b.w_fixed)


def augmented(hu: np.ndarray, kind: str, rng: np.random.Generator) -> np.ndarray:
    """The CT crops (N, X, Y, Z, 1) with a gain about 1 and an offset in HU drawn per crop and, under
    gain-offset-noise, Gaussian noise per voxel, for the encoder's input alone."""
    if kind == "off":
        return hu
    n = len(hu)
    gain = rng.uniform(1.0 - INTENSITY["gain"], 1.0 + INTENSITY["gain"], (n, 1, 1, 1, 1))
    offset = rng.uniform(-INTENSITY["offset_hu"], INTENSITY["offset_hu"], (n, 1, 1, 1, 1))
    out = hu * gain + offset
    if kind == "gain-offset-noise":
        out = out + rng.normal(0.0, INTENSITY["noise_hu"], hu.shape)
    return out.astype(hu.dtype, copy=False)


def leaf(v):
    return v[...] if isinstance(v, nnx.Variable) else v


def with_value(v, array):
    return v.replace(array) if hasattr(v, "replace") else array


def flat_arrays(obj, prefix: str) -> Dict[str, np.ndarray]:
    """Every leaf of the object's state as a numpy array under prefix/its path."""
    return {prefix + "/" + "/".join(str(k) for k in path): np.asarray(leaf(v))
            for path, v in nnx.to_flat_state(nnx.state(obj))}


def put_arrays(obj, arrays: Dict[str, np.ndarray], prefix: str) -> None:
    """The arrays under prefix put into the object's state by path, refused in words where the
    file's paths and the object's differ."""
    flat = nnx.to_flat_state(nnx.state(obj))
    want = {prefix + "/" + "/".join(str(k) for k in path): (path, v) for path, v in flat}
    have = {k for k in arrays if k.startswith(prefix + "/")}
    if set(want) != have:
        missing, extra = sorted(set(want) - have), sorted(have - set(want))
        raise ValueError("%s does not hold the %s this session's blocks build: missing %s; extra %s"
                         % (STATE, prefix, ", ".join(missing[:5]) or "none", ", ".join(extra[:5]) or "none"))
    wrong = [key for key, (path, v) in want.items() if tuple(np.shape(arrays[key])) != tuple(np.shape(leaf(v)))]
    if wrong:
        raise ValueError("%s does not hold the %s this session's blocks build: %s has shape %s, not %s"
                         % (STATE, prefix, wrong[0], np.shape(arrays[wrong[0]]), np.shape(leaf(want[wrong[0]][1]))))
    nnx.update(obj, nnx.from_flat_state([(path, with_value(v, jnp.asarray(arrays[key]))) for key, (path, v) in want.items()]))


def versions() -> dict:
    import flax
    import jax
    return {"jax": jax.__version__, "flax": flax.__version__, "optax": optax.__version__, "numpy": np.__version__}


@dataclass
class Session:
    """One configuration's training, from its step: the blocks, the network and its optimizer, the
    session's own generator, the anneal and the calibration (the module's docstring)."""
    blocks: Blocks
    cfg: Config
    model: Model
    opt: nnx.Optimizer
    rng: np.random.Generator
    step: int = 0
    anneal: Optional[ladder.Anneal] = None
    calibration: Optional[dict] = None
    n_bodies: int = 0
    record: List[dict] = field(default_factory=list)
    written: int = 0

    @classmethod
    def new(cls, b: Blocks, keys: Sequence[str] = tuple(SEVEN), shape: Sequence[int] = crops.SHAPE,
            spacing: float = crops.SPACING_MM) -> "Session":
        """A session at step 0 from its blocks: the network initialised from the seed, the optimizer
        fresh, the generator seeded, the anneal set where the blocks give its length."""
        cfg = Config(keys=tuple(keys), widths=tuple(b.widths), shape=tuple(int(n) for n in shape), spacing=float(spacing),
                     groups=b.groups, normalise=b.normalise, architecture=b.architecture)
        model = Model(cfg, nnx.Rngs(b.seed))
        return cls(blocks=b, cfg=cfg, model=model, opt=optimiser(b, model), rng=np.random.default_rng(b.seed),
                   anneal=anneal_of(b))

    def position(self) -> Tuple[float, float]:
        """(w, lambda) at the current step, or where training starts when no anneal is set yet."""
        return self.anneal.at(self.step) if self.anneal is not None else (1.0, 0.0)

    def train(self, ex: train.Examples, steps: int, log_every: int = 0,
              on_step: Optional[Callable[[dict], None]] = None) -> List[dict]:
        """`steps` more steps on the examples, whole spines `batch` at a time, (w, lambda) from the
        anneal at each step; the anneal spans these steps when none is set yet. With the naming
        term on, every spine needs the same number of crops, the naming layer's field, which the
        session then keeps. Returns this call's rows, also appended to the session's record."""
        b = self.blocks
        groups = ex.spines()
        counts = {len(g) for g in groups}
        if b.naming:
            if len(counts) != 1:
                raise ValueError("every spine needs the same number of crops for the naming layer: %r" % [len(g) for g in groups])
            count = counts.pop()
            if self.n_bodies and count != self.n_bodies:
                raise ValueError("the naming field was %d bodies and these examples have %d" % (self.n_bodies, count))
            self.n_bodies = count
        if self.anneal is None:
            self.anneal = anneal_of(b, steps)
        nm = naming.prepare(self.cfg.keys, n_bodies=self.n_bodies) if b.naming else None
        step_fn = train.make_step(nm, b.batch if b.naming else 0, b.weights(), b.knee, b.spread_floor, b.rungs())
        rows = []
        for _ in range(steps):
            pick = self.rng.choice(len(groups), size=b.batch, replace=len(groups) < b.batch)
            idx = np.concatenate([groups[g] for g in pick])
            batch = train.batch_of(ex, idx)
            if b.intensity != "off":
                batch["input"] = jnp.asarray(augmented(ex.hu[idx], b.intensity, self.rng))
            w, lam = self.anneal.at(self.step)
            t0 = time.time()
            total, terms = step_fn(self.model, self.opt, batch, jnp.float32(w), jnp.float32(lam))
            row = {"step": self.step, "w": w, "lam": lam, "total": float(total), "seconds": time.time() - t0}
            row.update({k: float(v) for k, v in terms.items()})
            rows.append(row)
            self.record.append(row)
            self.step += 1
            if log_every and (self.step % log_every == 0 or len(rows) == steps):
                print("step %d w %.2f lam %.2f total %.3f distance %.2f mm" % (row["step"], w, lam, row["total"], row["distance_mm"]))
            if on_step is not None:
                on_step(row)
        return rows

    def continue_anneal(self, until: int) -> ladder.Anneal:
        """Both ramps rebased from where they stand at the current step to their ends by `until`,
        whatever the kind: a fixed schedule anneals to the ends from its fixed values, and a session
        not yet trained from the blocks' anneal at its first step."""
        base = self.anneal if self.anneal is not None else anneal_of(self.blocks, until)
        self.anneal = base.continued(self.step, until)
        return self.anneal

    def predict(self, ex: train.Examples) -> Dict[str, np.ndarray]:
        return train.predict(self.model, ex.hu)

    def calibrate(self, ex: train.Examples) -> dict:
        """The spread's factors fit on these examples, the validation set, by the calibrate block;
        kept in the session and applied unchanged by evaluate from then on."""
        out = self.predict(ex)
        factors = calibrate.fit(out["values"] - ex.values, out["sigma"], self.blocks.calibrate, self.blocks.coverage)
        self.calibration = calibrate.record(self.blocks.calibrate, self.blocks.coverage, factors, self.cfg.keys, len(ex))
        return self.calibration

    def factors(self) -> Optional[np.ndarray]:
        if self.calibration is None:
            return None
        return np.array([self.calibration["factors"][k] for k in self.cfg.keys])

    def evaluate(self, ex: train.Examples) -> Dict[str, object]:
        """train.evaluate on the CT-only path, with the calibration where one has been fit, and the
        session's step and position."""
        res = train.evaluate(self.model, ex, use_naming=self.blocks.naming, calibration=self.factors())
        res["step"] = self.step
        res["w"], res["lam"] = self.position()
        return res

    def status(self) -> dict:
        """One line's worth: the step, (w, lambda), the blocks that differ from the defaults and the
        calibration's kind."""
        w, lam = self.position()
        return {"step": self.step, "w": w, "lam": lam, "blocks": self.blocks.changed(), "digest": self.blocks.digest()[:12],
                "calibration": None if self.calibration is None else self.calibration["kind"]}

    def save(self, folder: str) -> dict:
        """state.npz, session.json and record.jsonl (appended) in the folder; returns session.json's record."""
        os.makedirs(folder, exist_ok=True)
        arrays = dict(flat_arrays(self.model, "model"), **flat_arrays(self.opt, "optimizer"))
        tmp = os.path.join(folder, STATE + ".tmp-%d" % os.getpid())
        with open(tmp, "wb") as f:
            np.savez(f, **arrays)
        os.replace(tmp, os.path.join(folder, STATE))
        meta = {"what": "an auto-anatomist session (autoanatomist/session.py): state.npz holds every leaf of the model's and "
                        "the optimizer's state by path; this file holds the rest; record.jsonl the steps' rows",
                "blocks": self.blocks.record(), "keys": list(self.cfg.keys), "shape": list(self.cfg.shape),
                "spacing": self.cfg.spacing, "step": self.step,
                "anneal": None if self.anneal is None else self.anneal.as_record(),
                "rng": self.rng.bit_generator.state, "calibration": self.calibration, "n_bodies": self.n_bodies,
                "arrays": len(arrays), "versions": versions()}
        with open(os.path.join(folder, META), "w") as f:
            json.dump(meta, f, indent=1)
            f.write("\n")
        with open(os.path.join(folder, RECORD), "a") as f:
            for row in self.record[self.written:]:
                f.write(json.dumps(row) + "\n")
        self.written = len(self.record)
        return meta

    @classmethod
    def load(cls, folder: str) -> "Session":
        """The session the folder holds, rebuilt from its blocks and filled from its arrays."""
        with open(os.path.join(folder, META)) as f:
            meta = json.load(f)
        s = cls.new(parse(meta["blocks"]["words"]), keys=meta["keys"], shape=meta["shape"], spacing=meta["spacing"])
        with np.load(os.path.join(folder, STATE)) as z:
            arrays = {k: z[k] for k in z.files}
        put_arrays(s.model, arrays, "model")
        put_arrays(s.opt, arrays, "optimizer")
        s.step = int(meta["step"])
        s.anneal = None if meta["anneal"] is None else ladder.Anneal.from_record(meta["anneal"])
        s.rng.bit_generator.state = meta["rng"]
        s.calibration = meta["calibration"]
        s.n_bodies = int(meta["n_bodies"])
        return s
