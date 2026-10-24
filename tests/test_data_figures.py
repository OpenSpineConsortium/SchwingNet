"""tools/data_figures.py: the power arithmetic of chapter 35's calculator against cases computed by
hand, and the figures written from the committed records matching what the inputs give."""

import importlib.util
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("data_figures", ROOT / "tools" / "data_figures.py")
figures = importlib.util.module_from_spec(spec)
sys.modules["data_figures"] = figures
spec.loader.exec_module(figures)


class HandComputed(unittest.TestCase):
    def test_two_proportions_by_hand(self):
        # p1 0.90 against p2 0.80, alpha 0.05 two-sided, power 0.80: pbar 0.85;
        # 1.959964 x sqrt(2 x 0.85 x 0.15) = 0.989733 and 0.841621 x sqrt(0.09 + 0.16) = 0.420811;
        # (0.989733 + 0.420811)^2 / 0.01 = 198.96, so 199 a arm.
        self.assertEqual(figures.compare_n(0.90, 0.80, 0.05, 0.80), 199)

    def test_error_free_lower_bound_by_hand(self):
        # With every unit right the Wilson lower bound is n / (n + z^2), z^2 = 3.8415:
        # n / (n + 3.8415) at least 0.90 needs n at least 34.57, so 35; at least 0.85 needs 21.77, so 22.
        self.assertEqual(figures.bound_n(1.0, 0.90), 35)
        self.assertEqual(figures.bound_n(1.0, 0.85), 22)

    def test_wilson_half_width_by_hand(self):
        # n 30, p 0.9: centre (0.9 + 0.064) / 1.128 = 0.8546; half 1.7376 x sqrt(0.003 + 0.001067) = 0.1108.
        low, high = figures.wilson(27, 30, figures.z_of(0.05))
        self.assertAlmostEqual((high - low) / 2, 0.1108, places=3)
        self.assertAlmostEqual((high + low) / 2, 0.8546, places=3)
        self.assertEqual(figures.precision_n(0.9, 0.111), 30)


class TheRecordsFigures(unittest.TestCase):
    """The size-and-power analysis of 2026-10-08 gives these persons; the calculator gives them back."""

    def test_reproduces_the_recorded_targets(self):
        self.assertEqual(figures.bound_n(0.99, 0.90), 53)
        self.assertEqual(figures.bound_n(0.95, 0.90), 217)
        self.assertEqual(figures.bound_n(0.95, 0.85), 74)
        self.assertEqual(figures.bound_n(0.90, 0.85), 347)

    def test_unreachable_is_none(self):
        self.assertIsNone(figures.bound_n(0.80, 0.85))
        self.assertIsNone(figures.compare_n(0.7, 0.7))

    def test_design_effect_turns_units_into_persons(self):
        self.assertEqual(figures.persons_needed(240, 4, 4), 240)
        self.assertEqual(figures.persons_needed(19, 4, 1), 76)
        self.assertEqual(figures.persons_needed(10, 1.5, 2), 8)


class TheFigures(unittest.TestCase):
    def test_spans_follow_the_axis(self):
        self.assertEqual(figures.span_levels("C1-C3,L5-Co"), ["C1", "C2", "C3", "L5", "S1", "Co"])
        self.assertEqual(figures.span_levels(None), [])

    def test_every_record_has_a_row_with_its_source(self):
        table = figures.build_table()
        ids = {row["id"] for row in table["corpora"]}
        for path in (ROOT / "data" / "sources").glob("*.json"):
            self.assertIn(path.stem, ids)
        for row in table["corpora"]:
            self.assertTrue(row["sources"])
            for source in row["sources"]:
                self.assertTrue((ROOT / source).exists(), source)

    def test_written_files_are_what_the_inputs_give(self):
        for name, text in figures.outputs().items():
            self.assertEqual((figures.OUT / name).read_text(), text, name)
        self.assertTrue(math.isfinite(figures.z_of(0.05)))


if __name__ == "__main__":
    unittest.main()
