"""tools/protocol_update.py and .github/workflows/protocol.yml, which bring
each new release of the claim protocol into a repository made from the
template.

What the workflow decides is the script's, so it is tested here, on a real
git repository for the library's tags: the newest release tag by version,
never a tag of another shape; an update only when that tag is newer than
the version tools/VENDORED records, never back to an older one; and every
text the workflow posts. The workflow's own shape is held too: when it
runs and where it never does, a token of its own and no secret, the branch
it alone pushes and only when the branch lacks the copy, the check it asks
for on that branch, which ci.yml must answer, auto-merge armed and never a
merge, the issue where Actions may open no pull request, and the update
closed once the default branch carries the release."""

import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import protocol_update  # noqa: E402

WORKFLOWS = ROOT / ".github" / "workflows"
COMMIT = "7ebffdc0b2defb65af117ef22d6ade9934839db7"
LIBRARY_URL = "https://github.com/OpenSpineConsortium/symphony-protocol"


def record(version, commit=COMMIT):
    """A VENDORED text for a copy of version at commit, of one file."""
    return f"sdlc-protocol {version} {commit}\n{'0' * 64}  __init__.py\n"


def quiet_environment():
    """This environment without git's own variables, which a hook or an
    outer git might have set and which would point git elsewhere."""
    return {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}


class Releases(unittest.TestCase):
    def test_the_newest_release_is_chosen_by_version_not_by_name(self):
        self.assertEqual(protocol_update.newest_release(
            ["v0.2.0", "v0.10.0", "v0.9.1", "latest", "v1.0", "0.11.0", "v0.12.0-rc1"]), "v0.10.0")

    def test_no_release_tag_is_none(self):
        self.assertIsNone(protocol_update.newest_release(["latest", "1.0.0"]))
        self.assertIsNone(protocol_update.newest_release([]))

    def test_only_a_newer_release_is_taken(self):
        self.assertTrue(protocol_update.is_newer("v0.3.1", "0.3.0"))
        self.assertTrue(protocol_update.is_newer("v0.10.0", "0.9.0"))
        self.assertFalse(protocol_update.is_newer("v0.3.0", "0.3.0"))
        # A copy vendored from the library's main, ahead of every release,
        # is never taken back to one.
        self.assertFalse(protocol_update.is_newer("v0.2.0", "0.3.0"))


class Plan(unittest.TestCase):
    """The plan against a library with release tags and a copy's record,
    both removed after each test."""

    def setUp(self):
        environment = mock.patch.dict(os.environ, quiet_environment(), clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        self.folder = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.library = self.folder / "symphony-protocol"
        self.library.mkdir()
        self.git("init", "-q")
        (self.library / "README.md").write_text("the library\n", encoding="ascii")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "the library")
        self.record = self.folder / "VENDORED"

    def git(self, *args):
        done = subprocess.run(["git", "-c", "user.name=plan test", "-c", "user.email=plan@example.invalid",
                               "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false",
                               "-c", "init.defaultBranch=main", *args],
                              cwd=self.library, capture_output=True, text=True, timeout=60)
        if done.returncode != 0:
            raise AssertionError(f"git {' '.join(args)}: {done.stderr}")
        return done.stdout

    def tag(self, *names):
        for name in names:
            self.git("tag", name)

    def plan(self, recorded):
        self.record.write_text(record(recorded), encoding="ascii")
        return protocol_update.plan(self.library, self.record)

    def test_a_newer_release_is_needed(self):
        self.tag("v0.2.0", "v0.3.0", "v0.3.1")
        self.assertEqual(self.plan("0.3.0"), {"needed": "true", "tag": "v0.3.1", "recorded": "0.3.0",
                                              "recorded_commit": COMMIT})

    def test_a_copy_at_the_newest_release_needs_nothing(self):
        self.tag("v0.3.0", "v0.3.1")
        self.assertEqual(self.plan("0.3.1")["needed"], "false")

    def test_a_library_with_no_release_needs_nothing(self):
        self.assertEqual(self.plan("0.3.0"), {"needed": "false", "tag": "", "recorded": "0.3.0",
                                              "recorded_commit": COMMIT})

    def test_the_command_line_prints_the_steps_outputs(self):
        self.tag("v0.3.1")
        self.record.write_text(record("0.3.0"), encoding="ascii")
        out = io.StringIO()
        with mock.patch.object(protocol_update, "RECORD", self.record), redirect_stdout(out):
            self.assertEqual(protocol_update.main(["plan", "--library", str(self.library)]), 0)
        self.assertEqual(out.getvalue(), f"needed=true\ntag=v0.3.1\nrecorded=0.3.0\nrecorded_commit={COMMIT}\n")

    def test_this_repositorys_own_record_reads(self):
        recorded, commit, _ = protocol_update.vendoring.parse_record(
            protocol_update.RECORD.read_text(encoding="ascii"))
        self.assertIsNotNone(protocol_update.version_of("v" + recorded))
        self.assertRegex(commit, r"^[0-9a-f]{40}$")


class Texts(unittest.TestCase):
    def test_the_title_and_the_commit_message(self):
        self.assertEqual(protocol_update.title("v0.3.1"), "Bring in symphony-protocol 0.3.1")
        message = protocol_update.message("v0.3.1")
        self.assertTrue(message.startswith("Bring in symphony-protocol 0.3.1\n\n"))
        for words in ("v0.3.1", "tools/VENDORED", "scripts/vendor.py", ".github/workflows/protocol.yml"):
            self.assertIn(words, message)

    def test_the_body_links_the_release_and_every_change_since_the_copy(self):
        body = protocol_update.body("v0.3.1", "0.3.0", COMMIT)
        self.assertTrue(body.startswith(protocol_update.MARKER + "\n"))
        self.assertIn("from symphony-protocol 0.3.0 to 0.3.1", body)
        self.assertIn(f"({LIBRARY_URL}/releases/tag/v0.3.1)", body)
        self.assertIn(f"({LIBRARY_URL}/compare/{COMMIT}...v0.3.1)", body)
        self.assertIn("This repository's check decides", body)

    def test_the_issue_gives_the_link_that_opens_the_pull_request(self):
        url = "https://github.com/octo/widgets/compare/main...symphony-protocol/sync?expand=1"
        issue = protocol_update.issue_body("v0.3.1", "0.3.0", url)
        self.assertTrue(issue.startswith(protocol_update.MARKER + "\n"))
        self.assertIn(f"[open the pull request]({url})", issue)
        self.assertIn("The branch symphony-protocol/sync holds", issue)
        self.assertEqual(protocol_update.issue_title("v0.3.1"), "symphony-protocol 0.3.1 is ready to bring in")

    def test_the_closing_comment_names_the_release_the_default_branch_carries(self):
        self.assertIn("symphony-protocol 0.3.1, no older than the newest release", protocol_update.closing("0.3.1"))

    def test_every_text_is_ascii(self):
        for text in (protocol_update.message("v0.3.1"), protocol_update.body("v0.3.1", "0.3.0", COMMIT),
                     protocol_update.issue_body("v0.3.1", "0.3.0", "https://example.invalid"),
                     protocol_update.closing("0.3.1"), protocol_update.MARKER):
            text.encode("ascii")

    def test_a_text_without_what_it_needs_says_which_options_are_missing(self):
        err = io.StringIO()
        with redirect_stderr(err), self.assertRaises(SystemExit) as stopped:
            protocol_update.main(["body", "--tag", "v0.3.1"])
        self.assertEqual(stopped.exception.code, 2)
        self.assertIn("body needs --recorded, --from", err.getvalue())

    def test_the_command_line_prints_each_text(self):
        out = io.StringIO()
        with redirect_stdout(out):
            protocol_update.main(["marker"])
            protocol_update.main(["title", "--tag", "v0.3.1"])
        self.assertEqual(out.getvalue(), protocol_update.MARKER + "\nBring in symphony-protocol 0.3.1\n")


def workflow(name):
    return (WORKFLOWS / name).read_text(encoding="ascii")


def code_lines(text):
    """The lines that are not comments, YAML's or the shell's."""
    return [line for line in text.splitlines() if not line.lstrip().startswith("#")]


def shell_steps(text):
    """The text of each run: step, the key's line with the block under it."""
    lines, steps = text.splitlines(), []
    for number, line in enumerate(lines):
        key = re.match(r"^(\s*)(?:- )?run:", line)
        if not key:
            continue
        indent, block = len(key.group(1)), [line]
        for follower in lines[number + 1:]:
            if follower.strip() and len(follower) - len(follower.lstrip()) <= indent:
                break
            block.append(follower)
        steps.append("\n".join(block))
    return steps


def shell_script(step):
    key, *block = step.splitlines()
    inline = key.split("run:", 1)[1].strip()
    return textwrap.dedent("\n".join(block)) if inline.startswith("|") else inline


def step_named(text, name):
    """The lines of the step with that name, up to the next step."""
    start = text.index(f"- name: {name}")
    end = text.find("\n      - ", start + 1)
    return text[start:] if end < 0 else text[start:end]


class Workflow(unittest.TestCase):
    def setUp(self):
        self.text = workflow("protocol.yml")

    def test_runs_weekly_off_the_hour_and_by_hand(self):
        minute = re.search(r'- cron: "(\d+) ', self.text).group(1)
        self.assertNotEqual(minute, "0")
        self.assertIn("\n  workflow_dispatch:\n", self.text)

    def test_never_in_the_template_itself_nor_in_a_fork(self):
        self.assertIn("    if: github.event.repository.is_template == false && github.event.repository.fork == false\n",
                      self.text)
        self.assertIn("if [ -e .template/PENDING ]; then", self.text)

    def test_its_own_token_with_what_it_writes_and_no_secret(self):
        self.assertIn("permissions:\n  contents: write\n  pull-requests: write\n  issues: write\n  actions: write\n\n",
                      self.text)
        self.assertIn("GH_TOKEN: ${{ github.token }}", self.text)
        self.assertNotIn("secrets.", self.text)

    def test_only_the_steps_that_call_github_hold_the_token(self):
        """The library's scripts/vendor.py, cloned from another repository,
        runs in a step that holds no token."""
        job_env = self.text.split("\n    env:\n", 1)[1].split("\n    steps:\n", 1)[0]
        self.assertNotIn("GH_TOKEN", job_env)
        self.assertNotIn("GH_TOKEN", step_named(self.text, "Vendor the newest release"))
        for name in ("Close the update still open", "Push it to the branch", "Open or update the pull request"):
            self.assertIn("GH_TOKEN: ${{ github.token }}", step_named(self.text, name), name)

    def test_one_run_at_a_time_and_a_newer_one_waits(self):
        self.assertIn("concurrency:\n  group: protocol\n  cancel-in-progress: false\n", self.text)

    def test_vendors_the_tag_with_the_librarys_own_script_as_the_template_takes_it(self):
        self.assertIn('git -C "$library" checkout --quiet "$TAG"', self.text)
        self.assertIn('python3 "$library/scripts/vendor.py" . --consumer OpenSpineConsortium/symphony-template',
                      self.text)
        self.assertIn("git clone --quiet https://github.com/OpenSpineConsortium/symphony-protocol", self.text)

    def test_pushes_only_its_own_branch_and_only_a_copy_the_branch_lacks(self):
        pushes = [line.strip() for line in code_lines(self.text) if " push " in line]
        self.assertEqual(pushes, ['git -c http.extraheader="AUTHORIZATION: basic $basic" push --quiet --force '
                                  'origin "HEAD:refs/heads/$BRANCH"'])
        self.assertIn(f"BRANCH: {protocol_update.BRANCH}\n", self.text)
        self.assertLess(self.text.index("if already_pushed; then"), self.text.index("push --quiet --force"))
        self.assertIn("""[ "$(git rev-parse 'FETCH_HEAD^{tree}')" = "$(git rev-parse 'HEAD^{tree}')" ]""", self.text)
        self.assertIn("""[ "$(git rev-parse 'FETCH_HEAD^')" = "$(git rev-parse 'HEAD^')" ]""", self.text)

    def test_takes_as_its_own_only_a_pull_request_from_this_repository(self):
        """gh's --head matches the branch's name in any repository, so a
        fork's pull request from a branch of the same name is listed too."""
        listings = [line for line in code_lines(self.text) if "gh pr list" in line]
        self.assertEqual(len(listings), 2)
        self.assertEqual(self.text.count("--jq '[.[] | select(.isCrossRepository | not)][0].url // \"\"'"), 2)

    def test_asks_for_the_check_on_the_branch_and_ci_answers(self):
        self.assertIn('gh workflow run ci.yml --repo "$REPO" --ref "$BRANCH"', self.text)
        self.assertIn("\n  workflow_dispatch:\n", workflow("ci.yml"))

    def test_arms_auto_merge_and_never_merges(self):
        """gh pr merge --auto merges at once a pull request GitHub does not
        count as blocked; the mutation only arms auto-merge, by a merge
        commit."""
        self.assertEqual([line for line in code_lines(self.text) if "gh pr merge" in line], [])
        self.assertIn("enablePullRequestAutoMerge(input: {pullRequestId: $id, mergeMethod: MERGE})", self.text)
        offer = step_named(self.text, "Open or update the pull request")
        self.assertLess(offer.index(".autoMergeRequest != null"), offer.index("enablePullRequestAutoMerge"))

    def test_where_actions_may_open_no_pull_request_its_own_issue_says_so(self):
        offer = step_named(self.text, "Open or update the pull request")
        self.assertIn('compare="https://github.com/$REPO/compare/$DEFAULT_BRANCH...$BRANCH?expand=1"', offer)
        self.assertIn("contains(env.MARKER)", offer)
        self.assertIn('gh issue edit "$number"', offer)
        self.assertIn("gh issue create", offer)

    def test_closes_the_update_once_the_default_branch_carries_the_release(self):
        close = step_named(self.text, "Close the update still open")
        self.assertIn("if: steps.plan.outputs.needed == 'false'", close)
        self.assertIn('gh pr close "$url" --comment', close)
        self.assertIn('gh issue close "$number"', close)
        self.assertIn("contains(env.MARKER)", close)

    def test_no_expression_inside_a_shell_step_and_every_one_parses(self):
        for step in shell_steps(self.text):
            with self.subTest(step=step.splitlines()[0]):
                self.assertNotIn("${{", step)
                done = subprocess.run(["bash", "-n"], input=shell_script(step), capture_output=True, text=True,
                                      timeout=30)
                self.assertEqual(done.returncode, 0, done.stderr)

    def test_reads_its_lists_on_their_own_descriptor_never_a_heredoc_under_a_pipe(self):
        self.assertNotIn("<<", self.text)
        self.assertIn('while read -r number <&3; do', self.text)


if __name__ == "__main__":
    unittest.main()
