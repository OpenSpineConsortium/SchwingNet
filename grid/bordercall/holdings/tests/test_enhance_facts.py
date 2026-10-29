"""The ENHANCE.PET facts, on small synthetic masks written to a temporary folder.

The columns, the rib plans and the repair record come from the count's own tests, so the facts are
read on the same toy spines the count is. Run from the repository's root with
`python -m unittest discover -s holdings/tests -t .`."""
import io
import json
import os
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout

import nibabel as nib
import numpy as np
from scipy import ndimage

from holdings import count_enhance_pet as C
from holdings import enhance_facts as F
from holdings.tests import test_count_enhance_pet as T

T11, T12, L4, L5, SACRUM = 18, 19, 23, 24, 28
BLANK = {"cells": {}, "listed_bytes": None, "ribs_listed_bytes": None}
# touch.py's box around the two labels, in mm.
TOUCH_MARGIN_MM = 60.0


def touch_mm(mask, zooms, a, b):
    """The repair record's touch.py: the least of the distance map to label b over label a's
    voxels, in a box 60 mm around both."""
    idx = np.argwhere((mask == a) | (mask == b))
    pad = np.ceil(TOUCH_MARGIN_MM / zooms).astype(int)
    low = np.maximum(idx.min(0) - pad, 0)
    high = np.minimum(idx.max(0) + pad + 1, mask.shape)
    sub = mask[low[0]:high[0], low[1]:high[1], low[2]:high[2]]
    dist = ndimage.distance_transform_edt(sub != b, sampling=zooms)
    return round(float(dist[sub == a].min()), 1)


def save_pair(folder, sid, vert, rib, affine):
    paths = []
    for sub, mask in (("masks", vert), ("ribs", rib)):
        os.makedirs(os.path.join(folder, sub), exist_ok=True)
        path = os.path.join(folder, sub, sid + ".nii.gz")
        nib.save(nib.Nifti1Image(np.ascontiguousarray(mask), affine), path)
        paths.append(path)
    return paths


def column_and_ribs(plan=T.own_plan):
    mask = T.column(T.STRICT)
    return mask, T.rib_mask(mask, plan(mask))


class Folder(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def facts(self, vert, rib=None, affine=None, sid="0001"):
        affine = T.affine_for() if affine is None else affine
        rib = np.zeros_like(vert) if rib is None else rib
        vert_path, rib_path = save_pair(self.tmp.name, sid, vert, rib, affine)
        return F.study_facts((sid, vert_path, rib_path, BLANK))[1]


class Blocks(Folder):
    def test_blocks_are_the_files_own_and_cross_slabs(self):
        rng = np.random.default_rng(7)
        mask = rng.integers(-1, 31, size=(9, 7, 2 * C.SLAB_SLICES + 6)).astype(np.int16)
        mask[rng.random(mask.shape) < 0.6] = 0
        path = os.path.join(self.tmp.name, "blocks.nii.gz")
        nib.save(nib.Nifti1Image(mask, np.eye(4)), path)
        img = nib.load(path)
        voxels = F.LabelledVoxels(img)
        boxes = [(slice(None),) * 3, (slice(2, 7), slice(0, 3), slice(30, 40)),
                 (slice(0, 1), slice(None), slice(C.SLAB_SLICES - 1, C.SLAB_SLICES + 1)), (slice(3, 3),) * 3]
        for box in boxes:
            block = voxels[box]
            self.assertEqual(block.dtype, np.asanyarray(img.dataobj[box]).dtype)
            np.testing.assert_array_equal(block, np.asanyarray(img.dataobj[box]))
        np.testing.assert_array_equal(np.sort(voxels.label_points(5), axis=0), np.sort(np.argwhere(mask == 5), axis=0))

    def test_a_block_with_a_step_is_refused(self):
        img = nib.Nifti1Image(np.ones((4, 4, 4), np.uint8), np.eye(4))
        with self.assertRaises(ValueError):
            F.LabelledVoxels(img)[slice(None), slice(None), slice(0, 4, 2)]

    def test_two_reads_that_disagree_are_a_bug(self):
        img = nib.Nifti1Image(np.full((2, 2, 2), 3, np.uint8), np.eye(4))
        counts, _ = C.slice_counts(img, 2, C.TOP_VERTEBRA_LABEL)
        counts[0, 3] += 1
        with self.assertRaises(RuntimeError):
            F.check_reads_agree("x", counts, F.LabelledVoxels(img), C.TOP_VERTEBRA_LABEL)


class Labels(Folder):
    def test_voxels_extents_and_centroid(self):
        mask = T.column(T.STRICT)
        row = self.facts(mask)
        extents = C.mask_extents(os.path.join(self.tmp.name, "masks", "0001.nii.gz"))["extent_mm"]
        affine = T.affine_for()
        self.assertEqual(sorted(row["labels"], key=int), [str(label) for label in T.STRICT])
        for label in T.STRICT:
            fact = row["labels"][str(label)]
            self.assertEqual(fact["voxels"], int((mask == label).sum()))
            self.assertEqual([fact["bottom_mm"], fact["top_mm"]], [round(x, 1) for x in extents[str(label)][:2]])
            centre = affine[:3, :3] @ np.argwhere(mask == label).mean(0) + affine[:3, 3]
            self.assertEqual(fact["centroid_mm"], [round(float(x), 1) for x in centre])
        self.assertEqual(row["mask"]["head_foot_axis"], 2)
        self.assertEqual(row["mask"]["axcodes"], "RAS")
        self.assertEqual(row["mask"]["zooms"], [0.8, 0.8, 2.0])

    def test_a_flipped_affine_reads_the_same_column(self):
        mask = T.column(T.STRICT)
        upright = self.facts(mask)
        flipped = T.affine_for()
        flipped[2, 2] = -T.SLICE_MM
        flipped[2, 3] = T.ORIGIN_MM + T.SLICE_MM * (mask.shape[2] - 1)
        stored_foot_first = self.facts(np.ascontiguousarray(mask[:, :, ::-1]), affine=flipped, sid="0002")
        self.assertEqual(stored_foot_first["labels"], upright["labels"])
        self.assertEqual(stored_foot_first["mask"]["axcodes"], "RAI")
        top, bottom = upright["labels"][str(T.C2)], upright["labels"][str(SACRUM)]
        self.assertGreater(top["bottom_mm"], bottom["top_mm"])
        self.assertGreater(top["top_mm"], top["bottom_mm"])

    def test_pieces_and_the_largest_share(self):
        mask = np.zeros((16, 16, 16), np.uint8)
        mask[2:6, 2:6, 2:6] = L4             # 64 voxels
        mask[10:12, 10:12, 2:6] = L4         # 16 more, apart
        mask[14, 14, 14] = L4                # and one more, apart: the share is 64 / 81
        mask[2:4, 10:12, 10:12] = L5         # two cubes of 8 meeting only at a corner: one piece
        mask[4:6, 12:14, 12:14] = L5
        labels = self.facts(mask)["labels"]
        self.assertEqual((labels[str(L4)]["components"], labels[str(L4)]["largest_share"]), (3, 0.7901))
        self.assertEqual((labels[str(L5)]["components"], labels[str(L5)]["largest_share"]), (1, 1.0))

    def test_a_slice_centre_is_rounded_once(self):
        mask = np.zeros((6, 6, 4), np.uint8)
        mask[1:4, 1:4, 0] = L4
        affine = T.affine_for()
        affine[2, 3] = -118.0505             # the file keeps it as -118.05049896...
        fact = self.facts(mask, affine=affine)["labels"][str(L4)]
        # Rounded to 0.001 mm first, as the count writes it, the centre would read -118.0.
        self.assertEqual((fact["bottom_mm"], fact["top_mm"]), (-118.1, -118.1))

    def test_the_centroid_is_in_the_world_of_a_turned_grid(self):
        mask = T.column(T.STRICT)
        turned = np.array([[0.0, -0.9, 0.0, 40.02], [0.7, 0.0, 0.0, -20.03],
                           [0.0, 0.0, T.SLICE_MM, T.ORIGIN_MM], [0.0, 0.0, 0.0, 1.0]])
        row = self.facts(mask, affine=turned)
        written = nib.load(os.path.join(self.tmp.name, "masks", "0001.nii.gz")).affine   # in single precision
        self.assertEqual(row["mask"]["axcodes"], "ALS")
        for label in (T.C2, L4, SACRUM):
            centre = nib.affines.apply_affine(written, np.argwhere(mask == label)).mean(0)
            self.assertEqual(row["labels"][str(label)]["centroid_mm"], [round(float(x), 1) for x in centre])

    def test_a_grid_whose_head_foot_axis_is_stored_first_reads_the_same_spine(self):
        mask, ribs = column_and_ribs()
        upright = self.facts(mask, ribs)
        stored = np.zeros((4, 4))
        stored[2, 0], stored[1, 1], stored[0, 2] = T.SLICE_MM, 0.8, 0.8   # the same world as upright
        stored[2, 3], stored[3, 3] = T.ORIGIN_MM, 1.0
        first = self.facts(np.ascontiguousarray(mask.transpose(2, 1, 0)), np.ascontiguousarray(ribs.transpose(2, 1, 0)),
                           affine=stored, sid="0002")
        self.assertEqual(first["mask"]["head_foot_axis"], 0)
        for key in ("labels", "ribs", "distances_mm", "sternum_voxels", "outside_scheme_voxels"):
            self.assertEqual(first[key], upright[key], key)

    def test_voxels_outside_either_scheme(self):
        vert = np.zeros((8, 8, 8), np.int16)
        vert[1:3, 1:3, 1:3] = L4
        vert[5, 5, 5:7] = 29                 # past the sacrum, the vertebra scheme's top label
        vert[6, 6, 6] = -1
        vert[0, 7, 0:2] = 26                 # a hip, in the scheme
        rib = np.zeros((8, 8, 8), np.uint8)
        rib[7, 0, 0:2] = C.TOP_RIB_LABEL     # the sternum, in the scheme
        rib[7, 7, 7] = C.TOP_RIB_LABEL + 1
        row = self.facts(vert, rib, affine=np.eye(4))
        self.assertEqual(row["outside_scheme_voxels"], {"vertebrae": 3, "ribs": 1})
        self.assertEqual(row["sternum_voxels"], 2)


class Distances(Folder):
    def test_two_labels_a_known_gap_apart(self):
        mask = np.zeros((12, 12, 20), np.uint8)
        mask[2:8, 2:8, 10:15] = L4
        mask[2:8, 2:8, 2:7] = SACRUM         # three empty slices: centres 4 slices of 2 mm apart
        mask[9:11, 2:8, 10:15] = L5          # one empty column beside L4: centres 2 voxels of 0.8 mm
        distances = self.facts(mask)["distances_mm"]
        self.assertEqual(distances["23-28"], 8.0)
        self.assertEqual(distances["23-24"], 1.6)
        self.assertEqual(sorted(distances), ["23-24", "23-28", "24-28"])

    def test_the_distance_is_the_one_touch_py_reads_off_the_map(self):
        zooms = np.array([0.7, 0.9, 2.5])
        for seed in range(6):
            rng = np.random.default_rng(seed)
            mask = np.zeros((24, 20, 16), np.uint8)
            for label in (L4, L5, SACRUM):
                blob = ndimage.binary_dilation(rng.random(mask.shape) < 0.01) & (mask == 0)
                mask[blob] = label
            distances = self.facts(mask, affine=np.diag(list(zooms) + [1.0]), sid="%04d" % seed)["distances_mm"]
            for a, b in ((L4, L5), (L4, SACRUM), (L5, SACRUM)):
                self.assertEqual(distances["%d-%d" % (a, b)], touch_mm(mask, zooms, a, b))

    def test_the_pairs_are_the_column_neighbours_and_the_lumbar_labels_to_the_sacrum(self):
        self.assertEqual(len(F.DISTANCE_PAIRS), 30)
        for pair in ((1, 2), (19, 20), (23, 24), (24, 25), (20, 28), (23, 28), (25, 28)):
            self.assertIn(pair, F.DISTANCE_PAIRS)
        self.assertFalse([pair for pair in F.DISTANCE_PAIRS if {26, 27} & set(pair)])


class RibLadder(Folder):
    def test_every_rib_of_a_toy_column_leads_on_its_own_vertebra(self):
        mask, ribs = column_and_ribs()
        row = self.facts(mask, ribs)
        self.assertEqual(sorted(row["ribs"], key=int), [str(k) for k in range(1, 13)] + [str(k) for k in range(14, 26)])
        for label, rib in row["ribs"].items():
            k = (int(label) - 1) % C.RIBS_PER_SIDE + 1
            self.assertEqual(rib["lead"], k + C.OWN_VERTEBRA_OFFSET)
            self.assertEqual(rib["lead_n"], rib["contacts"][str(rib["lead"])])
            self.assertFalse(rib["tie"])
            self.assertEqual(rib["voxels"], int((ribs == int(label)).sum()))
            self.assertEqual(rib["components"], 1)
        self.assertEqual(row["sternum_voxels"], 0)
        self.assertTrue(row["ribs_mask"]["same_grid"])

    def test_a_thirteenth_rib_on_each_side_leads_on_the_label_l1(self):
        def plan(mask):
            return {**T.own_plan(mask), ("left", 13): T.L1, ("right", 13): T.L1}
        mask, ribs = column_and_ribs(plan)
        row = self.facts(mask, ribs)
        for label in (C.RIBS_PER_SIDE, F.TOP_RIB):          # left rib 13 and right rib 13
            self.assertEqual(row["ribs"][str(label)]["lead"], T.L1)
            self.assertEqual(row["ribs"][str(label)]["voxels"], int((ribs == label).sum()))

    def test_a_ladder_one_level_up_leads_one_label_up(self):
        def plan(mask):
            return {**T.own_plan(mask, sides=("right",)), **T.own_plan(mask, shift=-1, sides=("left",))}
        mask, ribs = column_and_ribs(plan)
        row = self.facts(mask, ribs)
        left = {int(label): rib["lead"] for label, rib in row["ribs"].items() if int(label) <= C.RIBS_PER_SIDE}
        self.assertEqual(left, {k: k + C.OWN_VERTEBRA_OFFSET - 1 for k in range(1, 13)})

    def test_every_tally_is_the_counts_own(self):
        mask, ribs = column_and_ribs()
        ribs[0:3, 0:3, 0:2] = C.TOP_RIB_LABEL            # a sternum of 18 voxels
        row = self.facts(mask, ribs)
        vert_img = nib.load(os.path.join(self.tmp.name, "masks", "0001.nii.gz"))
        rib_img = nib.load(os.path.join(self.tmp.name, "ribs", "0001.nii.gz"))
        counts, _ = C.slice_counts(rib_img, 2, C.TOP_RIB_LABEL)
        zooms = F.block_zooms(rib_img, 2)
        for label, rib in row["ribs"].items():
            tally = C.rib_contacts(vert_img, rib_img, 2, counts[:, int(label)], int(label), zooms)
            self.assertEqual(rib["contacts"], {str(k): n for k, n in sorted(tally.items())})
        lowest = C.rib_study(("0001", os.path.join(self.tmp.name, "masks"), os.path.join(self.tmp.name, "ribs"),
                              True))[1]["contacts"]
        for side, base in (("left", C.LEFT_RIB_BASE), ("right", C.RIGHT_RIB_BASE)):
            rib = row["ribs"][str(base + lowest[side]["lowest_rib"])]
            self.assertEqual((rib["contacts"], rib["lead"], rib["tie"]),
                             (lowest[side]["contacts"], lowest[side]["meets"], lowest[side]["tie"]))
        self.assertEqual(row["sternum_voxels"], 18)

    def test_a_tie_goes_head_most_and_is_marked(self):
        vert = np.zeros((30, 30, 30), np.uint8)
        vert[10:17, 10:17, 16:22] = T11
        vert[10:17, 10:17, 4:10] = T12
        rib = np.zeros_like(vert)
        rib[17, 10:17, 7] = 12                   # 7 voxels 1 mm from T12
        rib[17, 10:17, 19] = 12                  # 7 voxels 1 mm from T11
        fact = self.facts(vert, rib, affine=np.eye(4))["ribs"]["12"]
        self.assertEqual(fact["contacts"], {str(T11): 7, str(T12): 7})
        self.assertEqual((fact["lead"], fact["lead_n"], fact["tie"]), (T11, 7, True))
        self.assertEqual(fact["components"], 2)

    def test_a_rib_clear_of_the_spine_leads_on_nothing(self):
        vert = np.zeros((30, 30, 30), np.uint8)
        vert[10:17, 10:17, 4:10] = T12
        rib = np.zeros_like(vert)
        rib[25:28, 10:17, 7] = 12                # 9 mm from T12
        fact = self.facts(vert, rib, affine=np.eye(4))["ribs"]["12"]
        self.assertEqual((fact["contacts"], fact["lead"], fact["lead_n"], fact["tie"]), ({}, None, 0, False))

    def test_masks_on_different_grids_carry_no_tally(self):
        mask, ribs = column_and_ribs()
        ribs = np.concatenate([ribs, np.zeros(ribs.shape[:2] + (1,), np.uint8)], axis=2)
        row = self.facts(mask, ribs)
        self.assertFalse(row["ribs_mask"]["same_grid"])
        self.assertEqual({(rib["contacts"], rib["lead"]) for rib in row["ribs"].values()}, {(None, None)})


HEADER = ["Patient", "Data-Source", "Manufacturer", "Model", "kVp", "Filter", "Convolutional Kernel",
          "Pixel Spacing [mm]", "Slice Thickness [mm]", "Focal Spots [mm]"]
TABLE = [HEADER,
         ["0001", T.AUTOPET, "SIEMENS", "Biograph128", "120", "FLAT", "['I31f', '2']", "0.86328125", "3", "1.2"],
         ["1134", T.LEIPZIG, "Philips", "Gemini", "140", None, "B", "0.9765625", "2.5", None],
         [None, None, "GE", "Discovery", "120", None, "STANDARD", "0.97", "3.75", None]]


def write_table(path, rows):
    """A study table in the release's layout, every cell an inline string."""
    main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    pkg = "http://schemas.openxmlformats.org/package/2006/relationships"
    cell = '<c r="%s%d" t="inlineStr"><is><t>%s</t></is></c>'

    def row_xml(i, row):
        cells = "".join(cell % (letter, i, text) for letter, text in zip("ABCDEFGHIJ", row) if text is not None)
        return '<row r="%d">%s</row>' % (i, cells)
    body = "".join(row_xml(i, row) for i, row in enumerate(rows, 1))
    with zipfile.ZipFile(path, "w") as book:
        book.writestr("xl/workbook.xml", '<workbook xmlns="%s" xmlns:r="%s"><sheets><sheet name="S" sheetId="1" '
                                         'r:id="rId1"/></sheets></workbook>' % (main, rel))
        book.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="%s"><Relationship Id="rId1" '
                                                    'Target="worksheets/sheet1.xml" Type="x"/></Relationships>' % pkg)
        book.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="%s"><sheetData>%s</sheetData></worksheet>'
                      % (main, body))


def write_listing(path, folder, kind, wrong=()):
    entries = [["imaging-data/ground-truth/%s/%s" % (kind, name), os.path.getsize(os.path.join(folder, name))
                + (1 if C.study_id(name) in wrong else 0)] for name in sorted(os.listdir(folder))]
    with open(path, "w") as handle:
        json.dump(entries, handle)
    return path


class Rows(unittest.TestCase):
    """A run over three studies, one of them in the repair record, beside a study table and listings."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = cls.tmp.name
        cls.maskdir, cls.ribdir = os.path.join(root, "masks"), os.path.join(root, "ribs")
        os.mkdir(cls.maskdir), os.mkdir(cls.ribdir)
        for sid, mask in (("0001", T.column(T.STRICT)), ("0002", T.column(T.STRICT)), ("1134", T.CASES["1134"])):
            T.save(mask, os.path.join(cls.maskdir, sid + ".nii.gz"), flip=sid == "0002")
            T.save(T.rib_mask(mask, T.own_plan(mask)), os.path.join(cls.ribdir, sid + ".nii.gz"), flip=sid == "0002")
        cls.record = T.make_record(os.path.join(root, "record"), {"1134": T.REPAIRED_MASKS["1134"]})
        cls.xlsx = os.path.join(root, "CT-details.xlsx")
        write_table(cls.xlsx, TABLE)
        cls.listing = [write_listing(os.path.join(root, "keys.json"), cls.maskdir, "Vertebrae", wrong={"0002"}),
                       write_listing(os.path.join(root, "rib_keys.json"), cls.ribdir, "Ribs")]
        cls.out = cls.run_facts("facts.jsonl")
        with open(cls.out) as handle:
            cls.lines = handle.read().splitlines(keepends=True)
        cls.rows = {row["id"]: row for row in map(json.loads, cls.lines)}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @classmethod
    def run_facts(cls, name, workers=1, **options):
        out = os.path.join(cls.tmp.name, "out", name)
        with redirect_stderr(io.StringIO()):
            F.facts_step(cls.maskdir, cls.ribdir, cls.xlsx, out, options.get("listing", cls.listing),
                         options.get("record", cls.record), workers, options.get("ids"))
        return out

    def test_one_sorted_line_per_study_and_per_repaired_mask(self):
        self.assertEqual([json.loads(line)["id"] for line in self.lines], ["0001", "0002", "1134", "1134r"])
        for line in self.lines:
            self.assertEqual(line, F.row_line(json.loads(line)))
            line.encode("ascii")
        self.assertFalse(os.path.exists(self.out + F.PARTIAL_ENDING))

    def test_the_repaired_row_reads_the_repaired_vertebrae_beside_the_published_ribs(self):
        published, repaired = self.rows["1134"], self.rows["1134r"]
        sums = C.read_sha256sums(os.path.join(self.record, "SHA256SUMS"))
        self.assertEqual(repaired["repaired_from"], "1134")
        self.assertEqual(repaired["mask"]["sha256"], sums["repaired/1134.nii.gz"])
        self.assertIsNone(repaired["mask"]["listed_bytes"])
        self.assertEqual(repaired["ribs_mask"], published["ribs_mask"])
        self.assertEqual((repaired["site"], repaired["scanner"]), (published["site"], published["scanner"]))
        self.assertNotIn(str(8), published["labels"])
        self.assertIn(str(8), repaired["labels"])
        self.assertNotIn(str(19), repaired["labels"])
        self.assertNotIn("repaired_from", published)

    def test_the_study_table_and_the_listing(self):
        first, second = self.rows["0001"], self.rows["0002"]
        self.assertEqual(first["site"], "autoPET")
        self.assertEqual(first["scanner"], {"manufacturer": "SIEMENS", "model": "Biograph128", "kvp": "120",
                                            "kernel": "['I31f', '2']", "pixel_spacing": "0.86328125",
                                            "slice_thickness": "3"})
        self.assertEqual(self.rows["1134"]["site"], "Leipzig")
        self.assertEqual(second["site"], C.UNKNOWN_SITE)
        self.assertEqual(set(second["scanner"].values()), {None})
        self.assertEqual(first["mask"]["listed_bytes"], first["mask"]["bytes"])
        self.assertEqual(second["mask"]["listed_bytes"], second["mask"]["bytes"] + 1)
        self.assertEqual(F.listing_differences(self.rows), ["0002"])

    def test_the_output_is_the_same_byte_for_byte_in_two_processes(self):
        again = self.run_facts("again.jsonl", workers=2)
        with open(self.out, "rb") as first, open(again, "rb") as second:
            self.assertEqual(first.read(), second.read())

    def resumed(self, name, partial_text):
        """The rows of a run that finds `partial_text` left by an earlier one."""
        out = os.path.join(self.tmp.name, "out", name)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out + F.PARTIAL_ENDING, "w") as handle:
            handle.write(partial_text)
        self.run_facts(name)
        with open(out) as handle:
            return {row["id"]: row for row in map(json.loads, handle)}

    def test_a_run_cut_short_carries_on_from_the_rows_that_still_stand(self):
        kept = dict(self.rows["0001"], sternum_voxels=-1)                       # marked, to be seen reused
        stale = dict(self.rows["0002"], sternum_voxels=-1,
                     mask=dict(self.rows["0002"]["mask"], sha256="0" * 64))  # another mask's row
        moved = dict(self.rows["1134"], sternum_voxels=-1, site="Careggi")      # the table has changed
        header = json.dumps({F.CODE_KEY: F.code_digest()}) + "\n"
        rows = self.resumed("resumed.jsonl", header + F.row_line(kept) + F.row_line(stale) + F.row_line(moved)
                            + '{"id": "1134r", "cut')
        self.assertEqual(rows["0001"]["sternum_voxels"], -1)
        for sid in ("0002", "1134", "1134r"):
            self.assertEqual(rows[sid], self.rows[sid])

    def test_rows_other_code_wrote_are_computed_again(self):
        kept = F.row_line(dict(self.rows["0001"], sternum_voxels=-1))
        for header in (json.dumps({F.CODE_KEY: "another version"}) + "\n", ""):
            rows = self.resumed("other-code.jsonl", header + kept)
            self.assertEqual(rows, self.rows)

    def test_a_line_cut_short_is_ended_before_the_next_row(self):
        partial = os.path.join(self.tmp.name, "cut.partial")
        with open(partial, "w") as handle:
            handle.write(json.dumps({F.CODE_KEY: "x"}) + '\n{"id": "0001", "cut')
        with F.open_partial(partial, "x", resumed=True) as handle:
            handle.write(F.row_line(self.rows["0002"]))
        with open(partial) as handle:
            self.assertEqual(handle.read().splitlines(keepends=True)[-1], F.row_line(self.rows["0002"]))

    def test_ids_limit_the_run_and_a_record_is_read_only_when_needed(self):
        ids = os.path.join(self.tmp.name, "ids.json")
        with open(ids, "w") as handle:
            json.dump(["0001"], handle)
        out = self.run_facts("one.jsonl", ids=ids, record=os.path.join(self.tmp.name, "no-record"))
        with open(out) as handle:
            self.assertEqual([json.loads(line) for line in handle], [self.rows["0001"]])

    def test_the_committed_copy_of_the_table_reads_as_the_workbook(self):
        copy = os.path.join(self.tmp.name, "ct-details.json")
        with open(copy, "w") as handle:
            json.dump({"rows": C.sheet_rows(self.xlsx)}, handle)
        self.assertEqual(F.study_table(copy), F.study_table(self.xlsx))

    def test_an_empty_repair_record_reads_no_repaired_mask(self):
        with open(self.run_facts("no-record.jsonl", record="")) as handle:
            self.assertEqual([json.loads(line)["id"] for line in handle], ["0001", "0002", "1134"])

    def test_a_repaired_mask_not_the_one_its_hash_names_is_refused(self):
        bad = T.make_record(os.path.join(self.tmp.name, "bad-record"), {"1134": T.REPAIRED_MASKS["1134"]},
                            bad_hash={"1134"})
        with self.assertRaises(C.RepairRecordError):
            self.run_facts("bad.jsonl", record=bad)

    def test_the_command_line(self):
        out = os.path.join(self.tmp.name, "out", "cli.jsonl")
        printed = io.StringIO()
        with redirect_stdout(printed), redirect_stderr(io.StringIO()):
            F.main(["facts", self.maskdir, self.ribdir, self.xlsx, out, "--listing"] + self.listing
                   + ["--repair-record", self.record, "--workers", "1"])
        self.assertIn("4 rows (3 studies, 1 repaired masks)", printed.getvalue())
        self.assertIn("1 rows whose masks are missing from the listing or differ from it in bytes: 0002",
                      printed.getvalue())
        with open(out) as handle:
            self.assertEqual(handle.read().splitlines(keepends=True), self.lines)


if __name__ == "__main__":
    unittest.main()
