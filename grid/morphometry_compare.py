"""The morphometry rows the reruns of 2026-10-31 wrote, set beside the rows they replaced.

The owner's count of 2026-10-30 14:33 UTC measured both gold tier 3 sets once more on the engine at
bordercall 9c85de1 (docs/research/morphometry-resynthesis.md); the gate moved each set's earlier rows
under <set>/kept/<job>/ before the rerun (grid/gate.sh, morphometry_keep). This reads both and says,
per population, measure and level, how far the values moved, so the four measures bordercall #44
reworked can be seen to move and the rest seen to hold. The word `morphometry compare` in grid/gate.sh
runs it as one CPU job (grid/morphometry-compare.sbatch); the rows never leave the grid.

Read: under ROOT, the new rows (enhance/rows.csv, verse/rows.csv, verse/totalseg/rows.csv) and the
same file under the set's newest kept/<job>/. A value is paired with its study, level and key; an
empty value is none; the per-study rows (level "study": the code stamp, the timing) are left out of
the values and the code stamps are counted instead.

Written: under OUT, compare.csv (one line per population, key and level: the counts, the medians,
the median paired change and the share of pairs that moved by more than one percent),
compare-<population>.svg (a grid of measures by levels coloured by the median relative change), and
report.lines, the lines the job's report carries. No line holds a path, a study id or a person key.
Python 3.8 and the standard library alone, as the grid's interpreters have.
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import statistics
import sys
from typing import Dict, List, Optional, Tuple

POPULATIONS = (("enhance_pet", "enhance", "rows.csv"), ("verse", "verse", "rows.csv"),
               ("totalsegmentator", "verse", "totalseg/rows.csv"))
MOVED = 0.01          # a pair moved when it changed by more than this share of the old value
CLIP = 0.2            # the colour scale's end, a relative change of twenty percent
LEVEL = re.compile(r"^([CTLS])(\d+)$")
REGION_ORDER = "CTLS"

Key = Tuple[str, str, str]


def level_order(level: str) -> Tuple[int, int, str]:
    """C1 before C2 before T1 and on to the sacrum; a name of another form comes last, by name."""
    found = LEVEL.match(level)
    if found:
        return REGION_ORDER.index(found.group(1)), int(found.group(2)), ""
    return len(REGION_ORDER), 0, level


def number(text: str) -> Optional[float]:
    """The value of a cell, or None for an empty or unreadable one."""
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None
    return value if value == value else None


def read_rows(path: str) -> Tuple[Dict[Key, float], Dict[str, int]]:
    """Every value of a rows file by study, level and key, and how many studies each code stamp measured."""
    values: Dict[Key, float] = {}
    stamps: Dict[str, int] = {}
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("level") == "study":
                if row.get("key") == "code":
                    stamp = (row.get("note") or "").strip() or "none"
                    stamps[stamp] = stamps.get(stamp, 0) + 1
                continue
            value = number(row.get("value", ""))
            if value is not None:
                values[(row["study"], row["level"], row["key"])] = value
    return values, stamps


def newest_kept(folder: str) -> Optional[str]:
    """The newest kept/<job>/ of a set's folder, by job number, or None where nothing is kept."""
    kept = os.path.join(folder, "kept")
    jobs = [name for name in os.listdir(kept) if name.isdigit()] if os.path.isdir(kept) else []
    return os.path.join(kept, max(jobs, key=int)) if jobs else None


def relative(old: float, new: float) -> Optional[float]:
    """The change from old to new as a share of the old value, or None where the old value is zero."""
    return None if old == 0 else (new - old) / abs(old)


def compare(old: Dict[Key, float], new: Dict[Key, float]) -> Dict[Tuple[str, str], dict]:
    """Per key and level: the counts, the medians over the pairs and how far the pairs moved."""
    groups: Dict[Tuple[str, str], dict] = {}

    def group(key: str, level: str) -> dict:
        return groups.setdefault((key, level), {"old": 0, "new": 0, "pairs": [], "lost": 0, "gained": 0})

    for (study, level, key), value in old.items():
        entry = group(key, level)
        entry["old"] += 1
        if (study, level, key) in new:
            entry["pairs"].append((value, new[(study, level, key)]))
        else:
            entry["lost"] += 1
    for (study, level, key) in new:
        entry = group(key, level)
        entry["new"] += 1
        if (study, level, key) not in old:
            entry["gained"] += 1
    return {name: summarise(entry) for name, entry in groups.items()}


def summarise(entry: dict) -> dict:
    """One group's counts and medians from its pairs."""
    pairs = entry.pop("pairs")
    changes = [relative(a, b) for a, b in pairs]
    shares = [c for c in changes if c is not None]
    moved = sum(1 for (a, b), c in zip(pairs, changes) if (abs(c) > MOVED if c is not None else b != a))
    entry.update(paired=len(pairs), moved=moved,
                 old_median=statistics.median(a for a, _ in pairs) if pairs else None,
                 new_median=statistics.median(b for _, b in pairs) if pairs else None,
                 change_median=statistics.median(b - a for a, b in pairs) if pairs else None,
                 relative_median=statistics.median(shares) if shares else None)
    return entry


def by_key(groups: Dict[Tuple[str, str], dict]) -> Dict[str, List[Tuple[str, dict]]]:
    """The groups of each key in level order."""
    keys: Dict[str, List[Tuple[str, dict]]] = {}
    for (key, level), entry in groups.items():
        keys.setdefault(key, []).append((level, entry))
    for levels in keys.values():
        levels.sort(key=lambda item: level_order(item[0]))
    return keys


def percent(share: Optional[float]) -> str:
    return "n/a" if share is None else f"{100 * share:+.1f}%"


def key_line(key: str, levels: List[Tuple[str, dict]]) -> Tuple[float, str]:
    """A key's line of the report and the share of its pairs that moved, which orders the lines."""
    paired = sum(entry["paired"] for _, entry in levels)
    moved = sum(entry["moved"] for _, entry in levels)
    lost = sum(entry["lost"] for _, entry in levels)
    gained = sum(entry["gained"] for _, entry in levels)
    share = moved / paired if paired else 0.0
    ranked = [(abs(entry["relative_median"]), level, entry["relative_median"]) for level, entry in levels
              if entry["relative_median"] is not None and entry["paired"] >= 10]
    ranked.sort(reverse=True)
    largest = ", ".join(f"{level} {percent(value)}" for _, level, value in ranked[:3]) or "none with ten pairs"
    line = (f"{key}: {len(levels)} levels, {paired} pairs, {100 * share:.1f}% moved by more than "
            f"{100 * MOVED:.0f}%, {lost} values gone and {gained} new; largest median relative changes {largest}")
    return share, line


def population_lines(name: str, job: str, old_stamps: Dict[str, int], new_stamps: Dict[str, int],
                     old: Dict[Key, float], new: Dict[Key, float],
                     groups: Dict[Tuple[str, str], dict]) -> List[str]:
    """The report's lines for one population, its keys ordered by the share of their pairs that moved."""
    old_studies = {study for study, _, _ in old}
    new_studies = {study for study, _, _ in new}
    paired = sum(entry["paired"] for entry in groups.values())
    moved = sum(entry["moved"] for entry in groups.values())
    lines = [
        f"{name}: the rows of job {job} beside the new rows; studies {len(old_studies)} then {len(new_studies)}, "
        f"{len(old_studies & new_studies)} in both; values {len(old)} then {len(new)}, {paired} paired, "
        f"{100 * moved / paired if paired else 0:.1f}% of them moved by more than {100 * MOVED:.0f}%",
        f"{name}: code stamps then {stamp_text(old_stamps)}; now {stamp_text(new_stamps)}",
    ]
    keyed = [key_line(key, levels) for key, levels in by_key(groups).items()]
    keyed.sort(key=lambda item: (-item[0], item[1]))
    lines += [f"{name} {line}" for _, line in keyed]
    return lines


def stamp_text(stamps: Dict[str, int]) -> str:
    return ", ".join(f"{stamp} for {count} studies" for stamp, count in sorted(stamps.items())) or "none"


def write_csv(path: str, results: List[Tuple[str, Dict[Tuple[str, str], dict]]]) -> None:
    fields = ["population", "key", "level", "old", "new", "paired", "moved", "lost", "gained",
              "old_median", "new_median", "change_median", "relative_median"]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for name, groups in results:
            for key, levels in sorted(by_key(groups).items()):
                for level, entry in levels:
                    writer.writerow({"population": name, "key": key, "level": level,
                                     **{field: rounded(entry[field]) for field in fields[3:]}})


def rounded(value):
    return "" if value is None else round(value, 6) if isinstance(value, float) else value


def colour(share: Optional[float]) -> str:
    """Blue for a value that fell, red for one that rose, white for none, grey where nothing pairs."""
    if share is None:
        return "#d9d9d9"
    weight = min(abs(share), CLIP) / CLIP
    fade = round(255 * (1 - weight))
    return f"rgb({fade},{fade},255)" if share < 0 else f"rgb(255,{fade},{fade})"


def write_svg(path: str, name: str, groups: Dict[Tuple[str, str], dict]) -> None:
    """A grid of keys by levels, each cell the median relative change of its pairs."""
    keys = by_key(groups)
    levels = sorted({level for _, level in groups}, key=level_order)
    cell, left, top = 16, 190, 60
    width, height = left + cell * len(levels) + 20, top + cell * len(keys) + 40
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" font-family="sans-serif" font-size="10">',
             f'<rect width="{width}" height="{height}" fill="white"/>',
             f'<text x="{left}" y="16" font-size="12">{name}: median relative change, new rows against the kept rows '
             f'(blue fell, red rose, full colour at {100 * CLIP:.0f}%, grey none paired)</text>']
    for column, level in enumerate(levels):
        x = left + column * cell + cell / 2
        parts.append(f'<text x="{x}" y="{top - 6}" text-anchor="end" transform="rotate(-60 {x} {top - 6})">{level}</text>')
    for row, key in enumerate(sorted(keys)):
        y = top + row * cell
        parts.append(f'<text x="{left - 4}" y="{y + cell - 4}" text-anchor="end">{key}</text>')
        found = dict(keys[key])
        for column, level in enumerate(levels):
            entry = found.get(level)
            share = entry["relative_median"] if entry and entry["paired"] else None
            parts.append(f'<rect x="{left + column * cell}" y="{y}" width="{cell}" height="{cell}" '
                         f'fill="{colour(share)}" stroke="white"/>')
    parts.append("</svg>")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(parts) + "\n")


def run(root: str, out: str) -> int:
    """Every population with rows on both sides compared; 0 when all three were, 3 when one was not."""
    os.makedirs(out, exist_ok=True)
    lines: List[str] = []
    results = []
    status = 0
    for name, folder, rows in POPULATIONS:
        set_folder = os.path.join(root, folder)
        kept = newest_kept(set_folder)
        new_path = os.path.join(set_folder, rows)
        old_path = os.path.join(kept, rows) if kept else ""
        if not (kept and os.path.isfile(old_path) and os.path.isfile(new_path)):
            lines.append(f"FAILED: no kept rows and new rows to set side by side for {name}")
            status = 3
            continue
        old, old_stamps = read_rows(old_path)
        new, new_stamps = read_rows(new_path)
        groups = compare(old, new)
        results.append((name, groups))
        lines += population_lines(name, os.path.basename(kept), old_stamps, new_stamps, old, new, groups)
        write_svg(os.path.join(out, f"compare-{name}.svg"), name, groups)
    write_csv(os.path.join(out, "compare.csv"), results)
    with open(os.path.join(out, "report.lines"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return status


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--morphometry", required=True, help="the morphometry root that holds enhance/ and verse/")
    parser.add_argument("--out", required=True, help="the job's own folder")
    args = parser.parse_args(argv)
    return run(args.morphometry, args.out)


if __name__ == "__main__":
    sys.exit(main())
