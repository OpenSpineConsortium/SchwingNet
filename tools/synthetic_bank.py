"""Write a synthetic bank in the real X-ray builders' format, learnable enough for a dry run.

Usage: python3 tools/synthetic_bank.py <bank> --frames N --cases N [--seed S] [--test-cases a,b]
    [--map-share 0.75]

The bank has the layout tools/ingest.py reads (images/<split>/<stem>.png, meta/<stem>.json with
the case, the device, the view and the boxes), so the dry run of the flow exercises the same
ingest, catalog, split check, trainer and evaluator the grid runs, on bytes that hold nothing
of any person. Each box is a vertebra drawn as a bright rectangle with as many dark bars as
its level's index among the levels below, over noise, so a trainer that reads the crops can
learn the level and a trainer that reads nothing scores chance: a dry run whose accuracy stays
at chance is a broken workflow, not a hard dataset. Every frame's bytes differ, and a few frames
repeat an earlier frame's bytes of the same case under another stem, which the ingest must count as duplicates.
A share of the frames (--map-share, a seeded draw at 0.75 unless said otherwise) bring a projected level
map as a render's frame would (#228): maps/<stem>.png, each body's catalog level code over the
rectangle it fills and 0 elsewhere, named in the meta as level_map with level_map_from "render",
so the dry run exercises the trainer's prior block too and the rest of the frames exercise the
crops without a map; which frames is drawn from a generator of its own, so a seed's frames and
metas are what they were before maps existed and the recorded dry runs' banks come out again.
Standard library only, so it runs where the verification environment runs.
"""

import argparse
import json
import random
import struct
import zlib
from pathlib import Path

LEVELS = ("T11", "T12", "L1", "L2", "L3", "L4", "L5", "sacrum")
# The catalog's 27 levels in schwingnet.catalog.LEVELS' order, so a map's byte 1 to 27 is the code
# the catalog gives that level; a copy, since this tool imports nothing of the package, held equal
# to the package's list by tests/schwingnet/test_flow.py.
CATALOG_LEVELS = (
    *(f"C{i}" for i in range(1, 8)),
    *(f"T{i}" for i in range(1, 14)),
    *(f"L{i}" for i in range(1, 7)),
    "sacrum",
)
WIDTH, HEIGHT = 256, 192
BODY = 28
MAP_SHARE = 0.75


def png(rows):
    """A greyscale 8-bit PNG from rows of pixel values."""
    raw = bytearray()
    for row in rows:
        raw.append(0)
        raw.extend(row)

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", len(rows[0]), len(rows), 8, 0, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(raw)))
        + chunk(b"IEND", b"")
    )


def draw_body(rows, box, level_index):
    """A bright vertebral body with level_index dark bars across it."""
    x0, y0, x1, y1 = (int(v) for v in box)
    for y in range(y0, y1):
        for x in range(x0, x1):
            rows[y][x] = min(255, rows[y][x] + 120)
    bars = level_index + 1
    for bar in range(bars):
        y = y0 + 2 + int((y1 - y0 - 4) * (bar + 0.5) / bars)
        for x in range(x0 + 2, x1 - 2):
            rows[y][x] = max(0, rows[y][x] - 100)


def frame_rows(rnd, boxes):
    """A frame: noise, the bodies drawn, and a slow gradient so no two frames share bytes."""
    offset = rnd.randrange(0, 40)
    rows = [[rnd.randrange(40, 110) + (y + offset) // 8 for _ in range(WIDTH)] for y in range(HEIGHT)]
    for box, level in boxes:
        draw_body(rows, box, LEVELS.index(level))
    return rows


def map_rows(boxes):
    """The frame's projected level map: each body's catalog code over the rectangle it fills but
    its outermost pixel, 0 elsewhere, as a segmented CT's levels fall on the frame; a map's values
    are the catalog's codes, 1 to 27, whatever the bank calls the level in its boxes."""
    rows = [[0] * WIDTH for _ in range(HEIGHT)]
    for box, level in boxes:
        x0, y0, x1, y1 = (int(v) for v in box)
        code = CATALOG_LEVELS.index(level) + 1
        for y in range(y0 + 1, y1 - 1):
            for x in range(x0 + 1, x1 - 1):
                rows[y][x] = code
    return rows


def boxes_for(rnd):
    """A column of consecutive levels down the frame, as a lateral view shows them."""
    first = rnd.randrange(0, len(LEVELS) - 2)
    count = rnd.randrange(3, min(6, len(LEVELS) - first) + 1)
    x = rnd.uniform(60, WIDTH - 60 - BODY)
    y = rnd.uniform(4, 20)
    boxes = []
    for level in LEVELS[first : first + count]:
        x += rnd.uniform(-3, 3)
        boxes.append(([x, y, x + BODY + rnd.uniform(-2, 4), y + BODY - 4 + rnd.uniform(-2, 4)], level))
        y += BODY
    return boxes


def meta_for(case, index, split, boxes, rnd, level_map=None):
    """The frame's meta in the builders' shape; a tenth of the levels are left null, and a frame
    with a level map names it as the ingest reads it (tools/ingest.py)."""
    named = {} if level_map is None else {"level_map": level_map, "level_map_from": "render"}
    return {
        **named,
        "dataset": "synthetic",
        "case": case,
        "frame": f"f{index:06d}",
        "split": split,
        "device": {
            "make": "Synthetic",
            "model": "Dry run",
            "detector": "flat panel",
            "kvp": rnd.choice([62.0, 70.0, 73.0, 81.0]),
            "mas": round(rnd.uniform(1, 4), 2),
        },
        "px_mm": 0.3,
        "view": {"gantry_deg": rnd.uniform(-20, 20), "lat_from_ap_deg": 90.0},
        "boxes": [
            {
                "cls": 0,
                "level": level if rnd.random() > 0.1 else None,
                "box": box,
                "visible_frac": 1.0,
                "px": 100,
            }
            for box, level in boxes
        ],
        "label_source": "synthetic",
    }


def write_bank(bank, frames, cases, seed, test_cases, map_share=MAP_SHARE):
    """Write the bank and return its counts; map_share of the frames bring a level map."""
    rnd = random.Random(seed)
    map_rnd = random.Random(f"maps-{seed}")
    for split in ("train", "val", "test"):
        (bank / "images" / split).mkdir(parents=True, exist_ok=True)
    (bank / "meta").mkdir(exist_ok=True)
    (bank / "maps").mkdir(exist_ok=True)
    maps = 0
    # A repeat copies an earlier frame of the same case: the ingest counts that as a duplicate,
    # while the same bytes under two persons it refuses as an identity question (tools/ingest.py).
    last = {}
    for index in range(frames):
        case = test_cases[index % len(test_cases)] if test_cases else f"case{1000 + index % cases}"
        split = "test" if test_cases else ("val" if index % 10 == 7 else "train")
        stem = f"{case}_f{index:06d}"
        boxes = boxes_for(rnd)
        data = last[case] if (index % 97 == 50 and case in last) else png(frame_rows(rnd, boxes))
        (bank / "images" / split / f"{stem}.png").write_bytes(data)
        level_map = None
        if map_rnd.random() < map_share:
            level_map = f"maps/{stem}.png"
            (bank / level_map).write_bytes(png(map_rows(boxes)))
            maps += 1
        (bank / "meta" / f"{stem}.json").write_text(
            json.dumps(meta_for(case, index, split, boxes, rnd, level_map)), encoding="utf-8"
        )
        last[case] = data
    return {"bank": str(bank), "frames": frames, "cases": cases or len(test_cases), "maps": maps}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("bank", type=Path)
    parser.add_argument("--frames", type=int, required=True)
    parser.add_argument("--cases", type=int, default=0)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--test-cases", default="", help="comma-separated; every frame is theirs")
    parser.add_argument("--map-share", type=float, default=MAP_SHARE, help="the share of frames with a level map, 0 to 1")
    args = parser.parse_args(argv)
    test_cases = [c for c in args.test_cases.split(",") if c]
    if not test_cases and args.cases < 1:
        parser.error("--cases is needed unless --test-cases names the cases")
    if not 0.0 <= args.map_share <= 1.0:
        parser.error("--map-share is a share, 0 to 1")
    print(json.dumps(write_bank(args.bank, args.frames, args.cases, args.seed, test_cases, args.map_share)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
