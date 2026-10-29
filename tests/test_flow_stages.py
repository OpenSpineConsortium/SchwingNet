"""What every launched flow keeps for the owner's rule of 2026-10-29, held without Metaflow.

The rule: every deep learning job on the grid runs on a flow flows/launch.py starts, under a PREREG
frozen before the run, with the CLAIM 2024 and REFORMS report enforced and a progress page in the
browser. These tests hold the parts that need no Metaflow and so run under the required check's
plain python3: the registry of flows and its PREREG freeze (flows/stage_registry.py), the launcher's
refusal with the Lab Recipe's exit 90 before it imports Metaflow, the progress page and its short
lines (flows/stage_progress.py), and the page drawn off the grid from the gate's status answer
(tools/progress_page.py). tests/test_flows.py runs the flows themselves where Metaflow is installed.
"""

import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import warnings
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
LAUNCH = ROOT / "flows" / "launch.py"
# The launcher imports the contracts of schwingnet.pipeline, which the plain python of the required
# check lacks; its refusals are tested where the train environment is, as tests/test_flows.py is.
NO_CONTRACTS = importlib.util.find_spec("icontract") is None
# flows/stage.py imports Metaflow's current, which only the train environment carries.
NO_METAFLOW = importlib.util.find_spec("metaflow") is None


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


registry = load(ROOT / "flows" / "stage_registry.py", "stage_registry_under_test")
progress = load(ROOT / "flows" / "stage_progress.py", "stage_progress_under_test")
page_tool = load(ROOT / "tools" / "progress_page.py", "progress_page_under_test")

ALPHA = hashlib.sha256(b"the plan alpha\n").hexdigest()
PREREG = f"# A design\n\nCovers: alpha={ALPHA}, beta\n\n## 1. The question\n\nWhether it runs.\n"


# A flow whose PREREG covers parts names the part a run is, as the sweep does.
DEEP_FLOW = "class DeepFlow(FlowSpec):\n    pass\n\n\ndef prereg_part(words, folder):\n    return None, None\n"


def freeze(folder, text=PREREG):
    """A PREREG.md and the PREREG.md.sha256 `sha256sum PREREG.md` writes beside it."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "PREREG.md").write_text(text, encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    (folder / "PREREG.md.sha256").write_text(f"{digest}  PREREG.md\n", encoding="ascii")
    return digest


class RegistryTest(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        (self.repo / "flows").mkdir()
        (self.repo / "grid").mkdir()
        (self.repo / "flows" / "deep.py").write_text(DEEP_FLOW, encoding="utf-8")
        (self.repo / "grid" / "deep.sbatch").write_text('exec python "$REPO/flows/launch.py" deep -- "$@"\n', encoding="utf-8")
        self.digest = freeze(self.repo / "docs" / "deep")
        self.write_registry("deep DeepFlow DEEP_RC deep.sbatch docs/deep/PREREG.md")

    def write_registry(self, *lines):
        (self.repo / "flows" / "registry.txt").write_text("# kind class word script PREREG\n" + "\n".join(lines) + "\n", encoding="utf-8")

    def test_the_repositorys_registry_holds_together_and_names_every_flow_the_launcher_started_before(self):
        self.assertEqual(registry.problems(ROOT), [])
        listed = registry.entries(ROOT)
        self.assertLessEqual({"bank", "catalog", "sweep"}, set(listed))
        self.assertEqual((listed["sweep"]["class"], listed["sweep"]["word"], listed["sweep"]["script"]),
                         ("SweepFlow", "SWEEP_RC", "sweep-driver.sbatch"))
        # the stages that train and run no network have no PREREG; the sweep trains, so it has one
        self.assertIsNone(registry.frozen_prereg("bank", ROOT))
        self.assertEqual(registry.frozen_prereg("sweep", ROOT)[0], "docs/research/block-smoke/PREREG.md")

    def test_a_frozen_prereg_is_its_path_and_sha256(self):
        self.assertEqual(registry.frozen_prereg("deep", self.repo), ("docs/deep/PREREG.md", self.digest))
        self.assertEqual(registry.problems(self.repo), [])

    def test_a_prereg_edited_since_its_freeze_stops_the_job_in_the_lab_recipes_words(self):
        with (self.repo / "docs" / "deep" / "PREREG.md").open("a", encoding="utf-8") as prereg:
            prereg.write("A hypothesis added after the data were seen.\n")
        with self.assertRaisesRegex(registry.PreregError, r"^STOP: docs/deep/PREREG.md changed since the freeze"):
            registry.frozen_prereg("deep", self.repo)
        self.assertEqual(len(registry.problems(self.repo)), 1)

    def test_a_prereg_never_frozen_or_frozen_in_another_shape_is_refused(self):
        record = self.repo / "docs" / "deep" / "PREREG.md.sha256"
        record.write_text(f"{self.digest}\n", encoding="ascii")
        with self.assertRaisesRegex(registry.PreregError, "not one line of `sha256sum PREREG.md`"):
            registry.frozen_prereg("deep", self.repo)
        record.unlink()
        with self.assertRaisesRegex(registry.PreregError, "was never frozen"):
            registry.frozen_prereg("deep", self.repo)

    def test_a_part_the_prereg_does_not_cover_waits_for_a_prereg_of_its_own(self):
        self.assertEqual(registry.covered(self.repo / "docs" / "deep" / "PREREG.md"), [("alpha", ALPHA), ("beta", None)])
        self.assertEqual(registry.frozen_for("deep", "beta", repo=self.repo), ("docs/deep/PREREG.md", self.digest))
        with self.assertRaisesRegex(registry.PreregError, "covers alpha, beta, not trials: a run of it waits for a PREREG of its own"):
            registry.frozen_for("deep", "trials", repo=self.repo)

    def test_a_part_covered_by_its_bytes_is_covered_only_while_they_are_the_ones_frozen(self):
        self.assertEqual(registry.frozen_for("deep", "alpha", ALPHA, self.repo), ("docs/deep/PREREG.md", self.digest))
        edited = hashlib.sha256(b"the plan alpha, edited\n").hexdigest()
        with self.assertRaisesRegex(registry.PreregError, rf"covers alpha as the bytes of sha256 {ALPHA[:16]}, and its bytes "
                                                          rf"now have sha256 {edited[:16]}: a alpha changed since the freeze is another design"):
            registry.frozen_for("deep", "alpha", edited, self.repo)
        with self.assertRaisesRegex(registry.PreregError, "and its bytes were not read"):
            registry.frozen_for("deep", "alpha", None, self.repo)
        # an entry named alone takes any bytes, as the name is all it holds the part to
        self.assertEqual(registry.frozen_for("deep", "beta", edited, self.repo)[0], "docs/deep/PREREG.md")

    def test_a_covers_entry_of_another_shape_covers_nothing(self):
        self.digest = freeze(self.repo / "docs" / "deep", PREREG.replace(f"alpha={ALPHA}", "alpha=0123"))
        with self.assertRaisesRegex(registry.PreregError, "holds 'alpha=0123', which is neither a part nor <part>=<sha256>"):
            registry.frozen_for("deep", "beta", repo=self.repo)

    def test_the_sweeps_prereg_covers_the_three_smoke_plans_by_their_bytes_and_not_the_trials(self):
        for plan in ("synthetic", "real", "two_source"):
            digest = hashlib.sha256((ROOT / "grid" / "sweeps" / f"{plan}.json").read_bytes()).hexdigest()
            self.assertEqual(registry.frozen_for("sweep", plan, digest, ROOT)[0], "docs/research/block-smoke/PREREG.md")
            with self.assertRaises(registry.PreregError):
                registry.frozen_for("sweep", plan, hashlib.sha256(b"another plan").hexdigest(), ROOT)
        trials = hashlib.sha256((ROOT / "grid" / "sweeps" / "trials.json").read_bytes()).hexdigest()
        with self.assertRaises(registry.PreregError):
            registry.frozen_for("sweep", "trials", trials, ROOT)

    def test_each_line_is_held_to_its_class_its_script_and_its_shape(self):
        (self.repo / "grid" / "deep.sbatch").write_text("python tools/train.py\n", encoding="utf-8")
        self.assertEqual(registry.problems(self.repo), ["deep: grid/deep.sbatch names no flows/launch.py deep"])
        (self.repo / "grid" / "deep.sbatch").write_text('exec python "$REPO/flows/launch.py" deeper\n', encoding="utf-8")
        self.assertEqual(registry.problems(self.repo), ["deep: grid/deep.sbatch names no flows/launch.py deep"])
        self.write_registry("deep OtherFlow DEEP_RC deep.sbatch docs/deep/PREREG.md")
        self.assertIn("deep: flows/deep.py defines no class OtherFlow", registry.problems(self.repo))
        for line, words in (("deep DeepFlow DEEP_RC deep.sbatch", "five words"),
                            ("deep DeepFlow DEEP deep.sbatch -", "is no word"),
                            ("deep DeepFlow DEEP_RC deep.sbatch ../PREREG.md", "a relative path to a PREREG.md inside the checkout"),
                            ("deep DeepFlow DEEP_RC deep.sbatch docs/../../PREREG.md", "with no . or .. folder"),
                            ("deep DeepFlow DEEP_RC deep.sbatch /etc/deep/PREREG.md", "a relative path"),
                            ("deep DeepFlow DEEP_RC deep.sbatch docs/./deep/PREREG.md", "with no . or .. folder"),
                            ("deep DeepFlow DEEP_RC deep.sbatch -\ndeep DeepFlow DEEP_RC other.sbatch -", "listed twice")):
            self.write_registry(line)
            with self.assertRaisesRegex(registry.RegistryError, words):
                registry.entries(self.repo)

    def test_a_prereg_folder_that_leads_out_of_the_checkout_is_refused(self):
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        freeze(outside)
        (self.repo / "docs" / "away").symlink_to(outside, target_is_directory=True)
        self.write_registry("deep DeepFlow DEEP_RC deep.sbatch docs/away/PREREG.md")
        self.assertEqual(registry.problems(self.repo), ["deep: docs/away/PREREG.md leads out of the checkout"])

    def test_only_the_stages_that_run_no_network_may_name_no_prereg(self):
        self.assertEqual(registry.NO_NETWORK, ("bank", "catalog"))
        self.write_registry("deep DeepFlow DEEP_RC deep.sbatch -")
        with self.assertRaisesRegex(registry.PreregError, "the deep flow names no PREREG, which only bank and catalog"):
            registry.frozen_prereg("deep", self.repo)
        self.assertEqual(len(registry.problems(self.repo)), 1)
        (self.repo / "flows" / "bank.py").write_text("class BankFlow(FlowSpec):\n    pass\n", encoding="utf-8")
        (self.repo / "grid" / "bank.sbatch").write_text('exec python "$REPO/flows/launch.py" bank\n', encoding="utf-8")
        self.write_registry("bank BankFlow BANK_RC bank.sbatch -")
        self.assertIsNone(registry.frozen_prereg("bank", self.repo))
        self.assertEqual(registry.problems(self.repo), [])

    def test_a_prereg_that_names_parts_needs_a_flow_that_names_the_part_a_run_is(self):
        message = ("deep: docs/deep/PREREG.md names the parts it covers, but flows/deep.py defines no prereg_part, "
                   "so no run would say which part it is and every run would pass as covered")
        self.assertEqual(registry.problems(self.repo), [])
        (self.repo / "flows" / "deep.py").write_text("class DeepFlow(FlowSpec):\n    pass\n", encoding="utf-8")
        self.assertEqual(registry.problems(self.repo), [message])
        # a PREREG with no Covers line covers every run of its kind, which needs no part
        (self.repo / "flows" / "deep.py").write_text("class DeepFlow(FlowSpec):\n    pass\n", encoding="utf-8")
        freeze(self.repo / "docs" / "deep", "# A design of one part\n")
        self.assertEqual(registry.problems(self.repo), [])

    def test_the_command_line_prints_the_prereg_or_stops_with_90(self):
        done = subprocess.run([sys.executable, str(ROOT / "flows" / "stage_registry.py"), "prereg", "sweep"], cwd=ROOT,
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertRegex(done.stdout, r"^docs/research/block-smoke/PREREG\.md [0-9a-f]{64}\n$")
        done = subprocess.run([sys.executable, str(ROOT / "flows" / "stage_registry.py"), "check"], cwd=ROOT,
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)


# No git of these tests runs gc or maintenance on its own, which once raced a scratch folder's removal
# on GitHub's runners; set both in the environment and in each scratch repository's config.
QUIET = {"gc.auto": "0", "gc.autoDetach": "false", "maintenance.auto": "false", "maintenance.autoDetach": "false",
         "receive.autogc": "false"}
GIT_ENV = {"GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.invalid", "GIT_COMMITTER_NAME": "Test",
           "GIT_COMMITTER_EMAIL": "test@example.invalid", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_CONFIG_COUNT": str(len(QUIET)), **{f"GIT_CONFIG_KEY_{i}": key for i, key in enumerate(QUIET)},
           **{f"GIT_CONFIG_VALUE_{i}": value for i, value in enumerate(QUIET.values())}}


class FrozenTest(unittest.TestCase):
    """`stage_registry.py frozen` on scratch repositories: what main froze never changes, whatever a
    pull request writes beside it, and a DEVIATIONS.md beside a frozen PREREG only grows."""

    def setUp(self):
        patcher = mock.patch.dict(os.environ, GIT_ENV)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = self.tmp / "repo"
        self.init(self.repo)
        self.study = self.repo / "docs" / "research" / "study"
        freeze(self.study)
        (self.study / "DEVIATIONS.md").write_text("# Deviations\n\n- 2026-10-29: the first.\n", encoding="utf-8")
        self.commit("the study, frozen")
        self.git("branch", "-M", "main")
        self.git("checkout", "-q", "-b", "topic")

    def git(self, *words, repo=None):
        return subprocess.run(["git", "-C", str(repo or self.repo), *words], check=True, capture_output=True, text=True, timeout=60).stdout

    def init(self, repo):
        repo.mkdir(parents=True, exist_ok=True)
        self.git("init", "-q", repo=repo)
        for key, value in QUIET.items():
            self.git("config", key, value, repo=repo)

    def commit(self, message, repo=None):
        self.git("add", "-A", repo=repo)
        self.git("commit", "-q", "--allow-empty", "-m", message, repo=repo)

    def frozen(self, base="main", repo=None, environ=None):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = registry.frozen_check(base, repo or self.repo, environ if environ is not None else {})
        return code, out.getvalue() + err.getvalue()

    def test_a_branch_that_leaves_every_frozen_prereg_as_it_was_passes(self):
        (self.repo / "README.md").write_text("work\n", encoding="utf-8")
        self.commit("other work")
        self.assertEqual(self.frozen(), (0, f"registry: every PREREG frozen where HEAD left main ({self.git('rev-parse', 'main')[:12]}) "
                                             f"is as it was, and every DEVIATIONS.md beside one only grew\n"))

    def test_a_prereg_edited_and_frozen_again_in_one_change_is_refused(self):
        freeze(self.study, PREREG + "A hypothesis added after the data were seen.\n")
        self.commit("an edit, frozen again")
        # the freeze record agrees with the file, so the registry's own check sees nothing wrong
        self.assertEqual(registry.frozen_hash(self.study / "PREREG.md"), hashlib.sha256((self.study / "PREREG.md").read_bytes()).hexdigest())
        code, said = self.frozen()
        self.assertEqual(code, 1, said)
        self.assertIn("registry: docs/research/study/PREREG.md changed since ", said)
        self.assertIn("registry: docs/research/study/PREREG.md.sha256 changed since ", said)
        self.assertIn("a frozen PREREG is never edited; a departure goes in DEVIATIONS.md beside it", said)

    def test_a_frozen_prereg_removed_is_refused_and_a_new_one_is_free_until_it_lands(self):
        fresh = self.repo / "docs" / "research" / "fresh"
        freeze(fresh)
        self.commit("a new design")
        freeze(fresh, PREREG + "Its design settled before it lands.\n")
        self.commit("the new design, settled")
        self.assertEqual(self.frozen()[0], 0)
        (self.study / "PREREG.md.sha256").unlink()
        self.commit("the freeze record taken away")
        code, said = self.frozen()
        self.assertEqual(code, 1, said)
        self.assertIn("docs/research/study/PREREG.md.sha256 is gone since ", said)

    def test_deviations_beside_a_frozen_prereg_only_grow(self):
        deviations = self.study / "DEVIATIONS.md"
        deviations.write_text(deviations.read_text(encoding="utf-8") + "- 2026-10-30: the second.\n", encoding="utf-8")
        self.commit("a departure added")
        self.assertEqual(self.frozen()[0], 0)
        deviations.write_text("# Deviations\n\n- 2026-10-29: the first, said otherwise.\n", encoding="utf-8")
        self.commit("a departure rewritten")
        code, said = self.frozen()
        self.assertEqual(code, 1, said)
        self.assertIn("docs/research/study/DEVIATIONS.md no longer begins with its text at ", said)
        deviations.unlink()
        self.commit("the departures taken away")
        self.assertIn("docs/research/study/DEVIATIONS.md is gone at ", self.frozen()[1])

    def test_a_branch_behind_the_base_is_held_to_where_it_left_it(self):
        # main froze another design after the branch left it, and added a departure: the branch has neither
        self.git("checkout", "-q", "main")
        freeze(self.repo / "docs" / "research" / "later")
        deviations = self.study / "DEVIATIONS.md"
        deviations.write_text(deviations.read_text(encoding="utf-8") + "- 2026-10-30: on main.\n", encoding="utf-8")
        self.commit("a later design on main")
        self.git("checkout", "-q", "topic")
        self.assertEqual(self.frozen()[0], 0)

    def test_under_github_actions_a_checkout_one_commit_deep_fetches_main_and_elsewhere_it_skips(self):
        freeze(self.study, PREREG + "An edit.\n")
        self.commit("an edit, frozen again")
        work = self.tmp / "work"
        subprocess.run(["git", "clone", "-q", "--depth", "1", "--branch", "topic", f"file://{self.repo}", str(work)], check=True,
                       capture_output=True, timeout=60)
        for key, value in QUIET.items():
            self.git("config", key, value, repo=work)
        self.assertEqual(self.git("for-each-ref", "refs/remotes/origin/main", repo=work), "")
        code, said = self.frozen(base=None, repo=work)
        self.assertEqual(code, 0, said)
        self.assertIn("no origin/main here and not under GitHub Actions, so whether a frozen PREREG moved was not checked", said)
        self.assertFalse((work / ".git" / "FETCH_HEAD").exists(), "nothing is fetched outside GitHub Actions")
        code, said = self.frozen(base=None, repo=work, environ={"GITHUB_ACTIONS": "true"})
        self.assertEqual(code, 1, said)
        self.assertIn("docs/research/study/PREREG.md changed since ", said)
        self.assertTrue((work / ".git" / "FETCH_HEAD").exists())
        # a clone with origin/main reads it and fetches nothing
        self.git("fetch", "-q", "origin", "main:refs/remotes/origin/main", repo=self.tmp / "work")
        code, said = self.frozen(base=None, repo=work)
        self.assertEqual(code, 1, said)

    def test_a_base_that_is_not_there_is_said_and_fails(self):
        code, said = self.frozen(base="no-such-branch")
        self.assertEqual(code, 1)
        self.assertIn("no commit no-such-branch in ", said)

    def test_the_repositorys_own_freeze_holds_against_its_head(self):
        done = subprocess.run([sys.executable, str(ROOT / "flows" / "stage_registry.py"), "frozen", "--base", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)


@unittest.skipIf(NO_CONTRACTS, "needs the train environment (icontract missing)")
class LauncherPreregTest(unittest.TestCase):
    """The launcher refuses before it imports Metaflow, so a datastore is never made."""

    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        shutil.copytree(ROOT / "flows", self.repo / "flows", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "docs" / "research" / "block-smoke", self.repo / "docs" / "research" / "block-smoke")

    def launch(self, *words):
        env = {k: v for k, v in os.environ.items() if k not in ("SLURM_JOB_ID",)}
        env["SCHWINGNET"] = str(self.repo)
        return subprocess.run([sys.executable, str(LAUNCH), *words], cwd=self.repo, env=env, capture_output=True, text=True, timeout=60)

    def test_a_sweep_whose_prereg_moved_ends_with_90_before_any_flow_and_says_so(self):
        with (self.repo / "docs" / "research" / "block-smoke" / "PREREG.md").open("a", encoding="utf-8") as prereg:
            prereg.write("\nAn edit after the freeze.\n")
        done = self.launch("sweep", "--root", str(self.repo / "metaflow"), "--", "--plan", "grid/sweeps/real.json")
        self.assertEqual(done.returncode, 90, done.stderr)
        self.assertRegex(done.stderr, r"^LaunchError: the sweep flow's runs are held to a frozen PREREG \(the owner's rule of 2026-10-29\), "
                                      r"so none was started or resumed: STOP: docs/research/block-smoke/PREREG.md changed since the freeze")
        self.assertRegex(done.stdout, r"^SWEEP_RC=90 [0-9-]+ [0-9:]+\n$")
        self.assertFalse((self.repo / "metaflow").exists())

    def test_a_kind_the_registry_lists_is_the_one_the_launcher_takes(self):
        done = self.launch("deep", "--", "--plan", "p.json")
        self.assertEqual(done.returncode, 64, done.stderr)
        self.assertIn("{bank|catalog|sweep", done.stderr)
        self.assertRegex(done.stdout, r"^LAUNCH_RC=64 ")
        (self.repo / "flows" / "registry.txt").write_text("not a registry\n", encoding="utf-8")
        done = self.launch("sweep", "--", "--plan", "p.json")
        self.assertEqual(done.returncode, 69, done.stderr)
        self.assertIn("the registry of flows cannot be read", done.stderr)


@unittest.skipIf(NO_CONTRACTS, "needs the train environment (icontract missing)")
class LauncherBeatTest(unittest.TestCase):
    """The launcher's heartbeat names the run before its page is begun, and a page that fails, for
    whatever reason, never stops the beat that keeps another launch from resuming a live run."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.launch = load(LAUNCH, "launch_beat_under_test")

    def test_the_beat_goes_on_naming_the_run_whatever_its_page_does(self):
        run_id_file = self.tmp / "run-id"
        run_id_file.write_text("1792902585286456\n", encoding="utf-8")
        page = self.launch.Page(self.tmp / "metaflow", {"flow": "SweepFlow", "kind": "sweep"})
        folder, err = self.tmp / "launches", io.StringIO()
        with mock.patch.object(self.launch.stage_progress, "draw", side_effect=RuntimeError("a view that does not hold")), \
                mock.patch.object(self.launch, "BEAT_SECONDS", 1), redirect_stderr(err):
            with self.launch.Heartbeat(folder, "68974c7ccabf5595", run_id_file, page) as heartbeat:
                beats = []
                for _ in range(40):
                    time.sleep(0.1)
                    if heartbeat.path.is_file():
                        beats.append(json.loads(heartbeat.path.read_text(encoding="utf-8")))
                self.assertTrue(heartbeat.thread.is_alive(), err.getvalue())
        self.assertEqual(beats[-1]["run"], "1792902585286456")
        self.assertGreaterEqual(len({beat["beat"] for beat in beats if beat["run"]}), 2, "the beat went on after the page failed")
        self.assertEqual(page.run, "1792902585286456")
        self.assertEqual(err.getvalue().count("launch: the progress page could not be written: RuntimeError"), 1, err.getvalue())
        self.assertFalse(heartbeat.path.exists(), "the beat is taken away when the flow ends")

    def test_a_flow_that_ended_before_the_heartbeat_named_its_run_still_has_its_head_on_its_page(self):
        root = self.tmp / "metaflow"
        page = self.launch.Page(root, {"flow": "SweepFlow", "kind": "sweep", "key": "68974c7ccabf5595"})
        started = page.started
        page.end({"words": "the launcher exited 0, the flow succeeded"}, "1792902585286456")
        folder = root / "progress" / "SweepFlow" / "1792902585286456"
        head = json.loads((folder / "run.json").read_text(encoding="utf-8"))
        self.assertEqual((head["run"], head["kind"], head["started"]), ("1792902585286456", "sweep", started))
        self.assertEqual(json.loads((folder / "launch.json").read_text(encoding="utf-8"))["words"], "the launcher exited 0, the flow succeeded")
        self.assertRegex((folder / "PROGRESS.txt").read_text(encoding="utf-8"), r"^flow SweepFlow/1792902585286456 sweep: failed, started ")
        # a flow Metaflow never named leaves no page
        unnamed = self.launch.Page(self.tmp / "other", {"flow": "SweepFlow", "kind": "sweep"})
        unnamed.end({"words": "the launcher exited 137, the flow did not succeed"})
        self.assertFalse((self.tmp / "other").exists())


# A flow that sleeps as a row trains, with a child that sleeps too; where STUB_IGNORES_TERM is set
# both ignore SIGTERM, as a process stuck in a call might. It writes both process ids once both run.
SLEEPING_FLOW = """import os, signal, subprocess, sys, time
from pathlib import Path
if os.environ.get("STUB_IGNORES_TERM"):
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"])
Path(os.environ["STUB_PIDS"]).write_text(f"{os.getpid()} {child.pid}\\n", encoding="utf-8")
time.sleep(600)
"""
# The launcher's run_flow in a process of its own, which the test sends the signal to, with a grace
# of one second; what it returned is printed, and written to the file a fifth word names, for a test
# whose reader of the output has gone.
RUN_FLOW = """import importlib.util, json, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("launch_signal_under_test", sys.argv[1])
launch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launch)
launch.STOP_GRACE_SECONDS = 1
code, stopped_by = launch.run_flow([sys.executable, sys.argv[2]], sys.argv[3], sys.argv[3])
said = json.dumps({"code": code, "stopped_by": stopped_by})
if len(sys.argv) > 4:
    Path(sys.argv[4]).write_text(said, encoding="utf-8")
launch.tell(said, sys.stdout)
"""


def alive(pid):
    """Whether a process is there and not a zombie, which a container whose first process reaps
    nothing keeps."""
    try:
        state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except (OSError, IndexError):
        return False
    return state != "Z"


@unittest.skipIf(NO_CONTRACTS, "needs the train environment (icontract missing)")
class LauncherSignalTest(unittest.TestCase):
    """A SIGTERM or SIGINT the launcher is sent while its flow runs reaches every process of the flow,
    and what does not end within the grace is killed, so nothing of the flow outlives its launcher."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / "flow.py").write_text(SLEEPING_FLOW, encoding="utf-8")
        (self.tmp / "run_flow.py").write_text(RUN_FLOW, encoding="utf-8")

    def started(self, output, **env):
        """run_flow in a process of its own, its output to the file object or pipe given, once its
        flow and the flow's child run: (the process, their process ids)."""
        pids_file = self.tmp / "pids"
        for left in (pids_file, self.tmp / "said.json"):  # an earlier start's, in a test that starts twice
            left.unlink(missing_ok=True)
        process = subprocess.Popen([sys.executable, str(self.tmp / "run_flow.py"), str(LAUNCH), str(self.tmp / "flow.py"), str(self.tmp),
                                    str(self.tmp / "said.json")], env=dict(os.environ, STUB_PIDS=str(pids_file), **env), stdout=output,
                                   stderr=output, text=True)
        self.addCleanup(process.kill)
        for _ in range(300):
            if pids_file.is_file() and pids_file.read_text(encoding="utf-8").endswith("\n"):
                break
            time.sleep(0.1)
        pids = [int(word) for word in pids_file.read_text(encoding="utf-8").split()]
        self.addCleanup(lambda: [os.kill(pid, signal.SIGKILL) for pid in pids if alive(pid)])
        return process, pids

    def all_ended(self, pids):
        for _ in range(50):
            if not any(alive(pid) for pid in pids):
                break
            time.sleep(0.1)
        self.assertEqual([pid for pid in pids if alive(pid)], [], "no process of the flow outlives the launcher")

    def stopped(self, signum, **env):
        process, pids = self.started(subprocess.PIPE, **env)
        process.send_signal(signum)
        out, err = process.communicate(timeout=60)
        self.assertEqual(process.returncode, 0, err)
        self.all_ended(pids)
        return json.loads(out.splitlines()[-1]), err

    def stopped_with_no_reader(self, signum, **env):
        """As stopped, with the reader of the launcher's output gone before the signal comes, as a
        pipe's reader, tee in a job's script, goes with its job: every line the launcher says then
        meets a broken pipe."""
        reader, writer = os.pipe()
        try:
            process, pids = self.started(writer, **env)
        finally:
            os.close(writer)
        os.close(reader)
        process.send_signal(signum)
        self.assertEqual(process.wait(timeout=60), 0, "the launcher's stop ran to its end whatever its words met")
        self.all_ended(pids)
        return json.loads((self.tmp / "said.json").read_text(encoding="utf-8"))

    def test_a_sigterm_reaches_every_process_of_the_flow(self):
        said, err = self.stopped(signal.SIGTERM)
        self.assertEqual(said, {"code": -signal.SIGTERM, "stopped_by": signal.SIGTERM})
        self.assertIn("launch: SIGTERM: passed on to every process of the flow, which has 1 s to end", err)
        self.assertNotIn("so they were killed", err)
        self.assertEqual(self.launch_exit(said), 143)

    def test_a_sigint_is_passed_on_as_well(self):
        said, err = self.stopped(signal.SIGINT)
        self.assertEqual(said["stopped_by"], signal.SIGINT)
        self.assertIn("launch: SIGINT: passed on", err)
        self.assertEqual(self.launch_exit(said), 130)

    def test_a_flow_that_does_not_end_within_the_grace_is_killed(self):
        said, err = self.stopped(signal.SIGTERM, STUB_IGNORES_TERM="yes")
        self.assertEqual(said, {"code": -signal.SIGKILL, "stopped_by": signal.SIGTERM})
        self.assertIn("launch: the flow's processes did not end within 1 s, so they were killed", err)

    def test_a_reader_gone_before_the_signal_never_cuts_the_stop_short(self):
        # its message met a broken pipe before the signal was passed on, so the flow ran on unstopped
        # and the launcher fell out of its stop with its beat taken away (the review of the fixes)
        self.assertEqual(self.stopped_with_no_reader(signal.SIGTERM), {"code": -signal.SIGTERM, "stopped_by": signal.SIGTERM})
        # and where the flow ignores the signal, its message no longer comes before the kill either
        self.assertEqual(self.stopped_with_no_reader(signal.SIGTERM, STUB_IGNORES_TERM="yes"),
                         {"code": -signal.SIGKILL, "stopped_by": signal.SIGTERM})

    def test_a_line_the_launcher_cannot_write_is_dropped_and_its_stream_written_nowhere_after(self):
        launch = load(LAUNCH, "launch_tell_under_test")
        reader, writer = os.pipe()
        os.close(reader)
        stream = os.fdopen(writer, "w", encoding="utf-8")
        self.addCleanup(lambda: stream.close() if not stream.closed else None)
        launch.tell("a line nobody reads", stream)
        launch.tell("and another", stream)
        stream.flush()
        self.assertEqual(os.path.realpath(f"/proc/self/fd/{stream.fileno()}"), os.devnull)

    def launch_exit(self, said):
        return load(LAUNCH, "launch_exit_under_test").exit_code(said["code"], None, said["stopped_by"])


@unittest.skipIf(NO_METAFLOW, "needs the train environment (metaflow missing)")
class ClaimReportTest(unittest.TestCase):
    """stage.claim_report with the real tools/report.py on a run folder that holds only RUN.json, which
    the tool reports with every item it cannot answer counted as missing."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / "flows"))
        with warnings.catch_warnings():  # what Metaflow's own imports warn of is not this test's
            warnings.simplefilter("ignore", DeprecationWarning)
            cls.stage = load(ROOT / "flows" / "stage.py", "stage_under_test")
        cls.stage.REPO = ROOT

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(str(ROOT / "flows"))

    def setUp(self):
        self.folder = Path(tempfile.mkdtemp()) / "row"
        self.addCleanup(shutil.rmtree, self.folder.parent, ignore_errors=True)
        self.folder.mkdir()
        (self.folder / "RUN.json").write_text(json.dumps({"run_id": "row-1"}), encoding="utf-8")

    def check(self):
        return self.stage.report_tool("check", self.folder).returncode

    def test_a_report_the_run_left_current_is_current_as_the_run_wrote_it_and_is_not_written_again(self):
        self.assertEqual(self.stage.report_tool("write", self.folder).returncode, 0)
        before = {name: (self.folder / name).stat().st_mtime_ns for name in ("REPORT.md", "claim.json", "reforms.json")}
        ok, line = self.stage.claim_report(self.folder)
        self.assertTrue(ok, line)
        self.assertRegex(line, r"^row: current as the run wrote it; CLAIM 2024: \d+ met, \d+ declared, \d+ not applicable, \d+ missing; REFORMS: ")
        self.assertEqual({name: (self.folder / name).stat().st_mtime_ns for name in before}, before)

    def test_a_folder_with_no_report_has_it_written_at_the_end_and_says_so(self):
        ok, line = self.stage.claim_report(self.folder)
        self.assertTrue(ok, line)
        self.assertRegex(line, r"^row: current, written at the end since the run left none; CLAIM 2024: ")
        self.assertEqual(self.check(), 0)

    def test_a_report_the_run_left_stale_is_written_anew_and_is_not_current(self):
        # the run's files changed after its report: what a write gives now differs from what it left
        self.assertEqual(self.stage.report_tool("write", self.folder).returncode, 0)
        (self.folder / "RUN.json").write_text(json.dumps({"run_id": "row-2"}), encoding="utf-8")
        self.assertEqual(self.check(), 1)
        ok, line = self.stage.claim_report(self.folder)
        self.assertFalse(ok, line)
        self.assertEqual(line, f"row: NOT CURRENT as the run wrote it, so written anew; why: {self.folder}: REPORT.md, claim.json, "
                               f"reforms.json not what the run gives; run python3 tools/report.py write --run {self.folder}")
        self.assertEqual(self.check(), 0, "the folder holds the current report once end has run")

    def test_a_folder_that_is_no_run_is_not_written_and_says_why(self):
        (self.folder / "RUN.json").unlink()
        ok, line = self.stage.claim_report(self.folder)
        self.assertFalse(ok, line)
        self.assertEqual(line, f"row: NOT WRITTEN at the end; why: report: {self.folder}: no RUN.json, so this is not a run folder")


@unittest.skipIf(NO_METAFLOW, "needs the train environment (metaflow missing)")
class BeatTest(unittest.TestCase):
    """stage.Beat and run_watched on a page under a scratch root: a step's line stays fresh while its
    work runs, and nothing the page does ever fails the step."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / "flows"))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            cls.stage = load(ROOT / "flows" / "stage.py", "stage_beat_under_test")

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(str(ROOT / "flows"))

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def beat(self):
        """A Beat as a row's step makes one, without the Metaflow task that names it."""
        beat = object.__new__(self.stage.Beat)
        beat.root, beat.flow, beat.run, beat.steps, beat.said = str(self.root), "SweepFlow", "1", ["start", "first", "end"], False
        beat.task = {"step": "first", "task": "3", "label": "row", "state": "running", "attempt": 0, "started": progress.utc_now(),
                     "lines": []}
        return beat

    def task_file(self):
        return json.loads((self.root / "progress" / "SweepFlow" / "1" / "tasks" / "first-3.json").read_text(encoding="utf-8"))

    def test_a_line_that_does_not_change_still_keeps_the_task_fresh(self):
        # an epoch longer than SILENT_SECONDS says the same line all along; the task is written at every tick
        beat = self.beat()
        with mock.patch.object(beat, "write", wraps=beat.write) as write:
            code, out, _ = self.stage.run_watched([sys.executable, "-c", "import time; time.sleep(1.2); print('trained')"], beat,
                                                  lambda: "Last epoch: epoch 0 of 2.", every=0.25)
        self.assertEqual((code, out), (0, "trained\n"))
        self.assertGreaterEqual(write.call_count, 4)
        self.assertEqual(self.task_file()["lines"], ["Last epoch: epoch 0 of 2."])
        beat.task["updated"] = "2026-01-01T00:00:00Z"
        beat.tick(lambda: "Last epoch: epoch 0 of 2.")
        updated = self.task_file()["updated"]
        self.assertNotEqual(updated, "2026-01-01T00:00:00Z")
        self.assertEqual(progress.view_of_folder(self.root, "SweepFlow", "1", now=progress.parse_time(updated) + 60)["state"], "running")

    def test_a_line_with_line_breaks_is_kept_as_one_line(self):
        beat = self.beat()
        beat.task["label"] = "row\nx"
        beat.say("Outcome: ran,\nmatched the check.\r\n")
        self.assertEqual(self.task_file()["lines"], ["Outcome: ran, matched the check."])
        text = (self.root / "progress" / "SweepFlow" / "1" / "PROGRESS.txt").read_text(encoding="utf-8")
        self.assertIn("task first row x: running; Outcome: ran, matched the check.\n", text)

    def test_a_page_that_cannot_be_drawn_or_a_line_that_cannot_be_read_never_fails_the_step(self):
        beat, err = self.beat(), io.StringIO()
        with mock.patch.object(self.stage.progress, "draw", side_effect=RuntimeError("a view that does not hold")), redirect_stderr(err):
            beat.write()
            beat.say("a line")
            beat.tick(lambda: 1 / 0)
        self.assertEqual(err.getvalue().count("the progress page could not be written"), 1, err.getvalue())
        self.assertIn("RuntimeError: a view that does not hold", err.getvalue())
        self.assertEqual(self.task_file()["lines"], ["a line"], "the task's own file is written before the page is drawn")
        err = io.StringIO()
        with mock.patch.object(self.stage, "current", mock.Mock(flow_name="SweepFlow", run_id="1")), \
                mock.patch.dict(os.environ, {"METAFLOW_DATASTORE_SYSROOT_LOCAL": str(self.root)}), \
                mock.patch.object(self.stage.progress, "draw", side_effect=KeyError("steps")), redirect_stderr(err):
            self.stage.finish(1, [(False, "row: NOT CURRENT")])
        self.assertIn("the progress page could not be written (KeyError", err.getvalue())
        self.assertEqual(json.loads((self.root / "progress" / "SweepFlow" / "1" / "result.json").read_text(encoding="utf-8"))["lines"],
                         ["row: NOT CURRENT"])


def a_run(root, flow="SweepFlow", run="1792902585286456", origin=None):
    """A run's progress folder as the launcher and its steps leave it midway: start done, two of
    three rows done, one running, the end not yet run."""
    head = {"flow": flow, "run": run, "kind": "sweep", "key": "68974c7ccabf5595", "commit": "35a4b6f", "code": "0123456789ab",
            "prereg": "docs/research/block-smoke/PREREG.md", "prereg_sha256": "5779e79a2a7c" + "0" * 52, "origin": origin,
            "started": "2026-10-29T03:00:00Z"}
    progress.write_head(root, head)
    progress.write_graph(root, flow, run, ["start", "fan_first", "first", "join_first", "end"])
    now = progress.utc_now()
    tasks = [("start", "1", "prepare", "done", ["state <smoke>, 3 rows first, 0 warm starts after"]),
             ("fan_first", "2", None, "done", []),
             ("first", "3", "resnet18-64px-3d291b87", "done", ["Outcome: ran, matched the check."]),
             ("first", "4", "resnet34-32px-b2928840", "done", ["Outcome: ran, matched the check."]),
             ("first", "5", "resnet50-96px-6133c32a", "running", ["Last epoch: epoch 1 of 2, train loss 0.25."])]
    for step, task, label, state, lines in tasks:
        progress.write_task(root, flow, run, {"step": step, "task": task, "label": label, "state": state, "attempt": 0,
                                              "started": now, "updated": now, "lines": lines})
    return progress.draw(root, flow, run)


class ProgressPageTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def test_a_running_run_draws_its_page_its_short_lines_and_the_list_of_runs(self):
        view = a_run(self.root)
        folder = self.root / "progress" / "SweepFlow" / "1792902585286456"
        self.assertEqual(view["state"], "running")
        self.assertEqual([(step["name"], step["state"]) for step in view["steps"]],
                         [("start", "done"), ("fan_first", "done"), ("first", "running"), ("join_first", "waiting"), ("end", "waiting")])
        lines = (folder / "PROGRESS.txt").read_text(encoding="utf-8").splitlines()
        self.assertRegex(lines[0], r"^flow SweepFlow/1792902585286456 sweep: running, started 2026-10-29 03:00:00 UTC, updated ")
        self.assertEqual(lines[1], "run: key 68974c7ccabf5595, commit 35a4b6f, code 0123456789ab, "
                                   "PREREG docs/research/block-smoke/PREREG.md sha256 5779e79a2a7c")
        self.assertIn("step first: running; 2 done, 1 running of 3", lines)
        self.assertIn("task first resnet50-96px-6133c32a: running; Last epoch: epoch 1 of 2, train loss 0.25.", lines)
        self.assertIn("step end: waiting", lines)
        page = (folder / "index.html").read_text(encoding="utf-8")
        self.assertIn('<meta http-equiv="refresh" content="30">', page)
        self.assertIn("resnet50-96px-6133c32a", page)
        self.assertIn("Not written yet: the end step writes it.", page)
        overview = (self.root / "progress" / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="SweepFlow/1792902585286456/index.html"', overview)

    def test_the_end_step_and_the_launcher_close_the_page_with_the_verdict_and_the_report(self):
        a_run(self.root)
        progress.write_result(self.root, "SweepFlow", "1792902585286456",
                              {"verdict": 1, "lines": ["resnet18-64px-3d291b87: NOT CURRENT, why: REPORT.md not what the run gives",
                                                       "resnet34-32px-b2928840: current as the run wrote it"],
                               "reports": 2, "not_current": 1})
        progress.write_launch(self.root, "SweepFlow", "1792902585286456", {"words": "the launcher exited 1, the flow succeeded"})
        view = progress.draw(self.root, "SweepFlow", "1792902585286456")
        self.assertEqual((view["state"], view["verdict"]), ("failed", 1))
        lines = progress.text_lines(view)
        # how the run ended comes right after the head, before any step
        self.assertEqual(lines[2:7], ["verdict: 1", "ended: the launcher exited 1, the flow succeeded",
                                      "reports: 1 of 2 current, 1 not current or not written",
                                      "report: resnet18-64px-3d291b87: NOT CURRENT, why: REPORT.md not what the run gives",
                                      "report: resnet34-32px-b2928840: current as the run wrote it"])
        self.assertEqual(lines[7], "step start: done")
        page = (self.root / "progress" / "SweepFlow" / "1792902585286456" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("http-equiv", page)
        self.assertIn("1, not all well", page)
        self.assertIn("<p>1 of 2 current, 1 not current or not written</p>", page)

    def test_a_whole_plans_run_fits_the_lines_the_gates_status_keeps_with_its_end_first(self):
        # a smoke plan of 27 rows, 25 first and 2 warm starts, with one report not current: the
        # status keeps the first FLOW_PROGRESS_LINES of the file, which once cut the verdict away
        kept = int(re.search(r"FLOW_PROGRESS_LINES=(\d+)", (ROOT / "grid" / "gate.sh").read_text(encoding="utf-8")).group(1))
        flow, run = "SweepFlow", "1"
        progress.write_head(self.root, {"flow": flow, "run": run, "kind": "sweep", "key": "0" * 16, "started": progress.utc_now()})
        progress.write_graph(self.root, flow, run, ["start", "fan_first", "first", "join_first", "middle", "fan_second", "second",
                                                    "join_second", "end"])

        def task(step, number, label, lines, state="done"):
            progress.write_task(self.root, flow, run, {"step": step, "task": str(number), "label": label, "state": state, "lines": lines})

        task("start", 1, "prepare", ["state x, 25 rows first, 2 warm starts after"])
        for number, step in ((2, "fan_first"), (50, "join_first"), (51, "middle"), (52, "fan_second"), (70, "join_second")):
            task(step, number, None, [])
        for n in range(25):
            task("first", 10 + n, f"row{n:02d}", ["Outcome: ran, matched the check."], "failed" if n == 24 else "done")
        for n in range(2):
            task("second", 60 + n, f"warm{n}", ["Outcome: ran, matched the check."])
        task("end", 71, "results", ["{...}, faults 1, verdict 1"])
        reports = [f"row{n:02d}: current as the run wrote it" for n in range(23)] + ["warm0: current", "warm1: current"]
        progress.write_result(self.root, flow, run, {"verdict": 1, "lines": ["row03: NOT CURRENT as the run wrote it, so written anew; why: x",
                                                                            *reports], "reports": 26, "not_current": 1})
        progress.write_launch(self.root, flow, run, {"words": "the launcher exited 1, the flow succeeded"})
        progress.draw(self.root, flow, run)
        lines = (self.root / "progress" / flow / run / "PROGRESS.txt").read_text(encoding="utf-8").splitlines()
        self.assertLessEqual(len(lines), kept, lines)
        self.assertEqual(lines[2:6], ["verdict: 1", "ended: the launcher exited 1, the flow succeeded",
                                      "reports: 25 of 26 current, 1 not current or not written",
                                      "report: row03: NOT CURRENT as the run wrote it, so written anew; why: x"])
        self.assertIn(f"({26 - progress.REPORTS_SHOWN} more report lines; the page on the grid lists them)", lines)
        # a step's failed task comes first among the few shown, and the rest are counted
        first = lines.index("step first: failed; 24 done, 1 failed of 25")
        self.assertEqual(lines[first + 1], "task first row24: failed; Outcome: ran, matched the check.")
        self.assertEqual(lines[first + 1 + progress.TASKS_SHOWN], f"({25 - progress.TASKS_SHOWN} more tasks of first; the page on the grid lists them)")
        self.assertIn("task end results: done; {...}, faults 1, verdict 1", lines)
        # the page on the grid lists every row and every report
        page = (self.root / "progress" / flow / run / "index.html").read_text(encoding="utf-8")
        self.assertIn("row22: current as the run wrote it", page)
        self.assertIn("<td>row13</td>", page)

    def test_a_run_whose_files_stopped_moving_is_shown_silent_and_a_failed_launch_failed(self):
        view = a_run(self.root)
        later = progress.parse_time(view["updated"]) + progress.SILENT_SECONDS + 1
        self.assertEqual(progress.view_of_folder(self.root, "SweepFlow", "1792902585286456", now=later)["state"], "silent")
        progress.write_launch(self.root, "SweepFlow", "1792902585286456", {"words": "the launcher exited 137, the flow did not succeed"})
        self.assertEqual(progress.draw(self.root, "SweepFlow", "1792902585286456")["state"], "failed")

    def test_a_resumed_run_shows_the_steps_it_cloned_from_its_origin(self):
        a_run(self.root, run="1")
        progress.write_head(self.root, {"flow": "SweepFlow", "run": "2", "kind": "sweep", "origin": "1", "started": progress.utc_now()})
        # before any task of the resume has run, its page shows the origin's steps in the origin's order
        view = progress.draw(self.root, "SweepFlow", "2")
        self.assertEqual([(step["name"], step["state"]) for step in view["steps"]],
                         [("start", "cloned"), ("fan_first", "cloned"), ("first", "running"), ("join_first", "waiting"), ("end", "waiting")])
        progress.write_task(self.root, "SweepFlow", "2", {"step": "first", "task": "9", "label": "resnet50-96px-6133c32a", "state": "running",
                                                         "lines": []})
        view = progress.draw(self.root, "SweepFlow", "2")
        steps = {step["name"]: step for step in view["steps"]}
        self.assertEqual(steps["start"]["state"], "cloned")
        self.assertEqual(steps["first"]["state"], "running")
        # the row this run runs again is its own; the two its origin finished are cloned, each once
        self.assertEqual((steps["first"]["total"], steps["first"]["counts"]["cloned"], steps["first"]["counts"]["running"]), (3, 2, 1))

    def test_a_resume_of_a_resume_counts_each_row_once_from_the_newest_run_that_ran_it(self):
        # run 1 cut in its third row; run 2 cloned the first two, ran the third and was cut in the
        # join; run 3 cloned the whole foreach, two rows from run 1 and the third from run 2
        graph = ["start", "fan_first", "first", "join_first", "end"]

        def task(run, step, number, label, state):
            progress.write_task(self.root, "SweepFlow", run, {"step": step, "task": str(number), "label": label, "state": state, "lines": []})

        for run, origin in (("1", None), ("2", "1"), ("3", "2")):
            progress.write_head(self.root, {"flow": "SweepFlow", "run": run, "kind": "sweep", "origin": origin})
            progress.write_graph(self.root, "SweepFlow", run, graph)
        task("1", "start", 1, "prepare", "done")
        task("1", "fan_first", 2, None, "done")
        for number, label, state in ((3, "a", "done"), (4, "b", "done"), (5, "c", "running")):
            task("1", "first", number, label, state)
        task("1", "join_first", 6, None, "running")
        task("2", "first", 9, "c", "done")
        task("2", "join_first", 10, None, "running")
        steps = {step["name"]: step for step in progress.draw(self.root, "SweepFlow", "2")["steps"]}
        self.assertEqual((steps["first"]["state"], steps["first"]["total"]), ("done", 3))
        self.assertEqual((steps["first"]["counts"]["done"], steps["first"]["counts"]["cloned"]), (1, 2))
        self.assertEqual(steps["join_first"]["total"], 1, "a step that is no foreach is this run's alone where it has run it")
        task("3", "join_first", 20, None, "done")
        task("3", "end", 21, "results", "running")
        steps = {step["name"]: step for step in progress.draw(self.root, "SweepFlow", "3")["steps"]}
        self.assertEqual([(name, steps[name]["state"], steps[name]["total"]) for name in graph],
                         [("start", "cloned", 1), ("fan_first", "cloned", 1), ("first", "cloned", 3), ("join_first", "done", 1),
                          ("end", "running", 1)])
        self.assertEqual(sorted(task["label"] for task in steps["first"]["tasks"]), ["a", "b", "c"])

    def test_the_short_lines_read_back_into_the_view_the_page_is_drawn_from(self):
        view = a_run(self.root)
        back = progress.view_of_lines(progress.text_lines(view) + ["(a line of another shape)"])
        self.assertEqual((back["flow"], back["run"], back["kind"], back["state"]), ("SweepFlow", "1792902585286456", "sweep", "running"))
        self.assertEqual([(s["name"], s["state"], s["total"]) for s in back["steps"]], [(s["name"], s["state"], s["total"]) for s in view["steps"]])
        first = next(step for step in back["steps"] if step["name"] == "first")
        self.assertEqual(first["counts"]["done"], 2)
        self.assertEqual([task["label"] for task in first["tasks"]][0], "resnet50-96px-6133c32a")
        self.assertEqual(back["notes"], ["(a line of another shape)"])

    def test_every_value_is_one_short_line_whatever_a_task_file_holds(self):
        a_run(self.root)
        progress.write_task(self.root, "SweepFlow", "1792902585286456", {"step": "first", "task": "6", "label": "two\nlines",
                                                                        "state": "done", "lines": ["a fault\nwhy: x"]})
        progress.write_result(self.root, "SweepFlow", "1792902585286456", {"verdict": 1, "lines": ["row: NOT CURRENT\nwhy: y"]})
        lines = progress.text_lines(progress.draw(self.root, "SweepFlow", "1792902585286456"))
        self.assertIn("task first two lines: done; a fault why: x", lines)
        self.assertIn("report: row: NOT CURRENT why: y", lines)

    def test_a_file_is_written_beside_itself_under_the_host_and_the_process(self):
        replaced = []
        real_replace = os.replace
        with mock.patch.object(progress.os, "replace", side_effect=lambda part, path: replaced.append(Path(part).name) or real_replace(part, path)), \
                mock.patch.object(progress.socket, "gethostname", return_value="node12.grid"):
            progress.write_whole(self.root / "index.html", "a page\n")
        self.assertEqual(replaced, [f".index.html.node12.grid-{os.getpid()}.part"])
        self.assertEqual((self.root / "index.html").read_text(encoding="utf-8"), "a page\n")

    def test_a_task_that_cannot_write_its_page_never_fails_the_page_of_another(self):
        a_run(self.root)
        (self.root / "progress" / "SweepFlow" / "1792902585286456" / "tasks" / "broken.json").write_text("{not json", encoding="utf-8")
        self.assertEqual(progress.draw(self.root, "SweepFlow", "1792902585286456")["state"], "running")


class OffTheGridPageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def status_answer(self):
        root = self.tmp / "metaflow"
        view = a_run(root)
        lines = progress.text_lines(view)
        return "\n".join(["## space on the lab volume (CephFS ceph.dir.rbytes; GB rounded up)", "  data 12",
                          "## flow sweep 1792902585286456, progress (2026-10-29 03:05 UTC)", *(f"  {line}" for line in lines),
                          "## the gate's newest jobs (sacct): id, what, state", "  4242 sweep:real sweep RUNNING"]) + "\n"

    def test_the_page_is_drawn_from_the_status_answers_section_and_nothing_else(self):
        status = self.tmp / "status.txt"
        status.write_text(self.status_answer(), encoding="utf-8")
        out = self.tmp / "page.html"
        done = subprocess.run([sys.executable, str(ROOT / "tools" / "progress_page.py"), str(status), "--out", str(out)],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        page = out.read_text(encoding="utf-8")
        self.assertIn("SweepFlow 1792902585286456", page)
        self.assertIn("resnet50-96px-6133c32a", page)
        self.assertIn("its section of 2026-10-29 03:05 UTC", page)
        self.assertNotIn("4242", page)
        listed = subprocess.run([sys.executable, str(ROOT / "tools" / "progress_page.py"), str(status), "--list"],
                                capture_output=True, text=True, timeout=60)
        self.assertRegex(listed.stdout, r"^1792902585286456 sweep \(2026-10-29 03:05 UTC\), \d+ lines\n$")
        missing = subprocess.run([sys.executable, str(ROOT / "tools" / "progress_page.py"), str(status), "--run", "9", "--out", str(out)],
                                 capture_output=True, text=True, timeout=60)
        self.assertEqual(missing.returncode, 1)
        self.assertIn("no flow's progress of run 9", missing.stderr)


if __name__ == "__main__":
    unittest.main()
