"""The figures of the exact study, from its recorded JSON and nothing else.

    python run.py exact-figures --json ../records/exact-2026-10-26/exact.json --outdir ../records/exact-2026-10-26/figures

Drawn as junction_figures.py draws: black ink, serif type, an axis on two sides, no grid, no
colour; a series is told apart by its line and marker, in the styles identify_figures.py set for
the widths of the field and neighbour_figures.py for the planes. Every figure is written as PDF
(no date inside), PNG, the CSV of the numbers drawn and its caption, and FIGURES.md records the
run and the code by sha256. Captions stay under sixty words; the argument is in
docs/EXACT_IDENTIFICATION_RESULTS.md. Every number here is about synthetic columns drawn from
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
import identify_figures as IF                                       # noqa: E402
import junction_figures as JF                                       # noqa: E402
import panjabi as P                                                 # noqa: E402

INK = JF.INK
style, letter, save, write_csv, sha256 = JF.style, JF.letter, JF.save, JF.write_csv, JF.sha256
REGIME_STYLE, REGIME_NAME, WIDTH_STYLE = IF.REGIME_STYLE, IF.REGIME_NAME, IF.WIDTH_STYLE
MEASURE_SHORT = IF.MEASURE_SHORT
CUTS = ["%s/%s" % (P.LEVELS[c - 1], P.LEVELS[c]) for c in range(1, len(P.LEVELS))]
RULE_STYLE = {"nominal": dict(linestyle="--", marker="s", markerfacecolor="white"),
              "predictive": dict(linestyle=":", marker="^", markerfacecolor="white"),
              "honest": dict(linestyle="-", marker="o", markerfacecolor=INK)}
RULE_NAME = {"nominal": "Printed table", "predictive": "New spine's spread about twelve (no tuning)",
             "honest": "Twelve spines' means, 2 mm error (tuned on a pilot)"}
# the worlds of the robustness figure, top to bottom: where each lives in the record and its name
WORLDS = [("none", ("misspecified", "none"), "Generator as assumed"),
          ("table_specimens", ("table_specimens",), "Rule's table from twelve spines"),
          ("table_levels", ("table_levels",), "Data from a table redrawn by its errors"),
          ("combined", ("combined_worlds",), "Twelve-spine table, r 0.4, 1.5 mm"),
          ("noise_mm=2", ("misspecified", "noise_mm=2"), "Measurement error 2 mm"),
          ("noise_mm=3", ("misspecified", "noise_mm=3"), "Measurement error 3 mm"),
          ("rho=0.3", ("misspecified", "rho=0.3"), "Within-column correlation 0.3"),
          ("rho=0.7", ("misspecified", "rho=0.7"), "Within-column correlation 0.7"),
          ("scale_sd=0.14", ("misspecified", "scale_sd=0.14"), "Size spread doubled"),
          ("r_between=0.4", ("misspecified", "r_between=0.4"), "Between-measure r 0.4"),
          ("r_between=0.8", ("misspecified", "r_between=0.8"), "Between-measure r 0.8"),
          ("gradient", ("bias", "gradient"), "Size trend, 5 per cent C3 to L5"),
          ("canal_low", ("bias", "canal_low"), "Canals 8 per cent small")]
CHALLENGER_STYLE = {"closed_form": dict(marker="D", markerfacecolor="white", linestyle="-"),
                    "qda_log": dict(marker="v", markerfacecolor="white", linestyle="--"),
                    "qda_raw": dict(marker="^", markerfacecolor="white", linestyle=":"),
                    "network": dict(marker="o", markerfacecolor=INK, linestyle="-.")}
CHALLENGER_NAME = {"closed_form": "Closed form in the log measures", "qda_log": "Quadratic rule fitted, log measures",
                   "qda_raw": "Quadratic rule fitted, raw measures", "network": "Network, one hidden layer"}
HEADLINE = "3"

CAPTIONS = {
    "exact_ceiling":
        "Naming a run of consecutive bodies. A, share named exactly by the generator's Bayes rule, "
        "by plane; crosses, the earlier linear classifier, both planes, first 1,000 columns. B, "
        "share named at posterior 0.99 and 0.999, both planes. C, points by which approximations "
        "and rules fitted on 5,000 columns fall short of it, bars two standard errors. %d "
        "synthetic columns.",
    "exact_calibration":
        "The posterior is the probability of being right. A, error predicted by the posterior "
        "against error counted, by posterior bin, on fresh draws; diagonal, exact agreement; a bin "
        "with no error drawn at 1e-4. B, share named at posterior 0.99 by true centre level, both "
        "planes: a rate given the truth, measured, not guaranteed. %d synthetic columns.",
    "exact_claims":
        "What a field says for certain about its middle body: at each border, the share of fields "
        "whose middle body lies within two levels of it for which the rule says above or below at "
        "probability 0.99, both planes, by the bodies in view. Wrong claims and the precision near "
        "each border are in the CSV. %d synthetic columns.",
    "exact_measures":
        "Which measure makes claims at which border, one body (A) and three (B): of the fields "
        "whose middle body lies within two levels of the border, the share given a claim at "
        "probability 0.99 by that measure alone, the best pair and all seven, as a square of "
        "proportional area. Wrong claims are counted in the CSV.",
    "exact_subsets":
        "How many measures naming needs: the share named exactly by the best subset of each size "
        "of the seven SPINEPS measures, every one of the 127 subsets scored on the same fields, by "
        "the number of bodies in view; the best single measure is named in the CSV. %d synthetic "
        "columns.",
    "exact_interval":
        "The narrowest claim of its kind: the median number of consecutive levels in the shortest "
        "run that holds 99 per cent of the middle body's posterior, by its true level and the "
        "number of bodies in view, both planes. A width of one is the name itself. %d synthetic "
        "columns.",
    "exact_robust":
        "When the generator is not the truth, three bodies, both planes, three rules, thirteen "
        "worlds: precision of the name at 0.99 (A), of border claims within two levels of the "
        "border (B), share named (C). Bars, two standard errors. Dotted, 99 per cent: promised for "
        "A under the generator; for B, a group picked by the truth, a reference.",
    "exact_robust_widths":
        "The rule built on a table re-estimated from twelve spines, forty such tables pooled, by the "
        "bodies in view: precision of the name given at 0.99 (A), of border claims within two levels "
        "of the border (B), and share named (C), for three rules. Bars, two standard errors "
        "clustered by table.",
}


def widths_of(d: dict) -> List[int]:
    return sorted(int(n) for n in d["widths"])


def body_label(n: int) -> str:
    return "%d bod%s" % (n, "y" if n == 1 else "ies")


# ---- 1 the ceiling and the certified share ------------------------------------------------------

def fig_ceiling(d: dict, outdir: str):
    plt = style()
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(7.6, 2.9))
    ns = widths_of(d)
    rows = []
    for regime in ("both", "ap", "lateral"):
        y = [d["widths"][str(n)]["regimes"][regime]["exact"] for n in ns]
        a.plot(ns, 100 * np.asarray(y), color=INK, label=REGIME_NAME[regime], markersize=3.2, **REGIME_STYLE[regime])
    cl = d.get("classifier", {}).get("both", {})
    cx = sorted(int(n) for n in cl)
    if cx:
        a.plot(cx, [100 * cl[str(n)]["exact"] for n in cx], linestyle="none", marker="x", color=INK, markersize=4.5,
               label="Fitted linear classifier")
    for n in ns:
        both = d["widths"][str(n)]["regimes"]["both"]
        rows.append({"bodies": n, "places": d["widths"][str(n)]["places"],
                     **{"exact_%s" % r: d["widths"][str(n)]["regimes"][r]["exact"] for r in ("both", "ap", "lateral")},
                     "se_both": both["se_cluster"], "within_one_both": both["within_one"],
                     "bayes_error_predicted_both": both["bayes_error_predicted"],
                     "formula_both": d.get("formula", {}).get("both", {}).get(str(n), {}).get("exact", ""),
                     "classifier_both": cl.get(str(n), {}).get("exact", ""),
                     **{"answered_%s" % t: both["selective"][t]["answered"] for t in ("0.99", "0.999")},
                     **{"precision_%s" % t: both["selective"][t]["precision"] for t in ("0.99", "0.999")},
                     **{"errors_%s" % t: both["selective"][t]["errors"] for t in ("0.99", "0.999")},
                     **{"n_answered_%s" % t: both["selective"][t]["n_answered"] for t in ("0.99", "0.999")}})
    a.set_xlabel("Consecutive bodies in view")
    a.set_ylabel("Named exactly, per cent")
    a.set_ylim(0, 103)
    a.legend(loc="lower right", fontsize=6.3)
    letter(a, "A")
    for t, st in (("0.99", dict(linestyle="-", marker="o", markerfacecolor=INK)),
                  ("0.999", dict(linestyle="--", marker="s", markerfacecolor="white"))):
        b.plot(ns, [100 * r["answered_%s" % t] for r in rows], color=INK, markersize=3.2,
               label="Posterior at least %s" % t, **st)
    b.set_xlabel("Consecutive bodies in view")
    b.set_ylabel("Fields named, per cent")
    b.set_ylim(0, 103)
    b.legend(loc="lower right", fontsize=6.5)
    letter(b, "B")
    for ax in (a, b):
        ax.set_xticks([n for n in ns if n in (1, 5, 9, 13, 17, 21)] or ns)
    ch = d.get("challengers", {})
    cw = sorted(int(n) for n in ch if n.isdigit()) if "error" not in ch else []
    for j, name in enumerate(("closed_form", "qda_log", "qda_raw", "network")):
        xs = [n + (j - 1.5) * 0.18 for n in cw]
        ys = [100 * ch[str(n)][name]["minus_exact"] for n in cw]
        es = [200 * ch[str(n)][name]["minus_exact_se"] for n in cw]
        if cw:
            c.errorbar(xs, ys, yerr=es, color=INK, markersize=3.2, linewidth=0.6, elinewidth=0.6, capsize=1.5,
                       label=CHALLENGER_NAME[name], **CHALLENGER_STYLE[name])
        for n in cw:
            r = ch[str(n)][name]
            row = next(x for x in rows if x["bodies"] == n)
            row["%s_exact" % name] = r["exact"]
            row["%s_minus_exact" % name] = r["minus_exact"]
            row["%s_minus_exact_se" % name] = r["minus_exact_se"]
            row["%s_log_loss_minus_exact" % name] = r["log_loss_minus_exact"]
    c.axhline(0.0, color=INK, linewidth=0.5, linestyle=":")
    c.set_xlabel("Consecutive bodies in view")
    c.set_ylabel("Points named exactly, minus the exact rule")
    if cw:
        c.set_xticks(cw)
    c.legend(loc="lower left", fontsize=5.6)
    letter(c, "C")
    fig.tight_layout(w_pad=1.2)
    fields = list(dict.fromkeys(k for r in rows for k in r))
    write_csv(outdir, "exact_ceiling", rows, fields)
    return save(fig, outdir, "exact_ceiling", CAPTIONS["exact_ceiling"] % d["n_columns"])


# ---- 2 calibration ---------------------------------------------------------------------------------

def fig_calibration(d: dict, outdir: str):
    plt = style()
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.0, 2.9), gridspec_kw={"width_ratios": [1.0, 1.5]})
    rows = []
    shown = [n for n in (1, 3, 9) if str(n) in d["widths"]]
    lo = 1e-4
    for n in shown:
        cal = d["widths"][str(n)]["regimes"]["both"]["calibration"]
        xs, ys = [], []
        for c in cal:
            if c["n"] == 0:
                continue
            pred, seen = 1.0 - c["mean_posterior"], 1.0 - c["correct"]
            rows.append({"bodies": n, "bin_lo": c["lo"], "bin_hi": c["hi"], "n": c["n"], "mean_posterior": c["mean_posterior"],
                         "correct": c["correct"], "error_predicted": pred, "error_counted": seen})
            xs.append(max(pred, lo))
            ys.append(max(seen, lo))
        a.plot(xs, ys, color=INK, label=body_label(n), markersize=3.2, **WIDTH_STYLE[n])
    a.plot([lo, 1], [lo, 1], color=INK, linewidth=0.5, linestyle=":")
    a.set_xscale("log")
    a.set_yscale("log")
    a.set_xlim(lo * 0.8, 1.0)
    a.set_ylim(lo * 0.8, 1.0)
    a.set_xlabel("Error the posterior predicts")
    a.set_ylabel("Error counted")
    a.legend(loc="upper left", fontsize=6.5)
    letter(a, "A")
    levels = list(P.LEVELS)
    for n in [n for n in (3, 5, 9) if str(n) in d["widths"]]:
        bc = d["widths"][str(n)]["regimes"]["both"].get("by_centre", {})
        xs = [levels.index(lv) for lv in levels if lv in bc]
        ys = [100 * bc[lv]["answered_099"] for lv in levels if lv in bc]
        for lv in levels:
            if lv in bc:
                rows.append({"bodies": n, "centre": lv, "answered_099": bc[lv]["answered_099"],
                             "precision_099": bc[lv]["precision_099"], "exact": bc[lv]["exact"]})
        b.plot(xs, ys, color=INK, label=body_label(n), markersize=3.2, **WIDTH_STYLE[n])
    IF._level_axis(b, levels)
    b.set_ylabel("Named at posterior 0.99, per cent")
    b.set_ylim(0, 103)
    b.legend(loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=3, frameon=False, fontsize=6.5)
    letter(b, "B")
    fig.tight_layout(w_pad=1.5)
    fields = ["bodies", "bin_lo", "bin_hi", "n", "mean_posterior", "correct", "error_predicted", "error_counted",
              "centre", "answered_099", "precision_099", "exact"]
    write_csv(outdir, "exact_calibration", rows, fields)
    return save(fig, outdir, "exact_calibration", CAPTIONS["exact_calibration"] % d["n_columns"])


# ---- 3 the border claims -----------------------------------------------------------------------------

def fig_claims(d: dict, outdir: str):
    plt = style()
    fig, ax = plt.subplots(figsize=(6.2, 2.9))
    cuts = ["%s/%s" % (P.LEVELS[c - 1], P.LEVELS[c]) for c in range(1, len(P.LEVELS))]
    rows = []
    for n in [n for n in (1, 3, 5, 9) if str(n) in d["widths"]]:
        cl = d["widths"][str(n)]["regimes"]["both"].get("claims")
        if not cl:
            continue
        xs, ys = [], []
        for i, cut in enumerate(cuts):
            if cut not in cl["cuts"]:
                continue
            r = cl["cuts"][cut]
            xs.append(i)
            ys.append(100 * r["decided_within_two"])
            rows.append({"bodies": n, "border": cut, "decided_within_two": r["decided_within_two"],
                         "n_decided_within_two": r["n_decided_within_two"], "errors_within_two": r["errors_within_two"],
                         "precision_within_two": r["precision_within_two"], "decided": r["decided"],
                         "n_decided": r["n_decided"], "errors": r["errors"], "precision": r["precision"]})
        ax.plot(xs, ys, color=INK, label=body_label(n), markersize=3.2, **WIDTH_STYLE[n])
    ax.set_xticks(range(len(cuts)))
    ax.set_xticklabels(cuts, fontsize=6.0, rotation=90)
    ax.set_xlim(-0.7, len(cuts) - 0.3)
    ax.set_ylabel("Said above or below at 0.99, per cent")
    ax.set_xlabel("Border, middle body within two levels of it")
    ax.set_ylim(0, 103)
    ax.legend(loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=4, frameon=False, fontsize=6.5)
    fig.tight_layout()
    write_csv(outdir, "exact_claims", rows, ["bodies", "border", "decided_within_two", "n_decided_within_two",
                                             "errors_within_two", "precision_within_two", "decided", "n_decided",
                                             "errors", "precision"])
    return save(fig, outdir, "exact_claims", CAPTIONS["exact_claims"] % d["n_columns"])


# ---- 4 which measure settles which border --------------------------------------------------------------

def measure_rows(d: dict, n: int) -> List[dict]:
    """The single measures, the best pair by exact naming, and all seven, from the subset record."""
    subs = d["widths"][str(n)]["subsets"]
    singles = sorted([s for s in subs if s["k"] == 1], key=lambda s: d["measures"].index(s["measures"][0]))
    pair = max([s for s in subs if s["k"] == 2], key=lambda s: s["exact"])
    full = [s for s in subs if s["k"] == len(d["measures"])][0]
    return singles + [pair, full]


def row_name(s: dict, nm: int) -> str:
    if s["k"] == 1:
        return MEASURE_SHORT[s["measures"][0]]
    if s["k"] == nm:
        return "All seven"
    return "Best pair: " + " + ".join(MEASURE_SHORT[m].lower() for m in s["measures"])


def fig_measures(d: dict, outdir: str):
    plt = style()
    shown = [n for n in (1, 3) if str(n) in d["widths"] and "claims" in d["widths"][str(n)]["subsets"][0]]
    fig, axes = plt.subplots(len(shown), 1, figsize=(6.6, 2.4 * len(shown)))
    axes = np.atleast_1d(axes)
    rows = []
    for ax, n in zip(axes, shown):
        srows = measure_rows(d, n)
        key = "cuts_decided_within_two" if "cuts_decided_within_two" in srows[0]["claims"] else "cuts_decided"
        cuts = [c for c in CUTS if c in srows[0]["claims"][key]]
        M = np.array([[s["claims"][key][c] for c in cuts] for s in srows])
        IF.hinton(ax, M, [row_name(s, len(d["measures"])) for s in srows], cuts)
        ax.set_aspect("auto")
        for s in srows:
            for c in cuts:
                rows.append({"bodies": n, "measures": "+".join(s["measures"]), "border": c,
                             "decided_within_two": s["claims"].get("cuts_decided_within_two", {}).get(c, ""),
                             "errors_within_two": s["claims"].get("cuts_errors_within_two", {}).get(c, ""),
                             "decided": s["claims"]["cuts_decided"][c], "errors": s["claims"]["cuts_errors"][c]})
    for ax, ltr in zip(axes, "AB"):
        letter(ax, ltr)
    fig.tight_layout(h_pad=0.8)
    write_csv(outdir, "exact_measures", rows, ["bodies", "measures", "border", "decided_within_two", "errors_within_two",
                                               "decided", "errors"])
    return save(fig, outdir, "exact_measures", CAPTIONS["exact_measures"])


# ---- 5 how many measures ------------------------------------------------------------------------------

def fig_subsets(d: dict, outdir: str):
    plt = style()
    fig, ax = plt.subplots(figsize=(4.4, 2.9))
    nm = len(d["measures"])
    rows = []
    for n in [n for n in (1, 3, 5, 9) if str(n) in d["widths"]]:
        subs = d["widths"][str(n)]["subsets"]
        best = [max([s for s in subs if s["k"] == k], key=lambda s: s["exact"]) for k in range(1, nm + 1)]
        ax.plot(range(1, nm + 1), [100 * s["exact"] for s in best], color=INK, label=body_label(n), markersize=3.2,
                **WIDTH_STYLE[n])
        for s in best:
            rows.append({"bodies": n, "k": s["k"], "best_measures": "+".join(s["measures"]), "exact": s["exact"],
                         "se_cluster": s["se_cluster"], "answered_099": s["answered_099"], "precision_099": s["precision_099"]})
    ax.set_xlabel("Measures used, best subset of each size")
    ax.set_ylabel("Named exactly, per cent")
    ax.set_xticks(range(1, nm + 1))
    ax.set_ylim(0, 103)
    ax.legend(loc="lower right", fontsize=6.5)
    fig.tight_layout()
    write_csv(outdir, "exact_subsets", rows, ["bodies", "k", "best_measures", "exact", "se_cluster", "answered_099", "precision_099"])
    return save(fig, outdir, "exact_subsets", CAPTIONS["exact_subsets"] % d["n_columns"])


# ---- 6 the narrowest interval ----------------------------------------------------------------------

def fig_interval(d: dict, outdir: str):
    plt = style()
    fig, ax = plt.subplots(figsize=(5.4, 2.9))
    levels = list(P.LEVELS)
    rows = []
    for n in [n for n in (1, 3, 5, 9) if str(n) in d["widths"]]:
        cl = d["widths"][str(n)]["regimes"]["both"].get("claims")
        if not cl:
            continue
        mw = cl["interval"]["median_width_by_level"]
        xs = [levels.index(lv) for lv in levels if lv in mw]
        ax.plot(xs, [mw[lv] for lv in levels if lv in mw], color=INK, label=body_label(n), markersize=3.2, **WIDTH_STYLE[n])
        for lv in levels:
            if lv in mw:
                rows.append({"bodies": n, "level": lv, "median_width": mw[lv], "coverage_all": cl["interval"]["coverage"],
                             "mean_width_all": cl["interval"]["mean_width"]})
    IF._level_axis(ax, levels)
    ax.set_ylabel("Levels in the 99 per cent run")
    ax.set_ylim(0, None)
    ax.axhline(1.0, color=INK, linewidth=0.5, linestyle=":")
    ax.legend(loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=4, frameon=False, fontsize=6.5)
    fig.tight_layout()
    write_csv(outdir, "exact_interval", rows, ["bodies", "level", "median_width", "coverage_all", "mean_width_all"])
    return save(fig, outdir, "exact_interval", CAPTIONS["exact_interval"] % d["n_columns"])


# ---- 7 robustness --------------------------------------------------------------------------------------

def world_cells(rob: dict, path: tuple, rule: str) -> Dict[str, dict]:
    """One world's pooled cells for one rule, keyed by width, or none where the record lacks it."""
    node = rob
    for k in path:
        node = node.get(k, {})
    return node.get(rule, {})


def world_numbers(c: dict) -> dict:
    sel = c["selective"]["0.99"]
    cl = c.get("claims", {})
    nan = float("nan")
    return {"exact": c["exact_mean"], "precision_099": sel["precision"], "precision_099_se": sel["precision_se"],
            "n_answered_099": sel["n_answered"], "errors_099": sel["errors"], "answered_099": sel["answered"],
            "cuts_precision": cl.get("cuts_precision", nan), "cuts_decided": cl.get("cuts_decided", nan),
            "cuts_precision_within_two": cl.get("cuts_precision_within_two", nan),
            "cuts_precision_within_two_se": cl.get("cuts_precision_within_two_se", nan),
            "cuts_errors_within_two": cl.get("cuts_errors_within_two", ""),
            "cuts_n_decided_within_two": cl.get("cuts_n_decided_within_two", ""),
            "cuts_decided_within_two": cl.get("cuts_decided_within_two", nan), "worlds": c["worlds"]}


ROBUST_FIELDS = ["world", "rule", "bodies", "worlds", "exact", "precision_099", "precision_099_se", "n_answered_099",
                 "errors_099", "answered_099", "cuts_precision", "cuts_decided", "cuts_precision_within_two",
                 "cuts_precision_within_two_se", "cuts_errors_within_two", "cuts_n_decided_within_two",
                 "cuts_decided_within_two"]


def robust_rows(rob: dict) -> List[dict]:
    """Every world, rule and width the record holds, the pilot's variants among them."""
    rows = []
    for key, path, _ in WORLDS:
        for rule in RULE_STYLE:
            for n, c in sorted(world_cells(rob, path, rule).items(), key=lambda kv: int(kv[0])):
                rows.append({"world": key, "rule": rule, "bodies": int(n), **world_numbers(c)})
    for variant, cells in rob.get("pilot", {}).items():
        for n, c in sorted(cells.items(), key=lambda kv: int(kv[0])):
            rows.append({"world": "pilot", "rule": variant, "bodies": int(n), **world_numbers(c)})
    return rows


def fig_robust(d: dict, outdir: str):
    rob = d.get("robust")
    if not rob or "error" in rob:
        return []
    plt = style()
    fig, axes = plt.subplots(1, 3, figsize=(7.6, 3.6), sharey=True, gridspec_kw={"width_ratios": [1.0, 1.0, 0.8]})
    worlds = [w for w in WORLDS if world_cells(rob, w[1], "nominal").get(HEADLINE)]
    ys = np.arange(len(worlds))[::-1]
    keys = (("precision_099", "precision_099_se"), ("cuts_precision_within_two", "cuts_precision_within_two_se"),
            ("answered_099", None))
    for j, rule in enumerate(RULE_STYLE):
        nums = [world_numbers(world_cells(rob, w[1], rule)[HEADLINE]) for w in worlds]
        st = {k: v for k, v in RULE_STYLE[rule].items() if k != "linestyle"}
        for ax, (key, se) in zip(axes, keys):
            x = [100 * u[key] for u in nums]
            err = [200 * u[se] if se and np.isfinite(u[se]) else 0.0 for u in nums] if se else None
            ax.errorbar(x, ys + (1 - j) * 0.22, xerr=err, linestyle="none", color=INK, markersize=3.2, elinewidth=0.6,
                        capsize=1.2, label=RULE_NAME[rule], **st)
    axes[0].set_yticks(ys)
    axes[0].set_yticklabels([w[2] for w in worlds], fontsize=6.3)
    axes[0].set_xlabel("Name right at 0.99, per cent")
    axes[1].set_xlabel("Border claims right, near border, per cent")
    axes[2].set_xlabel("Named at 0.99, per cent")
    for ax in axes[:2]:
        ax.axvline(99.0, color=INK, linewidth=0.5, linestyle=":")
    for ax, ltr in zip(axes, "ABC"):
        letter(ax, ltr)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.55, 1.0), ncol=3, frameon=False, fontsize=6.2)
    fig.tight_layout(w_pad=0.8)
    write_csv(outdir, "exact_robust", robust_rows(rob), ROBUST_FIELDS)
    return save(fig, outdir, "exact_robust", CAPTIONS["exact_robust"])


def fig_robust_widths(d: dict, outdir: str):
    rob = d.get("robust")
    if not rob or "error" in rob or not rob.get("table_specimens"):
        return []
    plt = style()
    fig, axes = plt.subplots(1, 3, figsize=(7.4, 2.8))
    rows = []
    for rule in RULE_STYLE:
        cells = rob["table_specimens"][rule]
        ns = sorted(int(n) for n in cells)
        nums = {n: world_numbers(cells[str(n)]) for n in ns}
        for n in ns:
            rows.append({"world": "table_specimens", "rule": rule, "bodies": n, **nums[n]})
        for ax, (key, se) in zip(axes, (("precision_099", "precision_099_se"),
                                        ("cuts_precision_within_two", "cuts_precision_within_two_se"),
                                        ("answered_099", None))):
            xs = [n for n in ns if np.isfinite(nums[n][key])]
            ax.errorbar(xs, [100 * nums[n][key] for n in xs],
                        yerr=[200 * nums[n][se] for n in xs] if se else None, color=INK, markersize=3.2,
                        linewidth=0.8, elinewidth=0.6, capsize=1.5, label=RULE_NAME[rule], **RULE_STYLE[rule])
    axes[0].set_ylabel("Name right at 0.99, per cent")
    axes[1].set_ylabel("Border claims right, near border, per cent")
    axes[2].set_ylabel("Named at 0.99, per cent")
    for ax, ltr in zip(axes, "ABC"):
        ax.set_xlabel("Bodies in view")
        ax.set_xticks(rob["widths"])
        letter(ax, ltr)
    for ax in axes[:2]:
        ax.axhline(99.0, color=INK, linewidth=0.5, linestyle=":")
        ax.set_ylim(top=100.4)                      # a bar past 100 is the normal approximation's, not a rate
    axes[2].set_ylim(0, 103)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3, frameon=False, fontsize=6.2)
    fig.tight_layout(w_pad=1.2)
    write_csv(outdir, "exact_robust_widths", rows, ROBUST_FIELDS)
    return save(fig, outdir, "exact_robust_widths", CAPTIONS["exact_robust_widths"])


# ---- the record ----------------------------------------------------------------------------------------

def write_record(outdir: str, json_path: str, d: dict, written: List[str]) -> str:
    import matplotlib
    cmd = "python run.py exact-figures --json %s --outdir %s" % (json_path, outdir)
    lines = ["# The exact-identification figures", "", "Built with `%s`." % cmd, "",
             "- Run: `%s`, sha256 %s; scoring seed %s; %d columns; synth %s; %d Gauss-Hermite nodes."
             % (json_path, sha256(json_path), d["score_seed"], d["n_columns"], json.dumps(d["synth"], sort_keys=True),
                d["gh_nodes"]),
             "- Reference table: `bordercall/reference/panjabi_full_spine.csv`, sha256 %s." % sha256(P.DEFAULT_REFERENCE)]
    for name in ("exact_figures.py", "exact.py", "identify_figures.py", "neighbour.py", "junction_figures.py",
                 "panjabi.py", "covariance.py"):
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
        files = sorted(f for f in os.listdir(outdir) if f.startswith(name + "."))
        with open(os.path.join(outdir, name + ".caption.txt"), encoding="utf-8") as fh:
            caption = fh.read().strip().replace("|", "/")
        lines.append("| %s | %s | %s |" % (name, ", ".join("`%s`" % f for f in files), caption))
    path = os.path.join(outdir, "FIGURES.md")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


def run(json_path: str, outdir: str) -> List[str]:
    os.makedirs(outdir, exist_ok=True)
    with open(json_path, encoding="utf-8") as fh:
        d = json.load(fh)
    written = []
    for fn in (fig_ceiling, fig_calibration, fig_claims, fig_measures, fig_subsets, fig_interval, fig_robust,
               fig_robust_widths):
        written += fn(d, outdir)
    written.append(write_record(outdir, json_path, d, written))
    for p in written:
        print("wrote %s" % p)
    return written
