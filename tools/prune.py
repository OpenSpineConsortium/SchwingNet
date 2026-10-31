"""Plan, then delete, the raw folders of a pruning list the owner chose.

The owner's choice of 2026-10-31 (the thread "Prune unused grid datasets", issue #515): four raw
folders on the data root that neither the gold tier nor the fluoroscopy work reads, none of them a
set the storage planner tracks, so spine-datasets' retirement cannot reach them. A list under
grid/prune/ names the sets, one id a line; the folder of each is <data root>/<id>/raw. The gate
word `prune <list>` runs this twice, as two jobs (grid/prune.sbatch), with the plan shown between:

    python3 tools/prune.py plan   --list <list.txt> --data <data root> --out <plan.json> --report <plan.md>
    python3 tools/prune.py delete --list <list.txt> --data <data root> --plan <plan.json> --report <done.md>

plan walks each folder, never following a link, and records its files and bytes; it deletes
nothing. delete walks each folder again and deletes it only when it still holds exactly the files
and bytes the plan recorded, so nothing landed or changed since the owner saw the plan is ever
deleted; a folder that differs is kept and the report says so. A folder that is a link, has a link
on its path, or lies outside <data root>/<id>/raw is refused by both. Only ids, counts and sizes
leave the grid; no path of the volume is named.

The standard library alone, run by the python the gate names as PYDRV, on a compute node, since the
login node, where the gate runs, kills python by name.
"""

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

ID = re.compile(r"[a-z0-9_]{1,40}")


def read_list(path):
    """The ids a list names, in order; ValueError on a line that is no id or an id named twice."""
    ids = []
    for line in Path(path).read_text(encoding="ascii").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if not ID.fullmatch(line):
            raise ValueError(f"{line!r} is no id: lower-case letters, digits and _, at most 40")
        if line in ids:
            raise ValueError(f"{line} is named twice")
        ids.append(line)
    if not ids:
        raise ValueError("the list names no set")
    return ids


def folder_problem(data, folder):
    """Why a set's raw folder may not be read or deleted, or None when it may."""
    if not folder.exists() and not folder.is_symlink():
        return "no raw folder"
    if folder.is_symlink() or not folder.is_dir():
        return "the raw folder is a link or no folder"
    if os.path.realpath(folder) != os.path.join(os.path.realpath(data), folder.parent.name, folder.name):
        return "a link on the folder's path below the data root"
    return None


def measure(folder):
    """The files and bytes under a folder, walked without following a link; a link counts as a file."""
    files = size = 0
    for root, dirs, names in os.walk(folder, followlinks=False):
        for name in names + [d for d in dirs if os.path.islink(os.path.join(root, d))]:
            files += 1
            size += os.lstat(os.path.join(root, name)).st_size
    return {"files": files, "bytes": size}


def plan(ids, data):
    """{id: measure or problem} for each set of the list."""
    entries = {}
    for one in ids:
        folder = data / one / "raw"
        problem = folder_problem(data, folder)
        entries[one] = {"problem": problem} if problem else measure(folder)
    return entries


def plan_lines(name, entries):
    lines = [f"# prune {name}: the plan", ""]
    total = 0
    for one, entry in entries.items():
        if "problem" in entry:
            lines.append(f"- {one}: refused, {entry['problem']}")
        else:
            total += entry["bytes"]
            lines.append(f"- {one}: {entry['files']:,} files, {entry['bytes'] / 1e9:,.1f} GB")
    lines += ["", f"To delete: {total / 1e9:,.1f} GB. Nothing is deleted until the word is sent again after this report."]
    return lines


def delete(ids, data, planned):
    """Delete each folder that still matches its plan; the report's lines and the bytes freed."""
    lines, freed = [], 0
    for one in ids:
        folder, entry = data / one / "raw", planned.get(one)
        problem = folder_problem(data, folder)
        if entry is None or "problem" in entry:
            lines.append(f"- {one}: kept, the plan lists no folder for it")
        elif problem:
            lines.append(f"- {one}: kept, {problem}")
        elif measure(folder) != {"files": entry["files"], "bytes": entry["bytes"]}:
            lines.append(f"- {one}: kept, it changed since the plan; send the word again for a new plan")
        else:
            shutil.rmtree(folder)
            freed += entry["bytes"]
            lines.append(f"- {one}: deleted, {entry['files']:,} files, {entry['bytes'] / 1e9:,.1f} GB")
    return lines, freed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=("plan", "delete"))
    parser.add_argument("--list", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--out")
    parser.add_argument("--plan")
    parser.add_argument("--report", required=True)
    args = parser.parse_args(argv)
    name, data = Path(args.list).stem, Path(args.data)
    try:
        ids = read_list(args.list)
    except (OSError, ValueError) as error:
        print(f"prune {name}: refused, {error}", file=sys.stderr)
        return 2
    if args.mode == "plan":
        entries = plan(ids, data)
        Path(args.out).write_text(json.dumps(entries, indent=1, sort_keys=True) + "\n", encoding="ascii")
        lines = plan_lines(name, entries)
    else:
        planned = json.loads(Path(args.plan).read_text(encoding="ascii"))
        done, freed = delete(ids, data, planned)
        lines = [f"# prune {name}: the deletion", "", *done, "", f"Freed: {freed / 1e9:,.1f} GB."]
    Path(args.report).write_text("\n".join(lines) + "\n", encoding="ascii")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
