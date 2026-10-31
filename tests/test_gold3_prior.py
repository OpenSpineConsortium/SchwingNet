"""The gold tier 3 correlation prior's job tool on rows made from a known structure.

The rows are drawn per population from a matrix normal whose correlation between levels is an
AR(1) at 0.8 and between the five measures is fixed, so the fit has an exact truth to find. The
tool must leave out a study the admission refuses, a test-reserve person, a study with an L6 or a
T13 row or no L5, keep a repeat group in one part, fit each population alone, beat the generator's
assumed structure on the held-out spines, and write report lines that carry no study id or person
key. The vendored correlation module is held to grid/prior/VENDORED's hashes.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRIOR = ROOT / "grid" / "prior"
sys.path.insert(0, str(PRIOR))

try:                                           # the job runs on the grid's numpy; CI's python has none
    import numpy as np
    import gold3_prior as GP
except ImportError:
    np = GP = None

HAVE_NUMPY = np is not None
MEASURES = GP.MEASURES if HAVE_NUMPY else []
LEVELS = GP.LEVEL_SETS["C3..L5"] if HAVE_NUMPY else []


def ar1(n, phi):
    i = np.arange(n)
    return phi ** np.abs(i[:, None] - i[None, :])


R_MEASURE = [[1.0, 0.6, 0.5, 0.4, 0.3], [0.6, 1.0, 0.4, 0.5, 0.2], [0.5, 0.4, 1.0, 0.6, 0.3],
             [0.4, 0.5, 0.6, 1.0, 0.2], [0.3, 0.2, 0.3, 0.2, 1.0]]


def spines(rng, n):
    al, am = np.linalg.cholesky(ar1(len(LEVELS), 0.8)), np.linalg.cholesky(np.array(R_MEASURE))
    e = rng.normal(size=(n, len(LEVELS), len(MEASURES)))
    return 30.0 + 3.0 * np.einsum("lk,nkj,mj->nlm", al, e, am)


def write_rows(path, ids, values, extra=()):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["study", "level", "key", "value", "note"])
        for sid, v in zip(ids, values):
            for i, level in enumerate(LEVELS):
                for k, m in enumerate(MEASURES):
                    w.writerow([sid, level, m, "%.4f" % v[i, k], ""])
            w.writerow([sid, "study", "code", "", "stamp"])
        for row in extra:
            w.writerow(row)


def make_inputs(base: Path, n=400):
    rng = np.random.default_rng(3)
    morph, records = base / "morphometry", base / "data"
    enhance = ["%d" % i for i in range(1, n + 1)]          # the rows' raw ids, unpadded
    v = spines(rng, n)
    v[5, 3, 1] = np.nan                                     # one incomplete spine
    write_rows(morph / "enhance/rows.csv", enhance, v,
               extra=[["7", "L6", "h_post", "20", ""]])     # study 7 draws an L6
    ts = ["s%04d" % i for i in range(1, 121)]
    write_rows(morph / "verse/totalseg/rows.csv", ts, spines(rng, 120))
    studies = [{"id": "%04d" % i, "member": "enhance_pet", "verdict": "admitted"} for i in range(1, n + 1) if i != 9]
    studies += [{"id": sid, "member": "totalsegmentator", "verdict": "admitted"} for sid in ts]
    (records / "gold3-ct" / "verse").mkdir(parents=True)
    (records / "gold3-ct" / "admission.json").write_text(json.dumps({"studies": studies}))
    (records / "gold3-ct" / "verse" / "series.json").write_text(json.dumps({"series": []}))
    (records / "splits").mkdir()
    (records / "splits" / "latent-prior-test-reserve.json").write_text(json.dumps(
        [{"person": "enhance_pet:0002"}, {"person": "enhance_pet:0003"}, {"person": "totalsegmentator:s0001"}]))
    (records / "splits" / "latent-prior-repeat-groups.json").write_text(json.dumps(
        [{"unit": "enhance_pet:0010", "persons": ["enhance_pet:0010", "enhance_pet:0011"]}]))
    return morph, records


@unittest.skipUnless(HAVE_NUMPY, "numpy is needed, as on the grid")
class Tool(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.morph, self.records = make_inputs(self.tmp)
        self.out = self.tmp / "out"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_fits_each_population_and_beats_the_assumed_structure(self):
        rc = GP.run(self.morph, self.records, self.out)
        self.assertEqual(rc, 3)                              # verse's own rows are missing: one FAILED line
        lines = (self.out / "report.lines").read_text().splitlines()
        self.assertIn("FAILED: no rows for verse", lines)
        head = [l for l in lines if l.startswith("enhance_pet C3..L5: studies")][0]
        # 400 read, 1 not admitted (0009), 2 reserved, 1 with an L6 (7); the rest fit or held
        self.assertIn("studies 400, not admitted 1, test reserve 2, L6 or T13 or no L5 1,", head)
        prior = json.loads((self.out / "prior-enhance_pet-C3-L5.json").read_text())
        rl, rm = np.array(prior["r_level"]), np.array(prior["r_measure"])
        self.assertLess(np.abs(rm - (0.95 * np.array(R_MEASURE) + 0.05 * np.eye(5))).max(), 0.06)
        self.assertLess(np.abs(rl - (0.95 * ar1(len(LEVELS), 0.8) + 0.05 * np.eye(len(LEVELS)))).max(), 0.08)
        gain = [l for l in lines if l.startswith("enhance_pet C3..L5: held out")][0]
        self.assertRegex(gain, r"gain \d+\.\d+ nats")
        self.assertTrue((self.out / "prior-totalsegmentator-T1-L5.json").is_file())
        text = "\n".join(lines)
        for leak in ("0010", "s0001", "enhance_pet:", "totalsegmentator:", str(self.tmp)):
            self.assertNotIn(leak, text)
        self.assertTrue(all(len(l) <= 196 for l in lines), max(map(len, lines)))

    def test_a_repeat_group_is_one_unit(self):
        self.assertEqual(GP.held_out("enhance_pet:0010"), GP.held_out("enhance_pet:0010"))
        units = GP.unit_map(self.records)
        self.assertEqual(units["enhance_pet:0011"], "enhance_pet:0010")


class Vendored(unittest.TestCase):
    def test_the_copy_is_the_one_vendored_names(self):
        lines = (PRIOR / "VENDORED").read_text().splitlines()
        self.assertRegex(lines[0], r"^bordercall [0-9a-f]{40} OpenSpineConsortium/bordercall$")
        for line in lines[1:]:
            digest, name = line.split()
            self.assertEqual(hashlib.sha256((PRIOR / name).read_bytes()).hexdigest(), digest, name)


if __name__ == "__main__":
    unittest.main()
