"""The second reading of ENHANCE.PET's masks (holdings/enhance_facts_check.py) on hand-made volumes with
known answers, and its comparison with the first.

Run from the repository's root with `python -m unittest discover -s holdings/tests -t .`."""
import json, os, sys, tempfile, unittest, math
import numpy as np, nibabel as nib

from holdings import enhance_facts_check as fb


def write(folder, name, data, zooms):
    affine = np.diag(list(zooms) + [1.0])
    nib.save(nib.Nifti1Image(data.astype(np.uint8), affine), os.path.join(folder, name))


class Synthetic(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.mkdir(os.path.join(self.tmp, "m")); os.mkdir(os.path.join(self.tmp, "r"))
        self.zooms = (1.0, 1.0, 2.5)
        v = np.zeros((40, 40, 30), np.uint8)
        v[10:20, 10:20, 2:6] = 22    # L3 slices 2..5
        v[10:20, 10:20, 8:12] = 23   # L4 slices 8..11: gap of 2 slices -> 3 * 2.5 = 7.5 mm
        v[10:20, 10:20, 13:17] = 28  # sacrum: gap 1 slice -> 2 * 2.5 = 5.0 mm from L4
        v[30, 30, 29] = 26           # a hip voxel, never a contact
        v[0, 0, 0] = 30              # outside the scheme
        r = np.zeros_like(v)
        r[21:26, 12:14, 9] = 15      # right rib 2: x 21..25 at slice 9 next to L4 (x 19)
        r[21, 15, 3] = 15            # one voxel next to L3, distance 2 mm
        r[31, 30, 29] = 3            # rib 3 next to the hip only: no contact
        r[5, 5, 5] = 27
        write(os.path.join(self.tmp, "m"), "0001.nii.gz", v, self.zooms)
        write(os.path.join(self.tmp, "r"), "0001.nii.gz", r, self.zooms)

    def test_row(self):
        row = fb.study_facts("0001", os.path.join(self.tmp, "m"), os.path.join(self.tmp, "r"))
        self.assertEqual(row["labels"]["22"]["voxels"], 400)
        self.assertEqual(row["outside_scheme_voxels"], {"vertebrae": 1, "ribs": 0})
        self.assertEqual(row["sternum_voxels"], 1)
        self.assertEqual(row["distances_mm"], {"22-23": 7.5, "22-28": 20.0, "23-28": 5.0})
        rib = row["ribs"]["15"]
        # x 21 is 2 mm from x 19, x 22 is 3 mm (counted, at the limit), x 23 is 4 mm.
        self.assertEqual(rib["contacts"], {"22": 1, "23": 4})
        self.assertEqual((rib["lead"], rib["lead_n"], rib["tie"]), (23, 4, False))
        self.assertEqual(row["ribs"]["3"]["contacts"], {})
        self.assertIsNone(row["ribs"]["3"]["lead"])
        self.assertTrue(row["b_audit"]["ribs"]["15"]["offsets_agree"])
        self.assertEqual(row["b_audit"]["ribs"]["15"]["at_limit_voxels"], 2)

    def test_tie_and_lead(self):
        self.assertEqual(fb.lead_of({20: 5, 19: 5, 21: 1}), (19, 5, True))
        self.assertEqual(fb.lead_of({}), (None, 0, False))

    def test_boundary_distance_matches_edt(self):
        rng = np.random.default_rng(0)
        v = np.zeros((30, 30, 20), np.uint8)
        v[rng.random(v.shape) < 0.02] = 5
        v[rng.random(v.shape) < 0.02] = 6
        boxes = fb.label_boxes(v)
        z = (0.8, 0.9, 2.5)
        edt, _ = fb.shortest_distance(v, boxes, 5, 6, z)
        self.assertAlmostEqual(edt, fb.boundary_distance(v, boxes, 5, 6, z), places=9)

    def test_equidistant(self):
        v = np.zeros((20, 20, 5), np.uint8)
        v[8, 10, 2] = 10; v[12, 10, 2] = 11
        r = np.zeros_like(v); r[10, 10, 2] = 4
        groups = fb.offset_groups((1.0, 1.0, 1.0), 3.0)
        best, low, high = fb.nearest_by_offsets(v, np.nonzero(r == 4), groups)
        self.assertEqual((best[0], low[0], high[0]), (2.0, 10, 11))


class Compare(unittest.TestCase):
    ROW = {"id": "0001", "labels": {"19": {"voxels": 10}}, "sternum_voxels": 3,
           "ribs": {"12": {"voxels": 5, "contacts": {"19": 4}, "lead": 19, "tie": False}},
           "distances_mm": {"19-20": 1.2}}

    def compared(self, a_rows, b_rows):
        folder = tempfile.mkdtemp()
        paths = []
        for name, rows in (("a.jsonl", a_rows), ("b.jsonl", b_rows)):
            paths.append(os.path.join(folder, name))
            with open(paths[-1], "w") as handle:
                handle.writelines(json.dumps(row) + "\n" for row in rows)
        return fb.compare(*paths)

    def test_two_equal_readings_agree(self):
        result = self.compared([self.ROW], [self.ROW])
        self.assertEqual((result["studies"], result["agree"], result["disagree_by_field"]), (1, 1, {}))

    def test_a_distance_on_a_rounding_edge_still_agrees(self):
        other = json.loads(json.dumps(self.ROW))
        other["distances_mm"]["19-20"] = 1.3
        self.assertEqual(self.compared([self.ROW], [other])["agree"], 1)

    def test_a_lead_that_moves_is_named_and_a_lone_study_is_listed(self):
        other = json.loads(json.dumps(self.ROW))
        other["ribs"]["12"].update(contacts={"18": 4}, lead=18)
        lone = dict(self.ROW, id="0002")
        result = self.compared([self.ROW, lone], [other])
        self.assertEqual(result["disagree_by_field"], {"rib_contacts": ["0001"], "rib_contacts_unexplained": ["0001"],
                                                       "rib_leads": ["0001"]})
        self.assertEqual(result["only_a"], ["0002"])
        self.assertFalse(fb.holds(result))

    def test_a_contact_count_the_audit_explains_and_a_repaired_row_still_hold(self):
        other = json.loads(json.dumps(self.ROW))
        other["ribs"]["12"]["contacts"] = {"19": 3}
        other["b_audit"] = {"ribs": {"12": {"equidistant_voxels": 0, "at_limit_voxels": 1}}}
        repaired = dict(self.ROW, id="0001r")
        result = self.compared([self.ROW, repaired], [other])
        self.assertEqual(result["disagree_by_field"], {"rib_contacts": ["0001"]})
        self.assertEqual(result["contacts_moved"], {"0001": {"12": [1, 1]}})
        self.assertTrue(fb.holds(result))

    def test_a_tie_voxel_moves_two_counts_and_a_larger_move_is_a_fault(self):
        other = json.loads(json.dumps(self.ROW))
        other["ribs"]["12"]["contacts"] = {"19": 3, "20": 1}
        other["b_audit"] = {"ribs": {"12": {"equidistant_voxels": 1, "at_limit_voxels": 0}}}
        self.assertTrue(fb.holds(self.compared([self.ROW], [other])))
        other["ribs"]["12"]["contacts"] = {"19": 2, "20": 2}
        result = self.compared([self.ROW], [other])
        self.assertEqual(result["disagree_by_field"], {"rib_contacts": ["0001"], "rib_contacts_unexplained": ["0001"]})
        self.assertFalse(fb.holds(result))

    def test_a_limit_voxel_both_readings_name_is_one_count(self):
        audit = {"equidistant_voxels": 0, "at_limit_voxels": 9, "within_1e-4_mm_of_limit": 9, "offsets_agree": True}
        self.assertEqual(fb.limit_voxels(audit), 9)
        self.assertEqual(fb.limit_voxels(dict(audit, offsets_agree=False)), 18)
        self.assertEqual(fb.limit_voxels({"at_limit_voxels": 2}), 2)
        other = json.loads(json.dumps(self.ROW))
        other["ribs"]["12"]["contacts"] = {"19": 2}
        other["b_audit"] = {"ribs": {"12": dict(audit, at_limit_voxels=1, **{"within_1e-4_mm_of_limit": 1})}}
        result = self.compared([self.ROW], [other])
        self.assertEqual(result["contacts_moved"], {"0001": {"12": [2, 1]}})
        self.assertFalse(fb.holds(result))

    def test_the_command_exits_by_whether_the_comparison_holds(self):
        folder = tempfile.mkdtemp()
        other = json.loads(json.dumps(self.ROW))
        other["sternum_voxels"] = 4
        paths = {}
        for name, rows in (("a", [self.ROW]), ("same", [self.ROW]), ("other", [other])):
            paths[name] = os.path.join(folder, name + ".jsonl")
            with open(paths[name], "w") as handle:
                handle.writelines(json.dumps(row) + "\n" for row in rows)
        out = os.path.join(folder, "out.json")
        self.assertEqual(fb.compare_main([paths["a"], paths["same"], out]), 0)
        self.assertEqual(fb.compare_main([paths["a"], paths["other"], out]), 1)
        with open(out) as handle:
            self.assertFalse(json.load(handle)["holds"])


class Resume(unittest.TestCase):
    """A requeued run reads the partial rows an earlier run left, whatever the cut left of them."""

    def partial(self, text):
        path = os.path.join(tempfile.mkdtemp(), "b.jsonl.partial")
        with open(path, "w") as handle:
            handle.write(text)
        return path

    def test_a_line_cut_short_is_skipped_and_closed_before_the_next_row(self):
        path = self.partial('{"id": "0001", "labels": {}}\n{"id": "0002", "lab')
        self.assertEqual(fb.done_ids(path), {"0001"})
        fb.end_last_line(path)
        with open(path, "a") as handle:
            handle.write('{"id": "0002", "labels": {}}\n')
        self.assertEqual(fb.done_ids(path), {"0001", "0002"})
        out = path[:-len(".partial")]
        self.assertEqual(fb.finish(path, out), (2, 0))
        with open(out) as handle:
            self.assertEqual([json.loads(line)["id"] for line in handle], ["0001", "0002"])

    def test_a_study_that_failed_is_read_again_and_its_last_row_stands(self):
        path = self.partial('{"id": "0001", "error": "MemoryError: "}\n')
        self.assertEqual(fb.done_ids(path), set())
        self.assertEqual(fb.finish(path, path + ".out"), (1, 1))
        with open(path, "a") as handle:
            handle.write('{"id": "0001", "labels": {}}\n')
        self.assertEqual(fb.done_ids(path), {"0001"})
        self.assertEqual(fb.finish(path, path + ".out"), (1, 0))

    def test_closing_a_whole_file_adds_nothing(self):
        path = self.partial('{"id": "0001"}\n')
        fb.end_last_line(path)
        with open(path) as handle:
            self.assertEqual(handle.read(), '{"id": "0001"}\n')


if __name__ == "__main__":
    unittest.main()
