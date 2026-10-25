"""tools/textbook_publish.py publishes the textbook edition as one claude.ai artifact from the
owner's computer (issues #236 and #277): the fingerprint of the book's inputs at a commit, the
same for two commits that leave them alone and covering every module the builders run; the plan of
what changed since the record, in batches under the Artifact tool's limits, with the page
published whenever anything is; the mechanical prompt, with the paths and nothing of the book's
text, and the answer file the session writes its marker lines to; what that answer says; and the
record a publish leaves, whole, partial or moved on. The command itself is run against a bare
repository standing in for GitHub: the record read and written by fast-forward alone from a
repository of its own, the edition built by the commit's own builders in UTF-8 mode in a worktree
that goes again, a stop where the book's inputs are already published, and the answer file the
session writes deciding what is recorded."""

import ast
import datetime as dt
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import textbook_publish as tp  # noqa: E402
from test_textbook_site import GIT_ENV, QUIET  # noqa: E402

URL = "https://claude.ai/artifact/AbC123-xyz"
RUN = "local 2026-10-25T03:00:00Z"
FOLDER, ANSWER = "/h/ed/textbook-out", "/h/ed/answer.txt"


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True,
                          env={**os.environ, **GIT_ENV}).stdout.strip()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def edition(folder, pages):
    """An edition folder by hand: the page, the files given as path: text, and the builder's
    summary, which is no file of the book."""
    write(folder / "index.html", "<title>SchwingNet Textbook</title><style></style><h1>Front</h1>")
    for rel, text in pages.items():
        write(folder / rel, text)
    write(folder / "batches.json", "{}")
    return folder


FILES = {"a.html": "A", "ask.js": "js", "figures/01/x.png": "png", "artifacts/f/index.html": "F"}


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
    return any(rel == path or rel.startswith(path + "/") for path in tp.INPUTS)


class Inputs(unittest.TestCase):
    def test_two_commits_with_the_same_inputs_share_a_fingerprint(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            git(root, "init", "-q")
            write(root / "docs" / "textbook" / "01-one.md", "# 01 One\n")
            write(root / "artifacts" / "x" / "index.html", "<p>x</p>")
            write(root / "tools" / "textbook_site.py", "# the site\n")
            write(root / "README.md", "one\n")
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "one")
            first = tp.inputs_fingerprint(root, "HEAD")
            self.assertRegex(first, r"^[0-9a-f]{64}$")
            write(root / "README.md", "two\n")
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "two")
            self.assertEqual(tp.inputs_fingerprint(root, "HEAD"), first)
            write(root / "docs" / "textbook" / "01-one.md", "# 01 One\n\nMore.\n")
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "three")
            self.assertNotEqual(tp.inputs_fingerprint(root, "HEAD"), first)
            self.assertEqual(tp.inputs_fingerprint(root, "HEAD~1"), first)

    def test_the_fingerprint_lists_the_books_folders(self):
        self.assertIn("docs/textbook", tp.INPUTS)
        self.assertIn("artifacts", tp.INPUTS)

    def test_the_fingerprint_covers_the_code_the_builders_run(self):
        # A module the builders run that the list leaves out would change the pages without
        # changing the fingerprint, and the command would find nothing new to publish.
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
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            git(root, "init", "-q")
            write(root / "docs" / "textbook" / "01-one.md", "# 01 One\n\nText.\n")
            write(root / "src" / "schwingnet" / "rag.py", "K = 8\n")
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "one")
            first = tp.inputs_fingerprint(root, "HEAD")
            write(root / "src" / "schwingnet" / "rag.py", "K = 5\n")
            git(root, "commit", "-q", "-am", "two")
            self.assertNotEqual(tp.inputs_fingerprint(root, "HEAD"), first)


class StateFile(unittest.TestCase):
    STATE = {"schema": tp.SCHEMA, "url": URL, "sha": "1234567890abcdef", "inputs": "f" * 64,
             "files": {"index.html": "h"}}

    def test_an_absent_broken_or_foreign_record_is_read_as_none(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "state.json"
            self.assertEqual(tp.load_state(""), {})
            self.assertEqual(tp.load_state(str(path)), {})
            path.write_text("not json", encoding="utf-8")
            self.assertEqual(tp.load_state(str(path)), {})
            path.write_text(json.dumps({"schema": "other/1", "url": URL}), encoding="utf-8")
            self.assertEqual(tp.load_state(str(path)), {})
            path.write_text(json.dumps(self.STATE), encoding="utf-8")
            self.assertEqual(tp.load_state(str(path)), self.STATE)


class Plan(unittest.TestCase):
    def test_a_first_publish_sends_everything_with_the_page_in_no_batch(self):
        with tempfile.TemporaryDirectory() as folder:
            out = edition(Path(folder) / "out", FILES)
            plan = tp.plan(out, {})
            self.assertTrue(plan["first"])
            self.assertFalse(plan["nothing"])
            self.assertEqual(plan["url"], "")
            self.assertEqual(plan["batches"], [{"n": 1, "files": ["a.html", "artifacts/f/index.html", "ask.js",
                                                                   "figures/01/x.png"], "remove": [], "bytes": 7}])
            self.assertEqual((plan["changed"], plan["removed"], plan["unchanged"]), (5, 0, 0))
            self.assertEqual(sorted(plan["files"]), ["a.html", "artifacts/f/index.html", "ask.js", "figures/01/x.png",
                                                     "index.html"])
            self.assertEqual((plan["total_files"], plan["page"], plan["root"]), (5, "index.html", "textbook-out"))

    def test_a_later_publish_sends_what_changed_and_removes_what_went(self):
        with tempfile.TemporaryDirectory() as folder:
            out = edition(Path(folder) / "out", FILES)
            state = {"schema": tp.SCHEMA, "url": URL, "files": tp.plan(out, {})["files"]}
            same = tp.plan(out, state)
            self.assertTrue(same["nothing"])
            self.assertEqual(same["batches"], [])
            self.assertEqual((same["changed"], same["removed"], same["unchanged"]), (0, 0, 5))
            write(out / "a.html", "A changed")
            (out / "figures" / "01" / "x.png").unlink()
            write(out / "new.html", "N")
            plan = tp.plan(out, state)
            self.assertFalse(plan["first"])
            self.assertEqual(plan["url"], URL)
            self.assertEqual(plan["batches"], [{"n": 1, "files": ["a.html", "new.html"], "remove": ["figures/01/x.png"],
                                                "bytes": 10}])
            self.assertEqual((plan["changed"], plan["removed"], plan["unchanged"]), (2, 1, 3))
            self.assertNotIn("figures/01/x.png", plan["files"])

    def test_the_page_alone_changing_is_a_publish_with_an_empty_batch(self):
        with tempfile.TemporaryDirectory() as folder:
            out = edition(Path(folder) / "out", FILES)
            state = {"schema": tp.SCHEMA, "url": URL, "files": tp.plan(out, {})["files"]}
            write(out / "index.html", "<title>SchwingNet Textbook</title><style></style><h1>Front, again</h1>")
            plan = tp.plan(out, state)
            self.assertFalse(plan["nothing"])
            self.assertEqual(plan["batches"], [{"n": 1, "files": [], "remove": [], "bytes": 0}])
            self.assertEqual((plan["changed"], plan["removed"], plan["unchanged"]), (1, 0, 4))

    def test_the_batches_keep_under_the_limits_with_the_removals_in_the_first(self):
        with tempfile.TemporaryDirectory() as folder:
            out = edition(Path(folder) / "out", dict(FILES, **{"new.html": "N"}))
            state = {"schema": tp.SCHEMA, "url": URL, "files": {"gone.html": "h"}}
            with mock.patch.object(tp, "PER_PUBLISH_FILES", 2):
                batches = tp.plan(out, state)["batches"]
            self.assertEqual([len(b["files"]) + len(b["remove"]) for b in batches], [2, 2, 2])
            self.assertEqual([b["remove"] for b in batches], [["gone.html"], [], []])
            self.assertEqual([b["n"] for b in batches], [1, 2, 3])
            with mock.patch.object(tp, "PER_PUBLISH_BYTES", 3):
                batches = tp.plan(out, {})["batches"]
            self.assertTrue(all(b["bytes"] <= 3 or len(b["files"]) == 1 for b in batches), batches)
            self.assertEqual([f for b in batches for f in b["files"]], ["a.html", "artifacts/f/index.html", "ask.js",
                                                                        "figures/01/x.png", "new.html"])

    def test_a_folder_without_the_page_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            write(Path(folder) / "a.html", "A")
            with self.assertRaises(SystemExit):
                tp.plan(folder, {})


class Prompt(unittest.TestCase):
    def plans(self, folder):
        out = edition(Path(folder) / "out", dict(FILES, **{"a.html": "SECRETWORD-ZXQ in a page"}))
        first = tp.plan(out, {})
        state = {"schema": tp.SCHEMA, "url": URL, "files": first["files"], "capabilities": tp.CAPABILITIES}
        write(out / "a.html", "A changed")
        (out / "figures" / "01" / "x.png").unlink()
        return first, tp.plan(out, state)

    def test_the_first_publish_makes_the_artifact_with_its_capabilities_and_label(self):
        with tempfile.TemporaryDirectory() as folder:
            first, _later = self.plans(folder)
            text = tp.prompt(first, "abc1234def", FOLDER, ANSWER)
        self.assertIn(f"capabilities {json.dumps(tp.CAPABILITIES)}", text)
        self.assertIn('"mcp": {"servers": [{"server": "GitHub", "tools": ["actions_run_trigger", "get_file_contents"]}]}', text)
        self.assertIn("icon book", text)
        self.assertIn('label "Edition abc1234"', text)
        self.assertIn('title "SchwingNet Textbook"', text)
        self.assertIn(f"file_path {FOLDER}/index.html, root {FOLDER}", text)
        for rel in first["files"]:
            if rel != "index.html":
                self.assertIn(f"\n  {rel}\n", text)
        self.assertIn("Batch 1 of 1: 4 files, 30 bytes\n", text)
        for marker in ("ARTIFACT_URL=<url>", "ARTIFACT_TOOL_MISSING", "PUBLISH_INCOMPLETE=<n> of <m>"):
            self.assertIn(marker, text)
        self.assertNotIn("Action read", text)
        self.assertNotIn("overwrite_unread", text)

    def test_a_later_publish_reads_and_lists_first_and_removes_with_null(self):
        with tempfile.TemporaryDirectory() as folder:
            _first, later = self.plans(folder)
            text = tp.prompt(later, "abc1234def", FOLDER, ANSWER)
        self.assertIn(f"The artifact exists: {URL}", text)
        self.assertIn("1. Action read with that url", text)
        self.assertIn("2. Action list with scope files", text)
        self.assertIn("mapped to\n   null", text)
        self.assertIn("overwrite_unread", text)
        self.assertIn(f"file_path {FOLDER}/index.html, root {FOLDER}", text)
        self.assertIn("Batch 1 of 1: 1 files, 9 bytes, 1 to remove\n  a.html\n  remove: figures/01/x.png\n", text)
        self.assertIn("Pass no capabilities, icon, title or description", text)
        self.assertNotIn('capabilities {"sample"', text)

    def test_a_record_with_other_capabilities_or_none_passes_them_once_on_the_first_batch(self):
        # An artifact published before the connector was declared, or under another list, takes the
        # current list on its next publish and keeps it after that.
        with tempfile.TemporaryDirectory() as folder:
            out = edition(Path(folder) / "out", FILES)
            first = tp.plan(out, {})
            write(out / "a.html", "A changed")
            for recorded in ({}, {"capabilities": {"sample": {}}}):
                state = dict({"schema": tp.SCHEMA, "url": URL, "files": first["files"]}, **recorded)
                later = tp.plan(out, state)
                self.assertEqual(later["capabilities"], tp.CAPABILITIES)
                text = tp.prompt(later, "abc1234def", FOLDER, ANSWER)
                self.assertIn(f"on the first of them alone capabilities {json.dumps(tp.CAPABILITIES)}", text)
                self.assertNotIn("Pass no capabilities", text)
            same = tp.plan(out, {"schema": tp.SCHEMA, "url": URL, "files": first["files"], "capabilities": tp.CAPABILITIES})
            self.assertIsNone(same["capabilities"])
        self.assertEqual(first["capabilities"], tp.CAPABILITIES)

    def test_nothing_of_the_books_text_is_in_the_prompt_or_the_plan(self):
        with tempfile.TemporaryDirectory() as folder:
            first, later = self.plans(folder)
            for plan in (first, later):
                self.assertNotIn("SECRETWORD", json.dumps(plan))
                self.assertNotIn("SECRETWORD", tp.prompt(plan, "abc1234def", FOLDER, ANSWER))

    def test_the_session_writes_its_markers_to_the_answer_file_alone(self):
        # Nothing else carries the session's answer back to the command, so it writes the marker
        # lines to a file of the work folder, and may write that file alone.
        with tempfile.TemporaryDirectory() as folder:
            first, later = self.plans(folder)
            for plan in (first, later):
                text = tp.prompt(plan, "abc1234def", FOLDER, ANSWER)
                self.assertIn("one private claude.ai artifact from the\nowner's computer", text)
                self.assertIn(f"Write (only for the\nanswer file, {ANSWER}), write no other file", text)
                self.assertIn(f"write the line ARTIFACT_TOOL_MISSING to {ANSWER}", text)
                self.assertIn(f"write the marker lines to {ANSWER} with the\nWrite tool", text)
                self.assertIn("and last ARTIFACT_URL=<url>", text)
                self.assertIn("typing\n/exit lets the command", text)
                self.assertNotIn("GitHub Actions", text)


class Answer(unittest.TestCase):
    def test_the_link_is_read_from_the_last_line_alone(self):
        found = tp.answer_of(f"Published two batches.\nARTIFACT_URL={URL}\n")
        self.assertEqual(found, {"url": URL, "missing_tool": False, "incomplete": "", "capabilities_refused": False})
        self.assertEqual(tp.answer_of(f"ARTIFACT_URL={URL}\nand more")["url"], "")
        self.assertEqual(tp.answer_of("ARTIFACT_URL=https://example.com/artifact/x")["url"], "")
        self.assertEqual(tp.answer_of("ARTIFACT_URL=https://claude.ai/artifact/x; rm")["url"], "")
        self.assertEqual(tp.answer_of("ARTIFACT_URL=https://claude.ai/code/artifact/0f0e-1a")["url"],
                         "https://claude.ai/code/artifact/0f0e-1a")
        found = tp.answer_of(f"PUBLISH_INCOMPLETE=2 of 3\nARTIFACT_URL={URL}")
        self.assertEqual((found["incomplete"], found["url"]), ("2 of 3", URL))
        self.assertEqual(tp.answer_of("ARTIFACT_TOOL_MISSING"), {"url": "", "missing_tool": True, "incomplete": "", "capabilities_refused": False})
        self.assertEqual(tp.answer_of("")["url"], "")

class Record(unittest.TestCase):
    PLAN = {"files": {"index.html": "h1", "a.html": "h2"}, "changed": 3, "removed": 1, "unchanged": 2}
    WHOLE = {"url": URL, "missing_tool": False, "incomplete": "", "capabilities_refused": False}

    def test_a_whole_publish_records_the_edition_and_every_hash(self):
        new, message = tp.record({}, self.PLAN, self.WHOLE, "abc1234def", "2026-10-24T18:42:00Z", "i" * 64, RUN)
        self.assertEqual(new, {"schema": tp.SCHEMA, "url": URL, "sha": "abc1234def", "built": "2026-10-24T18:42:00Z",
                               "inputs": "i" * 64, "run": RUN, "files": self.PLAN["files"], "capabilities": tp.CAPABILITIES})
        self.assertEqual(message, "Edition abc1234: 3 files published, 1 removed, 2 unchanged")

    def test_a_refused_connector_publishes_with_ask_claude_alone_and_is_offered_again(self):
        # The connector's entry may be refused where the account has no GitHub connector; the session then
        # publishes with sample alone and says so, the record keeps what was applied, and the next plan
        # offers the connector again on its first batch.
        found = tp.answer_of(f"Published.\n{tp.REFUSED}\nARTIFACT_URL={URL}\n")
        self.assertTrue(found["capabilities_refused"])
        self.assertEqual(found["url"], URL)
        new, _message = tp.record({}, self.PLAN, found, "abc1234def", "d", "i" * 64, RUN)
        self.assertEqual(new["capabilities"], tp.BASIC_CAPABILITIES)
        new, _message = tp.record({}, self.PLAN, self.WHOLE, "abc1234def", "d", "i" * 64, RUN)
        self.assertEqual(new["capabilities"], tp.CAPABILITIES)

    def test_the_prompt_says_what_to_do_when_the_connector_is_refused_only_where_capabilities_go(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "out"
            write(out / "index.html", "page")
            first = tp.plan(out, {})
            again = tp.plan(out, {"schema": tp.SCHEMA, "url": URL, "files": {}, "capabilities": tp.BASIC_CAPABILITIES})
            kept = tp.plan(out, {"schema": tp.SCHEMA, "url": URL, "files": {}, "capabilities": tp.CAPABILITIES})
        for plan_, says in ((first, True), (again, True), (kept, False)):
            text = tp.prompt(plan_, "abc1234def", FOLDER, ANSWER)
            self.assertEqual(tp.REFUSED in text, says, text)
            self.assertEqual(f"capabilities {json.dumps(tp.BASIC_CAPABILITIES)} instead" in text, says)

    def test_a_publish_that_stopped_partway_records_the_link_with_nothing_published(self):
        state = {"schema": tp.SCHEMA, "url": URL, "sha": "old", "inputs": "o", "files": {"index.html": "x"}}
        new, message = tp.record(state, self.PLAN, dict(self.WHOLE, incomplete="2 of 3"), "abc1234def", "d", "i", RUN)
        self.assertEqual(new, {"schema": tp.SCHEMA, "url": URL, "sha": "", "built": "", "inputs": "", "run": RUN,
                               "files": {}, "incomplete": "2 of 3"})
        self.assertEqual(message, "Edition abc1234: incomplete (2 of 3); the next publish sends it whole")

    def test_nothing_to_publish_moves_the_fingerprint_alone(self):
        state = {"schema": tp.SCHEMA, "url": URL, "sha": "old1234567", "built": "b", "inputs": "o" * 64,
                 "run": "r", "files": {"index.html": "x"}}
        new, message = tp.record(state, self.PLAN, {"nothing": True}, "new1234567", "d", "n" * 64, RUN)
        self.assertEqual(new, dict(state, inputs="n" * 64, run=RUN))
        self.assertEqual(message, "Inputs at new1234: nothing to publish")
        with self.assertRaises(SystemExit):
            tp.record({}, self.PLAN, {"nothing": True}, "new1234567", "d", "n" * 64, RUN)

    def test_a_missing_tool_another_artifact_or_no_link_is_refused(self):
        state = {"schema": tp.SCHEMA, "url": "https://claude.ai/artifact/other", "files": {}}
        for current, answer in ((state, self.WHOLE), ({}, dict(self.WHOLE, url="")),
                                ({}, dict(self.WHOLE, missing_tool=True))):
            with self.assertRaises(SystemExit):
                tp.record(current, self.PLAN, answer, "abc1234def", "d", "i", RUN)


def quiet(repo):
    """A scratch repository that runs no gc or maintenance of its own, set in its config too, since
    the receive-pack and upload-pack git starts for a local remote do not take the environment's."""
    for key, value in QUIET.items():
        git(repo, "config", key, value)


# The builders' stand-ins: the site says what it was asked and which commit it stood on, and the
# edition carries that on as its page.
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
out.mkdir(parents=True)
said = json.loads((site / "site.json").read_text())
said["edition"] = sys.argv[3:]
(out / "index.html").write_text(json.dumps(said))
"""


class Local(unittest.TestCase):
    STATE = {"schema": tp.SCHEMA, "url": URL, "sha": "a" * 40, "built": "d", "inputs": "i" * 64, "run": "local",
             "files": {"index.html": "h"}}

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
        git(self.clone, "add", "-A")
        git(self.clone, "commit", "-q", "-m", "one")
        git(self.clone, "remote", "add", "origin", str(self.origin))
        git(self.clone, "push", "-q", "origin", "main")
        self.work = self.base / "SchwingNet-textbook-edition"
        self.remote = str(self.origin)

    def recorded(self):
        return json.loads(git(self.origin, "show", f"{tp.BRANCH}:{tp.STATE_FILE}"))

    def no_record(self):
        return git(self.origin, "branch", "--list", tp.BRANCH) == ""

    def fake_build(self, clone, sha, built, work):
        self.built = (Path(clone), sha, built)
        return edition(Path(work) / tp.OUT_REL, FILES)

    def test_the_record_is_read_and_written_by_fast_forward_alone(self):
        self.work.mkdir()
        self.assertEqual(tp.recorded_state(self.work, self.remote), {})
        self.assertFalse((self.work / tp.STATE_FILE).exists())
        first = tp.write_record(self.work, self.remote, self.STATE, "Edition aaaaaaa: 1 files published")
        self.assertEqual(git(self.origin, "ls-tree", "--name-only", tp.BRANCH), tp.STATE_FILE)
        self.assertEqual(self.recorded(), self.STATE)
        self.assertEqual(tp.recorded_state(self.work, self.remote), self.STATE)
        second = tp.write_record(self.work, self.remote, dict(self.STATE, sha="b" * 40), "Edition bbbbbbb")
        self.assertEqual(git(self.origin, "rev-parse", tp.BRANCH), second)
        self.assertEqual(git(self.origin, "rev-parse", f"{tp.BRANCH}^"), first)
        self.assertEqual(git(self.origin, "log", "-1", "--format=%s", tp.BRANCH), "Edition bbbbbbb")
        self.assertEqual(self.recorded()["sha"], "b" * 40)

    def test_a_remote_that_cannot_be_read_stops_the_command(self):
        self.work.mkdir()
        with self.assertRaises(SystemExit):
            tp.recorded_state(self.work, str(self.base / "missing.git"))

    def test_a_branch_that_holds_other_files_is_never_replaced(self):
        other = self.base / "other"
        git(self.base, "init", "-q", str(other))
        quiet(other)
        write(other / tp.STATE_FILE, json.dumps(self.STATE))
        write(other / "notes.md", "the project's own\n")
        git(other, "add", "-A")
        git(other, "commit", "-q", "-m", "a branch of its own")
        git(other, "push", "-q", self.remote, f"HEAD:refs/heads/{tp.BRANCH}")
        head = git(self.origin, "rev-parse", tp.BRANCH)
        self.work.mkdir()
        with self.assertRaises(SystemExit) as stop:
            tp.write_record(self.work, self.remote, self.STATE, "Edition aaaaaaa")
        self.assertIn("notes.md", str(stop.exception))
        self.assertEqual(git(self.origin, "rev-parse", tp.BRANCH), head)

    def test_a_branch_that_moved_meanwhile_is_read_again(self):
        self.work.mkdir()
        elsewhere = self.base / "elsewhere"
        elsewhere.mkdir()
        tp.write_record(self.work, self.remote, self.STATE, "Edition aaaaaaa")
        real, moved = tp.record_head, []

        def moving(repo, remote):
            head = real(repo, remote)
            if not moved:
                moved.append(head)
                tp.write_record(elsewhere, remote, dict(self.STATE, sha="c" * 40), "Edition ccccccc")
            return head

        with mock.patch.object(tp, "record_head", moving):
            commit = tp.write_record(self.work, self.remote, dict(self.STATE, sha="b" * 40), "Edition bbbbbbb")
        self.assertEqual(git(self.origin, "rev-parse", tp.BRANCH), commit)
        self.assertEqual(git(self.origin, "log", "--format=%s", tp.BRANCH).splitlines(),
                         ["Edition bbbbbbb", "Edition ccccccc", "Edition aaaaaaa"])

    def test_the_edition_is_built_by_the_commits_own_builders_in_a_worktree_that_goes_again(self):
        write(self.clone / "tools" / "textbook_site.py", SITE_STUB)
        write(self.clone / "tools" / "textbook_artifact.py", EDITION_STUB)
        git(self.clone, "add", "-A")
        git(self.clone, "commit", "-q", "-m", "builders")
        sha = git(self.clone, "rev-parse", "HEAD")
        self.work.mkdir()
        out = tp.build(self.clone, sha, "2026-10-25T02:00:00Z", self.work)
        self.assertEqual(out, self.work / tp.OUT_REL)
        said = json.loads((out / "index.html").read_text(encoding="utf-8"))
        self.assertEqual(said["head"], sha)
        self.assertEqual(said["utf8"], 1, "the builders run in UTF-8 mode, as on CI, whatever the computer's encoding")
        self.assertEqual(said["site"][:4], ["--repo", tp.REPO_NAME, "--sha", sha])
        self.assertEqual(said["edition"], ["--repo", tp.REPO_NAME, "--sha", sha, "--built", "2026-10-25T02:00:00Z"])
        self.assertFalse((self.work / "tree").exists())
        self.assertFalse((self.work / "site").exists())
        self.assertEqual(len(git(self.clone, "worktree", "list").splitlines()), 1)
        write(self.clone / "tools" / "textbook_site.py", "import sys\nsys.exit(3)\n")
        git(self.clone, "commit", "-q", "-am", "a site that fails")
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            tp.build(self.clone, git(self.clone, "rev-parse", "HEAD"), "d", self.work)
        self.assertFalse((self.work / "tree").exists())
        self.assertEqual(len(git(self.clone, "worktree", "list").splitlines()), 1)

    def test_a_work_folder_inside_the_clone_is_refused(self):
        with self.assertRaises(SystemExit):
            tp.local_publish(self.clone, self.clone / "edition", launch=False)

    def test_the_command_builds_opens_claude_code_and_records_its_answer(self):
        sha = git(self.clone, "rev-parse", "HEAD")

        def session(command, work):
            self.assertEqual(Path(work), self.work)
            text = (Path(work) / tp.PROMPT_FILE).read_text(encoding="utf-8")
            self.assertIn(f"answer file, {(self.work / tp.ANSWER_FILE).as_posix()})", text)
            self.assertIn(f"file_path {(self.work / tp.OUT_REL).as_posix()}/index.html", text)
            (Path(work) / tp.ANSWER_FILE).write_text(f"Published.\nARTIFACT_URL={URL}\n", encoding="utf-8")

        printed = io.StringIO()
        with mock.patch.object(tp, "build", self.fake_build), \
                mock.patch.object(tp, "open_session", side_effect=session) as opened, redirect_stdout(printed):
            self.assertEqual(tp.local_publish(self.clone, self.work, claude=sys.executable), 0)
        opened.assert_called_once()
        self.assertEqual(self.built[1], sha)
        state = self.recorded()
        self.assertEqual((state["url"], state["sha"]), (URL, sha))
        self.assertEqual(state["inputs"], tp.inputs_fingerprint(self.clone, sha))
        self.assertEqual(state["capabilities"], tp.CAPABILITIES)
        self.assertTrue(state["run"].startswith("local "))
        self.assertEqual(printed.getvalue(), f"Edition {sha[:7]}: 5 files published, 0 removed, 0 unchanged\n{URL}\n")
        self.assertFalse((self.work / tp.OUT_REL).exists())
        printed = io.StringIO()
        with mock.patch.object(tp, "build", side_effect=AssertionError("built again")), redirect_stdout(printed):
            self.assertEqual(tp.local_publish(self.clone, self.work, claude=sys.executable), 0)
        self.assertIn(f"already published at {URL}", printed.getvalue())

    def test_without_claude_code_the_folder_waits_with_the_two_steps(self):
        printed = io.StringIO()
        with mock.patch.object(tp, "build", self.fake_build), redirect_stdout(printed):
            code = tp.main(["local", "--clone", str(self.clone), "--work", str(self.work),
                            "--claude", "no-such-claude-command"])
        self.assertEqual(code, 0)
        self.assertIn(tp.LOCAL_ASK, printed.getvalue())
        self.assertIn(f"local --record --work {self.work}", printed.getvalue())
        self.assertTrue((self.work / tp.PROMPT_FILE).is_file())
        self.assertTrue(self.no_record())
        with self.assertRaises(SystemExit) as stop:
            tp.main(["local", "--work", str(self.work), "--record"])
        self.assertIn("wrote no answer.txt", str(stop.exception))
        (self.work / tp.ANSWER_FILE).write_text("ARTIFACT_TOOL_MISSING\n", encoding="utf-8")
        with self.assertRaises(SystemExit) as stop:
            tp.main(["local", "--work", str(self.work), "--record"])
        self.assertIn("/login", str(stop.exception))
        self.assertTrue(self.no_record())
        (self.work / tp.ANSWER_FILE).write_text(f"{tp.REFUSED}\nARTIFACT_URL={URL}\n", encoding="utf-8")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(tp.finish(self.work, now=dt.datetime(2026, 10, 25, 2, 30, tzinfo=dt.timezone.utc)), 0)
        state = self.recorded()
        self.assertEqual((state["url"], state["run"]), (URL, "local 2026-10-25T02:30:00Z"))
        self.assertEqual(state["capabilities"], tp.BASIC_CAPABILITIES)
        self.assertFalse((self.work / tp.ANSWER_FILE).exists())
        with self.assertRaises(SystemExit):
            tp.main(["local", "--work", str(self.work), "--record"])

    def test_the_default_work_folder_is_beside_the_clone(self):
        self.assertEqual(tp.default_work(self.clone), self.work)


if __name__ == "__main__":
    unittest.main()
