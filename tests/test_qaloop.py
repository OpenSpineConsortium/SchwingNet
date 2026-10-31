"""The QA loop's checkpoints and its controller (tools/qaloop_gates.py), and the two plans it runs
(grid/qaloop/): every plan the loop's PREREG covers holds, a plan that does not is refused in words,
each gate's answer is read as its bars say, a measure that is not a number fails, and the controller
ends the loop met, stopped or not met where the PREREG says and otherwise makes one change for each
failing gate, the growing levers bounded by the memory each round measures and by nothing else where
the plan sets no limit. numpy is all the module needs, which CI's python3 does not hold, so the file
is skipped there; run it with any python that has numpy:

    python3 -m unittest tests.test_qaloop -v
"""

import copy
import importlib.util
import json
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MISSING = [name for name in ("numpy",) if importlib.util.find_spec(name) is None]


def load_gates():
    spec = importlib.util.spec_from_file_location("qaloop_gates_under_test", ROOT / "tools" / "qaloop_gates.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def plan_of(name):
    return json.loads((ROOT / "grid" / "qaloop" / f"{name}.json").read_text(encoding="utf-8"))


def passing():
    return {"pass": True}


def failing_cells(within_reach, ceiling_known=True):
    cell = {"cell": "ap/none/typical", "accuracy": 0.7, "low": 0.6, "margin": 1.0, "ceiling": 0.95 if within_reach else 0.5,
            "within_reach": within_reach}
    return {"pass": False, "cells": 4, "failing": ["ap/none/typical: low"], "failing_cells": [cell],
            "beyond_ceiling": [] if within_reach else [cell["cell"]], "ceiling_known": ceiling_known}


def record_of(**gates):
    """A round's record whose gates pass but those given, with the space a round measured."""
    answers = {g: passing() for g in ("convergence", "anomaly", "fingerprint", "presence", "real_naming", "latency")}
    answers.update(gates)
    return {"gates": answers, "space": {"rows_fit": 600, "persons_fit": 40}}


@unittest.skipIf(MISSING, f"needs numpy ({', '.join(MISSING)} missing)")
class PlansTest(unittest.TestCase):
    def setUp(self):
        self.gates = load_gates()

    def test_both_plans_the_prereg_covers_hold(self):
        for name in ("qa_smoke", "qa_loop"):
            with self.subTest(plan=name):
                plan = plan_of(name)
                self.assertEqual(self.gates.plan_problems(plan), [])
                self.assertEqual(plan["plan"], name)

    def test_the_loop_plan_lets_the_memory_alone_bound_its_growing_levers(self):
        limits = plan_of("qa_loop")["limits"]
        self.assertIsNone(limits["phantoms_per_class"])
        self.assertIsNone(limits["fingerprint_persons"])
        self.assertEqual(limits["max_landmarks"], len(self.gates.LANDMARKS))

    def test_a_plan_that_does_not_hold_is_refused_in_words(self):
        cases = {
            "class": ("class", "trial", "class is one of"),
            "rounds": ("rounds", 0, "rounds is a whole number"),
            "gates": ("gates", ["speed"], "gates are some of"),
            "steps": ("steps_per_round", 2.5, "steps_per_round is a whole number"),
        }
        for label, (key, value, words) in cases.items():
            with self.subTest(case=label):
                plan = plan_of("qa_smoke")
                plan[key] = value
                self.assertTrue(any(words in p for p in self.gates.plan_problems(plan)), self.gates.plan_problems(plan))
        plan = plan_of("qa_smoke")
        plan["classes"] = ["lumbar_rib"]
        self.assertTrue(any("typical among them" in p for p in self.gates.plan_problems(plan)))
        plan = plan_of("qa_loop")
        plan["pairs"]["stand_ins"] = 3
        self.assertTrue(any("never names stand-ins" in p for p in self.gates.plan_problems(plan)))
        del plan_of("qa_smoke")["bars"]
        self.assertEqual(self.gates.plan_problems([]), ["the plan is not a JSON object"])

    def test_only_the_growing_levers_may_be_left_to_the_memory(self):
        plan = plan_of("qa_loop")
        plan["limits"]["w_name"] = None
        self.assertTrue(any("w_name is a number" in p for p in self.gates.plan_problems(plan)))
        plan = plan_of("qa_loop")
        plan["limits"]["max_landmarks"] = 2
        self.assertTrue(any("below its start" in p for p in self.gates.plan_problems(plan)))
        plan = plan_of("qa_loop")
        del plan["limits"]["presence_floor"]
        self.assertTrue(any("limits has no presence_floor" in p for p in self.gates.plan_problems(plan)))


@unittest.skipIf(MISSING, f"needs numpy ({', '.join(MISSING)} missing)")
class GatesTest(unittest.TestCase):
    def setUp(self):
        self.gates = load_gates()
        self.bars = plan_of("qa_smoke")["bars"]

    def test_a_measure_that_is_not_a_number_fails_the_anomaly_bars(self):
        per_class = {"normal": {"n": 4, "dice": 0.9, "named_right": 0.9, "probe_recall": 0.9},
                     "six_lumbar": {"n": 2, "dice": 0.9, "named_right": 0.9, "probe_recall": float("nan")}}
        result = self.gates.anomaly_gate(per_class, self.bars["anomaly"], ["normal", "six_lumbar"])
        self.assertFalse(result["pass"])
        self.assertEqual(len(result["failing"]), 1)
        self.assertIn("six_lumbar: probe recall", result["failing"][0])
        per_class["six_lumbar"]["probe_recall"] = 0.9
        self.assertTrue(self.gates.anomaly_gate(per_class, self.bars["anomaly"], ["normal", "six_lumbar"])["pass"])
        self.assertFalse(self.gates.anomaly_gate({}, self.bars["anomaly"], ["t13"])["pass"])

    def test_convergence_reads_the_windows_and_the_held_distance(self):
        bars = self.bars["convergence"]
        short = self.gates.convergence([1.0] * 300, [3.0], bars)
        self.assertFalse(short["pass"])
        self.assertIn("fewer than two windows", short["why"])
        flat = [1.0] * 400
        self.assertTrue(self.gates.convergence(flat, [3.0], bars)["pass"])
        rising = self.gates.convergence(flat, [3.0, 2.0, 2.5], bars)
        self.assertFalse(rising["pass"])
        self.assertIn("held-out distance rising", rising["why"])
        # a held distance JSON brought back as its name in words is passed over, not a failure of the reader
        self.assertTrue(self.gates.convergence(flat, ["nan", 3.0], bars)["pass"])
        moving = self.gates.convergence([2.0] * 200 + [1.0] * 200, [3.0], bars)
        self.assertFalse(moving["pass"])

    def test_a_cell_passes_on_its_interval_and_its_margin_and_a_failing_one_is_set_beside_the_ceiling(self):
        bars = self.bars["fingerprint"]
        table = {"ap/none/typical": {"n": 400, "right": 400, "accuracy": 1.0, "low": 0.99, "median_margin": 5.0},
                 "lat/none/typical": {"n": 400, "right": 400, "accuracy": 1.0, "low": 0.99, "median_margin": 1.0},
                 "ap/bottom/six_lumbar": {"n": 40, "right": 2, "accuracy": 0.05, "low": 0.01, "median_margin": -3.0},
                 "ap_real/none/typical": {"n": 40, "right": 40, "accuracy": 1.0, "low": 0.91, "median_margin": 4.0}}
        ceiling = {"lat/none/typical": {"accuracy": 1.0}, "ap/bottom/six_lumbar": {"accuracy": 0.2}}
        result = self.gates.fingerprint_gate(table, bars, ("bottom", "none"), "phantom", ceiling)
        self.assertFalse(result["pass"])
        self.assertEqual(result["cells"], 3)
        self.assertEqual([c["cell"] for c in result["failing_cells"]], ["ap/bottom/six_lumbar", "lat/none/typical"])
        self.assertEqual(result["beyond_ceiling"], ["ap/bottom/six_lumbar"])
        self.assertTrue(self.gates.within_reach(result))
        real = self.gates.fingerprint_gate(table, bars, ("none",), "real", ceiling)
        self.assertTrue(real["pass"])
        self.assertEqual(real["cells"], 1)
        self.assertFalse(self.gates.fingerprint_gate({}, bars, ("none",), "real", ceiling)["pass"])

    def test_a_cell_that_fails_for_want_of_runs_is_within_reach_and_only_both_upper_ends_below_the_bar_are_beyond(self):
        # the smoke's case: a perfect cell of eight runs fails on its interval alone, and its ceiling's
        # six of eight still reach the bar at the upper end, so neither is called beyond one frame
        bars = self.bars["fingerprint"]
        table = {"ap/bottom/typical": {"n": 8, "right": 8, "accuracy": 1.0, "low": 0.676, "median_margin": 5.0},
                 "ap/bottom/six_lumbar": {"n": 8, "right": 0, "accuracy": 0.0, "low": 0.0, "median_margin": -3.0}}
        ceiling = {"ap/bottom/typical": {"n": 8, "right": 6, "accuracy": 0.75},
                   "ap/bottom/six_lumbar": {"n": 8, "right": 1, "accuracy": 0.125}}
        result = self.gates.fingerprint_gate(table, bars, ("bottom",), "phantom", ceiling)
        self.assertFalse(result["pass"])
        reach = {c["cell"]: c["within_reach"] for c in result["failing_cells"]}
        self.assertEqual(reach, {"ap/bottom/typical": True, "ap/bottom/six_lumbar": False})
        self.assertEqual(result["beyond_ceiling"], ["ap/bottom/six_lumbar"])
        self.assertAlmostEqual(self.gates.upper(ceiling["ap/bottom/six_lumbar"]), self.gates.wilson(1, 8)[1], places=12)
        self.assertLess(self.gates.upper(ceiling["ap/bottom/six_lumbar"]), bars["accuracy_low"])
        self.assertTrue(self.gates.within_reach(result))

    def test_presence_and_latency_are_held_to_their_bars(self):
        shown = self.gates.presence_gate([0.9] * 30 + [float("nan")], self.bars["presence"])
        self.assertTrue(shown["pass"])
        self.assertEqual(shown["frames"], 30)
        self.assertFalse(self.gates.presence_gate([0.9, 0.1, 0.1], self.bars["presence"])["pass"])
        self.assertEqual(self.gates.presence_gate([], self.bars["presence"])["why"], "no frame had a landmark to read")
        self.assertTrue(self.gates.latency_gate([0.001] * 100, self.bars["latency"])["pass"])
        self.assertFalse(self.gates.latency_gate([0.2] * 100, self.bars["latency"])["pass"])
        self.assertFalse(self.gates.latency_gate([], self.bars["latency"])["pass"])

    def test_the_wilson_interval_holds_its_known_values(self):
        lo, hi = self.gates.wilson(10, 10)
        self.assertAlmostEqual(lo, 0.7225, places=3)
        self.assertAlmostEqual(hi, 1.0, places=9)
        lo, hi = self.gates.wilson(0, 0)
        self.assertTrue(lo == 0.0 or math.isnan(lo))


@unittest.skipIf(MISSING, f"needs numpy ({', '.join(MISSING)} missing)")
class ControllerTest(unittest.TestCase):
    def setUp(self):
        self.gates = load_gates()
        self.plan = plan_of("qa_loop")
        self.state = {"round": 0, "config": dict(self.plan["start"]), "held": []}

    def decide(self, record, state=None, plan=None):
        return self.gates.controller(record, copy.deepcopy(state or self.state), plan or self.plan)

    def test_every_gate_passing_ends_the_loop_met(self):
        decision = self.decide(record_of())
        self.assertEqual((decision["branch"], decision["verdict"]), ("done", "met"))

    def test_a_gate_without_its_data_ends_the_loop_stopped_with_why(self):
        decision = self.decide(record_of(presence={"pass": False, "missing": "no gate frame to look at"}))
        self.assertEqual((decision["branch"], decision["verdict"]), ("done", "stopped"))
        self.assertIn("presence: no gate frame to look at", decision["why"])

    def test_the_last_round_ends_the_loop_not_met(self):
        state = dict(self.state, round=self.plan["rounds"] - 1)
        decision = self.decide(record_of(latency={"pass": False}), state)
        self.assertEqual((decision["branch"], decision["verdict"]), ("done", "not met"))
        self.assertIn(f"{self.plan['rounds']} rounds run", decision["why"])

    def test_anomaly_waits_for_convergence_then_grows_as_the_memory_holds(self):
        waiting = self.decide(record_of(convergence={"pass": False}, anomaly={"pass": False}))
        self.assertEqual(waiting["branch"], "again")
        self.assertIn("anomaly: waits for the loss to settle", waiting["why"])
        self.assertEqual(waiting["config"]["phantoms_per_class"], self.plan["start"]["phantoms_per_class"])
        grown = self.decide(record_of(anomaly={"pass": False}))
        self.assertEqual(grown["config"]["phantoms_per_class"], 2 * self.plan["start"]["phantoms_per_class"])
        # the loop plan sets no limit, so the memory alone holds the rows: 600 rows fit, six classes,
        # eight gate rows a class, so 92 a class at most
        state = dict(self.state, config=dict(self.state["config"], phantoms_per_class=64))
        bounded = self.decide(record_of(anomaly={"pass": False}), state)
        self.assertEqual(bounded["config"]["phantoms_per_class"], 600 // 6 - 8)
        state = dict(self.state, config=dict(self.state["config"], phantoms_per_class=92))
        heavier = self.decide(record_of(anomaly={"pass": False}), state)
        self.assertEqual(heavier["config"]["phantoms_per_class"], 92)
        self.assertEqual(heavier["config"]["w_name"], 2 * self.plan["start"]["w_name"])

    def test_with_no_limit_and_no_measure_of_the_memory_no_rows_are_added(self):
        record = record_of(anomaly={"pass": False})
        record["space"] = {}
        decision = self.decide(record)
        self.assertEqual(decision["config"]["phantoms_per_class"], self.plan["start"]["phantoms_per_class"])
        self.assertIn("the name head's weight", decision["why"])

    def test_the_fingerprint_adds_landmarks_toward_the_ceiling_then_persons_as_the_memory_holds(self):
        decision = self.decide(record_of(fingerprint=failing_cells(within_reach=True)))
        self.assertEqual(decision["config"]["max_landmarks"], self.plan["start"]["max_landmarks"] + 2)
        self.assertEqual(decision["config"]["fingerprint_persons"], self.plan["start"]["fingerprint_persons"])
        state = dict(self.state, config=dict(self.state["config"], max_landmarks=18))
        decision = self.decide(record_of(fingerprint=failing_cells(within_reach=True)), state)
        self.assertEqual(decision["config"]["fingerprint_persons"], 32)
        state = dict(self.state, config=dict(self.state["config"], max_landmarks=18, fingerprint_persons=32))
        decision = self.decide(record_of(fingerprint=failing_cells(within_reach=True)), state)
        self.assertEqual(decision["config"]["fingerprint_persons"], 40)  # the persons the memory holds, measured
        state = dict(self.state, config=dict(self.state["config"], max_landmarks=18, fingerprint_persons=40))
        decision = self.decide(record_of(fingerprint=failing_cells(within_reach=True)), state)
        self.assertEqual((decision["branch"], decision["verdict"]), ("done", "not met"))
        self.assertIn("as many as the plan and the memory hold", decision["why"])

    def test_a_fingerprint_beyond_the_ceiling_grows_its_persons_as_the_memory_holds_then_names_the_cells(self):
        # the ceiling is measured at the selection's size, so the persons grow before any cell is called beyond
        decision = self.decide(record_of(fingerprint=failing_cells(within_reach=False)))
        self.assertEqual((decision["branch"], decision["verdict"]), ("again", "running"))
        self.assertEqual(decision["config"]["fingerprint_persons"], 32)
        self.assertEqual(decision["config"]["max_landmarks"], self.plan["start"]["max_landmarks"])
        self.assertIn("every failing cell beyond the ceiling at this size, so the ceiling is measured again", decision["why"])
        state = dict(self.state, config=dict(self.state["config"], fingerprint_persons=40))
        decision = self.decide(record_of(fingerprint=failing_cells(within_reach=False)), state)
        self.assertEqual((decision["branch"], decision["verdict"]), ("done", "not met"))
        self.assertIn("beyond the ceiling of the pool's landmarks in one frame at 40 persons a type", decision["why"])
        self.assertIn("ap/none/typical", decision["why"])

    def test_real_naming_and_presence_and_latency_each_make_their_change(self):
        decision = self.decide(record_of(real_naming=failing_cells(within_reach=True)))
        self.assertEqual(decision["config"]["max_landmarks"], self.plan["start"]["max_landmarks"] + 2)
        both = self.decide(record_of(fingerprint=failing_cells(within_reach=True), real_naming=failing_cells(within_reach=True)))
        self.assertEqual(both["config"]["max_landmarks"], self.plan["start"]["max_landmarks"] + 2)
        self.assertIn("real naming: the fingerprint's added landmarks serve it too", both["why"])
        floor = self.decide(record_of(presence={"pass": False}))
        self.assertEqual(floor["config"]["presence_floor"], 0.1)
        fewer = self.decide(record_of(latency={"pass": False}))
        self.assertEqual(fewer["config"]["max_landmarks"], self.plan["start"]["max_landmarks"] - 2)

    def test_the_smoke_plans_limits_stop_its_levers(self):
        plan = plan_of("qa_smoke")
        state = {"round": 0, "config": dict(plan["limits"]), "held": []}
        decision = self.gates.controller(record_of(anomaly={"pass": False}, presence={"pass": False}), state, plan)
        self.assertEqual((decision["branch"], decision["verdict"]), ("done", "not met"))
        self.assertIn("anomaly: phantoms per class at 2", decision["why"])
        self.assertIn("presence: the floor is at its limit", decision["why"])


if __name__ == "__main__":
    unittest.main()
