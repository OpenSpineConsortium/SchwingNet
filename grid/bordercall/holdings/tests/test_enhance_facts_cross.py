"""The first reading set beside the count's outputs, holdings/enhance_facts_cross.py, on made-up rows.

Run from the repository's root with `python -m unittest discover -s holdings/tests -t .`."""
import copy
import json
import os
import tempfile
import unittest

from holdings import enhance_facts_cross as X


def fact_row(sid="0001"):
    """One study as the first reading writes it: T12 and the sacrum, a rib 12 on each side and a sternum."""
    return {
        "id": sid,
        "labels": {"19": {"voxels": 900, "bottom_mm": -500.0, "top_mm": -480.0},
                   "28": {"voxels": 4000, "bottom_mm": -700.0, "top_mm": -600.0}},
        "mask": {"shape": [10, 10, 10], "dtype": "uint8"},
        "outside_scheme_voxels": {"vertebrae": 0, "ribs": 0},
        "ribs": {"12": {"voxels": 300, "contacts": {"19": 40}, "lead": 19, "tie": False},
                 "25": {"voxels": 280, "contacts": {"19": 30, "28": 30}, "lead": 19, "tie": True},
                 "13": {"voxels": 20, "contacts": {}, "lead": None, "tie": False}},
        "sternum_voxels": 77,
        "distances_mm": {"23-28": 15.3, "24-28": 0.9},
    }


def count_extents():
    return {"voxels": {"19": 900, "28": 4000}, "outside_scheme_voxels": 0,
            "extent_mm": {"19": [-500.0, -480.0, 20], "28": [-700.0, -600.0, 100]},
            "shape": [10, 10, 10], "dtype": "uint8"}


def count_ribs():
    return {"voxels": {"12": 300, "25": 280, "13": 20, "27": 77}, "outside_scheme_voxels": 0,
            "lowest": {"left": 12, "right": 12},
            "contacts": {"left": {"lowest_rib": 12, "contacts": {"19": 40}, "meets": 19, "tie": False},
                         "right": {"lowest_rib": 12, "contacts": {"19": 30, "28": 30}, "meets": 19, "tie": True}}}


def failed(result):
    return {name: check["failed"] for name, check in result["checks"].items() if check["failed"]}


class Agreement(unittest.TestCase):
    def test_a_study_that_matches_agrees(self):
        result = X.cross({"0001": fact_row()}, {"0001": count_extents()}, {"0001": count_ribs()})
        self.assertTrue(result["agree"])
        self.assertEqual(failed(result), {})

    def test_the_sternum_is_set_beside_the_counts_label_27(self):
        row = fact_row()
        row["sternum_voxels"] = 0
        result = X.cross({"0001": row}, {"0001": count_extents()}, {"0001": count_ribs()})
        self.assertEqual(failed(result), {"rib_voxels": 1})

    def test_a_repaired_row_is_left_out(self):
        rows = {"0001": fact_row(), "0001r": dict(fact_row("0001r"), repaired_from="0001")}
        result = X.cross(rows, {"0001": count_extents()}, {"0001": count_ribs()})
        self.assertTrue(result["agree"])

    def test_extents_agree_within_the_rounding(self):
        row = fact_row()
        row["labels"]["19"]["top_mm"] = -480.05
        self.assertTrue(X.cross({"0001": row}, {"0001": count_extents()}, {"0001": count_ribs()})["agree"])
        row["labels"]["19"]["top_mm"] = -480.1
        self.assertEqual(failed(X.cross({"0001": row}, {"0001": count_extents()}, {"0001": count_ribs()})),
                         {"extents_and_grid": 1})


class Disagreement(unittest.TestCase):
    def check_one_change(self, change, check):
        row, extents, ribs = fact_row(), count_extents(), count_ribs()
        change(row, extents, ribs)
        result = X.cross({"0001": row}, {"0001": extents}, {"0001": ribs})
        self.assertFalse(result["agree"])
        self.assertEqual(failed(result), {check: 1})

    def test_a_vertebra_voxel_count(self):
        self.check_one_change(lambda r, e, b: r["labels"]["19"].update(voxels=901), "vertebra_voxels")

    def test_voxels_outside_the_scheme(self):
        self.check_one_change(lambda r, e, b: e.update(outside_scheme_voxels=3), "vertebra_voxels")

    def test_a_label_the_count_never_saw(self):
        def change(row, extents, ribs):
            row["labels"]["20"] = {"voxels": 5, "bottom_mm": -520.0, "top_mm": -510.0}
            extents["voxels"]["20"] = 5
        self.check_one_change(change, "extents_and_grid")

    def test_the_grid(self):
        self.check_one_change(lambda r, e, b: e.update(dtype="int16"), "extents_and_grid")

    def test_the_lowest_rib(self):
        def change(row, extents, ribs):
            row["ribs"]["13"]["voxels"] = 60
            ribs["voxels"]["13"] = 60
        self.check_one_change(change, "lowest_ribs")

    def test_the_lowest_ribs_tally(self):
        self.check_one_change(lambda r, e, b: b["contacts"]["left"].update(contacts={"19": 41}), "lowest_ribs")

    def test_the_lowest_ribs_tie(self):
        self.check_one_change(lambda r, e, b: r["ribs"]["25"].update(tie=False), "lowest_ribs")

    def test_a_study_on_one_side_only(self):
        result = X.cross({"0001": fact_row(), "0002": fact_row("0002")},
                         {"0001": count_extents()}, {"0001": count_ribs()})
        self.assertFalse(result["agree"])
        self.assertEqual(failed(result), {})
        self.assertIn("0002", result["missing"])

    def test_a_count_with_no_contacts_still_checks_the_lowest_rib(self):
        ribs = count_ribs()
        del ribs["contacts"]
        self.assertTrue(X.cross({"0001": fact_row()}, {"0001": count_extents()}, {"0001": ribs})["agree"])


class Distances(unittest.TestCase):
    def test_touch_distances_are_compared_where_given(self):
        touch = {"0001": {"L4_sacrum": 15.3, "L5_sacrum": 0.9}}
        result = X.cross({"0001": fact_row()}, {"0001": count_extents()}, {"0001": count_ribs()}, touch)
        self.assertTrue(result["agree"])
        touch["0001"]["L4_sacrum"] = 15.4
        result = X.cross({"0001": fact_row()}, {"0001": count_extents()}, {"0001": count_ribs()}, touch)
        self.assertEqual(failed(result), {"touch_distances": 1})

    def test_no_touch_file_makes_no_distance_check(self):
        result = X.cross({"0001": fact_row()}, {"0001": count_extents()}, {"0001": count_ribs()})
        self.assertNotIn("touch_distances", result["checks"])


class Command(unittest.TestCase):
    def test_the_command_writes_its_verdict_and_exits_by_it(self):
        with tempfile.TemporaryDirectory() as folder:
            def put(name, data, lines=False):
                path = os.path.join(folder, name)
                with open(path, "w") as handle:
                    handle.write(json.dumps(data) + "\n" if lines else json.dumps(data))
                return path
            facts = put("facts.jsonl", fact_row(), lines=True)
            extents = put("extents.json", {"maskdir": "x", "studies": {"0001": count_extents()}})
            ribs = put("ribs.json", {"studies": {"0001": count_ribs()}})
            out = os.path.join(folder, "out.json")
            self.assertEqual(X.main([facts, extents, ribs, out]), 0)
            with open(out) as handle:
                self.assertTrue(json.load(handle)["agree"])
            wrong = copy.deepcopy(count_ribs())
            wrong["lowest"]["left"] = 11
            ribs = put("ribs.json", {"studies": {"0001": wrong}})
            self.assertEqual(X.main([facts, extents, ribs, out]), 1)


if __name__ == "__main__":
    unittest.main()
