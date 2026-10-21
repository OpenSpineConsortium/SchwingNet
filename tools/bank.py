"""Turn a raw copy of a dataset into a bank tools/ingest.py reads, by a recipe.

A bank is the real X-ray builders' format: `images/<split>/<stem>.png` and `meta/<stem>.json`
with the case, the device, the view and the boxes with their level names. A raw copy is whatever
the publisher shipped. The recipe, one file grid/banks/<id>.json per source, says where the
images are (glob patterns under raw/), their format, how the person key is read (a regex over
the relative path with a named group `case`, or a column of a CSV keyed by the path), the view,
the device and modality constants, the split, and whether a label file exists and in what shape.
A field spelled "to confirm" stops the conversion with the field's name, so a job never guesses
what a person has not read on the page; every unknown of a recipe written before the files were
seen is spelled that way on purpose.

    python3 tools/bank.py --recipe grid/banks/nih_chestxray14.json            # plan: counts, writes nothing
    python3 tools/bank.py --recipe grid/banks/nih_chestxray14.json --run      # write the bank
    python3 tools/bank.py --recipe R --raw <dir> --bank <dir>                  # another root, for a test

The conversion is deterministic (the files in path order, one stem per relative path, the meta
with sorted keys) and writes only under the recipe's bank folder: a file already there with the
same bytes is left, one with other bytes is refused, and nothing is ever deleted, so a changed
raw copy is a person's decision and a rerun is idempotent. PNG is copied byte for byte (the
ingest hashes the bytes, so a copy keeps the shard's name stable). JPEG, TIFF and BMP are read
through Pillow where it can be imported (the train environment, `pixi run -e train-cpu`), and
refused with the way to get it otherwise; DICOM is refused until pydicom is in pixi.lock, since
no new dependency enters without a change that locks it. Standard library only, Pillow optional.
"""

import argparse
import csv
import hashlib
import io
import json
import re
import struct
import sys
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
TO_CONFIRM = "to confirm"
REQUIRED = ("id", "raw", "bank", "images", "format", "person", "view", "device", "split", "labels")
FORMATS = ("png", "jpg", "jpeg", "tif", "tiff", "bmp", "dcm")
PILLOW_FORMATS = ("jpg", "jpeg", "tif", "tiff", "bmp")


class BankError(Exception):
    """A recipe, a raw copy or a bank folder this tool refuses, with the reason a person reads."""


def unconfirmed(value, path=""):
    """Every field of a recipe still spelled 'to confirm', as dotted paths."""
    if isinstance(value, str):
        return [path] if value.strip().lower().startswith(TO_CONFIRM) else []
    if isinstance(value, dict):
        return [p for k, v in value.items() for p in unconfirmed(v, f"{path}.{k}" if path else k)]
    if isinstance(value, list):
        return [p for i, v in enumerate(value) for p in unconfirmed(v, f"{path}[{i}]")]
    return []


def load_recipe(path):
    recipe = json.loads(Path(path).read_text(encoding="utf-8"))
    missing = [key for key in REQUIRED if key not in recipe]
    if missing:
        raise BankError(f"{path}: no field {', '.join(missing)}")
    open_fields = unconfirmed({k: v for k, v in recipe.items() if k not in ("notes", "confirm")})
    if open_fields:
        raise BankError(f"{path}: still to confirm: {', '.join(open_fields)}; read the page and fill them in")
    if recipe["format"] not in FORMATS:
        raise BankError(f"{path}: format {recipe['format']!r} is none of {', '.join(FORMATS)}")
    return recipe


def image_paths(raw, patterns):
    """Every file under raw matching a pattern, relative to raw, in path order, each once."""
    raw = Path(raw)
    found = set()
    for pattern in patterns:
        for path in raw.glob(pattern):
            if path.is_file() and not any(part.startswith(".") for part in path.relative_to(raw).parts):
                found.add(path.relative_to(raw).as_posix())
    if not found:
        raise BankError(f"{raw}: no file matches {patterns}")
    return sorted(found)


def stem_of(relative):
    """One stem per relative path: the separators and anything a shell would quote become `_`."""
    text = re.sub(r"[^A-Za-z0-9_-]+", "_", relative.rsplit(".", 1)[0] if "." in Path(relative).name else relative)
    return text.strip("_") or hashlib.sha256(relative.encode()).hexdigest()[:12]


def csv_column(table, key_column, value_column):
    rows = {}
    with open(table, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            rows[row[key_column]] = row[value_column]
    return rows


class Persons:
    """The person key of a relative path, by the recipe's rule."""

    def __init__(self, rule, raw):
        self.regex = re.compile(rule["regex"]) if "regex" in rule else None
        self.table = None
        if "csv" in rule:
            self.table = csv_column(Path(raw) / rule["csv"], rule["path_column"], rule["person_column"])
            self.key = rule.get("key", "name")
        if self.regex is None and self.table is None:
            raise BankError("the person rule names neither a regex nor a csv")

    def of(self, relative):
        if self.regex is not None:
            match = self.regex.search(relative)
            if not match or not match.group("case"):
                raise BankError(f"{relative}: the person regex finds no case")
            return match.group("case")
        key = Path(relative).name if self.key == "name" else relative
        if key not in self.table:
            raise BankError(f"{relative}: not in the person table")
        return self.table[key]


def png_size(data):
    if len(data) < 24 or data[:8] != PNG_SIGNATURE or data[12:16] != b"IHDR":
        raise BankError("not a PNG")
    return struct.unpack(">II", data[16:24])


def pillow():
    try:
        from PIL import Image
    except ImportError as error:
        raise BankError("this format needs Pillow, which the default environment does not hold:"
                        " run the bank stage with PYDRV=<repo>/.pixi/envs/train-cpu/bin/python"
                        " (pixi install --locked -e train-cpu)") from error
    return Image


def as_png(data, image_format):
    """The frame's bytes as a PNG with its width and height; PNG passes through untouched."""
    if image_format == "png":
        width, height = png_size(data)
        return data, width, height
    if image_format == "dcm":
        raise BankError("DICOM sources need pydicom, which is not in pixi.lock; add it in a change of"
                        " its own that re-locks, then teach this tool to read the pixel array")
    image = pillow().open(io.BytesIO(data))
    if image.mode not in ("L", "I;16", "I"):
        image = image.convert("L")
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue(), image.width, image.height


class Labels:
    """The boxes of a frame from the recipe's label files, in the shape ingest reads."""

    def __init__(self, rule, raw):
        self.rule, self.raw = rule, Path(raw)
        self.rows = self.read_csv(rule) if rule and rule["kind"] in ("csv_boxes", "landmarks_csv") else {}

    def read_csv(self, rule):
        grouped = {}
        with open(self.raw / rule["csv"], encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                grouped.setdefault(row[rule["image_column"]], []).append(row)
        return grouped

    def of(self, relative, width, height):
        if not self.rule:
            return []
        kind = self.rule["kind"]
        if kind == "yolo":
            return self.yolo(relative, width, height)
        key = Path(relative).name if self.rule.get("key", "name") == "name" else relative
        rows = self.rows.get(key, [])
        if kind == "csv_boxes":
            return [self.box(row[self.rule["level_column"]], *(float(row[c]) for c in self.rule["box_columns"]))
                    for row in rows]
        return self.landmarks(rows)

    def landmarks(self, rows):
        """Landmarks of one body become its bounding box; the rows of one image hold one body each
        or one landmark each with a body column, which the recipe says."""
        bodies = {}
        for row in rows:
            level = row[self.rule["level_column"]]
            xs = [float(row[c]) for c in self.rule["x_columns"]]
            ys = [float(row[c]) for c in self.rule["y_columns"]]
            x0, y0, x1, y1 = bodies.get(level, (min(xs), min(ys), max(xs), max(ys)))
            bodies[level] = (min(x0, *xs), min(y0, *ys), max(x1, *xs), max(y1, *ys))
        return [self.box(level, *box) for level, box in sorted(bodies.items())]

    def yolo(self, relative, width, height):
        text = (self.raw / self.rule["labels_dir"] / (Path(relative).stem + ".txt"))
        if not text.is_file():
            return []
        boxes = []
        for line in text.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) < 5:
                continue
            cx, cy, w, h = (float(v) for v in parts[1:5])
            level = self.rule["classes"].get(parts[0])
            boxes.append(self.box(level, (cx - w / 2) * width, (cy - h / 2) * height,
                                  (cx + w / 2) * width, (cy + h / 2) * height))
        return boxes

    @staticmethod
    def box(level, x0, y0, x1, y1):
        return {"cls": 0, "level": level, "box": [x0, y0, x1, y1], "visible_frac": 1.0, "px": 100}


def meta_of(recipe, case, relative, boxes):
    device = dict(recipe["device"])
    return {
        "dataset": recipe["id"],
        "case": case,
        "source_path": relative,
        "split": recipe["split"],
        "device": {"make": device.get("make"), "model": device.get("model"), "detector": device.get("detector"),
                   "kvp": device.get("kvp"), "mas": device.get("mas")},
        "px_mm": recipe.get("px_mm"),
        "view": {"gantry_deg": recipe["view"].get("gantry_deg"),
                 "lat_from_ap_deg": recipe["view"].get("lat_from_ap_deg")},
        "boxes": boxes,
        "label_source": recipe["labels"]["kind"] if recipe["labels"] else "none",
        "synthetic": bool(recipe.get("synthetic", False)),
    }


def write_once(path, data):
    """Write a file that is not there; one there with the same bytes is kept, other bytes refused."""
    if path.exists():
        if path.read_bytes() == data:
            return "kept"
        raise BankError(f"{path}: already there with other bytes; the raw copy changed, which is a person's call")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return "written"


def convert(recipe, raw, bank, run):
    """Plan or write the bank; the counts either way."""
    raw, bank = Path(raw), Path(bank)
    persons, labels = Persons(recipe["person"], raw), Labels(recipe["labels"], raw)
    counts = {"frames": 0, "written": 0, "kept": 0, "boxes": 0, "persons": set(), "stems": set()}
    for relative in image_paths(raw, recipe["images"]):
        stem = stem_of(relative)
        if stem in counts["stems"]:
            raise BankError(f"{relative}: its stem {stem} is another file's too")
        counts["stems"].add(stem)
        case = persons.of(relative)
        counts["persons"].add(case)
        if not run:
            counts["frames"] += 1
            continue
        data, width, height = as_png((raw / relative).read_bytes(), recipe["format"])
        boxes = labels.of(relative, width, height)
        counts["boxes"] += len(boxes)
        meta = json.dumps(meta_of(recipe, case, relative, boxes), indent=1, sort_keys=True) + "\n"
        outcome = write_once(bank / "images" / recipe["split"] / f"{stem}.png", data)
        write_once(bank / "meta" / f"{stem}.json", meta.encode("utf-8"))
        counts[outcome] += 1
        counts["frames"] += 1
    counts["persons"], counts["stems"] = len(counts["persons"]), len(counts["stems"])
    return counts


def parser():
    top = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    top.add_argument("--recipe", required=True, help="grid/banks/<id>.json")
    top.add_argument("--raw", default=None, help="the raw folder; the recipe's unless named")
    top.add_argument("--bank", default=None, help="the bank folder; the recipe's unless named")
    top.add_argument("--run", action="store_true", help="write the bank; a plan otherwise")
    return top


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        recipe = load_recipe(args.recipe)
        counts = convert(recipe, args.raw or recipe["raw"], args.bank or recipe["bank"], args.run)
        counts.update({"id": recipe["id"], "bank": args.bank or recipe["bank"], "mode": "run" if args.run else "plan",
                       "split": recipe["split"], "person_prefix": recipe.get("person_prefix", recipe["id"])})
        print(json.dumps(counts, indent=1, sort_keys=True))
        return 0
    except (BankError, OSError, ValueError, KeyError) as error:
        print(f"bank: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
