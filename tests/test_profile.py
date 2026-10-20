"""tools/profile.py: a session's profile from its transcript, each API call
counted once, each tool call with its answer, the files read and read
again, the context's growth shared out to the tools, the time in tools
and outside them; a record that carries counts alone; and the line a
commit carries, the counts since the session's last commit. The module is
loaded as tools/usage.py loads it, by its path, since the standard library
has a module of the same name."""

import io
import json
import random
import shutil
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import economics  # noqa: E402
import usage  # noqa: E402

profile = usage.profiler()

CWD = "/work/repo"
SHELL = {"read": 3, "filter": 0, "search": 1, "list": 0, "git": 0, "run": 1}


def at(seconds):
    """A timestamp seconds after the start of a session that began at 10:00."""
    minute, second = divmod(seconds, 60)
    return f"2026-10-15T10:{int(minute):02d}:{second:06.3f}Z"


def assistant(message_id, usage_fields, blocks, seconds, model="claude-opus-5-5", thinking=None):
    """One assistant message as the transcript writes it: one line per
    block, each carrying the whole message's usage, the lines a second
    apart."""
    lines = []
    for index, block in enumerate(blocks):
        line = {"type": "assistant", "timestamp": at(seconds + index), "cwd": CWD, "uuid": f"u-{message_id}-{index}",
                "message": {"id": message_id, "model": model, "usage": usage_fields, "content": [block]}}
        if thinking is not None and index == 0:
            line["thinkingDurationMs"] = thinking
        lines.append(line)
    return lines


def used(inp, write, read, out):
    return {"input_tokens": inp, "cache_creation_input_tokens": write, "cache_read_input_tokens": read,
            "output_tokens": out}


def tool_use(block_id, name, **given):
    return {"type": "tool_use", "id": block_id, "name": name, "input": given}


def result(block_id, content, seconds, error=False):
    block = {"type": "tool_result", "tool_use_id": block_id, "content": content}
    if error:
        block["is_error"] = True
    return {"type": "user", "timestamp": at(seconds), "cwd": CWD, "message": {"role": "user", "content": [block]}}


def prompt(text, seconds):
    return {"type": "user", "timestamp": at(seconds), "cwd": CWD, "message": {"role": "user", "content": text}}


def attachment(seconds):
    return {"type": "attachment", "timestamp": at(seconds), "attachment": {"type": "hook_success"}}


def write_lines(path, entries):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e) + "\n" for e in entries) + "half a line\n", encoding="utf-8")


def undated(entries):
    """The same messages as a run's execution file carries them: no
    timestamp and no working directory on any."""
    return [{k: v for k, v in e.items() if k not in ("timestamp", "cwd")} for e in entries]


def outside_by_definition(times, intervals):
    """profile.active_outside's measure as its docstring defines it, each
    gap less its overlap with every interval of the union: slow, and
    plainly right."""
    times, merged = sorted(times), profile.union(intervals)
    total = 0.0
    for a, b in zip(times, times[1:]):
        if b - a <= usage.IDLE_GAP:
            total += (b - a) - sum(max(0.0, min(b, end) - max(a, start)) for start, end in merged)
    return total


def helper_entries():
    """A helper's work: one call of 9,000 tokens, the helper's own context,
    that reads a file the session read too."""
    return [*assistant("h1", used(9000, 0, 0, 5), [tool_use("h-t1", "Read", file_path="/work/repo/a.py")], 100,
                       model="claude-sonnet-5-5"),
            result("h-t1", "a" * 400, 102)]


def session_entries():
    """A session of three API calls: a prompt; a call that reads a file
    with Read and two with the shell, one of them for the second time; a
    call with a failing command and a search; a last call that answers
    with text alone."""
    return [
        prompt("Please look at the code.", 0),
        *assistant("m1", used(100, 900, 0, 50), [
            {"type": "text", "text": "Reading."},
            tool_use("t1", "Read", file_path="/work/repo/a.py"),
            tool_use("t2", "Bash", command="cat b.py docs/c.md && head -n 20 a.py | grep x"),
        ], 10, thinking=1500),
        result("t1", "a" * 400, 14),
        result("t2", [{"type": "text", "text": "b" * 600}], 16),
        # The context grew by 1250 (2250 - 1000) less the 50 output tokens:
        # 1200 tokens, shared 400:600 between the two tools.
        *assistant("m2", used(0, 1250, 1000, 20), [
            tool_use("t3", "Bash", command="python3 -m unittest\nsed -n '1,5p' b.py"),
            tool_use("t4", "Grep", pattern="def"),
        ], 20),
        result("t3", "boom", 25, error=True),
        result("t4", "a.py:1:def f", 26),
        *assistant("m3", used(0, 100, 2250, 30), [{"type": "text", "text": "Done."}], 30),
        attachment(31),
    ]


class ATranscriptOnDisk(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.transcript = self.folder / "abcdef12-3456-7890.jsonl"

    def profiled(self, entries):
        write_lines(self.transcript, entries)
        return profile.profile(self.transcript)


class ReadingATranscript(ATranscriptOnDisk):
    def setUp(self):
        super().setUp()
        self.record, self.built = self.profiled(session_entries())

    def test_each_api_call_counts_once_whatever_its_lines(self):
        self.assertEqual(self.record["context"]["calls"], 3)
        self.assertEqual(self.record["models"], {"claude-opus-5-5": [100, 1250 + 900 + 100, 0, 3250, 100]})
        self.assertEqual(self.record["tokens"]["total"], 100 + 2250 + 3250 + 100)
        self.assertEqual(self.record["session"], "abcdef12")
        self.assertEqual(self.record["prompts"], 1)
        self.assertEqual(self.record["attachments"], 1)
        self.assertEqual(self.record["helpers"], {"transcripts": 0, "calls": 0, "seconds_in_tool": 0, "output_tokens": 0})

    def test_the_context_is_read_call_by_call_and_its_growth_shared_out(self):
        context = self.record["context"]
        self.assertEqual((context["first"], context["peak"], context["last"]), (1000, 2350, 2350))
        self.assertEqual(context["mean"], round((1000 + 2250 + 2350) / 3))
        self.assertEqual(context["cached_share"], round(3250 / (1000 + 2250 + 2350), 3))
        # 2250 - 1000 - 50 from the first call's tools, 2350 - 2250 - 20 from the second's.
        self.assertEqual(context["growth"], 1200 + 80)
        by_tool = self.record["calls"]["by_tool"]
        self.assertEqual(by_tool["Read"]["context_tokens_estimated"], 480)
        self.assertEqual(by_tool["Bash"]["context_tokens_estimated"], 720 + 80 * 4 // 16)
        self.assertEqual(by_tool["Grep"]["context_tokens_estimated"], 80 * 12 // 16)
        self.assertEqual((context["compactions"], context["drops"]), (0, 0))
        self.assertEqual(sorted(context), ["cached_share", "calls", "compactions", "drops", "first", "growth",
                                           "last", "mean", "peak"])

    def test_tool_calls_by_tool_with_their_answers(self):
        calls = self.record["calls"]
        self.assertEqual((calls["total"], calls["failed"], calls["unanswered"], calls["repeated"]), (4, 1, 0, 0))
        self.assertEqual(calls["by_tool"]["Bash"]["calls"], 2)
        self.assertEqual(calls["by_tool"]["Bash"]["failed"], 1)
        self.assertEqual(calls["by_tool"]["Bash"]["result_bytes"], 600 + 4)
        self.assertEqual(calls["by_tool"]["Read"]["result_bytes"], 400)
        # From the line that asked (t1 at 11 s, t2 at 12 s) to the line that
        # answered; per tool, calls that ran at once each count.
        self.assertEqual(calls["by_tool"]["Read"]["seconds_in_tool"], 3)
        self.assertEqual(calls["by_tool"]["Bash"]["seconds_in_tool"], 4 + 5)
        self.assertEqual(calls["by_tool"]["Grep"]["seconds_in_tool"], 5)
        self.assertEqual(self.record["shell"], SHELL)

    def test_reads_and_rereads(self):
        reads = self.record["reads"]
        # Read a.py; cat b.py docs/c.md and head a.py (a.py again); sed b.py (again).
        self.assertEqual(reads["calls"], 3)
        self.assertEqual(reads["files_named"], 1 + 3 + 1)
        self.assertEqual(reads["files"], 3)
        self.assertEqual(reads["rereads"], 2)
        self.assertEqual(reads["partial"], 2)
        self.assertEqual(reads["bytes"], 400 + 600 + 4)
        self.assertEqual(reads["reread_bytes"], 4)
        self.assertEqual(self.built.per_path["/work/repo/a.py"], 2)
        self.assertEqual(self.built.per_path["/work/repo/docs/c.md"], 1)

    def test_time_in_tools_and_outside_them(self):
        seconds = self.record["seconds"]
        self.assertEqual((seconds["span"], seconds["active"]), (31, 31))
        # t1 ran from 11 s to 14 and t2 from 12 to 16, together 11 to 16;
        # t3 from 20 to 25 and t4 from 21 to 26, together 20 to 26.
        self.assertEqual(seconds["in_tools"], 5 + 6)
        # The gaps between lines, 31 s in all, less the 11 s a tool was running.
        self.assertEqual(seconds["outside_tools"], 20)
        self.assertEqual(seconds["thinking"], 2)

    def test_the_record_carries_no_path_command_or_text(self):
        text = json.dumps(self.record)
        for secret in ("a.py", "b.py", "docs/c.md", "cat ", "unittest", "Please", "Done", "boom", CWD):
            self.assertNotIn(secret, text)
        self.assertEqual(self.record["schema"], "symphony-profile/1")
        self.assertEqual(self.record["started_at"], "2026-10-15T10:00:00Z")

    def test_the_report_reads_the_record(self):
        text = profile.report(self.record)
        self.assertIn("Profile of session abcdef12", text)
        self.assertIn("in tools 11 s (35% of active), outside tools 20 s (65%)", text)
        self.assertIn("the harness counted 2 s of thinking", text)
        self.assertIn("Tool calls: 4, 1 failed, 0 unanswered, 0 repeated", text)
        self.assertIn("Reads: 3 calls naming 5 files (3 distinct), 2 re-reads (40%), 2 partial", text)
        self.assertIn("Shell commands: read 3, filter 0, search 1, list 0, git 0, run 1", text)
        self.assertIn("shared out to the tools below (an estimate)", text)
        self.assertIn("compactions", text)
        self.assertTrue(text.isascii())


class TheTranscriptsClock(ATranscriptOnDisk):
    def test_an_answer_between_two_asks_of_one_call_is_timed_from_its_own_ask(self):
        """The harness writes a message's tool lines as it runs them, so a
        tool's answer can come before the message's next line; each tool
        runs from its own line, and the call's lines do not bound it."""
        text, ask_one, ask_two = assistant("m1", used(100, 0, 0, 10), [
            {"type": "text", "text": "Two at a time."},
            tool_use("t1", "Bash", command="ls"),
            tool_use("t2", "Bash", command="git status"),
        ], 10)
        ask_two["timestamp"] = at(13)
        record, _ = self.profiled([text, ask_one, result("t1", "x", 12), ask_two, result("t2", "y", 15)])
        self.assertEqual(record["context"]["calls"], 1)
        self.assertEqual(record["calls"]["total"], 2)
        self.assertEqual(record["calls"]["by_tool"]["Bash"]["seconds_in_tool"], 1 + 2)
        self.assertEqual(record["seconds"], {"span": 5, "active": 5, "in_tools": 3, "outside_tools": 2, "thinking": 0})
        self.assertEqual(record["shell"], {"read": 0, "filter": 0, "search": 0, "list": 1, "git": 1, "run": 0})

    def test_two_tools_running_at_once_count_once(self):
        self.assertEqual(profile.union([(2, 6), (1, 4), (8, 9), (9, 10)]), [(1, 6), (8, 10)])
        self.assertEqual(profile.active_outside([0, 10, 20], [(5, 12)]), 10 + 10 - 7)

    def test_the_time_outside_tools_is_what_its_definition_says(self):
        """The walk side by side gives what each gap less its overlap with
        every interval gives, on lines and tool calls drawn at random: tools
        that overlap, that take no time, that outlast the lines, and pauses
        longer than five minutes."""
        draw = random.Random(20261016)
        for _ in range(300):
            times = sorted(draw.uniform(0, 3000) for _ in range(draw.randint(0, 40)))
            intervals = []
            for _ in range(draw.randint(0, 25)):
                start = draw.uniform(-50, 3050)
                intervals.append((start, start + draw.choice([0, draw.uniform(0, 5), draw.uniform(0, 400)])))
            self.assertAlmostEqual(profile.active_outside(times, intervals), outside_by_definition(times, intervals),
                                   places=6, msg=(times, intervals))

    def test_a_long_sessions_time_outside_tools_is_read_in_one_pass(self):
        """Each gap measured against every tool call took time with the
        product of the two: about 10 seconds for a session of 3,000 calls,
        before every commit; here 40,000 lines and 20,000 calls."""
        times = [index * 0.5 for index in range(40_000)]
        intervals = [(start, start + 0.25) for start in range(20_000)]
        started = time.monotonic()
        self.assertAlmostEqual(profile.active_outside(times, intervals), 39_999 * 0.5 - 20_000 * 0.25)
        self.assertLess(time.monotonic() - started, 2.0)

    def test_an_attachment_written_as_the_answer_arrives_takes_no_time_from_the_model(self):
        """The harness writes an attachment line the instant a response
        arrives, before the response's own lines; the time before it is
        still time outside the tools."""
        entries = session_entries()
        entries.insert(6, attachment(19.9))
        record, _ = self.profiled(entries)
        self.assertEqual(record["attachments"], 2)
        self.assertEqual(record["seconds"]["outside_tools"], 20)
        self.assertEqual(record["seconds"]["in_tools"], 11)

    def test_a_pause_over_five_minutes_is_not_active(self):
        entries = session_entries()
        entries.append(prompt("Back after lunch.", 31 + 1800))
        record, _ = self.profiled(entries)
        self.assertEqual(record["seconds"]["span"], 1831)
        self.assertEqual(record["seconds"]["active"], 31)
        self.assertEqual(record["seconds"]["outside_tools"], 20)
        self.assertEqual(record["prompts"], 2)


class HelpersAndCompactions(ATranscriptOnDisk):
    def test_a_helpers_calls_count_and_its_context_does_not(self):
        write_lines(self.transcript, session_entries())
        helper = self.folder / "abcdef12-3456-7890" / "subagents" / "agent-1.jsonl"
        write_lines(helper, [
            *assistant("h1", used(10, 0, 0, 5), [tool_use("h-t1", "Read", file_path="/work/repo/a.py")], 100,
                       model="claude-sonnet-5-5"),
            result("h-t1", "a" * 400, 102),
        ])
        record, built = profile.profile(self.transcript)
        self.assertEqual(record["helpers"], {"transcripts": 1, "calls": 1, "seconds_in_tool": 2, "output_tokens": 5})
        self.assertEqual(record["calls"]["total"], 5)
        self.assertEqual(record["models"]["claude-sonnet-5-5"], [10, 0, 0, 0, 5])
        self.assertEqual(record["context"]["calls"], 3)
        # The helper reads a.py for the first time in its own context.
        self.assertEqual(record["reads"]["rereads"], 2)
        self.assertEqual(record["reads"]["files"], 3)
        self.assertEqual(profile.profile(self.transcript, helpers=False)[0]["calls"]["total"], 4)
        self.assertIn("Helpers: 1 transcripts added 1 calls, 2 s and 5 output tokens", profile.report(record))

    def test_a_messages_output_count_grows_line_by_line_and_the_largest_is_taken(self):
        """A helper's transcript writes each line of a message with the
        output count as far as the message had got; the first line's is
        the smallest."""
        lines = assistant("m1", used(2, 500, 0, 7), [
            {"type": "thinking", "thinking": "..."},
            {"type": "text", "text": "Reading."},
            tool_use("t1", "Bash", command="ls"),
        ], 10, thinking=900)
        lines[1]["message"]["usage"] = used(2, 500, 0, 8)
        lines[2]["message"]["usage"] = used(2, 500, 0, 371)
        record, _ = self.profiled([*lines, result("t1", "x", 14)])
        self.assertEqual(record["models"], {"claude-opus-5-5": [2, 500, 0, 0, 371]})
        self.assertEqual(record["tokens"]["output"], 371)
        self.assertEqual(record["context"]["first"], 502)
        self.assertEqual(record["seconds"]["thinking"], 1)

    def test_a_compaction_is_counted_and_the_drop_is_no_growth(self):
        entries = [
            *assistant("m1", used(0, 5000, 0, 100), [tool_use("t1", "Bash", command="ls")], 10),
            result("t1", "x" * 10, 12),
            {"type": "system", "subtype": "compact_boundary", "timestamp": at(13),
             "compactMetadata": {"trigger": "auto", "preTokens": 5100}},
            {"type": "user", "timestamp": at(14), "isCompactSummary": True,
             "message": {"role": "user", "content": "This session is being continued"}},
            *assistant("m2", used(1200, 0, 0, 10), [{"type": "text", "text": "Going on."}], 15),
        ]
        record, _ = self.profiled(entries)
        self.assertEqual(record["context"]["compactions"], 1)
        self.assertEqual(record["context"]["drops"], 1)
        self.assertEqual(record["context"]["growth"], 0)
        self.assertEqual(record["prompts"], 0)

    def test_a_synthetic_message_and_a_message_without_usage_are_no_api_calls(self):
        entries = [
            *assistant("s1", used(0, 0, 0, 0), [{"type": "text", "text": "No response requested."}], 1,
                       model="<synthetic>"),
            {"type": "assistant", "timestamp": at(2), "message": {"id": "n1", "model": "claude-opus-5-5",
                                                                    "content": [tool_use("t9", "Bash", command="ls")]}},
            result("t9", "", 3),
        ]
        record, _ = self.profiled(entries)
        self.assertEqual(record["context"]["calls"], 0)
        self.assertEqual(record["models"], {})
        self.assertEqual(record["calls"]["total"], 1)

    def test_a_call_the_same_as_an_earlier_one_is_repeated(self):
        """The same tool with the same input again is a repeated call, in
        its own transcript: a helper's repeat of the session's call is not."""
        entries = session_entries()
        entries[7:7] = assistant("m2b", used(0, 10, 2250, 5), [
            tool_use("t5", "Bash", command="python3 -m unittest\nsed -n '1,5p' b.py"),
            tool_use("t6", "Bash", command="git status"),
            tool_use("t7", "Read", file_path="/work/repo/a.py"),
        ], 27)
        write_lines(self.transcript, entries)
        helper = self.folder / "abcdef12-3456-7890" / "subagents" / "agent-1.jsonl"
        write_lines(helper, assistant("h1", used(10, 0, 0, 5), [tool_use("h-t1", "Bash", command="git status")], 100))
        record, _ = profile.profile(self.transcript)
        # t5 repeats t3 and t7 repeats t1; t6 is new, and the helper's git status is its own first.
        self.assertEqual(record["calls"]["repeated"], 2)
        self.assertEqual(record["calls"]["by_tool"]["Bash"]["repeated"], 1)
        self.assertEqual(record["calls"]["by_tool"]["Read"]["repeated"], 1)
        self.assertEqual(record["calls"]["total"], 8)
        self.assertIn("2 repeated", profile.report(record))

    def test_a_call_whose_usage_says_it_sent_nothing_is_not_measured(self):
        """An error line carries a usage of zeros; it is no context and
        breaks no pair of consecutive calls."""
        entries = session_entries()
        entries.insert(7, assistant("e1", used(0, 0, 0, 0), [{"type": "text", "text": "API error"}], 27)[0])
        record, _ = self.profiled(entries)
        self.assertEqual(record["context"]["calls"], 3)
        self.assertEqual((record["context"]["last"], record["context"]["growth"]), (2350, 1280))
        self.assertEqual(record["models"], {"claude-opus-5-5": [100, 2250, 0, 3250, 100]})


class TheTrailer(ATranscriptOnDisk):
    """The line each commit of a session carries beside its usage line, the
    profile since the session's last commit, as tools/usage.py's hooks
    write it from these functions."""

    def counts(self, entries):
        write_lines(self.transcript, entries)
        return profile.session_counts(self.transcript)

    def test_a_sessions_counts_are_the_records_sums_and_its_calls_contexts(self):
        now = self.counts(session_entries())
        self.assertEqual(now["sums"], {"calls": 4, "failed": 1, "repeated": 0, "reads": 5, "rereads": 2,
                                       "read_bytes": 1004, "reread_bytes": 4, "compactions": 0, "drops": 0,
                                       "tool_seconds": 11})
        self.assertEqual(now["sizes"], [1000, 2250, 2350])
        self.assertEqual(profile.since(now, {}), {**now["sums"], "peak": 2350},
                         "a session's first commit carries everything so far")
        self.assertEqual(profile.kept(now), {"sums": now["sums"], "api_calls": 3})

    def test_a_helpers_calls_and_reads_count_and_its_context_and_time_do_not(self):
        write_lines(self.folder / "abcdef12-3456-7890" / "subagents" / "agent-1.jsonl", helper_entries())
        now = self.counts(session_entries())
        self.assertEqual(now["sums"], {"calls": 5, "failed": 1, "repeated": 0, "reads": 6, "rereads": 2,
                                       "read_bytes": 1404, "reread_bytes": 4, "compactions": 0, "drops": 0,
                                       "tool_seconds": 11}, "the helper's first read of a.py is its own")
        self.assertEqual(now["sizes"], [1000, 2250, 2350], "the helper's 9,000 tokens are its own context")

    def test_each_count_is_its_rise_since_the_last_commit(self):
        entries = session_entries()
        # The first commit came after the first call's two tools answered.
        before = profile.kept(self.counts(entries[:6]))
        self.assertEqual(before["api_calls"], 1)
        spent = profile.since(self.counts(entries), before)
        # The second call's two tools: the failing command, whose sed read b.py
        # again, and the search; their union of time is 20 to 26 s.
        self.assertEqual(spent, {"calls": 2, "failed": 1, "repeated": 0, "reads": 1, "rereads": 1, "read_bytes": 4,
                                 "reread_bytes": 4, "peak": 2350, "compactions": 0, "drops": 0, "tool_seconds": 6})

    def test_the_peak_is_of_the_calls_since_the_last_commit_alone(self):
        """A session's peak before a compaction is no commit's after it."""
        entries = [
            *assistant("m1", used(0, 5000, 0, 100), [tool_use("t1", "Bash", command="ls")], 10),
            result("t1", "x" * 10, 12),
            {"type": "system", "subtype": "compact_boundary", "timestamp": at(13)},
            *assistant("m2", used(1200, 0, 0, 10), [tool_use("t2", "Bash", command="ls")], 15),
            result("t2", "y", 16),
        ]
        before = profile.kept(self.counts(entries[:2]))
        spent = profile.since(self.counts(entries), before)
        self.assertEqual((spent["peak"], spent["compactions"], spent["drops"]), (1200, 1, 1))
        self.assertEqual((spent["calls"], spent["repeated"]), (1, 1), "the second ls repeats the first")
        self.assertEqual(profile.since(self.counts(entries), {})["peak"], 5000)

    def test_only_counts_as_kept_or_none_are_counted_from(self):
        kept = profile.kept(self.counts(session_entries()))
        self.assertTrue(profile.known(kept))
        self.assertTrue(profile.known({}), "after a first commit whose profile was not read")
        for broken in ({"api_calls": 3}, {"sums": None, "api_calls": 3}, {"sums": kept["sums"], "api_calls": -1},
                       {"sums": {**kept["sums"], "calls": -1}, "api_calls": 3},
                       {"sums": {**kept["sums"], "calls": True}, "api_calls": 3},
                       {"sums": {**kept["sums"], "calls": 1.5}, "api_calls": 3},
                       {"sums": {k: v for k, v in kept["sums"].items() if k != "drops"}, "api_calls": 3}):
            self.assertFalse(profile.known(broken), broken)

    def test_a_count_never_falls_below_nothing(self):
        """Counts kept from a longer transcript than the one read now, a file
        replaced under the session, give nothing rather than less."""
        now = self.counts(session_entries()[:6])
        before = {"sums": dict.fromkeys(profile.SUMS, 10 ** 6), "api_calls": 99}
        self.assertEqual(profile.since(now, before), dict.fromkeys(profile.TRAILER_FIELDS, 0))

    def test_the_trailer_round_trips_and_carries_counts_alone(self):
        spent = profile.since(self.counts(session_entries()), {})
        value = profile.trailer("abcdef12-3456-7890", spent)
        self.assertEqual(value, "v1 session=abcdef12 calls=4 failed=1 repeated=0 reads=5 rereads=2 read_bytes=1004 "
                                "reread_bytes=4 peak=2350 compactions=0 drops=0 tool_seconds=11")
        message = (f"Do it\n\nWhy.\n\nCo-Authored-By: x\nSymphony-Usage: v1 session=abcdef12 seconds=31 m=1,2,3,4,5\n"
                   f"Symphony-Profile: {value}\n")
        self.assertEqual(profile.parse_trailer(message), [("abcdef12", spent)])
        for secret in ("a.py", "b.py", "cat", "Read", "Bash", CWD):
            self.assertNotIn(secret, value)
        self.assertEqual(profile.parse_trailer("Symphony-Profile: v2 calls=1\n"), [])
        self.assertEqual(profile.parse_trailer("Symphony-Usage: v1 session=x seconds=1 m=1,2,3,4,5\n"), [])

    def test_a_count_that_cannot_be_read_is_passed_over(self):
        # Anyone who can push writes a commit's message, and int() refuses a
        # string of more than 4,300 digits with ValueError; a count is read as
        # the usage line's are, a whole number below 2 ** 53 in ASCII digits.
        huge = "1" * 4301
        line = f"symphony-profile: v1 session=x calls={huge} failed={2 ** 53} reads=٣ paths=3 peak=7 drops\n"
        self.assertEqual(profile.parse_trailer(line), [("x", {"peak": 7})])

    def test_a_line_with_a_long_run_of_blanks_is_read_in_one_pass(self):
        message = "Symphony-Profile: v1 session=x" + " " * 100_000 + "calls=3" + " " * 100_000 + "\n"
        started = time.monotonic()
        self.assertEqual(profile.parse_trailer(message), [("x", {"calls": 3})])
        self.assertLess(time.monotonic() - started, 1.0)

    def test_only_the_messages_last_paragraph_is_read(self):
        """git and the hook put a commit's trailers in its message's last
        paragraph, so a line quoted in the body counts for nothing."""
        message = ("Explain the line\n\nIt reads like this:\nSymphony-Profile: v1 session=quoted calls=99\n \n"
                   "Co-Authored-By: x\nSymphony-Profile: v1 session=abcdef12 calls=3\n\n")
        self.assertEqual(profile.parse_trailer(message), [("abcdef12", {"calls": 3})])
        self.assertEqual(profile.parse_trailer("Symphony-Profile: v1 session=a calls=1"), [("a", {"calls": 1})])
        self.assertEqual(profile.parse_trailer(""), [])
        self.assertEqual(profile.parse_trailer(None), [])

    def test_a_key_said_again_counts_once_and_a_session_is_at_most_the_tokens_eight_characters(self):
        line = "Symphony-Profile: v1 session=abc calls=2 calls=99 session=zzz peak=x peak=7\n"
        self.assertEqual(profile.parse_trailer(line), [("abc", {"calls": 2})])
        for session in ("a" * 9, "a;b", "٣", ""):
            self.assertEqual(profile.parse_trailer(f"Symphony-Profile: v1 session={session} calls=1\n"),
                             [("", {"calls": 1})], session)


def mixed_tool_entries():
    """A call of four tools: two from MCP servers, one an Agent SDK program
    defined for itself, and the shell."""
    return [
        *assistant("m1", used(100, 900, 0, 50), [
            tool_use("t1", "mcp__github__get_file_contents", path="secret/a.py"),
            tool_use("t2", "mcp__private-crm__lookup", customer="x"),
            tool_use("t3", "lookup_customer", id=1),
            tool_use("t4", "Bash", command="ls"),
        ], 10),
        result("t1", "a" * 40, 12), result("t2", "b" * 60, 13, error=True), result("t3", "c" * 10, 14),
        result("t4", "d", 15),
        *assistant("m2", used(0, 100, 1000, 10), [{"type": "text", "text": "Done."}], 20),
    ]


class ToolNames(ATranscriptOnDisk):
    """The record names the harness's own tools and folds every other: each
    MCP tool into one row, since a server's name can say what a session
    was connected to, and any other into another."""

    def test_every_mcp_tool_is_one_row_and_any_other_tool_another(self):
        record, built = self.profiled(mixed_tool_entries())
        by_tool = record["calls"]["by_tool"]
        self.assertEqual(sorted(by_tool), ["Bash", profile.MCP_TOOLS, profile.OTHER_TOOLS])
        mcp = by_tool[profile.MCP_TOOLS]
        self.assertEqual((mcp["calls"], mcp["failed"], mcp["result_bytes"]), (2, 1, 100))
        self.assertEqual((by_tool["other"]["calls"], by_tool["other"]["result_bytes"]), (1, 10))
        self.assertEqual(sum(row["calls"] for row in by_tool.values()), record["calls"]["total"])
        text = json.dumps(record)
        for name in ("github", "private-crm", "lookup", "mcp__"):
            self.assertNotIn(name, text)
        self.assertEqual(len(built.by_tool), 4, "the names stay in memory for the screen")

    def test_the_harness_list_holds_names_alone(self):
        self.assertIn("Bash", profile.HARNESS_TOOLS)
        for name in profile.HARNESS_TOOLS:
            self.assertRegex(name, r"^[A-Z][A-Za-z]+$", "a harness tool is a word, never a server's name")
        self.assertEqual(profile.tool_kind("Read"), "Read")
        self.assertEqual(profile.tool_kind("mcp__x__y"), profile.MCP_TOOLS)
        self.assertEqual(profile.tool_kind("read"), profile.OTHER_TOOLS)

    def test_the_tools_by_name_are_printed_and_never_written(self):
        write_lines(self.transcript, [
            *mixed_tool_entries()[:-1],
            *assistant("m2", used(0, 100, 1000, 10), [tool_use("t5", "mcp__private-crm__lookup", customer="y")], 20),
            result("t5", "e", 21),
            *assistant("m3", used(0, 100, 1100, 10), [{"type": "text", "text": "Done."}], 30),
        ])
        out = self.folder / "profile.json"
        printed = io.StringIO()
        with redirect_stdout(printed):
            self.assertEqual(profile.main([str(self.transcript), "--json", str(out), "--tools", "3"]), 0)
        self.assertIn("Tools called most often, by name (not in the record):\n    2  mcp__private-crm__lookup\n"
                      "    1  Bash\n    1  lookup_customer\n", printed.getvalue())
        self.assertNotIn("mcp__", out.read_text())


def profile_line(session, **counts):
    return f"Symphony-Profile: v1 session={session} " + " ".join(f"{key}={value}" for key, value in counts.items())


def commit_of(*lines, body="Work"):
    return {"sha": "x", "commit": {"message": f"{body}\n\nCo-Authored-By: x\n" + "\n".join(lines) + "\n"}}


def counted(calls, peak, **rest):
    """A run's profile as its record carries it: every count nothing but
    calls, peak and those given."""
    return {**dict.fromkeys(profile.TRAILER_FIELDS, 0), "calls": calls, "peak": peak, **rest}


def run_record(profiled, workflow="claude", issue=None, pull=None):
    return {"workflow": workflow, "issue": issue, "pull": pull, "profile": profiled}


class SumsOverPullRequests(unittest.TestCase):
    """What tools/metrics.py writes into PROFILE.json: each pull request's
    lines and runs summed, then per work setting and on the two sides the
    coordination block compares, with the same pull requests on each side
    as economics.coordination puts there."""

    NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)

    def test_a_pull_requests_profile_is_its_commits_lines_and_the_runs_that_name_it(self):
        work = economics.Work(40, claim=12, commits=[
            commit_of(profile_line("aaaa", calls=10, reads=3, peak=500)),
            commit_of(profile_line("aaaa", calls=5, reads=1, peak=900), profile_line("bbbb", calls=2, peak=100)),
            {"sha": "x", "commit": {"message": "Quoted:\nSymphony-Profile: v1 session=x calls=99\n\nNo trailer."}},
            commit_of(profile_line("cccc")), commit_of(body="plain")])
        records = [run_record(counted(7, 300), pull=40), run_record(counted(1, 2000), issue=12),
                   run_record(counted(100, 9), issue=99), run_record(None, pull=40)]
        self.assertEqual(profile.pull_profile(work, records),
                         {**dict.fromkeys(profile.SUMS, 0), "calls": 25, "reads": 4, "peak": 2000})
        self.assertEqual(profile.commit_lines(work.commits[1]), [("aaaa", {"calls": 5, "reads": 1, "peak": 900}),
                                                                 ("bbbb", {"calls": 2, "peak": 100})])
        self.assertEqual(profile.commit_lines(work.commits[3]), [], "a line with no count is no profile")
        self.assertIsNone(profile.pull_profile(economics.Work(41, commits=work.commits[2:]), records))

    def test_a_line_or_a_run_of_zeros_is_no_profile(self):
        # A session or a run that made no call writes every count 0: no
        # profile, so it neither counts a pull request as profiled nor
        # pulls the median peak down.
        zeros = profile_line("dddd", **dict.fromkeys(profile.TRAILER_FIELDS, 0))
        work = economics.Work(42, commits=[commit_of(zeros)])
        self.assertEqual(profile.commit_lines(work.commits[0]), [])
        self.assertIsNone(profile.pull_profile(work, []))
        self.assertTrue(profile.measured({"calls": 0, "peak": 5}))
        self.assertTrue(profile.measured({"calls": 3, "peak": 0}))
        for counts in ({}, None, {"calls": 0, "peak": 0, "reads": 4}):
            self.assertFalse(profile.measured(counts), counts)

    def works(self):
        """economics' own two sides: 1 and 2 alone, 3 to 5 at work together,
        and the automation's 6 beside them all, which counts on no side."""
        def work(number, start, end, merged=True, kind="person"):
            begun = self.NOW + timedelta(hours=start)
            finished = self.NOW + timedelta(hours=end)
            return economics.Work(number, kind=kind, start=begun, end=finished,
                                  merged=finished if merged else None, opened=begun)
        return [work(1, 0, 10), work(2, 20, 30), work(3, 40, 44), work(4, 41, 45, kind="workflow_agents"),
                work(5, 42, 46, merged=False), work(6, 0, 50, kind="automation")]

    PROFILES = {1: counted(40, 1000, reads=10, rereads=4), 2: None, 3: counted(10, 3000, reads=4, rereads=1),
                4: counted(6, 500, reads=2), 5: counted(4, 2000, reads=2, rereads=1), 6: counted(100, 9)}
    OVERHEAD = [run_record(counted(4, 50), workflow="coordinator", issue=77),
                run_record(counted(500, 50), workflow="coordinator", pull=3),
                run_record(counted(600, 50), workflow="workers", issue=78)]

    def test_each_side_sums_its_profiled_pull_requests_and_the_parallel_one_the_coordinators_runs(self):
        found = profile.coordination(self.works()[::-1], self.PROFILES, self.NOW + timedelta(hours=100),
                                     window_records=self.OVERHEAD)
        alone, parallel = found["alone"], found["parallel"]
        self.assertEqual(tuple(alone), profile.GROUP_KEYS)
        self.assertEqual(tuple(found["ratios"]), profile.RATIO_KEYS)
        self.assertEqual([alone[k] for k in ("pull_requests", "merged", "profiled", "profiled_merged")], [2, 2, 1, 1])
        self.assertEqual([alone[k] for k in ("calls", "reads", "rereads", "peak_median")], [40, 10, 4, 1000])
        self.assertEqual([parallel[k] for k in ("pull_requests", "merged", "profiled", "profiled_merged")],
                         [3, 2, 3, 2])
        # 3, 4 and 5, the unmerged 5 among them, and the plan that names none.
        self.assertEqual([parallel[k] for k in ("calls", "reads", "rereads", "peak_median")], [24, 8, 2, 2000])

    def test_each_ratio_is_over_one_where_parallel_did_better(self):
        ratios = profile.coordination(self.works(), self.PROFILES, self.NOW + timedelta(hours=100),
                                      window_records=self.OVERHEAD)["ratios"]
        # Per profiled merge: one alone, two in parallel.
        self.assertEqual(ratios, {"calls_per_merge": round(40 / (24 / 2), 4), "reads_per_merge": 2.5,
                                  "rereads_per_merge": 4.0, "peak": 0.5})

    def test_a_side_with_nothing_profiled_gives_no_ratio(self):
        found = profile.coordination(self.works(), {}, self.NOW + timedelta(hours=100))
        self.assertTrue(all(value is None for value in found["ratios"].values()))
        self.assertEqual((found["alone"]["profiled"], found["alone"]["peak_median"], found["alone"]["calls"]),
                         (0, None, 0))

    def test_a_setting_sums_whatever_kind_its_pull_requests_are_and_its_median_peak_rounds_half_up(self):
        works = self.works()
        profiles = {6: counted(3, 10), 1: counted(1, 1), 2: counted(1, 2), 3: counted(1, 3)}
        row = profile.group([works[5], works[0], works[1], works[2]], profiles)
        self.assertEqual(row, {**dict.fromkeys(profile.GROUP_KEYS, 0), "pull_requests": 4, "merged": 4, "profiled": 4,
                               "profiled_merged": 4, "calls": 6, "peak_median": 3})


class WhatATextIsWorth(unittest.TestCase):
    def test_a_tools_answer_is_measured_as_the_model_saw_it(self):
        self.assertEqual(profile.text_bytes("abc"), 3)
        self.assertEqual(profile.text_bytes([{"type": "text", "text": "ab"}, {"type": "text", "text": "\u00e9"}]), 4)
        reference = {"type": "tool_reference", "tool_name": "Read"}
        self.assertEqual(profile.text_bytes([reference]), len(json.dumps(reference, sort_keys=True)))
        self.assertEqual(profile.text_bytes(None), 0)


class ReadingShellCommands(unittest.TestCase):
    def test_the_files_a_command_prints(self):
        self.assertEqual(profile.shell_reads("cat a b", "/r"), ["/r/a", "/r/b"])
        self.assertEqual(profile.shell_reads("head -n 20 a; tail -5 b; tail -c 10 c", "/r"), ["/r/a", "/r/b", "/r/c"])
        self.assertEqual(profile.shell_reads("sed -n '1,20p' tools/x.py", "/r"), ["/r/tools/x.py"])
        self.assertEqual(profile.shell_reads("sed -e 's/a/b/' -n x.py y.py", "/r"), ["/r/x.py", "/r/y.py"])
        self.assertEqual(profile.shell_reads("cat -; cat '*.py'; cat $HOME/x; cat ~/y", "/r"), [])
        self.assertEqual(profile.shell_reads("cd /elsewhere && cat a && cd sub && cat b", "/r"),
                         ["/elsewhere/a", "/elsewhere/sub/b"])
        self.assertEqual(profile.shell_reads("FOO=1 cat /abs/../x", "/r"), ["/x"])
        self.assertEqual(profile.shell_reads("cat a", ""), ["a"])
        self.assertEqual(profile.shell_reads("cat a > out 2>&1 | tee b", "/r"), ["/r/a"])
        self.assertEqual(profile.shell_reads("echo 'unclosed", "/r"), [])
        self.assertEqual(profile.shell_reads("cat `ls`; less +F x; more +10 y; sed -l 5 -n p f", "/r"),
                         ["/r/x", "/r/y", "/r/f"])

    def test_the_shells_keywords_and_wrappers_are_no_programs(self):
        self.assertEqual(profile.shell_uses("for f in a b; do cat $f; done"), {"read": 1})
        self.assertEqual(profile.shell_reads("if [ -f x ]; then cat x; fi", "/r"), ["/r/x"])
        self.assertEqual(profile.shell_uses("if [ -f x ]; then cat x; else ls; fi"), {"read": 1, "list": 1})
        self.assertEqual(profile.shell_reads("{ cat a; cat b; } > out", "/r"), ["/r/a", "/r/b"])
        self.assertEqual(profile.shell_uses("while read line; do echo $line; done < f"), {})
        self.assertEqual(profile.shell_uses("until grep -q done log; do sleep 1; done"), {"search": 1, "run": 1})
        # The case header runs to the ) and names no command; the pattern a goes with it.
        self.assertEqual(profile.shell_uses("case $x in a) cat f;; esac"), {"read": 1})
        for command in ("time cat f", "env X=1 cat f", "sudo cat f", "nohup cat f", "! cat f"):
            self.assertEqual(profile.shell_reads(command, "/r"), ["/r/f"], command)
        # A wrapper that takes a value first is not seen through.
        self.assertEqual(profile.shell_uses("timeout 10 cat f"), {"run": 1})

    def test_a_readers_options_and_their_values_are_no_files(self):
        for command in ("head --lines 20 x.py", "head --lines=20 x.py", "head -20 x.py", "head -n20 x.py",
                        "tail -n +5 x.py", "nl -w 3 x.py", "nl -ba x.py", "sed -f script.sed x.py",
                        "sed --expression='s/a/b/' x.py", "sed -ne 's/a/b/p' x.py", "sed -n -e p x.py",
                        "less x.py", "more x.py"):
            self.assertEqual(profile.shell_reads(command, "/r"), ["/r/x.py"], command)
            self.assertEqual(profile.shell_uses(command), {"read": 1}, command)

    def test_sed_in_place_writes_and_reads_for_nobody(self):
        for command in ("sed -i 's/a/b/' x.py", "sed -ni 's/a/b/p' x.py", "sed -i.bak 's/a/b/' x.py",
                        "sed --in-place 's/a/b/' x.py", "sed --in-place=.bak -e 's/a/b/' x.py"):
            self.assertEqual(profile.shell_reads(command, "/r"), [], command)
            self.assertEqual(profile.shell_uses(command), {"run": 1}, command)

    def test_a_here_document_is_data_not_commands(self):
        command = "python3 - x <<'EOF'\ncat secret\nls\nEOF\ngit status"
        self.assertEqual(profile.shell_reads(command, "/r"), [])
        self.assertEqual(profile.shell_uses(command), {"run": 1, "git": 1})
        self.assertEqual(profile.without_heredocs("cat <<EOF > f\nline\nEOF"), "cat <<EOF > f")
        self.assertEqual(profile.without_heredocs('a <<"X"\nb\nX\nc'), "a <<\"X\"\nc")
        self.assertEqual(profile.without_heredocs("cat <<-EOF\n\tx\n\tEOF\nls"), "cat <<-EOF\nls")
        self.assertEqual(profile.without_heredocs("cat << EOF\nx\nEOF\nls"), "cat << EOF\nls")
        self.assertEqual(profile.shell_uses("cat <<EOF > f\ncat a\nEOF"), {"filter": 1})

    def test_a_command_with_no_here_document_is_not_read_for_one(self):
        """Reading a long command a character at a time for a << it does not
        hold was most of what a long inline script cost a profile."""
        with mock.patch.object(usage, "heredoc_bodies", wraps=usage.heredoc_bodies) as reader:
            self.assertEqual(profile.without_heredocs("python3 -c 'x = 1; y = 2'"), "python3 -c 'x = 1; y = 2'")
            self.assertEqual(reader.call_count, 0)
            self.assertEqual(profile.without_heredocs("cat <<EOF\nx\nEOF"), "cat <<EOF")
            self.assertEqual(reader.call_count, 1)

    def test_a_delimiter_is_looked_for_within_reach(self):
        """Reading the rest of a long line for each << on it took time with
        the square of the line: about 2 seconds for 32,000 of them."""
        line, empty_bodies = "cat <<a " * 2_000 + "x" * 5_000, "\na" * 2_000
        with mock.patch.object(usage, "delimiter_of", wraps=usage.delimiter_of) as reader:
            self.assertEqual(profile.without_heredocs(line + empty_bodies + "\nls"), line + "\nls")
        self.assertEqual(reader.call_count, 2_000)
        self.assertLessEqual(max(len(call.args[0]) for call in reader.call_args_list), usage.DELIMITER_REACH)

    def test_what_only_looks_like_a_here_document_opens_none(self):
        for line in ('cat <<<"bar"', "grep -rn '<<EOF' x", 'python3 -c "x << y"', "cat a", "a <<", "a << ;",
                     "# cat <<EOF", "cat f # comment <<EOF", 'echo "<<" x; cat g', 'grep -rn "<<" tools/'):
            command = line + "\ncat body\nEOF\nls"
            self.assertEqual(profile.without_heredocs(command), command, line)
        self.assertEqual(profile.shell_uses("grep -rn '<<EOF' x\ncat y"), {"search": 1, "read": 1})
        self.assertEqual(profile.shell_reads("# cat <<EOF\ncat real.py\nls", "/r"), ["/r/real.py"])
        self.assertEqual(profile.shell_reads("cat f # comment <<EOF\ncat g", "/r"), ["/r/f", "/r/g"])
        self.assertEqual(profile.shell_reads('echo "<<" x; cat g', "/r"), ["/r/g"])
        for line in ("cat <<-EOF", "cat <<- EOF"):
            self.assertEqual(profile.without_heredocs(line + "\n\tbody\n\tEOF\nls"), line + "\nls", line)
        for line in ("cat <<'EOF'", 'cat <<"EOF" > f', "cat <<\\EOF", "cat <<EOF; echo started", "sort 0<<EOF",
                     "cat << EOF | sort"):
            self.assertEqual(profile.without_heredocs(line + "\nbody\nEOF\nls"), line + "\nls", line)
        # A << the shell reads as no operator: mid-word quotes, arithmetic.
        for line in ('x="a << b" cat f', "echo $((1 << 3))", 'echo "$((1 << 3))"', "(( x <<= 2 ))",
                     'echo "a" \\<< b'):
            command = line + "\nb\n3\n=\nls"
            self.assertEqual(profile.without_heredocs(command), command, line)
        # A commit message written through a here-document inside $( ) in
        # double quotes is one quoted word to the shell: one git command.
        commit = "git commit -m \"$(cat <<'EOF'\nfix: cat secret\nEOF\n)\""
        self.assertEqual(profile.shell_uses(commit), {"git": 1})
        self.assertEqual(profile.shell_reads(commit, "/r"), [])
        # The delimiter closes a here-document only where it stands alone at the
        # line's start; <<- forgives leading tabs.
        self.assertEqual(profile.without_heredocs("cat <<EOF\n  EOF  \nls"), "cat <<EOF")
        self.assertEqual(profile.without_heredocs("cat <<-EOF\n\tEOF\nls"), "cat <<-EOF\nls")

    def test_a_command_is_read_whole_for_its_here_documents(self):
        """Read a line at a time, a << on a line that a string carries on
        from an earlier one opened a here-document, which hid every line
        after it, and one inside $( ) in double quotes opened none, so a "
        in its body ended the string."""
        message = 'git commit -m "Read here-documents\n\nA body after <<EOF is data.\nMore text."\ncat f'
        self.assertEqual(profile.without_heredocs(message), message)
        self.assertEqual(profile.shell_reads(message, "/r"), ["/r/f"])
        quoted = "git commit -m \"$(cat <<'EOF'\nThe 6\" display\nEOF\n)\"\ncat f"
        self.assertEqual(profile.without_heredocs(quoted), "git commit -m \"$(cat <<'EOF'\n)\"\ncat f")
        self.assertEqual(profile.shell_uses(quoted), {"git": 1, "read": 1})
        # Two here-documents on one line: their bodies follow it in order.
        self.assertEqual(profile.without_heredocs("cat <<A <<B\na\nA\nb\nB\nls"), "cat <<A <<B\nls")
        # A line the shell carries on with a backslash opens the bodies at its end.
        self.assertEqual(profile.without_heredocs("cat <<EOF \\\n| sort\nx\nEOF\nls"), "cat <<EOF \\\n| sort\nls")
        # A body the command ends inside runs to its end; a body with no line is empty.
        self.assertEqual(profile.without_heredocs("cat <<EOF\n"), "cat <<EOF")
        self.assertEqual(profile.without_heredocs("cat <<A <<B\nA"), "cat <<A <<B")
        # A $( ) unquoted keeps its quotes apart from the line's, and its ( ) nest.
        nested = "x=$( (cat <<EOF\nit's\nEOF\n) )\ngit status"
        self.assertEqual(profile.without_heredocs(nested), "x=$( (cat <<EOF\n) )\ngit status")
        inner = 'echo "$(printf "%s" "$(cat <<EOF\nit\'s\nEOF\n)")"\ngit status'
        self.assertEqual(profile.without_heredocs(inner), 'echo "$(printf "%s" "$(cat <<EOF\n)")"\ngit status')
        subshell = 'echo "$( (true); cat <<EOF\nit\'s\nEOF\n)"\ngit status'
        self.assertEqual(profile.without_heredocs(subshell), 'echo "$( (true); cat <<EOF\n)"\ngit status')
        # A # inside a word starts no comment.
        self.assertEqual(profile.without_heredocs("echo a#b <<EOF\nbody\nEOF\nls"), "echo a#b <<EOF\nls")
        # Each depth of $( ) reads its own bodies, the inner one's after the
        # newline inside it, the outer one's after the line; a $( ) closed on
        # its line hands its bodies to the line.
        two = 'cat <<A && echo "$(cat <<B\nb\nB\n)"\na\nA\nls'
        self.assertEqual(profile.without_heredocs(two), 'cat <<A && echo "$(cat <<B\n)"\nls')
        self.assertEqual(profile.without_heredocs("x=$(cat <<EOF) && cat f\nbody\nEOF\nls"), "x=$(cat <<EOF) && cat f\nls")
        # Inside $( ), bash 5.2 ends a body at its delimiter and the ) too;
        # outside, that line is the body's.
        self.assertEqual(profile.without_heredocs("x=$(cat <<EOF\nhello\nEOF )\nls"), "x=$(cat <<EOF )\nls")
        self.assertEqual(profile.without_heredocs("cat <<EOF\nhello\nEOF)\nEOF\nls"), "cat <<EOF\nls")
        # The ) that ends the first body ends the $( ), and the second body
        # follows the line, as bash reads it.
        self.assertEqual(profile.without_heredocs("x=$(cat <<A <<B\na\nA)\nb\nB\nls"), "x=$(cat <<A <<B)\nls")
        # The bodies of a $( ) closed on the line that opens them come first,
        # at the very next newline, one a backslash takes out of the line too.
        self.assertEqual(profile.without_heredocs("cat <<X; v=$(cat <<Z)\nz\nZ\nx\nX\nls"), "cat <<X; v=$(cat <<Z)\nls")
        self.assertEqual(profile.without_heredocs("x=$(cat <<A) \\\nl1\nA\nls"), "x=$(cat <<A) \\\nls")

    def test_what_each_command_is_for(self):
        self.assertEqual(profile.shell_uses("cd /r && ls -la | grep x; git log; python3 t.py; wc -l a; echo hi"),
                         {"list": 2, "search": 1, "git": 1, "run": 1})
        self.assertEqual(profile.shell_uses("rg -n def tools/ && find . -name '*.py'"), {"search": 1, "list": 1})
        # A reader naming no file filters another command's output.
        self.assertEqual(profile.shell_uses("ls | head -5"), {"list": 1, "filter": 1})
        self.assertEqual(profile.shell_uses("cat - | sed 's/a/b/'"), {"filter": 2})
        self.assertEqual(profile.shell_uses(""), {})


class AnExecutionFile(ATranscriptOnDisk):
    def test_a_runs_execution_file_is_one_array_with_no_clock(self):
        execution = self.folder / "execution.json"
        execution.write_text(json.dumps(undated(session_entries())), encoding="utf-8")
        self.assertEqual(len(profile.entries_of(execution)), len(session_entries()))
        record, built = profile.profile(execution)
        self.assertEqual(record["calls"]["total"], 4)
        self.assertEqual(record["context"]["calls"], 3)
        self.assertEqual(record["seconds"], dict.fromkeys(profile.SECONDS_KEYS, 0))
        self.assertEqual((record["started_at"], record["ended_at"], record["session"]), (None, None, None))
        self.assertTrue(profile.report(record).startswith("Profile of a run (no clock, 0 helper transcripts"))
        self.assertEqual(record["reads"]["calls"], 3)
        self.assertEqual(built.lines, len(session_entries()))

    def test_an_execution_file_written_over_many_lines_is_read_whole(self):
        """claude-code-action writes the file indented, a key a line, so an
        empty message is a line that is a whole object by itself; read a
        line at a time, it was the file's one entry."""
        execution = self.folder / "execution.json"
        execution.write_text(json.dumps(undated(session_entries()) + [{}], indent=2), encoding="utf-8")
        self.assertEqual(len(profile.entries_of(execution)), len(session_entries()) + 1)
        self.assertEqual(profile.profile(execution)[0]["calls"]["total"], 4)
        broken = self.folder / "broken.json"
        broken.write_text("[\n  {}\n", encoding="utf-8")
        self.assertEqual(profile.entries_of(broken), [{}], "an array cut short is read a line at a time")

    def test_a_helpers_messages_in_an_execution_file_are_the_helpers(self):
        """The Agent SDK writes a helper's messages into the run's own
        array, each naming the tool call that started the helper."""
        execution = self.folder / "execution.json"
        entries = undated(session_entries())
        helper = [dict(entry, parent_tool_use_id="t-agent") for entry in undated(helper_entries())]
        execution.write_text(json.dumps(entries[:6] + helper + entries[6:], indent=2), encoding="utf-8")
        record, built = profile.profile(execution)
        alone, _ = profile.profile(execution, helpers=False)
        self.assertEqual(record["helpers"], {"transcripts": 1, "calls": 1, "seconds_in_tool": 0, "output_tokens": 5})
        self.assertEqual((record["calls"]["total"], alone["calls"]["total"]), (5, 4))
        self.assertEqual(record["context"]["peak"], 2350, "the helper's 9,000 tokens are its own context")
        self.assertEqual(record["context"], alone["context"])
        self.assertEqual(record["reads"]["files_named"], alone["reads"]["files_named"] + 1)
        self.assertEqual(record["reads"]["rereads"], alone["reads"]["rereads"], "the helper's first read is its own")
        self.assertEqual(record["models"]["claude-sonnet-5-5"], [9000, 0, 0, 0, 5])
        self.assertNotIn("claude-sonnet-5-5", alone["models"])
        self.assertEqual(built.lines, len(entries))

    def test_each_shell_command_is_split_once(self):
        """Three readers ask for each shell call's commands, and splitting a
        long command is most of what a profile costs."""
        command = "cat split-once.py && ls -la split-once"
        profile.commands_of.cache_clear()
        with mock.patch.object(profile.guard, "simple_commands", wraps=profile.guard.simple_commands) as split:
            record, _ = self.profiled([*assistant("m1", used(1, 0, 0, 1), [tool_use("t1", "Bash", command=command)], 0),
                                       result("t1", "x", 1)])
        self.assertEqual(split.call_count, 1)
        self.assertEqual((record["reads"]["files_named"], record["shell"]["read"], record["shell"]["list"]), (1, 1, 1))

    def test_a_byte_that_is_not_utf8_is_read_past(self):
        execution = self.folder / "execution.json"
        execution.write_bytes(b'[{"type": "user", "text": "cut \xe2\x80"}]')
        self.assertEqual(profile.entries_of(execution), [{"type": "user", "text": "cut \ufffd"}])
        transcript = self.folder / "cut.jsonl"
        transcript.write_bytes(b'{"type": "user", "text": "cut \xe2\x80\n{"type": "user"}\n')
        self.assertEqual(profile.entries_of(transcript), [{"type": "user"}])

    def test_a_file_with_no_entries_is_no_transcript(self):
        empty = self.folder / "empty.jsonl"
        empty.write_text("", encoding="utf-8")
        half = self.folder / "half.jsonl"
        half.write_text("half a line\n", encoding="utf-8")
        self.assertEqual(profile.entries_of(empty), [])
        self.assertEqual(profile.entries_of(half), [])
        for path in (empty, half):
            with redirect_stderr(io.StringIO()) as said:
                self.assertEqual(profile.main([str(path)]), 2)
            self.assertIn("no entries", said.getvalue())


class TheCommandLine(ATranscriptOnDisk):
    def setUp(self):
        super().setUp()
        write_lines(self.transcript, session_entries())

    def test_prints_the_report_and_writes_the_record(self):
        out = self.folder / "out" / "profile.json"
        printed = io.StringIO()
        with redirect_stdout(printed):
            code = profile.main([str(self.transcript), "--json", str(out), "--paths", "2"])
        self.assertEqual(code, 0)
        self.assertIn("Profile of session abcdef12", printed.getvalue())
        self.assertIn("Files read most often (not in the record):", printed.getvalue())
        self.assertIn("    2  /work/repo/a.py", printed.getvalue())
        record = json.loads(out.read_text(encoding="ascii"))
        self.assertEqual(record["calls"]["total"], 4)
        self.assertNotIn("a.py", out.read_text())

    def test_a_missing_transcript_is_said(self):
        with redirect_stderr(io.StringIO()) as said:
            self.assertEqual(profile.main([str(self.folder / "none.jsonl")]), 2)
        self.assertIn("no transcript", said.getvalue())


if __name__ == "__main__":
    unittest.main()
