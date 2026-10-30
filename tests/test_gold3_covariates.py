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


def jitter(study, level):
    return int(hashlib.sha256(f"{study} {level}".encode()).hexdigest()[:6], 16) / 0xFFFFFF


def value(study, sex, age, level, index):
    return 20.0 + index + (2.0 if sex.upper() == "M" else 0.0) + age / 100.0 + jitter(study, level)


def write_rows(path, studies):
    """rows.csv as grid/morphometry.sbatch writes it: study, level, key, value, note, long."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["study", "level", "key", "value", "note"])
        for study, (sex, age) in studies.items():
            for index, level in enumerate(LEVELS):
                writer.writerow([study, level, "h_ant", f"{value(study, sex, age, level, index):.4f}", ""])
                if study.zfill(4) in CANAL:
                    writer.writerow([study, level, "canal_w", f"{value(study, sex, age, level, index) / 2:.4f}", ""])
            for index, level in enumerate(DISCS):
                if (study, level) not in UNMEASURED:
                    write_disc(writer, study, level, value(study, sex, age, level, index) / 4)
            writer.writerow([study, "C3", "h_ant", "9.0", ""])
            writer.writerow([study, "L1", "not_in_the_vocabulary", "9.0", ""])
            writer.writerow([study, "L2", "h_mid", "nan", "unmeasured"])


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

    def write_rows(self):
        enhance = {sid: (sex, age) for sid, (_, sex, age, _) in AUTOPET.items()}
        enhance.update({sid: ("M", 50) for sid in SITES})
        write_rows(self.morph / "enhance/rows.csv", {str(int(sid)): v for sid, v in enhance.items()})
        write_rows(self.morph / "verse/rows.csv", {f"{sid}_seg": (sex, age) for sid, (_, sex, age) in VERSE.items()})
        write_rows(self.morph / "verse/totalseg/rows.csv", {sid: (g, age) for sid, (g, age) in TOTALSEG.items()})

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
                    records=str(self.records), workers=1)
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
        self.assertFalse({r["key"] for r in joined} - {"h_ant", "canal_w", "disc_h_ant", "disc_h_mid", "disc_h_post", "disc_h_mean"})

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

    def test_the_meta_table_is_read_extracted_before_zipped(self):
        extracted = self.fake.data / "totalsegmentator_v300/raw/Totalsegmentator_dataset_v300/meta.csv"
        extracted.parent.mkdir(parents=True)
        extracted.write_bytes(self.fake.meta_csv())
        self.assertEqual(J.meta_bytes(self.fake.data / "totalsegmentator_v300"), self.fake.meta_csv())


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

    def test_no_commit_named_fails_plainly(self):
        done, report = self.run_job(COVARIATES_COMMIT="")
        self.assertIn("SN_COVARIATES_RC=2", done.stdout)
        failed = [line for line in report if line.startswith("- FAILED: ")]
        self.assertEqual(failed, ["- FAILED: the gate named no commit to copy the code from"])


if __name__ == "__main__":
    unittest.main()
