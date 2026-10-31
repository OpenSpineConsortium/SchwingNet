"""The comparison of the morphometry reruns' rows with the rows they replaced, on rows made to move.

One key moves by ten percent at one level and holds elsewhere, one value is lost and one gained, and
the per-study code rows carry two stamps. The tool must pair by study, level and key, order the keys
by the share of their pairs that moved, count the stamps, take the newest kept job, fail a population
it cannot pair, and write lines and a table with no study id in them.
"""
from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "grid"))

import morphometry_compare as MC  # noqa: E402

STUDIES = [f"study{n:03d}" for n in range(12)]


def write_rows(path: Path, stamp: str, moved: float, drop: str = "", add: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["study", "level", "key", "value", "note"])
        for n, study in enumerate(STUDIES):
            writer.writerow([study, "study", "code", "", stamp])
            for level in ("L4", "L5", "T12"):
                writer.writerow([study, level, "endplate", 30 + n, ""])
                width = (8 + n / 10) * (moved if level == "L5" else 1.0)
                if not (study == drop and level == "L4"):
                    writer.writerow([study, level, "pedicle_width", round(width, 4), ""])
            writer.writerow([study, "L4", "h_post", "" if study != add else 25, ""])


def make_root(base: Path) -> Path:
    root = base / "morphometry"
    for folder, rows in (("enhance", "rows.csv"), ("verse", "rows.csv"), ("verse", "totalseg/rows.csv")):
        write_rows(root / folder / "kept" / "5" / rows, "aaaaaaaaaaaaaaaa", 1.0, add="")
        write_rows(root / folder / "kept" / "40" / rows, "bbbbbbbbbbbbbbbb", 1.0, add="")
        write_rows(root / folder / rows, "cccccccccccccccc", 1.1, drop="study003", add="study004")
    return root


class Compare(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = make_root(self.tmp)
        self.out = self.tmp / "out"

    def lines(self):
        return (self.out / "report.lines").read_text(encoding="utf-8").splitlines()

    def test_pairs_orders_and_counts(self):
        self.assertEqual(MC.run(str(self.root), str(self.out)), 0)
        lines = self.lines()
        head = [line for line in lines if line.startswith("enhance_pet: the rows of job 40 ")]
        self.assertEqual(len(head), 1, lines)
        self.assertIn("studies 12 then 12, 12 in both", head[0])
        self.assertIn("code stamps then bbbbbbbbbbbbbbbb for 12 studies; now cccccccccccccccc for 12 studies",
                      "\n".join(lines))
        keyed = [line for line in lines if line.startswith("enhance_pet ")]
        self.assertTrue(keyed[0].startswith("enhance_pet pedicle_width: 3 levels, 35 pairs"), keyed)
        self.assertIn("1 values gone and 0 new", keyed[0])
        self.assertIn("largest median relative changes L5 +10.0%", keyed[0])
        endplate = [line for line in keyed if " endplate: " in line][0]
        self.assertIn("0.0% moved", endplate)
        h_post = [line for line in keyed if " h_post: " in line][0]
        self.assertIn("0 pairs", h_post)
        self.assertIn("1 new", h_post)
        self.assertFalse(any("study0" in line for line in lines))

    def test_writes_the_table_and_one_svg_a_population(self):
        MC.run(str(self.root), str(self.out))
        with open(self.out / "compare.csv", newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        l5 = [row for row in rows if row["population"] == "verse" and row["key"] == "pedicle_width" and row["level"] == "L5"]
        self.assertEqual(len(l5), 1)
        self.assertAlmostEqual(float(l5[0]["relative_median"]), 0.1, places=6)
        self.assertEqual(l5[0]["moved"], "12")
        for name in ("enhance_pet", "verse", "totalsegmentator"):
            self.assertTrue((self.out / f"compare-{name}.svg").read_text(encoding="utf-8").startswith("<svg"))
        self.assertFalse(any("study0" in str(row) for row in rows))

    def test_a_population_with_nothing_kept_fails_alone(self):
        for path in sorted((self.root / "verse" / "kept").rglob("*"), reverse=True):
            path.unlink() if path.is_file() else path.rmdir()
        (self.root / "verse" / "kept").rmdir()
        self.assertEqual(MC.run(str(self.root), str(self.out)), 3)
        lines = self.lines()
        self.assertIn("FAILED: no kept rows and new rows to set side by side for verse", lines)
        self.assertTrue(any(line.startswith("enhance_pet: ") for line in lines))

    def test_levels_run_from_the_neck_to_the_sacrum(self):
        levels = ["S1", "L5", "T12", "C7", "T1", "C2", "sacrum", "L10"]
        self.assertEqual(sorted(levels, key=MC.level_order), ["C2", "C7", "T1", "T12", "L5", "L10", "S1", "sacrum"])


if __name__ == "__main__":
    unittest.main()
