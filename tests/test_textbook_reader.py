"""tools/textbook_reader.py puts the textbook into the Claude project's files for the reader on
claude.ai (issue #294): the fingerprint of the book's inputs at a commit, the same for two commits
that leave them alone and covering every module the builders run; the pack of an edition, each
file whole again from its span and in the order of the paths, the text gzipped only where that is
smaller, the same bytes from the same edition; its place in the project's files, the pointer
written only after the pack reads back whole, the edition before it kept and older ones removed
once no stage may still be about to point at them; and the stage itself, against a bare repository
standing in for GitHub, main built by its own builders in UTF-8 mode in a worktree that goes again,
nothing copied where the book's inputs are already staged. The reader page is held to what the
publish needs of it: small enough for a session to read whole, ASCII, no address outside claude.ai,
and the pack's layout spelled as this module spells it."""

import ast
import datetime as dt
import gzip
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import textbook_reader as tr  # noqa: E402
from test_textbook_site import GIT_ENV, QUIET  # noqa: E402

SHA = "0123456789abcdef0123456789abcdef01234567"
BUILT = "2026-10-25T04:19:10+00:00"
NOW = dt.datetime(2026, 10, 25, 5, 0, tzinfo=dt.timezone.utc)
PAGE = ROOT / "tools" / "textbook_reader.html"


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True,
                          env={**os.environ, **GIT_ENV}).stdout.strip()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding="utf-8")


def quiet(repo):
    """A scratch repository that runs no gc or maintenance of its own, set in its config too, since
    the receive-pack and upload-pack git starts for a local remote do not take the environment's."""
    for key, value in QUIET.items():
        git(repo, "config", key, value)


# An edition by hand: the page proper, a chapter long enough to gzip, a one-byte page that gzip
# would only make longer, a picture, an exported artifact's files, and the builder's summaries,
# which are no files of the book.
EDITION = {"index.html": "<title>SchwingNet Textbook</title><h1>Front</h1>" + "<p>The front page.</p>" * 40,
           "chapter-01.html": "<h1>One</h1>" + "<p>A chapter of the book, said at length.</p>" * 80,
           "z.html": "z",
           "figures/01/plot.png": bytes(range(256)) * 4,
           "artifacts/thing/index.html": "<h1>Thing</h1>" * 30,
           "artifacts/thing/app.js": "console.log('thing');\n" * 30,
           "batches.json": "{}", "plan.json": "{}"}


def edition(folder, files=None):
    for rel, data in (files or EDITION).items():
        write(Path(folder) / rel, data)
    return Path(folder)


def tools_imported(name):
    """The modules of tools/ that tools/<name>.py imports, wherever in its code the import stands."""
    tree = ast.parse((ROOT / "tools" / f"{name}.py").read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.add(node.module.split(".")[0])
    return {n for n in names if (ROOT / "tools" / f"{n}.py").is_file()}


def builders_code():
    """Every module of tools/ the site and edition builders run, followed through their own imports."""
    seen, waiting = set(), ["textbook_site", "textbook_artifact"]
    while waiting:
        name = waiting.pop()
        if name not in seen:
            seen.add(name)
            waiting.extend(tools_imported(name) - seen)
    return seen


def fingerprinted(rel):
    """Whether a path is one the fingerprint covers."""
    return any(rel == path or rel.startswith(path + "/") for path in tr.INPUTS)


class Inputs(unittest.TestCase):
    def test_two_commits_with_the_same_inputs_share_a_fingerprint(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, GIT_ENV):
            root = Path(folder)
            git(root, "init", "-q")
            write(root / "docs" / "textbook" / "01-one.md", "# 01 One\n")
            write(root / "artifacts" / "x" / "index.html", "<p>x</p>")
            write(root / "tools" / "textbook_site.py", "# the site\n")
            write(root / "README.md", "one\n")
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "one")
            first = tr.inputs_fingerprint(root, "HEAD")
            self.assertRegex(first, r"^[0-9a-f]{64}$")
            write(root / "README.md", "two\n")
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "two")
            self.assertEqual(tr.inputs_fingerprint(root, "HEAD"), first)
            write(root / "docs" / "textbook" / "01-one.md", "# 01 One\n\nMore.\n")
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "three")
            self.assertNotEqual(tr.inputs_fingerprint(root, "HEAD"), first)
            self.assertEqual(tr.inputs_fingerprint(root, "HEAD~1"), first)

    def test_the_fingerprint_lists_the_books_folders_and_the_pack(self):
        for path in ("docs/textbook", "artifacts", "tools/textbook_reader.py"):
            self.assertIn(path, tr.INPUTS)

    def test_the_fingerprint_covers_the_code_the_builders_run(self):
        # A module the builders run that the list leaves out would change the pages without
        # changing the fingerprint, and a stage would find nothing new to copy (#269).
        code = builders_code()
        self.assertTrue({"textbook_site", "textbook_artifact", "claims_rank", "rag"} <= code)
        for name in sorted(code):
            with self.subTest(module=name):
                self.assertTrue(fingerprinted(f"tools/{name}.py"), f"tools/{name}.py is not in INPUTS")
        import rag
        import textbook_site
        self.assertTrue(fingerprinted(rag.PACKAGE.as_posix()), f"{rag.PACKAGE} is not in INPUTS")
        self.assertTrue(fingerprinted(textbook_site.LEDGER_TOOLS.as_posix()))

    def test_a_change_to_the_search_alone_changes_the_fingerprint(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, GIT_ENV):
            root = Path(folder)
            git(root, "init", "-q")
            write(root / "docs" / "textbook" / "01-one.md", "# 01 One\n\nText.\n")
            write(root / "src" / "schwingnet" / "rag.py", "K = 8\n")
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "one")
            first = tr.inputs_fingerprint(root, "HEAD")
            write(root / "src" / "schwingnet" / "rag.py", "K = 5\n")
            git(root, "commit", "-q", "-am", "two")
            self.assertNotEqual(tr.inputs_fingerprint(root, "HEAD"), first)


class Pack(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.edition = edition(self.base / "edition")

    def packed(self, out="pack"):
        index = tr.pack(self.edition, self.base / out, tr.REPO_NAME, SHA, BUILT, "i" * 64)
        return index, (self.base / out / "book.bin").read_bytes()

    def test_every_file_comes_back_whole_from_its_span(self):
        index, data = self.packed()
        book = {rel: body for rel, body in EDITION.items() if rel not in tr.NOT_BOOK}
        self.assertEqual(sorted(index["files"]), sorted(book))
        for rel, body in book.items():
            raw = body if isinstance(body, bytes) else body.encode("utf-8")
            with self.subTest(file=rel):
                self.assertEqual(tr.unpacked(index, data, rel), raw)
                self.assertEqual(index["files"][rel]["sha256"], hashlib.sha256(raw).hexdigest())
                self.assertEqual(index["files"][rel]["size"], len(raw))
        self.assertEqual(index["files"]["figures/01/plot.png"]["type"], "image/png")
        self.assertEqual(index["files"]["artifacts/thing/app.js"]["type"], "text/javascript")
        self.assertEqual((index["format"], index["repo"], index["sha"], index["built"], index["inputs"], index["start"]),
                         (tr.FORMAT, tr.REPO_NAME, SHA, BUILT, "i" * 64, "index.html"))

    def test_the_files_lie_in_the_order_of_their_paths_one_after_another(self):
        index, data = self.packed()
        spans = sorted((entry["at"], entry["n"], rel) for rel, entry in index["files"].items())
        self.assertEqual([rel for _at, _n, rel in spans], sorted(index["files"]))
        at = 0
        for start, length, _rel in spans:
            self.assertEqual(start, at)
            at += length
        self.assertEqual(index["bytes"], len(data))
        self.assertEqual(at, len(data))
        written = json.loads((self.base / "pack" / "book.json").read_text(encoding="utf-8"))
        self.assertEqual(written, index)

    def test_text_is_gzipped_only_where_that_is_smaller_and_never_a_picture(self):
        index, data = self.packed()
        files = index["files"]
        self.assertTrue(files["chapter-01.html"]["gz"])
        self.assertLess(files["chapter-01.html"]["n"], files["chapter-01.html"]["size"])
        self.assertFalse(files["z.html"]["gz"])
        self.assertEqual(files["z.html"]["n"], 1)
        self.assertFalse(files["figures/01/plot.png"]["gz"])
        entry = files["chapter-01.html"]
        self.assertEqual(gzip.decompress(data[entry["at"]:entry["at"] + entry["n"]]).decode("utf-8"),
                         EDITION["chapter-01.html"])

    def test_one_edition_packs_to_the_same_bytes_twice(self):
        self.packed("one")
        time.sleep(1.1)  # a clock in a gzip header would differ by now
        self.packed("two")
        for name in ("book.bin", "book.json"):
            self.assertEqual((self.base / "one" / name).read_bytes(), (self.base / "two" / name).read_bytes(), name)

    def test_a_folder_without_the_front_page_is_refused(self):
        (self.edition / "index.html").unlink()
        with self.assertRaises(SystemExit) as stop:
            self.packed()
        self.assertIn("no index.html", str(stop.exception))

    def test_the_command_packs_and_says_how_much(self):
        printed = io.StringIO()
        with redirect_stdout(printed):
            code = tr.main(["pack", str(self.edition), str(self.base / "cli"), "--sha", SHA, "--built", BUILT])
        self.assertEqual(code, 0)
        self.assertRegex(printed.getvalue(), r"^6 files, \d+\.\d MB packed\n$")
        self.assertTrue((self.base / "cli" / "book.bin").is_file())


class Place(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.folder = self.base / "files" / tr.FOLDER

    def pack_of(self, sha, files=None):
        out = self.base / f"pack-{sha[:4]}"
        source = edition(self.base / f"edition-{sha[:4]}", files)
        return out, tr.pack(source, out, tr.REPO_NAME, sha, BUILT, sha[:8])

    def placed(self, sha, files=None, staged="2026-10-25T05:00:00Z"):
        out, index = self.pack_of(sha, files)
        return tr.place(self.folder, out, index, staged, wait=0)

    def aged(self, name, seconds):
        for suffix in (".bin", ".json"):
            path = self.folder / f"{name}{suffix}"
            then = time.time() - seconds
            os.utime(path, (then, then))

    def test_the_pack_goes_in_under_its_editions_name_and_the_pointer_names_it(self):
        pointer, gone = self.placed(SHA)
        name = f"book-{SHA[:12]}"
        self.assertEqual(gone, [])
        self.assertEqual(pointer, tr.read_pointer(self.folder))
        self.assertEqual((pointer["index"], pointer["data"]), (f"{name}.json", f"{name}.bin"))
        self.assertEqual((pointer["format"], pointer["sha"], pointer["built"], pointer["inputs"], pointer["staged"]),
                         (tr.FORMAT, SHA, BUILT, SHA[:8], "2026-10-25T05:00:00Z"))
        self.assertEqual(pointer["files"], 6)
        self.assertTrue(tr.whole(self.folder, pointer))
        self.assertEqual((self.folder / tr.NOTE).read_text(encoding="utf-8"), tr.NOTE_TEXT)
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()),
                         sorted([tr.POINTER, tr.NOTE, f"{name}.bin", f"{name}.json"]))

    def test_the_edition_before_is_kept_and_older_ones_go_once_an_hour_old(self):
        first, second, third = "1" * 40, "2" * 40, "3" * 40
        self.placed(first)
        self.placed(second, dict(EDITION, **{"chapter-02.html": "<h1>Two</h1>"}))
        pointer, gone = self.placed(third, dict(EDITION, **{"chapter-03.html": "<h1>Three</h1>"}))
        self.assertEqual(gone, [], "an edition written within the hour may be about to be pointed at")
        self.assertEqual(pointer["sha"], third)
        self.aged(f"book-{first[:12]}", 2 * tr.FRESH_SECONDS)
        self.aged(f"book-{second[:12]}", 2 * tr.FRESH_SECONDS)
        fourth = "4" * 40
        pointer, gone = self.placed(fourth, dict(EDITION, **{"chapter-04.html": "<h1>Four</h1>"}))
        self.assertEqual(gone, [f"book-{first[:12]}.bin", f"book-{first[:12]}.json",
                                f"book-{second[:12]}.bin", f"book-{second[:12]}.json"])
        self.assertTrue((self.folder / f"book-{third[:12]}.bin").is_file(), "the edition before stays for open readers")
        self.assertEqual(pointer["sha"], fourth)

    def test_a_pack_already_there_is_left_alone(self):
        self.placed(SHA)
        data = self.folder / f"book-{SHA[:12]}.bin"
        then = time.time() - 600
        os.utime(data, (then, then))
        before = data.stat().st_mtime_ns
        pointer, _gone = self.placed(SHA, staged="2026-10-25T06:00:00Z")
        self.assertEqual(data.stat().st_mtime_ns, before)
        self.assertEqual(pointer["staged"], "2026-10-25T06:00:00Z")

    def test_a_copy_that_does_not_read_back_whole_leaves_the_pointer_as_it_was(self):
        self.placed("1" * 40)
        before = tr.read_pointer(self.folder)

        def torn(source, target):
            Path(target).write_bytes(Path(source).read_bytes()[:-1])

        with mock.patch.object(tr.shutil, "copyfile", torn), self.assertRaises(SystemExit) as stop:
            self.placed("2" * 40, dict(EDITION, **{"chapter-02.html": "<h1>Two</h1>"}))
        self.assertIn("did not read back", str(stop.exception))
        self.assertEqual(tr.read_pointer(self.folder), before)

    def test_a_pointer_of_another_format_or_none_reads_as_empty(self):
        self.folder.mkdir(parents=True)
        self.assertEqual(tr.read_pointer(self.folder), {})
        (self.folder / tr.POINTER).write_text(json.dumps({"format": "textbook-reader/0", "sha": SHA}), encoding="utf-8")
        self.assertEqual(tr.read_pointer(self.folder), {})
        (self.folder / tr.POINTER).write_text("not json", encoding="utf-8")
        self.assertEqual(tr.read_pointer(self.folder), {})
        self.assertFalse(tr.whole(self.folder, {}))


# The builders' stand-ins: the site says what it was asked, which commit it stood on and whether it
# ran in UTF-8 mode, and the edition carries that on as its page beside a chapter, a picture and
# the builder's summary.
SITE_STUB = """import json, subprocess, sys
from pathlib import Path
out = Path(sys.argv[1])
out.mkdir(parents=True)
root = sys.argv[sys.argv.index("--root") + 1]
head = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout
(out / "site.json").write_text(json.dumps({"site": sys.argv[2:], "head": head.strip(), "utf8": sys.flags.utf8_mode}))
"""
EDITION_STUB = """import json, sys
from pathlib import Path
site, out = Path(sys.argv[1]), Path(sys.argv[2])
(out / "figures" / "01").mkdir(parents=True)
said = json.loads((site / "site.json").read_text())
said["edition"] = sys.argv[3:]
(out / "index.html").write_text(json.dumps(said))
(out / "chapter-01.html").write_text(Path(said["site"][-1], "docs", "textbook", "01-one.md").read_text())
(out / "figures" / "01" / "plot.png").write_bytes(bytes(range(256)))
(out / "batches.json").write_text("{}")
"""


class Stage(unittest.TestCase):
    def setUp(self):
        patched = mock.patch.dict(os.environ, GIT_ENV)
        patched.start()
        self.addCleanup(patched.stop)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.origin = self.base / "origin.git"
        git(self.base, "init", "-q", "--bare", "-b", "main", str(self.origin))
        quiet(self.origin)
        self.clone = self.base / "SchwingNet"
        git(self.base, "init", "-q", "-b", "main", str(self.clone))
        quiet(self.clone)
        write(self.clone / "docs" / "textbook" / "01-one.md", "# 01 One\n")
        write(self.clone / "tools" / "textbook_site.py", SITE_STUB)
        write(self.clone / "tools" / "textbook_artifact.py", EDITION_STUB)
        git(self.clone, "add", "-A")
        git(self.clone, "commit", "-q", "-m", "one")
        git(self.clone, "remote", "add", "origin", str(self.origin))
        git(self.clone, "push", "-q", "origin", "main")
        self.root = self.base / "project-files"
        self.root.mkdir()
        self.folder = self.root / tr.FOLDER

    def commit(self, rel, text, message):
        write(self.clone / rel, text)
        git(self.clone, "add", "-A")
        git(self.clone, "commit", "-q", "-m", message)
        git(self.clone, "push", "-q", "origin", "main")
        return git(self.clone, "rev-parse", "HEAD")

    def staged(self, **options):
        return tr.stage(self.clone, self.root, wait=0, now=options.pop("now", NOW), **options)

    def book(self):
        pointer = tr.read_pointer(self.folder)
        index = json.loads((self.folder / pointer["index"]).read_text(encoding="utf-8"))
        return pointer, index, (self.folder / pointer["data"]).read_bytes()

    def test_main_is_built_by_its_own_builders_and_placed(self):
        sha = git(self.origin, "rev-parse", "main")
        message = self.staged()
        pointer, index, data = self.book()
        self.assertEqual(message, f"Staged the edition built from {sha[:7]} into {self.folder}: 3 files, "
                                  f"{pointer['bytes'] / 1e6:.1f} MB packed")
        self.assertEqual((pointer["sha"], pointer["staged"]), (sha, "2026-10-25T05:00:00Z"))
        self.assertEqual(pointer["built"], git(self.clone, "show", "-s", "--format=%cI", sha))
        self.assertEqual(pointer["inputs"], tr.inputs_fingerprint(self.clone, sha))
        self.assertEqual(sorted(index["files"]), ["chapter-01.html", "figures/01/plot.png", "index.html"])
        said = json.loads(tr.unpacked(index, data, "index.html"))
        self.assertEqual(said["head"], sha)
        self.assertEqual(said["utf8"], 1, "the builders run in UTF-8 mode, as on CI, whatever the computer's encoding")
        self.assertEqual(said["site"][:4], ["--repo", tr.REPO_NAME, "--sha", sha])
        self.assertEqual(said["edition"], ["--repo", tr.REPO_NAME, "--sha", sha, "--built", pointer["built"]])
        self.assertEqual(tr.unpacked(index, data, "chapter-01.html"), b"# 01 One\n")
        self.assertEqual(len(git(self.clone, "worktree", "list").splitlines()), 1, "the build's worktree goes again")

    def test_a_stage_whose_inputs_are_staged_copies_nothing_unless_asked(self):
        self.staged()
        before = self.book()[0]
        sha = self.commit("README.md", "a change outside the book\n", "readme")
        later = NOW + dt.timedelta(hours=1)
        message = self.staged(now=later)
        self.assertIn("already in", message)
        self.assertIn(f"inputs at {sha[:7]} are the same", message)
        self.assertEqual(self.book()[0], before)
        self.staged(now=later, anyway=True)
        pointer = self.book()[0]
        self.assertEqual((pointer["sha"], pointer["staged"]), (sha, "2026-10-25T06:00:00Z"))

    def test_a_copy_that_is_not_whole_is_staged_again(self):
        self.staged()
        pointer = self.book()[0]
        (self.folder / pointer["data"]).write_bytes(b"cut short")
        self.assertIn("Staged the edition", self.staged())
        self.assertTrue(tr.whole(self.folder, self.book()[0]))

    def test_a_change_to_the_book_is_a_new_edition_beside_the_one_before(self):
        self.staged()
        first = self.book()[0]
        sha = self.commit("docs/textbook/01-one.md", "# 01 One\n\nMore.\n", "more")
        self.staged()
        pointer, index, data = self.book()
        self.assertEqual(pointer["sha"], sha)
        self.assertEqual(tr.unpacked(index, data, "chapter-01.html"), b"# 01 One\n\nMore.\n")
        self.assertTrue((self.folder / first["data"]).is_file(), "a reader open on the edition before reads on")

    def test_a_given_commit_is_staged_as_it_stands(self):
        first = git(self.clone, "rev-parse", "HEAD")
        self.commit("docs/textbook/01-one.md", "# 01 One\n\nMore.\n", "more")
        self.staged(sha=first[:10])
        self.assertEqual(self.book()[0]["sha"], first)

    def test_no_project_files_or_a_failing_builder_stages_nothing(self):
        with self.assertRaises(SystemExit) as stop:
            tr.stage(self.clone, self.base / "nowhere", wait=0)
        self.assertIn("no project files", str(stop.exception))
        self.staged()
        before = self.book()[0]
        self.commit("tools/textbook_site.py", "import sys\nsys.exit(3)\n", "a site that fails")
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stop:
            self.staged()
        self.assertIn("textbook_site.py failed; nothing was staged", str(stop.exception))
        self.assertEqual(self.book()[0], before)
        self.assertEqual(len(git(self.clone, "worktree", "list").splitlines()), 1)

    def test_the_command_stages_and_says_what_it_did(self):
        printed = io.StringIO()
        with mock.patch.object(tr.time, "sleep"), redirect_stdout(printed):  # the read-back pause of the network mount
            code = tr.main(["stage", "--clone", str(self.clone), "--root", str(self.root)])
        self.assertEqual(code, 0)
        self.assertIn("Staged the edition built from", printed.getvalue())


class ThePage(unittest.TestCase):
    """What the publish needs of the reader page: a session reads it whole before it publishes it,
    so it is small, its lines short and its text ASCII; it reads the pack this module writes; and it
    asks the runtime for the project's files and the permissions panel alone and loads nothing from
    anywhere, since nothing of the book or the viewer leaves claude.ai."""

    text = PAGE.read_text(encoding="utf-8")

    def test_a_session_reads_it_whole_in_one_read(self):
        lines = self.text.splitlines()
        self.assertLess(len(self.text.encode("utf-8")), 64 * 1024)
        self.assertLess(len(lines), 2000, "the Read tool reads 2,000 lines at a time")
        self.assertLess(max(len(line) for line in lines), 2000, "the Read tool cuts longer lines")
        self.assertTrue(self.text.isascii())
        self.assertNotIn("\r", self.text)

    def test_it_reads_the_layout_this_module_writes(self):
        self.assertIn(f'var FORMAT = "{tr.FORMAT}";', self.text)
        self.assertIn(f'var FOLDER = "{tr.FOLDER}", POINTER = "{tr.POINTER}";', self.text)

    def test_it_asks_for_the_files_and_the_permissions_panel_alone(self):
        self.assertEqual(sorted(set(re.findall(r'\.use\("([a-z]+)"\)', self.text))), ["files", "permissions"])

    def test_it_loads_nothing_from_anywhere(self):
        self.assertNotRegex(self.text, r"https?://")
        self.assertNotRegex(self.text, r"<script[^>]*\bsrc=")
        self.assertNotRegex(self.text, r"<link[^>]*\bhref=")
        self.assertTrue(self.text.startswith("<title>SchwingNet Textbook</title>\n"))


if __name__ == "__main__":
    unittest.main()
