"""tools/dropzip.py, run as the job runs it (the gate word dropzip): a zip whose every file the fetch
unpacked beside it is deleted, and one with a member missing, one cut short, one named outside the
raw folder or one that is no zip at all is kept, with the report saying why.

    python3 -m unittest tests/test_dropzip.py
"""

import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEMBERS = {"study/a/1.dcm": b"one" * 100, "study/a/2.dcm": b"two" * 200, "train.csv": b"id,label\n"}


def packed(folder, name, members, unpack=True):
    """A zip of the members in the folder and, as the fetch leaves it, each member beside it."""
    archive = folder / name
    with zipfile.ZipFile(archive, "w") as out:
        for member, data in members.items():
            out.writestr(member, data)
    if unpack:
        for member, data in members.items():
            twin = folder / member
            twin.parent.mkdir(parents=True, exist_ok=True)
            twin.write_bytes(data)
    return archive


class DropzipTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raw = Path(self.tmp.name) / "raw"
        self.raw.mkdir()
        self.out = Path(self.tmp.name) / "DROPZIP-set.md"

    def tearDown(self):
        self.tmp.cleanup()

    def run_tool(self):
        done = subprocess.run([sys.executable, str(ROOT / "tools" / "dropzip.py"), "--id", "set",
                               "--raw", str(self.raw), "--out", str(self.out)],
                              capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        return self.out.read_text(encoding="ascii")

    def test_a_zip_wholly_unpacked_is_deleted_and_its_files_stay(self):
        archive = packed(self.raw, "set.zip", MEMBERS)
        said = self.run_tool()
        self.assertFalse(archive.exists())
        self.assertIn("set.zip: deleted", said)
        self.assertIn("all 3 files are unpacked beside it", said)
        for member, data in MEMBERS.items():
            self.assertEqual((self.raw / member).read_bytes(), data)

    def test_a_zip_missing_or_short_a_member_is_kept(self):
        archive = packed(self.raw, "set.zip", MEMBERS)
        (self.raw / "study" / "a" / "2.dcm").unlink()
        (self.raw / "train.csv").write_bytes(b"id\n")
        said = self.run_tool()
        self.assertTrue(archive.exists())
        self.assertIn("set.zip: kept", said)
        self.assertIn("2 of 3 files are not unpacked beside it", said)
        self.assertIn("not on disk: study/a/2.dcm", said)
        self.assertIn("freed: 0.0 GB", said)

    def test_a_zip_never_unpacked_and_a_nested_one_are_settled_apart(self):
        kept = packed(self.raw, "later.zip", {"other/x.dcm": b"x" * 10}, unpack=False)
        nested = self.raw / "part"
        nested.mkdir()
        gone = packed(nested, "inner.zip", {"y.dcm": b"y" * 10})
        said = self.run_tool()
        self.assertTrue(kept.exists())
        self.assertFalse(gone.exists())
        self.assertIn("zips: 2", said)
        self.assertIn("part/inner.zip: deleted", said)

    def test_a_member_named_outside_the_folder_keeps_its_zip(self):
        (Path(self.tmp.name) / "escape.dcm").write_bytes(b"e" * 5)
        archive = packed(self.raw, "set.zip", {"../escape.dcm": b"e" * 5}, unpack=False)
        said = self.run_tool()
        self.assertTrue(archive.exists())
        self.assertIn("1 of 1 files are not unpacked beside it", said)

    def test_a_file_that_is_no_zip_is_kept(self):
        broken = self.raw / "broken.zip"
        broken.write_bytes(b"not a zip")
        said = self.run_tool()
        self.assertTrue(broken.exists())
        self.assertIn("broken.zip: kept", said)
        self.assertIn("could not be read (BadZipFile)", said)


if __name__ == "__main__":
    unittest.main()
