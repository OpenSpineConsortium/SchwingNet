"""Measure the column from the segmented CTs: each pair's spacing and how many bodies a column has.

Usage (inside the train-cpu environment, on the grid, one CPU job):
    python tools/chain_stats.py --totalseg <root> [--totalseg <root> ...] --verse <root> [...] \
        [--columns <calls.csv> ...] --out <prior.json> [--records <records.jsonl>]

docs/research/ct-priors-for-2d-detection.md, item 1. For every segmented CT it finds each
vertebra's craniocaudal centroid and extent in millimetres (the 5th to 95th percentile of its
voxels along the scanner's z, through the image's affine), then, for each pair of neighbouring
levels, the ratio of the centroids' gap to the pair's mean extent. src/schwingnet/chain.py's
fit_spacing turns each pair's ratios into a log-normal law. A column's thoracic and lumbar counts
are read only from a CT that holds both T1 and the sacrum, the one case where a count is whole.

Two layouts are read, the two the grid's CTs come in: TotalSegmentator's folder of one mask per
structure (vertebrae_L1.nii.gz, ..., sacrum.nii.gz), and VerSe's one label map per scan
(*_seg-vert_msk.nii.gz, 1 to 7 cervical, 8 to 19 T1 to T12, 20 to 24 L1 to L5, 25 L6, 26 the
sacrum, 28 T13). Another source's layout is added as a third reader here when its labels are
confirmed.

The anomalies are labelled on CT, where a sixth lumbar or a thirteenth thoracic body is seen whole
and counted from C2 down, and that labelling is the prior's: --columns takes CSV files of a
reader's calls, one row per scan with the columns scan, column (T12L5, T12L6, T13L5, ...) and
reader, such as the anomaly harvest's census or the owner's own reads. A call names the scan's
column even where the segmentation is cut short of T1 or the sacrum, so the column odds come from
every scan a reader called, and a called scan's measured pairs (L6|sacrum, T13|L1) are fitted
from the very CTs that show them; the X-ray decoder then weighs a transitional column by what the
CTs saw. A call a reader marked other than a column name is counted nowhere. NIfTI-1 is read with numpy alone, so no reader joins the environment. What is written
is aggregates and per-scan level geometry with no identifier but the file's own name, which stays
on the grid: only the prior's JSON, which holds means and spreads, comes back to the repository.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[0] = str(ROOT / "src")

import argparse  # noqa: E402
import csv  # noqa: E402
import gzip  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import struct  # noqa: E402
from collections import defaultdict  # noqa: E402

import numpy as np  # noqa: E402
from schwingnet.chain import SACRUM, column, fit_spacing, hypothesis_name, pair_key  # noqa: E402

DTYPES = {2: "u1", 4: "i2", 8: "i4", 16: "f4", 64: "f8", 256: "i1", 512: "u2", 768: "u4"}
VERSE = {**{i: f"C{i}" for i in range(1, 8)}, **{7 + i: f"T{i}" for i in range(1, 13)},
         **{19 + i: f"L{i}" for i in range(1, 6)}, 25: "L6", 26: SACRUM, 28: "T13"}
ORDER = column(13, 6)


def read_nifti(path):
    """The voxel array and the 4x4 voxel-to-millimetre affine of a NIfTI-1 file."""
    raw = Path(path).read_bytes()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    endian = "<" if struct.unpack("<i", raw[:4])[0] == 348 else ">"
    dims = struct.unpack(endian + "8h", raw[40:56])
    datatype = struct.unpack(endian + "h", raw[70:72])[0]
    pixdim = struct.unpack(endian + "8f", raw[76:108])
    offset = int(struct.unpack(endian + "f", raw[108:112])[0])
    slope, inter = struct.unpack(endian + "2f", raw[112:120])
    sform_code = struct.unpack(endian + "h", raw[254:256])[0]
    shape = tuple(int(d) for d in dims[1 : 1 + dims[0]])[:3]
    data = np.frombuffer(raw, dtype=endian + DTYPES[datatype], count=int(np.prod(shape)), offset=offset)
    data = data.reshape(shape, order="F")
    if slope not in (0.0, 1.0) or inter != 0.0:
        data = data * slope + inter
    if sform_code > 0:
        rows = [struct.unpack(endian + "4f", raw[280 + 16 * k : 296 + 16 * k]) for k in range(3)]
        affine = np.array([*rows, (0, 0, 0, 1)], dtype=float)
    else:
        affine = np.diag([pixdim[1], pixdim[2], pixdim[3], 1.0])
    return data, affine


def z_extent(mask, affine):
    """A structure's craniocaudal centroid and extent in millimetres, or None when it is empty."""
    voxels = np.argwhere(mask)
    if len(voxels) < 20:
        return None
    z = voxels @ affine[2, :3] + affine[2, 3]
    low, high = np.percentile(z, [5, 95])
    return float(z.mean()), float(high - low)


def totalseg_scan(folder):
    levels = {}
    for name in ORDER:
        stem = "sacrum" if name == SACRUM else f"vertebrae_{name}"
        for candidate in (folder / f"{stem}.nii.gz", folder / f"{stem}.nii"):
            if candidate.exists():
                data, affine = read_nifti(candidate)
                found = z_extent(data > 0, affine)
                if found:
                    levels[name] = found
                break
    return levels


def verse_scan(path):
    data, affine = read_nifti(path)
    labels = np.rint(data).astype(int)
    levels = {}
    for value, name in VERSE.items():
        found = z_extent(labels == value, affine)
        if found:
            levels[name] = found
    return levels


def scans(totalseg_roots, verse_roots):
    """Each scan's name and its levels' (centroid, extent), the scan's own folder or file name."""
    for root in totalseg_roots:
        for folder in sorted(Path(root).rglob("segmentations")):
            if folder.is_dir():
                yield str(folder.parent.name), totalseg_scan(folder)
    for root in verse_roots:
        for path in sorted(Path(root).rglob("*_seg-vert_msk.nii*")):
            yield path.name.split("_seg-vert")[0], verse_scan(path)


def neighbours(upper, lower):
    """Whether lower comes right after upper in some column: the next number, or a region's start."""
    if ORDER.index(lower) - ORDER.index(upper) == 1:
        return True
    return (upper.startswith("T") and lower == "L1") or (upper.startswith("L") and lower == SACRUM)


def pair_ratios(levels):
    """Each neighbouring pair's gap over mean extent, along the order the levels present give."""
    present = [n for n in ORDER if n in levels]
    found = {}
    for upper, lower in zip(present, present[1:]):
        if not neighbours(upper, lower):
            continue
        (zu, eu), (zl, el) = levels[upper], levels[lower]
        gap, height = abs(zu - zl), 0.5 * (eu + el)
        if gap > 0 and height > 0:
            found[pair_key(upper, lower)] = gap / height
    return found


def count_of(levels):
    """The column's name when the scan holds it whole, from T1 to the sacrum; else None."""
    if "T1" not in levels or SACRUM not in levels:
        return None
    thoracic = sum(1 for n in levels if n.startswith("T"))
    lumbar = sum(1 for n in levels if n.startswith("L"))
    if 11 <= thoracic <= 13 and 4 <= lumbar <= 6:
        return hypothesis_name(thoracic, lumbar)
    return None


def read_calls(paths):
    """Each called scan's column, from readers' CSV files; a later file's call wins."""
    valid = {hypothesis_name(t, n) for t in (11, 12, 13) for n in (4, 5, 6)}
    calls = {}
    for path in paths:
        with open(path, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                column_name = (row.get("column") or "").strip()
                if column_name in valid and row.get("scan"):
                    calls[row["scan"].strip()] = column_name
    return calls


def fit(records, smoothing):
    ratios = defaultdict(list)
    counts = defaultdict(int)
    for record in records:
        for key, value in record["ratios"].items():
            ratios[key].append(value)
        if record["column"]:
            counts[record["column"]] += 1
    spacing = {k: fit_spacing(v).__dict__ for k, v in sorted(ratios.items()) if len(v) >= 5}
    pooled = [v for values in ratios.values() for v in values]
    fallback = fit_spacing(pooled).__dict__ if len(pooled) >= 2 else {"mu": math.log(1.3), "sigma": 0.15}
    names = [hypothesis_name(t, n) for t in (11, 12, 13) for n in (4, 5, 6)]
    total = sum(counts.values()) + smoothing * len(names)
    columns = {n: (counts[n] + smoothing) / total for n in names}
    return {
        "spacing": spacing,
        "fallback": fallback,
        "columns": columns,
        "scans": len(records),
        "whole_columns": {k: v for k, v in sorted(counts.items()) if v},
        "pairs_measured": {k: len(v) for k, v in sorted(ratios.items())},
    }


def parse(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--totalseg", action="append", default=[], help="a TotalSegmentator root")
    parser.add_argument("--verse", action="append", default=[], help="a VerSe-layout root")
    parser.add_argument("--columns", action="append", default=[], help="CSV of CT column calls")
    parser.add_argument("--out", required=True, help="the prior's JSON")
    parser.add_argument("--records", help="per-scan level geometry, JSON lines, kept on the grid")
    parser.add_argument("--smoothing", type=float, default=1.0, help="add-k counts per column")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse(argv)
    records = []
    sink = open(args.records, "w", encoding="utf-8") if args.records else None
    calls = read_calls(args.columns)
    for name, levels in scans(args.totalseg, args.verse):
        column_name = calls.pop(name, None) or count_of(levels)
        record = {"scan": name, "levels": levels, "ratios": pair_ratios(levels), "column": column_name}
        records.append(record)
        if sink:
            sink.write(json.dumps(record, sort_keys=True) + "\n")
    if sink:
        sink.close()
    records += [{"scan": n, "levels": {}, "ratios": {}, "column": c} for n, c in sorted(calls.items())]
    prior = fit(records, args.smoothing)
    Path(args.out).write_text(json.dumps(prior, indent=1, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"scans": prior["scans"], "whole_columns": prior["whole_columns"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
