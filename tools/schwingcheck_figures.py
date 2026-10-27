"""Draw chapter 36's diagrams of SchwingNet, SchwingCheck and a measuring device, as SVG.

Five diagrams come out of this script, each with the JSON record the textbook site reads beside
it: SchwingNet's stages as chapter 12 describes the reported stack; SchwingCheck's rule, from
seven measures to a named field; the three pathways the white paper lays out, LevelCheck among them;
the seven measures as distances between landmarks on an AP and a lateral view; and a proposed
device that reads those landmarks in one pass with no segmentation, to keep latency low.

Every number a diagram prints is copied from tools/schwingcheck_records.json, which names the file
and the commit each one comes from; nothing here is computed. The device is a proposal: no part of
it beyond the four-corner detector and the posterior has been built or timed, and the diagrams say
so where they show it.

    python3 tools/schwingcheck_figures.py docs/textbook/figures/36

Standard library only, ASCII output, so it runs on a GitHub runner in under a second.
"""
from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORDS = ROOT / "tools" / "schwingcheck_records.json"
CHAPTER = "docs/textbook/36-schwingcheck-an-explainable-bayesian-check-on-vertebral-labels.md"
SCRIPT = "tools/schwingcheck_figures.py"

INK, INK2, GRID, BG = "#1b1b1a", "#5c5b57", "#d9d8d3", "#ffffff"
FILL = "#f2f1ed"          # a learned stage
ACCENT = "#2a5fa8"        # a length being measured
PROPOSED = "#9a6f12"      # a part that is proposed and not built
FONT = "font-family='DejaVu Sans, Helvetica, Arial, sans-serif'"
STYLE = (
    "<style>.ink{fill:#1b1b1a}.ink2{fill:#5c5b57}.stk{stroke:#1b1b1a}.stk2{stroke:#5c5b57}"
    ".learned{fill:#f2f1ed}.paper{fill:#ffffff}.head{fill:#1b1b1a}.rec{fill:#e4ecf7}"
    "@media (prefers-color-scheme: dark){"
    ".bg{fill:#151514}.ink{fill:#ecebe6}.ink2{fill:#b5b3ac}.stk{stroke:#ecebe6}.stk2{stroke:#b5b3ac}"
    ".learned{fill:#262624}.paper{fill:#1c1c1a}.head{fill:#ecebe6}.rec{fill:#1e2b40}}</style>"
)
DEFS = (
    "<defs>"
    f"<marker id='arrow' viewBox='0 0 10 10' refX='9' refY='5' markerWidth='7' markerHeight='7' orient='auto'>"
    f"<path d='M0,0 L10,5 L0,10 z' class='head' fill='{INK}'/></marker>"
    f"<marker id='dim' viewBox='0 0 10 10' refX='9' refY='5' markerWidth='6' markerHeight='6' "
    f"orient='auto-start-reverse'><path d='M0,0 L10,5 L0,10 z' fill='{ACCENT}'/></marker>"
    f"<marker id='prop' viewBox='0 0 10 10' refX='9' refY='5' markerWidth='7' markerHeight='7' orient='auto'>"
    f"<path d='M0,0 L10,5 L0,10 z' fill='{PROPOSED}'/></marker>"
    "</defs>"
)
CHAR = 0.57               # mean glyph width of DejaVu Sans, in ems, for wrapping by hand


# ----------------------------------------------------------------------------------------
# SVG primitives
# ----------------------------------------------------------------------------------------
def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, size=12, anchor="start", cls="ink", weight="normal", style="normal", color=None):
    fill = color or (INK if cls == "ink" else INK2)
    klass = "" if color else f" class='{cls}'"
    return (f"<text x='{x:.1f}' y='{y:.1f}' font-size='{size}' text-anchor='{anchor}'{klass} fill='{fill}' "
            f"font-weight='{weight}' font-style='{style}'>{esc(s)}</text>")


def wrap(s, width, size):
    return textwrap.wrap(s, max(8, int(width / (size * CHAR))), break_long_words=False)


def paragraph(x, y, s, width, size=11, anchor="start", cls="ink2", lead=1.3, color=None, style="normal"):
    """A wrapped block of text; returns the parts and the y below its last line."""
    out = []
    for line in wrap(s, width, size):
        out.append(text(x, y, line, size, anchor, cls, style=style, color=color))
        y += size * lead
    return out, y


def line(x1, y1, x2, y2, cls="stk", width=1.2, dash=None, color=None, end=None, start=None):
    stroke = color or (INK if cls == "stk" else INK2)
    klass = "" if color else f" class='{cls}'"
    d = f" stroke-dasharray='{dash}'" if dash else ""
    m = (f" marker-end='url(#{end})'" if end else "") + (f" marker-start='url(#{start})'" if start else "")
    return (f"<line x1='{x1:.1f}' y1='{y1:.1f}' x2='{x2:.1f}' y2='{y2:.1f}'{klass} stroke='{stroke}' "
            f"stroke-width='{width}'{d}{m}/>")


def arrow(x1, y1, x2, y2, proposed=False):
    if proposed:
        return line(x1, y1, x2, y2, width=1.4, dash="2 3", color=PROPOSED, end="prop")
    return line(x1, y1, x2, y2, width=1.3, end="arrow")


def polygon(points, fill_cls="paper", width=1.2, dash=None, color=None):
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    stroke = f"stroke='{color}'" if color else f"class='{fill_cls} stk' stroke='{INK}'"
    fill = BG if fill_cls == "paper" else FILL
    d = f" stroke-dasharray='{dash}'" if dash else ""
    if color:
        return f"<polygon points='{pts}' fill='none' {stroke} stroke-width='{width}'{d}/>"
    return f"<polygon points='{pts}' {stroke} fill='{fill}' stroke-width='{width}'{d}/>"


def ellipse(cx, cy, rx, ry, width=1.0):
    return (f"<ellipse cx='{cx:.1f}' cy='{cy:.1f}' rx='{rx:.1f}' ry='{ry:.1f}' class='stk' stroke='{INK}' "
            f"fill='none' stroke-width='{width}'/>")


KINDS = {
    # kind: (fill class, dash, stroke colour)
    "learned": ("learned", None, None),
    "rule": ("paper", "5 3", None),
    "proposed": ("paper", "2 3", PROPOSED),
    "plain": ("paper", None, None),
}


def box(x, y, w, h, title, body="", kind="learned", size=11):
    """A stage: a rectangle whose border says what kind of stage it is, a bold title and a
    wrapped line or two below it."""
    fill_cls, dash, color = KINDS[kind]
    fill = FILL if fill_cls == "learned" else BG
    d = f" stroke-dasharray='{dash}'" if dash else ""
    stroke = f"stroke='{color}'" if color else f"class='{fill_cls} stk' stroke='{INK}'"
    fill_attr = f" fill='{fill}'" if not color else f" fill='{BG}' class='paper'"
    out = [f"<rect x='{x:.1f}' y='{y:.1f}' width='{w:.1f}' height='{h:.1f}' rx='4' {stroke}{fill_attr} "
           f"stroke-width='1.3'{d}/>"]
    tcolor = PROPOSED if kind == "proposed" else None
    yy = y + 18
    for t in wrap(title, w - 16, size + 1):
        out.append(text(x + w / 2, yy, t, size + 1, "middle", "ink", "bold", color=tcolor))
        yy += (size + 1) * 1.25
    if body:
        parts, _ = paragraph(x + w / 2, yy + 2, body, w - 14, size, "middle", "ink2")
        out += parts
    return out


def legend_kinds(x, y, kinds=("learned", "rule", "proposed")):
    words = {"learned": "learned from data", "rule": "a rule: learns nothing",
             "proposed": "proposed: not built, not timed", "plain": "an input or an output"}
    out, xx = [], x
    for k in kinds:
        out += box(xx, y, 26, 16, "", kind=k)
        out.append(text(xx + 34, y + 12, words[k], 11, cls="ink2"))
        xx += 46 + len(words[k]) * 11 * CHAR + 18
    return out


def svg(width, height, body, title):
    return (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {width} {height}' width='{width}' "
            f"height='{height}' {FONT} role='img'><title>{esc(title)}</title>{STYLE}{DEFS}"
            f"<rect class='bg' width='{width}' height='{height}' fill='{BG}'/>" + "".join(body) + "</svg>\n")


def pct(v, places=1):
    return f"{100 * v:.{places}f}%"


# ----------------------------------------------------------------------------------------
# small anatomical drawings
# ----------------------------------------------------------------------------------------
def frame_icon(x, y, w, h, bodies=5, sacrum=True):
    """A fluoroscopic frame: a dark-edged field holding a short column of bodies, drawn as lines."""
    out = [f"<rect x='{x}' y='{y}' width='{w}' height='{h}' rx='6' class='paper stk' stroke='{INK}' "
           f"fill='{BG}' stroke-width='1.3'/>"]
    bh, gap = (h - 40) / (bodies + 1.2), 5
    cx = x + w / 2
    for k in range(bodies):
        top = y + 12 + k * bh
        half = w * 0.22 + k * 1.2
        out.append(polygon([(cx - half, top), (cx + half, top), (cx + half + 1, top + bh - gap),
                            (cx - half - 1, top + bh - gap)]))
    if sacrum:
        top = y + 12 + bodies * bh
        half = w * 0.22 + bodies * 1.2
        out.append(polygon([(cx - half - 4, top), (cx + half + 4, top), (cx + 4, top + bh * 1.1),
                            (cx - 4, top + bh * 1.1)]))
    return out


def ap_vertebra(ox, oy, k):
    """The lumbar-shaped body of bordercall's measures figure, seen front to back, at scale k
    (pixels per drawing unit), origin at the lower end plate's middle; returns parts and the
    landmark positions in pixels."""
    def p(x, y):
        return ox + k * x, oy - k * y
    out = [polygon([p(-24, 0), p(-21.5, 13.5), p(-23, 27), p(23, 27), p(21.5, 13.5), p(24, 0)], width=1.4)]
    for s in (-1, 1):
        out.append(polygon([p(s * 23, 17), p(s * 36, 18), p(s * 36, 22.5), p(s * 23, 23.5)], width=1.0))
        cx, cy = p(s * 15.5, 20)
        out.append(ellipse(cx, cy, 4 * k, 5.25 * k))
    cx, cy = p(0, 11)
    out.append(ellipse(cx, cy, 2.75 * k, 4.5 * k))
    marks = {1: p(-23, 27), 2: p(23, 27), 3: p(-24, 0), 4: p(24, 0), 5: p(-11.5, 20), 6: p(11.5, 20)}
    return out, marks


def lateral_vertebra(ox, oy, k):
    """The same body from the side, front to the left; landmarks 1 to 4 are the body's corners and
    5 the spinolaminar point, where the laminae meet behind the canal."""
    def p(x, y):
        return ox + k * x, oy - k * y
    out = [polygon([p(-16.5, 0), p(-15, 13), p(-16.5, 26), p(16.5, 27), p(16.5, 0)], width=1.4),
           polygon([p(16.5, 23.5), p(30, 23), p(30, 15.5), p(16.5, 15)], width=1.0),
           polygon([p(30, 28), p(35.5, 27), p(36.5, 4), p(31, 5)], width=1.0),
           polygon([p(36.2, 20), p(53, 9.5), p(51.5, 5.5), p(36.4, 11)], width=1.0)]
    marks = {1: p(-16.5, 26), 2: p(16.5, 27), 3: p(16.5, 0), 4: p(-16.5, 0), 5: p(30.8, 10.5)}
    return out, marks


def dot(x, y, n, proposed=False, dx=0, dy=-9):
    color = PROPOSED if proposed else INK
    fill = PROPOSED if proposed else INK
    klass = "" if proposed else " class='head'"
    return [f"<circle cx='{x:.1f}' cy='{y:.1f}' r='4.2' fill='{fill}'{klass} stroke='{BG}' stroke-width='1'/>",
            text(x + dx, y + dy, str(n), 11, "middle", "ink", "bold", color=color if proposed else None)]


def dimension(a, b, label, offset=(0, 0), size=11, anchor="middle"):
    out = [line(a[0], a[1], b[0], b[1], width=1.4, color=ACCENT, end="dim", start="dim")]
    mx, my = (a[0] + b[0]) / 2 + offset[0], (a[1] + b[1]) / 2 + offset[1]
    for i, t in enumerate(label.split("\n")):
        out.append(text(mx, my + i * size * 1.2, t, size, anchor, color=ACCENT))
    return out


def extension(a, b):
    return line(a[0], a[1], b[0], b[1], cls="stk2", width=0.7)


# ----------------------------------------------------------------------------------------
# 36.1 SchwingNet as built
# ----------------------------------------------------------------------------------------
def fig_schwingnet(rec):
    det = rec["corner_detector"]
    W, H = 1000, 520
    body = [text(20, 30, "SchwingNet as built: the stages, and which of them learn", 16, weight="bold"),
            text(20, 50, "The reported stack of chapter 12, one model per stage; version 1 inherits the separate "
                 "stages. Read left to right.", 11.5, cls="ink2")]
    body += frame_icon(20, 90, 110, 190)
    body.append(text(75, 300, "a C-arm frame", 11, "middle", "ink2"))
    body += box(160, 100, 170, 150, "Body detector",
                "YOLO11m-pose: a box and four corner keypoints per body; a second detector finds the "
                "vertebra and the sacrum on real frames", "learned")
    body.append(arrow(130, 185, 158, 185))
    body += box(360, 110, 150, 130, "Box repair",
                "fills at most two bodies per gap from the spacing, never past the chain's ends", "rule")
    body.append(arrow(330, 175, 358, 175))
    body += box(560, 70, 200, 120, "Level encoder and run head",
                "ResNet-18 over 27 classes, C1 to C7, T1 to T13, L1 to L6 and the sacrum; a bidirectional "
                "GRU reads runs of 2 to 9 bodies", "learned")
    body += box(560, 215, 200, 100, "Count from the anchor",
                "each body the k-th from the sacrum or C2; reads positions, never a class", "rule")
    body.append(arrow(510, 160, 558, 130))
    body.append(arrow(510, 190, 558, 255))
    body += box(800, 140, 170, 100, "Coupling",
                "the count and the names joined into one answer per body", "rule")
    body.append(arrow(760, 130, 798, 175))
    body.append(arrow(760, 265, 798, 210))
    body.append(text(885, 262, "named bodies on the overlay", 11, "middle", "ink2", style="italic"))
    # what the white paper asks of SchwingNet, and where SchwingCheck reads its output
    body.append(text(160, 352, "In the white paper's two SchwingCheck pathways", 12, weight="bold", cls="ink2"))
    body.append(arrow(245, 250, 245, 364))
    body += box(160, 366, 240, 92, "AP and lateral panoramas",
                "overlapping exposures linked from the anchor into one map per plane (chapter 34)", "rule")
    body.append(arrow(400, 412, 438, 412, proposed=True))
    body += box(440, 366, 260, 92, "Five of the seven measures",
                "the corners give both end-plate widths (AP) or depths (lateral) and the body's height; the "
                "canal needs landmarks no head finds yet (figures 36.4, 36.5)", "proposed")
    body.append(arrow(700, 412, 738, 412, proposed=True))
    body += box(740, 366, 230, 92, "SchwingCheck",
                "names the run, or checks the run head's names, with a probability on each (figure 36.2)",
                "rule")
    body += legend_kinds(20, 478)
    body.append(text(20, 510, f"Source: chapter 12 and its artifacts (Reported). The corner detector, "
                     f"{det['model'].split(',')[0]}, takes {det['ms_per_image']:g} ms per image on hardware its "
                     f"report does not name.", 10.5, cls="ink2"))
    return svg(W, H, body, "SchwingNet as built")


# ----------------------------------------------------------------------------------------
# 36.2 SchwingCheck's rule
# ----------------------------------------------------------------------------------------
LEVELS = (["C3", "C4", "C5", "C6", "C7"] + [f"T{i}" for i in range(1, 13)] + [f"L{i}" for i in range(1, 6)])


def fig_rule(rec):
    ex = rec["exact_rule"]
    gen = ex["generator"]
    W, H = 1000, 640
    body = [text(20, 30, "SchwingCheck: from seven measures to a named field", 16, weight="bold"),
            text(20, 50, "The Bayes rule for these fields and a uniform prior over places, as bordercall's "
                 "exact.py computes it. Steps 1 to 4, left to right.", 11.5, cls="ink2")]
    # 1 the field
    body.append(text(30, 88, "1  The bodies in view", 13, weight="bold"))
    for i in range(3):
        top = 108 + i * 52
        body.append(polygon([(60, top), (150, top - 2), (150, top + 38), (60, top + 40)]))
    body.append(line(160, 106, 160, 252, width=1.0))
    body += paragraph(168, 150, "seven measures of each body: end-plate widths and depths, posterior "
                      "height, canal width and depth (figure 36.4)", 92, 10.5)[0]
    # 2 every place
    body.append(text(300, 88, "2  Every place it could occupy", 13, weight="bold"))
    lx, ly, step = 330, 106, 15
    for i, name in enumerate(LEVELS):
        body.append(text(lx, ly + i * step + 4, name, 10, "end", "ink2"))
        body.append(line(lx + 6, ly + i * step, lx + 18, ly + i * step, cls="stk2", width=0.8))
    for top, shade in (("C3", 0.10), ("T5", 0.10), ("T11", 0.35), ("L3", 0.10)):
        y0 = ly + LEVELS.index(top) * step - 6
        body.append(f"<rect x='{lx + 24}' y='{y0:.1f}' width='26' height='{3 * step - 3:.1f}' rx='3' "
                    f"fill='{ACCENT}' fill-opacity='{shade}' stroke='{ACCENT}' stroke-width='1'/>")
    body += paragraph(lx + 60, ly + 4, "the same three bodies set from C3, from T5, from T11, from L3, "
                      "and every place between", 150, 10.5)[0]
    places = gen["levels"] - 3 + 1
    body += paragraph(lx + 60, ly + 8 * step, f"{places} places for three bodies between "
                      f"{gen['places_from']} and {gen['places_to']} ({gen['levels']} levels), each "
                      f"equally likely before the measures are seen", 150, 10.5)[0]
    body.append(arrow(268, 180, 296, 180))
    # 3 likelihood
    body.append(text(560, 88, "3  Likelihood of each place", 13, weight="bold"))
    body += box(560, 104, 200, 190, "Likelihood at each place",
                f"each measure against Panjabi's mean and spread for that level, every body scaled by one "
                f"shared size factor (SD {pct(gen['scale_sd'], 0)}), measurement noise {gen['noise_mm']:g} mm; "
                f"the size factor integrated out by {gen['gh_nodes']}-node quadrature", "rule", 10.5)
    body.append(arrow(512, 200, 558, 200))
    # 4 posterior and the decision
    body.append(text(790, 88, "4  Posterior and a name", 13, weight="bold"))
    bx, by, bw, bh = 790, 110, 190, 120
    heights = [0.01, 0.0, 0.0, 0.01, 0.0, 0.0, 0.02, 0.0, 0.0, 0.01, 0.02, 0.03, 0.04, 0.06, 0.11, 0.55,
               0.10, 0.03, 0.01, 0.0]
    for i, v in enumerate(heights):
        h = bh * v / 0.6
        x = bx + i * bw / len(heights)
        body.append(f"<rect x='{x + 1:.1f}' y='{by + bh - h:.1f}' width='{bw / len(heights) - 2:.1f}' "
                    f"height='{h:.1f}' fill='{ACCENT}'/>")
    body.append(line(bx, by + bh, bx + bw, by + bh, cls="stk2", width=1))
    body.append(text(bx + bw / 2, by + bh + 16, "places, C3 to L3 (schematic)", 10, "middle", "ink2"))
    body.append(arrow(762, 200, 788, 200))
    body += box(790, 268, 190, 70, "Largest place at 0.99 or above?", "yes: name every body in view", "plain",
                10.5)
    body += box(790, 372, 190, 70, "No", "a region or border claim that reaches 0.99, or \"cannot say\"",
                "plain", 10.5)
    body.append(arrow(885, 252, 885, 266))
    body.append(arrow(885, 338, 885, 370))
    # the numbers
    ty = 488
    body.append(text(30, ty, "On the record's synthetic columns (2,000 per width), with both views:", 12.5,
                     weight="bold"))
    cols = ["1", "3", "5", "9", "15"]
    head = ["Bodies in view"] + cols
    rows = [["Right on forced choice"] + [pct(ex["widths"][c]["exact"]) for c in cols],
            ["Answered at 0.99"] + [pct(ex["widths"][c]["answered_099"]) for c in cols],
            ["Right when answered at 0.99"] + [pct(ex["widths"][c]["precision_099"], 2) for c in cols]]
    xs = [30, 300, 420, 540, 660, 780]
    for j, h in enumerate(head):
        body.append(text(xs[j], ty + 26, h, 11.5, "start" if j == 0 else "middle", "ink", "bold"))
    for i, r in enumerate(rows):
        for j, v in enumerate(r):
            body.append(text(xs[j], ty + 48 + 20 * i, v, 11.5, "start" if j == 0 else "middle",
                             "ink" if j else "ink2"))
    body.append(line(30, ty + 33, 820, ty + 33, cls="stk2", width=0.7))
    s = ex["source"]
    body += paragraph(30, ty + 124, f"Source: bordercall {s['file']} at {s['commit']} (Reported here, since the "
                      "record is another repository's; synthetic columns from Panjabi's tables, no patient). "
                      "While the generator holds, a name given at 0.99 is right at least 99% of the time by "
                      "construction.", 940, 10.5)[0]
    return svg(W, H, body, "SchwingCheck's rule")


# ----------------------------------------------------------------------------------------
# 36.3 the three pathways
# ----------------------------------------------------------------------------------------
RECOMMENDED = "#e4ecf7"     # the outputs the white paper recommends


def lane(y, title, stages, note, decided, recommended=None):
    """One pathway as a row of stages, from its input to a label on the X-ray: the stage where the
    level is decided drawn with a heavy border, a recommended output shaded, the note underneath."""
    out = [text(20, y - 14, title, 13.5, weight="bold")]
    x, w, h, gap = 20, 162, 112, 22
    for k, (name, words, kind) in enumerate(stages):
        out += box_on_shade(x, y, w, h, name, words, 10.5) if k == recommended else box(x, y, w, h, name, words,
                                                                                         kind, 10.5)
        if k == decided:
            out.append(f"<rect x='{x - 3}' y='{y - 3}' width='{w + 6}' height='{h + 6}' rx='6' fill='none' "
                       f"class='stk' stroke='{INK}' stroke-width='2.6'/>")
        if k < len(stages) - 1:
            out.append(arrow(x + w, y + h / 2, x + w + gap - 2, y + h / 2, proposed=(stages[k + 1][2] == "proposed")))
        x += w + gap
    out += paragraph(20, y + h + 22, note, 960, 11, cls="ink2")[0]
    return out


def box_on_shade(x, y, w, h, title, body, size):
    """An output the white paper recommends: a plain box on the recommended shade, whose fill and words
    follow the colour scheme through their classes."""
    out = [f"<rect x='{x:.1f}' y='{y:.1f}' width='{w:.1f}' height='{h:.1f}' rx='4' class='rec' "
           f"fill='{RECOMMENDED}' stroke='{ACCENT}' stroke-width='1.6'/>"]
    yy = y + 18
    for t in wrap(title, w - 16, size + 1):
        out.append(text(x + w / 2, yy, t, size + 1, "middle", weight="bold"))
        yy += (size + 1) * 1.25
    for t in wrap(body, w - 14, size):
        out.append(text(x + w / 2, yy + 2, t, size, "middle", cls="ink2"))
        yy += size * 1.3
    return out


def fig_pathways(rec):
    ex = rec["exact_rule"]
    W, H = 1000, 740
    body = [text(20, 30, "Three pathways to a level label on the X-ray", 16, weight="bold"),
            text(20, 50, "As the white paper lays them out: LevelCheck is prior art; SchwingCheck3D and "
                 "SchwingCheck2D are its own. The heavy border marks where the level is decided.", 11.5,
                 cls="ink2")]
    body += lane(96, "LevelCheck, prior art (US 11,284,846, listed to expire about 2034)", [
        ("1  Label the CT", "a clinician's click on each target vertebra: the only classification", "plain"),
        ("2  Segment the CT", "the target vertebra in the preoperative CT", "learned"),
        ("3  Line integrals", "the X-ray converted to line integrals of attenuation", "rule"),
        ("4, 5  Pose and DRR", "render, compare by gradient information, update the pose, repeat", "rule"),
        ("6  Overlay", "the final DRR and the CT's labels on the X-ray", "plain")],
        "Nothing checks step 1: a wrong CT label registers as well as a right one. LevelCheck matters here as "
        "proof that surgeons use a label overlay; in a mock operating room their median error fell from 30.4% "
        "to 2.4% with it (Manbachi et al. 2018).", 0)
    body += lane(306, "SchwingCheck3D, when a preoperative CT exists", [
        ("1  Segment the CT", "one mask per vertebra from a CT instance segmenter", "learned"),
        ("2  Check the labels", "SchwingCheck reads the seven measures from the 3D masks; a label it "
                                "contradicts at 0.01 goes back to the radiologist", "rule"),
        ("3  Panorama", "SchwingNet, with each C-arm pose tracked in world space", "learned"),
        ("4  Carry the labels", "a pose fitted to matched vertebral centroids; SchwingCheck's posterior "
                                "fused with each label", "rule"),
        ("A label with its probability", "on the X-ray", "plain")],
        "The only pathway that checks the CT's labels before surgery; the centroid fit uses no DRR, no image "
        "similarity and no overlay of a rendered image.", 1, recommended=4)
    body += lane(516, "SchwingCheck2D, no CT: the default", [
        ("1  Panoramas", "AP and lateral, from SchwingNet; both planes, since widths come from the AP and "
                         "depths from the lateral", "learned"),
        ("2  One mask per body", "FlexRay on each panorama; or landmarks with no mask (figure 36.5)",
         "learned"),
        ("3  Name or check", "SchwingCheck names the run from the bodies, or checks the names it is given",
         "rule"),
        ("A name at 0.99", "otherwise the two or three likeliest levels, or \"cannot say\"", "plain")],
        f"No CT, no registration and no patent in the path. On the synthetic record its forced-choice error "
        f"falls from {pct(1 - ex['widths']['9']['exact'])} at nine bodies to "
        f"{pct(1 - ex['widths']['15']['exact'], 2)} at fifteen, and a panorama puts more bodies in view. The reader "
        "that takes the measures off radiographs is not built.", 2, recommended=3)
    body += legend_kinds(20, 686, ("learned", "rule", "plain"))
    body.append(f"<rect x='640' y='686' width='26' height='16' rx='4' class='rec' fill='{RECOMMENDED}' stroke='{ACCENT}' "
                f"stroke-width='1.6'/>")
    body.append(text(674, 698, "the output the white paper recommends", 11, cls="ink2"))
    body += paragraph(20, 726, "Source: the white paper's section Three pathways (Inferred, a design); "
                      "SchwingCheck's rates from bordercall's records (synthetic, no patient).", 960, 10.5)[0]
    return svg(W, H + 12, body, "Three pathways")


# ----------------------------------------------------------------------------------------
# 36.4 the seven measures as landmark distances
# ----------------------------------------------------------------------------------------
def fig_landmarks(rec):
    W, H = 1000, 620
    k = 6.2
    body = [text(20, 30, "The seven measures as distances between landmarks, with no outline", 16,
                 weight="bold"),
            text(20, 50, "Black dots: the four corners SchwingNet's body detector already finds. Ochre: landmarks "
                 "no trained head finds yet. Blue: the lengths SchwingCheck reads.", 11.5, cls="ink2")]
    # AP
    ox, oy = 285, 330
    parts, m = ap_vertebra(ox, oy, k)
    body.append(text(ox, 90, "AP", 14, "middle", weight="bold"))
    body += parts
    body += [extension((m[1][0], m[1][1] - 4), (m[1][0], m[1][1] - 40)),
             extension((m[2][0], m[2][1] - 4), (m[2][0], m[2][1] - 40))]
    body += dimension((m[1][0], m[1][1] - 32), (m[2][0], m[2][1] - 32), "upper end-plate width (1 to 2)",
                      offset=(0, -8))
    body += [extension((m[3][0], m[3][1] + 4), (m[3][0], m[3][1] + 40)),
             extension((m[4][0], m[4][1] + 4), (m[4][0], m[4][1] + 40))]
    body += dimension((m[3][0], m[3][1] + 32), (m[4][0], m[4][1] + 32), "lower end-plate width (3 to 4)",
                      offset=(0, 20))
    body += dimension((m[5][0] + 6, m[5][1]), (m[6][0] - 6, m[6][1]), "canal width (5 to 6)",
                      offset=(0, -10), size=10.5)
    hx = m[3][0] - 62
    body += [extension((m[1][0] - 4, m[1][1]), (hx - 6, m[1][1])),
             extension((m[3][0] - 4, m[3][1]), (hx - 6, m[3][1]))]
    body += dimension((hx, m[1][1]), (hx, m[3][1]), "body\nheight", offset=(-8, -6), size=10.5, anchor="end")
    for n in (1, 2, 3, 4):
        body += dot(*m[n], n, dy=(-9 if n < 3 else 18), dx=(-10 if n in (1, 3) else 10))
    for n in (5, 6):
        body += dot(*m[n], n, proposed=True, dy=18)
    # lateral
    ox, oy = 640, 330
    parts, m = lateral_vertebra(ox, oy, k)
    body.append(text(ox + 60, 90, "Lateral", 14, "middle", weight="bold"))
    body += parts
    body += [extension((m[1][0], m[1][1] - 4), (m[1][0], m[1][1] - 40)),
             extension((m[2][0], m[2][1] - 4), (m[2][0], m[2][1] - 40))]
    body += dimension((m[1][0], m[1][1] - 32), (m[2][0], m[2][1] - 32), "upper end-plate depth (1 to 2)",
                      offset=(0, -8))
    body += [extension((m[4][0], m[4][1] + 4), (m[4][0], m[4][1] + 40)),
             extension((m[3][0], m[3][1] + 4), (m[3][0], m[3][1] + 40))]
    body += dimension((m[4][0], m[4][1] + 32), (m[3][0], m[3][1] + 32), "lower end-plate depth (4 to 3)",
                      offset=(0, 20))
    body += dimension((m[2][0] - 18, m[2][1] + 6), (m[3][0] - 18, m[3][1] - 6), "posterior\nheight\n(2 to 3)",
                      offset=(-8, -14), size=10.5, anchor="end")
    body += dimension((m[3][0] + 2, m[5][1]), (m[5][0] - 4, m[5][1]), "canal depth", offset=(0, -8), size=10.5)
    body.append(text(ox - 70, oy - 80, "front", 10.5, "middle", "ink2", style="italic"))
    for n in (1, 2, 3, 4):
        body += dot(*m[n], n, dy=(-9 if n in (1, 2) else 18), dx=(-10 if n in (1, 4) else 10))
    body += dot(*m[5], 5, proposed=True, dx=12, dy=4)
    # the key
    ky = 470
    rows = [
        ("AP, landmarks 1 to 4", "the two ends of the upper and of the lower end plate: the corner detector's "
                                 "four slots, decoded for an AP view (chapter 12, figure 12.4)"),
        ("AP, landmarks 5 and 6", "the medial borders of the two pedicles' rings, whose gap is the canal's width "
                                  "(the interpedicular distance)"),
        ("Lateral, landmarks 1 to 4", "the body's four corners, front and back, top and bottom"),
        ("Lateral, landmark 5", "the spinolaminar point, the canal's back wall where the laminae meet; the canal "
                                "depth runs from it to the line through 2 and 3"),
    ]
    for i, (a, b) in enumerate(rows):
        body.append(text(30, ky + 22 * i, a, 11, weight="bold"))
        body.append(text(230, ky + 22 * i, b, 11, cls="ink2"))
    planes = rec["exact_rule"]["planes"]
    body += paragraph(30, ky + 100, f"Each view shows four of the seven: AP the two widths, the body's height and "
                      f"the canal width; lateral the two depths, the posterior height and the canal depth (bordercall "
                      f"{planes['source']['file']}, which counts the height on both). Every length is a distance "
                      f"between two landmarks, or from a landmark to the line through two others, so no mask and no "
                      f"outline is needed. The drawing follows bordercall's measures figure; the landmark scheme is "
                      f"a proposal (Inferred).", 940, 10.5)[0]
    return svg(W, H, body, "Seven measures from landmarks")


# ----------------------------------------------------------------------------------------
# 36.5 the device
# ----------------------------------------------------------------------------------------
def fig_device(rec):
    det = rec["corner_detector"]
    lat = rec["posterior_latency"]
    noise = rec["measurement_error_3mm"]
    one = rec["exact_rule"]["one_plane_at_nine"]
    budget = rec["frame_budget"]
    W, H = 1000, 760
    body = [text(20, 30, "A measuring device with no segmentation: one landmark pass, then arithmetic", 16,
                 weight="bold"),
            text(20, 50, "Proposed to keep latency low. Only the corner detector and the posterior exist and have "
                 "been timed; everything ochre is to build.", 11.5, cls="ink2")]
    y = 80
    body += frame_icon(20, y, 70, 120, bodies=4)
    body += frame_icon(100, y, 70, 120, bodies=4, sacrum=False)
    body.append(text(95, y + 140, "AP and lateral frames", 11, "middle", "ink2"))
    body.append(text(95, y + 154, "or panoramas", 11, "middle", "ink2"))
    stages = [
        (190, "Landmarks, one pass per frame", "a pose detector with seven landmarks per body: the four corners "
                                               "exist today, three more to train", "proposed"),
        (370, "Lengths in pixels", "distances between landmarks, and from a landmark to a line", "proposed"),
        (550, "Millimetres", "the detector's pixel spacing times the source-to-object over the source-to-image "
                             "distance, or a marker of known size", "proposed"),
        (730, "SchwingCheck", f"the posterior over places: median {lat['median_ms']:.1f} ms, at most "
                              f"{lat['max_ms']:.1f} ms, for a {lat['bodies']}-body field", "rule"),
    ]
    for x, title, words, kind in stages:
        body += box(x, y, 160, 120, title, words, kind, 10.5)
    body.append(arrow(172, y + 60, 188, y + 60, proposed=True))
    for x in (350, 530):
        body.append(arrow(x, y + 60, x + 18, y + 60, proposed=True))
    body.append(arrow(710, y + 60, 728, y + 60, proposed=True))
    body.append(arrow(890, y + 60, 908, y + 60))
    body += paragraph(912, y + 40, "a name and its probability for each body, or \"cannot say\"", 84, 10)[0]
    # the road not taken
    ry = 240
    body.append(text(190, ry, "The road it replaces: SchwingCheck2D's step 2 as the white paper draws it", 12,
                     weight="bold", cls="ink2"))
    for i, (title, words) in enumerate([("One mask per body", "FlexRay labels every pixel of every body on "
                                                              "each panorama"),
                                        ("Outlines", "each body's contour traced from its mask"),
                                        ("Lengths off the outlines", "end plates, walls and canal found on "
                                                                     "the contour")]):
        x = 190 + i * 180
        body += box(x, ry + 12, 160, 76, title, words, "rule", 10)
        if i < 2:
            body.append(arrow(x + 160, ry + 50, x + 178, ry + 50))
    body += paragraph(730, ry + 30, "No time for this road on a C-arm frame is in any record read here. "
                      "bordercall's handoff judges that the time goes to segmentation rather than to naming; "
                      "that is the reason to try the road above.", 250, 10.5)[0]
    # the latency budget
    ay, ax, aw = 390, 300, 600
    body.append(text(20, ay, "Where the time goes, against one frame", 13, weight="bold"))
    scale = aw / 100.0
    bars = [
        ("Four-corner detector, per image", det["ms_per_image"], None,
         f"{det['ms_per_image']:g} ms ({det['model'].split(',')[0]}; hardware not named)", "measured"),
        ("Three more landmarks", None, None, "not built, not timed", "proposed"),
        ("Pixels to millimetres", None, None, "arithmetic, not timed", "proposed"),
        (f"SchwingCheck, {lat['bodies']} bodies", lat["median_ms"], lat["max_ms"],
         f"median {lat['median_ms']:.1f} ms, max {lat['max_ms']:.1f} ms ({lat['calls']} calls, {lat['cpus']} CPUs)",
         "measured"),
    ]
    for i, (name, v, vmax, words, kind) in enumerate(bars):
        yy = ay + 22 + 30 * i
        body.append(text(ax - 10, yy + 13, name, 11, "end"))
        if v is None:
            body.append(f"<rect x='{ax}' y='{yy}' width='60' height='18' fill='none' stroke='{PROPOSED}' "
                        f"stroke-dasharray='2 3' stroke-width='1.3'/>")
            body.append(text(ax + 70, yy + 13, words, 10.5, color=PROPOSED))
        else:
            body.append(f"<rect x='{ax}' y='{yy}' width='{v * scale:.1f}' height='18' fill='{ACCENT}'/>")
            if vmax:
                body.append(line(ax + v * scale, yy + 9, ax + vmax * scale, yy + 9, color=ACCENT, width=1.2))
                body.append(line(ax + vmax * scale, yy + 3, ax + vmax * scale, yy + 15, color=ACCENT, width=1.2))
            body.append(text(ax + (vmax or v) * scale + 8, yy + 13, words, 10.5, cls="ink2"))
    top, bottom = ay + 14, ay + 22 + 30 * len(bars)
    body.append(line(ax, top, ax, bottom, cls="stk2", width=1))
    bx = ax + budget["ms"] * scale
    body.append(line(bx, top - 4, bx, bottom + 4, width=1.4, dash="5 3"))
    body.append(text(bx, top - 8, f"{budget['ms']} ms: {budget['why']}", 10.5, "end", "ink2"))
    for t in (0, 25, 50, 75, 100):
        body.append(text(ax + t * scale, bottom + 16, f"{t}", 10, "middle", "ink2"))
    body.append(text(ax + aw / 2, bottom + 32, "milliseconds", 10.5, "middle", "ink2"))
    body += paragraph(20, bottom + 54, "The bars come from different machines and are not one measured end-to-end "
                      "time; the device's own time is unknown until it is built.", 960, 10.5)[0]
    # what it must reach
    qy = bottom + 92
    body.append(text(20, qy, "What the device must reach for SchwingCheck's guarantee to hold", 13, weight="bold"))
    needs = [
        "Lengths as accurate as the generator assumes, 1 mm of noise. With 3 mm, names given at 0.99 from "
        f"{noise['bodies']} bodies are right {pct(noise['nominal'])} under the nominal rule and "
        f"{pct(noise['honest'], 2)} under the honest rule that widens its spreads.",
        f"Today's corners: {pct(det['pck_01'])} within a tenth of the body's height and {pct(det['pck_02'])} "
        f"within a fifth, on {det['test_instances']} test instances, mostly film; their error in millimetres is "
        "not measured.",
        f"Both views where it can: from nine bodies AP alone names {pct(one['ap'])} exactly, lateral alone "
        f"{pct(one['lateral'])}, both {pct(one['both'])} (synthetic).",
        "A magnification error scales every length by one factor, as patient size does; whether the rule's size "
        "factor absorbs it has not been scored.",
    ]
    yy = qy + 22
    for n in needs:
        body.append(f"<circle cx='28' cy='{yy - 4:.1f}' r='2.5' class='head' fill='{INK}'/>")
        parts, yy = paragraph(40, yy, n, 940, 10.5, cls="ink2")
        body += parts
        yy += 4
    return svg(W, max(H, int(yy) + 10), body, "A segmentation-free measuring device")


# ----------------------------------------------------------------------------------------
# the records the site reads
# ----------------------------------------------------------------------------------------
def figure_record(slug, title, caption, grade, kind, data, notes):
    return {
        "id": f"36/{slug}",
        "title": title,
        "caption": caption,
        "chapter": "36",
        "grade": grade,
        "status": "current",
        "source": {"kind": kind, "artifact": None, "artifact_url": None, "made_by": SCRIPT, "commit": None,
                   "data": data, "run": None, "notes": notes},
        "explore": [{"label": "The script", "href": SCRIPT},
                    {"label": "The recorded numbers", "href": "tools/schwingcheck_records.json"},
                    {"label": "The chapter", "href": CHAPTER}],
        "rerun": {"where": "actions", "command": f"python3 {SCRIPT} docs/textbook/figures/36",
                  "cost": "CPU, under a second", "needs_owner_word": False},
    }


FIGURES = [
    ("schwingnet-stages", fig_schwingnet, "SchwingNet as built: the stages, and which of them learn",
     "The reported stack, left to right: the body detector with four corner keypoints, box repair, the level "
     "encoder and its run head beside the count from the anchor, and their coupling. Below, the proposed tie: "
     "the detector's corners already give five of SchwingCheck's seven measures.",
     "Reported", "diagram", ["docs/textbook/12-detectors-the-architecture-and-the-version-1-training-plan.md"],
     "Drawn from chapter 12's description of the stack as built; the SchwingCheck branch is a proposal."),
    ("schwingcheck-rule", fig_rule, "SchwingCheck: from seven measures to a named field",
     "The bodies in view, every place between C3 and L5 they could occupy, the likelihood of each place from "
     "Panjabi's means and spreads with one shared size factor, and the posterior: a name at 0.99, a region or "
     "border claim, or \"cannot say\". The posterior bars are schematic; the table is the record's.",
     "Reported", "diagram", ["tools/schwingcheck_records.json"],
     "The rule as bordercall's exact.py computes it; numbers copied from bordercall records/exact-2026-10-26/"
     "exact.json at 00f969f, synthetic columns only."),
    ("schwingcheck-pathways", fig_pathways, "Three pathways to a level label on the X-ray",
     "LevelCheck, prior art, whose only classification is the click that labels the CT; SchwingCheck3D, which "
     "checks the CT's labels before surgery and carries them to the X-ray by a centroid fit; SchwingCheck2D, the "
     "default, which names or checks the bodies on AP and lateral panoramas with no CT. Heavy borders mark where "
     "the level is decided.",
     "Inferred", "diagram", ["tools/schwingcheck_records.json", CHAPTER],
     "A design, drawn from the white paper's section Three pathways; LevelCheck's figures are the publications', "
     "SchwingCheck's rates bordercall's synthetic records."),
    ("measures-as-landmarks", fig_landmarks, "The seven measures as distances between landmarks, with no outline",
     "An AP and a lateral lumbar-shaped body with numbered landmarks: the four corners the body detector finds "
     "today, and the pedicles' medial borders and the spinolaminar point no head finds yet. Every measure is a "
     "distance between landmarks, so none needs a mask.",
     "Inferred", "diagram", ["tools/schwingcheck_records.json"],
     "The body follows bordercall's measures figure (exact_slide_figures.py); which plane shows which measure is "
     "bordercall neighbour.py REGIMES; the landmark scheme is a proposal."),
    ("segmentation-free-device", fig_device,
     "A measuring device with no segmentation: one landmark pass, then arithmetic",
     "A proposed reader for SchwingCheck: one keypoint pass per frame, lengths in pixels, millimetres from the "
     "C-arm's geometry, then the posterior. The two timed parts sit far inside one frame's 97 ms; the parts to "
     "build are untimed, and the lengths must reach about 1 mm for the guarantee to hold.",
     "Inferred", "diagram", ["tools/schwingcheck_records.json"],
     "A design with no outcome. The detector's 6.8 ms and corner accuracy are chapter 12's (Reported); the "
     "posterior's time and the 3 mm result are bordercall's records; the budget is docs/memory/"
     "latency-and-the-recorded-sweep.md."),
]


def main(argv):
    rec = json.loads(RECORDS.read_text(encoding="utf-8"))
    out = Path(argv[0]) if argv else ROOT / "docs" / "textbook" / "figures" / "36"
    out.mkdir(parents=True, exist_ok=True)
    for slug, draw, title, caption, grade, kind, data, notes in FIGURES:
        (out / f"{slug}.svg").write_text(draw(rec), encoding="ascii")
        record = figure_record(slug, title, caption, grade, kind, data, notes)
        (out / f"{slug}.json").write_text(json.dumps(record, indent=2, ensure_ascii=True) + "\n", encoding="ascii")
        print(out / f"{slug}.svg")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
