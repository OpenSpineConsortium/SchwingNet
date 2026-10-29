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
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAUNCH = ROOT / "flows" / "launch.py"
# The launcher imports the contracts of schwingnet.pipeline, which the plain python of the required
# check lacks; its refusals are tested where the train environment is, as tests/test_flows.py is.
NO_CONTRACTS = importlib.util.find_spec("icontract") is None


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


registry = load(ROOT / "flows" / "stage_registry.py", "stage_registry_under_test")
progress = load(ROOT / "flows" / "stage_progress.py", "stage_progress_under_test")
page_tool = load(ROOT / "tools" / "progress_page.py", "progress_page_under_test")

PREREG = "# A design\n\nCovers: alpha, beta\n\n## 1. The question\n\nWhether it runs.\n"


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
        (self.repo / "flows" / "deep.py").write_text("class DeepFlow(FlowSpec):\n    pass\n", encoding="utf-8")
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
        self.assertEqual(registry.covered(self.repo / "docs" / "deep" / "PREREG.md"), ["alpha", "beta"])
        self.assertEqual(registry.frozen_for("deep", "beta", self.repo), ("docs/deep/PREREG.md", self.digest))
        with self.assertRaisesRegex(registry.PreregError, "covers alpha, beta, not trials: a run of trials waits for a PREREG of its own"):
            registry.frozen_for("deep", "trials", self.repo)

    def test_the_sweeps_prereg_covers_the_three_smoke_plans_and_not_the_trials(self):
        for plan in ("synthetic", "real", "two_source"):
            self.assertEqual(registry.frozen_for("sweep", plan, ROOT)[0], "docs/research/block-smoke/PREREG.md")
        with self.assertRaises(registry.PreregError):
            registry.frozen_for("sweep", "trials", ROOT)

    def test_each_line_is_held_to_its_class_its_script_and_its_shape(self):
        (self.repo / "grid" / "deep.sbatch").write_text("python tools/train.py\n", encoding="utf-8")
        self.assertEqual(registry.problems(self.repo), ["deep: grid/deep.sbatch names no flows/launch.py deep"])
        (self.repo / "grid" / "deep.sbatch").write_text('exec python "$REPO/flows/launch.py" deeper\n', encoding="utf-8")
        self.assertEqual(registry.problems(self.repo), ["deep: grid/deep.sbatch names no flows/launch.py deep"])
        self.write_registry("deep OtherFlow DEEP_RC deep.sbatch docs/deep/PREREG.md")
        self.assertIn("deep: flows/deep.py defines no class OtherFlow", registry.problems(self.repo))
        for line, words in (("deep DeepFlow DEEP_RC deep.sbatch", "five words"),
                            ("deep DeepFlow DEEP deep.sbatch -", "is no word"),
                            ("deep DeepFlow DEEP_RC deep.sbatch ../PREREG.md", "a path to a PREREG.md"),
                            ("deep DeepFlow DEEP_RC deep.sbatch -\ndeep DeepFlow DEEP_RC other.sbatch -", "listed twice")):
            self.write_registry(line)
            with self.assertRaisesRegex(registry.RegistryError, words):
                registry.entries(self.repo)

    def test_the_command_line_prints_the_prereg_or_stops_with_90(self):
        done = subprocess.run([sys.executable, str(ROOT / "flows" / "stage_registry.py"), "prereg", "sweep"], cwd=ROOT,
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertRegex(done.stdout, r"^docs/research/block-smoke/PREREG\.md [0-9a-f]{64}\n$")
        done = subprocess.run([sys.executable, str(ROOT / "flows" / "stage_registry.py"), "check"], cwd=ROOT,
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
                              {"verdict": 1, "lines": ["resnet18-64px-3d291b87: NOT CURRENT, why: REPORT.md not what the run gives"]})
        progress.write_launch(self.root, "SweepFlow", "1792902585286456", {"words": "the launcher exited 1, the flow succeeded"})
        view = progress.draw(self.root, "SweepFlow", "1792902585286456")
        self.assertEqual((view["state"], view["verdict"]), ("failed", 1))
        lines = progress.text_lines(view)
        self.assertEqual(lines[-3:], ["report: resnet18-64px-3d291b87: NOT CURRENT, why: REPORT.md not what the run gives",
                                      "verdict: 1", "ended: the launcher exited 1, the flow succeeded"])
        page = (self.root / "progress" / "SweepFlow" / "1792902585286456" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("http-equiv", page)
        self.assertIn("1, not all well", page)

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
        self.assertEqual(steps["first"]["total"], 1, "a step this run has a task of shows its own, not its origin's")

    def test_the_short_lines_read_back_into_the_view_the_page_is_drawn_from(self):
        view = a_run(self.root)
        back = progress.view_of_lines(progress.text_lines(view) + ["(a line of another shape)"])
        self.assertEqual((back["flow"], back["run"], back["kind"], back["state"]), ("SweepFlow", "1792902585286456", "sweep", "running"))
        self.assertEqual([(s["name"], s["state"], s["total"]) for s in back["steps"]], [(s["name"], s["state"], s["total"]) for s in view["steps"]])
        first = next(step for step in back["steps"] if step["name"] == "first")
        self.assertEqual(first["counts"]["done"], 2)
        self.assertEqual([task["label"] for task in first["tasks"]][0], "resnet50-96px-6133c32a")
        self.assertEqual(back["notes"], ["(a line of another shape)"])

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
