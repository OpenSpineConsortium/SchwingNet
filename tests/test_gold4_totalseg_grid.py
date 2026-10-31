"""tools/gold4_totalseg_grid.py: which census rows become units and why the rest are left out, how the
tasks of an array share the units, when a unit is passed over or given up, the weights guard, each
unit's kind against SPINEPS, and, where numpy and nibabel are installed, the label maps turned into
VerSe's ids and a whole run and merge over crafted CTs with a stand-in segmenter."""
from __future__ import annotations

import csv
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None
try:
    import nibabel as nib
except ImportError:  # pragma: no cover
    nib = None


def load_tool():
    spec = importlib.util.spec_from_file_location("gold4_totalseg_grid", ROOT / "tools/gold4_totalseg_grid.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["gold4_totalseg_grid"] = module
    spec.loader.exec_module(module)
    return module


G = load_tool()
TIER_FIELDS = ["tier", "ct_path", "collection", "case_id", "person_key", "spineps_vert", "spineps_ids"]


def census_row(collection, case, mask, verdict="admitted", person="", head="drawn", foot="drawn"):
    """A row of the census's gold4.json as its part gold4 writes it: the tier list's row and the field test's verdict."""
    return {"tier": "1", "collection": collection, "case_id": case, "person_key": person, "spineps_vert": mask,
            "spineps_ids": "verse", "verdict": verdict, "head": head, "foot": foot, "complete": True, "flags": []}


def write_tiers(folder, rows, name="tier1.tsv"):
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / name, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=TIER_FIELDS, delimiter="\t")
        writer.writeheader()
        for mask, ct in rows:
            writer.writerow({"tier": "1", "ct_path": ct, "collection": "x", "case_id": "x", "person_key": "",
                             "spineps_vert": mask, "spineps_ids": "verse"})


def spine_facts(names=None, step=30.0, voxels=1000, **moved):
    """Level facts of a straight spine down the z axis, C1 at the top, every level a step apart; a
    level named in moved takes the centre given."""
    names = names or [*G.TS_VERTEBRAE, "sacrum"]
    facts = {name: {"voxels": voxels, "centroid": [0.0, 0.0, -step * i]} for i, name in enumerate(names)}
    for name, centre in moved.items():
        facts[name] = {"voxels": voxels, "centroid": centre}
    return facts


class Selection(unittest.TestCase):
    """The census's rows read into units: one a CT, in a fixed order, every other row counted by its reason."""

    def setUp(self):
        self.rows = [
            census_row("AbdomenAtlas", "a1", "/m/a1.nii.gz", person="p1"),
            census_row("AbdomenAtlas", "a1b", "/m/a1-second.nii.gz"),          # a second mask of a1's CT
            census_row("ts", "ts:s0001", "/m/ts1.nii.gz"),                       # TotalSegmentator's own subject
            census_row("TotalSegmentator_v2", "s2", "/m/ts2.nii.gz"),            # a release by its collection
            census_row("IDC_x", "c9", "/m/TSV3_s0123_vert.nii.gz"),             # a release by its mask's name
            census_row("verse2020", "v1", "/m/v1.nii.gz"),
            census_row("FDG-PET-CT-Lesions", "f1", "/m/f1.nii.gz"),
            census_row("CT-ORG", "o1", "/m/o1.nii.gz"),                          # no tier row
            census_row("CT-ORG", "o2", "/m/o2.nii.gz"),                          # its CT is DICOM
            census_row("CT-ORG", "o3", "/m/o3.nii.gz"),                          # its CT is not there
            census_row("CT-ORG", "o4", "/m/o4.nii.gz"),                          # its mask is not there
            census_row("CT-ORG", "o5", "/m/o5.nii.gz", verdict="outside"),        # not admitted
            {"collection": "CT-ORG", "case_id": "o6", "spineps_vert": "/m/o6.nii.gz", "set_aside": "raw ids"},
            census_row("IDC_nlst", "n1", "/m/n1.nii.gz", verdict="look"),
            census_row("CArmLSpine", "case134", "/m/c134.nii.gz"),
        ]
        self.ct_of = {"/m/a1.nii.gz": "/c/a1.nii.gz", "/m/a1-second.nii.gz": "/c/a1.nii.gz", "/m/ts1.nii.gz": "/c/ts1.nii.gz",
                      "/m/o2.nii.gz": "/c/o2.dcm", "/m/o3.nii.gz": "/c/o3.nii.gz", "/m/o4.nii.gz": "/c/o4.nii.gz",
                      "/m/n1.nii.gz": "/c/n1.nii", "/m/c134.nii.gz": "/c/c134.nii.gz", "/m/f1.nii.gz": "/c/f1.nii.gz"}
        self.there = {"/c/a1.nii.gz", "/m/a1.nii.gz", "/c/o4.nii.gz", "/c/n1.nii", "/m/n1.nii.gz", "/c/c134.nii.gz", "/m/c134.nii.gz"}

    def select(self, rows=None):
        return G.select(rows or self.rows, self.ct_of, exists=self.there.__contains__)

    def test_one_unit_a_ct_in_a_fixed_order_and_every_other_row_counted_by_its_reason(self):
        units, left_out, by_collection, candidates = self.select()
        self.assertEqual([u["case_id"] for u in units], ["a1", "case134", "n1"])
        self.assertEqual(candidates, 13)
        self.assertEqual(dict(left_out), {"second_mask": 1, "release": 4, "fdg": 1, "no_tier_row": 1, "not_nifti": 1,
                                          "no_ct": 1, "no_spineps": 1})
        self.assertEqual(dict(by_collection["release"]), {"ts": 1, "TotalSegmentator_v2": 1, "idc": 1, "verse2020": 1})
        self.assertEqual(dict(by_collection["fdg"]), {"FDG-PET-CT-Lesions": 1})

    def test_a_unit_is_named_by_its_ct_and_carries_what_the_census_said(self):
        units, *_ = self.select()
        a1 = units[0]
        self.assertEqual(a1["id"], G.unit_id("/c/a1.nii.gz"))
        self.assertEqual(len(a1["id"]), 16)
        self.assertEqual((a1["ct"], a1["spineps"], a1["person_key"]), ("/c/a1.nii.gz", "/m/a1.nii.gz", "p1"))
        self.assertEqual(a1["census"]["verdict"], "admitted")
        self.assertEqual(units[2]["group"], "idc")
        self.assertEqual(units[2]["census"]["verdict"], "look")

    def test_c_armlspine_is_segmented_and_marked_held_out(self):
        units, *_ = self.select()
        self.assertEqual({u["case_id"]: u["held_out"] for u in units}, {"a1": False, "case134": True, "n1": False})

    def test_the_census_order_changes_nothing(self):
        first = self.select()
        again = self.select(list(reversed(self.rows)))
        self.assertEqual(json.dumps(first[0]), json.dumps(again[0]))
        self.assertEqual(first[1], again[1])

    def test_a_release_is_read_from_its_collection_its_case_or_its_masks_name(self):
        self.assertTrue(G.release_study({"collection": "TS", "case_id": "x", "spineps_vert": ""}))
        self.assertTrue(G.release_study({"collection": "verse19", "case_id": "x", "spineps_vert": ""}))
        self.assertTrue(G.release_study({"collection": "other", "case_id": "ts:s1234", "spineps_vert": ""}))
        self.assertTrue(G.release_study({"collection": "other", "case_id": "x", "spineps_vert": "/m/VERSE_gl003_vert.nii.gz"}))
        self.assertTrue(G.release_study({"collection": "other", "case_id": "x", "spineps_vert": "/m/TSV3C_s0007_vert.nii.gz"}))
        self.assertFalse(G.release_study({"collection": "CT-ORG", "case_id": "x", "spineps_vert": "/m/tsv3.nii.gz"}))

    def test_selection_reads_the_files_and_is_the_same_bytes_from_every_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            census = tmp / "gold4.json"
            census.write_text(json.dumps({"rows": self.rows}), encoding="utf-8")
            write_tiers(tmp / "tiers", list(self.ct_of.items()))
            first = G.selection(str(census), str(tmp / "tiers"), exists=self.there.__contains__)
            again = G.selection(str(census), str(tmp / "tiers"), exists=self.there.__contains__)
            self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(again, sort_keys=True))
            self.assertEqual(len(first["units"]), 3)
            self.assertEqual(first["census_sha256"], G.sha256_of(census))
            self.assertEqual(sorted(first["tiers"]), ["tier1.tsv"])
            self.assertEqual(first["task"]["roi_subset"], list(G.VERSE_ID))

    def test_a_missing_census_or_tier_list_stops_the_run_in_words(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            with self.assertRaisesRegex(G.InputsMissing, "census gold3"):
                G.read_census(str(tmp / "gold4.json"))
            (tmp / "bad.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(G.InputsMissing, "no list of rows"):
                G.read_census(str(tmp / "bad.json"))
            with self.assertRaisesRegex(G.InputsMissing, "tier list"):
                G.read_tiers(str(tmp))

    def test_a_masks_first_tier_row_keeps_its_place(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            write_tiers(tmp, [("/m/a.nii.gz", "/c/first.nii.gz")], "tier1.tsv")
            write_tiers(tmp, [("/m/a.nii.gz", "/c/second.nii.gz"), ("/m/b.nii.gz", "/c/b.nii.gz")], "tier2.tsv")
            ct_of, read = G.read_tiers(str(tmp))
        self.assertEqual(ct_of, {"/m/a.nii.gz": "/c/first.nii.gz", "/m/b.nii.gz": "/c/b.nii.gz"})
        self.assertEqual(sorted(read), ["tier1.tsv", "tier2.tsv"])


class Sharing(unittest.TestCase):
    """The tasks of one chain share the list: each starts at its own place, and a claim is taken once."""

    def test_each_task_starts_at_its_own_place_and_goes_round_the_whole_list(self):
        units = list(range(10))
        starts = [G.rotated(units, task, 4)[0] for task in range(4)]
        self.assertEqual(starts, [0, 2, 5, 7])
        for task in range(4):
            self.assertEqual(sorted(G.rotated(units, task, 4)), units)
        self.assertEqual(G.rotated([], 3, 16), [])
        self.assertEqual([G.rotated([0, 1], task, 16)[0] for task in (0, 7, 8, 15)], [0, 0, 1, 1])

    def test_a_unit_is_claimed_by_one_task_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "claims"
            self.assertTrue(G.claim(folder, "abc", 0))
            self.assertFalse(G.claim(folder, "abc", 1))
            self.assertTrue(G.claim(folder, "abd", 1))
            self.assertIn("task 0", (folder / "abc").read_text(encoding="utf-8"))

    def test_a_unit_is_segmented_only_where_its_run_ended_0_and_its_map_stands(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(G.segmented(tmp, "u1", {"exit": 0}))
            G.labels_path(tmp, "u1").parent.mkdir(parents=True)
            G.labels_path(tmp, "u1").write_bytes(b"x")
            self.assertTrue(G.segmented(tmp, "u1", {"exit": 0}))
            self.assertFalse(G.segmented(tmp, "u1", {"exit": 1}))
            self.assertFalse(G.segmented(tmp, "u1", {"exit": None}))

    def test_failures_count_at_one_code_and_a_run_that_ended_mid_unit_counts_once_its_chain_is_over(self):
        failed = {"exit": 1, "chain": "11", "commit": "c1", "failed": [{"chain": "10", "commit": "c1"}, {"chain": "11", "commit": "c1"}]}
        self.assertEqual(G.failures_of(failed, "c1"), {"10", "11"})
        self.assertTrue(G.given_up(failed, "c1"))
        self.assertEqual(G.failures_of(failed, "c2"), set())
        self.assertFalse(G.given_up(failed, "c2"))
        killed = {"exit": None, "chain": "12", "commit": "c1", "failed": [{"chain": "10", "commit": "c1"}]}
        self.assertEqual(G.failures_of(killed, "c1", running="12"), {"10"})
        self.assertEqual(G.failures_of(killed, "c1", running="13"), {"10", "12"})
        self.assertTrue(G.given_up(killed, "c1"))
        self.assertEqual(G.failures_of({"exit": 0, "failed": [{"chain": "10", "commit": "c1"}]}, "c1"), set())
        self.assertEqual(G.failures_of(None, "c1"), set())


class Weights(unittest.TestCase):
    def test_the_parts_needed_must_be_whole_and_the_guard_refuses_any_other_part_the_folder_lacks(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "Dataset292_TotalSegmentator_part2_vertebrae_1792subj").mkdir()
            (Path(tmp) / "Dataset292_TotalSegmentator_part2_vertebrae_1792subj" / "UNPACKED").write_text("", encoding="utf-8")
            (Path(tmp) / "Dataset298_TotalSegmentator_total_6mm_1559subj").mkdir()
            self.assertTrue(G.has_part(tmp, 292, whole=True))
            self.assertTrue(G.has_part(tmp, 298))
            self.assertFalse(G.has_part(tmp, 298, whole=True))
            self.assertFalse(G.has_part(tmp, 29))
            self.assertFalse(G.has_part("", 292))
            guard = G.weights_guard(tmp)
            self.assertIsNone(guard(292))
            self.assertIsNone(guard(task_id=291))
            for part in G.PARTS_NOT_COMPUTED:
                self.assertIsNone(guard(part))
            with self.assertRaisesRegex(RuntimeError, "downloads nothing"):
                guard(296)


class Kinds(unittest.TestCase):
    """A unit's kind against SPINEPS, from each level's centre alone."""

    def test_two_maps_naming_every_bone_alike_are_concordant(self):
        self.assertEqual(G.judge(spine_facts(), spine_facts()), "concordant")
        # C1 lies above the field the census admitted, so SPINEPS leaving it out changes nothing
        theirs = spine_facts()
        del theirs["C1"]
        self.assertEqual(G.judge(spine_facts(), theirs), "concordant")

    def test_no_c2_no_sacrum_and_a_sacrum_above_the_lumbar_spine_come_first(self):
        ours = spine_facts()
        del ours["C2"]
        self.assertEqual(G.judge(ours, spine_facts()), "no_c2")
        ours = spine_facts()
        ours["sacrum"]["voxels"] = G.MIN_VOXELS - 1
        self.assertEqual(G.judge(ours, spine_facts()), "no_sacrum")
        self.assertEqual(G.judge(spine_facts(sacrum=[0.0, 0.0, -100.0]), spine_facts()), "sacrum_above")
        self.assertEqual(G.judge(spine_facts(), None), "no_comparison")

    def test_spineps_drawing_a_t13_or_an_l6_is_a_variant(self):
        names = [*G.TS_VERTEBRAE[:19], "T13", *G.TS_VERTEBRAE[19:], "sacrum"]
        self.assertEqual(G.judge(spine_facts(), spine_facts(names)), "variant")

    def test_one_bone_with_two_names_is_a_name_shift_and_a_bone_alone_is_unmatched(self):
        names = [*G.TS_VERTEBRAE, "sacrum"]
        shifted = {names[i + 1]: f for i, f in enumerate(spine_facts().values()) if i + 1 < len(names) and names[i + 1] != "sacrum"}
        shifted["sacrum"] = spine_facts()["sacrum"]
        self.assertEqual(G.judge(spine_facts(), shifted), "name_shift")
        theirs = spine_facts()
        del theirs["L3"]
        self.assertEqual(G.judge(spine_facts(), theirs), "unmatched")

    def test_a_level_above_the_top_of_the_others_field_is_coverage_and_one_below_it_is_not(self):
        theirs = spine_facts()
        for name in ("C2", "C3"):                      # SPINEPS's field shows C2's foot alone, and its head-most level is C4
            del theirs[name]
        self.assertEqual(G.judge(spine_facts(), theirs), "concordant")
        ours = spine_facts()
        ours["C2"]["voxels"] = G.MIN_VOXELS            # TotalSegmentator draws C2 by the floor and SPINEPS beside it ...
        theirs = spine_facts()
        theirs["C2"]["voxels"] = G.MIN_VOXELS - 1      # ... draws it under the floor
        self.assertEqual(G.judge(ours, theirs), "concordant")
        theirs = spine_facts()
        del theirs["L5"]                               # the foot of the column is where the count's variants lie
        self.assertEqual(G.judge(spine_facts(), theirs), "unmatched")
        ours = spine_facts()
        del ours["L5"]
        self.assertEqual(G.judge(ours, spine_facts()), "unmatched")

    def test_maps_with_no_bone_in_common_are_unmatched(self):
        far = {name: {"voxels": 1000, "centroid": [500.0, 0.0, f["centroid"][2]]} for name, f in spine_facts().items()}
        self.assertEqual(G.judge(spine_facts(), far), "unmatched")
        self.assertEqual(G.judge(spine_facts(), {}), "unmatched")

    def test_centres_further_apart_than_the_match_distance_never_pair(self):
        pairs, alone = G.matched({"L1": [0.0, 0.0, 0.0]}, {"L1": [0.0, 0.0, G.MATCH_MM + 0.5]})
        self.assertEqual((pairs, alone), ([], [("spineps", "L1"), ("totalseg", "L1")]))
        pairs, alone = G.matched({"L1": [0.0, 0.0, 0.0], "L2": [0.0, 0.0, -30.0]}, {"L1": [0.0, 0.0, -3.0], "L2": [0.0, 0.0, -29.0]})
        self.assertEqual((sorted(pairs), alone), ([("L1", "L1"), ("L2", "L2")], []))


def record(kind, status="segmented", grid=None, dice=None, head="drawn", foot="drawn"):
    return {"status": status, "kind": kind, "grid": grid, "dice": dice or {}, "census": {"head": head, "foot": foot}}


class Bars(unittest.TestCase):
    """The PREREG's three bars, read by the merge from the units' records."""

    def test_each_bar_counts_its_own_units(self):
        records = ([record("concordant", grid="same", dice={"C3": 0.85, "T5": 0.9, "L2": 0.8, "sacrum": 0.1})] * 6
                   + [record("name_shift"), record("unmatched"), record("variant"), record("no_comparison"),
                      record("no_c2"), record("sacrum_above"), record(None, status="given up"),
                      record("no_c2", head="in_view"), record("concordant", foot="in_view"), record("unmatched", head="border")])
        lines = G.bar_lines(records)
        self.assertEqual(lines[0], "- the PREREG's bars (part 4):")
        self.assertIn("whose SPINEPS mask draws both: 10 of 12 (83.3%); bar 90%; not met", lines[1])
        self.assertIn("an end only in view or as a border case: 2 of 3 drawn whole by TotalSegmentator (66.7%)", lines[2])
        self.assertIn("in SPINEPS's map: 7 of 10 (70.0%); bar 80%; not met", lines[3])
        self.assertIn("(C 0.80, T 0.85, L 0.85), over the 6 concordant units on a shared lattice: C 0.850, T 0.900, L 0.800; not met",
                      lines[4])

    def test_a_bar_with_nothing_to_read_is_not_tested_and_open_units_make_it_provisional(self):
        lines = G.bar_lines([record("concordant", grid="another lattice"), record(None, status="failed"), record(None, status="not run")])
        self.assertEqual(lines[0], "- the PREREG's bars (part 4), provisional, units neither segmented nor given up: 2:")
        self.assertIn("1 of 1 (100.0%); bar 90%; met", lines[1])
        self.assertIn("0 of 0 drawn whole by TotalSegmentator", lines[2])
        self.assertIn("1 of 1 (100.0%); bar 80%; met", lines[3])
        self.assertIn("over the 0 concordant units on a shared lattice: not tested, no level of C or T or L on a shared lattice", lines[4])
        lines = G.bar_lines([])
        self.assertIn("not tested, no unit to read it on; bar 90%", lines[1])
        reoriented = G.bar_lines([record("concordant", grid="reoriented", dice={"C2": 0.8, "T1": 0.85, "L5": 0.85})])
        self.assertIn("over the 1 concordant units on a shared lattice: C 0.800, T 0.850, L 0.850; met", reoriented[4])


@unittest.skipUnless(np is not None, "numpy is not installed")
class Maps(unittest.TestCase):
    """The label arrays: TotalSegmentator's ids to VerSe's, each level's voxels and centre, Dice."""

    ids = {name: 100 + i for i, name in enumerate(G.VERSE_ID)}

    def test_its_classes_become_verse_ids_with_s1_and_the_sacrum_one_mask(self):
        values = np.zeros((4, 4, 4), dtype=np.uint8)
        values[0, 0, 0] = self.ids["vertebrae_C1"]
        values[1, 1, 1] = self.ids["vertebrae_C2"]
        values[2, 2, 2] = self.ids["vertebrae_S1"]
        values[2, 2, 3] = self.ids["sacrum"]
        values[3, 3, 3] = 7
        verse, counts = G.to_verse(values, self.ids)
        self.assertEqual(verse.dtype, np.int16)
        self.assertEqual((int(verse[0, 0, 0]), int(verse[1, 1, 1]), int(verse[2, 2, 2]), int(verse[2, 2, 3]), int(verse[3, 3, 3])),
                         (1, 2, 26, 26, 0))
        self.assertEqual((counts["vertebrae_C2"], counts["vertebrae_S1"], counts["sacrum"], counts["other"]), (1, 1, 1, 1))
        empty, counts = G.to_verse(np.zeros((3, 3, 3), dtype=np.uint8), self.ids)
        self.assertFalse(empty.any())
        self.assertEqual(counts["other"], 0)
        with self.assertRaisesRegex(ValueError, "outside 0 to 255"):
            G.to_verse(np.full((2, 2, 2), 300, dtype=np.int16), self.ids)

    def test_a_float_map_is_read_as_its_rounded_labels(self):
        values = np.zeros((2, 2, 2), dtype=np.float32)
        values[0, 0, 0] = self.ids["vertebrae_L5"] + 0.0001
        verse, _ = G.to_verse(values, self.ids)
        self.assertEqual(int(verse[0, 0, 0]), 24)

    def test_each_levels_voxels_and_world_centre_the_sacrum_from_26_and_29(self):
        labels = np.zeros((10, 10, 10), dtype=np.int16)
        labels[2:4, 2:4, 2:4] = 2
        labels[6:8, 6:8, 6:7] = 26
        labels[6:8, 6:8, 7:8] = 29
        labels[0, 9, 9] = 105
        affine = np.diag([2.0, 2.0, 3.0, 1.0])
        affine[:3, 3] = [-10.0, 0.0, 5.0]
        facts, outside = G.level_facts(labels, affine)
        self.assertEqual(sorted(facts), ["C2", "sacrum"])
        self.assertEqual(facts["C2"], {"voxels": 8, "centroid": [-5.0, 5.0, 12.5]})
        self.assertEqual(facts["sacrum"]["voxels"], 8)
        self.assertEqual(facts["sacrum"]["centroid"], [3.0, 13.0, 24.5])
        self.assertEqual(outside, 1)
        self.assertEqual(G.level_facts(np.zeros((3, 3, 3), dtype=np.int16), affine), ({}, 0))

    def test_dice_by_level_on_one_grid(self):
        ours = np.zeros((6, 6, 6), dtype=np.int16)
        ours[0:2, 0:2, 0:2] = 2
        ours[3:5, 3:5, 3:5] = 26
        theirs = ours.copy()
        theirs[theirs == 26] = 29
        theirs[0:2, 0:2, 0:1] = 0
        found = G.dice_by_level(ours, theirs, ["C2", "sacrum", "L1"])
        self.assertEqual(found, {"C2": round(2 * 4 / 12, 4), "sacrum": 1.0})
        self.assertEqual(G.dice_by_level(np.zeros((2, 2, 2)), np.zeros((2, 2, 2)), ["C2"]), {})

    def test_two_grids_are_one_within_a_hundredth_of_a_millimetre(self):
        affine = np.eye(4)
        near, far = affine.copy(), affine.copy()
        near[0, 3] = 0.005
        far[0, 3] = 0.1
        self.assertTrue(G.same_grid((2, 2, 2), affine, (2, 2, 2), near))
        self.assertFalse(G.same_grid((2, 2, 2), affine, (2, 2, 2), far))
        self.assertFalse(G.same_grid((2, 2, 2), affine, (2, 2, 3), affine))

    @unittest.skipUnless(nib is not None, "nibabel is not installed")
    def test_a_map_reoriented_shares_the_lattice_and_one_on_other_voxels_does_not(self):
        labels = np.zeros((4, 5, 6), dtype=np.int16)
        labels[1, 2, 3] = 20
        labels[0, 4, 5] = 26
        affine = np.diag([0.8, 0.8, 2.0, 1.0])
        affine[:3, 3] = [-10.0, 4.0, 7.0]
        same, how = G.on_our_lattice(labels, affine, labels.shape, affine)
        self.assertEqual(how, "same")
        self.assertIs(same, labels)
        # the axes swapped and the first flipped, as SPINEPS's own orientation might hold them
        turned = np.flip(labels, axis=0).transpose(2, 0, 1)
        to_turned = np.zeros((4, 4))
        to_turned[3, 3] = 1.0
        to_turned[0, 1] = -1.0          # turned's j is labels' i, flipped
        to_turned[0, 3] = labels.shape[0] - 1
        to_turned[1, 2] = 1.0           # turned's k is labels' j
        to_turned[2, 0] = 1.0           # turned's i is labels' k
        turned_affine = affine @ to_turned
        back, how = G.on_our_lattice(turned, turned_affine, labels.shape, affine)
        self.assertEqual(how, "reoriented")
        self.assertTrue(np.array_equal(back, labels))
        finer = affine.copy()
        finer[2, 2] = 1.0
        self.assertEqual(G.on_our_lattice(labels, finer, labels.shape, affine), (None, "another lattice"))
        self.assertEqual(G.on_our_lattice(labels[:, :, :5], affine, labels.shape, affine), (None, "another lattice"))

    def test_bounding_box(self):
        mask = np.zeros((5, 6, 7), dtype=bool)
        mask[1:3, 2, 4:7] = True
        self.assertEqual(G.bounding_box(mask), (slice(1, 3), slice(2, 3), slice(4, 7)))
        self.assertIsNone(G.bounding_box(np.zeros((2, 2), dtype=bool)))


LEVELS = [*G.TS_VERTEBRAE, "sacrum"]
SLICES = 6            # each level's slab along z; at 2 mm a slice, centres 12 mm apart, beyond the match distance


def spine_map(shape=(8, 8, SLICES * len(LEVELS))):
    """A crafted spine in VerSe's ids, every level a slab of 8 by 8 by 6 voxels (384), C1 at the top."""
    labels = np.zeros(shape, dtype=np.int16)
    for i, name in enumerate(LEVELS):
        value = 26 if name == "sacrum" else G.IDS_OF[name][0]
        labels[:, :, shape[2] - SLICES * (i + 1):shape[2] - SLICES * i] = value
    return labels


@unittest.skipUnless(np is not None and nib is not None, "numpy and nibabel are not installed")
class WholeRun(unittest.TestCase):
    """run and merge over crafted CTs, with a stand-in for TotalSegmentator that draws the SPINEPS
    mask again in TotalSegmentator's ids, or fails where the CT's name says so."""

    ids = {name: 100 + i for i, name in enumerate(G.VERSE_ID)}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.affine = np.diag([1.0, 1.0, 2.0, 1.0])
        self.environ = mock.patch.dict(os.environ)
        self.environ.start()
        rows, tiers = [], []
        for name in ("good", "fails", "good2"):
            ct, mask = self.root / "data" / f"{name}.nii.gz", self.root / "spineps" / f"{name}_vert.nii.gz"
            for path, data in ((ct, np.zeros((8, 8, SLICES * len(LEVELS)), dtype=np.int16)), (mask, spine_map())):
                path.parent.mkdir(parents=True, exist_ok=True)
                nib.save(nib.Nifti1Image(data, self.affine), str(path))
            rows.append(census_row("CT-ORG", name, str(mask)))
            tiers.append((str(mask), str(ct)))
        rows.append(census_row("ts", "ts:s0001", "/nowhere/ts.nii.gz"))
        self.census = self.root / "gold4.json"
        self.census.write_text(json.dumps({"rows": rows}), encoding="utf-8")
        write_tiers(self.root / "tiers", tiers)
        self.weights = self.root / "weights"
        for part in ("Dataset292_vertebrae", "Dataset298_total_6mm"):
            (self.weights / part).mkdir(parents=True)
            (self.weights / part / "UNPACKED").write_text("", encoding="utf-8")
        self.out = self.root / "out"

    def tearDown(self):
        self.environ.stop()
        self.tmp.cleanup()

    def segment(self, ct, dest, args, fail=True):
        if fail and "fails" in str(ct):
            raise RuntimeError("CUDA out of memory")
        verse = np.asanyarray(nib.load(str(self.root / "spineps" / (Path(ct).name.split(".")[0] + "_vert.nii.gz"))).dataobj)
        values = np.zeros(verse.shape, dtype=np.uint8)
        back = {}
        for name, value in self.ids.items():
            back.setdefault(G.VERSE_ID[name], value)
        for verse_id, ts_id in back.items():
            values[verse == verse_id] = ts_id
        nib.save(nib.Nifti1Image(values, self.affine), str(dest))

    def args(self, chain, task=0, tasks=1, commit="c" * 40, device="cpu"):
        return Namespace(census=str(self.census), tiers=str(self.root / "tiers"), out=str(self.out), chain=chain, task=task,
                         tasks=tasks, commit=commit, weights=str(self.weights), threads=1, device=device,
                         stop_after=G.STOP_AFTER)

    def run_chain(self, chain, **words):
        with mock.patch("sys.stdout"):
            return G.run(self.args(chain, **words), segment=self.segment, ids=self.ids)

    def merge(self, chain, commit="c" * 40):
        with mock.patch("sys.stdout"):
            return G.merge(Namespace(out=str(self.out), chain=chain, commit=commit))

    def unit(self, name):
        jobs = json.loads((self.out / "chains" / "1" / "jobs.json").read_text(encoding="utf-8"))
        return next(u for u in jobs["units"] if u["case_id"] == name)

    def test_a_ct_segmented_comes_out_on_its_own_grid_in_verse_ids_beside_spineps(self):
        self.assertEqual(self.run_chain("1"), 1)
        good = self.unit("good")
        image = nib.load(str(G.labels_path(self.out, good["id"])))
        self.assertEqual(image.get_data_dtype(), np.int16)
        self.assertTrue(np.allclose(image.affine, self.affine))
        self.assertTrue(np.array_equal(np.asanyarray(image.dataobj), spine_map()))
        record = json.loads(G.record_path(self.out, good["id"]).read_text(encoding="utf-8"))
        self.assertEqual((record["exit"], record["kind"], record["grid"]), (0, "concordant", "same"))
        self.assertEqual(set(record["dice"].values()), {1.0})
        self.assertEqual(len(record["dice"]), len(LEVELS))                # every level both maps drew, C1 and the sacrum among them
        self.assertNotIn("failed", record)
        self.assertEqual(record["labels_sha256"], G.sha256_of(G.labels_path(self.out, good["id"])))
        failed = json.loads(G.record_path(self.out, self.unit("fails")["id"]).read_text(encoding="utf-8"))
        self.assertEqual((failed["exit"], failed["failed"]), (1, [{"chain": "1", "commit": "c" * 40}]))
        self.assertTrue(failed["error"].startswith("RuntimeError: CUDA out of memory"))
        self.assertEqual(os.environ["TOTALSEG_WEIGHTS_PATH"], str(self.weights))
        config = json.loads((Path(os.environ["TOTALSEG_HOME_DIR"]) / "config.json").read_text(encoding="utf-8"))
        self.assertFalse(config["send_usage_stats"])

    def test_a_spineps_mask_in_another_orientation_is_compared_voxel_by_voxel(self):
        mask = self.root / "spineps" / "good2_vert.nii.gz"
        image = nib.load(str(mask))
        nib.save(image.as_reoriented([[1, -1], [0, 1], [2, 1]]), str(mask))
        self.assertNotEqual(nib.aff2axcodes(nib.load(str(mask)).affine), nib.aff2axcodes(self.affine))
        self.run_chain("1")
        record = json.loads(G.record_path(self.out, self.unit("good2")["id"]).read_text(encoding="utf-8"))
        self.assertEqual((record["kind"], record["grid"]), ("concordant", "reoriented"))
        self.assertEqual(set(record["dice"].values()), {1.0})

    def test_a_send_again_carries_on_and_a_unit_that_failed_in_two_chains_is_given_up(self):
        self.assertEqual(self.run_chain("1"), 1)
        self.assertEqual(self.merge("1"), 3)
        good_record = G.record_path(self.out, self.unit("good")["id"])
        written = good_record.stat().st_mtime_ns
        self.assertEqual(self.run_chain("2"), 1)
        self.assertEqual(good_record.stat().st_mtime_ns, written)          # passed over, not run again
        failed = json.loads(G.record_path(self.out, self.unit("fails")["id"]).read_text(encoding="utf-8"))
        self.assertEqual([f["chain"] for f in failed["failed"]], ["1", "2"])
        self.assertEqual(self.run_chain("3"), 0)                            # nothing left to run
        self.assertEqual(self.merge("3"), 0)
        lines = (self.out / "chains" / "3" / "tasks" / "0.txt").read_text(encoding="utf-8")
        self.assertIn("0 segmented, 0 failed, 3 passed over", lines)
        # a new commit gives the unit that failed its chances again
        self.assertEqual(self.run_chain("4", commit="d" * 40), 1)

    def test_the_merge_writes_every_unit_and_a_report_of_counts_alone(self):
        self.run_chain("1")
        self.assertEqual(self.merge("1"), 3)
        records = [json.loads(line) for line in (self.out / "records.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(sorted(r["status"] for r in records), ["failed", "segmented", "segmented"])
        good = next(r for r in records if r["case_id"] == "good")
        self.assertEqual(good["labels"], f"labels/{good['id']}.nii.gz")
        self.assertEqual(good["ct"], str(self.root / "data" / "good.nii.gz"))
        self.assertEqual(good["spineps_mask"], str(self.root / "spineps" / "good_vert.nii.gz"))
        report = (self.out / "chains" / "1" / "REPORT.md").read_text(encoding="utf-8")
        self.assertNotIn(str(self.root), report)
        for case in ("good", "fails"):
            self.assertNotIn(case, report)
        self.assertIn("- units: 3 CTs (3 admitted, 0 look by the census's field test) of 4 candidate rows; left out: "
                      f"{G.WHY['release']} 1", report)
        self.assertIn("segmented 2 (2 by this chain, 0 before it); failed 1; given up 0", report)
        self.assertIn("failures by kind: RuntimeError 1", report)
        self.assertIn("against the census's SPINEPS masks: concordant 2", report)
        self.assertIn("by collection (units, segmented, concordant): CT-ORG 3 2 2", report)
        self.assertIn("sacrum 1.000 (2 levels)", report)
        self.assertIn("share a lattice (2: 2 on one grid, 0 reoriented)", report)
        self.assertIn("- the PREREG's bars (part 4), provisional, units neither segmented nor given up: 1:", report)
        self.assertIn("H1, C2 and the sacrum drawn, the sacrum below the lowest level, of the units segmented whose SPINEPS mask "
                      "draws both: 2 of 2 (100.0%); bar 90%; met", report)
        self.assertIn("of the units compared with no T13 or L6 in SPINEPS's map: 2 of 2 (100.0%); bar 80%; met", report)
        self.assertIn("over the 2 concordant units on a shared lattice: C 1.000, T 1.000, L 1.000; met", report)

    def test_a_task_stops_after_three_failures_in_a_row_and_takes_no_unit_past_its_time(self):
        def always_fails(ct, dest, args):
            raise MemoryError("no room")
        with mock.patch("sys.stdout"):
            self.assertEqual(G.run(self.args("1"), segment=always_fails, ids=self.ids), 1)
        lines = (self.out / "chains" / "1" / "tasks" / "0.txt").read_text(encoding="utf-8")
        self.assertIn("stopped after 3 failures in a row", lines)
        ticks = iter([0.0, 10.0, 10.0 + G.STOP_AFTER])
        with mock.patch("sys.stdout"):
            code = G.run(self.args("2"), segment=lambda ct, dest, args: self.segment(ct, dest, args, fail=False), ids=self.ids,
                         clock=lambda: next(ticks))
        self.assertEqual(code, 0)
        lines = (self.out / "chains" / "2" / "tasks" / "0.txt").read_text(encoding="utf-8")
        self.assertIn("s have passed, so it takes no new unit", lines)
        self.assertIn("1 segmented, 0 failed", lines)

    def test_two_tasks_of_one_chain_take_each_unit_once(self):
        self.assertEqual(self.run_chain("1", task=0, tasks=2), 1)
        self.assertEqual(self.run_chain("1", task=1, tasks=2), 0)              # every unit claimed already
        claims = sorted(p.name for p in (self.out / "chains" / "1" / "claims").iterdir())
        self.assertEqual(len(claims), 3)

    def test_inputs_missing_or_no_card_stop_the_task_before_any_ct(self):
        (self.weights / "Dataset292_vertebrae" / "UNPACKED").unlink()
        self.assertEqual(self.run_chain("1"), 2)
        (self.weights / "Dataset292_vertebrae" / "UNPACKED").write_text("", encoding="utf-8")
        with mock.patch.object(G, "gpu_name", return_value=None), mock.patch("sys.stdout"):
            self.assertEqual(G.run(self.args("2", device="gpu"), segment=self.segment, ids=self.ids), 4)
        self.census.unlink()
        self.assertEqual(self.run_chain("3"), 2)
        self.assertEqual(self.merge("9"), 2)


class Command(unittest.TestCase):
    def test_a_task_outside_the_array_is_refused(self):
        with mock.patch("sys.stderr"), self.assertRaises(SystemExit):
            G.main(["run", "--census", "c", "--tiers", "t", "--out", "o", "--chain", "1", "--task", "16", "--tasks", "16"])


if __name__ == "__main__":
    unittest.main()
