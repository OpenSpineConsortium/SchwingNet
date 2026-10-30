"""The persons this evaluation may read as test, written before any run trains, so that no run whose checkpoint the
evaluation may start from ever trains on them.

    # in SchwingNet, at the commit the evaluation freezes
    python3 tools/gold3_ct.py build --root DIR
    python3 tools/gold3_ct.py export --format json --tier gold3 --root DIR > gold3.jsonl
    python3 tools/gold3_ct.py query "SELECT i.item, i.count_class, i.duplicate_of, a.call_by_names, a.class
        FROM item i LEFT JOIN anomaly a ON a.item = i.item WHERE i.tier = 'gold3' ORDER BY i.item" \
        --root DIR --json > gold3-calls.jsonl
    # here
    python3 -I draw_test_reserve.py gold3.jsonl gold3-calls.jsonl --schwingnet SCHWINGNET_CLONE \
        --schwingnet-commit SHA --out latent-prior-test-reserve.json --groups-out latent-prior-repeat-groups.json \
        --report reserve-report.json [--test-share 0.2 --parts-out parts.jsonl]

The reserve is a JSON list in data/splits/test-persons.json's form ("person", "why") with a third key, "class": the
store's class, or "outside_export" for a study outside the export (SchwingNet's catalog.load_split, whose rows forbid
an extra key, does not read it as it is). It is sorted by person, and the auto-anatomist flow reads it beside that
file and leaves out of every part it trains or validates on. The
groups file lists every unit of more than one study by the export's person keys, so that a run keeps each in one part.
The report pins every input and both outputs by sha256 and gives the counts by stratum and part, in units and in
studies, at both test shares section 8 allows (0.2, and 0.3 if the naming bar of stage 2 is wider than three points).
With --parts-out it also writes every study's part, unit, family and whether the first run reads it, at the share the
PREREG freezes, which is the evaluation's split: the evaluation reads its test part from that file and this reserve
and never draws it again from a later export, so a person not listed here is never test, and any fallback to the hash
draws by the unit column of that file, never by a row's own person key.

The rule, section 8 and decision 7 of the README, with greg's rule of 2026-10-30 09:43 UTC on the anomalies:

- Every class belongs to one family, ribs first, as section 8's truth is: thirteen rib-bearing bodies are a T13
  (l6_thirteen_ribs, thirteen_ribs, VerSe's t13); eleven, or eleven on one side and twelve on the other, are a
  thoracic rib anomaly (eleven_ribs, asymmetric_ribs); twelve go by the column's length, an L6 below an L5 a six
  lumbar column (l6_twelve_ribs) and L4 on the sacrum a four lumbar one (four_lumbar_twelve_ribs). VerSe draws no
  ribs, so its readers' l6 and four_lumbar go to six lumbar and four lumbar by the read (verse581's read, 7/11/6/5,
  is eleven thoracic and so a rib anomaly by its ribs, but it is a held fold person in no part). TotalSegmentator's
  ribs are not read against its levels, so the l6 its masks name is a family of its own, six_lumbar_by_names,
  reported apart and never pooled with six lumbar until its ribs are counted. normal and unread are families of
  their own, and a study of a doubt class is of the family doubt.
- The first run trains, validates and tests on normal spines alone: the store's class normal confirmed by the masks
  (status confirmed_by_masks: twelve rib pairs, C2 to L5 named, every structural check passed), as the annealer
  screen takes them, or read normal by VerSe's readers with an L5 its masks draw (admission.json's flag no_l5 marks
  a fused L5 they leave undrawn, as verse573's sacralised one). Every other study waits for a later run.

- A unit is hashed as data/splits/rule.json hashes a person (sha256 over 'schwingnet-split|' + salt + '|' + key, its
  first 8 bytes big-endian, over 2**64), with rule.json's salt: validation below 0.1, the test band from 0.1 to 0.1
  plus the share, train above.
- ENHANCE.PET studies that are probably one patient's repeat scans are one unit, read from
  data/gold3-ct/enhance-pet/facts.jsonl with repaired masks left out. Two studies are linked when they are autoPET
  studies at most 3 ids apart whose vertebral volumes agree, or studies of one site, at any ids, whose vertebral
  volumes agree loosely and whose vertebral spacings or rib volumes agree too. Vertebral volumes agree when, over at
  least 15 shared levels C3 to L4 (each of 200 voxels or more, one component), the mean absolute log ratio of the
  volumes in mm^3 is under 0.03, loosely under 0.05; spacings agree when, over at least 12 shared pairs of consecutive
  such levels, the mean absolute log ratio of the distances between their centroids is under 0.015; rib volumes agree
  when, over at least 16 shared rib labels (each of 500 voxels or more, one component, on the vertebra mask's grid),
  the mean absolute log ratio of the volumes in mm^3 is under 0.04. Links are joined by union-find over every study
  of the facts, in the export or not. A unit is keyed by the person key of its group's lowest study id (member:id for a
  study outside the export), hashed, drawn and given its part by that key, counts once in its stratum, and its studies
  always share a part. A unit whose studies outside doubt read different classes (or the same class with different
  calls) is in doubt as a whole, since one patient read two ways means a reading, or the link, is wrong; a person
  settles it. data/splits/aliases.json takes over once it lists anything; until then this rule refuses to run on a
  non-empty one rather than ignore it.
- Plain studies (classes normal and unread) are drawn by the hash. A study of an anomaly class (l6_twelve_ribs,
  l6_thirteen_ribs, eleven_ribs, four_lumbar_twelve_ribs, thirteen_ribs, asymmetric_ribs, l6, t13, four_lumbar) is
  not tested by the hash; holdout units count in no stratum. Its stratum is the member, the store's class and the call by
  names (member:class:call, the call 'none' where the store has none), so the eleven-rib columns with L4 on the sacrum
  are a stratum apart from those with L5; each stratum lies inside one family and is drawn on its own, so every
  family is split across test and train, though a stratum of one unit is wholly test (at 3abc2fa,
  enhance_pet:asymmetric_ribs:T12L4). Each stratum's units are ordered by the bytes of sha256 over
  'schwingnet-latent-prior-test|2026-10-30|' + stratum + '|' + unit key, ascending, and its test units are the first
  min(n, max(ceil(share * n), min(10, floor(n / 2)))) of n. A unit of the stratum not drawn is train: the anomalies
  are split across test and train alone, and a run's choices are made on the normal validation part.
- A study in doubt is in no part, neither trained nor tested here, until a person has looked: the store's classes
  look, open, labelling_error and not_whole; anomaly-holdout.json's disputed persons; and, for every member, a study
  whose release masks lack a level from C2 to L5 that a segmenter adds (admission.json, complete), since a machine-
  added level is never pooled with the release's masks. A study whose list holds only the sacrum stays. Doubt comes
  before every other branch: a held or holdout study in doubt is held.
- anomaly-holdout.json's holdout persons are test at every share, never trained on: testing trains nothing, and
  section 8 reports T13 as a type on them, descriptively; a holdout unit counts in no stratum and carries no
  weight in a number pooled over strata. A study the store marks training_allowed 0 otherwise (the
  holdout's fold persons, which the route's other fine-tunes train on) is held: in no part and not reserved.
- The reserve is every unit not held that is test at 0.3, or whose hash is in the band [0.1, 0.4) whatever its
  kind, so that decision 7's fallback to the plain hash draw, and a reader's look that moves a study into or out of a
  class, can never make a study test after a run trained on it. Studies outside the export that wait on a person are
  reserved with their unit where they are in one, else by their own key's band: those admission.json marks look,
  and those it admits but the export leaves out, at 3abc2fa the ENHANCE.PET studies whose repaired masks
  (facts.jsonl's rows with repaired_from) keep them out of gold 3 until a person checks them. Every study of a reserved unit is listed, each with its own why.

A person is the export's person key (enhance_pet:0001, verse:..., totalsegmentator:...), compared by exact string.
This evaluation's arm F starts from an annealer checkpoint only where the run recorded this file's sha256 and no
listed person is in that run's training manifest; otherwise arm F trains from scratch.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import itertools
import json
import math
import os
import sys

SALT = "schwingnet-2026-10-21"
RANK_PREFIX = "schwingnet-latent-prior-test"
RANK_SALT = "2026-10-30"
VALIDATION_SHARE = 0.1
SHARES = (0.2, 0.3)
RESERVE_SHARE = max(SHARES)
STRATUM_FLOOR = 10
HASH_SPAN = 2**64

REPEAT_ID_GAP = 3
REPEAT_VOLUME = 0.03
REPEAT_LOOSE_VOLUME = 0.05
REPEAT_SPACING = 0.015
REPEAT_MIN_LEVELS = 15
REPEAT_MIN_SPACINGS = 12
REPEAT_MIN_VOXELS = 200
REPEAT_RIBS = 0.04
REPEAT_MIN_RIBS = 16
REPEAT_MIN_RIB_VOXELS = 500
REPEAT_LABELS = tuple(range(3, 24))

ANOMALY_CLASSES = frozenset({
    "l6_twelve_ribs", "l6_thirteen_ribs", "eleven_ribs", "four_lumbar_twelve_ribs", "thirteen_ribs",
    "asymmetric_ribs", "l6", "t13", "four_lumbar",
})
DOUBT_CLASSES = frozenset({"look", "open", "labelling_error", "not_whole"})
PLAIN_CLASSES = frozenset({"normal", "unread"})
FAMILY_OF = {
    "normal": "normal", "unread": "unread",
    "l6_twelve_ribs": "six_lumbar", "l6": "six_lumbar",
    "four_lumbar_twelve_ribs": "four_lumbar", "four_lumbar": "four_lumbar",
    "l6_thirteen_ribs": "t13", "thirteen_ribs": "t13", "t13": "t13",
    "eleven_ribs": "rib_anomaly", "asymmetric_ribs": "rib_anomaly",
}
ANOMALY_FAMILIES = ("four_lumbar", "six_lumbar", "t13", "rib_anomaly")
FAMILY_BY_MEMBER = {("totalsegmentator", "l6"): "six_lumbar_by_names"}
FIRST_RUN_STATUS = "confirmed_by_masks"
FIRST_RUN_PARTS = frozenset({"train", "validation", "test"})
assert {c for c, f in FAMILY_OF.items() if f in ANOMALY_FAMILIES} == ANOMALY_CLASSES
assert set(FAMILY_OF) == ANOMALY_CLASSES | PLAIN_CLASSES
NAMED_LEVELS = frozenset(
    [f"C{n}" for n in range(2, 8)] + [f"T{n}" for n in range(1, 13)] + [f"L{n}" for n in range(1, 6)])
ALIAS_KEYS = frozenset({"persons", "sources"})

SCHWINGNET_INPUTS = {
    "admission": "data/gold3-ct/admission.json",
    "anomaly_holdout": "data/splits/anomaly-holdout.json",
    "aliases": "data/splits/aliases.json",
    "rule": "data/splits/rule.json",
    "enhance_pet_facts": "data/gold3-ct/enhance-pet/facts.jsonl",
}


def split_value(key: str) -> float:
    """rule.json's hash of a person, as a share of the 64-bit span."""
    text = f"schwingnet-split|{SALT}|{key}".encode()
    return int.from_bytes(hashlib.sha256(text).digest()[:8], "big") / HASH_SPAN


def rank_key(stratum: str, key: str) -> bytes:
    """The order a stratum's units are drawn in; fixed by the unit and the stratum alone."""
    return hashlib.sha256(f"{RANK_PREFIX}|{RANK_SALT}|{stratum}|{key}".encode()).digest()


def stratum_count(n: int, share: float) -> int:
    """How many units of a stratum of n are tested at a share: the share, rounded up, but at least ten where the
    stratum has twenty, and half of it, rounded down, where it has fewer."""
    return min(n, max(math.ceil(share * n), min(STRATUM_FLOOR, n // 2)))


def in_band(value: float, share: float) -> bool:
    return VALIDATION_SHARE <= value < VALIDATION_SHARE + share


def sha256_of(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def read_lines(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def read_json(path: str):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


# Reading the inputs


def read_rows(export_path: str, calls_path: str) -> list[dict]:
    """The export's rows, each with its call by names and count class from the store, checked to be one gold 3
    study a person with a class this rule places."""
    rows = read_lines(export_path)
    if not rows:
        raise SystemExit("the export is empty")
    calls = {call["item"]: call for call in read_lines(calls_path)}
    for row in rows:
        if row["tier"] != "gold3":
            raise SystemExit(f"{row['item']} is tier {row['tier']}, not gold3")
        if not row.get("person"):
            raise SystemExit(f"{row['item']} has no person key")
        call = calls.get(row["item"])
        if call is None or call["class"] != row["class"]:
            raise SystemExit(f"{row['item']} has no store call, or the store's class differs from the export's")
        row["call_by_names"] = call["call_by_names"]
        row["count_class"] = call["count_class"]
    for field in ("person", "item"):
        values = [row[field] for row in rows]
        if len(set(values)) != len(values):
            raise SystemExit(f"two rows share a {field}; the export is read one study a person")
    unknown = {row["class"] for row in rows} - ANOMALY_CLASSES - DOUBT_CLASSES - PLAIN_CLASSES
    if unknown:
        raise SystemExit(f"classes this rule does not place: {sorted(unknown)}")
    return rows


def refuse_aliases(aliases: dict) -> None:
    """Until the unit rule reads declared aliases, any declaration stops the draw rather than being ignored."""
    unknown = set(aliases) - ALIAS_KEYS
    if unknown or any(aliases.get(key) for key in ALIAS_KEYS):
        raise SystemExit("aliases.json declares aliases; rewrite the unit rule to take them before drawing")


def study_key(study: dict) -> str:
    """admission.json names a study's person where the store knows it, else only its member and id."""
    return study["person"] or f"{study['member']}:{study['id']}"


def missing_levels(admission: dict) -> dict[str, list[str]]:
    """Each admitted study whose release masks lack a level from C2 to L5, with those levels, by item."""
    out = {}
    for study in admission["studies"]:
        complete = study.get("complete") or []
        unknown = set(complete) - NAMED_LEVELS - {"sacrum"}
        if unknown:
            raise SystemExit(f"admission.json names levels this rule does not know: {sorted(unknown)}")
        named = [level for level in complete if level in NAMED_LEVELS]
        if named:
            out[f"{study['member']}:{study['id']}"] = named
    return out


def waiting_studies(admission: dict, exported: set[str]) -> dict[str, dict]:
    """Studies outside the export that admission.json waits on, by item: a look, or an admitted study the export
    leaves out because its mask was repaired and is not yet checked."""
    out = {}
    for study in admission["studies"]:
        item = f"{study['member']}:{study['id']}"
        if study["verdict"] == "look" or (study["verdict"] == "admitted" and item not in exported):
            reason = "waits for a look" if study["verdict"] == "look" else "a repaired mask not yet checked"
            out[item] = {"person": study_key(study), "item": item, "reason": reason}
    return out


def no_l5_persons(admission: dict, rows: list[dict]) -> frozenset:
    """The exported persons whose masks leave a fused L5 undrawn (admission.json's flag no_l5)."""
    person_of = {row["item"]: row["person"] for row in rows}
    flagged = (f"{study['member']}:{study['id']}" for study in admission["studies"]
               if "no_l5" in (study.get("flags") or []))
    return frozenset(person_of[item] for item in flagged if item in person_of)


def holdout_roles(holdout: dict) -> tuple[frozenset, frozenset]:
    """anomaly-holdout.json's holdout persons, and its disputed persons."""
    return frozenset(entry["person"] for entry in holdout["persons"]), frozenset(holdout["disputed"])


# Repeat scans


def whole_levels(fact: dict) -> dict[int, dict]:
    levels = {}
    for label in REPEAT_LABELS:
        level = fact["labels"].get(str(label))
        if level and level["voxels"] >= REPEAT_MIN_VOXELS and level.get("components", 1) == 1:
            levels[label] = level
    return levels


def volume_profile(fact: dict) -> dict[int, float]:
    """The log volume in mm^3 of each whole level C3 to L4."""
    zooms = fact["mask"]["zooms"]
    voxel = zooms[0] * zooms[1] * zooms[2]
    return {label: math.log(level["voxels"] * voxel) for label, level in whole_levels(fact).items()}


def spacing_profile(fact: dict) -> dict[int, float]:
    """The log distance between the centroids of each pair of consecutive whole levels C3 to L4."""
    levels = whole_levels(fact)
    out = {}
    for label in levels:
        if label + 1 in levels:
            distance = math.dist(levels[label]["centroid_mm"], levels[label + 1]["centroid_mm"])
            if distance > 0:
                out[label] = math.log(distance)
    return out


def rib_profile(fact: dict) -> dict[str, float]:
    """The log volume in mm^3 of each whole rib, where the rib mask lies on the vertebra mask's grid."""
    if not fact.get("ribs_mask", {}).get("same_grid"):
        return {}
    zooms = fact["mask"]["zooms"]
    voxel = zooms[0] * zooms[1] * zooms[2]
    return {label: math.log(rib["voxels"] * voxel) for label, rib in (fact.get("ribs") or {}).items()
            if rib["voxels"] >= REPEAT_MIN_RIB_VOXELS and rib.get("components", 1) == 1}


def profile_distance(left: dict, right: dict, minimum: int) -> float | None:
    shared = [key for key in left if key in right]
    if len(shared) < minimum:
        return None
    return sum(abs(left[key] - right[key]) for key in shared) / len(shared)


def linked(left: dict, right: dict) -> bool:
    """Whether two studies of one site are probably one patient's repeat scans."""
    volume = profile_distance(left["volume"], right["volume"], REPEAT_MIN_LEVELS)
    if volume is None or volume >= REPEAT_LOOSE_VOLUME:
        return False
    near_ids = left["site"] == "autoPET" and abs(int(left["id"]) - int(right["id"])) <= REPEAT_ID_GAP
    if near_ids and volume < REPEAT_VOLUME:
        return True
    spacing = profile_distance(left["spacing"], right["spacing"], REPEAT_MIN_SPACINGS)
    if spacing is not None and spacing < REPEAT_SPACING:
        return True
    ribs = profile_distance(left["ribs"], right["ribs"], REPEAT_MIN_RIBS)
    return ribs is not None and ribs < REPEAT_RIBS


def repeat_groups(facts_path: str) -> list[list[str]]:
    """ENHANCE.PET studies that are probably one patient's repeat scans, as lists of items, lowest id first."""
    studies = {}
    for fact in read_lines(facts_path):
        if "repaired_from" in fact or fact["id"].endswith("r"):
            continue
        studies[fact["id"]] = {"id": fact["id"], "site": fact["site"], "volume": volume_profile(fact),
                               "spacing": spacing_profile(fact), "ribs": rib_profile(fact)}
    parent = {study: study for study in studies}

    def root(study: str) -> str:
        while parent[study] != study:
            parent[study] = parent[parent[study]]
            study = parent[study]
        return study

    by_site = collections.defaultdict(list)
    for study in studies.values():
        by_site[study["site"]].append(study["id"])
    for ids in by_site.values():
        for left, right in itertools.combinations(sorted(ids, key=int), 2):
            if linked(studies[left], studies[right]):
                parent[root(right)] = root(left)
    groups = collections.defaultdict(list)
    for study in sorted(studies, key=int):
        groups[root(study)].append(f"enhance_pet:{study}")
    return [members for members in groups.values() if len(members) > 1]


# The rule


def doubt_reason(row: dict, disputed: frozenset, missing: dict[str, list[str]]) -> str | None:
    if row["class"] in DOUBT_CLASSES:
        return f"the store's class {row['class']}"
    if row["person"] in disputed:
        return "a disputed person of anomaly-holdout.json"
    if row["item"] in missing:
        return "its release masks lack " + ", ".join(missing[row["item"]]) + ", which a segmenter adds"
    return None


def kind_of(row: dict, holdout: frozenset, doubt: dict[str, str]) -> str:
    """Which branch of the rule a study takes; doubt comes first."""
    if row["person"] in doubt:
        return "doubt" if row["training_allowed"] and row["person"] not in holdout else "held"
    if row["person"] in holdout:
        return "holdout"
    if not row["training_allowed"]:
        return "held"
    if row["class"] in ANOMALY_CLASSES:
        return "stratum"
    return "plain"


def stratum_of(row: dict) -> str:
    return f"{row['member']}:{row['class']}:{row['call_by_names'] or 'none'}"


def build_units(rows, kinds, groups, waiting) -> dict[str, dict]:
    """Every study's unit: its repeat group where it has one, else itself. A unit is keyed by its group's lowest
    study, in the export or not, takes the stratum its studies outside doubt agree on, and carries the studies
    outside the export that admission.json waits on. A unit whose studies outside doubt read two ways is in doubt as
    a whole; one that mixes a held or holdout study with any other branch is refused, which no repeat link makes
    today, since only ENHANCE.PET studies are linked and none is held."""
    by_person = {row["person"]: row for row in rows}
    person_of = {row["item"]: row["person"] for row in rows}
    grouped = {}
    for group in groups:
        key = person_of.get(group[0]) or (waiting[group[0]]["person"] if group[0] in waiting else group[0])
        members = [person_of[item] for item in group if item in person_of]
        outside = [waiting[item] for item in group if item in waiting]
        if members or outside:
            for item in group:
                grouped[item] = (key, members, outside)
    units = {}
    for row in rows:
        key, members, outside = grouped.get(row["item"], (row["person"], [row["person"]], []))
        if key in units:
            if units[key]["members"] != sorted(members):
                raise SystemExit(f"two units would share the key {key}")
            continue
        placed = {kinds[p] if kinds[p] != "stratum" else "stratum " + stratum_of(by_person[p])
                  for p in members if kinds[p] != "doubt"}
        conflict = sorted(placed) if len(placed) > 1 else []
        if conflict and placed & {"held", "holdout"}:
            raise SystemExit(f"repeat group {members} spans {conflict}; the rule cannot place it")
        kind = "doubt" if conflict or not placed else placed.pop()
        units[key] = {"key": key, "members": sorted(members), "outside": outside, "kind": kind.split(" ", 1)[0],
                      "stratum": kind.split(" ", 1)[1] if kind.startswith("stratum ") else None,
                      "value": split_value(key), "conflict": conflict}
    for item, (key, members, outside) in grouped.items():
        if not members and key not in units:
            units[key] = {"key": key, "members": [], "outside": outside, "kind": "doubt", "stratum": None,
                          "value": split_value(key), "conflict": []}
    return units


def doubt_conflicts(units, kinds, doubt) -> None:
    """Put every study of a unit read two ways in doubt, with the readings that disagree."""
    for unit in units.values():
        if not unit["conflict"]:
            continue
        readings = "; ".join(unit["conflict"])
        for person in unit["members"]:
            if kinds[person] != "doubt":
                kinds[person] = "doubt"
                doubt[person] = f"its unit {unit['key']} is read two ways ({readings})"


def drawn_units(units: dict[str, dict], share: float) -> dict[str, tuple[int, int]]:
    """Each stratum's test units at a share, with the unit's rank and the stratum's size in units."""
    strata = collections.defaultdict(list)
    for unit in units.values():
        if unit["kind"] == "stratum":
            strata[unit["stratum"]].append(unit["key"])
    drawn = {}
    for stratum, keys in strata.items():
        ordered = sorted(keys, key=lambda key: rank_key(stratum, key))
        for rank, key in enumerate(ordered[: stratum_count(len(ordered), share)], start=1):
            drawn[key] = (rank, len(ordered))
    return drawn


def unit_part(unit: dict, share: float, drawn: dict[str, tuple[int, int]]) -> str:
    """The part a unit's studies outside doubt take in this evaluation at a test share."""
    if unit["kind"] in ("holdout", "held", "doubt"):
        return {"holdout": "test", "held": "held", "doubt": "doubt"}[unit["kind"]]
    if unit["key"] in drawn:
        return "test"
    if unit["kind"] == "stratum":
        return "train"
    if unit["value"] < VALIDATION_SHARE:
        return "validation"
    if in_band(unit["value"], share):
        return "test"
    return "train"


def unit_parts(units, share) -> dict[str, str]:
    drawn = drawn_units(units, share)
    return {key: unit_part(unit, share, drawn) for key, unit in units.items()}


def study_parts(units, kinds, share) -> dict[str, str]:
    parts = {}
    for key, part in unit_parts(units, share).items():
        for person in units[key]["members"]:
            parts[person] = part if kinds[person] in ("stratum", "plain", "holdout") else kinds[person]
    return parts


def family_of(member: str, klass: str) -> str:
    return FAMILY_BY_MEMBER.get((member, klass)) or FAMILY_OF.get(klass, "doubt")


def in_first_run(row: dict, part: str, no_l5: frozenset) -> bool:
    """Whether the first run reads a study: normal spines alone, confirmed by the masks or read normal by VerSe's
    readers with an L5 drawn, and only in a part it may train, validate or test on."""
    if part not in FIRST_RUN_PARTS or row["class"] != "normal":
        return False
    if row["member"] == "verse":
        return row["person"] not in no_l5
    return row["status"] == FIRST_RUN_STATUS


def unit_family(unit: dict, by_person: dict[str, dict], kinds: dict[str, str]) -> str:
    """A unit's family: its stratum's, else the family its studies outside doubt share, else doubt."""
    if unit["stratum"]:
        member, klass, _ = unit["stratum"].split(":")
        return family_of(member, klass)
    families = {family_of(by_person[p]["member"], by_person[p]["class"]) for p in unit["members"]
                if kinds[p] != "doubt"}
    return families.pop() if len(families) == 1 else "doubt"


def family_part(unit: dict, part: str) -> str:
    """The part a unit counts under in a family's counts: a holdout unit, tested in no stratum, apart."""
    return "holdout" if unit["kind"] == "holdout" else part


def unit_reserved(unit: dict, drawn: dict[str, tuple[int, int]]) -> bool:
    if unit["kind"] == "held":
        return False
    return unit_part(unit, RESERVE_SHARE, drawn) == "test" or in_band(unit["value"], RESERVE_SHARE)


def repeat_note(person: str, unit: dict) -> str:
    if person == unit["key"] or len(unit["members"]) + len(unit["outside"]) < 2:
        return ""
    return (f"; a probable repeat scan of {unit['key']} (vertebral volumes, spacings and ribs of one patient), "
            f"kept with it")


def why_of(person, unit, kind, drawn, doubt) -> str:
    never = "never trained on by a run whose checkpoint this evaluation may start from"
    if kind == "holdout":
        reason = "a holdout person of anomaly-holdout.json, tested at every share"
    elif kind == "doubt":
        reason = (f"in doubt ({doubt[person]}), in no part until a person has looked; reserved with its unit "
                  f"so that a look cannot make it test after a run trained on it")
    elif unit["key"] in drawn:
        rank, size = drawn[unit["key"]]
        reason = f"drawn for the listed test stratum {unit['stratum']} (rank {rank} of {size} units at share 0.3)"
    elif unit["kind"] == "plain":
        reason = "in the test part by rule.json's hash at the larger test share, 0.3"
    else:
        reason = (f"in rule.json's test band at 0.3 though not drawn for {unit['stratum']}; reserved so that the "
                  f"fallback hash draw, or a look that changes its class, cannot make it test after a run trained on it")
    return f"{reason}{repeat_note(person, unit)}; {never}"


def outside_why(study: dict, unit: dict | None) -> str:
    where = f"outside the gold 3 export ({study['reason']})"
    if unit is None:
        return (f"{where} and in rule.json's test band at 0.3; reserved so that its admission cannot make it test "
                "after a run trained on it")
    return (f"{where}, a probable repeat scan of {unit['key']}, reserved with its unit so that its admission cannot "
            "make it test after a run trained on it")


def reserve(rows, units, kinds, doubt, waiting) -> list[dict]:
    by_person = {row["person"]: row for row in rows}
    drawn = drawn_units(units, RESERVE_SHARE)
    listed, in_unit = [], set()
    for unit in units.values():
        in_unit.update(study["item"] for study in unit["outside"])
        if not unit_reserved(unit, drawn):
            continue
        for person in unit["members"]:
            listed.append({"person": person, "why": why_of(person, unit, kinds[person], drawn, doubt),
                           "class": by_person[person]["class"]})
        for study in unit["outside"]:
            listed.append({"person": study["person"], "why": outside_why(study, unit), "class": "outside_export"})
    known = {row["person"] for row in rows} | {entry["person"] for entry in listed}
    for item, study in waiting.items():
        if item not in in_unit and study["person"] not in known and in_band(split_value(study["person"]), RESERVE_SHARE):
            listed.append({"person": study["person"], "why": outside_why(study, None), "class": "outside_export"})
    return sorted(listed, key=lambda entry: entry["person"])


# Checks and the report


def check(rows, units, kinds, doubt, listed, groups, no_l5) -> dict:
    """The properties both threads rely on, each read apart from the branch that should make it hold; any one
    failing stops the files from being written."""
    reserved = {entry["person"] for entry in listed}
    person_of = {row["item"]: row["person"] for row in rows}
    unit_of = {person: key for key, unit in units.items() for person in unit["members"]}
    placed = [person for unit in units.values() for person in unit["members"]]
    tests = {share: {p for p, part in study_parts(units, kinds, share).items() if part == "test"}
             for share in SHARES}
    fallback = {share: {p for unit in units.values() if unit["kind"] in ("stratum", "plain")
                        and in_band(unit["value"], share) for p in unit["members"] if kinds[p] != "doubt"}
                for share in SHARES}
    exported_groups = [[person_of[item] for item in group if item in person_of] for group in groups]
    whole_units = [unit["members"] + [study["person"] for study in unit["outside"]] for unit in units.values()]
    by_person = {row["person"]: row for row in rows}
    by_unit = {share: unit_parts(units, share) for share in SHARES}
    family_parts = {share: collections.defaultdict(set) for share in SHARES}
    for share in SHARES:
        for key, part in by_unit[share].items():
            if units[key]["members"]:
                family_parts[share][unit_family(units[key], by_person, kinds)].add(family_part(units[key], part))
    study_by_share = {share: study_parts(units, kinds, share) for share in SHARES}
    first_run = [p for share in SHARES for p, part in study_by_share[share].items()
                 if in_first_run(by_person[p], part, no_l5)]
    results = {
        "reserve_not_empty": bool(listed),
        "persons_unique": len(reserved) == len(listed),
        "every_study_in_one_unit": sorted(placed) == sorted(person_of.values()),
        "repeat_groups_are_units": all(len({unit_of[p] for p in members}) <= 1 for members in exported_groups),
        "smaller_test_inside_larger": tests[min(SHARES)] <= tests[max(SHARES)],
        "larger_test_inside_reserve": tests[max(SHARES)] <= reserved,
        "fallback_tests_inside_reserve": all(fallback[share] <= reserved for share in SHARES),
        "no_unit_split_by_reserve": all(len({p in reserved for p in members}) <= 1 for members in whole_units),
        "no_held_study_reserved": not any(not row["training_allowed"] and row["person"] not in tests[RESERVE_SHARE]
                                          and row["person"] in reserved for row in rows),
        "no_doubt_study_tested": not any(p in doubt for share in SHARES for p in tests[share]),
        "no_anomaly_validated": not any(by_person[p]["class"] in ANOMALY_CLASSES and part == "validation"
                                        for share in SHARES for p, part in study_by_share[share].items()),
        "anomalies_in_strata": all(units[unit_of[row["person"]]]["kind"] == "stratum" for row in rows
                                   if row["class"] in ANOMALY_CLASSES
                                   and kinds[row["person"]] not in ("doubt", "held", "holdout")),
        "every_family_drawn_into_test_and_train": all({"test", "train"} <= family_parts[share][family]
                                                      for share in SHARES for family in ANOMALY_FAMILIES),
        "first_run_normal_only": all(
            by_person[p]["class"] == "normal" and p not in doubt and p not in no_l5
            and (by_person[p]["status"] == FIRST_RUN_STATUS if by_person[p]["member"] != "verse"
                 else bool(by_person[p]["training_allowed"]) or kinds[p] == "holdout")
            for p in first_run),
    }
    if not all(results.values()):
        failed = [name for name, ok in results.items() if not ok]
        raise SystemExit(f"checks failed: {failed}")
    return results


def summary(rows, units, kinds, no_l5) -> dict:
    """Counts at each share: units and studies by part, units by family and part (a holdout unit apart), the first
    run's units and studies by part, each stratum's units (N_h) and test units (n_h), and studies by member, class and
    part."""
    out = {}
    by_person = {row["person"]: row for row in rows}
    for share in SHARES:
        by_unit = unit_parts(units, share)
        parts = study_parts(units, kinds, share)
        drawn = drawn_units(units, share)
        strata = collections.defaultdict(lambda: [0, 0])
        for unit in units.values():
            if unit["kind"] == "stratum":
                strata[unit["stratum"]][0] += 1
                strata[unit["stratum"]][1] += unit["key"] in drawn
        counts = collections.Counter((by_person[p]["member"], by_person[p]["class"], part)
                                     for p, part in parts.items())
        families = collections.Counter((unit_family(units[key], by_person, kinds), family_part(units[key], part))
                                       for key, part in by_unit.items() if units[key]["members"])
        first = {p: part for p, part in parts.items() if in_first_run(by_person[p], part, no_l5)}
        out[str(share)] = {
            "units_by_part": dict(sorted(collections.Counter(
                part for key, part in by_unit.items() if units[key]["members"]).items())),
            "studies_by_part": dict(sorted(collections.Counter(parts.values()).items())),
            "families_units_by_part": {f"{family}|{part}": n for (family, part), n in sorted(families.items())},
            "first_run_units_by_part": dict(sorted(collections.Counter(
                part for key, part in by_unit.items() if any(p in first for p in units[key]["members"])).items())),
            "first_run_studies_by_part": dict(sorted(collections.Counter(first.values()).items())),
            "strata_units_N_h_n_h": {name: pair for name, pair in sorted(strata.items())},
            "member_class_part": {f"{m}|{c}|{p}": n for (m, c, p), n in sorted(counts.items())},
        }
    return out


def groups_listing(units) -> list[dict]:
    """Every unit of more than one study, by the export's person keys, for a run to keep in one part."""
    out = []
    for unit in units.values():
        outside = [study["person"] for study in unit["outside"]]
        if len(unit["members"]) + len(outside) > 1:
            out.append({"unit": unit["key"], "persons": unit["members"], "outside_export": outside,
                        "why": "probable repeat scans of one patient (vertebral volumes, spacings and ribs); keep in one part"})
    return sorted(out, key=lambda entry: entry["unit"])


def write_atomically(path: str, text: str) -> None:
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(temporary, path)


def list_text(entries: list[dict]) -> str:
    return "[\n" + ",\n".join("  " + json.dumps(entry) for entry in entries) + "\n]\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("export", help="the gold tier 3 export, one JSON row a study")
    parser.add_argument("calls", help="the store's call by names and count class, one JSON row a study")
    parser.add_argument("--schwingnet", required=True, help="a SchwingNet tree at the export's commit")
    parser.add_argument("--schwingnet-commit", required=True, help="the SchwingNet commit the export was made at")
    parser.add_argument("--expect-export-sha256", help="refuse an export whose sha256 differs")
    parser.add_argument("--out", required=True, help="where the reserve's JSON list is written")
    parser.add_argument("--groups-out", required=True, help="where the units of more than one study are written")
    parser.add_argument("--report", required=True, help="where the report is written")
    parser.add_argument("--test-share", type=float, choices=SHARES, help="the share the PREREG freezes")
    parser.add_argument("--parts-out", help="with --test-share, every study's part at that share, one JSON row each")
    args = parser.parse_args(argv)
    if (args.test_share is None) != (args.parts_out is None):
        parser.error("--test-share and --parts-out go together")

    paths = {name: os.path.join(args.schwingnet, rel) for name, rel in SCHWINGNET_INPUTS.items()}
    digests = {"export": sha256_of(args.export), "calls": sha256_of(args.calls)}
    digests.update({name: sha256_of(path) for name, path in paths.items()})
    if args.expect_export_sha256 and digests["export"] != args.expect_export_sha256:
        raise SystemExit(f"export sha256 {digests['export']} is not the one expected")
    rule = read_json(paths["rule"])
    if rule.get("salt") != SALT or rule.get("validation_share") != VALIDATION_SHARE:
        raise SystemExit("rule.json's salt or validation share is not the one this rule hashes with")
    refuse_aliases(read_json(paths["aliases"]))

    rows = read_rows(args.export, args.calls)
    admission = read_json(paths["admission"])
    holdout, disputed = holdout_roles(read_json(paths["anomaly_holdout"]))
    no_l5 = no_l5_persons(admission, rows)
    missing = missing_levels(admission)
    doubt = {row["person"]: reason for row in rows
             if (reason := doubt_reason(row, disputed, missing)) is not None}
    kinds = {row["person"]: kind_of(row, holdout, doubt) for row in rows}
    groups = repeat_groups(paths["enhance_pet_facts"])
    waiting = waiting_studies(admission, {row["item"] for row in rows})
    units = build_units(rows, kinds, groups, waiting)
    doubt_conflicts(units, kinds, doubt)
    listed = reserve(rows, units, kinds, doubt, waiting)
    checks = check(rows, units, kinds, doubt, listed, groups, no_l5)

    reserve_text = list_text(listed)
    groups_text = list_text(groups_listing(units))
    report = {
        "schwingnet_commit": args.schwingnet_commit,
        "inputs_sha256": digests,
        "reserve_sha256": hashlib.sha256(reserve_text.encode()).hexdigest(),
        "groups_sha256": hashlib.sha256(groups_text.encode()).hexdigest(),
        "rule": {"salt": SALT, "rank": f"sha256('{RANK_PREFIX}|{RANK_SALT}|' + stratum + '|' + unit key), ascending",
                 "validation_share": VALIDATION_SHARE, "shares": SHARES,
                 "reserve_band": [VALIDATION_SHARE, VALIDATION_SHARE + RESERVE_SHARE],
                 "stratum_floor": STRATUM_FLOOR, "repeat_id_gap": REPEAT_ID_GAP, "repeat_volume": REPEAT_VOLUME,
                 "repeat_loose_volume": REPEAT_LOOSE_VOLUME, "repeat_spacing": REPEAT_SPACING,
                 "repeat_min_levels": REPEAT_MIN_LEVELS, "repeat_min_spacings": REPEAT_MIN_SPACINGS,
                 "repeat_ribs": REPEAT_RIBS, "repeat_min_ribs": REPEAT_MIN_RIBS,
                 "repeat_min_rib_voxels": REPEAT_MIN_RIB_VOXELS, "families": FAMILY_OF,
                 "family_by_member": {f"{m}:{c}": f for (m, c), f in FAMILY_BY_MEMBER.items()},
                 "anomalies": "drawn test or train by stratum, never validation; anomaly-holdout.json's holdout "
                              "persons test in no stratum; training_allowed 0 persons held",
                 "first_run": f"class normal with status {FIRST_RUN_STATUS}, or VerSe's readers' normal whose masks "
                              "draw its L5 (no admission.json flag no_l5), "
                              f"in {sorted(FIRST_RUN_PARTS)}"},
        "rows": len(rows),
        "units": sum(1 for unit in units.values() if unit["members"]),
        "kinds": dict(sorted(collections.Counter(kinds.values()).items())),
        "doubt": {person: {"reason": reason, "kind": kinds[person]} for person, reason in sorted(doubt.items())},
        "repeat_groups_in_facts": len(groups),
        "units_of_more_than_one_study": len(groups_listing(units)),
        "units_read_two_ways": sorted(unit["key"] for unit in units.values() if unit["conflict"]),
        "reserved": len(listed),
        "reserved_by_class": dict(sorted(collections.Counter(entry["class"] for entry in listed).items())),
        "checks": checks,
        "counts": summary(rows, units, kinds, no_l5),
    }
    write_atomically(args.out, reserve_text)
    write_atomically(args.groups_out, groups_text)
    write_atomically(args.report, json.dumps(report, indent=1) + "\n")
    if args.parts_out:
        parts = study_parts(units, kinds, args.test_share)
        unit_key = {person: unit["key"] for unit in units.values() for person in unit["members"]}
        by_person = {row["person"]: row for row in rows}
        family_of_unit = {key: unit_family(unit, by_person, kinds) for key, unit in units.items()}
        lines = [json.dumps({"person": p, "part": parts[p], "unit": unit_key[p],
                             "family": family_of(by_person[p]["member"], by_person[p]["class"]),
                             "unit_family": family_of_unit[unit_key[p]],
                             "first_run": in_first_run(by_person[p], parts[p], no_l5)}) for p in sorted(parts)]
        write_atomically(args.parts_out, "\n".join(lines) + "\n")
    print(json.dumps({"reserved": len(listed), "reserve_sha256": report["reserve_sha256"],
                      "groups_sha256": report["groups_sha256"], "checks": checks}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
