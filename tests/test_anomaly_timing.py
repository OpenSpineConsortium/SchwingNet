"""tools/anomaly_timing.py: the GPU self-test, the inventory of paired CTs and their SPINEPS masks, the pick and the estimate (#398, stage 2)."""
import csv
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("anomaly_timing", ROOT / "tools" / "anomaly_timing.py")
timing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(timing)


def touch(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class GpuTest(unittest.TestCase):
    def test_a_blackwell_card_or_no_card_leaves_the_node_and_an_older_card_goes_on(self):
        self.assertEqual(timing.gpu_verdict("NVIDIA A100-SXM4-80GB, 8.0"), (0, "GPU: NVIDIA A100-SXM4-80GB, sm_80"))
        self.assertEqual(timing.gpu_verdict("NVIDIA H100 80GB HBM3, 9.0")[0], 0)
        for smi in ("NVIDIA RTX PRO 6000 Blackwell Server Edition, 12.0", "NVIDIA B200, 10.0"):
            code, line = timing.gpu_verdict(smi)
            self.assertEqual(code, timing.NODE_UNUSABLE, smi)
            self.assertIn("Blackwell", line)
        code, line = timing.gpu_verdict("")
        self.assertEqual(code, timing.NODE_UNUSABLE)
        self.assertIn("none seen", line)
        # a driver whose nvidia-smi cannot say the compute capability gives the name alone, and the stage goes on
        code, line = timing.gpu_verdict("Tesla V100-PCIE-32GB")
        self.assertEqual(code, 0)
        self.assertIn("unread", line)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(timing.main(["gpu", "--smi", "NVIDIA B200, 10.0"]), 4)
            self.assertEqual(timing.main(["gpu", "--smi", "NVIDIA H100, 9.0"]), 0)


class InventoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.data = self.tmp / "data"
        self.work = self.tmp / "realxray_work"
        cobra = self.data / "cobra2026"
        for case in ("cobra_named", "cobra_raw", "cobra_bare", "cobra_mha"):
            touch(cobra / "cases" / case / "ct_def.mha")
        touch(cobra / "lstv" / "nifti" / "cobra_named_ct.nii.gz")
        touch(cobra / "lstv" / "nifti" / "cobra_raw_ct.nii.gz")
        touch(cobra / "varian" / "nifti" / "cobra_bare_ct.nii.gz")
        touch(cobra / "lstv" / "seg" / f"cobra_named{timing.MASK}")
        # the Elekta harvest's masks carry raw instance ids, so they count as lacking (section 2 of the route note)
        touch(cobra / "seg" / "spineps" / f"cobra_raw{timing.MASK}")
        carm = self.data / "carmlspine"
        for case in ("carm_one", "carm_two"):
            touch(carm / "nifti" / f"{case}_ct.nii.gz")
        rows = [{"case": "carm_one", "ct": str(carm / "nifti" / "carm_one_ct.nii.gz")},
                {"case": "carm_two", "ct": str(carm / "nifti" / "carm_two_ct.nii.gz")},
                {"case": "carm_gone", "ct": str(carm / "nifti" / "carm_gone_ct.nii.gz")}]
        timing.write_csv(touch(carm / "cases.csv"), ["case", "ct"], rows)
        touch(carm / "spineps" / f"carm_one{timing.MASK}")
        touch(self.data / "anomaly_harvest" / "carmlspine_spot" / "spineps" / f"carm_two{timing.MASK}")
        touch(self.data / "deepfluoro_h5" / "raw" / "deepfluoro" / "17-1882.h5")
        touch(self.data / "zenodo_lumos" / "raw" / "lumos_001.zip")

    def by_case(self, rows):
        return {entry["case"]: entry for entry in rows}

    def test_the_inventory_counts_named_raw_lacking_and_unconverted_cts_per_set(self):
        rows = timing.inventory(self.data, self.work)
        status = {case: entry["status"] for case, entry in self.by_case(rows).items()}
        self.assertEqual(status, {"cobra_named": "named", "cobra_raw": "raw", "cobra_bare": "lacking", "cobra_mha": "no_nifti",
                                  "carm_one": "named", "carm_two": "named", "carm_gone": "no_nifti", "17-1882": "no_nifti",
                                  "lumos_001": "no_nifti"})
        stores = {case: entry["mask_store"] for case, entry in self.by_case(rows).items() if entry["mask_store"]}
        self.assertEqual(stores, {"cobra_named": "cobra2026/lstv/seg", "cobra_raw": "cobra2026/seg/spineps (raw ids)",
                                  "carm_one": "carmlspine/spineps", "carm_two": "anomaly_harvest/carmlspine_spot/spineps"})
        lines = timing.inventory_lines(rows)
        self.assertIn("| cobra | 4 | 1 | 1 | 1 | 1 |", lines)
        self.assertIn("| carmlspine | 3 | 2 | 0 | 0 | 1 |", lines)
        self.assertIn("| deepfluoro | 1 | 0 | 0 | 0 | 1 |", lines)
        self.assertIn("| lumos | 1 | 0 | 0 | 0 | 1 |", lines)
        self.assertEqual(timing.inventory(self.tmp / "nowhere", self.work), [])
        self.assertIn("| (no paired set found under the data root) | 0 | 0 | 0 | 0 | 0 |", timing.inventory_lines([]))

    def test_deepfluoro_reads_the_realxray_export_where_its_ct_stage_ran(self):
        exported = self.work / "deepfluoro"
        touch(exported / "nifti" / "17-1882_ct.nii.gz")
        timing.write_csv(touch(exported / "cases.csv"), ["case", "ct"], [{"case": "17-1882", "ct": str(exported / "nifti" / "17-1882_ct.nii.gz")}])
        rows = [entry for entry in timing.inventory(self.data, self.work) if entry["set"] == "deepfluoro"]
        self.assertEqual([(entry["case"], entry["status"]) for entry in rows], [("17-1882", "lacking")])

    def test_the_pick_draws_by_rank_among_cts_with_a_nifti_and_no_named_mask_and_never_lumos(self):
        rows = timing.inventory(self.data, self.work)
        touch(self.data / "zenodo_lumos" / "nifti" / "lumos_ct_001.nii.gz")
        rows = timing.inventory(self.data, self.work)
        self.assertIn(("lumos_ct_001", "lacking"), [(entry["case"], entry["status"]) for entry in rows])
        chosen = timing.pick(rows, 10)
        self.assertEqual({name: sorted(entry["case"] for entry in entries) for name, entries in chosen.items()},
                         {"cobra": ["cobra_bare", "cobra_raw"]})
        self.assertEqual(timing.pick(rows, 10), chosen)
        one = timing.pick(rows, 1)
        self.assertEqual(sum(map(len, one.values())), 1)
        first = min(("cobra_bare", "cobra_raw"), key=lambda case: timing.rank(f"cobra:{case}"))
        self.assertEqual(one["cobra"][0]["case"], first)
        lines = timing.pick_lines(chosen, rows, 10)
        self.assertIn("Asked for 10; picked 2 by rank among the 2 CTs with a NIfTI and no named mask, of 2 lacking one in all.", lines)
        self.assertIn("Fewer than 10: only 2 paired CTs lack a named mask.", lines)
        self.assertEqual(timing.shares(10, {"a": 30, "b": 10}), {"a": 8, "b": 2})
        self.assertEqual(timing.shares(3, {"a": 1, "b": 100}), {"a": 0, "b": 3})
        self.assertEqual(timing.shares(5, {"a": 2, "b": 100}), {"a": 0, "b": 5})
        self.assertEqual(timing.shares(7, {"a": 2, "b": 3}), {"a": 2, "b": 3})
        self.assertEqual(timing.shares(0, {"a": 1}), {"a": 0})

    def test_the_pick_says_how_many_lacking_cts_have_no_nifti_yet(self):
        touch(self.data / "cobra2026" / "seg" / "spineps" / f"cobra_mha{timing.MASK}")
        rows = timing.inventory(self.data, self.work)
        chosen = timing.pick(rows, 10)
        lines = timing.pick_lines(chosen, rows, 10)
        self.assertIn("| cobra | 3 | 2 | 2 |", lines)
        self.assertIn("Fewer than 10: 1 of the lacking CTs have no NIfTI yet, which the production array's request must bring.", lines)

    def test_the_estimate_reads_the_runners_timing_records_and_counts_what_still_lacks_a_mask(self):
        rows = timing.inventory(self.data, self.work)
        out = self.tmp / "out"
        timing.write_csv(touch(out / "inventory.csv"), ["set", "case", "ct", "ct_kind", "mask", "mask_store", "status"], rows)
        spineps = out / "spineps" / "cobra"
        records = [{"case": "cobra_raw", "seconds": 60.0, "ok": True}, {"case": "cobra_bare", "seconds": 120.0, "ok": False, "error": "x"}]
        touch(spineps / "timing_shard0.jsonl", "".join(json.dumps(record) + "\n" for record in records))
        touch(spineps / f"cobra_raw{timing.MASK}")
        done, failed = timing.timings(out / "spineps")
        self.assertEqual((done, failed), ([60.0], 1))
        text = io.StringIO()
        with redirect_stdout(text):
            code = timing.main(["estimate", "--timing-dir", str(out / "spineps"), "--inventory", str(out / "inventory.csv"), "--gpu", "GPU: A100, sm_80"])
        self.assertEqual(code, 0)
        lines = text.getvalue().splitlines()
        self.assertIn("GPU: A100, sm_80", lines)
        self.assertIn("Timed 1 CTs; 1 failed.", lines)
        self.assertIn("Seconds per CT: median 60, least 60, most 60.", lines)
        self.assertIn("CTs still lacking a named mask after this run: 1 (cobra 1).", lines)
        self.assertIn("At the median, one GPU would take 0.0 hours for them; one job keeps each under 8 hours.", lines)
        self.assertIn("The production array is not approved: this estimate is for the owner's count, asked once as a decision.", lines)
        # three hundred lacking CTs at twenty minutes each are an array
        lines = timing.estimate([1200.0, 1200.0], 0, {"cobra": 300})
        self.assertIn("At the median, one GPU would take 100.0 hours for them; an array of 13 tasks keeps each under 8 hours.", lines)
        self.assertIn("No paired CT lacks a named mask after this run, so no production array is needed.", timing.estimate([30.0], 0, {}))
        # no CT finished: the stage fails, so the gate queues it again once a fix lands
        touch(spineps / "timing_shard0.jsonl", json.dumps(records[1]) + "\n")
        (spineps / f"cobra_raw{timing.MASK}").unlink()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(timing.main(["estimate", "--timing-dir", str(out / "spineps"), "--inventory", str(out / "inventory.csv")]), 1)

    def test_the_commands_write_their_files_under_out(self):
        out = self.tmp / "out"
        with redirect_stdout(io.StringIO()):
            self.assertEqual(timing.main(["inventory", "--data", str(self.data), "--work", str(self.work), "--out", str(out)]), 0)
            self.assertEqual(timing.main(["pick", "--inventory", str(out / "inventory.csv"), "--count", "10", "--out", str(out)]), 0)
        with open(out / "cases-cobra.csv", newline="", encoding="utf-8") as handle:
            cases = list(csv.DictReader(handle))
        self.assertEqual(sorted(entry["case"] for entry in cases), ["cobra_bare", "cobra_raw"])
        self.assertTrue(all(Path(entry["ct"]).is_file() for entry in cases))
        self.assertFalse((out / "cases-carmlspine.csv").exists())
        self.assertEqual(json.loads((out / "picked.json").read_text(encoding="utf-8")), {"cobra": 2})


if __name__ == "__main__":
    unittest.main()
