"""The annealing demo: a network of the smoke run's widths trained on one measurement, with a snapshot
every few steps of the width it measures on held-out CTs from the CT alone, drawn as one figure with
a slider over the steps (notebooks/anneal_demo.ipynb runs it in Colab).

    python -m autoanatomist.demo demo.html --record demo.json    # from bordercall's root; needs plotly, which no requirements file pins

The run takes smoke.py's phantoms, seeds, learning rate, batches and schedule (lambda from 0 to 1
over steps 23 to 82 of 150, then w from 1 to 0 over steps 68 to 127), but trains one measurement,
the upper end-plate's width (Panjabi's EPWu), with the naming layer off, where smoke.py trains all
seven with it on; its network is train.train's to the bit for that measurement with the naming
layer off (tests/test_anneal_demo.py). Each snapshot holds the last step's lambda and w, and the
network's two end-plate landmarks and its width on every held-out crop, read by model.ct_only, the
path a raw CT takes, with no mask anywhere. The reference is the oracle's width and its two points,
read off each held-out vertebra's mask. On the shown vertebra's CT the figure also draws what the
mask branch would be given of that vertebra at each snapshot's lambda (ladder.degrade: its own mask
fading into every vertebra's, blurring and giving way to a soft threshold of the CT), at the weight
w, so it fades out as the network comes to read the CT alone; the network's reading never sees it.

A demonstration on phantoms, not a result: minutes of training on a CPU, nothing kept, no real CT.
The held-out crops are placed as the training crops are, from the oracle's frame turned and moved at
random; placing a crop from the CT alone (crops.from_found) is not measured yet.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import os
import pickle
import platform
import sys
import time
from dataclasses import dataclass
from typing import Iterator, List, Optional, Tuple

import jax
import jax.numpy as jnp
import numpy as np
import optax
from flax import nnx
from scipy import ndimage

from . import gates, ladder, smoke, train
from .model import Config, Model

KEY = "endplate"                    # Panjabi's EPWu, the upper end-plate's width
EVERY = 5                           # steps between snapshots
# Okabe and Ito's colours, apart for colour-blind readers: the oracle's reference, the network's
# reading from the CT alone, and the mask branch with its weight w.
BLUE, ORANGE, GREEN = "#0072B2", "#D55E00", "#009E73"
BONE = "#D9CFB8"
BONE_OPACITY = 0.25                 # see-through, so the widths on the end plate show
MASK_OPACITY = 0.4                  # the mask input's surface at w = 1; at w it is MASK_OPACITY times w
MOVING = [1, 3, 6, 8]               # the traces a frame changes: the mask input, the network's width, the dots, its line
WIDTH_PX, HEIGHT_PX = 1060, 680     # the figure's fixed size, whatever the window or the notebook's cell
LAM, W = "λ", "w"                 # lambda, as the figure prints it
TEST_SEED = 100                     # the test phantoms' seed, far from the run's (smoke.SEEDS)
TEST_COLUMNS = 6                    # columns of smoke.COUNT vertebrae in each test set
TEST_HEIGHT_PX = 470                # the test figure's height, at the demo figure's width
GREY = "#7F7F7F"


@dataclass
class Snapshot:
    """The network after `step` steps: the last step's w and lambda (the first step's before any),
    and from the CT alone the two end-plate landmarks on every held-out crop (H, 2, 3), in the
    crop's millimetres, and the width between them (H,)."""
    step: int
    w: float
    lam: float
    points: np.ndarray
    widths: np.ndarray


@dataclass
class Demo:
    """A run's snapshots and what they are read against: each held-out crop's CT in HU (H, X, Y, Z),
    its mask channels (H, X, Y, Z, 2), the target's then every vertebra's, which the figure takes
    down the ladder and the network's reading never sees, and its level; the oracle's two points and
    width there, the crop's axis ticks and spacing in millimetres, w and lambda at every step, every
    step's loss and the seconds the run took; and the network's settings, its weights after the last
    step and the training phantoms' mean width, for the test on phantoms it never saw."""
    snapshots: List[Snapshot]
    hu: np.ndarray
    masks: np.ndarray
    levels: List[str]
    reference_points: np.ndarray
    reference_widths: np.ndarray
    ticks: List[np.ndarray]
    spacing: float
    w: np.ndarray
    lam: np.ndarray
    losses: List[float]
    seconds: float
    cfg: Config
    params: dict
    train_mean: float

    @property
    def steps(self) -> int:
        return len(self.losses)

    def error_mm(self, k: int) -> float:
        """The mean absolute error of snapshot k's widths against the oracle's, over the held-out crops."""
        return float(np.nanmean(np.abs(self.snapshots[k].widths - self.reference_widths)))

    def typical(self) -> int:
        """The held-out crop whose error after the last step is the median of all of them (the lower
        of the two middle ones for an even count): the figure's vertebra unless one is named, so
        that it shows neither the best reading nor the worst."""
        errors = np.abs(self.snapshots[-1].widths - self.reference_widths)
        return int(np.argsort(errors, kind="stable")[(len(errors) - 1) // 2])


def examples(cfg: Config) -> Tuple[train.Examples, train.Examples]:
    """The smoke run's phantoms for cfg: its training columns and its held-out ones."""
    ex = train.make_examples(cfg, smoke.TRAIN_SPINES, smoke.COUNT, seed=smoke.SEEDS["train_examples"],
                             starts=smoke.TRAIN_STARTS, **smoke.PHANTOM)
    held = train.make_examples(cfg, smoke.HELD_SPINES, smoke.COUNT, seed=smoke.SEEDS["held_examples"],
                               starts=smoke.HELD_STARTS, **smoke.PHANTOM)
    return ex, held


class Snapper:
    """Takes snapshots of one model: its CT-only reading of the held-out crops, jitted once."""

    def __init__(self, held: train.Examples):
        self.hu = jnp.asarray(held.hu)
        self.read = nnx.jit(lambda m, hu: m.ct_only(hu))

    def take(self, model: Model, step: int, w: float, lam: float) -> Snapshot:
        out = self.read(model, self.hu)
        return Snapshot(step=step, w=float(w), lam=float(lam), points=np.asarray(out["points"]),
                        widths=np.asarray(out["values"])[:, 0])


def anneal(ex: train.Examples, held: train.Examples, cfg: Config, steps: int, every: int = EVERY,
           log_every: int = 0) -> Tuple[Model, List[Snapshot], List[float]]:
    """train.train with the naming layer off, step for step (the same model, optimiser, batches and
    schedule at smoke.py's batch, rate and seed, so the network is train.train's to the bit), with
    a snapshot before the first step, after every `every` steps and after the last."""
    groups = ex.spines()
    model = Model(cfg, nnx.Rngs(smoke.SEEDS["run"]))
    opt = nnx.Optimizer(model, optax.adamw(smoke.LR), wrt=nnx.Param)
    schedule = ladder.Schedule(steps)
    step = train.make_step(None, 0)
    rng = np.random.default_rng(smoke.SEEDS["run"])
    snapper = Snapper(held)
    snapshots, losses = [snapper.take(model, 0, *schedule.at(0))], []
    for s in range(steps):
        pick = rng.choice(len(groups), size=smoke.SPINES_PER_BATCH, replace=len(groups) < smoke.SPINES_PER_BATCH)
        batch = train.batch_of(ex, np.concatenate([groups[g] for g in pick]))
        w, lam = schedule.at(s)
        total, _ = step(model, opt, batch, jnp.float32(w), jnp.float32(lam))
        losses.append(float(total))
        if (s + 1) % every == 0 or s + 1 == steps:
            snapshots.append(snapper.take(model, s + 1, w, lam))
        if log_every and ((s + 1) % log_every == 0 or s + 1 == steps):
            print(progress(snapshots[-1], held, s + 1, steps), flush=True)
    return model, snapshots, losses


def progress(snap: Snapshot, held: train.Examples, step: int, steps: int) -> str:
    error = float(np.nanmean(np.abs(snap.widths - held.values[:, 0])))
    return "step %d of %d: w %.2f, lambda %.2f, the width's mean error on the held-out CTs %.1f mm" % (
        step, steps, snap.w, snap.lam, error)


def run(steps: int = smoke.STEPS, every: int = EVERY, cfg: Optional[Config] = None, log_every: int = 25) -> Demo:
    """The demo: the phantoms, the annealed training with its snapshots, and what they are read against."""
    cfg = cfg or Config(keys=(KEY,))
    t0 = time.time()
    ex, held = examples(cfg)
    model, snapshots, losses = anneal(ex, held, cfg, steps, every, log_every)
    schedule = ladder.Schedule(steps)
    w, lam = np.array([schedule.at(s) for s in range(steps)]).T
    params = jax.tree.map(np.asarray, nnx.to_pure_dict(nnx.state(model, nnx.Param)))
    return Demo(snapshots=snapshots, hu=held.hu[..., 0], masks=held.masks, levels=[r.level for r in held.readings],
                reference_points=held.targets, reference_widths=held.values[:, 0],
                ticks=held.frames[0].axis_ticks(), spacing=cfg.spacing, w=w, lam=lam, losses=losses,
                seconds=time.time() - t0, cfg=cfg, params=params, train_mean=float(np.mean(ex.values[:, 0])))


def pooled(volume: np.ndarray) -> np.ndarray:
    """A volume's means over blocks of two voxels a side, an odd last voxel on an axis left out, so
    that a page carries each frame's mask input at an eighth of the crop's voxels."""
    X, Y, Z = (n // 2 * 2 for n in volume.shape[:3])
    return volume[:X, :Y, :Z].reshape(X // 2, 2, Y // 2, 2, Z // 2, 2).mean(axis=(1, 3, 5))


def pooled_ticks(ticks: List[np.ndarray]) -> List[np.ndarray]:
    """The centres of pooled's blocks, in the crop's millimetres."""
    return [t[:len(t) // 2 * 2].reshape(-1, 2).mean(1) for t in ticks]


def mask_values(demo: Demo, vertebra: int, lam: float) -> np.ndarray:
    """What the mask branch would be given of a held-out vertebra at lambda, the target's channel
    after ladder.degrade, pooled. The figure draws it; the network's reading of the vertebra never
    sees it."""
    out = ladder.degrade(jnp.asarray(demo.masks[vertebra:vertebra + 1]), jnp.asarray(demo.hu[vertebra:vertebra + 1, ..., None]),
                         jnp.float32(lam), spacing_mm=demo.spacing)
    return pooled(np.asarray(out[0, ..., 0], np.float64))


def surface(demo: Demo, vertebra: int):
    """The held-out crop's CT as plotly's isosurface at the ladder's bone level (gates.BONE_HU),
    lightly smoothed against the phantom's noise: a raw CT, no mask in it."""
    import plotly.graph_objects as go
    x, y, z = np.meshgrid(*demo.ticks, indexing="ij")
    hu = ndimage.gaussian_filter(np.asarray(demo.hu[vertebra], np.float32), 1.0)
    return go.Isosurface(x=x.ravel(), y=y.ravel(), z=z.ravel(), value=hu.ravel(), isomin=gates.BONE_HU,
                         isomax=gates.BONE_HU, surface_count=1, caps=dict(x_show=False, y_show=False, z_show=False),
                         colorscale=[[0.0, BONE], [1.0, BONE]], showscale=False, opacity=BONE_OPACITY,
                         lighting=dict(ambient=0.55, diffuse=0.7, specular=0.15), hoverinfo="skip",
                         name="the CT at %d HU, no mask" % gates.BONE_HU, showlegend=True)


def mask_frame(demo: Demo, vertebra: int, snap: Snapshot) -> dict:
    """What a frame changes of the mask input's surface: its values at the snapshot's lambda, to two
    places (a page's size), and its opacity, MASK_OPACITY times w, so it fades out as w falls to 0."""
    values = np.round(mask_values(demo, vertebra, snap.lam), 2)
    return dict(type="isosurface", value=values.ravel().tolist(), opacity=MASK_OPACITY * max(snap.w, 0.0))


def mask_surface(demo: Demo, vertebra: int, snap: Snapshot):
    """The mask input on the shown vertebra, in green where it is one half, on pooled's grid."""
    import plotly.graph_objects as go
    x, y, z = np.meshgrid(*pooled_ticks(demo.ticks), indexing="ij")
    return go.Isosurface(x=x.ravel(), y=y.ravel(), z=z.ravel(), isomin=0.5, isomax=0.5, surface_count=1,
                         caps=dict(x_show=False, y_show=False, z_show=False), colorscale=[[0.0, GREEN], [1.0, GREEN]],
                         showscale=False, hoverinfo="skip", showlegend=True,
                         name="the mask branch's input at %s, at weight %s (training only)" % (LAM, W),
                         **{k: v for k, v in mask_frame(demo, vertebra, snap).items() if k != "type"})


def chord(points: np.ndarray, colour: str, name: str):
    import plotly.graph_objects as go
    return go.Scatter3d(x=points[:, 0], y=points[:, 1], z=points[:, 2], mode="lines+markers", name=name,
                        line=dict(color=colour, width=12), marker=dict(color=colour, size=5), hoverinfo="skip")


def reference_chord(demo: Demo, vertebra: int):
    """The oracle's width, its length in the legend."""
    return chord(demo.reference_points[vertebra], BLUE,
                 "the reference, from the mask: %.1f mm" % demo.reference_widths[vertebra])


def network_chord(snap: Snapshot, vertebra: int):
    """The network's width from the CT alone at a snapshot, its length in the legend."""
    return chord(snap.points[vertebra], ORANGE, "the network, from the CT alone: %.1f mm" % snap.widths[vertebra])


def schedule_marks(snap: Snapshot):
    import plotly.graph_objects as go
    return go.Scatter(x=[snap.step, snap.step], y=[snap.lam, snap.w], mode="markers", showlegend=False,
                      marker=dict(color=["#000000", GREEN], size=10), hoverinfo="skip")


def width_line(demo: Demo, k: int, vertebra: int):
    import plotly.graph_objects as go
    shown = demo.snapshots[:k + 1]
    return go.Scatter(x=[s.step for s in shown], y=[float(s.widths[vertebra]) for s in shown], mode="lines+markers",
                      line=dict(color=ORANGE, width=3), marker=dict(size=5), name="the network, from the CT alone",
                      showlegend=False)


def title(demo: Demo, k: int, vertebra: int) -> str:
    snap = demo.snapshots[k]
    return ("<b>After %d of %d steps: %s %.2f, %s %.2f</b><br>%s's end-plate width %.1f mm from the CT alone, "
            "the reference %.1f mm; mean error over the %d held-out vertebrae %.1f mm" % (
                snap.step, demo.steps, LAM, snap.lam, W, snap.w, demo.levels[vertebra], snap.widths[vertebra],
                demo.reference_widths[vertebra], len(demo.reference_widths), demo.error_mm(k)))


def figure(demo: Demo, vertebra: Optional[int] = None):
    """The demo drawn with a slider over the snapshots, at a fixed size. Left: one held-out vertebra's
    CT as a bone isosurface with no mask, the mask branch's input on it at the snapshot's lambda in
    green at its weight w, and the network's end-plate width from the CT alone (orange) beside the
    oracle's (blue). Right, stacked and of one height: lambda and w over the run, and the width over
    the run against the reference."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    vertebra = demo.typical() if vertebra is None else vertebra
    fig = make_subplots(rows=2, cols=2, column_widths=[0.6, 0.4], row_heights=[0.5, 0.5],
                        specs=[[{"type": "scene", "rowspan": 2}, {"type": "xy"}], [None, {"type": "xy"}]],
                        horizontal_spacing=0.08, vertical_spacing=0.17,
                        subplot_titles=("", "The schedule: %s (black) and %s (green)" % (LAM, W),
                                        "The end-plate width of the vertebra on the left (mm)"))
    first = demo.snapshots[0]
    fig.add_trace(surface(demo, vertebra), row=1, col=1)
    fig.add_trace(mask_surface(demo, vertebra, first), row=1, col=1)
    fig.add_trace(reference_chord(demo, vertebra), row=1, col=1)
    fig.add_trace(network_chord(first, vertebra), row=1, col=1)
    add_schedule(fig, demo)
    fig.add_trace(schedule_marks(first), row=1, col=2)
    add_reference_width(fig, demo, vertebra)
    fig.add_trace(width_line(demo, 0, vertebra), row=2, col=2)
    fig.frames = [go.Frame(name=str(k), traces=MOVING, layout=dict(title_text=title(demo, k, vertebra)),
                           data=[mask_frame(demo, vertebra, s), network_chord(s, vertebra), schedule_marks(s),
                                 width_line(demo, k, vertebra)])
                  for k, s in enumerate(demo.snapshots)]
    lay_out(fig, demo, vertebra)
    fig.update_layout(title_text=title(demo, 0, vertebra), sliders=[slider(demo)], updatemenus=[buttons()])
    return fig


def add_schedule(fig, demo: Demo) -> None:
    """lambda and w over the run, counted as the slider counts: at step s the values the s-th update
    used, and at step 0 the first update's, so each snapshot's dots lie on the curves."""
    import plotly.graph_objects as go
    steps = np.arange(demo.steps + 1)
    for values, line in ((demo.lam, dict(color="#000000", width=2)), (demo.w, dict(color=GREEN, width=2, dash="dot"))):
        fig.add_trace(go.Scatter(x=steps, y=np.concatenate([values[:1], values]), mode="lines", line=line,
                                 showlegend=False, hoverinfo="skip"), row=1, col=2)


def add_reference_width(fig, demo: Demo, vertebra: int) -> None:
    import plotly.graph_objects as go
    ref = float(demo.reference_widths[vertebra])
    fig.add_trace(go.Scatter(x=[0, demo.steps], y=[ref, ref], mode="lines", showlegend=False,
                             line=dict(color=BLUE, width=2, dash="dash"), hoverinfo="skip"), row=2, col=2)


def width_range(demo: Demo, vertebra: int) -> List[float]:
    values = [float(s.widths[vertebra]) for s in demo.snapshots] + [float(demo.reference_widths[vertebra])]
    return [min(values) - 3.0, max(values) + 3.0]


def lay_out(fig, demo: Demo, vertebra: int) -> None:
    hidden = dict(visible=False)        # the vertebra alone, as large as the panel holds it
    # Seen from the front and a little above, the view's centre raised so the vertebra sits below the legend.
    fig.update_scenes(aspectmode="data", camera=dict(eye=dict(x=0.26, y=1.15, z=0.54), center=dict(x=0, y=0, z=0.1)),
                      xaxis=hidden, yaxis=hidden, zaxis=hidden)
    fig.update_xaxes(range=[0, demo.steps], row=1, col=2)
    fig.update_yaxes(range=[-0.05, 1.05], row=1, col=2)
    fig.update_xaxes(range=[0, demo.steps], title_text="step", row=2, col=2)
    fig.update_yaxes(range=width_range(demo, vertebra), title_text="mm", row=2, col=2)
    fig.update_layout(width=WIDTH_PX, height=HEIGHT_PX, autosize=False, margin=dict(l=10, r=20, t=85, b=135),
                      plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
                      title=dict(font=dict(size=14), x=0.01, y=0.975, yanchor="top"),
                      legend=dict(x=0.0, y=1.0, xanchor="left", yanchor="top", font=dict(size=12),
                                  bgcolor="rgba(255,255,255,0.8)"))


def slider(demo: Demo) -> dict:
    moves = [dict(method="animate", label=str(s.step),
                  args=[[str(k)], dict(mode="immediate", frame=dict(duration=0, redraw=True),
                                       transition=dict(duration=0))])
             for k, s in enumerate(demo.snapshots)]
    return dict(steps=moves, active=0, x=0.1, len=0.9, xanchor="left", y=0.0, yanchor="top",
                currentvalue=dict(prefix="After step ", font=dict(size=12)), font=dict(size=10),
                pad=dict(t=55, b=10))


def buttons() -> dict:
    play = dict(label="Play", method="animate",
                args=[None, dict(frame=dict(duration=250, redraw=True), transition=dict(duration=0), fromcurrent=True)])
    pause = dict(label="Pause", method="animate",
                 args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")])
    return dict(type="buttons", buttons=[play, pause], direction="left", x=0.0, y=0.0, xanchor="left",
                yanchor="top", pad=dict(t=70, r=10), showactive=False)


def page(fig, plotlyjs: str = "inline", after: str = "") -> str:
    """The figure as an HTML page at its fixed size, set in from the edges of the page or the
    notebook's cell, with plotly.js in it (inline, for reading offline) or from plotly's CDN (cdn,
    a page of a megabyte or two, as Colab shows it), and any HTML after it in the same box."""
    body = fig.to_html(full_html=False, include_plotlyjs=True if plotlyjs == "inline" else "cdn", auto_play=False,
                       default_width="%dpx" % fig.layout.width, default_height="%dpx" % fig.layout.height,
                       config={"responsive": False, "displaylogo": False})
    return ('<!DOCTYPE html>\n<html>\n<head><meta charset="utf-8"><title>The anneal, on a slider</title></head>\n'
            '<body style="margin:0;background:#FFFFFF">\n<div style="width:%dpx;margin:16px auto;padding:12px;'
            'border:1px solid #DDDDDD;border-radius:8px;background:#FFFFFF;font-family:sans-serif">\n%s\n%s</div>\n'
            '</body>\n</html>\n' % (WIDTH_PX, body, after))


@dataclass
class TestSet:
    """Phantoms drawn after training that the network never saw: a name, what differs from the
    training phantoms, and the settings of train.make_examples that differ from the held-out ones'."""
    name: str
    differs: str
    settings: dict


# Each differs from the training phantoms in one way. The noisier and coarser scans are of the
# new patients, the same draws, so the change in error between them is the scan's alone.
TESTS = (
    TestSet("new patients", "new draws of the training phantoms' kind", {}),
    TestSet("unseen levels", "T6 to T10, where training saw T11 to L5", {"starts": ("T6", "T7", "T8")}),
    TestSet("transitional spines", "six-lumbar, T13, four-lumbar and lumbar-rib columns, at their transitions",
            {"phenotypes": ("six_lumbar", "t13", "four_lumbar", "lumbar_rib"), "starts": ("L4", "T12", "L2", "T12")}),
    TestSet("noisier scanner", "the new patients with 200 HU of noise, where training had 20", {"noise_hu": 200.0}),
    TestSet("coarser scan", "the new patients in 3 mm voxels, where training had 1.25 mm", {"spacing_mm": 3.0}),
)
# Okabe and Ito's colours, one for each test set.
TEST_COLOURS = ("#000000", "#D55E00", "#CC79A7", "#0072B2", "#009E73")


def phantom_settings(test: TestSet) -> dict:
    """train.make_examples' settings for a test set: the held-out phantoms', then the set's own."""
    return dict(dict(phenotypes=("typical",), starts=smoke.HELD_STARTS, **smoke.PHANTOM), **test.settings)


@dataclass
class Tested:
    """One test set read from the CT alone by the run's network after its last step, against the
    oracle's reference off the mask: each vertebra's level, its column (one phantom patient) and
    the two widths."""
    test: TestSet
    levels: List[str]
    columns: np.ndarray
    reference: np.ndarray
    read: np.ndarray

    def error(self, widths: Optional[np.ndarray] = None) -> float:
        """The mean absolute error of these widths (the network's unless given) against the reference."""
        return float(np.mean(np.abs((self.read if widths is None else widths) - self.reference)))

    def interval(self, draws: int = 2000, seed: int = 0) -> Tuple[float, float]:
        """A 95% interval for the network's mean error, resampling whole columns, since one patient's
        vertebrae are not independent of each other."""
        rng = np.random.default_rng(seed)
        errors = np.abs(self.read - self.reference)
        by_column = [errors[self.columns == c] for c in np.unique(self.columns)]
        means = [np.mean(np.concatenate([by_column[i] for i in rng.integers(len(by_column), size=len(by_column))]))
                 for _ in range(draws)]
        return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def restored(demo: Demo) -> Model:
    """The run's network after its last step, from the weights it kept."""
    model = Model(demo.cfg, nnx.Rngs(smoke.SEEDS["run"]))
    state = nnx.state(model, nnx.Param)
    nnx.replace_by_pure_dict(state, jax.tree.map(jnp.asarray, demo.params))
    nnx.update(model, state)
    return model


def tested(demo: Demo, tests: Tuple[TestSet, ...] = TESTS, columns: int = TEST_COLUMNS) -> Iterator[Tested]:
    """Each test set in turn, drawn as columns of smoke.COUNT vertebrae and read from the CT alone by
    the run's network, its crops placed from the oracle's frame as the training crops are."""
    model = restored(demo)
    read = nnx.jit(lambda m, hu: m.ct_only(hu)["values"][:, 0])
    for test in tests:
        ex = train.make_examples(demo.cfg, columns, smoke.COUNT, seed=TEST_SEED, **phantom_settings(test))
        yield Tested(test=test, levels=[r.level for r in ex.readings], columns=np.asarray(ex.spine),
                     reference=np.asarray(ex.values[:, 0]), read=np.asarray(read(model, jnp.asarray(ex.hu))))


def test_figure(results: List[Tested], demo: Demo):
    """Left: each test vertebra's width from the CT alone against the reference, one colour a set,
    on the diagonal where the two agree. Right: each set's mean error with its 95% interval over
    columns, beside always guessing the training phantoms' mean width, which reads no CT at all."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    fig = make_subplots(rows=1, cols=2, column_widths=[0.42, 0.58], horizontal_spacing=0.1,
                        subplot_titles=("Each vertebra: the network against the reference",
                                        "Each set: the mean error, with its 95% interval"))
    every = np.concatenate([np.concatenate([r.reference, r.read]) for r in results])
    span = [float(every.min()) - 2.0, float(every.max()) + 2.0]
    fig.add_trace(go.Scatter(x=span, y=span, mode="lines", line=dict(color=GREY, width=1, dash="dash"),
                             showlegend=False, hoverinfo="skip"), row=1, col=1)
    for r, colour in zip(results, TEST_COLOURS):
        fig.add_trace(go.Scatter(x=r.reference, y=r.read, mode="markers", name=r.test.name, legendgroup=r.test.name,
                                 marker=dict(color=colour, size=8, opacity=0.85), text=r.levels,
                                 hovertemplate="%{text}: reference %{x:.1f} mm, network %{y:.1f} mm<extra></extra>"),
                      row=1, col=1)
    for r, colour in zip(results, TEST_COLOURS):
        mean, (low, high) = r.error(), r.interval()
        fig.add_trace(go.Scatter(x=[r.test.name], y=[mean], mode="markers", legendgroup=r.test.name, showlegend=False,
                                 marker=dict(color=colour, size=12),
                                 error_y=dict(type="data", symmetric=False, array=[high - mean], arrayminus=[mean - low],
                                              color=colour, thickness=2, width=8),
                                 hovertemplate="%{x}: %{y:.1f} mm<extra></extra>"), row=1, col=2)
    fig.add_trace(go.Scatter(x=[r.test.name for r in results],
                             y=[r.error(np.full_like(r.reference, demo.train_mean)) for r in results], mode="markers",
                             name="always the training mean width", marker=dict(symbol="diamond-open", size=11, color=GREY,
                                                                                line=dict(width=2, color=GREY)),
                             hovertemplate="%{x}: guessing the mean, %{y:.1f} mm<extra></extra>"), row=1, col=2)
    fig.update_xaxes(range=span, title_text="the reference, from the mask (mm)", row=1, col=1)
    fig.update_yaxes(range=span, title_text="the network, from the CT alone (mm)", row=1, col=1)
    fig.update_yaxes(rangemode="tozero", title_text="mean error (mm)", row=1, col=2)
    fig.update_layout(width=WIDTH_PX, height=TEST_HEIGHT_PX, autosize=False, margin=dict(l=60, r=20, t=70, b=60),
                      plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
                      title=dict(text="<b>The network after %d steps, on phantoms it never saw</b>" % demo.steps,
                                 font=dict(size=14), x=0.01, y=0.98, yanchor="top"),
                      legend=dict(orientation="h", x=0.0, y=-0.16, xanchor="left", yanchor="top", font=dict(size=12)))
    fig.update_xaxes(showgrid=True, gridcolor="#EEEEEE")
    fig.update_yaxes(showgrid=True, gridcolor="#EEEEEE")
    return fig


def test_table(results: List[Tested], demo: Demo) -> str:
    """The test sets' numbers under the figure, one row a set."""
    rows = "".join('<tr><td style="color:%s;font-weight:bold">%s</td><td>%s</td><td>%d</td><td>%.1f mm [%.1f, %.1f]</td>'
                   '<td>%.1f mm</td></tr>' % ((colour, r.test.name, r.test.differs, len(r.reference), r.error())
                                              + r.interval() + (r.error(np.full_like(r.reference, demo.train_mean)),))
                   for r, colour in zip(results, TEST_COLOURS))
    return ('<table style="border-collapse:collapse;font-size:13px;margin:8px 4px" cellpadding="5">'
            '<tr style="text-align:left;border-bottom:1px solid #CCCCCC"><th>test set</th><th>what differs</th>'
            '<th>vertebrae</th><th>the network\'s mean error [95%%]</th><th>guessing the mean</th></tr>%s</table>\n' % rows)


def versions() -> dict:
    """What ran a demo: Python, the packages its numbers depend on, JAX's device and the CPUs it may use."""
    import jax
    found = {"python": platform.python_version(), "device": str(jax.devices()[0]),
             "cpus": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count()}
    for name in ("jax", "jaxlib", "flax", "optax", "numpy", "scipy"):
        found[name] = importlib.metadata.version(name)
    return found


def record(demo: Demo, cfg: Config) -> dict:
    """A run's numbers for its record file: the settings, each snapshot's lambda, w and mean error over
    the held-out vertebrae, each held-out vertebra's reference and its reading after the last step,
    the vertebra the figure shows unless told otherwise, the seconds from making the phantoms to the
    last snapshot, and what ran it."""
    last = demo.snapshots[-1]
    return {"measurement": KEY, "steps": demo.steps, "widths": list(cfg.widths), "crop": list(cfg.shape),
            "spacing_mm": cfg.spacing, "learning_rate": smoke.LR, "seeds": dict(smoke.SEEDS),
            "snapshots": [{"step": s.step, "w": s.w, "lambda": s.lam, "mean_error_mm": demo.error_mm(k)}
                          for k, s in enumerate(demo.snapshots)],
            "held_out": [{"level": level, "reference_mm": float(ref), "read_mm": float(read),
                          "error_mm": float(abs(read - ref))}
                         for level, ref, read in zip(demo.levels, demo.reference_widths, last.widths)],
            "shown": demo.typical(), "seconds": demo.seconds, "ran_on": versions()}


def widths_of(text: str) -> Tuple[int, ...]:
    """--widths 8,16,32: the encoders' channels at each of the three scales."""
    widths = tuple(int(part) for part in text.split(","))
    if len(widths) != 3 or min(widths) < 1:
        raise argparse.ArgumentTypeError("three positive widths, as 8,16,32")
    return widths


def test(demo: Demo, path: str, plotlyjs: str) -> int:
    """The --test page: the run's network on each test set, with a line a set as it goes."""
    results = []
    for r in tested(demo, TESTS, TEST_COLUMNS):
        results.append(r)
        print("%s: %d vertebrae, the network's mean error %.1f mm [%.1f, %.1f], guessing the mean %.1f mm" % (
            (r.test.name, len(r.reference), r.error()) + r.interval() + (r.error(np.full_like(r.reference, demo.train_mean)),)),
            flush=True)
    with open(path, "w") as f:
        f.write(page(test_figure(results, demo), plotlyjs, after=test_table(results, demo)))
    print("%s: the network after %d steps on %d test sets" % (path, demo.steps, len(results)))
    return 0


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m autoanatomist.demo",
                                     description="Train the demo's network and draw its anneal as an HTML page.")
    parser.add_argument("page", help="the HTML page to write")
    parser.add_argument("--steps", type=int, default=smoke.STEPS, help="training steps (%(default)s, the smoke run's)")
    parser.add_argument("--widths", type=widths_of, default=Config(keys=(KEY,)).widths,
                        help="the encoders' widths (16,32,64, the smoke run's)")
    parser.add_argument("--vertebra", type=int, help="the held-out vertebra to show, from 0 (unless named, the one "
                                                     "whose error at the end is the median)")
    parser.add_argument("--plotlyjs", choices=("inline", "cdn"), default="inline",
                        help="plotly.js inline in the page (the default, for reading offline) or from plotly's CDN")
    parser.add_argument("--record", help="also write the run's numbers here as JSON")
    parser.add_argument("--save", help="also keep the run here, a pickle, to draw again with --load")
    parser.add_argument("--load", help="draw the run kept by --save, a pickle this command wrote, instead of training")
    parser.add_argument("--test", action="store_true",
                        help="with --load: read phantoms the network never saw and draw how it does, in place of the anneal")
    args = parser.parse_args(argv[1:])
    if args.load and (args.record or args.save):
        parser.error("--record and --save go with a run that trains, not with --load")
    if args.test and not args.load:
        parser.error("--test reads the network a run kept: give --load")
    held = smoke.HELD_SPINES * smoke.COUNT
    if args.vertebra is not None and not args.load and not 0 <= args.vertebra < held:
        parser.error("--vertebra takes 0 to %d, the held-out vertebrae" % (held - 1))
    if importlib.util.find_spec("plotly") is None:      # said before the minutes of training, not after
        print("the figure needs plotly, which no requirements file pins: pip install plotly", file=sys.stderr)
        return 2
    if args.load:
        with open(args.load, "rb") as f:
            demo = pickle.load(f)
        if args.vertebra is not None and not 0 <= args.vertebra < len(demo.levels):
            parser.error("--vertebra takes 0 to %d, the run's held-out vertebrae" % (len(demo.levels) - 1))
    else:
        cfg = Config(keys=(KEY,), widths=args.widths)
        demo = run(args.steps, EVERY, cfg)
        if args.save:
            with open(args.save, "wb") as f:
                pickle.dump(demo, f, protocol=pickle.HIGHEST_PROTOCOL)
        if args.record:
            with open(args.record, "w") as f:
                json.dump(record(demo, cfg), f, indent=1)
                f.write("\n")
    if args.test:
        return test(demo, args.page, args.plotlyjs)
    vertebra = demo.typical() if args.vertebra is None else args.vertebra
    with open(args.page, "w") as f:
        f.write(page(figure(demo, vertebra), args.plotlyjs))
    print("%s: %d snapshots over %d steps in %.0f s; it shows held-out vertebra %d, %s" % (
        args.page, len(demo.snapshots), demo.steps, demo.seconds, vertebra, demo.levels[vertebra]))
    return 0


if __name__ == "__main__":
    # main from the module autoanatomist.demo, not from __main__, so that a run kept with --save names
    # its classes as autoanatomist.demo's and --load reads it wherever bordercall imports.
    from autoanatomist import demo
    sys.exit(demo.main(sys.argv))
