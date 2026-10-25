"""tools/choose_data.py: the power, the test, the training sets and the committed choice (#291)."""
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("choose_data", ROOT / "tools" / "choose_data.py")
choose_data = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(choose_data)

POWER = {"expected_accuracy": 0.5, "half_width": 0.05, "confidence": 0.95}
RECIPE = {"name": "research-internal", "allow": ["open", "non-commercial"], "reviewed_only": False}
SETTINGS = {"recipe": "research-internal", "power": POWER, "device_training_persons": 12,
            "test_groups": ["fluoro"], "fill_groups": ["fluoro"], "never_train": {"sweeps": "demo"}}


def record(rid, group="fluoro", reach="held", truth="yes, lumbar", **counts):
    return {"id": rid, "group": group, "reach": reach, "level_truth": truth, "counts": counts}


def licences(**classes):
    return {"aliases": {}, "sources": {k: {"class": v, "reviewed": "rule"} for k, v in classes.items()}}


class Power(unittest.TestCase):
    def test_the_feeds_power_by_wilson(self):
        self.assertEqual(choose_data.people_needed(POWER), 381)

    def test_a_higher_expected_accuracy_needs_fewer(self):
        self.assertEqual(choose_data.people_needed(dict(POWER, expected_accuracy=0.95)), 83)

    def test_n_is_the_least_that_reaches_the_half_width(self):
        n = choose_data.people_needed(POWER)
        z = choose_data.z_of(0.95)
        self.assertLessEqual(choose_data.wilson_half_width(n, 0.5, z), 0.05)
        self.assertGreater(choose_data.wilson_half_width(n - 1, 0.5, z), 0.05)

    def test_bad_settings_are_refused(self):
        with self.assertRaises(choose_data.ChoiceError):
            choose_data.people_needed(dict(POWER, confidence=1))
        with self.assertRaises(choose_data.ChoiceError):
            choose_data.people_needed(dict(POWER, half_width=0))


class Truth(unittest.TestCase):
    def test_words(self):
        cases = {"yes, lumbar, projected from the CBCT": "read", "none; no spine": "none", "pelvis": "none",
                 "partial": "partial", "fractures; C1, C2, C7 anchors": "partial", "exact": "read",
                 "pseudo, no patient key": "none", "": "none", "pelvis and lower lumbar, from the CT": "read",
                 "levels readable from the paired CT after a 2D/3D registration": "derivable"}
        for text, word in cases.items():
            with self.subTest(text=text):
                self.assertEqual(choose_data.truth_of(text), word)


class TheChoice(unittest.TestCase):
    def choose(self, records, classes, frozen=()):
        persons = [{"person": p, "why": "frozen"} for p in frozen]
        return choose_data.choose(records, licences(**classes), RECIPE, persons, SETTINGS)

    def test_frozen_persons_and_device_persons_leave_the_test(self):
        out = self.choose([record("carm", cases=149)], {"carm": "open"}, frozen=["carm:a", "carm:b"])
        row = out["test"]["sources"][0]
        self.assertEqual((row["frozen_out"], row["training_persons"], row["test_persons"]), (2, 12, 135))
        self.assertEqual(out["test"]["shortfall"], 381 - 135)
        self.assertEqual(out["training"][0]["persons"], 12)

    def test_a_small_set_trains_whole_and_tests_none(self):
        out = self.choose([record("tiny", specimens=6)], {"tiny": "open"})
        self.assertEqual(out["test"]["sources"][0]["test_persons"], 0)

    def test_the_fill_is_ranked_by_people_and_says_where_the_gap_closes(self):
        records = [record("carm", cases=149), record("a", reach="get", patients=100),
                   record("b", reach="get", patients=300), record("c", reach="none")]
        out = self.choose(records, {"carm": "open"})
        self.assertEqual([(f["id"], f["closes_the_gap"]) for f in out["fill"]], [("b", True), ("a", True)])

    def test_licences_outside_the_recipe_and_never_trained_sets_are_excluded(self):
        records = [record("u", group="films"), record("nd", group="films"), record("sweeps", group="video")]
        out = self.choose(records, {"nd": "no-derivatives", "sweeps": "open"})
        self.assertEqual({e["id"]: e["why"][:12] for e in out["excluded"]},
                         {"nd": "licence clas", "sweeps": "never traine", "u": "licence unkn"})
        self.assertEqual(out["training"], [])

    def test_levels_a_registration_must_name_first_are_no_test(self):
        out = self.choose([record("lumos", truth="levels readable from the paired CT after a 2D/3D registration",
                                  patients=803)], {"lumos": "non-commercial"})
        self.assertEqual(out["test"]["sources"], [])
        self.assertEqual(out["training"][0]["level_truth"], "derivable")

    def test_ct_without_levels_is_no_render_source(self):
        out = self.choose([record("ct1", group="ct", truth="none"), record("ct2", group="ct", truth="yes")],
                          {"ct1": "open", "ct2": "open"})
        self.assertEqual([t["id"] for t in out["training"]], ["ct2"])
        self.assertEqual(out["excluded"][0]["id"], "ct1")

    def test_the_same_inputs_give_the_same_choice(self):
        records = [record("b", cases=50), record("a", cases=40)]
        one = choose_data.render(self.choose(records, {"a": "open", "b": "open"}))
        two = choose_data.render(self.choose(list(reversed(records)), {"a": "open", "b": "open"}))
        self.assertEqual(one, two)


class TheCommittedChoice(unittest.TestCase):
    def test_it_is_what_the_inputs_give(self):
        committed = (ROOT / "data" / "choice" / "CHOICE.json").read_text(encoding="ascii")
        self.assertEqual(committed, choose_data.render(choose_data.build()),
                         "run python3 tools/choose_data.py write and commit data/choice/CHOICE.json")

    def test_the_demo_sweeps_are_never_training(self):
        choice = json.loads((ROOT / "data" / "choice" / "CHOICE.json").read_text(encoding="ascii"))
        self.assertNotIn("carmlspine_sweeps", [t["id"] for t in choice["training"]])


if __name__ == "__main__":
    unittest.main()
