"""tools/stitched_fields_figure.py on drawn spines: the fields step up the column at the chosen
overlap, are lettered cranial first, cover the anchor below L5 and the top of T1, and the figure
draws one strip per case with nothing off the film turning white when a frame is inverted.

It needs numpy and Pillow, so it skips under the required check's plain python3 where either is
missing and runs wherever the figure itself can (`python3 -m unittest tests.test_stitched_fields_figure`)."""

import importlib.util
import math
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MISSING = [name for name in ("numpy", "PIL") if importlib.util.find_spec(name) is None]


def load():
    spec = importlib.util.spec_from_file_location("stitched_fields_under_test",
                                                  ROOT / "tools" / "stitched_fields_figure.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipIf(MISSING, f"needs {', '.join(MISSING)}")
class StitchedFieldsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fig = load()
        cls.case = cls.fig.demo_case(0, 0.0)

    def test_fields_are_lettered_cranial_first(self):
        fields = self.fig.place_fields(self.case.centres, 2.0)
        cranial_first = sorted(fields, key=lambda f: f.y)
        self.assertEqual([f.letter for f in cranial_first],
                         [chr(ord("a") + i) for i in range(len(fields))])

    def test_fields_cover_the_anchor_and_the_top_of_t1(self):
        fields = self.fig.place_fields(self.case.centres, 2.0)
        lowest = max(fields, key=lambda f: f.y)
        highest = min(fields, key=lambda f: f.y)
        anchor = self.fig.column_with_anchor(self.case.centres)[0]
        self.assertGreater(lowest.y + lowest.radius, anchor[1])
        self.assertLess(highest.y - highest.radius, self.case.centres[0][1])

    def test_less_overlap_takes_fewer_fields(self):
        counts = [len(self.fig.place_fields(self.case.centres, bodies)) for bodies in (0.5, 2.0, 3.0)]
        self.assertLessEqual(counts[0], counts[1])
        self.assertLessEqual(counts[1], counts[2])

    def test_the_lumbar_step_is_the_field_less_the_overlap(self):
        fields = sorted(self.fig.place_fields(self.case.centres, 2.0), key=lambda f: -f.y)
        px_per_mm = self.fig.lumbar_pitch_px(self.case.centres) / self.fig.LUMBAR_PITCH_MM
        step = math.hypot(fields[1].x - fields[0].x, fields[1].y - fields[0].y) / px_per_mm
        expected = self.fig.FIELD_MM - 2.0 * self.fig.LUMBAR_PITCH_MM
        self.assertAlmostEqual(step, expected, delta=1.0)

    def test_off_film_stays_black_after_inversion(self):
        fields = self.fig.place_fields(self.case.centres, 2.0)
        film, pad = self.fig.padded_film(self.fig.gray(self.case.image), fields)
        corner = self.fig.Field(pad - 10, pad - 10, 20.0, "x")
        frame, _ = self.fig.round_frame(film, corner)
        quarter = frame.crop((0, 0, 10, 10))
        self.assertEqual(max(quarter.getdata()), 0)

    def test_the_figure_has_one_strip_per_case(self):
        cases = [self.fig.demo_case(i, curve) for i, curve in enumerate((0.0, 0.8))]
        figure = self.fig.compose(cases, 2.0, "drawn spines")
        self.assertEqual(figure.height, self.fig.PANEL_HEIGHT + 150)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "figure.png"
            figure.save(path)
            self.assertGreater(path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
