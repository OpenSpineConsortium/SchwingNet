"""grid/fetch_size.py, the exact size a fetch will land read from its source before a byte of it
comes (issue #160), with stand-in answers in place of the Hub, Zenodo and S3: a Hub repository is
summed over the files its glob takes, page by page, less the files already landed whole; a zip is
counted by its members, read from its central directory by range requests alone, and a plain tar by
its own size once its first block shows it is one, each with room for the largest archive while it
opens, and a compressed tar states no size, whatever its name; an S3 bucket is listed page by page,
every object under its prefix, as s5cmd syncs them; an IDC manifest is summed less the series
already verified; a record read with the owner's token is summed as it lands. Every answer that gives no
exact size ends 3 and every source that does not answer ends 2, so the size rule refuses the
fetch. The one HTTP read is checked against a local server: a range is asked and refused when the
server ignores it, and a token is never carried through a redirect. grid/idc_manifest.py's byte
column is checked too. Standard library only, so the required check runs it."""

import csv
import gzip
import http.server
import importlib.util
import io
import json
import os
import tarfile
import tempfile
import threading
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent


def load(name):
    spec = importlib.util.spec_from_file_location(f"{name}_grid", ROOT / "grid" / f"{name}.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


class Source:
    """Stand-in answers by address, read whole or by a byte range as a file server reads them, with
    every request it was asked kept."""

    def __init__(self, tool):
        self.tool, self.answers, self.asked = tool, {}, []

    def add(self, url, body, headers=None):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode("utf-8")
        self.answers[url] = (body, headers or {})

    def __call__(self, url, token="", byte_range=None):
        self.asked.append((url, token, byte_range))
        if url not in self.answers:
            raise self.tool.NoAnswer("http 404")
        body, headers = self.answers[url]
        if byte_range:
            body = body[byte_range[0] : byte_range[1] + 1]
        return body, headers


def zip_of(members):
    """A zip of (name, bytes) pairs, stored so its size is about its members' and a read of it all
    would show."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, data in members:
            archive.writestr(name, data)
    return buffer.getvalue()


def tar_of(members):
    """A plain tar of (name, bytes) pairs, in the POSIX format whose first block says ustar."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for name, data in members:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


class FetchSizeTest(unittest.TestCase):
    HUB_TREE = "https://huggingface.co/api/datasets/a/b/tree/main?recursive=true"

    def setUp(self):
        self.tool = load("fetch_size")
        self.source = Source(self.tool)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def size(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = self.tool.main(list(argv), fetch=self.source)
        return code, out.getvalue().strip()

    def hub(self):
        following = self.HUB_TREE + "&cursor=x"
        self.source.add(
            self.HUB_TREE,
            [
                {"type": "directory", "path": "0043_new_ct_tri"},
                {"type": "file", "path": "0043_new_ct_tri/a.nii.gz", "size": 134, "lfs": {"size": 1000}},
                {"type": "file", "path": "0001_visceral_gc/b.nii.gz", "size": 500},
            ],
            {"Link": f'<{following}>; rel="next"'},
        )
        self.source.add(following, [{"type": "file", "path": "0043_new_ct_tri/c.nii.gz", "size": 2000}])

    def test_a_hub_repository_is_summed_over_its_glob_less_what_landed_whole(self):
        self.hub()
        dest = self.tmp / "raw"
        hf = ("hf", "--repo", "a/b", "--repo-type", "dataset", "--dest", str(dest))
        self.assertEqual(self.size(*hf, "--include", "*0043_new_ct_tri*"), (0, "3000 3000 2 files listed by the hub"))
        # a pattern that ends in / takes everything under it, as huggingface_hub reads it
        self.assertEqual(self.size(*hf, "--include", "0043_new_ct_tri/"), (0, "3000 3000 2 files listed by the hub"))
        self.assertEqual(self.size(*hf), (0, "3500 3500 3 files listed by the hub"))
        # a file already there at its listed size is not fetched again; one of another size is
        (dest / "0043_new_ct_tri").mkdir(parents=True)
        (dest / "0043_new_ct_tri" / "a.nii.gz").write_bytes(b"x" * 1000)
        (dest / "0043_new_ct_tri" / "c.nii.gz").write_bytes(b"x" * 1999)
        self.assertEqual(self.size(*hf, "--include", "*0043_new_ct_tri*"), (0, "3000 2000 2 files listed by the hub"))

    def test_the_token_goes_to_the_hub_alone_and_is_never_printed(self):
        self.hub()
        with mock.patch.dict(os.environ, {"HF_TOKEN": "hf-not-a-token"}):
            code, out = self.size("hf", "--repo", "a/b", "--dest", str(self.tmp))
        self.assertEqual(code, 0, out)
        self.assertEqual({token for _, token, _ in self.source.asked}, {"hf-not-a-token"})
        self.assertNotIn("hf-not-a-token", out)
        # a next page on another host is not followed with the token
        self.source.add(self.HUB_TREE, [], {"Link": '<https://elsewhere.example/page2>; rel="next"'})
        with mock.patch.dict(os.environ, {"HF_TOKEN": "hf-not-a-token"}):
            code, out = self.size("hf", "--repo", "a/b", "--dest", str(self.tmp))
        self.assertEqual((code, out), (2, "the source did not answer; the hub named a next page on another host"))

    def test_a_glob_that_matches_nothing_states_no_size(self):
        self.hub()
        code, out = self.size("hf", "--repo", "a/b", "--include", "*nothing*", "--dest", str(self.tmp))
        self.assertEqual((code, out), (3, "no exact size; no file of the repository matches the include pattern"))

    def zenodo(self, files):
        record = {"files": []}
        for key, body in files:
            address = f"https://zenodo.org/api/records/123/files/{key}/content"
            record["files"].append({"key": key, "size": len(body), "links": {"self": address}})
            self.source.add(address, body)
        self.source.add("https://zenodo.org/api/records/123", record)

    def acq_zenodo(self, *extra):
        return self.size("acq", "zenodo", "--collection", "zenodo_x", "--record", "123", "--include", ".",
                         "--data-root", str(self.tmp), *extra)

    def test_a_zip_is_counted_unpacked_from_its_directory_with_room_to_open_it(self):
        members = [("set/a.bin", os.urandom(150_000)), ("set/", b""), ("set/b.bin", os.urandom(50_000))]
        archive = zip_of(members)
        self.zenodo([("set.zip", archive), ("readme.txt", b"0123456789")])
        code, out = self.acq_zenodo()
        lands = 200_000 + 10
        self.assertEqual((code, out), (0, f"{lands + len(archive)} {lands + len(archive)} 2 files listed by zenodo with 1 zips read"))
        # the members were never downloaded: only the zip's end and its central directory were read
        reads = [r for url, _, r in self.source.asked if url.endswith("set.zip/content")]
        self.assertTrue(reads and all(r is not None for r in reads))
        self.assertLess(sum(r[1] - r[0] + 1 for r in reads), 5000)
        # an archive kept beside its members counts twice and needs no room to open
        code, out = self.acq_zenodo("--keep-archives")
        self.assertEqual(out.split()[:2], [str(lands + len(archive))] * 2)
        # what an earlier try verified is not asked for again, nor room to open it
        fetch = self.tmp / "zenodo_x" / "fetch"
        fetch.mkdir(parents=True)
        (fetch / "verified.jsonl").write_text(json.dumps({"unit": "123/set.zip"}) + "\n", encoding="utf-8")
        code, out = self.acq_zenodo()
        self.assertEqual(out.split()[:2], [str(lands + len(archive)), "10"])
        # --root names the landing's parent where acquisition_fetch.py is given one
        code, out = self.acq_zenodo("--root", str(self.tmp / "elsewhere"))
        self.assertEqual(out.split()[1], str(lands + len(archive)))

    def test_a_tar_is_bounded_by_its_size_and_a_compressed_tar_states_none(self):
        plain = tar_of([("set/a.bin", os.urandom(3000)), ("set/b.bin", os.urandom(5000))])
        self.zenodo([("part.tar", plain)])
        both = 2 * len(plain)
        self.assertEqual(self.acq_zenodo(), (0, f"{both} {both} 1 files listed by zenodo with 0 zips read"))
        # only its first block is read, to see that it is a plain tar
        reads = [r for url, _, r in self.source.asked if url.endswith("part.tar/content")]
        self.assertEqual(reads, [(0, 511)])
        for name in ("part.tar.gz", "part.tgz"):
            self.zenodo([(name, b"z" * 4096)])
            self.assertEqual(self.acq_zenodo(), (3, "no exact size; a compressed tar states no unpacked size"))
        # tarfile.open decompresses what it is given, so a .tar compressed inside could unpack
        # past its own size: whatever its name, it states no size
        self.zenodo([("part.tar", gzip.compress(plain))])
        self.assertEqual(self.acq_zenodo(), (3, "no exact size; a .tar compressed with gzip states no unpacked size"))
        for body in (b"t" * 4096, plain[:200]):
            self.zenodo([("part.tar", body)])
            self.assertEqual(self.acq_zenodo(), (3, "no exact size; a .tar whose first block is no ustar header"))

    def test_a_server_that_reads_no_range_or_a_broken_zip_states_no_size(self):
        self.zenodo([("set.zip", zip_of([("a", b"a")]))])
        whole = self.source

        def no_range(url, token="", byte_range=None):
            if byte_range:
                raise self.tool.NoSize("the file server answers no range request")
            return whole(url, token)

        out = io.StringIO()
        with redirect_stdout(out):
            code = self.tool.main(["acq", "zenodo", "--collection", "zenodo_x", "--record", "123",
                                   "--data-root", str(self.tmp)], fetch=no_range)
        self.assertEqual((code, out.getvalue().strip()), (3, "no exact size; the file server answers no range request"))
        self.zenodo([("set.zip", b"this is no zip at all" * 10)])
        self.assertEqual(self.acq_zenodo(), (3, "no exact size; a zip whose central directory cannot be read"))

    def test_a_source_that_does_not_answer_or_answers_no_listing_ends_2(self):
        self.assertEqual(self.acq_zenodo(), (2, "the source did not answer; http 404"))
        self.source.add("https://zenodo.org/api/records/123", b"<html>maintenance</html>")
        self.assertEqual(self.acq_zenodo(), (2, "the source did not answer; an answer that is not a listing"))
        self.source.add("https://zenodo.org/api/records/123", {"files": []})
        self.assertEqual(self.acq_zenodo(), (3, "no exact size; no file of the source matches the include pattern"))

    def test_an_s3_bucket_is_listed_page_by_page(self):
        first = "https://stoic2021-training.s3.amazonaws.com/?list-type=2&prefix=data%2Fmha%2F"
        namespace = 'xmlns="http://s3.amazonaws.com/doc/2006-03-01/"'

        def page(objects, more):
            rows = "".join(f"<Contents><Key>data/mha/{key}</Key><Size>{size}</Size></Contents>" for key, size in objects)
            tail = "<IsTruncated>true</IsTruncated><NextContinuationToken>tok</NextContinuationToken>" if more else "<IsTruncated>false</IsTruncated>"
            return f"<ListBucketResult {namespace}>{rows}{tail}</ListBucketResult>".encode()

        self.source.add(first, page([("1.mha", 100), ("2.txt", 50)], True))
        self.source.add(first + "&continuation-token=tok", page([("3.mha", 300)], False))
        s3 = ("acq", "s3", "--collection", "aws_x", "--bucket", "s3://stoic2021-training/data/mha",
              "--include", r"\.mha$", "--data-root", str(self.tmp))
        # s5cmd syncs every object under the prefix, so the include pattern, which narrows only
        # what is verified afterwards, narrows nothing here
        self.assertEqual(self.size(*s3), (0, "450 450 3 objects listed by s3"))
        (self.tmp / "aws_x" / "raw").mkdir(parents=True)
        (self.tmp / "aws_x" / "raw" / "1.mha").write_bytes(b"m" * 100)
        self.assertEqual(self.size(*s3), (0, "450 350 3 objects listed by s3"))
        self.source.add(first, page([], False))
        self.assertEqual(self.size(*s3), (3, "no exact size; the bucket lists no object under its prefix"))

    def test_an_idc_manifest_is_summed_less_the_series_verified(self):
        manifest = self.tmp / "idc.csv"
        landing = self.tmp / "idc_x"

        def write(rows, fields=("collection", "PatientID", "SeriesInstanceUID", "instanceCount", "series_bytes")):
            with manifest.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)

        rows = [{"collection": "x", "PatientID": "p", "SeriesInstanceUID": f"S{n}", "instanceCount": 1,
                 "series_bytes": n * 100} for n in (1, 2, 3)]
        write(rows)
        idc = ("idc", "--manifest", str(manifest), "--landing", str(landing))
        self.assertEqual(self.size(*idc), (0, "600 600 3 series listed by idc"))
        (landing / "fetch").mkdir(parents=True)
        (landing / "fetch" / "verified.jsonl").write_text(json.dumps({"unit": "S2"}) + "\n", encoding="utf-8")
        self.assertEqual(self.size(*idc), (0, "600 400 3 series listed by idc"))
        write(rows, fields=("collection", "PatientID", "SeriesInstanceUID", "instanceCount"))
        self.assertEqual(self.size(*idc), (3, "no exact size; the manifest has no series bytes column"))
        write([dict(rows[0], series_bytes="")] + rows[1:])
        self.assertEqual(self.size(*idc), (3, "no exact size; a series of the manifest has no byte count"))
        write([])
        self.assertEqual(self.size(*idc), (3, "no exact size; the manifest lists no series"))

    def test_a_record_read_with_the_owners_token_is_summed_as_it_lands(self):
        self.source.add("https://zenodo.org/api/records/18389015",
                        {"files": [{"key": "a.nii.gz", "size": 700}, {"key": "b.nii.gz", "size": 300}]})
        dest = self.tmp / "raw"
        dest.mkdir()
        (dest / "a.nii.gz").write_bytes(b"a" * 700)
        with mock.patch.dict(os.environ, {"ZENODO_TOKEN": "zenodo-not-a-token"}):
            code, out = self.size("zenodo-token", "--record", "18389015", "--max-gb", "50", "--dest", str(dest))
        self.assertEqual((code, out), (0, "1000 300 2 files listed by zenodo"))
        self.assertEqual(self.source.asked[-1][1], "zenodo-not-a-token")
        self.source.add("https://zenodo.org/api/records/18389015", {"files": []})
        code, out = self.size("zenodo-token", "--record", "18389015", "--dest", str(dest))
        self.assertEqual((code, out), (3, "no exact size; the record lists no file"))

    def test_a_route_with_no_size_reader_is_refused(self):
        self.assertEqual(self.size("gdown", "1r9wX"), (3, "no exact size; no size reader for this route; one of hf acq idc zenodo-token"))
        self.assertEqual(self.size(), (3, "no exact size; no size reader for this route; one of hf acq idc zenodo-token"))
        code, out = self.size("acq", "idc", "--collection", "x", "--data-root", str(self.tmp))
        self.assertEqual((code, out), (3, "no exact size; no size reader for the idc route of the acquisition fetcher"))


class Server(http.server.BaseHTTPRequestHandler):
    """A file server on 127.0.0.1: /ranged honours a range, /whole ignores it, /moved redirects to
    /ranged; each request's Authorization header is kept."""

    BODY = bytes(range(256)) * 4
    seen = []

    def do_GET(self):
        Server.seen.append((self.path, self.headers.get("Authorization")))
        if self.path == "/moved":
            self.send_response(302)
            self.send_header("Location", "/ranged")
            self.end_headers()
            return
        if self.path not in ("/ranged", "/whole"):
            self.send_error(404)
            return
        asked = self.headers.get("Range", "")
        if self.path == "/ranged" and asked.startswith("bytes="):
            start, end = (int(part) for part in asked[6:].split("-"))
            body = self.BODY[start : end + 1]
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(self.BODY)}")
        else:
            body = self.BODY
            self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class GetTest(unittest.TestCase):
    def setUp(self):
        self.tool = load("fetch_size")
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.base = f"http://127.0.0.1:{server.server_address[1]}"
        Server.seen = []
        # a proxy in the environment would carry the requests away from the local server
        patched = mock.patch.dict(os.environ, {"no_proxy": "*", "NO_PROXY": "*"})
        patched.start()
        self.addCleanup(patched.stop)

    def test_a_range_is_read_when_the_server_honours_it_and_refused_when_it_does_not(self):
        body, _ = self.tool.get(self.base + "/ranged", byte_range=(2, 5))
        self.assertEqual(body, Server.BODY[2:6])
        with self.assertRaisesRegex(self.tool.NoSize, "answers no range request"):
            self.tool.get(self.base + "/whole", byte_range=(2, 5))
        with self.assertRaisesRegex(self.tool.NoAnswer, "http 404"):
            self.tool.get(self.base + "/missing")

    def test_a_token_is_never_carried_through_a_redirect(self):
        with self.assertRaisesRegex(self.tool.NoAnswer, "http 302"):
            self.tool.get(self.base + "/moved", token="t-secret")
        self.assertEqual(Server.seen, [("/moved", "Bearer t-secret")])
        # with no token the redirect is followed, the range with it
        body, _ = self.tool.get(self.base + "/moved", byte_range=(0, 3))
        self.assertEqual(body, Server.BODY[:4])
        self.assertEqual(Server.seen[1:], [("/moved", None), ("/ranged", None)])


class IdcManifestTest(unittest.TestCase):
    def test_series_size_mb_is_a_byte_count_and_a_missing_one_is_left_blank(self):
        tool = load("idc_manifest")
        # NLST series as the bucket listed them on 2026-10-23 beside the index's figures
        self.assertEqual([tool.series_bytes(mb) for mb in (89.168188, 0.470942, 0.58988)], [89168188, 470942, 589880])
        self.assertEqual(tool.series_bytes(None), "")
        self.assertEqual(tool.series_bytes(float("nan")), "")

    def test_the_rows_are_the_collections_ct_series_in_order_with_their_bytes(self):
        tool = load("idc_manifest")
        records = [
            {"collection_id": "nlst", "Modality": "CT", "PatientID": "p2", "SeriesInstanceUID": "1.2",
             "instanceCount": 3.0, "series_size_MB": 1.5},
            {"collection_id": "nlst", "Modality": "SEG", "PatientID": "p1", "SeriesInstanceUID": "1.0",
             "instanceCount": 1, "series_size_MB": 9.0},
            {"collection_id": "other", "Modality": "CT", "PatientID": "p9", "SeriesInstanceUID": "0.9",
             "instanceCount": 1, "series_size_MB": 9.0},
            {"collection_id": "nlst", "Modality": "CT", "PatientID": "p1", "SeriesInstanceUID": "1.1",
             "instanceCount": 2, "series_size_MB": None},
        ]
        self.assertEqual(tool.rows_of(records, "nlst"), [
            {"collection": "nlst", "PatientID": "p1", "SeriesInstanceUID": "1.1", "instanceCount": 2, "series_bytes": ""},
            {"collection": "nlst", "PatientID": "p2", "SeriesInstanceUID": "1.2", "instanceCount": 3, "series_bytes": 1500000},
        ])
        self.assertEqual(tool.FIELDS[-1], "series_bytes")


if __name__ == "__main__":
    unittest.main()
