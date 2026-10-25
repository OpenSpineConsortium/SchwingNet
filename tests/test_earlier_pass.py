"""tools/earlier_pass.py: a Checks run that no commit started skips the
work an earlier run on the same head passed, and does it whenever GitHub
cannot say so."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import earlier_pass  # noqa: E402

HEAD = "a" * 40
RUNS = "/repos/o/r/actions/workflows/ci.yml/runs"


def run(number, head=HEAD, created="2026-10-25T10:00:00Z", status="completed"):
    return {"id": number, "head_sha": head, "created_at": created, "status": status}


def job(name, conclusion="success", steps=()):
    return {"name": name, "conclusion": conclusion,
            "steps": [{"name": step, "conclusion": done} for step, done in steps]}


class FakeApi:
    repo = "o/r"

    def __init__(self, answers):
        self.answers = answers
        self.asked = []

    def get(self, path, params=None):
        self.asked.append((path, dict(params or {})))
        answer = self.answers[path]
        if isinstance(answer, Exception):
            raise answer
        return answer


def api_with(runs, jobs):
    answers = {RUNS: {"workflow_runs": runs}}
    answers.update({f"/repos/o/r/actions/runs/{number}/jobs": {"jobs": found} for number, found in jobs.items()})
    return FakeApi(answers)


class Standing(unittest.TestCase):
    def test_a_job_of_that_name_that_succeeded(self):
        passed = earlier_pass.PASSED
        self.assertEqual(earlier_pass.standing([job("check part 1/4")], "check part 1/4"), passed)
        self.assertIsNone(earlier_pass.standing([job("check part 1/4", "failure")], "check part 1/4"))
        self.assertIsNone(earlier_pass.standing([job("check part 1/4", "cancelled")], "check part 1/4"))
        self.assertIsNone(earlier_pass.standing([job("check part 2/4")], "check part 1/4"))
        self.assertIsNone(earlier_pass.standing([], "check part 1/4"))

    def test_with_a_step_the_step_decides(self):
        passed = earlier_pass.PASSED
        ran = job("check", steps=[("Run the checks", "success"), ("Hold a pull request", "success")])
        self.assertEqual(earlier_pass.standing([ran], "check", "Run the checks"), passed)
        # The body's checks failed after the checks passed: the checks still passed on the head.
        body_failed = job("check", "failure", steps=[("Run the checks", "success"), ("Hold", "failure")])
        self.assertEqual(earlier_pass.standing([body_failed], "check", "Run the checks"), passed)
        self.assertIsNone(earlier_pass.standing([body_failed], "check"))
        self.assertIsNone(earlier_pass.standing([job("check", steps=[("Run the checks", "failure")])],
                                                "check", "Run the checks"))
        self.assertIsNone(earlier_pass.standing([job("check")], "check", "Run the checks"))

    def test_a_step_skipped_in_a_job_that_succeeded_carries_a_pass(self):
        carried = job("check", steps=[("Run the checks", "skipped")])
        self.assertEqual(earlier_pass.standing([carried], "check", "Run the checks"), earlier_pass.CARRIED)
        # Skipped after an earlier step failed: no pass to carry.
        broken = job("check", "failure", steps=[("Clone", "failure"), ("Run the checks", "skipped")])
        self.assertIsNone(earlier_pass.standing([broken], "check", "Run the checks"))


class Verdict(unittest.TestCase):
    def test_the_newest_earlier_run_that_passed_the_job(self):
        api = api_with([run(7), run(9, created="2026-10-25T10:05:00Z")],
                       {9: [job("check part 1/4")], 7: [job("check part 1/4", "failure")]})
        passed, line = earlier_pass.verdict(api, "ci.yml", HEAD, "11", "check part 1/4")
        self.assertTrue(passed)
        self.assertIn("run 9 passed 'check part 1/4'", line)
        self.assertEqual([path for path, _ in api.asked], [RUNS, "/repos/o/r/actions/runs/9/jobs"])
        self.assertEqual(api.asked[0][1], {"head_sha": HEAD, "event": "pull_request", "per_page": 100})

    def test_only_the_newest_decides(self):
        # The newest failed, as on a base branch an edit changed: an older pass stands in for nothing.
        api = api_with([run(7), run(9, created="2026-10-25T10:05:00Z")],
                       {9: [job("check part 1/4", "failure")], 7: [job("check part 1/4")]})
        passed, line = earlier_pass.verdict(api, "ci.yml", HEAD, "11", "check part 1/4")
        self.assertFalse(passed, line)
        self.assertEqual([path for path, _ in api.asked], [RUNS, "/repos/o/r/actions/runs/9/jobs"])
        # The newest was cancelled, or is still going: the same.
        for newest in (run(9, created="2026-10-25T10:05:00Z", status="in_progress"),
                       run(9, created="2026-10-25T10:05:00Z", status="queued")):
            api = api_with([run(7), newest], {7: [job("check part 1/4")]})
            passed, line = earlier_pass.verdict(api, "ci.yml", HEAD, "11", "check part 1/4")
            self.assertFalse(passed, line)
            self.assertEqual([path for path, _ in api.asked], [RUNS])
        api = api_with([run(7), run(9, created="2026-10-25T10:05:00Z")],
                       {9: [job("check part 1/4", "cancelled")], 7: [job("check part 1/4")]})
        self.assertFalse(earlier_pass.verdict(api, "ci.yml", HEAD, "11", "check part 1/4")[0])

    def test_a_carried_pass_is_read_past_to_the_run_that_passed(self):
        jobs = {9: [job("check", steps=[("Run the checks", "skipped")])],
                7: [job("check", "failure", steps=[("Run the checks", "success"), ("Hold", "failure")])]}
        api = api_with([run(7), run(9, created="2026-10-25T10:05:00Z")], jobs)
        passed, line = earlier_pass.verdict(api, "ci.yml", HEAD, "11", "check", "Run the checks")
        self.assertTrue(passed, line)
        self.assertIn("run 7 passed 'check' (step 'Run the checks') on aaaaaaaaaaaa", line)
        # A carried run with nothing before it carries nothing.
        api = api_with([run(9)], {9: jobs[9]})
        self.assertFalse(earlier_pass.verdict(api, "ci.yml", HEAD, "11", "check", "Run the checks")[0])

    def test_the_run_asking_and_other_heads_never_count(self):
        api = api_with([run(11), run(5, head="b" * 40)], {11: [job("check")], 5: [job("check")]})
        passed, line = earlier_pass.verdict(api, "ci.yml", HEAD, "11", "check")
        self.assertFalse(passed)
        self.assertIn("no earlier run on aaaaaaaaaaaa passed 'check', so it runs", line)
        self.assertEqual([path for path, _ in api.asked], [RUNS])

    def test_whatever_github_does_not_answer_runs_the_work(self):
        for broken in ({RUNS: OSError("no answer")},
                       {RUNS: {"workflow_runs": [run(7)]}, "/repos/o/r/actions/runs/7/jobs": OSError("refused")},
                       {RUNS: None},
                       {RUNS: {"workflow_runs": [run(7)]}, "/repos/o/r/actions/runs/7/jobs": None},
                       {RUNS: {"workflow_runs": [dict(run(7), status=None)]}}):
            passed, line = earlier_pass.verdict(FakeApi(broken), "ci.yml", HEAD, "11", "check")
            self.assertFalse(passed, line)


class Main(unittest.TestCase):
    def output_of(self, environ, api=None, argv=("--job", "check")):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "output"
            environ = dict(environ, GITHUB_OUTPUT=str(target))
            with mock.patch.dict(os.environ, environ, clear=True), \
                    mock.patch.object(earlier_pass, "client", return_value=api):
                self.assertEqual(earlier_pass.main(list(argv)), 0)
            return target.read_text()

    def test_it_writes_the_verdict_for_the_steps_that_follow(self):
        api = api_with([run(7)], {7: [job("check")]})
        environ = {"HEAD_SHA": HEAD, "GITHUB_RUN_ID": "11", "GITHUB_REPOSITORY": "o/r"}
        self.assertEqual(self.output_of(environ, api), "passed=true\n")
        self.assertEqual(self.output_of(environ, api_with([], {})), "passed=false\n")

    def test_no_head_runs_the_work(self):
        self.assertEqual(self.output_of({"GITHUB_REPOSITORY": "o/r"}), "passed=false\n")

    def test_no_client_runs_the_work(self):
        environ = {"HEAD_SHA": HEAD, "GITHUB_REPOSITORY": "o/r"}
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "output"
            with mock.patch.dict(os.environ, dict(environ, GITHUB_OUTPUT=str(target)), clear=True):
                self.assertEqual(earlier_pass.main(["--job", "check"]), 0)
            self.assertEqual(target.read_text(), "passed=false\n")


if __name__ == "__main__":
    unittest.main()
