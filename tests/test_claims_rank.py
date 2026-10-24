"""tools/claims_rank.py: the weight formula, the cost factor, what next picks, and the checks that
keep the claims register (docs/textbook/claims.json) whole."""

import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("claims_rank", ROOT / "tools" / "claims_rank.py")
claims_rank = importlib.util.module_from_spec(spec)
sys.modules["claims_rank"] = claims_rank
spec.loader.exec_module(claims_rank)


def register():
    """Two claims and three items small enough to work out by hand."""
    return {
        "stakes": {"patent": "the patent", "talk": "the talk"},
        "claims": [
            {"id": "N1", "kind": "novelty", "statement": "new", "stakes": ["patent"], "grade": "Unverified",
             "evidence": [{"chapter": "19", "source": "a paper", "grade": "Unverified"}]},
            {"id": "F1", "kind": "functionality", "statement": "works", "stakes": ["patent", "talk"],
             "grade": "Inferred", "evidence": [{"chapter": "03", "source": "a page", "grade": "Inferred"}]},
        ],
        "items": [
            {"id": "E1", "title": "read", "what": "read the papers", "needs_owner_word": False,
             "bears_on": [{"claim": "N1", "to": "Inferred", "could_refute": True}],
             "cost": {"session_hours": 2, "basis": "estimate"}, "depends_on": [], "status": "open"},
            {"id": "E2", "title": "train", "what": "train and score", "needs_owner_word": True,
             "bears_on": [{"claim": "F1", "to": "Measured"}],
             "cost": {"gpu_hours": [2, 6], "basis": "estimate"}, "depends_on": ["E3"], "status": "open"},
            {"id": "E3", "title": "freeze", "what": "freeze the plan", "needs_owner_word": True,
             "bears_on": [], "cost": {"basis": "a decision"}, "depends_on": [], "status": "open"},
        ],
    }


class TheFormula(unittest.TestCase):
    def test_criticality_sums_the_weights_of_the_stakes(self):
        claim = register()["claims"][1]
        self.assertEqual(claims_rank.criticality(claim), 5 + 4)

    def test_a_refutation_counts_a_step_even_with_no_rise_in_grade(self):
        claim = register()["claims"][1]
        self.assertEqual(claims_rank.move({"to": "Inferred", "could_refute": True}, claim), 1)
        self.assertEqual(claims_rank.move({"to": "Inferred"}, claim), 0)
        self.assertEqual(claims_rank.move({"to": "Measured"}, claim), 2)

    def test_a_range_counts_at_its_midpoint(self):
        item = register()["items"][1]
        self.assertAlmostEqual(claims_rank.cost_factor(item), 1 + claims_rank.GPU_HOUR * 4)

    def test_an_unsized_cost_and_an_outside_party_add_their_constants(self):
        cost = {"unknown": ["grid"], "external": "counsel", "basis": "none"}
        expected = 1 + claims_rank.UNKNOWN_COST["grid"] + claims_rank.EXTERNAL_PARTY
        self.assertAlmostEqual(claims_rank.cost_factor({"cost": cost}), expected)

    def test_an_item_carries_a_share_of_what_it_unlocks(self):
        weights = claims_rank.weights(register())
        own_e2 = 9 * 2
        self.assertEqual(weights["E2"], own_e2)
        self.assertEqual(weights["E3"], claims_rank.UNLOCK_SHARE * own_e2)
        self.assertEqual(weights["E1"], 5 * 1)

    def test_a_done_item_unlocks_nothing_and_is_not_ranked(self):
        data = register()
        data["items"][1]["status"] = "done"
        weights = claims_rank.weights(data)
        self.assertNotIn("E2", weights)
        self.assertEqual(weights["E3"], 0)

    def test_the_ranking_is_score_first(self):
        rows = claims_rank.ranked(register())
        scores = [row["score"] for row in rows]
        self.assertEqual(scores, sorted(scores, reverse=True))


class Next(unittest.TestCase):
    def test_next_picks_ready_items_with_and_without_the_owner(self):
        chosen = claims_rank.next_items(register())
        self.assertEqual(chosen["without_owner_word"]["id"], "E1")
        self.assertEqual(chosen["with_owner_word"]["id"], "E3")

    def test_an_item_waiting_on_an_open_item_is_not_next(self):
        data = register()
        data["items"][2]["bears_on"] = []
        data["items"][1]["bears_on"] = [{"claim": "F1", "to": "Measured"}]
        chosen = claims_rank.next_items(data)
        self.assertNotEqual(chosen["with_owner_word"]["id"], "E2")

    def test_next_prints_json_the_integration_can_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claims.json"
            path.write_text(json.dumps(register()), encoding="utf-8")
            out = io.StringIO()
            with redirect_stdout(out):
                code = claims_rank.main(["next", "--file", str(path)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())["without_owner_word"]["bears_on"][0]["claim"], "N1")


class Status(unittest.TestCase):
    def test_an_item_under_way_is_not_next_but_stays_ranked(self):
        data = register()
        data["items"][0]["status"] = "doing"
        chosen = claims_rank.next_items(data)
        self.assertIsNone(chosen["without_owner_word"])
        self.assertIn("E1", [row["item"]["id"] for row in claims_rank.ranked(data)])

    def test_an_item_with_no_status_is_open(self):
        data = register()
        del data["items"][0]["status"]
        self.assertEqual(claims_rank.next_items(data)["without_owner_word"]["id"], "E1")
        self.assertEqual(claims_rank.problems(data), [])

    def test_a_done_item_is_not_in_the_queue_and_an_item_under_way_is(self):
        data = register()
        data["items"][0]["status"] = "doing"
        data["items"][2]["status"] = "done"
        listed = {entry["id"]: entry for entry in claims_rank.queue(data)}
        self.assertEqual(set(listed), {"E1", "E2"})
        self.assertEqual(listed["E1"]["status"], "doing")
        self.assertTrue(listed["E2"]["ready"])
        self.assertEqual(sorted(entry["rank"] for entry in listed.values()), [1, 2])

    def test_a_status_outside_the_three_is_caught(self):
        data = register()
        data["items"][0]["status"] = "paused"
        found = claims_rank.problems(data)
        self.assertTrue(any("is not one of open, doing, done" in problem for problem in found), found)

    def test_the_register_itself_holds_together_and_gives_every_item_a_status(self):
        data = claims_rank.load()
        self.assertEqual(claims_rank.problems(data), [])
        self.assertTrue(all(item.get("status") in claims_rank.STATUSES for item in data["items"]))


class TheChecks(unittest.TestCase):
    def assert_problem(self, data, words):
        found = claims_rank.problems(data)
        self.assertTrue(any(words in problem for problem in found), found)

    def test_the_small_register_holds_together(self):
        self.assertEqual(claims_rank.problems(register()), [])

    def test_a_reference_to_no_claim_is_caught(self):
        data = register()
        data["items"][0]["bears_on"][0]["claim"] = "N9"
        self.assert_problem(data, "which is no claim")

    def test_a_grade_outside_the_four_is_caught(self):
        data = register()
        data["claims"][0]["grade"] = "Verified"
        self.assert_problem(data, "is not one of the four")

    def test_a_grade_that_is_not_the_weakest_link_is_caught(self):
        data = register()
        data["claims"][1]["evidence"].append({"chapter": "03", "source": "x", "grade": "Unverified"})
        self.assert_problem(data, "is not its weakest link")

    def test_a_novelty_claim_cannot_become_measured(self):
        data = register()
        data["items"][0]["bears_on"][0]["to"] = "Measured"
        self.assert_problem(data, "cannot become Measured")

    def test_items_waiting_on_each_other_are_caught(self):
        data = register()
        data["items"][2]["depends_on"] = ["E2"]
        self.assert_problem(data, "in a circle")

    def test_a_stake_with_no_weight_is_caught(self):
        data = register()
        data["claims"][0]["stakes"] = ["press"]
        self.assert_problem(data, "has no weight")

    def test_a_cost_range_that_runs_backwards_is_caught(self):
        data = register()
        data["items"][1]["cost"]["gpu_hours"] = [6, 2]
        self.assert_problem(data, "low-to-high range")

    def test_a_repository_source_that_does_not_exist_is_caught(self):
        data = copy.deepcopy(register())
        data["claims"][0]["evidence"][0]["source"] = "docs/research/no-such-note.md"
        self.assert_problem(data, "does not exist")

    def test_the_repository_register_holds_together(self):
        data = claims_rank.load()
        self.assertEqual(claims_rank.problems(data), [])
        self.assertTrue(claims_rank.table(data).startswith("| Rank |"))


if __name__ == "__main__":
    unittest.main()
