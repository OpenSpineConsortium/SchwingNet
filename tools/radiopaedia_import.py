"""Arrange Radiopaedia images saved by hand into the raw copies the bank recipes read.

Radiopaedia's licence to the owner (agreement 202610-9517, countersigned 2026-10-23) covers the
Spine cases, but the site refuses scripted requests and supplies no export, so the images are
saved by hand from the case pages, as clause 3 of the agreement contemplates. This tool takes what
was saved and lays it out for grid/banks/radiopaedia_fluoro.json and radiopaedia_xr.json:

    <from>/<group>/<rID or rID-slug>/<any name>.jpg     what the owner saved, group fluoro or xr
    <to>/radiopaedia_<group>/raw/<rID>/<sha256[:16]>.jpg  what the recipes read, one case one person

A case can be saved as a CT too, the third group, whose images are the slices of a stack and so
carry an order the other groups do not. Each slice is named by its one number, as the case
viewer shows it (12.jpg or slice-012.jpg); a case's slices sit straight in its folder, one
series, or in one folder per series (axial, sagittal), and are laid out by their number:

    <from>/ct/<rID>/[<series>/]<n>.jpg
    <to>/radiopaedia_ct/raw/<rID>/<series or stack>/<n, four digits>-<sha256[:16]>.jpg

A case saved as a CT and as an X-ray (xr or fluoro) is a paired case: one person seen both
ways, so the CT can say which levels and which transitional anatomy the X-ray shows.
`<to>/PAIRS.csv` lists every such case with its counts. No recipe banks the ct group: the
banks hold 2-D frames, and the CT side of the project reads volumes with a voxel spacing,
which a stack of JPEGs does not carry (docs/research/radiopaedia-paired.md).

Every image is named by its bytes, so the same image saved twice in a case is kept once and
reported, and the same image under two cases is refused, since which case it belongs to is not
the tool's to decide; in a CT stack the same slice under two numbers is refused too, since one
of the two numbers is wrong. A file that is not a JPEG, a folder whose name does not start with
an rID, a group other than ct, fluoro or xr, a slice name with no number or more than one, and
two slices of one number are refused by name, and nothing is written until the whole set has
been read. `<to>/CASES.csv` lists each case with its group, frame count and page, and
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
from collections import namedtuple
from pathlib import Path

CT = "ct"
XRAY_GROUPS = ("fluoro", "xr")
GROUPS = (CT, *XRAY_GROUPS)
SUFFIXES = (".jpg", ".jpeg")
JPEG_START = b"\xff\xd8\xff"
CASE_FOLDER = re.compile(r"^(?:rID[-_ ]?)?([1-9][0-9]{0,8})(?:[-_ ].*)?$", re.IGNORECASE)
SERIES_FOLDER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")
LOOSE_SERIES = "stack"
SLICE_MAX = 9999
CASE_PAGE = "https://radiopaedia.org/cases/{rid}"
CASE_FIELDS = ["rid", "group", "frames", "page"]
PAIR_FIELDS = ["rid", "ct_series", "ct_slices", "xray_group", "xray_frames", "page"]

# One saved image: its group and case, and for a CT slice its series and number (empty and None
# for the X-ray groups, whose images carry no order), with the path it was saved at.
Saved = namedtuple("Saved", "group rid series number path")
# One kept image, by what places it and the sha256 of its bytes.
Frame = namedtuple("Frame", "group rid series number digest")


class ImportError_(Exception):
    """A saved set that cannot be arranged as it stands."""


def case_of(folder_name):
    match = CASE_FOLDER.match(folder_name)
    if not match:
        raise ImportError_(f"{folder_name}: a case folder must start with its rID, as 24796 or 24796-slug")
    return match.group(1)


def require_jpeg_name(path):
    if path.suffix.lower() not in SUFFIXES:
        raise ImportError_(f"{path}: not a .jpg; save the image as Radiopaedia serves it")


def slice_number(path):
    """The slice's place in its stack, the one number its name holds."""
    require_jpeg_name(path)
    runs = re.findall(r"[0-9]+", path.stem)
    if len(runs) != 1:
        held = "no number" if not runs else f"{len(runs)} numbers"
        raise ImportError_(f"{path}: a CT slice is named by its one number, as 12.jpg; this name holds {held}")
    number = int(runs[0])
    if number > SLICE_MAX:
        raise ImportError_(f"{path}: {number} is no slice number; a stack saved by hand ends below {SLICE_MAX + 1}")
    return number


def series_folders(case_dir):
    """A CT case's slices by series: loose slices are one series, else one folder per series."""
    entries = sorted(case_dir.iterdir())
    loose = [p for p in entries if p.is_file()]
    folders = [p for p in entries if p.is_dir()]
    if loose and folders:
        raise ImportError_(f"{case_dir}: slices both loose and in series folders; put every slice in a series folder")
    if loose:
        return [(LOOSE_SERIES, loose)]
    found = []
    for folder in folders:
        if not SERIES_FOLDER.match(folder.name):
            raise ImportError_(f"{folder}: a series folder is named in letters, digits, - and _, as axial or sagittal-t2")
        inner = sorted(folder.iterdir())
        deeper = [p for p in inner if p.is_dir()]
        if deeper:
            raise ImportError_(f"{deeper[0]}: a series folder holds slices only")
        found.append((folder.name, inner))
    return found


def case_images(group, rid, case_dir):
    if group != CT:
        return [Saved(group, rid, "", None, p) for p in sorted(p for p in case_dir.rglob("*") if p.is_file())]
    return [Saved(group, rid, series, slice_number(p), p)
            for series, paths in series_folders(case_dir) for p in paths]


def saved_images(source):
    """Every saved image as a Saved record, in path order."""
    found = []
    for group_dir in sorted(p for p in source.iterdir() if p.is_dir()):
        if group_dir.name not in GROUPS:
            raise ImportError_(f"{group_dir.name}: the group is none of {', '.join(GROUPS)}")
        for case_dir in sorted(p for p in group_dir.iterdir() if p.is_dir()):
            found.extend(case_images(group_dir.name, case_of(case_dir.name), case_dir))
    if not found:
        raise ImportError_(f"{source}: no saved image under <group>/<rID>/")
    return found


def read_jpeg(path):
    require_jpeg_name(path)
    data = path.read_bytes()
    if not data.startswith(JPEG_START):
        raise ImportError_(f"{path}: the bytes are not a JPEG")
    return data


def refuse_unless_repeat(item, first, first_path):
    """An image kept already may come again only as a second save in the same place."""
    if (first.group, first.rid) != (item.group, item.rid):
        raise ImportError_(f"{item.path}: the same image is saved under {first.group}/{first.rid} too")
    if (first.series, first.number) != (item.series, item.number):
        raise ImportError_(f"{item.path}: the same slice is saved as {first_path.name} in {first.series} too; "
                           "one of its two numbers is wrong")


def claim_slot(slots, item):
    """A CT slice takes its number in its series, which no other slice may hold."""
    slot = (item.rid, item.series, item.number)
    if slot in slots:
        raise ImportError_(f"{item.path}: slice {item.number} of {CT}/{item.rid}/{item.series} "
                           f"is {slots[slot].name} too; two slices cannot share a number")
    slots[slot] = item.path


def arrange(source):
    """The plan: the kept frames with their bytes, and the duplicates dropped."""
    owner, slots, kept, duplicates = {}, {}, {}, []
    for item in saved_images(source):
        data = read_jpeg(item.path)
        digest = hashlib.sha256(data).hexdigest()
        if digest in owner:
            refuse_unless_repeat(item, *owner[digest])
            duplicates.append(item.path.relative_to(source).as_posix())
            continue
        if item.group == CT:
            claim_slot(slots, item)
        owner[digest] = (Frame(item.group, item.rid, item.series, item.number, digest), item.path)
        kept[owner[digest][0]] = data
    return kept, duplicates


def case_rows(kept):
    counts = {}
    for frame in kept:
        counts[(frame.group, frame.rid)] = counts.get((frame.group, frame.rid), 0) + 1
    clash = {rid for (group, rid) in counts if all((g, rid) in counts for g in XRAY_GROUPS)}
    if clash:
        raise ImportError_(f"rID {min(clash, key=int)} is under both {' and '.join(XRAY_GROUPS)}; "
                           "one case is one X-ray group")
    return [{"rid": rid, "group": group, "frames": n, "page": CASE_PAGE.format(rid=rid)}
            for (group, rid), n in sorted(counts.items(), key=lambda item: (item[0][0], int(item[0][1])))]


def pair_rows(kept, rows):
    """Every case held both as a CT and as an X-ray, with what each side holds."""
    groups = {}
    for row in rows:
        groups.setdefault(row["rid"], {})[row["group"]] = row["frames"]
    series = {}
    for frame in kept:
        if frame.group == CT:
            series.setdefault(frame.rid, set()).add(frame.series)
    pairs = []
    for rid in sorted(groups, key=int):
        xray = [g for g in XRAY_GROUPS if g in groups[rid]]
        if CT in groups[rid] and xray:
            pairs.append({"rid": rid, "ct_series": len(series[rid]), "ct_slices": groups[rid][CT],
                          "xray_group": xray[0], "xray_frames": groups[rid][xray[0]],
                          "page": CASE_PAGE.format(rid=rid)})
    return pairs


def target_of(frame):
    raw = Path(f"radiopaedia_{frame.group}") / "raw" / frame.rid
    if frame.group == CT:
        return raw / frame.series / f"{frame.number:04d}-{frame.digest[:16]}.jpg"
    return raw / f"{frame.digest[:16]}.jpg"


def csv_bytes(rows, fields):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
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


def write_all(target, kept, rows, pairs):
    files = {target_of(frame): data for frame, data in kept.items()}
    files[Path("CASES.csv")] = csv_bytes(rows, CASE_FIELDS)
    files[Path("PAIRS.csv")] = csv_bytes(pairs, PAIR_FIELDS)
    for relative, data in sorted(files.items()):
        write_once(target / relative, data)
    sums = "".join(f"{hashlib.sha256(data).hexdigest()}  {relative.as_posix()}\n"
                   for relative, data in sorted(files.items(), key=lambda item: item[0].as_posix()))
    write_once(target / "SHA256SUMS", sums.encode())


def summary(kept, duplicates, rows, pairs):
    by_group = {group: sum(1 for frame in kept if frame.group == group) for group in GROUPS}
    lines = [f"{group}: {sum(1 for row in rows if row['group'] == group)} cases, {by_group[group]} frames"
             for group in GROUPS]
    lines.append(f"paired (ct with {' or '.join(XRAY_GROUPS)}): {len(pairs)} cases")
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
        pairs = pair_rows(kept, rows)
        if args.action == "run":
            write_all(args.target, kept, rows, pairs)
    except (ImportError_, OSError) as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    print(summary(kept, duplicates, rows, pairs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
