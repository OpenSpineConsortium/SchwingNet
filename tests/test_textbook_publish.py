"""tools/textbook_publish.py is what .github/workflows/textbook-artifact.yml runs around the
publish of the textbook edition as one claude.ai artifact (issue #236): the fingerprint of the
book's inputs at a commit, the same for two commits that leave them alone; whether a run may
publish, and the first reason it may not; the plan of what changed since the record, in batches
under the Artifact tool's limits, with the page published whenever anything is; the mechanical
prompt, with the paths and nothing of the book's text; the session's arguments; what its answer
says; and the record a run leaves, whole, partial or moved on. The workflow's text is held to the
helper: its push filter is the fingerprint's list, every action is pinned, the session runs in
the job that cannot write and may fail without failing the record, and the day's count, the
switch and the cap are read where the helper expects them. The command local, the same publish
from the owner's computer (issue #277), is run against a bare repository standing in for GitHub:
the record read and written by fast-forward alone from a repository of its own, the edition built
by the commit's own builders in a worktree that goes again, a stop where the book's inputs are
already published, and the answer file the session writes deciding what is recorded."""

import ast
import datetime as dt
import io
import json
import os
import re
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

WORKFLOW = ROOT / ".github" / "workflows" / "textbook-artifact.yml"
TODAY = "2026-10-24"
URL = "https://claude.ai/artifact/AbC123-xyz"
RUN = "https://github.com/OWNER/NAME/actions/runs/1"


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True,
                          env={**os.environ, **GIT_ENV}).stdout.strip()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def commit_of(message, date):
    return {"sha": "0" * 40, "commit": {"message": message, "committer": {"date": date}}}


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
    """Whether a path is one the fingerprint and the push filter cover."""
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

    def test_the_fingerprint_lists_the_filters_paths(self):
        self.assertEqual(tp.INPUTS, [p.removesuffix("/**") for p in tp.FILTER])
        self.assertIn("docs/textbook", tp.INPUTS)
        self.assertIn("artifacts", tp.INPUTS)

    def test_the_fingerprint_covers_the_code_the_builders_run(self):
        # A module the builders run that the list leaves out would change the pages without
        # changing the fingerprint, and the half-hourly run would find nothing new to publish.
        code = builders_code()
        self.assertTrue({"textbook_site", "textbook_artifact", "claims_rank", "rag"} <= code)
        for name in sorted(code):
            with self.subTest(module=name):
                self.assertTrue(fingerprinted(f"tools/{name}.py"), f"tools/{name}.py is not in FILTER")
        import rag
        import textbook_site
        self.assertTrue(fingerprinted(rag.PACKAGE.as_posix()), f"{rag.PACKAGE} is not in FILTER")
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


class Admit(unittest.TestCase):
    STATE = {"schema": tp.SCHEMA, "url": URL, "sha": "1234567890abcdef", "inputs": "f" * 64,
             "files": {"index.html": "h"}}

    def decide(self, **over):
        values = dict(state=self.STATE, inputs="e" * 64, event="schedule", switch="", crowd="", token="true",
                      cap=12, commits=[], today=TODAY)
        values.update(over)
        return tp.admit(**values)

    def test_a_run_may_publish_when_everything_holds(self):
        self.assertEqual(self.decide(), (True, "0 of 12 publishes today"))
        self.assertEqual(self.decide(state={})[0], True)

    def test_the_first_reason_that_does_not_hold_is_named(self):
        self.assertEqual(self.decide(switch="off"), (False, "the variable TEXTBOOK_ARTIFACT is off"))
        self.assertIn("crowd mode", self.decide(crowd="true", switch="")[1])
        self.assertIn("CLAUDE_CODE_OAUTH_TOKEN", self.decide(token="false")[1])
        self.assertIn("CLAUDE_CODE_OAUTH_TOKEN", self.decide(token="")[1])
        ok, why = self.decide(inputs="f" * 64)
        self.assertFalse(ok)
        self.assertIn("built from 1234567 is already published", why)
        self.assertTrue(self.decide(inputs="f" * 64, event="workflow_dispatch")[0], "a person asked")
        edition = commit_of("Edition 1234567: 3 files published, 0 removed, 2 unchanged", f"{TODAY}T10:00:00Z")
        ok, why = self.decide(commits=[edition] * 12)
        self.assertFalse(ok)
        self.assertEqual(why, "12 publishes today reached the day's cap of 12 (the variable TEXTBOOK_PUBLISHES_PER_DAY)")
        self.assertEqual(self.decide(commits=[edition] * 11), (True, "11 of 12 publishes today"))
        self.assertFalse(self.decide(commits=[edition] * 3, cap=3)[0])

    def test_the_days_count_takes_todays_editions_alone(self):
        commits = [commit_of("Edition a: 1 files published", f"{TODAY}T01:00:00Z"),
                   commit_of("Inputs at a: nothing to publish", f"{TODAY}T02:00:00Z"),
                   commit_of("Edition b: 1 files published", "2026-10-23T23:59:00Z"),
                   commit_of("Edition c: incomplete (2 of 3)", f"{TODAY}T03:00:00Z"),
                   {"sha": "x"}]
        self.assertEqual(tp.publishes_today(commits, TODAY), 2)
        self.assertEqual(tp.publishes_today(None, TODAY), 0)

    def test_the_cap_has_a_default_and_a_most(self):
        for text, want in (("", 12), ("abc", 12), ("7", 7), ("100", 50), ("0", 1), (" 3 ", 3), (None, 12)):
            self.assertEqual(tp.cap_of(text), want, text)

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
            text = tp.prompt(first, "abc1234def", "/w/textbook-out")
        self.assertIn(f"capabilities {json.dumps(tp.CAPABILITIES)}", text)
        self.assertIn('"mcp": {"servers": [{"server": "GitHub", "tools": ["actions_run_trigger", "get_file_contents"]}]}', text)
        self.assertIn("icon book", text)
        self.assertIn('label "Edition abc1234"', text)
        self.assertIn('title "SchwingNet Textbook"', text)
        self.assertIn("file_path /w/textbook-out/index.html, root /w/textbook-out", text)
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
            text = tp.prompt(later, "abc1234def")
        self.assertIn(f"The artifact exists: {URL}", text)
        self.assertIn("1. Action read with that url", text)
        self.assertIn("2. Action list with scope files", text)
        self.assertIn("mapped to\n   null", text)
        self.assertIn("overwrite_unread", text)
        self.assertIn("file_path textbook-out/index.html, root textbook-out", text)
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
                text = tp.prompt(later, "abc1234def")
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
                self.assertNotIn("SECRETWORD", tp.prompt(plan, "abc1234def"))

    def test_a_session_on_the_owners_computer_writes_its_markers_to_the_answer_file(self):
        # No execution file carries a local session's answer back, so it writes the marker lines to
        # a file of the work folder, and may write that file alone.
        with tempfile.TemporaryDirectory() as folder:
            first, later = self.plans(folder)
            for plan in (first, later):
                text = tp.prompt(plan, "abc1234def", "/h/ed/textbook-out", "/h/ed/answer.txt")
                self.assertIn("one private claude.ai artifact from the\nowner's computer", text)
                self.assertIn("Write (only for the\nanswer file, /h/ed/answer.txt), write no other file", text)
                self.assertIn("write the line ARTIFACT_TOOL_MISSING to /h/ed/answer.txt", text)
                self.assertIn("Last of all, write the marker lines of your answer to /h/ed/answer.txt", text)
                self.assertIn("file_path /h/ed/textbook-out/index.html, root /h/ed/textbook-out", text)
                self.assertNotIn("GitHub Actions", text)
                self.assertNotIn("SECRETWORD", text)
            action = tp.prompt(first, "abc1234def", "/w/textbook-out")
        self.assertIn("from a\nGitHub Actions run", action)
        self.assertNotIn("answer file", action)
        self.assertNotIn("Write tool", action)


class Args(unittest.TestCase):
    def test_the_sessions_arguments(self):
        self.assertEqual(tp.args_lines(), ["--max-turns 40", "--permission-mode default", "--setting-sources user",
                                           '--allowedTools "Artifact,Read"'])
        self.assertEqual(tp.args_lines("claude-opus-4-1", "high", "claude-sonnet-4-5")[1:4],
                         ["--model claude-opus-4-1", "--effort high", "--fallback-model claude-sonnet-4-5"])
        odd = " ".join(tp.args_lines("bad name; rm -rf", "silly", "claude-opus-4-1"))
        self.assertNotIn("--model", odd)
        self.assertNotIn("--effort", odd)
        self.assertIn("--fallback-model claude-opus-4-1", odd)
        self.assertNotIn("--fallback-model", " ".join(tp.args_lines("m", "", "m")))


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

    def test_the_answer_comes_from_the_execution_files_last_result(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "execution.json"
            self.assertEqual(tp.result_text(path), "")
            path.write_text(json.dumps([{"type": "system"}, {"type": "assistant", "message": {}},
                                        {"type": "result", "result": "first"},
                                        {"type": "result", "result": f"done\nARTIFACT_URL={URL}"}]), encoding="utf-8")
            self.assertEqual(tp.result_text(path), f"done\nARTIFACT_URL={URL}")
            path.write_text(json.dumps({"type": "result", "result": "alone"}), encoding="utf-8")
            self.assertEqual(tp.result_text(path), "alone")
            path.write_text("{broken", encoding="utf-8")
            self.assertEqual(tp.result_text(path), "")


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
            text = tp.prompt(plan_, "abc1234def", "/w/textbook-out")
            self.assertEqual(tp.REFUSED in text, says, text)
            self.assertEqual(f"capabilities {json.dumps(tp.BASIC_CAPABILITIES)} instead" in text, says)

    def test_a_publish_that_stopped_partway_records_the_link_with_nothing_published(self):
        state = {"schema": tp.SCHEMA, "url": URL, "sha": "old", "inputs": "o", "files": {"index.html": "x"}}
        new, message = tp.record(state, self.PLAN, dict(self.WHOLE, incomplete="2 of 3"), "abc1234def", "d", "i", RUN)
        self.assertEqual(new, {"schema": tp.SCHEMA, "url": URL, "sha": "", "built": "", "inputs": "", "run": RUN,
                               "files": {}, "incomplete": "2 of 3"})
        self.assertEqual(message, "Edition abc1234: incomplete (2 of 3); the next run publishes it whole")

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


class Command(unittest.TestCase):
    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = tp.main(list(argv))
        return code, out.getvalue()

    def test_the_steps_from_the_command_line(self):
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder)
            out = edition(temp / "textbook-out", FILES)
            code, text = self.run_main("plan", "--out", str(out), "--plan", str(temp / "plan.json"))
            self.assertEqual(code, 0)
            self.assertIn("nothing=false\nfirst=true\nchanged=5\nremoved=0\nunchanged=0\ntotal_files=5\n", text)
            self.assertIn("batches=1\n", text)
            code, text = self.run_main("prompt", "--plan", str(temp / "plan.json"), "--sha", "abc1234def",
                                       "--folder", str(out))
            self.assertEqual(code, 0)
            self.assertTrue(text.startswith("prompt<<TEXTBOOK_PROMPT\nYou are publishing"))
            self.assertTrue(text.endswith("\nTEXTBOOK_PROMPT\n"))
            self.assertIn(f"file_path {out}/index.html, root {out}", text)
            code, text = self.run_main("args", "--model", "m", "--effort", "low")
            self.assertEqual(text, 'args<<TEXTBOOK_ARGS\n--max-turns 40\n--model m\n--effort low\n--permission-mode default\n'
                                   '--setting-sources user\n--allowedTools "Artifact,Read"\nTEXTBOOK_ARGS\n')
            execution = temp / "execution.json"
            execution.write_text(json.dumps([{"type": "result", "result": "ARTIFACT_TOOL_MISSING"}]), encoding="utf-8")
            code, text = self.run_main("answer", "--execution-file", str(execution), "--out", str(temp / "answer.json"))
            self.assertEqual(code, 1)
            execution.write_text(json.dumps([{"type": "result", "result": f"ok\nARTIFACT_URL={URL}"}]), encoding="utf-8")
            code, text = self.run_main("answer", "--execution-file", str(execution), "--out", str(temp / "answer.json"))
            self.assertEqual((code, text), (0, f"url={URL}\n"))
            code, text = self.run_main("record", "--plan", str(temp / "plan.json"), "--answer", str(temp / "answer.json"),
                                       "--sha", "abc1234def", "--built", "2026-10-24T18:42:00Z", "--inputs", "i" * 64,
                                       "--run", RUN, "--write", str(temp / "new.json"), "--message", str(temp / "m.txt"))
            self.assertEqual((code, text), (0, f"url={URL}\npublished=true\n"))
            state = json.loads((temp / "new.json").read_text(encoding="utf-8"))
            self.assertEqual((state["sha"], state["inputs"], len(state["files"])), ("abc1234def", "i" * 64, 5))
            self.assertEqual((temp / "m.txt").read_text(encoding="utf-8"),
                             "Edition abc1234: 5 files published, 0 removed, 0 unchanged\n")
            code, text = self.run_main("admit", "--state", str(temp / "new.json"), "--inputs", "i" * 64,
                                       "--event", "schedule", "--token", "true", "--words", str(temp / "words.md"))
            self.assertEqual(code, 0)
            self.assertIn("admit=false\nwhy=the edition built from abc1234 is already published", text)
            self.assertIn("This run does not publish:", (temp / "words.md").read_text(encoding="utf-8"))
            (temp / "commits.json").write_text("not json", encoding="utf-8")
            code, text = self.run_main("admit", "--state", str(temp / "new.json"), "--inputs", "j" * 64,
                                       "--event", "schedule", "--token", "true", "--cap", "3",
                                       "--commits", str(temp / "commits.json"))
            self.assertIn("admit=true\nwhy=0 of 3 publishes today\n", text)

    def test_the_fingerprint_from_the_command_line(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            git(root, "init", "-q")
            write(root / "docs" / "textbook" / "01-one.md", "# 01 One\n")
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "one")
            code, text = self.run_main("inputs", "--root", str(root), "--sha", "HEAD")
            self.assertEqual(code, 0)
            self.assertRegex(text, r"^inputs=[0-9a-f]{64}\n$")


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
(out / "site.json").write_text(json.dumps({"site": sys.argv[2:], "head": head.strip()}))
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


def jobs_of(text):
    """The workflow's jobs, each as its text: a job starts two spaces in under the key jobs."""
    jobs, current = {}, None
    for line in text.split("jobs:\n", 1)[1].split("\n"):
        start = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if start:
            current = start.group(1)
            jobs[current] = []
        elif current is not None:
            jobs[current].append(line)
    return {name: "\n".join(lines) for name, lines in jobs.items()}


class Workflow(unittest.TestCase):
    TEXT = WORKFLOW.read_text(encoding="utf-8")
    JOBS = jobs_of(TEXT)

    def test_the_push_filter_is_the_fingerprints_list_on_main_alone(self):
        block = self.TEXT.split("  push:\n", 1)[1].split("  schedule:", 1)[0]
        self.assertIn("    branches: [main]\n", block)
        self.assertEqual(re.findall(r'^\s+- "([^"]+)"$', block, re.M), tp.FILTER)
        self.assertIn('    - cron: "13,43 * * * *"\n', self.TEXT)
        self.assertIn("  workflow_dispatch:\n", self.TEXT)

    def test_every_action_is_pinned_and_nothing_is_granted_at_the_top(self):
        self.assertIn("\npermissions: {}\n", self.TEXT)
        for uses in re.findall(r"uses:\s*(\S+)", self.TEXT):
            self.assertRegex(uses, r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")
        self.assertIn("concurrency:\n  group: textbook-artifact\n  cancel-in-progress: true\n", self.TEXT)
        self.assertNotIn("persist-credentials: true", self.TEXT)
        self.assertEqual(self.TEXT.count("persist-credentials: false"), self.TEXT.count("actions/checkout@"))

    def test_the_switches_the_cap_and_the_token_are_read_where_the_helper_expects_them(self):
        edition = self.JOBS["edition"]
        for needed in ("SWITCH: ${{ vars.TEXTBOOK_ARTIFACT }}", "CAP: ${{ vars.TEXTBOOK_PUBLISHES_PER_DAY }}",
                       "CROWD: ${{ vars.CLAUDE_CROWD }}", "HAVE_TOKEN: ${{ needs.values.outputs.token }}",
                       "EVENT: ${{ github.event_name }}", 'commits?sha=$STATE_BRANCH&since=', "contents/state.json?ref=$STATE_BRANCH"):
            self.assertIn(needed, edition, needed)
        self.assertIn("TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN != '' }}", self.JOBS["values"])
        self.assertIn("STATE_BRANCH: textbook-artifact", self.TEXT)
        called = set(re.findall(r"python3 tools/textbook_publish\.py (\w+)", self.TEXT))
        self.assertEqual(called, {"inputs", "admit", "plan", "prompt", "args", "answer", "record"})
        self.assertIn("tools/textbook_site.py", edition)
        self.assertIn('tools/textbook_artifact.py "$RUNNER_TEMP/site" textbook-out', edition)

    def test_the_session_runs_where_nothing_can_be_written_and_may_fail_without_losing_the_record(self):
        edition, record = self.JOBS["edition"], self.JOBS["record"]
        self.assertIn("anthropics/claude-code-action@", edition)
        self.assertNotIn("anthropics/claude-code-action@", record)
        self.assertNotIn("secrets.", record)
        self.assertIn("      contents: read", edition)
        self.assertNotIn("contents: write", edition)
        self.assertIn("      contents: write", record)
        step = edition.split("        id: claude\n", 1)[1].split("      - name:", 1)[0]
        self.assertIn("continue-on-error: true", step)
        self.assertIn("claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}", step)
        self.assertIn("claude_args: ${{ steps.brief.outputs.args }}", step)
        before = edition.split("        id: claude\n", 1)[0]
        self.assertIn("-name CLAUDE.md", before)
        self.assertIn("-name .claude -type d -prune", before)
        self.assertIn('tools/usage.py actions --root "$GITHUB_WORKSPACE"', edition)
        self.assertIn("name: symphony-usage-${{ github.run_id }}-${{ github.run_attempt }}-textbook-artifact", edition)
        self.assertIn("if-no-files-found: ignore", edition)

    def test_the_record_is_written_fast_forward_and_a_foreign_branch_is_left_alone(self):
        record = self.JOBS["record"]
        self.assertIn('--force-with-lease="refs/heads/$STATE_BRANCH:$previous"', record)
        self.assertIn("grep -v -x state.json", record)
        self.assertIn("git commit-tree", record)
        self.assertIn('parent=(-p "$previous")', record)
        self.assertIn("needs.edition.outputs.record == 'true'", record)
        self.assertNotIn("--force ", record)


if __name__ == "__main__":
    unittest.main()
