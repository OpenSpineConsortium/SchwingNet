"""tools/bench_public.py (issue #287): the rules that score a public model against the record, fixed
before any frame was scored. A FleXray channel names its level; a bank box maps onto FleXray's
padded square canvas; a box takes the level that covers most of it, or none under a quarter; a
tally reads accuracy over detected bodies and over all, with the Wilson interval, one-off errors
and truth levels with no channel apart; xvr's CSV sums to its median final mTRE. Standard library
only, so the required check runs it; the model runs on the grid alone."""

import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

try:
    import numpy
except ImportError:
    numpy = None

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("bench_public", ROOT / "tools" / "bench_public.py")
bench = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bench)


def row(truth, named, view="lateral", has_channel=True):
    return {"truth": truth, "named": named, "view": view, "has_channel": has_channel}


class ChannelTest(unittest.TestCase):
    def test_a_channel_names_its_level_and_nothing_else(self):
        self.assertEqual(bench.level_of_channel("vertebra_l4"), "L4")
        self.assertEqual(bench.level_of_channel("vertebra_t12"), "T12")
        self.assertEqual(bench.level_of_channel("vertebra_c1"), "C1")
        self.assertEqual(bench.level_of_channel("sacrum"), "sacrum")
        for name in ("hips", "femurs", "lumbar_spine", "vertebra_x1", "ribs_1"):
            self.assertIsNone(bench.level_of_channel(name), name)

    def test_a_truth_box_reads_s1_as_the_sacrum_and_refuses_what_is_no_level(self):
        self.assertEqual(bench.truth_level("S1"), "sacrum")
        self.assertEqual(bench.truth_level("L6"), "L6")
        self.assertIsNone(bench.truth_level(None))
        self.assertIsNone(bench.truth_level("L9"))


class CanvasTest(unittest.TestCase):
    def test_a_wide_frame_is_padded_top_and_bottom_and_scaled_to_the_canvas(self):
        # 512 wide, 256 high: padded to 512 square, 128 rows above, then halved to 256
        self.assertEqual(bench.canvas_box([0, 0, 512, 256], 256, 512), (64, 192, 0, 256))
        self.assertEqual(bench.canvas_box([100, 50, 200, 150], 256, 512), (89, 139, 50, 100))

    def test_a_square_frame_maps_straight_and_a_tiny_box_keeps_one_pixel(self):
        self.assertEqual(bench.canvas_box([0, 0, 1024, 1024], 1024, 1024), (0, 256, 0, 256))
        r0, r1, c0, c1 = bench.canvas_box([10, 10, 10.5, 10.5], 1024, 1024)
        self.assertEqual((r1 - r0, c1 - c0), (1, 1))
        r0, r1, c0, c1 = bench.canvas_box([1023, 1023, 1024, 1024], 1024, 1024)
        self.assertEqual((r0, r1, c0, c1), (255, 256, 255, 256))


class NamingTest(unittest.TestCase):
    def test_a_box_takes_the_level_that_covers_most_of_it(self):
        self.assertEqual(bench.name_box({"L3": 0.3, "L4": 0.6}), "L4")

    def test_a_box_no_level_covers_a_quarter_of_is_undetected(self):
        self.assertIsNone(bench.name_box({"L3": 0.2, "L4": 0.24}))
        self.assertIsNone(bench.name_box({}))
        self.assertEqual(bench.name_box({"L4": bench.DETECTED_SHARE}), "L4")

    def test_a_tie_goes_to_the_level_higher_in_the_spine_whatever_the_order(self):
        self.assertEqual(bench.name_box({"L5": 0.5, "L4": 0.5}), "L4")
        self.assertEqual(bench.name_box({"L4": 0.5, "L5": 0.5}), "L4")

    def test_one_off_is_the_neighbouring_level_only(self):
        self.assertTrue(bench.one_off("L5", "L4"))
        self.assertTrue(bench.one_off("sacrum", "L6"))
        self.assertTrue(bench.one_off("L1", "T12"))
        self.assertFalse(bench.one_off("L2", "L4"))
        self.assertFalse(bench.one_off(None, "L4"))


class TallyTest(unittest.TestCase):
    def test_accuracy_is_read_over_detected_bodies_and_over_all(self):
        rows = [row("L1", "L1"), row("L2", "L2"), row("L3", "L4"), row("L4", None),
                row("L6", "L5", has_channel=False)]
        t = bench.tally(rows)
        self.assertEqual((t["bodies"], t["detected"], t["correct"]), (4, 3, 2))
        self.assertAlmostEqual(t["accuracy_detected"], 2 / 3)
        self.assertAlmostEqual(t["accuracy_all"], 2 / 4)
        self.assertEqual((t["wrong"], t["wrong_one_off"], t["no_channel"]), (1, 1, 1))
        low, high = t["accuracy_detected_ci"]
        self.assertLess(low, 2 / 3)
        self.assertGreater(high, 2 / 3)

    def test_nothing_counted_reads_as_no_accuracy_and_the_whole_interval(self):
        t = bench.tally([])
        self.assertIsNone(t["accuracy_detected"])
        self.assertEqual(t["accuracy_all_ci"], (0.0, 1.0))

    def test_the_wilson_interval_of_595_of_617(self):
        # A2.1's count; its reported interval, [92.3, 98.4], is wider than Wilson's, so this
        # tool's intervals are set beside the record's as each side computed them, never mixed.
        low, high = bench.wilson(595, 617)
        self.assertAlmostEqual(low, 0.9466, places=4)
        self.assertAlmostEqual(high, 0.9763, places=4)

    def test_views_are_tallied_apart_and_together(self):
        rows = [row("L1", "L1", "lateral"), row("L2", "L3", "ap"), row("L3", "L3", "ap")]
        by = bench.tally_by_view(rows)
        self.assertEqual(by["all"]["bodies"], 3)
        self.assertEqual(by["ap"]["correct"], 1)
        self.assertEqual(by["lateral"]["correct"], 1)
        self.assertNotIn("oblique", by)

    def test_a_meta_view_maps_to_its_group(self):
        self.assertEqual(bench.view_group({"view": "LAT2"}), "lateral")
        self.assertEqual(bench.view_group({"view": "AP"}), "ap")
        self.assertEqual(bench.view_group({"view": "OBL"}), "oblique")
        self.assertEqual(bench.view_group({}), "other")


class XvrSummaryTest(unittest.TestCase):
    def test_the_csv_sums_to_the_median_final_mtre_and_the_submillimetre_share(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "registration.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                out = csv.DictWriter(handle, ["pose", "mTRE_cpos", "runtime"])
                out.writeheader()
                for pose, mtre, runtime in (("init", 40, 0), ("final", 0.5, 7), ("final", 1.5, 9), ("final", 0.9, 8)):
                    out.writerow({"pose": pose, "mTRE_cpos": mtre, "runtime": runtime})
            bench.main(["xvr-summary", "--csv", str(path), "--out", td])
            summary = json.loads((Path(td) / "xvr-deepfluoro.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["views"], 3)
        self.assertEqual(summary["median_mtre_mm"], 0.9)
        self.assertAlmostEqual(summary["submillimetre_share"], 2 / 3)
        self.assertEqual(summary["median_runtime_s"], 8)


class Group(dict):
    """An h5py group as far as deepfluoro_views reads one: keys, and paths through subgroups."""

    def __getitem__(self, path):
        node = self
        for part in path.split("/"):
            node = dict.__getitem__(node, part)
        return node


@unittest.skipIf(numpy is None, "numpy is in the train environment")
class DeepFluoroViewsTest(unittest.TestCase):
    def test_a_views_segmentation_is_read_from_its_image_group_or_as_an_array(self):
        np = numpy
        labels = np.array([[0, 1], [2, 3]], dtype="uint8")
        image = Group(pixels=np.ones((2, 2), dtype="float32"))
        grouped = Group({"dir-mat": np.eye(2), "origin": np.zeros(2), "pixels": labels, "spacing": np.ones(2)})
        projections = Group({"000": Group(image=image, **{"gt-seg": grouped}),
                             "001": Group(image=image, **{"gt-seg": labels}),
                             "002": Group(image=image)})
        h5 = Group({"17-1882": Group(projections=projections)})
        views = list(bench.deepfluoro_views(h5))
        self.assertEqual([(s, v) for s, v, *_ in views], [("subject01", "000"), ("subject01", "001")])
        for _subject, _view, _pixels, read, rotate in views:
            self.assertEqual(read.dtype, np.uint8)
            self.assertTrue((read == labels).all())
            self.assertFalse(rotate)


if __name__ == "__main__":
    unittest.main()
