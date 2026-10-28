"""The gold tier 3 CT dataset: its index, its anomaly calls, its quality checks and its manifest.

Source: the thread "Finish scan import and tier counts", 2026-10-27, for the owner's ask of 22:49 UTC:
"i want all the gold tier 3 CT data as its own dataset, with a indexable database, an artefact, and
anything i need to use it in the workflow, including anomaly statistics, and quality assurance they
are true anomalies". docs/research/gold3-ct/ is the programme's folder;
docs/research/enhance-pet-gold-tier-3.md holds the numbers the ENHANCE.PET calls must reproduce.
Confidential: nothing here, and nothing it writes, goes to a public place.

Gold tier 3 is a whole spine, C2 to the sacrum in one CT study, with a person's annotation. The members
are data/gold3-ct/members.json: ENHANCE.PET (one facts row per study, made from the published masks by
bordercall's holdings/enhance_facts.py, data/gold3-ct/enhance-pet/facts.jsonl), VerSe (17 series from
the committed records, data/gold3-ct/verse.json) and TotalSegmentator (declared, no rows until the
grid reads its subject list). Everything here is the standard library over committed files: the
masks never enter the repository, only facts read from them.

    python3 tools/gold3_ct.py build [--root DIR]          # a new version of the store, if anything changed
    python3 tools/gold3_ct.py query "SELECT ..." [--root DIR] [--json]
    python3 tools/gold3_ct.py stats                       # writes docs/research/gold3-ct/STATS.md
    python3 tools/gold3_ct.py qa                          # writes docs/research/gold3-ct/QA.md
    python3 tools/gold3_ct.py export [--format json|csv] [--tier gold3] [--training-only] [--root DIR]
    python3 tools/gold3_ct.py page                        # writes docs/research/gold3-ct/page-data.json
    python3 tools/gold3_ct.py check                       # exit 1 when a written file is stale or a row breaks its schema
    python3 tools/gold3_ct.py take-facts FACTS.jsonl FACTS_B.jsonl --read-on TEXT --bordercall-commit SHA
                                                          # a reading of the masks into the facts files

The store is tools/catalog.py's pattern, in a folder outside the repository (--root, or GOLD3_ROOT; on
the grid $DATA_ROOT/_gold3_ct): versions/gold3-NNNNNN-<12 hex>.sqlite, each sealed at mode 0444,
VERSIONS.jsonl, the append-only log, CURRENT naming the latest, and LOCK, held for a whole write. A build
whose rows equal the latest's, the code that ran it apart, makes no new version. The tables keep the
catalog's names where tools/licences.py derive and provenance read them (source, shard, person, item,
label, embedding). derive deletes only from those tables, so triggers take each dropped item's masks,
ribs, anomaly and checks, a dropped person's aliases and a dropped source's counts with it, and a cut
by a recipe carries nothing of a source the recipe refuses. provenance counts a source's studies by
item sha256, which VerSe's rows lack until the grid reads their files, so it counts their persons only.

Two column calls are kept and never merged: the call by the release's names (thoracic and lumbar labels
present) and the call by the ribs (rib k leads on its own body, label k + 7, so the lowest rib-bearing
body divides the column). One class per study follows from them and from what a person or the note
decided (data/gold3-ct/enhance-pet/record.json, data and never literals here). The status says how far
the masks alone carry it: confirmed_by_masks is the internal consistency of two masks the same readers
checked, never a reader's read of the CT, and a lumbosacral question always needs the CT. The quality
checks Q01 to Q16 are pure functions of a facts row, each threshold a named constant below with its
reason, taken from bordercall's holdings/count_enhance_pet.py where it has one.
"""

import argparse
import contextlib
import csv
import fcntl
import hashlib
import io
import itertools
import json
import os
import re
import sqlite3
import statistics
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
TOOL = "tools/gold3_ct.py"
DATA = "data/gold3-ct"
MEMBERS = f"{DATA}/members.json"
VERSE = f"{DATA}/verse.json"
TOTALSEG = f"{DATA}/totalsegmentator.json"
ENHANCE = f"{DATA}/enhance-pet"
FACTS = f"{ENHANCE}/facts.jsonl"
FACTS_RECORD = f"{ENHANCE}/FACTS.json"
# A second, independent reading of the same masks, where one is committed: check Q14 compares its
# rib leads and lumbosacral distances with the first's.
FACTS_B = f"{ENHANCE}/facts-b.jsonl"
# The three repaired rows, read from the repair record in the thread's container: bordercall keeps no
# mask in git, so a reading on the grid has the 1,597 published studies alone, and take-facts joins
# these to it. The file goes once facts.jsonl holds them; nothing else reads it.
FACTS_REPAIRED = f"{ENHANCE}/facts-repaired.jsonl"
MASK_SUMS = f"{ENHANCE}/SHA256SUMS"
CT_DETAILS = f"{ENHANCE}/ct-details.json"
RECORD = f"{ENHANCE}/record.json"
BUCKET = f"{ENHANCE}/bucket.json"
RULE = "data/splits/rule.json"
TEST_PERSONS = "data/splits/test-persons.json"
HOLDOUT = "data/splits/anomaly-holdout.json"
LICENCES = "data/licences.json"
INPUTS = (MEMBERS, VERSE, TOTALSEG, RECORD, BUCKET, FACTS, FACTS_RECORD, FACTS_B, RULE, TEST_PERSONS, HOLDOUT, LICENCES)
OUT = "docs/research/gold3-ct"
STATS_PAGE = f"{OUT}/STATS.md"
QA_PAGE = f"{OUT}/QA.md"
PAGE_DATA = f"{OUT}/page-data.json"

SCHEMA_VERSION = 1
# PRAGMA application_id of every version file: "SG3C", so SQLite's own tools name it.
APPLICATION_ID = 0x53473343
VERSIONS_DIR = "versions"
VERSIONS_LOG = "VERSIONS.jsonl"
CURRENT = "CURRENT"
LOCK = "LOCK"
VERSION_FILE = re.compile(r"^gold3-(?P<number>\d{6})-(?P<hash>[0-9a-f]{12})\.sqlite$")
STORE_VARIABLE = "GOLD3_ROOT"

# ---------------------------------------------------------------- label schemes

# ENHANCE.PET's vertebra masks: C1 to C7 are 1 to 7, T1 to T12 8 to 19, L1 to L6 20 to 25, the hips
# 26 and 27, the sacrum 28; there is no T13.
C1, C2, C7, T1, T12, L1, L4, L5, L6, SACRUM = 1, 2, 7, 8, 19, 20, 23, 24, 25, 28
TOP_VERTEBRA_LABEL = 28
LEVEL_NAMES = {**{i: f"C{i}" for i in range(1, 8)}, **{7 + i: f"T{i}" for i in range(1, 13)},
               **{19 + i: f"L{i}" for i in range(1, 7)}, 26: "hip 26", 27: "hip 27", SACRUM: "sacrum"}
# Head to foot, from C2 as the whole-spine count reads it; the hips stand beside the column.
COLUMN = (*range(C2, L6 + 1), SACRUM)
# The same with C1, for the checks that compare a label with its neighbours.
COLUMN_FROM_C1 = (C1, *COLUMN)
# The rib masks: left rib k is k, right rib k is 13 + k, the sternum 27. Rib k's own vertebra is label
# k + 7, so rib 13's own body is the one this scheme names L1 (20).
RIBS_PER_SIDE = 13
RIGHT_RIB_BASE = 13
TOP_RIB_LABEL = 26
OWN_VERTEBRA_OFFSET = 7
SIDES = ("left", "right")
# ENHANCE.PET's ids to the 28 canonical ids of tools/anomaly_pack.py (T13 20, L6 26, sacrum 27): never
# VERSE_TO_CANONICAL, which would make the right hip the sacrum and the sacrum a T13.
ENHANCE_TO_CANONICAL = {**{i: i for i in range(1, 20)}, **{19 + i: 20 + i for i in range(1, 7)}, SACRUM: 27}

# ---------------------------------------------------------------- thresholds, each with its reason

# A level counts as labelled at 200 voxels or more, the floor of the TotalSegmentator count and of
# count_enhance_pet's MIN_VOXELS: it drops specks a reader left behind, and no C2 or sacrum label in
# the release holds 1 to 199 voxels, so it moves no study into or out of the whole count.
LEVEL_MIN_VOXELS = 200
# A rib counts at 50 voxels or more (count_enhance_pet's RIB_MIN_VOXELS, the release's rule): a short
# twelfth rib on 5 mm slices holds a few hundred voxels, and 27 rib labels hold 50 to 199, none fewer.
RIB_MIN_VOXELS = 50
# The contact rule the facts were tallied with (count_enhance_pet's CONTACT_MM); it names a table row.
CONTACT_MM = 3.0
# A clear space wider than 20 mm between consecutive labels, more than any disc, holds a body with no
# label (count_enhance_pet's UNLABELLED_GAP_MM); above T12 it leaves the study out, below it the space
# is a lumbar one, which the owner's rule keeps.
UNLABELLED_GAP_MM = 20.0
# Twice the widest space between neighbours in the release's whole spines (count_enhance_pet's
# LOOK_GAP_MM): wider lists a whole study for a look.
LOOK_GAP_MM = 10.0
# With no L5 label, every label from L4 down overlaps the next head to foot by 5 mm or more, as an L5
# overlaps the sacrum in the shallowest of the 1,450 strict spines with no L6 (NO_L5_MEETS_MM).
NO_L5_MEETS_MM = -5.0
# An L5 label under a quarter of L4's voxels over an L4 that meets the sacrum is the no-L5 pattern
# with a sliver left behind (count_enhance_pet's FRAGMENT_SHARE).
FRAGMENT_SHARE = 0.25
# Two labels touch in 3-D within one voxel's diagonal: the 39 no-L5 spines put L4 0.7 to 1.2 mm from
# the sacrum, and L5 touches it in every control (enhance-pet-repair's touch.py).
TOUCH_MM = 1.5
# Across a labelled L5, L4 never comes nearer the sacrum than 2.3 mm in the 100 controls (median 15.0
# mm), so nearer than that the L5 label may be a piece and not a body.
CONTROL_NEAREST_ACROSS_L5_MM = 2.3
# More than half the ribs with contacts leading one level off the same way is a shifted ladder, a
# labelling suspect, as 0245 (every rib one up) and 1336 (every rib one down) show; fewer is a look.
SHIFT_SHARE = 0.5
# A column label under 0.4 of both neighbours' voxels is a piece split off a body: 0603's T6 holds 0.30
# of T5's and 0.22 of T7's, while a whole body's neighbours differ by far less (C1 to C2 0.79, C7 to
# T1 0.80 at the controls' medians).
SPLIT_SHARE = 0.4
# A label whose largest connected piece holds under 0.9 of its voxels has a second piece worth a look:
# 1347's T1 carried a whole body far below its own as a second piece.
COMPONENT_SHARE = 0.9
# C7 against T1 outside the controls' 1st to 99th percentile is a look: a label one level off at the
# cervicothoracic junction moves the ratio (0245's C7 held 0.99 of T1, the controls a median 0.80).
RATIO_PERCENTILES = (1, 99)
# Fewer controls than this give no percentile worth reading, so Q13 does not run.
MIN_CONTROLS_FOR_RATIO = 20
# Slices further apart than the table's thickness leave gaps it does not state (1213: 0.98 mm in the
# table, 3 mm in the file); nearer is an overlapping reconstruction, common and harmless (1 mm slices
# every 0.7 mm). The tolerance absorbs rounding in the table.
SLICE_TOLERANCE_MM = 0.05
# An affine's column lengths match the voxel sizes to a micrometre in a sane header.
AFFINE_TOLERANCE = 1e-3
# Two readings of one distance agree within the facts' rounding of 0.1 mm.
DISTANCE_AGREEMENT_MM = 0.1
# autoPET's 1,014 studies are 900 persons (Gatidis S et al., Scientific Data 2022;9:601).
AUTOPET_PERSONS = 900
AUTOPET_SITE = "autoPET"
# The 95 percent normal quantile of every Wilson interval, the project's convention.
Z95 = statistics.NormalDist().inv_cdf(0.975)

WHOLE_COUNT_CLASSES = ("strict", "no_l5", "lumbar_look")
CLASSES = ("normal", "l6_twelve_ribs", "l6_thirteen_ribs", "four_lumbar_twelve_ribs", "eleven_ribs",
           "thirteen_ribs", "asymmetric_ribs", "labelling_error", "open", "look", "not_whole", "repaired")
VERSE_CLASSES = ("t13", "l6", "four_lumbar", "normal", "unread")
STATUSES = ("confirmed_by_masks", "candidate", "labelling_error", "open", "reader_confirmed", "not_assessed")
RECORD_CLASSES = ("repaired", "labelling_error", "open", "look")
MEMBER_ORDER = ("enhance_pet", "verse", "totalsegmentator")
# A lumbosacral question no mask check can settle: the class and why the CT is needed.
NEEDS_CT = {
    "four_lumbar_twelve_ribs": "an L5 counted into the sacrum or a column one body short: sacralisation is a"
                               " lumbosacral question no mask check can settle",
    "l6_twelve_ribs": "an S1 freed from the sacrum or a column one body long: lumbarisation is a lumbosacral"
                      " question no mask check can settle",
    "l6_thirteen_ribs": "a thirteenth thoracic body over a whole sacrum and an L1 carrying a rib over a freed S1"
                        " give the same count; the ribs cannot say where the extra body arose",
}
CASTELLVI_NOTE = "Castellvi is typed by no code here; it is a person's read of the CT"

# ---------------------------------------------------------------- reading the committed files


class Gold3Error(Exception):
    """A file or a row the dataset refuses, with the reason a person reads."""


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise Gold3Error(f"{path}: {error}") from error


def read_jsonl(path):
    rows = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        try:
            rows.append(json.loads(line))
        except ValueError as error:
            raise Gold3Error(f"{path}: line {number}: {error}") from error
    return rows


def sha256_of(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def optional(repo, rel, reader):
    path = Path(repo) / rel
    return reader(path) if path.is_file() else None


def load_inputs(repo=ROOT):
    """Every committed file the dataset is built from; the facts and facts B are None until committed."""
    repo = Path(repo)
    rule = read_json(repo / RULE)
    return {
        "members": read_json(repo / MEMBERS), "verse": read_json(repo / VERSE),
        "totalsegmentator": read_json(repo / TOTALSEG), "record": read_json(repo / RECORD),
        "bucket": optional(repo, BUCKET, read_json), "facts": optional(repo, FACTS, read_jsonl),
        "facts_record": optional(repo, FACTS_RECORD, read_json), "facts_b": optional(repo, FACTS_B, read_jsonl),
        "rule": rule, "test_persons": frozenset(p["person"] for p in read_json(repo / TEST_PERSONS)),
        "holdout": read_json(repo / HOLDOUT), "licences": read_json(repo / LICENCES),
        "hashes": {rel: sha256_of(repo / rel) if (repo / rel).is_file() else None for rel in INPUTS},
    }


def code_digest(repo=ROOT):
    """The run_code style digest of the code a build runs: the kind's name, then each file's path and
    sha256, so the build table says what made the version beside what it read."""
    return hashlib.sha256(f"gold3\n{TOOL}\t{sha256_of(Path(repo) / TOOL)}\n".encode()).hexdigest()

# ---------------------------------------------------------------- the split, as tools/catalog.py has it


def person_hash(salt, person):
    """The split hash of a person: data/splits/rule.json's rule, as tools/catalog.py person_hash has it."""
    text = f"schwingnet-split|{salt}|{person}".encode()
    return int.from_bytes(hashlib.sha256(text).digest()[:8], "big")


def part_of(person, rule, test_persons):
    """Where a person goes, as schwingnet.catalog part_of decides it: a frozen test person is test, and
    everyone else is validation below validation_share of the hash space, training above."""
    if person in test_persons:
        return "test"
    return "validation" if person_hash(rule["salt"], person) < rule["validation_share"] * 2**64 else "train"


def anomaly_roles(holdout):
    """Each person data/splits/anomaly-holdout.json names, with its role: holdout or fold<k>; a scan the
    file lists under a person maps to that person."""
    roles, scans = {}, {}
    for entry in holdout.get("persons", []):
        roles[entry["person"]] = "holdout"
        for scan in entry.get("scans", []):
            scans[scan] = entry["person"]
    for entry in holdout.get("folds", []):
        roles.setdefault(entry["person"], f"fold{entry['fold']}")
    return roles, scans

# ---------------------------------------------------------------- one facts row: labels


def level_name(label):
    return LEVEL_NAMES.get(label, f"label {label}")


def label_of(row, label):
    return row["labels"].get(str(label))


def voxels_of(row, label):
    entry = label_of(row, label)
    return entry["voxels"] if entry else 0


def present(row):
    """The vertebra labels that count as labelled, at LEVEL_MIN_VOXELS or more."""
    return {int(label) for label, entry in row["labels"].items() if entry["voxels"] >= LEVEL_MIN_VOXELS}


def column_labels(have, column=COLUMN):
    return [label for label in column if label in have]


def gap_mm(row, upper, lower):
    """mm from the foot-most edge of `upper` to the head-most edge of `lower`; negative where they overlap."""
    return round(label_of(row, upper)["bottom_mm"] - label_of(row, lower)["top_mm"], 1)


def links(row):
    labels = column_labels(present(row))
    return [(upper, lower, gap_mm(row, upper, lower)) for upper, lower in zip(labels, labels[1:])]


def lumbar_tail_meets(row):
    """Whether every label from L4 down overlaps the next as deeply as an L5 overlaps the sacrum."""
    return all(gap <= NO_L5_MEETS_MM for upper, _, gap in links(row) if upper >= L4)


def missing_levels(row, last=L5):
    have = present(row)
    return [label for label in range(C2, last + 1) if label not in have]


def count_class(row):
    """count_enhance_pet's class: strict, no_l5, lumbar_look (all three whole), or why it is not whole."""
    have = present(row)
    if C2 not in have:
        return "no_c2"
    if SACRUM not in have:
        return "no_sacrum"
    missing = missing_levels(row)
    wide = [link for link in links(row) if link[2] > UNLABELLED_GAP_MM]
    if any(label < L1 for label in missing):
        return "skipped_label"
    if any(upper < T12 for upper, _, _ in wide):
        return "unlabelled_body"
    if not missing and not wide:
        return "strict"
    if missing == [L5] and not wide and lumbar_tail_meets(row):
        return "no_l5"
    return "lumbar_look"


def whole_problems(row):
    """Why a study is not whole, in words; empty for a whole study."""
    have = present(row)
    ends = [f"no {level_name(label)}" for label in (C2, SACRUM) if label not in have]
    if ends:
        return ends
    skipped = [f"{level_name(label)} missing" for label in missing_levels(row, T12)]
    wide = [f"a space of {gap} mm between {level_name(upper)} and {level_name(lower)}"
            for upper, lower, gap in links(row) if gap > UNLABELLED_GAP_MM and upper < T12]
    return skipped + wide


def l5_fragment(row):
    have = present(row)
    if not {L4, L5, SACRUM} <= have:
        return False
    small = voxels_of(row, L5) < FRAGMENT_SHARE * voxels_of(row, L4)
    return small and gap_mm(row, L4, SACRUM) <= NO_L5_MEETS_MM


def label_pattern(row):
    """What the release's lumbar names say, in words."""
    have = present(row)
    if L5 not in have and L6 in have:
        return "no L5, an L6 in its place"
    if L5 not in have and L4 in have:
        return "no L5, L4 meeting the sacrum" if lumbar_tail_meets(row) else "no L5"
    absent = [level_name(label) for label in range(L1, L5) if label not in have]
    if absent:
        return "lumbar label missing: " + ", ".join(absent)
    if L6 in have:
        return "L6 named below an L5"
    if l5_fragment(row):
        return "L5 label a fragment, L4 meeting the sacrum"
    return "C2 to L5 named"


def call_by_names(row):
    """The release's column call: T{thoracic labels}L{lumbar labels}, and the bodies above the sacrum,
    C1 counted as present where the field's top cut it off and C2 is there."""
    have = present(row)
    thoracic = sum(1 for label in range(T1, T12 + 1) if label in have)
    lumbar = sum(1 for label in range(L1, L6 + 1) if label in have)
    presacral = sum(1 for label in range(C1, L6 + 1) if label in have) + (C1 not in have and C2 in have)
    return {"thoracic": thoracic, "lumbar": lumbar, "presacral": presacral, "call": f"T{thoracic}L{lumbar}"}

# ---------------------------------------------------------------- one facts row: ribs


def rib_label(side, rib):
    return rib if side == "left" else RIGHT_RIB_BASE + rib


def rib_of(row, side, rib):
    return row["ribs"].get(str(rib_label(side, rib)))


def ribs_on(row, side):
    """The ribs of one side that count, at RIB_MIN_VOXELS or more, head to foot."""
    return [rib for rib in range(1, RIBS_PER_SIDE + 1)
            if (entry := rib_of(row, side, rib)) and entry["voxels"] >= RIB_MIN_VOXELS]


def own_vertebra(rib):
    return rib + OWN_VERTEBRA_OFFSET


def reading_of(rib, lead):
    """Where a rib leads against its own body: own, one_high (the label above), one_low, further, nothing."""
    if lead is None:
        return "nothing"
    return {0: "own", -1: "one_high", 1: "one_low"}.get(lead - own_vertebra(rib), "further")


def lowest_rib(row, side):
    """One side's lowest rib, the label it leads on and how that reads; None for a side with no rib."""
    have = ribs_on(row, side)
    if not have:
        return None
    rib = max(have)
    entry = rib_of(row, side, rib)
    return {"rib": rib, "lead": entry["lead"], "tie": bool(entry["tie"]), "reading": reading_of(rib, entry["lead"])}


ONE_OFF = "a label one level off"
FURTHER_OFF = "a label further off"
NOTHING = f"no spine label within {CONTACT_MM} mm"
NO_RIB = "no rib on either side"
# The facts carry no contacts where the two masks lie on different grids (bordercall's enhance_facts),
# and the count names that row so.
UNREADABLE = "masks unreadable"


def lowest_rib_row(row):
    """The row of the note's table a study falls in, by the sides whose lowest rib touches the spine, as
    count_enhance_pet's contact_class places it: one level off before further off before its own level."""
    if not row["ribs_mask"]["same_grid"]:
        return UNREADABLE
    sides = [found for found in (lowest_rib(row, side) for side in SIDES) if found]
    touching = [found for found in sides if found["lead"] is not None]
    readings = {found["reading"] for found in touching}
    if readings & {"one_high", "one_low"}:
        return ONE_OFF
    if "further" in readings:
        return FURTHER_OFF
    if not touching:
        return NOTHING if sides else NO_RIB
    named = [f"rib {rib} on {level_name(own_vertebra(rib))}" for rib in sorted({found["rib"] for found in touching})]
    return named[0] if len(named) == 1 else f"{named[0]} on one side, {named[1]} on the other"


def ladder(row):
    """How every rib with contacts leads against its own body, and the shift where most lead one way off."""
    counts = {"own": 0, "one_high": 0, "one_low": 0, "further": 0}
    for side in SIDES:
        for rib in ribs_on(row, side):
            lead = rib_of(row, side, rib)["lead"]
            if lead is not None:
                counts[reading_of(rib, lead)] += 1
    read = sum(counts.values())
    shift = next((way for way in ("one_high", "one_low") if read and counts[way] > SHIFT_SHARE * read), None)
    return {"read": read, **counts, "shift": shift}


LADDER_OFFSET = {None: 0, "one_high": -1, "one_low": 1}


def side_by_side(row):
    """The two sides as the note reads them: ribs on each, pairs, and what each lowest rib meets."""
    left, right = ribs_on(row, "left"), ribs_on(row, "right")
    meets = {side: lowest_rib(row, side) for side in SIDES}
    return {"rib_pairs_left": len(left), "rib_pairs_right": len(right), "rib_pairs": len(set(left) & set(right)),
            "lowest_rib_left": meets["left"]["rib"] if meets["left"] else None,
            "lowest_rib_right": meets["right"]["rib"] if meets["right"] else None,
            "lowest_rib_meets_left": lead_name(meets["left"]), "lowest_rib_meets_right": lead_name(meets["right"])}


def lead_name(found):
    return level_name(found["lead"]) if found and found["lead"] is not None else None


def call_by_ribs(row):
    """The ribs' column call: the thoracic count is the highest rib whose lead sits on the ladder (its
    own body, or one off the same way as most ribs on a shifted ladder), and the lumbar count the labelled
    bodies below that rib's body down to the sacrum. None where no rib touches the spine, and None where a
    rib lower than every rib on the ladder meets no label: that rib still bears a body, so counting from
    the last rib that touches would read a twelve-rib spine whose twelfth ribs end short as T11L6."""
    offset = LADDER_OFFSET[ladder(row)["shift"]]
    on_ladder = [rib for side in SIDES for rib in ribs_on(row, side)
                 if rib_of(row, side, rib)["lead"] == own_vertebra(rib) + offset]
    if not on_ladder:
        return None
    thoracic = max(on_ladder)
    if any(rib > thoracic and rib_of(row, side, rib)["lead"] is None for side in SIDES for rib in ribs_on(row, side)):
        return None
    lowest_body = own_vertebra(thoracic) + offset
    have = present(row)
    lumbar = sum(1 for label in range(lowest_body + 1, L6 + 1) if label in have)
    return {"thoracic": thoracic, "lumbar": lumbar, "presacral": call_by_names(row)["presacral"],
            "call": f"T{thoracic}L{lumbar}", "lowest_rib_bearing": level_name(lowest_body)}

# ---------------------------------------------------------------- one facts row: class and status


def own_lowest_ribs(row):
    """The lowest ribs, one or two numbers, of the sides whose lowest rib touches its own body."""
    sides = [lowest_rib(row, side) for side in SIDES]
    return sorted({found["rib"] for found in sides if found and found["reading"] == "own"})


def name_class(row):
    """The class the names give where the ribs say twelve, or say nothing."""
    pattern = label_pattern(row)
    by_pattern = {"C2 to L5 named": "normal", "L6 named below an L5": "l6_twelve_ribs",
                  "no L5, L4 meeting the sacrum": "four_lumbar_twelve_ribs"}
    return by_pattern.get(pattern, "look"), pattern


def class_by_rib_count(row, ribs, why):
    if ribs == 11:
        return "eleven_ribs", f"{why}: a ribless T12"
    if ribs == 13:
        bodies = "an L6 below: 25 bodies" if L6 in present(row) else "no L6: 24 bodies"
        return ("l6_thirteen_ribs" if L6 in present(row) else "thirteen_ribs"), f"{why}, {bodies}"
    if ribs == 12:
        klass, pattern = name_class(row)
        return klass, f"{why}; {pattern}"
    return "look", f"{why}: an unusual lowest rib"


def silent_rib_class(row):
    """The class where no lowest rib touches the spine: the rib counts stand in, else the names alone."""
    left, right = ribs_on(row, "left"), ribs_on(row, "right")
    if not left and not right:
        klass, pattern = name_class(row)
        return klass, f"{NO_RIB}: the names alone; {pattern}"
    if left and right and max(left) != max(right):
        return "look", "no lowest rib touches the spine and the two sides' lowest ribs differ"
    return class_by_rib_count(row, max(left or right), f"no lowest rib touches the spine; {max(left or right)} ribs a side")


def rib_class(row):
    """The class the ribs give a whole study, deferring to the names where they say twelve."""
    reading = lowest_rib_row(row)
    if reading in (ONE_OFF, FURTHER_OFF):
        return "look", f"the lowest rib meets {reading}: a labelling suspect"
    if ladder(row)["shift"]:
        return "look", "most ribs lead on a label one level off their own: a labelling suspect"
    if reading == UNREADABLE:
        klass, pattern = name_class(row)
        return klass, f"the rib and vertebra masks lie on different grids: the names alone; {pattern}"
    if reading in (NOTHING, NO_RIB):
        return silent_rib_class(row)
    ribs = own_lowest_ribs(row)
    if len(ribs) > 1:
        return "asymmetric_ribs", reading
    return class_by_rib_count(row, ribs[0], reading)


def classify(row, decided=None):
    """(class, reason): a repair first, then the whole rule, then what a person or the note decided,
    then the ribs and the names."""
    if decided and decided[0] == "repaired":
        return decided
    problems = whole_problems(row)
    if problems:
        return "not_whole", "; ".join(problems)
    return decided or rib_class(row)


# The checks a confirmation needs to pass: every structural one but C2 at the field's top, which says
# where the field ends and nothing of the labels.
STRUCTURAL = ("Q01", "Q02", "Q03", "Q04", "Q05", "Q07", "Q08", "Q09", "Q10", "Q11", "Q12", "Q13")


def ribs_agree(row):
    """Both sides' lowest ribs touch their own body, with no tie."""
    sides = [lowest_rib(row, side) for side in SIDES]
    return all(found and found["reading"] == "own" and not found["tie"] for found in sides)


def checks_pass(verdicts):
    """Every structural check that applies passes; one that did not run had nothing to read (no L5 for
    the fragment check, too few controls for the ratio), which is no doubt about the study."""
    return all(verdicts.get(check, "not_run") in ("pass", "not_run") for check in (*STRUCTURAL, "Q14"))


def status_of(klass, row, verdicts):
    """How far the masks alone carry the class: confirmed_by_masks only where the names and the rib
    ladder agree and every structural check that applies passes; never a reader's read of the CT."""
    if klass in ("labelling_error", "open"):
        return klass
    if klass == "not_whole":
        return "not_assessed"
    if klass in ("repaired", "look", "asymmetric_ribs"):
        return "candidate"
    return "confirmed_by_masks" if ribs_agree(row) and checks_pass(verdicts) else "candidate"


def route_truth(call):
    """A column call in tools/anomaly_route.py's vocabulary (call_of's order): L6, T13, four_lumbar,
    eleven, normal or other."""
    if call is None:
        return None
    thoracic, lumbar = call["thoracic"], call["lumbar"]
    if lumbar == 6:
        return "L6"
    if thoracic == 13:
        return "T13"
    if lumbar == 4:
        return "four_lumbar"
    if thoracic == 11:
        return "eleven"
    return "normal" if (thoracic, lumbar) == (12, 5) else "other"

# ---------------------------------------------------------------- the quality checks, Q01 to Q16


def verdict(kind, value, threshold):
    return {"verdict": kind, "value": value, "threshold": threshold}


def not_run(why):
    return verdict("not_run", why, None)


def determinant(m):
    return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))


def affine_problems(mask):
    affine, zooms, axis = mask["affine"], mask["zooms"], mask["head_foot_axis"]
    problems = []
    if [round(x, 6) for x in affine[3]] != [0, 0, 0, 1]:
        problems.append("the affine's last row is not 0 0 0 1")
    if abs(determinant([r[:3] for r in affine[:3]])) < AFFINE_TOLERANCE:
        problems.append("the affine is singular")
    lengths = [sum(affine[i][j] ** 2 for i in range(3)) ** 0.5 for j in range(3)]
    if any(abs(a - b) > AFFINE_TOLERANCE * max(1.0, b) for a, b in zip(lengths, zooms)):
        problems.append("the affine's columns do not match the voxel sizes")
    if axis != max(range(3), key=lambda j: abs(affine[2][j])):
        problems.append("the head-foot axis is not the one the affine moves most along world z")
    return problems


# The release stores most masks as uint8 and 17 as int16 (the count's extents step): any integer type
# holds the same labels, while a float one has to be rounded and may not.
INTEGER_DTYPE = re.compile(r"^u?int(8|16|32|64)$")


def check_header(row):
    """Q01: the mask is readable, of an integer type, its shape and affine sane, on the rib mask's grid."""
    mask = row["mask"]
    problems = [] if INTEGER_DTYPE.match(str(mask["dtype"])) else [f"dtype {mask['dtype']}"]
    if len(mask["shape"]) != 3 or min(mask["shape"]) < 1 or min(mask["zooms"]) <= 0:
        problems.append("the shape or the voxel sizes are not three positive numbers")
    problems += affine_problems(mask)
    if not row["ribs_mask"]["same_grid"]:
        problems.append("the rib mask lies on another grid")
    value = {"problems": problems, "dtype": mask["dtype"]}
    return verdict("fail" if problems else "pass", value, {"dtype": "an integer type", "affine_tolerance": AFFINE_TOLERANCE})


def check_alphabet(row):
    """Q02: vertebra ids 1 to 28 and rib ids 1 to 26 (the sternum counted apart), nothing outside the scheme."""
    outside = row["outside_scheme_voxels"]
    labels = sorted(int(k) for k in row["labels"] if not 1 <= int(k) <= TOP_VERTEBRA_LABEL)
    ribs = sorted(int(k) for k in row["ribs"] if not 1 <= int(k) <= TOP_RIB_LABEL)
    value = {"outside_vertebrae": outside["vertebrae"], "outside_ribs": outside["ribs"],
             "labels_outside": labels, "ribs_outside": ribs}
    bad = outside["vertebrae"] or outside["ribs"] or labels or ribs
    return verdict("fail" if bad else "pass", value, {"vertebrae": "0-28", "ribs": "0-27", "outside": 0})


def check_whole(row):
    """Q03: C2 and the sacrum at LEVEL_MIN_VOXELS or more and every level from C2 to T12; a lumbar label
    missing other than L5 is whole by the owner's rule and a look; an absent L5 is excepted."""
    have = present(row)
    core = [level_name(label) for label in (C2, *range(C2 + 1, T12 + 1), SACRUM) if label not in have]
    lumbar = [level_name(label) for label in range(L1, L5) if label not in have]
    value = {"missing": core + lumbar, "c2_voxels": voxels_of(row, C2), "sacrum_voxels": voxels_of(row, SACRUM)}
    kind = "fail" if core else "look" if lumbar else "pass"
    return verdict(kind, value, {"min_voxels": LEVEL_MIN_VOXELS, "excepted": "L5"})


def check_order(row):
    """Q04: neighbouring labels in head-foot order; a lower label whose top lies above the upper's is a look."""
    labels = column_labels(present(row))
    pairs = [[level_name(upper), level_name(lower)] for upper, lower in zip(labels, labels[1:])
             if label_of(row, upper)["top_mm"] < label_of(row, lower)["top_mm"]]
    return verdict("look" if pairs else "pass", pairs, "the lower label's top below the upper's")


def spans_missing(link, missing):
    upper, lower, _ = link
    return any(upper < label < lower for label in missing)


def check_gaps(row):
    """Q05: a space over UNLABELLED_GAP_MM above T12 fails (a body with no label); below T12, or over
    LOOK_GAP_MM anywhere, it is a look."""
    found, missing = links(row), missing_levels(row)
    wide = [link for link in found if link[2] > UNLABELLED_GAP_MM]
    look = [link for link in found if LOOK_GAP_MM < link[2] <= UNLABELLED_GAP_MM and not spans_missing(link, missing)]
    value = [[level_name(u), level_name(l), g] for u, l, g in wide + look]
    kind = "fail" if any(u < T12 for u, _, _ in wide) else "look" if wide or look else "pass"
    return verdict(kind, value, {"fail_mm": UNLABELLED_GAP_MM, "look_mm": LOOK_GAP_MM})


def field_top_mm(mask):
    """The head-most slice centre's head-foot coordinate and the slice step, as the extents step reads them."""
    affine, axis = mask["affine"], mask["head_foot_axis"]
    first = affine[2][3]
    last = first + affine[2][axis] * (mask["shape"][axis] - 1)
    return max(first, last), abs(affine[2][axis])


def check_c2_top(row):
    """Q06: C2 in the field's top slice, so its top may be cut off: a look."""
    if C2 not in present(row):
        return not_run("no C2")
    top, step = field_top_mm(row["mask"])
    below = round(top - label_of(row, C2)["top_mm"], 1)
    return verdict("look" if below < step / 2 else "pass", {"c2_below_field_top_mm": below}, {"within_mm": round(step / 2, 3)})


def check_l5_fragment(row):
    """Q07: an L5 label under FRAGMENT_SHARE of L4's voxels over an L4 that meets the sacrum."""
    if not {L4, L5, SACRUM} <= present(row):
        return not_run("L4, L5 or the sacrum is not labelled")
    share = round(voxels_of(row, L5) / voxels_of(row, L4), 4)
    meets = gap_mm(row, L4, SACRUM)
    kind = "look" if share < FRAGMENT_SHARE and meets <= NO_L5_MEETS_MM else "pass"
    return verdict(kind, {"l5_of_l4": share, "l4_to_sacrum_head_foot_mm": meets},
                   {"share": FRAGMENT_SHARE, "meets_mm": NO_L5_MEETS_MM})


def distance(row, first, second):
    low, high = sorted((first, second))
    return row["distances_mm"].get(f"{low}-{high}")


def lowest_lumbar(row):
    lumbar = [label for label in range(L1, L6 + 1) if label in present(row)]
    return max(lumbar) if lumbar else None


def check_lumbosacral_touch(row):
    """Q08: the lowest lumbar label touches the sacrum in 3-D, so no body without a label lies between;
    and across a labelled L5, L4 stays as far from the sacrum as in every control."""
    low = lowest_lumbar(row)
    if low is None or SACRUM not in present(row):
        return not_run("no lumbar label or no sacrum")
    reach = distance(row, low, SACRUM)
    if reach is None:
        return not_run(f"no {level_name(low)} to sacrum distance in the facts")
    across = distance(row, L4, SACRUM) if {L4, L5} <= present(row) else None
    value = {"lowest": level_name(low), "lowest_to_sacrum_mm": reach, "l4_to_sacrum_mm": across}
    kind = "look" if reach > TOUCH_MM or (across is not None and across < CONTROL_NEAREST_ACROSS_L5_MM) else "pass"
    return verdict(kind, value, {"touch_mm": TOUCH_MM, "l4_across_l5_at_least_mm": CONTROL_NEAREST_ACROSS_L5_MM})


def check_ladder(row):
    """Q09: every rib with contacts leads on its own label, k + 7; more than SHIFT_SHARE of them one level
    off the same way is a shifted ladder and fails, fewer off is a look."""
    found = ladder(row)
    if not found["read"]:
        return not_run("no rib touches the spine")
    kind = "fail" if found["shift"] else "look" if found["own"] != found["read"] else "pass"
    return verdict(kind, found, {"shift_share": SHIFT_SHARE})


def check_lowest_rib(row):
    """Q10: each side's lowest rib meets its own vertebra; off its own fails, no contact or a tie is a look."""
    sides = {side: lowest_rib(row, side) for side in SIDES}
    if not any(sides.values()):
        return not_run(NO_RIB)
    value = {side: found and {"rib": found["rib"], "meets": lead_name(found), "tie": found["tie"]}
             for side, found in sides.items()}
    readings = [found["reading"] for found in sides.values() if found]
    if set(readings) & {"one_high", "one_low", "further"}:
        return verdict("fail", value, "rib k on label k + 7")
    doubtful = None in sides.values() or "nothing" in readings or any(f["tie"] for f in sides.values() if f)
    return verdict("look" if doubtful else "pass", value, "rib k on label k + 7")


def check_split_piece(row):
    """Q11: a column label under SPLIT_SHARE of both neighbours' voxels is a piece split off a body."""
    labels = column_labels(present(row), COLUMN_FROM_C1)
    pieces = [{"label": level_name(mid), "voxels": voxels_of(row, mid), "above": voxels_of(row, up),
               "below": voxels_of(row, down)}
              for up, mid, down in zip(labels, labels[1:], labels[2:])
              if voxels_of(row, mid) < SPLIT_SHARE * min(voxels_of(row, up), voxels_of(row, down))]
    return verdict("look" if pieces else "pass", pieces, {"share": SPLIT_SHARE})


def check_fragments(row):
    """Q12: a column label whose largest connected piece holds under COMPONENT_SHARE of its voxels."""
    have = present(row)
    split = {level_name(label): label_of(row, label)["largest_share"] for label in COLUMN_FROM_C1
             if label in have and label_of(row, label)["largest_share"] < COMPONENT_SHARE}
    return verdict("look" if split else "pass", split, {"largest_share": COMPONENT_SHARE})


def check_c7_t1(row, bounds):
    """Q13: C7's voxels over T1's outside the controls' 1st to 99th percentile."""
    if bounds is None:
        return not_run(f"fewer than {MIN_CONTROLS_FOR_RATIO} controls carry C7 and T1")
    if not {C7, T1} <= present(row):
        return not_run("C7 or T1 is not labelled")
    ratio = round(voxels_of(row, C7) / voxels_of(row, T1), 4)
    kind = "pass" if bounds[0] <= ratio <= bounds[1] else "look"
    return verdict(kind, {"c7_of_t1": ratio}, {"percentiles": list(RATIO_PERCENTILES), "bounds": list(bounds)})


LUMBOSACRAL_KEYS = tuple(f"{label}-{SACRUM}" for label in range(L1, L6 + 1))


def implementation_differences(row, other):
    """Where two readings of one study differ on what Q08 to Q10 read: lumbosacral distances, rib leads."""
    out = []
    for key in LUMBOSACRAL_KEYS:
        mine, theirs = row["distances_mm"].get(key), other["distances_mm"].get(key)
        if (mine is None) != (theirs is None) or (mine is not None and abs(mine - theirs) > DISTANCE_AGREEMENT_MM):
            out.append(f"distance {key}: {mine} against {theirs}")
    for label in sorted(set(row["ribs"]) | set(other["ribs"]), key=int):
        mine, theirs = row["ribs"].get(label, {}), other["ribs"].get(label, {})
        fields = ("voxels", "lead", "tie")
        if any(mine.get(f) != theirs.get(f) for f in fields):
            out.append(f"rib {label}: {[mine.get(f) for f in fields]} against {[theirs.get(f) for f in fields]}")
    return out


def check_two_implementations(row, other):
    """Q14: an independent reading of the same masks (facts B) agrees on the inputs of Q08 to Q10."""
    if other is None:
        return not_run("no second reading of this study is committed")
    found = implementation_differences(row, other)
    return verdict("fail" if found else "pass", found, {"distance_mm": DISTANCE_AGREEMENT_MM, "rib_leads": "equal"})


def first_number(text):
    found = re.search(r"\d+(?:\.\d+)?", str(text)) if text is not None else None
    return float(found.group()) if found else None


def check_slice_spacing(row):
    """Q15: the NIfTI's slice spacing no wider than the slice thickness CT-details.xlsx gives."""
    thickness = first_number(row["scanner"].get("slice_thickness"))
    if thickness is None:
        return not_run("CT-details.xlsx gives no slice thickness")
    spacing = row["mask"]["zooms"][row["mask"]["head_foot_axis"]]
    kind = "look" if spacing > thickness + SLICE_TOLERANCE_MM else "pass"
    return verdict(kind, {"spacing_mm": spacing, "thickness_mm": thickness}, {"tolerance_mm": SLICE_TOLERANCE_MM})


def check_bucket_bytes(row, listed):
    """Q16: each mask's bytes are what the public bucket lists; a repaired vertebra mask is not listed."""
    if listed is None:
        return not_run("the study is not in the bucket's listing")
    pairs = [("ribs", row["ribs_mask"]["bytes"], listed[2])]
    if "repaired_from" not in row:
        pairs.insert(0, ("vertebrae", row["mask"]["bytes"], listed[1]))
    differences = [f"{kind}: {mine} against {theirs}" for kind, mine, theirs in pairs if mine != theirs]
    return verdict("fail" if differences else "pass", differences, "equal bytes")


CHECKS = (
    ("Q01", 1, "header", check_header),
    ("Q02", 1, "alphabet", check_alphabet),
    ("Q03", 1, "whole rule", check_whole),
    ("Q04", 1, "head-foot order", check_order),
    ("Q05", 1, "gaps", check_gaps),
    ("Q06", 1, "C2 in the field's top slice", check_c2_top),
    ("Q07", 1, "L5 fragment", check_l5_fragment),
    ("Q08", 1, "lowest lumbar label touches the sacrum", check_lumbosacral_touch),
    ("Q09", 1, "rib ladder", check_ladder),
    ("Q10", 1, "lowest rib meets its own vertebra", check_lowest_rib),
    ("Q11", 1, "split piece", check_split_piece),
    ("Q12", 1, "fragments", check_fragments),
    ("Q13", 1, "C7 against T1", check_c7_t1),
    ("Q14", 1, "two implementations agree", check_two_implementations),
    ("Q15", 1, "slice spacing against the table", check_slice_spacing),
    ("Q16", 1, "bucket bytes", check_bucket_bytes),
)
# The named constants each check reads, shown beside it on QA.md and the page.
CHECK_THRESHOLDS = {
    "Q01": ("AFFINE_TOLERANCE",), "Q02": (), "Q03": ("LEVEL_MIN_VOXELS",), "Q04": ("LEVEL_MIN_VOXELS",),
    "Q05": ("UNLABELLED_GAP_MM", "LOOK_GAP_MM"), "Q06": (), "Q07": ("FRAGMENT_SHARE", "NO_L5_MEETS_MM"),
    "Q08": ("TOUCH_MM", "CONTROL_NEAREST_ACROSS_L5_MM"), "Q09": ("RIB_MIN_VOXELS", "SHIFT_SHARE"),
    "Q10": ("RIB_MIN_VOXELS",), "Q11": ("SPLIT_SHARE",), "Q12": ("COMPONENT_SHARE",),
    "Q13": ("RATIO_PERCENTILES", "MIN_CONTROLS_FOR_RATIO"), "Q14": ("DISTANCE_AGREEMENT_MM",),
    "Q15": ("SLICE_TOLERANCE_MM",), "Q16": (),
}


def check_text(function):
    """What a check holds, from its docstring, on one line."""
    return " ".join(function.__doc__.split(": ", 1)[1].split())


def thresholds_text(check_id):
    """The constants a check reads with their values; Q06's half slice comes from each mask's header."""
    named = [f"{name} = {globals()[name]}" for name in CHECK_THRESHOLDS[check_id]]
    return "; ".join(named) or ("half the mask's slice step" if check_id == "Q06" else "none")


def study_of(row):
    return row.get("repaired_from", row["id"])


def run_qa(row, context):
    """Every check on one facts row, with its id, version, what it checks and why it says so."""
    extra = {"Q13": (context["bounds"],), "Q14": (context["facts_b"].get(row["id"]),),
             "Q16": (context["bucket"].get(study_of(row)),)}
    results = []
    for check_id, version, title, function in CHECKS:
        found = function(row, *extra.get(check_id, ()))
        found.update(check=check_id, version=version, title=title, why=check_text(function))
        results.append(found)
    return results


def ratio_bounds(rows, control_ids):
    """The controls' 1st and 99th percentile of C7's voxels over T1's, or None with too few controls."""
    wanted = set(control_ids)
    ratios = [voxels_of(r, C7) / voxels_of(r, T1) for r in rows if r["id"] in wanted and {C7, T1} <= present(r)]
    if len(ratios) < MIN_CONTROLS_FOR_RATIO:
        return None
    cuts = statistics.quantiles(ratios, n=100, method="inclusive")
    return (round(cuts[RATIO_PERCENTILES[0] - 1], 4), round(cuts[RATIO_PERCENTILES[1] - 1], 4))

# ---------------------------------------------------------------- the facts' schema


ROW_KEYS = {"id", "site", "mask", "ribs_mask", "scanner", "labels", "ribs", "sternum_voxels", "distances_mm",
            "outside_scheme_voxels"}
MASK_KEYS = {"bytes", "sha256", "shape", "zooms", "affine", "axcodes", "head_foot_axis", "dtype"}
SCANNER_KEYS = {"manufacturer", "model", "kvp", "kernel", "pixel_spacing", "slice_thickness"}
LABEL_KEYS = {"voxels", "top_mm", "bottom_mm", "centroid_mm", "components", "largest_share"}
RIB_KEYS = {"voxels", "components", "contacts", "lead", "lead_n", "tie"}
ROW_ID = re.compile(r"^\d{4}r?$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
DISTANCE_KEY = re.compile(r"^(\d+)-(\d+)$")


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def missing_keys(where, found, wanted):
    if not isinstance(found, dict):
        return [f"{where} is not an object"]
    return [f"{where} lacks {key}" for key in sorted(wanted - set(found))]


def mask_problems(mask):
    problems = missing_keys("mask", mask, MASK_KEYS)
    if problems:
        return problems
    if not (is_int(mask["bytes"]) and HEX64.match(str(mask["sha256"]))):
        problems.append("mask bytes or sha256 malformed")
    if not (len(mask["shape"]) == 3 and all(is_int(n) for n in mask["shape"])):
        problems.append("mask shape is not three integers")
    if not (len(mask["zooms"]) == 3 and all(is_number(z) for z in mask["zooms"])):
        problems.append("mask zooms are not three numbers")
    if not (len(mask["affine"]) == 4 and all(len(r) == 4 and all(is_number(x) for x in r) for r in mask["affine"])):
        problems.append("mask affine is not 4 by 4 numbers")
    if mask["head_foot_axis"] not in (0, 1, 2):
        problems.append("mask head_foot_axis is not 0, 1 or 2")
    return problems


def label_problems(labels):
    problems = []
    for key, entry in labels.items():
        problems += [f"label {key}: {p}" for p in missing_keys("entry", entry, LABEL_KEYS)]
        if not key.isdigit():
            problems.append(f"label {key} is not a number")
        elif isinstance(entry, dict) and LABEL_KEYS <= set(entry):
            ok = (is_int(entry["voxels"]) and entry["voxels"] >= 1 and is_number(entry["top_mm"])
                  and is_number(entry["bottom_mm"]) and entry["top_mm"] >= entry["bottom_mm"]
                  and len(entry["centroid_mm"]) == 3 and is_int(entry["components"])
                  and is_number(entry["largest_share"]) and 0 < entry["largest_share"] <= 1)
            problems += [] if ok else [f"label {key}: a value out of shape"]
    return problems


def rib_problems(ribs):
    problems = []
    for key, entry in ribs.items():
        problems += [f"rib {key}: {p}" for p in missing_keys("entry", entry, RIB_KEYS)]
        if isinstance(entry, dict) and RIB_KEYS <= set(entry):
            # contacts is null where the two masks lie on different grids, an empty object where the
            # rib meets nothing within CONTACT_MM.
            ok = (key.isdigit() and is_int(entry["voxels"]) and entry["voxels"] >= 1
                  and (entry["contacts"] is None or tally_in_shape(entry["contacts"]))
                  and (entry["lead"] is None or is_int(entry["lead"])) and isinstance(entry["tie"], bool)
                  and (entry["lead"] is None) == (not entry["contacts"]))
            problems += [] if ok else [f"rib {key}: a value out of shape"]
            if ok and (entry["lead"], entry["tie"], entry["lead_n"]) != lead_of_tally(entry["contacts"]):
                problems.append(f"rib {key}: lead, tie or lead_n is not what its contacts give")
    return problems


def tally_in_shape(contacts):
    return isinstance(contacts, dict) and all(str(k).isdigit() and is_int(n) for k, n in contacts.items())


def lead_of_tally(contacts):
    """(lead, tie, lead_n) as spec section 2 defines them from a contact tally: the label with the most
    contacts, a tie going to the head-most (lowest) label and marked; the classes and Q09 and Q10 read
    the lead alone, so a lead its own tally does not give would move a study unseen."""
    if not contacts:
        return None, False, 0
    best = max(contacts.values())
    leaders = sorted(int(label) for label, n in contacts.items() if n == best)
    return leaders[0], len(leaders) > 1, best


def distance_problems(distances):
    problems = []
    for key, value in distances.items():
        found = DISTANCE_KEY.match(key)
        if not found or int(found.group(1)) >= int(found.group(2)) or not is_number(value):
            problems.append(f"distance {key}: not <a>-<b> with a < b and a number")
    return problems


def row_problems(row):
    """What breaks spec section 2's schema in one facts row."""
    if not isinstance(row, dict):
        return ["a row is not an object"]
    problems = missing_keys("row", row, ROW_KEYS)
    problems += [f"row has an unknown key {key}" for key in sorted(set(row) - ROW_KEYS - {"repaired_from"})]
    if problems:
        return problems
    if not ROW_ID.match(str(row["id"])) or (row["id"].endswith("r") != ("repaired_from" in row)):
        problems.append("id is not 4 digits, or 4 digits and r with repaired_from")
    problems += mask_problems(row["mask"])
    problems += missing_keys("ribs_mask", row["ribs_mask"], {"bytes", "sha256", "same_grid"})
    problems += missing_keys("scanner", row["scanner"], SCANNER_KEYS)
    problems += missing_keys("outside_scheme_voxels", row["outside_scheme_voxels"], {"vertebrae", "ribs"})
    problems += label_problems(row["labels"]) + rib_problems(row["ribs"]) + distance_problems(row["distances_mm"])
    return problems


def facts_problems(rows, record, bucket):
    """Every schema problem in the facts, each with its row, and the coverage the spec asks: every
    study in the bucket's listing once, and the three repaired masks as extra rows."""
    problems = [f"{row.get('id', '?') if isinstance(row, dict) else '?'}: {p}" for row in rows for p in row_problems(row)]
    if problems:
        return problems
    ids = [row["id"] for row in rows]
    if ids != sorted(ids) or len(set(ids)) != len(ids):
        problems.append("the rows are not sorted by id, one each")
    published = {row["id"] for row in rows if "repaired_from" not in row}
    repaired = {row["repaired_from"] for row in rows if "repaired_from" in row}
    if bucket and published != set(bucket["studies"]):
        problems.append(f"the rows cover {len(published)} studies, the bucket lists {len(bucket['studies'])}")
    expected = {entry["id"] for entry in record["repaired"]}
    if repaired != expected:
        problems.append(f"repaired rows {sorted(repaired)}, the record names {sorted(expected)}")
    return problems


def facts_record_problems(facts, facts_record):
    """The facts and FACTS.json come together, and the record's row count is the rows'."""
    if facts is None and facts_record is None:
        return []
    if facts is None or facts_record is None:
        return [f"{FACTS} and {FACTS_RECORD} are committed together or not at all"]
    count = next((facts_record[key] for key in ("rows", "row_count", "count") if key in facts_record), None)
    if count != len(facts):
        return [f"{FACTS_RECORD} gives {count} rows, {FACTS} holds {len(facts)}"]
    return []

# ---------------------------------------------------------------- the dataset's rows, from the inputs


def record_decisions(record):
    """The study ids a person or the note decided, each with its class and why."""
    decided = {}
    for klass in RECORD_CLASSES:
        for entry in record.get(klass, []):
            decided[entry["id"]] = (klass, entry["why"])
    return decided


def member_of(inputs, name):
    return next(m for m in inputs["members"]["members"] if m["member"] == name)


def compact(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def enhance_context(inputs):
    facts = inputs["facts"] or []
    published = [row for row in facts if "repaired_from" not in row]
    bucket = inputs["bucket"] or {"studies": {}}
    return {"bounds": ratio_bounds(published, inputs["record"]["controls"]["ids"]),
            "facts_b": {row["id"]: row for row in inputs["facts_b"] or []},
            "bucket": bucket["studies"], "decided": record_decisions(inputs["record"]),
            "known": known_exceptions(inputs["record"])}


def known_exceptions(record):
    known = {(check, entry["id"]): entry["why"] for check, entries in record.get("known_exceptions", {}).items()
             for entry in entries}
    known.update({("Q04", entry["id"]): entry["why"] for entry in record.get("out_of_order_read_as_bend", [])})
    return known


def tier_of(klass, row):
    if klass == "repaired":
        return "gold4", "repaired: the readers' voxels under names a rule moved, or a machine's mask; gold 4 until a person checks it"
    if klass == "not_whole":
        return "silver3", "partial: " + "; ".join(whole_problems(row))
    return "gold3", "whole, C2 to the sacrum, the four readers' masks"


def qa_rows(item, row, results, known):
    study = study_of(row)
    return [{"item": item, "facts_row": row["id"], "check_id": r["check"], "check_version": r["version"],
             "verdict": r["verdict"], "value": compact(r["value"]), "threshold": compact(r["threshold"]),
             "why": r["why"], "known": known.get((r["check"], study)) if r["verdict"] in ("fail", "look") else None,
             "ran_where": "container", "run_id": None} for r in results]


def anomaly_row(item, member, row, klass, reason, verdicts, decided_by):
    """One study's calls, class and status, the two calls side by side and never merged."""
    names, ribs = call_by_names(row), call_by_ribs(row)
    sides, lad = side_by_side(row), ladder(row)
    status = status_of(klass, row, verdicts)
    why_ct = NEEDS_CT.get(klass) or (reason if klass == "open" else None)
    return {"item": item, "member": member, "facts_row": row["id"], "call_by_names": names["call"],
            "presacral_by_names": names["presacral"], "call_by_ribs": ribs and ribs["call"],
            "presacral_by_ribs": ribs and ribs["presacral"], "rib_ladder": lad["shift"] or ("own" if lad["read"] else None),
            **sides, "lowest_rib_row": lowest_rib_row(row), "label_pattern": label_pattern(row),
            "l4_to_sacrum_mm": distance(row, L4, SACRUM), "lowest_lumbar_to_sacrum_mm": lowest_lumbar_distance(row),
            "class": klass, "class_reason": reason, "status": status, "needs_ct": int(why_ct is not None),
            "needs_ct_why": why_ct, "route_truth": route_truth(ribs or names),
            "evidence": "release names and ribs" if ribs else "release names alone", "reader_source": None,
            "castellvi": None, "decided_by": decided_by, "note": CASTELLVI_NOTE}


def lowest_lumbar_distance(row):
    low = lowest_lumbar(row)
    return distance(row, low, SACRUM) if low else None


def enhance_item(row, inputs, context, member):
    """The item, its masks, labels, ribs, anomaly and checks for one ENHANCE.PET study."""
    sid, item = row["id"], f"enhance_pet:{row['id']}"
    repaired = context["repaired_rows"].get(sid)
    read = repaired or row
    decision = context["decided"].get(sid)
    klass, reason = classify(read, decision)
    results = {r["id"]: run_qa(r, context) for r in filter(None, (row, repaired))}
    verdicts = {r["check"]: r["verdict"] for r in results[read["id"]]}
    tier, tier_reason = tier_of(klass, row)
    source = next((e["source"] for k in RECORD_CLASSES for e in inputs["record"].get(k, []) if e["id"] == sid), None)
    return {
        "item": enhance_item_row(row, item, member, tier, tier_reason, context),
        "masks": enhance_masks(row, repaired, item, member, context),
        "labels": [r for f in filter(None, (row, repaired)) for r in label_rows(item, f)],
        "ribs": [r for f in filter(None, (row, repaired)) for r in rib_rows(item, f)],
        "anomaly": anomaly_row(item, "enhance_pet", read, klass, reason, verdicts, source),
        "qa": [r for f_id, found in results.items() for r in qa_rows(item, row if f_id == sid else repaired, found, context["known"])],
    }


def enhance_item_row(row, item, member, tier, tier_reason, context):
    mask, scanner, sid = row["mask"], row["scanner"], row["id"]
    listed = context["bucket"].get(sid)
    c2_top = check_c2_top(row)["verdict"] == "look"
    return {"item": item, "sha256": mask["sha256"], "shard": context["shard"], "source": member["source"],
            "member": "enhance_pet", "person": item, "native_id": sid, "site": row["site"],
            "licence": member["licence"].get(row["site"]), "ct_sha256": None,
            "ct_url": member["public"]["ct"].format(id=sid), "ct_location": None,
            "ct_bytes": listed[0] if listed else None, "shape": compact(mask["shape"]), "spacing_mm": compact(mask["zooms"]),
            "affine_sha256": hashlib.sha256(compact(mask["affine"]).encode()).hexdigest(),
            "slice_mm": mask["zooms"][mask["head_foot_axis"]], "axcodes": mask["axcodes"],
            **{key: none_or_text(scanner.get(key)) for key in sorted(SCANNER_KEYS)},
            "tier": tier, "tier_reason": tier_reason, "provisional": 0, "has_c2": int(C2 in present(row)),
            "c2_in_top_slice": int(c2_top), "has_sacrum": int(SACRUM in present(row)), "sacrum_basis": "mask",
            "n_presacral": call_by_names(row)["presacral"], "count_class": count_class(row), "duplicate_of": None}


def none_or_text(value):
    return None if value is None else str(value)


def enhance_masks(row, repaired, item, member, context):
    sid = row["id"]
    listed = context["bucket"].get(sid)
    author = member["mask_author"]
    masks = [mask_row(item, row, "vertebrae", author, member["public"]["vertebrae"].format(id=sid), listed and listed[1]),
             ribs_mask_row(item, row, author, member["public"]["ribs"].format(id=sid), listed and listed[2])]
    if repaired:
        how = next(e for e in context["record_repaired"] if e["id"] == sid)
        author = "the readers' voxels, names moved by a rule the ribs settle" if how["voxels"] == "readers" else "MOOSE's rerun, a machine's mask checked by rule"
        masks.append(mask_row(item, repaired, "vertebrae_repaired", author, None, None, member["repair_record"]))
    return masks


def mask_row(item, row, kind, author, url, listed, location=None):
    mask = row["mask"]
    return {"mask": f"{item}/{kind}", "item": item, "facts_row": row["id"], "kind": kind,
            "scheme": "enhance_pet_vertebrae", "author": author, "url": url, "location": location,
            "sha256": mask["sha256"], "bytes": mask["bytes"], "bucket_bytes": listed, "dtype": mask["dtype"],
            "shape": compact(mask["shape"]), "zooms": compact(mask["zooms"]), "same_grid": int(row["ribs_mask"]["same_grid"]),
            "matched_by": None, "match_ok": None}


def ribs_mask_row(item, row, author, url, listed):
    ribs = row["ribs_mask"]
    return {"mask": f"{item}/ribs", "item": item, "facts_row": row["id"], "kind": "ribs", "scheme": "enhance_pet_ribs",
            "author": author, "url": url, "location": None, "sha256": ribs["sha256"], "bytes": ribs["bytes"],
            "bucket_bytes": listed, "dtype": None, "shape": None, "zooms": None, "same_grid": int(ribs["same_grid"]),
            "matched_by": None, "match_ok": None}


def label_rows(item, row):
    have, out = present(row), []
    order = {label: i for i, label in enumerate(column_labels(have))}
    gaps = {upper: gap for upper, _, gap in links(row)}
    disordered = {level for pair in check_order(row)["value"] for level in pair}
    for key in sorted(row["labels"], key=int):
        label, entry = int(key), row["labels"][key]
        x, y, z = entry["centroid_mm"]
        out.append({"item": item, "shard": "enhance_pet", "facts_row": row["id"], "source_label": label,
                    "level": level_name(label), "canonical_id": ENHANCE_TO_CANONICAL.get(label),
                    "voxels": entry["voxels"], "top_mm": entry["top_mm"], "bottom_mm": entry["bottom_mm"],
                    "centroid_x_mm": x, "centroid_y_mm": y, "centroid_z_mm": z, "components": entry["components"],
                    "largest_share": entry["largest_share"], "present": int(label in have),
                    "gap_to_next_mm": gaps.get(label) if label in order else None,
                    "out_of_order": int(level_name(label) in disordered)})
    return out


def rib_rows(item, row):
    out = []
    for side in SIDES:
        for rib in range(1, RIBS_PER_SIDE + 1):
            entry = rib_of(row, side, rib)
            if entry:
                out.append({"item": item, "facts_row": row["id"], "side": side, "rib_k": rib,
                            "source_label": rib_label(side, rib), "voxels": entry["voxels"],
                            "present": int(entry["voxels"] >= RIB_MIN_VOXELS), "components": entry["components"],
                            "lead_label": entry["lead"], "lead_level": level_name(entry["lead"]) if entry["lead"] else None,
                            "lead_n": entry["lead_n"], "tie": int(entry["tie"]), "reading": reading_of(rib, entry["lead"]),
                            "contacts": compact(entry["contacts"])})
    return out


def verse_items(inputs, member):
    """VerSe's 17 series as items and anomalies, from the records' reads; no masks are read here."""
    roles, scans = anomaly_roles(inputs["holdout"])
    items, anomalies = [], []
    for series in inputs["verse"]["series"]:
        person = scans.get(series["id"], f"verse:{series['id']}")
        item = f"verse:{series['id']}"
        items.append(verse_item_row(series, item, person, member))
        anomalies.append(verse_anomaly_row(series, item))
    return items, anomalies, {item["person"]: roles.get(item["person"], "none") for item in items}


def verse_item_row(series, item, person, member):
    return {"item": item, "sha256": None, "shard": "verse", "source": member["source"], "member": "verse",
            "person": person, "native_id": series["id"], "site": None, "licence": member["licence"]["as_one"],
            "ct_sha256": None, "ct_url": None, "ct_location": member["grid"]["pattern"].replace("{id}", series["id"]),
            "ct_bytes": None, "shape": None, "spacing_mm": None, "affine_sha256": None, "slice_mm": None,
            "axcodes": None, **{key: None for key in sorted(SCANNER_KEYS)}, "tier": "gold3",
            "tier_reason": "whole by the release mask's levels and the junction in the field; provisional until the"
                           " sacrum is confirmed on the grid", "provisional": 1, "has_c2": 1, "c2_in_top_slice": None,
            "has_sacrum": None, "sacrum_basis": "look on the grid", "n_presacral": None, "count_class": None,
            "duplicate_of": None}


VERSE_CLASS = {"T13": "t13", "L6": "l6", "four_lumbar": "four_lumbar", "normal": "normal", "unread": "unread"}


def verse_status(read):
    """A read the records cite (the readers' table, carried as evidence "read") leaves the class a
    candidate: reader_confirmed is given only by a verdict recorded on the reader bench, and there is
    none yet, as spec section 3 and docs/research/gold3-ct/README.md say."""
    return "candidate" if read else "not_assessed"


def verse_anomaly_row(series, item):
    variant = series["variant"]
    read = variant != "unread"
    says = "; ".join(claim["says"] for claim in series["claims"])
    return {"item": item, "member": "verse", "facts_row": None, "call_by_names": None, "presacral_by_names": None,
            "call_by_ribs": None, "presacral_by_ribs": None, "rib_ladder": None, "rib_pairs": None,
            "rib_pairs_left": None, "rib_pairs_right": None, "lowest_rib_left": None, "lowest_rib_right": None,
            "lowest_rib_meets_left": None, "lowest_rib_meets_right": None, "lowest_rib_row": None,
            "label_pattern": None, "l4_to_sacrum_mm": None, "lowest_lumbar_to_sacrum_mm": None,
            "class": VERSE_CLASS[variant], "class_reason": says,
            "status": verse_status(read), "needs_ct": int(not read),
            "needs_ct_why": None if read else "no read recorded: a count from C2 on the CT, or the readers' table row",
            "route_truth": variant if read else None, "evidence": "read" if read else "none",
            "reader_source": "Loeffler 2021, Supplementary Table 1, as the cited records carry it" if read else None,
            "castellvi": "IIIb" if "Castellvi IIIb" in says else None,
            "decided_by": "; ".join(claim["source"] for claim in series["claims"]),
            "note": "the sacrum is unlabelled in VerSe and waits for a look on the grid"}


def person_rows(items, roles, inputs):
    """One row per person key, its part by tools/catalog.py's rule and its role in the anomaly route."""
    rule, test = inputs["rule"], inputs["test_persons"]
    counts = {}
    for item in items:
        counts.setdefault(item["person"], [item, 0])[1] += 1
    out = []
    for person, (item, count) in sorted(counts.items()):
        role = roles.get(person, "none")
        out.append({"person": person, "source": item["source"], "member": item["member"],
                    "native_id": person.split(":", 1)[1], "identity": "study" if item["member"] == "enhance_pet" else "person",
                    "part": part_of(person, rule, test), "hash_hex": f"{person_hash(rule['salt'], person):016x}",
                    "part_reason": "a frozen test person" if person in test else "data/splits/rule.json's hash",
                    "anomaly_role": role, "training_allowed": int(role == "none"), "item_count": count})
    return out


def assemble(inputs):
    """Every table's rows from the committed inputs, in a fixed order, so one input gives one store."""
    tables = {name: [] for name in TABLE_ORDER}
    enhance, verse, ts = (member_of(inputs, name) for name in ("enhance_pet", "verse", "totalsegmentator"))
    add_enhance(tables, inputs, enhance)
    verse_rows, verse_anomalies, roles = verse_items(inputs, verse)
    tables["item"] += verse_rows
    tables["anomaly"] += verse_anomalies
    for item in tables["item"]:
        item["part"] = part_of(item["person"], inputs["rule"], inputs["test_persons"])
    tables["person"] = person_rows(tables["item"], roles, inputs)
    tables["person_alias"] = alias_rows(tables["person"])
    tables["source"] = [source_row(m, inputs) for m in (enhance, verse, ts)]
    tables["shard"] = shard_rows(inputs, tables["item"])
    tables["member_count"] = member_count_rows(inputs, tables["item"])
    tables["build"] = [build_row(inputs)]
    for name in ("item", "anomaly"):
        tables[name].sort(key=lambda r: r["item"])
    return tables


def add_enhance(tables, inputs, member):
    facts = inputs["facts"] or []
    context = enhance_context(inputs)
    context["repaired_rows"] = {row["repaired_from"]: row for row in facts if "repaired_from" in row}
    context["record_repaired"] = inputs["record"]["repaired"]
    context["shard"] = "enhance_pet"
    for row in facts:
        if "repaired_from" in row:
            continue
        found = enhance_item(row, inputs, context, member)
        tables["item"].append(found["item"])
        tables["mask"] += found["masks"]
        tables["label"] += found["labels"]
        tables["rib"] += found["ribs"]
        tables["anomaly"].append(found["anomaly"])
        tables["qa_check"] += found["qa"]


def alias_rows(persons):
    spellings = {"enhance_pet": ("scidb_enhance_pet_1_6k",), "verse": ("verse19_20", "versefusion")}
    return [{"alias": f"{spelling}:{p['native_id']}", "person": p["person"], "kind": "record id spelling"}
            for p in persons for spelling in spellings.get(p["member"], ())]


def source_row(member, inputs):
    entry = inputs["licences"]["sources"].get(member["source"], {})
    scheme = member["scheme"]
    return {"source": member["source"], "member": member["member"], "name": member["name"],
            "identity_level": "study" if member["member"] == "enhance_pet" else "person", "modality": "ct",
            "device_class": "ct", "grid_root": member["grid"]["root"],
            "access": "public bucket" if member["member"] == "enhance_pet" else "held on the grid",
            "licence": entry.get("licence", ""), "licence_class": entry.get("class"), "scheme": compact(scheme),
            "expresses_l6": int(scheme["expresses_l6"]), "expresses_t13": int(scheme["expresses_t13"]),
            "expresses_ribs": int(scheme["expresses_ribs"]), "mask_author": member["mask_author"],
            "studies_listed": member["studies_listed"], "gold3_by_records": member["gold3"]}


def shard_rows(inputs, items):
    """One shard per member, named by the member and the sha256 of the file its rows come from."""
    files = {"enhance_pet": FACTS, "verse": VERSE, "totalsegmentator": TOTALSEG}
    out = []
    for member in inputs["members"]["members"]:
        name, rel = member["member"], files[member["member"]]
        out.append({"name": name, "source": member["source"], "kind": "member", "manifest": rel,
                    "manifest_sha256": inputs["hashes"].get(rel), "item_count": sum(1 for i in items if i["member"] == name),
                    "made_by": member.get("rows_made_by", "the committed records")})
    return out


def site_counts(items, member, site):
    chosen = [i for i in items if i["member"] == member and (site == "all" or i["site"] == site)]
    tiers = [i["tier"] for i in chosen]
    return chosen, {"studies": len(chosen), "gold3": tiers.count("gold3"), "gold4": tiers.count("gold4"),
                    "silver3": tiers.count("silver3")}


def autopet_persons(whole, studies):
    """The fewest and most persons a number of autoPET studies can be: each repeat is one study."""
    repeats = max(studies - AUTOPET_PERSONS, 0)
    return max(whole - repeats, 0), min(whole, AUTOPET_PERSONS)


def member_count_rows(inputs, items):
    """Studies, tiers and persons as a range per member and per ENHANCE.PET site."""
    out = []
    for member in inputs["members"]["members"]:
        name = member["member"]
        sites = sorted({i["site"] for i in items if i["member"] == name and i["site"]})
        for site in ["all", *sites]:
            out.append(count_row(inputs, items, member, site))
    return out


def count_row(inputs, items, member, site):
    name = member["member"]
    chosen, counts = site_counts(items, name, site)
    low, high, basis = persons_of(items, member, site, counts)
    return {"member": name, "site": site, **counts, "gold3_by_records": member["gold3"] if site == "all" else None,
            "persons_low": low, "persons_high": high, "persons_basis": basis}


def persons_of(items, member, site, counts):
    name = member["member"]
    if not counts["studies"]:
        low, high = member["persons_by_records"]
        return low, high, "by the records; no rows yet"
    if name != "enhance_pet":
        keys = {i["person"] for i in items if i["member"] == name and i["tier"] == "gold3"}
        return len(keys), len(keys), "one person a key"
    _, autopet = site_counts(items, name, AUTOPET_SITE)
    low, high = autopet_persons(autopet["gold3"], autopet["studies"])
    if site == AUTOPET_SITE:
        return low, high, f"autoPET's studies are {AUTOPET_PERSONS} persons, so each repeat is one study"
    if site != "all":
        return None, counts["gold3"], "no person id: at most one person a whole study"
    others = counts["gold3"] - autopet["gold3"]
    return low, high + others, "autoPET's range, and at most one person a whole study at the sites with no person id"


def build_row(inputs):
    return {"schema_version": SCHEMA_VERSION, "code_commit": inputs.get("code_commit"), "code_digest": inputs.get("code_digest", ""),
            "whole_rule_version": inputs["members"]["whole_rule"]["version"], "salt": inputs["rule"]["salt"],
            "validation_share": inputs["rule"]["validation_share"], "inputs": compact(inputs["hashes"])}

# ---------------------------------------------------------------- the SQLite file


SCHEMA = """
CREATE TABLE build (
    schema_version INTEGER NOT NULL, code_commit TEXT, code_digest TEXT NOT NULL,
    whole_rule_version INTEGER NOT NULL, salt TEXT NOT NULL, validation_share REAL NOT NULL, inputs TEXT NOT NULL
);
CREATE TABLE source (
    source TEXT PRIMARY KEY, member TEXT NOT NULL UNIQUE, name TEXT NOT NULL, identity_level TEXT NOT NULL,
    modality TEXT NOT NULL, device_class TEXT NOT NULL, grid_root TEXT NOT NULL, access TEXT NOT NULL,
    licence TEXT NOT NULL, licence_class TEXT, scheme TEXT NOT NULL, expresses_l6 INTEGER NOT NULL,
    expresses_t13 INTEGER NOT NULL, expresses_ribs INTEGER NOT NULL, mask_author TEXT NOT NULL,
    studies_listed INTEGER NOT NULL, gold3_by_records INTEGER NOT NULL
);
CREATE TABLE shard (
    name TEXT PRIMARY KEY, source TEXT NOT NULL REFERENCES source(source), kind TEXT NOT NULL,
    manifest TEXT NOT NULL, manifest_sha256 TEXT, item_count INTEGER NOT NULL, made_by TEXT NOT NULL
);
CREATE TABLE person (
    person TEXT PRIMARY KEY, source TEXT NOT NULL REFERENCES source(source), member TEXT NOT NULL,
    native_id TEXT NOT NULL, identity TEXT NOT NULL, part TEXT NOT NULL, hash_hex TEXT NOT NULL,
    part_reason TEXT NOT NULL, anomaly_role TEXT NOT NULL, training_allowed INTEGER NOT NULL,
    item_count INTEGER NOT NULL
);
CREATE TABLE person_alias (
    alias TEXT NOT NULL, person TEXT NOT NULL REFERENCES person(person), kind TEXT NOT NULL,
    PRIMARY KEY (alias, person)
);
CREATE TABLE member_count (
    member TEXT NOT NULL, site TEXT NOT NULL, studies INTEGER NOT NULL, gold3 INTEGER NOT NULL,
    gold4 INTEGER NOT NULL, silver3 INTEGER NOT NULL, gold3_by_records INTEGER, persons_low INTEGER,
    persons_high INTEGER, persons_basis TEXT NOT NULL, PRIMARY KEY (member, site)
);
CREATE TABLE item (
    item TEXT PRIMARY KEY, sha256 TEXT, shard TEXT NOT NULL REFERENCES shard(name), source TEXT NOT NULL,
    member TEXT NOT NULL, person TEXT NOT NULL REFERENCES person(person), native_id TEXT NOT NULL, site TEXT,
    part TEXT NOT NULL, licence TEXT, ct_sha256 TEXT, ct_url TEXT, ct_location TEXT, ct_bytes INTEGER,
    shape TEXT, spacing_mm TEXT, affine_sha256 TEXT, slice_mm REAL, axcodes TEXT, kernel TEXT, kvp TEXT,
    manufacturer TEXT, model TEXT, pixel_spacing TEXT, slice_thickness TEXT, tier TEXT NOT NULL,
    tier_reason TEXT NOT NULL, provisional INTEGER NOT NULL, has_c2 INTEGER, c2_in_top_slice INTEGER,
    has_sacrum INTEGER, sacrum_basis TEXT, n_presacral INTEGER, count_class TEXT, duplicate_of TEXT
);
CREATE TABLE mask (
    mask TEXT PRIMARY KEY, item TEXT NOT NULL REFERENCES item(item), facts_row TEXT, kind TEXT NOT NULL,
    scheme TEXT NOT NULL, author TEXT NOT NULL, url TEXT, location TEXT, sha256 TEXT, bytes INTEGER,
    bucket_bytes INTEGER, dtype TEXT, shape TEXT, zooms TEXT, same_grid INTEGER, matched_by TEXT, match_ok INTEGER
);
CREATE TABLE label (
    item TEXT NOT NULL, shard TEXT NOT NULL, facts_row TEXT NOT NULL, source_label INTEGER NOT NULL,
    level TEXT NOT NULL, canonical_id INTEGER, voxels INTEGER NOT NULL, top_mm REAL, bottom_mm REAL,
    centroid_x_mm REAL, centroid_y_mm REAL, centroid_z_mm REAL, components INTEGER, largest_share REAL,
    present INTEGER NOT NULL, gap_to_next_mm REAL, out_of_order INTEGER NOT NULL,
    PRIMARY KEY (facts_row, source_label)
);
CREATE TABLE rib (
    item TEXT NOT NULL, facts_row TEXT NOT NULL, side TEXT NOT NULL, rib_k INTEGER NOT NULL,
    source_label INTEGER NOT NULL, voxels INTEGER NOT NULL, present INTEGER NOT NULL, components INTEGER,
    lead_label INTEGER, lead_level TEXT, lead_n INTEGER, tie INTEGER NOT NULL, reading TEXT NOT NULL,
    contacts TEXT NOT NULL, PRIMARY KEY (facts_row, source_label)
);
CREATE TABLE anomaly (
    item TEXT PRIMARY KEY REFERENCES item(item), member TEXT NOT NULL, facts_row TEXT, call_by_names TEXT,
    presacral_by_names INTEGER, call_by_ribs TEXT, presacral_by_ribs INTEGER, rib_ladder TEXT, rib_pairs INTEGER,
    rib_pairs_left INTEGER, rib_pairs_right INTEGER, lowest_rib_left INTEGER, lowest_rib_meets_left TEXT,
    lowest_rib_right INTEGER, lowest_rib_meets_right TEXT, lowest_rib_row TEXT, label_pattern TEXT,
    l4_to_sacrum_mm REAL, lowest_lumbar_to_sacrum_mm REAL, class TEXT NOT NULL, class_reason TEXT NOT NULL,
    status TEXT NOT NULL, needs_ct INTEGER NOT NULL, needs_ct_why TEXT, route_truth TEXT, evidence TEXT NOT NULL,
    reader_source TEXT, castellvi TEXT, decided_by TEXT, note TEXT
);
CREATE TABLE qa_check (
    item TEXT NOT NULL, facts_row TEXT NOT NULL, check_id TEXT NOT NULL, check_version INTEGER NOT NULL,
    verdict TEXT NOT NULL, value TEXT, threshold TEXT, why TEXT NOT NULL, known TEXT, ran_where TEXT NOT NULL,
    run_id TEXT, PRIMARY KEY (facts_row, check_id)
);
CREATE TABLE qa_review (
    item TEXT NOT NULL, reviewer_role TEXT, reader_n INTEGER, verdict TEXT, column_call_read TEXT, utc TEXT, source TEXT
);
CREATE TABLE embedding (
    item TEXT NOT NULL, model TEXT NOT NULL, dim INTEGER NOT NULL, vector BLOB NOT NULL, PRIMARY KEY (item, model)
);
CREATE INDEX item_member ON item(member, site);
CREATE INDEX item_person ON item(person);
CREATE INDEX item_tier ON item(tier);
CREATE INDEX anomaly_class ON anomaly(class, status);
CREATE INDEX label_item ON label(item);
CREATE INDEX rib_item ON rib(item);
CREATE INDEX qa_verdict ON qa_check(check_id, verdict);
CREATE TRIGGER item_dropped AFTER DELETE ON item BEGIN
    DELETE FROM mask WHERE item = OLD.item;
    DELETE FROM label WHERE item = OLD.item;
    DELETE FROM rib WHERE item = OLD.item;
    DELETE FROM anomaly WHERE item = OLD.item;
    DELETE FROM qa_check WHERE item = OLD.item;
    DELETE FROM qa_review WHERE item = OLD.item;
    DELETE FROM embedding WHERE item = OLD.item;
END;
CREATE TRIGGER person_dropped AFTER DELETE ON person BEGIN
    DELETE FROM person_alias WHERE person = OLD.person;
END;
CREATE TRIGGER source_dropped AFTER DELETE ON source BEGIN
    DELETE FROM member_count WHERE member = OLD.member;
END;
CREATE VIEW gold3_persons_by_member AS
    SELECT item.member, COUNT(*) AS studies, COUNT(DISTINCT item.person) AS person_keys,
           SUM(item.provisional) AS provisional, member_count.persons_low, member_count.persons_high
    FROM item JOIN member_count ON member_count.member = item.member AND member_count.site = 'all'
    WHERE item.tier = 'gold3' GROUP BY item.member;
CREATE VIEW anomalies_by_class_and_status AS
    SELECT anomaly.member, item.site, anomaly.class, anomaly.status, COUNT(*) AS studies,
           SUM(anomaly.needs_ct) AS needs_ct
    FROM anomaly JOIN item ON item.item = anomaly.item GROUP BY anomaly.member, item.site, anomaly.class, anomaly.status;
CREATE VIEW qa_failures AS
    SELECT item, facts_row, check_id, verdict, value, threshold, why, known FROM qa_check
    WHERE verdict IN ('fail', 'look');
CREATE VIEW workflow_manifest AS
    SELECT item.item, item.person, item.member, item.source, item.site, item.tier, item.provisional, item.part,
           person.anomaly_role, person.training_allowed, anomaly.class, anomaly.status, anomaly.needs_ct,
           item.ct_url, item.ct_location
    FROM item JOIN person ON person.person = item.person LEFT JOIN anomaly ON anomaly.item = item.item;
"""

TABLE_ORDER = ("build", "source", "shard", "person", "person_alias", "member_count", "item", "mask", "label",
               "rib", "anomaly", "qa_check", "qa_review", "embedding")


def table_columns(db, table):
    return [row[1] for row in db.execute(f'PRAGMA table_info("{table}")')]


def fill(db, tables):
    db.executescript(SCHEMA)
    for table in TABLE_ORDER:
        columns = table_columns(db, table)
        marks = ", ".join("?" for _ in columns)
        db.executemany(f'INSERT INTO "{table}" VALUES ({marks})', ([row.get(c) for c in columns] for row in tables[table]))
    db.commit()


def stamp(db):
    """Mark the file as this dataset's and pack it: the same rows give the same bytes."""
    db.execute(f"PRAGMA application_id = {APPLICATION_ID}")
    db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    db.commit()
    db.execute("VACUUM")


def memory_db(inputs):
    """The dataset built into memory: what a build of the same inputs holds, for the pages and the check."""
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    fill(db, assemble(inputs))
    return db

# ---------------------------------------------------------------- the store


def store_paths(store):
    store = Path(store)
    return store / VERSIONS_DIR, store / VERSIONS_LOG, store / CURRENT


def read_versions(store):
    """The version log, oldest first; line N is version N and its parent is line N-1's hash."""
    _, log, _ = store_paths(store)
    if not log.is_file():
        return []
    records = []
    for number, line in enumerate(log.read_text(encoding="utf-8").splitlines(), start=1):
        record = json.loads(line)
        parent = records[-1]["sha256"] if records else None
        if record.get("version") != number or record.get("parent") != parent:
            raise Gold3Error(f"{log}: line {number} breaks the chain (version {record.get('version')}, parent {record.get('parent')})")
        records.append(record)
    return records


@contextlib.contextmanager
def store_lock(store):
    """One writer at a time: an exclusive POSIX record lock on <store>/LOCK for the whole write."""
    with (Path(store) / LOCK).open("a") as handle:
        fcntl.lockf(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.lockf(handle, fcntl.LOCK_UN)


def file_uri(path, flags):
    return f"file:{quote(str(path))}?{flags}"


def content_rows(db, table):
    """A table's rows, the build table's without what names the code that ran it."""
    columns = [c for c in table_columns(db, table) if not (table == "build" and c in ("code_commit", "code_digest"))]
    listed = ", ".join(f'"{c}"' for c in columns)
    return db.execute(f'SELECT {listed} FROM "{table}" ORDER BY rowid')


def same_content(one, other):
    """Whether two version files hold the same schema and rows, the code that built them apart."""
    first = sqlite3.connect(file_uri(one, "mode=ro"), uri=True)
    second = sqlite3.connect(file_uri(other, "mode=ro"), uri=True)
    try:
        schema = "SELECT type, name, sql FROM sqlite_master ORDER BY type, name"
        if first.execute(schema).fetchall() != second.execute(schema).fetchall():
            return False
        tables = [r[0] for r in first.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
        pairs = (itertools.zip_longest(content_rows(first, t), content_rows(second, t)) for t in tables)
        return all(a == b for pair in pairs for a, b in pair)
    finally:
        first.close()
        second.close()


def version_name(number, digest):
    return f"gold3-{number:06d}-{digest[:12]}.sqlite"


def write_db(path, tables):
    db = sqlite3.connect(path)
    try:
        fill(db, tables)
        stamp(db)
    finally:
        db.close()


def seal(fresh, final):
    if final.exists():
        raise Gold3Error(f"{final}: a file of that name is already there")
    os.chmod(fresh, 0o444)
    os.replace(fresh, final)


def write_current(current, name):
    point = current.with_name(current.name + ".new")
    point.write_text(name + "\n", encoding="utf-8")
    os.replace(point, current)


def unchanged(fresh, folder, latest):
    if latest is None:
        return False
    old = folder / latest["file"]
    return old.is_file() and sha256_of(old) == latest["sha256"] and (sha256_of(fresh) == latest["sha256"] or same_content(fresh, old))


def build(store, tables, code_commit=None):
    """A new version from the rows, or the latest where nothing but the code that built it changed.
    Returns the version's log record and whether it is new."""
    folder, log, current = store_paths(store)
    folder.mkdir(parents=True, exist_ok=True)
    with store_lock(store):
        records = read_versions(store)
        latest = records[-1] if records else None
        handle, name = tempfile.mkstemp(dir=folder, prefix=".building-")
        os.close(handle)
        fresh = Path(name)
        try:
            write_db(fresh, tables)
            if unchanged(fresh, folder, latest):
                write_current(current, latest["file"])
                return latest, False
            record = version_record(fresh, len(records) + 1, latest, tables, code_commit)
            seal(fresh, folder / record["file"])
        finally:
            fresh.unlink(missing_ok=True)
        with log.open("a", encoding="utf-8") as out:
            out.write(json.dumps(record, sort_keys=True) + "\n")
        write_current(current, record["file"])
    return record, True


def version_record(fresh, number, latest, tables, code_commit):
    digest = sha256_of(fresh)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {"version": number, "file": version_name(number, digest), "sha256": digest,
            "parent": latest["sha256"] if latest else None, "written_at": max(now, latest["written_at"]) if latest else now,
            "code_commit": code_commit, "items": len(tables["item"]), "bytes": Path(fresh).stat().st_size, "reason": "build"}


def open_store(store, version=None):
    """A version, read-only and immutable, its bytes checked against the log: the latest unless a number is named."""
    records = read_versions(store)
    if not records:
        raise Gold3Error(f"{store}: no store there; build one first")
    named = store_paths(store)[2].read_text(encoding="utf-8").strip()
    if named != records[-1]["file"]:
        raise Gold3Error(f"{store}: CURRENT names {named}, the log's last line {records[-1]['file']}")
    wanted = records[-1] if version is None else next((r for r in records if r["version"] == version), None)
    if wanted is None:
        raise Gold3Error(f"{store}: no version {version}")
    path = store_paths(store)[0] / wanted["file"]
    if sha256_of(path) != wanted["sha256"]:
        raise Gold3Error(f"{path}: its bytes are not the ones it was sealed with")
    db = sqlite3.connect(file_uri(path, "mode=ro&immutable=1"), uri=True)
    db.row_factory = sqlite3.Row
    return db


def store_root(named, repo=ROOT):
    """The store's folder: --root, else GOLD3_ROOT; never inside the repository, which holds no store."""
    root = named or os.environ.get(STORE_VARIABLE)
    if not root:
        raise Gold3Error(f"name the store with --root or {STORE_VARIABLE}; it lives outside the repository")
    resolved = Path(root).resolve()
    if resolved == Path(repo).resolve() or Path(repo).resolve() in resolved.parents:
        raise Gold3Error(f"{root}: the store lives outside the repository")
    return resolved

# ---------------------------------------------------------------- numbers for the pages


def wilson(hits, total, z=Z95):
    """The 95 percent Wilson interval of hits out of total, as fractions."""
    if not total:
        return (0.0, 1.0)
    p = hits / total
    centre = (p + z * z / (2 * total)) / (1 + z * z / total)
    half = z * ((p * (1 - p) / total + z * z / (4 * total * total)) ** 0.5) / (1 + z * z / total)
    # At none and at all the bounds are p itself, which floating point misses by a last digit; held to
    # p, as schwingnet.flow's wilson holds them, the interval always contains its own estimate.
    return (min(max(0.0, centre - half), p), max(min(1.0, centre + half), p))


def interval_text(hits, total):
    low, high = wilson(hits, total)
    return f"{hits} ({100 * hits / total:.1f} %, {100 * low:.1f} to {100 * high:.1f})" if total else str(hits)


def thousands(n):
    return "" if n is None else f"{n:,}"


def facts_committed(db):
    return bool(db.execute("SELECT COUNT(*) FROM item WHERE member = 'enhance_pet'").fetchone()[0])


def table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + " --- |" * len(header)]
    return lines + ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]


def class_shares(db, member, site=None):
    """Each class of one member (and site) with its count and its share of the whole studies."""
    where, params = "anomaly.member = ?", [member]
    if site:
        where, params = where + " AND item.site = ?", params + [site]
    whole = db.execute(f"SELECT COUNT(*) FROM anomaly JOIN item ON item.item = anomaly.item WHERE {where}"
                       " AND item.tier = 'gold3'", params).fetchone()[0]
    rows = db.execute(f"SELECT anomaly.class, COUNT(*) FROM anomaly JOIN item ON item.item = anomaly.item WHERE {where}"
                      " GROUP BY anomaly.class", params).fetchall()
    order = {k: i for i, k in enumerate(CLASSES + VERSE_CLASSES)}
    return whole, sorted(((c, n) for c, n in rows), key=lambda r: order.get(r[0], 99))


def status_counts(db, member):
    return db.execute("SELECT class, status, COUNT(*) FROM anomaly WHERE member = ? GROUP BY class, status"
                      " ORDER BY class, status", (member,)).fetchall()


def distribution(db, column, member="enhance_pet", where="item.tier = 'gold3'"):
    return db.execute(f"SELECT anomaly.{column}, COUNT(*) FROM anomaly JOIN item ON item.item = anomaly.item"
                      f" WHERE anomaly.member = ? AND {where} GROUP BY anomaly.{column} ORDER BY COUNT(*) DESC, anomaly.{column}",
                      (member,)).fetchall()


DISTANCE_BINS = ((TOUCH_MM, f"touching, {TOUCH_MM} mm or less"), (CONTROL_NEAREST_ACROSS_L5_MM, f"{TOUCH_MM} to {CONTROL_NEAREST_ACROSS_L5_MM} mm"),
                 (5.0, f"{CONTROL_NEAREST_ACROSS_L5_MM} to 5 mm"), (10.0, "5 to 10 mm"), (20.0, "10 to 20 mm"),
                 (float("inf"), "over 20 mm"))


def distance_bins(db):
    values = [r[0] for r in db.execute("SELECT anomaly.l4_to_sacrum_mm FROM anomaly JOIN item ON item.item = anomaly.item"
                                       " WHERE anomaly.member = 'enhance_pet' AND item.tier = 'gold3'"
                                       " AND anomaly.l4_to_sacrum_mm IS NOT NULL")]
    edges = [float("-inf"), *(edge for edge, _ in DISTANCE_BINS)]
    counts = [sum(1 for v in values if low < v <= high) for low, high in zip(edges, edges[1:])]
    median = round(statistics.median(values), 1) if values else None
    return [(name, n) for (_, name), n in zip(DISTANCE_BINS, counts)], median, len(values)


def note_groups(db, record):
    """The note's three columns as item lists: the record's controls, then the rules' two groups."""
    controls = [f"enhance_pet:{i}" for i in record["controls"]["ids"]]
    return {"controls": controls, "L4 above the sacrum": count_class_items(db, "no_l5", with_l6=False),
            "L6 below L5": count_class_items(db, "strict", with_l6=True)}


def count_class_items(db, count_class, with_l6):
    """ENHANCE.PET items of one count class, with or without an L6 label on the published mask."""
    has_l6 = ("EXISTS (SELECT 1 FROM label WHERE label.facts_row = item.native_id AND label.source_label = ?"
              " AND label.present = 1)")
    sql = (f"SELECT item FROM item WHERE member = 'enhance_pet' AND count_class = ? AND {'' if with_l6 else 'NOT '}{has_l6}"
           " ORDER BY item")
    return [r[0] for r in db.execute(sql, (count_class, L6))]


def note_table(db, record):
    """The note's table of where the lowest rib meets, made again from the rows, beside the note's numbers."""
    expected = record["note_table"]
    groups = note_groups(db, record)
    rows = {r[0]: r[1] for r in db.execute("SELECT item, lowest_rib_row FROM anomaly WHERE member = 'enhance_pet'")}
    found = {}
    for column, name in enumerate(expected["columns"]):
        for item in groups[name]:
            found.setdefault(rows.get(item, "not in the rows"), [0] * len(expected["columns"]))[column] += 1
    names = list(expected["rows"]) + sorted(set(found) - set(expected["rows"]))
    table_rows = {name: found.get(name, [0] * len(expected["columns"])) for name in names}
    studies = [len(groups[name]) for name in expected["columns"]]
    matches = all(table_rows[n] == expected["rows"].get(n, [0] * len(studies)) for n in names) and studies == expected["studies"]
    return {"columns": expected["columns"], "rows": table_rows, "studies": studies, "expected": expected["rows"],
            "expected_studies": expected["studies"], "matches": matches}

# ---------------------------------------------------------------- STATS.md


def stats_page(db, inputs):
    lines = ["# Gold tier 3 CT dataset: statistics", "",
             f"Written by `python3 {TOOL} stats` from the committed files under {DATA}/ (their sha256 are listed at the end);"
             f" do not edit it by hand, since `python3 {TOOL} check` fails on a page that is not what the files give."
             " Every share carries its 95 percent Wilson interval. A class rests on two masks the same readers checked;"
             " it is not a reader's read of the CT (QA.md says what the checks can and cannot show).", ""]
    lines += members_section(db) + enhance_sections(db, inputs) + verse_section(db) + roles_section(db)
    return "\n".join(lines + inputs_section(inputs)) + "\n"


def members_section(db):
    order = {name: i for i, name in enumerate(MEMBER_ORDER)}
    rows = sorted(db.execute("SELECT * FROM member_count WHERE site = 'all'").fetchall(), key=lambda r: order[r["member"]])
    body = [(r["member"], thousands(r["studies"]), thousands(r["gold3"]), thousands(r["gold4"]), thousands(r["silver3"]),
             thousands(r["gold3_by_records"]), persons_text(r), r["persons_basis"]) for r in rows]
    return ["## Members", ""] + table(("Member", "Rows", "Gold 3", "Gold 4", "Silver 3", "Gold 3 by the records",
                                       "Persons", "Persons basis"), body) + [""]


def persons_text(row):
    low, high = row["persons_low"], row["persons_high"]
    if low is None:
        return f"at most {thousands(high)}"
    return thousands(low) if low == high else f"{thousands(low)} to {thousands(high)}"


def enhance_sections(db, inputs):
    if not facts_committed(db):
        return ["## ENHANCE.PET", "",
                f"The ENHANCE.PET rows are not yet committed ({FACTS}, made by bordercall's holdings/enhance_facts.py"
                " from the published masks), so this page carries their counts by the records alone. Once they are,"
                f" `python3 {TOOL} stats` writes the sites, the classes with their intervals, the note's table made again"
                " and the distributions here.", ""]
    return (sites_section(db) + classes_section(db) + statuses_section(db) + note_section(db, inputs)
            + distributions_section(db) + exclusions_section(db))


def sites_section(db):
    rows = db.execute("SELECT * FROM member_count WHERE member = 'enhance_pet' ORDER BY site = 'all', site").fetchall()
    body = [(r["site"], thousands(r["studies"]), thousands(r["gold3"]), thousands(r["gold4"]), thousands(r["silver3"]),
             persons_text(r)) for r in rows]
    return ["## ENHANCE.PET by site", ""] + table(("Site", "Studies", "Whole, gold 3", "Repaired, gold 4",
                                                   "Not whole, silver 3", "Persons"), body) + [""]


def classes_section(db):
    sites = [r[0] for r in db.execute("SELECT DISTINCT site FROM item WHERE member = 'enhance_pet' ORDER BY site")]
    columns = [None, *sites]
    shares = [class_shares(db, "enhance_pet", site) for site in columns]
    names = list(dict.fromkeys(c for _, found in shares for c, _ in found))
    body = [(name, *(share_cell(dict(found).get(name, 0), whole, name) for whole, found in shares)) for name in names]
    header = ("Class", "All", *sites)
    return (["## ENHANCE.PET classes", "",
             "One class per study. The share is of the whole studies (gold 3) of the column; a repaired or not-whole"
             " study is counted, with no share, since it is not among them.", ""]
            + table(header, body) + [""])


def share_cell(n, whole, name):
    return thousands(n) if name in ("repaired", "not_whole") else interval_text(n, whole)


def statuses_section(db):
    body = [(c, s, thousands(n)) for c, s, n in status_counts(db, "enhance_pet")]
    return ["## ENHANCE.PET statuses", ""] + table(("Class", "Status", "Studies"), body) + [""]


def note_section(db, inputs):
    found = note_table(db, inputs["record"])
    columns = found["columns"]
    body = [(name, *(f"{f}" if f == e else f"{f} (note {e})" for f, e in zip(cells, found["expected"].get(name, [0] * len(columns)))))
            for name, cells in found["rows"].items()]
    body.append(("Studies", *(f"{f}" if f == e else f"{f} (note {e})" for f, e in zip(found["studies"], found["expected_studies"]))))
    verdict_line = ("The rows give the note's numbers exactly." if found["matches"]
                    else "The rows do not give the note's numbers; each cell that differs shows the note's beside it.")
    return (["## The note's table, made again", "",
             "Where the lowest rib meets, for the record's 100 controls and the rules' two groups (docs/research/"
             "enhance-pet-gold-tier-3.md, What the ribs say about the unusual lumbar counts). " + verdict_line, ""]
            + table(("Lowest rib meets", *columns), body) + [""])


def distributions_section(db):
    lines = ["## ENHANCE.PET distributions, whole studies", ""]
    for title, column in (("Rib pairs", "rib_pairs"), ("Lowest rib meets", "lowest_rib_row"),
                          ("Bodies above the sacrum, by the names", "presacral_by_names"),
                          ("Call by the names", "call_by_names"), ("Call by the ribs", "call_by_ribs"),
                          ("Rib ladder", "rib_ladder"), ("Lumbar names", "label_pattern")):
        lines += [f"{title}: " + "; ".join(f"{value if value is not None else 'none'} {thousands(n)}"
                                           for value, n in distribution(db, column)) + ".", ""]
    bins, median, n = distance_bins(db)
    lines += ["L4 to the sacrum, shortest 3-D distance, over the " + thousands(n) + " whole studies that carry it"
              + (f" (median {median} mm)" if median is not None else "") + ": "
              + "; ".join(f"{name} {thousands(count)}" for name, count in bins) + ".", ""]
    return lines


def exclusions_section(db):
    rows = db.execute("SELECT class_reason, COUNT(*) FROM anomaly WHERE member = 'enhance_pet' AND class = 'not_whole'"
                      " GROUP BY class_reason ORDER BY COUNT(*) DESC, class_reason").fetchall()
    body = [(reason, thousands(n)) for reason, n in rows]
    return ["## Why a study is not whole", ""] + (table(("Reason", "Studies"), body) if body else ["None."]) + [""]


def verse_section(db):
    rows = db.execute("SELECT item.native_id, anomaly.class, anomaly.status, person.anomaly_role, anomaly.castellvi"
                      " FROM anomaly JOIN item ON item.item = anomaly.item JOIN person ON person.person = item.person"
                      " WHERE anomaly.member = 'verse' ORDER BY item.native_id").fetchall()
    body = [(r[0], r[1], r[2], r[3], r[4] or "") for r in rows]
    whole, found = class_shares(db, "verse")
    shares = "; ".join(f"{name} {interval_text(n, whole)}" for name, n in found)
    return (["## VerSe", "", "17 series of 17 persons, gold 3 provisional until each sacrum is confirmed on the grid;"
             " the classes are the readers' reads as the committed records carry them. " + shares + ".", ""]
            + table(("Series", "Class", "Status", "Anomaly route role", "Castellvi"), body) + [""])


def roles_section(db):
    rows = db.execute("SELECT member, anomaly_role, COUNT(*) FROM person GROUP BY member, anomaly_role"
                      " ORDER BY member, anomaly_role").fetchall()
    body = [(m, r, thousands(n)) for m, r, n in rows]
    return (["## Holdout and folds", "", "Persons the SPINEPS to FleXray route holds out or deals into folds"
             " (data/splits/anomaly-holdout.json) are carried, flagged, and never trained on (training_allowed 0).", ""]
            + table(("Member", "Role", "Persons"), body) + [""])


def page_inputs(inputs):
    """The dataset's own files and their sha256, as the pages list them. The split files and
    data/licences.json are read too, but a change there that moves no row of this dataset must not fail
    every other pull request's check; one that moves a row changes the pages' text, and the check fails
    on that. The store's build table keeps every input's hash."""
    return {rel: digest for rel, digest in inputs["hashes"].items() if rel.startswith(f"{DATA}/")}


def inputs_section(inputs):
    lines = ["## Inputs", ""]
    for rel, digest in sorted(page_inputs(inputs).items()):
        lines.append(f"- {rel}: {digest if digest else 'not committed'}")
    return lines

# ---------------------------------------------------------------- QA.md


def qa_page(db, inputs):
    lines = ["# Gold tier 3 CT dataset: quality assurance", "",
             f"Written by `python3 {TOOL} qa` from the committed files under {DATA}/; do not edit it by hand, since"
             f" `python3 {TOOL} check` fails on a page that is not what the files give.", "",
             "What the checks can show: that the release's names, the rib ladder and the label geometry hold together,"
             " study by study. They read two masks the same four readers checked, so a study that passes every one is"
             " consistent, not read: confirmed_by_masks is never a reader's read of the CT. No mask check can settle a"
             " lumbosacral question (sacralisation, lumbarisation, Castellvi), which waits for the CT and a person;"
             " reader_confirmed comes only from a recorded reader's verdict.", ""]
    if not facts_committed(db):
        lines += [f"The ENHANCE.PET rows are not yet committed ({FACTS}), so no check has run on them. VerSe's and"
                  " TotalSegmentator's checks need their masks, which are on the grid.", ""]
    return "\n".join(lines + checks_section(db) + flagged_section(db)) + "\n"


def checks_section(db):
    counts = {}
    for check, kind, n in db.execute("SELECT check_id, verdict, COUNT(*) FROM qa_check GROUP BY check_id, verdict"):
        counts.setdefault(check, {})[kind] = n
    body = [(cid, version, title, check_text(function), thresholds_text(cid),
             *(thousands(counts.get(cid, {}).get(k, 0)) for k in ("pass", "fail", "look", "not_run")))
            for cid, version, title, function in CHECKS]
    return ["## The checks", ""] + table(("Id", "Version", "Check", "What it holds", "Thresholds", "Pass", "Fail", "Look",
                                          "Not run"), body) + [""]


def flagged_section(db):
    lines = ["## Every fail and look", ""]
    rows = db.execute("SELECT check_id, verdict, facts_row, value, known FROM qa_failures ORDER BY check_id, verdict, facts_row").fetchall()
    if not rows:
        return lines + ["None.", ""]
    for (check, kind), group in itertools.groupby(rows, key=lambda r: (r[0], r[1])):
        group = list(group)
        lines.append(f"- {check} {kind} ({len(group)}): " + "; ".join(flag_text(r) for r in group) + ".")
    return lines + [""]


def flag_text(row):
    known = f" [known: {row['known']}]" if row["known"] else ""
    return f"{row['facts_row']} {row['value']}{known}"

# ---------------------------------------------------------------- the page's data


PAGE_COLUMNS = ("item", "member", "site", "tier", "provisional", "part", "anomaly_role", "training_allowed", "class",
                "status", "needs_ct", "call_by_names", "call_by_ribs", "rib_pairs", "lowest_rib_row",
                "l4_to_sacrum_mm", "qa_fail", "qa_look")


def study_rows(db):
    sql = ("SELECT item.item, item.member, item.site, item.tier, item.provisional, item.part, person.anomaly_role,"
           " person.training_allowed, anomaly.class, anomaly.status, anomaly.needs_ct, anomaly.call_by_names,"
           " anomaly.call_by_ribs, anomaly.rib_pairs, anomaly.lowest_rib_row, anomaly.l4_to_sacrum_mm,"
           " (SELECT GROUP_CONCAT(check_id, ' ') FROM (SELECT check_id FROM qa_check WHERE qa_check.item = item.item"
           "  AND verdict = 'fail' ORDER BY check_id)),"
           " (SELECT GROUP_CONCAT(check_id, ' ') FROM (SELECT check_id FROM qa_check WHERE qa_check.item = item.item"
           "  AND verdict = 'look' ORDER BY check_id))"
           " FROM item JOIN person ON person.person = item.person LEFT JOIN anomaly ON anomaly.item = item.item ORDER BY item.item")
    return [list(r) for r in db.execute(sql)]


def page_data(db, inputs):
    """What the private page shows: the members, the classes with intervals, the note's table, the checks
    and one row per study, from the same rows the store holds."""
    note = note_table(db, inputs["record"]) if facts_committed(db) else None
    return {
        "about": "The gold tier 3 CT dataset's page data, written by python3 tools/gold3_ct.py page; confidential.",
        "facts_committed": facts_committed(db),
        "members": [dict(r) for r in db.execute("SELECT * FROM member_count ORDER BY member, site")],
        "classes": [dict(r) for r in db.execute("SELECT * FROM anomalies_by_class_and_status ORDER BY member, site, class, status")],
        "class_shares": class_share_rows(db),
        "note_table": note,
        "checks": [{"id": cid, "version": v, "title": t, "holds": check_text(f), "thresholds": thresholds_text(cid)}
                   for cid, v, t, f in CHECKS],
        "qa_counts": [dict(r) for r in db.execute("SELECT check_id, verdict, COUNT(*) AS n FROM qa_check GROUP BY check_id, verdict ORDER BY check_id, verdict")],
        "studies": {"columns": list(PAGE_COLUMNS), "rows": study_rows(db)},
        "schema": SCHEMA.strip(),
        "inputs": page_inputs(inputs),
    }


def class_share_rows(db):
    out = []
    for member, site in db.execute("SELECT DISTINCT member, site FROM member_count ORDER BY member, site").fetchall():
        whole, found = class_shares(db, member, None if site == "all" else site)
        for name, n in found:
            low, high = wilson(n, whole)
            out.append({"member": member, "site": site, "class": name, "n": n, "whole": whole,
                        "low": round(low, 4), "high": round(high, 4)})
    return out


def page_text(data):
    """The data as JSON, a study a line, so a change reads as a diff of the rows it touches."""
    head = {k: v for k, v in data.items() if k != "studies"}
    lines = ["{"]
    for key in sorted(head):
        lines.append(f" {json.dumps(key)}: {json.dumps(head[key], sort_keys=True)},")
    lines.append(f' "studies": {{"columns": {json.dumps(data["studies"]["columns"])}, "rows": [')
    rows = data["studies"]["rows"]
    lines += [f"  {json.dumps(row)}{',' if i < len(rows) - 1 else ''}" for i, row in enumerate(rows)]
    lines += [" ]}", "}"]
    return "\n".join(lines) + "\n"

# ---------------------------------------------------------------- the manifest


def export_rows(db, tier=None, training_only=False):
    """One row per study, as the workflow reads it: person, member, site, tier, part, the holdout flags,
    the class and status, and where the CT and the masks are."""
    sql = ("SELECT m.*, (SELECT url FROM mask WHERE mask.item = m.item AND kind = 'vertebrae') AS vertebrae_url,"
           " (SELECT url FROM mask WHERE mask.item = m.item AND kind = 'ribs') AS ribs_url,"
           " (SELECT location FROM mask WHERE mask.item = m.item AND kind = 'vertebrae_repaired') AS repaired_mask"
           " FROM workflow_manifest AS m WHERE (? IS NULL OR m.tier = ?) AND (? = 0 OR m.training_allowed = 1)"
           " ORDER BY m.item")
    rows = [dict(r) for r in db.execute(sql, (tier, tier, int(training_only)))]
    for row in rows:
        row["holdout"] = int(row["anomaly_role"] != "none")
    return rows


def export_text(rows, kind):
    if kind == "json":
        return "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=sorted(rows[0]) if rows else ["item"], lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()

# ---------------------------------------------------------------- written files and the check


def written(repo=ROOT):
    """Every file the tool writes into the repository, by path, from a build of the committed files."""
    inputs = load_inputs(repo)
    with contextlib.closing(memory_db(inputs)) as db:
        return pages_of(db, inputs)


def pages_of(db, inputs):
    return {STATS_PAGE: stats_page(db, inputs), QA_PAGE: qa_page(db, inputs), PAGE_DATA: page_text(page_data(db, inputs))}


def data_problems(inputs):
    """What breaks in the committed data files, beside the facts' schema."""
    problems = facts_record_problems(inputs["facts"], inputs["facts_record"])
    if inputs["facts"] is not None:
        problems += facts_problems(inputs["facts"], inputs["record"], inputs["bucket"])
    names = [m["member"] for m in inputs["members"]["members"]]
    if names != list(MEMBER_ORDER):
        problems.append(f"{MEMBERS}: the members are enhance_pet, verse and totalsegmentator, in that order")
    problems += verse_problems(inputs) + record_problems(inputs["record"])
    if inputs["totalsegmentator"]["rows"]:
        problems.append(f"{TOTALSEG}: rows are written by the grid index job, none by hand")
    return problems


def verse_problems(inputs):
    roles, scans = anomaly_roles(inputs["holdout"])
    problems = []
    for series in inputs["verse"]["series"]:
        person = scans.get(series["id"], f"verse:{series['id']}")
        role = roles.get(person, "none")
        if series["person"] != person or series["role"] != role:
            problems.append(f"{VERSE}: {series['id']} says {series['person']} {series['role']},"
                            f" {HOLDOUT} gives {person} {role}")
        if series["variant"] not in VERSE_CLASS or not series["claims"]:
            problems.append(f"{VERSE}: {series['id']} has no known variant or no claim with its source")
    if len(inputs["verse"]["series"]) != member_of(inputs, "verse")["studies_listed"]:
        problems.append(f"{VERSE}: the series are not the {member_of(inputs, 'verse')['studies_listed']} {MEMBERS} lists")
    return problems


def record_problems(record):
    """Each study the record names once, under one decision, with a reason and a source."""
    seen, problems = set(), []
    for klass in RECORD_CLASSES:
        for entry in record.get(klass, []):
            if entry["id"] in seen or not entry.get("why") or not entry.get("source"):
                problems.append(f"{RECORD}: {entry['id']} is named twice or lacks a reason or a source")
            seen.add(entry["id"])
    return problems


def check(repo=ROOT):
    """(problems, notes): what fails the repository, and what a person should know though it passes."""
    inputs = load_inputs(repo)
    problems = data_problems(inputs)
    if problems:
        return problems, []
    notes = []
    with contextlib.closing(memory_db(inputs)) as db:
        matches = note_table(db, inputs["record"])["matches"] if facts_committed(db) else None
        problems += tier_differences(db, inputs)
        pages = pages_of(db, inputs)
    if matches is False:
        problems.append("the ENHANCE.PET classes do not give the note's table; STATS.md shows the cells that differ")
    if matches is None:
        notes.append(f"the ENHANCE.PET facts are not yet committed ({FACTS}); the dataset carries their counts by the records")
    for rel, text in pages.items():
        path = Path(repo) / rel
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            problems.append(f"{rel}: not what the committed files give; run python3 {TOOL} {COMMAND_OF[rel]}")
    return problems, notes


COMMAND_OF = {STATS_PAGE: "stats", QA_PAGE: "qa", PAGE_DATA: "page"}


def tier_differences(db, inputs):
    """Each member with rows whose tiers are not the counts members.json records: the rows and the
    records are two readings of one release, and a difference is a bug or a record to correct."""
    problems = []
    for row in db.execute("SELECT * FROM member_count WHERE site = 'all' AND studies > 0"):
        member = member_of(inputs, row["member"])
        found = [row[tier] for tier in ("gold3", "gold4", "silver3")]
        recorded = [member[tier] for tier in ("gold3", "gold4", "silver3")]
        if found != recorded:
            problems.append(f"{row['member']}: the rows give gold 3, gold 4 and silver 3 {found}, {MEMBERS} records {recorded}")
    return problems

# ---------------------------------------------------------------- the command line


def parser():
    top = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    top.add_argument("--repo", default=str(ROOT), help="the repository to read and write (a scratch copy, for a test)")
    sub = top.add_subparsers(dest="command", required=True)
    build_p = sub.add_parser("build", help="build a new version of the store from the committed files")
    build_p.add_argument("--root", default=None, help=f"the store's folder, outside the repository; else {STORE_VARIABLE}")
    build_p.add_argument("--code-commit", default=None)
    query = sub.add_parser("query", help="run a read-only query on the store's current version")
    query.add_argument("sql")
    query.add_argument("--root", default=None)
    query.add_argument("--version", type=int, default=None)
    query.add_argument("--json", action="store_true", help="one JSON object a row, not tab-separated")
    for name in ("stats", "qa"):
        sub.add_parser(name, help=f"write {STATS_PAGE if name == 'stats' else QA_PAGE}")
    page = sub.add_parser("page", help=f"write {PAGE_DATA}")
    page.add_argument("--root", default=None, help="read the store's current version instead of building in memory")
    export = sub.add_parser("export", help="print the manifest the workflow reads")
    export.add_argument("--format", choices=("json", "csv"), default="json")
    export.add_argument("--tier", default=None, help="gold3, gold4 or silver3")
    export.add_argument("--training-only", action="store_true", help="leave out holdout and fold persons")
    export.add_argument("--root", default=None, help="read the store's current version instead of building in memory")
    export.add_argument("--out", default=None, help="a file to write; else standard output")
    sub.add_parser("check", help="exit 1 when a written file is stale or the committed data breaks its schema")
    take = sub.add_parser("take-facts", help=f"take a reading of the masks into {FACTS}, {FACTS_B} and {FACTS_RECORD}")
    take.add_argument("facts", help="the first reading's rows (holdings/enhance_facts.py)")
    take.add_argument("facts_b", help="the second reading's rows (holdings/enhance_facts_check.py)")
    take.add_argument("--read-on", required=True, help="where the masks were read, for FACTS.json; no path under the data root")
    take.add_argument("--bordercall-commit", required=True, help="bordercall's commit the readers ran at")
    take.add_argument("--date", default=time.strftime("%Y-%m-%d", time.gmtime()), help="the day the masks were read, UTC")
    return top


def source_db(args, inputs):
    """The store's current version where one is named, else the committed files built into memory."""
    if args.root or (args.command == "export" and os.environ.get(STORE_VARIABLE)):
        return open_store(store_root(args.root, args.repo))
    return memory_db(inputs)


def write_file(repo, rel, text):
    path = Path(repo) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"wrote {rel}")


def command_build(args):
    inputs = load_inputs(args.repo)
    inputs["code_digest"] = code_digest(args.repo)
    inputs["code_commit"] = args.code_commit
    record, new = build(store_root(args.root, args.repo), assemble(inputs), args.code_commit)
    print(json.dumps({"version": record["version"], "file": record["file"], "sha256": record["sha256"],
                      "new": new, "items": record["items"]}, sort_keys=True))
    return 0


def command_query(args):
    with contextlib.closing(open_store(store_root(args.root, args.repo), args.version)) as db:
        cursor = db.execute(args.sql)
        names = [d[0] for d in cursor.description or ()]
        if not args.json:
            print("\t".join(names))
        for row in cursor:
            print(json.dumps(dict(zip(names, row)), sort_keys=True) if args.json else "\t".join("" if v is None else str(v) for v in row))
    return 0


def command_page(args):
    inputs = load_inputs(args.repo)
    with contextlib.closing(source_db(args, inputs)) as db:
        write_file(args.repo, PAGE_DATA, page_text(page_data(db, inputs)))
    return 0


def command_pages(args):
    inputs = load_inputs(args.repo)
    with contextlib.closing(memory_db(inputs)) as db:
        write_pages(args, db, inputs)
    return 0


def write_pages(args, db, inputs):
    if args.command == "stats":
        write_file(args.repo, STATS_PAGE, stats_page(db, inputs))
    else:
        write_file(args.repo, QA_PAGE, qa_page(db, inputs))
        for check_id, kind, n in db.execute("SELECT check_id, verdict, COUNT(*) FROM qa_check GROUP BY check_id, verdict ORDER BY 1, 2"):
            print(f"{check_id} {kind} {n}")


def command_export(args):
    inputs = load_inputs(args.repo)
    with contextlib.closing(source_db(args, inputs)) as db:
        text = export_text(export_rows(db, args.tier, args.training_only), args.format)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


def row_line(row):
    """One facts row as bordercall's holdings/enhance_facts.py writes it."""
    return json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n"


def joined_rows(reading, repaired):
    """The reading's rows with the repaired rows it lacks, sorted by id. A reading that has a repaired
    row too must have the side file's, field for field, or neither is taken."""
    have = {row["id"]: row for row in reading}
    for row in repaired or ():
        if have.setdefault(row["id"], row) != row:
            raise Gold3Error(f"the reading's row {row['id']} differs from {FACTS_REPAIRED}'s")
    return [have[sid] for sid in sorted(have)]


def published_differences(rows, committed):
    """The study ids whose row from the published masks differs between two readings, or one lacks."""
    mine = {row["id"]: row for row in rows if "repaired_from" not in row}
    theirs = {row["id"]: row for row in committed if "repaired_from" not in row}
    return sorted(sid for sid in mine.keys() | theirs.keys() if mine.get(sid) != theirs.get(sid))


def second_reading_problems(rows, bucket):
    ids = [row.get("id") for row in rows]
    if len(set(ids)) != len(ids) or (bucket and set(ids) != set(bucket["studies"])):
        return [f"the second reading covers {len(set(ids))} studies, the bucket lists {len(bucket['studies'])}"]
    return []


def facts_record_of(repo, rows, args):
    """FACTS.json: where and by what the rows were read, the inputs' hashes, and the row count check reads."""
    return {"bordercall_commit": args.bordercall_commit, "ct_details_sha256": sha256_of(Path(repo) / CT_DETAILS),
            "date": args.date, "facts_b": f"{FACTS_B}, read by bordercall's holdings/enhance_facts_check.py",
            "masks_sha256sums_sha256": sha256_of(Path(repo) / MASK_SUMS), "read_on": args.read_on,
            "repaired_rows": "read from the repair record in the thread's container", "rows": len(rows),
            "tool": "bordercall holdings/enhance_facts.py"}


def reproduced_record(record, args):
    """FACTS.json with this reading added to the readings that gave its rows again, once."""
    entry = {"bordercall_commit": args.bordercall_commit, "date": args.date, "read_on": args.read_on}
    readings = record.setdefault("reproduced_on", [])
    if entry not in readings:
        readings.append(entry)
    return record


def command_take_facts(args):
    """A reading of the published masks into the facts files: the first reading with the repaired rows
    joined, the second beside it, and FACTS.json. Where facts are committed already, the rows are left as
    they are: a reading that gives them again is added to FACTS.json's reproduced_on, and one that does
    not changes nothing and exits 1."""
    if not re.fullmatch(r"[0-9a-f]{40}", args.bordercall_commit):
        raise Gold3Error(f"--bordercall-commit {args.bordercall_commit!r} is no full commit id")
    repo = Path(args.repo)
    inputs = load_inputs(repo)
    repaired = optional(repo, FACTS_REPAIRED, read_jsonl)
    if repaired is None and inputs["facts"] is not None:
        repaired = [row for row in inputs["facts"] if "repaired_from" in row]
    rows = joined_rows(read_jsonl(args.facts), repaired)
    second = sorted(read_jsonl(args.facts_b), key=lambda row: row.get("id", ""))
    problems = facts_problems(rows, inputs["record"], inputs["bucket"]) + second_reading_problems(second, inputs["bucket"])
    if problems:
        raise Gold3Error("the reading is not taken: " + "; ".join(problems[:10]))
    if inputs["facts"] is not None:
        differ = {"facts": published_differences(rows, inputs["facts"]),
                  "facts_b": published_differences(second, inputs["facts_b"] or [])}
        reproduces = not any(differ.values())
        print(json.dumps({"reproduces": reproduces, "differ": differ}, sort_keys=True))
        if not reproduces:
            return 1
        record = reproduced_record(inputs["facts_record"], args)
        write_file(repo, FACTS_RECORD, json.dumps(record, indent=1, sort_keys=True) + "\n")
        return 0
    write_file(repo, FACTS, "".join(map(row_line, rows)))
    write_file(repo, FACTS_B, "".join(map(row_line, second)))
    write_file(repo, FACTS_RECORD, json.dumps(facts_record_of(repo, rows, args), indent=1, sort_keys=True) + "\n")
    if (repo / FACTS_REPAIRED).is_file():
        (repo / FACTS_REPAIRED).unlink()
        print(f"removed {FACTS_REPAIRED}")
    return 0


def command_check(args):
    problems, notes = check(args.repo)
    for note in notes:
        print(f"note: {note}")
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        return 1
    print(f"{DATA} and {OUT}: current")
    return 0


HANDLERS = {"build": command_build, "query": command_query, "stats": command_pages, "qa": command_pages,
            "page": command_page, "export": command_export, "check": command_check, "take-facts": command_take_facts}


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        return HANDLERS[args.command](args)
    except (Gold3Error, sqlite3.Error) as error:
        print(f"gold3_ct: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
