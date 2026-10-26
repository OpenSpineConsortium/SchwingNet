"""tools/anomaly_pack.py (#391, stage 3, pack): every row of a fake selection resolved to its CT and mask by
the stores the records name, the expert mask first and never a TotalSegmentator store; the guard's lines read;
the masks rewritten, counted and measured for countability; the G3 exclusion, the validation draw and the
splits; FleXray's manifests; the size the admission reads; and sections and errors that carry counts only.
The tree is synthetic under a temporary directory: 16x16x8 NIfTIs built by tests/test_nifti_label.py's helper."""

import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("anomaly_pack", ROOT / "tools" / "anomaly_pack.py")
pack = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pack)

from tests.test_nifti_label import pattern, write_nifti  # noqa: E402  (the NIfTI builder, one source of truth)

SMALL = (16, 16, 8)
# VerSe-alphabet spines: C2 to T12, L1 to L5 and the sacrum; an L6 adds 25, a T13 adds 28.
NORMAL = list(range(2, 20)) + list(range(20, 25)) + [26]
WITH_L6 = NORMAL[:-1] + [25, 26]
WITH_T13 = list(range(2, 20)) + [28] + list(range(20, 25)) + [26]
# The registry's and the harvest's columns, as the records carry them.
REGISTRY_COLUMNS = ("patient_key,is_person,in_streams,subtype,call,truth_tier,castellvi,castellvi_candidate,four_lumbar,"
                    "lumbar_rib,winning_source,winning_case,sources,n_scans,real_frames,frames_role,aliases,other_calls,"
                    "disagreement,table_subtype,table_after_ts_subtype,table_basis,table_vs_registry,labeller_a,labeller_b,"
                    "agree,n_thoracic_rib_bearing,n_lumbar,junction_tl_in_fov,junction_ls_in_fov,fused_mask_representation,"
                    "review_queue,notes").split(",")
HARVEST_COLUMNS = ("source,case,patient_key,subtype,castellvi,four_lumbar,lumbar_rib,truth_tier,labeller_a,labeller_b,"
                   "agree,n_thoracic_rib_bearing,n_lumbar,junction_tl_in_fov,junction_ls_in_fov,fused_mask_representation,"
                   "real_frames,notes").split(",")
SELECTION_COLUMNS = ["person", "collection", "case", "variant", "tier", "role", "fold"]
FAIL = "SPINEPS ids cannot be read as VerSe names"
CASE_IDS = ("verse100", "verse200", "verse300", "verse401", "B100", "B200", "B400", "amos_0001", "TS_s0001", "case1",
            "RibFrac1", "liver_1")
KEY_PREFIXES = re.compile(r"\b(verse|ctsp|ts|cobra|amos22|carmlspine|ctspine1k|ribfrac|deepfluoro):")


def write_csv(path, columns, rows):
    pack.write_csv(path, columns, rows)


def ctd_json(path, ids):
    """A TPTBox POI ctd: a header with zoom, origin and rotation, then {id: {"50": [x, y, z]}}."""
    header = {"direction": ["R", "A", "S"], "zoom": [1.0, 1.0, 1.0], "origin": [0.0, 0.0, 0.0],
              "rotation": [[1, 0, 0], [0, 1, 0], [0, 0, 1]], "format": "POI"}
    points = {str(i): {"50": [1.0, 1.0, float(i)]} for i in ids}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps([header, points]), encoding="utf-8")


def ct_file(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return write_nifti(path, SMALL, 4, bytes(2 * 16 * 16 * 8))


def mask_file(path, ids, datatype=2, plant=(), body=None):
    """A mask of the given VerSe ids with extra (id, count) runs planted at the start."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    body = bytearray(body if body is not None else pattern(SMALL, ids))
    at = 0
    for value, count in plant:
        body[at:at + count] = bytes([value]) * count
        at += count
    if datatype == 2:
        return write_nifti(path, SMALL, 2, bytes(body))
    return write_nifti(path, SMALL, datatype, list(body))


def touch(path, text="x"):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")
    return Path(path)


class Tree(unittest.TestCase):
    """A selection of fourteen train and test rows over every store the records name, a holdout of two
    persons, the records, a G3 split and a validation rule, all under one temporary directory."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.data, self.home, self.out = self.tmp / "data", self.tmp / "home", self.tmp / "out"
        self.landing = self.data / "flexray_pack"
        self.harvest = self.data / "anomaly_harvest"
        self.selection = self.tmp / "selection.csv"
        self.holdout = self.tmp / "holdout.json"
        self.registry = self.tmp / "registry.csv"
        self.g3 = self.tmp / "split_final.json"
        self.validation = self.tmp / "validation.json"
        self.build()

    # ---- the tree
    def build(self):
        rows = []

        def select(person, collection, case, variant, role, tier="", fold=""):
            rows.append({"person": person, "collection": collection, "case": case, "variant": variant, "tier": tier,
                         "role": role, "fold": fold})

        unified = self.home / "VerSeFusion" / "data" / "unified"
        for case, ids in (("verse100", WITH_L6), ("verse200", NORMAL), ("verse300", WITH_T13), ("verse401", NORMAL),
                          ("verse402", NORMAL)):
            ct_file(unified / f"scan-{case}" / f"scan-{case}_ct.nii.gz")
            mask_file(unified / f"scan-{case}" / f"scan-{case}_msk.nii.gz", ids)
            ctd_json(self.home / "bench_ts" / "spineps" / "native" / f"VERSE_{case}_ctd.json", [i for i in ids if i != 1])
        select("verse:verse100", "verse", "verse100", "L6", "train", "read")
        select("verse:verse200", "verse", "verse200", "normal", "train", "", "1")
        select("verse:verse300", "verse", "verse300", "T13", "train", "read")
        ctsp = self.home / "data" / "CTSpinoPelvic1K"
        ct_file(ctsp / "ct" / "0001_ct.nii.gz")
        mask_file(ctsp / "labels" / "0001_label.nii.gz", NORMAL[:-1] + [25], plant=((29, 12),))
        ctd_json(self.data / "spineps" / "ctsp" / "CTSP_0001_ctd.json", NORMAL)
        select("ctsp:0001", "ctsp", "0001", "L6", "train", "read")
        # the holdout's CTSP label is int16 with one value past 255: refused high_bytes, a test-gate row
        ct_file(ctsp / "ct" / "0005_ct.nii.gz")
        values = list(pattern(SMALL, NORMAL))
        values[0] = 300
        write_nifti(ctsp / "labels" / "0005_label.nii.gz", SMALL, 4, values)
        # TotalSegmentator: s0001's CT from the bench's cases.csv, s0003's from the corpus folder; the relabelled
        # store first, the bench's native store (raw ids) only as the fallback, never segmentations/
        bench = self.home / "bench_ts"
        relabel = self.data / "spineps" / "ctd_relabel" / "bench_ts_native"
        native = bench / "spineps" / "native"
        ct_file(bench / "cts" / "s0001.nii.gz")
        ct_file(self.home / "data" / "TotalSegmentator" / "s0001" / "ct.nii.gz")
        write_csv(touch(bench / "cases.csv"), ["case", "ct"], [{"case": "TS_s0001", "ct": str(bench / "cts" / "s0001.nii.gz")}])
        mask_file(relabel / "TS_s0001_seg-vert_msk.nii.gz", NORMAL[:-1])
        ctd_json(relabel / "TS_s0001_ctd.json", NORMAL[:-1])
        mask_file(native / "TS_s0001_seg-vert_msk.nii.gz", list(range(1, 24)))
        for subject in ("s0002", "s0003"):
            ct_file(self.home / "data" / "TotalSegmentator" / subject / "ct.nii.gz")
            touch(self.home / "data" / "TotalSegmentator" / subject / "segmentations" / "vertebrae_L1.nii.gz")
        mask_file(native / "TS_s0002_seg-vert_msk.nii.gz", list(range(1, 24)))
        ctd_json(native / "TS_s0002_ctd.json", NORMAL)
        mask_file(relabel / "TS_s0003_seg-vert_msk.nii.gz", [i for i in NORMAL if i >= 8])
        ctd_json(relabel / "TS_s0003_ctd.json", NORMAL)
        select("ts:s0001", "totalsegmentator", "TS_s0001", "normal", "train")
        select("ts:s0002", "totalsegmentator", "TS_s0002", "L6", "train", "two-labeller")
        select("ts:s0003", "totalsegmentator", "TS_s0003", "normal", "train")
        # COBRA2026: B100 by the lstv store, B200 .mha only, B300 a NIfTI with a raw-id mask only, B400 Varian
        cobra = self.data / "cobra2026"
        for case in ("B100", "B200", "B300", "B400"):
            touch(cobra / "cases" / case / "ct_def.mha")
        ct_file(cobra / "lstv" / "nifti" / "B100_ct.nii.gz")
        mask_file(cobra / "lstv" / "seg" / "B100_seg-vert_msk.nii.gz", NORMAL)
        ctd_json(cobra / "lstv" / "seg" / "B100_ctd.json", NORMAL)
        ct_file(cobra / "seg" / "B300" / "ct_def.nii.gz")
        mask_file(cobra / "seg" / "spineps" / "B300_seg-vert_msk.nii.gz", list(range(1, 24)))
        touch(self.harvest / "cobra" / "ts" / "B300.nii.gz")
        ct_file(cobra / "varian" / "nifti" / "B400_ct.nii.gz")
        mask_file(self.data / "spineps" / "cobra_varian" / "B400_seg-vert_msk.nii.gz", NORMAL, datatype=4, plant=((80, 30),))
        for case, variant in (("B100", "normal"), ("B200", "L6"), ("B300", "normal"), ("B400", "normal")):
            select(f"cobra:{case}", "cobra2026", case, variant, "test")
        # the acquisition screen's amos22: 0001 by cases.csv before the nifti folder, 0002 by the folder, 0003 nowhere,
        # 0004 a mask the guard never listed; its seg/<case>/ts folder is never read
        amos = self.harvest / "amos22"
        ct_file(amos / "raw" / "amos_0001.nii.gz")
        ct_file(self.data / "amos22" / "nifti" / "amos_0001_ct.nii.gz")
        ct_file(self.data / "amos22" / "nifti" / "amos_0002_ct.nii.gz")
        ct_file(self.data / "amos22" / "nifti" / "amos_0004_ct.nii.gz")
        write_csv(touch(amos / "cases.csv"), ["case", "ct", "source", "patient_key", "extent_mm", "dz_mm", "pixel_sha1"],
                  [{"case": "amos_0001", "ct": str(amos / "raw" / "amos_0001.nii.gz"), "source": "amos22",
                    "patient_key": "amos22:0001", "extent_mm": "300", "dz_mm": "1.0", "pixel_sha1": "abc"}])
        mask_file(amos / "spineps" / "amos_0001_seg-vert_msk.nii.gz", [i for i in NORMAL if i != 19])
        ctd_json(amos / "spineps" / "amos_0001_ctd.json", [i for i in NORMAL if i != 19])
        mask_file(amos / "spineps" / "amos_0002_seg-vert_msk.nii.gz", WITH_L6, plant=((27, 6), (40, 4)))
        mask_file(amos / "spineps" / "amos_0004_seg-vert_msk.nii.gz", NORMAL)
        touch(amos / "seg" / "amos_0001" / "ts" / "sacrum.nii.gz")
        write_csv(touch(amos / "rows.csv"), HARVEST_COLUMNS, [
            {"source": "amos22", "case": "amos_0001", "patient_key": "amos22:0001", "subtype": "none", "junction_ls_in_fov": "True"},
            {"source": "amos22", "case": "amos_0002", "patient_key": "amos22:0002", "subtype": "L6", "junction_ls_in_fov": "False"},
            {"source": "amos22", "case": "amos_0004", "patient_key": "", "subtype": "none", "junction_ls_in_fov": "True"}])
        write_csv(touch(self.harvest / "totalsegmentator_v2" / "rows.csv"), HARVEST_COLUMNS, [
            {"source": "totalsegmentator_v2", "case": "TS_s0009", "patient_key": "totalsegmentator_v2:s0009",
             "subtype": "lumbar_rib", "junction_ls_in_fov": "True"},
            {"source": "totalsegmentator_v2", "case": "TS_s0001", "patient_key": "totalsegmentator_v2:s0001",
             "subtype": "harvest-says-otherwise", "junction_ls_in_fov": "False"}])
        select("amos22:0001", "amos22", "amos_0001", "normal", "train")
        select("amos22:0002", "amos22", "amos_0002", "L6", "train", "two-labeller")
        select("amos22:0003", "amos22", "amos_0003", "normal", "train")
        select("amos22:0004", "amos22", "amos_0004", "normal", "train")
        select("deepfluoro:17-1882", "deepfluoro", "17-1882", "normal", "test")
        carm = self.data / "carmlspine"
        ct_file(carm / "nifti" / "case1_ct.nii.gz")
        write_csv(touch(carm / "cases.csv"), ["case", "ct"], [{"case": "case1", "ct": str(carm / "nifti" / "case1_ct.nii.gz")}])
        mask_file(carm / "spineps" / "case1_seg-vert_msk.nii.gz", NORMAL)
        select("carmlspine:case1", "carmlspine", "case1", "normal", "test")
        other = self.harvest / "other_ct"
        ct_file(self.data / "ctspine1k" / "raw_data" / "volumes" / "MSD-T10" / "liver_1.nii.gz")
        mask_file(self.data / "ctspine1k" / "raw_data" / "labels" / "MSD-T10" / "liver_1_seg.nii.gz", NORMAL)
        mask_file(other / "ctspine1k" / "spineps" / "MSD-T10__liver_1_seg-vert_msk_veridah.nii.gz", NORMAL)
        mask_file(other / "ctspine1k" / "spineps" / "MSD-T10__liver_1_seg-vert_msk.nii.gz", list(range(1, 24)))
        ctd_json(other / "ctspine1k" / "spineps" / "MSD-T10__liver_1_ctd.json", NORMAL)
        select("ctspine1k:MSD-T10/liver_1", "ctspine1k", "MSD-T10/liver_1", "normal", "train")
        ct_file(self.data / "ribfrac" / "images" / "RibFrac1-image.nii.gz")
        mask_file(other / "ribfrac" / "spineps" / "RibFrac1_seg-vert_msk.nii.gz", NORMAL)
        touch(other / "ribfrac" / "ts_total" / "RibFrac1.nii.gz")
        select("ribfrac:RibFrac1", "ribfrac", "RibFrac1", "normal", "train")
        write_csv(self.selection, SELECTION_COLUMNS, rows)
        self.holdout.write_text(json.dumps({
            "frozen": "test", "rule": {}, "inputs": {},
            "persons": [{"person": "verse:verse400", "variant": "L6", "release": "2019", "stratum": "L6", "scans": ["verse401", "verse402"]},
                        {"person": "ctsp:0005", "variant": "L6", "release": "ctspinopelvic1k", "stratum": "reader-confirmed L6", "scans": ["0005"]}],
            "folds": [{"person": "verse:verse200", "fold": 1}], "disputed": []}), encoding="utf-8")
        registry = {"verse:verse100": ("L6", "True"), "verse:verse200": ("none", "True"), "verse:verse300": ("T13", "True"),
                    "verse:verse400": ("L6", "True"), "ctsp:0001": ("L6", "True"), "ctsp:0005": ("L6", "True"),
                    "ts:s0001": ("castellvi_I_II", "True"), "ts:s0002": ("L6", "False"), "ts:s0003": ("none", "True"),
                    "cobra:B100": ("none", "True"), "cobra:B200": ("L6", "True"), "cobra:B300": ("none", "True"),
                    "cobra:B400": ("none", "True"), "carmlspine:case1": ("none", "True"),
                    "ctspine1k:MSD-T10/liver_1": ("none", "True"), "ribfrac:RibFrac1": ("none", "False")}
        write_csv(self.registry, REGISTRY_COLUMNS,
                  [{"patient_key": key, "subtype": subtype, "junction_ls_in_fov": ls} for key, (subtype, ls) in registry.items()])
        self.g3.write_text(json.dumps({
            "_format": "g3-person-split-v1",
            "side_of_person": {"verse:verse100": "train", "verse:verse300": "val", "ts:s0001": "test", "ts:s0003": "val",
                               "ctsp:group0001": "test", "cobra:B100": "test", "verse:verse200": "train"},
            "group_of": {"ctsp:0001": "ctsp:group0001"},
            "raw_to_group": {"ts:TS_s0001": "ts:s0001"},
            "item_side": {}}), encoding="utf-8")
        self.write_validation(None)

    def write_validation(self, drawn, counts=None):
        self.validation.write_text(json.dumps({
            "frozen": "test", "why": "test",
            "rule": {"rank": "first 8 bytes, big-endian, of sha256 over the UTF-8 of 'schwingnet-anomaly-validation|' + salt + '|' + person",
                     "salt": "test-salt", "counts": counts or {"T13": 1, "L6": 1, "normal": 1}, "pool": "the test's"},
            "drawn": drawn}), encoding="utf-8")

    # ---- running the tool
    def run_pack(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = pack.main([str(a) for a in argv])
        return code, out.getvalue(), err.getvalue()

    def rows(self, **extra):
        argv = ["rows", "--selection", self.selection, "--holdout", self.holdout, "--data", self.data, "--home", self.home,
                "--registry", self.registry, "--harvest", self.harvest, "--out", self.out]
        for key, value in extra.items():
            argv += [f"--{key}", value]
        code, text, err = self.run_pack(*argv)
        self.assertEqual((code, err), (0, ""), err)
        return {row["sample_id"]: row for row in pack.read_csv(self.out / "rows.csv")}, text

    def guard_file(self, rows, fails=None, unlisted=()):
        """guard.txt as spineps_ids.py check --strict prints it over guard-list.txt: OK for every SPINEPS mask
        but the ones failed by verdict or left unlisted, plus a warning and a traceback line it must ignore."""
        fails = fails or {}
        lines = ["WARNING something: misnamed_1_2_levels at a level", "Traceback (most recent call last):"]
        for row in rows.values():
            if row["status"] != "ok" or row["mask_kind"] != "spineps" or row["case"] in unlisted:
                continue
            verdict = fails.get(row["case"])
            if verdict:
                lines.append(f"FAIL {row['mask']}: {FAIL} [{verdict}]: VERIDAH's ctd skips T12 between T11 and L1 at a "
                             "normal spacing (28.9 mm, local 28.5 mm). Name this case from another labeller.")
            else:
                lines.append(f"OK   {row['mask']}: verse_ok")
        lines.append(f"OK   {self.tmp}/elsewhere_seg-vert_msk.nii.gz: empty")
        return touch(self.out / "guard.txt", "\n".join(lines) + "\n")

    DEFAULT_FAILS = {"TS_s0002": "raw_or_scrambled", "RibFrac1": "veridah_skipped_name"}

    def chain(self, distrust="ctsp", uncounted="pack", fails=None, unlisted=("amos_0004",)):
        """rows, guard-list, rewrite, split, trainval, the two manifests and size, as the stage runs them."""
        rows, rows_text = self.rows()
        code, guard_text, err = self.run_pack("guard-list", "--rows", self.out / "rows.csv", "--out", self.out)
        self.assertEqual((code, err), (0, ""))
        guard = self.guard_file(rows, self.DEFAULT_FAILS if fails is None else fails, unlisted)
        code, masks_text, err = self.run_pack("rewrite", "--rows", self.out / "rows.csv", "--guard", guard,
                                              "--masks", self.landing / "masks", "--out", self.out)
        self.assertEqual((code, err), (0, ""), err)
        code, splits_text, err = self.run_pack("split", "--rows", self.out / "rows.csv", "--masks", self.out / "masks.csv",
                                               "--g3", self.g3, "--validation", self.validation, "--out", self.out,
                                               "--distrust", distrust, "--uncounted", uncounted)
        self.assertEqual((code, err), (0, ""), err)
        code, trainval_text, err = self.run_pack("trainval", "--splits", self.out / "splits.csv", "--out", self.out)
        self.assertEqual((code, err), (0, ""))
        manifests = {}
        for dataset in pack.DATASETS:
            code, text, err = self.run_pack("manifest", "--splits", self.out / "splits.csv", "--masks", self.out / "masks.csv",
                                            "--rows", self.out / "rows.csv", "--dataset", dataset, "--hu=-1000,2000",
                                            "--out", self.out)
            self.assertEqual((code, err), (0, ""), err)
            manifests[dataset] = text
        code, size_text, err = self.run_pack("size", "--rows", self.out / "rows.csv", "--landing", self.landing)
        self.assertEqual((code, err), (0, ""))
        return {"rows": rows, "masks": {m["sample_id"]: m for m in pack.read_csv(self.out / "masks.csv")},
                "splits": {s["sample_id"]: s for s in pack.read_csv(self.out / "splits.csv")},
                "texts": {"rows": rows_text, "guard-list": guard_text, "masks": masks_text, "splits": splits_text,
                          "trainval": trainval_text, "size": size_text, **manifests}}

    @staticmethod
    def by_case(table):
        return {entry["case"]: entry for entry in table.values()}


class RowsTest(Tree):
    def test_resolve_each_collection_takes_the_expert_mask_first_and_never_a_ts_store(self):
        rows, text = self.rows()
        by = self.by_case(rows)
        self.assertEqual((by["verse100"]["status"], by["verse100"]["mask_kind"]), ("ok", "release"))
        self.assertTrue(by["verse100"]["mask"].endswith("scan-verse100_msk.nii.gz"))
        self.assertTrue(by["verse100"]["ctd"].endswith("VERSE_verse100_ctd.json"))
        self.assertEqual(by["0001"]["mask_kind"], "release")
        self.assertTrue(by["0001"]["mask"].endswith("labels/0001_label.nii.gz"))
        self.assertTrue(by["0001"]["ctd"].endswith("spineps/ctsp/CTSP_0001_ctd.json"))
        # the relabelled copy before the bench's native store, and the native store only as the fallback
        self.assertIn("ctd_relabel/bench_ts_native/TS_s0001_seg-vert_msk.nii.gz", by["TS_s0001"]["mask"])
        self.assertIn("bench_ts/spineps/native/TS_s0002_seg-vert_msk.nii.gz", by["TS_s0002"]["mask"])
        self.assertEqual(by["TS_s0001"]["mask_kind"], "spineps")
        self.assertEqual(by["TS_s0001"]["ct"], str(self.home / "bench_ts" / "cts" / "s0001.nii.gz"))
        self.assertEqual(by["TS_s0003"]["ct"], str(self.home / "data" / "TotalSegmentator" / "s0003" / "ct.nii.gz"))
        self.assertIn("cobra2026/lstv/seg/B100_seg-vert_msk.nii.gz", by["B100"]["mask"])
        self.assertIn("spineps/cobra_varian/B400_seg-vert_msk.nii.gz", by["B400"]["mask"])
        self.assertEqual(by["B400"]["ct"], str(self.data / "cobra2026" / "varian" / "nifti" / "B400_ct.nii.gz"))
        # B300 has a NIfTI but its only mask is in seg/spineps, whose ids are raw: never read
        self.assertEqual((by["B300"]["status"], by["B300"]["mask"]), ("no_mask", ""))
        self.assertIn("anomaly_harvest/amos22/spineps/amos_0001_seg-vert_msk.nii.gz", by["amos_0001"]["mask"])
        self.assertIn("carmlspine/spineps/case1_seg-vert_msk.nii.gz", by["case1"]["mask"])
        self.assertTrue(by["MSD-T10/liver_1"]["mask"].endswith("MSD-T10__liver_1_seg-vert_msk_veridah.nii.gz"))
        self.assertTrue(by["MSD-T10/liver_1"]["ct"].endswith("raw_data/volumes/MSD-T10/liver_1.nii.gz"))
        self.assertTrue(by["RibFrac1"]["mask"].endswith("other_ct/ribfrac/spineps/RibFrac1_seg-vert_msk.nii.gz"))
        self.assertTrue(by["RibFrac1"]["ct"].endswith("ribfrac/images/RibFrac1-image.nii.gz"))
        for row in rows.values():
            for path in (row["ct"], row["mask"], row["ctd"]):
                self.assertNotRegex(path, r"/ts/|segmentations/|seg/spineps/|ts_total/|raw_data/labels/", path)
        self.assertIn("- masks: release 7, spineps 11", text)
        self.assertEqual(sum(row["status"] == "ok" for row in rows.values()), 18)

    def test_harvest_ct_comes_from_cases_csv_before_the_nifti_folder(self):
        by = self.by_case(self.rows()[0])
        self.assertEqual(by["amos_0001"]["ct"], str(self.harvest / "amos22" / "raw" / "amos_0001.nii.gz"))
        self.assertEqual(by["amos_0002"]["ct"], str(self.data / "amos22" / "nifti" / "amos_0002_ct.nii.gz"))
        self.assertEqual((by["amos_0003"]["status"], by["amos_0003"]["ct"]), ("no_ct", ""))
        self.assertEqual(by["amos_0001"]["ls_record"], "True")
        self.assertEqual(by["amos_0002"]["subtype"], "L6")

    def test_cobra_mha_only_is_no_nifti(self):
        rows, text = self.rows()
        by = self.by_case(rows)
        self.assertEqual((by["B200"]["status"], by["B200"]["ct"], by["B200"]["mask"]), ("no_nifti", "", ""))
        self.assertEqual(by["B100"]["status"], "ok")
        self.assertIn("| cobra2026 | test | 4 | 2 | 0 | 1 | 1 | 0 | 0 |", text)
        # a CT whose bytes are no NIfTI is no_nifti too, found by the header census
        bad = self.data / "cobra2026" / "lstv" / "nifti" / "B100_ct.nii.gz"
        bad.write_bytes(b"not a volume at all" * 30)
        by = self.by_case(self.rows()[0])
        self.assertEqual(by["B100"]["status"], "no_nifti")

    def test_unknown_collection_is_counted_not_fatal(self):
        rows, text = self.rows()
        self.assertEqual(self.by_case(rows)["17-1882"]["status"], "unknown_collection")
        self.assertIn("unknown_collection 1", text)
        self.assertEqual(pack.resolve({"collection": "geneva", "case": "x"}, self.data, self.home)["status"], "unknown_collection")

    def test_holdout_rows_one_per_scan(self):
        held = pack.holdout_rows(json.loads(self.holdout.read_text()))
        self.assertEqual([(row["person"], row["collection"], row["case"], row["variant"], row["role"]) for row in held],
                         [("verse:verse400", "verse", "verse401", "L6", "holdout"), ("verse:verse400", "verse", "verse402", "L6", "holdout"),
                          ("ctsp:0005", "ctsp", "0005", "L6", "holdout")])
        rows, text = self.rows()
        by = self.by_case(rows)
        self.assertEqual([by[c]["status"] for c in ("verse401", "verse402", "0005")], ["ok", "ok", "ok"])
        self.assertEqual(by["verse401"]["subtype"], "L6")
        self.assertEqual(by["verse200"]["fold"], "1")
        self.assertIn("holdout: 2 persons, 3 scans", text)
        self.assertIn("| verse | holdout | 2 |", text)

    def test_record_flags_read_the_registry_and_every_harvest_rows_csv(self):
        flags = pack.record_flags(self.registry, self.harvest)
        self.assertEqual(flags["verse:verse100"], (True, "L6"))
        self.assertEqual(flags["ts:s0002"], (False, "L6"))
        self.assertEqual(flags["amos22:0001"], (True, "none"))
        self.assertEqual(flags["amos22:0002"], (False, "L6"))
        # the alias totalsegmentator_v2 -> ts, and the registry's row before a harvest's for the same person
        self.assertEqual(flags["ts:s0009"], (True, "lumbar_rib"))
        self.assertEqual(flags["ts:s0001"], (True, "castellvi_I_II"))
        # a harvest row with no patient_key is keyed by its collection and case
        self.assertEqual(flags["amos22:amos_0004"], (True, "none"))
        self.assertEqual(pack.registry_key("totalsegmentator_v2:s0009"), "ts:s0009")
        self.assertEqual(pack.registry_key("cobra:B100"), "cobra:B100")

    def test_rows_records_the_segmenter_and_refuses_moose(self):
        rows, text = self.rows(segmenter="spineps")
        self.assertTrue(all(row["segmenter"] == "spineps" for row in rows.values()))
        self.assertIn("- segmenter: spineps", text)
        code, out, err = self.run_pack("rows", "--selection", self.selection, "--holdout", self.holdout, "--data", self.data,
                                       "--home", self.home, "--registry", self.registry, "--harvest", self.harvest,
                                       "--out", self.out / "moose", "--segmenter", "moose")
        self.assertEqual((code, out), (1, ""))
        self.assertEqual(err, "FAILED: the moose segmenter is not built for this stage: no MOOSE mask exists on the grid\n")
        self.assertFalse((self.out / "moose").exists())

    def test_sample_id_never_starts_with_underscore(self):
        self.assertEqual(pack.sample_id("verse", "verse100"), "verse__verse100")
        self.assertEqual(pack.sample_id("ctspine1k", "MSD-T10/liver_1"), "ctspine1k__MSD-T10__liver_1")
        self.assertEqual(pack.sample_id("amos22", "amos 0001:a"), "amos22__amos_0001_a")
        for collection, case in (("", "_x"), ("_a", "b")):
            self.assertFalse(pack.sample_id(collection, case).startswith("_"))
        rows, _ = self.rows()
        self.assertTrue(all(not sid.startswith("_") and re.fullmatch(r"[A-Za-z0-9_.-]+", sid) for sid in rows))


class GuardAndMasksTest(Tree):
    def test_read_guard_takes_ok_lines_only_and_counts_skipped_names_apart(self):
        done = self.chain()
        guard = pack.read_guard(self.out / "guard.txt")
        by = self.by_case(done["rows"])
        self.assertEqual(guard[by["TS_s0001"]["mask"]], (True, "verse_ok"))
        self.assertEqual(guard[by["TS_s0002"]["mask"]], (False, "raw_or_scrambled"))
        self.assertEqual(guard[by["RibFrac1"]["mask"]], (False, "veridah_skipped_name"))
        self.assertNotIn(by["amos_0004"]["mask"], guard)
        self.assertEqual(guard[f"{self.tmp}/elsewhere_seg-vert_msk.nii.gz"], (True, "empty"))
        self.assertFalse(any("WARNING" in key or "Traceback" in key for key in guard))
        masks = self.by_case(done["masks"])
        self.assertEqual((masks["TS_s0002"]["status"], masks["TS_s0002"]["reason"]), ("guard_refused", "raw_or_scrambled"))
        self.assertEqual((masks["RibFrac1"]["status"], masks["RibFrac1"]["reason"]), ("guard_refused", "veridah_skipped_name"))
        self.assertEqual((masks["amos_0004"]["status"], masks["amos_0004"]["reason"]), ("guard_refused", "guard_unlisted"))
        self.assertEqual(masks["TS_s0001"]["status"], "rewritten")
        # a release mask needs no guard line
        self.assertEqual(masks["verse100"]["status"], "rewritten")
        self.assertIn("- refused by the guard 3: raw_or_scrambled 1, guard_unlisted 1; veridah_skipped_name 1 apart", done["texts"]["masks"])
        self.assertFalse((self.landing / "masks" / "totalsegmentator__TS_s0002.nii.gz").exists())
        listed = (self.out / "guard-list.txt").read_text().splitlines()
        self.assertEqual(len(listed), 11)
        self.assertEqual(listed, sorted(set(listed)))
        self.assertIn("- 11 SPINEPS masks", done["texts"]["guard-list"])

    def test_countable_complete_and_gap_from_record_mask_and_ctd(self):
        canonical = lambda ids: [pack.VERSE_TO_CANONICAL[i] for i in ids]  # noqa: E731
        both = pack.countable_of(canonical(NORMAL), set(), False)
        self.assertEqual((both["top_from"], both["sacrum_from"], both["gap"], both["countable"], both["complete"], both["top"]),
                         ("mask", "mask", False, True, True, 2))
        record = pack.countable_of(canonical(NORMAL[:-1]), set(), True)
        self.assertEqual((record["sacrum_from"], record["countable"], record["complete"]), ("record", True, False))
        gap = pack.countable_of(canonical([i for i in NORMAL if i != 19]), set(), False)
        self.assertEqual((gap["gap"], gap["countable"], gap["complete"]), (True, True, False))
        from_ctd = pack.countable_of(canonical([i for i in NORMAL if i >= 8]), {2, 26}, False)
        self.assertEqual((from_ctd["top_from"], from_ctd["countable"], from_ctd["complete"], from_ctd["top"]), ("ctd", True, False, 8))
        sacrum_ctd = pack.countable_of(canonical(NORMAL[:-1]), {26}, False)
        self.assertEqual((sacrum_ctd["sacrum_from"], sacrum_ctd["countable"]), ("ctd", True))
        none = pack.countable_of(canonical(NORMAL[:-1]), set(), False)
        self.assertEqual((none["top_from"], none["sacrum_from"], none["countable"]), ("mask", "none", False))
        self.assertEqual(pack.countable_of(canonical([20, 21, 22]), set(), True)["top_from"], "none")
        # C1 counts as the top too; T13 and L6 absent are no gap, present they are no gap either
        self.assertEqual(pack.countable_of(canonical([1] + NORMAL), set(), False)["complete"], True)
        # C1 present with C2 absent is a gap, as any missing body between the ends is
        self.assertEqual(pack.countable_of(canonical([1] + NORMAL[1:]), set(), False)["gap"], True)
        self.assertEqual(pack.countable_of(canonical(WITH_T13), set(), False)["gap"], False)
        self.assertEqual(pack.countable_of(canonical(WITH_L6), set(), False)["complete"], True)
        # through the chain: the record-only sacrum, the T12 gap and the C2 from the ctd are countable and partial
        masks = self.by_case(self.chain()["masks"])
        self.assertEqual((masks["TS_s0001"]["sacrum_from"], masks["TS_s0001"]["countable"], masks["TS_s0001"]["complete"]), ("record", "True", "False"))
        self.assertEqual((masks["amos_0001"]["gap"], masks["amos_0001"]["complete"]), ("True", "False"))
        self.assertEqual((masks["TS_s0003"]["top_from"], masks["TS_s0003"]["complete"]), ("ctd", "False"))
        self.assertEqual((masks["verse100"]["complete"], masks["0001"]["complete"], masks["B100"]["complete"]), ("True", "True", "True"))
        self.assertEqual(pack.ctd_ids(self.data / "spineps" / "ctsp" / "CTSP_0001_ctd.json"), set(NORMAL))
        self.assertIsNone(pack.ctd_ids(""))
        self.assertIsNone(pack.ctd_ids(self.tmp / "absent.json"))

    def test_rewrite_counts_dropped_ids_metal_and_the_retired_s1_and_resumes_by_sidecar(self):
        done = self.chain()
        masks = self.by_case(done["masks"])
        self.assertEqual(masks["0001"]["ids_out"].split()[-1], "27")
        self.assertIn("29", masks["0001"]["ids_in"].split())
        self.assertEqual(masks["amos_0002"]["dropped"], "27:6 40:4")
        self.assertEqual((masks["B400"]["metal_voxels"], masks["B400"]["dropped"]), ("30", "80:30"))
        self.assertEqual((masks["0005"]["status"], masks["0005"]["reason"]), ("refused", "high_bytes"))
        text = done["texts"]["masks"]
        self.assertIn("- rewritten 14 (release 6, spineps 8); kept 0 from an earlier run", text)
        self.assertIn("- unreadable 1: high_bytes 1", text)
        self.assertIn("- dropped ids: 27 in 1 masks (6 voxels), 40 in 1 masks (4 voxels), 80 in 1 masks (30 voxels)", text)
        self.assertIn("- metal: 1 masks, 0 of them 5 ml or more", text)
        self.assertIn("- seconds: median ", text)
        self.assertIn("over 14 masks rewritten in this run", text)
        sidecar = self.landing / "masks" / "cobra2026__B400.json"
        record = json.loads(sidecar.read_text())
        self.assertEqual((record["metal_voxels"], record["ids_out"][-1], record["dims"]), (30, 27, [16, 16, 8]))
        written = (self.landing / "masks" / "cobra2026__B400.nii.gz").read_bytes()
        # a second run writes nothing and keeps every mask; a source touched since is written again
        time.sleep(0.02)
        source = Path(masks["B100"]["src"])
        os.utime(source, None)
        code, text, err = self.run_pack("rewrite", "--rows", self.out / "rows.csv", "--guard", self.out / "guard.txt",
                                        "--masks", self.landing / "masks", "--out", self.out)
        self.assertEqual((code, err), (0, ""))
        self.assertIn("- rewritten 1 (release 0, spineps 1); kept 13 from an earlier run", text)
        again = self.by_case({m["sample_id"]: m for m in pack.read_csv(self.out / "masks.csv")})
        self.assertEqual((again["B100"]["status"], again["B400"]["status"]), ("rewritten", "kept"))
        self.assertEqual(again["B400"]["countable"], "True")
        self.assertEqual((self.landing / "masks" / "cobra2026__B400.nii.gz").read_bytes(), written)

    def test_testgate_counts_unresolved_and_refused_test_and_holdout_rows(self):
        self.rows()
        code, text, err = self.run_pack("testgate", "--rows", self.out / "rows.csv")
        self.assertEqual((code, text, err), (0, "3\n", ""))
        self.chain()
        code, text, err = self.run_pack("testgate", "--rows", self.out / "rows.csv", "--masks", self.out / "masks.csv")
        self.assertEqual((code, text), (0, "4\n"))


class SplitTest(Tree):
    def test_g3_key_matches_make_split_norm_key(self):
        # the expectations are spinesurg-ct-nnunet tools/make_split.py norm_key's own, case by case
        cases = {"ts:TS_s0049": "ts:s0049", "totalsegmentator:s0050": "ts:s0050", "totalseg:TS_s1": "ts:s1",
                 "ctsp:5": "ctsp:0005", "ctsp:0376": "ctsp:0376", "verse:809": "verse:verse809", "verse:verse809": "verse:verse809",
                 "gl:419": "verse:gl419", "case:121": "carmlspine:case121", "carmlspine_real:case1": "carmlspine:case1",
                 "geneva_hip:x": "geneva:x", "nhanes:12": "nhanes:00012", "sim:a": "spinalai:a", "cobra:B127": "cobra:B127",
                 " verse:verse1 ": "verse:verse1", "nocolon": "nocolon", "ctspine1k:MSD-T10/liver_1": "ctspine1k:MSD-T10/liver_1"}
        for raw, wanted in cases.items():
            self.assertEqual(pack.g3_key(raw), wanted, raw)

    def test_g3_side_resolves_group_of_and_raw_to_group(self):
        g3 = json.loads(self.g3.read_text())
        self.assertEqual(pack.g3_side("ts:TS_s0001", g3), "test")
        self.assertEqual(pack.g3_side("ts:s0001", g3), "test")
        self.assertEqual(pack.g3_side("ctsp:1", g3), "test")
        self.assertEqual(pack.g3_side("ctsp:0001", g3), "test")
        self.assertEqual(pack.g3_side("verse:300", g3), "val")
        self.assertEqual(pack.g3_side("verse:verse100", g3), "train")
        self.assertIsNone(pack.g3_side("ribfrac:RibFrac1", g3))
        self.assertIsNone(pack.g3_side("ctspine1k:MSD-T10/liver_1", g3))
        self.assertIsNone(pack.g3_side("verse:verse100", {}))

    def test_g3_transitional_is_the_subtype_or_the_variant_and_goes_to_the_g3_excluded_split(self):
        self.assertTrue(pack.transitional("normal", "castellvi_I_II"))
        self.assertTrue(pack.transitional("normal", "sacralised_L5_fused"))
        self.assertTrue(pack.transitional("L6", ""))
        self.assertTrue(pack.transitional("both_L6_T13", "none"))
        self.assertFalse(pack.transitional("normal", "none"))
        self.assertFalse(pack.transitional("normal", "ordinary"))
        self.assertFalse(pack.transitional("normal", ""))
        done = self.chain()
        splits = self.by_case(done["splits"])
        self.assertEqual((splits["verse300"]["split"], splits["verse300"]["why"]), ("g3_excluded", "transitional on G3 val"))
        self.assertEqual((splits["TS_s0001"]["split"], splits["TS_s0001"]["why"]), ("g3_excluded", "transitional on G3 test"))
        self.assertIn(splits["TS_s0003"]["split"], ("train", "val"))
        self.assertEqual(splits["verse100"]["split"] in ("train", "val"), True)
        self.assertIn("- G3: 2 persons excluded, 1 of them variant normal", done["texts"]["splits"])
        # the uncounted and excluded splits are packed and listed, trained on by nothing
        self.assertIn("| verse | train | g3_excluded | complete | 1 | 0 | 1 | 0 | 0 | 1 |", done["texts"]["splits"])

    def test_validation_draw_is_per_variant_in_rank_order_without_fold_persons(self):
        pool = {"verse:a": "L6", "verse:b": "L6", "verse:c": "L6", "ts:d": "normal", "ts:e": "T13", "ts:f": "eleven"}
        rule = {"salt": "s", "counts": {"L6": 2, "normal": 1, "T13": 1, "four_lumbar": 1}}
        drawn, taken, short = pack.draw_validation(pool, rule)
        ranked = sorted(("verse:a", "verse:b", "verse:c"), key=lambda p: pack.validation_rank(p, "s"))
        self.assertEqual(drawn, set(ranked[:2]) | {"ts:d", "ts:e"})
        self.assertEqual(taken, {"L6": 2, "normal": 1, "T13": 1, "four_lumbar": 0})
        self.assertEqual(short, {"L6": 0, "normal": 0, "T13": 0, "four_lumbar": 1})
        self.assertEqual(pack.validation_rank("verse:a", "s"),
                         int.from_bytes(hashlib.sha256(b"schwingnet-anomaly-validation|s|verse:a").digest()[:8], "big"))
        self.assertEqual(pack.draw_digest(drawn), hashlib.sha256("\n".join(sorted(drawn)).encode()).hexdigest())
        self.assertEqual(pack.draw_digest(drawn)[:16], "e2fea3af3575c5b4")
        # through the chain: the pool is the countable train persons with no fold, not distrusted, not G3-excluded
        done = self.chain()
        splits = self.by_case(done["splits"])
        pool = {"verse:verse100": "L6", "amos22:0002": "L6", "ts:s0003": "normal", "amos22:0001": "normal",
                "ctspine1k:MSD-T10/liver_1": "normal"}
        drawn, taken, short = pack.draw_validation(pool, {"salt": "test-salt", "counts": {"T13": 1, "L6": 1, "normal": 1}})
        for entry in splits.values():
            if entry["person"] in pool:
                self.assertEqual(entry["split"], "val" if entry["person"] in drawn else "train", entry["person"])
        self.assertEqual(splits["verse200"]["split"], "train")
        self.assertEqual(sum(entry["split"] == "val" for entry in splits.values()), 2)
        self.assertIn(f"drawn T13 0 (short 1), L6 1, normal 1; sha256 {pack.draw_digest(drawn)[:16]}", done["texts"]["splits"])
        self.assertIn("- validation: salt test-salt; counts {\"T13\": 1, \"L6\": 1, \"normal\": 1}", done["texts"]["splits"])

    def test_distrusted_collection_is_uncounted_whatever_the_measure(self):
        splits = self.by_case(self.chain()["splits"])
        self.assertEqual((splits["0001"]["split"], splits["0001"]["why"], splits["0001"]["complete"]), ("uncounted", "distrusted", "True"))
        self.assertNotIn("0005", splits)
        # trusted, the CTSP L6 is a transitional person G3 places on test, so it is excluded, not trained on
        trusted = self.by_case(self.chain(distrust="")["splits"])
        self.assertEqual((trusted["0001"]["split"], trusted["0001"]["why"]), ("g3_excluded", "transitional on G3 test"))
        self.assertEqual(sum(entry["why"] == "distrusted" for entry in trusted.values()), 0)

    def test_uncounted_drop_switch(self):
        packed = self.chain()
        self.assertEqual(sorted(entry["case"] for entry in packed["splits"].values() if entry["split"] == "uncounted"), ["0001"])
        self.assertIn("- uncounted: distrusted 1, uncountable 0; packed, trained on by nothing", packed["texts"]["splits"])
        dropped = self.chain(uncounted="drop")
        self.assertEqual([entry for entry in dropped["splits"].values() if entry["split"] == "uncounted"], [])
        self.assertEqual(len(dropped["splits"]), len(packed["splits"]) - 1)
        self.assertIn("1 rows dropped by --uncounted drop", dropped["texts"]["splits"])

    def test_a_person_in_two_splits_of_one_package_exits_one(self):
        done = self.chain()
        rows = done["rows"]
        twin = dict(rows["verse__verse100"], sample_id="verse__verse199", case="verse199", role="test")
        rows["verse__verse199"] = twin
        pack.write_csv(self.out / "rows.csv", pack.ROW_COLUMNS, rows.values())
        masks = done["masks"]
        masks["verse__verse199"] = dict(masks["verse__verse100"], sample_id="verse__verse199", case="verse199", role="test")
        pack.write_csv(self.out / "masks.csv", pack.MASK_COLUMNS, masks.values())
        code, out, err = self.run_pack("split", "--rows", self.out / "rows.csv", "--masks", self.out / "masks.csv",
                                       "--g3", self.g3, "--validation", self.validation, "--out", self.out / "twin")
        self.assertEqual((code, out, err), (1, "", "FAILED: 1 persons sit in two splits of one package\n"))
        self.assertFalse((self.out / "twin" / "splits.csv").exists())
        # the same person complete in one package and partial in the other is no conflict
        masks["verse__verse199"]["complete"] = "False"
        pack.write_csv(self.out / "masks.csv", pack.MASK_COLUMNS, masks.values())
        code, out, err = self.run_pack("split", "--rows", self.out / "rows.csv", "--masks", self.out / "masks.csv",
                                       "--g3", self.g3, "--validation", self.validation, "--out", self.out / "twin")
        self.assertEqual((code, err), (0, ""))

    def test_frozen_draw_that_differs_exits_one(self):
        done = self.chain()
        digest = re.search(r"sha256 ([0-9a-f]{16})", done["texts"]["splits"]).group(1)
        self.write_validation({"digest": "0" * 16, "persons": {"L6": 1}, "report": "ANOMALY-pack.md, job 1"})
        code, out, err = self.run_pack("split", "--rows", self.out / "rows.csv", "--masks", self.out / "masks.csv",
                                       "--g3", self.g3, "--validation", self.validation, "--out", self.out / "frozen")
        self.assertEqual((code, out, err), (1, "", "FAILED: the validation draw differs from the frozen one\n"))
        self.assertFalse((self.out / "frozen").exists())
        self.write_validation({"digest": digest, "persons": {"L6": 1, "normal": 1}, "report": "ANOMALY-pack.md, job 1"})
        code, out, err = self.run_pack("split", "--rows", self.out / "rows.csv", "--masks", self.out / "masks.csv",
                                       "--g3", self.g3, "--validation", self.validation, "--out", self.out / "frozen")
        self.assertEqual((code, err), (0, ""))
        self.assertTrue((self.out / "frozen" / "splits.csv").exists())
        self.assertFalse(pack.digest_differs(None, "abc"))
        self.assertFalse(pack.digest_differs({"digest": ""}, "abc"))
        self.assertTrue(pack.digest_differs({"digest": "0123456789abcdef"}, "0123456789abcdee" + "0" * 48))
        self.assertFalse(pack.digest_differs({"digest": "0123456789abcdef" + "0" * 48}, "0123456789abcdef" + "0" * 48))

    def test_trainval_lists_train_and_val_persons_only(self):
        done = self.chain()
        listed = [row["person"] for row in pack.read_csv(self.out / "trainval.csv")]
        wanted = sorted({entry["person"] for entry in done["splits"].values() if entry["split"] in ("train", "val")})
        self.assertEqual(listed, wanted)
        self.assertNotIn("ctsp:0001", listed)
        self.assertNotIn("verse:verse300", listed)
        self.assertNotIn("cobra:B100", listed)
        self.assertNotIn("verse:verse400", listed)
        self.assertIn("verse:verse200", listed)
        self.assertIn(f"- {len(wanted)} persons (train {len(wanted) - 2}, val 2)", done["texts"]["trainval"])


class ManifestTest(Tree):
    def manifest(self, dataset):
        return json.loads((self.out / f"manifest-{dataset}.yml").read_text(encoding="utf-8"))

    def test_manifest_keys_are_exactly_flexrays_without_protocol_name_and_stored_labels_are_contiguous(self):
        done = self.chain()
        manifest = self.manifest("schwingnet_spine")
        self.assertEqual(list(manifest), ["schema_version", "dataset_name", "dataset_type", "stored_labels", "preprocessing", "samples"])
        self.assertEqual((manifest["schema_version"], manifest["dataset_name"], manifest["dataset_type"]), (1, "schwingnet_spine", "ct-seg"))
        self.assertEqual(manifest["preprocessing"], {"hu_window": [-1000, 2000]})
        self.assertNotIn("protocol_name", manifest)
        self.assertNotIn("crops", manifest)
        self.assertEqual(list(manifest["stored_labels"]), [str(i) for i in range(28)])
        self.assertEqual(list(manifest["stored_labels"].values()), pack.CANONICAL)
        self.assertEqual(manifest["stored_labels"]["0"], "background")
        self.assertEqual(len(set(pack.CANONICAL)), 28)
        for sample in manifest["samples"]:
            self.assertEqual(list(sample), ["sample_id", "subject_id", "split", "image", "label", "metadata"])
            self.assertTrue(Path(sample["image"]).is_absolute() and Path(sample["image"]).is_file())
            self.assertTrue(Path(sample["label"]).is_absolute() and Path(sample["label"]).is_file())
            self.assertTrue(sample["label"].startswith(str(self.landing / "masks")))
            self.assertEqual(sample["subject_id"], sample["metadata"]["person"])
            self.assertEqual(sample["metadata"]["completeness"], "complete")
            self.assertEqual(sample["metadata"]["segmenter"], "spineps")
            self.assertEqual(set(sample["metadata"]), {"person", "collection", "case", "variant", "subtype", "tier", "role", "fold",
                                                       "countable", "completeness", "top_from", "sacrum_from", "gap", "mask_kind",
                                                       "why", "segmenter"})
            self.assertEqual(json.loads(json.dumps(sample["metadata"], allow_nan=False)), sample["metadata"])
        digest = hashlib.sha256((self.out / "manifest-schwingnet_spine.yml").read_bytes()).hexdigest()[:16]
        self.assertIn(f"- sha256 {digest}; whole volumes", done["texts"]["schwingnet_spine"])

    def test_manifest_text_is_json_that_yaml_would_read(self):
        self.chain()
        text = (self.out / "manifest-schwingnet_spine.yml").read_text(encoding="utf-8")
        self.assertTrue(text.endswith("\n"))
        self.assertNotIn("\t", text)
        self.assertTrue(text.isascii())
        parsed = json.loads(text)
        self.assertEqual(parsed["dataset_type"], "ct-seg")
        # every key is quoted and followed by ': ', the form YAML reads as a flow mapping
        self.assertRegex(text, r'^\{\n "schema_version": 1,\n')
        self.assertFalse(re.search(r'":[^ ]', text))
        try:
            import yaml
        except ImportError:
            return
        self.assertEqual(yaml.safe_load(text), parsed)

    def test_two_datasets_by_completeness_and_an_empty_one_writes_nothing(self):
        done = self.chain()
        complete = {s["metadata"]["case"] for s in self.manifest("schwingnet_spine")["samples"]}
        partial = {s["metadata"]["case"] for s in self.manifest("schwingnet_spine_partial")["samples"]}
        self.assertEqual(partial, {"TS_s0001", "TS_s0003", "amos_0001"})
        self.assertEqual(complete & partial, set())
        self.assertEqual(len(complete) + len(partial), len(done["splits"]))
        self.assertEqual({s["split"] for s in self.manifest("schwingnet_spine")["samples"]}, {"train", "val", "test", "holdout", "uncounted", "g3_excluded"})
        partial_splits = {s["split"] for s in self.manifest("schwingnet_spine_partial")["samples"]}
        self.assertIn("g3_excluded", partial_splits)
        self.assertLessEqual(partial_splits, {"train", "val", "g3_excluded"})
        self.assertIn("- samples 3: ", done["texts"]["schwingnet_spine_partial"])
        # every packed row is complete: the partial dataset writes no manifest and says so
        masks = done["masks"]
        for rec in masks.values():
            if rec["status"] in pack.PACKED:
                rec["complete"] = "True"
        pack.write_csv(self.out / "masks.csv", pack.MASK_COLUMNS, masks.values())
        (self.out / "manifest-schwingnet_spine_partial.yml").unlink()
        code, text, err = self.run_pack("manifest", "--splits", self.out / "splits.csv", "--masks", self.out / "masks.csv",
                                        "--rows", self.out / "rows.csv", "--dataset", "schwingnet_spine_partial", "--out", self.out)
        self.assertEqual((code, err), (0, ""))
        self.assertIn("- no sample; no manifest written", text)
        self.assertFalse((self.out / "manifest-schwingnet_spine_partial.yml").exists())
        code, text, err = self.run_pack("manifest", "--splits", self.out / "splits.csv", "--masks", self.out / "masks.csv",
                                        "--rows", self.out / "rows.csv", "--dataset", "other", "--out", self.out)
        self.assertEqual((code, err), (1, "FAILED: the dataset is schwingnet_spine or schwingnet_spine_partial\n"))

    def test_crops_switch_refuses_a_non_512_row(self):
        self.chain()
        argv = ["manifest", "--splits", self.out / "splits.csv", "--masks", self.out / "masks.csv", "--rows", self.out / "rows.csv",
                "--dataset", "schwingnet_spine", "--out", self.out / "crops"]
        code, out, err = self.run_pack(*argv, "--crops", "512,512,256")
        self.assertEqual((code, out, err), (1, "", "FAILED: 11 rows are not 512 by 512 in plane\n"))
        self.assertFalse((self.out / "crops" / "manifest-schwingnet_spine.yml").exists())
        code, out, err = self.run_pack(*argv, "--crops", "16,16,4")
        self.assertEqual((code, err), (0, ""))
        manifest = json.loads((self.out / "crops" / "manifest-schwingnet_spine.yml").read_text())
        self.assertEqual(manifest["crops"], {"size": [16, 16, 4]})
        self.assertEqual(list(manifest)[-2:], ["crops", "samples"])
        self.assertIn("crops 16x16x4", out)
        code, out, err = self.run_pack(*argv, "--crops", "16,16")
        self.assertEqual((code, err), (1, "FAILED: --crops takes three positive integers X,Y,Z\n"))
        code, out, err = self.run_pack(*argv, "--hu=2000,-1000")
        self.assertEqual((code, err), (1, "FAILED: --hu takes an increasing low,high pair\n"))


class SizeTest(Tree):
    def size_line(self):
        code, text, err = self.run_pack("size", "--rows", self.out / "rows.csv", "--landing", self.landing)
        self.assertEqual((code, err), (0, ""))
        total, need, how = text.splitlines()[-1].split(" ", 2)
        return int(total), int(need), how, text

    def test_size_reads_rows_not_the_manifest_counts_masks_and_never_subtracts_a_package(self):
        rows, _ = self.rows()
        ok = [row for row in rows.values() if row["status"] == "ok"]
        expected = sum(int(row["voxels"]) * 4 + 64 for row in ok)
        self.assertEqual(expected, 18 * (2048 * 4 + 64))
        total, need, how, text = self.size_line()
        self.assertEqual((total, need), (expected, expected))
        self.assertEqual(how, "header census of 18 CTs: float16 image, uint8 label and uint8 mask, uncompressed")
        self.assertIn("- payload_too_large: 0 rows", text)
        self.assertFalse(list(self.out.glob("manifest-*")))
        # after the rewrite, the verified masks lower the need by their uint8 bytes, one voxel each
        self.chain()
        written = sum(1 for rec in pack.read_csv(self.out / "masks.csv") if rec["status"] in pack.PACKED)
        total, need, how, _ = self.size_line()
        self.assertEqual((total, need), (expected, expected - written * 2048))
        # a package on the landing changes nothing; a sidecar whose source moved on is not verified
        package = self.landing / "schwingnet_spine" / "thunder_dbs" / "v1"
        package.mkdir(parents=True)
        (package / "data.mdb").write_bytes(bytes(100000))
        self.assertEqual(self.size_line()[:2], (expected, expected - written * 2048))
        time.sleep(0.02)
        os.utime(self.by_case(rows)["B100"]["mask"], None)
        self.assertEqual(self.size_line()[:2], (expected, expected - (written - 1) * 2048))
        (self.landing / "masks" / "cobra2026__B400.nii.gz").write_bytes(b"short")
        self.assertEqual(self.size_line()[:2], (expected, expected - (written - 2) * 2048))
        # an oversize row is refused before the census and counted apart
        rows["verse__verse100"]["status"] = "payload_too_large"
        pack.write_csv(self.out / "rows.csv", pack.ROW_COLUMNS, rows.values())
        total, need, how, text = self.size_line()
        self.assertEqual(total, expected - (2048 * 4 + 64))
        self.assertIn("- payload_too_large: 1 rows", text)
        self.assertIn("census of 17 CTs", how)

    def test_the_census_refuses_a_payload_past_the_limit(self):
        rows = [{"status": "ok", "ct": str(ct_file(self.tmp / "big.nii.gz"))}]
        pack.census(rows)
        self.assertEqual((rows[0]["status"], rows[0]["voxels"], rows[0]["dims"]), ("ok", "2048", "16x16x8"))
        huge = write_nifti(self.tmp / "huge.nii.gz", (1024, 1024, 1100), 4, b"")
        rows = [{"status": "ok", "ct": str(huge)}]
        pack.census(rows)
        self.assertEqual((rows[0]["status"], rows[0]["voxels"]), ("payload_too_large", str(1024 * 1024 * 1100)))


class ReportTest(Tree):
    def test_sections_and_errors_carry_counts_only(self):
        done = self.chain()
        texts = dict(done["texts"])
        self.write_validation({"digest": "f" * 16})
        texts["frozen"] = "".join(self.run_pack("split", "--rows", self.out / "rows.csv", "--masks", self.out / "masks.csv",
                                                "--g3", self.g3, "--validation", self.validation, "--out", self.out / "x")[1:])
        texts["moose"] = "".join(self.run_pack("rows", "--selection", self.selection, "--holdout", self.holdout, "--data", self.data,
                                               "--home", self.home, "--registry", self.registry, "--harvest", self.harvest,
                                               "--out", self.out / "x", "--segmenter", "moose")[1:])
        texts["missing"] = "".join(self.run_pack("split", "--rows", self.tmp / "absent.csv", "--masks", self.out / "masks.csv",
                                                 "--g3", self.g3, "--validation", self.validation, "--out", self.out / "x")[1:])
        texts["broken"] = "".join(self.run_pack("split", "--rows", self.out / "rows.csv", "--masks", self.out / "masks.csv",
                                                "--g3", touch(self.tmp / "broken.json", "{not json"), "--validation", self.validation,
                                                "--out", self.out / "x")[1:])
        self.assertEqual(texts["missing"], "FAILED: a file could not be read or written (No such file or directory)\n")
        self.assertEqual(texts["broken"], "FAILED: an input file could not be parsed\n")
        for name, text in texts.items():
            self.assertTrue(text, name)
            self.assertNotIn(str(self.tmp), text, name)
            self.assertNotIn("/", text, name)
            for case in CASE_IDS:
                self.assertNotIn(case, text, f"{name} names {case}")
            self.assertIsNone(KEY_PREFIXES.search(text), f"{name} names a person key: {KEY_PREFIXES.search(text)}")
        for name in ("rows", "guard-list", "masks", "splits", "trainval", "manifest-schwingnet_spine", "manifest-schwingnet_spine_partial"):
            self.assertTrue((self.out / f"{name}.md").is_file(), name)
        # the stderr sentence is the whole of a failure's output
        for name in ("frozen", "moose"):
            self.assertRegex(texts[name], r"^FAILED: [^\n]+\n$")

    def test_every_subcommand_help_parses(self):
        for sub in ("rows", "guard-list", "testgate", "size", "rewrite", "split", "trainval", "manifest"):
            with redirect_stdout(io.StringIO()) as out:
                with self.assertRaises(SystemExit) as left:
                    pack.main([sub, "--help"])
            self.assertEqual(left.exception.code, 0, sub)
            self.assertIn(f" {sub} [-h]", out.getvalue())
        with redirect_stdout(io.StringIO()) as out:
            with self.assertRaises(SystemExit):
                pack.main(["--help"])
        for sub in ("rows", "guard-list", "testgate", "size", "rewrite", "split", "trainval", "manifest"):
            self.assertIn(sub, out.getvalue())


if __name__ == "__main__":
    unittest.main()
