"""What each unmapped folder of the data root holds, read from the sample index (#294).

The owner asked on 2026-10-25 whether any thoracic or cervical fluoroscopy is held, and whether
every set on the grid maps to a known dataset. The sample index (tools/sample_index.py) names
every file, but its manifest gives each group only totals, and 56 groups are folders of the data
root that no record names ("unmapped <folder>"). This report breaks each such group down by its
first folder level, with what tells real fluoroscopy and a body region apart: DICOM modality,
frames, maker and model, image sizes, and how many paths name the cervical or thoracic spine.
It also quotes the first lines of each small text file near a folder's top (a README, a
manifest's notes), since that is where a derived bank says what it was built from. Its first
section lists every folder of the data root with the groups it holds, mapped or not, so each can
be set beside the spine-datasets record and task that account for it (the owner's ask of
2026-10-25 04:53 UTC).

    python tools/folder_report.py --db <run>/samples.sqlite --out logs/FOLDERS.md [--page-bytes N]

Counts, folder names and those quoted lines only; never a file name below the first level, a
header value other than the four above, or a patient key. A long report is cut into pages,
FOLDERS-1.md, FOLDERS-2.md and so on, so the gate prints one page per send within its limit.
"""

import argparse
import os
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

UNMAPPED = "unmapped:"
GRID_DATA = "/rs/rs_grp_oschome/go2432/data"
REGIONS = {"cervical": re.compile(r"cervic|c[-_]?spine|\bneck\b|\bc[1-7]\b", re.I),
           "thoracic": re.compile(r"thorac|t[-_]?spine|\bt(?:[1-9]|1[0-2])\b", re.I),
           "fluoro": re.compile(r"fluoro|c[-_]?arm|cine|intra[-_]?op", re.I)}
NOTE = re.compile(r"(readme|notes?|about|description|manifest|origin|source|license|licence)[^/]*"
                  r"\.(md|txt|rst)$|^readme$", re.I)
TOP_FOLDERS = 15
NOTE_LINES = 12
NOTES_PER_GROUP = 3
NOTE_DEPTH = 2
PAGE_BYTES = 55_000
# The gate's output comes back through grid-accounts.yml, which keeps only a job's last 400 lines
# (symphony-template tools/grid_accounts.py, LOG_LINES), so a page stays well under that in lines too.
PAGE_LINES = 350
# The index keeps what each reader gave, so a number can be stored as text (a header's "1" for
# NumberOfFrames); SQL casts each to an integer, and anything not a number to 0, before Python compares.
ROWS = """SELECT r.sources, COALESCE(f.rel, ''), f.path, f.role, f.format, CAST(f.size AS INTEGER),
                 CAST(f.width AS INTEGER), CAST(f.height AS INTEGER), CAST(f.frames AS INTEGER),
                 f.modality, f.manufacturer, f.model
          FROM file f JOIN root r ON r.id = f.root_id WHERE r.sources LIKE 'unmapped:%'"""


def new_folder():
    return {"files": 0, "bytes": 0, "images": 0, "formats": Counter(), "multiframe": 0,
            "width": [], "height": [], "regions": Counter()}  # each [least, most]


def new_group():
    return {"folders": defaultdict(new_folder), "modality": Counter(), "maker": Counter(),
            "notes": []}


def first_level(rel):
    parts = rel.split("/")
    return parts[0] if len(parts) > 1 else "(top)"


def count_row(group, row):
    _, rel, path, role, fmt, size, width, height, frames, modality, maker, model = row
    folder = group["folders"][first_level(rel)]
    folder["files"] += 1
    folder["bytes"] += size or 0
    folder["formats"][fmt or "unknown"] += 1
    if role == "image":
        folder["images"] += 1
        if width and height:
            widen(folder["width"], width)
            widen(folder["height"], height)
    if (frames or 0) > 1:
        folder["multiframe"] += 1
    for name, pattern in REGIONS.items():
        if pattern.search(rel):
            folder["regions"][name] += 1
    if modality:
        group["modality"][modality] += 1
    if maker or model:
        group["maker"][" ".join(x for x in (maker, model) if x)] += 1
    if rel.count("/") < NOTE_DEPTH and NOTE.search(os.path.basename(rel)):
        group["notes"].append((rel, path))


def widen(bounds, value):
    """Keeps a folder's least and most, since a bank of a million images would not fit as a list."""
    if bounds:
        bounds[:] = [min(bounds[0], value), max(bounds[1], value)]
    else:
        bounds[:] = [value, value]


def gather(db):
    groups = defaultdict(new_group)
    for row in db.execute(ROWS):
        count_row(groups[row[0][len(UNMAPPED):]], row)
    return groups


def note_lines(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            lines = [handle.readline() for _ in range(NOTE_LINES)]
    except OSError as error:
        return [f"(not read: {error.strerror})"]
    text = [line.rstrip()[:160] for line in lines if line.strip()]
    return [line.encode("ascii", "replace").decode("ascii") for line in text]


def human(size):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return str(size)


def span(values):
    return f"{values[0]}-{values[1]}" if values else "-"


def top(counter, n=4):
    """The n commonest, a tie by name, so the same index always gives the same page."""
    ranked = sorted(counter.items(), key=lambda item: (-item[1], str(item[0])))[:n]
    return ", ".join(f"{k} {v}" for k, v in ranked) or "-"


def folder_line(name, folder):
    regions = top(folder["regions"], 3)
    return (f"| {name} | {folder['files']} | {human(folder['bytes'])} | {folder['images']} | "
            f"{top(folder['formats'], 3)} | {span(folder['width'])} x {span(folder['height'])} | "
            f"{folder['multiframe']} | {regions} |")


def group_section(name, group):
    folders = group["folders"]
    files = sum(f["files"] for f in folders.values())
    size = sum(f["bytes"] for f in folders.values())
    lines = [f"## {name}", "",
             f"{files} files, {human(size)}, {len(folders)} first-level folders. "
             f"DICOM modality: {top(group['modality'])}. Maker and model: {top(group['maker'])}.", "",
             "| folder | files | size | images | formats | width x height | multi-frame | paths naming |",
             "| --- | ---: | ---: | ---: | --- | --- | ---: | --- |"]
    ranked = sorted(folders.items(), key=lambda item: (-item[1]["files"], item[0]))
    lines += [folder_line(folder, data) for folder, data in ranked[:TOP_FOLDERS]]
    if len(ranked) > TOP_FOLDERS:
        rest = ranked[TOP_FOLDERS:]
        lines.append(f"| ({len(rest)} more) | {sum(f['files'] for _, f in rest)} | "
                     f"{human(sum(f['bytes'] for _, f in rest))} | {sum(f['images'] for _, f in rest)} | | | "
                     f"{sum(f['multiframe'] for _, f in rest)} | |")
    for rel, path in sorted(group["notes"])[:NOTES_PER_GROUP]:
        lines += ["", f"{rel}:", ""] + [f"    {line}" for line in note_lines(path)]
    return "\n".join(lines) + "\n"


def data_root_folders(db, data_root):
    """Every folder directly under the data root that holds a root of the index, with the groups in
    it, mapped or not, so each folder can be set beside the dataset record that accounts for it."""
    prefix = data_root.rstrip("/") + "/"
    folders = defaultdict(Counter)
    query = ("SELECT r.path, r.sources, COUNT(f.id), COALESCE(SUM(CAST(f.size AS INTEGER)), 0) "
             "FROM root r LEFT JOIN file f ON f.root_id = r.id GROUP BY r.id")
    for path, sources, files, size in db.execute(query):
        if path.startswith(prefix):
            name = path[len(prefix):].split("/")[0]
            folders[name][sources or "-"] += files
            folders[name]["__bytes"] += size
    return folders


def data_root_section(folders):
    lines = ["## Every folder of the data root", "",
             "| folder | size | files | groups (files) |", "| --- | ---: | ---: | --- |"]
    for name in sorted(folders):
        counts = folders[name]
        size = counts.pop("__bytes", 0)
        groups = ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
        lines.append(f"| {name} | {human(size)} | {sum(counts.values())} | {groups} |")
    return "\n".join(lines) + "\n"


def report(groups, roots=None):
    head = ("# What the unmapped folders hold\n\nFrom the sample index, by tools/folder_report.py. "
            "Multi-frame counts files with more than one frame (video or cine). \"Paths naming\" counts "
            "files whose path names the cervical or thoracic spine, or fluoroscopy, a C-arm, cine or "
            "the operating room.\n")
    order = sorted(groups, key=lambda name: -sum(f["bytes"] for f in groups[name]["folders"].values()))
    tail = [data_root_section(roots)] if roots is not None else []
    return [head] + tail + [group_section(name, groups[name]) for name in order]


def chunks(section, limit, max_lines):
    """A section longer than a page goes on over the next pages, never cut, by lines and by bytes."""
    out, chunk = [], []
    for line in section.splitlines(keepends=True):
        line = line[:limit]
        if chunk and (len(chunk) >= max_lines or sum(map(len, chunk)) + len(line) > limit):
            out.append("".join(chunk))
            chunk = ["(continued)\n"]
        chunk.append(line)
    return out + (["".join(chunk)] if chunk else [])


def pages(sections, limit, max_lines=PAGE_LINES):
    out, page = [], ""
    for section in sections:
        for chunk in chunks(section, limit - 1, max_lines - 1):
            if page and (len(page) + len(chunk) + 1 > limit or
                         page.count("\n") + chunk.count("\n") + 1 > max_lines):
                out.append(page)
                page = ""
            page += chunk + "\n"
    return out + ([page] if page else [])


def write(sections, out, limit):
    out = Path(out)
    written = pages(sections, limit, PAGE_LINES)
    for number, text in enumerate(written, 1):
        # Folder names on the volume are not all ASCII; escaped, they stay readable and the page prints.
        out.with_name(f"{out.stem}-{number}{out.suffix}").write_text(text, encoding="ascii", errors="backslashreplace")
    return len(written)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--page-bytes", type=int, default=PAGE_BYTES)
    parser.add_argument("--data-root", default=os.environ.get("DATA_ROOT", GRID_DATA))
    args = parser.parse_args(argv)
    db = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    sections = report(gather(db), data_root_folders(db, args.data_root))
    db.close()
    count = write(sections, args.out, args.page_bytes)
    print(f"folders: {len(sections) - 2} groups in {count} pages beside {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
