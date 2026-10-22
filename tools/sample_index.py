"""The sample index: one queryable SQLite file naming every file the lab holds, with its metadata.

The owner's asks of 2026-10-21 21:27 and 21:28 UTC: more than a count of datasets, a manifest of
what each holds (annotated or not, the size, the data format and whatever else is relevant), and a
database in which each sample is paired with its variables, every DICOM header field and every
sample-specific record that came with its dataset, so that a query, not a person, joins them.

    python tools/sample_index.py roots --data-root <dir> --out <run>/roots.tsv
    python tools/sample_index.py units --roots <run>/roots.tsv --out <run>/units.tsv
    python tools/sample_index.py scan --run <run> --task <n> --tasks <m> [--all-slices]
    python tools/sample_index.py merge --run <run>
    python tools/sample_index.py report --db <run>/samples.sqlite

grid/run-samples.sh submits these as Slurm jobs: roots and units in one small job, scan as an
array whose tasks take every m-th unit, and merge after the array. On the grid every byte stays on
the lab volume; samples.sqlite holds paths and header values, PatientID and the UIDs among them,
so it is never copied off the grid. What leaves it is MANIFEST.json and MANIFEST.md, which are
aggregates only: counts, bytes, formats, tag names, column names, decades of age.

What is read where:
- roots: every path the data platform's manifest (data/reproduce/sources.json) lists as a raw
  location of a source held on disk, every path a registry record (data/sources/) names, and
  every folder directly under the data root that is not a tool's own (no leading underscore).
  A file belongs to the deepest root that holds it, so a source inside a larger folder keeps its
  name; a root that another holds is scanned as part of it, never twice.
- scan: for each file its size, time and format from its first bytes, never its suffix alone;
  the width, height, depth, frames and bits of PNG, JPEG, TIFF, NIfTI, NRRD and DICOM from their
  headers; for DICOM (pydicom, the train-cpu environment) every header element but the pixels,
  sequences to two levels, written in full for every projection image and for the first file of
  each series of a cross-sectional study (the slices name their series, and the view
  sample_header gives each slice its series' header), or for every slice with --all-slices; and
  for every table (CSV, TSV, XLSX) and JSON that came with a source, its rows as cells.
- merge: the parts into samples.sqlite, then the joins: a cell whose value names a sample (its
  file name, stem, a run of five or more digits in it, or for DICOM its SOP, series or study UID
  or PatientID) links that row to the sample; an annotation file whose stem, less words such as
  label, mask or seg, is an image's stem marks the image annotated, as does a link to a row of a
  table whose columns hold coordinates, labels or classes, or a COCO file's images list.

The views sample_meta (each sample's linked cells) and sample_header (each sample's DICOM
elements, its own or its series') are the two the queries start from; README in
docs/research/data-manifest/ gives examples.
"""

import argparse
import csv
import glob
import gzip
import hashlib
import json
import os
import re
import sqlite3
import struct
import sys
import time
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRID_DATA = "/rs/rs_grp_oschome/go2432/data"
LAB_PATH = re.compile(r"/(?:rs|wsu)/[^\s;,()]+")
HEAD = 512
MAX_ROWS = 2_000_000
MAX_JSON = 200_000_000
CELL_CHARS = 512
MAX_KEY_FILES = 20

IMAGE_FORMATS = {"png", "jpeg", "tiff", "bigtiff", "bmp", "dicom", "jpeg2000"}
VOLUME_FORMATS = {"nifti", "nifti-gz", "nrrd", "metaimage"}
VIDEO_FORMATS = {"mp4", "mkv", "avi"}
TABLE_FORMATS = {"csv", "tsv", "xlsx"}
ARCHIVE_FORMATS = {"zip", "gzip", "tar", "xz", "bzip2", "7z"}
LABEL_WORDS = {"label", "labels", "annotation", "annotations", "mask", "masks", "seg", "segs",
               "segmentation", "segmentations", "gt", "groundtruth", "landmark", "landmarks",
               "keypoints", "ann", "anns", "bbox", "bboxes", "msk"}
ANNOTATION_COLUMNS = {"x", "y", "x1", "y1", "xmin", "ymin", "bbox", "landmark", "landmarks",
                      "keypoints", "points", "corner", "label", "labels", "class", "category",
                      "level", "vertebra", "vertebrae", "cobb", "grade", "finding", "findings",
                      "diagnosis", "segmentation"}
PROJECTION_MODALITIES = {"CR", "DX", "RF", "XA", "MG", "IO", "PX", "OT", "RG", "DF", "SC"}
BULK_VRS = {"OB", "OW", "OF", "OD", "OL", "OV", "UN"}
WIDE_TAGS = {"Rows": "height", "Columns": "width", "NumberOfFrames": "frames", "BitsStored": "bits",
             "SamplesPerPixel": "channels", "Modality": "modality", "BodyPartExamined": "body_part",
             "ViewPosition": "view", "Manufacturer": "manufacturer",
             "ManufacturerModelName": "model", "KVP": "kvp", "PatientSex": "patient_sex",
             "StudyInstanceUID": "study_uid", "SeriesInstanceUID": "series_uid",
             "SOPInstanceUID": "sop_uid", "PatientID": "patient_id"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS root (id INTEGER PRIMARY KEY, path TEXT UNIQUE, sources TEXT,
    roles TEXT, storage TEXT, scanned_as INTEGER);
CREATE TABLE IF NOT EXISTS file (id INTEGER PRIMARY KEY, path TEXT UNIQUE, root_id INTEGER,
    rel TEXT, name TEXT, key TEXT, bare TEXT, size INTEGER, mtime REAL, role TEXT, format TEXT,
    width INTEGER, height INTEGER, depth INTEGER, frames INTEGER, channels INTEGER, bits INTEGER,
    modality TEXT, body_part TEXT, view TEXT, manufacturer TEXT, model TEXT, kvp REAL,
    patient_sex TEXT, age_years REAL, pixel_spacing TEXT, study_uid TEXT, series_uid TEXT,
    sop_uid TEXT, patient_id TEXT, header_full INTEGER DEFAULT 0, header_from INTEGER,
    annotated INTEGER DEFAULT 0, error TEXT);
CREATE TABLE IF NOT EXISTS dicom (file_id INTEGER, tag TEXT, keyword TEXT, vr TEXT, value TEXT);
CREATE TABLE IF NOT EXISTS tab (id INTEGER PRIMARY KEY, file_id INTEGER, kind TEXT,
    columns TEXT, rows INTEGER, truncated INTEGER, annotation INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS cell (tab_id INTEGER, row INTEGER, col TEXT, value TEXT, key TEXT);
CREATE TABLE IF NOT EXISTS key (file_id INTEGER, value TEXT, via TEXT);
CREATE TABLE IF NOT EXISTS link (file_id INTEGER, tab_id INTEGER, row INTEGER, col TEXT, via TEXT);
CREATE TABLE IF NOT EXISTS annotation (image_id INTEGER, annotation_id INTEGER, via TEXT);
CREATE TABLE IF NOT EXISTS done (unit TEXT PRIMARY KEY, files INTEGER, seconds REAL);
"""

INDEXES = """
CREATE INDEX IF NOT EXISTS file_root ON file(root_id);
CREATE INDEX IF NOT EXISTS file_role ON file(role, annotated);
CREATE INDEX IF NOT EXISTS file_bare ON file(bare);
CREATE INDEX IF NOT EXISTS file_series ON file(series_uid, header_full);
CREATE INDEX IF NOT EXISTS dicom_file ON dicom(file_id);
CREATE INDEX IF NOT EXISTS dicom_keyword ON dicom(keyword, value);
CREATE INDEX IF NOT EXISTS cell_key ON cell(key);
CREATE INDEX IF NOT EXISTS cell_row ON cell(tab_id, row);
CREATE INDEX IF NOT EXISTS key_value ON key(value);
CREATE INDEX IF NOT EXISTS link_file ON link(file_id);
CREATE INDEX IF NOT EXISTS annotation_image ON annotation(image_id);
CREATE VIEW IF NOT EXISTS sample AS
    SELECT f.*, r.sources AS sources, r.path AS root_path FROM file f JOIN root r ON r.id = f.root_id;
CREATE VIEW IF NOT EXISTS sample_meta AS
    SELECT l.file_id, l.via, t.file_id AS table_file_id, l.row, c.col, c.value
    FROM link l JOIN tab t ON t.id = l.tab_id JOIN cell c ON c.tab_id = l.tab_id AND c.row = l.row;
CREATE VIEW IF NOT EXISTS sample_header AS
    SELECT f.id AS file_id, d.tag, d.keyword, d.vr, d.value, f.header_from = f.id AS own
    FROM file f JOIN dicom d ON d.file_id = f.header_from;
"""


# ---- roots: where the lab's files are --------------------------------------------------------

def lab_paths(text):
    """The lab paths a free-text field names, globs expanded, trailing punctuation dropped."""
    found = []
    for match in LAB_PATH.findall(text or ""):
        path = match.rstrip(".:/") or "/"
        found.extend(sorted(glob.glob(path)) if "*" in path else [path])
    return found


def manifest_roots(sources_json):
    """(path, source, role, storage) for every raw location of a source the manifest holds."""
    data = json.loads(Path(sources_json).read_text(encoding="utf-8"))
    for source in data.get("sources", []):
        if not str(source.get("status", "")).startswith("on_disk"):
            continue
        for place in source.get("locations") or []:
            if place.get("role") in ("raw", "unknown"):
                yield place["path"].rstrip("/"), source["id"], place["role"], place.get("storage") or ""


def registry_roots(folder):
    for record_path in sorted(Path(folder).glob("*.json")):
        record = json.loads(record_path.read_text(encoding="utf-8"))
        for path in lab_paths(record.get("grid_path")):
            yield path.rstrip("/"), record["id"], "registry", ""


def data_root_children(data_root):
    if not os.path.isdir(data_root):
        return
    for entry in sorted(os.scandir(data_root), key=lambda e: e.name):
        if not entry.name.startswith(("_", ".")) and entry.is_dir(follow_symlinks=False):
            yield entry.path.rstrip("/"), "unmapped:" + entry.name, "folder", "CEPH"


def gather_roots(sources_json, registry, data_root):
    """Every root, its sources and roles joined, as {path: {"sources": set, ...}}."""
    roots = defaultdict(lambda: {"sources": set(), "roles": set(), "storage": set()})
    found = list(manifest_roots(sources_json)) + list(registry_roots(registry))
    named = {path for path, _, _, _ in found}
    for path, source, role, storage in found + list(data_root_children(data_root)):
        if source.startswith("unmapped:") and path in named:
            continue
        entry = roots[os.path.normpath(path)]
        entry["sources"].add(source)
        entry["roles"].add(role)
        if storage:
            entry["storage"].add(storage)
    return roots


def scanned_as(path, all_paths):
    """The outermost root that holds path (itself when none does), so nothing is walked twice."""
    best = path
    for other in all_paths:
        if other != path and path.startswith(other.rstrip("/") + "/") and len(other) < len(best):
            best = other
    return best


def write_roots(roots, out):
    paths = sorted(roots)
    lines = ["path\tsources\troles\tstorage\tscanned_as\texists"]
    for path in paths:
        entry = roots[path]
        lines.append("\t".join([path, ",".join(sorted(entry["sources"])), ",".join(sorted(entry["roles"])),
                                ",".join(sorted(entry["storage"])), scanned_as(path, paths),
                                "1" if os.path.exists(path) else "0"]))
    Path(out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(paths)


def read_roots(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


# ---- units: the pieces the array shares out --------------------------------------------------

def child_dirs(path):
    try:
        return sorted(e.path for e in os.scandir(path) if e.is_dir(follow_symlinks=False))
    except OSError:
        return []


def units_of(top, depth):
    """('files', dir) for each folder above depth and ('tree', dir) at it: the walk in pieces."""
    if not os.path.isdir(top):
        return [("file", top)] if os.path.isfile(top) else []
    units, level = [], [top]
    for _ in range(depth):
        units.extend(("files", folder) for folder in level)
        level = [child for folder in level for child in child_dirs(folder)]
    return units + [("tree", folder) for folder in level]


def write_units(roots, out, depth):
    tops = sorted({row["scanned_as"] for row in roots if row["exists"] == "1"})
    units = [unit for top in tops for unit in units_of(top, depth)]
    Path(out).write_text("".join(f"{kind}\t{path}\n" for kind, path in units), encoding="utf-8")
    return len(units)


# ---- reading one file ------------------------------------------------------------------------

def sniff(head, name):
    """The format of a file from its first bytes, with the suffix only where bytes cannot tell."""
    low = name.lower()
    signatures = ((b"\x89PNG\r\n\x1a\n", "png"), (b"\xff\xd8\xff", "jpeg"), (b"II*\x00", "tiff"),
                  (b"MM\x00*", "tiff"), (b"II+\x00", "bigtiff"), (b"MM\x00+", "bigtiff"),
                  (b"\x89HDF\r\n\x1a\n", "hdf5"), (b"MATLAB 5.0", "mat"), (b"\x93NUMPY", "npy"),
                  (b"\x1aE\xdf\xa3", "mkv"), (b"NRRD", "nrrd"), (b"%PDF", "pdf"),
                  (b"\xfd7zXZ", "xz"), (b"BZh", "bzip2"), (b"7z\xbc\xaf", "7z"),
                  (b"\x00\x00\x00\x0cjP  ", "jpeg2000"), (b"\xff\x4f\xff\x51", "jpeg2000"))
    if head[128:132] == b"DICM":
        return "dicom"
    for magic, name_of in signatures:
        if head.startswith(magic):
            return "mat" if name_of == "hdf5" and low.endswith(".mat") else name_of
    return sniff_containers(head, low) or sniff_by_suffix(head, low)


def sniff_containers(head, low):
    if head.startswith(b"PK\x03\x04"):
        return "npz" if low.endswith(".npz") else "xlsx" if low.endswith(".xlsx") else "zip"
    if head.startswith(b"\x1f\x8b"):
        return "nifti-gz" if low.endswith(".nii.gz") else "gzip"
    if head[257:262] == b"ustar":
        return "tar"
    if head[4:8] == b"ftyp":
        return "mp4"
    if head[:4] == b"RIFF" and head[8:12] == b"AVI ":
        return "avi"
    if head[:2] == b"BM" and low.endswith(".bmp"):
        return "bmp"
    if len(head) >= 348 and head[344:347] in (b"n+1", b"ni1"):
        return "nifti"
    return None


def sniff_by_suffix(head, low):
    if head[:1] == b"\x80" and low.endswith((".pkl", ".pickle", ".pk")):
        return "pickle"
    if low.endswith((".mha", ".mhd")):
        return "metaimage"
    if low.endswith(".dcm"):
        return "dicom"
    for suffix, name_of in ((".csv", "csv"), (".tsv", "tsv"), (".json", "json"), (".xml", "xml"),
                            (".txt", "txt"), (".md", "text"), (".html", "html"), (".xls", "xls")):
        if low.endswith(suffix):
            return name_of
    return "other"


def png_size(head):
    width, height, bits, colour = struct.unpack(">IIBB", head[16:26])
    return {"width": width, "height": height, "bits": bits,
            "channels": {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(colour)}


def jpeg_size(handle):
    """Width, height, bits and channels from the first start-of-frame marker."""
    data = handle.read(1 << 20)
    at = 2
    while at + 9 < len(data):
        if data[at] != 0xFF:
            at += 1
            continue
        marker = data[at + 1]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            bits, height, width, channels = struct.unpack(">BHHB", data[at + 4:at + 10])
            return {"width": width, "height": height, "bits": bits, "channels": channels}
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            at += 2
            continue
        at += 2 + struct.unpack(">H", data[at + 2:at + 4])[0]
    return {}


def tiff_size(handle):
    """Width, height, bits and channels from the first image directory of a classic TIFF."""
    handle.seek(0)
    order = "<" if handle.read(2) == b"II" else ">"
    handle.seek(4)
    handle.seek(struct.unpack(order + "I", handle.read(4))[0])
    count = struct.unpack(order + "H", handle.read(2))[0]
    wanted = {256: "width", 257: "height", 258: "bits", 277: "channels"}
    found = {}
    for _ in range(min(count, 512)):
        tag, kind, number, raw = struct.unpack(order + "HHI4s", handle.read(12))
        if tag in wanted:
            found[wanted[tag]] = tiff_value(order, kind, number, raw, handle)
    return found


def tiff_value(order, kind, number, raw, handle):
    """A SHORT or LONG entry's first value, read where it lives (inline or at its offset)."""
    width = 2 if kind == 3 else 4
    if number * width > 4:
        here = handle.tell()
        handle.seek(struct.unpack(order + "I", raw)[0])
        raw = handle.read(width)
        handle.seek(here)
    return struct.unpack(order + ("H" if kind == 3 else "I"), raw[:width])[0]


def nifti_size(head):
    order = "<" if struct.unpack("<i", head[:4])[0] == 348 else ">"
    dims = struct.unpack(order + "8h", head[40:56])
    found = {"width": dims[1], "height": dims[2], "depth": dims[3] if dims[0] >= 3 else None,
             "frames": dims[4] if dims[0] >= 4 else None}
    found["bits"] = struct.unpack(order + "h", head[72:74])[0]
    return found


def nrrd_size(head):
    text = head.decode("latin-1", "replace")
    match = re.search(r"^sizes:\s*([\d ]+)$", text, flags=re.M)
    sizes = [int(n) for n in match.group(1).split()] if match else []
    keys = ("width", "height", "depth", "frames")
    return dict(zip(keys, sizes))


def image_size(path, fmt, head):
    """What the header of an image or volume says of its shape; {} where it cannot be read."""
    if fmt == "png" and len(head) >= 26:
        return png_size(head)
    if fmt in ("nifti", "nrrd"):
        return nifti_size(head) if fmt == "nifti" else nrrd_size(head)
    if fmt == "nifti-gz":
        with gzip.open(path, "rb") as handle:
            return nifti_size(handle.read(348))
    if fmt in ("jpeg", "tiff"):
        with open(path, "rb") as handle:
            return jpeg_size(handle) if fmt == "jpeg" else tiff_size(handle)
    return {}


# ---- keys: how a cell names a sample ---------------------------------------------------------

def key_of(text):
    """A name reduced so a table's 'images/0012.PNG' and the file 0012.png meet: lower case, the
    last path part, its suffixes off, leading zeros off a number; None when under 3 characters."""
    value = str(text).strip().lower().replace("\\", "/")
    if not value or len(value) > 260:
        return None
    value = value.rsplit("/", 1)[-1]
    while re.search(r"\.[a-z0-9]{1,5}$", value) and not re.fullmatch(r"[\d.]+", value):
        value = value[: value.rfind(".")]
    if value.isdigit():
        value = value.lstrip("0") or "0"
    return value if len(value) >= 3 else None


def bare_of(key):
    """A stem with the words that mark an annotation taken out, so img7_mask meets img7."""
    if not key:
        return None
    words = [w for w in re.split(r"[_\-. ]+", key) if w and w not in LABEL_WORDS]
    bare = "_".join(words)
    return bare if len(bare) >= 3 else None


def digit_runs(key):
    return sorted({(run.lstrip("0") or "0") for run in re.findall(r"\d{5,}", key or "")})


def is_annotation_path(rel, fmt):
    words = {w for part in rel.lower().split("/") for w in re.split(r"[_\-. ]+", part) if w}
    if words & LABEL_WORDS:
        return True
    return fmt in ("pickle", "xml")


def role_of(rel, fmt):
    if fmt in TABLE_FORMATS:
        return "table"
    if is_annotation_path(rel, fmt) and fmt not in VIDEO_FORMATS:
        return "annotation"
    if fmt in IMAGE_FORMATS or fmt in VOLUME_FORMATS:
        return "image"
    if fmt in VIDEO_FORMATS:
        return "video"
    if fmt == "json":
        return "json"
    return "archive" if fmt in ARCHIVE_FORMATS else "other"


# ---- DICOM -----------------------------------------------------------------------------------

def dicom_value(element):
    if element.VR in BULK_VRS or isinstance(element.value, (bytes, bytearray)):
        size = len(element.value or b"")
        return f"<{size} bytes>" if size > 64 else bytes(element.value or b"").hex()
    value = element.value
    if isinstance(value, (list, tuple)) or type(value).__name__ == "MultiValue":
        return "\\".join(str(v) for v in value)[:1024]
    return str(value)[:1024]


def dicom_elements(dataset, prefix="", depth=0):
    """(tag, keyword, vr, value) for every element but the pixels, sequences to two levels."""
    for element in dataset:
        if element.tag == 0x7FE00010:
            continue
        keyword = prefix + (element.keyword or f"{element.tag:08X}")
        tag = f"{element.tag.group:04X},{element.tag.element:04X}"
        if element.VR == "SQ":
            yield tag, keyword, "SQ", f"{len(element.value)} items"
            if depth < 2:
                for index, item in enumerate(list(element.value)[:5]):
                    yield from dicom_elements(item, f"{keyword}[{index}].", depth + 1)
            continue
        yield tag, keyword, element.VR, dicom_value(element)


def age_in_years(text):
    match = re.fullmatch(r"(\d{3})([DWMY])", str(text or "").strip().upper())
    if not match:
        return None
    return int(match.group(1)) / {"Y": 1, "M": 12, "W": 52, "D": 365}[match.group(2)]


def dicom_wide(dataset):
    """The columns of the file table a DICOM header fills."""
    found = {}
    for keyword, column in WIDE_TAGS.items():
        value = getattr(dataset, keyword, None)
        if value not in (None, ""):
            found[column] = str(value).strip()[:256]
    spacing = getattr(dataset, "PixelSpacing", None) or getattr(dataset, "ImagerPixelSpacing", None)
    if spacing:
        found["pixel_spacing"] = "\\".join(str(v) for v in spacing)
    found["age_years"] = age_in_years(getattr(dataset, "PatientAge", None))
    return found


def read_dicom(path):
    try:
        import pydicom
    except ImportError:
        return None, "pydicom missing"
    try:
        return pydicom.dcmread(path, stop_before_pixels=True, force=True), None
    except Exception as error:  # pydicom raises many kinds for a file it cannot parse
        return None, type(error).__name__


# ---- tables and JSON -------------------------------------------------------------------------

def csv_rows(path, fmt):
    with open(path, newline="", encoding="utf-8", errors="replace") as handle:
        reader = csv.reader(handle, delimiter="\t" if fmt == "tsv" else ",")
        header = [h.strip() or f"col{i}" for i, h in enumerate(next(reader, []))]
        for number, row in enumerate(reader):
            if number >= MAX_ROWS:
                yield None
                return
            yield dict(zip(header, row))


def xlsx_rows(path):
    """The first sheet's rows as dicts keyed by its first row, read from the workbook's XML."""
    with zipfile.ZipFile(path) as book:
        names = book.namelist()
        shared = []
        if "xl/sharedStrings.xml" in names:
            text = book.read("xl/sharedStrings.xml").decode("utf-8", "replace")
            shared = [re.sub(r"<[^>]+>", "", s) for s in re.findall(r"<si>(.*?)</si>", text, flags=re.S)]
        sheet = book.read("xl/worksheets/sheet1.xml").decode("utf-8", "replace")
    rows = [xlsx_cells(row, shared) for row in re.findall(r"<row[^>]*>(.*?)</row>", sheet, flags=re.S)]
    header = [h or f"col{i}" for i, h in enumerate(rows[0])] if rows else []
    for number, row in enumerate(rows[1:]):
        if number >= MAX_ROWS:
            yield None
            return
        yield dict(zip(header, row))


def xlsx_cells(row, shared):
    cells = []
    for attributes, body in re.findall(r"<c([^>]*?)(?:/>|>(.*?)</c>)", row, flags=re.S):
        value = re.search(r"<v>([^<]*)</v>", body or "") or re.search(r"<t[^>]*>([^<]*)</t>", body or "")
        text = value.group(1) if value else ""
        if 't="s"' in attributes and text.isdigit() and int(text) < len(shared):
            text = shared[int(text)]
        cells.append(text.strip())
    return cells


def flatten(value, prefix="", out=None, depth=0):
    """A JSON object's scalar leaves as {'a.b[0].c': value}, three levels and 500 keys at most."""
    out = {} if out is None else out
    if len(out) >= 500:
        return out
    if isinstance(value, dict) and depth < 3:
        for key, inner in value.items():
            flatten(inner, f"{prefix}{key}." if depth < 2 else f"{prefix}{key}", out, depth + 1)
    elif isinstance(value, list) and depth < 3 and value and not isinstance(value[0], (dict, list)):
        out[prefix.rstrip(".")] = json.dumps(value)[:CELL_CHARS]
    elif not isinstance(value, (dict, list)):
        out[prefix.rstrip(".")] = value
    return out


def coco_rows(data):
    """A COCO file's images, each with how many annotations name it and their categories."""
    names = {c.get("id"): str(c.get("name")) for c in data.get("categories") or [] if isinstance(c, dict)}
    counts, kinds = Counter(), defaultdict(set)
    for annotation in data.get("annotations") or []:
        if isinstance(annotation, dict):
            counts[annotation.get("image_id")] += 1
            kinds[annotation.get("image_id")].add(names.get(annotation.get("category_id"), ""))
    for image in data["images"]:
        if isinstance(image, dict):
            row = flatten(image)
            row["n_annotations"] = counts[image.get("id")]
            row["categories"] = ",".join(sorted(k for k in kinds[image.get("id")] if k))
            yield row


def json_rows(path):
    """(kind, rows) for a JSON file: a list of objects, a COCO file's images, or one object."""
    if os.path.getsize(path) > MAX_JSON:
        return "too-large", []
    data = json.loads(Path(path).read_text(encoding="utf-8", errors="replace"))
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return "json-list", (flatten(item) for item in data[:MAX_ROWS])
    if isinstance(data, dict) and isinstance(data.get("images"), list):
        return "coco", coco_rows(data)
    if isinstance(data, dict):
        return "json-object", [flatten(data)]
    return "json-other", []


def table_rows(path, fmt):
    if fmt in ("csv", "tsv"):
        return fmt, csv_rows(path, fmt)
    if fmt == "xlsx":
        return fmt, xlsx_rows(path)
    return json_rows(path)


def is_annotation_table(kind, columns):
    words = {w for c in columns for w in re.split(r"[^a-z0-9]+", str(c).lower()) if w}
    return kind == "coco" or bool(words & ANNOTATION_COLUMNS)


# ---- scan: one task's share of the units -----------------------------------------------------

class Inspector:
    """Reads one file at a time into the rows the part database takes."""

    def __init__(self, all_slices):
        self.all_slices = all_slices
        self.series_seen = set()

    def inspect(self, path, root_id, root_path):
        rel = os.path.relpath(path, root_path)
        name = os.path.basename(path)
        row = {"path": path, "root_id": root_id, "rel": rel, "name": name}
        try:
            status = os.lstat(path)
            row.update(size=status.st_size, mtime=status.st_mtime)
            if os.path.islink(path):
                row.update(role="symlink", format="symlink")
                return row, []
            with open(path, "rb") as handle:
                head = handle.read(HEAD)
            row["format"] = sniff(head, name)
            row["role"] = role_of(rel, row["format"])
            row.update(image_size(path, row["format"], head))
        except (OSError, struct.error, EOFError, ValueError) as error:
            row["error"] = type(error).__name__
            row.setdefault("role", "unreadable")
        row["key"] = key_of(name)
        row["bare"] = bare_of(row["key"])
        elements = self.dicom(path, row) if row.get("format") == "dicom" else []
        return row, elements

    def dicom(self, path, row):
        dataset, error = read_dicom(path)
        if dataset is None:
            row["error"] = error
            return []
        row.update(dicom_wide(dataset))
        series = row.get("series_uid")
        full = (self.all_slices or row.get("modality") in PROJECTION_MODALITIES
                or not series or series not in self.series_seen)
        if series:
            self.series_seen.add(series)
        row["header_full"] = 1 if full else 0
        return list(dicom_elements(dataset)) if full else []


def keys_for(row):
    """(value, via) pairs by which a table's cell may name this file."""
    keys = [(row["key"], "name")] if row.get("key") else []
    keys += [(run, "digits") for run in digit_runs(row.get("key"))]
    for column in ("sop_uid", "series_uid", "study_uid", "patient_id"):
        if row.get(column):
            keys.append((key_of(row[column]) or str(row[column]).lower(), column))
    return [(value, via) for value, via in keys if value and (via == "name" or value != row.get("key"))]


FILE_COLUMNS = ("path", "root_id", "rel", "name", "key", "bare", "size", "mtime", "role", "format",
                "width", "height", "depth", "frames", "channels", "bits", "modality", "body_part",
                "view", "manufacturer", "model", "kvp", "patient_sex", "age_years", "pixel_spacing",
                "study_uid", "series_uid", "sop_uid", "patient_id", "header_full", "error")


def insert_file(db, row, elements):
    values = [row.get(c) for c in FILE_COLUMNS]
    cursor = db.execute(f"INSERT OR IGNORE INTO file ({','.join(FILE_COLUMNS)}) VALUES "
                        f"({','.join('?' * len(FILE_COLUMNS))})", values)
    if not cursor.rowcount:
        return None
    file_id = cursor.lastrowid
    db.executemany("INSERT INTO dicom VALUES (?,?,?,?,?)", [(file_id, *e) for e in elements])
    db.executemany("INSERT INTO key VALUES (?,?,?)", [(file_id, v, via) for v, via in keys_for(row)])
    return file_id


def insert_table(db, file_id, path, fmt):
    try:
        kind, rows = table_rows(path, fmt)
        columns, count, truncated = set(), 0, 0
        cursor = db.execute("INSERT INTO tab (file_id, kind) VALUES (?, ?)", (file_id, kind))
        tab_id = cursor.lastrowid
        for number, row in enumerate(rows):
            if row is None:
                truncated = 1
                break
            count += 1
            columns.update(row)
            db.executemany("INSERT INTO cell VALUES (?,?,?,?,?)", cell_rows(tab_id, number, row))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, csv.Error, RecursionError) as error:
        db.execute("UPDATE file SET error = ? WHERE id = ?", (type(error).__name__, file_id))
        return
    db.execute("UPDATE tab SET columns = ?, rows = ?, truncated = ?, annotation = ? WHERE id = ?",
               (json.dumps(sorted(map(str, columns))[:500]), count, truncated,
                int(is_annotation_table(kind, columns)), tab_id))


def cell_rows(tab_id, number, row):
    for column, value in row.items():
        if value in (None, ""):
            continue
        text = str(value)[:CELL_CHARS]
        yield tab_id, number, str(column)[:200], text, key_of(text)


def root_of(folder, roots, cache):
    """The id and path of the deepest root that holds folder, found once per folder."""
    if folder in cache:
        return cache[folder]
    if folder in roots:
        found = roots[folder]
    else:
        parent = os.path.dirname(folder)
        found = root_of(parent, roots, cache) if parent != folder else (None, folder)
    cache[folder] = found
    return found


def unit_files(kind, path):
    """The files one unit holds: a folder's own files, a whole tree, or one file."""
    if kind == "file":
        yield path
        return
    if kind == "files":
        try:
            yield from sorted(e.path for e in os.scandir(path) if not e.is_dir(follow_symlinks=False))
        except OSError:
            return
        return
    for folder, dirs, files in os.walk(path, followlinks=False):
        dirs.sort()
        for name in sorted(files):
            yield os.path.join(folder, name)


def scan_unit(db, inspector, unit, roots, cache, workers):
    kind, path = unit
    started, count = time.time(), 0
    files = [(f, *root_of(os.path.dirname(f), roots, cache)) for f in unit_files(kind, path)]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = pool.map(lambda item: inspector.inspect(*item), files)
        for (row, elements), item in zip(results, files):
            file_id = insert_file(db, row, elements)
            count += 1
            if file_id and row.get("role") in ("table", "json"):
                insert_table(db, file_id, item[0], row["format"])
    return count, time.time() - started


def open_part(path):
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    return db


def root_ids(rows):
    return {os.path.normpath(r["path"]): (number, os.path.normpath(r["path"])) for number, r in enumerate(rows, 1)}


def read_units(path):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [tuple(line.split("\t", 1)) for line in lines if "\t" in line]


def scan(run, task, tasks, all_slices, workers):
    """Scan every tasks-th unit from task on, each committed with its done line, so a requeued
    task skips what it finished."""
    run = Path(run)
    roots = root_ids(read_roots(run / "roots.tsv"))
    units = read_units(run / "units.tsv")[task::tasks]
    (run / "parts").mkdir(exist_ok=True)
    db = open_part(run / "parts" / f"task-{task:04d}.sqlite")
    done = {row[0] for row in db.execute("SELECT unit FROM done")}
    inspector, cache, total = Inspector(all_slices), {}, 0
    for unit in units:
        name = "\t".join(unit)
        if name in done:
            continue
        count, seconds = scan_unit(db, inspector, unit, roots, cache, workers)
        db.execute("INSERT INTO done VALUES (?,?,?)", (name, count, seconds))
        db.commit()
        total += count
    db.close()
    return len(units), total


# ---- merge: the parts into one file, then the joins ------------------------------------------

def merge(run):
    run = Path(run)
    final = run / "samples.sqlite"
    staging = run / "samples.sqlite.part"
    if staging.exists():
        staging.unlink()
    db = sqlite3.connect(staging)
    db.executescript(SCHEMA)
    db.execute("PRAGMA journal_mode = OFF")
    db.execute("PRAGMA synchronous = OFF")
    db.execute(f"PRAGMA cache_size = {-merge_cache_kib()}")
    insert_roots(db, read_roots(run / "roots.tsv"))
    parts = sorted((run / "parts").glob("task-*.sqlite"))
    for number, part in enumerate(parts, 1):
        merge_part(db, part)
        progress(f"part {number} of {len(parts)} merged")
    db.executescript(INDEXES)
    progress("indexes built")
    join(db)
    db.commit()
    db.close()
    os.replace(staging, final)
    return final


def merge_cache_kib():
    """The page cache the merge may use, in KiB. SQLite's default of 2 MB makes every index build
    and join sort spill to the lab volume, the likeliest reason the first merge on the grid's
    network storage ran past five hours. SAMPLES_CACHE_MB sets it, in ASCII digits; the default,
    32 GB, is half the memory grid/run-samples.sh gives the merge job."""
    megabytes = os.environ.get("SAMPLES_CACHE_MB", "")
    if re.fullmatch(r"[0-9]{1,7}", megabytes):
        return int(megabytes) * 1024
    return 32 * 1024 * 1024


def progress(step):
    """A dated line on stderr, the job's own log, so a long merge shows where it is."""
    print(f"merge: {step} at {time.strftime('%Y-%m-%d %H:%M:%S')}", file=sys.stderr, flush=True)


def insert_roots(db, rows):
    for number, row in enumerate(rows, 1):
        outer = next((n for n, r in enumerate(rows, 1) if r["path"] == row["scanned_as"]), number)
        db.execute("INSERT INTO root VALUES (?,?,?,?,?,?)",
                   (number, row["path"], row["sources"], row["roles"], row["storage"], outer))


def merge_part(db, part):
    """One task's rows, its file ids moved past the ones already in."""
    db.execute("ATTACH DATABASE ? AS part", (str(part),))
    file_shift = db.execute("SELECT COALESCE(MAX(id), 0) FROM file").fetchone()[0]
    tab_shift = db.execute("SELECT COALESCE(MAX(id), 0) FROM tab").fetchone()[0]
    columns = ",".join(FILE_COLUMNS)
    db.execute(f"INSERT OR IGNORE INTO file (id,{columns}) SELECT id + ?, {columns} FROM part.file", (file_shift,))
    db.execute("INSERT INTO dicom SELECT file_id + ?, tag, keyword, vr, value FROM part.dicom", (file_shift,))
    db.execute("INSERT INTO key SELECT file_id + ?, value, via FROM part.key", (file_shift,))
    db.execute("INSERT INTO tab SELECT id + ?, file_id + ?, kind, columns, rows, truncated, annotation FROM part.tab",
               (tab_shift, file_shift))
    db.execute("INSERT INTO cell SELECT tab_id + ?, row, col, value, key FROM part.cell", (tab_shift,))
    db.commit()
    db.execute("DETACH DATABASE part")


JOINS = (
    # A cell names a sample when its key is one a few files carry, so 'lateral' names nothing.
    """INSERT INTO link (file_id, tab_id, row, col, via)
       SELECT k.file_id, c.tab_id, c.row, c.col, k.via FROM cell c JOIN key k ON k.value = c.key
       WHERE c.key IN (SELECT value FROM key GROUP BY value HAVING COUNT(DISTINCT file_id) <= {cap})
         AND k.file_id NOT IN (SELECT file_id FROM tab WHERE id = c.tab_id)""",
    """INSERT INTO annotation (image_id, annotation_id, via)
       SELECT i.id, a.id, CASE WHEN i.root_id = a.root_id THEN 'stem' ELSE 'stem-elsewhere' END
       FROM file i JOIN file a ON a.bare = i.bare
       WHERE i.role = 'image' AND a.role = 'annotation' AND i.id != a.id
         AND i.bare IN (SELECT bare FROM file WHERE bare IS NOT NULL GROUP BY bare HAVING COUNT(*) <= 50)""",
    """INSERT INTO annotation (image_id, annotation_id, via)
       SELECT DISTINCT l.file_id, t.file_id, 'table:' || t.kind FROM link l JOIN tab t ON t.id = l.tab_id
       JOIN file f ON f.id = l.file_id WHERE t.annotation = 1 AND f.role = 'image'""",
    "UPDATE file SET annotated = 1 WHERE id IN (SELECT image_id FROM annotation)",
    "UPDATE file SET header_from = id WHERE header_full = 1",
    """UPDATE file SET header_from = (SELECT MIN(r.id) FROM file r
         WHERE r.series_uid = file.series_uid AND r.header_full = 1)
       WHERE header_from IS NULL AND series_uid IS NOT NULL""",
)


def join(db):
    for number, statement in enumerate(JOINS, 1):
        db.execute(statement.format(cap=MAX_KEY_FILES))
        db.commit()
        progress(f"join {number} of {len(JOINS)} done")


# ---- report: aggregates only -----------------------------------------------------------------

def group_rows(db):
    """Per root group (its sources), the counts the manifest gives, aggregates only."""
    query = """SELECT r.sources, f.role, f.format, COUNT(*), COALESCE(SUM(f.size), 0), SUM(f.annotated)
               FROM file f JOIN root r ON r.id = f.root_id GROUP BY r.sources, f.role, f.format"""
    groups = defaultdict(lambda: {"files": 0, "bytes": 0, "roles": Counter(), "formats": Counter(),
                                  "format_bytes": Counter(), "images": 0, "annotated": 0})
    for sources, role, fmt, count, size, annotated in db.execute(query):
        group = groups[sources]
        group["files"] += count
        group["bytes"] += size
        group["roles"][role] += count
        group["formats"][fmt] += count
        group["format_bytes"][fmt] += size
        if role == "image":
            group["images"] += count
            group["annotated"] += annotated or 0
    return groups


def group_details(db, groups):
    """Shapes, DICOM fill, sex and age decades and table columns for each group."""
    for sources, group in groups.items():
        rows = db.execute("""SELECT MIN(width), MAX(width), MIN(height), MAX(height), COUNT(width),
                             COUNT(DISTINCT series_uid), COUNT(DISTINCT patient_id)
                             FROM file f JOIN root r ON r.id = f.root_id
                             WHERE r.sources = ? AND f.role = 'image'""", (sources,)).fetchone()
        group["shape"] = dict(zip(("width_min", "width_max", "height_min", "height_max", "sized",
                                   "dicom_series", "dicom_patients"), rows))
        group["counts"] = {column: dict(group_counter(db, sources, column)) for column in
                           ("modality", "view", "body_part", "manufacturer", "patient_sex")}
        group["age_decades"] = dict(group_counter(db, sources, "CAST(age_years / 10 AS INTEGER) * 10"))
        group["dicom_tags_filled"] = dict(db.execute(
            """SELECT d.keyword, COUNT(DISTINCT d.file_id) FROM dicom d JOIN file f ON f.id = d.file_id
               JOIN root r ON r.id = f.root_id WHERE r.sources = ? AND d.keyword NOT LIKE '%[%'
               GROUP BY d.keyword ORDER BY 2 DESC LIMIT 60""", (sources,)).fetchall())
        group["tables"] = [{"kind": k, "rows": n, "columns": json.loads(c or "[]")[:60],
                            "annotation": a, "linked_samples": linked}
                           for k, n, c, a, linked in db.execute(
            """SELECT t.kind, t.rows, t.columns, t.annotation,
                      (SELECT COUNT(DISTINCT file_id) FROM link WHERE tab_id = t.id)
               FROM tab t JOIN file f ON f.id = t.file_id JOIN root r ON r.id = f.root_id
               WHERE r.sources = ? ORDER BY t.rows DESC LIMIT 40""", (sources,))]


def group_counter(db, sources, expression):
    return db.execute(f"""SELECT {expression}, COUNT(*) FROM file f JOIN root r ON r.id = f.root_id
                          WHERE r.sources = ? AND f.role = 'image' AND {expression} IS NOT NULL
                          GROUP BY 1 ORDER BY 2 DESC LIMIT 15""", (sources,)).fetchall()


def manifest(db_path):
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    groups = group_rows(db)
    group_details(db, groups)
    db.close()
    return {sources: {k: (dict(v) if isinstance(v, Counter) else v) for k, v in group.items()}
            for sources, group in sorted(groups.items())}


def human(size):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{size} B"
        size /= 1024
    return str(size)


def recorded_annotation(sources_json=ROOT / "data" / "reproduce" / "sources.json"):
    """What the data platform's manifest says of each source's labels, to set beside the scan."""
    try:
        data = json.loads(Path(sources_json).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {s["id"]: ",".join((s.get("annotation") or {}).get("status") or []) for s in data.get("sources", [])}


def markdown(result, recorded=None):
    recorded = recorded_annotation() if recorded is None else recorded
    lines = ["# Sample manifest", "",
             "| sources | files | size | images | annotated | unannotated | main formats | manifest says |",
             "| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |"]
    for sources, g in sorted(result.items(), key=lambda item: -item[1]["bytes"]):
        formats = ", ".join(f"{f} {n}" for f, n in Counter(g["formats"]).most_common(3))
        says = "; ".join(sorted({recorded[s] for s in sources.split(",") if recorded.get(s)}))
        lines.append(f"| {sources} | {g['files']} | {human(g['bytes'])} | {g['images']} | "
                     f"{g['annotated']} | {g['images'] - g['annotated']} | {formats} | {says} |")
    total = sum(g["bytes"] for g in result.values())
    lines += ["", f"{len(result)} groups, {sum(g['files'] for g in result.values())} files, {human(total)}."]
    return "\n".join(lines) + "\n"


def string_keys(value):
    """The manifest with every key a string, a missing one named unknown: a group's formats and
    roles hold None beside names for a file the scan could not open, and json.dumps sorts keys only of
    one type, which failed the first grid merge (job 40702276) after samples.sqlite was whole."""
    if isinstance(value, dict):
        return {("unknown" if key is None else str(key)): string_keys(item) for key, item in value.items()}
    if isinstance(value, list):
        return [string_keys(item) for item in value]
    return value


def report(db_path, out_json=None, out_md=None):
    result = manifest(db_path)
    text = markdown(result)
    if out_json:
        Path(out_json).write_text(json.dumps(string_keys(result), indent=1, sort_keys=True, default=str) + "\n",
                                  encoding="utf-8")
    if out_md:
        Path(out_md).write_text(text, encoding="utf-8")
    return text


# ---- command line ----------------------------------------------------------------------------

def parse(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    roots = sub.add_parser("roots")
    roots.add_argument("--data-root", default=os.environ.get("DATA_ROOT", GRID_DATA))
    roots.add_argument("--sources", default=str(ROOT / "data" / "reproduce" / "sources.json"))
    roots.add_argument("--registry", default=str(ROOT / "data" / "sources"))
    roots.add_argument("--out", required=True)
    units = sub.add_parser("units")
    units.add_argument("--roots", required=True)
    units.add_argument("--out", required=True)
    units.add_argument("--depth", type=int, default=2)
    scan_ = sub.add_parser("scan")
    scan_.add_argument("--run", required=True)
    scan_.add_argument("--task", type=int, required=True)
    scan_.add_argument("--tasks", type=int, required=True)
    scan_.add_argument("--all-slices", action="store_true")
    scan_.add_argument("--workers", type=int, default=8)
    merge_ = sub.add_parser("merge")
    merge_.add_argument("--run", required=True)
    report_ = sub.add_parser("report")
    report_.add_argument("--db", required=True)
    report_.add_argument("--json")
    report_.add_argument("--md")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse(argv)
    if args.command == "roots":
        count = write_roots(gather_roots(args.sources, args.registry, args.data_root), args.out)
        print(f"roots: {count} written to {args.out}")
    elif args.command == "units":
        print(f"units: {write_units(read_roots(args.roots), args.out, args.depth)} written to {args.out}")
    elif args.command == "scan":
        units, files = scan(args.run, args.task, args.tasks, args.all_slices, args.workers)
        print(f"scan: task {args.task} of {args.tasks}: {units} units, {files} files read this time")
    elif args.command == "merge":
        final = merge(args.run)
        print(report(final, Path(args.run) / "MANIFEST.json", Path(args.run) / "MANIFEST.md"))
    else:
        print(report(args.db, args.json, args.md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
