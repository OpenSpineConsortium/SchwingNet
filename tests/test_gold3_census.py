"""tools/gold3_census.py on made-up files: its NIfTI reader against nibabel's, the field test over a census
mask, the CT's own planes, the autoPET match and the held checks, and the report's lines. Needs numpy,
which the check's environment may lack, so it is a plain unittest under tests/ and skips without it; the
reader's comparison with nibabel runs where nibabel is installed too."""

import csv
import gzip
import hashlib
import importlib.util
import json
import os
import re
import shutil
import struct
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None
try:
    import nibabel as nib
except ImportError:  # pragma: no cover
    nib = None


def load_census():
    spec = importlib.util.spec_from_file_location("gold3_census", ROOT / "tools/gold3_census.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["gold3_census"] = module
    spec.loader.exec_module(module)
    return module


C = load_census() if np is not None else None

CODES = {"u1": 2, "i2": 4, "i4": 8, "f4": 16, "f8": 64, "u2": 512}


def nifti_bytes(data, affine, zooms=None, slope=0.0, inter=0.0, qform=None, sform_code=1, endian="<"):
    """A single-file NIfTI-1 image as bytes: the sform from affine, a qform given as (code, b, c, d, qfac,
    offset) or none, and the voxels in Fortran order after a 4-byte empty extension."""
    data = np.asarray(data)
    code = CODES[data.dtype.str[1:]]
    zooms = zooms or [float(np.sqrt((np.asarray(affine)[:3, i] ** 2).sum())) for i in range(3)]
    header = bytearray(348)
    struct.pack_into(endian + "i", header, 0, 348)
    struct.pack_into(endian + "8h", header, 40, 3, *data.shape, 1, 1, 1, 1)
    struct.pack_into(endian + "hh", header, 70, code, data.dtype.itemsize * 8)
    qfac = qform[4] if qform else 1.0
    struct.pack_into(endian + "8f", header, 76, qfac, *zooms, 0, 0, 0, 0)
    struct.pack_into(endian + "f", header, 108, 352.0)
    struct.pack_into(endian + "ff", header, 112, slope, inter)
    struct.pack_into(endian + "hh", header, 252, qform[0] if qform else 0, sform_code)
    if qform:
        struct.pack_into(endian + "6f", header, 256, *qform[1:4], *qform[5])
    struct.pack_into(endian + "12f", header, 280, *np.asarray(affine, float)[:3].ravel())
    header[344:348] = b"n+1\0"
    raw = data.astype(data.dtype.newbyteorder(endian)).tobytes(order="F")
    return bytes(header) + b"\0\0\0\0" + raw


def write_nifti(path, data, affine, gz=True, **kw):
    blob = nifti_bytes(data, affine, **kw)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(gzip.compress(blob, mtime=0) if gz else blob)
    return Path(path)


def column(shape=(16, 16, 240), names=None, body=7, gap=2, top_margin=4):
    """Boxes stacked head to foot along axis 2 (head at the high index), one per VerSe id given."""
    names = names or [2, *range(3, 26), 26]
    data = np.zeros(shape, np.uint8)
    z = shape[2] - top_margin
    for label in names:
        if z <= 0:
            raise ValueError("the column does not fit the shape")
        data[4:12, 4:12, max(z - body, 0):z] = label
        z -= body + gap
    return data


@unittest.skipIf(np is None, "numpy is not installed")
class Reader(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)

    def read_points(self, path):
        volume = C.Volume(path)
        try:
            return volume, C.voxel_points(volume)
        finally:
            volume.close()

    def test_labels_come_in_fortran_order_with_their_world_extent(self):
        data = np.zeros((4, 3, 5), np.uint8)
        data[1, 2, 0], data[0, 0, 3], data[2, 1, 3] = 7, 7, 9
        affine = np.diag([2.0, 2.0, 3.0, 1.0])
        affine[:3, 3] = [10, 20, 30]
        volume, points = self.read_points(write_nifti(self.dir / "a.nii.gz", data, affine))
        self.assertEqual(sorted(points), [7, 9])
        self.assertEqual(points[7].tolist(), [[1, 2, 0], [0, 0, 3]])
        facts = C.label_facts(points[7], volume.affine, volume.shape)
        self.assertEqual((facts["voxels"], facts["top_mm"], facts["bottom_mm"]), (2, 39.0, 30.0))
        self.assertEqual(facts["faces"], ["A", "I", "L", "P"])

    def test_slabs_cut_a_volume_into_pieces_without_losing_a_voxel(self):
        data = column()
        path = write_nifti(self.dir / "c.nii.gz", data, np.eye(4))
        saved = C.SLAB_VOXELS
        C.SLAB_VOXELS = 16 * 16 * 7
        try:
            _, points = self.read_points(path)
        finally:
            C.SLAB_VOXELS = saved
        for label in (2, 13, 26):
            want = np.argwhere(data.transpose(2, 1, 0) == label)[:, ::-1]
            self.assertEqual(points[label].tolist(), want.tolist())

    def test_a_hashed_read_gives_the_files_own_sha256(self):
        for gz in (True, False):
            path = write_nifti(self.dir / f"h{gz}.nii{'.gz' if gz else ''}", column(), np.eye(4), gz=gz)
            volume = C.Volume(path, hashed=True)
            for _ in volume.slabs():
                pass
            self.assertEqual(volume.finish(), (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_size))

    def test_float_labels_are_rounded_and_scaling_is_applied(self):
        data = np.zeros((3, 3, 3), np.float32)
        data[1, 1, 1] = 4.9999
        _, points = self.read_points(write_nifti(self.dir / "f.nii.gz", data, np.eye(4)))
        self.assertEqual(list(points), [5])
        ints = np.full((2, 2, 2), 3, np.int16)
        volume = C.Volume(write_nifti(self.dir / "s.nii.gz", ints, np.eye(4), slope=2.0, inter=-1.0))
        try:
            self.assertEqual({float(v) for _, slab in volume.slabs() for v in slab.ravel()}, {5.0})
        finally:
            volume.close()

    def test_a_nifti_2_header_is_refused_by_name(self):
        blob = bytearray(nifti_bytes(np.zeros((2, 2, 2), np.uint8), np.eye(4)))
        struct.pack_into("<i", blob, 0, 540)
        path = self.dir / "two.nii"
        path.write_bytes(bytes(blob))
        with self.assertRaisesRegex(C.NiftiError, "NIfTI-2"):
            C.Volume(path)

    @unittest.skipIf(nib is None, "nibabel is not installed")
    def test_the_grid_is_nibabels_for_sform_qform_and_neither(self):
        rng = np.random.default_rng(7)
        cases = []
        for i in range(12):
            q = rng.normal(size=4)
            q /= np.linalg.norm(q)
            q *= np.sign(q[0])
            zooms = list(rng.uniform(0.3, 3.0, 3))
            offset = list(rng.uniform(-300, 300, 3))
            qfac = (-1.0, 1.0, 0.0)[i % 3]
            rot = nib.quaternions.quat2mat(q)
            affine = np.eye(4)
            affine[:3, :3] = rot @ np.diag(zooms)
            affine[:3, 3] = offset
            sform_code = (1, 0, 0)[i % 3]
            qform = (1, *q[1:], qfac, offset) if i % 3 != 2 else None
            cases.append((affine, zooms, qform, sform_code))
        for i, (affine, zooms, qform, sform_code) in enumerate(cases):
            path = write_nifti(self.dir / f"g{i}.nii.gz", np.zeros((5, 6, 7), np.int16), affine, zooms=zooms,
                               qform=qform, sform_code=sform_code, endian="<>"[i % 2])
            ours = C.Volume(path)
            ours.close()
            theirs = nib.load(path)
            np.testing.assert_array_equal(ours.affine, theirs.affine)
            self.assertEqual(tuple(float(z) for z in ours.zooms), tuple(float(z) for z in theirs.header.get_zooms()))
            self.assertEqual(C.axcodes_of(ours.affine), nib.aff2axcodes(theirs.affine))
            np.testing.assert_array_equal(C.io_orientation(ours.affine), nib.orientations.io_orientation(theirs.affine))


FIXTURE = ROOT / "tests/fixtures/gold3-census-grids.json"


@unittest.skipIf(np is None, "numpy is not installed")
class RecordedReadings(unittest.TestCase):
    """The reader against readings recorded once from nibabel 5.4.2 and bordercall's fullspine_facts, so the
    agreement is held on CI, where neither is installed."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.recorded = json.loads(FIXTURE.read_text())

    def test_every_crafted_header_reads_as_nibabel_read_it(self):
        self.assertEqual(len(self.recorded["cases"]), 15)
        for i, case in enumerate(self.recorded["cases"]):
            with self.subTest(case["name"]):
                qform = case["qform"]
                if qform is not None:
                    qform = (qform[0], qform[1], qform[2], qform[3], qform[4], qform[5])
                path = write_nifti(self.dir / f"r{i}.nii.gz", np.zeros(case["shape"], np.int16), case["affine"],
                                   zooms=case["zooms"], qform=qform, sform_code=case["sform_code"],
                                   endian=case["endian"])
                ours = C.Volume(path)
                ours.close()
                theirs = case["nibabel"]
                np.testing.assert_array_equal(np.asarray(ours.affine, float), np.asarray(theirs["affine"], float))
                self.assertEqual([float(z) for z in ours.zooms], [float(z) for z in theirs["zooms"]])
                self.assertEqual(list(C.axcodes_of(ours.affine)), theirs["axcodes"])
                np.testing.assert_array_equal(C.io_orientation(ours.affine), np.asarray(theirs["io_orientation"]))

    def test_a_big_endian_labelled_column_gives_fullspine_facts_own_facts(self):
        case = self.recorded["labelled"]
        data = column(tuple(case["shape"]), case["names"], body=case["body"], gap=case["gap"]).astype(np.int16)
        *where, label = case["stray"]
        data[tuple(where)] = label
        path = write_nifti(self.dir / "labelled.nii.gz", data, case["affine"], endian=case["endian"])
        volume = C.Volume(path)
        try:
            points = C.voxel_points(volume)
            self.assertEqual(C.grid_facts(volume), case["grid"])
            self.assertEqual(C.field_facts(volume), case["field"])
            facts = {str(n): C.label_facts(p, volume.affine, volume.shape) for n, p in points.items()}
        finally:
            volume.close()
        self.assertEqual(facts, case["labels"])


@unittest.skipIf(np is None, "numpy is not installed")
class Grids(unittest.TestCase):
    def test_one_grid_stored_las_and_ras_is_one_canonical_grid(self):
        ras = np.diag([0.8, 0.8, 2.5, 1.0])
        ras[:3, 3] = [-200.0, -180.0, -1100.0]
        las = ras.copy()
        las[0, 0], las[0, 3] = -0.8, -200.0 + 0.8 * 511
        first, second = C.canonical_grid((512, 512, 300), ras), C.canonical_grid((512, 512, 300), las)
        self.assertEqual(first[0], second[0])
        self.assertLess(C.grid_residual(first, second), 1e-9)

    def test_a_study_matches_the_one_ct_on_its_grid(self):
        grid = C.canonical_grid((4, 4, 9), np.diag([1.0, 1.0, 2.0, 1.0]))
        moved = C.canonical_grid((4, 4, 9), np.array([[1, 0, 0, 0.5], [0, 1, 0, 0], [0, 0, 2, 0], [0, 0, 0, 1.0]]))
        rows = [{"id": "0001", "mask": {"shape": [4, 4, 9], "affine": np.diag([1.0, 1.0, 2.0, 1.0]).tolist()}},
                {"id": "0002", "mask": {"shape": [4, 4, 8], "affine": np.eye(4).tolist()}}]
        cases = [("PETCT_0a1b/ct", "a/CT.nii.gz"), ("PETCT_0c2d/ct", "b/CT.nii.gz")]
        matches, bins = C.match_studies(rows, cases, [moved, grid])
        self.assertEqual(matches["0001"]["ct"], "b/CT.nii.gz")
        self.assertEqual(matches["0001"]["person"], "PETCT_0c2d")
        self.assertEqual(bins, {"matched": 1, "no CT of the same shape": 1})

    def test_only_ct_files_are_taken_from_a_walk(self):
        names = {"CT.nii.gz": True, "CTres.nii.gz": True, "PETCT_0a1b_CT.nii.gz": True, "SUV.nii.gz": False,
                 "SEG.nii.gz": False, "PET.nii.gz": False, "ct_seg.nii.gz": False, "ct.json": False}
        self.assertEqual({n: C.looks_like_ct(n) for n in names}, names)


def tier_list(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(C.TIER_COLUMNS) + ["spineps_ctd"], delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({**{k: "" for k in C.TIER_COLUMNS}, **row})


@unittest.skipIf(np is None, "numpy is not installed")
class Census(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.args = Namespace(data=str(self.dir / "data"), rs=str(self.dir / "rs"), home=str(self.dir / "home"),
                              out=str(self.dir / "out"), workers=1)
        affine = np.diag([1.0, 1.0, 1.0, 1.0])
        masks = self.dir / "masks"
        whole = write_nifti(masks / "whole.nii.gz", column(shape=(16, 16, 300), body=10, gap=2), affine)
        # the same column with its top cut through C3, and so neither C2 drawn nor its foot in the field
        cut = write_nifti(masks / "cut.nii.gz", column(shape=(16, 16, 300), body=10, gap=2)[:, :, :272], affine)
        raw = write_nifti(masks / "raw.nii.gz", column(), affine)
        tier_list(Path(self.args.rs) / "ruleclass/tiers/tier1.tsv", [
            {"tier": "1", "collection": "idc_one", "case_id": "a", "person_key": "p1", "spineps_vert": str(whole), "spineps_ids": "verse_coded"},
            {"tier": "1", "collection": "idc_two", "case_id": "b", "person_key": "p2", "spineps_vert": str(cut), "spineps_ids": "verse_coded"},
            {"tier": "1", "collection": "amos", "case_id": "c", "person_key": "p3", "spineps_vert": str(raw), "spineps_ids": "raw"},
            {"tier": "1", "collection": "amos", "case_id": "d", "person_key": "p4", "spineps_vert": str(masks / "gone.nii.gz"), "spineps_ids": "verse_coded"},
        ])
        tier_list(Path(self.args.rs) / "ruleclass/tiers/tier2.tsv", [
            {"tier": "2", "collection": "idc_one", "case_id": "a", "person_key": "p1", "spineps_vert": str(whole), "spineps_ids": "verse_coded"},
        ])

    def test_a_whole_column_is_gold_4_and_a_cut_one_is_not(self):
        rows = C.census_rows(self.args.rs)
        self.assertEqual(len(rows), 4)
        results = {row["case_id"]: C.gold4_one(row) for row in rows}
        self.assertEqual(results["a"]["verdict"], "admitted")
        self.assertEqual((results["a"]["head"], results["a"]["foot"]), ("drawn", "drawn"))
        self.assertEqual(results["b"]["verdict"], "not_admitted")
        self.assertIn("raw ids", results["c"]["set_aside"])
        self.assertIn("no mask file", results["d"]["set_aside"])

    def test_the_part_counts_by_collection_with_idc_folded(self):
        part = C.part_gold4(self.args)
        text = "\n".join(part.lines)
        self.assertIn("gold4: census masks 4", text)
        self.assertIn("new to the dataset", text)
        self.assertIn("1 studies, 1 persons", text)
        self.assertIn("gold4: idc rows 2, admitted 1 of 1 persons", text)
        self.assertTrue((Path(self.args.out) / "gold4.json").is_file())
        assert_report_lines(self, part.lines)

    def test_the_older_list_is_set_beside_rule_3s_admitted(self):
        record = json.loads((C.DATA / "totalsegmentator.json").read_text())
        admitted = sorted(C.admitted_ids("totalsegmentator"))
        listed = admitted[:3] + ["s9998"]
        path = Path(self.args.home) / "model_night/ts_clean_subjects.txt"
        path.parent.mkdir(parents=True)
        path.write_text("\n".join(listed) + "\n")
        part = C.part_ts142(self.args)
        self.assertEqual(part.detail["both"], admitted[:3])
        self.assertEqual(part.detail["unknown"], ["s9998"])
        self.assertFalse(part.detail["matches_record"])
        self.assertEqual(record["count"], 142)
        assert_report_lines(self, part.lines)


@unittest.skipIf(np is None, "numpy is not installed")
class Extent(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)

    def test_constant_planes_at_either_end_give_the_ct_its_own_planes(self):
        data = np.full((6, 6, 40), -1024, np.int16)
        data[:, :, 5:33] = np.arange(6 * 6 * 28, dtype=np.int16).reshape(6, 6, 28)
        affine = np.diag([1.0, 1.0, 2.0, 1.0])
        affine[2, 3] = 100.0
        path = write_nifti(self.dir / "ct.nii.gz", data, affine)
        read = C.extent_one(("s0001", str(path), np.array([3.0, 3.0, 150.0])))
        self.assertEqual((read["flat_low"], read["flat_high"]), (5, 7))
        self.assertEqual((read["low_mm"], read["high_mm"]), (110.0, 164.0))
        self.assertEqual(C.own_planes(read), (164.0, 110.0))
        self.assertEqual(read["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_a_grid_stored_head_to_foot_reverses_the_ends(self):
        read = {"grid": {"affine": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, -2, 0], [0, 0, 0, 1]], "head_foot_axis": 2},
                "flat_low": 3, "flat_high": 0, "low_mm": -6.0, "high_mm": -70.0}
        self.assertEqual(C.own_planes(read), (-6.0, None))

    def test_a_named_study_takes_the_planes_it_is_given(self):
        G = C.sibling("gold3_field")
        row = {"member": "totalsegmentator", "id": "s0001", "field_mm": {"top": 200.0, "bottom": 0.0}, "context": {},
               "grid": {"affine": np.eye(4).tolist(), "shape": [10, 10, 200], "zooms": [1.0, 1.0, 1.0], "head_foot_axis": 2},
               "levels": {"C2": {"voxels": 500, "faces": [], "top_mm": 180.0, "bottom_mm": 160.0, "centroid_mm": [5, 5, 170]}}}
        self.assertEqual((G.named_study(row, None, None, None)["top"]), 200.0)
        self.assertEqual((G.named_study(row, None, None, None, planes=(181.0, None))["top"]), 181.5)


@unittest.skipIf(np is None, "numpy is not installed")
class Held(unittest.TestCase):
    def test_a_name_matches_by_any_sha256_recorded_for_it(self):
        recorded = {"a": {"1", "2"}, "b": {"3"}, "c": {"4"}}
        found = {"a": ["2"], "b": ["9"], "x": ["5"]}
        self.assertEqual(C.tally(found, recorded),
                         {"match": 1, "other bytes": 1, "not found": 1, "on the grid and not recorded": 1})

    def test_totalsegmentators_files_digest_as_the_facts_record_them(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder)
        seg = folder / "segmentations"
        seg.mkdir()
        for name in ("vertebrae_C2.nii.gz", "sacrum.nii.gz", "rib_left_3.nii.gz", "liver.nii.gz"):
            (seg / name).write_bytes(name.encode())
        files = {name: {"sha256": hashlib.sha256(name.encode()).hexdigest(), "bytes": len(name)}
                 for name in ("vertebrae_C2.nii.gz", "sacrum.nii.gz", "rib_left_3.nii.gz")}
        self.assertEqual(C.ts_digest(folder), C.sibling("gold3_field").sums_digest(files))

    def test_verses_record_holds_every_mask_of_both_releases(self):
        recorded, entries = C.verse_recorded()
        self.assertEqual(entries, 473)
        self.assertLessEqual(sum(len(s) for s in recorded.values()), 473)


HEX_RUN = re.compile(r"[0-9a-f]{32,}", re.IGNORECASE)
DATE_RUN = re.compile(r"\b20\d{6}\b")


def assert_report_lines(test, lines):
    """What gate.sh's masking would cut or redact, a report line carries none of: no path, no key-shaped
    hex, no date run together, no `name:value`, nothing over LINE_CHARS."""
    for line in lines:
        test.assertNotIn("/", line, line)
        test.assertIsNone(HEX_RUN.search(line), line)
        test.assertIsNone(DATE_RUN.search(line), line)
        test.assertIsNone(re.search(r"\w:\S", line), line)
        test.assertLessEqual(len(line), C.LINE_CHARS, line)


if __name__ == "__main__":
    unittest.main()
