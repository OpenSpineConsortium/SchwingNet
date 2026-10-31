"""tools/prune.py, run as the job runs it (the gate word prune): the plan records each raw folder and
deletes nothing; the deletion removes a folder only when it still matches its plan, and refuses a
link, a folder that changed and a set the plan does not list.

    python3 -m unittest tests/test_prune.py
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class PruneTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.data, self.list = base / "data", base / "round.txt"
        self.plan, self.plan_md, self.done = base / "plan.json", base / "plan.md", base / "done.md"
        for one, size in (("a_set", 10), ("b_set", 20)):
            raw = self.data / one / "raw" / "sub"
            raw.mkdir(parents=True)
            (raw / "x.nii.gz").write_bytes(b"x" * size)
        (self.data / "a_set" / "README.yaml").write_text("kept\n", encoding="ascii")

    def tearDown(self):
        self.tmp.cleanup()

    def run_tool(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "tools" / "prune.py"), *args], capture_output=True, text=True)

    def plan_step(self, ids):
        self.list.write_text("# a comment\n" + "\n".join(ids) + "\n", encoding="ascii")
        return self.run_tool("plan", "--list", str(self.list), "--data", str(self.data), "--out", str(self.plan),
                             "--report", str(self.plan_md))

    def delete_step(self):
        return self.run_tool("delete", "--list", str(self.list), "--data", str(self.data), "--plan", str(self.plan),
                             "--report", str(self.done))

    def test_the_plan_deletes_nothing_and_the_deletion_removes_only_the_raw_folders(self):
        done = self.plan_step(["a_set", "b_set", "missing_set"])
        self.assertEqual(done.returncode, 0, done.stderr)
        planned = json.loads(self.plan.read_text(encoding="ascii"))
        self.assertEqual(planned["a_set"], {"files": 1, "bytes": 10})
        self.assertEqual(planned["missing_set"], {"problem": "no raw folder"})
        self.assertIn("- missing_set: refused, no raw folder", self.plan_md.read_text(encoding="ascii"))
        self.assertTrue((self.data / "a_set" / "raw").is_dir())
        done = self.delete_step()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertFalse((self.data / "a_set" / "raw").exists())
        self.assertFalse((self.data / "b_set" / "raw").exists())
        self.assertTrue((self.data / "a_set" / "README.yaml").is_file())
        report = self.done.read_text(encoding="ascii")
        self.assertIn("- missing_set: kept, the plan lists no folder for it", report)
        self.assertIn("Freed: 0.0 GB.", report)

    def test_a_folder_that_changed_since_the_plan_is_kept(self):
        self.plan_step(["a_set", "b_set"])
        (self.data / "a_set" / "raw" / "late.json").write_text("{}", encoding="ascii")
        self.delete_step()
        self.assertTrue((self.data / "a_set" / "raw").is_dir())
        self.assertFalse((self.data / "b_set" / "raw").exists())
        self.assertIn("- a_set: kept, it changed since the plan", self.done.read_text(encoding="ascii"))

    def test_a_link_is_never_followed_or_deleted_through(self):
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        (outside / "keep.bin").write_bytes(b"k")
        (self.data / "c_set").mkdir()
        os.symlink(outside, self.data / "c_set" / "raw")
        self.plan_step(["c_set"])
        self.assertIn("link", json.loads(self.plan.read_text(encoding="ascii"))["c_set"]["problem"])
        self.delete_step()
        self.assertTrue((outside / "keep.bin").is_file())
        # a link inside a raw folder is counted as a file and removed with the folder, its target kept
        os.symlink(outside, self.data / "a_set" / "raw" / "link")
        self.plan_step(["a_set"])
        self.assertEqual(json.loads(self.plan.read_text(encoding="ascii"))["a_set"]["files"], 2)
        self.delete_step()
        self.assertFalse((self.data / "a_set" / "raw").exists())
        self.assertTrue((outside / "keep.bin").is_file())

    def test_a_list_that_is_not_ids_is_refused(self):
        self.list.write_text("../etc\n", encoding="ascii")
        done = self.run_tool("plan", "--list", str(self.list), "--data", str(self.data), "--out", str(self.plan),
                             "--report", str(self.plan_md))
        self.assertEqual(done.returncode, 2)
        self.assertFalse(self.plan.exists())

    def test_a_path_below_the_account_is_planned_and_deleted(self):
        derived = self.data / "a_set" / "derived"
        derived.mkdir()
        (derived / "bank.npz").write_bytes(b"y" * 7)
        results = Path(self.tmp.name) / "results" / "old_run"
        results.mkdir(parents=True)
        (results / "out.json").write_text("{}", encoding="ascii")
        done = self.plan_step(["data/a_set/derived", "results/old_run", "data/no_set/derived"])
        self.assertEqual(done.returncode, 0, done.stderr)
        planned = json.loads(self.plan.read_text(encoding="ascii"))
        self.assertEqual(planned["data/a_set/derived"], {"files": 1, "bytes": 7})
        self.assertEqual(planned["data/no_set/derived"], {"problem": "no folder"})
        self.delete_step()
        self.assertFalse(derived.exists())
        self.assertFalse(results.exists())
        self.assertTrue((self.data / "a_set" / "raw").is_dir())
        self.assertTrue((Path(self.tmp.name) / "results").is_dir())

    def test_a_path_through_a_link_is_refused(self):
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        (outside / "keep.bin").write_bytes(b"k")
        os.symlink(outside, self.data / "linked")
        self.plan_step(["data/linked"])
        self.assertIn("link", json.loads(self.plan.read_text(encoding="ascii"))["data/linked"]["problem"])
        self.delete_step()
        self.assertTrue((outside / "keep.bin").is_file())

    def test_a_path_outside_data_or_results_is_refused(self):
        for bad in ("u251_host/results", "data/", "results/", "data/x/../y", "/data/x"):
            self.list.write_text(bad + "\n", encoding="ascii")
            done = self.run_tool("plan", "--list", str(self.list), "--data", str(self.data), "--out", str(self.plan),
                                 "--report", str(self.plan_md))
            self.assertEqual(done.returncode, 2, bad)

    def test_the_committed_list_names_ids(self):
        sys.path.insert(0, str(ROOT / "tools"))
        try:
            import prune
        finally:
            sys.path.pop(0)
        self.assertEqual(prune.read_list(ROOT / "grid" / "prune" / "round2.txt"),
                         ["idc_nlst", "hf_abdomenatlas2_0_mini", "zenodo_unitochest", "hf_rexgradient_160k"])
        round4 = prune.read_list(ROOT / "grid" / "prune" / "round4.txt")
        self.assertFalse([line for line in round4 if "u251" in line or "versefusion" in line])


if __name__ == "__main__":
    unittest.main()
