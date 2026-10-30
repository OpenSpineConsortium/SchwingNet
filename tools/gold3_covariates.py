"""The gold tier 3 morphometry beside each person's sex and age: one CPU job on the grid that joins the rows
the word `morphometry <set>` measured with the persons they belong to, and writes the aggregates a sex and age
analysis starts from.

Source: the thread "Extract morphometrics from gold tier 3 CT", 2026-10-30: the morphometry rows of ENHANCE.PET
(job 40872077) and of VerSe with TotalSegmentator's admitted subjects (job 40877151) are long rows of a study,
a level, a measure and a value, and the per-person covariate analysis needs each person's sex and age beside
them, which no committed file holds. grid/morphometry-covariates.sbatch runs this file from git's copy of it at
the gate's commit, and the gate's word `morphometry covariates` queues it once, on the owner's count. Confidential,
like the rest of SchwingNet: the joined per-person table stays in the job's folder on the lab volume, mode 0700,
and only the aggregates in report.lines leave the grid, in the job's report.

    python3 tools/gold3_covariates.py --morphometry ROOT --verse-demographics CSV --data DATA_ROOT --out DIR
        [--autopet AUTOPET_JSON] [--index SAMPLES_SQLITE] [--records DIR] [--workers N]

where ROOT holds enhance/rows.csv, verse/rows.csv and verse/totalseg/rows.csv as grid/morphometry.sbatch
writes them; an absent --autopet or --index is a failure the report says, autoPET then having no person or
no sex and age.

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
grid, so it is found again here as the census's held part found it). An age above AGE_CEILING is no age (three
TotalSegmentator subjects, s1774, s1776 and s1839, read 115 to 118). Every admitted person with sex read enters
the sex tables, a child among them, since the dataset carries its children and never leaves one out
(docs/research/gold3-ct/README.md, decision 13), and the fill rates count how many are under ADULT_AGE; the age
slope is over the adults of known age alone, since growth and not ageing moves a child's measures, so a child
and a person of unknown age enter no slope.

The aggregates, over the measures the bordercall vocabulary names (VERTEBRA_KEYS at T10 to L5, DISC_KEYS at the
discs T10-T11 to L4-L5) and a whole-column summary, T10-L5, each person's mean over every level of the range,
taken only where the person has all of them, so that a person missing the largest or the smallest body never
moves the mean:
- fill rates of sex and age per member and part (ENHANCE.PET's sites);
- for each member (autopet, verse, totalseg, and all, every person of the three with sex read), measure, level
  and sex: n, mean and SD where n is at least MIN_CELL; Hedges' g, men minus women, with its variance, where both
  sexes have MIN_CELL; the within-person Pearson correlation of the level with the one above it (T10-T11 to L4-L5,
  and the discs' pairs likewise), within sex, where at least MIN_PAIR persons of that sex have both; and the least
  squares slope of the measure on age per decade within sex with its standard error, over the adults of known
  age, where there are at least MIN_SLOPE (two parameters rest on them, as a correlation's co-variation does).

One line per (member, measure, level), both sexes on it, so the whole aggregate is one report the gate prints a
page a send:

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
since zlib lets go of the interpreter's lock while it inflates and a thread needs nothing pickled. A failure
the report says is worded with no slash, quote, file name or long number, since the gate withholds any
reason after FAILED: that could quote a value (grid/report-shapes.awk).
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
TOTALSEG_META = "Totalsegmentator_dataset_v300/meta.csv"
PETCT = re.compile(r"PETCT_([0-9a-f]+)", re.IGNORECASE)
VERSE_SERIES = re.compile(r"(verse\d+|gl\d+)", re.IGNORECASE)
TOTALSEG_SUBJECT = re.compile(r"s\d{4}")
MALE = {"m", "male", "man", "men", "mann", "maennlich"}
FEMALE = {"f", "w", "female", "woman", "women", "frau", "weiblich"}


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
        """Whether the person enters the sex tables: sex read, a child among them."""
        return self.sex in SEXES

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

    def fail(self, text):
        """A failure in plain words, which the gate shows: no quote, slash, file name or long number."""
        self.failures.extend(textwrap.wrap("FAILED: " + text, width=LINE_CHARS - 2, subsequent_indent="  "))

    def all_lines(self):
        return self.failures + self.lines


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


def read_rows(path, study_id):
    """({study: {(level, measure): value}}, every study the file names) over the vocabulary's measures and levels."""
    values, seen = defaultdict(dict), set()
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            study = study_id(row.get("study") or "")
            seen.add(study)
            key, level = row.get("key") or "", row.get("level") or ""
            value = number(row.get("value"))
            if value is not None and wanted(level, key):
                values[study].setdefault((level, key), value)
    return dict(values), seen


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
            report.fail(f"the sample index could not be read ({type(error).__name__}), so autoPET has no sex or age")
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
        report.fail(f"the VerSe demographics table could not be read ({type(error).__name__}), so VerSe has no sex")
        return {}
    if sha256_of(data) != recorded:
        report.fail("the VerSe demographics table is not the one the VerSe series record names by its sha256, so VerSe has no sex")
        return {}
    header, rows = table_rows(data)
    column = sex_column(header)
    if column is None:
        report.fail("the VerSe demographics table has no one column named sex or gender, so VerSe has no sex")
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
        report.fail("no meta table of the TotalSegmentator release under the data root, extracted or zipped, so it has no sex or age")
        return {}
    if sha256_of(found) != recorded:
        report.fail("the TotalSegmentator meta table is not the one its subjects record names by its sha256, so it has no sex or age")
        return {}
    header, rows = table_rows(found, ";")
    names = [h.lower() for h in header]
    if not {"image_id", "age", "gender"} <= set(names):
        report.fail("the TotalSegmentator meta table lacks one of its image id, age and gender columns")
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


def value_at(person, key, level):
    """A person's value of a measure at a level, or at COLUMN the mean over every level of the range they all have."""
    if level != COLUMN:
        return person.values.get((level, key))
    levels = VERTEBRA_LEVELS if key in VERTEBRA_KEYS else DISC_LEVELS
    values = [person.values.get((lv, key)) for lv in levels]
    return sum(values) / len(values) if all(v is not None for v in values) else None


def level_above(key, level):
    levels = VERTEBRA_LEVELS if key in VERTEBRA_KEYS else DISC_LEVELS
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
        out[sex] = {"summary": mean_sd(values), "r": pearson(pairs) if above else None, "slope": age_slope(points)}
    out["g"] = hedges_g(out["M"]["summary"], out["F"]["summary"])
    return out


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
        shown = n >= MIN_CELL
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


def cells_of(persons):
    """[(key, level, numbers)] over every measure of the vocabulary, its levels and its column."""
    out = []
    for keys, levels in ((VERTEBRA_KEYS, VERTEBRA_LEVELS), (DISC_KEYS, DISC_LEVELS)):
        for key in keys:
            for level in (*levels, COLUMN):
                out.append((key, level, cell(persons, key, level)))
    return out


def table_members(persons):
    """[(member, persons in its tables)]: each member, then all of them with sex read."""
    tabled = [p for p in persons if p.member in MEMBERS and p.tabled]
    return [(member, [p for p in tabled if p.member == member]) for member in MEMBERS] + [("all", tabled)]


# ---------------------------------------------------------------- the fill rates


def share(part, whole):
    return f"{part} ({100.0 * part / whole:.1f} %)" if whole else f"{part}"


def fill_line(label, persons, studies):
    """How many of a part's persons carry sex and age, and how many of those are adults, children or too old."""
    total = len(persons)
    sexed = Counter(p.sex for p in persons if p.sex in SEXES)
    aged = [p for p in persons if p.age is not None]
    return (f"fill {label}: persons {total} of {studies} studies; sex {share(sum(sexed.values()), total)}, "
            f"M {sexed['M']}, F {sexed['F']}; age {share(len(aged), total)}, adults {sum(1 for p in aged if not p.child)}, "
            f"under {ADULT_AGE:.0f} {sum(1 for p in aged if p.child)}, above {AGE_CEILING:.0f} dropped from age "
            f"{sum(1 for p in persons if p.age_read is not None and p.age is None)}; in the sex tables "
            f"{sum(1 for p in persons if p.tabled and p.member in MEMBERS)}")


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
        shown = n >= MIN_CELL
        out[sex] = {"n": n, "mean": mean if shown else None, "sd": sd if shown else None,
                    "r": list(numbers[sex]["r"]) if numbers[sex]["r"] else None, "slope": list(numbers[sex]["slope"])}
    return out


# ---------------------------------------------------------------- the run


def member_studies(path, study_id, allowed, report, label, tally):
    """The admitted studies of one rows file with their values, and the counts of what it held and left."""
    if not Path(path).is_file():
        plain = label.replace(".", " ")
        report.fail(f"no rows of {plain} where the morphometry job writes them, so {plain} has no person")
        return {}
    values, seen = read_rows(path, study_id)
    kept = {sid: values.get(sid, {}) for sid in seen if sid in allowed}
    tally[f"{label} studies in the rows"] = len(seen)
    tally[f"{label} studies not admitted"] = len(seen - allowed)
    return kept


def enhance_studies(args, report, tally, off_grid):
    """ENHANCE.PET's admitted studies with rows, less those measured on unrepaired masks and those off their grid."""
    allowed = admitted(args.records, "enhance_pet")
    studies = member_studies(Path(args.morphometry) / "enhance/rows.csv", enhance_id, allowed, report, "ENHANCE.PET", tally)
    facts = enhance_facts(args.records)
    off, grid = off_grid(args.data, facts, args.workers)
    if off is None:
        report.fail("no ENHANCE.PET CTs on the data root, so the CT off its mask's grid could not be found and left out")
        off = set()
    report.say(f"ENHANCE.PET grid check: CTs read {grid['read']}, not found {grid['missing']}, off their mask's grid "
               f"or unreadable {grid['off']}")
    dropped = (set(MEASURED_ON_UNREPAIRED) | off) & set(studies)
    tally["ENHANCE.PET left out"] = len(dropped)
    return {sid: v for sid, v in studies.items() if sid not in dropped}, {sid: facts[sid].get("site", "") for sid in facts}


def autopet_matches(path, report):
    """{ENHANCE.PET study: the census's match} from its autopet.json, or {} with the failure said."""
    if not path:
        report.fail("no census map of autoPET was named, so autoPET has no person")
        return {}
    try:
        return read_json(path).get("matches", {})
    except (OSError, ValueError, AttributeError) as error:
        report.fail(f"the census map of autoPET could not be read ({type(error).__name__}), so autoPET has no person")
        return {}


def gather(args, report, off_grid):
    """Every person of the three members, the counts of how they were found, and the autoPET tally."""
    tally, auto = Counter(), Counter()
    enhance, sites = enhance_studies(args, report, tally, off_grid)
    autopet = {sid: v for sid, v in enhance.items() if sites.get(sid) == "autoPET"}
    matches = autopet_matches(args.autopet, report)
    if not args.index:
        report.fail("no sample index was named, so autoPET has no sex or age")
    persons = autopet_persons(autopet, matches, args.index, report, auto)
    persons += site_persons(enhance, sites, "Leipzig") + site_persons(enhance, sites, "Careggi")
    verse = member_studies(Path(args.morphometry) / "verse/rows.csv", verse_id, admitted(args.records, "verse"),
                           report, "VerSe", tally)
    persons += verse_persons(verse, args.records, verse_sexes(args.verse_demographics, args.records, report), tally)
    totalseg = member_studies(Path(args.morphometry) / "verse/totalseg/rows.csv", totalseg_id,
                              admitted(args.records, "totalsegmentator"), report, "TotalSegmentator", tally)
    persons += totalseg_persons(totalseg, totalseg_meta(args.data, args.records, report))
    counts = {"autoPET": len(autopet), "Leipzig": sum(1 for s in enhance if sites.get(s) == "Leipzig"),
              "Careggi": sum(1 for s in enhance if sites.get(s) == "Careggi"), "verse": len(verse), "totalseg": len(totalseg)}
    return persons, tally, auto, counts


def run(args, off_grid=off_grid_studies):
    """The join, the per-person table under args.out and the report's lines; 0, or 3 where a failure was said."""
    report = Report()
    persons, tally, auto, counts = gather(args, report, off_grid)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_persons(out, persons)
    report.say("rows: " + ", ".join(f"{k} {v}" for k, v in sorted(tally.items())))
    for part in ("autoPET", "Leipzig", "Careggi", "verse", "totalseg"):
        label = f"enhance_pet {part}" if part in ("autoPET", "Leipzig", "Careggi") else part
        report.say(fill_line(label, [p for p in persons if p.part == part], counts[part]))
    for line in autopet_lines([p for p in persons if p.part == "autoPET"], auto):
        report.say(line)
    report.say(f"rule: a person enters the tables with sex read, those under {ADULT_AGE:.0f} among them; mean and SD where "
               f"a sex has {MIN_CELL} or more; g where both have; r with the level above where {MIN_PAIR} or more of a sex "
               f"have both; a, the slope per decade of age within sex, over adults of known age alone where {MIN_SLOPE} or more; "
               f"{COLUMN} is each person's mean over every level of the range, where the person has all of them; "
               "TotalSegmentator's ages carry the release's jitter of up to four years")
    report.say("line: member measure level M n mean sd F n mean sd g g var r rM nM rF nF a slopeM seM nM slopeF seF nF; "
               "- where not shown")
    cells = []
    for member, tabled in table_members(persons):
        written = left = 0
        for key, level, numbers in cells_of(tabled):
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
    return parser.parse_args(argv)


def main(argv=None):
    rc = run(parse(argv))
    return rc


if __name__ == "__main__":
    sys.exit(main())
