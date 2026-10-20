"""tools/metrics.py writes aggregates and nothing else: off means no call
at all, every key is the spec's, no name, title, branch or text from the
repository reaches the output, and the judge keeps counts only, never runs
with an API key and, in a dry run, sends nothing. The work-setting
breakdown is run over a two-person world and over two real histories,
anonymised, so each rule is held to numbers measured outside this code; no
login, session link or file name of theirs reaches the file. The workflow's
write step is run here against local git repositories, so the lease that
keeps a judge push is tested as it runs, not read, and a socket on this
machine answers the usage records' downloads cut short, so the run meets
what http.client itself raises."""

import http.client
import io
import json
import os
import re
import shlex
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from functools import partial
from itertools import permutations
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import guard_push  # noqa: E402
import metrics  # noqa: E402

# A repository made from the template turns sharing off by writing off into
# the switch file, and its tests must pass then: what the shipped file says
# is checked in the template alone, where .template/ still is, as
# tests/test_crowd.py does.
IN_TEMPLATE = (ROOT / ".template" / "PENDING").is_file()
template_only = unittest.skipUnless(IN_TEMPLATE, "reads the template's own switch file, which a copy may have turned off")

WORKFLOW = ROOT / ".github" / "workflows" / "metrics.yml"
REPO = "octo/widgets"
API = f"/repos/{REPO}"
NOW = "2026-10-10T12:00:00Z"
GIT_ENV = {"GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.invalid", "GIT_COMMITTER_NAME": "Test",
           "GIT_COMMITTER_EMAIL": "test@example.invalid", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}

# Every string below is something of the repository's own that must never
# reach METRICS.json or JUDGE.json.
PRIVATE = ("Secret plan for widgets", "Fix the login page", "mona-secret", "lisa-secret", "octo-reviewer",
           "agent@example.invalid", "claude/4711", "claude/4712", "claude/4713", "claude/4714",
           "feature/login-page", "the body says secret things", "secret text in a comment", REPO,
           "src/secret_module.py", "Sounds good", "secret words of the judge", "session_01MonaSecretSession")
NUMBERS = (99, 101, 102, 103, 104, 4711, 4712, 4713, 4714, 4715, 4716)
# OpenSpineConsortium's collector (symphony-app, its collect script's VERSION)
# keeps protocol_version only when the whole value is a release, alone or
# followed by a space and 7 to 40 hex digits of the commit.
COLLECTOR_VERSION = re.compile(r"[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}( [0-9a-f]{7,40})?")
# An epoch second, as GitHub's X-RateLimit-Reset header is.
RESET = 1791637200
# OpenSpineConsortium's collector (symphony-app, its collect workflow) reads the
# branch metrics at 04:17 UTC, so the day's record must be there by then.
COLLECTOR_READ = 4 * 60 + 17


def user(login, kind="User"):
    return {"login": login, "type": kind}


def base(ref="main"):
    """A pull request's base as /pulls lists it, in a repository whose
    default branch is main."""
    return {"ref": ref, "repo": {"default_branch": "main"}}


def commit(sha, authored, committed=None, login=None, email=None):
    return {"sha": sha, "author": user(login, "Bot" if login and login.endswith("[bot]") else "User") if login else None,
            "commit": {"author": {"name": "someone", "email": email or f"{login}@example.invalid", "date": authored},
                       "committer": {"date": committed or authored}}}


def pull(number, ref, author, created, updated, head, state="closed", merged=None, closed=None, kind="User"):
    return {"number": number, "title": "Secret plan for widgets" if number != 104 else "Fix the login page",
            "body": "the body says secret things", "state": state, "created_at": created, "updated_at": updated,
            "merged_at": merged, "closed_at": closed or merged, "user": user(author, kind),
            "head": {"ref": ref, "sha": head}, "base": base()}


def review(login, state, submitted):
    return {"user": user(login), "state": state, "submitted_at": submitted, "body": "secret text in a comment"}


def run(number, conclusion, completed, name="check"):
    return {"id": number, "name": name, "status": "completed", "conclusion": conclusion, "completed_at": completed}


def runs(*items):
    return {"total_count": len(items), "check_runs": list(items)}


def comment(issue, created, body, association="COLLABORATOR"):
    return {"issue_url": f"https://api.github.com{API}/issues/{issue}", "created_at": created, "body": body,
            "user": user("lisa-secret"), "author_association": association}


SHA = {name: name * 40 for name in "abcdef9"}
BEHIND = metrics.board.MAIN_MOVED_MARKER.format(sha="abc1234") + "\n" + \
    metrics.board.main_moved_text("behind", "main", "abc1234")
CONFLICTING = metrics.board.MAIN_MOVED_MARKER.format(sha="abc1234") + "\n" + \
    metrics.board.main_moved_text("conflicting", "main", "abc1234")

# A window from 2026-09-10 12:00 to 2026-10-10 12:00. Pull request 101 is
# merged, 102 closed unmerged, 103 open, a draft in conflict, 104 open, old
# and a bot's, 99 changed before the window, where the listing stops. 101's
# check failed on a and passed when run again, failed on b, its first head,
# and passed on c, the head it merged with.
PULLS = [
    pull(103, "claude/4713", "lisa-secret", "2026-10-05T00:00:00Z", "2026-10-09T00:00:00Z", SHA["f"], state="open"),
    pull(102, "claude/4712", "mona-secret", "2026-10-03T00:00:00Z", "2026-10-04T00:00:00Z", SHA["d"],
         closed="2026-10-04T00:00:00Z"),
    pull(101, "claude/4711", "mona-secret", "2026-10-01T10:00:00Z", "2026-10-02T10:00:00Z", SHA["c"],
         merged="2026-10-02T10:00:00Z"),
    pull(104, "feature/login-page", "dependabot[bot]", "2026-08-01T00:00:00Z", "2026-09-20T00:00:00Z", SHA["9"],
         state="open", kind="Bot"),
    pull(99, "claude/4710", "mona-secret", "2026-08-01T00:00:00Z", "2026-09-01T00:00:00Z", "0" * 40),
]
ROUTES = {
    f"{API}/pulls": PULLS,
    f"{API}/pulls/101/commits": [commit(SHA["a"], "2026-10-01T09:00:00Z", login="mona-secret"),
                                 commit(SHA["b"], "2026-10-01T09:30:00Z", login="mona-secret"),
                                 commit(SHA["c"], "2026-10-01T15:00:00Z", login="mona-secret")],
    f"{API}/pulls/101/reviews": [review("octo-reviewer", "CHANGES_REQUESTED", "2026-10-01T12:00:00Z"),
                                 review("octo-reviewer", "APPROVED", "2026-10-02T09:00:00Z"),
                                 review("octo-reviewer", "PENDING", None)],
    f"{API}/commits/{SHA['c']}/check-runs": runs(run(1, "success", "2026-10-01T15:05:00Z"),
                                                 run(2, "success", "2026-10-01T15:02:00Z", "board")),
    f"{API}/commits/{SHA['b']}/check-runs": runs(run(3, "failure", "2026-10-01T10:05:00Z")),
    f"{API}/commits/{SHA['a']}/check-runs": runs(run(10, "failure", "2026-10-01T09:05:00Z"),
                                                 run(11, "success", "2026-10-01T09:40:00Z")),
    f"{API}/pulls/102/commits": [commit(SHA["d"], "2026-10-02T22:00:00Z", email="agent@example.invalid")],
    f"{API}/pulls/102/reviews": [review("mona-secret", "COMMENTED", "2026-10-03T01:00:00Z")],
    f"{API}/commits/{SHA['d']}/check-runs": runs(run(4, "success", "2026-10-03T00:05:00Z")),
    f"{API}/pulls/103": {"number": 103, "mergeable": False, "mergeable_state": "dirty"},
    f"{API}/pulls/103/commits": [commit(SHA["e"], "2026-10-04T21:00:00Z", login="lisa-secret"),
                                 commit(SHA["f"], "2026-10-06T00:00:00Z", login="lisa-secret")],
    f"{API}/pulls/103/reviews": [],
    f"{API}/commits/{SHA['e']}/check-runs": runs(run(5, "success", "2026-10-05T00:05:00Z"),
                                                 run(6, "timed_out", "2026-10-05T00:20:00Z", "lint")),
    f"{API}/commits/{SHA['f']}/check-runs": runs(run(7, "timed_out", "2026-10-06T00:10:00Z"),
                                                 run(9, "cancelled", "2026-10-06T00:11:00Z", "lint")),
    f"{API}/pulls/104": {"number": 104, "mergeable": True, "mergeable_state": "clean"},
    f"{API}/pulls/104/commits": [commit(SHA["9"], "2026-08-01T00:00:00Z", login="dependabot[bot]")],
    f"{API}/pulls/104/reviews": [review("octo-reviewer", "APPROVED", "2026-09-20T00:00:00Z")],
    f"{API}/branches": [{"name": n, "commit": {"sha": s}} for n, s in (
        ("main", "5" * 40), ("board", "6" * 40), ("metrics", "7" * 40), ("claude/4711", SHA["c"]),
        ("claude/4713", SHA["f"]), ("claude/4714", "1" * 40), ("claude/4715", "2" * 40), ("claude/notes", "3" * 40))],
    f"{API}/commits/{'1' * 40}": commit("1" * 40, "2026-10-08T00:00:00Z", login="lisa-secret"),
    f"{API}/commits/{'2' * 40}": commit("2" * 40, "2026-08-01T00:00:00Z", login="lisa-secret"),
    f"{API}/issues/comments": [
        comment(4716, "2026-10-07T00:00:00Z", metrics.RELEASE_MARKER + "\nReleased: no commit for a day."),
        comment(4716, "2026-09-01T00:00:00Z", metrics.RELEASE_MARKER + "\nAn old release, edited lately."),
        comment(101, "2026-10-01T20:00:00Z", BEHIND),
        comment(104, "2026-09-25T00:00:00Z", CONFLICTING),
        comment(102, "2026-10-03T02:00:00Z", "secret text in a comment"),
    ],
}


def zeros(keys):
    return dict.fromkeys(keys, 0)


def settings_with(**rows):
    """by_setting with every setting at zero but the rows given."""
    return {name: rows.get(name, zeros(metrics.SETTING_KEYS)) for name in metrics.SETTINGS}


def breakdown_values(record):
    """Every value of a record's parallel, by_setting and pairs."""
    yield from record["parallel"].values()
    for block in ("by_setting", "pairs"):
        for row in record[block].values():
            yield from row.values()


# The breakdown, for these pull requests: 101 works from 09:00 on Oct 1 to
# 10:00 on Oct 2 (90000 s) and 102 from 22:00 on Oct 2 to 00:00 on Oct 4
# (93600 s), and nothing overlaps, so both are solo, and 103, open, too;
# the board-shaped comments are posted by lisa-secret, a person, so none is
# a mark; 99 is closed with no dates and is no unit; 104, a bot's, is open
# but neither opened nor given a commit in the window, only reviewed, so it
# is stale and no unit either.
EXPECTED = {
    "counts": {"claims": 4, "pull_requests_opened": 3, "merged": 1, "closed_unmerged": 1, "reviews": 3,
               "changes_requested": 1, "check_runs_passed": 5, "check_runs_failed": 4, "conflicts_seen": 2,
               "released_claims": 1, "contributors": 4},
    "durations_seconds": {"claim_to_first_pull_request_median": 7200, "claim_to_first_pull_request_p90": 10800,
                          "open_to_merge_median": 86400, "open_to_merge_p90": 86400,
                          "first_review_median": 7200, "first_review_p90": 7200},
    "rates": {"merge_rate": 0.5, "first_check_pass_rate": 0.3333},
    "parallel": {"people": 2, "sessions": 0, "sessions_per_person_max": 0, "pull_requests_with_session": 0,
                 "pull_requests_without_session": 3, "pull_requests_multi_session": 0, "sessions_across_people": 0,
                 "peak_parallel": 1, "peak_parallel_people": 1, "peak_sessions_one_person": 0, "conflict_marks": 0,
                 "conflict_marks_unattributed": 0, "open_conflicting": 1, "open_conflicting_drafts": 0,
                 "open_conflicting_dirty": 1, "truncated": 0, "files_unread": 0},
    "by_setting": settings_with(
        solo={"pull_requests": 2, "merged": 1, "closed_unmerged": 1, "open": 1, "conflicted": 0, "released": 0,
              "changes_requested": 1, "claim_branches": 2, "partners": 0, "work_seconds": 183600,
              "landings_under": 0, "landings_before_opening": 0, "file_overlap": 0}),
    "pairs": {name: zeros(metrics.PAIR_KEYS) for name in metrics.RELATIONS},
}


class Answer:
    def __init__(self, body, headers=None):
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.body, self.status, self.headers = raw, 200, headers or {}

    def read(self, size=-1):
        return self.body if size < 0 else self.body[:size]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class Redirect:
    """A route GitHub answers with a redirect to target, as it answers an
    artifact's download."""

    def __init__(self, target):
        self.target = target


class FakeGitHub:
    """Stands in for urllib's opener: answers by path, one page each, and
    a 404 for any path it has no answer for, so a call the code should not
    make fails the test that made it. Given a number of requests left, it
    counts them down in the rate-limit headers as GitHub does, on its own
    API's answers only. It keeps each request's host and headers too."""

    def __init__(self, routes, remaining=None):
        self.routes, self.calls, self.queries, self.remaining = routes, [], [], remaining
        self.sent = []

    def open(self, request, timeout=None):
        parts = urllib.parse.urlsplit(request.full_url)
        self.calls.append(parts.path)
        self.queries.append(dict(urllib.parse.parse_qsl(parts.query)))
        self.sent.append((parts.netloc, {name.lower(): value for name, value in request.header_items()}))
        headers = {}
        if self.remaining is not None and parts.netloc == "api.github.com":
            self.remaining -= 1
            headers = {"X-RateLimit-Remaining": str(self.remaining), "X-RateLimit-Reset": str(RESET)}
        if parts.path not in self.routes:
            raise urllib.error.HTTPError(request.full_url, 404, "Not Found", headers, io.BytesIO(b"{}"))
        answer = self.routes[parts.path]
        if isinstance(answer, Redirect):
            raise urllib.error.HTTPError(request.full_url, 302, "Found", {**headers, "Location": answer.target},
                                         io.BytesIO(b""))
        return Answer(answer, headers)


class SpentHour:
    """An opener whose every answer is GitHub's refusal of a spent hour."""

    def open(self, request, timeout=None):
        body = io.BytesIO(b'{"message": "API rate limit exceeded for installation ID 1."}')
        raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {"X-RateLimit-Remaining": "0"}, body)


class NoCalls:
    def open(self, request, timeout=None):
        raise AssertionError(f"an API call was made: {request.full_url}")


# What a socket on this machine answers in the tests of an answer cut
# short or garbled: a refusal whose body stops before the length it gave, a
# download sent in chunks that stops inside its first, one that stops
# before the length it gave, and an answer that is not HTTP at all.
REFUSAL_CUT_SHORT = (b"HTTP/1.1 502 Bad Gateway\r\nContent-Type: application/json\r\nContent-Length: 96\r\n\r\n"
                     b'{"message": "Server Err')
CHUNKS_CUT_SHORT = (b"HTTP/1.1 200 OK\r\nContent-Type: application/zip\r\nTransfer-Encoding: chunked\r\n\r\n"
                    b"400\r\nPK\x03\x04")
LENGTH_CUT_SHORT = b"HTTP/1.1 200 OK\r\nContent-Type: application/zip\r\nContent-Length: 600\r\n\r\nPK\x03\x04"
NOT_HTTP = b"SSH-2.0-OpenSSH_9.6\r\n"
NOT_FOUND = b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n"


class RawSocket:
    """A socket on this machine that answers each request with the bytes
    given for its path and then closes the connection, whatever the bytes
    say. Its opener sends https requests there in plain HTTP, so urllib and
    http.client read those bytes as they read GitHub's, and an answer cut
    short or garbled raises what it raises in a real run."""

    def __init__(self, answers):
        self.answers, self.asked = answers, []
        self.listener = socket.create_server(("127.0.0.1", 0))
        self.listener.settimeout(0.05)
        self.closing = threading.Event()
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.closing.set()
        self.thread.join(10)
        self.listener.close()
        return False

    def serve(self):
        while not self.closing.is_set():
            try:
                connection, _ = self.listener.accept()
            except TimeoutError:
                continue
            with connection:
                try:
                    self.answer(connection)
                except OSError:
                    pass

    def answer(self, connection):
        """The bytes for the path the request names, then the end of the
        answer; what the other side sends after that is read and dropped
        for a moment, so the close is not a reset that could overtake the
        bytes, and a client that keeps the connection open holds up the
        next request no longer than that."""
        connection.settimeout(10)
        asked = b""
        while b"\r\n\r\n" not in asked and (chunk := connection.recv(65536)):
            asked += chunk
        words = asked.split(b" ", 2)
        path = urllib.parse.urlsplit(words[1].decode("ascii")).path if len(words) == 3 else ""
        self.asked.append(path)
        connection.sendall(self.answers.get(path, NOT_FOUND))
        connection.shutdown(socket.SHUT_WR)
        connection.settimeout(1)
        while connection.recv(65536):
            pass

    def opener(self, follow=False):
        """urllib's opener as the run builds it, but with https sent here,
        and with no proxy, which the environment may name for every host:
        the one Budgeted asks GitHub where a download is with, which
        follows no redirect, or with follow the library's own, which
        follows each one wherever it says."""
        port = self.listener.getsockname()[1]

        class HereInPlainHTTP(urllib.request.HTTPSHandler):
            def https_open(self, request):
                return self.do_open(lambda host, **options: http.client.HTTPConnection("127.0.0.1", port, **options),
                                    request)

        redirects = () if follow else (metrics.Unfollowed,)
        return urllib.request.build_opener(urllib.request.ProxyHandler({}), *redirects, HereInPlainHTTP)


class PartlyOverASocket(FakeGitHub):
    """The world's GitHub, but for the paths a RawSocket answers, whose
    requests go to that socket through urllib and http.client."""

    def __init__(self, routes, raw):
        super().__init__(routes)
        self.raw, self.real = raw, raw.opener()

    def open(self, request, timeout=None):
        path = urllib.parse.urlsplit(request.full_url).path
        if path not in self.raw.answers:
            return super().open(request, timeout)
        self.calls.append(path)
        return self.real.open(request, timeout=timeout)


def collect(folder, environ, opener, extra=()):
    out = Path(folder) / "METRICS.json"
    args = metrics.parse_args(["collect", "--repo", REPO, "--out", str(out), "--root", str(folder), "--now", NOW,
                               *extra])
    with redirect_stdout(io.StringIO()):
        code = metrics.collect(args, environ, opener=opener, sleep=lambda seconds: None)
    return code, json.loads(out.read_text()), out.read_text()


def switch(folder, text, name="symphony-metrics"):
    path = Path(folder) / ".github" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class Switch(unittest.TestCase):
    def test_off_in_the_file_writes_off_alone_and_calls_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            switch(folder, "off\n\nwhy it is off\n")
            code, record, text = collect(folder, {"GITHUB_TOKEN": "t"}, NoCalls())
        self.assertEqual(code, 0)
        self.assertEqual(record, {"schema": "sdlc-metrics/1", "sharing": "off"})
        self.assertEqual(list(record), ["schema", "sharing"])

    def test_the_switch_under_its_old_name_still_counts_and_off_in_either_wins(self):
        """A repository set up before the rename carries .github/sdlc-metrics,
        and one adopted again since may carry both files: an off in either is
        the owner's word, which an on in the other never lifts, so the run
        writes off and calls nothing; only both saying on, or one saying on
        with the other missing, shares."""
        with tempfile.TemporaryDirectory() as folder:
            switch(folder, "off\n", name="sdlc-metrics")
            code, record, _ = collect(folder, {"GITHUB_TOKEN": "t"}, NoCalls())
        self.assertEqual((code, record["sharing"]), (0, "off"))
        with tempfile.TemporaryDirectory() as folder:
            switch(folder, "off\n", name="sdlc-metrics")
            switch(folder, "on\n")
            self.assertEqual(metrics.sharing(folder, {}), metrics.OFF)
            code, record, _ = collect(folder, {"GITHUB_TOKEN": "t"}, NoCalls())
        self.assertEqual((code, record), (0, metrics.OFF_RECORD))
        for new, old, said in (("off\n", "on\n", metrics.OFF), ("on\n", "maybe\n", metrics.OFF),
                               ("on\n", "on\n", metrics.ON), (None, "on\n", metrics.ON)):
            with self.subTest(new=new, old=old), tempfile.TemporaryDirectory() as folder:
                if new is not None:
                    switch(folder, new)
                switch(folder, old, name="sdlc-metrics")
                self.assertEqual(metrics.sharing(folder, {}), said)

    def test_off_in_the_variable_wins_over_on_in_the_file_and_needs_no_token(self):
        with tempfile.TemporaryDirectory() as folder:
            switch(folder, "on\n")
            code, record, _ = collect(folder, {metrics.SWITCH_VARIABLE: "off"}, NoCalls())
        self.assertEqual((code, record), (0, metrics.OFF_RECORD))

    def test_each_doubt_falls_to_off(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(metrics.sharing(folder, {}), "on")
            self.assertEqual(metrics.sharing(folder, {metrics.SWITCH_VARIABLE: ""}), "on")
            self.assertEqual(metrics.sharing(folder, {metrics.SWITCH_VARIABLE: " On "}), "on")
            for said in ("off", "OFF", "false", "no"):
                self.assertEqual(metrics.sharing(folder, {metrics.SWITCH_VARIABLE: said}), "off", said)
            for text in ("", "maybe\n", "offline\n", "  OFF  \n"):
                switch(folder, text)
                self.assertEqual(metrics.sharing(folder, {}), "off", text)
            switch(folder, "ON\nthe rest is prose\n")
            self.assertEqual(metrics.sharing(folder, {}), "on")
            self.assertEqual(metrics.sharing(folder, {metrics.SWITCH_VARIABLE: "on"}), "on")

    @template_only
    def test_the_template_ships_the_switch_on(self):
        self.assertEqual(metrics.first_word((ROOT / metrics.SWITCH_FILE).read_text(encoding="utf-8")), "on")


class Collect(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.opener = FakeGitHub(ROUTES)
        with tempfile.TemporaryDirectory() as folder:
            cls.code, cls.record, cls.text = collect(folder, {"GITHUB_TOKEN": "t"}, cls.opener)

    def test_the_window_measures_what_it_holds(self):
        self.assertEqual(self.code, 0)
        for section, values in EXPECTED.items():
            self.assertEqual(self.record[section], values, section)
        self.assertEqual(self.record["generated_at"], NOW)
        self.assertEqual(self.record["window_days"], 30)
        self.assertEqual(self.record["sharing"], "on")
        self.assertEqual(self.record["protocol_version"], metrics.protocol_version())
        self.assertRegex(self.record["protocol_version"], r"^\d+\.\d+\.\d+ [0-9a-f]{7}$")

    def test_the_listing_stops_at_the_first_pull_request_older_than_the_look_back(self):
        # 99 was changed before the window, in the look-back, and is closed
        # with no dates, so it is listed and costs nothing.
        self.assertFalse([path for path in self.opener.calls if "/pulls/99" in path])
        self.assertEqual(self.opener.calls.count(f"{API}/pulls"), 1)

    def test_every_key_is_the_specs_and_every_value_its_type(self):
        self.assertEqual(tuple(self.record), metrics.RECORD_KEYS)
        self.assertEqual(tuple(self.record["counts"]), metrics.COUNT_KEYS)
        self.assertEqual(tuple(self.record["durations_seconds"]), metrics.DURATION_KEYS)
        self.assertEqual(tuple(self.record["rates"]), metrics.RATE_KEYS)
        self.assertEqual(tuple(self.record["parallel"]), metrics.PARALLEL_KEYS)
        self.assertEqual(tuple(self.record["by_setting"]), metrics.SETTINGS)
        for row in self.record["by_setting"].values():
            self.assertEqual(tuple(row), metrics.SETTING_KEYS)
        self.assertEqual(tuple(self.record["pairs"]), metrics.RELATIONS)
        for row in self.record["pairs"].values():
            self.assertEqual(tuple(row), metrics.PAIR_KEYS)
        for value in self.record["counts"].values():
            self.assertIs(type(value), int)
        for value in self.record["durations_seconds"].values():
            self.assertIn(type(value), (int, type(None)))
        for value in self.record["rates"].values():
            self.assertIn(type(value), (float, type(None)))
        for value in breakdown_values(self.record):
            self.assertIs(type(value), int)

    def test_nothing_of_the_repository_reaches_the_file(self):
        for secret in PRIVATE:
            self.assertNotIn(secret, self.text, secret)
        numbers = [v for section in ("counts", "durations_seconds") for v in self.record[section].values()]
        numbers += list(breakdown_values(self.record))
        for number in NUMBERS:
            self.assertNotIn(number, numbers)
        strings = [v for v in self.record.values() if isinstance(v, str)]
        self.assertEqual(len(strings), 4)

    def test_an_empty_window_gives_zeros_and_nulls(self):
        routes = {f"{API}/pulls": [], f"{API}/branches": [], f"{API}/issues/comments": []}
        with tempfile.TemporaryDirectory() as folder:
            _, record, _ = collect(folder, {"GITHUB_TOKEN": "t"}, FakeGitHub(routes))
        self.assertEqual(set(record["counts"].values()), {0})
        self.assertEqual(set(record["durations_seconds"].values()), {None})
        self.assertEqual(record["rates"], {"merge_rate": None, "first_check_pass_rate": None})
        self.assertEqual(set(breakdown_values(record)), {0})

    def test_on_without_a_token_fails_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, {}, clear=True):
            out = Path(folder) / "METRICS.json"
            with redirect_stderr(io.StringIO()) as said:
                with mock.patch.object(metrics, "collect", partial(metrics.collect, opener=NoCalls())):
                    code = metrics.main(["collect", "--repo", REPO, "--out", str(out), "--root", folder])
            self.assertEqual(code, 1)
            self.assertIn("no token", said.getvalue())
            self.assertFalse(out.exists())

    def test_check_runs_are_read_on_every_commit_made_in_the_window_every_attempt_of_each(self):
        asked = [(path, query) for path, query in zip(self.opener.calls, self.opener.queries)
                 if path.endswith("/check-runs")]
        # One call per commit made in the window, the first heads b and d
        # among them once; none for 104's head, made before the window.
        self.assertEqual(sorted(path for path, _ in asked),
                         sorted(f"{API}/commits/{SHA[name]}/check-runs" for name in "abcdef"))
        self.assertEqual({query.get("filter") for _, query in asked}, {"all"})
        # a's failure and its re-run both count, and so does b's failure,
        # which the push of c fixed before the merge.
        self.assertEqual((self.record["counts"]["check_runs_passed"], self.record["counts"]["check_runs_failed"]),
                         (5, 4))

    def test_a_commit_in_two_pull_requests_brings_its_runs_once(self):
        window = metrics.Window.ending(metrics.parse_time(NOW), 30)
        shared = run(1, "failure", "2026-10-01T10:05:00Z")
        facts = [metrics.PullFacts(PULLS[2], runs={SHA["b"]: [shared]}),
                 metrics.PullFacts(PULLS[0], runs={SHA["b"]: [dict(shared)]})]
        self.assertEqual(len(metrics.window_runs(facts, window)), 1)

    def test_a_first_head_made_before_the_window_costs_one_more_call(self):
        old, new = "3" * 40, "4" * 40
        routes = {
            f"{API}/pulls": [pull(105, "claude/4716", "lisa-secret", "2026-10-07T00:00:00Z", "2026-10-08T00:00:00Z",
                                  new, merged="2026-10-08T00:00:00Z")],
            f"{API}/pulls/105/commits": [commit(old, "2026-09-01T00:00:00Z", login="lisa-secret"),
                                         commit(new, "2026-10-07T01:00:00Z", login="lisa-secret")],
            f"{API}/pulls/105/reviews": [],
            f"{API}/commits/{old}/check-runs": runs(run(1, "success", "2026-09-01T00:05:00Z")),
            f"{API}/commits/{new}/check-runs": runs(run(2, "failure", "2026-10-07T01:05:00Z")),
            f"{API}/branches": [], f"{API}/issues/comments": [],
        }
        opener = FakeGitHub(routes)
        with tempfile.TemporaryDirectory() as folder:
            _, record, _ = collect(folder, {"GITHUB_TOKEN": "t"}, opener)
        self.assertEqual([path for path in opener.calls if path.endswith("/check-runs")],
                         [f"{API}/commits/{new}/check-runs", f"{API}/commits/{old}/check-runs"])
        self.assertEqual((record["counts"]["check_runs_passed"], record["counts"]["check_runs_failed"]), (0, 1))
        self.assertEqual(record["rates"]["first_check_pass_rate"], 1.0)

    def test_contributors_are_dated_by_their_own_acts_not_the_pull_requests(self):
        # An open pull request from June, bumped into the window by a board
        # comment: its author, its reviewer and its committer did nothing
        # in the window.
        stale = pull(106, "claude/4717", "alice-secret", "2026-06-01T00:00:00Z", "2026-10-09T00:00:00Z", "4" * 40,
                     state="open")
        routes = {
            f"{API}/pulls": [stale],
            f"{API}/pulls/106": {"number": 106, "mergeable": True, "mergeable_state": "clean"},
            f"{API}/pulls/106/commits": [commit("3" * 40, "2026-06-01T00:00:00Z", login="dave-secret")],
            f"{API}/pulls/106/reviews": [review("carol-secret", "APPROVED", "2026-06-02T00:00:00Z")],
            f"{API}/branches": [], f"{API}/issues/comments": [comment(106, "2026-10-09T00:00:00Z", BEHIND)],
        }
        with tempfile.TemporaryDirectory() as folder:
            _, record, _ = collect(folder, {"GITHUB_TOKEN": "t"}, FakeGitHub(routes))
        self.assertEqual((record["counts"]["contributors"], record["counts"]["reviews"]), (0, 0))
        # A review in the window and a June commit rebased in it count
        # their two people; the author of June still does not.
        routes[f"{API}/pulls/106/reviews"].append(review("carol-secret", "COMMENTED", "2026-10-09T00:00:00Z"))
        routes[f"{API}/pulls/106/commits"].append(
            commit("4" * 40, "2026-06-01T00:00:00Z", "2026-10-08T00:00:00Z", login="dave-secret"))
        routes[f"{API}/commits/{'4' * 40}/check-runs"] = runs()
        with tempfile.TemporaryDirectory() as folder:
            _, record, _ = collect(folder, {"GITHUB_TOKEN": "t"}, FakeGitHub(routes))
        self.assertEqual((record["counts"]["contributors"], record["counts"]["reviews"]), (2, 1))

    def test_it_stops_short_of_the_boards_reserve_and_writes_nothing(self):
        opener, environ = FakeGitHub(ROUTES, remaining=metrics.RESERVE + 5), {"GITHUB_TOKEN": "t"}
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, environ, clear=True):
            out = Path(folder) / "METRICS.json"
            with redirect_stderr(io.StringIO()) as said, redirect_stdout(io.StringIO()):
                with mock.patch.object(metrics, "collect", partial(metrics.collect, opener=opener)):
                    code = metrics.main(["collect", "--repo", REPO, "--out", str(out), "--root", folder,
                                         "--now", NOW])
            self.assertEqual(code, 1)
            self.assertFalse(out.exists())
        self.assertEqual(len(opener.calls), 5)
        self.assertIn(f"metrics: stopped after 5 calls, with {metrics.RESERVE} of GITHUB_TOKEN's 1,000 requests an "
                      "hour left for the board, whose reserve is 300: nothing is written, and the branch metrics "
                      "keeps its last record.", said.getvalue())
        self.assertIn(f"comes back at {metrics.iso(datetime.fromtimestamp(RESET, timezone.utc))}", said.getvalue())

    def test_githubs_refusal_of_a_spent_hour_is_told_the_same_way(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "METRICS.json"
            args = metrics.parse_args(["collect", "--repo", REPO, "--out", str(out), "--root", folder, "--now", NOW])
            with self.assertRaises(metrics.OutOfBudget) as caught:
                metrics.collect(args, {"GITHUB_TOKEN": "t"}, opener=SpentHour(), sleep=lambda seconds: None)
            self.assertFalse(out.exists())
        # GitHub answered the call it refused, so it is one of the hour's.
        self.assertIn("GitHub refused the call (API rate limit exceeded for installation ID 1.); stopped after "
                      "1 calls, with 0 of GITHUB_TOKEN's", str(caught.exception))
        self.assertIn("comes back within the hour", str(caught.exception))

    def test_a_try_made_again_after_a_rate_limit_counts_as_a_call(self):
        """The first rate-limit review's sixth finding: Budgeted counted its
        own requests, one for a call the client made twice after GitHub's
        wait; the count is now the client's, every answer counted."""
        class LimitedOnce:
            def __init__(self):
                self.opened = 0

            def open(self, request, timeout=None):
                self.opened += 1
                if self.opened == 1:
                    body = io.BytesIO(b'{"message": "You have exceeded a secondary rate limit."}')
                    raise urllib.error.HTTPError(request.full_url, 429, "Too Many Requests",
                                                 {"Retry-After": "1"}, body)
                return Answer(b"[]", {"X-RateLimit-Remaining": "900"})
        opener = LimitedOnce()
        api = metrics.Budgeted("t", REPO, opener=opener, sleep=lambda seconds: None)
        self.assertEqual(api.get(f"/repos/{REPO}/labels"), [])
        self.assertEqual((opener.opened, api.calls), (2, 2))

    def test_a_run_that_fits_says_how_many_calls_it_took(self):
        opener = FakeGitHub(ROUTES, remaining=1000)
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "METRICS.json"
            args = metrics.parse_args(["collect", "--repo", REPO, "--out", str(out), "--root", folder, "--now", NOW])
            with redirect_stdout(io.StringIO()) as shown:
                code = metrics.collect(args, {"GITHUB_TOKEN": "t"}, opener=opener, sleep=lambda seconds: None)
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(out.read_text())["counts"], EXPECTED["counts"])
        self.assertIn(f"written over 30 days, in {len(opener.calls)} calls", shown.getvalue())
        # The listing, then 103 (commits, reviews, two commits' runs, the
        # detail), 102 (three), 101 (five), 104 (commits, reviews, the
        # detail), the branches with two claim commits, and the comments.
        # The breakdown adds nothing here: nothing was at work beside
        # anything, so no changed files are read, and 99, in the look-back,
        # is no unit, so its commits are not read either. Last, the listing
        # of the Actions runs' usage records, which this fake answers 404.
        self.assertEqual(len(opener.calls), 1 + 5 + 3 + 5 + 3 + 3 + 1 + 1)

    def test_a_parked_pull_request_is_beside_nobody_until_its_own_work_comes_back(self):
        """Under the template's ruleset a pull request behind the default
        branch gets the board's main-moved comment at every move of it,
        which renews its updated_at though nobody has touched it since
        August; only its opening or a commit in the window count as work."""
        parked = pull(105, "claude/4719", "mona-secret", "2026-08-02T00:00:00Z", "2026-10-09T12:00:00Z", "5" * 40,
                      state="open")
        routes = {**ROUTES, f"{API}/pulls": [parked, *PULLS],
                  f"{API}/pulls/105": {"number": 105, "mergeable": True, "mergeable_state": "behind"},
                  f"{API}/pulls/105/commits": [commit("5" * 40, "2026-08-01T00:00:00Z", login="mona-secret")],
                  f"{API}/pulls/105/reviews": [],
                  **{f"{API}/pulls/{number}/files": [] for number in (101, 102, 103, 105)}}
        opener = FakeGitHub(routes)
        with tempfile.TemporaryDirectory() as folder:
            code, record, _ = collect(folder, {"GITHUB_TOKEN": "t"}, opener)
        self.assertEqual(code, 0)
        for section in ("parallel", "by_setting", "pairs"):
            self.assertEqual(record[section], EXPECTED[section], section)
        # Its commits, its reviews and its detail, as before the breakdown,
        # and nothing more but the usage records' listing: no changed file,
        # since nothing was beside anything.
        self.assertEqual(len(opener.calls), 21 + 3 + 1)
        # A commit made in the window, a rebase here, puts it back at work,
        # beside everything since August.
        routes[f"{API}/pulls/105/commits"] = [commit("5" * 40, "2026-08-01T00:00:00Z", "2026-10-09T11:00:00Z",
                                                     login="mona-secret")]
        routes[f"{API}/commits/{'5' * 40}/check-runs"] = runs()
        with tempfile.TemporaryDirectory() as folder:
            _, record, _ = collect(folder, {"GITHUB_TOKEN": "t"}, FakeGitHub(routes))
        self.assertEqual({name: row["pull_requests"] for name, row in record["by_setting"].items()
                          if row["pull_requests"]}, {"undetermined": 2})
        # Its work began before the look-back, but it has not ended, so it
        # is no truncated pull request: those are the window's finished ones.
        self.assertEqual(record["parallel"]["truncated"], 0)

    def test_a_pull_request_opened_in_the_window_is_at_work_whatever_its_commits_dates(self):
        """The other half of the rule: a pull request opened in the window is
        work in the window, though every commit it carries was made before,
        a branch pushed in August and opened in October."""
        opened = pull(106, "claude/4720", "mona-secret", "2026-10-06T00:00:00Z", "2026-10-06T00:00:00Z", "6" * 40,
                      state="open")
        routes = {**ROUTES, f"{API}/pulls": [PULLS[0], opened, *PULLS[1:]],
                  f"{API}/pulls/106": {"number": 106, "mergeable": True, "mergeable_state": "clean"},
                  f"{API}/pulls/106/commits": [commit("6" * 40, "2026-08-01T00:00:00Z", login="mona-secret")],
                  f"{API}/pulls/106/reviews": [],
                  f"{API}/commits/{'6' * 40}/check-runs": runs()}
        with tempfile.TemporaryDirectory() as folder:
            code, record, _ = collect(folder, {"GITHUB_TOKEN": "t"}, FakeGitHub(routes))
        self.assertEqual(code, 0)
        # Lisa's 103, open since October 5, and Mona's 106 are each other's
        # partner, so both are open beside another person.
        self.assertEqual({name: row["open"] for name, row in record["by_setting"].items() if row["open"]},
                         {"several_people": 2})

    def test_the_look_back_comments_are_read_only_when_the_windows_own_work_began_before_it(self):
        """A pull request that began and ended in the look-back bears on no
        count of the window's, so its early start costs no read of the
        look-back's comments: here every counted pull request began in the
        window, and Mona's 98, merged in August, is a unit of the look-back
        whose commits are not read either."""
        earlier = pull(98, "claude/4709", "mona-secret", "2026-08-20T00:00:00Z", "2026-08-25T00:00:00Z", "8" * 40,
                       merged="2026-08-25T00:00:00Z")
        routes = {**ROUTES, f"{API}/pulls": [*PULLS, earlier]}
        opener = FakeGitHub(routes)
        with tempfile.TemporaryDirectory() as folder:
            code, record, _ = collect(folder, {"GITHUB_TOKEN": "t"}, opener)
        self.assertEqual(code, 0)
        for section in ("parallel", "by_setting", "pairs"):
            self.assertEqual(record[section], EXPECTED[section], section)
        look_back = metrics.iso(metrics.look_back_start(metrics.Window.ending(metrics.parse_time(NOW), 30)))
        self.assertNotIn(look_back, [query.get("since") for query in opener.queries])
        self.assertEqual(len(opener.calls), 1 + 5 + 3 + 5 + 3 + 3 + 1 + 1)


class Economics(unittest.TestCase):
    """What the work cost, from the sessions' trailers and the Actions runs'
    records, read after the breakdown and never in its way."""

    def collect(self, folder, routes=None, cache=None, opener=None):
        opener = opener or FakeGitHub(routes or world_routes())
        out = Path(folder) / "METRICS.json"
        extra = ["--usage-cache", str(cache)] if cache else []
        args = metrics.parse_args(["collect", "--repo", REPO, "--out", str(out), "--root", str(folder), "--now", NOW,
                                   *extra])
        with redirect_stdout(io.StringIO()) as shown:
            self.assertEqual(metrics.collect(args, {"GITHUB_TOKEN": "t"}, opener=opener, sleep=lambda s: None), 0)
        return json.loads(out.read_text()), shown.getvalue(), opener

    def test_the_world_costs_what_its_trailers_and_records_say(self):
        with tempfile.TemporaryDirectory() as folder:
            record, shown, _ = self.collect(folder)
        self.assertEqual(record["economics"], WORLD_ECONOMICS)
        self.assertEqual(record["coordination"], WORLD_COORDINATION)
        self.assertEqual(tuple(record["economics"]), metrics.economics.ECONOMICS_KEYS)
        for side in ("alone", "parallel"):
            self.assertEqual(tuple(record["coordination"][side]), metrics.economics.GROUP_KEYS)
        self.assertEqual(tuple(record["coordination"]["ratios"]), metrics.economics.RATIO_KEYS)
        self.assertNotIn("usage records", shown)

    def test_the_token_goes_to_the_api_and_never_to_the_storage_host(self):
        with tempfile.TemporaryDirectory() as folder:
            _, _, opener = self.collect(folder)
        hosts = {host for host, _ in opener.sent}
        self.assertEqual(hosts, {"api.github.com", "storage.example"})
        for host, headers in opener.sent:
            self.assertEqual("authorization" in headers, host == "api.github.com", host)

    def test_a_run_reads_only_the_records_its_cache_does_not_hold(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = Path(folder) / "usage.json"
            first, _, opener = self.collect(folder, cache=cache)
            self.assertEqual(sum(path.endswith("/zip") for path in opener.calls), 2)
            kept = json.loads(cache.read_text())
            self.assertEqual(sorted(kept["records"]), ["9001", "9002"])
            second, _, opener = self.collect(folder, cache=cache)
        self.assertEqual(sum(path.endswith("/zip") for path in opener.calls), 0)
        self.assertEqual(second["economics"], first["economics"])

    def test_records_over_the_limit_wait_for_the_next_run(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(metrics, "USAGE_LIMIT", 1):
            record, shown, opener = self.collect(folder)
        self.assertEqual((record["economics"]["actions_runs"], record["economics"]["actions_runs_unread"]), (1, 1))
        self.assertEqual([path for path in opener.calls if path.endswith("/zip")],
                         [f"{API}/actions/artifacts/9001/zip"])
        self.assertTrue(shown.rstrip("\n").endswith("; 1 Actions runs' usage records were left for the next run"),
                        shown)

    def test_records_that_cannot_be_listed_leave_only_the_cached_ones(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = Path(folder) / "usage.json"
            self.collect(folder, cache=cache)
            routes = world_routes()
            del routes[f"{API}/actions/artifacts"]
            record, shown, _ = self.collect(folder, routes=routes, cache=cache)
            kept = json.loads(cache.read_text())
        self.assertEqual(record["economics"]["actions_runs"], 2)
        self.assertIsNone(record["economics"]["actions_runs_unread"])
        self.assertEqual(sorted(kept["records"]), ["9001", "9002"])
        self.assertTrue(shown.rstrip("\n").endswith(
            "; the Actions runs' usage records could not be listed, so only those read before count"), shown)

    def test_a_spent_hour_leaves_every_record_after_it_for_the_next_run(self):
        class SpentAtDownloads(FakeGitHub):
            def open(self, request, timeout=None):
                if request.full_url.endswith("/zip"):
                    self.calls.append(urllib.parse.urlsplit(request.full_url).path)
                    body = io.BytesIO(b'{"message": "API rate limit exceeded for installation ID 1."}')
                    raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, body)
                return super().open(request, timeout)

        opener = SpentAtDownloads(world_routes())
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "METRICS.json"
            args = metrics.parse_args(["collect", "--repo", REPO, "--out", str(out), "--root", folder, "--now", NOW])
            with redirect_stdout(io.StringIO()):
                self.assertEqual(metrics.collect(args, {"GITHUB_TOKEN": "t"}, opener=opener,
                                                 sleep=lambda seconds: None), 0)
            record = json.loads(out.read_text())
        self.assertEqual((record["economics"]["actions_runs"], record["economics"]["actions_runs_unread"]), (0, 2))
        self.assertEqual(sum(path.endswith("/zip") for path in opener.calls), 1)

    def test_an_answer_cut_short_or_not_http_is_one_record_left_unread_and_the_run_goes_on(self):
        # Budgeted.location and Budgeted.download ask GitHub and the storage
        # host with urllib themselves, around the library's request, and
        # http.client's own errors are no OSError; a download read up to a
        # limit also stops short of the length it was told without a word.
        zipped, stored = f"{API}/actions/artifacts/9001/zip", "/usage/9001.zip"
        for name, path, raw in (("refused, its body cut short", zipped, REFUSAL_CUT_SHORT),
                                ("asked for its redirect, not HTTP", zipped, NOT_HTTP),
                                ("downloaded in chunks, cut short", stored, CHUNKS_CUT_SHORT),
                                ("downloaded, cut short of its length", stored, LENGTH_CUT_SHORT),
                                ("downloaded, not HTTP", stored, NOT_HTTP)):
            with self.subTest(name), RawSocket({path: raw}) as here, tempfile.TemporaryDirectory() as folder:
                opener = PartlyOverASocket(world_routes(), here)
                record, shown, _ = self.collect(folder, opener=opener)
                self.assertIn(path, opener.calls)
                self.assertEqual((record["economics"]["actions_runs"], record["economics"]["actions_runs_unread"]),
                                 (1, 1))
                self.assertEqual(record["economics"]["tokens_total"], WORLD_ECONOMICS["tokens_total"] - 332300)
                self.assertTrue(shown.rstrip("\n").endswith(
                    "; 1 Actions runs' usage records were left for the next run"), shown)

    def test_location_and_download_say_what_went_wrong_as_the_github_error_the_run_reads(self):
        refused, garbled = f"{API}/actions/artifacts/9001/zip", f"{API}/actions/artifacts/9002/zip"
        answers = {refused: REFUSAL_CUT_SHORT, garbled: NOT_HTTP, "/chunks": CHUNKS_CUT_SHORT,
                   "/length": LENGTH_CUT_SHORT, "/ssh": NOT_HTTP}
        with RawSocket(answers) as here:
            api = metrics.Budgeted("t", REPO, opener=here.opener(), sleep=lambda seconds: None)
            with self.assertRaises(metrics.GitHubError) as caught:
                api.location(refused)
            self.assertEqual((str(caught.exception), caught.exception.status, caught.exception.detail),
                             (f"GET {refused}: HTTP 502", 502, ""))
            self.assertEqual(api.calls, 1)
            with self.assertRaises(metrics.GitHubError) as caught:
                api.location(garbled)
            self.assertTrue(str(caught.exception).startswith(f"GET {garbled}: BadStatusLine("), caught.exception)
            self.assertIsNone(caught.exception.status)
            with self.assertRaises(metrics.GitHubError) as caught:
                api.download(f"{STORAGE}/chunks", metrics.USAGE_MAX_BYTES)
            self.assertTrue(str(caught.exception).startswith("download: IncompleteRead("), caught.exception)
            with self.assertRaises(metrics.GitHubError) as caught:
                api.download(f"{STORAGE}/length", metrics.USAGE_MAX_BYTES)
            self.assertEqual(str(caught.exception), "download: the answer was cut short, 4 of 600 bytes")
            with self.assertRaises(metrics.GitHubError) as caught:
                api.download(f"{STORAGE}/ssh", metrics.USAGE_MAX_BYTES)
            self.assertTrue(str(caught.exception).startswith("download: BadStatusLine("), caught.exception)

    def test_a_record_anyone_uploaded_never_ends_the_run_and_only_what_is_read_is_kept(self):
        # Any workflow run of the repository can upload an artifact named as
        # the usage records are, so its bytes are anyone's; each of these
        # once ended the run with a traceback, and no record was written.
        # Record 9001 is still read where its JSON is, with what cannot be
        # read in it passed over, and passed over whole where it is not.
        sonnet = [900, 25000, 0, 300000, 6400]
        cases = {
            "seconds json reads as infinity": (zipped_text(record_text(seconds="1e999")), sonnet),
            "seconds too large for a float": (zipped_text(record_text(seconds="9" * 401)), sonnet),
            "models given as a list": (zipped_text(record_text(models="[1, 2]")), None),
            "a key nested deeper than the interpreter's stack": (
                zipped_text(record_text(worker="[" * 20000 + "]" * 20000)), "unread"),
            "a key nested deep enough to stop the cache being written": (
                zipped_text(record_text(worker="[" * 1500 + "]" * 1500)), sonnet),
            "a workflow that is no word": (zipped_text(record_text(workflow="[" * 900 + "]" * 900)), sonnet),
            "an entry marked encrypted": (with_entry_field(zipped_text(record_text()), 6, 8, 1), "unread"),
            "a compression method zipfile does not know": (
                with_entry_field(zipped_text(record_text()), 8, 10, 99), "unread"),
            "a broken deflate stream": (with_broken_stream(zipped_text(record_text(), zipfile.ZIP_DEFLATED)),
                                        "unread"),
            "a model named by a run of 60,000 brackets": (
                zipped_text(record_text(models=json.dumps({"[" * 60000: [1, 0, 0, 0, 1],
                                                           "claude-sonnet-5-5": sonnet}))), sonnet),
        }
        for name, (data, sonnet_read) in cases.items():
            routes = world_routes()
            routes["/usage/9001.zip"] = data
            with self.subTest(name):
                with tempfile.TemporaryDirectory() as folder:
                    cache = Path(folder) / "usage.json"
                    record, _, _ = self.collect(folder, routes=routes, cache=cache)
                    kept = json.loads(cache.read_text())["records"]
                economics = record["economics"]
                self.assertEqual(economics["actions_runs"], 1 if sonnet_read == "unread" else 2)
                self.assertEqual(economics["actions_runs_unread"], 0)
                self.assertEqual(economics["tokens_unpriced"], WORLD_ECONOMICS["tokens_unpriced"])
                spent = sum(sonnet_read) if isinstance(sonnet_read, list) else 0
                self.assertEqual(economics["tokens_total"], WORLD_ECONOMICS["tokens_total"] - 332300 + spent)
                self.assertEqual(sorted(kept), ["9002"] if sonnet_read == "unread" else ["9001", "9002"])
                for entry in kept.values():
                    self.assertEqual(set(entry["record"]),
                                     {"v", "source", "workflow", "job", "issue", "pull", "seconds", "models",
                                      "profile"})

    def test_a_cache_an_older_run_wrote_is_read_in_the_form_the_cache_keeps(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = Path(folder) / "usage.json"
            uploaded = json.loads(record_text(worker='"left over"'))
            cache.write_text(json.dumps({"v": metrics.USAGE_CACHE_VERSION, "records": {
                "9001": {"at": "2026-10-07T10:28:00Z", "record": uploaded},
                "9002": {"at": "2026-10-06T08:00:00Z", "record": [1, 2]},
                "9003": ["not", "an", "entry"]}}))
            self.assertEqual(sorted(metrics.read_usage_cache(cache)), ["9001"])
            self.assertNotIn("worker", metrics.read_usage_cache(cache)["9001"]["record"])
            self.assertEqual(metrics.read_usage_cache(cache)["9001"]["record"]["profile"], RUN_9001_PROFILE)
            cache.write_text(json.dumps({"v": metrics.USAGE_CACHE_VERSION, "records": [1, 2]}))
            self.assertEqual(metrics.read_usage_cache(cache), {})

    def test_a_cache_kept_before_the_profile_is_read_again_from_the_artifacts(self):
        # Version 1 kept no run's profile: its records still count, marked
        # old, and are downloaded again for the profile.
        with tempfile.TemporaryDirectory() as folder:
            cache = Path(folder) / "usage.json"
            cache.write_text(json.dumps({"v": 1, "records": OLDER_CACHE}))
            read = metrics.read_usage_cache(cache)
            self.assertEqual(sorted(read), ["9001", "9002"])
            self.assertEqual({(entry["old"], entry["record"]["profile"]) for entry in read.values()}, {(True, None)})
            record, _, opener = self.collect(folder, cache=cache)
            kept = json.loads(cache.read_text())
        self.assertEqual(sum(path.endswith("/zip") for path in opener.calls), 2)
        self.assertEqual(record["economics"], WORLD_ECONOMICS)
        self.assertEqual((kept["v"], kept["records"]["9001"]["record"]["profile"]),
                         (metrics.USAGE_CACHE_VERSION, RUN_9001_PROFILE))
        self.assertFalse(any("old" in entry for entry in kept["records"].values()))

    def test_an_old_record_whose_artifact_has_expired_still_counts(self):
        # A repository whose artifacts live less than the 60 days a run
        # reads back: the old records cannot be downloaded again, and the
        # economics keep them as they were.
        routes = world_routes()
        routes[f"{API}/actions/artifacts"] = {"total_count": 4, "artifacts": [
            dict(item, expired=True) for item in WORLD_ARTIFACTS["artifacts"]]}
        with tempfile.TemporaryDirectory() as folder:
            cache = Path(folder) / "usage.json"
            cache.write_text(json.dumps({"v": 1, "records": OLDER_CACHE}))
            record, _, opener = self.collect(folder, routes=routes, cache=cache)
            kept = json.loads(cache.read_text())
        self.assertEqual(sum(path.endswith("/zip") for path in opener.calls), 0)
        self.assertEqual(record["economics"], WORLD_ECONOMICS)
        self.assertEqual(record["coordination"], WORLD_COORDINATION)
        self.assertEqual({key: entry.get("old") for key, entry in kept["records"].items()},
                         {"9001": True, "9002": True}, "still old, so a later run may read them again")

    def test_an_old_record_whose_download_fails_is_kept_as_it_was(self):
        routes = world_routes()
        del routes[f"{API}/actions/artifacts/9001/zip"]
        with tempfile.TemporaryDirectory() as folder:
            cache = Path(folder) / "usage.json"
            cache.write_text(json.dumps({"v": 1, "records": OLDER_CACHE}))
            record, _, _ = self.collect(folder, routes=routes, cache=cache)
            kept = json.loads(cache.read_text())["records"]
        self.assertEqual(record["economics"], WORLD_ECONOMICS)
        self.assertEqual((kept["9001"].get("old"), kept["9001"]["record"]["profile"]), (True, None))
        self.assertEqual((kept["9002"].get("old"), kept["9002"]["record"]["profile"]), (None, RUN_9002_PROFILE))

    def test_old_records_are_read_again_only_after_the_new_ones_within_the_limit(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(metrics, "USAGE_LIMIT", 1):
            cache = Path(folder) / "usage.json"
            cache.write_text(json.dumps({"v": metrics.USAGE_CACHE_VERSION, "records": {
                "9002": dict(OLDER_CACHE["9002"], old=True)}}))
            record, shown, opener = self.collect(folder, cache=cache)
            kept = json.loads(cache.read_text())["records"]
        self.assertEqual([path for path in opener.calls if path.endswith("/zip")],
                         [f"{API}/actions/artifacts/9001/zip"])
        self.assertEqual((record["economics"]["actions_runs"], record["economics"]["actions_runs_unread"]), (2, 0))
        self.assertNotIn("left for the next run", shown)
        self.assertEqual((kept["9002"].get("old"), "old" in kept["9001"]), (True, False))

    def test_a_listing_or_a_breakdown_read_cut_short_or_not_http_is_one_line_of_the_record(self):
        # The library's request lets http.client's own errors through, which
        # are no OSError; Budgeted.request says them as GitHubErrors, so the
        # listing of the usage records and the breakdown's reads fail as
        # GitHub's refusals of them do.
        listing, files = f"{API}/actions/artifacts", f"{API}/pulls/301/files"
        cut = (b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 500\r\n\r\n"
               b'{"total_count": 4, "artifacts": [')
        chunks = (b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n"
                  b"400\r\n[{")
        for name, raw, answer in (("a refusal whose words are cut short", REFUSAL_CUT_SHORT, "HTTP 502"),
                                  ("an answer cut short of its length", cut, "no answer"),
                                  ("chunks cut short", chunks, "no answer"), ("not HTTP", NOT_HTTP, "no answer")):
            with self.subTest(name, read="listing"), RawSocket({listing: raw}) as here, \
                    tempfile.TemporaryDirectory() as folder:
                record, shown, _ = self.collect(folder, opener=PartlyOverASocket(world_routes(), here))
                self.assertIn(listing, here.asked)
                self.assertIsNone(record["economics"]["actions_runs_unread"])
                self.assertTrue(shown.rstrip("\n").endswith(
                    "; the Actions runs' usage records could not be listed, so only those read before count"), shown)
            with self.subTest(name, read="breakdown"), RawSocket({files: raw}) as here, \
                    tempfile.TemporaryDirectory() as folder:
                record, shown, _ = self.collect(folder, opener=PartlyOverASocket(world_routes(), here))
                self.assertIn(files, here.asked)
                self.assertNotIn("economics", record)
                self.assertIn(f"the breakdown was left out because GitHub failed one of its reads ({answer})", shown)

    def test_a_request_says_what_http_client_raised_as_the_github_error_of_its_call(self):
        refused, garbled = f"{API}/pulls/1", f"{API}/pulls/2"
        with RawSocket({refused: REFUSAL_CUT_SHORT, garbled: NOT_HTTP}) as here:
            api = metrics.Budgeted("t", REPO, opener=here.opener(), sleep=lambda seconds: None)
            with self.assertRaises(metrics.GitHubError) as caught:
                api.get(refused)
            self.assertEqual((str(caught.exception), caught.exception.status, caught.exception.detail),
                             (f"GET {refused}: HTTP 502", 502, ""))
            self.assertEqual(api.calls, 1, "a call GitHub refused is a call of the hour")
            with self.assertRaises(metrics.GitHubError) as caught:
                api.get(garbled)
            self.assertTrue(str(caught.exception).startswith(f"GET {garbled}: BadStatusLine("), caught.exception)
            self.assertIsNone(caught.exception.status)
            self.assertEqual(api.calls, 1)

    def test_a_download_follows_no_redirect_and_an_address_urllib_cannot_read_is_a_github_error(self):
        with RawSocket({}) as here:
            port = here.listener.getsockname()[1]
            here.answers.update({
                "/to-plain": (f"HTTP/1.1 302 Found\r\nLocation: http://127.0.0.1:{port}/plain\r\n"
                              "Content-Length: 0\r\n\r\n").encode(),
                "/plain": b"HTTP/1.1 200 OK\r\nContent-Type: application/zip\r\nContent-Length: 4\r\n\r\nPK\x03\x04",
                "/to-unreadable": b"HTTP/1.1 302 Found\r\nLocation: http://[::1/x\r\nContent-Length: 0\r\n\r\n",
                f"{API}/actions/artifacts/9001/zip": (b"HTTP/1.1 302 Found\r\nLocation: https://[::1/x\r\n"
                                                      b"Content-Length: 0\r\n\r\n")})
            # As a run builds them: the library's opener follows redirects,
            # and the one location asks with does not.
            api = metrics.Budgeted("t", REPO, opener=here.opener(follow=True), sleep=lambda seconds: None)
            api.unfollowed = here.opener()
            target = api.location(f"{API}/actions/artifacts/9001/zip")
            self.assertEqual((target, api.calls), ("https://[::1/x", 1), "GitHub's address, as it gave it")
            for url, said in ((f"{STORAGE}/to-plain", "download: HTTP 302"),
                              (f"{STORAGE}/to-unreadable", "download: HTTP 302"),
                              (target, "download: an address urllib cannot read ("),
                              ("storage.example/x.zip", "a download address that is not https is not fetched")):
                with self.assertRaises(metrics.GitHubError) as caught:
                    api.download(url, metrics.USAGE_MAX_BYTES)
                self.assertTrue(str(caught.exception).startswith(said), caught.exception)
            self.assertNotIn("/plain", here.asked, "a download never follows a redirect to plain http")

    def test_a_download_longer_than_the_limit_is_too_big_whatever_length_it_gives(self):
        # Read up to the limit and one byte more, a download whose length is
        # over that is too big, and so no record of ours, not one cut short.
        big = b"HTTP/1.1 200 OK\r\nContent-Type: application/zip\r\nContent-Length: 70000\r\n\r\n" + b"x" * 70000
        with RawSocket({"/usage/9001.zip": big}) as here, tempfile.TemporaryDirectory() as folder:
            cache = Path(folder) / "usage.json"
            record, _, _ = self.collect(folder, cache=cache, opener=PartlyOverASocket(world_routes(), here))
            kept = json.loads(cache.read_text())["records"]
        self.assertEqual((record["economics"]["actions_runs"], record["economics"]["actions_runs_unread"]), (1, 0))
        self.assertEqual(sorted(kept), ["9002"])

    def test_what_is_no_record_of_ours_is_passed_over(self):
        routes = world_routes()
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("record.json", json.dumps({"v": 1, "source": "somewhere else"}))
        routes["/usage/9001.zip"] = buffer.getvalue()
        routes["/usage/9002.zip"] = b"not a zip"
        listing = json.loads(json.dumps(WORLD_ARTIFACTS))
        listing["artifacts"].append(artifact(9005, "symphony-usage-80-1-claude", "2026-10-05T00:00:00Z",
                                             size=metrics.USAGE_MAX_BYTES + 1))
        routes[f"{API}/actions/artifacts"] = listing
        with tempfile.TemporaryDirectory() as folder:
            record, _, opener = self.collect(folder, routes=routes)
        self.assertEqual((record["economics"]["actions_runs"], record["economics"]["actions_runs_unread"]), (0, 0))
        self.assertNotIn(f"{API}/actions/artifacts/9005/zip", opener.calls)
        self.assertEqual(record["economics"]["tokens_total"], WORLD_ECONOMICS["tokens_total"] - 332300 - 109100)

    def test_the_listing_stops_at_the_first_page_made_before_the_look_back(self):
        old = artifact(8000, "symphony-usage-1-1-claude", "2026-07-01T00:00:00Z")
        api = metrics.Budgeted("t", REPO, opener=FakeGitHub({f"{API}/actions/artifacts": {"artifacts": [old]}}),
                               sleep=lambda seconds: None)
        self.assertEqual(metrics.usage_artifacts(api, metrics.parse_time("2026-08-11T12:00:00Z")), [])

    def test_a_revert_is_a_merged_pull_request_titled_as_the_revert_button_titles_it(self):
        window = metrics.Window.ending(metrics.parse_time(NOW), 30)
        facts = [metrics.PullFacts({"number": 1, "title": 'Revert "Add the thing"', "merged_at": "2026-10-02T00:00:00Z"}),
                 metrics.PullFacts({"number": 2, "title": "Revert the thing", "merged_at": "2026-10-02T00:00:00Z"}),
                 metrics.PullFacts({"number": 3, "title": 'Revert "Old"', "merged_at": "2026-08-02T00:00:00Z"})]
        self.assertEqual(metrics.reverts(facts, window), 1)


def collect_profile(folder, routes=None, environ=None, remaining=None, cache=None):
    """collect with --profile-out over the world: METRICS.json, PROFILE.json
    and what the run printed."""
    out, profile_out = Path(folder) / "METRICS.json", Path(folder) / "PROFILE.json"
    extra = ["--usage-cache", str(cache)] if cache else []
    args = metrics.parse_args(["collect", "--repo", REPO, "--out", str(out), "--root", str(folder), "--now", NOW,
                               "--profile-out", str(profile_out), *extra])
    opener = FakeGitHub(routes or world_routes(), remaining=remaining)
    with redirect_stdout(io.StringIO()) as shown:
        code = metrics.collect(args, {"GITHUB_TOKEN": "t"} if environ is None else environ, opener=opener,
                               sleep=lambda seconds: None)
    return code, json.loads(out.read_text()), profile_out.read_text(), shown.getvalue()


class ProfileSums(unittest.TestCase):
    """PROFILE.json: the Symphony-Profile lines on the pull requests'
    commits and the runs' profiles, summed beside the breakdown and under
    the same switch, into a file of the repository's own that the collector
    does not read."""

    def test_the_world_sums_to_what_its_lines_and_runs_say(self):
        with tempfile.TemporaryDirectory() as folder:
            code, record, text, shown = collect_profile(folder)
        found = json.loads(text)
        self.assertEqual(code, 0)
        self.assertEqual(found, WORLD_PROFILE)
        self.assertEqual(tuple(found), metrics.PROFILE_KEYS)
        self.assertEqual(tuple(found["by_setting"]), metrics.SETTINGS)
        for row in [*found["by_setting"].values(), found["coordination"]["alone"], found["coordination"]["parallel"]]:
            self.assertEqual(tuple(row), metrics.profile.GROUP_KEYS)
        self.assertEqual(tuple(found["coordination"]["ratios"]), metrics.profile.RATIO_KEYS)
        self.assertEqual((record["economics"], record["coordination"]), (WORLD_ECONOMICS, WORLD_COORDINATION))
        self.assertIn(f"METRICS.json and {Path(folder) / 'PROFILE.json'} written over 30 days", shown)
        self.assertEqual(sum(row["profiled"] for row in found["by_setting"].values()),
                         found["coordination"]["parallel"]["profiled"])

    def test_nothing_of_the_repository_reaches_the_file(self):
        with tempfile.TemporaryDirectory() as folder:
            _, _, text, _ = collect_profile(folder)
        for secret in ("secret", "a1a1a1a1", "b1b1b1b1", A1, B1, TOKEN, "claude/", REPO, LINK):
            self.assertNotIn(secret, text)
        self.assertNotIn("mcp", text)

    def test_sharing_off_writes_off_alone_and_calls_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            switch(folder, "off\n")
            out, profile_out = Path(folder) / "METRICS.json", Path(folder) / "PROFILE.json"
            args = metrics.parse_args(["collect", "--repo", REPO, "--out", str(out), "--root", folder, "--now", NOW,
                                       "--profile-out", str(profile_out)])
            with redirect_stdout(io.StringIO()):
                self.assertEqual(metrics.collect(args, {"GITHUB_TOKEN": "t"}, opener=NoCalls()), 0)
            self.assertEqual(json.loads(profile_out.read_text()), {"schema": "symphony-profile-sums/1",
                                                                   "sharing": "off"})

    def test_the_sums_are_left_out_with_the_breakdown(self):
        routes = world_routes()
        del routes[f"{API}/pulls/314/commits"]
        with tempfile.TemporaryDirectory() as folder:
            code, record, text, _ = collect_profile(folder, routes=routes)
        self.assertEqual(code, 0)
        self.assertNotIn("economics", record)
        self.assertEqual(json.loads(text), {"schema": "symphony-profile-sums/1", "generated_at": NOW,
                                            "window_days": 30, "sharing": "on"})
        self.assertEqual(tuple(json.loads(text)), metrics.PROFILE_KEYS[:4])

    def test_without_its_option_no_profile_is_written(self):
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(metrics, "profile_keys", side_effect=AssertionError("summed")) as summed:
            code, record, _, shown, _, _ = collect_world(folder)
            self.assertEqual(sorted(path.name for path in Path(folder).iterdir()), ["METRICS.json"])
        self.assertEqual(code, 0)
        self.assertNotIn("PROFILE", shown)
        summed.assert_not_called()

    def test_a_fault_in_the_sums_never_stops_metrics_json(self):
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(metrics, "profile_keys", side_effect=ZeroDivisionError("a slip")):
            out, profile_out = Path(folder) / "METRICS.json", Path(folder) / "PROFILE.json"
            args = metrics.parse_args(["collect", "--repo", REPO, "--out", str(out), "--root", folder, "--now", NOW,
                                       "--profile-out", str(profile_out)])
            with redirect_stdout(io.StringIO()) as shown:
                code = metrics.collect(args, {"GITHUB_TOKEN": "t"}, opener=FakeGitHub(world_routes()),
                                       sleep=lambda seconds: None)
            record, written = json.loads(out.read_text()), profile_out.exists()
        self.assertEqual(code, 0)
        self.assertEqual(record["economics"], WORLD_ECONOMICS)
        self.assertFalse(written, "the write step keeps the branch's PROFILE.json")
        self.assertIn("; PROFILE.json was not written: ZeroDivisionError: a slip", shown.getvalue())
        self.assertIn("::warning::PROFILE.json was not written, so the branch keeps its older one: ZeroDivisionError",
                      shown.getvalue())

    def test_runs_not_read_again_yet_are_counted_as_unread(self):
        routes = world_routes()
        del routes[f"{API}/actions/artifacts/9001/zip"]
        with tempfile.TemporaryDirectory() as folder:
            cache = Path(folder) / "usage.json"
            cache.write_text(json.dumps({"v": 1, "records": OLDER_CACHE}))
            _, record, text, _ = collect_profile(folder, routes=routes, cache=cache)
        found = json.loads(text)
        self.assertEqual((record["economics"]["actions_runs_unread"], found["actions_runs_unread"]), (0, 1))
        self.assertEqual(found["by_setting"]["workflow_agents"]["profiled"], 0, "9001 is read without its profile")
        unlisted = world_routes()
        del unlisted[f"{API}/actions/artifacts"]
        with tempfile.TemporaryDirectory() as folder:
            _, _, text, _ = collect_profile(folder, routes=unlisted)
        self.assertIsNone(json.loads(text)["actions_runs_unread"])

    def test_beyond_the_world_each_run_and_line_counts_where_it_belongs(self):
        # The world and five things more: a run from the look-back naming
        # 309, which ended in the window; a run in the window naming
        # nothing, not the coordinator's; a coordinator's run from the
        # look-back; 330, which only open work (331) is beside; and on 330
        # a line of a session seen nowhere else, made before the window.
        with tempfile.TemporaryDirectory() as folder:
            code, _, text, _ = collect_profile(folder, routes=beyond_the_world_routes())
        found = json.loads(text)
        self.assertEqual(code, 0)
        self.assertEqual(found["sessions"], 3, "the line made before the window names its session")
        self.assertEqual(found["actions_runs"], 3, "9001, 9002 and the look-back's run on 309")
        self.assertEqual(found["by_setting"]["workflow_agents"]["calls"], 18 + 7, "the look-back's run on 309")
        self.assertEqual((found["coordination"]["alone"]["pull_requests"],
                          found["coordination"]["parallel"]["pull_requests"]), (0, 12), "331 is beside 330")
        self.assertEqual(found["coordination"]["parallel"]["calls"], 236 + 7 + 4,
                         "neither the run naming nothing nor the look-back's coordinator run")


class ProtocolVersion(unittest.TestCase):
    def test_it_is_the_release_and_seven_hex_digits_which_the_collector_keeps(self):
        with tempfile.TemporaryDirectory() as folder:
            vendored = Path(folder) / "VENDORED"
            vendored.write_text("sdlc-protocol 0.2.0 f530a6694477466c5826a6626681c8c84c8f1aa9\nhash  __init__.py\n")
            self.assertEqual(metrics.protocol_version(vendored), "0.2.0 f530a66")
            for text in ("", "0.2.0 f530a66\n", "sdlc-protocol 0.2.0\n", "something 0.2.0 f530a66\n"):
                vendored.write_text(text)
                self.assertIsNone(metrics.protocol_version(vendored), text)
            self.assertIsNone(metrics.protocol_version(Path(folder) / "missing"))
        for version in ("0.2.0 f530a66", metrics.protocol_version()):
            self.assertTrue(COLLECTOR_VERSION.fullmatch(version), version)
        self.assertIsNone(COLLECTOR_VERSION.fullmatch("0.2.0 f530a6"))


class Durations(unittest.TestCase):
    def test_the_median_rounds_half_up_to_whole_seconds(self):
        self.assertIsNone(metrics.median_seconds([]))
        self.assertEqual(metrics.median_seconds([5]), 5)
        self.assertEqual(metrics.median_seconds([1, 2]), 2)
        self.assertEqual(metrics.median_seconds([4, 1, 3, 2]), 3)
        self.assertEqual(metrics.median_seconds([30, 10, 20]), 20)

    def test_the_p90_is_the_nearest_rank(self):
        self.assertIsNone(metrics.p90_seconds([]))
        self.assertEqual(metrics.p90_seconds([7]), 7)
        self.assertEqual(metrics.p90_seconds([2, 1]), 2)
        self.assertEqual(metrics.p90_seconds(list(range(1, 11))), 9)
        self.assertEqual(metrics.p90_seconds(list(range(20, 0, -1))), 18)

    def test_a_wait_against_the_clock_is_left_out(self):
        early, late = metrics.parse_time("2026-10-01T00:00:00Z"), metrics.parse_time("2026-10-01T01:00:00Z")
        self.assertEqual(metrics.seconds_between(early, late), 3600)
        self.assertIsNone(metrics.seconds_between(late, early))
        self.assertIsNone(metrics.seconds_between(None, late))

    def test_rates_round_to_four_places(self):
        self.assertEqual(metrics.ratio(1, 3), 0.3333)
        self.assertEqual(metrics.ratio(2, 3), 0.6667)
        self.assertIsNone(metrics.ratio(0, 0))


class ReleasedClaims(unittest.TestCase):
    RELEASE = metrics.RELEASE_MARKER + "\nReleased: no commit for a day."

    def test_the_marker_is_the_vendored_protocols(self):
        self.assertEqual(metrics.RELEASE_MARKER, metrics.claims.RELEASE_MARKER)
        self.assertEqual(metrics.RELEASE_MARKER, "<!-- sdlc-coordinator: claim-released -->")

    def test_a_release_said_again_within_a_day_counts_once(self):
        # An hourly coordinator repeated the release of one idle claim; a
        # second claim on the issue is released a day or more later.
        comments = [
            comment(7, "2026-10-01T10:00:00Z", self.RELEASE),
            comment(7, "2026-10-01T11:00:00Z", self.RELEASE),
            comment(7, "2026-10-01T12:00:00Z", self.RELEASE),
            comment(7, "2026-10-04T09:00:00Z", self.RELEASE),
            comment(8, "2026-10-01T11:30:00Z", self.RELEASE),
        ]
        self.assertEqual(metrics.released_claims(comments), 3)
        self.assertEqual(metrics.released_claims(list(reversed(comments))), 3)

    def test_only_a_comment_that_opens_with_the_marker_counts(self):
        comments = [
            comment(8, "2026-10-01T10:00:00Z", "> " + self.RELEASE),
            comment(9, "2026-10-01T10:00:00Z", "Why released?\n" + self.RELEASE),
            dict(comment(10, "2026-10-01T10:00:00Z", self.RELEASE), issue_url=""),
            dict(comment(11, "2026-10-01T10:00:00Z", self.RELEASE), created_at=None),
        ]
        self.assertEqual(metrics.released_claims(comments), 0)
        self.assertEqual(metrics.released_claims([]), 0)

    def test_whoever_wrote_it_counts(self):
        # The workflow's token may show the owner's account, a private
        # member of the organization, as a contributor.
        comments = [comment(7, "2026-10-01T10:00:00Z", self.RELEASE, association="CONTRIBUTOR")]
        self.assertEqual(metrics.released_claims(comments), 1)


class Unchanged(unittest.TestCase):
    def test_only_generated_at_may_differ(self):
        old = dict(EXPECTED, schema="sdlc-metrics/1", generated_at="2026-10-09T04:43:00Z")
        same = dict(old, generated_at="2026-10-10T04:43:00Z")
        moved = dict(same, rates={"merge_rate": 1.0, "first_check_pass_rate": None})
        self.assertTrue(metrics.same_apart_from_time(json.dumps(old), json.dumps(same)))
        self.assertFalse(metrics.same_apart_from_time(json.dumps(old), json.dumps(moved)))
        self.assertFalse(metrics.same_apart_from_time("not json", json.dumps(same)))
        self.assertTrue(metrics.same_apart_from_time(json.dumps(metrics.OFF_RECORD), json.dumps(metrics.OFF_RECORD)))


# --- the work-setting breakdown ------------------------------------------------

LINK = "https://claude.ai/code/"
# Two people's work in one repository, beside two bots': Ann's from two
# cloud sessions and a local one, Ben's from one. The window runs from
# 2026-09-10 12:00 to 2026-10-10 12:00 and the look-back from 2026-08-11
# 12:00. Every commit is the account claude's, as a cloud session's is, so
# only the opener's login tells the people apart.
A1, A2, B1 = "session_01AnnFirstSecretAaaaaaaa", "session_01AnnSecondSecretBbbbbbb", "session_01BenOnlySecretCcccccccc"
TOKEN = "annlocal-secret-0001"


def merge_sha(number):
    """A merge commit's sha: hex, one per pull request, its first seven what
    the board's mark carries."""
    return f"{number:04d}abc" + "0" * 33


def commit_sha(number, index):
    return f"{number:04d}{index:02d}e" + "f" * 33


def trailer(session, usage="", profile=""):
    """A cloud session's trailers, with a Symphony-Usage line when usage
    gives its value and a Symphony-Profile line after it when profile
    does, as the hook writes them."""
    lines = f"Work.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\nClaude-Session: {LINK}{session}"
    lines += f"\nSymphony-Usage: v1 {usage}" if usage else ""
    return lines + (f"\nSymphony-Profile: v1 {profile}" if profile else "")


def profiled(session, *counts):
    """A Symphony-Profile line's value: the session and each count in
    tools/profile.py's TRAILER_FIELDS order (calls, failed, repeated, reads,
    rereads, read_bytes, reread_bytes, peak, compactions, drops,
    tool_seconds)."""
    fields = zip(metrics.profile.TRAILER_FIELDS, counts, strict=True)
    return f"session={session} " + " ".join(f"{key}={value}" for key, value in fields)


def run_profile(*counts):
    """A run's profile block, its counts in the same order."""
    return dict(zip(metrics.profile.TRAILER_FIELDS, counts, strict=True))


def usage_record(workflow, job, models, seconds, issue=None, pull=None, profile=None):
    """The record a run in Actions uploads (tools/usage.py), zipped as
    upload-artifact keeps it, with its profile block when profile gives it."""
    record = {"v": 1, "source": "actions", "workflow": workflow, "job": job, "worker": "", "issue": issue,
              "pull": pull, "at": "2026-10-06T00:00:00Z", "seconds": seconds, "api_seconds": seconds,
              "turns": 12, "reported_usd": 0.0, "error": False, "models": models}
    if profile is not None:
        record["profile"] = profile
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("record.json", json.dumps(record))
    return buffer.getvalue()


def zipped_text(text, compression=zipfile.ZIP_STORED):
    """A record's JSON exactly as written, zipped as upload-artifact keeps it."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=compression) as archive:
        archive.writestr("record.json", text)
    return buffer.getvalue()


def record_text(**raw):
    """World record 9001's JSON with some fields' values written as raw JSON
    text, which json.dumps would never write."""
    record = {"v": 1, "source": "actions", "workflow": "claude", "job": "claude", "worker": "", "issue": None,
              "pull": 309, "at": "2026-10-06T00:00:00Z", "seconds": 340.5,
              "models": {"claude-sonnet-5-5": [900, 25000, 0, 300000, 6400]}, "profile": RUN_9001_PROFILE}
    text = json.dumps({**record, **{key: f"@{key}@" for key in raw}})
    for key, value in raw.items():
        text = text.replace(f'"@{key}@"', value)
    return text


def with_entry_field(data, local_offset, central_offset, value):
    """A zip with one two-byte field of its entry set to value, in the local
    header and in the central directory alike: the flags at 6 and 8, the
    compression method at 8 and 10."""
    data = bytearray(data)
    for signature, offset in ((b"PK\x03\x04", local_offset), (b"PK\x01\x02", central_offset)):
        struct.pack_into("<H", data, data.find(signature) + offset, value)
    return bytes(data)


def with_broken_stream(data):
    """A deflated zip whose compressed bytes are garbled."""
    data = bytearray(data)
    local = data.find(b"PK\x03\x04")
    name_length, extra_length = struct.unpack_from("<HH", data, local + 26)
    start = local + 30 + name_length + extra_length
    for index in range(start, start + 12):
        data[index] ^= 0xA5
    return bytes(data)


def artifact(number, name, created, expired=False, size=600):
    return {"id": number, "name": name, "created_at": created, "expired": expired, "size_in_bytes": size}


def world_commit(number, index, authored, message="Work, no trailer."):
    return {"sha": commit_sha(number, index), "author": user("claude"),
            "commit": {"author": {"name": "Claude", "email": "noreply@anthropic.com", "date": authored},
                       "committer": {"date": authored}, "message": message}}


def world_pull(number, login, created, updated, ref, merged=None, closed=None, state="closed", kind="User", body="",
               draft=False):
    return {"number": number, "title": "Secret title", "body": body, "state": state, "draft": draft,
            "created_at": created, "updated_at": updated, "merged_at": merged, "closed_at": closed or merged,
            "merge_commit_sha": merge_sha(number) if merged else None, "user": user(login, kind),
            "head": {"ref": ref, "sha": commit_sha(number, 0), "repo": {"full_name": REPO}}, "base": base()}


def mark(number, created, state, sha, login="github-actions[bot]", kind="Bot"):
    """The board's main-moved comment, as the vendored board writes it."""
    body = metrics.board.MAIN_MOVED_MARKER.format(sha=sha) + "\n" + metrics.board.main_moved_text(state, "main", sha)
    return {"issue_url": f"https://api.github.com{API}/issues/{number}", "created_at": created, "body": body,
            "user": user(login, kind)}


WORLD_PULLS = [
    world_pull(312, "ben-secret", "2026-10-09T11:00:00Z", "2026-10-09T12:00:00Z", "feature/ben-twelve", state="open"),
    world_pull(311, "ann-secret", "2026-10-09T10:00:00Z", "2026-10-09T11:30:00Z", "claude/511", state="open",
               draft=True),
    world_pull(310, "dependabot[bot]", "2026-10-02T00:00:00Z", "2026-10-09T00:00:00Z", "dependabot/pip/x",
               state="open", kind="Bot"),
    world_pull(308, "ben-secret", "2026-10-07T10:00:00Z", "2026-10-07T11:00:00Z", "claude/508",
               merged="2026-10-07T11:00:00Z"),
    world_pull(309, "claude[bot]", "2026-10-07T10:10:00Z", "2026-10-07T10:30:00Z", "claude/509",
               merged="2026-10-07T10:30:00Z", kind="Bot"),
    world_pull(307, "ann-secret", "2026-10-05T11:00:00Z", "2026-10-05T15:00:00Z", "claude/507",
               merged="2026-10-05T15:00:00Z"),
    world_pull(319, "dependabot[bot]", "2026-10-05T12:30:00Z", "2026-10-05T13:00:00Z", "dependabot/pip/y",
               merged="2026-10-05T13:00:00Z", kind="Bot"),
    # A link inside a sentence names no session.
    world_pull(306, "ann-secret", "2026-10-05T10:00:00Z", "2026-10-05T12:00:00Z", "claude/506",
               merged="2026-10-05T12:00:00Z", body=f"Closes #506. Continues {LINK}{A1} where it stopped."),
    world_pull(305, "ben-secret", "2026-10-03T11:00:00Z", "2026-10-03T13:00:00Z", "claude/505",
               merged="2026-10-03T13:00:00Z", body=f"Closes #505\n\n{LINK}{B1}\n"),
    world_pull(304, "ben-secret", "2026-10-03T10:00:00Z", "2026-10-03T10:58:00Z", "claude/504",
               merged="2026-10-03T10:58:00Z"),
    world_pull(303, "ben-secret", "2026-10-01T15:00:00Z", "2026-10-01T18:00:00Z", "claude/503",
               closed="2026-10-01T18:00:00Z"),
    world_pull(302, "ann-secret", "2026-10-01T11:00:00Z", "2026-10-01T16:00:00Z", "claude/session-ann2",
               merged="2026-10-01T16:00:00Z",
               body=f"Plan and summary.\n\n---\n_Generated by [Claude Code]({LINK}{A2})_"),
    world_pull(301, "ann-secret", "2026-10-01T10:00:00Z", "2026-10-01T14:00:00Z", "claude/501",
               merged="2026-10-01T14:00:00Z"),
    world_pull(313, "ann-secret", "2026-09-05T10:00:00Z", "2026-09-12T10:00:00Z", "claude/513",
               merged="2026-09-12T10:00:00Z"),
    world_pull(315, "ann-secret", "2026-07-01T10:00:00Z", "2026-09-11T00:00:00Z", "claude/515",
               merged="2026-09-11T00:00:00Z"),
    # In the look-back, ended before the window: read only as a partner.
    world_pull(314, "ann-secret", "2026-09-01T10:00:00Z", "2026-09-06T10:00:00Z", "claude/514",
               merged="2026-09-06T10:00:00Z"),
    # Open and unchanged since before the window: stale, nobody's partner.
    world_pull(316, "ann-secret", "2026-08-20T00:00:00Z", "2026-08-25T00:00:00Z", "claude/516", state="open",
               draft=True),
    # Changed before the look-back: the listing stops here.
    world_pull(317, "ben-secret", "2026-07-20T00:00:00Z", "2026-08-01T00:00:00Z", "claude/517",
               merged="2026-08-01T00:00:00Z"),
]
# The usage the sessions' commits carry (tools/usage.py), in the trailer's
# order: uncached input, cache writes kept five minutes and an hour, cache
# reads, output. 313's commit was made before the window, so it is on no
# bill of the window, though it counts for 313, which ended in it. The
# profile lines after them (tools/profile.py) are summed the same way into
# PROFILE.json, and 312's, open, into none of it.
WORLD_COMMITS = {
    301: [world_commit(301, 1, "2026-10-01T09:00:00Z", trailer(
              A1, "session=a1a1a1a1 seconds=2400 claude-opus-5-5=2100,61000,0,880000,18500",
              profiled("a1a1a1a1", 40, 2, 1, 12, 3, 60000, 9000, 150000, 0, 0, 300))),
          world_commit(301, 2, "2026-10-01T12:00:00Z", trailer(
              A1, "session=a1a1a1a1 seconds=1500 claude-opus-5-5=900,22000,0,540000,9800",
              profiled("a1a1a1a1", 25, 1, 0, 8, 2, 30000, 4000, 180000, 1, 1, 200))),
          world_commit(301, 3, "2026-10-01T12:30:00Z", trailer(B1))],
    # A profile line whose session is no token's: its counts are summed,
    # and it names no session.
    302: [world_commit(302, 1, "2026-10-01T10:30:00Z"), world_commit(302, 2, "2026-10-01T13:00:00Z", (
              "Work.\n\nSymphony-Profile: v1 " + profiled("toolongtoken", 12, 1, 0, 4, 1, 10000, 1000, 100000, 0, 0, 60)))],
    303: [world_commit(303, 1, "2026-10-01T15:00:00Z", trailer(B1))],
    304: [world_commit(304, 1, "2026-10-03T09:50:00Z", trailer(
              B1, "session=b1b1b1b1 seconds=1200 claude-sonnet-5-5=1500,30000,0,420000,7600",
              profiled("b1b1b1b1", 30, 0, 2, 10, 4, 40000, 12000, 120000, 0, 0, 150))),
          world_commit(304, 2, "2026-10-03T10:56:00Z", trailer(B1))],
    305: [world_commit(305, 1, "2026-10-03T10:55:00Z")],
    306: [world_commit(306, 1, "2026-10-05T09:00:00Z")],
    307: [world_commit(307, 1, "2026-10-05T11:00:00Z", trailer(
              A1, "session=a1a1a1a1 seconds=900 claude-haiku-5-5=300,4000,0,30000,900 "
                  "claude-opus-5-5=700,18000,0,260000,5200",
              profiled("a1a1a1a1", 20, 1, 0, 6, 1, 20000, 2000, 90000, 0, 0, 100)))],
    # The Sept 20 commit is more than seven days before the opening.
    308: [world_commit(308, 1, "2026-09-20T09:00:00Z", trailer(B1)),
          world_commit(308, 2, "2026-10-07T09:00:00Z", trailer(
              B1, "session=b1b1b1b1 seconds=1600 claude-sonnet-5-5=1800,35000,0,610000,11200",
              profiled("b1b1b1b1", 50, 4, 3, 15, 6, 70000, 20000, 200000, 0, 0, 400)))],
    309: [world_commit(309, 1, "2026-10-07T10:05:00Z")],
    310: [world_commit(310, 1, "2026-10-02T00:00:00Z")],
    311: [world_commit(311, 1, "2026-10-09T09:00:00Z", trailer(A2)),
          world_commit(311, 2, "2026-10-09T09:30:00Z", f"Local work.\n\nSymphony-Session: {TOKEN}")],
    312: [world_commit(312, 1, "2026-10-09T11:00:00Z", trailer(
              B1, "session=b1b1b1b1 seconds=600 claude-sonnet-5-5=400,9000,0,120000,2100",
              profiled("b1b1b1b1", 10, 0, 0, 3, 0, 8000, 0, 60000, 0, 0, 50)))],
    313: [world_commit(313, 1, "2026-09-05T09:00:00Z", trailer(
              A1, "session=a1a1a1a1 seconds=3000 claude-opus-5-5=2500,70000,0,1000000,20000",
              profiled("a1a1a1a1", 35, 2, 1, 11, 2, 50000, 6000, 160000, 1, 0, 250)))],
    314: [world_commit(314, 1, "2026-09-01T09:00:00Z", trailer(A2))],
    315: [world_commit(315, 1, "2026-07-01T09:00:00Z", trailer(A2))],
    319: [world_commit(319, 1, "2026-10-05T12:30:00Z")],
}
WORLD_FILES = {
    301: ["src/secret_a.py", "src/secret_shared.py"], 302: ["src/secret_shared.py", "docs/secret_b.md"],
    303: ["docs/secret_b.md"], 304: ["src/secret_c.py"], 305: ["src/secret_d.py"], 306: ["src/secret_e.py"],
    307: ["src/secret_e.py"], 313: ["src/secret_f.py"], 314: ["src/secret_g.py"], 315: ["src/secret_g.py"],
}
WORLD_REVIEWS = {
    308: [{"user": user("ann-secret"), "state": "CHANGES_REQUESTED", "submitted_at": "2026-10-07T10:20:00Z",
           "body": "Secret review words."}],
    303: [{"user": user("ann-secret"), "state": "COMMENTED", "submitted_at": "2026-10-01T16:30:00Z",
           "body": "Secret review words."}],
    # The author's own answer, which GitHub files as a review.
    301: [{"user": user("ann-secret"), "state": "COMMENTED", "submitted_at": "2026-10-01T13:30:00Z",
           "body": "Secret answer of the author."}],
}
WORLD_DETAILS = {310: {"number": 310, "mergeable": True, "mergeable_state": "clean"},
                 311: {"number": 311, "mergeable": False, "mergeable_state": "draft"},
                 312: {"number": 312, "mergeable": False, "mergeable_state": "dirty"}}
WORLD_COMMENTS = [
    mark(313, "2026-09-07T00:00:00Z", "conflicting", merge_sha(314)[:7]),
    mark(302, "2026-10-01T14:05:00Z", "conflicting", merge_sha(301)[:7]),
    mark(305, "2026-10-03T12:05:00Z", "behind", merge_sha(304)[:7]),
    mark(307, "2026-10-05T12:10:00Z", "conflicting", merge_sha(306)[:7]),
    {"issue_url": f"https://api.github.com{API}/issues/507", "created_at": "2026-10-05T13:00:00Z",
     "body": metrics.RELEASE_MARKER + "\nReleased: no commit for a day, secret plan left.", "user": user("ann-secret")},
    # A person's paste of the board's words: conflicts_seen takes it, the
    # breakdown does not.
    mark(308, "2026-10-07T10:40:00Z", "conflicting", merge_sha(309)[:7], login="ann-secret", kind="User"),
    mark(312, "2026-10-09T12:00:00Z", "conflicting", "deadbee"),
]


# The Actions runs' usage records, newest first as GitHub lists them: the
# @claude run that made 309, the coordinator's plan of an epic, which names
# no pull request, an artifact of another workflow, and an expired record.
# The two records carry the runs' profiles, 9002's on the parallel side.
STORAGE = "https://storage.example"
WORLD_ARTIFACTS = {"total_count": 4, "artifacts": [
    artifact(9003, "build-output", "2026-10-08T00:00:00Z"),
    artifact(9001, "symphony-usage-71-1-claude", "2026-10-07T10:28:00Z"),
    artifact(9002, "symphony-usage-70-1-plan", "2026-10-06T08:00:00Z"),
    artifact(9000, "symphony-usage-60-1-claude", "2026-09-30T08:00:00Z", expired=True),
]}
RUN_9001_PROFILE = run_profile(18, 0, 0, 5, 1, 15000, 3000, 80000, 0, 0, 0)
RUN_9002_PROFILE = run_profile(6, 0, 0, 2, 0, 5000, 0, 40000, 0, 0, 0)
WORLD_RECORDS = {
    9001: usage_record("claude", "claude", {"claude-sonnet-5-5": [900, 25000, 0, 300000, 6400]}, 340.5, pull=309,
                       profile=RUN_9001_PROFILE),
    9002: usage_record("coordinator", "plan", {"claude-opus-5-5": [600, 15000, 0, 90000, 3500]}, 95.0, issue=900,
                       profile=RUN_9002_PROFILE),
}


# A version 1 cache of the world's two records, as an older run kept them,
# with no profile.
OLDER_CACHE = {
    "9001": {"at": "2026-10-07T10:28:00Z", "record": json.loads(record_text(profile="null"))},
    "9002": {"at": "2026-10-06T08:00:00Z", "record": {
        "v": 1, "source": "actions", "workflow": "coordinator", "job": "plan", "issue": 900, "pull": None,
        "seconds": 95.0, "models": {"claude-opus-5-5": [600, 15000, 0, 90000, 3500]}}},
}


def beyond_the_world_routes():
    """The world with the runs, the pull requests and the line that
    ProfileSums.test_beyond_the_world_each_run_and_line_counts_where_it_belongs
    names."""
    routes = world_routes()
    extra = {
        9004: ("symphony-usage-40-1-claude", "2026-09-01T08:00:00Z",
               usage_record("claude", "claude", {"claude-sonnet-5-5": [10, 0, 0, 0, 10]}, 30.0, pull=309,
                            profile=run_profile(7, 0, 0, 1, 0, 100, 0, 90000, 0, 0, 0))),
        9005: ("symphony-usage-80-1-claude", "2026-10-08T06:00:00Z",
               usage_record("claude", "claude", {"claude-sonnet-5-5": [10, 0, 0, 0, 10]}, 30.0, issue=999,
                            profile=run_profile(5, 0, 0, 1, 0, 100, 0, 30000, 0, 0, 0))),
        9006: ("symphony-usage-41-1-plan", "2026-09-02T08:00:00Z",
               usage_record("coordinator", "plan", {"claude-opus-5-5": [10, 0, 0, 0, 10]}, 30.0, issue=901,
                            profile=run_profile(9, 0, 0, 1, 0, 100, 0, 50000, 0, 0, 0))),
    }
    listed = WORLD_ARTIFACTS["artifacts"] + [artifact(number, name, made) for number, (name, made, _) in extra.items()]
    routes[f"{API}/actions/artifacts"] = {"total_count": len(listed), "artifacts": sorted(
        listed, key=lambda item: item["created_at"], reverse=True)}
    for number, (_, _, record) in extra.items():
        routes[f"{API}/actions/artifacts/{number}/zip"] = Redirect(f"{STORAGE}/usage/{number}.zip?sig=x")
        routes[f"/usage/{number}.zip"] = record
    pulls = list(WORLD_PULLS)
    at = next(index for index, item in enumerate(pulls) if item["number"] == 313)
    pulls[at:at] = [
        world_pull(330, "zed-secret", "2026-09-15T00:30:00Z", "2026-09-15T02:00:00Z", "claude/530",
                   merged="2026-09-15T02:00:00Z"),
        world_pull(331, "yan-secret", "2026-09-15T00:00:00Z", "2026-09-15T01:00:00Z", "claude/531", state="open")]
    routes[f"{API}/pulls"] = pulls
    commits = {330: [world_commit(330, 1, "2026-09-07T00:00:00Z", "Work.\n\nSymphony-Profile: v1 " + profiled(
                         "c1c1c1c1", 4, 0, 0, 1, 0, 100, 0, 1000, 0, 0, 5)),
                     world_commit(330, 2, "2026-09-15T01:00:00Z")],
               331: [world_commit(331, 1, "2026-09-15T00:10:00Z")]}
    for number, listed_commits in commits.items():
        routes[f"{API}/pulls/{number}/commits"] = listed_commits
        routes[f"{API}/pulls/{number}/reviews"] = []
        routes[f"{API}/pulls/{number}/files"] = [{"filename": f"src/secret_{number}.py"}]
        for item in listed_commits:
            routes[f"{API}/commits/{item['sha']}/check-runs"] = runs()
    routes[f"{API}/pulls/331"] = {"number": 331, "mergeable": True, "mergeable_state": "clean"}
    # 331, open since Sept 15, is beside the world's work since, whose files
    # are read for it.
    for item in pulls:
        routes.setdefault(f"{API}/pulls/{item['number']}/files", [])
    return routes


def world_routes():
    routes = {f"{API}/pulls": WORLD_PULLS, f"{API}/branches": [], f"{API}/issues/comments": WORLD_COMMENTS,
              f"{API}/actions/artifacts": WORLD_ARTIFACTS}
    for number, record in WORLD_RECORDS.items():
        routes[f"{API}/actions/artifacts/{number}/zip"] = Redirect(f"{STORAGE}/usage/{number}.zip?sig=x")
        routes[f"/usage/{number}.zip"] = record
    for number, listed in WORLD_COMMITS.items():
        routes[f"{API}/pulls/{number}/commits"] = listed
        routes[f"{API}/pulls/{number}/reviews"] = WORLD_REVIEWS.get(number, [])
        for item in listed:
            routes[f"{API}/commits/{item['sha']}/check-runs"] = runs()
    for number, detail in WORLD_DETAILS.items():
        routes[f"{API}/pulls/{number}"] = detail
    for number, names in WORLD_FILES.items():
        routes[f"{API}/pulls/{number}/files"] = [{"filename": name} for name in names]
    return routes


def row_of(keys, *values):
    return dict(zip(keys, values, strict=True))


def setting_row(*values):
    return row_of(metrics.SETTING_KEYS, *values)


def pair_row(*values):
    return row_of(metrics.PAIR_KEYS, *values)


WORLD_COUNTS = {"claims": 11, "pull_requests_opened": 13, "merged": 11, "closed_unmerged": 1, "reviews": 2,
                "changes_requested": 1, "check_runs_passed": 0, "check_runs_failed": 0, "conflicts_seen": 4,
                "released_claims": 1, "contributors": 3}
WORLD_DURATIONS = {"claim_to_first_pull_request_median": 600, "claim_to_first_pull_request_p90": 1472400,
                   "open_to_merge_median": 7200, "open_to_merge_p90": 604800, "first_review_median": 3300,
                   "first_review_p90": 5400}
WORLD_RATES = {"merge_rate": 0.9167, "first_check_pass_rate": None}
# The world's economics, as docs/setup/metrics.md shows them. The bill is
# the trailers of the six commits made in the window that carry one and
# the two records of runs in it; the delivery is the eleven pull requests
# of people and of the Claude workflows that ended in it (319, dependabot's,
# is neither), of which six have usage against them: 301, 304, 307, 308,
# 309 by its record and 313 by a commit made before the window.
WORLD_ECONOMICS = {
    "prices_as_of": "2026-10-16", "pull_requests": 11, "pull_requests_measured": 6, "merged": 10, "sessions": 2,
    "actions_runs": 2, "actions_runs_unread": 0, "tokens_input": 9200, "tokens_cache_write": 219000,
    "tokens_cache_read": 3250000, "tokens_output": 65200, "tokens_total": 3543400, "tokens_unpriced": 0,
    "estimated_usd": 2.3672, "coordinator_usd": 0.1654, "claude_seconds": 8635, "commits": 16, "check_failures": 0,
    "reverts": 0, "tokens_by_family": {"fable": 0, "opus": 1927300, "sonnet": 1580900, "haiku": 35200, "other": 0},
    "tokens_per_merge": 354340.0, "usd_per_merge": 0.23672, "claude_seconds_per_merge": 863.5,
    "commits_per_merge": 1.6,
}
# Every pull request of the world had other work beside it, so the alone
# side is empty and no ratio can be taken; the parallel side carries the
# coordinator's plan, which names none of them.
WORLD_COORDINATION = {
    "alone": {"pull_requests": 0, "merged": 0, "measured": 0, "measured_merged": 0, "tokens": 0,
              "estimated_usd": 0.0, "claude_seconds": 0, "commits": 0, "check_failures": 0, "first_check_passed": 0,
              "first_check_counted": 0, "open_to_merge_median": None, "active_seconds": 0},
    "parallel": {"pull_requests": 11, "merged": 10, "measured": 6, "measured_merged": 6, "tokens": 4504400,
                 "estimated_usd": 3.2709, "claude_seconds": 10940, "commits": 16, "check_failures": 0,
                 "first_check_passed": 0, "first_check_counted": 0, "open_to_merge_median": 10800,
                 "active_seconds": 6383400},
    "ratios": {"tokens_per_merge": None, "usd_per_merge": None, "latency": None, "throughput": None,
               "first_check_pass": None, "commits_per_merge": None, "failures_per_pull_request": None},
}


def profile_row(*values):
    return row_of(metrics.profile.GROUP_KEYS, *values)


# The world's PROFILE.json, as docs/setup/metrics.md shows it: the profile
# lines of the pull requests that ended in the window, two of 301's among
# them, 313's from before the window and 302's, whose session is no
# token's, each in its setting as the breakdown sorts it, with 9001's
# profile on 309; on the parallel side, where every one of them is, the
# coordinator's plan too (9002). The median peak is of 301's 180000, 302's
# 100000, 304's 120000, 307's 90000, 308's 200000, 309's 80000 and 313's
# 160000.
NOTHING_PROFILED = (0,) * 10
WORLD_PROFILE = {
    "schema": "symphony-profile-sums/1", "generated_at": NOW, "window_days": 30, "sharing": "on", "sessions": 2,
    "actions_runs": 2, "actions_runs_unread": 0,
    "by_setting": {
        "solo": profile_row(1, 1, 1, 1, 50, 4, 3, 15, 6, 70000, 20000, 0, 0, 400, 200000),
        "one_session": profile_row(2, 2, 1, 1, 30, 0, 2, 10, 4, 40000, 12000, 0, 0, 150, 120000),
        "one_person_sessions": profile_row(3, 3, 2, 2, 100, 5, 2, 31, 7, 140000, 19000, 2, 1, 750, 170000),
        "several_people": profile_row(1, 0, 0, 0, *NOTHING_PROFILED, None),
        "several_people_and_sessions": profile_row(1, 1, 1, 1, 12, 1, 0, 4, 1, 10000, 1000, 0, 0, 60, 100000),
        "undetermined": profile_row(2, 2, 1, 1, 20, 1, 0, 6, 1, 20000, 2000, 0, 0, 100, 90000),
        "workflow_agents": profile_row(1, 1, 1, 1, 18, 0, 0, 5, 1, 15000, 3000, 0, 0, 0, 80000),
        "automation": profile_row(1, 1, 0, 0, *NOTHING_PROFILED, None),
    },
    "coordination": {
        "alone": profile_row(0, 0, 0, 0, *NOTHING_PROFILED, None),
        "parallel": profile_row(11, 10, 7, 7, 236, 11, 7, 73, 20, 300000, 57000, 2, 1, 1460, 120000),
        "ratios": {"calls_per_merge": None, "reads_per_merge": None, "rereads_per_merge": None, "peak": None},
    },
}
# The world's breakdown, as docs/setup/metrics.md shows it: every setting's
# row in SETTING_KEYS order and every relation's in PAIR_KEYS order.
WORLD_EXPECTED = {
    "parallel": {"people": 2, "sessions": 4, "sessions_per_person_max": 4, "pull_requests_with_session": 11,
                 "pull_requests_without_session": 1, "pull_requests_multi_session": 2, "sessions_across_people": 1,
                 "peak_parallel": 2, "peak_parallel_people": 2, "peak_sessions_one_person": 2, "conflict_marks": 3,
                 "conflict_marks_unattributed": 1, "open_conflicting": 2, "open_conflicting_drafts": 1,
                 "open_conflicting_dirty": 1, "truncated": 1, "files_unread": 0},
    "by_setting": {
        "solo": setting_row(1, 1, 0, 0, 0, 0, 1, 1, 0, 7200, 1, 0, 0),
        "one_session": setting_row(2, 2, 0, 0, 0, 0, 0, 2, 2, 11580, 0, 1, 0),
        "one_person_sessions": setting_row(3, 3, 0, 0, 1, 0, 0, 3, 5, 6814800, 2, 0, 2),
        "several_people": setting_row(1, 0, 1, 2, 0, 0, 0, 1, 1, 10800, 1, 0, 1),
        "several_people_and_sessions": setting_row(1, 1, 0, 0, 1, 0, 0, 0, 2, 19800, 1, 0, 1),
        "undetermined": setting_row(2, 2, 0, 0, 1, 1, 0, 2, 2, 25200, 1, 0, 2),
        "workflow_agents": setting_row(1, 1, 0, 0, 0, 0, 0, 1, 0, 1500, 0, 0, 0),
        "automation": setting_row(1, 1, 0, 1, 0, 0, 0, 0, 0, 1800, 0, 0, 0),
    },
    "pairs": {
        "same_session": pair_row(2, 1, 1, 1, 1, 0, 0),
        "one_person_sessions": pair_row(3, 1, 1, 2, 1, 2, 1),
        "several_people": pair_row(1, 0, 1, 1, 1, 0, 0),
        "undetermined": pair_row(1, 0, 1, 1, 1, 1, 1),
    },
}
# Each unit's work setting; 314 is a unit from the look-back, and 316 and
# 317 are none.
WORLD_SETTINGS = {301: "one_person_sessions", 302: "several_people_and_sessions", 303: "several_people",
                  304: "one_session", 305: "one_session", 306: "undetermined", 307: "undetermined", 308: "solo",
                  309: "workflow_agents", 310: "automation", 311: "several_people", 312: "several_people",
                  313: "one_person_sessions", 314: "one_person_sessions", 315: "one_person_sessions",
                  319: "automation"}


def collect_world(folder, remaining=None, routes=None):
    """collect over the world, or over other routes: its exit code, its
    record, the file's text, what it printed and said, and the fake API."""
    opener = FakeGitHub(routes or world_routes(), remaining=remaining)
    out = Path(folder) / "METRICS.json"
    args = metrics.parse_args(["collect", "--repo", REPO, "--out", str(out), "--root", str(folder), "--now", NOW])
    with redirect_stdout(io.StringIO()) as shown, redirect_stderr(io.StringIO()) as said:
        code = metrics.collect(args, {"GITHUB_TOKEN": "t"}, opener=opener, sleep=lambda seconds: None)
    text = out.read_text()
    return code, json.loads(text), text, shown.getvalue(), said.getvalue(), opener


def world_units():
    api = metrics.Budgeted("t", REPO, opener=FakeGitHub(world_routes()), sleep=lambda seconds: None)
    window = metrics.Window.ending(metrics.parse_time(NOW), 30)
    facts, _, _, rest = metrics.read_repository(api, window)
    earlier, _ = metrics.updated_since(rest, metrics.look_back_start(window))
    return metrics.work_units(api, facts, earlier, window), window


def labelled_pull(number, login, sessions, start, end, kind="User", ref=None, into="main"):
    """A pull request open from start to end and merged then, into main or
    the branch into names, whose description names each of its sessions by
    the link alone on a line."""
    return {"number": number, "user": user(login, kind), "state": "closed",
            "body": "".join(f"{LINK}session_{name}\n" for name in sessions), "created_at": start,
            "merged_at": end, "closed_at": end, "updated_at": end, "merge_commit_sha": merge_sha(number),
            "head": {"ref": ref or f"claude/{number}", "repo": {"full_name": REPO}}, "base": base(into)}


def labelled_unit(number, login, sessions, start, end, first_commit=None, **pull_fields):
    """labelled_pull's unit, with one commit authored at first_commit, or at
    its opening."""
    return metrics.unit_of(labelled_pull(number, login, sessions, start, end, **pull_fields),
                           [commit("0" * 40, first_commit or start)], True)


class Sessions(unittest.TestCase):
    def test_a_session_is_a_whole_line_of_a_commit_or_a_description(self):
        names = metrics.session_names
        self.assertEqual(names("Fix the parser.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n"
                               "Claude-Session: https://claude.ai/code/session_01AbCdEf"), {"session_01AbCdEf"})
        self.assertEqual(names("claude-session:   https://claude.ai/code/session_X1  "), {"session_X1"})
        self.assertEqual(names("Closes #4.\n\nhttps://claude.ai/code/session_Y2\n"), {"session_Y2"})
        self.assertEqual(names("Summary.\n\n---\n_Generated by [Claude Code](https://claude.ai/code/session_Z3)_"),
                         {"session_Z3"})
        self.assertEqual(names("Symphony-Session: worker-0001-secret"), {"token:worker-0001-secret"})
        self.assertEqual(names("Work.\n\nClaude-Session: https://claude.ai/code/session_A\n"
                               "Claude-Session: https://claude.ai/code/session_B"), {"session_A", "session_B"})
        for text in ("See https://claude.ai/code/session_Q4 for the plan.",
                     "Claude-Session: https://example.com/code/session_R5", "Claude-Session: none",
                     "Symphony-Session: abc1234", "Co-Authored-By: Claude <noreply@anthropic.com>",
                     "Claude-Session: https://claude.ai/code/session_ok trailing words", "", None):
            self.assertEqual(names(text), set(), text)
        # GitHub's web page saves a description with CRLF line ends.
        self.assertEqual(names("Plan.\r\n\r\n---\r\n"
                               "_Generated by [Claude Code](https://claude.ai/code/session_W6)_\r\n"), {"session_W6"})

    def test_sessions_are_read_from_the_commits_and_the_description(self):
        pull_ = {"body": "Plan.\n\nhttps://claude.ai/code/session_Body1\n"}
        commits = [{"commit": {"message": "Work.\n\nClaude-Session: https://claude.ai/code/session_Commit1"}},
                   {"commit": {"message": "Local work.\n\nSymphony-Session: local-run-0001"}}, {"commit": {}}]
        self.assertEqual(metrics.sessions_of(pull_, commits),
                         frozenset({"session_Body1", "session_Commit1", "token:local-run-0001"}))
        self.assertEqual(metrics.sessions_of({"body": None}, []), frozenset())


class Intervals(unittest.TestCase):
    def test_the_work_runs_from_the_first_authored_commit_to_the_end(self):
        at, merged = metrics.parse_time, "2026-10-08T12:00:00Z"

        def unit(created, *dates, committed=None):
            return metrics.unit_of(pull(401, "claude/4711", "ann-secret", created, merged, "0" * 40, merged=merged),
                                   [commit("0" * 40, date, committed) for date in dates], True)

        # An author date seven days and an hour before the opening is an old
        # commit carried in; one exactly seven days before is kept.
        self.assertEqual(unit("2026-10-08T10:00:00Z", "2026-10-08T08:00:00Z", "2026-10-01T09:00:00Z").start,
                         at("2026-10-08T08:00:00Z"))
        self.assertEqual(unit("2026-10-08T10:00:00Z", "2026-10-01T10:00:00Z").start, at("2026-10-01T10:00:00Z"))
        # A rebase renews the committer date and keeps the author date.
        rebased = unit("2026-10-08T10:00:00Z", "2026-10-08T08:00:00Z", committed="2026-10-08T09:30:00Z")
        self.assertEqual((rebased.start, rebased.end), (at("2026-10-08T08:00:00Z"), at(merged)))

    def test_a_branch_used_again_starts_no_earlier_than_its_last_pull_request_ended(self):
        at = metrics.parse_time
        first = metrics.unit_of(pull(402, "claude/x", "ann-secret", "2026-10-05T10:00:00Z", "2026-10-05T12:00:00Z",
                                     "0" * 40, merged="2026-10-05T12:00:00Z"), [], True)
        again = pull(403, "claude/x", "ann-secret", "2026-10-05T13:00:00Z", "2026-10-05T15:00:00Z", "0" * 40,
                     merged="2026-10-05T15:00:00Z")
        commits = [commit("1" * 40, "2026-10-05T11:00:00Z"), commit("2" * 40, "2026-10-05T12:30:00Z")]
        second = metrics.unit_of(again, commits, True)
        metrics.floor_starts([first, second])
        self.assertEqual(second.start, at("2026-10-05T12:00:00Z"))
        elsewhere = metrics.unit_of(dict(again, head={"ref": "claude/y"}), commits, True)
        metrics.floor_starts([first, elsewhere])
        self.assertEqual(elsewhere.start, at("2026-10-05T11:00:00Z"))

    def test_a_pull_request_without_an_end_or_stale_is_no_unit(self):
        no_dates = pull(404, "claude/4714", "ann-secret", "2026-10-01T00:00:00Z", "2026-10-02T00:00:00Z", "0" * 40)
        self.assertIsNone(metrics.unit_of(no_dates, [], True))
        stale = pull(405, "claude/4715", "ann-secret", "2026-08-20T00:00:00Z", "2026-08-25T00:00:00Z", "0" * 40,
                     state="open")
        self.assertIsNone(metrics.unit_of(stale, [], False))
        live = metrics.unit_of(dict(stale, created_at="2026-10-01T00:00:00Z"), [], True)
        self.assertIsNone(live.end)
        self.assertEqual(live.start, metrics.parse_time("2026-10-01T00:00:00Z"))


# Name, person, sessions, day of October 2026, start, end, and the setting
# the rules give it.
SETTING_CASES = [
    ("U1", "ann", ["S1"], 1, "09:00:00", "10:00:00", "solo"),
    ("U2", "ann", ["S1"], 1, "11:00:00", "13:00:00", "one_session"),
    ("U3", "ann", ["S1"], 1, "12:00:00", "14:00:00", "one_session"),
    ("U4", "ann", ["S1"], 1, "15:00:00", "17:00:00", "one_person_sessions"),
    ("U5", "ann", ["S2"], 1, "16:00:00", "18:00:00", "one_person_sessions"),
    ("U6", "ann", ["S1"], 1, "19:00:00", "21:00:00", "several_people"),
    ("U7", "ben", ["S3"], 1, "20:00:00", "22:00:00", "several_people"),
    ("U8", "ann", ["S1"], 2, "09:00:00", "12:00:00", "several_people_and_sessions"),
    ("U9", "ann", ["S2"], 2, "10:00:00", "11:00:00", "one_person_sessions"),
    ("U10", "ben", ["S3"], 2, "11:30:00", "13:00:00", "several_people"),
    ("U11", "ann", [], 3, "09:00:00", "10:00:00", "undetermined"),
    ("U12", "ann", ["S1"], 3, "09:30:00", "11:00:00", "undetermined"),
    # A known other session wins over an unknown one.
    ("U13", "ann", ["S1"], 4, "09:00:00", "12:00:00", "one_person_sessions"),
    ("U14", "ann", ["S2"], 4, "09:30:00", "10:00:00", "one_person_sessions"),
    ("U15", "ann", [], 4, "10:30:00", "11:00:00", "undetermined"),
    # Another person beside it, and the same person's from a session that
    # cannot be told.
    ("U16", "ann", ["S1"], 5, "09:00:00", "12:00:00", "undetermined"),
    ("U17", "ben", ["S3"], 5, "09:30:00", "10:00:00", "several_people"),
    ("U18", "ann", [], 5, "10:30:00", "11:00:00", "undetermined"),
    # Another person beside it, and the same session's other pull request.
    ("U19", "ann", ["S1"], 6, "09:00:00", "12:00:00", "several_people"),
    ("U20", "ann", ["S1"], 6, "09:30:00", "10:00:00", "one_session"),
    ("U21", "ben", ["S3"], 6, "10:30:00", "11:00:00", "several_people"),
    # A bot's pull request at work beside it is nobody's partner.
    ("U22", "ann", ["S1"], 7, "09:00:00", "10:00:00", "solo"),
    # An overlap of exactly the clock's grace is not enough; a second more is.
    ("U23", "ann", ["S1"], 8, "09:00:00", "10:00:00", "solo"),
    ("U24", "ann", ["S2"], 8, "09:59:00", "11:00:00", "solo"),
    ("U25", "ann", ["S3"], 8, "12:00:00", "13:00:00", "one_person_sessions"),
    ("U26", "ann", ["S4"], 8, "12:58:59", "14:00:00", "one_person_sessions"),
]


class Settings(unittest.TestCase):
    def test_the_rule_order_settles_every_case(self):
        units = {}
        for number, (name, login, sessions, day, start, end, _) in enumerate(SETTING_CASES, start=400):
            units[name] = labelled_unit(number, login, sessions, f"2026-10-{day:02d}T{start}Z",
                                        f"2026-10-{day:02d}T{end}Z")
        units["bot"] = labelled_unit(499, "dependabot[bot]", [], "2026-10-07T09:00:00Z", "2026-10-07T12:00:00Z",
                                     kind="Bot", ref="dependabot/x")
        everything = list(units.values())
        metrics.floor_starts(everything)
        partners = metrics.partners_of(everything, metrics.parse_time(NOW))
        found = {name: metrics.setting_of(unit, partners[unit.number]) for name, unit in units.items()}
        expected = {name: setting for name, *_, setting in SETTING_CASES} | {"bot": "automation"}
        self.assertEqual(found, expected)
        self.assertEqual(metrics.relation(units["U2"], units["U3"]), "same_session")
        self.assertEqual(metrics.relation(units["U8"], units["U9"]), "one_person_sessions")
        self.assertEqual(metrics.relation(units["U8"], units["U10"]), "several_people")
        self.assertEqual(metrics.relation(units["U11"], units["U12"]), "undetermined")


class Breakdown(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as folder:
            cls.code, cls.record, cls.text, cls.shown, cls.said, cls.opener = collect_world(folder)
        cls.calls = cls.opener.calls

    def test_the_world_sorts_every_setting_and_pair(self):
        self.assertEqual(self.code, 0)
        for key, block in WORLD_EXPECTED.items():
            self.assertEqual(self.record[key], block, key)
        self.assertEqual(self.record["counts"], WORLD_COUNTS)
        self.assertEqual(self.record["durations_seconds"], WORLD_DURATIONS)
        self.assertEqual(self.record["rates"], WORLD_RATES)
        units, window = world_units()
        partners = metrics.partners_of(units, window.end)
        self.assertEqual({unit.number: metrics.setting_of(unit, partners[unit.number]) for unit in units},
                         WORLD_SETTINGS)
        # 308's Sept 20 commit is set aside by the seven-day horizon.
        self.assertEqual(next(unit.start for unit in units if unit.number == 308),
                         metrics.parse_time("2026-10-07T09:00:00Z"))

    def test_the_breakdown_adds_up_to_the_counts(self):
        rows = self.record["by_setting"].values()
        self.assertEqual(sum(row["merged"] for row in rows), self.record["counts"]["merged"])
        self.assertEqual(sum(row["closed_unmerged"] for row in rows), self.record["counts"]["closed_unmerged"])
        # conflicts_seen keeps any author's mark (302, 307 and 312 by the
        # board, 308 by a person's paste); the breakdown takes an app's or a
        # bot's in the window. 313's mark of Sept 7 lies before the window,
        # yet still marks 313 conflicted and its onset.
        self.assertEqual((self.record["counts"]["conflicts_seen"], self.record["parallel"]["conflict_marks"]), (4, 3))

    def test_the_breakdown_reads_after_every_existing_key_and_the_files_last(self):
        # The 55 calls collect made before the breakdown, in the same order:
        # the listing, two for each of the 15 recent pull requests, 19
        # check-run lists, 3 details, the branches, the window's comments.
        # Then 314's commits; then the look-back's comments, since 313's and
        # 315's work began before the window; then the files; and last the
        # Actions runs' usage records: the listing, and for each of the two
        # records the API's redirect and the storage host's file.
        self.assertEqual(len(self.calls), 72)
        self.assertEqual((self.calls[54], self.opener.queries[54]["since"]),
                         (f"{API}/issues/comments", "2026-09-10T12:00:00Z"))
        self.assertEqual(self.calls[55], f"{API}/pulls/314/commits")
        self.assertEqual((self.calls[56], self.opener.queries[56]["since"]),
                         (f"{API}/issues/comments", "2026-08-11T12:00:00Z"))
        self.assertEqual(self.calls[57:67], [f"{API}/pulls/{n}/files"
                                             for n in (301, 302, 303, 304, 305, 306, 307, 313, 314, 315)])
        self.assertEqual(self.calls[67:], [f"{API}/actions/artifacts", f"{API}/actions/artifacts/9001/zip",
                                           "/usage/9001.zip", f"{API}/actions/artifacts/9002/zip", "/usage/9002.zip"])
        self.assertFalse([path for path in self.calls if re.search(r"/pulls/31[67]\b", path)])

    def test_files_are_read_last_and_left_null_under_the_reserve(self):
        with tempfile.TemporaryDirectory() as folder:
            code, record, _, shown, _, opener = collect_world(folder, remaining=360)
        self.assertEqual(code, 0)
        self.assertEqual(len(opener.calls), 60)
        self.assertEqual([path for path in opener.calls if path.endswith("/files")],
                         [f"{API}/pulls/{n}/files" for n in (301, 302, 303)])
        self.assertEqual(record["parallel"]["files_unread"], 7)
        for name in metrics.SETTINGS:
            self.assertEqual(record["by_setting"][name]["file_overlap"],
                             None if name in metrics.PERSON_SETTINGS else 0, name)
        for name in metrics.RELATIONS:
            for key in metrics.FILE_PAIR_KEYS:
                self.assertIsNone(record["pairs"][name][key], (name, key))
        expected = json.loads(json.dumps(WORLD_EXPECTED))
        expected["parallel"]["files_unread"] = 7
        metrics.null_file_counts(expected["by_setting"], expected["pairs"])
        for key, block in expected.items():
            self.assertEqual(record[key], block, key)
        self.assertTrue(shown.rstrip("\n").endswith(
            "in 60 calls; the changed files of 7 pull requests were left unread to keep the board's reserve, so the "
            "counts that need them are null; the Actions runs' usage records could not be listed, so only those "
            "read before count"), shown)

    def test_the_breakdown_gives_way_to_the_reserve_and_never_costs_an_existing_key(self):
        """The existing keys are measured from the reads collect made before
        the breakdown, in the same order; when a breakdown read other than
        the changed files would reach the board's reserve, the record is
        written with those keys alone, not broken out."""
        for spent in (55, 56):
            # Refused at 314's commits, then at the look-back's comments.
            with tempfile.TemporaryDirectory() as folder:
                code, record, text, shown, _, opener = collect_world(folder, remaining=metrics.RESERVE + spent)
            self.assertEqual(code, 0, spent)
            self.assertEqual(tuple(record), metrics.RECORD_KEYS[:-len(metrics.BREAKDOWN_KEYS)], spent)
            self.assertEqual((record["counts"], record["durations_seconds"], record["rates"]),
                             (WORLD_COUNTS, WORLD_DURATIONS, WORLD_RATES), spent)
            self.assertEqual(opener.calls, self.calls[:spent], spent)
            self.assertTrue(shown.rstrip("\n").endswith(
                f"in {spent} calls; the breakdown was left out to keep the board's reserve, so the record has no "
                "parallel, by_setting, pairs, economics or coordination"), shown)
            for secret in ("ann-secret", A1, "src/secret_"):
                self.assertNotIn(secret, text + shown)

    def test_a_failed_breakdown_read_leaves_the_breakdown_out_and_keeps_every_existing_key(self):
        """A read only the breakdown makes, which GitHub fails, here 314's
        commits answering 404, leaves the record a copy of the template from
        before the breakdown writes: every existing key, measured as before,
        and no parallel, by_setting or pairs."""
        routes = world_routes()
        del routes[f"{API}/pulls/314/commits"]
        with tempfile.TemporaryDirectory() as folder:
            code, record, text, shown, _, _ = collect_world(folder, routes=routes)
        self.assertEqual(code, 0)
        self.assertEqual(tuple(record), metrics.RECORD_KEYS[:-len(metrics.BREAKDOWN_KEYS)])
        self.assertEqual((record["counts"], record["durations_seconds"], record["rates"]),
                         (WORLD_COUNTS, WORLD_DURATIONS, WORLD_RATES))
        self.assertTrue(shown.rstrip("\n").endswith(
            "the breakdown was left out because GitHub failed one of its reads (HTTP 404), so the record has no "
            "parallel, by_setting, pairs, economics or coordination"), shown)
        for secret in ("ann-secret", A1, "src/secret_"):
            self.assertNotIn(secret, text + shown)

    def test_an_old_comment_edited_lately_changes_nothing(self):
        """GitHub's since is the last update, so a mark made before the
        look-back and edited since is listed, first, as GitHub lists them
        oldest first; it is left out by when it was made."""
        routes = world_routes()
        routes[f"{API}/issues/comments"] = [mark(313, "2026-08-01T00:00:00Z", "conflicting", "unknown"),
                                            *WORLD_COMMENTS]
        with tempfile.TemporaryDirectory() as folder:
            _, record, _, _, _, _ = collect_world(folder, routes=routes)
        for key, block in WORLD_EXPECTED.items():
            self.assertEqual(record[key], block, key)
        self.assertEqual(record["counts"], WORLD_COUNTS)

    def test_the_look_back_reads_commits_only_where_they_can_bear(self):
        """A look-back pull request's commits are read only when it is a
        person's and ended after the earliest start of the window's people's
        work, finished or open, taken after the branch floor: those without
        a route here would answer 404 and fail the run if they were read."""
        pulls = [
            # Listed in the window for a comment, but ended in the look-back:
            # its early start is no window work's.
            world_pull(604, "ben-secret", "2026-08-20T09:00:00Z", "2026-09-20T00:00:00Z", "claude/604",
                       merged="2026-09-01T00:00:00Z"),
            world_pull(703, "ben-secret", "2026-09-06T12:00:00Z", "2026-09-12T00:00:00Z", "claude/703",
                       merged="2026-09-12T00:00:00Z"),
            # A branch used again: its commits carry its predecessor's, so the
            # floor, which the listing alone gives, starts it at 701's merge.
            world_pull(702, "ann-secret", "2026-09-11T09:00:00Z", "2026-09-11T12:00:00Z", "claude/session-x",
                       merged="2026-09-11T12:00:00Z"),
            # In the look-back: a person's ended after that start, read.
            world_pull(707, "ben-secret", "2026-09-06T09:00:00Z", "2026-09-08T00:00:00Z", "claude/707",
                       merged="2026-09-08T00:00:00Z"),
            # A bot's ended after it, a person's ended before it, and the
            # predecessor, ended exactly at it: none read.
            world_pull(706, "dependabot[bot]", "2026-09-06T00:00:00Z", "2026-09-07T00:00:00Z", "dependabot/pip/z",
                       merged="2026-09-07T00:00:00Z", kind="Bot"),
            world_pull(701, "ann-secret", "2026-09-04T09:00:00Z", "2026-09-05T10:00:00Z", "claude/session-x",
                       merged="2026-09-05T10:00:00Z"),
            world_pull(705, "ben-secret", "2026-09-02T00:00:00Z", "2026-09-03T10:00:00Z", "claude/705",
                       merged="2026-09-03T10:00:00Z"),
            # Before the look-back: the listing stops here.
            world_pull(708, "ben-secret", "2026-07-20T00:00:00Z", "2026-08-01T00:00:00Z", "claude/708",
                       merged="2026-08-01T00:00:00Z"),
        ]
        commits = {604: [world_commit(604, 1, "2026-08-20T09:00:00Z")],
                   703: [world_commit(703, 1, "2026-09-06T12:00:00Z")],
                   702: [world_commit(702, 1, "2026-09-05T09:00:00Z", trailer(A1)),
                         world_commit(702, 2, "2026-09-11T10:00:00Z", trailer(A2))],
                   707: [world_commit(707, 1, "2026-09-06T09:00:00Z")]}
        routes = {f"{API}/pulls": pulls, f"{API}/branches": [], f"{API}/issues/comments": [],
                  **{f"{API}/pulls/{n}/commits": listed for n, listed in commits.items()},
                  **{f"{API}/pulls/{n}/reviews": [] for n in (604, 703, 702)},
                  **{f"{API}/commits/{commit_sha(702, i)}/check-runs": runs() for i in (1, 2)},
                  **{f"{API}/pulls/{n}/files": [] for n in (702, 703, 707)}}
        with tempfile.TemporaryDirectory() as folder:
            code, _, _, _, _, opener = collect_world(folder, routes=routes)
        self.assertEqual(code, 0)
        # The 11 calls before the breakdown (the listing, 604's two, 703's
        # two, 702's two and the runs of its commit made in the window and
        # of its first head, the branches, the comments), then 707's commits,
        # the look-back's comments, three changed-file lists and the usage
        # records' listing.
        self.assertEqual([path for path in opener.calls[11:] if path.endswith("/commits")],
                         [f"{API}/pulls/707/commits"])
        self.assertEqual(len(opener.calls), 17)

    def test_a_pair_counts_once_in_the_record_whose_window_holds_its_later_end(self):
        window = metrics.Window.ending(metrics.parse_time(NOW), 30)
        day = "2026-10-02T"
        recent = [labelled_unit(460, "ann", ["S1"], day + "09:00:00Z", day + "12:00:00Z"),
                  labelled_unit(461, "ann", ["S2"], day + "10:00:00Z", day + "13:00:00Z")]
        # Two of Ann's sessions at work together in the look-back, both ended
        # before the window: their pair is the earlier record's alone.
        back = [labelled_unit(462, "ann", ["S3"], "2026-08-19T09:00:00Z", "2026-08-20T09:00:00Z"),
                labelled_unit(463, "ann", ["S4"], "2026-08-19T12:00:00Z", "2026-08-21T09:00:00Z")]
        self.assertEqual(metrics.breakdown(recent + back, [], {}, 0, window)["pairs"],
                         metrics.breakdown(recent, [], {}, 0, window)["pairs"])
        earlier = metrics.Window.ending(metrics.parse_time("2026-09-01T00:00:00Z"), 30)
        self.assertEqual(metrics.breakdown(back, [], {}, 0, earlier)["pairs"]["one_person_sessions"]["pairs"], 1)

    def test_sessions_joined_through_a_third_pull_request_are_one_group(self):
        window = metrics.Window.ending(metrics.parse_time(NOW), 30)
        day = "2026-10-03T"
        units = [labelled_unit(470, "ann", ["A", "B"], day + "09:00:00Z", day + "12:00:00Z"),
                 labelled_unit(471, "ann", ["A"], day + "09:30:00Z", day + "12:00:00Z"),
                 labelled_unit(472, "ann", ["B"], day + "10:00:00Z", day + "12:00:00Z")]
        for order in permutations(units):
            found = metrics.breakdown(list(order), [], {}, 0, window)["parallel"]
            self.assertEqual((found["peak_parallel"], found["peak_sessions_one_person"]), (3, 1),
                             [unit.number for unit in order])

    def test_a_release_counts_from_the_first_commit_to_the_end(self):
        """The coordinator releases a claim with no commit for a day, which
        can come before the pull request opens."""
        window = metrics.Window.ending(metrics.parse_time(NOW), 30)
        day = "2026-10-04T"
        unit = labelled_unit(480, "ann", ["S1"], day + "10:00:00Z", day + "12:00:00Z", first_commit=day + "09:00:00Z")

        def released(at):
            release = {"issue_url": f"https://api.github.com{API}/issues/480", "created_at": day + at,
                       "body": metrics.RELEASE_MARKER + "\nReleased.", "user": user("ann-secret")}
            return metrics.breakdown([unit], [release], {}, 0, window)["by_setting"]["solo"]["released"]

        self.assertEqual([released(at) for at in ("08:59:00Z", "09:30:00Z", "12:00:00Z", "12:01:00Z")], [0, 1, 1, 0])

    def test_a_landing_is_a_merge_into_the_default_branch_from_another_branch(self):
        window = metrics.Window.ending(metrics.parse_time(NOW), 30)
        day = "2026-10-06T"
        ann = labelled_unit(710, "ann", ["S1"], day + "10:00:00Z", day + "14:00:00Z")
        # A merge into a release branch moves nothing the board marks.
        for into, landings in (("release/1.x", 0), ("main", 1)):
            ben = labelled_unit(711, "ben", ["S3"], day + "11:00:00Z", day + "12:00:00Z", into=into)
            found = metrics.breakdown([ann, ben], [], {}, 0, window)
            self.assertEqual((found["by_setting"]["several_people"]["landings_under"],
                              found["pairs"]["several_people"]["landings"]), (landings, landings), into)
        # A branch used again starts at its predecessor's merge, which
        # carries its own earlier work and is no landing for it; another
        # branch's merge before its opening is.
        day = "2026-10-07T"
        first = labelled_unit(712, "ann", ["S1"], day + "10:00:00Z", day + "12:00:00Z", ref="claude/session-x")
        again = labelled_unit(713, "ann", ["S1"], day + "13:00:00Z", day + "15:00:00Z", first_commit=day + "11:00:00Z",
                              ref="claude/session-x")
        other = labelled_unit(714, "ben", ["S3"], day + "12:15:00Z", day + "12:30:00Z")
        metrics.floor_starts([first, again, other])
        self.assertEqual(again.start, metrics.parse_time(day + "12:00:00Z"))
        found = metrics.breakdown([first, again, other], [], {}, 0, window)
        self.assertEqual(found["by_setting"]["several_people"]["landings_before_opening"], 1)
        # Another branch's merge at the very moment the work began counts.
        merged = labelled_unit(717, "ben", ["S3"], day + "08:00:00Z", day + "09:00:00Z")
        started = labelled_unit(718, "ann", ["S1"], day + "09:30:00Z", day + "10:00:00Z", first_commit=day + "09:00:00Z")
        found = metrics.breakdown([merged, started], [], {}, 0, window)
        self.assertEqual(found["by_setting"]["solo"]["landings_before_opening"], 1)
        # One branch's two pull requests at once, into main and into a
        # release branch: the merge into main is the other's own work.
        day = "2026-10-08T"
        to_main = labelled_unit(715, "ann", ["S1"], day + "10:00:00Z", day + "12:00:00Z", ref="claude/session-y")
        to_release = labelled_unit(716, "ann", ["S1"], day + "11:00:00Z", day + "13:00:00Z", ref="claude/session-y",
                                   into="release/1.x")
        found = metrics.breakdown([to_main, to_release], [], {}, 0, window)
        self.assertEqual((found["by_setting"]["one_session"]["landings_under"],
                          found["pairs"]["same_session"]["pairs"], found["pairs"]["same_session"]["landings"]),
                         (0, 1, 0))

    def test_a_pull_request_listed_twice_is_one_unit(self):
        """GitHub pages its listing by page number, so an update while it is
        read can push a pull request onto the next page a second time."""
        twice = world_pull(320, "ann-secret", "2026-10-02T09:00:00Z", "2026-10-02T12:00:00Z", "claude/520",
                           merged="2026-10-02T12:00:00Z")
        routes = {f"{API}/pulls": [twice], f"{API}/branches": [], f"{API}/issues/comments": [],
                  f"{API}/pulls/320/commits": [world_commit(320, 1, "2026-10-02T09:00:00Z", trailer(A1))],
                  f"{API}/pulls/320/reviews": [], f"{API}/commits/{commit_sha(320, 1)}/check-runs": runs(),
                  f"{API}/pulls/320/files": []}
        with tempfile.TemporaryDirectory() as folder:
            _, once, _, _, _, _ = collect_world(folder, routes=routes)
        routes[f"{API}/pulls"] = [twice, dict(twice)]
        with tempfile.TemporaryDirectory() as folder:
            _, record, _, _, _, _ = collect_world(folder, routes=routes)
        for key in ("parallel", "by_setting", "pairs"):
            self.assertEqual(record[key], once[key], key)
        self.assertEqual(record["by_setting"]["solo"]["pull_requests"], 1)
        # Listed twice in the look-back, 314 is one partner, and its commits
        # are read once.
        routes = world_routes()
        listing = routes[f"{API}/pulls"]
        at = next(index for index, pull_ in enumerate(listing) if pull_["number"] == 314)
        routes[f"{API}/pulls"] = listing[:at + 1] + [dict(listing[at])] + listing[at + 1:]
        with tempfile.TemporaryDirectory() as folder:
            _, record, _, _, _, opener = collect_world(folder, routes=routes)
        for key, block in WORLD_EXPECTED.items():
            self.assertEqual(record[key], block, key)
        self.assertEqual(opener.calls, self.calls)

    def test_nothing_of_the_world_reaches_the_file_or_the_log(self):
        for secret in ("ann-secret", "ben-secret", A1, A2, B1, TOKEN, "claude.ai/code", "src/secret_",
                       "docs/secret_b.md", "claude/session-ann2", "feature/ben-twelve", "dependabot/pip", "deadbee",
                       "0301abc", "Secret title", "Secret review words", "secret plan left"):
            for where, text in (("the file", self.text), ("stdout", self.shown), ("stderr", self.said)):
                self.assertNotIn(secret, text, (secret, where))
        numbers = set(range(301, 320)) | set(range(501, 518))
        self.assertFalse([value for value in breakdown_values(self.record) if value in numbers])
        self.assertEqual(len([value for value in self.record.values() if isinstance(value, str)]), 4)

    def test_a_burst_is_marked_against_its_last_merge(self):
        day = "2026-10-02T"
        p = labelled_unit(501, "ann", ["S1"], day + "11:00:00Z", day + "14:00:00Z")
        l1 = labelled_unit(502, "ben", ["S3"], day + "10:30:00Z", day + "12:00:00Z", first_commit=day + "10:00:00Z")
        l2 = labelled_unit(503, "ann", ["S2"], day + "10:45:00Z", day + "12:01:00Z", first_commit=day + "10:15:00Z")
        burst = [mark(501, day + "12:03:00Z", "conflicting", l2.merge_sha[:7])]
        window = metrics.Window.ending(metrics.parse_time(NOW), 30)
        found = metrics.breakdown([p, l1, l2], burst, {}, 0, window)

        def pick(row, *keys):
            return {key: row[key] for key in keys}

        settings = found["by_setting"]
        self.assertEqual(pick(settings["several_people_and_sessions"], "pull_requests", "conflicted", "partners",
                              "landings_under"),
                         {"pull_requests": 2, "conflicted": 1, "partners": 4, "landings_under": 3})
        self.assertEqual(pick(settings["several_people"], "pull_requests", "conflicted", "partners", "landings_under"),
                         {"pull_requests": 1, "conflicted": 0, "partners": 2, "landings_under": 0})
        self.assertEqual(pick(found["pairs"]["one_person_sessions"], "pairs", "landings", "conflict_onsets"),
                         {"pairs": 1, "landings": 1, "conflict_onsets": 1})
        self.assertEqual(pick(found["pairs"]["several_people"], "pairs", "landings", "conflict_onsets"),
                         {"pairs": 2, "landings": 2, "conflict_onsets": 0})
        self.assertEqual(pick(found["parallel"], "conflict_marks", "conflict_marks_unattributed"),
                         {"conflict_marks": 1, "conflict_marks_unattributed": 0})


FIXTURES = ROOT / "tests" / "fixtures"
REPLICA = LINK + "session_replica"
HISTORY_END = "2030-01-31T00:00:00Z"


def replica_commits(created, commits):
    """The commits of a history's row: [minutes after the opening, session
    label or None], each authored and committed then."""
    opened = metrics.parse_time(created)
    found = []
    for minutes, label in commits:
        when = metrics.iso(opened + timedelta(minutes=minutes))
        message = "Work." if label is None else f"Work.\n\nClaude-Session: {REPLICA}{label}"
        found.append({"sha": "0" * 40, "commit": {"author": {"date": when}, "committer": {"date": when},
                                                   "message": message}})
    return found


def replica_pull(number, ref, created, merged, closed, body=""):
    return {"number": number, "user": user("replica-person"), "state": "closed", "body": body,
            "created_at": created, "merged_at": merged, "closed_at": closed, "updated_at": closed,
            "head": {"ref": ref, "repo": {"full_name": REPO}}, "base": base(), "merge_commit_sha": merge_sha(number)}


def replica_body(labels):
    """A description naming each session as a cloud session's does: the link
    alone on a line, and the footer."""
    return "".join(f"{REPLICA}{label}\n\n---\n_Generated by [Claude Code]({REPLICA}{label})_\n" for label in labels)


def history_breakdown(units):
    metrics.floor_starts(units)
    return metrics.breakdown(units, [], {}, 0, metrics.Window.ending(metrics.parse_time(HISTORY_END), 30))


def relay_history():
    """The template's own 37 merged pull requests, anonymised: one person,
    sessions handing work on to each other."""
    rows = json.loads((FIXTURES / "metrics_history_relay.json").read_text(encoding="ascii"))
    return history_breakdown([metrics.unit_of(replica_pull(number, ref, created, merged, merged),
                                              replica_commits(created, commits), True)
                              for number, ref, created, merged, commits in rows])


def parallel_history(bodies=True, own_branches=False):
    """Another repository's 45 pull requests, anonymised: one person running
    up to three sessions at once."""
    rows = json.loads((FIXTURES / "metrics_history_parallel.json").read_text(encoding="ascii"))
    units = []
    for number, branch, created, merged, closed, labels, commits in rows:
        ref = f"claude/session-only-{number}" if own_branches else f"claude/session-{branch}"
        pull_ = replica_pull(number, ref, created, merged, closed, replica_body(labels) if bodies else "")
        units.append(metrics.unit_of(pull_, replica_commits(created, commits), True))
    return history_breakdown(units)


def column(block, key):
    """One count of every setting or relation that has it, zeros left out."""
    return {name: row[key] for name, row in block.items() if row[key]}


def pick_all(block, keys):
    return {name: {key: row[key] for key in keys} for name, row in block.items() if row["pairs"]}


class Histories(unittest.TestCase):
    """Two real histories, anonymised (times moved to 2030, numbers
    renumbered, sessions and branches made labels), give the composition
    measured on the repositories themselves."""

    def test_the_relay_history_gives_the_measured_composition(self):
        found = relay_history()
        settings = found["by_setting"]
        self.assertEqual(column(settings, "pull_requests"), {"solo": 21, "one_session": 14, "one_person_sessions": 2})
        self.assertEqual(column(settings, "merged"), column(settings, "pull_requests"))
        self.assertEqual(column(settings, "claim_branches"), {"solo": 1, "one_session": 7})
        self.assertEqual(column(settings, "partners"), {"one_session": 26, "one_person_sessions": 2})
        self.assertEqual(column(settings, "work_seconds"),
                         {"solo": 55384, "one_session": 220416, "one_person_sessions": 12007})
        self.assertEqual(column(settings, "landings_under"), {"one_session": 13})
        self.assertEqual(column(settings, "landings_before_opening"), {"one_session": 1, "one_person_sessions": 1})
        self.assertEqual(pick_all(found["pairs"], ("pairs", "both_active", "landings")),
                         {"same_session": {"pairs": 13, "both_active": 5, "landings": 13},
                          "one_person_sessions": {"pairs": 1, "both_active": 0, "landings": 0}})
        self.assertEqual({key: found["parallel"][key] for key in metrics.PARALLEL_KEYS[:10]},
                         {"people": 1, "sessions": 4, "sessions_per_person_max": 4, "pull_requests_with_session": 37,
                          "pull_requests_without_session": 0, "pull_requests_multi_session": 4,
                          "sessions_across_people": 0, "peak_parallel": 3, "peak_parallel_people": 1,
                          "peak_sessions_one_person": 2})

    def test_the_parallel_history_gives_the_measured_composition(self):
        found = parallel_history()
        settings = found["by_setting"]
        self.assertEqual(column(settings, "pull_requests"), {"solo": 26, "one_session": 12, "one_person_sessions": 7})
        self.assertEqual(column(settings, "merged"), {"solo": 26, "one_session": 11, "one_person_sessions": 7})
        self.assertEqual(column(settings, "closed_unmerged"), {"one_session": 1})
        self.assertEqual(column(settings, "partners"), {"one_session": 20, "one_person_sessions": 10})
        self.assertEqual(column(settings, "work_seconds"),
                         {"solo": 141694, "one_session": 97771, "one_person_sessions": 14730})
        self.assertEqual(column(settings, "landings_under"), {"one_session": 5, "one_person_sessions": 5})
        # Two of one_session's pull requests reuse a session's branch, whose
        # earlier pull request's merge, where the floor starts them, is their
        # own work landing and no landing before their opening.
        self.assertEqual(column(settings, "landings_before_opening"), {"one_session": 6})
        self.assertEqual(pick_all(found["pairs"], ("pairs", "both_active", "landings")),
                         {"same_session": {"pairs": 10, "both_active": 5, "landings": 5},
                          "one_person_sessions": {"pairs": 5, "both_active": 2, "landings": 5}})
        self.assertEqual({key: found["parallel"][key] for key in metrics.PARALLEL_KEYS[:10]},
                         {"people": 1, "sessions": 15, "sessions_per_person_max": 15,
                          "pull_requests_with_session": 44, "pull_requests_without_session": 1,
                          "pull_requests_multi_session": 4, "sessions_across_people": 0, "peak_parallel": 3,
                          "peak_parallel_people": 1, "peak_sessions_one_person": 3})

    def test_the_descriptions_and_the_branch_floor_each_move_the_parallel_history(self):
        # Without the descriptions' lines, the pull requests whose commits
        # name no session fall into undetermined.
        found = parallel_history(bodies=False)
        self.assertEqual(column(found["by_setting"], "pull_requests"),
                         {"solo": 26, "one_session": 5, "one_person_sessions": 7, "undetermined": 7})
        self.assertEqual(pick_all(found["pairs"], ("pairs", "both_active")),
                         {"same_session": {"pairs": 4, "both_active": 3},
                          "one_person_sessions": {"pairs": 5, "both_active": 2},
                          "undetermined": {"pairs": 6, "both_active": 2}})
        self.assertEqual({key: found["parallel"][key] for key in ("sessions", "pull_requests_with_session",
                                                                    "pull_requests_without_session")},
                         {"sessions": 14, "pull_requests_with_session": 42, "pull_requests_without_session": 3})
        # Without the branch floor, a successor's start reaches back over
        # commits its predecessor landed.
        found = parallel_history(own_branches=True)
        self.assertEqual(column(found["by_setting"], "pull_requests"),
                         {"solo": 26, "one_session": 10, "one_person_sessions": 9})
        self.assertEqual(pick_all(found["pairs"], ("pairs", "both_active")),
                         {"same_session": {"pairs": 13, "both_active": 9},
                          "one_person_sessions": {"pairs": 8, "both_active": 5}})


# --- the judge ----------------------------------------------------------------

JUDGE_PULLS = [
    {"number": 201, "body": "Plan: I will change the parser. @lisa-secret can you confirm the format?",
     "state": "closed", "created_at": "2026-10-01T10:00:00Z", "updated_at": "2026-10-02T00:00:00Z",
     "merged_at": "2026-10-02T00:00:00Z", "closed_at": "2026-10-02T00:00:00Z", "user": user("mona-secret"),
     "title": "Secret plan for widgets", "head": {"ref": "claude/4711", "sha": SHA["a"]}},
    {"number": 202, "body": "", "state": "open", "created_at": "2026-10-03T10:00:00Z",
     "updated_at": "2026-10-01T00:00:00Z", "user": user("mona-secret"), "title": "Fix the login page",
     "head": {"ref": "claude/4712", "sha": SHA["b"]}},
]
MONA_SESSION = "session_01MonaSecretSession"


def session_commit(sha, authored):
    """A commit as /pulls/{n}/commits lists it, ending with the trailer a
    Claude Code cloud session writes."""
    return {"sha": sha, "commit": {"author": {"date": authored}, "committer": {"date": authored},
                                   "message": f"Plan.\n\nClaude-Session: https://claude.ai/code/{MONA_SESSION}"}}


GH_ROUTES = {
    f"repos/{REPO}/pulls": JUDGE_PULLS,
    # 201 works from Oct 1 09:00 to its merge on Oct 2, 202 from Oct 3 09:00,
    # in the same session: one after the other, so 201 is solo.
    f"repos/{REPO}/pulls/201/commits": [session_commit(SHA["a"], "2026-10-01T09:00:00Z")],
    f"repos/{REPO}/pulls/202/commits": [session_commit(SHA["b"], "2026-10-03T09:00:00Z")],
    f"repos/{REPO}/issues/201/comments": [
        {"user": user("lisa-secret"), "created_at": "2026-10-01T11:00:00Z", "body": "Sounds good"},
        {"user": user("github-actions[bot]", "Bot"), "created_at": "2026-10-01T12:00:00Z", "body": BEHIND},
        {"user": user("github-actions[bot]", "Bot"), "created_at": "2026-10-01T12:30:00Z",
         "body": metrics.board.IDLE_MARKER + "\n" + metrics.board.IDLE_TEXT},
        {"user": user("lisa-secret"), "created_at": "2026-10-01T12:40:00Z",
         "body": metrics.RELEASE_MARKER + "\nReleased: no commit for a day."}],
    f"repos/{REPO}/pulls/201/comments": [
        {"user": user("lisa-secret"), "created_at": "2026-10-01T13:00:00Z", "body": "Rename src/secret_module.py",
         "path": "src/secret_module.py"}],
    f"repos/{REPO}/pulls/201/reviews": [
        {"user": user("lisa-secret"), "state": "APPROVED", "submitted_at": "2026-10-01T14:00:00Z", "body": ""}],
    f"repos/{REPO}/issues/202/comments": [],
    f"repos/{REPO}/pulls/202/comments": [],
    f"repos/{REPO}/pulls/202/reviews": [],
}


class FakeGh:
    """Stands in for subprocess.run for gh: answers gh api by path, the
    query aside, and gh repo view with the repository."""

    def __init__(self, routes=GH_ROUTES):
        self.routes, self.calls = routes, []

    def __call__(self, args, **kwargs):
        self.calls.append(args)
        if args[1:3] == ["repo", "view"]:
            return subprocess.CompletedProcess(args, 0, REPO + "\n", "")
        path = args[-1].split("?", 1)[0]
        if path not in self.routes:
            return subprocess.CompletedProcess(args, 1, "", f"no route for {path}")
        return subprocess.CompletedProcess(args, 0, json.dumps(self.routes[path]), "")


class FakeClaude:
    """Stands in for subprocess.run for claude: answers with each reply in
    turn, in claude -p's JSON result, and keeps what it was given, the
    system prompt file's text and the folder's listing among it, both read
    now because the folder is gone once the call returns."""

    def __init__(self, *replies):
        self.replies, self.calls, self.prompts, self.folders = list(replies), [], [], []

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        self.prompts.append(Path(command[command.index("--system-prompt-file") + 1]).read_text(encoding="utf-8"))
        self.folders.append(sorted(os.listdir(kwargs["cwd"])))
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        body = {"type": "result", "subtype": "success", "is_error": False, "result": reply}
        return subprocess.CompletedProcess(command, 0, json.dumps(body), "")


def refuse_every_call(*args, **kwargs):
    raise AssertionError(f"called: {args}")


def found(name):
    return f"/usr/bin/{name}"


def origin_at(url):
    """A git whose origin has this URL, and which refuses every other
    call: the origin check must cost nothing else."""
    def git(*args, input=None):
        if args[:2] == ("remote", "get-url"):
            return url + "\n"
        raise AssertionError(f"git called: {args}")
    return git


def run_judge(folder, gh, claude_run, extra=(), environ=None, which=found, git=refuse_every_call):
    out = Path(folder) / "JUDGE.json"
    args = metrics.parse_args(["judge", "--now", NOW, "--out", str(out), *extra])
    shown, said = io.StringIO(), io.StringIO()
    with redirect_stderr(said):
        code = metrics.judge(args, environ or {}, metrics.Gh(run=gh), metrics.LocalClaude(args.model, run=claude_run),
                             which=which, git=git, out=shown)
    return code, out, shown.getvalue(), said.getvalue()


class Judge(unittest.TestCase):
    def test_a_dry_run_sends_nothing_writes_nothing_and_shows_both(self):
        with tempfile.TemporaryDirectory() as folder:
            code, out, shown, _ = run_judge(folder, FakeGh(), refuse_every_call, ["--dry-run", "--repo", REPO])
            self.assertEqual(code, 0)
            self.assertFalse(out.exists())
        self.assertIn(metrics.APPF_PROMPT, shown)
        self.assertIn("[1] 2026-10-01T10:00:00Z A -> all: (description) Plan: I will change the parser. "
                      "@B can you confirm the format?", shown)
        self.assertIn("B -> all: Sounds good", shown)
        self.assertIn("B -> all: (review: approved)", shown)
        for private in ("mona-secret", "lisa-secret", "github-actions", MONA_SESSION):
            self.assertNotIn(private, shown)
        self.assertIn("judge: 1 of them ended in the window, by work setting: solo 1, one_session 0, "
                      "one_person_sessions 0, several_people 0, several_people_and_sessions 0, undetermined 0, "
                      "workflow_agents 0, automation 0", shown)
        record = json.loads(shown.split("(its counts are the model's to fill) ---\n", 1)[1])
        self.assertEqual(record["conversations"], 1)
        self.assertEqual(set(record["counts"].values()), {0})
        self.assertEqual(record["by_setting"]["solo"], {"pull_requests": 1, "conversations": 1, "multi_speaker": 1,
                                                        "counts": zeros(metrics.APPF_CODES)})
        self.assertEqual((record["multi_speaker"], record["limit"]), (1, None))
        self.assertIn(f"--system-prompt-file '<that folder>/{metrics.PROMPT_FILE}'", shown)
        self.assertNotIn("ANTHROPIC_BASE_URL", shown)

    def test_the_protocols_own_comments_stay_out_of_the_conversation(self):
        with tempfile.TemporaryDirectory() as folder:
            _, _, shown, _ = run_judge(folder, FakeGh(), refuse_every_call, ["--dry-run", "--repo", REPO])
        self.assertIn("Conversation of a pull request: 4 messages", shown)
        for left_out in ("sdlc-board: main-moved", "sdlc-board: idle", metrics.board.IDLE_TEXT,
                         metrics.RELEASE_MARKER, "Released: no commit"):
            self.assertNotIn(left_out, shown, left_out)
        self.assertIn("B -> all: Sounds good", shown)

    def test_a_dry_run_names_a_base_url_it_drops(self):
        with tempfile.TemporaryDirectory() as folder:
            _, _, shown, _ = run_judge(folder, FakeGh(), refuse_every_call, ["--dry-run", "--repo", REPO],
                                       environ={"ANTHROPIC_BASE_URL": "https://gateway.example.invalid"})
        self.assertIn("ANTHROPIC_BASE_URL is set here and is dropped", shown)
        self.assertNotIn("gateway.example.invalid", shown)

    def test_it_refuses_while_an_api_key_is_set_and_calls_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            code, out, _, said = run_judge(folder, refuse_every_call, refuse_every_call,
                                           environ={"ANTHROPIC_API_KEY": "set"})
            self.assertFalse(out.exists())
        self.assertEqual(code, 1)
        self.assertIn("unset ANTHROPIC_API_KEY", said)

    def test_it_refuses_while_another_way_of_billing_is_set_and_calls_nothing(self):
        for name in ("ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX",
                     "CLAUDE_CODE_USE_FOUNDRY"):
            with tempfile.TemporaryDirectory() as folder:
                code, out, _, said = run_judge(folder, refuse_every_call, refuse_every_call, environ={name: "1"})
                self.assertFalse(out.exists(), name)
            self.assertEqual(code, 1, name)
            self.assertIn(f"{name} is set", said)
            self.assertIn(f"unset {name}", said)
            self.assertIn("never does", said)

    def test_a_base_url_alone_is_dropped_not_refused(self):
        self.assertIsNone(metrics.judge_refusal({"ANTHROPIC_BASE_URL": "https://gateway.example.invalid"}, found))
        kept = metrics.judge_environment({name: "set" for name in metrics.DROPPED_VARIABLES} | {"HOME": "/h"})
        self.assertEqual(kept, {"HOME": "/h"})

    def test_a_model_is_a_plain_name_of_the_shape_the_collector_keeps(self):
        for name in ("claude-sonnet-5-5", "opus", "claude-opus-4-1-20250805", "claude-sonnet-4-5[1m]", "a.b_c"):
            self.assertEqual(metrics.parse_args(["judge", "--model", name]).model, name, name)
        for name in ("arn:aws:bedrock:us-east-1:123456789012:inference-profile/x", "a/b", "-x", "", "x" * 65,
                     "sonnet [1m]", "sonnet[1M]"):
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit, msg=name):
                metrics.parse_args(["judge", "--model", name])

    def test_it_refuses_without_claude_or_gh(self):
        for missing in ("claude", "gh"):
            with tempfile.TemporaryDirectory() as folder:
                which = partial(lambda gone, name: None if name == gone else found(name), missing)
                code, _, _, said = run_judge(folder, refuse_every_call, refuse_every_call, which=which)
            self.assertEqual(code, 1)
            self.assertIn(f"judge: {missing} is not on PATH", said)

    def test_it_keeps_counts_only_whatever_the_reply_carries(self):
        reply = json.dumps({"codes": ["c1A", "C4b"], "evidence": ["Sounds good"],
                            "issue": {"description": "secret words of the judge"}})
        claude, gh = FakeClaude("Here it is:\n" + reply), FakeGh()
        with tempfile.TemporaryDirectory() as folder:
            code, out, _, _ = run_judge(folder, gh, claude, ["--repo", REPO, "--model", "claude-test"])
            text = out.read_text()
        self.assertEqual(code, 0)
        record = json.loads(text)
        self.assertEqual(list(record), list(metrics.JUDGE_KEYS))
        self.assertEqual(record["schema"], "sdlc-judge/1")
        self.assertEqual((record["model"], record["prompt_variant"], record["conversations"]),
                         ("claude-test", "appF-7", 1))
        self.assertEqual(record["counts"], {"C1a": 1, "C1b": 0, "C2": 0, "C3a": 0, "C3b": 0, "C4a": 0, "C4b": 0})
        self.assertEqual(record["groups"], {"unresponsiveness": 1, "hallucination": 0, "repetition": 0})
        self.assertEqual((record["window_days"], record["limit"], record["multi_speaker"]), (30, None, 1))
        self.assertEqual(record["by_setting"]["solo"], {"pull_requests": 1, "conversations": 1, "multi_speaker": 1,
                                                        "counts": dict(zeros(metrics.APPF_CODES), C1a=1)})
        for name in metrics.SETTINGS[1:]:
            self.assertEqual(record["by_setting"][name], metrics.empty_judge_settings()[name], name)
        for secret in PRIVATE:
            self.assertNotIn(secret, text, secret)
        # The listing, three reads for each of the two conversations, and
        # the two commit lists that sort them into settings.
        self.assertEqual(len(gh.calls), 9)

    def test_the_conversation_goes_to_one_local_claude_on_stdin_and_nowhere_else(self):
        claude = FakeClaude('{"codes": []}')
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
            run_judge(folder, FakeGh(), claude, ["--repo", REPO])
        self.assertEqual(len(claude.calls), 1)
        command, kwargs = claude.calls[0]
        self.assertEqual(command[:4], [found("claude"), "-p", "--output-format", "json"])
        self.assertNotIn("--system-prompt", command)
        self.assertEqual(claude.prompts, [metrics.APPF_PROMPT])
        self.assertEqual(claude.folders, [[metrics.PROMPT_FILE]])
        self.assertEqual(command[command.index("--tools") + 1], "")
        self.assertEqual(command[command.index("--setting-sources") + 1], "")
        self.assertIn("A -> all: (description)", kwargs["input"])
        self.assertNotIn("lisa-secret", kwargs["input"])
        self.assertNotEqual(Path(kwargs["cwd"]).resolve(), ROOT)
        self.assertNotIn("ANTHROPIC_API_KEY", kwargs["env"])

    def test_nothing_that_bills_or_redirects_reaches_claude(self):
        claude = FakeClaude('{"codes": []}')
        shell = {name: "set" for name in metrics.DROPPED_VARIABLES} | {"HOME": "/home/maintainer"}
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, shell):
            run_judge(folder, FakeGh(), claude, ["--repo", REPO])
        _, kwargs = claude.calls[0]
        self.assertEqual(kwargs["env"]["HOME"], "/home/maintainer")
        for name in metrics.DROPPED_VARIABLES:
            self.assertNotIn(name, kwargs["env"])

    def test_claudes_own_reason_is_shown_when_it_fails(self):
        body = {"type": "result", "subtype": "success", "is_error": True, "result": "Not logged in. Please run /login"}
        done = subprocess.CompletedProcess(["claude"], 0, json.dumps(body), "")
        with self.assertRaises(metrics.JudgeError) as caught:
            metrics.claude_result(done)
        self.assertIn("claude failed (success; Not logged in. Please run /login); nothing is written",
                      str(caught.exception))
        body = {"type": "result", "subtype": "error_during_execution", "is_error": True, "errors": ["usage limit"]}
        done = subprocess.CompletedProcess(["claude"], 1, json.dumps(body), "a line on stderr\n")
        with self.assertRaises(metrics.JudgeError) as caught:
            metrics.claude_result(done)
        self.assertIn("error_during_execution; usage limit; a line on stderr", str(caught.exception))

    def test_a_reply_that_is_not_json_is_asked_once_more_then_left_out(self):
        claude = FakeClaude("I think it is C1a.")
        with tempfile.TemporaryDirectory() as folder:
            code, out, _, said = run_judge(folder, FakeGh(), claude, ["--repo", REPO])
            record = json.loads(out.read_text())
        self.assertEqual((code, len(claude.calls), record["conversations"]), (0, 2, 0))
        self.assertEqual(set(record["counts"].values()), {0})
        self.assertEqual(record["by_setting"]["solo"], {"pull_requests": 1, "conversations": 0, "multi_speaker": 0,
                                                        "counts": zeros(metrics.APPF_CODES)})
        self.assertEqual(record["multi_speaker"], 0)
        self.assertIn("left out", said)

    def test_a_reply_names_at_most_one_code_of_the_taxonomy(self):
        read = metrics.reply_object
        self.assertEqual(metrics.reply_code(read('{"codes": ["C9", "C2", "C3a"]}')), "C2")
        self.assertEqual(metrics.reply_code(read('```json\n{"codes": ["C4b"]}\n```')), "C4b")
        self.assertIsNone(metrics.reply_code(read('{"codes": ["C1"]}')))
        self.assertIsNone(metrics.reply_code(read('{"codes": "C1a"}')))
        self.assertIsNone(metrics.reply_code(read('{"issue": {"category": "C1a"}}')))
        self.assertIsNone(read("no braces here"))

    def test_the_prompt_is_app_f_with_the_codes_and_names_of_coordbench(self):
        self.assertEqual(metrics.APPF_CODES, ("C1a", "C1b", "C2", "C3a", "C3b", "C4a", "C4b"))
        for code in metrics.APPF_CODES:
            self.assertIn(f"- {code} {metrics.APPF_NAMES[code]}\n", metrics.APPF_PROMPT)
        self.assertEqual({metrics.APPF_GROUPS[code] for code in metrics.APPF_CODES}, set(metrics.GROUPS))
        self.assertTrue(metrics.APPF_PROMPT.startswith("You are a careful reviewer of two agent collaboration"))
        self.assertIn('{"codes": ["<category id>"]}', metrics.APPF_PROMPT)

    def test_speakers_are_lettered_and_long_conversations_cut(self):
        self.assertEqual([metrics.letters(i) for i in (0, 1, 25, 26, 27)], ["A", "B", "Z", "AA", "AB"])
        long_text = "x" * metrics.CONVERSATION_LIMIT * 2
        cut = metrics.bounded(long_text)
        self.assertLess(len(cut), metrics.CONVERSATION_LIMIT + 1000)
        self.assertTrue(cut.startswith("x" * metrics.CONVERSATION_KEEP))
        self.assertIn("left out here", cut)
        self.assertEqual(metrics.bounded("short"), "short")


def without_prompt_folder(command):
    """claude's command with the temporary folder of its prompt file left
    out, since that folder is new on every call."""
    at = command.index("--system-prompt-file") + 1
    return command[:at] + ["<prompt file>"] + command[at + 1:]


class JudgeBySetting(unittest.TestCase):
    def judged(self, routes, extra=()):
        claude, gh = FakeClaude(json.dumps({"codes": ["c1A", "C4b"]})), FakeGh(routes)
        with tempfile.TemporaryDirectory() as folder:
            code, out, _, _ = run_judge(folder, gh, claude, ["--repo", REPO, *extra])
            self.assertEqual(code, 0)
            return json.loads(out.read_text()), claude, gh

    def test_the_setting_never_reaches_the_model(self):
        apart, apart_claude, _ = self.judged(GH_ROUTES)
        # 202's first commit moved to Oct 1 12:00 puts it at work beside 201,
        # in the same session.
        beside_routes = dict(GH_ROUTES, **{f"repos/{REPO}/pulls/202/commits": [
            session_commit(SHA["b"], "2026-10-01T12:00:00Z")]})
        beside, beside_claude, _ = self.judged(beside_routes)
        self.assertEqual(beside["by_setting"]["one_session"], apart["by_setting"]["solo"])
        self.assertEqual(beside["by_setting"]["solo"], metrics.empty_judge_settings()["solo"])
        self.assertEqual([kwargs["input"] for _, kwargs in beside_claude.calls],
                         [kwargs["input"] for _, kwargs in apart_claude.calls])
        self.assertEqual(beside_claude.prompts, apart_claude.prompts)
        self.assertEqual([without_prompt_folder(command) for command, _ in beside_claude.calls],
                         [without_prompt_folder(command) for command, _ in apart_claude.calls])

    def test_a_limit_judges_fewer_and_still_sorts_every_listed_pull_request(self):
        record, _, gh = self.judged(GH_ROUTES, ["--limit", "1"])
        self.assertEqual([call[-1].split("?", 1)[0] for call in gh.calls],
                         [f"repos/{REPO}/{path}" for path in ("pulls", "issues/201/comments", "pulls/201/comments",
                                                              "pulls/201/reviews", "pulls/201/commits",
                                                              "pulls/202/commits")])
        self.assertEqual(record["limit"], 1)
        self.assertEqual(record["by_setting"]["solo"]["pull_requests"], 1)

    def test_a_limit_that_left_nothing_unjudged_is_written_as_null(self):
        """Analyses leave out a record whose limit is set, since it judged
        only the newest pull requests; a limit that cut nothing is none."""
        for limit in ("2", "5"):
            record, _, _ = self.judged(GH_ROUTES, ["--limit", limit])
            self.assertIsNone(record["limit"], limit)
            self.assertEqual(record, self.judged(GH_ROUTES)[0], limit)

    def test_a_pull_request_listed_twice_is_judged_and_sorted_once(self):
        """GitHub pages its listing by page number, so an update while it is
        read can push a pull request onto the next page a second time."""
        twice = {**GH_ROUTES, f"repos/{REPO}/pulls": [JUDGE_PULLS[0], dict(JUDGE_PULLS[0]), JUDGE_PULLS[1]]}
        record, claude, gh = self.judged(twice)
        once, once_claude, once_gh = self.judged(GH_ROUTES)
        self.assertEqual(record, once)
        self.assertEqual((len(claude.calls), len(gh.calls)), (len(once_claude.calls), len(once_gh.calls)))

    def test_a_parked_pull_request_is_beside_nobody(self):
        """Open since before the window, with no commit in it, and changed in
        it only by the board's comments: beside nobody, so 201 stays solo."""
        parked = {"number": 203, "body": "", "state": "open", "created_at": "2026-09-01T00:00:00Z",
                  "updated_at": "2026-10-05T00:00:00Z", "user": user("mona-secret"),
                  "title": "Secret plan for widgets", "head": {"ref": "claude/4713", "sha": SHA["c"]}}
        routes = {**GH_ROUTES, f"repos/{REPO}/pulls": [parked, *JUDGE_PULLS],
                  f"repos/{REPO}/pulls/203/commits": [session_commit(SHA["c"], "2026-09-01T00:00:00Z")],
                  f"repos/{REPO}/issues/203/comments": [], f"repos/{REPO}/pulls/203/comments": [],
                  f"repos/{REPO}/pulls/203/reviews": []}
        record, _, _ = self.judged(routes)
        self.assertEqual(record["by_setting"], self.judged(GH_ROUTES)[0]["by_setting"])

    def test_push_takes_numbers_alone_under_the_keys_the_breakdown_added(self):
        """The branch metrics is as public as the repository, so a file with
        words under the new keys is refused as one the judge did not write."""
        legacy = {"schema": "sdlc-judge/1", "generated_at": NOW, "model": "claude-sonnet-5-5",
                  "prompt_variant": "appF-7", "conversations": 1, "counts": zeros(metrics.APPF_CODES),
                  "groups": zeros(metrics.GROUPS)}

        def current(**changes):
            return dict(legacy, window_days=30, limit=None, multi_speaker=0,
                        by_setting=metrics.empty_judge_settings()) | changes

        def rows(change):
            settings = metrics.empty_judge_settings()
            change(settings)
            return settings

        refused = [
            current(by_setting=rows(lambda s: s.update({"ann-secret": s.pop("solo")}))),
            current(by_setting=dict(reversed(metrics.empty_judge_settings().items()))),
            current(by_setting=rows(lambda s: s["solo"].update(title="Secret title"))),
            current(by_setting=rows(lambda s: s["solo"]["counts"].update(C9=1))),
            current(by_setting=rows(lambda s: s["solo"]["counts"].update(C1a="secret plan"))),
            current(by_setting=rows(lambda s: s["solo"].update(pull_requests=True))),
            current(by_setting=rows(lambda s: s.update(solo="secret plan"))),
            current(by_setting=list(metrics.SETTINGS)),
            current(window_days="ann-secret's thirty days"),
            current(multi_speaker=1.5),
            current(limit={"why": "secret plan"}),
            current(limit=True),
        ]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "JUDGE.json"
            for record in refused:
                path.write_text(json.dumps(record))
                with self.assertRaises(metrics.JudgeError, msg=record) as caught:
                    metrics.judge_file(path)
                self.assertIn("not a JUDGE.json the judge wrote", str(caught.exception))
            for record in (legacy, current(), current(limit=20)):
                path.write_text(json.dumps(record))
                self.assertEqual(metrics.judge_file(path), record)

    def test_push_takes_a_file_judged_before_the_breakdown(self):
        legacy = {"schema": "sdlc-judge/1", "generated_at": NOW, "model": "claude-sonnet-5-5",
                  "prompt_variant": "appF-7", "conversations": 1, "counts": zeros(metrics.APPF_CODES),
                  "groups": zeros(metrics.GROUPS)}
        current = dict(legacy, window_days=30, limit=None, multi_speaker=0, by_setting=metrics.empty_judge_settings())
        self.assertEqual((tuple(legacy), tuple(current)), (metrics.LEGACY_JUDGE_KEYS, metrics.JUDGE_KEYS))
        for record in (legacy, current):
            with tempfile.TemporaryDirectory() as folder:
                origin, _ = seeded_origin(folder, {"METRICS.json": '{"schema": "sdlc-metrics/1"}\n'}, ORIGIN_NAME)
                clone = clone_of(folder, origin, "clone")
                path = Path(folder) / "JUDGE.json"
                path.write_text(json.dumps(record, indent=2) + "\n")
                code, shown, _ = run_push(folder, refuse_every_call, ["--repo", REPO], git=partial(run_in, clone))
                self.assertEqual(code, 0, list(record))
                self.assertIn("pushed to metrics as", shown)
                self.assertEqual(git(origin, "show", "metrics:JUDGE.json") + "\n", path.read_text())
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "JUDGE.json"
            for text in ('{"schema": "sdlc-judge/1"}\n', "not json", json.dumps(dict(current, repository=REPO))):
                path.write_text(text)
                with self.assertRaises(metrics.JudgeError, msg=text) as caught:
                    run_push(folder, refuse_every_call, ["--repo", REPO])
                self.assertIn("not a JUDGE.json the judge wrote", str(caught.exception))


def git(cwd, *args):
    done = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True,
                          env={**os.environ, **GIT_ENV})
    if done.returncode != 0:
        raise AssertionError(f"git {args}: {done.stderr}")
    return done.stdout.strip()


def seeded_origin(folder, files, name="origin.git"):
    """A bare origin whose branch metrics is one commit holding files."""
    origin, seed = Path(folder) / name, Path(folder) / "seed"
    git(folder, "init", "--quiet", "--bare", str(origin))
    git(folder, "init", "--quiet", str(seed))
    entries = []
    for name, text in files.items():
        path = Path(folder) / name
        path.write_text(text)
        entries.append(f"100644 blob {git(seed, 'hash-object', '-w', str(path))}\t{name}")
    tree = subprocess.run(["git", "-C", str(seed), "mktree"], input="\n".join(entries) + "\n", capture_output=True,
                          text=True, check=True).stdout.strip()
    sha = git(seed, "commit-tree", tree, "-m", "Metrics")
    git(seed, "push", "--quiet", str(origin), f"{sha}:refs/heads/metrics")
    return origin, sha


def clone_of(folder, origin, name):
    clone = Path(folder) / name
    git(folder, "init", "--quiet", str(clone))
    git(clone, "remote", "add", "origin", str(origin))
    return clone


def tree_of(cwd, ref):
    return {line.split("\t")[1]: line.split()[2] for line in git(cwd, "ls-tree", ref).splitlines()}


# The judged repository's bare origin, at a path whose last two parts
# name it, as a remote URL's do.
ORIGIN_NAME = REPO + ".git"


def run_push(folder, gh, extra=(), git=refuse_every_call):
    args = metrics.parse_args(["push", "--out", str(Path(folder) / "JUDGE.json"), *extra])
    shown, said = io.StringIO(), io.StringIO()
    with redirect_stderr(said), mock.patch.dict(os.environ, GIT_ENV):
        code = metrics.push(args, metrics.Gh(run=gh), git=git, out=shown)
    return code, shown.getvalue(), said.getvalue()


class JudgeOrigin(unittest.TestCase):
    """--push and push go to origin, which must be the repository judged."""

    def test_a_remote_url_names_its_repository_in_every_form(self):
        for url in ("https://github.com/octo/widgets.git", "https://github.com/octo/widgets",
                    "https://mona@github.com/octo/widgets.git/", "git@github.com:octo/widgets.git",
                    "git@github.com:octo/widgets", "ssh://git@github.com/octo/widgets.git",
                    "ssh://git@github.com:22/octo/widgets.git", "/srv/git/octo/widgets.git"):
            self.assertEqual(metrics.repository_of(url), "octo/widgets", url)
        self.assertIsNone(metrics.repository_of(""))
        self.assertIsNone(metrics.repository_of("widgets"))
        self.assertIsNone(metrics.origin_refusal(origin_at("git@github.com:Octo/Widgets.git"), REPO))

    def test_judge_push_refuses_another_repositorys_clone_before_reading_anything(self):
        gh = FakeGh()
        with tempfile.TemporaryDirectory() as folder:
            code, out, _, said = run_judge(folder, gh, refuse_every_call, ["--repo", REPO, "--push"],
                                           git=origin_at("https://github.com/acme/other.git"))
            self.assertFalse(out.exists())
        self.assertEqual(code, 1)
        self.assertEqual(gh.calls, [])
        self.assertIn(f"judge: --push refused: the repository judged is {REPO}, but this clone's origin is "
                      "https://github.com/acme/other.git", said)
        self.assertIn(f"Run this in a clone of {REPO}", said)

    def test_judge_push_refuses_a_clone_without_an_origin(self):
        with tempfile.TemporaryDirectory() as folder:
            clone = Path(folder) / "clone"
            git(folder, "init", "--quiet", str(clone))
            code, _, _, said = run_judge(folder, FakeGh(), refuse_every_call, ["--repo", REPO, "--push"],
                                         git=partial(run_in, clone))
        self.assertEqual(code, 1)
        self.assertIn("this clone's origin has no URL", said)

    def test_judge_push_lands_in_the_judged_repositorys_clone(self):
        claude = FakeClaude('{"codes": ["C2"]}')
        with tempfile.TemporaryDirectory() as folder:
            origin, seeded = seeded_origin(folder, {"METRICS.json": '{"schema": "sdlc-metrics/1"}\n'}, ORIGIN_NAME)
            clone = clone_of(folder, origin, "clone")
            with mock.patch.dict(os.environ, GIT_ENV):
                code, out, shown, _ = run_judge(folder, FakeGh(), claude, ["--repo", REPO, "--push"],
                                                git=partial(run_in, clone))
            self.assertEqual(code, 0)
            self.assertIn("judge: pushed to metrics as", shown)
            self.assertEqual(git(origin, "rev-parse", "metrics^"), seeded)
            self.assertEqual(git(origin, "show", "metrics:JUDGE.json") + "\n", out.read_text())
            self.assertEqual(json.loads(out.read_text())["counts"]["C2"], 1)

    def test_push_sends_the_written_file_without_judging_again(self):
        claude = FakeClaude('{"codes": ["C3a"]}')
        with tempfile.TemporaryDirectory() as folder:
            origin, seeded = seeded_origin(folder, {"METRICS.json": '{"schema": "sdlc-metrics/1"}\n'}, ORIGIN_NAME)
            clone = clone_of(folder, origin, "clone")
            _, out, _, _ = run_judge(folder, FakeGh(), claude, ["--repo", REPO])
            code, shown, _ = run_push(folder, refuse_every_call, ["--repo", REPO], git=partial(run_in, clone))
            self.assertEqual(code, 0)
            self.assertIn(f"push: {out} pushed to metrics as", shown)
            self.assertEqual(len(claude.calls), 1)
            self.assertEqual(git(origin, "rev-parse", "metrics^"), seeded)
            self.assertEqual(git(origin, "show", "metrics:JUDGE.json") + "\n", out.read_text())
            self.assertEqual(sorted(tree_of(origin, "metrics")), ["JUDGE.json", "METRICS.json"])

    def test_push_asks_gh_for_the_repository_only_without_repo(self):
        gh = FakeGh()
        with tempfile.TemporaryDirectory() as folder:
            origin, _ = seeded_origin(folder, {"METRICS.json": "{}\n"}, ORIGIN_NAME)
            clone = clone_of(folder, origin, "clone")
            run_judge(folder, FakeGh(), FakeClaude('{"codes": []}'), ["--repo", REPO])
            code, _, _ = run_push(folder, gh, git=partial(run_in, clone))
        self.assertEqual(code, 0)
        self.assertEqual([call[1:3] for call in gh.calls], [["repo", "view"]])

    def test_push_refuses_another_repositorys_clone_and_a_file_the_judge_did_not_write(self):
        with tempfile.TemporaryDirectory() as folder:
            run_judge(folder, FakeGh(), FakeClaude('{"codes": []}'), ["--repo", REPO])
            code, _, said = run_push(folder, refuse_every_call, ["--repo", REPO],
                                     git=origin_at("git@github.com:acme/other.git"))
            self.assertEqual(code, 1)
            self.assertIn(f"push: refused: the repository judged is {REPO}, but this clone's origin is "
                          "git@github.com:acme/other.git", said)
            path = Path(folder) / "JUDGE.json"
            for text in ('{"schema": "sdlc-judge/1"}\n', "not json", json.dumps(dict(
                    json.loads(path.read_text()), repository=REPO))):
                path.write_text(text)
                with self.assertRaises(metrics.JudgeError, msg=text) as caught:
                    run_push(folder, refuse_every_call, ["--repo", REPO])
                self.assertIn("not a JUDGE.json the judge wrote", str(caught.exception))
            path.unlink()
            with self.assertRaises(metrics.JudgeError):
                run_push(folder, refuse_every_call, ["--repo", REPO])


def refusing_push(clone):
    """A git on the clone whose every push is refused."""
    real = partial(run_in, clone)

    def git(*args, input=None):
        if args[0] == "push":
            raise metrics.JudgeError("push: refused by the test")
        return real(*args, input=input)
    return git


class JudgePush(unittest.TestCase):
    def push(self, folder, origin):
        clone = clone_of(folder, origin, "clone")
        path = Path(folder) / "JUDGE.json"
        path.write_text('{"schema": "sdlc-judge/1"}\n')
        with mock.patch.dict(os.environ, GIT_ENV):
            commit = metrics.push_judge(path, partial(run_in, clone))
        return clone, commit, path

    def test_it_lands_as_a_fast_forward_that_keeps_metrics_json_and_profile_json(self):
        with tempfile.TemporaryDirectory() as folder:
            origin, seeded = seeded_origin(folder, {"METRICS.json": '{"schema": "sdlc-metrics/1"}\n',
                                                    "PROFILE.json": '{"schema": "symphony-profile-sums/1"}\n'})
            before = tree_of(origin, seeded)
            clone, commit, path = self.push(folder, origin)
            self.assertEqual(git(origin, "rev-parse", "metrics"), commit)
            self.assertEqual(git(origin, "rev-parse", "metrics^"), seeded)
            after = tree_of(origin, "metrics")
            self.assertEqual((after["METRICS.json"], after["PROFILE.json"]),
                             (before["METRICS.json"], before["PROFILE.json"]))
            self.assertEqual(git(origin, "show", "metrics:JUDGE.json") + "\n", path.read_text())
            self.assertRegex(git(origin, "log", "-1", "--format=%s", "metrics"),
                             r"^Judge counts as of \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ \[skip ci\]$")

    def test_after_two_refusals_it_names_the_push_that_judges_nothing_again(self):
        with tempfile.TemporaryDirectory() as folder:
            origin, _ = seeded_origin(folder, {"METRICS.json": "{}\n"})
            clone = clone_of(folder, origin, "clone")
            path = Path(folder) / "JUDGE.json"
            path.write_text('{"schema": "sdlc-judge/1"}\n')
            with mock.patch.dict(os.environ, GIT_ENV), self.assertRaises(metrics.JudgeError) as caught:
                metrics.push_judge(path, refusing_push(clone))
            self.assertIn("refused twice, the last time with: push: refused by the test", str(caught.exception))
            self.assertIn(f"push it alone with `python3 tools/metrics.py push --out {path}`", str(caught.exception))

    def test_it_starts_the_branch_when_there_is_none(self):
        with tempfile.TemporaryDirectory() as folder:
            origin = Path(folder) / "origin.git"
            git(folder, "init", "--quiet", "--bare", str(origin))
            _, commit, _ = self.push(folder, origin)
            self.assertEqual(sorted(tree_of(origin, "metrics")), ["JUDGE.json"])
            self.assertEqual(git(origin, "rev-list", "--count", "metrics"), "1")

    def test_the_push_guard_lets_its_push_through(self):
        command = shlex.join(["git", *metrics.push_arguments("0123456789abcdef0123456789abcdef01234567")])
        pushes = [args for argv in guard_push.simple_commands(command)
                  if (args := guard_push.push_arguments(argv)) is not None]
        self.assertEqual(len(pushes), 1)
        for current in (None, "main", "claude/7", "metrics"):
            self.assertIsNone(guard_push.refusal(pushes[0], current, "main"), current)
        self.assertNotIn("--force", " ".join(pushes[0]))
        payload = json.dumps({"tool_input": {"command": command}})
        with mock.patch.object(guard_push, "branches", return_value=("main", "main")), \
                mock.patch.object(sys, "stdin", io.StringIO(payload)), redirect_stderr(io.StringIO()):
            self.assertEqual(guard_push.main(), 0)


def run_in(cwd, *args, input=None):
    done = subprocess.run(["git", "-C", str(cwd), *args], input=input, capture_output=True, text=True)
    if done.returncode != 0:
        raise metrics.JudgeError(f"git {args[0]}: {done.stderr.strip()}")
    return done.stdout


# --- the workflow ---------------------------------------------------------------

def step_lines(name):
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = lines.index(f"      - name: {name}")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("      - ")), len(lines))
    return lines[start:end]


def run_block(lines):
    start = next(i for i, line in enumerate(lines) if line.strip() == "run: |")
    return "\n".join(line[10:] for line in lines[start + 1:]) + "\n"


WRITE_STEP = "Write METRICS.json and PROFILE.json to the branch metrics when they changed"
OLD = dict(EXPECTED, schema="sdlc-metrics/1", generated_at="2026-10-09T04:43:00Z")
NEW_TIME = dict(OLD, generated_at="2026-10-10T04:43:00Z")
MOVED = dict(NEW_TIME, counts=dict(EXPECTED["counts"], merged=2))
SUMS_OLD = dict(WORLD_PROFILE, generated_at="2026-10-09T04:43:00Z")
SUMS_NEW_TIME = dict(SUMS_OLD, generated_at="2026-10-10T04:43:00Z")
SUMS_MOVED = dict(SUMS_NEW_TIME, sessions=3)
RACE_GIT = """#!/bin/bash
# The first push of the run is preceded by a judge's, as if it landed
# between the run's fetch and its own push.
if [ "$1" = "push" ] && [ ! -e "$RACE_DONE" ]; then
  touch "$RACE_DONE"
  "$REAL_GIT" -C "$RACE_CLONE" push --quiet origin "$RACE_COMMIT:refs/heads/metrics"
fi
exec "$REAL_GIT" "$@"
"""


class WriteStep(unittest.TestCase):
    """The step's own script, run against a bare origin."""

    def step(self, folder, origin, record, extra_env=None, sums=None):
        """The step after a collect that wrote record as METRICS.json and,
        where sums is given, sums as PROFILE.json."""
        work = clone_of(folder, origin, "work")
        (work / "tools").symlink_to(ROOT / "tools")
        temp = Path(folder) / "runner"
        temp.mkdir()
        (temp / "METRICS.json").write_text(json.dumps(record, indent=2) + "\n")
        if sums is not None:
            (temp / "PROFILE.json").write_text(json.dumps(sums, indent=2) + "\n")
        env = {**os.environ, **GIT_ENV, "RUNNER_TEMP": str(temp), **(extra_env or {})}
        return subprocess.run(["bash", "-e", "-c", run_block(step_lines(WRITE_STEP))], cwd=work, env=env,
                              capture_output=True, text=True)

    def run_step(self, folder, origin, record, extra_env=None, sums=None):
        done = self.step(folder, origin, record, extra_env, sums)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout

    def origin_with_sums(self, folder):
        return seeded_origin(folder, {"METRICS.json": json.dumps(OLD, indent=2) + "\n",
                                      "PROFILE.json": json.dumps(SUMS_OLD, indent=2) + "\n",
                                      "JUDGE.json": '{"n": 1}\n'})

    def origin_with_judge(self, folder):
        return seeded_origin(folder, {"METRICS.json": json.dumps(OLD, indent=2) + "\n", "JUDGE.json": '{"n": 1}\n'})

    def test_a_change_replaces_the_branch_with_one_commit_that_keeps_judge_json(self):
        with tempfile.TemporaryDirectory() as folder:
            origin, seeded = self.origin_with_judge(folder)
            judge_blob = tree_of(origin, seeded)["JUDGE.json"]
            said = self.run_step(folder, origin, MOVED)
            self.assertIn("metrics written as", said)
            self.assertEqual(git(origin, "rev-list", "--count", "metrics"), "1")
            self.assertEqual(tree_of(origin, "metrics")["JUDGE.json"], judge_blob)
            self.assertEqual(json.loads(git(origin, "show", "metrics:METRICS.json")), MOVED)

    def test_a_new_time_alone_writes_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            origin, seeded = self.origin_with_judge(folder)
            said = self.run_step(folder, origin, NEW_TIME)
            self.assertIn("metrics unchanged", said)
            self.assertEqual(git(origin, "rev-parse", "metrics"), seeded)

    def test_the_first_write_starts_the_branch(self):
        with tempfile.TemporaryDirectory() as folder:
            origin = Path(folder) / "origin.git"
            git(folder, "init", "--quiet", "--bare", str(origin))
            self.run_step(folder, origin, MOVED)
            self.assertEqual(sorted(tree_of(origin, "metrics")), ["METRICS.json"])

    def test_a_branch_metrics_the_project_had_before_is_left_as_it_is(self):
        # A branch metrics of the project's own holds files this workflow
        # never wrote. The lease alone would hold, since the run fetched
        # that very commit, so the run looks at the tree, pushes nothing
        # and fails, without the second attempt a failed lease gets.
        with tempfile.TemporaryDirectory() as folder:
            origin, seeded = seeded_origin(folder, {"METRICS.json": json.dumps(OLD, indent=2) + "\n",
                                                    "JUDGE.json": '{"n": 1}\n', "README.md": "the project's own\n"})
            done = self.step(folder, origin, MOVED)
            self.assertNotEqual(done.returncode, 0)
            self.assertIn("the branch metrics holds files this workflow did not write:\nREADME.md\n", done.stdout)
            self.assertIn("nothing was pushed", done.stdout)
            self.assertIn("Rename it", done.stdout)
            self.assertNotIn("moved during this run", done.stdout)
            self.assertEqual(git(origin, "rev-parse", "metrics"), seeded)

    def test_the_profile_goes_beside_metrics_json_and_a_first_one_is_a_change(self):
        with tempfile.TemporaryDirectory() as folder:
            origin, seeded = self.origin_with_judge(folder)
            judge_blob = tree_of(origin, seeded)["JUDGE.json"]
            said = self.run_step(folder, origin, NEW_TIME, sums=SUMS_NEW_TIME)
            self.assertIn("metrics written as", said)
            self.assertEqual(sorted(tree_of(origin, "metrics")), ["JUDGE.json", "METRICS.json", "PROFILE.json"])
            self.assertEqual(tree_of(origin, "metrics")["JUDGE.json"], judge_blob)
            self.assertEqual(json.loads(git(origin, "show", "metrics:PROFILE.json")), SUMS_NEW_TIME)

    def test_both_files_unchanged_apart_from_their_time_write_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            origin, seeded = self.origin_with_sums(folder)
            said = self.run_step(folder, origin, NEW_TIME, sums=SUMS_NEW_TIME)
            self.assertIn("metrics unchanged", said)
            self.assertEqual(git(origin, "rev-parse", "metrics"), seeded)

    def test_a_moved_profile_alone_is_a_change(self):
        with tempfile.TemporaryDirectory() as folder:
            origin, _ = self.origin_with_sums(folder)
            said = self.run_step(folder, origin, NEW_TIME, sums=SUMS_MOVED)
            self.assertIn("metrics written as", said)
            self.assertEqual(json.loads(git(origin, "show", "metrics:PROFILE.json")), SUMS_MOVED)
            self.assertEqual(json.loads(git(origin, "show", "metrics:METRICS.json")), NEW_TIME)
            self.assertEqual(git(origin, "show", "metrics:JUDGE.json"), '{"n": 1}')

    def test_a_run_that_wrote_no_profile_keeps_the_branchs(self):
        with tempfile.TemporaryDirectory() as folder:
            origin, seeded = self.origin_with_sums(folder)
            sums_blob = tree_of(origin, seeded)["PROFILE.json"]
            self.assertIn("metrics unchanged", self.run_step(folder, origin, NEW_TIME))
        with tempfile.TemporaryDirectory() as folder:
            origin, seeded = self.origin_with_sums(folder)
            said = self.run_step(folder, origin, MOVED)
            self.assertIn("metrics written as", said)
            self.assertEqual(tree_of(origin, "metrics")["PROFILE.json"], sums_blob)

    def test_a_judge_push_landing_meanwhile_is_kept(self):
        with tempfile.TemporaryDirectory() as folder:
            origin, seeded = self.origin_with_judge(folder)
            race = clone_of(folder, origin, "race")
            judge = Path(folder) / "JUDGE.json"
            judge.write_text('{"n": 2}\n')
            git(race, "fetch", "--quiet", "origin", "metrics")
            with mock.patch.dict(os.environ, GIT_ENV):
                race_commit = metrics.judge_commit(partial(run_in, race), judge, seeded)
            shim = Path(folder) / "bin"
            shim.mkdir()
            (shim / "git").write_text(RACE_GIT)
            (shim / "git").chmod(0o755)
            env = {"PATH": f"{shim}{os.pathsep}{os.environ['PATH']}", "REAL_GIT": subprocess.run(
                ["bash", "-c", "command -v git"], capture_output=True, text=True).stdout.strip(),
                "RACE_DONE": str(Path(folder) / "race-done"), "RACE_CLONE": str(race), "RACE_COMMIT": race_commit}
            said = self.run_step(folder, origin, MOVED, env)
            self.assertIn("moved during this run", said)
            self.assertEqual(git(origin, "show", "metrics:JUDGE.json"), '{"n": 2}')
            self.assertEqual(json.loads(git(origin, "show", "metrics:METRICS.json")), MOVED)
            self.assertEqual(git(origin, "rev-list", "--count", "metrics"), "1")


class Workflow(unittest.TestCase):
    TEXT = WORKFLOW.read_text(encoding="utf-8")

    def test_daily_at_an_odd_minute_before_the_collectors_read_and_by_hand(self):
        found = re.search(r'\n  schedule:\n    - cron: "([1-9]|[1-5][0-9]) (\d{1,2}) \* \* \*"\n', self.TEXT)
        self.assertTrue(found, "one daily cron at an odd minute")
        self.assertLess(int(found.group(2)) * 60 + int(found.group(1)), COLLECTOR_READ)
        self.assertIn("\n  workflow_dispatch:\n", self.TEXT)

    def test_a_change_to_the_switch_on_the_default_branch_starts_it_and_a_fork_never_runs_it(self):
        self.assertIn('\non:\n  push:\n    paths: [".github/symphony-metrics", ".github/sdlc-metrics"]\n', self.TEXT)
        folded = self.TEXT.split("    if: >-\n", 1)[1].split("\n    runs-on:", 1)[0]
        self.assertEqual(" ".join(line.strip() for line in folded.splitlines()),
                         "github.event.repository.is_template == false "
                         "&& (github.event_name != 'push' || github.ref_name == github.event.repository.default_branch) "
                         "&& github.event.repository.fork == false")

    def test_its_permissions_are_these_five(self):
        # actions: read lists and downloads the Actions runs' usage records.
        block = self.TEXT.split("\npermissions:\n", 1)[1].split("\n\n", 1)[0]
        self.assertEqual(block.splitlines(), ["  contents: write", "  pull-requests: read", "  issues: read",
                                              "  checks: read", "  actions: read"])

    def test_it_skips_the_template_and_a_pending_copy(self):
        self.assertIn("    if: >-\n      github.event.repository.is_template == false\n", self.TEXT)
        self.assertIn("if [ -e .template/PENDING ]; then", "\n".join(step_lines("Stop in the template repository itself")))

    def test_values_reach_the_shell_through_env_alone(self):
        for name in ("Stop in the template repository itself", "Collect the aggregates", WRITE_STEP):
            lines = step_lines(name)
            start = next(i for i, line in enumerate(lines) if line.strip().startswith("run:"))
            self.assertNotIn("${{", "\n".join(lines[start:]), name)
        collect_step = "\n".join(step_lines("Collect the aggregates"))
        self.assertIn("SDLC_METRICS: ${{ vars.SDLC_METRICS }}", collect_step)
        self.assertIn("GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}", collect_step)

    def test_it_names_no_secret_but_its_own_token(self):
        self.assertEqual(set(re.findall(r"secrets\.([A-Z_]+)", self.TEXT)), {"GITHUB_TOKEN"})
        self.assertNotIn("anthropics/claude-code-action", self.TEXT)
        self.assertIn("In crowd mode", self.TEXT.split("\non:", 1)[0])

    def test_the_profile_collect_writes_is_the_one_the_write_step_puts_on_the_branch(self):
        collect_step = " ".join(line.strip() for line in step_lines("Collect the aggregates"))
        self.assertIn('--profile-out "$RUNNER_TEMP/PROFILE.json"', collect_step)
        self.assertIn('profile="$RUNNER_TEMP/PROFILE.json"', run_block(step_lines(WRITE_STEP)))

    def test_its_one_forced_push_is_leased_to_the_commit_it_read(self):
        script = run_block(step_lines(WRITE_STEP))
        self.assertIn('--force-with-lease="refs/heads/metrics:$previous"', script)
        self.assertNotRegex(script, r"--force(?!-with-lease)|\s-f\s|\+\$commit")


class Coordinator(unittest.TestCase):
    def test_the_coordinators_release_starts_with_the_marker_metrics_counts(self):
        # The coordinator releases in the board's own run, with the claim
        # protocol's words, so metrics and the release read one marker.
        from sdlc_protocol import board, claims, coordinator
        self.assertEqual(metrics.RELEASE_MARKER, claims.RELEASE_MARKER)
        snap = board.Snapshot.from_dict({
            "branches": ["claude/12"],
            "claim_issues": {"12": {"state": "open", "labels": ["claimed", "todo"]}},
            "releases": {"12": {"released_at": "", "sha": "aaaaaaa1111111", "committed_at": "2026-09-18T12:00:00Z"}},
        })
        text = coordinator.release_text(snap, "12", coordinator.Holding())
        self.assertTrue(text.startswith(metrics.RELEASE_MARKER + "\n"), text)


class Page(unittest.TestCase):
    TEXT = (ROOT / "docs" / "setup" / "metrics.md").read_text(encoding="utf-8")

    def samples(self):
        return [json.loads(block.split("\n", 1)[1]) for block in self.TEXT.split("```")[1::2]
                if block.startswith("json\n")]

    def test_the_samples_have_exactly_the_keys_the_tool_writes(self):
        found = {}
        for sample in self.samples():
            found.setdefault(sample["schema"], sample)
        sample = found["sdlc-metrics/1"]
        self.assertEqual(tuple(sample), metrics.RECORD_KEYS)
        self.assertEqual(tuple(sample["counts"]), metrics.COUNT_KEYS)
        self.assertEqual(tuple(sample["durations_seconds"]), metrics.DURATION_KEYS)
        self.assertEqual(tuple(sample["rates"]), metrics.RATE_KEYS)
        self.assertEqual(tuple(sample["parallel"]), metrics.PARALLEL_KEYS)
        self.assertEqual(tuple(sample["by_setting"]), metrics.SETTINGS)
        for row in sample["by_setting"].values():
            self.assertEqual(tuple(row), metrics.SETTING_KEYS)
        self.assertEqual(tuple(sample["pairs"]), metrics.RELATIONS)
        for row in sample["pairs"].values():
            self.assertEqual(tuple(row), metrics.PAIR_KEYS)
        judge = found["sdlc-judge/1"]
        self.assertEqual(tuple(judge), metrics.JUDGE_KEYS)
        self.assertEqual(tuple(judge["counts"]), metrics.APPF_CODES)
        self.assertEqual(tuple(judge["groups"]), metrics.GROUPS)
        self.assertEqual(tuple(judge["by_setting"]), metrics.SETTINGS)
        for row in judge["by_setting"].values():
            self.assertEqual(tuple(row), metrics.JUDGE_SETTING_KEYS)
            self.assertEqual(tuple(row["counts"]), metrics.APPF_CODES)

    def test_the_metrics_sample_is_what_collect_writes_for_the_two_person_world(self):
        sample = next(s for s in self.samples() if s["schema"] == "sdlc-metrics/1" and "counts" in s)
        for key, block in WORLD_EXPECTED.items():
            self.assertEqual(sample[key], block, key)
        self.assertEqual((sample["economics"], sample["coordination"]), (WORLD_ECONOMICS, WORLD_COORDINATION))
        self.assertEqual((sample["counts"], sample["durations_seconds"], sample["rates"]),
                         (WORLD_COUNTS, WORLD_DURATIONS, WORLD_RATES))

    def test_the_profile_sample_is_what_collect_writes_for_the_two_person_world(self):
        sample = next(s for s in self.samples() if s["schema"] == metrics.PROFILE_SCHEMA)
        self.assertEqual(sample, WORLD_PROFILE)
        self.assertEqual(tuple(sample), metrics.PROFILE_KEYS)
        self.assertEqual(tuple(sample["by_setting"]), metrics.SETTINGS)
        for row in [*sample["by_setting"].values(), sample["coordination"]["alone"],
                    sample["coordination"]["parallel"]]:
            self.assertEqual(tuple(row), metrics.profile.GROUP_KEYS)
        self.assertEqual(tuple(sample["coordination"]), ("alone", "parallel", "ratios"))
        self.assertEqual(tuple(sample["coordination"]["ratios"]), metrics.profile.RATIO_KEYS)
        self.assertIn(f"`{json.dumps(metrics.PROFILE_OFF)}`", self.TEXT)
        for key in (*metrics.profile.GROUP_KEYS, *metrics.profile.RATIO_KEYS, *metrics.PROFILE_KEYS[4:6]):
            self.assertIn(key, self.TEXT.split("## The profile's sums", 1)[1].split("\n## ", 1)[0], key)

    def test_it_names_the_switch_both_ways_and_never_an_api_key_for_the_judge(self):
        for needed in (metrics.SWITCH_FILE, "SDLC_METRICS", "python3 tools/metrics.py judge --dry-run",
                       "unset ANTHROPIC_API_KEY", metrics.RELEASE_MARKER, metrics.PUSH_COMMAND, "[skip ci]",
                       *metrics.BILLING_VARIABLES, "ANTHROPIC_BASE_URL"):
            self.assertIn(needed, self.TEXT)

    def test_it_says_how_runs_and_people_are_counted_and_what_the_reserve_is(self):
        for needed in ("filter=all", f"fewer than {metrics.RESERVE} for the board", "shows as dismissed",
                       "reply in a review thread by anyone else", "dated by their own act", "Claude-Session:",
                       "Symphony-Session:", "_Generated by [Claude Code](", "more than 60 seconds",
                       "more than seven days", "one more window", "no session link",
                       *metrics.SETTINGS, *metrics.RELATIONS):
            self.assertIn(needed, self.TEXT)


if __name__ == "__main__":
    unittest.main()
