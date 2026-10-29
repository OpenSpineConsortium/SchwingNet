"""The field test of the gold tier 3 CT dataset: which CT volumes show the whole spine, C2 to the sacrum,
whatever their masks hold, and which levels a segmenter must draw to complete each.

Source: the thread "Complete every full-spine CT for gold tier 3", 2026-10-28, for the owner's answer of
22:58 UTC on the admission rule of VerSe and TotalSegmentator (#443): "essentially if the full spune is in
view in the volume, and just missing a mask or two, that should just be completed using a segmentation
software of choice ... i dont think i should leave out any spines that have ct volumes with the full spine
in view, i should do whatever is necessary to get them ready for usage". docs/research/gold3-ct/ is the
programme's folder and ADMISSION.md, written by this file, its page for the rule. Confidential, like the
rest of SchwingNet: nothing here, and nothing it writes, goes to a public place.

The rule, version 3, is version 2 with the owner's two ends of 2026-10-29 12:58 UTC: "If the top of the
sacrum is visible that is acceptable, which I believe is all of them but check" and "Same for the bottom
c2". Version 2 replaced version 1's whole-by-the-masks rule (data/gold3-ct/members.json): a CT is admitted
when its field holds the foot of C2 and the top of the sacrum, whatever its masks hold. A level is drawn
when its mask holds at least LEVEL_MIN_VOXELS voxels. The head end is in view when C2 is drawn, wherever
the field cuts it, since a person drew what the CT shows (a C2 in the field's top slice is flagged for a
look), unless the level below C2 is cut by the field's top too, when the field holds a sliver of C2 and
the end is out; or when C2 is not drawn and the field reaches far enough above the head-most drawn level
that C2's foot lies under the field's top in 95 of 100 spines that draw both (the head table); it is out
when that level is cut by the field's top, or when the field ends below where C2's foot lies in 95 of 100
spines. The foot end is in view when the sacrum is drawn, however little of it the field holds, since a
drawn sacrum's top is in the field; or when the sacrum is not drawn and the field's foot lies below where
the sacrum's top lies in 95 of 100 spines that draw both, from the foot-most drawn level (the foot table),
out when that level is cut by the field's foot or the field ends above where the sacrum's top lies in 95
of 100 spines. A study between in view and out of view at either end is a border case, admitted only after
a person's look. The tables are measured here on the members' own masks, never assumed. Version 2 asked
for 20 mm of S1 below the sacrum's top and for C2 whole under the field's top; ADMISSION.md gives the
counts with S1 asked for beside the rule's.

The field is measured at the column, not at the volume's corners: on a tilted grid the faces are tilted
planes, so the field's top over a level is where the world's head-foot line through the level's centre
leaves the volume. TotalSegmentator's CTs are sometimes padded inside their grid with slices that hold no
image; there the spinal cord, which runs on above every cervical level and below the conus, stops with
the column at one plane, and that plane over the column, not the grid's face, is the field's edge
(image_planes); a level is cut by it within a slice and the plane's tilt across a vertebra's depth.

A name the column's order expects and no mask draws, between two drawn levels, is a level to add when the
two levels' centres stand farther apart than the study's own spacing of neighbours allows, and a count
variant or a skipped label, flagged and never added, when they do not (name_runs).

A mask that lies on its CT's grid gives the CT's field: TotalSegmentator's and ENHANCE.PET's masks share
their CT's header by release, and VerSe's were checked against every CT's header (data/gold3-ct/verse/
FACTS.json). What the rule admits but no mask draws is the completion list of each study: the levels from
C2 to the sacrum a segmenter must add, kept as a machine mask of its own, recorded apart and never
pooled with SPINEPS or with the release's masks, and never raising a tier.

    python3 tools/gold3_field.py write     # data/gold3-ct/admission.json and docs/research/gold3-ct/ADMISSION.md
    python3 tools/gold3_field.py check     # exit 1 when either differs from what the facts give
    python3 tools/gold3_field.py show ID   # one study's verdict and the numbers behind it
    python3 tools/gold3_field.py take MEMBER FACTS.jsonl --read-on TEXT --bordercall-commit SHA --source TEXT
                                           # bordercall's reading of a member's masks into data/gold3-ct/<member>/

Everything here is the standard library over committed files.
"""

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = "data/gold3-ct"
ENHANCE_FACTS = f"{DATA}/enhance-pet/facts.jsonl"
VERSE_FACTS = f"{DATA}/verse/facts.jsonl"
VERSE_SERIES = f"{DATA}/verse/series.json"
TOTALSEG_FACTS = f"{DATA}/totalsegmentator/facts.jsonl"
TOTALSEG_SUBJECTS = f"{DATA}/totalsegmentator/subjects.json"
FACTS_OF = {"verse": VERSE_FACTS, "totalsegmentator": TOTALSEG_FACTS}
READER = "bordercall holdings/fullspine_facts.py"
ADMISSION = f"{DATA}/admission.json"
PAGE = "docs/research/gold3-ct/ADMISSION.md"
MEMBER_ORDER = ("enhance_pet", "verse", "totalsegmentator")
RULE_VERSION = 3

# ---------------------------------------------------------------- the column

CERVICAL = tuple(f"C{i}" for i in range(1, 8))
THORACIC = tuple(f"T{i}" for i in range(1, 13))
LUMBAR = tuple(f"L{i}" for i in range(1, 6))
# Head to foot, with the two variant levels where they sit; C1 stands above the count, which starts at C2.
ORDER = (*CERVICAL, *THORACIC, "T13", *LUMBAR, "L6", "sacrum")
# The levels every spine has from C2 to L4: an undrawn one between two drawn ones is a gap to complete.
# L5, T13 and L6 are left out, since four lumbar, a thirteenth thoracic and a sixth lumbar are variants
# the count reads, not masks to add.
EXPECTED = (*CERVICAL[1:], *THORACIC, *LUMBAR[:4])
LAST_LUMBARS = ("L4", "L5", "L6")
# ENHANCE.PET's label numbers (data/gold3-ct/members.json, scheme): the hips 26 and 27 stand beside the column.
ENHANCE_NAMES = {**{str(i): f"C{i}" for i in range(1, 8)}, **{str(7 + i): f"T{i}" for i in range(1, 13)},
                 **{str(19 + i): f"L{i}" for i in range(1, 7)}, "28": "sacrum"}

# ---------------------------------------------------------------- thresholds, each with its reason

# A level is drawn when its mask holds at least this many voxels: version 1's floor (tools/gold3_ct.py
# LEVEL_MIN_VOXELS, from bordercall's holdings/count_enhance_pet.py), under which a label is a stray.
LEVEL_MIN_VOXELS = 200
# The head and foot tables are read at these percentiles: in view needs the 95th, so C2's foot lies under
# the field's top, or the sacrum's top above the field's bottom, in 95 of 100 spines that draw both.
LOW_PERCENTILE, HIGH_PERCENTILE = 5, 95
# A table row needs this many spines to be read; a level with fewer gives a border case, not a verdict.
MIN_TABLE_SPINES = 20
# How much of S1 must be in the field below the top of the sacrum: none since version 3, the owner's "If the
# top of the sacrum is visible that is acceptable" (2026-10-29 12:58 UTC). Version 2 asked 20 mm, the L5-S1
# disc and the top of S1's body; ADMISSION.md gives the counts at 10, 20 and 30 mm beside the rule's.
S1_VIEW_MM = 0.0
S1_VIEW_SENSITIVITY = (10.0, 20.0, 30.0)
# A slice centre within half a slice of the field's edge is on the edge: ENHANCE.PET's facts carry no
# faces, so its cut levels are read from the head-foot positions, as tools/gold3_ct.py's Q06 reads C2.
# The 0.05 mm is the facts' rounding to 0.1 mm.
EDGE_ROUNDING_MM = 0.05
# How far apart in the plane of a slice the structures that end at one padded plane lie (the cord, the
# vertebral body, the skull or the hips): on a tilted grid the plane's height changes across that span,
# so structures it cuts end up to that change apart. 100 mm is a body's width at the neck and at the pelvis.
TILT_SPAN_MM = 100.0
# How far apart in the plane of a slice a level's own top and the cord or column top that marks the plane
# lie: a vertebra's depth, from its body's front to the canal behind it. On a tilted grid a level is cut
# by a padded plane only within the change of the plane's height across this span, not across the body.
LEVEL_SPAN_MM = 40.0
# A missing name lies between two drawn levels when their centres are farther apart than this many times
# the study's own spacing of neighbouring levels nearby. Over every whole level of the three members,
# neighbours lie 1.01 times that spacing apart at the median and above 1.4 times in 84 of 49,719 pairs;
# with one level hidden between them, 2.03 at the median and at or below 1.4 in 120 of 45,454, nearly all
# in studies whose labels run out of order. Their extremes cannot tell the two apart, since neighbours
# overlap by their facets and so do levels two apart in the thoracic and lower cervical spine.
ROOM_TIMES = 1.4
# The neighbouring pairs nearest a missing name whose spacing the study's own is read from.
ROOM_PAIRS = 4
# Under 18 at the scan is a child's spine: flagged, never left out, since the rule asks for the whole
# spine in view and says nothing of age.
CHILD_UNDER_YEARS = 18
# A column from C2's top to L1's foot shorter than this is a child's whatever age is recorded: of the
# members' 130 spines recorded 18 to 89 that draw both whole, all but four are longer than 330 mm: s1931,
# recorded 77, at 330 mm, and three (TotalSegmentator s1411, s1532 and s2065, under 233 mm) recorded 21 to
# 25 with the column of a child under five; the 22 recorded under 18 have a median of 285 mm. Flagged,
# never left out.
SMALL_COLUMN_MM = 300.0
# A drawn level taller than this many times the median of the study's drawn levels holds voxels far from
# its body, scattered or mislabelled, so the top and foot the rule reads may not be the body's. Flagged.
TALL_LABEL_TIMES = 4

IN_VIEW, DRAWN, BORDER, OUT, NO_COLUMN = "in_view", "drawn", "border", "out", "no_column"
ADMITTED, LOOK, NOT_ADMITTED = "admitted", "look", "not_admitted"


class FieldError(Exception):
    """A file or a row the field test refuses, with the reason a person reads."""


# ---------------------------------------------------------------- reading the committed files


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise FieldError(f"{path}: {error}") from error


def read_jsonl(path):
    rows = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        try:
            rows.append(json.loads(line))
        except ValueError as error:
            raise FieldError(f"{path}: line {number}: {error}") from error
    return rows


def load_inputs(repo=ROOT):
    repo = Path(repo)
    return {"enhance_pet": read_jsonl(repo / ENHANCE_FACTS), "verse": read_jsonl(repo / VERSE_FACTS),
            "totalsegmentator": read_jsonl(repo / TOTALSEG_FACTS), "verse_series": read_json(repo / VERSE_SERIES),
            "totalseg_subjects": read_json(repo / TOTALSEG_SUBJECTS)}


# ---------------------------------------------------------------- one study, in level names


def inverse3(m):
    a, b, c = m[0]
    d, e, f = m[1]
    g, h, i = m[2]
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if abs(det) < 1e-12:
        raise FieldError(f"a grid whose affine cannot be inverted: {m}")
    return [[(e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det],
            [(f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det],
            [(d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det]]


def vertical_edges(affine, shape, point):
    """Where the world's head-foot line through a point leaves the volume, upward and downward. On an
    untilted grid these are the faces' heights; on a tilted one the corners stand above or below them."""
    inverse = inverse3([row[:3] for row in affine[:3]])
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


def corner_heights(shape, affine):
    """The head-foot positions of the volume's outer voxel faces at its eight corners."""
    row = affine[2]
    return [row[0] * i + row[1] * j + row[2] * k + row[3]
            for i in (-0.5, shape[0] - 0.5) for j in (-0.5, shape[1] - 0.5) for k in (-0.5, shape[2] - 0.5)]


def enhance_level(entry, top, bottom, step):
    """ENHANCE.PET's facts give no faces: a level whose head-most or foot-most voxel centre lies in the
    field's first or last slice reaches that face. Its grids are untilted (enhance_study), so the field
    over every level is the volume's."""
    half = step / 2 + EDGE_ROUNDING_MM
    return {"voxels": entry["voxels"], "top": entry["top_mm"], "bottom": entry["bottom_mm"],
            "head_cut": top - entry["top_mm"] <= half, "foot_cut": entry["bottom_mm"] - bottom <= half,
            "side_cut": None, "field_top": top, "field_bottom": bottom, "centre": entry["centroid_mm"][2]}


def tilted(affine, axis):
    return any(abs(affine[2][i]) > 1e-9 for i in range(3) if i != axis)


def enhance_study(row):
    mask = row["mask"]
    if tilted(mask["affine"], mask["head_foot_axis"]):
        raise FieldError(f"enhance_pet {row['id']}: a tilted grid, which enhance_level does not measure")
    heights = corner_heights(mask["shape"], mask["affine"])
    top, bottom = max(heights), min(heights)
    step = abs(mask["affine"][2][mask["head_foot_axis"]])
    levels = {ENHANCE_NAMES[label]: enhance_level(entry, top, bottom, step)
              for label, entry in row["labels"].items() if label in ENHANCE_NAMES}
    return {"member": "enhance_pet", "id": row["id"], "top": top, "bottom": bottom, "levels": levels,
            "person": None, "age": None, "site": row.get("site")}


def column_field(row, entry):
    """The field's top and bottom over a level: the grid's faces as the facts give them, moved by how far
    the world's head-foot line through the level's centre leaves the volume below the highest corner, or
    above the lowest, which is nothing on an untilted grid."""
    grid, field = row["grid"], row["field_mm"]
    if not tilted(grid["affine"], grid["head_foot_axis"]):
        return field["top"], field["bottom"]
    heights = corner_heights(grid["shape"], grid["affine"])
    up, down = vertical_edges(grid["affine"], grid["shape"], entry["centroid_mm"])
    return round(field["top"] - (max(heights) - up), 1), round(field["bottom"] + (down - min(heights)), 1)


def plane_slack(grid, span=TILT_SPAN_MM):
    """How far apart structures that one plane of the grid cuts may end: a slice, the facts' rounding,
    and how much the plane's height changes across `span` in the slice's plane."""
    axis, affine, zooms = grid["head_foot_axis"], grid["affine"], grid["zooms"]
    tilt = sum(abs(affine[2][i]) * span / zooms[i] for i in range(3) if i != axis)
    return zooms[axis] + EDGE_ROUNDING_MM + tilt


def image_planes(row):
    """The head-most and foot-most planes the image reaches, where they lie inside the grid; else None.
    The spinal cord runs on above every level below C1 and down past the conus to the canal's foot in
    TotalSegmentator's masks, and the release draws every structure its image shows: so where the cord
    and the column stop together at the highest (or lowest) height anything is drawn, with grid left
    beyond it, the image ends there, and the slices beyond hold padding, not anatomy. The plane is given
    at the column, the higher (or lower) of the cord's end and the column's, since on a tilted grid the
    skull or the hips a body's width away can end higher or lower on the same plane."""
    cord = row["context"].get("spinal_cord")
    if not cord:
        return None, None
    slack = plane_slack(row["grid"])
    drawn_here = [e for e in (*row["levels"].values(), *row["context"].values()) if e["voxels"] > 0]
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


def named_level(row, entry, planes, slack):
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


def named_study(row, person, age, site):
    planes = image_planes(row)
    slack = plane_slack(row["grid"], LEVEL_SPAN_MM)
    step = row["grid"]["zooms"][row["grid"]["head_foot_axis"]]
    top = row["field_mm"]["top"] if planes[0] is None else round(planes[0] + step / 2, 1)
    bottom = row["field_mm"]["bottom"] if planes[1] is None else round(planes[1] - step / 2, 1)
    return {"member": row["member"], "id": row["id"], "top": top, "bottom": bottom,
            "levels": {name: named_level(row, e, planes, slack) for name, e in row["levels"].items()},
            "person": person, "age": age, "site": site, "image_planes": [p is not None for p in planes]}


def verse_study(row, series):
    entry = series[row["id"]]
    return named_study(row, f"verse:{entry['patient']}", entry.get("age"), None)


def totalseg_study(row, subjects):
    entry = subjects.get(row["id"], {})
    return named_study(row, f"totalsegmentator:{row['id']}", entry.get("age"), entry.get("institute") or None)


def studies_of(inputs):
    """Every readable study of the three members, in level names; rows that say they could not be read
    are kept apart, by id. An ENHANCE.PET study with a repaired mask is judged once, on its repair and
    under its own id, as tools/gold3_ct.py reads it."""
    series = {s["series"]: s for s in inputs["verse_series"]["series"]}
    subjects = inputs["totalseg_subjects"]["subjects"]
    out, unread = [], []
    repaired = {row["repaired_from"]: row for row in inputs["enhance_pet"] if "repaired_from" in row}
    for row in inputs["enhance_pet"]:
        if "repaired_from" in row:
            continue
        study = enhance_study(repaired.get(row["id"], row))
        study["id"] = row["id"]
        out.append(study)
    for member, make in (("verse", lambda r: verse_study(r, series)),
                         ("totalsegmentator", lambda r: totalseg_study(r, subjects))):
        for row in inputs[member]:
            if "error" in row:
                unread.append({"member": member, "id": row["id"], "error": row["error"]})
            else:
                out.append(make(row))
    return out, unread


# ---------------------------------------------------------------- what is drawn


def drawn(study, name):
    level = study["levels"].get(name)
    return level if level and level["voxels"] >= LEVEL_MIN_VOXELS else None


def drawn_names(study):
    return [name for name in ORDER if drawn(study, name)]


def drawn_below(study, name):
    """The first drawn level below a name, C1 and the sacrum aside."""
    names = [n for n in drawn_names(study) if n not in ("C1", "sacrum")]
    later = [n for n in names if ORDER.index(n) > ORDER.index(name)]
    return later[0] if later else None


def head_most(study):
    """The head-most drawn level from C2 down; C1 alone above an undrawn C2 says C2 lies under it."""
    names = [name for name in drawn_names(study) if name != "sacrum"]
    return names[0] if names else None


def foot_most(study):
    names = [name for name in drawn_names(study) if name != "sacrum"]
    return names[-1] if names else None


# ---------------------------------------------------------------- the head and foot tables


def percentile(values, p):
    """The p-th percentile by linear interpolation between order statistics (numpy's default)."""
    values = sorted(values)
    if len(values) == 1:
        return values[0]
    at = (len(values) - 1) * p / 100
    low = int(at)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (at - low)


def summary(values):
    if len(values) < MIN_TABLE_SPINES:
        return {"n": len(values)}
    return {"n": len(values), "low": round(percentile(values, LOW_PERCENTILE), 1),
            "median": round(statistics.median(values), 1), "high": round(percentile(values, HIGH_PERCENTILE), 1)}


def whole(level):
    return level is not None and not level["head_cut"] and not level["foot_cut"]


def head_pairs(studies):
    """For each level below C2, how far C2's top and C2's foot-most voxel lie above that level's top, in
    spines that draw both whole: how much field C2 needs above a level when C2 is not drawn, and how
    little leaves none of it in view."""
    pairs = {}
    for study in studies:
        c2 = drawn(study, "C2")
        if not whole(c2):
            continue
        for name in ORDER[ORDER.index("C3"):ORDER.index("sacrum")]:
            level = drawn(study, name)
            if whole(level):
                pairs.setdefault(name, []).append(c2["top"] - level["top"])
                pairs.setdefault(f"{name} to C2's foot", []).append(c2["bottom"] - level["top"])
    return pairs


def foot_pairs(studies):
    """For each level above the sacrum, where the sacrum's top lies against that level's foot-most voxel,
    in spines that draw both whole (positive above it): where the sacrum begins when it is not drawn. The
    last lumbar, whatever its name, is its own row, since VerSe draws every lumbar it shows and its last
    meets the sacrum."""
    pairs = {}
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


def tables(studies):
    return {"head": {name: summary(v) for name, v in sorted(head_pairs(studies).items(), key=order_key)},
            "foot": {name: summary(v) for name, v in sorted(foot_pairs(studies).items(), key=order_key)}}


def order_key(item):
    """Head to foot by the level a row starts from, a level's own row before its second; the last
    lumbar after L6."""
    name = item[0]
    level = name.split(" ")[0]
    rank = ORDER.index(level) if level in ORDER else ORDER.index("sacrum")
    return rank, name != level


# ---------------------------------------------------------------- the two ends


def head_end(study, table):
    """drawn, in_view, border, out or no_column, with the numbers it rests on. A C2 the release draws is
    in view however the field cuts it, as version 1 had it: a person drew what the CT shows, and a C2 in
    the top slice is flagged for a look (flags), not left out; but where the field's top cuts the level
    below C2 too, the field holds no more of C2 than a sliver beside that level, and the end is out. A C2
    the release does not draw is in view when the field's top lies above where C2's foot lies in 95 of
    100 spines, counted from the head-most drawn level, since C2's foot in the field is what the owner's
    "the bottom c2" asks (version 3); version 2 asked for C2's top."""
    c2 = drawn(study, "C2")
    if c2:
        below = drawn_below(study, "C2")
        if c2["head_cut"] and below and drawn(study, below)["head_cut"]:
            return OUT, {"why": f"C2 and {below} are both cut by the field's top: the field holds a sliver of C2"}
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
        return OUT, {"why": f"{top}, the head-most drawn level, is cut by the field's top"}
    foot = table.get(f"{top} to C2's foot", {})
    margin = round(level["field_top"] - level["top"], 1)
    numbers = {"from": top, "field_above_mm": margin, "c2_foot_above_mm": [foot.get("low"), foot.get("high")]}
    if "high" not in foot or "low" not in foot:
        return BORDER, {**numbers, "why": f"fewer than {MIN_TABLE_SPINES} spines measure C2 above {top}"}
    if margin >= foot["high"]:
        return IN_VIEW, numbers
    return (OUT if margin < foot["low"] else BORDER), numbers


def sacrum_held(study):
    """How many mm of the sacrum the field holds below its top, where the field's foot cuts a sacrum
    label of any size, since a cut label shows where the sacrum begins however few voxels it has; else
    None."""
    sacrum = study["levels"].get("sacrum")
    if not sacrum or sacrum["voxels"] == 0 or not sacrum["foot_cut"]:
        return None
    return round(sacrum["top"] - sacrum["field_bottom"], 1)


def foot_end(study, table, s1_view=S1_VIEW_MM):
    """The same for the sacrum: one the release draws is drawn, however little of it the field holds,
    since its top is in the field and the owner's "If the top of the sacrum is visible that is acceptable"
    asks no more (version 3); a foot-most level above it that runs on to the field's foot is flagged
    (flags), not a border case as in version 2. A sacrum the release does not draw is placed from the
    foot-most drawn level by the foot table and is in view when the field's foot lies below the place; it
    is out when that level is cut by the field's foot. s1_view, none in the rule, asks for that much of S1
    below the sacrum's top, as version 2 asked 20 mm, for the counts ADMISSION.md sets beside the rule's:
    where the field's foot cuts a sacrum label, drawn or under the floor, with less than s1_view of it in
    the field, the end is out when the foot-most level above it is cut too and a border case otherwise."""
    last = foot_most(study)
    if last is None:
        return (DRAWN if drawn(study, "sacrum") else NO_COLUMN), {}
    level = drawn(study, last)
    held = sacrum_held(study)
    if held is not None and held < s1_view:
        numbers = {"sacrum_in_field_mm": held}
        if level["foot_cut"]:
            return OUT, {**numbers, "why": f"{last} is cut by the field's foot, and the field holds {held} mm of the "
                                            f"sacrum below its top, under {s1_view:g} mm of S1"}
        return BORDER, {**numbers, "why": f"the field's foot cuts the sacrum {held} mm below its top, under {s1_view:g} mm of S1"}
    if drawn(study, "sacrum"):
        return DRAWN, {}
    if level["foot_cut"]:
        return OUT, {"why": f"{last}, the foot-most drawn level, is cut by the field's foot"}
    row = table.get("last lumbar" if last in LAST_LUMBARS else last, {})
    numbers = {"from": last, "field_below_mm": round(level["bottom"] - level["field_bottom"], 1),
               "sacrum_top_from_level_mm": [row.get("low"), row.get("high")]}
    if "high" not in row:
        return BORDER, {**numbers, "why": f"fewer than {MIN_TABLE_SPINES} spines measure the sacrum below {last}"}
    lowest_top, highest_top = level["bottom"] + row["low"], level["bottom"] + row["high"]
    if level["field_bottom"] <= lowest_top - s1_view:
        return IN_VIEW, numbers
    return (OUT if level["field_bottom"] > highest_top else BORDER), numbers


def verdict_of(head, foot):
    if head in (OUT, NO_COLUMN) or foot in (OUT, NO_COLUMN):
        return NOT_ADMITTED
    return ADMITTED if {head, foot} <= {DRAWN, IN_VIEW} else LOOK


# ---------------------------------------------------------------- what a segmenter must draw


def name_runs(study):
    """(gaps, skipped): the expected levels undrawn between two drawn ones, split by whether those two
    leave room for a body between them. One name missing between neighbours whose centres lie no farther
    apart than ROOM_TIMES the study's own spacing of neighbouring levels nearby skips a level the column
    does not have: a count variant, as eleven thoracic and then L1, or a skipped label, for the count to
    read, never a mask to add. Two names or more, a lower level whose centre is not below the upper's, or
    a study with no neighbouring pair to measure, are gaps, since no spine lacks two levels in a row and a
    gap a segmenter finds empty costs a refusal, where a gap read as a variant leaves a level undrawn. Above
    a drawn sacrum, a column that stops above L4 leaves room for L5 too, as completion asks it below a
    sacrum in view, and an L6 drawn below L4 asks the L5 between them."""
    names = drawn_names(study)
    gaps, skipped = [], []
    for upper, lower in zip(names, names[1:]):
        missing = [n for n in EXPECTED if ORDER.index(upper) < ORDER.index(n) < ORDER.index(lower)]
        if lower in ("sacrum", "L6") and ORDER.index(upper) < ORDER.index("L4" if lower == "sacrum" else "L5"):
            missing.append("L5")
        if missing:
            (gaps if room_between(study, upper, lower, missing) else skipped).extend(missing)
    return gaps, skipped


def room_between(study, upper, lower, missing):
    spacing = drawn(study, upper)["centre"] - drawn(study, lower)["centre"]
    reference = nearby_spacing(study, upper, lower)
    return len(missing) > 1 or spacing <= 0 or reference is None or spacing > ROOM_TIMES * reference


def nearby_spacing(study, upper, lower):
    """The median spacing of the centres of the ROOM_PAIRS pairs of drawn levels next to each other in
    ORDER nearest the run between `upper` and `lower`; C1, C2 and the sacrum are left out, as their
    centres stand apart from a body's. None where the study has no such pair."""
    names = [n for n in drawn_names(study) if n not in ("C1", "C2", "sacrum")]
    middle = (ORDER.index(upper) + ORDER.index(lower)) / 2
    pairs = [(abs((ORDER.index(a) + ORDER.index(b)) / 2 - middle),
              drawn(study, a)["centre"] - drawn(study, b)["centre"])
             for a, b in zip(names, names[1:]) if ORDER.index(b) == ORDER.index(a) + 1]
    nearest = [spacing for _, spacing in sorted(pairs)[:ROOM_PAIRS]]
    return statistics.median(nearest) if nearest else None


def gaps(study):
    return name_runs(study)[0]


def completion(study, head, foot):
    """The levels from C2 to the sacrum a segmenter must add to an admitted study: C2 and the levels
    above the head-most drawn one, the gaps, the sacrum, and the lumbar levels below a foot-most drawn
    level that cannot be the last, L5 among them, since the field reaches the pelvis and nearly every
    spine has one (the foot table's L5 row against its last lumbar's); a four-lumbar spine's segmenter
    finds none, and the count reads it."""
    add = set(gaps(study))
    top, last = head_most(study), foot_most(study)
    if head == IN_VIEW and top not in (None, "C1"):
        add |= {n for n in EXPECTED if ORDER.index(n) < ORDER.index(top) and not drawn(study, n)}
    if head == IN_VIEW and top == "C1":
        add.add("C2")
    if foot == IN_VIEW:
        add.add("sacrum")
        if last not in LAST_LUMBARS and ORDER.index(last) < ORDER.index("L4"):
            add |= {n for n in (*EXPECTED, "L5") if ORDER.index(n) > ORDER.index(last) and not drawn(study, n)}
    return [n for n in ORDER if n in add]


def flags(study, head, foot):
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
    span = drawn_names(study)
    if any(drawn(study, n)["side_cut"] for n in span if n not in ("C1",)):
        out.append("cut_in_plane")
    if not drawn(study, "L5") and drawn(study, "L4") and not drawn(study, "L6") and foot in (DRAWN, IN_VIEW):
        out.append("no_l5")
    small = [n for n, e in study["levels"].items() if 0 < e["voxels"] < LEVEL_MIN_VOXELS]
    if small:
        out.append("stray_labels")
    if study["age"] is not None and study["age"] < CHILD_UNDER_YEARS:
        out.append("child")
    if column_length(study) is not None and column_length(study) < SMALL_COLUMN_MM:
        out.append("small_column")
    if tall_labels(study):
        out.append("label_spans_levels")
    return out


def column_length(study):
    """C2's top to L1's foot, where both are drawn whole; else None."""
    c2, l1 = drawn(study, "C2"), drawn(study, "L1")
    return round(c2["top"] - l1["bottom"], 1) if whole(c2) and whole(l1) else None


def tall_labels(study):
    names = [n for n in drawn_names(study) if n != "sacrum"]
    if len(names) < 3:
        return []
    heights = {n: study["levels"][n]["top"] - study["levels"][n]["bottom"] for n in names}
    median = statistics.median(heights.values())
    return [n for n in names if heights[n] > TALL_LABEL_TIMES * median]


def to_complete(study, verdict, head, foot):
    """The completion list of an admitted study; of a border case, the list should a person's look admit
    it, an undrawn C2 or sacrum at a border end taken as in view; none for a study not admitted."""
    if verdict == NOT_ADMITTED:
        return []
    if verdict == LOOK:
        head = IN_VIEW if head == BORDER and not drawn(study, "C2") else (DRAWN if head == BORDER else head)
        foot = IN_VIEW if foot == BORDER and not drawn(study, "sacrum") else (DRAWN if foot == BORDER else foot)
    return completion(study, head, foot)


def judge(study, table, s1_view=S1_VIEW_MM):
    head, head_numbers = head_end(study, table["head"])
    foot, foot_numbers = foot_end(study, table["foot"], s1_view)
    verdict = verdict_of(head, foot)
    return {"member": study["member"], "id": study["id"], "person": study["person"], "verdict": verdict,
            "head": head, "foot": foot, "head_numbers": head_numbers, "foot_numbers": foot_numbers,
            "complete": to_complete(study, verdict, head, foot),
            "flags": flags(study, head, foot)}


# ---------------------------------------------------------------- the checks against what is known


def hidden(study, names):
    return {**study, "levels": {n: e for n, e in study["levels"].items() if n not in names}}


def hide_and_judge(studies, table, names, end):
    """The rule run with levels hidden on spines that draw them whole: how often it finds in view what
    the masks show is there. A check of the tables' use, not of the tables, which these spines made."""
    out = {}
    for study in studies:
        if not all(whole(drawn(study, n)) for n in names if n != "C1") or not drawn(study, names[-1]):
            continue
        if head_most(hidden(study, names)) is None:
            continue
        if end == "head":
            found, _ = head_end(hidden(study, names), table["head"])
        else:
            found, _ = foot_end(hidden(study, names), table["foot"])
        key = f"{study['member']}: {found}"
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items()))


def truncation_check(studies, table):
    """Spines whose head-most drawn level below C2 is cut by the field's top: no C2 fits in the field above
    a level its top cuts, so the rule must call them out. A check of the rule's own branch, which reads no
    table, kept so that a change that breaks the branch shows here."""
    out = {}
    for study in studies:
        top = head_most(study)
        if top and top not in ("C1", "C2") and drawn(study, top)["head_cut"]:
            found, _ = head_end(study, table["head"])
            key = f"{study['member']}: {found}"
            out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items()))


# ---------------------------------------------------------------- the counts


def count(judged, key):
    out = {}
    for row in judged:
        out[row[key]] = out.get(row[key], 0) + 1
    return dict(sorted(out.items()))


def persons(judged, verdict):
    keys = [row["person"] for row in judged if row["verdict"] == verdict]
    return len(set(keys)) if all(keys) else None


def completion_counts(judged):
    out = {}
    for row in judged:
        if row["verdict"] == ADMITTED:
            for name in row["complete"]:
                out[name] = out.get(name, 0) + 1
    return {name: out[name] for name in ORDER if name in out}


def member_counts(judged, member):
    rows = [r for r in judged if r["member"] == member]
    admitted = [r for r in rows if r["verdict"] == ADMITTED]
    return {"studies": len(rows), "verdicts": count(rows, "verdict"),
            "admitted_persons": persons(rows, ADMITTED), "look_persons": persons(rows, LOOK),
            "admitted_whole_by_masks": sum(1 for r in admitted if not r["complete"]),
            "admitted_to_complete": sum(1 for r in admitted if r["complete"]),
            "head": count(rows, "head"), "foot": count(rows, "foot"),
            "complete": completion_counts(rows),
            "flags_admitted": count([{"f": f} for r in admitted for f in r["flags"]], "f")}


def admission(inputs):
    studies, unread = studies_of(inputs)
    table = tables(studies)
    judged = [judge(s, table) for s in studies]
    sensitivity = {f"{mm:g}": count([judge(s, table, mm) for s in studies if s["member"] != "enhance_pet"] +
                                    [j for j in judged if j["member"] == "enhance_pet"], "verdict")
                   for mm in S1_VIEW_SENSITIVITY}
    return {
        "about": f"The gold tier 3 CT dataset's admission by the field test, rule version {RULE_VERSION} (tools/gold3_field.py): "
                 "every study of the three members with its verdict, its two ends and the levels a segmenter must "
                 "add. Written by `python3 tools/gold3_field.py write`; never edited by hand.",
        "rule": rule_record(),
        "tables": table,
        "checks": {"head_with_c1_c2_hidden": hide_and_judge(studies, table, ("C1", "C2"), "head"),
                   "foot_with_sacrum_hidden": hide_and_judge(studies, table, ("sacrum",), "foot"),
                   "head_most_level_cut_at_the_top": truncation_check(studies, table)},
        "sensitivity_s1_view_mm": sensitivity,
        "members": {m: member_counts(judged, m) for m in MEMBER_ORDER},
        "unread": unread,
        "studies": [{k: row[k] for k in ("member", "id", "person", "verdict", "head", "foot", "complete", "flags")}
                    for row in judged],
    }


def rule_record():
    return {"version": RULE_VERSION,
            "rule": "A CT is admitted when its field holds the foot of C2 and the top of the sacrum, whatever its masks "
                    "hold; a level its masks do not draw is completed by a segmenter, kept as a machine mask of its own. "
                    "A drawn C2 is in view however the field's top cuts it, unless it cuts the level below C2 too, a "
                    "sliver of C2, and the end is out; an undrawn C2 is in view when the field's top lies above where "
                    "C2's foot lies in 95 of 100 spines. A drawn sacrum is in view however little of it the field holds; "
                    "an undrawn one is in view when the field's foot lies below where the sacrum's top lies in 95 of "
                    "100 spines. The field is read "
                    "over each level along the world's vertical line, and a padded grid's field ends where the "
                    "spinal cord and the column stop together. A name missing between two drawn levels is a level "
                    "to add when their centres stand more than room_times the study's spacing of neighbours apart, "
                    "else a count variant, flagged.",
            "asked": "the owner, 2026-10-28 22:58 UTC (#443's question): \"if the full spune is in view in the volume, "
                     "and just missing a mask or two, that should just be completed using a segmentation software of "
                     "choice ... i dont think i should leave out any spines that have ct volumes with the full spine in view\"; "
                     "and for version 3, 2026-10-29 12:58 UTC: \"If the top of the sacrum is visible that is acceptable, "
                     "which I believe is all of them but check\" and \"Same for the bottom c2\"",
            "thresholds": {"level_min_voxels": LEVEL_MIN_VOXELS, "percentiles": [LOW_PERCENTILE, HIGH_PERCENTILE],
                           "min_table_spines": MIN_TABLE_SPINES, "s1_view_mm": S1_VIEW_MM,
                           "tilt_span_mm": TILT_SPAN_MM, "level_span_mm": LEVEL_SPAN_MM, "room_times": ROOM_TIMES,
                           "room_pairs": ROOM_PAIRS, "child_under_years": CHILD_UNDER_YEARS,
                           "small_column_mm": SMALL_COLUMN_MM, "tall_label_times": TALL_LABEL_TIMES}}


# ---------------------------------------------------------------- the page


def table_text(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    return "\n".join(lines + ["| " + " | ".join(str(c) for c in row) + " |" for row in rows])


def verdict_rows(data):
    rows = []
    for member in MEMBER_ORDER:
        m = data["members"][member]
        v = m["verdicts"]
        rows.append([member, m["studies"], v.get(ADMITTED, 0), m["admitted_whole_by_masks"], m["admitted_to_complete"],
                     v.get(LOOK, 0), v.get(NOT_ADMITTED, 0), m["admitted_persons"] if m["admitted_persons"] is not None else "-"])
    return rows


def end_rows(data, end):
    names = (DRAWN, IN_VIEW, BORDER, OUT, NO_COLUMN)
    return [[member, *(data["members"][member][end].get(n, 0) for n in names)] for member in MEMBER_ORDER]


def table_rows(rows):
    return [[name, r["n"], r.get("low", "-"), r.get("median", "-"), r.get("high", "-")] for name, r in rows.items()]


def page_text(data):
    sections = [
        "# Gold tier 3 CT: the admission by the field test",
        "",
        "Written by `python3 tools/gold3_field.py write` from data/gold3-ct/admission.json; never edited by hand. "
        "The rule, its reasons and the definition of held are docs/research/gold3-ct/README.md. Confidential.",
        "",
        f"## The rule, version {data['rule']['version']}",
        "",
        data["rule"]["rule"],
        "",
        f"Asked: {data['rule']['asked']}.",
        "",
        "## The verdicts",
        "",
        "A study is admitted when both ends are drawn or in view; look means a border case at one end, admitted "
        "only after a person's look; not admitted means C2 or the sacrum is out of the field, or no vertebra is "
        "drawn above the sacrum (no column). Whole by masks means no level to add; to complete means a segmenter adds the levels listed below.",
        "",
        table_text(["member", "studies", "admitted", "whole by masks", "to complete", "look", "not admitted",
                    "admitted persons"], verdict_rows(data)),
        "",
        "## The head end",
        "",
        table_text(["member", "C2 drawn", "C2 in view, not drawn", "border", "out", "no column"], end_rows(data, "head")),
        "",
        "## The foot end",
        "",
        table_text(["member", "sacrum drawn", "sacrum in view, not drawn", "border", "out", "no column"],
                   end_rows(data, "foot")),
        "",
        "## What a segmenter must draw",
        "",
        "Levels to add over the admitted studies, by member: each a machine mask of its own, never pooled with "
        "SPINEPS or with the release's masks, never raising a tier. admission.json gives each border case the "
        "list its look would ask, should it admit the study.",
        "",
        table_text(["member", "levels to add (studies)"],
                   [[m, ", ".join(f"{n} {c}" for n, c in data["members"][m]["complete"].items()) or "none"]
                    for m in MEMBER_ORDER]),
        "",
        "## Flags on the admitted studies",
        "",
        table_text(["member", "flags (studies)"],
                   [[m, ", ".join(f"{n} {c}" for n, c in data["members"][m]["flags_admitted"].items()) or "none"]
                    for m in MEMBER_ORDER]),
        "",
        "What each flag means: c2_at_field_top, the field's top cuts C2; sacrum_at_field_foot, the field's foot "
        "cuts a sacrum label of any size; level_past_sacrum_top, the foot-most level above a drawn sacrum runs on "
        "past the sacrum's top to the field's foot, a label over the junction; name_skipped, one name the column's order expects is missing where its "
        "neighbours' centres stand no farther apart than its own spacing of neighbours allows (a count "
        f"variant, as eleven thoracic and then L1, or a skipped label, within {ROOM_TIMES:g} times that spacing), "
        "so nothing is added for it and the count reads it; cut_in_plane, a level touches a side face of the grid; no_l5, L4 is the last lumbar, no L5 or "
        "L6 drawn, with the foot in view; stray_labels, a label of fewer voxels than the floor; child, under "
        f"{CHILD_UNDER_YEARS} at the scan; small_column, C2's top to L1's foot under {SMALL_COLUMN_MM:g} mm; "
        f"label_spans_levels, a label more than {TALL_LABEL_TIMES:g} times the study's median level height, as "
        "one label drawn over several bodies. A flag asks for a look and leaves a study's verdict as it is.",
        "",
        "## The head table",
        "",
        "How far C2's top (a level's own row) and C2's foot (its row to C2's foot) lie above each level's top, in "
        "mm, in spines of all three members that draw both whole; the rule reads the rows to C2's foot.",
        "",
        table_text(["level", "spines", f"p{LOW_PERCENTILE}", "median", f"p{HIGH_PERCENTILE}"], table_rows(data["tables"]["head"])),
        "",
        "## The foot table",
        "",
        "Where the sacrum's top lies against each level's foot-most voxel, in mm, positive above it, in spines that "
        "draw both whole; the last lumbar is whichever lumbar a spine draws last.",
        "",
        table_text(["level", "spines", f"p{LOW_PERCENTILE}", "median", f"p{HIGH_PERCENTILE}"], table_rows(data["tables"]["foot"])),
        "",
        "## Checks",
        "",
        "The rule run with C1 and C2 hidden on spines that draw them whole and a level below them (it should "
        "find C2 in view or a border case, never out), with the sacrum hidden on spines that draw it and a "
        "level above it (it should find the sacrum in view), and, a check of the rule's own branch that reads "
        "no table, on spines whose head-most drawn level below C2 is cut by the field's top (no C2 fits above "
        "it, so the rule must call C2 out):",
        "",
        table_text(["check", "result (studies)"],
                   [[name, ", ".join(f"{k} {v}" for k, v in result.items())] for name, result in data["checks"].items()]),
        "",
        f"## How the counts move with S1_VIEW_MM ({S1_VIEW_MM:g} mm in the rule)",
        "",
        table_text(["s1 view mm", "verdicts (studies)"],
                   [[mm, ", ".join(f"{k} {v}" for k, v in result.items())] for mm, result in data["sensitivity_s1_view_mm"].items()]),
        "",
        "## Unread",
        "",
        ", ".join(f"{u['member']} {u['id']}" for u in data["unread"]) or "none",
        "",
    ]
    return "\n".join(sections)


def json_text(data):
    return json.dumps(data, indent=1, sort_keys=False, ensure_ascii=True) + "\n"


# ---------------------------------------------------------------- taking a reading of the masks


def sums_digest(files):
    """One digest for a study's files: the sha256 of the lines `sha256sum` prints for them, sorted by
    name, so a grid job checks its copy with `sha256sum <names> | sort -k2 | sha256sum`."""
    lines = "".join(f"{entry['sha256']}  {name}\n" for name, entry in sorted(files.items()))
    return {"count": len(files), "bytes": sum(entry["bytes"] for entry in files.values()),
            "sha256_of_sums": hashlib.sha256(lines.encode("ascii")).hexdigest()}


def compact(row):
    """A reader's row as committed: a study read from several files keeps one digest of their sums, so
    TotalSegmentator's fifty-odd masks a subject do not double the file; one file keeps its own sum."""
    if "files" in row and len(row["files"]) > 1:
        return {**row, "files": sums_digest(row["files"])}
    return row


def take_record(member, raw, rows, args):
    return {"member": member, "rows": len(rows), "unreadable": sorted(r["id"] for r in rows if "error" in r),
            "made_by": READER, "bordercall_commit": args.bordercall_commit, "read_on": args.read_on,
            "source": args.source, "date": args.date, "ct_grid_check": args.ct_check,
            "reader_output_sha256": hashlib.sha256(raw).hexdigest(),
            "committed_as": "one row a study, keys sorted; a study read from several files keeps one digest of "
                            "their sums (tools/gold3_field.py sums_digest)"}


def command_take(args):
    raw = Path(args.facts).read_bytes()
    rows = [compact(json.loads(line)) for line in raw.decode("ascii").splitlines()]
    if any(row.get("member", args.member) != args.member for row in rows if "error" not in row):
        raise FieldError(f"{args.facts}: rows of another member than {args.member}")
    rel = FACTS_OF[args.member]
    out = Path(args.repo) / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n" for r in rows),
                   encoding="ascii", newline="\n")
    record = take_record(args.member, raw, rows, args)
    (out.parent / "FACTS.json").write_text(json.dumps(record, indent=1) + "\n", encoding="ascii", newline="\n")
    print(f"wrote {rel} ({len(rows)} rows) and its FACTS.json")
    return 0


# ---------------------------------------------------------------- the command line


def written(repo=ROOT):
    data = admission(load_inputs(repo))
    return {ADMISSION: json_text(data), PAGE: page_text(data)}


def command_write(args):
    for rel, text in written(args.repo).items():
        (Path(args.repo) / rel).write_text(text, encoding="ascii", newline="\n")
        print(f"wrote {rel}")
    return 0


def command_check(args):
    stale = [rel for rel, text in written(args.repo).items()
             if not (Path(args.repo) / rel).is_file() or (Path(args.repo) / rel).read_text(encoding="ascii") != text]
    for rel in stale:
        print(f"{rel} is stale: run python3 tools/gold3_field.py write", file=sys.stderr)
    return 1 if stale else 0


def command_show(args):
    inputs = load_inputs(args.repo)
    studies, _ = studies_of(inputs)
    table = tables(studies)
    for study in studies:
        if study["id"] == args.id and (args.member is None or study["member"] == args.member):
            print(json.dumps(judge(study, table), indent=1))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=str(ROOT))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("write")
    sub.add_parser("check")
    show = sub.add_parser("show")
    show.add_argument("id")
    show.add_argument("--member", choices=MEMBER_ORDER)
    take = sub.add_parser("take")
    take.add_argument("member", choices=sorted(FACTS_OF))
    take.add_argument("facts")
    take.add_argument("--read-on", required=True)
    take.add_argument("--bordercall-commit", required=True)
    take.add_argument("--source", required=True)
    take.add_argument("--date", required=True)
    take.add_argument("--ct-check", required=True, help="how the masks were found on their CTs' grids")
    args = parser.parse_args(argv)
    handlers = {"write": command_write, "check": command_check, "show": command_show, "take": command_take}
    try:
        return handlers[args.command](args)
    except FieldError as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
