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
raw copy is a person's decision and a rerun is idempotent. An 8-bit PNG is copied byte for byte
(the ingest hashes the bytes, so a copy keeps the shard's name stable). A frame of more than 8 bits,
a 16-bit PNG or a 16-bit, 32-bit or float image read through Pillow, is cut to 8 bits by the same
0.5 to 99.5 percentile window the DICOM path uses (#260): the trainer reads every frame as 8-bit
grey, and Pillow's conversion of a 16-bit frame clips every value above 255, so such a frame
reached the trainer white. JPEG, TIFF and BMP are read through Pillow where it can be imported
(the train environment, `pixi run -e train-cpu`), and refused with the way to get it otherwise. DICOM is read through pydicom, numpy and Pillow, all in
the train environment's lock (#44), with pylibjpeg's decoders for a compressed pixel array: the
modality LUT applied, MONOCHROME1 inverted, and the 0.5 to 99.5 percentile window cut to 8 bits,
the reduction LEAKAGE.md's pixel key is defined on. Identity comes from the header first: a
person rule `{"dicom": ["PatientID", "StudyInstanceUID"]}` keys the whole source by the first tag
that holds a value that is not a placeholder in every file (never one tag here and another there,
which would key one study's films apart), every header is read before anything is written, and a
study found under two keys is refused, since such a key is finer than the study; the view, the
device and the pixel size may each be read from the header by naming its tag, and a number of zero
or less there is a blank, not a value. A person key that holds more frames than the recipe's
`max_frames_per_person` is refused, since a blank tag filled with one constant would make the
whole set one person; only MONOCHROME1 and MONOCHROME2 pixels are banked, and every file is
written as a .part first and renamed, so a preempted job leaves no short frame. `--workers N` decodes in N processes and writes in path order, so the bank
is the same bytes whatever N is. A finished run writes `<bank>/BANK.json`, the stamp of what made the
bank: the recipe, every file under the raw folder by its path, size and modification time, this
tool's own bytes and the decoders' versions; a later run whose stamp is the same decodes and reads
nothing and says the bank is unchanged (#260), so a rerun of the chain costs a listing of the raw
folder and not a decode of the set. Any change to any of them, a file fetched again among them, makes
a full run, which is idempotent as before. Standard library only, Pillow, numpy and pydicom optional.
"""

import argparse
import csv
import hashlib
import io
import json
import os
import re
import struct
import sys
import zipfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
STAMP = "BANK.json"
# Pillow's modes for a grey frame of more than 8 bits, which the window cuts to 8 (#260).
WIDE_MODES = ("I;16", "I;16L", "I;16B", "I;16N", "I", "F")
TO_CONFIRM = "to confirm"
REQUIRED = ("id", "raw", "bank", "images", "format", "person", "view", "device", "split", "labels")
FORMATS = ("png", "jpg", "jpeg", "tif", "tiff", "bmp", "dcm")
PILLOW_FORMATS = ("jpg", "jpeg", "tif", "tiff", "bmp")
PLACEHOLDERS = ("", "anonymous", "anonymous^", "anonymized", "anonymised", "anon", "none", "unknown",
                "unknown_patient", "0", "00000000", "-", "na", "n/a", "null")
HEADER_TAGS = ("PatientID", "StudyInstanceUID", "SeriesInstanceUID", "ViewPosition", "Manufacturer",
               "ManufacturerModelName", "DetectorType", "KVP", "Exposure", "ExposureInmAs", "ExposureInuAs",
               "ImagerPixelSpacing", "PixelSpacing",
               "BodyPartExamined", "PhotometricInterpretation", "Modality")


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


MEMBER = "!/"


def image_paths(raw, patterns, archives=None):
    """Every file under raw matching a pattern, relative to raw, in path order, each once. Where the
    recipe names archives (zip globs under raw), the patterns match the members inside them, named
    `<archive>!/<member>`, so a set shipped as zips is banked without a second copy on the volume."""
    raw = Path(raw)
    found = set()
    for archive in sorted({p for glob in (archives or []) for p in raw.glob(glob) if p.is_file()}):
        with zipfile.ZipFile(archive) as opened:
            for member in opened.namelist():
                if member.endswith("/") or ".." in Path(member).parts:
                    continue
                if any(Path(member).match(pattern) or Path("x", member).match(pattern) for pattern in patterns):
                    found.add(f"{archive.relative_to(raw).as_posix()}{MEMBER}{member}")
    for pattern in patterns if not archives else []:
        for path in raw.glob(pattern):
            if path.is_file() and not any(part.startswith(".") for part in path.relative_to(raw).parts):
                found.add(path.relative_to(raw).as_posix())
    if not found:
        raise BankError(f"{raw}: no file matches {patterns}" + (f" inside {archives}" if archives else ""))
    return sorted(found)


def read_frame(raw, relative):
    """A frame's bytes, from its file or from its member of an archive."""
    if MEMBER in relative:
        archive, member = relative.split(MEMBER, 1)
        with zipfile.ZipFile(Path(raw) / archive) as opened:
            return opened.read(member)
    return (Path(raw) / relative).read_bytes()


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
        self.tags = [rule["dicom"]] if isinstance(rule.get("dicom"), str) else list(rule.get("dicom") or [])
        self.placeholders = {p.lower() for p in rule.get("placeholders", PLACEHOLDERS)}
        self.table = None
        if "csv" in rule:
            self.table = csv_column(Path(raw) / rule["csv"], rule["path_column"], rule["person_column"])
            self.key = rule.get("key", "name")
        if self.regex is None and self.table is None and not self.tags:
            raise BankError("the person rule names neither a regex, a csv nor a dicom tag")

    def choose_tag(self, headers):
        """The one tag the whole source is keyed by: the first named tag that holds a real value in
        every file. Mixing tags file by file would key one study's AP film by its patient and its
        lateral film by its study, two persons the hash may split."""
        for tag in self.tags:
            if all(str(h.get(tag) or "").strip().lower() not in self.placeholders for h in headers):
                self.tags = [tag]
                return tag
        raise BankError(f"none of the tags {', '.join(self.tags)} holds a person key in every file;"
                        " the recipe is read again rather than mixing keys")

    def of(self, relative, header=None):
        if self.tags:
            return self.from_header(relative, header or {})
        if self.regex is not None:
            match = self.regex.search(relative)
            if not match or not match.group("case"):
                raise BankError(f"{relative}: the person regex finds no case")
            return match.group("case")
        key = Path(relative).name if self.key == "name" else relative
        if key not in self.table:
            raise BankError(f"{relative}: not in the person table")
        return self.table[key]

    def from_header(self, relative, header):
        """The value of the first named tag that holds one; after choose_tag, the source's one tag."""
        for tag in self.tags:
            value = str(header.get(tag) or "").strip()
            if value.lower() not in self.placeholders:
                return value
        raise BankError(f"{relative}: none of the tags {', '.join(self.tags)} holds a person key")


def png_size(data):
    if len(data) < 24 or data[:8] != PNG_SIGNATURE or data[12:16] != b"IHDR":
        raise BankError("not a PNG")
    return struct.unpack(">II", data[16:24])


def png_depth(data):
    """The bits per sample a PNG's header gives, read after png_size has checked the header."""
    if len(data) < 25:
        raise BankError("not a PNG")
    return data[24]


def pillow():
    try:
        from PIL import Image
    except ImportError as error:
        raise BankError("this format needs Pillow, which the default environment does not hold:"
                        " run the bank stage with PYDRV=<repo>/.pixi/envs/train-cpu/bin/python"
                        " (pixi install --locked -e train-cpu)") from error
    return Image


def as_png(data, image_format):
    """The frame's bytes as a PNG with its width and height; an 8-bit PNG passes through
    untouched, so a bank written before #260 is the same bytes."""
    if image_format == "png":
        width, height = png_size(data)
        if png_depth(data) <= 8:
            return data, width, height
    if image_format == "dcm":
        data, width, height, _ = dicom_as_png(data)
        return data, width, height
    image = grey_8bit(pillow().open(io.BytesIO(data)))
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue(), image.width, image.height


def numpy_module():
    try:
        import numpy
    except ImportError as error:
        raise BankError("a frame of more than 8 bits needs numpy to be windowed, which the train environment"
                        " holds: run the bank stage with PYDRV=<repo>/.pixi/envs/train-cpu/bin/python"
                        " (pixi install --locked -e train-cpu)") from error
    return numpy


def grey_8bit(image):
    """An image as the 8-bit grey frame the trainer reads. A grey frame of more than 8 bits is
    windowed as a DICOM film is, since Pillow's own conversion clips it; any other mode is
    converted by Pillow, as the trainer would convert it, and an 8-bit grey frame is kept."""
    if image.mode == "L":
        return image
    if image.mode not in WIDE_MODES:
        return image.convert("L")
    numpy = numpy_module()
    pixels = numpy.asarray(image, dtype=numpy.float64)
    if pixels.ndim != 2:
        raise BankError(f"the {image.mode} image has shape {pixels.shape}; a grey film is two dimensional")
    return pillow().fromarray(window_8bit(numpy, pixels), mode="L")


def dicom_modules():
    try:
        import numpy
        import pydicom
        from pydicom.pixels import apply_modality_lut
    except ImportError as error:
        raise BankError("DICOM needs pydicom and numpy, which the train environment holds: run the bank stage"
                        " with PYDRV=<repo>/.pixi/envs/train-cpu/bin/python (pixi install --locked -e train-cpu)"
                        ) from error
    return numpy, pydicom, apply_modality_lut


def positive(value, scale=1.0):
    """A header number as a float above zero, else None: an X-ray's kVp, mAs or pixel size of zero
    or less is a blank written as a number, which the catalog's models refuse."""
    try:
        number = float(value) * scale
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def tag_value(dataset, tag):
    """One header field as a plain string or number, None where absent or unreadable."""
    try:
        value = dataset.get(tag)
    except Exception:  # pydicom raises several kinds for a malformed element
        return None
    if value is None or value == "":
        return None
    if tag in ("ImagerPixelSpacing", "PixelSpacing"):
        values = list(value) if isinstance(value, (list, tuple)) or hasattr(value, "__iter__") and not isinstance(
            value, str) else [value]
        spacing = [positive(v) for v in values]
        return spacing if spacing and all(spacing) else None
    if tag in ("KVP", "Exposure", "ExposureInmAs", "ExposureInuAs"):
        return positive(value)
    return str(value)


def header_of(dataset):
    """The header fields a recipe may read, absent or unreadable ones left out; `mAs` is the
    exposure from the most precise of its three tags, since a paediatric film under 1 mAs keeps a
    zero in the integer tag Exposure."""
    header = {tag: value for tag in HEADER_TAGS if (value := tag_value(dataset, tag)) is not None}
    header["mAs"] = header.get("ExposureInmAs") or positive(header.get("ExposureInuAs"), 0.001) or header.get("Exposure")
    header = {k: v for k, v in header.items() if v is not None}
    meta = getattr(dataset, "file_meta", None)
    header["TransferSyntaxUID"] = str(getattr(meta, "TransferSyntaxUID", "") or "")
    return header


def dicom_header(data):
    """The header alone, the pixel data not read, for a plan."""
    _, pydicom, _ = dicom_modules()
    return header_of(pydicom.dcmread(io.BytesIO(data), stop_before_pixels=True, force=True))


def window_8bit(numpy, pixels):
    """The 0.5 to 99.5 percentile window to 8 bits, LEAKAGE.md's pixel-key reduction; a flat
    frame, whose window is empty, is refused rather than written as one grey."""
    low, high = numpy.percentile(pixels, (0.5, 99.5))
    if not high > low:
        raise BankError("the frame is flat: its 0.5 and 99.5 percentiles are equal")
    scaled = (numpy.clip(pixels, low, high) - low) * (255.0 / (high - low))
    return numpy.round(scaled).astype(numpy.uint8)


def dicom_as_png(data):
    """One DICOM frame as an 8-bit PNG with its width, height and header."""
    numpy, pydicom, apply_modality_lut = dicom_modules()
    dataset = pydicom.dcmread(io.BytesIO(data), force=True)
    header = header_of(dataset)
    if header.get("PhotometricInterpretation") not in ("MONOCHROME1", "MONOCHROME2"):
        raise BankError(f"photometric interpretation {header.get('PhotometricInterpretation')!r}; a film is"
                        " MONOCHROME1 or MONOCHROME2, and palette or colour pixels are not grey levels")
    if int(dataset.get("NumberOfFrames", 1) or 1) > 1:
        raise BankError(f"{int(dataset.NumberOfFrames)} frames in one file; a cine is not a film and this tool"
                        " banks one frame per file")
    try:
        pixels = dataset.pixel_array
    except Exception as error:  # pydicom raises several kinds for a pixel array it cannot decode
        raise BankError(f"the pixel data does not decode (transfer syntax {header['TransferSyntaxUID'] or 'none'}):"
                        f" {error}") from error
    pixels = numpy.asarray(apply_modality_lut(pixels, dataset), dtype=numpy.float64)
    if pixels.ndim != 2:
        raise BankError(f"the pixel array has shape {pixels.shape}; a grey film is two dimensional")
    if header.get("PhotometricInterpretation") == "MONOCHROME1":
        pixels = pixels.max() - pixels
    grey = window_8bit(numpy, pixels)
    image = pillow().fromarray(grey, mode="L")
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue(), image.width, image.height, header


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


def from_header(value, header, scale=None):
    """A recipe value, or the header's where the recipe names a tag as {"dicom": tag}; a mapped tag
    gives its map's value, and a value the map lacks gives the map's default."""
    if not isinstance(value, dict) or "dicom" not in value:
        return value
    found = header.get(value["dicom"])
    if "map" in value:
        return value["map"].get(str(found).strip().upper(), value.get("default"))
    if isinstance(found, list):
        found = found[0] if found else None
    return found if found not in ("", None) else value.get("default")


def meta_of(recipe, case, relative, boxes, header=None):
    header = header or {}
    device, view = dict(recipe["device"]), recipe["view"]
    meta = {
        "dataset": recipe["id"],
        "case": case,
        "source_path": relative,
        "split": recipe["split"],
        "device": {key: from_header(device.get(key), header) for key in ("make", "model", "detector", "kvp", "mas")},
        "px_mm": from_header(recipe.get("px_mm"), header),
        "view": {"gantry_deg": from_header(view.get("gantry_deg"), header),
                 "lat_from_ap_deg": from_header(view.get("lat_from_ap_deg"), header)},
        "boxes": boxes,
        "label_source": recipe["labels"]["kind"] if recipe["labels"] else "none",
        "synthetic": bool(recipe.get("synthetic", False)),
    }
    if header:
        meta["dicom"] = {key: header[key] for key in sorted(header) if key != "PatientID"}
    return meta


def write_once(path, data):
    """Write a file that is not there; one there with the same bytes is kept, other bytes refused."""
    if path.exists():
        if path.read_bytes() == data:
            return "kept"
        raise BankError(f"{path}: already there with other bytes; the raw copy changed, which is a person's call,"
                        " or an older tools/bank.py wrote it (a frame of more than 8 bits is windowed since #260)")
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    part.write_bytes(data)
    os.replace(part, path)  # a job preempted mid-write leaves a .part, never a short frame
    return "written"


def decode(job):
    """One file's frame: the PNG bytes, its size and the header; run in a worker process."""
    raw, relative, image_format = job
    data = read_frame(raw, relative)
    try:
        if image_format == "dcm":
            return dicom_as_png(data)
        png, width, height = as_png(data, image_format)
        return png, width, height, {}
    except BankError as error:
        raise BankError(f"{relative}: {error}") from None
    except Exception as error:  # a malformed file names itself in the report, not a traceback
        raise BankError(f"{relative}: {type(error).__name__}: {error}") from None


def header_only(job):
    raw, relative, image_format = job
    try:
        return dicom_header(read_frame(raw, relative)) if image_format == "dcm" else {}
    except BankError as error:
        raise BankError(f"{relative}: {error}") from None
    except Exception as error:
        raise BankError(f"{relative}: {type(error).__name__}: {error}") from None


def mapped(function, jobs, workers):
    """function over jobs in order, in `workers` processes where more than one is asked for."""
    if workers <= 1:
        yield from map(function, jobs)
        return
    window = workers * 4  # a bounded queue, so decoded frames never pile up past the writer
    with ProcessPoolExecutor(max_workers=workers) as pool:
        pending = []
        for job in jobs:
            pending.append(pool.submit(function, job))
            if len(pending) >= window:
                yield pending.pop(0).result()
        for future in pending:
            yield future.result()


def keys_of(persons, relatives, headers):
    """Each file's person key; for a header-keyed source one tag for the whole source, and no study
    under two keys, since a key finer than the study would let the hash split one study's films."""
    tag = persons.choose_tag(headers) if persons.tags else None
    keys = [persons.of(relative, header) for relative, header in zip(relatives, headers)]
    by_study = {}
    for key, header in zip(keys, headers):
        study = header.get("StudyInstanceUID")
        if study:
            by_study.setdefault(study, set()).add(key)
    split = sorted(study for study, found in by_study.items() if len(found) > 1)
    if split:
        raise BankError(f"{len(split)} studies fall under more than one person key (first {split[0]}); the key is"
                        " finer than the study, so the recipe is read again")
    return keys, tag, len(by_study)


def raw_listing(raw):
    """Every file under the raw folder as path, size and modification time in nanoseconds, in path
    order: what the stamp says the bank was made from. A file rewritten with the same bytes has a
    new time, so the stamp errs towards a full run, never towards a skip."""
    raw = Path(raw)
    lines = []
    for folder, folders, files in os.walk(raw):
        folders.sort()
        for name in sorted(files):
            path = Path(folder) / name
            info = path.stat()
            lines.append(f"{path.relative_to(raw).as_posix()}\t{info.st_size}\t{info.st_mtime_ns}")
    return sorted(lines)


def decoder_versions():
    """The versions of the decoders this python holds, since a new decoder may decode a frame
    to other bytes."""
    versions = {}
    for name, module in (("Pillow", "PIL"), ("numpy", "numpy"), ("pydicom", "pydicom")):
        try:
            versions[name] = getattr(__import__(module), "__version__", "unknown")
        except ImportError:
            versions[name] = None
    return versions


def stamp_of(recipe, raw):
    """What made a bank, as the hashes BANK.json holds and a rerun compares."""
    text = "\n".join(raw_listing(raw)) + "\n"
    return {
        "recipe_sha256": hashlib.sha256(json.dumps(recipe, sort_keys=True).encode("utf-8")).hexdigest(),
        "raw_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "decoders": decoder_versions(),
    }


def unchanged_counts(bank, stamp):
    """The counts the stamp recorded when the bank was made from the same inputs, else None."""
    try:
        recorded = json.loads((Path(bank) / STAMP).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(recorded, dict) or recorded.get("stamp") != stamp:
        return None
    counts = dict(recorded.get("counts") or {})
    counts.update(written=0, kept=counts.get("frames", 0), unchanged=True)
    return counts


def write_stamp(bank, stamp, counts):
    """Record what made the bank, last, so a bank cut short has no stamp and runs again."""
    kept = {key: value for key, value in counts.items() if key not in ("written", "kept")}
    text = json.dumps({"stamp": stamp, "counts": kept}, indent=1, sort_keys=True) + "\n"
    path = Path(bank) / STAMP
    part = path.with_name(path.name + ".part")
    path.parent.mkdir(parents=True, exist_ok=True)
    part.write_text(text, encoding="utf-8")
    os.replace(part, path)


def run_once(recipe, raw, bank, workers=1):
    """Write the bank unless its stamp says the same inputs made it; the counts either way."""
    stamp = stamp_of(recipe, raw)
    counts = unchanged_counts(bank, stamp)
    if counts is not None:
        return counts
    counts = convert(recipe, raw, bank, True, workers)
    write_stamp(bank, stamp, counts)
    return counts


def convert(recipe, raw, bank, run, workers=1):
    """Plan or write the bank; the counts either way. A DICOM source's headers are read first, every
    one, so the person keys, the studies and the transfer syntaxes are settled before a pixel is
    decoded or a file written."""
    raw, bank = Path(raw), Path(bank)
    persons, labels = Persons(recipe["person"], raw), Labels(recipe["labels"], raw)
    counts = {"frames": 0, "written": 0, "kept": 0, "boxes": 0, "persons": set(), "stems": set()}
    relatives = image_paths(raw, recipe["images"], recipe.get("archives"))
    for relative in relatives:
        stem = stem_of(relative)
        if stem in counts["stems"]:
            raise BankError(f"{relative}: its stem {stem} is another file's too")
        counts["stems"].add(stem)
    jobs = [(str(raw), relative, recipe["format"]) for relative in relatives]
    dicom_source = recipe["format"] == "dcm"
    headers = list(mapped(header_only, jobs, workers)) if dicom_source else [{} for _ in jobs]
    keys, tag, studies = keys_of(persons, relatives, headers)
    per_person = {}
    for key in keys:
        per_person[key] = per_person.get(key, 0) + 1
    limit = recipe.get("max_frames_per_person")
    crowded = [key for key, n in per_person.items() if limit and n > int(limit)]
    if crowded:
        raise BankError(f"person {crowded[0]} holds more than {limit} frames (max_frames_per_person); a"
                        " placeholder in the person tag would make the set one person, so the recipe is read again")
    counts["persons"] = set(keys)
    if dicom_source:
        syntaxes = {}
        for header in headers:
            syntax = header.get("TransferSyntaxUID") or "none"
            syntaxes[syntax] = syntaxes.get(syntax, 0) + 1
        counts.update(transfer_syntaxes=dict(sorted(syntaxes.items())), studies=studies, person_tag=tag,
                      most_frames_per_person=max(per_person.values(), default=0))
    if not run:
        counts["frames"] = len(relatives)
    else:
        for relative, case, (data, width, height, header) in zip(relatives, keys, mapped(decode, jobs, workers)):
            stem = stem_of(relative)
            boxes = labels.of(relative, width, height)
            counts["boxes"] += len(boxes)
            meta = meta_of(recipe, case, relative, boxes, header)
            if tag:
                meta["person_tag"] = tag
            text = json.dumps(meta, indent=1, sort_keys=True) + "\n"
            outcome = write_once(bank / "images" / recipe["split"] / f"{stem}.png", data)
            write_once(bank / "meta" / f"{stem}.json", text.encode("utf-8"))
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
    top.add_argument("--workers", type=int, default=int(os.environ.get("BANK_WORKERS", "1")),
                     help="processes that decode; the bank is the same bytes whatever the number")
    return top


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        recipe = load_recipe(args.recipe)
        raw, bank = args.raw or recipe["raw"], args.bank or recipe["bank"]
        if args.run:
            counts = run_once(recipe, raw, bank, args.workers)
        else:
            counts = convert(recipe, raw, bank, False, args.workers)
        counts.update({"id": recipe["id"], "bank": args.bank or recipe["bank"], "mode": "run" if args.run else "plan",
                       "split": recipe["split"], "person_prefix": recipe.get("person_prefix", recipe["id"])})
        print(json.dumps(counts, indent=1, sort_keys=True))
        return 0
    except (BankError, OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as error:
        print(f"bank: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
