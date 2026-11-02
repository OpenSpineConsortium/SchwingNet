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


def slice_bytes(number):
    return b"\xff\xd8\xff\xe0" + f"slice-{number}".encode()


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
        self.assertEqual((self.out / "PAIRS.csv").read_text(),
                         "rid,ct_series,ct_slices,xray_group,xray_frames,page\n")
        sums = (self.out / "SHA256SUMS").read_text()
        self.assertIn("CASES.csv", sums)
        self.assertIn("PAIRS.csv", sums)
        self.assertEqual(len(sums.splitlines()), 4)

    def test_the_same_image_under_two_cases_is_refused(self):
        save(self.saved, "fluoro/1/a.jpg", JPEG)
        save(self.saved, "fluoro/2/b.jpg", JPEG)
        self.assertEqual(rp.main(["plan", "--from", str(self.saved), "--to", str(self.out)]), 2)
        self.assertFalse(self.out.exists())

    def test_refusals_by_name(self):
        for relative, data in (("mr/1/a.jpg", JPEG), ("fluoro/case/a.jpg", JPEG),
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
        save(self.saved, "ct/7/1.jpg", slice_bytes(1))
        rp.main(["run", "--from", str(self.saved), "--to", str(self.out)])
        self.assertEqual(rp.main(["run", "--from", str(self.saved), "--to", str(self.out)]), 0)


class PairedCaseTest(unittest.TestCase):
    """A case saved as a CT and as an X-ray is one person seen both ways."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = Path(self.tmp.name) / "saved"
        self.out = Path(self.tmp.name) / "out"

    def tearDown(self):
        self.tmp.cleanup()

    def run_import(self):
        return rp.main(["run", "--from", str(self.saved), "--to", str(self.out)])

    def test_a_paired_case_is_laid_out_by_slice_and_listed(self):
        save(self.saved, "ct/24796-l6-transitional/axial/slice-10.jpg", slice_bytes(10))
        save(self.saved, "ct/24796-l6-transitional/axial/slice-2.jpg", slice_bytes(2))
        save(self.saved, "ct/24796-l6-transitional/sagittal/7.jpg", slice_bytes(7))
        save(self.saved, "xr/24796/lateral.jpg", OTHER)
        save(self.saved, "ct/555/3.jpg", slice_bytes(3))
        self.assertEqual(self.run_import(), 0)
        axial = sorted(p.name for p in (self.out / "radiopaedia_ct/raw/24796/axial").iterdir())
        self.assertEqual([name[:5] for name in axial], ["0002-", "0010-"])
        self.assertEqual(axial[0][5:], hashlib.sha256(slice_bytes(2)).hexdigest()[:16] + ".jpg")
        self.assertTrue((self.out / "radiopaedia_ct/raw/555/stack").is_dir())
        pairs = (self.out / "PAIRS.csv").read_text().splitlines()
        self.assertEqual(pairs, ["rid,ct_series,ct_slices,xray_group,xray_frames,page",
                                 "24796,2,3,xr,1,https://radiopaedia.org/cases/24796"])
        cases = (self.out / "CASES.csv").read_text().splitlines()
        self.assertEqual(cases[1:3], ["555,ct,1,https://radiopaedia.org/cases/555",
                                      "24796,ct,3,https://radiopaedia.org/cases/24796"])
        self.assertEqual(len((self.out / "SHA256SUMS").read_text().splitlines()), 7)

    def test_a_fluoroscopy_case_pairs_too(self):
        save(self.saved, "ct/9/1.jpg", slice_bytes(1))
        save(self.saved, "fluoro/9/a.jpg", JPEG)
        kept, _ = rp.arrange(self.saved)
        pairs = rp.pair_rows(kept, rp.case_rows(kept))
        self.assertEqual([(p["rid"], p["xray_group"], p["xray_frames"]) for p in pairs], [("9", "fluoro", 1)])

    def test_a_slice_name_must_hold_one_number(self):
        for name in ("a.jpg", "12 (1).jpg", "12 of 87.jpg", "20261031.jpg", "12.png", "notes.txt"):
            with self.subTest(name=name):
                saved = Path(self.tmp.name) / name.replace(" ", "_")
                save(saved, f"ct/1/{name}", slice_bytes(12))
                with self.assertRaises(rp.ImportError_):
                    rp.arrange(saved)

    def test_two_slices_of_one_number_are_refused(self):
        save(self.saved, "ct/1/12.jpg", slice_bytes(12))
        save(self.saved, "ct/1/slice-012.jpg", slice_bytes(13))
        self.assertEqual(self.run_import(), 2)
        self.assertFalse(self.out.exists())

    def test_one_slice_under_two_numbers_is_refused(self):
        save(self.saved, "ct/1/1.jpg", slice_bytes(1))
        save(self.saved, "ct/1/2.jpg", slice_bytes(1))
        with self.assertRaises(rp.ImportError_):
            rp.arrange(self.saved)

    def test_a_second_save_of_one_slice_is_dropped(self):
        save(self.saved, "ct/1/12.jpg", slice_bytes(12))
        save(self.saved, "ct/1/12 - Copy.jpg", slice_bytes(12))
        kept, duplicates = rp.arrange(self.saved)
        self.assertEqual((len(kept), len(duplicates)), (1, 1))
        self.assertTrue(duplicates[0].startswith("ct/1/12"))

    def test_the_same_slice_in_two_series_is_refused(self):
        save(self.saved, "ct/1/axial/1.jpg", slice_bytes(1))
        save(self.saved, "ct/1/sagittal/1.jpg", slice_bytes(1))
        with self.assertRaises(rp.ImportError_):
            rp.arrange(self.saved)

    def test_a_ct_slice_saved_as_the_x_ray_is_refused(self):
        save(self.saved, "ct/1/1.jpg", slice_bytes(1))
        save(self.saved, "xr/1/a.jpg", slice_bytes(1))
        with self.assertRaises(rp.ImportError_):
            rp.arrange(self.saved)

    def test_series_folders_are_refused_where_the_order_would_be_unclear(self):
        layouts = (("ct/1/3.jpg", "ct/1/axial/4.jpg"), ("ct/1/axial/deeper/4.jpg",),
                   ("ct/1/axial view/4.jpg",))
        for index, layout in enumerate(layouts):
            with self.subTest(layout=layout):
                saved = Path(self.tmp.name) / f"layout-{index}"
                for n, relative in enumerate(layout):
                    save(saved, relative, slice_bytes(n))
                with self.assertRaises(rp.ImportError_):
                    rp.arrange(saved)

    def refusal(self, layout):
        """The message a saved layout is refused with."""
        for relative, data in layout:
            save(self.saved, relative, data)
        with self.assertRaises(rp.ImportError_) as caught:
            rp.arrange(self.saved)
        return str(caught.exception)

    def test_a_ct_case_saved_in_two_folders_is_refused(self):
        layouts = ((("ct/5-axial/21.jpg", 21), ("ct/5-axial/22.jpg", 22), ("ct/5-sagittal/1.jpg", 1)),
                   (("ct/5-a/1.jpg", 1), ("ct/5-b/axial/2.jpg", 2), ("xr/5/a.jpg", 99)),
                   (("ct/5/1.jpg", 1), ("ct/rID5/2.jpg", 2)))
        for index, layout in enumerate(layouts):
            with self.subTest(layout=layout):
                self.saved = Path(self.tmp.name) / f"two-folders-{index}"
                message = self.refusal([(relative, slice_bytes(n)) for relative, n in layout])
                self.assertIn("a CT case is one folder", message)

    def test_two_film_folders_of_one_rid_are_one_case(self):
        save(self.saved, "xr/5-ap/a.jpg", JPEG)
        save(self.saved, "xr/5-lateral/b.jpg", OTHER)
        kept, _ = rp.arrange(self.saved)
        self.assertEqual(rp.case_rows(kept), [{"rid": "5", "group": "xr", "frames": 2,
                                               "page": "https://radiopaedia.org/cases/5"}])

    def test_a_file_above_the_case_folders_is_refused_by_name(self):
        for index, stray in enumerate(("ct/12.jpg", "xr/a.jpg", "fluoro/a.jpg", "notes.jpg", "desktop.ini")):
            with self.subTest(stray=stray):
                self.saved = Path(self.tmp.name) / f"stray-{index}"
                message = self.refusal([(stray, slice_bytes(12)), ("xr/5/b.jpg", OTHER)])
                self.assertIn(Path(stray).name, message)
                self.assertIn("belongs to no case", message)

    def test_the_same_slice_in_two_series_is_refused_as_such(self):
        message = self.refusal([("ct/5/axial/1.jpg", slice_bytes(1)), ("ct/5/sagittal/1.jpg", slice_bytes(1))])
        self.assertIn("belongs to one series", message)
        self.assertNotIn("numbers", message)

    def test_one_slice_under_two_numbers_names_the_numbers(self):
        message = self.refusal([("ct/5/axial/1.jpg", slice_bytes(1)), ("ct/5/axial/2.jpg", slice_bytes(1))])
        self.assertIn("one of its two numbers is wrong", message)

    def test_a_stray_file_beside_series_folders_is_refused_by_name(self):
        message = self.refusal([("ct/5/axial/1.jpg", slice_bytes(1)), ("ct/5/Thumbs.db", b"x")])
        self.assertIn("Thumbs.db", message)
        self.assertIn("not a .jpg", message)

    def test_a_ct_beside_both_x_ray_groups_is_refused(self):
        save(self.saved, "ct/5/1.jpg", slice_bytes(1))
        save(self.saved, "fluoro/5/a.jpg", JPEG)
        save(self.saved, "xr/5/b.jpg", OTHER)
        kept, _ = rp.arrange(self.saved)
        with self.assertRaises(rp.ImportError_):
            rp.case_rows(kept)


if __name__ == "__main__":
    unittest.main()
