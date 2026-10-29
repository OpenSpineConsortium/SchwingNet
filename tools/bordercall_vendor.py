"""The pinned copy of bordercall under grid/bordercall/, and the check that it is the copy it says.

    python3 tools/bordercall_vendor.py copy <clone of OpenSpineConsortium/bordercall>
    python3 tools/bordercall_vendor.py check

Why a copy. The grid's jobs (grid/bordercall.sbatch, grid/morphometry.sbatch) run bordercall's
own commands over the masks the grid holds, and the gate's clone of this repository is the one
tree a job can count on being there and at a known commit; bordercall is a private repository
of its own that the grid has no token for. So the parts the jobs need are copied here at one
commit, grid/bordercall/VENDORED records that commit and the sha256 of every file, and `check`,
run by scripts/check.sh, fails when the copy drifts from the record, as tools/VENDORED does for
the protocol library. A change to bordercall is made in bordercall and brought here by `copy`,
never edited in the copy.

What is copied, from a clone whose root is given. The old package, its reference tables, its
selftest fixture and its notes live under the clone's archive/ since the measuring engine
replaced it, and come here as grid/bordercall/bordercall, testdata, README.md, HANDOFF.md and
requirements.txt, the layout grid/bordercall.sbatch reads (BC=$REPO/grid/bordercall/bordercall);
a clone from before that move, with bordercall/run.py at its root, is read the same way. The
engine's packages at the clone's root, morphometry, scanimport and screening, come beside them
as grid/bordercall/<name>, without their tests/ folders, so that a job's
PYTHONPATH=$REPO/grid/bordercall imports each as the clone does; morphometry's code stamp, which
names every run, hashes only the top-level .py files of morphometry and scanimport, so the copy
stamps as the clone does. The gold tier 3 holdings package at the clone's root, holdings, comes
the same way for grid/bordercall-complete.sbatch, with its tests/ folder, since that job runs the
matcher's own tests first and trusts nothing it reads where they fail.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
TARGET = HERE / "grid" / "bordercall"
RECORD = TARGET / "VENDORED"
# what grid/bordercall.sbatch needs: the old package, its reference tables and the selftest's
# fixture, under the clone's archive/ (or at its root, before the move)
KEEP = ("bordercall", "testdata", "README.md", "HANDOFF.md", "requirements.txt")
# what grid/morphometry.sbatch needs: the measuring engine's packages at the clone's root
ENGINE = ("morphometry", "scanimport", "screening")
# what grid/bordercall-complete.sbatch needs: the gold tier 3 holdings at the clone's root, whose
# tests the job runs before the matcher (holdings.tests.test_fullspine_complete and
# test_fullspine_facts, which import the package's other tests), so its tests/ folder comes too
HOLDINGS = ("holdings",)
# a package's tests never run on the grid (but the holdings', above), a cache or an output folder
# is nobody's record, and the old package's reference papers and the renders its tables were read
# from are not its code
SKIP_DIRS = {"__pycache__", "figures", "out", "tests", "papers", "provenance"}
TESTS_KEPT = set(HOLDINGS)


def skipped_dirs(name: str) -> set:
    """The folder names left out of the copy of the clone's folder called name."""
    return SKIP_DIRS - {"tests"} if name in TESTS_KEPT else SKIP_DIRS


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def files_under(root: Path):
    for p in sorted(root.rglob("*")):
        parts = p.relative_to(root).parts
        if p.is_file() and not (set(parts[:-1]) & skipped_dirs(parts[0])) and p.name != "VENDORED":
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


def copy(source: str) -> int:
    src = Path(source).resolve()
    archive = archive_of(src)
    commit = subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True,
                            text=True, check=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(src), "status", "--porcelain"], capture_output=True,
                           text=True, check=True).stdout.strip()
    if dirty:
        raise SystemExit("the clone has uncommitted changes; commit them first, so the record names them")
    if TARGET.exists():
        shutil.rmtree(TARGET)
    TARGET.mkdir(parents=True)
    tracked = tracked_files(src)
    for folder, names in ((archive, KEEP), (src, ENGINE), (src, HOLDINGS)):
        for name in names:
            s = folder / name
            if s.is_dir():
                shutil.copytree(s, TARGET / name, ignore=shutil.ignore_patterns(*skipped_dirs(name)))
                drop_untracked(TARGET / name, s, src, tracked)
            elif s.exists():
                shutil.copy2(s, TARGET / name)
    lines = ["bordercall %s OpenSpineConsortium/bordercall" % commit]
    for p in files_under(TARGET):
        lines.append("%s  %s" % (sha256(p), p.relative_to(TARGET).as_posix()))
    RECORD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("copied bordercall at %s: %d files recorded in %s" % (commit[:7], len(lines) - 1, RECORD))
    return 0


def check() -> int:
    if not RECORD.exists():
        print("no %s: the grid job has no bordercall to run (tools/bordercall_vendor.py copy)" % RECORD)
        return 1
    lines = RECORD.read_text(encoding="utf-8").splitlines()
    recorded = {}
    for line in lines[1:]:
        digest, _, rel = line.partition("  ")
        recorded[rel] = digest
    present = {p.relative_to(TARGET).as_posix(): sha256(p) for p in files_under(TARGET)}
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
        print("grid/bordercall differs from its record (edit bordercall itself, then copy again):")
        for b in bad:
            print("  " + b)
        return 1
    print("grid/bordercall matches its record: %s" % lines[0])
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["copy"] and len(argv) == 2:
        return copy(argv[1])
    if argv == ["check"]:
        return check()
    print(__doc__)
    return 64


if __name__ == "__main__":
    sys.exit(main())
