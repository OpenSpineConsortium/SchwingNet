"""The house format for line graphs, which every study of the package draws its line graphs in.

The owner's words of 28 October 2026, 22:54 UTC, of the build-up study's figure "Naming as the
measures are added": "i really like the format of the graph ... use it much more, as the default
for line graph plotting, of course for anatomical type graphs use Benzel format graphs". So a line
graph here is drawn as that figure is (curve_report.fig_accuracy): lettered panels side by side,
A, B, C, each with a short title beside its letter; black ink on white, serif type, thin lines,
an axis on two sides, ticks outward, no grid and no colour; each series told apart by its line
(solid, dashed, dotted, dash-dot) and its marker (filled, open; circle, square, triangle,
diamond), never by a hue, so the figure reads the same printed, projected or photocopied; a
reference level as a thin dotted line; a legend in a plain box. A drawing of the anatomy, the
column to the tables' own millimetres, takes Benzel's textbook drawing instead, as
archive/bordercall/junction_figures.py draws its profile.

Every figure is written four ways beside each other, so that nothing in it is typed: the PDF, with
no date inside, so that two builds with the same versions give one file; the PNG at 300 dpi; the
CSV of every number drawn; and the caption, under sixty words. The folder's FIGURES.md names the
records the figures were drawn from and the code that drew them, each by sha256.
"""
from __future__ import annotations

import csv
import hashlib
import os
from typing import List

INK = "#000000"
SERIF = ["Liberation Serif", "Times New Roman", "Nimbus Roman", "DejaVu Serif"]
PNG_DPI = 300
CAPTION_WORDS = 60                   # a caption's most words; the argument goes in the text
# a series by the bodies in view, as the build-up study's figures tell its widths apart
WIDTH_STYLE = {1: dict(linestyle=":", marker="^", markerfacecolor="white"),
               3: dict(linestyle="--", marker="s", markerfacecolor="white"),
               5: dict(linestyle="-", marker="o", markerfacecolor="white"),
               7: dict(linestyle="-.", marker="D", markerfacecolor="white"),
               9: dict(linestyle="-", marker="o", markerfacecolor=INK)}


def style():
    """pyplot with the house rcParams set, on the Agg backend."""
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
        "errorbar.capsize": 2.5, "figure.dpi": 100, "savefig.dpi": PNG_DPI,
        "axes.prop_cycle": matplotlib.cycler(color=[INK]),
    })
    return plt


def letter(ax, text: str, title: str = ""):
    """A panel's letter, bold, above its top left corner, and its title beside it."""
    ax.annotate(text, xy=(0, 1), xycoords="axes fraction", xytext=(-6, 5), textcoords="offset points",
                fontsize=12, fontweight="bold", ha="left", va="bottom")
    if title:
        ax.annotate(title, xy=(0, 1), xycoords="axes fraction", xytext=(10, 5), textcoords="offset points",
                    fontsize=9, ha="left", va="bottom")


def body_label(n: int) -> str:
    return "%d bod%s" % (n, "y" if n == 1 else "ies")


def save(fig, outdir: str, name: str, caption: str) -> List[str]:
    """The figure as PDF and PNG, and its caption beside them; the paths written."""
    import matplotlib.pyplot as plt
    paths = [os.path.join(outdir, name + ".pdf"), os.path.join(outdir, name + ".png")]
    fig.savefig(paths[0], bbox_inches="tight", facecolor="white", metadata={"CreationDate": None, "ModDate": None})
    fig.savefig(paths[1], bbox_inches="tight", facecolor="white")
    plt.close(fig)
    p = os.path.join(outdir, name + ".caption.txt")
    with open(p, "w", encoding="ascii", newline="\n") as fh:
        fh.write(caption.strip() + "\n")
    return paths + [p]


def write_csv(outdir: str, name: str, rows: List[dict]) -> str:
    """Every number drawn, one row a point, floats to six significant figures."""
    path = os.path.join(outdir, name + ".csv")
    with open(path, "w", encoding="ascii", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: format(v, ".6g") if isinstance(v, float) else v for k, v in r.items()})
    return path


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def words(caption: str) -> int:
    return len(caption.split())
