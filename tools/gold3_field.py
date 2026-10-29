"""The field test of the gold tier 3 CT dataset: which CT volumes show the whole spine, C2 to the sacrum,
whatever their masks hold, and which levels a segmenter must draw to complete each.

Source: the thread "Complete every full-spine CT for gold tier 3", 2026-10-28, for the owner's answer of
22:58 UTC on the admission rule of VerSe and TotalSegmentator (#443): "essentially if the full spune is in
view in the volume, and just missing a mask or two, that should just be completed using a segmentation
software of choice ... i dont think i should leave out any spines that have ct volumes with the full spine
in view, i should do whatever is necessary to get them ready for usage". docs/research/gold3-ct/ is the
programme's folder and ADMISSION.md, written by this file, its page for the rule. Confidential, like the
rest of SchwingNet: nothing here, and nothing it writes, goes to a public place.

The rule, version 2, replaces version 1's whole-by-the-masks rule (data/gold3-ct/members.json): a CT is
admitted when its field holds C2 and the top of the sacrum, whatever its masks hold. A level is drawn when
its mask holds at least LEVEL_MIN_VOXELS voxels. The head end is in view when C2 is drawn, wherever the
field cuts it, since a person drew what the CT shows (a C2 in the field's top slice is flagged for a
look), or when C2 is not drawn and the field reaches far enough above the head-most drawn level that C2
fits under it in 95 of 100 spines that draw both (the head table); it is out when that level is cut by
the field's top, or when the field ends below where C2's foot lies in 95 of 100 spines. The foot end is in
view when the sacrum is drawn (one cut by the field's foot with less than S1_VIEW_MM of it drawn is
flagged), or when it is not drawn and the field reaches at least S1_VIEW_MM below where the sacrum's top
lies in 95 of 100 spines that draw both, from the foot-most drawn level (the foot table); it is out when
that level is cut by the field's foot, or when the field ends above where the sacrum's top lies in 95 of
100 spines. A study between in view and out of view at either end is a border case, admitted only after a
person's look. The tables are measured here on the members' own masks, never assumed.

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
RULE_VERSION = 2

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
# The head and foot tables are read at these percentiles: in view needs the 95th, so C2 fits under the
# field's top, or the sacrum's top lies above the field's bottom, in 95 of 100 spines that draw both.
LOW_PERCENTILE, HIGH_PERCENTILE = 5, 95
# A table row needs this many spines to be read; a level with fewer gives a border case, not a verdict.
MIN_TABLE_SPINES = 20
# How much of S1 must be in the field below the top of the sacrum for the lumbosacral junction to be
# read: the L5-S1 disc and the top of S1's body. A choice, with ADMISSION.md giving the counts at 10 and
# 30 mm beside it, since no published number fixes it.
S1_VIEW_MM = 20.0
S1_VIEW_SENSITIVITY = (10.0, 30.0)
# A slice centre within half a slice of the field's edge is on the edge: ENHANCE.PET's facts carry no
# faces, so its cut levels are read from the head-foot positions, as tools/gold3_ct.py's Q06 reads C2.
# The 0.05 mm is the facts' rounding to 0.1 mm.
EDGE_ROUNDING_MM = 0.05
# Under 18 at the scan is a child's spine: flagged, never left out, since the rule asks for the whole
# spine in view and says nothing of age.
CHILD_UNDER_YEARS = 18

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


def corner_heights(shape, affine):
    """The head-foot positions of the volume's outer voxel faces at its eight corners."""
    row = affine[2]
    return [row[0] * i + row[1] * j + row[2] * k + row[3]
            for i in (-0.5, shape[0] - 0.5) for j in (-0.5, shape[1] - 0.5) for k in (-0.5, shape[2] - 0.5)]


def enhance_level(entry, top, bottom, step):
    """ENHANCE.PET's facts give no faces: a level whose head-most or foot-most voxel centre lies in the
    field's first or last slice reaches that face."""
    half = step / 2 + EDGE_ROUNDING_MM
    return {"voxels": entry["voxels"], "top": entry["top_mm"], "bottom": entry["bottom_mm"],
            "head_cut": top - entry["top_mm"] <= half, "foot_cut": entry["bottom_mm"] - bottom <= half,
            "side_cut": None}


def enhance_study(row):
    mask = row["mask"]
    heights = corner_heights(mask["shape"], mask["affine"])
    top, bottom = max(heights), min(heights)
    step = abs(mask["affine"][2][mask["head_foot_axis"]])
    levels = {ENHANCE_NAMES[label]: enhance_level(entry, top, bottom, step)
              for label, entry in row["labels"].items() if label in ENHANCE_NAMES}
    return {"member": "enhance_pet", "id": row["id"], "top": top, "bottom": bottom, "levels": levels,
            "person": None, "age": None, "site": row.get("site")}


def named_level(entry):
    faces = set(entry["faces"])
    return {"voxels": entry["voxels"], "top": entry["top_mm"], "bottom": entry["bottom_mm"],
            "head_cut": "S" in faces, "foot_cut": "I" in faces, "side_cut": bool(faces & set("LRAP"))}


def named_study(row, person, age, site):
    return {"member": row["member"], "id": row["id"], "top": row["field_mm"]["top"],
            "bottom": row["field_mm"]["bottom"], "levels": {name: named_level(e) for name, e in row["levels"].items()},
            "person": person, "age": age, "site": site}


def verse_study(row, series):
    entry = series[row["id"]]
    return named_study(row, f"verse:{entry['patient']}", entry.get("age"), None)


def totalseg_study(row, subjects):
    entry = subjects.get(row["id"], {})
    return named_study(row, f"totalsegmentator:{row['id']}", entry.get("age"), entry.get("institute") or None)


def studies_of(inputs):
    """Every readable study of the three members, in level names; rows that say they could not be read
    are kept apart, by id."""
    series = {s["series"]: s for s in inputs["verse_series"]["series"]}
    subjects = inputs["totalseg_subjects"]["subjects"]
    out, unread = [], []
    for row in inputs["enhance_pet"]:
        out.append(enhance_study(row))
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
    the top slice is flagged for a look (flags), not left out."""
    if drawn(study, "C2"):
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
    fits, foot = table.get(top, {}), table.get(f"{top} to C2's foot", {})
    margin = round(study["top"] - level["top"], 1)
    numbers = {"from": top, "field_above_mm": margin, "c2_top_above_mm": [fits.get("low"), fits.get("high")],
               "c2_foot_above_mm": [foot.get("low"), foot.get("high")]}
    if "high" not in fits or "low" not in foot:
        return BORDER, {**numbers, "why": f"fewer than {MIN_TABLE_SPINES} spines measure C2 above {top}"}
    if margin >= fits["high"]:
        return IN_VIEW, numbers
    return (OUT if margin < foot["low"] else BORDER), numbers


def foot_end(study, table, s1_view=S1_VIEW_MM):
    """The same for the sacrum: one the release draws is in view, one it does not is placed from the
    foot-most drawn level by the foot table, and in view needs S1_VIEW_MM of S1 below its top."""
    if drawn(study, "sacrum"):
        return DRAWN, {}
    last = foot_most(study)
    if last is None:
        return NO_COLUMN, {}
    level = drawn(study, last)
    if level["foot_cut"]:
        return OUT, {"why": f"{last}, the foot-most drawn level, is cut by the field's foot"}
    row = table.get("last lumbar" if last in LAST_LUMBARS else last, {})
    numbers = {"from": last, "field_below_mm": round(level["bottom"] - study["bottom"], 1),
               "sacrum_top_from_level_mm": [row.get("low"), row.get("high")]}
    if "high" not in row:
        return BORDER, {**numbers, "why": f"fewer than {MIN_TABLE_SPINES} spines measure the sacrum below {last}"}
    lowest_top, highest_top = level["bottom"] + row["low"], level["bottom"] + row["high"]
    if study["bottom"] <= lowest_top - s1_view:
        return IN_VIEW, numbers
    return (OUT if study["bottom"] > highest_top else BORDER), numbers


def verdict_of(head, foot):
    if head in (OUT, NO_COLUMN) or foot in (OUT, NO_COLUMN):
        return NOT_ADMITTED
    return ADMITTED if {head, foot} <= {DRAWN, IN_VIEW} else LOOK


# ---------------------------------------------------------------- what a segmenter must draw


def gaps(study):
    """Expected levels undrawn between the head-most and foot-most drawn ones."""
    names = drawn_names(study)
    inside = [n for n in EXPECTED if n in ORDER[ORDER.index(names[0]):ORDER.index(names[-1]) + 1]] if names else []
    return [n for n in inside if not drawn(study, n)]


def completion(study, head, foot):
    """The levels from C2 to the sacrum a segmenter must add to an admitted study: C2 and the levels
    above the head-most drawn one, the gaps, the sacrum, and the lumbar levels below a foot-most drawn
    level that cannot be the last."""
    add = set(gaps(study))
    top, last = head_most(study), foot_most(study)
    if head == IN_VIEW and top not in (None, "C1"):
        add |= {n for n in EXPECTED[:EXPECTED.index(top)] if not drawn(study, n)}
    if head == IN_VIEW and top == "C1":
        add.add("C2")
    if foot == IN_VIEW:
        add.add("sacrum")
        if last not in LAST_LUMBARS and last in EXPECTED:
            add |= {n for n in EXPECTED[EXPECTED.index(last) + 1:] if not drawn(study, n)}
    return [n for n in ORDER if n in add]


def flags(study, head, foot):
    out = []
    c2, sacrum = drawn(study, "C2"), drawn(study, "sacrum")
    if c2 and c2["head_cut"]:
        out.append("c2_at_field_top")
    if sacrum and sacrum["foot_cut"] and sacrum["top"] - sacrum["bottom"] < S1_VIEW_MM:
        out.append("sacrum_at_field_foot")
    span = drawn_names(study)
    if any(drawn(study, n)["side_cut"] for n in span if n not in ("C1",)):
        out.append("cut_in_plane")
    if not drawn(study, "L5") and drawn(study, "L4") and foot in (DRAWN, IN_VIEW):
        out.append("no_l5")
    small = [n for n, e in study["levels"].items() if 0 < e["voxels"] < LEVEL_MIN_VOXELS]
    if small:
        out.append("stray_labels")
    if study["age"] is not None and study["age"] < CHILD_UNDER_YEARS:
        out.append("child")
    return out


def judge(study, table, s1_view=S1_VIEW_MM):
    head, head_numbers = head_end(study, table["head"])
    foot, foot_numbers = foot_end(study, table["foot"], s1_view)
    verdict = verdict_of(head, foot)
    return {"member": study["member"], "id": study["id"], "person": study["person"], "verdict": verdict,
            "head": head, "foot": foot, "head_numbers": head_numbers, "foot_numbers": foot_numbers,
            "complete": completion(study, head, foot) if verdict != NOT_ADMITTED else [],
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
        if end == "head":
            found, _ = head_end(hidden(study, names), table["head"])
        else:
            found, _ = foot_end(hidden(study, names), table["foot"])
        key = f"{study['member']}: {found}"
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items()))


def truncation_check(studies, table):
    """Spines whose head-most drawn level is cut by the field's top, in the members that draw every level
    they show (ENHANCE.PET and TotalSegmentator): the rule must call them out, whatever the table says."""
    out = {}
    for study in studies:
        if study["member"] == "verse":
            continue
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
        "about": "The gold tier 3 CT dataset's admission by the field test, rule version 2 (tools/gold3_field.py): "
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
            "rule": "A CT is admitted when its field holds C2 and the top of the sacrum, whatever its masks hold; "
                    "a level its masks do not draw is completed by a segmenter, kept as a machine mask of its own.",
            "asked": "the owner, 2026-10-28 22:58 UTC (#443's question): \"if the full spune is in view in the volume, "
                     "and just missing a mask or two, that should just be completed using a segmentation software of "
                     "choice ... i dont think i should leave out any spines that have ct volumes with the full spine in view\"",
            "thresholds": {"level_min_voxels": LEVEL_MIN_VOXELS, "percentiles": [LOW_PERCENTILE, HIGH_PERCENTILE],
                           "min_table_spines": MIN_TABLE_SPINES, "s1_view_mm": S1_VIEW_MM,
                           "child_under_years": CHILD_UNDER_YEARS}}


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
        "## The rule, version 2",
        "",
        data["rule"]["rule"],
        "",
        f"Asked: {data['rule']['asked']}.",
        "",
        "## The verdicts",
        "",
        "A study is admitted when both ends are drawn or in view; look means a border case at one end, admitted "
        "only after a person's look; not admitted means C2 or the sacrum is out of the field, or no level is "
        "drawn. Whole by masks means no level to add; to complete means a segmenter adds the levels listed below.",
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
        "SPINEPS or with the release's masks, never raising a tier.",
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
        "## The head table",
        "",
        "How far C2's top lies above each level's top, in mm, in spines of all three members that draw both whole.",
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
        "The rule run with C1 and C2 hidden on spines that draw them whole (it should find C2 in view), with the "
        "sacrum hidden on spines that draw it (it should find the sacrum in view), and on spines whose head-most "
        "drawn level is cut by the field's top (it must call C2 out):",
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
