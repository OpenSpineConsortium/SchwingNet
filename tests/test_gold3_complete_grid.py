"""tools/gold3_complete_grid.py: which studies the grid's completion asks for, how a census row is found
for a CT, why a study is left out, the report's lines, and, where nibabel is installed, the masks brought
onto the release's grid and a whole prepare over a crafted TotalSegmentator subject."""
from __future__ import annotations

import csv
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

try:
    import numpy as np
    import nibabel as nib
except ImportError:  # pragma: no cover
    np = nib = None


def load_tool():
    spec = importlib.util.spec_from_file_location("gold3_complete_grid", ROOT / "tools/gold3_complete_grid.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["gold3_complete_grid"] = module
    spec.loader.exec_module(module)
    return module


G = load_tool()


def facts_row(*names, voxels=500):
    return {"levels": {name: {"voxels": voxels} for name in names}}


class Targets(unittest.TestCase):
    def test_a_head_held_for_a_look_asks_for_c2_and_every_undrawn_name_above_the_top_level(self):
        self.assertEqual(G.head_targets(facts_row("C5", "C6", "C7", "T1")), ["C2", "C3", "C4"])
        self.assertEqual(G.head_targets(facts_row("C1", "C3")), ["C2"])
        # a level under the drawing floor is not drawn, and the sacrum never stands for the top
        self.assertEqual(G.head_targets({"levels": {"C3": {"voxels": 10}, "C4": {"voxels": 900}}}), ["C2", "C3"])
        self.assertEqual(G.head_targets(facts_row("sacrum")), [])

    def test_the_committed_admission_asks_for_43_studies_and_42_have_facts(self):
        # 27 VerSe (the 21 admitted, each its sacrum, and the 6 border cases' lists), 15 TotalSegmentator (11
        # admitted with levels to add, 4 of them on the CT's own planes since 2026-10-30, and the 4 border
        # cases those planes made) and ENHANCE.PET 1379, which has no facts row
        studies = G.studies_to_complete(ROOT / "data/gold3-ct/admission.json", ROOT / "data/gold3-ct")
        by_member = {}
        for study in studies:
            by_member[study["member"]] = by_member.get(study["member"], 0) + 1
            self.assertEqual(study["targets"], [n for n in G.ORDER if n in study["targets"]], study["id"])
            self.assertTrue(study["targets"], study["id"])
        self.assertEqual(by_member, {"verse": 27, "totalsegmentator": 15, "enhance_pet": 1})
        missing = [s["id"] for s in studies if not s["has_facts"]]
        self.assertEqual(missing, ["1379"])


class CensusRows(unittest.TestCase):
    def test_a_verse_row_is_found_by_its_series_and_a_totalsegmentator_row_by_its_id(self):
        self.assertEqual(G.verse_sid({"ct_path": "/x/VerSeFusion/sub-verse018/sub-verse018_dir-iso_scan-verse018_ct.nii.gz"}),
                         None if not G.VERSE_IN_PATH.search("scan-verse018_ct.") else "verse018")
        self.assertEqual(G.verse_sid({"spineps_vert": "/m/VERSE_verse033_seg-vert.nii.gz"}), "verse033")
        self.assertEqual(G.ts_id({"case_id": "ts:s1411"}), "s1411")
        self.assertEqual(G.ts_id({"ct_path": "/d/totalsegmentator_v300/s1532/ct.nii.gz"}), "s1532")
        self.assertEqual(G.ts_id({"spineps_vert": "/m/TSV3C_s1593_vert.nii.gz"}), "s1593")
        self.assertIsNone(G.ts_id({"case_id": "ts:1411"}))

    def test_the_first_row_of_a_ct_keeps_its_place_and_a_second_is_counted(self):
        rows = [{"case_id": "ts:s1411", "tier_file": "tier1.tsv"}, {"case_id": "ts:s1411", "tier_file": "tier2.tsv"},
                {"spineps_vert": "VERSE_verse018_x"}]
        index, doubled = G.index_rows(rows)
        self.assertEqual(index["totalsegmentator"]["s1411"]["tier_file"], "tier1.tsv")
        self.assertIn("verse018", index["verse"])
        self.assertEqual(doubled, [("totalsegmentator", "s1411")])

    def test_a_store_is_named_without_the_path_above_it(self):
        self.assertEqual(G.short_store("/rs/lab/go2432/ruleclass/spineps_v2/"), "ruleclass/spineps_v2")
        self.assertEqual(G.short_store("census"), "census")
        self.assertEqual(G.short_store(""), "unnamed")


class Releases(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)

    def test_a_release_that_is_not_on_the_grid_is_a_reason_not_a_path(self):
        path, why = G.release_of("verse", "verse018", str(self.dir), str(self.dir))
        self.assertIsNone(path)
        self.assertIn("verse_masks_2026_10_29", why)
        (self.dir / "s1411" / "segmentations").mkdir(parents=True)
        self.assertIn("no vertebrae_", G.release_of("totalsegmentator", "s1411", "", str(self.dir))[1])
        (self.dir / "s1411" / "segmentations" / "vertebrae_L1.nii.gz").write_bytes(b"")
        self.assertEqual(G.release_of("totalsegmentator", "s1411", "", str(self.dir)),
                         (str(self.dir / "s1411" / "segmentations"), None))
        self.assertIn("census holds no SPINEPS mask", G.release_of("enhance_pet", "1379", "", "")[1])


class Report(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)

    def test_the_report_counts_lists_every_study_and_names_each_refusal(self):
        inventory = {"guard": True, "doubled_rows": [],
                     "segmenter": {"name": "SPINEPS", "version_in_environment": "2.1.1"},
                     "studies": [{"id": "s1411", "member": "totalsegmentator", "state": "prepared", "targets": ["sacrum"],
                                  "source": {"store": "ruleclass/spineps", "ids": "verse_coded"},
                                  "grid": {"vertebrae": "same", "subregions": "same"}},
                                 {"id": "verse018", "member": "verse", "state": "prepared", "targets": ["C2", "sacrum"],
                                  "source": {"store": "ruleclass/spineps", "ids": "raw"},
                                  "grid": {"vertebrae": "resampled_nearest", "subregions": "resampled_nearest"}},
                                 {"id": "1379", "member": "enhance_pet", "state": "not_prepared", "targets": ["C2"],
                                  "reason": "member enhance_pet: not on the grid"}]}
        (self.dir / "inventory.json").write_text(json.dumps(inventory), encoding="ascii")
        (self.dir / "matcher").mkdir()
        records = [{"id": "s1411", "added": ["sacrum"], "refused": [], "files": {"arm": {"s1411_machine.nii.gz": {}}},
                    "targets": [{"name": "sacrum", "state": "added"}]},
                   {"id": "verse018", "added": [], "refused": ["C2", "sacrum"], "files": {},
                    "targets": [{"name": "C2", "state": "refused", "reason": "no anchor above C7"},
                                {"name": "sacrum", "state": "refused", "reason": "x" * 400}]}]
        (self.dir / "matcher" / "records.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records), encoding="ascii")
        out = self.run_report()
        self.assertIn("- studies asked: 3 (enhance_pet 1, totalsegmentator 2, verse 1)".replace("totalsegmentator 2, ", "totalsegmentator 1, "), out)
        self.assertIn("prepared for the matcher: 2; not prepared: 1", out)
        self.assertIn("studies with a level added: 1; levels added: 1; studies refused whole: 1; error rows: 0", out)
        self.assertIn("| s1411 | totalsegmentator | ruleclass/spineps | verse_coded | same | sacrum | sacrum | - | s1411_machine.nii.gz |", out)
        self.assertIn("| verse018 | verse | ruleclass/spineps | raw | resampled_nearest | C2 sacrum | - | C2 sacrum | - |", out)
        self.assertIn("| 1379 | enhance_pet | - | - | - | C2 | - | - | not run |", out)
        self.assertIn("- verse018 C2: no anchor above C7", out)
        self.assertIn("- verse018 sacrum: " + "x" * (G.REASON_CHARS - 3) + "...", out)
        self.assertIn("- 1379 (enhance_pet): member enhance_pet: not on the grid", out)

    def run_report(self):
        import io
        from contextlib import redirect_stdout
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(G.report(Namespace(out=str(self.dir))), 0)
        return buffer.getvalue()


@unittest.skipUnless(nib is not None, "nibabel is not installed")
class Grids(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.affine = np.diag([1.5, 1.5, 2.0, 1.0])
        self.affine[:3, 3] = [-30.0, -40.0, -500.0]
        self.data = np.zeros((6, 7, 20), np.int16)
        self.data[2:4, 2:5, 3:9] = 20
        self.data[2:4, 2:5, 11:17] = 26

    def test_a_mask_on_the_release_grid_is_kept_as_it_is(self):
        img = nib.Nifti1Image(self.data, self.affine + 0.001 * np.eye(4))
        out, how = G.onto_release_grid(img, self.data.shape, self.affine)
        self.assertEqual(how["grid"], "same")
        np.testing.assert_array_equal(np.asanyarray(out.dataobj), self.data)
        np.testing.assert_array_equal(out.affine, self.affine)

    def test_a_mask_stored_with_flipped_axes_is_reoriented_and_no_voxel_moves(self):
        flipped = self.data[::-1]
        affine = self.affine.copy()
        affine[0, 0] = -1.5
        affine[0, 3] = -30.0 + 1.5 * (self.data.shape[0] - 1)
        out, how = G.onto_release_grid(nib.Nifti1Image(flipped, affine), self.data.shape, self.affine)
        self.assertEqual(how["grid"], "reoriented")
        np.testing.assert_array_equal(np.asanyarray(out.dataobj), self.data)

    def test_a_mask_on_another_lattice_is_resampled_nearest_with_its_counts_recorded(self):
        coarse = self.data[:, :, ::2]
        affine = self.affine.copy()
        affine[2, 2] = 4.0
        out, how = G.onto_release_grid(nib.Nifti1Image(coarse, affine), self.data.shape, self.affine)
        self.assertEqual(how["grid"], "resampled_nearest")
        self.assertEqual(out.shape, self.data.shape)
        self.assertEqual(set(np.unique(np.asanyarray(out.dataobj))), {0, 20, 26})
        self.assertEqual(set(how["voxels_by_label_before"]), {20, 26})

    def test_prepare_writes_the_inputs_and_jobs_and_says_why_the_rest_are_left_out(self):
        ts_root, tiers, census, out = (self.dir / name for name in ("ts", "tiers", "census", "out"))
        segs = ts_root / "s1411" / "segmentations"
        segs.mkdir(parents=True)
        nib.save(nib.Nifti1Image((self.data == 20).astype(np.uint8), self.affine), segs / "vertebrae_L1.nii.gz")
        census.mkdir()
        nib.save(nib.Nifti1Image(self.data, self.affine), census / "TSV3C_s1411_vert.nii.gz")
        spine = np.where(self.data > 0, 49, 0).astype(np.int16)
        nib.save(nib.Nifti1Image(spine, self.affine), census / "TSV3C_s1411_spine.nii.gz")
        tiers.mkdir()
        fields = ["tier", "ct_path", "collection", "case_id", "spineps_vert", "spineps_spine", "spineps_ctd", "spineps_ids", "spineps_store"]
        with open(tiers / "tier1.tsv", "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields, delimiter="\t")
            writer.writeheader()
            writer.writerow({"tier": "1", "ct_path": str(ts_root / "s1411" / "ct.nii.gz"), "collection": "ts", "case_id": "ts:s1411",
                             "spineps_vert": str(census / "TSV3C_s1411_vert.nii.gz"), "spineps_spine": str(census / "TSV3C_s1411_spine.nii.gz"),
                             "spineps_ctd": "", "spineps_ids": "verse_coded", "spineps_store": str(census)})
        args = Namespace(admission=str(ROOT / "data/gold3-ct/admission.json"), facts=str(ROOT / "data/gold3-ct"), tiers=str(tiers),
                         verse_masks=str(self.dir / "none"), ts_root=str(ts_root), out=str(out), ssn=str(self.dir / "no-ssn"), python="")
        self.assertEqual(G.prepare(args), 0)
        jobs = json.loads((out / "jobs.json").read_text(encoding="ascii"))
        self.assertEqual([job["id"] for job in jobs["studies"]], ["s1411"])
        self.assertEqual(jobs["segmenter"]["version_in_environment"], "not read")
        record = json.loads((out / "prepared" / "s1411" / "input.json").read_text(encoding="ascii"))
        self.assertEqual(record["vertebrae_grid"]["grid"], "same")
        self.assertEqual(record["subregion_labels"], {"49": int((self.data > 0).sum()), "100": 0})
        inventory = json.loads((out / "inventory.json").read_text(encoding="ascii"))
        reasons = {e["id"]: e["reason"] for e in inventory["studies"] if e["state"] != "prepared"}
        self.assertEqual(len(reasons), 34)
        self.assertIn("census holds no SPINEPS mask", reasons["1379"])
        self.assertEqual(reasons["s1532"], "no census row for this CT in tier1.tsv or tier2.tsv")
        # no path under the data root reaches the report's store column
        self.assertEqual(record["source"]["store"], G.short_store(str(census)))


if __name__ == "__main__":
    unittest.main()
