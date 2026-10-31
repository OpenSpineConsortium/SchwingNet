"""tools/radiopaedia_import.py: hand-saved cases laid out for the bank recipes."""

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import radiopaedia_import as rp  # noqa: E402

JPEG = b"\xff\xd8\xff\xe0" + b"frame-a"
OTHER = b"\xff\xd8\xff\xe0" + b"frame-b"


def save(root, relative, data):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


class ArrangeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = Path(self.tmp.name) / "saved"
        self.out = Path(self.tmp.name) / "out"

    def tearDown(self):
        self.tmp.cleanup()

    def test_lays_out_by_rid_and_drops_a_repeat_in_one_case(self):
        save(self.saved, "fluoro/24796-myelogram/1.jpg", JPEG)
        save(self.saved, "fluoro/24796-myelogram/1 (copy).jpg", JPEG)
        save(self.saved, "xr/rID90103/a.jpeg", OTHER)
        self.assertEqual(rp.main(["run", "--from", str(self.saved), "--to", str(self.out)]), 0)
        digest = hashlib.sha256(JPEG).hexdigest()
        self.assertEqual((self.out / f"radiopaedia_fluoro/raw/24796/{digest[:16]}.jpg").read_bytes(), JPEG)
        self.assertTrue((self.out / "radiopaedia_xr/raw/90103").is_dir())
        cases = (self.out / "CASES.csv").read_text().splitlines()
        self.assertEqual(cases[1], "24796,fluoro,1,https://radiopaedia.org/cases/24796")
        sums = (self.out / "SHA256SUMS").read_text()
        self.assertIn("CASES.csv", sums)
        self.assertEqual(len(sums.splitlines()), 3)

    def test_the_same_image_under_two_cases_is_refused(self):
        save(self.saved, "fluoro/1/a.jpg", JPEG)
        save(self.saved, "fluoro/2/b.jpg", JPEG)
        self.assertEqual(rp.main(["plan", "--from", str(self.saved), "--to", str(self.out)]), 2)
        self.assertFalse(self.out.exists())

    def test_refusals_by_name(self):
        for relative, data in (("ct/1/a.jpg", JPEG), ("fluoro/case/a.jpg", JPEG),
                               ("fluoro/1/a.png", JPEG), ("fluoro/1/a.jpg", b"not a jpeg")):
            with self.subTest(relative=relative):
                saved = Path(self.tmp.name) / relative.replace("/", "_")
                save(saved, relative, data)
                with self.assertRaises(rp.ImportError_):
                    rp.arrange(saved)

    def test_one_case_in_two_groups_is_refused(self):
        save(self.saved, "fluoro/5/a.jpg", JPEG)
        save(self.saved, "xr/5/b.jpg", OTHER)
        kept, _ = rp.arrange(self.saved)
        with self.assertRaises(rp.ImportError_):
            rp.case_rows(kept)

    def test_a_rerun_writes_the_same_bytes(self):
        save(self.saved, "xr/7/a.jpg", OTHER)
        rp.main(["run", "--from", str(self.saved), "--to", str(self.out)])
        self.assertEqual(rp.main(["run", "--from", str(self.saved), "--to", str(self.out)]), 0)


if __name__ == "__main__":
    unittest.main()
