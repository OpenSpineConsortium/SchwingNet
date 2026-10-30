"""The gold tier 3 morphometry beside each person's sex and age: one CPU job on the grid that joins the rows
the word `morphometry <set>` measured with the persons they belong to, and writes the aggregates a sex and age
analysis starts from.

Source: the thread "Extract morphometrics from gold tier 3 CT", 2026-10-30: the morphometry rows of ENHANCE.PET
and of VerSe with TotalSegmentator's admitted subjects (jobs 40872077 and 40877151 on bordercall 16f7b40, and
once more on ee495d5 on the owner's count of 2026-10-30 14:33 UTC) are long rows of a study, a level, a measure
and a value, and the per-person covariate analysis needs each person's sex and age beside them, which no
committed file holds. grid/morphometry-covariates.sbatch runs this file from git's copy of it at the gate's
commit, and the gate's word `morphometry covariates` queues it once, on the owner's count. Confidential, like
the rest of SchwingNet: the joined per-person table stays in the job's folder on the lab volume, mode 0700,
and only the aggregates in report.lines leave the grid, in the job's report.

    python3 tools/gold3_covariates.py --morphometry ROOT --verse-demographics CSV --data DATA_ROOT --out DIR
        [--autopet AUTOPET_JSON] [--index SAMPLES_SQLITE] [--records DIR] [--workers N] [--previous DIR ...]

where ROOT holds enhance/rows.csv, verse/rows.csv and verse/totalseg/rows.csv as grid/morphometry.sbatch
writes them; an absent --autopet or --index is a failure the report says, autoPET then having no person or
no sex and age; and each --previous names the job folder of an earlier join whose report printed cells, whose
joined.csv the check across reports reads (below).

Where each person and their sex and age come from:

    autoPET     ENHANCE.PET's autoPET studies, matched to TCIA's FDG-PET-CT-Lesions CTs by their grids in the
                census (its autopet.json, a PETCT key a study); sex and age from the DICOM headers of that
                person's series in the sample index (samples.sqlite, file.patient_sex and file.age_years of
                the first file of each series), the age of the series in the matched CT's own study folder, or
                of the person's only study in the index; weight and height from the same headers, kept in the
                per-person table only. One study a person: the first, the scan taken at the youngest age the
                index reads, the lowest ENHANCE.PET id breaking a tie or standing in where no age is read.
    Leipzig, Careggi   ENHANCE.PET's other sites carry no person id, sex or age anywhere: each study is its own
                person, sex unknown, kept apart in the per-person table and counted in the fill rates only.
    VerSe       each admitted series' person and age from data/gold3-ct/verse/series.json, sex from VerSeFusion's
                demographics table on the grid, checked against the sha256 series.json records; its first column
                is the person and its second the series where a person has several (series.json names its
                reader), but its sex column's name is recorded nowhere, so the header is read and the one column
                named sex or gender taken, and none found is a failure said in the report. One series a person,
                chosen as autoPET's study is.
    TotalSegmentator   each admitted subject its own person; age and gender from the release's meta.csv,
                semicolon separated, read from the extracted release or from inside its zip and checked
                against the sha256 data/gold3-ct/totalsegmentator/subjects.json records. The release jitters
                its ages by up to four years between versions, which slightly flattens an age slope.

Left out before any person is made: every study the admission (data/gold3-ct/admission.json) does not admit;
ENHANCE.PET 1134, 1283 and 1347, admitted on their repaired masks but measured on the published ones; and every
ENHANCE.PET study whose CT on the data root is not on its mask's grid (the census found one, named only on the
grid, so it is found again here as the census's held part found it). A person's age is their chosen study's,
and an age above AGE_CEILING is unknown (three TotalSegmentator subjects, s1774, s1776 and s1839, read 115 to
118). The tables are of adults: a person whose known age is under ADULT_AGE enters none of them, no mean, g, r
or slope, as docs/research/morphometry-beyond-the-42-papers.md recommends until the owner sets the age range,
though the dataset itself carries its children and never leaves one out (docs/research/gold3-ct/README.md,
decision 13); a person of unknown age enters the sex tables, g and r but no slope, which is over adults of known
age alone; the fill rates count the children and the persons of unknown age apart.

Each study's rows name the code that measured them, bordercall's code stamp in its code row: a study that names
none, and rows measured by more than one stamp, within a set or between the sets, are failures the report says,
since one table over two engines would blend their definitions, and the stamp is printed beside the counts, so
the report names the engine it rests on. interpedicular is left out at each vertebra the rows flag
interpedicular_band: there no pedicle was found on both sides, and the hole's width through its middle stands in,
flagged, for the reading on the pedicles' walls; that width read about 2 to 3 mm under the papers' interpedicular
distances at L4 and L5 (grid/bordercall/morphometry/canal.py, the run of 2026-10-29), so a mean over both would
blend two definitions; the report counts the stand-ins left out.

The aggregates, over the measures the bordercall vocabulary names (VERTEBRA_KEYS at T10 to L5, DISC_KEYS at the
discs T10-T11 to L4-L5) and a whole-column summary, T10-L5, each person's mean over every level of the range,
taken only where the person has all of them, so that a person missing the largest or the smallest body never
moves the mean:
- fill rates of sex and age per member and part (ENHANCE.PET's sites);
- for each member (autopet, verse, totalseg), measure, level and sex: n, mean and SD where n is at least
  MIN_CELL; Hedges' g, men minus women, with its variance, where both sexes' means are shown; the within-person
  Pearson correlation of the level with the one above it (T10-T11 to L4-L5, and the discs' pairs likewise),
  within sex, where at least MIN_PAIR persons of that sex have both; and the least squares slope of the measure
  on age per decade within sex with its standard error, over the adults of known age, where there are at least
  MIN_SLOPE (two parameters rest on them, as a correlation's co-variation does).

No printed means can be differenced against one another into a sum over fewer than MIN_CELL persons. Each line
is one member's and each of its blocks one sex's; the members' persons are distinct and no line pools members or
sexes (the pooling across members is done later from the member lines, by inverse variance, off the grid), so the
only means that can be set against one another are one member's and one sex's, of one measure or of measures one
of which is made from others, and two such relations are left. The column's persons, those with every level,
are among each level's, and the level means times their n, summed, less the column's mean times its n and the
number of levels, give the sum over the persons with some of the levels but not all: so a sex's column mean and
SD are shown only where those persons number none or MIN_CELL at least, which is the one relation one measure's
lines hold. And a measure that is the mean of others printed beside it (DERIVED: bordercall's disc_h_mean, the
mean of the three disc heights, grid/bordercall/morphometry/column.py) would with them give the sum over the
persons who have some of them but not all, and with the columns could carve that down to one person: so it is
shown, at a level or at the column, only where its persons are each part's there and each part's mean is shown,
its sum then the mean of theirs, adding nothing to what they show. g is shown only where both sexes' means are;
r and the slope are printed with their n and never with a mean of their own persons, so they give no sum to
difference; n and the fill rates are counts, printed whatever their size.

A join run once more prints its blocks beside an earlier report's, and the two would difference into the persons
they do not share, or share with other readings: so every earlier join whose report printed cells is named with
--previous, its joined.csv read back into the persons, sexes, ages and readings to four places that join's
blocks were made of, and a block of this join is withheld wherever the earlier join had persons enough to print
it and the two differ by more than none and fewer than the block's least count, a person counted where one join
has them and the other has not, or has them with another reading: a sex's mean and SD against MIN_CELL, and at
the column the persons with some levels but not all against it as well; r's pairs against MIN_PAIR; the slope's
points, each an age and a reading, against MIN_SLOPE. The derived rule and g are applied again after, and the
report counts what the check withheld. An earlier joined table that cannot be read is a failure said, and every
mean, r and slope is then withheld, n alone printed, since nothing could be checked against it.

One line per (member, measure, level), both sexes on it, at most MAX_CELL_LINES, 822: each member's 26 vertebra
keys at 8 levels and the column (234 lines) and 5 disc keys at 7 disc levels and the column (40); with the fill
rates, the counts and the rules about 25 more, three of the gate's pages, one a send:

    <member> <measure> <level> M <n> <mean> <sd> F <n> <mean> <sd> g <g> <var> r <r M> <n M> <r F> <n F>
        a <slope M> <se M> <n M> <slope F> <se F> <n F>

on one line, where a value not shown is "-" (n is always shown, and the r block is all "-" at T10, T10-T11 and
T10-L5, which have no level above them inside the range); a line where neither sex reaches MIN_CELL is left out
and counted. g is J d with d = (mean M - mean F) / pooled SD and J = 1 - 3 / (4 (n M + n F) - 9); its variance
is J^2 ((n M + n F) / (n M n F) + d^2 / (2 (n M + n F))). The slope and its SE are per ten years. Every line is at
most LINE_CHARS characters, and none holds a path, a `name:value` without a space, a study id, a person key or
one person's value: no single age is printed, and a mean rests on MIN_CELL persons at least.

Everything but the grid check is the standard library, so the join and the arithmetic run where numpy is not;
the grid check reads the CTs' headers with tools/gold3_census.py's reader, which needs numpy, in threads,
since zlib lets go of the interpreter's lock while it inflates and a thread needs nothing pickled. Every failure
the report says is one of FAILURES, beside at most the kind of error that caused it as a plain word, worded with
no quote, slash, dotted name (ENHANCE.PET reads as a file's) or long number, since the gate withholds any reason
after FAILED: that could quote a value (grid/shape-words.awk, grid/report-shapes.awk).
"""

import argparse
import concurrent.futures
import csv
import hashlib
import importlib.util
import io
import json
import math
import os
import re
import sqlite3
import sys
import textwrap
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
RECORDS = ROOT / "data/gold3-ct"
LINE_CHARS = 200

VERTEBRA_KEYS = ("h_ant", "h_mid", "h_post", "h_post_inset", "body_w_mid", "body_d_mid", "endplate", "endplate_depth",
                 "endplate_lower", "endplate_lower_depth", "endplate_area", "endplate_lower_area", "wedge", "canal_w",
                 "canal_ap", "canal_area", "interpedicular", "pedicle_w", "pedicle_h", "pedicle_chord", "pedicle_area",
                 "pedicle_angle_transverse", "pedicle_angle_sagittal", "spinous_length", "transverse_width",
                 "lamina_thickness")
DISC_KEYS = ("disc_h_ant", "disc_h_mid", "disc_h_post", "disc_h_mean", "foramen_h")
VERTEBRA_LEVELS = ("T10", "T11", "T12", "L1", "L2", "L3", "L4", "L5")
DISC_LEVELS = tuple(f"{a}-{b}" for a, b in zip(VERTEBRA_LEVELS, VERTEBRA_LEVELS[1:]))
COLUMN = "T10-L5"
MIN_CELL, MIN_PAIR, MIN_SLOPE = 5, 10, 10
ADULT_AGE, AGE_CEILING = 18.0, 110.0
MEASURED_ON_UNREPAIRED = ("1134", "1283", "1347")
SEXES = ("M", "F")
MEMBERS = ("autopet", "verse", "totalseg")
# A measure that is the mean of others the report prints (bordercall's morphometry/column.py: disc_h_mean is
# the mean of the three disc heights, and none where one is missing).
DERIVED = {"disc_h_mean": ("disc_h_ant", "disc_h_mid", "disc_h_post")}
# bordercall's stand-in for interpedicular where no pedicle was found on both sides (morphometry/canal.py),
# flagged at that vertebra and left out of the tables, which take the reading on the pedicles' walls.
STAND_IN_KEY, STAND_IN_FLAG = "interpedicular", "flag:interpedicular_band"
# bordercall's code stamp, the first sixteen hex digits of the sha256 of its measuring code
# (morphometry/__main__.py, code_stamp), which every study's code row carries.
STAMP = re.compile(r"[0-9a-f]{16}")
MAX_CELL_LINES = len(MEMBERS) * (len(VERTEBRA_KEYS) * (len(VERTEBRA_LEVELS) + 1) + len(DISC_KEYS) * (len(DISC_LEVELS) + 1))
TOTALSEG_META = "Totalsegmentator_dataset_v300/meta.csv"
PETCT = re.compile(r"PETCT_([0-9a-f]+)", re.IGNORECASE)
VERSE_SERIES = re.compile(r"(verse\d+|gl\d+)", re.IGNORECASE)
TOTALSEG_SUBJECT = re.compile(r"s\d{4}")
MALE = {"m", "male", "man", "men", "mann", "maennlich"}
FEMALE = {"f", "w", "female", "woman", "women", "frau", "weiblich"}
# Every failure the report can say, each with at most the kind of error that caused it: plain words the gate
# shows whole, with no quote, slash, dotted name or long number (tests/test_gold3_covariates.py runs each
# through grid/shape-words.awk and grid/report-shapes.awk).
FAILURES = {
    "index_unnamed": "no sample index was named, so autoPET has no sex or age",
    "index_unreadable": "the sample index could not be read ({kind}), so autoPET has no sex or age",
    "autopet_map_unnamed": "no census map of autoPET was named, so autoPET has no person",
    "autopet_map_unreadable": "the census map of autoPET could not be read ({kind}), so autoPET has no person",
    "enhance_rows_missing": "no rows of ENHANCE PET where the morphometry job writes them, so ENHANCE PET has no person",
    "enhance_cts_missing": "no ENHANCE PET CTs on the data root, so the CT off the grid of its mask could not be found "
                           "and left out",
    "verse_rows_missing": "no rows of VerSe where the morphometry job writes them, so VerSe has no person",
    "verse_table_unreadable": "the VerSe demographics table could not be read ({kind}), so VerSe has no sex",
    "verse_table_not_recorded": "the VerSe demographics table is not the one the VerSe series record names by its "
                                "sha256, so VerSe has no sex",
    "verse_table_no_sex_column": "the VerSe demographics table has no one column named sex or gender, so VerSe has no sex",
    "totalseg_rows_missing": "no rows of TotalSegmentator where the morphometry job writes them, so TotalSegmentator "
                             "has no person",
    "totalseg_meta_missing": "no meta table of the TotalSegmentator release under the data root, extracted or zipped, "
                             "so it has no sex or age",
    "totalseg_meta_not_recorded": "the TotalSegmentator meta table is not the one its subjects record names by its "
                                  "sha256, so it has no sex or age",
    "totalseg_meta_columns": "the TotalSegmentator meta table lacks one of its image id, age and gender columns, so it "
                             "has no sex or age",
    "rows_code_unnamed": "a study in the morphometry rows names no measuring code of the plain form, so its rows cannot be "
                         "tied to the engine that measured them",
    "rows_code_mixed": "the morphometry rows were measured by more than one version of the measuring code, within a set or "
                       "between the sets, so the tables blend two engines",
    "previous_unreadable": "the joined table of an earlier join could not be read ({kind}), so every mean, r and slope is "
                           "withheld, none checked against that join",
}
PLAIN_KIND = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,39}")
UNPLAIN_RUN = re.compile(r"[0-9]{5}|[0-9a-fA-F]{8}")


def sibling(name):
    """A tool beside this one, loaded by path: tools/ is no package and never joins sys.path, since
    tools/profile.py would shadow the standard library's profile for anything imported after it."""
    file = TOOLS / f"{name}.py"
    found = sys.modules.get(name)
    if found is not None and getattr(found, "__file__", None) == str(file):
        return found
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_of(data):
    return hashlib.sha256(data).hexdigest()


@dataclass
class Person:
    """One person's chosen study and what is known of them; values maps (level, measure) to the row's value."""

    key: str
    member: str
    part: str
    study: str
    sex: str = ""
    age_read: float = None
    weight: float = None
    height: float = None
    studies: int = 1
    how: str = ""
    values: dict = field(default_factory=dict)

    @property
    def age(self):
        """The age the analysis reads: none above AGE_CEILING, which no person reaches."""
        return self.age_read if self.age_read is not None and self.age_read <= AGE_CEILING else None

    @property
    def child(self):
        return self.age is not None and self.age < ADULT_AGE

    @property
    def tabled(self):
        """Whether the person enters the tables: sex read and no child, a person of unknown age among them."""
        return self.sex in SEXES and not self.child

    @property
    def sloped(self):
        """Whether the person enters the age slope: an adult of known age."""
        return self.age is not None and not self.child


class Report:
    """The report's lines, at most LINE_CHARS each with the job's "- " before them, and its failures first."""

    def __init__(self):
        self.lines, self.failures = [], []

    def say(self, text):
        self.lines.extend(textwrap.wrap(text, width=LINE_CHARS - 2, subsequent_indent="  ") or [""])

    def fail(self, failure, error=None):
        """One of FAILURES, with the kind of the error where it names one: plain words, which the gate shows."""
        text = FAILURES[failure].format(kind=plain_kind(error))
        self.failures.extend(textwrap.wrap("FAILED: " + text, width=LINE_CHARS - 2, subsequent_indent="  "))

    def all_lines(self):
        return self.failures + self.lines


def plain_kind(error):
    """An error's class name where it is a plain word the gate shows whole, else words that stand in for it."""
    name = type(error).__name__ if error is not None else ""
    if PLAIN_KIND.fullmatch(name) and not UNPLAIN_RUN.search(name):
        return name
    return "an error of no plain name"


# ---------------------------------------------------------------- the records and the rows


def admitted(records, member):
    return {s["id"] for s in read_json(Path(records) / "admission.json")["studies"]
            if s["member"] == member and s["verdict"] == "admitted"}


def enhance_facts(records):
    """{id: facts row} of ENHANCE.PET's published masks, the repaired rows left out."""
    return {r["id"]: r for r in read_jsonl(Path(records) / "enhance-pet/facts.jsonl") if "repaired_from" not in r}


def enhance_id(stem):
    return stem.zfill(4) if stem.isdigit() else stem


def verse_id(stem):
    found = VERSE_SERIES.search(stem)
    return found.group(1).lower() if found else stem


def totalseg_id(stem):
    found = TOTALSEG_SUBJECT.search(stem)
    return found.group(0) if found else stem


def number(text):
    """A finite float, or None for a blank, a word or a value that is no number."""
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def wanted(level, key):
    if key in VERTEBRA_KEYS:
        return level in VERTEBRA_LEVELS
    return key in DISC_KEYS and level in DISC_LEVELS


@dataclass
class Rows:
    """One rows file: {study: {(level, measure): value}} over the vocabulary's measures and levels, every study
    it names, {study: the code stamps its code rows name}, and the (study, level) whose interpedicular was the
    flagged stand-in and is left out of values."""

    values: dict
    seen: set
    codes: dict
    stand_ins: set


def read_rows(path, study_id):
    """A rows file as grid/morphometry.sbatch writes it, read whole: the flag rows come after a vertebra's
    values, so the stand-ins are taken out once every row is read."""
    values, seen, codes, flagged = defaultdict(dict), set(), defaultdict(set), set()
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            study = study_id(row.get("study") or "")
            seen.add(study)
            key, level = row.get("key") or "", row.get("level") or ""
            if key == "code" and level == "study":
                codes[study].add((row.get("note") or "").strip())
            elif key == STAND_IN_FLAG:
                flagged.add((study, level))
            value = number(row.get("value"))
            if value is not None and wanted(level, key):
                values[study].setdefault((level, key), value)
    stand_ins = set()
    for study, level in flagged:
        if values.get(study, {}).pop((level, STAND_IN_KEY), None) is not None:
            stand_ins.add((study, level))
    return Rows(dict(values), seen, dict(codes), stand_ins)


def code_line(codes, report):
    """The report's line naming the code that measured the rows, from {label: {study: stamps}}: a study that
    names no stamp of the plain form, and more than one stamp within a file or between the files, are failures
    said, and only stamps of the plain form are printed."""
    found, unnamed = {}, False
    for label, studies in codes.items():
        found[label] = set()
        for named in studies.values():
            plain = {stamp for stamp in named if STAMP.fullmatch(stamp)}
            unnamed = unnamed or not plain or plain != named
            found[label] |= plain
    if unnamed:
        report.fail("rows_code_unnamed")
    every = set().union(*found.values())
    if len(every) > 1:
        report.fail("rows_code_mixed")
    if len(every) == 1:
        where = "where the rows name one" if unnamed else "for every set's rows"
        return f"rows: measuring code {min(every)} {where}"
    if every:
        return "rows: measuring code by set, " + "; ".join(f"{label} {' '.join(sorted(stamps)) or 'none named'}"
                                                         for label, stamps in found.items())
    return "rows: no measuring code named in any rows file"


# ---------------------------------------------------------------- the grid check: a CT off its mask's grid


def off_grid_studies(data, facts, workers):
    """(ids whose CT is off its mask's grid or unreadable, a tally), as the census's held part reads them."""
    import numpy as np
    census = sibling("gold3_census")
    root = Path(data) / "aws_enhance_pet_ct/raw"
    if not root.is_dir():
        return None, Counter()
    files = census.walk_files(root, lambda name: name.endswith(".nii.gz") and name[:-7] in facts)
    paths = {name[:-7]: sorted(found)[0] for name, found in files.items()}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        heads = dict(zip(paths, ex.map(census.ct_grid, paths.values())))
    off, tally = set(), Counter(read=len(paths), missing=len(facts) - len(paths))
    for sid, head in heads.items():
        mask = facts[sid]["mask"]
        same = "error" not in head and head["shape"] == mask["shape"] and np.allclose(head["affine"], mask["affine"], atol=2e-6)
        if not same:
            off.add(sid)
    tally["off"] = len(off)
    return off, tally


# ---------------------------------------------------------------- autoPET: persons, the sample index, one study a person


def petct_key(text):
    found = PETCT.search(text or "")
    return "PETCT_" + found.group(1).lower() if found else None


def study_folder(path, key):
    """The folder after the person's own in a path, the study a TCIA download keeps its series in, normalised."""
    parts = [p for p in re.split(r"[\\/]", path or "") if p]
    for index, part in enumerate(parts[:-1]):
        if petct_key(part) == key and PETCT.fullmatch(part):
            return " ".join(parts[index + 1].lower().split())
    return None


def sex_of(text):
    word = (text or "").strip().lower()
    return "M" if word in MALE else "F" if word in FEMALE else ""


def index_series(index, keys):
    """{person key: [series]} from the sample index's first file of each DICOM series, with weight and height."""
    db = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
    try:
        rows = db.execute("SELECT id, path, patient_id, patient_sex, age_years, modality FROM file "
                          "WHERE format = 'dicom' AND header_full = 1 "
                          "AND (patient_id LIKE '%PETCT%' OR path LIKE '%PETCT%')").fetchall()
        found = defaultdict(list)
        for file_id, path, patient, sex, age, modality in rows:
            key = petct_key(patient) or petct_key(path)
            if key in keys:
                found[key].append({"id": file_id, "folder": study_folder(path, key), "sex": sex_of(sex),
                                   "age": number(age), "modality": (modality or "").upper()})
        try:
            add_body_size(db, [s for series in found.values() for s in series])
        except sqlite3.Error:
            pass  # weight and height are kept in the per-person table only; sex and age stand without them
    finally:
        db.close()
    return found


def add_body_size(db, series):
    """Each series' weight in kg and height in m, from its header's elements, where the index holds them."""
    by_id = {s["id"]: s for s in series}
    ids = sorted(by_id)
    for start in range(0, len(ids), 500):
        chunk = ids[start:start + 500]
        marks = ",".join("?" * len(chunk))
        for file_id, keyword, value in db.execute(
                f"SELECT file_id, keyword, value FROM dicom WHERE keyword IN ('PatientWeight', 'PatientSize') "
                f"AND file_id IN ({marks})", chunk):
            by_id[file_id]["weight" if keyword == "PatientWeight" else "height"] = number(value)


def one_value(values):
    """The one value a set of readings agrees on, or None where they are none or disagree."""
    distinct = {v for v in values if v is not None}
    return distinct.pop() if len(distinct) == 1 else None


def person_sex(series, tally):
    sexes = {s["sex"] for s in series if s["sex"]}
    if len(sexes) > 1:
        tally["sex conflicting"] += 1
    return sexes.pop() if len(sexes) == 1 else ""


def study_reading(series, folder, tally):
    """(age, weight, height, how) of one study: its own folder's series, the CTs first, else the person's only study."""
    own = [s for s in series if folder and s["folder"] == folder]
    how = "its own folder"
    if not own:
        folders = {s["folder"] for s in series}
        own, how = (series, "the only study") if len(folders) == 1 else ([], "not found")
    ct = [s for s in own if s["modality"] == "CT"] or own
    age = one_value(s["age"] for s in ct)
    if age is None and len({s["age"] for s in ct if s["age"] is not None}) > 1:
        tally["age conflicting within a study"] += 1
    return age, one_value(s.get("weight") for s in ct), one_value(s.get("height") for s in ct), how


def first_study(candidates):
    """The person's first study: the youngest age read, the lowest id breaking a tie or standing in for no age."""
    return min(candidates, key=lambda c: (c["age"] is None, c["age"] if c["age"] is not None else 0.0, c["id"]))


def autopet_persons(studies, matches, index, report, tally):
    """Persons of the autoPET studies with rows, one study each, sex and age from the index."""
    by_key = defaultdict(list)
    for sid in sorted(studies):
        match = matches.get(sid) or {}
        key = match.get("person") or petct_key(match.get("case")) or petct_key(match.get("ct"))
        if key:
            by_key[key].append({"id": sid, "where": match.get("ct") or match.get("case") or ""})
        else:
            tally["no PETCT key"] += 1
    series = {}
    if index:
        try:
            series = index_series(index, set(by_key))
        except sqlite3.Error as error:
            report.fail("index_unreadable", error)
    tally["persons with no series in the index"] = sum(1 for key in by_key if not series.get(key))
    tally["series in the index"] = sum(len(series.get(key, [])) for key in by_key)
    return [autopet_person(key, by_key[key], series.get(key, []), studies, tally) for key in sorted(by_key)]


def autopet_person(key, candidates, series, studies, tally):
    for candidate in candidates:
        candidate["age"], candidate["weight"], candidate["height"], candidate["how"] = \
            study_reading(series, study_folder(candidate["where"], key), tally)
    chosen = first_study(candidates)
    tally[f"age from {chosen['how']}"] += 1
    if len(candidates) > 1:
        tally["persons with more than one study"] += 1
    return Person(key=key, member="autopet", part="autoPET", study=chosen["id"], sex=person_sex(series, tally),
                  age_read=chosen["age"], weight=chosen["weight"], height=chosen["height"], studies=len(candidates),
                  how=chosen["how"], values=studies[chosen["id"]])


# ---------------------------------------------------------------- VerSe and TotalSegmentator's tables


def table_rows(data, delimiter=None):
    """(header, rows) of a small table's text, the delimiter the header splits widest on where none is given."""
    text = data.decode("utf-8-sig", errors="replace")
    first = text.splitlines()[0] if text.strip() else ""
    delimiter = delimiter or max((",", ";", "\t"), key=first.count)
    rows = [r for r in csv.reader(io.StringIO(text), delimiter=delimiter) if any(c.strip() for c in r)]
    return ([c.strip() for c in rows[0]], rows[1:]) if rows else ([], [])


def sex_column(header):
    """The index of the one column named sex or gender, whole or as a word of its name, or None."""
    names = [h.strip().lower() for h in header]
    for test in (lambda n: n in ("sex", "gender"), lambda n: re.search(r"\b(sex|gender)\b", n)):
        found = [i for i, n in enumerate(names) if test(n)]
        if len(found) == 1:
            return found[0]
        if found:
            return None
    return None


def verse_sexes(path, records, report):
    """{patient or series key: sex} from VerSeFusion's demographics table, or {} with the failure said."""
    recorded = read_json(Path(records) / "verse/series.json")["source"]["sha256"]
    try:
        data = Path(path).read_bytes()
    except OSError as error:
        report.fail("verse_table_unreadable", error)
        return {}
    if sha256_of(data) != recorded:
        report.fail("verse_table_not_recorded")
        return {}
    header, rows = table_rows(data)
    column = sex_column(header)
    if column is None:
        report.fail("verse_table_no_sex_column")
        return {}
    found = defaultdict(set)
    for row in rows:
        sex = sex_of(row[column] if column < len(row) else "")
        # the person and the series by their cells as written and by the VerSe id inside them, since a
        # BIDS name such as sub-verse004 names the series.json key verse004
        for cell in (c.strip() for c in row[:2]):
            for key in {cell.lower(), verse_id(cell).lower()} if cell else ():
                found[key].add(sex)
    return {key: (sexes.pop() if len(sexes) == 1 else "") for key, sexes in found.items()}


def verse_persons(studies, records, sexes, tally):
    """Persons of the admitted VerSe series with rows, one series each, by series.json's patient."""
    listed = {s["series"]: s for s in read_json(Path(records) / "verse/series.json")["series"]}
    by_patient = defaultdict(list)
    for sid in sorted(studies):
        entry = listed.get(sid)
        if entry is None:
            tally["series not in series.json"] += 1
            continue
        by_patient[entry["patient"]].append({"id": sid, "age": number(entry.get("age"))})
    persons = []
    for patient in sorted(by_patient):
        chosen = first_study(by_patient[patient])
        sex = sexes.get(chosen["id"].lower()) or sexes.get(patient.lower()) or ""
        persons.append(Person(key=f"verse:{patient}", member="verse", part="verse", study=chosen["id"], sex=sex,
                              age_read=chosen["age"], studies=len(by_patient[patient]), values=studies[chosen["id"]]))
    return persons


def totalseg_meta(data, records, report):
    """{subject: (sex, age)} from the release's meta.csv, extracted or in its zip, or {} with the failure said."""
    recorded = read_json(Path(records) / "totalsegmentator/subjects.json")["source"]["sha256"]
    root = Path(data) / "totalsegmentator_v300"
    found = meta_bytes(root)
    if found is None:
        report.fail("totalseg_meta_missing")
        return {}
    if sha256_of(found) != recorded:
        report.fail("totalseg_meta_not_recorded")
        return {}
    header, rows = table_rows(found, ";")
    names = [h.lower() for h in header]
    if not {"image_id", "age", "gender"} <= set(names):
        report.fail("totalseg_meta_columns")
        return {}
    at = {name: names.index(name) for name in ("image_id", "age", "gender")}
    return {row[at["image_id"]].strip(): (sex_of(row[at["gender"]]), number(row[at["age"]]))
            for row in rows if len(row) > max(at.values())}


def meta_bytes(root):
    """The bytes of the release's meta.csv: the extracted file where one is there, else the zip's member."""
    if not root.is_dir():
        return None
    for folder, _, names in os.walk(root):
        if "meta.csv" in names and Path(folder).name == "Totalsegmentator_dataset_v300":
            return (Path(folder) / "meta.csv").read_bytes()
    for folder, _, names in os.walk(root):
        for name in sorted(n for n in names if n.endswith(".zip")):
            try:
                with zipfile.ZipFile(Path(folder) / name) as archive:
                    if TOTALSEG_META in archive.namelist():
                        return archive.read(TOTALSEG_META)
            except (OSError, zipfile.BadZipFile):
                continue
    return None


def totalseg_persons(studies, meta):
    persons = []
    for sid in sorted(studies):
        sex, age = meta.get(sid, ("", None))
        persons.append(Person(key=f"totalsegmentator:{sid}", member="totalseg", part="totalseg", study=sid, sex=sex,
                              age_read=age, values=studies[sid]))
    return persons


def site_persons(studies, sites, site):
    """Leipzig's or Careggi's studies, each its own person with no sex or age, as the records say."""
    return [Person(key=f"enhance_pet:{sid}", member="enhance_pet", part=site, study=sid, values=studies[sid])
            for sid in sorted(studies) if sites.get(sid) == site]


# ---------------------------------------------------------------- the arithmetic


def mean_sd(values):
    """(n, mean, sample SD) of a list; mean None for none, SD None for fewer than two."""
    n = len(values)
    if not n:
        return 0, None, None
    mean = sum(values) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1)) if n > 1 else None
    return n, mean, sd


def hedges_g(men, women):
    """(g, its variance), men minus women, from two (n, mean, sd), or (None, None) where either is too small."""
    (n1, m1, s1), (n2, m2, s2) = men, women
    if n1 < MIN_CELL or n2 < MIN_CELL or s1 is None or s2 is None:
        return None, None
    pooled = math.sqrt(((n1 - 1) * s1 ** 2 + (n2 - 1) * s2 ** 2) / (n1 + n2 - 2))
    if pooled == 0:
        return None, None
    d = (m1 - m2) / pooled
    j = 1 - 3 / (4 * (n1 + n2) - 9)
    return j * d, j ** 2 * ((n1 + n2) / (n1 * n2) + d ** 2 / (2 * (n1 + n2)))


def pearson(pairs):
    """(r, n) of (x, y) pairs, r None below MIN_PAIR or where either side does not vary."""
    n = len(pairs)
    if n < MIN_PAIR:
        return None, n
    mx, my = sum(x for x, _ in pairs) / n, sum(y for _, y in pairs) / n
    sxy = sum((x - mx) * (y - my) for x, y in pairs)
    sxx, syy = sum((x - mx) ** 2 for x, _ in pairs), sum((y - my) ** 2 for _, y in pairs)
    return (sxy / math.sqrt(sxx * syy), n) if sxx > 0 and syy > 0 else (None, n)


def age_slope(points):
    """(slope per decade, its SE, n) of (age, value) points by least squares, the slope None below MIN_SLOPE."""
    n = len(points)
    if n < MIN_SLOPE:
        return None, None, n
    xs = [age / 10.0 for age, _ in points]
    mx, my = sum(xs) / n, sum(v for _, v in points) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None, None, n
    slope = sum((x - mx) * (v - my) for x, (_, v) in zip(xs, points)) / sxx
    residual = sum((v - my - slope * (x - mx)) ** 2 for x, (_, v) in zip(xs, points))
    return slope, math.sqrt(residual / (n - 2) / sxx), n


# ---------------------------------------------------------------- the cells and the lines


def levels_of(key):
    return VERTEBRA_LEVELS if key in VERTEBRA_KEYS else DISC_LEVELS


def value_at(person, key, level):
    """A person's value of a measure at a level, or at COLUMN the mean over every level of the range they all have."""
    if level != COLUMN:
        return person.values.get((level, key))
    values = [person.values.get((lv, key)) for lv in levels_of(key)]
    return sum(values) / len(values) if all(v is not None for v in values) else None


def partial_persons(persons, key):
    """How many of the persons have the measure at some of its levels but not at all of them."""
    counts = (sum((lv, key) in p.values for lv in levels_of(key)) for p in persons)
    return sum(1 for have in counts if 0 < have < len(levels_of(key)))


def mean_shown(n, level, partial):
    """Whether a sex's mean and SD are printed: MIN_CELL persons at least, and at COLUMN only where the persons
    with some levels but not all, whose sum the level lines less the column's would give, number none or
    MIN_CELL at least."""
    return n >= MIN_CELL and (level != COLUMN or partial == 0 or partial >= MIN_CELL)


def level_above(key, level):
    levels = levels_of(key)
    return levels[levels.index(level) - 1] if level in levels and levels.index(level) > 0 else None


def cell(persons, key, level):
    """Every number of one (measure, level) over persons already in the table, by sex."""
    out, above = {}, level_above(key, level)
    for sex in SEXES:
        own = [p for p in persons if p.sex == sex]
        values = [v for v in (value_at(p, key, level) for p in own) if v is not None]
        pairs = [(p.values[(above, key)], p.values[(level, key)]) for p in own
                 if above and (above, key) in p.values and (level, key) in p.values]
        points = [(p.age, value_at(p, key, level)) for p in own if p.sloped and value_at(p, key, level) is not None]
        partial = partial_persons(own, key) if level == COLUMN else 0
        summary = mean_sd(values)
        out[sex] = {"summary": summary, "shown": mean_shown(summary[0], level, partial), "partial": partial,
                    "persons": frozenset(p.key for p in own if value_at(p, key, level) is not None),
                    "r": pearson(pairs) if above else None, "slope": age_slope(points)}
    out["g"] = g_of(out)
    return out


def g_of(numbers):
    """Hedges' g of a cell where both sexes' means are shown, else none."""
    if not (numbers["M"]["shown"] and numbers["F"]["shown"]):
        return None, None
    return hedges_g(numbers["M"]["summary"], numbers["F"]["summary"])


def withhold_derived(cells, whole, parts, level):
    """A measure that is the mean of others printed beside it is shown, by sex, only where its persons are each
    part's at the same place and each part's mean is shown, so that its sum is the mean of theirs and the four
    lines difference into nothing."""
    numbers = cells[(whole, level)]
    for sex in SEXES:
        own = numbers[sex]
        if not all(cells[(part, level)][sex]["shown"] and cells[(part, level)][sex]["persons"] == own["persons"]
                   for part in parts):
            own["shown"] = False
    numbers["g"] = g_of(numbers)


def texts_of(persons):
    """{id of a person: {(level, measure): the reading to four places}}, as the joined table writes it."""
    return {id(p): {place: f"{value:.4f}" for place, value in p.values.items()} for p in persons}


def block_readings(persons, texts, key, level, sex):
    """{kind: {person: reading}} behind one sex's block: the persons of its mean, at the column those with some
    levels but not all (partial), r's pairs and the slope's points, each reading as the joined table writes it and
    a point's age too, so that two joins' blocks are set side by side as their tables hold them."""
    out = {"mean": {}, "partial": {}, "r": {}, "slope": {}}
    above = level_above(key, level)
    for p in persons:
        if p.sex != sex:
            continue
        text = texts[id(p)]
        if level == COLUMN:
            have = tuple(text.get((lv, key)) for lv in levels_of(key))
            reading = have if all(have) else None
            if reading is None and any(have):
                out["partial"][p.key] = have
        else:
            reading = text.get((level, key))
        if reading is not None:
            out["mean"][p.key] = reading
            if p.sloped:
                out["slope"][p.key] = (blank(p.age), reading)
        if above and (above, key) in text and (level, key) in text:
            out["r"][p.key] = (text[(above, key)], text[(level, key)])
    return out


def differing(ours, theirs):
    """How many persons one block's readings have that the other's have not, or have with another reading."""
    return len(ours.keys() ^ theirs.keys()) + sum(1 for k in ours.keys() & theirs.keys() if ours[k] != theirs[k])


def few(ours, theirs, least):
    """Whether two blocks differ by more than none and fewer than least persons, so their sums difference into
    those few persons' readings."""
    return 0 < differing(ours, theirs) < least


def withhold_across(cells, persons, before, withheld):
    """This join's blocks withheld where an earlier join's persons, before, had persons enough to print the same
    block and the two differ by 1 to its least count less one; a block the earlier join had fewer for was never
    printed, so it differences into nothing. withheld counts, by kind, what is taken."""
    ours, theirs = texts_of(persons), texts_of(before)
    for (key, level), numbers in cells.items():
        for sex in SEXES:
            now = block_readings(persons, ours, key, level, sex)
            then = block_readings(before, theirs, key, level, sex)
            own = numbers[sex]
            if own["shown"] and len(then["mean"]) >= MIN_CELL and (
                    few(now["mean"], then["mean"], MIN_CELL) or few(now["partial"], then["partial"], MIN_CELL)):
                own["shown"] = False
                withheld["means"] += 1
            if own["r"] and own["r"][0] is not None and len(then["r"]) >= MIN_PAIR and few(now["r"], then["r"], MIN_PAIR):
                own["r"] = (None, own["r"][1])
                withheld["r"] += 1
            if own["slope"][0] is not None and len(then["slope"]) >= MIN_SLOPE and few(now["slope"], then["slope"], MIN_SLOPE):
                own["slope"] = (None, None, own["slope"][2])
                withheld["slopes"] += 1


def blind(numbers):
    """A block with every mean, r and slope withheld, its n alone printed: what is left where an earlier join's
    table could not be read, so nothing of this join could be checked against it."""
    for sex in SEXES:
        own = numbers[sex]
        own["shown"] = False
        own["r"] = (None, own["r"][1]) if own["r"] else None
        own["slope"] = (None, None, own["slope"][2])
    numbers["g"] = (None, None)


def figure(value, digits=4):
    """A number in about digits significant figures, never in exponent form; "-" for none."""
    if value is None:
        return "-"
    if value == 0:
        return "0"
    places = max(0, min(6, digits - 1 - math.floor(math.log10(abs(value)))))
    return f"{value:.{places}f}"


def cell_line(member, key, level, numbers):
    """The report's one line of a cell, or None where neither sex reaches MIN_CELL."""
    if all(numbers[sex]["summary"][0] < MIN_CELL for sex in SEXES):
        return None
    parts = [member, key, level]
    for sex in SEXES:
        n, mean, sd = numbers[sex]["summary"]
        shown = numbers[sex]["shown"]
        parts += [sex, str(n), figure(mean if shown else None), figure(sd if shown else None)]
    g, var = numbers["g"]
    parts += ["g", "-" if g is None else f"{g:.3f}", figure(var, 3)]
    parts.append("r")
    for sex in SEXES:
        found = numbers[sex]["r"]
        parts += ["-", "-"] if found is None else ["-" if found[0] is None else f"{found[0]:.3f}", str(found[1])]
    parts.append("a")
    for sex in SEXES:
        slope, se, n = numbers[sex]["slope"]
        parts += [figure(slope), figure(se), str(n)]
    return " ".join(parts)


def cells_of(persons, earlier=(), withheld=None):
    """[(key, level, numbers)] over every measure of the vocabulary, its levels and its column: a block withheld
    where it and an earlier join's could be differenced (earlier, each earlier join's persons of the same
    member; withheld counts what that takes), then a derived measure's means where its lines and its parts'
    could be, and g wherever a sex's mean is no longer shown."""
    cells = {}
    for keys, levels in ((VERTEBRA_KEYS, VERTEBRA_LEVELS), (DISC_KEYS, DISC_LEVELS)):
        for key in keys:
            for level in (*levels, COLUMN):
                cells[(key, level)] = cell(persons, key, level)
    for before in earlier:
        withhold_across(cells, persons, before, Counter() if withheld is None else withheld)
    for whole, parts in DERIVED.items():
        for level in (*levels_of(whole), COLUMN):
            withhold_derived(cells, whole, parts, level)
    for numbers in cells.values():
        numbers["g"] = g_of(numbers)
    return [(key, level, numbers) for (key, level), numbers in cells.items()]


def table_members(persons):
    """[(member, persons in its tables)], each member apart: no table pools them, so that no member's mean can be
    taken from a pooled one to leave another's few persons (the pooling is done later, from the member lines)."""
    tabled = [p for p in persons if p.member in MEMBERS and p.tabled]
    return [(member, [p for p in tabled if p.member == member]) for member in MEMBERS]


# ---------------------------------------------------------------- the fill rates


def share(part, whole):
    return f"{part} ({100.0 * part / whole:.1f} %)" if whole else f"{part}"


def fill_line(label, persons, studies):
    """How many of a part's persons carry sex and age, how many of those are adults, children or too old, and
    how many enter the tables, those of unknown age counted apart."""
    total = len(persons)
    sexed = Counter(p.sex for p in persons if p.sex in SEXES)
    aged = [p for p in persons if p.age is not None]
    tabled = [p for p in persons if p.tabled and p.member in MEMBERS]
    return (f"fill {label}: persons {total} of {studies} studies; sex {share(sum(sexed.values()), total)}, "
            f"M {sexed['M']}, F {sexed['F']}; age {share(len(aged), total)}, adults {sum(1 for p in aged if not p.child)}, "
            f"under {ADULT_AGE:.0f} {sum(1 for p in aged if p.child)} in no table, above {AGE_CEILING:.0f} read as unknown "
            f"{sum(1 for p in persons if p.age_read is not None and p.age is None)}; in the tables {len(tabled)}, "
            f"of unknown age {sum(1 for p in tabled if p.age is None)}")


def autopet_lines(persons, tally):
    with_weight = sum(1 for p in persons if p.weight is not None)
    with_height = sum(1 for p in persons if p.height is not None)
    return [f"autoPET index: series of these persons {tally['series in the index']}; persons with none "
            f"{tally['persons with no series in the index']}; sex conflicting between series {tally['sex conflicting']}; "
            f"age conflicting within a study {tally['age conflicting within a study']}; the chosen study's age from its own "
            f"folder {tally['age from its own folder']}, from the only study the index holds {tally['age from the only study']}, "
            f"study not found {tally['age from not found']}; weight read {share(with_weight, len(persons))}, height read "
            f"{share(with_height, len(persons))}",
            f"autoPET one study a person: persons with more than one admitted study {tally['persons with more than one study']}, "
            f"each taking its first, the youngest age read, the lowest ENHANCE.PET id breaking a tie or standing in where "
            f"no age is read; studies with no PETCT key in the census map {tally['no PETCT key']}, which enter no table"]


# ---------------------------------------------------------------- writing


def write_persons(out, persons):
    """persons.csv, one row a person, and joined.csv, one row a (person, level, measure): they stay on the grid."""
    out = Path(out)
    with open(out / "persons.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["person", "member", "part", "study", "studies", "sex", "age_read", "age", "child",
                         "tabled", "weight_kg", "height_m", "how"])
        for p in persons:
            writer.writerow([p.key, p.member, p.part, p.study, p.studies, p.sex, blank(p.age_read), blank(p.age),
                             int(p.child), int(p.tabled), blank(p.weight), blank(p.height), p.how])
    with open(out / "joined.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["person", "member", "part", "study", "sex", "age", "level", "key", "value"])
        for p in persons:
            for (level, key), value in sorted(p.values.items()):
                writer.writerow([p.key, p.member, p.part, p.study, p.sex, blank(p.age), level, key, f"{value:.4f}"])


def blank(value):
    return "" if value is None else f"{value:g}"


def summary_of(member, key, level, numbers):
    """One cell as the JSON the job keeps beside the report: aggregates only."""
    out = {"member": member, "key": key, "level": level, "g": list(numbers["g"])}
    for sex in SEXES:
        n, mean, sd = numbers[sex]["summary"]
        shown = numbers[sex]["shown"]
        out[sex] = {"n": n, "mean": mean if shown else None, "sd": sd if shown else None, "partial": numbers[sex]["partial"],
                    "r": list(numbers[sex]["r"]) if numbers[sex]["r"] else None, "slope": list(numbers[sex]["slope"])}
    return out


# ---------------------------------------------------------------- the run


def member_studies(path, study_id, allowed, report, label, tally, missing, codes):
    """The admitted studies of one rows file with their values, and the counts of what it held and left;
    missing names the failure said where the file is not there, and codes takes every study's code stamps
    under the file's label, since the whole file is one run's."""
    if not Path(path).is_file():
        report.fail(missing)
        return {}
    rows = read_rows(path, study_id)
    kept = {sid: rows.values.get(sid, {}) for sid in rows.seen if sid in allowed}
    tally[f"{label} studies in the rows"] = len(rows.seen)
    tally[f"{label} studies not admitted"] = len(rows.seen - allowed)
    tally[f"{label} interpedicular stand-ins left out"] = sum(1 for sid, _ in rows.stand_ins if sid in allowed)
    codes[label] = {sid: rows.codes.get(sid, set()) for sid in rows.seen}
    return kept


def enhance_studies(args, report, tally, off_grid, codes):
    """ENHANCE.PET's admitted studies with rows, less those measured on unrepaired masks and those off their grid."""
    allowed = admitted(args.records, "enhance_pet")
    studies = member_studies(Path(args.morphometry) / "enhance/rows.csv", enhance_id, allowed, report, "ENHANCE.PET", tally,
                             "enhance_rows_missing", codes)
    facts = enhance_facts(args.records)
    off, grid = off_grid(args.data, facts, args.workers)
    if off is None:
        report.fail("enhance_cts_missing")
        off = set()
    report.say(f"ENHANCE.PET grid check: CTs read {grid['read']}, not found {grid['missing']}, off their mask's grid "
               f"or unreadable {grid['off']}")
    dropped = (set(MEASURED_ON_UNREPAIRED) | off) & set(studies)
    tally["ENHANCE.PET left out"] = len(dropped)
    return {sid: v for sid, v in studies.items() if sid not in dropped}, {sid: facts[sid].get("site", "") for sid in facts}


def autopet_matches(path, report):
    """{ENHANCE.PET study: the census's match} from its autopet.json, or {} with the failure said."""
    if not path:
        report.fail("autopet_map_unnamed")
        return {}
    try:
        return read_json(path).get("matches", {})
    except (OSError, ValueError, AttributeError) as error:
        report.fail("autopet_map_unreadable", error)
        return {}


def gather(args, report, off_grid):
    """Every person of the three members, the counts of how they were found, and the autoPET tally; the code
    that measured the rows is said first."""
    tally, auto, codes = Counter(), Counter(), {}
    enhance, sites = enhance_studies(args, report, tally, off_grid, codes)
    autopet = {sid: v for sid, v in enhance.items() if sites.get(sid) == "autoPET"}
    matches = autopet_matches(args.autopet, report)
    if not args.index:
        report.fail("index_unnamed")
    persons = autopet_persons(autopet, matches, args.index, report, auto)
    persons += site_persons(enhance, sites, "Leipzig") + site_persons(enhance, sites, "Careggi")
    verse = member_studies(Path(args.morphometry) / "verse/rows.csv", verse_id, admitted(args.records, "verse"),
                           report, "VerSe", tally, "verse_rows_missing", codes)
    persons += verse_persons(verse, args.records, verse_sexes(args.verse_demographics, args.records, report), tally)
    totalseg = member_studies(Path(args.morphometry) / "verse/totalseg/rows.csv", totalseg_id,
                              admitted(args.records, "totalsegmentator"), report, "TotalSegmentator", tally,
                              "totalseg_rows_missing", codes)
    persons += totalseg_persons(totalseg, totalseg_meta(args.data, args.records, report))
    report.say(code_line(codes, report))
    counts = {"autoPET": len(autopet), "Leipzig": sum(1 for s in enhance if sites.get(s) == "Leipzig"),
              "Careggi": sum(1 for s in enhance if sites.get(s) == "Careggi"), "verse": len(verse), "totalseg": len(totalseg)}
    return persons, tally, auto, counts


def earlier_persons(folder):
    """The persons an earlier join's blocks were made of, rebuilt from the joined table it kept in its job
    folder: each with the sex, the age and the readings to four places it wrote."""
    persons = {}
    with open(Path(folder) / "joined.csv", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            person = persons.get(row["person"])
            if person is None:
                person = persons[row["person"]] = Person(key=row["person"], member=row["member"], part=row["part"],
                                                         study=row["study"], sex=row["sex"], age_read=number(row["age"]))
            value = number(row["value"])
            if value is not None:
                person.values[(row["level"], row["key"])] = value
    return list(persons.values())


def earlier_joins(folders, report):
    """Each earlier join's persons, and whether the joined table of any could not be read, a failure said."""
    joins, unread = [], False
    for folder in folders:
        try:
            joins.append(earlier_persons(folder))
        except (OSError, KeyError, ValueError, csv.Error) as error:
            report.fail("previous_unreadable", error)
            unread = True
    return joins, unread


def across_line(joins, withheld, unread):
    """What the check across reports read and, by member, what it withheld."""
    counts = "; ".join(f"{member} means {taken['means']}, r {taken['r']}, slopes {taken['slopes']}"
                       for member, taken in withheld.items())
    blinded = ", and a joined table not read, so every mean, r and slope withheld" if unread else ""
    return (f"across reports: {joins} earlier joins read{blinded}; a block withheld where an earlier join had persons "
            f"enough to print it and the two differ by 1 to {MIN_CELL - 1} persons or readings for a mean and SD, "
            f"1 to {MIN_PAIR - 1} for r and 1 to {MIN_SLOPE - 1} for a slope; withheld {counts}")


def run(args, off_grid=off_grid_studies):
    """The join, the per-person table under args.out and the report's lines; 0, or 3 where a failure was said."""
    report = Report()
    persons, tally, auto, counts = gather(args, report, off_grid)
    previous = getattr(args, "previous", None) or []
    joins, unread = earlier_joins(previous, report)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_persons(out, persons)
    report.say("rows: " + ", ".join(f"{k} {v}" for k, v in sorted(tally.items())))
    for part in ("autoPET", "Leipzig", "Careggi", "verse", "totalseg"):
        label = f"enhance_pet {part}" if part in ("autoPET", "Leipzig", "Careggi") else part
        report.say(fill_line(label, [p for p in persons if p.part == part], counts[part]))
    for line in autopet_lines([p for p in persons if p.part == "autoPET"], auto):
        report.say(line)
    report.say(f"rule: the tables are of adults, a person under {ADULT_AGE:.0f} in none and one of unknown age in all but the "
               f"slope; each line one member and each block one sex, none pooled; mean and SD where a sex has {MIN_CELL} or "
               f"more; g where both means are shown; r with the level above where {MIN_PAIR} or more of a sex have both; "
               f"a, the slope per decade of age within sex, over adults of known age alone where {MIN_SLOPE} or more; "
               f"{COLUMN} is each person's mean over every level of the range, where the person has all of them, its mean "
               f"and SD shown only where the persons of that sex with some levels but not all number none or {MIN_CELL} "
               f"or more; {', '.join(DERIVED)}, the mean of {', '.join(p for parts in DERIVED.values() for p in parts)}, "
               "shown only where its persons are each of theirs and their means are shown; TotalSegmentator's ages "
               "carry the release's jitter of up to four years; interpedicular is left out where the rows flag the "
               "hole's width standing in for the reading on the pedicles' walls")
    report.say("line: member measure level M n mean sd F n mean sd g g var r rM nM rF nF a slopeM seM nM slopeF seF nF; "
               "- where not shown")
    tables, withheld = [], {}
    for member, tabled in table_members(persons):
        withheld[member] = Counter()
        before = [dict(table_members(join))[member] for join in joins]
        tables.append((member, tabled, cells_of(tabled, before, withheld[member])))
    if previous:
        report.say(across_line(len(joins), withheld, unread))
    cells = []
    for member, tabled, listed in tables:
        written = left = 0
        for key, level, numbers in listed:
            if unread:
                blind(numbers)
            line = cell_line(member, key, level, numbers)
            cells.append(summary_of(member, key, level, numbers))
            if line is None:
                left += 1
                continue
            report.lines.append(line)
            written += 1
        report.say(f"member {member}: persons {len(tabled)}, lines {written}, left out {left} where neither sex reached {MIN_CELL}")
    (out / "summary.json").write_text(json.dumps({"cells": cells, "counts": counts, "rows": dict(tally),
                                                  "autopet": dict(auto)}, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    lines = report.all_lines()
    (out / "report.lines").write_text("".join(line + "\n" for line in lines), encoding="ascii", errors="replace")
    return 3 if report.failures else 0


def parse(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--morphometry", required=True, help="the morphometry root, which holds enhance/ and verse/")
    parser.add_argument("--autopet", default="", help="the census's autopet.json, its map of autoPET's studies to PETCT keys")
    parser.add_argument("--index", default="", help="the sample index, samples.sqlite")
    parser.add_argument("--verse-demographics", required=True, help="VerSeFusion's demographics table on the grid")
    parser.add_argument("--data", required=True, help="the data root")
    parser.add_argument("--out", required=True, help="the job's folder, mode 0700")
    parser.add_argument("--records", default=str(RECORDS), help="the gold 3 records, data/gold3-ct")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    parser.add_argument("--previous", action="append", default=[],
                        help="an earlier join's job folder, whose joined.csv this join's blocks are checked against; once for each")
    return parser.parse_args(argv)


def main(argv=None):
    rc = run(parse(argv))
    return rc


if __name__ == "__main__":
    sys.exit(main())
