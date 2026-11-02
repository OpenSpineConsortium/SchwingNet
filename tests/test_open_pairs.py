"""The open paired sets' fetch (grid/series_select.py, grid/idc_headers.py, grid/open-pairs.sbatch).

The selections are rules applied on the grid to the catalogue, so they are tested here on rows of
the catalogue's shape; the header reader is tested on DICOM files built byte by byte in the three
shapes it must walk past to reach the Pixel Data: explicit VR with a sequence of undefined length,
implicit VR, and a private UN of undefined length."""

import csv
import importlib.util
import json
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

GRID = Path(__file__).resolve().parent.parent / "grid"


def load(name):
    spec = importlib.util.spec_from_file_location(name, GRID / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


select = load("series_select")
headers = load("idc_headers")

EXPLICIT = "1.2.840.10008.1.2.1"
IMPLICIT = "1.2.840.10008.1.2"
LONG = {b"OB", b"OW", b"SQ", b"UN", b"UT"}


def explicit_element(group, element, vr, value):
    head = struct.pack("<HH", group, element) + vr
    if vr in LONG:
        return head + b"\x00\x00" + struct.pack("<I", len(value)) + value
    return head + struct.pack("<H", len(value)) + value


def implicit_element(group, element, value, length=None):
    return struct.pack("<HHI", group, element, len(value) if length is None else length) + value


def item(body, undefined=True):
    if undefined:
        return struct.pack("<HHI", 0xFFFE, 0xE000, 0xFFFFFFFF) + body + struct.pack("<HHI", 0xFFFE, 0xE00D, 0)
    return struct.pack("<HHI", 0xFFFE, 0xE000, len(body)) + body


SEQUENCE_END = struct.pack("<HHI", 0xFFFE, 0xE0DD, 0)


def part10(syntax, dataset):
    uid = syntax.encode() + (b"\x00" if len(syntax) % 2 else b"")
    meta = explicit_element(0x0002, 0x0010, b"UI", uid)
    meta = explicit_element(0x0002, 0x0000, b"UL", struct.pack("<I", len(meta))) + meta
    return b"\x00" * 128 + b"DICM" + meta + dataset


def pixels(explicit=True):
    data = b"\x07" * 4096
    if explicit:
        return explicit_element(0x7FE0, 0x0010, b"OW", data)
    return implicit_element(0x7FE0, 0x0010, data)


def explicit_file():
    nested = explicit_element(0x0008, 0x0100, b"SH", b"T-D1100 ")
    inner_sq = (struct.pack("<HH", 0x0040, 0xA730) + b"SQ\x00\x00" + struct.pack("<I", 0xFFFFFFFF)
                + item(nested) + SEQUENCE_END)
    outer = (struct.pack("<HH", 0x0008, 0x1140) + b"SQ\x00\x00" + struct.pack("<I", 0xFFFFFFFF)
             + item(inner_sq) + item(nested, undefined=False) + SEQUENCE_END)
    private_un = (struct.pack("<HH", 0x0029, 0x1010) + b"UN\x00\x00" + struct.pack("<I", 0xFFFFFFFF)
                  + item(implicit_element(0x0029, 0x0010, b"ab")) + SEQUENCE_END)
    head = (explicit_element(0x0008, 0x0060, b"CS", b"CT")
            + outer + private_un
            + explicit_element(0x0020, 0x0032, b"DS", b"-200\\-180\\-1234.5 ")
            + explicit_element(0x0028, 0x0010, b"US", struct.pack("<H", 512)))
    return part10(EXPLICIT, head), len(part10(EXPLICIT, head))


def implicit_file():
    sq = implicit_element(0x0008, 0x1140, item(implicit_element(0x0008, 0x1155, b"1.2.3\x00")) + SEQUENCE_END,
                          length=0xFFFFFFFF)
    head = implicit_element(0x0008, 0x0060, b"CT") + sq + implicit_element(0x0020, 0x0032, b"0\\0\\-10 ")
    return part10(IMPLICIT, head), len(part10(IMPLICIT, head))


class HeaderEnd(unittest.TestCase):
    def test_explicit_vr_with_nested_undefined_sequences_and_a_private_un(self):
        head, end = explicit_file()
        self.assertEqual(headers.header_end(head + pixels()), end)

    def test_implicit_vr_with_a_sequence_of_undefined_length(self):
        head, end = implicit_file()
        self.assertEqual(headers.header_end(head + pixels(explicit=False)), end)

    def test_a_read_that_ends_before_the_pixels_is_truncated_not_cut(self):
        head, end = explicit_file()
        for cut in (100, 140, end - 3, end):
            with self.subTest(cut=cut), self.assertRaises(headers.Truncated):
                headers.header_end((head + pixels())[:cut])

    def test_a_file_that_is_no_part10_file_is_refused(self):
        with self.assertRaises(headers.NotDicom):
            headers.header_end(b"\x00" * 128 + b"NOPE" + b"\x00" * 64)


LISTING = """<?xml version="1.0" encoding="UTF-8"?>
<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><Name>idc-open-data</Name>
<Prefix>uuid-1/</Prefix><KeyCount>2</KeyCount><IsTruncated>{more}</IsTruncated>{token}
<Contents><Key>uuid-1/{a}.dcm</Key><Size>{size}</Size></Contents>
<Contents><Key>uuid-1/{b}.dcm</Key><Size>{size}</Size></Contents>
</ListBucketResult>"""


class FakeBucket:
    """A bucket of one series in two pages of two objects each, every object the same file."""

    def __init__(self, body):
        self.body = body
        self.ranges = []

    def __call__(self, url, byte_range=None):
        if "list-type=2" in url:
            if "continuation-token" in url:
                page = LISTING.format(more="false", token="", a="i3", b="i4", size=len(self.body))
            else:
                page = LISTING.format(more="true", token="<NextContinuationToken>t1</NextContinuationToken>",
                                      a="i1", b="i2", size=len(self.body))
            return page.encode()
        self.ranges.append(byte_range)
        return self.body[byte_range[0]:byte_range[1] + 1]


class ReadHeaders(unittest.TestCase):
    def manifest(self, folder, count):
        path = Path(folder) / "m.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=select.FIELDS)
            writer.writeheader()
            writer.writerow({"collection": "ct_colonography", "PatientID": "P1", "SeriesInstanceUID": "1.2.3",
                             "instanceCount": count, "series_bytes": 1, "series_aws_url": "s3://idc-open-data/uuid-1/*"})
        return path

    def test_the_size_is_the_listed_objects_up_to_the_prefix_and_the_read_keeps_no_pixels(self):
        head, end = explicit_file()
        bucket = FakeBucket(head + pixels())
        with tempfile.TemporaryDirectory() as folder:
            landing = Path(folder) / "landing"
            manifest = self.manifest(folder, 4)
            args = ["--manifest", str(manifest), "--landing", str(landing), "--prefix", "2048", "--workers", "2"]
            with mock.patch("builtins.print") as said:
                self.assertEqual(headers.main(args + ["--size"], fetch=bucket), 0)
            self.assertEqual(said.call_args[0][0].split()[:2], ["8192", "8192"])
            with mock.patch("builtins.print"):
                self.assertEqual(headers.main(args, fetch=bucket), 0)
            kept = sorted((landing / "raw" / "ct_colonography" / "P1" / "1.2.3").iterdir())
            self.assertEqual([p.name for p in kept], ["i1.dcmhdr", "i2.dcmhdr", "i3.dcmhdr", "i4.dcmhdr"])
            self.assertTrue(all(p.read_bytes() == head for p in kept))
            self.assertEqual(set(bucket.ranges), {(0, 2047)})
            line = json.loads((landing / "fetch" / "verified.jsonl").read_text(encoding="utf-8"))
            self.assertEqual((line["unit"], line["n_headers"], line["bytes"]), ("1.2.3", 4, 4 * end))
            with mock.patch("builtins.print") as said:
                headers.main(args + ["--size"], fetch=bucket)
            self.assertEqual(said.call_args[0][0].split()[:2], ["8192", "0"])

    def test_a_header_past_the_prefix_or_a_short_listing_leaves_the_series_unverified(self):
        head, _ = explicit_file()
        for prefix, count in (("100", 4), ("2048", 5)):
            with self.subTest(prefix=prefix, count=count), tempfile.TemporaryDirectory() as folder:
                landing = Path(folder) / "landing"
                args = ["--manifest", str(self.manifest(folder, count)), "--landing", str(landing),
                        "--prefix", prefix, "--workers", "1"]
                with mock.patch("builtins.print"):
                    self.assertEqual(headers.main(args, fetch=FakeBucket(head + pixels())), 3)
                self.assertFalse((landing / "fetch" / "verified.jsonl").exists())
                self.assertTrue((landing / "fetch" / "failed.jsonl").exists())


def row(**fields):
    base = {"collection_id": "ct_colonography", "Modality": "CT", "PatientID": "P1", "SeriesInstanceUID": "1.2.3.4.5",
            "SeriesDescription": "", "StudyDescription": "", "SeriesNumber": 1, "instanceCount": 2,
            "series_size_MB": 1.5, "series_aws_url": "s3://idc-open-data/u/*"}
    base.update(fields)
    return base


class Selections(unittest.TestCase):
    def test_localizers_are_named_by_the_scanners_own_words(self):
        names = ["Topogram  0.6  T20s", "SCOUT", "PRONE SURVIEW", "Supine AP Top  1.0  T20s", "Prone APtop  1.0  T20s",
                 "Coloprone  1.0  B30f", "Topo prone  0.6  T20s", "///FL02/ORG/"]
        chosen = select.localizers([row(SeriesDescription=n) for n in names], "ct_colonography")
        self.assertEqual([r["SeriesDescription"] for r in chosen],
                         ["Topogram  0.6  T20s", "SCOUT", "PRONE SURVIEW", "Supine AP Top  1.0  T20s",
                          "Prone APtop  1.0  T20s", "Topo prone  0.6  T20s"])

    def test_a_masked_series_is_found_by_its_nbia_folder_name(self):
        lines = ["P1/01-01-2000-1-Abdomen24ACRIN-0.4.1/4.000000-Coloprone  1.0  B30f-0.4.2",
                 "P2/01-01-2000-1-Abdomen-.1240/3.000000-Colosupine  1.0  B30f-.4371",
                 "P3/01-01-2000-1-CT ABDOMEN WO CONTRA-91117/100.000000-91118",
                 "P9/01-01-2000-1-Abdomen-.1/2.000000-x-12345"]
        keys = select.masked_keys(lines, {"P1", "P2", "P3"})
        series = [row(PatientID="P1", SeriesNumber=4, SeriesInstanceUID="1.3.6.1.4.1.9328.50.4.2"),
                  row(PatientID="P1", SeriesNumber=5, SeriesInstanceUID="1.3.6.1.4.1.9328.50.4.2"),
                  row(PatientID="P2", SeriesNumber=3, SeriesInstanceUID="1.3.6.1.4.1.9328.50.4.4371"),
                  row(PatientID="P3", SeriesNumber=100, SeriesInstanceUID="1.3.6.1.4.1.9328.50.4.91118")]
        chosen, unmatched = select.masked_series(series, keys)
        self.assertEqual([(r["PatientID"], r["SeriesNumber"]) for r in chosen], [("P1", 4), ("P2", 3), ("P3", 100)])
        self.assertEqual(unmatched, set())

    def test_sbu_takes_the_abdominal_films_and_scouts_of_a_held_abdomen_and_pelvis_ct(self):
        c = "covid_19_ny_sbu"
        series = [row(collection_id=c, PatientID="A", SeriesInstanceUID="ct-a", StudyDescription="CT ABD AND PELVIS WO IV CONT"),
                  row(collection_id=c, PatientID="A", SeriesInstanceUID="f-a", Modality="CR",
                      StudyDescription="FLAT PLATE OF ABDOMEN PORTABLE"),
                  row(collection_id=c, PatientID="A", SeriesInstanceUID="c-a", Modality="CR", StudyDescription="CHEST AP PORT"),
                  row(collection_id=c, PatientID="A", SeriesInstanceUID="s-a", SeriesDescription="SCOUT AP/LAT"),
                  row(collection_id=c, PatientID="B", SeriesInstanceUID="ct-b", StudyDescription="CT CHEST WO IV CONT"),
                  row(collection_id=c, PatientID="B", SeriesInstanceUID="f-b", Modality="DX", StudyDescription="ABDOMEN SUPINE KUB"),
                  row(collection_id=c, PatientID="C", SeriesInstanceUID="ct-c", StudyDescription="CT ABD AND PELVIS WITH IV CONT")]
        chosen = select.sbu_abdominal(series, {"ct-a", "ct-b"})
        self.assertEqual(sorted(r["SeriesInstanceUID"] for r in chosen), ["f-a", "s-a"])

    def test_sbu_localizers_are_every_held_ct_patients_less_those_fetched(self):
        c = "covid_19_ny_sbu"
        series = [row(collection_id=c, PatientID="A", SeriesInstanceUID="ct-a"),
                  row(collection_id=c, PatientID="A", SeriesInstanceUID="s1", SeriesDescription="SCOUT AP/LAT"),
                  row(collection_id=c, PatientID="A", SeriesInstanceUID="s2", SeriesDescription="Scout"),
                  row(collection_id=c, PatientID="B", SeriesInstanceUID="s3", SeriesDescription="SCOUT")]
        chosen = select.sbu_localizers(series, {"ct-a"}, {"s2"})
        self.assertEqual([r["SeriesInstanceUID"] for r in chosen], ["s1"])

    def test_cmb_takes_every_series_of_the_modality_and_the_unheld_ct_of_its_patients(self):
        series = [row(collection_id="cmb_mml", PatientID="M1", Modality="XA", SeriesInstanceUID="x1"),
                  row(collection_id="cmb_mml", PatientID="M1", SeriesInstanceUID="held"),
                  row(collection_id="cmb_mml", PatientID="M1", SeriesInstanceUID="new"),
                  row(collection_id="cmb_aml", PatientID="M1", SeriesInstanceUID="other-collection"),
                  row(collection_id="cmb_mml", PatientID="M2", SeriesInstanceUID="no-xa")]
        chosen = select.cmb_with_ct(series, ("XA",), {"held"})
        self.assertEqual([r["SeriesInstanceUID"] for r in chosen], ["x1", "new"])

    def test_the_nbia_size_holds_room_for_the_largest_zip_still_to_land(self):
        rows = [{"SeriesInstanceUID": "a", "series_bytes": "1000", "instanceCount": "2"},
                {"SeriesInstanceUID": "b", "series_bytes": "5000", "instanceCount": "1"}]
        self.assertEqual(select.nbia_need(rows, set()).split()[:2], ["12024", "12024"])
        self.assertEqual(select.nbia_need(rows, {"b"}).split()[:2], ["12024", "4048"])
        self.assertEqual(select.nbia_need(rows, {"a", "b"}).split()[:2], ["12024", "0"])

    def test_the_idc_row_is_what_fetch_size_and_acquisition_fetch_read(self):
        out = select.idc_row(row(series_size_MB=89.168188))
        self.assertEqual((out["series_bytes"], out["instanceCount"], out["collection"]), (89168188, 2, "ct_colonography"))


class Script(unittest.TestCase):
    def test_the_job_script_parses(self):
        done = subprocess.run(["bash", "-n", "open-pairs.sbatch"], cwd=GRID, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_every_route_asks_the_size_rule_before_it_fetches(self):
        text = (GRID / "open-pairs.sbatch").read_text(encoding="utf-8")
        for route in ("idc)", "nbia)", "headers)"):
            arm = text.split("  " + route, 1)[1].split(";;", 1)[0]
            self.assertLess(arm.index("size_and_admit"), arm.index("then"), route)


if __name__ == "__main__":
    unittest.main()
