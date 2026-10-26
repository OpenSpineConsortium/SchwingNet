"""The pinned copy of bordercall under grid/bordercall/, and the check that it is the copy it says.

    python3 tools/bordercall_vendor.py copy <clone of OpenSpineConsortium/bordercall>
    python3 tools/bordercall_vendor.py check

Why a copy. The grid's job (grid/bordercall.sbatch) runs bordercall's own commands over the
SPINEPS corpus, and the gate's clone of this repository is the one tree a job can count on
being there and at a known commit; bordercall is a private repository of its own that the
grid has no token for. So the package, its reference tables and its selftest fixture are copied
here at one commit, grid/bordercall/VENDORED records that commit and the sha256 of every file,
and `check`, run by scripts/check.sh, fails when the copy drifts from the record, as
tools/VENDORED does for the protocol library. A change to bordercall is made in bordercall and
brought here by `copy`, never edited in the copy.
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
# what the job needs: the package, its reference tables and the selftest's fixture
KEEP = ("bordercall", "testdata", "README.md", "HANDOFF.md", "requirements.txt")
SKIP_DIRS = {"__pycache__", "figures", "out"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def files_under(root: Path):
    for p in sorted(root.rglob("*")):
        if p.is_file() and not (set(p.relative_to(root).parts[:-1]) & SKIP_DIRS) and p.name != "VENDORED":
            yield p


def copy(source: str) -> int:
    src = Path(source).resolve()
    if not (src / "bordercall" / "run.py").exists():
        raise SystemExit("%s is not a bordercall clone (no bordercall/run.py)" % src)
    commit = subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True,
                            text=True, check=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(src), "status", "--porcelain"], capture_output=True,
                           text=True, check=True).stdout.strip()
    if dirty:
        raise SystemExit("the clone has uncommitted changes; commit them first, so the record names them")
    if TARGET.exists():
        shutil.rmtree(TARGET)
    TARGET.mkdir(parents=True)
    for name in KEEP:
        s = src / name
        if s.is_dir():
            shutil.copytree(s, TARGET / name, ignore=shutil.ignore_patterns(*SKIP_DIRS))
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
