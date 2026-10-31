"""The QA loop's CLAIM 2024 and REFORMS report (tools/qaloop_report.py, the study qa-loop of
tools/report.py): a chain folder as flows/qaloop.py's end leaves it is written and then checked
current, every code answer quotes the files RECORD.json names, a file whose bytes moved since the
record is missing in words, a chain run under another PREREG is never reported in this design's
words, the design the module restates is the one frozen beside the PREREG, with every known limit of
its section 6, and the rounds, the sizes and the exclusions are read from the chain, not assumed.
Standard library only, so the required check runs it with the runner's python3.
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
STUDY = "qa-loop"
# A word of each of PREREG.md section 6's known limits, in its order, found in the limit and in its
# restatement (tools/qaloop_report.py, LIMITS).
LIMIT_WORDS = ("drawn as an l5", "a single body", "no landmark detector", "no sacrum", "typical columns alone",
               "fit them imperfectly", "mirrored", "same in every round", "counts runs", "is a cue", "2 pixels of noise",
               "stand-ins")


def load_module():
    spec = importlib.util.spec_from_file_location("qaloop_report_under_test", ROOT / "tools" / "qaloop_report.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def sha256_of(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cells_result(passing):
    failing = [] if passing else [{"cell": "ap/bottom/six_lumbar", "accuracy": 0.0, "low": 0.0, "margin": -2.9,
                                   "ceiling": 0.1, "within_reach": False}]
    return {"pass": passing, "cells": 3, "failing": [f"{c['cell']}: low" for c in failing], "failing_cells": failing,
            "beyond_ceiling": [c["cell"] for c in failing], "ceiling_known": True}


def gates_of(n, pairs):
    """A round's gates.json as tools/qaloop_round.py writes it, every value an aggregate."""
    stand_in = pairs["source"] == "stand-ins"
    return {
        "round": n, "plan": "qa_smoke",
        "config": {"phantoms_per_class": 1 + n, "w_name": 0.1, "fingerprint_persons": 4, "max_landmarks": 4,
                   "presence_floor": 0.0},
        "gates": {
            "convergence": {"pass": False, "why": f"{25 * (n + 1)} steps, fewer than two windows of 200", "steps": 25 * (n + 1)},
            "anomaly": {"pass": False, "failing": ["six_lumbar: Dice 0.6 below 0.8"],
                        "per_class": {"normal": {"n": 4, "dice": 0.8, "named_right": 0.25, "probe_recall": 0.75},
                                      "six_lumbar": {"n": 1, "dice": 0.6, "named_right": 0.0, "probe_recall": "nan"}}},
            "fingerprint": cells_result(False),
            "presence": {"pass": False, "why": "4 of 4 frames show the landmarks at or above the 0.6 percentile, the "
                         "share's low 0.510 below 0.6", "frames": 4, "hits": 4, "low": 0.51, "high": 1.0, "median": 0.8,
                         "stand_in": stand_in},
            "real_naming": dict(cells_result(True), stand_in=stand_in),
            "latency": {"pass": True, "n": 50, "p50_ms": 0.16, "p95_ms": 0.25, "max_ms": 0.3, "budget_ms": 97.0,
                        "what": "the 2-D naming path alone"},
        },
        "held": {"crops": 24, "dice": 0.78, "distance_mm": 2.7},
        "fingerprint": {"chosen": ["body_height", "endplate_tilt"], "pool": [f"l{i}" for i in range(18)],
                        "selection_runs": 316, "gate_runs": 318, "real_selection_runs": 31, "real_gate_runs": 15},
        "cells": {"ap/bottom/six_lumbar": {"n": 7}, "ap/none/typical": {"n": 20}, "lat_real/none/typical": {"n": 15}},
        "pairs": pairs,
        "seconds": {"pairs": 7.0, "crops": 50.0, "train": 46.0, "evaluate": 7.0, "fingerprint": 5.0},
        "environment": {"python": "3.11.9", "packages": {"jax": "0.10.2", "nibabel": None}, "cpus": 8, "backend": "gpu",
                        "devices": ["NVIDIA L40S"]},
        "stand_in": stand_in,
    }


def summary_of(n, exit_code, verdict, changes):
    return {"round": n, "exit": exit_code, "tries": 1,
            "gates": {"convergence": "fail", "anomaly": "fail", "fingerprint": "fail", "presence": "fail",
                      "real_naming": "pass", "latency": "pass"} if exit_code == 0 else {},
            "verdict": verdict, "why": "; ".join(changes) or verdict, "changes": changes, "stuck": [], "config": None,
            "held_distance_mm": 2.7, "held_dice": 0.78, "chosen": ["body_height"], "seconds": None, "stand_in": True}


def write_chain(folder, prereg_sha256, pairs=None, last_fails=False, plan_name="qa_smoke"):
    """A chain folder of two rounds, RECORD.json naming each round's files by their sha256."""
    pairs = pairs or {"source": "stand-ins", "cases": 3, "read": 3, "stand_in": True}
    plan = json.loads((ROOT / "grid" / "qaloop" / f"{plan_name}.json").read_text(encoding="utf-8"))
    files, rounds = {}, []
    decisions = [{"branch": "again", "verdict": "running", "why": "anomaly: phantoms per class 1 to 2",
                  "changes": ["anomaly: phantoms per class 1 to 2"], "stuck": [], "passing": [], "failing": []},
                 {"branch": "done", "verdict": "failed" if last_fails else "not met",
                  "why": "round 1's tool exited 1: ValueError" if last_fails else "2 rounds run; failing anomaly",
                  "changes": [], "stuck": ["fingerprint: beyond the ceiling of the pool's landmarks in one frame"],
                  "passing": [], "failing": []}]
    for n, decision in enumerate(decisions):
        exit_code = 1 if last_fails and n == 1 else 0
        names = ["state.json", "decision.json"] + (["gates.json"] if exit_code == 0 else [])
        for name in names:
            value = {"state.json": {"round": n}, "decision.json": decision, "gates.json": gates_of(n, pairs)}[name]
            write_json(folder / "rounds" / f"{n:03d}" / name, value)
            files[f"rounds/{n:03d}/{name}"] = sha256_of(folder / "rounds" / f"{n:03d}" / name)
        rounds.append(summary_of(n, exit_code, decision["verdict"], decision["changes"]))
    record = {"study": STUDY, "run": "QaloopFlow/7", "key": "k", "commit": "a" * 40,
              "prereg": "docs/research/qa-loop/PREREG.md", "prereg_sha256": prereg_sha256, "prereg_part": plan_name,
              "prereg_part_sha256": "b" * 64, "chain": "41000001", "started": "2026-10-31 04:00:00",
              "ended": "2026-10-31 05:00:00", "where": {"host": "gpu-node", "slurm_job": "41000001", "copy_of": "a" * 40},
              "plan": dict(plan, file=f"grid/qaloop/{plan_name}.json"), "rounds": rounds, "decision": decisions[-1],
              "splits": {"data/splits/rule.json": "c" * 64, "data/splits/test-persons.json": "d" * 64}, "files": files}
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
        frozen = (ROOT / "docs" / "research" / "qa-loop" / "PREREG.md.sha256").read_text(encoding="utf-8").split()[0]
        self.assertEqual(self.module.DESIGN, frozen)
        self.assertEqual(self.module.DESIGN, sha256_of(self.module.PREREG))

    def test_a_chain_is_written_and_checked_current_with_its_rounds_quoted(self):
        write_chain(self.folder, self.module.DESIGN)
        wrote = report("write", self.folder)
        self.assertEqual(wrote.returncode, 0, wrote.stdout + wrote.stderr)
        checked = report("check", self.folder)
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
        claim, reforms = items(self.folder, "claim"), items(self.folder, "reforms")
        performance = claim["37"]["evidence"]
        self.assertEqual(claim["37"]["state"], "met")
        self.assertIn("the loop ended not met after 2 rounds", performance)
        self.assertIn("latency passes: 95th percentile 0.250 ms over 50 runs", performance)
        self.assertIn("2 of 3 cells pass, 1 of the 1 failing beyond the ceiling", performance)
        self.assertIn("asked of stand-ins", performance)
        self.assertIn("probe recall nan", performance)
        self.assertIn("ap/bottom/six_lumbar accuracy 0.000", claim["39"]["evidence"])
        self.assertIn("no real case was read (stand-ins)", claim["35"]["evidence"])
        self.assertIn("jax 0.10.2", claim["23"]["evidence"])
        self.assertIn("nibabel absent", claim["23"]["evidence"])
        self.assertIn("seed 1, the plan's word", claim["24"]["evidence"])
        self.assertEqual(claim["1"]["state"], "missing")  # the title is the owner's, and the answers file is empty
        self.assertEqual(claim["36"]["state"], "missing")  # no characteristic of a real person leaves the grid
        self.assertIn("the smoke answers no question", claim["29"]["evidence"])
        self.assertIn("the smoke's sizes", reforms["3e"]["evidence"])
        self.assertIn("train 92 s", reforms["2c"]["evidence"])
        self.assertIn("42 runs in 3 cells, 7 to 20 a cell", reforms["3d"]["evidence"])
        page = (self.folder / "REPORT.md").read_text(encoding="utf-8")
        self.assertIn("chain 41000001 of qa_smoke", page)
        self.assertIn("The loop ended **not met** after 2 rounds", page)
        self.assertIn("| 0 | 0 | fail | fail | fail | fail | pass | pass | running | anomaly: phantoms per class 1 to 2 |", page)
        self.assertIn("say nothing of real fluoroscopy", page)

    def test_a_file_whose_bytes_moved_since_the_record_answers_nothing(self):
        write_chain(self.folder, self.module.DESIGN)
        (self.folder / "rounds" / "001" / "gates.json").write_text("{}\n", encoding="utf-8")
        wrote = report("write", self.folder)
        self.assertEqual(wrote.returncode, 0, wrote.stdout + wrote.stderr)
        performance = items(self.folder, "claim")["37"]
        self.assertEqual(performance["state"], "missing")
        self.assertIn("rounds/001/gates.json is not the file RECORD.json names", performance["evidence"])

    def test_a_round_that_failed_leaves_the_newest_round_that_answered_quoted(self):
        write_chain(self.folder, self.module.DESIGN, last_fails=True)
        wrote = report("write", self.folder)
        self.assertEqual(wrote.returncode, 0, wrote.stdout + wrote.stderr)
        performance = items(self.folder, "claim")["37"]
        self.assertEqual(performance["state"], "met")
        self.assertIn("the loop ended failed after 2 rounds: round 1's tool exited 1", performance["evidence"])
        self.assertIn("round 0:", performance["evidence"])

    def test_a_chain_of_another_design_is_not_reported_in_this_ones_words(self):
        write_chain(self.folder, "c" * 64)
        wrote = report("write", self.folder)
        self.assertEqual(wrote.returncode, 0, wrote.stdout + wrote.stderr)
        claim = items(self.folder, "claim")
        for item in ("19", "40", "42"):
            with self.subTest(item=item):
                self.assertEqual(claim[item]["state"], "missing")
                self.assertIn("the chain ran another design", claim[item]["evidence"])

    def test_the_real_pairs_are_quoted_as_counts_by_reason_and_with_their_licence(self):
        pairs = {"source": "C-ArmLSpine", "cases": 120, "read": 118, "stand_in": False,
                 "left_out": {"test": 5, "flagged": 2, "no mask": 0, "no pose": 1, "too few levels": 3},
                 "failed": {"ValueError": 2}}
        write_chain(self.folder, self.module.DESIGN, pairs=pairs)
        self.assertEqual(report("write", self.folder).returncode, 0)
        claim = items(self.folder, "claim")
        self.assertIn("120 cases taken and 118 read", claim["35"]["evidence"])
        self.assertIn("test 5", claim["35"]["evidence"])
        self.assertIn("ValueError 2", claim["35"]["evidence"])
        self.assertIn("CC BY 4.0", claim["7"]["evidence"])
        self.assertNotIn("stand-ins", claim["37"]["evidence"])

    def test_a_loop_plans_levers_the_memory_bounds_are_said_so(self):
        run = {"record": {"prereg_sha256": self.module.DESIGN,
                          "plan": json.loads((ROOT / "grid" / "qaloop" / "qa_loop.json").read_text(encoding="utf-8"))}}
        sizes = self.module.fact_sample_size(run)[1]
        self.assertIn("phantoms_per_class the memory", sizes)
        self.assertIn("fingerprint_persons the memory", sizes)
        self.assertIn("max_landmarks 18", sizes)
        self.assertNotIn("the smoke", sizes + self.module.fact_uncertainty(run)[1])

    def test_every_known_limit_of_the_prereg_is_restated_in_its_order(self):
        section = self.module.PREREG.read_text(encoding="utf-8").split("## 6.", 1)[1].split("## 7.", 1)[0]
        limits = [line for line in section.split("Known limits", 1)[1].splitlines() if line.startswith("- ")]
        self.assertEqual(len(limits), len(self.module.LIMITS))
        self.assertEqual(len(limits), len(LIMIT_WORDS))
        for word, limit, restated in zip(LIMIT_WORDS, limits, self.module.LIMITS, strict=True):
            with self.subTest(word=word):
                self.assertIn(word, limit.lower())
                self.assertIn(word, restated.lower())

    def test_a_report_the_files_moved_under_is_not_current(self):
        write_chain(self.folder, self.module.DESIGN)
        self.assertEqual(report("write", self.folder).returncode, 0)
        (self.folder / "rounds" / "000" / "gates.json").write_text("{}\n", encoding="utf-8")
        self.assertNotEqual(report("check", self.folder).returncode, 0)

    def test_the_answers_file_holds_every_item_the_owner_answers_and_no_other(self):
        spec = importlib.util.spec_from_file_location("report_under_test", REPORT)
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        path = ROOT / "data" / "reporting" / "studies" / f"{STUDY}.json"
        self.assertEqual(set(tool.study_answers(path)), tool.study_declared_facts(STUDY))
        self.assertTrue(all(value == "" for value in tool.study_answers(path).values()))

    def test_a_folder_with_no_record_of_the_loop_is_refused(self):
        self.folder.mkdir(parents=True)
        wrote = report("write", self.folder)
        self.assertNotEqual(wrote.returncode, 0)
        self.assertIn("not a chain of the loop", wrote.stdout + wrote.stderr)


if __name__ == "__main__":
    unittest.main()
