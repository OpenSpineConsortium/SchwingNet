"""The smoke run: the whole path once, on phantoms, on this machine, with its record.

    python -m autoanatomist.smoke records/autoanatomist-2026-10-29      # from bordercall's root

It draws phantoms, TRAIN_SPINES to train on and HELD_SPINES held out, each a column of COUNT
consecutive levels, reads them with the oracle, trains the network for STEPS steps on the
schedule (lambda from 0 to 1 and w from 1 to 0 after it, the two ramps overlapping by a tenth of
the steps) and writes smoke.json: the settings, every
step's losses, the held-out evaluation of the CT-only path before training and after, E(lambda)
and dE/dlambda on the held-out crops at w 1 after training, the CT-only path's seconds per crop
and the versions of jax, flax and optax. It draws three figures under figures/: the oracle's lines
on one held-out vertebra's mask and on its CT, and the network's lines on the same CT.

Nothing in it is a result. A few minutes of training on a dozen phantoms says the path runs from
the oracle to the named bodies and that its losses fall, not how well a trained network will
place a landmark on a real CT. No weight is written.
"""
from __future__ import annotations

import json
import os
import platform
import sys
import time

import jax
import jax.numpy as jnp
import numpy as np
from flax import nnx

from . import render, train
from .model import Config

TRAIN_SPINES, HELD_SPINES, COUNT, STEPS = 8, 4, 3, 150
SPINES_PER_BATCH, LR = 2, 2e-3
SEEDS = {"train_examples": 1, "held_examples": 2, "untrained_model": 0, "run": 0}
PHANTOM = {"spacing_mm": 1.25, "noise_hu": 20.0, "sub": 1, "jitter": True}
TRAIN_STARTS = ("T11", "T12", "L1", "L2", "L3")
HELD_STARTS = ("T12", "L1", "L2", "L3")
LAMS = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)


def versions() -> dict:
    import flax
    import optax
    return {"python": platform.python_version(), "jax": jax.__version__, "flax": flax.__version__,
            "optax": optax.__version__, "numpy": np.__version__, "device": str(jax.devices()[0]),
            "cpus": os.cpu_count()}


def figures(run: train.Run, held: train.Examples, out_dir: str) -> dict:
    """The oracle's lines on the first held-out phantom's middle vertebra, mask and CT, and the
    network's lines (the CT-only path) on the same CT."""
    os.makedirs(out_dir, exist_ok=True)
    i = int(held.spines()[0][COUNT // 2])
    ph, r, cf = held.phantoms[0], held.readings[i], held.frames[i]
    keys = list(run.model.cfg.keys)
    pred = nnx.jit(lambda m, hu: m.ct_only(hu))(run.model, jnp.asarray(held.hu[i:i + 1]))
    mine = train.as_reading(r, cf, np.asarray(pred["points"][0]), np.asarray(pred["values"][0]), keys)
    names = {"oracle_mask": os.path.join(out_dir, "oracle_lines_mask.png"),
             "oracle_ct": os.path.join(out_dir, "oracle_lines_ct.png"),
             "network_ct": os.path.join(out_dir, "network_lines_ct.png")}
    render.draw(r, ph.labels, ph.affine, names["oracle_mask"], kind="mask", keys=keys,
                title="The oracle's lines on %s's mask (phantom)" % r.level)
    render.draw(r, ph.hu, ph.affine, names["oracle_ct"], kind="ct", keys=keys,
                title="The oracle's lines on %s's CT (phantom)" % r.level)
    render.draw(mine, ph.hu, ph.affine, names["network_ct"], kind="ct", keys=keys,
                title="The network's lines on %s's CT, from the CT alone (smoke run)" % r.level)
    return {k: os.path.basename(v) for k, v in names.items()}


def main(out_dir: str) -> dict:
    cfg = Config()
    t0 = time.time()
    ex = train.make_examples(cfg, TRAIN_SPINES, COUNT, seed=SEEDS["train_examples"], starts=TRAIN_STARTS, **PHANTOM)
    held = train.make_examples(cfg, HELD_SPINES, COUNT, seed=SEEDS["held_examples"], starts=HELD_STARTS, keep=True,
                               **PHANTOM)
    made = time.time() - t0
    untrained = train.Run(model=train.Model(cfg, nnx.Rngs(SEEDS["untrained_model"])), schedule=None, record=[])
    before = train.evaluate(untrained.model, held)
    t0 = time.time()
    run = train.train(ex, cfg, STEPS, spines_per_batch=SPINES_PER_BATCH, lr=LR, seed=SEEDS["run"], log_every=25)
    trained_s = time.time() - t0
    after = train.evaluate(run.model, held)
    batch = train.batch_of(held, np.arange(len(held)))
    E, dE = train.error_curve(run.model, batch, LAMS, w=1.0)
    record = {
        "what": "the auto-anatomist's smoke run: phantoms read by the stand-in oracle, a few minutes of training "
                "on this machine's CPU; not a result, and no weight written",
        "command": "python -m autoanatomist.smoke " + out_dir,
        "settings": {"config": {"keys": list(cfg.keys), "widths": list(cfg.widths), "shape": list(cfg.shape),
                                "spacing_mm": cfg.spacing},
                     "train_spines": TRAIN_SPINES, "held_spines": HELD_SPINES, "count": COUNT, "steps": STEPS,
                     "train_starts": list(TRAIN_STARTS), "held_starts": list(HELD_STARTS),
                     "spines_per_batch": SPINES_PER_BATCH, "lr": LR, "seeds": SEEDS, "phantoms": PHANTOM,
                     "loss_weights": train.LOSS_WEIGHTS, "huber_knee_mm": train.HUBER_KNEE_MM,
                     "spread_floor_mm": train.SPREAD_FLOOR_MM,
                     "schedule": {"lam_span": list(run.schedule.lam_span), "w_span": list(run.schedule.w_span)}},
        "examples": {"train": ex.meta, "held": held.meta, "seconds": made},
        "record": run.record,
        "train_seconds": trained_s,
        "held_before": before,
        "held_after": after,
        "error_curve": {"w": 1.0, "lam": list(LAMS), "E_mm": E.tolist(), "dE_dlam": dE.tolist()},
        "timing": train.timing(run.model),
        "versions": versions(),
    }
    record["figures"] = figures(run, held, os.path.join(out_dir, "figures"))
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "smoke.json"), "w") as f:
        json.dump(record, f, indent=1, default=float)
        f.write("\n")
    return record


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m autoanatomist.smoke OUT_DIR")
    rec = main(sys.argv[1])
    print(json.dumps({k: rec[k] for k in ("held_before", "held_after", "error_curve", "timing")}, indent=1, default=float))
