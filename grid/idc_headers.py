"""Read the DICOM header of every instance of a manifest's series from IDC's public bucket, and no pixels.

CTSpine1K's COLONOG vertebra masks were drawn on CT COLONOGRAPHY series whose images the grid no
longer holds (ctspine1k retired 2026-10-31, spine-datasets #379), and a mask sits in the scanner's
frame, where the same exam's localizer is, only through its series' geometry: every slice's
ImagePositionPatient, the orientation, the spacing, the frame of reference. Those are in the
headers, which come before the pixel data in each file. So each instance is read from the start
by an HTTP range request of PREFIX bytes on the public bucket idc-index names (no sign-in, no
token), and kept up to the element (7FE0,0010) Pixel Data, which is never written: a header file of
a few kilobytes in place of a half-megabyte slice.

The size rule (grid/size-rule.sh) is told, before a byte lands, the most this can land: for each
object the bucket lists, the smaller of its size and PREFIX, summed (`--size`). What lands is the
part of that before the pixel data. A series counts as read when the bucket lists as many objects
as the manifest's instanceCount and every one gave a header that ends where its Pixel Data
begins; it is then a line of the landing's fetch/verified.jsonl, the state acquisition_fetch.py
keeps and grid/fetch_size.py reads, so a second run reads only the rest. A file whose header runs
past PREFIX is reported and its series left unverified, never cut short.

    python grid/idc_headers.py --manifest <landing>/meta/ctc_masked.csv --landing <landing> --size
    python grid/idc_headers.py --manifest <landing>/meta/ctc_masked.csv --landing <landing>

Each header lands as raw/<collection>/<PatientID>/<SeriesInstanceUID>/<object name>hdr, the
object's name with "hdr" after its ".dcm", so nothing that looks for images takes it for one;
pydicom reads it as it is (it keeps the preamble and the file meta). Standard library alone; runs in
a Slurm job on a compute node.
"""

import argparse
import concurrent.futures
import csv
import json
import os
import struct
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from xml.etree import ElementTree

# What is read of each object: CT COLONOGRAPHY's headers measured 1,890 to 1,896 bytes on 24 instances
# of 4 series (2026-11-02), so 16 KiB holds a header eight times as long; one longer is reported.
PREFIX = 1 << 14
S3_NAMESPACE = "{http://s3.amazonaws.com/doc/2006-03-01/}"
PIXEL_DATA = (0x7FE0, 0x0010)
ITEM, ITEM_END, SEQUENCE_END = (0xFFFE, 0xE000), (0xFFFE, 0xE00D), (0xFFFE, 0xE0DD)
UNDEFINED = 0xFFFFFFFF
# The VRs whose explicit-VR length is four bytes after two reserved ones (PS3.5 section 7.1.2).
LONG_VRS = {b"OB", b"OD", b"OF", b"OL", b"OV", b"OW", b"SQ", b"SV", b"UC", b"UN", b"UR", b"UT", b"UV"}
IMPLICIT_LITTLE = "1.2.840.10008.1.2"
EXPLICIT_BIG = "1.2.840.10008.1.2.2"


class Truncated(Exception):
    """The bytes read end before the Pixel Data element begins."""


class NotDicom(Exception):
    """The bytes are no DICOM Part 10 file this reader can walk."""


def bucket_listing_url(series_aws_url, token=None):
    """The public S3 listing of one series' prefix, from idc-index's s3://<bucket>/<uuid>/* form."""
    if not series_aws_url.startswith("s3://"):
        raise ValueError(f"not an s3 address: {series_aws_url}")
    bucket, _, prefix = series_aws_url[5:].partition("/")
    query = {"list-type": "2", "prefix": prefix.rstrip("*")}
    if token:
        query["continuation-token"] = token
    return f"https://{bucket}.s3.amazonaws.com/?" + urllib.parse.urlencode(query)


def parse_listing(xml_bytes):
    """[(key, size)], and the continuation token where the listing goes on."""
    root = ElementTree.fromstring(xml_bytes)
    objects = [(item.findtext(S3_NAMESPACE + "Key"), int(item.findtext(S3_NAMESPACE + "Size")))
               for item in root.findall(S3_NAMESPACE + "Contents")]
    more = root.findtext(S3_NAMESPACE + "IsTruncated") == "true"
    return objects, (root.findtext(S3_NAMESPACE + "NextContinuationToken") if more else None)


def get(url, byte_range=None, tries=5):
    request = urllib.request.Request(url)
    if byte_range is not None:
        request.add_header("Range", f"bytes={byte_range[0]}-{byte_range[1]}")
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(request, timeout=120) as answer:
                return answer.read()
        except OSError:
            if attempt == tries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    raise AssertionError("unreachable")


def list_series(series_aws_url, fetch=get):
    """Every object under a series' prefix, as (key, size), following continuation tokens."""
    objects, token = [], None
    while True:
        page, token = parse_listing(fetch(bucket_listing_url(series_aws_url, token)))
        objects += page
        if not token:
            return objects


def transfer_syntax(data):
    """The file meta's TransferSyntaxUID and the offset where the data set begins."""
    if len(data) < 132:
        raise Truncated("shorter than the preamble")
    if data[128:132] != b"DICM":
        raise NotDicom("no DICM after the preamble")
    at, syntax = 132, None
    while True:
        if at + 8 > len(data):
            raise Truncated("inside the file meta")
        group, element = struct.unpack_from("<HH", data, at)
        if group != 0x0002:
            return syntax, at
        vr = data[at + 4:at + 6]
        if vr in LONG_VRS:
            if at + 12 > len(data):
                raise Truncated("inside the file meta")
            length, start = struct.unpack_from("<I", data, at + 8)[0], at + 12
        else:
            length, start = struct.unpack_from("<H", data, at + 6)[0], at + 8
        if element == 0x0010:
            syntax = data[start:start + length].rstrip(b"\x00 ").decode("ascii", "replace")
        at = start + length


def element_header(data, at, explicit, big):
    """(tag, vr, value length, offset of the value) of the element at `at`."""
    order = ">" if big else "<"
    if at + 8 > len(data):
        raise Truncated("inside an element's header")
    group, element = struct.unpack_from(order + "HH", data, at)
    tag = (group, element)
    if tag in (ITEM, ITEM_END, SEQUENCE_END) or not explicit:
        # Items and delimiters have no VR in any syntax; group FFFE is always little-endian's here
        # only in a little-endian file, which is every file IDC serves of these collections.
        return tag, None, struct.unpack_from(order + "I", data, at + 4)[0], at + 8
    vr = data[at + 4:at + 6]
    if vr in LONG_VRS:
        if at + 12 > len(data):
            raise Truncated("inside an element's header")
        return tag, vr, struct.unpack_from(order + "I", data, at + 8)[0], at + 12
    return tag, vr, struct.unpack_from(order + "H", data, at + 6)[0], at + 8


def skip_undefined(data, at, explicit, big, vr):
    """The offset just past an element of undefined length whose value starts at `at`."""
    if vr == b"UN":
        explicit = False  # PS3.5 section 6.2.2: an undefined-length UN holds implicit little-endian
    while True:
        tag, _, length, start = element_header(data, at, False, big)
        if tag == SEQUENCE_END:
            return start
        if tag != ITEM:
            raise NotDicom("a sequence of undefined length holds no item")
        at = skip_item(data, start, length, explicit, big)


def skip_item(data, start, length, explicit, big):
    """The offset just past an item whose value starts at `start`."""
    if length != UNDEFINED:
        return start + length
    at = start
    while True:
        tag, vr, value_length, value_at = element_header(data, at, explicit, big)
        if tag == ITEM_END:
            return value_at
        at = (skip_undefined(data, value_at, explicit, big, vr) if value_length == UNDEFINED
              else value_at + value_length)


def header_end(data):
    """Where the top-level Pixel Data element begins: the bytes before it are the header.

    Raises Truncated where `data` ends first and NotDicom where it is no file this walk reads."""
    syntax, at = transfer_syntax(data)
    if syntax is None:
        raise NotDicom("the file meta names no transfer syntax")
    if syntax.startswith("1.2.840.10008.1.2.1.99"):
        raise NotDicom("a deflated data set")
    explicit, big = syntax != IMPLICIT_LITTLE, syntax == EXPLICIT_BIG
    while True:
        tag, vr, length, value_at = element_header(data, at, explicit, big)
        if tag == PIXEL_DATA:
            return at
        at = skip_undefined(data, value_at, explicit, big, vr) if length == UNDEFINED else value_at + length
        if at > len(data):
            raise Truncated("an element runs past what was read")


def manifest_rows(path):
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def verified(landing):
    path = landing / "fetch" / "verified.jsonl"
    if not path.exists():
        return set()
    return {json.loads(line)["unit"] for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def listings(rows, landing, fetch=get):
    """Every series' objects, read once and kept in meta/listings.jsonl, so the size and the read agree."""
    cache = landing / "meta" / "listings.jsonl"
    known = {}
    if cache.exists():
        for line in cache.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entry = json.loads(line)
                known[entry["series"]] = [tuple(o) for o in entry["objects"]]
    cache.parent.mkdir(parents=True, exist_ok=True)
    with cache.open("a", encoding="utf-8") as handle:
        for row in rows:
            uid = row["SeriesInstanceUID"]
            if uid not in known:
                known[uid] = list_series(row["series_aws_url"], fetch)
                handle.write(json.dumps({"series": uid, "objects": known[uid]}) + "\n")
    return known


def bound(objects, prefix=PREFIX):
    return sum(min(size, prefix) for _, size in objects)


def size_line(rows, known, done, prefix=PREFIX):
    total = sum(bound(known[r["SeriesInstanceUID"]], prefix) for r in rows)
    need = sum(bound(known[r["SeriesInstanceUID"]], prefix) for r in rows if r["SeriesInstanceUID"] not in done)
    count = sum(len(known[r["SeriesInstanceUID"]]) for r in rows)
    return f"{total} {need} {len(rows)} series of {count} objects listed by IDC's bucket, read up to {prefix} bytes each"


def object_url(series_aws_url, key):
    bucket = series_aws_url[5:].partition("/")[0]
    return f"https://{bucket}.s3.amazonaws.com/{urllib.parse.quote(key)}"


def read_header(url, size, prefix=PREFIX, fetch=get):
    """The header of one object: its bytes before Pixel Data, read with one range request."""
    data = fetch(url, (0, min(size, prefix) - 1))
    return data[:header_end(data)]


def read_series(row, objects, landing, prefix=PREFIX, fetch=get, workers=16):
    """Write every header of one series; returns (headers, bytes, problems)."""
    folder = landing / "raw" / row["collection"] / row["PatientID"] / row["SeriesInstanceUID"]
    folder.mkdir(parents=True, exist_ok=True)
    problems, written, headers = [], 0, 0

    def one(item):
        key, size = item
        name = key.rsplit("/", 1)[-1] + "hdr"
        target = folder / name
        if target.exists() and target.stat().st_size > 0:
            return target.stat().st_size, None
        try:
            header = read_header(object_url(row["series_aws_url"], key), size, prefix, fetch)
        except (Truncated, NotDicom, OSError) as why:
            return 0, f"{name}: {type(why).__name__}: {why}"
        partial = target.with_name(name + ".part")
        partial.write_bytes(header)
        os.replace(partial, target)
        return len(header), None

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for nbytes, problem in pool.map(one, objects):
            if problem:
                problems.append(problem)
            else:
                written += nbytes
                headers += 1
    if len(objects) != int(row["instanceCount"]):
        problems.append(f"the bucket lists {len(objects)} objects, the manifest {row['instanceCount']}")
    return headers, written, problems


def record(landing, name, entry):
    path = landing / "fetch" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")


def run(rows, known, landing, prefix=PREFIX, fetch=get, workers=16):
    """Read every series not yet verified; returns how many are left unverified."""
    done = verified(landing)
    left = 0
    for number, row in enumerate(rows, 1):
        uid = row["SeriesInstanceUID"]
        if uid in done:
            continue
        headers, nbytes, problems = read_series(row, known[uid], landing, prefix, fetch, workers)
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        if problems:
            left += 1
            record(landing, "failed.jsonl", {"unit": uid, "t": stamp, "why": "; ".join(problems)[:800]})
        else:
            record(landing, "verified.jsonl", {"unit": uid, "t": stamp, "patient": row["PatientID"],
                                               "coll": row["collection"], "n_headers": headers, "bytes": nbytes})
        if number % 50 == 0:
            print(f"idc_headers: {number}/{len(rows)} series tried, {left} left unverified", flush=True)
    return left


def main(argv=None, fetch=get):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--landing", required=True, type=Path)
    parser.add_argument("--size", action="store_true", help="print the most this can land, for the size rule")
    parser.add_argument("--prefix", type=int, default=PREFIX, help="the bytes read from the start of each object")
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args(argv)
    rows = manifest_rows(args.manifest)
    if not rows or any(not r.get("series_aws_url") for r in rows):
        print("no exact size; a series of the manifest has no bucket address")
        return 3
    try:
        known = listings(rows, args.landing, fetch)
    except (OSError, ElementTree.ParseError, ValueError) as why:
        print(f"the source did not answer; the bucket's listing failed: {why}")
        return 2
    if args.size:
        print(size_line(rows, known, verified(args.landing), args.prefix))
        return 0
    left = run(rows, known, args.landing, args.prefix, fetch, args.workers)
    print(f"idc_headers: {len(rows) - left} of {len(rows)} series verified, {left} left (fetch/failed.jsonl says why)")
    return 0 if left == 0 else 3


if __name__ == "__main__":
    sys.exit(main())
