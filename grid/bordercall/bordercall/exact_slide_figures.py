"""The figures of the five exact-identification slides, from the recorded run and nothing typed.

    python run.py exact-slide-figures --json ../records/exact-2026-10-26/exact.json \
        --outdir ../records/exact-2026-10-26/slide-figures

writes the NeurIPS set into `--outdir` and the CNS set into `--outdir`/cns (`--venue` builds one).

The owner's ask of 2026-10-26 20:45 UTC: figures and five slides, styled like Benzel but with
inspiration from Kevin Murphy's chapter on Bayes' rule (Probabilistic Machine Learning: An
Introduction, 2022), ready for a Congress of Neurological Surgeons talk or a NeurIPS oral.

Drawn as the textbook figures are (junction_figures.py: black ink, serif type, an axis on two
sides, no grid, the column drawn as an anatomy text draws it), with what the Bayes chapter
adds: the prior beside the posterior it becomes, the posterior and the rule that computes it in
one deep blue, the prior and whatever is set beside the rule for reference in grey. Colour
carries meaning and nothing else; every series is also told apart by its line and marker, so a
figure reads the same printed in black. A run of widths is one hue from light to dark (one,
three and nine bodies). The type is Caladea where it is installed, the face PowerPoint's Cambria
is measured from, so a figure's type matches the slide's.

Each panel is its own file, drawn at the exact size it takes on its venue's slide (inches,
SIZES), so the deck places it with no scaling of its type, and a person editing the deck moves
or swaps one panel without touching the others. The two venues differ in what a panel says as
well as its size: the CNS talk shows results and not methods, so its panels and captions name
no rule, no posterior and no generator, and it has no calibration panel. Every panel is written
as junction_figures.py writes: PDF with no date inside, PNG at 300 dpi, the CSV of the numbers
drawn and a caption under sixty words; FIGURES.md records the run and the code by sha256.

  exact_slide_view        the column C3 to L5, three bodies in view and the rest unseen
  exact_slide_measures    the seven measures on a vertebra, AP and lateral, schematic
  exact_slide_posterior   the prior and the posterior over the middle body's level, one, three
                          and nine bodies, for the scoring column a stated rule picks
  exact_slide_ceiling     share named exactly, and named at posterior 0.99, by bodies in view
  exact_slide_calibration error the posterior predicts against error counted (NeurIPS only)
  exact_slide_claims      the column beside the share of fields that say which side of each
                          border their middle body is on, at 0.99
  exact_slide_robust      the name's precision at 0.99 and the share named, when the rule's
                          table or error model is not the truth, three bodies

The posterior panel is the one panel not read from the record: it scores the record's own
scoring columns again (the same seed, table and settings) for the fields centred on T12, and
refuses to draw unless the share it names exactly at each width equals the record's
`by_centre` rate for T12, so the panel and the record cannot disagree. The column it draws is
the one whose posterior at T12 lies nearest the median at all three widths together (least
summed rank distance from each width's median), a rule stated before looking. Every number is
about synthetic columns drawn from Panjabi's tables, never a patient.
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
import exact as E                                                   # noqa: E402
import exact_figures as EF                                          # noqa: E402
import junction_figures as JF                                       # noqa: E402
import neighbour as NB                                              # noqa: E402
import panjabi as P                                                 # noqa: E402

INK = JF.INK
BLUE = "#1B4F8C"                    # the posterior and the exact rule
GREY = "#595959"                    # the prior and anything set beside the rule; the deck's text grey
FAINT = "#BDBDBD"                   # the outline of a body not in view
WIDTH_BLUE = {1: "#6B95CC", 3: "#4A78B5", 9: BLUE}      # one hue, light to dark
WIDTH_MARK = {1: dict(linestyle=":", marker="^", markerfacecolor="white"),
              3: dict(linestyle="--", marker="s", markerfacecolor="white"),
              9: dict(linestyle="-", marker="o", markerfacecolor=None)}
FACE = ["Caladea"] + JF.SERIF
SHOWN = (1, 3, 9)
CENTRE = "T12"                      # the level the posterior panel's fields are centred on
VIEW = 3                            # bodies in view in the column drawing
TICKED = ("C3", "C7", "T4", "T8", "T12", "L5")          # the levels named under the posterior rows
VENUES = ("neurips", "cns")
CNS_SCALE = 11.10 / 12.13           # the CNS template's content box against the plain deck's

NEURIPS_SIZES = {"exact_slide_view": (2.3, 5.3), "exact_slide_measures": (3.8, 5.1),
                 "exact_slide_posterior": (6.3, 5.25), "exact_slide_ceiling": (5.6, 4.15),
                 "exact_slide_calibration": (3.65, 3.6), "exact_slide_claims": (5.45, 5.3),
                 "exact_slide_robust": (7.4, 4.0)}
SIZES = {"neurips": NEURIPS_SIZES,
         "cns": {k: (round(w * CNS_SCALE, 2), round(h * CNS_SCALE, 2)) for k, (w, h) in NEURIPS_SIZES.items()
                 if k != "exact_slide_calibration"}}
SIZES["cns"]["exact_slide_ceiling"] = (6.9, 4.7)        # the CNS slide 3 drops the calibration panel

# What a CNS panel says in place of a method word.
SURE = {"neurips": "posterior 0.99", "cns": "99% confidence"}


def world_names(d: dict, venue: str) -> List[tuple]:
    """The robustness worlds drawn, by record key, with each venue's label; the combined world's
    settings are read from the record."""
    com = d["robust"]["combined"]
    combined = ("Twelve-spine table, measures\ncorrelated %g, %g mm error" % (com["r_between"], com["noise_mm"])
                if venue == "neurips" else "Twelve-spine table\nand more error")
    return [("none", "Generator as assumed" if venue == "neurips" else "Anatomy as the tables say"),
            ("table_specimens", "Table from twelve spines"), ("table_levels", "Data from a redrawn table"),
            ("combined", combined), ("noise_mm=2", "Measurement error 2 mm"), ("noise_mm=3", "Measurement error 3 mm")]


def robust_rules(d: dict, venue: str) -> Dict[str, tuple]:
    """The rule in its blue with filled circles, as on the other slides; the corrected rule in ink,
    open diamonds."""
    h = d["robust"]["rules"]["honest"]
    corrected = "Spreads widened, %g mm error" % h["noise_mm"] if venue == "neurips" else "Corrected rule"
    return {"nominal": ("Printed table", dict(marker="o"), BLUE),
            "honest": (corrected, dict(marker="D", markerfacecolor="white"), INK)}


def captions(d: dict, venue: str) -> Dict[str, str]:
    n_col = "{:,}".format(d["n_columns"])
    rob, h, com = d["robust"], d["robust"]["rules"]["honest"], d["robust"]["combined"]
    common = {
        "exact_slide_view":
            "A field of view: three consecutive vertebral bodies seen, the rest of the column unseen, "
            "and no C2 or sacrum to count from. Bodies drawn to Panjabi's mean upper end-plate width, "
            "C3 to L5, the tables' range.",
        "exact_slide_measures":
            "The seven measures each body gives, schematic and not to scale: the AP plane shows the "
            "upper and lower end-plate widths and the canal width, the lateral plane the two end-plate "
            "depths, the canal depth and the posterior body height, which both planes show.",
    }
    if venue == "cns":
        return dict(common, **{
            "exact_slide_posterior":
                "Probability of each level for the middle body, every level equally likely before "
                "looking, then from one, three and nine bodies centred on T12, for the synthetic column "
                "nearest the median of %s at all three widths." % n_col,
            "exact_slide_ceiling":
                "Share of fields named exactly (solid) and named at 99%% confidence (dashed), both "
                "planes, by consecutive bodies in view; crosses, a linear classifier fitted on other "
                "synthetic columns, scored on the first 1,000. %s synthetic columns." % n_col,
            "exact_slide_claims":
                "What a field says for certain about its middle body: at each border, the share of fields "
                "whose middle body lies within two levels of it that say which side at 99%% confidence, "
                "by bodies in view, both planes. %s synthetic columns." % n_col,
            "exact_slide_robust":
                "When the anatomy table or the measurement error is wrong, three bodies, both planes: how "
                "often a name given at 99% confidence is right (A) and the share named (B), printed table "
                "and a corrected rule, on separate synthetic columns. Bars, two standard errors; dotted, 99 "
                "per cent.",
        })
    return dict(common, **{
        "exact_slide_posterior":
            "Bayes' rule over every place. Top, the prior over the middle body's level for one body (for "
            "n bodies, uniform over the 23 - n places); below, its posterior from one, three and nine "
            "bodies centred on T12, for the scoring column nearest the median of %s at all three widths. "
            "Uniform prior, so the posterior is the normalised likelihood." % n_col,
        "exact_slide_ceiling":
            "Share of fields named exactly by the exact rule (solid) and named at posterior 0.99 "
            "(dashed), both planes, by consecutive bodies in view; crosses, a linear classifier fitted "
            "on other synthetic columns, scored on the first 1,000. %s synthetic columns." % n_col,
        "exact_slide_calibration":
            "The posterior is the chance of being right: error the posterior predicts against error "
            "counted, by posterior bin, one, three and nine bodies, both planes; dotted, exact "
            "agreement; a bin with no error counted sits on the floor. %s synthetic columns." % n_col,
        "exact_slide_claims":
            "What a field says for certain about its middle body: at each border, the share of fields "
            "whose middle body lies within two levels of it that say which side at probability 0.99, "
            "by bodies in view, both planes. %s synthetic columns." % n_col,
        "exact_slide_robust":
            "Three bodies, when the table or error model is wrong: precision at posterior 0.99 (A) and "
            "share named (B), printed table and spreads widened by the root of "
            "1 + 1/%d with %g mm error (chosen on a pilot); combined, measures correlated %g. Separate "
            "columns: %d per error world, %d x %d per table world. Bars, two SE."
            % (h["table_n"], h["noise_mm"], com["r_between"], rob["misspecified_columns"],
               rob["worlds"], rob["columns_per_world"]),
    })


def style(venue: str = "neurips"):
    """junction_figures' ink style at slide size: larger type, the slide's serif, Computer Modern
    for mathematics as the equations on the slides are set. The CNS hall is larger, so its type is
    a step larger again."""
    plt = JF.style()
    big = venue == "cns"
    plt.rcParams.update({
        "font.serif": FACE, "font.size": 14 if big else 13, "axes.labelsize": 14 if big else 13,
        "axes.titlesize": 13, "xtick.labelsize": 13 if big else 12, "ytick.labelsize": 13 if big else 12,
        "legend.fontsize": 12.5 if big else 11.5, "mathtext.fontset": "cm",
        "axes.linewidth": 0.9, "xtick.major.width": 0.9, "ytick.major.width": 0.9, "xtick.major.size": 4,
        "ytick.major.size": 4, "lines.linewidth": 1.6, "lines.markersize": 6, "lines.markeredgewidth": 1.1,
        "errorbar.capsize": 3})
    return plt


def figure(name: str, venue: str):
    plt = style(venue)
    return plt, plt.figure(figsize=SIZES[venue][name])


def save(fig, outdir: str, name: str, caption: str, venue: str) -> List[str]:
    """At the exact size the slide gives the panel: no tight bounding box, which would change it."""
    w, h = SIZES[venue][name]
    fig.set_size_inches(w, h)
    paths = []
    for ext in ("pdf", "png"):
        p = os.path.join(outdir, "%s.%s" % (name, ext))
        kw = dict(metadata={"CreationDate": None, "ModDate": None}) if ext == "pdf" else {}
        fig.savefig(p, facecolor="white", **kw)
        paths.append(p)
    import matplotlib.pyplot as plt
    plt.close(fig)
    p = os.path.join(outdir, name + ".caption.txt")
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(caption.strip() + "\n")
    return paths + [p]


def widths_mark(n: int) -> dict:
    st = dict(WIDTH_MARK[n])
    if st["markerfacecolor"] is None:
        st["markerfacecolor"] = WIDTH_BLUE[n]
    return dict(st, color=WIDTH_BLUE[n], markeredgecolor=WIDTH_BLUE[n])


def body_label(n: int) -> str:
    return EF.body_label(n)


# ---- the column as rows: one body per row, so a border is half a row ----------------------------

def draw_rows(ax, ref, seen=None, labels=True, mark_seen=False, label_size=13.5):
    """The column C3 to L5 as rows, top to bottom, each body a box of its mean upper end-plate width,
    as junction_figures draws the column but one row per body, so that a plot beside it can share
    its rows. A body outside `seen` keeps a faint dashed outline; every label stays legible, since
    the outline alone says a body is out of view."""
    from matplotlib.patches import Rectangle
    levels = list(P.LEVELS)
    widest = max(ref["endplate"][lv][0] for lv in levels)
    for i, lv in enumerate(levels):
        w = ref["endplate"][lv][0]
        inview = seen is None or i in seen
        ax.add_patch(Rectangle((-w / 2, i - 0.36), w, 0.72, facecolor="white", edgecolor=INK if inview else FAINT,
                               linewidth=1.0 if inview else 0.9, linestyle="-" if inview else (0, (3, 2))))
        if labels:
            hidden = mark_seen and inview
            ax.text(-widest / 2 - 3, i, "?" if hidden else lv, ha="right", va="center",
                    fontsize=label_size + 1 if hidden else label_size,
                    color=BLUE if hidden else (INK if inview else GREY), fontweight="bold" if hidden else "normal")
    ax.set_xlim(-widest / 2 - 17, widest / 2 + 4)
    ax.set_ylim(len(levels) - 0.4, -0.6)
    for side in ("left", "bottom", "top", "right"):
        ax.spines[side].set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])
    return widest


def fig_view(d: dict, ref, outdir: str, venue: str) -> List[str]:
    name = "exact_slide_view"
    plt, fig = figure(name, venue)
    ax = fig.add_axes([0.02, 0.03, 0.96, 0.94])
    centre = P.LEVELS.index(CENTRE)
    start = centre - E.target_offset(VIEW)
    seen = set(range(start, start + VIEW))
    widest = draw_rows(ax, ref, seen=seen, mark_seen=True)
    x = widest / 2 + 2.5
    ax.plot([x, x + 1.5, x + 1.5, x], [start - 0.42, start - 0.42, start + VIEW - 0.58, start + VIEW - 0.58],
            color=BLUE, linewidth=1.6, solid_capstyle="butt")
    # The CNS panel is narrower while its type is not, so its column takes a little less of it.
    ax.set_xlim(-widest / 2 - 17, widest / 2 + (35 if venue == "cns" else 30))
    ax.text(x + 3, start + (VIEW - 1) / 2, "in view:\n%d bodies" % VIEW, ha="left", va="center", fontsize=13,
            color=BLUE, linespacing=1.1)
    ax.text(x + 3, 2.0, "unseen", ha="left", va="center", fontsize=12.5, color=GREY, style="italic")
    ax.text(x + 3, 20.0, "unseen", ha="left", va="center", fontsize=12.5, color=GREY, style="italic")
    rows = [{"level": lv, "row": i, "in_view": int(i in seen), "endplate_mean_mm": ref["endplate"][lv][0]}
            for i, lv in enumerate(P.LEVELS)]
    JF.write_csv(outdir, name, rows, ["level", "row", "in_view", "endplate_mean_mm"])
    return save(fig, outdir, name, captions(d, venue)[name], venue)


# ---- the seven measures --------------------------------------------------------------------------

def dimension(ax, p0, p1, text, offset=(0, 0), ha="center", va="center", rotation=0, size=11.5):
    ax.annotate("", xy=p1, xytext=p0, arrowprops=dict(arrowstyle="<|-|>", color=BLUE, linewidth=1.1,
                                                      shrinkA=0, shrinkB=0, mutation_scale=7))
    mx, my = (p0[0] + p1[0]) / 2 + offset[0], (p0[1] + p1[1]) / 2 + offset[1]
    ax.text(mx, my, text, ha=ha, va=va, fontsize=size, color=INK, rotation=rotation)


def extension(ax, x0, y0, x1, y1):
    ax.plot([x0, x1], [y0, y1], color=GREY, linewidth=0.6)


def draw_ap(ax):
    """A lumbar-shaped body seen front to back: the end plates, the pedicles' rings and the canal
    width between their inner borders, the spinous process between them, the transverse processes."""
    from matplotlib.patches import Ellipse, Polygon
    body = [(-24, 0), (-21.5, 13.5), (-23, 27), (23, 27), (21.5, 13.5), (24, 0)]
    ax.add_patch(Polygon(body, closed=True, facecolor="white", edgecolor=INK, linewidth=1.1))
    for s in (-1, 1):
        ax.add_patch(Ellipse((s * 15.5, 20), 8, 10.5, facecolor="none", edgecolor=INK, linewidth=0.9))
        ax.add_patch(Polygon([(s * 23, 17), (s * 36, 18), (s * 36, 22.5), (s * 23, 23.5)], closed=True,
                             facecolor="white", edgecolor=INK, linewidth=0.9, zorder=0))
    ax.add_patch(Ellipse((0, 11), 5.5, 9, facecolor="none", edgecolor=INK, linewidth=0.9))
    extension(ax, -23, 27.5, -23, 33)
    extension(ax, 23, 27.5, 23, 33)
    dimension(ax, (-23, 31.5), (23, 31.5), "upper end-plate width", offset=(0, 2.6))
    extension(ax, -24, -0.5, -24, -6)
    extension(ax, 24, -0.5, 24, -6)
    dimension(ax, (-24, -4.5), (24, -4.5), "lower end-plate width", offset=(0, -2.8))
    dimension(ax, (-11.5, 20), (11.5, 20), "canal width", offset=(0, 3.3), size=11)
    ax.text(0, 42, "AP", ha="center", va="bottom", fontsize=13.5, fontweight="bold")
    ax.set_xlim(-40, 40)
    ax.set_ylim(-11, 47)


def draw_lateral(ax):
    """The same body from the side, front to the left: the two end-plate depths, the posterior body
    height along the back wall, and the canal depth from the back wall to the lamina."""
    from matplotlib.patches import Polygon
    body = [(-16.5, 0), (-15, 13), (-16.5, 26), (16.5, 27), (16.5, 0)]
    ax.add_patch(Polygon(body, closed=True, facecolor="white", edgecolor=INK, linewidth=1.1))
    pedicle = [(16.5, 23.5), (30, 23), (30, 15.5), (16.5, 15)]
    ax.add_patch(Polygon(pedicle, closed=True, facecolor="white", edgecolor=INK, linewidth=0.9))
    lamina = [(30, 28), (35.5, 27), (36.5, 4), (31, 5)]
    ax.add_patch(Polygon(lamina, closed=True, facecolor="white", edgecolor=INK, linewidth=0.9))
    ax.add_patch(Polygon([(36.2, 20), (53, 9.5), (51.5, 5.5), (36.4, 11)], closed=True, facecolor="white",
                         edgecolor=INK, linewidth=0.9))
    extension(ax, -16.5, 26.5, -16.5, 33)
    extension(ax, 16.5, 27.5, 16.5, 33)
    dimension(ax, (-16.5, 31.5), (16.5, 31.5), "upper end-plate depth", offset=(0, 2.6))
    extension(ax, -16.5, -0.5, -16.5, -6)
    extension(ax, 16.5, -0.5, 16.5, -6)
    dimension(ax, (-16.5, -4.5), (16.5, -4.5), "lower end-plate depth", offset=(0, -2.8))
    dimension(ax, (12.5, 0.5), (12.5, 26.5), "posterior\nheight", offset=(-8.5, 0), size=11)
    dimension(ax, (16.5, 10.5), (30.7, 10.5), "canal\ndepth", offset=(0, -5.4), size=11)
    ax.text(-11.5, 13.5, "front", ha="left", va="center", fontsize=10.5, color=GREY, style="italic", rotation=90)
    ax.text(0, 42, "Lateral", ha="center", va="bottom", fontsize=13.5, fontweight="bold")
    ax.set_xlim(-28, 55)
    ax.set_ylim(-11, 47)


def fig_measures(d: dict, outdir: str, venue: str) -> List[str]:
    name = "exact_slide_measures"
    plt, fig = figure(name, venue)
    for k, draw in enumerate((draw_ap, draw_lateral)):
        ax = fig.add_axes([0.02, 0.52 - 0.5 * k, 0.96, 0.46])
        draw(ax)
        ax.set_aspect("equal")
        ax.axis("off")
    rows = []
    for m in E.MEASURES7:
        planes = [p for p in ("ap", "lateral") if m in NB.REGIMES[p]]
        rows.append({"measure": m, "name": NB.MEASURE_NAME[m], "planes": "+".join(planes)})
    JF.write_csv(outdir, name, rows, ["measure", "name", "planes"])
    return save(fig, outdir, name, captions(d, venue)[name], venue)


# ---- prior to posterior ----------------------------------------------------------------------------

def centred_posteriors(d: dict) -> Dict[int, np.ndarray]:
    """The exact rule's posterior over the middle body's level, (columns, 22), for the record's
    scoring columns' fields centred on CENTRE, at each width shown; refuses a record scored with other
    settings, or any mismatch with its own rates for these fields (named, answered and right at 0.99)."""
    measures = list(d["measures"])
    synth = {k: d["synth"][k] for k in ("rho", "noise_mm", "scale_sd")}
    if (any(abs(NB.SYNTH[k] - synth[k]) > 1e-12 for k in synth) or int(d["score_seed"]) != int(E.SCORE_SEED)
            or int(d["gh_nodes"]) != int(E.GH_NODES) or measures != list(E.MEASURES7)):
        raise ValueError("the record was scored with other settings than the generator's defaults")
    ref = P.load_reference(measures=measures)
    cols = NB.draw_columns(ref, ["typical"], int(d["score_seed"]), int(d["n_columns"]), measures)
    V = E.column_values(cols, measures)
    mu, sd = E.table_arrays(ref, measures)
    centre = P.LEVELS.index(CENTRE)
    out = {}
    for n in SHOWN:
        start = centre - E.target_offset(n)
        X = V[:, :, start:start + n]
        post = np.concatenate([E.chunked_posterior(X[i:i + 200], mu, sd, synth, n) for i in range(0, len(X), 200)])
        hit, sure = post.argmax(1) == start, post.max(1) >= 0.99
        here = {"exact": float(hit.mean()), "answered_099": float(sure.mean()),
                "precision_099": float(hit[sure].mean()) if sure.any() else float("nan")}
        recorded = d["widths"][str(n)]["regimes"]["both"]["by_centre"][CENTRE]
        for key, value in here.items():
            same = (np.isnan(value) and np.isnan(recorded[key])) or abs(value - recorded[key]) <= 1e-12
            if not same:
                raise ValueError("%d bodies: %s %.6f here, %.6f in the record" % (n, key, value, recorded[key]))
        out[n] = E.target_posterior(post, n)
    return out


def median_column(tps: Dict[int, np.ndarray]) -> int:
    """The column whose posterior at CENTRE lies nearest the median at every width shown together:
    the least sum, over the widths, of its rank's distance from the median rank. A rule stated
    before looking, so that no width's row is an outlier picked to make a point."""
    k = P.LEVELS.index(CENTRE)
    total = 0.0
    for n in SHOWN:
        p = tps[n][:, k]
        rank = np.argsort(np.argsort(p, kind="stable"), kind="stable")
        total = total + np.abs(rank - (len(p) - 1) / 2.0)
    return int(np.argmin(total))


def fig_posterior(d: dict, outdir: str, tps: Dict[int, np.ndarray], venue: str) -> List[str]:
    name = "exact_slide_posterior"
    plt, fig = figure(name, venue)
    cns = venue == "cns"
    levels = list(P.LEVELS)
    centre = levels.index(CENTRE)
    col = median_column(tps)
    xs = np.arange(len(levels))
    rows_spec = [("prior", None)] + [("posterior", n) for n in SHOWN]
    gs = fig.add_gridspec(len(rows_spec), 1, left=0.14, right=0.70, top=0.94, bottom=0.10, hspace=0.42)
    rows = []
    for r, (kind, n) in enumerate(rows_spec):
        ax = fig.add_subplot(gs[r, 0])
        if kind == "prior":
            p = np.full(len(levels), 1.0 / len(levels))
            ax.bar(xs, p, width=0.72, color=GREY, edgecolor=GREY, linewidth=0.6)
            label = "before looking" if cns else "prior"
            sub = "every level\nequally likely" if cns else "one body:\n1/%d each" % len(levels)
        else:
            p = tps[n][col]
            ax.bar(xs, p, width=0.72, color=BLUE, edgecolor=BLUE, linewidth=0.6)
            label = body_label(n) if cns else "posterior"
            sub = ("P(%s) = %.3f" % (CENTRE, p[centre]) if cns else
                   "%s\n$p(\\ell=\\mathrm{%s}\\mid x_{1:n})$\n$=%.3f$" % (body_label(n), CENTRE, p[centre]))
        ax.set_ylim(0, 1.0)
        ax.set_yticks([0, 0.5, 1.0])
        ax.set_yticklabels(["0", "0.5", "1"])
        ax.set_xlim(-0.7, len(levels) - 0.3)
        ax.set_xticks(xs)
        last = r == len(rows_spec) - 1
        ax.set_xticklabels([lv if (last and lv in TICKED) else "" for lv in levels], fontsize=13)
        ax.tick_params(axis="x", length=2.5)
        ax.text(1.03, 0.95, label, transform=ax.transAxes, ha="left", va="top", fontsize=13,
                color=GREY if kind == "prior" else BLUE, fontweight="bold")
        ax.text(1.03, 0.60 if cns or kind == "prior" else 0.62, sub, transform=ax.transAxes, ha="left", va="top",
                fontsize=12, linespacing=1.15)
        ax.plot([centre], [1.16], marker="v", color=INK, markersize=6, clip_on=False, zorder=5)
        if r == 0:
            ax.text(centre - 0.8, 1.16, "true level", fontsize=12, ha="right", va="center")
        for k, lv in enumerate(levels):
            rows.append({"row": kind if n is None else "posterior_%d" % n, "column": col, "level": lv,
                         "probability": p[k], "truth": int(k == centre)})
    fig.text(0.035, 0.52, "Probability of the middle body's level", rotation=90, ha="center", va="center",
             fontsize=13)
    for n in SHOWN:
        tp = tps[n]
        rows.append({"row": "all_columns_%d" % n, "column": "", "level": CENTRE,
                     "probability": float(tp[:, centre].mean()), "truth": 1})
    JF.write_csv(outdir, name, rows, ["row", "column", "level", "probability", "truth"])
    return save(fig, outdir, name, captions(d, venue)[name], venue)


# ---- the ceiling and the share named when sure ---------------------------------------------------

def fig_ceiling(d: dict, outdir: str, venue: str) -> List[str]:
    name = "exact_slide_ceiling"
    plt, fig = figure(name, venue)
    ax = fig.add_axes([0.13, 0.15, 0.84, 0.81])
    ns = EF.widths_of(d)
    both = {n: d["widths"][str(n)]["regimes"]["both"] for n in ns}
    exact = [100 * both[n]["exact"] for n in ns]
    sure = [100 * both[n]["selective"]["0.99"]["answered"] for n in ns]
    cl = d["classifier"]["both"]
    cx = sorted(int(n) for n in cl)
    ax.plot(ns, exact, color=BLUE, linestyle="-", marker="o", markersize=4.5, markerfacecolor=BLUE)
    ax.plot(ns, sure, color=BLUE, linestyle="--", marker="o", markersize=4.5, markerfacecolor="white")
    ax.plot(cx, [100 * cl[str(n)]["exact"] for n in cx], linestyle="none", marker="x", color=GREY,
            markersize=7, markeredgewidth=1.6)
    ax.text(5.6, 100 * both[5]["exact"] + 3.5, "named exactly", color=BLUE, fontsize=13, ha="right", va="bottom")
    ax.text(6.6, 100 * both[6]["selective"]["0.99"]["answered"] - 3, "named at\n%s" % SURE[venue], color=BLUE,
            fontsize=13, ha="left", va="top", linespacing=1.1)
    # The crosses sit too close to both curves for a direct label, so they take a one-entry key in the
    # empty lower right.
    ax.plot([13.2], [20], linestyle="none", marker="x", color=GREY, markersize=7, markeredgewidth=1.6)
    ax.text(13.9, 20, "linear classifier", color=GREY, fontsize=12.5, ha="left", va="center")
    # The three-body point's label sits above and left of it, clear of the curve and of the cross at five.
    e3 = 100 * both[3]["exact"]
    ax.annotate("%.0f%%" % e3, xy=(3, e3), xytext=(1.0, e3 + 9), fontsize=13, color=BLUE, ha="left", va="bottom",
                arrowprops=dict(arrowstyle="-", color=BLUE, linewidth=0.7, shrinkA=0, shrinkB=3))
    ax.set_xlabel("Consecutive bodies in view")
    ax.set_ylabel("Fields, per cent")
    ax.set_xlim(0.3, max(ns) + 0.7)
    ax.set_xticks([1, 3, 5, 9, 15, 22])
    ax.set_ylim(0, 102)
    rows = [{"bodies": n, "exact": both[n]["exact"], "se_cluster": both[n]["se_cluster"],
             "answered_099": both[n]["selective"]["0.99"]["answered"],
             "precision_099": both[n]["selective"]["0.99"]["precision"],
             "errors_099": both[n]["selective"]["0.99"]["errors"],
             "n_answered_099": both[n]["selective"]["0.99"]["n_answered"],
             "classifier_exact": cl.get(str(n), {}).get("exact", "")} for n in ns]
    JF.write_csv(outdir, name, rows, ["bodies", "exact", "se_cluster", "answered_099", "precision_099",
                                      "errors_099", "n_answered_099", "classifier_exact"])
    return save(fig, outdir, name, captions(d, venue)[name], venue)


# ---- calibration ----------------------------------------------------------------------------------

ODDS = {1e-4: "1 in 10,000", 1e-3: "1 in 1,000", 1e-2: "1 in 100", 1e-1: "1 in 10", 1.0: "1"}


def fig_calibration(d: dict, outdir: str, venue: str) -> List[str]:
    name = "exact_slide_calibration"
    plt, fig = figure(name, venue)
    ax = fig.add_axes([0.335, 0.20, 0.625, 0.75])
    floor, lo = 1e-5, 4e-6
    rows = []
    for n in SHOWN:
        xs, ys, zx = [], [], []
        for c in d["widths"][str(n)]["regimes"]["both"]["calibration"]:
            if c["n"] == 0:
                continue
            pred, seen = 1.0 - c["mean_posterior"], 1.0 - c["correct"]
            rows.append({"bodies": n, "bin_lo": c["lo"], "bin_hi": c["hi"], "n": c["n"],
                         "error_predicted": pred, "error_counted": seen})
            (xs if seen > 0 else zx).append(pred)
            if seen > 0:
                ys.append(seen)
        st = widths_mark(n)
        ax.plot(xs, ys, label=body_label(n), markersize=5.5, **st)
        if zx:
            ax.plot(zx, [floor] * len(zx), linestyle="none", marker=st["marker"], markersize=5.5,
                    markerfacecolor="white", markeredgecolor=st["color"], clip_on=False)
    ax.plot([lo, 1], [lo, 1], color=GREY, linewidth=1.2, linestyle=":")
    ax.text(2.2e-3, 5.5e-4, "predicted = counted", fontsize=11.5, color=GREY, rotation=44, ha="center", va="center",
            rotation_mode="anchor")
    ax.axhline(floor, color=GREY, linewidth=0.5, linestyle="-")
    ax.text(1.1e-3, floor * 1.6, "no error counted", fontsize=11.5, color=GREY, ha="left", va="bottom",
            style="italic")
    # The floor is not on the scale: a break on the axis says so.
    for y in (1.9e-5, 2.6e-5):
        ax.plot([-0.035, 0.035], [y * 0.82, y * 1.22], transform=ax.get_yaxis_transform(), color=INK,
                linewidth=0.9, clip_on=False)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(lo, 1)
    ax.set_ylim(lo, 1)
    ticks = sorted(ODDS)
    ax.set_xticks(ticks)
    ax.set_xticklabels([ODDS[t] if t in (1e-4, 1e-2, 1.0) else "" for t in ticks], fontsize=12)
    ax.set_yticks(ticks)
    ax.set_yticklabels([ODDS[t] for t in ticks], fontsize=12)
    ax.minorticks_off()
    ax.set_xlabel("Error the posterior predicts")
    ax.set_ylabel("Error counted")
    leg = ax.legend(loc="upper left", fontsize=11, handlelength=2.0, borderpad=0.35, labelspacing=0.3,
                    title="the widths overlap", title_fontsize=10.5)
    leg._legend_box.align = "left"
    JF.write_csv(outdir, name, rows, ["bodies", "bin_lo", "bin_hi", "n", "error_predicted", "error_counted"])
    return save(fig, outdir, name, captions(d, venue)[name], venue)


# ---- the border claims beside the column ---------------------------------------------------------

def fig_claims(d: dict, ref, outdir: str, venue: str) -> List[str]:
    name = "exact_slide_claims"
    plt, fig = figure(name, venue)
    gs = fig.add_gridspec(1, 2, width_ratios=[0.95, 1.6], left=0.02, right=0.83, top=0.92, bottom=0.21, wspace=0.04)
    a = fig.add_subplot(gs[0, 0])
    draw_rows(a, ref, label_size=13)
    b = fig.add_subplot(gs[0, 1], sharey=a)
    rows = []
    for n in SHOWN:
        cl = d["widths"][str(n)]["regimes"]["both"]["claims"]["cuts"]
        ys, xs = [], []
        for c in range(1, len(P.LEVELS)):
            cut = E.CUT_NAMES[c - 1]
            if cut not in cl:
                continue
            r = cl[cut]
            ys.append(c - 0.5)
            xs.append(100 * r["decided_within_two"])
            rows.append({"bodies": n, "border": cut, "decided_within_two": r["decided_within_two"],
                         "n_decided_within_two": r["n_decided_within_two"], "n_within_two": r["n_within_two"],
                         "errors_within_two": r["errors_within_two"], "precision_within_two": r["precision_within_two"]})
        b.plot(xs, ys, label=body_label(n), markersize=5, **widths_mark(n))
    for cut in ("C7/T1", "T12/L1"):
        y = E.CUT_NAMES.index(cut) + 0.5
        for ax in (a, b):
            ax.axhline(y, color=INK, linewidth=0.7, linestyle=(0, (1, 2)))
        b.text(103, y, cut, ha="left", va="center", fontsize=12.5, fontweight="bold",
               bbox=dict(facecolor="white", edgecolor="none", pad=1.0))
    b.set_xlim(0, 100)
    b.set_xticks([0, 25, 50, 75, 100])
    b.set_xlabel("Fields near this border that say\nwhich side at %s, %%" % ("0.99" if venue == "neurips" else
                                                                           SURE[venue]), linespacing=1.1)
    b.text(98, 21.6, "one marker per border\nbetween adjacent bodies", fontsize=11.5, color=GREY, style="italic",
           ha="right", va="bottom", linespacing=1.05)
    b.tick_params(axis="y", left=False, labelleft=False)
    b.spines["left"].set_visible(False)
    b.set_ylim(len(P.LEVELS) - 0.4, -0.6)
    b.legend(loc="lower left", bbox_to_anchor=(0.0, 1.0), ncol=3, frameon=False, fontsize=11.5, handlelength=2.0,
             borderaxespad=0.1, columnspacing=0.9)
    JF.write_csv(outdir, name, rows, ["bodies", "border", "decided_within_two", "n_decided_within_two", "n_within_two",
                                      "errors_within_two", "precision_within_two"])
    return save(fig, outdir, name, captions(d, venue)[name], venue)


# ---- robustness ----------------------------------------------------------------------------------

def world_path(key: str) -> tuple:
    return next(w[1] for w in EF.WORLDS if w[0] == key)


def fig_robust(d: dict, outdir: str, venue: str) -> List[str]:
    name = "exact_slide_robust"
    plt, fig = figure(name, venue)
    rob = d["robust"]
    worlds = world_names(d, venue)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.35, 1.0], left=0.36, right=0.98,
                          top=0.82 if venue == "cns" else 0.85, bottom=0.18, wspace=0.10)
    a, b = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1])
    ys = np.arange(len(worlds))[::-1]
    rows = []
    for j, (rule, (label, mark, colour)) in enumerate(robust_rules(d, venue).items()):
        nums = [EF.world_numbers(EF.world_cells(rob, world_path(k), rule)[EF.HEADLINE]) for k, _ in worlds]
        off = ys + (0.14 if j == 0 else -0.14)
        face = mark.get("markerfacecolor", colour)
        a.errorbar([100 * u["precision_099"] for u in nums], off, xerr=[200 * u["precision_099_se"] for u in nums],
                   linestyle="none", color=colour, ecolor=colour, marker=mark["marker"], markerfacecolor=face,
                   markeredgecolor=colour, markersize=6, elinewidth=1.0, capsize=2.5, label=label)
        b.plot([100 * u["answered_099"] for u in nums], off, linestyle="none", color=colour, marker=mark["marker"],
               markerfacecolor=face, markeredgecolor=colour, markersize=6)
        for (k, wname), u in zip(worlds, nums):
            rows.append({"world": k, "name": wname.replace("\n", " "), "rule": rule, "bodies": int(EF.HEADLINE), **u})
    a.axvline(99.0, color=INK, linewidth=0.8, linestyle=":")
    a.set_yticks(ys)
    a.set_yticklabels([w for _, w in worlds], fontsize=12, linespacing=1.0)
    a.set_xlim(80, 100.6)
    a.set_xticks([80, 85, 90, 95, 99])
    a.set_xlabel("Names right, per cent")
    fig.text(0.01, 0.975, "Names given at %s,\nthree bodies" % ("0.99" if venue == "neurips" else "99% confidence"),
             fontsize=12, color=GREY, style="italic", ha="left", va="top", linespacing=1.05)
    b.set_yticks(ys)
    b.set_yticklabels([])
    b.set_xlim(0, 25)
    b.set_xticks([0, 10, 20])
    b.set_xlabel("Fields named, per cent")
    for ax in (a, b):
        ax.set_ylim(-0.6, len(worlds) - 0.4)
    JF.letter(a, "A")
    JF.letter(b, "B")
    handles, labels = a.get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper left", bbox_to_anchor=(0.345, 1.0), ncol=2, frameon=False, fontsize=12,
               handletextpad=0.3, columnspacing=1.4)
    JF.write_csv(outdir, name, rows, ["world", "name", "rule", "bodies"] + EF.ROBUST_FIELDS[3:])
    return save(fig, outdir, name, captions(d, venue)[name], venue)


# ---- the record ----------------------------------------------------------------------------------

def write_record(outdir: str, json_path: str, d: dict, written: List[str], column: int, venue: str) -> str:
    import matplotlib
    cmd = "python run.py exact-slide-figures --json %s --outdir %s" % (
        json_path, os.path.dirname(outdir.rstrip("/")) if venue == "cns" else outdir)
    lines = ["# The exact-identification slide figures, %s" % ("CNS (results only)" if venue == "cns" else "NeurIPS"),
             "", "Built with `%s`%s." % (cmd, ", which writes this set into its `cns/` folder" if venue == "cns" else ""),
             "",
             "- Run: `%s`, sha256 %s; scoring seed %s; %d columns; synth %s; %d Gauss-Hermite nodes."
             % (json_path, JF.sha256(json_path), d["score_seed"], d["n_columns"],
                json.dumps(d["synth"], sort_keys=True), d["gh_nodes"]),
             "- The posterior panel scores the record's scoring columns again for the fields centred on %s; "
             "its shares named exactly, answered at 0.99 and right at 0.99 at each width equal the record's "
             "`by_centre` rates, checked before it draws; the column drawn is scoring column %d, the one with the least summed distance of its rank "
             "from the median rank of the posterior at %s over one, three and nine bodies."
             % (CENTRE, column, CENTRE),
             "- Reference table: `bordercall/reference/panjabi_full_spine.csv`, sha256 %s." % JF.sha256(P.DEFAULT_REFERENCE)]
    for nm in ("exact_slide_figures.py", "exact_figures.py", "exact.py", "neighbour.py", "junction_figures.py",
               "panjabi.py", "covariance.py"):
        lines.append("- Code: `bordercall/%s`, sha256 %s." % (nm, JF.sha256(os.path.join(HERE, nm))))
    lines += ["- Python %s, numpy %s, matplotlib %s; serif type %s where installed, embedded in the PDF."
              % (platform.python_version(), np.__version__, matplotlib.__version__, FACE[0]),
              "- Each panel is drawn at the size the %s slide gives it, in inches: %s."
              % ("CNS" if venue == "cns" else "NeurIPS",
                 "; ".join("%s %.3g x %.3g" % (k, w, h) for k, (w, h) in SIZES[venue].items())), ""]
    lines += ["| Figure | Files | Caption |", "|---|---|---|"]
    names = []
    for p in written:
        base = os.path.basename(p).split(".")[0]
        if base not in names:
            names.append(base)
    for nm in names:
        files = sorted(f for f in os.listdir(outdir) if f.startswith(nm + "."))
        with open(os.path.join(outdir, nm + ".caption.txt"), encoding="utf-8") as fh:
            caption = fh.read().strip().replace("|", "/")
        lines.append("| %s | %s | %s |" % (nm, ", ".join("`%s`" % f for f in files), caption))
    path = os.path.join(outdir, "FIGURES.md")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


def venue_dir(outdir: str, venue: str) -> str:
    return os.path.join(outdir, "cns") if venue == "cns" else outdir


def run(json_path: str, outdir: str, venue: str = "both") -> List[str]:
    """Both sets, the NeurIPS one into `outdir` and the CNS one into `outdir`/cns, or one of them."""
    with open(json_path, encoding="utf-8") as fh:
        d = json.load(fh)
    ref = P.load_reference(measures=list(d["measures"]))
    tps = centred_posteriors(d)
    written_all = []
    for v in (VENUES if venue == "both" else (venue,)):
        out = venue_dir(outdir, v)
        os.makedirs(out, exist_ok=True)
        written = []
        written += fig_view(d, ref, out, v)
        written += fig_measures(d, out, v)
        written += fig_posterior(d, out, tps, v)
        written += fig_ceiling(d, out, v)
        if v == "neurips":
            written += fig_calibration(d, out, v)
        written += fig_claims(d, ref, out, v)
        written += fig_robust(d, out, v)
        written.append(write_record(out, json_path, d, written, median_column(tps), v))
        written_all += written
    for p in written_all:
        print("wrote %s" % p)
    return written_all
