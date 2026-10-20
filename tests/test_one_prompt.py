"""One prompt for every worker and one for the coordinator, wherever they
run: a routine pastes the short prompt of docs/agents/routines/worker.md or
coordinator.md, and .github/workflows/workers.yml and coordinator.yml pass
the same words, with GitHub's own values where the page names the
repository and its default branch, so a worker in Actions and a routine
read the same full prompt and do the same thing. The page names them with
placeholders in the template and with the copy's own names once
tools/template_init.py has filled it, while the workflows, which the fill
never writes, keep GitHub's values; so the comparison reads what the page
holds in those places, and holds the template's page to the placeholders.
The workflows also read the registry the way the library reads it, so a
worker's file decides its model, turns and rounds."""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
ROUTINES = ROOT / "docs" / "agents" / "routines"
P = {"REPO": "{{" + "REPO" + "}}", "DEFAULT_BRANCH": "{{" + "DEFAULT_BRANCH" + "}}"}
GITHUB = {"REPO": "${{ github.repository }}", "DEFAULT_BRANCH": "${{ env.DEFAULT_BRANCH }}"}
IN_TEMPLATE = (ROOT / ".template" / "PENDING").is_file()
CROWD_PAGE = ROOT / "docs" / "setup" / "crowd" / "worker.md"
# How many characters on either side of a name find it in a page whose
# other words differ from the workflow's.
NEAR = 16
sys.path.insert(0, str(ROOT / "tools"))

import crowd_check  # noqa: E402

# In crowd mode no worker runs in GitHub Actions, since CLAUDE_CROWD keeps
# workers.yml from starting (tests/test_crowd_check.py), and scripts/crowd.py
# puts the crowd's worker page in the worker page's place, whose prompt names
# the worker LOGIN, the contributor's login, where the template's says NAME.
CROWD = crowd_check.mode_of((ROOT / "docs" / "project.md").read_text(encoding="utf-8")) == "on"


def short_prompt(page):
    return (ROUTINES / page).read_text(encoding="utf-8").split("```")[1].strip("\n")


def names_held(page, sent):
    """What a page's words hold where the workflow's words have GitHub's own
    values: one name for the repository and one for its default branch, each
    the same wherever it stands; None when the words around them differ."""
    pattern, seen = "", set()
    for piece in re.split("(" + "|".join(map(re.escape, GITHUB.values())) + ")", sent):
        key = next((key for key, value in GITHUB.items() if value == piece), None)
        if key is None:
            pattern += re.escape(piece)
        elif key in seen:
            pattern += f"(?P={key})"
        else:
            seen.add(key)
            pattern += rf"(?P<{key}>\S+?)"
    found = re.fullmatch(pattern, page)
    return found.groupdict() if found else None


def names_near(page, sent):
    """For showing words that differ: the name a page holds where the
    workflow's words first have each of GitHub's values, found by the words
    on either side, so that a difference elsewhere shows alone; the
    placeholder where the words beside it differ too. Each is one word, as a
    name names_held finds is, so words it found differing still differ with
    these names in place."""
    names = {}
    for key, value in GITHUB.items():
        before, found, after = sent.partition(value)
        if not found:
            continue
        near = re.search(re.escape(before[-NEAR:]) + r"(\S+)" + re.escape(after[:NEAR]), page)
        names[key] = near.group(1) if near else P[key]
    return names


def as_the_page_holds(sent, names):
    """The workflow's words with the page's names where GitHub's values stand."""
    for key, name in names.items():
        sent = sent.replace(GITHUB[key], name)
    return sent


def assert_passes(test, page, sent):
    """The workflow passes the page's words: the same words, with GitHub's
    values where the page names the repository and its default branch,
    which the template's page names by placeholder. Words that differ are
    shown with the names the page should hold in those places, the
    placeholders in the template and in a copy the names found beside them,
    so that only the words that differ show."""
    names = names_held(page, sent)
    shown = names if names is not None else P if IN_TEMPLATE else names_near(page, sent)
    test.assertEqual(as_the_page_holds(sent, shown), page)
    if IN_TEMPLATE:
        test.assertEqual(names, {key: P[key] for key in names},
                         "the template's page names the repository and its default branch by placeholder")


def prompt_of(workflow, step_id):
    """The prompt input of the step with this id, as one line."""
    text = (WORKFLOWS / workflow).read_text(encoding="utf-8")
    step = text.split(f"id: {step_id}\n", 1)[1]
    block = step.split("prompt: |\n", 1)[1]
    lines = []
    for line in block.splitlines():
        if line.strip() and not line.startswith(" " * 12):
            break
        lines.append(line.strip())
    return " ".join(line for line in lines if line)


def assert_reads_its_own_file_and_given_issues_first(test, page, name):
    full = page.read_text(encoding="utf-8").split("```")[-2]
    test.assertIn(f"worker:{name}", full)
    test.assertIn(f'"- Worker: {name}"', full)
    test.assertIn(f".github/symphony/workers/{name}.json", full)
    test.assertIn('the board\'s "Given to workers" section', full)
    test.assertLess(full.index("If whoever started this run named an issue, take that one."),
                    full.index("Given to workers"))


class TheWorkerPrompt(unittest.TestCase):
    @unittest.skipIf(CROWD, "in crowd mode no worker runs in GitHub Actions and the page is the crowd's")
    def test_a_worker_in_actions_gets_the_routines_short_prompt_with_its_name(self):
        routine = short_prompt("worker.md").replace("<name>", "${{ matrix.worker }}")
        sent = prompt_of("workers.yml", "claude")
        self.assertIn("This run, ${{ steps.next.outputs.move }} issue #${{ steps.next.outputs.issue }}", sent)
        # The workflow passes the routine's words up to their last sentence,
        # and then a sentence of the run's own.
        assert_passes(self, routine.split(" Read it again on every run")[0], sent.split(" This run, ")[0])

    def test_the_full_prompt_reads_the_workers_file_and_its_given_issues_first(self):
        assert_reads_its_own_file_and_given_issues_first(self, ROUTINES / "worker.md", "LOGIN" if CROWD else "NAME")

    def test_the_crowds_full_prompt_does_the_same_under_the_contributors_login(self):
        assert_reads_its_own_file_and_given_issues_first(self, CROWD_PAGE, "LOGIN")

    def test_the_workflow_reads_the_registry_and_the_workers_own_settings(self):
        text = (WORKFLOWS / "workers.yml").read_text(encoding="utf-8")
        self.assertIn("python3 tools/workers.py list --runs actions", text)
        # The first job deals the run from one look and hands each leg its
        # move; a leg asks for itself only while the vendored library has
        # no deal (symphony-protocol's F4).
        self.assertIn('python3 tools/team.py deal --registry "$REGISTRY" --workers "$workers"', text)
        self.assertIn("deals: ${{ steps.list.outputs.deals }}", text)
        self.assertIn("DEALS: ${{ needs.registry.outputs.deals }}", text)
        self.assertIn('python3 tools/team.py next --agent "$WORKER" --registry "$REGISTRY" --label "worker:$WORKER"', text)
        self.assertIn("for setting in model max_turns rounds; do", text)
        self.assertIn("--max-turns ${{ steps.next.outputs.max_turns }}", text)
        self.assertIn("ROUNDS: ${{ steps.next.outputs.rounds }}", text)
        from sdlc_protocol import workers
        for setting in ("model", "max_turns", "rounds"):
            self.assertIn(setting, workers.KEYS)


class TheCoordinatorPrompt(unittest.TestCase):
    def test_the_weekly_run_passes_the_routines_short_prompt(self):
        assert_passes(self, short_prompt("coordinator.md"), prompt_of("coordinator.yml", "tidy"))

    def test_the_full_prompt_leaves_releases_and_overlaps_to_the_board(self):
        full = (ROUTINES / "coordinator.md").read_text(encoding="utf-8").split("```")[-2]
        self.assertIn("The board's own run releases idle claims and tells open work that overlaps", full)
        self.assertNotIn("claim-released", full)
        self.assertEqual(re.findall(r"^(\d)\. ", full, re.MULTILINE), ["1", "2"])

    def test_the_plan_asks_for_the_clerks_schema_and_names_the_workers(self):
        text = (WORKFLOWS / "coordinator.yml").read_text(encoding="utf-8")
        self.assertIn('python3 tools/team.py schema --registry "$REGISTRY"', text)
        self.assertIn('python3 tools/workers.py --dir "$REGISTRY" describe', text)
        self.assertIn("--json-schema '${{ steps.due.outputs.schema }}'", text)
        self.assertIn('python3 tools/team.py seed --epic "$EPIC" --plan "$RUNNER_TEMP/plan.json" --registry "$REGISTRY"',
                      text)


if __name__ == "__main__":
    unittest.main()
