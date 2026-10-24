"""tools/research_loop.py: the research loop's switch and daily cap, the choice of item that never
duplicates work, the prompt it builds, and the inputs it hands the grid's workflows."""

import datetime
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

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

    def test_the_real_register_gives_a_choice(self):
        choice = research_loop.choose(research_loop.claims_rank.load(), [], [])
        self.assertEqual(choice["mode"], "new")


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
                      "claims.json", "run id", "blocked"):
            self.assertIn(words, brief)


class GridRoute(unittest.TestCase):
    def test_grid_inputs_carry_the_command_and_the_boxes(self):
        self.assertEqual(research_loop.grid_inputs("bash x.sh", True, False),
                         ["-f", "command=bash x.sh", "-F", "start=true", "-F", "python=false"])
        with self.assertRaises(SystemExit):
            research_loop.grid_inputs("  ", False, True)

    def test_the_gate_takes_only_its_three_words(self):
        self.assertEqual(research_loop.gate_inputs("status"), ["-f", "word=status"])
        with self.assertRaises(SystemExit):
            research_loop.gate_inputs("fetch")

    def test_only_the_grids_workflows_are_dispatched(self):
        with self.assertRaises(SystemExit):
            research_loop.dispatch("synthesis.yml", [], "o/r")

    def test_dispatch_needs_the_workflow_token(self):
        saved = research_loop.os.environ.pop("RESEARCH_DISPATCH_TOKEN", None)
        try:
            with self.assertRaises(SystemExit):
                research_loop.dispatch_env()
        finally:
            if saved is not None:
                research_loop.os.environ["RESEARCH_DISPATCH_TOKEN"] = saved


if __name__ == "__main__":
    unittest.main()
