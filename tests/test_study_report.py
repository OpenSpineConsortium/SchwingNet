"""Study mode of the run report (tools/report.py --study): a study that trains no network, read from
its recorded folder, every code answer taken from its record lines, its summary or the table the
record names and never guessed, and every owner item missing until the owner writes it."""

import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "report-study" / "1000001"
STUDY = "drr-domain-gap"
# A licence register of the fixture's own, so no test reads data/licences.json: one source by its
# id, one through an alias, and the fixture's two folders with no entry.
REGISTER = {
    "aliases": {"fixture_film_alias": "fixture_film_entry"},
    "sources": {
        "fixture_fluoro_source": {"licence": "fixture", "class": "open", "reviewed": "rule"},
        "fixture_film_entry": {"licence": "fixture", "class": "non-commercial", "reviewed": "owner 2000-01-01"},
    },
}


def load_report():
    spec = importlib.util.spec_from_file_location("report_under_test", ROOT / "tools" / "report.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


report = load_report()


def quiet(function, *args, **kwargs):
    with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
        return function(*args, **kwargs)


class StudyFolder(unittest.TestCase):
    """Each test copies the fixture into a folder of its own and reads answers and a licence
    register of its own, so the repository's study files are never read for it or written."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        root = Path(self.folder.name)
        self.run = root / "runs" / FIXTURE.name
        shutil.copytree(FIXTURE, self.run)
        self.answers = root / "answers.json"
        self.write_answers({})
        register = root / "licences.json"
        register.write_text(json.dumps(REGISTER), encoding="utf-8")
        # a frozen pre-registration of the fixture's own, its digest written into the record line
        prereg = root / "PREREG.md"
        prereg.write_text("fixture pre-registration, frozen\n", encoding="ascii")
        self.prereg = report.dashed(hashlib.sha256(prereg.read_bytes()).hexdigest()[:16])
        self.replace_line("record: study ", self.lines()[0].replace("PREREG 2222-2222-2222-2222", f"PREREG {self.prereg}"))
        # a README of the fixture's own whose section 6 records the run and what it does not support
        self.readme = root / "README.md"
        self.readme.write_text("# Fixture study\n\n## 6. Results\n\nThe fixture run is recorded under runs/1000001/.\n\n"
                               "What the run does not support, in the fixture: its film persons are files.\n\n## 7. How to run it\n", encoding="ascii")
        config = report.STUDIES[STUDY]
        self.addCleanup(config.update, dict(config))
        config.update(answers=self.answers, runs=root / "runs", prereg=prereg, design=self.prereg, readme=self.readme)
        self.addCleanup(setattr, report, "LICENCES", report.LICENCES)
        report.LICENCES = register

    def write_answers(self, answers):
        self.answers.write_text(json.dumps({"_about": "test", **answers}), encoding="utf-8")

    def lines(self):
        return (self.run / "summary.txt").read_text(encoding="utf-8").splitlines()

    def write_lines(self, lines):
        (self.run / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def replace_line(self, start, new):
        """The summary line that starts so replaced by new, or dropped where new is None."""
        self.write_lines([line if not line.startswith(start) else new for line in self.lines() if not (line.startswith(start) and new is None)])

    def rows(self, checklist):
        report.write(self.run, STUDY)
        return {row["id"]: row for row in json.loads((self.run / f"{checklist}.json").read_text(encoding="utf-8"))["items"]}

    def text(self):
        return (self.run / "REPORT.md").read_text(encoding="utf-8")


class RecordTest(StudyFolder):
    def test_the_record_lines_are_read_by_their_forms(self):
        fields, problems, unknown, body = report.record_of(self.lines(), STUDY)
        self.assertEqual((problems, unknown), ({}, []))
        self.assertEqual({key: fields["study"][key] for key in ("commit", "tree", "seed", "groups", "prereg")},
                         {"commit": "0000000", "tree": "clean", "seed": "0", "groups": "7e1b-145e-9d74-759a", "prereg": self.prereg})
        self.assertEqual((fields["jobs"]["prepare"], fields["jobs"]["tasks"], fields["jobs"]["gpu"], fields["jobs"]["gpus"]),
                         ("1000001", "4", "FIXTURE GPU", "1"))
        self.assertEqual((fields["units"]["done"], fields["units"]["backend"]), ("4", "numpy"))
        self.assertEqual((fields["seconds"]["analysis"], fields["seconds"]["figures"]), ("6", "8"))
        self.assertEqual(fields["environment"]["pins"], "fixture-package 0.0.0 other-fixture-package 0.0.0")
        self.assertTrue(body[0].startswith("drr gap: "))

    def test_a_serial_run_writes_its_one_job(self):
        self.replace_line("record: jobs", "record: jobs run local; GPUs FIXTURE GPU x1")
        fields, problems, _, _ = report.record_of(self.lines(), STUDY)
        self.assertEqual((problems, fields["jobs"]["run"]), ({}, "local"))
        compute = self.rows("reforms")["2c"]
        self.assertEqual(compute["state"], "met")
        self.assertIn("one job, run local, on GPUs FIXTURE GPU x1", compute["evidence"])

    def test_the_array_forms_a_local_step_and_a_missing_array_write_are_read(self):
        for jobs, array in (("prepare local, array none (0 tasks), merge local", "none"),
                            ("prepare 1000001, array 1000002, 1000004 (5 tasks), merge 1000003", "1000002, 1000004")):
            self.replace_line("record: jobs", f"record: jobs {jobs}; GPUs FIXTURE GPU x1")
            fields, problems, _, _ = report.record_of(self.lines(), STUDY)
            self.assertEqual((problems, fields["jobs"]["array"]), ({}, array), jobs)

    def test_a_digest_written_whole_is_out_of_its_form(self):
        self.replace_line("record: study ", self.lines()[0].replace("code 3333-3333-3333-3333", "code 3333333333333333"))
        _, problems, _, _ = report.record_of(self.lines(), STUDY)
        self.assertEqual(problems, {"study": "not in its form"})

    def test_pins_the_step_did_not_give_leave_the_software_item_missing(self):
        self.replace_line("record: environment", "record: environment not given")
        software = self.rows("claim")["23"]
        self.assertEqual(software["state"], "missing")
        self.assertIn("SN_PINS", software["evidence"])

    def test_a_line_out_of_its_form_given_twice_or_after_the_summary_is_not_read(self):
        lines = self.lines()
        study = lines[0].replace("commit 0000000", "commit 00000000")
        units = next(line for line in lines if line.startswith("record: units"))
        seconds = next(line for line in lines if line.startswith("record: seconds"))
        rest = [line for line in lines[1:] if line != seconds]
        _, problems, _, _ = report.record_of([study, units, *rest[:-1], seconds], STUDY)
        self.assertEqual(problems, {"study": "not in its form", "units": "given 2 times", "seconds": "absent"})
        other = lines[0].replace("study drr-domain-gap", "study other-study")
        _, problems, _, _ = report.record_of([other, *lines[1:]], STUDY)
        self.assertEqual(problems, {"study": "names study other-study"})

    def test_digests_the_record_names_as_none_are_read_and_answer_nothing(self):
        line = self.lines()[0].replace("groups.json 7e1b-145e-9d74-759a", "groups.json none").replace(f"PREREG {self.prereg}", "PREREG none")
        self.replace_line("record: study", line)
        claim = self.rows("claim")
        self.assertEqual(claim["7"]["state"], "missing")
        self.assertIn("the record names none", claim["7"]["evidence"])
        self.assertEqual(claim["26"]["state"], "not applicable")
        self.assertIn("PREREG none", claim["26"]["evidence"])


class MissingRecordLineTest(StudyFolder):
    def test_an_absent_line_makes_its_items_missing_and_no_others(self):
        self.replace_line("record: seconds", None)
        reforms = self.rows("reforms")
        self.assertEqual(reforms["2c"]["state"], "missing")
        self.assertIn("'record: seconds ...' (absent)", reforms["2c"]["evidence"])
        self.assertEqual(reforms["2b"]["state"], "met")
        self.assertIn("seconds absent", self.text())

    def test_without_the_study_line_its_items_are_missing_never_not_applicable(self):
        self.replace_line("record: study", None)
        claim = self.rows("claim")
        for item in ("4", "7", "9", "14", "19", "26", "33", "34", "38"):
            self.assertEqual(claim[item]["state"], "missing", item)
            self.assertIn("'record: study ...' (absent)", claim[item]["evidence"], item)
        self.assertEqual(claim["35"]["state"], "met")
        self.assertIn("Not recorded: the report needs summary.txt's record line", self.text())

    def test_units_not_all_done_leave_the_results_missing(self):
        self.replace_line("record: units", "record: units 3 of 4 done, 1 failed; mmd backend numpy")
        claim = self.rows("claim")
        for item in ("32", "37"):
            self.assertEqual(claim[item]["state"], "missing", item)
            self.assertIn("units 3 of 4 done, 1 failed", claim[item]["evidence"], item)
        self.assertEqual(claim["28"]["state"], "met")

    def test_a_dirty_tree_is_never_met(self):
        self.replace_line("record: study", self.lines()[0].replace("tree clean", "tree dirty"))
        code = self.rows("reforms")["2b"]
        self.assertEqual(code["state"], "missing")
        self.assertIn("DIRTY tree", code["evidence"])
        self.assertIn("Study record: commit 0000000, DIRTY tree", self.text())

    def test_a_bench_report_on_another_commit_or_a_moved_checkout_is_never_met(self):
        bench = self.run / "BENCH.md"
        original = bench.read_text(encoding="utf-8")
        bench.write_text(original.replace("commit 0000000", "commit 1234567"), encoding="utf-8")
        self.assertIn("BENCH.md names commit 1234567", self.rows("reforms")["2b"]["evidence"])
        bench.write_text(original + "- FAILED: the checkout moved from 0000000 to 1234567 during the benchmark\n", encoding="utf-8")
        code = self.rows("reforms")["2b"]
        self.assertEqual(code["state"], "missing")
        self.assertIn("the checkout moved", code["evidence"])


class RunLogTest(StudyFolder):
    # the owner's ask of 2026-10-28 00:23 UTC, "make sure there is realtime logging in the
    # CLAIMS/REPORT": the run log the merge wrote into BENCH.md is copied whole into the report's
    # section Run log, its span cited by REFORMS 2c, and a report with none says why
    def bench(self):
        return (self.run / "BENCH.md").read_text(encoding="utf-8")

    def test_the_run_log_is_copied_whole_and_its_span_is_cited(self):
        compute = self.rows("reforms")["2c"]
        self.assertEqual(compute["state"], "met")
        self.assertIn("run log: 6 lines in BENCH.md, 2000-01-01 00:00:00 to 2000-01-01 00:00:07 UTC, shown in the section Run log",
                      compute["evidence"])
        text = self.text()
        self.assertIn("- BENCH.md's run log: 6 lines in BENCH.md, 2000-01-01 00:00:00 to 2000-01-01 00:00:07 UTC", text)
        section = text[text.index("## Run log\n"):]
        logged = [line[2:] for line in self.bench().splitlines() if line.startswith("  2000-")]
        self.assertEqual(len(logged), 6)
        self.assertIn("```text\n" + "\n".join(logged) + "\n```\n", section)
        self.assertLess(text.index("## REFORMS"), text.index("## Run log"))

    def test_lines_after_the_run_log_and_an_earlier_one_are_not_its_own(self):
        bench = self.bench().replace("- run log, UTC: ", "- run log, UTC: an earlier one\n  2000-01-01 00:00:00 old line\n- next\n- run log, UTC: ", 1)
        (self.run / "BENCH.md").write_text(bench + "  2000-01-01 00:00:09 after the exit\n", encoding="utf-8")
        self.assertIn("run log: 6 lines in BENCH.md", self.rows("reforms")["2c"]["evidence"])
        section = self.text().split("## Run log\n", 1)[1]
        self.assertNotIn("old line", section)
        self.assertNotIn("after the exit", section)
        self.assertIn("merge: results.json, the figures and summary.txt written\n```", section)

    def test_a_report_with_no_run_log_says_why(self):
        kept = [line for line in self.bench().splitlines() if not line.startswith(("- run log", "  2000-"))]
        (self.run / "BENCH.md").write_text("\n".join(kept) + "\n", encoding="utf-8")
        self.assertIn("run log: none (BENCH.md carries no run log: the run began 2000-01-01 00:00:00 UTC, before the study wrote"
                      " one (2026-10-28))", self.rows("reforms")["2c"]["evidence"])
        self.assertIn("## Run log\n\nNone: BENCH.md carries no run log", self.text())
        # a run its header dates after the study began writing one is never said to have come before
        later = [line.replace("2000-01-01 00:00:00 UTC", "2026-11-02 09:00:00 UTC", 1) if line.startswith("# bench ") else line
                 for line in kept]
        self.assertNotEqual(later, kept)
        (self.run / "BENCH.md").write_text("\n".join(later) + "\n", encoding="utf-8")
        evidence = self.rows("reforms")["2c"]["evidence"]
        self.assertIn("run log: none (BENCH.md carries no run log line, though the run began 2026-11-02 09:00:00 UTC)", evidence)
        self.assertNotIn("before the study", evidence)
        (self.run / "BENCH.md").write_text("\n".join(kept[:-1] + ["- run log: not read, since the study's environment was not made.", kept[-1]]) + "\n",
                                           encoding="utf-8")
        self.assertIn("run log: none (not read, since the study's environment was not made)", self.rows("reforms")["2c"]["evidence"])
        self.assertIn("None: not read, since the study's environment was not made.\n", self.text())

    def test_no_line_of_the_run_log_can_close_its_block(self):
        bench = self.bench().replace("- exit ", "  ```\n  2000-01-01 00:00:08 a line with ```` four\n- exit ", 1)
        (self.run / "BENCH.md").write_text(bench, encoding="utf-8")
        self.assertIn("run log: 8 lines in BENCH.md", self.rows("reforms")["2c"]["evidence"])
        section = self.text().split("## Run log\n", 1)[1]
        self.assertIn("\n`````text\n", section)
        self.assertIn("written\n```\n2000-01-01 00:00:08 a line with ```` four\n`````\n", section)
        self.assertEqual(section.count("`````"), 2)


class NotApplicableTest(StudyFolder):
    def test_what_the_design_leaves_out_says_why_and_names_the_run(self):
        claim, reforms = self.rows("claim"), self.rows("reforms")
        for row in (*(claim[item] for item in ("14", "15", "16", "17", "18", "26", "33", "34", "38", "39")), reforms["5d"], reforms["5e"]):
            self.assertEqual(row["state"], "not applicable", row["id"])
            self.assertTrue(row["evidence"].startswith("Not applicable: the study "), row["id"])
            self.assertIn("study drr-domain-gap, commit 0000000, code 3333-3333-3333-3333", row["evidence"])
        self.assertIn(f"PREREG.md {self.prereg}", claim["26"]["evidence"])
        self.assertIn("trains no model", claim["33"]["evidence"])

    def test_a_record_naming_another_pre_registration_answers_nothing_that_reads_it(self):
        self.replace_line("record: study ", self.lines()[0].replace(f"PREREG {self.prereg}", "PREREG 2222-2222-2222-2222"))
        claim, reforms = self.rows("claim"), self.rows("reforms")
        for row in (claim["4"], claim["26"], claim["42"], reforms["1a"], reforms["5d"], reforms["2d"]):
            self.assertEqual(row["state"], "missing", row["id"])
            self.assertIn("the record names PREREG 2222-2222-2222-2222, which is not the frozen ", row["evidence"])

    def test_only_code_items_are_not_applicable_by_code(self):
        rows = {**self.rows("claim"), **{f"R{key}": row for key, row in self.rows("reforms").items()}}
        for row in rows.values():
            if row["state"] == "not applicable":
                self.assertEqual(row["basis"], "code", row["id"])


class DesignTest(StudyFolder):
    """The answers that restate the frozen design hold only for a run whose record names it, and the
    answers that read the table or the summary quote them."""

    DESIGN = {"claim": ("4", "6", "8", "21", "30", "31", "34", "39", "40", "42"),
              "reforms": ("1a", "1b", "1c", "3b", "3c", "3g", "5e", "5f", "6c", "7c")}

    def design_rows(self):
        return [row for key, items in self.DESIGN.items() for row in map(self.rows(key).get, items)]

    def test_the_design_answers_hold_for_the_design_the_record_names(self):
        for row in self.design_rows():
            self.assertIn(row["state"], ("met", "not applicable"), row["id"])
            self.assertEqual(row["basis"], "code", row["id"])

    def test_a_design_other_than_the_one_the_answers_restate_leaves_them_missing(self):
        report.STUDIES[STUDY]["design"] = "4444-4444-4444-4444"
        for row in self.design_rows():
            self.assertEqual(row["state"], "missing", row["id"])
            self.assertIn(f"the record names PREREG {self.prereg}, and these answers restate PREREG.md 4444-4444-4444-4444", row["evidence"], row["id"])
        self.assertEqual(self.rows("claim")["14"]["state"], "not applicable")

    def test_a_record_naming_no_pre_registration_leaves_the_design_answers_missing(self):
        self.replace_line("record: study ", self.lines()[0].replace(f"PREREG {self.prereg}", "PREREG none"))
        for row in self.design_rows():
            self.assertEqual(row["state"], "missing", row["id"])
            self.assertIn("the record names none (PREREG none)", row["evidence"], row["id"])

    def test_what_the_table_answers_is_missing_without_it(self):
        (self.run / "groups.json").unlink()
        claim, reforms = self.rows("claim"), self.rows("reforms")
        for row in (claim["8"], claim["21"], reforms["1a"], reforms["3b"], reforms["3g"]):
            self.assertEqual(row["state"], "missing", row["id"])
            self.assertIn("needs the groups table the record names", row["evidence"], row["id"])

    def test_the_table_and_the_summary_are_quoted(self):
        claim, reforms = self.rows("claim"), self.rows("reforms")
        self.assertIn("summary.txt carries flexray dim 8; flexray_as_stored dim 8; physics dim 4; imagenet not run (no ImageNet weights in this fixture);", claim["30"]["evidence"])
        self.assertIn("have none of their own: flexray_drr 10, flexray_drr_ct 10, fixture_fluoro 8", claim["30"]["evidence"])
        self.assertIn("1 group skipped, fluxray (not on the data root in this fixture); persons by file in fixture_film", claim["40"]["evidence"])
        self.assertIn("the calibration lines reading flexray mmd flagged none, auc interval above half 0; physics mmd flagged none, auc interval above half 0", claim["40"]["evidence"])
        self.assertIn('"What the run does not support, in the fixture: its film persons are files."', claim["40"]["evidence"])
        self.assertIn("render fixture_cts: 10 CTs chosen of 10", claim["21"]["evidence"])
        self.assertIn("; render fixture_cts: 10 CTs chosen of 10 with every mask of 12 CTs (moose 10); 10 kept by every group", claim["8"]["evidence"])
        self.assertIn("of which the analysis reads only those every render group on the folder kept (README section 7)", claim["8"]["evidence"])
        self.assertIn("the records of its ThunderDB as FleXray's reader lists them: fluxray", reforms["3b"]["evidence"])
        self.assertIn("salt fixture-salt", reforms["3b"]["evidence"])
        self.assertIn("synthetic, flexray_drr, flexray_drr_ct, fluxray; fluoroscopy, fixture_fluoro; film, fixture_film", reforms["1a"]["evidence"])
        self.assertIn("in the spaces flexray, physics", reforms["5f"]["evidence"])

    def test_a_flagged_null_is_named_where_the_design_s_failures_are(self):
        calibration = " calibration split-half auc median 0.33 range 0.32 to 0.34 over 1, mmd flagged 0, auc interval above half 0"
        lines = self.lines()
        at = lines.index(calibration)
        self.write_lines(lines[:at] + [calibration.replace("mmd flagged 0", "mmd flagged 1"), " calibration flagged flexray_drr"] + lines[at + 1:])
        claim = self.rows("claim")
        for item in ("39", "40"):
            self.assertIn("flexray mmd flagged flexray_drr, auc interval above half 0; physics mmd flagged none", claim[item]["evidence"], item)


    def test_a_flagged_count_its_lines_do_not_name_is_said_as_it_stands(self):
        self.replace_line(" calibration split-half auc median 0.33", " calibration split-half auc median 0.33 range 0.32 to 0.34 over 1, mmd flagged 1, auc interval above half 0")
        claim = self.rows("claim")
        for item in ("39", "40"):
            self.assertIn("flexray mmd flagged 1, its lines naming 0", claim[item]["evidence"], item)
            self.assertNotIn("flexray mmd flagged none", claim[item]["evidence"], item)

    def test_a_summary_with_no_group_line_leaves_what_reads_them_missing(self):
        self.write_lines([line for line in self.lines() if not line.startswith("group")])
        claim = self.rows("claim")
        for item in ("8", "40"):
            self.assertEqual(claim[item]["state"], "missing", item)
            self.assertIn("needs summary.txt's group lines", claim[item]["evidence"], item)

    def test_a_partial_run_points_at_no_answer_it_leaves_missing(self):
        self.replace_line("record: units", "record: units 3 of 4 done, 1 failed; mmd backend numpy")
        claim, reforms = self.rows("claim"), self.rows("reforms")
        self.assertEqual((claim["32"]["state"], claim["37"]["state"]), ("missing", "missing"))
        self.assertNotIn("CLAIM 32", reforms["5f"]["evidence"])
        self.assertIn("the primary endpoints are not read here", claim["39"]["evidence"])

    def test_the_paired_null_of_a_pair_on_the_same_persons_is_named(self):
        self.assertIn("the p holds under the null that a person's two sides are exchangeable (tools/domain_gap_stats.py, twin_swaps", self.rows("reforms")["7c"]["evidence"])

    def verdict(self, family):
        """The fixture with a not-replicated verdict that the MMD alone carries, its q taken with the
        split-half nulls in its family or without them."""
        calibration = " calibration split-half auc median 0.33 range 0.32 to 0.34 over 1, mmd flagged 0, auc interval above half 0"
        lines = self.lines()
        at = lines.index(calibration)
        pair = " replication flexray_replica vs flexray_reference persons 10/10 n 40/40 auc 0.50 [0.50, 0.50] p 0.455 knn 0.50 mmd p 0.043 q 0.046 fd64 0.0 kid64 -1.000 prdc 1.00 1.00 1.00 1.00 not replicated"
        self.write_lines(lines[:at] + [calibration + (", nulls in the mmd q family" if family else ""), pair] + lines[at + 1:])
        self.replace_line("replication flexray_replica vs flexray_reference", "replication flexray_replica vs flexray_reference in flexray (invariant): not replicated (persons 10/10 n 40/40; mmd q 0.046)")
        return self.rows("claim")

    def test_a_verdict_the_mmd_alone_carries_is_read_in_the_design_s_words(self):
        claim = self.verdict(True)
        for item in ("30", "39", "40"):
            evidence = claim[item]["evidence"]
            self.assertIn("in PREREG.md section 5's words this project's blocks did not reproduce FleXray's own renders of its recipe: the MMD told them apart (q 0.046)", evidence, item)
            self.assertIn("so the word rests on the MMD alone", evidence, item)

    def test_a_verdict_whose_q_left_the_nulls_out_is_not_the_frozen_rule_s(self):
        evidence = self.verdict(False)["30"]["evidence"]
        self.assertIn("so the frozen rule's word on the MMD is not read in this run", evidence)
        self.assertNotIn("in PREREG.md section 5's words", evidence)

    def test_the_limits_wait_for_the_readme_to_record_the_run(self):
        self.readme.write_text("# Fixture study\n\n## 6. Results\n\nNo run is recorded yet.\n\n## 7. How to run it\n", encoding="ascii")
        limits = self.rows("claim")["40"]
        self.assertEqual(limits["state"], "missing")
        self.assertIn("needs README section 6's record of this run (runs/1000001/)", limits["evidence"])

    def test_a_space_the_summary_does_not_name_is_said_to_be_given_up(self):
        lines = self.lines()
        at = lines.index("space physics dim 4 rows 160 spread 0.555 pca64 0.66")
        self.write_lines(lines[:at])
        self.assertIn("of the design's spaces and readings it does not name physics, which its 80-line budget gave up", self.rows("claim")["30"]["evidence"])

    def test_a_reading_of_a_space_that_did_not_run_was_never_made(self):
        lines = self.lines()
        start = lines.index("space flexray dim 8 rows 160 spread 0.111 pca64 0.22")
        end = lines.index("space imagenet not run, no ImageNet weights in this fixture")
        self.write_lines(lines[:start] + ["space flexray not run, no features"] + lines[end:])
        evidence = self.rows("claim")["30"]["evidence"]
        self.assertIn("flexray_as_stored was never made, since the space it reads had no features", evidence)
        self.assertNotIn("it does not name flexray_as_stored", evidence)

    def test_a_reading_of_a_space_whose_invariant_head_alone_failed_was_made(self):
        lines = self.lines()
        start = lines.index("space flexray dim 8 rows 160 spread 0.111 pca64 0.22")
        end = lines.index("space imagenet not run, no ImageNet weights in this fixture")
        self.write_lines(lines[:start] + ["space flexray not run, every image has the same features"] + lines[end:])
        evidence = self.rows("claim")["30"]["evidence"]
        self.assertIn("it does not name flexray_as_stored, which its 80-line budget gave up", evidence)
        self.assertNotIn("never made", evidence)

    def test_the_verdict_is_the_verdict_pair_s_and_no_other_pair_s(self):
        lines = self.lines()
        at = next(i for i, line in enumerate(lines) if line.startswith("replication flexray_replica vs flexray_reference"))
        other = "replication fluxray_raw vs fluxray_raw_reference in flexray (invariant): replicated (persons 10/10 n 40/40; mmd q 0.910)"
        self.write_lines(lines[:at + 1] + [other] + lines[at + 1:])
        evidence = self.rows("claim")["30"]["evidence"]
        self.assertIn("the verdict pair, flexray_replica against flexray_reference, has no word, summary.txt giving its reason: flexray_replica: not in this fixture table", evidence)
        self.assertNotIn("reads replicated", evidence)

    def test_a_replicated_verdict_on_a_q_without_the_nulls_is_not_the_frozen_rule_s(self):
        calibration = " calibration split-half auc median 0.33 range 0.32 to 0.34 over 1, mmd flagged 0, auc interval above half 0"
        lines = self.lines()
        at = lines.index(calibration)
        pair = " replication flexray_replica vs flexray_reference persons 10/10 n 40/40 auc 0.50 [0.45, 0.55] p 0.455 knn 0.50 mmd p 0.060 q 0.070 fd64 0.0 kid64 -1.000 prdc 1.00 1.00 1.00 1.00 replicated"
        self.write_lines(lines[:at + 1] + [pair] + lines[at + 1:])
        self.replace_line("replication flexray_replica vs flexray_reference", "replication flexray_replica vs flexray_reference in flexray (invariant): replicated (persons 10/10 n 40/40; mmd q 0.070)")
        evidence = self.rows("claim")["30"]["evidence"]
        self.assertIn("reads replicated, the AUC's lower bound of 0.45 at most the bar of 0.6 and the MMD's q of 0.070 at least 0.05", evidence)
        self.assertIn("so the frozen rule's word on the MMD is not read in this run", evidence)

    def pair_verdict(self, lo, q, family, word="not replicated"):
        """The fixture with the verdict pair's line at this AUC lower bound and MMD q, its q's
        family the frozen one or the contrasts alone; CLAIM 30's evidence."""
        calibration = " calibration split-half auc median 0.33 range 0.32 to 0.34 over 1, mmd flagged 0, auc interval above half 0"
        self.base = getattr(self, "base", None) or self.lines()
        lines = list(self.base)
        at = lines.index(calibration)
        pair = f" replication flexray_replica vs flexray_reference persons 10/10 n 40/40 auc 0.80 [{lo}, 0.90] p 0.010 knn 0.80 mmd p 0.040 q {q} fd64 9.0 kid64 1.000 prdc 0.50 0.50 0.50 0.50 {word}"
        self.write_lines(lines[:at] + [calibration + (", nulls in the mmd q family" if family else ""), pair] + lines[at + 1:])
        self.replace_line("replication flexray_replica vs flexray_reference", f"replication flexray_replica vs flexray_reference in flexray (invariant): {word} (persons 10/10 n 40/40; mmd q {q})")
        return self.rows("claim")["30"]["evidence"]

    def test_a_verdict_the_classifier_decides_stands_under_either_family(self):
        evidence = self.pair_verdict("0.70", "0.300", False)
        self.assertIn("the classifier told them apart (AUC lower bound 0.70), which decides the word whichever family the MMD's q is taken over (DEVIATIONS.md, item 11); the MMD's q is 0.300; that q was taken over the space's contrasts alone", evidence)
        self.assertNotIn("rests on the classifier alone", evidence)
        self.assertIn("the classifier told them apart (AUC lower bound 0.70), the MMD's q of 0.300 being at least 0.05, so the word rests on the classifier alone", self.pair_verdict("0.70", "0.300", True))

    def test_the_mmd_s_bar_is_said_in_the_design_s_words_only_under_the_frozen_family(self):
        alone = self.pair_verdict("0.65", "0.048", False)
        self.assertIn("in PREREG.md section 5's words this project's blocks did not reproduce FleXray's own renders of its recipe: the classifier told them apart (AUC lower bound 0.65), which decides", alone)
        self.assertNotIn("the MMD told them apart", alone)
        self.assertIn("so the frozen rule's word on the MMD is not read in this run", alone)
        frozen = self.pair_verdict("0.65", "0.048", True)
        self.assertIn("the classifier told them apart (AUC lower bound 0.65) and the MMD told them apart (q 0.048);", frozen)

    def test_a_number_printed_at_its_bar_places_nothing(self):
        auc_at = self.pair_verdict("0.60", "0.046", True)
        self.assertIn("the MMD told them apart (q 0.046), the AUC's lower bound printed as 0.60, the bar of 0.6 to the digits the summary prints, so whether the classifier told them apart too is not read here", auc_at)
        self.assertNotIn("rests on the MMD alone", auc_at)
        mmd_at = self.pair_verdict("0.65", "0.050", True)
        self.assertIn("the MMD's q printed as 0.050, the bar of 0.05 to the digits the summary prints, so whether the MMD told them apart too is not read here", mmd_at)
        self.assertNotIn("rests on the classifier alone", mmd_at)

    def test_the_endpoints_item_reads_the_verdict_as_the_others_do(self):
        self.pair_verdict("0.50", "0.048", False)
        self.assertIn("read here, the verdict, flexray_replica against flexray_reference in the flexray space read inversion-invariant, reads not replicated, the MMD's q of 0.048 being under the bar of 0.05", self.rows("claim")["37"]["evidence"])

    def test_every_descriptive_line_the_summary_prints_is_named(self):
        lines = self.lines()
        at = lines.index(" fluoroscopy vs film auc 0.64 [0.63, 0.65] p 0.066")
        self.write_lines(lines[:at + 1] + [" silhouette 0.01", " nearest real; flexray_drr fixture_fluoro 90 pct", " tsne centres; flexray_drr 1.0 2.0 3.0"] + lines[at + 1:])
        self.assertIn("of these summary.txt prints PRDC, the silhouette, the nearest real corpora and the t-SNE map's group centres, and the rest are on the grid", self.rows("claim")["31"]["evidence"])

    def test_the_limits_are_this_run_s_own_or_held_by_its_own_part(self):
        earlier = "# Fixture study\n\n## 6. Results\n\nAn earlier run is recorded under runs/999999/.\n\nWhat the run does not support, in the earlier run: its persons are files.\n\n"
        self.readme.write_text(earlier + "### The fixture run\n\nThe fixture run is recorded under runs/1000001/.\n\n## 7. How to run it\n", encoding="ascii")
        limits = self.rows("claim")["40"]
        self.assertEqual(limits["state"], "missing")
        self.assertIn("its part says nothing of what the run does not support", limits["evidence"])
        self.readme.write_text(earlier + "### The fixture run\n\nThe fixture run is recorded under runs/1000001/.\n\nWhat the earlier run does not support holds for this one.\n\n## 7. How to run it\n", encoding="ascii")
        evidence = self.rows("claim")["40"]["evidence"]
        self.assertIn('"What the run does not support, in the earlier run: its persons are files." "What the earlier run does not support holds for this one."', evidence)


class TableAndLicenceTest(StudyFolder):
    def test_each_group_s_licence_is_copied_and_a_source_with_no_entry_is_named(self):
        report.write(self.run, STUDY)
        text = self.text()
        self.assertIn("- Source ids with no entry in data/licences.json: fixture_cts, fixture_flux.", text)
        self.assertIn("| flexray_drr | synthetic | fixture_cts | fixture licence text R | fixture_cts: no entry |", text)
        self.assertIn("| fixture_film | film | fixture_film_alias | fixture licence text B | fixture_film_alias as fixture_film_entry: non-commercial, reviewed owner 2000-01-01 |", text)
        self.assertIn("names no network's commercial use", text)

    def test_a_folder_of_the_two_files_alone_is_read_and_a_table_of_another_digest_is_not_used(self):
        (self.run / "groups.json").unlink()
        claim = self.rows("claim")
        self.assertEqual(claim["7"]["state"], "missing")
        self.assertIn("needs the groups table the record names, 7e1b-145e-9d74-759a: data/domain_gap/groups.json is", claim["7"]["evidence"])
        self.assertEqual(claim["35"]["state"], "met")
        self.assertIn("Not recorded: the report needs the groups table", self.text())

    def test_a_group_of_the_table_the_summary_has_no_line_for_leaves_the_counts_missing(self):
        self.replace_line("group fluxray ", None)
        exclusions = self.rows("claim")["35"]
        self.assertEqual(exclusions["state"], "missing")
        self.assertIn("no line for the table's groups fluxray", exclusions["evidence"])

    def test_the_summary_s_counts_and_endpoints_are_quoted(self):
        claim, reforms = self.rows("claim"), self.rows("reforms")
        self.assertIn("flexray_drr_ct 40/40/40/10 (the counts of flexray_drr)", claim["35"]["evidence"])
        self.assertIn("fluxray skipped (not on the data root in this fixture)", claim["35"]["evidence"])
        self.assertIn("flexray_drr vs fluoroscopy auc 0.12 [0.11, 0.13]", claim["37"]["evidence"])
        self.assertIn("not in summary.txt: fluxray vs fluoroscopy (group skipped, not on the data root in this fixture)", claim["37"]["evidence"])
        self.assertIn("fixture_fluoro 1", reforms["4b"]["evidence"])
        self.assertIn("persons by file: fixture_film", reforms["6b"]["evidence"])


    def test_a_primary_endpoint_whose_null_is_flagged_is_not_read(self):
        calibration = " calibration split-half auc median 0.33 range 0.32 to 0.34 over 1, mmd flagged 0, auc interval above half 0"
        lines = self.lines()
        at = lines.index(calibration)
        self.write_lines(lines[:at] + [calibration.replace("mmd flagged 0", "mmd flagged 1"), " calibration flagged flexray_drr"] + lines[at + 1:])
        endpoints = self.rows("claim")["37"]
        self.assertEqual(endpoints["state"], "met")
        self.assertIn("not read: flexray_drr vs fluoroscopy: the split-half null of flexray_drr in flexray found a difference", endpoints["evidence"])
        self.assertNotIn("flexray_drr vs fluoroscopy auc 0.12", endpoints["evidence"])
        self.assertIn("flexray_drr_ct vs fluoroscopy auc 0.32", endpoints["evidence"])

    def test_an_endpoint_whose_family_holds_a_flagged_group_is_not_read(self):
        calibration = " calibration split-half auc median 0.33 range 0.32 to 0.34 over 1, mmd flagged 0, auc interval above half 0"
        lines = self.lines()
        at = lines.index(calibration)
        self.write_lines(lines[:at] + [calibration.replace("mmd flagged 0", "mmd flagged 1"), " calibration flagged fixture_fluoro"] + lines[at + 1:])
        endpoints = self.rows("claim")["37"]["evidence"]
        self.assertIn("not read: flexray_drr vs fluoroscopy: the split-half null of fixture_fluoro in flexray found a difference", endpoints)
        self.assertIn("flexray_drr vs film auc 0.22", endpoints)
        self.assertNotIn("flexray_drr vs fluoroscopy auc 0.12", endpoints)

    def test_an_endpoint_line_with_no_word_is_not_counted_as_worded(self):
        self.replace_line(" flexray_drr vs film auc 0.22", " flexray_drr vs film auc 0.22 [0.21, 0.23] p 0.020 knn 0.24 fd64 2.5 mmd p 0.027 prdc 0.28 0.29 0.30 0.31")
        self.assertIn("of the primary endpoints' 3 worded lines read, none worded separable, 1 printed with no word", self.rows("claim")["39"]["evidence"])

    def test_a_flagged_count_the_names_do_not_match_leaves_the_endpoints_missing(self):
        calibration = " calibration split-half auc median 0.33 range 0.32 to 0.34 over 1, mmd flagged 0, auc interval above half 0"
        self.replace_line(calibration, calibration.replace("mmd flagged 0", "mmd flagged 2"))
        endpoints = self.rows("claim")["37"]
        self.assertEqual(endpoints["state"], "missing")
        self.assertIn("counts 2 and names 0", endpoints["evidence"])


class CheckTest(StudyFolder):
    def test_complete_fails_while_the_owner_s_items_are_empty(self):
        self.assertEqual(quiet(report.check, self.run, study=STUDY), 1)
        report.write(self.run, STUDY)
        self.assertEqual(quiet(report.check, self.run, study=STUDY), 0)
        self.assertEqual(quiet(report.check, self.run, True, STUDY), 1)
        self.write_answers({fact: "Fixture sentence." for fact in report.study_declared_facts(STUDY)})
        self.assertEqual(quiet(report.check, self.run, study=STUDY), 1)
        report.write(self.run, STUDY)
        self.assertEqual(quiet(report.check, self.run, True, STUDY), 0)

    def test_a_folder_without_its_summary_or_with_a_summary_too_long_is_refused(self):
        self.write_lines(self.lines() + [" filler"] * 80)
        with self.assertRaises(report.ReportError):
            report.render_study(STUDY, self.run)
        (self.run / "summary.txt").unlink()
        with self.assertRaises(report.ReportError):
            report.render_study(STUDY, self.run)


class AnswersForARunTest(StudyFolder):
    def test_answers_written_for_another_run_answer_nothing_here(self):
        answers = {fact: "Fixture sentence." for fact in report.study_declared_facts(STUDY)}
        self.write_answers({"_run": "1000001", **answers})
        self.assertEqual(self.rows("claim")["1"]["state"], "declared")
        self.write_answers({"_run": "2000002", **answers})
        title = self.rows("claim")["1"]
        self.assertEqual(title["state"], "missing")
        self.assertIn("whose answers are run 2000002's, not this run's", title["evidence"])
        self.assertEqual(quiet(report.check, self.run, True, STUDY), 1)


class StudyRulesTest(unittest.TestCase):
    def test_every_item_a_training_run_answers_by_code_has_a_study_answer(self):
        for key, checklist in report.checklists().items():
            for item in checklist["items"]:
                basis, fact = report.study_basis(key, item, STUDY)
                self.assertIn(basis, ("code", "declared"), item["id"])
                if basis == "code":
                    self.assertIn(fact, report.STUDY_FACTS, item["id"])

    def test_the_owner_answers_only_what_no_file_of_the_study_says(self):
        self.assertEqual(report.study_declared_facts(STUDY), {"title", "abstract", "background", "study_design", "acquisition", "deidentification", "characteristics", "implications", "availability", "funding", "model_rationale", "external_validity", "non_generalization"})

    def test_the_design_the_answers_restate_is_the_frozen_pre_registration(self):
        prereg = ROOT / "docs" / "research" / "drr-domain-gap" / "PREREG.md"
        self.assertEqual(hashlib.sha256(prereg.read_bytes()).hexdigest()[:16], report.undashed(report.STUDIES[STUDY]["design"]))

    def test_the_study_s_answers_file_holds_every_fact_its_owner_answers(self):
        path = ROOT / "data" / "reporting" / "studies" / f"{STUDY}.json"
        self.assertEqual(set(report.study_answers(path)), report.study_declared_facts(STUDY))


class RecordedTest(StudyFolder):
    def setUp(self):
        super().setUp()
        self.addCleanup(setattr, report, "RUNS", report.RUNS)
        report.RUNS = Path(self.folder.name) / "no-training-runs"

    def test_check_recorded_passes_with_no_study_run(self):
        report.STUDIES[STUDY]["runs"] = Path(self.folder.name) / "no-study-runs"
        self.assertEqual(report.recorded_studies(), [])
        self.assertEqual(quiet(report.main, ["check-recorded"]), 0)

    def test_check_recorded_holds_each_study_run_to_its_report(self):
        self.assertEqual(report.recorded_studies(), [(STUDY, self.run)])
        self.assertEqual(quiet(report.main, ["check-recorded"]), 1)
        self.assertEqual(quiet(report.main, ["write-recorded"]), 0)
        self.assertEqual(quiet(report.main, ["check-recorded"]), 0)

    def test_the_command_line_takes_the_study(self):
        self.assertEqual(quiet(report.main, ["write", "--study", STUDY, "--run", str(self.run)]), 0)
        self.assertEqual(quiet(report.main, ["check", "--study", STUDY, "--run", str(self.run)]), 0)
        self.assertEqual(quiet(report.main, ["check", "--study", STUDY, "--run", str(self.run), "--complete"]), 1)


if __name__ == "__main__":
    unittest.main()
