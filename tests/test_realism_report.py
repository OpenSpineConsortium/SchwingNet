"""The FluXray reproduction's report (tools/report.py --study flux-realism, tools/realism_report.py):
read from a run folder of flows/realism.py, every code answer taken from RECORD.json and the files it
names by their sha256 and never guessed, each GPU job's code, compute and software said from that
job's own files, the answers that restate the frozen design held to its digest, the statistics
missing until the stats stage has run, the verdict never read, and only the items no file answers
left to the owner, missing until the owner writes them."""

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
PREREG = ROOT / "docs" / "research" / "flux-realism" / "PREREG.md"
DESIGN = (PREREG.parent / "PREREG.md.sha256").read_text(encoding="ascii").split()[0]
OTHER_DESIGN = "5" * 64
# What no file of the study says, which the owner alone answers.
OWNER_ITEMS = {"title", "abstract", "background", "deidentification", "implications", "availability", "funding",
               "external_validity", "non_generalization"}
AFTER_FREEZE = 'DEVIATIONS.md, "From PREREG.md, after the freeze", entry'
REGISTER = {"aliases": {}, "sources": {"scidb_enhance_pet_1_6k": {"licence": "fixture", "class": "non-commercial"}}}
PLAN = {"subjects": 2, "poses_per_subject": 2, "arms": 2, "draw_seed": 1, "shard_subjects": 1, "ray_samples": 500,
        "hu_low": -1000.0, "hu_high": 2000.0, "air_clamp_hu": -900.0, "stats_seed": 7, "canvas": 256, "percentile_low": 0.5,
        "percentile_high": 99.5, "physics_bins": 32, "radial_bands": 16, "pca_components": 64, "knn": 5, "bootstraps": 200,
        "permutations": 200, "kid_subset": 100, "kid_repeats": 10}
RECIPE = {"model": "klein-9b", "steps": 4, "guidance": 1.0, "dtype": "bfloat16", "render_pixels": 1024,
          "render_spacing_mm": 0.6, "render_sdd_mm": 1250.0, "isocentre": "volume-centre", "stored_pixels": 256,
          "foreground_floor": 0.05, "filter_quantile": 0.98, "lora": ""}
RULES = {"neighbours": "5 nearest neighbours, every image of the sample's own subject left out in both sets",
         "auc_interval": "200-draw bootstrap over subjects, 95 percent",
         "permutation": "200 permutations; labels shuffled only among the images of each sample where the sets share samples",
         "mmd": "unbiased, on k principal components; k here: physics 57, flexray 64, imagenet 64",
         "distances": "FD and KID on k principal components; k here: physics 57, flexray 64, imagenet 64",
         "multiplicity": "Benjamini-Hochberg over the spaces, for the pooled comparison and for each seed arm",
         "nulls": "the second set's subjects split in halves; the first two seed arms against each other"}
COMPONENTS = {"physics": 57, "flexray": 64, "imagenet": 64}
COUNTS = {"fluxray_samples": 20, "not_in_db": 1, "off_grid": 2, "eligible_subjects": 3, "drawn_subjects": 2,
          "renders": 4, "edits": 8, "kept": 7, "fluxray_exported": 4}
EDIT_ENVIRONMENT = {"diffusers": "0.42.0", "torch": "2.0.0", "gpu": "EDIT GPU", "cuda": "12.0", "card_ok": True,
                    "installed": ["diffusers==0.42.0", "thunderpack==0.0.2", "torch==2.0.0"]}
STATS_ENVIRONMENT = {"diffusers": "0.42.0", "torch": "2.0.1", "gpu": "STATS GPU", "cuda": "12.1"}
# What the stats stage copies of the edit's folder under edit/ (flows/realism.py, EDIT_FILES).
EDIT_FILES = ("RECORD.json", "ENDED.json", "inputs.json", "split/split.json", "filter/filter_kept.csv",
              "filter/filter_dropped.csv", "measure/measure.md", "render/manifest.jsonl")
JOBS = {"edit": ("1000001", "aaaaaaa"), "stats": ("2000002", "bbbbbbb")}


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


def measured(auc, strata):
    """One comparison's classifier and kernel test as tools/realism.py compare writes them."""
    return {"c2st": {"auc": auc, "low": auc - 0.05, "high": auc + 0.05, "p": 0.5, "strata": strata},
            "mmd": {"mmd2": 0.01, "bandwidth": 1.0, "p": 0.5, "q": 0.5, "strata": strata}}


def comparison(auc, word, components):
    def compared(value, strata):
        return {"n_a": 4, "n_b": 4, "components": components, "frechet64": 1.0, "kid64": 0.01, **measured(value, strata)}

    return {"a_vs_b": compared(auc, "sample"), "b_split_half": compared(0.5, "subject"),
            "arms": {"a0": compared(auc, "sample"), "a1": compared(auc, "sample")}, "arm_null": compared(0.5, "sample"),
            "nulls_separable": False, "verdict": word}


def stats(auc, word):
    return {"size": 256, "seed": 7, "sets": {"a": {"n": 8, "subjects": 2}, "b": {"n": 4, "subjects": 2}}, "rules": RULES,
            "spaces": {space: comparison(auc, word, k) for space, k in COMPONENTS.items()}, "verdict": word,
            "paired": {"pairs": 4, "psnr_median": 20.0, "ssim_median": 0.5, "shift_px_median": 0.2, "shift_px_p90": 0.4}}


def without(document, field):
    """A stats.json with a field taken out of every test of every comparison that holds it."""
    for entry in document["spaces"].values():
        for test in [entry["a_vs_b"], entry["b_split_half"], entry["arm_null"], *entry["arms"].values()]:
            test.pop(field, None)
            for side in ("c2st", "mmd"):
                test[side].pop(field, None)
    return document


def stamp(folder):
    """Every file of a folder by its sha256, as the flow's end names them: all but those called
    RECORD.json, the copied edit's among them, and ENDED.json, which the end writes after the record."""
    return {str(path.relative_to(folder)): sha256(path) for path in sorted(folder.rglob("*"))
            if path.is_file() and path.name != "RECORD.json" and str(path.relative_to(folder)) != "ENDED.json"}


def restamp(folder):
    """A record restamped over its folder's files as they now are, as if the run had written them."""
    record = json.loads((folder / "RECORD.json").read_text(encoding="utf-8"))
    record["files"] = stamp(folder)
    write(folder / "RECORD.json", json.dumps(record))


class RealismFolder(unittest.TestCase):
    """Each test builds an edit run folder, and a stats run folder that copies the edit's small
    files under edit/ as the flow does, each with a record in the flow's shape, and reads answers
    and a licence register of its own."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.answers = self.root / "answers.json"
        self.write_answers({})
        register = self.root / "licences.json"
        register.write_text(json.dumps(REGISTER), encoding="utf-8")
        config = report.STUDIES[STUDY]
        self.addCleanup(config.update, dict(config))
        config.update(answers=self.answers, runs=self.root / "runs")
        self.addCleanup(setattr, report.REALISM, "LICENCES", report.REALISM.LICENCES)
        report.REALISM.LICENCES = register
        self.edit = self.make_edit(self.root / "runs" / "edit-0000000000000001-1001")
        self.stats = self.make_stats(self.root / "runs" / "stats-0000000000000002-2002", self.edit)

    def write_answers(self, answers):
        self.answers.write_text(json.dumps({"_about": "test", **answers}), encoding="utf-8")

    def record(self, folder, stage, extra):
        """RECORD.json in the flow's shape, the run that made the folder its last name, then ENDED.json."""
        job, commit = JOBS[stage]
        run = f"RealismFlow/{folder.name.rsplit('-', 1)[1]}"
        # the commit and tree read where the run began and where it ended, as the flow's code_state
        # reads them; a record's clean_tree given dirty is dirty at both ends
        code = {"commit": commit.ljust(40, "0"), "clean_tree": extra.get("clean_tree", True)}
        where = {"run": run, "host": f"{stage}-node", "slurm_job": job, "datastore": "/fixture/metaflow", **code,
                 **extra.pop("where", {})}
        ended_in = {"run": run, "host": f"{stage}-node", "slurm_job": job, "ended": "2026-10-29 04:00:00", **code}
        if "ended_in" in extra:
            given = extra.pop("ended_in")
            ended_in = given and {**code, **given}
        record = {"study": STUDY, "stage": stage, "run": run, "key": "0000000000000001", "commit": commit.ljust(40, "0"),
                  "clean_tree": True, "prereg": "docs/research/flux-realism/PREREG.md", "prereg_sha256": DESIGN,
                  "started": "2026-10-29 03:00:00", "ended": "2026-10-29 04:00:00", "where": where, "ended_in": ended_in,
                  "plan": PLAN, "recipe": RECIPE, "short": [], "files": stamp(folder), **extra}
        write(folder / "RECORD.json", json.dumps(record))
        ended = {"folder": str(folder), "run": (record["ended_in"] or {}).get("run"), "started_run": where["run"],
                 "key": record["key"], "started": record["started"], "ended": (record["ended_in"] or {}).get("ended"),
                 "verdict": 0, "report": "fixture"}
        write(folder / "ENDED.json", json.dumps(ended))

    def make_edit(self, folder, environment=None, **extra):
        inputs = {"model": "klein-9b", "samples_sha256": "1" * 64, "samples_rows": 20, "db_sha256": "2" * 64,
                  "klein_sha256": "3" * 64, "bundle_sha256": "4" * 64, "imagenet_sha256": "6" * 64,
                  "environment": environment or EDIT_ENVIRONMENT, "pins_differ": []}
        write(folder / "inputs.json", json.dumps(inputs))
        write(folder / "split" / "split.json", json.dumps({"seed": 1, "from": 3, "all": 2, "shards": 2}))
        write(folder / "filter" / "filter_kept.csv", "name\na\nb\nc\nd\ne\nf\ng\n")
        write(folder / "filter" / "filter_dropped.csv", "name\nh\n")
        write(folder / "render" / "manifest.jsonl", "{}\n")
        write(folder / "measure" / "measure.md", "| level | angle |\n")
        self.record(folder, "edit", {"counts": COUNTS, **extra})
        return folder

    def make_stats(self, folder, edit, environment=True, bundle_sha256="4" * 64, kept=None, raw=None, **extra):
        for name in EDIT_FILES:
            write(folder / "edit" / name, (edit / name).read_text(encoding="utf-8"))
        if environment:
            write(folder / "environment.json", json.dumps({"environment": STATS_ENVIRONMENT, "pins_differ": [], "bundle": "/b",
                                                           "bundle_sha256": bundle_sha256, "imagenet": "/r.pth",
                                                           "imagenet_sha256": "6" * 64}))
        write(folder / "kept" / "stats.json", json.dumps(kept or stats(0.52, "indistinguishable")))
        write(folder / "raw" / "stats.json", json.dumps(raw or stats(0.9, "separable")))
        sets = {"a": {"n": 8, "subjects": 2}, "b": {"n": 4, "subjects": 2}}
        self.record(folder, "stats", {"replication": "reproduced", "geometry": "holds", "shifts": {"raw": 0.2},
                                      "words": {"kept": "indistinguishable", "raw": "separable"}, "edit_folder": str(edit),
                                      "counts": {"kept": sets, "raw": sets}, **extra})
        return folder

    def another(self, name):
        """A folder outside runs/, so the recorded runs stay the two setUp made."""
        return self.root / "more" / name

    def rows(self, folder, checklist):
        report.write(folder, STUDY)
        return {row["id"]: row for row in json.loads((folder / f"{checklist}.json").read_text(encoding="utf-8"))["items"]}

    def both(self, folder):
        return {**{f"CLAIM {k}": v for k, v in self.rows(folder, "claim").items()},
                **{f"REFORMS {k}": v for k, v in self.rows(folder, "reforms").items()}}


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

    def test_an_edit_run_says_its_own_job_s_code_and_compute(self):
        reforms = self.rows(self.edit, "reforms")
        self.assertEqual(reforms["2b"]["state"], "met")
        self.assertIn("edit: commit aaaaaaa from a clean tree", reforms["2b"]["evidence"])
        self.assertEqual(reforms["2c"]["state"], "met")
        self.assertIn("edit: run RealismFlow/1001 in Slurm job 1000001 on host edit-node", reforms["2c"]["evidence"])
        self.assertIn("GPU EDIT GPU, CUDA 12.0 (inputs.json", reforms["2c"]["evidence"])

    def test_a_file_that_is_no_longer_the_one_the_record_names_is_not_read(self):
        write(self.edit / "split" / "split.json", json.dumps({"seed": 1, "from": 3, "all": 3, "shards": 3}))
        subsets = self.rows(self.edit, "claim")["10"]
        self.assertEqual(subsets["state"], "missing")
        self.assertIn("split/split.json is not the file the record names", subsets["evidence"])

    def test_a_file_that_lacks_a_field_an_answer_quotes_leaves_it_missing(self):
        edit = self.another("edit-0000000000000001-1003")
        self.make_edit(edit)
        inputs = json.loads((edit / "inputs.json").read_text(encoding="utf-8"))
        del inputs["samples_sha256"]
        write(edit / "inputs.json", json.dumps(inputs))
        restamp(edit)
        sources = self.rows(edit, "claim")["7"]
        self.assertEqual(sources["state"], "missing")
        self.assertIn("KeyError: 'samples_sha256'", sources["evidence"])

    def test_a_run_short_of_the_plan_is_not_called_complete(self):
        record = json.loads((self.edit / "RECORD.json").read_text(encoding="utf-8"))
        record["counts"]["edits"] = 7
        write(self.edit / "RECORD.json", json.dumps(record))
        corrupt = self.rows(self.edit, "reforms")["4b"]
        self.assertEqual(corrupt["state"], "missing")
        self.assertIn("edits 7 of 8", corrupt["evidence"])

    def test_a_run_the_flow_found_short_of_its_draw_says_so(self):
        edit = self.make_edit(self.another("edit-0000000000000001-1004"), short=["fluxray_exported 3 of 4"])
        corrupt, limitations = self.rows(edit, "reforms")["4b"], self.rows(edit, "claim")["40"]
        self.assertEqual(corrupt["state"], "missing")
        self.assertIn("short of the draw: fluxray_exported 3 of 4", corrupt["evidence"])
        self.assertIn("short of the draw: fluxray_exported 3 of 4", limitations["evidence"])

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

    def test_each_job_s_code_compute_and_software_come_from_that_job_s_own_files(self):
        reforms, claim = self.rows(self.stats, "reforms"), self.rows(self.stats, "claim")
        compute = reforms["2c"]["evidence"]
        self.assertEqual(reforms["2c"]["state"], "met")
        edit_part, stats_part = compute.split("; stats: ")
        self.assertIn("edit: run RealismFlow/1001 in Slurm job 1000001 on host edit-node", edit_part)
        self.assertIn("GPU EDIT GPU, CUDA 12.0 (edit/inputs.json", edit_part)
        self.assertIn("run RealismFlow/2002 in Slurm job 2000002 on host stats-node", stats_part)
        self.assertIn("GPU STATS GPU, CUDA 12.1 (environment.json", stats_part)
        self.assertNotIn("EDIT GPU", stats_part)
        code = reforms["2b"]["evidence"]
        self.assertIn("edit: commit aaaaaaa from a clean tree, key 0000000000000001, run RealismFlow/1001 (edit/RECORD.json)", code)
        self.assertIn("stats: commit bbbbbbb from a clean tree, key 0000000000000001, run RealismFlow/2002 (RECORD.json)", code)
        software = claim["23"]["evidence"]
        self.assertIn("the edit job, as edit/inputs.json measured them at its start: cuda 12.0, diffusers 0.42.0, torch 2.0.0; "
                      "3 distributions installed in all, each named in the file; pins that differ: none", software)
        self.assertNotIn("card_ok", software)
        self.assertIn("the stats job, as environment.json measured them at its start: cuda 12.1, diffusers 0.42.0, torch 2.0.1", software)
        self.assertIn("the same bundle the edit's filter read", claim["24"]["evidence"])
        self.assertIn("for the statistics' flexray and imagenet spaces (environment.json)", claim["7"]["evidence"])
        page = (self.stats / "REPORT.md").read_text(encoding="utf-8")
        self.assertIn("- The edit job (edit/RECORD.json): run RealismFlow/1001", page)
        self.assertIn("- The stats job (RECORD.json): run RealismFlow/2002", page)

    def test_a_stats_job_whose_bundle_is_not_the_edit_s_says_so(self):
        stats = self.make_stats(self.another("stats-0000000000000002-2003"), self.edit, bundle_sha256="7" * 64)
        self.assertIn("other bundle bytes than the edit's filter read", self.rows(stats, "claim")["24"]["evidence"])

    def test_a_stats_run_without_its_own_environment_record_leaves_what_it_ran_on_missing(self):
        stats = self.make_stats(self.another("stats-0000000000000002-2004"), self.edit, environment=False)
        rows = self.both(stats)
        for item in ("REFORMS 2c", "CLAIM 23", "CLAIM 24", "CLAIM 7"):
            self.assertEqual(rows[item]["state"], "missing", item)
            self.assertIn("environment.json is not among the files the record names", rows[item]["evidence"], item)

    def test_a_dirty_tree_leaves_the_code_missing_in_either_job(self):
        edit = self.make_edit(self.another("edit-0000000000000001-1005"), clean_tree=False)
        code = self.rows(edit, "reforms")["2b"]
        self.assertEqual(code["state"], "missing")
        self.assertIn("began on commit aaaaaaa from a DIRTY tree and ended on commit aaaaaaa from a DIRTY tree, so the commit "
                      "does not say which code ran", code["evidence"])
        stats = self.make_stats(self.another("stats-0000000000000002-2005"), edit)
        code = self.rows(stats, "reforms")["2b"]
        self.assertEqual(code["state"], "missing")
        self.assertIn("the edit job (edit/RECORD.json) began on commit aaaaaaa from a DIRTY tree", code["evidence"])
        stats = self.make_stats(self.another("stats-0000000000000002-2006"), self.edit, clean_tree=False)
        code = self.rows(stats, "reforms")["2b"]
        self.assertEqual(code["state"], "missing")
        self.assertIn("the stats job (RECORD.json) began on commit bbbbbbb from a DIRTY tree", code["evidence"])

    def test_a_start_or_an_end_whose_commit_or_tree_was_not_read_leaves_the_code_missing(self):
        # git not read at the start, as an empty commit; a resume that ended on a dirty tree; and a
        # record from before the flow read the code at both ends
        for n, extra, words in ((1, {"where": {"commit": None, "clean_tree": False}}, "began on a commit not recorded"),
                                (2, {"ended_in": {"run": "RealismFlow/1099", "clean_tree": False}},
                                 "ended on commit aaaaaaa from a DIRTY tree"),
                                (3, {"where": {"commit": None, "clean_tree": None}, "ended_in": {"commit": None, "clean_tree": None}},
                                 "began on a commit not recorded and ended on a commit not recorded")):
            edit = self.make_edit(self.another(f"edit-0000000000000001-11{n:02d}"), **extra)
            code = self.rows(edit, "reforms")["2b"]
            self.assertEqual(code["state"], "missing", n)
            self.assertIn(words, code["evidence"], n)

    def test_a_resume_that_ended_on_a_later_commit_of_the_same_key_says_both(self):
        resumed = {"run": "RealismFlow/1111", "commit": "c" * 40}
        edit = self.make_edit(self.another("edit-0000000000000001-1110"), ended_in=resumed)
        code = self.rows(edit, "reforms")["2b"]
        self.assertEqual(code["state"], "met")
        self.assertIn("commit aaaaaaa, resumed to its end on commit ccccccc of the same run key, each from a clean tree, key", code["evidence"])

    def test_one_run_whose_checkout_moved_under_it_leaves_the_code_missing(self):
        # the same run at both ends on two commits is no resume, which the run key holds to one code
        moved = {"commit": "c" * 40}
        edit = self.make_edit(self.another("edit-0000000000000001-1140"), ended_in=moved)
        code = self.rows(edit, "reforms")["2b"]
        self.assertEqual(code["state"], "missing")
        self.assertIn("began on commit aaaaaaa and ended on commit ccccccc in the same run RealismFlow/1140, the checkout moved "
                      "under it", code["evidence"])

    def test_a_resume_outside_slurm_is_not_taken_for_the_job_that_began_it(self):
        # no Slurm job on either side says nothing of whether the resume ran where the start did
        alone = {"slurm_job": "none", "host": "edit-node"}
        edit = self.make_edit(self.another("edit-0000000000000001-1120"), where=alone,
                              ended_in={**alone, "run": "RealismFlow/1121", "ended": "2026-10-29 05:00:00"})
        reforms = self.rows(edit, "reforms")
        self.assertEqual(reforms["2c"]["state"], "missing")
        self.assertIn("in Slurm job none on host edit-node and resumed to its end by run RealismFlow/1121", reforms["2c"]["evidence"])
        # one run outside Slurm, never resumed, is one job
        edit = self.make_edit(self.another("edit-0000000000000001-1122"), where=alone, ended_in={**alone, "run": "RealismFlow/1122"})
        self.assertEqual(self.rows(edit, "reforms")["2c"]["state"], "met")

    def test_the_page_says_not_recorded_where_a_record_holds_no_end(self):
        edit = self.make_edit(self.another("edit-0000000000000001-1130"), ended_in={"ended": None, "host": None})
        self.rows(edit, "reforms")
        page = (edit / "REPORT.md").read_text(encoding="utf-8")
        self.assertIn("ended not recorded UTC in Slurm job not recorded on host not recorded", page)
        self.assertNotIn("None", page)

    def test_a_stage_resumed_in_another_job_names_both_runs_and_leaves_its_card_unknown(self):
        resumed = {"run": "RealismFlow/1009", "host": "other-node", "slurm_job": "1000009", "ended": "2026-10-29 05:00:00"}
        edit = self.make_edit(self.another("edit-0000000000000001-1006"), ended_in=resumed)
        stats = self.make_stats(self.another("stats-0000000000000002-2007"), edit)
        rows = self.both(stats)
        self.assertEqual(rows["REFORMS 2b"]["state"], "met")
        self.assertIn("started by run RealismFlow/1006 and, resumed, ended by run RealismFlow/1009", rows["REFORMS 2b"]["evidence"])
        for item in ("REFORMS 2c", "CLAIM 23"):
            self.assertEqual(rows[item]["state"], "missing", item)
            self.assertIn("begun by run RealismFlow/1006 in Slurm job 1000001 on host edit-node and resumed to its end by run "
                          "RealismFlow/1009 in Slurm job 1000009 on host other-node", rows[item]["evidence"], item)
        self.assertIn("ended 2026-10-29 05:00:00 UTC in Slurm job 1000009 on host other-node",
                      (stats / "REPORT.md").read_text(encoding="utf-8"))

    def test_a_stage_resumed_in_the_same_job_is_met_and_names_both_runs(self):
        resumed = {"run": "RealismFlow/1010", "host": "edit-node", "slurm_job": "1000001", "ended": "2026-10-29 05:00:00"}
        edit = self.make_edit(self.another("edit-0000000000000001-1007"), ended_in=resumed)
        reforms = self.rows(edit, "reforms")
        self.assertEqual(reforms["2c"]["state"], "met")
        self.assertIn("started by run RealismFlow/1007 and, resumed, ended by run RealismFlow/1010", reforms["2b"]["evidence"])

    def test_a_record_that_names_no_ended_run_leaves_code_and_compute_missing(self):
        edit = self.make_edit(self.another("edit-0000000000000001-1008"), ended_in=None)
        reforms = self.rows(edit, "reforms")
        self.assertEqual((reforms["2b"]["state"], reforms["2c"]["state"]), ("missing", "missing"))
        self.assertIn("names no ended_in, the run that ended the folder", reforms["2b"]["evidence"])
        self.assertIn("names no ended_in", reforms["2c"]["evidence"])

    def copied_edit(self, change):
        """The stats run's copy of the edit's record changed after the stats record was written."""
        record = json.loads((self.stats / "edit" / "RECORD.json").read_text(encoding="utf-8"))
        change(record)
        write(self.stats / "edit" / "RECORD.json", json.dumps(record))

    def assert_edit_unread(self, said):
        rows = self.both(self.stats)
        for item in ("CLAIM 35", "REFORMS 4b", "REFORMS 2b", "CLAIM 7"):
            self.assertEqual(rows[item]["state"], "missing", item)
            self.assertIn(said, rows[item]["evidence"], item)
            self.assertIn("so the edit the statistics read is not known", rows[item]["evidence"], item)
        self.assertIn(f"- The edit job: not read, {said}", (self.stats / "REPORT.md").read_text(encoding="utf-8"))

    def test_a_copied_edit_record_that_names_other_files_than_the_stats_record_is_not_read(self):
        self.copied_edit(lambda record: record["files"].update({"inputs.json": "9" * 64}))
        self.assert_edit_unread("edit/RECORD.json names other bytes for inputs.json than the stats record")

    def test_a_copied_edit_record_of_another_run_than_the_copied_ended_json_is_not_read(self):
        self.copied_edit(lambda record: record["where"].update({"run": "RealismFlow/1999"}))
        self.assert_edit_unread("edit/RECORD.json and edit/ENDED.json name another started_run")

    def test_a_copied_edit_record_the_stats_record_names_is_read_only_as_those_bytes(self):
        record = json.loads((self.stats / "RECORD.json").read_text(encoding="utf-8"))
        record["files"]["edit/RECORD.json"] = sha256(self.stats / "edit" / "RECORD.json")
        write(self.stats / "RECORD.json", json.dumps(record))
        self.assertEqual(self.rows(self.stats, "reforms")["4b"]["state"], "met")
        self.copied_edit(lambda record: record["counts"].update({"kept": 8}))
        self.assert_edit_unread("edit/RECORD.json is not the file the record names")

    def test_the_components_each_space_was_read_on_are_quoted_and_their_absence_is_missing(self):
        claim = self.rows(self.stats, "claim")
        self.assertIn("k by space physics 57, flexray 64, imagenet 64", claim["28"]["evidence"])
        self.assertIn(f"{AFTER_FREEZE} 2", claim["28"]["evidence"])
        self.assertIn("kept physics: AUC 0.520 [0.470, 0.570], MMD q 0.5 on 57 components", claim["37"]["evidence"])
        kept = without(stats(0.52, "indistinguishable"), "components")
        stats_folder = self.make_stats(self.another("stats-0000000000000002-2008"), self.edit, kept=kept)
        rows = self.both(stats_folder)
        for item in ("CLAIM 28", "CLAIM 37", "REFORMS 7a"):
            self.assertEqual(rows[item]["state"], "missing", item)
            self.assertIn("needs the number of principal components each space was read on", rows[item]["evidence"], item)

    def test_the_strata_each_test_shuffled_within_are_quoted_and_their_absence_is_missing(self):
        reforms = self.rows(self.stats, "reforms")
        said = ("a against b by sample, b's split halves by subject, the arm null by sample, arm 0 against b by sample, "
                "arm 1 against b by sample")
        self.assertIn(f"in both comparisons alike, {said}", reforms["7c"]["evidence"])
        self.assertIn(f"in both comparisons alike, {said}", reforms["6b"]["evidence"])
        raw = without(stats(0.9, "separable"), "strata")
        stats_folder = self.make_stats(self.another("stats-0000000000000002-2009"), self.edit, raw=raw)
        rows = self.both(stats_folder)
        for item in ("REFORMS 7c", "REFORMS 6b", "CLAIM 20"):
            self.assertEqual(rows[item]["state"], "missing", item)
            self.assertIn("needs the strata each permutation test shuffled within", rows[item]["evidence"], item)

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
        report.RUNS = self.root / "no-training-runs"
        drr = report.STUDIES["drr-domain-gap"]
        self.addCleanup(drr.update, dict(drr))
        drr["runs"] = self.root / "no-drr-runs"
        self.assertEqual([name for name, _ in report.recorded_studies()], [STUDY, STUDY])
        self.assertEqual(quiet(report.main, ["check-recorded"]), 1)
        self.assertEqual(quiet(report.main, ["write-recorded"]), 0)
        self.assertEqual(quiet(report.main, ["check-recorded"]), 0)


class DesignTest(RealismFolder):
    """The answers that restate PREREG.md, DEVIATIONS.md or README.md hold only for a run whose
    records name the frozen PREREG's digest; every other answer reads the run's files alone."""

    @staticmethod
    def cites_the_design(evidence):
        return any(name in evidence for name in ("PREREG.md", "DEVIATIONS.md", "README.md"))

    def test_the_design_is_the_frozen_prereg_s_digest(self):
        self.assertEqual(report.REALISM.DESIGN, DESIGN)
        self.assertEqual(hashlib.sha256(PREREG.read_bytes()).hexdigest(), DESIGN)

    def test_answers_that_restate_the_design_are_missing_for_another_design_and_the_rest_unchanged(self):
        ours = self.both(self.stats)
        # the same run ids under another folder, so only the digest the records name differs
        edit = self.make_edit(self.another("other/edit-0000000000000001-1001"), prereg_sha256=OTHER_DESIGN)
        theirs = self.both(self.make_stats(self.another("other/stats-0000000000000002-2002"), edit, prereg_sha256=OTHER_DESIGN))
        restating = [item for item, row in ours.items() if row["basis"] == "code" and self.cites_the_design(row["evidence"])]
        self.assertGreater(len(restating), 40)
        for item, row in ours.items():
            if item in restating:
                self.assertEqual(theirs[item]["state"], "missing", item)
                self.assertIn("names PREREG sha256 5555555555555555, and these answers restate PREREG.md", theirs[item]["evidence"], item)
            elif row["basis"] == "code":
                self.assertEqual(theirs[item], row, item)

    def test_a_stats_run_whose_edit_ran_another_design_is_held_to_it_too(self):
        edit = self.make_edit(self.another("edit-0000000000000001-1012"), prereg_sha256=OTHER_DESIGN)
        aims = self.rows(self.make_stats(self.another("stats-0000000000000002-2011"), edit), "claim")["4"]
        self.assertEqual(aims["state"], "missing")
        self.assertIn("the edit's record (edit/RECORD.json) names PREREG sha256 5555555555555555", aims["evidence"])
        edit = self.make_edit(self.another("edit-0000000000000001-1013"), prereg_sha256=None)
        aims = self.rows(edit, "claim")["4"]
        self.assertEqual(aims["state"], "missing")
        self.assertIn("names no PREREG sha256", aims["evidence"])

    def test_answers_that_restate_a_departure_quote_the_prereg_and_its_entry(self):
        rows = self.both(self.stats)
        for item, entry, section in (("REFORMS 7c", 1, "section 3"), ("CLAIM 28", 2, "section 3"), ("REFORMS 6a", 2, "section 3"),
                                     ("CLAIM 8", 3, "section 2"), ("REFORMS 3b", 3, "section 2"), ("CLAIM 12", 3, "section 2")):
            self.assertIn(f"PREREG.md {section}", rows[item]["evidence"], item)
            self.assertIn(f"{AFTER_FREEZE} {entry}", rows[item]["evidence"], item)
        self.assertIn("the question, PREREG.md section 1", rows["CLAIM 4"]["evidence"])

    def test_items_whose_object_the_design_leaves_out_are_not_applicable_with_the_reason(self):
        rows = self.both(self.stats)
        for item in ("CLAIM 14", "CLAIM 15", "CLAIM 16", "CLAIM 17", "CLAIM 18", "CLAIM 25", "CLAIM 26", "CLAIM 27",
                     "CLAIM 33", "CLAIM 34", "CLAIM 36", "CLAIM 38", "CLAIM 39", "REFORMS 5a", "REFORMS 5d", "REFORMS 5e"):
            self.assertEqual(rows[item]["state"], "not applicable", item)
            self.assertTrue(rows[item]["evidence"].startswith("not applicable: "), item)
            self.assertTrue(self.cites_the_design(rows[item]["evidence"]), item)


class RulesTest(unittest.TestCase):
    def test_every_item_the_study_answers_by_code_has_a_fact(self):
        for key, checklist in report.checklists().items():
            for item in checklist["items"]:
                basis, fact = report.study_basis(key, item, STUDY)
                self.assertIn(basis, ("code", "declared"), item["id"])
                if basis == "code":
                    self.assertIn(fact, report.REALISM.FACTS, item["id"])

    def test_the_owner_answers_only_what_no_file_of_the_study_says(self):
        self.assertEqual(report.study_declared_facts(STUDY), OWNER_ITEMS)

    def test_the_study_s_answers_file_holds_the_owner_s_items_and_none_filled(self):
        path = ROOT / "data" / "reporting" / "studies" / f"{STUDY}.json"
        answers = report.study_answers(path)
        self.assertEqual(set(answers), OWNER_ITEMS)
        self.assertEqual([fact for fact, text in answers.items() if text], [])
        about = json.loads(path.read_text(encoding="utf-8"))["_about"]
        self.assertIn("A session copies into a field only the owner's own words", about)


if __name__ == "__main__":
    unittest.main()
