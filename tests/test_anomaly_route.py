"""tools/anomaly_route.py: the frozen holdout, the CT finder's score and the selection (#398)."""
import csv
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("anomaly_route", ROOT / "tools" / "anomaly_route.py")
route = importlib.util.module_from_spec(spec)
spec.loader.exec_module(route)

SCREEN_COLUMNS = ["case", "patient_key", "read_structure", "read_subtype", "mask_has_L6", "a_nL", "a_nT", "b_nL",
                  "b_nL_contact", "b_nT", "labeller_a", "labeller_b", "junction_tl_in_fov", "junction_ls_in_fov", "review",
                  "disposition"]
CONTRADICTS = "a voxel count from the mask or labeller A contradicts the published read"
REGISTRY_COLUMNS = ["patient_key", "subtype", "truth_tier", "four_lumbar", "winning_source", "winning_case", "real_frames",
                    "frames_role", "junction_tl_in_fov", "junction_ls_in_fov"]


def scan(case, structure, a_nl="", a_nt="", b_nl="", b_nt="", labeller_b="", review="", subtype="", disposition=""):
    return {"case": case, "patient_key": f"verse:{case}", "read_structure": structure, "read_subtype": subtype,
            "mask_has_L6": "False", "a_nL": a_nl, "a_nT": a_nt, "b_nL": b_nl, "b_nL_contact": b_nl, "b_nT": b_nt,
            "labeller_a": "", "labeller_b": labeller_b, "junction_tl_in_fov": "True", "junction_ls_in_fov": "True",
            "review": review, "disposition": disposition}


def write(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


class Calls(unittest.TestCase):
    def test_the_readers_structure_names_the_variant(self):
        self.assertEqual(route.truth_of("7/12/6/5"), "L6")
        self.assertEqual(route.truth_of("7/11/6/5"), "L6")
        self.assertEqual(route.truth_of("7/13/5/5"), "T13")
        self.assertEqual(route.truth_of("7/12/4/5"), "four_lumbar")
        self.assertEqual(route.truth_of("7/12/5/5"), "normal")
        self.assertIsNone(route.truth_of(""))
        self.assertIsNone(route.truth_of("7/12/5"))

    def test_a_variant_is_called_only_where_both_labellers_count_the_same(self):
        self.assertEqual(route.two_labeller_call(scan("verse1", "", a_nl="6", b_nl="6")), "L6")
        self.assertEqual(route.two_labeller_call(scan("verse1", "", a_nl="6", b_nl="5")), "discordant")
        self.assertEqual(route.two_labeller_call(scan("verse1", "", a_nl="6")), "single")
        # labeller B's thoracic count by rib contact, from its text, stands beside A's T13
        self.assertEqual(route.two_labeller_call(scan("verse1", "", a_nl="5", a_nt="13", b_nl="5", b_nt="12",
                                                      labeller_b="L6 [nT=12 nL=6]; by rib contact nT=13")), "T13")
        # A's T13 alone is no two-labeller call, though VERIDAH alone makes it
        alone = scan("verse1", "", a_nl="5", a_nt="13", b_nl="5")
        self.assertEqual(route.two_labeller_call(alone), "normal")
        self.assertEqual(route.veridah_call(alone), "T13")


class Holdout(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        rows = [scan(f"verse{500 + n}", "7/12/6/5", a_nl="6", b_nl="6") for n in range(30)]
        rows += [scan(f"verse{600 + n}", "7/13/5/5", a_nl="5", a_nt="13", b_nl="5") for n in range(5)]
        rows += [scan(f"verse{700 + n}", "7/12/4/5", a_nl="4", b_nl="4") for n in range(3)]
        rows += [scan(f"verse{100 + n}", "7/12/5/5", a_nl="5", b_nl="5") for n in range(60)]
        rows.append(scan("verse707", "7/12/5/5", review="read NORMAL but release mask carries an L6 (id 25)"))
        # the mask contradicts this read, so it is disputed; labeller A alone contradicts the next, so it is scored
        rows.append(scan("verse026", "7/12/6/5", a_nl="5", b_nl="5", review=CONTRADICTS,
                         disposition="read, CONTRADICTED by mask lumbar ids + unlabelled bodies below = 5 (supported by B counts 5)"))
        rows.append(scan("verse588", "7/13/5/5", a_nl="5", a_nt="12", b_nl="5", review=CONTRADICTS,
                         disposition="read, CONTRADICTED by A counts 12 thoracic (supported by release mask id 28)"))
        self.screen = write(self.tmp / "screened.csv", SCREEN_COLUMNS, rows)
        table = [{"verse_id": str(number), "in_verse2019": "1" if number < 550 else "0"} for number in range(100, 800)]
        self.table = write(self.tmp / "table.csv", ["verse_id", "in_verse2019"], table)
        ctsp = [{"patient_key": f"ctsp:{n:04d}", "subtype": "sacralised_L5_fused", "truth_tier": "read", "winning_source": "ctsp",
                 "winning_case": f"{n:04d}", "frames_role": "CT-only", "junction_tl_in_fov": "True", "junction_ls_in_fov": "True"}
                for n in range(600, 612)]
        self.registry = write(self.tmp / "registry-frozen.csv", REGISTRY_COLUMNS, ctsp)

    def frozen(self):
        return route.freeze(self.screen, self.table, self.registry)

    def test_the_same_inputs_freeze_the_same_list_and_the_disputed_are_never_held(self):
        first, second = self.frozen(), self.frozen()
        self.assertEqual(first, second)
        held = {entry["person"] for entry in first["persons"]}
        self.assertNotIn("verse:verse707", held)
        self.assertIn("verse:verse707", first["disputed"])
        self.assertIn("verse:verse026", first["disputed"])
        self.assertNotIn("verse:verse588", first["disputed"])
        counts = {variant: sum(entry["variant"] == variant for entry in first["persons"] if entry["release"] != "ctspinopelvic1k")
                  for variant in ("T13", "L6", "four_lumbar", "normal")}
        self.assertEqual(counts, route.HOLD)
        # a few of each variant are held, and the rest are left to train on
        self.assertLess(counts["T13"], 5)
        self.assertEqual(first["inputs"]["screen"]["sha256"], route.sha256_of(self.screen))

    def test_the_selection_refuses_every_held_out_person_and_keeps_paired_persons_for_testing(self):
        holdout = self.tmp / "holdout.json"
        holdout.write_text(json.dumps(self.frozen()), encoding="utf-8")
        held = [entry["person"] for entry in json.loads(holdout.read_text(encoding="utf-8"))["persons"]]
        registry = [{"patient_key": person, "subtype": "L6", "truth_tier": "read", "winning_source": "verse",
                     "winning_case": person.split(":")[1], "frames_role": "CT-only"} for person in held[:3]]
        registry += [{"patient_key": f"verse:verse{900 + n}", "subtype": "L6", "truth_tier": "two-labeller",
                      "winning_source": "verse", "winning_case": f"verse{900 + n}", "frames_role": "CT-only"} for n in range(3)]
        registry.append({"patient_key": "cobra2026:A270", "subtype": "L6", "truth_tier": "two-labeller",
                         "winning_source": "cobra2026", "winning_case": "A270", "real_frames": "True", "frames_role": "TEST"})
        registry.append({"patient_key": "ts:s1", "subtype": "L6", "truth_tier": "single-labeller", "winning_source": "totalsegmentator"})
        registry_path = write(self.tmp / "registry.csv", REGISTRY_COLUMNS, registry)
        harvest = self.tmp / "harvest"
        normals = [{"patient_key": f"amos:{n}", "case": str(n), "subtype": "ordinary", "truth_tier": "two-labeller",
                    "junction_tl_in_fov": "True", "junction_ls_in_fov": "True"} for n in range(20)]
        normals.append({"patient_key": "amos:cut", "case": "cut", "subtype": "ordinary", "truth_tier": "two-labeller",
                        "junction_tl_in_fov": "False", "junction_ls_in_fov": "True"})
        write(harvest / "amos22" / "rows.csv", ["patient_key", "case", "subtype", "truth_tier", "junction_tl_in_fov",
                                                "junction_ls_in_fov"], normals)
        chosen, left_out = route.select(registry_path, harvest, holdout)
        people = {entry["person"]: entry for entry in chosen}
        self.assertFalse(set(held) & set(people))
        self.assertEqual(people["cobra2026:A270"]["role"], "test")
        self.assertNotIn("ts:s1", people)
        self.assertNotIn("amos:cut", people)
        train = [entry for entry in chosen if entry["role"] == "train"]
        self.assertEqual(sum(entry["variant"] == "L6" for entry in train), 3)
        # normal counts fill the training list until variants are 30 percent: 3 variants, 7 normals
        self.assertEqual(sum(entry["variant"] == "normal" for entry in train), 7)
        listed = write(self.tmp / "list.csv", ["patient_key"], [{"patient_key": held[0]}])
        self.assertEqual(route.check(holdout, listed), [held[0]])

    def test_the_disputed_ctspinopelvic1k_records_are_refused_like_the_held_out(self):
        holdout = self.tmp / "holdout.json"
        holdout.write_text(json.dumps(self.frozen()), encoding="utf-8")
        self.assertIn("ctsp:0033", json.loads(holdout.read_text(encoding="utf-8"))["disputed"])
        registry = [{"patient_key": "ctsp:0033", "subtype": "L6", "truth_tier": "read", "winning_source": "ctsp",
                     "winning_case": "0033", "frames_role": "CT-only"},
                    {"patient_key": "ctsp:0097", "subtype": "L6", "truth_tier": "read", "winning_source": "ctsp",
                     "winning_case": "0097", "frames_role": "CT-only"}]
        registry_path = write(self.tmp / "registry.csv", REGISTRY_COLUMNS, registry)
        chosen, left_out = route.select(registry_path, self.tmp / "no-harvest", holdout)
        self.assertNotIn("ctsp:0033", {entry["person"] for entry in chosen})
        self.assertEqual(left_out["held out or disputed"], 1)
        listed = write(self.tmp / "list.csv", ["patient_key"], [{"patient_key": "ctsp:0033"}])
        self.assertEqual(route.check(holdout, listed), ["ctsp:0033"])

    def test_the_score_counts_a_missed_or_discordant_variant_as_a_miss(self):
        text = route.score(self.screen)
        self.assertIn("| L6: sensitivity | 30 of 30 (100.0 %", text)
        # A's T13 with no thoracic count from B is no two-labeller T13, and verse588, which A alone
        # contradicts, is scored as the finder's miss rather than left out
        self.assertIn("| T13: sensitivity | 0 of 6 (0.0 %", text)
        self.assertIn("disputed and left out 2", text)

    def test_the_folds_deal_every_clean_l6_not_held_once_and_the_ctsp_normals_are_held(self):
        frozen = self.frozen()
        held = {entry["person"] for entry in frozen["persons"]}
        folds = {entry["person"]: entry["fold"] for entry in frozen["folds"]}
        self.assertFalse(held & set(folds))
        self.assertEqual(len(folds), 30 - route.HOLD["L6"])
        sizes = sorted(list(folds.values()).count(fold) for fold in range(1, route.FOLDS + 1))
        self.assertLessEqual(sizes[-1] - sizes[0], 1)
        normals = [entry for entry in frozen["persons"] if entry["release"] == "ctspinopelvic1k" and entry["variant"] == "normal"]
        self.assertEqual(len(normals), route.CTSP_HOLD_NORMAL)

    def test_a_stream_screened_twice_is_one_person(self):
        holdout = self.tmp / "holdout.json"
        holdout.write_text(json.dumps(self.frozen()), encoding="utf-8")
        registry = write(self.tmp / "registry.csv", REGISTRY_COLUMNS, [
            {"patient_key": "ts:s0049", "subtype": "L6", "truth_tier": "two-labeller", "winning_source": "totalsegmentator",
             "winning_case": "s0049", "frames_role": "CT-only"}])
        write(self.tmp / "harvest" / "validation_ts" / "rows.csv", ["patient_key", "case", "subtype", "truth_tier"],
              [{"patient_key": "totalsegmentator_v2:s0049", "case": "s0049", "subtype": "L6", "truth_tier": "two-labeller"}])
        chosen, _ = route.select(registry, self.tmp / "harvest", holdout)
        self.assertEqual([entry["person"] for entry in chosen if entry["variant"] == "L6"], ["ts:s0049"])


if __name__ == "__main__":
    unittest.main()
