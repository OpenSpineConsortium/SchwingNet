"""The completion of a column by a segmenter's levels, on stacked boxes written to a temporary folder.

Each column is a stack of slots, one per body, head at the top: a slot is a body of BODY_SLICES slices
over one slice of disc. The release's and the segmenter's masks share the slots, so a test says which
slots each arm draws and what it calls them; the segmenter's subregion mask calls each of its vertebrae's
voxels body and puts a disc under each slot that has a level below it, unless a test says where the
discs lie. Above the first slot lies a margin of MARGIN slices, where the segmenter draws its atlas
unless a test says otherwise, with no disc under it, as C1 and C2 meet. Run from the repository's root
with `python -m unittest discover -s holdings/tests -t .`."""
import gzip
import hashlib
import io
import json
import os
import re
import tempfile
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace

import nibabel as nib
import numpy as np

from holdings import fullspine_complete as C
from holdings import fullspine_facts as F

SIDE, BODY, BODY_SLICES, MARGIN = 16, 12, 4, 3   # a body is 12 x 12 x 4 = 576 voxels, over the 200 floor
SLOT = BODY_SLICES + 1                            # and a slice of disc under it
LOW = (SIDE - BODY) // 2
AFFINE = np.diag([1.0, 1.0, 2.0, 1.0])            # RAS, the third axis rising to the head
ID = C.VERSE_IDS
FULL = ["C2", "C3", "C4", "C5", "C6", "C7", *[f"T{i}" for i in range(1, 13)], *[f"L{i}" for i in range(1, 6)]]
ARCH = 41                                         # a subregion that is neither body nor disc
SEGMENTER = {"name": "SPINEPS"}


def slot_top(height, i):
    """The slice above the head-most slice of slot i's body."""
    return height - MARGIN - SLOT * i


def blank(slots):
    return np.zeros((SIDE, SIDE, 2 * MARGIN + SLOT * len(slots)), np.uint8)


def stack(slots):
    """A mask with one body per slot, the first slot at the head; a slot is a VerSe id or 0 for none."""
    mask = blank(slots)
    for i, label in enumerate(slots):
        if label:
            top = slot_top(mask.shape[2], i)
            mask[LOW:LOW + BODY, LOW:LOW + BODY, top - BODY_SLICES:top] = label
    return mask


def head_level(mask, name):
    """A level of 432 voxels drawn in the margin above the first slot, touching it, as an atlas is."""
    mask[LOW:LOW + BODY, LOW:LOW + BODY, mask.shape[2] - MARGIN:] = ID[name]


def disc_slice(mask, i):
    """The slice of disc under slot i's body."""
    return slot_top(mask.shape[2], i) - BODY_SLICES - 1


def subregion_mask(machine, slots, discs=None, arch=None):
    """The segmenter's subregion mask: its vertebrae's voxels as body, its sacrum's as sacrum, ARCH where
    arch is set, and a disc under each slot discs names (by default, every slot with a level below it)."""
    spine = np.where((machine > 0) & (machine != ID["sacrum"]), C.CORPUS, 0).astype(np.uint8)
    spine[machine == ID["sacrum"]] = ID["sacrum"]
    if arch is not None:
        spine[arch] = ARCH
    if discs is None:
        discs = [bool(slots[i]) and slots[i] != ID["sacrum"] and i + 1 < len(slots) and bool(slots[i + 1])
                 for i in range(len(slots))]
    for i, here in enumerate(discs):
        if here:
            spine[LOW:LOW + BODY, LOW:LOW + BODY, disc_slice(spine, i)] = C.DISC
    return spine


def ids(names):
    return [ID[name] if name else 0 for name in names]


def read(path, mode="rb"):
    with open(path, mode) as f:
        return f.read()


def write_json(value, path):
    with open(path, "w", encoding="ascii") as f:
        json.dump(value, f)


def save(path, mask):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(gzip.compress(nib.Nifti1Image(mask, AFFINE).to_bytes(), mtime=0))
    return path


def merge(mask, slots, label, first, second):
    """Slots first and second drawn as one level label, joined across the disc between them by a bar
    outside the body, as a segmenter's arch joins two vertebrae it merges; returns the bar."""
    height = mask.shape[2]
    for i in (first, second):
        top = slot_top(height, i)
        mask[LOW:LOW + BODY, LOW:LOW + BODY, top - BODY_SLICES:top] = label
        slots[i] = label
    bar = np.zeros(mask.shape, bool)
    bar[SIDE - LOW:, LOW:LOW + 2, slot_top(height, second) - BODY_SLICES:slot_top(height, first)] = True
    mask[bar] = label
    return bar


class Study:
    """A VerSe study in a temporary folder: the release's mask and the segmenter's two. atlas names the
    level the segmenter draws in the margin above the first slot (None for none), release_atlas the one
    the release draws there; edit(spine) changes the subregion mask before it is written; crop cuts that
    many slices off the head end of all three masks, so the field's top cuts what lies there."""

    def __init__(self, folder, release, machine, sid="verse001", discs=None, atlas="C1", release_atlas=None,
                 edit=None, crop=0):
        release_mask = np.array(release) if isinstance(release, np.ndarray) else stack(ids(release))
        if isinstance(machine, tuple):
            machine_mask, slots, arch = machine
            machine_mask = machine_mask.copy()
        else:
            slots, arch = ids(machine), None
            machine_mask = stack(slots)
        if atlas:
            head_level(machine_mask, atlas)
        if release_atlas:
            head_level(release_mask, release_atlas)
        spine_mask = subregion_mask(machine_mask, slots, discs, arch)
        if edit is not None:
            edit(spine_mask)
        keep = release_mask.shape[2] - crop
        self.release = save(os.path.join(folder, sid, "release.nii.gz"), release_mask[:, :, :keep])
        self.machine = save(os.path.join(folder, sid, "vert.nii.gz"), machine_mask[:, :, :keep])
        self.spine = save(os.path.join(folder, sid, "spine.nii.gz"), spine_mask[:, :, :keep])

    def complete(self, asked=None):
        return C.complete_study("verse", self.release, self.machine, self.spine, asked)


def outcome(record, name):
    return next(o for o in record["targets"] if o["name"] == name)


class Rules(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def study(self, release, machine, asked=None, **options):
        return Study(self.tmp.name, release, machine, **options).complete(asked)

    def test_the_sacrum_below_a_matched_column_is_added_and_the_release_is_left_alone(self):
        record, levels, completed, arm, grid = self.study(FULL + [None], FULL + ["sacrum"])
        self.assertEqual(record["added"], ["sacrum"])
        self.assertEqual(len(record["anchors"]), len(FULL))
        self.assertEqual(record["anchors"][0]["inside_machine"], 1.0)
        self.assertEqual(list(arm), ["sacrum"])
        self.assertEqual(len(arm["sacrum"]), BODY * BODY * BODY_SLICES)
        discs = outcome(record, "sacrum")["body"]["discs"]              # read inside L5's own cylinder
        self.assertEqual(len(discs), 1)
        self.assertEqual(discs[0]["start_mm"], -2.0)
        self.assertEqual(discs[0]["mm3"], 2.0 * discs[0]["voxels"])
        released = np.concatenate([C.flat(points, grid.shape) for points in levels.values()])
        self.assertEqual(len(np.intersect1d(arm["sacrum"], released)), 0)

    def test_the_disc_reading_is_checked_on_the_release_s_own_levels_first(self):
        record, *_ = self.study(FULL + [None], FULL + ["sacrum"])
        rows = record["calibration"]["pairs"]
        self.assertIsNone(record["calibration"]["reason"])
        self.assertEqual(len(rows), len(FULL) - 1)
        self.assertEqual((rows[0]["upper"], rows[0]["lower"]), ("C2", "C3"))
        self.assertEqual(rows[0]["upper_read"]["gap_mm"], 2.0)
        self.assertEqual(rows[0]["lower_read"]["overreach_share"], 0.0)

    def test_a_column_whose_discs_the_reading_cannot_find_is_refused_whole(self):
        record, *_ = self.study(FULL[:-1] + [None, None], FULL + ["sacrum"], discs=[False] * (len(FULL) + 1))
        self.assertEqual(record["added"], [])
        self.assertEqual(record["refused"], ["L5", "sacrum"])
        self.assertIn("fails on %d of %d pairs" % (len(FULL) - 2, len(FULL) - 2), record["calibration"]["reason"])
        for o in record["targets"]:
            self.assertEqual(o["reason"], record["calibration"]["reason"])

    def test_a_single_pair_of_anchors_is_too_few_to_trust_the_reading(self):
        release = [None] * (len(FULL) - 2) + ["L4", "L5", None]
        record, *_ = self.study(release, FULL + ["sacrum"], asked=["sacrum"])
        self.assertEqual(outcome(record, "sacrum")["state"], C.REFUSED)
        self.assertIn("checked on 1 pair(s)", outcome(record, "sacrum")["reason"])

    def test_a_gap_between_anchors_is_named_by_the_count_whatever_the_segmenter_calls_it(self):
        release = [n if n not in ("T6", "T7", "T8", "T9") else None for n in FULL] + [None]
        shifted = {name: FULL[i + 1] for i, name in enumerate(FULL[:-1])}
        machine = [shifted.get(n, "L6") for n in FULL] + ["sacrum"]
        record, *_ = self.study(release, machine)
        for name in ("T6", "T7", "T8", "T9"):
            self.assertEqual(outcome(record, name)["state"], C.ADDED, name)
            self.assertEqual(outcome(record, name)["naming"], "between T5 and T10")
        self.assertEqual(outcome(record, "T6")["machine_name"], "T7")
        self.assertEqual(outcome(record, "T9")["body"]["outer"]["discs"], 1)
        self.assertEqual(outcome(record, "T9")["body"]["inner"]["discs"], 1)

    def test_a_gap_whose_count_differs_is_refused(self):
        release = [n if n not in ("T6", "T7") else None for n in FULL] + [None]
        machine = ["T6" if n == "T7" else n for n in FULL] + ["sacrum"]   # two bodies drawn as one
        record, *_ = self.study(release, machine)
        for name in ("T6", "T7"):
            self.assertEqual(outcome(record, name)["state"], C.REFUSED)
            self.assertIn("has 1 levels between T5 and T8", outcome(record, name)["reason"])

    def test_a_gap_with_more_segmenter_levels_than_names_is_refused(self):
        mask = stack(ids(FULL + ["sacrum"]))
        top = slot_top(mask.shape[2], FULL.index("T6"))
        mask[:, :, top - 2:top] = np.where(mask[:, :, top - 2:top] > 0, ID["T13"], 0)   # T6 split in two
        slots = ids(FULL + ["sacrum"])
        release = [n if n != "T6" else None for n in FULL] + [None]
        record, *_ = self.study(release, (mask, slots, None))
        self.assertIn("has 2 levels between T5 and T7", outcome(record, "T6")["reason"])

    def test_a_release_level_the_segmenter_misses_in_a_gap_blocks_the_gap(self):
        release = [n if n not in ("T6", "T8") else None for n in FULL] + [None]
        machine = [n if n != "T7" else None for n in FULL] + ["sacrum"]
        record, *_ = self.study(release, machine)
        for name in ("T6", "T8"):
            self.assertIn("draws T7 between T5 and T9", outcome(record, name)["reason"])

    def test_one_level_of_a_gap_failing_its_checks_refuses_the_gap(self):
        release = stack(ids([n if n not in ("T6", "T7") else None for n in FULL] + [None]))
        top = slot_top(release.shape[2], FULL.index("T7"))
        release[LOW:LOW + BODY, LOW:LOW + 7, top - BODY_SLICES] = ID["T8"]   # the release's T8 reaches into T7
        record, *_ = self.study(release, FULL + ["sacrum"])
        for name in ("T6", "T7"):
            self.assertEqual(outcome(record, name)["state"], C.REFUSED, name)
            self.assertIn("count names T7 between T5 and T8", outcome(record, name)["reason"])
            self.assertIn("so no level of the gap is taken", outcome(record, name)["reason"])

    def test_c2_under_the_atlas_in_a_gap_is_read_with_c3_inward_and_the_atlas_outward(self):
        release = [None] + FULL[1:] + [None]
        record, *_ = self.study(release, FULL + ["sacrum"], release_atlas="C1")
        self.assertEqual([a["release"] for a in record["anchors"]][:2], ["C1", "C3"])
        c2 = outcome(record, "C2")
        self.assertEqual(c2["state"], C.ADDED)
        self.assertEqual(c2["naming"], "between C1 and C3")
        self.assertEqual(c2["body"]["outer"], {"beyond": "the atlas, a level of its own"})
        self.assertEqual(c2["body"]["inner"]["discs"], 1)
        self.assertNotIn("C1", [row["upper"] for row in record["calibration"]["pairs"]])

    def test_the_head_end_takes_levels_only_where_the_segmenter_names_them_alike(self):
        release = [None] * 6 + FULL[6:] + [None]
        record, *_ = self.study(release, FULL + ["sacrum"])
        self.assertEqual(record["refused"], [])
        c2 = outcome(record, "C2")
        self.assertEqual(c2["naming"], "above T1, named alike by the count and the segmenter")
        self.assertEqual(c2["body"]["step_ratio"], 1.0)
        self.assertFalse(c2["body"]["cut_by_field"])
        self.assertEqual(c2["body"]["outer"], {"beyond": "the atlas, a level of its own"})

    def test_c2_with_nothing_above_it_is_refused_unless_the_field_cuts_it(self):
        release = [None] * 6 + FULL[6:] + [None]
        record, *_ = self.study(release, FULL + ["sacrum"], atlas=None)
        self.assertEqual(outcome(record, "C3")["state"], C.ADDED)
        self.assertEqual(outcome(record, "C2")["state"], C.REFUSED)
        self.assertIn("its label may hold the atlas", outcome(record, "C2")["reason"])
        record, *_ = self.study(release, FULL + ["sacrum"], atlas=None, crop=MARGIN + 2)
        c2 = outcome(record, "C2")
        self.assertEqual(c2["state"], C.ADDED)
        self.assertTrue(c2["body"]["cut_by_field"])
        self.assertEqual(c2["body"]["height_ratio"], 0.5)                # under 0.6, where the field cuts it
        self.assertEqual(c2["body"]["outer"], {"beyond": "the field's top, which cuts its body"})

    def test_c2_under_a_level_the_segmenter_does_not_call_the_atlas_is_refused(self):
        release = [None] * 6 + FULL[6:] + [None]
        record, *_ = self.study(release, FULL + ["sacrum"], atlas="T13")
        self.assertEqual(outcome(record, "C3")["state"], C.ADDED)
        self.assertIn("is its T13, not an atlas of its own", outcome(record, "C2")["reason"])

    def test_a_level_beyond_which_the_segmenter_draws_its_atlas_is_refused(self):
        release = [None] * 6 + FULL[6:] + [None]
        machine = ["C2", "C3", "C4", "C1", "C6", "C7"] + FULL[6:] + ["sacrum"]   # C5 called C1
        record, *_ = self.study(release, machine, atlas=None)
        self.assertEqual(outcome(record, "C7")["state"], C.ADDED)
        self.assertIn("level beyond it is the atlas, where the count names it C6", outcome(record, "C6")["reason"])
        for name in ("C5", "C4", "C3", "C2"):
            self.assertEqual(outcome(record, name)["state"], C.REFUSED, name)

    def test_the_head_walk_stops_at_the_first_name_that_differs(self):
        release = [None] * 6 + FULL[6:] + [None]
        machine = ["C2", "C3", "C4", "L6", "C6", "C7"] + FULL[6:] + ["sacrum"]   # C5 called L6, the rest alike
        record, *_ = self.study(release, machine)
        self.assertEqual(outcome(record, "C7")["state"], C.ADDED)
        self.assertEqual(outcome(record, "C6")["state"], C.ADDED)
        for name in ("C5", "C4", "C3", "C2"):
            self.assertEqual(outcome(record, name)["state"], C.REFUSED, name)
            self.assertIn("gives C5 where the segmenter calls the level L6", outcome(record, name)["reason"])

    def test_an_unmatched_release_level_beyond_the_end_anchor_stops_the_walk(self):
        release = [None, "C3", None, None, None, None] + FULL[6:] + [None]
        mask = stack(ids(FULL + ["sacrum"]))
        top = slot_top(mask.shape[2], 1)
        mask[LOW:LOW + BODY, LOW + 8:LOW + BODY, top - BODY_SLICES:top] = 0   # the segmenter's C3 a third short
        record, *_ = self.study(release, (mask, ids(FULL + ["sacrum"]), None), asked=["C2", "C4", "C5", "C6", "C7"])
        self.assertNotIn("C3", [a["release"] for a in record["anchors"]])
        self.assertEqual(outcome(record, "C4")["state"], C.ADDED)
        self.assertIn("the release draws C3 above T1", outcome(record, "C2")["reason"])

    def test_the_walk_counts_through_names_not_asked_for(self):
        release = [None] * 2 + FULL[2:] + [None]                       # the release starts at C4
        machine = ["C1", "C2"] + FULL[2:] + ["sacrum"]                 # the segmenter one off above C4
        record, *_ = self.study(release, machine, asked=["C2"], atlas=None)
        self.assertEqual(outcome(record, "C2")["state"], C.REFUSED)
        self.assertIn("gives C3 where the segmenter calls the level C2", outcome(record, "C2")["reason"])

    def test_names_no_rule_here_gives_are_refused_when_asked_for(self):
        record, *_ = self.study(FULL + [None], FULL + ["sacrum"], asked=["C1", "T13", "L6"])
        self.assertEqual(record["refused"], ["C1", "T13", "L6"])
        for o in record["targets"]:
            self.assertIn("no rule here names %s" % o["name"], o["reason"])

    def test_the_sacrum_is_refused_past_a_level_no_name_accounts_for(self):
        release = FULL[:-1] + [None, None]
        machine = FULL[:-1] + ["L6", "sacrum"]
        record, *_ = self.study(release, machine)
        self.assertIn("calls the level L6", outcome(record, "L5")["reason"])
        self.assertIn("1 level(s) between the release's L4 and the sacrum", outcome(record, "sacrum")["reason"])

    def test_a_body_the_field_test_does_not_ask_for_is_never_named_and_blocks_the_sacrum(self):
        release = FULL[:-1] + [None, None]                  # no_l5: the release stops at L4
        record, *_ = self.study(release, FULL + ["sacrum"], asked=["sacrum"])
        self.assertEqual([o["name"] for o in record["targets"]], ["sacrum"])
        self.assertIn("below the release's L4 L5, which the field test does not ask for",
                      outcome(record, "sacrum")["reason"])

    def test_the_sacrum_below_levels_the_foot_walk_named_is_added(self):
        release = [n if n not in ("L4", "L5") else None for n in FULL] + [None]   # the release stops at L3
        record, *_ = self.study(release, FULL + ["sacrum"])
        self.assertEqual(record["added"], ["L4", "L5", "sacrum"])
        self.assertEqual(outcome(record, "sacrum")["naming"], "the segmenter's sacrum, below L5")
        self.assertEqual(outcome(record, "L5")["body"]["outer"]["discs"], 1)

    def test_a_sacrum_that_takes_in_the_body_below_the_release_s_l4_is_refused(self):
        release = FULL[:-1] + [None, None]
        mask, slots = stack(ids(FULL[:-1] + [None, None])), ids(FULL[:-1] + [None, None])
        bar = merge(mask, slots, ID["sacrum"], len(FULL) - 1, len(FULL))
        record, *_ = self.study(release, (mask, slots, bar), asked=["sacrum"])
        self.assertIn("directly under L4", outcome(record, "sacrum")["reason"])

    def sacrum_of_three(self, inner_disc_rows):
        """The column with a sacrum three slots long, a disc of inner_disc_rows rows of BODY voxels
        between its second and third slots (none for 0) and none between its first and second."""
        n = len(FULL)
        mask, slots = stack(ids(FULL + [None] * 3)), ids(FULL + [None] * 3)
        bar = merge(mask, slots, ID["sacrum"], n, n + 1) | merge(mask, slots, ID["sacrum"], n + 1, n + 2)
        discs = [True] * n + [False] * 3

        def edit(spine):
            spine[LOW:LOW + inner_disc_rows, LOW:LOW + BODY, disc_slice(spine, n + 1)] = C.DISC
        return self.study(FULL + [None] * 3, (mask, slots, bar), discs=discs, edit=edit)[0]

    def test_a_sacrum_holding_a_disc_as_large_as_the_one_above_it_is_refused(self):
        record = self.sacrum_of_three(BODY)
        sacrum = outcome(record, "sacrum")
        self.assertEqual(sacrum["state"], C.REFUSED)
        self.assertRegex(sacrum["reason"], r"a disc of \d+ voxels, 9\d% of the one above it, lies 18.0 mm below its head end")
        self.assertEqual([d["start_mm"] for d in sacrum["body"]["discs"]], [-2.0, 18.0])

    def test_a_sacrum_holding_a_small_disc_is_added_with_its_runs_recorded(self):
        record = self.sacrum_of_three(5)                                   # 5 of the disc above's 12 rows
        sacrum = outcome(record, "sacrum")
        self.assertEqual(sacrum["state"], C.ADDED)
        discs = sacrum["body"]["discs"]
        self.assertEqual([d["start_mm"] for d in discs], [-2.0, 18.0])
        self.assertLess(discs[1]["voxels"], C.SACRUM_DISC_SHARE * discs[0]["voxels"])
        record = self.sacrum_of_three(1)                                   # 12 voxels, a speck under the floor
        self.assertEqual(len(outcome(record, "sacrum")["body"]["discs"]), 1)

    def test_a_sacrum_that_reaches_past_the_disc_into_the_body_above_refuses_that_body_too(self):
        release = FULL[:-1] + [None, None]                                 # the release stops at L4
        mask = stack(ids(FULL + ["sacrum"]))
        bottom = slot_top(mask.shape[2], FULL.index("L5")) - BODY_SLICES
        mask[LOW + 5, LOW + 5:LOW + 7, bottom] = ID["sacrum"]              # two voxels of L5's foot slice
        record, *_ = self.study(release, (mask, ids(FULL + ["sacrum"]), None), asked=["L5", "sacrum"])
        sacrum, l5 = outcome(record, "sacrum"), outcome(record, "L5")
        self.assertEqual(sacrum["state"], C.REFUSED)
        self.assertIn("past the disc above it, in the body above's place", sacrum["reason"])
        self.assertEqual(l5["state"], C.REFUSED)
        self.assertIn("the next level out, which the count names sacrum, fails against it", l5["reason"])
        self.assertEqual(l5["body"]["outer"]["discs"], 1)                 # the numbers L5 passed on are kept

    def test_a_name_asked_for_that_the_release_draws_is_no_target(self):
        record, *_ = self.study(FULL + [None], FULL + ["sacrum"], asked=["L5", "sacrum"])
        self.assertEqual(record["added"], ["sacrum"])
        self.assertEqual(record["asked"], ["L5", "sacrum"])
        with self.assertRaises(ValueError):
            C.targets_of(set(), ["S1"])

    def test_the_sacrum_is_refused_where_the_release_s_last_level_is_unmatched(self):
        release = FULL + [None]
        machine = FULL[:-1] + [None, "sacrum"]
        record, *_ = self.study(release, machine)
        self.assertIn("foot-most level L5 is not matched", outcome(record, "sacrum")["reason"])

    def test_anchors_out_of_order_refuse_everything(self):
        self.assertFalse(C.in_order({"T1": 9, "T2": 8}, [8, 9]))
        self.assertTrue(C.in_order({"T1": 8, "T2": 9}, [8, 7, 9]))
        swap = {"T5": "T6", "T6": "T5"}
        release = [None] + [swap.get(n, n) for n in FULL[1:]] + [None]   # C2 undrawn, T5 and T6 swapped
        record, *_ = self.study(release, FULL + ["sacrum"])
        self.assertEqual(record["added"], [])
        self.assertEqual(record["refused"], ["C2", "sacrum"])
        for o in record["targets"]:
            self.assertIn("another order", o["reason"])

    def test_an_anchor_needs_each_level_mostly_inside_the_other(self):
        self.assertEqual(C.anchors({"L5": 100}, {24: 100}, {("L5", 24): 80}), {"L5": 24})
        self.assertEqual(C.anchors({"L5": 100}, {24: 100}, {("L5", 24): 79}), {})
        self.assertEqual(C.anchors({"L5": 100}, {24: 200}, {("L5", 24): 100}), {})   # a merge: Dice 0.67
        self.assertEqual(C.anchors({"L5": 200}, {24: 100}, {("L5", 24): 100}), {})   # a split
        self.assertEqual(C.anchors({"L5": 100}, {24: 100}, {}), {})

    def test_a_merged_end_anchor_stops_the_foot_walk(self):
        release = [n if n not in ("L4", "L5") else None for n in FULL] + [None]   # the release stops at L3
        mask, slots = stack(ids(FULL + ["sacrum"])), ids(FULL + ["sacrum"])
        bar = merge(mask, slots, ID["L3"], FULL.index("L3"), FULL.index("L4"))
        top = slot_top(mask.shape[2], FULL.index("L5"))
        mask[LOW:LOW + BODY, LOW:LOW + BODY, top - BODY_SLICES:top] = ID["L4"]   # the real L5 called L4
        slots[FULL.index("L5")] = ID["L4"]
        record, *_ = self.study(release, (mask, slots, bar))
        self.assertNotIn("L3", [a["release"] for a in record["anchors"]])
        self.assertEqual(record["added"], [])
        self.assertIn("the release draws L3 below L2", outcome(record, "L4")["reason"])

    def test_a_merged_head_anchor_stops_the_head_walk(self):
        release = [None] * 6 + FULL[6:] + [None]                         # the release starts at T1
        names = ["C3", "C4", "C5", "C6", "C7", None] + FULL[6:] + ["sacrum"]   # each cervical one off
        mask, slots = stack(ids(names)), ids(names)
        bar = merge(mask, slots, ID["T1"], FULL.index("C7"), FULL.index("T1"))
        record, *_ = self.study(release, (mask, slots, bar))
        self.assertNotIn("T1", [a["release"] for a in record["anchors"]])
        self.assertEqual(record["added"], ["sacrum"])
        for name in ("C7", "C6", "C5", "C4", "C3", "C2"):
            self.assertIn("the release draws T1 above T2", outcome(record, name)["reason"])

    def test_a_split_body_beyond_the_anchor_stops_the_walk_and_refuses_the_body_inward_of_it(self):
        release = [None] * 6 + FULL[6:] + [None]
        names = ["C2", "C3", "C4", "C5", "C6", "C7"]
        mask, slots = stack(ids(names + FULL[6:] + ["sacrum"])), ids(names + FULL[6:] + ["sacrum"])
        height = mask.shape[2]
        relabel = {"C2": None, "C3": "C2", "C4": "C3"}                  # the C5 body cut in two below them
        for name, new in relabel.items():
            top = slot_top(height, FULL.index(name))
            mask[LOW:LOW + BODY, LOW:LOW + BODY, top - BODY_SLICES:top] = ID[new] if new else 0
        top = slot_top(height, FULL.index("C5"))
        mask[LOW:LOW + BODY, LOW:LOW + BODY, top - 2:top] = ID["C4"]
        record, *_ = self.study(release, (mask, slots, None))
        self.assertEqual(outcome(record, "C7")["state"], C.ADDED)
        self.assertEqual(outcome(record, "C5")["state"], C.REFUSED)
        self.assertIn("times its inner neighbour's height", outcome(record, "C5")["reason"])
        self.assertEqual(outcome(record, "C6")["state"], C.REFUSED)
        self.assertIn("which the count names C5, fails against it", outcome(record, "C6")["reason"])
        for name in ("C4", "C3", "C2"):
            self.assertEqual(outcome(record, name)["state"], C.REFUSED, name)

    def test_a_body_the_segmenter_missed_beyond_the_anchor_stops_the_walk(self):
        release = [None] * 6 + FULL[6:] + [None]
        machine = ["C3", None, "C4", "C5", "C6", "C7"] + FULL[6:] + ["sacrum"]   # no level on C3's body
        discs = [True] * (len(FULL)) + [False]
        record, *_ = self.study(release, machine, discs=discs)
        self.assertEqual(outcome(record, "C5")["state"], C.ADDED)
        self.assertEqual(outcome(record, "C4")["state"], C.REFUSED)
        self.assertIn("on its outer side, 2 discs lie between", outcome(record, "C4")["reason"])
        self.assertEqual(outcome(record, "C3")["state"], C.REFUSED)
        self.assertEqual(outcome(record, "C2")["state"], C.REFUSED)

    def test_a_level_the_voxel_check_refuses_stops_the_walk_and_blocks_the_sacrum(self):
        release = stack(ids(FULL[:-1] + [None, None]))                  # the release stops at L4
        top = slot_top(release.shape[2], FULL.index("L5"))
        release[LOW:LOW + BODY, LOW:LOW + 6, top - 1] = ID["L4"]         # 72 voxels of L5 under its L4
        record, *_ = self.study(release, FULL + ["sacrum"], asked=["L5", "sacrum"])
        self.assertIn("over 10%", outcome(record, "L5")["reason"])
        self.assertEqual(outcome(record, "L5")["release_share"], 0.125)
        self.assertEqual(outcome(record, "L5")["added_voxels"], 504)
        self.assertEqual(outcome(record, "sacrum")["state"], C.REFUSED)
        self.assertIn("1 level(s) between the release's L4 and the sacrum", outcome(record, "sacrum")["reason"])

    def test_the_voxel_floor_and_share_apply_to_what_a_level_adds(self):
        numbers, reason = C.voxel_check(np.arange(300), np.arange(150), np.arange(0), None)
        self.assertIn("adds 150 voxels", reason)
        numbers, reason = C.voxel_check(np.arange(400), np.arange(50), np.arange(50), None)
        self.assertIn("lies under the release's other levels", reason)
        self.assertEqual(numbers["added_voxels"], 350)

    def test_a_release_fragment_is_kept_whole_and_the_arm_never_draws_over_the_release(self):
        mask = stack(ids(FULL + [None]))
        height = mask.shape[2]
        top = slot_top(height, 0)
        mask[:, :, top - BODY_SLICES:top] = 0
        mask[LOW:LOW + BODY, LOW:LOW + BODY, top - 1] = ID["C2"]         # a 144-voxel sliver of C2
        machine = stack(ids(FULL + ["sacrum"]))
        machine[:, :, top - 1] = 0                                       # the segmenter's C2 starts lower
        reach = np.zeros(machine.shape, bool)
        reach[LOW:LOW + BODY, LOW:LOW + 2, top - SLOT - 1] = True        # and its arch reaches C3's top slice
        machine[reach] = ID["C2"]
        slots = ids(FULL + ["sacrum"])
        record, levels, completed, arm, grid = self.study(mask, (machine, slots, reach))
        self.assertEqual(outcome(record, "C2")["state"], C.ADDED)
        self.assertEqual(outcome(record, "C2")["release_fragment_voxels"], 144)
        self.assertEqual(outcome(record, "C2")["release_fragment_inside"], 0)
        release_all = np.concatenate([C.flat(points, grid.shape) for points in levels.values()])
        self.assertEqual(len(np.intersect1d(arm["C2"], release_all)), 0)
        self.assertEqual(len(np.intersect1d(completed["C2"], C.flat(levels["C2"], grid.shape))), 144)
        self.assertEqual(len(np.intersect1d(completed["C2"], C.flat(levels["C3"], grid.shape))), 0)

    def test_a_stray_label_under_the_floor_is_left_out_of_the_chain(self):
        release = [n if n not in ("T6", "T7") else None for n in FULL] + [None]
        machine = stack(ids(FULL + ["sacrum"]))
        machine[0:2, 0:2, slot_top(machine.shape[2], FULL.index("T7")) - 1] = ID["T13"]
        record, *_ = self.study(release, (machine, ids(FULL + ["sacrum"]), None))
        self.assertEqual(record["machine_small"], [{"label": ID["T13"], "voxels": 4}])
        self.assertEqual(outcome(record, "T7")["state"], C.ADDED)


def column(bodies, disc_points, affine, shape, shares=None, names=None, atlas=()):
    """A segmenter's column as column_of() gives it, from bodies placed by hand."""
    return SimpleNamespace(bodies=bodies, discs=C.placed(disc_points, affine),
                           grid=SimpleNamespace(shape=shape, affine=np.asarray(affine, float)),
                           cell=C.cell_of(affine), shares=shares or {label: 1.0 for label in bodies},
                           names=names or {label: "L%d" % label for label in bodies},
                           chain=sorted(bodies), sacrum=None, atlas=set(atlas))


class Bodies(unittest.TestCase):
    """The body checks of rule 6 on bodies placed by hand: level 1 between its inner neighbour 2 (and 3
    beyond it) and its outer neighbour 4."""

    def body(self, low, high, extra=()):
        points = [[i, j, k] for i in range(12) for j in range(12) for k in range(low, high)] + list(extra)
        return C.placed(np.array(points), AFFINE)

    def check(self, slices, discs, name="T5", extra=(), shares=None, atlas=()):
        bodies = {label: self.body(*span, extra=extra if label == 1 else ()) for label, span in slices.items()}
        disc_points = np.array([[i, j, k] for i in range(12) for j in range(12) for k in discs]) if discs else C.NO_POINTS
        return C.body_check(name, 1, 2, [(2, 3)], 4, column(bodies, disc_points, AFFINE, (64, 64, 64), shares,
                                                            atlas=atlas))

    COLUMN = {3: (0, 4), 2: (5, 9), 1: (10, 14), 4: (15, 19)}

    def test_one_body_one_disc_away_on_each_side_passes(self):
        numbers, reason, against = self.check(self.COLUMN, [4, 9, 14])
        self.assertIsNone(reason)
        self.assertEqual(numbers["inner"]["discs"], 1)
        self.assertEqual(numbers["inner"]["gap_mm"], 2.0)
        self.assertEqual(numbers["inner"]["cells"], 12)                 # the cylinder cuts the four corner cells
        self.assertEqual(numbers["outer"]["discs"], 1)
        self.assertEqual(numbers["disc_voxels_middle"], 0)

    def test_two_bodies_drawn_as_one_hold_a_disc_inside(self):
        numbers, reason, against = self.check({3: (0, 9), 2: (10, 19), 1: (20, 29), 4: (30, 39)}, [9, 19, 24, 29],
                                               name="C2")
        self.assertIn("a disc lies in the middle third of its body", reason)
        self.assertIsNone(against)

    def test_no_disc_between_two_bodies_is_refused_against_the_inner_one(self):
        numbers, reason, against = self.check(self.COLUMN, [4, 14])
        self.assertIn("toward its inner neighbour, 0 discs lie between", reason)
        self.assertEqual(against, C.INNER)

    def test_no_disc_beyond_a_body_is_refused_on_its_outer_side(self):
        numbers, reason, against = self.check(self.COLUMN, [4, 9])
        self.assertIn("on its outer side, 0 discs lie between", reason)
        self.assertIsNone(against)

    def test_a_body_too_short_is_refused(self):
        numbers, reason, against = self.check({3: (0, 4), 2: (5, 9), 1: (10, 12), 4: (13, 17)}, [4, 9, 12])
        self.assertIn("times its inner neighbour's height", reason)
        self.assertEqual(against, C.INNER)

    def test_a_body_in_pieces_is_refused(self):
        numbers, reason, against = self.check(self.COLUMN, [4, 9, 14], shares={1: 0.6, 2: 1.0, 3: 1.0, 4: 1.0})
        self.assertIn("largest piece holds 60%", reason)

    def test_a_body_whose_own_voxels_lie_in_two_pieces_is_refused(self):
        far = [[i, j, 18] for i in range(12) for j in range(2)]          # 24 voxels in the outer body's place
        numbers, reason, against = self.check(self.COLUMN, [4, 9, 14], extra=far)
        self.assertIn("its body is in pieces, the largest holding 96.0%", reason)

    def test_a_body_that_reaches_past_the_disc_into_its_neighbour_is_refused(self):
        across = [[5, 5, 8], [5, 6, 8]]                                  # two voxels of the inner body's top slice
        numbers, reason, against = self.check(self.COLUMN, [4, 9, 14], extra=across)
        self.assertIn("toward its inner neighbour, 0.35% of its body lies over 1 mm past the disc", reason)
        self.assertEqual(numbers["inner"]["overreach_share"], 0.00346)
        self.assertEqual(against, C.INNER)

    def test_a_body_cut_short_of_the_disc_is_refused(self):
        numbers, reason, against = self.check({3: (0, 4), 2: (5, 9), 1: (11, 15), 4: (16, 20)}, [4, 9, 15])
        self.assertIn("stops 4.0 mm short of the disc, over 3.0 mm: cut short", reason)

    def test_a_body_that_runs_into_a_thick_disc_is_refused(self):
        numbers, reason, against = self.check({3: (0, 4), 2: (5, 9), 1: (10, 15), 4: (16, 20)}, [4, 9, 10, 11, 15])
        self.assertIn("its body runs 2.0 mm into the disc, over 1 mm", reason)

    def test_a_tall_body_with_a_long_step_reads_as_two_merged_except_at_c2(self):
        slices = {3: (0, 4), 2: (5, 9), 1: (10, 16), 4: (17, 21)}
        numbers, reason, against = self.check(slices, [4, 9, 16])
        self.assertIn("as two bodies with no disc drawn between them read", reason)
        self.assertEqual((numbers["height_ratio"], numbers["step_ratio"]), (1.5, 1.2))
        numbers, reason, against = self.check(slices, [4, 9], name="C2", atlas=[4])
        self.assertIsNone(reason)
        self.assertEqual(numbers["outer"], {"beyond": "the atlas, a level of its own"})

    def test_a_voxel_reaches_along_an_axis_by_its_longest_edge(self):
        self.assertEqual(C.reach(C.cell_of(AFFINE), np.array([0.0, 0.0, 1.0])), 2.0)
        self.assertAlmostEqual(C.reach(C.cell_of(AFFINE), np.array([1.0, 0.0, 1.0]) / np.sqrt(2)), np.sqrt(2))


class Tilted(unittest.TestCase):
    """The body checks on a column tilted 35 degrees from the image's head-foot axis, as VerSe's
    sagittal necks are: boxes 12 mm wide and 16 mm deep, stacked along the column on a 1 mm grid."""

    ANGLE = 35.0

    def box(self, first, last):
        """The voxels of a box from first to last mm along the tilted column."""
        angle = np.radians(self.ANGLE)
        axis, depth = np.array([0.0, np.sin(angle), np.cos(angle)]), np.array([0.0, np.cos(angle), -np.sin(angle)])
        steps = np.arange(first, last, 0.5)[:, None, None] * axis + np.arange(-8, 8, 0.5)[None, :, None] * depth
        points = steps.reshape(-1, 3)[:, None, :] + np.array([[x, 0.0, 0.0] for x in range(12)])[None]
        return np.unique(np.round(points.reshape(-1, 3) + [20, 40, 40]).astype(np.int64), axis=0)

    def check(self, bodies, discs, name="T5"):
        placed = {label: C.placed(self.box(*span), np.eye(4)) for label, span in bodies.items()}
        disc_points = np.concatenate([self.box(*span) for span in discs])
        return C.body_check(name, 1, 2, [(2, 3)], 4, column(placed, disc_points, np.eye(4), (128, 128, 128)))

    def test_a_tilted_body_with_the_disc_beside_it_at_its_middle_height_passes(self):
        bodies = {3: (26, 36), 2: (13, 23), 1: (0, 10), 4: (-13, -3)}
        discs = [(10, 13), (23, 26), (-3, 0)]
        body, disc = self.box(*bodies[1]), self.box(*discs[0])
        low, high = body[:, 2].min(), body[:, 2].max()
        middle_height = (disc[:, 2] > low + (high - low) / 4) & (disc[:, 2] < high - (high - low) / 4)
        under = np.all((disc[:, :2] >= body[:, :2].min(0)) & (disc[:, :2] <= body[:, :2].max(0)), axis=1)
        self.assertGreater(int((middle_height & under).sum()), 0)
        numbers, reason, against = self.check(bodies, discs)
        self.assertIsNone(reason)
        self.assertEqual(numbers["inner"]["discs"], 1)
        self.assertEqual(numbers["outer"]["discs"], 1)
        self.assertEqual(numbers["disc_voxels_middle"], 0)
        self.assertAlmostEqual(numbers["tilt_deg"], self.ANGLE, delta=1.0)

    def test_two_tilted_bodies_drawn_as_one_hold_a_disc_inside(self):
        bodies = {3: (52, 75), 2: (26, 49), 1: (0, 23), 4: (-26, -3)}
        discs = [(23, 26), (49, 52), (8, 11), (-3, 0)]
        numbers, reason, against = self.check(bodies, discs)
        self.assertIn("a disc lies in the middle third of its body", reason)

    def test_a_body_missed_on_a_tilted_column_leaves_two_discs(self):
        bodies = {3: (52, 62), 2: (26, 36), 1: (0, 10), 4: (-13, -3)}
        discs = [(10, 13), (23, 26), (36, 39), (-3, 0)]
        numbers, reason, against = self.check(bodies, discs)
        self.assertIn("2 discs lie between", reason)


class Arm(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_the_arm_is_written_byte_for_byte_the_same_and_holds_verse_ids(self):
        study = Study(self.tmp.name, FULL + [None], FULL + ["sacrum"])
        _, _, _, arm, grid = study.complete()
        first, second = C.arm_bytes(arm, grid), C.arm_bytes(arm, grid)
        self.assertEqual(hashlib.sha256(first).hexdigest(), hashlib.sha256(second).hexdigest())
        written = F.image_of(first)
        self.assertTrue(F.same_grid(written, grid))
        self.assertEqual(sorted(np.unique(np.asanyarray(written.dataobj))), [0, ID["sacrum"]])
        self.assertEqual(C.arm_name("verse001", first),
                         "verse001_machine_%s.nii.gz" % hashlib.sha256(first).hexdigest()[:12])

    def test_a_totalsegmentator_folder_is_read_level_by_level(self):
        folder = os.path.join(self.tmp.name, "s0001")
        release = [n if n not in ("T6",) else None for n in FULL] + ["sacrum"]
        for name in set(release) - {None}:
            mask = (stack(ids(release)) == ID[name]).astype(np.uint8)
            base = "sacrum.nii.gz" if name == "sacrum" else "vertebrae_%s.nii.gz" % name
            save(os.path.join(folder, base), mask)
        machine_mask = stack(ids(FULL + ["sacrum"]))
        machine = save(os.path.join(self.tmp.name, "s0001.nii.gz"), machine_mask)
        spine = save(os.path.join(self.tmp.name, "s0001_spine.nii.gz"),
                     subregion_mask(machine_mask, ids(FULL + ["sacrum"])))
        record, *_ = C.complete_study("totalsegmentator", folder, machine, spine)
        self.assertEqual(record["added"], ["T6"])
        self.assertEqual(len(record["files"]["release"]), len(FULL))
        self.assertEqual(len(C.release_files("totalsegmentator", folder)), len(FULL))

    def test_a_release_that_differs_from_its_facts_row_is_caught(self):
        levels = {"L5": np.zeros((5, 3), np.int32)}
        self.assertTrue(C.same_release(levels, {"levels": {"L5": {"voxels": 5}}}))
        self.assertFalse(C.same_release(levels, {"levels": {"L5": {"voxels": 6}}}))
        self.assertFalse(C.same_release(levels, {"levels": {"L5": {"voxels": 5}, "L4": {"voxels": 9}}}))

    def test_a_study_that_cannot_be_completed_is_a_row_that_says_whose_it_is(self):
        study = Study(self.tmp.name, FULL + [None], FULL + ["sacrum"])
        job = ("verse001", "verse", study.release, study.machine, study.spine, None, None, SEGMENTER,
               {"levels": {}}, self.tmp.name, "f" * 64)
        row = C.study_safe(job)
        self.assertIn("ValueError: the release read here differs", row["error"])
        self.assertEqual((row["id"], row["member"], row["segmenter"], row["job_sha256"]),
                         ("verse001", "verse", SEGMENTER, "f" * 64))


def facts_row(study, sid):
    img = F.image_of(read(study.release))
    levels = {F.VERSE_NAMES[label]: points for label, points in F.voxel_points(img).items()}
    return F.study_row("verse", sid, {"release.nii.gz": read(study.release)}, img, levels, {}, {})


class CommandLine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        tmp = self.tmp.name
        self.studies = {"verse001": Study(tmp, FULL + [None], FULL + ["sacrum"]),
                        "verse002": Study(tmp, FULL + [None], FULL + [None], sid="verse002")}
        facts = os.path.join(tmp, "facts.jsonl")
        with open(facts, "w", encoding="ascii") as f:
            f.writelines(F.row_line(facts_row(s, sid)) for sid, s in self.studies.items())
        how = os.path.join(tmp, "input.json")
        write_json({"input": "as_is"}, how)
        spec = {"segmenter": SEGMENTER, "facts": {"verse": facts},
                "studies": [dict({"id": sid, "member": "verse", "release": s.release, "machine": s.machine,
                                  "spine": s.spine}, **({"input": how} if sid == "verse001" else {}))
                            for sid, s in self.studies.items()]}
        self.jobs = os.path.join(tmp, "jobs.json")
        write_json(spec, self.jobs)
        self.out = os.path.join(tmp, "out")

    def run_main(self):
        with redirect_stdout(io.StringIO()) as printed:
            C.main([self.jobs, self.out])
        return printed.getvalue()

    def test_records_masks_and_completed_facts(self):
        os.makedirs(os.path.join(self.out, "masks"))
        stale = os.path.join(self.out, "masks", "verse002_machine_000000000000.nii.gz")
        with open(stale, "wb"):                                         # an arm an earlier run left
            pass
        self.run_main()
        records = [json.loads(line) for line in read(os.path.join(self.out, "records.jsonl"), "r").splitlines()]
        self.assertEqual([r["id"] for r in records], ["verse001", "verse002"])
        self.assertEqual(records[0]["input"], {"input": "as_is"})
        self.assertEqual(records[0]["segmenter"], SEGMENTER)
        self.assertRegex(records[0]["job_sha256"], "^[0-9a-f]{64}$")
        self.assertEqual(records[1]["refused"], ["sacrum"])
        self.assertIn("draws no sacrum", records[1]["targets"][0]["reason"])
        completed = [json.loads(line) for line in read(os.path.join(self.out, "facts.jsonl"), "r").splitlines()]
        self.assertEqual(len(completed), 1)
        row = completed[0]
        self.assertIn("sacrum", row["levels"])
        self.assertEqual(list(row["machine_levels"]), ["sacrum"])
        self.assertIn("L5-sacrum", row["distances_mm"])
        (name, entry), = row["machine_files"].items()
        self.assertRegex(name, r"^verse001_machine_[0-9a-f]{12}\.nii\.gz$")
        data = read(os.path.join(self.out, "masks", name))
        self.assertEqual(entry["sha256"], hashlib.sha256(data).hexdigest())
        self.assertTrue(entry["sha256"].startswith(re.match(r"verse001_machine_(\w+)\.nii", name).group(1)))
        self.assertEqual(os.listdir(os.path.join(self.out, "masks")), [name])

    def test_a_run_cut_short_keeps_only_the_rows_its_jobs_still_make(self):
        jobs = C.jobs_of(json.loads(read(self.jobs)), os.path.join(self.out, "masks"))
        digests = {job[0]: job[10] for job in jobs}
        part = os.path.join(self.tmp.name, "records.jsonl.part")
        rows = [{"id": "verse001", "job_sha256": digests["verse001"]}, {"id": "verse002", "job_sha256": "0" * 64},
                {"id": "verse003", "job_sha256": "1" * 64}, {"id": "verse004", "error": "OSError: gone"}]
        with open(part, "w", encoding="ascii") as f:
            f.writelines(F.row_line(row) for row in rows)
            f.write('{"id": "verse005"')                                   # a line cut off
        self.assertEqual(C.keep_current(part, jobs), 3)
        self.assertEqual(F.rows_written(part), rows[:1])
        self.assertEqual(C.keep_current(os.path.join(self.tmp.name, "none.part"), jobs), 0)

    def test_a_job_s_digest_follows_the_bytes_it_reads(self):
        first = C.jobs_of(json.loads(read(self.jobs)), "masks")[0][10]
        study = self.studies["verse001"]
        save(study.spine, subregion_mask(stack(ids(FULL + ["sacrum"])), ids(FULL + ["sacrum"]), discs=[False]))
        self.assertNotEqual(C.jobs_of(json.loads(read(self.jobs)), "masks")[0][10], first)

    def test_a_second_run_reads_again_only_what_changed(self):
        os.makedirs(self.out)
        jobs = C.jobs_of(json.loads(read(self.jobs)), os.path.join(self.out, "masks"))
        part = os.path.join(self.out, "records.jsonl.part")
        with open(part, "w", encoding="ascii") as f:
            f.write(F.row_line({"id": "verse001", "job_sha256": "0" * 64, "stale": True}))
            f.write(F.row_line(dict(C.study_safe(jobs[1]), kept=True)))
        printed = self.run_main()
        self.assertIn("2 records (1 earlier rows read again", printed)
        records = [json.loads(line) for line in read(os.path.join(self.out, "records.jsonl"), "r").splitlines()]
        self.assertNotIn("stale", records[0])
        self.assertTrue(records[1]["kept"])


if __name__ == "__main__":
    unittest.main()
