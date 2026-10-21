"""Freeze the witness frames from a catalog, check them against another, and draw them.

Usage:
    python3 tools/witness.py freeze --catalog <catalog.sqlite> --out <witness.json>
    python3 tools/witness.py check --witness <witness.json> --catalog <catalog.sqlite>

The choosing rules are schwingnet.witness (proven by the gate); this file reads the catalog and
writes the frozen list, and holds the drawing the trainer and the evaluator share. A witness list
is chosen once, from the first real catalog, and committed as data/witness/witness.json by the
pull request that records that run (tools/flow.py record), so every later run, on every later
catalog version, draws the same frames; a catalog that no longer holds a frozen frame, or holds
it in another part, is refused rather than quietly drawing others. Reading and freezing need the
standard library alone; drawing needs Pillow, so it is imported only where a frame is drawn.

A drawn frame is the whole frame, every labelled body boxed, and beside each box the true name
and the predicted one, green where they agree and red where they do not, with the checkpoint and
the frame's score in a band above it. Over the checkpoints each frame gets a strip (the epochs
side by side, the untrained network first) and an animation, the video per frame of the plan.
"""

import argparse
import json
import sqlite3
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from schwingnet.witness import Candidate, WitnessRule, choose  # noqa: E402

FROZEN = ROOT / "data" / "witness" / "witness.json"
SCHEMA = 1
FRAMES_SQL = """
SELECT i.sha256, i.person, i.part, i.source, i.path, s.manifest, group_concat(l.level, ',') AS levels
FROM item i
JOIN shard s ON s.name = i.shard
JOIN label l ON l.item = i.sha256 AND l.shard = i.shard
GROUP BY i.shard, i.sha256
ORDER BY i.sha256, i.shard
"""
GOOD, BAD, INK, PAPER = (40, 170, 60), (210, 40, 40), (255, 255, 255), (20, 20, 20)
BAND = 22


class WitnessError(Exception):
    """What stops the witness step with a reason a person reads."""


def read_candidates(catalog):
    """Every labelled frame of the catalog once, with its levels and its file's path."""
    db = sqlite3.connect(f"file:{catalog}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        rows = db.execute(FRAMES_SQL).fetchall()
    finally:
        db.close()
    seen, out = set(), []
    for row in rows:
        if row["sha256"] in seen:
            continue
        seen.add(row["sha256"])
        frame = Path(row["manifest"]).parent / row["path"]
        levels = tuple(sorted(set(row["levels"].split(","))))
        out.append(Candidate(row["sha256"], row["person"], row["part"], row["source"], levels, str(frame)))
    return tuple(out)


def freeze(catalog, catalog_sha256, rule=None):
    """The witness document for a catalog: the rule, every frame with its role, what is missing."""
    rule = rule or WitnessRule()
    picked, missing = choose(read_candidates(catalog), rule)
    frames = [dict(key=key_of(role, n, c.sha256), role=role, **asdict(c)) for n, (role, c) in enumerate(picked)]
    for frame in frames:
        frame["levels"] = list(frame["levels"])
    return {"schema": SCHEMA, "rule": asdict(rule), "chosen_from_catalog": catalog_sha256, "frames": frames, "missing": list(missing)}


def key_of(role, n, sha):
    return f"{role}-{n:02d}-{sha[:8]}"


def check(document, catalog):
    """The frozen frames as this catalog holds them, with their paths on this catalog's volume.

    A frame the catalog lost, or holds in another part, is refused: the witness frames are the
    same frames at every version, or the page compares nothing.
    """
    if document.get("schema") != SCHEMA:
        raise WitnessError(f"witness list schema {document.get('schema')}, not {SCHEMA}")
    here = {c.sha256: c for c in read_candidates(catalog)}
    lost = [f["key"] for f in document["frames"] if f["sha256"] not in here or here[f["sha256"]].part != f["part"]]
    if lost:
        raise WitnessError(f"the catalog no longer holds {len(lost)} frozen witness frames in their part: {', '.join(lost[:6])}")
    frames = [dict(f, path=here[f["sha256"]].path) for f in document["frames"]]
    return dict(document, frames=frames)


def for_run(catalog, catalog_sha256):
    """The witness list a run draws: the frozen one where the repository has it, else chosen now."""
    if FROZEN.is_file():
        return check(json.loads(FROZEN.read_text(encoding="utf-8")), catalog), "frozen"
    return freeze(catalog, catalog_sha256), "chosen"


def of_roles(document, roles):
    return [f for f in document["frames"] if f["role"] in roles]


def _font():
    from PIL import ImageFont

    try:
        return ImageFont.load_default(size=13)
    except TypeError:
        return ImageFont.load_default()


def draw_frame(path, marks, heading, height=320):
    """One frame with every body boxed and named: marks are (unit box, truth, guess) triples."""
    from PIL import Image, ImageDraw

    frame = Image.open(path).convert("RGB")
    scale = height / frame.height
    frame = frame.resize((max(1, round(frame.width * scale)), height), Image.BILINEAR)
    canvas = Image.new("RGB", (frame.width, height + BAND), PAPER)
    canvas.paste(frame, (0, BAND))
    pen, font = ImageDraw.Draw(canvas), _font()
    for (x0, y0, x1, y1), truth, guess in marks:
        colour = GOOD if truth == guess else BAD
        box = (x0 * frame.width, BAND + y0 * height, x1 * frame.width, BAND + y1 * height)
        pen.rectangle(box, outline=colour, width=2)
        label = truth if truth == guess else f"{truth}>{guess}"
        pen.text((box[2] + 3, box[1]), label, fill=colour, font=font)
    pen.text((4, 4), heading, fill=INK, font=font)
    return canvas


def score_of(marks):
    return sum(1 for _, truth, guess in marks if truth == guess), len(marks)


def draw_checkpoint(frames, marks_by_sha, epoch, folder):
    """Every witness frame at one checkpoint, one file each; returns each frame's score."""
    scores = {}
    for frame in frames:
        marks = marks_by_sha.get(frame["sha256"], [])
        right, total = score_of(marks)
        heading = f"epoch {epoch}  {frame['role']}  {right}/{total}"
        image = draw_frame(frame["path"], marks, heading)
        target = Path(folder) / frame["key"]
        target.mkdir(parents=True, exist_ok=True)
        image.save(target / f"epoch-{epoch:02d}.png")
        scores[frame["key"]] = [right, total]
    return scores


def _epochs(folder):
    return sorted(Path(folder).glob("epoch-*.png"))


def strip_and_animation(folder, thumb=160, columns=11):
    """strip.png (the untrained frame, then evenly spaced epochs to the last) and anim.gif (all)."""
    from PIL import Image

    files = _epochs(folder)
    if not files:
        return
    shots = [Image.open(f).convert("RGB") for f in files]
    small = [s.resize((max(1, round(s.width * thumb / s.height)), thumb), Image.BILINEAR) for s in shots]
    picks = sorted({0, len(small) - 1, *(round(n * (len(small) - 1) / max(1, columns - 1)) for n in range(columns))})
    width = sum(small[i].width for i in picks) + 2 * (len(picks) - 1)
    strip = Image.new("RGB", (width, thumb), PAPER)
    x = 0
    for i in picks:
        strip.paste(small[i], (x, 0))
        x += small[i].width + 2
    strip.save(Path(folder) / "strip.png")
    frames = [s.quantize(colors=32) for s in small]
    durations = [700] * (len(frames) - 1) + [2000]
    frames[0].save(Path(folder) / "anim.gif", save_all=True, append_images=frames[1:], duration=durations, loop=0)


def sheet(folder, frames, epoch, out, thumb=200, columns=6):
    """All witness frames at one checkpoint on one page, for W&B and the docs page."""
    from PIL import Image

    tiles = []
    for frame in frames:
        path = Path(folder) / frame["key"] / f"epoch-{epoch:02d}.png"
        if path.is_file():
            image = Image.open(path).convert("RGB")
            tiles.append(image.resize((max(1, round(image.width * thumb / image.height)), thumb), Image.BILINEAR))
    if not tiles:
        return None
    cell = max(t.width for t in tiles) + 4
    rows = -(-len(tiles) // columns)
    page = Image.new("RGB", (cell * min(columns, len(tiles)), (thumb + 4) * rows), PAPER)
    for n, tile in enumerate(tiles):
        page.paste(tile, ((n % columns) * cell, (n // columns) * (thumb + 4)))
    page.save(out)
    return out


def finish(folder, frames, epochs):
    """The strips and animations of every frame, and the first and last sheets."""
    for frame in frames:
        strip_and_animation(Path(folder) / frame["key"])
    for epoch in sorted({epochs[0], epochs[-1]}):
        sheet(folder, frames, epoch, Path(folder) / f"sheet-epoch-{epoch:02d}.png")


def parse(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    f = sub.add_parser("freeze")
    f.add_argument("--catalog", required=True)
    f.add_argument("--out", required=True)
    c = sub.add_parser("check")
    c.add_argument("--witness", default=str(FROZEN))
    c.add_argument("--catalog", required=True)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse(argv)
    try:
        if args.command == "freeze":
            import hashlib

            digest = hashlib.sha256(Path(args.catalog).read_bytes()).hexdigest()
            document = freeze(args.catalog, digest)
            Path(args.out).write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
            print(json.dumps({"frames": len(document["frames"]), "missing": document["missing"]}))
        else:
            document = check(json.loads(Path(args.witness).read_text(encoding="utf-8")), args.catalog)
            print(json.dumps({"frames": len(document["frames"]), "held": True}))
    except (WitnessError, sqlite3.Error, OSError) as error:
        print(f"witness: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
