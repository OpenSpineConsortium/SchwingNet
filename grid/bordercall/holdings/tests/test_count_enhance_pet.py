"""The ENHANCE.PET count's rules, on columns of boxes with chosen labels and gaps.

Run from the repository's root with `python -m unittest discover -s holdings/tests -t .`."""
import hashlib
import io
import json
import os
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from unittest import mock

import nibabel as nib
import numpy as np

from holdings import count_enhance_pet as C

SIDE = 12          # the synthetic field is SIDE x SIDE voxels in each slice
BODY = 8           # each body is BODY x BODY voxels in a slice: 64, so 4 slices pass the 200 floor
SLICES = 5         # slices per body
SLICE_MM = 2.0
ORIGIN_MM = -100.0
LEFT_X, RIGHT_X = [10, 11], [0, 1]   # where a rib lies beside a body, in the field's x

C1, C2, C3, C4, C5, C6, C7 = range(1, 8)
T1, T6, T7, T8, T9, T10, T11, T12 = 8, 13, 14, 15, 16, 17, 18, 19
L1, L2, L3, L4, L5, L6, SACRUM = 20, 21, 22, 23, 24, 25, 28
# A sacrum tall enough to keep 200 voxels when L4 sinks four slices into it.
TALL_SACRUM = (SACRUM, 10, 0)


def labels(first, last):
    return list(range(first, last + 1))


def column(levels, space=-1, margin_top=3, margin_bottom=3):
    """A mask of boxes stacked head to foot, z rising to the head.

    `levels` lists labels, or (label, slices, space below in slices) where the defaults do not fit.
    A space of -1 shares one slice with the next box, as consecutive levels overlap in a real
    column, and -n shares n slices; in shared slices the lower box takes half the body and the
    upper keeps the rest."""
    rows = [level if isinstance(level, tuple) else (level, SLICES, space) for level in levels]
    height = margin_top + margin_bottom + sum(n for _, n, _ in rows) + sum(s for _, _, s in rows[:-1])
    mask = np.zeros((SIDE, SIDE, height), np.uint8)
    top = height - 1 - margin_top
    low = (SIDE - BODY) // 2
    for i, (label, n, below) in enumerate(rows):
        bottom = top - n + 1
        mask[low:low + BODY, low:low + BODY, bottom:top + 1] = label
        shared = rows[i - 1][2] if i else 0
        if shared < 0:   # give the upper box back its half of the slices this box shares with it
            mask[low + BODY // 2:low + BODY, low:low + BODY, top + shared + 1:top + 1] = rows[i - 1][0]
        top = bottom - 1 - below
    return mask


def trimmed(mask, label, keep):
    """The mask with `label` cut down to its first `keep` voxels."""
    out = mask.copy()
    flat = out.reshape(-1)
    flat[np.flatnonzero(flat == label)[keep:]] = 0
    return out


def with_speck(mask, label, voxels):
    """The mask with its first `voxels` sacrum voxels relabelled `label`."""
    out = mask.copy()
    flat = out.reshape(-1)
    flat[np.flatnonzero(flat == SACRUM)[:voxels]] = label
    return out


def fragment_case():
    """L4 sinking 6 mm into a tall sacrum, and an L5 label of 208 voxels inside the sacrum's top,
    under a quarter of L4's 864: the no-L5 pattern with a sliver left behind."""
    mask = column(labels(C2, L3) + [(L4, 16, -4), (SACRUM, 16, 0)])
    low = (SIDE - BODY) // 2
    top = int(np.flatnonzero((mask == SACRUM).any(axis=(0, 1)))[-1])
    mask[low:low + 4, low:low + 4, top - 12:top + 1] = L5
    return mask


def affine_for(slice_mm=SLICE_MM):
    affine = np.diag([0.8, 0.8, slice_mm, 1.0])
    affine[2, 3] = ORIGIN_MM
    return affine


def save(mask, path, flip=False, slice_mm=SLICE_MM):
    affine = affine_for(slice_mm)
    if flip:   # stored foot first: the slice index runs down the patient
        mask = mask[:, :, ::-1]
        affine[2, 2] = -slice_mm
        affine[2, 3] = ORIGIN_MM + slice_mm * (mask.shape[2] - 1)
    nib.save(nib.Nifti1Image(np.ascontiguousarray(mask), affine), path)


STRICT = labels(C1, L5) + [SACRUM]
CASES = {
    "0001": column(STRICT),                                                     # strict, a control
    "0002": column(labels(C2, L6) + [SACRUM]),                                  # strict, an L6
    "0003": column(labels(C2, L3) + [(L4, 8, -4), TALL_SACRUM]),                # no L5, L4 6 mm into the sacrum
    "0004": column(labels(C2, L3) + [(L4, SLICES, 6), SACRUM]),                 # no L5 over a 14 mm space
    "0007": column(labels(C3, L5) + [SACRUM]),                                  # no C2
    "0008": column([C2, C3, C4, C6, C5] + labels(C7, L5) + [SACRUM]),           # C5 and C6 out of order
    "0009": column(labels(C2, L3) + [(L4, 8, -4), (L6, 8, -4), TALL_SACRUM]),   # no L5, an L6 in its place
    "0010": with_speck(column(labels(C2, L3) + [(L4, 8, -4), TALL_SACRUM]), L5, 32),  # L5 only a speck
    "0011": column(labels(C2, L5) + [SACRUM], margin_top=0),                    # C2 in the top slice
    "0012": column(labels(C2, L5)),                                             # no sacrum
    "0013": column(labels(C2, L3) + [(L4, 8, -3), TALL_SACRUM]),                # no L5, L4 4 mm into the sacrum
    "0014": column(labels(C2, L3) + [(L4, 8, -3), TALL_SACRUM]),                # the same at 2.5 mm: 5 mm in
    "0015": column(labels(C2, L2) + labels(L4, L5) + [SACRUM]),                 # L3 label missing
    "0016": column(labels(C2, T1) + [(T1 + 1, SLICES, 5)] + labels(T1 + 2, T6 - 1)     # 12 and 20 mm
                   + [(T6, SLICES, 9)] + labels(T7, L5) + [SACRUM]),                  # spaces
    "0017": trimmed(column(STRICT), L5, 199),                                   # L5 one voxel under the floor
    "0018": trimmed(column(STRICT), L5, 200),                                   # L5 at the floor
    "0019": fragment_case(),                                                    # L5 a fragment
    "0020": column(labels(C2, L4) + [(L5, SLICES, 10), SACRUM]),                # 22 mm from L5 to the sacrum
    "0021": column(labels(C2, T6 - 1) + [(T6, SLICES, 4)] + labels(T7, L5) + [SACRUM]),   # 10 mm space
    "1134": column([C2, C3, C4, C5, C6, C7] + labels(T1 + 1, L5) + [SACRUM]),   # T1 skipped
    "1283": column(labels(C2, T6 - 1) + [(T6, SLICES, 10)] + [T7, T8, T10, T9]  # 22 mm space, T9 and
                   + labels(T11, L5) + [SACRUM]),                               # T10 out of order
}
SLICE_OF = {"0014": 2.5}
FLIPPED = {"0011"}
AUTOPET, LEIPZIG = "AutoPET Challenge", "University Hospital Leipzig"
CAREGGI = "Azienda Ospedalierio Universitaria Careggi"
SITES = {sid: AUTOPET for sid in ("0001", "0002", "0003", "0004", "0008", "0010", "0013", "0014", "0015")}
SITES.update({sid: LEIPZIG for sid in ("0011", "0012", "0016", "0017", "1134", "1283")})
SITES.update({sid: CAREGGI for sid in ("0007", "0009", "0018", "0019", "0020", "0021")})
REPAIRED_MASKS = {
    "1134": column([C2, C3, C4, C5, C6, C7] + labels(T1, T11) + labels(L1, L5) + [SACRUM]),  # 11 thoracic
    "1283": column(labels(C2, L5) + [SACRUM]),
    "1347": column(labels(C2, L5) + [SACRUM]),
}


def sites_record(sites):
    return {"sites": sites, "short": {sid: C.short_site(raw) for sid, raw in sites.items()}, "blank_rows": 0}


def make_record(folder, masks, bad_hash=()):
    """A repair record: repaired/<id>.nii.gz and SHA256SUMS, with a wrong hash for `bad_hash`."""
    os.makedirs(os.path.join(folder, "repaired"))
    lines = []
    for sid, mask in sorted(masks.items()):
        path = os.path.join(folder, "repaired", sid + ".nii.gz")
        save(mask, path)
        with open(path, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        lines.append("%s  repaired/%s.nii.gz\n" % ("0" * 64 if sid in bad_hash else digest, sid))
    with open(os.path.join(folder, "SHA256SUMS"), "w") as handle:
        handle.writelines(lines)
    return folder


class Synthetic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.maskdir = os.path.join(cls.tmp.name, "masks")
        os.mkdir(cls.maskdir)
        for sid, mask in CASES.items():
            save(mask, os.path.join(cls.maskdir, sid + ".nii.gz"), flip=sid in FLIPPED,
                 slice_mm=SLICE_OF.get(sid, SLICE_MM))
        cls.record = make_record(os.path.join(cls.tmp.name, "record"), REPAIRED_MASKS)
        cls.extents = C.extents_step(cls.maskdir, workers=1)
        cls.repairs = C.read_repairs(cls.record)
        cls.count = C.count_step(cls.extents, sites_record(SITES), cls.repairs)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def cls_of(self, sid):
        return self.count["studies"][sid]["class"]

    def path(self, name):
        return os.path.join(self.tmp.name, name)


class Extents(Synthetic):
    def test_voxels_and_extents_in_world_mm(self):
        study = self.extents["studies"]["0001"]
        self.assertEqual(study["slice_mm"], SLICE_MM)
        self.assertEqual(study["voxels"]["1"], SLICES * BODY * BODY - (BODY // 2) * BODY)
        top_slice = CASES["0001"].shape[2] - 1 - 3
        low, high, n = study["extent_mm"]["1"]
        self.assertEqual(high, ORIGIN_MM + SLICE_MM * top_slice)
        self.assertEqual(low, ORIGIN_MM + SLICE_MM * (top_slice - SLICES + 1))
        self.assertEqual(n, SLICES)
        self.assertEqual(study["top_labels"], [])
        self.assertEqual(self.extents["studies"]["0011"]["top_labels"], [C2])

    def test_a_mask_stored_foot_first_reads_as_the_same_column(self):
        whole = column(labels(C2, L5) + [SACRUM], margin_top=0, margin_bottom=0)
        save(whole, self.path("up.nii.gz"))
        save(whole, self.path("down.nii.gz"), flip=True)
        upright, flipped = C.mask_extents(self.path("up.nii.gz")), C.mask_extents(self.path("down.nii.gz"))
        for key in ("extent_mm", "voxels", "top_labels", "bottom_labels"):
            self.assertEqual(upright[key], flipped[key], key)
        self.assertEqual(flipped["top_labels"], [C2])
        self.assertEqual(flipped["bottom_labels"], [SACRUM])

    def test_a_head_foot_axis_stored_first_is_counted_in_slabs(self):
        mask = column(STRICT)
        save(mask, self.path("last.nii.gz"))
        affine = np.zeros((4, 4))
        affine[0, 1], affine[1, 2], affine[2, 0], affine[2, 3], affine[3, 3] = 0.8, 0.8, SLICE_MM, ORIGIN_MM, 1
        nib.save(nib.Nifti1Image(np.ascontiguousarray(np.moveaxis(mask, 2, 0)), affine), self.path("first.nii.gz"))
        with mock.patch.object(C, "SLAB_SLICES", 5):   # the 12 stored slices come in three slabs
            first = C.mask_extents(self.path("first.nii.gz"))
        last = C.mask_extents(self.path("last.nii.gz"))
        self.assertEqual(first["slice_axis"], 0)
        for key in ("extent_mm", "voxels", "top_labels", "bottom_labels", "slice_mm", "tilt_mm"):
            self.assertEqual(first[key], last[key], key)

    def test_slabs_add_up_to_the_whole_mask(self):
        tall = column(STRICT * 3)
        save(tall, self.path("tall.nii.gz"))
        self.assertGreater(tall.shape[2], C.SLAB_SLICES)
        got = C.mask_extents(self.path("tall.nii.gz"))["voxels"]
        want = {str(label): int(n) for label, n in enumerate(np.bincount(tall.ravel())) if label and n}
        self.assertEqual(got, want)

    def test_voxels_outside_the_scheme_and_a_tilted_grid_are_reported(self):
        mask = np.zeros((10, 10, 10), np.uint8)
        mask[4:8, 4:8, 2:8] = C2
        mask[0, 0, 0], mask[1, 1, 1] = 29, 200
        affine = np.eye(4)
        affine[2, 0] = 0.1   # head-foot position moves 0.1 mm per column across a slice
        nib.save(nib.Nifti1Image(mask, affine), self.path("odd.nii.gz"))
        study = C.mask_extents(self.path("odd.nii.gz"))
        self.assertEqual(study["outside_scheme_voxels"], 2)
        self.assertEqual(study["tilt_mm"], 0.9)
        self.assertEqual(study["voxels"], {str(C2): 96})
        signed = mask.astype(np.int16)
        signed[2, 2, 2] = -3
        nib.save(nib.Nifti1Image(signed, np.eye(4)), self.path("signed.nii.gz"))
        self.assertEqual(C.mask_extents(self.path("signed.nii.gz"))["outside_scheme_voxels"], 3)

    def test_two_masks_of_one_study_are_refused(self):
        folder = self.path("twice")
        os.mkdir(folder)
        for name in ("0001.nii.gz", "0001.nii"):
            save(CASES["0001"], os.path.join(folder, name))
        with self.assertRaises(ValueError):
            C.mask_files(folder)


class Rules(Synthetic):
    def test_the_classes(self):
        lists = self.count["lists"]
        self.assertEqual(lists["strict"], ["0001", "0002", "0008", "0011", "0016", "0018", "0019", "0021"])
        self.assertEqual(lists["no_l5"], ["0003", "0009", "0010", "0014"])
        self.assertEqual(lists["lumbar_look"], ["0004", "0013", "0015", "0017", "0020"])
        self.assertEqual(lists["unlabelled_body"], ["1283"])
        self.assertEqual(lists["skipped_label"], ["1134"])
        self.assertEqual((lists["no_c2"], lists["no_sacrum"]), (["0007"], ["0012"]))
        self.assertEqual(lists["whole"], sorted(lists["strict"] + lists["no_l5"] + lists["lumbar_look"]))
        self.assertEqual(lists["gold_3"], lists["whole"])

    def test_an_l6_is_whole_and_a_variant(self):
        self.assertEqual(self.cls_of("0002"), "strict")
        self.assertEqual(self.count["lists"]["l6"], ["0002", "0009"])
        self.assertEqual(self.count["studies"]["0002"]["variants"], ["L6 named"])

    def test_no_l5_whose_l4_sinks_into_the_sacrum_is_whole(self):
        row = self.count["studies"]["0003"]
        self.assertEqual(row["class"], "no_l5")
        self.assertEqual(row["lumbosacral_gap_mm"], -6.0)
        self.assertEqual(row["links_from_l4"], [["L4", "sacrum", -6.0]])
        self.assertEqual(row["variants"], ["no L5 label, L4 meeting the sacrum"])
        self.assertEqual(self.count["gaps"]["no_l5_l4_to_sacrum_mm"], {"0003": -6.0, "0010": -6.0, "0014": -5.0})

    def test_the_no_l5_bound_at_its_edge(self):
        self.assertEqual(self.count["studies"]["0014"]["l4_to_sacrum_mm"], -5.0)
        self.assertEqual(self.cls_of("0014"), "no_l5")
        self.assertEqual(self.count["studies"]["0013"]["l4_to_sacrum_mm"], -4.0)
        self.assertEqual(self.cls_of("0013"), "lumbar_look")

    def test_no_l5_over_a_real_space_is_whole_and_listed_for_a_look(self):
        self.assertEqual(self.cls_of("0004"), "lumbar_look")
        self.assertIn("0004", self.count["lists"]["whole"])
        self.assertEqual(self.count["studies"]["0004"]["variants"],
                         ["no L5 label, L4-to-sacrum gap 14.0 mm: may hold an unlabelled L5, look"])

    def test_a_missing_lumbar_label_is_whole_and_listed_for_a_look(self):
        self.assertEqual(self.cls_of("0015"), "lumbar_look")
        self.assertEqual(self.count["studies"]["0015"]["variants"], ["L3 label missing: look"])

    def test_a_wide_lumbar_space_is_whole_and_listed_for_a_look(self):
        self.assertEqual(self.cls_of("0020"), "lumbar_look")
        self.assertEqual(self.count["studies"]["0020"]["variants"],
                         ["a space of 22.0 mm between L5 and sacrum: may hold an unlabelled body, look"])

    def test_a_space_that_holds_a_body_above_t12_is_left_out(self):
        self.assertEqual(self.cls_of("1283"), "unlabelled_body")
        self.assertEqual(self.count["studies"]["1283"]["wide_gaps"], [["T6", "T7", 22.0]])

    def test_the_unlabelled_body_bound_at_its_edge(self):
        row = self.count["studies"]["0016"]
        self.assertEqual(row["class"], "strict")
        self.assertEqual(row["look_gaps"], [["T2", "T3", 12.0], ["T6", "T7", 20.0]])
        self.assertEqual(row["variants"], ["a space of 12.0 mm between T2 and T3: look",
                                           "a space of 20.0 mm between T6 and T7: look"])
        self.assertEqual(self.count["lists"]["look_gaps"], ["0016"])

    def test_the_look_bound_at_its_edge(self):
        row = self.count["studies"]["0021"]
        self.assertEqual(row["class"], "strict")
        self.assertEqual((row["look_gaps"], row["variants"]), ([], []))
        self.assertEqual(C.gap_mm(self.extents["studies"]["0021"]["extent_mm"], T6, T7), 10.0)

    def test_a_wide_space_is_lumbar_from_t12_down(self):
        self.assertEqual(C.class_of([], [[T12, L1, 22.0]], []), "lumbar_look")
        self.assertEqual(C.class_of([], [[T11, T12, 22.0]], []), "unlabelled_body")
        self.assertEqual(C.class_of([L1], [], []), "lumbar_look")
        self.assertEqual(C.class_of([T12], [], []), "skipped_label")

    def test_a_skipped_label_above_l1_is_left_out(self):
        self.assertEqual(self.cls_of("1134"), "skipped_label")
        self.assertEqual(self.count["studies"]["1134"]["missing"], ["T1"])

    def test_out_of_order_extents_are_reported_not_excluded(self):
        self.assertEqual(self.cls_of("0008"), "strict")
        self.assertEqual(self.count["studies"]["0008"]["out_of_order"], [["C5", "C6"]])
        self.assertEqual(self.count["lists"]["out_of_order"], ["0008"])
        self.assertEqual(self.count["studies"]["1283"]["out_of_order"], [["T9", "T10"]])
        self.assertEqual(self.count["lists"]["out_of_order_left_out"], ["1283"])

    def test_an_l6_in_the_place_of_l5_is_whole(self):
        self.assertEqual(self.cls_of("0009"), "no_l5")
        self.assertEqual(self.count["studies"]["0009"]["variants"], ["no L5 label, an L6 in its place"])
        self.assertEqual(self.count["gaps"]["no_l5_l6_in_its_place"], ["0009"])

    def test_a_speck_is_no_label(self):
        self.assertLess(self.extents["studies"]["0010"]["voxels"][str(L5)], C.MIN_VOXELS)
        self.assertEqual(self.cls_of("0010"), "no_l5")

    def test_the_voxel_floor_at_its_edge(self):
        self.assertEqual(self.extents["studies"]["0017"]["voxels"][str(L5)], 199)
        self.assertEqual(self.cls_of("0017"), "lumbar_look")
        self.assertEqual(self.count["studies"]["0017"]["variants"],
                         ["no L5 label, L4-to-sacrum gap 8.0 mm: may hold an unlabelled L5, look"])
        self.assertEqual(self.extents["studies"]["0018"]["voxels"][str(L5)], 200)
        self.assertEqual(self.cls_of("0018"), "strict")

    def test_an_l5_fragment_over_an_l4_meeting_the_sacrum_is_strict_and_listed(self):
        voxels = self.extents["studies"]["0019"]["voxels"]
        self.assertEqual((voxels[str(L5)], voxels[str(L4)]), (208, 864))
        self.assertEqual(self.cls_of("0019"), "strict")
        self.assertEqual(self.count["lists"]["l5_fragment"], ["0019"])
        self.assertEqual(self.count["studies"]["0019"]["variants"],
                         ["L5 label a fragment, L4 meeting the sacrum: look"])

    def test_the_fragment_share_at_its_edge(self):
        study = {"voxels": {str(L4): 1000, str(L5): 249, str(SACRUM): 1000},
                 "extent_mm": {str(L4): [0.0, 20.0, 9], str(SACRUM): [-30.0, 6.0, 15]}}
        present = {L4, L5, SACRUM}
        self.assertTrue(C.l5_fragment(study, present))
        study["voxels"][str(L5)] = 250
        self.assertFalse(C.l5_fragment(study, present))

    def test_the_no_l5_rule_leak_is_counted(self):
        # Of the strict spines with no L6, only 0019's L4 overlaps the sacrum by 5 mm or more.
        self.assertEqual(self.count["gaps"]["no_l5_rule_leak"], {"passing": 1, "of": 7})

    def test_c2_in_the_top_slice_is_reported_from_a_mask_stored_foot_first(self):
        self.assertEqual(self.count["lists"]["c2_in_top_slice"], ["0011"])


class Repair(Synthetic):
    def test_the_repaired_masks_are_read_and_counted_whole(self):
        lists = self.count["lists"]
        self.assertEqual(lists["left_out"], ["1134", "1283"])
        self.assertEqual(lists["repaired"], ["1134", "1283"])
        self.assertEqual(lists["left_out_not_repaired"], [])
        self.assertEqual(lists["repair_record_not_left_out"], ["1347"])
        self.assertEqual(set(lists["whole_after_repair"]) - set(lists["whole"]), {"1134", "1283"})
        self.assertNotIn("1283", lists["whole_after_repair_readers_voxels"])
        self.assertIn("1134", lists["whole_after_repair_readers_voxels"])
        found = self.repairs["studies"]
        self.assertEqual((found["1134"]["class"], found["1134"]["missing"]), ("skipped_label", ["T12"]))
        self.assertTrue(all(found[sid]["matches_record"] for sid in found))

    def test_a_repaired_mask_that_does_not_read_as_the_record_says_is_not_counted(self):
        masks = dict(REPAIRED_MASKS, **{"1134": REPAIRED_MASKS["1283"]})   # twelve thoracic, not eleven
        repairs = C.read_repairs(make_record(self.path("wrong"), masks))
        count = C.count_step(self.extents, sites_record(SITES), repairs)
        self.assertEqual(count["lists"]["repair_does_not_match_record"], ["1134"])
        self.assertNotIn("1134", count["lists"]["whole_after_repair"])
        self.assertEqual(count["lists"]["left_out_not_repaired"], ["1134"])

    def test_a_missing_or_changed_repaired_mask_fails_the_count(self):
        missing = {sid: mask for sid, mask in REPAIRED_MASKS.items() if sid != "1347"}
        with self.assertRaises(C.RepairRecordError):
            C.read_repairs(make_record(self.path("short"), missing))
        with self.assertRaises(C.RepairRecordError):
            C.read_repairs(make_record(self.path("changed"), REPAIRED_MASKS, bad_hash={"1283"}))
        with self.assertRaises(C.RepairRecordError):
            C.read_repairs(self.path("nowhere"))

    def test_counts_by_site_and_persons(self):
        by_site = self.count["by_site"]
        self.assertEqual(by_site["whole"], {"autoPET": 9, "Leipzig": 3, "Careggi": 5})
        self.assertEqual(by_site["whole_after_repair"], {"autoPET": 9, "Leipzig": 5, "Careggi": 5})
        self.assertEqual(self.count["autopet_studies"], 9)
        self.assertEqual(self.count["persons"]["autopet_whole"], [9, 9])
        self.assertEqual(self.count["persons"]["other_sites_whole_at_most"], 8)
        self.assertEqual(self.count["persons"]["gold_3"], [9, 17])

    def test_contact_groups(self):
        ids = self.count["rib_contact_ids"]
        self.assertEqual(ids["variants"], ["0002", "0003", "0004", "0009", "0010", "0013", "0014", "0015",
                                           "0016", "0017", "0019", "0020"])
        self.assertEqual(ids["controls"], ["0001", "0008", "0011", "0018", "0021"])

    def test_autopet_persons(self):
        self.assertEqual(C.autopet_persons(979, 1014), [865, 900])
        self.assertEqual(C.autopet_persons(50, 1014), [0, 50])


def rib_mask(mask, plan):
    """Ribs placed beside the slices where a label stands alone: plan maps (side, rib) to the label
    it lies beside, or to FAR for a rib well clear of the spine."""
    ribs = np.zeros(mask.shape, np.uint8)
    for (side, rib), label in sorted(plan.items()):
        value = rib + (C.LEFT_RIB_BASE if side == "left" else C.RIGHT_RIB_BASE)
        if label == FAR:   # the bottom two slices, at least 4 mm below the lowest body
            ribs[6:SIDE, :, 0:2] = value
            continue
        alone = [z for z in range(mask.shape[2]) if set(np.unique(mask[:, :, z])) - {0} == {label}]
        columns = LEFT_X if side == "left" else RIGHT_X
        ribs[np.ix_(columns, range(SIDE), alone)] = value
    return ribs


FAR = "far"


def own_plan(mask, shift=0, sides=("left", "right")):
    present = set(np.unique(mask))
    return {(side, rib): rib + C.OWN_VERTEBRA_OFFSET + shift for side in sides for rib in range(1, 13)
            if rib + C.OWN_VERTEBRA_OFFSET + shift in present}


def rib_plan(sid, mask):
    plan = own_plan(mask)
    if sid == "0002":          # thirteen ribs, the thirteenth on L1
        plan.update({("left", 13): L1, ("right", 13): L1})
    elif sid == "0003":        # every left rib one level up
        plan = {**own_plan(mask, sides=("right",)), **own_plan(mask, shift=-1, sides=("left",))}
    elif sid == "0009":        # no right rib 12
        del plan[("right", 12)]
    elif sid == "0019":        # the left rib 12 clear of the spine
        plan[("left", 12)] = FAR
    return plan


class RibCommandLine(Synthetic):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ribdir = os.path.join(cls.tmp.name, "ribs")
        os.mkdir(cls.ribdir)
        for sid, mask in CASES.items():
            ribs = rib_mask(mask, rib_plan(sid, mask))
            if sid == "0008":   # one slice more than its vertebra mask: another grid
                ribs = np.concatenate([ribs, np.zeros(ribs.shape[:2] + (1,), np.uint8)], axis=2)
            save(ribs, os.path.join(cls.ribdir, sid + ".nii.gz"), flip=sid in FLIPPED,
                 slice_mm=SLICE_OF.get(sid, SLICE_MM))
        out = os.path.join(cls.tmp.name, "out")
        cls.files = {name: os.path.join(out, name + ".json") for name in ("count", "pairs", "contacts")}
        C.write(cls.count, cls.files["count"])
        with redirect_stdout(io.StringIO()):
            C.main(["ribs", cls.maskdir, cls.ribdir, "all", cls.files["pairs"], "--pairs-only", "--workers", "1"])
            C.main(["ribs", cls.maskdir, cls.ribdir, cls.files["count"], cls.files["contacts"], "--workers", "1"])
        cls.pairs, cls.contacts = C.load(cls.files["pairs"]), C.load(cls.files["contacts"])

    def printed(self, *ribs):
        text = io.StringIO()
        with redirect_stdout(text):
            C.main(["report", self.files["count"]] + [self.files[name] for name in ribs])
        return text.getvalue()

    def test_the_report_is_the_same_whichever_rib_file_comes_first(self):
        self.assertEqual(self.printed("pairs", "contacts"), self.printed("contacts", "pairs"))

    def test_the_pairs_table_counts_every_study_and_the_whole_apart(self):
        text = self.printed("pairs", "contacts")
        self.assertIn("| Rib pairs | Studies read (21) | Whole after repair (19) |", text)
        self.assertIn("| 11 | 2 | 2 |", text)
        self.assertIn("| 12 | 18 | 16 |", text)
        self.assertIn("| 13 | 1 | 1 |", text)
        self.assertIn("1 study has different ribs on the two sides", text)
        self.assertIn("0009 (left 1-12, right 1-11)", text)

    def test_the_contact_table_pairs_each_rib_with_the_label_it_meets(self):
        text = self.printed("pairs", "contacts")
        self.assertIn("| Lowest rib meets | controls | no L5 label, L4 meeting the sacrum | no L5 label, an L6 in its "
                      "place | L6 named below an L5 | lumbar label missing or lumbar space, look | L5 label a "
                      "fragment, L4 meeting the sacrum | left out, repaired |", text)
        self.assertIn("| rib 12 on T12 | 4 | 2 | 0 | 0 | 5 | 1 | 2 |", text)
        self.assertIn("| rib 13 on L1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |", text)
        self.assertIn("| rib 11 on T11 on one side, rib 12 on T12 on the other | 0 | 0 | 1 | 0 | 0 | 0 | 0 |", text)
        self.assertIn("| a label one level off | 0 | 1 | 0 | 0 | 0 | 0 | 0 |", text)
        self.assertIn("| masks unreadable | 1 | 0 | 0 | 0 | 0 | 0 | 0 |", text)
        self.assertIn("| Studies | 5 | 3 | 1 | 1 | 5 | 1 | 2 |", text)

    def test_every_study_off_its_own_level_or_unread_is_named(self):
        text = self.printed("pairs", "contacts")
        self.assertIn("0008 (the vertebra and rib masks lie on different grids)", text)
        self.assertIn("0003 (left rib 12 on T11, right rib 12 on T12)", text)
        self.assertIn("0009 (left rib 12 on T12, right rib 11 on T11)", text)
        self.assertIn("0019 (left rib 12 meets nothing within 3.0 mm, right rib 12 on T12)", text)

    def test_a_group_read_only_in_part_is_left_out_and_said_to_be(self):
        partial = json.loads(json.dumps(self.contacts))
        del partial["studies"]["0011"]["contacts"]
        text = C.report(self.count, C.merge_ribs([self.pairs, partial]))
        self.assertIn("- controls: 4 of 5 studies tallied, so the group is left out of the table.", text)
        self.assertNotIn("| Lowest rib meets | controls |", text)

    def test_the_repaired_table_reads_the_repaired_masks(self):
        text = self.printed("pairs", "contacts")
        self.assertIn("| 1134 | Leipzig | skipped label (T1) |", text)
        self.assertIn("| T12 absent: an 11-thoracic count variant; 11 rib pairs | the readers' voxels, names moved "
                      "by a rule the ribs settle | gold 4 until a person checks it |", text)


class Ribs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        for sub in ("masks", "ribs"):
            os.mkdir(os.path.join(self.tmp.name, sub))

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, sid, vert, rib, ending=".nii.gz"):
        affine = np.eye(4)
        nib.save(nib.Nifti1Image(vert, affine), os.path.join(self.tmp.name, "masks", sid + ending))
        nib.save(nib.Nifti1Image(rib, affine), os.path.join(self.tmp.name, "ribs", sid + ending))

    def study(self, sid, contacts):
        return C.rib_study((sid, os.path.join(self.tmp.name, "masks"), os.path.join(self.tmp.name, "ribs"),
                            contacts))[1]

    def test_rib_pairs_and_the_lowest_rib(self):
        rib = np.zeros((30, 30, 30), np.uint8)
        for k in range(1, 13):
            rib[2:12, k, 2:7] = k                 # left ribs 1 to 12, 50 voxels each
        for k in range(1, 12):
            rib[15:25, k, 2:7] = 13 + k           # right ribs 1 to 11
        rib[2:4, 20, 2:7] = 13                    # left rib 13: 10 voxels, a speck
        self.write("0001", np.zeros_like(rib), rib)
        row = self.study("0001", contacts=False)
        self.assertEqual(row["left"], list(range(1, 13)))
        self.assertEqual(row["right"], list(range(1, 12)))
        self.assertEqual(row["pairs"], 11)
        self.assertTrue(row["asymmetric"])
        self.assertEqual(row["lowest"], {"left": 12, "right": 11})

    def test_the_tally_chooses_the_ribs_own_vertebra_over_the_one_its_head_touches(self):
        vert = np.zeros((40, 30, 30), np.uint8)
        vert[10:17, 10:17, 14:20] = T11
        vert[10:17, 10:17, 6:12] = T12            # a disc between them at z 12 and 13
        rib = np.zeros_like(vert)
        rib[17, 12:14, 14] = 12                   # left rib 12's head touches T11
        rib[17, 10:17, 8:10] = 12                 # its neck and tubercle lie along T12
        rib[18:38, 12:15, 8] = 12                 # the shaft runs off away from the spine
        self.write("0002", vert, rib)
        side = self.study("0002", contacts=True)["contacts"]["left"]
        self.assertEqual(side["lowest_rib"], 12)
        self.assertGreater(side["contacts"][str(T11)], 0)
        self.assertEqual(side["meets"], T12)
        self.assertEqual(side["meets_name"], "T12")
        self.assertFalse(side["tie"])

    def test_the_contact_distance_at_its_edge(self):
        vert = np.zeros((30, 30, 30), np.uint8)
        vert[10:17, 10:17, 18:24] = T11
        vert[10:17, 10:17, 4:10] = T12
        rib = np.zeros(vert.shape, bool)
        rib[17, 10:15, 6:8] = True                # 10 voxels 1 mm from T12
        rib[19, 10:16, 20] = True                 # 6 voxels exactly 3 mm from T11: counted
        rib[20, 10:16, 19:24] = True              # 30 voxels 4 mm from T11: not counted
        self.assertEqual(C.contact_tally(vert, rib, np.ones(3)), {T11: 6, T12: 10})

    def test_a_tie_goes_head_most_and_is_marked(self):
        self.assertEqual(C.meeting({T12: 5, T11: 5, 20: 1}), (T11, True))
        self.assertEqual(C.meeting({}), (None, False))

    def test_masks_on_different_grids_are_refused(self):
        rib = np.zeros((20, 20, 20), np.uint8)
        rib[2:12, 3, 2:7] = 12
        self.write("0003", np.zeros((20, 20, 21), np.uint8), rib)
        self.assertIn("error", self.study("0003", contacts=True)["contacts"])

    def test_uncompressed_masks_are_read(self):
        vert = np.zeros((20, 20, 20), np.uint8)
        vert[5:10, 5:10, 5:10] = T12
        rib = np.zeros_like(vert)
        rib[10, 5:10, 5:10] = 12                  # left rib 12, 25 voxels beside T12, and 25 more
        rib[11, 5:10, 5:10] = 12
        self.write("0004", vert, rib, ending=".nii")
        row = self.study("0004", contacts=True)
        self.assertEqual(row["left"], [12])
        self.assertEqual(row["contacts"]["left"]["meets"], T12)


class Sites(unittest.TestCase):
    def test_the_study_table_is_read_without_a_spreadsheet_library(self):
        main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
        rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        pkg = "http://schemas.openxmlformats.org/package/2006/relationships"
        strings = ["Patient", "Data-Source", "0001", "AutoPET Challenge", "0002",
                   "Azienda Ospedalierio Universitaria Careggi"]
        sst = '<sst xmlns="%s">%s</sst>' % (main, "".join("<si><t>%s</t></si>" % s for s in strings))
        cell = '<c r="%s" t="s"><v>%d</v></c>'
        sheet = ('<worksheet xmlns="%s"><sheetData>'
                 '<row r="1">%s%s</row><row r="2">%s%s</row><row r="3">%s%s</row>'
                 '<row r="4"><c r="A4" t="inlineStr"><is><t>0003</t></is></c>'
                 '<c r="B4" t="inlineStr"><is><t>University Hospital Leipzig</t></is></c></row>'
                 '<row r="5"><c r="C5"/></row></sheetData></worksheet>'
                 % (main, cell % ("A1", 0), cell % ("B1", 1), cell % ("A2", 2), cell % ("B2", 3),
                    cell % ("A3", 4), cell % ("B3", 5)))
        book = ('<workbook xmlns="%s" xmlns:r="%s"><sheets><sheet name="S" sheetId="1" r:id="rId2"/>'
                '</sheets></workbook>' % (main, rel))
        rels = ('<Relationships xmlns="%s"><Relationship Id="rId2" Target="worksheets/sheet1.xml" '
                'Type="x"/></Relationships>' % pkg)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "t.xlsx")
            with zipfile.ZipFile(path, "w") as book_file:
                book_file.writestr("xl/workbook.xml", book)
                book_file.writestr("xl/_rels/workbook.xml.rels", rels)
                book_file.writestr("xl/sharedStrings.xml", sst)
                book_file.writestr("xl/worksheets/sheet1.xml", sheet)
            got = C.sites_step(path)
        self.assertEqual(got["header"], ["Patient", "Data-Source"])
        self.assertEqual(got["short"], {"0001": "autoPET", "0002": "Careggi", "0003": "Leipzig"})
        self.assertEqual(got["blank_rows"], 1)


class CommandLine(Synthetic):
    def test_each_step_writes_json_and_the_report_prints_the_table(self):
        out = self.path("cli")
        sites = os.path.join(out, "sites.json")
        C.write(sites_record(SITES), sites)
        with redirect_stdout(io.StringIO()):
            C.main(["extents", self.maskdir, os.path.join(out, "extents.json"), "--workers", "1"])
            C.main(["count", os.path.join(out, "extents.json"), sites, os.path.join(out, "count.json"),
                    "--repair-record", self.record])
        written = C.load(os.path.join(out, "count.json"))
        self.assertEqual(written["lists"]["whole"], self.count["lists"]["whole"])
        printed = io.StringIO()
        with redirect_stdout(printed):
            C.main(["report", os.path.join(out, "count.json")])
        text = printed.getvalue()
        self.assertIn("| **Whole C2 to sacrum, published labels** | 9 | 3 | 5 | 17 |", text)
        self.assertIn("| **Gold 3: the readers' labels as published** | 9 | 3 | 5 | 17 |", text)
        self.assertIn("| **Whole after repair** | 9 | 5 | 5 | 19 |", text)
        self.assertIn("| of which keep the readers' voxels (1134 and 1347 under names a rule moved) | 9 | 4 | 5 | 18 |",
                      text)
        self.assertIn("| Whole with out-of-order extents, not excluded | 1 | 0 | 0 | 1 |", text)
        self.assertIn("| Left out, out of order in the published mask | 0 | 1 | 0 | 1 |", text)
        self.assertIn("- No L5 label, L4 meeting the sacrum: 3 studies, L4-to-sacrum gaps from -6.0 to -5.0 mm "
                      "(median -6.0).", text)
        self.assertIn("1 of the 7 strict spines with no L6 would pass it", text)
        self.assertIn("- Gold 3 from this set: 9 to 17 persons", text)
        self.assertIn("- 0015: L3 label missing: look.", text)

    def test_a_study_the_table_does_not_name_gets_its_own_column(self):
        sites = {sid: site for sid, site in SITES.items() if sid != "0001"}
        count = C.count_step(self.extents, sites_record(sites), self.repairs)
        text = C.report(count, {"studies": {}, "groups": {}})
        self.assertIn("| | autoPET | Leipzig | Careggi | unknown | All |", text)
        self.assertIn("| **Whole C2 to sacrum, published labels** | 8 | 3 | 5 | 1 | 17 |", text)
        self.assertIn("counted under unknown: 0001.", text)


if __name__ == "__main__":
    unittest.main()
