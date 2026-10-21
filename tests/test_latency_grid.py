"""grid/run-latency-sweep.sh and grid/latency-sweep.sbatch (issue #13): the scripts parse, a probe is
one small CPU job, each run directory gets a GPU job, a CPU job after it and a sweep array after it,
in parallel across runs, and a run without its checkpoint or without a catalog is refused before
anything is submitted. A fake sbatch records what would be submitted; nothing reaches a scheduler.
Standard library only, so the required check runs it."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRID = ROOT / "grid"

FAKE_SBATCH = """#!/bin/bash
n=$(( $(wc -l < "$LOG" 2>/dev/null || echo 0) + 1001 ))
echo "$*" >> "$LOG"
echo "$n"
"""


class LatencyGridTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.sbatch = self.tmp / "sbatch"
        self.sbatch.write_text(FAKE_SBATCH, encoding="utf-8")
        self.sbatch.chmod(0o755)
        self.log = self.tmp / "submitted.txt"
        # a copy of the two scripts, so a test's LAST_LATENCY.txt never lands in the checkout
        self.repo = self.tmp / "repo"
        (self.repo / "grid").mkdir(parents=True)
        for name in ("run-latency-sweep.sh", "latency-sweep.sbatch"):
            (self.repo / "grid" / name).write_bytes((GRID / name).read_bytes())

    def make_run(self, name):
        run = self.tmp / name
        (run / "train").mkdir(parents=True)
        (run / "RUN.json").write_text("{}", encoding="utf-8")
        (run / "train" / "best.pt").write_bytes(b"weights")
        return run

    def submit(self, *args):
        env = dict(os.environ, SBATCH=str(self.sbatch), LOG=str(self.log), SCHWINGNET=str(self.repo))
        done = subprocess.run(["bash", str(self.repo / "grid" / "run-latency-sweep.sh"), *args], env=env, capture_output=True, text=True, timeout=60)
        lines = self.log.read_text(encoding="utf-8").splitlines() if self.log.exists() else []
        return done, lines

    def test_the_scripts_parse(self):
        for name in ("run-latency-sweep.sh", "latency-sweep.sbatch"):
            done = subprocess.run(["bash", "-n", str(GRID / name)], capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)

    def test_the_probe_is_one_small_cpu_job(self):
        done, lines = self.submit("--probe")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(len(lines), 1)
        self.assertIn("PART=probe", lines[0])
        self.assertIn("--gres=none", lines[0])
        self.assertIn("--partition=reqp", lines[0])

    def test_each_run_gets_a_gpu_job_then_a_cpu_job_and_a_sweep_array(self):
        first, second = self.make_run("a"), self.make_run("b")
        done, lines = self.submit("--catalog", "/c.sqlite", str(first), str(second), "--sweep", "case134:/f134:/b134.jsonl", "--sweep", "case39:/f39:/b39.jsonl")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(len(lines), 6)
        gpu_a, cpu_a, sweep_a, gpu_b = lines[0], lines[1], lines[2], lines[3]
        self.assertIn("PART=gpu", gpu_a)
        self.assertIn(f"RUN={first}", gpu_a)
        self.assertNotIn("--dependency", gpu_a)
        self.assertIn("--dependency=afterok:1001", cpu_a)
        self.assertIn("PART=cpu", cpu_a)
        self.assertIn("--array=0-1", sweep_a)
        self.assertIn("--dependency=afterok:1001", sweep_a)
        self.assertIn("SWEEPS=case134:/f134:/b134.jsonl case39:/f39:/b39.jsonl", sweep_a)
        self.assertIn(f"RUN={second}", gpu_b)
        self.assertNotIn("--dependency", gpu_b)
        self.assertIn("--dependency=afterok:1004", lines[4])

    def test_no_sweep_is_submitted_without_frames_and_boxes(self):
        done, lines = self.submit("--catalog", "/c.sqlite", str(self.make_run("a")))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual([("PART=gpu" in l, "PART=cpu" in l) for l in lines], [(True, False), (False, True)])

    def test_a_run_without_its_checkpoint_is_refused(self):
        bare = self.tmp / "bare"
        bare.mkdir()
        done, lines = self.submit("--catalog", "/c.sqlite", str(bare))
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(lines, [])

    def test_runs_without_a_catalog_are_refused(self):
        done, lines = self.submit(str(self.make_run("a")))
        self.assertEqual(done.returncode, 64)
        self.assertEqual(lines, [])


if __name__ == "__main__":
    unittest.main()
