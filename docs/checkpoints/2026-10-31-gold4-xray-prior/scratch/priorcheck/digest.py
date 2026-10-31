#!/usr/bin/env python3
"""Print the compact tables of the kron_sim.py results (results-*.json beside this file)."""
import json
import math
import os

HERE = "/tmp/claude-0/-home-claude/3a9f8f67-4b49-5dd0-98ba-d0bd1c4358ce/scratchpad/priorcheck"


def load(part):
    p = os.path.join(HERE, "results-%s.json" % part)
    return json.load(open(p)) if os.path.exists(p) else None


def heldout_table(h):
    print("\n== held-out log likelihood per spine, minus the Kronecker fit's (mean over reps; SE within a rep in brackets)")
    cols = ["oracle_minus_kron", "kw_minus_kron", "unstructured_toI_minus_kron", "unstructured_toKron_minus_kron", "kron_minus_assumed"]
    print("%-24s %-6s" % ("truth", "n") + "".join("%-26s" % c.replace("_minus_kron", "").replace("_minus_", "-") for c in cols))
    for name, x in h.items():
        if name.startswith("_") or not isinstance(x, dict):
            continue
        for tag in ("n693_test158", "n67_test13"):
            if tag not in x:
                continue
            r = x[tag]
            cells = []
            for c in cols:
                if c in r:
                    cells.append("%7.2f [%5.2f] %4.0f%%   " % (r[c]["mean"], r[c + "_se"]["mean"], 100 * r[c + "_share_better"]["mean"]))
                else:
                    cells.append("%-26s" % "-")
            print("%-24s %-6s" % (name, tag.split("_")[0]) + "".join(cells))
    print("   (each cell: mean difference, nats per spine [mean within-rep SE], per cent of test spines scored better)")


def power(h):
    """share of reps in which the alternative beats the Kronecker by more than 2 within-rep SE is not
    stored per rep; report the ratio mean/SE as a z for one rep instead"""
    print("\n== one held-out comparison's z (mean difference / its SE), n693 fit, 158 test spines")
    for name, x in h.items():
        if name.startswith("_") or not isinstance(x, dict) or "n693_test158" not in x:
            continue
        r = x["n693_test158"]
        zs = []
        for c in ("oracle_minus_kron", "kw_minus_kron", "unstructured_toI_minus_kron", "unstructured_toKron_minus_kron"):
            m, se = r[c]["mean"], r[c + "_se"]["mean"]
            zs.append("%s z=%.1f" % (c.replace("_minus_kron", ""), m / se if se else float("nan")))
        print("  %-24s %s" % (name, "  ".join(zs)))


KEYS = [
    ("misfit_same_level_widths", "same-level widths, Pearson minus R_measure"),
    ("misfit_same_level_depths", "same-level depths, Pearson minus R_measure"),
    ("misfit_same_level_wd4_mean", "same-level, mean of the six end-plate pairs, minus implied"),
    ("misfit_disc_widths", "facing widths across the disc, minus implied"),
    ("misfit_disc_depths", "facing depths across the disc, minus implied"),
    ("misfit_lag1_cross_wd4_not_facing", "lag-1 cross-measure (not facing), minus implied"),
    ("misfit_lag5_cross_wd4", "lag-5 cross-measure, minus implied"),
    ("misfit_cerv_lumbar_cross_measure", "cervical x lumbar cross-measure, minus implied"),
    ("misfit_lag1_same", "lag-1 same measure, minus implied"),
    ("T1L5_minus_C3L5_widths", "T1..L5 fit minus C3..L5 fit, widths, same spines"),
    ("T1L5_minus_C3L5_wd_upper", "T1..L5 fit minus C3..L5 fit, upper width-depth"),
]


def grid_table(g):
    print("\n== grid statistics (mean +- SD over simulated data sets) and the n a test needs to tell the truth from")
    print("   a separable truth (null mean from a_sep; n = n_sim (2.8 SD / |difference|)^2, alpha 0.05 two-sided, power 0.8)")
    null = g.get("a_sep")
    for key, label in KEYS:
        print("\n  %s  [%s]" % (label, key))
        for name, x in g.items():
            if name.startswith("_") or key not in x["n693"]:
                continue
            a, b = x["n693"][key], x["n67"][key]
            line = "    %-24s n693 %+.3f +- %.3f   n67 %+.3f +- %.3f" % (name, a["mean"], a["sd"], b["mean"], b["sd"])
            if null and name != "a_sep":
                d = a["mean"] - null["n693"][key]["mean"]
                sd = max(a["sd"], null["n693"][key]["sd"])
                if abs(d) > 1e-9 and sd > 0:
                    need = 693 * (2.8 * sd / abs(d)) ** 2
                    line += "   n needed ~%s" % ("%.0f" % need if need < 1e6 else ">1e6")
            print(line)


def robust_table(g):
    print("\n== Pearson against Spearman (normal scale) and the copula fit, n693")
    for name, x in g.items():
        if name.startswith("_"):
            continue
        r = x["n693"]
        print("  %-24s same-level widths P %.3f S %.3f | lag1 P %.3f S %.3f | R_measure widths Pearson-fit %.3f copula-fit %.3f | lag1 fit %.3f copula %.3f" % (
            name, r["pearson_same_level_widths"]["mean"], r["spearman_same_level_widths"]["mean"],
            r["pearson_lag1_same"]["mean"], r["spearman_lag1_same"]["mean"],
            r["kron_R_measure_widths"]["mean"], r["copula_R_measure_widths"]["mean"],
            r["kron_lag1"]["mean"], r["copula_lag1"]["mean"]))


def regional_table(g):
    print("\n== same-level widths by region (Pearson), and the cervical-only fit, n693 and n67")
    for name, x in g.items():
        if name.startswith("_"):
            continue
        a, b = x["n693"], x["n67"]
        print("  %-24s cervical %.3f +- %.3f  T1..L5 %.3f +- %.3f | cervical fit R_measure widths %.3f +- %.3f || n67: cervical %.3f +- %.3f  T1..L5 %.3f +- %.3f" % (
            name, a["pearson_same_level_widths_cervical"]["mean"], a["pearson_same_level_widths_cervical"]["sd"],
            a["pearson_same_level_widths_T1L5"]["mean"], a["pearson_same_level_widths_T1L5"]["sd"],
            a["cervical_fit_R_measure_widths"]["mean"], a["cervical_fit_R_measure_widths"]["sd"],
            b["pearson_same_level_widths_cervical"]["mean"], b["pearson_same_level_widths_cervical"]["sd"],
            b["pearson_same_level_widths_T1L5"]["mean"], b["pearson_same_level_widths_T1L5"]["sd"]))


def main():
    h = load("heldout")
    g = load("grid")
    if h:
        heldout_table(h)
        power(h)
    if g:
        grid_table(g)
        robust_table(g)
        regional_table(g)


if __name__ == "__main__":
    main()
