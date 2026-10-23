"""Delete a fetched set's download archives once every file in them sits unpacked beside them.

The owner's word of 2026-10-23 (the Dataset finalization thread): RSPECT's Kaggle download, a zip
of 534 GB, stayed beside the 1,937,450 files the fetch unpacked from it (tools/fetch_sources.py,
unpack_archives, writes each member at the archive's folder joined with its name), and the owner
said to delete it, from GitHub Actions rather than the grid's shell. The gate word `dropzip <id>`
runs this as one job (grid/dropzip.sbatch) and prints the report on the next send.

    python3 tools/dropzip.py --id <id> --raw <dest> --out <report.md>

Every .zip under the raw folder is read, never unpacked: a zip is deleted only when it holds at
least one file and every file in it has its twin beside the archive, a regular file of the same
size, inside the raw folder. A zip with one member missing, short, or named outside the folder
is kept, and the report says how many and gives the first few, so nothing is ever deleted that
the disk does not also hold. A zip that cannot be read is kept too. Only counts, sizes and the
set's own member names leave the grid; no folder of the volume is named.

The standard library alone, run by the python the gate names as PYDRV, on a compute node, since
the login node, where the gate runs, kills python by name.
"""

import argparse
import sys
import zipfile
from pathlib import Path

SHOWN = 5


def twin_of(raw, archive, name):
    """Where the fetch unpacked one member, or None when its name leads outside the raw folder."""
    twin = (archive.parent / name).resolve()
    return twin if twin.is_relative_to(raw) else None


def unpacked(twin, size):
    """Whether the member's twin is a regular file of the member's size."""
    return twin is not None and twin.is_file() and not twin.is_symlink() and twin.stat().st_size == size


def missing_members(raw, archive):
    """The member names of one zip whose twin is not on disk, and how many files it holds."""
    missing, files = [], 0
    with zipfile.ZipFile(archive) as opened:
        for info in opened.infolist():
            if info.is_dir():
                continue
            files += 1
            if not unpacked(twin_of(raw, archive, info.filename), info.file_size):
                missing.append(info.filename)
    return missing, files


def settle(raw, archive):
    """Delete one zip if the disk holds all of it; the report's lines for it either way."""
    name, size = archive.relative_to(raw), archive.stat().st_size
    try:
        missing, files = missing_members(raw, archive)
    except (zipfile.BadZipFile, OSError) as error:
        return [f"  {name}: kept, {size / 1e9:,.1f} GB: it could not be read ({type(error).__name__})"], 0
    if files == 0:
        return [f"  {name}: kept, {size / 1e9:,.1f} GB: it holds no file"], 0
    if missing:
        lines = [f"  {name}: kept, {size / 1e9:,.1f} GB: {len(missing):,} of {files:,} files are not unpacked beside it"]
        return lines + [f"    not on disk: {member}" for member in missing[:SHOWN]], 0
    archive.unlink()
    return [f"  {name}: deleted, {size / 1e9:,.1f} GB: all {files:,} files are unpacked beside it"], size


def report(set_id, raw):
    """The report's lines for every zip under the raw folder, deleting those the disk holds."""
    archives = sorted(path for path in raw.rglob("*") if path.suffix.lower() == ".zip" and path.is_file())
    lines, freed = [f"# dropzip {set_id}", f"  zips: {len(archives)}"], 0
    for archive in archives:
        said, size = settle(raw, archive)
        lines += said
        freed += size
    lines.append(f"  freed: {freed / 1e9:,.1f} GB")
    return lines


def main(argv=None):
    """Settle every zip of one set and write the report atomically."""
    top = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    top.add_argument("--id", required=True, help="the set's id, for the report's title")
    top.add_argument("--raw", required=True, help="the set's raw folder")
    top.add_argument("--out", required=True, help="the report, Markdown")
    args = top.parse_args(argv)
    raw = Path(args.raw).resolve()
    if not raw.is_dir():
        print(f"dropzip: no folder {args.raw}")
        return 2
    lines = report(args.id, raw)
    out = Path(args.out)
    partial = out.with_name(out.name + ".part")
    partial.write_text("\n".join(lines) + "\n", encoding="ascii", errors="replace")
    partial.replace(out)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
