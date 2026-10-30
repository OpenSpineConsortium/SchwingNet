"""The auto-anatomist screen's flow (flows/autoanatomist.py), run for real through flows/launch.py.

Each test runs the launcher with a datastore of its own over a scratch repository that holds the
flow, the stage helpers, the registry, the frozen PREREG with the plans it covers, the split and the
test lists, the real join (tools/autoanatomist_join.py), the real report (tools/report.py with
tools/autoanatomist_report.py) and a stand-in for tools/autoanatomist_trial.py that writes the entry
a trial of the plan writes, with no JAX and no card. So the smoke's two trials and its join, the
PREREG and the plan's bytes held at start, the record, the report and a failed trial are tested in
seconds before a GPU job spends the owner's count. Metaflow is in the train feature only, so CI's
python, which has none, skips the file; run it with the train-cpu environment:

    pixi run -e train-cpu python -m unittest tests.test_autoanatomist_flow -v
"""

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAUNCH = ROOT / "flows" / "launch.py"
NEEDED = ("metaflow", "beartype", "icontract", "pydantic", "matplotlib")
MISSING = [name for name in NEEDED if importlib.util.find_spec(name) is None]
TIMEOUT = 600
PREREG = "docs/research/autoanatomist-screen/PREREG.md"
PLAN = "grid/screens/gold3_latent_smoke.json"
# What the scratch repository copies whole: the flow and what it runs, and the report with what it reads.
COPIED = ("flows/autoanatomist.py", "flows/stage.py", "flows/stage_progress.py", "flows/stage_registry.py",
          "flows/registry.txt", "src/schwingnet/__init__.py", "src/schwingnet/autoanatomist_screen.py",
          "src/schwingnet/autoanatomist_search.py",
          "tools/autoanatomist_join.py", "tools/run_code.py", "tools/report.py", "tools/realism_report.py",
          "tools/autoanatomist_report.py", "data/reporting/checklists.json", "data/reporting/study.json",
          "data/reporting/studies/flux-realism.json", "data/reporting/studies/drr-domain-gap.json",
          "data/reporting/studies/autoanatomist-screen.json", "data/licences.json", "data/splits/rule.json",
          "data/splits/test-persons.json", "data/splits/latent-prior-test-reserve.json",
          "data/splits/latent-prior-repeat-groups.json", "grid/autoanatomist.sbatch", "grid/screens/gold3_latent_smoke.json",
          "grid/screens/gold3_latent_screen.json", PREREG, PREREG + ".sha256")

# A stand-in for tools/autoanatomist_trial.py: the trial the words name, its entry written as the
# real one writes it and checked by the package's own entry_problems, so the real join reads it; the
# trial FLOW_TEST_FAIL names fails as a card fault would, leaving its why. Its calls go to FLOW_TEST_CALLS.
STUB_TRIAL = r'''"""A stand-in for tools/autoanatomist_trial.py in tests/test_autoanatomist_flow.py."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[0] = str(ROOT / "src")
sys.path.insert(1, str(ROOT / "vendor" / "beethoven-qa" / "src"))
from schwingnet import autoanatomist_screen as screen  # noqa: E402

words = sys.argv[1:]


def value(flag):
    return words[words.index(flag) + 1]


plan = screen.plan_of(json.loads(Path(value("--plan")).read_text(encoding="utf-8")))
trial = screen.trials(plan)[int(value("--task"))]
folder = Path(value("--out")) / "trials" / trial.id
folder.mkdir(parents=True, exist_ok=True)
with open(os.environ["FLOW_TEST_CALLS"], "a", encoding="utf-8") as calls:
    calls.write(f"trial {trial.id} {len(screen.trials(plan))} {value('--tasks')}\n")
(folder / "PROGRESS.txt").write_text(f"{trial.id}: epoch {plan.epochs} of {plan.epochs}\n", encoding="utf-8")
if os.environ.get("FLOW_TEST_FAIL") == trial.id:
    (folder / "why.txt").write_text("the stand-in's card fault\n", encoding="utf-8")
    print(f"{trial.id}: the card faulted", file=sys.stderr)
    sys.exit(1)
per_epoch = screen.steps_per_epoch(screen.train_count(plan), plan.batch)
distance = 8.0 if trial.arm == plan.null else 6.0
readings = [{"epoch": e, "steps": e * per_epoch, "loss": 1.0 / e, "dice": 0.5, "distance_mm": distance,
             "surface_missing": 0, "centroid_mm": 3.0, "name_accuracy": None} for e in screen.evaluation_epochs(plan)]
entry = {"version": screen.ENTRY_VERSION, "screen": plan.screen, "trial": trial.id, "arm": trial.arm,
         "seed": trial.seed, "words": list(trial.words), "steps": screen.total_steps(plan), "epochs": readings,
         "final": {key: readings[-1][key] for key in screen.FINAL_KEYS}, "seconds": 10.0, "seconds_per_crop": 0.01,
         "train_rows": screen.train_count(plan), "validation_rows": len(plan.rows) - screen.train_count(plan)}
problems = screen.entry_problems(entry, trial, plan)
if problems:
    sys.exit("the stand-in's entry does not hold: " + problems[0])
environment = {"host": "stand-in", "python": sys.version.split()[0], "backend": "cpu", "devices": ["none"],
               "packages": {"jax": "stand-in"}, "train_and_read_seconds": 10.0}
for name, record in (("entry.json", entry), ("environment.json", environment)):
    (folder / name).write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
print(f"{trial.id}: {plan.measure} {distance}")
'''


def base_env(**extra):
    env = {k: v for k, v in os.environ.items() if k not in ("SLURM_JOB_ID", "SCHWINGNET_FLOW_STEP", "FLOW_TEST_FAIL")}
    env.update(METAFLOW_USER="flowtest", **extra)
    return env


def launch(words, cwd, env, root):
    """flows/launch.py with the test's own datastore: its exit code, its JSON lines and its output."""
    done = subprocess.run([sys.executable, str(LAUNCH), words[0], "--root", str(root), *words[1:]], cwd=cwd, env=env,
                          capture_output=True, text=True, timeout=TIMEOUT)
    said = [json.loads(line) for line in done.stdout.splitlines() if line.startswith("{")]
    return done.returncode, said, done.stdout + done.stderr


@unittest.skipIf(MISSING, f"needs the train environment ({', '.join(MISSING)} missing)")
class AutoanatomistFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = self.tmp / "repo"
        for name in COPIED:
            (self.repo / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / name, self.repo / name)
        shutil.copytree(ROOT / "vendor" / "beethoven-qa" / "src", self.repo / "vendor" / "beethoven-qa" / "src")
        (self.repo / "tools" / "autoanatomist_trial.py").write_text(STUB_TRIAL, encoding="utf-8")
        self.stand_ins_for_the_run_code()
        # The tools write their caches into the checkout, as Python does on the grid, where the
        # repository's own .gitignore keeps the tree the record calls clean.
        (self.repo / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        subprocess.run(self.git("init", "-q"), check=True, capture_output=True, timeout=60)
        self.commit("the stand-in")
        self.root, self.out, self.data, self.work = (self.tmp / name for name in ("metaflow", "autoanatomist", "data", "work"))
        self.data.mkdir()
        self.work.mkdir()

    def stand_ins_for_the_run_code(self):
        """A file for every path the kind's run code names that the scratch repository does not
        copy, a folder's with one file in it, so the digest the launcher names the run by is read."""
        spec = importlib.util.spec_from_file_location("run_code_for_autoanatomist_test", self.repo / "tools" / "run_code.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for name in module.KINDS["autoanatomist"]:
            path = self.repo / name / "stand-in.txt" if name.endswith("/") else self.repo / name
            if not (self.repo / name).exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"# {name}, a stand-in\n", encoding="utf-8")

    def git(self, *words):
        return ["git", "-C", str(self.repo), "-c", "user.name=flow test", "-c", "user.email=flow@test", "-c", "commit.gpgsign=false",
                "-c", "gc.auto=0", "-c", "gc.autoDetach=false", "-c", "maintenance.auto=false", "-c", "maintenance.autoDetach=false", *words]

    def commit(self, message):
        for words in (["add", "-A"], ["commit", "-q", "-m", message]):
            subprocess.run(self.git(*words), check=True, capture_output=True, timeout=60)

    def run_part(self, part, *words, **extra):
        """One launch of a part of the smoke, as the job script's series makes it: exit code, JSON
        lines, output and the stand-in's calls."""
        calls = self.tmp / f"calls-{part}-{len(list(self.tmp.glob('calls-*')))}"
        calls.write_text("", encoding="utf-8")
        given = ["--part", part, "--plan", str(self.repo / PLAN), "--chain", "none", "--out", str(self.out), *words]
        env = base_env(SCHWINGNET=str(self.repo), FLOW_TEST_CALLS=str(calls), **extra)
        code, said, out = launch(["autoanatomist", "--max-workers", "1", "--", *given], self.work, env, self.root)
        return code, said, out, calls.read_text(encoding="utf-8").splitlines()

    def run_trial(self, task, **extra):
        return self.run_part("trial", "--data", str(self.data), "--task", str(task), "--tasks", "2", **extra)

    def folder(self):
        return self.out / "gold3_latent_smoke" / "none"

    def report_rows(self, checklist):
        document = json.loads((self.folder() / f"{checklist}.json").read_text(encoding="utf-8"))
        return {row["id"]: row for row in document["items"]}

    def test_the_smokes_two_trials_and_its_join_run_through_the_launcher_with_the_record_and_the_report(self):
        for task, trial in enumerate(("lambda_then_w_s1", "null_s1")):
            code, said, out, calls = self.run_trial(task)
            self.assertEqual(code, 0, out)
            self.assertEqual((said[-1]["successful"], said[-1]["verdict"]), (True, 0), out)
            self.assertEqual(calls, [f"trial {trial} 2 2"])
            ended = json.loads((self.folder() / "trials" / trial / "ENDED.json").read_text(encoding="utf-8"))
            self.assertEqual((ended["code"], ended["verdict"], ended["part"]), (0, 0, "trial"))
            self.assertIn(f"$ {sys.executable} {self.repo / 'tools' / 'autoanatomist_trial.py'}",
                          (self.folder() / "logs" / f"{trial}.log").read_text(encoding="utf-8"))
        code, said, out, calls = self.run_part("join", "--tasks", "2")
        self.assertEqual(code, 0, out)
        self.assertEqual((said[-1]["successful"], said[-1]["verdict"]), (True, 0), out)
        self.assertIn("AutoanatomistFlow: lambda_then_w: beats the null", out)
        self.assertEqual(calls, [])
        decision = json.loads((self.folder() / "join" / "DECISION.json").read_text(encoding="utf-8"))
        self.assertEqual(decision["arms"]["lambda_then_w"]["beats_null"], True)
        record = json.loads((self.folder() / "RECORD.json").read_text(encoding="utf-8"))
        self.assertEqual((record["study"], record["part"], record["prereg"], record["prereg_part"]),
                         ("autoanatomist-screen", "join", PREREG, "gold3_latent_smoke"))
        self.assertEqual(record["plan"]["file"], PLAN)
        self.assertEqual([t["id"] for t in record["trials"]], ["lambda_then_w_s1", "null_s1"])
        self.assertIn("trials/null_s1/entry.json", record["files"])
        self.assertIn("join/DECISION.json", record["files"])
        self.assertEqual(len(record["where"]["commit"]), 40)
        # the split it kept, each file by its sha256, so a later run that starts from its checkpoint can check it
        splits = ("data/splits/rule.json", "data/splits/test-persons.json", "data/splits/latent-prior-test-reserve.json",
                  "data/splits/latent-prior-repeat-groups.json")
        self.assertEqual(record["splits"], {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in splits})
        self.assertTrue(record["where"]["clean_tree"], record["where"])
        summary = (self.folder() / "SUMMARY.md").read_text(encoding="utf-8")
        self.assertIn("- lambda_then_w: beats the null", summary)
        self.assertEqual(json.loads((self.folder() / "ENDED.json").read_text(encoding="utf-8"))["verdict"], 0)
        for name in ("REPORT.md", "claim.json", "reforms.json"):
            self.assertTrue((self.folder() / name).is_file(), name)
        check = subprocess.run([sys.executable, str(self.repo / "tools" / "report.py"), "check", "--study",
                                "autoanatomist-screen", "--run", str(self.folder())], capture_output=True, text=True, timeout=120)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)

    def test_a_trial_that_fails_fails_its_run_and_the_join_reports_it_with_its_arm_undecided(self):
        code, said, out, _ = self.run_trial(0)
        self.assertEqual(code, 0, out)
        code, said, out, calls = self.run_trial(1, FLOW_TEST_FAIL="null_s1")
        self.assertNotEqual(code, 0, out)
        self.assertEqual(said[-1]["verdict"], 1, out)
        self.assertEqual(calls, ["trial null_s1 2 2"])
        ended = json.loads((self.folder() / "trials" / "null_s1" / "ENDED.json").read_text(encoding="utf-8"))
        self.assertEqual((ended["code"], ended["verdict"]), (1, 1))
        # the join still decides, with the failed null leaving every arm undecided, and its run says so
        code, said, out, _ = self.run_part("join", "--tasks", "2")
        self.assertEqual(said[-1]["verdict"], 1, out)
        self.assertIn("AutoanatomistFlow: lambda_then_w: undecided", out)
        self.assertIn("AutoanatomistFlow: null_s1 failed:", out)
        self.assertTrue((self.folder() / "RECORD.json").is_file())

    def test_a_prereg_moved_since_its_freeze_starts_nothing(self):
        with (self.repo / PREREG).open("a", encoding="utf-8") as prereg:
            prereg.write("An edit after the freeze.\n")
        self.commit("an edit to the PREREG after its freeze")
        code, said, out, calls = self.run_trial(0)
        self.assertEqual(code, 90, out)
        self.assertEqual((said, calls), ([], []), out)

    def test_a_plan_changed_since_its_freeze_starts_nothing(self):
        plan = self.repo / PLAN
        text = plan.read_text(encoding="utf-8")
        plan.write_text(text.replace('"epochs": 150', '"epochs": 151'), encoding="utf-8")
        self.commit("a plan changed after the freeze")
        code, said, out, calls = self.run_trial(0)
        self.assertEqual(code, 90, out)
        self.assertEqual((said, calls), ([], []), out)

    def test_words_that_name_no_trial_of_the_plan_stop_before_the_trial_runs(self):
        code, said, out, calls = self.run_trial(2)
        self.assertNotEqual(code, 0, out)
        self.assertEqual(calls, [])
        self.assertFalse((self.folder() / "trials").exists())


if __name__ == "__main__":
    unittest.main()
