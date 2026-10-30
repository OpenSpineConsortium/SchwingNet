"""The degradation ladder, lambda from the instance mask to a soft threshold of the CT, and the
schedules of lambda and of the fusion weight w.

The privileged branch of the network (model.py) sees two channels beside the CT: the target
vertebra's mask and every vertebra's. lambda takes them down a ladder of three rungs, each a
third of [0, 1], each rung's progress a smoothstep so lambda's derivative is continuous within it:

1. identity fades (lambda 0 to 1/3): the target's channel is blended into every vertebra's, so at
   1/3 the branch no longer knows which voxels are the target's;
2. shape blurs (1/3 to 2/3): both channels are blurred by a Gaussian whose sigma grows to
   BLUR_MAX_MM, so the edges a mask states exactly become uncertain;
3. the mask gives way to the CT (2/3 to 1): both channels are blended into a soft threshold of the
   CT at BONE_HU (scanimport.intensity's dense bone), so at lambda 1 the branch sees a function of
   the CT alone, which a raw CT gives at test time.

Every step is a soft gate (gates.py), so the error of a network as a function of lambda, E(lambda),
has a derivative dE/dlambda that jax.grad computes (train.error_curve). The rungs and their order
are this module's design, from the owner's pasted notes (a perfect mask, then semantic bone, then
softer shapes, then HU thresholding), not a published schedule.

The schedules (Schedule) run lambda from 0 to 1 over the middle of the training steps and the
fusion weight w from 1 to 0 after it, each by a half cosine over its span, the two spans
overlapping by a tenth of the steps, so most of the degradation comes before the branch is taken
away, and at the end the network reads the CT alone (w = 0), with no mask asked for. Anneal is
the same schedule in absolute steps for a session that carries on (session.py): its spans are
shares of a stated number of steps rather than of one run's length, its kind places the two
ramps (blocks.py's schedule), and continue_anneal rebases both ramps from wherever they stand to
their ends by a later step, which is how a continued run anneals further without starting over.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Optional, Tuple

import jax.numpy as jnp

from . import gates

BLUR_MAX_MM = 4.0
THRESHOLD_WIDTH_HU = 60.0
LAMBDA_END, W_END = 1.0, 0.0            # where every anneal ends: the CT alone, no mask asked for
KINDS = ("lambda-then-w", "joint", "w-first", "fixed")


def smoothstep(u):
    u = jnp.clip(u, 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)


def rung(lam, k: int):
    """How far along rung k (0, 1 or 2) lambda is, 0 to 1, smoothly."""
    return smoothstep(3.0 * lam - k)


def degrade(masks, hu, lam, spacing_mm: float = 2.0, bone_hu: float = gates.BONE_HU,
            width_hu: float = THRESHOLD_WIDTH_HU, blur_max_mm: float = BLUR_MAX_MM):
    """The privileged channels at lambda: masks (batch, X, Y, Z, 2), target then every vertebra,
    hu (batch, X, Y, Z, 1); returns (batch, X, Y, Z, 2)."""
    target, every = masks[..., 0], masks[..., 1]
    a = rung(lam, 0)
    target = (1.0 - a) * target + a * every
    b = rung(lam, 1)
    sigma = jnp.maximum(b * blur_max_mm / spacing_mm, 1e-3)
    max_sigma = blur_max_mm / spacing_mm
    target = gates.gaussian_blur(target, sigma, max_sigma)
    every = gates.gaussian_blur(every, sigma, max_sigma)
    c = rung(lam, 2)
    bone = gates.soft_threshold(hu[..., 0], bone_hu, width_hu)
    target = (1.0 - c) * target + c * bone
    every = (1.0 - c) * every + c * bone
    return jnp.stack([target, every], -1)


@dataclass(frozen=True)
class Schedule:
    """lambda and w over `steps` training steps: lambda from 0 to 1 over the shares lam_span of the
    steps and w from 1 to 0 over w_span, which starts a tenth of the steps before lam_span ends,
    each by a half cosine; before a span its start value holds and after it its end value."""
    steps: int
    lam_span: Tuple[float, float] = (0.15, 0.55)
    w_span: Tuple[float, float] = (0.45, 0.85)

    @staticmethod
    def ramp(t: float, span: Tuple[float, float]) -> float:
        u = (t - span[0]) / max(span[1] - span[0], 1e-12)
        u = min(max(u, 0.0), 1.0)
        return 0.5 * (1.0 - math.cos(math.pi * u))

    def at(self, step: int) -> Tuple[float, float]:
        """(w, lambda) at a step."""
        t = step / max(self.steps - 1, 1)
        return 1.0 - self.ramp(t, self.w_span), self.ramp(t, self.lam_span)


@dataclass(frozen=True)
class Anneal:
    """lambda and w in absolute steps, a session's schedule: over `steps` steps, lambda from 0 to
    LAMBDA_END and w from 1 to W_END by half cosines over spans that are shares of the steps, placed
    by the kind (lambda-then-w: lambda over lam_span and w over w_span, Schedule's numbers to the
    bit when steps is the run's length; joint: both over lam_span; w-first: the spans swapped, so
    the earlier one is w's; fixed: w_fixed and lam_fixed throughout) and, once continued, both from
    where they stood at that step to their ends by the step named. as_record and from_record carry
    it as plain numbers (session.json)."""
    kind: str = "lambda-then-w"
    steps: int = 1
    lam_span: Tuple[float, float] = (0.15, 0.55)
    w_span: Tuple[float, float] = (0.45, 0.85)
    lam_fixed: float = 0.0
    w_fixed: float = 1.0
    rebased: Optional[dict] = None          # {"from": step, "until": step, "w": w then, "lam": lambda then}

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError("schedule takes %s, not %r" % (", ".join(KINDS), self.kind))
        if self.steps < 1:
            raise ValueError("an anneal takes at least one step, not %r" % self.steps)

    def spans(self) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """(w's span, lambda's span) by the kind."""
        if self.kind == "lambda-then-w":
            return self.w_span, self.lam_span
        if self.kind == "joint":
            return self.lam_span, self.lam_span
        return self.lam_span, self.w_span

    def at(self, step: int) -> Tuple[float, float]:
        """(w, lambda) at a step."""
        if self.rebased is not None:
            r = self.rebased
            u = (step - r["from"]) / max(r["until"] - r["from"], 1e-12)
            h = Schedule.ramp(u, (0.0, 1.0))
            return r["w"] + (W_END - r["w"]) * h, r["lam"] + (LAMBDA_END - r["lam"]) * h
        if self.kind == "fixed":
            return self.w_fixed, self.lam_fixed
        w_span, lam_span = self.spans()
        t = step / max(self.steps - 1, 1)
        return 1.0 - Schedule.ramp(t, w_span), Schedule.ramp(t, lam_span)

    def continued(self, step: int, until: int) -> "Anneal":
        """The anneal rebased at `step`: both ramps from (w, lambda) there to their ends by `until`."""
        if until <= step:
            raise ValueError("continue_anneal needs a step after the current one (%d), not %r" % (step, until))
        w, lam = self.at(step)
        return replace(self, rebased={"from": int(step), "until": int(until), "w": float(w), "lam": float(lam)})

    def as_record(self) -> dict:
        return {"kind": self.kind, "steps": self.steps, "lam_span": list(self.lam_span), "w_span": list(self.w_span),
                "lam_fixed": self.lam_fixed, "w_fixed": self.w_fixed, "rebased": self.rebased}

    @staticmethod
    def from_record(d: dict) -> "Anneal":
        return Anneal(kind=d["kind"], steps=int(d["steps"]), lam_span=tuple(d["lam_span"]), w_span=tuple(d["w_span"]),
                      lam_fixed=float(d["lam_fixed"]), w_fixed=float(d["w_fixed"]), rebased=d.get("rebased"))
