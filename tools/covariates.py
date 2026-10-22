"""Census of the variables each source carries beside its images: age, sex, pathology, device.

Usage (inside the train-cpu environment, on the grid, one CPU job per source or one for all):
    python tools/covariates.py --source <name>=<root> [--source ...] --out <census.json>
        [--sample 500]

The owner's ask of 2026-10-21 20:12 UTC: check every dataset for pathology, age or anything else
that could be a variable, in the files that came with it, in its paper's supplements and in the
image metadata such as DICOM headers (docs/research/xr-annotation-format.md, section 7). This
tool does the two parts a machine can do on the grid. For DICOM it reads the headers of a sample
of each source's files, never the pixels, and counts how often each tag of interest is filled and
which values it takes, the values only for tags that cannot name a person (sex, view, body part,
manufacturer, model, kVp ranges) and only as counts; age is reported as decade counts, never a
value per file. For the files that came with the source it lists every table (CSV, TSV, XLSX)
and JSON with its column names and row count, so a person reads which variables exist without
the rows leaving the grid. The paper's supplements are read by a person or a session from the
inventory's links and recorded beside this census, since the grid does not reach the publishers.
What it writes is aggregates and column names only; no identifier, no date, no free text.
"""

import argparse
import csv
import json
import random
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

# Tags whose values are counted: none of them names a person.
COUNTED = ("PatientSex", "ViewPosition", "BodyPartExamined", "Manufacturer", "ManufacturerModelName",
           "Modality", "ImageLaterality", "PhotometricInterpretation")
# Tags whose presence is counted and whose values are reduced before counting.
REDUCED = ("PatientAge", "PatientBirthDate", "KVP", "Exposure", "ExposureInmAs", "DistanceSourceToDetector",
           "ImagerPixelSpacing", "PixelSpacing")
# Tags whose presence alone is counted, since their values are free text or identify.
PRESENT = ("StudyDescription", "SeriesDescription", "ProtocolName", "AcquisitionDeviceProcessingDescription",
           "PatientWeight", "PatientSize", "EthnicGroup", "AdditionalPatientHistory", "ReasonForStudy",
           "RequestedProcedureDescription")
TABLES = (".csv", ".tsv", ".xlsx", ".xls")
DICOM_SUFFIXES = (".dcm", ".dicom", "")


def age_decade(value):
    """A DICOM age string (045Y, 006M) as a decade label, or None when it cannot be read."""
    text = str(value).strip().upper()
    if len(text) != 4 or not text[:3].isdigit():
        return None
    number, unit = int(text[:3]), text[3]
    years = {"Y": number, "M": number / 12, "W": number / 52, "D": number / 365}.get(unit)
    if years is None:
        return None
    return f"{int(years // 10) * 10}s"


def reduce_value(tag, value):
    if tag == "PatientAge":
        return age_decade(value)
    if tag == "PatientBirthDate":
        return "present"
    if tag == "KVP":
        try:
            return f"{int(float(value) // 10) * 10} kV"
        except (TypeError, ValueError):
            return None
    return "present"


def dicom_files(root, sample, seed):
    """A seeded sample of the files under root that may be DICOM, by suffix or by no suffix."""
    found = [p for p in Path(root).rglob("*") if p.is_file() and p.suffix.lower() in DICOM_SUFFIXES]
    random.Random(seed).shuffle(found)
    return found[:sample]


def read_header(pydicom, path):
    try:
        return pydicom.dcmread(str(path), stop_before_pixels=True)
    except Exception:  # pydicom raises several kinds for a file that is not DICOM
        return None


def dicom_census(root, sample, seed):
    import pydicom

    filled = Counter()
    values = defaultdict(Counter)
    read = 0
    for path in dicom_files(root, sample, seed):
        header = read_header(pydicom, path)
        if header is None:
            continue
        read += 1
        for tag in COUNTED + REDUCED + PRESENT:
            value = getattr(header, tag, None)
            if value in (None, ""):
                continue
            filled[tag] += 1
            if tag in COUNTED:
                values[tag][str(value).strip()[:40]] += 1
            elif tag in REDUCED:
                reduced = reduce_value(tag, value)
                if reduced:
                    values[tag][reduced] += 1
    return {"headers_read": read, "filled": dict(sorted(filled.items())),
            "values": {k: dict(v.most_common(20)) for k, v in sorted(values.items())}}


def table_columns(path):
    """A table's column names and row count, read without keeping a row."""
    suffix = path.suffix.lower()
    if suffix in (".csv", ".tsv"):
        with open(path, newline="", encoding="utf-8", errors="replace") as handle:
            reader = csv.reader(handle, delimiter="\t" if suffix == ".tsv" else ",")
            header = next(reader, [])
            rows = sum(1 for _ in reader)
        return {"columns": [h.strip()[:60] for h in header][:200], "rows": rows}
    if suffix == ".xlsx":
        return xlsx_columns(path)
    return {"columns": [], "rows": None, "note": "old Excel format, read by hand"}


def xlsx_columns(path):
    """The first sheet's first row, from the workbook's XML, with no spreadsheet library."""
    import re

    with zipfile.ZipFile(path) as book:
        names = book.namelist()
        shared = []
        if "xl/sharedStrings.xml" in names:
            shared = re.findall(r"<t[^>]*>([^<]*)</t>", book.read("xl/sharedStrings.xml").decode("utf-8", "replace"))
        sheet = book.read("xl/worksheets/sheet1.xml").decode("utf-8", "replace")
    rows = re.findall(r"<row[^>]*>(.*?)</row>", sheet, flags=re.S)
    if not rows:
        return {"columns": [], "rows": 0}
    cells = re.findall(r'<c[^>]*?(t="s")?[^>]*>(?:<f>[^<]*</f>)?<v>([^<]*)</v>', rows[0])
    header = [shared[int(v)] if t and v.isdigit() and int(v) < len(shared) else v for t, v in cells]
    return {"columns": [h.strip()[:60] for h in header][:200], "rows": len(rows) - 1}


def json_keys(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (ValueError, OSError):
        return {"keys": [], "note": "not read"}
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return {"keys": sorted(data[0])[:200], "items": len(data)}
    if isinstance(data, dict):
        return {"keys": sorted(data)[:200]}
    return {"keys": []}


def side_files(root, limit=200):
    """Every table and the small JSON files that came with the source, with their columns."""
    found = {}
    for path in sorted(Path(root).rglob("*")):
        if len(found) >= limit:
            break
        if not path.is_file():
            continue
        name = str(path.relative_to(root))
        if path.suffix.lower() in TABLES:
            try:
                found[name] = table_columns(path)
            except (OSError, zipfile.BadZipFile, KeyError, csv.Error) as error:
                found[name] = {"note": f"not read: {type(error).__name__}"}
        elif path.suffix.lower() == ".json" and path.stat().st_size < 50_000_000 and "meta" not in path.parts:
            found[name] = json_keys(path)
    return found


def parse(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", action="append", required=True, help="name=root")
    parser.add_argument("--out", required=True)
    parser.add_argument("--sample", type=int, default=500)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--no-dicom", action="store_true", help="tables only, where pydicom is missing")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse(argv)
    census = {}
    for item in args.source:
        name, _, root = item.partition("=")
        entry = {"tables_and_json": side_files(root)}
        if not args.no_dicom:
            entry["dicom"] = dicom_census(root, args.sample, args.seed)
        census[name] = entry
    Path(args.out).write_text(json.dumps(census, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: v.get("dicom", {}).get("headers_read") for k, v in census.items()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
