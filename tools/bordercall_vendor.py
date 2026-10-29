"""The pinned copies of bordercall under grid/, and the check that each is the copy it says.

    python3 tools/bordercall_vendor.py copy <clone of OpenSpineConsortium/bordercall> [engine|search]
    python3 tools/bordercall_vendor.py check

Why a copy. The grid's jobs (grid/bordercall.sbatch, grid/morphometry.sbatch, grid/autoanatomist-driver.sbatch)
run bordercall's own code over the masks and phantoms the grid holds, and the gate's clone of this
repository is the one tree a job can count on being there and at a known commit; bordercall is a
private repository of its own that the grid has no token for. So the parts the jobs need are copied
here at one commit, each copy's VENDORED records that commit and the sha256 of every file, and
`check`, run by scripts/check.sh, fails when a copy drifts from its record, as tools/VENDORED does
for the protocol library. A change to bordercall is made in bordercall and brought here by `copy`,
never edited in the copy.

Two copies, each pinned on its own, since the two jobs that read them move at different times:

- engine, grid/bordercall/, what grid/bordercall.sbatch and grid/morphometry.sbatch read. The old
  package, its reference tables, its selftest fixture and its notes live under the clone's archive/
  since the measuring engine replaced it, and come here as grid/bordercall/bordercall, testdata,
  README.md, HANDOFF.md and requirements.txt, the layout grid/bordercall.sbatch reads
  (BC=$REPO/grid/bordercall/bordercall); a clone from before that move, with bordercall/run.py at
  its root, is read the same way. The engine's packages at the clone's root, morphometry, scanimport
  and screening, come beside them as grid/bordercall/<name>, without their tests/ folders, so that a
  job's PYTHONPATH=$REPO/grid/bordercall imports each as the clone does; morphometry's code stamp,
  which names every run, hashes only the top-level .py files of morphometry and scanimport, so the
  copy stamps as the clone does. Its pin is the morphometry thread's (the owner's count of two CPU
  jobs over it), and a copy of the search never moves it. The gold tier 3 holdings package at the
  clone's root, holdings, comes the same way for grid/bordercall-complete.sbatch, with its tests/
  folder, since that job runs the matcher's own tests first and trusts nothing it reads where they
  fail.
- search, grid/autoanatomist/, what grid/autoanatomist-driver.sbatch reads through flows/autoanatomist.py:
  the auto-anatomist package, schwingcheck, whose chain and measures its naming layer imports, and
  scanimport, whose intensity levels, geometry and schemes it imports, with scanimport's phantom
  fixture (scanimport/tests/__init__.py and scanimport/tests/phantom.py), which autoanatomist.phantom
  imports as code and which the tests/ rule would otherwise leave behind, and
  requirements-autoanatomist.txt, the pins the search's environment is made from (grid/venv.sh). A
  job's PYTHONPATH=$REPO/grid/autoanatomist imports each as the clone does, and the copy carries its
  own scanimport so that the engine's copy is read by no search and the two pins stay apart.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
# what grid/bordercall.sbatch needs: the old package, its reference tables and the selftest's
# fixture, under the clone's archive/ (or at its root, before the move)
KEEP = ("bordercall", "testdata", "README.md", "HANDOFF.md", "requirements.txt")
# what grid/morphometry.sbatch needs: the measuring engine's packages at the clone's root
ENGINE = ("morphometry", "scanimport", "screening")
# what grid/bordercall-complete.sbatch needs: the gold tier 3 holdings at the clone's root, whose
# tests the job runs before the matcher (holdings.tests.test_fullspine_complete and
# test_fullspine_facts, which import the package's other tests), so its tests/ folder comes too
HOLDINGS = ("holdings",)
# what flows/autoanatomist.py needs: the search's packages at the clone's root, and its pins
SEARCH = ("autoanatomist", "schwingcheck", "scanimport", "requirements-autoanatomist.txt")
# the fixture files autoanatomist.phantom imports as code, copied although they lie under tests/
SEARCH_FIXTURES = ("scanimport/tests/__init__.py", "scanimport/tests/phantom.py")
# a package's tests never run on the grid (but the holdings', above), a cache or an output folder
# is nobody's record, and the old package's reference papers and the renders its tables were read
# from are not its code
SKIP_DIRS = {"__pycache__", "figures", "out", "tests", "papers", "provenance"}


@dataclass(frozen=True)
class Copy:
    """One pinned copy: its name on the command line, where it lies, what it takes from the clone's
    archive/ and from the clone's root, the files it takes although a skipped folder holds them, the
    root names whose tests/ folder comes too, and whether a clone without one of its root names is
    refused (a clone from before the engine has none of the engine's packages and is still read; a
    search copy without its packages is nothing)."""
    name: str
    target: Path
    archive: tuple
    root: tuple
    fixtures: tuple = ()
    tests_kept: tuple = ()
    required: bool = False

    def skipped_dirs(self, folder: str) -> set:
        """The folder names left out of the copy of the clone's folder called folder."""
        return SKIP_DIRS - {"tests"} if folder in self.tests_kept else SKIP_DIRS

    @property
    def record(self) -> Path:
        return self.target / "VENDORED"

    @property
    def shown(self) -> str:
        return self.target.relative_to(HERE).as_posix() if self.target.is_relative_to(HERE) else str(self.target)


COPIES = {
    "engine": Copy("engine", HERE / "grid" / "bordercall", KEEP, ENGINE + HOLDINGS, tests_kept=HOLDINGS),
    "search": Copy("search", HERE / "grid" / "autoanatomist", (), SEARCH, SEARCH_FIXTURES, required=True),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def files_under(root: Path, which: Copy):
    """The copy's files under root: every file outside a skipped folder, the fixtures the copy
    names although a skipped folder holds them, and the tests of a folder whose tests are kept."""
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.name == "VENDORED":
            continue
        rel = p.relative_to(root)
        if rel.as_posix() in which.fixtures or not (set(rel.parts[:-1]) & which.skipped_dirs(rel.parts[0])):
            yield p


def archive_of(src: Path) -> Path:
    """Where the old package sits in the clone: archive/ since the engine replaced it, the root before."""
    for folder in (src / "archive", src):
        if (folder / "bordercall" / "run.py").exists():
            return folder
    raise SystemExit("%s is not a bordercall clone (no archive/bordercall/run.py, nor bordercall/run.py)" % src)


def tracked_files(src: Path) -> set:
    """What the clone's git tracks, so a paper or a render left in the working tree never rides along."""
    out = subprocess.run(["git", "-C", str(src), "ls-files", "-z"], capture_output=True, text=True, check=True).stdout
    return {name for name in out.split("\0") if name}


def drop_untracked(copied: Path, origin: Path, src: Path, tracked: set) -> None:
    """Remove from the copy every file the clone's git does not track, and the folders left empty."""
    for p in sorted(copied.rglob("*"), reverse=True):
        if p.is_file() and (origin / p.relative_to(copied)).relative_to(src).as_posix() not in tracked:
            p.unlink()
        elif p.is_dir() and not any(p.iterdir()):
            p.rmdir()


def copy_fixtures(which: Copy, src: Path, tracked: set) -> None:
    """The files a skipped folder holds that the copy needs as code, each tracked by the clone."""
    for rel in which.fixtures:
        if rel not in tracked:
            raise SystemExit("the clone does not track %s, which the %s copy imports" % (rel, which.name))
        (which.target / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src / rel, which.target / rel)


def copy(source: str, name: str = "engine") -> int:
    which = COPIES[name]
    src = Path(source).resolve()
    archive = archive_of(src)
    commit = subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True,
                            text=True, check=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(src), "status", "--porcelain"], capture_output=True,
                           text=True, check=True).stdout.strip()
    if dirty:
        raise SystemExit("the clone has uncommitted changes; commit them first, so the record names them")
    tracked = tracked_files(src)
    missing = [n for n in which.root if not (src / n).exists()] if which.required else []
    if missing:
        raise SystemExit("the clone has no %s, which the %s copy takes" % (", ".join(missing), which.name))
    if which.target.exists():
        shutil.rmtree(which.target)
    which.target.mkdir(parents=True)
    for folder, names in ((archive, which.archive), (src, which.root)):
        for n in names:
            s = folder / n
            if s.is_dir():
                shutil.copytree(s, which.target / n, ignore=shutil.ignore_patterns(*which.skipped_dirs(n)))
                drop_untracked(which.target / n, s, src, tracked)
            elif s.exists():
                shutil.copy2(s, which.target / n)
    copy_fixtures(which, src, tracked)
    lines = ["bordercall %s OpenSpineConsortium/bordercall" % commit]
    for p in files_under(which.target, which):
        lines.append("%s  %s" % (sha256(p), p.relative_to(which.target).as_posix()))
    which.record.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("copied bordercall at %s into %s: %d files recorded in %s" % (commit[:7], which.shown, len(lines) - 1, which.record))
    return 0


def check_one(which: Copy) -> int:
    if not which.record.exists():
        print("no %s: the grid job has no bordercall to run (tools/bordercall_vendor.py copy <clone> %s)" % (which.record, which.name))
        return 1
    lines = which.record.read_text(encoding="utf-8").splitlines()
    recorded = {}
    for line in lines[1:]:
        digest, _, rel = line.partition("  ")
        recorded[rel] = digest
    present = {p.relative_to(which.target).as_posix(): sha256(p) for p in files_under(which.target, which)}
    bad = []
    for rel, digest in recorded.items():
        if rel not in present:
            bad.append("missing: %s" % rel)
        elif present[rel] != digest:
            bad.append("changed: %s" % rel)
    for rel in present:
        if rel not in recorded:
            bad.append("unrecorded: %s" % rel)
    if bad:
        print("%s differs from its record (edit bordercall itself, then copy again):" % which.shown)
        for b in bad:
            print("  " + b)
        return 1
    print("%s matches its record: %s" % (which.shown, lines[0]))
    return 0


def check() -> int:
    """Every copy held to its record; one that differs fails the check, and the rest are still said."""
    return max(check_one(which) for which in COPIES.values())


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["copy"] and len(argv) in (2, 3) and (len(argv) == 2 or argv[2] in COPIES):
        return copy(argv[1], argv[2] if len(argv) == 3 else "engine")
    if argv == ["check"]:
        return check()
    print(__doc__)
    return 64


if __name__ == "__main__":
    sys.exit(main())
