"""grid/gate.sh (issue #53), the one script the Beethoven grid gate calls with a fixed word, and the
jobs it submits: every script parses; a word outside the list, an argument where none belongs and an
id that is not a plain name are refused before anything is submitted; start submits the whole graph
with its Slurm dependencies, leaving out the setup and weights jobs when their results are there;
start refuses while one of the gate's jobs is live; stop cancels the gate's jobs and nothing else;
a credentialed fetch needs ~/.netrc at mode 600 with a PhysioNet line; v1 and latency find their
catalog; sweep runs a plan of the block smoke test after what it needs, and bank one recipe with
its catalog build (issue #252). Every job goes through hpcworker's job submit with a class (issue
#77): the fake hpcworker under tests/fakes/ records what would be queued, and fake squeue, sacct,
scancel and df on PATH answer for Slurm; nothing reaches a scheduler. Standard library only, so the
required check runs it."""

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRID = ROOT / "grid"
FAKE_HPCWORKER = ROOT / "tests" / "fakes" / "hpcworker"
NEW_SCRIPTS = ("gate.sh", "hpcw.sh", "box.sh", "bin/pixi", "bin/train-cpu-python", "00-setup.sbatch", "00-weights.sbatch",
               "00-carmlspine.sbatch", "v1-driver.sbatch", "experiment-driver.sbatch", "run-xray-chain.sh",
               "run-platform-fetch.sh", "sweep-driver.sbatch", "v1-version.sh")
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
    # stat as grid/size-rule.sh asks it: -f -c %T, before df, names a mount that is no CephFS, kernel
    # or FUSE, so the stand-in df may answer for it, and every other question, the devices that show
    # the data root inside the volume on its mount among them, goes to stat itself; named so it never
    # stands in for stat on PATH
    "fstype": """#!/bin/bash
case " $* " in *" -f "*) echo "ext2/ext3" ;; *) exec stat "$@" ;; esac
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
        self.smoke = self.tmp / "smoke"
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
                   NETRC=str(self.netrc), USER="go2432", HPCWORKER=str(FAKE_HPCWORKER), SMOKE=str(self.smoke),
                   HPCW_LOG=str(self.fake / "sbatch.log"), HPCW_REFUSE=str(self.fake / "refuse"), HPCW_LOGS=str(self.fake / "joblogs"), SHARED_DATA=str(self.tmp / "shared"))
        for name in ("GETFATTR", "VOLUME", "HPCW_DRY", "HPCW_FIRST", "HPCW_FRAMEWORK", "SBATCH", "SQUEUE", "SACCT", "SCANCEL", "DF", "DEPEND", "PYDRV"):
            env.pop(name, None)
        env["STAT"] = str(self.fake / "fstype")
        # The lab volume is the test's own folder, which holds the data root as /rs/rs_grp_oschome
        # holds go2432/data: the size rule reads no room where the data root lies outside the volume (#180).
        env["VOLUME"] = str(self.tmp)
        # the size rule reads these fakes only where a test says so, and waits no minute here (#180)
        env.update(SIZE_RULE_STAND_INS="yes", SIZE_RULE_SETTLE="0")
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

    def catalog_ready(self, version=3, carmlspine_test=True, shards=SHARDS, checked=True, also=()):
        """A version in the store as tools/catalog.py writes one: its file, its line in VERSIONS.jsonl
        (compact, as pydantic writes it) and CURRENT naming it, and, when checked, the split-check
        marker grid/03-catalog.sbatch writes for today's freeze and rule. Each source of also adds
        its train part."""
        store = self.data / "_catalog"
        versions = store / "versions"
        versions.mkdir(parents=True, exist_ok=True)
        name = f"catalog-{version:06d}-0123456789ab.sqlite"
        (versions / name).write_bytes(b"")
        parts = '"carmlspine|test":59,"carmlspine|train":50' if carmlspine_test else '"vindr_pcxr|train":7'
        parts += "".join(f',"{source}|train":11' for source in also)
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

    def chosen(self, *source):
        """What grid/v1-version.sh chooses now, with the source given as its fourth argument: its exit
        code and what it said."""
        done = subprocess.run(["bash", str(self.repo / "grid" / "v1-version.sh"), str(self.data / "_catalog"), str(self.data),
                               str(self.repo), *source], capture_output=True, text=True, timeout=60)
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

    REQUEST = "recipe: none\nepochs: 12\nseed: 3\nhours: 2.5\nblock: architecture=resnet34\nblock: optimiser=adamw\n"

    def experiment(self, *words, requests):
        """The gate with EXPERIMENTS_DIR standing in for the branch experiments, as a test must."""
        env = self.gate_env()
        env["EXPERIMENTS_DIR"] = str(requests)
        return subprocess.run(["bash", str(self.repo / "grid" / "gate.sh"), *words], env=env, capture_output=True, text=True, timeout=120)

    def test_experiment_runs_the_recorded_request_as_one_gpu_job_once_the_inputs_are_there(self):
        requests = self.tmp / "requests"
        requests.mkdir()
        (requests / "250.request").write_text(self.REQUEST, encoding="utf-8")
        for words in (("experiment",), ("experiment", "x"), ("experiment", "01"), ("experiment", "0"), ("experiment", "1", "2"), ("experiment", "1" * 10)):
            done = self.experiment(*words, requests=requests)
            self.assertEqual(done.returncode, 64, f"{words}: {done.stdout}{done.stderr}")
        done = self.experiment("experiment", "251", requests=requests)
        self.assertEqual(done.returncode, 75, done.stdout + done.stderr)
        self.assertIn("no 251.request on the branch experiments", done.stdout)
        # the version 1 inputs come first: the word submits nothing until v1 made them
        done = self.experiment("experiment", "250", requests=requests)
        self.assertEqual(done.returncode, 75, done.stdout + done.stderr)
        self.assertIn("'start' makes them first", done.stdout)
        self.environments_ready()
        done = self.experiment("experiment", "250", requests=requests)
        self.assertEqual(done.returncode, 75, done.stdout + done.stderr)
        self.assertIn("'v1' makes them first", done.stdout)
        self.weights_ready()
        self.carmlspine_shards()
        self.catalog_ready(version=2)
        self.assertEqual(self.submitted(), [])
        done = self.experiment("experiment", "250", requests=requests)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(len(self.submitted()), 1, self.submitted())
        line = self.line_of("experiment-driver.sbatch")[0]
        self.assertIn("ISSUE=250", line)
        self.assertIn(f"REQUEST={self.repo}/grid/logs/experiment-250.request", line)
        self.assertIn(f"RUNS={self.runs} WEIGHTS={self.models}/resnet18-f37072fd.pth", line)
        self.assertIn("--no-requeue", line)
        self.assertIn("gpu", line)
        # 2.5 hours of training fit the driver's own 24 hours, which stay the floor
        self.assertIn("--time 24:00:00", line)
        self.assertIn("catalog: catalog-000002-0123456789ab.sqlite qualifies for the run", done.stdout)
        self.assertIn("request: recipe: none epochs: 12 seed: 3 hours: 2.5 block: architecture=resnet34 block: optimiser=adamw", done.stdout)
        self.assertEqual((self.repo / "grid" / "logs" / "experiment-250.request").read_text(encoding="utf-8"), self.REQUEST)
        job = self.recorded()["experiment_250"]
        (self.fake / "queue").write_text(job + "\n", encoding="utf-8")
        done = self.experiment("experiment", "250", requests=requests)
        self.assertEqual(done.returncode, 75, done.stdout + done.stderr)
        self.assertIn(f"already queued or running (job {job})", done.stdout)
        self.assertEqual(len(self.submitted()), 1)
        # a longer training asks for its hours, the evaluation's quarter of them and an hour more
        (requests / "252.request").write_text(self.REQUEST.replace("hours: 2.5", "hours: 40"), encoding="utf-8")
        done = self.experiment("experiment", "252", requests=requests)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("--time 51:00:00", self.line_of("experiment-driver.sbatch")[1])
        self.assertIn("wall time: 51:00:00 for 40 hours of training", done.stdout)

    def test_experiment_refuses_a_request_with_a_strange_line_before_anything_is_submitted(self):
        self.environments_ready()
        self.weights_ready()
        self.carmlspine_shards()
        self.catalog_ready(version=2)
        requests = self.tmp / "requests"
        requests.mkdir()
        strange = {
            "260": "recipe: none\nepochs: 12\nseed: 3\nhours: 2\nblock: architecture=resnet34; rm -rf /\n",
            "261": "recipe: none\nrecipe: none\nepochs: 12\nseed: 3\nhours: 2\n",
            "262": "recipe: none\nepochs: 12\nseed: 3\n",
            "263": "recipe: none\nepochs: 0x\nseed: 3\nhours: 2\n",
            "264": "recipe: none\nepochs: 12\nseed: 3\nhours: 2\nsomething else\n",
            "265": "recipe: none\nepochs: 12\nseed: 3\nhours: 2\nblock: " + "a" * 120 + "=b\n",
            "266": "".join(f"block: architecture=resnet34\n" for _ in range(41)) + "recipe: none\nepochs: 1\nseed: 1\nhours: 1\n",
            "267": "recipe: none\nepochs: 12\nseed: 3\nhours: 2.5.1\n",
            "268": "recipe: none\nepochs: 12\nseed: 3\nhours: 4h\n",
        }
        for number, body in strange.items():
            (requests / f"{number}.request").write_text(body, encoding="utf-8")
            done = self.experiment("experiment", number, requests=requests)
            self.assertEqual(done.returncode, 64, f"{number}: {done.stdout}{done.stderr}")
            self.assertIn("refusing:", done.stdout)
            self.assertFalse((self.repo / "grid" / "logs" / f"experiment-{number}.request").exists(), number)
        self.assertEqual(self.submitted(), [])

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
        # Inside a Slurm shell the stage would hand itself to the launcher and never run the body
        # this test is about, as tests/test_flows.py's base_env says too.
        for name in ("STORE", "SLURM_JOB_ID", "SCHWINGNET_FLOW_STEP"):
            env.pop(name, None)
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

    def test_a_fetch_is_refused_while_a_bank_of_the_same_set_is_live(self):
        # the chain's bank half would bank the folder the bank word's job is writing, and the
        # fetch's admission would replace the bank's in the set's meta/SIZE
        self.environments_ready()
        self.state_line(960, "bank:aariz", "bank")
        self.live(960)
        done = self.gate("fetch", "aariz")
        self.assertEqual(done.returncode, 75, done.stdout)
        self.assertIn("a bank of aariz is still queued or running (job 960)", done.stdout)
        self.assertEqual(self.submitted(), [])
        # a bank of another set stands in the way of nothing
        self.netrc.write_text("machine physionet.org login x password y\n", encoding="utf-8")
        self.netrc.chmod(0o600)
        done = self.gate("fetch", "vindr_pcxr")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(len(self.line_of("01-fetch.sbatch")), 1)

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
  ceph.quota.max_bytes:"$VOLUME") echo -n 21990232555520 ;;
  ceph.dir.rbytes:"$VOLUME") echo -n 13146000000000 ;;
  ceph.dir.rfiles:"$VOLUME") echo -n 7008826 ;;
  ceph.quota.*|*:"$VOLUME") echo "$folder: $3: No such attribute" >&2; exit 1 ;;
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
        # a value is read whole, so one with a NUL in it, which a NUL could have cut short, reads
        # unknown (#180), as one that is no count of at most 18 digits does, never as a figure bash's
        # arithmetic wrapped (#160)
        self.assertEqual(sorted(tally[1:5]), [["2", "small"], ["?", "long"], ["?", "nul"], ["?", "unread"]])
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

    def test_explore_looks_once_then_prints_the_report(self):
        (self.repo / "tools" / "explore.py").write_text("# the tool\n", encoding="utf-8")
        shutil.copy(GRID / "fetch-xray.json", self.repo / "grid" / "fetch-xray.json")
        # an id of no list, and one with no raw folder yet, are refused and queue nothing
        self.assertEqual(self.gate("explore", "no_such_set").returncode, 64)
        self.assertEqual(self.gate("explore", "kaggle_scoliosis_yolov5").returncode, 2)
        self.assertEqual(self.gate("explore", "a", "b").returncode, 64)
        self.assertEqual(self.gate("explore", "Bad-Id").returncode, 64)
        for name in ("kaggle_scoliosis_yolov5", "kaggle_fracture_multiregion"):
            (self.data / name / "raw").mkdir(parents=True)
        self.assertEqual(self.gate("explore", "kaggle_scoliosis_yolov5").returncode, 75)
        self.environments_ready()
        done = self.gate("explore", "kaggle_scoliosis_yolov5")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        lines = self.submitted()
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("--class batch --name explore", lines[0])
        self.assertIn("explore.sbatch", lines[0])
        self.assertIn(f"EXPLORE_RAW={self.data}/kaggle_scoliosis_yolov5/raw", lines[0])
        # the scoliosis export is compared with both AASCE copies; the fracture set with nothing
        self.assertIn(f"AASCE-ke30-mirror={self.data}/thoracic_xr/mirror_zlinzju_ke30_u7_AASCE2019|"
                      f"AASCE-BoostNet={self.data}/aasce2019_boostnet/raw/aasce", lines[0])
        job = self.recorded()["explore"]
        # while its job is live a second send is refused and queues nothing
        self.live(job)
        done = self.gate("explore", "kaggle_scoliosis_yolov5")
        self.assertEqual(done.returncode, 75, done.stdout)
        self.assertEqual(len(self.submitted()), 1)
        # once it has ended, the report it wrote is printed and nothing is queued
        (self.fake / "queue").write_text("", encoding="utf-8")
        report = self.repo / "grid" / "logs" / "EXPLORE-kaggle_scoliosis_yolov5.md"
        report.write_text("# explore kaggle_scoliosis_yolov5\n## what the set holds\n  files: 3\n", encoding="utf-8")
        done = self.gate("explore", "kaggle_scoliosis_yolov5")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("  files: 3", done.stdout)
        self.assertEqual(len(self.submitted()), 1)
        # a change to the tool makes the next send look again
        (self.repo / "tools" / "explore.py").write_text("# the tool, changed\n", encoding="utf-8")
        done = self.gate("explore", "kaggle_scoliosis_yolov5")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertEqual(len(self.submitted()), 2)
        done = self.gate("explore", "kaggle_fracture_multiregion")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("EXPLORE_AGAINST= ", self.submitted()[2] + " ")

    def test_nodequota_reads_a_node_once_then_prints_what_it_read(self):
        # an argument is refused, and nothing is queued before the environments are made
        self.assertEqual(self.gate("nodequota", "x").returncode, 64)
        self.assertEqual(self.gate("nodequota").returncode, 75)
        self.environments_ready()
        done = self.gate("nodequota")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        lines = self.submitted()
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("--class batch --name nodequota", lines[0])
        self.assertIn("nodequota.sbatch", lines[0])
        job = self.recorded()["nodequota"]
        # while its job is live a second send is refused and queues nothing
        self.live(job)
        self.assertEqual(self.gate("nodequota").returncode, 75)
        self.assertEqual(len(self.submitted()), 1)
        # once it has ended, its report is printed once and nothing is queued
        (self.fake / "queue").write_text("", encoding="utf-8")
        report = self.repo / "grid" / "logs" / "NODEQUOTA.md"
        report.write_text("# The lab volume as compute node n1 reads it\n  2 up: ceph.quota.max_bytes reads 1\n",
                          encoding="utf-8")
        done = self.gate("nodequota")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("2 up: ceph.quota.max_bytes reads 1", done.stdout)
        self.assertEqual(len(self.submitted()), 1)
        self.assertFalse(report.exists())
        # the send after that reads a node again
        self.assertEqual(self.gate("nodequota").returncode, 0)
        self.assertEqual(len(self.submitted()), 2)

    def test_folders_reads_the_index_once_then_prints_one_page_a_send(self):
        # an argument is refused, and nothing is queued before there is a whole sample index
        self.assertEqual(self.gate("folders", "x").returncode, 64)
        self.assertEqual(self.gate("folders").returncode, 2)
        run = self.data / "_samples" / "20261022-000000-abcd"
        run.mkdir(parents=True)
        (run / "samples.sqlite").write_bytes(b"")
        (self.data / "_samples" / "CURRENT").write_text(run.name + "\n", encoding="utf-8")
        self.assertEqual(self.gate("folders").returncode, 75)
        # environments made from an older pixi.lock are enough, since the report is standard library alone
        self.environments_ready()
        (self.repo / ".pixi" / "SETUP.sha256").write_text("stale\n", encoding="utf-8")
        done = self.gate("folders")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        lines = self.submitted()
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("--class batch --name folders", lines[0])
        self.assertIn(f"FOLDERS_DB={run / 'samples.sqlite'}", lines[0])
        self.assertIn("folders.sbatch", lines[0])
        # while its job is live a second send is refused and queues nothing
        self.live(self.recorded()["folders"])
        self.assertEqual(self.gate("folders").returncode, 75)
        # once it has ended, each send prints the next page, in number order, and clears it
        (self.fake / "queue").write_text("", encoding="utf-8")
        logs = self.repo / "grid" / "logs"
        for number in (1, 2, 10):
            (logs / f"FOLDERS-{number}.md").write_text(f"## page {number}\n", encoding="utf-8")
        printed = [self.gate("folders").stdout for _ in range(3)]
        self.assertIn("page 1", printed[0])
        self.assertIn("2 more to print", printed[0])
        self.assertIn("page 2", printed[1])
        self.assertIn("page 10", printed[2])
        self.assertEqual(len(self.submitted()), 1)
        # the send after the last page looks again
        self.assertEqual(self.gate("folders").returncode, 0)
        self.assertEqual(len(self.submitted()), 2)

    def test_bench_queues_one_gpu_job_per_model_and_then_keeps_printing_its_report(self):
        # no name, two names and a name of no benchmark are refused before anything is read
        self.assertEqual(self.gate("bench").returncode, 64)
        self.assertEqual(self.gate("bench", "a", "b").returncode, 64)
        self.assertEqual(self.gate("bench", "fluorosam").returncode, 64)
        # nothing is queued before the fetch has landed the weights, and the refusal names the fetch
        refused = self.gate("bench", "flexray_carmlspine")
        self.assertEqual(refused.returncode, 2, refused.stdout)
        self.assertIn("fetch hf_flexray_weights first", refused.stdout)
        refused = self.gate("bench", "xvr_deepfluoro")
        self.assertEqual(refused.returncode, 2, refused.stdout)
        self.assertIn("fetch hf_xvr_models first", refused.stdout)
        bundle = self.data / "hf_flexray_weights" / "raw"
        bundle.mkdir(parents=True)
        (bundle / "ensemble.json").write_text("{}\n", encoding="utf-8")
        refused = self.gate("bench", "flexray_carmlspine")
        self.assertEqual(refused.returncode, 2, refused.stdout)
        self.assertIn("C-ArmLSpine's bank", refused.stdout)
        (self.data / "realxray" / "carmlspine" / "meta").mkdir(parents=True)
        self.environments_ready()
        done = self.gate("bench", "flexray_carmlspine")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        lines = self.submitted()
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("--class gpu --name bench_flexray_carmlspine", lines[0])
        self.assertIn("BENCH=flexray_carmlspine", lines[0])
        self.assertIn("--no-requeue", lines[0])
        self.assertIn("bench.sbatch", lines[0])
        job = self.recorded()["bench_flexray_carmlspine"]
        # while its job is live a second send is refused and queues nothing
        self.live(job)
        self.assertEqual(self.gate("bench", "flexray_carmlspine").returncode, 75)
        # once it has ended, its report is printed on every send and nothing more is queued,
        # so the owner's count of one job each holds
        (self.fake / "queue").write_text("", encoding="utf-8")
        report = self.repo / "grid" / "logs" / "BENCH-flexray_carmlspine.md"
        report.write_text("# bench flexray_carmlspine\n- exit 0\n", encoding="utf-8")
        for _ in range(2):
            done = self.gate("bench", "flexray_carmlspine")
            self.assertEqual(done.returncode, 0, done.stdout)
            self.assertIn("- exit 0", done.stdout)
        self.assertEqual(len(self.submitted()), 1)
        self.assertTrue(report.exists())

    def test_a_failed_benchmark_is_queued_once_more_only_after_the_checkout_moves(self):
        # a benchmark that failed scored nothing: once a fix has moved the checkout past the commit
        # its report names, one more send keeps the report under its job's number and queues it
        # again (#312); on the same commit, or once it succeeded, a send queues nothing
        bundle = self.data / "hf_flexray_weights" / "raw"
        bundle.mkdir(parents=True)
        (bundle / "ensemble.json").write_text("{}\n", encoding="utf-8")
        h5 = self.data / "deepfluoro_h5" / "raw"
        h5.mkdir(parents=True)
        with (h5 / "ipcai_2020_full_res_data.h5").open("wb") as handle:
            handle.truncate(2 * 1024 * 1024)
        self.environments_ready()
        logs = self.repo / "grid" / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        report = logs / "BENCH-flexray_deepfluoro.md"
        head = "# bench flexray_deepfluoro: job 4242 on voh3, commit {}, 2026-10-25 13:20:52 UTC\n"
        report.write_text(head.format("unknown") + "- exit 1 at 2026-10-25 13:21:01 UTC\n", encoding="utf-8")
        done = self.gate("bench", "flexray_deepfluoro")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("- exit 1", done.stdout)
        self.assertEqual(self.submitted(), [])
        report.write_text(head.format("fc027a6") + "- exit 1 at 2026-10-25 13:21:01 UTC\n", encoding="utf-8")
        done = self.gate("bench", "flexray_deepfluoro")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("queueing the benchmark again", done.stdout)
        self.assertFalse(report.exists())
        self.assertIn("- exit 1", (logs / "BENCH-flexray_deepfluoro-4242.md").read_text(encoding="utf-8"))
        lines = self.submitted()
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("BENCH=flexray_deepfluoro", lines[0])
        (self.fake / "queue").write_text("", encoding="utf-8")
        report.write_text(head.format("fc027a6") + "- exit 0 at 2026-10-25 14:00:00 UTC\n", encoding="utf-8")
        self.assertEqual(self.gate("bench", "flexray_deepfluoro").returncode, 0)
        self.assertEqual(len(self.submitted()), 1)

    def test_anomaly_queues_one_cpu_job_for_select_and_then_keeps_printing_its_report(self):
        # no stage, two stages and a stage not built yet are refused before anything is read
        self.assertEqual(self.gate("anomaly").returncode, 64)
        self.assertEqual(self.gate("anomaly", "a", "b").returncode, 64)
        refused = self.gate("anomaly", "tune")
        self.assertEqual(refused.returncode, 64, refused.stdout)
        self.assertIn("not built yet", refused.stdout)
        self.environments_ready()
        done = self.gate("anomaly", "select")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        lines = self.submitted()
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("--class batch --name anomaly_select", lines[0])
        self.assertIn("STAGE=select", lines[0])
        self.assertIn("--no-requeue", lines[0])
        self.assertIn("anomaly.sbatch", lines[0])
        job = self.recorded()["anomaly_select"]
        self.live(job)
        self.assertEqual(self.gate("anomaly", "select").returncode, 75)
        (self.fake / "queue").write_text("", encoding="utf-8")
        report = self.repo / "grid" / "logs" / "ANOMALY-select.md"
        report.write_text("# anomaly select\n- exit 0\n", encoding="utf-8")
        for _ in range(2):
            done = self.gate("anomaly", "select")
            self.assertEqual(done.returncode, 0, done.stdout)
            self.assertIn("- exit 0", done.stdout)
        self.assertEqual(len(self.submitted()), 1)

    def test_select_is_refused_without_the_frozen_holdout(self):
        (self.repo / "data" / "splits" / "anomaly-holdout.json").unlink()
        self.environments_ready()
        refused = self.gate("anomaly", "select")
        self.assertEqual(refused.returncode, 2, refused.stdout)
        self.assertIn("data/splits/anomaly-holdout.json", refused.stdout)
        self.assertEqual(self.submitted(), [])

    def anomaly_job(self, ssn):
        env = dict(os.environ, SCHWINGNET=str(self.repo), DATA_ROOT=str(self.data), LAB_VOLUME=str(self.tmp), SSN=str(ssn),
                   STAGE="select", SLURM_JOB_ID="779", PYDRV=sys.executable)
        return subprocess.run(["bash", str(self.repo / "grid" / "anomaly.sbatch")], cwd=self.repo / "grid", env=env,
                              capture_output=True, text=True, timeout=60)

    def test_the_select_stage_scores_selects_and_reports_counts_only(self):
        # anomaly.sbatch runs tools/anomaly_route.py from the checkout over the grid's records and
        # writes a report of counts and digests, holding the checkout while it runs
        self.git_repo()
        shutil.copy(ROOT / "tools" / "anomaly_route.py", self.repo / "tools" / "anomaly_route.py")
        subprocess.run(["git", "-C", str(self.repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@t", "-c", "gc.auto=0",
                        "-c", "maintenance.auto=false", "commit", "-q", "-m", "tool"], check=True)
        registry = self.tmp / "ssn" / "SchwingNet" / "results" / "transitional_registry"
        (registry / "verse").mkdir(parents=True)
        columns = "case,patient_key,read_structure,read_subtype,mask_has_L6,a_nL,a_nT,b_nL,b_nL_contact,b_nT,labeller_a,labeller_b,junction_tl_in_fov,junction_ls_in_fov,review"
        rows = [f"verse{500 + n},verse:verse{500 + n},7/12/6/5,L6,True,6,,6,6,,,,True,True," for n in range(4)]
        rows += [f"verse{100 + n},verse:verse{100 + n},7/12/5/5,normal,False,5,,5,5,,,,True,True," for n in range(8)]
        (registry / "verse" / "screened.csv").write_text("\n".join([columns] + rows) + "\n", encoding="utf-8")
        (registry / "registry.csv").write_text(
            "patient_key,subtype,truth_tier,winning_source,winning_case,frames_role,junction_tl_in_fov,junction_ls_in_fov\n"
            "verse:verse900,L6,read,verse,verse900,CT-only,True,True\n"
            + "".join(f"verse:verse{200 + n},none,read,verse,verse{200 + n},CT-only,True,True\n" for n in range(5)), encoding="utf-8")
        done = self.anomaly_job(self.tmp / "ssn")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        report = (self.repo / "grid" / "logs" / "ANOMALY-select.md").read_text(encoding="utf-8")
        self.assertIn("# anomaly select: job 779", report.splitlines()[0])
        self.assertIn("NOTE: the grid's VerSe screen", report)
        self.assertIn("| L6: sensitivity | 4 of 4", report)
        self.assertIn("no held-out person in", report)
        self.assertIn("- exit 0 at ", report)
        self.assertFalse((self.repo / "grid" / "logs" / "HOLD").exists())
        self.assertTrue((self.tmp / "go2432" / "anomaly" / "select" / "selection.csv").exists())

    def bench_job(self, name):
        env = dict(os.environ, SCHWINGNET=str(self.repo), DATA_ROOT=str(self.data), LAB_VOLUME=str(self.tmp), FAKE=str(self.fake),
                   BENCH=name, SLURM_JOB_ID="778")
        return subprocess.run(["bash", str(self.repo / "grid" / "bench.sbatch")], cwd=self.repo / "grid", env=env,
                              capture_output=True, text=True, timeout=60)

    def test_a_benchmark_holds_the_checkout_while_it_runs_and_fails_when_it_moved(self):
        # bench.sbatch runs its steps from the checkout for hours and its report names the commit it
        # began on, so it holds grid/logs/HOLD as the drivers do, and a checkout that moved anyway
        # fails the benchmark rather than leave a report naming code some steps did not run
        self.git_repo()
        commit = subprocess.run(["git", "-C", str(self.repo), "rev-parse", "HEAD"], check=True, capture_output=True,
                                text=True).stdout.strip()
        bundle = self.data / "hf_flexray_weights" / "raw"
        bundle.mkdir(parents=True)
        (bundle / "ensemble.json").write_text("{}\n", encoding="utf-8")
        (self.repo / "grid" / "box.sh").write_text(
            '#!/bin/bash\necho "$* hold=$(cat "$SCHWINGNET/grid/logs/HOLD" 2>/dev/null)" >> "$FAKE/box.log"\n'
            '[[ "$*" == *bench_public.py* ]] || exit 0\n'
            'if [ -f "$FAKE/move" ]; then\n'
            '  git -C "$SCHWINGNET" -c user.name=t -c user.email=t@t -c gc.auto=0 -c maintenance.auto=false commit -q --allow-empty -m moved\n'
            'fi\necho "scored"\n', encoding="utf-8")
        hold = self.repo / "grid" / "logs" / "HOLD"
        done = self.bench_job("flexray_carmlspine")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        boxed = self.boxed()
        self.assertTrue(boxed and all(line.endswith(f" hold=778 {commit}") for line in boxed), boxed)
        self.assertTrue([line for line in boxed if "tools/bench_public.py flexray-carmlspine" in line], boxed)
        self.assertFalse(hold.exists())
        report = self.repo / "grid" / "logs" / "BENCH-flexray_carmlspine.md"
        self.assertIn(f"commit {commit[:7]}", report.read_text(encoding="utf-8").splitlines()[0])
        self.assertIn("- exit 0 at ", report.read_text(encoding="utf-8"))
        (self.fake / "move").write_text("1", encoding="utf-8")
        done = self.bench_job("flexray_carmlspine")
        self.assertEqual(done.returncode, 3, done.stdout)
        self.assertIn("SN_BENCH_RC=3", done.stdout)
        self.assertIn(f"- FAILED: the checkout moved from {commit[:7]} to ", report.read_text(encoding="utf-8"))
        self.assertIn("- exit 3 at ", report.read_text(encoding="utf-8"))
        self.assertFalse(hold.exists())

    def test_a_benchmark_and_the_runs_that_hold_the_checkout_each_wait_for_the_others(self):
        self.environments_ready()
        self.weights_ready()
        self.carmlspine_shards()
        self.catalog_ready(version=2)
        bundle = self.data / "hf_flexray_weights" / "raw"
        bundle.mkdir(parents=True)
        (bundle / "ensemble.json").write_text("{}\n", encoding="utf-8")
        (self.data / "realxray" / "carmlspine" / "meta").mkdir(parents=True, exist_ok=True)
        self.state_line(900, "sweep:synthetic", "sweep")
        self.live(900)
        done = self.gate("bench", "flexray_carmlspine")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("--dependency=afterany:900 ", self.line_of("bench.sbatch")[0])
        self.assertIn("the checkout: after the live runs that hold it (afterany:900)", done.stdout)
        job = self.recorded()["bench_flexray_carmlspine"]
        self.live(job)
        done = self.gate("v1")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn(f"--dependency=afterany:{job} ", self.line_of("v1-driver.sbatch")[0])

    def test_bench_with_stale_environments_queues_one_setup_job_that_every_bench_waits_on(self):
        bundle = self.data / "hf_flexray_weights" / "raw"
        bundle.mkdir(parents=True)
        (bundle / "ensemble.json").write_text("{}\n", encoding="utf-8")
        (self.data / "realxray" / "carmlspine" / "meta").mkdir(parents=True)
        h5 = self.data / "deepfluoro_h5" / "raw"
        h5.mkdir(parents=True)
        with (h5 / "ipcai_2020_full_res_data.h5").open("wb") as out:
            out.truncate(2 * 1024 * 1024)
        done = self.gate("bench", "flexray_carmlspine")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        lines = self.submitted()
        self.assertEqual(len(lines), 2, lines)
        self.assertIn("--name setup", lines[0])
        setup = self.recorded()["setup"]
        self.assertIn("--name bench_flexray_carmlspine", lines[1])
        self.assertIn(f"afterok:{setup}", lines[1])
        # a second bench sent while that setup job is live waits on it and queues no second setup
        self.live(setup)
        done = self.gate("bench", "flexray_deepfluoro")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        lines = self.submitted()
        self.assertEqual(len(lines), 3, lines)
        self.assertIn("--name bench_flexray_deepfluoro", lines[2])
        self.assertIn(f"afterok:{setup}", lines[2])

    def test_dropzip_deletes_once_then_prints_what_it_did(self):
        shutil.copy(GRID / "fetch-xray.json", self.repo / "grid" / "fetch-xray.json")
        # an id of no list, one with no raw folder yet, and a malformed send are refused and queue nothing
        self.assertEqual(self.gate("dropzip", "no_such_set").returncode, 64)
        self.assertEqual(self.gate("dropzip", "kaggle_scoliosis_yolov5").returncode, 2)
        self.assertEqual(self.gate("dropzip", "a", "b").returncode, 64)
        self.assertEqual(self.gate("dropzip", "Bad-Id").returncode, 64)
        (self.data / "kaggle_scoliosis_yolov5" / "raw").mkdir(parents=True)
        self.assertEqual(self.gate("dropzip", "kaggle_scoliosis_yolov5").returncode, 75)
        self.environments_ready()
        done = self.gate("dropzip", "kaggle_scoliosis_yolov5")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        lines = self.submitted()
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("--class batch --name dropzip", lines[0])
        self.assertIn("dropzip.sbatch", lines[0])
        self.assertIn(f"DROPZIP_RAW={self.data}/kaggle_scoliosis_yolov5/raw", lines[0])
        job = self.recorded()["dropzip"]
        # while its job is live a second send is refused and queues nothing
        self.live(job)
        self.assertEqual(self.gate("dropzip", "kaggle_scoliosis_yolov5").returncode, 75)
        self.assertEqual(len(self.submitted()), 1)
        # once it has ended, its report is printed once and nothing is queued
        (self.fake / "queue").write_text("", encoding="utf-8")
        report = self.repo / "grid" / "logs" / "DROPZIP-kaggle_scoliosis_yolov5.md"
        report.write_text("# dropzip kaggle_scoliosis_yolov5\n  zips: 1\n  freed: 0.5 GB\n", encoding="utf-8")
        done = self.gate("dropzip", "kaggle_scoliosis_yolov5")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("  freed: 0.5 GB", done.stdout)
        self.assertEqual(len(self.submitted()), 1)
        self.assertFalse(report.exists())
        # the send after that looks again
        self.assertEqual(self.gate("dropzip", "kaggle_scoliosis_yolov5").returncode, 0)
        self.assertEqual(len(self.submitted()), 2)
        # never while a fetch or a look at the set is live, since a zip half unpacked is missing members
        (self.fake / "queue").write_text("", encoding="utf-8")
        self.state_line("4242", "explore:kaggle_scoliosis_yolov5", "explore")
        self.live("4242")
        done = self.gate("dropzip", "kaggle_scoliosis_yolov5")
        self.assertEqual(done.returncode, 75, done.stdout)
        self.assertEqual(len(self.submitted()), 2)

    def test_unpack_queues_once_then_prints_what_it_wrote(self):
        shutil.copy(GRID / "fetch-xray.json", self.repo / "grid" / "fetch-xray.json")
        # an id of no list, one with no raw folder yet, and a malformed send are refused and queue nothing
        self.assertEqual(self.gate("unpack", "no_such_set").returncode, 64)
        self.assertEqual(self.gate("unpack", "kaggle_scoliosis_yolov5").returncode, 2)
        self.assertEqual(self.gate("unpack", "a", "b").returncode, 64)
        (self.data / "kaggle_scoliosis_yolov5" / "raw").mkdir(parents=True)
        self.assertEqual(self.gate("unpack", "kaggle_scoliosis_yolov5").returncode, 75)
        self.environments_ready()
        done = self.gate("unpack", "kaggle_scoliosis_yolov5")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        lines = self.submitted()
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("--class batch --name unpack", lines[0])
        self.assertIn("unpack.sbatch", lines[0])
        self.assertIn(f"UNPACK_RAW={self.data}/kaggle_scoliosis_yolov5/raw", lines[0])
        self.assertIn(f"DATA_ROOT={self.data}", lines[0])
        job = self.recorded()["unpack"]
        # while it is live, a second unpacking and a deletion of the set's zips are refused
        self.live(job)
        self.assertEqual(self.gate("unpack", "kaggle_scoliosis_yolov5").returncode, 75)
        self.assertEqual(self.gate("dropzip", "kaggle_scoliosis_yolov5").returncode, 75)
        self.assertEqual(len(self.submitted()), 1)
        # once it has ended, its report is printed once and nothing is queued
        (self.fake / "queue").write_text("", encoding="utf-8")
        report = self.repo / "grid" / "logs" / "UNPACK-kaggle_scoliosis_yolov5.md"
        report.write_text("# unpack kaggle_scoliosis_yolov5\n  written: 0.5 GB\n", encoding="utf-8")
        done = self.gate("unpack", "kaggle_scoliosis_yolov5")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("  written: 0.5 GB", done.stdout)
        self.assertEqual(len(self.submitted()), 1)
        self.assertFalse(report.exists())
        # never beside a deletion of the set's zips
        self.state_line("4243", "dropzip:kaggle_scoliosis_yolov5", "dropzip")
        self.live("4243")
        self.assertEqual(self.gate("unpack", "kaggle_scoliosis_yolov5").returncode, 75)
        self.assertEqual(len(self.submitted()), 1)

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


    # The block smoke test's words (issue #252): sweep <plan> and bank <id>.

    def plan(self, name, catalog, weights=False):
        """A plan under grid/sweeps/ as tools/block_sweep.py cover writes one: indent 1, sorted keys."""
        import json
        rows = [{"blocks": ["denoise=none"], "init": None, "role": "cover", "size": 64, "slug": "resnet18-64px-0123abcd",
                 "weights": None}]
        if weights:
            rows.append({"blocks": ["normalise=imagenet"], "init": None, "role": "imagenet", "size": 64,
                         "slug": "imagenet-resnet18-64px-89abcdef", "weights": "resnet18"})
        record = {"about": "A plan for the tests.", "catalog": catalog, "epochs": 3, "plan": name, "rows": rows, "seed": 1}
        folder = self.repo / "grid" / "sweeps"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{name}.json").write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        return folder / f"{name}.json"

    def test_sweep_and_bank_each_take_exactly_one_plain_id(self):
        for words in (("sweep",), ("sweep", "a", "b"), ("sweep", "Real"), ("sweep", "../real"), ("bank",),
                      ("bank", "vindr-spinexr"), ("bank", "a" * 41), ("sweep real",)):
            done = self.gate(*words)
            self.assertEqual(done.returncode, 64, f"{words}: {done.stdout}")
        self.assertEqual(self.submitted(), [])

    def test_sweep_refuses_a_plan_that_is_not_under_grid_sweeps(self):
        self.plan("real", "v1")
        done = self.gate("sweep", "no_such_plan")
        self.assertEqual(done.returncode, 64, done.stdout)
        self.assertIn("no_such_plan is not a plan under grid/sweeps/", done.stdout)
        self.assertIn("real", done.stdout)
        self.assertEqual(self.submitted(), [])

    def test_sweep_waits_on_the_setup_the_weights_a_live_catalog_and_every_run_that_holds_the_checkout(self):
        self.plan("real", "v1", weights=True)
        # start's first catalog, which may make a version of C-ArmLSpine alone; a bank's never does
        self.state_line(700, "start", "catalog")
        self.state_line(701, "v1", "v1_driver")
        self.state_line(702, "sweep:synthetic", "sweep")
        self.state_line(703, "start", "xr_catalog")
        self.state_line(704, "experiment:250", "experiment_250")
        self.live(700, 701, 702, 703, 704)
        done = self.gate("sweep", "real")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        lines = self.submitted()
        self.assertEqual([line.split(" | ")[0].split()[-1] for line in lines],
                         ["00-setup.sbatch", "00-weights.sbatch", "sweep-driver.sbatch"], lines)
        jobs = self.recorded()
        sweep = self.line_of("sweep-driver.sbatch")[0]
        self.assertTrue(sweep.startswith("--class gpu --name sweep "), sweep)
        self.assertIn(f"--dependency=afterok:{jobs['setup']},afterok:{jobs['weights']},afterok:700,afterany:701,afterany:702,"
                      "afterany:704 ", sweep)
        self.assertIn("--kill-on-invalid-dep=yes", sweep)
        self.assertIn(" --no-requeue sweep-driver.sbatch", sweep)
        # the X-ray chain's catalog follows a fetch of days and is never waited on
        self.assertNotIn(":703", sweep)
        self.assertIn(f"DATA_ROOT={self.data} ", sweep)
        self.assertIn(f"WEIGHTS={self.models}/resnet18-f37072fd.pth MODELS={self.models} ", sweep)
        self.assertIn(f"PLAN=real SMOKE={self.smoke} ", sweep)
        state = (self.repo / "grid" / "logs" / "GATE_JOBS.txt").read_text(encoding="utf-8")
        self.assertIn(f"{jobs['sweep']} sweep:real sweep ", state)

    def test_sweep_needs_nothing_where_everything_is_there(self):
        self.environments_ready()
        self.weights_ready()
        self.plan("synthetic", "synthetic", weights=True)
        done = self.gate("sweep", "synthetic")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(len(self.submitted()), 1, self.submitted())
        self.assertNotIn("--dependency", self.submitted()[0])
        # a real catalog that qualifies now, and no ImageNet row: no wait and no weights job either
        (self.models / "resnet18-f37072fd.pth").unlink()
        self.plan("real", "v1")
        self.carmlspine_shards()
        self.catalog_ready(version=2)
        done = self.gate("sweep", "real")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("catalog-000002-0123456789ab.sqlite qualifies", done.stdout)
        self.assertEqual(len(self.submitted()), 2, self.submitted())
        self.assertNotIn("--dependency", self.submitted()[1])
        self.assertEqual(self.line_of("00-weights.sbatch"), [])

    def test_sweep_is_refused_while_the_same_plan_is_live_and_another_plan_waits_for_it(self):
        self.environments_ready()
        self.plan("synthetic", "synthetic")
        self.plan("trials", "synthetic")
        self.state_line(800, "sweep:synthetic", "sweep")
        self.live(800)
        done = self.gate("sweep", "synthetic")
        self.assertEqual(done.returncode, 75, done.stdout)
        self.assertIn("already queued or running (job 800)", done.stdout)
        self.assertEqual(self.submitted(), [])
        done = self.gate("sweep", "trials")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("--dependency=afterany:800 ", self.line_of("sweep-driver.sbatch")[0])

    def test_a_real_plan_with_no_catalog_to_come_is_refused_and_queues_nothing(self):
        self.plan("real", "v1")
        self.plan("two_source", "with:vindr_spinexr")
        done = self.gate("sweep", "real")
        self.assertEqual(done.returncode, 75, done.stdout)
        self.assertIn("the v1 word or start makes the catalog first", done.stdout)
        # a version that holds C-ArmLSpine and not the second source
        self.carmlspine_shards()
        self.catalog_ready(version=2)
        done = self.gate("sweep", "two_source")
        self.assertEqual(done.returncode, 75, done.stdout)
        self.assertIn("bank vindr_spinexr first", done.stdout)
        # refused before the setup job the environments would need, so nothing at all is queued
        self.assertEqual(self.submitted(), [])
        self.catalog_ready(version=3, also=("vindr_spinexr",))
        done = self.gate("sweep", "two_source")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("catalog-000003-0123456789ab.sqlite qualifies", done.stdout)
        # a plan whose catalog is none the sweep knows
        self.plan("odd", "elsewhere")
        self.assertEqual(self.gate("sweep", "odd").returncode, 2)

    def test_a_failed_squeue_refuses_sweep_and_bank(self):
        self.plan("synthetic", "synthetic")
        (self.fake / "squeue_fails").write_text("", encoding="utf-8")
        for words in (("sweep", "synthetic"), ("bank", "vindr_spinexr")):
            done = self.gate(*words)
            self.assertEqual(done.returncode, 75, f"{words}: {done.stdout}")
        self.assertEqual(self.submitted(), [])

    def test_v1_waits_on_a_live_sweep_since_both_hold_the_checkout(self):
        self.environments_ready()
        self.weights_ready()
        self.carmlspine_shards()
        self.catalog_ready(version=2)
        self.state_line(900, "sweep:synthetic", "sweep")
        self.live(900)
        done = self.gate("v1")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("--dependency=afterany:900 ", self.line_of("v1-driver.sbatch")[0])

    def test_an_experiment_run_and_the_runs_beside_it_each_wait_for_the_others_that_hold_the_checkout(self):
        # experiment-driver.sbatch writes and clears grid/logs/HOLD as v1-driver and sweep-driver do,
        # so each of the three waits afterany on every other one still live, whichever came first
        self.environments_ready()
        self.weights_ready()
        self.carmlspine_shards()
        self.catalog_ready(version=2)
        self.plan("synthetic", "synthetic")
        requests = self.tmp / "requests"
        requests.mkdir()
        for number in ("250", "251"):
            (requests / f"{number}.request").write_text(self.REQUEST, encoding="utf-8")
        self.state_line(600, "experiment:250", "experiment_250")
        self.live(600)
        done = self.gate("sweep", "synthetic")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("--dependency=afterany:600 ", self.line_of("sweep-driver.sbatch")[0])
        done = self.gate("v1")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("--dependency=afterany:600 ", self.line_of("v1-driver.sbatch")[0])
        # an experiment sent while a sweep, a version 1 run and another experiment are live
        self.state_line(601, "sweep:real", "sweep")
        self.state_line(602, "v1", "v1_driver")
        self.live(600, 601, 602)
        done = self.experiment("experiment", "251", requests=requests)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        line = self.line_of("experiment-driver.sbatch")[0]
        self.assertIn("--dependency=afterany:600,afterany:601,afterany:602 ", line)
        self.assertIn("the checkout: after the live runs that hold it", done.stdout)
        # none live: no wait at all
        self.live()
        done = self.experiment("experiment", "250", requests=requests)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertNotIn("--dependency", self.line_of("experiment-driver.sbatch")[1])

    def ceph_fake(self, raw_bytes=None):
        """CephFS's attributes, faked by folder: the volume's quota, use and file count; a raw folder's
        size from $FAKE/raw_bytes; every other folder the same size; no quota anywhere else."""
        if raw_bytes is not None:
            (self.fake / "raw_bytes").write_text(str(raw_bytes), encoding="utf-8")
        (self.fake / "getfattr").write_text("""#!/bin/bash
folder=${!#}
case "$3:$folder" in
  ceph.quota.max_bytes:"$VOLUME") echo -n 21990232555520 ;;
  ceph.dir.rbytes:"$VOLUME") echo -n 13146000000000 ;;
  ceph.dir.rfiles:"$VOLUME") echo -n 7008826 ;;
  ceph.quota.*|*:"$VOLUME") echo "$folder: $3: No such attribute" >&2; exit 1 ;;
  ceph.dir.rbytes:*/raw) cat "$FAKE/raw_bytes" ;;
  *) echo -n 2600000000000 ;;
esac
""", encoding="utf-8")
        (self.fake / "getfattr").chmod(0o755)

    def gate_with_ceph(self, *words):
        return subprocess.run(["bash", str(self.repo / "grid" / "gate.sh"), *words], env=dict(self.gate_env(), GETFATTR=str(self.fake / "getfattr")),
                              capture_output=True, text=True, timeout=120)

    def test_bank_is_refused_for_an_unknown_id_an_unconfirmed_recipe_a_missing_raw_copy_and_no_room(self):
        self.environments_ready()
        self.assertEqual(self.gate("bank", "no_such_recipe").returncode, 64)
        done = self.gate("bank", "aariz")
        self.assertEqual(done.returncode, 2, done.stdout)
        self.assertIn('still has a field spelled "to confirm"', done.stdout)
        done = self.gate("bank", "vindr_spinexr")
        self.assertEqual(done.returncode, 2, done.stdout)
        self.assertIn("raw copy is not on the volume", done.stdout)
        raw = self.data / "vindr_spinexr" / "raw"
        raw.mkdir(parents=True)
        self.assertEqual(self.gate("bank", "vindr_spinexr").returncode, 2, "an empty raw folder is no raw copy")
        (raw / "a.dicom").write_bytes(b"d")
        # no CephFS attribute on the raw folder: its size is not known, so nothing is queued
        done = self.gate("bank", "vindr_spinexr")
        self.assertEqual(done.returncode, 2, done.stdout)
        self.assertIn("what vindr_spinexr's raw copy holds could not be read", done.stdout)
        # 5000 GB of raw copy: the bank and its shard may take 10000 GB, more than the 8844 GB of room
        self.ceph_fake(raw_bytes=5000 * 10**9)
        done = self.gate_with_ceph("bank", "vindr_spinexr")
        self.assertEqual(done.returncode, 75, done.stdout)
        self.assertIn("raw copy: 5000 GB of dcm, which bank.py windows to an 8-bit PNG; the bank and its shard: 10000 GB held", done.stdout)
        self.assertIn("room: 8844 GB free under its quota after 0 GB owed to 0 running fetches", done.stdout)
        self.assertIn("refusing: the bank and its shard need 10000 GB and the room is 8844 GB", done.stdout)
        self.assertEqual(self.submitted(), [])
        self.assertNotIn(str(raw), done.stdout)

    def test_bank_submits_the_bank_and_a_catalog_build_afterok_on_it_and_waits_its_turn(self):
        raw = self.data / "vindr_spinexr" / "raw"
        raw.mkdir(parents=True)
        (raw / "a.dicom").write_bytes(b"d")
        self.ceph_fake(raw_bytes=100 * 10**9)
        done = self.gate_with_ceph("bank", "vindr_spinexr")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("raw copy: 100 GB of dcm, which bank.py windows to an 8-bit PNG; the bank and its shard: 200 GB held", done.stdout)
        jobs = self.recorded()
        lines = self.submitted()
        self.assertEqual([line.split(" | ")[0].split()[-1] for line in lines],
                         ["00-setup.sbatch", "02-bank-ingest.sbatch", "03-catalog.sbatch"], lines)
        bank, catalog = self.line_of("02-bank-ingest.sbatch")[0], self.line_of("03-catalog.sbatch")[0]
        self.assertTrue(bank.startswith("--class batch --name bank "), bank)
        self.assertIn(f"--dependency=afterok:{jobs['setup']} ", bank)
        self.assertIn(" ONLY=vindr_spinexr", bank)
        self.assertTrue(catalog.startswith("--class batch --name catalog "), catalog)
        self.assertIn(f"--dependency=afterok:{jobs['bank']} ", catalog)
        state = (self.repo / "grid" / "logs" / "GATE_JOBS.txt").read_text(encoding="utf-8")
        self.assertIn(f"{jobs['bank']} bank:vindr_spinexr bank ", state)
        self.assertIn(f"{jobs['catalog']} bank:vindr_spinexr catalog ", state)
        # while its bank or catalog job is live, or the X-ray chain's bank, the word is refused
        count = len(self.submitted())
        for job in (jobs["bank"], jobs["catalog"]):
            self.live(job)
            done = self.gate_with_ceph("bank", "vindr_spinexr")
            self.assertEqual(done.returncode, 75, done.stdout)
        self.state_line(950, "start", "xr_bank")
        self.live(950)
        self.assertEqual(self.gate_with_ceph("bank", "lumos").returncode, 75)
        self.assertEqual(len(self.submitted()), count)
        # a sweep of the second source waits on the build the bank word queued
        self.live(jobs["catalog"])
        self.plan("two_source", "with:vindr_spinexr")
        done = self.gate("sweep", "two_source")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn(f"afterok:{jobs['catalog']}", self.line_of("sweep-driver.sbatch")[0])

    def test_bank_holds_its_room_while_its_job_is_live_and_settles_it_once_the_job_has_ended(self):
        # The size rule counts what a running job owes from its admission (grid/size-rule.sh,
        # owed_by_running): the bank word writes one for its bank job, $DATA/<id>/meta/SIZE, so a
        # fetch or an unpacking admitted after it counts the bank's room as taken (finding 23).
        raw = self.data / "vindr_spinexr" / "raw"
        raw.mkdir(parents=True)
        (raw / "a.dicom").write_bytes(b"d")
        self.ceph_fake(raw_bytes=100 * 10**9)
        done = self.gate_with_ceph("bank", "vindr_spinexr")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        bank = self.recorded()["bank"]
        size = self.data / "vindr_spinexr" / "meta" / "SIZE"
        record = size.read_text(encoding="utf-8").split()
        # admitted <job> <bytes to write> <bytes the landing held then> <utc> <total>, as a fetch's
        self.assertEqual(record[:4] + record[5:], ["admitted", bank, str(200 * 10**9), "2600000000000", str(200 * 10**9)])
        line = self.line_of("02-bank-ingest.sbatch")[0]
        self.assertIn(f" BANK_NEED={200 * 10**9}", line)
        self.assertIn(f" VOLUME={self.tmp} ", line)
        # while the job is queued or running, every decision counts it
        self.live(bank)
        done = self.gate_with_ceph("status")
        self.assertIn("  Owed  =         200.00gb still to land for 1 running fetch\n", done.stdout)
        self.assertTrue(size.read_text(encoding="utf-8").startswith(f"admitted {bank} "))
        # once Slurm no longer holds it, the next word settles the record, which then counts nothing
        self.live()
        done = self.gate_with_ceph("status")
        self.assertIn("  Owed  =         0.00gb still to land for 0 running fetches\n", done.stdout)
        self.assertTrue(size.read_text(encoding="utf-8").startswith(f"settled {bank} 200000000000 "))

    def grid_layout(self):
        """The gate as it reads the grid: the test's data root stands as the grid's own, so the gate
        hands the stages no DATA_ROOT and reads each recipe's own raw folder, moved under that root."""
        gate = self.repo / "grid" / "gate.sh"
        gate.write_text(gate.read_text(encoding="utf-8").replace(
            "GRID_DATA=/rs/rs_grp_oschome/go2432/data", f"GRID_DATA={self.data}"), encoding="utf-8")
        for recipe in (self.repo / "grid" / "banks").glob("*.json"):
            recipe.write_text(recipe.read_text(encoding="utf-8").replace("/rs/rs_grp_oschome/go2432/data", str(self.data)),
                              encoding="utf-8")

    def test_bank_waits_until_the_landing_that_holds_its_raw_copy_has_landed(self):
        # lumos's raw copy is zenodo_lumos/raw, which start's platform chain lands one zip at a time
        # as dp_zenodo_lumos: a bank admitted beside it would bank part of the set against a budget
        # read from part of it, so it waits for every fetch, unpacking and admission of the landing
        self.grid_layout()
        self.environments_ready()
        raw = self.data / "zenodo_lumos" / "raw"
        raw.mkdir(parents=True)
        (raw / "lumos_x_01_dcm.zip").write_bytes(b"z")
        (raw / "lumos_x_02_dcm.zip.part").write_bytes(b"z")
        self.ceph_fake(raw_bytes=2 * 10**9)
        self.state_line(7001, "start", "dp_zenodo_lumos")
        self.state_line(7002, "fetch:zenodo_lumos", "xr_fetch")
        self.state_line(7003, "unpack:zenodo_lumos", "unpack")
        for job in ("7001", "7002", "7003"):
            self.live(job)
            refused = self.gate_with_ceph("bank", "lumos")
            self.assertEqual(refused.returncode, 75, refused.stdout)
            self.assertIn(f"zenodo_lumos, which holds lumos's raw copy, is still being landed (job {job})", refused.stdout)
        # an admission of the landing a live job of any word still holds
        meta = self.data / "zenodo_lumos" / "meta"
        meta.mkdir()
        (meta / "SIZE").write_text("admitted 7004 46400000000 2598000000000 2026-10-25T00:00:00Z 46400000000\n", encoding="utf-8")
        self.live("7004")
        refused = self.gate_with_ceph("bank", "lumos")
        self.assertEqual(refused.returncode, 75, refused.stdout)
        self.assertIn("(job 7004)", refused.stdout)
        # start's X-ray fetch lands every open set of grid/fetch-xray.json, nih_chestxray14 among them
        self.state_line(7005, "start", "xr_fetch")
        self.live("7005")
        refused = self.gate_with_ceph("bank", "nih_chestxray14")
        self.assertEqual(refused.returncode, 75, refused.stdout)
        self.assertIn("nih_chestxray14, which holds nih_chestxray14's raw copy, is still being landed (job 7005)", refused.stdout)
        self.assertEqual(self.submitted(), [])
        # once the landing is still, the bank is queued for the recipe's own id
        self.live()
        done = self.gate_with_ceph("bank", "lumos")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn(" ONLY=lumos ", self.line_of("02-bank-ingest.sbatch")[0])
        # a recipe whose raw folder lies outside the data root names no landing to wait on: refused
        elsewhere = self.tmp / "elsewhere" / "vindr" / "raw"
        elsewhere.mkdir(parents=True)
        (elsewhere / "a.dicom").write_bytes(b"d")
        recipe = self.repo / "grid" / "banks" / "vindr_spinexr.json"
        recipe.write_text(recipe.read_text(encoding="utf-8").replace(f"{self.data}/vindr_spinexr/raw/vindr/1.0.0", str(elsewhere)),
                          encoding="utf-8")
        refused = self.gate_with_ceph("bank", "vindr_spinexr")
        self.assertEqual(refused.returncode, 2, refused.stdout)
        self.assertIn("is not under the data root", refused.stdout)
        self.assertEqual(len(self.submitted()), 2)

    def test_bank_budgets_by_the_format_the_recipe_names(self):
        # tools/bank.py copies a PNG and windows an uncompressed or lossless DICOM to an 8-bit PNG
        # under the raw copy's size, but turns JPEG, TIFF and BMP into PNG, which a q95 JPEG radiograph
        # grows 1.8 to 2.5 times into; its shard then copies the bank once more (finding 24). The word
        # holds this while the job waits; a lossy file's frames outgrow it, which the job's pixel bound
        # catches (test_the_bank_job_admits_what_the_frames_pixels_need_where_the_words_budget_is_less)
        self.environments_ready()
        recipe = (GRID / "banks" / "nih_chestxray14.json").read_text(encoding="utf-8")
        for name, image_format in (("a_jpg_set", "jpg"), ("a_tiff_set", "tiff"), ("a_webp_set", "webp")):
            (self.repo / "grid" / "banks" / f"{name}.json").write_text(
                recipe.replace('"id": "nih_chestxray14"', f'"id": "{name}"').replace('"format": "png"', f'"format": "{image_format}"'),
                encoding="utf-8")
            (self.data / name / "raw").mkdir(parents=True)
            (self.data / name / "raw" / "a").write_bytes(b"x")
        self.ceph_fake(raw_bytes=1500 * 10**9)
        done = self.gate_with_ceph("bank", "a_jpg_set")
        self.assertEqual(done.returncode, 75, done.stdout)
        self.assertIn("raw copy: 1500 GB of jpg, which bank.py turns into PNG; the bank and its shard: 9000 GB held", done.stdout)
        self.assertIn("refusing: the bank and its shard need 9000 GB and the room is 8844 GB", done.stdout)
        self.assertEqual(self.submitted(), [])
        self.ceph_fake(raw_bytes=1000 * 10**9)
        done = self.gate_with_ceph("bank", "a_tiff_set")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("the bank and its shard: 6000 GB held", done.stdout)
        self.assertIn(f" BANK_NEED={6000 * 10**9}", self.line_of("02-bank-ingest.sbatch")[0])
        # a format bank.py takes in no recipe here is never budgeted by a guess
        self.live()
        done = self.gate_with_ceph("bank", "a_webp_set")
        self.assertEqual(done.returncode, 2, done.stdout)
        self.assertIn("refusing: grid/banks/a_webp_set.json names the format 'webp', which the bank word has no budget for", done.stdout)
        # the shipped recipes' png and dcm keep twice the raw copy
        self.assertEqual(self.gate_with_ceph("bank", "nih_chestxray14").returncode, 2, "no raw copy of it here")
        (self.data / "nih_chestxray14" / "raw").mkdir(parents=True)
        (self.data / "nih_chestxray14" / "raw" / "a.png").write_bytes(b"p")
        self.live()
        done = self.gate_with_ceph("bank", "nih_chestxray14")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("raw copy: 1000 GB of png, which bank.py copies; the bank and its shard: 2000 GB held", done.stdout)

    def test_bank_and_unpack_of_one_set_never_run_side_by_side(self):
        # both hold their room through the set's one admission file, and a bank of a raw folder still
        # being unpacked would read half of it
        self.environments_ready()
        (self.data / "nih_chestxray14" / "raw").mkdir(parents=True)
        (self.data / "nih_chestxray14" / "raw" / "a.png").write_bytes(b"p")
        self.ceph_fake(raw_bytes=10**9)
        self.state_line(960, "unpack:nih_chestxray14", "unpack")
        self.live(960)
        done = self.gate_with_ceph("bank", "nih_chestxray14")
        self.assertEqual(done.returncode, 75, done.stdout)
        self.assertIn("an unpacking of nih_chestxray14 is still queued or running (job 960)", done.stdout)
        self.state_line(961, "bank:nih_chestxray14", "bank")
        self.live(961)
        done = self.gate("unpack", "nih_chestxray14")
        self.assertEqual(done.returncode, 75, done.stdout)
        self.assertIn("job 961", done.stdout)
        self.assertEqual(self.submitted(), [])

    def bank_job(self, **extra):
        """grid/02-bank-ingest.sbatch as Slurm starts the bank word's job: its admission checked under
        the size rule before the launcher, which a fake python stands in for, is handed the job; the
        job's other python, tools/bank.py's bound among it, runs on python3."""
        pydrv = self.fake / "pydrv"
        pydrv.write_text('#!/bin/bash\ncase "$1" in */flows/launch.py) printf \'%s\\n\' "$@" > "$FAKE/launched" ;; *) exec python3 "$@" ;; esac\n',
                         encoding="utf-8")
        pydrv.chmod(0o755)
        (self.fake / "launched").unlink(missing_ok=True)
        env = dict(self.gate_env(), GETFATTR=str(self.fake / "getfattr"), PYDRV=str(pydrv), SLURM_JOB_ID="4242", ONLY="vindr_spinexr",
                   BANK_NEED=str(200 * 10**9), VOLUME=str(self.tmp))
        env.update(extra)
        env.pop("SCHWINGNET_FLOW_STEP", None)
        done = subprocess.run(["bash", str(self.repo / "grid" / "02-bank-ingest.sbatch")], cwd=self.repo / "grid", env=env,
                              capture_output=True, text=True, timeout=60)
        launched = (self.fake / "launched").read_text(encoding="utf-8").split() if (self.fake / "launched").exists() else None
        return done, launched

    def test_the_bank_job_checks_the_room_again_before_it_writes_and_keeps_it_when_requeued(self):
        self.ceph_fake(raw_bytes=100 * 10**9)
        size = self.data / "vindr_spinexr" / "meta" / "SIZE"
        size.parent.mkdir(parents=True)
        size.write_text("admitted 4242 200000000000 2600000000000 2026-10-25T00:00:00Z 200000000000\n", encoding="utf-8")
        # a fetch admitted while the bank job waited in the queue now owes 8700 GB of the 8844 GB room
        other = self.data / "other_set" / "meta"
        other.mkdir(parents=True)
        (other / "SIZE").write_text("admitted 555 8700000000000 2600000000000 2026-10-25T00:00:00Z 8700000000000\n", encoding="utf-8")
        self.live(555, 4242)
        done, launched = self.bank_job()
        self.assertEqual(done.returncode, 4, done.stdout + done.stderr)
        self.assertIn("vindr_spinexr: refused for space; it needs 200 gb", done.stdout)
        self.assertIn("XR_BANK_RC=4", done.stdout)
        self.assertIsNone(launched, "nothing was banked")
        self.assertTrue((self.data / "vindr_spinexr" / "meta" / "REFUSED").exists())
        # its admission is settled, so it holds no room once the job has ended
        self.assertTrue(size.read_text(encoding="utf-8").startswith("settled 4242 "))
        # with the room there, the job is admitted again under its own id and hands itself to the launcher
        self.live(4242)
        done, launched = self.bank_job()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("vindr_spinexr: admitted; it needs 200 gb", done.stdout)
        self.assertEqual(launched[1:3], ["bank", "--max-workers"])
        self.assertTrue(size.read_text(encoding="utf-8").startswith("admitted 4242 200000000000 2600000000000 "))
        # requeued by Slurm after a preemption, it keeps the room it was given rather than decide again
        self.live(555, 4242)
        done, launched = self.bank_job(SLURM_RESTART_COUNT="1")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("vindr_spinexr: admitted already; job 4242 restarted", done.stdout)
        self.assertIsNotNone(launched)
        # a need that is no count, or more than one recipe, is refused before anything is read
        for extra in ({"BANK_NEED": "2e11"}, {"ONLY": "vindr_spinexr lumos"}):
            done, launched = self.bank_job(**extra)
            self.assertEqual(done.returncode, 4, f"{extra}: {done.stdout}")
            self.assertIsNone(launched)

    def test_the_bank_job_admits_what_the_frames_pixels_need_where_the_words_budget_is_less(self):
        # The word budgets the bank and its shard by a multiple of the raw copy's bytes, which a
        # lossy file holds fewer of than its frame takes as PNG (the second review of #252); the job
        # bounds them by the frames, read from their headers by tools/bank.py, before it writes, and
        # takes the larger admission under the size lock. Three 8-bit PNG frames of 40000 bytes,
        # which the bank copies and its shard copies again, need 240000 bytes, more than a budget
        # of 1000 bytes stands for.
        shutil.copy(ROOT / "tools" / "bank.py", self.repo / "tools" / "bank.py")
        self.ceph_fake(raw_bytes=120000)
        images = self.data / "nih_chestxray14" / "raw" / "images_001" / "images"
        images.mkdir(parents=True)
        header = b"\x89PNG\r\n\x1a\n" + b"\0\0\0\x0dIHDR" + (64).to_bytes(4, "big") * 2 + b"\x08\0\0\0\0"
        for name in ("00000001_000", "00000001_001", "00000002_000"):
            (images / f"{name}.png").write_bytes(header + b"\0" * (40000 - len(header)))
        size = self.data / "nih_chestxray14" / "meta" / "SIZE"
        size.parent.mkdir(parents=True)

        def admitted_for(need):
            size.write_text(f"admitted 4242 {need} 2600000000000 2026-10-25T00:00:00Z {need}\n", encoding="utf-8")
            return self.bank_job(ONLY="nih_chestxray14", BANK_NEED=str(need))

        # a fetch admitted while the job waited leaves 200000 bytes of room: the budget fits, the frames do not
        other = self.data / "other_set" / "meta"
        other.mkdir(parents=True)
        (other / "SIZE").write_text("admitted 555 8844232355520 2600000000000 2026-10-25T00:00:00Z 8844232355520\n",
                                    encoding="utf-8")
        self.live(555, 4242)
        done, launched = admitted_for(1000)
        self.assertEqual(done.returncode, 4, done.stdout + done.stderr)
        self.assertIn("nih_chestxray14: refused for space; it needs 1 gb of its 1 gb by the pixels of the bank and its shard", done.stdout)
        self.assertIsNone(launched, "nothing was banked")
        self.assertEqual((self.data / "nih_chestxray14" / "meta" / "REFUSED").read_text(encoding="utf-8").split()[:3],
                         ["4242", "240000", "200000"])
        self.assertTrue(size.read_text(encoding="utf-8").startswith("settled 4242 1000 "))
        # with the room there, the job holds the frames' need, not the budget, while it writes
        self.live(4242)
        done, launched = admitted_for(1000)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIsNotNone(launched)
        self.assertTrue(size.read_text(encoding="utf-8").startswith("admitted 4242 240000 2600000000000 "))
        # a budget above what the frames take stands as it did
        done, launched = admitted_for(500000)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("by the bank and its shard and", done.stdout)
        self.assertTrue(size.read_text(encoding="utf-8").startswith("admitted 4242 500000 2600000000000 "))
        # a frame whose header the bound cannot read admits nothing, whatever the budget
        (images / "00000003_000.png").write_bytes(b"not a png")
        done, launched = admitted_for(500000)
        self.assertEqual(done.returncode, 4, done.stdout + done.stderr)
        self.assertIn("nih_chestxray14: refused; the bank tool could not bound the frames by their pixels", done.stdout)
        self.assertIn("00000003_000.png: not a PNG", done.stderr)
        self.assertIsNone(launched)
        self.assertTrue(size.read_text(encoding="utf-8").startswith("settled 4242 500000 "))

    def progress(self, plan, folder, lines, age=0):
        state = self.smoke / plan / folder
        state.mkdir(parents=True)
        (state / "PROGRESS.txt").write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
        if age:
            stamp = time.time() - age
            os.utime(state / "PROGRESS.txt", (stamp, stamp))
        return state

    def test_status_shows_each_plans_newest_progress_rows_not_yet_matched_and_its_wandb_links(self):
        self.progress("synthetic", "0000000-00000000", ["plan synthetic state old rows 1", "row old-row failed no"], age=3600)
        state = self.smoke / "synthetic" / "abc1234-0123abcd"
        self.progress("synthetic", "abc1234-0123abcd", [
            f"plan synthetic state {state} rows 5 ran 2 refused 1 not_applicable 0 failed 1 to_come 1 mismatched 1 updated 2026-10-24T22:00:00Z",
            "row resnet18-64px-1a2b3c4d ran yes",
            "row refuse-resnet18-64px-00ff00ff refused yes",
            "row densenet121-32px-5e6f7a8b failed no",
            "row mobilenet-96px-9c0d1e2f ran no",
            "row seresnet50-128px-31415926 to-come -",
            *[f"wandb https://wandb.ai/lab/schwingnet/runs/run{n}" for n in range(5)]])
        # the synthetic catalog beside the state folders holds no PROGRESS.txt and is passed over
        (self.smoke / "synthetic" / "catalog").mkdir()
        self.progress("real", "abc1234-89abcdef", ["plan real state x rows 30 to_come 30"]
                      + [f"row resnet18-64px-{n:08x} to-come -" for n in range(25)])
        done = self.gate("status")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        out = done.stdout
        self.assertIn("## sweep synthetic, abc1234-0123abcd (", out)
        self.assertIn("  plan synthetic state <smoke>/synthetic/abc1234-0123abcd rows 5 ran 2", out)
        for shown in ("  row densenet121-32px-5e6f7a8b failed no", "  row mobilenet-96px-9c0d1e2f ran no",
                      "  row seresnet50-128px-31415926 to-come -", "  wandb https://wandb.ai/lab/schwingnet/runs/run3"):
            self.assertIn(shown, out)
        for gone in ("resnet18-64px-1a2b3c4d", "refuse-resnet18", "run4", "old-row", str(self.smoke)):
            self.assertNotIn(gone, out)
        self.assertIn("## sweep real, abc1234-89abcdef (", out)
        self.assertEqual(out.count("to-come -"), 21, out)
        self.assertIn("  (5 more rows not yet matched; the state folder's PROGRESS.txt holds them)", out)

    def test_status_shows_a_rows_code_and_withholds_a_reason_that_can_quote_a_value(self):
        # tools/block_sweep.py writes a row's refusal code and, after "why:", the last words the tools
        # wrote of it, which can quote a run's folder, a frame's file name with its case number, or a
        # run's id; status judges each row it shows as it judges a stage report's lines (report_shapes)
        withheld = "why: <reason withheld: it can quote a value; the whole report stays on the grid>"
        state = self.smoke / "real" / "c0dec0de-0123abcd"
        self.progress("real", "c0dec0de-0123abcd", [
            f"plan real state {state} rows 8 ran 0 refused 3 not_applicable 1 failed 4 to_come 0 mismatched 4 updated 2026-10-25T06:00:00Z",
            f"row resnet18-64px-0000aaaa refused mismatched init-mismatch why: the parent {self.runs}/20261022-ab12/train/best.pt is another net",
            "row resnet18-64px-00002222 failed - why: cannot open /scratch/go2432/case39 for reading",
            "row resnet18-64px-0000bbbb failed - why: FileNotFoundError: no such frame case134_0007.png",
            "row resnet18-64px-0000cccc failed - why: the flow run 1f2e3d4c5b6a7980 ended before its first epoch",
            "row resnet18-64px-0000dddd failed - why: CUDA out of memory / the trainer stopped",
            "row resnet18-64px-0000eeee refused mismatched no-validation why: the catalog holds no validation part of this source",
            "row resnet18-64px-0000ffff not-applicable mismatched why: no frame of the catalog is as large as the crop",
            "row resnet18-64px-00001111 refused mismatched one-crop",
            "wandb https://wandb.ai/lab/schwingnet/runs/1f2e3d4c"])
        done = self.gate("status")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        out = done.stdout
        # the code is shown whether its reason is or not; a path under the runs is cut to <runs> and
        # its reason kept, while a path the gate cannot name, a file name and a long hex run withhold it
        for shown in ("  row resnet18-64px-0000aaaa refused mismatched init-mismatch why: the parent <runs> is another net\n",
                      f"  row resnet18-64px-00002222 failed - {withheld}\n",
                      f"  row resnet18-64px-0000bbbb failed - {withheld}\n",
                      f"  row resnet18-64px-0000cccc failed - {withheld}\n",
                      f"  row resnet18-64px-0000dddd failed - {withheld}\n",
                      "  row resnet18-64px-0000eeee refused mismatched no-validation why: the catalog holds no validation part of this source\n",
                      "  row resnet18-64px-0000ffff not-applicable mismatched why: no frame of the catalog is as large as the crop\n",
                      "  row resnet18-64px-00001111 refused mismatched one-crop\n"):
            self.assertIn(shown, out)
        for gone in (str(self.runs), "20261022", "ab12", "best.pt", "scratch", "case39", "case134", "0007",
                     "1f2e3d4c5b6a7980", "the trainer stopped"):
            self.assertNotIn(gone, out.split("## sweep real", 1)[1].split("  wandb ", 1)[0])
        # the headline keeps its state folder and the W&B link stays whole: neither is a row
        self.assertIn("  plan real state <smoke>/real/c0dec0de-0123abcd rows 8", out)
        self.assertIn("  wandb https://wandb.ai/lab/schwingnet/runs/1f2e3d4c\n", out)

    def test_status_shows_every_sweeps_progress_even_when_the_other_sections_fill_the_page(self):
        # A status of the grid's size, every section at the most it shows: 80 sets on each root,
        # four plans' progress, 60 jobs, the newest of them a sweep that failed with its log and its
        # stage report, an older setup that failed, eight older stage reports, the committed sample
        # manifest and a results table of 30 lines. The sweeps' progress once came last and was cut
        # by the 400 lines; then it came first and pushed the newest jobs, every failed job's log and
        # every stage report off the page behind the manifest. Now the page is handed out in the
        # order a reader needs it, and what found no room is named on its last line.
        self.ceph_fake(raw_bytes=10**9)
        (self.tmp / "shared").mkdir()
        for n in range(80):
            (self.data / f"set_{n:02d}").mkdir()
            (self.tmp / "shared" / f"shared_{n:02d}").mkdir()
        logs = self.repo / "grid" / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        now = time.time()
        shutil.copy(ROOT / "docs" / "research" / "data-manifest" / "MANIFEST.md", logs / "SAMPLES-STAGE-REPORT.md")
        os.utime(logs / "SAMPLES-STAGE-REPORT.md", (now - 7200, now - 7200))
        rows = [(2000 + n, "start", f"job_{n}", f"sn_job_{n}", "COMPLETED", "00:10:00", None) for n in range(57)]
        rows += [(2100 + n, "start", "setup", "sn_setup", "FAILED", "00:01:00", [f"error line {i}" for i in range(20)])
                 for n in range(2)]
        rows += [(2200, "sweep:real", "sweep", "sweep", "FAILED", "04:00:00", [f"step {i}" for i in range(30)] + ["SN_SWEEP_RC=1"])]
        self.failed(*rows)
        for n in range(8):
            (logs / f"0{n}-STAGE-REPORT.md").write_text("".join(f"- line {i}\n" for i in range(13)), encoding="utf-8")
            os.utime(logs / f"0{n}-STAGE-REPORT.md", (now - 3600 - n, now - 3600 - n))
        (logs / "sweep-real-STAGE-REPORT.md").write_text(
            "".join(f"- sweep line {i}\n" for i in range(12)) + "- FAILED: the flow stopped before its first row\n", encoding="utf-8")
        run = self.runs / "newest"
        (run / "evaluate").mkdir(parents=True)
        (run / "evaluate" / "results.md").write_text("".join(f"| row {i} |\n" for i in range(30)), encoding="utf-8")
        plans = ("real", "synthetic", "trials", "two_source")
        for plan in plans:
            self.progress(plan, "abc1234-0123abcd", [f"plan {plan} rows 25 to_come 25"]
                          + [f"row resnet18-64px-{n:08x} to-come -" for n in range(25)]
                          + [f"wandb https://wandb.ai/lab/schwingnet/runs/{plan}{n}" for n in range(5)])
        done = self.gate_with_ceph("status")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        out = done.stdout
        self.assertLessEqual(len(out.splitlines()), 402)
        for plan in plans:
            self.assertIn(f"## sweep {plan}, abc1234-0123abcd (", out)
            self.assertIn(f"  plan {plan} rows 25 to_come 25", out)
            self.assertIn(f"  wandb https://wandb.ai/lab/schwingnet/runs/{plan}3", out)
        self.assertEqual(out.count("  (5 more rows not yet matched; the state folder's PROGRESS.txt holds them)"), 4)
        # after the space it reads beside, before the job list and every section that grows with the jobs
        self.assertLess(out.index("## space on the lab volume"), out.index("## sweep real"))
        self.assertLess(out.index("## sweep two_source"), out.index("## the gate's newest jobs"))
        # the newest job's row, the failed sweep's log and its stage report, newest of the reports
        self.assertIn("\n  2200 sweep FAILED 04:00:00 1:0 n1\n", out)
        self.assertIn("## 2200 (sweep) ended FAILED after 04:00:00, exit 1:0\n    SN_SWEEP_RC=1\n", out)
        self.assertIn("## 2101 (setup) ended FAILED after 00:01:00, exit 1:0\n", out)
        self.assertIn("## sweep-real-STAGE-REPORT.md (", out)
        self.assertIn("  - FAILED: the flow stopped before its first row\n", out)
        self.assertLess(out.index("## sweep-real-STAGE-REPORT.md ("), out.index("## 00-STAGE-REPORT.md ("))
        # the manifest, older than every report, and the run found no room, and the page says so last
        self.assertNotIn("## SAMPLES-STAGE-REPORT.md", out)
        unsaid = out.splitlines()[-2]
        self.assertTrue(unsaid.startswith("## not shown, for want of room on the page (400 lines and 64 KiB): "), unsaid)
        for named in ("stage reports", "the sample manifest", "the newest run"):
            self.assertIn(named, unsaid)

    def test_status_hands_the_sample_manifest_its_room_among_the_stage_reports_by_its_date(self):
        # The manifest changes only when a census runs: newest, it is shown whole before the jobs and
        # the older reports are cut and named; older than the reports, they come first and it is cut
        # to what is left, keeping its largest groups, and the page says what it left out.
        logs = self.repo / "grid" / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        manifest = logs / "SAMPLES-STAGE-REPORT.md"
        manifest.write_text("# The sample index\n\n" + "".join(f"| source_{i} | {i} |\n" for i in range(150)), encoding="utf-8")
        now = time.time()
        def reports(count):
            for path in logs.glob("[0-9]*-STAGE-REPORT.md"):
                path.unlink()
            for n in range(count):
                path = logs / f"{n:02d}-STAGE-REPORT.md"
                path.write_text("".join(f"- report {n} line {i}\n" for i in range(12)), encoding="utf-8")
                os.utime(path, (now - 600 - n, now - 600 - n))
        reports(30)
        os.utime(manifest, (now, now))
        out = self.gate("status").stdout
        self.assertLessEqual(len(out.splitlines()), 402)
        self.assertIn("  | source_0 | 0 |\n", out)
        self.assertIn("  | source_149 | 149 |\n", out)
        self.assertLess(out.index("## SAMPLES-STAGE-REPORT.md"), out.index("no job submitted by the gate yet"))
        # the reports newest first, so the newest is whole and the oldest gone
        self.assertIn("  - report 0 line 11\n", out)
        self.assertNotIn("report 29 line", out)
        self.assertEqual(out.count("earlier lines of this section not shown, for want of room on the page)"), 1, out)
        unsaid = out.splitlines()[-2]
        self.assertTrue(unsaid.startswith("## not shown, for want of room on the page (400 lines and 64 KiB): "), unsaid)
        self.assertIn(" stage reports", unsaid)
        self.assertNotIn("manifest", unsaid)
        reports(26)
        os.utime(manifest, (now - 7200, now - 7200))
        out = self.gate("status").stdout
        self.assertLessEqual(len(out.splitlines()), 402)
        for n in range(26):
            self.assertIn(f"  - report {n} line 11\n", out)
        self.assertIn("  | source_0 | 0 |\n", out)
        self.assertNotIn("source_149", out)
        self.assertEqual(out.count("more lines of this section not shown, for want of room on the page)"), 1, out)
        self.assertNotIn("## not shown", out)

    def test_status_shows_the_newest_failed_sweep_of_each_plan_by_its_shapes(self):
        self.failed((1001, "sweep:real", "sweep", "sweep", "FAILED", "04:00:00", ["person carmlspine:case042 seen", "SN_SWEEP_RC=1"]),
                    (1002, "sweep:synthetic", "sweep", "sweep", "TIMEOUT", "04:00:00", ["SN_SWEEP_RC=3"]))
        done = self.gate("status")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("## 1001 (sweep) ended FAILED after 04:00:00", done.stdout)
        self.assertIn("## 1002 (sweep) ended TIMEOUT after 04:00:00", done.stdout)
        self.assertIn("    SN_SWEEP_RC=1", done.stdout)
        self.assertNotIn("case042", done.stdout)

    def test_the_chooser_with_a_source_also_wants_that_sources_train_part(self):
        self.carmlspine_shards()
        self.catalog_ready(version=2, also=("vindr_spinexr",))
        self.catalog_ready(version=3)
        # three arguments choose as before: the newest that holds C-ArmLSpine
        self.assertEqual(self.chosen(), (0, "catalog-000003-0123456789ab.sqlite"))
        # with the source, the newest that holds its train part too, the reason the newest one's
        self.assertEqual(self.chosen("vindr_spinexr"), (0, "catalog-000002-0123456789ab.sqlite"))
        code, said = self.chosen("lumos")
        self.assertEqual(code, 1)
        self.assertIn("(catalog-000003-0123456789ab.sqlite) holds no lumos train part", said)
        # a source's part needs every other test too: an unmarked version is passed over
        (self.data / "_catalog" / "checked" / "catalog-000002-0123456789ab.sqlite").unlink()
        self.assertEqual(self.chosen("vindr_spinexr")[0], 1)
        for odd in ("vindr*", "../x", "Vindr"):
            self.assertEqual(self.chosen(odd)[0], 1, odd)

    def test_the_chooser_alone_wants_c_armlspine_as_the_only_source_a_run_trains_or_selects_on(self):
        # the v1 plan's catalog: C-ArmLSpine's train and validation parts and no other source's,
        # since real is set against two_source, the same plan with VinDr-SpineXR beside it (#252)
        self.carmlspine_shards()
        self.catalog_ready(version=2)
        self.catalog_ready(version=3, also=("vindr_spinexr",))
        self.assertEqual(self.chosen(), (0, "catalog-000003-0123456789ab.sqlite"))
        self.assertEqual(self.chosen("--alone"), (0, "catalog-000002-0123456789ab.sqlite"))
        # another source's validation part counts as much as its train part; its test part does not
        log = self.data / "_catalog" / "VERSIONS.jsonl"
        lines = log.read_text(encoding="utf-8").splitlines()
        lines[0] = lines[0].replace('"carmlspine|train":50', '"carmlspine|train":50,"lumos|validation":3,"lumos|test":2')
        log.write_text("\n".join(lines) + "\n", encoding="utf-8")
        code, said = self.chosen("--alone")
        self.assertEqual(code, 1)
        self.assertIn("(catalog-000003-0123456789ab.sqlite) holds frames of vindr_spinexr to train or select on beside C-ArmLSpine's",
                      said)
        lines[0] = lines[0].replace(',"lumos|validation":3', "")
        log.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.assertEqual(self.chosen("--alone"), (0, "catalog-000002-0123456789ab.sqlite"))
        # every other test still holds: an unmarked version is passed over
        (self.data / "_catalog" / "checked" / "catalog-000002-0123456789ab.sqlite").unlink()
        self.assertEqual(self.chosen("--alone")[0], 1)
        self.assertEqual(self.chosen("--alone", "vindr_spinexr")[0], 1, "one choice at a time")

    def test_the_v1_plan_takes_the_version_that_qualifies_now_and_never_a_banks_build(self):
        self.environments_ready()
        self.carmlspine_shards()
        self.catalog_ready(version=2)
        self.plan("real", "v1")
        self.plan("two_source", "with:vindr_spinexr")
        self.state_line(700, "bank:vindr_spinexr", "bank")
        self.state_line(701, "bank:vindr_spinexr", "catalog")
        self.live(700, 701)
        done = self.gate("sweep", "real")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("catalog-000002-0123456789ab.sqlite qualifies", done.stdout)
        self.assertNotIn("--dependency", self.line_of("sweep-driver.sbatch")[0])
        # with the bank's two-source version in, real still finds the one of C-ArmLSpine alone
        self.live()
        self.catalog_ready(version=3, also=("vindr_spinexr",))
        done = self.gate("sweep", "real")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("catalog-000002-0123456789ab.sqlite qualifies", done.stdout)
        # no version of C-ArmLSpine alone: the bank's build never makes one, so it is not waited on
        (self.data / "_catalog" / "checked" / "catalog-000002-0123456789ab.sqlite").unlink()
        self.live(701)
        count = len(self.submitted())
        done = self.gate("sweep", "real")
        self.assertEqual(done.returncode, 75, done.stdout)
        self.assertIn("refusing: no catalog version holds C-ArmLSpine alone for the v1 plan", done.stdout)
        self.assertIn("holds frames of vindr_spinexr to train or select on", done.stdout)
        self.assertEqual(len(self.submitted()), count)
        # start's or v1's build may make one while C-ArmLSpine's are the only shards on the data root
        self.state_line(702, "v1", "catalog")
        self.live(701, 702)
        done = self.gate("sweep", "real")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("--dependency=afterok:702 ", self.line_of("sweep-driver.sbatch")[-1])
        # and never once another source's shard is there, which every build takes in
        self.live(702)
        shard = self.data / "vindr_spinexr" / "shards" / "2026-10-25-0a0b0c0d0e0f"
        shard.mkdir(parents=True)
        (shard / "MANIFEST.json").write_text("{}\n", encoding="utf-8")
        count = len(self.submitted())
        done = self.gate("sweep", "real")
        self.assertEqual(done.returncode, 75, done.stdout)
        self.assertIn("only while C-ArmLSpine's are the only shards on the data root", done.stdout)
        self.assertEqual(len(self.submitted()), count)

    def test_a_second_source_plan_waits_only_on_a_build_that_can_hold_that_source(self):
        self.environments_ready()
        self.carmlspine_shards()
        self.catalog_ready(version=2)
        self.plan("two_source", "with:vindr_spinexr")
        # start's build is live but nothing of vindr_spinexr is banked: it will not hold the source
        self.state_line(800, "start", "catalog")
        self.live(800)
        done = self.gate("sweep", "two_source")
        self.assertEqual(done.returncode, 75, done.stdout)
        self.assertIn("bank vindr_spinexr first", done.stdout)
        self.assertEqual(self.submitted(), [])
        # once its shard is on the data root, every build holds it
        shard = self.data / "vindr_spinexr" / "shards" / "2026-10-25-0a0b0c0d0e0f"
        shard.mkdir(parents=True)
        (shard / "MANIFEST.json").write_text("{}\n", encoding="utf-8")
        done = self.gate("sweep", "two_source")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("--dependency=afterok:800 ", self.line_of("sweep-driver.sbatch")[0])
        # a version that holds it now: no wait, though a bank of it is live
        self.catalog_ready(version=3, also=("vindr_spinexr",))
        self.state_line(801, "bank:vindr_spinexr", "catalog")
        self.live(800, 801)
        done = self.gate("sweep", "two_source")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("catalog-000003-0123456789ab.sqlite qualifies", done.stdout)
        self.assertNotIn("afterok:80", self.line_of("sweep-driver.sbatch")[1])

    def sweep_box(self):
        """box.sh as a fake for the sweep driver: it logs what it was asked and where the hold was,
        names $FAKE_CATALOG as the synthetic catalog, fails a split check while $FAKE/split_fails is
        there, names the state folder as block_sweep's state does with $FAKE/code, else c0dec0de,
        for the code's part, and answers for the launcher as flows/launch.py does, its exit code
        $FAKE/launch_rc, after a commit to the checkout that leaves the code $FAKE/move names where
        that file is there."""
        (self.repo / "grid" / "box.sh").write_text(r"""#!/bin/bash
echo "$* hold=$(cat "$SCHWINGNET/grid/logs/HOLD" 2>/dev/null)" >> "$FAKE/box.log"
case "$*" in
  *"block_sweep.py synthetic"*) echo "built a bank" >&2; echo "{\"catalog\": \"$FAKE_CATALOG\", \"reused\": false}" ;;
  *"block_sweep.py state"*)
    while [ $# -gt 0 ]; do case "$1" in --plan) p=$2; shift 2 ;; --catalog) c=$2; shift 2 ;; --out) o=$2; shift 2 ;; *) shift ;; esac; done
    name=$(sed -n 's/^ "plan": "\([^"]*\)",\{0,1\}$/\1/p' "$p" | head -n 1)
    echo "$o/$name/$(cat "$FAKE/code" 2>/dev/null || echo c0dec0de)-$(sha256sum < "$c" | cut -c1-8)" ;;
  *split-check*) [ ! -f "$FAKE/split_fails" ] || exit 1 ;;
  *"flows/launch.py"*)
    if [ -f "$FAKE/move" ]; then
      git -C "$SCHWINGNET" -c user.name=t -c user.email=t@t -c gc.auto=0 -c maintenance.auto=false commit -q --allow-empty -m "main moved"
      cp "$FAKE/move" "$FAKE/code"
    fi
    echo '{"decision": "run", "flow": "sweep", "key": "0123456789abcdef", "origin": null, "root": "/m"}'
    echo "a row ran"
    echo '{"flow": "sweep", "run": "SweepFlow/12", "successful": true, "verdict": 0}'
    exit "$(cat "$FAKE/launch_rc" 2>/dev/null || echo 0)" ;;
  *"import torch"*) echo "torch 2.5 cuda available False" ;;
esac
""", encoding="utf-8")

    def git_repo(self):
        git = ["git", "-c", "gc.auto=0", "-c", "maintenance.auto=false", "-c", "user.name=t", "-c", "user.email=t@t",
               "-C", str(self.repo)]
        subprocess.run([*git, "init", "-q"], check=True)
        subprocess.run([*git, "add", "pixi.lock"], check=True)
        subprocess.run([*git, "commit", "-q", "-m", "c"], check=True)
        return subprocess.run([*git, "rev-parse", "--short=7", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()

    def sweep_driver(self, plan, **extra):
        env = dict(os.environ, SCHWINGNET=str(self.repo), DATA_ROOT=str(self.data), SMOKE=str(self.smoke), FAKE=str(self.fake),
                   MODELS=str(self.models), PLAN=plan, SLURM_JOB_ID="777", **extra)
        for name in ("STORE", "WEIGHTS"):
            env.pop(name, None)
        return subprocess.run(["bash", str(self.repo / "grid" / "sweep-driver.sbatch")], cwd=self.repo / "grid", env=env,
                              capture_output=True, text=True, timeout=60)

    def synthetic_catalog(self):
        catalog = self.smoke / "synthetic" / "catalog" / "_catalog" / "versions" / "catalog-000001-0123456789ab.sqlite"
        catalog.parent.mkdir(parents=True)
        catalog.write_bytes(b"a synthetic catalog")
        return catalog

    def test_the_sweep_driver_builds_the_synthetic_catalog_checks_its_split_and_runs_the_launcher(self):
        self.git_repo()
        self.weights_ready()
        self.sweep_box()
        plan = self.plan("synthetic", "synthetic")
        catalog = self.synthetic_catalog()
        state = self.smoke / "synthetic" / f"c0dec0de-{hashlib.sha256(b'a synthetic catalog').hexdigest()[:8]}"
        state.mkdir(parents=True)
        (state / "RESULTS.md").write_text("# Sweep synthetic\n\n22 rows: 20 ran, 2 refused, all matched.\n\n| slug | outcome |\n|---|---|\n"
                                          "| a | ran |\n", encoding="utf-8")
        (state / "PROGRESS.txt").write_text("plan synthetic rows 22\nrow a ran yes\nwandb https://wandb.ai/lab/schwingnet/runs/x1\n",
                                            encoding="utf-8")
        done = self.sweep_driver("synthetic", FAKE_CATALOG=str(catalog))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("SN_SWEEP_RC=0", done.stdout)
        boxed = self.boxed()
        check = [i for i, line in enumerate(boxed) if "tools/catalog.py split-check" in line]
        launch = [i for i, line in enumerate(boxed) if "flows/launch.py" in line]
        self.assertTrue(check and launch and check[0] < launch[0], boxed)
        self.assertIn(f"tools/block_sweep.py synthetic --into {self.smoke}/synthetic/catalog hold=777 ", boxed[0])
        self.assertIn(f"split-check {catalog.parent.parent} --version 1 hold=777 ", boxed[check[0]])
        self.assertTrue([line for line in boxed if f"python tools/block_sweep.py state --plan {plan} --catalog {catalog} --out {self.smoke} " in line], boxed)
        self.assertIn(f"pixi run --locked -e train-gpu python flows/launch.py sweep --max-workers 1 -- --plan {plan} "
                      f"--catalog {catalog} --out {self.smoke} --environment train-gpu "
                      f"--weights resnet18={self.models}/resnet18-f37072fd.pth hold=777", boxed[launch[0]])
        report = (self.repo / "grid" / "logs" / "sweep-synthetic-STAGE-REPORT.md").read_text(encoding="utf-8")
        for line in (f"- state folder: {state}\n", "- catalog: the synthetic one (built now)\n",
                     '- launcher: {"decision": "run", "flow": "sweep"',
                     "- results: # Sweep synthetic\n", "- results: 22 rows: 20 ran, 2 refused, all matched.\n",
                     "- W&B: https://wandb.ai/lab/schwingnet/runs/x1\n", '- Metaflow: {"flow": "sweep", "run": "SweepFlow/12"',
                     "- launcher exited 0\n"):
            self.assertIn(line, report)
        self.assertNotIn("| a | ran |", report)
        self.assertFalse((self.repo / "grid" / "logs" / "HOLD").exists())
        # the launcher's own exit code is the job's
        (self.fake / "launch_rc").write_text("1", encoding="utf-8")
        done = self.sweep_driver("synthetic", FAKE_CATALOG=str(catalog))
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("SN_SWEEP_RC=1", done.stdout)
        # a failed split check: the launcher never runs
        (self.fake / "box.log").unlink()
        (self.fake / "split_fails").write_text("1", encoding="utf-8")
        done = self.sweep_driver("synthetic", FAKE_CATALOG=str(catalog))
        self.assertEqual(done.returncode, 1)
        self.assertIn("FAILED: the split check of version 1 failed; no sweep reads it", done.stdout)
        self.assertFalse([line for line in self.boxed() if "flows/launch.py" in line])

    def test_a_sweep_whose_checkout_moved_is_used_only_where_the_code_its_rows_run_stayed_the_same(self):
        # The state folder is named by the code the rows run (#252, finding 27), so a merge that
        # landed during the sweep and changed none of it leaves every row the code its folder names.
        self.git_repo()
        self.sweep_box()
        self.plan("synthetic", "synthetic")
        catalog = self.synthetic_catalog()
        (self.fake / "move").write_text("c0dec0de", encoding="utf-8")
        done = self.sweep_driver("synthetic", FAKE_CATALOG=str(catalog))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("during the sweep, with none of the code its rows run changed", done.stdout)
        (self.fake / "move").write_text("0dd0c0de", encoding="utf-8")
        done = self.sweep_driver("synthetic", FAKE_CATALOG=str(catalog))
        self.assertEqual(done.returncode, 3, done.stdout + done.stderr)
        self.assertIn("SN_SWEEP_RC=3", done.stdout)
        self.assertIn(f"changed the code its rows run (state folder now {self.smoke}/synthetic/0dd0c0de-", done.stdout)

    def test_the_sweep_driver_takes_the_version_its_catalog_names_and_refuses_one_that_lacks_a_source(self):
        self.git_repo()
        self.sweep_box()
        self.carmlspine_shards()
        self.catalog_ready(version=2)
        self.catalog_ready(version=3, carmlspine_test=False)
        self.plan("real", "v1")
        done = self.sweep_driver("real")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        launch = [line for line in self.boxed() if "flows/launch.py" in line]
        self.assertIn(f"--catalog {self.data}/_catalog/versions/catalog-000002-0123456789ab.sqlite ", launch[0])
        # no weights file: the launcher is given none, and the report says why
        self.assertNotIn("--weights", launch[0])
        self.assertIn("weights: none at", done.stdout)
        self.assertIn("CURRENT names catalog-000003-0123456789ab.sqlite; the sweep takes catalog-000002-0123456789ab.sqlite", done.stdout)
        # the second source's plan: no version holds its train part, so nothing runs
        (self.fake / "box.log").unlink()
        self.plan("two_source", "with:vindr_spinexr")
        done = self.sweep_driver("two_source")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("no catalog version to run on: the newest version with C-ArmLSpine (catalog-000002-0123456789ab.sqlite) "
                      "holds no vindr_spinexr train part (the gate's v1 word or bank vindr_spinexr makes one)", done.stdout)
        self.assertEqual(self.boxed(), [])
        self.assertFalse((self.repo / "grid" / "logs" / "HOLD").exists())
        # a plan's name that is no id never reaches a path
        self.assertEqual(self.sweep_driver("../real").returncode, 2)


    def test_the_sweep_driver_runs_the_v1_plan_on_c_armlspine_alone_and_the_second_source_plan_beside_it(self):
        # the comparison the plans are for: real on the version of C-ArmLSpine alone, two_source on
        # the newer one the bank word built with VinDr-SpineXR beside it, never both on the same file
        self.git_repo()
        self.sweep_box()
        self.carmlspine_shards()
        self.catalog_ready(version=2)
        self.catalog_ready(version=3, also=("vindr_spinexr",))
        self.plan("real", "v1")
        self.plan("two_source", "with:vindr_spinexr")
        catalogs = {}
        for plan in ("real", "two_source"):
            (self.fake / "box.log").unlink(missing_ok=True)
            done = self.sweep_driver(plan)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            launch = [line for line in self.boxed() if "flows/launch.py" in line]
            catalogs[plan] = launch[0].split("--catalog ", 1)[1].split()[0]
        self.assertEqual(catalogs, {"real": f"{self.data}/_catalog/versions/catalog-000002-0123456789ab.sqlite",
                                    "two_source": f"{self.data}/_catalog/versions/catalog-000003-0123456789ab.sqlite"})
        # with no version of C-ArmLSpine alone, real runs nothing rather than the two-source one
        (self.data / "_catalog" / "checked" / "catalog-000002-0123456789ab.sqlite").unlink()
        (self.fake / "box.log").unlink()
        done = self.sweep_driver("real")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("no catalog version to run on: the newest version with C-ArmLSpine (catalog-000003-0123456789ab.sqlite) holds frames "
                      "of vindr_spinexr to train or select on beside C-ArmLSpine's", done.stdout)
        self.assertEqual(self.boxed(), [])


if __name__ == "__main__":
    unittest.main()
