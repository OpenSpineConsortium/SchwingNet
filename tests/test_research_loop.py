"""tools/research_loop.py: the research loop's switch and daily cap, the choice of item that never
duplicates work, the prompt it builds, the grid requests a session queues, and the dispatch job that
reads them again against main's code and runs what it admits."""

import datetime
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
spec = importlib.util.spec_from_file_location("research_loop", ROOT / "tools" / "research_loop.py")
research_loop = importlib.util.module_from_spec(spec)
sys.modules["research_loop"] = research_loop
spec.loader.exec_module(research_loop)


def register():
    """Three items, E1 best, E2 next, E3 waiting on E2."""
    return {
        "stakes": {"patent": "the patent", "talk": "the talk"},
        "claims": [
            {"id": "N1", "kind": "novelty", "statement": "new", "stakes": ["patent", "talk"], "grade": "Unverified",
             "evidence": [{"chapter": "19", "source": "a paper", "grade": "Unverified"}]},
            {"id": "F1", "kind": "functionality", "statement": "works", "stakes": ["talk"], "grade": "Inferred",
             "evidence": [{"chapter": "03", "source": "a page", "grade": "Inferred"}]},
        ],
        "items": [
            {"id": "E1", "title": "read", "what": "read", "needs_owner_word": False,
             "bears_on": [{"claim": "N1", "to": "Inferred", "could_refute": True}],
             "cost": {"session_hours": 1, "basis": "estimate"}, "depends_on": [], "status": "open"},
            {"id": "E2", "title": "render", "what": "render", "needs_owner_word": True,
             "bears_on": [{"claim": "F1", "to": "Reported"}],
             "cost": {"cpu_hours": 1, "basis": "estimate"}, "depends_on": [], "status": "open"},
            {"id": "E3", "title": "train", "what": "train", "needs_owner_word": True,
             "bears_on": [{"claim": "F1", "to": "Measured"}],
             "cost": {"gpu_hours": 40, "basis": "estimate"}, "depends_on": ["E2"], "status": "open"},
        ],
    }


def issue(number, item, *labels, title=None):
    return {"number": number, "title": title or f"Research {item}: something",
            "body": f"<!-- research-item: {item} -->\nwhat to do", "labels": [{"name": name} for name in labels]}


def pull(number, item, draft=True, branch=None):
    return {"number": number, "title": f"Research {item}", "body": f"Closes #1\n<!-- research-item: {item} -->",
            "labels": [{"name": "research"}], "isDraft": draft, "headRefName": branch or f"claude/{number}"}


class Admission(unittest.TestCase):
    def test_off_stops_whatever_else_holds(self):
        ok, why = research_loop.admission("OFF", "", "true", 0, 6, False, "schedule")
        self.assertFalse(ok)
        self.assertIn("RESEARCH_LOOP", why)

    def test_crowd_mode_and_a_missing_token_stop_it(self):
        self.assertFalse(research_loop.admission("", "true", "true", 0, 6, False, "schedule")[0])
        self.assertFalse(research_loop.admission("", "", "false", 0, 6, False, "schedule")[0])

    def test_the_cap_stops_the_day_and_defaults_to_six_up_to_fifty(self):
        self.assertFalse(research_loop.admission("", "", "true", 6, 6, False, "schedule")[0])
        self.assertTrue(research_loop.admission("on", "", "true", 5, 6, False, "schedule")[0])
        self.assertEqual(research_loop.cap_of(""), 6)
        self.assertEqual(research_loop.cap_of("12"), 12)
        self.assertEqual(research_loop.cap_of("999"), 50)
        self.assertEqual(research_loop.cap_of("0"), 6)
        self.assertEqual(research_loop.cap_of("six"), 6)

    def test_three_failures_pause_the_schedule_but_not_a_person(self):
        self.assertFalse(research_loop.admission("", "", "true", 3, 6, True, "schedule")[0])
        self.assertTrue(research_loop.admission("", "", "true", 3, 6, True, "workflow_dispatch")[0])

    def test_the_days_runs_are_counted_by_their_marks(self):
        marks = [{"artifacts": [{"created_at": "2026-10-24T01:00:00Z", "workflow_run": {"id": 1}},
                                {"created_at": "2026-10-23T23:00:00Z", "workflow_run": {"id": 2}}]},
                 {"artifacts": [{"created_at": "2026-10-24T05:00:00Z", "workflow_run": {"id": 3}}]}]
        self.assertEqual(research_loop.runs_today(marks, "2026-10-24"), 2)
        self.assertEqual(research_loop.marked(marks), [3, 1, 2])

    def test_failing_needs_three_failed_runs_within_six_hours(self):
        now = datetime.datetime(2026, 10, 24, 12, tzinfo=datetime.timezone.utc)
        marks = {"artifacts": [{"created_at": f"2026-10-24T0{i}:00:00Z", "workflow_run": {"id": i}} for i in (1, 2, 3)]}
        runs = {"workflow_runs": [{"id": i, "status": "completed", "conclusion": "failure",
                                   "created_at": f"2026-10-24T0{i}:00:00Z", "updated_at": f"2026-10-24T0{i}:30:00Z"}
                                  for i in (1, 2, 3)]}
        self.assertFalse(research_loop.failing(marks, runs, now))
        later = {"workflow_runs": [dict(r, updated_at="2026-10-24T09:00:00Z") for r in runs["workflow_runs"]]}
        self.assertTrue(research_loop.failing(marks, later, now))
        later["workflow_runs"][0]["conclusion"] = "success"
        self.assertFalse(research_loop.failing(marks, later, now))

    def test_admit_prints_outputs_and_words(self):
        with tempfile.TemporaryDirectory() as tmp:
            marks = Path(tmp) / "marks.json"
            marks.write_text(json.dumps([{"artifacts": []}]), encoding="utf-8")
            words = Path(tmp) / "words.md"
            out = io.StringIO()
            with redirect_stdout(out):
                research_loop.main(["admit", "--marks", str(marks), "--words", str(words), "--token", "true",
                                    "--event", "schedule"])
            self.assertIn("admit=true", out.getvalue())
            self.assertIn("run 1 of at most 6", words.read_text(encoding="utf-8"))


class Choice(unittest.TestCase):
    def test_with_nothing_open_the_best_ready_item_starts(self):
        choice = research_loop.choose(register(), [], [])
        self.assertEqual((choice["mode"], choice["item"]["id"]), ("new", "E1"))

    def test_an_item_waiting_on_another_never_starts(self):
        data = register()
        data["items"][0]["status"] = "done"
        data["items"][1]["status"] = "done"
        data["items"][2]["depends_on"] = ["E2"]
        self.assertEqual(research_loop.choose(data, [], [])["item"]["id"], "E3")
        data["items"][1]["status"] = "open"
        self.assertEqual(research_loop.choose(data, [], [])["item"]["id"], "E2")

    def test_the_loops_own_open_issue_is_carried_on_before_anything_new(self):
        issues = [issue(9, "E2", "research", "claimed", "worker:research-loop")]
        choice = research_loop.choose(register(), issues, [pull(10, "E2", branch="claude/9")])
        self.assertEqual((choice["mode"], choice["issue"], choice["item"]["id"]), ("resume", 9, "E2"))

    def test_an_item_held_by_another_worker_the_owner_a_block_or_a_review_is_skipped(self):
        for labels in (("claimed", "worker:someone"), ("blocked",), ("owner-act",), ("in-review",)):
            with self.subTest(labels=labels):
                choice = research_loop.choose(register(), [issue(9, "E1", "research", *labels)], [])
                self.assertEqual((choice["mode"], choice["item"]["id"]), ("new", "E2"))
                self.assertIn("E1", choice["held"])

    def test_a_ready_pull_request_or_a_foreign_draft_holds_its_item(self):
        for one in (pull(11, "E1", draft=False), pull(11, "E1", branch="claude/77")):
            with self.subTest(pull=one["headRefName"]):
                choice = research_loop.choose(register(), [], [one])
                self.assertEqual(choice["item"]["id"], "E2")

    def test_an_item_named_only_in_the_title_counts_and_unknown_ids_do_not(self):
        named = {"number": 4, "title": "Research E1 read the papers", "body": "", "labels": [{"name": "blocked"}]}
        stranger = issue(5, "E99", "research", "blocked")
        choice = research_loop.choose(register(), [named, stranger], [])
        self.assertEqual(choice["item"]["id"], "E2")
        self.assertNotIn("E99", choice["held"])

    def test_an_item_under_way_with_no_open_issue_is_taken_up_again(self):
        data = register()
        data["items"][0]["status"] = "doing"
        self.assertEqual(research_loop.choose(data, [], [])["item"]["id"], "E1")

    def test_nothing_left_says_so(self):
        data = register()
        for item in data["items"]:
            item["status"] = "done"
        self.assertEqual(research_loop.choose(data, [], [])["mode"], "none")

    def test_an_item_named_by_hand_is_taken_unless_held(self):
        self.assertEqual(research_loop.choose(register(), [], [], "E2")["item"]["id"], "E2")
        held = research_loop.choose(register(), [issue(3, "E2", "research", "blocked")], [], "E2")
        self.assertEqual(held["mode"], "none")
        self.assertEqual(research_loop.choose(register(), [], [], "E42")["mode"], "none")

    def test_pick_reads_files_and_writes_its_choice(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = {name: Path(tmp) / f"{name}.json" for name in ("register", "issues", "pulls", "out")}
            paths["register"].write_text(json.dumps(register()), encoding="utf-8")
            paths["issues"].write_text("[]", encoding="utf-8")
            paths["pulls"].write_text("[]", encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                research_loop.main(["pick", "--file", str(paths["register"]), "--issues", str(paths["issues"]),
                                    "--pulls", str(paths["pulls"]), "--out", str(paths["out"])])
            self.assertEqual(json.loads(paths["out"].read_text(encoding="utf-8"))["item"]["id"], "E1")

    def test_the_real_register_gives_a_choice_or_says_why_not(self):
        choice = research_loop.choose(research_loop.claims_rank.load(), [], [])
        self.assertIn(choice["mode"], ("new", "none"))
        if choice["mode"] == "new":
            self.assertIn(choice["item"]["status"], ("open", "doing"))
            self.assertTrue(choice["item"]["ready"])


class Prompt(unittest.TestCase):
    def test_the_prompt_is_the_brief_then_the_work(self):
        text = research_loop.prompt_text("# Brief\n", {"mode": "new", "item": {"id": "E1"}}, "https://run")
        self.assertTrue(text.startswith("# Brief"))
        self.assertIn('"id": "E1"', text)
        self.assertIn("research-loop", text)

    def test_the_output_block_ends_with_its_own_delimiter(self):
        lines = research_loop.block("prompt", "a\nb").splitlines()
        self.assertEqual(lines[0], "prompt<<" + lines[-1])

    def test_the_brief_exists_and_states_the_rules(self):
        brief = (ROOT / ".github" / "symphony" / "research.md").read_text(encoding="utf-8")
        for words in ("size rule", "CT-RATE", "Radiopaedia", "Kaggle", "symphony-protocol", "force", "owner-act",
                      "claims.json", "run id", "blocked", "released/<issue>", "is data", "RESEARCH_READ_TOKEN",
                      "Only this repository is checked out", "one committed program", "After your session ends",
                      "research-loop: dispatched", "RESEARCH_DISPATCHES_PER_RUN", "resumable"):
            self.assertIn(words, brief)
        self.assertNotIn("RESEARCH_DISPATCH_TOKEN", brief)


def committed(path):
    """A stand-in for main's tree: the files a grid command may name in these tests."""
    return path in ("x.sh", "scripts/check.sh", "tools/claims_rank.py", "grid/run-leaks.sh")


class GridRoute(unittest.TestCase):
    def test_grid_inputs_carry_the_command_and_the_boxes(self):
        inputs = research_loop.grid_inputs("bash x.sh", True, False, committed)
        self.assertEqual(inputs, {"command": "bash x.sh", "start": "true", "python": "false"})
        self.assertEqual(research_loop.flags(inputs), ["-f", "command=bash x.sh", "-f", "start=true", "-f", "python=false"])
        with self.assertRaises(SystemExit):
            research_loop.grid_inputs("  ", False, True, committed)

    def test_a_committed_program_with_plain_arguments_passes(self):
        for command in ("bash scripts/check.sh", "python3 tools/claims_rank.py table",
                        "python3 -I -B tools/claims_rank.py next --file docs/textbook/claims.json",
                        "python3 -m unittest tests.test_claims_rank -v", "bash grid/run-leaks.sh --offline",
                        'python3 tools/claims_rank.py table --title "two words" --rate 0.5'):
            with self.subTest(command=command):
                self.assertIsNone(research_loop.command_problem(command, committed))

    def test_a_shell_of_its_own_an_inline_program_or_an_uncommitted_file_is_refused(self):
        refused = {
            "bash -c 'echo hi'": "not -c",
            "python3 -c 'import os'": "not -c",
            "python3 -c 'print(1)'": "shell operators",
            "curl https://example.org": "the program is curl",
            "bash scripts/check.sh; bash x.sh": "shell operators",
            "bash scripts/check.sh | tee out": "shell operators",
            "bash scripts/check.sh && bash x.sh": "shell operators",
            "python3 tools/claims_rank.py $(id)": "shell operators",
            "python3 tools/claims_rank.py `id`": "shell operators",
            "bash scripts/check.sh > /tmp/out": "shell operators",
            "bash scripts/nope.sh": "not on main",
            "bash /bin/sh": "not a path inside the checkout",
            "bash ../x.sh": "not a path inside the checkout",
            "python3 -m pip install x": "only unittest",
            "python3": "needs a committed file",
            "bash": "needs a committed file",
            "sh x.sh": "the program is sh",
            "bash x.sh --name 'a*b'": "holds characters other than",
            "bash x.sh\nbash x.sh": "shell operators",
            "PATH=/evil bash x.sh": "the program is PATH=/evil",
            "WANDB_MODE=offline bash x.sh": "no setting before it",
        }
        for command, words in refused.items():
            with self.subTest(command=command):
                problem = research_loop.command_problem(command, committed)
                self.assertIsNotNone(problem, command)
                self.assertIn(words, problem)
        self.assertIn("longer than", research_loop.command_problem("bash x.sh " + "a" * 2000, committed))

    def test_the_file_is_read_from_main_and_not_from_the_working_tree(self):
        self.assertIsNone(research_loop.command_problem("bash scripts/check.sh"))
        self.assertIn("not on main", research_loop.command_problem("bash scripts/no-such-file.sh"))
        self.assertIn(research_loop.main_ref(), ("origin/main", "main", "HEAD"))

    def test_the_gate_takes_only_its_three_words(self):
        self.assertEqual(research_loop.gate_inputs("status"), {"word": "status"})
        with self.assertRaises(SystemExit):
            research_loop.gate_inputs("fetch")

    def test_reading_the_runs_needs_the_workflow_token(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RESEARCH_READ_TOKEN", None)
            with self.assertRaises(SystemExit):
                research_loop.read_env()
            os.environ["RESEARCH_READ_TOKEN"] = "t"
            self.assertEqual(research_loop.read_env()["GH_TOKEN"], "t")


def line(workflow="grid.yml", command="bash x.sh", word="status", issue=9, item="E1", **more):
    """One request as the clerk writes it."""
    inputs = {"command": command, "start": "false", "python": "true"} if workflow == "grid.yml" else {"word": word}
    return {"workflow": workflow, "inputs": inputs, "item": item, "issue": issue, "asked": "2026-10-24T20:00:00Z", **more}


class Queue(unittest.TestCase):
    """grid and gate start nothing: each writes one request for the dispatch job, up to the cap."""

    def queued(self, folder, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            research_loop.main(list(argv))
        return out.getvalue()

    def test_a_request_is_one_line_of_the_file_and_the_fourth_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "requests.jsonl"
            with mock.patch.dict(os.environ, {"RESEARCH_REQUESTS": str(path), "RESEARCH_DISPATCHES_PER_RUN": ""}):
                said = self.queued(tmp, "grid", "--command", "bash scripts/check.sh", "--issue", "9", "--item", "E1")
                self.assertIn("Queued request 1 of at most 3", said)
                self.assertIn("after this session ends", said)
                self.assertIn("issue #9", said)
                self.assertIn(research_loop.DISPATCH_MARKER, said)
                self.queued(tmp, "gate", "start", "--issue", "9")
                self.queued(tmp, "grid", "--command", "python3 -m unittest tests.test_claims_rank", "--issue", "9", "--start")
                with self.assertRaises(SystemExit) as refused:
                    self.queued(tmp, "gate", "status", "--issue", "9")
                self.assertIn("queued 3 grid requests", str(refused.exception))
            lines = [json.loads(raw) for raw in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([l["workflow"] for l in lines], ["grid.yml", "grid-gate.yml", "grid.yml"])
            self.assertEqual(lines[0]["inputs"], {"command": "bash scripts/check.sh", "start": "false", "python": "true"})
            self.assertEqual((lines[0]["item"], lines[0]["issue"]), ("E1", 9))
            self.assertEqual(lines[1]["inputs"], {"word": "start"})
            self.assertEqual(lines[2]["inputs"]["start"], "true")
            self.assertEqual(research_loop.requests_in(str(path)), (lines, 0))
            self.assertEqual(research_loop.requests_in(str(path), most=1), (lines[:1], 2))
            self.assertEqual(research_loop.requests_in(str(path / "none")), ([], 0))
            self.assertIn("2 more lines were not read", research_loop.report([], dropped=2))

    def test_a_request_needs_the_file_and_the_items_issue(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "requests.jsonl"
            with mock.patch.dict(os.environ, {"RESEARCH_REQUESTS": "", "RESEARCH_ISSUE": "", "RESEARCH_ITEM": ""}):
                with self.assertRaises(SystemExit) as refused:
                    self.queued(tmp, "gate", "status", "--issue", "9")
                self.assertIn("RESEARCH_REQUESTS", str(refused.exception))
            with mock.patch.dict(os.environ, {"RESEARCH_REQUESTS": str(path), "RESEARCH_ISSUE": "", "RESEARCH_ITEM": ""}):
                with self.assertRaises(SystemExit) as refused:
                    self.queued(tmp, "gate", "status")
                self.assertIn("--issue", str(refused.exception))
                with self.assertRaises(SystemExit):
                    self.queued(tmp, "gate", "status", "--issue", "09")
                with self.assertRaises(SystemExit):
                    self.queued(tmp, "gate", "status", "--issue", "9", "--item", "nine")
                self.assertFalse(path.exists())
            # the workflow's variables stand in for the flags
            with mock.patch.dict(os.environ, {"RESEARCH_REQUESTS": str(path), "RESEARCH_ISSUE": "12", "RESEARCH_ITEM": "E2"}):
                self.queued(tmp, "gate", "status")
            written = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual((written["issue"], written["item"]), (12, "E2"))

    def test_a_refused_command_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "requests.jsonl"
            with mock.patch.dict(os.environ, {"RESEARCH_REQUESTS": str(path)}):
                with self.assertRaises(SystemExit):
                    self.queued(tmp, "grid", "--command", "bash -c 'id'", "--issue", "9")
            self.assertFalse(path.exists())

    def test_the_cap_comes_from_the_variable_from_one_to_ten(self):
        self.assertEqual(research_loop.dispatches_per_run(""), 3)
        self.assertEqual(research_loop.dispatches_per_run("5"), 5)
        self.assertEqual(research_loop.dispatches_per_run("99"), 10)
        self.assertEqual(research_loop.dispatches_per_run("0"), 3)
        self.assertEqual(research_loop.dispatches_per_run("three"), 3)
        with mock.patch.dict(os.environ, {"RESEARCH_DISPATCHES_PER_RUN": "2"}):
            self.assertEqual(research_loop.dispatches_per_run(), 2)
            self.assertEqual(research_loop.dispatches_per_run(None), 2)


class Dispatch(unittest.TestCase):
    """The second job reads the session's requests again against main's code, runs what it admits up
    to the limit, and tells the item's issue, an open issue labelled research and no other."""

    def setUp(self):
        self.started = []

        def starter(workflow, inputs, repo, env=None, seen=()):
            self.started.append((workflow, dict(inputs), repo, list(seen)))
            number = 100 + len(self.started)
            return number, f"https://github.com/{repo}/actions/runs/{number}"

        self.starter = starter
        self.standing = {9: True, 12: False}
        self.asked = []

        def issue_check(repo, number):
            self.asked.append(number)
            return self.standing.get(number, False)

        self.issue_check = issue_check

    def settle(self, lines, limit=3):
        return research_loop.settle(lines, "o/r", limit, committed, self.issue_check, self.starter)

    def test_it_refuses_what_main_does_not_admit_and_runs_the_rest_in_order_up_to_the_limit(self):
        lines = [line(), line(workflow="synthesis.yml"), line(command="curl https://example.org"),
                 line(workflow="grid-gate.yml", word="fetch"), "not a request at all", line(issue=12),
                 line(workflow="grid-gate.yml", word="status"), line(command="python3 tools/claims_rank.py table")]
        rows, standing = self.settle(lines, limit=2)
        refused = [row["refused"] for row in rows]
        self.assertIsNone(refused[0])
        self.assertIn("dispatches only grid.yml, grid-gate.yml", refused[1])
        self.assertIn("the program is curl", refused[2])
        self.assertIn("the gate's word is one of", refused[3])
        self.assertIn("not a request", refused[4])
        self.assertIn("issue #12 is not an open issue labelled research", refused[5])
        self.assertIsNone(refused[6])
        self.assertIn("over this run's limit of 2", refused[7])
        self.assertEqual([(w, i) for w, i, _, _ in self.started],
                         [("grid.yml", {"command": "bash x.sh", "start": "false", "python": "true"}),
                          ("grid-gate.yml", {"word": "status"})])
        self.assertEqual(self.started[1][3], [101], "the second dispatch skips the first's run when it looks for its own")
        self.assertEqual((rows[0]["run"], rows[6]["url"]), (101, "https://github.com/o/r/actions/runs/102"))
        self.assertEqual(standing, {9: True, 12: False})
        self.assertEqual(self.asked, [9, 12], "each issue is asked about once")

    def test_the_shape_of_a_request_is_held(self):
        problems = {
            "start": research_loop.request_problem(dict(line(), inputs={"command": "bash x.sh", "start": "yes", "python": "true"}), committed),
            "names": research_loop.request_problem(dict(line(), inputs={"command": "bash x.sh"}), committed),
            "strings": research_loop.request_problem(dict(line(), inputs={"command": 1, "start": "true", "python": "true"}), committed),
            "issue": research_loop.request_problem(line(issue="03"), committed),
            "item": research_loop.request_problem(line(item="nine"), committed),
            "gate": research_loop.request_problem(dict(line(workflow="grid-gate.yml"), inputs={"word": "status", "x": "y"}), committed),
        }
        for name, problem in problems.items():
            with self.subTest(name=name):
                self.assertIsNotNone(problem)
        self.assertIsNone(research_loop.request_problem(line(item=""), committed))
        self.assertIsNone(research_loop.request_problem(line(workflow="grid-gate.yml"), committed))

    def test_the_report_begins_with_the_marker_and_names_each_request(self):
        rows, _ = self.settle([line(), line(command="curl x")])
        text = research_loop.report(rows, "https://github.com/o/r/actions/runs/7")
        self.assertTrue(text.startswith(research_loop.DISPATCH_MARKER + "\n"))
        self.assertIn("- dispatched grid.yml `bash x.sh`: https://github.com/o/r/actions/runs/101", text)
        self.assertIn("- refused grid.yml `curl x`: the program is curl", text)
        self.assertIn("actions/runs/7", text)
        self.assertIn("- no request", research_loop.report([]))

    def test_a_failed_dispatch_is_a_refusal_with_ghs_words_and_fails_the_job(self):
        def failing(workflow, inputs, repo, env=None, seen=()):
            raise subprocess.CalledProcessError(1, ["gh"], stderr="HTTP 403: refused\nmore")
        rows, _ = research_loop.settle([line()], "o/r", 3, committed, self.issue_check, failing)
        self.assertEqual(rows[0]["refused"], "gh workflow run failed: HTTP 403: refused")

    def test_the_command_comments_only_on_an_open_research_issue_and_writes_the_summary(self):
        comments = []
        with tempfile.TemporaryDirectory() as tmp:
            requests = Path(tmp) / "requests.jsonl"
            requests.write_text("\n".join(json.dumps(l) for l in (line(), line(issue=12), line(command="curl x")))
                                + "\nnot json\n", encoding="utf-8")
            summary = Path(tmp) / "summary.md"
            with mock.patch.object(research_loop, "research_issue", self.issue_check), \
                    mock.patch.object(research_loop, "start_run", self.starter), \
                    mock.patch.object(research_loop, "comment", lambda repo, n, text, env=None: comments.append((repo, n, text))), \
                    mock.patch.object(research_loop, "on_main", committed), \
                    mock.patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary), "GITHUB_RUN_ID": "7",
                                                 "GITHUB_SERVER_URL": "https://github.com"}):
                with redirect_stdout(io.StringIO()):
                    code = research_loop.main(["dispatch", "--requests", str(requests), "--repo", "o/r", "--limit", "3"])
            self.assertEqual(code, 0)
            self.assertEqual([(repo, n) for repo, n, _ in comments], [("o/r", 9)])
            text = comments[0][2]
            self.assertTrue(text.startswith(research_loop.DISPATCH_MARKER + "\n"))
            self.assertIn("dispatched grid.yml `bash x.sh`", text)
            self.assertIn("refused grid.yml `curl x`", text, "the issue hears of its refused requests too")
            self.assertNotIn("#12", text)
            written = summary.read_text(encoding="utf-8")
            self.assertIn("issue #12 is not an open issue labelled research", written)
            self.assertIn("not a request", written)
            self.assertIn("actions/runs/7", written)
            self.assertEqual(len(self.started), 1)

    def test_the_issue_check_reads_state_label_and_kind(self):
        answers = {
            "open": {"state": "open", "labels": [{"name": "research"}]},
            "closed": {"state": "closed", "labels": [{"name": "research"}]},
            "pull": {"state": "open", "labels": [{"name": "research"}], "pull_request": {}},
            "unlabelled": {"state": "open", "labels": [{"name": "todo"}]},
        }
        for name, answer in answers.items():
            with self.subTest(name=name), mock.patch.object(research_loop, "gh_json_env", lambda a, e, answer=answer: answer):
                self.assertEqual(research_loop.research_issue("o/r", 9), name == "open")

        def refused(args, env):
            raise subprocess.CalledProcessError(1, ["gh"], stderr="HTTP 404")
        with mock.patch.object(research_loop, "gh_json_env", refused):
            self.assertFalse(research_loop.research_issue("o/r", 9))

    def test_a_dispatch_flag_list_names_each_input_and_the_ref_is_main(self):
        calls = []

        def run(argv, **kw):
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 0, stdout="[]", stderr="")
        with mock.patch.object(research_loop.subprocess, "run", run), mock.patch.object(research_loop, "newest_run",
                                                                                       lambda *a, **k: (5, "u")):
            self.assertEqual(research_loop.start_run("grid-gate.yml", {"word": "stop"}, "o/r"), (5, "u"))
        self.assertEqual(calls, [["gh", "workflow", "run", "grid-gate.yml", "--repo", "o/r", "--ref", "main", "-f", "word=stop"]])


if __name__ == "__main__":
    unittest.main()
