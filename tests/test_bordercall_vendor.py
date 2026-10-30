"""tools/bordercall_vendor.py on a made-up clone: the engine copy reads the old package from the
clone's archive/ and the engine's packages from its root, the search copy reads the auto-anatomist's
packages from the root with scanimport's phantom fixture, each leaves the tests behind but the holdings'
(grid/bordercall-complete.sbatch runs them first), records every file in its VENDORED, and check() holds both copies to their records; morphometry's code stamp, which
names every run on the grid, is the same over the engine copy as over the clone. The clone is a real
git repository in a temporary folder, since copy() reads its commit and refuses a dirty tree.
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
from dataclasses import replace
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

# the clone's layout since the engine replaced the old package: the archive, the engine's four
# packages (morphoview's lines among them, without its tests), the holdings package, whose tests ride along (they import one another, as
# test_fullspine_facts imports test_count_enhance_pet), and the search's two with their pins
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
    "morphoview/__init__.py": "",
    "morphoview/lines.py": "E = 5\n",
    "morphoview/tests/test_e.py": "assert True\n",
    "scanimport/__init__.py": "",
    "scanimport/b.py": "B = 2\n",
    "scanimport/tests/__init__.py": "",
    "scanimport/tests/phantom.py": "ARCH = 5.0\n",
    "scanimport/tests/test_b.py": "assert True\n",
    "screening/c.py": "C = 3\n",
    "screening/tables.json": "{}\n",
    "holdings/__init__.py": "",
    "holdings/fullspine_complete.py": "D = 4\n",
    "holdings/tests/__init__.py": "",
    "holdings/tests/test_d.py": "from holdings import fullspine_complete\n",
    "autoanatomist/__init__.py": "",
    "autoanatomist/phantom.py": "from scanimport.tests.phantom import ARCH\n",
    "autoanatomist/tests/t.py": "assert True\n",
    "schwingcheck/__init__.py": "",
    "schwingcheck/data/p.csv": "measure,level\n",
    "requirements-autoanatomist.txt": "jax==0.12.0.1\n",
}
ENGINE_COPY = ["HANDOFF.md", "README.md", "VENDORED",
               "bordercall/reference/table.csv", "bordercall/run.py",
               "holdings/__init__.py", "holdings/fullspine_complete.py",
               "holdings/tests/__init__.py", "holdings/tests/test_d.py",
               "morphometry/__init__.py", "morphometry/a.py",
               "morphoview/__init__.py", "morphoview/lines.py",
               "requirements.txt",
               "scanimport/__init__.py", "scanimport/b.py",
               "screening/c.py", "screening/tables.json",
               "testdata/x"]
SEARCH_COPY = ["VENDORED",
               "autoanatomist/__init__.py", "autoanatomist/phantom.py",
               "requirements-autoanatomist.txt",
               "scanimport/__init__.py", "scanimport/b.py", "scanimport/tests/__init__.py", "scanimport/tests/phantom.py",
               "schwingcheck/__init__.py", "schwingcheck/data/p.csv"]


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


def present_in(target: Path):
    return sorted(p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file())


class BordercallVendorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.clone = self.tmp / "clone"
        self.clone.mkdir()
        # the two copies under the test's own grid/, as the repository keeps them under its grid/
        self.old = BV.COPIES
        BV.COPIES = {name: replace(which, target=self.tmp / "grid" / which.target.name) for name, which in self.old.items()}
        self.addCleanup(self.restore)
        self.engine, self.search = BV.COPIES["engine"], BV.COPIES["search"]

    def restore(self):
        BV.COPIES = self.old

    def recorded(self, which):
        lines = which.record.read_text(encoding="utf-8").splitlines()
        return lines[0], {line.split("  ", 1)[1]: line.split("  ", 1)[0] for line in lines[1:]}

    def copy_both(self):
        commit = make_clone(self.clone)
        for name in ("engine", "search"):
            rc, said = quiet(BV.copy, str(self.clone), name)
            self.assertEqual(rc, 0, said)
        return commit

    def test_the_engine_copy_takes_the_archive_and_the_engine_and_leaves_the_tests_behind(self):
        commit = make_clone(self.clone)
        rc, said = quiet(BV.copy, str(self.clone))
        self.assertEqual(rc, 0, said)
        self.assertIn("copied bordercall at %s into" % commit[:7], said)
        self.assertEqual(present_in(self.engine.target), ENGINE_COPY)
        self.assertFalse(self.search.target.exists())
        first, digests = self.recorded(self.engine)
        self.assertEqual(first, "bordercall %s OpenSpineConsortium/bordercall" % commit)
        self.assertEqual(sorted(digests), [p for p in ENGINE_COPY if p != "VENDORED"])
        self.assertEqual(digests["morphometry/a.py"], hashlib.sha256(b"A = 1\n").hexdigest())
        for rel in digests:
            self.assertEqual(digests[rel], BV.sha256(self.engine.target / rel), rel)

    def test_the_search_copy_takes_the_auto_anatomist_with_scanimports_phantom_fixture_and_the_pins(self):
        commit = make_clone(self.clone)
        rc, said = quiet(BV.copy, str(self.clone), "search")
        self.assertEqual(rc, 0, said)
        self.assertEqual(present_in(self.search.target), SEARCH_COPY)
        self.assertFalse(self.engine.target.exists())
        first, digests = self.recorded(self.search)
        self.assertEqual(first, "bordercall %s OpenSpineConsortium/bordercall" % commit)
        self.assertEqual(sorted(digests), [p for p in SEARCH_COPY if p != "VENDORED"])
        # the fixture is held by the record as every other file is, and the other tests are not there
        self.assertEqual(digests["scanimport/tests/phantom.py"], hashlib.sha256(b"ARCH = 5.0\n").hexdigest())
        self.assertFalse((self.search.target / "scanimport" / "tests" / "test_b.py").exists())
        self.assertFalse((self.search.target / "autoanatomist" / "tests").exists())

    def test_check_holds_both_copies_and_fails_once_a_byte_of_either_changes_or_a_file_is_added(self):
        self.copy_both()
        rc, said = quiet(BV.check)
        self.assertEqual(rc, 0, said)
        self.assertIn("grid/bordercall matches its record", said)
        self.assertIn("grid/autoanatomist matches its record", said)
        (self.engine.target / "scanimport" / "b.py").write_text("B = 3\n", encoding="utf-8")
        rc, said = quiet(BV.check)
        self.assertEqual(rc, 1)
        self.assertIn("grid/bordercall differs from its record", said)
        self.assertIn("changed: scanimport/b.py", said)
        self.assertIn("grid/autoanatomist matches its record", said)
        (self.engine.target / "scanimport" / "b.py").write_text("B = 2\n", encoding="utf-8")
        (self.engine.target / "screening" / "d.py").write_text("", encoding="utf-8")
        rc, said = quiet(BV.check)
        self.assertEqual(rc, 1)
        self.assertIn("unrecorded: screening/d.py", said)
        (self.engine.target / "screening" / "d.py").unlink()
        (self.engine.target / "testdata" / "x").unlink()
        rc, said = quiet(BV.check)
        self.assertEqual(rc, 1)
        self.assertIn("missing: testdata/x", said)
        (self.engine.target / "testdata" / "x").write_text("fixture\n", encoding="utf-8")
        # the holdings' tests are part of the record, so a change there is caught as any other
        (self.engine.target / "holdings" / "tests" / "test_d.py").write_text("", encoding="utf-8")
        rc, said = quiet(BV.check)
        self.assertEqual(rc, 1)
        self.assertIn("changed: holdings/tests/test_d.py", said)
        (self.engine.target / "holdings" / "tests" / "test_d.py").write_text("from holdings import fullspine_complete\n", encoding="utf-8")
        # the fixture is held too: a change to it, or a test file added beside it, fails the search copy
        (self.search.target / "scanimport" / "tests" / "phantom.py").write_text("ARCH = 6.0\n", encoding="utf-8")
        rc, said = quiet(BV.check)
        self.assertEqual(rc, 1)
        self.assertIn("grid/autoanatomist differs from its record", said)
        self.assertIn("changed: scanimport/tests/phantom.py", said)
        (self.search.target / "scanimport" / "tests" / "phantom.py").write_text("ARCH = 5.0\n", encoding="utf-8")
        (self.search.target / "scanimport" / "tests" / "test_b.py").write_text("assert True\n", encoding="utf-8")
        rc, said = quiet(BV.check)
        self.assertEqual(rc, 0, said)  # a test left in a skipped folder is read by nobody, as the rule says
        shutil.rmtree(self.search.target)
        rc, said = quiet(BV.check)
        self.assertEqual(rc, 1)
        self.assertIn("copy <clone> search", said)

    def test_the_code_stamp_is_the_same_over_the_engine_copy_as_over_the_clone(self):
        make_clone(self.clone)
        before = code_stamp(self.clone)
        quiet(BV.copy, str(self.clone))
        self.assertEqual(code_stamp(self.engine.target), before)
        # the stamp reads only the two packages' top-level sources, so a test left behind changes nothing
        self.assertFalse((self.engine.target / "morphometry" / "tests").exists())

    def test_a_clone_with_the_old_package_at_its_root_is_still_read(self):
        files = {rel.removeprefix("archive/"): text for rel, text in CLONE_FILES.items() if rel.startswith("archive/")}
        commit = make_clone(self.clone, files)
        rc, said = quiet(BV.copy, str(self.clone))
        self.assertEqual(rc, 0, said)
        self.assertTrue((self.engine.target / "bordercall" / "run.py").exists())
        self.assertFalse((self.engine.target / "morphometry").exists())
        self.assertFalse((self.engine.target / "holdings").exists())
        self.assertEqual(self.recorded(self.engine)[0], "bordercall %s OpenSpineConsortium/bordercall" % commit)

    def test_a_clone_without_the_search_or_its_fixture_is_refused_for_the_search_copy(self):
        files = {rel: text for rel, text in CLONE_FILES.items() if not rel.startswith("autoanatomist/")}
        make_clone(self.clone, files)
        with self.assertRaises(SystemExit) as refused:
            BV.copy(str(self.clone), "search")
        self.assertIn("no autoanatomist", str(refused.exception))
        self.assertFalse(self.search.target.exists())
        shutil.rmtree(self.clone)
        self.clone.mkdir()
        files = {rel: text for rel, text in CLONE_FILES.items() if rel != "scanimport/tests/phantom.py"}
        make_clone(self.clone, files)
        with self.assertRaises(SystemExit) as refused:
            BV.copy(str(self.clone), "search")
        self.assertIn("does not track scanimport/tests/phantom.py", str(refused.exception))

    def test_a_folder_that_is_no_clone_or_a_dirty_clone_is_refused(self):
        with self.assertRaises(SystemExit) as refused:
            BV.copy(str(self.clone))
        self.assertIn("not a bordercall clone", str(refused.exception))
        make_clone(self.clone)
        (self.clone / "morphometry" / "a.py").write_text("A = 2\n", encoding="utf-8")
        for name in ("engine", "search"):
            with self.assertRaises(SystemExit) as refused:
                BV.copy(str(self.clone), name)
            self.assertIn("uncommitted changes", str(refused.exception))
        self.assertFalse(self.engine.target.exists())
        self.assertFalse(self.search.target.exists())

    def test_the_command_line_takes_copy_with_a_clone_and_a_name_and_check(self):
        make_clone(self.clone)
        rc, said = quiet(BV.main, ["copy", str(self.clone), "search"])
        self.assertEqual(rc, 0, said)
        rc, said = quiet(BV.main, ["copy", str(self.clone)])
        self.assertEqual(rc, 0, said)
        rc, said = quiet(BV.main, ["check"])
        self.assertEqual(rc, 0, said)
        for words in (["copy"], ["copy", str(self.clone), "other"], ["check", "x"], []):
            rc, said = quiet(BV.main, words)
            self.assertEqual(rc, 64, words)


if __name__ == "__main__":
    unittest.main()
