"""Which studies show the whole spine, C2 to the sacrum: two readings of one row of facts, in level
names, whatever dataset the masks came from.

    python -m screening whole --facts facts.jsonl --out verdicts.csv [--tables TABLES.json | --measure-tables]
        [--ages MAP.json] [--s1-view MM]

By the masks (rule version 1, SchwingNet data/gold3-ct/members.json, from bordercall's
holdings/count_enhance_pet.py): C2 and the sacrum each hold at least LEVEL_MIN_VOXELS voxels;
every level from C2 to T12 is drawn; no space wider than UNLABELLED_GAP_MM lies between
consecutive drawn levels above T12. A lumbar label missing or extra never drops a spine (the
owner, 2026-10-27 17:10 UTC): an absent L5 whose L4 meets the sacrum is the variant no_l5, and
any other lumbar gap is whole and listed for a look (lumbar_look). count_class gives the class,
whole_problems why a study is not whole, label_pattern what the lumbar names say and
call_by_names the column call, each as SchwingNet's tools/gold3_ct.py gives them on ENHANCE.PET's
rows (the test holds them equal on a recorded sample).

By the field (rule version 3, SchwingNet tools/gold3_field.py, the owner's words of 2026-10-28
22:58 UTC and 2026-10-29 12:58 UTC): a CT is admitted when its field holds the foot of C2 and the
top of the sacrum, whatever its masks draw; a level its masks do not draw is completed by a
segmenter, kept as a machine mask of its own. A drawn C2 is in view however the field's top cuts
it, unless it cuts the level below C2 too, a sliver of C2, and the end is out; an undrawn C2 is
in view when the field's top lies above where C2's foot lies in 95 of 100 spines, counted from
the head-most drawn level (the head table). A drawn sacrum is in view however little of it the
field holds; an undrawn one is in view when the field's foot lies below where the sacrum's top
lies in 95 of 100 spines, from the foot-most drawn level (the foot table). The field is read over
each level along the world's vertical line, so a tilted grid's faces count where they stand over
the column, and a padded grid's field ends where the spinal cord and the column stop together
(image_planes). A name missing between two drawn levels is a level to add when their centres
stand more than ROOM_TIMES the study's own spacing of neighbours apart, else a count variant,
flagged (name_runs). The tables are measured on the studies given (--measure-tables), read from
a file, or taken from tables.json, the members' own as SchwingNet measured them.

Every decision here is a pure function over the study form, plain dicts and numbers, with its
contracts; the only numpy-free geometry it needs, a 3 by 3 inverse, is written out. A study row
of this package's facts is read by study_of; a row of SchwingNet's ENHANCE.PET facts
(holdings/enhance_facts.py, by raw label) by study_from_enhance_facts.
"""
from __future__ import annotations

import json
import math
import os
from typing import Dict, List, Optional, Sequence, Tuple

from . import EXPECTED, LAST_LUMBARS, LEVEL_MIN_VOXELS, LUMBAR, ORDER, THORACIC, rank
from .contracts import beartype, ensure, require
from .stats import median, percentile

# ---------------------------------------------------------------- the mask rule's thresholds

# the levels the mask rule counts from C2 to L5: L5 missing is the no_l5 variant, read, not a gap
COUNTED = (*EXPECTED, "L5")
# a clear space wider than this between consecutive labels, more than any disc, holds a body with
# no label (count_enhance_pet's UNLABELLED_GAP_MM); above T12 it leaves the study out
UNLABELLED_GAP_MM = 20.0
# with no L5 label, every label from L4 down overlaps the next head to foot by 5 mm or more, as an
# L5 overlaps the sacrum in the shallowest of the 1,450 strict spines with no L6
NO_L5_MEETS_MM = -5.0
# an L5 label under a quarter of L4's voxels over an L4 that meets the sacrum is the no-L5 pattern
# with a sliver left behind
FRAGMENT_SHARE = 0.25
MASK_CLASSES = ("strict", "no_l5", "lumbar_look", "no_c2", "no_sacrum", "skipped_label", "unlabelled_body")

# ---------------------------------------------------------------- the field rule's thresholds

RULE_VERSION = 3
LOW_PERCENTILE, HIGH_PERCENTILE = 5.0, 95.0
# a table row needs this many spines to be read; fewer gives a border case, not a verdict
MIN_TABLE_SPINES = 20
# how much of S1 the field must hold below the sacrum's top: none since version 3
S1_VIEW_MM = 0.0
# a slice centre within half a slice of the field's edge is on the edge; 0.05 mm is the facts'
# rounding to 0.1 mm
EDGE_ROUNDING_MM = 0.05
# how far apart in the plane of a slice the structures that end at one padded plane lie: a body's
# width at the neck and at the pelvis
TILT_SPAN_MM = 100.0
# how far apart in the plane of a slice a level's own top and the cord or column top that marks the
# plane lie: a vertebra's depth
LEVEL_SPAN_MM = 40.0
# a missing name lies between two drawn levels when their centres are farther apart than this many
# times the study's own spacing of neighbouring levels nearby
ROOM_TIMES = 1.4
ROOM_PAIRS = 4
CHILD_UNDER_YEARS = 18
SMALL_COLUMN_MM = 300.0
TALL_LABEL_TIMES = 4

IN_VIEW, DRAWN, BORDER, OUT, NO_COLUMN = "in_view", "drawn", "border", "out", "no_column"
ENDS = (IN_VIEW, DRAWN, BORDER, OUT, NO_COLUMN)
ADMITTED, LOOK, NOT_ADMITTED = "admitted", "look", "not_admitted"
TABLES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tables.json")
# ENHANCE.PET's raw labels, for SchwingNet's facts rows: the hips 26 and 27 stand beside the column
ENHANCE_NAMES = {**{str(i): "C%d" % i for i in range(1, 8)}, **{str(7 + i): "T%d" % i for i in range(1, 13)},
                 **{str(19 + i): "L%d" % i for i in range(1, 7)}, "28": "sacrum"}


# ---------------------------------------------------------------- geometry, written out

@beartype
@require(lambda m: len(m) == 3 and all(len(row) == 3 for row in m), "a 3 by 3 matrix")
@require(lambda m: all(math.isfinite(x) for row in m for x in row), "finite entries")
def inverse3(m: Sequence[Sequence[float]]) -> List[List[float]]:
    """The inverse of a 3 by 3 matrix by cofactors; a singular grid raises ValueError."""
    a, b, c = m[0]
    d, e, f = m[1]
    g, h, i = m[2]
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if abs(det) < 1e-12:
        raise ValueError("a grid whose affine cannot be inverted: %r" % (m,))
    return [[(e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det],
            [(f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det],
            [(d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det]]


@beartype
@require(lambda affine: len(affine) >= 3 and all(len(row) == 4 for row in affine[:3]), "an affine of four columns")
@require(lambda shape: len(shape) == 3 and all(n >= 1 for n in shape), "three axes of at least one voxel")
@require(lambda point: len(point) == 3 and all(math.isfinite(x) for x in point), "a finite point in mm")
@ensure(lambda result: result[0] >= result[1], "the edge above lies at or above the edge below")
def vertical_edges(affine: Sequence[Sequence[float]], shape: Sequence[int], point: Sequence[float]) -> Tuple[float, float]:
    """Where the world's head-foot line through a point leaves the volume, upward and downward. On
    an untilted grid these are the faces' heights; on a tilted one the corners stand above or below."""
    inverse = inverse3([list(row[:3]) for row in affine[:3]])
    offset = [p - row[3] for p, row in zip(point, affine[:3])]
    start = [sum(inverse[r][c] * offset[c] for c in range(3)) for r in range(3)]
    along = [inverse[r][2] for r in range(3)]
    up = down = float("inf")
    for axis in range(3):
        if abs(along[axis]) < 1e-12:
            continue
        for bound in (-0.5, shape[axis] - 0.5):
            t = (bound - start[axis]) / along[axis]
            if t > 0:
                up = min(up, t)
            elif t < 0:
                down = min(down, -t)
    return point[2] + up, point[2] - down


@beartype
@require(lambda shape: len(shape) == 3 and all(n >= 1 for n in shape), "three axes of at least one voxel")
@require(lambda affine: len(affine) >= 3 and len(affine[2]) == 4, "an affine with a superior row of four")
def corner_heights(shape: Sequence[int], affine: Sequence[Sequence[float]]) -> List[float]:
    """The head-foot positions of the volume's outer voxel faces at its eight corners."""
    row = affine[2]
    return [row[0] * i + row[1] * j + row[2] * k + row[3]
            for i in (-0.5, shape[0] - 0.5) for j in (-0.5, shape[1] - 0.5) for k in (-0.5, shape[2] - 0.5)]


@beartype
@require(lambda affine: len(affine) >= 3 and len(affine[2]) >= 3, "an affine with a superior row")
@require(lambda axis: 0 <= axis <= 2, "a voxel axis")
def tilted(affine: Sequence[Sequence[float]], axis: int) -> bool:
    """Whether the superior row leans on any voxel axis but the head-foot one."""
    return any(abs(affine[2][i]) > 1e-9 for i in range(3) if i != axis)


# ---------------------------------------------------------------- the study form

def _enhance_level(entry: dict, top: float, bottom: float, step: float) -> dict:
    """ENHANCE.PET's facts give no faces: a level whose head-most or foot-most voxel centre lies in
    the field's first or last slice reaches that face. Its grids are untilted, so the field over
    every level is the volume's."""
    half = step / 2 + EDGE_ROUNDING_MM
    return {"voxels": entry["voxels"], "top": entry["top_mm"], "bottom": entry["bottom_mm"],
            "head_cut": top - entry["top_mm"] <= half, "foot_cut": entry["bottom_mm"] - bottom <= half,
            "side_cut": None, "field_top": top, "field_bottom": bottom, "centre": entry["centroid_mm"][2]}


def study_from_enhance_facts(row: dict, member: str = "enhance_pet") -> dict:
    """The study form of a row of SchwingNet's ENHANCE.PET facts (labels by raw label, the grid
    under mask); a tilted grid is refused, since the slice-edge rule does not measure one."""
    mask = row["mask"]
    if tilted(mask["affine"], mask["head_foot_axis"]):
        raise ValueError("%s %s: a tilted grid, which the slice-edge rule does not measure" % (member, row["id"]))
    heights = corner_heights(mask["shape"], mask["affine"])
    top, bottom = max(heights), min(heights)
    step = abs(mask["affine"][2][mask["head_foot_axis"]])
    levels = {ENHANCE_NAMES[label]: _enhance_level(entry, top, bottom, step)
              for label, entry in row["labels"].items() if label in ENHANCE_NAMES}
    return {"member": member, "id": row["id"], "top": top, "bottom": bottom, "levels": levels,
            "person": row.get("person"), "age": None, "site": row.get("site"), "image_planes": [False, False]}


def column_field(row: dict, entry: dict) -> Tuple[float, float]:
    """The field's top and bottom over a level: the grid's faces as the facts give them, moved by
    how far the world's head-foot line through the level's centre leaves the volume below the
    highest corner, or above the lowest, which is nothing on an untilted grid."""
    grid, field = row["grid"], row["field_mm"]
    if not tilted(grid["affine"], grid["head_foot_axis"]):
        return field["top"], field["bottom"]
    heights = corner_heights(grid["shape"], grid["affine"])
    up, down = vertical_edges(grid["affine"], grid["shape"], entry["centroid_mm"])
    return round(field["top"] - (max(heights) - up), 1), round(field["bottom"] + (down - min(heights)), 1)


def plane_slack(grid: dict, span: float = TILT_SPAN_MM) -> float:
    """How far apart structures that one plane of the grid cuts may end: a slice, the facts'
    rounding, and how much the plane's height changes across `span` in the slice's plane."""
    axis, affine, zooms = grid["head_foot_axis"], grid["affine"], grid["zooms"]
    tilt = sum(abs(affine[2][i]) * span / zooms[i] for i in range(3) if i != axis)
    return zooms[axis] + EDGE_ROUNDING_MM + tilt


def image_planes(row: dict) -> Tuple[Optional[float], Optional[float]]:
    """The head-most and foot-most planes the image reaches, where they lie inside the grid; else
    None. Where the spinal cord and the column stop together at the highest (or lowest) height
    anything is drawn, with grid left beyond it, the image ends there and the slices beyond hold
    padding, not anatomy; the plane is given at the column."""
    context = row.get("context", {})
    cord = context.get("spinal_cord")
    if not cord:
        return None, None
    slack = plane_slack(row["grid"])
    drawn_here = [e for e in (*row["levels"].values(), *context.values()) if e["voxels"] > 0]
    column = [e for e in row["levels"].values() if e["voxels"] >= LEVEL_MIN_VOXELS]
    if not column:
        return None, None
    highest = max(e["top_mm"] for e in drawn_here)
    lowest = min(e["bottom_mm"] for e in drawn_here)
    column_top = max(cord["top_mm"], max(e["top_mm"] for e in column))
    column_foot = min(cord["bottom_mm"], min(e["bottom_mm"] for e in column))
    top = (column_top if "S" not in cord["faces"] and highest - cord["top_mm"] <= slack
           and highest - max(e["top_mm"] for e in column) <= slack else None)
    foot = (column_foot if "I" not in cord["faces"] and cord["bottom_mm"] - lowest <= slack
            and min(e["bottom_mm"] for e in column) - lowest <= slack else None)
    return top, foot


def _named_level(row: dict, entry: dict, planes: tuple, slack: float) -> dict:
    faces = set(entry["faces"])
    field_top, field_bottom = column_field(row, entry)
    top_plane, foot_plane = planes
    step = row["grid"]["zooms"][row["grid"]["head_foot_axis"]]
    head_cut, foot_cut = "S" in faces, "I" in faces
    if top_plane is not None:
        field_top = min(field_top, round(top_plane + step / 2, 1))
        head_cut = head_cut or top_plane - entry["top_mm"] <= slack
    if foot_plane is not None:
        field_bottom = max(field_bottom, round(foot_plane - step / 2, 1))
        foot_cut = foot_cut or entry["bottom_mm"] - foot_plane <= slack
    return {"voxels": entry["voxels"], "top": entry["top_mm"], "bottom": entry["bottom_mm"],
            "head_cut": head_cut, "foot_cut": foot_cut, "side_cut": bool(faces & set("LRAP")),
            "field_top": field_top, "field_bottom": field_bottom, "centre": entry["centroid_mm"][2]}


def study_of(row: dict, age: Optional[float] = None, site: Optional[str] = None) -> dict:
    """The study form of a row of this package's facts (level names, faces, the grid under grid)."""
    planes = image_planes(row)
    slack = plane_slack(row["grid"], LEVEL_SPAN_MM)
    step = row["grid"]["zooms"][row["grid"]["head_foot_axis"]]
    top = row["field_mm"]["top"] if planes[0] is None else round(planes[0] + step / 2, 1)
    bottom = row["field_mm"]["bottom"] if planes[1] is None else round(planes[1] - step / 2, 1)
    return {"member": row.get("member", ""), "id": row["id"], "top": top, "bottom": bottom,
            "levels": {name: _named_level(row, e, planes, slack) for name, e in row["levels"].items()},
            "person": row.get("person"), "age": age, "site": site, "image_planes": [p is not None for p in planes]}


def study_from_row(row: dict, age: Optional[float] = None) -> dict:
    """Either facts form into the study form: SchwingNet's ENHANCE.PET rows carry labels and
    mask, this package's rows levels and grid."""
    if "labels" in row and "mask" in row:
        return study_from_enhance_facts(row)
    return study_of(row, age, row.get("site"))


# ---------------------------------------------------------------- what is drawn

def drawn(study: dict, name: str) -> Optional[dict]:
    """A level's entry when its mask holds LEVEL_MIN_VOXELS voxels or more, else None."""
    level = study["levels"].get(name)
    return level if level and level["voxels"] >= LEVEL_MIN_VOXELS else None


def drawn_names(study: dict) -> List[str]:
    return [name for name in ORDER if drawn(study, name)]


def drawn_below(study: dict, name: str) -> Optional[str]:
    """The first drawn level below a name, C1 and the sacrum aside."""
    later = [n for n in drawn_names(study) if n not in ("C1", "sacrum") and rank(n) > rank(name)]
    return later[0] if later else None


def head_most(study: dict) -> Optional[str]:
    """The head-most drawn level, the sacrum aside; C1 alone above an undrawn C2 says C2 lies under it."""
    names = [name for name in drawn_names(study) if name != "sacrum"]
    return names[0] if names else None


def foot_most(study: dict) -> Optional[str]:
    names = [name for name in drawn_names(study) if name != "sacrum"]
    return names[-1] if names else None


def whole(level: Optional[dict]) -> bool:
    return level is not None and not level["head_cut"] and not level["foot_cut"]


# ---------------------------------------------------------------- the mask rule

@beartype
@require(lambda upper, lower: all(math.isfinite(v) for v in (upper["bottom"], lower["top"])), "finite extents")
def gap_mm(upper: dict, lower: dict) -> float:
    """mm from the foot-most edge of the upper level to the head-most edge of the lower; negative
    where they overlap."""
    return round(upper["bottom"] - lower["top"], 1)


def links(study: dict) -> List[Tuple[str, str, float]]:
    """Each drawn level with the drawn level below it, C2 down to the sacrum, and the space between."""
    names = [n for n in drawn_names(study) if n != "C1"]
    return [(upper, lower, gap_mm(drawn(study, upper), drawn(study, lower))) for upper, lower in zip(names, names[1:])]


def lumbar_tail_meets(study: dict) -> bool:
    """Whether every drawn level from L4 down overlaps the next as deeply as an L5 overlaps the sacrum."""
    return all(gap <= NO_L5_MEETS_MM for upper, _, gap in links(study) if rank(upper) >= rank("L4"))


def missing_levels(study: dict, last: str = "L5") -> List[str]:
    return [n for n in COUNTED if rank(n) <= rank(last) and not drawn(study, n)]


@ensure(lambda result: result in MASK_CLASSES, "one of the mask rule's classes")
def count_class(study: dict) -> str:
    """count_enhance_pet's class: strict, no_l5, lumbar_look (all three whole), or why it is not whole."""
    if not drawn(study, "C2"):
        return "no_c2"
    if not drawn(study, "sacrum"):
        return "no_sacrum"
    missing = missing_levels(study)
    wide = [link for link in links(study) if link[2] > UNLABELLED_GAP_MM]
    if any(rank(n) < rank("L1") for n in missing):
        return "skipped_label"
    if any(rank(upper) < rank("T12") for upper, _, _ in wide):
        return "unlabelled_body"
    if not missing and not wide:
        return "strict"
    if missing == ["L5"] and not wide and lumbar_tail_meets(study):
        return "no_l5"
    return "lumbar_look"


def whole_problems(study: dict) -> List[str]:
    """Why a study is not whole by the masks, in words; empty for a whole study."""
    ends = ["no %s" % name for name in ("C2", "sacrum") if not drawn(study, name)]
    if ends:
        return ends
    skipped = ["%s missing" % n for n in missing_levels(study, "T12")]
    wide = ["a space of %s mm between %s and %s" % (gap, upper, lower)
            for upper, lower, gap in links(study) if gap > UNLABELLED_GAP_MM and rank(upper) < rank("T12")]
    return skipped + wide


def l5_fragment(study: dict) -> bool:
    l4, l5, sacrum = drawn(study, "L4"), drawn(study, "L5"), drawn(study, "sacrum")
    if not (l4 and l5 and sacrum):
        return False
    return l5["voxels"] < FRAGMENT_SHARE * l4["voxels"] and gap_mm(l4, sacrum) <= NO_L5_MEETS_MM


def label_pattern(study: dict) -> str:
    """What the dataset's lumbar names say, in words."""
    has = lambda name: drawn(study, name) is not None
    if not has("L5") and has("L6"):
        return "no L5, an L6 in its place"
    if not has("L5") and has("L4"):
        return "no L5, L4 meeting the sacrum" if lumbar_tail_meets(study) else "no L5"
    absent = [n for n in LUMBAR[:4] if not has(n)]
    if absent:
        return "lumbar label missing: " + ", ".join(absent)
    if has("L6"):
        return "L6 named below an L5"
    if l5_fragment(study):
        return "L5 label a fragment, L4 meeting the sacrum"
    return "C2 to L5 named"


def call_by_names(study: dict) -> dict:
    """The dataset's column call: T{thoracic levels drawn}L{lumbar levels drawn}, and the bodies
    above the sacrum, C1 counted as present where the field's top cut it off and C2 is there."""
    names = set(drawn_names(study))
    thoracic = sum(1 for n in THORACIC if n in names)
    lumbar = sum(1 for n in LUMBAR if n in names)
    presacral = sum(1 for n in ORDER[:-1] if n in names) + ("C1" not in names and "C2" in names)
    return {"thoracic": thoracic, "lumbar": lumbar, "presacral": presacral, "call": "T%dL%d" % (thoracic, lumbar)}


# ---------------------------------------------------------------- the head and foot tables

def summary(values: Sequence[float]) -> dict:
    if len(values) < MIN_TABLE_SPINES:
        return {"n": len(values)}
    return {"n": len(values), "low": round(percentile(values, LOW_PERCENTILE), 1),
            "median": round(median(values), 1), "high": round(percentile(values, HIGH_PERCENTILE), 1)}


def head_pairs(studies: Sequence[dict]) -> Dict[str, List[float]]:
    """For each level below C2, how far C2's top and C2's foot-most voxel lie above that level's
    top, in spines that draw both whole."""
    pairs: Dict[str, List[float]] = {}
    for study in studies:
        c2 = drawn(study, "C2")
        if not whole(c2):
            continue
        for name in ORDER[rank("C3"):rank("sacrum")]:
            level = drawn(study, name)
            if whole(level):
                pairs.setdefault(name, []).append(c2["top"] - level["top"])
                pairs.setdefault("%s to C2's foot" % name, []).append(c2["bottom"] - level["top"])
    return pairs


def foot_pairs(studies: Sequence[dict]) -> Dict[str, List[float]]:
    """For each level above the sacrum, where the sacrum's top lies against that level's foot-most
    voxel, in spines that draw both whole (positive above it); the last lumbar, whatever its name,
    its own row."""
    pairs: Dict[str, List[float]] = {}
    for study in studies:
        sacrum = drawn(study, "sacrum")
        if sacrum is None or sacrum["head_cut"]:
            continue
        last = foot_most(study)
        for name in drawn_names(study):
            level = drawn(study, name)
            if name == "sacrum" or not whole(level):
                continue
            pairs.setdefault(name, []).append(sacrum["top"] - level["bottom"])
            if name == last and name in LAST_LUMBARS:
                pairs.setdefault("last lumbar", []).append(sacrum["top"] - level["bottom"])
    return pairs


def order_key(item: tuple) -> tuple:
    """Head to foot by the level a row starts from, a level's own row before its second; the last
    lumbar after L6."""
    name = item[0]
    level = name.split(" ")[0]
    return (rank(level) if level in ORDER else rank("sacrum")), name != level


def tables(studies: Sequence[dict]) -> dict:
    return {"head": {name: summary(v) for name, v in sorted(head_pairs(studies).items(), key=order_key)},
            "foot": {name: summary(v) for name, v in sorted(foot_pairs(studies).items(), key=order_key)}}


def default_tables() -> dict:
    """The members' tables as SchwingNet measured them (tables.json), head and foot."""
    with open(TABLES, encoding="ascii") as f:
        return json.load(f)["tables"]


# ---------------------------------------------------------------- the two ends

@ensure(lambda result: result[0] in ENDS, "one of the five words for an end")
def head_end(study: dict, table: dict) -> Tuple[str, dict]:
    """drawn, in_view, border, out or no_column, with the numbers it rests on."""
    c2 = drawn(study, "C2")
    if c2:
        below = drawn_below(study, "C2")
        if c2["head_cut"] and below and drawn(study, below)["head_cut"]:
            return OUT, {"why": "C2 and %s are both cut by the field's top: the field holds a sliver of C2" % below}
        return DRAWN, {}
    top = head_most(study)
    if top is None:
        return NO_COLUMN, {}
    if top == "C1":
        if foot_most(study) == "C1":
            return BORDER, {"why": "C1 drawn alone: C2 lies at or under the field's foot"}
        return IN_VIEW, {"why": "C1 drawn above an undrawn C2, with levels drawn below it"}
    level = drawn(study, top)
    if level["head_cut"]:
        return OUT, {"why": "%s, the head-most drawn level, is cut by the field's top" % top}
    return _head_by_table(top, level, table.get("%s to C2's foot" % top, {}))


def _head_by_table(top: str, level: dict, foot: dict) -> Tuple[str, dict]:
    margin = round(level["field_top"] - level["top"], 1)
    numbers = {"from": top, "field_above_mm": margin, "c2_foot_above_mm": [foot.get("low"), foot.get("high")]}
    if "high" not in foot or "low" not in foot:
        return BORDER, {**numbers, "why": "fewer than %d spines measure C2 above %s" % (MIN_TABLE_SPINES, top)}
    if margin >= foot["high"]:
        return IN_VIEW, numbers
    return (OUT if margin < foot["low"] else BORDER), numbers


def sacrum_held(study: dict) -> Optional[float]:
    """How many mm of the sacrum the field holds below its top, where the field's foot cuts a
    sacrum label of any size; else None."""
    sacrum = study["levels"].get("sacrum")
    if not sacrum or sacrum["voxels"] == 0 or not sacrum["foot_cut"]:
        return None
    return round(sacrum["top"] - sacrum["field_bottom"], 1)


@ensure(lambda result: result[0] in ENDS, "one of the five words for an end")
def foot_end(study: dict, table: dict, s1_view: float = S1_VIEW_MM) -> Tuple[str, dict]:
    """The same for the sacrum: one the dataset draws is drawn, however little of it the field
    holds; an undrawn sacrum is placed from the foot-most drawn level by the foot table. s1_view,
    none in the rule, asks for that much of S1 below the sacrum's top, as version 2 asked 20 mm."""
    last = foot_most(study)
    if last is None:
        return (DRAWN if drawn(study, "sacrum") else NO_COLUMN), {}
    level = drawn(study, last)
    held = sacrum_held(study)
    if held is not None and held < s1_view:
        numbers = {"sacrum_in_field_mm": held}
        if level["foot_cut"]:
            return OUT, {**numbers, "why": "%s is cut by the field's foot, and the field holds %s mm of the sacrum "
                                          "below its top, under %g mm of S1" % (last, held, s1_view)}
        return BORDER, {**numbers, "why": "the field's foot cuts the sacrum %s mm below its top, under %g mm of S1"
                                         % (held, s1_view)}
    if drawn(study, "sacrum"):
        return DRAWN, {}
    if level["foot_cut"]:
        return OUT, {"why": "%s, the foot-most drawn level, is cut by the field's foot" % last}
    return _foot_by_table(last, level, table.get("last lumbar" if last in LAST_LUMBARS else last, {}), s1_view)


def _foot_by_table(last: str, level: dict, row: dict, s1_view: float) -> Tuple[str, dict]:
    numbers = {"from": last, "field_below_mm": round(level["bottom"] - level["field_bottom"], 1),
               "sacrum_top_from_level_mm": [row.get("low"), row.get("high")]}
    if "high" not in row:
        return BORDER, {**numbers, "why": "fewer than %d spines measure the sacrum below %s" % (MIN_TABLE_SPINES, last)}
    lowest_top, highest_top = level["bottom"] + row["low"], level["bottom"] + row["high"]
    if level["field_bottom"] <= lowest_top - s1_view:
        return IN_VIEW, numbers
    return (OUT if level["field_bottom"] > highest_top else BORDER), numbers


@beartype
@require(lambda head, foot: head in ENDS and foot in ENDS, "each end one of the five words")
@ensure(lambda result: result in (ADMITTED, LOOK, NOT_ADMITTED), "a verdict")
def verdict_of(head: str, foot: str) -> str:
    """admitted when both ends are drawn or in view, not_admitted when either is out or there is
    no column, look for a border case at either end."""
    if head in (OUT, NO_COLUMN) or foot in (OUT, NO_COLUMN):
        return NOT_ADMITTED
    return ADMITTED if {head, foot} <= {DRAWN, IN_VIEW} else LOOK


# ---------------------------------------------------------------- what a segmenter must draw

def name_runs(study: dict) -> Tuple[List[str], List[str]]:
    """(gaps, skipped): the expected levels undrawn between two drawn ones, split by whether those
    two leave room for a body between them. Two names or more, a lower level whose centre is not
    below the upper's, or a study with no neighbouring pair to measure, are gaps."""
    names = drawn_names(study)
    gaps, skipped = [], []
    for upper, lower in zip(names, names[1:]):
        missing = [n for n in EXPECTED if rank(upper) < rank(n) < rank(lower)]
        if lower in ("sacrum", "L6") and rank(upper) < rank("L4" if lower == "sacrum" else "L5"):
            missing.append("L5")
        if missing:
            (gaps if room_between(study, upper, lower, missing) else skipped).extend(missing)
    return gaps, skipped


def room_between(study: dict, upper: str, lower: str, missing: Sequence[str]) -> bool:
    spacing = drawn(study, upper)["centre"] - drawn(study, lower)["centre"]
    reference = nearby_spacing(study, upper, lower)
    return len(missing) > 1 or spacing <= 0 or reference is None or spacing > ROOM_TIMES * reference


def nearby_spacing(study: dict, upper: str, lower: str) -> Optional[float]:
    """The median spacing of the centres of the ROOM_PAIRS pairs of drawn levels next to each other
    in the order nearest the run between upper and lower; C1, C2 and the sacrum are left out."""
    names = [n for n in drawn_names(study) if n not in ("C1", "C2", "sacrum")]
    middle = (rank(upper) + rank(lower)) / 2
    pairs = [(abs((rank(a) + rank(b)) / 2 - middle), drawn(study, a)["centre"] - drawn(study, b)["centre"])
             for a, b in zip(names, names[1:]) if rank(b) == rank(a) + 1]
    nearest = [spacing for _, spacing in sorted(pairs)[:ROOM_PAIRS]]
    return median(nearest) if nearest else None


def completion(study: dict, head: str, foot: str) -> List[str]:
    """The levels from C2 to the sacrum a segmenter must add to an admitted study."""
    add = set(name_runs(study)[0])
    top, last = head_most(study), foot_most(study)
    if head == IN_VIEW and top not in (None, "C1"):
        add |= {n for n in EXPECTED if rank(n) < rank(top) and not drawn(study, n)}
    if head == IN_VIEW and top == "C1":
        add.add("C2")
    if foot == IN_VIEW:
        add.add("sacrum")
        if last not in LAST_LUMBARS and rank(last) < rank("L4"):
            add |= {n for n in (*EXPECTED, "L5") if rank(n) > rank(last) and not drawn(study, n)}
    return [n for n in ORDER if n in add]


def column_length(study: dict) -> Optional[float]:
    """C2's top to L1's foot, where both are drawn whole; else None."""
    c2, l1 = drawn(study, "C2"), drawn(study, "L1")
    return round(c2["top"] - l1["bottom"], 1) if whole(c2) and whole(l1) else None


def tall_labels(study: dict) -> List[str]:
    names = [n for n in drawn_names(study) if n != "sacrum"]
    if len(names) < 3:
        return []
    heights = {n: study["levels"][n]["top"] - study["levels"][n]["bottom"] for n in names}
    middle = median(list(heights.values()))
    return [n for n in names if heights[n] > TALL_LABEL_TIMES * middle]


def flags(study: dict, head: str, foot: str) -> List[str]:
    out = []
    c2, sacrum = drawn(study, "C2"), study["levels"].get("sacrum")
    if c2 and c2["head_cut"]:
        out.append("c2_at_field_top")
    if sacrum and sacrum["voxels"] > 0 and sacrum["foot_cut"]:
        out.append("sacrum_at_field_foot")
    last = foot_most(study)
    if drawn(study, "sacrum") and last and drawn(study, last)["foot_cut"]:
        out.append("level_past_sacrum_top")
    if name_runs(study)[1]:
        out.append("name_skipped")
    if any(drawn(study, n)["side_cut"] for n in drawn_names(study) if n != "C1"):
        out.append("cut_in_plane")
    if not drawn(study, "L5") and drawn(study, "L4") and not drawn(study, "L6") and foot in (DRAWN, IN_VIEW):
        out.append("no_l5")
    return out + _study_flags(study)


def _study_flags(study: dict) -> List[str]:
    out = []
    if any(0 < e["voxels"] < LEVEL_MIN_VOXELS for e in study["levels"].values()):
        out.append("stray_labels")
    if study.get("age") is not None and study["age"] < CHILD_UNDER_YEARS:
        out.append("child")
    length = column_length(study)
    if length is not None and length < SMALL_COLUMN_MM:
        out.append("small_column")
    if tall_labels(study):
        out.append("label_spans_levels")
    return out


def to_complete(study: dict, verdict: str, head: str, foot: str) -> List[str]:
    """The completion list of an admitted study; of a border case, the list should a person's look
    admit it; none for a study not admitted."""
    if verdict == NOT_ADMITTED:
        return []
    if verdict == LOOK:
        head = IN_VIEW if head == BORDER and not drawn(study, "C2") else (DRAWN if head == BORDER else head)
        foot = IN_VIEW if foot == BORDER and not drawn(study, "sacrum") else (DRAWN if foot == BORDER else foot)
    return completion(study, head, foot)


def judge(study: dict, table: dict, s1_view: float = S1_VIEW_MM) -> dict:
    """One study's verdict by the field, its two ends with their numbers, the levels to add and the flags."""
    head, head_numbers = head_end(study, table["head"])
    foot, foot_numbers = foot_end(study, table["foot"], s1_view)
    verdict = verdict_of(head, foot)
    return {"member": study["member"], "id": study["id"], "person": study["person"], "verdict": verdict,
            "head": head, "foot": foot, "head_numbers": head_numbers, "foot_numbers": foot_numbers,
            "complete": to_complete(study, verdict, head, foot), "flags": flags(study, head, foot)}


# ---------------------------------------------------------------- both readings of one study

VERDICT_FIELDS = ("member", "id", "person", "count_class", "problems", "pattern", "call", "presacral",
                  "verdict", "head", "foot", "complete", "flags", "head_numbers", "foot_numbers")


def verdict_row(study: dict, table: dict, s1_view: float = S1_VIEW_MM) -> dict:
    """The mask rule's class and the field rule's verdict of one study, one CSV row."""
    field = judge(study, table, s1_view)
    call = call_by_names(study)
    return {"member": study["member"], "id": study["id"], "person": study.get("person") or "",
            "count_class": count_class(study), "problems": "; ".join(whole_problems(study)),
            "pattern": label_pattern(study), "call": call["call"], "presacral": call["presacral"],
            "verdict": field["verdict"], "head": field["head"], "foot": field["foot"],
            "complete": " ".join(field["complete"]), "flags": " ".join(field["flags"]),
            "head_numbers": json.dumps(field["head_numbers"], sort_keys=True),
            "foot_numbers": json.dumps(field["foot_numbers"], sort_keys=True)}


def counts(rows: Sequence[dict], key: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for row in rows:
        out[str(row[key])] = out.get(str(row[key]), 0) + 1
    return dict(sorted(out.items()))
