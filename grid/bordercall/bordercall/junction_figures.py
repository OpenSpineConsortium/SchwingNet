"""The figures of the junction predictor, from a recorded `panjabi` run and the reference table.

    python run.py panjabi-figures --json records/panjabi-2026-10-26/three-measures/panjabi_junction.json \
        --outdir figures/junction

Drawn as a spine textbook draws its figures (Benzel's Biomechanics of Spine Stabilization is the
model the owner named): black ink on white, serif type, thin lines, an axis on two sides only,
ticks outward, no grid and no colour. A series is told apart by its line (solid, dashed) and its
marker (filled, open; circle, square, triangle), never by a hue, so the figure reads the same
printed, projected or photocopied. Panels are lettered A, B, C. Where a drawing says more than a
plot the anatomy is drawn to the tables' own millimetres: the column as an AP projection, each
body a box of its end-plate width and posterior height with the canal hatched over it.

Every figure is written four ways, beside each other, so that nothing in it is typed:

  <name>.pdf          vector, type as type, with no date inside, so two builds give one file
  <name>.png          300 dpi, under a megabyte
  <name>.csv          the numbers drawn, row by row, written from the arrays the plot reads
  <name>.caption.txt  the legend a textbook prints under the figure

and FIGURES.md in the same folder records the run the figures came from (its path and sha256),
the reference table and the code (sha256 each), the library versions and the command, so that a
reader can rebuild the folder and compare it file for file.

  profile    A: the column drawn to Panjabi's means; B to D (or E): each measure down the column,
             mean and one population SD, the two junctions marked: the shape the template reads,
             so a reader sees why the cervicothoracic step is large and the thoracolumbar one small
  posterior  one window of eight bodies straddling each junction, synthesised from the table with
             a fixed seed, the bodies drawn above as seen, and the template's posterior over every
             cut below, the true cut filled: how it decides, and by how much
  width      exact and within-one naming against the width of the window, both junctions
  twins      a lumbosacral twin (four or six lumbar bodies) and whether the call moved, and the
             exact rate by phenotype, both junctions
  blend      the thoracolumbar call as the transitional body blends from its own shape to its
             neighbour's, the three thoracolumbar phenotypes, one set of calls scored against the
             count's junction and against the rib reading's, one level apart

Every number is read from the JSON a run wrote, never typed. The figures are about synthetic
columns from Panjabi's tables; every caption says so.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import platform
import sys
from typing import List, Sequence

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import panjabi as P  # noqa: E402

INK = "#000000"
SERIF = ["Liberation Serif", "Times New Roman", "Nimbus Roman", "DejaVu Serif"]
JUNCTION_NAME = {"ct": "C7/T1, cervicothoracic", "tl": "T12/L1, thoracolumbar"}
# one junction solid with filled markers, the other dashed with open ones
JUNCTION_STYLE = {"ct": dict(linestyle="-", marker="o", markerfacecolor=INK),
                  "tl": dict(linestyle="--", marker="o", markerfacecolor="white")}
MEASURE_NAME = {"endplate": "End-plate width", "h_post": "Posterior body height",
                "canal_w": "Canal width", "canal_ap": "Canal depth", "pedicle": "Pedicle width"}
PHENOTYPE_NAME = {"typical": "Typical", "four_lumbar": "Four lumbar", "six_lumbar": "Six lumbar",
                  "t13": "Thirteenth rib-bearing body", "lumbar_rib": "Rib on L1",
                  "no_rib_t12": "No rib on T12"}
PHENOTYPE_ORDER = ["typical", "four_lumbar", "six_lumbar", "t13", "lumbar_rib", "no_rib_t12"]
# the transitional phenotypes by marker shape; the truth scored against by line and fill
PHENOTYPE_MARKER = {"t13": "o", "lumbar_rib": "s", "no_rib_t12": "^"}
TRUTH_STYLE = {"count": dict(linestyle="-", markerfacecolor=INK),
               "ribs": dict(linestyle="--", markerfacecolor="white")}
DRAW_MEASURES = ["endplate", "h_post", "canal_w"]
DISC_MM = 5.0          # the tables give no disc height; the drawing uses one height throughout
POSTERIOR_SEED = 11    # the one column the posterior figure draws
PNG_DPI = 300

CAPTIONS = {
    "junction_profile":
        "The vertebral column as the tables describe it. A, the column in anteroposterior projection, "
        "drawn to Panjabi's published means: each body a box of its end-plate width and posterior "
        "height, the canal width hatched over it, the disc spaces at one height throughout (%.0f mm) "
        "since the tables give none; the scale is millimetres from the C3 upper end-plate. B onward, "
        "each measure down the column, the mean and one population standard deviation (the printed "
        "standard error times the square root of twelve), the two junctions as dotted lines. The "
        "cervicothoracic step is large in every measure; the thoracolumbar step is small beside the "
        "spread of one level. C2 has no upper end-plate row, so the profile starts at C3. Panjabi MM "
        "et al., Spine 1991;16:861 and 888; Spine 1992;17:299. No patient data." % DISC_MM,
    "junction_posterior":
        "How the template decides. One synthetic typical column drawn from the tables (seed %d), a "
        "window of eight bodies around each junction: A, the cervicothoracic; B, the thoracolumbar. "
        "Above, the window as a reader sees it, each body a box of its measured end-plate width, "
        "named by the count. Below, the template's posterior probability over every cut the window "
        "allows, each naming the column could have scored against the profile with one free offset "
        "per measure and averaged under a flat prior over the cut; the true junction's bar is "
        "filled, the arrow marks the call. The inset gives the log-likelihood gap, per measure, "
        "between the best naming and the runner-up: at C7/T1 the canal width carries the call by "
        "itself; at T12/L1 no measure decides strongly." % POSTERIOR_SEED,
    "junction_width":
        "Naming against the width of the window. A, named exactly; B, named within one level; "
        "%s. Filled circles and a solid line, C7/T1; open circles and a dashed line, T12/L1. Bars "
        "are 95%% Wilson intervals. The model is read off the published tables and fitted on no "
        "CT, so every number is about the tables and the generator, not about a patient.",
    "junction_twins":
        "A lumbosacral anomaly does not move the junction call. A, one column drawn once and named "
        "two ways, with four or six lumbar bodies in place of five, and whether the call on the "
        "twin was the same: %s. B, named exactly by the column's phenotype, %s. Filled circles, "
        "C7/T1; open circles, T12/L1; bars are 95%% Wilson intervals. The lumbosacral count is "
        "not in the junction's window, so by construction it cannot move the call; the "
        "thoracolumbar anomalies are in it, and do.",
    "junction_blend":
        "The thoracolumbar transitional body, two truths one level apart. The nineteenth body is "
        "drawn from its own region's shape (blend 0) toward its neighbour's (blend 1) for the three "
        "thoracolumbar phenotypes, told apart by marker: circle, a thirteenth rib-bearing body drawn "
        "thoracic; square, a rib on L1 drawn lumbar; triangle, no rib on T12. One set of calls is "
        "scored two ways: against the count from C2, which names the nineteenth body L1 whatever "
        "its shape (solid line, filled markers), and against the rib reading, which names the same "
        "column one level apart (dashed line, open markers). %s. Bars are 95%% Wilson intervals. "
        "The shape cannot choose between the two conventions; only the count from C2 settles it, "
        "which is the case a full-spine corpus meets.",
}


def wilson(k: int, n: int, z: float = 1.959964):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def style():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "pdf.fonttype": 42, "ps.fonttype": 42,
        "font.family": "serif", "font.serif": SERIF, "font.size": 9.5, "mathtext.fontset": "dejavuserif",
        "text.color": INK, "axes.edgecolor": INK, "axes.labelcolor": INK, "axes.linewidth": 0.8,
        "axes.titlesize": 9.5, "axes.titleweight": "normal", "axes.labelsize": 9,
        "xtick.color": INK, "ytick.color": INK, "xtick.direction": "out", "ytick.direction": "out",
        "xtick.major.width": 0.8, "ytick.major.width": 0.8, "xtick.major.size": 3.5, "ytick.major.size": 3.5,
        "xtick.labelsize": 8, "ytick.labelsize": 8,
        "axes.spines.top": False, "axes.spines.right": False, "axes.grid": False,
        "legend.frameon": True, "legend.edgecolor": INK, "legend.fancybox": False, "legend.framealpha": 1.0,
        "legend.fontsize": 7.5, "legend.title_fontsize": 7.5,
        "lines.linewidth": 1.1, "lines.markersize": 4.5, "lines.markeredgewidth": 0.9, "lines.color": INK,
        "patch.linewidth": 0.8, "patch.edgecolor": INK, "hatch.linewidth": 0.5, "hatch.color": INK,
        "errorbar.capsize": 2.5, "figure.dpi": 100, "savefig.dpi": PNG_DPI,
        "axes.prop_cycle": matplotlib.cycler(color=[INK]),
    })
    return plt


def letter(ax, text: str, title: str = ""):
    """The panel's letter above its top-left corner, bold, with its heading in plain type beside."""
    ax.annotate(text, xy=(0, 1), xycoords="axes fraction", xytext=(-6, 5), textcoords="offset points",
                fontsize=12, fontweight="bold", ha="left", va="bottom")
    if title:
        ax.annotate(title, xy=(0, 1), xycoords="axes fraction", xytext=(10, 5), textcoords="offset points",
                    fontsize=9, ha="left", va="bottom")


def fmt(v):
    if isinstance(v, (bool, np.bool_)):
        return int(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        return format(float(v), ".6g")
    return v


def write_csv(outdir: str, name: str, rows: List[dict], fields: Sequence[str]) -> str:
    """The numbers a figure draws, in the order it draws them."""
    path = os.path.join(outdir, name + ".csv")
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fields), lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: fmt(r.get(k, "")) for k in fields})
    return path


def save(fig, outdir: str, name: str, caption: str) -> List[str]:
    """PDF without a date, so two builds are one file; PNG at 300 dpi; the caption beside them."""
    import matplotlib.pyplot as plt
    paths = []
    p = os.path.join(outdir, name + ".pdf")
    fig.savefig(p, bbox_inches="tight", facecolor="white", metadata={"CreationDate": None, "ModDate": None})
    paths.append(p)
    p = os.path.join(outdir, name + ".png")
    fig.savefig(p, bbox_inches="tight", facecolor="white")
    paths.append(p)
    plt.close(fig)
    p = os.path.join(outdir, name + ".caption.txt")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(caption.strip() + "\n")
    paths.append(p)
    return paths


# ---- 1 the profile -------------------------------------------------------------------------

def draw_column(ax, ref, levels):
    """The column in AP projection, to the tables' means: a box per body, the canal hatched over it."""
    from matplotlib.patches import Patch, Rectangle
    y = 0.0
    discs = {}
    for lv in levels:
        w, h, c = ref["endplate"][lv][0], ref["h_post"][lv][0], ref["canal_w"][lv][0]
        ax.add_patch(Rectangle((-w / 2, -(y + h)), w, h, facecolor="white", edgecolor=INK, linewidth=0.8))
        ax.add_patch(Rectangle((-c / 2, -(y + h)), c, h, facecolor="none", edgecolor=INK, hatch="/////", linewidth=0.3))
        ax.text(-w / 2 - 3.5, -(y + h / 2), lv, ha="right", va="center", fontsize=5.8)
        y += h
        discs[lv] = -(y + DISC_MM / 2)
        y += DISC_MM
    for j, above in (("ct", "C7"), ("tl", "T12")):
        ax.annotate("C7/T1" if j == "ct" else "T12/L1", xy=(28, discs[above]), xytext=(40, discs[above]),
                    fontsize=7, va="center", ha="left",
                    arrowprops=dict(arrowstyle="-|>", linewidth=0.7, color=INK, shrinkA=0, shrinkB=0))
    ax.set_xlim(-52, 62)
    ax.set_ylim(-y, 8)
    ax.set_aspect("equal")
    ticks = np.arange(0, y, 100)
    ax.set_yticks(-ticks)
    ax.set_yticklabels(["%d" % t for t in ticks])
    ax.set_ylabel("Millimetres from the C3 upper end-plate")
    ax.spines["bottom"].set_visible(False)
    ax.set_xticks([])
    ax.legend([Patch(facecolor="white", edgecolor=INK), Patch(facecolor="none", edgecolor=INK, hatch="/////")],
              ["body", "canal"], loc="upper right", bbox_to_anchor=(1.04, 1.0), fontsize=6.5,
              handlelength=1.2, borderpad=0.4, labelspacing=0.3)


def fig_profile(ref, measures, outdir):
    plt = style()
    levels = P.LEVELS
    draw_ref = P.load_reference(measures=DRAW_MEASURES)
    rows = [{"measure": m, "level": lv, "mean_mm": ref[m][lv][0], "sd_mm": ref[m][lv][1]}
            for m in measures for lv in levels]
    rows += [{"measure": m, "level": lv, "mean_mm": draw_ref[m][lv][0], "sd_mm": draw_ref[m][lv][1]}
             for m in DRAW_MEASURES if m not in measures for lv in levels]
    write_csv(outdir, "junction_profile", rows, ["measure", "level", "mean_mm", "sd_mm"])
    n = len(measures)
    fig = plt.figure(figsize=(2.3 + 1.9 * n, 4.6))
    gs = fig.add_gridspec(1, 1 + n, width_ratios=[1.6] + [1.0] * n, wspace=0.5)
    ax0 = fig.add_subplot(gs[0, 0])
    draw_column(ax0, draw_ref, levels)
    letter(ax0, "A")
    y = np.arange(len(levels))
    cuts = {"ct": len(P.CERVICAL), "tl": len(P.CERVICAL) + len(P.THORACIC)}
    for i, m in enumerate(measures):
        ax = fig.add_subplot(gs[0, 1 + i])
        mu = np.array([ref[m][lv][0] for lv in levels])
        sd = np.array([ref[m][lv][1] for lv in levels])
        ax.errorbar(mu, y, xerr=sd, marker="o", markersize=3, markerfacecolor=INK, color=INK,
                    linewidth=0.9, elinewidth=0.6, capsize=1.8)
        for j, cut in cuts.items():
            ax.axhline(cut - 0.5, color=INK, linewidth=0.6, linestyle=":")
            if i == n - 1:
                ax.annotate("C7/T1" if j == "ct" else "T12/L1", xy=(1.0, cut - 0.5), xycoords=("axes fraction", "data"),
                            xytext=(3, 0), textcoords="offset points", fontsize=7, va="center", ha="left")
        ax.set_ylim(len(levels) - 0.5, -0.5)
        ax.set_yticks(y)
        ax.set_yticklabels(levels if i == 0 else [], fontsize=6.5)
        ax.set_xlim(left=0)
        ax.set_xlabel(MEASURE_NAME[m] + ", mm")
        letter(ax, "BCDEF"[i])
    return save(fig, outdir, "junction_profile", CAPTIONS["junction_profile"])


# ---- 2 how it decides ----------------------------------------------------------------------

def fig_posterior(ref, measures, outdir, seed=POSTERIOR_SEED, noise_mm=1.0):
    import junction as J
    from matplotlib.patches import Rectangle
    plt = style()
    rng = np.random.default_rng(seed)
    strip_measure = "endplate" if "endplate" in measures else measures[0]
    fig = plt.figure(figsize=(7.4, 4.3))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 3.0], hspace=0.1, wspace=0.28)
    rows, bodies = [], []
    for i, j in enumerate(("ct", "tl")):
        col = P.synthesize(ref, "typical", rng, measures=list(measures), noise_mm=noise_mm)
        cut = col.cut(j)
        w = col.window(cut - 4, cut + 4)
        t = J.Template(j, ref, measures=list(measures), noise_mm=noise_mm)
        pl = t.place(w.values)
        finite = np.isfinite(pl.loglik)
        post = np.zeros(len(pl.loglik))
        post[finite] = np.exp(pl.loglik[finite] - pl.loglik[finite].max())
        post /= post.sum()
        xs = np.arange(len(post))
        truth = w.cut(j)
        labels = ["above %s" % w.levels[0]] + ["%s/%s" % (w.levels[k - 1], w.levels[k]) for k in range(1, len(w))] + ["below %s" % w.levels[-1]]
        gaps = t.explain(w.values)["gap_by_measure"]
        # the window as seen: each body a box of its end-plate width, between the cuts it lies between
        axs = fig.add_subplot(gs[0, i])
        heights = w.values[strip_measure]
        for k, lv in enumerate(w.levels):
            axs.add_patch(Rectangle((k + 0.15, 0), 0.7, heights[k], facecolor="white", edgecolor=INK, linewidth=0.8))
            axs.text(k + 0.5, heights[k] + 0.08 * heights.max(), lv, ha="center", va="bottom", fontsize=6.5)
        axs.set_ylim(0, heights.max() * 1.5)
        axs.set_yticks([0, round(float(heights.max()), -1)])
        axs.set_ylabel("%s\nmm" % MEASURE_NAME[strip_measure].split()[0].lower(), fontsize=7)
        axs.spines["bottom"].set_visible(False)
        axs.tick_params(labelbottom=False, bottom=False)
        letter(axs, "AB"[i], JUNCTION_NAME[j])
        # the posterior over the cut
        ax = fig.add_subplot(gs[1, i], sharex=axs)
        ax.bar(xs, post, width=0.55, facecolor=["black" if k == truth else "white" for k in xs], edgecolor=INK, linewidth=0.8)
        ax.annotate("called", xy=(pl.cut, post[pl.cut]), xytext=(pl.cut - 0.45, min(1.08, post[pl.cut] + 0.2)),
                    ha="right", va="bottom", fontsize=7.5,
                    arrowprops=dict(arrowstyle="-|>", linewidth=0.7, color=INK, shrinkA=0, shrinkB=1))
        ax.set_xlim(-0.6, len(w) + 0.6)
        ax.set_xticks(xs)
        ax.set_xticklabels(labels, rotation=90, fontsize=7)
        ax.set_ylim(0, 1.25)
        ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
        ax.set_ylabel("Posterior probability of the cut")
        ax.set_xlabel("Cut: the junction placed between these bodies", fontsize=8)
        txt = "Gap to the runner-up, log-likelihood\n" + "\n".join("%s %+.1f" % (MEASURE_NAME.get(m, m), g) for m, g in gaps.items())
        ax.text(0.97, 0.97, txt, transform=ax.transAxes, fontsize=6.8, ha="right", va="top",
                bbox=dict(boxstyle="square,pad=0.4", facecolor="white", edgecolor=INK, linewidth=0.6))
        rows += [{"junction": j, "cut": int(k), "boundary": labels[k], "posterior": post[k],
                  "loglik": pl.loglik[k] if finite[k] else "", "truth": int(k == truth), "called": int(k == pl.cut)} for k in xs]
        bodies += [dict({"junction": j, "position": k, "level": lv}, **{m: w.values[m][k] for m in measures}) for k, lv in enumerate(w.levels)]
    write_csv(outdir, "junction_posterior", rows, ["junction", "cut", "boundary", "posterior", "loglik", "truth", "called"])
    write_csv(outdir, "junction_posterior_window", bodies, ["junction", "position", "level"] + list(measures))
    return save(fig, outdir, "junction_posterior", CAPTIONS["junction_posterior"])


# ---- 3 the width of the window -------------------------------------------------------------

def width_rows(d):
    rows = []
    for j in ("ct", "tl"):
        table = d["by_width"]["%s/profile" % j]
        for w in sorted(int(x) for x in table):
            r = table[str(w)]
            for key in ("exact", "within_one"):
                lo, hi = wilson(r[key], r["called"])
                rows.append({"junction": j, "width": w, "metric": key, "k": r[key], "called": r["called"],
                             "rate": r[key] / r["called"] if r["called"] else float("nan"), "wilson_lo": lo, "wilson_hi": hi})
    return rows


def plot_rates(ax, rows, x_key, series, horizontal=False, annotate_last=False):
    """Rates with their Wilson bars, one series per (filter, style, label)."""
    for keep, style_, label, *rest in series:
        offset = rest[0] if rest else (5, 0)
        r = [row for row in rows if keep(row)]
        if not r:
            continue
        x = np.array([row[x_key] for row in r], float)
        rate = np.array([100 * row["rate"] for row in r])
        # the interval holds the rate; floating point can put its end a hair inside, which errorbar refuses
        err = np.maximum(np.array([[100 * (row["rate"] - row["wilson_lo"]) for row in r],
                                   [100 * (row["wilson_hi"] - row["rate"]) for row in r]]), 0.0)
        if horizontal:
            ax.errorbar(rate, x, xerr=err, color=INK, elinewidth=0.7, label=label, **style_)
        else:
            ax.errorbar(x, rate, yerr=err, color=INK, elinewidth=0.7, label=label, **style_)
            if annotate_last:
                ax.annotate("%.0f%%" % rate[-1], (x[-1], rate[-1]), xytext=offset, textcoords="offset points",
                            fontsize=7.5, va="center")


def fig_width(d, outdir):
    plt = style()
    rows = width_rows(d)
    write_csv(outdir, "junction_width", rows, ["junction", "width", "metric", "k", "called", "rate", "wilson_lo", "wilson_hi"])
    widths = sorted({r["width"] for r in rows})
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.3), sharey=True)
    for ax, key, title, L in zip(axes, ("exact", "within_one"), ("Named exactly", "Named within one level"), "AB"):
        plot_rates(ax, rows, "width",
                   [((lambda r, j=j, k=key: r["junction"] == j and r["metric"] == k), JUNCTION_STYLE[j], JUNCTION_NAME[j],
                     (5, 4) if j == "ct" else (5, -5)) for j in ("ct", "tl")],
                   annotate_last=True)
        ax.set_xlabel("Bodies in the window")
        ax.set_xticks(widths)
        ax.set_xlim(widths[0] - 0.8, widths[-1] + 2.2)
        ax.set_ylim(0, 103)
        letter(ax, L, title)
    axes[0].set_ylabel("Windows, per cent")
    axes[1].legend(loc="lower right")
    n = next(iter(d["by_width"]["ct/profile"].values()))["n"]
    caption = CAPTIONS["junction_width"] % ("profile template on synthetic typical columns, %d windows per width, measures %s"
                                            % (n, ", ".join(MEASURE_NAME[m].lower() for m in d["measures"])))
    return save(fig, outdir, "junction_width", caption)


# ---- 4 the twins and the phenotypes --------------------------------------------------------

def twin_rows(d):
    rows = []
    tw = d["twins"]["profile"]
    for k in ("four_lumbar", "six_lumbar"):
        for j in ("ct", "tl"):
            t = tw[k][j]
            lo, hi = wilson(t["same_call"], t["n"])
            rows.append({"panel": "twin", "junction": j, "class": k, "k": t["same_call"], "n": t["n"],
                         "rate": t["same_call"] / t["n"], "wilson_lo": lo, "wilson_hi": hi})
    for ph in PHENOTYPE_ORDER:
        for j in ("ct", "tl"):
            r = d["by_phenotype"]["%s/profile" % j][ph]
            lo, hi = wilson(r["exact"], r["called"])
            rows.append({"panel": "phenotype", "junction": j, "class": ph, "k": r["exact"], "n": r["called"],
                         "rate": r["exact"] / r["called"], "wilson_lo": lo, "wilson_hi": hi})
    return rows


def fig_twins(d, outdir):
    plt = style()
    rows = twin_rows(d)
    write_csv(outdir, "junction_twins", rows, ["panel", "junction", "class", "k", "n", "rate", "wilson_lo", "wilson_hi"])
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.4), gridspec_kw={"width_ratios": [1, 1.35], "wspace": 0.95})
    for ax, panel, classes, title, L in ((axes[0], "twin", ["four_lumbar", "six_lumbar"], "Same call on the lumbosacral twin", "A"),
                                         (axes[1], "phenotype", PHENOTYPE_ORDER, "Named exactly, by phenotype", "B")):
        for row in rows:
            if row["panel"] == panel:
                row["y"] = classes.index(row["class"]) + (0.16 if row["junction"] == "tl" else -0.16)
        plot_rates(ax, [r for r in rows if r["panel"] == panel], "y",
                   [((lambda r, j=j: r["junction"] == j), dict(JUNCTION_STYLE[j], linestyle="none"), JUNCTION_NAME[j]) for j in ("ct", "tl")],
                   horizontal=True)
        if panel == "twin":
            for row in rows:
                if row["panel"] == panel:
                    ax.annotate("%.1f%% of %d" % (100 * row["rate"], row["n"]), (100 * row["rate"], row["y"]),
                                xytext=(-4, 0), textcoords="offset points", ha="right", va="center", fontsize=6.8)
        ax.set_yticks(range(len(classes)))
        ax.set_yticklabels(["Twin with %s bodies" % PHENOTYPE_NAME[c].lower() if panel == "twin" else PHENOTYPE_NAME[c] for c in classes])
        ax.set_ylim(len(classes) - 0.5, -0.5)
        ax.set_xlim(0, 104)
        ax.set_xlabel("Same call on the twin, per cent" if panel == "twin" else "Named exactly, per cent")
        letter(ax, L, title)
    axes[0].legend(loc="lower left")
    tw = d["twins"]["profile"]
    twin_text = "; ".join("%s, %s: %d of %d" % (PHENOTYPE_NAME[k].lower(), j.upper(), tw[k][j]["same_call"], tw[k][j]["n"])
                          for k in ("four_lumbar", "six_lumbar") for j in ("ct", "tl"))
    n = d["by_phenotype"]["ct/profile"]["typical"]["called"]
    caption = CAPTIONS["junction_twins"] % (twin_text, "%d synthetic windows per class, measures %s"
                                            % (n, ", ".join(MEASURE_NAME[m].lower() for m in d["measures"])))
    return save(fig, outdir, "junction_twins", caption)


# ---- 5 the transitional body ---------------------------------------------------------------

def blend_rows(d):
    rows = []
    for r in sorted(d["blend_sweep"]["profile"], key=lambda r: (PHENOTYPE_ORDER.index(r["phenotype"]), r["blend"])):
        for truth, key in (("count", "exact"), ("ribs", "exact_ribs")):
            lo, hi = wilson(r[key], r["called"])
            rows.append({"phenotype": r["phenotype"], "blend": r["blend"], "truth": truth, "k": r[key], "called": r["called"],
                         "rate": r[key] / r["called"] if r["called"] else float("nan"), "wilson_lo": lo, "wilson_hi": hi})
    return rows


def fig_blend(d, outdir):
    from matplotlib.lines import Line2D
    plt = style()
    rows = blend_rows(d)
    write_csv(outdir, "junction_blend", rows, ["phenotype", "blend", "truth", "k", "called", "rate", "wilson_lo", "wilson_hi"])
    phenotypes = [p for p in PHENOTYPE_ORDER if any(r["phenotype"] == p for r in rows)]
    fig, ax = plt.subplots(figsize=(7.4, 3.8))
    series = []
    for ph in phenotypes:
        for truth in ("count", "ribs"):
            series.append(((lambda r, p=ph, t=truth: r["phenotype"] == p and r["truth"] == t),
                           dict(TRUTH_STYLE[truth], marker=PHENOTYPE_MARKER[ph]), "_nolegend_"))
    plot_rates(ax, rows, "blend", series)
    ax.set_xlabel("Blend of the transitional body, from its own region's shape (0) to its neighbour's (1)")
    ax.set_ylabel("T12/L1 named exactly, per cent")
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(0, 103)
    by_shape = ax.legend([Line2D([], [], color=INK, linestyle="none", marker=PHENOTYPE_MARKER[p], markerfacecolor=INK) for p in phenotypes],
                         [PHENOTYPE_NAME[p] for p in phenotypes], title="Column", loc="upper right")
    ax.add_artist(by_shape)
    ax.legend([Line2D([], [], color=INK, marker="o", **TRUTH_STYLE["count"]), Line2D([], [], color=INK, marker="o", **TRUTH_STYLE["ribs"])],
              ["Scored against the count from C2", "Scored against the rib reading"], title="Truth", loc="upper left")
    n = d["blend_sweep"]["profile"][0]["n"]
    caption = CAPTIONS["junction_blend"] % ("Profile template, %d synthetic windows per point, measures %s"
                                            % (n, ", ".join(MEASURE_NAME[m].lower() for m in d["measures"])))
    return save(fig, outdir, "junction_blend", caption)


# ---- the record ----------------------------------------------------------------------------

def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def write_record(outdir: str, json_path: str, d: dict, written: List[str]) -> str:
    """FIGURES.md: what the figures were built from, so a reader rebuilds and compares them."""
    import matplotlib
    lines = ["# The junction figures", "",
             "Built with `python run.py panjabi-figures --json %s --outdir %s`." % (json_path, outdir), "",
             "- Run: `%s`, sha256 %s; measures %s; %s columns fitted on, %s windows scored per class; synth %s; seed %s."
             % (json_path, sha256(json_path), ", ".join(d["measures"]), d.get("n_columns"), d.get("n_eval"),
                json.dumps(d.get("synth"), sort_keys=True), d.get("seed", "0 (the default; not recorded in this run)")),
             "- Reference table: `bordercall/reference/panjabi_full_spine.csv`, sha256 %s." % sha256(P.DEFAULT_REFERENCE)]
    for name in ("junction_figures.py", "junction.py", "panjabi.py"):
        lines.append("- Code: `bordercall/%s`, sha256 %s." % (name, sha256(os.path.join(HERE, name))))
    lines += ["- Posterior panel: one typical column per junction, drawn in the figure code with seed %d; not part of the run." % POSTERIOR_SEED,
              "- Python %s, numpy %s, matplotlib %s; serif type %s, embedded in the PDF." % (platform.python_version(), np.__version__, matplotlib.__version__, SERIF[0]),
              "- The PDFs carry no creation date, so a rebuild with the same versions gives the same files; the CSVs beside them hold every number drawn.", ""]
    lines += ["| Figure | Files | Caption |", "|---|---|---|"]
    names = []
    for p in written:
        base = os.path.basename(p).split(".")[0]
        if base not in names:
            names.append(base)
    for name in names:
        files = sorted(f for f in os.listdir(outdir) if f.startswith(name + ".") or f.startswith(name + "_"))
        with open(os.path.join(outdir, name + ".caption.txt"), encoding="utf-8") as fh:
            caption = fh.read().strip().replace("|", "/")
        lines.append("| %s | %s | %s |" % (name, ", ".join("`%s`" % f for f in files), caption))
    path = os.path.join(outdir, "FIGURES.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


def run(json_path: str, outdir: str) -> List[str]:
    """The five figures, their data and their record, from one recorded panjabi run."""
    os.makedirs(outdir, exist_ok=True)
    with open(json_path, encoding="utf-8") as fh:
        d = json.load(fh)
    measures = list(d["measures"])
    ref = P.load_reference(measures=measures)
    written = []
    written += fig_profile(ref, measures, outdir)
    written += fig_posterior(ref, measures, outdir, noise_mm=d["synth"].get("noise_mm", 1.0))
    written += fig_width(d, outdir)
    written += fig_twins(d, outdir)
    written += fig_blend(d, outdir)
    written.append(write_record(outdir, json_path, d, written))
    for p in written:
        print("%7.0f KB  %s" % (os.path.getsize(p) / 1024, p))
    return written
