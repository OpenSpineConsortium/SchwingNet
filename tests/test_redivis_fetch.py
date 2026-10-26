"""grid/redivis_fetch.py with a stand-in for the redivis client: the manifest is written and the
cap refuses before any download, files and CSV tables land under their table's folder; with --size
it downloads nothing and prints the size rule's line, the files' listed bytes and each CSV export's,
less what the files' landing paths already hold (issue #163). Standard library only, so the
required check runs it without the client."""

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
    path = Path("/")
    files = []

    def __init__(self, calls):
        self.calls = calls

    def list(self, mode, recursive):
        return FakeDirectory.files

    def download(self, path, overwrite, progress):
        self.calls.append(("files", str(path), overwrite))


class FakeTable:
    def __init__(self, reference, calls):
        self.reference = reference
        self.calls = calls
        self.uri = f"/tables/{reference}"

    def to_directory(self):
        return FakeDirectory(self.calls)

    def download(self, path, format, overwrite, progress):
        self.calls.append(("csv", path, format))


def fake_client(calls):
    client = types.ModuleType("redivis")
    client.table = lambda reference: FakeTable(reference, calls)
    return client


class FakeExport:
    """The client's export job: made from the export request's answer, finished on waiting with
    the size Redivis states for it."""

    sizes = {}

    def __init__(self, export_id, table, properties):
        self.id, self.table, self.properties = export_id, table, dict(properties)

    def wait_for_finish(self, progress):
        self.table.calls.append(("export", self.table.reference, progress))
        self.properties.update(status="completed")
        size = FakeExport.sizes.get(self.table.reference)
        if size is not None:
            self.properties["size"] = size


class RedivisCase(unittest.TestCase):
    def setUp(self):
        self.tool = load_tool()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.calls = []
        sys.modules["redivis"] = fake_client(self.calls)
        self.addCleanup(sys.modules.pop, "redivis", None)
        self.requests = []

        def make_request(method, path, payload):
            self.requests.append((method, path, payload))
            return {"id": "e1", "status": "queued"}

        self.tool.client_internals = lambda: (make_request, FakeExport)
        FakeExport.sizes = {CSV_REF: 70_000_000}
        FakeDirectory.files = [FakeFile("train/p1/a.png", 6 * 10**9), FakeFile("train/p2/b.png", 5 * 10**9)]

    def run_tool(self, *extra):
        out = io.StringIO()
        with redirect_stdout(out):
            code = self.tool.main(["--dest", str(self.tmp / "raw"), "--manifest", str(self.tmp / "meta"),
                                   "--files", REF, "--csv", CSV_REF, *extra])
        return code, out.getvalue()


class RedivisFetchTest(RedivisCase):
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


class RedivisSizeTest(RedivisCase):
    def test_the_size_is_the_files_and_the_csv_export_and_nothing_is_downloaded(self):
        code, out = self.run_tool("--size", "--max-gb", "20")
        self.assertEqual(code, 0, out)
        total = 11 * 10**9 + 70_000_000
        self.assertEqual(out.strip().splitlines()[-1], f"{total} {total} 2 files and 1 csv exports listed by redivis")
        # the export is asked for as Table.download asks, and waited on; no file is downloaded
        self.assertEqual(self.requests, [("POST", f"/tables/{CSV_REF}/exports", {"format": "csv"})])
        self.assertEqual(self.calls, [("export", CSV_REF, False)])
        self.assertTrue((self.tmp / "meta" / "redivis_files.tsv").is_file())

    def test_a_file_on_disk_counts_against_what_is_still_to_land(self):
        # sizes in the kilobytes, so the file on disk is written whole and needs no sparse-file support
        FakeDirectory.files = [FakeFile("train/p1/a.png", 6000), FakeFile("train/p2/b.png", 5000)]
        FakeExport.sizes = {CSV_REF: 70}
        landed = self.tmp / "raw" / "png_train" / "train" / "p1"
        landed.mkdir(parents=True)
        # a file is written in place of what is there, so it adds its size less what it holds
        (landed / "a.png").write_bytes(b"p" * 4000)
        code, out = self.run_tool("--size")
        self.assertEqual(code, 0, out)
        self.assertEqual(out.split()[:2], ["11070", "7070"])

    def test_the_cap_refuses_the_size_before_any_export_is_asked(self):
        code, out = self.run_tool("--size", "--max-gb", "10")
        self.assertEqual(code, self.tool.REFUSED_FOR_SIZE, out)
        self.assertEqual(out.strip(), "the files redivis lists come to 11 gb over the cap of 10 gb the source line names")
        self.assertEqual((self.requests, self.calls), ([], []))

    def test_no_stated_size_refuses_and_a_failing_client_names_only_its_kind(self):
        FakeExport.sizes = {}
        self.assertEqual(self.run_tool("--size"), (3, "no exact size; redivis stated no size for a csv export\n"))
        # a file listed with no size refuses before any export is asked for
        self.requests.clear()
        FakeDirectory.files = [FakeFile("train/p1/a.png", None)]
        self.assertEqual(self.run_tool("--size"), (3, "no exact size; redivis lists a file with no size\n"))
        self.assertEqual(self.requests, [])

        def failing(method, path, payload):
            raise PermissionError("403 for https://redivis.com/api/v1/tables/x?token=secret")

        FakeDirectory.files = []
        self.tool.client_internals = lambda: (failing, FakeExport)
        code, out = self.run_tool("--size")
        self.assertEqual((code, out), (2, "the source did not answer; the redivis client failed with PermissionError\n"))


if __name__ == "__main__":
    unittest.main()
