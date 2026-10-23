"""The run report (tools/report.py): every item answered, a gap named, the licences read and not worked out."""

import importlib.util
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_report():
    spec = importlib.util.spec_from_file_location("report_under_test", ROOT / "tools" / "report.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


report = load_report()
RECORD = {"run_id": "a767a466f5c1", "code_commit": "11546b7e534e56ce89676da17034c1ede65caaaf", "clean_tree": True, "catalog_version": 1, "catalog_sha256": "9" * 64, "split_disjoint": True, "stage": "level", "seed": 1, "epochs": 4, "parent_weights": None, "started_at": "2026-10-21T02:36:55Z", "mode": "local", "jobs": [{"step": "train", "partition": "local", "gpus": 0, "seconds_used": 146, "exit_code": 0}]}
CHECKPOINT = {"epoch": 2, "validation_accuracy": 0.99, "validation_ci": [0.98, 0.997], "validation_n": 546, "counts": {"train": 4840, "validation": 546, "train_persons": 54, "validation_persons": 6}}
RESULTS = {"part": "test", "counts": {"crops": 556, "persons": 5, "frames": 148, "levels": {"L1": 73}}, "rows": [{"measure": "accuracy", "stratum": "all levels", "correct": 556, "total": 556}]}
PROVENANCE = {"catalog_sha256": "9" * 64, "recipe": {"name": "commercial", "allow": ["open"], "parent_catalog_sha256": "8" * 64}, "sources": [{"source": "carmlspine", "licence": "CC BY 4.0", "class": "open", "commercial": "yes", "reviewed": "rule", "frames": {"train": 10, "test": 2}}], "run_class": "open", "commercial_use": "yes", "fits_recipes": ["commercial", "research"], "unclassified": [], "caveat": "The classes are proposed by rule until the owner reviews them."}


def make_run(folder, provenance=None):
    run = Path(folder) / RECORD["run_id"]
    (run / "train").mkdir(parents=True)
    (run / "evaluate").mkdir()
    (run / "RUN.json").write_text(json.dumps(RECORD), encoding="utf-8")
    (run / "split-check.json").write_text(json.dumps({"disjoint": True, "persons_in_two_parts": [], "frames_in_two_parts": []}), encoding="utf-8")
    (run / "train" / "checkpoint.json").write_text(json.dumps(CHECKPOINT), encoding="utf-8")
    (run / "train" / "MODEL.md").write_text("- Architecture: torchvision resnet18, crops 64x64.\n- Initial weights: none (from scratch).\n", encoding="utf-8")
    (run / "evaluate" / "results.json").write_text(json.dumps(RESULTS), encoding="utf-8")
    if provenance:
        (run / "PROVENANCE.json").write_text(json.dumps(provenance), encoding="utf-8")
    return run


class WithStudy(unittest.TestCase):
    """Each test runs against a study file of its own, so the repository's is never read or written."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.study_path = Path(self.folder.name) / "study.json"
        self.write_study({})
        self.saved = report.STUDY
        report.STUDY = self.study_path
        self.addCleanup(setattr, report, "STUDY", self.saved)

    def write_study(self, answers):
        self.study_path.write_text(json.dumps({"_about": "test", **answers}), encoding="utf-8")

    def rows(self, run, checklist):
        return {row["id"]: row for row in json.loads((run / f"{checklist}.json").read_text(encoding="utf-8"))["items"]}


class ChecklistsTest(unittest.TestCase):
    def test_every_item_has_an_answer_rule(self):
        lists = report.checklists()
        self.assertEqual(len(lists["claim"]["items"]), 44)
        self.assertEqual(len(lists["reforms"]["items"]), 32)
        for checklist in ("claim", "reforms"):
            ids = [item["id"] for item in lists[checklist]["items"]]
            self.assertEqual(len(ids), len(set(ids)), checklist)
            for item in lists[checklist]["items"]:
                self.assertIn(item["basis"], ("code", "declared"))
                if item["basis"] == "code":
                    self.assertIn(item["fact"], report.CODE_FACTS, item["id"])

    def test_the_study_file_holds_every_declared_fact(self):
        declared = {item["fact"] for checklist in report.checklists().values() for item in checklist["items"] if item["basis"] == "declared"}
        self.assertEqual(declared, set(report.study_answers()))


class AnswerTest(WithStudy):
    def test_code_items_quote_the_run_and_gaps_name_their_work(self):
        run = make_run(self.folder.name)
        report.write(run)
        claim = self.rows(run, "claim")
        self.assertEqual(claim["20"]["state"], "met")
        self.assertIn("split-check.json", claim["20"]["evidence"])
        self.assertEqual(claim["26"]["state"], "met")
        self.assertIn("epoch 2", claim["26"]["evidence"])
        self.assertEqual(claim["7"]["state"], "missing")
        self.assertIn("PROVENANCE.json", claim["7"]["evidence"])
        self.assertEqual(claim["35"]["state"], "missing")
        self.assertIn("exclusions.json", claim["35"]["evidence"])

    def test_a_declared_answer_and_a_reason_it_does_not_apply(self):
        self.write_study({"study_design": "Retrospective.", "trial_registration": "Not applicable: no trial."})
        run = make_run(self.folder.name)
        report.write(run)
        claim = self.rows(run, "claim")
        self.assertEqual((claim["5"]["state"], claim["5"]["evidence"]), ("declared", "Retrospective."))
        self.assertEqual(claim["34"]["state"], "not applicable")
        self.assertEqual(claim["44"]["state"], "missing")
        self.assertIn('"funding"', claim["44"]["evidence"])

    def test_a_dirty_tree_or_a_leak_is_never_met(self):
        run = make_run(self.folder.name)
        record = dict(RECORD, clean_tree=False)
        (run / "RUN.json").write_text(json.dumps(record), encoding="utf-8")
        (run / "split-check.json").write_text(json.dumps({"disjoint": False, "persons_in_two_parts": ["p1"]}), encoding="utf-8")
        report.write(run)
        reforms = self.rows(run, "reforms")
        self.assertEqual(reforms["2b"]["state"], "missing")
        self.assertEqual(reforms["6b"]["state"], "missing")
        self.assertIn("DIRTY tree", (run / "REPORT.md").read_text(encoding="utf-8"))


class LicenceTest(WithStudy):
    def test_the_licences_come_from_provenance(self):
        run = make_run(self.folder.name, PROVENANCE)
        report.write(run)
        text = (run / "REPORT.md").read_text(encoding="utf-8")
        self.assertIn("Commercial use of this network: **yes**", text)
        self.assertIn("| carmlspine | CC BY 4.0 | open | yes | rule | test 2, train 10 |", text)
        self.assertIn("Recipe: commercial (open)", text)
        self.assertIn("- Caveat: The classes are proposed by rule", text)
        claim = self.rows(run, "claim")
        self.assertEqual(claim["10"]["state"], "met")
        self.assertIn("recipe commercial", claim["10"]["evidence"])

    def test_no_provenance_says_commercial_use_is_unknown(self):
        run = make_run(self.folder.name)
        report.write(run)
        self.assertIn("whether the network may be used commercially", (run / "REPORT.md").read_text(encoding="utf-8"))


class CheckTest(WithStudy):
    def quiet(self, *args, **kwargs):
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            return report.check(*args, **kwargs)

    def test_a_stale_report_fails_and_an_incomplete_one_fails_complete(self):
        run = make_run(self.folder.name)
        self.assertEqual(self.quiet(run), 1)
        report.write(run)
        self.assertEqual(self.quiet(run), 0)
        self.assertEqual(self.quiet(run, complete=True), 1)
        self.write_study({"study_design": "Retrospective."})
        self.assertEqual(self.quiet(run), 1)

    def test_a_folder_with_no_run_record_is_refused(self):
        with self.assertRaises(report.ReportError):
            report.render(self.folder.name)


class FlowKeepsTheReportTest(unittest.TestCase):
    def test_record_copies_the_report_files(self):
        text = (ROOT / "tools" / "flow.py").read_text(encoding="utf-8")
        for name in report.OUTPUTS:
            self.assertIn(f'"{name}"', text)


if __name__ == "__main__":
    unittest.main()
