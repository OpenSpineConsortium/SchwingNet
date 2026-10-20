"""scripts/setup-repo.sh parses, documents every option, reads the labels
from tools/template_init.py so the list lives in one place, carries every
gh call the owner's checklist relies on, and turns on the setting that
lets GitHub Actions open pull requests, keeping the token's default
permissions, or says why it could not and goes on;
docs/setup/ruleset-org.json holds the same rules as ruleset-main.json, so
the two cannot drift apart; and every ruleset the template ships targets
the default branch alone, so none can stand in the way of a branch the
workflows rewrite. The real gh is not run here: the script needs a
signed-in CLI with admin rights, which no test has, so a fake gh on PATH
(tests/fake_gh.py) answers the script's calls and records them."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fake_gh  # noqa: E402
from fake_gh import answer  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "setup-repo.sh"
MAIN = ROOT / "docs" / "setup" / "ruleset-main.json"
ORG = ROOT / "docs" / "setup" / "ruleset-org.json"
# The gh calls the research notes verified against gh 2.89.0 and the REST
# description, one piece each; those of the workflow permissions were
# checked against the same two on 2026-10-13.
GH_CALLS = (
    "rulesets", "--input", "repo edit", "--delete-branch-on-merge", "--enable-auto-merge", "--add-topic symphony",
    "--enable-secret-scanning", "--enable-secret-scanning-push-protection",
    "actions/permissions/workflow", "--method PUT", "default_workflow_permissions=",
    "-F can_approve_pull_request_reviews=true",
    "pages", "build_type=workflow",
    "label create", "variable set", "secret set", "codeowners/errors",
)
REPO = "octo/widgets"
WORKFLOW = f"repos/{REPO}/actions/permissions/workflow"
STORE = f"repos/{REPO}/environments/token-store"
PAGES = f"repos/{REPO}/pages"
SETTING = "workflow permissions: allow GitHub Actions to create and approve pull requests"
# What the script reads from the tree it runs in, copied to a tree of the
# test's own whose docs/project.md says crowd mode is off: a crowd
# repository's own says on, and there the script stops before any write.
TREE = ("scripts/setup-repo.sh", "tools/template_init.py", "tools/marked_section.py", "docs/setup/ruleset-main.json")
CROWD_OFF = "# Project\n\n## Crowd mode\n\n- Crowd mode: off. Nobody has run setup.\n"


def run(*args):
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, cwd=ROOT)


class Script(unittest.TestCase):
    def test_bash_parses_it(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True, cwd=ROOT)

    def test_help_exits_0_and_names_every_option(self):
        done = run("--help")
        self.assertEqual(done.returncode, 0, done.stderr)
        for option in ("OWNER/NAME", "--var NAME=VALUE", "--token", "--help"):
            self.assertIn(option, done.stdout)

    def test_an_unknown_option_exits_2_before_any_gh_call(self):
        self.assertEqual(run("--nope").returncode, 2)
        self.assertEqual(run("--var", "not a pair").returncode, 2)

    def test_the_labels_come_from_template_init_and_nowhere_else(self):
        text = SCRIPT.read_text()
        self.assertIn("template_init", text)
        self.assertIn("LABELS", text)
        self.assertNotIn("account:main", text)

    def test_every_verified_gh_call_is_there(self):
        text = SCRIPT.read_text()
        for piece in GH_CALLS:
            self.assertIn(piece, text)

    def test_the_token_never_goes_on_a_command_line(self):
        # gh secret set without --body prompts without echo, or reads stdin.
        calls = [line for line in SCRIPT.read_text().splitlines() if re.search(r"gh secret set", line)]
        self.assertTrue(calls)
        for line in calls:
            self.assertNotIn("--body", line)
            self.assertNotIn(" -b ", line)


def workflow_answer(permissions, can_approve):
    """GitHub's answer to the read, in the shape the REST description
    gives: the token's default permissions beside a JSON boolean."""
    return answer(200, {"default_workflow_permissions": permissions, "can_approve_pull_request_reviews": can_approve})


def fields(call):
    """The -f and -F pairs of one gh api call, as gh would send them."""
    args, found = call["args"], {}
    for flag, pair in zip(args, args[1:]):
        if flag in ("-f", "-F"):
            name, _, value = pair.partition("=")
            found[name] = (flag, value)
    return found


class TokenStore(unittest.TestCase):
    """The environment token-store, limited to the default branch, so a
    workflow pushed to another branch never runs the Token workflow's job
    that holds the App's token; one the repository has already is left as
    it is, and a refusal names the page and stops nothing."""

    def run_script(self, extra):
        runner = WorkflowPermissions()
        runner.addCleanup = self.addCleanup
        return runner.run_script(workflow_answer("read", True), extra=extra)

    def store_line(self, done):
        found = [line for line in done.stdout.splitlines() if line.startswith("environment token-store:")]
        self.assertEqual(len(found), 1, done.stdout)
        return found[0]

    def test_makes_it_for_the_default_branch_alone(self):
        done, calls = self.run_script({})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.store_line(done), "environment token-store: made, main only")
        put = next(call for call in calls if call["key"] == f"PUT {STORE}")
        self.assertEqual(fields(put), {"deployment_branch_policy[protected_branches]": ("-F", "false"),
                                       "deployment_branch_policy[custom_branch_policies]": ("-F", "true")})
        rule = next(call for call in calls if call["key"] == f"POST {STORE}/deployment-branch-policies")
        self.assertEqual(fields(rule), {"name": ("-f", "main"), "type": ("-f", "branch")})

    def test_leaves_one_there_already_alone(self):
        done, calls = self.run_script({f"GET {STORE}": [answer(200, "")]})
        self.assertEqual(self.store_line(done), "environment token-store: exists, left as it is")
        self.assertNotIn(f"PUT {STORE}", [call["key"] for call in calls])

    def test_a_refusal_names_the_page_and_goes_on(self):
        done, calls = self.run_script({f"PUT {STORE}": [answer(403, {"message": "Forbidden"})]})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn(f"https://github.com/{REPO}/settings/environments/new", self.store_line(done))
        self.assertNotIn(f"POST {STORE}/deployment-branch-policies", [call["key"] for call in calls])
        self.assertIn("label create", [call["key"] for call in calls])

    def test_a_refused_branch_rule_says_the_environment_stands_closed(self):
        done, _ = self.run_script({f"POST {STORE}/deployment-branch-policies": [answer(422, {"message": "x"})]})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("made with no branch allowed", self.store_line(done))

    def test_a_refused_read_writes_nothing(self):
        done, calls = self.run_script({f"GET {STORE}": [answer(403, {"message": "Forbidden"})]})
        self.assertIn("not made", self.store_line(done))
        self.assertNotIn(f"PUT {STORE}", [call["key"] for call in calls])


class Pages(unittest.TestCase):
    """GitHub Pages built by GitHub Actions and the variable SYMPHONY_DOCS,
    so docs.yml publishes the documentation site with no click; a site
    there already is left as it is, a non-public repository's site is
    limited to its readers or removed, and a refusal stops nothing."""

    def run_script(self, extra, visibility="PUBLIC"):
        extra = dict(extra)
        extra.setdefault("repo view", [answer(200, f"{REPO}\tmain\t{visibility}\n")])
        return TokenStore.run_script(self, extra)

    def pages_line(self, done):
        found = [line for line in done.stdout.splitlines() if line.startswith("pages:")]
        self.assertEqual(len(found), 1, done.stdout)
        return found[0]

    def keys(self, calls):
        return [call["key"] for call in calls]

    def test_turns_it_on_built_by_actions_and_sets_the_variable(self):
        done, calls = self.run_script({})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("pages: turned on, built by GitHub Actions", self.pages_line(done))
        made = next(call for call in calls if call["key"] == f"POST {PAGES}")
        self.assertEqual(fields(made), {"build_type": ("-f", "workflow")})
        self.assertNotIn(f"PUT {PAGES}", self.keys(calls))
        variable = next(call for call in calls if call["key"] == "variable set")
        self.assertEqual(variable["args"][:3], ["variable", "set", "SYMPHONY_DOCS"])
        self.assertIn("pages", variable["args"])

    def test_a_site_there_already_is_left_as_it_is_with_no_variable(self):
        done, calls = self.run_script({f"GET {PAGES}": [answer(200, "")]})
        self.assertIn("left as it is", self.pages_line(done))
        self.assertNotIn(f"POST {PAGES}", self.keys(calls))
        self.assertNotIn("variable set", self.keys(calls))

    def test_a_site_published_already_is_left_alone_whatever_builds_it(self):
        """A site that has been built may be the owner's own, so the
        variable that would let docs.yml deploy over it stays unset."""
        for site in ("workflow built", "legacy never"):
            with self.subTest(site=site):
                done, calls = self.run_script({f"GET {PAGES}": [answer(200, f"{site}\n")]})
                self.assertIn("left as it is", self.pages_line(done))
                self.assertNotIn("variable set", self.keys(calls))

    def test_a_site_from_actions_never_published_takes_the_variable(self):
        """An earlier run made the site before it could set the variable;
        nothing has deployed there since, so this run sets it."""
        done, calls = self.run_script({f"GET {PAGES}": [answer(200, "workflow never\n")]})
        self.assertIn("never published, so the variable SYMPHONY_DOCS is set to pages", self.pages_line(done))
        self.assertNotIn(f"POST {PAGES}", self.keys(calls))
        variable = next(call for call in calls if call["key"] == "variable set")
        self.assertEqual(variable["args"][:3], ["variable", "set", "SYMPHONY_DOCS"])

    def limiting(self, public):
        """The PUT that limits the site, after which the read back says
        public as given."""
        return {f"PUT {PAGES}": [answer(204, "", after={f"GET {PAGES}": [answer(200, f"{public}\n")]})]}

    def test_an_internal_repositorys_site_is_limited_to_its_readers(self):
        done, calls = self.run_script(self.limiting("false"), visibility="INTERNAL")
        self.assertIn("turned on", self.pages_line(done))
        limited = next(call for call in calls if call["key"] == f"PUT {PAGES}")
        self.assertEqual(fields(limited), {"public": ("-F", "false")})
        self.assertIn("variable set", self.keys(calls))

    def test_a_limit_github_took_but_did_not_keep_removes_the_site(self):
        done, calls = self.run_script(self.limiting("true"), visibility="PRIVATE")
        self.assertIn("still reads as public", self.pages_line(done))
        self.assertIn("removed again", self.pages_line(done))
        self.assertIn(f"DELETE {PAGES}", self.keys(calls))
        self.assertNotIn("variable set", self.keys(calls))

    def test_a_site_that_could_not_be_removed_says_so(self):
        done, calls = self.run_script({f"PUT {PAGES}": [answer(422, {"message": "plan"})],
                                       f"DELETE {PAGES}": [answer(500, {"message": "oops"})]}, visibility="PRIVATE")
        self.assertIn("could not be removed again", self.pages_line(done))

    def test_a_site_that_cannot_be_limited_is_removed_again(self):
        done, calls = self.run_script({f"PUT {PAGES}": [answer(422, {"message": "plan"})]}, visibility="PRIVATE")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("would be open to anyone", self.pages_line(done))
        self.assertIn(f"DELETE {PAGES}", self.keys(calls))
        self.assertNotIn("variable set", self.keys(calls))

    def test_a_refusal_names_the_page_and_goes_on(self):
        done, calls = self.run_script({f"POST {PAGES}": [answer(422, {"message": "plan"})]})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn(f"https://github.com/{REPO}/settings/pages", self.pages_line(done))
        self.assertIn("label create", self.keys(calls))

    def test_a_refused_read_writes_nothing(self):
        done, calls = self.run_script({f"GET {PAGES}": [answer(403, {"message": "Forbidden"})]})
        self.assertIn("not turned on", self.pages_line(done))
        self.assertNotIn(f"POST {PAGES}", self.keys(calls))


class AsTheApp(unittest.TestCase):
    """The Settings workflow runs the script with the SymphonyBoard App's
    token (SYMPHONY_SETTINGS_APP=1), whose installation may not have
    accepted every permission: each refusal is reported and the run goes
    on, and a crowd mode it cannot read leaves auto-merge alone."""

    def run_script(self, extra, app=True):
        runner = WorkflowPermissions()
        runner.addCleanup = self.addCleanup
        with mock.patch.dict(os.environ, {"SYMPHONY_SETTINGS_APP": "1"} if app else {}):
            return runner.run_script(workflow_answer("read", True), extra=extra)

    def keys(self, calls):
        return [call["key"] for call in calls]

    def test_an_unread_crowd_variable_goes_on_without_auto_merge(self):
        refused = {f"GET repos/{REPO}/actions/variables/CLAUDE_CROWD": [answer(403, {"message": "Forbidden"})]}
        done, calls = self.run_script(refused)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("crowd mode: unknown", done.stdout)
        edit = next(call for call in calls if call["key"] == "repo edit" and "--delete-branch-on-merge" in call["args"])
        self.assertNotIn("--enable-auto-merge", edit["args"])
        self.assertIn("label create", self.keys(calls))

    def test_the_workflows_own_read_of_the_variable_needs_no_permission(self):
        """The workflow hands the value from its vars context: empty turns
        auto-merge on without asking the API, true stops before any write."""
        refused = {f"GET repos/{REPO}/actions/variables/CLAUDE_CROWD": [answer(403, {"message": "Forbidden"})]}
        with mock.patch.dict(os.environ, {"SYMPHONY_CROWD_VARIABLE": ""}):
            done, calls = self.run_script(refused)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("crowd mode: unknown", done.stdout)
        self.assertNotIn(f"GET repos/{REPO}/actions/variables/CLAUDE_CROWD", self.keys(calls))
        edit = next(call for call in calls if call["key"] == "repo edit" and "--delete-branch-on-merge" in call["args"])
        self.assertIn("--enable-auto-merge", edit["args"])
        with mock.patch.dict(os.environ, {"SYMPHONY_CROWD_VARIABLE": "TRUE"}):
            done, calls = self.run_script({})
        self.assertNotEqual(done.returncode, 0)
        self.assertNotIn("repo edit", self.keys(calls))

    def test_a_recheck_makes_only_the_environment_and_pages(self):
        """The weekly and visibility runs make only what a plan or a
        private repository held back, and touch no toggle, topic, ruleset,
        scanning, Actions box or label the owner may have changed since."""
        with mock.patch.dict(os.environ, {"SYMPHONY_SETTINGS_RECHECK": "1", "SYMPHONY_CROWD_VARIABLE": ""}):
            done, calls = self.run_script({})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("recheck: only the environment and Pages", done.stdout)
        keys = self.keys(calls)
        for untouched in ("repo edit", "label create", f"GET repos/{REPO}/rulesets", f"PATCH repos/{REPO}"):
            self.assertNotIn(untouched, keys)
        self.assertTrue([key for key in keys if "environments" in key], keys)
        self.assertIn(f"POST repos/{REPO}/pages", keys)

    def test_a_recheck_leaves_pages_alone_once_the_variable_is_set(self):
        """SYMPHONY_DOCS set means Pages was decided, so a site the owner
        removed is not put back."""
        env = {"SYMPHONY_SETTINGS_RECHECK": "1", "SYMPHONY_CROWD_VARIABLE": "", "SYMPHONY_DOCS_VARIABLE": "pages"}
        with mock.patch.dict(os.environ, env):
            done, calls = self.run_script({})
        self.assertIn("pages: left as it is", done.stdout)
        self.assertFalse([key for key in self.keys(calls) if "/pages" in key])

    def test_a_person_who_cannot_read_it_is_still_stopped(self):
        refused = {f"GET repos/{REPO}/actions/variables/CLAUDE_CROWD": [answer(403, {"message": "Forbidden"})]}
        done, calls = self.run_script(refused, app=False)
        self.assertNotEqual(done.returncode, 0)
        self.assertNotIn("repo edit", self.keys(calls))

    def test_refused_rulesets_toggles_topic_and_labels_stop_nothing(self):
        done, calls = self.run_script({
            f"GET repos/{REPO}/rulesets": [answer(403, {"message": "Resource not accessible by integration"})],
            "repo edit": [answer(403, {"message": "Forbidden"})],
            f"PATCH repos/{REPO}": [answer(403, {"message": "Forbidden"})],
            "label create": [answer(403, {"message": "Forbidden"})],
        })
        self.assertEqual(done.returncode, 0, done.stderr)
        for said in ("ruleset \"Protect the default branch\": not created", "general: delete head branches on merge, "
                     "allow auto-merge: not changed", "topic symphony: not added", "not made"):
            self.assertIn(said, done.stdout)
        self.assertIn(f"GET repos/{REPO}/codeowners/errors", self.keys(calls))

    def test_a_refused_toggle_command_goes_through_the_rest_api(self):
        done, calls = self.run_script({"repo edit": [answer(403, {"message": "Forbidden"})],
                                       f"PATCH repos/{REPO}": [answer(200, "")]})
        self.assertIn("general: delete head branches on merge, allow auto-merge: on", done.stdout)
        self.assertIn("secret scanning: on", done.stdout)


class WorkflowPermissions(unittest.TestCase):
    """.github/workflows/protocol.yml and add-worker.yml open their pull
    requests with GITHUB_TOKEN, which GitHub allows only once "Allow GitHub
    Actions to create and approve pull requests" is on. The script turns it
    on, sends back the token's default permissions as it read them so
    nothing else changes, sends nothing when GitHub's answer does not say
    them, and reports a refusal with where to change it without stopping,
    since an organization's policy is no reason to leave the labels and the
    rest undone."""

    def run_script(self, read, write=None, owner_type=None, extra=None):
        """The whole script against the fake gh, every other call answered
        as a fresh repository would: its output and the calls it made.
        owner_type answers the read of the repository's owner, which the
        script makes only after a 409; without it that read fails."""
        folder = tempfile.mkdtemp(prefix="setup-repo-")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        root = Path(folder) / "tree"
        for path in TREE:
            (root / path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / path, root / path)
        (root / "docs" / "project.md").write_text(CROWD_OFF)
        routes = {
            "repo view": [answer(200, f"{REPO}\tmain\tPUBLIC\n")],
            f"GET repos/{REPO}/actions/variables/CLAUDE_CROWD": [answer(404, {"message": "Not Found"})],
            f"GET repos/{REPO}/rulesets": [answer(200, "")],
            f"POST repos/{REPO}/rulesets": [answer(201, "")],
            "repo edit": [answer(200, "")],
            f"GET {WORKFLOW}": [read],
            f"PUT {WORKFLOW}": [write or answer(599, {"message": "not expected"})],
            "label create": [answer(200, "")],
            f"GET repos/{REPO}/codeowners/errors": [answer(200, "")],
            f"GET {STORE}": [answer(404, {"message": "Not Found"})],
            f"PUT {STORE}": [answer(200, "")],
            f"POST {STORE}/deployment-branch-policies": [answer(200, "")],
            f"GET {PAGES}": [answer(404, {"message": "Not Found"})],
            f"POST {PAGES}": [answer(201, "")],
            f"PUT {PAGES}": [answer(204, "")],
            f"DELETE {PAGES}": [answer(204, "")],
            "variable set": [answer(200, "")],
            # Read only when a flag is unknown, so it names a gh that old.
            "--version": [answer(200, "gh version 1.14.0 (2021-08-04)\n")],
        }
        if owner_type:
            routes[f"GET repos/{REPO}"] = [answer(200, f"{owner_type}\n")]
        routes.update(extra or {})
        env = dict(os.environ, **fake_gh.environment(Path(folder) / "gh", routes))
        done = subprocess.run(["bash", str(root / "scripts" / "setup-repo.sh"), REPO], cwd=root, env=env,
                              capture_output=True, text=True)
        return done, fake_gh.calls(env["FAKE_GH_LOG"])

    def line(self, done):
        """The one line the step printed."""
        found = [line for line in done.stdout.splitlines() if line.startswith("workflow permissions:")]
        self.assertEqual(len(found), 1, done.stdout)
        return found[0]

    def assert_went_on(self, done, calls):
        """The run finished, and the labels and the code owners came after
        the step, so a refusal stopped nothing."""
        self.assertEqual(done.returncode, 0, done.stderr)
        keys = [call["key"] for call in calls]
        step = max(index for index, key in enumerate(keys) if key.endswith(WORKFLOW))
        self.assertIn("label create", keys[step:])
        self.assertIn(f"GET repos/{REPO}/codeowners/errors", keys[step:])

    def puts(self, calls):
        """The calls that wrote the setting."""
        return [call for call in calls if call["key"] == f"PUT {WORKFLOW}"]

    def test_turns_it_on_and_sends_the_default_permissions_back_as_read(self):
        # "write" here and "read" in the refusal below: whichever GitHub
        # reads goes back as it was, a string (-f), beside a JSON true (-F).
        done, calls = self.run_script(workflow_answer("write", False), answer(204))
        # The read takes GitHub's own body, unfiltered, which the fake gives
        # in the REST description's shape; a --jq filter would change what
        # the real gh prints, and the fake would not show it.
        self.assertEqual([call["args"] for call in calls if call["key"] == f"GET {WORKFLOW}"], [["api", WORKFLOW]])
        self.assertEqual([fields(call) for call in self.puts(calls)],
                         [{"default_workflow_permissions": ("-f", "write"),
                           "can_approve_pull_request_reviews": ("-F", "true")}])
        self.assertEqual(self.line(done), f"{SETTING}: on")
        self.assert_went_on(done, calls)

    def test_leaves_it_alone_when_it_is_on_already(self):
        done, calls = self.run_script(workflow_answer("read", True))
        self.assertEqual(self.puts(calls), [])
        self.assertEqual(self.line(done), f"{SETTING}: on already")
        self.assert_went_on(done, calls)

    def test_an_organizations_policy_is_reported_with_where_its_owner_changes_it(self):
        # With --silent gh keeps a refused call's body off standard output
        # and prints GitHub's answer on standard error: the line carries the
        # answer, and the body shows nowhere.
        refused = answer(409, {"message": "Conflict"}, stderr="gh: Conflict (HTTP 409)\n")
        done, calls = self.run_script(workflow_answer("read", False), refused, owner_type="Organization")
        self.assertEqual([fields(call) for call in self.puts(calls)],
                         [{"default_workflow_permissions": ("-f", "read"),
                           "can_approve_pull_request_reviews": ("-F", "true")}])
        line = self.line(done)
        self.assertIn("held off by the policy of octo or its enterprise (gh: Conflict (HTTP 409))", line)
        self.assertIn("an owner of octo turns it on under https://github.com/organizations/octo/settings/actions", line)
        self.assertIn("then run this again", line)
        self.assertNotIn('{"message"', done.stdout)
        self.assert_went_on(done, calls)

    def test_a_personal_accounts_409_names_the_repositorys_own_page_and_no_organization(self):
        # A personal account has no organization settings page, so the line
        # points at the repository's own Actions page instead.
        refused = answer(409, {"message": "Conflict"}, stderr="gh: Conflict (HTTP 409)\n")
        done, calls = self.run_script(workflow_answer("read", False), refused, owner_type="User")
        line = self.line(done)
        self.assertIn("held off by a policy above this repository (gh: Conflict (HTTP 409))", line)
        self.assertIn(f"https://github.com/{REPO}/settings/actions", line)
        self.assertNotIn("/organizations/", line)
        self.assert_went_on(done, calls)

    def test_a_409_whose_owner_cannot_be_read_names_no_organization_page(self):
        # The owner's read fails (no route), so the script cannot tell an
        # organization and names only the page every repository has.
        refused = answer(409, {"message": "Conflict"}, stderr="gh: Conflict (HTTP 409)\n")
        done, calls = self.run_script(workflow_answer("read", False), refused)
        line = self.line(done)
        self.assertIn(f"https://github.com/{REPO}/settings/actions", line)
        self.assertNotIn("/organizations/", line)
        self.assert_went_on(done, calls)

    def test_a_refused_read_is_reported_with_the_repositorys_page_and_nothing_is_written(self):
        # A login without admin rights cannot read the setting, and without
        # the default permissions there is nothing safe to send back.
        refused = answer(403, {"message": "Must have admin rights to Repository."},
                         stderr="gh: Must have admin rights to Repository. (HTTP 403)\n")
        done, calls = self.run_script(refused)
        self.assertEqual(self.puts(calls), [])
        line = self.line(done)
        self.assertIn("not changed (gh: Must have admin rights to Repository. (HTTP 403))", line)
        self.assertIn(f"https://github.com/{REPO}/settings/actions", line)
        self.assert_went_on(done, calls)

    def test_a_refused_write_that_is_not_the_organizations_is_the_repositorys_to_fix(self):
        done, calls = self.run_script(workflow_answer("read", False), answer(403))
        line = self.line(done)
        self.assertIn("not changed (gh: fake answer (HTTP 403))", line)
        self.assertIn(f"https://github.com/{REPO}/settings/actions", line)
        self.assertNotIn("organizations/", line)
        self.assert_went_on(done, calls)

    def test_an_answer_that_does_not_say_the_permissions_sends_nothing(self):
        # The PUT sets the token's default permissions too, so a value read
        # wrong or missing would be written back: no PUT at all instead.
        for body in ({"can_approve_pull_request_reviews": False},
                     {"default_workflow_permissions": "admin", "can_approve_pull_request_reviews": False},
                     {"default_workflow_permissions": "read", "can_approve_pull_request_reviews": "false"}):
            with self.subTest(body=body):
                done, calls = self.run_script(answer(200, body), answer(204))
                self.assertEqual(self.puts(calls), [])
                line = self.line(done)
                self.assertIn("not changed (GitHub's answer did not say the token's default permissions, so nothing "
                              "was sent back)", line)
                self.assertIn(f"https://github.com/{REPO}/settings/actions", line)
                self.assert_went_on(done, calls)

    def test_a_gh_too_old_for_the_flags_is_named_as_that_and_not_as_github(self):
        old = answer(400, stderr="unknown flag: --silent\n\nUsage:  gh api <endpoint> [flags]\n")
        done, calls = self.run_script(workflow_answer("read", False), old)
        self.assertEqual(self.line(done), "workflow permissions: this gh (gh version 1.14.0 (2021-08-04)) predates the "
                         "flag; install gh 2.65 or later (https://github.com/cli/cli/blob/trunk/docs/install_linux.md) "
                         "and run this again")
        self.assertEqual(len(self.puts(calls)), 1)
        self.assert_went_on(done, calls)


RULESET_ID = 42
CHECK_RUNS = f"repos/{REPO}/commits/main/check-runs?check_name=check&per_page=100"
LISTED = f"repos/{REPO}/rulesets?includes_parents=false&per_page=100"


def live_ruleset(check, strict=False):
    """The ruleset as GitHub reads it back, with fields a PUT does not take."""
    ruleset = json.loads(MAIN.read_text())
    for rule in ruleset["rules"]:
        if rule["type"] == "required_status_checks":
            rule["parameters"]["required_status_checks"] = [check]
            rule["parameters"]["strict_required_status_checks_policy"] = strict
    return dict(ruleset, id=RULESET_ID, source_type="Repository", source=REPO, _links={})


class CheckPin(unittest.TestCase):
    """A required check named by its context alone takes a commit status of
    that name from anyone with write access, so the script pins "check" to
    GitHub Actions (app 15368) once Actions has reported it on the default
    branch, and says to run it again when it has not, since GitHub refuses
    a pin to an app that never reported the check."""

    run_script = WorkflowPermissions.run_script

    def pin(self, reported, check=None, write=None, listed=None, read=None, strict=False, both=False):
        name = json.loads(MAIN.read_text())["name"]
        live = live_ruleset(check or {"context": "check"}, strict)
        extra = {
            f"GET {LISTED}": [listed or answer(200, [{"id": RULESET_ID, "name": name}])],
            f"GET {CHECK_RUNS}": [answer(200, f"{reported}\n")],
            f"GET repos/{REPO}/rulesets/{RULESET_ID}": [read or answer(200, live)],
            f"PUT repos/{REPO}/rulesets/{RULESET_ID}": [write or answer(200, "")],
        }
        done, calls = self.run_script(workflow_answer("read", True), extra=extra)
        self.assertEqual(done.returncode, 0, done.stderr)
        lines = [line for line in done.stdout.splitlines() if line.startswith("check pin:")]
        rules = [line for line in done.stdout.splitlines() if line.startswith("up-to-date rule:")]
        self.assertEqual(len(lines), 1, done.stdout)
        self.assertEqual(len(rules), 1, done.stdout)
        puts = [call for call in calls if call["key"] == f"PUT repos/{REPO}/rulesets/{RULESET_ID}"]
        return ((lines[0], rules[0]) if both else lines[0]), puts

    def test_pins_the_check_once_actions_has_reported_it_keeping_every_rule(self):
        line, puts = self.pin(1)
        self.assertEqual(line, 'check pin: "check" now requires GitHub Actions as its source')
        self.assertEqual(len(puts), 1)
        sent = json.loads(puts[0]["stdin"])
        wanted = json.loads(MAIN.read_text())
        for rule in wanted["rules"]:
            if rule["type"] == "required_status_checks":
                rule["parameters"]["required_status_checks"] = [{"context": "check", "integration_id": 15368}]
        self.assertEqual(sent, wanted)

    def test_waits_for_actions_to_report_the_check(self):
        line, puts = self.pin(0)
        self.assertIn("not yet; GitHub Actions has not reported \"check\" on main", line)
        self.assertIn("run this again after the first pull request's check", line)
        self.assertEqual(puts, [])

    def test_leaves_a_pinned_check_alone(self):
        line, puts = self.pin(1, {"context": "check", "integration_id": 15368})
        self.assertEqual(line, 'check pin: already pinned, or the ruleset requires no check named "check"')
        self.assertEqual(puts, [])

    def test_an_organizations_ruleset_is_left_to_its_owners(self):
        # The list asks for the repository's own rulesets alone; with none of
        # the name, the step names where an organization's is pinned.
        line, puts = self.pin(1, listed=answer(200, []))
        self.assertIn("the repository has no ruleset", line)
        self.assertIn("organization's Settings, Rules", line)
        self.assertEqual(puts, [])

    def test_a_refused_list_says_so(self):
        line, puts = self.pin(1, listed=answer(403))
        self.assertIn("could not list the rulesets: gh: fake answer (HTTP 403)", line)
        self.assertEqual(puts, [])

    def test_a_ruleset_that_cannot_be_read_is_not_called_pinned(self):
        line, puts = self.pin(1, read=answer(200, "not json"))
        self.assertEqual(line, "check pin: not changed (the ruleset GitHub gave back could not be read)")
        self.assertEqual(puts, [])

    def test_a_refused_pin_names_the_rulesets_page_and_goes_on(self):
        line, puts = self.pin(1, write=answer(422, {"message": "Validation Failed"}))
        self.assertIn("not changed (gh: fake answer (HTTP 422))", line)
        self.assertIn(f"https://github.com/{REPO}/settings/rules/{RULESET_ID}", line)
        self.assertEqual(len(puts), 1)


class UpToDateRule(unittest.TestCase):
    """"Require branches to be up to date" made every merge send each other
    ready pull request back to CI, so no shipped ruleset carries it and the
    script turns it off in a ruleset that has it on, whether or not the
    check can be pinned yet, keeping every other rule as it was."""

    pin = CheckPin.pin
    run_script = WorkflowPermissions.run_script

    def test_no_shipped_ruleset_requires_an_up_to_date_branch(self):
        for path in sorted((ROOT / "docs" / "setup").glob("ruleset-*.json")):
            with self.subTest(ruleset=path.name):
                for rule in json.loads(path.read_text())["rules"]:
                    if rule["type"] == "required_status_checks":
                        self.assertIs(rule["parameters"]["strict_required_status_checks_policy"], False)

    def test_turns_it_off_before_the_check_has_reported(self):
        (pin, rule), puts = self.pin(0, strict=True, both=True)
        self.assertIn("not yet", pin)
        self.assertEqual(rule, "up-to-date rule: turned off")
        self.assertEqual(len(puts), 1)
        sent_back = {key: value for key, value in live_ruleset({"context": "check"}).items()
                     if key in ("name", "target", "enforcement", "conditions", "rules", "bypass_actors")}
        self.assertEqual(json.loads(puts[0]["stdin"]), sent_back)

    def test_turns_it_off_and_pins_in_one_put(self):
        (pin, rule), puts = self.pin(1, strict=True, both=True)
        self.assertEqual(pin, 'check pin: "check" now requires GitHub Actions as its source')
        self.assertEqual(rule, "up-to-date rule: turned off")
        self.assertEqual(len(puts), 1)
        checks = [r for r in json.loads(puts[0]["stdin"])["rules"] if r["type"] == "required_status_checks"]
        self.assertIs(checks[0]["parameters"]["strict_required_status_checks_policy"], False)
        self.assertEqual(checks[0]["parameters"]["required_status_checks"], [{"context": "check", "integration_id": 15368}])

    def test_leaves_a_ruleset_with_it_off_alone(self):
        (pin, rule), puts = self.pin(1, {"context": "check", "integration_id": 15368}, both=True)
        self.assertEqual(rule, "up-to-date rule: off already")
        self.assertEqual(puts, [])

    def test_a_refused_put_names_the_box_to_untick(self):
        (pin, rule), puts = self.pin(0, strict=True, write=answer(403), both=True)
        self.assertIn("not yet", pin)
        self.assertIn("not changed (gh: fake answer (HTTP 403))", rule)
        self.assertIn("Require branches to be up to date before merging", rule)
        self.assertIn(f"https://github.com/{REPO}/settings/rules/{RULESET_ID}", rule)


class EveryShippedRuleset(unittest.TestCase):
    """The workflows rewrite branches of their own with GitHub's token: the
    board force-pushes board, the metrics workflow metrics and the protocol
    workflow symphony-protocol/sync, and the board renames a released
    claim's branch out of claude/ into released/. GitHub lets only an
    administrator do that to a branch a ruleset covers, so a ruleset over
    any of them strands a claim or leaves a branch stale. Every ruleset the
    template ships, which setup-repo.sh, crowd.py and an organization's
    owner apply, therefore targets the default branch and nothing else, and
    a change that widens one fails here before any repository takes it."""

    def test_each_targets_the_default_branch_and_nothing_else(self):
        files = sorted((ROOT / "docs" / "setup").glob("ruleset-*.json"))
        self.assertEqual([path.name for path in files],
                         ["ruleset-crowd.json", "ruleset-main.json", "ruleset-org.json"])
        for path in files:
            with self.subTest(ruleset=path.name):
                ruleset = json.loads(path.read_text())
                self.assertEqual(ruleset["target"], "branch")
                self.assertEqual(ruleset["conditions"]["ref_name"], {"include": ["~DEFAULT_BRANCH"], "exclude": []})


class OrganizationRuleset(unittest.TestCase):
    def test_holds_the_same_rules_and_ref_condition_as_the_repository_one(self):
        main = json.loads(MAIN.read_text())
        org = json.loads(ORG.read_text())
        self.assertEqual(org["rules"], main["rules"])
        self.assertEqual(org["conditions"]["ref_name"], main["conditions"]["ref_name"])
        for key in ("target", "enforcement", "bypass_actors"):
            self.assertEqual(org[key], main[key])

    def test_targets_every_repository_of_the_organization(self):
        # The organization endpoint wants repository_name beside ref_name.
        org = json.loads(ORG.read_text())
        self.assertEqual(org["conditions"]["repository_name"], {"include": ["~ALL"], "exclude": [], "protected": False})
        self.assertNotIn("repository_name", json.loads(MAIN.read_text())["conditions"])


if __name__ == "__main__":
    unittest.main()
