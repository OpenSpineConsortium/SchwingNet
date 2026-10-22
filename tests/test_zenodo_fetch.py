"""grid/zenodo_fetch.py with a stand-in record and a stand-in curl: the manifest is written and
the cap refuses before any download, a file already on disk at the record's md5 is kept, a fetched
file is checked and a mismatch is set aside and fails the run; the token goes in the curl config
and never on the command line."""

import hashlib
import importlib.util
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_tool():
    spec = importlib.util.spec_from_file_location("zenodo_fetch", ROOT / "grid" / "zenodo_fetch.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


GOOD = b"scans"
BAD = b"other bytes"


def record(size_of_second=None):
    size_of_second = len(GOOD) if size_of_second is None else size_of_second
    return {
        "files": [
            {
                "key": "a.json",
                "size": len(GOOD),
                "checksum": "md5:" + hashlib.md5(GOOD).hexdigest(),
                "links": {"self": "https://zenodo.org/api/records/1/files/a.json/content"},
            },
            {
                "key": "b.zip",
                "size": size_of_second,
                "checksum": "md5:" + hashlib.md5(GOOD).hexdigest(),
                "links": {"self": "https://zenodo.org/api/records/1/files/b.zip/content"},
            },
        ]
    }


class ZenodoFetchTest(unittest.TestCase):
    def setUp(self):
        self.tool = load_tool()
        self.tmp = Path(tempfile.mkdtemp())
        self.calls = []
        self.reads = []
        os.environ["ZENODO_TOKEN"] = "t-secret"
        self.addCleanup(os.environ.pop, "ZENODO_TOKEN", None)

    def fake_curl(self, body):
        def curl(address, target, token):
            self.calls.append((address, token))
            Path(target).write_bytes(body)
            return 0

        return curl

    def run_tool(self, body=GOOD, rec=None, *extra):
        def read(number, token):
            self.reads.append((number, token))
            return rec or record()

        out = io.StringIO()
        with redirect_stdout(out):
            code = self.tool.main(
                [
                    "--record",
                    "1",
                    "--dest",
                    str(self.tmp / "raw"),
                    "--manifest",
                    str(self.tmp / "meta"),
                    *extra,
                ],
                read=read,
                curl=self.fake_curl(body),
            )
        return code, out.getvalue()

    def test_the_manifest_is_written_and_the_cap_refuses_first(self):
        code, out = self.run_tool(GOOD, record(size_of_second=20 * 10**9), "--max-gb", "10")
        self.assertEqual(code, self.tool.REFUSED_FOR_SIZE, out)
        self.assertIn("20.0 GB listed exceeds the cap of 10 GB", out)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.reads, [("1", "t-secret")])
        lines = (self.tmp / "meta" / "zenodo_files.tsv").read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "name\tsize\tmd5\turl")
        self.assertTrue(
            lines[2].startswith(f"b.zip\t{20 * 10**9}\t{hashlib.md5(GOOD).hexdigest()}\thttps://")
        )

    def test_files_are_fetched_and_checked_then_kept_on_the_next_run(self):
        code, out = self.run_tool(GOOD, None, "--max-gb", "1")
        self.assertEqual(code, 0, out)
        self.assertIn("a.json: fetched", out)
        self.assertEqual(self.calls[0][1], "t-secret")
        self.assertEqual((self.tmp / "raw" / "b.zip").read_bytes(), GOOD)
        self.calls.clear()
        code, out = self.run_tool(GOOD)
        self.assertEqual(code, 0, out)
        self.assertIn("b.zip: kept", out)
        self.assertEqual(self.calls, [])

    def test_a_mismatch_is_set_aside_and_fails_the_run(self):
        code, out = self.run_tool(BAD)
        self.assertEqual(code, self.tool.MISMATCH, out)
        self.assertIn("a.json: mismatch", out)
        self.assertFalse((self.tmp / "raw" / "a.json").exists())
        aside = list((self.tmp / "raw").glob("a.json.mismatch-*"))
        self.assertEqual(len(aside), 1)
        self.assertEqual(aside[0].read_bytes(), BAD)

    def test_list_only_downloads_nothing(self):
        code, out = self.run_tool(GOOD, None, "--list-only")
        self.assertEqual(code, 0, out)
        self.assertIn("record 1: 2 files", out)
        self.assertEqual(self.calls, [])

    def test_the_token_rides_in_the_config_and_the_redirect_is_followed_by_curl(self):
        text = self.tool.curl_config("https://x/y", "/d/y", "t-secret")
        self.assertIn('header = "Authorization: Bearer t-secret"', text)
        self.assertIn("continue-at = -", text)
        self.assertIn("location", text.splitlines())
        self.assertNotIn("header", self.tool.curl_config("https://x/y", "/d/y", ""))


if __name__ == "__main__":
    unittest.main()
