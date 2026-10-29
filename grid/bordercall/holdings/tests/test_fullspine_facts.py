"""The full-spine facts of VerSe and TotalSegmentator, on small synthetic masks written to a temporary folder.

The columns come from the ENHANCE.PET count's own tests, relabelled into each release's spelling, so the
facts are read on the same toy spines. Run from the repository's root with
`python -m unittest discover -s holdings/tests -t .`."""
import gzip
import io
import json
import os
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout

import nibabel as nib
import numpy as np

from holdings import fullspine_facts as F
from holdings.tests import test_count_enhance_pet as T

# ENHANCE.PET's sacrum is 28; VerSe's scheme has it at 26 and draws it in no scan.
VERSE_SACRUM, VERSE_T13 = 26, 28


def nifti_bytes(mask, affine):
    return gzip.compress(nib.Nifti1Image(np.ascontiguousarray(mask), affine).to_bytes())


def verse_column(levels):
    """A VerSe mask from the count's column, with no sacrum, as VerSe draws none."""
    return T.column([level for level in levels if level != T.SACRUM])


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)


def box(i, j, k):
    """The voxel indices of a box, each argument the first and last index on its axis."""
    return np.array([(a, b, c) for a in range(i[0], i[1] + 1) for b in range(j[0], j[1] + 1)
                     for c in range(k[0], k[1] + 1)])


class Names(unittest.TestCase):
    def test_every_spelling_of_the_release(self):
        cases = {"verse014_seg.nii.gz": ("verse014", None),
                 "verse512_CT-iso_seg.nii.gz": ("verse512", None),
                 "GL017_CT_ax_seg.nii.gz": ("gl017", None),
                 "GL090_CT-ax_seg.nii.gz": ("gl090", None),
                 "verse400_verse090_CT-iso_seg.nii.gz": ("verse090", "verse400"),
                 "sub-verse500_dir-iso_seg-vert_msk.nii.gz": ("verse500", None),
                 "sub-verse400_split-verse090_dir-iso_seg-vert_msk.nii.gz": ("verse090", "verse400")}
        for name, wanted in cases.items():
            self.assertEqual(F.verse_series(name), wanted, name)

    def test_images_centroids_and_subregions_are_not_masks(self):
        for name in ("verse512_CT-iso.nii.gz", "verse014_ctd.json", "verse014_snapshot.png",
                     "sub-verse500_dir-iso_seg-subreg_msk.nii.gz", "sub-verse500_dir-iso_ct.nii.gz"):
            self.assertIsNone(F.verse_series(name), name)


class Field(unittest.TestCase):
    def test_edges_are_the_outer_faces_on_the_head_foot_axis(self):
        top, bottom = F.field_edges((4, 4, 10), T.affine_for())
        self.assertAlmostEqual(top, T.ORIGIN_MM + 9.5 * T.SLICE_MM)
        self.assertAlmostEqual(bottom, T.ORIGIN_MM - 0.5 * T.SLICE_MM)

    def test_a_volume_stored_foot_first_has_the_same_edges(self):
        affine = T.affine_for()
        affine[2, 2] = -T.SLICE_MM
        affine[2, 3] = T.ORIGIN_MM + 9 * T.SLICE_MM
        self.assertEqual(tuple(round(x, 6) for x in F.field_edges((4, 4, 10), affine)),
                         tuple(round(x, 6) for x in F.field_edges((4, 4, 10), T.affine_for())))

    def test_faces_are_named_by_the_way_they_look(self):
        points = np.array([[0, 5, 9], [3, 5, 4]])
        # RAS: x rises to the right, so index 0 is the left face; z rises to the head.
        self.assertEqual(F.faces_touched(points, (4, 8, 10), T.affine_for()), ["L", "R", "S"])
        flipped = T.affine_for()
        flipped[2, 2] = -T.SLICE_MM
        self.assertEqual(F.faces_touched(np.array([[1, 1, 0]]), (4, 8, 10), flipped), ["S"])


class Slabs(unittest.TestCase):
    """A mask read a slab at a time gives the points a whole read gives, in the same order."""

    def whole(self, img):
        saved = F.SLAB_VOXELS
        F.SLAB_VOXELS = 1 << 40
        try:
            return F.voxel_points(img)
        finally:
            F.SLAB_VOXELS = saved

    def sliced(self, img):
        saved = F.SLAB_VOXELS
        F.SLAB_VOXELS = 7
        try:
            return F.voxel_points(img)
        finally:
            F.SLAB_VOXELS = saved

    def assert_same(self, img):
        whole, sliced = self.whole(img), self.sliced(img)
        self.assertEqual(list(whole), list(sliced))
        for label in whole:
            np.testing.assert_array_equal(whole[label], sliced[label])

    def test_a_float_mask_from_its_file(self):
        mask = verse_column(T.labels(T.C1, T.L5)).astype(np.float64)
        self.assert_same(F.image_of(nifti_bytes(mask, T.affine_for())))

    def test_an_integer_mask_from_its_file_and_from_an_array(self):
        mask = verse_column(T.labels(T.C1, T.L5)).astype(np.uint8)
        self.assert_same(F.image_of(nifti_bytes(mask, T.affine_for())))
        self.assert_same(nib.Nifti1Image(np.ascontiguousarray(mask), T.affine_for()))

    def test_the_slabs_cover_the_volume_once(self):
        spans = [(start, stop) for _, start, stop in F.slabs((4, 5, 11), "F")]
        self.assertEqual(spans[0][0], 0)
        self.assertEqual(spans[-1][1], 11)
        self.assertTrue(all(a[1] == b[0] for a, b in zip(spans, spans[1:])))

    def test_several_slabs_cover_the_slowest_axis_once_in_order(self):
        saved = F.SLAB_VOXELS
        F.SLAB_VOXELS = 3 * 4 * 5
        try:
            for order, shape, axis in (("F", (4, 5, 11), 2), ("C", (11, 4, 5), 0)):
                spans = list(F.slabs(shape, order))
                self.assertEqual(len(spans), 4, order)
                self.assertEqual({a for a, _, _ in spans}, {axis}, order)
                self.assertEqual([i for _, start, stop in spans for i in range(start, stop)], list(range(11)), order)
        finally:
            F.SLAB_VOXELS = saved

    def test_a_level_on_the_last_plane_is_read_by_the_last_slab(self):
        """The toy columns leave empty planes at both ends; here C1 reaches the head face, which only
        the last slab of a sliced read holds, so a walker that dropped it would lose those voxels."""
        mask = verse_column(T.labels(T.C1, T.L5)).astype(np.float64)
        mask[2:4, 2:4, -1] = T.C1
        img = F.image_of(nifti_bytes(mask, T.affine_for()))
        self.assert_same(img)
        found = self.sliced(img)
        for label in found:
            self.assertEqual(len(found[label]), int((mask == label).sum()), label)
        self.assertEqual(int(found[T.C1][:, 2].max()), mask.shape[2] - 1)


class Distances(unittest.TestCase):
    """Distances are in mm on the grid's own spacing, 0.8 mm in plane and 2 mm between slices here."""

    def test_lumbar_to_sacrum_across_slices_and_in_plane(self):
        levels = {"sacrum": box((0, 2), (0, 2), (0, 2)), "L5": box((0, 2), (0, 2), (5, 6)),
                  "L4": box((7, 8), (0, 2), (0, 2))}
        # L5 lies three slices above the sacrum (6 mm), L4 five voxels beside it in plane (4 mm).
        self.assertEqual(F.lumbosacral_distances(levels, T.affine_for()), {"L4-sacrum": 4.0, "L5-sacrum": 6.0})

    def test_a_rib_reach_is_in_mm(self):
        levels = {"T12": box((0, 2), (0, 2), (0, 2)), "L1": box((0, 2), (0, 2), (10, 12))}
        rib = box((6, 7), (0, 2), (0, 2))
        reach = F.rib_reach(rib, F.level_trees(levels, T.affine_for()), T.affine_for())
        # Four voxels beside T12 is 3.2 mm; L1 is that far beside and eight slices above, 16.3 mm.
        self.assertEqual(reach, {"T12": 3.2, "L1": 16.3})


class Ribs(unittest.TestCase):
    def test_the_nearest_level_leads_and_a_tie_goes_to_the_head(self):
        self.assertEqual(F.lead_of({"T12": 4.0, "L1": 9.5}), ("T12", 5.5, False))
        self.assertEqual(F.lead_of({"L1": 3.0, "T12": 3.0}), ("T12", 0.0, True))
        self.assertEqual(F.lead_of({}), (None, None, False))


class Verse(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        affine = T.affine_for()
        whole = verse_column(T.labels(T.C1, T.L5))
        self.whole = whole
        changed = whole.copy()
        changed[changed == T.L5] = 0
        write(os.path.join(self.root, "verse20", "verse400_verse090_CT-iso_seg.nii.gz"), nifti_bytes(whole, affine))
        write(os.path.join(self.root, "verse19", "verse090_seg.nii.gz"), nifti_bytes(changed, affine))
        write(os.path.join(self.root, "verse19", "verse014_seg.nii.gz"), nifti_bytes(whole, affine))
        write(os.path.join(self.root, "verse19", "verse014.nii.gz"), nifti_bytes(whole, affine))

    def tearDown(self):
        self.tmp.cleanup()

    def test_jobs_group_a_series_across_the_releases(self):
        jobs = F.verse_jobs(self.root)
        self.assertEqual([j[0] for j in jobs], ["verse014", "verse090"])
        self.assertEqual(jobs[1][1], "verse400")
        self.assertEqual(sorted(jobs[1][2]), ["verse19", "verse20"])

    def test_verse20_is_read_and_verse19_set_beside_it(self):
        row = F.verse_row(F.verse_jobs(self.root)[1])
        self.assertEqual(row["release"], "verse20")
        self.assertEqual(row["patient_in_name"], "verse400")
        other = row["other_release"]
        self.assertEqual(other["release"], "verse19")
        self.assertTrue(other["same_grid"])
        self.assertFalse(other["same_levels"])
        self.assertEqual(other["voxels_differ"], ["L5"])

    def test_levels_are_named_and_the_field_is_the_mask_grid(self):
        row = F.verse_row(F.verse_jobs(self.root)[0])
        self.assertEqual(list(row["levels"]), [f"C{i}" for i in range(1, 8)] + [f"T{i}" for i in range(1, 13)]
                         + [f"L{i}" for i in range(1, 6)])
        top, bottom = F.field_edges(self.whole.shape, T.affine_for())
        self.assertEqual(row["field_mm"], {"top": round(top, 1), "bottom": round(bottom, 1)})
        self.assertEqual(row["levels"]["C1"]["faces"], [])
        self.assertEqual(row["distances_mm"], {})
        self.assertNotIn("other_release", row)

    def test_the_variant_levels_and_the_sacrum_are_named_by_the_scheme(self):
        """VerSe's own numbers, not ENHANCE.PET's: T13 is 28, L6 25 and the sacrum 26."""
        levels = [*range(1, 20), 28, *range(20, 26), 26]
        mask = T.column(levels)
        write(os.path.join(self.root, "verse20", "verse888_seg.nii.gz"), nifti_bytes(mask, T.affine_for()))
        row = F.verse_row([j for j in F.verse_jobs(self.root) if j[0] == "verse888"][0])
        names = [F.VERSE_NAMES[label] for label in levels]
        self.assertEqual(sorted(row["levels"]), sorted(names))
        for label, name in zip(levels, names):
            self.assertEqual(row["levels"][name]["voxels"], int((mask == label).sum()), name)
        self.assertGreater(row["levels"]["T13"]["top_mm"], row["levels"]["L1"]["top_mm"])
        self.assertIn("L6-sacrum", row["distances_mm"])
        self.assertNotIn("outside_scheme", row)

    def test_a_label_outside_the_scheme_is_named(self):
        odd = self.whole.copy()
        odd[0, 0, 0] = 30
        write(os.path.join(self.root, "verse20", "verse777_seg.nii.gz"), nifti_bytes(odd, T.affine_for()))
        row = F.verse_row([j for j in F.verse_jobs(self.root) if j[0] == "verse777"][0])
        self.assertEqual(row["outside_scheme"], [30])

    def test_two_masks_of_one_series_in_one_release_are_refused(self):
        write(os.path.join(self.root, "verse19", "verse014_CT-iso_seg.nii.gz"), nifti_bytes(self.whole, T.affine_for()))
        with self.assertRaises(ValueError):
            F.verse_jobs(self.root)


def ts_zip(subject, masks, affine):
    """A release zip holding one subject's segmentations, and the index entries the spans carry."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, mask in masks.items():
            archive.writestr(f"Totalsegmentator_dataset_v300/{subject}/segmentations/{name}", nifti_bytes(mask, affine))
    data = buffer.getvalue()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = [{"name": i.filename, "method": i.compress_type, "csize": i.compress_size,
                    "usize": i.file_size, "offset": i.header_offset} for i in archive.infolist()]
    return data, entries


def binary(mask, label):
    return (mask == label).astype(np.uint8)


class TotalSegmentator(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        mask = T.column(T.labels(T.C2, T.L5) + [T.TALL_SACRUM])
        self.mask = mask
        names = {**{f"vertebrae_{F.VERSE_NAMES[label]}.nii.gz": label for label in range(T.C2, T.L5 + 1)},
                 "sacrum.nii.gz": T.SACRUM}
        masks = {name: binary(mask, label) for name, label in names.items()}
        masks["rib_left_12.nii.gz"] = (T.rib_mask(mask, {("left", 12): T.T12}) > 0).astype(np.uint8)
        masks["vertebrae_T13.nii.gz"] = np.zeros_like(mask)
        data, entries = ts_zip("s0001", masks, T.affine_for())
        self.span = os.path.join(self.tmp.name, "s0001.span")
        write(self.span, data)
        with open(os.path.join(self.tmp.name, "index.json"), "w") as handle:
            json.dump({"s0001": {"lo": 0, "hi": len(data), "entries": entries}}, handle)

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_subject_row(self):
        row = F.ts_row(F.ts_jobs(self.tmp.name)[0])
        self.assertEqual(row["member"], "totalsegmentator")
        self.assertIn("sacrum", row["levels"])
        self.assertNotIn("T13", row["levels"])
        self.assertEqual(row["levels"]["C2"]["components"], 1)
        self.assertIn("L5-sacrum", row["distances_mm"])
        self.assertEqual(row["ribs"]["left_12"]["lead"], "T12")
        self.assertEqual(len(row["files"]), 26)

    def test_a_member_on_another_grid_is_refused(self):
        buffer = io.BytesIO()
        moved = T.affine_for()
        moved[0, 3] += 5
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, label, affine in (("vertebrae_C2.nii.gz", T.C2, T.affine_for()), ("vertebrae_C3.nii.gz", T.C3, moved)):
                archive.writestr(f"Totalsegmentator_dataset_v300/s0002/segmentations/{name}",
                                 nifti_bytes(binary(self.mask, label), affine))
        data = buffer.getvalue()
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = [{"name": i.filename, "method": i.compress_type, "csize": i.compress_size,
                        "usize": i.file_size, "offset": i.header_offset} for i in archive.infolist()]
        path = os.path.join(self.tmp.name, "s0002.span")
        write(path, data)
        row = F.safe(F.ts_row)(("s0002", path, 0, entries))
        self.assertIn("another grid", row["error"])

    def test_the_command_writes_sorted_rows(self):
        out = os.path.join(self.tmp.name, "facts.jsonl")
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(F.main(["totalsegmentator", self.tmp.name, out, "--workers", "1"]), 0)
        rows = [json.loads(line) for line in open(out)]
        self.assertEqual([r["id"] for r in rows], ["s0001"])


    def test_a_run_cut_short_reads_only_what_it_has_not_written(self):
        out = os.path.join(self.tmp.name, "facts.jsonl")
        kept = {"id": "s0001", "member": "totalsegmentator", "kept": True}
        with open(out + ".part", "w") as handle:
            handle.write(json.dumps(kept) + "\n" + '{"id": "s00')
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(F.main(["totalsegmentator", self.tmp.name, out, "--workers", "1"]), 0)
        rows = [json.loads(line) for line in open(out)]
        self.assertEqual(rows, [kept])
        self.assertFalse(os.path.exists(out + ".part"))


if __name__ == "__main__":
    unittest.main()
