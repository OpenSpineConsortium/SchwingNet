"""Unpack a fetched set's download zips beside themselves, as the fetch itself would have.

The owner's word of 2026-10-23 (the Dataset finalization thread): RSPECT came down from Kaggle as
one 534 GB zip that the fetch never unpacked, so the set on the grid is the zip alone, and the
owner chose to unpack it once the lab volume's room could be read, then drop the zip with the gate
word dropzip. The gate word `unpack <id>` runs this as one job (grid/unpack.sbatch), under the
size rule (grid/size-rule.sh): the job first asks `size`, which reads every zip's central
directory and gives what the unpacked files will take, and starts only when the rule admits it.

    python3 tools/unpack.py size --raw <dest>
    python3 tools/unpack.py unpack --id <id> --raw <dest> --out <report.md>

Each member lands where tools/fetch_sources.py's unpack_archives puts it, at the archive's folder
joined with its name, so tools/dropzip.py finds it there afterwards. A member already there at its
full size is left, so a job cut short and sent again goes on where it stopped; a member whose name
leads outside the raw folder is never written. Each file is written under a .part name and renamed
once whole, so a file cut short by a job's end is never taken for an unpacked one. Only counts and
sizes leave the grid; no member is named.

The standard library alone, run by the python the gate names as PYDRV, on a compute node.
"""

import argparse
import shutil
import sys
import zipfile
from pathlib import Path

from dropzip import twin_of, unpacked

CHUNK = 16 * 1024 * 1024


def archives_under(raw):
    """Every zip under the raw folder, in a fixed order."""
    return sorted(path for path in raw.rglob("*") if path.suffix.lower() == ".zip" and path.is_file())


def members(archive):
    """The files of one zip, directories left out."""
    with zipfile.ZipFile(archive) as opened:
        return [info for info in opened.infolist() if not info.is_dir()]


def still_to_land(raw):
    """What every zip's files take unpacked, and the part of it not yet beside its zip."""
    total = need = 0
    for archive in archives_under(raw):
        for info in members(archive):
            total += info.file_size
            if not unpacked(twin_of(raw, archive, info.filename), info.file_size):
                need += info.file_size
    return total, need


def land(opened, info, twin):
    """Write one member to its twin through a .part file, renamed only once whole."""
    twin.parent.mkdir(parents=True, exist_ok=True)
    partial = twin.with_name(twin.name + ".part")
    with opened.open(info) as source, open(partial, "wb") as sink:
        shutil.copyfileobj(source, sink, CHUNK)
    partial.replace(twin)


def unpack_one(raw, archive):
    """Unpack one zip; its report line and the bytes it wrote."""
    name = archive.relative_to(raw)
    written = present = refused = files = 0
    try:
        with zipfile.ZipFile(archive) as opened:
            for info in opened.infolist():
                if info.is_dir():
                    continue
                files += 1
                twin = twin_of(raw, archive, info.filename)
                if twin is None:
                    refused += 1
                elif unpacked(twin, info.file_size):
                    present += 1
                else:
                    land(opened, info, twin)
                    written += info.file_size
    except (zipfile.BadZipFile, OSError) as error:
        return f"  {name}: stopped: {type(error).__name__} after {written / 1e9:,.1f} GB written", written
    line = (f"  {name}: {files:,} files; {files - present - refused:,} written ({written / 1e9:,.1f} GB), "
            f"{present:,} already there, {refused:,} named outside the raw folder and left")
    return line, written


def report(set_id, raw):
    """The report's lines, unpacking every zip under the raw folder."""
    archives = archives_under(raw)
    lines, written = [f"# unpack {set_id}", f"  zips: {len(archives)}"], 0
    for archive in archives:
        line, size = unpack_one(raw, archive)
        lines.append(line)
        written += size
    total, need = still_to_land(raw)
    lines += [f"  written: {written / 1e9:,.1f} GB",
              f"  still to land: {need / 1e9:,.1f} GB of {total / 1e9:,.1f} GB"]
    return lines


def parsed(argv):
    """The two modes and their arguments."""
    top = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = top.add_subparsers(dest="mode", required=True)
    size = sub.add_parser("size", help="what the unpacked files take, for the size rule")
    size.add_argument("--raw", required=True)
    run = sub.add_parser("unpack", help="unpack every zip and write the report")
    run.add_argument("--id", required=True)
    run.add_argument("--raw", required=True)
    run.add_argument("--out", required=True)
    return top.parse_args(argv)


def main(argv=None):
    """Size or unpack one set's zips."""
    args = parsed(argv)
    raw = Path(args.raw).resolve()
    if not raw.is_dir():
        print(f"unpack: no folder {args.raw}")
        return 2
    if args.mode == "size":
        try:
            total, need = still_to_land(raw)
        except (zipfile.BadZipFile, OSError) as error:
            print(f"a zip could not be read ({type(error).__name__})")
            return 1
        # The line grid/size-rule.sh's size_and_admit reads: total, need, how.
        print(f"{total} {need} the zips central directories")
        return 0
    lines = report(args.id, raw)
    out = Path(args.out)
    partial = out.with_name(out.name + ".part")
    partial.write_text("\n".join(lines) + "\n", encoding="ascii", errors="replace")
    partial.replace(out)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
