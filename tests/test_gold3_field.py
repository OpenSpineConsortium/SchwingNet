"""tools/gold3_field.py: the field test of the gold tier 3 CT dataset, on synthetic spines.

Every test builds its spines in memory, in the level names the field test reads, from a column with fixed
heights and discs; no mask, no grid and nothing written into the repository but a scratch folder.
"""
import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_tool(name):
    """A module under tools/, loaded by path, since tools/ is no package."""
    found = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(found)
    found.loader.exec_module(module)
    return module


field = load_tool("gold3_field")

DISC_MM = 4.0
HEIGHT = {**{"C1": 12.0, "C2": 30.0}, **{f"C{i}": 15.0 for i in range(3, 8)},
          **{f"T{i}": 22.0 for i in range(1, 13)}, **{f"L{i}": 28.0 for i in range(1, 6)}, "sacrum": 90.0}
NORMAL = ("C1", "C2", *[f"C{i}" for i in range(3, 8)], *[f"T{i}" for i in range(1, 13)],
          *[f"L{i}" for i in range(1, 6)], "sacrum")
# The sacrum's top stands this far above L5's foot-most voxel, as L5's facets reach down beside S1.
SACRUM_ABOVE_L5_MM = 20.0


def column(names=NORMAL, top=0.0, stretch=1.0):
    """Levels stacked head to foot from `top`, a disc between neighbours, each height times `stretch`
    so a population of spines spreads the tables."""
    levels, position = {}, top
    for name in names:
        height = HEIGHT[name] * stretch
        if name == "sacrum":
            position = levels["L5"]["bottom"] + SACRUM_ABOVE_L5_MM * stretch if "L5" in levels else position
        levels[name] = {"voxels": 5000, "top": round(position, 1), "bottom": round(position - height, 1),
                        "head_cut": False, "foot_cut": False, "side_cut": False}
        position -= height + DISC_MM * stretch
    return levels


def study(levels, top, bottom, member="totalsegmentator", sid="s0001", age=50.0):
    """A study on an untilted grid, so the field over every level is the volume's."""
    levels = {name: {"field_top": top, "field_bottom": bottom, **entry} for name, entry in levels.items()}
    return {"member": member, "id": sid, "top": top, "bottom": bottom, "levels": levels,
            "person": f"{member}:{sid}", "age": age, "site": None}


def whole_spine(sid, stretch):
    levels = column(stretch=stretch)
    return study(levels, levels["C1"]["top"] + 20.0, levels["sacrum"]["bottom"] - 20.0, sid=sid)


def population(n=40):
    """Spines whose sizes spread from 0.8 to 1.2 of the column's, every level drawn whole."""
    return [whole_spine(f"p{k:03d}", 0.8 + 0.4 * k / (n - 1)) for k in range(n)]


def without(levels, *names):
    return {name: entry for name, entry in levels.items() if name not in names}


class Tables(unittest.TestCase):
    def setUp(self):
        self.table = field.tables(population())

    def test_percentiles_interpolate_between_order_statistics(self):
        self.assertEqual(field.percentile([1, 2, 3, 4, 5], 50), 3)
        self.assertAlmostEqual(field.percentile([0, 10], 95), 9.5)
        self.assertEqual(field.percentile([7], 5), 7)

    def test_a_row_needs_twenty_spines(self):
        self.assertEqual(field.summary([1.0] * 19), {"n": 19})
        self.assertEqual(field.summary([1.0] * 20)["n"], 20)

    def test_the_head_table_measures_c2_above_each_level(self):
        row = self.table["head"]["C3"]
        # C2's top lies C2's height and a disc above C3's top, both stretched.
        self.assertAlmostEqual(row["median"], round(34.0, 1), delta=0.2)
        self.assertLess(row["low"], row["median"])
        self.assertIn("C3 to C2's foot", self.table["head"])

    def test_the_foot_table_has_a_last_lumbar_row(self):
        self.assertAlmostEqual(self.table["foot"]["last lumbar"]["median"], SACRUM_ABOVE_L5_MM, delta=0.2)


class Ends(unittest.TestCase):
    def setUp(self):
        self.table = field.tables(population())

    def judged(self, levels, top, bottom, **extra):
        return field.judge(study(levels, top, bottom, **extra), self.table)

    def test_a_whole_spine_is_admitted_with_nothing_to_add(self):
        levels = column()
        found = self.judged(levels, levels["C1"]["top"] + 5, levels["sacrum"]["bottom"] - 5)
        self.assertEqual((found["verdict"], found["head"], found["foot"], found["complete"]), ("admitted", "drawn", "drawn", []))

    def test_a_sacrum_in_view_and_undrawn_is_added(self):
        levels = without(column(), "sacrum")
        found = self.judged(levels, levels["C1"]["top"] + 5, levels["L5"]["bottom"] - 80)
        self.assertEqual((found["verdict"], found["foot"], found["complete"]), ("admitted", "in_view", ["sacrum"]))

    def test_a_field_ending_at_the_last_lumbar_leaves_the_sacrum_out(self):
        levels = without(column(), "sacrum")
        found = self.judged(levels, levels["C1"]["top"] + 5, levels["L5"]["bottom"] + 30)
        self.assertEqual(found["foot"], "out")

    def test_a_field_just_below_the_last_lumbar_is_a_border_case(self):
        levels = without(column(), "sacrum")
        found = self.judged(levels, levels["C1"]["top"] + 5, levels["L5"]["bottom"] + 5)
        self.assertEqual((found["verdict"], found["foot"]), ("look", "border"))

    def test_a_foot_most_level_cut_by_the_field_is_out(self):
        levels = without(column(), "sacrum")
        levels["L5"] = {**levels["L5"], "foot_cut": True}
        found = self.judged(levels, levels["C1"]["top"] + 5, levels["L5"]["bottom"] - 0.5)
        self.assertEqual((found["verdict"], found["foot"]), ("not_admitted", "out"))

    def test_c2_in_view_above_an_undrawn_head_is_added_with_c3_to_c7_above_t1(self):
        levels = without(column(), "C1", "C2", "C3", "C4", "C5", "C6", "C7")
        found = self.judged(levels, levels["T1"]["top"] + 200, levels["sacrum"]["bottom"] - 5)
        self.assertEqual(found["head"], "in_view")
        self.assertEqual(found["complete"], ["C2", "C3", "C4", "C5", "C6", "C7"])

    def test_a_field_part_way_up_c2_is_a_border_case_and_a_cut_head_is_out(self):
        levels = without(column(), "C1", "C2")
        # Twenty millimetres clear C2's foot in every spine and fall short of C2's top in most.
        found = self.judged(levels, levels["C3"]["top"] + 20, levels["sacrum"]["bottom"] - 5)
        self.assertEqual(found["head"], "border")
        levels["C3"] = {**levels["C3"], "head_cut": True}
        found = self.judged(levels, levels["C3"]["top"] + 0.5, levels["sacrum"]["bottom"] - 5)
        self.assertEqual((found["verdict"], found["head"]), ("not_admitted", "out"))

    def test_a_thoracic_spine_ending_far_above_c2_is_out(self):
        levels = without(column(), *[n for n in NORMAL if not n.startswith("T")])
        levels["T1"] = {**levels["T1"], "head_cut": False}
        found = self.judged(levels, levels["T1"]["top"] + 2, levels["T12"]["bottom"] - 5)
        self.assertEqual((found["head"], found["verdict"]), ("out", "not_admitted"))

    def test_c1_above_an_undrawn_c2_is_in_view_only_with_levels_below(self):
        levels = without(column(), "C2")
        found = self.judged(levels, levels["C1"]["top"] + 5, levels["sacrum"]["bottom"] - 5)
        self.assertEqual((found["verdict"], found["head"], found["complete"]), ("admitted", "in_view", ["C2"]))
        alone = {"C1": column()["C1"]}
        found = self.judged(alone, alone["C1"]["top"] + 5, alone["C1"]["bottom"] - 2)
        self.assertEqual((found["verdict"], found["head"]), ("not_admitted", "border"))

    def test_a_drawn_c2_in_the_top_slice_is_in_view_and_flagged(self):
        levels = column()
        levels["C2"] = {**levels["C2"], "head_cut": True}
        found = self.judged(without(levels, "C1"), levels["C2"]["top"] + 0.5, levels["sacrum"]["bottom"] - 5)
        self.assertEqual((found["verdict"], found["head"]), ("admitted", "drawn"))
        self.assertIn("c2_at_field_top", found["flags"])

    def test_a_gap_is_added_and_a_missing_l5_is_a_flag_not_a_gap(self):
        levels = without(column(), "T7", "L5")
        found = self.judged(levels, levels["C1"]["top"] + 5, levels["sacrum"]["bottom"] - 5)
        self.assertEqual(found["complete"], ["T7"])
        self.assertIn("no_l5", found["flags"])

    def test_a_label_under_the_floor_is_not_drawn(self):
        levels = column()
        levels["T7"] = {**levels["T7"], "voxels": field.LEVEL_MIN_VOXELS - 1}
        found = self.judged(levels, levels["C1"]["top"] + 5, levels["sacrum"]["bottom"] - 5)
        self.assertEqual(found["complete"], ["T7"])
        self.assertIn("stray_labels", found["flags"])

    def test_no_level_drawn_is_no_column(self):
        found = self.judged({}, 100.0, -100.0)
        self.assertEqual((found["verdict"], found["head"], found["foot"]), ("not_admitted", "no_column", "no_column"))

    def test_a_child_and_a_spine_cut_in_plane_are_flagged(self):
        levels = column()
        levels["T4"] = {**levels["T4"], "side_cut": True}
        found = self.judged(levels, levels["C1"]["top"] + 5, levels["sacrum"]["bottom"] - 5, age=12.0)
        self.assertEqual(sorted(found["flags"]), ["child", "cut_in_plane"])

    def test_a_c2_sliver_beside_a_level_the_top_cuts_is_out(self):
        levels = without(column(), "C1")
        levels["C2"] = {**levels["C2"], "head_cut": True, "voxels": 229}
        levels["C3"] = {**levels["C3"], "head_cut": True}
        found = self.judged(levels, levels["C2"]["top"] + 0.5, levels["sacrum"]["bottom"] - 5)
        self.assertEqual((found["verdict"], found["head"]), ("not_admitted", "out"))

    def test_a_sacrum_the_foot_cuts_needs_s1_view_of_it_in_the_field(self):
        levels = column()
        top = levels["C1"]["top"] + 5
        levels["sacrum"] = {**levels["sacrum"], "foot_cut": True}
        for held, expected in ((25.0, ("admitted", "drawn")), (10.0, ("look", "border"))):
            found = self.judged(levels, top, levels["sacrum"]["top"] - held)
            self.assertEqual((found["verdict"], found["foot"]), expected, held)
            self.assertIn("sacrum_at_field_foot", found["flags"])
        levels["L5"] = {**levels["L5"], "foot_cut": True}
        found = self.judged(levels, top, levels["sacrum"]["top"] - 10.0)
        self.assertEqual((found["verdict"], found["foot"]), ("not_admitted", "out"))

    def test_a_cut_sacrum_label_under_the_floor_keeps_the_sacrum_from_view(self):
        levels = column()
        levels["sacrum"] = {**levels["sacrum"], "voxels": 11, "foot_cut": True}
        # The table alone would put the sacrum in view 80 mm below L5's foot; the label says the field
        # holds 2 mm of it.
        found = self.judged(levels, levels["C1"]["top"] + 5, levels["sacrum"]["top"] - 2.0)
        self.assertEqual((found["verdict"], found["foot"]), ("look", "border"))

    def test_eleven_thoracic_is_a_skipped_name_not_a_gap(self):
        levels = without(column(), "T12")
        # L1's top stands 15 mm above T11's foot, as neighbours overlap by their facets.
        shift = levels["T11"]["bottom"] - levels["L1"]["top"] + 15.0
        for name in ("L1", "L2", "L3", "L4", "L5", "sacrum"):
            levels[name] = {**levels[name], "top": levels[name]["top"] + shift, "bottom": levels[name]["bottom"] + shift}
        found = self.judged(levels, levels["C1"]["top"] + 5, levels["sacrum"]["bottom"] - 5)
        self.assertEqual((found["verdict"], found["complete"]), ("admitted", []))
        self.assertIn("name_skipped", found["flags"])

    def test_l5_is_asked_below_a_column_that_stops_above_l4(self):
        levels = without(column(), "L4", "L5", "sacrum")
        found = self.judged(levels, levels["C1"]["top"] + 5, levels["L3"]["bottom"] - 200)
        self.assertEqual((found["foot"], found["complete"]), ("in_view", ["L4", "L5", "sacrum"]))
        drawn = without(column(), "L4", "L5")
        found = self.judged(drawn, drawn["C1"]["top"] + 5, drawn["sacrum"]["bottom"] - 5)
        self.assertEqual(found["complete"], ["L4", "L5"])

    def test_a_column_of_lumbar_levels_alone_is_judged(self):
        levels = {"L5": column()["L5"]}
        found = self.judged(levels, levels["L5"]["top"] + 700, levels["L5"]["bottom"] - 200)
        self.assertEqual(found["verdict"], "admitted")
        self.assertEqual(found["complete"][0], "C2")

    def test_a_short_column_and_a_label_far_taller_than_its_body_are_flagged(self):
        small = column(stretch=0.5)
        found = self.judged(small, small["C1"]["top"] + 5, small["sacrum"]["bottom"] - 5, age=30.0)
        self.assertIn("small_column", found["flags"])
        levels = column()
        levels["T6"] = {**levels["T6"], "bottom": levels["T6"]["top"] - 300.0}
        found = self.judged(levels, levels["C1"]["top"] + 5, levels["sacrum"]["bottom"] - 5)
        self.assertIn("label_spans_levels", found["flags"])
        self.assertNotIn("small_column", found["flags"])


class Enhance(unittest.TestCase):
    def test_a_level_in_the_first_or_last_slice_reaches_that_face(self):
        # Slices 2 mm apart: the top slice's centre is 99.0, a millimetre under the field's top at 100.
        entry = {"voxels": 900, "top_mm": 99.0, "bottom_mm": -40.0}
        found = field.enhance_level(entry, 100.0, -41.0, 2.0)
        self.assertEqual((found["head_cut"], found["foot_cut"], found["side_cut"]), (True, True, None))
        found = field.enhance_level({**entry, "top_mm": 97.0, "bottom_mm": -38.0}, 100.0, -41.0, 2.0)
        self.assertEqual((found["head_cut"], found["foot_cut"]), (False, False))

    def test_the_field_is_the_outer_faces(self):
        affine = [[1.0, 0, 0, 0], [0, 1.0, 0, 0], [0, 0, 2.0, -100.0], [0, 0, 0, 1]]
        heights = field.corner_heights([4, 4, 10], affine)
        self.assertEqual((max(heights), min(heights)), (-100.0 + 9.5 * 2, -100.0 - 0.5 * 2))


class Geometry(unittest.TestCase):
    def test_the_vertical_line_leaves_an_untilted_grid_at_its_faces(self):
        affine = [[1.5, 0, 0, -10.0], [0, 1.5, 0, -10.0], [0, 0, 2.0, -100.0], [0, 0, 0, 1]]
        up, down = field.vertical_edges(affine, [20, 20, 50], [0.0, 0.0, -50.0])
        self.assertAlmostEqual(up, -100.0 + 49.5 * 2)
        self.assertAlmostEqual(down, -100.0 - 0.5 * 2)

    def test_a_tilted_grid_holds_less_above_the_column_than_its_highest_corner(self):
        # Each step along the first axis climbs 0.5 mm, so the top face is 25 mm higher at one side.
        affine = [[1.0, 0, 0, 0.0], [0, 1.0, 0, 0.0], [0.5, 0, 1.0, 0.0], [0, 0, 0, 1]]
        up, _ = field.vertical_edges(affine, [50, 10, 100], [5.0, 5.0, 50.0])
        self.assertAlmostEqual(up, 99.5 + 0.5 * 5.0)
        self.assertGreater(max(field.corner_heights([50, 10, 100], affine)), up + 20)

    def padded(self, cord_top):
        affine = [[1.5, 0, 0, -100.0], [0, 1.5, 0, -100.0], [0, 0, 1.5, -500.0], [0, 0, 0, 1]]
        level = {"voxels": 5000, "faces": [], "centroid_mm": [0.0, 0.0, -40.0], "top_mm": -22.7, "bottom_mm": -60.0}
        return {"member": "totalsegmentator", "id": "s0102", "field_mm": {"top": 71.0, "bottom": -482.5},
                "grid": {"affine": affine, "shape": [100, 100, 369], "zooms": [1.5, 1.5, 1.5], "head_foot_axis": 2},
                "levels": {"C6": level, "T1": {**level, "top_mm": -61.0, "bottom_mm": -90.0}},
                "context": {"spinal_cord": {"voxels": 20000, "faces": [], "top_mm": cord_top, "bottom_mm": -300.0}}}

    def test_a_padded_grid_ends_its_field_where_the_cord_and_column_stop(self):
        found = field.named_study(self.padded(-22.7), "p", 50.0, None)
        self.assertEqual(found["levels"]["C6"]["field_top"], -21.9)
        self.assertTrue(found["levels"]["C6"]["head_cut"])
        self.assertFalse(found["levels"]["T1"]["head_cut"])

    def test_a_cord_that_runs_on_above_the_column_leaves_the_grid_as_the_field(self):
        found = field.named_study(self.padded(10.0), "p", 50.0, None)
        self.assertEqual(found["levels"]["C6"]["field_top"], 71.0)
        self.assertFalse(found["levels"]["C6"]["head_cut"])


class Studies(unittest.TestCase):
    def test_a_repaired_mask_is_judged_once_under_its_study_id(self):
        mask = {"affine": [[1.0, 0, 0, 0], [0, 1.0, 0, 0], [0, 0, 2.0, -100.0], [0, 0, 0, 1]],
                "shape": [4, 4, 100], "head_foot_axis": 2}
        entry = {"voxels": 900, "top_mm": 50.0, "bottom_mm": 20.0, "centroid_mm": [1.0, 1.0, 35.0]}
        published = {"id": "1134", "mask": mask, "labels": {"2": entry}, "site": "autopet"}
        repaired = {**published, "id": "1134r", "repaired_from": "1134", "labels": {"3": entry}}
        inputs = {"enhance_pet": [published, repaired], "verse": [], "totalsegmentator": [],
                  "verse_series": {"series": []}, "totalseg_subjects": {"subjects": {}}}
        studies, unread = field.studies_of(inputs)
        self.assertEqual([(s["id"], sorted(s["levels"])) for s in studies], [("1134", ["C3"])])
        self.assertEqual(unread, [])


class Take(unittest.TestCase):
    def test_the_digest_is_sha256sum_of_the_sorted_lines(self):
        files = {"b.nii.gz": {"bytes": 3, "sha256": "2" * 64}, "a.nii.gz": {"bytes": 5, "sha256": "1" * 64}}
        lines = f"{'1' * 64}  a.nii.gz\n{'2' * 64}  b.nii.gz\n"
        self.assertEqual(field.sums_digest(files), {"count": 2, "bytes": 8,
                                                    "sha256_of_sums": hashlib.sha256(lines.encode()).hexdigest()})

    def test_one_file_keeps_its_own_sum(self):
        row = {"id": "verse004", "files": {"verse004_seg.nii.gz": {"bytes": 1, "sha256": "3" * 64}}}
        self.assertEqual(field.compact(row), row)


class Written(unittest.TestCase):
    """The page and the admission written from the committed files are what is committed."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gold3-field-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_the_committed_admission_is_current(self):
        if not (ROOT / field.VERSE_FACTS).is_file():
            self.skipTest("no VerSe facts committed")
        written = field.written(ROOT)
        for rel, text in written.items():
            self.assertEqual((ROOT / rel).read_text(encoding="ascii"), text, rel)

    def test_every_readable_study_has_one_verdict(self):
        if not (ROOT / field.VERSE_FACTS).is_file():
            self.skipTest("no VerSe facts committed")
        data = json.loads((ROOT / field.ADMISSION).read_text(encoding="ascii"))
        keys = [(s["member"], s["id"]) for s in data["studies"]]
        self.assertEqual(len(keys), len(set(keys)))
        counted = sum(m["studies"] for m in data["members"].values())
        self.assertEqual(counted, len(keys))
        members = json.loads((ROOT / "data/gold3-ct/members.json").read_text(encoding="ascii"))["members"]
        unread = {}
        for row in data["unread"]:
            unread[row["member"]] = unread.get(row["member"], 0) + 1
        for member in members:
            name = member["member"]
            self.assertEqual(data["members"][name]["studies"] + unread.get(name, 0), member["studies_listed"], name)


if __name__ == "__main__":
    unittest.main()
