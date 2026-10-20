"""tools/add_worker.py, what .github/workflows/add-worker.yml decides and
says, and the form whose answers it reads: the issue form asks exactly
the questions the library's registry reads (sdlc_protocol.workers.FORM),
an issue is the form's by its two dropdown headings, and every answer on
the issue says what to do next for the kind of worker it adds."""

import io
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

import add_worker  # noqa: E402
import crowd_check  # noqa: E402
from sdlc_protocol import workers  # noqa: E402

# In crowd mode scripts/crowd.py puts the crowd's worker page in the worker
# page's place, so the tests of the template's page hold only outside it, and
# the crowd's own page, which every copy carries, is tested as it stands.
CROWD = crowd_check.mode_of((ROOT / "docs" / "project.md").read_text(encoding="utf-8")) == "on"
CROWD_PAGE = ROOT / "docs" / "setup" / "crowd" / "worker.md"
IN_CROWD_MODE = "in crowd mode the worker page is the crowd's, tested below as docs/setup/crowd/worker.md"

FORM = ROOT / ".github" / "ISSUE_TEMPLATE" / "worker.yml"
WORKFLOW = ROOT / ".github" / "workflows" / "add-worker.yml"


def answers(**given):
    """An issue body as GitHub writes the form's answers, empty ones as
    GitHub's "_No response_"."""
    lines = []
    for label, key in workers.FORM:
        lines += [f"### {label}", "", str(given.get(key) or "_No response_"), ""]
    return "\n".join(lines)


class TheForm(unittest.TestCase):
    TEXT = FORM.read_text(encoding="utf-8")

    def test_it_asks_exactly_the_questions_the_registry_reads_in_order(self):
        labels = re.findall(r"^      label: (.+)$", self.TEXT, re.MULTILINE)
        self.assertEqual(labels, [label for label, _ in workers.FORM])

    def test_each_dropdown_option_starts_with_the_value_it_gives(self):
        options = re.findall(r'^        - "([a-z-]+): ', self.TEXT, re.MULTILINE)
        self.assertEqual(options, list(workers.RUNS) + list(workers.LANDS))

    def test_the_two_dropdown_headings_are_what_the_workflow_looks_for(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        for heading in add_worker.FORM_HEADINGS:
            self.assertIn(f"contains(github.event.issue.body, '{heading}')", text)
            self.assertIn(heading[len("### "):], self.TEXT)

    def test_the_answers_of_a_filled_form_make_a_worker(self):
        body = answers(name="nightly", runs="routine: a routine on someone's Claude account",
                       lands="owner: the owner merges each pull request", area="docs/")
        self.assertTrue(add_worker.is_form(body))
        worker = workers.from_dict(workers.from_form(body))
        self.assertEqual((worker.name, worker.runs, worker.area, worker.lands), ("nightly", "routine", ("docs/",), "owner"))


class Deciding(unittest.TestCase):
    def test_only_the_forms_answers_are_the_form(self):
        self.assertTrue(add_worker.is_form("### Where it runs\n\nx\n\n### How its pull requests land\n\ny\n"))
        self.assertFalse(add_worker.is_form("### Goal\n\nx\n\n### Acceptance\n\ny\n"))
        self.assertFalse(add_worker.is_form("I wrote ### Where it runs in a sentence"))
        self.assertFalse(add_worker.is_form(None))

    def test_the_branch_title_message_and_body_name_the_worker(self):
        self.assertEqual(add_worker.branch("nightly"), "symphony/worker-nightly")
        self.assertEqual(add_worker.title("nightly"), "Add the worker nightly")
        message = add_worker.message("nightly", "actions", "7")
        self.assertTrue(message.startswith("Add the worker nightly\n\nnightly is a worker in GitHub Actions:"))
        body = add_worker.body("nightly", "routine", "7")
        self.assertIn(".github/symphony/workers/nightly.json, from the answers on #7.", body)
        self.assertTrue(body.endswith("Closes #7\n"))


class Answering(unittest.TestCase):
    @unittest.skipIf(CROWD, IN_CROWD_MODE)
    def test_a_routine_gets_the_short_prompt_with_its_name_filled_in(self):
        text = add_worker.reply("nightly", "routine", "https://github.com/o/r/pull/9", True)
        self.assertTrue(text.startswith("The pull request that adds it: https://github.com/o/r/pull/9."))
        prompt = text.split("```")[1].strip("\n")
        self.assertIn("You are the worker nightly on the repository", prompt)
        self.assertIn("as the worker nightly.", prompt)
        self.assertNotIn(add_worker.NAME_SLOT, prompt)
        self.assertEqual(prompt, add_worker.short_prompt("nightly"))

    def test_a_worker_in_actions_needs_only_the_token(self):
        text = add_worker.reply("night", "actions", "https://github.com/o/r/compare/main...symphony/worker-night", False)
        self.assertIn("does not let GitHub Actions open a pull request", text)
        self.assertIn("CLAUDE_CODE_OAUTH_TOKEN", text)
        self.assertIn("There is nothing to paste.", text)
        self.assertNotIn("```", text)

    def test_a_persons_sessions_hear_how_to_take_the_name(self):
        text = add_worker.reply("alice-api", "session", "u", True)
        self.assertIn("SYMPHONY_WORKER=alice-api", text)

    def test_every_answer_says_nothing_here_is_a_credential(self):
        for runs in workers.RUNS:
            self.assertIn(add_worker.NOTHING_SECRET, add_worker.reply("x", runs, "u", True))

    def test_refused_answers_list_each_problem(self):
        text = add_worker.refused("workers: name must be lower case\nworkers: rounds must be a whole number\n")
        self.assertIn("- name must be lower case\n- rounds must be a whole number\n", text)
        self.assertNotIn("workers:", text)

    def test_a_routine_in_crowd_mode_is_sent_to_the_crowds_own_prompt(self):
        """The crowd's prompt names the worker by the contributor's login and
        keeps one of two area lines, which crowd.py fills in, so the answer
        sends the contributor there and pastes nothing half filled."""
        text = add_worker.reply("alice", "routine", "u", True, page=CROWD_PAGE)
        self.assertIn("python3 scripts/crowd.py doctor --worker", text)
        self.assertNotIn("```", text)
        self.assertNotIn(add_worker.LOGIN_SLOT, text)

    def test_the_crowds_page_is_told_from_the_templates_by_its_slot(self):
        self.assertTrue(add_worker.is_crowd_page(CROWD_PAGE))
        self.assertEqual(add_worker.is_crowd_page(), CROWD)

    @unittest.skipIf(CROWD, IN_CROWD_MODE)
    def test_the_short_prompt_is_the_worker_pages_first_block(self):
        page = (ROOT / "docs" / "agents" / "routines" / "worker.md").read_text(encoding="utf-8")
        first = page.split("```")[1].strip("\n")
        self.assertIn(add_worker.NAME_SLOT, first)
        self.assertEqual(add_worker.short_prompt("w1"), first.replace(add_worker.NAME_SLOT, "w1"))


class TheCommand(unittest.TestCase):
    def run_main(self, *argv, stdin=""):
        out = io.StringIO()
        with redirect_stdout(out), mock.patch.object(sys, "stdin", io.StringIO(stdin)):
            code = add_worker.main(list(argv))
        return code, out.getvalue()

    def test_is_form_answers_by_its_exit_code(self):
        self.assertEqual(self.run_main("is-form", stdin=answers(name="x", runs="session")), (0, ""))
        self.assertEqual(self.run_main("is-form", stdin="### Goal\n"), (1, ""))

    def test_each_text_is_printed(self):
        self.assertEqual(self.run_main("branch", "--name", "x"), (0, "symphony/worker-x\n"))
        self.assertEqual(self.run_main("title", "--name", "x"), (0, "Add the worker x\n"))
        code, out = self.run_main("reply", "--name", "x", "--runs", "routine", "--url", "u", "--opened")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("The pull request that adds it: u."))
        with tempfile.TemporaryDirectory() as folder:
            problems = Path(folder) / "problems.txt"
            problems.write_text("workers: runs must be one of actions, routine, session\n", encoding="utf-8")
            self.assertIn("- runs must be one of", self.run_main("refused", "--problems", str(problems))[1])

    def test_a_missing_argument_is_a_usage_error(self):
        with self.assertRaises(SystemExit) as caught, mock.patch("sys.stderr", io.StringIO()):
            add_worker.main(["reply", "--name", "x"])
        self.assertEqual(caught.exception.code, 2)

    def test_it_runs_as_a_script(self):
        done = subprocess.run([sys.executable, str(ROOT / "tools" / "add_worker.py"), "crowd"],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("crowd mode", done.stdout)


class TheWorkflow(unittest.TestCase):
    TEXT = WORKFLOW.read_text(encoding="utf-8")

    def test_it_names_no_secret_and_passes_the_body_through_the_environment(self):
        self.assertEqual(re.findall(r"secrets\.([A-Z_]+)", self.TEXT), [])
        self.assertIn("BODY: ${{ github.event.issue.body }}", self.TEXT)
        for line in self.TEXT.splitlines():
            if "github.event.issue.body" in line:
                self.assertTrue("BODY:" in line or "contains(" in line, line)

    def test_only_a_writer_adds_a_worker(self):
        self.assertIn('gh api "repos/$REPO/collaborators/$AUTHOR/permission" --jq .role_name', self.TEXT)
        self.assertIn("admin|maintain|write) ;;", self.TEXT)

    def test_it_starts_the_checks_on_its_branch_since_its_token_starts_none(self):
        self.assertIn('gh workflow run ci.yml --repo "$REPO" --ref "$branch"', self.TEXT)


if __name__ == "__main__":
    unittest.main()
