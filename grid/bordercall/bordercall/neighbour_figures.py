"""The figures of the neighbour-identity study, from its recorded JSON and nothing else.

    python run.py neighbour-figures --json records/neighbour-2026-10-26/neighbour.json \
        --enumerate-json records/neighbour-2026-10-26/enumerate.json \
        --more-json records/neighbour-2026-10-26/neighbour_more.json --outdir figures/neighbour

Drawn as junction_figures.py draws: black ink, serif type, an axis on two sides, no grid, no
colour; a series is told apart by its line and marker. The three projection regimes keep one
style throughout: both, a solid line with filled circles; ap, a dashed line with open squares;
lateral, a dotted line with open triangles. Every figure is written as PDF (no date inside), PNG,
the CSV of the numbers drawn and its caption, and FIGURES.md records the run and the code by
sha256. Captions stay under sixty words; the argument is in docs/NEIGHBOUR_IDENTITY_RESULTS.md.
Every number here is about synthetic columns drawn from Panjabi's tables, never a patient.
"""
from __future__ import annotations

import json
import os
import platform
import sys
from typing import List, Optional

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import junction_figures as JF                                       # noqa: E402
import neighbour as NB                                              # noqa: E402
import panjabi as P                                                 # noqa: E402

INK = JF.INK
style, letter, save, write_csv, sha256 = JF.style, JF.letter, JF.save, JF.write_csv, JF.sha256
PHENOTYPE_NAME, PHENOTYPE_ORDER = JF.PHENOTYPE_NAME, JF.PHENOTYPE_ORDER
REGIME_STYLE = {"both": dict(linestyle="-", marker="o", markerfacecolor=INK),
                "ap": dict(linestyle="--", marker="s", markerfacecolor="white"),
                "lateral": dict(linestyle=":", marker="^", markerfacecolor="white")}
REGIME_NAME = {"both": "Both planes, seven measures", "ap": "AP plane, four measures",
               "lateral": "Lateral plane, four measures"}
ARM_NAME = {"below1": "Body below", "above1": "Body above", "flank": "Both neighbours",
            "flank2": "Two each side", "with_target": "Target seen"}
ARM_ORDER = ["below1", "above1", "flank", "flank2", "with_target"]
PHENOTYPE_MARKER = {"typical": "o", "four_lumbar": "v", "six_lumbar": "^", "t13": "s",
                    "lumbar_rib": "D", "no_rib_t12": "x"}
Z = 1.959964

CAPTIONS = {
    "neighbour_field":
        "The field of view named as a whole, the target in it: exact naming by the direct "
        "classifier on every visible body against the number of bodies, three regimes. Filled "
        "markers, typical columns; open markers, the worst phenotype; crosses, the published means "
        "with nothing fitted, both planes. Bars, 95%% column-clustered intervals; %d synthetic "
        "columns per phenotype.",
    "neighbour_arms":
        "Naming a vertebra from its neighbours alone, solution C, by what is visible and by "
        "projection regime. A, typical columns, named exactly; B, the worst of the six phenotypes; "
        "C, the worst phenotype, named within one level. Bars are 95%% intervals from "
        "column-clustered errors; %d synthetic columns per phenotype.",
    "neighbour_levels":
        "Where the neighbours fail to name the body: exact naming by true level on typical "
        "columns, both neighbours visible, solution C, three regimes. The upper thoracic bodies, "
        "alike in every published measure, are the floor; the junctions and the lumbar bodies "
        "are named. Synthetic columns from Panjabi's tables.",
    "neighbour_formula":
        "Is there a scalar formula? A, the first linear discriminant of the neighbour features, "
        "its class mean and one within-class SD by true level, both neighbours visible: monotone, "
        "but flat across the thoracic bodies. B, exact naming against the number of discriminant "
        "directions kept, typical columns. C, the share of the between-class separation each "
        "direction carries.",
    "neighbour_offsets":
        "The signed offset of the name, by phenotype: both neighbours visible, seven measures, "
        "solution C, scored against the count from C2. Filled bars, the count's truth. The text "
        "gives the exact rate against the count and, where it differs, against the rib reading. "
        "%d synthetic columns per phenotype.",
    "neighbour_shift":
        "The shift, level by level: the mean signed offset of the call at each true level, by "
        "phenotype, both neighbours visible, seven measures, solution C. Below a thirteenth "
        "rib-bearing body the count moves every name one further than the shape says, and the "
        "model follows the shape. Synthetic columns.",
    "neighbour_normalisation":
        "What the normalisation smuggles in. Exact naming against the number of visible bodies "
        "whose median each measure is divided by, both neighbours visible, seven measures, "
        "solution C; the horizontal lines are the arm normalised by a fixed constant from the "
        "table, which carries no position. Typical columns and the worst phenotype.",
    "neighbour_coverage":
        "Selective naming: exact rate against coverage as the model abstains below a confidence, "
        "both neighbours visible, solution C, three regimes; solid markers, typical columns; open "
        "markers, the worst phenotype. The thresholds were chosen on the selection seed and scored "
        "on another.",
    "neighbour_r":
        "The unidentified correlation r between a patient's offsets in the different measures, "
        "swept: exact naming over all six phenotypes, both neighbours visible, solution C, three "
        "regimes, with 95% column-clustered intervals. At the right, each regime's identified "
        "set over the grid (thick) inside its Imbens-Manski interval (thin).",
    "neighbour_subsets":
        "Every subset of the seven measures, both neighbours visible, solution C: the worst "
        "phenotype's exact rate on the scoring seed against the number of measures. Filled, the "
        "subset chosen on the selection seed; squares, the AP set; triangles, the lateral set; "
        "the circle at seven, the full set.",
}


def cell_of(d: dict, arm: str, regime: str) -> dict:
    for c in d["cells"]:
        if c["arm"] == arm and c["regime"] == regime and c["norm"] == "external":
            return c
    raise KeyError((arm, regime))


def rate_rows(d: dict, solution: str = "C") -> List[dict]:
    rows = []
    for arm in ARM_ORDER:
        for regime in NB.REGIMES:
            s = cell_of(d, arm, regime)["solutions"][solution]
            for ph, r in s["per_phenotype"].items():
                rows.append({"arm": arm, "regime": regime, "solution": solution, "phenotype": ph,
                             "n": r["n"], "n_columns": r["n_columns"], "exact_rate": r["exact_rate"],
                             "within_one_rate": r["within_one_rate"], "se_cluster": r["se_cluster"],
                             "wilson_lo": r["wilson"][0], "wilson_hi": r["wilson"][1],
                             "worst": int(ph == s["worst"]["phenotype"])})
    return rows


def _series(ax, x, y, se, regime, label=None):
    err = Z * np.asarray(se, float) * 100
    ax.errorbar(np.asarray(x, float), 100 * np.asarray(y, float), yerr=err, color=INK, elinewidth=0.7,
                label=label if label is not None else REGIME_NAME[regime], **REGIME_STYLE[regime])


# ---- 1 the arms --------------------------------------------------------------------------------

def fig_arms(d, outdir):
    plt = style()
    rows = rate_rows(d, "C") + rate_rows(d, "B") + rate_rows(d, "A")
    write_csv(outdir, "neighbour_arms", rows, ["arm", "regime", "solution", "phenotype", "n", "n_columns", "exact_rate",
                                               "within_one_rate", "se_cluster", "wilson_lo", "wilson_hi", "worst"])
    fig, axes = plt.subplots(1, 3, figsize=(7.4, 3.0), sharey=True)
    x = np.arange(len(ARM_ORDER))
    for ax, L, title, pick in zip(axes, "ABC", ("Typical, named exactly", "Worst phenotype, exactly", "Worst phenotype, within one"),
                                  (("typical", "exact_rate"), ("worst", "exact_rate"), ("worst", "within_one_rate"))):
        for regime in ("both", "ap", "lateral"):
            ys, ses = [], []
            for arm in ARM_ORDER:
                s = cell_of(d, arm, regime)["solutions"]["C"]
                ph = pick[0] if pick[0] != "worst" else (s["worst"] if pick[1] == "exact_rate" else s["worst_within_one"])["phenotype"]
                r = s["per_phenotype"][ph]
                ys.append(r[pick[1]])
                ses.append(r["se_cluster"])
            _series(ax, x + {"both": 0, "ap": -0.12, "lateral": 0.12}[regime], ys, ses, regime)
        ax.set_xticks(x)
        ax.set_xticklabels([ARM_NAME[a] for a in ARM_ORDER], rotation=35, ha="right", fontsize=7.5)
        ax.set_ylim(0, 103)
        ax.set_xlim(-0.6, len(ARM_ORDER) - 0.4)
        letter(ax, L, title)
    axes[0].set_ylabel("Bodies named, per cent")
    axes[2].legend(loc="lower right")
    n = d["n_columns"]["score_per_phenotype"]
    return save(fig, outdir, "neighbour_arms", CAPTIONS["neighbour_arms"] % n)


# ---- 2 by level ----------------------------------------------------------------------------------

def fig_levels(d, outdir):
    plt = style()
    rows = []
    fig, ax = plt.subplots(figsize=(7.4, 3.0))
    levels = None
    for regime in ("both", "ap", "lateral"):
        by = cell_of(d, "flank", regime)["solutions"]["C"]["by_level_typical"]
        levels = [lv for lv in NB.COUNT_NAMES if lv in by]
        y = [by[lv] for lv in levels]
        rows += [{"regime": regime, "level": lv, "exact_rate": v} for lv, v in zip(levels, y)]
        ax.plot(np.arange(len(levels)), 100 * np.asarray(y), color=INK, label=REGIME_NAME[regime], **REGIME_STYLE[regime])
    write_csv(outdir, "neighbour_levels", rows, ["regime", "level", "exact_rate"])
    ax.set_xticks(np.arange(len(levels)))
    ax.set_xticklabels(levels, fontsize=7.5)
    for cut in (len(P.CERVICAL), len(P.CERVICAL) + len(P.THORACIC)):
        k = levels.index(NB.COUNT_NAMES[cut])
        ax.axvline(k - 0.5, color=INK, linestyle=(0, (1, 2)), linewidth=0.7)
    chance = 100 * d["chance"]["flank"]["uniform_exact"]
    ax.axhline(chance, color=INK, linewidth=0.6, linestyle=(0, (4, 3)))
    ax.annotate("chance, uniform over %d names" % d["chance"]["flank"]["k_names"], xy=(len(levels) - 0.6, chance),
                xytext=(0, 3), textcoords="offset points", ha="right", va="bottom", fontsize=7)
    ax.set_ylim(0, 124)
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.set_ylabel("Named exactly, per cent")
    ax.set_xlabel("True level, by the count from C2")
    ax.legend(loc="upper left")
    return save(fig, outdir, "neighbour_levels", CAPTIONS["neighbour_levels"])


# ---- 3 the formula and the dimensionality ---------------------------------------------------------

def fig_formula(d, outdir):
    plt = style()
    rows, rows_dims, rows_share = [], [], []
    fig = plt.figure(figsize=(7.4, 3.2))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.5, 1.0, 0.8], wspace=0.45)
    ax = fig.add_subplot(gs[0, 0])
    for regime in ("both", "ap", "lateral"):
        chk = cell_of(d, "flank", regime)["formula"]["check"]
        m, s = np.asarray(chk["class_means"]), np.asarray(chk["class_sds"])
        # every index in the same units: the within-class SD
        within = float(np.sqrt(np.mean(s ** 2)))
        x = np.arange(len(m))
        ax.errorbar(x, m / within, yerr=s / within, color=INK, elinewidth=0.5, label=REGIME_NAME[regime],
                    **dict(REGIME_STYLE[regime], markersize=3.2))
        rows += [{"regime": regime, "level": lv, "index_mean": mu, "index_sd": sd, "within_sd": within,
                  "monotone": int(chk["monotone"]), "spearman": chk["spearman"]}
                 for lv, mu, sd in zip(chk["classes"], chk["class_means"], chk["class_sds"])]
    levels = cell_of(d, "flank", "both")["formula"]["check"]["classes"]
    ax.set_xticks(np.arange(len(levels)))
    ax.set_xticklabels(levels, fontsize=6.5, rotation=90)
    ax.set_ylabel("Scalar index, within-class SD units")
    ax.set_xlabel("True level")
    ax.legend(loc="upper left", fontsize=6.5)
    letter(ax, "A", "The first discriminant by level")
    ax = fig.add_subplot(gs[0, 1])
    for regime in ("both", "ap", "lateral"):
        dims = cell_of(d, "flank", regime)["dimensionality"]["exact_by_dims"]
        ks = sorted(int(k) for k in dims)
        y = [dims[str(k)]["typical"] for k in ks]
        w = [dims[str(k)]["worst"] for k in ks]
        rows_dims += [{"regime": regime, "dims": k, "exact_typical": a, "exact_worst": b} for k, a, b in zip(ks, y, w)]
        ax.plot(ks, 100 * np.asarray(y), color=INK, label=REGIME_NAME[regime], **REGIME_STYLE[regime])
    ax.set_xlabel("Discriminant directions kept")
    ax.set_ylabel("Named exactly, per cent")
    ax.set_ylim(0, 103)
    ax.set_xticks([1, 3, 5, 7, 9, 11, 13])
    letter(ax, "B", "Accuracy by dimensions")
    ax = fig.add_subplot(gs[0, 2])
    share = cell_of(d, "flank", "both")["formula"]["share"]
    ax.bar(np.arange(1, len(share) + 1), 100 * np.asarray(share), width=0.6, facecolor="white", edgecolor=INK, linewidth=0.8)
    rows_share = [{"direction": k + 1, "share": s} for k, s in enumerate(share)]
    ax.set_xlabel("Direction")
    ax.set_ylabel("Share of the separation, per cent")
    ax.set_xticks(range(1, len(share) + 1, 2))
    letter(ax, "C", "Both planes")
    write_csv(outdir, "neighbour_formula", rows, ["regime", "level", "index_mean", "index_sd", "within_sd", "monotone", "spearman"])
    write_csv(outdir, "neighbour_formula_dims", rows_dims, ["regime", "dims", "exact_typical", "exact_worst"])
    write_csv(outdir, "neighbour_formula_share", rows_share, ["direction", "share"])
    return save(fig, outdir, "neighbour_formula", CAPTIONS["neighbour_formula"])


# ---- 4 the signed offsets ---------------------------------------------------------------------------

def fig_offsets(d, outdir):
    plt = style()
    per = cell_of(d, "flank", "both")["solutions"]["C"]["per_phenotype"]
    rows = []
    fig, axes = plt.subplots(2, 3, figsize=(7.4, 4.2), sharex=True, sharey=True)
    span = list(range(-3, 4))
    for ax, ph in zip(axes.ravel(), PHENOTYPE_ORDER):
        r = per[ph]
        counts = {int(k): v for k, v in r["offsets"].items()}
        n = r["n"]
        y = [100 * counts.get(o, 0) / n for o in span]
        beyond = 100 * sum(v for o, v in counts.items() if abs(o) > 3) / n
        ax.bar(span, y, width=0.7, facecolor=INK, edgecolor=INK, linewidth=0.6)
        text = "exact %.0f%%" % (100 * r["exact_rate"])
        if r["n_rib"] and abs(r["exact_rib_rate"] - r["exact_rate"]) > 1e-9:
            text += "\nby the ribs %.0f%%" % (100 * r["exact_rib_rate"])
        if beyond > 0:
            text += "\nbeyond 3: %.1f%%" % beyond
        ax.text(0.97, 0.95, text, transform=ax.transAxes, ha="right", va="top", fontsize=7)
        ax.set_title(PHENOTYPE_NAME[ph], fontsize=8.5, loc="left")
        ax.set_xticks(span)
        rows += [{"phenotype": ph, "offset": o, "count": counts.get(o, 0), "n": n, "share": counts.get(o, 0) / n} for o in span]
        rows.append({"phenotype": ph, "offset": "beyond", "count": sum(v for o, v in counts.items() if abs(o) > 3), "n": n, "share": beyond / 100})
    for ax in axes[1]:
        ax.set_xlabel("Signed offset of the name, levels")
    for ax in axes[:, 0]:
        ax.set_ylabel("Bodies, per cent")
    write_csv(outdir, "neighbour_offsets", rows, ["phenotype", "offset", "count", "n", "share"])
    return save(fig, outdir, "neighbour_offsets", CAPTIONS["neighbour_offsets"] % d["n_columns"]["score_per_phenotype"])


def fig_shift(d, outdir):
    plt = style()
    per = cell_of(d, "flank", "both")["solutions"]["C"]["per_phenotype"]
    rows = []
    fig, ax = plt.subplots(figsize=(7.4, 3.0))
    levels = [lv for lv in NB.COUNT_NAMES if any(lv in per[ph]["mean_offset_by_level"] for ph in PHENOTYPE_ORDER)]
    for ph in PHENOTYPE_ORDER:
        by = per[ph]["mean_offset_by_level"]
        xs = [k for k, lv in enumerate(levels) if lv in by]
        ys = [by[levels[k]] for k in xs]
        rows += [{"phenotype": ph, "level": levels[k], "mean_offset": v} for k, v in zip(xs, ys)]
        ax.plot(xs, ys, color=INK, linewidth=0.8, marker=PHENOTYPE_MARKER[ph], markersize=4,
                markerfacecolor=(INK if ph in ("typical", "t13") else "white"), label=PHENOTYPE_NAME[ph])
    ax.axhline(0, color=INK, linewidth=0.5)
    ax.set_xticks(np.arange(len(levels)))
    ax.set_xticklabels(levels, fontsize=7.5)
    ax.set_xlabel("True level, by the count from C2")
    ax.set_ylabel("Mean signed offset, levels")
    ax.legend(loc="lower left", ncol=2)
    write_csv(outdir, "neighbour_shift", rows, ["phenotype", "level", "mean_offset"])
    return save(fig, outdir, "neighbour_shift", CAPTIONS["neighbour_shift"])


# ---- 5 the normalisation -------------------------------------------------------------------------

def fig_normalisation(d, outdir):
    plt = style()
    rows = []
    fig, ax = plt.subplots(figsize=(4.6, 3.0))
    ext = cell_of(d, "flank", "both")["solutions"]["C"]
    xs, yt, st, yw, sw = [], [], [], [], []
    for k, entry in enumerate(d["normalisation"]):
        c = entry["solutions"]["C"]
        xs.append(k)
        yt.append(c["per_phenotype"]["typical"]["exact_rate"])
        st.append(c["per_phenotype"]["typical"]["se_cluster"])
        w = c["worst"]["phenotype"]
        yw.append(c["per_phenotype"][w]["exact_rate"])
        sw.append(c["per_phenotype"][w]["se_cluster"])
        rows.append({"bodies": entry["bodies"], "exact_typical": yt[-1], "se_typical": st[-1],
                     "exact_worst": yw[-1], "se_worst": sw[-1], "worst_phenotype": w})
    ax.errorbar(xs, 100 * np.asarray(yt), yerr=Z * 100 * np.asarray(st), color=INK, linestyle="-", marker="o",
                markerfacecolor=INK, elinewidth=0.7, label="Typical columns")
    ax.errorbar(xs, 100 * np.asarray(yw), yerr=Z * 100 * np.asarray(sw), color=INK, linestyle="--", marker="o",
                markerfacecolor="white", elinewidth=0.7, label="Worst phenotype")
    for y, ls, lab in ((ext["per_phenotype"]["typical"]["exact_rate"], "-", "constant, typical"),
                       (ext["per_phenotype"][ext["worst"]["phenotype"]]["exact_rate"], "--", "constant, worst")):
        ax.axhline(100 * y, color=INK, linestyle=ls, linewidth=0.6)
        ax.annotate(lab, xy=(len(xs) - 0.55, 100 * y), xytext=(0, 2), textcoords="offset points", ha="right", va="bottom", fontsize=6.5)
    rows.append({"bodies": "constant", "exact_typical": ext["per_phenotype"]["typical"]["exact_rate"],
                 "se_typical": ext["per_phenotype"]["typical"]["se_cluster"],
                 "exact_worst": ext["per_phenotype"][ext["worst"]["phenotype"]]["exact_rate"],
                 "se_worst": ext["per_phenotype"][ext["worst"]["phenotype"]]["se_cluster"], "worst_phenotype": ext["worst"]["phenotype"]})
    ax.set_xticks(xs)
    ax.set_xticklabels([str(e["bodies"]) for e in d["normalisation"]])
    ax.set_xlabel("Visible bodies the median is taken over")
    ax.set_ylabel("Named exactly, per cent")
    ax.set_ylim(0, 103)
    ax.legend(loc="lower right")
    write_csv(outdir, "neighbour_normalisation", rows, ["bodies", "exact_typical", "se_typical", "exact_worst", "se_worst", "worst_phenotype"])
    return save(fig, outdir, "neighbour_normalisation", CAPTIONS["neighbour_normalisation"])


# ---- 6 selective naming -----------------------------------------------------------------------------

def fig_coverage(d, outdir):
    plt = style()
    rows = []
    fig, ax = plt.subplots(figsize=(4.6, 3.2))
    for regime in ("both", "ap", "lateral"):
        cell = cell_of(d, "flank", regime)
        sel = cell["selective"]
        worst = cell["solutions"]["C"]["worst"]["phenotype"]
        for ph, face in (("typical", INK), (worst, "white")):
            cv = np.asarray(sel["curve"][ph]["coverage"])
            ac = np.asarray(sel["curve"][ph]["exact_rate"])
            keep = cv > 0.02
            ax.plot(100 * cv[keep], 100 * ac[keep], color=INK, markersize=3, markevery=4,
                    label="%s, %s" % (REGIME_NAME[regime].split(",")[0], "typical" if ph == "typical" else PHENOTYPE_NAME[ph].lower()),
                    **dict(REGIME_STYLE[regime], markerfacecolor=face))
            rows += [{"regime": regime, "phenotype": ph, "threshold": t, "coverage": c, "exact_rate": a}
                     for t, c, a in zip(sel["grid"], sel["curve"][ph]["coverage"], sel["curve"][ph]["exact_rate"])]
    ax.set_xlabel("Coverage: bodies named rather than abstained, per cent")
    ax.set_ylabel("Of those named, named exactly, per cent")
    ax.set_xlim(0, 103)
    ax.set_ylim(0, 103)
    ax.legend(loc="lower left", fontsize=6.3)
    write_csv(outdir, "neighbour_coverage", rows, ["regime", "phenotype", "threshold", "coverage", "exact_rate"])
    return save(fig, outdir, "neighbour_coverage", CAPTIONS["neighbour_coverage"])


# ---- 7 the r sweep ---------------------------------------------------------------------------------

def fig_r(d, outdir):
    plt = style()
    rows = []
    fig, ax = plt.subplots(figsize=(4.8, 3.0))
    for k, regime in enumerate(("both", "ap", "lateral")):
        sw = d["r_sweep"][regime]
        x = [r["r"] for r in sw]
        _series(ax, x, [r["acc"] for r in sw], [r["se"] for r in sw], regime)
        s = d["identified"][regime]
        xb = 1.02 + 0.06 * k
        ax.plot([xb, xb], [100 * s["ci_lo"], 100 * s["ci_hi"]], color=INK, linewidth=0.6)
        ax.plot([xb, xb], [100 * s["lo"], 100 * s["hi"]], color=INK, linewidth=2.2, solid_capstyle="butt")
        rows += [{"regime": regime, "r": r["r"], "exact_all_phenotypes": r["acc"], "se_cluster": r["se"],
                  "exact_worst": r["worst"]["exact_rate"], "worst_phenotype": r["worst"]["phenotype"],
                  "set_lo": s["lo"], "set_hi": s["hi"], "im_lo": s["ci_lo"], "im_hi": s["ci_hi"]} for r in sw]
    ax.set_xlabel("r, the correlation between a patient's offsets across measures")
    ax.set_ylabel("Named exactly, all phenotypes, per cent")
    ax.set_xlim(-0.05, 1.15)
    ax.set_ylim(0, 103)
    ax.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.legend(loc="lower left")
    write_csv(outdir, "neighbour_r", rows, ["regime", "r", "exact_all_phenotypes", "se_cluster", "exact_worst", "worst_phenotype",
                                            "set_lo", "set_hi", "im_lo", "im_hi"])
    return save(fig, outdir, "neighbour_r", CAPTIONS["neighbour_r"])


# ---- 8 the subsets ---------------------------------------------------------------------------------

def fig_subsets(e, outdir):
    plt = style()
    rows = []
    fig, ax = plt.subplots(figsize=(4.8, 3.2))
    allrows = []
    for x in e["ranked_by_selection"]:
        allrows.append(x)
    # every subset is in the shards; the gathered file keeps the top ten and the named sets, so
    # the scatter reads the shard rows the gather was made from
    pts = e.get("all_rows") or []
    winner = tuple(sorted(e["winner"]["measures"]))
    named = {tuple(sorted(v["measures"])): k for k, v in e["named"].items()}
    rng = np.random.default_rng(0)
    for x in pts:
        key = tuple(sorted(x["measures"]))
        jitter = (rng.random() - 0.5) * 0.3
        marker, face = "o", "white"
        if key == winner:
            face = INK
        if named.get(key) == "ap":
            marker = "s"
        elif named.get(key) == "lateral":
            marker = "^"
        ax.plot(x["k"] + jitter, 100 * x["score_worst"]["exact_rate"], marker=marker, markerfacecolor=face,
                color=INK, linestyle="none", markersize=4 if key in named or key == winner else 3)
        rows.append({"measures": " ".join(x["measures"]), "k": x["k"], "select_worst": x["select_worst"]["exact_rate"],
                     "score_worst": x["score_worst"]["exact_rate"], "score_worst_phenotype": x["score_worst"]["phenotype"],
                     "winner": int(key == winner), "named": named.get(key, "")})
    ax.set_xlabel("Measures in the subset")
    ax.set_ylabel("Worst phenotype named exactly, per cent")
    ax.set_xticks(range(1, 8))
    ax.set_ylim(0, 103)
    write_csv(outdir, "neighbour_subsets", rows, ["measures", "k", "select_worst", "score_worst", "score_worst_phenotype", "winner", "named"])
    return save(fig, outdir, "neighbour_subsets", CAPTIONS["neighbour_subsets"])


# ---- the record ------------------------------------------------------------------------------------

# ---- 10 the field ----------------------------------------------------------------------------------

def fig_field(more: dict, outdir: str):
    plt = style()
    rows = []
    fig, ax = plt.subplots(figsize=(4.8, 3.0))
    cells = {(c["regime"], c["half"]): c for c in more["field"]}
    halves = sorted({c["half"] for c in more["field"]})
    for regime in ("both", "ap", "lateral"):
        x, typ, se_t, worst, se_w, pub, worst_ph = [], [], [], [], [], [], []
        for h in halves:
            w = cells[(regime, h)]["arms"]["with_target"]
            g = w["C_field"]
            x.append(w["visible_bodies"])
            typ.append(g["per_phenotype"]["typical"]["exact_rate"])
            se_t.append(g["per_phenotype"]["typical"]["se_cluster"])
            wp = g["worst"]["phenotype"]
            worst.append(g["worst"]["exact_rate"])
            se_w.append(g["per_phenotype"][wp]["se_cluster"])
            worst_ph.append(wp)
            pub.append(w["G_B"]["per_phenotype"]["typical"]["exact_rate"])
            rows.append({"regime": regime, "visible_bodies": w["visible_bodies"], "exact_typical": typ[-1],
                         "se_typical": se_t[-1], "exact_worst": worst[-1], "se_worst": se_w[-1],
                         "worst_phenotype": wp, "exact_published_typical": pub[-1],
                         "within_one_typical": g["per_phenotype"]["typical"]["within_one_rate"],
                         "exact_G_typical": w["G"]["per_phenotype"]["typical"]["exact_rate"],
                         "exact_G_worst": w["G"]["worst"]["exact_rate"]})
        _series(ax, x, typ, se_t, regime)
        st = dict(REGIME_STYLE[regime], markerfacecolor="white", linestyle="none")
        ax.errorbar(np.asarray(x, float), 100 * np.asarray(worst), yerr=Z * 100 * np.asarray(se_w), color=INK,
                    elinewidth=0.7, label="_nolegend_", **st)
        if regime == "both":
            ax.plot(x, 100 * np.asarray(pub), linestyle="none", marker="x", color=INK, markersize=5,
                    label="Published means, nothing fitted")
    ax.set_xlabel("Bodies in the field of view, the target among them")
    ax.set_ylabel("Named exactly, per cent")
    ax.set_xticks([1, 3, 5, 7, 9])
    ax.set_ylim(0, 103)
    ax.legend(loc="lower right")
    write_csv(outdir, "neighbour_field", rows, ["regime", "visible_bodies", "exact_typical", "se_typical", "exact_worst",
                                                "se_worst", "worst_phenotype", "exact_published_typical", "within_one_typical",
                                                "exact_G_typical", "exact_G_worst"])
    return save(fig, outdir, "neighbour_field", CAPTIONS["neighbour_field"] % more["n_columns"]["score_per_phenotype"])


def write_record(outdir: str, json_path: str, d: dict, enumerate_json: Optional[str], written: List[str],
                 more_json: Optional[str] = None) -> str:
    import matplotlib
    cmd = "python run.py neighbour-figures --json %s%s%s --outdir %s" % (
        json_path, (" --enumerate-json %s" % enumerate_json) if enumerate_json else "",
        (" --more-json %s" % more_json) if more_json else "", outdir)
    lines = ["# The neighbour-identity figures", "", "Built with `%s`." % cmd, "",
             "- Run: `%s`, sha256 %s; seeds %s; columns %s; synth %s."
             % (json_path, sha256(json_path), json.dumps(d["seeds"], sort_keys=True),
                json.dumps(d["n_columns"], sort_keys=True), json.dumps(d["synth"], sort_keys=True))]
    if enumerate_json:
        lines.append("- Enumeration: `%s`, sha256 %s." % (enumerate_json, sha256(enumerate_json)))
    if more_json:
        lines.append("- The series continued: `%s`, sha256 %s." % (more_json, sha256(more_json)))
    lines.append("- Reference table: `bordercall/reference/panjabi_full_spine.csv`, sha256 %s." % sha256(P.DEFAULT_REFERENCE))
    for name in ("neighbour_figures.py", "neighbour.py", "neighbour_more.py", "junction_figures.py", "panjabi.py", "covariance.py"):
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


def run(json_path: str, outdir: str, enumerate_json: Optional[str] = None, more_json: Optional[str] = None) -> List[str]:
    os.makedirs(outdir, exist_ok=True)
    with open(json_path, encoding="utf-8") as fh:
        d = json.load(fh)
    written = []
    written += fig_arms(d, outdir)
    written += fig_levels(d, outdir)
    written += fig_formula(d, outdir)
    written += fig_offsets(d, outdir)
    written += fig_shift(d, outdir)
    written += fig_normalisation(d, outdir)
    written += fig_coverage(d, outdir)
    written += fig_r(d, outdir)
    if enumerate_json:
        with open(enumerate_json, encoding="utf-8") as fh:
            e = json.load(fh)
        written += fig_subsets(e, outdir)
    if more_json:
        with open(more_json, encoding="utf-8") as fh:
            more = json.load(fh)
        written += fig_field(more, outdir)
    written.append(write_record(outdir, json_path, d, enumerate_json, written, more_json=more_json))
    for p in written:
        print("%7.0f KB  %s" % (os.path.getsize(p) / 1024, p))
    return written
