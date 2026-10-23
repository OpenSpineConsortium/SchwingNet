"""grid/gate.sh (issue #53), the one script the Beethoven grid gate calls with a fixed word, and the
jobs it submits: every script parses; a word outside the list, an argument where none belongs and an
id that is not a plain name are refused before anything is submitted; start submits the whole graph
with its Slurm dependencies, leaving out the setup and weights jobs when their results are there;
start refuses while one of the gate's jobs is live; stop cancels the gate's jobs and nothing else;
a credentialed fetch needs ~/.netrc at mode 600 with a PhysioNet line; v1 and latency find their
catalog. Every job goes through hpcworker's job submit with a class (issue #77): the fake hpcworker
under tests/fakes/ records what would be queued, and fake squeue, sacct, scancel and df on PATH
answer for Slurm; nothing reaches a scheduler. Standard library only, so the required check runs it."""

import hashlib
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRID = ROOT / "grid"
FAKE_HPCWORKER = ROOT / "tests" / "fakes" / "hpcworker"
NEW_SCRIPTS = ("gate.sh", "hpcw.sh", "box.sh", "bin/pixi", "bin/train-cpu-python", "00-setup.sbatch", "00-weights.sbatch",
               "00-carmlspine.sbatch", "v1-driver.sbatch", "run-xray-chain.sh", "run-platform-fetch.sh")
ENVS = ("default", "train-cpu", "train-gpu", "telemetry")

FAKES = {
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
    # df -B1 --output=avail, in bytes, as grid/size-rule.sh asks it where no CephFS quota answers
    "df": """#!/bin/bash
echo "Avail"
echo "900000000000000"
""",
    # stat -f -c %T as grid/size-rule.sh asks it before df: a mount that is no CephFS, kernel or FUSE,
    # so the stand-in df may answer for it; named so it never stands in for stat itself
    "fstype": """#!/bin/bash
echo "ext2/ext3"
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
        # the freeze and the rule the split-check marker names (grid/03-catalog.sbatch, grid/v1-version.sh)
        shutil.copytree(ROOT / "data" / "splits", self.repo / "data" / "splits")
        self.data = self.tmp / "data"
        self.runs = self.tmp / "runs"
        self.models = self.tmp / "models"
        for folder in (self.data, self.runs, self.models):
            folder.mkdir()
        self.netrc = self.tmp / "netrc"

    def gate(self, *words, data_root=None):
        env = self.gate_env(data_root)
        if data_root == "":
            env.pop("DATA_ROOT")
        return subprocess.run(["bash", str(self.repo / "grid" / "gate.sh"), *words], env=env, capture_output=True, text=True, timeout=120)

    def gate_env(self, data_root=None):
        env = dict(os.environ, PATH=f"{self.fake}:{os.environ['PATH']}", FAKE=str(self.fake), SCHWINGNET=str(self.repo),
                   DATA_ROOT=str(self.data) if data_root is None else data_root, RUNS=str(self.runs), MODELS=str(self.models),
                   NETRC=str(self.netrc), USER="go2432", HPCWORKER=str(FAKE_HPCWORKER),
                   HPCW_LOG=str(self.fake / "sbatch.log"), HPCW_REFUSE=str(self.fake / "refuse"), HPCW_LOGS=str(self.fake / "joblogs"), SHARED_DATA=str(self.tmp / "shared"))
        for name in ("GETFATTR", "VOLUME", "HPCW_DRY", "HPCW_FIRST", "HPCW_FRAMEWORK", "SBATCH", "SQUEUE", "SACCT", "SCANCEL", "DF", "DEPEND", "PYDRV"):
            env.pop(name, None)
        env["STAT"] = str(self.fake / "fstype")
        return env

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

    SHARDS = ("2026-10-21-c8ea18032437", "2026-10-21-2f554446fe70")

    def catalog_ready(self, version=3, carmlspine_test=True, shards=SHARDS, checked=True):
        """A version in the store as tools/catalog.py writes one: its file, its line in VERSIONS.jsonl
        (compact, as pydantic writes it) and CURRENT naming it, and, when checked, the split-check
        marker grid/03-catalog.sbatch writes for today's freeze and rule."""
        store = self.data / "_catalog"
        versions = store / "versions"
        versions.mkdir(parents=True, exist_ok=True)
        name = f"catalog-{version:06d}-0123456789ab.sqlite"
        (versions / name).write_bytes(b"")
        parts = '"carmlspine|test":59,"carmlspine|train":50' if carmlspine_test else '"vindr_pcxr|train":7'
        listed = ",".join(f'"{shard}"' for shard in shards)
        with (store / "VERSIONS.jsonl").open("a", encoding="utf-8") as log:
            log.write(f'{{"version":{version},"file":"{name}","sha256":"{"0" * 64}","shards":[{listed}],'
                      f'"frames_by_source_and_part":{{{parts}}}}}\n')
        (store / "CURRENT").write_text(name + "\n", encoding="utf-8")
        if checked:
            self.mark(name)
        return versions / name

    def mark(self, name, persons=None):
        """The split-check marker of a version, against the freeze as it is or the digest given."""
        checked = self.data / "_catalog" / "checked"
        checked.mkdir(parents=True, exist_ok=True)
        splits = self.repo / "data" / "splits"
        persons = persons or hashlib.sha256((splits / "test-persons.json").read_bytes()).hexdigest()
        rule = hashlib.sha256((splits / "rule.json").read_bytes()).hexdigest()
        (checked / name).write_text(f"commit abc1234\ntest-persons {persons}\nrule {rule}\n", encoding="utf-8")

    def carmlspine_shards(self):
        for kind, folder in zip(("train", "test"), self.SHARDS):
            self.shard(folder, kind)

    def shard(self, name, kind, supersedes=None):
        """A C-ArmLSpine shard's manifest as tools/ingest.py writes one: indent 1, sorted keys."""
        shard = self.data / "carmlspine" / "shards" / name
        shard.mkdir(parents=True)
        later = f'"{supersedes}"' if supersedes else "null"
        (shard / "MANIFEST.json").write_text(
            f'{{\n "items": [\n  {{\n   "name": "frame"\n  }}\n ],\n "kind": "{kind}",\n "name": "{name}",\n'
            f' "source": "carmlspine",\n "supersedes": {later}\n}}\n', encoding="utf-8")

    def chosen(self):
        """What grid/v1-version.sh chooses now: its exit code and what it said."""
        done = subprocess.run(["bash", str(self.repo / "grid" / "v1-version.sh"), str(self.data / "_catalog"), str(self.data),
                               str(self.repo)], capture_output=True, text=True, timeout=60)
        return done.returncode, (done.stdout + done.stderr).strip()

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

    def gate_at_home(self, *words):
        """The gate with HOME in the test's folder, where a gated source's token or link file is looked for."""
        home = self.tmp / "home"
        home.mkdir(exist_ok=True)
        env = dict(self.gate_env(), HOME=str(home))
        return subprocess.run(["bash", str(self.repo / "grid" / "gate.sh"), *words], env=env, capture_output=True, text=True,
                              timeout=120)

    def link_file(self, mode):
        link = self.tmp / "home" / ".rsna" / "ratic_link"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.write_text("https://example.invalid/ratic.zip?X-Amz-Signature=secretpart\n", encoding="utf-8")
        link.chmod(mode)

    def test_a_gated_ct_source_needs_its_file_and_is_fetched_alone(self):
        ratic = "rsna_ratic_abdominal_trauma"
        done = self.gate_at_home("fetch", ratic)
        self.assertEqual(done.returncode, 2, done.stdout)
        self.assertIn("~/.rsna/ratic_link", done.stdout)
        self.link_file(0o644)
        done = self.gate_at_home("fetch", ratic)
        self.assertEqual(done.returncode, 2, done.stdout)
        self.assertIn("mode 644", done.stdout)
        self.assertEqual(self.submitted(), [])
        self.link_file(0o600)
        done = self.gate_at_home("fetch", ratic)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertNotIn("secretpart", done.stdout + done.stderr)
        jobs = self.line_of("platform-fetch.sbatch")
        self.assertEqual(len(jobs), 1)
        self.assertIn(f"ID={ratic}", jobs[0])
        self.assertNotIn("--dependency", jobs[0])
        self.assertEqual(len(self.submitted()), 1)
        self.assertIn(f"dp_{ratic}", self.recorded())
        self.assertNotIn("hf_ct_rate", done.stdout)
        # the same source again while its fetch is live: refused
        self.live(self.recorded()[f"dp_{ratic}"])
        self.assertEqual(self.gate_at_home("fetch", ratic).returncode, 75)
        self.assertEqual(len(self.submitted()), 1)

    def test_a_gated_ct_source_waits_for_a_live_x_ray_fetch(self):
        self.state_line(201, "start", "xr_fetch")
        self.state_line(202, "fetch:vindr_pcxr", "xr_fetch")
        self.state_line(203, "start", "xr_fetch")
        self.live(201, 202)
        self.link_file(0o600)
        done = self.gate_at_home("fetch", "rsna_ratic_abdominal_trauma")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("--dependency=afterany:201,afterany:202 ", self.line_of("platform-fetch.sbatch")[0])

    def test_ct_rate_and_an_open_chain_source_are_never_a_fetch_word(self):
        for name in ("hf_ct_rate", "aws_stoic2021"):
            self.assertEqual(self.gate_at_home("fetch", name).returncode, 64, name)
        self.assertEqual(self.submitted(), [])

    def test_the_full_nlst_is_a_fetch_word_on_the_owners_yes(self):
        done = self.gate_at_home("fetch", "idc_nlst")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(len(self.line_of("platform-fetch.sbatch")), 1)
        self.assertEqual(self.recorded().get("dp_idc_nlst") is not None, True, self.recorded())

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
        self.assertIn(f"RUNS={self.runs} WEIGHTS={self.models}/resnet18-f37072fd.pth", line)
        self.assertIn("catalog: catalog-000002-0123456789ab.sqlite qualifies for the run (grid/v1-version.sh); no job", done.stdout)

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
        # each build's split check passed, so each wrote its marker for today's freeze and rule
        for version in (1, 2):
            marker = (self.data / "_catalog" / "checked" / f"catalog-00000{version}-0123456789ab.sqlite").read_text(encoding="utf-8")
            persons = hashlib.sha256((self.repo / "data" / "splits" / "test-persons.json").read_bytes()).hexdigest()
            self.assertIn(f"test-persons {persons}\n", marker)
            self.assertIn("rule ", marker)

    def test_a_catalog_build_never_lists_a_shard_still_being_staged(self):
        for folder in ("a", ".ingest-a-x1y2"):
            manifest = self.data / "carmlspine" / "shards" / folder / "MANIFEST.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text("{}\n", encoding="utf-8")
        pydrv = self.fake / "pydrv"
        pydrv.write_text("""#!/bin/bash
echo "$*" >> "$FAKE/pydrv.log"
[ "$2" = build ] && echo '{"file": "catalog-000001-0123456789ab.sqlite", "new": true, "version": 1}'
exit 0
""", encoding="utf-8")
        pydrv.chmod(0o755)
        job = self.run_catalog_job(pydrv)
        out = job.communicate(timeout=120)[0]
        self.assertEqual(job.returncode, 0, out)
        build = (self.fake / "pydrv.log").read_text(encoding="utf-8").splitlines()[0]
        self.assertIn("/shards/a/MANIFEST.json", build)
        self.assertNotIn(".ingest-", build)

    def test_a_failed_split_check_writes_no_marker(self):
        manifest = self.data / "carmlspine" / "shards" / "a" / "MANIFEST.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text("{}\n", encoding="utf-8")
        pydrv = self.fake / "pydrv"
        pydrv.write_text("""#!/bin/bash
if [ "$2" = build ]; then echo '{"file": "catalog-000001-0123456789ab.sqlite", "new": true, "version": 1}'; exit 0; fi
echo "the split is not disjoint; no training step reads this version"; exit 1
""", encoding="utf-8")
        pydrv.chmod(0o755)
        job = self.run_catalog_job(pydrv)
        out = job.communicate(timeout=120)[0]
        self.assertEqual(job.returncode, 1, out)
        self.assertIn("split-check of version 1 FAILED", out)
        self.assertFalse((self.data / "_catalog" / "checked" / "catalog-000001-0123456789ab.sqlite").exists())

    def driver(self):
        env = dict(os.environ, SCHWINGNET=str(self.repo), DATA_ROOT=str(self.data), RUNS=str(self.runs), FAKE=str(self.fake),
                   WEIGHTS=str(self.models / "resnet18-f37072fd.pth"), SLURM_JOB_ID="777")
        env.pop("STORE", None)
        return subprocess.run(["bash", str(self.repo / "grid" / "v1-driver.sbatch")], cwd=self.repo / "grid", env=env,
                              capture_output=True, text=True, timeout=60)

    def fake_box(self):
        """box.sh as a fake: it logs what it was asked, fails a split check while $FAKE/split_fails is
        there, and says where the hold was when it was asked."""
        (self.repo / "grid" / "box.sh").write_text(
            '#!/bin/bash\necho "$* hold=$(cat "$SCHWINGNET/grid/logs/HOLD" 2>/dev/null)" >> "$FAKE/box.log"\n'
            'if [[ "$*" == *split-check* ]] && [ -f "$FAKE/split_fails" ]; then exit 1; fi\n'
            'echo \'{"run_dir": "/nowhere"}\'\n', encoding="utf-8")

    def boxed(self):
        log = self.fake / "box.log"
        return log.read_text(encoding="utf-8").splitlines() if log.exists() else []

    def test_the_run_takes_the_newest_version_that_qualifies_and_checks_its_split_first(self):
        self.weights_ready()
        self.carmlspine_shards()
        self.catalog_ready(version=2)
        self.catalog_ready(version=3, carmlspine_test=False)
        self.fake_box()
        done = self.driver()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        boxed = self.boxed()
        check = [i for i, line in enumerate(boxed) if "tools/catalog.py split-check" in line]
        flow = [i for i, line in enumerate(boxed) if "flow.py" in line]
        self.assertTrue(check and flow and check[0] < flow[0], boxed)
        self.assertIn(f"split-check {self.data}/_catalog --version 2 hold=777 ", boxed[check[0]])
        self.assertIn(f"--catalog {self.data}/_catalog/versions/catalog-000002-0123456789ab.sqlite ", boxed[flow[0]])
        self.assertIn("CURRENT names catalog-000003-0123456789ab.sqlite; the run takes catalog-000002-0123456789ab.sqlite", done.stdout)
        # the split check fails on the chosen file: the run says so and never starts the flow
        (self.fake / "box.log").unlink()
        (self.fake / "split_fails").write_text("1", encoding="utf-8")
        done = self.driver()
        self.assertEqual(done.returncode, 1)
        self.assertIn("FAILED: the split check of version 2 failed; no run reads it", done.stdout)
        self.assertFalse([line for line in self.boxed() if "flow.py" in line])
        # no version holds the test part: the run says so and starts nothing
        (self.fake / "split_fails").unlink()
        (self.data / "_catalog" / "VERSIONS.jsonl").write_text("", encoding="utf-8")
        (self.fake / "box.log").unlink()
        done = self.driver()
        self.assertEqual(done.returncode, 1)
        self.assertIn("no catalog version to run on: no catalog version holds both of the C-ArmLSpine parts", done.stdout)
        self.assertEqual(self.boxed(), [])
        self.assertFalse((self.repo / "grid" / "logs" / "HOLD").exists())

    def test_the_chooser_wants_both_parts_every_head_shard_and_a_current_split_check(self):
        self.carmlspine_shards()
        self.assertEqual(self.chosen()[0], 1)
        # only the test part: not chosen
        store = self.data / "_catalog"
        self.catalog_ready(version=1)
        log = store / "VERSIONS.jsonl"
        log.write_text(log.read_text(encoding="utf-8").replace(',"carmlspine|train":50', ""), encoding="utf-8")
        self.assertEqual(self.chosen(), (1, "no catalog version holds both of the C-ArmLSpine parts"))
        # both parts and every shard, checked against today's freeze: chosen
        self.catalog_ready(version=2)
        self.assertEqual(self.chosen(), (0, "catalog-000002-0123456789ab.sqlite"))
        # a newer version checked against another freeze is passed over for the older one that holds
        self.catalog_ready(version=3)
        self.mark("catalog-000003-0123456789ab.sqlite", persons="0" * 64)
        self.assertEqual(self.chosen(), (0, "catalog-000002-0123456789ab.sqlite"))
        # with no marker at all, the same
        (store / "checked" / "catalog-000003-0123456789ab.sqlite").unlink()
        self.assertEqual(self.chosen(), (0, "catalog-000002-0123456789ab.sqlite"))
        # a new head shard that supersedes the test shard: no version holds it, and the reason is the newest one's
        self.shard("2026-10-22-0a0b0c0d0e0f", "test", supersedes=self.SHARDS[1])
        code, said = self.chosen()
        self.assertEqual(code, 1)
        self.assertIn("catalog-000003-0123456789ab.sqlite) lacks a C-ArmLSpine shard now on the volume", said)
        self.catalog_ready(version=4, shards=(self.SHARDS[0], "2026-10-22-0a0b0c0d0e0f"))
        self.assertEqual(self.chosen(), (0, "catalog-000004-0123456789ab.sqlite"))
        # the file is gone from versions/: not chosen
        (store / "versions" / "catalog-000004-0123456789ab.sqlite").unlink()
        code, said = self.chosen()
        self.assertEqual(code, 1)
        self.assertIn("names catalog-000004-0123456789ab.sqlite, which is not under versions/", said)

    def test_v1_builds_a_catalog_when_no_version_holds_the_newest_shards(self):
        self.environments_ready()
        self.weights_ready()
        self.carmlspine_shards()
        self.catalog_ready(version=2, shards=(self.SHARDS[0],))
        done = self.gate("v1")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        catalog = self.recorded()["catalog"]
        self.assertIn(f"--dependency=afterok:{catalog} ", self.line_of("v1-driver.sbatch")[0])

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

    def test_no_job_header_places_a_job_and_every_submission_names_a_class(self):
        # Slurm refused the version 1 run for a GPU partition with no QoS (issue #74), so where a job
        # runs is hpcworker's job submit's, from the site profile (issue #77): a header holds only
        # the wall time, the CPUs and the memory, and each submission names cpu, batch or gpu
        for script in sorted(GRID.glob("*.sbatch")):
            header = [line for line in script.read_text(encoding="utf-8").splitlines() if line.startswith("#SBATCH")]
            self.assertEqual(sorted(line.split("=")[0] for line in header),
                             ["#SBATCH --cpus-per-task", "#SBATCH --mem", "#SBATCH --time"], script.name)
        for path in [*GRID.glob("*.sh"), ROOT / "tools" / "flow.py"]:
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r'"\$SBATCH"|\bsbatch --|--qos[= ]|--gres', path.name)
        self.assertEqual(self.gate("start").returncode, 0)
        lines = self.submitted()
        self.assertTrue(lines)
        for line in lines:
            self.assertRegex(line, r"^--class (cpu|batch|gpu) --name [a-z0-9_]+ ", line)
        v1 = self.line_of("v1-driver.sbatch")[0]
        self.assertTrue(v1.startswith("--class gpu --name v1_driver "), v1)
        self.assertIn(" --no-requeue v1-driver.sbatch", v1)

    def test_a_dependency_reaches_job_submit_as_after_options(self):
        script = f'REPO={self.repo}; . {GRID / "hpcw.sh"}; hpcw_after "$1" && printf "%s\\n" ${{HPCW_AFTER[@]+"${{HPCW_AFTER[@]}}"}}'
        done = subprocess.run(["bash", "-c", script, "-", "afterok:101,afterany:102:103"], capture_output=True, text=True)
        self.assertEqual(done.stdout.split(), ["--after", "101:ok", "--after", "102:any", "--after", "103:any"])
        # anything job submit cannot say is refused, so no job is queued without its wait
        for refused in ("singleton", "afternotok:5", "afterok:12_3"):
            done = subprocess.run(["bash", "-c", script, "-", refused], capture_output=True, text=True)
            self.assertEqual((done.returncode, done.stdout), (1, ""), refused)
            self.assertIn("nothing was queued", done.stderr)

    def test_an_old_hpcworker_or_the_old_dry_run_queues_nothing(self):
        self.environments_ready()
        done = subprocess.run(["bash", str(self.repo / "grid" / "gate.sh"), "start"], capture_output=True, text=True, timeout=60,
                              env={**self.gate_env(), "HPCW_FRAMEWORK": "25"})
        self.assertEqual(done.returncode, 2, done.stdout)
        self.assertIn("job submit needs 27 or later", done.stdout)
        done = subprocess.run(["bash", str(self.repo / "grid" / "gate.sh"), "start"], capture_output=True, text=True, timeout=60,
                              env={**self.gate_env(), "SBATCH": "echo"})
        self.assertIn("SBATCH is no longer read", done.stdout)
        self.assertEqual(self.submitted(), [])

    def test_without_hpcworker_no_word_runs(self):
        env = dict(os.environ, PATH=f"{self.fake}:/usr/bin:/bin", FAKE=str(self.fake), SCHWINGNET=str(self.repo),
                   HPCWORKER=str(self.tmp / "no-such-hpcworker"))
        done = subprocess.run(["bash", str(self.repo / "grid" / "gate.sh"), "start"], env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 2, done.stdout)
        self.assertIn("HPCWORKER names", done.stdout)
        self.assertEqual(self.submitted(), [])

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
        self.assertTrue(lines and all(f"RUN={finished} " in line for line in lines), lines)
        status = self.gate("status")
        self.assertIn("has not finished", status.stdout)

    def live(self, *jobs):
        (self.fake / "queue").write_text("".join(f"{job}\n" for job in jobs), encoding="utf-8")

    def state_line(self, job, word, what):
        state = self.repo / "grid" / "logs" / "GATE_JOBS.txt"
        state.parent.mkdir(parents=True, exist_ok=True)
        with state.open("a", encoding="utf-8") as out:
            out.write(f"{job} {word} {what} 2026-10-21T20:00:00Z\n")

    def test_cancel_takes_one_job_and_the_live_jobs_its_word_queued_and_nothing_else(self):
        self.state_line(900, "fetch:vindr_pcxr", "xr_fetch")
        self.state_line(901, "fetch:vindr_pcxr", "xr_bank")
        self.state_line(902, "fetch:vindr_pcxr", "xr_catalog")
        self.state_line(800, "fetch:vindr_pcxr", "xr_fetch")
        self.state_line(950, "fetch:aariz", "xr_fetch")
        self.state_line(960, "start", "dp_zenodo_x")
        self.live(900, 901, 902, 950, 960, 99999)
        done = self.gate("cancel", "900")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertEqual(sorted((self.fake / "scancel.log").read_text(encoding="utf-8").split()), ["900", "901", "902"])
        self.assertIn("cancelled (fetch:vindr_pcxr): 900 901 902", done.stdout)

    def test_cancel_refuses_a_job_not_the_gates_and_leaves_an_ended_one(self):
        self.state_line(900, "fetch:vindr_pcxr", "xr_fetch")
        self.live(99999)
        done = self.gate("cancel", "99999")
        self.assertEqual(done.returncode, 64, done.stdout)
        self.assertIn("not one of the gate's", done.stdout)
        done = self.gate("cancel", "900")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("no longer queued or running", done.stdout)
        self.assertFalse((self.fake / "scancel.log").exists())
        for words in (("cancel",), ("cancel", "9a"), ("cancel", "1", "2"), ("cancel", "1234567890123")):
            self.assertEqual(self.gate(*words).returncode, 64, words)
        self.assertFalse((self.fake / "scancel.log").exists())

    def test_a_failed_squeue_refuses_every_word_that_submits_or_cancels(self):
        self.environments_ready()
        self.weights_ready()
        (self.fake / "squeue_fails").write_text("", encoding="utf-8")
        for words in (("start",), ("leaks",), ("v1",), ("latency",), ("fetch", "aariz"), ("stop",), ("cancel", "101")):
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
        # a credentialed set goes in, its catalog job after every catalog still live, with the
        # size the start chain's list stated left for that chain (grid/size-rule.sh)
        sizes = (self.repo / "grid" / "logs" / "XRAY_SIZES.txt").read_text(encoding="utf-8").split()
        self.assertEqual(sizes[0], started["xr_fetch"])
        done = self.gate("fetch", "vindr_pcxr")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn(f"{int(sizes[1]) // 10**9} GB of it owed to 1 running fetch", done.stdout)
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

    def test_status_tallies_the_space_each_set_takes_largest_first(self):
        # CephFS's attributes, faked per folder: the volume's quota, use and file count, each set's
        # recursive size; a folder the attribute is missing on reads unknown
        (self.fake / "getfattr").write_text("""#!/bin/bash
folder=${!#}
case "$3:$folder" in
  ceph.quota.max_bytes:/rs/rs_grp_oschome) echo -n 21990232555520 ;;
  ceph.dir.rbytes:/rs/rs_grp_oschome) echo -n 13146000000000 ;;
  ceph.dir.rfiles:/rs/rs_grp_oschome) echo -n 7008826 ;;
  *:/rs/rs_grp_oschome) exit 1 ;;
  */big) echo -n 2500000000000 ;;
  */small) echo -n 1500000000 ;;
  */unread) exit 1 ;;
  */nul) printf '1500000000\\0999' ;;
  */long) echo -n 165744388008563119603013828275240916436124852417 ;;
  *) echo -n 2600000000000 ;;
esac
""", encoding="utf-8")
        (self.fake / "getfattr").chmod(0o755)
        for name in ("small", "big", "unread", "nul", "long"):
            (self.data / name).mkdir()
        done = self.gate("status")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        out = done.stdout
        self.assertIn("## space on the lab volume", out)
        # the room under the quota as the size rule reads it, in wsuquota's layout (#160); never
        # df's figure, which on CephFS is the whole pool's
        readout = out[out.index("  Lab Volume Disk Usage"):].splitlines()[:8]
        self.assertEqual(readout, [
            "  Lab Volume Disk Usage (CephFS quota; 1 gb = 10^9 bytes)",
            "  Used  = 59.78%  13146.00gb",
            "  Free  = 40.22%  8844.23gb",
            "  Total =         21990.23gb",
            "  File Count =    7008826",
            "  [" + "#" * 57 + "-" * 39 + "]",
            "  Owed  =         0.00gb still to land for 0 running fetches",
            "  Room  =         8844.23gb for a new fetch, which lands whole or not at all",
        ])
        self.assertNotIn("900000", out)
        self.assertIn("  data: 2600 GB in all", out)
        tally = [line.split() for line in out.splitlines() if line.startswith("    ")]
        self.assertEqual(tally[0], ["2500", "big"])
        # a value ends at its first NUL, and one that is no count of at most 18 digits reads
        # unknown, never as a figure bash's arithmetic wrapped (#160)
        self.assertEqual(sorted(tally[1:5]), [["2", "nul"], ["2", "small"], ["?", "long"], ["?", "unread"]])
        self.assertIn("shared datasets: not there", out)
        self.assertNotIn(str(self.tmp), out)
        self.assertLess(out.index("## space"), out.index("## the gate's newest jobs") if "## the gate's" in out else len(out))

    def test_status_shows_what_a_live_fetch_has_landed_with_no_walk(self):
        # CephFS's recursive attributes, faked by name: a fetch sent 40 s ago still writing
        now = int(time.time())
        (self.fake / "getfattr").write_text(f"""#!/bin/bash
case "$3" in
  ceph.dir.rfiles) echo -n 1234 ;;
  ceph.dir.rbytes) echo -n 4560000000 ;;
  ceph.dir.rctime) echo -n {now - 40}.123456789 ;;
  *) echo -n 1500000000 ;;
esac
""", encoding="utf-8")
        (self.fake / "getfattr").chmod(0o755)
        (self.data / "vindr_pcxr" / "raw").mkdir(parents=True)
        self.state_line(900, "fetch:vindr_pcxr", "xr_fetch")
        self.state_line(901, "fetch:padchest", "xr_fetch")
        self.state_line(902, "start", "xr_fetch")
        self.live(900, 901, 902)
        done = self.gate("status")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        # The age is counted when status reaches the fetch, after the space block, so a slow runner
        # may see a few seconds more than the 40 the fake attribute was written with.
        landed = (r"\n  fetch of vindr_pcxr \(job 900\): 1234 files, 4560 MB, "
                  r"last write 4[0-9]s ago\n")
        self.assertRegex(done.stdout, landed)
        self.assertIn("  fetch of padchest (job 901): nothing landed yet", done.stdout)
        self.assertNotIn("job 902", done.stdout)
        self.assertNotIn(str(self.data), done.stdout)
        # a fetch that ended says nothing here, and a folder with no attributes says so
        self.live(900)
        (self.fake / "getfattr").write_text("#!/bin/bash\nexit 1\n", encoding="utf-8")
        done = self.gate("status")
        self.assertIn("fetch of vindr_pcxr (job 900): the raw folder is there; its size is not readable here", done.stdout)
        self.assertNotIn("job 901", done.stdout)
        # A size of 48 digits, as the owner's shell printed the volume's, is no count and is not read;
        # one with more after a NUL is read up to the NUL.
        for rbytes, said in (("165744388008563119603013828275240916436124852417",
                              "the raw folder is there; its size is not readable here"),
                             ("4560000000\\0999", "1234 files, 4560 MB, last write")):
            (self.fake / "getfattr").write_text(f"""#!/bin/bash
case "$3" in
  ceph.dir.rfiles) printf '1234' ;;
  ceph.dir.rbytes) printf '{rbytes}' ;;
  ceph.dir.rctime) printf '{now}.5' ;;
  *) printf '1500000000' ;;
esac
""", encoding="utf-8")
            done = self.gate("status")
            self.assertIn(f"  fetch of vindr_pcxr (job 900): {said}", done.stdout)

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
                # where hpcworker's job log finds it (tests/fakes/hpcworker): <id>.out, <id>_<task>.out
                (self.fake / "joblogs").mkdir(exist_ok=True)
                (self.fake / "joblogs" / f"{job}.out").write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
        (self.fake / "sacct.out").write_text("".join(f"{row}\n" for row in sacct), encoding="utf-8")

    def test_status_shows_the_end_of_an_open_jobs_log_masked_and_cut(self):
        lines = [f"pixi line {i}" for i in range(30)] + ["x" * 300, "token=abcdef0123456789 and https://u:p@host/x"]
        self.failed((300, "start", "setup", "sn_setup", "FAILED", "00:00:10", lines))
        done = self.gate("status")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("## 300 (setup) ended FAILED after 00:00:10, exit 1:0\n", done.stdout)
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
                 "IndexError: index 1965031 is out of bounds",
                 "TypeError: unhashable type: 'Doe_John'",
                 "TypeError: can only concatenate 'str' (not 'int') to 'str'",
                 "HTTP request sent, awaiting response... 403 Forbidden",
                 "SN_CARMLSPINE_RC=1"]
        self.failed((301, "start", "carmlspine", "sn_carmlspine", "FAILED", "00:00:48", lines))
        done = self.gate("status")
        self.assertEqual(done.returncode, 0, done.stdout)
        for kept in ('  File "/home/go2432/SchwingNet/tools/ingest.py", line 153, in item_of',
                     "AttributeError: 'str' object has no attribute 'get'", "KeyError: <message withheld>",
                     "IndexError: <message withheld>", "TypeError: <message withheld>",
                     "TypeError: can only concatenate 'str' (not 'int') to 'str'",
                     "HTTP request sent, awaiting response... 403 Forbidden", "SN_CARMLSPINE_RC=1",
                     "XR_FETCH start 2026-10-21 21:30:00 on n1 job 301\n"):
            self.assertIn(kept, done.stdout)
        for value in ("ABC123", "DOE", "Doe_John", "9f86d081", "1.2.840", "abc123", "case042", "credentialed"):
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
        self.assertIn("## 402 (v1_driver) ended CANCELLED after 00:00:00", done.stdout)
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
        self.assertIn("## 700_0 (latency_sweep) ended TIMEOUT after 01:00:00, exit 1:0\n", done.stdout)
        self.assertIn("    SN_LATENCY_RC=1", done.stdout)
        self.assertNotIn("700_2 (", done.stdout)

    def test_status_cuts_the_paths_of_the_stage_reports_and_withholds_a_quoting_reason(self):
        logs = self.repo / "grid" / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        (logs / "02-bank-ingest-STAGE-REPORT.md").write_text(
            "- vindr_spinexr: bank refused: person vindr_spinexr:9f86d081884c7d659a2feaa0c55ad015 holds more than one part (first 1.2.3.4.5.6)\n"
            f"- FAILED: no bank at {self.data}/realxray/carmlspine/case134_19650312\n"
            f"- run directory: {self.runs}/20261022-abc, weights {self.models}/resnet18-f37072fd.pth, raw /home/go2432/x/case39.png\n"
            "- split-check of version 3 FAILED: the split is not disjoint; no training step reads this version\n"
            "| accuracy | all levels | 21/21 | 1.000 |\nChance is 1/27.\n"
            "- vindr: bank refused: Doe_John/IM0007.dcm: not in the person table\n"
            "- carmlspine: refused: the same bytes as case039_0002.png, under another person\n",
            encoding="utf-8")
        done = self.gate("status")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("bank refused: <reason withheld: it can quote a value; the whole report stays on the grid>", done.stdout)
        self.assertIn("- FAILED: no bank at <data root: realxray>\n", done.stdout)
        self.assertIn("- run directory: <runs>, weights <models>, raw <path>\n", done.stdout)
        self.assertIn("FAILED: the split is not disjoint; no training step reads this version", done.stdout)
        # a count is no path: the run's results table keeps 21/21 and chance 1/27
        self.assertIn("| accuracy | all levels | 21/21 | 1.000 |", done.stdout)
        self.assertIn("Chance is 1/27.", done.stdout)
        self.assertEqual(done.stdout.count("<reason withheld"), 3, done.stdout)
        for value in ("9f86d081", "1.2.3.4", "case134", "19650312", "20261022", "case39", "go2432", "Doe_John", "case039"):
            self.assertNotIn(value, done.stdout)

    def test_the_box_runs_apptainer_quietly(self):
        # apptainer's INFO lines would land in the output a stage reads as JSON (the C-ArmLSpine
        # ingest's summary failed on one on 2026-10-22)
        sandbox = self.tmp / "sandbox"
        (sandbox / "bin").mkdir(parents=True)
        (sandbox / "bin" / "bash").write_text("", encoding="utf-8")
        (sandbox / "bin" / "bash").chmod(0o755)
        (self.fake / "apptainer").write_text('#!/bin/bash\necho "$*" > "$FAKE/apptainer.log"\n', encoding="utf-8")
        (self.fake / "apptainer").chmod(0o755)
        env = dict(os.environ, PATH=f"{self.fake}:{os.environ['PATH']}", FAKE=str(self.fake), SCHWINGNET_SANDBOX=str(sandbox),
                   LAB_VOLUME=str(self.tmp))
        for name in ("APPTAINER_CONTAINER", "SINGULARITY_CONTAINER", "SCHWINGNET_NATIVE", "CUDA_VISIBLE_DEVICES", "SLURM_JOB_GPUS"):
            env.pop(name, None)
        done = subprocess.run(["bash", str(GRID / "box.sh"), "python", "-V"], env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue((self.fake / "apptainer.log").read_text(encoding="utf-8").startswith("--quiet exec "))

    def test_status_is_bounded_whatever_the_reports_hold(self):
        # 50 reports of 12 lines each would print 650 lines: the bound, not the inputs, keeps it to 400
        logs = self.repo / "grid" / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        for n in range(50):
            (logs / f"{n:02d}-STAGE-REPORT.md").write_text("".join(f"- line {i} {'z' * 150}\n" for i in range(12)), encoding="utf-8")
        self.failed((300, "start", "setup", "sn_setup", "FAILED", "00:00:10", ["y" * 100000]))
        done = self.gate("status")
        self.assertEqual(done.returncode, 0, done.stdout)
        lines = done.stdout.splitlines()
        # the word's first line, the 400 the bound lets through and the exit line
        self.assertEqual(len(lines), 402, lines[-3:])
        self.assertEqual(lines[-1], "schwingnet status: exit 0")
        self.assertLess(len(done.stdout), 65536 + 100)

    def test_status_shows_slurms_errors_by_phrase_and_masks_a_date_after_an_underscore(self):
        lines = ["slurmstepd: error: *** JOB 40697734 ON n7 CANCELLED AT 2026-10-22T01:00:00 DUE TO TIME LIMIT ***",
                 "srun: error: n7: task 0: Exited with exit code 1",
                 "TypeError: cannot read /rs/data/case134_19650312.dcm",
                 "SN_V1_RC=1"]
        self.failed((310, "v1", "v1_driver", "sn_v1", "TIMEOUT", "24:00:00", lines))
        done = self.gate("status")
        self.assertIn("slurmstepd: error: [DUE TO TIME LIMIT]", done.stdout)
        self.assertIn("srun: error: <message withheld>", done.stdout)
        self.assertIn("TypeError: <message withheld>", done.stdout)
        for value in ("40697734", "n7", "case134"):
            self.assertNotIn(value, done.stdout)
        masked = subprocess.run(["sed", "-r", "-f", str(GRID / "redact.sed")], input="scan_19650312.dcm 20201231_19990101\n",
                                capture_output=True, text=True).stdout
        self.assertEqual(masked, "scan_<date withheld>.dcm <date withheld>_<date withheld>\n")

    def test_status_keeps_a_sources_id_and_masks_a_hugging_face_token(self):
        # the size rule's lines open with the source's id, hf_fluoroseg, which is no token; a token
        # is hf_ and 34 letters, built here so no file holds one
        token = "hf_" + "Ab" * 17
        lines = ("hf_fluoroseg: refused for space; it needs 2650 gb at 2026-10-23T12:00:00Z\n"
                 "hf_abdomenatlas2_0_mini: admitted already; job 9 restarted\n"
                 f"token {token} and HF_TOKEN={token}\n")
        masked = subprocess.run(["sed", "-r", "-f", str(GRID / "redact.sed")], input=lines,
                                capture_output=True, text=True).stdout.splitlines()
        self.assertEqual(masked, ["hf_fluoroseg: refused for space; it needs 2650 gb at 2026-10-23T12:00:00Z",
                                  "hf_abdomenatlas2_0_mini: admitted already; job 9 restarted",
                                  "token <withheld> and HF_TOKEN=<withheld>"])

    def test_status_finds_the_log_a_job_queued_before_hpcworker_wrote_in_grid_logs(self):
        # a job sbatch queued before issue #77 is in no ledger of hpcworker's; its log is where its
        # script's own --output put it, %x_%A_%a giving a job that is no array Slurm's NO_VAL
        self.failed((320, "start", "probe", "sn_probe", "FAILED", "00:00:05", None))
        logs = self.repo / "grid" / "logs"
        (logs / "sn_probe_320_4294967294.out").write_text("PROBE start 2026-10-22 01:00:00 on n1 job 320\ncase134 frames 12\nSN_PROBE_RC=1\n",
                                                          encoding="utf-8")
        done = self.gate("status")
        self.assertIn("## 320 (probe) ended FAILED", done.stdout)
        self.assertIn("    SN_PROBE_RC=1", done.stdout)
        # the probe prints the sweeps' file names, so its log is shown as shapes too
        self.assertNotIn("case134", done.stdout)
        self.assertIn("(1 of its last 400 lines withheld", done.stdout)

    PROBE = (
        "SN_LATENCY probe start 2026-10-21 17:31:00 on hao1 job 9 task  commit 5ecce95",
        "raw case134: 302 files under /rs/data/carmlspine/unpacked/C-ArmLSpine",
        "  suffixes: {'(none)': 302}",
        "     302  /rs/data/carmlspine/unpacked/C-ArmLSpine/case134/ori",
        "       4  /rs/data/carmlspine/unpacked/C-ArmLSpine/Jane_Doe_scan",
        "  commonest sizes in bytes: [(2098432, 301), (1024, 1)]",
        "bank case134: 301 PNG frames under /rs/data/realxray/carmlspine_sweep/images",
        "  first: case134_sw000.png 1024x1024, 8-bit, colour type 0 | last: case134_sw300.png",
        "  meta keys: ['angle', 'boxes', 'mode'] | view: None | boxes: 5 | box keys: ['level', 'xyxy'] | levels: ['L1', 'L2']",
        "  frames with meta: 301",
        "Traceback (most recent call last): Jane Doe",
    )

    def test_status_prints_the_newest_latency_probe_by_its_shapes(self):
        logs = self.repo / "grid" / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        older = logs / "sn_probe_7_4294967294.out"
        older.write_text("raw case39: 1 files under /x\n", encoding="utf-8")
        os.utime(older, (1, 1))
        (logs / "sn_probe_9_4294967294.out").write_text("\n".join(self.PROBE) + "\n", encoding="utf-8")
        done = self.gate("status")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("## the latency probe: sn_probe_9_4294967294.out", done.stdout)
        for kept in ("  raw case134: 302 files", "  302 files in case134/ori", "  bank case134: 301 PNG frames",
                     "  first frame: 1024x1024, 8-bit, colour type 0", "levels: ['L1', 'L2']", "  frames with meta: 301",
                     "suffixes: {'(none)': 302}", "(2 of its lines not shown"):
            self.assertIn(kept, done.stdout)
        for gone in ("case39", "Jane", "/rs/", "sw000", "C-ArmLSpine"):
            self.assertNotIn(gone, done.stdout)

    def test_status_reads_a_recorded_probe_from_hpcworkers_log(self):
        # since issue #77 the probe logs to hpcworker's folder under its recorded id, not grid/logs
        logs = self.repo / "grid" / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        (logs / "sn_probe_7_4294967294.out").write_text("raw case39: 1 files under /x\n", encoding="utf-8")
        (logs / "GATE_JOBS.txt").write_text("7 start probe 2026-10-21T00:00:00Z\n12 start probe 2026-10-22T00:00:00Z\n", encoding="utf-8")
        (self.fake / "joblogs").mkdir(exist_ok=True)
        (self.fake / "joblogs" / "12.out").write_text("\n".join(self.PROBE) + "\n", encoding="utf-8")
        done = self.gate("status")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("## the latency probe: job 12", done.stdout)
        self.assertIn("  bank case134: 301 PNG frames", done.stdout)
        for gone in ("case39", "Jane", "/rs/", "sw000"):
            self.assertNotIn(gone, done.stdout)

    def test_samples_submits_the_index_records_its_jobs_and_waits_for_them(self):
        (self.repo / "tools" / "sample_index.py").write_text("", encoding="utf-8")
        self.assertEqual(self.gate("samples").returncode, 75)
        self.environments_ready()
        done = self.gate("samples")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        jobs = self.recorded()
        plan, scan, merge = jobs["samples_plan"], jobs["samples_scan"], jobs["samples_merge"]
        lines = self.submitted()
        self.assertEqual(len(lines), 3, lines)
        self.assertIn(f"--dependency=afterok:{plan} ", lines[1])
        self.assertIn(f"--dependency=afterany:{scan} ", lines[2])
        # while one of its jobs is live, samples is refused and submits nothing
        self.live(merge)
        done = self.gate("samples")
        self.assertEqual(done.returncode, 75, done.stdout)
        self.assertIn("sample index is still queued or running", done.stdout)
        self.assertEqual(len(self.submitted()), 3)
        self.assertEqual(self.gate("samples", "all").returncode, 64)

    def test_status_shows_the_sample_manifest_whole(self):
        logs = self.repo / "grid" / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        rows = "".join(f"| source_{i} | {i * 10} | {i} |\n" for i in range(40))
        (logs / "SAMPLES-STAGE-REPORT.md").write_text("# The sample index\n\n" + rows, encoding="utf-8")
        (logs / "03-catalog-STAGE-REPORT.md").write_text("".join(f"- line {i}\n" for i in range(20)), encoding="utf-8")
        done = self.gate("status")
        self.assertIn("  # The sample index\n", done.stdout)
        self.assertIn("| source_0 | 0 | 0 |", done.stdout)
        self.assertIn("| source_39 | 390 | 39 |", done.stdout)
        # another report still shows only its end
        self.assertNotIn("- line 7\n", done.stdout)
        self.assertIn("- line 19\n", done.stdout)

    def test_status_prints_the_newest_runs_latency_parity_and_sweep(self):
        import json
        run = self.runs / "e4f7054848f5"
        for folder in ("onnx", "latency", "evaluate", "sweep/case134"):
            (run / folder).mkdir(parents=True)
        def write(path, record):
            (run / path).write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
        write("onnx/parity-onnxruntime-cuda.json", {"runtime": "onnxruntime", "device": "cuda", "crops": 64, "persons": 4,
                                                    "witness_frames": 6, "max_abs_probability_difference": 2.5e-06,
                                                    "labels_equal": True, "passed": True, "onnx_sha256": "ab" * 32})
        arm = {"arm": "onnxruntime-cuda-1t", "device": "NVIDIA H200", "frames": 300, "ms_per_frame_median": 3.21,
               "ms_per_frame_p95": 4.56, "ms_per_frame_p99": 5.0, "budget_ms": 97.0, "within_budget": True,
               "frame": {"p50": 3.21}, "per_stage": {"model_ms": {"p50": 2.0}}}
        write("latency/onnxruntime-cuda-1t.json", arm)
        write("evaluate/latency.json", dict(arm, arms=["onnxruntime-cuda-1t"]))
        write("sweep/case134/summary.json", {"name": "case134", "frames": 301, "runtime": "onnxruntime", "device": "NVIDIA H200",
                                             "box_source": "truth", "latency_ms": {"p50": 6.04, "p95": 7.91}, "within_budget": True,
                                             "accuracy": {"all frames": {"correct": 290, "total": 301, "ci95": [0.9, 1.0]},
                                                          "Jane/Doe": {"correct": 1, "total": 1}},
                                             "video": str(run / "sweep" / "case134" / "sweep.mp4")})
        done = self.gate("status")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        for kept in ("## latency of the newest run, e4f7054848f5",
                     "  parity onnxruntime on cuda: 64 crops of 4 persons (6 witness frames), max difference 2.5e-06, labels equal yes, passed yes",
                     "  arm onnxruntime-cuda-1t on NVIDIA H200: 300 frames, p50 3.2 ms, p95 4.6 ms, p99 5.0 ms, within the 97.0 ms budget yes",
                     "  headline: onnxruntime-cuda-1t on NVIDIA H200, p50 3.2 ms, p95 4.6 ms",
                     "  sweep case134: 301 frames, onnxruntime on NVIDIA H200, boxes truth, p50 6.0 ms, p95 7.9 ms, within budget yes, video mp4",
                     "    accuracy all frames: 290/301", "    accuracy <withheld>: 1/1"):
            self.assertIn(kept, done.stdout)
        section = done.stdout.split("## latency of the newest run", 1)[1].split("## newest run:", 1)[0]
        for gone in (str(self.runs), "Jane", "abab"):
            self.assertNotIn(gone, section)

    def test_status_shows_the_sample_manifest_whole_before_the_jobs(self):
        # the manifest once came after the jobs, where status's 400 lines cut it, and its widest row,
        # the bank root a dozen X-ray sources share, was cut at 200 characters; an unmapped root is
        # named by its folder under the data root, not withheld as a person key
        sources = ",".join(f"source_{n:02d}_of_the_bank" for n in range(12))
        logs = self.repo / "grid" / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        (logs / "SAMPLES-STAGE-REPORT.md").write_text(
            "# Sample manifest\n\n| sources | files |\n| --- | ---: |\n"
            f"| {sources} | 20269 |\n| unmapped:xr_bank | 368455 |\n\n2 groups, 388724 files, 1.0 GB.\n", encoding="utf-8")
        self.assertEqual(self.gate("start").returncode, 0)
        done = self.gate("status")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertLess(done.stdout.index("## SAMPLES-STAGE-REPORT.md"), done.stdout.index("the gate's newest jobs"))
        self.assertIn("source_11_of_the_bank | 20269 |", done.stdout)
        self.assertIn("| unmapped xr_bank | 368455 |", done.stdout)
        self.assertIn("2 groups, 388724 files, 1.0 GB.", done.stdout)
        self.assertEqual(done.stdout.count("## SAMPLES-STAGE-REPORT.md"), 1)
        self.assertTrue(all(len(line) <= 202 for line in done.stdout.splitlines()), "a row longer than 200 characters")

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
                    self.assertIn(" DATA_ROOT= PART=", line, f"{given!r}: {line}")

    def test_a_probe_that_was_not_submitted_is_said_and_nothing_stale_is_recorded(self):
        (self.repo / "grid" / "LAST_LATENCY.txt").write_text("probe 999\ngpu /old/run 998\n", encoding="utf-8")
        (self.fake / "refuse").write_text("latency_probe", encoding="utf-8")
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
