"""tools/usage.py: a session's usage read from its transcript and its
helpers', written on each commit as one trailer line by way of a real git
repository's commit-msg hook, with the session's profile on a second line
where tools/profile.py is beside it, and a run in Actions read from the
action's execution file; the switch turns both off, and inside Actions a
session records nothing, so no run counts twice."""

import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import usage  # noqa: E402

profile = usage.profiler()

# The environment the commit tests run in: without git's own variables, which
# would point the hooks' git at another repository, and without the two the
# tool reads to decide whether to record at all, GitHub Actions and the
# metrics switch, which a person may have turned off in their own shell, as
# usage.py's docstring tells them to; a test that wants either sets it itself.
QUIET = {key: value for key, value in os.environ.items()
         if not key.startswith("GIT_") and key not in ("GITHUB_ACTIONS", usage.SWITCH_VARIABLE)}
# No git of the commit tests runs gc or maintenance on its own: git 2.55
# starts it detached after a commit, and it raced the removal of a scratch
# folder; set in the environment and in each repository's config, as
# tests/test_claim_skill.py sets them.
NO_MAINTENANCE = {"gc.auto": "0", "gc.autoDetach": "false", "maintenance.auto": "false",
                  "maintenance.autoDetach": "false", "receive.autogc": "false"}
# Nor does any read the config of the person running them, whose
# commit.verbose, say, puts a diff in a bare commit's message.
GIT_QUIET = {"GIT_CONFIG_COUNT": str(len(NO_MAINTENANCE)),
             **{f"GIT_CONFIG_KEY_{i}": key for i, key in enumerate(NO_MAINTENANCE)},
             **{f"GIT_CONFIG_VALUE_{i}": value for i, value in enumerate(NO_MAINTENANCE.values())},
             "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def assistant(message_id, model, usage_fields, at="2026-10-12T10:00:00Z"):
    return {"type": "assistant", "timestamp": at, "requestId": "r-" + message_id,
            "message": {"id": message_id, "model": model, "usage": usage_fields}}


def used(inp=0, write=0, read=0, out=0, hour=None):
    fields = {"input_tokens": inp, "cache_creation_input_tokens": write, "cache_read_input_tokens": read,
              "output_tokens": out}
    if hour is not None:
        fields["cache_creation"] = {"ephemeral_5m_input_tokens": write - hour, "ephemeral_1h_input_tokens": hour}
    return fields


def write_lines(path, entries):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e) + "\n" for e in entries) + "not json\n", encoding="utf-8")


def asking(message_id, usage_fields, at, *tools):
    """An assistant line that asks for tools, each a (name, input) pair whose
    call's id is the message's and its place."""
    entry = assistant(message_id, "claude-opus-5-5", usage_fields, at)
    entry["message"]["content"] = [{"type": "tool_use", "id": f"{message_id}-{index}", "name": name, "input": given}
                                   for index, (name, given) in enumerate(tools)]
    return entry


def answer(tool_id, text, at, error=False):
    block = {"type": "tool_result", "tool_use_id": tool_id, "content": text, "is_error": error}
    return {"type": "user", "timestamp": at, "message": {"role": "user", "content": [block]}}


class ReadingATranscript(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.transcript = self.folder / "abcdef12-3456.jsonl"

    def test_each_message_counts_once_and_helpers_count_too(self):
        write_lines(self.transcript, [
            {"type": "user", "timestamp": "2026-10-12T10:00:00Z"},
            assistant("m1", "claude-opus-5-5", used(10, 100, 1000, 5), "2026-10-12T10:00:10Z"),
            assistant("m1", "claude-opus-5-5", used(10, 100, 1000, 5), "2026-10-12T10:00:11Z"),
            assistant("m2", "claude-opus-5-5", used(1, 0, 2000, 7, hour=0), "2026-10-12T10:01:00Z"),
            assistant("s", usage.SYNTHETIC, used(99, 99, 99, 99), "2026-10-12T10:01:01Z"),
            {"type": "user", "timestamp": "2026-10-12T11:00:00Z"},
        ])
        write_lines(self.folder / "abcdef12-3456" / "subagents" / "agent-1.jsonl",
                    [assistant("h1", "claude-haiku-5-5", used(3, 30, 300, 4, hour=10))])
        found = usage.session_usage(self.transcript)
        self.assertEqual(found["models"], {"claude-opus-5-5": [11, 100, 0, 3000, 12],
                                           "claude-haiku-5-5": [3, 20, 10, 300, 4]})
        self.assertEqual(found["seconds"], 61, "the hour's pause is left out")

    def test_what_was_spent_since_the_last_commit(self):
        before = {"models": {"m": [1, 2, 3, 4, 5]}, "seconds": 10}
        now = {"models": {"m": [2, 2, 3, 6, 9], "n": [0, 0, 0, 0, 0], "o": [1, 0, 0, 0, 0]}, "seconds": 25}
        self.assertEqual(usage.since(now, before), {"models": {"m": [1, 0, 0, 2, 4], "o": [1, 0, 0, 0, 0]}, "seconds": 15})

    def test_the_trailer_round_trips(self):
        value = usage.trailer("6e4cb20b-affa", {"models": {"b": [1, 2, 3, 4, 5], "a": [0, 0, 0, 1, 0]}, "seconds": 9})
        self.assertEqual(value, "v1 session=6e4cb20b seconds=9 a=0,0,0,1,0 b=1,2,3,4,5")
        message = f"Do it\n\nWhy.\n\nCo-Authored-By: x\nSymphony-Usage: {value}\n"
        self.assertEqual(usage.parse_trailer(message), [("6e4cb20b", 9, {"a": [0, 0, 0, 1, 0], "b": [1, 2, 3, 4, 5]})])
        self.assertEqual(usage.parse_trailer("symphony-usage: v1 session=x seconds=no m=1,2\n"), [("x", 0, {})])
        self.assertEqual(usage.parse_trailer("Symphony-Usage: v2 later\n"), [])

    def test_a_count_too_long_or_in_other_digits_is_passed_over_as_unreadable(self):
        # Anyone who can push a commit writes its message, and int() refuses
        # a string of more than 4,300 digits with ValueError, which stopped
        # the metrics run; a count is read as the Actions records' are, a
        # whole number below 2 ** 53 in ASCII digits.
        huge = "1" * 4301
        self.assertEqual(usage.parse_trailer(f"Symphony-Usage: v1 session=x seconds={huge} m={huge},0,0,0,0\n"),
                         [("x", 0, {})])
        self.assertEqual(usage.parse_trailer(f"Symphony-Usage: v1 session=x seconds={2 ** 53} m=0,0,0,0,{2 ** 53}\n"),
                         [("x", 0, {})])
        self.assertEqual(usage.parse_trailer("Symphony-Usage: v1 session=x seconds=\u0663 m=\u0663,0,0,0,0\n"),
                         [("x", 0, {})])
        self.assertEqual(usage.parse_trailer(f"Symphony-Usage: v1 session=x seconds={2 ** 53 - 1} m=0,0,0,0,7\n"),
                         [("x", 2 ** 53 - 1, {"m": [0, 0, 0, 0, 7]})])

    def test_a_line_with_a_long_run_of_blanks_is_read_in_one_pass(self):
        # A value read lazily up to optional blanks before the line's end took
        # time that grew with the square of a run of blanks inside the line:
        # a second for 16,000 of them, and the metrics run reads each message
        # more than once, under a 20-minute limit.
        message = "Symphony-Usage: v1 session=x" + " " * 100_000 + "m=1,2,3,4,5" + " " * 100_000 + "\n"
        started = time.monotonic()
        self.assertEqual(usage.parse_trailer(message), [("x", 0, {"m": [1, 2, 3, 4, 5]})])
        self.assertLess(time.monotonic() - started, 1.0)
        self.assertEqual(usage.parse_trailer("Symphony-Usage: v1 \t session=y\t \r\n"), [("y", 0, {})])

    def test_a_byte_that_is_not_utf8_costs_its_line_alone(self):
        """A read that ends inside a character Claude Code is still writing,
        an em dash cut after two of its three bytes, passes over that line
        and reads the rest."""
        line = json.dumps(assistant("m1", "claude-opus-5-5", used(10, 0, 100, 5)))
        self.transcript.write_bytes(line.encode("ascii") + b'\n{"type": "user", "text": "cut \xe2\x80\n'
                                    + line.replace("m1", "m2").encode("ascii") + b"\n")
        self.assertEqual(usage.session_usage(self.transcript)["models"], {"claude-opus-5-5": [20, 0, 0, 200, 10]})

    def test_a_line_with_a_byte_that_is_not_utf8_is_passed_over_whole(self):
        """Read with a stand-in character, a bad byte in a message's id made
        another message of the same one, counted twice, and one in a model's
        name a model no trailer can carry."""
        line = json.dumps(assistant("m1", "claude-opus-5-5", used(10, 0, 100, 5)))
        self.transcript.write_bytes(line.encode("ascii") + b"\n" + line.replace('"m1"', '"m\xff1"').encode("latin-1")
                                    + b"\n" + line.replace("opus", "op\xffus").replace("m1", "m3").encode("latin-1")
                                    + b"\n")
        self.assertEqual(usage.session_usage(self.transcript)["models"], {"claude-opus-5-5": [10, 0, 0, 100, 5]})

    def test_the_trailer_carries_eight_characters_of_the_session_and_nothing_more(self):
        spent = {"models": {"m": [1, 0, 0, 0, 1]}, "seconds": 1}
        self.assertTrue(usage.trailer("session_01AMrLKnvPcvNBSchUXZbDDX", spent).startswith("v1 session=01AMrLKn "))
        self.assertTrue(usage.trailer("6e4cb20b-affa-5339", spent).startswith("v1 session=6e4cb20b "))
        self.assertTrue(usage.trailer("a b;c$d", spent).startswith("v1 session=abcd "))


class ARepository(unittest.TestCase):
    """A real repository whose commit-msg hook runs the tools copied into it."""

    COPIED = ("usage.py",)

    def setUp(self):
        environment = mock.patch.dict(os.environ, {**QUIET, **GIT_QUIET}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        self.folder = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.repo = self.folder / "repo"
        (self.repo / "tools").mkdir(parents=True)
        for name in self.COPIED:
            shutil.copy(ROOT / "tools" / name, self.repo / "tools" / name)
        shutil.copytree(ROOT / "tools" / "sdlc_protocol", self.repo / "tools" / "sdlc_protocol")
        self.git("init", "-q")
        for key, value in NO_MAINTENANCE.items():
            self.git("config", key, value)
        self.transcript = self.folder / "s1.jsonl"

    def git(self, *args):
        done = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c",
                               "commit.gpgsign=false", *args], cwd=self.repo, capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout.strip()

    def hook(self, command="git commit -m x", session="6e4cb20b-affa-5339", where=None):
        payload = {"session_id": session, "transcript_path": str(self.transcript), "cwd": str(where or self.repo),
                   "tool_input": {"command": command}}
        self.assertEqual(usage.main(["hook"], stdin=io.StringIO(json.dumps(payload))), 0)

    def shell_commit(self, *args, environ=None, config=(), where=None):
        """git commit as Claude Code's shell runs it, its editor true, with
        git's own options (config) before commit, in the repository or a
        folder of it (where): the result, which may be git's refusal."""
        return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c",
                               "commit.gpgsign=false", *config, "commit", *args], cwd=where or self.repo,
                              capture_output=True, text=True, timeout=60,
                              env={**os.environ, "GIT_EDITOR": "true", **(environ or {})})

    def commit(self, name, where=None):
        where = where or self.repo
        (where / name).write_text(name, encoding="ascii")
        self.git("-C", str(where), "add", name)
        self.git("-C", str(where), "commit", "-q", "-m", f"Add {name}\n\nCo-Authored-By: someone")
        return self.git("-C", str(where), "log", "-1", "--format=%B")


class Commits(ARepository):
    """The hook and the commit-msg hook in a real repository, here one whose
    tools hold usage.py alone, as a copy may that has no profile.py, so the
    usage line stands by itself."""

    def test_each_commit_carries_what_the_session_spent_since_the_last(self):
        self.assertIn("commit-msg hook in place", usage.install(cwd=self.repo))
        write_lines(self.transcript, [assistant("m1", "claude-opus-5-5", used(10, 0, 100, 5))])
        self.hook()
        first = self.commit("a.txt")
        self.assertEqual(usage.parse_trailer(first), [("6e4cb20b", 0, {"claude-opus-5-5": [10, 0, 0, 100, 5]})])
        self.assertTrue(first.rstrip().endswith("Symphony-Usage: v1 session=6e4cb20b seconds=0 claude-opus-5-5=10,0,0,100,5"))
        self.assertIn("Co-Authored-By: someone", first)
        write_lines(self.transcript, [assistant("m1", "claude-opus-5-5", used(10, 0, 100, 5)),
                                      assistant("m2", "claude-opus-5-5", used(1, 0, 50, 2))])
        self.hook()
        second = self.commit("b.txt")
        self.assertEqual(usage.parse_trailer(second)[0][2], {"claude-opus-5-5": [1, 0, 0, 50, 2]})

    def test_a_commit_no_session_asked_for_carries_nothing(self):
        usage.install(cwd=self.repo)
        self.assertEqual(usage.parse_trailer(self.commit("a.txt")), [])
        write_lines(self.transcript, [assistant("m1", "m", used(1, 0, 0, 1))])
        self.hook(command="git status")
        self.assertEqual(usage.parse_trailer(self.commit("b.txt")), [])

    def test_a_usage_left_too_long_ago_belongs_to_no_commit(self):
        usage.install(cwd=self.repo)
        write_lines(self.transcript, [assistant("m1", "m", used(1, 0, 0, 1))])
        self.hook()
        pending = usage.state_dir(self.repo) / "pending.json"
        data = json.loads(pending.read_text())
        data["at"] = time.time() - usage.PENDING_FRESH - 5
        pending.write_text(json.dumps(data))
        self.assertEqual(usage.parse_trailer(self.commit("a.txt")), [])

    def test_inside_actions_or_with_the_switch_off_nothing_is_recorded(self):
        usage.install(cwd=self.repo)
        write_lines(self.transcript, [assistant("m1", "m", used(1, 0, 0, 1))])
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}):
            self.hook()
        self.assertFalse((usage.state_dir(self.repo) / "pending.json").exists())
        (self.repo / ".github").mkdir()
        (self.repo / usage.SWITCH_FILE).write_text("off\n", encoding="ascii")
        self.hook()
        self.assertFalse((usage.state_dir(self.repo) / "pending.json").exists())
        self.assertIn("switch is off", usage.install(cwd=self.repo))
        self.assertIn("GitHub Actions", usage.install(cwd=self.repo, environ={"GITHUB_ACTIONS": "true"}))

    def test_a_commit_with_nothing_for_its_message_is_still_refused(self):
        """Where the editor is true, as in Claude Code's shell, a bare git
        commit has an empty message, which git refuses; the lines must not
        give it one, and the usage waits for the commit that follows."""
        usage.install(cwd=self.repo)
        write_lines(self.transcript, [assistant("m1", "claude-opus-5-5", used(10, 0, 100, 5))])
        self.hook(command="git commit")
        (self.repo / "a.txt").write_text("a", encoding="ascii")
        self.git("add", "a.txt")
        done = self.shell_commit()
        self.assertNotEqual(done.returncode, 0, done.stdout)
        self.assertIn("empty commit message", done.stderr)
        self.assertEqual(self.git("rev-list", "--all"), "", "no commit was made")
        self.git("commit", "-q", "-m", "Add a.txt")
        self.assertEqual(usage.parse_trailer(self.git("log", "-1", "--format=%B")),
                         [("6e4cb20b", 0, {"claude-opus-5-5": [10, 0, 0, 100, 5]})])

    def test_a_commit_with_its_diff_below_the_message_and_nothing_above_is_still_refused(self):
        """With -v or commit.verbose, git puts the diff below its scissors
        line in the editor's template and cuts the message there: blanks and
        comments above it are no message, whatever the diff holds."""
        usage.install(cwd=self.repo)
        write_lines(self.transcript, [assistant("m1", "claude-opus-5-5", used(10, 0, 100, 5))])
        (self.repo / "a.txt").write_text("a", encoding="ascii")
        self.git("add", "a.txt")
        for command, args in (("git commit -v", ("-v",)), ("git commit", ("-c", "commit.verbose=true"))):
            self.hook(command=command)
            done = self.shell_commit(*args) if args[0] == "-v" else subprocess.run(
                ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.verbose=true",
                 "commit"], cwd=self.repo, capture_output=True, text=True, timeout=60,
                env={**os.environ, "GIT_EDITOR": "true"})
            self.assertIn("empty commit message", done.stderr, command)
        self.assertEqual(self.git("rev-list", "--all"), "", "no commit was made")

    def test_a_message_given_keeps_its_comment_like_lines_and_its_usage(self):
        """A message given with -m keeps a line that starts with #, as git
        keeps it, and the usage goes on it; an empty one given is refused."""
        usage.install(cwd=self.repo)
        write_lines(self.transcript, [assistant("m1", "claude-opus-5-5", used(10, 0, 100, 5))])
        (self.repo / "a.txt").write_text("a", encoding="ascii")
        self.git("add", "a.txt")
        self.hook(command="git commit -m ''")
        self.assertIn("empty commit message", self.shell_commit("-m", "").stderr)
        self.hook(command="git commit -m '#42 fix login'")
        self.assertEqual(self.shell_commit("-m", "#42 fix login").returncode, 0)
        message = self.git("log", "-1", "--format=%B")
        self.assertEqual(message.splitlines()[0], "#42 fix login")
        self.assertEqual(usage.parse_trailer(message), [("6e4cb20b", 0, {"claude-opus-5-5": [10, 0, 0, 100, 5]})])

    def test_a_message_of_comments_alone_is_refused_wherever_git_takes_them_out(self):
        """git takes the comments out where its config says, where a
        shortened --cleanup or --edit says and where an e runs together with
        other flags; a message of comments alone is then empty, and the lines
        must not give it a subject. git tells the hook by GIT_EDITOR whether
        it opened the editor, so a bare commit the hook did not see, after
        one that failed, is refused too."""
        usage.install(cwd=self.repo)
        write_lines(self.transcript, [assistant("m1", "claude-opus-5-5", used(10, 0, 100, 5))])
        (self.repo / "a.txt").write_text("a", encoding="ascii")
        self.git("add", "a.txt")
        for config, args in ((("-c", "commit.cleanup=strip"), ("-m", "#42 fix login")),
                             ((), ("-m", "#42 fix login", "--clean=strip")), ((), ("-m", "#42 fix login", "--ed")),
                             ((), ("-m", "#42 fix login", "-ae")), ((), ("-s",))):
            self.hook(command=shlex.join(["git", *config, "commit", *args]))
            self.assertIn("empty commit message", self.shell_commit(*args, config=config).stderr, args)
        self.git("config", "commit.cleanup", "strip")
        self.hook(command="git commit -m '#42 fix login'")
        self.assertIn("empty commit message", self.shell_commit("-m", "#42 fix login").stderr, "commit.cleanup")
        self.git("config", "--unset", "commit.cleanup")
        self.hook(command="git commit -m 'Add notes'")
        self.assertIn("empty commit message", self.shell_commit().stderr, "after a failed commit")
        # Where : is the person's own editor, git leaves GIT_EDITOR as it is,
        # and the words say that git opened it.
        for args in ((), ("-e", "-m", "#42 fix login"), ("-m", "#42 fix login", "--edit")):
            self.hook(command=shlex.join(["git", "commit", *args]))
            self.assertIn("empty commit message", self.shell_commit(*args, environ={"GIT_EDITOR": ":"}).stderr, args)
        self.assertEqual(self.git("rev-list", "--all"), "", "no commit was made")

    def test_a_message_git_opens_no_editor_for_keeps_its_comment_like_subject(self):
        """--amend --no-edit keeps the commit's message as it is, a subject
        such as "#42 fix login" with it, since git opens no editor for it."""
        usage.install(cwd=self.repo)
        (self.repo / "a.txt").write_text("a", encoding="ascii")
        self.git("add", "a.txt")
        self.git("commit", "-q", "-m", "#42 fix login")
        write_lines(self.transcript, [assistant("m1", "claude-opus-5-5", used(10, 0, 100, 5))])
        self.hook(command="git commit --amend --no-edit")
        self.assertEqual(self.shell_commit("--amend", "--no-edit").returncode, 0)
        message = self.git("log", "-1", "--format=%B")
        self.assertEqual(message.splitlines()[0], "#42 fix login")
        self.assertEqual(usage.parse_trailer(message), [("6e4cb20b", 0, {"claude-opus-5-5": [10, 0, 0, 100, 5]})])

    def test_with_the_comment_string_git_picks_the_usage_goes_above_the_scissors(self):
        """With core.commentChar auto, git commit picks a comment string the
        message does not begin a line with, here ; for a message that begins
        with #, and git interpret-trailers, which reads auto as #, put the
        lines below the scissors line, where git cut them away."""
        usage.install(cwd=self.repo)
        self.git("config", "core.commentChar", "auto")
        self.git("config", "commit.verbose", "true")
        (self.repo / "a.txt").write_text("a", encoding="ascii")
        self.git("add", "a.txt")
        self.git("commit", "-q", "-m", "#42 fix login")
        (self.repo / "a.txt").write_text("b", encoding="ascii")
        self.git("add", "a.txt")
        write_lines(self.transcript, [assistant("m1", "claude-opus-5-5", used(10, 0, 100, 5))])
        self.hook(command="git commit --amend")
        self.assertEqual(self.shell_commit("--amend").returncode, 0)
        message = self.git("log", "-1", "--format=%B")
        self.assertEqual(message.splitlines()[0], "#42 fix login")
        self.assertEqual(usage.parse_trailer(message), [("6e4cb20b", 0, {"claude-opus-5-5": [10, 0, 0, 100, 5]})])

    def test_with_the_comment_string_git_picks_a_message_of_its_comments_alone_is_refused(self):
        """Where git picked ; for a message that began with #, and the
        editor took that line out, only git's ; comments are left: git
        stripspace, which reads auto as #, kept them as a message, and the
        lines gave git a commit of themselves alone."""
        usage.install(cwd=self.repo)
        # Two names for one setting, of which the last counts, auto in any case.
        self.git("config", "core.commentString", "%")
        self.git("config", "core.commentChar", "Auto")
        self.git("config", "commit.verbose", "true")
        (self.repo / "a.txt").write_text("a", encoding="ascii")
        self.git("add", "a.txt")
        write_lines(self.transcript, [assistant("m1", "claude-opus-5-5", used(10, 0, 100, 5))])
        self.hook(command="git commit -e -m '#42 fix login'")
        done = self.shell_commit("-e", "-m", "#42 fix login", environ={"GIT_EDITOR": "sed -i.bak /^#/d"})
        self.assertIn("empty commit message", done.stderr)
        # With no scissors line to read the string from, every string git
        # can pick for auto is tried.
        self.git("config", "commit.verbose", "false")
        self.hook(command="git commit -e -m '#42 fix login'")
        done = self.shell_commit("-e", "-m", "#42 fix login", environ={"GIT_EDITOR": "sed -i.bak /^#/d"})
        self.assertIn("empty commit message", done.stderr, "no scissors line")
        self.assertEqual(self.git("rev-list", "--all"), "", "no commit was made")

    def test_a_message_that_is_the_template_and_nothing_more_is_still_refused(self):
        """git refuses a message that is its commit template, cleaned up
        alike, and nothing more, as an unedited one; the lines would have
        made it differ, and the template's text gone in as the message."""
        usage.install(cwd=self.repo)
        write_lines(self.transcript, [assistant("m1", "claude-opus-5-5", used(10, 0, 100, 5))])
        (self.folder / "t.txt").write_text("Subject: \n\nWhy:\n# Say why.\n", encoding="ascii")
        (self.repo / "a.txt").write_text("a", encoding="ascii")
        self.git("add", "a.txt")
        # -t names the template from where the command runs, here a folder
        # below the top of the tree, where the commit-msg hook runs.
        (self.repo / "docs").mkdir()
        self.hook(command="git commit -t ../../t.txt", where=self.repo / "docs")
        done = self.shell_commit("-t", "../../t.txt", where=self.repo / "docs")
        self.assertIn("did not edit the message", done.stderr, "-t")
        self.git("config", "commit.template", str(self.folder / "t.txt"))
        self.hook(command="git commit")
        self.assertIn("did not edit the message", self.shell_commit().stderr, "commit.template")
        self.assertEqual(self.git("rev-list", "--all"), "", "no commit was made")
        self.hook(command="git commit -m 'Fix the login form'")
        self.assertEqual(self.shell_commit("-m", "Fix the login form").returncode, 0)
        self.assertEqual(usage.parse_trailer(self.git("log", "-1", "--format=%B")),
                         [("6e4cb20b", 0, {"claude-opus-5-5": [10, 0, 0, 100, 5]})])

    def test_an_amend_commit_with_nothing_past_its_subject_is_still_refused(self):
        """git refuses an amend! commit of --fixup=amend: whose body says
        nothing once cleaned up, here the body of a commit whose only line
        starts with #, or, kept verbatim, has no body at all, or follows a
        subject of two lines with no blank line between, which git reads as
        one subject; the lines would have been its body."""
        usage.install(cwd=self.repo)
        (self.repo / "a.txt").write_text("a", encoding="ascii")
        self.git("add", "a.txt")
        self.git("commit", "-q", "-m", "#42 fix login")
        (self.repo / "a.txt").write_text("b", encoding="ascii")
        self.git("add", "a.txt")
        write_lines(self.transcript, [assistant("m1", "claude-opus-5-5", used(10, 0, 100, 5))])
        self.hook(command="git commit --fixup=amend:HEAD")
        self.assertIn("empty commit message body", self.shell_commit("--fixup=amend:HEAD").stderr)
        self.hook(command="git commit --fixup=amend:HEAD --cleanup=verbatim")
        done = self.shell_commit("--fixup=amend:HEAD", "--cleanup=verbatim", environ={"GIT_EDITOR": "sed -i.bak '2,$d'"})
        self.assertIn("empty commit message body", done.stderr, "verbatim, the body taken out in the editor")
        self.hook(command="git commit --fixup=amend:HEAD")
        done = self.shell_commit("--fixup=amend:HEAD", environ={"GIT_EDITOR": "sed -i.bak '2s/^$/more/'"})
        self.assertIn("empty commit message body", done.stderr, "a subject of two lines, no blank between")
        self.assertEqual(self.git("rev-list", "--count", "HEAD"), "1", "no commit was made")

    def test_git_cuts_at_the_scissors_line_wherever_it_shows_the_diff(self):
        """git cuts the message at its scissors line with -v whatever gave
        the message, and before it reads a verbatim message as empty: the
        lines went above the line, a message of their own."""
        usage.install(cwd=self.repo)
        write_lines(self.transcript, [assistant("m1", "claude-opus-5-5", used(10, 0, 100, 5))])
        (self.repo / "a.txt").write_text("a", encoding="ascii")
        self.git("add", "a.txt")
        (self.folder / "m.txt").write_text("# ------------------------ >8 ------------------------\nbelow\n",
                                           encoding="ascii")
        self.hook(command="git commit -v -F ../m.txt")
        self.assertIn("empty commit message", self.shell_commit("-v", "-F", "../m.txt").stderr, "-F")
        self.hook(command="git commit -v --cleanup=verbatim")
        done = self.shell_commit("-v", "--cleanup=verbatim", environ={"GIT_EDITOR": "sed -i.bak '1,/>8/{/>8/!d;}'"})
        self.assertIn("empty commit message", done.stderr, "verbatim")
        self.assertEqual(self.git("rev-list", "--all"), "", "no commit was made")

    def test_a_message_of_gits_own_comments_kept_as_text_takes_no_lines(self):
        """With commit.cleanup whitespace, git keeps a bare commit's comments
        and commits them; the usage line would have been its subject, so it
        waits for the commit after."""
        usage.install(cwd=self.repo)
        self.git("config", "commit.cleanup", "whitespace")
        write_lines(self.transcript, [assistant("m1", "claude-opus-5-5", used(10, 0, 100, 5))])
        (self.repo / "a.txt").write_text("a", encoding="ascii")
        self.git("add", "a.txt")
        self.hook(command="git commit")
        self.assertEqual(self.shell_commit().returncode, 0)
        message = self.git("log", "-1", "--format=%B")
        self.assertTrue(message.startswith("# "), message)
        self.assertEqual(usage.parse_trailer(message), [])

    def test_a_scissors_line_that_crlf_ends_cuts_nothing(self):
        """git cuts only at a scissors line that LF alone ends, so one an
        editor wrote with CRLF leaves the diff below it in the message."""
        message = self.folder / "COMMIT_EDITMSG"
        message.write_bytes(b"\n# ------------------------ >8 ------------------------\r\ndiff --git a/a b/a\n")
        self.assertFalse(usage.says_nothing(message, self.repo))
        message.write_bytes(b"\n# ------------------------ >8 ------------------------\ndiff --git a/a b/a\n")
        self.assertTrue(usage.says_nothing(message, self.repo))

    def test_a_message_outside_the_locales_characters_keeps_its_usage(self):
        """The message goes to git stripspace as UTF-8: in the locale's own
        encoding, ASCII here and cp1252 on Windows, an arrow raised, and the
        commit lost its lines."""
        usage.install(cwd=self.repo)
        (self.repo / "a.txt").write_text("a", encoding="ascii")
        self.git("add", "a.txt")
        self.git("commit", "-q", "-m", "Fix the caf\u00e9 \u2192 bar")
        write_lines(self.transcript, [assistant("m1", "claude-opus-5-5", used(10, 0, 100, 5))])
        self.hook(command="git commit --amend")
        ascii_locale = {"LC_ALL": "C", "LANG": "C", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0"}
        self.assertEqual(self.shell_commit("--amend", environ=ascii_locale).returncode, 0)
        message = self.git("log", "-1", "--format=%B")
        self.assertTrue(message.startswith("Fix the caf\u00e9 \u2192 bar"), message)
        self.assertEqual(usage.parse_trailer(message), [("6e4cb20b", 0, {"claude-opus-5-5": [10, 0, 0, 100, 5]})])

    def test_a_merge_that_takes_the_usage_keeps_its_subject(self):
        """git merge leaves its message with no newline at the end, and git
        interpret-trailers joined the lines to it: the usage line in the
        merge's subject."""
        usage.install(cwd=self.repo)
        self.commit("a.txt")
        base = self.git("rev-parse", "--abbrev-ref", "HEAD")
        self.git("checkout", "-q", "-b", "side")
        self.commit("b.txt")
        self.git("checkout", "-q", base)
        self.commit("c.txt")
        write_lines(self.transcript, [assistant("m1", "claude-opus-5-5", used(10, 0, 100, 5))])
        self.hook(command="git commit -m x")
        done = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "merge", "-q", "side"],
                              cwd=self.repo, capture_output=True, text=True, timeout=60,
                              env={**os.environ, "GIT_EDITOR": "true"})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.git("log", "-1", "--format=%s"), "Merge branch 'side'")
        self.assertEqual(usage.parse_trailer(self.git("log", "-1", "--format=%B")),
                         [("6e4cb20b", 0, {"claude-opus-5-5": [10, 0, 0, 100, 5]})])

    def test_what_the_words_say_of_the_editor_and_the_cleanup(self):
        """The --cleanup a command gives and whether git opens the editor,
        read as git's option parser reads the words: shortened long options,
        short ones run together, a value taken from the next word, and
        nothing after --."""
        for command, read in (("git commit", (None, True)), ("git commit -v", (None, True)),
                              ("git commit --amend", (None, True)), ("git commit -m x", (None, False)),
                              ("git commit -qam x", (None, False)), ("git commit -mx", (None, False)),
                              ("git commit --message=x", (None, False)), ("git commit --mess x", (None, False)),
                              ("git commit -F m.txt", (None, False)), ("git commit --file m.txt", (None, False)),
                              ("git commit -m x -e", (None, True)), ("git commit -em ''", (None, True)),
                              ("git commit -aem x", (None, True)), ("git commit -m x -ae", (None, True)),
                              ("git commit -m x --ed", (None, True)), ("git commit -m -e", (None, False)),
                              ("git commit -e -m x --no-edit", (None, False)),
                              ("git commit --amend --no-edit", (None, False)), ("git commit -C HEAD", (None, False)),
                              ("git commit -c HEAD", (None, True)), ("git commit --fixup=HEAD", (None, False)),
                              ("git commit --fixup=amend:HEAD", (None, True)), ("git commit --squash HEAD", (None, True)),
                              ("git commit -t t.txt", (None, True)), ("git commit --author -m x", (None, True)),
                              ("git commit -m x --cleanup=strip", ("strip", False)),
                              ("git commit --cleanup strip -m x", ("strip", False)),
                              ("git commit -m x --clean=strip", ("strip", False)),
                              ("git commit --cleanup=verbatim", ("verbatim", True)),
                              ("git commit -Smykey", (None, True)), ("git commit -- -m", (None, True)),
                              ("git commit -m A=1 --cleanup=strip", ("strip", False))):
            self.assertEqual(usage.commit_options(usage.commit_arguments(command))[:2], read, command)

    def test_what_the_words_say_of_the_template_and_a_fixup(self):
        for command, read in (("git commit", (None, False)), ("git commit -t t.txt", ("t.txt", False)),
                              ("git commit -tt.txt", ("t.txt", False)), ("git commit --templ t.txt", ("t.txt", False)),
                              ("git commit --no-template", ("", False)), ("git commit -qat t.txt", ("t.txt", False)),
                              ("git commit --fixup=amend:HEAD", (None, True)), ("git commit --fixup HEAD", (None, True)),
                              ("git commit --no-fixup", (None, False))):
            self.assertEqual(usage.commit_options(usage.commit_arguments(command))[2:], read, command)

    def test_a_clones_own_commit_msg_hook_is_left_alone(self):
        hooks = Path(self.git("rev-parse", "--absolute-git-dir")) / "hooks"
        hooks.mkdir(exist_ok=True)
        (hooks / "commit-msg").write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
        self.assertIn("left as it is", usage.install(cwd=self.repo))
        self.assertEqual((hooks / "commit-msg").read_text(), "#!/bin/sh\nexit 0\n")

    def test_the_profiler_is_loaded_once(self):
        self.assertIs(usage.profiler(), usage.profiler())
        self.assertIs(usage.profiler(), profile)

    def test_the_hook_reads_only_a_git_commit(self):
        for command, commits in (("git commit -m x", True), ("git -C . commit -qm x", True),
                                 ("cd x && git commit --amend --no-edit", True), ("echo git commit", False),
                                 ("git log --grep commit", False), ("GIT_EDITOR=true git commit", True),
                                 ("gh pr create", False), ("", False),
                                 # A message in a here-document, an apostrophe in it, read as a
                                 # quote left open and hid the commit; a body is data.
                                 ("git commit -F - <<'EOF'\nIt's done\nEOF", True),
                                 ("cat > m.txt <<'EOF'\nIt's done\nEOF\ngit commit -F m.txt", True),
                                 ("cat > s.sh <<'EOF'\ngit commit -m x\nEOF", False),
                                 ("git commit -m \"$(cat <<'EOF'\nIt's done\nEOF\n)\"", True),
                                 # A << in a message that spans lines opens nothing, and a " in
                                 # the body of one inside $( ) in double quotes ends no string.
                                 ("git commit -m \"Read them\n\nA body after <<EOF is data.\nMore.\"", True),
                                 ("git commit -m \"$(cat <<'EOF'\nThe 6\" display\nEOF\n)\"", True),
                                 # Here-documents opened on one line at two depths of $( ): the
                                 # inner body follows the newline inside it, the outer the line.
                                 ("git commit -F - <<'EOF' && gh pr create --body \"$(cat <<'BODY'\nPR body\nBODY\n"
                                  ")\"\nCommit message\nEOF", True),
                                 ("cat > notes.md <<'EOF' && git commit -m \"$(cat <<'MSG'\nAdd notes\nMSG\n)\"\n"
                                  "# Notes\nEOF", True),
                                 ("cat <<EOF >/dev/null; out=$(true\ngit commit -m wip)\nbody\nEOF", True),
                                 # Inside $( ), bash 5.2 ends a body at its delimiter and the ).
                                 ("git commit -m \"$(cat <<'EOF'\nhello\nEOF)\"\nls", True),
                                 # The ) closes its frame, and )) closes two where no arithmetic is open.
                                 ("git commit -m \"$(cat <<'EOF'\nmsg\nEOF\n)\" && cat > notes <<'X'\nit's\nX", True),
                                 ("echo $(echo $(echo a)) <<EOF\nit's\nEOF\ngit commit -m x", True),
                                 # A delimiter longer than a few letters, a carriage return in it,
                                 # one that starts with a -, a comment after $(, and one after a
                                 # line carried on with a backslash.
                                 ("git commit -F - <<'END_OF_MESSAGE'\nIt's done\nEND_OF_MESSAGE", True),
                                 ("cat > m.txt <<'EOF'\r\nIt's done\r\nEOF\r\ngit commit -F m.txt\r\n", True),
                                 ("cat << -EOF\nit's\n-EOF\ngit commit -m x", True),
                                 ("git commit -m \"$(# note <<EOF\necho hi\n)\"", True),
                                 ("echo a \\\n#<<EOF\ngit commit -m x", True),
                                 # The bodies of a $( ) that closes on the line opening them follow
                                 # the very next newline, in quotes or a later $( ) too, first.
                                 ("cat <<A >a.txt; x=$(cat <<B)\nb-line\nB\na-line\nA\ngit commit -m wip\n", True),
                                 ("x=$(cat <<A) y=$(cat\nA\n)\ngit commit -m wip\n", True),
                                 ("x=$(cat <<A) y=$(cat <<B\nl1\nA\nl2\nB\n)\ngit commit -m wip\n", True),
                                 ("x=$(cat <<A) && echo \"q\nl1\nA\nstill quoted\"\ngit commit -m wip\n", True),
                                 ("x=$(cat <<A)\nit's\nA\ngit commit -m wip\n", True),
                                 # <( ) reads as $( ) does, a backquoted command by itself, $[ ] is
                                 # arithmetic, and inside $( ) a delimiter with a ) after it ends.
                                 ("cat <(cat <<EOF\na\nEOF)\ngit commit -m wip\n", True),
                                 ("x=`cat <<EOF\nhi\nEOF`\ngit commit -m wip\n", True),
                                 ("x=`cat <<EOF`\ngit commit -m wip\nEOF\n", True),
                                 ("x=`cat <<'EOF'\nit's\nEOF`\ngit commit -m wip\n", True),
                                 ("echo $[1<<2]\ngit commit -m wip\n", True),
                                 ("x=$(cat <<EOF\nhi\nEOFX) && git commit -m wip\n", True),
                                 # What follows such a delimiter is read anew, a # there a comment;
                                 # a backquote a backslash escapes ends nothing; $[ ] nests.
                                 ("x=$(cat <<EOF\nEOF#)\ncat <<B\nb\nB)\ngit commit -m wip\n", True),
                                 ("x=`cat <<'EOF'\nit\\`s, it's\nEOF`\ngit commit -m wip\n", True),
                                 ("echo $[a[1]<<2] <<EOF\nit's\nEOF\ngit commit -m wip\n", True),
                                 # A reserved word or a wrapper before git is read past, as the guard
                                 # reads one before a push.
                                 ("if git commit; then echo done; fi", True), ("{ git commit -m x; }", True),
                                 ("! git commit -m x", True), ("time git commit -m x", True),
                                 ("time -p git commit -m x", True), ("nice -n 5 git commit -m x", True),
                                 ("env GIT_EDITOR=true git commit -m x", True), ("command git commit -m x", True),
                                 ("timeout 60 git commit -m x", True), ("command -v git commit", False),
                                 # A body that runs to the end after a backslash-newline takes the
                                 # backslash; a newline in backquotes reads bodies handed on; $[ ]
                                 # runs past its line.
                                 ("git commit -m x $(cat <<E) \\\nmore\n", True),
                                 ("x=$(cat <<A) ; y=`echo\nl1\nA\n`\ngit commit -m x\n", True),
                                 ("x=\"$(cat <<A)\" ; y=\"`echo\nl1\nA\n`\"\ngit commit -m x\n", True),
                                 ("echo $[1 +\n1<<2]\ngit commit -m x\n", True)):
            self.assertEqual(usage.is_commit(command), commits, command)

    def test_a_payload_the_hook_cannot_read_passes(self):
        for text in ("not json", "[]", json.dumps({"tool_input": "git commit"})):
            self.assertEqual(usage.main(["hook"], stdin=io.StringIO(text)), 0)


class ProfiledCommits(ARepository):
    """With tools/profile.py beside usage.py, as in every copy of the
    template, each commit carries the session's profile since its last
    commit too, on a line of its own after the usage line."""

    COPIED = ("usage.py", "profile.py", "economics.py")
    SESSION = "6e4cb20b-affa-5339"
    # A call that reads a file and runs a failing command, its context 4,010
    # tokens; then a compaction, and a call of 1,200 that reads the file again.
    FIRST = [asking("m1", used(10, 4000, 0, 5), "2026-10-12T10:00:00Z",
                    ("Read", {"file_path": "/r/a.py"}), ("Bash", {"command": "ls"})),
             answer("m1-0", "x" * 300, "2026-10-12T10:00:02Z"),
             answer("m1-1", "boom", "2026-10-12T10:00:03Z", error=True)]
    SECOND = [{"type": "system", "subtype": "compact_boundary", "timestamp": "2026-10-12T10:00:04Z"},
              asking("m2", used(1200, 0, 0, 7), "2026-10-12T10:00:05Z", ("Read", {"file_path": "/r/a.py"})),
              answer("m2-0", "y" * 50, "2026-10-12T10:00:06Z")]
    # A call of 1,301 tokens that runs the first call's command again.
    THIRD = [asking("m3", used(1, 0, 1300, 3), "2026-10-12T10:00:08Z", ("Bash", {"command": "ls"})),
             answer("m3-0", "z", "2026-10-12T10:00:09Z")]

    def setUp(self):
        super().setUp()
        usage.install(cwd=self.repo)

    def test_each_commit_carries_the_profile_since_the_last(self):
        write_lines(self.transcript, self.FIRST)
        self.hook(session=self.SESSION)
        first = self.commit("a.txt")
        usage_line, profile_line = first.rstrip().split("\n")[-2:]
        self.assertTrue(usage_line.startswith("Symphony-Usage: v1 session=6e4cb20b "), first)
        self.assertTrue(profile_line.startswith("Symphony-Profile: v1 session=6e4cb20b "), first)
        self.assertEqual(profile.parse_trailer(first), [("6e4cb20b", {
            "calls": 2, "failed": 1, "repeated": 0, "reads": 1, "rereads": 0, "read_bytes": 300, "reread_bytes": 0,
            "peak": 4010, "compactions": 0, "drops": 0, "tool_seconds": 3})])
        write_lines(self.transcript, self.FIRST + self.SECOND)
        self.hook(session=self.SESSION)
        second = self.commit("b.txt")
        self.assertEqual(usage.parse_trailer(second)[0][2], {"claude-opus-5-5": [1200, 0, 0, 0, 7]})
        # The peak is the second call's, not the session's; the Read repeats
        # the first one's and reads a.py again.
        self.assertEqual(profile.parse_trailer(second), [("6e4cb20b", {
            "calls": 1, "failed": 0, "repeated": 1, "reads": 1, "rereads": 1, "read_bytes": 50, "reread_bytes": 50,
            "peak": 1200, "compactions": 1, "drops": 1, "tool_seconds": 1})])

    def test_a_last_commit_recorded_without_a_profile_leaves_one_commit_without_it(self):
        """A hook older than the profile line kept the usage of the session's
        last commit and no profile: the counts since that commit cannot be
        told, so the next commit carries the usage line alone, and the one
        after it the profile since."""
        state = usage.kept_dir(self.repo) / f"{self.SESSION}.json"
        state.write_text(json.dumps({"models": {"claude-opus-5-5": [1, 0, 0, 0, 1]}, "seconds": 0}))
        write_lines(self.transcript, self.FIRST)
        self.hook(session=self.SESSION)
        first = self.commit("a.txt")
        self.assertEqual(usage.parse_trailer(first)[0][2], {"claude-opus-5-5": [9, 4000, 0, 0, 4]})
        self.assertEqual(profile.parse_trailer(first), [])
        write_lines(self.transcript, self.FIRST + self.SECOND)
        self.hook(session=self.SESSION)
        self.assertEqual(profile.parse_trailer(self.commit("b.txt"))[0][1]["calls"], 1)

    def test_a_profile_the_hook_cannot_read_leaves_that_commit_without_the_line_and_the_next_counts_it(self):
        write_lines(self.transcript, self.FIRST)
        self.hook(session=self.SESSION)
        self.commit("a.txt")
        write_lines(self.transcript, self.FIRST + self.SECOND)
        with mock.patch.object(usage, "profiler", side_effect=OSError("no profile.py")):
            self.hook(session=self.SESSION)
        second = self.commit("b.txt")
        self.assertEqual(usage.parse_trailer(second)[0][2], {"claude-opus-5-5": [1200, 0, 0, 0, 7]})
        self.assertEqual(profile.parse_trailer(second), [])
        write_lines(self.transcript, self.FIRST + self.SECOND + self.THIRD)
        self.hook(session=self.SESSION)
        third = self.commit("c.txt")
        self.assertEqual(usage.parse_trailer(third)[0][2], {"claude-opus-5-5": [1, 0, 0, 1300, 3]})
        # Counted from the first commit, the last whose profile is known: the
        # second's Read and the third's ls, both repeats of the first's.
        self.assertEqual(profile.parse_trailer(third), [("6e4cb20b", {
            "calls": 2, "failed": 0, "repeated": 2, "reads": 1, "rereads": 1, "read_bytes": 50, "reread_bytes": 50,
            "peak": 1301, "compactions": 1, "drops": 1, "tool_seconds": 2})])

    def test_kept_counts_that_cannot_be_read_start_the_count_from_now(self):
        """Counts kept at the last commit as kept() keeps them, or empty,
        are counted from; any other shape, a damaged file or another
        version's, gives no line, so no line claims what one carried."""
        write_lines(self.transcript, self.FIRST)
        now = usage.profile_so_far(self.transcript)
        kept = profile.kept(now)
        self.assertIn("calls=2 ", usage.profile_line(self.SESSION, now, {"models": {}, "profile": {}})[0])
        line, keep = usage.profile_line(self.SESSION, now, {"models": {}, "profile": kept})
        self.assertIn("calls=0 ", line)
        self.assertEqual(keep, kept)
        broken = [{"api_calls": 0}, {"sums": None, "api_calls": 0}, {"sums": [], "api_calls": 0},
                  {"sums": {**kept["sums"], "calls": -1000}, "api_calls": 0}, {"sums": kept["sums"]},
                  {"sums": {**kept["sums"], "calls": "40"}, "api_calls": 0},
                  {"sums": kept["sums"], "api_calls": -1}, {"sums": {"calls": 1}, "api_calls": 0}]
        for earlier in broken:
            self.assertEqual(usage.profile_line(self.SESSION, now, {"models": {}, "profile": earlier}), (None, kept),
                             earlier)

    def test_the_usage_is_left_before_the_profile_is_read(self):
        """Reading the profile takes longer than reading the usage: a hook
        stopped while it reads the profile, at Claude Code's timeout for a
        hook, has left the usage for the commit already."""
        write_lines(self.transcript, self.FIRST)
        with mock.patch.object(usage, "profile_so_far", side_effect=SystemExit("stopped")), \
                self.assertRaises(SystemExit):
            self.hook(session=self.SESSION)
        first = self.commit("a.txt")
        self.assertEqual(usage.parse_trailer(first)[0][2], {"claude-opus-5-5": [10, 4000, 0, 0, 5]})
        self.assertEqual(profile.parse_trailer(first), [])
        write_lines(self.transcript, self.FIRST + self.SECOND)
        self.hook(session=self.SESSION)
        self.assertEqual(profile.parse_trailer(self.commit("b.txt"))[0][1]["calls"], 3,
                         "the first commit carried no line, so the second counts from the start")

    def test_a_commit_whose_hook_read_nothing_keeps_nothing(self):
        """A commit whose hook read nothing at all, a transcript not there
        for that one hook, carries no line and keeps nothing, so the next
        line counts from the last line and claims nothing it carried."""
        write_lines(self.transcript, self.FIRST)
        self.hook(session=self.SESSION)
        self.commit("a.txt")
        kept = usage.kept_dir(self.repo) / f"{self.SESSION}.json"
        before = kept.read_text()
        write_lines(self.transcript, [])
        self.hook(session=self.SESSION)
        self.assertEqual(usage.parse_trailer(self.commit("b.txt")), [])
        self.assertEqual(kept.read_text(), before)
        write_lines(self.transcript, self.FIRST + self.SECOND)
        self.hook(session=self.SESSION)
        third = self.commit("c.txt")
        self.assertEqual(usage.parse_trailer(third)[0][2], {"claude-opus-5-5": [1200, 0, 0, 0, 7]})
        self.assertEqual(profile.parse_trailer(third)[0][1]["calls"], 1)

    def test_counts_that_fall_for_good_are_counted_on_from(self):
        """A transcript replaced under the session reads below the counts
        kept: that commit carries no line and keeps the lower counts, so
        the commits after it carry lines again; keeping the old counts left
        every later commit without one until the session spent past them."""
        write_lines(self.transcript, self.FIRST + self.SECOND)
        self.hook(session=self.SESSION)
        self.commit("a.txt")
        replaced = [asking("m4", used(5, 0, 0, 2), "2026-10-12T11:00:00Z", ("Bash", {"command": "pwd"})),
                    answer("m4-0", "/r", "2026-10-12T11:00:01Z")]
        write_lines(self.transcript, replaced)
        self.hook(session=self.SESSION)
        self.assertEqual(usage.parse_trailer(self.commit("b.txt")), [])
        more = [asking("m5", used(5, 0, 0, 2), "2026-10-12T11:00:02Z", ("Bash", {"command": "date"})),
                answer("m5-0", "now", "2026-10-12T11:00:03Z")]
        write_lines(self.transcript, replaced + more)
        self.hook(session=self.SESSION)
        third = self.commit("c.txt")
        self.assertEqual(usage.parse_trailer(third)[0][2], {"claude-opus-5-5": [5, 0, 0, 0, 2]})
        self.assertEqual(profile.parse_trailer(third)[0][1]["calls"], 1)
        self.assertEqual(profile.parse_trailer(third)[0][1]["peak"], 5)

    def test_another_sessions_usage_left_while_the_profile_is_read_stays(self):
        """Two sessions in one clone: when the second one's hook leaves its
        usage while the first one's reads the profile, the first one's
        second write would put its own usage back on the second one's
        commit, so it writes nothing."""
        write_lines(self.transcript, self.FIRST)
        pending = usage.state_dir(self.repo) / "pending.json"
        other = {"session": "bbbbbbbb-other", "at": time.time(), "models": {"claude-opus-5-5": [1, 0, 0, 0, 1]},
                 "seconds": 0}

        def read_while_another_hook_runs(transcript):
            usage.write_json(pending, other)
            return {"sums": dict.fromkeys(profile.SUMS, 0), "sizes": []}

        with mock.patch.object(usage, "profile_so_far", side_effect=read_while_another_hook_runs):
            self.hook(session=self.SESSION)
        self.assertEqual(json.loads(pending.read_text()), other)

    def test_a_session_committing_from_two_worktrees_counts_nothing_twice(self):
        """A linked worktree has a git directory of its own, where the hook
        leaves what it read; the counts already written are kept in the
        common one, so the second worktree's commit counts from the first's."""
        self.git("add", "tools")
        self.git("commit", "-q", "-m", "Add the tools")
        side = self.folder / "side"
        self.git("worktree", "add", "-q", "-b", "side", str(side))
        write_lines(self.transcript, self.FIRST)
        self.hook(session=self.SESSION)
        self.commit("a.txt")
        write_lines(self.transcript, self.FIRST + self.SECOND)
        self.hook(session=self.SESSION, where=side)
        second = self.commit("b.txt", where=side)
        self.assertEqual(usage.parse_trailer(second)[0][2], {"claude-opus-5-5": [1200, 0, 0, 0, 7]})
        self.assertEqual(profile.parse_trailer(second)[0][1]["calls"], 1)
        self.assertEqual(usage.kept_dir(side), usage.kept_dir(self.repo))
        self.assertNotEqual(usage.state_dir(side), usage.state_dir(self.repo))


class AnActionsRun(unittest.TestCase):
    MESSAGES = [
        {"type": "system", "subtype": "init", "model": "claude-sonnet-5-5"},
        assistant("a1", "claude-sonnet-5-5", used(5, 10, 20, 30)),
        {"type": "result", "subtype": "success", "is_error": False, "duration_ms": 61234, "duration_api_ms": 50000,
         "num_turns": 7, "total_cost_usd": 0.42,
         "modelUsage": {"claude-sonnet-5-5": {"inputTokens": 5, "outputTokens": 30, "cacheReadInputTokens": 20,
                                              "cacheCreationInputTokens": 10, "costUSD": 0.4},
                        "claude-haiku-5-5": {"inputTokens": 1, "outputTokens": 2}}},
    ]

    def test_the_record_holds_counts_times_and_where_it_ran(self):
        record = usage.actions_record(self.MESSAGES, "worker", "workers", "nightly", 12, 40, at="2026-10-12T10:00:00Z")
        self.assertEqual(record, {
            "v": 1, "source": "actions", "workflow": "workers", "job": "worker", "worker": "nightly", "issue": 12,
            "pull": 40, "at": "2026-10-12T10:00:00Z", "seconds": 61.2, "api_seconds": 50.0, "turns": 7,
            "reported_usd": 0.42, "error": False,
            "models": {"claude-sonnet-5-5": [5, 10, 0, 20, 30], "claude-haiku-5-5": [1, 0, 0, 0, 2]}})

    # A run that read a file: an execution file has no clock, so its seconds
    # in tools are nothing; its larger context is the second call's, 36.
    READING = [
        {"type": "system", "subtype": "init", "model": "claude-sonnet-5-5"},
        {"type": "assistant", "message": {"id": "a1", "model": "claude-sonnet-5-5", "usage": used(5, 10, 20, 30),
                                          "content": [{"type": "tool_use", "id": "t1", "name": "Read",
                                                       "input": {"file_path": "/w/a.py"}}]}},
        {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1",
                                                                  "content": "abc"}]}},
        {"type": "assistant", "message": {"id": "a2", "model": "claude-sonnet-5-5", "usage": used(1, 0, 35, 4),
                                          "content": [{"type": "text", "text": "Done."}]}},
        {"type": "result", "subtype": "success", "is_error": False, "duration_ms": 1000, "num_turns": 2},
    ]
    READ = {"calls": 1, "failed": 0, "repeated": 0, "reads": 1, "rereads": 0, "read_bytes": 3, "reread_bytes": 0,
            "peak": 36, "compactions": 0, "drops": 0, "tool_seconds": 0}

    def recorded_by_a_copy(self, names, messages=None, indent=None):
        """The record a copy of the named tools writes, as each workflow runs
        one, made in the runner's temporary folder before Claude starts."""
        with tempfile.TemporaryDirectory() as folder:
            for name in names:
                source = ROOT / "tools" / name
                (shutil.copytree if source.is_dir() else shutil.copy)(source, Path(folder) / name)
            execution = Path(folder) / "execution.json"
            execution.write_text(json.dumps(messages or self.READING, indent=indent), encoding="utf-8")
            out = Path(folder) / "record.json"
            done = subprocess.run([sys.executable, str(Path(folder) / "usage.py"), "actions", "--execution-file",
                                   str(execution), "--out", str(out), "--workflow", "workers", "--job", "worker",
                                   "--root", folder], capture_output=True, text=True, timeout=60, env=QUIET)
            self.assertEqual(done.returncode, 0, done.stderr)
            return json.loads(out.read_text())

    def test_a_copy_with_the_profiler_records_the_runs_profile_and_one_without_it_the_rest(self):
        record = self.recorded_by_a_copy(("usage.py", "profile.py", "economics.py", "sdlc_protocol"))
        self.assertEqual(record["profile"], self.READ)
        alone = self.recorded_by_a_copy(("usage.py",))
        self.assertNotIn("profile", alone)
        self.assertEqual(alone["models"], record["models"])
        self.assertEqual(record["models"], {"claude-sonnet-5-5": [6, 10, 0, 55, 34]})

    def test_a_helpers_calls_in_the_runs_file_count_and_its_context_does_not(self):
        """claude-code-action writes the execution file indented, and the
        Agent SDK puts a helper's messages in it, each naming the call that
        started the helper: its call and its read count, and its 5,000
        tokens of context are its own, no peak of the run's."""
        helper = [
            {"type": "assistant", "parent_tool_use_id": "t0", "message": {
                "id": "h1", "model": "claude-haiku-5-5", "usage": used(5000, 0, 0, 2),
                "content": [{"type": "tool_use", "id": "h-t1", "name": "Read", "input": {"file_path": "/w/b.py"}}]}},
            {"type": "user", "parent_tool_use_id": "t0", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "h-t1", "content": "abcdef"}]}},
        ]
        record = self.recorded_by_a_copy(("usage.py", "profile.py", "economics.py", "sdlc_protocol"),
                                         self.READING[:3] + helper + self.READING[3:], indent=2)
        self.assertEqual(record["profile"], {**self.READ, "calls": 2, "reads": 2, "read_bytes": 9})
        self.assertEqual(record["models"]["claude-haiku-5-5"], [5000, 0, 0, 0, 2])

    def test_an_execution_file_with_a_cut_character_is_still_read(self):
        with tempfile.TemporaryDirectory() as folder:
            execution = Path(folder) / "claude-execution-output.json"
            execution.write_bytes(json.dumps(self.MESSAGES).replace("success", "succ\u2014ess").encode("utf-8")
                                  .replace("\u2014".encode("utf-8"), b"\xe2\x80"))
            out = Path(folder) / "record.json"
            argv = ["actions", "--execution-file", str(execution), "--out", str(out), "--workflow", "workers",
                    "--job", "worker", "--root", folder]
            with mock.patch("sys.stdout", io.StringIO()):
                self.assertEqual(usage.main(argv, environ={}), 0)
            self.assertEqual(json.loads(out.read_text())["models"]["claude-sonnet-5-5"], [5, 10, 0, 20, 30])

    def test_without_a_result_the_messages_are_summed_and_the_run_marked(self):
        record = usage.actions_record(self.MESSAGES[:2], "plan", "coordinator")
        self.assertTrue(record["error"])
        self.assertEqual(record["models"], {"claude-sonnet-5-5": [5, 10, 0, 20, 30]})

    def test_the_command_writes_the_record_or_says_why_not(self):
        with tempfile.TemporaryDirectory() as folder:
            execution = Path(folder) / "claude-execution-output.json"
            execution.write_text(json.dumps(self.MESSAGES), encoding="utf-8")
            out = Path(folder) / "usage" / "record.json"
            # The switch that counts is the one in the checkout --root names,
            # here a folder with no switch file, which is on, whatever the
            # repository running this test has turned its own to.
            argv = ["actions", "--execution-file", str(execution), "--out", str(out), "--workflow", "workers",
                    "--job", "worker", "--worker", "nightly", "--issue", "12", "--pull", "", "--root", folder]
            with mock.patch("sys.stdout", io.StringIO()) as printed:
                self.assertEqual(usage.main(argv, environ={}), 0)
            self.assertIn("68 tokens", printed.getvalue())
            record = json.loads(out.read_text())
            self.assertEqual((record["issue"], record["pull"]), (12, None))
            out.unlink()
            with mock.patch("sys.stdout", io.StringIO()) as printed:
                usage.main(argv, environ={"SDLC_METRICS": "off"})
            self.assertFalse(out.exists())
            self.assertIn("switch is off", printed.getvalue())
            missing = list(argv)
            missing[2] = str(Path(folder) / "none.json")
            with mock.patch("sys.stdout", io.StringIO()) as printed:
                self.assertEqual(usage.main(missing, environ={}), 0)
            self.assertIn("no execution file", printed.getvalue())
            (Path(folder) / ".github").mkdir()
            (Path(folder) / usage.SWITCH_FILE).write_text("off\n", encoding="ascii")
            with mock.patch("sys.stdout", io.StringIO()) as printed:
                self.assertEqual(usage.main(argv, environ={}), 0)
            self.assertFalse(out.exists(), "the switch of the checkout --root names says off")
            self.assertIn("switch is off", printed.getvalue())


class NeverInTheWay(unittest.TestCase):
    def test_whatever_goes_wrong_the_hook_and_the_trailer_exit_0(self):
        with mock.patch.object(usage, "run_hook", side_effect=KeyError("surprise")):
            self.assertEqual(usage.main(["hook"], stdin=io.StringIO("{}")), 0)
        with mock.patch.object(usage, "run_trailer", side_effect=TypeError("surprise")):
            self.assertEqual(usage.main(["trailer", "MSG"]), 0)


class Switch(unittest.TestCase):
    def test_the_switch_reads_as_the_metrics_tool_reads_it(self):
        import metrics
        cases = [({}, None), ({"SDLC_METRICS": "off"}, None), ({"SDLC_METRICS": "no"}, None),
                 ({"SDLC_METRICS": "on"}, "off\n"), ({}, "on\n"), ({}, "off\n"), ({}, "maybe\n"), ({}, ""),
                 ({"SDLC_METRICS": ""}, "on please\n")]
        for environ, file_text in cases:
            with tempfile.TemporaryDirectory() as folder:
                if file_text is not None:
                    (Path(folder) / ".github").mkdir()
                    (Path(folder) / usage.SWITCH_FILE).write_text(file_text, encoding="ascii")
                self.assertEqual(usage.sharing_off(folder, environ), metrics.sharing(folder, environ) == metrics.OFF,
                                 (environ, file_text))
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / ".github").mkdir()
            (Path(folder) / ".github" / "sdlc-metrics").write_text("off\n", encoding="ascii")
            self.assertTrue(usage.sharing_off(folder, {}))
        # Both names at once, as in a repository adopted again since the
        # rename: an off in either wins, as tools/metrics.py reads them.
        for new, old in (("on\n", "off\n"), ("off\n", "on\n"), ("on\n", "on\n")):
            with self.subTest(new=new, old=old), tempfile.TemporaryDirectory() as folder:
                (Path(folder) / ".github").mkdir()
                (Path(folder) / usage.SWITCH_FILE).write_text(new, encoding="ascii")
                (Path(folder) / ".github" / "sdlc-metrics").write_text(old, encoding="ascii")
                self.assertEqual(usage.sharing_off(folder, {}), "off" in (new.strip(), old.strip()))
                self.assertEqual(usage.sharing_off(folder, {}), metrics.sharing(folder, {}) == metrics.OFF)


class Wiring(unittest.TestCase):
    """Every Claude session the repository runs leaves what it spent where
    the metrics workflow reads it, and every session of a person's records
    its own on its commits."""

    WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))

    def test_every_claude_step_in_actions_is_recorded_and_kept(self):
        found = 0
        for path in self.WORKFLOWS:
            steps = path.read_text(encoding="utf-8").split("\n      - ")
            for index, step in enumerate(steps):
                if not step.startswith("uses: anthropics/claude-code-action@"):
                    continue
                found += 1
                step_id = re.search(r"\n        id: (\S+)", step)
                self.assertIsNotNone(step_id, f"{path.name}: a Claude step with no id")
                self.assertIn('cp tools/usage.py "$RUNNER_TEMP/usage.py"', steps[index - 1], path.name)
                self.assertIn('cp -r tools/profile.py tools/economics.py tools/sdlc_protocol "$RUNNER_TEMP/" || true',
                              steps[index - 1], path.name)
                record, kept = steps[index + 1], steps[index + 2]
                self.assertIn(f"steps.{step_id.group(1)}.outputs.execution_file", record, path.name)
                self.assertIn('python3 "$RUNNER_TEMP/usage.py" actions --root "$GITHUB_WORKSPACE"', record, path.name)
                self.assertIn("continue-on-error: true", record, path.name)
                self.assertIn("uses: actions/upload-artifact@v7", kept, path.name)
                self.assertIn("name: symphony-usage-${{ github.run_id }}-${{ github.run_attempt }}-", kept, path.name)
                self.assertIn("if-no-files-found: ignore", kept, path.name)
        self.assertEqual(found, 9, "workers.yml's one, coordinator.yml's four, claude.yml's one, agents.yml's one, "
                         "pool.yml's probe and drive-organize.yml's one")

    def test_the_metrics_workflow_reads_the_records_and_keeps_what_it_read(self):
        text = (ROOT / ".github" / "workflows" / "metrics.yml").read_text(encoding="utf-8")
        for needed in ("  actions: read\n", "uses: actions/cache/restore@v6", "uses: actions/cache/save@v6",
                       '--usage-cache "$RUNNER_TEMP/usage-records.json"'):
            self.assertIn(needed, text)

    def test_every_session_runs_the_hook_and_installs_the_commit_msg_hook(self):
        settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
        commands = [hook["command"] for entry in settings["hooks"]["PreToolUse"] if entry["matcher"] == "Bash"
                    for hook in entry["hooks"]]
        self.assertIn('python3 "$CLAUDE_PROJECT_DIR"/tools/usage.py hook', commands)
        start = (ROOT / ".claude" / "hooks" / "session-start.sh").read_text(encoding="utf-8")
        self.assertIn("python3 tools/usage.py install >/dev/null 2>&1 || true", start)


if __name__ == "__main__":
    unittest.main()
