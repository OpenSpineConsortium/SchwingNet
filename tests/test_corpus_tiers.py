"""tools/corpus_tiers.py: the owner's gold and silver tiers for one CT, a person counted once at
their best tier, the reading of a made-up column on the grid's masks, and the interval arithmetic
the power table uses. The column tests need numpy, nibabel and scipy, which the check's
environment may lack, so this is a plain unittest under tests/ and those tests skip without them."""
from __future__ import annotations

import csv
import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

try:
    import nibabel as nib
    import numpy as np
    import scipy  # noqa: F401
    HAVE_IMAGING = True
except ImportError:                                            # pragma: no cover
    HAVE_IMAGING = False

import bordercall_corpus as BC                                   # noqa: E402
import corpus_tiers as CT                                        # noqa: E402


class TheOwnersTiers(unittest.TestCase):
    def test_the_eight_names(self):
        self.assertEqual(CT.tier_name("gold", True, True), "gold1")
        self.assertEqual(CT.tier_name("gold", True, False), "gold2")
        self.assertEqual(CT.tier_name("gold", False, True), "gold3")
        self.assertEqual(CT.tier_name("gold", False, False), "gold4")
        self.assertEqual(CT.tier_name("silver", True, True), "silver1")
        self.assertEqual(CT.tier_name("silver", False, False), "silver4")
        with self.assertRaises(ValueError):
            CT.tier_name("bronze", False, False)

    def test_gold_comes_before_silver_and_one_before_four(self):
        self.assertEqual(CT.better("gold4", "silver1"), "gold4")
        self.assertEqual(CT.better("gold3", "gold2"), "gold2")
        self.assertEqual(CT.better("", "silver3"), "silver3")
        self.assertEqual(CT.better("silver2", ""), "silver2")

    def test_a_full_ct_alone_is_gold(self):
        self.assertEqual(CT.case_tiers(True, True, ""), ("gold3", ""))
        self.assertEqual(CT.case_tiers(True, False, ""), ("gold4", ""))
        self.assertEqual(CT.case_tiers(False, True, ""), ("silver3", ""))

    def test_a_pair_is_gold_only_when_both_images_show_the_whole_spine(self):
        self.assertEqual(CT.case_tiers(True, True, "full"), ("gold1", "gold1"))
        self.assertEqual(CT.case_tiers(True, False, "full"), ("gold2", "gold2"))
        # real C-arm frames show part of the spine: the pair is silver, the full CT alone still gold
        self.assertEqual(CT.case_tiers(True, True, "partial"), ("gold3", "silver1"))
        self.assertEqual(CT.case_tiers(False, False, "partial"), ("silver2", "silver2"))
        with self.assertRaises(ValueError):
            CT.case_tiers(True, True, "drr")

    def test_full_needs_the_count_from_c2_and_the_sacrum(self):
        self.assertEqual(CT.coverage_of({"status": "countable", "countable": 1, "has_sacrum": 1}), "full")
        self.assertEqual(CT.coverage_of({"status": "countable", "countable": "1", "has_sacrum": "0"}), "partial")
        self.assertEqual(CT.coverage_of({"status": "set_aside", "countable": 0, "has_sacrum": 1,
                                         "reason": "no C2 in the mask"}), "partial")
        self.assertEqual(CT.coverage_of({"status": "error", "reason": "OSError: x"}), "unknown")
        self.assertEqual(CT.coverage_of({"status": "set_aside", "reason": "mask file missing"}), "unknown")

    def test_annotation_comes_from_the_collection_and_an_unlisted_one_is_read_as_none(self):
        sources = {"census_collections": {"verse": {"human": "yes"}, "abdomenatlas3_mini": {"human": "no"}}}
        rec = CT.place({"case": "verse__1", "collection": "verse", "status": "countable", "countable": 1,
                        "has_sacrum": 1, "real_frames": ""}, sources)
        self.assertEqual((rec["coverage"], rec["human"], rec["tier"]), ("full", 1, "gold3"))
        rec = CT.place({"case": "x__1", "collection": "unlisted", "status": "countable", "countable": 1,
                        "has_sacrum": 0, "real_frames": "1"}, sources)
        self.assertEqual((rec["coverage"], rec["human"], rec["tier"], rec["pair_tier"]),
                         ("partial", 0, "silver2", "silver2"))
        self.assertEqual(CT.collection_facts(sources, "unlisted"),
                         {"human": False, "xr": "", "untrusted": False, "listed": False})

    def test_a_linked_partial_x_ray_pairs_as_silver_and_an_untrusted_collection_is_never_whole(self):
        sources = {"census_collections": {
            "cobra": {"human": "no", "xr_partial": True},
            "ctsp": {"human": "yes", "untrusted": True}}}
        rec = CT.place({"case": "cobra__1", "collection": "cobra", "status": "countable", "countable": 1,
                        "has_sacrum": 1, "real_frames": ""}, sources)
        self.assertEqual((rec["coverage"], rec["tier"], rec["pair_tier"]), ("full", "gold4", "silver2"))
        rec = CT.place({"case": "ctsp__1", "collection": "ctsp", "status": "countable", "countable": 1,
                        "has_sacrum": 1, "real_frames": ""}, sources)
        self.assertEqual((rec["coverage"], rec["untrusted"], rec["tier"]), ("partial", 1, "silver3"))

    def test_a_person_counts_once_at_their_best_tier(self):
        rows = [{"case": "a", "person_key": "p1", "tier": "silver4"},
                {"case": "b", "person_key": "p1", "tier": "gold4"},
                {"case": "c", "person_key": "", "tier": "silver3"},
                {"case": "d", "person_key": "p2", "tier": ""}]
        self.assertEqual(CT.best_by_person(rows), {"p1": "gold4", "c": "silver3", "p2": ""})


class TheIntervals(unittest.TestCase):
    def test_wilson_matches_the_published_example(self):
        lo, hi = CT.wilson(22, 83)                        # the select report's L6 sensitivity
        self.assertAlmostEqual(lo, 0.182, places=3)
        self.assertAlmostEqual(hi, 0.369, places=3)
        self.assertEqual(CT.wilson(0, 0), (0.0, 1.0))

    def test_no_error_in_n_bounds_the_rate_near_three_over_n(self):
        self.assertAlmostEqual(CT.zero_error_bound(300), 3 / 300, delta=0.0005)
        self.assertEqual(CT.zero_error_bound(0), 1.0)

    def test_persons_needed_is_the_least_n(self):
        n = CT.persons_needed(0.05, p=0.9)
        self.assertLessEqual(CT.half_width(0.9, n), 0.05)
        self.assertGreater(CT.half_width(0.9, n - 1), 0.05)


class TheCommittedTable(unittest.TestCase):
    def test_the_table_holds_together(self):
        sources = CT.load_sources()
        ids = [s["id"] for s in sources["sources"]]
        self.assertEqual(len(ids), len(set(ids)), "a source is listed twice")
        for s in sources["sources"]:
            tiers = s["tiers"]
            self.assertEqual(set(tiers) - {"outside", "unknown"}, set(CT.TIERS), s["id"])
            if s["status"] != "held":
                self.assertEqual(sum(tiers[k] for k in CT.TIERS), 0, "%s is not held, so it holds no one" % s["id"])
            if s.get("counted_in"):
                self.assertIn(s["counted_in"], ids, s["id"])
        for coll, facts in sources["census_collections"].items():
            self.assertIn(facts["human"], ("yes", "no", "some"), coll)

    def test_table_and_power_print(self):
        for cmd in ("table", "power"):
            buf = io.StringIO()
            with redirect_stdout(buf):
                self.assertEqual(CT.main([cmd]), 0)
            self.assertIn("gold1", buf.getvalue())


def column(ids, shape=(20, 20, 160), slab=6):
    arr = np.zeros(shape, np.int16)
    z = shape[2] - slab - 2
    for vid in ids:
        arr[4:16, 4:16, z:z + slab - 1] = vid
        z -= slab
    return arr


@unittest.skipUnless(HAVE_IMAGING, "numpy, nibabel and scipy are needed")
class TheCensus(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.min_voxels = BC.MIN_VOXELS
        BC.MIN_VOXELS = 100
        self.addCleanup(setattr, BC, "MIN_VOXELS", self.min_voxels)
        self.rows = []

    def add(self, collection, name, ids, person=None, real_frames=""):
        path = self.tmp / ("%s_seg-vert_msk.nii.gz" % name)
        nib.save(nib.Nifti1Image(column(ids), np.eye(4)), str(path))
        row = {k: "" for k in BC.TIER_COLUMNS}
        row.update(tier="1", collection=collection, case_id=name, person_key=person or "p:" + name,
                   spineps_vert=str(path), spineps_ids="verse_coded", spineps_store="test", real_frames=real_frames)
        self.rows.append(row)

    def test_whole_and_lumbar_columns_land_in_gold_and_silver(self):
        whole = list(range(1, 25)) + [26]                      # C1 to L5 and the sacrum
        self.add("verse", "whole", whole)
        self.add("verse", "lumbar", [17, 18, 19, 20, 21, 22, 23, 24, 26])
        self.add("abdomenatlas3_mini", "cut", list(range(1, 22)))   # from C1, no sacrum
        self.add("cobra", "paired", whole, real_frames="1")
        self.add("abdomenatlas3_mini", "again", whole, person="p:cut")
        tiers = self.tmp / "tiers"
        tiers.mkdir()
        with open(tiers / "tier1.tsv", "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(BC.TIER_COLUMNS), delimiter="\t")
            w.writeheader()
            w.writerows(self.rows)
        sources = self.tmp / "sources.json"
        sources.write_text(json.dumps({"sources": [], "census_collections": {
            "verse": {"human": "yes"}, "abdomenatlas3_mini": {"human": "no"}, "cobra": {"human": "no"}}}),
            encoding="utf-8")
        out = self.tmp / "out"
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = CT.main(["census", "--tiers", str(tiers), "--out", str(out), "--workers", "1",
                          "--sources", str(sources)])
        self.assertEqual(rc, 0, buf.getvalue())
        with open(out / "cases.csv", encoding="utf-8") as fh:
            cases = {r["case_id"]: r for r in csv.DictReader(fh)}
        self.assertEqual((cases["whole"]["coverage"], cases["whole"]["tier"]), ("full", "gold3"))
        self.assertEqual((cases["lumbar"]["coverage"], cases["lumbar"]["tier"]), ("partial", "silver3"))
        self.assertEqual((cases["cut"]["coverage"], cases["cut"]["tier"]), ("partial", "silver4"))
        self.assertEqual((cases["paired"]["tier"], cases["paired"]["pair_tier"]), ("gold4", "silver2"))
        report = buf.getvalue()
        self.assertIn("CTs read 5: full 3, partial 2, unknown 0", report)
        self.assertIn("persons 4,", report)                    # p:cut has two CTs and counts once, as gold4
        self.assertRegex(report, r"gold4\s+2")


if __name__ == "__main__":
    unittest.main()
