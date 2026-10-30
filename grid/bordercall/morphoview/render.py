"""The slices and the lines on them, drawn as Benzel's textbook draws a vertebra: the bone white with
a black outline, the vertebra measured in light grey, black ink, no colour.

A panel is a plane of the vertebra's frame, cut through the place its measures are taken: the
sagittal through the body's middle across, the first coronal through the body's mid-depth, the
second through the pedicles' isthmus, the axial through the pedicles' centre. The masks are
sampled on the plane every PIXEL_MM, each label's own indicator interpolated linearly and
outlined where it crosses one half, which is where morphometry reads a surface. A line whose
middle lies more than PROJECTED_MM off its panel's plane is drawn where it projects and marked
(p) in the key; Eisenstein's apex-to-apex line is a projection by definition, as a lateral film
superimposes the two sides.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import ndimage

from morphometry import anatomy as A

from .lines import Line

PIXEL_MM = 0.2
MARGIN_MM = 4.0
REACH_MM = 12.0                # how far above and below the vertebra the sagittal and coronal panels reach
PROJECTED_MM = 3.0
GREY = 0.82
SCALE_MM = 10.0
CALLOUT_CLEAR_MM = 3.6

# panel: (the frame axis the plane is square to, the axis drawn across and its sign, the axis drawn up)
PANELS = {
    "sagittal": (0, (1, -1.0), 2),
    "coronal_body": (1, (0, -1.0), 2),
    "coronal_pedicle": (1, (0, -1.0), 2),
    "axial_pedicle": (2, (0, -1.0), 1),
}
SHOWN_IN = {"axial_canal": "axial_pedicle"}
TITLES = {"sagittal": "Sagittal, through the body's middle", "coronal_body": "Coronal, through the body",
          "coronal_pedicle": "Coronal, each side at its isthmus", "axial_pedicle": "Axial, through the pedicles"}
ENDS = {"sagittal": ("A", "P", "S", "I"), "coronal_body": ("R", "L", "S", "I"),
        "coronal_pedicle": ("R", "L", "S", "I"), "axial_pedicle": ("R", "L", "A", "P")}
NAMES = {
    "h_ant": "anterior height", "h_mid": "middle height", "h_post_inset": "posterior height",
    "h_post": "posterior height at the wall", "wedge": "wedge",
    "body_d_mid": "waist depth", "body_w_mid": "waist width", "endplate": "upper end-plate width",
    "endplate_lower": "lower end-plate width", "endplate_depth": "upper end-plate depth",
    "endplate_lower_depth": "lower end-plate depth", "canal_ap_min": "least canal depth",
    "canal_w": "canal width", "canal_ap": "canal depth",
    "canal_ap_lateral_film": "canal depth to film line", "spinous_length": "spinous length",
    "tp_span": "transverse span", "interpedicular": "interpedicular distance", "disc_h_ant": "disc, anterior",
    "disc_h_mid": "disc, middle", "disc_h_post": "disc, posterior"}
for _side in ("right", "left"):
    NAMES["pedicle_w_" + _side] = "pedicle width, " + _side
    NAMES["pedicle_h_" + _side] = "pedicle height, " + _side
    NAMES["pedicle_chord_" + _side] = "pedicle chord, " + _side


def panel_of(ln: Line) -> str:
    return SHOWN_IN.get(ln.panel, ln.panel)


def to_panel(v: A.Vertebra, panel: str, pts: np.ndarray) -> np.ndarray:
    """World points as (across, up) on the panel, in millimetres of the vertebra's frame."""
    _, (ai, sign), up = PANELS[panel]
    loc = v.frame.local(np.atleast_2d(pts))
    return np.column_stack([sign * loc[:, ai], loc[:, up]])


def off_plane(v: A.Vertebra, panel: str, ln: Line, cut: "Cut") -> float:
    normal = PANELS[panel][0]
    mid = v.frame.local(np.atleast_2d(0.5 * (ln.a + ln.b)))[0]
    return abs(mid[normal] - cut.at(mid[0]))


class Cut:
    """Where a panel's plane lies along its normal; the pedicles' coronal panel takes each side at
    its own isthmus, the patient's right (x above the canal's midline) at one depth and the left at
    another, since the two isthmuses can lie millimetres apart front to back."""

    def __init__(self, right: float, left: float, midline: float):
        self.right, self.left, self.midline = right, left, midline

    def at(self, x):
        return np.where(np.asarray(x) >= self.midline, self.right, self.left)

    @property
    def split(self) -> bool:
        return abs(self.right - self.left) > 1e-9


def middle_of(v: A.Vertebra, normal: int, lines: List[Line]) -> Optional[float]:
    if not lines:
        return None
    mids = v.frame.local(np.array([0.5 * (ln.a + ln.b) for ln in lines]))
    return float(np.median(mids[:, normal]))


def cut_of(v: A.Vertebra, panel: str, lines: List[Line]) -> Cut:
    """Through the lines the panel shows, or the body's middle where it shows none."""
    normal = PANELS[panel][0]
    mine = [ln for ln in lines if panel_of(ln) == panel and ln.status == "drawn"
            and not ln.key.startswith(("canal_ap_lateral_film", "tp_span", "interpedicular", "canal_w"))]
    B = v.body_pts if v.body.any() else v.loc
    whole = middle_of(v, normal, mine)
    if whole is None:
        whole = float(0.5 * (B[:, normal].min() + B[:, normal].max()))
    if panel != "coronal_pedicle":
        return Cut(whole, whole, v.midline)
    right = middle_of(v, normal, [ln for ln in mine if ln.key.endswith("_right")])
    left = middle_of(v, normal, [ln for ln in mine if ln.key.endswith("_left")])
    return Cut(whole if right is None else right, whole if left is None else left, v.midline)


def window(v: A.Vertebra, panel: str) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    _, (ai, sign), up = PANELS[panel]
    lo, hi = v.loc.min(0), v.loc.max(0)
    across = sorted((sign * (lo[ai] - MARGIN_MM), sign * (hi[ai] + MARGIN_MM)))
    reach = REACH_MM if up == 2 else MARGIN_MM
    return (across[0], across[1]), (lo[up] - reach, hi[up] + reach)


def sample(v: A.Vertebra, vol: np.ndarray, panel: str, cut: Cut) -> Tuple[Dict[int, np.ndarray], tuple]:
    """Each label's indicator on the panel's pixels, and the panel's extent for imshow."""
    normal, (ai, sign), up = PANELS[panel]
    (h0, h1), (u0, u1) = window(v, panel)
    hs, us = np.arange(h0, h1, PIXEL_MM), np.arange(u0, u1, PIXEL_MM)
    H, U = np.meshgrid(hs, us)
    loc = np.zeros((H.size, 3))
    loc[:, ai], loc[:, up] = sign * H.ravel(), U.ravel()
    loc[:, normal] = cut.at(loc[:, 0]) if normal != 0 else cut.right
    inv = np.linalg.inv(np.asarray(v.grid.affine, float))
    ijk = v.points_world(loc) @ inv[:3, :3].T + inv[:3, 3]
    a = np.maximum(np.floor(ijk.min(0)).astype(int) - 1, 0)
    b = np.minimum(np.ceil(ijk.max(0)).astype(int) + 2, np.array(vol.shape))
    crop = vol[a[0]:b[0], a[1]:b[1], a[2]:b[2]]
    fields = {}
    for lab in np.unique(crop):
        if lab == 0:
            continue
        f = ndimage.map_coordinates((crop == lab).astype(np.float32), (ijk - a).T, order=1, cval=0.0)
        if f.max() >= 0.5:
            fields[int(lab)] = f.reshape(H.shape)
    return fields, (hs[0], hs[-1], us[0], us[-1])


def draw_bone(ax, fields: Dict[int, np.ndarray], extent: tuple, mine: int) -> None:
    hs = np.linspace(extent[0], extent[1], next(iter(fields.values())).shape[1]) if fields else None
    if hs is None:
        return
    us = np.linspace(extent[2], extent[3], next(iter(fields.values())).shape[0])
    for lab, f in sorted(fields.items(), key=lambda kv: kv[0] == mine):
        shade = str(GREY) if lab == mine else "white"
        ax.contourf(hs, us, f, levels=[0.5, 2.0], colors=[shade])
        ax.contour(hs, us, f, levels=[0.5], colors="black", linewidths=0.6)


def caliper(ax, p: np.ndarray, q: np.ndarray, dashed: bool = False) -> None:
    style = dict(arrowstyle="|-|,widthA=0.25,widthB=0.25", lw=0.8, color="black", shrinkA=0, shrinkB=0)
    if dashed:
        style["linestyle"] = (0, (3, 2))
    ax.annotate("", xy=tuple(q), xytext=tuple(p), arrowprops=style)


def callout(ax, p: np.ndarray, q: np.ndarray, n: int, taken: List[np.ndarray]) -> None:
    """The line's number in a circle beside it, at the first place along it, either side, that
    lies CALLOUT_CLEAR_MM from every number already placed on the panel."""
    d = q - p
    norm = float(np.hypot(*d)) or 1.0
    off = np.array([-d[1], d[0]]) / norm * 2.4
    spots = [p + t * d + s * off for t in (0.5, 0.3, 0.7, 0.15, 0.85) for s in (1.0, -1.0)]
    clear = [c for c in spots if all(np.hypot(*(c - t)) >= CALLOUT_CLEAR_MM for t in taken)]
    at = clear[0] if clear else spots[0]
    taken.append(at)
    ax.text(*at, str(n), fontsize=6.5, ha="center", va="center",
            bbox=dict(boxstyle="circle,pad=0.15", fc="white", ec="black", lw=0.5))


def scale_bar(ax, extent: tuple) -> None:
    x0, y0 = extent[0] + 2.0, extent[2] + 2.0
    ax.plot([x0, x0 + SCALE_MM], [y0, y0], color="black", lw=1.6, solid_capstyle="butt")
    ax.text(x0 + 0.5 * SCALE_MM, y0 + 1.0, "%d mm" % SCALE_MM, fontsize=6.5, ha="center", va="bottom")


def ends(ax, panel: str) -> None:
    left, right, top, bottom = ENDS[panel]
    kw = dict(transform=ax.transAxes, fontsize=7, ha="center", va="center")
    ax.text(-0.03, 0.5, left, **kw)
    ax.text(1.03, 0.5, right, **kw)
    ax.text(0.5, 1.02, top, **kw)
    ax.text(0.5, -0.02, bottom, **kw)


def value_text(ln: Line) -> str:
    unit = " deg" if ln.rule == "angle" else " mm"
    return "%.1f%s" % (ln.measured, unit)


def draw_line(ax, v: A.Vertebra, panel: str, ln: Line, n: int, taken: List[np.ndarray]) -> None:
    p, q = to_panel(v, panel, np.array([ln.a, ln.b]))
    if ln.rule == "angle":
        ax.plot(*np.array([p, q]).T, color="black", lw=0.8, linestyle=(0, (3, 2)))
        lp, lq = to_panel(v, panel, np.array(ln.extra["lower plate"]))
        ax.plot(*np.array([lp, lq]).T, color="black", lw=0.8, linestyle=(0, (3, 2)))
        callout(ax, p, 0.5 * (p + lp), n, taken)
        return
    for jp, jq in (to_panel(v, panel, np.array(pair)) for pair in ln.extra.values()):
        ax.plot([jp[0], jq[0]], [jp[1], jq[1]], color="black", lw=0.6, linestyle=":")
    caliper(ax, p, q)
    callout(ax, p, q, n, taken)


def panel(ax, v: A.Vertebra, vol: np.ndarray, mine: int, name: str, lines: List[Line], start: int) -> List[str]:
    """One panel drawn; the key's lines for it, numbered from start."""
    cut = cut_of(v, name, lines)
    fields, extent = sample(v, vol, name, cut)
    draw_bone(ax, fields, extent, mine)
    key = []
    taken: List[np.ndarray] = []
    n = start
    for ln in lines:
        if panel_of(ln) != name or ln.status != "drawn":
            continue
        draw_line(ax, v, name, ln, n, taken)
        mark = " (p)" if "apex to apex" in ln.extra or off_plane(v, name, ln, cut) > PROJECTED_MM else ""
        where = "" if ln.level == v.level else " %s" % ln.level
        key.append("%d  %s%s %s%s" % (n, NAMES.get(ln.key, ln.key), where, value_text(ln), mark))
        n += 1
    if cut.split:
        ax.axvline(-cut.midline if PANELS[name][1][1] < 0 else cut.midline, color="black", lw=0.5, linestyle=":")
    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])
    ax.set_aspect("equal")
    ax.axis("off")
    scale_bar(ax, extent)
    ends(ax, name)
    return key


def figure(v: A.Vertebra, vol: np.ndarray, mine: int, lines: List[Line], study: str):
    """The vertebra's four panels, each with its key beside it; the figure."""
    from schwingcheck import figures as FIG
    plt = FIG.style()
    fig = plt.figure(figsize=(10.5, 8.4))
    grid = fig.add_gridspec(2, 4, width_ratios=[3.0, 1.9, 3.0, 1.9], hspace=0.22, wspace=0.08)
    n = 1
    for k, (letter, name) in enumerate(zip("ABCD", PANELS)):
        row, col = divmod(k, 2)
        ax, side = fig.add_subplot(grid[row, 2 * col]), fig.add_subplot(grid[row, 2 * col + 1])
        key = panel(ax, v, vol, mine, name, lines, n)
        n += len(key)
        FIG.letter(ax, letter, TITLES[name])
        side.axis("off")
        side.text(0.02, 0.98, "\n".join(key) or "nothing measured here", transform=side.transAxes, fontsize=6.8,
                  ha="left", va="top", linespacing=1.35)
    fig.text(0.5, 0.94, "Study %s, %s" % (study, v.level), fontsize=10, ha="center", va="bottom")
    return fig


def mine_of(names: Dict[int, str], level: str) -> Optional[int]:
    for k, lv in names.items():
        if lv == level:
            return k
    return None

