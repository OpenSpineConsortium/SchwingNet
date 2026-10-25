"""tools/folder_report.py: an unmapped group broken down by its first folders, in pages (#296)."""
import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


folder_report = load("folder_report")
sample_index = load("sample_index")


class FolderReport(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        bank = self.tmp / "data" / "realxray"
        (bank / "carm").mkdir(parents=True)
        (bank / "README.md").write_text("Real C-arm frames from CArmLSpine.\n\nBuilt by tools/x.py\n", encoding="utf-8")
        self.db = self.tmp / "samples.sqlite"
        db = sqlite3.connect(self.db)
        db.executescript(sample_index.SCHEMA)
        db.execute("INSERT INTO root (id, path, sources) VALUES (1, ?, 'unmapped:realxray')", (str(bank),))
        db.execute("INSERT INTO root (id, path, sources) VALUES (2, '/x/known', 'carmlspine')")
        rows = [(1, "carm/cervical_c5_001.png", "image", "png", 100, 512, 480, 1, None),
                (1, "carm/thoracic/a.dcm", "image", "dicom", 300, 1024, 1024, 30, "RF"),
                (1, "README.md", "other", "text", 50, None, None, None, None),
                (2, "known/b.png", "image", "png", 10, 9, 9, 1, None)]
        for root, rel, role, fmt, size, width, height, frames, modality in rows:
            db.execute("""INSERT INTO file (path, root_id, rel, role, format, size, width, height, frames, modality,
                          manufacturer, model) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                       (str(bank / rel), root, rel, role, fmt, size, width, height, frames, modality,
                        "Siemens" if modality else None, "Cios" if modality else None))
        db.commit()
        db.close()

    def test_an_unmapped_group_is_broken_down_and_a_known_one_left_out(self):
        out = self.tmp / "logs" / "FOLDERS.md"
        out.parent.mkdir()
        data = str(self.tmp / "data")
        self.assertEqual(folder_report.main(["--db", str(self.db), "--out", str(out), "--data-root", data]), 0)
        text = (out.parent / "FOLDERS-1.md").read_text(encoding="ascii")
        self.assertIn("## realxray", text)
        self.assertNotIn("## known", text)
        self.assertIn("| realxray | 450 B | 3 | unmapped:realxray 3 |", text)
        self.assertIn("| carm | 2 | 400 B | 2 | dicom 1, png 1 | 512-1024 x 480-1024 | 1 | fluoro 2, cervical 1, thoracic 1 |", text)
        self.assertIn("DICOM modality: RF 1. Maker and model: Siemens Cios 1.", text)
        self.assertIn("    Real C-arm frames from CArmLSpine.", text)
        self.assertNotIn("cervical_c5_001", text)

    def test_a_folder_name_that_is_not_ascii_is_escaped_not_fatal(self):
        db = sqlite3.connect(self.db)
        db.execute("INSERT INTO file (path, root_id, rel, role, format, size) VALUES (?, 1, ?, 'image', 'png', 7)",
                   (str(self.tmp / "data" / "realxray" / "\u8170\u690e" / "a.png"), "\u8170\u690e/a.png"))
        db.commit()
        db.close()
        out = self.tmp / "logs" / "FOLDERS.md"
        out.parent.mkdir()
        self.assertEqual(folder_report.main(["--db", str(self.db), "--out", str(out), "--data-root", str(self.tmp / "data")]), 0)
        self.assertIn("| \\u8170\\u690e | 1 |", (out.parent / "FOLDERS-1.md").read_text(encoding="ascii"))

    def test_a_long_report_is_cut_into_pages_under_the_limit(self):
        sections = ["head\n"] + [f"## g{n}\n" + "x" * 300 + "\n" for n in range(10)]
        pages = folder_report.pages(sections, 1000)
        self.assertGreater(len(pages), 2)
        self.assertTrue(all(len(page) <= 1000 + 20 for page in pages))
        self.assertEqual("".join(pages).count("## g"), 10)


if __name__ == "__main__":
    unittest.main()
