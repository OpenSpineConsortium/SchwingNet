"""Conference figures: morphometry by level, and the border broken out by phenotype.

    python run.py plot --levels levels.csv --phenotype phenotype.csv --measure endplate

Writes a PDF and a PNG side by side. The PDF is vector and is the one to put in a slide or a
poster; the PNG is for a quick look and for anything that cannot take a PDF.

THE AXIS ORDER IS THE TEXTBOOK ONE and is not negotiable here: vertebral body class on the y
axis, cranial at the top, the measurement on the x axis. That is how the morphometry plates a
spine audience has read for thirty years are drawn, and matching them is what lets a surgeon
read the figure without being taught the plot first.

TWO FIGURES, BECAUSE THEY ANSWER DIFFERENT QUESTIONS

  levels    every case, one violin per level, with a published reference interval over it.
            What the corpus looks like.
  classes   one panel per phenotype, each over the typical column in grey, anomalous cases
            as points. Where the border method succeeds and where it fails.

WHY ANOMALOUS CASES ARE POINTS AND NOT VIOLINS. A violin over fourteen cases draws a smooth
density through almost nothing and invites the eye to read a distribution that is not there.
Points show the sample size honestly. Above roughly forty cases a violin becomes fair and
`--violin-min` controls that.

THE REFERENCE INTERVAL IS A POPULATION INTERVAL, mean +/- 1.96 SD, and the SD is recovered
from the reported standard error as sem*sqrt(n). Drawing the standard error instead gives an
interval sqrt(n) times too narrow and makes every cohort look aberrant for a reason that is
arithmetic rather than anatomical. `reference/panjabi_1992.csv` ships as an example; supply
your own with --reference, columns: measure, level, mean, sem, n (n defaults to 12).
"""
from __future__ import annotations

import csv
import math
import os
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import phenotype as PH
import scheme as S
from border import BASE, Corpus

HERE = os.path.dirname(os.path.abspath(__file__))

# column template, axis label, and the name this measure has in a reference table
MEASURES = {
    "endplate": ("endplate_width_{}_mm", "End-plate width (mm)", "endplate"),
    "h_ant":    ("body_height_{}_mm", "Anterior body height (mm)", "h_ant"),
    "h_post":   ("body_height_post_{}_mm", "Posterior body height (mm)", "h_post"),
    "canal_w":  ("canal_width_{}_mm", "Canal width (mm)", "canal_w"),
    "tp_span":  ("tp_span_{}_mm", "Transverse-process span (mm)", "tp_span"),
}
REF_K = 1.96
COHORT = "#2a5d8f"
REFCOL = "#b2182b"

# THE LAST LUMBAR LEVEL IS WITHHELD FOR TWO MEASURES, AND THIS TRAVELS WITH THE CODE.
# End-plate width and pedicle width are both taken from a body isolated by cutting the mask
# at the anterior wall of the canal. At the last lumbar level the transverse processes and
# pedicle roots arise far enough forward to fall in front of that cut, so the cut keeps them:
# in CTSpinoPelvic1K the L5 median ran about 2 mm wide with an SD 1.58x the levels above, and
# three separation rules were built and run over all 802 records without beating the one that
# ships. It is a property of the measurement, not of that cohort, so any corpus measured with
# measure_levels.py inherits it. --no-withhold draws the level anyway and says so.
WITHHOLD_LAST_LUMBAR = {"endplate", "pedicle"}


def withheld_level(measure, levels):
    """The level to drop for this measure, or None."""
    if measure not in WITHHOLD_LAST_LUMBAR:
        return None
    lumbar = [l for l in levels if l.startswith("L") and l[1:].isdigit()]
    return max(lumbar, key=lambda l: int(l[1:])) if lumbar else None


def _style(scale=1.0):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": "sans-serif",
        # Arial and Helvetica first: journals and meetings ask for them, and the fallback
        # is named so a machine without them still produces a sans-serif figure
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 11 * scale,
        "axes.labelsize": 11 * scale,
        "axes.titlesize": 11.5 * scale,
        "xtick.labelsize": 10 * scale,
        "ytick.labelsize": 10 * scale,
        "legend.fontsize": 9.5 * scale,
        "axes.linewidth": 0.9,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "pdf.fonttype": 42,      # real text in the PDF, not outlines: editable and searchable
        "ps.fonttype": 42,
        "savefig.bbox": "tight",
    })
    return plt


def read_reference(path, measure):
    """{level: (mean, population SD)} for one measure, or {}."""
    if not path or not os.path.exists(path):
        return {}
    out = {}
    with open(path) as fh:
        rows = csv.DictReader([l for l in fh if not l.startswith("#")])
        for r in rows:
            if (r.get("measure") or "").strip() != measure:
                continue
            try:
                mean = float(r["mean"])
            except (TypeError, ValueError, KeyError):
                continue
            n = float(r.get("n") or 12)
            sd = r.get("sd")
            try:
                sd = float(sd)
            except (TypeError, ValueError):
                try:
                    sd = float(r["sem"]) * math.sqrt(n)     # SEM -> population SD
                except (TypeError, ValueError, KeyError):
                    continue
            out[(r.get("level") or "").strip()] = (mean, sd)
    return out


def values_by_level(corpus: Corpus, column, levels):
    out = {}
    for l in levels:
        v = []
        for r in corpus.rows:
            try:
                x = float(r[column.format(l)])
            except (TypeError, ValueError, KeyError):
                continue
            if x > 0:
                v.append(x)
        out[l] = np.asarray(v, float)
    return out


def per_case_values(corpus: Corpus, column, levels):
    out = defaultdict(dict)
    for r in corpus.rows:
        for l in levels:
            try:
                x = float(r[column.format(l)])
            except (TypeError, ValueError, KeyError):
                continue
            if x > 0:
                out[r[corpus.case_key]][l] = x
    return out


def _violins(ax, data, levels, ys, color, alpha=0.75, edge="black"):
    keep = [(data[l], p) for l, p in zip(levels, ys) if len(data.get(l, [])) > 1]
    if not keep:
        return
    parts = ax.violinplot([v for v, _ in keep], positions=[p for _, p in keep],
                          vert=False, widths=0.84, showextrema=False, showmedians=True)
    for b in parts["bodies"]:
        b.set_facecolor(color)
        b.set_alpha(alpha)
        b.set_edgecolor(edge)
        b.set_linewidth(0.5)
    parts["cmedians"].set_color("black" if edge != "none" else "0.3")
    parts["cmedians"].set_linewidth(1.2)


def _frame(ax, levels, ys, xlabel):
    ax.set_yticks(ys)
    ax.set_yticklabels(levels)
    ax.set_ylim(0.4, len(levels) + 0.7)
    ax.set_xlabel(xlabel)
    ax.grid(True, axis="both", color="0.88", linewidth=0.5)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def _save(fig, out_base):
    outs = []
    for ext in ("pdf", "png"):
        p = "%s.%s" % (out_base, ext)
        fig.savefig(p, dpi=300)
        outs.append(p)
    print("wrote " + " and ".join(outs))
    return outs


def plot_levels(corpus, measure, out_base, reference=None, levels=None, title=None,
                scale=1.0, withhold=True):
    """Every case, one violin per level, reference interval over it."""
    plt = _style(scale)
    column, xlabel, refname = MEASURES[measure]
    levels = [l for l in (levels or corpus.levels)]
    drop = withheld_level(measure, levels) if withhold else None
    if drop:
        levels = [l for l in levels if l != drop]
        print("  %s withheld for %s: the transverse processes fall in front of the body cut"
              % (drop, measure))
    ys = list(range(len(levels), 0, -1))
    data = values_by_level(corpus, column, levels)
    refs = read_reference(reference, refname)

    fig, ax = plt.subplots(figsize=(7.2, 0.62 * len(levels) + 1.5),
                           constrained_layout=True)
    _violins(ax, data, levels, ys, COHORT)
    for l, p in zip(levels, ys):
        if l in refs and len(data.get(l, [])) > 1:
            m, sd = refs[l]
            ax.plot([m - REF_K * sd, m + REF_K * sd], [p + 0.42] * 2, color=REFCOL,
                    linewidth=2.0, solid_capstyle="butt", zorder=5)
            ax.plot([m], [p + 0.42], marker="|", color=REFCOL, markersize=9,
                    markeredgewidth=2.0, zorder=6)
    _frame(ax, levels, ys, xlabel)
    n_cases = len({r[corpus.case_key] for r in corpus.rows})
    ax.set_title(title or "%s by vertebral level" % xlabel.split(" (")[0])
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    h = [Patch(facecolor=COHORT, alpha=0.75, edgecolor="black",
               label="this cohort, $n$=%d" % n_cases)]
    if refs:
        h.append(Line2D([0], [0], color=REFCOL, linewidth=2.0,
                        label="reference, mean $\\pm$ 1.96 SD"))
    ax.legend(handles=h, loc="best", frameon=True, framealpha=0.95)
    return _save(fig, out_base)


def plot_classes(corpus, measure, out_base, phenotypes, reference=None, levels=None,
                 accuracy=None, violin_min=40, scale=1.0, withhold=True):
    """One panel per phenotype over the typical column."""
    plt = _style(scale)
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    column, xlabel, refname = MEASURES[measure]
    levels = [l for l in (levels or corpus.levels)]
    drop = withheld_level(measure, levels) if withhold else None
    if drop:
        levels = [l for l in levels if l != drop]
    ys = list(range(len(levels), 0, -1))
    refs = read_reference(reference, refname)
    vals = per_case_values(corpus, column, levels)

    cls = {c: p.get("phenotype", "typical") for c, p in phenotypes.items()}
    groups = [k for k in PH.CLASS_ORDER
              if k != "typical" and any(v == k for v in cls.values())]
    if not groups:
        raise SystemExit("every case is the typical column; nothing to break out")
    typical = [c for c, k in cls.items() if k == "typical"]
    base = {l: np.array([vals[c][l] for c in typical if l in vals.get(c, {})], float)
            for l in levels}
    if not any(len(v) for v in base.values()):
        raise SystemExit("no typical cases carry this measure; cannot draw the background")

    n = len(groups)
    fig, axes = plt.subplots(1, n, figsize=(3.2 * n, 0.52 * len(levels) + 2.3),
                             sharex=True, sharey=True, constrained_layout=True)
    axes = np.atleast_1d(axes)
    lo = min(np.percentile(v, 0.5) for v in base.values() if len(v))
    hi = max(np.percentile(v, 99.5) for v in base.values() if len(v))
    pad = 0.08 * (hi - lo)
    rng = np.random.default_rng(7)

    for ax, key in zip(axes, groups):
        _violins(ax, base, levels, ys, "0.72", alpha=0.6, edge="none")
        for l, p in zip(levels, ys):
            if l in refs and len(base.get(l, [])):
                m, sd = refs[l]
                ax.plot([m - REF_K * sd, m + REF_K * sd], [p + 0.40] * 2, color=REFCOL,
                        linewidth=1.5, solid_capstyle="butt", zorder=5)
        sel = [c for c, k in cls.items() if k == key]
        if len(sel) >= violin_min:
            d = {l: np.array([vals[c][l] for c in sel if l in vals.get(c, {})], float)
                 for l in levels}
            _violins(ax, d, levels, ys, COHORT, alpha=0.65)
        else:
            for l, p in zip(levels, ys):
                v = [vals[c][l] for c in sel if l in vals.get(c, {})]
                if v:
                    ax.scatter(v, np.full(len(v), p) + (rng.random(len(v)) - 0.5) * 0.30,
                               s=17, color=COHORT, edgecolor="white", linewidth=0.4,
                               zorder=7)
        head = PH.PRETTY.get(key, key)
        sub = "$n$=%d" % len(sel)
        if accuracy and key in accuracy and accuracy[key][0]:
            k_, n_ = accuracy[key][1], accuracy[key][0]
            sub += "   border correct %.0f%%" % (100.0 * k_ / n_)
        ax.set_title("%s\n%s" % (head, sub))
        _frame(ax, levels, ys, xlabel)
        ax.set_xlim(lo - pad, hi + pad)

    h = [Patch(facecolor="0.72", alpha=0.6, label="typical column, $n$=%d" % len(typical)),
         Line2D([0], [0], marker="o", color="none", markerfacecolor=COHORT,
                markeredgecolor="white", markersize=7, label="this class, one per case")]
    if refs:
        h.append(Line2D([0], [0], color=REFCOL, linewidth=1.5,
                        label="reference, mean $\\pm$ 1.96 SD"))
    fig.legend(handles=h, loc="outside lower center", ncol=len(h), frameon=False)
    return _save(fig, out_base)
