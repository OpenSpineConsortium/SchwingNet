"""Look inside one fetched set before anyone writes its bank recipe: what its folders and archives
hold and, for a set that may be another set re-exported, whether its images are that set's films.

The owner's choice of 2026-10-23 (the Dataset finalization thread): the Kaggle fracture set
(spine-datasets #24) needs its folder names and counts so he can map it back to the three uploads
it merges, and the Kaggle scoliosis set (#23) needs a content comparison with AASCE, since a
Roboflow export re-encodes and usually resizes every image, so no sha256 of it can match the
original film even when the person is the same. The gate word `explore <id>` runs this as one job
(grid/explore.sbatch) and prints the report on the next send.

    pixi run --locked -e train-cpu python tools/explore.py --id <id> --raw <dest> \\
        [--against <label>=<folder> ...] --out <report.md> [--workers N]

The listing reads the raw folder and every zip in it without unpacking: files and bytes by
extension, each folder to depth three with its file count, the image sizes of a sample, the
classes a YOLO export's data.yaml names with the boxes its label files hold per class, and each
CSV's header and row count. The comparison reduces every image of the set, and its mirror image,
as the leak checks do (tools/leaks.py: the 0.5-99.5 percentile 8-bit reduction squashed to a
square, so a resize or a stretch to 640 x 640 changes little), finds the pairs within a perceptual
hash distance by schwingnet.leaks' multi-index search, and confirms each by NCC64 at 0.97, the
leak checks' threshold; it also matches file names once Roboflow's `_jpg.rf.<hash>` suffix is cut.
A crop or a rotation beyond a few degrees escapes both, so the report says what it could not see.

Only counts, the set's own folder and class names and a few example pairs leave the grid; no
folder of the volume is named, only the labels the caller gives. tools/ never goes on sys.path,
since tools/profile.py would shadow the standard library's profile.
"""

import argparse
import fnmatch
import importlib.util
import io
import os
import re
import sys
import zipfile
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [entry for entry in sys.path if Path(entry or ".").resolve() != ROOT / "tools"]
for folder in (ROOT / "vendor" / "beethoven-qa" / "src", ROOT / "src"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from schwingnet import leaks  # noqa: E402

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
DEPTH = 3
FOLDER_LINES = 60
SIZE_SAMPLE = 400
CSV_FILES = 10
YAML_LINES = 30
DISTANCE = 12
NCC_SAME = 0.97
NCC_NEAR = 0.90
EXAMPLES = 8
PAIR_LIMIT = 5_000_000
ROBOFLOW = re.compile(r"_(jpe?g|png|bmp)\.rf\.[0-9a-f]+$", re.IGNORECASE)


def load_leaks_tool():
    """tools/leaks.py by path, for the reduction the leak checks take of a frame."""
    spec = importlib.util.spec_from_file_location("leaks_tool", ROOT / "tools" / "leaks.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


# --- what the set holds ------------------------------------------------------------------------


def members(raw):
    """Every file of the set as (where, inner path, size): a file on disk is its own place, a zip's
    member is read from its archive; folders and unreadable archives are skipped with a note."""
    found, notes = [], []
    for path in sorted(Path(raw).rglob("*")):
        if not path.is_file() or path.name.endswith(".part"):
            continue
        relative = path.relative_to(raw).as_posix()
        found.append(("disk", relative, path.stat().st_size))
        if path.suffix.lower() == ".zip":
            try:
                with zipfile.ZipFile(path) as archive:
                    for info in archive.infolist():
                        if not info.is_dir():
                            found.append((relative, info.filename, info.file_size))
            except (OSError, zipfile.BadZipFile) as error:
                notes.append(f"{relative}: not readable as a zip ({type(error).__name__})")
    return found, notes


def suffix_of(name):
    """A file's extension in lower case, or '(none)'."""
    return PurePosixPath(name).suffix.lower() or "(none)"


def by_extension(files):
    """Lines of files and bytes per extension, the commonest first."""
    counts, sizes = Counter(), Counter()
    for _, name, size in files:
        counts[suffix_of(name)] += 1
        sizes[suffix_of(name)] += size
    return [f"  {ext}: {counts[ext]:,} files, {sizes[ext] / 1e6:,.1f} MB" for ext, _ in counts.most_common()]


def folder_counts(files):
    """Lines of each folder to depth three with the files below it, in path order, bounded."""
    counts = Counter()
    for _, name, _ in files:
        parts = PurePosixPath(name).parts[:-1]
        for depth in range(1, min(len(parts), DEPTH) + 1):
            counts["/".join(parts[:depth])] += 1
    lines = [f"  {'  ' * (key.count('/'))}{key.split('/')[-1]}/: {counts[key]:,}" for key in sorted(counts)]
    if len(lines) > FOLDER_LINES:
        lines = lines[:FOLDER_LINES] + [f"  ... {len(lines) - FOLDER_LINES} more folders"]
    return lines


def read_member(raw, where, name):
    """The bytes of one file of the set, from disk or from its zip."""
    if where == "disk":
        return (Path(raw) / name).read_bytes()
    with zipfile.ZipFile(Path(raw) / where) as archive:
        return archive.read(name)


def images_of(files):
    """The image files of the set, as (where, name)."""
    return [(where, name) for where, name, _ in files if suffix_of(name) in IMAGE_SUFFIXES]


def image_sizes(raw, images):
    """Lines of the commonest width x height over an even sample of the images."""
    from PIL import Image

    step = max(1, len(images) // SIZE_SAMPLE)
    sizes, failed = Counter(), 0
    for where, name in images[::step][:SIZE_SAMPLE]:
        try:
            with Image.open(io.BytesIO(read_member(raw, where, name))) as image:
                sizes[f"{image.width} x {image.height} {image.mode}"] += 1
        except Exception:  # Pillow raises many kinds for a broken file; each is counted
            failed += 1
    lines = [f"  {size}: {count}" for size, count in sizes.most_common(8)]
    if failed:
        lines.append(f"  not decodable: {failed}")
    return lines


def text_of(raw, where, name):
    """A small text file of the set as ASCII, other characters dropped."""
    data = read_member(raw, where, name)[:200_000]
    return "".join(c for c in data.decode("utf-8", "replace") if c == "\n" or " " <= c <= "~")


def yolo_lines(raw, files):
    """The first data.yaml's lines and the boxes per class over every YOLO label file."""
    lines = []
    yamls = [(w, n) for w, n, _ in files if fnmatch.fnmatch(PurePosixPath(n).name.lower(), "*.yaml")]
    for where, name in yamls[:1]:
        lines.append(f"  {PurePosixPath(name).name}:")
        lines += [f"    {line}" for line in text_of(raw, where, name).splitlines()[:YAML_LINES]]
    labels = [(w, n) for w, n, _ in files if suffix_of(n) == ".txt" and "/labels/" in f"/{n}"]
    boxes, empty = Counter(), 0
    for where, name in labels:
        rows = [row.split() for row in text_of(raw, where, name).splitlines() if row.strip()]
        empty += not rows
        boxes.update(row[0] for row in rows)
    if labels:
        lines.append(f"  label files: {len(labels):,}, {empty:,} with no box")
        lines += [f"  class {key}: {boxes[key]:,} boxes" for key in sorted(boxes, key=lambda k: (len(k), k))]
    return lines


def csv_lines(raw, files):
    """Each CSV's header and its number of rows, bounded."""
    lines = []
    for where, name, _ in [f for f in files if suffix_of(f[1]) == ".csv"][:CSV_FILES]:
        rows = text_of(raw, where, name).splitlines()
        lines.append(f"  {name}: {max(len(rows) - 1, 0):,} rows; header: {rows[0][:240] if rows else ''}")
    return lines


def listing(raw, files, notes):
    """The listing part of the report."""
    images = images_of(files)
    lines = ["## what the set holds", f"  files: {len(files):,}, images: {len(images):,}"]
    lines += [f"  {note}" for note in notes]
    lines += ["## by extension"] + by_extension(files)
    lines += ["## folders (depth 3; a zip's members under the zip's own folders)"] + folder_counts(files)
    lines += ["## image sizes (an even sample)"] + image_sizes(raw, images)
    yolo = yolo_lines(raw, files)
    if yolo:
        lines += ["## YOLO classes and boxes"] + yolo
    tables = csv_lines(raw, files)
    if tables:
        lines += ["## tables"] + tables
    return lines


# --- whether the images are another set's ------------------------------------------------------


def stem_key(name):
    """A file name as the comparison of names reads it: Roboflow's suffix cut, lower case,
    letters and digits only."""
    stem = ROBOFLOW.sub("", PurePosixPath(name).stem)
    return re.sub(r"[^a-z0-9]", "", stem.lower())


def shown(name):
    """A file name as an example pair shows it: Roboflow's suffix cut, at most 60 characters."""
    path = PurePosixPath(name)
    return (ROBOFLOW.sub("", path.stem) + path.suffix)[:60]


_TOOL = {}


def reduce_one(task):
    """One image's perceptual hashes and NCC64 reductions, as is and mirrored, or None."""
    raw, where, name = task
    if not _TOOL:
        _TOOL["leaks"] = load_leaks_tool()
    tool = _TOOL["leaks"]
    np, Image = tool.imaging()
    try:
        with Image.open(io.BytesIO(read_member(raw, where, name))) as image:
            image.load()
            eight = tool.eight_bit(tool.grey_array(image, np), np)
    except Exception:  # a file Pillow cannot decode is counted, never fatal
        return None
    out = []
    for array in (eight, eight[:, ::-1]):
        reduced = Image.fromarray(np.ascontiguousarray(array))
        box = Image.Resampling.BOX
        small = reduced.resize((tool.HASH_REDUCTION, tool.HASH_REDUCTION), box).tobytes()
        ncc64 = reduced.resize((leaks.NCC_SIDE, leaks.NCC_SIDE), box).tobytes()
        out.append((leaks.phash(small, tool.HASH_REDUCTION), ncc64))
    return out


def reductions(raw, images, workers):
    """Each image's reductions in order, None where it could not be decoded."""
    tasks = [(str(raw), where, name) for where, name in images]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(reduce_one, tasks, chunksize=16))


def best_matches(ours, theirs):
    """For each image of ours that decoded, its best NCC64 over the candidates within the hash
    distance, as is or mirrored, with the index of their image and whether it was the mirror."""
    codes, owner = [], []
    for i, pair in enumerate(theirs):
        if pair:
            codes.append(pair[0][0])
            owner.append(("theirs", i, False))
    probes = set()
    for i, pair in enumerate(ours):
        if pair:
            for mirrored in (False, True):
                probes.add(len(codes))
                codes.append(pair[mirrored][0])
                owner.append(("ours", i, mirrored))
    pairs = leaks.candidate_pairs(tuple(codes), DISTANCE, frozenset(probes), PAIR_LIMIT)
    best = {}
    for a, b, distance in pairs:
        one, two = owner[a], owner[b]
        if one[0] == two[0]:
            continue
        mine, other = (one, two) if one[0] == "ours" else (two, one)
        score = leaks.ncc(ours[mine[1]][mine[2]][1], theirs[other[1]][0][1])
        if score > best.get(mine[1], (-2.0,))[0]:
            best[mine[1]] = (score, other[1], mine[2], distance)
    return best, len(pairs) > PAIR_LIMIT


def comparison(raw, images, against, workers):
    """The comparison part of the report: names, then content, against every labelled set."""
    lines = ["## against the sets named (names, then content)"]
    ours = reductions(raw, images, workers)
    decoded = sum(1 for r in ours if r)
    lines.append(f"  this set: {len(images):,} images, {decoded:,} decoded")
    our_keys = Counter(stem_key(name) for _, name in images)
    theirs_all, labels = [], []
    for label, folder in against:
        files, notes = members(folder)
        their_images = images_of(files)
        theirs = reductions(folder, their_images, workers)
        theirs_all.append((label, their_images, theirs))
        named = {stem_key(name) for _, name in their_images}
        shared = sum(count for key, count in our_keys.items() if key in named)
        lines.append(f"  {label}: {len(their_images):,} images, {sum(1 for r in theirs if r):,} decoded"
                     + (f" ({'; '.join(notes)})" if notes else ""))
        lines.append(f"    names: {shared:,} of this set's images share a file name with it once Roboflow's suffix is cut")
        labels.append(label)
    for label, their_images, theirs in theirs_all:
        best, cut = best_matches(ours, theirs)
        same = {i: m for i, m in best.items() if m[0] >= NCC_SAME}
        near = {i: m for i, m in best.items() if NCC_NEAR <= m[0] < NCC_SAME}
        films = {m[1] for m in same.values()}
        lines.append(f"  {label} by content (hash distance <= {DISTANCE}, then NCC64):")
        lines.append(f"    the same film (NCC64 >= {NCC_SAME}): {len(same):,} of this set's images,"
                     f" {len(films):,} distinct films of {label}, {sum(1 for m in same.values() if m[2]):,} of them mirrored")
        lines.append(f"    close (NCC64 {NCC_NEAR} to {NCC_SAME}): {len(near):,}; a candidate below {NCC_NEAR}: {len(best) - len(same) - len(near):,};"
                     f" no candidate at all: {decoded - len(best):,}")
        if cut:
            lines.append(f"    the search stopped at {PAIR_LIMIT:,} pairs, so these counts are a floor")
        for i, (score, j, mirrored, distance) in sorted(same.items(), key=lambda kv: -kv[1][0])[:EXAMPLES]:
            lines.append(f"    e.g. {shown(images[i][1])} ~ {shown(their_images[j][1])}"
                         f" (NCC64 {score:.3f}, distance {distance}{', mirrored' if mirrored else ''})")
    lines.append("  not seen: a crop, or a rotation beyond a few degrees, moves both the hash and NCC64, so an"
                 " augmented copy of that kind counts as no candidate; the names line catches those whose name survived")
    return lines


def report(set_id, raw, against, workers):
    """The whole report as lines."""
    files, notes = members(raw)
    lines = [f"# explore {set_id}"] + listing(raw, files, notes)
    if against:
        lines += comparison(raw, images_of(files), against, workers)
    return lines


def parse_against(values):
    """--against label=folder pairs, in the order given."""
    pairs = []
    for value in values:
        label, sep, folder = value.partition("=")
        if not sep or not label or not folder:
            raise SystemExit(f"--against takes label=folder, not {value!r}")
        pairs.append((label, folder))
    return pairs


def main(argv=None):
    """Write the report for one set, atomically, and print where."""
    top = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    top.add_argument("--id", required=True, help="the set's id, for the report's title")
    top.add_argument("--raw", required=True, help="the set's raw folder")
    top.add_argument("--against", action="append", default=[], help="label=folder of a set to compare with")
    top.add_argument("--out", required=True, help="the report, Markdown")
    top.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    args = top.parse_args(argv)
    if not Path(args.raw).is_dir():
        print(f"explore: no folder {args.raw}")
        return 2
    lines = report(args.id, args.raw, parse_against(args.against), max(1, args.workers))
    out = Path(args.out)
    partial = out.with_name(out.name + ".part")
    partial.write_text("\n".join(lines) + "\n", encoding="ascii", errors="replace")
    partial.replace(out)
    print(f"explore: {len(lines)} lines to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
