"""grid/redivis_fetch.py with a stand-in for the redivis client: the manifest is written and the
cap refuses before any download, files and CSV tables land under their table's folder. Standard
library only, so the required check runs it without the client."""

import importlib.util
import io
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF = "aimi.chexpert_plus:5yyj:v1_0.png_train:s6cj"
CSV_REF = "aimi.chexpert_plus:5yyj:v1_0.df_chexpert_plus_240401:bavj"


def load_tool():
    spec = importlib.util.spec_from_file_location("redivis_fetch", ROOT / "grid" / "redivis_fetch.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


class FakeFile:
    def __init__(self, path, size):
        self.path = Path(path)
        self.size = size
        self.properties = {"md5_hash": "bWQ1"}


class FakeDirectory:
    def __init__(self, calls):
        self.calls = calls

    def list(self, mode, recursive):
        return [FakeFile("train/p1/a.png", 6 * 10**9), FakeFile("train/p2/b.png", 5 * 10**9)]

    def download(self, path, overwrite, progress):
        self.calls.append(("files", str(path), overwrite))


class FakeTable:
    def __init__(self, reference, calls):
        self.reference = reference
        self.calls = calls

    def to_directory(self):
        return FakeDirectory(self.calls)

    def download(self, path, format, overwrite, progress):
        self.calls.append(("csv", path, format))


def fake_client(calls):
    client = types.ModuleType("redivis")
    client.table = lambda reference: FakeTable(reference, calls)
    return client


class RedivisFetchTest(unittest.TestCase):
    def setUp(self):
        self.tool = load_tool()
        self.tmp = Path(tempfile.mkdtemp())
        self.calls = []
        sys.modules["redivis"] = fake_client(self.calls)
        self.addCleanup(sys.modules.pop, "redivis", None)

    def run_tool(self, *extra):
        out = io.StringIO()
        with redirect_stdout(out):
            code = self.tool.main(["--dest", str(self.tmp / "raw"), "--manifest", str(self.tmp / "meta"),
                                   "--files", REF, "--csv", CSV_REF, *extra])
        return code, out.getvalue()

    def test_a_table_lands_in_its_own_folder(self):
        self.assertEqual(self.tool.folder_of(REF), "png_train")
        self.assertEqual(self.tool.folder_of(CSV_REF), "df_chexpert_plus_240401")

    def test_the_cap_refuses_before_any_download(self):
        code, out = self.run_tool("--max-gb", "10")
        self.assertEqual(code, self.tool.REFUSED_FOR_SIZE, out)
        self.assertIn("11.0 GB listed exceeds the cap of 10 GB", out)
        self.assertEqual(self.calls, [])
        manifest = (self.tmp / "meta" / "redivis_files.tsv").read_text(encoding="utf-8").splitlines()
        self.assertEqual(manifest[1], "png_train\ttrain/p1/a.png\t6000000000\tbWQ1")

    def test_files_and_csv_tables_are_downloaded_under_the_cap(self):
        code, out = self.run_tool("--max-gb", "20")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.calls[0], ("files", str(self.tmp / "raw" / "png_train"), True))
        self.assertEqual(self.calls[1], ("csv", str(self.tmp / "raw" / "df_chexpert_plus_240401"), "csv"))

    def test_list_only_downloads_nothing(self):
        code, out = self.run_tool("--list-only")
        self.assertEqual(code, 0, out)
        self.assertIn("listed: 2 files", out)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
