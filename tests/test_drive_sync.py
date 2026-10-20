"""tools/drive_sync.py: what each file of a connected drive does in a run,
pulled, pushed, put beside or left waiting, decided from the drive, the
default branch and the last run; a run end to end against a drive kept in
memory, nothing either side wrote lost, and one picked item the drive
will not list failing only itself; the two providers' calls, a redirect
followed without the token, a drive's name kept to one path segment and
no drive's error message in the log; and the folder gate, which keeps the
sync out of the repository's own files."""

import io
import json
import shutil
import sys
import tempfile
import unittest
import unittest.mock
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import drive_sync  # noqa: E402


def entry(version, native=False, rel="a.docx"):
    return {"id": "f1", "rel": rel, "version": version, "native": native}


def record(version, blob, pending=False, base=None, staged=(), rel="a.docx"):
    return {"rel": rel, "version": version, "blob": blob, "pending": pending, "base": base,
            "staged": list(staged)}


class DecideTest(unittest.TestCase):
    def test_each_side_alone(self):
        self.assertEqual(drive_sync.decide(entry("2"), "a", record("1", "a")), "pull")
        self.assertEqual(drive_sync.decide(entry("1"), "b", record("1", "a")), "push")
        self.assertEqual(drive_sync.decide(entry("1"), "a", record("1", "a")), "nothing")
        self.assertEqual(drive_sync.decide(entry("2"), "b", record("1", "a")), "conflict")

    def test_first_sight_and_a_file_the_drive_dropped(self):
        self.assertEqual(drive_sync.decide(entry("1"), None, None), "first")
        self.assertEqual(drive_sync.decide(None, "a", record("1", "a")), "forget")
        self.assertEqual(drive_sync.decide(None, "a", None), "nothing")

    def test_a_pulled_file_waits_for_its_merge_and_is_never_pushed_back(self):
        waiting = record("2", "new", pending=True, base="old")
        self.assertEqual(drive_sync.decide(entry("2"), "old", waiting), "wait")
        self.assertEqual(drive_sync.decide(entry("3"), "old", waiting), "pull")
        self.assertEqual(drive_sync.decide(entry("2"), "other", waiting), "conflict")

    def test_a_copy_staged_once_that_merged_late_is_pulled_over_not_pushed(self):
        self.assertEqual(drive_sync.decide(entry("3"), "b1", record("3", "m0", staged=["b1", "m0"])), "pull")

    def test_a_rename_in_the_drive_moves_the_file_and_keeps_our_revision(self):
        self.assertEqual(drive_sync.decide(entry("1", rel="b.docx"), "a", record("1", "a")), "pull")
        self.assertEqual(drive_sync.decide(entry("1", rel="b.docx"), "ours", record("1", "a")), "conflict")

    def test_a_file_removed_here_is_not_pushed(self):
        self.assertEqual(drive_sync.decide(entry("1"), None, record("1", "a")), "nothing")


class MemoryDrive:
    """A drive kept in memory, with the provider's four calls."""

    def __init__(self, files):
        self.files = dict(files)  # id -> (version, bytes, native), or (version, bytes, native, rel)
        self.beside = {}
        self.reverse = False

    def rel(self, file_id):
        found = self.files[file_id]
        return found[3] if len(found) > 3 else file_id

    def listing(self, items):
        for file_id in sorted(self.files, reverse=self.reverse):
            version, _, native = self.files[file_id][:3]
            yield {"id": file_id, "rel": self.rel(file_id), "version": version, "native": native,
                   "parent": "p", "mime": "m"}

    def download(self, found):
        return self.files[found["id"]][1]

    def upload(self, found, data):
        old = self.files[found["id"]]
        version = str(int(old[0]) + 1)
        self.files[found["id"]] = (version, data, False, *old[3:])
        return version

    def upload_beside(self, found, name, data):
        self.beside[name] = data


class RunTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        (self.root / "papers").mkdir()
        self.config = {"provider": "google", "folder": "papers", "items": [{"id": "x"}]}

    def sync(self, drive, state):
        out = self.root / "staging"
        shutil.rmtree(out, ignore_errors=True)
        summary = drive_sync.run(self.config, state, self.root, out, drive)
        return summary, out / "papers"

    def merge(self, staged):
        for path in staged.rglob("*"):
            if path.is_file():
                target = self.root / "papers" / path.relative_to(staged)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(path.read_bytes())

    def test_the_round_trip_loses_nothing(self):
        drive = MemoryDrive({"a.docx": ("1", b"draft", False)})
        state = {}
        summary, staged = self.sync(drive, state)
        self.assertEqual(summary["pulled"], ["a.docx"])
        summary, staged_again = self.sync(drive, state)
        self.assertEqual(summary["waiting"], ["a.docx"])
        self.merge(staged_again)
        summary, _ = self.sync(drive, state)
        self.assertEqual(sum(map(len, summary.values())), 0)
        (self.root / "papers" / "a.docx").write_bytes(b"revised")
        summary, _ = self.sync(drive, state)
        self.assertEqual(summary["pushed"], ["a.docx"])
        self.assertEqual(drive.files["a.docx"][1], b"revised")
        summary, _ = self.sync(drive, state)
        self.assertEqual(sum(map(len, summary.values())), 0)

    def test_both_sides_changed_puts_ours_beside_theirs(self):
        drive = MemoryDrive({"a.docx": ("1", b"draft", False)})
        state = {}
        _, staged = self.sync(drive, state)
        self.merge(staged)
        self.sync(drive, state)
        (self.root / "papers" / "a.docx").write_bytes(b"ours")
        drive.files["a.docx"] = ("5", b"theirs", False)
        summary, staged = self.sync(drive, state)
        self.assertEqual(drive.beside, {"a (Symphony revisions).docx": b"ours"})
        self.assertEqual((staged / "a.docx").read_bytes(), b"theirs")
        self.assertEqual(summary["beside"], ["a.docx"])

    def test_a_native_google_file_takes_its_revision_beside_it(self):
        drive = MemoryDrive({"g.docx": ("1", b"export", True)})
        state = {}
        _, staged = self.sync(drive, state)
        self.merge(staged)
        self.sync(drive, state)
        (self.root / "papers" / "g.docx").write_bytes(b"revised")
        summary, _ = self.sync(drive, state)
        self.assertEqual(summary["beside"], ["g.docx"])
        self.assertEqual(drive.files["g.docx"][1], b"export")
        self.assertEqual(sum(map(len, self.sync(drive, state)[0].values())), 0)

    def test_a_late_merge_of_an_old_pull_never_overwrites_the_drive(self):
        drive = MemoryDrive({"a.docx": ("1", b"m0", False)})
        state = {}
        _, staged = self.sync(drive, state)
        self.merge(staged)
        self.sync(drive, state)
        drive.files["a.docx"] = ("2", b"b1", False)
        _, old_pull = self.sync(drive, state)
        late = (old_pull / "a.docx").read_bytes()
        drive.files["a.docx"] = ("3", b"m0", False)
        summary, staged = self.sync(drive, state)
        self.assertFalse(staged.exists())
        (self.root / "papers" / "a.docx").write_bytes(late)
        summary, staged = self.sync(drive, state)
        self.assertEqual(summary["pushed"], [])
        self.assertEqual(drive.files["a.docx"][1], b"m0")
        self.assertEqual((staged / "a.docx").read_bytes(), b"m0")

    def test_two_files_of_one_name_keep_their_own_paths_whatever_the_order(self):
        drive = MemoryDrive({"id-a": ("1", b"A", False, "x.docx"), "id-b": ("1", b"B", False, "x.docx")})
        state = {}
        _, first = self.sync(drive, state)
        drive.reverse = True
        self.merge(first)
        summary, _ = self.sync(drive, state)
        self.assertEqual(sum(map(len, summary.values())), 0)
        self.assertEqual((self.root / "papers" / "x.docx").read_bytes(), b"A")

    def test_a_file_seen_first_with_another_copy_here_keeps_ours_beside(self):
        (self.root / "papers" / "a.docx").write_bytes(b"ours")
        drive = MemoryDrive({"a.docx": ("1", b"theirs", False)})
        summary, staged = self.sync(drive, {})
        self.assertEqual(drive.beside, {"a (Symphony revisions).docx": b"ours"})
        self.assertEqual((staged / "a.docx").read_bytes(), b"theirs")

    def test_a_copy_that_cannot_go_beside_still_lets_theirs_come_down(self):
        drive = MemoryDrive({"a.docx": ("1", b"draft", False)})
        state = {}
        _, staged = self.sync(drive, state)
        self.merge(staged)
        self.sync(drive, state)

        def refuse(*args):
            raise drive_sync.DriveError("too big")
        drive.upload_beside = refuse
        (self.root / "papers" / "a.docx").write_bytes(b"ours")
        drive.files["a.docx"] = ("5", b"theirs", False)
        summary, staged = self.sync(drive, state)
        self.assertEqual((staged / "a.docx").read_bytes(), b"theirs")
        self.assertEqual(len(summary["problems"]), 1)

    def test_a_file_already_equal_is_recorded_not_staged(self):
        (self.root / "papers" / "a.docx").write_bytes(b"same")
        summary, staged = self.sync(MemoryDrive({"a.docx": ("1", b"same", False)}), {})
        self.assertEqual(summary["pulled"], [])
        self.assertFalse(staged.exists())


class GoneItemDrive(MemoryDrive):
    """A drive whose item "gone" was deleted or unshared."""

    def listing(self, items):
        if items[0]["id"] == "gone":
            raise drive_sync.DriveError("GET https://graph.microsoft.com/x answered 404: itemNotFound")
        yield from super().listing(items)


class PartListingTest(unittest.TestCase):
    setUp, sync = RunTest.setUp, RunTest.sync

    def test_one_item_gone_still_syncs_the_others_and_forgets_nothing(self):
        self.config["items"] = [{"id": "gone", "name": "Old folder"}, {"id": "x"}]
        drive = GoneItemDrive({"a.docx": ("1", b"draft", False)})
        state = {"files": {"old": record("1", "o", rel="old.docx")}}
        summary, staged = self.sync(drive, state)
        self.assertEqual(summary["pulled"], ["a.docx"])
        self.assertEqual(len(summary["problems"]), 1)
        self.assertTrue(summary["problems"][0].startswith("Old folder: "))
        self.assertIn("old", state["files"])

    def test_a_new_file_never_takes_the_path_of_one_it_could_not_see(self):
        self.config["items"] = [{"id": "gone"}, {"id": "x"}]
        (self.root / "papers" / "a.docx").write_bytes(b"theirs, from the gone item")
        state = {"files": {"old": record("1", "o", rel="a.docx")}}
        drive = GoneItemDrive({"new": ("1", b"new", False, "a.docx")})
        summary, staged = self.sync(drive, state)
        self.assertFalse(staged.exists())
        self.assertEqual(drive.beside, {})
        self.assertEqual(set(state["files"]), {"old"})

    def test_every_item_gone_fails_the_run(self):
        self.config["items"] = [{"id": "gone"}]
        with self.assertRaises(drive_sync.DriveError):
            self.sync(GoneItemDrive({}), {})

    def test_another_folder_starts_afresh(self):
        state = {"folder": "notes", "files": {"a.docx": record("1", "x")}}
        summary, _ = self.sync(MemoryDrive({"a.docx": ("1", b"draft", False)}), state)
        self.assertEqual(summary["pulled"], ["a.docx"])
        self.assertEqual(state["folder"], "papers")


class ReasonTest(unittest.TestCase):
    def test_only_the_error_code_reaches_the_log(self):
        graph = {"error": {"code": "itemNotFound", "message": "greg@example.edu's Thesis.docx is gone"}}
        google = {"error": {"code": 404, "message": "File not found: 1AbC.", "status": "NOT_FOUND"}}
        self.assertEqual(drive_sync.reason_in(json.dumps(graph).encode()), "itemNotFound")
        self.assertEqual(drive_sync.reason_in(json.dumps(google).encode()), "NOT_FOUND")
        self.assertEqual(drive_sync.reason_in(b'{"error": "invalid_grant"}'), "invalid_grant")
        self.assertEqual(drive_sync.reason_in(b'{"error": "the token for greg@example.edu expired"}'),
                         "no reason given")
        self.assertEqual(drive_sync.reason_in(b"<html>secret page</html>"), "no reason given")
        self.assertEqual(drive_sync.reason_in(b"error code: 1010"), "cloudflare_1010")

    def test_a_refused_call_names_no_body(self):
        body = json.dumps({"error": "invalid_grant", "error_description": "refresh token of greg"}).encode()
        refused = urllib.error.HTTPError("https://signin.example/drive/token", 400, "Bad Request", {},
                                         io.BytesIO(body))
        with self.assertRaises(drive_sync.DriveError) as caught:
            drive_sync.access_token("https://signin.example/drive/token", "microsoft", "r",
                                    FakeOpener([("https://signin.example/", refused)]))
        self.assertEqual(str(caught.exception), "POST https://signin.example/drive/token answered 400: invalid_grant")


class FolderTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        (self.root / "scripts").mkdir()
        (self.root / "scripts" / "check.sh").write_text("true\n")
        (self.root / "README.md").write_text("x\n")

    def folder(self, name, state=None):
        return drive_sync.checked_folder({"folder": name}, state or {}, self.root)

    def test_a_new_folder_is_taken(self):
        self.assertEqual(self.folder("papers"), "papers")
        self.assertEqual(self.folder("papers/2026"), "papers/2026")

    def test_the_repositorys_own_files_are_refused(self):
        for name in ("scripts", "scripts/sub", "README.md", ".github", "../x", "a/../scripts", "/etc", ""):
            with self.assertRaises(drive_sync.DriveError, msg=name):
                self.folder(name)

    def test_a_folder_the_sync_keeps_is_taken(self):
        (self.root / "papers").mkdir()
        (self.root / "papers" / "a.docx").write_bytes(b"a")
        self.assertEqual(self.folder("papers", {"folder": "papers", "files": {}}), "papers")
        with self.assertRaises(drive_sync.DriveError):
            self.folder("scripts", {"folder": "papers", "files": {}})

    def test_a_state_from_before_counts_only_where_the_sync_brought_every_file(self):
        (self.root / "papers").mkdir()
        (self.root / "papers" / "a.docx").write_bytes(b"a")
        legacy = {"files": {"f1": record("1", "a")}}
        self.assertEqual(self.folder("papers", legacy), "papers")
        with self.assertRaises(drive_sync.DriveError):
            self.folder("scripts", legacy)
        with self.assertRaises(drive_sync.DriveError):
            self.folder("scripts/drive", legacy)

    def test_the_folder_command_prints_the_output_line_or_fails(self):
        config, state = self.root / "drive.json", self.root / "state.json"
        config.write_text(json.dumps({"folder": "papers"}))
        out = io.StringIO()
        with unittest.mock.patch("sys.stdout", out):
            code = drive_sync.main(["folder", "--config", str(config), "--state", str(state), "--root", str(self.root)])
        self.assertEqual((code, out.getvalue()), (0, "folder=papers\n"))
        config.write_text(json.dumps({"folder": "scripts"}))
        with unittest.mock.patch("sys.stderr", io.StringIO()):
            self.assertEqual(drive_sync.main(["folder", "--config", str(config), "--state", str(state),
                                              "--root", str(self.root)]), 1)


class Answer:
    def __init__(self, body, status=200):
        self.status, self.headers, self.body = status, {}, body

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeOpener:
    """Answers by URL prefix, and keeps each request for the test to read."""

    def __init__(self, routes):
        self.routes, self.requests = routes, []

    def open(self, request, timeout=None):
        self.requests.append(request)
        for prefix, answer in self.routes:
            if request.full_url.startswith(prefix):
                if isinstance(answer, urllib.error.HTTPError):
                    raise answer
                return Answer(answer if isinstance(answer, bytes) else json.dumps(answer).encode())
        raise AssertionError(f"no route for {request.full_url}")


class Throttled:
    """Refuses the first answers with the given HTTP codes, then answers."""

    def __init__(self, codes, retry_after="7"):
        self.codes, self.retry_after, self.requests = list(codes), retry_after, []

    def open(self, request, timeout=None):
        self.requests.append(request)
        if self.codes:
            headers = {"Retry-After": self.retry_after} if self.retry_after is not None else {}
            raise urllib.error.HTTPError(request.full_url, self.codes.pop(0), "Throttled", headers,
                                         io.BytesIO(b'{"error": {"code": "activityLimitReached"}}'))
        return Answer(b'{"value": []}')


class ThrottleTest(unittest.TestCase):
    def call(self, method, opener):
        waits = []
        answer = drive_sync.call(method, "https://graph.microsoft.com/v1.0/me/drive/root/children", "t",
                                 opener=opener, sleep=waits.append)
        return answer, waits

    def test_a_429_is_asked_again_after_the_wait_it_names(self):
        opener = Throttled([429, 429])
        (status, _, body), waits = self.call("GET", opener)
        self.assertEqual((status, body, waits, len(opener.requests)), (200, b'{"value": []}', [7, 7], 3))
        self.assertTrue(all(r.get_header("Authorization") == "Bearer t" for r in opener.requests))

    def test_a_503_is_asked_again_only_for_a_read(self):
        _, waits = self.call("GET", Throttled([503]))
        self.assertEqual(waits, [7])
        with self.assertRaises(drive_sync.DriveError) as caught:
            self.call("PUT", Throttled([503]))
        self.assertIn("answered 503: activityLimitReached", str(caught.exception))
        _, waits = self.call("PUT", Throttled([429]))
        self.assertEqual(waits, [7])

    def test_the_tries_end(self):
        opener = Throttled([429] * drive_sync.THROTTLE_TRIES)
        with self.assertRaises(drive_sync.DriveError):
            self.call("GET", opener)
        self.assertEqual(len(opener.requests), drive_sync.THROTTLE_TRIES)

    def test_the_wait_is_bounded_and_read_as_ascii_digits(self):
        for named, wanted in (("0", 1), ("100000", drive_sync.THROTTLE_WAIT_MOST), (None, 5),
                              ("Wed, 21 Oct 2026 07:28:00 GMT", 5), ("\u0663", 5), ("9" * 5000, 5)):
            _, waits = self.call("GET", Throttled([429], named))
            self.assertEqual(waits, [wanted], msg=named)

    def test_other_refusals_are_not_asked_again(self):
        for code in (400, 401, 403, 404, 500):
            opener = Throttled([code])
            with self.assertRaises(drive_sync.DriveError, msg=code):
                self.call("GET", opener)
            self.assertEqual(len(opener.requests), 1, msg=code)


class ProviderTest(unittest.TestCase):
    def test_google_walks_a_folder_and_names_exports(self):
        opener = FakeOpener([
            ("https://www.googleapis.com/drive/v3/files/root?", {"id": "root", "name": "Paper ../x",
                                                                "mimeType": drive_sync.GOOGLE_FOLDER}),
            ("https://www.googleapis.com/drive/v3/files?q=", {"files": [
                {"id": "d1", "name": "Draft", "mimeType": "application/vnd.google-apps.document", "version": "4",
                 "parents": ["root"]},
                {"id": "f2", "name": "Draft (Symphony revisions).docx", "mimeType": drive_sync.DOCX},
                {"id": "s1", "name": "Shortcut", "mimeType": "application/vnd.google-apps.shortcut"}]}),
            ("https://www.googleapis.com/drive/v3/files/d1/comments", {"comments": []}),
        ])
        found = list(drive_sync.Google("t", opener).listing([{"id": "root"}]))
        self.assertEqual([f["rel"] for f in found], ["Paper .._x/Draft.docx"])
        self.assertTrue(found[0]["native"])
        self.assertTrue(all(r.get_header("Authorization") == "Bearer t" for r in opener.requests))

    def test_a_name_never_leaves_its_folder(self):
        for name in ("..", "../../etc", "a/b", "C:\\x", ".hidden.", ""):
            cleaned = drive_sync.segment(name)
            self.assertNotIn("/", cleaned)
            self.assertNotIn("\\", cleaned)
            self.assertNotIn(cleaned, ("", ".", ".."))

    def test_a_redirect_is_followed_without_the_token(self):
        moved = urllib.error.HTTPError("https://graph.microsoft.com/x", 302, "Found",
                                       {"Location": "https://storage.example/file"}, io.BytesIO(b""))
        opener = FakeOpener([("https://graph.microsoft.com/", moved), ("https://storage.example/", b"bytes")])
        data = drive_sync.Microsoft("t", opener).download({"drive": "d", "id": "i"})
        self.assertEqual(data, b"bytes")
        self.assertIsNone(opener.requests[-1].get_header("Authorization"))

    def test_the_access_token_comes_from_the_sign_in_service(self):
        opener = FakeOpener([("https://signin.example/", {"access_token": "a"})])
        self.assertEqual(drive_sync.access_token("https://signin.example/drive/token", "google", "r", opener), "a")
        self.assertEqual(json.loads(opener.requests[0].data), {"provider": "google", "refresh_token": "r"})

    def test_every_call_names_this_program_not_urllib(self):
        opener = FakeOpener([("https://signin.example/", {"access_token": "a"})])
        drive_sync.access_token("https://signin.example/drive/token", "microsoft", "r", opener)
        self.assertEqual(opener.requests[0].get_header("User-agent"), drive_sync.USER_AGENT)


if __name__ == "__main__":
    unittest.main()
