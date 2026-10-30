"""The auto-anatomist screen's CLAIM 2024 and REFORMS report (tools/autoanatomist_report.py, the study
autoanatomist-screen of tools/report.py): a chain folder as flows/autoanatomist.py's join leaves it
is written and then checked current, every code answer quotes the files RECORD.json names, a file
whose bytes moved since the record is missing in words, a chain run under another PREREG is never
reported in this design's words, the design the module restates is the one frozen beside the PREREG,
with every known limit of its section 6, and the sizes, the chance and the precision are read from
the chain, not assumed. Standard library only, so the required check runs it with the runner's
python3.
"""

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "tools" / "report.py"
STUDY = "autoanatomist-screen"
TRIALS = (("lambda_then_w_s1", "lambda_then_w", 1), ("null_s1", "null", 1))
# A word of each of PREREG.md section 6's known limits, in its order, found in the limit and in its
# restatement (tools/autoanatomist_report.py, LIMITS).
LIMIT_WORDS = ("centroid", "a person is a study", "one population", "normal spines", "mean over",
               "64 mm along z", "same to the bit", "frozen teacher")
# The same for section 8's known limits of the second screen (SECOND_LIMITS).
SECOND_LIMIT_WORDS = ("defaults", "volume share", "seed to seed", "takes no gradient")


def load_module():
    spec = importlib.util.spec_from_file_location("autoanatomist_report_under_test", ROOT / "tools" / "autoanatomist_report.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def sha256_of(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reading(epoch, distance):
    return {"epoch": epoch, "steps": epoch * 2, "loss": 1.0 / epoch, "dice": 0.5, "distance_mm": distance,
            "surface_missing": 0, "centroid_mm": 3.0, "name_accuracy": 0.25}


def write_chain(folder, prereg_sha256, precision="highest"):
    """A chain folder of two trials and the join, with RECORD.json naming each file by its sha256."""
    files = {}
    for tid, arm, seed in TRIALS:
        entry = {"version": 1, "screen": "gold3_latent_smoke", "trial": tid, "arm": arm, "seed": seed, "words": [f"seed={seed}"],
                 "steps": 4, "epochs": [reading(1, 9.0), reading(2, 8.0 if arm == "null" else 6.0)], "seconds": 10.0,
                 "seconds_per_crop": 0.01, "train_rows": 3, "validation_rows": 1}
        entry["final"] = {key: entry["epochs"][-1][key] for key in ("dice", "distance_mm", "surface_missing", "centroid_mm", "name_accuracy")}
        environment = {"host": "gpu-node", "python": "3.11.9", "backend": "gpu", "devices": ["NVIDIA A100"],
                       "packages": {"jax": "0.10.2", "flax": "0.12.8"}, "train_and_read_seconds": 12.5,
                       "matmul_precision": precision if arm == "null" else "highest"}
        for name, value in (("entry.json", entry), ("environment.json", environment)):
            write_json(folder / "trials" / tid / name, value)
            files[f"trials/{tid}/{name}"] = sha256_of(folder / "trials" / tid / name)
    decision = {"screen": "gold3_latent_smoke", "measure": "distance_mm", "null": "null", "null_finals": [8.0], "seeds": [1],
                "rule": "an arm beats null when every one of its seeds' final validation distance_mm is below every one of null's",
                "arms": {"lambda_then_w": {"finals": [6.0], "beats_null": True, "why": "every seed of lambda_then_w ends below every seed of null"}},
                "failed": {}}
    write_json(folder / "join" / "DECISION.json", decision)
    files["join/DECISION.json"] = sha256_of(folder / "join" / "DECISION.json")
    record = {"study": STUDY, "part": "join", "run": "AutoanatomistFlow/7", "key": "k", "commit": "a" * 40,
              "prereg": "docs/research/autoanatomist-screen/PREREG.md", "prereg_sha256": prereg_sha256,
              "prereg_part": "gold3_latent_smoke", "prereg_part_sha256": "b" * 64, "chain": "41000001",
              "started": "2026-10-30 10:00:00", "ended": "2026-10-30 11:00:00", "where": {"copy_of": "a" * 40},
              "plan": {"file": "grid/screens/gold3_latent_smoke.json", "screen": "gold3_latent_smoke",
                       "rows": {"train": 3, "validation": 1}, "epochs": 2, "evaluate_every": 1, "batch": 2,
                       "measure": "distance_mm", "null": "null", "seeds": [1]},
              "trials": [{"id": tid, "arm": arm, "seed": seed, "words": [f"seed={seed}"]} for tid, arm, seed in TRIALS],
              "files": files}
    write_json(folder / "RECORD.json", record)


def report(action, folder):
    return subprocess.run([sys.executable, str(REPORT), action, "--study", STUDY, "--run", str(folder)],
                          capture_output=True, text=True, timeout=120)


def items(folder, checklist):
    return {item["id"]: item for item in json.loads((folder / f"{checklist}.json").read_text(encoding="utf-8"))["items"]}


class ReportTest(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name) / "41000001"

    def test_the_design_restated_is_the_one_frozen_beside_the_prereg(self):
        frozen = (ROOT / "docs" / "research" / "autoanatomist-screen" / "PREREG.md.sha256").read_text(encoding="utf-8").split()[0]
        self.assertEqual(self.module.DESIGN, frozen)
        self.assertEqual(self.module.DESIGN, sha256_of(self.module.PREREG))

    def test_a_chain_is_written_and_checked_current_with_its_files_quoted(self):
        write_chain(self.folder, self.module.DESIGN)
        wrote = report("write", self.folder)
        self.assertEqual(wrote.returncode, 0, wrote.stdout + wrote.stderr)
        checked = report("check", self.folder)
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
        claim = items(self.folder, "claim")
        self.assertEqual(claim["37"]["state"], "met")
        self.assertIn("lambda_then_w [6.0]", claim["37"]["evidence"])
        self.assertIn("never dropped: none", claim["35"]["evidence"])
        self.assertEqual(claim["42"]["state"], "met")
        self.assertIn("jax 0.10.2", claim["23"]["evidence"])
        self.assertEqual(claim["1"]["state"], "missing")  # the title is the owner's, and the answers file is empty
        self.assertIn("chain 41000001 of gold3_latent_smoke", (self.folder / "REPORT.md").read_text(encoding="utf-8"))
        reforms = items(self.folder, "reforms")
        self.assertIn("the smoke's sizes, 3 training and 1 validation studies at 1 seed an arm", reforms["3e"]["evidence"])
        self.assertIn("at most one time in 2 at 1 seed a side", claim["29"]["evidence"])
        self.assertIn("the smoke answers no hypothesis", claim["29"]["evidence"])
        self.assertIn("every trial computed float32 in full", reforms["2d"]["evidence"])
        self.assertIn("AUTOANATOMIST_RERUNS", reforms["2d"]["evidence"])

    def test_a_file_whose_bytes_moved_since_the_record_answers_nothing(self):
        write_chain(self.folder, self.module.DESIGN)
        (self.folder / "join" / "DECISION.json").write_text("{}\n", encoding="utf-8")
        wrote = report("write", self.folder)
        self.assertEqual(wrote.returncode, 0, wrote.stdout + wrote.stderr)
        performance = items(self.folder, "claim")["37"]
        self.assertEqual(performance["state"], "missing")
        self.assertIn("join/DECISION.json is not the file RECORD.json names", performance["evidence"])

    def test_a_chain_of_another_design_is_not_reported_in_this_ones_words(self):
        write_chain(self.folder, "c" * 64)
        wrote = report("write", self.folder)
        self.assertEqual(wrote.returncode, 0, wrote.stdout + wrote.stderr)
        claim = items(self.folder, "claim")
        for item in ("19", "40", "42"):
            with self.subTest(item=item):
                self.assertEqual(claim[item]["state"], "missing")
                self.assertIn("the chain ran another design", claim[item]["evidence"])

    def test_a_trial_that_computed_in_another_precision_is_named_and_not_called_full(self):
        write_chain(self.folder, self.module.DESIGN, precision="default")
        wrote = report("write", self.folder)
        self.assertEqual(wrote.returncode, 0, wrote.stdout + wrote.stderr)
        reproduce = items(self.folder, "reforms")["2d"]["evidence"]
        self.assertIn("matmul precision was default, highest", reproduce)
        self.assertIn("not every card computed float32 in full", reproduce)
        self.assertNotIn("every trial computed float32 in full", reproduce)

    def test_the_screens_sizes_and_chance_are_read_from_its_plan(self):
        run = {"record": {"prereg_sha256": self.module.DESIGN,
                          "plan": {"screen": "gold3_latent_screen", "rows": {"train": 96, "validation": 24}, "seeds": [1, 2]}}}
        sizes = self.module.fact_sample_size(run)[1]
        self.assertIn("the screen's sizes are its budget, 96 training and 24 validation studies at 2 seeds an arm", sizes)
        chance = self.module.fact_uncertainty(run)[1]
        self.assertIn("at most one time in 6 at 2 seeds a side", chance)
        self.assertNotIn("no hypothesis", sizes + chance)

    def test_the_second_smoke_answers_no_hypothesis_and_the_second_screen_says_its_own_limits(self):
        smoke = {"record": {"prereg_sha256": self.module.DESIGN,
                            "plan": {"screen": "gold3_latent_smoke2", "rows": {"train": 3, "validation": 1}, "seeds": [1]}}}
        sizes = self.module.fact_sample_size(smoke)[1]
        self.assertIn("the smoke answers no hypothesis (PREREG.md section 8)", sizes)
        self.assertIn("no verdict of it is read as a result (PREREG.md section 8)", self.module.fact_uncertainty(smoke)[1])
        screen = {"record": {"prereg_sha256": self.module.DESIGN,
                             "plan": {"screen": "gold3_latent_screen2", "rows": {"train": 96, "validation": 24}, "seeds": [1, 2]}}}
        chance = self.module.fact_uncertainty(screen)[1]
        self.assertIn("five arms are read against one null, so a chance pass of some arm is likely", chance)
        self.assertNotIn("no hypothesis", chance + self.module.fact_sample_size(screen)[1])
        limits = self.module.fact_limitations(screen)[1]
        self.assertIn("(PREREG.md sections 6 and 8)", limits)
        for restated in self.module.LIMITS + self.module.SECOND_LIMITS:
            self.assertIn(restated, limits)
        self.assertNotIn(self.module.SECOND_LIMITS[0], self.module.fact_limitations(
            {"record": {"prereg_sha256": self.module.DESIGN, "plan": {"screen": "gold3_latent_screen"}}})[1])

    def test_every_known_limit_of_the_prereg_is_restated_in_its_order(self):
        section = self.module.PREREG.read_text(encoding="utf-8").split("## 6.", 1)[1].split("## 7.", 1)[0]
        limits = [line for line in section.split("Known limits", 1)[1].splitlines() if line.startswith("- ")]
        self.assertEqual(len(limits), len(self.module.LIMITS))
        self.assertEqual(len(limits), len(LIMIT_WORDS))
        for word, limit, restated in zip(LIMIT_WORDS, limits, self.module.LIMITS, strict=True):
            with self.subTest(word=word):
                self.assertIn(word, limit.lower())
                self.assertIn(word, restated.lower())

    def test_every_known_limit_of_the_second_screen_is_restated_in_its_order(self):
        section = self.module.PREREG.read_text(encoding="utf-8").split("## 8.", 1)[1]
        limits = [line for line in section.split("Known limits", 1)[1].splitlines() if line.startswith("- ")]
        self.assertEqual(len(limits), len(self.module.SECOND_LIMITS))
        self.assertEqual(len(limits), len(SECOND_LIMIT_WORDS))
        for word, limit, restated in zip(SECOND_LIMIT_WORDS, limits, self.module.SECOND_LIMITS, strict=True):
            with self.subTest(word=word):
                self.assertIn(word, limit.lower())
                self.assertIn(word, restated.lower())

    def test_a_report_the_files_moved_under_is_not_current(self):
        write_chain(self.folder, self.module.DESIGN)
        self.assertEqual(report("write", self.folder).returncode, 0)
        (self.folder / "trials" / "null_s1" / "environment.json").write_text("{}\n", encoding="utf-8")
        self.assertNotEqual(report("check", self.folder).returncode, 0)

    def test_the_answers_file_holds_every_item_the_owner_answers_and_no_other(self):
        spec = importlib.util.spec_from_file_location("report_under_test", REPORT)
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        path = ROOT / "data" / "reporting" / "studies" / f"{STUDY}.json"
        self.assertEqual(set(tool.study_answers(path)), tool.study_declared_facts(STUDY))
        self.assertTrue(all(value == "" for value in tool.study_answers(path).values()))

    def test_a_folder_with_no_record_of_the_screen_is_refused(self):
        self.folder.mkdir(parents=True)
        wrote = report("write", self.folder)
        self.assertNotEqual(wrote.returncode, 0)
        self.assertIn("not a chain of the screen", wrote.stdout + wrote.stderr)


if __name__ == "__main__":
    unittest.main()
