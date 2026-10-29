"""The FluXray reproduction's report (tools/report.py --study flux-realism, tools/realism_report.py):
read from a run folder of flows/realism.py, every code answer taken from RECORD.json and the files it
names by their sha256 and never guessed, the statistics missing until the stats stage has run, the
verdict never read, and every owner item missing until the owner writes it."""

import hashlib
import importlib.util
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STUDY = "flux-realism"
REGISTER = {"aliases": {}, "sources": {"scidb_enhance_pet_1_6k": {"licence": "fixture", "class": "non-commercial"}}}
PLAN = {"subjects": 2, "poses_per_subject": 2, "arms": 2, "draw_seed": 1, "shard_subjects": 1, "ray_samples": 500,
        "hu_low": -1000.0, "hu_high": 2000.0, "air_clamp_hu": -900.0, "canvas": 256, "percentile_low": 0.5,
        "percentile_high": 99.5}
RECIPE = {"model": "klein-9b", "steps": 4, "guidance": 1.0, "dtype": "bfloat16", "render_pixels": 1024,
          "render_spacing_mm": 0.6, "render_sdd_mm": 1250.0, "foreground_floor": 0.05}
RULES = {"neighbours": "5 nearest neighbours, own subject left out", "auc_interval": "200-draw bootstrap over subjects",
         "permutation": "200 permutations within subjects", "multiplicity": "Benjamini-Hochberg over the spaces"}


def load_report():
    spec = importlib.util.spec_from_file_location("report_under_test", ROOT / "tools" / "report.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


report = load_report()


def quiet(function, *args, **kwargs):
    with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
        return function(*args, **kwargs)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def comparison(auc, word):
    side = {"c2st": {"auc": auc, "low": auc - 0.05, "high": auc + 0.05}, "mmd": {"p": 0.5, "q": 0.5}}
    null = {"c2st": {"auc": 0.5, "low": 0.45, "high": 0.55}}
    return {"a_vs_b": side, "b_split_half": null, "arm_null": null, "nulls_separable": False, "verdict": word}


def stats(auc, word):
    return {"seed": 7, "sets": {"a": {"n": 8, "subjects": 2}, "b": {"n": 4, "subjects": 2}}, "rules": RULES,
            "spaces": {space: comparison(auc, word) for space in ("physics", "flexray", "imagenet")}}


class RealismFolder(unittest.TestCase):
    """Each test builds an edit run folder, and a stats run folder that copies the edit's small
    files under edit/ as the flow does, and reads answers and a licence register of its own."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        root = Path(self.folder.name)
        self.answers = root / "answers.json"
        self.write_answers({})
        register = root / "licences.json"
        register.write_text(json.dumps(REGISTER), encoding="utf-8")
        config = report.STUDIES[STUDY]
        self.addCleanup(config.update, dict(config))
        config.update(answers=self.answers, runs=root / "runs")
        self.addCleanup(setattr, report.REALISM, "LICENCES", report.REALISM.LICENCES)
        report.REALISM.LICENCES = register
        self.edit = self.make_edit(root / "runs" / "edit-0000000000000001")
        self.stats = self.make_stats(root / "runs" / "stats-0000000000000002", self.edit)

    def write_answers(self, answers):
        self.answers.write_text(json.dumps({"_about": "test", **answers}), encoding="utf-8")

    def record(self, folder, stage, extra):
        files = {str(path.relative_to(folder)): sha256(path) for path in sorted(folder.rglob("*")) if path.is_file()}
        record = {"study": STUDY, "stage": stage, "run": "41", "key": "0000000000000001", "commit": "0" * 40,
                  "clean_tree": True, "prereg": "docs/research/flux-realism/PREREG.md", "prereg_sha256": "5" * 64,
                  "started": "2026-10-29 03:00:00", "where": {"host": "fixture-node", "slurm_job": "1000001"},
                  "plan": PLAN, "recipe": RECIPE, "files": files, **extra}
        write(folder / "RECORD.json", json.dumps(record))
        write(folder / "ENDED.json", json.dumps({"verdict": 0}))

    def make_edit(self, folder):
        inputs = {"model": "klein-9b", "samples_sha256": "1" * 64, "samples_rows": 20, "db_sha256": "2" * 64,
                  "klein_sha256": "3" * 64, "bundle_sha256": "4" * 64, "imagenet_sha256": "6" * 64,
                  "environment": {"diffusers": "0.0.0", "gpu": "FIXTURE GPU", "cuda": "12.0"}, "pins_differ": []}
        write(folder / "inputs.json", json.dumps(inputs))
        write(folder / "split" / "split.json", json.dumps({"seed": 1, "from": 3, "all": 2, "shards": 2}))
        write(folder / "filter" / "filter_kept.csv", "name\na\nb\nc\nd\ne\nf\ng\n")
        write(folder / "filter" / "filter_dropped.csv", "name\nh\n")
        write(folder / "render" / "manifest.jsonl", "{}\n")
        counts = {"fluxray_samples": 20, "not_in_db": 1, "off_grid": 2, "eligible_subjects": 3, "drawn_subjects": 2,
                  "renders": 4, "edits": 8, "kept": 7, "fluxray_exported": 4}
        self.record(folder, "edit", {"counts": counts})
        return folder

    def make_stats(self, folder, edit):
        for name in ("RECORD.json", "ENDED.json", "inputs.json", "split/split.json", "filter/filter_kept.csv",
                     "filter/filter_dropped.csv", "render/manifest.jsonl"):
            write(folder / "edit" / name, (edit / name).read_text(encoding="utf-8"))
        write(folder / "kept" / "stats.json", json.dumps(stats(0.52, "indistinguishable")))
        write(folder / "raw" / "stats.json", json.dumps(stats(0.9, "separable")))
        extra = {"replication": "reproduced", "geometry": "holds", "shifts": {"raw": 0.2}, "edit_folder": str(edit),
                 "counts": {}}
        self.record(folder, "stats", extra)
        return folder

    def rows(self, folder, checklist):
        report.write(folder, STUDY)
        return {row["id"]: row for row in json.loads((folder / f"{checklist}.json").read_text(encoding="utf-8"))["items"]}


class EditRunTest(RealismFolder):
    def test_an_edit_run_answers_what_it_made_and_waits_for_the_stats(self):
        claim = self.rows(self.edit, "claim")
        self.assertEqual(claim["7"]["state"], "met")
        self.assertIn("klein-9b", claim["7"]["evidence"])
        self.assertEqual(claim["35"]["state"], "met")
        self.assertIn("dropped 1 (12.5 percent", claim["35"]["evidence"])
        for item in ("20", "28", "29", "37"):
            self.assertEqual(claim[item]["state"], "missing", item)
            self.assertIn("needs the stats stage's run", claim[item]["evidence"], item)
        self.assertEqual(claim["25"]["state"], "not applicable")
        self.assertEqual(self.rows(self.edit, "reforms")["4b"]["state"], "met")

    def test_a_file_that_is_no_longer_the_one_the_record_names_is_not_read(self):
        write(self.edit / "split" / "split.json", json.dumps({"seed": 1, "from": 3, "all": 3, "shards": 3}))
        subsets = self.rows(self.edit, "claim")["10"]
        self.assertEqual(subsets["state"], "missing")
        self.assertIn("split/split.json is not the file the record names", subsets["evidence"])

    def test_a_short_run_is_not_called_complete(self):
        record = json.loads((self.edit / "RECORD.json").read_text(encoding="utf-8"))
        record["counts"]["edits"] = 7
        write(self.edit / "RECORD.json", json.dumps(record))
        corrupt = self.rows(self.edit, "reforms")["4b"]
        self.assertEqual(corrupt["state"], "missing")
        self.assertIn("edits 7 of 8", corrupt["evidence"])

    def test_the_report_never_reads_the_verdict(self):
        report.write(self.edit, STUDY)
        before = (self.edit / "REPORT.md").read_text(encoding="utf-8")
        write(self.edit / "ENDED.json", json.dumps({"verdict": 1}))
        report.write(self.edit, STUDY)
        self.assertEqual((self.edit / "REPORT.md").read_text(encoding="utf-8"), before)

    def test_a_folder_that_is_no_run_of_the_study_is_refused_in_words(self):
        record = json.loads((self.edit / "RECORD.json").read_text(encoding="utf-8"))
        write(self.edit / "RECORD.json", json.dumps({**record, "study": "drr-domain-gap"}))
        with self.assertRaises(report.ReportError):
            report.render_study(STUDY, self.edit)
        (self.edit / "RECORD.json").unlink()
        with self.assertRaises(report.ReportError):
            report.render_study(STUDY, self.edit)


class StatsRunTest(RealismFolder):
    def test_a_stats_run_answers_every_code_item_from_its_own_folder(self):
        for checklist in ("claim", "reforms"):
            rows = self.rows(self.stats, checklist)
            code = [row for row in rows.values() if row["basis"] == "code"]
            self.assertTrue(code)
            self.assertEqual([row["id"] for row in code if row["state"] == "missing"], [], checklist)
        endpoints = self.rows(self.stats, "claim")["37"]["evidence"]
        self.assertIn("replication: reproduced", endpoints)
        self.assertIn("raw flexray: AUC 0.900", endpoints)

    def test_complete_waits_for_the_owner_s_answers(self):
        self.assertEqual(quiet(report.check, self.stats, study=STUDY), 1)
        report.write(self.stats, STUDY)
        self.assertEqual(quiet(report.check, self.stats, study=STUDY), 0)
        self.assertEqual(quiet(report.check, self.stats, True, STUDY), 1)
        self.write_answers({fact: "Fixture sentence." for fact in report.study_declared_facts(STUDY)})
        report.write(self.stats, STUDY)
        self.assertEqual(quiet(report.check, self.stats, True, STUDY), 0)

    def test_the_licence_register_is_quoted_and_a_source_with_no_entry_is_named(self):
        text = report.render_study(STUDY, self.stats)["REPORT.md"]
        self.assertIn("ENHANCE.PET 1.6k, Science Data Bank doi:10.57760/sciencedb.34150, the bucket enhance-pet-1-6k: fixture; class non-commercial", text)
        self.assertIn("FLUX.2 klein-9B, black-forest-labs/FLUX.2-klein-9B: no entry in data/licences.json", text)

    def test_the_command_line_takes_the_study(self):
        self.assertEqual(quiet(report.main, ["write", "--study", STUDY, "--run", str(self.stats)]), 0)
        self.assertEqual(quiet(report.main, ["check", "--study", STUDY, "--run", str(self.stats)]), 0)
        self.assertEqual(quiet(report.main, ["check", "--study", STUDY, "--run", str(self.stats), "--complete"]), 1)

    def test_check_recorded_holds_a_realism_run_to_its_report(self):
        self.addCleanup(setattr, report, "RUNS", report.RUNS)
        report.RUNS = Path(self.folder.name) / "no-training-runs"
        drr = report.STUDIES["drr-domain-gap"]
        self.addCleanup(drr.update, dict(drr))
        drr["runs"] = Path(self.folder.name) / "no-drr-runs"
        self.assertEqual([name for name, _ in report.recorded_studies()], [STUDY, STUDY])
        self.assertEqual(quiet(report.main, ["check-recorded"]), 1)
        self.assertEqual(quiet(report.main, ["write-recorded"]), 0)
        self.assertEqual(quiet(report.main, ["check-recorded"]), 0)


class RulesTest(unittest.TestCase):
    def test_every_item_the_study_answers_by_code_has_a_fact(self):
        for key, checklist in report.checklists().items():
            for item in checklist["items"]:
                basis, fact = report.study_basis(key, item, STUDY)
                self.assertIn(basis, ("code", "declared"), item["id"])
                if basis == "code":
                    self.assertIn(fact, report.REALISM.FACTS, item["id"])

    def test_the_study_s_answers_file_holds_every_fact_its_owner_answers_and_none_filled(self):
        path = ROOT / "data" / "reporting" / "studies" / f"{STUDY}.json"
        answers = report.study_answers(path)
        self.assertEqual(set(answers), report.study_declared_facts(STUDY))
        self.assertEqual([fact for fact, text in answers.items() if text], [])



if __name__ == "__main__":
    unittest.main()
