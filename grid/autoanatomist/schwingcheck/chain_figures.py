"""The chain study's figures, from its three records alone (chain_study.py writes them).

    python -m schwingcheck.chain_figures [--outdir records/chain-2026-10-28/figures]

Drawn in the package's house format for line graphs (figures.py): lettered panels, black ink,
serif type, an axis on two sides, no grid, no colour, each rule told apart by its line and marker.
Each figure is written as PDF with no date inside, PNG at 300 dpi, the CSV of every number drawn
and its caption, under sixty words, and FIGURES.md names the records and the code by sha256.
Every number is about synthetic columns drawn from Panjabi's tables, never a patient.

  chain_accuracy  the share named exactly against the bodies in view, the four rules on the same
                  fields, each column type, all 32 measures and the seven
  chain_answers   the answers at 0.99 against the bodies in view, all 32 measures: how many are
                  named, and how many of those are right, where enough were named to say
  chain_data      the chain's table re-estimated from 12 to 2,000 people at five bodies, nominal
                  and predictive, each type, against the table as printed on the same fields
  chain_speed     the time to name one field against the bodies in view, each rule built
                  beforehand, alone and in a batch, beside chain.path_logev
"""
from __future__ import annotations

import argparse
import os
import platform
from typing import Dict, List, Sequence

import numpy as np

from . import chain as CH
from . import chain_study as CS
from .figures import INK, SERIF, letter, save, sha256, style, write_csv

OUTDIR = os.path.join(CS.RECORD_DIR, "figures")
TYPE_NAME = {"typical": "Typical", "six_lumbar": "Six lumbar", "t13": "With a T13"}
SUBSET_NAME = {"all": "all 32", "seven": "the seven"}
RULE_STYLE = {"consecutive": dict(linestyle=":", marker="^", markerfacecolor="white"),
              "gaps": dict(linestyle="--", marker="s", markerfacecolor="white"),
              "chain": dict(linestyle="-", marker="o", markerfacecolor=INK),
              "known gaps": dict(linestyle="-.", marker="D", markerfacecolor="white", markersize=3.4)}
REFERENCE_STYLE = dict(linestyle="-", linewidth=0.6, marker="x", markersize=4.0)
DATA_BODIES = 5                      # the width the data axis is drawn at, as the README's table gives it
DATA_STYLE = {("seven", "nominal"): dict(linestyle="--", marker="s", markerfacecolor="white"),
              ("seven", "predictive"): dict(linestyle=":", marker="^", markerfacecolor="white"),
              ("all", "nominal"): dict(linestyle="-", marker="o", markerfacecolor=INK),
              ("all", "predictive"): dict(linestyle="-.", marker="D", markerfacecolor=INK, markersize=3)}
PRINTED_STYLE = {"seven": dict(linestyle=(0, (6, 2)), linewidth=0.6), "all": dict(linestyle="-", linewidth=0.6)}
ANSWERS_DRAWN = 50                   # the fields named at 0.99 that a share right must rest on to be drawn
CAPTIONS = {
    "chain_accuracy":
        "Naming the middle body of a field on synthetic columns of three types, %s fields a point: per "
        "cent named exactly against the bodies in view, A to C with all 32 measures, D to F with the "
        "seven SPINEPS measures. Lines, the four rules on the same fields; each step misses a body "
        "with probability %.3g.",
    "chain_answers":
        "The answers at posterior 0.99, all 32 measures, synthetic columns of three types, %s fields a "
        "point: A to C, per cent of fields named at 0.99; D to F, per cent of those right, drawn where "
        "%d or more were named, dotted at 99 per cent. Lines, the four rules on the same fields.",
    "chain_data":
        "The chain's table re-estimated from P people, %d bodies, synthetic columns: A to C, per cent "
        "named exactly; D to F, per cent right of those named at 0.99, where %d or more were named; the "
        "seven and all 32, nominal or widened for a new person (predictive); thin lines, the table as "
        "printed on the same fields.",
    "chain_speed":
        "Time to name the middle body of one synthetic typical field, single-threaded, each rule built "
        "beforehand: A, all 32 measures; B, the seven, %s. Alone (lines, median of %d "
        "calls) and per field in a batch of %d (points, median of %d calls); crosses, chain.path_logev, "
        "which builds its blocks in every call.",
}


def miss_probability(main: dict) -> float:
    """The chance that a step misses a body under the record's step law, before the fit to the column."""
    return float(CH.step_law(main["skip"], main["max_step"])[1:].sum())


def rows_by(record: dict, *keys: str) -> Dict[tuple, dict]:
    return {tuple(r[k] for k in keys): r for r in record["rows"]}


def percent(x: float) -> float:
    return 100.0 * x if x is not None and np.isfinite(x) else float("nan")


def type_axes(plt, n_rows: int, height: float):
    fig, axes = plt.subplots(n_rows, len(CH.TYPES), figsize=(7.2, height), layout="constrained", squeeze=False)
    return fig, axes


def bodies_axis(ax, widths: Sequence[int]):
    ax.set_xticks(list(widths))
    ax.set_xlim(min(widths) - 0.6, max(widths) + 0.6)
    ax.set_xlabel("Bodies in view")


def fig_accuracy(main: dict, outdir: str) -> List[str]:
    plt = style()
    key = rows_by(main, "type", "bodies", "subset", "arm")
    widths = main["widths"]
    fig, axes = type_axes(plt, 2, 4.6)
    rows = []
    for i, sub in enumerate(("all", "seven")):
        for j, kind in enumerate(CH.TYPES):
            ax = axes[i, j]
            for arm in CS.ARMS:
                ys = [percent(key[kind, B, sub, arm]["exact"]) for B in widths]
                ax.plot(widths, ys, color=INK, label=arm, **RULE_STYLE[arm])
                rows += [{"panel": "ABCDEF"[3 * i + j], "type": kind, "measures": sub, "rule": arm, "bodies": B,
                          "percent": y, "fields": key[kind, B, sub, arm]["n_fields"]} for B, y in zip(widths, ys)]
            bodies_axis(ax, widths)
            letter(ax, "ABCDEF"[3 * i + j], "%s, %s" % (TYPE_NAME[kind], SUBSET_NAME[sub]))
        axes[i, 0].set_ylabel("Per cent named exactly")
    fig.legend(*axes[0, 0].get_legend_handles_labels(), loc="outside right center")
    name = "chain_accuracy"
    caption = CAPTIONS[name] % ("{:,}".format(fields_a_point(main)), miss_probability(main))
    return save(fig, outdir, name, caption) + [write_csv(outdir, name, rows)]


def fields_a_point(record: dict) -> int:
    """The fields every point rests on, read off the record; the figures say it only where it is one."""
    counts = {r["n_fields"] for r in record["rows"]}
    if len(counts) != 1:
        raise ValueError("the record's cells rest on different numbers of fields: %s" % sorted(counts))
    return counts.pop()


def fig_answers(main: dict, outdir: str) -> List[str]:
    plt = style()
    key = rows_by(main, "type", "bodies", "subset", "arm")
    widths = main["widths"]
    fig, axes = type_axes(plt, 2, 4.6)
    rows = []
    for j, kind in enumerate(CH.TYPES):
        top, bottom = axes[0, j], axes[1, j]
        for arm in CS.ARMS:
            cells = [key[kind, B, "all", arm] for B in widths]
            named = [percent(c["answered"]) for c in cells]
            right = [percent(c["precision"]) if c["n_answered"] >= ANSWERS_DRAWN else float("nan") for c in cells]
            top.plot(widths, named, color=INK, label=arm, **RULE_STYLE[arm])
            bottom.plot(widths, right, color=INK, label=arm, **RULE_STYLE[arm])
            for B, c, n, r in zip(widths, cells, named, right):
                rows.append({"panel": "ABC"[j], "type": kind, "rule": arm, "bodies": B, "stat": "named at 0.99",
                             "percent": n, "fields": c["n_fields"], "drawn": "yes"})
                rows.append({"panel": "DEF"[j], "type": kind, "rule": arm, "bodies": B, "stat": "right of those",
                             "percent": percent(c["precision"]), "fields": c["n_answered"],
                             "drawn": "yes" if np.isfinite(r) else "no"})
        bottom.axhline(99.0, color=INK, linewidth=0.5, linestyle=":")
        for ax in (top, bottom):
            bodies_axis(ax, widths)
        letter(top, "ABC"[j], "%s, named at 0.99" % TYPE_NAME[kind])
        letter(bottom, "DEF"[j], "%s, right of those" % TYPE_NAME[kind])
    axes[0, 0].set_ylabel("Per cent of fields")
    axes[1, 0].set_ylabel("Per cent right")
    fig.legend(*axes[0, 0].get_legend_handles_labels(), loc="outside right center")
    name = "chain_answers"
    caption = CAPTIONS[name] % ("{:,}".format(fields_a_point(main)), ANSWERS_DRAWN)
    return save(fig, outdir, name, caption) + [write_csv(outdir, name, rows)]


def data_point(cell: dict, stat: str) -> dict:
    """One point of the data figure: the share in per cent, the fields it rests on (those named at
    0.99 for the share right, pooled over the tables, every field otherwise) and whether it is drawn,
    a share right on fewer than ANSWERS_DRAWN fields not being drawn, as in fig_answers."""
    fields = cell["n_answered"] if stat == "precision" else cell["n_fields"]
    drawn = stat != "precision" or fields >= ANSWERS_DRAWN
    return {"percent": percent(cell[stat]), "fields": fields, "drawn": "yes" if drawn else "no"}


def fig_data(axis: dict, main: dict, outdir: str, bodies: int = DATA_BODIES) -> List[str]:
    plt = style()
    printed = rows_by(main, "type", "bodies", "subset", "arm")
    key = rows_by(axis, "people", "rule", "type", "bodies", "subset", "arm")
    people = sorted(int(p) for p in axis["worlds"])
    fig, axes = type_axes(plt, 2, 4.6)
    rows = []
    for j, kind in enumerate(CH.TYPES):
        for i, stat in enumerate(("exact", "precision")):
            ax, panel = axes[i, j], "ABCDEF"[3 * i + j]
            for sub in ("seven", "all"):
                point = data_point(printed[kind, bodies, sub, "chain"], stat)
                y = point["percent"] if point["drawn"] == "yes" else float("nan")
                ax.axhline(y, color=INK, label="%s, as printed" % SUBSET_NAME[sub].capitalize(), **PRINTED_STYLE[sub])
                rows.append(dict(panel=panel, type=kind, stat=stat, measures=sub, rule="printed", people="", **point))
            for (sub, rule), st in DATA_STYLE.items():
                points = [data_point(key[p, rule, kind, bodies, sub, "chain"], stat) for p in people]
                ys = [q["percent"] if q["drawn"] == "yes" else float("nan") for q in points]
                ax.plot(people, ys, color=INK, label="%s, %s" % (SUBSET_NAME[sub].capitalize(), rule), **st)
                rows += [dict(panel=panel, type=kind, stat=stat, measures=sub, rule=rule, people=p, **q)
                         for p, q in zip(people, points)]
            ax.set_xscale("log")
            ax.set_xticks(people)
            ax.set_xticklabels(["{:,}".format(p) for p in people])
            ax.minorticks_off()
            ax.set_xlabel("People the table is estimated from")
            if stat == "precision":
                ax.axhline(99.0, color=INK, linewidth=0.5, linestyle=":")
            letter(ax, panel, "%s, %s" % (TYPE_NAME[kind], "named exactly" if stat == "exact" else "right at 0.99"))
    axes[0, 0].set_ylabel("Per cent named exactly")
    axes[1, 0].set_ylabel("Per cent right")
    fig.legend(*axes[0, 0].get_legend_handles_labels(), loc="outside right center")
    name = "chain_data"
    return save(fig, outdir, name, CAPTIONS[name] % (bodies, ANSWERS_DRAWN)) + [write_csv(outdir, name, rows)]


def fig_speed(speed: dict, outdir: str) -> List[str]:
    plt = style()
    from matplotlib.ticker import FuncFormatter
    key = {(r["engine"], r["arm"], r["subset"], r["bodies"]): r for r in speed["rows"]}
    widths = speed["widths"]
    fig, axes = plt.subplots(1, 2, figsize=(6.4, 2.6), layout="constrained")
    rows = []
    for ax, sub, panel in zip(axes, ("all", "seven"), "AB"):
        for arm in CS.CHAIN_ARMS:
            st = RULE_STYLE[arm]
            alone = [key["prepared", arm, sub, B]["median_ms"] for B in widths]
            batch = [key["prepared", arm, sub, B]["batch_ms"] for B in widths]
            ax.plot(widths, alone, color=INK, label=arm, **st)
            ax.plot(widths, batch, color=INK, linestyle="none", marker=st["marker"], markerfacecolor=st["markerfacecolor"])
            rows += [{"panel": panel, "measures": sub, "engine": "prepared", "rule": arm, "bodies": B, "how": how, "ms": v}
                     for how, vs in (("alone", alone), ("in a batch", batch)) for B, v in zip(widths, vs)]
        ref = [key["path_logev", "chain", sub, B]["median_ms"] for B in widths]
        ax.plot(widths, ref, color=INK, label="chain, path_logev", **REFERENCE_STYLE)
        rows += [{"panel": panel, "measures": sub, "engine": "path_logev", "rule": "chain", "bodies": B, "how": "alone",
                  "ms": v} for B, v in zip(widths, ref)]
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: "%g" % v))      # 1, 10, 100, not powers of ten
        bodies_axis(ax, widths)
        letter(ax, panel, SUBSET_NAME[sub].capitalize())
    axes[0].set_ylabel("Milliseconds a field")
    axes[0].legend(loc="upper left")
    name = "chain_speed"
    c = speed["counts"]
    how = "a rule cut to them" if speed.get("cut") else "a mask on the rule for all 32"
    caption = CAPTIONS[name] % (how, c["calls"], c["batch"], c["batches"])
    return save(fig, outdir, name, caption) + [write_csv(outdir, name, rows)]


def write_figures_md(outdir: str, written: List[str]) -> str:
    import matplotlib
    here = os.path.dirname(os.path.abspath(__file__))
    lines = ["# The chain study's figures", "",
             "Built with `python -m schwingcheck.chain_figures --outdir %s`." % os.path.relpath(outdir, CS.ROOT), ""]
    for which in ("main", "axis", "speed"):
        path = CS.RECORDS[which]
        lines.append("- Record: `%s`, sha256 %s." % (os.path.relpath(path, CS.ROOT), sha256(path)))
    for name in ("figures.py", "chain_figures.py", "chain_study.py"):
        lines.append("- Code: `schwingcheck/%s`, sha256 %s." % (name, sha256(os.path.join(here, name))))
    lines += ["- Python %s, numpy %s, matplotlib %s; serif type %s, embedded in the PDF."
              % (platform.python_version(), np.__version__, matplotlib.__version__, SERIF[0]),
              "- The PDFs carry no creation date, so a rebuild with the same versions gives the same files; the CSVs "
              "beside them hold every number drawn.", "",
              "| Figure | Files | Caption |", "|---|---|---|"]
    for name in dict.fromkeys(os.path.basename(p).split(".")[0] for p in written):
        files = sorted(f for f in os.listdir(outdir) if f.split(".")[0] == name)
        with open(os.path.join(outdir, name + ".caption.txt"), encoding="ascii") as fh:
            caption = fh.read().strip().replace("|", "/")
        lines.append("| %s | %s | %s |" % (name, ", ".join("`%s`" % f for f in files), caption))
    path = os.path.join(outdir, "FIGURES.md")
    with open(path, "w", encoding="ascii", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


def draw_figures(main: dict, axis: dict, speed: dict, outdir: str, figures_md: bool = False) -> List[str]:
    """Every figure from the three records; with figures_md, FIGURES.md naming the committed
    records and the code, which only the records in CS.RECORDS can be."""
    os.makedirs(outdir, exist_ok=True)
    written = fig_accuracy(main, outdir) + fig_answers(main, outdir) + fig_data(axis, main, outdir) + \
        fig_speed(speed, outdir)
    if figures_md:
        written.append(write_figures_md(outdir, written))
    return written


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m schwingcheck.chain_figures")
    ap.add_argument("--outdir", default=OUTDIR)
    a = ap.parse_args(argv)
    for p in draw_figures(CS.load("main"), CS.load("axis"), CS.load("speed"), a.outdir, figures_md=True):
        print(os.path.relpath(p, CS.ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
