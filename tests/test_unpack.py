"""tools/unpack.py and grid/unpack.sbatch, as the gate word unpack runs them: a zip's members land
beside it where the fetch would have put them, through a .part file, a member already whole is
left, a member named outside the raw folder is never written, and the job writes nothing until
the size rule admits what the unpacked files take, refusing whole where they would not fit.

    python3 -m unittest tests/test_unpack.py
"""

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEMBERS = {"study/a/1.dcm": b"one" * 100, "study/a/2.dcm": b"two" * 200, "train.csv": b"id,label\n"}
TOTAL = sum(len(data) for data in MEMBERS.values())


def chain_helpers():
    """The size rule's stand-ins, kept with the X-ray chain's tests."""
    spec = importlib.util.spec_from_file_location("xray_chain_helpers", ROOT / "tests" / "test_xray_chain.py")
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    return helpers


def zipped(folder, name, members):
    archive = folder / name
    with zipfile.ZipFile(archive, "w") as out:
        for member, data in members.items():
            out.writestr(member, data)
    return archive


class UnpackToolTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raw = Path(self.tmp.name) / "raw"
        self.raw.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def tool(self, *args):
        done = subprocess.run([sys.executable, str(ROOT / "tools" / "unpack.py"), *args],
                              capture_output=True, text=True, check=False)
        return done.returncode, done.stdout

    def test_size_gives_what_is_still_to_land(self):
        zipped(self.raw, "set.zip", MEMBERS)
        self.assertEqual(self.tool("size", "--raw", str(self.raw)), (0, f"{TOTAL} {TOTAL} the zips central directories\n"))
        (self.raw / "train.csv").write_bytes(MEMBERS["train.csv"])
        need = TOTAL - len(MEMBERS["train.csv"])
        self.assertEqual(self.tool("size", "--raw", str(self.raw))[1], f"{TOTAL} {need} the zips central directories\n")

    def test_unpack_lands_every_member_beside_its_zip_and_dropzip_then_finds_them(self):
        archive = zipped(self.raw, "set.zip", MEMBERS)
        (self.raw / "train.csv").write_bytes(MEMBERS["train.csv"])
        out = Path(self.tmp.name) / "UNPACK-set.md"
        code, said = self.tool("unpack", "--id", "set", "--raw", str(self.raw), "--out", str(out))
        self.assertEqual(code, 0, said)
        for member, data in MEMBERS.items():
            self.assertEqual((self.raw / member).read_bytes(), data)
        self.assertEqual(list(self.raw.rglob("*.part")), [])
        self.assertTrue(archive.exists())
        report = out.read_text(encoding="ascii")
        self.assertIn("set.zip: 3 files; 2 written", report)
        self.assertIn("1 already there", report)
        self.assertIn("still to land: 0.0 GB", report)
        self.assertEqual(self.tool("size", "--raw", str(self.raw))[1], f"{TOTAL} 0 the zips central directories\n")

    def test_a_member_named_outside_the_folder_is_never_written(self):
        zipped(self.raw, "set.zip", {"../escape.dcm": b"e" * 5, "inside.dcm": b"i" * 5})
        out = Path(self.tmp.name) / "UNPACK-set.md"
        self.assertEqual(self.tool("unpack", "--id", "set", "--raw", str(self.raw), "--out", str(out))[0], 0)
        self.assertFalse((Path(self.tmp.name) / "escape.dcm").exists())
        self.assertTrue((self.raw / "inside.dcm").exists())
        self.assertIn("1 named outside the raw folder and left", out.read_text(encoding="ascii"))

    def test_a_file_that_is_no_zip_gives_no_size(self):
        (self.raw / "broken.zip").write_bytes(b"not a zip")
        code, said = self.tool("size", "--raw", str(self.raw))
        self.assertEqual(code, 1)
        self.assertIn("BadZipFile", said)


class UnpackJobTest(unittest.TestCase):
    """grid/unpack.sbatch under the size rule, with the X-ray chain's stand-ins for CephFS and Slurm."""

    def setUp(self):
        helpers = chain_helpers()
        self.gb = helpers.GB
        self.repo = helpers.repo_copy(self)
        (self.repo / "tools").mkdir()
        for name in ("unpack.py", "dropzip.py"):
            shutil.copy(ROOT / "tools" / name, self.repo / "tools" / name)
        self.volume = helpers.volume_in(self, quota=20 * self.gb, used=10 * self.gb)
        self.raw = self.volume.data / "set" / "raw"
        self.raw.mkdir(parents=True)
        zipped(self.raw, "set.zip", MEMBERS)

    def job(self, **extra):
        env = dict(os.environ, SCHWINGNET=str(self.repo), PYDRV=sys.executable, XATTR_PYTHON=sys.executable,
                   UNPACK_ID="set", UNPACK_RAW=str(self.raw), SLURM_JOB_ID="77", **self.volume.env(**extra))
        done = subprocess.run(["bash", str(self.repo / "grid" / "unpack.sbatch")], env=env, cwd=self.repo / "grid",
                              capture_output=True, text=True, timeout=120)
        return done.returncode, done.stdout + done.stderr

    def test_it_unpacks_once_admitted_and_holds_its_room(self):
        code, out = self.job()
        self.assertEqual(code, 0, out)
        self.assertIn("set: admitted", out)
        for member, data in MEMBERS.items():
            self.assertEqual((self.raw / member).read_bytes(), data)
        state, job, need = (self.volume.data / "set" / "meta" / "SIZE").read_text(encoding="utf-8").split()[:3]
        self.assertEqual((state, job, need), ("admitted", "77", str(TOTAL)))
        self.assertTrue((self.repo / "grid" / "logs" / "UNPACK-set.md").exists())

    def test_it_writes_nothing_where_the_room_is_too_small(self):
        self.volume.attribute(self.volume.path, "ceph.dir.rbytes", 20 * self.gb)
        code, out = self.job()
        self.assertEqual(code, 4, out)
        self.assertIn("set: refused for space", out)
        self.assertEqual(sorted(path.name for path in self.raw.iterdir()), ["set.zip"])
        self.assertFalse((self.repo / "grid" / "logs" / "UNPACK-set.md").exists())


if __name__ == "__main__":
    unittest.main()
