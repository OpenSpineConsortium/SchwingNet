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

Three arms of a second screen, from the owner's question of 30 October 2026 about free energy
perturbation's lambda schedules (Lambda-ABF, arXiv 2307.08006) and his choice of four arms at 16:52
UTC that day; each ends where every anneal ends, lambda 1 and w 0:

- cyclic (Anneal's kind): lambda-then-w twice, each pass in half the steps, and between the passes
  back to lambda CYCLE_LAM and w CYCLE_W, a re-anneal from a state the first pass left;
- adaptive (Anneal's kind, with Adapt and adapt): w on lambda-then-w's clock, and lambda moved at
  checks by the error's own slope, dE/dlambda on the batch just trained, faster where E is flat in
  lambda and slower where it is steep, half a move back where E jumped by more than the slope said,
  and never behind a floor that reaches 1 a tenth of the steps after lam_span ends, so every run
  still ends at lambda 1 and w 0;
- overlapping rungs (degrade's rung_span, blocks.py's ladder): each rung over half of lambda, a
  quarter apart, so the three move at once in places, as Lambda-ABF staggers its two lambdas on one.

The fourth arm, the restraint, is a loss term (train.py's restraint).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Optional, Sequence, Tuple

import jax.numpy as jnp

from . import gates

BLUR_MAX_MM = 4.0
THRESHOLD_WIDTH_HU = 60.0
LAMBDA_END, W_END = 1.0, 0.0            # where every anneal ends: the CT alone, no mask asked for
KINDS = ("lambda-then-w", "joint", "w-first", "fixed", "cyclic", "adaptive")
# How much of lambda each rung spans (blocks.py's ladder): in turn, a third each by rung's own
# arithmetic; overlapping, half each, a quarter apart; together, all of lambda each.
RUNG_SPANS = {"in-turn": None, "overlapping": 0.5, "together": 1.0}
CYCLE_LAM, CYCLE_W = 0.5, 0.3           # where schedule=cyclic goes back to between its passes
ADAPT_EVERY = 20                        # steps between two checks of schedule=adaptive
ADAPT_SLACK = 0.1                       # its floor reaches lambda 1 this share of the steps after lam_span ends
ADAPT_GAIN = (0.5, 2.0)                 # the least and the most of the nominal move one check makes
ADAPT_JUMP = 3.0                        # a rise in E this many times the slope's promise takes half the move back


def smoothstep(u):
    u = jnp.clip(u, 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)


def rung(lam, k: int, span: Optional[float] = None):
    """How far along rung k (0, 1 or 2) lambda is, 0 to 1, smoothly: in turn, each rung over its own
    third of lambda (span None); else each over `span` of lambda, the three starting evenly from 0
    so that the last ends at 1 (span 1/2: 0 to 1/2, 1/4 to 3/4 and 1/2 to 1; span 1: all of it)."""
    if span is None:
        return smoothstep(3.0 * lam - k)
    start = k * (1.0 - span) / 2.0
    return smoothstep((lam - start) / span)


def degrade(masks, hu, lam, spacing_mm: float = 2.0, bone_hu: float = gates.BONE_HU,
            width_hu: float = THRESHOLD_WIDTH_HU, blur_max_mm: float = BLUR_MAX_MM,
            rung_span: Optional[float] = None):
    """The privileged channels at lambda: masks (batch, X, Y, Z, 2), target then every vertebra,
    hu (batch, X, Y, Z, 1); returns (batch, X, Y, Z, 2). rung_span is rung's span, None in turn."""
    target, every = masks[..., 0], masks[..., 1]
    a = rung(lam, 0, rung_span)
    target = (1.0 - a) * target + a * every
    b = rung(lam, 1, rung_span)
    sigma = jnp.maximum(b * blur_max_mm / spacing_mm, 1e-3)
    max_sigma = blur_max_mm / spacing_mm
    target = gates.gaussian_blur(target, sigma, max_sigma)
    every = gates.gaussian_blur(every, sigma, max_sigma)
    c = rung(lam, 2, rung_span)
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


def along(t: float, knots: Sequence[Tuple[float, float]]) -> float:
    """A path through knots ((share, value), ...) in order of share: the first value before the
    first knot, the last after the last, and a half cosine from each value to the next between."""
    if t <= knots[0][0]:
        return knots[0][1]
    for (t0, v0), (t1, v1) in zip(knots, knots[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * Schedule.ramp(t, (t0, t1))
    return knots[-1][1]


@dataclass(frozen=True)
class Anneal:
    """lambda and w in absolute steps, a session's schedule: over `steps` steps, lambda from 0 to
    LAMBDA_END and w from 1 to W_END by half cosines over spans that are shares of the steps, placed
    by the kind (lambda-then-w: lambda over lam_span and w over w_span, Schedule's numbers to the
    bit when steps is the run's length; joint: both over lam_span; w-first: the spans swapped, so
    the earlier one is w's; fixed: w_fixed and lam_fixed throughout; cyclic: lambda-then-w's two
    ramps twice, each pass in half the steps, and between the passes, from where the first pass ends
    to where the second begins, back to lambda cycle_lam and w cycle_w; adaptive: w as in
    lambda-then-w and lambda at least its floor, a half cosine over lam_span stretched by
    ADAPT_SLACK, which a session's checks (Adapt) may run ahead of) and, once continued, both from
    where they stood at that step to their ends by the step named. as_record and from_record carry
    it as plain numbers (session.json)."""
    kind: str = "lambda-then-w"
    steps: int = 1
    lam_span: Tuple[float, float] = (0.15, 0.55)
    w_span: Tuple[float, float] = (0.45, 0.85)
    lam_fixed: float = 0.0
    w_fixed: float = 1.0
    rebased: Optional[dict] = None          # {"from": step, "until": step, "w": w then, "lam": lambda then}
    cycle_lam: float = CYCLE_LAM
    cycle_w: float = CYCLE_W

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError("schedule takes %s, not %r" % (", ".join(KINDS), self.kind))
        if self.steps < 1:
            raise ValueError("an anneal takes at least one step, not %r" % self.steps)

    def spans(self) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """(w's span, lambda's span) by the kind; adaptive's lambda span is its floor's."""
        if self.kind == "lambda-then-w":
            return self.w_span, self.lam_span
        if self.kind == "joint":
            return self.lam_span, self.lam_span
        if self.kind == "adaptive":
            return self.w_span, self.floor_span()
        return self.lam_span, self.w_span

    def floor_span(self) -> Tuple[float, float]:
        """The shares over which schedule=adaptive's floor takes lambda from 0 to 1."""
        return self.lam_span[0], min(1.0, self.lam_span[1] + ADAPT_SLACK)

    def cycle_knots(self) -> Tuple[Tuple[Tuple[float, float], ...], Tuple[Tuple[float, float], ...]]:
        """schedule=cyclic's knots for w and for lambda, ((share, value), ...): the first pass over the
        spans halved, the second over the halved spans moved on by half the steps, and between them
        back to w cycle_w and lambda cycle_lam."""
        (l0, l1), (w0, w1) = (tuple(s / 2.0 for s in span) for span in (self.lam_span, self.w_span))
        (m0, m1), (v0, v1) = (tuple(0.5 + s / 2.0 for s in span) for span in (self.lam_span, self.w_span))
        back, on = max(l1, w1), min(m0, v0)
        w = ((w0, 1.0), (w1, W_END), (back, W_END), (on, self.cycle_w), (v0, self.cycle_w), (v1, W_END))
        lam = ((l0, 0.0), (l1, LAMBDA_END), (back, LAMBDA_END), (on, self.cycle_lam), (m0, self.cycle_lam),
               (m1, LAMBDA_END))
        return w, lam

    def at(self, step: int) -> Tuple[float, float]:
        """(w, lambda) at a step; under adaptive, lambda's floor."""
        if self.rebased is not None:
            r = self.rebased
            u = (step - r["from"]) / max(r["until"] - r["from"], 1e-12)
            h = Schedule.ramp(u, (0.0, 1.0))
            return r["w"] + (W_END - r["w"]) * h, r["lam"] + (LAMBDA_END - r["lam"]) * h
        if self.kind == "fixed":
            return self.w_fixed, self.lam_fixed
        t = step / max(self.steps - 1, 1)
        if self.kind == "cyclic":
            w_knots, lam_knots = self.cycle_knots()
            return along(t, w_knots), along(t, lam_knots)
        w_span, lam_span = self.spans()
        return 1.0 - Schedule.ramp(t, w_span), Schedule.ramp(t, lam_span)

    def adapting(self, step: int) -> bool:
        """Whether a session's checks steer lambda at this step: under adaptive, not continued, from
        lam_span's start on."""
        return (self.kind == "adaptive" and self.rebased is None
                and step / max(self.steps - 1, 1) >= self.lam_span[0])

    def nominal(self, step: int, lam: float, every: int) -> float:
        """schedule=adaptive's even move at a check: what takes lambda from where it stands to 1 by
        lam_span's end in equal moves over the checks left, or the rest of the way once past it."""
        end = self.lam_span[1] * max(self.steps - 1, 1)
        left = (end - step) / max(every, 1)
        return (LAMBDA_END - lam) / max(left, 1.0)

    def continued(self, step: int, until: int) -> "Anneal":
        """The anneal rebased at `step`: both ramps from (w, lambda) there to their ends by `until`."""
        if until <= step:
            raise ValueError("continue_anneal needs a step after the current one (%d), not %r" % (step, until))
        w, lam = self.at(step)
        return replace(self, rebased={"from": int(step), "until": int(until), "w": float(w), "lam": float(lam)})

    def as_record(self) -> dict:
        return {"kind": self.kind, "steps": self.steps, "lam_span": list(self.lam_span), "w_span": list(self.w_span),
                "lam_fixed": self.lam_fixed, "w_fixed": self.w_fixed, "rebased": self.rebased,
                "cycle_lam": self.cycle_lam, "cycle_w": self.cycle_w}

    @staticmethod
    def from_record(d: dict) -> "Anneal":
        """The anneal a record names; a record written before the cycle's numbers takes their defaults."""
        return Anneal(kind=d["kind"], steps=int(d["steps"]), lam_span=tuple(d["lam_span"]), w_span=tuple(d["w_span"]),
                      lam_fixed=float(d["lam_fixed"]), w_fixed=float(d["w_fixed"]), rebased=d.get("rebased"),
                      cycle_lam=float(d.get("cycle_lam", CYCLE_LAM)), cycle_w=float(d.get("cycle_w", CYCLE_W)))


@dataclass(frozen=True)
class Adapt:
    """schedule=adaptive's controller between its checks: lam, where it has taken lambda for the
    steps to the next check (the session takes the larger of it and the floor); last, the lambda in
    force over the steps just checked; pace, the mean of |dE/dlambda| over its checks; checks, how
    many it has made. as_record and from_record carry it as plain numbers (session.json)."""
    lam: float = 0.0
    last: float = 0.0
    pace: float = 0.0
    checks: int = 0

    def as_record(self) -> dict:
        return {"lam": self.lam, "last": self.last, "pace": self.pace, "checks": self.checks}

    @staticmethod
    def from_record(d: dict) -> "Adapt":
        return Adapt(lam=float(d["lam"]), last=float(d["last"]), pace=float(d["pace"]), checks=int(d["checks"]))


def adapt(a: Adapt, now: float, rise: float, slope: float, nominal: float) -> Adapt:
    """One check of the adaptive schedule. now is the lambda in force over the steps just trained,
    rise is E at now less E at the last check's lambda, both read on the batch just trained so that
    the batch's own noise cancels, slope is dE/dlambda at now on that batch, and nominal is the even
    move (Anneal.nominal). Where lambda went up since the last check and E rose by more than
    ADAPT_JUMP times what the mean slope promised for that move, lambda goes half that move back;
    else it moves on by nominal times the mean of |slope| over this one's, held within ADAPT_GAIN,
    so faster where E is flat in lambda and slower where it is steep. lambda stays in [0, 1]."""
    g = abs(float(slope))
    pace = g if a.checks == 0 else a.pace + (g - a.pace) / (a.checks + 1)
    moved = now - a.last
    if a.checks > 0 and moved > 0.0 and rise > ADAPT_JUMP * a.pace * moved:
        step = -moved / 2.0
    else:
        lo, hi = ADAPT_GAIN
        step = nominal * (hi if g <= 0.0 else min(max(pace / g, lo), hi))
    return Adapt(lam=min(max(now + step, 0.0), LAMBDA_END), last=float(now), pace=pace, checks=a.checks + 1)
