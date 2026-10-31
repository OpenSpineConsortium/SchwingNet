"""Arrange Radiopaedia images saved by hand into the raw copies the bank recipes read.

Radiopaedia's licence to the owner (agreement 202610-9517, countersigned 2026-10-23) covers the
Spine cases, but the site refuses scripted requests and supplies no export, so the images are
saved by hand from the case pages, as clause 3 of the agreement contemplates. This tool takes what
was saved and lays it out for grid/banks/radiopaedia_fluoro.json and radiopaedia_xr.json:

    <from>/<group>/<rID or rID-slug>/<any name>.jpg     what the owner saved, group fluoro or xr
    <to>/radiopaedia_<group>/raw/<rID>/<sha256[:16]>.jpg  what the recipes read, one case one person

Every image is named by its bytes, so the same image saved twice in a case is kept once and
reported, and the same image under two cases is refused, since which case it belongs to is not
the tool's to decide. A file that is not a JPEG, a folder whose name does not start with an rID
and a group other than fluoro or xr are refused by name, and nothing is written until the whole
set has been read. `<to>/CASES.csv` lists each case with its group, frame count and page, and
`<to>/SHA256SUMS` every file, so the folder can be carried to the grid (grid/carry/README.md);
the near-duplicate check against the corpora already held is the leak check after ingest
(grid/run-leaks.sh with NEW=<source>/<shard>), which runs before any frame enters a test split.

    python3 tools/radiopaedia_import.py plan --from <saved> --to <out>
    python3 tools/radiopaedia_import.py run --from <saved> --to <out>

Standard library only.
"""

import argparse
import csv
import hashlib
import io
import re
import sys
from pathlib import Path

GROUPS = ("fluoro", "xr")
SUFFIXES = (".jpg", ".jpeg")
JPEG_START = b"\xff\xd8\xff"
CASE_FOLDER = re.compile(r"^(?:rID[-_ ]?)?([1-9][0-9]{0,8})(?:[-_ ].*)?$", re.IGNORECASE)
CASE_PAGE = "https://radiopaedia.org/cases/{rid}"


class ImportError_(Exception):
    """A saved set that cannot be arranged as it stands."""


def case_of(folder_name):
    match = CASE_FOLDER.match(folder_name)
    if not match:
        raise ImportError_(f"{folder_name}: a case folder must start with its rID, as 24796 or 24796-slug")
    return match.group(1)


def saved_images(source):
    """Every saved file as (group, rID, path), in path order."""
    found = []
    for group_dir in sorted(p for p in source.iterdir() if p.is_dir()):
        if group_dir.name not in GROUPS:
            raise ImportError_(f"{group_dir.name}: the group is none of {', '.join(GROUPS)}")
        for case_dir in sorted(p for p in group_dir.iterdir() if p.is_dir()):
            rid = case_of(case_dir.name)
            for path in sorted(p for p in case_dir.rglob("*") if p.is_file()):
                found.append((group_dir.name, rid, path))
    if not found:
        raise ImportError_(f"{source}: no saved image under <group>/<rID>/")
    return found


def read_jpeg(path):
    if path.suffix.lower() not in SUFFIXES:
        raise ImportError_(f"{path}: not a .jpg; save the image as Radiopaedia serves it")
    data = path.read_bytes()
    if not data.startswith(JPEG_START):
        raise ImportError_(f"{path}: the bytes are not a JPEG")
    return data


def arrange(source):
    """The plan: kept frames by (group, rID, digest), the duplicates, and the cases."""
    owner, kept, duplicates = {}, {}, []
    for group, rid, path in saved_images(source):
        data = read_jpeg(path)
        digest = hashlib.sha256(data).hexdigest()
        if digest in owner and owner[digest] != (group, rid):
            first = owner[digest]
            raise ImportError_(f"{path}: the same image is saved under {first[0]}/{first[1]} too")
        if digest in owner:
            duplicates.append(str(path.relative_to(source)))
            continue
        owner[digest] = (group, rid)
        kept[(group, rid, digest)] = data
    return kept, duplicates


def case_rows(kept):
    counts = {}
    for group, rid, _ in kept:
        counts[(group, rid)] = counts.get((group, rid), 0) + 1
    clash = {rid for (group, rid) in counts if (GROUPS[0], rid) in counts and (GROUPS[1], rid) in counts}
    if clash:
        raise ImportError_(f"rID {min(clash, key=int)} is under both groups; one case is one group")
    return [{"rid": rid, "group": group, "frames": n, "page": CASE_PAGE.format(rid=rid)}
            for (group, rid), n in sorted(counts.items(), key=lambda item: (item[0][0], int(item[0][1])))]


def target_of(group, rid, digest):
    return Path(f"radiopaedia_{group}") / "raw" / rid / f"{digest[:16]}.jpg"


def cases_csv(rows):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=["rid", "group", "frames", "page"], lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode()


def write_once(path, data):
    if path.exists():
        if path.read_bytes() != data:
            raise ImportError_(f"{path}: already there with other bytes")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    part.write_bytes(data)
    part.replace(path)


def write_all(target, kept, rows):
    files = {target_of(g, r, d): data for (g, r, d), data in kept.items()}
    files[Path("CASES.csv")] = cases_csv(rows)
    for relative, data in sorted(files.items()):
        write_once(target / relative, data)
    sums = "".join(f"{hashlib.sha256(data).hexdigest()}  {relative.as_posix()}\n"
                   for relative, data in sorted(files.items(), key=lambda item: item[0].as_posix()))
    write_once(target / "SHA256SUMS", sums.encode())


def summary(kept, duplicates, rows):
    by_group = {group: sum(1 for (g, _, _) in kept if g == group) for group in GROUPS}
    lines = [f"{group}: {sum(1 for row in rows if row['group'] == group)} cases, {by_group[group]} frames"
             for group in GROUPS]
    lines.append(f"duplicates dropped: {len(duplicates)}")
    lines.extend(f"  {name}" for name in duplicates)
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("action", choices=("plan", "run"))
    parser.add_argument("--from", dest="source", required=True, type=Path)
    parser.add_argument("--to", dest="target", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        kept, duplicates = arrange(args.source)
        rows = case_rows(kept)
        if args.action == "run":
            write_all(args.target, kept, rows)
    except (ImportError_, OSError) as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    print(summary(kept, duplicates, rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
