"""tools/bordercall_vendor.py on a made-up clone: copy() reads the old package from the clone's
archive/ and the engine's packages from its root, leaves their tests behind, records every file
in VENDORED, and check() holds the copy to that record; morphometry's code stamp, which names
every run on the grid, is the same over the copy as over the clone. The clone is a real git
repository in a temporary folder, since copy() reads its commit and refuses a dirty tree.
Standard library only, so the required check runs it."""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import bordercall_vendor as BV  # noqa: E402

# git's automatic maintenance runs detached and races a test's cleanup, so each scratch
# repository is made with it off, in the environment and in its own config
QUIET = {"gc.auto": "0", "gc.autoDetach": "false", "maintenance.auto": "false",
         "maintenance.autoDetach": "false", "receive.autogc": "false"}
GIT_ENV = dict(os.environ, GIT_CONFIG_COUNT=str(len(QUIET)),
               **{f"GIT_CONFIG_KEY_{i}": k for i, k in enumerate(QUIET)},
               **{f"GIT_CONFIG_VALUE_{i}": v for i, v in enumerate(QUIET.values())})
GIT_ENV.update(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")

# the clone's layout since the engine replaced the old package: the archive and the three packages
CLONE_FILES = {
    "archive/bordercall/run.py": "print('run')\n",
    "archive/bordercall/reference/table.csv": "a,b\n1,2\n",
    "archive/testdata/x": "fixture\n",
    "archive/README.md": "the old package\n",
    "archive/HANDOFF.md": "handoff\n",
    "archive/requirements.txt": "numpy\n",
    "morphometry/__init__.py": "",
    "morphometry/a.py": "A = 1\n",
    "morphometry/tests/t.py": "assert True\n",
    "scanimport/__init__.py": "",
    "scanimport/b.py": "B = 2\n",
    "scanimport/tests/__init__.py": "",
    "screening/c.py": "C = 3\n",
    "screening/tables.json": "{}\n",
}


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(repo), *args], env=GIT_ENV, capture_output=True, text=True, check=True)
    return done.stdout.strip()


def make_clone(root: Path, files=CLONE_FILES) -> str:
    """A committed git repository holding FILES; its commit's sha."""
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    if "morphometry/a.py" in files:  # a cache beside the sources, which the copy leaves behind
        (root / "morphometry" / "__pycache__").mkdir(parents=True, exist_ok=True)
        (root / "morphometry" / "__pycache__" / "a.cpython-312.pyc").write_bytes(b"\x00")
    git(root, "init", "-q")
    for key, value in QUIET.items():
        git(root, "config", key, value)
    (root / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "c")
    return git(root, "rev-parse", "HEAD")


def code_stamp(root: Path) -> str:
    """morphometry.__main__.code_stamp's rule: sha256 over name, NUL and bytes of each top-level
    .py of morphometry and scanimport, names sorted, the first 16 hex digits."""
    h = hashlib.sha256()
    for pkg in ("morphometry", "scanimport"):
        for name in sorted(os.listdir(root / pkg)):
            if name.endswith(".py"):
                h.update(name.encode() + b"\0" + (root / pkg / name).read_bytes())
    return h.hexdigest()[:16]


def quiet(call, *args):
    out = StringIO()
    with redirect_stdout(out):
        rc = call(*args)
    return rc, out.getvalue()


class BordercallVendorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.clone = self.tmp / "clone"
        self.clone.mkdir()
        self.target = self.tmp / "grid" / "bordercall"
        self.record = self.target / "VENDORED"
        self.old = (BV.TARGET, BV.RECORD)
        BV.TARGET, BV.RECORD = self.target, self.record
        self.addCleanup(self.restore)

    def restore(self):
        BV.TARGET, BV.RECORD = self.old

    def recorded(self):
        lines = self.record.read_text(encoding="utf-8").splitlines()
        return lines[0], {line.split("  ", 1)[1]: line.split("  ", 1)[0] for line in lines[1:]}

    def test_copy_takes_the_archive_and_the_engine_and_leaves_the_tests_behind(self):
        commit = make_clone(self.clone)
        rc, said = quiet(BV.copy, str(self.clone))
        self.assertEqual(rc, 0, said)
        self.assertIn("copied bordercall at %s" % commit[:7], said)
        present = sorted(p.relative_to(self.target).as_posix() for p in self.target.rglob("*") if p.is_file())
        self.assertEqual(present, [
            "HANDOFF.md", "README.md", "VENDORED",
            "bordercall/reference/table.csv", "bordercall/run.py",
            "morphometry/__init__.py", "morphometry/a.py",
            "requirements.txt",
            "scanimport/__init__.py", "scanimport/b.py",
            "screening/c.py", "screening/tables.json",
            "testdata/x"])
        first, digests = self.recorded()
        self.assertEqual(first, "bordercall %s OpenSpineConsortium/bordercall" % commit)
        self.assertEqual(sorted(digests), [p for p in present if p != "VENDORED"])
        self.assertEqual(digests["morphometry/a.py"], hashlib.sha256(b"A = 1\n").hexdigest())
        for rel in digests:
            self.assertEqual(digests[rel], BV.sha256(self.target / rel), rel)
        rc, said = quiet(BV.check)
        self.assertEqual(rc, 0, said)
        self.assertIn("matches its record", said)

    def test_check_fails_once_a_byte_of_the_copy_changes_or_a_file_is_added(self):
        make_clone(self.clone)
        quiet(BV.copy, str(self.clone))
        (self.target / "scanimport" / "b.py").write_text("B = 3\n", encoding="utf-8")
        rc, said = quiet(BV.check)
        self.assertEqual(rc, 1)
        self.assertIn("changed: scanimport/b.py", said)
        (self.target / "scanimport" / "b.py").write_text("B = 2\n", encoding="utf-8")
        (self.target / "screening" / "d.py").write_text("", encoding="utf-8")
        rc, said = quiet(BV.check)
        self.assertEqual(rc, 1)
        self.assertIn("unrecorded: screening/d.py", said)
        (self.target / "screening" / "d.py").unlink()
        (self.target / "testdata" / "x").unlink()
        rc, said = quiet(BV.check)
        self.assertEqual(rc, 1)
        self.assertIn("missing: testdata/x", said)

    def test_the_code_stamp_is_the_same_over_the_copy_as_over_the_clone(self):
        make_clone(self.clone)
        before = code_stamp(self.clone)
        quiet(BV.copy, str(self.clone))
        self.assertEqual(code_stamp(self.target), before)
        # the stamp reads only the two packages' top-level sources, so a test left behind changes nothing
        self.assertFalse((self.target / "morphometry" / "tests").exists())

    def test_a_clone_with_the_old_package_at_its_root_is_still_read(self):
        files = {rel.removeprefix("archive/"): text for rel, text in CLONE_FILES.items() if rel.startswith("archive/")}
        commit = make_clone(self.clone, files)
        rc, said = quiet(BV.copy, str(self.clone))
        self.assertEqual(rc, 0, said)
        self.assertTrue((self.target / "bordercall" / "run.py").exists())
        self.assertFalse((self.target / "morphometry").exists())
        self.assertEqual(self.recorded()[0], "bordercall %s OpenSpineConsortium/bordercall" % commit)

    def test_a_folder_that_is_no_clone_or_a_dirty_clone_is_refused(self):
        with self.assertRaises(SystemExit) as refused:
            BV.copy(str(self.clone))
        self.assertIn("not a bordercall clone", str(refused.exception))
        make_clone(self.clone)
        (self.clone / "morphometry" / "a.py").write_text("A = 2\n", encoding="utf-8")
        with self.assertRaises(SystemExit) as refused:
            BV.copy(str(self.clone))
        self.assertIn("uncommitted changes", str(refused.exception))
        self.assertFalse(self.target.exists())


if __name__ == "__main__":
    unittest.main()
