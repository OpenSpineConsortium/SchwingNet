"""tools/textbook_publish.py publishes the repository's front door as one claude.ai artifact from
the owner's computer (issues #236, #277 and #294, the owner's word of 2026-10-26): the plan,
nothing where the record holds this page and these capabilities, the capabilities passed on a
first publish and again only where the record's differ; the mechanical prompt, which has the
session read the page whole before it publishes it and stop where the connector is refused, with
nothing of the page's text in it; what the answer file says; and the record a publish leaves. The
command itself is run against a bare repository standing in for GitHub: the record read and
written by fast-forward alone from a repository of its own, the page taken from main's commit, a
stop where it is already published, an artifact already at a link adopted with --url, and the
answer file the session writes deciding what is recorded."""

import datetime as dt
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import textbook_publish as tp  # noqa: E402
from test_textbook_site import GIT_ENV, QUIET  # noqa: E402

URL = "https://claude.ai/artifact/AbC123-xyz"
RUN = "local 2026-10-25T03:00:00Z"
SHA = "abc1234def567890abc1234def567890abc1234d"
PAGE, ANSWER = "/h/SchwingNet-front-door/door.html", "/h/SchwingNet-front-door/answer.txt"


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True,
                          env={**os.environ, **GIT_ENV}).stdout.strip()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def quiet(repo):
    """A scratch repository that runs no gc or maintenance of its own, set in its config too, since
    the receive-pack and upload-pack git starts for a local remote do not take the environment's."""
    for key, value in QUIET.items():
        git(repo, "config", key, value)


class ThePublish(unittest.TestCase):
    def test_the_door_reads_the_viewers_github_connector_and_nothing_else_of_the_viewers(self):
        self.assertEqual(tp.CAPABILITIES, {"mcp": {"servers": [{"server": "GitHub", "tools": tp.TOOLS}]}, "sample": {}})
        self.assertEqual(tp.TOOLS, ["get_file_contents", "list_commits", "search_code"], "read-only tools alone")
        self.assertTrue((ROOT / tp.PAGE_SOURCE).is_file())
        # The door names the same connector and calls no tool but the ones declared.
        door = (ROOT / tp.DOOR_SOURCE).read_text(encoding="ascii")
        self.assertIn('SERVER = "GitHub"', door)
        called = set(re.findall(r'call\("([a-z_]+)"', door))
        self.assertEqual(called, set(tp.TOOLS))

    def test_the_page_published_is_the_loader_which_reads_the_door_from_main(self):
        # The published page holds none of the door: it reads the door's path on main through the
        # same connector with a tool the declaration names, so the declaration covers both pages.
        self.assertEqual(tp.PAGE_SOURCE, "tools/front_door_loader.html")
        loader = (ROOT / tp.PAGE_SOURCE).read_text(encoding="ascii")
        self.assertIn('SERVER = "GitHub"', loader)
        self.assertIn(f'DOOR = "{tp.DOOR_SOURCE}", REF = "refs/heads/main"', loader)
        self.assertEqual(set(re.findall(r'callTool\(SERVER, "([a-z_]+)"', loader)), {"get_file_contents"})
        self.assertNotIn("listTools", loader.split("<script>")[0])
        self.assertLess(len(loader), len((ROOT / tp.DOOR_SOURCE).read_text(encoding="ascii")) // 4)


class StateFile(unittest.TestCase):
    STATE = {"schema": tp.SCHEMA, "url": URL, "sha": SHA, "page": "p" * 64, "capabilities": tp.CAPABILITIES}

    def test_an_absent_broken_or_foreign_record_is_read_as_none(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "state.json"
            self.assertEqual(tp.load_state(""), {})
            self.assertEqual(tp.load_state(str(path)), {})
            path.write_text("not json", encoding="utf-8")
            self.assertEqual(tp.load_state(str(path)), {})
            # The edition's record of #236 and #277: the reader is a new artifact, published once.
            path.write_text(json.dumps({"schema": "textbook-artifact/1", "url": URL}), encoding="utf-8")
            self.assertEqual(tp.load_state(str(path)), {})
            path.write_text(json.dumps(self.STATE), encoding="utf-8")
            self.assertEqual(tp.load_state(str(path)), self.STATE)


class Plan(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.page = Path(temp.name) / "door.html"
        self.page.write_text("<title>SchwingNet Front Door</title>\n<p>The door.</p>\n", encoding="utf-8")

    def recorded(self, **fields):
        state = {"schema": tp.SCHEMA, "url": URL, "page": tp.sha256(self.page), "capabilities": tp.CAPABILITIES}
        return dict(state, **fields)

    def test_a_first_publish_makes_the_artifact_with_its_capabilities(self):
        plan = tp.plan(self.page, {})
        self.assertEqual(plan, {"first": True, "url": "", "nothing": False, "page": tp.sha256(self.page),
                                "bytes": self.page.stat().st_size, "adopted": False, "clear": False,
                                "capabilities": tp.CAPABILITIES})

    def test_a_declaration_that_drops_a_held_capability_clears_the_artifact_first(self):
        held = {"schema": tp.SCHEMA, "url": URL, "page": "o" * 64}
        # An adopted link holds the reader's files, unknown to the record: cleared first.
        self.assertTrue(tp.plan(self.page, tp.adopt({}, URL))["clear"])
        # A record naming a capability the door no longer declares: cleared first.
        self.assertTrue(tp.plan(self.page, dict(held, capabilities={"files": {"project": "chan_x"}, "sample": {}}))["clear"])
        # A record whose capabilities the door's declaration all keeps: nothing to clear.
        self.assertFalse(tp.plan(self.page, dict(held, capabilities={"sample": {}}))["clear"])
        # The same capabilities, or a first publish: nothing goes out again, nothing to clear.
        self.assertFalse(tp.plan(self.page, dict(held, capabilities=tp.CAPABILITIES))["clear"])
        self.assertFalse(tp.plan(self.page, {})["clear"])

    def test_the_page_and_capabilities_recorded_are_nothing_to_publish(self):
        plan = tp.plan(self.page, self.recorded())
        self.assertTrue(plan["nothing"])
        self.assertEqual((plan["first"], plan["url"], plan["capabilities"]), (False, URL, None))

    def test_a_changed_page_is_published_again_and_keeps_its_capabilities(self):
        plan = tp.plan(self.page, self.recorded(page="o" * 64))
        self.assertFalse(plan["nothing"])
        self.assertIsNone(plan["capabilities"], "a redeploy that passes none keeps what the artifact has")

    def test_a_record_with_other_capabilities_or_none_passes_them_again(self):
        for capabilities in ({"sample": {}}, None):
            with self.subTest(recorded=capabilities):
                plan = tp.plan(self.page, self.recorded(capabilities=capabilities))
                self.assertFalse(plan["nothing"])
                self.assertEqual(plan["capabilities"], tp.CAPABILITIES)


class Prompt(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        page = Path(temp.name) / "door.html"
        page.write_text("<title>SchwingNet Front Door</title>\n<p>SECRETWORD-ZXQ</p>\n", encoding="utf-8")
        self.first = tp.plan(page, {})
        self.later = tp.plan(page, {"schema": tp.SCHEMA, "url": URL, "page": "o" * 64, "capabilities": tp.CAPABILITIES})
        self.again = tp.plan(page, {"schema": tp.SCHEMA, "url": URL, "page": "o" * 64, "capabilities": {"sample": {}}})
        self.adopted = tp.plan(page, tp.adopt({}, URL))
        self.dropping = tp.plan(page, {"schema": tp.SCHEMA, "url": URL, "page": "o" * 64,
                                       "capabilities": {"files": {"project": "chan_x"}, "sample": {}}})

    def text(self, plan):
        return tp.prompt(plan, SHA, PAGE, ANSWER)

    def test_the_page_is_read_whole_before_any_publish(self):
        for plan in (self.first, self.later, self.again):
            text = self.text(plan)
            read = text.index(f"1. Read {PAGE} with the Read tool, the whole of it, before any publish.")
            self.assertLess(read, text.index("Publish it") if plan["first"] else text.index("Action publish"))
            self.assertIn(f"publish nothing but {PAGE}", text)
            self.assertIn(f"{self.first['bytes']} bytes of HTML that hold no file of the repository", text)

    def test_the_first_publish_makes_the_artifact_with_its_capabilities_and_label(self):
        text = self.text(self.first)
        self.assertIn(f"2. Publish it: action publish, file_path {PAGE}, title \"{tp.TITLE}\", icon door, description\n"
                      f"   \"{tp.DESCRIPTION}\", capabilities {json.dumps(tp.CAPABILITIES)}, label \"Door abc1234\".",
                      text)
        self.assertNotIn("Action read", text)

    def test_a_later_publish_reads_the_artifact_first_and_passes_no_capabilities(self):
        text = self.text(self.later)
        self.assertIn(f"2. Action read with url {URL}", text)
        self.assertIn(f"3. Action publish with url {URL}, file_path {PAGE}, label \"Door abc1234\"; pass no "
                      "capabilities; pass no icon,\n   title or description", text)
        self.assertNotIn("cleared", text)
        self.assertNotIn("capabilities {", text)
        self.assertNotIn(tp.REFUSED, text)

    def test_a_later_publish_says_what_the_link_holds_and_needs_no_confirmation(self):
        # The owner's first run of 2026-10-26 stopped at the link, since the session read the textbook
        # reader there and the prompt had not said that was the page the door replaces.
        for plan in (self.later, self.again, self.adopted):
            text = self.text(plan)
            self.assertRegex(text, rf'the textbook reader titled\s+"{tp.READER_TITLE}"')
            self.assertRegex(text, r"needs no\s+confirmation from the person")
            self.assertIn(f"Stop, writing the line {tp.MISMATCH} to {ANSWER} with what you found after it on the same line, only where\n"
                          "the read fails or shows a page that is neither the door, its loader, nor that reader.", text)
            self.assertLess(text.index(tp.MISMATCH), text.index("2. Action read"), "the stop is said before the read")
        self.assertIn("Replacing that page and its declaration with the door is\nwhat this command does, on the owner's "
                      "choice of 2026-10-26", self.text(self.adopted))
        self.assertNotIn("Replacing that page", self.text(self.later))

    def test_an_adopted_link_takes_the_doors_icon_and_description_with_its_capabilities(self):
        text = self.text(self.adopted)
        self.assertIn(f"4. Action publish with url {URL}, file_path {PAGE}, label \"Door abc1234\", icon door, description\n"
                      f"   \"{tp.DESCRIPTION}\", capabilities {json.dumps(tp.CAPABILITIES)}, since the door's capabilities "
                      "are not the ones recorded; the page's own title names the artifact.", text)
        self.assertIn("the publish of step 4 needs no confirmation", text)
        self.assertNotIn("pass no icon", text)
        self.assertNotIn("Publish it: action publish", text)

    def test_a_declaration_that_drops_a_held_capability_is_cleared_first_in_the_prompt(self):
        # The owner's second run of 2026-10-26 was refused: the Artifact tool keeps a stored capability
        # (the reader's files) from being dropped silently, so the prompt clears the artifact first.
        for plan in (self.adopted, self.dropping):
            text = self.text(plan)
            self.assertIn(f"3. Action publish with url {URL}, file_path {PAGE}, label \"Door abc1234, cleared\" and "
                          "capabilities {},\n   nothing else.", text)
            self.assertIn("the Artifact tool refuses a\n   declaration that drops a stored capability unless the artifact "
                          "is cleared first", text)
            self.assertLess(text.index("2. Action read"), text.index("3. Action publish"))
            self.assertLess(text.index("3. Action publish"), text.index("4. Action publish"))
        text = self.text(self.dropping)
        self.assertIn(f"4. Action publish with url {URL}, file_path {PAGE}, label \"Door abc1234\", capabilities "
                      f"{json.dumps(tp.CAPABILITIES)}, since the door's capabilities are not the ones recorded; pass no icon,",
                      text)
        for plan in (self.later, self.again):
            self.assertNotIn("cleared", self.text(plan))
            self.assertNotIn("4. Action", self.text(plan))

    def test_capabilities_that_changed_go_again_and_their_refusal_stops_the_publish(self):
        text = self.text(self.again)
        self.assertIn(f"label \"Door abc1234\", capabilities {json.dumps(tp.CAPABILITIES)}, since the door's "
                      "capabilities are not the ones recorded", text)
        for text in (self.text(self.first), text):
            self.assertIn("If the publish is refused for its capabilities, do not publish without them", text)
            self.assertIn(f"write the line {tp.REFUSED} to the answer file", text)

    def test_the_session_writes_its_markers_to_the_answer_file_alone(self):
        for plan in (self.first, self.later):
            text = self.text(plan)
            self.assertIn(f"call\nno other tool than Artifact, Read and Write (only for the answer file, {ANSWER})", text)
            self.assertIn(f"write the line ARTIFACT_TOOL_MISSING to {ANSWER}", text)
            self.assertIn(f"write the line ARTIFACT_URL=<url> to {ANSWER} with the Write\ntool", text)
            self.assertIn("typing /exit lets the command that opened this session record it", text)
        self.assertIn("the viewer's own GitHub connector\nin claude.ai (the connector named GitHub)", text)

    def test_nothing_of_the_pages_text_is_in_the_prompt_or_the_plan(self):
        for plan in (self.first, self.later, self.again):
            self.assertNotIn("SECRETWORD", json.dumps(plan))
            self.assertNotIn("SECRETWORD", self.text(plan))


class Answer(unittest.TestCase):
    def test_the_link_is_read_from_the_last_line_alone(self):
        self.assertEqual(tp.answer_of(f"Published.\nARTIFACT_URL={URL}\n"),
                         {"url": URL, "missing_tool": False, "refused": "", "mismatch": ""})
        self.assertEqual(tp.answer_of(f"ARTIFACT_URL={URL}\nand more")["url"], "")
        self.assertEqual(tp.answer_of("ARTIFACT_URL=https://example.com/artifact/x")["url"], "")
        self.assertEqual(tp.answer_of("ARTIFACT_URL=https://claude.ai/artifact/x; rm")["url"], "")
        self.assertEqual(tp.answer_of("ARTIFACT_URL=https://claude.ai/code/artifact/0f0e-1a")["url"],
                         "https://claude.ai/code/artifact/0f0e-1a")
        self.assertEqual(tp.answer_of("")["url"], "")

    def test_a_missing_tool_and_a_refusal_are_read_with_its_words(self):
        self.assertEqual(tp.answer_of("ARTIFACT_TOOL_MISSING"),
                         {"url": "", "missing_tool": True, "refused": "", "mismatch": ""})
        self.assertEqual(tp.answer_of(f"{tp.REFUSED} files: not a member of the project\n")["refused"],
                         "files: not a member of the project")
        self.assertEqual(tp.answer_of(f"{tp.REFUSED}\n")["refused"], "no reason given")

    def test_a_mismatch_is_read_with_the_sessions_words(self):
        said = f"{tp.MISMATCH}: {URL} reads as \"Something Else\", not as the front door. Nothing was published.\n"
        self.assertEqual(tp.answer_of(said)["mismatch"],
                         f"{URL} reads as \"Something Else\", not as the front door. Nothing was published.")
        self.assertEqual(tp.answer_of(f"{tp.MISMATCH}\n")["mismatch"], "no words given")
        self.assertEqual(tp.answer_of(f"Published.\nARTIFACT_URL={URL}\n")["mismatch"], "")


class Record(unittest.TestCase):
    PLAN = {"first": True, "url": "", "nothing": False, "page": "p" * 64, "bytes": 100, "capabilities": tp.CAPABILITIES}
    WHOLE = {"url": URL, "missing_tool": False, "refused": ""}

    def test_a_publish_records_the_link_the_commit_the_page_and_the_capabilities(self):
        new, message = tp.record({}, self.PLAN, self.WHOLE, SHA, RUN)
        self.assertEqual(new, {"schema": tp.SCHEMA, "url": URL, "sha": SHA, "page": "p" * 64,
                               "capabilities": tp.CAPABILITIES, "run": RUN})
        self.assertEqual(message, "Door abc1234: published")

    def test_a_redeploy_that_passed_no_capabilities_keeps_the_recorded_ones(self):
        state = {"schema": tp.SCHEMA, "url": URL, "capabilities": {"sample": {}}}
        new, _message = tp.record(state, dict(self.PLAN, first=False, url=URL, capabilities=None), self.WHOLE, SHA, RUN)
        self.assertEqual(new["capabilities"], {"sample": {}})

    def test_a_missing_tool_a_refusal_another_artifact_or_no_link_is_refused(self):
        other = {"schema": tp.SCHEMA, "url": "https://claude.ai/artifact/other"}
        for current, answer, says in ((other, self.WHOLE, "not to the artifact https://claude.ai/artifact/other"),
                                      ({}, dict(self.WHOLE, url=""), "no ARTIFACT_URL line"),
                                      ({}, dict(self.WHOLE, missing_tool=True), "no Artifact tool"),
                                      ({}, dict(self.WHOLE, refused="mcp: not allowed"), "refuse a page that declares a connector"),
                                      ({}, dict(self.WHOLE, url="", mismatch="reads as Something Else"),
                                       "neither the door nor the reader it replaces (reads as Something Else)"),
                                      ({}, dict(self.WHOLE, url="https://claude.ai/artifact/third"), "the record or --url names")):
            plan = dict(self.PLAN, url=URL) if says.endswith("names") else self.PLAN
            with self.subTest(says=says), self.assertRaises(SystemExit) as stop:
                tp.record(current, plan, answer, SHA, RUN)
            self.assertIn(says, str(stop.exception))


class Local(unittest.TestCase):
    STATE = {"schema": tp.SCHEMA, "url": URL, "sha": "a" * 40, "page": "p" * 64, "capabilities": tp.CAPABILITIES,
             "run": "local"}
    READER = "<title>SchwingNet Front Door</title>\n<p>The door, first.</p>\n"

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
        write(self.clone / tp.PAGE_SOURCE, self.READER)
        git(self.clone, "add", "-A")
        git(self.clone, "commit", "-q", "-m", "one")
        git(self.clone, "remote", "add", "origin", str(self.origin))
        git(self.clone, "push", "-q", "origin", "main")
        self.work = self.base / "SchwingNet-front-door"
        self.remote = str(self.origin)

    def recorded(self):
        return json.loads(git(self.origin, "show", f"{tp.BRANCH}:{tp.STATE_FILE}"))

    def no_record(self):
        return git(self.origin, "branch", "--list", tp.BRANCH) == ""

    def commit(self, rel, text, message):
        write(self.clone / rel, text)
        git(self.clone, "add", "-A")
        git(self.clone, "commit", "-q", "-m", message)
        git(self.clone, "push", "-q", "origin", "main")
        return git(self.clone, "rev-parse", "HEAD")

    def session(self, answer):
        """Claude Code standing in: it checks the folder holds the page and the prompt, and writes
        the answer given."""
        def opened(command, work):
            self.assertEqual(Path(work), self.work)
            text = (Path(work) / tp.PROMPT_FILE).read_text(encoding="utf-8")
            self.assertIn(f"1. Read {(self.work / tp.PAGE).as_posix()} with the Read tool", text)
            self.assertIn(f"answer file, {(self.work / tp.ANSWER_FILE).as_posix()})", text)
            self.seen.append((Path(work) / tp.PAGE).read_text(encoding="utf-8"))
            (Path(work) / tp.ANSWER_FILE).write_text(answer, encoding="utf-8")
        self.seen = []
        return opened

    def test_the_record_is_read_and_written_by_fast_forward_alone(self):
        self.work.mkdir()
        self.assertEqual(tp.recorded_state(self.work, self.remote), {})
        self.assertFalse((self.work / tp.STATE_FILE).exists())
        first = tp.write_record(self.work, self.remote, self.STATE, "Door aaaaaaa: published")
        self.assertEqual(git(self.origin, "ls-tree", "--name-only", tp.BRANCH), tp.STATE_FILE)
        self.assertEqual(self.recorded(), self.STATE)
        self.assertEqual(tp.recorded_state(self.work, self.remote), self.STATE)
        second = tp.write_record(self.work, self.remote, dict(self.STATE, sha="b" * 40), "Door bbbbbbb: published")
        self.assertEqual(git(self.origin, "rev-parse", tp.BRANCH), second)
        self.assertEqual(git(self.origin, "rev-parse", f"{tp.BRANCH}^"), first)
        self.assertEqual(git(self.origin, "log", "-1", "--format=%s", tp.BRANCH), "Door bbbbbbb: published")
        self.assertEqual(self.recorded()["sha"], "b" * 40)

    def test_the_editions_record_is_followed_by_the_readers_on_the_same_branch(self):
        # The branch holds the record of the edition #236 and #277 published; the reader's goes on
        # it as the next commit, and the reader is a new artifact.
        self.work.mkdir()
        old = {"schema": "textbook-artifact/1", "url": "https://claude.ai/artifact/edition", "files": {}}
        edition = tp.write_record(self.work, self.remote, old, "Edition aaaaaaa: 5 files published")
        self.assertEqual(tp.recorded_state(self.work, self.remote), {})
        tp.write_record(self.work, self.remote, self.STATE, "Door aaaaaaa: published")
        self.assertEqual(git(self.origin, "rev-parse", f"{tp.BRANCH}^"), edition)

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
            tp.write_record(self.work, self.remote, self.STATE, "Door aaaaaaa: published")
        self.assertIn("notes.md", str(stop.exception))
        self.assertEqual(git(self.origin, "rev-parse", tp.BRANCH), head)

    def test_a_branch_that_moved_meanwhile_is_read_again(self):
        self.work.mkdir()
        elsewhere = self.base / "elsewhere"
        elsewhere.mkdir()
        tp.write_record(self.work, self.remote, self.STATE, "Door aaaaaaa")
        real, moved = tp.record_head, []

        def moving(repo, remote):
            head = real(repo, remote)
            if not moved:
                moved.append(head)
                tp.write_record(elsewhere, remote, dict(self.STATE, sha="c" * 40), "Door ccccccc")
            return head

        with mock.patch.object(tp, "record_head", moving):
            commit = tp.write_record(self.work, self.remote, dict(self.STATE, sha="b" * 40), "Door bbbbbbb")
        self.assertEqual(git(self.origin, "rev-parse", tp.BRANCH), commit)
        self.assertEqual(git(self.origin, "log", "--format=%s", tp.BRANCH).splitlines(),
                         ["Door bbbbbbb", "Door ccccccc", "Door aaaaaaa"])

    def test_a_work_folder_inside_the_clone_is_refused(self):
        with self.assertRaises(SystemExit):
            tp.local_publish(self.clone, self.clone / "reader", launch=False)

    def test_a_main_without_the_reader_publishes_nothing(self):
        git(self.clone, "rm", "-q", tp.PAGE_SOURCE)
        git(self.clone, "commit", "-q", "-m", "no reader")
        git(self.clone, "push", "-q", "origin", "main")
        with self.assertRaises(SystemExit) as stop:
            tp.local_publish(self.clone, self.work, launch=False)
        self.assertIn(f"{tp.PAGE_SOURCE} is not in main's commit", str(stop.exception))

    def test_the_command_takes_mains_page_opens_claude_code_and_records_its_answer(self):
        # The clone's own checkout is not what is published: main's commit on the remote is.
        sha = git(self.clone, "rev-parse", "HEAD")
        write(self.clone / tp.PAGE_SOURCE, "<p>an edit in the checkout, not on main</p>\n")
        printed = io.StringIO()
        with mock.patch.object(tp, "open_session", side_effect=self.session(f"Published.\nARTIFACT_URL={URL}\n")) as opened, \
                redirect_stdout(printed):
            self.assertEqual(tp.local_publish(self.clone, self.work, claude=sys.executable), 0)
        opened.assert_called_once()
        self.assertEqual(self.seen, [self.READER])
        state = self.recorded()
        self.assertEqual((state["schema"], state["url"], state["sha"]), (tp.SCHEMA, URL, sha))
        self.assertEqual(state["page"], tp.sha256(self.work / tp.PAGE))
        self.assertEqual(state["capabilities"], tp.CAPABILITIES)
        self.assertTrue(state["run"].startswith("local "))
        self.assertEqual(printed.getvalue(), f"Door {sha[:7]}: published\n{URL}\n")
        self.assertFalse((self.work / tp.ANSWER_FILE).exists())
        self.assertFalse((self.work / tp.META_FILE).exists())

        printed = io.StringIO()
        with mock.patch.object(tp, "open_session", side_effect=AssertionError("opened again")), redirect_stdout(printed):
            self.assertEqual(tp.local_publish(self.clone, self.work, claude=sys.executable), 0)
        self.assertIn(f"already published at {URL}", printed.getvalue())

        # A change to the repository alone publishes nothing, since the door reads it live; a change
        # to the page publishes it again.
        git(self.clone, "checkout", "-q", "--", tp.PAGE_SOURCE)
        self.commit("docs/textbook/01-one.md", "# 01 One\n", "the book moves on")
        with mock.patch.object(tp, "open_session", side_effect=AssertionError("opened again")), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(tp.local_publish(self.clone, self.work, claude=sys.executable), 0)
        newer = self.commit(tp.PAGE_SOURCE, "<title>SchwingNet Front Door</title>\n<p>The door, second.</p>\n", "door")
        with mock.patch.object(tp, "open_session", side_effect=self.session(f"ARTIFACT_URL={URL}\n")), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(tp.local_publish(self.clone, self.work, claude=sys.executable), 0)
        prompt = (self.work / tp.PROMPT_FILE).read_text(encoding="utf-8")
        self.assertIn(f"2. Action read with url {URL}", prompt)
        self.assertIn("pass no capabilities", prompt)
        self.assertEqual(self.recorded()["sha"], newer)
        self.assertEqual(git(self.origin, "rev-list", "--count", tp.BRANCH), "2")

    def test_anyway_publishes_a_page_already_published(self):
        with mock.patch.object(tp, "open_session", side_effect=self.session(f"ARTIFACT_URL={URL}\n")), \
                redirect_stdout(io.StringIO()):
            tp.local_publish(self.clone, self.work, claude=sys.executable)
            tp.local_publish(self.clone, self.work, claude=sys.executable, anyway=True)
        self.assertEqual(self.seen, [self.READER, self.READER], "each publish opens one session")
        self.assertIn("pass no capabilities", (self.work / tp.PROMPT_FILE).read_text(encoding="utf-8"))
        self.assertEqual(git(self.origin, "rev-list", "--count", tp.BRANCH), "2")

    def test_without_claude_code_the_folder_waits_with_the_two_steps(self):
        printed = io.StringIO()
        with redirect_stdout(printed):
            code = tp.main(["local", "--clone", str(self.clone), "--work", str(self.work),
                            "--claude", "no-such-claude-command"])
        self.assertEqual(code, 0)
        self.assertIn(tp.LOCAL_ASK, printed.getvalue())
        self.assertIn(f"local --record --work {self.work}", printed.getvalue())
        self.assertTrue((self.work / tp.PROMPT_FILE).is_file())
        self.assertEqual((self.work / tp.PAGE).read_text(encoding="utf-8"), self.READER)
        self.assertTrue(self.no_record())
        with self.assertRaises(SystemExit) as stop:
            tp.main(["local", "--work", str(self.work), "--record"])
        self.assertIn("wrote no answer.txt", str(stop.exception))
        (self.work / tp.ANSWER_FILE).write_text("ARTIFACT_TOOL_MISSING\n", encoding="utf-8")
        with self.assertRaises(SystemExit) as stop:
            tp.main(["local", "--work", str(self.work), "--record"])
        self.assertIn("/login", str(stop.exception))
        (self.work / tp.ANSWER_FILE).write_text(f"{tp.REFUSED} mcp: not allowed\n", encoding="utf-8")
        with self.assertRaises(SystemExit) as stop:
            tp.main(["local", "--work", str(self.work), "--record"])
        self.assertIn("GitHub connector", str(stop.exception))
        self.assertTrue(self.no_record())
        (self.work / tp.ANSWER_FILE).write_text(f"ARTIFACT_URL={URL}\n", encoding="utf-8")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(tp.finish(self.work, now=dt.datetime(2026, 10, 25, 2, 30, tzinfo=dt.timezone.utc)), 0)
        state = self.recorded()
        self.assertEqual((state["url"], state["run"]), (URL, "local 2026-10-25T02:30:00Z"))
        self.assertFalse((self.work / tp.ANSWER_FILE).exists())
        with self.assertRaises(SystemExit):
            tp.main(["local", "--work", str(self.work), "--record"])

    def test_an_artifact_already_at_a_link_is_adopted_with_url_where_the_record_names_none(self):
        # The door of 2026-10-26 was first published from a thread that could not write the record:
        # the owner's run names its link, reads it, publishes the door to it with its capabilities
        # and records the link; the next run finds it published.
        with mock.patch.object(tp, "open_session", side_effect=self.session(f"ARTIFACT_URL={URL}\n")), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(tp.main(["local", "--clone", str(self.clone), "--work", str(self.work),
                                      "--claude", sys.executable, "--url", URL]), 0)
        prompt = (self.work / tp.PROMPT_FILE).read_text(encoding="utf-8")
        self.assertIn(f"2. Action read with url {URL}", prompt)
        self.assertIn(f"capabilities {json.dumps(tp.CAPABILITIES)}, since the door's capabilities are not the ones recorded",
                      prompt)
        self.assertRegex(prompt, rf'the textbook reader titled\s+"{tp.READER_TITLE}"')
        self.assertIn("icon door", prompt)
        self.assertIn("capabilities {},\n   nothing else", prompt)
        self.assertNotIn("Publish it: action publish", prompt)
        state = self.recorded()
        self.assertEqual((state["url"], state["capabilities"]), (URL, tp.CAPABILITIES))
        printed = io.StringIO()
        with mock.patch.object(tp, "open_session", side_effect=AssertionError("opened again")), redirect_stdout(printed):
            self.assertEqual(tp.local_publish(self.clone, self.work, claude=sys.executable, url=URL), 0)
        self.assertIn(f"already published at {URL}", printed.getvalue())
        # A record that names another artifact stands, and a link that is none is refused before anything runs.
        with self.assertRaises(SystemExit) as stop:
            tp.local_publish(self.clone, self.work, claude=sys.executable, url="https://claude.ai/artifact/other")
        self.assertIn(f"the record names {URL}", str(stop.exception))
        with self.assertRaises(SystemExit) as stop:
            tp.local_publish(self.clone, self.work, claude=sys.executable, url="https://example.com/artifact/x")
        self.assertIn("not a claude.ai artifact link", str(stop.exception))
        self.assertEqual(git(self.origin, "rev-list", "--count", tp.BRANCH), "1")

    def test_a_session_that_finds_another_page_at_the_adopted_link_records_nothing(self):
        said = f"{tp.MISMATCH}: {URL} reads as \"Something Else\". Nothing was published.\n"
        with mock.patch.object(tp, "open_session", side_effect=self.session(said)), \
                redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as stop:
            tp.local_publish(self.clone, self.work, claude=sys.executable, url=URL)
        self.assertIn(f"the session read {URL} and found a page that is neither the door nor the reader it replaces "
                      f"({URL} reads as \"Something Else\". Nothing was published.)", str(stop.exception))
        self.assertTrue(self.no_record())

    def test_a_session_that_published_elsewhere_than_the_adopted_link_records_nothing(self):
        other = "https://claude.ai/artifact/other"
        with mock.patch.object(tp, "open_session", side_effect=self.session(f"ARTIFACT_URL={other}\n")), \
                redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as stop:
            tp.local_publish(self.clone, self.work, claude=sys.executable, url=URL)
        self.assertIn(f"not to the artifact {URL}", str(stop.exception))
        self.assertTrue(self.no_record())

    def test_the_default_work_folder_is_beside_the_clone(self):
        self.assertEqual(tp.default_work(self.clone), self.work)


if __name__ == "__main__":
    unittest.main()
