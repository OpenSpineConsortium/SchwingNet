"""A reader's per-vertebra truth joined to the measures morphometry took on the same masks, and
what one measure screens: the AUC with a bootstrap over persons, sensitivity and specificity at
a cut, the agreement of the grade a ratio implies with the reader's, and why a graded vertebra
had no reading.

    python -m screening truth-from-riedel GRADES.csv --out truth.csv
    python -m screening join --rows rows.csv --truth truth.csv [--facts facts.jsonl] [--persons MAP.json] --out joined.csv
    python -m screening detect --joined joined.csv --out aggregates.json [--cut 0.8] [--boot 2000] [--seed 20261029]
    python -m screening neighbours --joined joined.csv --out neighbours.csv

The truth form is one CSV row per graded vertebra: study, level, truth (an integer grade; 0 is
sound), person (the study's person, filled from --persons where the table leaves it blank). Riedel's
VerSe table (Genant_Fractures_thoracolumbar_reference.csv, osf.io/download/zy68u/, sha256
9859a382c65bb23c374db7e269a7e090a928e0f6ea3fe1510f42407e186b5629) is the first truth, and
truth-from-riedel writes it in that form; any dataset's reads join the same way once they are in it.

Rules, fixed before the join was looked at (the helper thread's verse_genant.py, 29 October 2026,
whose numbers screening/tests/test_truth.py holds this module to):
- A grade is a cell holding 0, 1, 2 or 3; a cell holding anything else (Riedel's table holds 5 and 8,
  which Genant's scale does not have and the table does not define) is no grade, counted and left out.
- A vertebra is a person's level: where two studies of one person are graded at one level, the
  reading taken is the study where more ratios read, then the one whose mask holds more of the level's
  voxels (from the facts), then the lower study id; the others are counted as duplicates.
- The smaller ratio is the least of the ratio keys that read (body_index_ant_post and
  body_index_mid_post); a vertebra where neither reads has no reading, and the reason is the measure's
  own note, then its heights', then the level's absence from the mask.
- A lower ratio means a fracture. The AUC counts a tie as half. Genant's cut: a vertebra whose smaller
  ratio is under 0.80 is called fractured. The grade the ratio implies is 0 at 0.80 or more, 1 from
  0.75, 2 from 0.60, 3 under 0.60 (Genant's 20, 25 and 40 per cent).
- The bootstrap resamples persons, BOOT times from SEED (stats.py), so an interval is the same on every run.

The decisions are pure functions over plain values with contracts; the CSV, JSON and the random
picks stay in the private readers and in __main__.py. VerSe is never pooled with ENHANCE.PET: a join
takes one dataset's rows and one dataset's truth.
"""
from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Sequence, Tuple

from . import LUMBAR, THORACIC
from .contracts import beartype, ensure, require
from .stats import BOOT, SEED, auc, boot_interval, quartiles, share, weighted_kappa

MEASURES = ("h_ant", "h_mid", "h_post_inset", "body_index_ant_post", "body_index_mid_post")
RATIOS = ("body_index_ant_post", "body_index_mid_post")
GRADES = ("0", "1", "2", "3")
# Genant's range, T4 to L4
GENANT_RANGE = tuple("T%d" % i for i in range(4, 13)) + ("L1", "L2", "L3", "L4")
CUT = 0.80
# the grade a ratio implies: 0 at or above the first, 1 at or above the second, 2 at or above the third
GRADE_CUTS = (0.80, 0.75, 0.60)
TRUTH_FIELDS = ("study", "level", "truth", "person")
JOINED_FIELDS = ("study", "person", "level", "region", "truth", *MEASURES, "smaller_ratio", "ratios_read",
                 "coarsest_mm", "slice_mm", "duplicates", "no_reading")


# ---------------------------------------------------------------- pure decisions

@beartype
@require(lambda ratio: math.isfinite(ratio), "a ratio that read")
@ensure(lambda result: 0 <= result <= 3, "a Genant grade")
def implied_grade(ratio: float) -> int:
    """The grade a height ratio implies under Genant's cuts (GRADE_CUTS)."""
    for grade, cut in enumerate(GRADE_CUTS):
        if ratio >= cut:
            return grade
    return 3


@beartype
def smaller_ratio(values: Dict[str, float]) -> Optional[float]:
    """The least of the ratio keys that read, or None where neither did."""
    got = [values[k] for k in RATIOS if k in values and math.isfinite(values[k])]
    return min(got) if got else None


@beartype
def region_of(level: str) -> str:
    """thoracic, lumbar, or cervical for anything else, so strata read by region."""
    if level in THORACIC:
        return "thoracic"
    return "lumbar" if level in LUMBAR else "cervical"


@beartype
@require(lambda code: len(code) >= 0, "a cell's text")
def grade_of(code: str) -> Optional[int]:
    """The grade a cell holds, or None where it holds anything but 0, 1, 2 or 3."""
    text = code.strip()
    return int(text) if text in GRADES else None


@beartype
@require(lambda candidates: len(candidates) >= 1, "at least one graded study of the person's level")
@require(lambda candidates: all(c["ratios_read"] >= 0 and c["voxels"] >= 0 for c in candidates), "counts")
@ensure(lambda candidates, result: result[0] in candidates and len(result) == len(candidates), "the same candidates, reordered")
def reading_order(candidates: Sequence[dict]) -> List[dict]:
    """The studies of one person's level in the order a reading is taken from them: more ratios
    read first, then more voxels of the level, then the lower study id."""
    return sorted(candidates, key=lambda c: (-c["ratios_read"], -c["voxels"], c["study"]))


@beartype
@require(lambda cut: 0.0 < cut < 10.0, "a cut on a ratio")
def below_cut(values: Sequence[float], cut: float) -> int:
    """How many values lie under the cut."""
    return sum(1 for v in values if v < cut)


@beartype
@require(lambda items: all(math.isfinite(it["ratio"]) and 0 <= it["truth"] <= 3 for it in items), "read vertebrae with grades")
@require(lambda cut: 0.0 < cut < 10.0, "a cut on a ratio")
def detect(items: Sequence[dict], label: str, cut: float = CUT) -> dict:
    """What the smaller ratio screens in one stratum: the AUC for grade 1 and over and for grade 2
    and over against grade 0, the sensitivity and specificity at the cut, and how many sound
    vertebrae the cut calls fractured."""
    neg = [it["ratio"] for it in items if it["truth"] == 0]
    pos1 = [it["ratio"] for it in items if it["truth"] >= 1]
    pos2 = [it["ratio"] for it in items if it["truth"] >= 2]
    at = "at_%.2f" % cut
    return {"stratum": label, "vertebrae": len(items), "persons": len({it["person"] for it in items}),
            "grade0": len(neg), "grade1plus": len(pos1), "grade2plus": len(pos2),
            "auc_grade1plus": round(auc(neg, pos1), 4) if pos1 and neg else None,
            "auc_grade2plus": round(auc(neg, pos2), 4) if pos2 and neg else None,
            "sens_grade1plus_" + at: share(below_cut(pos1, cut), len(pos1)),
            "sens_grade2plus_" + at: share(below_cut(pos2, cut), len(pos2)),
            "spec_" + at: share(len(neg) - below_cut(neg, cut), len(neg)),
            "grade0_below_" + at.split("_")[1]: share(below_cut(neg, cut), len(neg)),
            "grade0_below_%s_count" % at.split("_")[1]: below_cut(neg, cut)}


@beartype
@require(lambda items: all(math.isfinite(it["ratio"]) for it in items), "read vertebrae")
def groups_by_person(items: Sequence[dict], from_grade: int) -> List[Tuple[List[float], List[float]]]:
    """Each person's negatives (grade 0) and positives (grade at or over from_grade), persons in
    sorted order, so the bootstrap's picks index the same person on every run."""
    by: Dict[str, Tuple[List[float], List[float]]] = {}
    for it in items:
        neg, pos = by.setdefault(it["person"], ([], []))
        (pos if it["truth"] >= from_grade else neg).append(it["ratio"])
    return [by[p] for p in sorted(by)]


def strata(read: Sequence[dict]) -> List[Tuple[str, List[dict]]]:
    """The strata the aggregates report: all, by region, Genant's range, by slice thickness, and the
    vertebrae where both ratios read."""
    return [("all", list(read)),
            ("thoracic", [it for it in read if it["region"] == "thoracic"]),
            ("lumbar", [it for it in read if it["region"] == "lumbar"]),
            ("T4 to L4", [it for it in read if it["level"] in GENANT_RANGE]),
            ("coarsest at most 1.25 mm", [it for it in read if (it["coarsest_mm"] or 99) <= 1.25]),
            ("coarsest over 1.25 mm", [it for it in read if (it["coarsest_mm"] or 99) > 1.25]),
            ("both ratios read", [it for it in read if it["ratios_read"] == 2])]


def agreement(read: Sequence[dict]) -> dict:
    """The quadratic weighted kappa of the reader's grade against the grade the ratio implies, the
    matrix (rows the reader's, columns the implied) and the exact agreement."""
    if not read:
        return {}
    kappa, matrix = weighted_kappa([it["truth"] for it in read], [implied_grade(it["ratio"]) for it in read])
    return {"quadratic_weighted_kappa": round(kappa, 4), "rows_readers_grade_cols_implied_grade": matrix,
            "exact": round(sum(matrix[i][i] for i in range(4)) / len(read), 4)}


def per_grade(joined: Sequence[dict]) -> dict:
    """Per grade: vertebrae, persons, how many read, and the quartiles of each measure."""
    out = {}
    for grade in range(4):
        rows = [row for row in joined if row["truth"] == grade]
        out[str(grade)] = {"vertebrae": len(rows), "persons": len({row["person"] for row in rows}),
                           "read": sum(1 for row in rows if row["smaller_ratio"] is not None),
                           **{k: quartiles([row[k] for row in rows if row[k] is not None])
                              for k in MEASURES + ("smaller_ratio",)}}
    return out


def no_reading(joined: Sequence[dict], read: Sequence[dict]) -> dict:
    unread = [row for row in joined if row["smaller_ratio"] is None]
    why = Counter(row["no_reading"][0] for row in unread if row["no_reading"])
    return {"vertebrae": len(unread), "by_grade": dict(Counter(str(row["truth"]) for row in unread)),
            "reasons": dict(why.most_common()), "one_ratio_only": sum(1 for it in read if it["ratios_read"] == 1)}


def aggregates(joined: Sequence[dict], counts: dict, picks: Sequence[Sequence[int]], cut: float = CUT) -> dict:
    """Everything detect writes for one dataset, the bootstrap's picks given (the whole stratum's
    persons for grade 1 and over; the persons with a grade other than 1 for grade 2 and over)."""
    read = [dict(row, ratio=row["smaller_ratio"]) for row in joined if row["smaller_ratio"] is not None]
    detection = [detect(items, label, cut) for label, items in strata(read)]
    sub2 = [it for it in read if it["truth"] != 1]
    detection[0]["auc_grade1plus_ci95"] = list(boot_interval(groups_by_person(read, 1), _fit(picks, read)))
    detection[0]["auc_grade2plus_ci95"] = list(boot_interval(groups_by_person(sub2, 2), _fit(picks, sub2)))
    return {"counts": dict(counts), "per_grade": per_grade(joined), "detection": detection,
            "agreement": agreement(read), "no_reading": no_reading(joined, read)}


def _fit(picks: Sequence[Sequence[int]], items: Sequence[dict]) -> List[List[int]]:
    """The picks for the number of persons the items hold: each pick drawn for that count (the
    helper's rng.integers(0, n, n) per resample), so a stratum with fewer persons re-draws."""
    n = len({it["person"] for it in items})
    return [list(pick[:n]) for pick in picks if len(pick) >= n] if n else []


# ---------------------------------------------------------------- the truth form

def riedel_cells(text: str) -> List[dict]:
    """The cells of Riedel's semicolon table: the first column the series number (verse<number>),
    the header the levels, each non-blank cell a code."""
    rows = list(csv.reader(text.splitlines(), delimiter=";"))
    head = [h.strip() for h in rows[0]]
    cells = []
    for r in rows[1:]:
        if not r or not r[0].strip():
            continue
        for level, code in zip(head[1:], r[1:]):
            if code.strip():
                cells.append({"study": "verse" + r[0].strip(), "level": level, "code": code.strip()})
    return cells


def truth_rows(cells: Sequence[dict]) -> Tuple[List[dict], Counter]:
    """The truth form of a table's cells, and the codes that are no grade, counted."""
    not_grades: Counter = Counter()
    rows = []
    for cell in cells:
        grade = grade_of(cell["code"])
        if grade is None:
            not_grades[cell["code"]] += 1
        else:
            rows.append({"study": cell["study"], "level": cell["level"], "truth": grade, "person": cell.get("person", "")})
    return rows, not_grades


# ---------------------------------------------------------------- the join

def read_measures(path: str) -> dict:
    """morphometry's rows.csv: the values per (study, level), the flag notes, the study rows, the
    note an unread measure carries, and the levels that have rows."""
    vals: dict = defaultdict(dict)
    flags: dict = defaultdict(list)
    study: dict = defaultdict(dict)
    notes: dict = defaultdict(dict)
    seen: dict = {}
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            s, lv, k = r["study"], r["level"], r["key"]
            if lv == "study":
                study[s][k] = r["value"] if r["value"] else r["note"]
                if k.startswith("flag"):
                    flags[(s, "study")].append(r["note"])
                continue
            seen[(s, lv)] = True
            _take_cell(r, s, lv, k, vals, flags, notes)
    return {"vals": vals, "flags": flags, "study": study, "notes": notes, "seen": seen}


def _take_cell(r: dict, s: str, lv: str, k: str, vals: dict, flags: dict, notes: dict) -> None:
    if k.startswith("flag"):
        flags[(s, lv)].append(r["note"])
    elif k in MEASURES and r["value"]:
        v = float(r["value"])
        if math.isfinite(v):
            vals[(s, lv)][k] = v
    elif k in MEASURES:
        notes[(s, lv)][k] = r["note"]


def read_truth(path: str) -> List[dict]:
    with open(path, newline="") as f:
        return [{"study": r["study"], "level": r["level"], "truth": int(r["truth"]), "person": r.get("person", "")}
                for r in csv.DictReader(f)]


def read_facts_levels(path: Optional[str]) -> Dict[str, Dict[str, int]]:
    """{study: {level: voxels}} from a facts file (this package's or holdings', both with levels)."""
    if not path:
        return {}
    out = {}
    with open(path, encoding="ascii") as f:
        for line in f:
            row = json.loads(line)
            out[row["id"]] = {name: e["voxels"] for name, e in row.get("levels", {}).items()}
    return out


def read_persons(path: Optional[str]) -> Dict[str, str]:
    """{study: person} from a JSON object, or from SchwingNet's series.json ({"series": [{series, patient}]})."""
    if not path:
        return {}
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, dict) and "series" in data:
        return {s["series"]: s["patient"] for s in data["series"]}
    return {str(k): str(v) for k, v in data.items()}


def why_unread(s: str, lv: str, measures: dict, held: dict) -> str:
    """Why neither ratio read: the ratio's own note, then its heights' notes; a level's other flags
    are kept beside it in joined.csv but never taken for the reason."""
    if s not in measures["study"]:
        return "study not measured"
    if held and s in held and lv not in held[s]:
        return "level not in the mask"
    if (s, lv) not in measures["seen"]:
        study_flags = measures["flags"].get((s, "study"))
        return "no row for the level" + ("; " + study_flags[0] if study_flags else "")
    for k in RATIOS + ("h_post_inset", "h_ant", "h_mid"):
        if measures["notes"][(s, lv)].get(k):
            return measures["notes"][(s, lv)][k]
    return "the heights did not read and the code left no note"


def _candidate(truth: dict, measures: dict, held: dict) -> dict:
    s, lv = truth["study"], truth["level"]
    v = measures["vals"].get((s, lv), {})
    return {"study": s, "truth": truth["truth"], "ratios_read": sum(1 for k in RATIOS if k in v),
            "voxels": held.get(s, {}).get(lv, 0)}


def _joined_row(chosen: dict, others: Sequence[dict], person: str, lv: str, measures: dict, held: dict) -> dict:
    s = chosen["study"]
    v = measures["vals"].get((s, lv), {})
    r = smaller_ratio(v)
    st = measures["study"].get(s, {})
    row = {"study": s, "person": person, "level": lv, "truth": chosen["truth"], "region": region_of(lv),
           "coarsest_mm": float(st["coarsest_mm"]) if st.get("coarsest_mm") else None,
           "slice_mm": float(st["slice_mm"]) if st.get("slice_mm") else None,
           "duplicates": [c["study"] for c in others]}
    for k in MEASURES:
        row[k] = round(v[k], 4) if k in v else None
    row["smaller_ratio"] = round(r, 4) if r is not None else None
    row["ratios_read"] = sum(1 for k in RATIOS if k in v)
    row["no_reading"] = ([why_unread(s, lv, measures, held)] + measures["flags"].get((s, lv), [])) if r is None else []
    return row


def join(truths: Sequence[dict], measures: dict, persons: Dict[str, str], held: dict) -> Tuple[List[dict], dict]:
    """One row per person's level, the reading taken by reading_order; the counts beside them."""
    groups: dict = defaultdict(list)
    for t in truths:
        person = t.get("person") or persons.get(t["study"], t["study"])
        groups[(person, t["level"])].append(t)
    joined, conflicts, duplicates = [], [], 0
    for (person, lv), ts in sorted(groups.items()):
        ordered = reading_order([_candidate(t, measures, held) for t in ts])
        if len({c["truth"] for c in ordered}) > 1:
            conflicts.append({"person": person, "level": lv, "truths": [c["truth"] for c in ordered]})
        duplicates += len(ordered) - 1
        joined.append(_joined_row(ordered[0], ordered[1:], person, lv, measures, held))
    counts = {"cells_graded": len(truths), "vertebrae": len(joined), "duplicates_dropped": duplicates,
              "conflicting_duplicates": len(conflicts)}
    return joined, {**counts, "conflicts": conflicts}


# ---------------------------------------------------------------- joined.csv in and out

def write_joined(rows: Sequence[dict], path: str) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(JOINED_FIELDS), lineterminator="\n")
        w.writeheader()
        for row in rows:
            w.writerow({**{k: ("" if row.get(k) is None else row.get(k)) for k in JOINED_FIELDS},
                        "duplicates": " ".join(row["duplicates"]), "no_reading": " | ".join(row["no_reading"])})


RENAMED = {"series": "study", "patient": "person", "grade": "truth", "duplicate_series": "duplicates"}


def read_joined(path: str) -> List[dict]:
    """joined.csv back into rows, in this module's names or the helper thread's (series, patient, grade)."""
    out = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            row = {RENAMED.get(k, k): v for k, v in r.items()}
            row["truth"] = int(row["truth"])
            row["ratios_read"] = int(row["ratios_read"])
            for k in MEASURES + ("smaller_ratio", "coarsest_mm", "slice_mm"):
                row[k] = float(row[k]) if row.get(k) else None
            row["duplicates"] = row["duplicates"].split() if row.get("duplicates") else []
            row["no_reading"] = [p.strip() for p in row["no_reading"].split("|")] if row.get("no_reading") else []
            out.append(row)
    return out


def picks_from_numpy(seed: int, n: int, boot: int) -> List[List[int]]:
    """The bootstrap's picks as the helper drew them: numpy's default_rng(seed).integers(0, n, n),
    boot times in order. The one use of numpy in this module, at the edge."""
    import numpy as np
    rng = np.random.default_rng(seed)
    return [[int(i) for i in rng.integers(0, n, n)] for _ in range(boot)] if n else []


# ---------------------------------------------------------------- the neighbour check

def neighbour_rows(joined: Sequence[dict]) -> List[dict]:
    """One explanation for missed grade 2 and 3 vertebrae: a crush lowers all three heights, so a
    ratio inside one vertebra cannot see it. Each read vertebra's posterior height against the
    median of its sound neighbours' in the same study, by grade and whether the cut caught it."""
    order = [*THORACIC, *LUMBAR]
    by = {(r["study"], r["level"]): r for r in joined}
    out: dict = {}
    for r in joined:
        if r["smaller_ratio"] is None or r["level"] not in order or r["h_post_inset"] is None:
            continue
        i = order.index(r["level"])
        near = [by.get((r["study"], order[j])) for j in (i - 1, i + 1) if 0 <= j < len(order)]
        heights = [n["h_post_inset"] for n in near if n and n["h_post_inset"] is not None and n["truth"] == 0]
        if not heights:
            continue
        rel = r["h_post_inset"] / (sorted(heights)[len(heights) // 2] if len(heights) % 2 else sum(heights) / 2)
        out.setdefault((r["truth"], r["smaller_ratio"] >= CUT), []).append(rel)
    return [{"truth": g, "caught": not missed, "n": len(xs), "median_post_over_neighbours": round(_median(xs), 3),
             "share_under_0.80": round(sum(x < 0.80 for x in xs) / len(xs), 2)}
            for (g, missed), xs in sorted(out.items())]


def _median(xs: Sequence[float]) -> float:
    s = sorted(xs)
    return s[len(s) // 2] if len(s) % 2 else (s[len(s) // 2 - 1] + s[len(s) // 2]) / 2
