"""An oracle's measurements drawn on a reslice of the mask or of the CT, in the vertebra's frame.

Each measurement is drawn on the plane of the vertebra's own frame that holds its line (specs.py,
`plane`): a width across on the coronal plane (x, z), a depth or a height on the sagittal plane
(y, z), the canal's chords on the axial plane (x, y). One cut cannot hold every line of a plane:
the stand-in's end-plate widths lie through the body's middle and its transverse span through the
processes, some 25 mm behind. So each panel cuts the volume along the plane's normal where most
of its lines lie, at the mean position of the largest group of lines within OFF_PLANE_MM of one
another, and a line farther than that from the cut is drawn dashed with its distance from the cut
in its label, so the reader sees which lines lie on the cut and which are projected onto it. The
voxels that set each chord (the slab whose extent is an end-plate's width, the cells whose median
is the posterior height) are dotted under its line, so the figure shows how the measurement was
made and not only where its ends are.

The image is resampled from the volume by its affine: nearest for a mask, linear for a CT, on a
grid of `step_mm` in the plane, so nothing is reoriented or written back. The target vertebra is
light grey and its neighbours dark grey on a mask; a CT is shown in a bone window. Each panel is
shown as radiology shows it, the patient's right and front on the viewer's left. The lines take
the first four categorical slots of the plotting guidance's reference palette in each panel's
fixed order, stepped for a dark ground and validated there (CVD separation 8.4, normal vision
19.8 on the worst adjacent pair), each with a dark outline and named on the image and in the
legend, so no line is told by its colour alone.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy import ndimage

from . import specs
from .oracle import Reading

PLANE_AXES = {"coronal": (0, 2, 1), "sagittal": (1, 2, 0), "axial": (0, 1, 2)}    # (u, v, normal) local axes
AXIS_WORDS = ("right", "anterior", "superior")
LINE_COLOURS = ("#3987e5", "#d95926", "#199e70", "#c98500")
INK, INK_SOFT, SURFACE, IMAGE_GROUND = "#0b0b0b", "#52514e", "#fcfcfb", "#1a1a19"
BONE_WINDOW = (-500.0, 1300.0)        # a bone window, level 400 HU and width 1800 HU


def plane_keys(reading: Reading, keys: Optional[Sequence[str]] = None) -> Dict[str, List[str]]:
    """The measurements each plane draws, in the specs' order, those whose points are known."""
    keys = list(reading.measurements) if keys is None else list(keys)
    out: Dict[str, List[str]] = {p: [] for p in PLANE_AXES}
    for k in keys:
        m = reading.measurements.get(k)
        if m is not None and m.taken and m.drawn:
            out[specs.SPECS[k].plane].append(k)
    return out


OFF_PLANE_MM = 2.0            # a line farther than this from its panel's cut is drawn dashed, its offset said
OFF_WORDS = (("right of", "left of"), ("in front of", "behind"), ("above", "below"))   # per normal axis, (+, -)


def line_depth(reading: Reading, key: str, plane: str) -> float:
    """Where a measurement's line lies along the plane's normal, in the frame's local
    coordinates: the mean of its points there."""
    n = PLANE_AXES[plane][2]
    return float(np.mean(reading.frame.local(reading.measurements[key].array())[:, n]))


def plane_offset(reading: Reading, plane: str, keys: Sequence[str]) -> float:
    """Where the plane cuts along its normal, in the frame's local coordinates: the mean position
    of the largest group of its lines that lie within OFF_PLANE_MM of one another, the first key's
    group on a tie; or the reading's centre where it draws none."""
    n = PLANE_AXES[plane][2]
    depths = [line_depth(reading, k, plane) for k in keys]
    if not depths:
        return float(reading.frame.local(reading.centre[None])[0, n])
    groups = [[e for e in depths if abs(e - d) <= OFF_PLANE_MM] for d in depths]
    return float(np.mean(max(groups, key=len)))


def reslice(volume: np.ndarray, affine: np.ndarray, reading: Reading, plane: str, through: float,
            half_mm: float = 60.0, step_mm: float = 0.5, order: int = 0, fill: float = 0.0
            ) -> Tuple[np.ndarray, Tuple[float, float, float, float]]:
    """The volume on one plane of the reading's frame, (rows v, columns u) with v increasing up,
    and the plane's extent (u0, u1, v0, v1) in local millimetres about the frame's origin: the
    outer edges of the first and last samples, which is how imshow reads an extent, so a sample is
    shown where it was taken."""
    a, b, n = PLANE_AXES[plane]
    centre = reading.frame.local(reading.centre[None])[0]
    us = centre[a] + np.arange(-half_mm, half_mm + 1e-9, step_mm)
    vs = centre[b] + np.arange(-half_mm, half_mm + 1e-9, step_mm)
    U, Vv = np.meshgrid(us, vs)
    local = np.zeros(U.shape + (3,))
    local[..., a], local[..., b], local[..., n] = U, Vv, through
    world = reading.frame.world(local.reshape(-1, 3))
    inv = np.linalg.inv(np.asarray(affine, float))
    ijk = world @ inv[:3, :3].T + inv[:3, 3]
    img = ndimage.map_coordinates(np.asarray(volume, float), ijk.T, order=order, mode="constant", cval=fill)
    h = 0.5 * step_mm
    return img.reshape(U.shape), (float(us[0] - h), float(us[-1] + h), float(vs[0] - h), float(vs[-1] + h))


def mask_shades(img: np.ndarray, label: int) -> np.ndarray:
    """A label reslice as shades: the target vertebra light, any other label dark grey, nothing
    darkest."""
    out = np.where(img > 0, 0.35, 0.0)
    return np.where(np.round(img) == label, 0.8, out)


def ct_shades(img: np.ndarray, window: Tuple[float, float] = BONE_WINDOW) -> np.ndarray:
    lo, hi = window
    return np.clip((img - lo) / (hi - lo), 0.0, 1.0)


SHORT = {"tp_span": "TP span", "spinous_length": "spinous"}      # the record-only chords, never Panjabi's names
CHAR_MM, LINE_MM = 2.1, 6.0                                         # a label's character width and height on a panel


def label_of(key: str, value: float) -> str:
    s = specs.SPECS[key]
    return "%s %.1f %s" % (s.panjabi or SHORT.get(key, key), value, s.units)


def room(at: np.ndarray, d: np.ndarray, ext: Tuple[float, float, float, float]) -> float:
    """How far from `at` along the unit direction d the panel's extent reaches, in millimetres."""
    out = np.inf
    for x, dx, lo, hi in ((at[0], d[0], ext[0], ext[1]), (at[1], d[1], ext[2], ext[3])):
        if dx > 1e-9:
            out = min(out, (hi - x) / dx)
        elif dx < -1e-9:
            out = min(out, (lo - x) / dx)
    return float(out)


def label_place(p: np.ndarray, a: int, b: int, ext: Tuple[float, float, float, float], text: str
                ) -> Tuple[Tuple[float, float], Tuple[float, float], str, str]:
    """Where a line's label goes: beyond whichever end leaves the label more room inside the
    panel, along the line, so labels of lines at different places do not fall on one another; or,
    where neither end leaves room for it, beside the line's middle. Returns the anchor, the offset
    in points and the alignments; the panel's horizontal axis is shown reversed, so a step to
    larger u is a step to the left."""
    ends = p[:, [a, b]]
    best = None
    for i in (0, 1):
        d = ends[i] - ends[1 - i]
        d = d / max(float(np.hypot(*d)), 1e-9)
        need = CHAR_MM * len(text) + 4.0 if abs(d[0]) > 0.5 else LINE_MM + 2.0
        r = room(ends[i], d, ext)
        if r >= need and (best is None or r > best[0]):
            best = (r, i, d)
    if best is None:
        mid = ends.mean(0)
        d = ends[1] - ends[0]
        horizontal = abs(d[0]) >= abs(d[1])
        return (float(mid[0]), float(mid[1])), ((0.0, 8.0) if horizontal else (-8.0, 0.0)), \
            ("center" if horizontal else "left"), ("bottom" if horizontal else "center")
    _, i, d = best
    dx, dy = -d[0], d[1]
    ha = "left" if dx > 0.3 else ("right" if dx < -0.3 else "center")
    va = "bottom" if dy > 0.3 else ("top" if dy < -0.3 else "center")
    return (float(ends[i, 0]), float(ends[i, 1])), (9.0 * dx, 9.0 * dy), ha, va


AXIS_NAMES = ("x", "y", "z")


def draw(reading: Reading, volume: np.ndarray, affine: np.ndarray, out_png: str, kind: str = "mask",
         keys: Optional[Sequence[str]] = None, half_mm: float = 60.0, step_mm: float = 0.5,
         title: Optional[str] = None) -> Dict[str, float]:
    """The reading's lines on three panels, coronal, sagittal and axial, cut from the mask
    (kind 'mask') or the CT (kind 'ct'); returns where each panel cut along its normal."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import patheffects as pe

    per_plane = plane_keys(reading, keys)
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 5.6), facecolor=SURFACE)
    cuts: Dict[str, float] = {}
    outline = [pe.Stroke(linewidth=3.6, foreground=IMAGE_GROUND), pe.Normal()]
    text_outline = [pe.Stroke(linewidth=2.6, foreground=IMAGE_GROUND), pe.Normal()]
    for ax, plane in zip(axes, PLANE_AXES):
        a, b, n = PLANE_AXES[plane]
        ks = per_plane[plane]
        through = plane_offset(reading, plane, ks)
        cuts[plane] = through
        if kind == "ct":
            img, ext = reslice(volume, affine, reading, plane, through, half_mm, step_mm, order=1, fill=-1000.0)
            shades = ct_shades(img)
        else:
            img, ext = reslice(volume, affine, reading, plane, through, half_mm, step_mm, order=0)
            shades = mask_shades(img, reading.label)
        ax.imshow(shades, cmap="gray", vmin=0.0, vmax=1.0, origin="lower", extent=ext, interpolation="nearest")
        ax.set_facecolor(IMAGE_GROUND)
        for i, k in enumerate(ks):
            m = reading.measurements[k]
            colour = LINE_COLOURS[i % len(LINE_COLOURS)]
            if m.witness is not None and len(m.witness):
                w = reading.frame.local(m.witness)
                ax.scatter(w[:, a], w[:, b], s=2.0, color=colour, alpha=0.35, linewidths=0, zorder=2)
            p = reading.frame.local(m.array())
            text = label_of(k, m.value)
            off_cut = line_depth(reading, k, plane) - through
            away = abs(off_cut) > OFF_PLANE_MM
            if away:
                text += ", %.0f mm %s the cut" % (abs(off_cut), OFF_WORDS[n][0 if off_cut > 0 else 1])
            ax.plot(p[:, a], p[:, b], color=colour, linewidth=2.0, solid_capstyle="round", zorder=3,
                    linestyle=(0, (4, 3)) if away else "-", path_effects=outline, label="%s (%s)" % (k, text))
            ax.scatter(p[:, a], p[:, b], s=64, color=colour, edgecolors=IMAGE_GROUND, linewidths=1.2, zorder=4)
            at, off, ha, va = label_place(p, a, b, ext, text)
            ax.annotate(text, at, xytext=off, textcoords="offset points", ha=ha, va=va,
                        color="#f0efec", fontsize=8.5, zorder=5, path_effects=text_outline)
        ax.invert_xaxis()
        ax.set_title("%s, cut at %s = %.1f mm" % (plane, AXIS_NAMES[n], through), color=INK, fontsize=10)
        ax.set_xlabel("%s (mm), %s to the left" % (AXIS_NAMES[a], AXIS_WORDS[a]), color=INK_SOFT, fontsize=9)
        ax.set_ylabel("%s (mm), %s up" % (AXIS_NAMES[b], AXIS_WORDS[b]), color=INK_SOFT, fontsize=9)
        ax.tick_params(colors=INK_SOFT, labelsize=8)
        for side in ax.spines.values():
            side.set_color("#c3c2b7")
        if ks:
            leg = ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), fontsize=8, frameon=False, ncol=1)
            for t in leg.get_texts():
                t.set_color(INK)
    fig.suptitle(title or "%s: the oracle's measurements on the %s" % (reading.level, "CT" if kind == "ct" else "mask"),
                 color=INK, fontsize=12)
    fig.savefig(out_png, dpi=110, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    return cuts
