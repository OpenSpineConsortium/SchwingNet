"""The numbers under the auto-anatomist join's verdicts (tools/autoanatomist_join.py, numbers_text):
each seed's final value by arm with the null first, each trial's readings as epoch=value in lines
of ten that the gate's 200 characters never cut, none for a reading with no value, and a failed
trial said to have no readings, read on the screen's two plans: the smoke's, whose fifteen
readings take two lines a trial, and the screen's, with a failed trial and a reading with none.

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
SCREENS = ROOT / "grid" / "screens"
FAILED = "w_first_s2"
NO_FIRST_VALUE = "joint_s1"


def load_join():
    kept = list(sys.path)
    try:
        spec = importlib.util.spec_from_file_location("autoanatomist_join_under_test", ROOT / "tools" / "autoanatomist_join.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = kept
    return module


def value(at, epoch):
    """A trial's made-up distance at a reading: lower for a later trial and a later epoch."""
    return 10.0 - at - epoch / 100


def made_up_entries(plan, epochs):
    """An entry for every trial but FAILED, which wrote none, NO_FIRST_VALUE's first reading empty."""
    from schwingnet.autoanatomist_screen import trials

    entries = {}
    for at, trial in enumerate(trials(plan)):
        if trial.id == FAILED:
            continue
        readings = [{"epoch": e, "distance_mm": value(at, e)} for e in epochs]
        if trial.id == NO_FIRST_VALUE:
            readings[0]["distance_mm"] = None
        entries[trial.id] = {"epochs": readings, "final": {"distance_mm": readings[-1]["distance_mm"]}}
    return entries


@unittest.skipIf(MISSING, f"needs the package's contracts ({', '.join(MISSING)} missing)")
class NumbersTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.join = load_join()
        from schwingnet.autoanatomist_screen import decide, evaluation_epochs, plan_of

        cls.read = {}
        for name in ("gold3_latent_smoke", "gold3_latent_screen"):
            plan = plan_of(json.loads((SCREENS / f"{name}.json").read_text(encoding="utf-8")))
            epochs = evaluation_epochs(plan)
            entries = made_up_entries(plan, epochs)
            lines = cls.join.numbers_text(plan, decide(plan, entries), entries)
            cls.read[name] = (epochs, entries, lines)

    def test_the_smoke_reads_more_than_ten_times_so_a_trial_takes_two_lines(self):
        epochs, _, lines = self.read["gold3_latent_smoke"]
        self.assertGreater(len(epochs), self.join.READINGS_A_LINE)
        first, cont = [line for line in lines if line.startswith("- lambda_then_w_s1")]
        self.assertEqual(first, "- lambda_then_w_s1: " + " ".join(f"{e}={value(0, e):.2f}" for e in epochs[:10]))
        self.assertEqual(cont, "- lambda_then_w_s1 (cont.): " + " ".join(f"{e}={value(0, e):.2f}" for e in epochs[10:]))

    def test_the_screen_reads_ten_times_so_a_trial_takes_one_line(self):
        epochs, _, lines = self.read["gold3_latent_screen"]
        self.assertEqual(len(epochs), self.join.READINGS_A_LINE)
        self.assertFalse([line for line in lines if "(cont.)" in line])

    def test_each_finals_line_names_its_arm_with_the_null_first(self):
        _, entries, lines = self.read["gold3_latent_screen"]
        finals = [line for line in lines if line.startswith("- final ")]
        null = [entries[f"null_s{seed}"]["final"]["distance_mm"] for seed in (1, 2)]
        self.assertEqual(finals[0], f"- final distance_mm of null (the null): s1 {null[0]:.2f}, s2 {null[1]:.2f}")
        self.assertEqual([line.split(" of ")[1].split(":")[0] for line in finals[1:]], ["joint", "lambda_then_w", "w_first"])
        w_first = entries["w_first_s1"]["final"]["distance_mm"]
        self.assertIn(f"- final distance_mm of w_first: s1 {w_first:.2f}, s2 none", finals)

    def test_a_reading_with_no_value_is_none_and_a_failed_trial_has_no_readings(self):
        epochs, _, lines = self.read["gold3_latent_screen"]
        self.assertTrue(any(line.startswith(f"- {NO_FIRST_VALUE}: {epochs[0]}=none ") for line in lines))
        self.assertIn(f"- {FAILED}: no readings, since it failed", lines)

    def test_no_line_passes_the_gates_200_characters_or_holds_a_word_colon_value_the_gate_withholds(self):
        for _, _, lines in self.read.values():
            for line in lines:
                self.assertLessEqual(len(line), 200, line)
                # grid/redact.sed withholds what follows a lower-case word and a colon with no space between
                self.assertNotRegex(line, r"\b[a-z][a-z0-9_]*:[A-Za-z0-9]")


if __name__ == "__main__":
    unittest.main()
