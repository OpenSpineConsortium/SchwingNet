"""tools/gold3_covariates.py on a made-up data root: the join of morphometry rows with each person's sex and
age, one study a person, the left-out studies, adults alone in the tables, the cells' rules (n of at least 5
for a mean, 10 for a correlation or an age slope), no two printed means that difference into fewer than 5
persons, the arithmetic, a report that carries nothing of one person and passes the gate's filters unchanged,
every failure it can say, and grid/morphometry-covariates.sbatch run end to end from a git copy. The join needs
only the standard library; the grid check and the job need numpy, so those skip without it, and the whole file
is a plain unittest under tests/, as tests/test_gold3_census.py is."""

import ast
import builtins
import csv
import hashlib
import importlib.util
import io
import json
import math
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile
from argparse import Namespace
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


J = load("gold3_covariates", ROOT / "tools/gold3_covariates.py")

LEVELS = J.VERTEBRA_LEVELS
DISCS = J.DISC_LEVELS
GRID = {"shape": [8, 8, 8], "affine": [[1.0, 0, 0, 0], [0, 1.0, 0, 0], [0, 0, 1.0, 0], [0, 0, 0, 1.0]]}

# autoPET: study -> (person's hex, sex, age, study folder). aa01 has two studies, the second younger, so the
# second is the person's first; aa12 is a child, in no table; 0014 is off its mask's grid; 0301 is not
# admitted; aa02 (study 0002) lacks disc_h_mean at T10-T11, the one man of six with some discs but not all.
AUTOPET = {
    "0001": ("aa01", "M", 60, "07-01-2005-NA-PET-CT a"), "0013": ("aa01", "M", 55, "07-01-2000-NA-PET-CT b"),
    "0002": ("aa02", "M", 62, "s"), "0003": ("aa03", "M", 44, "s"), "0004": ("aa04", "M", 71, "s"),
    "0005": ("aa05", "M", 38, "s"), "0006": ("aa06", "M", 66, "s"), "0007": ("aa07", "F", 59, "s"),
    "0008": ("aa08", "F", 47, "s"), "0009": ("aa09", "F", 70, "s"), "0010": ("aa10", "F", 52, "s"),
    "0011": ("aa11", "F", 64, "s"), "0012": ("aa12", "F", 15, "s"), "0014": ("aa14", "M", 50, "s"),
    "0301": ("ab01", "M", 50, "s"),
}
SITES = {"0101": "Leipzig", "0102": "Leipzig", "1134": "Leipzig", "0201": "Careggi"}
# VerSe: series -> (patient, sex, age); four persons, two of each sex, so no VerSe line reaches MIN_CELL.
VERSE = {"verse004": ("verse004", "M", 40), "verse005": ("verse005", "F", 51), "verse006": ("verse006", "M", 33),
         "verse007": ("verse007", "F", 72)}
# TotalSegmentator: subject -> (gender, age); s0011's age is above the ceiling, so unknown, and s0012 is a
# child: eleven men and eleven women in the tables, ten of the women of known age, so r and the age slope show.
TOTALSEG = {"s0001": ("m", 61), "s0002": ("m", 45), "s0003": ("m", 70), "s0004": ("m", 30), "s0005": ("m", 52),
            "s0006": ("m", 67), "s0007": ("f", 58), "s0008": ("f", 41), "s0009": ("f", 77), "s0010": ("f", 36),
            "s0011": ("f", 117), "s0012": ("f", 10), "s0013": ("m", 48), "s0014": ("m", 39), "s0015": ("m", 74),
            "s0016": ("m", 56), "s0017": ("m", 63), "s0018": ("f", 44), "s0019": ("f", 69), "s0020": ("f", 50),
            "s0021": ("f", 33), "s0022": ("f", 62), "s0023": ("f", 55)}
# canal_w is measured on these alone: six men and three women of autoPET's.
CANAL = {"0013", "0002", "0003", "0004", "0005", "0006", "0007", "0008", "0009"}
# (study, disc) left unmeasured: aa02's first disc. (study, disc) whose posterior height alone is unmeasured,
# so it has no disc_h_mean there either, as bordercall's column.py leaves one: s0013's L3-L4.
UNMEASURED = {("2", "T10-T11")}
NO_POSTERIOR = {("s0013", "L3-L4")}
# bordercall's code stamp at ee495d5, which every study's code row carries, and 16f7b40's before it.
STAMP, OLD_STAMP = "a56adf14a9e98b15", "81e732f142d3aa16"
# TotalSegmentator's rows carry interpedicular; where no pedicle was found on both sides bordercall flags the
# hole's width standing in for it: s0001's L4, and s0002's C3, a level outside the tables.
STAND_INS = {("s0001", "L4"), ("s0002", "C3")}


def jitter(study, level):
    return int(hashlib.sha256(f"{study} {level}".encode()).hexdigest()[:6], 16) / 0xFFFFFF


def value(study, sex, age, level, index):
    return 20.0 + index + (2.0 if sex.upper() == "M" else 0.0) + age / 100.0 + jitter(study, level)


def write_rows(path, studies, code=lambda study: STAMP, interpedicular=False):
    """rows.csv as grid/morphometry.sbatch writes it: study, level, key, value, note, long, each study's code
    row last with the stamp code gives it (none where it gives None), and with interpedicular the flag rows
    after a vertebra's values, as bordercall's measure.py writes them."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["study", "level", "key", "value", "note"])
        for study, (sex, age) in studies.items():
            for index, level in enumerate(LEVELS):
                writer.writerow([study, level, "h_ant", f"{value(study, sex, age, level, index):.4f}", ""])
                if study.zfill(4) in CANAL:
                    writer.writerow([study, level, "canal_w", f"{value(study, sex, age, level, index) / 2:.4f}", ""])
                if interpedicular:
                    write_interpedicular(writer, study, level, value(study, sex, age, level, index) / 3)
            for index, level in enumerate(DISCS):
                if (study, level) not in UNMEASURED:
                    write_disc(writer, study, level, value(study, sex, age, level, index) / 4)
            writer.writerow([study, "C3", "h_ant", "9.0", ""])
            if interpedicular:
                write_interpedicular(writer, study, "C3", 9.0)
            writer.writerow([study, "L1", "not_in_the_vocabulary", "9.0", ""])
            writer.writerow([study, "L2", "h_mid", "nan", "unmeasured"])
            if code(study) is not None:
                writer.writerow([study, "study", "code", "", code(study)])


def write_interpedicular(writer, study, level, width):
    """A vertebra's interpedicular, and where STAND_INS names it the flag that says the hole's width stands in."""
    writer.writerow([study, level, "interpedicular", f"{width:.4f}", ""])
    if (study, level) in STAND_INS:
        writer.writerow([study, level, "flag:interpedicular_band", "", "no pedicle found on both sides"])


def write_disc(writer, study, level, height):
    """A disc's three heights and their mean, disc_h_mean, as bordercall writes them: no mean where one is missing."""
    heights = {"disc_h_ant": height + 0.5, "disc_h_mid": height, "disc_h_post": height - 0.5 + jitter(study, level + "p") / 10}
    if (study, level) in NO_POSTERIOR:
        del heights["disc_h_post"]
    for key, found in heights.items():
        writer.writerow([study, level, key, f"{found:.4f}", ""])
    if len(heights) == 3:
        writer.writerow([study, level, "disc_h_mean", f"{sum(heights.values()) / 3:.4f}", ""])


class Fake:
    """A data root, records, morphometry rows, the census's map, a sample index and the two tables."""

    def __init__(self, base):
        self.base = Path(base)
        self.records = self.base / "records"
        self.morph = self.base / "morphometry"
        self.data = self.base / "data"
        self.out = self.base / "out"
        self.autopet = self.base / "census/autopet.json"
        self.index = self.base / "samples.sqlite"
        self.verse_table = self.base / "VerSeFusion/configs/verse_demographics.csv"
        self.write_tables()
        self.write_records()
        self.write_rows()
        self.write_census()
        self.write_index()

    def verse_csv(self, header="patient,series,sex,age"):
        lines = [header] + [f"sub-{p},{s if s != p else ''},{sex},{age}" for s, (p, sex, age) in VERSE.items()]
        return ("\n".join(lines) + "\n").encode()

    def meta_csv(self):
        lines = ["image_id;age;gender;institute;study_type;split"]
        lines += [f"{sid};{age};{g};J;ct abdomen;train" for sid, (g, age) in TOTALSEG.items()]
        return ("\n".join(lines) + "\n").encode()

    def write_tables(self):
        self.verse_table.parent.mkdir(parents=True)
        self.verse_table.write_bytes(self.verse_csv())
        zipped = self.data / "totalsegmentator_v300/raw/Totalsegmentator_dataset_v300.zip"
        zipped.parent.mkdir(parents=True)
        with zipfile.ZipFile(zipped, "w") as archive:
            archive.writestr(J.TOTALSEG_META, self.meta_csv())
        (self.data / "aws_enhance_pet_ct/raw").mkdir(parents=True)

    def write_records(self, verse_sha=None, meta_sha=None):
        studies = [{"member": "enhance_pet", "id": sid, "verdict": "not_admitted" if sid == "0301" else "admitted"}
                   for sid in [*AUTOPET, *SITES]]
        studies += [{"member": "verse", "id": sid, "verdict": "admitted"} for sid in VERSE]
        studies += [{"member": "verse", "id": "verse900", "verdict": "not_admitted"}]
        studies += [{"member": "totalsegmentator", "id": sid, "verdict": "admitted"} for sid in TOTALSEG]
        (self.records / "enhance-pet").mkdir(parents=True, exist_ok=True)
        (self.records / "verse").mkdir(exist_ok=True)
        (self.records / "totalsegmentator").mkdir(exist_ok=True)
        (self.records / "admission.json").write_text(json.dumps({"studies": studies}))
        facts = [{"id": sid, "site": "autoPET", "mask": GRID} for sid in AUTOPET]
        facts += [{"id": sid, "site": site, "mask": GRID} for sid, site in SITES.items()]
        facts += [{"id": "1134", "site": "Leipzig", "mask": GRID, "repaired_from": "the published mask"}]
        (self.records / "enhance-pet/facts.jsonl").write_text("".join(json.dumps(f) + "\n" for f in facts))
        series = [{"series": s, "patient": p, "age": age} for s, (p, _, age) in VERSE.items()]
        (self.records / "verse/series.json").write_text(json.dumps(
            {"source": {"sha256": verse_sha or hashlib.sha256(self.verse_csv()).hexdigest()}, "series": series}))
        (self.records / "totalsegmentator/subjects.json").write_text(json.dumps(
            {"source": {"sha256": meta_sha or hashlib.sha256(self.meta_csv()).hexdigest()},
             "subjects": {sid: {"age": age} for sid, (_, age) in TOTALSEG.items()}}))

    def write_rows(self, codes=None, totalseg=None):
        """The three rows files, codes giving each its stamps by its folder (enhance, verse, totalseg), and
        totalseg the TotalSegmentator subjects measured, every one where it is None."""
        codes = codes or {}
        enhance = {sid: (sex, age) for sid, (_, sex, age, _) in AUTOPET.items()}
        enhance.update({sid: ("M", 50) for sid in SITES})
        write_rows(self.morph / "enhance/rows.csv", {str(int(sid)): v for sid, v in enhance.items()},
                   codes.get("enhance", lambda study: STAMP))
        write_rows(self.morph / "verse/rows.csv", {f"{sid}_seg": (sex, age) for sid, (_, sex, age) in VERSE.items()},
                   codes.get("verse", lambda study: STAMP))
        write_rows(self.morph / "verse/totalseg/rows.csv",
                   {sid: (g, age) for sid, (g, age) in TOTALSEG.items() if totalseg is None or sid in totalseg},
                   codes.get("totalseg", lambda study: STAMP), interpedicular=True)

    def ct_path(self, sid):
        person, _, _, folder = AUTOPET[sid]
        return f"/data/fdg/FDG-PET-CT-Lesions/PETCT_{person}/{folder}/CT.nii.gz"

    def write_census(self):
        self.autopet.parent.mkdir(parents=True)
        matches = {sid: {"case": f"PETCT_{AUTOPET[sid][0]}/{AUTOPET[sid][3]}", "ct": self.ct_path(sid),
                         "residual_mm": 0.0, "person": f"PETCT_{AUTOPET[sid][0]}"} for sid in AUTOPET}
        self.autopet.write_text(json.dumps({"matches": matches}))

    def write_index(self):
        db = sqlite3.connect(self.index)
        db.execute("CREATE TABLE file (id INTEGER PRIMARY KEY, path TEXT, format TEXT, header_full INTEGER, "
                   "patient_id TEXT, patient_sex TEXT, age_years REAL, modality TEXT)")
        db.execute("CREATE TABLE dicom (file_id INTEGER, tag TEXT, keyword TEXT, vr TEXT, value TEXT)")
        row = 0
        for sid, (person, sex, age, folder) in AUTOPET.items():
            for modality in ("CT", "PT"):
                row += 1
                path = f"/data/tcia/FDG-PET-CT-Lesions/PETCT_{person}/{folder}/{modality}-{row}/1-001.dcm"
                db.execute("INSERT INTO file VALUES (?, ?, 'dicom', 1, ?, ?, ?, ?)",
                           (row, path, f"PETCT_{person}", sex, float(age), modality))
                db.execute("INSERT INTO dicom VALUES (?, '(0010,1030)', 'PatientWeight', 'DS', ?)", (row, "80"))
        db.commit()
        db.close()

    def args(self, **kw):
        base = dict(morphometry=str(self.morph), autopet=str(self.autopet), index=str(self.index),
                    verse_demographics=str(self.verse_table), data=str(self.data), out=str(self.out),
                    records=str(self.records), workers=1, previous=[])
        base.update(kw)
        return Namespace(**base)


def off_grid_fake(data, facts, workers):
    """The grid check as the job would find it: 0014's CT off its mask's grid, every other on it."""
    return {"0014"}, Counter(read=len(facts), missing=0, off=1)


def cell_lines(lines):
    """{(member, measure, level): tokens} of the report's cell lines."""
    out = {}
    for line in lines:
        tokens = line.split()
        if len(tokens) == 26 and tokens[3] == "M" and tokens[7] == "F":
            out[tuple(tokens[:3])] = tokens
    return out


class Join(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.fake = Fake(self.dir)

    def run_join(self, **kw):
        rc = J.run(self.fake.args(**kw), off_grid=off_grid_fake)
        lines = (self.fake.out / "report.lines").read_text(encoding="ascii").splitlines()
        with open(self.fake.out / "persons.csv", newline="", encoding="utf-8") as handle:
            persons = {row["person"]: row for row in csv.DictReader(handle)}
        return rc, lines, persons

    def test_each_person_once_with_their_first_study_and_the_left_out_studies_gone(self):
        rc, lines, persons = self.run_join()
        self.assertEqual(rc, 0, "\n".join(lines[:5]))
        auto = {k: v for k, v in persons.items() if v["member"] == "autopet"}
        self.assertEqual(sorted(auto), sorted(f"PETCT_aa{n:02d}" for n in range(1, 13)))
        self.assertEqual(auto["PETCT_aa01"]["study"], "0013", "the younger of the person's two studies is the first")
        self.assertEqual(auto["PETCT_aa01"]["studies"], "2")
        self.assertEqual(auto["PETCT_aa01"]["age"], "55")
        self.assertEqual(auto["PETCT_aa01"]["how"], "its own folder")
        self.assertEqual(auto["PETCT_aa01"]["weight_kg"], "80")
        studies = {row["study"] for row in persons.values()}
        for gone in ("0014", "0301", "1134", "verse900"):
            self.assertNotIn(gone, studies)
        self.assertEqual(auto["PETCT_aa12"]["child"], "1")
        self.assertEqual(auto["PETCT_aa12"]["tabled"], "0", "a child is kept in the per-person table and enters no table")
        sites = {row["study"]: row for row in persons.values() if row["member"] == "enhance_pet"}
        self.assertEqual(sorted(sites), ["0101", "0102", "0201"])
        self.assertTrue(all(row["sex"] == "" and row["tabled"] == "0" for row in sites.values()))
        verse = {row["study"]: row for row in persons.values() if row["member"] == "verse"}
        self.assertEqual({s: row["sex"] for s, row in verse.items()}, {s: v[1] for s, v in VERSE.items()})
        total = {row["study"]: row for row in persons.values() if row["member"] == "totalseg"}
        self.assertEqual(len(total), 23)
        self.assertEqual((total["s0011"]["age_read"], total["s0011"]["age"], total["s0011"]["tabled"]), ("117", "", "1"),
                         "an age above the ceiling is unknown, and a person of unknown age is in the tables")
        self.assertEqual((total["s0012"]["child"], total["s0012"]["tabled"]), ("1", "0"))
        with open(self.fake.out / "joined.csv", newline="", encoding="utf-8") as handle:
            joined = list(csv.DictReader(handle))
        self.assertFalse({r["level"] for r in joined} - {*LEVELS, *DISCS}, "levels outside T10 to L5 are left out")
        self.assertFalse({r["key"] for r in joined} - {"h_ant", "canal_w", "disc_h_ant", "disc_h_mid", "disc_h_post", "disc_h_mean",
                                                       "interpedicular"})

    def test_the_cells_keep_their_minimum_counts(self):
        rc, lines, _ = self.run_join()
        cells = cell_lines(lines)
        self.assertNotIn(("verse", "h_ant", "L1"), cells, "neither sex of VerSe's four reaches 5, so no line")
        auto = cells[("autopet", "h_ant", "L1")]
        self.assertEqual(auto[3:5] + auto[7:9], ["M", "6", "F", "5"], "the child is in no table")
        self.assertNotEqual(auto[12], "-", "g where both sexes have 5")
        self.assertEqual(auto[14:20], ["r", "-", "6", "-", "5", "a"], "no r below 10 a sex, its n shown")
        self.assertEqual(auto[20:26], ["-", "-", "6", "-", "-", "5"], "no age slope below 10 a sex")
        canal = cells[("autopet", "canal_w", "L1")]
        self.assertEqual(canal[3:11], ["M", "6", canal[5], canal[6], "F", "3", "-", "-"])
        self.assertNotEqual(canal[5], "-")
        self.assertEqual(canal[11:14], ["g", "-", "-"], "no g where one sex has fewer than 5")
        total = cells[("totalseg", "h_ant", "L1")]
        self.assertEqual((total[4], total[8]), ("11", "11"), "the child out, the woman of unknown age in")
        self.assertEqual((total[16], total[18]), ("11", "11"))
        self.assertNotIn("-", (total[15], total[17]), "r for both sexes, 11 of each")
        self.assertEqual((total[22], total[25]), ("11", "10"), "the woman of unknown age enters no slope")
        self.assertNotIn("-", total[20:22] + total[23:25])
        self.assertEqual(cells[("totalseg", "h_ant", "T10")][15:19], ["-"] * 4, "T10 has no level above it inside the range")
        self.assertEqual(cells[("totalseg", "h_ant", "T10-L5")][15:19], ["-"] * 4)
        self.assertEqual(cells[("totalseg", "disc_h_mean", "T10-T11")][15:19], ["-"] * 4)
        self.assertNotEqual(cells[("totalseg", "disc_h_mean", "T11-T12")][15], "-")
        for key, tokens in cells.items():
            self.assertIn(tokens[0], J.MEMBERS, key)
            self.assertEqual([tokens[i] for i in (3, 7, 11, 14, 19)], ["M", "F", "g", "r", "a"], key)
            for at in (4, 8):
                if int(tokens[at]) < J.MIN_CELL:
                    self.assertEqual(tokens[at + 1:at + 3], ["-", "-"], key)
            self.assertTrue(int(tokens[4]) >= J.MIN_CELL or int(tokens[8]) >= J.MIN_CELL, key)
            if "-" in (tokens[5], tokens[9]):
                self.assertEqual(tokens[12:14], ["-", "-"], key)
            for at in (16, 18):
                if tokens[at] == "-" or int(tokens[at]) < J.MIN_PAIR:
                    self.assertEqual(tokens[at - 1], "-", key)
            for at in (22, 25):
                if int(tokens[at]) < J.MIN_SLOPE:
                    self.assertEqual(tokens[at - 2:at], ["-", "-"], key)

    def test_children_enter_no_table_and_the_fill_rates_count_them_and_the_unknown_ages_apart(self):
        _, lines, persons = self.run_join()
        children = {row["person"] for row in persons.values() if row["child"] == "1"}
        self.assertEqual(children, {"PETCT_aa12", "totalsegmentator:s0012"})
        sets = person_sets(self.fake.out)
        for key, tokens in cell_lines(lines).items():
            # every cell's n counts adults and persons of unknown age, read from the joined table, and no child
            want = [sets.get((*key, sex), set()) for sex in J.SEXES]
            self.assertEqual((int(tokens[4]), int(tokens[8])), tuple(len(w) for w in want), key)
            self.assertFalse(children & (want[0] | want[1]), key)
        text = " ".join(" ".join(lines).split())
        self.assertIn("fill totalseg: persons 23 of 23 studies; sex 23 (100.0 %), M 11, F 12; age 22 (95.7 %), adults 21, "
                      "under 18 1 in no table, above 110 read as unknown 1; in the tables 22, of unknown age 1", text)
        self.assertIn("fill enhance_pet autoPET: persons 12 of 13 studies; sex 12 (100.0 %), M 6, F 6; age 12 (100.0 %), "
                      "adults 11, under 18 1 in no table, above 110 read as unknown 0; in the tables 11, of unknown age 0", text)
        self.assertIn("rule: the tables are of adults, a person under 18 in none and one of unknown age in all but the slope", text)
        self.assertIn("member autopet: persons 11,", text)
        self.assertIn("member totalseg: persons 22,", text)

    def test_no_line_pools_members_or_sexes_and_no_two_means_difference_into_fewer_than_five(self):
        # The rule of the tool's docstring, held on the fixture with each printed mean's persons read from the
        # joined table the job keeps on the grid: no two printed means of one measure and level share a
        # person, so no pooled line less a member's or a sex's leaves a few; a column's persons sit inside each
        # level's, and those with some levels but not all number none or 5 at least; and disc_h_mean, the mean
        # of the three disc heights, is shown only on the very persons of each height, whose means are shown.
        _, lines, _ = self.run_join()
        self.assertFalse([line for line in lines if line.split()[:1] == ["all"] or line.startswith("member all")],
                         "no line pools the members")
        self.assertEqual(J.DERIVED, {"disc_h_mean": ("disc_h_ant", "disc_h_mid", "disc_h_post")})
        source = (ROOT / "grid/bordercall/morphometry/column.py").read_text(encoding="utf-8")
        self.assertIn('vals = [out[k] for k in ("disc_h_ant", "disc_h_mid", "disc_h_post")]', source)
        self.assertIn('out["disc_h_mean"] = float(np.mean(vals))', source, "the relation the rule rests on is bordercall's")
        sets, cells = person_sets(self.fake.out), cell_lines(lines)
        shown = {(*place, sex): sets[(*place, sex)] for place, tokens in cells.items()
                 for sex, at in (("M", 5), ("F", 9)) if tokens[at] != "-"}
        self.assertGreater(len(shown), 40)
        for a, persons_a in shown.items():
            self.assertIn(a[0], J.MEMBERS)
            for b, persons_b in shown.items():
                if a != b and a[1:3] == b[1:3]:
                    self.assertFalse(persons_a & persons_b, (a, b))
            if a[2] == J.COLUMN:
                partial = set()
                for level in J.levels_of(a[1]):
                    inside = sets.get((a[0], a[1], level, a[3]), set())
                    self.assertLessEqual(persons_a, inside, (a, level))
                    partial |= inside - persons_a
                self.assertTrue(len(partial) == 0 or len(partial) >= J.MIN_CELL, (a, sorted(partial)))
            for part in J.DERIVED.get(a[1], ()):
                self.assertIn((a[0], part, a[2], a[3]), shown, a)
                self.assertEqual(persons_a, shown[(a[0], part, a[2], a[3])], (a, part))
        # the one man with some discs but not all: the level lines show his six discs among five others',
        # so the men's column means, which would give his discs' sum, are withheld, and g with them
        for key in ("disc_h_ant", "disc_h_mid", "disc_h_post", "disc_h_mean"):
            column = cells[("autopet", key, J.COLUMN)]
            self.assertEqual(column[3:7], ["M", "5", "-", "-"], key)
            self.assertNotIn("-", column[9:11], "the women's column, with every disc each, is shown")
            self.assertEqual(column[11:14], ["g", "-", "-"], key)
            self.assertEqual(cells[("autopet", key, "T10-T11")][3:5], ["M", "5"], key)
            self.assertNotEqual(cells[("autopet", key, "T10-T11")][5], "-", key)
        self.assertNotEqual(cells[("autopet", "h_ant", J.COLUMN)][5], "-", "every man has every body")
        # the one man with two heights of a disc and not the third: the four lines there would give his two
        # heights' sum, so the men's disc_h_mean is withheld at that disc while each height shows
        middle = cells[("totalseg", "disc_h_mean", "L3-L4")]
        self.assertEqual(middle[3:7] + middle[11:14], ["M", "10", "-", "-", "g", "-", "-"])
        self.assertNotEqual(middle[9], "-")
        for key, n in (("disc_h_ant", "11"), ("disc_h_mid", "11"), ("disc_h_post", "10")):
            self.assertEqual(cells[("totalseg", key, "L3-L4")][4], n, key)
            self.assertNotEqual(cells[("totalseg", key, "L3-L4")][5], "-", key)
        self.assertNotEqual(cells[("totalseg", "disc_h_mean", "L2-L3")][5], "-", "every man has all three heights there")
        self.assertNotEqual(cells[("totalseg", "disc_h_ant", J.COLUMN)][5], "-")
        for key in ("disc_h_post", "disc_h_mean"):
            self.assertEqual(cells[("totalseg", key, J.COLUMN)][4:7], ["10", "-", "-"], key)

    def test_the_rules_that_withhold_a_mean_on_made_up_persons(self):
        def person(key, sex, levels):
            values = {(lv, "h_ant"): 20.0 + i for i, lv in enumerate(levels)}
            return J.Person(key=key, member="totalseg", part="totalseg", study=key, sex=sex, age_read=50.0, values=values)
        whole = [person(f"w{i}", "M", J.VERTEBRA_LEVELS) for i in range(6)]
        for partial, shown in ((0, True), (4, False), (5, True)):
            persons = whole + [person(f"p{i}", "M", J.VERTEBRA_LEVELS[1:]) for i in range(partial)]
            numbers = J.cell(persons, "h_ant", J.COLUMN)
            self.assertEqual((numbers["M"]["partial"], numbers["M"]["shown"]), (partial, shown))
            self.assertEqual(J.cell(persons, "h_ant", "L1")["M"]["shown"], True, "a level's mean is held to its n alone")
        self.assertFalse(J.mean_shown(4, "L1", 0))
        self.assertTrue(J.mean_shown(5, "L1", 3))
        self.assertFalse(J.mean_shown(5, J.COLUMN, 3))

    def test_a_derived_mean_is_shown_only_beside_every_parts_mean_over_the_same_persons(self):
        def numbers(shown_m=True, persons_m=("a", "b", "c", "d", "e")):
            def sex(shown, persons):
                return {"shown": shown, "persons": frozenset(persons), "summary": (len(persons), 5.0, 1.0)}
            return {"M": sex(shown_m, persons_m), "F": sex(True, ("f", "g", "h", "i", "j"))}
        whole, parts = "disc_h_mean", J.DERIVED["disc_h_mean"]
        def withheld(**part_changes):
            cells = {(whole, "L4-L5"): numbers()}
            for part in parts:
                cells[(part, "L4-L5")] = numbers(**part_changes) if part == parts[-1] else numbers()
            J.withhold_derived(cells, whole, parts, "L4-L5")
            mean = cells[(whole, "L4-L5")]
            return mean["M"]["shown"], mean["F"]["shown"], mean["g"][0] is None
        self.assertEqual(withheld(), (True, True, False))
        self.assertEqual(withheld(shown_m=False), (False, True, True), "a part's mean withheld withholds the whole's")
        self.assertEqual(withheld(persons_m=("a", "b", "c", "d", "z")), (False, True, True),
                         "a part over other persons withholds the whole's")

    def test_the_column_summary_is_each_persons_mean_where_they_have_every_level(self):
        _, lines, _ = self.run_join()
        column = cell_lines(lines)[("autopet", "h_ant", "T10-L5")]
        men = [sum(float(f"{value(str(int(s)), 'M', AUTOPET[s][2], lv, i):.4f}") for i, lv in enumerate(LEVELS)) / len(LEVELS)
               for s in ("0013", "0002", "0003", "0004", "0005", "0006")]
        self.assertAlmostEqual(float(column[5]), sum(men) / 6, delta=0.006)
        self.assertEqual(column[4], "6")

    def test_the_report_holds_nothing_of_one_person_and_passes_the_gates_filters(self):
        _, lines, _ = self.run_join()
        text = "\n".join(lines)
        for pattern in (r"PETCT_", r"\bs\d{4}\b", r"verse\d", r"\b0\d{3}\b", r"aa\d\d", r"\b(person|patient)\b:\S"):
            self.assertIsNone(re.search(pattern, text, re.IGNORECASE), pattern)
        for line in lines:
            self.assertLessEqual(len("- " + line), J.LINE_CHARS, line)
            self.assertNotIn("/", line)
            self.assertIsNone(re.search(r"\w:\S", line), line)
            self.assertIsNone(re.search(r"[0-9a-fA-F]{32}", line), line)
            self.assertIsNone(re.search(r"\b(19|20)\d{6}\b", line), line)
        self.assertEqual(gate_filters(["- " + line for line in lines]), ["- " + line for line in lines])
        self.assertIsNone(re.search(r"(?<![0-9.])117(?![0-9.])", text), "no one person's age is printed, the one above the ceiling among them")
        self.assertNotIn("persons.csv", text)

    def test_a_table_that_is_not_the_recorded_one_or_has_no_sex_column_is_a_failure_said_plainly(self):
        self.fake.write_records(verse_sha="0" * 64)
        rc, lines, persons = self.run_join()
        self.assertEqual(rc, 3)
        self.assertTrue(lines[0].startswith("FAILED: the VerSe demographics table is not the one"), lines[0])
        self.assertTrue(all(row["sex"] == "" for row in persons.values() if row["member"] == "verse"))
        self.assertEqual(gate_filters(["- " + lines[0]]), ["- " + lines[0]], "the reason is plain, so the gate shows it")
        self.fake.verse_table.write_bytes(self.fake.verse_csv("patient,series,geschlecht,age"))
        self.fake.write_records(verse_sha=hashlib.sha256(self.fake.verse_csv("patient,series,geschlecht,age")).hexdigest())
        rc, lines, _ = self.run_join()
        self.assertEqual(rc, 3)
        self.assertIn("no one column named sex or gender", lines[0])
        self.assertEqual(gate_filters(["- " + lines[0]]), ["- " + lines[0]])

    def test_a_missing_input_is_a_failure_said_plainly(self):
        shutil.rmtree(self.fake.data / "totalsegmentator_v300")
        (self.fake.morph / "verse/rows.csv").unlink()
        rc, lines, persons = self.run_join(autopet="", index="")
        self.assertEqual(rc, 3)
        failures = [line for line in lines if line.startswith("FAILED: ")]
        self.assertEqual(len(failures), 4, failures)
        self.assertEqual(gate_filters(["- " + f for f in failures]), ["- " + f for f in failures])
        self.assertFalse([row for row in persons.values() if row["member"] in ("autopet", "verse")])
        self.assertTrue(all(row["sex"] == "" for row in persons.values() if row["member"] == "totalseg"))

    def test_the_rows_name_the_one_code_that_measured_them_or_the_join_says_it_cannot(self):
        rc, lines, _ = self.run_join()
        self.assertEqual(rc, 0, lines[:3])
        self.assertIn(f"rows: measuring code {STAMP} for every set's rows", lines)
        # one set measured on the older engine: its tables would blend two engines' definitions
        mixed = ("FAILED: the morphometry rows were measured by more than one version of the measuring code, within a "
                 "set or between the sets, so the tables blend two engines")
        self.fake.write_rows(codes={"verse": lambda study: OLD_STAMP})
        rc, lines, _ = self.run_join()
        self.assertEqual(rc, 3)
        self.assertEqual([line for line in lines if line.startswith("FAILED: ")], [mixed])
        self.assertIn(f"rows: measuring code by set, ENHANCE.PET {STAMP}; VerSe {OLD_STAMP}; TotalSegmentator {STAMP}", lines)
        # and within one set: a study the older engine wrote among the new ones
        self.fake.write_rows(codes={"enhance": lambda study: OLD_STAMP if study == "5" else STAMP})
        rc, lines, _ = self.run_join()
        self.assertEqual(rc, 3)
        self.assertEqual([line for line in lines if line.startswith("FAILED: ")], [mixed])
        # a study that names no code, or none of the plain form, ties its rows to no engine, and no such stamp is printed
        self.fake.write_rows(codes={"totalseg": lambda study: {"s0004": None, "s0005": "fake/x"}.get(study, STAMP)})
        rc, lines, _ = self.run_join()
        self.assertEqual(rc, 3)
        self.assertEqual([line for line in lines if line.startswith("FAILED: ")],
                         ["FAILED: a study in the morphometry rows names no measuring code of the plain form, so its rows "
                          "cannot be tied to the engine that measured them"])
        self.assertIn(f"rows: measuring code {STAMP} where the rows name one", lines)
        self.assertNotIn("fake", "\n".join(lines))
        self.assertEqual(gate_filters(["- " + line for line in lines]), ["- " + line for line in lines])

    def test_an_interpedicular_the_holes_width_stands_in_for_is_left_out_and_counted(self):
        # bordercall reads interpedicular on the pedicles' walls and, where no pedicle is found on both sides,
        # flags the hole's width standing in for it, which reads otherwise: the stand-in enters no table
        rc, lines, _ = self.run_join()
        self.assertEqual(rc, 0, lines[:3])
        with open(self.fake.out / "joined.csv", newline="", encoding="utf-8") as handle:
            joined = {(r["person"], r["level"], r["key"]) for r in csv.DictReader(handle)}
        self.assertNotIn(("totalsegmentator:s0001", "L4", "interpedicular"), joined)
        self.assertIn(("totalsegmentator:s0001", "L3", "interpedicular"), joined)
        self.assertIn(("totalsegmentator:s0002", "L4", "interpedicular"), joined)
        # counted where it would have entered a table: s0002's flagged C3 is outside the levels
        text = " ".join(" ".join(lines).split())
        self.assertIn("TotalSegmentator interpedicular stand-ins left out 1,", text)
        self.assertIn("interpedicular is left out where the rows flag the hole's width standing in", text)
        cells = cell_lines(lines)
        self.assertEqual(cells[("totalseg", "interpedicular", "L4")][4], "10", "the man whose L4 it stood in for is out there")
        self.assertEqual(cells[("totalseg", "interpedicular", "L3")][4], "11")

    def test_the_meta_table_is_read_extracted_before_zipped(self):
        extracted = self.fake.data / "totalsegmentator_v300/raw/Totalsegmentator_dataset_v300/meta.csv"
        extracted.parent.mkdir(parents=True)
        extracted.write_bytes(self.fake.meta_csv())
        self.assertEqual(J.meta_bytes(self.fake.data / "totalsegmentator_v300"), self.fake.meta_csv())


class AcrossReports(unittest.TestCase):
    """A join run once more prints its blocks beside an earlier report's: no block printed in both may
    difference into the readings of fewer than five persons."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.fake = Fake(self.dir)
        self.first = self.dir / "covariates/40878978"

    def join(self, out, previous=()):
        rc = J.run(self.fake.args(out=str(out), previous=[str(p) for p in previous]), off_grid=off_grid_fake)
        return rc, (Path(out) / "report.lines").read_text(encoding="ascii").splitlines()

    def assert_nothing_differences(self, earlier, later, lines_a, lines_b):
        """Every mean both reports print rests on the same readings of the same persons, or on readings that
        differ in five persons at least, read from the two joined tables alone; the same ones print the same."""
        a, b = cell_lines(lines_a), cell_lines(lines_b)
        readings_a, readings_b = readings_from(earlier), readings_from(later)
        both = 0
        for place in a.keys() & b.keys():
            for sex, at in (("M", 5), ("F", 9)):
                if a[place][at] == "-" or b[place][at] == "-":
                    continue
                both += 1
                ra, rb = readings_a.get((*place, sex), {}), readings_b.get((*place, sex), {})
                apart = len(ra.keys() ^ rb.keys()) + sum(1 for k in ra.keys() & rb.keys() if ra[k] != rb[k])
                self.assertTrue(apart == 0 or apart >= J.MIN_CELL, (place, sex, apart))
                if apart == 0:
                    self.assertEqual(a[place][at - 1:at + 2], b[place][at - 1:at + 2], (place, sex))
        for tokens in b.values():
            if "-" in (tokens[5], tokens[9]):
                self.assertEqual(tokens[12:14], ["-", "-"], "g goes with a sex's mean")
        return both

    def test_a_second_join_withholds_every_block_that_differences_against_the_first_into_fewer_than_five(self):
        rc, before = self.join(self.first)
        self.assertEqual(rc, 0, before[:3])
        # the rows measured once more: one man of TotalSegmentator's no longer measured, one woman's L2 height
        # read otherwise; nothing of autoPET's or VerSe's moved
        self.fake.write_rows(totalseg=set(TOTALSEG) - {"s0002"})
        shift(self.fake.morph / "verse/totalseg/rows.csv", "s0007", "L2", "h_ant", 0.75)
        second = self.dir / "covariates/4343"
        rc, after = self.join(second, [self.first])
        self.assertEqual(rc, 0, after[:3])
        self.assertGreater(self.assert_nothing_differences(self.first, second, before, after), 40)
        a, b = cell_lines(before), cell_lines(after)
        # the men's blocks lost one man, so each one the first report printed is withheld, its n still shown
        self.assertNotEqual(a[("totalseg", "h_ant", "L1")][5], "-")
        self.assertEqual(b[("totalseg", "h_ant", "L1")][3:7], ["M", "10", "-", "-"])
        self.assertEqual(b[("totalseg", "h_ant", "L4")][15:17], ["-", "10"], "r over pairs one man apart")
        self.assertEqual(b[("totalseg", "h_ant", "L1")][20:23], ["-", "-", "10"], "the slope over points one man apart")
        # the woman's moved reading withholds the blocks it enters, at L2 and the column, r on either side of
        # L2 and the slope at L2, and leaves the rest of the women's as they were
        for level in ("L2", J.COLUMN):
            self.assertNotEqual(a[("totalseg", "h_ant", level)][9], "-")
            self.assertEqual(b[("totalseg", "h_ant", level)][7:11], ["F", "11", "-", "-"], level)
        for level in ("L2", "L3"):
            self.assertNotEqual(a[("totalseg", "h_ant", level)][17], "-")
            self.assertEqual(b[("totalseg", "h_ant", level)][17:19], ["-", "11"], level)
        self.assertNotEqual(a[("totalseg", "h_ant", "L2")][23], "-")
        self.assertEqual(b[("totalseg", "h_ant", "L2")][23:26], ["-", "-", "10"])
        for level in ("L1", "L4"):
            self.assertEqual(b[("totalseg", "h_ant", level)][7:11], a[("totalseg", "h_ant", level)][7:11], level)
            self.assertEqual(b[("totalseg", "h_ant", level)][17:19], a[("totalseg", "h_ant", level)][17:19], level)
            self.assertEqual(b[("totalseg", "h_ant", level)][23:26], a[("totalseg", "h_ant", level)][23:26], level)
        # a member whose rows did not move prints what it printed
        self.assertEqual({k: v for k, v in b.items() if k[0] == "autopet"}, {k: v for k, v in a.items() if k[0] == "autopet"})
        text = " ".join(" ".join(after).split())
        self.assertIn("across reports: 1 earlier joins read; a block withheld where an earlier join had persons enough to "
                      "print it and the two differ by 1 to 4 persons or readings for a mean and SD, 1 to 9 for r and 1 to 9 "
                      "for a slope; withheld autopet means 0, r 0, slopes 0; verse means 0, r 0, slopes 0; totalseg means ", text)
        self.assertEqual(gate_filters(["- " + line for line in after]), ["- " + line for line in after])
        # five men apart is enough: against the first report alone the men's blocks are printed again
        self.fake.write_rows(totalseg=set(TOTALSEG) - {"s0002", "s0003", "s0004", "s0005", "s0006"})
        third = self.dir / "covariates/4444"
        rc, again = self.join(third, [self.first])
        self.assertEqual(rc, 0, again[:3])
        self.assert_nothing_differences(self.first, third, before, again)
        self.assertEqual(cell_lines(again)[("totalseg", "h_ant", "L1")][4], "6")
        self.assertNotEqual(cell_lines(again)[("totalseg", "h_ant", "L1")][5], "-")
        # but every earlier join counts: against the second too, four men apart, they are withheld
        fourth = self.dir / "covariates/4545"
        rc, last = self.join(fourth, [self.first, second])
        self.assertEqual(rc, 0, last[:3])
        self.assert_nothing_differences(self.first, fourth, before, last)
        self.assert_nothing_differences(second, fourth, after, last)
        self.assertEqual(cell_lines(last)[("totalseg", "h_ant", "L1")][3:7], ["M", "6", "-", "-"])
        self.assertIn("across reports: 2 earlier joins read;", " ".join(last))

    def test_the_column_is_withheld_where_its_persons_with_some_levels_alone_differ_from_an_earlier_reports(self):
        # Six men with every level all read otherwise and one man with some levels but not all new: each level
        # and the column differ in five or more, yet the levels less the column, set beside the earlier
        # report's, give that one man's sum, so the column is withheld for him
        def person(key, levels, moved=0.0):
            values = {(lv, "h_ant"): 20.0 + i + moved for i, lv in enumerate(levels)}
            return J.Person(key=key, member="totalseg", part="totalseg", study=key, sex="M", age_read=50.0, values=values)
        whole, some = J.VERTEBRA_LEVELS, J.VERTEBRA_LEVELS[1:]
        before = [person(f"w{i}", whole) for i in range(6)] + [person(f"p{i}", some) for i in range(5)]
        now = [person(f"w{i}", whole, 0.5) for i in range(6)] + [person(f"p{i}", some) for i in range(6)]
        alone = {(key, level): numbers for key, level, numbers in J.cells_of(now)}
        taken = Counter()
        checked = {(key, level): numbers for key, level, numbers in J.cells_of(now, [before], taken)}
        self.assertTrue(alone[("h_ant", J.COLUMN)]["M"]["shown"], "within one report its six such men let it show")
        for level in J.VERTEBRA_LEVELS:
            self.assertTrue(checked[("h_ant", level)]["M"]["shown"], level)
        self.assertFalse(checked[("h_ant", J.COLUMN)]["M"]["shown"])
        self.assertEqual(taken["means"], 1)

    def test_an_earlier_join_whose_table_cannot_be_read_withholds_every_mean_r_and_slope(self):
        rc, lines = self.join(self.dir / "covariates/4343", [self.first])
        self.assertEqual(rc, 3)
        self.assertEqual(lines[0], "FAILED: the joined table of an earlier join could not be read (FileNotFoundError), so every "
                                   "mean, r and slope is withheld, none checked against that join")
        self.assertEqual(gate_filters(["- " + lines[0]]), ["- " + lines[0]])
        cells = cell_lines(lines)
        self.assertGreater(len(cells), 40)
        for key, tokens in cells.items():
            self.assertEqual([tokens[i] for i in (5, 6, 9, 10, 12, 13, 15, 17, 20, 21, 23, 24)], ["-"] * 12, key)
        self.assertEqual(cells[("totalseg", "h_ant", "L1")][4], "11", "the counts are still printed")
        self.assertIn("and a joined table not read, so every mean, r and slope withheld", " ".join(lines))

    def test_an_earlier_joined_table_that_is_there_but_cannot_be_read_withholds_as_a_missing_one_does(self):
        # a table without the value column, one that is not UTF-8 and one whose field passes csv's limit
        bad = {"KeyError": b"person,member,part,study,sex,age,level,key\nx,totalseg,totalseg,s1,M,50,L1,h_ant\n",
               "UnicodeDecodeError": b"person,member,part,study,sex,age,level,key,value\nx\xff,totalseg,totalseg,s1,M,50,L1,h_ant,1\n",
               "Error": b"person,member,part,study,sex,age,level,key,value\n\"" + b"x" * 200000 + b"\",totalseg,t,s,M,50,L1,h_ant,1\n"}
        for kind, table in bad.items():
            self.first.mkdir(parents=True, exist_ok=True)
            (self.first / "joined.csv").write_bytes(table)
            rc, lines = self.join(self.dir / "covariates" / kind, [self.first])
            self.assertEqual(rc, 3, kind)
            self.assertEqual(lines[0], f"FAILED: the joined table of an earlier join could not be read ({kind}), so every "
                                       "mean, r and slope is withheld, none checked against that join")
            cells = cell_lines(lines)
            self.assertGreater(len(cells), 40, kind)
            for key, tokens in cells.items():
                self.assertEqual([tokens[i] for i in (5, 6, 9, 10, 12, 13, 15, 17, 20, 21, 23, 24)], ["-"] * 12, (kind, key))

    @staticmethod
    def person(key, values, age=50.0):
        return J.Person(key=key, member="totalseg", part="totalseg", study=key, sex="M", age_read=age, values=values)

    @staticmethod
    def checked(now, before):
        """The blocks of now alone, now checked against before, and what that check took, by kind."""
        taken = Counter()
        alone = {(key, level): numbers for key, level, numbers in J.cells_of(now)}
        checked = {(key, level): numbers for key, level, numbers in J.cells_of(now, [before], taken)}
        return alone, checked, taken

    def test_a_mean_the_earlier_join_printed_over_exactly_the_least_persons_is_withheld_one_person_on(self):
        # the earlier report printed the men's L1 mean over exactly MIN_CELL men, so a mean over one man more
        # would difference into his reading alone; over one man fewer it printed none, and nothing differences
        before = [self.person(f"m{i}", {("L1", "h_ant"): 20.0 + i * 0.37}) for i in range(J.MIN_CELL)]
        now = before + [self.person("new", {("L1", "h_ant"): 23.11})]
        alone, checked, taken = self.checked(now, before)
        self.assertTrue(alone[("h_ant", "L1")]["M"]["shown"])
        self.assertFalse(checked[("h_ant", "L1")]["M"]["shown"])
        self.assertEqual(checked[("h_ant", "L1")]["M"]["summary"][0], J.MIN_CELL + 1, "its n still printed")
        self.assertEqual(taken["means"], 1)
        alone, checked, taken = self.checked(now, before[:-1])
        self.assertTrue(checked[("h_ant", "L1")]["M"]["shown"])
        self.assertEqual(taken["means"], 0)

    def test_an_r_the_earlier_join_printed_over_exactly_the_least_pairs_is_withheld_one_pair_on(self):
        def man(i):
            return self.person(f"m{i}", {("L1", "h_ant"): 20.0 + i * 0.37, ("L2", "h_ant"): 21.0 + i * 0.29 + (i % 3) * 0.11})
        before = [man(i) for i in range(J.MIN_PAIR)]
        now = before + [man(J.MIN_PAIR)]
        alone, checked, taken = self.checked(now, before)
        self.assertIsNotNone(alone[("h_ant", "L2")]["M"]["r"][0])
        self.assertEqual(checked[("h_ant", "L2")]["M"]["r"], (None, J.MIN_PAIR + 1), "its n still printed")
        self.assertEqual(taken["r"], 1)
        # an r over one pair fewer was never printed, so the r over eleven differences into nothing
        alone, checked, taken = self.checked(now, before[:-1])
        self.assertIsNotNone(checked[("h_ant", "L2")]["M"]["r"][0])
        self.assertEqual(taken["r"], 0)

    def test_a_reading_moved_in_its_last_place_withholds_the_blocks_it_enters(self):
        # the joined table writes four places, and a block one reading apart in the fourth differences into
        # that reading, so the check reads all four
        before = [self.person(f"m{i}", {("L1", "h_ant"): 20.3 + i}) for i in range(J.MIN_SLOPE + 1)]
        now = [self.person(p.key, dict(p.values)) for p in before]
        now[0].values[("L1", "h_ant")] += 0.0001
        alone, checked, taken = self.checked(now, before)
        self.assertTrue(alone[("h_ant", "L1")]["M"]["shown"])
        self.assertFalse(checked[("h_ant", "L1")]["M"]["shown"])
        self.assertEqual(taken["means"], 1)
        # the same readings to the last place withhold nothing
        alone, checked, taken = self.checked([self.person(p.key, dict(p.values)) for p in before], before)
        self.assertTrue(checked[("h_ant", "L1")]["M"]["shown"])
        self.assertEqual(sum(taken.values()), 0)

    def test_an_age_moved_between_joins_withholds_the_slope_and_no_mean(self):
        # two slopes over the same readings, one man's age read otherwise, difference into his age and reading
        before = [self.person(f"m{i}", {("L1", "h_ant"): 20.0 + i * 0.37 + (i % 4) * 0.2}, age=30.0 + 3 * i)
                  for i in range(J.MIN_SLOPE + 1)]
        now = [self.person(p.key, dict(p.values), age=p.age_read) for p in before]
        now[3].age_read += 1.0
        alone, checked, taken = self.checked(now, before)
        self.assertIsNotNone(alone[("h_ant", "L1")]["M"]["slope"][0])
        self.assertEqual(checked[("h_ant", "L1")]["M"]["slope"][:2], (None, None))
        self.assertEqual(checked[("h_ant", "L1")]["M"]["slope"][2], J.MIN_SLOPE + 1, "its n still printed")
        self.assertTrue(checked[("h_ant", "L1")]["M"]["shown"], "the mean is over the same readings")
        self.assertEqual(taken["slopes"], 1)
        self.assertEqual(taken["means"], 0)


class Arithmetic(unittest.TestCase):
    def test_mean_and_sample_sd(self):
        self.assertEqual(J.mean_sd([]), (0, None, None))
        self.assertEqual(J.mean_sd([3.0]), (1, 3.0, None))
        n, mean, sd = J.mean_sd([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
        self.assertEqual((n, mean), (8, 5.0))
        self.assertAlmostEqual(sd, math.sqrt(32 / 7))

    def test_hedges_g_and_its_variance(self):
        men, women = (10, 12.0, 2.0), (12, 10.0, 2.0)
        g, var = J.hedges_g(men, women)
        j = 1 - 3 / (4 * 22 - 9)
        self.assertAlmostEqual(g, j * 1.0)
        self.assertAlmostEqual(var, j ** 2 * (22 / 120 + 1 / 44))
        self.assertEqual(J.hedges_g((4, 12.0, 2.0), women), (None, None))

    def test_pearson(self):
        line = [(x, 2 * x + 1) for x in range(10)]
        self.assertAlmostEqual(J.pearson(line)[0], 1.0)
        self.assertEqual(J.pearson(line[:9]), (None, 9))
        self.assertEqual(J.pearson([(1.0, 2.0)] * 10), (None, 10))

    def test_age_slope_per_decade(self):
        points = [(20.0 + 5 * i, 3.0 + 0.1 * (20.0 + 5 * i)) for i in range(12)]
        slope, se, n = J.age_slope(points)
        self.assertEqual(n, 12)
        self.assertAlmostEqual(slope, 1.0)
        self.assertAlmostEqual(se, 0.0)
        noisy = [(a, v + (0.5 if i % 2 else -0.5)) for i, (a, v) in enumerate(points)]
        slope, se, _ = J.age_slope(noisy)
        xs = [a / 10 for a, _ in noisy]
        mx = sum(xs) / 12
        b = sum((x - mx) * v for x, (_, v) in zip(xs, noisy)) / sum((x - mx) ** 2 for x in xs)
        self.assertAlmostEqual(slope, b)
        self.assertGreater(se, 0)
        self.assertEqual(J.age_slope(points[:9])[:2], (None, None))

    def test_figures_never_take_exponent_form(self):
        self.assertEqual(J.figure(None), "-")
        self.assertEqual(J.figure(1523.456), "1523")
        self.assertEqual(J.figure(0.000123456), "0.000123")
        self.assertEqual(J.figure(-12.3456), "-12.35")
        self.assertNotIn("e", J.figure(1e-9))

    def test_a_sex_column_is_found_by_name_or_refused(self):
        self.assertEqual(J.sex_column(["Patient", "Series", "Sex", "Age"]), 2)
        self.assertEqual(J.sex_column(["id", "patient gender"]), 1)
        self.assertIsNone(J.sex_column(["id", "sex", "gender"]))
        self.assertIsNone(J.sex_column(["id", "age"]))


class Failures(unittest.TestCase):
    def test_every_failure_the_join_can_say_passes_the_gates_filters_whole(self):
        # Every FAILED line the tool can write is one of FAILURES, with at most the kind of error beside it:
        # each, with every exception class the join could meet and a name that is no plain word, comes
        # through grid/shape-words.awk and grid/report-shapes.awk unwithheld and on one line.
        kinds = {cls for module in (builtins, sqlite3, json, zipfile, csv, os)
                 for cls in vars(module).values() if isinstance(cls, type) and issubclass(cls, BaseException)}
        kinds |= {type("Error12345", (Exception,), {}), type("deadbeefError", (Exception,), {}),
                  type("dotted.name", (Exception,), {})}
        said = set()
        for kind in sorted(kinds, key=lambda cls: cls.__name__):
            error = type(kind.__name__, (Exception,), {})()  # an error of that class's name, made without its arguments
            for failure in J.FAILURES:
                report = J.Report()
                report.fail(failure, error)
                self.assertEqual(len(report.failures), 1, report.failures)
                said.add("- " + report.failures[0])
        self.assertIn("an error of no plain name", " ".join(said))
        said = sorted(said)
        self.assertEqual(gate_filters(said), said)
        for line in said:
            self.assertLessEqual(len(line), J.LINE_CHARS, line)
            self.assertNotIn("ENHANCE.PET", line)

    def test_no_failure_is_said_but_through_the_table(self):
        # Report.fail takes a FAILURES key and nothing else, and nothing else in the tool writes FAILED, so
        # the table above is every FAILED line it holds.
        with self.assertRaises(KeyError):
            J.Report().fail("the CT at /rs/x is off its mask's grid")
        tree = ast.parse((ROOT / "tools/gold3_covariates.py").read_text(encoding="utf-8"))
        docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                      if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)) and node.body
                      and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)}
        texts = [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)
                 and "FAILED" in node.value and id(node) not in docstrings]
        self.assertEqual(texts, ["FAILED: "])
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                 and node.func.attr == "fail"]
        for call in calls:
            first = call.args[0]
            self.assertTrue(isinstance(first, ast.Name) or (isinstance(first, ast.Constant) and first.value in J.FAILURES),
                            ast.dump(first))
        changed = [node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call)
                   and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Attribute)
                   and node.func.value.attr == "failures"]
        self.assertEqual(changed, ["extend"], "only fail adds to the failures")

    def test_the_line_count_stated_is_the_vocabularys(self):
        # three members, 26 vertebra keys at 8 levels and the column, 5 disc keys at 7 discs and the column
        self.assertEqual(J.MAX_CELL_LINES, 3 * (26 * 9 + 5 * 8))
        self.assertEqual(J.MAX_CELL_LINES, 822)
        self.assertEqual((len(J.VERTEBRA_KEYS), len(J.VERTEBRA_LEVELS), len(J.DISC_KEYS), len(J.DISC_LEVELS)), (26, 8, 5, 7))
        self.assertIn("at most MAX_CELL_LINES, 822: each member's 26 vertebra\nkeys at 8 levels and the column (234 lines) "
                      "and 5 disc keys at 7 disc levels and the column (40)", J.__doc__)
        gate = (ROOT / "grid/gate.sh").read_text(encoding="utf-8")
        said = re.search(r"The report holds at most (\d+) lines of cells", gate)
        self.assertIsNotNone(said)
        self.assertEqual(int(said.group(1)), J.MAX_CELL_LINES)
        pages = int(re.search(r"(?m)^COVARIATES_PAGE_LINES=(\d+)$", gate).group(1))
        self.assertEqual(-(-(J.MAX_CELL_LINES + 30) // pages), 3, "three sends, as the gate's comment says")
        self.assertIn("so it takes three sends", gate)


def person_sets(out):
    """{(member, measure, level, sex): persons} behind each cell, read from the job's joined.csv alone: a
    person of a member with sex read whose age is unknown or at least 18 and who has the measure at the
    level, and at the column every level of it."""
    with open(Path(out) / "joined.csv", newline="", encoding="utf-8") as handle:
        rows = [r for r in csv.DictReader(handle) if r["member"] in J.MEMBERS and r["sex"] in J.SEXES
                and (r["age"] == "" or float(r["age"]) >= J.ADULT_AGE)]
    sets, levels = {}, {}
    for r in rows:
        sets.setdefault((r["member"], r["key"], r["level"], r["sex"]), set()).add(r["person"])
        levels.setdefault((r["member"], r["key"], r["sex"], r["person"]), set()).add(r["level"])
    for (member, key, sex, person), have in levels.items():
        if have >= set(J.levels_of(key)):
            sets.setdefault((member, key, J.COLUMN, sex), set()).add(person)
    return sets


def readings_from(out):
    """{(member, measure, level, sex): {person: reading}} behind each mean, read from a job's joined.csv alone,
    as person_sets reads its persons; at the column a person's reading is every level's value."""
    with open(Path(out) / "joined.csv", newline="", encoding="utf-8") as handle:
        rows = [r for r in csv.DictReader(handle) if r["member"] in J.MEMBERS and r["sex"] in J.SEXES
                and (r["age"] == "" or float(r["age"]) >= J.ADULT_AGE)]
    found, levels = {}, {}
    for r in rows:
        found.setdefault((r["member"], r["key"], r["level"], r["sex"]), {})[r["person"]] = r["value"]
        levels.setdefault((r["member"], r["key"], r["sex"], r["person"]), {})[r["level"]] = r["value"]
    for (member, key, sex, person), have in levels.items():
        if set(have) >= set(J.levels_of(key)):
            found.setdefault((member, key, J.COLUMN, sex), {})[person] = tuple(have[lv] for lv in J.levels_of(key))
    return found


def shift(path, study, level, key, by):
    """One reading of a rows file moved by BY, as other code might read it."""
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    for row in rows[1:]:
        if row[:3] == [study, level, key]:
            row[3] = f"{float(row[3]) + by:.4f}"
    with open(path, "w", newline="", encoding="utf-8") as handle:
        csv.writer(handle, lineterminator="\n").writerows(rows)


def gate_filters(lines):
    """The lines as the gate prints a stage report's: report_shapes, then the masks, then the cut."""
    awk = subprocess.run(["awk", "-v", "data=/rs/data", "-v", "runs=/rs/runs", "-v", "models=/rs/models",
                          "-v", "repo=/home/x/SchwingNet", "-f", str(ROOT / "grid/shape-words.awk"),
                          "-f", str(ROOT / "grid/report-shapes.awk")],
                         input="\n".join(lines) + "\n", capture_output=True, text=True, check=True)
    sed = subprocess.run(["sed", "-r", "-f", str(ROOT / "grid/redact.sed")], input=awk.stdout,
                         capture_output=True, text=True, check=True)
    return [line[:J.LINE_CHARS] for line in sed.stdout.splitlines()]


def census_helpers():
    """tests/test_gold3_census.py, for its NIfTI writer: the module already loaded where it is, and the census
    tool's module under the name gold3_census left as it was, since the census tests' worker processes pickle
    its functions by that name, and a second copy put there fails them when they run after these."""
    for name in ("tests.test_gold3_census", "test_gold3_census", "test_gold3_census_helpers"):
        if name in sys.modules:
            return sys.modules[name]
    kept = sys.modules.get("gold3_census")
    try:
        return load("test_gold3_census_helpers", ROOT / "tests/test_gold3_census.py")
    finally:
        if kept is not None:
            sys.modules["gold3_census"] = kept


@unittest.skipIf(np is None, "numpy is not installed")
class GridCheck(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)

    def test_a_ct_off_its_masks_grid_or_unreadable_is_found(self):
        helpers = census_helpers()
        raw = self.dir / "aws_enhance_pet_ct/raw"
        affine = np.asarray(GRID["affine"])
        helpers.write_nifti(raw / "a/0001.nii.gz", np.zeros((8, 8, 8), np.int16), affine)
        moved = affine.copy()
        moved[0, 3] = 1.0
        helpers.write_nifti(raw / "b/0002.nii.gz", np.zeros((8, 8, 8), np.int16), moved)
        (raw / "0003.nii.gz").write_bytes(b"not a NIfTI")
        facts = {sid: {"mask": GRID} for sid in ("0001", "0002", "0003", "0004")}
        off, tally = J.off_grid_studies(self.dir, facts, 2)
        self.assertEqual(off, {"0002", "0003"})
        self.assertEqual((tally["read"], tally["missing"], tally["off"]), (3, 1, 2))
        self.assertEqual(J.off_grid_studies(self.dir / "nowhere", facts, 1), (None, Counter()))


class JobHandoff(unittest.TestCase):
    """grid/morphometry-covariates.sbatch's handoff of the earlier joins to the tool, with a stand-in interpreter
    that answers the job's probes and keeps the words it is called with, so it needs no numpy and runs on CI."""

    STAND_IN = """#!/bin/bash
case "$1 $2" in
  '-c import sys, numpy, sqlite3'*) exit 0 ;;
  '-c import sys; print'*) echo 3.12.0; exit 0 ;;
  '-c import numpy; print'*) echo 2.0.0; exit 0 ;;
  '-c '*) exit 1 ;;
esac
printf '%s\\n' "$@" > "$FAKE_ARGS"
while [ $# -gt 0 ]; do [ "$1" = --out ] && out=$2; shift; done
echo "a line of the join" > "$out/report.lines"
"""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.repo = self.dir / "SchwingNet"
        for name in ("tools/gold3_covariates.py", "tools/gold3_census.py", "tools/gold3_field.py",
                     "grid/morphometry-covariates.sbatch"):
            (self.repo / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / name, self.repo / name)
        (self.repo / "data/gold3-ct").mkdir(parents=True)
        (self.repo / "data/gold3-ct/admission.json").write_text("{}\n", encoding="utf-8")
        quiet = dict(os.environ, GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="gc.auto", GIT_CONFIG_VALUE_0="0")
        git = ["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@example.org"]
        subprocess.run(["git", "init", "-q", str(self.repo)], env=quiet, check=True)
        subprocess.run([*git, "add", "-A"], env=quiet, check=True)
        subprocess.run([*git, "commit", "-qm", "the join"], env=quiet, check=True)
        self.commit = subprocess.run([*git, "rev-parse", "HEAD"], env=quiet, capture_output=True, text=True,
                                     check=True).stdout.strip()
        self.python = self.dir / "python"
        self.python.write_text(self.STAND_IN, encoding="utf-8")
        self.python.chmod(0o755)
        self.morph = self.dir / "morphometry"
        self.args = self.dir / "args.txt"

    def run_job(self, job, previous):
        env = {"PATH": os.environ.get("PATH", ""), "HOME": str(self.dir / "home"), "SCHWINGNET": str(self.repo),
               "RS_ROOT": str(self.dir / "rs"), "MORPHOMETRY_ROOT": str(self.morph), "COVARIATES_COMMIT": self.commit,
               "COVARIATES_PYTHON": str(self.python), "COVARIATES_PREVIOUS": previous, "SLURM_JOB_ID": job,
               "SLURM_CPUS_PER_TASK": "2", "FAKE_ARGS": str(self.args),
               "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "gc.auto", "GIT_CONFIG_VALUE_0": "0"}
        done = subprocess.run(["bash", str(self.repo / "grid/morphometry-covariates.sbatch")], env=env,
                              capture_output=True, text=True, timeout=120)
        report = self.repo / "grid/logs/MORPHOMETRY-covariates.md"
        return done, report.read_text(encoding="ascii").splitlines() if report.is_file() else []

    def test_each_earlier_join_the_gate_names_reaches_the_tool_as_its_job_folder(self):
        done, report = self.run_job("4343", "4242 77")
        self.assertIn("SN_COVARIATES_RC=0", done.stdout, done.stdout + done.stderr + "\n".join(report))
        self.assertIn("- earlier joins read for the check across reports: jobs 4242 77", report)
        words = self.args.read_text(encoding="utf-8").splitlines()
        self.assertEqual(words[-4:], ["--previous", str(self.morph / "covariates/4242"),
                                      "--previous", str(self.morph / "covariates/77")])
        # a first join names none, and is handed none
        self.args.unlink()
        done, report = self.run_job("4444", "")
        self.assertIn("SN_COVARIATES_RC=0", done.stdout, done.stdout + done.stderr + "\n".join(report))
        self.assertNotIn("--previous", self.args.read_text(encoding="utf-8").splitlines())
        self.assertFalse(any("earlier joins read" in line for line in report))

    def test_a_name_that_is_no_job_number_stops_the_job_before_the_tool_runs(self):
        for previous in ("4242 ../x", "1234567890123", "4242 77x"):
            done, report = self.run_job("4545", previous)
            self.assertIn("SN_COVARIATES_RC=2", done.stdout, previous + done.stdout + done.stderr)
            self.assertEqual([line for line in report if line.startswith("- FAILED: ")],
                             ["- FAILED: the gate named an earlier join that is no job number, so the check across "
                              "reports cannot be made; nothing was joined"], previous)
            self.assertFalse(self.args.exists(), previous)
            self.assertFalse((self.morph / "covariates/4545/report.lines").exists(), previous)


@unittest.skipIf(np is None, "numpy is not installed")
class Job(unittest.TestCase):
    """grid/morphometry-covariates.sbatch run as Slurm would, from a git repository holding the tool."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.fake = Fake(self.dir / "grid")
        self.repo = self.dir / "SchwingNet"
        for name in ("tools/gold3_covariates.py", "tools/gold3_census.py", "tools/gold3_field.py",
                     "grid/morphometry-covariates.sbatch"):
            (self.repo / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / name, self.repo / name)
        shutil.copytree(self.fake.records, self.repo / "data/gold3-ct")
        helpers = census_helpers()
        for sid in [*AUTOPET, *SITES]:
            affine = np.asarray(GRID["affine"])
            if sid == "0014":
                affine = affine.copy()
                affine[2, 3] = 3.0
            helpers.write_nifti(self.fake.data / f"aws_enhance_pet_ct/raw/{sid}.nii.gz", np.zeros((8, 8, 8), np.int16), affine)
        git = ["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@example.org", "-c", "gc.auto=0"]
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run([*git, "add", "-A"], check=True)
        subprocess.run([*git, "commit", "-qm", "the join"], check=True)
        self.commit = subprocess.run([*git, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()

    def run_job(self, **env):
        base = {"PATH": os.environ.get("PATH", ""), "HOME": str(self.dir / "home"), "SCHWINGNET": str(self.repo),
                "RS_ROOT": str(self.dir / "rs"), "DATA_ROOT": str(self.fake.data), "MORPHOMETRY_ROOT": str(self.fake.morph),
                "AUTOPET": str(self.fake.autopet), "INDEX": str(self.fake.index),
                "VERSE_DEMOGRAPHICS": str(self.fake.verse_table), "COVARIATES_COMMIT": self.commit,
                "COVARIATES_PYTHON": sys.executable, "SLURM_JOB_ID": "4242", "SLURM_CPUS_PER_TASK": "2",
                "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "gc.auto", "GIT_CONFIG_VALUE_0": "0"}
        base.update(env)
        done = subprocess.run(["bash", str(self.repo / "grid/morphometry-covariates.sbatch")], env=base,
                              capture_output=True, text=True, timeout=300)
        report = self.repo / "grid/logs/MORPHOMETRY-covariates.md"
        return done, report.read_text(encoding="ascii").splitlines() if report.is_file() else []

    def test_the_job_reports_aggregates_alone_and_keeps_the_tables_private(self):
        done, report = self.run_job()
        self.assertIn("SN_COVARIATES_RC=0", done.stdout, done.stdout + done.stderr + "\n".join(report))
        self.assertTrue(report[0].startswith("# morphometry covariates: job 4242 on "), report[0])
        self.assertIn(f"commit {self.commit[:7]}", report[0])
        self.assertTrue(report[-1].startswith("- exit 0 at "), report[-1])
        self.assertTrue(any(line.startswith("- autopet h_ant L1 M 6 ") for line in report))
        self.assertTrue(any("off their mask's grid or unreadable 1" in line for line in report))
        folder = self.fake.morph / "covariates/4242"
        self.assertEqual(oct(folder.stat().st_mode & 0o777), "0o700")
        self.assertEqual(oct((folder / "persons.csv").stat().st_mode & 0o777), "0o600")
        self.assertEqual(oct((self.repo / "grid/logs/MORPHOMETRY-covariates.md").stat().st_mode & 0o777), "0o644")
        text = "\n".join(report)
        self.assertNotIn(str(self.dir), text, "no path leaves the grid")
        self.assertIsNone(re.search(r"PETCT_|\bs\d{4}\b|verse\d", text))

    def test_a_join_that_said_a_failure_ends_1_with_its_reason_plain(self):
        self.fake.verse_table.write_bytes(b"patient,series,age\n")
        done, report = self.run_job()
        self.assertIn("SN_COVARIATES_RC=1", done.stdout)
        failed = [line for line in report if line.startswith("- FAILED: ")]
        self.assertTrue(failed and "VerSe demographics" in failed[0], report)
        self.assertEqual(gate_filters(failed), failed)

    def wrapper(self, path, body=""):
        """An interpreter at PATH that runs this python, BODY first when it is given the join to run."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"#!/bin/bash\ncase \"$1\" in -c) ;; *) {body or ':'} ;; esac\nexec {sys.executable} \"$@\"\n",
                        encoding="utf-8")
        path.chmod(0o755)
        return path

    def test_the_spineps_environment_comes_before_the_checkouts_interpreter(self):
        # As morphometry.sbatch looks for its own: the SPINEPS environment in the home first, the checkout's
        # train-cpu, which reads the working tree, last; the checkout's is not even asked here.
        home = self.dir / "home"
        self.wrapper(home / "mambaforge/envs/spineps/bin/python")
        touched = self.dir / "checkout-python-ran"
        checkout = self.repo / "grid/bin/train-cpu-python"
        checkout.parent.mkdir(parents=True, exist_ok=True)
        checkout.write_text(f"#!/bin/bash\ntouch {touched}\nexec {sys.executable} \"$@\"\n", encoding="utf-8")
        checkout.chmod(0o755)
        done, report = self.run_job(COVARIATES_PYTHON="", PYDRV=str(self.repo / "grid/bin/train-cpu-python"))
        self.assertIn("SN_COVARIATES_RC=0", done.stdout, done.stdout + done.stderr + "\n".join(report))
        self.assertTrue(any(line.startswith("- interpreter: the SPINEPS environment in the home, Python ") for line in report),
                        report)
        self.assertFalse(touched.exists(), "the checkout's interpreter was not run")
        # with no SPINEPS environment and no python3 on the PATH that imports numpy, the checkout's is taken, and said
        shutil.rmtree(home / "mambaforge")
        lacking = self.dir / "lacking"
        lacking.mkdir()
        (lacking / "python3").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        (lacking / "python3").chmod(0o755)
        shutil.rmtree(self.fake.morph / "covariates")
        done, report = self.run_job(COVARIATES_PYTHON="", PATH=f"{lacking}:{os.environ.get('PATH', '')}")
        self.assertIn("SN_COVARIATES_RC=0", done.stdout, done.stdout + done.stderr + "\n".join(report))
        self.assertTrue(any(line.startswith("- interpreter: the checkout train-cpu environment, read from the working tree, ")
                            for line in report), report)
        self.assertTrue(touched.exists())

    def test_a_join_that_crashed_names_its_errors_kind_alone(self):
        # the last line of a traceback names its kind and may quote a path, a person or a number: the kind
        # alone is said, as a plain word, and a last line that names none says so
        for last, said in (("json.decoder.JSONDecodeError: Expecting value at /rs/data/PETCT_0af3/1-001.dcm 40877151",
                            "an error of the kind JSONDecodeError"),
                           ("  File /rs/rs_grp_oschome/go2432/morphometry/covariates/40877151/code/tools/x.py, line 9",
                            "its output naming no error kind"),
                           ("Error40877151: at PETCT_0af3", "its output naming no error kind")):
            python = self.wrapper(self.dir / "crash/python", f"echo 'Traceback (most recent call last):'; echo '{last}'; exit 1")
            shutil.rmtree(self.fake.morph / "covariates", ignore_errors=True)
            done, report = self.run_job(COVARIATES_PYTHON=str(python))
            self.assertIn("SN_COVARIATES_RC=1", done.stdout, done.stdout + done.stderr)
            failed = [line for line in report if line.startswith("- FAILED: ")]
            self.assertEqual(len(failed), 1, report)
            self.assertTrue(failed[0].startswith("- FAILED: the join ended after 0 min with exit 1, "), failed[0])
            self.assertTrue(failed[0].endswith(said), failed[0])
            self.assertEqual(gate_filters(failed), failed)
            self.assertNotIn("40877151", "\n".join(report))
            self.assertNotIn("PETCT", "\n".join(report))

    def test_the_job_hands_the_join_every_earlier_join_the_gate_names(self):
        done, first = self.run_job()
        self.assertIn("SN_COVARIATES_RC=0", done.stdout, done.stdout + done.stderr + "\n".join(first))
        done, report = self.run_job(SLURM_JOB_ID="4343", COVARIATES_PREVIOUS="4242")
        self.assertIn("SN_COVARIATES_RC=0", done.stdout, done.stdout + done.stderr + "\n".join(report))
        self.assertIn("- earlier joins read for the check across reports: jobs 4242", report)
        text = " ".join(" ".join(line[2:].split()) for line in report)
        self.assertIn("across reports: 1 earlier joins read;", text)
        # the same rows joined again difference into nothing, so nothing is withheld and every line is the first's
        self.assertIn("withheld autopet means 0, r 0, slopes 0; verse means 0, r 0, slopes 0; totalseg means 0, r 0, slopes 0",
                      text)
        cells = [line for line in first if line.startswith(("- autopet ", "- totalseg "))]
        self.assertGreater(len(cells), 40)
        self.assertEqual([line for line in report if line.startswith(("- autopet ", "- totalseg "))], cells)
        # a name that is no job number stops the job before any join
        done, report = self.run_job(SLURM_JOB_ID="4444", COVARIATES_PREVIOUS="4242 ../x")
        self.assertIn("SN_COVARIATES_RC=2", done.stdout, done.stdout + done.stderr)
        failed = [line for line in report if line.startswith("- FAILED: ")]
        self.assertEqual(failed, ["- FAILED: the gate named an earlier join that is no job number, so the check across "
                                  "reports cannot be made; nothing was joined"])
        self.assertFalse((self.fake.morph / "covariates/4444/report.lines").exists())

    def test_no_commit_named_fails_plainly(self):
        done, report = self.run_job(COVARIATES_COMMIT="")
        self.assertIn("SN_COVARIATES_RC=2", done.stdout)
        failed = [line for line in report if line.startswith("- FAILED: ")]
        self.assertEqual(failed, ["- FAILED: the gate named no commit to copy the code from"])


if __name__ == "__main__":
    unittest.main()
