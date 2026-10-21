"""The leak checks as the ingestion step: fingerprint each shard, then join every fingerprint for
CHK-6 (near-duplicates across the split) and CHK-7 (undeclared aliases by store or pixel key).

docs/research/retraining-plan.md (3.2) runs the checks at ingestion, over a new shard against
every shard already registered, and spine-program's LEAKAGE.md defines them; the rules are
schwingnet.leaks under beethoven-qa's gate, and this script is the reading and writing around
them. It works in two steps so the expensive one runs in parallel, one Slurm array task a shard
(grid/04-leaks.sbatch), and the cheap one once (grid/05-leaks-join.sbatch):

    pixi run --locked -e train-cpu python tools/leaks.py fingerprint --shard <shard dir> \\
        --out <file.jsonl> [--workers N]
    pixi run --locked python tools/leaks.py join --fingerprints '<dir>/*.jsonl' --out <dir> \\
        [--expect <shard list>] [--declared data/splits/aliases.json] [--new <shard>] [--distance 8]

`fingerprint` reads the shard's MANIFEST.json and every frame it names, checks each frame's bytes
against the sha256 the manifest gives (the store key), decodes it with Pillow, reduces it to 8 bits
between its 0.5 and 99.5 percentiles and hashes that (the pixel key), and from the reduction takes
a 32 x 32 grey image for the perceptual hash and a 64 x 64 one for NCC64, kept in the file as
base64. One JSON line a frame after a header line that names the shard and the sha256 of its
manifest; the same shard gives the same bytes, and a file already there for the same manifest with
no failed frame is left as it is. The lines are written as they come, a chunk of 1,024 frames at a
time, atomically, beside the file (<file>.parts/), so a task the partition requeues takes up the
chunks it finished and decodes only the rest. A frame that cannot be read, does not match its hash or cannot be
decoded is a line with its reason and no keys, and the step exits 2 after writing the file, so the
join counts it: unknown is not clean.

`join` reads every fingerprint file, drops a shard another input supersedes (the catalog reads a
chain at its head alone), gives each person its part by the frozen split (data/splits/), finds the
pairs of perceptual hashes within the distance by multi-index hashing, confirms them by NCC64 and
writes LEAKS.json (every failing row, the counts, the verdict, the inputs) and LEAKS.md into the
folder named. `--new` probes only the frames of one shard, against every other and among its own,
which is the check an ingest runs; `--expect` names the shard folders the run meant to cover, one a
line, and a folder with no fingerprint, or one for another manifest, fails the join. It exits 1 on
FAIL, an input missing or unreadable among them, and 2 when it cannot run at all.

numpy and Pillow are imported only by `fingerprint`, from the train-cpu environment; `join` needs
only the default one. tools/ never goes on sys.path, since tools/profile.py would shadow the
standard library's profile for anything that imports it.
"""

import argparse
import base64
import dataclasses
import gc
import glob
import hashlib
import importlib.util
import io
import json
import multiprocessing
import os
import re
import shutil
import sys
import tempfile
from array import array
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [entry for entry in sys.path if Path(entry or ".").resolve() != ROOT / "tools"]
for folder in (ROOT / "vendor" / "beethoven-qa" / "src", ROOT / "src"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from pydantic import ValidationError  # noqa: E402
from schwingnet import leaks  # noqa: E402


def load_catalog_tool():
    """tools/catalog.py by path, for its manifest and split readers, without tools/ on sys.path."""
    spec = importlib.util.spec_from_file_location("catalog_tool", ROOT / "tools" / "catalog.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


catalog_tool = load_catalog_tool()

# Version 2: the perceptual hash in exact integer arithmetic (schwingnet.leaks), so a file of
# version 1, whose bits a node's floating point could flip, is taken again rather than joined.
FINGERPRINT_VERSION = 2
MANIFEST = "MANIFEST.json"
HASH_REDUCTION = 32
DECLARED = ROOT / "data" / "splits" / "aliases.json"
LEAKS_JSON, LEAKS_MD = "LEAKS.json", "LEAKS.md"
ROWS_IN_PAGE = 50
# The frames of one partial file, written as each fills, so a task the reqp partition requeues
# loses at most one chunk's work: about a minute of eight cores on the largest films.
CHUNK_FRAMES = 1024
REDUCTION_BYTES = 64 * 64
KEYS = ("store_key", "pixel_key", "phash", "ncc64")
PHASH_TEXT = re.compile(r"[0-9a-f]{16}")
# The candidate pairs a join holds before it stops: about 2 GB of pairs and, at the NCC rate
# measured in a container (grid/README.md, The leak checks), under an hour on eight cores.
MAX_PAIRS = 20_000_000


class LeakError(Exception):
    """An input the step cannot run on, with the reason a person reads."""


# --- fingerprint -------------------------------------------------------------------------------

_IMAGING = {}


def imaging():
    """numpy and Pillow, imported once per process, only where a frame is fingerprinted."""
    if not _IMAGING:
        import numpy
        from PIL import Image

        _IMAGING.update(np=numpy, Image=Image)
    return _IMAGING["np"], _IMAGING["Image"]


def grey_array(image, np):
    """The frame as one grey channel of floats: 16-bit and float frames keep their depth, every
    colour or palette mode is converted to Pillow's luminance."""
    if image.mode in ("I;16", "I;16L", "I;16B", "I", "F", "L"):
        array = np.asarray(image, dtype=np.float64)
    else:
        array = np.asarray(image.convert("L"), dtype=np.float64)
    if array.ndim != 2 or array.size == 0:
        raise ValueError(f"a frame of shape {array.shape}")
    return array


def eight_bit(array, np):
    """The 0.5-99.5 percentile 8-bit reduction LEAKAGE.md's pixel key is taken over."""
    low, high = np.percentile(array, [0.5, 99.5])
    if not high > low:
        return np.zeros(array.shape, dtype=np.uint8)
    scaled = np.clip((array - low) * (255.0 / (high - low)), 0.0, 255.0)
    return np.rint(scaled).astype(np.uint8)


def reduce_frame(data):
    """The pixel key, the perceptual hash and the NCC64 reduction of one frame's bytes."""
    np, Image = imaging()
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        eight = eight_bit(grey_array(image, np), np)
    height, width = eight.shape
    pixel_key = hashlib.sha256(f"{height}x{width}\n".encode() + eight.tobytes()).hexdigest()
    reduced = Image.fromarray(eight)
    box = Image.Resampling.BOX
    small = reduced.resize((HASH_REDUCTION, HASH_REDUCTION), box).tobytes()
    ncc64 = reduced.resize((leaks.NCC_SIDE, leaks.NCC_SIDE), box).tobytes()
    return {"pixel_key": pixel_key, "phash": f"{leaks.phash(small, HASH_REDUCTION):016x}",
            "ncc64": base64.b64encode(ncc64).decode("ascii")}


def fingerprint_frame(task):
    """One frame's line: its keys, or the reason none could be taken. The reason names the
    error's kind and never its text, which can carry a memory address and change the bytes."""
    shard_dir, path, sha256, person, source = task
    row = {"record": "frame", "frame": path, "person": person, "source": source}
    try:
        data = (Path(shard_dir) / path).read_bytes()
    except OSError as error:
        return {**row, "error": f"unreadable ({type(error).__name__})"}
    if hashlib.sha256(data).hexdigest() != sha256:
        return {**row, "error": "the bytes do not match the manifest's sha256"}
    try:
        keys = reduce_frame(data)
    except Exception as error:  # Pillow raises many kinds for a broken frame; each is a failure
        return {**row, "error": f"cannot decode ({type(error).__name__})"}
    return {**row, "store_key": sha256, **keys}


def read_manifest(shard_dir):
    path = Path(shard_dir) / MANIFEST
    try:
        manifest, digest = catalog_tool.load_manifest(path)
    except catalog_tool.CatalogError as error:
        raise LeakError(str(error)) from error
    return manifest, digest


def header_of(path):
    """The first line of a fingerprint file, or None where there is no readable one."""
    try:
        with open(path, encoding="utf-8") as handle:
            return json.loads(handle.readline())
    except (OSError, ValueError):
        return None


def up_to_date(out, digest):
    header = header_of(out)
    return bool(header and header.get("manifest_sha256") == digest
                and header.get("fingerprint_version") == FINGERPRINT_VERSION
                and header.get("errors") == 0)


def write_atomically(out, text):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    handle, staging = tempfile.mkstemp(dir=out.parent, prefix=f".{out.name}-")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.chmod(staging, 0o644)
        os.replace(staging, out)
    except BaseException:
        Path(staging).unlink(missing_ok=True)
        raise


def line(record):
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def parts_folder(out, digest):
    """Where a task keeps the chunks it has finished, by version and manifest, so a chunk of
    another manifest or of an older fingerprint is never taken for this one's."""
    return Path(f"{out}.parts") / f"v{FINGERPRINT_VERSION}-{digest}"


def chunk_path(folder, number):
    return Path(folder) / f"{number:06d}.jsonl"


def finished_chunk(path, tasks):
    """The rows of a chunk an earlier attempt finished, or None where it is to be done (again):
    no file, a file that does not read, other frames than these, or a frame that failed, which
    a requeue or a second run tries again."""
    try:
        rows = [json.loads(text) for text in Path(path).read_text(encoding="utf-8").splitlines()]
    except (OSError, ValueError):
        return None
    if [row.get("frame") for row in rows] != [task[1] for task in tasks]:
        return None
    if any("error" in row for row in rows):
        return None
    return rows


def computed(chunks, pending, pool):
    """The rows of each pending chunk in turn, the frames spread over the pool's processes in
    the manifest's order, which imap keeps."""
    tasks = (task for number in pending for task in chunks[number])
    rows = map(fingerprint_frame, tasks) if pool is None else pool.imap(fingerprint_frame, tasks, chunksize=16)
    for number in pending:
        yield [next(rows) for _ in chunks[number]]


def fingerprint_rows(shard_dir, manifest, folder, workers):
    """Every frame's line, in the manifest's order by path, and how many chunks an earlier
    attempt had already finished. Each chunk is written atomically as it fills, so a requeued
    task starts where its last finished chunk ends."""
    tasks = [(str(shard_dir), item.path, item.sha256, item.person, manifest.source)
             for item in sorted(manifest.items, key=lambda item: item.path)]
    chunks = [tasks[k:k + CHUNK_FRAMES] for k in range(0, len(tasks), CHUNK_FRAMES)]
    done = {number: finished_chunk(chunk_path(folder, number), chunk) for number, chunk in enumerate(chunks)}
    pending = [number for number, rows in done.items() if rows is None]
    pool = None if workers <= 1 or not pending else multiprocessing.get_context("fork").Pool(workers)
    try:
        for number, rows in zip(pending, computed(chunks, pending, pool)):
            write_atomically(chunk_path(folder, number), "".join(line(r) + "\n" for r in rows))
            done[number] = rows
    finally:
        if pool is not None:
            pool.terminate()
            pool.join()
    return [row for number in range(len(chunks)) for row in done[number]], len(chunks) - len(pending)


def fingerprint(shard_dir, out, workers):
    """Write one shard's fingerprint file; the answer is a line for the log. numpy and Pillow are
    asked for first, so a step run in an environment without them stops with that reason and
    never writes a file of frames that all failed to decode. The chunks a requeued attempt left
    are taken up, and removed once the whole file is written with no failed frame; with one,
    they stay, so the next run decodes only the chunks that failed."""
    try:
        imaging()
    except ImportError as error:
        raise LeakError(f"the fingerprint needs numpy and Pillow (the train-cpu environment): {error}") from error
    manifest, digest = read_manifest(shard_dir)
    if up_to_date(out, digest):
        return {"shard": manifest.name, "outcome": "already there", "frames": len(manifest.items), "errors": 0}
    folder = parts_folder(out, digest)
    folder.mkdir(parents=True, exist_ok=True)
    rows, resumed = fingerprint_rows(shard_dir, manifest, folder, workers)
    errors = sum(1 for row in rows if "error" in row)
    header = {"record": "shard", "shard": manifest.name, "source": manifest.source,
              "kind": manifest.kind.value, "supersedes": manifest.supersedes,
              "manifest_sha256": digest, "fingerprint_version": FINGERPRINT_VERSION,
              "frames": len(rows), "errors": errors}
    write_atomically(out, "".join(line(r) + "\n" for r in [header, *rows]))
    if not errors:
        shutil.rmtree(folder.parent, ignore_errors=True)
    return {"shard": manifest.name, "outcome": "written", "frames": len(rows), "errors": errors,
            "chunks_resumed": resumed}


# --- join --------------------------------------------------------------------------------------


def expand(patterns):
    """The fingerprint files the arguments name, each a path or a glob, sorted and each once."""
    files = set()
    for pattern in patterns:
        matched = glob.glob(pattern)
        files.update(matched if matched else [pattern])
    return sorted(files)


def read_file(path, keep):
    """A fingerprint file's header and its frame lines, each frame line passed through keep as it
    is read, so a file's text is never held whole; a LeakError where it cannot be read whole."""
    try:
        with open(path, encoding="utf-8") as handle:
            header = json.loads(handle.readline() or "null")
            named = isinstance(header, dict) and all(isinstance(header.get(k), str) for k in ("shard", "manifest_sha256"))
            if not named or header.get("record") != "shard":
                raise LeakError(f"{path}: no header line")
            frames = [keep(frame_line(text)) for text in handle]
    except (OSError, ValueError) as error:
        raise LeakError(f"{path}: not a readable fingerprint file ({type(error).__name__})") from error
    if header.get("fingerprint_version") != FINGERPRINT_VERSION or len(frames) != header.get("frames"):
        raise LeakError(f"{path}: version {header.get('fingerprint_version')}, {len(frames)} of"
                        f" {header.get('frames')} frames")
    return header, frames


def frame_line(text):
    """One frame line, which names at least the frame, its person and its source."""
    row = json.loads(text)
    if not isinstance(row, dict) or not all(isinstance(row.get(k), str) for k in ("frame", "person", "source")):
        raise ValueError("a frame line without its frame, person and source")
    return row


class Inputs:
    """Every fingerprint file read, with the problems that make the join fail before any check."""

    def __init__(self):
        self.headers, self.frames, self.problems, self.dropped = {}, {}, [], []
        # Every frame's 64 x 64 reduction, end to end in one buffer, a frame's row naming its
        # slot: about 4 KB a frame where the base64 text and its object were three times that,
        # and one object the scoring processes read without writing to its pages.
        self.reductions = bytearray()

    def kept(self, row):
        """A frame line as the join holds it: its reduction moved into the buffer, or, where a
        key is missing or malformed, a line with that reason and no keys, which the checks count
        as a frame never fingerprinted, since unknown is not clean."""
        if "error" in row:
            return row
        try:
            reduction = base64.b64decode(row.get("ncc64", ""), validate=True)
        except ValueError:
            reduction = b""
        whole = all(isinstance(row.get(key), str) for key in KEYS)
        if not whole or len(reduction) != REDUCTION_BYTES or not PHASH_TEXT.fullmatch(row["phash"]):
            bare = {key: value for key, value in row.items() if key not in KEYS}
            return {**bare, "error": "a fingerprint line with a key missing or malformed"}
        slot = len(self.reductions) // REDUCTION_BYTES
        self.reductions += reduction
        return {**{key: value for key, value in row.items() if key != "ncc64"}, "slot": slot}

    def add(self, path):
        start = len(self.reductions)
        try:
            header, frames = read_file(path, self.kept)
        except LeakError as error:
            self.problems.append(str(error))
            del self.reductions[start:]
            return
        shard = header["shard"]
        known = self.headers.get(shard)
        if known and known["manifest_sha256"] != header["manifest_sha256"]:
            self.problems.append(f"{path}: a second fingerprint of {shard} for another manifest")
            del self.reductions[start:]
            return
        self.headers[shard] = {**header, "file": str(path)}
        self.frames[shard] = frames

    def drop_superseded(self):
        """A shard another input supersedes leaves the join, as it leaves the catalog."""
        superseded = {h["supersedes"] for h in self.headers.values() if h.get("supersedes")}
        for shard in sorted(superseded & set(self.headers)):
            self.dropped.append(shard)
            del self.headers[shard], self.frames[shard]


def check_expected(inputs, listing):
    """Every shard folder the run meant to cover has a fingerprint of its current manifest."""
    try:
        folders = [text.strip() for text in Path(listing).read_text(encoding="utf-8").splitlines() if text.strip()]
    except OSError as error:
        raise LeakError(f"{listing}: {error.strerror}") from error
    for folder in folders:
        try:
            manifest, digest = read_manifest(folder)
        except LeakError as error:
            inputs.problems.append(f"{folder}: {error}")
            continue
        header = inputs.headers.get(manifest.name)
        superseded = manifest.name in inputs.dropped
        if not superseded and header is None:
            inputs.problems.append(f"{folder}: no fingerprint of {manifest.name}")
        elif header is not None and header["manifest_sha256"] != digest:
            inputs.problems.append(f"{folder}: the fingerprint of {manifest.name} is for another manifest")


def load_declared(path):
    """The person classes and the source classes the declaration file joins, kept as two maps,
    so a person key spelled like a source can never join or split a source."""
    try:
        declared = leaks.DeclaredAliases.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
    except (OSError, ValueError) as error:
        raise LeakError(f"{path}: not a readable declaration ({type(error).__name__})") from error
    persons = leaks.alias_classes(tuple(tuple(a.persons) for a in declared.persons))
    sources = leaks.alias_classes(tuple(tuple(a.sources) for a in declared.sources))
    return persons, sources


class Prints:
    """The frames of the join in one order: the rules' prints, the frames no key was taken
    from, and where each print's NCC64 reduction is, for the second pass."""

    def __init__(self, inputs, split):
        self.prints, self.unknown, self.where = [], [], []
        test_persons, rule = split
        for shard in sorted(inputs.frames):
            for number, row in enumerate(inputs.frames[shard]):
                self.add(shard, number, row, catalog_tool.person_part(row["person"], test_persons, rule)[0].value)

    def add(self, shard, number, row, part):
        frame = f"{shard}/{row['frame']}"
        if "error" in row:
            self.unknown.append((frame, row["person"], row["source"], row["error"]))
            return
        self.prints.append(leaks.Print(frame, row["person"], part, row["source"], row["store_key"],
                                       row["pixel_key"], int(row["phash"], 16)))
        self.where.append((shard, row["slot"]))


_SHARED = {}
SCORE_CHUNK = 4096


def score_chunk(chunk):
    """The NCC64 of some pairs of slots, from the buffer and the moments the parent process set
    before forking; reading them copies none of their pages into this process."""
    view, sums, squares = memoryview(_SHARED["reductions"]), _SHARED["sums"], _SHARED["squares"]
    scores = []
    for a, b in chunk:
        first = bytes(view[a * REDUCTION_BYTES:(a + 1) * REDUCTION_BYTES])
        second = bytes(view[b * REDUCTION_BYTES:(b + 1) * REDUCTION_BYTES])
        scores.append(leaks.ncc_with(first, second, (sums[a], squares[a]), (sums[b], squares[b])))
    view.release()
    return scores


def share_moments(inputs, slots):
    """The sum and the sum of squares of each reduction the pairs need, in two flat arrays the
    forked processes only read."""
    count = len(inputs.reductions) // REDUCTION_BYTES
    sums, squares = array("q", bytes(8 * count)), array("q", bytes(8 * count))
    view = memoryview(inputs.reductions)
    for slot in slots:
        sums[slot], squares[slot] = leaks.moments(bytes(view[slot * REDUCTION_BYTES:(slot + 1) * REDUCTION_BYTES]))
    view.release()
    _SHARED.update(reductions=inputs.reductions, sums=sums, squares=squares)


def scored_chunks(chunks, workers):
    """The scores of each chunk in turn. The pool forks, so the buffer is shared with it, and
    the collector is frozen first, so a child's collection never writes to the parent's pages."""
    if workers <= 1 or len(chunks) <= 1:
        yield from map(score_chunk, chunks)
        return
    gc.freeze()
    try:
        with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("fork")) as pool:
            yield from pool.map(score_chunk, chunks)
    finally:
        gc.unfreeze()


def near_duplicates(prints, inputs, pairs, settings):
    """CHK-6's rows: each chunk of crossing pairs scored by NCC64 and handed to the gated rule as
    it comes, so the scores of twenty million pairs are never held at once."""
    slot_of = [slot for _, slot in prints.where]
    share_moments(inputs, sorted({slot_of[i] for i, _, _ in pairs} | {slot_of[j] for _, j, _ in pairs}))
    chunks = [pairs[k:k + SCORE_CHUNK] for k in range(0, len(pairs), SCORE_CHUNK)]
    slot_chunks = [[(slot_of[i], slot_of[j]) for i, j, _ in chunk] for chunk in chunks]
    every, rows = tuple(prints.prints), []
    for chunk, scores in zip(chunks, scored_chunks(slot_chunks, settings["workers"])):
        scored = tuple(leaks.Scored(i, j, d, ncc) for (i, j, d), ncc in zip(chunk, scores))
        rows.extend(leaks.near_duplicates(every, scored, settings["persons"]))
    _SHARED.clear()
    return tuple(rows)


def probes_of(prints, new):
    """The prints a join probes: every one, or those of the one new shard."""
    if new is None:
        return frozenset(range(len(prints.prints)))
    return frozenset(i for i, (shard, _) in enumerate(prints.where) if shard == new)


def new_shard_name(new):
    """A shard named by its name, or by its folder, whose manifest names it."""
    if new is None or "/" in new and not Path(new).is_dir():
        return new
    return read_manifest(new)[0].name


def crossing_pairs(prints, settings):
    """The candidate pairs whose two frames stand on two sides of the split, and whether the
    search passed its budget; a pair on one side is never scored, since no NCC could fail it."""
    codes = tuple(p.phash for p in prints.prints)
    pairs = leaks.candidate_pairs(codes, settings["distance"], probes_of(prints, settings["new"]),
                                  settings["max_pairs"])
    over = len(pairs) > settings["max_pairs"]
    return leaks.crossing(tuple(prints.prints), pairs, settings["persons"]), len(pairs), over


def run_checks(prints, inputs, settings):
    crossing, candidates, over = crossing_pairs(prints, settings)
    if over:
        inputs.problems.append(f"the candidate search passed its budget of {settings['max_pairs']} pairs"
                               " within the distance, so CHK-6 did not finish; a smaller --distance or a"
                               " larger --max-pairs, decided by a person, runs it again")
        crossing = ()
    findings = (near_duplicates(prints, inputs, crossing, settings)
                + leaks.shared_keys(tuple(prints.prints), settings["persons"], settings["sources"])
                + leaks.unfingerprinted(tuple(prints.unknown)))
    return findings, {"candidate_pairs": candidates, "crossing_pairs": len(crossing)}


def concerns_new(finding, new):
    """Whether a row belongs in a check of one new shard: a row that ties one of its frames, or a
    frame of any shard that was never fingerprinted, which leaves every comparison incomplete."""
    return (new is None or finding.check == leaks.UNKNOWN
            or any(frame.startswith(new + "/") for frame in finding.frames))


def report(inputs, prints, findings, searched, settings):
    counts = leaks.counts(findings)
    failed = leaks.verdict(findings) == leaks.FAIL or bool(inputs.problems)
    return {
        "verdict": leaks.FAIL if failed else leaks.PASS,
        "counts": {**counts, "input_problems": len(inputs.problems)},
        "settings": {"distance": settings["distance"], "ncc_min": leaks.NCC_MIN, "bands": leaks.BANDS,
                     "new": settings["new"], "max_pairs": settings["max_pairs"],
                     "fingerprint_version": FINGERPRINT_VERSION},
        "frames": len(prints.prints) + len(prints.unknown), **searched,
        "inputs": [{k: h[k] for k in ("shard", "manifest_sha256", "frames", "errors", "file")}
                   for _, h in sorted(inputs.headers.items())],
        "superseded_dropped": inputs.dropped, "input_problems": inputs.problems,
        "rows": [dataclasses.asdict(f) for f in findings],
    }


def page(result):
    """LEAKS.md: the verdict, the counts and the first rows, for a person reading the log."""
    out = [f"# Leak checks: {result['verdict']}", "",
           f"{result['frames']} frames in {len(result['inputs'])} shards; {result['candidate_pairs']}"
           f" candidate pairs within perceptual-hash distance {result['settings']['distance']},"
           f" {result['crossing_pairs']} of them across the split and scored, confirmed at"
           f" NCC64 >= {result['settings']['ncc_min']}.", "",
           "| check | failing rows |", "|---|---|"]
    out += [f"| {name} | {n} |" for name, n in result["counts"].items()]
    if result["input_problems"]:
        out += ["", "## Input problems", ""] + [f"- {p}" for p in result["input_problems"]]
    out += ["", f"## Rows (the first {ROWS_IN_PAGE}; LEAKS.json has every one)", "",
            "| check | reason | frames | persons | parts | key or scores |", "|---|---|---|---|---|---|"]
    for row in result["rows"][:ROWS_IN_PAGE]:
        scores = row["key"] or (f"distance {row['distance']}, NCC64 {row['ncc']:.4f}"
                                if row["ncc"] is not None else "none taken")
        out.append(f"| {row['check']} | {row['reason']} | {', '.join(row['frames'])} | {', '.join(row['persons'])}"
                   f" | {', '.join(row['parts'])} | {scores} |")
    return "\n".join(out) + "\n"


def join(args):
    inputs = Inputs()
    for path in expand(args.fingerprints):
        inputs.add(path)
    inputs.drop_superseded()
    if args.expect:
        check_expected(inputs, args.expect)
    test_persons, rule, _ = catalog_tool.load_split(args.test_persons, args.rule)
    persons, sources = load_declared(args.declared)
    settings = {"persons": persons, "sources": sources, "distance": args.distance,
                "new": new_shard_name(args.new), "max_pairs": args.max_pairs, "workers": args.workers}
    if settings["new"] is not None and settings["new"] not in inputs.headers:
        inputs.problems.append(f"the new shard {settings['new']} has no fingerprint among the inputs")
    prints = Prints(inputs, (test_persons, rule))
    findings, searched = run_checks(prints, inputs, settings)
    findings = tuple(f for f in findings if concerns_new(f, settings["new"]))
    result = report(inputs, prints, findings, searched, settings)
    write_atomically(Path(args.out) / LEAKS_JSON, json.dumps(result, indent=1, sort_keys=True) + "\n")
    write_atomically(Path(args.out) / LEAKS_MD, page(result))
    return result


def distance(text):
    value = int(text)
    if not 0 <= value <= leaks.HASH_BITS:
        raise argparse.ArgumentTypeError("a distance from 0 to 64")
    return value


def parser():
    top = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = top.add_subparsers(dest="command", required=True)
    fp = sub.add_parser("fingerprint", help="one shard's fingerprint file")
    fp.add_argument("--shard", required=True, help="the shard's folder, which holds MANIFEST.json")
    fp.add_argument("--out", required=True, help="the fingerprint file to write")
    fp.add_argument("--workers", type=int, default=int(os.environ.get("SLURM_CPUS_PER_TASK", "1")))
    jn = sub.add_parser("join", help="CHK-6 and CHK-7 over every fingerprint")
    jn.add_argument("--fingerprints", nargs="+", required=True, help="files or globs")
    jn.add_argument("--out", required=True, help="the folder LEAKS.json and LEAKS.md go to")
    jn.add_argument("--expect", default=None, help="the shard folders the run meant to cover, one a line")
    jn.add_argument("--declared", default=str(DECLARED), help="the declared aliases")
    jn.add_argument("--new", default=None, help="probe only this shard (its name or its folder)")
    jn.add_argument("--distance", type=distance, default=leaks.DEFAULT_DISTANCE)
    jn.add_argument("--max-pairs", type=int, default=MAX_PAIRS,
                    help="the candidate pairs the search may hold before it stops and the join fails")
    jn.add_argument("--workers", type=int, default=int(os.environ.get("SLURM_CPUS_PER_TASK", "1")))
    jn.add_argument("--test-persons", default=str(catalog_tool.TEST_PERSONS))
    jn.add_argument("--rule", default=str(catalog_tool.RULE))
    return top


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "fingerprint":
            answer = fingerprint(Path(args.shard), Path(args.out), args.workers)
            print(json.dumps(answer, sort_keys=True))
            return 2 if answer["errors"] else 0
        result = join(args)
        print(json.dumps({k: result[k] for k in ("verdict", "counts", "frames", "candidate_pairs", "crossing_pairs")},
                         sort_keys=True))
        return 1 if result["verdict"] == leaks.FAIL else 0
    except (LeakError, catalog_tool.CatalogError, ValidationError, OSError) as error:
        print(f"leaks: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
