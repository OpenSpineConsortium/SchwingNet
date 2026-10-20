"""The two steps of .github/workflows/workers.yml that choose each leg's
move, and the step of .github/workflows/coordinator.yml that starts a
task's worker again, run as the workflows run them: their own scripts
under bash, in a folder laid out like the checkout, with stand-ins for
what they ask of GitHub. The registry's step deals the run from one look when the vendored
library has `team deal`, and leaves the deal empty when it has not; the
leg's step takes the move it was dealt, looks again since it may have
waited for an earlier run of its worker, and keeps from that look only its
worker's own work, while an issue of the shared queue, or one the labels
give to several workers, is taken only as dealt and only while nobody has
claimed, closed, held or given it away since. A string in the workflow
says nothing of what its script does, so these run it.

The stand-ins: tools/team.py answers `next` and `deal` as the test says and
logs each call; git answers `ls-remote` for the claim branches the test
names, exiting 2 for one that is not there, as git does; gh answers
`issue view` from the issues the test gives, in gh's JSON shape or, with
`--jq '.labels[].name'`, as the label names, fails for any other issue,
and logs each `workflow run`. The library's own labels module and the
registry's real tools/workers.py are used as they are.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "workers.yml"
COORDINATOR = ROOT / ".github" / "workflows" / "coordinator.yml"
REGISTRY = ".github/symphony/workers"
REPO = "example-org/example"
WORKERS = ("w1", "w2")

TEAM = """
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_TEAM_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\\n")
answers = json.loads(os.environ["FAKE_TEAM"])
answer = answers.get(args[0] + (" --help" if "--help" in args else ""))
if answer is None or isinstance(answer, int):
    sys.exit(answer if isinstance(answer, int) else 2)
print(answer)
"""
GIT = """#!/bin/bash
if [ "$1" = ls-remote ]; then
  [ -n "${FAKE_ORIGIN_DOWN:-}" ] && exit 128
  branch="${@: -1}"
  for claimed in $FAKE_CLAIMED; do
    [ "$branch" = "refs/heads/claude/$claimed" ] && exit 0
  done
  exit 2
fi
echo "fake git: $*" >&2
exit 1
"""
GH = """
import json, os, sys
args = sys.argv[1:]
if args[:2] == ["workflow", "run"]:
    with open(os.environ["FAKE_GH_LOG"], "a", encoding="utf-8") as log:
        log.write(json.dumps(args[2:]) + "\\n")
    sys.exit(0)
issues = json.loads(os.environ["FAKE_ISSUES"])
if args[:2] != ["issue", "view"] or args[2] not in issues:
    sys.stderr.write("fake gh: no answer for %s\\n" % " ".join(args))
    sys.exit(1)
issue = issues[args[2]]
if "--jq" in args and args[args.index("--jq") + 1] == ".labels[].name":
    print("\\n".join(issue.get("labels", [])))
    sys.exit(0)
print(json.dumps({"state": issue.get("state", "OPEN"),
                  "labels": [{"id": "L" + name, "name": name, "description": "", "color": "ededed"}
                             for name in issue.get("labels", [])]}))
"""


def step_script(name, workflow=WORKFLOW):
    """The script of the step with this name, as the runner hands it to bash."""
    lines = workflow.read_text(encoding="utf-8").splitlines()
    start = lines.index(f"      - name: {name}")
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].startswith("      - ") or (lines[i].strip() and not lines[i].startswith(" " * 8))),
               len(lines))
    body = lines[start:end]
    run = next(i for i, line in enumerate(body) if line.strip() == "run: |")
    return textwrap.dedent("\n".join(body[run + 1:])) + "\n"


LEG = step_script("Read the worker's settings and the move it was dealt")
REGISTRY_STEP = step_script("List the workers that run in Actions and deal them the open work")
UNBLOCK = step_script("Start the task's worker again", COORDINATOR)


def queued(*more):
    return {"labels": ["todo", *more]}


def given(worker, *more):
    return {"labels": [f"worker:{worker}", *more]}


class Checkout:
    """A folder laid out as the job's checkout, with the stand-ins first on
    PATH, the registry's two workers in Actions, and the runner's files."""

    def __init__(self, folder):
        self.root = Path(folder) / "checkout"
        tools = self.root / "tools"
        tools.mkdir(parents=True)
        (tools / "sdlc_protocol").symlink_to(ROOT / "tools" / "sdlc_protocol")
        (tools / "workers.py").symlink_to(ROOT / "tools" / "workers.py")
        (tools / "team.py").write_text(TEAM, encoding="utf-8")
        registry = self.root / REGISTRY
        registry.mkdir(parents=True)
        for name in WORKERS:
            (registry / f"{name}.json").write_text(json.dumps({
                "name": name, "runs": "actions", "about": "A worker of the test.", "area": [], "lands": "owner",
                "model": "", "max_turns": 40, "rounds": 3, "account": ""}, indent=2) + "\n", encoding="utf-8")
        self.bin = Path(folder) / "bin"
        self.bin.mkdir()
        for name, text in (("git", GIT), ("gh", f"#!{sys.executable} -IS\n" + GH)):
            (self.bin / name).write_text(text, encoding="utf-8")
            (self.bin / name).chmod(0o755)
        self.temp = Path(folder) / "runner"
        self.temp.mkdir()
        self.output = self.temp / "output"
        self.team_log = self.temp / "team.log"
        self.gh_log = self.temp / "gh.log"

    def run(self, script, team, issues=None, claimed=(), **env):
        self.output.write_text("")
        self.gh_log.unlink(missing_ok=True)
        environ = {
            "PATH": f"{self.bin}{os.pathsep}{Path(sys.executable).parent}{os.pathsep}/usr/bin:/bin",
            "HOME": str(self.temp), "RUNNER_TEMP": str(self.temp), "GITHUB_OUTPUT": str(self.output),
            "GITHUB_REPOSITORY": REPO, "REGISTRY": REGISTRY, "WORKER": "w1", "DEALS": "",
            "FAKE_TEAM": json.dumps(team), "FAKE_TEAM_LOG": str(self.team_log), "FAKE_GH_LOG": str(self.gh_log),
            "FAKE_ISSUES": json.dumps({str(n): i for n, i in (issues or {}).items()}),
            "FAKE_CLAIMED": " ".join(str(n) for n in claimed), **env,
        }
        python3 = self.bin / "python3"
        if not python3.exists():
            python3.symlink_to(sys.executable)
        return subprocess.run(["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", script],
                              cwd=self.root, env=environ, capture_output=True, text=True, timeout=60)

    def outputs(self):
        found = {}
        for line in self.output.read_text().splitlines():
            key, _, value = line.partition("=")
            found[key] = value
        return found

    def team_calls(self):
        if not self.team_log.exists():
            return []
        return [json.loads(line) for line in self.team_log.read_text().splitlines()]

    def workflow_runs(self):
        """What `gh workflow run` was asked for, each call's arguments."""
        if not self.gh_log.exists():
            return []
        return [json.loads(line) for line in self.gh_log.read_text().splitlines()]


class TheScripts(unittest.TestCase):
    def test_both_scripts_parse_and_the_python_in_the_leg_compiles(self):
        for script in (LEG, REGISTRY_STEP, UNBLOCK):
            done = subprocess.run(["bash", "-n"], input=script, capture_output=True, text=True, timeout=30)
            self.assertEqual(done.returncode, 0, done.stderr)
        python = LEG.split("python3 -c '\nimport json, sys\n", 1)[1].split("\n' ", 1)[0]
        compile("import json, sys\n" + python, "the leg's standing", "exec")
        self.assertNotIn("${{", LEG + REGISTRY_STEP + UNBLOCK)


class TheUnblock(unittest.TestCase):
    """The coordinator's step that starts a task's worker again once the
    task is settled: one worker named and in Actions is started alone;
    several named, one of them at least in Actions, start every worker,
    since the deal over the whole registry picks which of them takes it
    (symphony-protocol's F18); none of them in Actions, nobody named, or
    the task still blocked start nothing."""

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.checkout = Checkout(self.folder)

    def unblock(self, labels):
        done = self.checkout.run(UNBLOCK, {}, {5: {"labels": labels}}, TASK="5")
        self.assertEqual(done.returncode, 0, done.stderr)
        return self.checkout.workflow_runs(), done.stdout

    def test_one_worker_in_actions_is_started_alone(self):
        for labels in (["todo", "worker:w1"], ["agent:w1", "worker:w1", "todo"]):
            with self.subTest(labels=labels):
                runs, said = self.unblock(labels)
                self.assertEqual(runs, [["workers.yml", "--repo", REPO, "-f", "worker=w1"]])
                self.assertIn("w1 started again for #5", said)

    def test_several_workers_one_of_them_in_actions_start_every_worker(self):
        for labels in (["todo", "worker:w1", "worker:w2"], ["todo", "worker:alice", "worker:w1"],
                       ["account:w2", "worker:alice"]):
            with self.subTest(labels=labels):
                runs, said = self.unblock(labels)
                self.assertEqual(runs, [["workers.yml", "--repo", REPO]])
                self.assertIn("given to several workers", said)

    def test_workers_outside_actions_and_a_blocked_task_start_nothing(self):
        cases = {
            "two workers outside Actions": (["todo", "worker:alice", "worker:bob"], "does not run in Actions"),
            "one worker outside Actions": (["todo", "worker:alice"], "does not run in Actions"),
            "nobody named": (["todo"], "(none named) does not run in Actions"),
            "still blocked": (["blocked", "worker:w1", "worker:w2"], "still blocked"),
        }
        for why, (labels, word) in cases.items():
            with self.subTest(why=why):
                runs, said = self.unblock(labels)
                self.assertEqual(runs, [])
                self.assertIn(word, said)


class TheDeal(unittest.TestCase):
    """The registry's step: one deal for the run, or none while the vendored
    library has no deal command."""

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.checkout = Checkout(self.folder)

    def run_step(self, team, **env):
        done = self.checkout.run(REGISTRY_STEP, team, **{"ONLY": "", "LABEL": "", **env})
        self.assertEqual(done.returncode, 0, done.stderr)
        return self.checkout.outputs(), done.stdout

    def test_a_library_with_deal_deals_the_run_once(self):
        deals = '{"w1":"take 3","w2":"take 4"}'
        found, said = self.run_step({"deal --help": 0, "deal": deals})
        self.assertEqual(json.loads(found["workers"]), list(WORKERS))
        self.assertEqual(found["deals"], deals)
        self.assertIn("dealt from one look", said)
        calls = [c for c in self.checkout.team_calls() if "--help" not in c]
        self.assertEqual(calls, [["deal", "--registry", REGISTRY, "--workers", json.dumps(list(WORKERS))]])

    def test_a_library_without_deal_leaves_each_leg_to_ask_for_itself(self):
        found, said = self.run_step({"deal --help": 2})
        self.assertEqual(found["deals"], "")
        self.assertIn("each leg asks for itself", said)

    def test_a_deal_that_fails_fails_the_step(self):
        done = self.checkout.run(REGISTRY_STEP, {"deal --help": 0, "deal": 1}, ONLY="", LABEL="")
        self.assertNotEqual(done.returncode, 0)

    def test_a_worker_label_runs_that_worker_alone(self):
        """One worker under two spellings is one holder (labels.holder_names
        counts a name once), so the run still narrows to it."""
        for issue_labels in ('["todo", "worker:w2"]', '["agent:w2", "worker:w2"]', '["account:w2", "agent:w2", "worker:w2"]'):
            with self.subTest(issue_labels=issue_labels):
                found, _ = self.run_step({"deal --help": 0, "deal": '{"w2":"take 4"}'}, LABEL="worker:w2",
                                         ISSUE_LABELS=issue_labels)
                self.assertEqual(json.loads(found["workers"]), ["w2"])

    def test_a_worker_label_on_an_issue_given_to_several_workers_runs_every_worker(self):
        """The deal is over the whole registry, so an issue the labels give
        to several workers may go to one the new label does not name
        (symphony-protocol's F18); a run of the labelled worker alone would
        leave the task to the schedule. Labels the event does not give, as
        when the step runs outside an issue event, narrow nothing."""
        for issue_labels in ('["worker:w1", "worker:w2"]', '["todo", "agent:w1", "worker:w2"]', "null", "[]"):
            with self.subTest(issue_labels=issue_labels):
                found, _ = self.run_step({"deal --help": 0, "deal": '{"w1":"take 4","w2":"none"}'},
                                         LABEL="worker:w2", ISSUE_LABELS=issue_labels)
                self.assertEqual(json.loads(found["workers"]), list(WORKERS))


class TheLeg(unittest.TestCase):
    """The leg's step: the move it was dealt, checked against a fresh look
    and the issue's own state."""

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.checkout = Checkout(self.folder)

    def leg(self, dealt, fresh, issues=None, claimed=(), **env):
        """The move the leg settles on, given what the run dealt w1 (None
        for no deal) and what a fresh look answers (an int is the exit
        code of a look that fails)."""
        deals = "" if dealt is None else json.dumps({"w1": dealt, "w2": "none"})
        done = self.checkout.run(LEG, {"next": fresh}, issues, claimed, DEALS=deals, **env)
        self.assertEqual(done.returncode, 0, done.stderr)
        found = self.checkout.outputs()
        self.assertEqual((found["model"], found["max_turns"], found["rounds"]), ("", "40", "3"))
        move = found["move"] if found["move"] == "none" else f"{found['move']} {found['issue']}"
        return move, done.stdout

    def test_with_no_deal_the_leg_takes_its_own_look(self):
        move, said = self.leg(None, "take 5", {5: queued()})
        self.assertEqual(move, "take 5")
        self.assertIn("from its own look", said)
        self.assertEqual(self.checkout.team_calls(),
                         [["next", "--agent", "w1", "--registry", REGISTRY, "--label", "worker:w1"]])

    def test_a_dealt_issue_that_still_stands_is_taken_whatever_the_queue_holds_now(self):
        self.assertEqual(self.leg("take 5", "take 9", {5: queued(), 9: queued()})[0], "take 5")
        self.assertEqual(self.leg("take 5", "none", {5: queued()})[0], "take 5")
        self.assertEqual(self.leg("take 5", "take 5", {5: given("w1")})[0], "take 5")

    def test_a_dealt_issue_claimed_closed_held_or_given_away_since_is_left_alone(self):
        cases = {
            "claimed": ({5: queued()}, (5,)),
            "closed": ({5: dict(queued(), state="CLOSED")}, ()),
            "labelled claimed": ({5: queued("claimed")}, ()),
            "labelled blocked": ({5: queued("blocked")}, ()),
            "given to w2": ({5: given("w2", "todo")}, ()),
            "given to w2, w3": ({5: given("w2", "worker:w3")}, ()),
            "out of the queue": ({5: {"labels": []}}, ()),
        }
        for why, (issues, claimed) in cases.items():
            with self.subTest(why=why):
                move, said = self.leg("take 5", "none", issues, claimed)
                self.assertEqual(move, "none")
                self.assertIn(f"#5 is {why} since the run looked", said)

    def test_a_dealt_task_the_labels_give_to_several_workers_is_taken(self):
        """A task given to this worker and to others is each of theirs, and
        the run's deal says which of them takes it (symphony-protocol's
        F18): the leg takes it as dealt, with or without todo and under
        the older label spellings, whatever its own fresh look says of the
        queue. Until this, standing() called such an issue given to
        others, so the worker it was dealt to idled on every run."""
        issues = {5: given("w1", "worker:w2"), 6: given("w1", "worker:w2", "todo"),
                  7: {"labels": ["account:w1", "agent:w2"]}, 8: given("w2", "worker:w1", "worker:w3")}
        for number in issues:
            with self.subTest(number=number):
                move, said = self.leg(f"take {number}", "none", issues)
                self.assertEqual(move, f"take {number}")
                self.assertNotIn("since the run looked", said)
        self.assertEqual(self.leg("take 5", "take 5", issues)[0], "take 5")
        self.assertEqual(self.leg("take 5", "take 6", issues)[0], "take 5")
        self.assertEqual(self.leg("take 5", "none", issues, (5,))[0], "none")

    def test_the_worker_s_own_claim_that_needs_work_comes_first(self):
        """The clerk answers a claim of the worker's own first; one made by
        its earlier run while this leg waited is carried, and so is one that
        fell behind since the deal, which no peer can be dealt."""
        self.assertEqual(self.leg("take 5", "carry 5", {5: queued()}, (5,))[0], "carry 5")
        self.assertEqual(self.leg("take 5", "carry 3", {5: queued()}, (3,))[0], "carry 3")
        self.assertEqual(self.leg("none", "carry 4", {}, (4,))[0], "carry 4")
        self.assertEqual(self.leg("carry 4", "carry 4", {}, (4,))[0], "carry 4")

    def test_an_issue_given_to_the_worker_alone_is_kept_from_the_fresh_look(self):
        issues = {8: given("w1"), 7: queued()}
        self.assertEqual(self.leg("carry 4", "take 8", issues)[0], "take 8")
        self.assertEqual(self.leg("none", "take 8", issues)[0], "take 8")

    def test_a_take_of_the_shared_queue_from_the_fresh_look_is_never_kept(self):
        """Only the run's one look deals the queue (F4), and a task given to
        several workers with it (F18): a leg that kept its own look's take
        of a queued or shared issue could take one a peer was dealt."""
        issues = {7: queued(), 8: given("w1", "claimed"), 9: given("w1"), 10: given("w1", "worker:w2")}
        for fresh, claimed in (("take 7", ()), ("take 8", ()), ("take 9", (9,)), ("take 10", ())):
            with self.subTest(fresh=fresh):
                self.assertEqual(self.leg("carry 4", fresh, issues, claimed)[0], "none")
                self.assertEqual(self.leg("none", fresh, issues, claimed)[0], "none")

    def test_what_the_leg_cannot_read_leaves_the_claim_lock_to_decide(self):
        self.assertEqual(self.leg("take 5", "none", {})[0], "take 5")
        move, said = self.leg("take 5", "none", {5: queued()}, FAKE_ORIGIN_DOWN="1")
        self.assertEqual(move, "take 5")
        self.assertIn("the claim lock decides", said)

    def test_a_dealt_task_given_to_the_worker_alone_is_taken_as_dealt(self):
        """The dealt path's own acceptance of an issue given to this worker
        alone: the fresh look keeps such a take first, so this shows only
        when the fresh look fails or answers something else."""
        issues = {5: given("w1"), 6: given("w1", "todo")}
        self.assertEqual(self.leg("take 5", 1, issues)[0], "take 5")
        self.assertEqual(self.leg("take 6", "none", issues)[0], "take 6")
        self.assertEqual(self.leg("take 5", 1, issues, (5,))[0], "none")

    def test_standing_names_each_state_by_its_word(self):
        """The leg's checks read standing()'s word, which the log shows
        only on a refusal; each word is held here on its own."""
        issues = {1: queued(), 2: given("w1"), 3: given("w1", "worker:w2"), 4: given("w2", "worker:w3"),
                  5: {"labels": ["account:w1", "agent:w2"]}, 6: given("w1", "claimed", "worker:w2")}
        words = {1: "free", 2: "mine", 3: "shared", 4: "given to w2, w3", 5: "shared", 6: "labelled claimed"}
        for number, word in words.items():
            with self.subTest(number=number):
                done = self.checkout.run(LEG + f"\nstanding {number}\n", {"next": "none"}, issues)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertEqual(done.stdout.rstrip().splitlines()[-1], word)

    def test_a_fresh_look_that_fails_leaves_the_dealt_move_to_its_own_checks(self):
        move, said = self.leg("take 5", 1, {5: queued()})
        self.assertEqual(move, "take 5")
        self.assertIn("a fresh look failed", said)
        self.assertEqual(self.leg("take 5", 1, {5: queued()}, (5,))[0], "none")
        self.assertEqual(self.leg("carry 4", 1, {})[0], "carry 4")
        self.assertEqual(self.leg("none", 1, {})[0], "none")


if __name__ == "__main__":
    unittest.main()
