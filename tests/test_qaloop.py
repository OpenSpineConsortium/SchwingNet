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
        plan = plan_of("qa_smoke")
        del plan["bars"]
        self.assertEqual(self.gates.plan_problems(plan), ["the plan has no bars"])
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
        # the gate's rows a class taken off, so 68 a class at most
        gate = self.plan["phantom_rows"]["gate_per_class"]
        state = dict(self.state, config=dict(self.state["config"], phantoms_per_class=64))
        bounded = self.decide(record_of(anomaly={"pass": False}), state)
        self.assertEqual(bounded["config"]["phantoms_per_class"], 600 // 6 - gate)
        state = dict(self.state, config=dict(self.state["config"], phantoms_per_class=600 // 6 - gate))
        heavier = self.decide(record_of(anomaly={"pass": False}), state)
        self.assertEqual(heavier["config"]["phantoms_per_class"], 600 // 6 - gate)
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


def check_at(step, epoch, loss=0.5, dice=0.5, distance=5.0, missing=0, crops=10):
    """One check of the training watch, as tools/qaloop_round.py writes it to TREND.jsonl."""
    return {"round": 0, "step": step, "epoch": epoch, "loss": loss, "loss_last": loss, "held_dice": dice,
            "held_distance_mm": distance, "surface_missing": missing, "crops": crops}


@unittest.skipIf(MISSING, f"needs numpy ({', '.join(MISSING)} missing)")
class WatchTest(unittest.TestCase):
    """The training watch: the checks a run cannot be right after, the patience in epochs, and the
    loop's progress across rounds."""

    def setUp(self):
        self.gates = load_gates()
        self.plan = plan_of("qa_loop")
        self.watch = self.plan["watch"]

    def test_a_check_whose_numbers_cannot_be_right_is_named(self):
        insane, watch, bound = self.gates.insane, self.watch, 60.0
        self.assertIsNone(insane(check_at(10, 1.0), None, watch, bound))
        self.assertIn("loss is not a number", insane(check_at(10, 1.0, loss=float("nan")), None, watch, bound))
        self.assertIn("held_dice is not a number", insane(check_at(10, 1.0, dice=float("inf")), None, watch, bound))
        self.assertIn("over 10 times", insane(check_at(10, 1.0, loss=2.0), 0.1, watch, bound))
        # a best loss near nought is taken as the floor, so a small loss never reads as an explosion
        self.assertIsNone(insane(check_at(10, 1.0, loss=0.09), 0.001, watch, bound))
        self.assertIn("a held Dice of", insane(check_at(10, 1.0, dice=1.2), None, watch, bound))
        self.assertIn("outside 0 to the crop's", insane(check_at(10, 1.0, distance=61.0), None, watch, bound))
        warm = watch["warm_epochs"]
        self.assertIsNone(insane(check_at(10, warm - 1, missing=10), None, watch, bound))
        self.assertIn("collapsed", insane(check_at(10, warm, missing=10), None, watch, bound))
        self.assertIsNone(insane(check_at(10, warm, missing=9), None, watch, bound))

    def test_a_check_gains_on_the_distance_or_the_dice_and_training_stalls_after_its_patience(self):
        step = self.gates.watch_step
        w, gained = step({}, check_at(240, 10.0, distance=8.0), self.watch)
        self.assertTrue(gained)
        self.assertEqual((w["best_epoch"], w["since_best"]), (10.0, 0.0))
        w, gained = step(w, check_at(480, 20.0, distance=7.99, dice=0.505), self.watch)
        self.assertFalse(gained)  # both short of min_gain
        self.assertEqual(w["since_best"], 10.0)
        w, gained = step(w, check_at(720, 30.0, distance=7.5), self.watch)
        self.assertTrue(gained)
        w, gained = step(w, check_at(960, 40.0, distance=7.6, dice=0.52), self.watch)
        self.assertTrue(gained)
        self.assertEqual((w["best_distance_mm"], w["best_dice"], w["best_epoch"]), (7.5, 0.52, 40.0))
        for epoch in (50.0, 60.0, 70.0, 80.0):
            w, gained = step(w, check_at(int(epoch * 24), epoch, distance=7.6, dice=0.52), self.watch)
            self.assertFalse(gained)
        self.assertFalse(self.gates.stalled(w, self.watch))
        w, _ = step(w, check_at(2160, 90.0, distance=7.6, dice=0.52), self.watch)
        self.assertEqual(w["since_best"], self.watch["patience_epochs"])
        self.assertTrue(self.gates.stalled(w, self.watch))
        self.assertEqual(w["best_loss"], 0.5)

    def test_the_loops_progress_reads_only_the_measures_that_stay_put_between_rounds(self):
        first = self.gates.loop_progress({}, {"held_dice": 0.5, "latency": -3.0, "cells_phantom": 0.4}, self.watch)
        self.assertEqual((first["raised"], first["flat_rounds"]), (["held_dice"], 0))
        noisy = self.gates.loop_progress(first, {"held_dice": 0.505, "latency": -2.0, "cells_phantom": 0.9}, self.watch)
        self.assertEqual((noisy["raised"], noisy["flat_rounds"]), ([], 1))
        self.assertEqual(noisy["best"], {"held_dice": 0.505})
        again = self.gates.loop_progress(noisy, {"held_dice": 0.52}, self.watch)
        self.assertEqual((again["raised"], again["flat_rounds"]), (["held_dice"], 0))

    def test_a_rounds_measures_are_on_one_scale_larger_for_better(self):
        record = {"held": {"dice": 0.8, "distance_mm": math.e}, "fingerprint": {"objective": 0.9},
                  "gates": {"anomaly": {"per_class": {
                      "t13": {"dice_low": 0.7, "named_low": 0.5, "probe_low": 0.6},
                      "six_lumbar": {"dice": 0.9, "named_right": 0.8, "probe_recall": float("nan")}}},
                      "presence": {"low": 0.4}, "latency": {"p95_ms": math.e ** 2}},
                  "cells": {"ap/none/typical": {"low": 0.6}, "ap_real/none/typical": {"low": 0.2}}}
        m = self.gates.round_measures(record)
        self.assertAlmostEqual(m["held_distance"], -1.0)
        self.assertAlmostEqual(m["latency"], -2.0)
        self.assertAlmostEqual(m["anomaly"], 0.25)  # each class's worst lower bound, a missing one 0
        self.assertEqual((m["cells_phantom"], m["cells_real"]), (0.6, 0.2))
        self.assertEqual((m["held_dice"], m["objective"], m["presence"]), (0.8, 0.9, 0.4))
        self.assertEqual(self.gates.round_measures({}), {})

    def test_a_watch_that_cannot_hold_is_refused_in_words(self):
        cases = {"every_epochs": (0, "every_epochs is a number above 0"), "explode": (1.0, "explode is above 1"),
                 "watch_per_class": (2.5, "watch_per_class is a whole number"),
                 "patience_epochs": (5, "patience_epochs is at least every_epochs")}
        for key, (value, words) in cases.items():
            with self.subTest(key=key):
                plan = plan_of("qa_loop")
                plan["watch"][key] = value
                self.assertTrue(any(words in p for p in self.gates.plan_problems(plan)), self.gates.plan_problems(plan))
        plan = plan_of("qa_loop")
        del plan["watch"]["min_gain"]
        self.assertIn("watch has no min_gain", self.gates.plan_problems(plan))
        plan = plan_of("qa_loop")
        del plan["watch"]
        self.assertEqual(self.gates.plan_problems(plan), ["the plan has no watch"])

    def test_the_loop_ends_not_met_once_its_patience_of_rounds_raised_nothing(self):
        record = record_of(latency={"pass": False})
        record["held"] = {"dice": 0.85, "distance_mm": 3.0}
        best = {"held_dice": 0.9, "held_distance": 0.0}
        flat = {"best": best, "flat_rounds": self.watch["patience_rounds"] - 1}
        state = {"round": 3, "config": dict(self.plan["start"]), "held": [], "progress": flat}
        decision = self.gates.controller(record, copy.deepcopy(state), self.plan)
        self.assertEqual((decision["branch"], decision["verdict"]), ("done", "not met"))
        self.assertIn(f"no progress: {self.watch['patience_rounds']} rounds in a row", decision["why"])
        record["held"]["dice"] = 0.95
        decision = self.gates.controller(record, copy.deepcopy(state), self.plan)
        self.assertEqual((decision["branch"], decision["progress"]["raised"], decision["progress"]["flat_rounds"]),
                         ("again", ["held_dice"], 0))

    def test_training_that_rests_counts_as_converged_and_a_failing_convergence_is_then_stuck(self):
        state = {"round": 0, "config": dict(self.plan["start"]), "held": []}
        record = record_of(convergence={"pass": False}, anomaly={"pass": False})
        record["watch"] = {"stalled": True}
        decision = self.gates.controller(record, copy.deepcopy(state), self.plan)
        self.assertEqual(decision["branch"], "again")
        self.assertEqual(decision["config"]["phantoms_per_class"], 2 * self.plan["start"]["phantoms_per_class"])
        self.assertTrue(any(s.startswith("convergence: training rests") for s in decision["stuck"]))
        alone = record_of(convergence={"pass": False})
        alone["watch"] = {"stalled": True}
        decision = self.gates.controller(alone, copy.deepcopy(state), self.plan)
        self.assertEqual((decision["branch"], decision["verdict"]), ("done", "not met"))

    def test_the_latency_cap_binds_the_landmarks_the_other_gates_would_add(self):
        state = {"round": 0, "config": dict(self.plan["start"], max_landmarks=10), "held": []}
        record = record_of(latency={"pass": False}, fingerprint=failing_cells(within_reach=True))
        record["fingerprint"] = {"chosen": ["a"] * 10}
        decision = self.gates.controller(record, copy.deepcopy(state), self.plan)
        self.assertEqual((decision["config"]["landmark_cap"], decision["config"]["max_landmarks"]), (8, 8))
        self.assertIn("fingerprint: persons per type 16 to 32", decision["why"])
        state = {"round": 1, "config": decision["config"], "held": []}
        record = record_of(fingerprint=failing_cells(within_reach=True))
        record["fingerprint"] = {"chosen": ["a"] * 8}
        decision = self.gates.controller(record, copy.deepcopy(state), self.plan)
        self.assertEqual(decision["config"]["max_landmarks"], 8)
        self.assertIn("persons per type 32 to 40", decision["why"])
        # landmarks are added only where the search took every one it was allowed
        state = {"round": 0, "config": dict(self.plan["start"]), "held": []}
        record = record_of(fingerprint=failing_cells(within_reach=True))
        record["fingerprint"] = {"chosen": ["a"] * (self.plan["start"]["max_landmarks"] - 1)}
        decision = self.gates.controller(record, copy.deepcopy(state), self.plan)
        self.assertEqual(decision["config"]["max_landmarks"], self.plan["start"]["max_landmarks"])
        self.assertIn("persons per type", decision["why"])


@unittest.skipIf(MISSING, f"needs numpy ({', '.join(MISSING)} missing)")
class ReviewFixesTest(unittest.TestCase):
    """What the review of 2026-10-31 found and the fixes hold: an empty arm counts nought, an arm
    with no cell to judge is the gate's data missing, the anomaly bars read the lower bounds, and
    the test persons' ids and the agreed levels are read strictly."""

    def setUp(self):
        self.gates = load_gates()

    def test_an_arm_the_runs_hold_with_no_cell_counts_nought(self):
        table = {"ap/none/typical": {"accuracy": 1.0}}
        self.assertEqual(self.gates.objective(table), 1.0)
        self.assertEqual(self.gates.objective(table, ("phantom", "real")), 0.5)

    def test_a_fingerprint_arm_with_no_cell_is_missing_its_data(self):
        bars = plan_of("qa_smoke")["bars"]["fingerprint"]
        result = self.gates.fingerprint_gate({"ap/none/typical": {"n": 8, "right": 8, "accuracy": 1.0, "low": 0.7,
                                                                  "median_margin": 4.0}}, bars, ("none",), "real")
        self.assertFalse(result["pass"])
        self.assertIn("no real cell under the anchors none to judge", result["missing"])

    def test_the_anomaly_bars_read_the_lower_bounds_where_the_round_gives_them(self):
        bars = plan_of("qa_smoke")["bars"]["anomaly"]
        lucky = {"t13": {"n": 4, "dice": 0.9, "named_right": 0.9, "probe_recall": 0.9}}
        self.assertTrue(self.gates.anomaly_gate(lucky, bars, ["t13"])["pass"])
        lucky["t13"].update(dice_low=0.7, named_low=0.85, probe_low=0.8)
        result = self.gates.anomaly_gate(lucky, bars, ["t13"])
        self.assertFalse(result["pass"])
        self.assertEqual(result["failing"], ["t13: Dice lower bound 0.700 below 0.8"])
        self.assertLess(self.gates.mean_low([0.9, 0.8, 1.0, 0.9]), 0.9)
        self.assertTrue(math.isnan(self.gates.mean_low([0.9])))

    def test_the_test_persons_ids_and_the_agreed_levels_are_read_strictly(self):
        samples = load_tool("qaloop_samples")
        for written in ("case134", "Case_0134", "134", " case 134 "):
            self.assertEqual(samples.case_person(written), "carmlspine:case134")
        for written in ("caseA", "x134", "case134_ap", ""):
            self.assertIsNone(samples.case_person(written))

        def entry(levels, flags=()):
            return {"variant_flags": list(flags), "vertebrae": [{"level": lv, "agree": True} for lv in levels]}

        # a gap where the labellers disagree is never bridged: the longest consecutive stretch, the first of two alike
        self.assertEqual(samples.agreed_levels(entry(["T12", "L1", "L3", "L4", "L5"])), ["L3", "L4", "L5"])
        self.assertEqual(samples.agreed_levels(entry(["L1", "L2", "L4", "L5"])), ["L1", "L2"])
        self.assertIsNone(samples.agreed_levels(entry(["L1", "L2"], flags=["six_lumbar"])))

    def test_a_subregion_mask_with_no_canal_is_left_out_and_the_levels_read_whole(self):
        import importlib
        import sys
        import numpy as np
        samples = load_tool("qaloop_samples")
        saved = list(sys.path)
        try:
            sys.path.insert(0, str(ROOT / "grid" / "autoanatomist"))
            schemes = importlib.import_module("scanimport.schemes")
        finally:
            sys.path[:] = saved
        self.assertEqual(samples.SUB_CANAL, schemes.SUB_CANAL)
        # as C-ArmLSpine's CBCT masks carry them: the vertebra's parts and the sacrum's (70 to 74), no canal
        carm = np.zeros((4, 4, 4), np.int16)
        carm[0, :2, :2], carm[1, :2, :2], carm[2, :2, :2] = 49, 41, 72
        self.assertIsNone(samples.subregions_to_read(carm, carm.shape))
        canal = carm.copy()
        canal[3, :2, :2] = samples.SUB_CANAL
        self.assertIs(samples.subregions_to_read(canal, canal.shape), canal)
        self.assertIsNone(samples.subregions_to_read(canal, (4, 4, 5)))
        self.assertIsNone(samples.subregions_to_read(None, (4, 4, 4)))


def load_tool(name):
    """A tool of tools/ loaded by its path, sys.path as it was after, since the round tool sets its own."""
    import sys
    saved = list(sys.path)
    try:
        spec = importlib.util.spec_from_file_location(f"{name}_under_test", ROOT / "tools" / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path[:] = saved


def answer_or_die(job):
    """A pool's job that kills the worker it runs in when asked, as the kernel kills one that runs the
    memory out, and answers in the process that runs the pool."""
    import multiprocessing
    import os
    if job == "die" and multiprocessing.parent_process() is not None:
        os._exit(9)
    return job


@unittest.skipIf(MISSING, f"needs numpy ({', '.join(MISSING)} missing)")
class PoolTest(unittest.TestCase):
    def test_a_killed_worker_slows_the_pool_and_every_job_is_answered_in_order(self):
        round_tool = load_tool("qaloop_round")
        said = []
        jobs = ["a", "die", "b", "c"]
        self.assertEqual(round_tool.run_pool(answer_or_die, jobs, 4, said.append), jobs)
        self.assertTrue(said and "a worker was killed" in said[0], said)

    def test_the_presence_floor_keeps_two_landmarks_at_least(self):
        round_tool = load_tool("qaloop_round")
        nan = float("nan")
        self.assertEqual(round_tool.floor_pool([0, 1, 2, 3], [0.9, 0.2, nan, 0.7], 0.0), [0, 1, 2, 3])
        self.assertEqual(round_tool.floor_pool([0, 1, 2, 3], [0.9, 0.2, nan, 0.7], 0.5), [0, 3])
        self.assertEqual(round_tool.floor_pool([0, 1, 2, 3], [0.9, 0.2, nan, 0.1], 0.5), [0, 1])
        self.assertEqual(round_tool.floor_pool([0, 1, 2, 3], [nan, nan, nan, 0.1], 0.5), [0, 1, 2, 3])


@unittest.skipIf(MISSING, f"needs numpy ({', '.join(MISSING)} missing)")
class ExternalArmTest(unittest.TestCase):
    """The external real arms (docs/research/qa-loop-external/PREREG.md): the sacral anchor's points, the anchor's
    presence, the pair builder's levels and frame geometry, and the round reading a built arm for the gates alone."""

    def column(self):
        """A sacrum (VerSe 26) wider at its top, with an L5 (24) above it along +z, in RAS with 1 mm voxels."""
        import numpy as np
        labels = np.zeros((40, 40, 60), np.int16)
        labels[8:32, 10:24, 5:25] = 26          # the sacrum: x 8 to 31, y 10 to 23, z 5 to 24
        labels[2:38, 12:20, 20:25] = 26         # its alae, wider near the top
        labels[14:26, 12:22, 30:40] = 24        # L5 above it
        return labels, np.eye(4)

    def test_the_sacral_points_sit_on_the_top_of_s1_at_its_front_and_its_two_sides(self):
        import numpy as np
        samples = load_tool("qaloop_samples")
        labels, affine = self.column()
        pts = samples.sacral_points(labels, affine)
        self.assertEqual(pts.shape, (4, 3))
        promontory, centre, ala_one, ala_two = pts
        self.assertGreaterEqual(promontory[2], 24 - samples.SACRAL_TOP_MM)   # in the top slab
        self.assertEqual(promontory[1], 23)                                 # its most anterior voxel, +y in RAS
        self.assertEqual(sorted([ala_one[0], ala_two[0]]), [2, 37])         # the alae, the two lateral extremes
        self.assertTrue(np.isnan(samples.sacral_points(np.zeros((5, 5, 5), np.int16), affine)).all())
        # alae that rise above the endplate leave the top of S1 where the midline's body ends
        labels[2:8, 12:20, 25:29] = 26
        labels[32:38, 12:20, 25:29] = 26
        promontory, centre, _, _ = samples.sacral_points(labels, affine)
        self.assertLessEqual(promontory[2], 24)
        self.assertLessEqual(centre[2], 24)
        self.assertTrue(abs(centre[0] - 19.5) <= samples.SACRAL_MIDLINE_MM)

    def test_the_anchor_is_read_only_where_three_points_fall_in_the_frame(self):
        import numpy as np
        samples = load_tool("qaloop_samples")
        G = samples.G
        K = np.array([[1000.0, 0, 256], [0, 1000.0, 256], [0, 0, 1]])
        P = G.projection_matrix(K, np.eye(3), np.array([0.0, 0.0, 1000.0]))
        rng = np.random.default_rng(0)
        frame = {"view": "ap_real", "P": P, "image": rng.random((512, 512)).astype(np.float32), "edge_ncc": float("nan")}
        pair = {"frames": [frame], "sacral": np.array([[0.0, 0, 0], [20, 0, 0], [0, 20, 0], [-20, 0, 0]])}
        got = samples.pair_anchor(pair)
        self.assertEqual(len(got), 1)
        self.assertTrue(0.0 <= got[0] <= 1.0, got)
        pair["sacral"] = np.array([[0.0, 0, 0], [900, 0, 0], [0, 900, 0], [-900, 0, 0]])     # three of four off the frame
        self.assertTrue(np.isnan(samples.pair_anchor(pair)[0]))
        pair["sacral"] = np.full((4, 3), np.nan)
        self.assertTrue(np.isnan(samples.pair_anchor(pair)[0]))
        # four points on one line, as a lateral view can put them, with no body beside them: NaN, never a crash
        pair["sacral"] = np.array([[0.0, 0, 0], [10, 10, 0], [20, 20, 0], [30, 30, 0]])
        self.assertTrue(np.isnan(samples.pair_anchor(pair)[0]))
        # with the lowest level's landmarks beside them the outline holds points and the anchor reads
        pair["landmarks"] = rng.uniform(-40, 40, size=(1, 18, 3)) * np.array([1, 1, 0])
        got = samples.pair_anchor(pair)[0]
        self.assertTrue(0.0 <= got <= 1.0, got)

    def test_the_builders_levels_are_the_longest_agreed_stretch_and_a_padded_frame_keeps_its_projection(self):
        import json
        import tempfile
        import numpy as np
        from PIL import Image
        realx = load_tool("realx_pairs")
        entry = {"vertebrae": [{"level": "L3", "agree": True}, {"level": "L4", "agree": True}, {"level": "L5", "agree": True},
                               {"level": None, "agree": False}], "variant_flags": ["level names disagree"]}
        self.assertEqual(realx.agreed_stretch(entry), ["L3", "L4", "L5"])
        self.assertEqual(realx.agreed_stretch({"vertebrae": [{"level": "L4", "agree": True}]}), [])
        record = {"structures": {"L2": {"level": "L2", "level_agree": True}, "L3": {"level": "L3", "level_agree": False},
                                 "L4": {"level": "L4", "level_agree": True}, "L5": {"level": "L5", "level_agree": True}}}
        self.assertEqual(realx.cobra_levels(record), ["L4", "L5"])
        with tempfile.TemporaryDirectory() as tmp:
            png = Path(tmp) / "f.png"
            Image.new("L", (400, 200), 128).save(png)                       # wider than tall: padded top and bottom
            K = [[900.0, 0, 200.0], [0, 900.0, 100.0], [0, 0, 1]]
            meta = {"pose": {"K": K, "ext": np.eye(4).tolist(), "qc_edge_ncc": 0.8}, "view": {"lat_from_ap_deg": 80.0}}
            fr = realx.frame_of(meta, png)
            self.assertEqual(fr["view"], "lat_real")
            self.assertIsNone(realx.frame_of(dict(meta, view={"lat_from_ap_deg": 40.0}), png))   # oblique: never seen
            self.assertEqual(realx.view_of({"view": {"lat_from_ap_deg": -170.0}}), "ap_real")
            self.assertEqual(fr["image"].shape, (512, 512))
            point = np.array([[10.0, -5.0, 1000.0]])
            u, v, w = np.asarray(K) @ point[0]
            want = np.array([u / w, v / w + 100]) * 512 / 400                # the canvas adds 100 rows above, then scales
            self.assertTrue(np.allclose(realx.G.project(fr["P"], point)[0], want), (realx.G.project(fr["P"], point), want))
            flipped = realx.orient(-fr["P"], point)
            self.assertTrue(np.allclose(flipped, fr["P"]))
            json.dumps(meta)

    def test_the_round_reads_an_external_arm_for_the_gates_alone_and_refuses_a_manifest_of_another(self):
        import json
        import tempfile
        import numpy as np
        round_tool = load_tool("qaloop_round")
        samples = round_tool.S
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "realx" / "demo"
            folder.mkdir(parents=True)
            frame = {"view": "ap_real", "P": np.eye(3, 4), "image": np.zeros((8, 8), np.float32), "edge_ncc": 0.5}
            samples.save_pair(str(folder / "a.npz"), {"levels": ["L4", "L5"], "landmarks": np.zeros((2, 18, 3)),
                                                     "sacrum": np.zeros(3), "frames": [frame], "stand_in": False})
            manifest = {"source": "demo", "size": 512, "persons": [{"person": "demo:a", "npz": "a.npz"}],
                        "held_out": [{"person": "demo:b"}], "left_out": {"demo:c": "why"}}
            (folder / "manifest.json").write_text(json.dumps(manifest))
            said = []
            pairs, record = round_tool.external_pairs({"size": 512, "external": [{"source": "demo", "folder": "realx/demo"}]}, tmp, said.append)
            self.assertEqual([(p["person"], p["part"], p["source"]) for p in pairs], [("demo:a", "validation", "demo")])
            self.assertEqual({k: record["demo"][k] for k in ("persons", "frames", "held_out", "left_out")},
                             {"persons": 1, "frames": 1, "held_out": 1, "left_out": 1})
            self.assertEqual(len(record["demo"]["manifest_sha256"]), 64)
            self.assertTrue(np.isnan(pairs[0]["sacral"]).all())             # a cache written before the anchor reads as none
            with self.assertRaises(RuntimeError):
                round_tool.external_pairs({"size": 384, "external": [{"source": "demo", "folder": "realx/demo"}]}, tmp, said.append)


class ShippedAnnotationsTest(unittest.TestCase):
    """DeepFluoro's own annotations against the arm (tools/deepfluoro_shipped.py, tools/realx_pairs.py annotations):
    the shipped coordinates reach the loop's canvas as the export reads them, and the check finds the person's
    landmarks where the pair's pose puts them, the arm's landmarks on the shipped labels, and the presence measure
    seeing edges a person marked."""

    NAMES = ["ASIS-l", "ASIS-r", "FH-l", "FH-r", "GSN-l", "GSN-r", "IOF-l", "IOF-r", "IPS-l", "IPS-r", "MOF-l", "MOF-r",
             "SPS-l", "SPS-r"]

    def test_the_shipped_coordinates_reach_the_loop_canvas_turned_with_the_image(self):
        import numpy as np
        ds = load_tool("deepfluoro_shipped")
        # a full-resolution pixel centre is the export's (u + 0.5) / 4 at 384, which is (u + 0.5) / 3 at 512
        self.assertTrue(np.allclose(ds.to_loop(np.array([[0.0, 1535.0]]), 0, 1536, 1536), [[0.5 / 3, 1535.5 / 3]]))
        self.assertTrue(np.allclose(ds.to_loop(np.array([[0.0, 1535.0]]), 1, 1536, 1536), [[512 - 0.5 / 3, 512 - 1535.5 / 3]]))
        seg = np.zeros((1536, 1536), np.uint8)
        seg[:3, :2] = 4                                    # two of a block's three columns: the block takes the label
        seg[3:6, :1] = 3                                   # one of three: it does not
        got = ds.seg_to_loop(seg, 0)
        self.assertEqual(got.shape, (512, 512))
        self.assertEqual((got[0, 0], got[1, 0]), (4, 0))
        self.assertEqual(ds.seg_to_loop(seg, 1)[511, 511], 4)          # turned with the image
        self.assertTrue(ds.is_interior("FH-l") and not ds.is_interior("GSN-r"))

    def build(self, tmp, rots):
        import numpy as np
        samples = load_tool("qaloop_samples")
        G = samples.G
        rng = np.random.default_rng(3)
        K = np.array([[1200.0, 0, 256], [0, 1200.0, 256], [0, 0, 1]])
        P = G.projection_matrix(K, np.eye(3), np.array([0.0, 0.0, 1000.0]))
        lm3d = np.column_stack([rng.uniform(-120, 120, 14), rng.uniform(-120, 120, 14), rng.uniform(-30, 30, 14)])
        marks = np.stack([rng.uniform(-60, 60, (18, 3)) * np.array([1, 1, 0.2]) + np.array([0, -80 + 40 * i, 0]) for i in range(2)])
        sacral = np.array([[0.0, 10, 0], [0, 0, 0], [30, 0, 0], [-30, 0, 0]])
        frames, raws, segs = [], [], []
        for k, rot in enumerate(rots):
            image = np.zeros((512, 512), np.float32)
            uv = G.project(P, lm3d)
            for u, v in uv:                               # a bright patch at each landmark a person marked: an edge there
                image[int(v) - 2:int(v) + 3, int(u) - 2:int(u) + 3] = 1.0
            frames.append({"view": "ap_real", "P": P, "image": image, "edge_ncc": float("nan")})
            raw = (512 - uv if rot else uv) * 1536 / 512 - 0.5
            raws.append(raw)
            seg = np.zeros((512, 512), np.uint8)
            for pts in list(G.project(P, marks)) + [G.project(P, sacral)]:
                lo, hi = np.floor(pts.min(axis=0)).astype(int), np.ceil(pts.max(axis=0)).astype(int)
                seg[max(lo[1], 0):hi[1], max(lo[0], 0):hi[0]] = 3
            segs.append(seg[::-1, ::-1] if rot else seg)   # the shipped labels sit on the frame before it is turned
        out, shipped = Path(tmp) / "arm", Path(tmp) / "shipped"
        out.mkdir()
        shipped.mkdir()
        samples.save_pair(str(out / "c.npz"), {"levels": ["L4", "L5"], "landmarks": marks, "sacrum": np.zeros(3), "sacral": sacral,
                                              "frames": frames, "stand_in": False})
        ids = [f"{k:03d}" for k in range(len(rots))]
        (out / "manifest.json").write_text(json.dumps({"source": "deepfluoro", "size": 512, "held_out": [],
                                                       "persons": [{"person": "deepfluoro:c", "case": "c", "npz": "c.npz", "frame_ids": ids}]}))
        full_segs = [np.kron(s, np.ones((3, 3), np.uint8)) for s in segs]
        np.savez(shipped / "c.npz", names=np.asarray(self.NAMES), lm3d=lm3d, raw=np.asarray(raws), rot=np.asarray(rots),
                 cols=1536, rows=1536, frame_ids=np.asarray(ids),
                 seg=np.asarray([load_tool("deepfluoro_shipped").seg_to_loop(s, r) for s, r in zip(full_segs, rots)]))
        return out, shipped

    def test_the_check_finds_the_persons_landmarks_where_the_pose_puts_them(self):
        import tempfile
        realx = load_tool("realx_pairs")
        with tempfile.TemporaryDirectory() as tmp:
            out, shipped = self.build(tmp, [0, 1] * 5)          # ten frames: enough for the share's lower bound
            report = realx.annotations(out, shipped)
            winner = report["reprojection"]["winner"]
            self.assertTrue(report["reprojection"]["pass"], report["reprojection"])
            self.assertEqual((winner["order"], winner["turned_with_image"]), ("column first", True))
            self.assertLess(winner["median_px"], 0.01)
            # reading the turned frames' coordinates without the turn lands them far off
            other = [r for r in report["reprojection"]["readings"] if r["order"] == "column first" and not r["turned_with_image"]][0]
            self.assertGreater(other["p90_px"], 10)
            self.assertTrue(report["spine"]["pass"], report["spine"])
            self.assertTrue(report["sacral"]["pass"], report["sacral"])
            self.assertTrue(report["presence"]["person_outline_landmarks"]["pass"], report["presence"])
            self.assertIn("canal_ap.anterior", report["presence"]["arm_by_landmark"])
            self.assertTrue((shipped / "annotations.json").is_file() and (shipped / "annotations_sheet.png").is_file())
            self.assertEqual(sorted(x.name for x in out.iterdir()), ["c.npz", "manifest.json"])     # the arm is never written


if __name__ == "__main__":
    unittest.main()
