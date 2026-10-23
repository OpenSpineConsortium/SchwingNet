"""The synthesis that keeps itself current (artifacts/_synthesis/work/tools, run by
.github/workflows/synthesis.yml): the Claude sessions' arguments, schemas and briefs, whether a
run may read, a run whose answers come back in part and how the join places them, the issue's
report, the step that lays the open synthesis pull request on main, the scrub of what the
folder's rule keeps out, the concept checks' independence of Python's hash seed, and the pages,
which render from the committed records as they are committed. No Claude, no network and no
GitHub: the sessions' answers are written here by hand, gh is the suite's fake and the remote is a
bare repository in a scratch folder.

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
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SYNTH = ROOT / "artifacts" / "_synthesis"
TOOLS = SYNTH / "work" / "tools"
WORKFLOW = ROOT / ".github" / "workflows" / "synthesis.yml"
sys.path.insert(0, str(TOOLS))
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
            (dict(conflict="12"), "#12 no longer merges"),
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
        self.world = World(self.scratch.name)

    def tearDown(self):
        self.scratch.cleanup()

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
                            ({"record": record(), "cluster": "No such cluster"}, "chose no cluster")):
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
                                                         cluster_candidate(ALPHA, "SchwingNet/nowhere-x1y2z3", "unknown")],
                                  "number_candidates": [number_candidate("contradiction", "whole-frame accuracy"),
                                                        number_candidate("probably-different-quantities", "frames scored")]})
        w.answer("candidates:1", {"cluster_candidates": [cluster_candidate(GAMMA, ALPHA, "unruled", kind="stale")],
                                  "number_candidates": []})
        out = printed(sa.batch, str(w.plan), str(w.answers), str(w.batches))
        self.assertEqual((out["batches"], out["items"], out["dropped"]), ("[0]", "6", "1"))
        listed = json.loads((w.batches / "batches.json").read_text(encoding="utf-8"))
        self.assertIn("does not know", listed["dropped"][0]["why"])
        new = {"placed": f"new:{ALPHA}:cluster:0", "refused": f"new:{ALPHA}:cluster:1", "number": f"new:{ALPHA}:number:0",
               "unruled": f"new:{GAMMA}:cluster:0"}
        self.assertEqual(sorted(listed["batches"][0]["keys"]), sorted(["stale:C1|0", "unread:C1|1", *new.values()]))
        w.answer("skeptic:0", {"items": [reading("stale:C1|0", "refuted"), reading("unread:C1|1", "updated-later"),
                                         reading(new["placed"], "confirmed"),
                                         reading(new["refused"], "confirmed", explanation="ask reader@example.invalid"),
                                         reading(new["number"], "confirmed-contradiction"), reading(new["unruled"], "confirmed"),
                                         reading("not:in:this:batch", "confirmed")]})
        self.assertEqual(printed(sa.recheck, str(w.batches), str(w.answers), "0")["count"], "6")
        held = {"holds": True, "hint_ok": True}
        w.answer("recheck:0", {"items": [reading("stale:C1|0", "refuted", **held), reading("unread:C1|1", "updated-later", **held),
                                         reading(new["placed"], "confirmed", **held), reading(new["refused"], "confirmed", **held),
                                         reading(new["number"], "updated-later", holds=True, hint_ok=False),
                                         reading(new["unruled"], "refuted", holds=False, hint_ok=True)]})
        self.assertEqual(printed(sa.disputes, str(w.batches), str(w.answers), "0")["count"], "2")
        w.answer("judge:0", {"rulings": [reading(new["number"], "updated-later", sided_with="re-checker")]})

        found = sr.results_by_label(str(w.answers))
        final, missing = sr.final_verdicts(listed["batches"], listed["items"], found)
        self.assertIn("not on its scale", missing["unread:C1|1"])
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


class Scrub(unittest.TestCase):
    def test_what_the_folder_s_rule_keeps_out_is_replaced_and_names_and_ids_are_kept(self):
        cases = [
            (f"grid {LOGIN}@wayne, branch L6_Class", "grid [the owner's login], branch L6_Class"),
            (f"python at /rs/rs_grp_lab/{LOGIN}/envs/py312", "python at [a grid folder named by a login]/envs/py312"),
            (f"/rs/rs_grp_lab/{LOGIN}/data/or_ready", "[the lab volume's data root]/or_ready"),
            (f"account: {LOGIN}", "account: [the owner's login]"),
            (f"{FIRST}'s decision of 21 Oct", "[the owner]'s decision of 21 Oct"),
            ("register at forms.gle/AbC123xyz", "register at [the registration form's link]"),
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
    """synth_base.sh against a bare remote: the open synthesis pull request's changes laid on
    main as one commit, the same tree made again, a conflict named, a bad branch refused."""

    PULLS = "GET repos/o/r/pulls?state=open&base=main&sort=created&direction=asc&per_page=100"

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
        self.commit({"artifacts/_synthesis/page.md": "one\ntwo\nthree\n", "artifacts/x/index.md": "x\n"}, "Start")
        self.git(self.work, "push", "-q", "origin", "main")
        self.git(self.work, "switch", "-q", "-c", "synthesis/7")
        self.read_sha = self.commit({"artifacts/_synthesis/page.md": "one\ntwo\nthree, read again\n"}, "A run's reads")
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
        done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                              env={**{k: v for k, v in os.environ.items() if not k.startswith("GIT_")}, **GIT_ENV})
        if done.returncode:
            raise AssertionError(f"git {' '.join(args)}: {done.stderr}")
        return done.stdout.strip()

    def commit(self, files, message):
        for name, text in files.items():
            path = self.work / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            self.git(self.work, "add", name)
        self.git(self.work, "commit", "-q", "-m", message)
        return self.git(self.work, "rev-parse", "HEAD")

    def clone(self, name):
        path = self.folder / name
        self.git(self.folder, "clone", "-q", str(self.origin), str(path))
        for key, value in QUIET.items():
            self.git(path, "config", key, value)
        return path

    def base(self, clone, *args, pulls=None):
        line = pulls if pulls is not None else f"5\tsynthesis/7\t{self.read_sha}"
        done = subprocess.run(["bash", str(TOOLS / "synth_base.sh"), *args], cwd=clone, capture_output=True, text=True,
                              env=self.env({self.PULLS: [fake_gh.answer(body=line)]}))
        return done.returncode, dict(x.split("=", 1) for x in done.stdout.splitlines() if "=" in x), done.stderr

    def test_the_open_pull_request_s_reads_are_laid_on_main_and_made_again(self):
        clone = self.clone("look")
        code, out, err = self.base(clone, "look", "o/r")
        self.assertEqual(code, 0, err)
        self.assertEqual((out["main"], out["start"], out["pr"], out["branch"], out["conflict"]),
                         (self.main_sha, self.read_sha, "5", "synthesis/7", ""))
        self.assertEqual(self.git(clone, "rev-parse", "HEAD^"), self.main_sha)
        self.assertEqual(self.git(clone, "show", "HEAD:artifacts/_synthesis/page.md"), "one\ntwo\nthree, read again")
        self.assertEqual(self.git(clone, "show", "HEAD:artifacts/x/index.md"), "x, changed on main")
        code, again, err = self.base(self.clone("again"), "again", "o/r", out["start"])
        self.assertEqual(code, 0, err)
        self.assertEqual((again["tree"], again["synthesis"]), (out["tree"], out["synthesis"]))

    def test_no_open_pull_request_leaves_main(self):
        clone = self.clone("none")
        code, out, err = self.base(clone, "look", "o/r", pulls="")
        self.assertEqual(code, 0, err)
        self.assertEqual((out["start"], out["pr"], out["tree"]), ("", "", self.git(clone, "rev-parse", "main^{tree}")))

    def test_a_conflict_names_the_pull_request_and_leaves_main(self):
        old = self.clone("old")
        self.main_sha = self.commit({"artifacts/_synthesis/page.md": "one\ntwo\nthree, changed on main\n"}, "A hand edit")
        self.git(self.work, "push", "-q", "origin", "main")
        code, out, err = self.base(old, "now", "o/r")
        self.assertEqual(code, 0, err)
        self.assertEqual((out["main"], out["conflict"]), (self.main_sha, "5"))
        self.assertEqual(self.git(old, "rev-parse", "HEAD"), self.main_sha)
        self.assertEqual(self.git(old, "status", "--porcelain"), "")

    def test_a_branch_name_outside_the_rule_stops_it(self):
        code, _out, err = self.base(self.clone("bad"), "look", "o/r", pulls=f"5\tsynthesis/a b\t{self.read_sha}")
        self.assertEqual(code, 1)
        self.assertIn("does not take", err)


class Pages(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
