"""tools/gold3_ct.py: the gold tier 3 CT dataset's calls, classes, checks, store, pages and manifest.

Every test runs on synthetic facts rows that follow the facts schema (docs/research/gold3-ct/SPEC.md,
section 2) and on copies of the small committed records, in temporary folders: no mask, no grid and
nothing written into the repository.
"""
import ast
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import shutil
import sqlite3
import stat
import tempfile
import unittest
from enum import StrEnum
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_tool(name):
    """A module under tools/, loaded by path, since tools/ is no package."""
    found = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(found)
    found.loader.exec_module(module)
    return module


gold3 = load_tool("gold3_ct")

C1, C2, C7, T1, T6, T12, L1, L4, L5, L6, SACRUM = 1, 2, 7, 8, 13, 19, 20, 23, 24, 25, 28
NORMAL = (*range(C1, L5 + 1), SACRUM)
WITH_L6 = (*range(C1, L6 + 1), SACRUM)
NO_L5 = (*range(C1, L4 + 1), SACRUM)
HEIGHT = {**{C1: 12.0, C2: 30.0}, **{n: 15.0 for n in range(3, 8)}, **{n: 22.0 for n in range(T1, T12 + 1)},
          **{n: 28.0 for n in range(L1, L6 + 1)}, SACRUM: 90.0}
VOXELS = {**{C1: 8000, C2: 15000}, **{n: 10000 for n in range(3, 7)}, C7: 12000,
          **{n: 15000 for n in range(T1, T12 + 1)}, **{n: 30000 for n in range(L1, L6 + 1)}, SACRUM: 60000}
DISC_MM = 4.0
SACRUM_OVERLAP_MM = -6.0
SCANNER = {"manufacturer": "SIEMENS", "model": "Biograph128", "kvp": "120", "kernel": "B30f", "pixel_spacing": "0.8",
           "slice_thickness": "3"}
MASK_BYTES, RIB_BYTES, CT_BYTES = 123456, 2222, 98765432


def column(levels=NORMAL, top=-10.0, sacrum_gap=SACRUM_OVERLAP_MM):
    """Labels stacked head to foot from `top`, a disc between neighbours and the sacrum overlapping the
    lowest lumbar body, as the release's lumbosacral junction does."""
    labels, position = {}, top
    for label in levels:
        if label == SACRUM:
            position += DISC_MM - sacrum_gap
        height = HEIGHT[label]
        labels[str(label)] = {"voxels": VOXELS[label], "top_mm": round(position, 1),
                              "bottom_mm": round(position - height, 1), "centroid_mm": [1.0, 2.0, round(position - height / 2, 1)],
                              "components": 1, "largest_share": 1.0}
        position -= height + DISC_MM
    return labels


def rib_entry(lead, voxels=800, tie=False):
    contacts = {} if lead is None else {str(lead): 120}
    return {"voxels": voxels, "components": 1, "contacts": contacts, "lead": lead, "lead_n": 120 if lead else 0, "tie": tie}


def ribs(left=12, right=12, offset=0):
    """Rib 1 to `left` and 1 to `right`, each leading on its own body (label k + 7) plus `offset`."""
    out = {}
    for side, count in (("left", left), ("right", right)):
        for rib in range(1, count + 1):
            out[str(gold3.rib_label(side, rib))] = rib_entry(rib + 7 + offset)
    return out


def distances(labels, touch=0.6):
    have = sorted(int(key) for key in labels)
    out = {f"{a}-{a + 1}": 3.0 for a in have if a + 1 in have and a + 1 <= L6}
    lumbar = [label for label in have if L1 <= label <= L6]
    if SACRUM in have:
        for label in lumbar:
            out[f"{label}-{SACRUM}"] = round(touch + 15.0 * (max(lumbar) - label), 1)
    return out


def mask(top_slice_mm=0.0, slices=300, step=3.0):
    origin = top_slice_mm - step * (slices - 1)
    affine = [[-0.8, 0.0, 0.0, 200.0], [0.0, -0.8, 0.0, 200.0], [0.0, 0.0, step, origin], [0.0, 0.0, 0.0, 1.0]]
    return {"bytes": MASK_BYTES, "listed_bytes": MASK_BYTES, "sha256": "ab" * 32, "shape": [512, 512, slices],
            "zooms": [0.8, 0.8, step], "affine": affine, "axcodes": "LPS", "head_foot_axis": 2, "dtype": "uint8"}


def facts_row(sid, levels=NORMAL, site="autoPET", rib_entries=None, top=-10.0, top_slice_mm=0.0):
    labels = column(levels, top)
    return {"id": sid, "site": site, "mask": mask(top_slice_mm),
            "ribs_mask": {"bytes": RIB_BYTES, "listed_bytes": RIB_BYTES, "sha256": "cd" * 32, "same_grid": True},
            "scanner": dict(SCANNER), "labels": labels, "ribs": ribs() if rib_entries is None else rib_entries,
            "sternum_voxels": 3000, "distances_mm": distances(labels), "outside_scheme_voxels": {"vertebrae": 0, "ribs": 0}}


def normal(sid="0001", site="autoPET"):
    return facts_row(sid, site=site)


def l6_twelve(sid="0025"):
    return facts_row(sid, WITH_L6)


def l6_thirteen(sid="0026"):
    row = facts_row(sid, WITH_L6)
    row["ribs"].update({"13": rib_entry(L1), "26": rib_entry(L1)})
    return row


def four_lumbar(sid="0027"):
    """No L5 label; L4 overlaps the sacrum 8 mm head to foot and touches it in 3-D."""
    row = facts_row(sid, NO_L5)
    row["labels"] = column(NO_L5, sacrum_gap=-8.0)
    row["distances_mm"] = distances(row["labels"], touch=0.9)
    return row


def eleven_ribs(sid="0028"):
    return facts_row(sid, rib_entries=ribs(11, 11))


def asymmetric(sid="0029"):
    return facts_row(sid, rib_entries=ribs(11, 12))


def shifted(sid="0030"):
    """Every rib leads on the label one above its own, as 0245's mask does."""
    return facts_row(sid, rib_entries=ribs(offset=-1))


def split_piece(sid="0031"):
    row = facts_row(sid)
    row["labels"][str(T6)]["voxels"] = 4000
    return row


def fragment(sid="0032"):
    row = facts_row(sid)
    row["labels"][str(T1)].update(components=2, largest_share=0.6)
    return row


def c2_at_top(sid="0033"):
    """No C1, and C2's top in the field's top slice."""
    return facts_row(sid, NORMAL[1:], top=-10.0, top_slice_mm=-10.0)


def no_c2(sid="0034"):
    return facts_row(sid, NORMAL[2:], top=-60.0)


def l5_fragment(sid="0035"):
    """A sliver labelled L5 inside the overlap of an L4 that meets the sacrum."""
    row = facts_row(sid)
    labels = row["labels"]
    bottom = labels[str(L4)]["bottom_mm"]
    labels[str(L5)].update(voxels=2000, top_mm=bottom + 2.0, bottom_mm=bottom - 3.0)
    labels[str(SACRUM)].update(top_mm=bottom + 8.0, bottom_mm=bottom - 82.0)
    row["distances_mm"].update({f"{L5}-{SACRUM}": 0.5, f"{L4}-{SACRUM}": 1.0})
    return row


def missing_t1(sid="0036"):
    return facts_row(sid, tuple(n for n in NORMAL if n != T1))


def repaired_of(sid="0036"):
    row = normal(sid + "r")
    row["repaired_from"] = sid
    return row


CONTROLS = [f"{n:04d}" for n in range(1, 25)]
SITES = ("autoPET", "Leipzig", "Careggi")


def synthetic_facts():
    """24 normal controls across the three sites, then one study of each kind, and one repaired mask."""
    rows = [normal(sid, SITES[n % 3]) for n, sid in enumerate(CONTROLS)]
    rows += [l6_twelve(), l6_thirteen(), four_lumbar(), eleven_ribs(), asymmetric(), shifted(), split_piece(),
             fragment(), c2_at_top(), no_c2(), l5_fragment(), missing_t1(), repaired_of(), normal("0037")]
    return sorted(rows, key=lambda r: r["id"])


def synthetic_record(real):
    """The committed record's shape, naming the synthetic studies: 0036 repaired, 0037 a labelling
    error, and the note's table as the synthetic rows give it."""
    record = copy.deepcopy(real)
    source = "the synthetic facts of tests/test_gold3_ct.py"
    record.update(
        labelling_error=[{"id": "0037", "why": "a person read a skipped label", "source": source}],
        open=[], look=[], out_of_order_read_as_bend=[],
        repaired=[{"id": "0036", "voxels": "readers", "why": "no T1 label; renamed by the ribs", "source": source}],
        known_exceptions={"Q15": []}, controls={"ids": CONTROLS, "source": source})
    record["note_table"] = dict(real["note_table"], rows={"rib 12 on T12": [24, 1, 1], "rib 13 on L1": [0, 0, 1]},
                                studies=[24, 1, 2])
    return record


def bucket_for(rows):
    studies = {r["id"]: [CT_BYTES, MASK_BYTES, RIB_BYTES] for r in rows if "repaired_from" not in r}
    return {"about": "synthetic", "bucket": "s3://enhance-pet-1-6k", "columns": ["ct", "vertebrae", "ribs"],
            "studies": studies}


# The synthetic facts' 37 studies: 0034 has no C2, 0036 is repaired, the rest are whole.
TIERS_OF_SYNTHETIC = {"gold3": 35, "gold4": 1, "silver3": 1}
COPIED = (gold3.MEMBERS, gold3.VERSE, gold3.TOTALSEG, gold3.RECORD, gold3.RULE, gold3.TEST_PERSONS, gold3.HOLDOUT,
          gold3.LICENCES, gold3.TOOL)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def mini_repo(folder, facts=None):
    """A scratch repository holding copies of the committed records, and the synthetic facts if given."""
    folder = Path(folder)
    for rel in COPIED:
        (folder / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, folder / rel)
    if facts is not None:
        members = json.loads((ROOT / gold3.MEMBERS).read_text(encoding="utf-8"))
        members["members"][0].update(TIERS_OF_SYNTHETIC)
        write_json(folder / gold3.MEMBERS, members)
        write_json(folder / gold3.RECORD, synthetic_record(json.loads((ROOT / gold3.RECORD).read_text(encoding="utf-8"))))
        write_json(folder / gold3.BUCKET, bucket_for(facts))
        (folder / gold3.FACTS).write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in facts), encoding="utf-8")
        write_json(folder / gold3.FACTS_RECORD, {"tool": "synthetic", "rows": len(facts)})
    return folder


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = gold3.main([str(a) for a in argv])
    return code, out.getvalue(), err.getvalue()


class Scratch(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gold3-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def built(self, repo_or_inputs):
        inputs = repo_or_inputs if isinstance(repo_or_inputs, dict) else gold3.load_inputs(repo_or_inputs)
        db = gold3.memory_db(inputs)
        self.addCleanup(db.close)
        return db

    def opened(self, store):
        db = gold3.open_store(store)
        self.addCleanup(db.close)
        return db

# ---------------------------------------------------------------- the column, by the names


class Names(unittest.TestCase):
    def test_a_normal_column_is_strict_and_named_t12l5_with_24_bodies(self):
        row = normal()
        self.assertEqual(gold3.count_class(row), "strict")
        self.assertEqual(gold3.label_pattern(row), "C2 to L5 named")
        self.assertEqual(gold3.call_by_names(row), {"thoracic": 12, "lumbar": 5, "presacral": 24, "call": "T12L5"})
        self.assertEqual(gold3.whole_problems(row), [])

    def test_a_level_under_200_voxels_does_not_count(self):
        row, l3 = normal(), 22
        row["labels"][str(l3)]["voxels"] = gold3.LEVEL_MIN_VOXELS - 1
        self.assertNotIn(l3, gold3.present(row))
        self.assertEqual(gold3.missing_levels(row), [l3])

    def test_gaps_read_foot_edge_of_the_upper_to_head_edge_of_the_lower(self):
        row = normal()
        self.assertEqual(gold3.gap_mm(row, C2, 3), DISC_MM)
        self.assertEqual(gold3.gap_mm(row, L5, SACRUM), SACRUM_OVERLAP_MM)
        self.assertEqual(len(gold3.links(row)), len(NORMAL) - 2)

    def test_an_l6_column_is_strict_with_25_bodies(self):
        row = l6_twelve()
        self.assertEqual(gold3.count_class(row), "strict")
        self.assertEqual(gold3.label_pattern(row), "L6 named below an L5")
        self.assertEqual(gold3.call_by_names(row)["call"], "T12L6")
        self.assertEqual(gold3.call_by_names(row)["presacral"], 25)

    def test_four_lumbar_touching_the_sacrum_is_no_l5_with_23_bodies(self):
        row = four_lumbar()
        self.assertTrue(gold3.lumbar_tail_meets(row))
        self.assertEqual(gold3.count_class(row), "no_l5")
        self.assertEqual(gold3.label_pattern(row), "no L5, L4 meeting the sacrum")
        self.assertEqual(gold3.call_by_names(row)["presacral"], 23)

    def test_no_l5_with_l4_short_of_the_sacrum_is_a_lumbar_look(self):
        row = four_lumbar()
        row["labels"] = column(NO_L5, sacrum_gap=2.0)
        self.assertFalse(gold3.lumbar_tail_meets(row))
        self.assertEqual(gold3.count_class(row), "lumbar_look")
        self.assertEqual(gold3.label_pattern(row), "no L5")

    def test_no_l5_with_an_l6_is_named_so(self):
        row = facts_row("0050", (*range(C1, L4 + 1), L6, SACRUM))
        self.assertEqual(gold3.label_pattern(row), "no L5, an L6 in its place")

    def test_a_missing_upper_lumbar_label_keeps_the_spine_whole(self):
        row = facts_row("0051", tuple(n for n in NORMAL if n != 21))
        self.assertEqual(gold3.whole_problems(row), [])
        self.assertEqual(gold3.count_class(row), "lumbar_look")
        self.assertEqual(gold3.label_pattern(row), "lumbar label missing: L2")

    def test_no_c2_no_sacrum_and_a_skipped_thoracic_label_are_not_whole(self):
        self.assertEqual(gold3.count_class(no_c2()), "no_c2")
        self.assertEqual(gold3.whole_problems(no_c2()), ["no C2"])
        row = facts_row("0052", NORMAL[:-1])
        self.assertEqual(gold3.count_class(row), "no_sacrum")
        self.assertEqual(gold3.count_class(missing_t1()), "skipped_label")
        self.assertEqual(gold3.whole_problems(missing_t1()), ["T1 missing"])

    def test_a_wide_space_above_t12_holds_a_body_with_no_label(self):
        row = normal()
        for key in (str(n) for n in range(T6, SACRUM + 1) if str(n) in row["labels"]):
            row["labels"][key]["top_mm"] -= 30.0
            row["labels"][key]["bottom_mm"] -= 30.0
        self.assertEqual(gold3.count_class(row), "unlabelled_body")
        self.assertTrue(any("a space of" in p for p in gold3.whole_problems(row)))

    def test_c2_at_the_top_slice_counts_c1_as_cut_off(self):
        row = c2_at_top()
        self.assertNotIn(C1, gold3.present(row))
        self.assertEqual(gold3.call_by_names(row)["presacral"], 24)
        self.assertEqual(gold3.count_class(row), "strict")

    def test_an_l5_fragment_over_an_l4_meeting_the_sacrum(self):
        row = l5_fragment()
        self.assertTrue(gold3.l5_fragment(row))
        self.assertFalse(gold3.l5_fragment(normal()))
        self.assertEqual(gold3.label_pattern(row), "L5 label a fragment, L4 meeting the sacrum")

# ---------------------------------------------------------------- the column, by the ribs


class Ribs(unittest.TestCase):
    def test_each_rib_reads_against_its_own_body(self):
        self.assertEqual(gold3.reading_of(12, T12), "own")
        self.assertEqual(gold3.reading_of(12, T12 - 1), "one_high")
        self.assertEqual(gold3.reading_of(12, L1), "one_low")
        self.assertEqual(gold3.reading_of(12, T12 + 3), "further")
        self.assertEqual(gold3.reading_of(12, None), "nothing")
        self.assertEqual(gold3.own_vertebra(13), L1)

    def test_a_rib_under_50_voxels_does_not_count(self):
        row = normal()
        row["ribs"]["12"]["voxels"] = gold3.RIB_MIN_VOXELS - 1
        self.assertEqual(gold3.ribs_on(row, "left")[-1], 11)
        self.assertEqual(gold3.ribs_on(row, "right")[-1], 12)

    def test_a_normal_column_by_the_ribs(self):
        row = normal()
        self.assertEqual(gold3.lowest_rib_row(row), "rib 12 on T12")
        self.assertEqual(gold3.ladder(row), {"read": 24, "own": 24, "one_high": 0, "one_low": 0, "further": 0, "shift": None})
        self.assertEqual(gold3.call_by_ribs(row)["call"], "T12L5")
        self.assertEqual(gold3.call_by_ribs(row)["lowest_rib_bearing"], "T12")
        self.assertEqual(gold3.side_by_side(row)["rib_pairs"], 12)
        self.assertEqual(gold3.side_by_side(row)["lowest_rib_meets_left"], "T12")
        self.assertTrue(gold3.ribs_agree(row))

    def test_an_l6_with_twelve_ribs_has_six_lumbar_bodies_by_the_ribs(self):
        call = gold3.call_by_ribs(l6_twelve())
        self.assertEqual(call["call"], "T12L6")
        self.assertEqual(gold3.route_truth(call), "L6")

    def test_an_l6_with_thirteen_ribs_has_thirteen_thoracic_bodies_by_the_ribs(self):
        row = l6_thirteen()
        self.assertEqual(gold3.lowest_rib_row(row), "rib 13 on L1")
        call = gold3.call_by_ribs(row)
        self.assertEqual(call["call"], "T13L5")
        self.assertEqual(gold3.route_truth(call), "T13")

    def test_eleven_ribs_and_asymmetric_ribs(self):
        self.assertEqual(gold3.lowest_rib_row(eleven_ribs()), "rib 11 on T11")
        self.assertEqual(gold3.call_by_ribs(eleven_ribs())["call"], "T11L6")
        self.assertEqual(gold3.lowest_rib_row(asymmetric()), "rib 11 on T11 on one side, rib 12 on T12 on the other")
        self.assertEqual(gold3.side_by_side(asymmetric())["rib_pairs"], 11)

    def test_a_shifted_ladder_is_one_level_off_and_its_call_follows_the_shift(self):
        row = shifted()
        self.assertEqual(gold3.ladder(row)["shift"], "one_high")
        self.assertEqual(gold3.lowest_rib_row(row), gold3.ONE_OFF)
        self.assertEqual(gold3.call_by_ribs(row)["lowest_rib_bearing"], "T11")

    def test_a_tie_goes_with_the_lead_and_is_marked(self):
        row = normal()
        row["ribs"]["12"] = rib_entry(T12, tie=True)
        self.assertTrue(gold3.lowest_rib(row, "left")["tie"])
        self.assertFalse(gold3.ribs_agree(row))

    def test_no_contact_and_no_rib(self):
        row = normal()
        for side in ("left", "right"):
            row["ribs"][str(gold3.rib_label(side, 12))] = rib_entry(None)
        self.assertEqual(gold3.lowest_rib_row(row), gold3.NOTHING)
        row["ribs"] = {}
        self.assertEqual(gold3.lowest_rib_row(row), gold3.NO_RIB)
        self.assertIsNone(gold3.call_by_ribs(row))

    def test_masks_on_two_grids_are_unreadable_for_contacts(self):
        row = normal()
        row["ribs_mask"]["same_grid"] = False
        self.assertEqual(gold3.lowest_rib_row(row), gold3.UNREADABLE)
        self.assertEqual(gold3.rib_class(row)[0], "normal")

    def test_route_truth_follows_the_anomaly_routes_order(self):
        self.assertEqual(gold3.route_truth({"thoracic": 12, "lumbar": 5}), "normal")
        self.assertEqual(gold3.route_truth({"thoracic": 12, "lumbar": 4}), "four_lumbar")
        self.assertEqual(gold3.route_truth({"thoracic": 11, "lumbar": 5}), "eleven")
        self.assertEqual(gold3.route_truth({"thoracic": 13, "lumbar": 6}), "L6")
        self.assertEqual(gold3.route_truth({"thoracic": 11, "lumbar": 4}), "four_lumbar")
        self.assertEqual(gold3.route_truth({"thoracic": 10, "lumbar": 5}), "other")
        self.assertIsNone(gold3.route_truth(None))

# ---------------------------------------------------------------- the class and the status


class Classes(unittest.TestCase):
    def test_each_kind_of_column_gets_its_class(self):
        cases = {"normal": normal(), "l6_twelve_ribs": l6_twelve(), "l6_thirteen_ribs": l6_thirteen(),
                 "four_lumbar_twelve_ribs": four_lumbar(), "eleven_ribs": eleven_ribs(),
                 "asymmetric_ribs": asymmetric(), "look": shifted(), "not_whole": no_c2()}
        for klass, row in cases.items():
            with self.subTest(klass):
                self.assertEqual(gold3.classify(row)[0], klass)

    def test_thirteen_ribs_without_an_l6_is_its_own_class(self):
        row = normal()
        row["ribs"].update({"13": rib_entry(L1), "26": rib_entry(L1)})
        self.assertEqual(gold3.classify(row), ("thirteen_ribs", "rib 13 on L1, no L6: 24 bodies"))

    def test_a_name_pattern_the_ribs_do_not_explain_is_a_look(self):
        self.assertEqual(gold3.classify(l5_fragment())[0], "look")
        self.assertEqual(gold3.classify(facts_row("0051", tuple(n for n in NORMAL if n != 21)))[0], "look")

    def test_with_no_contact_the_rib_count_stands_in(self):
        row = eleven_ribs()
        for side in ("left", "right"):
            row["ribs"][str(gold3.rib_label(side, 11))] = rib_entry(None)
        self.assertEqual(gold3.classify(row)[0], "eleven_ribs")
        row = normal()
        row["ribs"] = {}
        self.assertEqual(gold3.classify(row)[0], "normal")

    def test_a_decision_comes_after_the_whole_rule_and_a_repair_before_it(self):
        self.assertEqual(gold3.classify(normal(), ("labelling_error", "read"))[0], "labelling_error")
        self.assertEqual(gold3.classify(no_c2(), ("labelling_error", "read"))[0], "not_whole")
        self.assertEqual(gold3.classify(no_c2(), ("repaired", "renamed"))[0], "repaired")

    def test_confirmed_by_masks_needs_both_calls_and_every_structural_check(self):
        passing = {check: "pass" for check in gold3.STRUCTURAL}
        self.assertEqual(gold3.status_of("normal", normal(), passing), "confirmed_by_masks")
        self.assertEqual(gold3.status_of("normal", normal(), dict(passing, Q11="look")), "candidate")
        self.assertEqual(gold3.status_of("normal", normal(), dict(passing, Q14="fail")), "candidate")
        self.assertEqual(gold3.status_of("normal", normal(), dict(passing, Q06="look")), "confirmed_by_masks")
        self.assertEqual(gold3.status_of("asymmetric_ribs", asymmetric(), passing), "candidate")
        self.assertEqual(gold3.status_of("look", shifted(), passing), "candidate")
        self.assertEqual(gold3.status_of("open", normal(), passing), "open")
        self.assertEqual(gold3.status_of("not_whole", no_c2(), passing), "not_assessed")

    def test_every_class_is_named_and_needs_ct_only_for_the_lumbosacral_ones(self):
        self.assertLessEqual(set(gold3.NEEDS_CT), set(gold3.CLASSES))
        self.assertNotIn("normal", gold3.NEEDS_CT)

# ---------------------------------------------------------------- the quality checks


def verdict_of(function, row, *extra):
    return function(row, *extra)["verdict"]


class Checks(unittest.TestCase):
    def test_a_normal_column_passes_every_check_that_runs(self):
        context = {"bounds": (0.7, 0.9), "facts_b": {}, "bucket": {"0001": [CT_BYTES, MASK_BYTES, RIB_BYTES]}}
        results = {r["check"]: r["verdict"] for r in gold3.run_qa(normal(), context)}
        self.assertEqual({k for k, v in results.items() if v != "pass"}, {"Q14"})
        self.assertEqual(results["Q14"], "not_run")

    def test_each_result_carries_its_id_version_and_why(self):
        context = {"bounds": None, "facts_b": {}, "bucket": {}}
        first = gold3.run_qa(normal(), context)[0]
        self.assertEqual((first["check"], first["version"]), ("Q01", 1))
        self.assertTrue(first["why"].startswith("the mask is readable"))

    def test_q01_header(self):
        row = normal()
        row["mask"]["dtype"] = "int16"
        self.assertEqual(verdict_of(gold3.check_header, row), "pass")
        row["mask"]["dtype"] = "float32"
        self.assertEqual(verdict_of(gold3.check_header, row), "fail")
        row = normal()
        row["mask"]["zooms"][2] = 5.0
        self.assertEqual(verdict_of(gold3.check_header, row), "fail")
        row = normal()
        row["ribs_mask"]["same_grid"] = False
        self.assertEqual(verdict_of(gold3.check_header, row), "fail")

    def test_q02_alphabet(self):
        row = normal()
        row["outside_scheme_voxels"]["ribs"] = 3
        self.assertEqual(verdict_of(gold3.check_alphabet, row), "fail")
        self.assertEqual(verdict_of(gold3.check_alphabet, normal()), "pass")

    def test_q03_whole_rule_excepts_an_absent_l5(self):
        self.assertEqual(verdict_of(gold3.check_whole, four_lumbar()), "pass")
        self.assertEqual(verdict_of(gold3.check_whole, no_c2()), "fail")
        self.assertEqual(verdict_of(gold3.check_whole, facts_row("0051", tuple(n for n in NORMAL if n != 21))), "look")

    def test_q04_order(self):
        self.assertEqual(verdict_of(gold3.check_order, normal()), "pass")
        self.assertEqual(gold3.check_order(l5_fragment())["value"], [["L5", "sacrum"]])

    def test_q05_gaps(self):
        row = normal()
        for key in (str(n) for n in range(L1, SACRUM + 1) if str(n) in row["labels"]):
            row["labels"][key]["top_mm"] -= 12.0
            row["labels"][key]["bottom_mm"] -= 12.0
        self.assertEqual(verdict_of(gold3.check_gaps, row), "look")
        row = normal()
        for key in (str(n) for n in range(T6, SACRUM + 1) if str(n) in row["labels"]):
            row["labels"][key]["top_mm"] -= 30.0
            row["labels"][key]["bottom_mm"] -= 30.0
        self.assertEqual(verdict_of(gold3.check_gaps, row), "fail")
        self.assertEqual(verdict_of(gold3.check_gaps, normal()), "pass")

    def test_q06_c2_at_the_top_slice_is_a_look(self):
        self.assertEqual(verdict_of(gold3.check_c2_top, c2_at_top()), "look")
        self.assertEqual(verdict_of(gold3.check_c2_top, normal()), "pass")
        self.assertEqual(verdict_of(gold3.check_c2_top, no_c2()), "not_run")

    def test_q07_l5_fragment(self):
        self.assertEqual(verdict_of(gold3.check_l5_fragment, l5_fragment()), "look")
        self.assertEqual(verdict_of(gold3.check_l5_fragment, normal()), "pass")
        self.assertEqual(verdict_of(gold3.check_l5_fragment, four_lumbar()), "not_run")

    def test_q08_lowest_lumbar_touches_the_sacrum(self):
        self.assertEqual(verdict_of(gold3.check_lumbosacral_touch, four_lumbar()), "pass")
        self.assertEqual(verdict_of(gold3.check_lumbosacral_touch, normal()), "pass")
        row = four_lumbar()
        row["distances_mm"][f"{L4}-{SACRUM}"] = 4.0
        self.assertEqual(verdict_of(gold3.check_lumbosacral_touch, row), "look")
        self.assertEqual(verdict_of(gold3.check_lumbosacral_touch, l5_fragment()), "look")

    def test_q09_ladder(self):
        self.assertEqual(verdict_of(gold3.check_ladder, shifted()), "fail")
        row = normal()
        row["ribs"]["3"] = rib_entry(9)
        self.assertEqual(verdict_of(gold3.check_ladder, row), "look")
        self.assertEqual(verdict_of(gold3.check_ladder, normal()), "pass")

    def test_q10_lowest_rib(self):
        self.assertEqual(verdict_of(gold3.check_lowest_rib, shifted()), "fail")
        self.assertEqual(verdict_of(gold3.check_lowest_rib, asymmetric()), "pass")
        row = normal()
        row["ribs"]["25"] = rib_entry(T12, tie=True)
        self.assertEqual(verdict_of(gold3.check_lowest_rib, row), "look")

    def test_q11_split_piece_and_q12_fragments(self):
        found = gold3.check_split_piece(split_piece())
        self.assertEqual((found["verdict"], found["value"][0]["label"]), ("look", "T6"))
        self.assertEqual(verdict_of(gold3.check_split_piece, normal()), "pass")
        self.assertEqual(gold3.check_fragments(fragment())["value"], {"T1": 0.6})
        self.assertEqual(verdict_of(gold3.check_fragments, normal()), "pass")

    def test_q13_c7_against_t1(self):
        self.assertEqual(verdict_of(gold3.check_c7_t1, normal(), (0.7, 0.9)), "pass")
        self.assertEqual(verdict_of(gold3.check_c7_t1, normal(), (0.85, 0.9)), "look")
        self.assertEqual(verdict_of(gold3.check_c7_t1, normal(), None), "not_run")

    def test_q13_bounds_need_twenty_controls(self):
        rows = [normal(f"{n:04d}") for n in range(1, 21)]
        self.assertEqual(gold3.ratio_bounds(rows, [r["id"] for r in rows]), (0.8, 0.8))
        self.assertIsNone(gold3.ratio_bounds(rows[:19], [r["id"] for r in rows]))

    def test_q14_two_readings(self):
        other = normal()
        self.assertEqual(verdict_of(gold3.check_two_implementations, normal(), other), "pass")
        other["distances_mm"][f"{L5}-{SACRUM}"] = 0.9
        other["ribs"]["12"]["lead"] = T12 - 1
        found = gold3.check_two_implementations(normal(), other)
        self.assertEqual((found["verdict"], len(found["value"])), ("fail", 2))
        self.assertEqual(verdict_of(gold3.check_two_implementations, normal(), None), "not_run")

    def test_q15_slice_spacing(self):
        row = normal()
        row["scanner"]["slice_thickness"] = "0.98"
        self.assertEqual(verdict_of(gold3.check_slice_spacing, row), "look")
        row["scanner"]["slice_thickness"] = "3.0 mm"
        self.assertEqual(verdict_of(gold3.check_slice_spacing, row), "pass")
        row["scanner"]["slice_thickness"] = None
        self.assertEqual(verdict_of(gold3.check_slice_spacing, row), "not_run")

    def test_q16_bucket_bytes_and_a_repaired_mask(self):
        self.assertEqual(verdict_of(gold3.check_bucket_bytes, normal(), [CT_BYTES, MASK_BYTES, RIB_BYTES]), "pass")
        self.assertEqual(verdict_of(gold3.check_bucket_bytes, normal(), [CT_BYTES, MASK_BYTES + 1, RIB_BYTES]), "fail")
        self.assertEqual(verdict_of(gold3.check_bucket_bytes, repaired_of(), [CT_BYTES, MASK_BYTES + 1, RIB_BYTES]), "pass")
        self.assertEqual(verdict_of(gold3.check_bucket_bytes, normal(), None), "not_run")

    def test_every_check_says_what_it_holds_and_the_constants_it_reads(self):
        self.assertEqual(set(gold3.CHECK_THRESHOLDS), {check_id for check_id, _, _, _ in gold3.CHECKS})
        for check_id, _, _, function in gold3.CHECKS:
            with self.subTest(check_id):
                self.assertTrue(function.__doc__.startswith(f"{check_id}: "))
                self.assertNotIn("\n", gold3.check_text(function))
                self.assertTrue(gold3.thresholds_text(check_id))
        self.assertEqual(gold3.thresholds_text("Q05"), "UNLABELLED_GAP_MM = 20.0; LOOK_GAP_MM = 10.0")

# ---------------------------------------------------------------- the facts' schema


class Schema(unittest.TestCase):
    def test_a_synthetic_row_follows_the_schema(self):
        for row in synthetic_facts():
            with self.subTest(row["id"]):
                self.assertEqual(gold3.row_problems(row), [])

    def test_an_unknown_key_a_bad_id_and_a_bad_distance_are_refused(self):
        row = normal()
        row["extra"] = 1
        self.assertIn("row has an unknown key extra", gold3.row_problems(row))
        row = normal("12345")
        self.assertTrue(gold3.row_problems(row))
        row = normal()
        row["distances_mm"]["28-24"] = 1.0
        self.assertTrue(gold3.row_problems(row))

    def test_contacts_are_null_only_with_no_lead(self):
        row = normal()
        row["ribs"]["12"].update(contacts=None, lead=None, lead_n=0)
        self.assertEqual(gold3.row_problems(row), [])
        row["ribs"]["12"]["lead"] = T12
        self.assertTrue(gold3.row_problems(row))

    def test_the_facts_cover_the_bucket_and_the_record_in_order(self):
        rows = synthetic_facts()
        record = synthetic_record(json.loads((ROOT / gold3.RECORD).read_text(encoding="utf-8")))
        self.assertEqual(gold3.facts_problems(rows, record, bucket_for(rows)), [])
        self.assertTrue(gold3.facts_problems(list(reversed(rows)), record, bucket_for(rows)))
        self.assertTrue(gold3.facts_problems([r for r in rows if r["id"] != "0036r"], record, bucket_for(rows)))
        self.assertTrue(gold3.facts_problems(rows[1:], record, bucket_for(rows)))

    def test_the_facts_and_their_record_come_together(self):
        self.assertEqual(gold3.facts_record_problems(None, None), [])
        self.assertTrue(gold3.facts_record_problems([normal()], None))
        self.assertTrue(gold3.facts_record_problems([normal()], {"rows": 2}))
        self.assertEqual(gold3.facts_record_problems([normal()], {"row_count": 1}), [])

# ---------------------------------------------------------------- the split and the intervals


def catalog_functions():
    """tools/catalog.py's person_hash and schwingnet.catalog's part_of, compiled from their own source
    with the decorators left off: the modules import pydantic and beartype, which the plain interpreter
    the check runs on lacks, while the functions themselves are the standard library."""
    namespace = {"hashlib": hashlib, "sha256": hashlib.sha256, "StrEnum": StrEnum}
    wanted = {ROOT / "tools" / "catalog.py": {"person_hash"},
              ROOT / "src" / "schwingnet" / "catalog.py": {"Part", "HASH_SPACE", "hash_part", "part_of"}}
    for path, names in wanted.items():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        nodes = []
        for node in tree.body:
            named = getattr(node, "name", None) or next((t.id for t in getattr(node, "targets", []) if isinstance(t, ast.Name)), None)
            if named in names:
                if hasattr(node, "decorator_list"):
                    node.decorator_list = []
                if isinstance(node, ast.FunctionDef):
                    node.returns = None
                    for argument in node.args.args:
                        argument.annotation = None
                nodes.append(node)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


class Split(unittest.TestCase):
    def setUp(self):
        self.rule = json.loads((ROOT / gold3.RULE).read_text(encoding="utf-8"))
        self.test = frozenset(p["person"] for p in json.loads((ROOT / gold3.TEST_PERSONS).read_text(encoding="utf-8")))

    def test_the_part_is_tools_catalogs_for_the_same_person(self):
        catalog = catalog_functions()
        persons = [f"enhance_pet:{n:04d}" for n in range(1, 300)] + ["verse:verse547", "verse:verse108", *sorted(self.test)[:3]]
        for person in persons:
            with self.subTest(person):
                digest = catalog["person_hash"](self.rule["salt"], person)
                self.assertEqual(gold3.person_hash(self.rule["salt"], person), digest)
                theirs = catalog["part_of"](person, digest, self.rule["validation_share"], self.test)
                self.assertEqual(gold3.part_of(person, self.rule, self.test), theirs.value)

    def test_known_values_of_the_hash(self):
        text = f"schwingnet-split|{self.rule['salt']}|enhance_pet:0001".encode()
        self.assertEqual(gold3.person_hash(self.rule["salt"], "enhance_pet:0001"),
                         int(hashlib.sha256(text).hexdigest()[:16], 16))
        self.assertEqual(gold3.part_of("x", {"salt": "s", "validation_share": 0.0}, frozenset()), "train")
        self.assertEqual(gold3.part_of("x", {"salt": "s", "validation_share": 1.0}, frozenset()), "validation")
        self.assertEqual(gold3.part_of("x", {"salt": "s", "validation_share": 1.0}, frozenset({"x"})), "test")


class Intervals(unittest.TestCase):
    def test_wilson_against_known_values(self):
        for hits, total, low, high in ((5, 10, 0.2366, 0.7634), (0, 10, 0.0, 0.2775), (10, 10, 0.7225, 1.0),
                                       (39, 1557, 0.0184, 0.0341), (1, 100, 0.0018, 0.0545)):
            with self.subTest(f"{hits}/{total}"):
                found = gold3.wilson(hits, total)
                self.assertAlmostEqual(found[0], low, places=4)
                self.assertAlmostEqual(found[1], high, places=4)

    def test_an_empty_total_says_nothing(self):
        self.assertEqual(gold3.wilson(0, 0), (0.0, 1.0))
        self.assertEqual(gold3.interval_text(0, 0), "0")
        self.assertEqual(gold3.interval_text(5, 10), "5 (50.0 %, 23.7 to 76.3)")

    def test_autopet_persons_count_each_repeat_once(self):
        self.assertEqual(gold3.autopet_persons(979, 1014), (865, 900))
        self.assertEqual(gold3.autopet_persons(10, 10), (10, 10))

# ---------------------------------------------------------------- the dataset built from the files


class Dataset(Scratch):
    def test_the_committed_files_build_with_no_facts(self):
        repo = mini_repo(self.tmp / "repo")
        db = self.built(repo)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM item").fetchone()[0], 17)
        counts = {r["member"]: (r["gold3"], r["persons_low"], r["persons_high"])
                  for r in db.execute("SELECT * FROM member_count WHERE site = 'all'")}
        self.assertEqual(counts, {"enhance_pet": (0, 865, 1478), "verse": (17, 17, 17), "totalsegmentator": (0, 142, 156)})

    def test_the_synthetic_facts_give_their_classes_tiers_and_statuses(self):
        repo = mini_repo(self.tmp / "repo", synthetic_facts())
        db = self.built(repo)
        found = {r[0]: r[1:] for r in db.execute(
            "SELECT item.native_id, anomaly.class, anomaly.status, item.tier FROM item JOIN anomaly USING (item)"
            " WHERE item.member = 'enhance_pet'")}
        self.assertEqual(found["0001"], ("normal", "confirmed_by_masks", "gold3"))
        self.assertEqual(found["0025"], ("l6_twelve_ribs", "confirmed_by_masks", "gold3"))
        self.assertEqual(found["0026"], ("l6_thirteen_ribs", "confirmed_by_masks", "gold3"))
        self.assertEqual(found["0027"], ("four_lumbar_twelve_ribs", "confirmed_by_masks", "gold3"))
        self.assertEqual(found["0028"], ("eleven_ribs", "confirmed_by_masks", "gold3"))
        self.assertEqual(found["0029"], ("asymmetric_ribs", "candidate", "gold3"))
        self.assertEqual(found["0030"], ("look", "candidate", "gold3"))
        self.assertEqual(found["0031"], ("normal", "candidate", "gold3"))
        self.assertEqual(found["0032"], ("normal", "candidate", "gold3"))
        self.assertEqual(found["0033"], ("normal", "confirmed_by_masks", "gold3"))
        self.assertEqual(found["0034"], ("not_whole", "not_assessed", "silver3"))
        self.assertEqual(found["0035"], ("look", "candidate", "gold3"))
        self.assertEqual(found["0036"], ("repaired", "candidate", "gold4"))
        self.assertEqual(found["0037"], ("labelling_error", "labelling_error", "gold3"))
        needs_ct = dict(db.execute("SELECT item.native_id, anomaly.needs_ct FROM anomaly JOIN item USING (item)"))
        self.assertEqual((needs_ct["0001"], needs_ct["0025"], needs_ct["0027"], needs_ct["verse108"]), (0, 1, 1, 1))

    def test_a_repaired_study_keeps_both_rows_and_its_checks(self):
        repo = mini_repo(self.tmp / "repo", synthetic_facts())
        db = self.built(repo)
        rows = {r[0] for r in db.execute("SELECT DISTINCT facts_row FROM qa_check WHERE item = 'enhance_pet:0036'")}
        self.assertEqual(rows, {"0036", "0036r"})
        kinds = [r[0] for r in db.execute("SELECT kind FROM mask WHERE item = 'enhance_pet:0036' ORDER BY kind")]
        self.assertEqual(kinds, ["ribs", "vertebrae", "vertebrae_repaired"])

    def test_the_note_table_is_made_again_from_the_rows(self):
        repo = mini_repo(self.tmp / "repo", synthetic_facts())
        inputs = gold3.load_inputs(repo)
        found = gold3.note_table(self.built(inputs), inputs["record"])
        self.assertTrue(found["matches"], found)
        inputs["record"]["note_table"]["rows"]["rib 12 on T12"] = [23, 1, 1]
        self.assertFalse(gold3.note_table(self.built(inputs), inputs["record"])["matches"])

    def test_the_sites_give_persons_as_a_range(self):
        repo = mini_repo(self.tmp / "repo", synthetic_facts())
        db = self.built(repo)
        rows = {r["site"]: (r["gold3"], r["persons_low"], r["persons_high"])
                for r in db.execute("SELECT * FROM member_count WHERE member = 'enhance_pet'")}
        autopet = rows["autoPET"]
        self.assertEqual(autopet[1:], (autopet[0], autopet[0]))
        self.assertEqual(rows["Leipzig"][1], None)
        self.assertEqual(rows["all"][2], rows["all"][0])

    def test_the_distance_bins_hold_every_whole_study_that_carries_the_distance(self):
        repo = mini_repo(self.tmp / "repo", synthetic_facts())
        bins, median, n = gold3.distance_bins(self.built(repo))
        self.assertEqual(sum(count for _, count in bins), n)
        self.assertEqual(dict(bins)["touching, 1.5 mm or less"], 2)
        self.assertEqual(median, 15.6)

    def test_both_labels_of_a_pair_out_of_order_are_flagged(self):
        flagged = {r["level"] for r in gold3.label_rows("enhance_pet:0035", l5_fragment()) if r["out_of_order"]}
        self.assertEqual(flagged, {"L5", "sacrum"})

    def test_the_views_answer(self):
        repo = mini_repo(self.tmp / "repo", synthetic_facts())
        db = self.built(repo)
        persons = {r["member"]: r["person_keys"] for r in db.execute("SELECT * FROM gold3_persons_by_member")}
        self.assertEqual(persons["verse"], 17)
        self.assertTrue(db.execute("SELECT COUNT(*) FROM qa_failures WHERE check_id = 'Q06'").fetchone()[0])
        self.assertTrue(db.execute("SELECT COUNT(*) FROM anomalies_by_class_and_status").fetchone()[0])

# ---------------------------------------------------------------- the store


class Store(Scratch):
    def setUp(self):
        super().setUp()
        self.repo = mini_repo(self.tmp / "repo", synthetic_facts())
        self.store = self.tmp / "store"

    def tables(self):
        return gold3.assemble(gold3.load_inputs(self.repo))

    def test_the_same_input_makes_no_new_version(self):
        first, new = gold3.build(self.store, self.tables(), "aaaa")
        self.assertTrue(new)
        again, new = gold3.build(self.store, self.tables(), "bbbb")
        self.assertFalse(new)
        self.assertEqual(again["file"], first["file"])
        self.assertEqual(len(list((self.store / gold3.VERSIONS_DIR).glob("*.sqlite"))), 1)
        self.assertFalse(list((self.store / gold3.VERSIONS_DIR).glob(".building-*")))

    def test_a_changed_input_makes_a_new_version_on_the_last(self):
        first, _ = gold3.build(self.store, self.tables())
        verse = json.loads((self.repo / gold3.VERSE).read_text(encoding="utf-8"))
        verse["series"][0]["claims"][0]["says"] = "a read recorded since"
        write_json(self.repo / gold3.VERSE, verse)
        second, new = gold3.build(self.store, self.tables())
        self.assertTrue(new)
        self.assertEqual((second["version"], second["parent"]), (2, first["sha256"]))
        self.assertEqual((self.store / gold3.CURRENT).read_text(encoding="utf-8").strip(), second["file"])
        self.assertEqual([r["version"] for r in gold3.read_versions(self.store)], [1, 2])

    def test_version_files_are_sealed_read_only(self):
        record, _ = gold3.build(self.store, self.tables())
        path = self.store / gold3.VERSIONS_DIR / record["file"]
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o444)
        self.assertRegex(record["file"], gold3.VERSION_FILE)
        db = self.opened(self.store)
        self.assertEqual(db.execute("PRAGMA application_id").fetchone()[0], gold3.APPLICATION_ID)
        with self.assertRaises(sqlite3.OperationalError):
            db.execute("DELETE FROM item")

    def test_a_changed_version_file_is_refused(self):
        record, _ = gold3.build(self.store, self.tables())
        path = self.store / gold3.VERSIONS_DIR / record["file"]
        path.chmod(0o644)
        with path.open("ab") as handle:
            handle.write(b"\0")
        with self.assertRaises(gold3.Gold3Error):
            self.opened(self.store)

    def test_the_store_lives_outside_the_repository(self):
        with self.assertRaises(gold3.Gold3Error):
            gold3.store_root(str(self.repo / "store"), self.repo)
        self.assertEqual(gold3.store_root(str(self.store), self.repo), self.store.resolve())

    def test_build_and_query_from_the_command_line(self):
        code, out, _ = run("--repo", self.repo, "build", "--root", self.store)
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out)["new"])
        code, out, _ = run("--repo", self.repo, "query", "SELECT member, COUNT(*) AS n FROM item GROUP BY member",
                           "--root", self.store, "--json")
        self.assertEqual(code, 0)
        self.assertIn({"member": "verse", "n": 17}, [json.loads(line) for line in out.splitlines()])
        code, _, err = run("--repo", self.repo, "query", "DELETE FROM item", "--root", self.store)
        self.assertEqual(code, 1)
        self.assertIn("gold3_ct:", err)

    def test_a_dropped_item_takes_its_rows_with_it_and_leaves_the_others(self):
        db = self.built(self.repo)
        tables = ("mask", "label", "rib", "anomaly", "qa_check")
        db.execute("DELETE FROM item WHERE item = 'enhance_pet:0001'")
        for table in tables:
            with self.subTest(table):
                self.assertEqual(db.execute(f"SELECT COUNT(*) FROM {table} WHERE item = 'enhance_pet:0001'").fetchone()[0], 0)
                self.assertTrue(db.execute(f"SELECT COUNT(*) FROM {table} WHERE item = 'enhance_pet:0002'").fetchone()[0])

    def test_a_licence_cut_that_refuses_every_source_carries_none_of_their_rows(self):
        licences = load_tool("licences")
        record, _ = gold3.build(self.store, self.tables())
        out = self.tmp / "cut.sqlite"
        kept, dropped = licences.derive(self.store / gold3.VERSIONS_DIR / record["file"], "commercial", out)
        self.assertEqual((kept, sorted(dropped)), ([], ["scidb_enhance_pet_1_6k", "totalsegmentator", "verse"]))
        with contextlib.closing(sqlite3.connect(out)) as db:
            for table in gold3.TABLE_ORDER:
                if table != "build":
                    with self.subTest(table):
                        self.assertEqual(db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0], 0)

# ---------------------------------------------------------------- the manifest, the pages and the check


class Manifest(Scratch):
    def test_export_flags_holdout_and_fold_persons(self):
        repo = mini_repo(self.tmp / "repo", synthetic_facts())
        rows = {r["item"]: r for r in gold3.export_rows(self.built(repo))}
        self.assertEqual((rows["verse:verse547"]["holdout"], rows["verse:verse547"]["training_allowed"]), (1, 0))
        self.assertEqual(rows["verse:verse581"]["anomaly_role"], "fold3")
        self.assertEqual((rows["verse:verse108"]["holdout"], rows["verse:verse108"]["training_allowed"]), (0, 1))
        self.assertEqual(rows["enhance_pet:0001"]["vertebrae_url"],
                         "s3://enhance-pet-1-6k/imaging-data/ground-truth/Vertebrae/0001.nii.gz")
        self.assertTrue(rows["verse:verse108"]["ct_location"].endswith("*verse108*.nii.gz"))
        self.assertTrue(all(r["part"] in ("train", "validation", "test") for r in rows.values()))

    def test_export_keeps_to_a_tier_and_to_training(self):
        repo = mini_repo(self.tmp / "repo", synthetic_facts())
        db = self.built(repo)
        self.assertEqual({r["tier"] for r in gold3.export_rows(db, "silver3")}, {"silver3"})
        training = gold3.export_rows(db, training_only=True)
        self.assertTrue(training and all(r["training_allowed"] == 1 and r["holdout"] == 0 for r in training))
        code, out, _ = run("--repo", repo, "export", "--format", "csv", "--tier", "gold4")
        self.assertEqual(code, 0)
        self.assertEqual(len(out.splitlines()), 2)


class Pages(Scratch):
    def write_pages(self, repo):
        for command in ("stats", "qa", "page"):
            code, _, err = run("--repo", repo, command)
            self.assertEqual(code, 0, err)

    def test_check_passes_with_a_note_while_the_facts_are_absent(self):
        repo = mini_repo(self.tmp / "repo")
        self.write_pages(repo)
        code, out, err = run("--repo", repo, "check")
        self.assertEqual(code, 0, err)
        self.assertIn("note: the ENHANCE.PET facts are not yet committed", out)

    def test_check_fails_on_a_stale_stats_page(self):
        repo = mini_repo(self.tmp / "repo")
        self.write_pages(repo)
        path = repo / gold3.STATS_PAGE
        path.write_text(path.read_text(encoding="utf-8") + "edited by hand\n", encoding="utf-8")
        code, _, err = run("--repo", repo, "check")
        self.assertEqual(code, 1)
        self.assertIn(f"{gold3.STATS_PAGE}: not what the committed files give", err)

    def test_a_licence_change_that_moves_no_row_leaves_the_pages_current(self):
        repo = mini_repo(self.tmp / "repo")
        self.write_pages(repo)
        licences = json.loads((repo / gold3.LICENCES).read_text(encoding="utf-8"))
        licences["sources"]["another_thread_source"] = {"licence": "CC BY 4.0", "class": "open"}
        write_json(repo / gold3.LICENCES, licences)
        code, _, err = run("--repo", repo, "check")
        self.assertEqual(code, 0, err)

    def test_a_split_change_that_moves_rows_makes_the_pages_stale(self):
        repo = mini_repo(self.tmp / "repo")
        self.write_pages(repo)
        rule = json.loads((repo / gold3.RULE).read_text(encoding="utf-8"))
        rule["validation_share"] = 1.0
        write_json(repo / gold3.RULE, rule)
        code, _, err = run("--repo", repo, "check")
        self.assertEqual(code, 1)
        self.assertIn(f"{gold3.PAGE_DATA}: not what the committed files give", err)

    def test_check_fails_on_a_missing_page(self):
        repo = mini_repo(self.tmp / "repo")
        self.write_pages(repo)
        (repo / gold3.QA_PAGE).unlink()
        self.assertEqual(run("--repo", repo, "check")[0], 1)

    def test_with_the_facts_the_pages_carry_the_classes_and_the_check_passes(self):
        repo = mini_repo(self.tmp / "repo", synthetic_facts())
        self.write_pages(repo)
        code, _, err = run("--repo", repo, "check")
        self.assertEqual(code, 0, err)
        stats = (repo / gold3.STATS_PAGE).read_text(encoding="utf-8")
        self.assertIn("The rows give the note's numbers exactly.", stats)
        self.assertIn("| l6_thirteen_ribs |", stats)
        qa = (repo / gold3.QA_PAGE).read_text(encoding="utf-8")
        self.assertIn("- Q06 look (1): 0033", qa)
        data = json.loads((repo / gold3.PAGE_DATA).read_text(encoding="utf-8"))
        self.assertTrue(data["facts_committed"])
        self.assertEqual(data["studies"]["columns"], list(gold3.PAGE_COLUMNS))
        self.assertEqual(len(data["studies"]["rows"]), 17 + 37)

    def test_check_fails_when_the_classes_miss_the_notes_table(self):
        repo = mini_repo(self.tmp / "repo", synthetic_facts())
        record = json.loads((repo / gold3.RECORD).read_text(encoding="utf-8"))
        record["note_table"]["studies"] = [24, 2, 2]
        write_json(repo / gold3.RECORD, record)
        self.write_pages(repo)
        code, _, err = run("--repo", repo, "check")
        self.assertEqual(code, 1)
        self.assertIn("do not give the note's table", err)

    def test_check_fails_when_the_tiers_miss_the_records_counts(self):
        repo = mini_repo(self.tmp / "repo", synthetic_facts())
        members = json.loads((repo / gold3.MEMBERS).read_text(encoding="utf-8"))
        members["members"][0]["gold3"] = 36
        write_json(repo / gold3.MEMBERS, members)
        self.write_pages(repo)
        code, _, err = run("--repo", repo, "check")
        self.assertEqual(code, 1)
        self.assertIn("enhance_pet: the rows give gold 3, gold 4 and silver 3 [35, 1, 1]", err)

    def test_check_fails_on_a_row_that_breaks_the_schema(self):
        facts = synthetic_facts()
        del facts[0]["sternum_voxels"]
        repo = mini_repo(self.tmp / "repo", facts)
        code, _, err = run("--repo", repo, "check")
        self.assertEqual(code, 1)
        self.assertIn("0001: row lacks sternum_voxels", err)

    def test_the_pages_are_ascii(self):
        repo = mini_repo(self.tmp / "repo", synthetic_facts())
        for text in gold3.written(repo).values():
            text.encode("ascii")

# ---------------------------------------------------------------- the correctness review's cases


class SilentLowestRibs(unittest.TestCase):
    """Four whole no-L5 spines of the release (0702, 0926, 1145, 1534) have twelve ribs a side whose
    twelfth reaches no label within 3 mm: their rib call must not read T11 from rib 11."""

    def test_a_lower_rib_that_meets_no_label_leaves_the_rib_call_unread(self):
        row = normal()
        for side in ("left", "right"):
            row["ribs"][str(gold3.rib_label(side, 12))] = rib_entry(None)
        self.assertIsNone(gold3.call_by_ribs(row))
        anomaly = gold3.anomaly_row("enhance_pet:0001", "enhance_pet", row, "normal", "why", {}, None)
        self.assertEqual((anomaly["route_truth"], anomaly["evidence"]), ("normal", "release names alone"))
        row = four_lumbar()
        for side in ("left", "right"):
            row["ribs"][str(gold3.rib_label(side, 12))] = rib_entry(None)
        self.assertEqual(gold3.classify(row)[0], "four_lumbar_twelve_ribs")
        self.assertEqual(gold3.route_truth(gold3.call_by_ribs(row) or gold3.call_by_names(row)), "four_lumbar")

    def test_one_side_read_still_places_the_lowest_rib_bearing_body(self):
        row = normal()
        row["ribs"][str(gold3.rib_label("left", 12))] = rib_entry(None)
        self.assertEqual(gold3.call_by_ribs(row)["call"], "T12L5")


class WilsonEnds(unittest.TestCase):
    def test_the_interval_holds_its_point_at_none_and_at_all(self):
        for total in (1, 5, 39, 100, 1557):
            with self.subTest(total):
                self.assertEqual(gold3.wilson(0, total)[0], 0.0)
                self.assertEqual(gold3.wilson(total, total)[1], 1.0)


class LeadFollowsItsTally(unittest.TestCase):
    def test_a_lead_or_tie_its_contacts_do_not_give_is_refused(self):
        row = normal()
        row["ribs"]["12"] = dict(rib_entry(T12), contacts={"18": 40, "19": 9}, lead_n=9)
        self.assertIn("rib 12: lead, tie or lead_n is not what its contacts give", gold3.row_problems(row))
        row["ribs"]["12"] = dict(rib_entry(T12), contacts={"18": 9, "19": 9}, lead_n=9, tie=False)
        self.assertIn("rib 12: lead, tie or lead_n is not what its contacts give", gold3.row_problems(row))
        row["ribs"]["12"] = dict(rib_entry(18), contacts={"18": 9, "19": 9}, lead_n=9, tie=True)
        self.assertEqual(gold3.row_problems(row), [])
        row["ribs"]["12"] = dict(rib_entry(None), contacts=None)
        self.assertEqual(gold3.row_problems(row), [])


class VerseReads(Scratch):
    def test_no_series_is_reader_confirmed_until_a_bench_verdict_is_recorded(self):
        db = self.built(mini_repo(self.tmp / "repo"))
        rows = {r["item"]: (r["status"], r["evidence"]) for r in db.execute("SELECT * FROM anomaly WHERE member = 'verse'")}
        self.assertNotIn("reader_confirmed", {status for status, _ in rows.values()})
        self.assertEqual(rows["verse:verse547"], ("candidate", "read"))
        self.assertEqual(rows["verse:verse108"], ("not_assessed", "none"))


class TakeFacts(Scratch):
    """take-facts joins a reading of the published masks to the repaired rows read elsewhere, as a grid
    run of the handoff does, and only compares where facts are committed already."""
    COMMIT = "0123456789abcdef0123456789abcdef01234567"

    def setUp(self):
        super().setUp()
        rows = synthetic_facts()
        self.repo = mini_repo(self.tmp / "repo", rows)
        (self.repo / gold3.FACTS).unlink()
        (self.repo / gold3.FACTS_RECORD).unlink()
        for rel in (gold3.MASK_SUMS, gold3.CT_DETAILS):
            (self.repo / rel).write_text(f"{rel}\n", encoding="utf-8")
        self.published = [r for r in rows if "repaired_from" not in r]
        self.repaired = [r for r in rows if "repaired_from" in r]
        self.second = [{"id": r["id"], "ribs": r["ribs"], "distances_mm": r["distances_mm"]} for r in self.published]

    def reading(self, name, rows):
        path = self.tmp / name
        path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        return path

    def take(self, first=None, second=None):
        first = self.reading("a.jsonl", self.published if first is None else first)
        second = self.reading("b.jsonl", self.second if second is None else second)
        return run("--repo", self.repo, "take-facts", first, second, "--read-on", "the grid, job 1",
                   "--bordercall-commit", self.COMMIT, "--date", "2026-10-28")

    def side_file(self, rows):
        (self.repo / gold3.FACTS_REPAIRED).write_text("".join(gold3.row_line(r) for r in rows), encoding="utf-8")

    def test_a_grid_reading_takes_the_repaired_rows_from_the_side_file(self):
        self.side_file(self.repaired)
        code, out, err = self.take()
        self.assertEqual(code, 0, err)
        inputs = gold3.load_inputs(self.repo)
        self.assertEqual([r["id"] for r in inputs["facts"]], sorted(r["id"] for r in self.published + self.repaired))
        self.assertEqual(gold3.facts_problems(inputs["facts"], inputs["record"], inputs["bucket"]), [])
        self.assertEqual(gold3.facts_record_problems(inputs["facts"], inputs["facts_record"]), [])
        self.assertEqual(inputs["facts_record"]["read_on"], "the grid, job 1")
        self.assertEqual(inputs["facts_record"]["bordercall_commit"], self.COMMIT)
        self.assertEqual(len(inputs["facts_b"]), len(self.published))
        self.assertFalse((self.repo / gold3.FACTS_REPAIRED).exists())
        self.assertIn(f"removed {gold3.FACTS_REPAIRED}", out)

    def test_a_reading_that_holds_the_repaired_rows_needs_no_side_file(self):
        code, _, err = self.take(first=self.published + self.repaired)
        self.assertEqual(code, 0, err)
        self.assertEqual(len(gold3.load_inputs(self.repo)["facts"]), len(self.published) + len(self.repaired))

    def test_with_facts_committed_a_reading_that_reproduces_them_is_recorded_and_no_row_moves(self):
        self.side_file(self.repaired)
        self.assertEqual(self.take()[0], 0)
        before = (self.repo / gold3.FACTS).read_bytes()
        code, out, _ = self.take()
        self.assertEqual((code, json.loads(out.splitlines()[0])["reproduces"]), (0, True))
        self.assertEqual((self.repo / gold3.FACTS).read_bytes(), before)
        record = gold3.load_inputs(self.repo)["facts_record"]
        self.assertEqual(record["reproduced_on"], [{"bordercall_commit": self.COMMIT, "date": "2026-10-28",
                                                    "read_on": "the grid, job 1"}])
        self.assertEqual(self.take()[0], 0)
        self.assertEqual(len(gold3.load_inputs(self.repo)["facts_record"]["reproduced_on"]), 1)
        recorded = (self.repo / gold3.FACTS_RECORD).read_bytes()
        moved = copy.deepcopy(self.published)
        moved[0]["sternum_voxels"] += 1
        code, out, _ = self.take(first=moved)
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)["differ"], {"facts": [moved[0]["id"]], "facts_b": []})
        self.assertEqual((self.repo / gold3.FACTS).read_bytes(), before)
        self.assertEqual((self.repo / gold3.FACTS_RECORD).read_bytes(), recorded)

    def test_a_reading_with_no_repaired_rows_anywhere_is_refused(self):
        code, _, err = self.take()
        self.assertEqual(code, 1)
        self.assertIn("repaired rows []", err)
        self.assertFalse((self.repo / gold3.FACTS).exists())

    def test_a_repaired_row_that_differs_from_the_side_file_is_refused(self):
        self.side_file(self.repaired)
        other = copy.deepcopy(self.repaired)
        other[0]["sternum_voxels"] += 1
        code, _, err = self.take(first=self.published + other)
        self.assertEqual(code, 1)
        self.assertIn("differs from", err)

    def test_a_second_reading_short_of_a_study_is_refused(self):
        self.side_file(self.repaired)
        code, _, err = self.take(second=self.second[1:])
        self.assertEqual(code, 1)
        self.assertIn("the second reading covers", err)

    def test_a_short_commit_id_is_refused(self):
        self.side_file(self.repaired)
        first, second = self.reading("a.jsonl", self.published), self.reading("b.jsonl", self.second)
        code, _, err = run("--repo", self.repo, "take-facts", first, second, "--read-on", "x", "--bordercall-commit", "abc123")
        self.assertEqual(code, 1)
        self.assertIn("no full commit id", err)


if __name__ == "__main__":
    unittest.main()
