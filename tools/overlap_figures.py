"""Draw chapter 34's figures on the overlap between exposures of a sweep, as SVG.

Two kinds of figure come out of this script. Three are drawn from recorded numbers that
tools/overlap_records.json copies from the artifacts and from spine-program, each with its
source; nothing in them is computed. Two come from a small geometric simulation of a sweep,
written here because the simulator that produced the record (spine-program's
01_carm_level_detection/code/sweep_map.py) needs the grid's renders and keeps no per-spine
result in any repository. The simulation copies that simulator's geometry and rules where it
can (field, pitch, step jitter, the rule for a body being in a frame, the robust pairing rule)
and states every simplification, so its curves are Inferred: they show mechanisms, never a
measured rate.

    python3 tools/overlap_figures.py docs/textbook/figures/34
    python3 tools/overlap_figures.py --table      # the simulation's numbers, as text

Standard library only, so it runs on a GitHub runner in under a minute.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORDS = ROOT / "tools" / "overlap_records.json"

# The simulation's parameters, each from sweep_map.py (spine-program commit 8839881, copied
# there from spinesurg-ct-nnunet 097933a) unless the comment says otherwise.
FIELD_MM = 140.0           # SPAN_PRESETS["ii9"]: a 9-inch intensifier's field at the spine
PITCH_MM = {"sacral": 34.0, "lumbar": 34.0, "thoracic": 27.0}   # PITCH_MM, centre to centre
JITTER = 0.3               # make_stations: the step is span - (overlap + U(-0.3, 0.3)) bodies
IN_FRAME_BAND = 0.3        # cut_frame: a body is in a frame when its centre +/- 0.3 pitch is inside
MIN_STEP = 0.5             # make_stations: no step shorter than half a body
FIRST_FRAME_BELOW = 0.7    # simplification: the first frame's lower edge sits 0.7 pitch below the
                           # sacral anchor's centre (the code puts it 0.2 pitch below the S1 part's box)
TOP_MARGIN = 0.5           # simplification: the sweep stops once the frame's top is half a pitch above
                           # the last body's centre (the code stops at the top of the stack's boxes)
# The column a sweep from the sacrum covers on the abdominopelvic renders, sacrum to about T10.
COLUMN = ["S", "L5", "L4", "L3", "L2", "L1", "T12", "T11", "T10"]
REGION = {"S": "sacral", "T12": "thoracic", "T11": "thoracic", "T10": "thoracic"}
OVERLAPS = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 3.5, 4.0]
TRIALS = 4000

INK, INK2, GRID, BG = "#1b1b1a", "#5c5b57", "#d9d8d3", "#ffffff"
SERIES = ["#2a78d6", "#d0632b", "#1a9c6e", "#8a5cc2", "#b0892a"]
FONT = "font-family='DejaVu Sans, Helvetica, Arial, sans-serif'"
DARK_STYLE = (
    "<style>@media (prefers-color-scheme: dark){"
    ".bg{fill:#151514}.ink{fill:#ecebe6}.ink2{fill:#b5b3ac}.grid{stroke:#3a3936}"
    ".axis{stroke:#b5b3ac}}</style>"
)


# ----------------------------------------------------------------------------------------
# the simulation
# ----------------------------------------------------------------------------------------
def column_centres():
    """Centres of the column's bodies in mm, measured upward from the sacral anchor."""
    centres, at = [], 0.0
    for i, name in enumerate(COLUMN):
        centres.append(at)
        at += PITCH_MM[REGION.get(name, "lumbar")]
    return centres


def commanded_pitch():
    gaps = [PITCH_MM[REGION.get(n, "lumbar")] for n in COLUMN[:-1]]
    return sorted(gaps)[len(gaps) // 2]


def stations(overlap, rng, jitter=JITTER):
    """The radiographer's frames as (bottom, top) in mm, caudal first."""
    centres, p = column_centres(), commanded_pitch()
    bottom = centres[0] - FIRST_FRAME_BELOW * p
    frames = []
    while True:
        frames.append((bottom, bottom + FIELD_MM))
        if bottom + FIELD_MM >= centres[-1] + TOP_MARGIN * p:
            return frames
        step = FIELD_MM - (overlap + rng.uniform(-jitter, jitter)) * p
        bottom += max(step, MIN_STEP * p)


def in_frame(centre, frame, pitch):
    return centre - IN_FRAME_BAND * pitch >= frame[0] and centre + IN_FRAME_BAND * pitch <= frame[1]


def visible(frames):
    """For each frame, the indices of the column's bodies it holds, bottom first."""
    centres, p = column_centres(), commanded_pitch()
    return [[i for i, c in enumerate(centres) if in_frame(c, f, p)] for f in frames]


def robust_block(lower, upper, pairs):
    """sweep_map.link_pair's robust rule: the upper frame's bottom m boxes on the lower frame's
    top m, m chosen by support, a block needing at least max(1, 0.6 m) supported pairs.
    Boxes are indexed top first, as image rows run."""
    nl, nu = len(lower), len(upper)
    best_m, best_score = 0, 0.0
    for m in range(1, min(nl, nu) + 1):
        hit = sum(1 for k in range(m) if (k, nu - m + k) in pairs)
        score = hit - 0.5 * (m - hit)
        if hit >= max(1, 0.6 * m) and score > best_score:
            best_m, best_score = m, score
    return [(k, nu - best_m + k) for k in range(best_m)]


def link(lower, upper):
    """Which detected boxes two frames share, with the image shift taken as found exactly.
    Each argument lists the true body index of each detected box, top first."""
    pairs = {(i, j) for i, a in enumerate(lower) for j, b in enumerate(upper) if a == b}
    return robust_block(lower, upper, pairs)


def chain_nodes(detected):
    """sweep_map.build_chain in the pairwise mode: each node is the set of true bodies its
    observations carry. detected[s] lists frame s's detected bodies, bottom first."""
    tops_first = [list(reversed(d)) for d in detected]
    nodes = [{"truth": {b}} for b in tops_first[0]]
    current = nodes[:]                       # the nodes the latest frame observed, top first
    for s in range(1, len(tops_first)):
        lower, upper = tops_first[s - 1], tops_first[s]
        shared = {j: current[i] for i, j in link(lower, upper) if i < len(current)}
        fresh = []
        for j, body in enumerate(upper):
            if j in shared:
                shared[j]["truth"].add(body)
                fresh.append(shared[j])
            else:
                node = {"truth": {body}}
                nodes.append(node)
                fresh.append(node)
        current = fresh
    return nodes


def repair(held, kept, max_insert=2):
    """Box repair as sweep_map.repair_boxes does it, idealised: a missed body with a detected body
    on each side in the same frame, in a gap of at most two, is put back; a missed body at either end
    of the frame is not, since repair never extrapolates past the ends of a run."""
    found = [i for i, b in enumerate(held) if b in kept]
    if not found:
        return []
    out = set(kept)
    for a, b in zip(found, found[1:]):
        if 1 <= b - a - 1 <= max_insert:
            out.update(held[a + 1:b])
    return [b for b in held if b in out]


def failure(nodes, n_bodies):
    """Why a chain is not complete: a node carrying two bodies, a body entered twice, or a body
    in no node."""
    if any(len(n["truth"]) > 1 for n in nodes):
        return "conflict"
    seen = [next(iter(n["truth"])) for n in nodes]
    if len(seen) != len(set(seen)):
        return "duplicate"
    return "missed" if len(set(seen)) != n_bodies else None


def one_sweep(overlap, miss, link_fail, rng):
    frames = stations(overlap, rng)
    held = visible(frames)
    counts = {}
    for f in held:
        for b in f:
            counts[b] = counts.get(b, 0) + 1
    gap = len(COLUMN) - len(counts)
    once = sum(1 for c in counts.values() if c == 1)
    detected = [repair(f, [b for b in f if rng.random() >= miss]) for f in held]
    links = len(frames) - 1
    broken = any(rng.random() < link_fail for _ in range(links))
    why = "link" if broken else failure(chain_nodes(detected), len(COLUMN))
    return {"ok": why is None, "why": why, "exposures": len(frames), "links": links, "gap": gap,
            "once": once}


def simulate(overlap, miss, link_fail, trials=TRIALS, seed=0):
    rng = random.Random(f"{seed}:{overlap}:{miss}:{link_fail}")
    runs = [one_sweep(overlap, miss, link_fail, rng) for _ in range(trials)]
    n = float(len(runs))
    return {
        "overlap": overlap, "miss": miss, "link_fail": link_fail,
        "complete": sum(r["ok"] for r in runs) / n,
        "exposures": sum(r["exposures"] for r in runs) / n,
        "links": sum(r["links"] for r in runs) / n,
        "gap_any": sum(r["gap"] > 0 for r in runs) / n,
        "once": sum(r["once"] for r in runs) / n,
        "why": {k: sum(r["why"] == k for r in runs) / n for k in ("missed", "duplicate", "conflict", "link")},
    }


# ----------------------------------------------------------------------------------------
# SVG
# ----------------------------------------------------------------------------------------
def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, size=12, anchor="start", cls="ink", weight="normal"):
    return (f"<text x='{x:.1f}' y='{y:.1f}' font-size='{size}' text-anchor='{anchor}' "
            f"class='{cls}' fill='{INK if cls == 'ink' else INK2}' font-weight='{weight}'>{esc(s)}</text>")


def svg(width, height, body, title):
    return (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {width} {height}' width='{width}' "
            f"height='{height}' {FONT} role='img'><title>{esc(title)}</title>{DARK_STYLE}"
            f"<rect class='bg' width='{width}' height='{height}' fill='{BG}'/>" + "".join(body) + "</svg>\n")


class Axes:
    def __init__(self, x, y, w, h, xr, yr):
        self.x, self.y, self.w, self.h, self.xr, self.yr = x, y, w, h, xr, yr

    def px(self, v):
        return self.x + (v - self.xr[0]) / (self.xr[1] - self.xr[0]) * self.w

    def py(self, v):
        return self.y + self.h - (v - self.yr[0]) / (self.yr[1] - self.yr[0]) * self.h

    def frame(self, xticks, yticks, xlabel, ylabel, yfmt="{:g}"):
        out = []
        for t in yticks:
            out.append(f"<line class='grid' x1='{self.x}' x2='{self.x + self.w}' y1='{self.py(t):.1f}' "
                       f"y2='{self.py(t):.1f}' stroke='{GRID}' stroke-width='1'/>")
            out.append(text(self.x - 6, self.py(t) + 4, yfmt.format(t), 11, "end", "ink2"))
        for t in xticks:
            out.append(text(self.px(t), self.y + self.h + 16, f"{t:g}", 11, "middle", "ink2"))
        out.append(f"<line class='axis' x1='{self.x}' x2='{self.x + self.w}' y1='{self.y + self.h}' "
                   f"y2='{self.y + self.h}' stroke='{INK2}'/>")
        out.append(text(self.x + self.w / 2, self.y + self.h + 34, xlabel, 12, "middle", "ink2"))
        out.append(f"<text x='{self.x - 44}' y='{self.y + self.h / 2}' font-size='12' class='ink2' "
                   f"fill='{INK2}' text-anchor='middle' transform='rotate(-90 {self.x - 44} "
                   f"{self.y + self.h / 2})'>{esc(ylabel)}</text>")
        return out

    def line(self, xs, ys, color, dash=None, marker=True, label=None, label_dy=0):
        pts = " ".join(f"{self.px(a):.1f},{self.py(b):.1f}" for a, b in zip(xs, ys))
        d = f" stroke-dasharray='{dash}'" if dash else ""
        out = [f"<polyline points='{pts}' fill='none' stroke='{color}' stroke-width='2'{d}/>"]
        if marker:
            out += [f"<circle cx='{self.px(a):.1f}' cy='{self.py(b):.1f}' r='3.5' fill='{color}'/>"
                    for a, b in zip(xs, ys)]
        if label:
            out.append(f"<text x='{self.px(xs[-1]) + 8:.1f}' y='{self.py(ys[-1]) + 4 + label_dy:.1f}' "
                       f"font-size='11' fill='{color}'>{esc(label)}</text>")
        return out


def legend(x, y, items):
    out = []
    for k, (label, color, dash) in enumerate(items):
        yy = y + 18 * k
        d = f" stroke-dasharray='{dash}'" if dash else ""
        out.append(f"<line x1='{x}' x2='{x + 22}' y1='{yy}' y2='{yy}' stroke='{color}' stroke-width='2'{d}/>")
        out.append(text(x + 28, yy + 4, label, 11, "start", "ink"))
    return out


# ----------------------------------------------------------------------------------------
# the figures
# ----------------------------------------------------------------------------------------
def fig_records(rec):
    ax = Axes(80, 60, 520, 300, (0.25, 4.25), (75, 100))
    body = [text(20, 28, "Chain complete against overlap: three recorded sets (each a record, not a final value)",
                 14, weight="bold")]
    body += ax.frame([0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4], [75, 80, 85, 90, 95, 100],
                     "overlap between consecutive exposures (vertebral bodies)", "chains complete (%)")
    body.append(f"<rect x='{ax.px(1.85):.1f}' y='{ax.y}' width='{ax.px(2.15) - ax.px(1.85):.1f}' "
                f"height='{ax.h}' fill='{SERIES[0]}' opacity='0.08'/>")
    items = []
    for k, s in enumerate(rec["chain_complete_by_overlap"]):
        dash = None if k == 0 else ("6 4" if k == 1 else "2 3")
        body += ax.line(s["overlap"], s["percent"], SERIES[k], dash)
        items.append((s["label"], SERIES[k], dash))
    body += legend(630, 90, items)
    body.append(text(630, 160, "Shaded: two bodies, the protocol.", 11, cls="ink2"))
    body.append(text(630, 178, "Every set peaks at two and is", 11, cls="ink2"))
    body.append(text(630, 196, "lowest at four or at half a body.", 11, cls="ink2"))
    body.append(text(20, 410, "Sources: tools/overlap_records.json, which names the artifact or file of each set.",
                     11, cls="ink2"))
    return svg(900, 425, body, "Chain complete against overlap, recorded sets")


def fig_exposures(rec, sim):
    ax = Axes(80, 60, 520, 300, (0.25, 4.25), (0, 12))
    body = [text(20, 28, "Exposures per sweep against overlap: records, and the simulation's geometry",
                 14, weight="bold")]
    body += ax.frame([0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4], [0, 2, 4, 6, 8, 10, 12],
                     "overlap between consecutive exposures (vertebral bodies)", "exposures per sweep")
    items = []
    for k, s in enumerate(rec["exposures_by_overlap"]):
        body += ax.line(s["overlap"], s["exposures"], SERIES[k], None if k == 0 else "6 4")
        items.append((s["label"] + " (record)", SERIES[k], None if k == 0 else "6 4"))
    xs = [r["overlap"] for r in sim]
    body += ax.line(xs, [r["exposures"] for r in sim], SERIES[3], "2 3", marker=False)
    items.append(("simulation, sacrum to T10 (Inferred)", SERIES[3], "2 3"))
    body += legend(630, 90, items)
    body.append(text(630, 180, "Each exposure after the first adds", 11, cls="ink2"))
    body.append(text(630, 198, "one link that can be joined wrongly.", 11, cls="ink2"))
    body.append(text(20, 410, "Records: tools/overlap_records.json. Simulation: tools/overlap_figures.py, "
                     "9-inch field, step jittered +/- 0.3 body.", 11, cls="ink2"))
    return svg(900, 425, body, "Exposures per sweep against overlap")


def fig_simulation(grid):
    body = [text(20, 28, "A sweep simulated: what goes wrong below two bodies and above (Inferred, not measured)",
                 14, weight="bold")]
    left = Axes(80, 70, 330, 280, (0.25, 4.25), (0, 100))
    body.append(text(80, 56, "Below two: bodies that fall between frames or are seen once", 12, cls="ink2"))
    body += left.frame([0.5, 1, 2, 3, 4], [0, 20, 40, 60, 80, 100],
                       "overlap (bodies)", "chains complete (%)")
    items = []
    for k, miss in enumerate([0.0, 0.024, 0.094]):
        rows = [r for r in grid if r["miss"] == miss and r["link_fail"] == 0.0]
        body += left.line([r["overlap"] for r in rows], [100 * r["complete"] for r in rows], SERIES[k],
                          marker=False)
        items.append((f"miss {100 * miss:.1f}% per body, no link error", SERIES[k], None))
    right = Axes(530, 70, 330, 280, (0.25, 4.25), (0, 100))
    body.append(text(530, 56, "Above two: every extra exposure is one more link", 12, cls="ink2"))
    body += right.frame([0.5, 1, 2, 3, 4], [0, 20, 40, 60, 80, 100],
                        "overlap (bodies)", "chains complete (%)")
    for k, eps in enumerate([0.0, 0.01, 0.02, 0.04]):
        rows = [r for r in grid if r["miss"] == 0.024 and r["link_fail"] == eps]
        body += right.line([r["overlap"] for r in rows], [100 * r["complete"] for r in rows], SERIES[k],
                           "5 3" if k else None, marker=False)
        items.append((f"miss 2.4%, each link fails {100 * eps:g}%", SERIES[k], "5 3" if k else None))
    body += legend(80, 410, items[:3])
    body += legend(530, 410, items[3:])
    notes = [
        "Field 140 mm, pitch 34 mm lumbar and 27 mm thoracic, sacrum to T10, step jittered +/- 0.3 body; the in-frame",
        "rule, box repair and the robust pairing rule follow sweep_map.py. The image shift is taken as found exactly, so a",
        "link error enters only through the stated per-link rate. Miss rates: 2.4% on held-out film and 9.4% = 1 - 0.906",
        f"on a held-out C-arm, both records. {TRIALS} simulated sweeps per point.",
    ]
    for k, line in enumerate(notes):
        body.append(text(20, 500 + 16 * k, line, 11, cls="ink2"))
    return svg(900, 570, body, "Simulated chain completion against overlap")


def fig_geometry():
    """One sweep at each overlap with the commanded step and no jitter: the frames, which bodies
    each frame holds, and the bodies a single missed box would cost."""
    rng = random.Random(0)
    centres, p = column_centres(), commanded_pitch()
    scale = 1.6
    x0 = 120
    body = [text(20, 28, "The geometry at half, one, two and four bodies of overlap (from the simulation, step "
                 "exact)", 14, weight="bold"),
            text(20, 48, "Bodies left to right from the sacral anchor. A frame holds a body when the body's middle "
                 "0.6 pitch is inside it, the simulator's rule.", 11, cls="ink2")]
    y = 80
    for overlap in (0.5, 1.0, 2.0, 4.0):
        frames = stations(overlap, rng, jitter=0.0)
        held = visible(frames)
        counts = {}
        for f in held:
            for b in f:
                counts[b] = counts.get(b, 0) + 1
        body.append(text(20, y + 14, f"{overlap:g} {'body' if overlap <= 1 else 'bodies'}", 13, weight="bold"))
        body.append(text(20, y + 30, f"{len(frames)} exposures", 11, cls="ink2"))
        body.append(text(20, y + 44, f"{len(frames) - 1} links", 11, cls="ink2"))
        for k, f in enumerate(frames):
            fy = y + 4 + 11 * k
            body.append(f"<rect x='{x0 + scale * (f[0] + 30):.1f}' y='{fy}' width='{scale * FIELD_MM:.1f}' "
                        f"height='8' fill='{SERIES[k % 4]}' opacity='0.35'/>")
        by = y + 12 + 11 * len(frames)
        for i, c in enumerate(centres):
            n = counts.get(i, 0)
            color = "#c23b22" if n == 0 else ("#e9c46a" if n == 1 else "#7fb3e6")
            bx = x0 + scale * (c + 30) - scale * 13
            body.append(f"<rect x='{bx:.1f}' y='{by}' width='{scale * 26:.1f}' height='22' rx='3' fill='{color}' "
                        f"stroke='{INK2}' stroke-width='0.8'/>")
            body.append(text(bx + scale * 13, by + 15, COLUMN[i], 10, "middle"))
        once = sum(1 for v in counts.values() if v == 1)
        gap = len(COLUMN) - len(counts)
        shared = [len(set(a) & set(b)) for a, b in zip(held, held[1:])]
        note = (f"shared per link {shared}; seen once {once}; in no frame {gap}")
        body.append(text(x0, by + 40, note, 11, cls="ink2"))
        y = by + 62
    body += [f"<rect x='120' y='{y}' width='14' height='12' fill='#c23b22'/>",
             text(140, y + 10, "in no frame: lost from the chain, every count above it one short", 11),
             f"<rect x='120' y='{y + 18}' width='14' height='12' fill='#e9c46a'/>",
             text(140, y + 28, "seen once: one missed box there loses the body the same way", 11),
             f"<rect x='120' y='{y + 36}' width='14' height='12' fill='#7fb3e6'/>",
             text(140, y + 46, "seen twice or more: a missed box is covered by the other frame, unless it breaks the pairing of a long shared block", 11)]
    return svg(900, y + 64, body, "Overlap geometry")


def fig_counting(rec):
    arms = rec["counting_exact_two_versus_three"]["arms"]
    body = [text(20, 28, "Counting with the annotation's boxes: two bodies of overlap against three (a record)",
                 14, weight="bold"),
            text(20, 48, "Exact of reached walks; a full bar is 100 percent. Wrong walks in brackets.", 11,
                 cls="ink2")]
    x0, w = 380, 380
    lo = 0.99
    y = 70
    for a in arms:
        body.append(text(20, y + 14, f"{a['arm']} ({a['spines']})", 11))
        for k, key in enumerate(("two", "three")):
            v = a[key]
            yy = y + 2 + 14 * k
            if v is None:
                body.append(text(x0, yy + 9, f"{key} bodies: not in the record", 10, cls="ink2"))
                continue
            frac = max(0.0, (v["exact"] - lo) / (1 - lo))
            body.append(f"<rect x='{x0}' y='{yy}' width='{w * frac:.1f}' height='11' fill='{SERIES[k]}'/>")
            body.append(text(x0 + w + 8, yy + 9, f"{key}: {100 * v['exact']:.2f}% of {v['walks']} "
                             f"({v['wrong']})", 10, cls="ink2"))
        y += 40
    body.append(f"<line x1='{x0}' x2='{x0}' y1='66' y2='{y - 6}' stroke='{INK2}'/>")
    body.append(text(x0, y + 8, "99%", 10, "middle", "ink2"))
    body.append(text(x0 + w, y + 8, "100%", 10, "middle", "ink2"))
    body.append(text(20, y + 30, "Source: spine-program 01_carm_level_detection/docs/COUNTING_EVIDENCE.md, "
                     "generated from result files on the grid.", 11, cls="ink2"))
    return svg(1000, y + 44, body, "Counting exactness at two and three bodies of overlap")


def simulation_grid():
    grid = []
    for overlap in OVERLAPS:
        for miss in (0.0, 0.024, 0.094):
            grid.append(simulate(overlap, miss, 0.0))
        for eps in (0.01, 0.02, 0.04):
            grid.append(simulate(overlap, 0.024, eps))
    return grid


def main(argv):
    rec = json.loads(RECORDS.read_text())
    grid = simulation_grid()
    if argv[:1] == ["--table"]:
        print("overlap miss link_fail complete exposures links P(body in no frame) bodies_seen_once")
        for r in grid:
            print(f"{r['overlap']:>5} {r['miss']:.3f} {r['link_fail']:.2f} {100 * r['complete']:6.1f} "
                  f"{r['exposures']:5.2f} {r['links']:5.2f} {100 * r['gap_any']:5.1f} {r['once']:5.2f}  "
                  + " ".join(f"{k} {100 * v:.1f}" for k, v in r["why"].items()))
        return 0
    out = Path(argv[0]) if argv else ROOT / "docs" / "textbook" / "figures" / "34"
    out.mkdir(parents=True, exist_ok=True)
    base = [r for r in grid if r["miss"] == 0.0 and r["link_fail"] == 0.0]
    figures = {
        "overlap-chain-completion-records.svg": fig_records(rec),
        "overlap-exposures.svg": fig_exposures(rec, base),
        "overlap-simulation.svg": fig_simulation(grid),
        "overlap-geometry.svg": fig_geometry(),
        "counting-two-versus-three-bodies.svg": fig_counting(rec),
    }
    for name, content in figures.items():
        (out / name).write_text(content, encoding="ascii")
        print(out / name)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
