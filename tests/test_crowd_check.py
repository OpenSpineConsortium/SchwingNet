"""tools/crowd_check.py holds a crowd repository to its rules inside the
required check and keeps its queue to what maintainers queued; the
workflows run it where GitHub will enforce it, and keep the Claude
workflows from starting in crowd mode while changing nothing elsewhere.

The workflows are read as text, the standard library having no YAML
parser, the same way tests/test_vendored.py reads ci.yml. The guard runs
against temporary git repositories and the queue gate against the fake gh
of tests/fake_gh.py; nothing here has the network. The template's
placeholders are assembled at run time, so template-init leaves this file
alone.
"""

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import crowd_check  # noqa: E402
import fake_gh  # noqa: E402
import marked_section  # noqa: E402
import template_init  # noqa: E402
from fake_gh import answer  # noqa: E402

TOOL = ROOT / "tools" / "crowd_check.py"
WORKFLOWS = ROOT / ".github" / "workflows"
REPO = "octo/widgets"
API = f"repos/{REPO}"
IN_TEMPLATE = (ROOT / ".template" / "PENDING").is_file()
CROWD_OFF = "vars.CLAUDE_CROWD != 'true' &&"
CROWD_ON = "vars.CLAUDE_CROWD == 'true' &&"
STATUS_FUNCTIONS = ("always()", "failure()", "cancelled()")
FORBIDDEN = crowd_check.SECRET_NAMES + crowd_check.VARIABLE_NAMES
# A workflow runs on a subscription when it uses Claude's action or hands the
# token's value to a step; ci.yml's guard only compares it with nothing.
REACHES_CLAUDE = re.compile(r"anthropics/claude-code-action|secrets\.CLAUDE_CODE_OAUTH_TOKEN\s*\}\}")
# A step that hands a routine's trigger pair to a command can start that
# routine on its owner's subscription.
TRIGGER_SECRET = re.compile(r"secrets\.COORDINATOR_TRIGGER_[A-Z]+\s*\}\}")

# The job-level condition in front of which each Claude workflow puts the
# gate, held here so the gate is proven to leave it whole: @claude's from
# before crowd mode, and the workers' and the coordinator's, which replaced
# the worker's and the lead's.
OLD_CONDITIONS = {
    ("claude.yml", "claude"): (
        "contains(fromJSON('[\"OWNER\", \"MEMBER\", \"COLLABORATOR\"]'), "
        "github.event.comment.author_association || github.event.review.author_association || "
        "github.event.issue.author_association) && ("
        "(github.event_name == 'issue_comment' && contains(github.event.comment.body, '@claude')) || "
        "(github.event_name == 'pull_request_review_comment' && contains(github.event.comment.body, '@claude')) || "
        "(github.event_name == 'pull_request_review' && contains(github.event.review.body, '@claude')) || "
        "(github.event_name == 'issues' && (contains(github.event.issue.body, '@claude') || "
        "contains(github.event.issue.title, '@claude'))))"
    ),
    ("workers.yml", "registry"): (
        "github.event_name != 'issues' "
        "|| (!contains(github.event.issue.labels.*.name, 'claimed') "
        "&& (github.event.label.name == 'todo' || github.event.label.name == 'blocker' "
        "|| startsWith(github.event.label.name, 'worker:')))"
    ),
    ("coordinator.yml", "route"): (
        "(github.event_name == 'workflow_dispatch' && inputs.event != 'tidy') "
        "|| (github.event.action == 'labeled' && github.event.label.name == 'epic') "
        "|| (github.event.action == 'labeled' && github.event.label.name == 'blocked' "
        "&& contains(github.event.issue.body, 'Epic: #')) "
        "|| (github.event.action == 'closed' && contains(github.event.issue.body, 'Epic: #'))"
    ),
}


# Reading workflows as text.

def jobs_of(name):
    """A workflow's jobs, each as its lines: a job starts two spaces in under
    the top-level key jobs."""
    lines = (WORKFLOWS / name).read_text(encoding="utf-8").split("\n")
    jobs, current = {}, None
    for line in lines[lines.index("jobs:") + 1:]:
        start = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if start:
            current = start.group(1)
            jobs[current] = []
        elif line.strip() and not line.startswith(" "):
            break
        elif current:
            jobs[current].append(line)
    return jobs


def key_of(lines, key, indent=4):
    """One key's value, a block scalar's lines folded into one, with the
    whitespace squeezed; None when the key is not there."""
    pattern = re.compile("^" + " " * indent + re.escape(key) + r":\s*(.*)$")
    for number, line in enumerate(lines):
        match = pattern.match(line)
        if not match:
            continue
        value = match.group(1)
        if value in ("|", "|-", ">", ">-"):
            folded = []
            for more in lines[number + 1:]:
                if more.strip() and not more.startswith(" " * (indent + 2)):
                    break
                folded.append(more.strip())
            value = " ".join(folded)
        return squeezed(value)
    return None


def squeezed(expression):
    expression = " ".join(expression.split())
    return re.sub(r"\s+\)", ")", re.sub(r"\(\s+", "(", expression))


def top_level(expression, operator):
    """Whether operator occurs outside every parenthesis and quoted string."""
    depth, quoted = 0, False
    for index, char in enumerate(expression):
        if char == "'":
            quoted = not quoted
        elif not quoted and char == "(":
            depth += 1
        elif not quoted and char == ")":
            depth -= 1
        elif not quoted and depth == 0 and expression.startswith(operator, index):
            return True
    return False


def needs_of(lines):
    value = key_of(lines, "needs") or ""
    return [name.strip() for name in value.strip("[]").split(",") if name.strip()]


def gated(jobs, name):
    """Whether a job never starts in crowd mode: its own condition puts the
    gate first, or every job it needs is gated and it asks for no status
    function, so GitHub skips it with them."""
    condition = key_of(jobs[name], "if") or ""
    if condition.startswith(CROWD_OFF):
        return True
    needs = needs_of(jobs[name])
    return bool(needs) and all(gated(jobs, need) for need in needs) and not any(
        function in condition for function in STATUS_FUNCTIONS)


def steps_of(job_lines):
    """One job's steps, each as its lines: a step starts with a dash six
    spaces in, under the job's key steps."""
    text = "\n".join(job_lines)
    steps = text.split("\n    steps:\n", 1)[1] if "\n    steps:\n" in text else text.split("    steps:\n", 1)[1]
    return [step.splitlines() for step in re.split(r"\n(?=      - )", steps.rstrip("\n"))]


def ci_steps(job="check"):
    """One of ci.yml's jobs, step by step."""
    return steps_of(jobs_of("ci.yml")[job])


def step_named(steps, name):
    return next(step for step in steps if step[0].strip() == f"- name: {name}")


def guard_step():
    return step_named(ci_steps(), "Hold a crowd repository to its rules")


def step_env(step):
    found = {}
    for line in step:
        match = re.match(r"^\s{10}([A-Z_]+): (.*)$", line)
        if match:
            found[match.group(1)] = match.group(2)
    return found


class ClaudeWorkflowsInCrowdMode(unittest.TestCase):
    """The workflows that run on a subscription never start while CLAUDE_CROWD
    is true, and run exactly as before where it is unset."""

    def test_each_puts_the_gate_before_its_old_condition_and_keeps_it_whole(self):
        for (workflow, job), old in OLD_CONDITIONS.items():
            condition = key_of(jobs_of(workflow)[job], "if")
            self.assertTrue(condition.startswith(CROWD_OFF + " "), (workflow, condition))
            rest = condition[len(CROWD_OFF) + 1:]
            if top_level(squeezed(old), "||"):
                self.assertEqual(rest, "(" + squeezed(old) + ")", workflow)
            else:
                self.assertEqual(rest, squeezed(old), workflow)

    def test_every_job_of_a_workflow_that_reaches_claude_is_gated(self):
        found = set()
        for path in sorted(WORKFLOWS.glob("*.yml")):
            if not REACHES_CLAUDE.search(path.read_text(encoding="utf-8")):
                continue
            found.add(path.name)
            jobs = jobs_of(path.name)
            for name in jobs:
                self.assertTrue(gated(jobs, name), f"{path.name}: job {name} can start in crowd mode")
        self.assertLessEqual({"claude.yml", "coordinator.yml", "workers.yml"}, found)

    def test_every_step_that_can_start_a_routine_is_gated(self):
        # A routine's trigger runs on its owner's subscription; a pair that
        # reaches a crowd repository must not let a writer's push start it.
        found = []
        for path in sorted(WORKFLOWS.glob("*.yml")):
            jobs = jobs_of(path.name)
            for name, lines in jobs.items():
                if not any(TRIGGER_SECRET.search(line) for line in lines) or gated(jobs, name):
                    continue
                for step in steps_of(lines):
                    if any(TRIGGER_SECRET.search(line) for line in step):
                        found.append((path.name, step[0].strip()))
                        condition = key_of(step, "if", indent=8) or ""
                        self.assertTrue(condition.startswith(CROWD_OFF + " "), (path.name, step[0], condition))
        self.assertIn(("board.yml", "- name: Tell the coordinator routine"), found)

    def test_the_coordinators_later_jobs_need_route_and_ask_for_no_status_function(self):
        jobs = jobs_of("coordinator.yml")
        for name in ("plan", "unblock", "integrate"):
            self.assertEqual(needs_of(jobs[name]), ["route"], name)
            for function in STATUS_FUNCTIONS:
                self.assertNotIn(function, key_of(jobs[name], "if"), name)

    def test_each_says_so_in_its_header(self):
        for workflow in ("claude.yml", "coordinator.yml", "workers.yml", "board.yml"):
            header = (WORKFLOWS / workflow).read_text(encoding="utf-8").split("\non:", 1)[0]
            self.assertIn("In crowd mode", header, workflow)


class GuardStep(unittest.TestCase):
    """The guard is a step of the required check; the job values, which runs
    no code of the repository's, tells it which secrets exist by name."""

    def test_it_runs_after_the_checks_in_the_job_check(self):
        names = [step[0].strip() for step in ci_steps()]
        self.assertLess(names.index("- name: Run the checks"),
                        names.index("- name: Hold a crowd repository to its rules"))
        self.assertIn("        run: python3 tools/crowd_check.py guard", guard_step())

    def test_the_job_that_runs_the_repositorys_code_names_no_secret(self):
        # GitHub hands a job's runner every secret the job names, and the
        # checks and tests a pull request brings run in check.
        for line in jobs_of("ci.yml")["check"]:
            self.assertNotIn("secrets.", line)

    def test_values_compares_each_secret_with_nothing_and_runs_nothing_of_the_repositorys(self):
        lines = jobs_of("ci.yml")["values"]
        steps = steps_of(lines)
        self.assertEqual(len(steps), 1)
        env = step_env(steps[0])
        wanted = {f"SET_{name}": f"${{{{ secrets.{name} != '' }}}}" for name in crowd_check.SECRET_NAMES}
        self.assertEqual(env, wanted)
        for line in lines:
            self.assertNotRegex(line, r"uses:|checkout|tools/|scripts/|python|bash ", line)
            for value in re.findall(r"secrets\.[A-Z_]+[^}]*", line):
                self.assertRegex(value, r"^secrets\.[A-Z_]+ != '' $", line)
        self.assertIsNone(key_of(lines, "if"))
        self.assertEqual(key_of(lines, "secrets", indent=6), "${{ steps.names.outputs.secrets }}")

    def test_values_prints_only_the_names_that_are_set(self):
        block = "\n".join(jobs_of("ci.yml")["values"]).split("run: |", 1)[1]
        run = "\n".join(line.strip() for line in block.splitlines())
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "output"
            environ = clean_environment(GITHUB_OUTPUT=str(output), SET_ANTHROPIC_API_KEY="true",
                                        SET_SDLC_APP_PRIVATE_KEY="true", SET_CLAUDE_CODE_OAUTH_TOKEN="false")
            done = subprocess.run(["bash", "-c", run], capture_output=True, text=True, env=environ)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(output.read_text(), "secrets=ANTHROPIC_API_KEY SDLC_APP_PRIVATE_KEY\n")
            self.assertEqual(crowd_check.present_names({"SECRETS_SET": "ANTHROPIC_API_KEY SDLC_APP_PRIVATE_KEY"}),
                             ["ANTHROPIC_API_KEY", "SDLC_APP_PRIVATE_KEY"])
            environ = clean_environment(GITHUB_OUTPUT=str(output))
            output.write_text("")
            subprocess.run(["bash", "-c", run], capture_output=True, text=True, env=environ, check=True)
            self.assertEqual(output.read_text(), "secrets=\n")

    def test_check_needs_values_and_runs_whatever_values_did(self):
        lines = jobs_of("ci.yml")["check"]
        self.assertEqual(needs_of(lines), ["values"])
        self.assertEqual(key_of(lines, "if"), "${{ !cancelled() }}")
        env = step_env(guard_step())
        self.assertEqual(env["SECRETS_SET"], "${{ needs.values.outputs.secrets }}")
        self.assertEqual(env["VALUES_RESULT"], "${{ needs.values.result }}")
        flags = {name: value for name, value in env.items() if name.startswith(crowd_check.SET_PREFIX)}
        self.assertEqual(flags, {f"SET_{name}": f"${{{{ vars.{name} != '' }}}}" for name in crowd_check.VARIABLE_NAMES})

    def test_it_is_never_skipped_and_tells_a_fork_from_this_repository(self):
        self.assertFalse([line for line in guard_step() if line.strip().startswith("if:")])
        env = step_env(guard_step())
        self.assertEqual(env["CLAUDE_CROWD"], "${{ vars.CLAUDE_CROWD }}")
        self.assertEqual(env["BASE_SHA"], "${{ github.event.pull_request.base.sha }}")
        self.assertIn("github.event.pull_request.head.repo.full_name != github.repository", env["FROM_FORK"])

    def test_the_push_trigger_leaves_out_the_setup_branch(self):
        text = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
        self.assertIn('branches-ignore: ["claude/**", "symphony-protocol/**", "crowd/setup", "metrics"]', text)


class QueueWorkflow(unittest.TestCase):
    def test_it_starts_only_in_crowd_mode_and_on_a_queue_label(self):
        jobs = jobs_of("queue.yml")
        condition = key_of(jobs["gate"], "if")
        self.assertTrue(condition.startswith(CROWD_ON + " "), condition)
        for label in crowd_check.QUEUE_LABELS:
            self.assertIn(f"github.event.label.name == '{label}'", condition)
            self.assertIn(f"contains(github.event.issue.labels.*.name, '{label}')", condition)

    def test_it_runs_on_issue_events_with_the_workflows_own_token_alone(self):
        text = (WORKFLOWS / "queue.yml").read_text(encoding="utf-8")
        self.assertIn("  issues:\n    types: [opened, labeled, edited]\n", text)
        self.assertNotIn("secrets.", text)
        self.assertIn("GH_TOKEN: ${{ github.token }}", text)
        self.assertIn("run: python3 tools/crowd_check.py queue", text)
        self.assertNotIn("\n    concurrency:", text)


def files(mode=None, block="nothing yet", session="old notes\n", outside="text"):
    """The three guarded files, with docs/project.md's mode line as given."""
    project = "# Project\n\n## Crowd mode\n\n" + (f"- Crowd mode: {mode}. More.\n" if mode else "")
    claude = (f"# Instructions\n\n{outside}\n\n" + marked_section.MARK_BEGIN + "\n" + block + "\n"
              + marked_section.MARK_END + "\n")
    return {crowd_check.PROJECT: project, crowd_check.CLAUDE_MD: claude, crowd_check.SESSION: session}


def problems(base, head=None, crowd="", present=(), pull_request=True, from_fork=False, values_result="success"):
    return crowd_check.guard_problems(base, head or base, crowd, list(present), pull_request, REPO, from_fork,
                                      values_result)


class GuardProblems(unittest.TestCase):
    def test_off_everywhere_passes_with_every_value_set(self):
        self.assertEqual(problems(files("off"), present=FORBIDDEN), [])
        self.assertEqual(problems(files(None), present=FORBIDDEN), [])
        self.assertEqual(crowd_check.guard_summary(files("off"), files("off"), ""), "crowd: off")

    def test_on_with_each_value_set_fails_naming_it(self):
        for name in FORBIDDEN:
            found = problems(files("on"), crowd="true", present=[name])
            self.assertEqual(len(found), 1, name)
            kind = "secret" if name in crowd_check.SECRET_NAMES else "variable"
            self.assertIn(f"the {kind} {name} reaches this repository", found[0])
            self.assertIn(f"gh {kind} delete {name} --repo {REPO}", found[0])

    def test_main_on_without_the_variable_fails(self):
        for value in ("", "false"):
            found = problems(files("on"), crowd=value)
            self.assertEqual(len(found), 1)
            self.assertIn(f"gh variable set CLAUDE_CROWD --repo {REPO} --body true", found[0])

    def test_the_variable_is_read_without_case(self):
        self.assertEqual(problems(files("on"), crowd="True"), [])

    def test_a_value_the_workflows_gate_reads_as_not_true_fails(self):
        # GitHub's != ignores case and trims nothing, so "true " leaves
        # claude.yml's gate open; the guard calls that off, not on.
        for value in ("true ", " true", "true\n", "yes"):
            found = problems(files("on"), crowd=value)
            self.assertEqual(len(found), 1, repr(value))
            self.assertIn("is not true", found[0])

    def test_the_variable_alone_holds_setups_window_to_the_secret_rule(self):
        found = problems(files("off"), crowd="true", present=["CLAUDE_CODE_OAUTH_TOKEN"])
        self.assertEqual(len(found), 1)
        self.assertIn("CLAUDE_CODE_OAUTH_TOKEN", found[0])

    def test_the_setup_pull_request_turning_it_on_is_held_to_the_secret_rule(self):
        found = problems(files("off"), files("on", block="crowd sentence"), present=["SDLC_APP_PRIVATE_KEY"])
        self.assertEqual(len(found), 1)
        self.assertIn("SDLC_APP_PRIVATE_KEY", found[0])

    def test_main_off_lets_the_setup_pull_request_write_the_block_once(self):
        self.assertEqual(problems(files("off"), files("on", block="crowd sentence"), crowd="true"), [])

    def test_main_on_refuses_a_change_to_the_session_file_or_the_block(self):
        for head, what in ((files("on", session="new notes\n"), crowd_check.SESSION),
                           (files("on", block="a checkpoint"), "the checkpoint block of CLAUDE.md")):
            found = problems(files("on"), head, crowd="true")
            self.assertEqual(len(found), 1, what)
            self.assertIn(f"this pull request changes {what}", found[0])

    def test_main_on_takes_a_change_to_claude_md_outside_the_block(self):
        self.assertEqual(problems(files("on"), files("on", outside="other text"), crowd="true"), [])

    def test_a_deleted_session_file_or_lost_markers_count_as_a_change(self):
        head = files("on")
        head[crowd_check.SESSION] = None
        self.assertEqual(len(problems(files("on"), head, crowd="true")), 1)
        head = files("on")
        head[crowd_check.CLAUDE_MD] = "# Instructions\n"
        self.assertEqual(len(problems(files("on"), head, crowd="true")), 1)

    def test_a_pull_request_turning_it_off_is_still_held_to_the_rules(self):
        head = files("off", session="new notes\n")
        found = problems(files("on"), head, crowd="", present=["CLAUDE_WORKER"])
        self.assertEqual(len(found), 3)

    def test_a_push_is_held_to_the_values_and_the_gate_but_has_no_diff(self):
        self.assertEqual(problems(files("on"), files("on", session="x\n"), crowd="true", pull_request=False), [])
        self.assertEqual(len(problems(files("on"), pull_request=False)), 1)

    def test_a_forks_pull_request_is_held_to_the_checkpoint_rule_alone(self):
        self.assertEqual(problems(files("on"), crowd="", present=FORBIDDEN, from_fork=True), [])
        found = problems(files("on"), files("on", session="new\n"), crowd="", from_fork=True)
        self.assertEqual(len(found), 1)
        self.assertIn(crowd_check.SESSION, found[0])

    def test_the_summary_says_on_and_what_it_saw(self):
        summary = crowd_check.guard_summary(files("on"), files("on"), "true")
        self.assertTrue(summary.startswith("crowd: on"), summary)
        self.assertIn("its rules hold", summary)

    def test_the_names_are_read_by_name_and_only_true_counts_for_a_variable(self):
        environ = {"SECRETS_SET": "CLAUDE_CODE_OAUTH_TOKEN OTHER", "SET_CLAUDE_TEAM": "false", "SET_CLAUDE_WORKER": "true",
                   "SET_ANTHROPIC_API_KEY": "true"}
        self.assertEqual(crowd_check.present_names(environ), ["CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_WORKER"])

    def test_values_that_did_not_succeed_fail_crowd_mode_and_nothing_else(self):
        for result in ("failure", "cancelled", ""):
            found = problems(files("on"), crowd="true", values_result=result)
            self.assertEqual(len(found), 1, result)
            self.assertIn("whether one does is unknown", found[0])
        self.assertEqual(problems(files("off"), values_result="failure"), [])
        self.assertEqual(problems(files("on"), crowd="", values_result="failure", from_fork=True), [])


def clean_environment(**extra):
    """The environment without git's own variables, which would point the
    git the tests start at another repository, and without any GitHub event
    variable the outer run has."""
    environ = {name: value for name, value in os.environ.items()
               if not name.startswith(("GIT_", "GITHUB_", "SET_"))
               and name not in ("CLAUDE_CROWD", "BASE_SHA", "SECRETS_SET", "VALUES_RESULT")}
    environ.update(extra)
    return environ


def git(cwd, *args):
    done = subprocess.run(["git", "-C", str(cwd), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                           "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main"] + list(args),
                          capture_output=True, text=True, env=clean_environment())
    if done.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {done.stderr}")
    return done.stdout.strip()


def commit(work, contents, message):
    for path, text in contents.items():
        (work / path).parent.mkdir(parents=True, exist_ok=True)
        (work / path).write_text(text, encoding="utf-8")
    git(work, "add", "-A")
    git(work, "commit", "--quiet", "-m", message)
    return git(work, "rev-parse", "HEAD")


class GuardCommand(unittest.TestCase):
    """The guard reads the default branch from git: a pull request's base,
    fetched one commit deep into a checkout that holds only its own commit,
    as actions/checkout leaves it, or the default branch on a push."""

    def setUp(self):
        self.folder = Path(tempfile.mkdtemp(prefix="crowd-guard-"))
        work = self.folder / "work"
        work.mkdir()
        git(work, "init", "--quiet")
        self.base = commit(work, files("on"), "crowd mode on")
        git(work, "switch", "--quiet", "-c", "notes")
        self.notes = commit(work, {crowd_check.SESSION: "a committed checkpoint\n"}, "commit a checkpoint")
        git(work, "switch", "--quiet", "main")
        git(work, "switch", "--quiet", "-c", "code")
        self.code = commit(work, {"src/thing.py": "print('hello')\n"}, "some code")
        self.origin = self.folder / "origin.git"
        git(self.folder, "clone", "--quiet", "--bare", str(work), str(self.origin))
        git(self.origin, "config", "uploadpack.allowAnySHA1InWant", "true")

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def checkout(self, branch):
        clone = self.folder / ("clone-" + branch)
        git(self.folder, "clone", "--quiet", "--depth=1", "--branch", branch, self.origin.as_uri(), str(clone))
        return clone

    def guard(self, clone, **environ):
        environ.setdefault("VALUES_RESULT", "success")
        return subprocess.run([sys.executable, str(TOOL), "guard"], cwd=clone, capture_output=True, text=True,
                              env=clean_environment(GITHUB_REPOSITORY=REPO, **environ))

    def test_a_pull_request_that_commits_a_checkpoint_fails_on_the_fetched_base(self):
        clone = self.checkout("notes")
        self.assertNotEqual(subprocess.run(["git", "-C", str(clone), "cat-file", "-e", self.base + "^{commit}"],
                                           capture_output=True, env=clean_environment()).returncode, 0)
        done = self.guard(clone, GITHUB_EVENT_NAME="pull_request", BASE_SHA=self.base, CLAUDE_CROWD="true")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn(f"this pull request changes {crowd_check.SESSION}", done.stderr)

    def test_a_pull_request_of_code_passes_and_says_crowd_mode_is_on(self):
        done = self.guard(self.checkout("code"), GITHUB_EVENT_NAME="pull_request", BASE_SHA=self.base,
                          CLAUDE_CROWD="true", SET_CLAUDE_TEAM="false")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(done.stdout.startswith("crowd: on"), done.stdout)

    def test_a_secret_reaching_the_repository_fails_without_its_value(self):
        done = self.guard(self.checkout("code"), GITHUB_EVENT_NAME="pull_request", BASE_SHA=self.base,
                          CLAUDE_CROWD="true", SECRETS_SET="CLAUDE_CODE_OAUTH_TOKEN")
        self.assertEqual(done.returncode, 1)
        self.assertIn("the secret CLAUDE_CODE_OAUTH_TOKEN reaches this repository", done.stderr)

    def test_a_push_to_another_branch_reads_the_default_branch(self):
        done = self.guard(self.checkout("code"), GITHUB_EVENT_NAME="push", GITHUB_REF_NAME="code",
                          DEFAULT_BRANCH="main", CLAUDE_CROWD="")
        self.assertEqual(done.returncode, 1)
        self.assertIn("the Claude workflows' gate is off", done.stderr)

    def test_a_pull_request_without_its_base_is_refused_not_passed(self):
        done = self.guard(self.checkout("code"), GITHUB_EVENT_NAME="pull_request", BASE_SHA="", CLAUDE_CROWD="true")
        self.assertEqual(done.returncode, 1)
        self.assertIn("BASE_SHA", done.stderr)

    @unittest.skipUnless((ROOT / ".git").exists(), "the guard reads HEAD, and this tree has no git")
    def test_the_template_itself_is_off_and_passes(self):
        done = subprocess.run([sys.executable, str(TOOL), "guard"], cwd=ROOT, capture_output=True, text=True,
                              env=clean_environment(GITHUB_EVENT_NAME="push", SECRETS_SET="SDLC_APP_PRIVATE_KEY",
                                                    VALUES_RESULT="success"))
        if crowd_check.mode_of((ROOT / crowd_check.PROJECT).read_text(encoding="utf-8")) == "off":
            self.assertEqual((done.returncode, done.stdout.strip()), (0, "crowd: off"), done.stderr)


def event(action, sender="writer1", labels=("todo",), label=None, changes=None, sender_type="User"):
    found = {"action": action, "issue": {"number": 12, "labels": [{"name": name} for name in labels]},
             "sender": {"login": sender, "type": sender_type}, "repository": {"default_branch": "main"}}
    if label:
        found["label"] = {"name": label}
    if changes is not None:
        found["changes"] = changes
    return found


class QueueActions(unittest.TestCase):
    def test_a_queue_label_from_anyone_who_may_not_queue_is_taken_off(self):
        for label in crowd_check.QUEUE_LABELS:
            for role in ("write", "triage", "read", None):
                action = crowd_check.queue_actions(event("labeled", labels=(label,), label=label), role)
                self.assertEqual(action, crowd_check.QueueAction((label,), True, True), (label, role))

    def test_a_maintainer_or_an_admin_queues(self):
        for role in crowd_check.MAINTAINER_ROLES:
            for queued in (event("labeled", label="todo"), event("opened"), event("edited", changes={"body": {}})):
                self.assertEqual(crowd_check.queue_actions(queued, role), crowd_check.NOTHING, role)

    def test_any_other_label_is_left_alone(self):
        self.assertEqual(crowd_check.queue_actions(event("labeled", labels=("todo", "bug"), label="bug"), "write"),
                         crowd_check.NOTHING)

    def test_a_writers_edit_of_a_queued_issue_takes_both_labels_off(self):
        for field in crowd_check.EDITED_FIELDS:
            action = crowd_check.queue_actions(event("edited", labels=("blocker", "bug", "todo"),
                                                     changes={field: {"from": "x"}}), "write")
            self.assertEqual(action.remove, ("todo", "blocker"), field)

    def test_an_edit_that_changes_neither_title_nor_body_is_left_alone(self):
        self.assertEqual(crowd_check.queue_actions(event("edited", changes={}), "write"), crowd_check.NOTHING)

    def test_an_issue_a_writer_opens_with_todo_loses_it(self):
        self.assertEqual(crowd_check.queue_actions(event("opened"), "write").remove, ("todo",))
        self.assertEqual(crowd_check.queue_actions(event("opened", labels=()), "write"), crowd_check.NOTHING)

    def test_the_comment_is_not_repeated(self):
        action = crowd_check.queue_actions(event("labeled", label="todo"), "write", commented=True)
        self.assertEqual(action, crowd_check.QueueAction(("todo",), False, True))


class QueueCommand(unittest.TestCase):
    """The queue gate on the fake gh: the calls and their order."""

    def run_queue(self, queued, routes):
        folder = tempfile.mkdtemp(prefix="crowd-queue-")
        try:
            path = Path(folder) / "event.json"
            path.write_text(json.dumps(queued), encoding="utf-8")
            environ = clean_environment(**fake_gh.environment(folder, routes))
            environ.update(GITHUB_EVENT_PATH=str(path), GITHUB_REPOSITORY=REPO, DEFAULT_BRANCH="main")
            done = subprocess.run([sys.executable, str(TOOL), "queue"], capture_output=True, text=True, env=environ)
            return done, fake_gh.calls(environ["FAKE_GH_LOG"])
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    def routes(self, role, comments=()):
        return {
            f"GET {API}/collaborators/writer1/permission": [answer(200, {"role_name": role})],
            f"GET {API}/issues/12/comments?per_page=100": [answer(200, list(comments))],
            f"DELETE {API}/issues/12/labels/todo": [answer(200, [])],
            f"DELETE {API}/issues/12/labels/blocker": [answer(404, {"message": "Label does not exist"})],
            f"POST {API}/issues/12/comments": [answer(201, {"id": 1})],
            f"POST {API}/actions/workflows/board.yml/dispatches": [answer(204)],
        }

    def test_a_writers_todo_is_taken_off_with_a_comment_and_the_board_started(self):
        done, calls = self.run_queue(event("labeled", label="todo"), self.routes("write"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual([call["key"] for call in calls], [
            f"GET {API}/collaborators/writer1/permission",
            f"GET {API}/issues/12/comments?per_page=100",
            f"DELETE {API}/issues/12/labels/todo",
            f"POST {API}/issues/12/comments",
            f"POST {API}/actions/workflows/board.yml/dispatches",
        ])
        comment = calls[3]["body"]["body"]
        self.assertTrue(comment.startswith(crowd_check.QUEUE_MARKER))
        self.assertIn("@writer1's change took todo off", comment)
        self.assertEqual(calls[4]["body"], {"ref": "main"})

    def test_a_maintainers_todo_is_left_after_one_read(self):
        done, calls = self.run_queue(event("labeled", label="todo"), self.routes("maintain"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual([call["key"] for call in calls], [f"GET {API}/collaborators/writer1/permission"])

    def test_a_bot_has_no_role_and_a_label_already_gone_is_no_failure(self):
        queued = event("edited", sender="claude[bot]", sender_type="Bot", labels=("todo", "blocker"),
                       changes={"title": {"from": "x"}})
        done, calls = self.run_queue(queued, self.routes("write"))
        self.assertEqual(done.returncode, 0, done.stderr)
        keys = [call["key"] for call in calls]
        self.assertNotIn(f"GET {API}/collaborators/writer1/permission", keys)
        self.assertIn(f"DELETE {API}/issues/12/labels/blocker", keys)

    def test_the_comment_is_posted_once_per_issue(self):
        earlier = {"body": crowd_check.QUEUE_MARKER + "\nearlier", "user": {"login": crowd_check.ACTIONS_BOT}}
        done, calls = self.run_queue(event("labeled", label="todo"), self.routes("write", [earlier]))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn(f"POST {API}/issues/12/comments", [call["key"] for call in calls])

    def test_a_marker_someone_else_wrote_does_not_silence_it(self):
        forged = {"body": crowd_check.QUEUE_MARKER, "user": {"login": "writer1"}}
        _, calls = self.run_queue(event("labeled", label="todo"), self.routes("write", [forged]))
        self.assertIn(f"POST {API}/issues/12/comments", [call["key"] for call in calls])

    def test_a_refused_call_fails_the_run(self):
        routes = self.routes("write")
        routes[f"DELETE {API}/issues/12/labels/todo"] = [answer(403, {"message": "Resource not accessible"})]
        done, _ = self.run_queue(event("labeled", label="todo"), routes)
        self.assertEqual(done.returncode, 1)
        self.assertIn("HTTP 403", done.stderr)


class ModeLine(unittest.TestCase):
    def test_docs_project_md_has_one_mode_line_and_the_template_says_off(self):
        text = (ROOT / crowd_check.PROJECT).read_text(encoding="utf-8")
        self.assertEqual(len(crowd_check.MODE_LINE.findall(text)), 1)
        if IN_TEMPLATE:
            self.assertEqual(crowd_check.mode_of(text), "off")

    def test_the_off_line_is_one_line_scripts_crowd_py_can_replace_whole(self):
        text = (ROOT / crowd_check.PROJECT).read_text(encoding="utf-8")
        if crowd_check.mode_of(text) != "off":
            self.skipTest("crowd mode is on here; its block has the decisions as sub-items")
        line = next(line for line in text.splitlines() if crowd_check.MODE_LINE.match(line))
        following = text.split(line, 1)[1].split("\n", 2)
        self.assertEqual(following[0], "")
        self.assertFalse(following[1].startswith("  "), "the mode line has sub-items")


class Source(unittest.TestCase):
    def test_carries_no_placeholder_and_parses_on_python_3_8(self):
        markers = [template_init.placeholder(name) for name in template_init.PLACEHOLDER_NAMES]
        for path in (TOOL, Path(__file__), WORKFLOWS / "queue.yml"):
            text = path.read_text(encoding="utf-8")
            for marker in markers:
                self.assertNotIn(marker, text, path.name)
        ast.parse(TOOL.read_text(encoding="utf-8"), feature_version=(3, 8))
        ast.parse((ROOT / "tools" / "marked_section.py").read_text(encoding="utf-8"), feature_version=(3, 8))

    def test_a_usage_error_exits_2(self):
        done = subprocess.run([sys.executable, str(TOOL), "nothing"], capture_output=True, text=True,
                              env=clean_environment())
        self.assertEqual(done.returncode, 2)


if __name__ == "__main__":
    unittest.main()
