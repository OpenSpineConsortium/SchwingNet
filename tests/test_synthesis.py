"""The synthesis that keeps itself current (artifacts/_synthesis/work/tools, run by
.github/workflows/synthesis.yml): the Claude sessions' arguments, schemas and briefs, whether a
run may read, a run whose answers come back in part and how the join places them, what the join
and the stamp take as read, the issue's report, the step that lays the open synthesis pull
request on main, the scrub of what the folder's rule keeps out and where a text is cut, the
concept checks and the rekey that carries the stamp's word over a change to the scrub, the
pages, which render from the committed records as they are committed, and the owner's gate the
synthesis's pull requests meet. No Claude, no network and no GitHub: the sessions' answers are
written here by hand, gh is the suite's fake and the remote is a bare repository in a scratch
folder.

    python3 -m unittest tests/test_synthesis.py
"""

import contextlib
import datetime
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import types
import unittest
from collections import Counter
from decimal import Decimal
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SYNTH = ROOT / "artifacts" / "_synthesis"
TOOLS = SYNTH / "work" / "tools"
WORKFLOW = ROOT / ".github" / "workflows" / "synthesis.yml"
sys.path.insert(0, str(TOOLS))
import extract  # noqa: E402
import fake_gh  # noqa: E402
import redact  # noqa: E402
import render_clusters  # noqa: E402
import render_contradictions2 as rc  # noqa: E402
import render_inventory  # noqa: E402
import synth  # noqa: E402
import synth_actions as sa  # noqa: E402
import synth_concepts as sc  # noqa: E402
import synth_reads as sr  # noqa: E402
import synth_schemas  # noqa: E402
import synth_state as st  # noqa: E402
import verify_quotes as vq  # noqa: E402

# Made-up values of the shapes the scrub knows, built from pieces so this file holds none of
# the real ones: a login, the owner's first name and a credential.
LOGIN = "zz" + "9876"
FIRST = "Gr" + "eg"
CREDENTIAL = "sk-" + "ant-" + "x" * 24
QUIET = {"gc.auto": "0", "gc.autoDetach": "false", "maintenance.auto": "false", "maintenance.autoDetach": "false",
         "receive.autogc": "false"}
GIT_ENV = {"GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.invalid", "GIT_COMMITTER_NAME": "Test",
           "GIT_COMMITTER_EMAIL": "test@example.invalid", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_CONFIG_COUNT": str(len(QUIET)),
           **{f"GIT_CONFIG_KEY_{i}": key for i, key in enumerate(QUIET)},
           **{f"GIT_CONFIG_VALUE_{i}": value for i, value in enumerate(QUIET.values())}}


def printed(call, *args):
    """What a tool prints, as name=value pairs where it prints them."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        call(*args)
    return dict(line.split("=", 1) for line in out.getvalue().splitlines() if "=" in line and not line.startswith(" "))


def write(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")


def git(repo, *args):
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                          env={**{k: v for k, v in os.environ.items() if not k.startswith("GIT_")}, **GIT_ENV})
    if done.returncode:
        raise AssertionError(f"git {' '.join(args)}: {done.stderr}")
    return done.stdout.strip()


@contextlib.contextmanager
def texts(folder, extracted, raw=None):
    """The artifacts' texts where verify_quotes reads them: each extracted text under SYNTH_TEXT
    and each of an artifact's own files under its checkout's artifacts/ folder, which
    SYNTH_SCHWINGNET and SYNTH_SYMPHONY name, with its caches emptied before and after, so no
    test reads another's texts. Yields the folder of the extracted texts."""
    root = Path(folder)
    checkouts = {"SchwingNet": root / "schwingnet", "symphony-template": root / "symphony"}
    for checkout in checkouts.values():
        (checkout / "artifacts").mkdir(parents=True, exist_ok=True)
    for aid, text in extracted.items():
        (root / "text" / aid).parent.mkdir(parents=True, exist_ok=True)
        (root / "text" / f"{aid}.txt").write_text(text, encoding="utf-8")
    for aid, files in (raw or {}).items():
        repo, folder_name = aid.split("/", 1)
        for name, text in files.items():
            path = checkouts[repo] / "artifacts" / folder_name / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    env = {"SYNTH_TEXT": str(root / "text"), "SYNTH_SCHWINGNET": str(checkouts["SchwingNet"]),
           "SYNTH_SYMPHONY": str(checkouts["symphony-template"])}
    with mock.patch.dict(os.environ, env), mock.patch.dict(vq.TEXTS, clear=True), mock.patch.dict(vq.RAW, clear=True):
        yield str(root / "text")


class Arguments(unittest.TestCase):
    """Each session reads with no repository settings, may not write, run or fetch, and answers
    in its stage's schema, carried through the action's shell-like parse whole."""

    def test_every_stage_denies_what_writes_and_takes_no_repository_settings(self):
        for stage in sa.STAGES:
            lines = sa.claude_args(stage).splitlines()
            self.assertIn("--setting-sources user", lines, stage)
            self.assertIn("--permission-mode default", lines, stage)
            self.assertFalse(any(line.startswith("--allowedTools") for line in lines), stage)
            denied = next(line for line in lines if line.startswith("--disallowedTools"))
            for tool in ("Bash", "Edit", "Write", "WebFetch", "Task", "Read(./.git/**)"):
                self.assertIn(tool, denied.split('"')[1].split(","), stage)

    def test_the_schema_survives_the_shell_words_and_holds_the_record_keys(self):
        for stage in sa.STAGES:
            line = next(x for x in sa.claude_args(stage).splitlines() if x.startswith("--json-schema"))
            text = line[len("--json-schema '"):-1]
            self.assertFalse(set(text) & set("'\\$"), stage)
            self.assertEqual(json.loads(text), synth_schemas.SCHEMAS[stage])
        self.assertEqual(set(synth_schemas.RECORD["properties"]), set(sr.RECORD_KEYS))

    def test_a_name_a_shell_would_split_is_left_out(self):
        args = sa.claude_args("read", model="opus; rm -rf /", fallback="claude-x", effort="max")
        self.assertFalse(any(line.startswith("--model") for line in args.splitlines()))
        self.assertIn("--fallback-model claude-x", args)
        self.assertIn("--effort max", args)
        self.assertIn("--effort high", sa.claude_args("judge", effort="low"))
        self.assertNotIn("--fallback-model", sa.claude_args("skeptic", model="m1", fallback="m1"))


class Briefs(unittest.TestCase):
    def test_every_brief_fills_every_place_and_stays_ascii(self):
        with tempfile.TemporaryDirectory() as folder:
            plan, batches = Path(folder, "plan"), Path(folder, "batches")
            write(plan / "args.json", {"inventory": [{"file": str(plan / "inventory-0.json")}]})
            for stage in ("skeptic", "recheck", "judge"):
                write(batches / f"{stage}-0.json", {"items": [{"key": "k1"}, {"key": "k2"}]})
            for stage in sa.STAGES:
                text = sa.prompt(stage, str(plan), str(batches), "0")
                self.assertNotIn("$", text, stage)
                self.assertTrue(text.isascii(), stage)
                self.assertIn(str(plan / "inventory-0.json") if stage == "read" else f"{stage}-0.json", text)


class Admission(unittest.TestCase):
    def test_the_first_thing_a_person_would_fix_is_named(self):
        cases = [
            (dict(waiting=0), "Nothing waits"),
            (dict(switch="OFF"), "SYNTHESIS_READS is off"),
            (dict(crowd="true"), "crowd mode"),
            (dict(token="false"), "CLAUDE_CODE_OAUTH_TOKEN"),
            (dict(app="false"), "SDLC_APP_ID"),
            (dict(without="symphony-template"), "could not check out symphony-template"),
            (dict(conflict="12"), "#12 no longer merges"),
            (dict(foreign="12"), "#12 changes a file no join writes"),
            (dict(rejected="12"), "owner-ok failed on the head of the open synthesis pull request #12"),
            (dict(done=10), "10 runs have read today"),
            (dict(stopped=True), "last three runs"),
        ]
        base = dict(waiting=3, switch="", crowd="", token="true", conflict="", done=0, cap=10, stopped=False, app="true")
        for change, words in cases:
            ok, why = sa.admission(**{**base, **change})
            self.assertFalse(ok, change)
            self.assertIn(words, why)
        ok, why = sa.admission(**{**base, "switch": "on"})
        self.assertTrue(ok)
        self.assertIn("run 1 of at most 10", why)
        _, why = sa.admission(**{**base, "rejected": "12", "done": 10})
        self.assertIn("owner-ok failed", why, "a Reject is named before the day's cap, which waiting would not clear")

    def test_the_marks_of_every_page_count_and_the_last_runs_are_named_by_id(self):
        day = "2026-10-24"
        mark = lambda run, hour: {"created_at": f"{day}T{hour:02d}:00:00Z", "workflow_run": {"id": run}}  # noqa: E731
        pages = [{"artifacts": [mark(1, 1), mark(2, 2)]}, {"artifacts": [mark(3, 3), mark(3, 4), mark(4, 5), mark("5", 6)]}]
        self.assertEqual(sa.runs_today(pages, day), 6, "gh api --paginate --slurp gives a list of pages")
        self.assertEqual(sa.runs_today(pages[0], day), 2, "one call gives one page")
        self.assertEqual(sa.marked(pages), [4, 3, 2], "newest first, each run once, an id that is no number left out")
        with tempfile.TemporaryDirectory() as folder:
            write(Path(folder, "marks.json"), pages)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                sa.main(["marked", "--marks", str(Path(folder, "marks.json"))])
            self.assertEqual(out.getvalue().split(), ["4", "3", "2"])

    def test_the_day_s_cap(self):
        for text, cap in (("", 10), ("7", 7), ("070", 50), ("abc", 10), ("1234", 10), (" 3 ", 3)):
            self.assertEqual(sa.cap_of(text), cap, text)

    def test_three_failures_pause_the_schedule_and_never_a_hand_started_run(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        stamp = lambda hours: (now - datetime.timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731
        marks = {"artifacts": [{"created_at": stamp(h), "workflow_run": {"id": i}} for i, h in ((1, 3), (2, 2), (3, 1))]}
        runs = {"workflow_runs": [{"id": i, "status": "completed", "conclusion": "failure", "created_at": stamp(h),
                                   "updated_at": stamp(h)} for i, h in ((1, 3), (2, 2), (3, 1))]}
        self.assertTrue(sa.failing(marks, runs, now))
        self.assertFalse(sa.failing(marks, runs, now + datetime.timedelta(hours=6)))
        runs["workflow_runs"][1]["conclusion"] = "success"
        self.assertFalse(sa.failing(marks, runs, now))
        runs["workflow_runs"][1]["conclusion"] = "failure"
        with tempfile.TemporaryDirectory() as folder:
            files = {name: Path(folder, f"{name}.json") for name in ("status", "marks", "runs")}
            write(files["status"], {"changes": [{"id": "SchwingNet/a"}], "new_checks": [], "stale": [], "unread": []})
            write(files["marks"], marks)
            write(files["runs"], runs)
            for event, admitted in (("schedule", "false"), ("push", "false"), ("workflow_dispatch", "true")):
                argv = ["admit", *(x for n, f in files.items() for x in (f"--{n}", str(f))), "--event", event,
                        "--token", "true", "--words", str(Path(folder, "words.md"))]
                self.assertEqual(printed(sa.main, argv)["admit"], admitted, event)


def record(**fields):
    """A record with every field the join requires."""
    rec = {k: [] for k in sr.LISTS}
    rec.update({k: "" for k in sr.RECORD_KEYS if k not in sr.LISTS})
    rec.update(summary="What the page says.", date="2026-10-24", confidentiality="schwingnet-other")
    rec.update(fields)
    return rec


ALPHA, BETA, GAMMA = "SchwingNet/alpha-page-a1b2c3", "SchwingNet/beta-page-d4e5f6", "SchwingNet/gamma-page-g7h8i9"
# What the artifacts say, so the finders' candidates below quote what is there: a cluster
# candidate's quotes are "<topic> in a" and "<topic> in b", a number candidate's "98.2% of
# frames" and "97.4% of frames"; and a figure only one of alpha's own files holds.
FOUND_TEXTS = {ALPHA: "placed in a. refused in a. 98.2% of frames. unruled in b.",
               BETA: "placed in b. refused in b. 97.4% of frames.", GAMMA: "unruled in a."}
FOUND_RAW = {ALPHA: {"data.json": '{"note": "a figure only the data holds"}'}}


class World:
    """Two inventoried artifacts in one cluster and a third that is new, the rows already on
    the contradictions page, and a plan for a run that reads the first and the third, as
    synth.py plan writes one."""

    def __init__(self, folder):
        self.folder = Path(folder)
        self.rows = [{"repo": "SchwingNet", "folder": aid.split("/")[1], "title": aid.split("/")[1], "account": "first account",
                      "link": f"https://claude.ai/artifact/{n}", "link_id": n, "readme_summary": "s"}
                     for n, aid in (("A1", ALPHA), ("G1", GAMMA), ("B1", BETA))]
        self.inventory = {"artifacts": [{"repo": "SchwingNet", "folder": aid.split("/")[1], "title": aid, **record(summary=aid)}
                                        for aid in (ALPHA, BETA)], "skipped": []}
        self.clustering = {"judged": {"clusters": [{"name": "C1", "description": "one topic", "members": [ALPHA, BETA]}],
                                      "unplaced": []}}
        old = {"kind": "contradiction", "topic": "t", "artifact_a": ALPHA, "artifact_b": BETA, "statement_a": "a",
               "quote_a": "qa", "statement_b": "b", "quote_b": "qb"}
        self.M = {"clusters": [{"cluster": "C1", "candidates": [old, {**old, "topic": "found", "delta": {"date": "2026-10-23"}}],
                                "verdicts": [{"verdict": "confirmed", "quote_a": "qa", "quote_b": "qb"}, None]}],
                  "numbers_extra": []}
        self.N = {"candidates": [], "verdicts": [], "finders": []}
        info = {aid: {"id": aid, "title": aid, "date": "2026-10-24", "text": f"/t/{aid}.txt", "folder": f"/c/{aid}"}
                for aid in (ALPHA, BETA, GAMMA)}
        items = [{"key": "stale:C1|0", "stratum": "C1", "index": 0, "kind": "contradiction", "a": info[ALPHA], "b": info[BETA],
                  "quote_a": "qa", "quote_b": "qb", "earlier": self.M["clusters"][0]["verdicts"][0], "why": "its quote moved"},
                 {"key": "unread:C1|1", "stratum": "C1", "index": 1, "kind": "contradiction", "a": info[ALPHA], "b": info[BETA],
                  "quote_a": "qa", "quote_b": "qb", "why": "found on 2026-10-23, whose run gave it no verdict"}]
        self.plan = self.folder / "plan"
        write(self.plan / "items.json", {"items": items})
        self.args = {"date": "2026-10-24", "items": str(self.plan / "items.json"), "items_waiting": [], "waiting": [],
                     "inventory": [{"file": "f0", "id": ALPHA, "new": False, "cluster": "C1"},
                                   {"file": "f1", "id": GAMMA, "new": True, "cluster": None}],
                     "clusters": {"C1": "c1.json"}, "numbers": "n.json", "paths": info, "batch": sr.BATCH, "found": sr.FOUND}
        write(self.plan / "args.json", self.args)
        self.answers = self.folder / "answers"
        self.batches = self.folder / "batches"

    def answer(self, label, result):
        write(self.answers / f"{label.replace(':', '-')}.json", {"label": label, "result": result})


def cluster_candidate(a, b, topic, kind="contradiction"):
    return {"kind": kind, "topic": topic, "artifact_a": a, "statement_a": "sa", "quote_a": f"{topic} in a", "artifact_b": b,
            "statement_b": "sb", "quote_b": f"{topic} in b", "why_it_matters": "w"}


def number_candidate(kind, quantity):
    return {"quantity": quantity, "artifact_a": ALPHA, "value_a": "98.2%", "quote_a": "98.2% of frames", "artifact_b": BETA,
            "value_b": "97.4%", "quote_b": "97.4% of frames", "kind": kind, "why": "two values"}


def reading(key, verdict, **more):
    return {"key": key, "verdict": verdict, "quote_a": "qa", "quote_b": "qb", "explanation": "e", "resolution_hint": "h", **more}


class Join(unittest.TestCase):
    """A run whose answers came back in part: what came back is placed, what did not waits or
    is added as a row with no verdict, and nothing moves a row's number."""

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.world = World(self.scratch.name)
        self.text_dir = self.enterContext(texts(Path(self.scratch.name, "texts"), FOUND_TEXTS, FOUND_RAW))

    def test_records_go_in_readme_order_and_what_cannot_be_placed_is_left_with_why(self):
        w = self.world
        found = {"inventory:0": {"record": record(summary="read again"), "changed": "its table"},
                 "inventory:1": {"record": record(summary="new"), "cluster": "C1", "cluster_why": "same topic"}}
        history = []
        read, left = sr.join_inventory(w.args, found, w.inventory, history, w.clustering, w.rows, "2026-10-24")
        self.assertEqual((read, left), ([ALPHA, GAMMA], {}))
        self.assertEqual([f"{r['repo']}/{r['folder']}" for r in w.inventory["artifacts"]], [ALPHA, GAMMA, BETA])
        self.assertEqual(history[0]["id"], ALPHA)
        self.assertEqual(w.inventory["artifacts"][0]["changed"], "its table")
        self.assertIn(GAMMA, w.clustering["judged"]["clusters"][0]["members"])
        self.assertEqual(w.clustering["judged"]["placed_later"][0]["cluster"], "C1")
        w.inventory["artifacts"].reverse()
        sr.join_inventory(w.args, {"inventory:0": found["inventory:0"]}, w.inventory, [], w.clustering, w.rows, "2026-10-25")
        self.assertEqual([f"{r['repo']}/{r['folder']}" for r in w.inventory["artifacts"]], [BETA, GAMMA, ALPHA],
                         "a record read again keeps its place, whatever the README's order")
        for answer, why in (({"record": {"summary": "x"}}, "the record lacks"),
                            ({"record": record(notes="write to reader@example.invalid")}, "keeps out"),
                            ({"record": record(notes=CREDENTIAL)}, "keeps out"),
                            ({"record": record(), "cluster": "No such cluster"}, "chose none of the 1 clusters")):
            _, left = sr.join_inventory(w.args, {"inventory:1": answer}, w.inventory, [], w.clustering, w.rows, "2026-10-24")
            self.assertIn(why, left[GAMMA])

    def test_a_finder_s_words_that_hold_an_address_are_kept_out(self):
        w = self.world
        address = "write to reader@example.invalid"
        found = {"inventory:0": {"record": record(), "changed": "its table"},
                 "inventory:1": {"record": record(), "cluster": "C1", "cluster_why": address},
                 "candidates:0": {"cluster_candidates": [{**cluster_candidate(ALPHA, BETA, "held"), "why_it_matters": address}],
                                  "number_candidates": [{**number_candidate("probably-different-quantities", "frames"), "why": address},
                                                        {**number_candidate("contradiction", "accuracy"), "quote_b": address}]}}
        _, left = sr.join_inventory(w.args, found, w.inventory, [], w.clustering, w.rows, "2026-10-24")
        self.assertIn("keeps out", left[GAMMA], "a new artifact's reason for its cluster is the finder's words too")
        items, dropped = sr.found_items(w.args, found)
        self.assertEqual(items, [])
        self.assertEqual(len(dropped), 3, "a number no skeptic reads is listed as dropped too, since it is kept as a row")
        self.assertTrue(all("keeps out" in d["why"] for d in dropped))
        self.assertEqual(sr.kept_numbers(w.args, found, w.N, "2026-10-24"), 0)

    def test_a_run_whose_answers_came_back_in_part(self):
        w = self.world
        w.answer("inventory:0", {"record": record(), "changed": "its table"})
        w.answer("inventory:1", {"record": record(), "cluster": "C1", "cluster_why": "same topic"})
        w.answer("candidates:0", {"cluster_candidates": [cluster_candidate(ALPHA, BETA, "placed"),
                                                         cluster_candidate(ALPHA, BETA, "refused"),
                                                         cluster_candidate(ALPHA, "SchwingNet/nowhere-x1y2z3", "unknown"),
                                                         cluster_candidate(ALPHA, BETA, "invented")],
                                  "number_candidates": [number_candidate("contradiction", "whole-frame accuracy"),
                                                        number_candidate("probably-different-quantities", "frames scored")]})
        w.answer("candidates:1", {"cluster_candidates": [cluster_candidate(GAMMA, ALPHA, "unruled", kind="stale")],
                                  "number_candidates": []})
        out = printed(sa.batch, str(w.plan), str(w.answers), str(w.batches))
        self.assertEqual((out["batches"], out["items"], out["dropped"]), ("[0, 1, 2]", "6", "2"))
        listed = json.loads((w.batches / "batches.json").read_text(encoding="utf-8"))
        dropped = {d["key"]: d["why"] for d in listed["dropped"]}
        self.assertIn("does not know", dropped[f"new:{ALPHA}:cluster:2"])
        self.assertEqual(dropped[f"new:{ALPHA}:cluster:3"], "its first quote is not in the artifact it names")
        new = {"placed": f"new:{ALPHA}:cluster:0", "refused": f"new:{ALPHA}:cluster:1", "number": f"new:{ALPHA}:number:0",
               "unruled": f"new:{GAMMA}:cluster:0"}
        self.assertEqual([b["keys"] for b in listed["batches"]],
                         [["stale:C1|0", "unread:C1|1"], [new["placed"], new["refused"], new["number"]], [new["unruled"]]],
                         "the planned items and each finder's candidates are batched apart")
        w.answer("skeptic:0", {"items": [reading("stale:C1|0", "refuted"), reading("unread:C1|1", "updated-later"),
                                         reading("not:in:this:batch", "confirmed")]})
        w.answer("skeptic:1", {"items": [reading(new["placed"], "confirmed"),
                                         reading(new["refused"], "confirmed", explanation="ask reader@example.invalid"),
                                         reading(new["number"], "confirmed-contradiction"), reading(new["unruled"], "refuted")]})
        w.answer("skeptic:2", {"items": [reading(new["unruled"], "confirmed")]})
        counts = [printed(sa.recheck, str(w.batches), str(w.answers), str(b))["count"] for b in range(3)]
        self.assertEqual(counts, ["2", "3", "1"], "a skeptic's answer about another batch's item is not taken")
        held = {"holds": True, "hint_ok": True}
        w.answer("recheck:0", {"items": [reading("stale:C1|0", "refuted", **held), reading("unread:C1|1", "updated-later", **held)]})
        w.answer("recheck:1", {"items": [reading(new["placed"], "confirmed", **held), reading(new["refused"], "confirmed", **held),
                                         reading(new["number"], "updated-later", holds=True, hint_ok=False)]})
        w.answer("recheck:2", {"items": [reading(new["unruled"], "refuted", holds=False, hint_ok=True)]})
        disputes = [printed(sa.disputes, str(w.batches), str(w.answers), str(b))["count"] for b in range(3)]
        self.assertEqual(disputes, ["0", "1", "1"])
        w.answer("judge:1", {"rulings": [reading(new["number"], "updated-later", sided_with="re-checker")]})

        found = sr.results_by_label(str(w.answers))
        final, missing = sr.final_verdicts(listed["batches"], listed["items"], found)
        self.assertIn("not on its item's scale", missing["unread:C1|1"])
        self.assertEqual(missing[new["unruled"]], "disputed, and the judge gave no ruling")
        self.assertEqual(final[new["number"]]["read"], ["skeptic", "re-checker", "judge"])
        joined = sr.join_verdicts(listed["items"], final, missing, w.M, w.N, "2026-10-24")
        self.assertEqual(joined["placed"], 3)
        self.assertEqual(joined["waiting"], ["unread:C1|1"])
        self.assertEqual(joined["unread"], sorted([new["refused"], new["unruled"]]))
        self.assertIn("was not kept", missing[new["refused"]])

        c = w.M["clusters"][0]
        self.assertEqual(c["verdicts"][0]["verdict"], "refuted")
        self.assertEqual(c["verdicts"][0]["delta"]["earlier"]["verdict"], "confirmed")
        self.assertEqual(rc.later_words(c["verdicts"][0], c["candidates"][0]), "read again on 2026-10-24, was confirmed")
        self.assertIsNone(c["verdicts"][1], "an item with no verdict on its scale waits where it was")
        topics = [x["topic"] for x in c["candidates"][2:]]
        self.assertEqual(sorted(topics), ["placed", "refused", "unruled"])
        by_topic = dict(zip(topics, c["verdicts"][2:]))
        self.assertEqual(by_topic["placed"]["delta"]["read"], ["skeptic", "re-checker"])
        self.assertIsNone(by_topic["refused"])
        self.assertEqual(len(w.N["candidates"]), 1)
        extra = w.M["numbers_extra"][0]
        self.assertEqual((extra["verdict"], extra["delta"]["sided_with"]), ("updated-later", "re-checker"))
        self.assertEqual(sr.kept_numbers(w.args, found, w.N, "2026-10-24"), 1)
        rc.number_verdicts(w.N, w.M["numbers_extra"])

        later = sr.unread_rows(w.M, w.N)
        self.assertEqual(sorted(later), sorted(["C1|1"] + [f"C1|{2 + topics.index(t)}" for t in ("refused", "unruled")]))
        kept = w.N["candidates"][-1]
        self.assertEqual(rc.later_words(None, kept), "found on 2026-10-24, a kind no skeptic reads")
        words = "\n".join(rc.later_section(w.M, w.N, rc.number_verdicts(w.N, w.M["numbers_extra"])))
        self.assertIn("read 1 verdict again", words)
        self.assertIn("3 rows found wait for a verdict", words)
        self.assertIn("1 number collision of another scope or another quantity was added with none", words)

    def test_a_candidate_is_kept_only_where_the_artifacts_it_names_hold_its_quotes(self):
        x = cluster_candidate(ALPHA, BETA, "placed")
        self.assertIsNone(sr.quote_problem(x))
        self.assertEqual(sr.quote_problem({**x, "quote_b": "a passage beta never gave"}),
                         "its second quote is not in the artifact it names")
        self.assertEqual(sr.quote_problem({**x, "quote_a": "refused in b"}), "its first quote is not in the artifact it names",
                         "the other artifact's words are not its own")
        self.assertIsNone(sr.quote_problem({**x, "quote_a": "a figure only the data holds"}), "an artifact's own files count")
        self.assertIsNone(sr.quote_problem({**x, "artifact_b": "", "quote_b": ""}), "a side that names nothing is not checked")

    def test_only_the_fields_a_schema_gives_are_kept(self):
        number = {"value": "98.2%", "unit": "%", "n": None, "interval": None, "context": "c", "quote": "q", "added": "x"}
        kept = sr.trimmed(record(added="x", numbers=[number]))
        self.assertNotIn("added", kept)
        self.assertEqual(set(kept["numbers"][0]), set(number) - {"added"})
        self.assertEqual(set(sr.candidate_fields({**cluster_candidate(ALPHA, BETA, "placed"), "added": "x"}, sr.CLUSTER_FIELDS)),
                         set(sr.CLUSTER_FIELDS))

    def test_a_finder_s_row_that_is_listed_already_is_not_added_again(self):
        w = self.world
        key = f"new:{BETA}:cluster:0"
        item = {"key": key, "stratum": "C1", "index": None, "kind": "contradiction", "topic": "T!", "a": {"id": BETA},
                "b": {"id": ALPHA}, "statement_a": "b", "quote_a": "qb", "statement_b": "a", "quote_b": "qa", "why": "found"}
        rows = len(w.M["clusters"][0]["candidates"])
        joined = sr.join_verdicts({key: item}, {key: {**reading(key, "confirmed"), "read": ["skeptic", "re-checker"]}}, {},
                                  w.M, w.N, "2026-10-24")
        self.assertEqual((joined["already"], joined["placed"]), ([key], 0))
        self.assertEqual(len(w.M["clusters"][0]["candidates"]), rows, "its sides swapped, and its topic's case and marks, make no new row")

    def test_a_row_a_concept_check_made_settles_no_figure_of_its_own(self):
        it = {"key": "concept:k1", "quantity": "whole-frame accuracy", "a": {"id": ALPHA}, "b": {"id": GAMMA},
              "value_a": "98.2%", "quote_a": "98.2% of frames", "value_b": "97.0%", "quote_b": "97.0% of frames",
              "kind": "updated-later", "why": "a concept check"}
        made = sr.new_number_row(it, "2026-10-24")
        plain = sr.new_number_row({**it, "key": f"new:{ALPHA}:number:0", "b": {"id": BETA}}, "2026-10-24")
        self.assertEqual(made["delta"]["concept"], "k1")
        self.assertNotIn("concept", plain["delta"])
        fields = ("quantity", "artifact_a", "artifact_b", "value_a", "value_b", "quote_a", "quote_b")
        verdicts = [{**{f: row[f] for f in fields}, "verdict": "updated-later", "explanation": "e", "resolution_hint": "",
                     "delta": {"date": "2026-10-24"}} for row in (made, plain)]
        figures = sc.figure_concepts({"clusters": [], "numbers_extra": verdicts}, {"candidates": [made, plain], "verdicts": []},
                                     {"artifacts": []}, {})
        self.assertEqual([f["row"] for f in figures], [1])

    def test_a_join_whose_ledger_would_hold_an_address_writes_nothing(self):
        w = self.world
        w.answer("inventory:0", {"record": record(), "changed": "its table"})
        ledger = synth.load(synth.LEDGER)
        held = {**ledger, "checks": [{**ledger["checks"][0], "text": "write to reader@example.invalid"}, *ledger["checks"][1:]]}
        records = Path(self.scratch.name, "records")
        for name, data in (("inventory.json", w.inventory), ("clustering.json", w.clustering),
                           ("contradictions-merged.json", w.M), ("numbers-partial.json", w.N)):
            write(records / name, data)
        run = types.SimpleNamespace(inventory=w.inventory, clustering=w.clustering, M=w.M, N=w.N, text_dir=self.text_dir,
                                    without=set())
        with mock.patch.object(synth, "SYNTH", records), mock.patch.object(synth, "OUT", records), \
                mock.patch.object(synth, "readme_rows", return_value=w.rows), mock.patch.object(synth, "concepts_now", return_value=held), \
                mock.patch.object(synth, "save", side_effect=AssertionError("a record was written")), \
                self.assertRaises(SystemExit) as stopped:
            synth.join_run(run, {}, str(w.plan), str(w.answers), str(w.batches))
        self.assertIn("concepts refused", str(stopped.exception))

    def test_the_pull_request_s_body_holds_no_answer_s_words(self):
        w, mark = self.world, "Quokka"
        w.answer("inventory:0", {"record": record(summary=f"{mark} read again", notes=f"{mark} notes"), "changed": f"{mark} changed"})
        w.answer("inventory:1", {"record": record(summary=f"{mark} new"), "cluster": "No such cluster", "cluster_why": f"{mark} why"})
        w.answer("candidates:0", {"cluster_candidates": [{**cluster_candidate(ALPHA, BETA, "placed"), "why_it_matters": f"{mark} matters"},
                                                         cluster_candidate(ALPHA, BETA, f"{mark} invented")],
                                  "number_candidates": []})
        printed(sa.batch, str(w.plan), str(w.answers), str(w.batches))
        listed = json.loads((w.batches / "batches.json").read_text(encoding="utf-8"))
        found_key, held = f"new:{ALPHA}:cluster:0", {"holds": True, "hint_ok": True}
        w.answer("skeptic:0", {"items": [reading("stale:C1|0", "confirmed", explanation=f"{mark} again"),
                                         reading("unread:C1|1", "confirmed", explanation=f"{mark} at reader@example.invalid")]})
        w.answer("skeptic:1", {"items": [reading(found_key, "confirmed", explanation=f"{mark} e", resolution_hint=f"{mark} h")]})
        w.answer("recheck:0", {"items": [reading("stale:C1|0", "confirmed", **held), reading("unread:C1|1", "confirmed", **held)]})
        w.answer("recheck:1", {"items": [reading(found_key, "confirmed", **held)]})
        found = sr.results_by_label(str(w.answers))
        read, left = sr.join_inventory(w.args, found, w.inventory, [], w.clustering, w.rows, "2026-10-24")
        final, missing = sr.final_verdicts(listed["batches"], listed["items"], found)
        joined = sr.join_verdicts(listed["items"], final, missing, w.M, w.N, "2026-10-24")
        run = types.SimpleNamespace(text_dir=self.text_dir)
        summary = {"date": "2026-10-24", "read": read, "left": left, "waiting_artifacts": [], **joined,
                   "missing": {k: missing[k] for k in joined["waiting"] + joined["unread"] if k in missing},
                   "items_waiting": [], "dropped": listed["dropped"], "kept_numbers": sr.kept_numbers(w.args, found, w.N, "2026-10-24"),
                   "unfound_quotes": synth.unfound_quotes(run, listed["items"], final, joined["placed_keys"])}
        self.assertTrue(all(summary[k] for k in ("read", "left", "missing", "dropped", "unfound_quotes")), "each list has entries")
        path = Path(self.scratch.name, "summary.json")
        write(path, summary)
        for text in (sa.body(str(path), "https://github.com/o/r/actions/runs/11"), sa.message(str(path))):
            self.assertNotIn(mark.lower(), text.lower())


def empty_status():
    return {"changes": [], "stale": [], "resolved": [], "lost_quotes": {}, "new_checks": [], "gone_checks": 0, "unread": [],
            "delta": {k: [] for k in ("new", "gone", "datasets_new", "datasets_changed", "datasets_gone")},
            "stamped": "2026-10-23", "date": "2026-10-24", "heads": {"SchwingNet": "a" * 40}, "without": []}


class Records(unittest.TestCase):
    def test_a_record_is_written_as_the_first_reading_wrote_it(self):
        with tempfile.TemporaryDirectory() as folder:
            for name, first in (("ends.json", "{}\n"), ("bare.json", "{}"), ("new.json", None)):
                path = Path(folder, name)
                if first is not None:
                    path.write_text(first, encoding="utf-8")
                synth.save(path, {"quote": "98.2 % \u2013 100 %"})
                text = path.read_text(encoding="ascii")
                self.assertEqual(text, '{\n "quote": "98.2 % \\u2013 100 %"\n}' + ("" if name == "bare.json" else "\n"), name)


class Stamp(unittest.TestCase):
    """What a join and a stamp take as read: the checks a row answers already, the checks a join
    takes as seen, the verdicts whose quotes are not where they should be, an artifact gone by
    its record, and the refusals that keep a stamp from saying more than was read."""

    def test_a_figure_check_whose_row_the_table_holds_is_covered(self):
        figure = {"id": "figure:0", "quantity": "Whole-frame accuracy", "artifacts": [ALPHA, BETA],
                  "values": [{"figure": "98.2", "percent": True, "status": "superseded", "side": "a"},
                             {"figure": "97.4", "percent": True, "status": "current", "side": "b"}]}
        check = {"key": "k1", "kind": "figure", "outcome": "superseded", "concept": "figure:0", "source": GAMMA, "value": "98.2%"}
        ledger = {"figures": [figure], "checks": [check, {**check, "key": "k2", "outcome": "differs"},
                                                  {**check, "key": "k3", "source": "SchwingNet/other-page-j1k2l3"}]}
        rows = {"candidates": [{"artifact_a": GAMMA, "artifact_b": BETA, "quantity": "whole-frame accuracy "}]}
        self.assertEqual(synth.covered_checks(ledger, rows), {"k1"})

    def test_a_verdict_on_a_row_already_there_is_something_to_write(self):
        nothing = {"read": [], "placed": 0, "already": []}
        self.assertFalse(synth.came_back(nothing))
        for change in ({"already": ["concept:k1"]}, {"placed": 1}, {"read": [ALPHA]}):
            self.assertTrue(synth.came_back({**nothing, **change}), change)

    def test_a_join_takes_as_seen_what_it_read_and_drops_what_no_text_gives(self):
        state = {"checks": {"old": ALPHA, "ghost": ALPHA}}
        ledger = {"checks": [{"key": k, "source": src} for k, src in
                             (("old", ALPHA), ("read", BETA), ("placed", GAMMA), ("waits", BETA), ("other", GAMMA))]}
        seen = synth.seen_after(state, ledger, read={BETA}, placed={"placed"}, waiting={"waits"})
        self.assertEqual(seen, {"old": ALPHA, "read": BETA, "placed": GAMMA})

    def test_a_verdict_whose_quote_is_not_in_its_own_artifact_is_listed(self):
        with tempfile.TemporaryDirectory() as folder, texts(folder, FOUND_TEXTS) as text_dir:
            items = {k: {"a": {"id": ALPHA}, "b": {"id": BETA}} for k in ("held", "other", "nowhere")}
            final = {"held": {"quote_a": "placed in a", "quote_b": "placed in b"},
                     "other": {"quote_a": "placed in b", "quote_b": "placed in b"},
                     "nowhere": {"quote_a": "placed in a", "quote_b": "a passage no page gives"}}
            unfound = synth.unfound_quotes(types.SimpleNamespace(text_dir=text_dir), items, final, ["held", "other", "nowhere"])
            self.assertEqual(unfound, ["other", "nowhere"])

    def test_a_quote_its_artifact_holds_only_by_a_window_is_held_in_part(self):
        page = "The level model named every vertebra on the held-out films with 98.2% of frames right."
        with tempfile.TemporaryDirectory() as folder, texts(folder, {ALPHA: page, BETA: "Another page."}) as text_dir:
            self.assertEqual(st.quote_place(text_dir, page, ALPHA, BETA), "own")
            self.assertEqual(st.quote_place(text_dir, page.replace("98.2", "97.0"), ALPHA, BETA), "own-in-part",
                             "a changed figure inside a long quote leaves its first 48 characters whole")
            self.assertEqual(st.quote_place(text_dir, "with 97.0% of frames right", ALPHA, BETA), "absent")
            self.assertEqual(st.quote_place(text_dir, "", ALPHA, BETA), "empty")

    def test_an_artifact_is_gone_while_its_record_stands_whatever_the_stamp_says(self):
        state = {"artifacts": {ALPHA: "t1", BETA: "t2"}, "datasets": {}}
        self.assertEqual(st.delta(state, {ALPHA: "t1"}, {}, recorded={ALPHA, BETA})["gone"], [BETA])
        self.assertEqual(st.delta(state, {ALPHA: "t1"}, {}, recorded={ALPHA})["gone"], [], "its record taken out, it is listed no more")
        self.assertEqual(st.delta({"artifacts": {ALPHA: "t1"}}, {ALPHA: "t1"}, {}, recorded={ALPHA, BETA})["gone"], [BETA],
                         "a stamp that no longer lists its tree does not hide it")

    def test_a_join_refuses_a_new_string_the_rule_keeps_out(self):
        before = ({"notes": "write to reader@example.invalid"},)
        synth.refuse_what_the_rule_keeps_out(before, ({"notes": "write to reader@example.invalid", "more": "fine"},))
        with self.assertRaises(SystemExit) as stopped:
            synth.refuse_what_the_rule_keeps_out(before, ({"notes": "write to reader@example.invalid", "more": "or other@example.invalid"},))
        self.assertIn("join refused", str(stopped.exception))

    def test_what_writes_every_text_s_word_refuses_to_run_without_a_checkout(self):
        for command, paths in (("concepts", []), ("plan", []), ("join", []), ("stamp", []), ("rekey", ["base"])):
            with self.assertRaises(SystemExit) as stopped, mock.patch.object(synth, "Run", side_effect=AssertionError("it ran")):
                synth.main([command, *paths, "--without", "symphony-template"])
            self.assertIn(f"{command} refused", str(stopped.exception))

    def test_a_ledger_or_page_that_holds_an_address_is_not_written(self):
        ledger, state = synth.load(synth.LEDGER), synth.load(synth.STATE)
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(synth, "LEDGER", Path(folder, "concepts.json")), \
                mock.patch.object(synth, "PAGE", Path(folder, "concepts.md")):
            synth.write_concepts(ledger, state)
            self.assertEqual(synth.load(synth.LEDGER), ledger)
            Path(folder, "concepts.json").unlink()
            Path(folder, "concepts.md").unlink()
            held = {**ledger, "checks": [{**ledger["checks"][0], "text": "write to reader@example.invalid"}, *ledger["checks"][1:]]}
            with self.assertRaises(SystemExit) as stopped:
                synth.write_concepts(held, state)
            self.assertIn("concepts refused", str(stopped.exception))
            self.assertEqual(sorted(os.listdir(folder)), [], "neither the ledger nor its page was written")

    def test_a_stamp_takes_its_trees_only_at_the_commit_its_checkout_is_at(self):
        with tempfile.TemporaryDirectory() as clone:
            git(clone, "init", "-q")
            for word in ("one", "two"):
                Path(clone, "f").write_text(word, encoding="utf-8")
                git(clone, "add", "f")
                git(clone, "commit", "-q", "-m", word)
            run = types.SimpleNamespace(clones={"SchwingNet": clone})
            synth.at_head(run, {"SchwingNet": "HEAD"})
            for at, words in (({"SchwingNet": "HEAD~1"}, "its checkout is at"), ({"elsewhere": "HEAD"}, "not one of")):
                with self.assertRaises(SystemExit) as stopped:
                    synth.at_head(run, at)
                self.assertIn(words, str(stopped.exception))


class Rekey(unittest.TestCase):
    """synth.py rekey, which carries the stamp's word over a change that renames the concept
    checks' keys and not what they check, as a change to what the scrub takes out does."""

    def test_the_stamp_s_word_goes_with_each_check_to_its_new_key(self):
        def ledger(*checks):
            return {"checks": [{"key": key, "concept": "dataset:x:films", "kind": "dataset", "source": ALPHA, "line": line,
                                "outcome": "agrees", "value": "100"} for key, line in checks]}
        # a and b are one check on each side, b under a new key; line 3 gives two checks on each
        # side, which pair with neither; d is gone and e is new.
        old = ledger(("a", 1), ("b", 2), ("c1", 3), ("c2", 3), ("d", 4))
        new = ledger(("a", 1), ("b2", 2), ("c3", 3), ("c4", 3), ("e", 5))
        pairs = synth.paired(old, new)
        self.assertEqual(pairs, {"a": "a", "b": "b2"})
        checks, renamed = synth.rekeyed({"d": ALPHA, "c1": ALPHA, "b": ALPHA, "a": ALPHA}, pairs)
        self.assertEqual(checks, {"a": ALPHA, "b2": ALPHA, "c1": ALPHA, "d": ALPHA})
        self.assertEqual(list(checks), sorted(checks), "the stamp's checks stay sorted")
        self.assertEqual(renamed, 1)
        with self.assertRaises(SystemExit):
            synth.rekeyed({"a": ALPHA, "b": ALPHA, "b2": ALPHA}, pairs)

    def test_a_check_pairs_only_with_one_that_is_the_same_in_all_but_its_key(self):
        old = {"key": "a", "concept": "figure:x", "kind": "figure", "source": ALPHA, "line": 1, "outcome": "superseded",
               "value": "98.2%"}
        self.assertEqual(synth.paired({"checks": [old]}, {"checks": [{**old, "key": "b"}]}), {"a": "b"})
        for field, other in (("concept", "figure:y"), ("kind", "dataset"), ("source", BETA), ("line", 2), ("outcome", "open"),
                             ("value", "97.4%")):
            self.assertEqual(synth.paired({"checks": [old]}, {"checks": [{**old, "key": "b", field: other}]}), {}, field)

    TEXTS = {"artifacts/alpha-page/index.md": "98.2% of frames\n", "docs/research/note.md": "a note\n",
             "data/sources/x.json": "{}\n"}

    def clean_git(self):
        """The process's environment with no git variable but the suite's own, as a hook that runs
        the tests may set one that names another repository."""
        return mock.patch.dict(os.environ, {**{k: v for k, v in os.environ.items() if not k.startswith("GIT_")}, **GIT_ENV},
                               clear=True)

    def checkout(self, folder, files):
        """A checkout of this repository's shape, the files given and the tools' entry point in
        it, everything committed."""
        git(folder, "init", "-q")
        for key, value in QUIET.items():
            git(folder, "config", key, value)
        records = {name: "{}\n" for name in synth.CONCEPT_RECORDS}
        for name, text in {**records, **files, "artifacts/_synthesis/work/tools/synth.py": "# the tools\n"}.items():
            Path(folder, name).parent.mkdir(parents=True, exist_ok=True)
            Path(folder, name).write_text(text, encoding="utf-8")
        git(folder, "add", "-A")
        git(folder, "commit", "-q", "-m", "texts")

    def refused(self, base, words):
        with self.assertRaises(SystemExit) as stopped:
            synth.rekey(None, {}, base)
        self.assertIn(words, str(stopped.exception))

    def test_a_rekey_reads_the_same_texts_on_both_sides_or_writes_nothing(self):
        with tempfile.TemporaryDirectory() as here, tempfile.TemporaryDirectory() as base, self.clean_git(), \
                mock.patch.object(synth, "ROOT", Path(here)), \
                mock.patch.object(synth, "concepts_now", side_effect=AssertionError("this checkout's ledger was made")), \
                mock.patch.object(synth, "ledger_of", side_effect=AssertionError("the base's ledger was made")):
            for folder in (here, base):
                self.checkout(folder, self.TEXTS)
            self.assertEqual(sorted(synth.text_trees(here, "here")),
                             sorted(["SchwingNet/alpha-page", "data/sources", "docs/research", *synth.CONCEPT_RECORDS]))
            Path(here, "artifacts", "_synthesis", "state.json").write_text("{}\n", encoding="utf-8")
            os.symlink("../inventory.json", Path(here, "artifacts", "_synthesis", "work", "linked.json"))
            git(here, "add", "artifacts/_synthesis/work/linked.json")
            git(here, "commit", "-q", "-m", "a link among the records, which are no text")
            synth.same_texts(base)
            for path, key in (("artifacts/alpha-page/index.md", "SchwingNet/alpha-page"), ("docs/research/note.md", "docs/research"),
                              ("data/sources/x.json", "data/sources")):
                Path(here, path).write_text("edited in place\n", encoding="utf-8")
                self.refused(base, "this checkout holds a change to the texts the checks read, or to the records")
                git(here, "commit", "-q", "-am", "an edit")
                self.refused(base, f"differ between this checkout and {base} in {key};")
                git(here, "reset", "-q", "--hard", "HEAD~1")
            numbers = "artifacts/_synthesis/work/out/numbers-partial.json"
            self.assertIn(numbers, synth.CONCEPT_RECORDS)
            Path(here, numbers).write_text('{"candidates": []}\n', encoding="utf-8")
            self.refused(base, "this checkout holds a change to the texts the checks read, or to the records")
            git(here, "commit", "-q", "-am", "the figures numbered again")
            self.refused(base, f"in {numbers};")
            git(here, "reset", "-q", "--hard", "HEAD~1")
            Path(here, "outside.md").write_text("a text no tree of the texts holds\n", encoding="utf-8")
            for link, to in (("artifacts/alpha-page/linked.md", "../../outside.md"), ("artifacts/linked-page", "../docs"),
                             ("docs/research/linked.md", "../../outside.md")):
                os.symlink(to, Path(here, link))
                git(here, "add", link)
                git(here, "commit", "-q", "-m", "a link")
                self.refused(base, "this checkout holds 1 links or submodules among the texts")
                git(here, "reset", "-q", "--hard", "HEAD~1")
            git(here, "update-index", "--add", "--cacheinfo", f"160000,{git(here, 'rev-parse', 'HEAD')},artifacts/a-submodule")
            Path(here, "artifacts", "a-submodule").mkdir()
            git(here, "commit", "-q", "-m", "a submodule")
            self.refused(base, "this checkout holds 1 links or submodules among the texts")
            git(here, "reset", "-q", "--hard", "HEAD~1")
            if Path(here, "artifacts", "a-submodule").exists():  # git may leave the empty folder behind
                Path(here, "artifacts", "a-submodule").rmdir()
            Path(here, "outside.md").unlink()
            git(base, "mv", "docs", "elsewhere")
            os.symlink("elsewhere", Path(base, "docs"))
            git(base, "add", "-A")
            git(base, "commit", "-q", "-m", "the notes behind a link")
            self.refused(base, f"{base} holds no tree at docs/research")
            git(base, "reset", "-q", "--hard", "HEAD~1")
            Path(base, "artifacts", "an-empty-page").mkdir()
            self.refused(base, f"{base} holds 1 folders under artifacts/ that no tree holds")
            Path(base, "artifacts", "an-empty-page").rmdir()
            Path(base, "artifacts", "alpha-page", "extra.md").write_text("a file of its own\n", encoding="utf-8")
            self.refused(base, f"{base} holds a change to the texts")
            Path(base, ".gitignore").write_text("*.pyc\n", encoding="utf-8")
            Path(base, "artifacts", "alpha-page", "extra.md").rename(Path(base, "artifacts", "alpha-page", "extra.pyc"))
            self.refused(base, f"{base} holds a change to the texts")
            Path(base, "artifacts", "alpha-page", "extra.pyc").unlink()
            Path(base, "artifacts", "beta-page").mkdir()
            Path(base, "artifacts", "beta-page", "index.md").write_text("a page main has\n", encoding="utf-8")
            git(base, "add", "-A")
            git(base, "commit", "-q", "-m", "a page")
            self.refused(base, "in SchwingNet/beta-page;")
            git(base, "reset", "-q", "--hard", "HEAD~1")
            synth.same_texts(base)
            inner = Path(here, "copy")
            (inner / "artifacts" / "_synthesis" / "work" / "tools").mkdir(parents=True)
            (inner / "artifacts" / "_synthesis" / "work" / "tools" / "synth.py").write_text("# the tools\n", encoding="utf-8")
            with tempfile.TemporaryDirectory() as elsewhere:
                for folder in (inner, elsewhere):
                    self.refused(str(folder), "is not a checkout of this repository")

    def test_a_run_names_its_checkouts_and_texts_by_whole_paths(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, {"SYNTH_TEXT": "texts", "SYNTH_SYMPHONY": "symphony"}):
            Path(folder, "symphony", "artifacts").mkdir(parents=True)
            with contextlib.chdir(folder):
                run = synth.Run(without={"SchwingNet"})
            for path in (run.clones["symphony-template"], run.text_dir, os.environ["SYNTH_SYMPHONY"], os.environ["SYNTH_TEXT"]):
                self.assertTrue(os.path.isabs(path), "a process that starts in another folder, as rekey's base does, finds it")
            self.assertTrue(os.path.samefile(run.clones["symphony-template"], Path(folder, "symphony")))

    def test_the_base_s_ledger_comes_from_its_own_tools_and_its_own_texts(self):
        mine = {"SYNTH_TEXT": "this checkout's texts", "SYNTH_SCHWINGNET": "this checkout"}
        with tempfile.TemporaryDirectory() as base, self.clean_git(), mock.patch.dict(os.environ, mine):
            self.checkout(base, {})
            tools = Path(base, "artifacts", "_synthesis", "work", "tools")
            (tools / "synth.py").write_text(
                "import os, tempfile\n"
                "class Run:\n"
                "    def __init__(self):\n"
                "        self.text_dir = os.environ.get('SYNTH_TEXT') or tempfile.mkdtemp(prefix='synth-text-')\n"
                "        os.makedirs(self.text_dir, exist_ok=True)\n"
                "def concepts_now(run):\n"
                "    return {'checks': [], 'texts': run.text_dir, 'tools': __file__,\n"
                "            'checkout': os.environ.get('SYNTH_SCHWINGNET')}\n", encoding="utf-8")
            got = synth.ledger_of(base)
            self.assertIsNone(got["checkout"], "the base's tools name their own checkout, not this one")
            self.assertEqual(Path(got["tools"]).resolve(), (tools / "synth.py").resolve())
            self.assertEqual(Path(got["texts"]).name, "texts", "the base's texts are extracted where ledger_of says")
            self.assertFalse(Path(got["texts"]).exists(), "and go with its ledger")
            (tools / "synth.py").write_text("raise SystemExit(3)\n", encoding="utf-8")
            with self.assertRaises(SystemExit) as stopped:
                synth.ledger_of(base)
            self.assertIn("gave no ledger (exit 3)", str(stopped.exception))
        with tempfile.TemporaryDirectory() as elsewhere, self.assertRaises(SystemExit) as stopped:
            synth.ledger_of(elsewhere)
        self.assertIn("is not a checkout of this repository", str(stopped.exception))
        with self.assertRaises(SystemExit) as stopped, contextlib.redirect_stderr(io.StringIO()), \
                mock.patch.object(synth, "Run", side_effect=AssertionError("it ran")):
            synth.main(["rekey"])
        self.assertEqual(stopped.exception.code, 2, "rekey takes the base's checkout")


class Report(unittest.TestCase):
    def test_an_issue_is_opened_only_for_what_the_stamp_had_not_seen(self):
        body, marker, anything = synth.report(empty_status())
        self.assertFalse(anything)
        self.assertTrue(body.startswith(f"<!-- synthesis-report: {marker} -->"))
        s = empty_status()
        s["changes"] = [{"id": ALPHA, "new": False, "hunks": [1], "added": 2, "removed": 1}]
        s["new_checks"] = [{"key": "k", "concept": "dataset:x:films", "kind": "dataset", "source": ALPHA, "line": 3,
                            "outcome": "differs", "value": "120", "text": f"120 films under /rs/lab/{LOGIN}/data/x and {LOGIN}@wayne"}]
        body2, marker2, anything2 = synth.report(s)
        self.assertTrue(anything2)
        self.assertNotEqual(marker, marker2)
        self.assertIn("## Reads waiting: 2", body2)
        self.assertNotIn(LOGIN, body2)
        self.assertTrue(body2.isascii())

    def test_the_issue_is_rewritten_whenever_what_it_says_changes(self):
        s = empty_status()
        s["changes"] = [{"id": ALPHA, "new": False, "hunks": [1], "added": 2, "removed": 1}]
        body, marker, _ = synth.report(s)
        later, later_marker, _ = synth.report({**s, "date": "2026-10-25", "heads": {"SchwingNet": "b" * 40}})
        self.assertNotEqual(body, later, "the run line names the run that wrote the issue")
        self.assertEqual(marker, later_marker, "a run that would write the same leaves the issue as it is")
        for change in ({"gone_checks": 1}, {"unread": ["C1|0"]}, {"resolved": [{"row": "C1|1"}]},
                       {"without": ["symphony-template"]}, {"stamped": "2026-10-24"}):
            self.assertNotEqual(marker, synth.report({**s, **change})[1], f"{change} changes what the issue says")

    def test_the_marker_is_made_from_the_scrubbed_report(self):
        def status(text):
            s = empty_status()
            s["new_checks"] = [{"key": "k", "concept": "dataset:x:films", "kind": "dataset", "source": ALPHA, "line": 3,
                                "outcome": "differs", "value": "120", "text": text}]
            return s
        body, marker, _ = synth.report(status(f"120 films under {LOGIN}"))
        self.assertNotIn(LOGIN, body)
        self.assertEqual(marker, synth.report(status("120 films under [the owner's login]"))[1],
                         "the marker gives away nothing the scrub took out")
        rule = ("a word the scrub keeps out from now on", re.compile(r"\bfilms\b"), "[a word]")
        with mock.patch.object(redact, "RULES", redact.RULES + [rule]):
            self.assertNotEqual(marker, synth.report(status(f"120 films under {LOGIN}"))[1], "a change to the scrub reaches the issue")

    def test_the_run_line_names_the_commit_of_main_the_workflow_gives(self):
        with tempfile.TemporaryDirectory() as folder:
            git(folder, "init", "-q", "repo")
            git(Path(folder, "repo"), "commit", "-q", "--allow-empty", "-m", "the records laid on main, on the runner")
            local = git(Path(folder, "repo"), "rev-parse", "HEAD").strip()
            run = types.SimpleNamespace(clones={"SchwingNet": str(Path(folder, "repo")), "symphony-template": str(Path(folder, "repo"))},
                                        without=set())
            main = "c" * 40
            for given, named in ((main, main), ("", local), ("not a commit", local), (main[:7], local)):
                with mock.patch.dict(os.environ, {"SYNTH_MAIN": given}):
                    self.assertEqual(synth.heads(run), {"SchwingNet": named, "symphony-template": local}, given)
            run.without = {"symphony-template"}
            with mock.patch.dict(os.environ, {"SYNTH_MAIN": main}):
                self.assertEqual(synth.heads(run), {"SchwingNet": main})
            # The look names them so, read here from records that hold nothing.
            run.trees, run.records, run.skipped = (lambda state, at=None: {}), dict, (lambda aid: aid.startswith("symphony-template/"))
            run.M, run.N, run.text_dir = {"clusters": [], "numbers_extra": []}, {"candidates": [], "verdicts": [], "finders": []}, folder
            with mock.patch.dict(os.environ, {"SYNTH_MAIN": main}):
                self.assertEqual(synth.status(run, {})["heads"], {"SchwingNet": main})
        self.assertIn("SYNTH_MAIN: ${{ steps.base.outputs.main }}", WORKFLOW.read_text(encoding="utf-8"))


class Scrub(unittest.TestCase):
    def test_what_the_folder_s_rule_keeps_out_is_replaced_and_names_and_ids_are_kept(self):
        cases = [
            (f"grid {LOGIN}@wayne, branch L6_Class", "grid [the owner's login], branch L6_Class"),
            (f"python at /rs/rs_grp_lab/{LOGIN}/envs/py312", "python at [a grid folder named by a login]/envs/py312"),
            (f"/rs/rs_grp_lab/{LOGIN}/data/or_ready", "[the lab volume's data root]/or_ready"),
            (f"account: {LOGIN}", "account: [the owner's login]"),
            (f"{FIRST}'s decision of 21 Oct", "[the owner]'s decision of 21 Oct"),
            ("register at forms.gle/AbC123xyz", "register at [the registration form's link]"),
            ("apply at https://docs.google.com/forms/d/e/1FAIpQLSe-x_y/viewform?usp=sf_link today",
             "apply at [a form's link] today"),
            # A prefilled link carries its answers in the link, so a long one is taken out whole.
            ("apply at https://docs.google.com/forms/d/e/1FAIpQLSe-x_y/viewform?usp=pp_url&entry.1=" + "a" * 6_000 + " today",
             "apply at [a form's link] today"),
            ("the volume /rs/rs_grp_lab/shared/x", "the volume [the lab volume]/shared/x"),
            ("Spinal ai2024 has 20000 films", "Spinal ai2024 has 20000 films"),
            (f"artifacts/the-lab-recipe-{LOGIN}/index.html", f"artifacts/the-lab-recipe-{LOGIN}/index.html"),
        ]
        for before, after in cases:
            self.assertEqual(redact.scrub(before, Counter()), after, before)
        value = {"folder": f"page-{LOGIN}", "account": LOGIN, "quotes": [f"{FIRST} ran it"]}
        self.assertEqual(synth.scrubbed(value), {"folder": f"page-{LOGIN}", "account": "[the owner's login]",
                                                 "quotes": ["[the owner] ran it"]})

    def test_a_scrubbed_quote_is_still_found_in_its_source(self):
        source = f"The overnight run on the grid under {LOGIN} took the whole night and gave every level a count."
        quote = synth.scrubbed(source)
        self.assertNotIn(LOGIN, quote)
        self.assertIn(vq.found_in(quote, vq.norm(source)), vq.HIT)

    def test_the_address_pattern_takes_a_long_run_in_linear_time(self):
        self.assertTrue(extract.EMAIL_RE.search("write to reader@example.invalid"))
        started = time.monotonic()
        self.assertIsNone(extract.EMAIL_RE.search("a" * 100_000))
        self.assertLess(time.monotonic() - started, 2, "an unbounded run before the @ took seconds, quadratic in its length")

    def test_the_grid_folder_rule_takes_a_long_run_of_path_parts_in_linear_time(self):
        self.assertEqual(redact.scrub(f"at /home/lab/{LOGIN}/envs", Counter()), "at [a grid folder named by a login]/envs")
        started = time.monotonic()
        self.assertEqual(redact.scrub("/abcde" * 8_000, Counter()), "/abcde" * 8_000)
        self.assertLess(time.monotonic() - started, 2, "the rule tried every run of path parts again from each slash")

    def test_the_secrets_page_rule_takes_a_long_run_of_links_in_linear_time(self):
        page = "https://github.com/o/r/settings/secrets/actions"
        self.assertEqual(redact.scrub(f"add it at {page} today", Counter()), "add it at [a repository's Actions secrets page] today")
        started = time.monotonic()
        self.assertEqual(redact.scrub("https://github.com/o/r" * 16_000, Counter()), "https://github.com/o/r" * 16_000)
        self.assertLess(time.monotonic() - started, 2, "the rule read the rest of the run again from each link")

    def test_the_report_scrubs_a_passage_and_a_quote_before_it_cuts_them(self):
        for kept in range(2, len(LOGIN)):
            text = ("the run took the night " * 9)[:160 - kept - 1] + f" {LOGIN} and gave every level a count"
            s = empty_status()
            s["new_checks"] = [{"key": "k", "concept": "dataset:x:films", "kind": "dataset", "source": ALPHA, "line": 3,
                                "outcome": "differs", "value": "120", "text": text}]
            s["lost_quotes"] = {ALPHA: {"q": text}}
            body = synth.report(s)[0]
            self.assertIn(" " + "[the owner's login]"[:kept].rstrip() + "`", body, "the scrub's words, cut where the login stood")
            self.assertNotIn(LOGIN[:kept], body, f"the cut at 160 kept {kept} characters of the login")


class Extract(unittest.TestCase):
    """Where extract.py cuts an artifact's text to a length: never through what it or the scrub
    takes out, an address, a phone number, a login or a grid path, since a piece of one is
    found by no pattern and would pass every scrub after."""

    ITEMS = (LOGIN, f"/rs/rs_grp_lab/{LOGIN}/data/", "zq@ex.invalid", "(555) 010-0199")

    def test_a_cut_goes_back_to_the_start_of_what_it_would_split(self):
        self.assertEqual(extract.clip("short", 600), "short")
        for item in self.ITEMS:
            text = "the run took the night " * 3 + item + " and the rest"
            start = text.index(item)
            for kept in range(1, len(item)):
                self.assertEqual(extract.clip(text, start + kept), text[:start], f"{kept} characters of {item!r}")
            self.assertEqual(extract.clip(text, start), text[:start])
            self.assertEqual(extract.clip(text, start + len(item)), text[:start + len(item)], "a cut after it keeps it whole")
        # The address goes back to its start, where the folder that names the login stands across
        # the cut again, so the cut goes back once more.
        self.assertEqual(extract.clip(f"/home/lab/{LOGIN}@ex.invalid and the rest", 20), "")
        # The longest grid path the rule takes, 32 folders of 255 characters, is seen whole from a
        # cut in its first folder.
        path = "the run " + ("/" + "a" * 255) * 32 + f"/{LOGIN}/data and the rest"
        self.assertEqual(extract.clip(path, path.index("/") + 100), "the run ")

    def test_nothing_a_cut_guards_runs_as_far_as_the_cut_looks(self):
        for pattern in extract.TAKEN_OUT:
            longest = re._parser.parse(pattern.pattern, pattern.flags).getwidth()[1]
            self.assertLess(longest, extract.REACH, pattern.pattern)

    def test_a_folder_s_text_holds_no_address_and_no_phone_number(self):
        with tempfile.TemporaryDirectory() as folder:
            artifact = Path(folder, "artifact")
            artifact.mkdir()
            (artifact / "page.html").write_text("<p>write to zq@ex.invalid or call (555) 010-0199</p>", encoding="utf-8")
            (artifact / "notes.md").write_text("zq@ex.invalid, (555) 010-0199\n", encoding="utf-8")
            (artifact / "from-zq@ex.invalid.txt").write_text("a note\n", encoding="utf-8")
            extract.extract_folder(artifact, Path(folder, "out.txt"))
            text = Path(folder, "out.txt").read_text(encoding="utf-8")
        self.assertIn("write to [address removed] or call [phone removed]", text)
        self.assertNotIn("zq@", text)
        self.assertNotIn("010-0199", text)

    def test_a_cut_reads_no_further_past_itself_than_what_it_guards_runs(self):
        text = "the run took the night " * 200_000
        started = time.monotonic()
        self.assertEqual(extract.clip(text, 3000), text[:3000])
        self.assertLess(time.monotonic() - started, 0.5, "a head of 3,000 characters read the whole data file")

    def test_no_cut_of_an_artifact_s_text_leaves_a_piece_of_what_is_taken_out(self):
        sites = {
            "a script's line, cut at 600": lambda b, item: {"page.html": f'<script>\n"{b(599)}{item} and the rest"\n</script>'},
            "an image's address, cut at 200": lambda b, item: {"page.html": f'<p>a page</p><img src="{b(200)}{item} rest" alt="x">'},
            "an embedded design file, cut at 200,000": lambda b, item: {"design.html": "<script>" + json.dumps(
                {"content": {"files": {"notes.md": b(200_000) + item + " and the rest"}}}) + "</script>"},
            "a data file's head, cut at 3,000": lambda b, item: {"data.js": b(3000) + item + " and the rest"},
            "a long file, cut at 400,000": lambda b, item: {"notes.md": b(400_000) + item + " and the rest"},
        }
        for item in self.ITEMS:
            kept = len(item) // 2

            def before(n):
                # So many characters that the item, put after them, starts kept characters before n.
                return ("the run took the night " * (n // 20 + 2))[:n - kept - 1] + " "

            for site, files in sites.items():
                with tempfile.TemporaryDirectory() as folder:
                    for name, text in files(before, item).items():
                        Path(folder, "artifact").mkdir(exist_ok=True)
                        Path(folder, "artifact", name).write_text(text, encoding="utf-8")
                    extract.extract_folder(Path(folder, "artifact"), Path(folder, "out.txt"))
                    text = Path(folder, "out.txt").read_text(encoding="utf-8")
                scrubbed = redact.scrub(extract.without_contacts(text), Counter())
                self.assertIn("the run took the night", scrubbed, f"{site} was read")
                self.assertNotIn(item[:kept], scrubbed, f"{site} kept {kept} characters of {item!r}")


SHARED = [{"id": f"dataset:{d}:films", "dataset": d, "name": d, "key": "films", "value": v, "noun": "films",
           "aliases": ["shared name"]} for d, v in (("alpha_set", "100"), ("beta_set", "200"))]
SHARED_TEXTS = {ALPHA: "The Shared Name set holds 200 films in all.", BETA: "Shared Name: 100 films were read."}


class Concepts(unittest.TestCase):
    def test_a_figure_near_a_name_two_sets_share_is_checked_against_both(self):
        checks = sc.check_datasets(SHARED_TEXTS, SHARED)
        self.assertEqual(sorted((c["source"], c["concept"], c["outcome"]) for c in checks),
                         [(ALPHA, "dataset:beta_set:films", "agrees"), (BETA, "dataset:alpha_set:films", "agrees")])

    def test_the_checks_do_not_depend_on_the_hash_seed(self):
        script = ("import json, sys; sys.path.insert(0, sys.argv[1]); import synth_concepts as sc; "
                  "print(json.dumps(sc.check_datasets(json.loads(sys.argv[2]), json.loads(sys.argv[3])), sort_keys=True))")
        outputs = set()
        for seed in ("0", "1", "2", "3"):
            env = {**os.environ, "PYTHONHASHSEED": seed}
            done = subprocess.run([sys.executable, "-B", "-c", script, str(TOOLS), json.dumps(SHARED_TEXTS), json.dumps(SHARED)],
                                  capture_output=True, text=True, env=env, check=True)
            outputs.add(done.stdout)
        self.assertEqual(len(outputs), 1)

    def test_a_figure_is_set_first_against_the_count_whose_words_follow_it(self):
        counts = [{"id": f"dataset:x:{key}", "key": key, "noun": "films", "value": value}
                  for key, value in (("ap_films", "3600"), ("lateral_films", "3610"))]
        outcome, hit = sc.count_outcome(Decimal("3603"), False, {"lateral", "films"}, counts)
        self.assertEqual((outcome, [c["key"] for c in hit]), ("differs", ["lateral_films"]),
                         "3,603 lateral films is not the AP count of 3,600 rounded")
        outcome, hit = sc.count_outcome(Decimal("3603"), False, {"films"}, counts)
        self.assertEqual((outcome, [c["key"] for c in hit]), ("rounded", ["ap_films"]))
        self.assertEqual(sc.count_outcome(Decimal("3610"), False, {"films"}, counts)[0], "agrees")
        self.assertEqual(sc.count_outcome(Decimal("3603"), True, {"films"}, counts), (None, None), "a percentage counts nothing")

    def test_a_record_whose_name_gives_no_name_to_check_is_listed(self):
        with tempfile.TemporaryDirectory() as root:
            for rid, name, counts in (("plain_bank", "the bank of films", {"films": 100}), ("named_bank", "SpineX bank", {"films": 200}),
                                      ("uncounted", "the other bank", {"colour_depth": 8})):
                write(Path(root, "data", "sources", f"{rid}.json"), {"id": rid, "name": name, "counts": counts})
            self.assertEqual(sc.unnamed_records(root, {}), [{"dataset": "plain_bank", "name": "the bank of films", "counts": ["films"]}])
            self.assertEqual(sc.unnamed_records(root, {"plain_bank": ["the bank"]}), [], "work/aliases.json names it")

    def test_what_the_scrub_keeps_out_reaches_no_check_whole_or_cut(self):
        filler = "the run took the night and gave every level a count " * 12

        def lines(item, width):
            # The item starts so many characters before a cut, short of its width: a check's cut at
            # 300, or the one that splits a line with no sentence's end into passages at 600.
            at_check = [(f"The Shared Name set holds 100 films; {filler}")[:300 - kept - 1] + f" {item} ends the line"
                        for kept in range(1, width)]
            at_passage = [filler[:600 - kept - 1] + f" {item} The Shared Name set holds 100 films" for kept in range(1, width)]
            return "\n".join(at_check + at_passage) + "\n"

        def checks(item, width):
            with tempfile.TemporaryDirectory() as root:
                texts = Path(root, "texts")
                (texts / "SchwingNet").mkdir(parents=True)
                (texts / f"{ALPHA}.txt").write_text(lines(item, width), encoding="utf-8")
                Path(root, "docs", "research").mkdir(parents=True)
                Path(root, "docs", "research", "note.md").write_text(lines(item, width), encoding="utf-8")
                write(Path(root, "data", "sources", "alpha_set.json"), {"id": "alpha_set", "what": lines(item, width)})
                return sc.check_datasets(sc.sources(str(texts), root), SHARED[:1])

        for item in Extract.ITEMS:
            words = redact.scrub(extract.without_contacts(item), Counter())
            found = checks(item, len(item))
            self.assertEqual(len(found), 3 * 2 * (len(item) - 1), "every line gives its check")
            self.assertFalse([c["text"] for c in found if item[:2] in c["text"]], item)
            self.assertIsNone(sr.personal_problem(found), item)
            self.assertEqual(found, checks(words, len(item)), "a check's words and key give away nothing the scrub took out")


class Answers(unittest.TestCase):
    def test_a_read_answer_is_split_for_the_join_and_none_writes_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            execution = Path(folder, "execution.json")
            result = {"record": record(), "changed": None, "cluster": "C1", "cluster_why": "w", "cluster_candidates": [],
                      "number_candidates": [number_candidate("contradiction", "q1")],
                      "number_other": [number_candidate("unit-or-scope-mismatch", "q2")]}
            write(execution, [{"type": "system"}, {"type": "result", "structured_output": result}])
            out = Path(folder, "answers")
            with contextlib.redirect_stdout(io.StringIO()):
                sa.answer("read", "2", str(execution), str(out))
                sa.answer("skeptic", "0", str(Path(folder, "missing.json")), str(out))
            found = sr.results_by_label(str(out))
            self.assertEqual(sorted(found), ["candidates:2", "inventory:2"])
            self.assertEqual([x["quantity"] for x in found["candidates:2"]["number_candidates"]], ["q1", "q2"])


class Words(unittest.TestCase):
    def test_the_body_keeps_earlier_runs_and_replaces_its_own(self):
        with tempfile.TemporaryDirectory() as folder:
            summary = Path(folder, "summary.json")
            write(summary, {"date": "2026-10-24", "read": [ALPHA], "left": {}, "waiting_artifacts": [], "placed": 1, "already": [],
                            "waiting": [], "unread": [], "missing": {}, "items_waiting": [], "dropped": [], "kept_numbers": 0})
            first = sa.body(str(summary), "https://github.com/o/r/actions/runs/11")
            old = Path(folder, "old.md")
            old.write_text(first, encoding="utf-8")
            second = sa.body(str(summary), "https://github.com/o/r/actions/runs/12", str(old))
            again = sa.body(str(summary), "https://github.com/o/r/actions/runs/12", str(old))
            self.assertEqual(second.count("<!-- synthesis-run: "), 2)
            self.assertEqual(second, again)
            self.assertIn("## Adversarial review", second)
            self.assertIn("carries the reads of the earlier runs", sa.message(str(summary), carried=True))


class Branch(unittest.TestCase):
    """synth_base.sh against a bare remote: the open synthesis pull request's records laid on
    main as one commit, the same tree made again, a conflict named, a pull request that changes
    more than the records or that owner-ok turned down not built on, none adopted but the App's,
    a bad branch refused, and the tree a join publishes."""

    PULLS = "GET repos/o/r/pulls?state=open&base=main&sort=created&direction=asc&per_page=100"
    CHECKS = "GET repos/o/r/commits/{}/check-runs?check_name=owner-ok&filter=latest&per_page=100"
    PAGE = "artifacts/_synthesis/inventory.md"

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.folder = Path(self.scratch.name)
        self.origin, self.work = self.folder / "origin.git", self.folder / "work"
        self.git(self.folder, "init", "-q", "--bare", "--initial-branch=main", str(self.origin))
        self.git(self.folder, "init", "-q", "--initial-branch=main", str(self.work))
        for repo in (self.origin, self.work):
            for key, value in QUIET.items():
                self.git(repo, "config", key, value)
        self.git(self.work, "remote", "add", "origin", str(self.origin))
        self.commit({self.PAGE: "one\ntwo\nthree\n", "artifacts/x/index.md": "x\n"}, "Start")
        self.git(self.work, "push", "-q", "origin", "main")
        self.git(self.work, "switch", "-q", "-c", "synthesis/7")
        self.read_sha = self.commit({self.PAGE: "one\ntwo\nthree, read again\n"}, "A run's reads")
        self.git(self.work, "push", "-q", "origin", "synthesis/7")
        self.git(self.work, "switch", "-q", "main")
        self.main_sha = self.commit({"artifacts/x/index.md": "x, changed on main\n"}, "An artifact changes")
        self.git(self.work, "push", "-q", "origin", "main")

    def tearDown(self):
        self.scratch.cleanup()

    def env(self, routes):
        clean = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        fake = fake_gh.environment(self.folder / "gh", routes)
        return {**clean, **GIT_ENV, **fake, "GH_TOKEN": "not-a-token"}

    def git(self, repo, *args):
        return git(repo, *args)

    def commit(self, files, message, repo=None):
        repo = repo or self.work
        for name, text in files.items():
            path = repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            self.git(repo, "add", name)
        self.git(repo, "commit", "-q", "-m", message)
        return self.git(repo, "rev-parse", "HEAD")

    def clone(self, name):
        path = self.folder / name
        self.git(self.folder, "clone", "-q", str(self.origin), str(path))
        for key, value in QUIET.items():
            self.git(path, "config", key, value)
        return path

    def base(self, clone, *args, pulls=None, checks=None, app="symphonyboard"):
        """synth_base.sh run in the clone, gh answering the open pull requests with the line pulls
        gives (the jq filter's output) and owner-ok's check runs on its head with checks."""
        line = pulls if pulls is not None else f"5\tsynthesis/7\t{self.read_sha}"
        routes = {self.PULLS: [fake_gh.answer(body=line)]}
        if line:
            routes[self.CHECKS.format(line.split("\t")[-1])] = [checks or fake_gh.answer(body="")]
        done = subprocess.run(["bash", str(TOOLS / "synth_base.sh"), *args], cwd=clone, capture_output=True, text=True,
                              env={**self.env(routes), "SYNTH_APP": app})
        return done.returncode, dict(x.split("=", 1) for x in done.stdout.splitlines() if "=" in x), done.stderr

    def asked(self):
        return [c["args"] for c in fake_gh.calls(self.folder / "gh" / "gh-log.jsonl")]

    def test_the_open_pull_request_s_reads_are_laid_on_main_and_made_again(self):
        clone = self.clone("look")
        code, out, err = self.base(clone, "look", "o/r")
        self.assertEqual(code, 0, err)
        self.assertEqual((out["main"], out["start"], out["pr"], out["branch"], out["conflict"], out["foreign"], out["rejected"]),
                         (self.main_sha, self.read_sha, "5", "synthesis/7", "", "", ""))
        self.assertEqual(self.git(clone, "rev-parse", "HEAD^"), self.main_sha)
        self.assertEqual(self.git(clone, "show", f"HEAD:{self.PAGE}"), "one\ntwo\nthree, read again")
        self.assertEqual(self.git(clone, "show", "HEAD:artifacts/x/index.md"), "x, changed on main")
        pulls = self.asked()[0]
        self.assertIn('.user.login == "symphonyboard[bot]"', pulls[pulls.index("--jq") + 1], "only the App's pull request is adopted")
        code, again, err = self.base(self.clone("again"), "again", "o/r", out["start"])
        self.assertEqual(code, 0, err)
        self.assertEqual((again["tree"], again["synthesis"]), (out["tree"], out["synthesis"]))

    def test_no_open_pull_request_leaves_main(self):
        clone = self.clone("none")
        code, out, err = self.base(clone, "look", "o/r", pulls="")
        self.assertEqual(code, 0, err)
        self.assertEqual((out["start"], out["pr"], out["tree"]), ("", "", self.git(clone, "rev-parse", "main^{tree}")))

    def test_with_no_app_named_no_pull_request_is_adopted(self):
        clone = self.clone("no-app")
        code, out, err = self.base(clone, "look", "o/r", app="")
        self.assertEqual(code, 0, err)
        self.assertEqual((out["pr"], out["start"], self.git(clone, "rev-parse", "HEAD")), ("", "", self.main_sha))
        self.assertEqual(self.asked(), [], "nothing is asked of GitHub")

    def test_a_conflict_names_the_pull_request_and_leaves_main(self):
        old = self.clone("old")
        self.main_sha = self.commit({self.PAGE: "one\ntwo\nthree, changed on main\n"}, "A hand edit")
        self.git(self.work, "push", "-q", "origin", "main")
        code, out, err = self.base(old, "now", "o/r")
        self.assertEqual(code, 0, err)
        self.assertEqual((out["main"], out["conflict"]), (self.main_sha, "5"))
        self.assertEqual(self.git(old, "rev-parse", "HEAD"), self.main_sha)
        self.assertEqual(self.git(old, "status", "--porcelain"), "")

    def test_a_pull_request_that_changes_what_no_join_writes_is_not_built_on(self):
        self.git(self.work, "switch", "-q", "synthesis/7")
        tool = self.commit({"artifacts/_synthesis/work/tools/synth.py": "print('changed')\n"}, "A tool too")
        self.git(self.work, "push", "-q", "origin", "synthesis/7")
        self.git(self.work, "switch", "-q", "main")
        clone = self.clone("foreign")
        code, out, err = self.base(clone, "look", "o/r", pulls=f"5\tsynthesis/7\t{tool}")
        self.assertEqual(code, 0, err)
        self.assertEqual((out["foreign"], out["start"], out["conflict"], out["rejected"]), ("5", tool, "", ""))
        self.assertEqual(self.git(clone, "rev-parse", "HEAD"), self.main_sha, "nothing of it is laid on main")
        self.assertIn("which no join writes", err)

    def test_a_pull_request_owner_ok_turned_down_is_not_built_on(self):
        clone = self.clone("rejected")
        code, out, err = self.base(clone, "look", "o/r", checks=fake_gh.answer(body="failure"))
        self.assertEqual(code, 0, err)
        self.assertEqual((out["rejected"], out["foreign"], out["conflict"]), ("5", "", ""))
        self.assertEqual(self.git(clone, "rev-parse", "HEAD"), self.main_sha)
        code, _out, err = self.base(self.clone("unread"), "look", "o/r", checks=fake_gh.answer(status=502))
        self.assertEqual(code, 1, "a Reject the run could not see is not built on either")
        self.assertIn("could not be read", err)

    def test_a_branch_name_outside_the_rule_stops_it(self):
        code, _out, err = self.base(self.clone("bad"), "look", "o/r", pulls=f"5\tsynthesis/a b\t{self.read_sha}")
        self.assertEqual(code, 1)
        self.assertIn("does not take", err)

    def test_a_join_publishes_its_records_on_main_s_tree_and_nothing_else(self):
        clone = self.clone("publish")
        self.git(clone, "rm", "-q", self.PAGE)
        joined = self.commit({"artifacts/_synthesis/clusters.md": "a new page\n", "artifacts/x/index.md": "x, as the join saw it\n",
                              "artifacts/_synthesis/work/tools/synth.py": "print('changed')\n"}, "A join", repo=clone)
        code, out, err = self.base(clone, "publish", "o/r", joined, self.main_sha)
        self.assertEqual(code, 0, err)
        names = self.git(clone, "ls-tree", "-r", "--name-only", out["tree"]).splitlines()
        self.assertEqual(sorted(names), ["artifacts/_synthesis/clusters.md", "artifacts/x/index.md"])
        self.assertEqual(self.git(clone, "cat-file", "-p", f"{out['tree']}:artifacts/_synthesis/clusters.md"), "a new page")
        self.assertEqual(self.git(clone, "cat-file", "-p", f"{out['tree']}:artifacts/x/index.md"), "x, changed on main")
        self.assertEqual(self.git(clone, "status", "--porcelain"), "", "the checkout's own index is left as it was")


class Pages(unittest.TestCase):
    def test_a_record_s_words_draw_no_tag_and_no_image(self):
        cases = [
            ("<img src=x onerror=y>", "&lt;img src=x onerror=y>"),
            ("<!-- a comment -->", "&lt;!-- a comment -->"),
            ("see ![a](https://h.invalid/x.png)", "see !\\[a](https://h.invalid/x.png)"),
            ("`<b>` stays as it is, <b> does not", "`<b>` stays as it is, &lt;b> does not"),
            ("fewer than < 224 frames", "fewer than < 224 frames"),
            ("an escaped \\` then `<b>`", "an escaped \\` then `&lt;b>`"),
        ]
        for text, drawn in cases:
            self.assertEqual(render_inventory.inert(text), drawn, text)
        self.assertEqual(render_inventory.cell("a|b\n<i>c</i>"), "a\\|b &lt;i>c&lt;/i>")

    def test_the_inventory_and_cluster_pages_render_from_the_committed_records(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            render_inventory.main(str(SYNTH / "inventory.json"), f"{folder}/inventory.md")
            render_clusters.main(str(SYNTH / "work" / "out" / "clustering.json"), str(SYNTH / "inventory.json"), f"{folder}/clusters.md")
            for name in ("inventory.md", "clusters.md"):
                self.assertEqual(Path(folder, name).read_text(encoding="utf-8"), (SYNTH / name).read_text(encoding="utf-8"), name)

    def test_the_concept_page_renders_from_the_committed_ledger(self):
        ledger = synth.load(synth.LEDGER)
        page = synth.scrubbed(sc.page(ledger, synth.load(synth.STATE)["stamped"]))
        self.assertEqual(page, synth.PAGE.read_text(encoding="ascii"))

    def test_the_committed_records_and_pages_hold_no_address_phone_number_or_credential(self):
        for path in sorted([*SYNTH.rglob("*.json"), *SYNTH.rglob("*.md")]):
            self.assertIsNone(sr.personal_problem(path.read_text(encoding="utf-8")), path.name)

    def test_the_committed_records_hold_nothing_the_scrub_would_change(self):
        for path in (SYNTH / "inventory.json", SYNTH / "work" / "out" / "concepts.json", SYNTH / "work" / "out" / "clustering.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(synth.scrubbed(data), data, path.name)


class Workflow(unittest.TestCase):
    def test_every_action_is_pinned_and_every_tool_it_calls_is_here(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("\npermissions: {}\n", text)
        for uses in re.findall(r"uses:\s*(\S+)", text):
            self.assertRegex(uses, r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")
        for name in set(re.findall(r"\$TOOLS/([\w.]+)", text)):
            self.assertTrue((TOOLS / name).exists(), name)
        self.assertTrue((ROOT / "tools" / "usage.py").exists())

    def jobs(self):
        """The workflow's jobs, each as its text: a job starts two spaces in under the key jobs."""
        found, current = {}, None
        for line in WORKFLOW.read_text(encoding="utf-8").split("\njobs:\n", 1)[1].split("\n"):
            start = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
            if start:
                current = start.group(1)
                found[current] = []
            elif current is not None:
                found[current].append(line)
        return {name: "\n".join(lines) for name, lines in found.items()}

    def test_a_push_only_starts_the_workflow_again_by_run_workflow(self):
        # claude-code-action stops at "Unsupported event type: push" (issue #274), so a push's run
        # hands the look and the reads to a run the action takes, and nothing else of it runs.
        text, jobs = WORKFLOW.read_text(encoding="utf-8"), self.jobs()
        relay = jobs["relay"]
        self.assertIn("    if: vars.CLAUDE_CROWD != 'true' && github.event_name == 'push' && "
                      "github.repository == 'OpenSpineConsortium/SchwingNet' && github.ref == 'refs/heads/main'\n", relay)
        self.assertEqual(re.findall(r"^      (\w+): ", relay.split("    permissions:\n", 1)[1], re.M), ["actions"])
        self.assertIn("      actions: write", relay)
        self.assertIn('gh workflow run synthesis.yml --repo "$REPO" --ref main -f relayed=push', relay)
        for absent in ("secrets.", "actions/checkout", "uses:", "contents:"):
            self.assertNotIn(absent, relay, absent)
        for name in ("values", "look"):
            self.assertIn("github.event_name != 'push'", jobs[name], name)
        for name in ("batch", "verdicts", "join"):
            self.assertIn("needs.", jobs[name].split("    if: ", 1)[1].split("\n", 1)[0], name)
        self.assertIn("concurrency:\n  group: ${{ github.event_name == 'push' && "
                      "format('synthesis-relay-{0}', github.run_id) || 'synthesis' }}\n  cancel-in-progress: false\n", text)

    def test_the_stand_in_is_admitted_as_the_push(self):
        # so three failed reading runs pause it, as they pause a push, and a run by hand still tries
        text = WORKFLOW.read_text(encoding="utf-8")
        dispatch = text.split("  workflow_dispatch:\n", 1)[1].split("\n\n", 1)[0]
        self.assertIn("      relayed:\n", dispatch)
        self.assertIn('        default: ""', dispatch)
        self.assertEqual(text.count("EVENT: ${{"), 1)
        self.assertIn("EVENT: ${{ inputs.relayed == 'push' && 'push' || github.event_name }}", text)

    def test_every_session_takes_runs_the_actions_bot_starts(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        steps = text.split("uses: anthropics/claude-code-action@")[1:]
        self.assertEqual(len(steps), 4)
        for step in steps:
            options = step.split("      - name:", 1)[0]
            self.assertIn('allowed_bots: "github-actions"\n', options)
        self.assertNotIn('allowed_bots: "*"', text)
        self.assertNotIn("allowed_non_write_users", text)


class OwnerGate(unittest.TestCase):
    """owner-ok.yml's first job, which the synthesis's pull requests meet: an admin's own pull
    request and one a bot opened pass at once (the owner, 2026-10-31), and a person's who does not
    administer, or whose role GitHub does not give, asks for the owner's tap; the job itself never
    fails, since a job skipped because its need failed reports as skipped, which a required check
    takes as passing."""

    WORKFLOW = ROOT / ".github" / "workflows" / "owner-ok.yml"

    def script(self):
        lines = self.WORKFLOW.read_text(encoding="utf-8").splitlines()
        body = []
        for line in lines[lines.index("        run: |") + 1:]:
            if line.strip() and not line.startswith(" " * 10):
                break
            body.append(line[10:])
        return "\n".join(body) + "\n"

    def test_an_admin_s_and_a_bot_s_pull_requests_pass_at_once(self):
        cases = [("User", fake_gh.answer(body="admin"), "owner-self"), ("User", fake_gh.answer(body="write"), "owner-ok"),
                 ("Bot", fake_gh.answer(body="admin"), "owner-self"), ("User", fake_gh.answer(status=502), "owner-ok")]
        for kind, answer, environment in cases:
            with tempfile.TemporaryDirectory() as folder:
                output = Path(folder, "output")
                fake = fake_gh.environment(Path(folder, "gh"), {"GET repos/o/r/collaborators/someone/permission": [answer]})
                env = {**os.environ, **fake, "GH_TOKEN": "not-a-token", "REPO": "o/r", "AUTHOR": "someone", "KIND": kind,
                       "GITHUB_OUTPUT": str(output)}
                done = subprocess.run(["bash", "-e", "-c", self.script()], capture_output=True, text=True, env=env)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertEqual(output.read_text(encoding="utf-8"), f"environment={environment}\n", (kind, answer))
                asked = fake_gh.calls(Path(folder, "gh", "gh-log.jsonl"))
                self.assertEqual(bool(asked), kind == "User", "a bot's role is never asked")


if __name__ == "__main__":
    unittest.main()
