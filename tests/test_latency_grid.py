"""grid/run-latency-sweep.sh and grid/latency-sweep.sbatch (issue #13): the scripts parse, a probe is
one small CPU job, each run directory gets a GPU job, a CPU job after it and a sweep array after it,
in parallel across runs, and a run without its checkpoint or without a catalog is refused before
anything is submitted. Every job goes through hpcworker's job submit with a class (issue #77); the
fake hpcworker under tests/fakes/ records what would be queued, and nothing reaches a scheduler.
Standard library only, so the required check runs it."""

import os
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRID = ROOT / "grid"

FAKE_HPCWORKER = ROOT / "tests" / "fakes" / "hpcworker"
# A stand-in for `pixi run` in the job: it records its words and answers as flows/launch.py would,
# or, where FAKE_PIXI_HOLD is set, holds until a TERM and then ends as the launcher ends on one.
FAKE_PIXI = """#!/bin/bash
echo "$*" >> "$FAKE_PIXI_LOG"
if [ -n "${FAKE_PIXI_HOLD:-}" ]; then
  trap 'echo TERM > "$FAKE_PIXI_STOPPED"; echo "{\\"flow\\": \\"latency\\", \\"run\\": \\"LatencyFlow/4\\", \\"successful\\": false, \\"verdict\\": null}"; exit 143' TERM
  echo '{"decision": "run", "flow": "latency", "key": "k", "origin": null}'
  : > "$FAKE_PIXI_HOLD"
  while :; do sleep 0.1; done
fi
echo '{"decision": "run", "flow": "latency", "key": "k", "origin": null}'
echo 'LatencyFlow: end: r1: current as an earlier run wrote it; CLAIM 2024: 20 met'
echo 'LatencyFlow: end: part gpu, verdict 1'
echo '{"flow": "latency", "run": "LatencyFlow/3", "successful": true, "verdict": 1}'
echo 'LATENCY_RC=1 2026-10-29 16:00:00'
exit "${FAKE_PIXI_RC:-0}"
"""


class LatencyGridTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.log = self.tmp / "submitted.txt"
        self.catalog = self.tmp / "catalog.sqlite"
        self.catalog.write_bytes(b"")
        # a copy of the two scripts, so a test's LAST_LATENCY.txt never lands in the checkout
        self.repo = self.tmp / "repo"
        (self.repo / "grid").mkdir(parents=True)
        for name in ("run-latency-sweep.sh", "latency-sweep.sbatch", "hpcw.sh"):
            (self.repo / "grid" / name).write_bytes((GRID / name).read_bytes())

    def make_run(self, name):
        run = self.tmp / name
        (run / "train").mkdir(parents=True)
        (run / "RUN.json").write_text("{}", encoding="utf-8")
        (run / "train" / "best.pt").write_bytes(b"weights")
        (run / "train" / "checkpoint.json").write_text("{}", encoding="utf-8")
        return run

    def env(self):
        return dict(os.environ, HPCWORKER=str(FAKE_HPCWORKER), HPCW_LOG=str(self.log), HPCW_FIRST="1001", SCHWINGNET=str(self.repo))

    def submit(self, *args):
        env = self.env()
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
        self.assertIn("--class batch --name latency_probe ", lines[0])
        self.assertIn("--cpus 1 --mem 2G --time 00:10:00 latency-sweep.sbatch", lines[0])

    def test_each_run_gets_a_gpu_job_then_a_cpu_job_and_a_sweep_array(self):
        first, second = self.make_run("a"), self.make_run("b")
        done, lines = self.submit("--catalog", str(self.catalog), str(first), str(second), "--sweep", "case134:/f134:/b134.jsonl", "--sweep", "case39:/f39:/b39.jsonl")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(len(lines), 6)
        gpu_a, cpu_a, sweep_a, gpu_b = lines[0], lines[1], lines[2], lines[3]
        self.assertIn("PART=gpu", gpu_a)
        # the gpu class, whose QoS the site profile gives (issues #74, #77), narrowed to gmsap, the
        # H200 nodes the retraining plan measures latency on
        self.assertIn("--class gpu --name latency_gpu --partition gmsap latency-sweep.sbatch", gpu_a)
        self.assertIn(f"CATALOG={self.catalog}", gpu_a)
        self.assertIn(f"RUN={first}", gpu_a)
        self.assertNotIn("--dependency", gpu_a)
        self.assertIn("--dependency=afterany:1001", cpu_a)
        self.assertIn("PART=cpu", cpu_a)
        self.assertIn("--class batch --name latency_cpu ", cpu_a)
        self.assertIn("--array 0-1", sweep_a)
        self.assertIn("--dependency=afterany:1001", sweep_a)
        self.assertIn("--class gpu --name latency_sweep ", sweep_a)
        self.assertIn("--partition gmsap ", sweep_a)
        for line in lines:
            self.assertNotIn("--qos", line)
            self.assertNotIn("--gres", line)
        self.assertIn("SWEEPS=case134:/f134:/b134.jsonl case39:/f39:/b39.jsonl", sweep_a)
        self.assertIn(f"RUN={second}", gpu_b)
        self.assertNotIn("--dependency", gpu_b)
        self.assertIn("--dependency=afterany:1004", lines[4])

    def test_no_sweep_is_submitted_without_frames_and_boxes(self):
        done, lines = self.submit("--catalog", str(self.catalog), str(self.make_run("a")))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual([("PART=gpu" in l, "PART=cpu" in l) for l in lines], [(True, False), (False, True)])

    def test_a_run_without_its_checkpoint_is_refused(self):
        bare = self.tmp / "bare"
        bare.mkdir()
        done, lines = self.submit("--catalog", str(self.catalog), str(bare))
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(lines, [])

    def test_a_run_still_training_is_refused(self):
        # train.py keeps best.pt from the first epoch on and writes checkpoint.json only at the end
        run = self.make_run("training")
        (run / "train" / "checkpoint.json").unlink()
        done, lines = self.submit("--catalog", str(self.catalog), str(run))
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertIn("has not finished training", done.stderr)
        self.assertEqual(lines, [])

    def test_a_relative_run_is_passed_to_the_jobs_as_an_absolute_path(self):
        self.make_run("rel")
        done = subprocess.run(["bash", str(self.repo / "grid" / "run-latency-sweep.sh"), "--catalog", "catalog.sqlite", "rel"],
                              env=self.env(), capture_output=True, text=True, timeout=60, cwd=self.tmp)
        self.assertEqual(done.returncode, 0, done.stderr)
        submitted = self.log.read_text(encoding="utf-8")
        self.assertIn(f"RUN={self.tmp.resolve()}/rel ", submitted)
        self.assertIn(f"CATALOG={self.tmp.resolve()}/catalog.sqlite ", submitted)

    def test_a_path_with_a_comma_or_an_extra_colon_is_refused(self):
        done, lines = self.submit("--catalog", str(self.catalog), str(self.make_run("a")), "--sweep", "case134:/f:/b:/c")
        self.assertEqual(done.returncode, 64)
        self.assertEqual(lines, [])
        comma = self.tmp / "a,b"
        comma.mkdir()
        done, lines = self.submit("--catalog", str(self.catalog), str(comma))
        self.assertEqual(done.returncode, 64)

    def test_runs_without_a_catalog_are_refused(self):
        done, lines = self.submit(str(self.make_run("a")))
        self.assertEqual(done.returncode, 64)
        self.assertEqual(lines, [])



class LatencyJobTest(unittest.TestCase):
    """grid/latency-sweep.sbatch's network parts: each starts the launched flow latency with its
    part's words, reports what the launcher said and ends with its exit, and hears job submit's
    early TERM at once; a fake pixi stands in for the launcher, so no flow runs."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = self.tmp / "repo"
        (self.repo / "grid").mkdir(parents=True)
        (self.repo / "grid" / "latency-sweep.sbatch").write_bytes((GRID / "latency-sweep.sbatch").read_bytes())
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        (bin_dir / "pixi").write_text(FAKE_PIXI, encoding="utf-8")
        (bin_dir / "pixi").chmod(0o755)
        self.calls = self.tmp / "pixi.log"
        self.run_dir = LatencyGridTest.make_run(self, "run-a")
        self.catalog = self.tmp / "catalog.sqlite"
        self.catalog.write_bytes(b"")
        self.base = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}", SCHWINGNET=str(self.repo), FAKE_PIXI_LOG=str(self.calls),
                         RUN=str(self.run_dir), CATALOG=str(self.catalog), SLURM_JOB_ID="55")
        self.base.pop("SLURM_ARRAY_TASK_ID", None)

    def job(self, **extra):
        done = subprocess.run(["bash", str(self.repo / "grid" / "latency-sweep.sbatch")], env=dict(self.base, **extra),
                              capture_output=True, text=True, timeout=60)
        return done, self.calls.read_text(encoding="utf-8").splitlines() if self.calls.exists() else []

    def report(self, label):
        return (self.repo / "grid" / "logs" / f"latency-{label}-STAGE-REPORT.md").read_text(encoding="utf-8")

    def test_the_gpu_part_starts_the_launched_flow_and_ends_with_its_exit_and_its_lines(self):
        done, calls = self.job(PART="gpu", FAKE_PIXI_RC="1")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("SN_LATENCY_RC=1", done.stdout)
        self.assertEqual(calls, [f"run --locked -e train-gpu python flows/launch.py latency --max-workers 1 -- --part gpu "
                                 f"--run-dir {self.run_dir} --catalog {self.catalog} --threads 8 --frames 300"])
        report = self.report("gpu")
        for line in ('- launcher: {"decision": "run", "flow": "latency", "key": "k", "origin": null}',
                     "- r1: current as an earlier run wrote it; CLAIM 2024: 20 met", "- part gpu, verdict 1",
                     '- Metaflow: {"flow": "latency", "run": "LatencyFlow/3", "successful": true, "verdict": 1}', "- launcher exited 1"):
            self.assertIn(line + "\n", report)

    def test_the_cpu_part_runs_in_the_cpu_environment_on_its_threads(self):
        done, calls = self.job(PART="cpu", THREADS="4")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(calls, [f"run --locked -e train-cpu python flows/launch.py latency --max-workers 1 -- --part cpu "
                                 f"--run-dir {self.run_dir} --catalog {self.catalog} --threads 4 --frames 300"])
        self.assertIn("- launcher exited 0\n", self.report("cpu"))

    def test_each_task_of_the_sweep_array_runs_its_own_sweep(self):
        done, calls = self.job(PART="sweep", SWEEPS="case134:bank=/b case39:/f:/b.jsonl", SLURM_ARRAY_TASK_ID="1")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(calls, [f"run --locked -e train-gpu python flows/launch.py latency --max-workers 1 -- --part sweep "
                                 f"--run-dir {self.run_dir} --sweep case39:/f:/b.jsonl --sweep-runtime onnxruntime --box-source truth"])
        self.assertIn("- sweep: case39\n", self.report("sweep-1"))

    def test_job_submits_early_term_reaches_the_latency_launcher_at_once(self):
        # As the sweep driver's: job submit's TERM two minutes before the limit goes to the batch
        # shell alone, and a launcher run in the shell's foreground would not hear it in time.
        held, stopped = self.tmp / "held", self.tmp / "stopped"
        job = subprocess.Popen(["bash", str(self.repo / "grid" / "latency-sweep.sbatch")],
                               env=dict(self.base, PART="gpu", FAKE_PIXI_HOLD=str(held), FAKE_PIXI_STOPPED=str(stopped)),
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.addCleanup(job.kill)
        for _ in range(300):
            if held.exists():
                break
            time.sleep(0.1)
        began = time.monotonic()
        job.send_signal(signal.SIGTERM)
        out, _ = job.communicate(timeout=60)
        self.assertLess(time.monotonic() - began, 30, out)
        self.assertEqual(job.returncode, 143, out)
        self.assertEqual(stopped.read_text(encoding="utf-8"), "TERM\n")
        self.assertIn("SN_LATENCY_RC=143", out)
        report = self.report("gpu")
        self.assertIn('- Metaflow: {"flow": "latency", "run": "LatencyFlow/4", "successful": false', report)
        self.assertIn("- launcher exited 143\n", report)


if __name__ == "__main__":
    unittest.main()
