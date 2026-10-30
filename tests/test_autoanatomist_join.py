"""The numbers under the auto-anatomist join's verdicts (tools/autoanatomist_join.py, numbers_text):
each seed's final value by arm with the null first, each trial's readings as epoch=value in lines
of ten that the gate's 200 characters never cut, none for a reading with no value, and a failed
trial said to have no readings, read on the second smoke's plan, the longest a report carries.

It imports the package's contracts, so it needs beartype and icontract, which CI's python3 does
not hold: it is skipped there, and runs in the locked environment as
    pixi run python -m unittest tests.test_autoanatomist_join -v
"""

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEEDED = ("beartype", "icontract")
MISSING = [name for name in NEEDED if importlib.util.find_spec(name) is None]
PLAN = ROOT / "grid" / "screens" / "gold3_latent_smoke2.json"


def load_join():
    kept = list(sys.path)
    try:
        spec = importlib.util.spec_from_file_location("autoanatomist_join_under_test", ROOT / "tools" / "autoanatomist_join.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = kept
    return module


@unittest.skipIf(MISSING, f"needs the package's contracts ({', '.join(MISSING)} missing)")
class NumbersTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.join = load_join()
        from schwingnet.autoanatomist_screen import decide, evaluation_epochs, plan_of, trials

        cls.plan = plan_of(json.loads(PLAN.read_text(encoding="utf-8")))
        cls.epochs = evaluation_epochs(cls.plan)
        cls.entries = {}
        for at, trial in enumerate(trials(cls.plan)):
            if trial.arm == "restraint":
                continue  # failed: it wrote no entry
            readings = [{"epoch": e, "distance_mm": 10.0 - at - e / 100} for e in cls.epochs]
            if trial.arm == "adaptive":
                readings[0]["distance_mm"] = None
            cls.entries[trial.id] = {"epochs": readings, "final": {"distance_mm": readings[-1]["distance_mm"]}}
        cls.decision = decide(cls.plan, cls.entries)
        cls.lines = cls.join.numbers_text(cls.plan, cls.decision, cls.entries)

    def test_the_plan_reads_more_than_ten_times_so_a_trial_takes_two_lines(self):
        self.assertGreater(len(self.epochs), self.join.READINGS_A_LINE)
        first, cont = [line for line in self.lines if line.startswith("- cyclic_s1")]
        self.assertEqual(first, "- cyclic_s1: " + " ".join(f"{e}={9.0 - e / 100:.2f}" for e in self.epochs[:10]))
        self.assertEqual(cont, "- cyclic_s1 (cont.): " + " ".join(f"{e}={9.0 - e / 100:.2f}" for e in self.epochs[10:]))

    def test_each_finals_line_names_its_arm_with_the_null_first(self):
        finals = [line for line in self.lines if line.startswith("- final ")]
        self.assertEqual(finals[0], f"- final distance_mm of lambda_then_w (the null): s1 {self.entries['lambda_then_w_s1']['final']['distance_mm']:.2f}")
        self.assertEqual([line.split(" of ")[1].split(":")[0] for line in finals[1:]],
                         ["adaptive", "cyclic", "overlapping", "restraint"])
        self.assertIn("- final distance_mm of restraint: s1 none", finals)

    def test_a_reading_with_no_value_is_none_and_a_failed_trial_has_no_readings(self):
        self.assertTrue(any(line.startswith(f"- adaptive_s1: {self.epochs[0]}=none ") for line in self.lines))
        self.assertIn("- restraint_s1: no readings, since it failed", self.lines)

    def test_no_line_passes_the_gates_200_characters_or_holds_a_word_colon_value_the_gate_withholds(self):
        for line in self.lines:
            self.assertLessEqual(len(line), 200, line)
            # grid/redact.sed withholds what follows a lower-case word and a colon with no space between
            self.assertNotRegex(line, r"\b[a-z][a-z0-9_]*:[A-Za-z0-9]")


if __name__ == "__main__":
    unittest.main()
