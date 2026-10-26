"""tools/bordercall_corpus.py on a made-up column: the count from C2, the gap rule, the ribs
and the files the grid job reads and writes. Needs numpy, nibabel and scipy, which the
check's environment may lack, so it is a plain unittest under tests/ and skips without them."""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))

try:
    import nibabel as nib
    import numpy as np
    import scipy  # noqa: F401
    HAVE_IMAGING = True
except ImportError:                                            # pragma: no cover
    HAVE_IMAGING = False

import bordercall_corpus as BC                                   # noqa: E402


def column_volume(names_by_slab, shape=(20, 20, 160), slab=6):
    """A stack of boxes, one per vertebra, cranial first, labelled by the ids given."""
    arr = np.zeros(shape, np.int16)
    z = shape[2] - slab - 2
    for vid in names_by_slab:
        if vid is None:                                      # a missed body: an empty slab
            z -= slab
            continue
        arr[4:16, 4:16, z:z + slab - 1] = vid
        z -= slab
    return arr


def spaced_column(ids_and_spacing, shape=(20, 20, 600)):
    """Boxes at the spacings given, cranial first: [(id, voxels to the next centroid)], so a
    column can sit as a spine does, cervical bodies about half as far apart as lumbar ones."""
    arr = np.zeros(shape, np.int16)
    z = shape[2] - 8
    for vid, step in ids_and_spacing:
        if vid is not None:
            arr[4:16, 4:16, z - 2:z + 2] = vid
        z -= step
    return arr


def spine_spacing(missing=()):
    """A whole column with a spine's spacings (cervical 16, thoracic 22 to 30, lumbar 34 voxels),
    the ids named in missing left out of the mask but their room kept."""
    rows = []
    for vid in range(1, 25):
        step = 16 if vid <= 7 else (22 + (vid - 8) if vid <= 19 else 34)
        rows.append((None if vid in missing else vid, step))
    rows.append((26, 40))
    return rows


@unittest.skipUnless(HAVE_IMAGING, "numpy, nibabel and scipy are needed")
class CountFromC2(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        BC.MIN_VOXELS = 100                                  # the boxes are small

    def write(self, name, ids, ribs=None, ids_state="verse_coded"):
        """One tier row with its mask, and a Moller rib table when ribs is given."""
        arr = column_volume(ids)
        path = self.tmp / ("%s_seg-vert_msk.nii.gz" % name)
        nib.save(nib.Nifti1Image(arr, np.eye(4)), str(path))
        row = {k: "" for k in BC.TIER_COLUMNS}
        row.update(tier="1", collection="made_up", case_id=name, person_key="p:" + name,
                   spineps_vert=str(path), spineps_ids=ids_state, spineps_store="test")
        if ribs is not None:
            d = self.tmp / "moller" / "made_up"
            d.mkdir(parents=True, exist_ok=True)
            with open(d / ("%s_rib_measurements.csv" % name), "w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=["variant", "vertebra", "side", "rib_length"])
                w.writeheader()
                for vid, side, length in ribs:
                    w.writerow({"variant": "upstream", "vertebra": vid, "side": side, "rib_length": length})
        return row

    def run_one(self, row, ribs=True):
        labels = self.tmp / "labels"
        labels.mkdir(exist_ok=True)
        return BC.one((row, str(self.tmp / "moller") if ribs else "", str(labels), True))

    def test_a_typical_column_is_named_by_its_count(self):
        ids = list(range(1, 26))[:24] + [26]                 # C1 to L5 then the sacrum
        ribs = [(v, "left", 120.0) for v in range(8, 20)]   # a rib on every thoracic body
        rec = self.run_one(self.write("typical", ids, ribs))
        self.assertEqual(rec["status"], "countable", rec)
        self.assertEqual((rec["n_from_c2"], rec["lowest_by_count"], rec["has_sacrum"]), (23, "L5", 1))
        self.assertEqual((rec["phenotype"], rec["lowest_rib_bearing"], rec["n_lumbar"]), ("typical", "T12", 5))
        self.assertEqual(rec["veridah_names_agree"], 1)
        out = np.asanyarray(nib.load(rec["label_file"]).dataobj)
        self.assertEqual(sorted(int(v) for v in np.unique(out) if v), ids)

    def test_the_labeller_skipping_t12_does_not_move_the_count(self):
        # VERIDAH named the column C1..T11, L1..L5, L6: one name skipped, 25 bodies present
        ids = list(range(1, 19)) + list(range(20, 26)) + [26]
        rec = self.run_one(self.write("skip", ids, []), ribs=True)
        self.assertEqual(rec["status"], "countable")
        self.assertEqual(rec["n_from_c2"], 23)
        self.assertEqual(rec["lowest_by_count"], "L5")
        self.assertEqual(rec["veridah_names_agree"], 0)
        self.assertEqual(rec["veridah_l1_offset"], "-1")

    def test_a_thirteenth_rib_bearing_body_is_l1_with_a_rib(self):
        ids = list(range(1, 20)) + [28, 20, 21, 22, 23, 24, 26]
        ribs = [(v, "right", 110.0) for v in range(8, 20)] + [(28, "right", 60.0)]
        rec = self.run_one(self.write("t13", ids, ribs))
        self.assertEqual(rec["status"], "countable")
        self.assertEqual(rec["n_from_c2"], 24)
        self.assertEqual((rec["phenotype"], rec["lowest_rib_bearing"], rec["has_lumbar_rib"]),
                         ("lumbar_rib", "L1", 1))
        self.assertEqual(rec["n_lumbar"], 6)

    def test_a_stump_under_38_mm_is_not_rib_bearing(self):
        ids = list(range(1, 25)) + [26]
        ribs = [(v, "left", 100.0) for v in range(8, 19)] + [(19, "left", 20.0)]
        rec = self.run_one(self.write("stump", ids, ribs))
        self.assertEqual((rec["phenotype"], rec["lowest_rib_bearing"]), ("no_rib_T12", "T11"))

    def test_without_c2_the_column_is_set_aside(self):
        rec = self.run_one(self.write("lumbar", [17, 18, 19, 20, 21, 22, 23, 24, 26], []))
        self.assertEqual(rec["status"], "set_aside")
        self.assertIn("no C2", rec["reason"])
        self.assertEqual(rec["countable"], 0)

    def test_a_missed_body_is_set_aside(self):
        ids = list(range(1, 12)) + [None] + list(range(13, 25)) + [26]
        rec = self.run_one(self.write("gap", ids, []))
        self.assertEqual(rec["status"], "set_aside")
        self.assertIn("gap", rec["reason"])

    def test_a_missed_cervical_body_is_caught_against_its_neighbours(self):
        # C4 missing leaves a 32-voxel gap among 16-voxel cervical gaps, narrower than any lumbar
        # gap, so a rule against the column's median would pass it and shift every name below
        arr = spaced_column(spine_spacing(missing=(4,)))
        inst = BC.instances(arr, (1.0, 1.0, 1.0))
        with self.assertRaises(BC.SetAside) as cm:
            BC.name_by_count(inst)
        self.assertIn("a gap of 32 mm between instances 3 and 4", str(cm.exception))
        # the same spine whole is countable, its lumbar gaps twice its cervical ones
        inst = BC.instances(spaced_column(spine_spacing()), (1.0, 1.0, 1.0))
        mapping = BC.name_by_count(inst)
        self.assertEqual(len(mapping), 24)
        self.assertEqual(BC.NAMES[mapping[24]], "L5")

    def test_a_missed_thoracic_body_is_caught_too(self):
        arr = spaced_column(spine_spacing(missing=(10,)))
        with self.assertRaises(BC.SetAside) as cm:
            BC.name_by_count(BC.instances(arr, (1.0, 1.0, 1.0)))
        self.assertIn("between instances 9 and 10", str(cm.exception))

    def test_four_lumbar_bodies_need_the_sacrum_in_view(self):
        ribs = {v: 100.0 for v in range(8, 20)}
        mapping = {v: v for v in range(1, 24)}                # C1 to L4, the field ends there
        rec = BC.phenotype_of(mapping, ribs, has_sacrum=False)
        self.assertEqual((rec["phenotype"], rec["phenotype_known"], rec["n_lumbar"]), ("", 1, 4))
        rec = BC.phenotype_of(mapping, ribs, has_sacrum=True)
        self.assertEqual(rec["phenotype"], "four_lumbar")
        # five lumbar bodies with no sacrum in view are not a typical column either
        rec = BC.phenotype_of({v: v for v in range(1, 25)}, ribs, has_sacrum=False)
        self.assertEqual(rec["phenotype"], "")
        # a sixth lumbar body is one whether or not the sacrum is in view
        rec = BC.phenotype_of({v: v for v in range(1, 26)}, ribs, has_sacrum=False)
        self.assertEqual(rec["phenotype"], "six_lumbar")

    def test_an_empty_rib_table_leaves_the_ribs_unread(self):
        rec = BC.phenotype_of({v: v for v in range(1, 25)}, {}, has_sacrum=True)
        self.assertEqual((rec["phenotype"], rec["phenotype_known"], rec["n_rib_bearing"]), ("", 0, ""))

    def test_rib_bearing_is_strictly_over_38_mm_as_the_census_reads_it(self):
        ribs = {v: 100.0 for v in range(8, 19)}
        ribs[19] = 38.0
        rec = BC.phenotype_of({v: v for v in range(1, 25)}, ribs, has_sacrum=True)
        self.assertEqual((rec["lowest_rib_bearing"], rec["phenotype"]), ("T11", "no_rib_T12"))
        ribs[19] = 38.1
        rec = BC.phenotype_of({v: v for v in range(1, 25)}, ribs, has_sacrum=True)
        self.assertEqual((rec["lowest_rib_bearing"], rec["phenotype"]), ("T12", "typical"))

    def test_the_report_reads_its_numbers_back_as_numbers(self):
        out = self.tmp / "report"
        out.mkdir()
        rows = []
        for i, (sac, n) in enumerate(((0, 9), (0, 10), (1, 23), (1, 24))):
            r = {k: "" for k in BC.ROW_FIELDS}
            r.update(case="c%d" % i, collection="made_up", status="countable", countable=1,
                     has_sacrum=sac, n_from_c2=n, phenotype="typical", phenotype_known=1,
                     reason="as read", n_lumbar=5, has_l6=0, spineps_ids="verse_coded",
                     veridah_names_agree=1, veridah_l1_offset="0")
            rows.append(r)
        r = {k: "" for k in BC.ROW_FIELDS}
        r.update(case="c9", collection="made_up", status="set_aside", countable=0,
                 reason="a gap of 37 mm between instances 3 and 4 (the spacing beside it 16 mm)")
        rows.append(r)
        BC.write_rows(rows, out / "corpus.csv")
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            BC.cmd_report(argparse.Namespace(out=str(out)))
        text = buf.getvalue()
        self.assertIn("  23 bodies: 1\n  24 bodies: 1", text)
        self.assertNotIn(" 9 bodies", text)
        self.assertIn("set aside, a gap of N mm between instances N and N: 1", text)

    def test_no_rib_table_leaves_the_phenotype_unknown(self):
        rec = self.run_one(self.write("noribs", list(range(1, 25)) + [26]), ribs=False)
        self.assertEqual(rec["status"], "countable")
        self.assertEqual((rec["phenotype"], rec["phenotype_known"]), ("", 0))

    def test_no_rib_table_still_counts_six_lumbar_bodies(self):
        # the count alone settles the lumbosacral classes, so a disagreement there is still in a
        # counted anomaly when the ribs were never read
        rec = self.run_one(self.write("noribs6", list(range(1, 26)) + [26]), ribs=False)
        self.assertEqual((rec["phenotype"], rec["phenotype_known"], rec["n_lumbar"]), ("six_lumbar", 0, 6))

    def test_a_raw_mask_is_set_aside_without_the_guard(self):
        row = self.write("raw", list(range(1, 25)), [], ids_state="raw")
        os.environ["SSN"] = str(self.tmp / "nowhere")
        rec = self.run_one(row)
        self.assertEqual(rec["status"], "set_aside")
        self.assertIn("raw ids", rec["reason"])

    def test_build_writes_the_corpus_and_phenotype_files(self):
        tiers = self.tmp / "tiers"
        tiers.mkdir()
        rows = [self.write("a", list(range(1, 25)) + [26], [(v, "left", 90.0) for v in range(8, 20)]),
                self.write("b", [18, 19, 20, 21, 22, 26], [])]
        with open(tiers / "tier1.tsv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(BC.TIER_COLUMNS), delimiter="\t")
            w.writeheader()
            w.writerows(rows)
        out = self.tmp / "out"
        rc = BC.main(["build", "--tiers", str(tiers), "--moller", str(self.tmp / "moller"),
                      "--out", str(out), "--workers", "1"])
        self.assertEqual(rc, 0)
        with open(out / "corpus.csv", encoding="utf-8", newline="") as fh:
            corpus = list(csv.DictReader(fh))
        self.assertEqual([r["status"] for r in corpus], ["countable", "set_aside"])
        with open(out / "phenotype.csv", encoding="utf-8", newline="") as fh:
            phen = list(csv.DictReader(fh))
        self.assertEqual([(r["case"], r["phenotype"], r["countable"]) for r in phen],
                         [("made_up__a", "typical", "1")])
        self.assertTrue((out / "labels" / "made_up__a_label.nii.gz").exists())
        self.assertFalse((out / "labels" / "made_up__b_label.nii.gz").exists())


if __name__ == "__main__":
    unittest.main()
