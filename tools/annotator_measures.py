#!/usr/bin/env python3
"""The measures the annotators' landmark schemes make, what an X-ray's projection does to each, and how much each
tells the Bayes rule (docs/research/annotator-landmarks/measures.md).

The owner, 1 November 2026: the landmark net should at least place what annotators have found useful (DeepFluoro's
points, the corners many X-ray groups mark), carried to the CT and used for the Bayes rule's measurements, the better
where they agree with Panjabi. This tool answers three questions of the measures those schemes make:

- Which of them the oracle's eighteen points (tools/qaloop_gates.py LANDMARKS) make, and how: MEASURES below, each
  a function of a column of points (levels, 18, D) that reads alike in three dimensions and in two.
- What a real frame's projection does to each (`project`): the real pairs' 3-D landmarks (tools/realx_pairs.py,
  read with qaloop_samples.load_pair) projected through each frame's P, each measure read in pixels beside its 3-D
  value: a ratio or an angle against its 3-D value, a length against its 3-D length times the frame's magnification
  at the length's middle, binned by how far the ray to the vertebra lies from the vertebra's own anteroposterior or
  lateral axis, which its own points give. The pairs keep only frames within 15 degrees of either view by the
  export's angle, so each person's other frames, which the same export registered the same way, are read from its
  metadata too, to reach the oblique views; the persons each set holds out are in no pair and are never read.
- How much each tells the Bayes rule (`gold`, then `census`): per-level means, SDs and counts of the engine's rows
  on the gold tier, one study a person, aggregates alone, ranked by bordercall's census (schwingcheck/census.py),
  read here as a library from a clone and never changed, as read on the CT and as read on an X-ray, each measure's
  error widened by what the projection test measured for it.

    python tools/annotator_measures.py project --pairs <realx/deepfluoro> <realx/cobra> --out projection.json
    python tools/annotator_measures.py gold --rows <morphometry/enhance/rows.csv> --persons <persons.csv> \
        --verdicts <morphometry/enhance/verdicts.csv> --out <dir>
    python tools/annotator_measures.py census --bordercall <clone at the commit the note names> --gold <dir> \
        --projection projection.json --out census.json
    python tools/annotator_measures.py report --projection projection.json --census census.json

The census's default of 2,000 bodies a level is the one the note's numbers were drawn with, and the record writes
down the clone's commit.

What the projection test is: fixed 3-D points (the oracle's) carried through each frame's P, so it measures what the
view does to those points. A reader marks an outline's extreme on the image, which moves round the rim as the view
turns, so off the view a reader's width is not the fixed points' (the note's section 2 says by how much for an
elliptic plate); within the view's tolerance the two differ by little.

Nothing here constructs a landmark: every point is the oracle's, as the owner's rule of 29 October 2026 asks, and a
measure the eighteen points cannot make (the six-point heights at the plates' surfaces, the concavity, the wedge angle,
the pelvic angles) is read from the engine's own rows instead, and only in the census.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(1, str(ROOT / "tools"))

import argparse  # noqa: E402
import csv  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import subprocess  # noqa: E402
import warnings  # noqa: E402
from contextlib import contextmanager  # noqa: E402
from dataclasses import dataclass  # noqa: E402

import numpy as np  # noqa: E402

import qaloop_samples as S  # noqa: E402

G = S.G
LUMBAR = ("T12", "L1", "L2", "L3", "L4", "L5")       # the levels a lumbar frame shows, the real pairs' levels
BINS = (0.0, 5.0, 10.0, 15.0, 25.0, 35.0, 60.0)       # degrees off the vertebra's own anteroposterior or lateral view
TOLERANCE = 15.0                                      # the real arm's view tolerance (realx_pairs VIEW_TOLERANCE_DEG)
PAIR_SIZE = 512                                       # the pairs' frames, at the loop's size
# What "survives projection" means, stated before the test ran: within TOLERANCE of the view a measure is read in,
# a ratio's 2-D value within the census's ratio error of its 3-D value (0.04) at the median and twice that at the
# 90th percentile; an angle's within the census's 3 degrees and 6; a length's, divided by the magnification at its
# middle, within 5 per cent of its 3-D length at the median and 10 at the 90th percentile.
BARS = {"ratio": (0.04, 0.08), "angle": (3.0, 6.0), "length": (0.05, 0.10)}
# DeepFluoro's read vertebrae lie a median 32 degrees tilted against the scanner's long axis by their own frames,
# which the test cannot tell from a frame the oracle tilted (its column line runs through the neighbours' centroids on
# a CT that cuts the lumbar spine), so their angles off the view are in doubt: their readings are tabled apart
# (bins_by_source, by_source, bins_all) and left out of the binned agreement, the verdicts and the census's errors.
ANGLES_IN_DOUBT = ("deepfluoro",)
# Twelve thoracic and five lumbar: only in such a column are the six names T12 to L5 the bodies they mean, with L5
# on the sacrum, so the gold table is built from these persons alone (bordercall's count call in verdicts.csv).
TYPICAL_CALL = "T12L5"
MIN_CELL = 5                                          # a gold table cell needs this many persons
MIN_R = 30                                            # a within-level correlation needs this many


# ---------------------------------------------------------------- terms: functions of a column of points

class Term:
    """A function of a column of points (levels, 18, D), D 3 or 2, giving one value (or one point) a level, with the
    points it uses as (level offset, landmark name): offset 0 is the level itself, 1 the one below, -1 the one above."""

    def __init__(self, fn, uses):
        self.fn, self.uses = fn, frozenset(uses)

    def __call__(self, col):
        return self.fn(np.asarray(col, float))


def shift(values, offset):
    """values (levels, ...) moved so that row i holds row i + offset, NaN past either end."""
    out = np.full(values.shape, np.nan)
    n = len(values)
    if offset == 0:
        return values.copy()
    if offset > 0 and offset < n:
        out[:n - offset] = values[offset:]
    elif offset < 0 and -offset < n:
        out[-offset:] = values[:n + offset]
    return out


def point(name, offset=0):
    i = G.INDEX[name]
    return Term(lambda col: shift(col[:, i, :], offset), {(offset, name)})


def length(a, b):
    return Term(lambda col: np.linalg.norm(a(col) - b(col), axis=-1), a.uses | b.uses)


def middle(a, b):
    return Term(lambda col: 0.5 * (a(col) + b(col)), a.uses | b.uses)


def ratio(f, g):
    def fn(col):
        num, den = f(col), g(col)
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(den > 0, num / den, np.nan)
    return Term(fn, f.uses | g.uses)


def mean_of(f, g):
    return Term(lambda col: 0.5 * (f(col) + g(col)), f.uses | g.uses)


def moved(f, offset):
    """A level's term taken at the level offset away (1 the one below)."""
    return Term(lambda col: shift(f(col), offset), {(o + offset, n) for o, n in f.uses})


def chord(name):
    """A spec's chord (grid/autoanatomist/autoanatomist/specs.py) between its two named ends."""
    from_, to = {"endplate": ("right", "left"), "endplate_lower": ("right", "left"),
                 "endplate_depth": ("posterior", "anterior"), "endplate_lower_depth": ("posterior", "anterior"),
                 "h_post": ("superior", "inferior"), "canal_w": ("right", "left"), "canal_ap": ("posterior", "anterior"),
                 "tp_span": ("right", "left"), "spinous_length": ("canal", "tip")}[name]
    return length(point(f"{name}.{from_}"), point(f"{name}.{to}"))


EPWU, EPWL, EPDU, EPDL = chord("endplate"), chord("endplate_lower"), chord("endplate_depth"), chord("endplate_lower_depth")
VBHP, SCW, SCD, TPW, SPL = chord("h_post"), chord("canal_w"), chord("canal_ap"), chord("tp_span"), chord("spinous_length")
# The corner heights a lateral reader takes: between the plates' anterior ends, their posterior ends, and the middles
# of the two depth chords. The oracle sets all four points of a plate at its slab's median height in the vertebra's
# frame (oracle.body_traces), so these are slab-centre heights, not the six-point morphometry's, which the engine
# reads as h_ant, h_post_inset and h_mid; the projection test reads them for what projection does to a vertical length.
HA = length(point("endplate_depth.anterior"), point("endplate_lower_depth.anterior"))
HP = length(point("endplate_depth.posterior"), point("endplate_lower_depth.posterior"))
HM = length(middle(point("endplate_depth.posterior"), point("endplate_depth.anterior")),
            middle(point("endplate_lower_depth.posterior"), point("endplate_lower_depth.anterior")))
# The lateral heights an anteroposterior reader takes, between the plates' right ends and their left ends.
HLR = length(point("endplate.right"), point("endplate_lower.right"))
HLL = length(point("endplate.left"), point("endplate_lower.left"))
HL = mean_of(HLR, HLL)


def crush(f):
    """A level's value over the mean of its neighbours', the form of quantitative morphometry's crush ratio (Eastell
    1991, McCloskey 1993: the posterior height against what the adjacent vertebrae's predict)."""
    return ratio(f, mean_of(moved(f, -1), moved(f, 1)))


# ---------------------------------------------------------------- angles

def axes(col):
    """Each vertebra's frame from its own points, (levels, 3) each: z up the posterior wall (h_post), y from the
    canal toward the body along the upper depth chord, x = y cross z, to the patient's right; NaN where a chord is
    missing."""
    ez = col[:, G.INDEX["h_post.superior"]] - col[:, G.INDEX["h_post.inferior"]]
    ez = ez / np.linalg.norm(ez, axis=-1, keepdims=True)
    y0 = col[:, G.INDEX["endplate_depth.anterior"]] - col[:, G.INDEX["endplate_depth.posterior"]]
    ey = y0 - np.sum(y0 * ez, axis=-1, keepdims=True) * ez
    ey = ey / np.linalg.norm(ey, axis=-1, keepdims=True)
    return np.cross(ey, ez), ey, ez


def signed_in_plane(u, v, n):
    """The angle from u to v in degrees, both taken into the plane square to n, positive about n."""
    u = u - np.sum(u * n, axis=-1, keepdims=True) * n
    v = v - np.sum(v * n, axis=-1, keepdims=True) * n
    return np.degrees(np.arctan2(np.sum(np.cross(u, v) * n, axis=-1), np.sum(u * v, axis=-1)))


def signed_2d(u, v):
    return np.degrees(np.arctan2(u[..., 0] * v[..., 1] - u[..., 1] * v[..., 0], np.sum(u * v, axis=-1)))


@dataclass(frozen=True)
class Segmental:
    """The angle between a level's chord and the same chord of the level below, in the level's sagittal (normal x)
    or coronal (normal y) plane; in 2-D the same angle on the image, its sign set by a reference pair of the level's
    own chords whose 3-D sign is known, since an image may show a plane from either side."""
    chord: tuple
    normal: int            # 0 for x (sagittal), 1 for y (coronal)
    reference: tuple       # two chords of the level whose signed angle about the normal fixes the image's side

    def vector(self, col, ends, offset=0):
        a, b = point(ends[0], offset)(col), point(ends[1], offset)(col)
        return b - a

    def uses(self):
        names = set(self.chord) | set(self.reference[0]) | set(self.reference[1])
        return frozenset({(0, n) for n in names} | {(1, n) for n in self.chord})

    def value3(self, col3):
        n = axes(col3)[self.normal]
        return signed_in_plane(self.vector(col3, self.chord), self.vector(col3, self.chord, 1), n)

    def value2(self, col3, col2):
        n = axes(col3)[self.normal]
        ref3 = np.sign(signed_in_plane(self.vector(col3, self.reference[0]), self.vector(col3, self.reference[1]), n))
        ref2 = np.sign(signed_2d(self.vector(col2, self.reference[0]), self.vector(col2, self.reference[1])))
        return ref3 * ref2 * signed_2d(self.vector(col2, self.chord), self.vector(col2, self.chord, 1))


DEPTH_ENDS = ("endplate_depth.posterior", "endplate_depth.anterior")
WIDTH_ENDS = ("endplate.left", "endplate.right")
POST_ENDS = ("h_post.inferior", "h_post.superior")
SEG_SAG = Segmental(DEPTH_ENDS, 0, (DEPTH_ENDS, POST_ENDS))
SEG_COR = Segmental(WIDTH_ENDS, 1, (WIDTH_ENDS, POST_ENDS))


# ---------------------------------------------------------------- the measures

@dataclass(frozen=True)
class Measure:
    """One measure of an annotator scheme as the eighteen points make it: a short name, its kind, the view its
    readers take it in (ap or lat), the term (or the segmental angle) that makes it, and the scheme it is from."""
    name: str
    kind: str
    view: str
    term: object
    scheme: str

    @property
    def uses(self):
        return self.term.uses() if isinstance(self.term, Segmental) else self.term.uses

    def value3(self, col3):
        return self.term.value3(col3) if isinstance(self.term, Segmental) else self.term(col3)

    def value2(self, col3, col2):
        return self.term.value2(col3, col2) if isinstance(self.term, Segmental) else self.term(col2)


MEASURES = [
    Measure("EPWu", "length", "ap", EPWU, "Panjabi; the anteroposterior corners"),
    Measure("EPWl", "length", "ap", EPWL, "Panjabi; the anteroposterior corners"),
    Measure("EPDu", "length", "lat", EPDU, "Panjabi; the lateral corners"),
    Measure("EPDl", "length", "lat", EPDL, "Panjabi; the lateral corners"),
    Measure("VBHp", "length", "lat", VBHP, "Panjabi's posterior wall height"),
    Measure("SCW", "length", "ap", SCW, "Panjabi; the interpedicular distance of the AP film"),
    Measure("SCD", "length", "lat", SCD, "Panjabi; the canal's depth of the lateral film"),
    Measure("TPW", "length", "ap", TPW, "Panjabi"),
    Measure("SPL", "length", "lat", SPL, "Panjabi"),
    Measure("ha", "length", "lat", HA, "six-point morphometry (Eastell, Black, McCloskey): anterior height, plates' ends"),
    Measure("hp", "length", "lat", HP, "six-point morphometry: posterior height, from the plates' ends"),
    Measure("hm", "length", "lat", HM, "six-point morphometry: middle height, from the chords' middles"),
    Measure("hl", "length", "ap", HL, "the coronal corners' lateral heights, right and left averaged"),
    Measure("ha/hp", "ratio", "lat", ratio(HA, HP), "Eastell's wedge ratio"),
    Measure("hm/hp", "ratio", "lat", ratio(HM, HP), "Eastell's biconcavity ratio"),
    Measure("crush", "ratio", "lat", crush(VBHP), "the crush ratio's form on Panjabi's VBHp, the wall over its neighbours'"),
    Measure("EPDu/VBHp", "ratio", "lat", ratio(EPDU, VBHP), "the body's depth over its height"),
    Measure("EPDl/EPDu", "ratio", "lat", ratio(EPDL, EPDU), "the depth's taper from the upper plate to the lower"),
    Measure("SCD/EPDu", "ratio", "lat", ratio(SCD, EPDU), "the canal over the body, Torg and Pavlov's form"),
    Measure("SPL/EPDu", "ratio", "lat", ratio(SPL, EPDU), "the spinous process over the body"),
    Measure("VBHp/below", "ratio", "lat", ratio(VBHP, moved(VBHP, 1)), "the posterior height over the next level's"),
    Measure("EPDu/below", "ratio", "lat", ratio(EPDU, moved(EPDU, 1)), "the depth over the next level's"),
    Measure("EPWl/EPWu", "ratio", "ap", ratio(EPWL, EPWU), "the width's taper from the upper plate to the lower"),
    Measure("SCW/EPWu", "ratio", "ap", ratio(SCW, EPWU), "the canal's width over the body's"),
    Measure("TPW/EPWu", "ratio", "ap", ratio(TPW, EPWU), "the transverse span over the body's width"),
    Measure("hl/EPWu", "ratio", "ap", ratio(HL, EPWU), "the body's height over its width, as an AP film shows it"),
    Measure("hlR/hlL", "ratio", "ap", ratio(HLR, HLL), "the coronal wedge, right height over left"),
    Measure("EPWu/below", "ratio", "ap", ratio(EPWU, moved(EPWU, 1)), "the width over the next level's"),
    Measure("TPW/below", "ratio", "ap", ratio(TPW, moved(TPW, 1)), "the transverse span over the next level's"),
    Measure("seg_sag", "angle", "lat", SEG_SAG, "the segmental angle, upper plate to the next upper plate, sagittal"),
    Measure("seg_cor", "angle", "ap", SEG_COR, "the segmental angle, upper plate to the next upper plate, coronal"),
]
BY_NAME = {m.name: m for m in MEASURES}


def construction_checks(col3):
    """What the oracle's construction gives the eighteen points, per vertebra: how far apart along the vertebra's own
    z a plate's four points lie (each plate's points share its slab's median height), the sagittal angle between the
    upper and lower depth chords and the coronal angle between the width chords (each chord runs along its frame
    axis), all of which a wedge read from these points would need to be other than zero."""
    ex, ey, ez = axes(col3)
    out = {}
    for name, plate in (("upper", "endplate"), ("lower", "endplate_lower")):
        z = np.stack([np.sum(col3[:, G.INDEX[f"{plate}{part}"]] * ez, axis=-1)
                      for part in (".right", ".left", "_depth.posterior", "_depth.anterior")], axis=-1)
        out[f"{name}_plate_z_spread_mm"] = np.nanmax(z, axis=-1) - np.nanmin(z, axis=-1)
    up = col3[:, G.INDEX["endplate_depth.anterior"]] - col3[:, G.INDEX["endplate_depth.posterior"]]
    low = col3[:, G.INDEX["endplate_lower_depth.anterior"]] - col3[:, G.INDEX["endplate_lower_depth.posterior"]]
    out["depth_chords_angle_deg"] = signed_in_plane(up, low, ex)
    upw = col3[:, G.INDEX["endplate.right"]] - col3[:, G.INDEX["endplate.left"]]
    loww = col3[:, G.INDEX["endplate_lower.right"]] - col3[:, G.INDEX["endplate_lower.left"]]
    out["width_chords_angle_deg"] = signed_in_plane(upw, loww, ey)
    return out


def frame_tilts(col3):
    """Per vertebra, how its own frame lies in the CT's: degrees between its z and the scanner's long axis, and
    between its x and the scanner's left-right axis. A large tilt is a column that lies bent in the scanner, or a
    frame the oracle set along a line through neighbours that do not follow the column."""
    ex, _, ez = axes(col3)
    with np.errstate(invalid="ignore"):
        tilt = np.degrees(np.arccos(np.clip(np.abs(ez[:, 2]), 0.0, 1.0)))
        turn = np.degrees(np.arccos(np.clip(np.abs(ex[:, 0]), 0.0, 1.0)))
    return {"column_tilt_deg": tilt, "left_right_turn_deg": turn}


# ---------------------------------------------------------------- a frame's geometry

def camera(P):
    """The source's position, the depth of world points along the principal axis in millimetres, and the focal
    length in pixels (the geometric mean over the detector's two axes) of P, set so that depth is positive."""
    P = np.asarray(P, float)
    P = P / np.linalg.norm(P[2, :3])
    M = P[:, :3]
    source = -np.linalg.solve(M, P[:, 3])
    r3 = M[2]
    e1 = np.cross(r3, [1.0, 0.0, 0.0] if abs(r3[0]) < 0.9 else [0.0, 1.0, 0.0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(r3, e1)
    focal = math.sqrt(abs(np.linalg.det(M[:2] @ np.column_stack([e1, e2]))))
    return source, P, focal


def depth(Pn, X):
    return np.asarray(X, float) @ Pn[2, :3] + Pn[2, 3]


def view_angles(col3, source):
    """Per level, the ray from the source to the vertebra's centre against the vertebra's own axes: degrees off its
    true anteroposterior view (the ray along y) and off its true lateral view (the ray along x)."""
    ex, ey, _ = axes(col3)
    centre = np.nanmean(col3, axis=1)
    ray = centre - source
    ray = ray / np.linalg.norm(ray, axis=-1, keepdims=True)
    with np.errstate(invalid="ignore"):
        off_ap = np.degrees(np.arccos(np.clip(np.abs(np.sum(ray * ey, axis=-1)), 0.0, 1.0)))
        off_lat = np.degrees(np.arccos(np.clip(np.abs(np.sum(ray * ex, axis=-1)), 0.0, 1.0)))
    return off_ap, off_lat


def seen(mask, uses):
    """Per level, whether every point a measure uses lies in the frame (mask (levels, 18))."""
    ok = np.ones(len(mask), bool)
    for offset, name in uses:
        col = shift(mask[:, G.INDEX[name]].astype(float), offset)
        ok &= col == 1.0
    return ok


def middle_depth(measure, col3, Pn):
    """Per level, the depth of the middle of the points a measure uses."""
    pts = [shift(col3[:, G.INDEX[name]], offset) for offset, name in measure.uses]
    return depth(Pn, np.nanmean(np.stack(pts), axis=0))


def frame_rows(col3, levels, P, size, person, source_name, kind):
    """Every measure at every level of one frame: the 3-D and 2-D values, the vertebra's angles off its two views,
    the magnification at the measure's middle and whether all its points lie in the frame."""
    source, Pn, focal = camera(P)
    col2 = G.project(Pn, col3)
    mask = S.in_frame(col2, size, margin=0.0)
    off_ap, off_lat = view_angles(col3, source)
    rows = []
    for k, m in enumerate(MEASURES):
        v3, v2 = m.value3(col3), m.value2(col3, col2)
        mag = focal / middle_depth(m, col3, Pn)
        inside = seen(mask, m.uses)
        for i in range(len(col3)):
            if np.isfinite(v3[i]) and np.isfinite(v2[i]) and np.isfinite(off_ap[i]):
                rows.append((k, levels[i], person, source_name, kind, off_ap[i], off_lat[i], mag[i], bool(inside[i]), v3[i],
                             v2[i], float(size)))
    return rows


# ---------------------------------------------------------------- the projection test

def export_frames(export, case):
    """The export's square frames of one case, each (frame id, P in its own pixels, its side), and the count of
    those left out for not being square: as realx_pairs leaves them out (COBRA's collimated bands), since the
    in-frame test takes one side for both."""
    out, not_square = [], 0
    for path in sorted((Path(export) / "meta").glob(f"{case}_*.json")):
        meta = json.loads(path.read_text())
        if meta.get("case") != case:
            continue
        pose = meta.get("pose") or {}
        size = meta.get("size") or meta.get("image_size")
        if "K" not in pose or "ext" not in pose or not size:
            continue
        if len(set(size)) != 1:
            not_square += 1
            continue
        ext = np.asarray(pose["ext"], float)
        out.append((meta["frame"], np.asarray(pose["K"], float) @ ext[:3, :4], float(size[0])))
    return out, not_square


def orient(P, col3):
    """P with the sign that puts the points in front of the source (realx_pairs.orient)."""
    pts = col3.reshape(-1, 3)
    pts = pts[np.isfinite(pts).all(axis=1)]
    w = pts @ P[2, :3] + P[2, 3]
    return -P if len(w) and np.median(w) < 0 else P


def person_rows(folder, entry, export):
    """One person's rows: its pair's frames through their P (kind pair), its other export frames (kind export), and
    the largest gap between a pair frame's ratios read through its P and through the export's P for the same frame,
    which differ by a similarity of the image and so must agree."""
    pair = S.load_pair(str(Path(folder) / entry["npz"]))
    col3 = np.asarray(pair["landmarks"], float)
    levels, source_name = pair["levels"], Path(folder).name
    rows = []
    for fr in pair["frames"]:
        rows += frame_rows(col3, levels, fr["P"], PAIR_SIZE, entry["person"], source_name, "pair")
    gap, not_square = 0.0, 0
    ids = list(entry.get("frame_ids", []))
    if export is not None:
        got, not_square = export_frames(export, entry["case"])
        frames = {fid: (orient(P, col3), size) for fid, P, size in got}
        for fr, fid in zip(pair["frames"], ids):
            if fid in frames:
                gap = max(gap, ratio_gap(col3, fr["P"], frames[fid][0]))
        for fid, (P, size) in frames.items():
            if fid not in ids:
                rows += frame_rows(col3, levels, P, size, entry["person"], source_name, "export")
    return rows, gap, pair, not_square


def ratio_gap(col3, P1, P2):
    worst = 0.0
    c1, c2 = G.project(P1, col3), G.project(P2, col3)
    for m in MEASURES:
        if m.kind == "ratio":
            d = np.abs(m.value2(col3, c1) - m.value2(col3, c2))
            if np.isfinite(d).any():
                worst = max(worst, float(np.nanmax(d)))
    return worst


def project_all(folders):
    """The projection test over every built person of every folder (a realx_pairs output with its manifest)."""
    rows, gaps, counts, checks = [], {}, {}, {k: [] for k in construction_checks(np.full((1, 18, 3), np.nan))}
    tilts = {}
    for folder in folders:
        manifest = json.loads((Path(folder) / "manifest.json").read_text())
        export = manifest.get("export")
        export = export if export and Path(export, "meta").is_dir() else None
        name = Path(folder).name
        counts[name] = {"persons": 0, "held_out_not_read": len(manifest.get("held_out", [])), "export_read": export is not None,
                        "export_frames_not_square": 0}
        for entry in manifest["persons"]:
            got, gap, pair, not_square = person_rows(folder, entry, export)
            rows += got
            gaps[name] = max(gaps.get(name, 0.0), gap)
            counts[name]["persons"] += 1
            counts[name]["export_frames_not_square"] += not_square
            for k, v in construction_checks(np.asarray(pair["landmarks"], float)).items():
                checks[k] += [float(x) for x in v if np.isfinite(x)]
            for k, v in frame_tilts(np.asarray(pair["landmarks"], float)).items():
                tilts.setdefault(name, {}).setdefault(k, []).extend(float(x) for x in v if np.isfinite(x))
    counts["frame_tilts"] = {src: {k: {"n": len(v), "percentiles": [float(np.percentile(v, q)) for q in (5, 50, 95)]}
                                   for k, v in by.items() if v} for src, by in tilts.items()}
    return rows, gaps, counts, checks


def as_arrays(rows):
    names = ("measure", "level", "person", "source", "kind", "off_ap", "off_lat", "mag", "inside", "v3", "v2", "size")
    cols = list(zip(*rows)) if rows else [[] for _ in names]
    return {n: np.asarray(c) for n, c in zip(names, cols)}


def agreement(kind, v3, v2, mag):
    """The 2-D reading against the 3-D one: a ratio's or an angle's difference, a length's 2-D value over its 3-D
    value times the magnification, less one."""
    if kind == "length":
        with np.errstate(invalid="ignore", divide="ignore"):
            return v2 / (mag * v3) - 1.0
    return v2 - v3


def cell(err):
    a = np.abs(err)
    return {"n": int(len(err)), "median_abs": float(np.median(a)), "p90_abs": float(np.percentile(a, 90)),
            "median": float(np.median(err)), "robust_sd": robust_sd(err)}


def binned(sel, A, err, view):
    """The agreement in each bin of degrees off the view."""
    off = A["off_ap"] if view == "ap" else A["off_lat"]
    out = []
    for lo, hi in zip(BINS[:-1], BINS[1:]):
        keep = sel & (off >= lo) & (off < hi)
        if keep.sum() >= 1:
            out.append({"bin": [lo, hi], "persons": int(len(set(A["person"][keep]))), **cell(err[keep])})
    return out


def within_level_r(A, keep, k):
    """Across persons, the correlation of a measure's 2-D reading (a length divided by its magnification) with its
    3-D value, each person and level's frames averaged, after each level's mean is taken out of both."""
    kind = MEASURES[k].kind
    read = A["v2"] / A["mag"] if kind == "length" else A["v2"]
    pairs = {}
    for p, lv, a, b in zip(A["person"][keep], A["level"][keep], A["v3"][keep], read[keep]):
        pairs.setdefault((p, lv), []).append((a, b))
    by_level = {}
    for (p, lv), vals in pairs.items():
        by_level.setdefault(lv, []).append((vals[0][0], float(np.mean([v[1] for v in vals]))))
    xs, ys = [], []
    for vals in by_level.values():
        if len(vals) >= 3:
            v = np.asarray(vals)
            xs += list(v[:, 0] - v[:, 0].mean())
            ys += list(v[:, 1] - v[:, 1].mean())
    if len(xs) < 5 or np.std(xs) == 0 or np.std(ys) == 0:
        return None, len(pairs)
    return float(np.corrcoef(xs, ys)[0, 1]), len(pairs)


def verdict(kind, near):
    if not near or near["n"] < 5:
        return "not tested"
    med, p90 = BARS[kind]
    return "survives" if near["median_abs"] <= med and near["p90_abs"] <= p90 else "does not survive"


def robust_sd(err):
    return float(1.4826 * np.median(np.abs(err - np.median(err)))) if len(err) else float("nan")


def summarise(A):
    """Per measure, in its own view and the other: the agreement by bin, within TOLERANCE of the view, the verdict,
    the robust SD of the error there (the census's X-ray error) and the within-level correlation, all from the
    sources whose angles are not in doubt (ANGLES_IN_DOUBT); each source's own bins and cells beside them, and the
    bins of every source pooled (bins_all), so that what the pooling would do can be read."""
    out = []
    trusted = ~np.isin(A["source"], ANGLES_IN_DOUBT)
    for k, m in enumerate(MEASURES):
        this = (A["measure"] == k) & A["inside"]
        err = agreement(m.kind, A["v3"], A["v2"], A["mag"])
        entry = {"name": m.name, "kind": m.kind, "view": m.view, "scheme": m.scheme, "views": {}}
        for view in ("ap", "lat"):
            if m.kind == "angle" and view != m.view:
                continue
            nearest = (A["off_ap"] <= A["off_lat"]) if view == "ap" else (A["off_lat"] < A["off_ap"])
            every = this & nearest
            sel = every & trusted
            off = A["off_ap"] if view == "ap" else A["off_lat"]
            near, near_every = sel & (off < TOLERANCE), every & (off < TOLERANCE)
            r, n_pl = within_level_r(A, near, k)
            stats = cell(err[near]) if near.any() else None
            entry["views"][view] = {
                "bins": binned(sel, A, err, view), "within_tolerance": stats, "bins_all": binned(every, A, err, view),
                "bins_by_source": {s: binned(every & (A["source"] == s), A, err, view) for s in sorted(set(A["source"]))},
                "persons": int(len(set(A["person"][near]))), "robust_sd": robust_sd(err[near]),
                "verdict": verdict(m.kind, stats), "r_within_level": r, "person_levels": n_pl,
                "by_source": {s: cell(err[near_every & (A["source"] == s)]) for s in sorted(set(A["source"][near_every]))}}
        out.append(entry)
    return out


def magnification_spread(A):
    """Per source, the spread of the magnification over its in-frame readings, as the SD of its logarithm: the scale
    a length read in pixels on an uncalibrated frame does not know. A pair's frame is its export frame brought to
    PAIR_SIZE pixels while an export frame keeps its own side, so each magnification is taken per pixel of its own
    canvas's side, which is the same for one frame on either canvas; the spread in each canvas's raw pixels is kept
    beside it, to show what pooling the two canvases would do."""
    out = {}
    for s in sorted(set(A["source"])):
        keep = (A["source"] == s) & A["inside"]
        if not keep.any():
            continue
        per_side = A["mag"] / A["size"]
        by_kind = {}
        for k in ("pair", "export"):
            got = keep & (A["kind"] == k)
            if got.any():
                by_kind[k] = {"n": int(got.sum()), "log_sd": float(np.std(np.log(per_side[got]))),
                              "canvas_sides": sorted({float(x) for x in A["size"][got]})}
        out[s] = {"n": int(keep.sum()), "log_sd": float(np.std(np.log(per_side[keep]))),
                  "p5_over_p95": float(np.percentile(per_side[keep], 5) / np.percentile(per_side[keep], 95)),
                  "log_sd_raw_pixels": float(np.std(np.log(A["mag"][keep]))), "by_kind": by_kind}
    return out


def off_view_by_source(A):
    """Per source, over the in-frame readings, how far the ray lies from the nearer of the vertebra's own two views:
    the share within TOLERANCE and the 5th, 50th and 95th percentiles in degrees, for the pairs' frames and the
    export's other frames apart."""
    out = {}
    off = np.minimum(A["off_ap"], A["off_lat"])
    for s in sorted(set(A["source"])):
        for kind in ("pair", "export"):
            keep = (A["source"] == s) & (A["kind"] == kind) & A["inside"]
            if keep.any():
                out[f"{s} {kind}"] = {"n": int(keep.sum()), "within_tolerance": float(np.mean(off[keep] < TOLERANCE)),
                                      "percentiles": [float(np.percentile(off[keep], q)) for q in (5, 50, 95)]}
    return out


def run_project(folders, out):
    with warnings.catch_warnings(), np.errstate(invalid="ignore", divide="ignore"):
        # a level the oracle read nothing of is all NaN, and its means and extremes warn; it gives no row
        warnings.simplefilter("ignore", RuntimeWarning)
        rows, gaps, counts, checks = project_all(folders)
    A = as_arrays(rows)
    result = {"folders": [Path(f).name for f in folders], "counts": counts, "bins": list(BINS), "tolerance_deg": TOLERANCE,
              "bars": BARS, "pair_vs_export_ratio_gap": gaps,
              "rows": {"total": int(len(A["v3"])), "in_frame": int(A["inside"].sum()) if len(A["v3"]) else 0,
                       "by_kind": {k: int((A["kind"] == k).sum()) for k in ("pair", "export")}},
              "frames_off_view": {k: [float(np.percentile(np.minimum(A["off_ap"], A["off_lat"])[A["kind"] == k], q)) for q in (5, 50, 95)]
                                  for k in ("pair", "export") if (A["kind"] == k).any()},
              "construction": {k: {"n": len(v), "median_abs": float(np.median(np.abs(v))), "p95_abs": float(np.percentile(np.abs(v), 95))}
                               for k, v in checks.items() if v},
              "off_view_by_source": off_view_by_source(A), "magnification": magnification_spread(A), "measures": summarise(A)}
    Path(out).write_text(json.dumps(result, indent=1))
    return result


# ---------------------------------------------------------------- the gold tier's aggregates

LEVEL_ORDER = [f"C{i}" for i in range(1, 8)] + [f"T{i}" for i in range(1, 13)] + [f"L{i}" for i in range(1, 7)]
# The engine's rows the census ranks, as the engine names them (grid/bordercall/morphometry), each with its kind, the
# measure of the eighteen points whose projection test stands for it in the X-ray run, and how: "same" where the
# eighteen points make the same chord (the oracle is scanimport's chords; the plate and canal widths among them are
# the label slab's extents at 9c85de1, which take in what the label fuses to the plate's edge, L5's transverse
# processes' roots among it, and read the canal from the label's hole: bordercall #78, after 9c85de1, reads plate_w
# and canal_w_ct instead, and these rows predate it), "analogue" where they make a line of the
# same direction at about the same place (the engine's corner heights against the slab-centre heights, the waist
# against the plate, the plates' angles against the segmental angle), None where nothing of the eighteen does (a
# concavity and a disc lie inside what the points span, and are not tested).
GOLD_ROWS = {
    "endplate": ("length", "EPWu", "same"), "endplate_lower": ("length", "EPWl", "same"),
    "endplate_depth": ("length", "EPDu", "same"), "endplate_lower_depth": ("length", "EPDl", "same"),
    "h_post": ("length", "VBHp", "same"), "canal_w": ("length", "SCW", "same"), "canal_ap": ("length", "SCD", "same"),
    "tp_span": ("length", "TPW", "same"), "spinous_length": ("length", "SPL", "same"),
    "h_ant": ("length", "ha", "analogue"), "h_post_inset": ("length", "hp", "analogue"), "h_mid": ("length", "hm", "analogue"),
    "body_index_ant_post": ("ratio", "ha/hp", "analogue"), "body_index_mid_post": ("ratio", "hm/hp", "analogue"),
    "wedge": ("angle", "seg_sag", "analogue"), "endplate_incl": ("angle", "seg_sag", "analogue"),
    "endplate_lower_incl": ("angle", "seg_sag", "analogue"),
    "endplate_concavity": ("length", None, None), "endplate_lower_concavity": ("length", None, None),
    "body_w_mid": ("length", "EPWu", "analogue"), "body_d_mid": ("length", "EPDu", "analogue"),
    "canal_index_torg": ("ratio", "SCD/EPDu", "analogue"), "interpedicular": ("length", "SCW", "analogue"),
    "segment_sagittal": ("angle", "seg_sag", "same"), "segment_coronal": ("angle", "seg_cor", "same"),
    "disc_h_ant": ("length", None, None), "disc_h_post": ("length", None, None),
}
# Ratios of the engine's rows: the numerator's row, the denominator's (a row, "below" for the same row of the level
# below, "crush" for the mean of the neighbours'), the ratio of the eighteen points (MEASURES) that stands for it, and
# how. The crush index is read on the engine's corner height h_post_inset, whose stand-in is the crush ratio's form on
# the posterior wall (VBHp), an analogue; every other is the same ratio of the same chords.
GOLD_RATIOS = {
    "crush_index": ("h_post_inset", "crush", "crush", "analogue"),
    "depth_over_h_post": ("endplate_depth", "h_post", "EPDu/VBHp", "same"),
    "depth_taper": ("endplate_lower_depth", "endplate_depth", "EPDl/EPDu", "same"),
    "canal_ap_over_depth": ("canal_ap", "endplate_depth", "SCD/EPDu", "same"),
    "spinous_over_depth": ("spinous_length", "endplate_depth", "SPL/EPDu", "same"),
    "h_post_over_below": ("h_post", "below", "VBHp/below", "same"),
    "depth_over_below": ("endplate_depth", "below", "EPDu/below", "same"),
    "width_taper": ("endplate_lower", "endplate", "EPWl/EPWu", "same"),
    "canal_w_over_width": ("canal_w", "endplate", "SCW/EPWu", "same"),
    "tp_span_over_width": ("tp_span", "endplate", "TPW/EPWu", "same"),
    "width_over_below": ("endplate", "below", "EPWu/below", "same"),
    "tp_span_over_below": ("tp_span", "below", "TPW/below", "same"),
}
PELVIS = ("pelvic_incidence", "sacral_slope_supine", "pelvic_tilt_supine", "intercristal_above_l4l5", "hip_axis_width")


def number(text):
    try:
        v = float(text)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def chosen_studies(persons_csv, members_out=("verse", "totalseg")):
    """One study a person, as the covariates' join chose it, of the members other than VerSe's and
    TotalSegmentator's (whose rows are another set's); and the count by member."""
    keep, members = set(), {}
    with open(persons_csv, newline="") as f:
        for r in csv.DictReader(f):
            if r["member"] in members_out or not r.get("study"):
                continue
            keep.add(r["study"])
            members[r["member"]] = members.get(r["member"], 0) + 1
    return keep, members


def typical_studies(verdicts_csv, studies):
    """Of the studies given, those whose column bordercall's count calls TYPICAL_CALL; and how many of the given
    studies each call holds, a call held by fewer than MIN_CELL counted under "other"."""
    keep, calls = set(), {}
    with open(verdicts_csv, newline="") as f:
        for r in csv.DictReader(f):
            if r["id"] not in studies:
                continue
            call = (r.get("call") or "").strip() or "none"
            calls[call] = calls.get(call, 0) + 1
            if call == TYPICAL_CALL:
                keep.add(r["id"])
    shown = {k: v for k, v in sorted(calls.items()) if v >= MIN_CELL}
    other = sum(v for v in calls.values() if v < MIN_CELL)
    if other:
        shown["other"] = other
    shown["no verdict"] = len(studies) - sum(calls.values())
    return keep, shown


def read_rows(rows_csv, studies):
    """The engine's rows of the chosen studies: {(study, level): {key: value}} for the keys the census reads, and
    the pelvis's rows apart."""
    wanted = set(GOLD_ROWS) | set(PELVIS) | {"intercristal_level"}
    body, pelvis = {}, {}
    with open(rows_csv, newline="") as f:
        for r in csv.DictReader(f):
            if r["study"] not in studies or r["key"] not in wanted:
                continue
            if r["level"] == "pelvis":
                pelvis.setdefault(r["study"], {})[r["key"]] = r["value"]
                continue
            v = number(r["value"])
            if v is not None:
                body.setdefault((r["study"], r["level"]), {})[r["key"]] = v
    return body, pelvis


def neighbour(level, step):
    """The level step below (or above, negative); None past the column's ends and for L6, so that L5's neighbour
    below, which in a typical column is the sacrum, is never a sixth lumbar's."""
    i = LEVEL_ORDER.index(level) + step if level in LEVEL_ORDER else -1
    return LEVEL_ORDER[i] if 0 <= i < len(LEVEL_ORDER) and LEVEL_ORDER[i] != "L6" else None


def derived(body):
    """The ratios of GOLD_RATIOS for every study and level whose parts were read."""
    out = {}
    for (study, level), vals in body.items():
        if level not in LEVEL_ORDER:
            continue
        got = {}
        for name, (num, den, _, _) in GOLD_RATIOS.items():
            a = vals.get(num)
            if den == "below":
                lower = neighbour(level, 1)
                b = body.get((study, lower), {}).get(num) if lower else None
            elif den == "crush":
                up, low = neighbour(level, -1), neighbour(level, 1)
                pair = [body.get((study, x), {}).get(num) for x in (up, low) if x]
                b = 0.5 * sum(pair) if len(pair) == 2 and None not in pair else None
            else:
                b = vals.get(den)
            if a is not None and b is not None and b > 0:
                got[name] = a / b
        out[(study, level)] = got
    return out


def gold_table(body, ratios):
    """Per level and measure, n, mean and SD, a cell kept where MIN_CELL persons give it."""
    by = {}
    for key, vals in body.items():
        if "L6" in key[1]:
            continue        # a sixth lumbar's rows and its disc's are another column's
        for name, v in list(vals.items()) + list(ratios.get(key, {}).items()):
            if name in GOLD_ROWS or name in GOLD_RATIOS:
                by.setdefault((key[1], name), []).append(v)
    rows = []
    for (level, name), vals in sorted(by.items(), key=lambda kv: (LEVEL_ORDER.index(kv[0][0]) if kv[0][0] in LEVEL_ORDER else 99, kv[0])):
        if len(vals) >= MIN_CELL:
            kind = GOLD_ROWS[name][0] if name in GOLD_ROWS else "ratio"
            rows.append({"level": level, "measure": name, "kind": kind, "n": len(vals), "mean": float(np.mean(vals)),
                         "sd": float(np.std(vals, ddof=1)), "error": ""})
    return rows


def gold_correlations(body, ratios, levels=LUMBAR):
    """Within each level, the Pearson r of every pair of measures over the studies that give both."""
    out = []
    for level in levels:
        per = {}
        for (study, lv), vals in body.items():
            if lv == level:
                per[study] = {**{k: v for k, v in vals.items() if k in GOLD_ROWS}, **ratios.get((study, lv), {})}
        names = sorted({k for v in per.values() for k in v})
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                xy = np.array([(v[a], v[b]) for v in per.values() if a in v and b in v])
                if len(xy) >= MIN_R and xy[:, 0].std() > 0 and xy[:, 1].std() > 0:
                    out.append({"level": level, "measure_a": a, "measure_b": b, "n": len(xy), "r": float(np.corrcoef(xy.T)[0, 1])})
    return out


def pelvis_summary(pelvis):
    """The pelvis's one value a person: mean, SD and n of each angle and length, and where the iliac crests' line
    falls, counted by level (the crests' line crosses a body or a disc between two)."""
    out = {}
    for key in PELVIS:
        vals = [number(p.get(key)) for p in pelvis.values()]
        vals = [v for v in vals if v is not None]
        if len(vals) >= MIN_CELL:
            out[key] = {"n": len(vals), "mean": float(np.mean(vals)), "sd": float(np.std(vals, ddof=1))}
    counts = {}
    for p in pelvis.values():
        lv = (p.get("intercristal_level") or "").strip()
        if lv:
            counts[lv] = counts.get(lv, 0) + 1
    out["intercristal_level"] = {k: v for k, v in sorted(counts.items()) if v >= MIN_CELL}
    out["intercristal_level_withheld_cells"] = sum(1 for v in counts.values() if v < MIN_CELL)
    out["intercristal_level_persons"] = sum(counts.values())
    return out


def write_csv(path, rows, fields):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def run_gold(rows_csv, persons_csv, out, verdicts_csv=None):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    studies, members = chosen_studies(persons_csv)
    calls = None
    if verdicts_csv:
        studies, calls = typical_studies(verdicts_csv, studies)
    body, pelvis = read_rows(rows_csv, studies)
    ratios = derived(body)
    table = gold_table(body, ratios)
    write_csv(out / "table.csv", table, ["level", "measure", "kind", "n", "mean", "sd", "error"])
    write_csv(out / "correlation.csv", gold_correlations(body, ratios), ["level", "measure_a", "measure_b", "n", "r"])
    summary = {"studies_chosen": len(studies), "members": members, "calls_of_the_chosen": calls,
               "typical_call": TYPICAL_CALL if calls is not None else None, "studies_with_rows": len({s for s, _ in body}),
               "cells": len(table), "pelvis": pelvis_summary(pelvis), "min_cell": MIN_CELL, "min_r": MIN_R}
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    return summary


# ---------------------------------------------------------------- the census

PANJABI_KEYS = ("endplate", "endplate_depth", "endplate_lower", "endplate_lower_depth", "h_post", "canal_w", "canal_ap",
                "spinous_length", "transverse_width", "endplate_incl", "endplate_lower_incl")


def census_module(clone):
    sys.path.insert(0, str(Path(clone).resolve()))
    import schwingcheck.census as C
    return C


def restricted(C, series, levels):
    """A census Series cut to the run of the levels given that it is printed at, None where that is under two
    levels or not one run (a measure taken against the level below has no row at L5, whose neighbour is the
    sacrum, and is ranked over T12 to L4 in a group of its own, as the census groups measures by their levels)."""
    keep = [lv for lv in levels if lv in series.levels]
    start = levels.index(keep[0]) if keep else 0
    if len(keep) < 2 or keep != list(levels[start:start + len(keep)]):
        return None
    idx = [series.levels.index(lv) for lv in keep]
    return C.Series(series.key, series.kind, series.error, tuple(keep), tuple(series.mean[i] for i in idx),
                    tuple(series.sd[i] for i in idx), tuple(series.n[i] for i in idx))


def lumbar_correlation(path, levels=LUMBAR):
    pairs = {}
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            if r["level"] in levels:
                a, b = sorted((r["measure_a"], r["measure_b"]))
                pairs.setdefault((a, b), []).append(abs(float(r["r"])))
    return {k: float(np.median(v)) for k, v in pairs.items()}


def stand_in(key):
    """The projection measure that stands for a gold measure, and how (same or analogue)."""
    if key in GOLD_ROWS:
        return GOLD_ROWS[key][1], GOLD_ROWS[key][2]
    if key in GOLD_RATIOS:
        return GOLD_RATIOS[key][2], GOLD_RATIOS[key][3]
    return None, None


def xray_error(C, series, projection):
    """A measure's error as read on an X-ray: its census error and the projection test's error within TOLERANCE of
    its view (the median, which is a bias, and the robust SD about it) added in quadrature, a length's (relative)
    times its mean over the levels; None where the projection test has no measure for it or the measure did not
    survive."""
    name, how = stand_in(series.key)
    entry = next((m for m in projection["measures"] if m["name"] == name), None) if name else None
    if entry is None:
        return None, name, "no measure of the eighteen points stands for it"
    view = entry["views"].get(entry["view"])
    if not view or view["verdict"] != "survives":
        return None, name, f"in its view it {view['verdict'] if view else 'was not read'}"
    near = view["within_tolerance"]
    spread = math.hypot(near["median"], view["robust_sd"])
    sd = spread * (float(np.mean(series.mean)) if series.kind == "length" else 1.0)
    return float(math.hypot(series.error, sd)), name, how


def xlogy(x, y):
    return float(x * math.log(y)) if x > 0 else 0.0


def tuffier(counts, persons=None, levels=LUMBAR):
    """What the iliac crests' line tells, two ways, with the count of persons whose line crosses each body or disc.

    About the body it crosses (crossed_body_nats): the name of the one body the line marks, its posterior the share
    of persons whose line crosses each body, so log K less that share's entropy. That is a question of its own and
    weights the levels by how often the line crosses them.

    About a lone body, by the census's definition (lone_body_nats): a body drawn at each of the K levels alike, the
    observation whether the line crosses it, q_k the share of persons whose line crosses body k (of `persons`, all
    whose crest level was read, discs among them), the information at level k the mean log posterior at the truth
    plus log K, and the mean over the K levels; this is the figure that sits beside the chords'."""
    bodies = {lv: n for lv, n in counts.items() if lv in levels}
    total = sum(bodies.values())
    if not total:
        return {}
    p = np.array([n / total for n in bodies.values()])
    K = len(levels)
    persons = persons or sum(counts.values())
    q = [bodies.get(lv, 0) / persons for lv in levels]
    yes, no = sum(q), sum(1.0 - x for x in q)
    per_level = [xlogy(x, x / yes) + xlogy(1.0 - x, (1.0 - x) / no) + math.log(K) for x in q]
    return {"crossing": counts, "bodies": bodies, "persons": persons,
            "crossed_body_nats": float(math.log(K) + np.sum(p * np.log(p))), "of_nats": float(math.log(K)),
            "named_by_the_commonest": float(p.max()), "lone_body_nats": float(np.mean(per_level)),
            "lone_body_by_level": dict(zip(levels, per_level))}


def rank(C, source_id, series, nodes, fields, seed, correlation=None):
    src = C.Source(id=source_id, paper=source_id, measures=list(series), correlation=correlation or {})
    return C.census_source(src, fields, seed, nodes)


def angle_cost(C, ct, projection, nodes, fields, seed, least=20):
    """Each gold measure with a stand-in, alone, as read in each bin of degrees off its view (its census error and
    that bin's projection error, bias and robust SD, in quadrature), from the same draws as on the CT: what the
    view's angle costs the Bayes rule, measure by measure. A bin with fewer than `least` readings is left out."""
    out = []
    for k, series in enumerate(ct):
        name, how = stand_in(series.key)
        entry = next((m for m in projection["measures"] if m["name"] == name), None) if name else None
        view = entry["views"].get(entry["view"]) if entry else None
        if view is None:
            continue
        scale = float(np.mean(series.mean)) if series.kind == "length" else 1.0
        on_ct = C.census_group([series], fields, seed + 31 * k, nodes, {})["measures"][0]["standalone"]
        row = {"key": series.key, "stand_in": name, "how": how, "view": entry["view"], "ct": float(np.mean(on_ct)), "bins": []}
        for b in view["bins"]:
            if b["n"] < least:
                continue
            error = math.hypot(series.error, math.hypot(b["median"], b["robust_sd"]) * scale)
            ex = C.Series(series.key, series.kind, error, series.levels, series.mean, series.sd, series.n)
            on_x = C.census_group([ex], fields, seed + 31 * k, nodes, {})["measures"][0]["standalone"]
            row["bins"].append({"bin": b["bin"], "n": b["n"], "error": error, "xray": float(np.mean(on_x))})
        out.append(row)
    return out


@contextmanager
def size_spread(R, sd):
    """The rule's size spread (R.SYNTH's scale_sd, which the census's draws read) set to sd inside, with the nodes
    for it, and put back after. A frame of unknown magnification reads every length of a body times one unknown
    factor, as an unknown size does, so the two spreads add in quadrature and a ratio or an angle, of power 0 in
    the size, is untouched."""
    old = R.SYNTH["scale_sd"]
    R.SYNTH["scale_sd"] = sd
    try:
        yield R.quadrature(sd)
    finally:
        R.SYNTH["scale_sd"] = old


def standalone(C, series, fields, seed, nodes, R=None, scale_sd=None):
    """One measure's standalone information, mean over its levels, and the standard error of that mean; with
    scale_sd, drawn and read with the size spread widened to it."""
    if scale_sd is None:
        m = C.census_group([series], fields, seed, nodes, {})["measures"][0]
    else:
        with size_spread(R, scale_sd) as wide:
            m = C.census_group([series], fields, seed, wide, {})["measures"][0]
    return float(np.mean(m["standalone"])), float(math.sqrt(np.nansum(np.square(m["standalone_se"]))) / len(m["standalone"]))


def paired_standalone(C, ct, xray, nodes, fields, seed, R=None, uncalibrated=None):
    """Each X-ray measure's standalone information beside the same measure's on the CT, each drawn alone from the
    same seed, so the two draws share every random number and differ only in the error: the difference is what the
    projection's error costs, free of the census's Monte Carlo noise. The X-ray here knows each frame's
    magnification, as the projection test divides by it; `uncalibrated` ({name: log SD}) adds, for each name, the
    same measure read on a frame whose magnification is unknown by that spread, the size spread widened by it."""
    by_key = {s.key: s for s in ct}
    out = []
    for k, sx in enumerate(xray):
        row = {"key": sx.key, "kind": sx.kind, "levels": list(sx.levels), "ct_error": by_key[sx.key].error, "xray_error": sx.error}
        row["ct"], row["ct_se"] = standalone(C, by_key[sx.key], fields, seed + 31 * k, nodes)
        row["xray"], row["xray_se"] = standalone(C, sx, fields, seed + 31 * k, nodes)
        for name, log_sd in (uncalibrated or {}).items():
            wide = math.hypot(R.SYNTH["scale_sd"], log_sd)
            row[f"xray_uncalibrated_{name}"], _ = standalone(C, sx, fields, seed + 31 * k, nodes, R, wide)
        out.append(row)
    return out


SHARED_KEYS = {"endplate": "endplate", "endplate_lower": "endplate_lower", "endplate_depth": "endplate_depth",
               "endplate_lower_depth": "endplate_lower_depth", "h_post": "h_post", "canal_w": "canal_w",
               "canal_ap": "canal_ap", "spinous_length": "spinous_length", "tp_span": "transverse_width"}
SERIES_CSV = Path("research_notes") / "paper-tables" / "data" / "series.csv"


def other_series(C, path, keys, levels=LUMBAR):
    """The clinical reread's series of the given keys at the given levels, read as the census reads them (the values
    a paper measured itself, no quoted value, figure's example or pig cohort, a disc's row to the body above) but
    with or without a spread, since a mean is all a comparison needs: {key: {series id: {level: mean}}}, the sides
    of a level averaged."""
    by = {}
    for r in C.read_csv(str(path)):
        key = r["key"].strip()
        if key not in keys or r.get("source_of_values", "this paper").strip() not in ("", "this paper"):
            continue
        if C.LEFT_OUT_COHORTS.search(r["cohort"].strip()):
            continue
        lv = C.body_level(r["level"])
        mean = number(r["mean"])
        if lv not in levels or mean is None:
            continue
        sid = " | ".join(x for x in (r["paper"].strip(), r["cohort"].strip(), r["technique"].strip(), r["sex"].strip()) if x)
        by.setdefault(key, {}).setdefault(sid, {}).setdefault(lv, []).append(mean)
    return {k: {sid: {lv: float(np.mean(v)) for lv, v in cells.items()} for sid, cells in series.items()}
            for k, series in by.items()}


def against_sources(C, clone, gold_series, pan_series, levels=LUMBAR):
    """Each chord the gold tier shares a name with Panjabi's table, level by level: the gold tier's mean, Panjabi's,
    and the other series' median, least and most with their count; and, for every series that prints both, the
    step from L4 to L5 and from T12 to L1, the two steps the ranking leans on."""
    gold = {s.key: dict(zip(s.levels, s.mean)) for s in gold_series}
    pan = {s.key: dict(zip(s.levels, s.mean)) for s in pan_series}
    path = Path(clone) / SERIES_CSV
    others = other_series(C, path, set(SHARED_KEYS.values()), levels) if path.is_file() else {}
    out = []
    for gkey, pkey in SHARED_KEYS.items():
        series = others.get(pkey, {})
        row = {"gold_key": gkey, "panjabi_key": pkey, "levels": {}, "steps": {}}
        for lv in levels:
            vals = [cells[lv] for cells in series.values() if lv in cells]
            row["levels"][lv] = {"gold": gold.get(gkey, {}).get(lv), "panjabi": pan.get(pkey, {}).get(lv),
                                 "others_median": float(np.median(vals)) if vals else None,
                                 "others_least": min(vals) if vals else None, "others_most": max(vals) if vals else None,
                                 "others_n": len(vals)}
        for name, (a, b) in (("L5_less_L4", ("L4", "L5")), ("L1_less_T12", ("T12", "L1"))):
            step = {"gold": None, "panjabi": None, "others": {}}
            if a in gold.get(gkey, {}) and b in gold.get(gkey, {}):
                step["gold"] = gold[gkey][b] - gold[gkey][a]
            if a in pan.get(pkey, {}) and b in pan.get(pkey, {}):
                step["panjabi"] = pan[pkey][b] - pan[pkey][a]
            step["others"] = {sid: cells[b] - cells[a] for sid, cells in sorted(series.items()) if a in cells and b in cells}
            row["steps"][name] = step
        out.append(row)
    return out


def commit_of(clone):
    try:
        return subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def run_census(clone, gold, projection_path, out, fields=2000):
    C = census_module(clone)
    R = sys.modules["schwingcheck.rule"]
    nodes = R.quadrature(R.SYNTH["scale_sd"])
    projection = json.loads(Path(projection_path).read_text())
    spreads = {s: v["log_sd"] for s, v in projection.get("magnification", {}).items()}
    pan, _ = C.panjabi_source()
    pan_series = [s for s in (restricted(C, m, LUMBAR) for m in pan.measures if m.key in PANJABI_KEYS) if s]
    table = C.table_source(str(Path(gold) / "table.csv"), "gold3-enhance")
    gold_series = [s for s in (restricted(C, m, LUMBAR) for m in table.measures) if s]
    corr = lumbar_correlation(Path(gold) / "correlation.csv")
    xray, left, how = [], [], {}
    for s in gold_series:
        err, name, why = xray_error(C, s, projection)
        if err is None:
            left.append({"key": s.key, "projection_measure": name, "why": why})
        else:
            xray.append(C.Series(s.key, s.kind, err, s.levels, s.mean, s.sd, s.n))
            how[s.key] = {"stand_in": name, "how": why, "error": err, "census_error": s.error}
    sources = [rank(C, "panjabi, T12 to L5", pan_series, nodes, fields, C.SEED),
               rank(C, "gold3 ENHANCE.PET, T12 to L5, on the CT", gold_series, nodes, fields, C.SEED + 1, corr),
               rank(C, "gold3 ENHANCE.PET, T12 to L5, on an X-ray of known magnification", xray, nodes, fields, C.SEED + 1, corr)]
    if "deepfluoro" in spreads:
        # the C-arm's own spread: every length of a body read times one unknown factor, the size spread widened by it
        # (an AP and a lateral frame each have their own factor, which one shared factor makes slightly optimistic)
        with size_spread(R, math.hypot(R.SYNTH["scale_sd"], spreads["deepfluoro"])) as wide:
            sources.append(rank(C, "gold3 ENHANCE.PET, T12 to L5, on an X-ray of unknown magnification (the C-arm's spread)",
                                xray, wide, fields, C.SEED + 1, corr))
    pelvis = json.loads((Path(gold) / "summary.json").read_text())["pelvis"]
    record = {"levels": list(LUMBAR), "fields_per_level": fields, "seed": C.SEED, "scale_sd": R.SYNTH["scale_sd"],
              "bordercall_commit": commit_of(clone), "magnification_log_sd": spreads,
              "ratio_error": C.RATIO_ERROR, "sources": sources,
              "paired_standalone": paired_standalone(C, gold_series, xray, nodes, fields, C.SEED + 5, R, spreads),
              "angle_cost": angle_cost(C, gold_series, projection, nodes, max(fields // 4, 100), C.SEED + 7),
              "xray_left_out": left, "xray_errors": how,
              "against_sources": against_sources(C, clone, gold_series, pan_series),
              "tuffier": tuffier(pelvis.get("intercristal_level", {}), pelvis.get("intercristal_level_persons"))}
    Path(out).write_text(json.dumps(record, indent=1))
    return record


# ---------------------------------------------------------------- the report

def projection_table(projection):
    lines = ["| Measure | Kind | View | Persons | 0-5 | 5-10 | 10-15 | 15-25 | 25-35 | 35+ | Within 15: median, p90 | r within level | Verdict |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for m in projection["measures"]:
        for view, v in m["views"].items():
            if view != m["view"]:
                continue
            bins = {tuple(b["bin"]): b for b in v["bins"]}
            cells = []
            for lo, hi in zip(BINS[:-1], BINS[1:]):
                b = bins.get((lo, hi))
                cells.append(fmt(m["kind"], b["median_abs"]) + f" ({b['n']})" if b else "-")
            near = v["within_tolerance"]
            r = "-" if v["r_within_level"] is None else f"{v['r_within_level']:.2f}"
            lines.append(f"| {m['name']} | {m['kind']} | {view} | {v['persons']} | " + " | ".join(cells) + " | "
                         + (f"{fmt(m['kind'], near['median_abs'])}, {fmt(m['kind'], near['p90_abs'])}" if near else "-")
                         + f" | {r} | {v['verdict']} |")
    return "\n".join(lines) + "\n"


def source_table(projection):
    """Per measure in its own view within TOLERANCE, each source's median absolute agreement and its count, the
    signed median, and the other view's, which shows what that view does to a measure it is not read in."""
    lines = ["| Measure | View | DeepFluoro | COBRA | Signed median | Other view within 15: median, p90 (n) |",
             "|---|---|---|---|---|---|"]
    for m in projection["measures"]:
        v = m["views"].get(m["view"])
        if not v:
            continue
        by = v["by_source"]
        cells = [f"{fmt(m['kind'], by[s]['median_abs'])} ({by[s]['n']})" if s in by else "-" for s in ("deepfluoro", "cobra")]
        signed = fmt(m["kind"], v["within_tolerance"]["median"]) if v["within_tolerance"] else "-"
        other = m["views"].get("lat" if m["view"] == "ap" else "ap")
        o = other["within_tolerance"] if other else None
        ocell = f"{fmt(m['kind'], o['median_abs'])}, {fmt(m['kind'], o['p90_abs'])} ({o['n']})" if o else "-"
        lines.append(f"| {m['name']} | {m['view']} | {cells[0]} | {cells[1]} | {signed} | {ocell} |")
    return "\n".join(lines) + "\n"


def pooling_table(projection, bins=((15.0, 25.0), (25.0, 35.0), (35.0, 60.0))):
    """Per measure in its own view, the off-view bins from the sources whose angles are trusted, from every source
    pooled and from each source whose angles are in doubt: what pooling them would do to the figures."""
    doubt = [s for s in ANGLES_IN_DOUBT]
    heads = [f"{int(lo)}-{int(hi)}" for lo, hi in bins]
    lines = ["| Measure | View | " + " | ".join(f"{h}: trusted, pooled, " + ", ".join(doubt) for h in heads) + " |",
             "|---|---|" + "---|" * len(bins)]
    for m in projection["measures"]:
        v = m["views"].get(m["view"])
        if not v or "bins_all" not in v:
            continue
        cells = []
        for lo, hi in bins:
            def at(seq):
                b = next((b for b in seq if tuple(b["bin"]) == (lo, hi)), None)
                return f"{fmt(m['kind'], b['median_abs'])} ({b['n']})" if b else "-"
            cells.append(", ".join([at(v["bins"]), at(v["bins_all"])] + [at(v["bins_by_source"].get(s, [])) for s in doubt]))
        lines.append(f"| {m['name']} | {m['view']} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def fmt(kind, x):
    if kind == "length":
        return f"{100 * x:.1f}%"
    if kind == "angle":
        return f"{x:.1f} deg"
    return f"{x:.3f}"


def census_table(record):
    """Per source and group of levels, the greedy order: each measure's standalone information as a mean over the
    levels (nats, of log K), the share of bodies it names exactly alone, what it adds after those above it (a mean
    over the levels) and what it repeats."""
    lines = []
    for src in record["sources"]:
        for g in src["groups"]:
            K = len(g["levels"])
            lines += [f"\n{src['id']}, {g['levels'][0]} to {g['levels'][-1]} ({K} levels, at most {math.log(K):.2f} nats):\n",
                      "| # | Measure | Alone, mean nats | Named alone | Adds, nats | Repeats |", "|---|---|---|---|---|---|"]
            alone = {m["key"]: m for m in g["measures"]}
            for e in g["order"]:
                m = alone[e["key"]]
                rep = f"{e['repeats']} ({e['redundancy'] / K:.3f})" if e["repeats"] else ""
                lines.append(f"| {e['rank']} | {e['key']} | {np.mean(m['standalone']):.3f} | {np.mean(m['standalone_exact']):.2f} | "
                             f"{e['conditional_sum'] / K:.3f} | {rep} |")
            shared = ", ".join(f"{s['a']} and {s['b']} ({s['r']:.2f})" for s in g["shared_by_correlation"])
            if shared:
                lines.append(f"\nShared by correlation (median |r| of at least 0.7 over the levels): {shared}.")
    paired = record.get("paired_standalone") or []
    if paired:
        sd_of = record.get("magnification_log_sd") or {}
        spreads = sorted(sd_of)
        named = ", ".join("%s %.3f" % (s, sd_of[s]) for s in spreads)
        lines += ["\nEach measure alone, on the CT and as read on an X-ray within 15 degrees of its view, the same draws (mean "
                  "nats over its levels, with the standard error of the mean); known: the frame's magnification known, as the "
                  "projection test divides by it; then on a frame whose magnification is unknown by each source's spread "
                  f"(the log SD: {named}):\n",
                  "| Measure | Kind | Levels | Error, CT | Error, X-ray | Alone, CT | Known | Cost | "
                  + " | ".join(f"Unknown, {s} | Cost" for s in spreads) + " |",
                  "|---|---|---|---|---|---|---|---|" + "---|---|" * len(spreads)]
        for e in sorted(paired, key=lambda e: -e["ct"]):
            unk = " | ".join(f"{e[f'xray_uncalibrated_{s}']:.3f} | {e['ct'] - e[f'xray_uncalibrated_{s}']:.3f}"
                             if f"xray_uncalibrated_{s}" in e else "- | -" for s in spreads)
            lines.append(f"| {e['key']} | {e.get('kind', '')} | {e['levels'][0]} to {e['levels'][-1]} | {e['ct_error']:.3g} | "
                         f"{e['xray_error']:.3g} | {e['ct']:.3f} +- {e['ct_se']:.3f} | {e['xray']:.3f} +- {e['xray_se']:.3f} | "
                         f"{e['ct'] - e['xray']:.3f} |" + (f" {unk} |" if spreads else ""))
    cost = record.get("angle_cost") or []
    if cost:
        heads = [f"{int(lo)}-{int(hi)}" for lo, hi in zip(BINS[:-1], BINS[1:])]
        lines += ["\nEach measure alone as read at each angle off its view (mean nats; the CT's first):\n",
                  "| Measure | Stand-in | View | CT | " + " | ".join(heads) + " |", "|---|---|---|---|" + "---|" * len(heads)]
        for e in sorted(cost, key=lambda e: -e["ct"]):
            got = {tuple(b["bin"]): b for b in e["bins"]}
            cells = [f"{got[(lo, hi)]['xray']:.3f}" if (lo, hi) in got else "-" for lo, hi in zip(BINS[:-1], BINS[1:])]
            lines.append(f"| {e['key']} | {e['stand_in']} ({e['how']}) | {e['view']} | {e['ct']:.3f} | " + " | ".join(cells) + " |")
    left = record.get("xray_left_out") or []
    if left:
        lines.append("\nLeft out of the X-ray run: " + "; ".join(f"{e['key']} ({e['why']})" for e in left) + ".")
    t = record.get("tuffier") or {}
    if t:
        lines.append(f"\nThe crests' line: {t['crossed_body_nats']:.2f} of {t['of_nats']:.2f} nats about the body it crosses, "
                     f"the commonest body {100 * t['named_by_the_commonest']:.1f} per cent; {t['lone_body_nats']:.3f} nats about "
                     f"a lone body, the census's way (by level: "
                     + ", ".join(f"{lv} {v:.3f}" for lv, v in t["lone_body_by_level"].items())
                     + f"); crossings {t['crossing']} of {t['persons']} persons read.")
    lines.append(sources_table(record.get("against_sources") or []))
    return "\n".join(lines) + "\n"


def sources_table(rows):
    """The gold tier's chords beside Panjabi's and the other series', level by level, and the steps the ranking leans
    on, series by series."""
    if not rows:
        return ""
    lines = ["\nThe chords against Panjabi and the reread's other series (mm; others: median, least to most, count):\n",
             "| Chord | Level | Gold | Panjabi | Gold less Panjabi | Others |", "|---|---|---|---|---|---|"]
    for r in rows:
        for lv, c in r["levels"].items():
            g, p = c["gold"], c["panjabi"]
            diff = f"{g - p:+.1f}" if g is not None and p is not None else "-"
            others = (f"{c['others_median']:.1f} ({c['others_least']:.1f} to {c['others_most']:.1f}, {c['others_n']})"
                      if c["others_n"] else "-")
            gs = "-" if g is None else f"{g:.1f}"
            ps = "-" if p is None else f"{p:.1f}"
            lines.append(f"| {r['gold_key']} ({r['panjabi_key']}) | {lv} | {gs} | {ps} | {diff} | {others} |")
    lines += ["\nThe steps, series by series (mm):\n", "| Chord | Step | Gold | Panjabi | Other series |", "|---|---|---|---|---|"]
    for r in rows:
        for name, st in r["steps"].items():
            if st["gold"] is None and st["panjabi"] is None and not st["others"]:
                continue
            others = "; ".join(f"{sid} {v:+.1f}" for sid, v in st["others"].items()) or "-"
            g = "-" if st["gold"] is None else f"{st['gold']:+.1f}"
            p = "-" if st["panjabi"] is None else f"{st['panjabi']:+.1f}"
            lines.append(f"| {r['gold_key']} | {name} | {g} | {p} | {others} |")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(prog="annotator_measures")
    sub = ap.add_subparsers(dest="what", required=True)
    p = sub.add_parser("project")
    p.add_argument("--pairs", nargs="+", required=True)
    p.add_argument("--out", required=True)
    g = sub.add_parser("gold")
    g.add_argument("--rows", required=True)
    g.add_argument("--persons", required=True)
    g.add_argument("--verdicts", help="bordercall's verdicts.csv: keep only the persons it calls T12L5")
    g.add_argument("--out", required=True)
    c = sub.add_parser("census")
    c.add_argument("--bordercall", required=True)
    c.add_argument("--gold", required=True)
    c.add_argument("--projection", required=True)
    c.add_argument("--fields", type=int, default=2000)
    c.add_argument("--out", required=True)
    r = sub.add_parser("report")
    r.add_argument("--projection")
    r.add_argument("--census")
    a = ap.parse_args(argv)
    if a.what == "project":
        res = run_project(a.pairs, a.out)
        print(json.dumps({k: res[k] for k in ("counts", "rows", "pair_vs_export_ratio_gap", "construction", "off_view_by_source",
                                              "magnification")}, indent=1))
    elif a.what == "gold":
        print(json.dumps(run_gold(a.rows, a.persons, a.out, a.verdicts), indent=1))
    elif a.what == "census":
        run_census(a.bordercall, a.gold, a.projection, a.out, a.fields)
        print(census_table(json.loads(Path(a.out).read_text())))
    else:
        if a.projection:
            projection = json.loads(Path(a.projection).read_text())
            print(projection_table(projection))
            print(source_table(projection))
            print(pooling_table(projection))
            print(json.dumps(projection.get("magnification", {}), indent=1))
        if a.census:
            print(census_table(json.loads(Path(a.census).read_text())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
