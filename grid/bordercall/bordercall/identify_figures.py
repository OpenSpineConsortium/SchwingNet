"""The figures of the identifiability study, from its recorded JSON and nothing else.

    python run.py identify-figures --json ../records/identify-2026-10-26/identify.json --outdir ../records/identify-2026-10-26/figures

Drawn as junction_figures.py draws: black ink, serif type, an axis on two sides, no grid, no
colour; a series is told apart by its line and marker. The widths of the field keep one style
throughout: one body, dotted with open triangles; three, dashed with open squares; five, solid
with open circles; nine, solid with filled circles. Every figure is written as PDF (no date
inside), PNG, the CSV of the numbers drawn and its caption, and FIGURES.md records the run and
the code by sha256. Captions stay under sixty words; the argument is in
docs/LEVEL_IDENTIFIABILITY_RESULTS.md. Every number here is about synthetic columns drawn from
Panjabi's tables, never a patient.
"""
from __future__ import annotations

import json
import os
import platform
import sys
from typing import Dict, List

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import junction_figures as JF                                       # noqa: E402
import neighbour_figures as NF                                      # noqa: E402
import panjabi as P                                                 # noqa: E402

INK = JF.INK
style, letter, save, write_csv, sha256 = JF.style, JF.letter, JF.save, JF.write_csv, JF.sha256
REGIME_STYLE, REGIME_NAME = NF.REGIME_STYLE, NF.REGIME_NAME
WIDTH_STYLE = {1: dict(linestyle=":", marker="^", markerfacecolor="white"),
               3: dict(linestyle="--", marker="s", markerfacecolor="white"),
               5: dict(linestyle="-", marker="o", markerfacecolor="white"),
               7: dict(linestyle="-.", marker="D", markerfacecolor="white", markersize=3),
               9: dict(linestyle="-", marker="o", markerfacecolor=INK)}
SIZE_STYLE = {"size_known": dict(linestyle="--", marker="s", markerfacecolor="white"),
              "size_unknown": dict(linestyle="-", marker="o", markerfacecolor=INK),
              "shape_only": dict(linestyle=":", marker="^", markerfacecolor="white")}
SIZE_NAME = {"size_known": "Patient's size known", "size_unknown": "Size unknown (one body as drawn)",
             "shape_only": "Shape only, size removed"}
MEASURE_SHORT = {"endplate": "Upper end-plate width", "endplate_depth": "Upper end-plate depth",
                 "endplate_lower": "Lower end-plate width", "endplate_lower_depth": "Lower end-plate depth",
                 "h_post": "Posterior body height", "canal_w": "Canal width", "canal_ap": "Canal depth"}
Z = 1.959964
# where each level's label sits beside its point in the Fig 2A panel, so none overlap
LABEL_OFFSET = {"C3": (0.4, -1.1, "left"), "C4": (0.4, 0.5, "left"), "C5": (-0.3, 0.3, "right"), "C6": (-0.3, 0.4, "right"),
                "C7": (0.3, 0.5, "left"), "T1": (-0.4, 0.3, "right"), "T2": (-0.7, -2.0, "center"), "T3": (0.2, 1.1, "left"),
                "T4": (0.0, -2.1, "center"), "T5": (0.5, -1.3, "left"), "T6": (0.3, -1.4, "left"), "T7": (0.3, -1.4, "left"),
                "T8": (0.3, -1.4, "left"), "T9": (0.3, -1.4, "left"), "T10": (0.3, -1.4, "left"), "T11": (0.3, -1.4, "left"),
                "T12": (0.3, -1.5, "left"), "L1": (-0.3, -1.6, "right"), "L2": (0.3, -0.4, "left"), "L3": (-0.4, 0.5, "right"),
                "L4": (0.3, 0.3, "left"), "L5": (-0.3, 0.3, "right")}

CAPTIONS = {
    "identify_kunkel":
        "Kunkel 2010's Fig 2A with the spreads drawn. A, the level means of the upper end-plate "
        "width against the posterior body height from Panjabi's tables, bars one population SD "
        "each way; filled, the sixteen levels Kunkel used, with the cubic refitted on them; open, "
        "the cervical levels and L5 Kunkel left out. B, each level's gap to its nearest other "
        "level along the body height, in units of one body's spread in the generator.",
    "identify_isolation":
        "How isolated each level is in the measure space, one body: the Mahalanobis distance to "
        "its nearest other level under the within-level covariance of a draw of synthetic columns. "
        "A, seven measures with the patient's size known, unknown, and removed. B, size unknown, "
        "by projection regime. A distance of 1 is one pooled SD.",
    "identify_levels":
        "Which levels the classifier names, typical columns, both planes: A, the share of each "
        "true level named exactly (recall), B, the share of calls of each name that are right "
        "(precision), by the number of bodies in the field. Bars, 95%% Wilson intervals on the "
        "recall; %d synthetic columns scored. Levels at the ends of the column drop out as the "
        "field widens.",
    "identify_confusion":
        "What each level is mistaken for, both planes, typical columns: the share of each true "
        "level (rows) given each name (columns), the area of a square proportional to the share; "
        "A, one body; B, five bodies. The diagonal is the recall. %d synthetic columns scored.",
    "identify_abstain":
        "What can be named with near certainty: the share of true bodies of each level kept when "
        "the classifier names that level only above a confidence chosen on another seed to reach "
        "95%% precision, by the number of bodies in the field, both planes, typical columns; the "
        "precision reached on the scoring seed is in the CSV.",
    "identify_measures":
        "Which measure isolates which level, one body, size unknown: the nearest-rival distance of "
        "each level along each measure alone (rows), and along all seven (top row), the area of a "
        "square proportional to the distance; from the within-level moments of %d synthetic "
        "columns.",
    "identify_field":
        "What a wider field adds, by the formula: A, each level's nearest-rival distance when the "
        "field around it is named as a whole, by the number of bodies in view, the shared size and "
        "the shared offsets of one patient in the joint covariance, so the field profiles them out "
        "as far as the Gaussian allows; a level drops out where the field no longer fits in the "
        "column. B, one body: the formula's distance with the 95%% interval the reference table's "
        "own sampling error gives it (%d redraws of the twelve-spine means and SDs), and the same "
        "distance with the table's two pedicle rows added, which no SPINEPS label measures.",
    "identify_ceiling":
        "The most one body can be named, both planes, typical columns: recall by level under the "
        "exact likelihood of the generator with the size integrated out, which no classifier can "
        "pass; under the quadratic rule from the moments of a draw; under the linear classifier "
        "the study uses; and under the same linear classifier with the table's two pedicle rows "
        "added. %d synthetic columns scored.",
    "identify_size":
        "What the patient's size does to naming one body, both planes: recall by level with the "
        "size spread removed, as drawn (7 per cent) and doubled; and, at the drawn spread, from "
        "the shape alone (size removed from the features) and from the published means with "
        "nothing fitted. %d synthetic columns scored.",
}


def cell_of(d: dict, regime: str, half: int) -> dict:
    cells = d["table"]["cells"] if regime == "table" else d["cells"]
    for c in cells:
        if c["regime"] == regime and c["half"] == half:
            return c
    raise KeyError((regime, half))


def _levels_x(levels: List[str]):
    return np.arange(len(levels)), levels


def _level_axis(ax, levels: List[str], fontsize: float = 6.5):
    x, _ = _levels_x(levels)
    ax.set_xticks(x)
    ax.set_xticklabels(levels, fontsize=fontsize, rotation=90)
    ax.set_xlim(-0.7, len(levels) - 0.3)


# ---- 1 Kunkel's Fig 2A with spreads ----------------------------------------------------------------

def fig_kunkel(d: dict, outdir: str):
    plt = style()
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.0, 3.1), gridspec_kw={"width_ratios": [1.15, 1.0]})
    hp = d["one_measure"]["h_post"]["all_22"]
    ep = d["one_measure"]["endplate"]["all_22"]
    kl = set(d["kunkel_levels"])
    rows = []
    for lv in d["classes"]:
        x, y = hp[lv]["mean_mm"], ep[lv]["mean_mm"]
        sx, sy = hp[lv]["table_sd_mm"], ep[lv]["table_sd_mm"]
        filled = lv in kl
        a.errorbar([x], [y], xerr=[sx], yerr=[sy], color=INK, elinewidth=0.5, capsize=1.5, marker="o",
                   markerfacecolor=INK if filled else "white", markersize=3.8, linestyle="none")
        dx, dy, ha = LABEL_OFFSET.get(lv, (0.25, 0.6, "left"))
        a.text(x + dx, y + dy, lv, fontsize=5.6, ha=ha, va="bottom")
        rows.append({"level": lv, "in_kunkel": int(filled), "h_post_mean_mm": x, "h_post_sd_mm": sx,
                     "endplate_mean_mm": y, "endplate_sd_mm": sy,
                     "gap_body_sd": hp[lv]["gap_body_sd"], "gap_table_sd": hp[lv]["gap_table_sd"],
                     "rival_along_h_post": hp[lv]["rival"], "gap_mm": hp[lv]["gap_mm"]})
    c = d["kunkel"]["measures"]["endplate"]["cubic_16"]["coefficients"]
    xs = np.linspace(min(hp[lv]["mean_mm"] for lv in kl) - 0.5, max(hp[lv]["mean_mm"] for lv in kl) + 0.5, 100)
    a.plot(xs, c[0] + c[1] * xs + c[2] * xs ** 2 + c[3] * xs ** 3, color=INK, linewidth=0.9,
           label="Cubic refitted on T1 to L4, R$^2$ %.3f" % d["kunkel"]["measures"]["endplate"]["cubic_16"]["r2"])
    a.set_xlabel("Posterior body height, mean, mm")
    a.set_ylabel("Upper end-plate width, mean, mm")
    a.legend(loc="upper left")
    letter(a, "A")
    levels = d["classes"]
    x, _ = _levels_x(levels)
    body = [hp[lv]["gap_body_sd"] for lv in levels]
    table = [hp[lv]["gap_table_sd"] for lv in levels]
    b.bar(x, body, width=0.62, facecolor="white", edgecolor=INK, linewidth=0.8, label="Gap over one body's spread")
    b.plot(x, table, linestyle="none", marker="_", color=INK, markersize=7, markeredgewidth=1.0,
           label="Gap over the table's SD alone")
    _level_axis(b, levels)
    b.set_ylabel("Nearest level along the body height, SD")
    b.axhline(1.0, color=INK, linewidth=0.5, linestyle=":")
    i0, i1 = levels.index("T1"), levels.index("L4")
    b.annotate("", xy=(i0 - 0.4, 1.12), xytext=(i1 + 0.4, 1.12), arrowprops=dict(arrowstyle="|-|", linewidth=0.7, color=INK))
    b.text(0.5 * (i0 + i1), 1.15, "Kunkel's levels, T1 to L4", ha="center", va="bottom", fontsize=6.5)
    b.set_ylim(0, 1.35)
    b.legend(loc="lower left", bbox_to_anchor=(0.0, 1.0), fontsize=6.5, frameon=False)
    letter(b, "B")
    fig.tight_layout(w_pad=1.5)
    write_csv(outdir, "identify_kunkel", rows, ["level", "in_kunkel", "h_post_mean_mm", "h_post_sd_mm", "endplate_mean_mm",
                                                "endplate_sd_mm", "gap_body_sd", "gap_table_sd", "rival_along_h_post", "gap_mm"])
    return save(fig, outdir, "identify_kunkel", CAPTIONS["identify_kunkel"])


# ---- 2 the isolation ---------------------------------------------------------------------------------

def fig_isolation(d: dict, outdir: str):
    plt = style()
    fig, (a, b) = plt.subplots(2, 1, figsize=(5.2, 4.6), sharex=True)
    levels = d["classes"]
    x, _ = _levels_x(levels)
    rows = []
    both = d["isolation"]["both"]
    for mode in ("size_known", "size_unknown", "shape_only"):
        y = [both[mode]["nearest"][lv]["d"] for lv in levels]
        a.plot(x, y, color=INK, label=SIZE_NAME[mode], **SIZE_STYLE[mode])
    for regime in ("both", "ap", "lateral"):
        y = [d["isolation"][regime]["size_unknown"]["nearest"][lv]["d"] for lv in levels]
        b.plot(x, y, color=INK, label=REGIME_NAME[regime], **REGIME_STYLE[regime])
    for lv in levels:
        rows.append({"level": lv,
                     **{"d_%s" % mode: both[mode]["nearest"][lv]["d"] for mode in ("size_known", "size_unknown", "shape_only")},
                     **{"rival_%s" % mode: both[mode]["nearest"][lv]["rival"] for mode in ("size_known", "size_unknown", "shape_only")},
                     **{"d_%s" % r: d["isolation"][r]["size_unknown"]["nearest"][lv]["d"] for r in ("ap", "lateral")}})
    for ax in (a, b):
        ax.axhline(1.0, color=INK, linewidth=0.5, linestyle=":")
        ax.set_ylabel("Nearest rival, pooled SD")
        ax.set_ylim(0, max(2.9, 1.05 * max(r["d_size_known"] for r in rows)))
    a.legend(loc="upper right")
    b.legend(loc="upper right")
    letter(a, "A")
    letter(b, "B")
    _level_axis(b, levels)
    fig.tight_layout(h_pad=0.6)
    write_csv(outdir, "identify_isolation", rows, list(rows[0].keys()))
    return save(fig, outdir, "identify_isolation", CAPTIONS["identify_isolation"])


# ---- 3 recall and precision by level --------------------------------------------------------------

def fig_levels(d: dict, outdir: str):
    plt = style()
    fig, (a, b) = plt.subplots(2, 1, figsize=(5.2, 4.8), sharex=True)
    levels = d["classes"]
    x, _ = _levels_x(levels)
    rows = []
    halves = {c["visible_bodies"]: c["half"] for c in d["cells"] if c["regime"] == "both"}
    for bodies in (1, 3, 5, 9):
        if bodies not in halves:
            continue
        c = cell_of(d, "both", halves[bodies])
        xs, rec, lo, hi, prec = [], [], [], [], []
        for i, lv in enumerate(levels):
            if lv not in c["by_level"]:
                continue
            t = c["by_level"][lv]
            xs.append(i)
            rec.append(t["recall"])
            lo.append(t["recall"] - t["recall_wilson"][0])
            hi.append(t["recall_wilson"][1] - t["recall"])
            prec.append(t["precision"])
            rows.append({"visible_bodies": bodies, "level": lv, "recall": t["recall"], "wilson_lo": t["recall_wilson"][0],
                         "wilson_hi": t["recall_wilson"][1], "precision": t["precision"], "f1": t["f1"],
                         "auc": t["auc"], "within_one": t["within_one"], "n": t["n"]})
        st = WIDTH_STYLE[bodies]
        a.errorbar(xs, 100 * np.asarray(rec), yerr=100 * np.asarray([lo, hi]), color=INK, elinewidth=0.5,
                   label="%d bod%s" % (bodies, "y" if bodies == 1 else "ies"), **st)
        b.plot(xs, 100 * np.asarray(prec), color=INK, label="%d bod%s" % (bodies, "y" if bodies == 1 else "ies"), **st)
    a.set_ylabel("Recall, per cent")
    b.set_ylabel("Precision, per cent")
    for ax in (a, b):
        ax.set_ylim(0, 103)
    a.legend(loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=4, frameon=False)
    letter(a, "A")
    letter(b, "B")
    _level_axis(b, levels)
    fig.tight_layout(h_pad=0.6)
    write_csv(outdir, "identify_levels", rows, ["visible_bodies", "level", "recall", "wilson_lo", "wilson_hi", "precision",
                                                "f1", "auc", "within_one", "n"])
    return save(fig, outdir, "identify_levels", CAPTIONS["identify_levels"] % d["n_columns"]["score_typical"])


# ---- 4 the confusion ----------------------------------------------------------------------------------

def hinton(ax, M: np.ndarray, row_labels: List[str], col_labels: List[str], scale: float = 1.0):
    """Squares whose area is proportional to the entry, black on white, rows from the top."""
    from matplotlib.patches import Rectangle
    n, m = M.shape
    for i in range(n):
        for j in range(m):
            v = M[i, j]
            if v <= 0:
                continue
            s = min(1.0, np.sqrt(v / scale)) * 0.92
            ax.add_patch(Rectangle((j - s / 2, (n - 1 - i) - s / 2), s, s, facecolor=INK, edgecolor="none"))
    ax.set_xlim(-0.6, m - 0.4)
    ax.set_ylim(-0.6, n - 0.4)
    ax.set_xticks(range(m))
    ax.set_xticklabels(col_labels, fontsize=5.6, rotation=90)
    ax.set_yticks(range(n))
    ax.set_yticklabels(list(reversed(row_labels)), fontsize=5.6)
    ax.set_aspect("equal")
    ax.tick_params(length=0)


def fig_confusion(d: dict, outdir: str):
    plt = style()
    halves = {c["visible_bodies"]: c["half"] for c in d["cells"] if c["regime"] == "both"}
    bodies = [b for b in (1, 5) if b in halves] or [max(halves)]
    fig, axes = plt.subplots(1, len(bodies), figsize=(3.4 * len(bodies), 3.6))
    axes = np.atleast_1d(axes)
    rows = []
    for ax, nb in zip(axes, bodies):
        c = cell_of(d, "both", halves[nb])
        levels = c["levels"]
        idx = [d["classes"].index(lv) for lv in levels]
        conf = np.asarray(c["confusion"], float)[np.ix_(idx, idx)]
        share = conf / np.maximum(conf.sum(1, keepdims=True), 1)
        hinton(ax, share, levels, levels)
        ax.set_xlabel("Name given")
        ax.set_ylabel("True level")
        ax.set_title("%d bod%s" % (nb, "y" if nb == 1 else "ies"), fontsize=8)
        for i, lv in enumerate(levels):
            for j, nm in enumerate(levels):
                if conf[i, j]:
                    rows.append({"visible_bodies": nb, "true_level": lv, "named": nm, "count": int(conf[i, j]), "share": share[i, j]})
    letter(axes[0], "A")
    if len(axes) > 1:
        letter(axes[1], "B")
    fig.tight_layout(w_pad=1.0)
    write_csv(outdir, "identify_confusion", rows, ["visible_bodies", "true_level", "named", "count", "share"])
    return save(fig, outdir, "identify_confusion", CAPTIONS["identify_confusion"] % d["n_columns"]["score_typical"])


# ---- 5 abstention ---------------------------------------------------------------------------------------

def fig_abstain(d: dict, outdir: str):
    plt = style()
    fig, ax = plt.subplots(figsize=(5.2, 2.9))
    levels = d["classes"]
    halves = {c["visible_bodies"]: c["half"] for c in d["cells"] if c["regime"] == "both"}
    rows = []
    for bodies in (1, 3, 5, 9):
        if bodies not in halves:
            continue
        c = cell_of(d, "both", halves[bodies])
        xs, kept = [], []
        for i, lv in enumerate(levels):
            if lv not in c["abstain"]:
                continue
            for t in d["precision_targets"]:
                e = c["abstain"][lv][str(t)]
                rows.append({"visible_bodies": bodies, "level": lv, "target_precision": t, "threshold": e["threshold"],
                             "precision_scored": e["precision"], "kept": e["kept"], "n_called": e["n_called"]})
            e = c["abstain"][lv]["0.95"]
            xs.append(i)
            kept.append(e["kept"])
        ax.plot(xs, 100 * np.asarray(kept), color=INK, label="%d bod%s" % (bodies, "y" if bodies == 1 else "ies"), **WIDTH_STYLE[bodies])
    ax.set_ylabel("True bodies kept at 95% precision, per cent")
    ax.set_ylim(0, 103)
    ax.legend(loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=4, frameon=False)
    _level_axis(ax, levels)
    fig.tight_layout()
    write_csv(outdir, "identify_abstain", rows, ["visible_bodies", "level", "target_precision", "threshold", "precision_scored",
                                                 "kept", "n_called"])
    return save(fig, outdir, "identify_abstain", CAPTIONS["identify_abstain"])


# ---- 6 which measure isolates which level ------------------------------------------------------------

def fig_measures(d: dict, outdir: str):
    plt = style()
    levels = d["classes"]
    measures = d["measures"]
    sub = d["subsets"]
    M = np.zeros((len(measures) + 1, len(levels)))
    rows = []
    for j, lv in enumerate(levels):
        M[0, j] = sub["full"][lv]
        rows.append({"measure": "all seven", "level": lv, "d": sub["full"][lv]})
        for i, m in enumerate(measures):
            M[i + 1, j] = sub["per_measure"][m][lv]
            rows.append({"measure": m, "level": lv, "d": sub["per_measure"][m][lv]})
    fig, ax = plt.subplots(figsize=(5.6, 2.9))
    hinton(ax, M, ["All seven"] + [MEASURE_SHORT[m] for m in measures], levels, scale=float(M.max()))
    ax.set_xlabel("Level")
    ax.text(len(levels) - 0.4, len(measures) + 0.9, "largest square, %.2f SD" % M.max(), ha="right", va="bottom", fontsize=6.5)
    fig.tight_layout()
    write_csv(outdir, "identify_measures", rows, ["measure", "level", "d"])
    return save(fig, outdir, "identify_measures", CAPTIONS["identify_measures"] % d["isolation"]["both"]["n_columns"])


# ---- 7 the size -----------------------------------------------------------------------------------------

def fig_size(d: dict, outdir: str):
    plt = style()
    fig, (a, b) = plt.subplots(2, 1, figsize=(5.2, 4.6), sharex=True)
    levels = d["classes"]
    x, _ = _levels_x(levels)
    rows = []
    variants = [v for v in d["size"]["variants"] if v["half"] == 0]
    ladder = {v["scale_sd"]: v for v in variants if v["features"] == "absolute"}
    styles = {0.0: SIZE_STYLE["size_known"], 0.07: SIZE_STYLE["size_unknown"], 0.14: dict(linestyle="-.", marker="D", markerfacecolor="white")}
    names = {0.0: "Size spread removed", 0.07: "As drawn, 7 per cent", 0.14: "Doubled, 14 per cent"}
    for s, v in sorted(ladder.items()):
        y = [v["recall_by_level"].get(lv, np.nan) for lv in levels]
        a.plot(x, 100 * np.asarray(y), color=INK, label=names[s], **styles[s])
        rows += [{"panel": "A", "variant": "scale_sd %.2f" % s, "level": lv, "recall": v["recall_by_level"].get(lv), "exact_all": v["exact"]} for lv in levels]
    others = {v["features"]: v for v in variants if v["scale_sd"] == 0.07}
    st = {"absolute": SIZE_STYLE["size_unknown"], "shape_only": SIZE_STYLE["shape_only"],
          "published_means": dict(linestyle="none", marker="x", markersize=5)}
    nm = {"absolute": "Seven measures as drawn", "shape_only": "Shape only, size removed", "published_means": "Published means, nothing fitted"}
    for key in ("absolute", "shape_only", "published_means"):
        if key not in others:
            continue
        v = others[key]
        y = [v["recall_by_level"].get(lv, np.nan) for lv in levels]
        b.plot(x, 100 * np.asarray(y), color=INK, label=nm[key], **st[key])
        rows += [{"panel": "B", "variant": key, "level": lv, "recall": v["recall_by_level"].get(lv), "exact_all": v["exact"]} for lv in levels]
    for ax in (a, b):
        ax.set_ylabel("Recall, one body, per cent")
        ax.set_ylim(0, 103)
        ax.legend(loc="upper right")
    letter(a, "A")
    letter(b, "B")
    _level_axis(b, levels)
    fig.tight_layout(h_pad=0.6)
    write_csv(outdir, "identify_size", rows, ["panel", "variant", "level", "recall", "exact_all"])
    return save(fig, outdir, "identify_size", CAPTIONS["identify_size"] % d["n_columns"]["score_typical"])


# ---- 8 the field by the formula, and the table's own error -------------------------------------------

def fig_field(d: dict, outdir: str):
    plt = style()
    fig, (a, b) = plt.subplots(2, 1, figsize=(5.2, 4.8), sharex=True)
    levels = d["classes"]
    x, _ = _levels_x(levels)
    rows = []
    for f in d["field_isolation"]:
        n = f["visible_bodies"]
        if n not in WIDTH_STYLE:
            continue
        y = [f["nearest"].get(lv, {}).get("d", np.nan) for lv in levels]
        a.plot(x, y, color=INK, label="%d bod%s" % (n, "y" if n == 1 else "ies"), **WIDTH_STYLE[n])
        rows += [{"panel": "A", "visible_bodies": n, "level": lv, "d": f["nearest"].get(lv, {}).get("d"),
                  "rival": f["nearest"].get(lv, {}).get("rival")} for lv in levels if lv in f["nearest"]]
    tb = d["table_bootstrap"]["by_level"]
    point = np.array([tb[lv]["d_point"] for lv in levels])
    lo = np.array([tb[lv]["d_lo"] for lv in levels])
    hi = np.array([tb[lv]["d_hi"] for lv in levels])
    b.fill_between(x, lo, hi, color=INK, alpha=0.15, linewidth=0, label="95% interval from the table's sampling error")
    b.plot(x, point, color=INK, linestyle="-", marker="o", markerfacecolor=INK, markersize=3.5, linewidth=0.9,
           label="Seven measures, the table as printed")
    table = d["table"]["isolation_size_unknown"]
    b.plot(x, [table[lv]["d"] for lv in levels], color=INK, linestyle="--", marker="s", markerfacecolor="white",
           label="With the table's pedicle rows added (not measurable)")
    rows += [{"panel": "B", "visible_bodies": 1, "level": lv, "d": tb[lv]["d_point"], "d_lo": tb[lv]["d_lo"],
              "d_hi": tb[lv]["d_hi"], "most_isolated_share": tb[lv]["most_isolated_7"],
              "rank_point": tb[lv]["rank_7_point"], "d_with_pedicle_rows": table[lv]["d"],
              "rival_with_pedicle_rows": table[lv]["rival"]} for lv in levels]
    for ax in (a, b):
        ax.axhline(1.0, color=INK, linewidth=0.5, linestyle=":")
        ax.set_ylabel("Nearest rival, pooled SD")
    a.set_ylim(0, 1.25 * max(r["d"] for r in rows if r["panel"] == "A" and r["d"] is not None))
    b.set_ylim(0, 1.45 * max(max(hi), max(r["d_with_pedicle_rows"] for r in rows if r["panel"] == "B")))
    a.legend(loc="upper center", bbox_to_anchor=(0.5, 1.02), ncol=5, frameon=False, fontsize=6.5)
    b.legend(loc="upper center", bbox_to_anchor=(0.5, 1.02), ncol=1, frameon=False, fontsize=6.5)
    letter(a, "A")
    letter(b, "B")
    _level_axis(b, levels)
    fig.tight_layout(h_pad=0.6)
    keys = ["panel", "visible_bodies", "level", "d", "rival", "d_lo", "d_hi", "most_isolated_share", "rank_point",
            "d_with_pedicle_rows", "rival_with_pedicle_rows"]
    write_csv(outdir, "identify_field", rows, keys)
    return save(fig, outdir, "identify_field", CAPTIONS["identify_field"] % d["table_bootstrap"]["n_draws"])


# ---- 9 the ceiling at one body ----------------------------------------------------------------------------

def fig_ceiling(d: dict, outdir: str):
    plt = style()
    fig, ax = plt.subplots(1, 1, figsize=(5.2, 2.9))
    levels = d["classes"]
    x, _ = _levels_x(levels)
    series = [("exact_likelihood", "Exact likelihood, the ceiling", d["bayes"]["exact_likelihood"]["recall_by_level"],
               dict(linestyle="-", marker="o", markerfacecolor=INK)),
              ("quadratic", "Quadratic rule from the draw's moments", d["bayes"]["quadratic_from_moments"]["recall_by_level"],
               dict(linestyle="--", marker="s", markerfacecolor="white")),
              ("linear", "Linear classifier (the study's)", {lv: v["recall"] for lv, v in cell_of(d, "both", 0)["by_level"].items()},
               dict(linestyle=":", marker="^", markerfacecolor="white")),
              ("linear_with_pedicle_rows", "Linear, with the table's pedicle rows (not measurable)",
               {lv: v["recall"] for lv, v in cell_of(d, "table", 0)["by_level"].items()},
               dict(linestyle="-.", marker="D", markerfacecolor="white", markersize=3))]
    rows = []
    for key, name, by, st in series:
        y = [by.get(lv, np.nan) for lv in levels]
        ax.plot(x, 100 * np.asarray(y), color=INK, label=name, **st)
        rows += [{"rule": key, "level": lv, "recall": by.get(lv)} for lv in levels]
    exact = {"exact_likelihood": d["bayes"]["exact_likelihood"]["exact"],
             "quadratic": d["bayes"]["quadratic_from_moments"]["exact"],
             "linear": cell_of(d, "both", 0)["exact"], "linear_with_pedicle_rows": cell_of(d, "table", 0)["exact"]}
    for r in rows:
        r["exact_all"] = exact[r["rule"]]
    ax.set_ylabel("Recall, one body, per cent")
    ax.set_ylim(0, 103)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.02), ncol=2, frameon=False, fontsize=6.5)
    _level_axis(ax, levels)
    fig.tight_layout()
    write_csv(outdir, "identify_ceiling", rows, ["rule", "level", "recall", "exact_all"])
    return save(fig, outdir, "identify_ceiling", CAPTIONS["identify_ceiling"] % d["n_columns"]["score_typical"])


# ---- the record ----------------------------------------------------------------------------------------

def write_record(outdir: str, json_path: str, d: dict, written: List[str]) -> str:
    import matplotlib
    cmd = "python run.py identify-figures --json %s --outdir %s" % (json_path, outdir)
    lines = ["# The identifiability figures", "", "Built with `%s`." % cmd, "",
             "- Run: `%s`, sha256 %s; seeds %s; columns %s; synth %s."
             % (json_path, sha256(json_path), json.dumps(d["seeds"], sort_keys=True),
                json.dumps(d["n_columns"], sort_keys=True), json.dumps(d["synth"], sort_keys=True)),
             "- Reference table: `bordercall/reference/panjabi_full_spine.csv`, sha256 %s." % sha256(P.DEFAULT_REFERENCE)]
    for name in ("identify_figures.py", "identify.py", "neighbour.py", "neighbour_more.py", "neighbour_figures.py",
                 "junction_figures.py", "panjabi.py", "covariance.py"):
        lines.append("- Code: `bordercall/%s`, sha256 %s." % (name, sha256(os.path.join(HERE, name))))
    lines += ["- Python %s, numpy %s, matplotlib %s; serif type %s, embedded in the PDF."
              % (platform.python_version(), np.__version__, matplotlib.__version__, JF.SERIF[0]),
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
    os.makedirs(outdir, exist_ok=True)
    with open(json_path, encoding="utf-8") as fh:
        d = json.load(fh)
    written = []
    for fn in (fig_kunkel, fig_isolation, fig_levels, fig_confusion, fig_abstain, fig_measures, fig_size, fig_field,
               fig_ceiling):
        written += fn(d, outdir)
    written.append(write_record(outdir, json_path, d, written))
    for p in written:
        print("wrote %s" % p)
    return written
