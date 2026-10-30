"""tools/gold3_totalseg_grid.py: the studies it asks for, where it looks for their files, the
check of each drawn target against the release's own levels, and the report that leaves the grid.

The check reads masks through nibabel, which this container may not have; where it is missing a
stub that gives an image its data and affine stands in, so the geometry is tested on numpy alone.
numpy itself is needed for those tests and they are skipped without it.
"""
import contextlib
import io
import json
import os
import re
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import gold3_totalseg_grid as tool  # noqa: E402

try:
    import numpy as np
except ImportError:                                             # pragma: no cover
    np = None


class Studies(unittest.TestCase):
    def test_the_committed_admission_asks_for_c2_or_the_sacrum_where_its_completion_lists_them(self):
        asked = tool.studies_asked(ROOT / "data" / "gold3-ct" / "admission.json")
        by_member = {}
        for study in asked:
            by_member[study["member"]] = by_member.get(study["member"], 0) + 1
            self.assertTrue(set(study["targets"]) <= {"C2", "sacrum"}, study)
            self.assertIn(study["verdict"], ("admitted", "look"))
            for target in study["targets"]:
                self.assertIn(target, study["complete"])
        # VerSe never draws the sacrum, so every admitted or held series asks for it; the ten
        # TotalSegmentator subjects and ENHANCE.PET's 1379 ask for what their releases left out.
        self.assertEqual(by_member, {"verse": 27, "totalsegmentator": 10, "enhance_pet": 1}, by_member)
        self.assertEqual([s["id"] for s in asked if s["member"] == "enhance_pet"], ["1379"])
        # each release's own segmenter draws for it (the owner, 2026-10-30 09:33 UTC)
        self.assertEqual({s["member"]: s["segmenter"] for s in asked},
                         {"verse": "TotalSegmentator", "totalsegmentator": "TotalSegmentator", "enhance_pet": "MOOSE"})

    def test_mooses_ids_are_the_buckets_and_the_segmenter_tables_and_the_release_ids_are_each_schemes(self):
        # the ids run cuts MOOSE's multilabel by, and writes ENHANCE.PET's arm files at, are the
        # vertebrae model's in the bucket's labels.json copy (read leniently: the copy carries a
        # trailing comma) and in schwingnet.segmenters' table
        text = (ROOT / "grid" / "enhance-pet-labels.json").read_text(encoding="utf-8")
        bucket = json.loads(re.sub(r",(\s*[}\]])", r"\1", text))["clin_ct_vertebrae"]
        for target, value in tool.MOOSE_IDS.items():
            self.assertEqual(bucket[str(value)], tool.MOOSE_NAMES[target], (target, value))
        sys.path.insert(0, str(ROOT / "src"))
        try:
            from schwingnet import segmenters
        except ImportError:
            segmenters = None
        if segmenters is not None:
            table = segmenters.MOOSEZ_MODELS["clin_ct_vertebrae"]
            for target, value in tool.MOOSE_IDS.items():
                self.assertEqual(table[value], tool.MOOSE_NAMES[target])
            self.assertEqual(segmenters.VERSE_IDS["C2"] if hasattr(segmenters, "VERSE_IDS") else 2, 2)
        self.assertEqual(tool.RELEASE_IDS["verse"], {"C2": 2, "sacrum": 26})
        self.assertEqual(tool.RELEASE_IDS["enhance_pet"], tool.MOOSE_IDS)
        self.assertEqual(tool.RELEASE_IDS["totalsegmentator"], {"C2": 1, "sacrum": 1})

    def test_a_study_that_asks_for_other_levels_alone_or_is_not_admitted_is_left_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "admission.json"
            path.write_text(json.dumps({"studies": [
                {"member": "verse", "id": "a", "verdict": "admitted", "complete": ["L5"]},
                {"member": "verse", "id": "b", "verdict": "not_admitted", "complete": ["sacrum"]},
                {"member": "verse", "id": "c", "verdict": "look", "complete": ["C2", "C3"]},
                {"member": "verse", "id": "d", "verdict": "admitted"},
            ]}), encoding="utf-8")
            asked = tool.studies_asked(path)
        self.assertEqual([(s["id"], s["targets"]) for s in asked], [("c", ["C2"])])


class Locate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        tool._TS_FOLDERS.clear()
        tool._FILES.clear()

    def touch(self, *parts):
        path = self.tmp.joinpath(*parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
        return str(path)

    def test_each_member_is_found_where_its_release_lies_and_refused_with_a_reason_otherwise(self):
        ts_root = self.tmp / "totalsegmentator_v300"
        nested_ct = self.touch("totalsegmentator_v300", "Totalsegmentator_dataset_v201", "s0102", "ct.nii.gz")
        self.touch("totalsegmentator_v300", "Totalsegmentator_dataset_v201", "s0102", "segmentations", "vertebrae_L1.nii.gz")
        self.touch("totalsegmentator_v300", "s0437", "ct.nii.gz")
        verse_ct = self.touch("verse", "scan-verse607_ct.nii.gz")
        verse_masks = self.tmp / "verse_masks_2026_10_29" / "masks"
        self.touch("verse_masks_2026_10_29", "masks", "verse607.nii.gz")
        enhance_ct = self.tmp / "aws_enhance_pet_ct" / "raw"
        enhance_labels = self.tmp / "aws_enhance_pet_labels" / "raw"
        self.touch("aws_enhance_pet_ct", "raw", "autopet", "1379.nii.gz")
        self.touch("aws_enhance_pet_labels", "raw", "autopet", "Ribs", "1379.nii.gz")
        self.touch("aws_enhance_pet_labels", "raw", "autopet", "Vertebrae", "1379.nii.gz")
        args = (str(ts_root), str(enhance_ct), str(enhance_labels), str(verse_masks))
        cts = {"verse607": verse_ct}

        ct, release, why = tool.locate({"member": "totalsegmentator", "id": "s0102"}, cts, *args)
        self.assertIsNone(why)
        self.assertEqual(ct, nested_ct)
        self.assertTrue(release.endswith(os.path.join("s0102", "segmentations")))
        ct, release, why = tool.locate({"member": "totalsegmentator", "id": "s0437"}, cts, *args)
        self.assertIn("no segmentations/ folder", why)
        ct, release, why = tool.locate({"member": "totalsegmentator", "id": "s9999"}, cts, *args)
        self.assertIn("no folder of the subject's name", why)

        ct, release, why = tool.locate({"member": "verse", "id": "verse607"}, cts, *args)
        self.assertIsNone(why)
        self.assertEqual((ct, Path(release).name), (verse_ct, "verse607.nii.gz"))
        ct, release, why = tool.locate({"member": "verse", "id": "verse999"}, cts, *args)
        self.assertIn("no census row", why)
        cts["verse608"] = verse_ct
        ct, release, why = tool.locate({"member": "verse", "id": "verse608"}, cts, *args)
        self.assertIn("no int16 copy", why)

        ct, release, why = tool.locate({"member": "enhance_pet", "id": "1379"}, cts, *args)
        self.assertIsNone(why)
        self.assertEqual(Path(release).parent.name, "Vertebrae")
        ct, release, why = tool.locate({"member": "enhance_pet", "id": "1"}, cts, *args)
        self.assertIn("no CT of the study's id", why)

    def test_prepare_writes_jobs_json_with_store_names_and_no_data_root_path_in_its_summary(self):
        self.touch("totalsegmentator_v300", "s0102", "ct.nii.gz")
        self.touch("totalsegmentator_v300", "s0102", "segmentations", "vertebrae_L1.nii.gz")
        admission = self.tmp / "admission.json"
        admission.write_text(json.dumps({"studies": [
            {"member": "totalsegmentator", "id": "s0102", "verdict": "admitted", "complete": ["C2", "sacrum"]},
            {"member": "totalsegmentator", "id": "s0437", "verdict": "look", "complete": ["sacrum"]},
        ]}), encoding="utf-8")
        out = self.tmp / "out"
        args = types.SimpleNamespace(admission=str(admission), tiers="", ts_root=str(self.tmp / "totalsegmentator_v300"),
                                     enhance_ct=str(self.tmp / "none"), enhance_labels=str(self.tmp / "none"),
                                     verse_masks=str(self.tmp / "verse_masks_2026_10_29" / "masks"), out=str(out))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(tool.prepare(args), 0)
        jobs = json.loads((out / "jobs.json").read_text(encoding="utf-8"))
        self.assertEqual((jobs["asked"], jobs["prepared"], jobs["not_prepared"]), (2, 1, 1))
        self.assertEqual(jobs["studies"][0]["ct_store"], "totalsegmentator_v300")
        self.assertEqual(jobs["studies"][0]["targets"], ["C2", "sacrum"])
        self.assertEqual(jobs["left_out"][0]["id"], "s0437")
        self.assertEqual(jobs["segmenter"], "TotalSegmentator")
        self.assertEqual(jobs["task"]["roi_subset"], ["vertebrae_C2", "sacrum"])
        self.assertEqual(jobs["studies"][0]["segmenter"], "TotalSegmentator")
        # the report, with nothing run yet, lists the prepared study as not run and names no path
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(tool.report(types.SimpleNamespace(out=str(out))), 0)
        text = (out / "REPORT.md").read_text(encoding="utf-8")
        self.assertIn("studies asked: 2 (totalsegmentator 2); prepared: 1; not prepared: 1", text)
        self.assertIn("| s0102 | totalsegmentator | TotalSegmentator | totalsegmentator_v300 | C2 sacrum | - | - | not run |", text)
        self.assertIn("| s0437 | totalsegmentator | TotalSegmentator | - | sacrum | - | - | not prepared |", text)
        self.assertIn("- s0437 (totalsegmentator): no folder of the subject's name", text)
        self.assertNotIn(str(self.tmp), text)


class FakeImage:
    def __init__(self, data, affine):
        self.dataobj = data
        self.affine = affine


def stub_nibabel(images):
    """A nibabel whose load gives the image a test placed under the path."""
    module = types.ModuleType("nibabel")
    module.load = lambda path: images[str(path)]
    return module


@unittest.skipIf(np is None, "numpy is needed to draw the masks")
class Check(unittest.TestCase):
    """The release's levels are stacked along the world's vertical: labels 1..3 at z 0 to 30 mm
    (index k 0 to 29, 1 mm voxels), so a C2 drawn above and a sacrum drawn below are kept."""

    def setUp(self):
        self.had = sys.modules.get("nibabel")
        self.images = {}
        if self.had is None:
            sys.modules["nibabel"] = stub_nibabel(self.images)
        else:                                                   # pragma: no cover
            self.skipTest("nibabel is installed; these tests exercise the stub path on numpy alone")
        self.addCleanup(self.restore)
        self.affine = np.eye(4)
        self.release = np.zeros((4, 4, 60), dtype=np.int16)
        self.release[:, :, 0:10] = 3
        self.release[:, :, 10:20] = 2
        self.release[:, :, 20:30] = 1
        self.images["release"] = FakeImage(self.release, self.affine)

    def restore(self):
        if self.had is None:
            sys.modules.pop("nibabel", None)

    def mask(self, name, lo, hi, affine=None, shape=(4, 4, 60)):
        data = np.zeros(shape, dtype=np.uint8)
        data[:, :, lo:hi] = 1
        self.images[name] = FakeImage(data, self.affine if affine is None else affine)
        return name

    def test_a_c2_above_the_topmost_level_and_a_sacrum_below_the_lowest_are_kept_with_their_gaps(self):
        levels, affine = tool.release_levels("release")
        self.assertEqual([n for n, _ in levels], ["label 1", "label 2", "label 3"])
        c2 = tool.check_target("C2", self.mask("c2", 34, 50), levels, affine, ["C2", "C3", "sacrum"])
        self.assertTrue(c2["kept"], c2)
        self.assertEqual((c2["nearest_release_level"], c2["gap_mm"], c2["undrawn_between"]), ("label 1", 5.0, ["C3"]))
        self.assertEqual(c2["voxels"], 16 * 16)
        sacrum = tool.check_target("sacrum", self.mask("sacrum", 0, 0), levels, affine, ["sacrum"])
        self.assertFalse(sacrum["kept"])
        self.assertIn("under 200", sacrum["reason"])

    def test_a_target_on_the_releases_own_levels_or_on_the_wrong_side_is_refused(self):
        levels, affine = tool.release_levels("release")
        over = tool.check_target("sacrum", self.mask("over", 5, 25), levels, affine, ["sacrum"])
        self.assertFalse(over["kept"])
        self.assertIn("lie on the release's own levels", over["reason"])
        # a sacrum drawn clear of the levels but above them all is on the wrong side
        above = tool.check_target("sacrum", self.mask("above", 40, 55), levels, affine, ["sacrum"])
        self.assertFalse(above["kept"])
        self.assertIn("wrong side", above["reason"])
        self.assertIn("lowest", above["reason"])
        # the sacrum's side reads from the affine, not the index: flipped, index 40..55 lies below
        flipped = np.diag([1.0, 1.0, -1.0, 1.0])
        levels_flipped = [(n, m) for n, m in levels]
        below = tool.check_target("sacrum", self.mask("below", 40, 55, affine=flipped), levels_flipped, flipped, ["sacrum"])
        self.assertTrue(below["kept"], below)

    def test_a_mask_off_the_releases_grid_is_refused_before_any_overlap_is_read(self):
        levels, affine = tool.release_levels("release")
        other = tool.check_target("C2", self.mask("other", 34, 50, shape=(4, 4, 61)), levels, affine, ["C2"])
        self.assertFalse(other["kept"])
        self.assertIn("not the release masks' grid", other["reason"])
        moved = np.eye(4)
        moved[0, 3] = 2.0
        shifted = tool.check_target("C2", self.mask("shifted", 34, 50, affine=moved), levels, affine, ["C2"])
        self.assertIn("not the release masks' grid", shifted["reason"])


class Report(unittest.TestCase):
    def test_the_report_counts_kept_and_refused_targets_and_cuts_every_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "jobs.json").write_text(json.dumps({
                "asked": 3, "prepared": 2, "not_prepared": 1,
                "studies": [{"member": "verse", "id": "verse607", "verdict": "admitted", "targets": ["sacrum"], "complete": ["sacrum"],
                             "segmenter": "TotalSegmentator", "ct": "/x", "release": "/y", "ct_store": "versefusion", "release_store": "verse_masks_2026_10_29"},
                            {"member": "totalsegmentator", "id": "s0102", "verdict": "look", "targets": ["C2", "sacrum"], "segmenter": "TotalSegmentator",
                             "complete": ["C2", "sacrum"], "ct": "/x", "release": "/y", "ct_store": "totalsegmentator_v300",
                             "release_store": "totalsegmentator_v300"},
                            {"member": "enhance_pet", "id": "1380", "verdict": "admitted", "targets": ["C2"], "segmenter": "MOOSE",
                             "complete": ["C2"], "ct": "/x", "release": "/y", "ct_store": "aws_enhance_pet_ct", "release_store": "aws_enhance_pet_labels"}],
                "left_out": [{"member": "enhance_pet", "id": "1379", "targets": ["C2"], "reason": "no CT of the study's id under aws_enhance_pet_ct"}],
            }), encoding="utf-8")
            records = [
                {"id": "verse607", "member": "verse", "ct_store": "versefusion", "version": "2.18.0", "segmenter": "TotalSegmentator", "label_scheme": "VerSe label ids",
                 "targets": {"sacrum": {"kept": True, "voxels": 5000, "gap_mm": 3.2, "nearest_release_level": "label 24", "label_value": 26,
                                        "undrawn_between": [], "file": "verse607_totalsegmentator_sacrum_abc123def456.nii.gz"}}},
                {"id": "s0102", "member": "totalsegmentator", "ct_store": "totalsegmentator_v300", "version": "2.18.0", "segmenter": "TotalSegmentator",
                 "targets": {"C2": {"kept": False, "reason": "x" * 300}, "sacrum": {"kept": False, "reason": "TotalSegmentator wrote no file for it"}}},
                {"id": "1380", "member": "enhance_pet", "ct_store": "aws_enhance_pet_ct", "version": "3.2.2", "segmenter": "MOOSE",
                 "error": "moose-one ended 1: no zip"},
            ]
            (out / "records.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(tool.report(types.SimpleNamespace(out=str(out))), 0)
            text = (out / "REPORT.md").read_text(encoding="utf-8")
        self.assertIn("studies asked: 3 (enhance_pet 2, totalsegmentator 1, verse 1); prepared: 2; not prepared: 1", text)
        self.assertIn("segmenters: TotalSegmentator 2.18.0 (task total, roi_subset vertebrae_C2 sacrum) for verse, totalsegmentator; MOOSE 3.2.2 (clin_ct_vertebrae) for enhance_pet", text)
        self.assertIn("targets kept: 1 (0 C2, 1 sacrum) in 1 studies; targets refused: 2; studies in error: 1", text)
        self.assertIn("| verse607 | verse | TotalSegmentator | versefusion | sacrum | - | kept | verse607_totalsegmentator_sacrum_abc123def456.nii.gz |", text)
        self.assertIn("| s0102 | totalsegmentator | TotalSegmentator | totalsegmentator_v300 | C2 sacrum | refused | refused | - |", text)
        self.assertIn("| 1380 | enhance_pet | MOOSE | aws_enhance_pet_ct | - | - | - | error |", text)
        self.assertIn("- verse607 sacrum: 5000 voxels, gap 3.2 mm to label 24, undrawn between: none; written at id 26 (VerSe label ids)", text)
        self.assertIn("- 1380: moose-one ended 1: no zip", text)
        self.assertIn("- s0102 C2: " + "x" * 157 + "...", text)
        self.assertIn("- 1379 (enhance_pet): no CT of the study's id", text)
        self.assertNotIn("/x", text)


if __name__ == "__main__":
    unittest.main()
