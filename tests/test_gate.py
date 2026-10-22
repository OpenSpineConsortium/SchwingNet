"""grid/gate.sh (issue #53), the one script the Beethoven grid gate calls with a fixed word, and the
jobs it submits: every script parses; a word outside the list, an argument where none belongs and an
id that is not a plain name are refused before anything is submitted; start submits the whole graph
with its Slurm dependencies, leaving out the setup and weights jobs when their results are there;
start refuses while one of the gate's jobs is live; stop cancels the gate's jobs and nothing else;
a credentialed fetch needs ~/.netrc at mode 600 with a PhysioNet line; v1 and latency find their
catalog. Fake sbatch, squeue, sacct, scancel and df on PATH record what would be submitted; nothing
reaches a scheduler. Standard library only, so the required check runs it."""

import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRID = ROOT / "grid"
NEW_SCRIPTS = ("gate.sh", "box.sh", "bin/pixi", "bin/train-cpu-python", "00-setup.sbatch", "00-weights.sbatch",
               "00-carmlspine.sbatch", "v1-driver.sbatch", "run-xray-chain.sh", "run-platform-fetch.sh")
ENVS = ("default", "train-cpu", "train-gpu", "telemetry")

FAKES = {
    # one job id per call, counting from 101, each call's arguments and dependency-bearing variables logged
    # a call whose arguments hold the text of $FAKE/refuse is refused, as a busy controller refuses one
    "sbatch": """#!/bin/bash
if [ -s "$FAKE/refuse" ] && [[ "$*" == *"$(cat "$FAKE/refuse")"* ]]; then echo "Socket timed out" >&2; exit 1; fi
n=$(( $(wc -l < "$FAKE/sbatch.log" 2>/dev/null || echo 0) + 101 ))
echo "$* | DEPEND=${DEPEND:-} FETCH_ARGS=${FETCH_ARGS:-} DATA_ROOT=${DATA_ROOT:-}" >> "$FAKE/sbatch.log"
echo "$n"
""",
    "squeue": """#!/bin/bash
[ -f "$FAKE/squeue_fails" ] && { echo "slurm_load_jobs error: Socket timed out" >&2; exit 1; }
cat "$FAKE/queue" 2>/dev/null || true
""",
    # what $FAKE/sacct.out holds, else one finished job; its arguments logged
    "sacct": """#!/bin/bash
echo "$*" >> "$FAKE/sacct.log"
if [ -f "$FAKE/sacct.out" ]; then cat "$FAKE/sacct.out"; else echo "101|sn_setup|COMPLETED|00:01:00|0:0|node1"; fi
""",
    "scancel": """#!/bin/bash
echo "$*" >> "$FAKE/scancel.log"
""",
    "df": """#!/bin/bash
echo "Avail"
echo "900000G"
""",
}


class GateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.fake = self.tmp / "fake"
        self.fake.mkdir()
        for name, text in FAKES.items():
            (self.fake / name).write_text(text, encoding="utf-8")
            (self.fake / name).chmod(0o755)
        # a copy of the checkout's grid/, so a test's logs and id files never land in the checkout
        self.repo = self.tmp / "SchwingNet"
        shutil.copytree(GRID, self.repo / "grid", ignore=shutil.ignore_patterns("logs", "LAST_*"))
        (self.repo / "pixi.lock").write_text("lock\n", encoding="utf-8")
        (self.repo / "tools").mkdir()
        (self.repo / "tools" / "leaks.py").write_text("", encoding="utf-8")
        self.data = self.tmp / "data"
        self.runs = self.tmp / "runs"
        self.models = self.tmp / "models"
        for folder in (self.data, self.runs, self.models):
            folder.mkdir()
        self.netrc = self.tmp / "netrc"

    def gate(self, *words, data_root=None):
        env = dict(os.environ, PATH=f"{self.fake}:{os.environ['PATH']}", FAKE=str(self.fake), SCHWINGNET=str(self.repo),
                   DATA_ROOT=str(self.data) if data_root is None else data_root, RUNS=str(self.runs), MODELS=str(self.models),
                   NETRC=str(self.netrc), USER="go2432")
        for name in ("SBATCH", "SQUEUE", "SACCT", "SCANCEL", "DF", "DEPEND", "PYDRV"):
            env.pop(name, None)
        if data_root == "":
            env.pop("DATA_ROOT")
        return subprocess.run(["bash", str(self.repo / "grid" / "gate.sh"), *words], env=env, capture_output=True, text=True, timeout=120)

    def submitted(self):
        log = self.fake / "sbatch.log"
        return log.read_text(encoding="utf-8").splitlines() if log.exists() else []

    def recorded(self):
        state = self.repo / "grid" / "logs" / "GATE_JOBS.txt"
        lines = state.read_text(encoding="utf-8").splitlines() if state.exists() else []
        return {line.split()[2]: line.split()[0] for line in lines}

    def environments_ready(self):
        for env in ENVS:
            python = self.repo / ".pixi" / "envs" / env / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.write_text("#!/bin/sh\n", encoding="utf-8")
            python.chmod(0o755)
        digest = hashlib.sha256(b"lock\n").hexdigest()
        (self.repo / ".pixi" / "SETUP.sha256").write_text(digest + "\n", encoding="utf-8")

    def weights_ready(self):
        (self.models / "resnet18-f37072fd.pth").write_bytes(b"weights")
        (self.models / "resnet18-f37072fd.pth.sha256").write_text("f37072fd" + "0" * 56 + "\n", encoding="utf-8")

    def catalog_ready(self, version=3, carmlspine_test=True):
        """A version in the store as tools/catalog.py writes one: its file, its line in VERSIONS.jsonl
        (compact, as pydantic writes it) and CURRENT naming it."""
        store = self.data / "_catalog"
        versions = store / "versions"
        versions.mkdir(parents=True, exist_ok=True)
        name = f"catalog-{version:06d}-0123456789ab.sqlite"
        (versions / name).write_bytes(b"")
        parts = '"carmlspine|test":59,"carmlspine|train":50' if carmlspine_test else '"vindr_pcxr|train":7'
        with (store / "VERSIONS.jsonl").open("a", encoding="utf-8") as log:
            log.write(f'{{"version":{version},"file":"{name}","sha256":"{"0" * 64}","frames_by_source_and_part":{{{parts}}}}}\n')
        (store / "CURRENT").write_text(name + "\n", encoding="utf-8")
        return versions / name

    def carmlspine_shards(self):
        for kind, folder in (("train", "2026-10-21-c8ea18032437"), ("test", "2026-10-21-2f554446fe70")):
            shard = self.data / "carmlspine" / "shards" / folder
            shard.mkdir(parents=True)
            (shard / "MANIFEST.json").write_text(f'{{\n "kind": "{kind}",\n "source": "carmlspine"\n}}\n', encoding="utf-8")

    def line_of(self, script):
        return [line for line in self.submitted() if script in line]

    def test_every_new_script_parses(self):
        for name in NEW_SCRIPTS:
            done = subprocess.run(["bash", "-n", str(GRID / name)], capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, f"{name}: {done.stderr}")

    def test_the_scripts_the_gate_and_the_jobs_run_are_executable(self):
        for name in ("gate.sh", "box.sh", "bin/pixi", "bin/train-cpu-python"):
            self.assertTrue(os.access(GRID / name, os.X_OK), name)

    def test_a_word_outside_the_list_or_a_stray_argument_is_refused(self):
        for words in (("rm",), (), ("start", "now"), ("status", "-v"), ("v1 latency",), ("start status",),
                      ("latency fetch",), (" start",), ("fetch",), ("fetch", "../netrc"),
                      ("fetch", "VinDr"), ("fetch", "a" * 41), ("fetch", "a", "b")):
            done = self.gate(*words)
            self.assertEqual(done.returncode, 64, f"{words}: {done.stdout}{done.stderr}")
        self.assertEqual(self.submitted(), [])

    def test_start_from_nothing_submits_the_whole_graph_with_its_dependencies(self):
        done = self.gate("start")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        jobs = self.recorded()
        for what in ("setup", "weights", "carmlspine", "catalog", "xr_fetch", "xr_bank", "xr_catalog", "probe", "v1_driver"):
            self.assertIn(what, jobs, done.stdout)
        self.assertTrue(any(what.startswith("dp_") for what in jobs), done.stdout)
        setup, weights, ingest, first = jobs["setup"], jobs["weights"], jobs["carmlspine"], jobs["catalog"]
        self.assertNotIn("--dependency", self.line_of("00-setup.sbatch")[0])
        self.assertIn(f"--dependency=afterok:{setup} ", self.line_of("00-carmlspine.sbatch")[0])
        # the first catalog after the ingest; the chain's own catalog after its bank and the first
        catalogs = self.line_of("03-catalog.sbatch")
        self.assertEqual(len(catalogs), 2, catalogs)
        self.assertIn(f"--dependency=afterok:{setup},afterany:{ingest} ", catalogs[0])
        self.assertIn(f"--dependency=afterany:{jobs['xr_bank']},afterany:{first} ", catalogs[1])
        # the fetch waits on the environments alone, not on the C-ArmLSpine ingest
        self.assertIn(f"--dependency=afterok:{setup} ", self.line_of("01-fetch.sbatch")[0])
        self.assertIn(f"--dependency=afterany:{jobs['xr_fetch']} ", self.line_of("02-bank-ingest.sbatch")[0])
        # X-ray before CT: the first platform job waits on the X-ray fetch
        self.assertIn(f"--dependency=afterany:{jobs['xr_fetch']} ", self.line_of("platform-fetch.sbatch")[0])
        self.assertIn("PART=probe", self.line_of("latency-sweep.sbatch")[0])
        v1 = self.line_of("v1-driver.sbatch")[0]
        self.assertIn(f"--dependency=afterok:{first},afterok:{ingest},afterok:{setup},afterok:{weights} ", v1)
        self.assertIn("--kill-on-invalid-dep=yes", v1)
        # the stages run their Python through the container's shim
        self.assertIn("pydrv=" + str(self.repo / "grid" / "bin" / "train-cpu-python"), (self.repo / "grid" / "LAST_RUN.txt").read_text(encoding="utf-8"))

    def test_start_leaves_out_what_is_already_there(self):
        self.environments_ready()
        self.weights_ready()
        done = self.gate("start")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        jobs = self.recorded()
        self.assertNotIn("setup", jobs)
        self.assertNotIn("weights", jobs)
        self.assertEqual(self.line_of("00-setup.sbatch") + self.line_of("00-weights.sbatch"), [])
        self.assertNotIn("--dependency", self.line_of("00-carmlspine.sbatch")[0])
        self.assertNotIn("--dependency", self.line_of("01-fetch.sbatch")[0])
        self.assertIn(f"--dependency=afterany:{jobs['carmlspine']} ", self.line_of("03-catalog.sbatch")[0])
        self.assertIn(f"--dependency=afterok:{jobs['catalog']},afterok:{jobs['carmlspine']} ", self.line_of("v1-driver.sbatch")[0])

    def test_start_refuses_while_a_job_of_the_gate_is_live_and_stop_cancels_only_its_own(self):
        self.assertEqual(self.gate("start").returncode, 0)
        count = len(self.submitted())
        jobs = self.recorded()
        (self.fake / "queue").write_text(f"{jobs['xr_catalog']}\n99999\n{jobs['probe']}_[0-1]\n", encoding="utf-8")
        done = self.gate("start")
        self.assertEqual(done.returncode, 75, done.stdout)
        self.assertEqual(len(self.submitted()), count)
        done = self.gate("stop")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        cancelled = (self.fake / "scancel.log").read_text(encoding="utf-8").split()
        self.assertEqual(sorted(cancelled), sorted([jobs["xr_catalog"], jobs["probe"]]))

    def test_leaks_wait_for_the_catalog(self):
        self.environments_ready()
        self.assertEqual(self.gate("start").returncode, 0)
        count = len(self.submitted())
        for what in ("catalog", "xr_catalog"):
            (self.fake / "queue").write_text(self.recorded()[what] + "\n", encoding="utf-8")
            self.assertEqual(self.gate("leaks").returncode, 75, what)
            self.assertEqual(len(self.submitted()), count)

    def test_a_credentialed_fetch_needs_the_netrc(self):
        self.environments_ready()
        done = self.gate("fetch", "vindr_pcxr")
        self.assertEqual(done.returncode, 2, done.stdout)
        self.netrc.write_text("machine physionet.org login x password y\n", encoding="utf-8")
        self.netrc.chmod(0o644)
        done = self.gate("fetch", "vindr_pcxr")
        self.assertEqual(done.returncode, 2, done.stdout)
        self.assertNotIn("password", done.stdout + done.stderr)
        self.netrc.chmod(0o600)
        done = self.gate("fetch", "vindr_pcxr")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertNotIn("password", done.stdout + done.stderr)
        fetch = self.line_of("01-fetch.sbatch")
        self.assertEqual(len(fetch), 1)
        self.assertIn("FETCH_ARGS=--only vindr_pcxr --credentialed", fetch[0])
        self.assertEqual(self.submitted()[0], fetch[0])
        self.assertIn("xr_catalog", self.recorded())

    def test_an_id_not_on_the_list_is_refused(self):
        self.assertEqual(self.gate("fetch", "nosuchset").returncode, 64)
        self.assertEqual(self.submitted(), [])

    def test_v1_with_every_input_there_submits_the_run_alone(self):
        self.environments_ready()
        self.weights_ready()
        self.carmlspine_shards()
        self.catalog_ready(version=2)
        self.catalog_ready(version=3, carmlspine_test=False)
        done = self.gate("v1")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(len(self.submitted()), 1, self.submitted())
        line = self.line_of("v1-driver.sbatch")[0]
        self.assertNotIn("--dependency", line)
        self.assertIn(f"RUNS={self.runs},WEIGHTS={self.models}/resnet18-f37072fd.pth", line)
        self.assertIn("catalog-000002-0123456789ab.sqlite holds C-ArmLSpine's test part; no job", done.stdout)

    def test_v1_from_nothing_submits_every_input_and_the_run_afterok_on_each(self):
        done = self.gate("v1")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        jobs = self.recorded()
        setup, weights, ingest, catalog = jobs["setup"], jobs["weights"], jobs["carmlspine"], jobs["catalog"]
        self.assertIn(f"--dependency=afterok:{setup} ", self.line_of("00-carmlspine.sbatch")[0])
        # afterok, unlike start's afterany: a failed ingest cancels the build and the run with it
        self.assertIn(f"--dependency=afterok:{setup},afterok:{ingest} ", self.line_of("03-catalog.sbatch")[0])
        line = self.line_of("v1-driver.sbatch")[0]
        self.assertIn(f"--dependency=afterok:{catalog},afterok:{ingest},afterok:{weights},afterok:{setup} ", line)
        self.assertIn("--kill-on-invalid-dep=yes", line)
        self.assertEqual(self.line_of("01-fetch.sbatch") + self.line_of("platform-fetch.sbatch"), [])

    def test_v1_builds_a_catalog_when_no_version_holds_the_test_part(self):
        self.environments_ready()
        self.weights_ready()
        self.carmlspine_shards()
        self.catalog_ready(version=4, carmlspine_test=False)
        done = self.gate("v1")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        catalog = self.recorded()["catalog"]
        self.assertNotIn("--dependency", self.line_of("03-catalog.sbatch")[0])
        self.assertEqual(self.line_of("00-carmlspine.sbatch"), [])
        self.assertIn(f"--dependency=afterok:{catalog} ", self.line_of("v1-driver.sbatch")[0])

    def test_v1_runs_again_the_inputs_that_failed_while_start_is_still_live(self):
        # issue #74, the grid at 21:48 UTC: setup and weights done, start's C-ArmLSpine ingest and
        # first catalog failed, its X-ray and CT jobs still queued or running; start refuses
        self.assertEqual(self.gate("start").returncode, 0)
        started = self.recorded()
        self.environments_ready()
        self.weights_ready()
        still = [started[what] for what in started if what.startswith(("xr_", "dp_"))]
        self.live(*still)
        count = len(self.submitted())
        self.assertEqual(self.gate("start").returncode, 75)
        self.assertEqual(len(self.submitted()), count)
        done = self.gate("v1")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        new = self.submitted()[count:]
        self.assertEqual([line.split(" | ")[0].split()[-1] for line in new],
                         ["00-carmlspine.sbatch", "03-catalog.sbatch", "v1-driver.sbatch"], new)
        jobs = self.recorded()
        ingest, catalog = jobs["carmlspine"], jobs["catalog"]
        self.assertNotIn("--dependency", new[0])
        self.assertIn(f"--dependency=afterok:{ingest} ", new[1])
        self.assertIn(f"--dependency=afterok:{catalog},afterok:{ingest} ", new[2])
        # the X-ray chain's catalogs are never waited on: they wait on fetches that take days
        for job in (started["xr_catalog"], started["xr_fetch"]):
            for waits in (f":{job},", f":{job} "):
                self.assertNotIn(waits, new[1] + new[2])
        # a v1 sent again while its run is queued is refused; one sent while only its inputs are
        # queued waits on them and submits nothing else
        self.live(*still, ingest, catalog, jobs["v1_driver"])
        self.assertEqual(self.gate("v1").returncode, 75)
        self.live(*still, ingest, catalog)
        done = self.gate("v1")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(len(self.submitted()), count + 4)
        self.assertIn(f"--dependency=afterok:{catalog},afterok:{ingest} ", self.submitted()[-1])

    def test_v1_says_when_the_ingest_failed_at_the_same_commit(self):
        git = ["git", "-c", "gc.auto=0", "-c", "maintenance.auto=false", "-c", "user.name=t", "-c", "user.email=t@t",
               "-C", str(self.repo)]
        subprocess.run([*git, "init", "-q"], check=True)
        subprocess.run([*git, "add", "pixi.lock"], check=True)
        subprocess.run([*git, "commit", "-q", "-m", "c"], check=True)
        commit = subprocess.run([*git, "rev-parse", "--short", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
        logs = self.repo / "grid" / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        report = logs / "00-carmlspine-STAGE-REPORT.md"
        report.write_text(f"# C-ArmLSpine ingest: 2026-10-21 21:31:00, job 40697678 on n1, commit {commit}\n"
                          "- train (unfrozen persons) refused: AttributeError: 'str' object has no attribute 'get'\n", encoding="utf-8")
        self.environments_ready()
        self.weights_ready()
        done = self.gate("v1")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn(f"refused at this same commit {commit}", done.stdout)
        report.write_text("# C-ArmLSpine ingest: 2026-10-21 21:31:00, job 40697678 on n1, commit 0000000\n- refused\n", encoding="utf-8")
        self.live()
        (self.repo / "grid" / "logs" / "GATE_JOBS.txt").unlink()
        self.assertNotIn("same commit", self.gate("v1").stdout)

    def test_v1_waits_on_a_start_still_in_the_queue(self):
        # issue #74: start's own v1 job was refused, and its catalog, weights and C-ArmLSpine jobs are
        # still queued or running; v1 chains onto them with afterok rather than refusing until they end
        self.assertEqual(self.gate("start").returncode, 0)
        jobs = self.recorded()
        setup, weights, ingest, first = jobs["setup"], jobs["weights"], jobs["carmlspine"], jobs["catalog"]
        count = len(self.submitted())
        (self.fake / "queue").write_text(f"{setup}\n{weights}\n{ingest}\n{first}\n", encoding="utf-8")
        done = self.gate("v1")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(len(self.submitted()), count + 1)
        line = self.line_of("v1-driver.sbatch")[-1]
        self.assertIn(f"--dependency=afterok:{first},afterok:{ingest},afterok:{weights},afterok:{setup} ", line)
        self.assertIn("--kill-on-invalid-dep=yes", line)
        # the weights job gone and its file not there: v1 fetches the weights again rather than refusing
        (self.fake / "queue").write_text(f"{setup}\n{ingest}\n{first}\n", encoding="utf-8")
        state = self.repo / "grid" / "logs" / "GATE_JOBS.txt"
        state.write_text("".join(l + "\n" for l in state.read_text(encoding="utf-8").splitlines() if " v1_driver " not in l), encoding="utf-8")
        done = self.gate("v1")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(len(self.line_of("00-weights.sbatch")), 2)

    def test_v1_after_a_finished_start_waits_only_on_what_is_still_live(self):
        self.environments_ready()
        self.weights_ready()
        self.assertEqual(self.gate("start").returncode, 0)
        self.carmlspine_shards()
        first = self.recorded()["catalog"]
        (self.fake / "queue").write_text(f"{first}\n", encoding="utf-8")
        done = self.gate("v1")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn(f"--dependency=afterok:{first} ", self.line_of("v1-driver.sbatch")[-1])

    def run_catalog_job(self, pydrv):
        env = dict(os.environ, SCHWINGNET=str(self.repo), PYDRV=str(pydrv), DATA_ROOT=str(self.data), FAKE=str(self.fake),
                   TMPDIR_OVERRIDE=str(self.tmp / "t"), BUILD_LOCK_WAIT="60")
        env.pop("STORE", None)
        return subprocess.Popen(["bash", str(self.repo / "grid" / "03-catalog.sbatch")], cwd=self.repo / "grid", env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def test_two_catalog_builds_run_one_after_the_other_and_each_checks_its_own_version(self):
        # issue #74: start's first catalog, the X-ray chain's and a fetch's can start together; one
        # build that listed the manifests before another job's shards landed must never land last
        manifest = self.data / "carmlspine" / "shards" / "a" / "MANIFEST.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text("{}\n", encoding="utf-8")
        pydrv = self.fake / "pydrv"
        pydrv.write_text("""#!/bin/bash
echo "$2 start $$ $(grep -o -- '--manifest' <<< "$*" | wc -l) $*" >> "$FAKE/pydrv.log"
if [ "$2" = build ]; then
  sleep 2
  if [ ! -f "$FAKE/grown" ]; then : > "$FAKE/grown"; mkdir -p "$DATA_ROOT/vindr_pcxr/shards/b"; echo '{}' > "$DATA_ROOT/vindr_pcxr/shards/b/MANIFEST.json"; fi
  n=$(( $(cat "$FAKE/n" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$FAKE/n"
  echo "{\\"added_shards\\": [], \\"file\\": \\"catalog-00000$n-0123456789ab.sqlite\\", \\"new\\": true, \\"version\\": $n}"
fi
echo "$2 end $$" >> "$FAKE/pydrv.log"
""", encoding="utf-8")
        pydrv.chmod(0o755)
        jobs = [self.run_catalog_job(pydrv), self.run_catalog_job(pydrv)]
        outs = [job.communicate(timeout=120)[0] for job in jobs]
        self.assertEqual([job.returncode for job in jobs], [0, 0], outs)
        events = (self.fake / "pydrv.log").read_text(encoding="utf-8").splitlines()
        self.assertEqual([e.split()[:2] for e in events],
                         [["build", "start"], ["build", "end"], ["split-check", "start"], ["split-check", "end"]] * 2, events)
        # the second build listed the manifests only once the first had ended, so it saw the shard
        # that landed during the first
        builds = [e.split() for e in events if e.startswith("build start")]
        self.assertEqual([int(b[3]) for b in builds], [1, 2], events)
        checks = [e for e in events if e.startswith("split-check start")]
        self.assertTrue(checks[0].endswith("--version 1") and checks[1].endswith("--version 2"), checks)
        self.assertTrue((self.data / "_catalog" / "BUILD.lock").exists())

    def test_the_run_takes_the_newest_version_that_holds_c_armlspine_s_test_part(self):
        self.weights_ready()
        self.catalog_ready(version=2)
        self.catalog_ready(version=3, carmlspine_test=False)
        (self.repo / "grid" / "box.sh").write_text('#!/bin/bash\necho "$*" >> "$FAKE/box.log"\necho \'{"run_dir": "/nowhere"}\'\n', encoding="utf-8")
        env = dict(os.environ, SCHWINGNET=str(self.repo), DATA_ROOT=str(self.data), RUNS=str(self.runs), FAKE=str(self.fake),
                   WEIGHTS=str(self.models / "resnet18-f37072fd.pth"), SLURM_JOB_ID="777")
        env.pop("STORE", None)
        done = subprocess.run(["bash", str(self.repo / "grid" / "v1-driver.sbatch")], cwd=self.repo / "grid", env=env,
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        flow = [line for line in (self.fake / "box.log").read_text(encoding="utf-8").splitlines() if "flow.py" in line]
        self.assertIn(f"--catalog {self.data}/_catalog/versions/catalog-000002-0123456789ab.sqlite ", flow[0])
        self.assertIn("CURRENT names catalog-000003-0123456789ab.sqlite, which holds no C-ArmLSpine test part", done.stdout)
        # no version holds it: the run says so and never starts the flow
        (self.data / "_catalog" / "VERSIONS.jsonl").write_text("", encoding="utf-8")
        (self.fake / "box.log").unlink()
        done = subprocess.run(["bash", str(self.repo / "grid" / "v1-driver.sbatch")], cwd=self.repo / "grid", env=env,
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 1)
        self.assertIn("holds C-ArmLSpine's test part", done.stdout)
        self.assertFalse((self.fake / "box.log").exists())

    def test_v1_never_waits_on_an_x_ray_chains_catalog(self):
        # start's first catalog ended without a version while its X-ray chain's catalog still waits
        # behind a fetch of days: v1 builds a catalog of its own and never waits on that job
        self.environments_ready()
        self.weights_ready()
        self.assertEqual(self.gate("start").returncode, 0)
        self.carmlspine_shards()
        xr_catalog = self.recorded()["xr_catalog"]
        count = len(self.submitted())
        self.live(xr_catalog)
        done = self.gate("v1")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        new = self.submitted()[count:]
        self.assertEqual(len(new), 2, new)
        self.assertIn("03-catalog.sbatch", new[0])
        for waits in (f":{xr_catalog},", f":{xr_catalog} "):
            self.assertNotIn(waits, new[0] + new[1])
        self.assertIn(f"--dependency=afterok:{self.recorded()['catalog']} ", new[1])

    def test_every_job_header_names_its_qos_and_a_gpu_job_takes_the_gpu_qos(self):
        # Slurm refused the version 1 run for a GPU partition with no QoS (issue #74); a GPU job takes
        # the gpu QoS on gmsap, gvohp or galhp, as Beethoven for VS Code submits one
        for script in sorted(GRID.glob("*.sbatch")):
            header = [line for line in script.read_text(encoding="utf-8").splitlines() if line.startswith("#SBATCH")]
            partitions = [line.split("=", 1)[1] for line in header if line.startswith("#SBATCH --partition=")]
            qos = [line.split("=", 1)[1] for line in header if line.startswith("#SBATCH --qos=")]
            self.assertEqual(len(partitions), 1, script.name)
            self.assertEqual(len(qos), 1, f"{script.name}: a partition with no QoS")
            if any(line.startswith("#SBATCH --gres=gpu") for line in header):
                self.assertEqual(qos, ["gpu"], script.name)
                self.assertTrue(set(partitions[0].split(",")) <= {"gmsap", "gvohp", "galhp"}, script.name)
            else:
                self.assertEqual((partitions, qos), (["reqp"], ["requeue"]), script.name)
        header = (GRID / "v1-driver.sbatch").read_text(encoding="utf-8")
        self.assertIn("#SBATCH --partition=gmsap,gvohp,galhp\n#SBATCH --qos=gpu\n#SBATCH --gres=gpu:1\n", header)

    def test_latency_takes_the_newest_run_with_a_checkpoint_and_its_catalog(self):
        self.environments_ready()
        catalog = self.catalog_ready(version=3)
        self.assertEqual(self.gate("latency").returncode, 2)
        run = self.runs / "run-a"
        (run / "train").mkdir(parents=True)
        (run / "RUN.json").write_text('{\n "catalog_version": 3,\n "seed": 1\n}\n', encoding="utf-8")
        (run / "train" / "best.pt").write_bytes(b"w")
        self.assertEqual(self.gate("latency").returncode, 2, "a run still training has no checkpoint.json")
        (run / "train" / "checkpoint.json").write_text("{}\n", encoding="utf-8")
        done = self.gate("latency")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        lines = self.line_of("latency-sweep.sbatch")
        self.assertEqual(len(lines), 3)
        self.assertIn(f"CATALOG={catalog}", lines[0])
        self.assertIn(f"SWEEPS=case134:bank={self.data}/realxray/carmlspine_sweep", lines[2])
        self.assertTrue({"latency_gpu", "latency_cpu", "latency_sweep"} <= set(self.recorded()))

    def test_latency_passes_over_a_run_still_training_for_the_newest_finished_one(self):
        self.environments_ready()
        self.catalog_ready(version=3)
        finished, training = self.runs / "run-a", self.runs / "run-b"
        for run in (finished, training):
            (run / "train").mkdir(parents=True)
            (run / "RUN.json").write_text('{\n "catalog_version": 3,\n "seed": 1\n}\n', encoding="utf-8")
            (run / "train" / "best.pt").write_bytes(b"w")
        (finished / "train" / "checkpoint.json").write_text("{}\n", encoding="utf-8")
        os.utime(finished, (1_000_000_000, 1_000_000_000))
        done = self.gate("latency")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        lines = self.line_of("latency-sweep.sbatch")
        self.assertTrue(lines and all(f"RUN={finished}," in line for line in lines), lines)
        status = self.gate("status")
        self.assertIn("has not finished", status.stdout)

    def live(self, *jobs):
        (self.fake / "queue").write_text("".join(f"{job}\n" for job in jobs), encoding="utf-8")

    def state_line(self, job, word, what):
        state = self.repo / "grid" / "logs" / "GATE_JOBS.txt"
        state.parent.mkdir(parents=True, exist_ok=True)
        with state.open("a", encoding="utf-8") as out:
            out.write(f"{job} {word} {what} 2026-10-21T20:00:00Z\n")

    def test_a_failed_squeue_refuses_every_word_that_submits_or_cancels(self):
        self.environments_ready()
        self.weights_ready()
        (self.fake / "squeue_fails").write_text("", encoding="utf-8")
        for words in (("start",), ("leaks",), ("v1",), ("latency",), ("fetch", "aariz"), ("stop",)):
            done = self.gate(*words)
            self.assertEqual(done.returncode, 75, f"{words}: {done.stdout}")
            self.assertIn("squeue failed", done.stdout)
        self.assertEqual(self.submitted(), [])
        self.assertFalse((self.fake / "scancel.log").exists())
        self.assertEqual(self.gate("status").returncode, 0)

    def test_a_chain_refused_part_way_is_cancelled_and_ct_waits_for_x_ray(self):
        (self.fake / "refuse").write_text("02-bank-ingest", encoding="utf-8")
        done = self.gate("start")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        fetch = self.line_of("01-fetch.sbatch")
        self.assertEqual(len(fetch), 1)
        fetch_id = str(101 + self.submitted().index(fetch[0]))
        self.assertEqual((self.fake / "scancel.log").read_text(encoding="utf-8").split(), [fetch_id])
        self.assertNotIn("xr_fetch", self.recorded())
        self.assertEqual(self.line_of("platform-fetch.sbatch"), [])
        self.assertIn("X-ray before CT", done.stdout)
        # version 1 never waited on the X-ray chain, so it still goes in
        self.assertEqual(len(self.line_of("v1-driver.sbatch")), 1)

    def test_a_fetch_waits_for_its_own_set_and_for_the_live_catalogs(self):
        self.environments_ready()
        self.netrc.write_text("machine physionet.org login x password y\n", encoding="utf-8")
        self.netrc.chmod(0o600)
        self.assertEqual(self.gate("start").returncode, 0)
        started = self.recorded()
        self.live(started["xr_fetch"], started["catalog"], started["xr_catalog"])
        # an open set while start's chain fetches every open set: refused
        count = len(self.submitted())
        self.assertEqual(self.gate("fetch", "aariz").returncode, 75)
        self.assertEqual(len(self.submitted()), count)
        # a credentialed set goes in, its catalog job after every catalog still live
        done = self.gate("fetch", "vindr_pcxr")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        catalog = self.line_of("03-catalog.sbatch")[-1]
        self.assertIn(f"afterany:{started['catalog']},afterany:{started['xr_catalog']} ", catalog)
        # the same set again while its fetch is live: refused
        state = (self.repo / "grid" / "logs" / "GATE_JOBS.txt").read_text(encoding="utf-8")
        own = [line.split()[0] for line in state.splitlines() if line.split()[1:3] == ["fetch:vindr_pcxr", "xr_fetch"]]
        self.assertEqual(len(own), 1, state)
        self.live(own[0])
        count = len(self.submitted())
        self.assertEqual(self.gate("fetch", "vindr_pcxr").returncode, 75)
        self.assertEqual(len(self.submitted()), count)

    def test_leaks_and_latency_refuse_while_their_own_jobs_are_live(self):
        self.environments_ready()
        self.state_line(500, "leaks", "leaks_fingerprint")
        self.state_line(600, "latency", "latency_gpu")
        self.live(500, 600)
        done = self.gate("leaks")
        self.assertEqual(done.returncode, 75, done.stdout)
        self.assertIn("leak checks are still queued", done.stdout)
        done = self.gate("latency")
        self.assertEqual(done.returncode, 75, done.stdout)
        self.assertIn("latency jobs are still queued", done.stdout)
        self.assertEqual(self.submitted(), [])

    def test_status_reads_the_jobs_and_never_fails(self):
        self.assertEqual(self.gate("status").returncode, 0)
        self.assertEqual(self.gate("start").returncode, 0)
        done = self.gate("status")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("101 setup COMPLETED", done.stdout)
        self.assertIn("--format=JobID,JobName,State,Elapsed,ExitCode,NodeList", (self.fake / "sacct.log").read_text(encoding="utf-8"))

    def failed(self, *rows):
        """rows of (id, word, what, job name, state, elapsed, log lines or None): the gate's list, what
        sacct says of them and their logs"""
        logs = self.repo / "grid" / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        sacct = []
        for job, word, what, name, state, elapsed, lines in rows:
            base = str(job).split("_")[0]
            state_file = logs / "GATE_JOBS.txt"
            if base not in (state_file.read_text(encoding="utf-8").split() if state_file.exists() else []):
                self.state_line(base, word, what)
            sacct.append(f"{job}|{name}|{state}|{elapsed}|1:0|n1")
            if lines is not None:
                (logs / f"{name}_{job}.out").write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
        (self.fake / "sacct.out").write_text("".join(f"{row}\n" for row in sacct), encoding="utf-8")

    def test_status_shows_the_end_of_an_open_jobs_log_masked_and_cut(self):
        lines = [f"pixi line {i}" for i in range(30)] + ["x" * 300, "token=abcdef0123456789 and https://u:p@host/x"]
        self.failed((300, "start", "setup", "sn_setup", "FAILED", "00:00:10", lines))
        done = self.gate("status")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("## 300 (sn_setup) ended FAILED after 00:00:10, exit 1:0: logs/sn_setup_300.out", done.stdout)
        self.assertIn("pixi line 29", done.stdout)
        self.assertNotIn("pixi line 15\n", done.stdout)
        self.assertIn("    pixi line 17\n", done.stdout)
        self.assertIn("    " + "x" * 200 + "\n", done.stdout)
        self.assertNotIn("x" * 201, done.stdout)
        self.assertNotIn("abcdef0123456789", done.stdout)
        self.assertNotIn("u:p@", done.stdout)

    def test_status_shows_a_dicom_jobs_log_only_as_its_traceback_and_status_lines(self):
        lines = ["XR_FETCH start 2026-10-21 21:30:00 on n1 job 301 restart 0: --only vindr_pcxr --credentialed",
                 "(0010, 0020) Patient ID                          LO: 'ABC123'",
                 "PatientName: DOE^JANE",
                 "person vindr_pcxr:9f86d081884c7d659a2feaa0c55ad015 holds more than one part",
                 "frames: 1.2.840.113619.2.55.3.604688119.868.1234567890.123",
                 "    \"vindr_spinexr:abc123\",",
                 "Traceback (most recent call last):",
                 '  File "/home/go2432/SchwingNet/tools/ingest.py", line 153, in item_of',
                 '    "lat_from_ap_deg": view.get("lat_from_ap_deg"),',
                 "                       ^^^^^^^^",
                 "AttributeError: 'str' object has no attribute 'get'",
                 "KeyError: 'carmlspine:case042'",
                 "HTTP request sent, awaiting response... 403 Forbidden",
                 "SN_CARMLSPINE_RC=1"]
        self.failed((301, "start", "carmlspine", "sn_carmlspine", "FAILED", "00:00:48", lines))
        done = self.gate("status")
        self.assertEqual(done.returncode, 0, done.stdout)
        for kept in ('  File "/home/go2432/SchwingNet/tools/ingest.py", line 153, in item_of',
                     "AttributeError: 'str' object has no attribute 'get'", "KeyError: <message withheld>",
                     "HTTP request sent, awaiting response... 403 Forbidden", "SN_CARMLSPINE_RC=1",
                     "XR_FETCH start 2026-10-21 21:30:00 on n1 job 301\n"):
            self.assertIn(kept, done.stdout)
        for value in ("ABC123", "DOE", "9f86d081", "1.2.840", "abc123", "case042", "credentialed"):
            self.assertNotIn(value, done.stdout)
        self.assertIn("(5 of its last 400 lines withheld", done.stdout)

    def test_status_shows_each_things_newest_job_and_says_what_never_started(self):
        self.failed((301, "start", "carmlspine", "sn_carmlspine", "FAILED", "00:00:48", ["old failure"]),
                    (302, "start", "xr_fetch", "xr_fetch", "RUNNING", "00:20:00", None),
                    (401, "v1", "carmlspine", "sn_carmlspine", "COMPLETED", "00:05:00", None),
                    (402, "v1", "v1_driver", "sn_v1", "CANCELLED by 0", "00:00:00", None),
                    (501, "fetch:vindr_pcxr", "xr_fetch", "xr_fetch", "FAILED", "00:00:08", ["XR_FETCH_RC=1"]))
        done = self.gate("status")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertNotIn("## 301", done.stdout)
        self.assertNotIn("## 302", done.stdout)
        self.assertIn("## 402 (sn_v1) ended CANCELLED after 00:00:00", done.stdout)
        self.assertIn("cancelled before it started", done.stdout)
        self.assertIn("## 501 (xr_fetch) ended FAILED", done.stdout)
        self.assertIn("    XR_FETCH_RC=1", done.stdout)

    def test_status_bounds_how_many_failed_jobs_and_array_tasks_it_shows(self):
        rows = [(600 + i, "start", f"dp_s{i}", f"dp_fetch_s{i}", "FAILED", "00:00:01", ["PLATFORM_RC=1"]) for i in range(8)]
        rows += [(f"700_{i}", "latency", "latency_sweep", "sn_latency", "TIMEOUT", "01:00:00", [f"SN_LATENCY_RC={i}"]) for i in range(3)]
        self.failed(*rows)
        done = self.gate("status")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertEqual(done.stdout.count("\n## 6"), 6, done.stdout)
        self.assertIn("## 4 more failed jobs not shown", done.stdout)
        rows = rows[8:] + rows[:1]
        self.failed(*rows)
        done = self.gate("status")
        self.assertIn("## 700_0 (sn_latency) ended TIMEOUT after 01:00:00, exit 1:0: logs/sn_latency_700_0.out", done.stdout)
        self.assertIn("    SN_LATENCY_RC=1", done.stdout)
        self.assertNotIn("700_2 (", done.stdout)

    def test_status_masks_the_stage_reports_and_bounds_what_it_prints(self):
        logs = self.repo / "grid" / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        (logs / "02-bank-ingest-STAGE-REPORT.md").write_text(
            "- vindr_spinexr: bank refused: person vindr_spinexr:9f86d081884c7d659a2feaa0c55ad015 holds more than one part (first 1.2.3.4.5.6)\n",
            encoding="utf-8")
        self.failed((300, "start", "setup", "sn_setup", "FAILED", "00:00:10", ["y" * 100000]))
        done = self.gate("status")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("bank refused: person <withheld> holds more than one part (first <withheld>)", done.stdout)
        self.assertNotIn("9f86d081", done.stdout)
        self.assertLess(len(done.stdout), 65536 + 400)

    def test_on_the_grid_the_stages_keep_their_own_data_paths(self):
        # stage 2 reads a set DATA_ROOT as its off-grid layout, so the gate passes none on the grid,
        # whether the caller sets nothing or the grid's own data root
        for given in ("", "/rs/rs_grp_oschome/go2432/data"):
            (self.fake / "sbatch.log").unlink(missing_ok=True)
            shutil.rmtree(self.repo / "grid" / "logs", ignore_errors=True)
            done = self.gate("start", data_root=given)
            self.assertEqual(done.returncode, 0, done.stdout)
            for script in ("01-fetch.sbatch", "02-bank-ingest.sbatch", "03-catalog.sbatch", "00-carmlspine.sbatch"):
                for line in self.line_of(script):
                    self.assertTrue(line.endswith("DATA_ROOT="), f"{given!r}: {line}")

    def test_a_probe_that_was_not_submitted_is_said_and_nothing_stale_is_recorded(self):
        (self.repo / "grid" / "LAST_LATENCY.txt").write_text("probe 999\ngpu /old/run 998\n", encoding="utf-8")
        (self.fake / "refuse").write_text("sn_probe", encoding="utf-8")
        done = self.gate("start")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("the probe was not submitted", done.stdout)
        state = (self.repo / "grid" / "logs" / "GATE_JOBS.txt").read_text(encoding="utf-8")
        self.assertNotIn("999", state)
        self.assertNotIn(" probe ", state)
        self.assertIn("v1_driver", state)

    def test_latency_records_only_the_jobs_its_own_call_submitted(self):
        self.environments_ready()
        catalog = self.catalog_ready(version=3)
        # a run folder whose name holds a comma is refused before the sweep script writes its id file,
        # so a stale probe line there would have been recorded as a latency job
        run = self.runs / "run,a"
        (run / "train").mkdir(parents=True)
        (run / "RUN.json").write_text('{"catalog_version": 3}', encoding="utf-8")
        (run / "train" / "best.pt").write_bytes(b"")
        (run / "train" / "checkpoint.json").write_text("{}\n", encoding="utf-8")
        (self.repo / "grid" / "LAST_LATENCY.txt").write_text("probe 999\n", encoding="utf-8")
        done = self.gate("latency")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("cannot be passed to the jobs", done.stdout)
        state = self.repo / "grid" / "logs" / "GATE_JOBS.txt"
        self.assertNotIn("999", state.read_text(encoding="utf-8") if state.exists() else "")
        self.assertTrue(catalog.exists())

    def test_the_version_1_hold_is_cleared_once_its_job_is_gone(self):
        logs = self.repo / "grid" / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        hold = logs / "HOLD"
        hold.write_text("555 0123456789abcdef\n", encoding="utf-8")
        self.live(555)
        done = self.gate("status")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertTrue(hold.exists())
        self.assertIn("holds still at 0123456", done.stdout)
        self.live()
        self.assertEqual(self.gate("status").returncode, 0)
        self.assertFalse(hold.exists())
        # a word squeue cannot answer for leaves the hold alone
        hold.write_text("555 0123456789abcdef\n", encoding="utf-8")
        (self.fake / "squeue_fails").write_text("", encoding="utf-8")
        self.assertEqual(self.gate("status").returncode, 0)
        self.assertEqual(self.gate("stop").returncode, 75)
        self.assertTrue(hold.exists())


if __name__ == "__main__":
    unittest.main()
