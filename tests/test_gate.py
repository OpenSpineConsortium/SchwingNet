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
import importlib.util
import io
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRID = ROOT / "grid"


def load_module(path, name):
    """A module of the repository by its file, as the flows' own progress writer is loaded to lay out
    what status reads."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FAKE_HPCWORKER = ROOT / "tests" / "fakes" / "hpcworker"
NEW_SCRIPTS = ("gate.sh", "hpcw.sh", "box.sh", "bin/pixi", "bin/train-cpu-python", "00-setup.sbatch", "00-weights.sbatch",
               "00-carmlspine.sbatch", "v1-driver.sbatch", "experiment-driver.sbatch", "run-xray-chain.sh",
               "run-platform-fetch.sh", "sweep-driver.sbatch", "v1-version.sh", "realism.sbatch", "venv.sh",
               "drr-gap.sbatch", "drr-seg.sbatch", "gold3-census.sbatch")
ENVS = ("default", "train-cpu", "train-gpu", "telemetry")
# What bench flexray_drr_gap's word says of a mask folder that is there: the study reads too few CTs'
# masks as none, which its summary says, so the word says only where the folder is.
READ_WHERE = "read where enough CTs have them (the study's summary says how many)"
# A stand-in for spinesurg-ct-nnunet's benchmark/run_spineps_cases.py, which the timing stage of the anomaly
# route runs in the spineps conda environment: a mask and a timing record per case, no SPINEPS; a case whose
# name says fail fails, and the runner then exits 2 as the real one does.
FAKE_SPINEPS_RUNNER = """import argparse, csv, json, os, sys
from pathlib import Path
ap = argparse.ArgumentParser()
for name in ("--cases", "--out_dir", "--work", "--model_semantic", "--model_instance", "--model_labeling"):
    ap.add_argument(name, required=True)
a = ap.parse_args()
assert os.environ.get("SPINEPS_SEGMENTOR_MODELS"), "SPINEPS_SEGMENTOR_MODELS is set"
assert a.model_semantic.endswith("/CT_semantic") and a.model_labeling.endswith("/ct_labeling"), "the CT models"
out = Path(a.out_dir)
out.mkdir(parents=True, exist_ok=True)
Path(a.work).mkdir(parents=True, exist_ok=True)
rc = 0
with open(a.cases, newline="") as fh, open(out / "timing_shard0.jsonl", "a") as log:
    for n, row in enumerate(csv.DictReader(fh)):
        ok = Path(row["ct"]).is_file() and "fail" not in row["case"]
        if ok:
            (out / (row["case"] + "_seg-vert_msk.nii.gz")).write_bytes(b"mask")
        else:
            rc = 2
        log.write(json.dumps({"case": row["case"], "seconds": 60.0 + 30 * n, "ok": ok}) + "\\n")
        print(row["case"], "ok" if ok else "failed", flush=True)
sys.exit(rc)
"""
# A stand-in for spinesurg-ct-nnunet's tools/spineps_ids.py check --strict, the guard the pack stage of the anomaly
# route runs over every SPINEPS mask in the spineps conda environment: OK for each mask but the one whose name
# holds FAKE_GUARD_FAIL (amos_0001 unless the test says otherwise), refused as a skipped name, as the real one prints them.
FAKE_SPINEPS_GUARD = """import os, sys
args = sys.argv[1:]
assert args[0] == "check" and "--strict" in args, args
fail = os.environ.get("FAKE_GUARD_FAIL", "amos_0001")
print("WARNING something: misnamed_1_2_levels at a level", file=sys.stderr)
for path in args[1:]:
    if path.startswith("--"):
        continue
    if fail in path:
        print(f"FAIL {path}: SPINEPS ids cannot be read as VerSe names [veridah_skipped_name]: VERIDAH's ctd skips T12")
    else:
        print(f"OK   {path}: verse_ok")
"""
# A stand-in for the packager's python in the pack stage's venv (grid/venv.sh), run through grid/box.sh with
# SCHWINGNET_NATIVE=1: the probe and the projection check by -c, fxr-dataset pack by copying the manifest into the
# package, check by its one line; it logs what it saw at each call, whether the checkout was held and whether the
# landing's masks folder and the admission stood, so a test reads the order the stage did things in.
FAKE_PACK_PYTHON = """#!/bin/bash
log=$FAKE/fakepy.log
hold=no; [ -e "$SCHWINGNET/grid/logs/HOLD" ] && hold=yes
masks=no; [ -d "$DATA_ROOT/flexray_pack/masks" ] && masks=yes
admission=$(cut -d' ' -f1 "$DATA_ROOT/flexray_pack/meta/SIZE" 2>/dev/null)
case "$1" in
  -c) echo "c hold=$hold masks=$masks admission=${admission:-none}" >> "$log"; exit 0 ;;
  -m)
    [ "$2" = fxr.datasets ] || { echo "fake python: $*" >&2; exit 64; }
    case "$3" in
      pack)
        dataset=$(basename "$(dirname "$(dirname "$5")")")
        echo "pack $dataset hold=$hold masks=$masks admission=${admission:-none}" >> "$log"
        [ ! -f "$FAKE/pack_fails" ] || { echo "the packager fell over"; exit 3; }
        mkdir -p "$5" && cp "$4" "$5/MANIFEST.json" || exit 2
        [ ! -f "$FAKE/commit_during_pack" ] || git -C "$SCHWINGNET" -c user.name=t -c user.email=t@t -c gc.auto=0 -c maintenance.auto=false commit -q --allow-empty -m moved
        echo "$dataset: ct-seg, dense labels, 2 subjects, 3 samples (train=2, val=1) -> $5" ;;
      check)
        dataset=$(basename "$(dirname "$(dirname "$4")")")
        echo "check $dataset" >> "$log"
        [ -f "$4/MANIFEST.json" ] || { echo "no package at $4"; exit 1; }
        echo "$dataset: ct-seg, dense labels, 2 subjects, 3 samples (train=2, val=1) -> $4" ;;
      *) echo "fake python: $*" >&2; exit 64 ;;
    esac ;;
  *) echo "fake python: $*" >&2; exit 64 ;;
esac
"""

FAKES = {
    # what $FAKE/queue holds, or, asked for the pending jobs' reasons, what $FAKE/pending holds; its
    # arguments logged
    "squeue": """#!/bin/bash
echo "$*" >> "$FAKE/squeue.log"
[ -f "$FAKE/squeue_fails" ] && { echo "slurm_load_jobs error: Socket timed out" >&2; exit 1; }
case " $* " in
  *" -t PENDING "*) cat "$FAKE/pending" 2>/dev/null || true ;;
  *) cat "$FAKE/queue" 2>/dev/null || true ;;
esac
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

    def gate(self, *words, data_root=None, **extra):
        env = self.gate_env(data_root)
        env.update(extra)
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
        # the benchmarks' run folders, where the DRR domain-gap study's PROGRESS.txt is read from
        env["BENCH_ROOT"] = str(self.tmp / "go2432" / "bench")
        # the Metaflow datastore, where every launched flow keeps its progress page (flows/stage_progress.py)
        env["SCHWINGNET_METAFLOW"] = str(self.flow_root())
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

    GIT = ("git", "-c", "gc.auto=0", "-c", "maintenance.auto=false", "-c", "user.name=t", "-c", "user.email=t@t")

    def carrier(self, files):
        """A private repository as a cloud session leaves one: a branch whose last commit holds FILES (path:
        bytes) and SHA256SUMS over them, in a bare repository at <tmp>/remotes/owner/carrier.git, which
        CARRY_BASE=file://<tmp>/remotes reaches. Its commits, oldest first, and the record's values."""
        work = self.tmp / "carrier-work"
        remote = self.tmp / "remotes" / "owner" / "carrier.git"
        remote.parent.mkdir(parents=True)
        subprocess.run([*self.GIT, "init", "-q", "--bare", str(remote)], check=True)
        subprocess.run([*self.GIT, "init", "-q", str(work)], check=True)
        git = [*self.GIT, "-C", str(work)]
        commits = []
        for step in (dict(list(files.items())[:1]), files):
            for name, data in step.items():
                (work / name).parent.mkdir(parents=True, exist_ok=True)
                (work / name).write_bytes(data)
            sums = "".join(f"{hashlib.sha256(data).hexdigest()}  {name}\n" for name, data in sorted(step.items()))
            (work / "SHA256SUMS").write_text(sums, encoding="utf-8")
            subprocess.run([*git, "add", "-A"], check=True)
            subprocess.run([*git, "commit", "-q", "-m", "carry"], check=True)
            commits.append(subprocess.run([*git, "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip())
        subprocess.run([*git, "push", "-q", str(remote), "HEAD:refs/heads/claude/carrier"], check=True, capture_output=True)
        sums = (work / "SHA256SUMS").read_bytes()
        values = {"repo": "owner/carrier", "branch": "claude/carrier", "commit": commits[-1], "files": str(len(files) + 1),
                  "bytes": str(sum(len(data) for data in files.values()) + len(sums)), "manifest": hashlib.sha256(sums).hexdigest()}
        return commits, values

    def carry_record(self, values, name="carried_set"):
        (self.repo / "grid" / "carry").mkdir(exist_ok=True)
        lines = "".join(f"{key} {value}\n" for key, value in values.items())
        (self.repo / "grid" / "carry" / f"{name}.txt").write_text("# a carried folder for the test\n" + lines, encoding="utf-8")

    def carry(self, name="carried_set"):
        self.ceph_fake()
        env = dict(self.gate_env(), GETFATTR=str(self.fake / "getfattr"), CARRY_BASE=f"file://{self.tmp / 'remotes'}")
        return subprocess.run(["bash", str(self.repo / "grid" / "gate.sh"), "fetch", name], env=env, capture_output=True, text=True, timeout=120)

    CARRIED = {"a/one.txt": b"one\n", "b c/two.bin": bytes(range(256)) * 4, "README.md": b"# carried\n"}

    def test_a_carried_folder_lands_checked_with_no_job_and_a_later_send_checks_it_again(self):
        commits, values = self.carrier(self.CARRIED)
        self.carry_record(values)
        done = self.carry()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        landing = self.data / "carried_set"
        for name, data in self.CARRIED.items():
            self.assertEqual((landing / name).read_bytes(), data, name)
        self.assertEqual(oct(landing.stat().st_mode & 0o777), "0o700")
        self.assertEqual((landing / "a" / "one.txt").stat().st_mode & 0o077, 0, "only the account reads the files")
        carried = (landing / "meta" / "CARRIED").read_text(encoding="utf-8").split()
        self.assertEqual(carried[:4], ["carried", commits[-1], values["files"], values["bytes"]])
        self.assertEqual(carried[5:], ["owner/carrier", "claude/carrier"])
        self.assertFalse((self.data / ".carry_carried_set").exists(), "the git copy is gone once the folder is in place")
        self.assertIn("room: 8844 GB free under its quota", done.stdout)
        self.assertIn(f"carried_set: carried at {commits[-1][:12]}", done.stdout)
        self.assertNotIn(str(self.data), done.stdout)
        self.assertEqual(self.submitted(), [])
        self.assertEqual(self.recorded(), {})
        # a later send fetches nothing and checks the landing again
        done = self.carry()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn(f"its {values['files']} files match SHA256SUMS again; nothing was fetched", done.stdout)
        (landing / "a" / "one.txt").write_bytes(b"changed\n")
        done = self.carry()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("1 of its files do not match SHA256SUMS", done.stdout)

    def test_a_carried_folder_is_refused_whole_when_anything_differs_from_its_record(self):
        commits, values = self.carrier(self.CARRIED)
        landing, stage = self.data / "carried_set", self.data / ".carry_carried_set"
        cases = (
            ({"commit": commits[0]}, 2, "is not at the record's commit"),
            ({"branch": "claude/gone"}, 1, "git could not fetch the branch claude/gone of owner/carrier"),
            ({"files": "3"}, 2, "where the record says 3 files"),
            ({"bytes": str(int(values["bytes"]) + 1)}, 2, "bytes and none other"),
            ({"manifest": "0" * 64}, 1, "its SHA256SUMS is not the one the record names"),
            ({"commit": "HEAD"}, 2, "is not of its shape"),
            ({"branch": "claude/../main"}, 2, "is not of its shape"),
            # ten terabytes and their git copy: more than the 8844 GB of room, refused before git runs
            ({"bytes": str(10 * 10**12)}, 75, "the folder and its git copy need 20200 GB and the room is 8844 GB; nothing was fetched"),
        )
        for change, code, said in cases:
            self.carry_record(dict(values, **change))
            done = self.carry()
            self.assertEqual(done.returncode, code, f"{change}: {done.stdout}{done.stderr}")
            self.assertIn(said, done.stdout, change)
            self.assertFalse(landing.exists(), change)
            self.assertFalse(stage.exists(), change)
        self.carry_record({key: value for key, value in values.items() if key != "manifest"})
        self.assertEqual(self.carry().returncode, 2, "a record without its manifest")
        self.carry_record(values)
        # a folder of that name that holds no carry of the commit is never overwritten
        landing.mkdir()
        (landing / "keep").write_text("mine\n", encoding="utf-8")
        done = self.carry()
        self.assertEqual(done.returncode, 2, done.stdout)
        self.assertIn("holds no carry of", done.stdout)
        self.assertEqual(sorted(path.name for path in landing.iterdir()), ["keep"])
        # a git copy an earlier send left behind is cleared, and the folder lands
        landing.rename(self.tmp / "aside")
        stage.mkdir()
        (stage / "half").write_text("x", encoding="utf-8")
        done = self.carry()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual((landing / "README.md").read_bytes(), b"# carried\n")
        self.assertFalse(stage.exists())
        self.assertEqual(self.submitted(), [])

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

    MOOSE_MODELS = ("clin_ct_vertebrae", "clin_ct_peripheral_bones", "clin_ct_ribs", "clin_ct_organs",
                    "clin_ct_cardiac")
    MOOSE_RELEASE = "https://github.com/ENHANCE-PET/MOOSE/releases/download/moosez-v.3.1.3/"

    def moose_zips(self):
        """The model zips the row moose_weights of grid/run-platform-fetch.sh names, by their file
        names, read from the row as the gate and the bench job read them."""
        args = subprocess.run(["bash", str(self.repo / "grid" / "run-platform-fetch.sh"), "--args", "moose_weights"],
                              capture_output=True, text=True).stdout.split()
        return [url.rsplit("/", 1)[1] for url in args]

    def moose_weights_landed(self, names, cut=0):
        """The zips as the url route lands them under moose_weights/raw, each a whole zip of one
        member; with cut, each less its last cut bytes, the part the route leaves under the zip's
        final name while curl resumes it or when a download was cut short."""
        raw = self.data / "moose_weights" / "raw"
        raw.mkdir(parents=True, exist_ok=True)
        for name in names:
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as archive:
                archive.writestr(f"{name[:-4]}/dataset.json", "{}\n")
            data = buffer.getvalue()
            (raw / name).write_bytes(data[:len(data) - cut] if cut else data)

    def test_moose_weights_is_a_fetch_word_for_the_five_model_zips_outside_the_chain(self):
        # MOOSE's weights (moose_weights), what bench flexray_drr_seg runs on, are the five model zips
        # of the moosez CT models whose labels FleXray's MOOSE.yml stores (schwingnet.segmenters
        # MOOSEZ_MODELS; lungs, muscles and digestive store none), by their release URLs, one row of the owner's own lines:
        # never in the chain, no token file, no size stated (the job reads each zip's exact size before
        # a byte lands), GPL-3.0 as moosez's repository says, and queued as one platform fetch
        script = self.repo / "grid" / "run-platform-fetch.sh"
        row = [line for line in script.read_text(encoding="utf-8").splitlines() if line.startswith("moose_weights|")]
        self.assertEqual(len(row), 1, row)
        fields = row[0].split("|")
        self.assertEqual(fields[1:3], ["url", "0"])
        self.assertIn("GPL-3.0", fields[3])
        self.assertEqual(fields[4], "open")
        urls = fields[5].split()
        self.assertEqual(len(urls), 5, urls)
        names = [url[len(self.MOOSE_RELEASE):] for url in urls]
        for url, name in zip(urls, names):
            self.assertTrue(url.startswith(self.MOOSE_RELEASE) and url.endswith(".zip"), url)
        for model in self.MOOSE_MODELS:
            self.assertEqual(len([name for name in names if name.startswith(model + "_")]), 1, (model, names))
        self.assertEqual(self.moose_zips(), names)
        stated = subprocess.run(["bash", str(script), "--stated", "moose_weights"], capture_output=True, text=True)
        self.assertEqual(stated.stdout.strip(), "0")
        self.assertEqual(subprocess.run(["bash", str(script), "--args", "no;such"], capture_output=True, text=True).returncode, 64)
        done = self.gate_at_home("fetch", "moose_weights")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("moose_weights: job", done.stdout)
        jobs = self.line_of("platform-fetch.sbatch")
        self.assertEqual(len(jobs), 1, jobs)
        self.assertIn("ID=moose_weights", jobs[0])
        self.assertIn("dp_moose_weights", self.recorded())
        # the open chain never carries it, and the dry run names its route, every URL and that no size is stated
        env = dict(self.gate_env(), HOME=str(self.tmp / "home"), HPCW_DRY="1")
        chain = subprocess.run(["bash", str(script)], env=env, capture_output=True, text=True, timeout=120)
        self.assertNotIn("moose_weights", chain.stdout.split("Not submitted")[0])
        dry = subprocess.run(["bash", str(script), "--only", "moose_weights"], env=env, capture_output=True, text=True,
                             timeout=120)
        self.assertEqual(dry.returncode, 0, dry.stdout + dry.stderr)
        self.assertIn(f"would submit moose_weights: ROUTE=url ARGS='{' '.join(urls)}'", dry.stdout)
        self.assertIn("size budget: 1 sources, 0 GB stated", dry.stdout)
        self.assertIn("no size stated on the line for: moose_weights", dry.stdout)

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
            "266": "".join("block: architecture=resnet34\n" for _ in range(41)) + "recipe: none\nepochs: 1\nseed: 1\nhours: 1\n",
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
        # a credentialed set goes in, its catalog job after every catalog still live; the start
        # chain is recorded with its bank job and counts only by its sets' own admissions, none
        # of which it has made yet (grid/size-rule.sh, grid/admit.sh)
        sizes = (self.repo / "grid" / "logs" / "XRAY_SIZES.txt").read_text(encoding="utf-8").split()
        self.assertEqual([sizes[0], sizes[1], sizes[3]], [started["xr_fetch"], "sets", started["xr_bank"]])
        done = self.gate("fetch", "vindr_pcxr")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("0 GB of it owed to 0 running fetches", done.stdout)
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

    def test_status_says_what_a_pending_job_waits_for_and_when_slurm_expects_it(self):
        self.failed((700, "bench", "bench_flexray_drr_gap", "bench_flexray_drr_gap", "PENDING", "00:00:00", None),
                    ("701_[0-3]", "bench", "bench_flexray_drr_gap_shard", "bench_flexray_drr_gap_shard", "PENDING", "00:00:00", None),
                    (702, "bench", "bench_flexray_drr_gap_merge", "bench_flexray_drr_gap_merge", "PENDING", "00:00:00", None),
                    (703, "bench", "bench_flexray_drr_seg", "bench_flexray_drr_seg", "RUNNING", "00:10:00", None),
                    ("704_1", "bench", "bench_flexray_carmlspine", "bench_flexray_carmlspine", "PENDING", "00:00:00", None),
                    ("704_[2-3]", "bench", "bench_flexray_carmlspine", "bench_flexray_carmlspine", "PENDING", "00:00:00", None),
                    (705, "bench", "bench_flexray_deepfluoro", "bench_flexray_deepfluoro", "PENDING", "00:00:00", None),
                    (706, "bench", "bench_xvr_deepfluoro", "bench_xvr_deepfluoro", "PENDING", "00:00:00", None),
                    (707, "bench", "setup", "sn_setup", "PENDING", "00:00:00", None))
        (self.fake / "queue").write_text("700\n701_[0-3]\n702\n703\n704_1\n704_[2-3]\n705\n706\n707\n", encoding="utf-8")
        # 702 has no row; 703 runs, so a stale row for it says nothing; 704 is an array Slurm split in
        # two, each part with a reason of its own; 705's reason is empty, 706's row is cut short, and
        # 707's reason holds a token, which the redaction withholds with the rest of its row
        (self.fake / "pending").write_text(
            "700|Resources|2026-10-28T03:12:00\n701_[0-3]|Dependency|N/A\n703|Priority|N/A\n"
            "704_1|BeginTime|2026-10-28T00:05:00\n704_[2-3]|QOSMaxGRESPerUser|N/A\n705||N/A\n706|Priority\n"
            "707|token=ghp_abcdefgh12345678|N/A\n", encoding="utf-8")
        done = self.gate("status")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("  700 bench_flexray_drr_gap PENDING 00:00:00 1:0 n1, waiting: Resources, start expected 2026-10-28T03:12:00 grid time\n",
                      done.stdout)
        self.assertIn("  701_[0-3] bench_flexray_drr_gap_shard PENDING 00:00:00 1:0 n1, waiting: Dependency\n", done.stdout)
        self.assertIn("  702 bench_flexray_drr_gap_merge PENDING 00:00:00 1:0 n1\n", done.stdout)
        self.assertIn("  703 bench_flexray_drr_seg RUNNING 00:10:00 1:0 n1\n", done.stdout)
        self.assertIn("  704_1 bench_flexray_carmlspine PENDING 00:00:00 1:0 n1, waiting: BeginTime, start expected 2026-10-28T00:05:00 grid time\n",
                      done.stdout)
        self.assertIn("  704_[2-3] bench_flexray_carmlspine PENDING 00:00:00 1:0 n1, waiting: QOSMaxGRESPerUser\n", done.stdout)
        self.assertIn("  705 bench_flexray_deepfluoro PENDING 00:00:00 1:0 n1\n", done.stdout)
        self.assertIn("  706 bench_xvr_deepfluoro PENDING 00:00:00 1:0 n1\n", done.stdout)
        self.assertIn("  707 setup PENDING 00:00:00 1:0 n1\n", done.stdout)
        self.assertNotIn("ghp_", done.stdout)
        # squeue that does not answer leaves the job lines as sacct gives them, its error unshown and
        # not asked again for the reasons
        (self.fake / "squeue_fails").write_text("", encoding="utf-8")
        (self.fake / "squeue.log").unlink()
        done = self.gate("status")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("  700 bench_flexray_drr_gap PENDING 00:00:00 1:0 n1\n", done.stdout)
        self.assertNotIn("slurm_load_jobs", done.stdout)
        self.assertNotIn("-t PENDING", (self.fake / "squeue.log").read_text(encoding="utf-8"))

    def test_status_asks_squeue_for_no_reasons_where_no_job_waits(self):
        self.failed((710, "bench", "bench_flexray_drr_seg", "bench_flexray_drr_seg", "RUNNING", "00:10:00", None))
        (self.fake / "queue").write_text("710\n", encoding="utf-8")
        done = self.gate("status")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("  710 bench_flexray_drr_seg RUNNING 00:10:00 1:0 n1\n", done.stdout)
        self.assertNotIn("-t PENDING", (self.fake / "squeue.log").read_text(encoding="utf-8"))

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

    def test_a_standing_report_is_queued_once_more_only_where_bench_reruns_lists_its_job(self):
        # the owner's count for one more run of a benchmark whose report stands is an entry
        # <id>:<job> of BENCH_RERUNS, committed by pull request: a send whose report names that job,
        # from a commit not the checkout's, keeps the report under its job's number and queues the
        # benchmark again, the study's three jobs; the new report names its own job, so the entry
        # runs it once; another job, the listed job at the checkout's own commit, or another id's
        # report queues nothing, and a send refused for a missing input leaves the report standing
        commit = self.git_repo()
        self.drr_gap_inputs()
        self.environments_ready()
        gate = (self.repo / "grid" / "gate.sh").read_text(encoding="utf-8")
        listed = [line for line in gate.splitlines() if line.startswith("BENCH_RERUNS=")]
        self.assertEqual(listed, ['BENCH_RERUNS="flexray_drr_gap:40859208"'])
        logs = self.repo / "grid" / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        report = logs / "BENCH-flexray_drr_gap.md"
        kept = logs / "BENCH-flexray_drr_gap-40859208.md"
        head = "# bench flexray_drr_gap: job {} on voh6, commit {}, 2026-10-28 03:08:36 UTC\n"
        ended = "- exit 0 at 2026-10-28 03:26:43 UTC\n"
        for job, at in (("40828920", "d3fe578"), ("40859208", commit)):
            report.write_text(head.format(job, at) + ended, encoding="utf-8")
            done = self.gate("bench", "flexray_drr_gap")
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertIn("## BENCH-flexray_drr_gap.md (", done.stdout)
            self.assertNotIn("queueing the benchmark again", done.stdout)
            self.assertTrue(report.is_file())
        other = logs / "BENCH-flexray_carmlspine.md"
        other.write_text(head.format("40859208", "d3fe578").replace("flexray_drr_gap", "flexray_carmlspine") + ended, encoding="utf-8")
        done = self.gate("bench", "flexray_carmlspine")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertNotIn("queueing the benchmark again", done.stdout)
        self.assertTrue(other.is_file())
        self.assertEqual(self.submitted(), [])
        # the entry before it, job 40828920, spent by the second run, is listed no more and queued nothing above;
        # the listed job from an older commit: refused while an input is missing, the report left
        # standing, then queued once the input is back
        report.write_text(head.format("40859208", "d3fe578") + ended, encoding="utf-8")
        cts = self.data / "totalsegmentator_v201"
        cts.rename(self.tmp / "cts")
        refused = self.gate("bench", "flexray_drr_gap")
        self.assertEqual(refused.returncode, 2, refused.stdout)
        self.assertIn("refusing: bench flexray_drr_gap needs the TotalSegmentator CTs", refused.stdout)
        self.assertNotIn("queueing the benchmark again", refused.stdout)
        self.assertTrue(report.is_file())
        self.assertFalse(kept.exists())
        self.assertEqual(self.submitted(), [])
        (self.tmp / "cts").rename(cts)
        done = self.gate("bench", "flexray_drr_gap")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("  the report above is job 40859208's, which BENCH_RERUNS lets the owner's count run once more:"
                      f" queueing the benchmark again at {commit}\n", done.stdout)
        self.assertFalse(report.exists())
        self.assertEqual(kept.read_text(encoding="utf-8"), head.format("40859208", "d3fe578") + ended)
        self.assertEqual(len(self.submitted()), 3)
        self.assertEqual([line.split("--name ")[1].split()[0] for line in self.submitted()], list(self.DRR_GAP_NAMES))
        # the rerun's own report names prepare's new job, which no entry lists: printed, nothing queued
        (self.fake / "queue").write_text("", encoding="utf-8")
        report.write_text(head.format("101", "c694cc0") + ended, encoding="utf-8")
        for _ in range(2):
            done = self.gate("bench", "flexray_drr_gap")
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertNotIn("queueing the benchmark again", done.stdout)
        self.assertTrue(report.is_file())
        self.assertEqual(len(self.submitted()), 3)

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

    def test_census_gold3_queues_one_cpu_job_once_and_never_again_without_the_owners_word(self):
        # the owner's count of 2026-10-29 12:26 UTC is one CPU job: no id, another id and no tool are refused
        self.assertEqual(self.gate("census").returncode, 64)
        refused = self.gate("census", "tiers")
        self.assertEqual(refused.returncode, 64, refused.stdout)
        self.assertIn("census takes gold3", refused.stdout)
        self.assertEqual(self.gate("census", "gold3").returncode, 2)
        (self.repo / "tools" / "gold3_census.py").write_text("", encoding="utf-8")
        done = self.gate("census", "gold3")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        lines = self.submitted()
        # the environments are not made here, and still no setup job goes with it: the job finds its own python
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("--class batch --name census_gold3", lines[0])
        self.assertIn("--no-requeue", lines[0])
        self.assertIn("gold3-census.sbatch", lines[0])
        job = self.recorded()["census_gold3"]
        self.live(job)
        self.assertEqual(self.gate("census", "gold3").returncode, 75)
        (self.fake / "queue").write_text("", encoding="utf-8")
        # a job that ended with no report is not queued again: a second one waits for the owner's word
        again = self.gate("census", "gold3")
        self.assertEqual(again.returncode, 64, again.stdout)
        self.assertIn("left no report", again.stdout)
        report = self.repo / "grid" / "logs" / "CENSUS-gold3.md"
        report.write_text("# census gold3: job 1 on node, commit abc1234, 2026-10-29 15:00:00 UTC\n"
                          "- gold4: idc rows 2, admitted 1\n- exit 0 at 2026-10-30 01:00:00 UTC\n", encoding="utf-8")
        for _ in range(2):
            done = self.gate("census", "gold3")
            self.assertEqual(done.returncode, 0, done.stdout)
            self.assertIn("gold4: idc rows 2, admitted 1", done.stdout)
        self.assertEqual(len(self.submitted()), 1)

    def realism_inputs(self, *which):
        """The data root as the realism fetches leave it, each named set landed by its marker file, and
        weights, the ImageNet file the weights job makes."""
        markers = {"klein_4b": ("hf_flux2_klein_4b", "raw", "model_index.json"),
                   "klein_9b": ("hf_flux2_klein_9b", "raw", "model_index.json"),
                   "klein_base_4b": ("hf_flux2_klein_base_4b", "raw", "model_index.json"),
                   "flexray": ("hf_flexray_weights", "raw", "ensemble.json"),
                   "fluxray": ("hf_flexray_data", "raw", "FluXray", "samples.csv"),
                   "ct": ("aws_enhance_pet_ct", "raw", "0001.nii.gz"),
                   "truth": ("aws_enhance_pet_labels", "raw", "Vertebrae", "0001.nii.gz")}
        for name in which:
            if name == "weights":
                self.weights_ready()
                continue
            path = self.data.joinpath(*markers[name])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}\n", encoding="utf-8")

    def test_realism_refuses_a_stage_it_does_not_know_and_names_each_missing_input_in_turn(self):
        # no stage, two stages and a stage that is not one of the count's two are refused before anything is read
        self.assertEqual(self.gate("realism").returncode, 64)
        self.assertEqual(self.gate("realism", "edit", "stats").returncode, 64)
        refused = self.gate("realism", "train")
        self.assertEqual(refused.returncode, 64, refused.stdout)
        self.assertIn("edit or stats", refused.stdout)
        # the adapter's stages wait for a count and a PREREG of their own, whatever has landed
        for stage in ("lora", "eval"):
            refused = self.gate("realism", stage)
            self.assertEqual(refused.returncode, 64, refused.stdout)
            self.assertIn("a count and a PREREG of its own", refused.stdout)
        self.environments_ready()
        # a klein-4B on the data root stands in for nothing: the recipe's klein-9B is asked for
        steps = (((), "fetch hf_flux2_klein_9b first"), (("klein_4b",), "fetch hf_flux2_klein_9b first"),
                 (("klein_9b",), "ResNet-18's ImageNet weights"), (("weights",), "fetch hf_flexray_weights first"),
                 (("flexray",), "fetch hf_flexray_data first"), (("fluxray",), "fetch aws_enhance_pet_ct first"),
                 (("ct",), "fetch aws_enhance_pet_labels first"))
        for landed, said in steps:
            self.realism_inputs(*landed)
            refused = self.gate("realism", "edit")
            self.assertEqual(refused.returncode, 2, refused.stdout)
            self.assertIn(said, refused.stdout)
        self.assertEqual(self.submitted(), [])
        # the stats wait for the edit, whatever the data root holds
        refused = self.gate("realism", "stats")
        self.assertEqual(refused.returncode, 2, refused.stdout)
        self.assertIn("send realism edit first", refused.stdout)

    def test_realism_queues_each_stage_once_as_one_gpu_job_and_then_prints_its_report(self):
        self.environments_ready()
        self.realism_inputs("klein_9b", "weights", "flexray", "fluxray", "ct", "truth")
        done = self.gate("realism", "edit")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        lines = self.submitted()
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("--class gpu --name realism_edit", lines[0])
        self.assertIn("STAGE=edit", lines[0])
        self.assertIn("--no-requeue", lines[0])
        self.assertIn("realism.sbatch", lines[0])
        job = self.recorded()["realism_edit"]
        self.live(job)
        self.assertEqual(self.gate("realism", "edit").returncode, 75)
        (self.fake / "queue").write_text("", encoding="utf-8")
        logs = self.repo / "grid" / "logs"
        report = logs / "REALISM-edit.md"
        # a report that ended in failure keeps stats waiting; one that ended well frees it
        report.write_text("# realism edit: job 4242 on node, commit 0000000, 2026-10-26 01:00:00 UTC\n- exit 1 at 2026-10-26 02:00:00 UTC\n", encoding="utf-8")
        refused = self.gate("realism", "stats")
        self.assertEqual(refused.returncode, 2, refused.stdout)
        self.assertIn("send realism edit first", refused.stdout)
        report.write_text("# realism edit: job 4242 on node, commit 0000000, 2026-10-26 01:00:00 UTC\n- exit 0 at 2026-10-26 02:00:00 UTC\n", encoding="utf-8")
        for _ in range(2):
            done = self.gate("realism", "edit")
            self.assertEqual(done.returncode, 0, done.stdout)
            self.assertIn("- exit 0", done.stdout)
        done = self.gate("realism", "stats")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        lines = self.submitted()
        self.assertEqual(len(lines), 2, lines)
        self.assertIn("--class gpu --name realism_stats", lines[1])
        self.assertIn("STAGE=stats", lines[1])
        # the count is two GPU jobs: the adapter's stages queue nothing, whatever has landed
        self.realism_inputs("klein_base_4b")
        for stage in ("lora", "eval"):
            self.assertEqual(self.gate("realism", stage).returncode, 64)
        self.assertEqual(len(self.submitted()), 2)

    def test_a_realism_stage_and_the_runs_that_hold_the_checkout_each_wait_for_the_others(self):
        self.environments_ready()
        self.weights_ready()
        self.carmlspine_shards()
        self.catalog_ready(version=2)
        self.realism_inputs("klein_9b", "weights", "flexray", "fluxray", "ct", "truth")
        (self.data / "realxray" / "carmlspine" / "meta").mkdir(parents=True, exist_ok=True)
        self.state_line(900, "sweep:synthetic", "sweep")
        self.live(900)
        done = self.gate("realism", "edit")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("--dependency=afterany:900 ", self.line_of("realism.sbatch")[0])
        job = self.recorded()["realism_edit"]
        self.live(job)
        done = self.gate("bench", "flexray_carmlspine")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn(f"afterany:{job}", self.line_of("bench.sbatch")[0])

    def test_an_unfinished_realism_report_is_printed_and_queues_nothing_until_a_fix_moves_the_checkout(self):
        # a job ended past its own trap leaves only the .part: the next send must not queue a GPU job
        # the count never gave at the same commit, nor let that job write over the record
        commit = self.git_repo()
        self.environments_ready()
        self.realism_inputs("klein_9b", "weights", "flexray", "fluxray", "ct", "truth")
        logs = self.repo / "grid" / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        part = logs / "REALISM-edit.md.part"
        record = (f"# realism edit: job 4242 on node1, commit {commit}, 2026-10-29 05:00:00 UTC\n"
                  "- inputs: FluXray samples.csv; klein-9B the stand-in\n")
        part.write_text(record, encoding="utf-8")
        # while its job is live the .part is that job's, and the word waits for it
        self.state_line(4242, "realism:edit", "realism_edit")
        self.live(4242)
        self.assertEqual(self.gate("realism", "edit").returncode, 75)
        self.assertEqual(part.read_text(encoding="utf-8"), record)
        (self.fake / "queue").write_text("", encoding="utf-8")
        for _ in range(2):
            done = self.gate("realism", "edit")
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertIn("## REALISM-edit.md unfinished: the job ended before it wrote its exit", done.stdout)
            self.assertIn("- inputs: FluXray samples.csv", done.stdout)
            self.assertNotIn("queueing the stage again", done.stdout)
            self.assertEqual(part.read_text(encoding="utf-8"), record)
        self.assertEqual(self.submitted(), [])
        # an unfinished edit lets no stats run
        refused = self.gate("realism", "stats")
        self.assertEqual(refused.returncode, 2, refused.stdout)
        self.assertIn("send realism edit first", refused.stdout)
        # once a fix has moved the checkout it is queued once more, the record kept under its job
        part.write_text(record.replace(f"commit {commit},", "commit 0000000,"), encoding="utf-8")
        done = self.gate("realism", "edit")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("  the unfinished report above began on older code: queueing the stage again at ", done.stdout)
        self.assertFalse(part.exists())
        self.assertIn("- inputs: FluXray samples.csv", (logs / "REALISM-edit-4242-unfinished.md").read_text(encoding="utf-8"))
        lines = self.submitted()
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("--class gpu --name realism_edit", lines[0])

    def test_the_realism_job_refuses_a_stage_it_does_not_know_before_touching_anything(self):
        for stage in ("", "train", "lora", "eval"):
            env = dict(os.environ, SCHWINGNET=str(self.repo), DATA_ROOT=str(self.data), LAB_VOLUME=str(self.tmp), STAGE=stage)
            done = subprocess.run(["bash", str(self.repo / "grid" / "realism.sbatch")], cwd=self.repo / "grid", env=env,
                                  capture_output=True, text=True, timeout=60)
            self.assertEqual(done.returncode, 64, done.stdout + done.stderr)
            self.assertIn("SN_REALISM_RC=64", done.stdout)
            self.assertIn("edit or stats", done.stdout)
        self.assertFalse((self.repo / "grid" / "logs" / "REALISM-.md").exists())

    # A stand-in for the realism environment's python: it is the launcher as the job runs it, its words
    # logged, its own lines printed as flows/launch.py prints them and the flow's end step's as
    # Metaflow's runtime relays them, its time and task ahead of each, and the pointer and SUMMARY.md
    # the flow writes left where the job reads them. FAKE_MODE refuse is a launcher that refuses
    # before any run, nostart a run whose start failed before it wrote the pointer, and hang a run
    # still going when Slurm ends the job; FAKE_KEY is the run key the decision line names, FAKE_RUN
    # the run id, FAKE_ORIGIN the run a resume carries on, and FAKE_LINES how many lines the end step
    # prints before its own.
    FAKE_REALISM_PYTHON = """#!/bin/bash
echo "$*" >> "$FAKE/realism-python.log"
[ "$1" = flows/launch.py ] || exit 0
if [ "${FAKE_MODE:-}" = refuse ]; then
  echo "LaunchError: the PREREG moved since its hash was frozen" >&2
  echo "REALISM_RC=90 2026-10-29 04:00:00"
  exit 90
fi
key=${FAKE_KEY:-0123456789abcdef}
run=${FAKE_RUN:-1761710000000001}
if [ -n "${FAKE_ORIGIN:-}" ]; then
  folder=$REALISM_ROOT/$STAGE-$key-$FAKE_ORIGIN
  echo '{"code": "c0de", "decision": "resume", "flow": "realism", "key": "'"$key"'", "live": null, "origin": "'"$FAKE_ORIGIN"'", "root": "/rs/x/metaflow"}'
else
  folder=$REALISM_ROOT/$STAGE-$key-$run
  echo '{"code": "c0de", "decision": "run", "flow": "realism", "key": "'"$key"'", "live": null, "origin": null, "root": "/rs/x/metaflow"}'
fi
if [ "${FAKE_MODE:-}" = hang ]; then
  touch "$FAKE/realism-started"
  sleep 30
fi
if [ "${FAKE_MODE:-}" != nostart ]; then
  mkdir -p "$folder"
  printf '# summary of the stand-in\\n- keep: 7 of 8 edits kept\\n' > "$folder/SUMMARY.md"
  printf '{\\n "folder": "%s",\\n "key": "%s",\\n "run": "RealismFlow/%s",\\n "verdict": 0\\n}\\n' "$folder" "$key" "$run" > "$REALISM_ROOT/$STAGE.last.json"
  for n in $(seq 1 "${FAKE_LINES:-0}"); do
    echo "2026-10-29 04:00:00.123 [$run/end/7 (pid 4242)] RealismFlow: extra $n"
  done
  for line in 'keep: 7 of 8 edits kept' 'report: CLAIM 2024 and REFORMS report current (the stand-in)' 'verdict 0'; do
    echo "2026-10-29 04:00:00.123 [$run/end/7 (pid 4242)] RealismFlow: $line"
  done
fi
echo '{"flow": "realism", "run": "RealismFlow/'"$run"'", "successful": true, "verdict": 0}'
echo "REALISM_RC=${FAKE_RC:-0} 2026-10-29 04:00:00"
exit "${FAKE_RC:-0}"
"""

    def realism_job_env(self, stage, **extra):
        """The environment grid/realism.sbatch runs in, over the stand-in python in a ready environment."""
        pins = re.search(r'^REALISM_PIN="([^"]*)"$', (self.repo / "grid" / "realism.sbatch").read_text(encoding="utf-8"), re.M).group(1)
        venv = self.tmp / "go2432" / ".cache" / "realism" / f"venv-{hashlib.sha256(pins.encode()).hexdigest()[:12]}"
        (venv / "bin").mkdir(parents=True, exist_ok=True)
        (venv / "READY").write_text(pins + "\n", encoding="utf-8")
        (venv / "bin" / "python").write_text(self.FAKE_REALISM_PYTHON, encoding="utf-8")
        (venv / "bin" / "python").chmod(0o755)
        return dict(os.environ, SCHWINGNET=str(self.repo), DATA_ROOT=str(self.data), LAB_VOLUME=str(self.tmp), MODELS=str(self.models),
                    REALISM_ROOT=str(self.tmp / "realism"), FAKE=str(self.fake), SCHWINGNET_NATIVE="1", STAGE=stage,
                    SLURM_JOB_ID="4242", **extra)

    def realism_job(self, stage, **extra):
        """grid/realism.sbatch run as Slurm runs it, over the stand-in python in a ready environment."""
        return subprocess.run(["bash", str(self.repo / "grid" / "realism.sbatch")], cwd=self.repo / "grid",
                              env=self.realism_job_env(stage, **extra), capture_output=True, text=True, timeout=60)

    def realism_edit_ready(self):
        """A checkout with a commit and every input the edit job looks for before it starts the launcher."""
        commit = self.git_repo()
        self.weights_ready()
        self.realism_inputs("klein_9b", "flexray", "fluxray", "ct", "truth")
        (self.data / "hf_flexray_data" / "raw" / "FluXray" / "1.0").mkdir(parents=True)
        return commit

    def test_the_realism_job_starts_the_flow_through_the_launcher_and_reports_its_run(self):
        self.git_repo()
        self.weights_ready()
        self.realism_inputs("klein_4b", "flexray", "fluxray", "ct", "truth")
        (self.data / "hf_flexray_data" / "raw" / "FluXray" / "1.0").mkdir(parents=True)
        # a klein-4B stands in for nothing: the edit asks for the recipe's klein-9B
        done = self.realism_job("edit")
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("no FLUX.2 klein-9B weights", done.stdout)
        self.assertFalse((self.fake / "realism-python.log").exists())
        self.realism_inputs("klein_9b")
        done = self.realism_job("edit")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("SN_REALISM_RC=0", done.stdout)
        called = (self.fake / "realism-python.log").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(called), 1, called)
        words = called[0].split()
        self.assertEqual(words[:5], ["flows/launch.py", "realism", "--max-workers", "1", "--"])
        given = dict(zip(words[5::2], words[6::2]))
        self.assertEqual(given["--stage"], "edit")
        self.assertEqual(given["--out"], str(self.tmp / "realism"))
        self.assertEqual(given["--klein"], str(self.data / "hf_flux2_klein_9b" / "raw"))
        self.assertEqual(given["--imagenet"], str(self.models / "resnet18-f37072fd.pth"))
        self.assertTrue(given["--samples"].endswith("FluXray/samples.csv"))
        report = (self.repo / "grid" / "logs" / "REALISM-edit.md").read_text(encoding="utf-8")
        self.assertIn('- launcher: {"code": "c0de", "decision": "run"', report)
        self.assertIn("- keep: 7 of 8 edits kept", report)
        # the end step's lines come through Metaflow's head, the report check's among them, which
        # SUMMARY.md never holds
        self.assertIn("\n- report: CLAIM 2024 and REFORMS report current (the stand-in)\n", report)
        self.assertIn("\n- verdict 0\n", report)
        self.assertNotIn("RealismFlow:", report)
        self.assertIn(f"- run folder: {self.tmp / 'realism' / 'edit-0123456789abcdef-1761710000000001'}\n", report)
        self.assertIn("- progress page: /rs/x/metaflow/progress/RealismFlow/1761710000000001/index.html", report)
        self.assertIn("### SUMMARY.md", report)
        self.assertIn("# summary of the stand-in", report)
        self.assertEqual(report.splitlines()[-1][:9], "- exit 0 ")
        self.assertFalse((self.repo / "grid" / "logs" / "HOLD").exists())
        # the stats take the bundle and the weights and nothing of the edit's inputs, which the flow reads from its record
        done = self.realism_job("stats", FAKE_RC="1")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        words = (self.fake / "realism-python.log").read_text(encoding="utf-8").splitlines()[-1].split()
        self.assertEqual(sorted(dict(zip(words[5::2], words[6::2]))), ["--bundle", "--imagenet", "--out", "--stage"])
        report = (self.repo / "grid" / "logs" / "REALISM-stats.md").read_text(encoding="utf-8")
        self.assertIn("- launcher exited 1", report)
        self.assertEqual(report.splitlines()[-1][:9], "- exit 1 ")

    def test_the_realism_job_reports_only_the_run_folder_and_summary_of_its_own_run(self):
        # the pointer the flow writes outlives its job: a later job whose run never reached the
        # pointer, or reached it under another key, must not paste the earlier run's numbers
        self.realism_edit_ready()
        report = self.repo / "grid" / "logs" / "REALISM-edit.md"
        folder = self.tmp / "realism" / "edit-0123456789abcdef-1761710000000001"
        self.assertEqual(self.realism_job("edit").returncode, 0)
        self.assertIn(f"- run folder: {folder}\n", report.read_text(encoding="utf-8"))
        hour_ago = time.time() - 3600
        os.utime(folder / "SUMMARY.md", (hour_ago, hour_ago))
        # a launcher that refuses before any run names no key
        done = self.realism_job("edit", FAKE_MODE="refuse")
        self.assertEqual(done.returncode, 90, done.stdout + done.stderr)
        text = report.read_text(encoding="utf-8")
        self.assertIn("- run folder: none for this job (the launcher named no run key)\n", text)
        self.assertNotIn("### SUMMARY.md", text)
        self.assertNotIn("summary of the stand-in", text)
        self.assertTrue(text.splitlines()[-1].startswith("- exit 90 at "), text)
        # a run of another key whose start failed before the pointer: the pointer names the earlier key
        done = self.realism_job("edit", FAKE_MODE="nostart", FAKE_KEY="fedcba9876543210", FAKE_RC="1")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        text = report.read_text(encoding="utf-8")
        self.assertIn(f"- run folder: none for this job ({self.tmp / 'realism' / 'edit.last.json'} names no run of the key "
                      "fedcba9876543210)\n", text)
        self.assertNotIn("### SUMMARY.md", text)
        # a new run of the same key whose start failed before the pointer: the pointer names the earlier run
        done = self.realism_job("edit", FAKE_MODE="nostart", FAKE_RUN="1761710000000002", FAKE_RC="1")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        text = report.read_text(encoding="utf-8")
        self.assertIn(f"- run folder: none for this job ({self.tmp / 'realism' / 'edit.last.json'} names run 1761710000000001 "
                      "of the key 0123456789abcdef, not this job's run 1761710000000002)\n", text)
        self.assertNotIn(str(folder), text)
        self.assertNotIn("summary of the stand-in", text)
        # a resume of that run, which clones its start and pointer and failed again before its end:
        # the folder it carries on, but not the SUMMARY.md an earlier job wrote
        done = self.realism_job("edit", FAKE_MODE="nostart", FAKE_RUN="1761710000000003", FAKE_ORIGIN="1761710000000001", FAKE_RC="1")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        text = report.read_text(encoding="utf-8")
        self.assertIn(f"- run folder: {folder}\n", text)
        self.assertIn("- SUMMARY.md: not written by this job (the run did not reach its end step)\n", text)
        self.assertNotIn("summary of the stand-in", text)

    def test_the_realism_job_keeps_the_last_lines_of_the_end_step_and_its_launcher_s_exit(self):
        # the end step's last 40 lines, the report and the verdict last among them, and never its first
        self.realism_edit_ready()
        self.assertEqual(self.realism_job("edit", FAKE_LINES="45").returncode, 0)
        text = (self.repo / "grid" / "logs" / "REALISM-edit.md").read_text(encoding="utf-8")
        head = text[:text.index("### SUMMARY.md")]
        relayed = [line for line in head.splitlines() if line.startswith(("- extra ", "- keep: ", "- report: ", "- verdict "))]
        self.assertEqual(relayed[0], "- extra 9")
        self.assertEqual(relayed[-1], "- verdict 0")
        self.assertEqual(len(relayed), 40)
        self.assertNotIn("- - ", text)
        # a TERM once the launcher has exited keeps the launcher's exit, and none after finish begins
        # writes a second report (a TERM there comes too late to time in a test, so the script is read)
        script = (GRID / "realism.sbatch").read_text(encoding="utf-8")
        after = script[script.index("rc=${PIPESTATUS[0]}"):]
        self.assertRegex(after.splitlines()[3], r"^trap '.*finish \"\$rc\"' TERM$")
        finish = script[script.index("finish() {"):]
        self.assertEqual(finish.splitlines()[2].split("#")[0].strip(), "trap '' TERM")

    def test_a_realism_job_slurm_ends_writes_its_exit_and_the_gate_queues_nothing_at_its_commit(self):
        # Slurm's TERM at the time limit or a cancel reaches every process of the job; the job's trap
        # still finishes its report, and the next send prints it and queues no job at that commit
        self.realism_edit_ready()
        job = subprocess.Popen(["bash", str(self.repo / "grid" / "realism.sbatch")], cwd=self.repo / "grid",
                               env=self.realism_job_env("edit", FAKE_MODE="hang"), stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, start_new_session=True)
        try:
            for _ in range(400):
                if (self.fake / "realism-started").exists():
                    break
                time.sleep(0.05)
            self.assertTrue((self.fake / "realism-started").exists(), "the stand-in launcher never started")
            os.killpg(job.pid, signal.SIGTERM)
            output, _ = job.communicate(timeout=20)
        finally:
            if job.poll() is None:
                os.killpg(job.pid, signal.SIGKILL)
                job.wait()
        self.assertEqual(job.returncode, 143, output)
        logs = self.repo / "grid" / "logs"
        text = (logs / "REALISM-edit.md").read_text(encoding="utf-8")
        self.assertIn("- TERMINATED: Slurm ended the stage (its time limit, or a cancel) before it finished\n", text)
        self.assertTrue(text.splitlines()[-1].startswith("- exit 143 at "), text)
        self.assertEqual(text.count("- exit "), 1, text)
        self.assertFalse((logs / "REALISM-edit.md.part").exists())
        self.assertFalse((logs / "HOLD").exists())
        self.environments_ready()
        done = self.gate("realism", "edit")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("- TERMINATED: Slurm ended the stage", done.stdout)
        self.assertEqual(self.submitted(), [])

    def test_the_realism_job_installs_exactly_the_pins_the_prereg_froze(self):
        pins = re.search(r'^REALISM_PIN="([^"]*)"$', (GRID / "realism.sbatch").read_text(encoding="utf-8"), re.M).group(1)
        frozen = re.findall(r'^    "([^"]+==[^"]+)",$', (ROOT / "src" / "schwingnet" / "realism.py").read_text(encoding="utf-8"), re.M)
        self.assertTrue(frozen)
        self.assertEqual(pins.split(), frozen)

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
        self.assertIn("no held-out or disputed person in", report)
        self.assertIn("- exit 0 at ", report)
        self.assertFalse((self.repo / "grid" / "logs" / "HOLD").exists())
        self.assertTrue((self.tmp / "go2432" / "anomaly" / "select" / "selection.csv").exists())

    def spineps_fakes(self, smi="NVIDIA A100-SXM4-80GB, 8.0"):
        """What the timing stage needs on the node, each a stand-in: conda with the spineps environment, the runner, nvidia-smi."""
        ssn = self.tmp / "ssn"
        runner = ssn / "benchmark" / "run_spineps_cases.py"
        runner.parent.mkdir(parents=True, exist_ok=True)
        runner.write_text(FAKE_SPINEPS_RUNNER, encoding="utf-8")
        conda = self.tmp / "conda.sh"
        conda.write_text('conda() { echo "conda $*" >> "$FAKE/conda.log"; }\n', encoding="utf-8")
        (self.fake / "nvidia-smi").write_text('#!/bin/bash\ncat "$FAKE/smi"\n', encoding="utf-8")
        (self.fake / "nvidia-smi").chmod(0o755)
        (self.fake / "smi").write_text(smi + "\n", encoding="utf-8")
        return ssn, conda

    def test_timing_waits_for_a_sane_select_report_then_queues_one_gpu_job_and_leaves_a_blackwell_node_for_another(self):
        self.environments_ready()
        ssn, conda = self.spineps_fakes()
        logs = self.repo / "grid" / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        # each stage goes once the one before looks sane: no select report, or one that failed, refuses timing
        for text in (None, "# anomaly select: job 101 on n1, commit unknown, 2026-10-25 23:42:00 UTC\n- exit 1 at 2026-10-25 23:50:00 UTC\n"):
            if text:
                (logs / "ANOMALY-select.md").write_text(text, encoding="utf-8")
            refused = self.gate("anomaly", "timing", SSN=str(ssn), CONDA_SH=str(conda))
            self.assertEqual(refused.returncode, 2, refused.stdout)
            self.assertIn("logs/ANOMALY-select.md", refused.stdout)
        (logs / "ANOMALY-select.md").write_text("# anomaly select: job 101 on n1, commit unknown, 2026-10-25 23:42:00 UTC\n"
                                                "- exit 0 at 2026-10-25 23:50:00 UTC\n", encoding="utf-8")
        # and the node's side must be there: the spineps environment's conda and the runner
        refused = self.gate("anomaly", "timing", SSN=str(ssn), CONDA_SH=str(self.tmp / "no-conda.sh"))
        self.assertEqual(refused.returncode, 2, refused.stdout)
        self.assertIn("conda at", refused.stdout)
        refused = self.gate("anomaly", "timing", SSN=str(self.tmp / "no-ssn"), CONDA_SH=str(conda))
        self.assertEqual(refused.returncode, 2, refused.stdout)
        self.assertIn("run_spineps_cases.py", refused.stdout)
        self.assertEqual(self.submitted(), [])
        done = self.gate("anomaly", "timing", SSN=str(ssn), CONDA_SH=str(conda))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        lines = self.submitted()
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("--class gpu --name anomaly_timing", lines[0])
        self.assertIn("--cpus 8 --mem 64G --time 04:00:00 --no-requeue", lines[0])
        self.assertIn("STAGE=timing", lines[0])
        self.assertIn("anomaly.sbatch", lines[0])
        job = self.recorded()["anomaly_timing"]
        self.live(job)
        self.assertEqual(self.gate("anomaly", "timing", SSN=str(ssn), CONDA_SH=str(conda)).returncode, 75)
        (self.fake / "queue").write_text("", encoding="utf-8")
        # step 0 left a Blackwell node: the stage spent nothing, so it is queued again at the same commit
        report = logs / "ANOMALY-timing.md"
        head = "# anomaly timing: job {} on ymh3, commit unknown, 2026-10-26 00:10:00 UTC\n- GPU: NVIDIA RTX PRO 6000, sm_120: a Blackwell card\n"
        report.write_text(head.format(job) + "- exit 4 at 2026-10-26 00:10:05 UTC\n", encoding="utf-8")
        done = self.gate("anomaly", "timing", SSN=str(ssn), CONDA_SH=str(conda))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("left its node unused: queueing the stage again", done.stdout)
        self.assertFalse(report.exists())
        self.assertIn("- exit 4", (logs / f"ANOMALY-timing-{job}.md").read_text(encoding="utf-8"))
        self.assertEqual(len(self.submitted()), 2)
        # a stage that failed at the same commit is not queued again, and one that ended well never is
        report.write_text(head.format(job) + "- exit 1 at 2026-10-26 00:20:00 UTC\n", encoding="utf-8")
        self.assertEqual(self.gate("anomaly", "timing", SSN=str(ssn), CONDA_SH=str(conda)).returncode, 0)
        self.assertEqual(len(self.submitted()), 2)
        report.write_text(head.format(job) + "- exit 0 at 2026-10-26 00:30:00 UTC\n", encoding="utf-8")
        for _ in range(2):
            done = self.gate("anomaly", "timing", SSN=str(ssn), CONDA_SH=str(conda))
            self.assertEqual(done.returncode, 0, done.stdout)
            self.assertIn("- exit 0", done.stdout)
        self.assertEqual(len(self.submitted()), 2)

    def timing_job(self, ssn, conda):
        env = dict(os.environ, PATH=f"{self.fake}:{os.environ['PATH']}", FAKE=str(self.fake), SCHWINGNET=str(self.repo),
                   DATA_ROOT=str(self.data), LAB_VOLUME=str(self.tmp), SSN=str(ssn), CONDA_SH=str(conda), SPINEPS_PYTHON=sys.executable,
                   SPINEPS_SEGMENTOR_MODELS=str(self.tmp / "models"), TIMING_WORK=str(self.tmp / "work"), REALXRAY_WORK=str(self.tmp / "rxw"),
                   STAGE="timing", SLURM_JOB_ID="780", PYDRV=sys.executable)
        return subprocess.run(["bash", str(self.repo / "grid" / "anomaly.sbatch")], cwd=self.repo / "grid", env=env,
                              capture_output=True, text=True, timeout=60)

    def paired_cts(self):
        """A few paired CTs as the grid's records lay them out: COBRA's screen folders and C-ArmLSpine's case table."""
        cobra = self.data / "cobra2026"
        for case in ("cobra_named", "cobra_two", "cobra_mha"):
            (cobra / "cases" / case).mkdir(parents=True)
            (cobra / "cases" / case / "ct_def.mha").write_bytes(b"ct")
        (cobra / "lstv" / "nifti").mkdir(parents=True)
        (cobra / "lstv" / "seg").mkdir(parents=True)
        for case in ("cobra_named", "cobra_two"):
            (cobra / "lstv" / "nifti" / f"{case}_ct.nii.gz").write_bytes(b"ct")
        (cobra / "lstv" / "seg" / "cobra_named_seg-vert_msk.nii.gz").write_bytes(b"mask")
        carm = self.data / "carmlspine"
        (carm / "nifti").mkdir(parents=True)
        (carm / "spineps").mkdir()
        rows = []
        for case in ("carm_named", "carm_two", "carm_fail"):
            (carm / "nifti" / f"{case}_ct.nii.gz").write_bytes(b"ct")
            rows.append(f"{case},{carm / 'nifti' / f'{case}_ct.nii.gz'}")
        (carm / "cases.csv").write_text("case,ct\n" + "\n".join(rows) + "\n", encoding="utf-8")
        (carm / "spineps" / "carm_named_seg-vert_msk.nii.gz").write_bytes(b"mask")

    def anomaly_tools_committed(self, *names):
        self.git_repo()
        for name in names:
            shutil.copy(ROOT / "tools" / name, self.repo / "tools" / name)
        subprocess.run(["git", "-C", str(self.repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@t", "-c", "gc.auto=0",
                        "-c", "maintenance.auto=false", "commit", "-q", "-m", "tool"], check=True)

    def test_the_timing_stage_lists_the_lacking_cts_times_spineps_on_them_and_reports_counts_and_seconds_only(self):
        # anomaly.sbatch with STAGE=timing: the GPU self-test, the inventory, the pick, SPINEPS through
        # spinesurg-ct-nnunet's runner in the spineps environment, and the estimate; no case id or path
        # in the report, the runner's log on the lab volume, the work folder gone
        self.anomaly_tools_committed("anomaly_timing.py")
        self.paired_cts()
        ssn, conda = self.spineps_fakes()
        done = self.timing_job(ssn, conda)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("SN_ANOMALY_RC=0", done.stdout)
        report = (self.repo / "grid" / "logs" / "ANOMALY-timing.md").read_text(encoding="utf-8")
        self.assertIn("# anomaly timing: job 780", report.splitlines()[0])
        self.assertIn("- GPU: NVIDIA A100-SXM4-80GB, sm_80", report)
        self.assertIn("| cobra | 3 | 1 | 0 | 1 | 1 |", report)
        self.assertIn("| carmlspine | 3 | 1 | 0 | 2 | 0 |", report)
        self.assertIn("Asked for 10; picked 3 by rank among the 3 CTs with a NIfTI and no named mask, of 3 lacking one in all.", report)
        self.assertIn("NOTE: the runner over carmlspine exited 2 with 1 failed cases", report)
        self.assertIn("Timed 2 CTs; 1 failed.", report)
        self.assertIn("CTs still lacking a named mask after this run: 1 (carmlspine 1).", report)
        self.assertIn("The production array is not approved", report)
        self.assertIn("- exit 0 at ", report)
        for name in ("cobra_two", "carm_two", "carm_fail", str(self.data)):
            self.assertNotIn(name, report)
        out = self.tmp / "go2432" / "anomaly" / "timing"
        self.assertTrue((out / "spineps" / "cobra" / "cobra_two_seg-vert_msk.nii.gz").exists())
        self.assertTrue((out / "spineps" / "carmlspine" / "carm_two_seg-vert_msk.nii.gz").exists())
        self.assertFalse((out / "spineps" / "carmlspine" / "carm_fail_seg-vert_msk.nii.gz").exists())
        self.assertIn("carm_fail", (out / "spineps" / "carmlspine.log").read_text(encoding="utf-8"))
        self.assertIn("conda activate spineps", (self.fake / "conda.log").read_text(encoding="utf-8"))
        self.assertFalse((self.tmp / "work").exists())
        self.assertFalse((self.repo / "grid" / "logs" / "HOLD").exists())

    def test_the_timing_stage_leaves_a_blackwell_node_before_staging_a_ct(self):
        self.anomaly_tools_committed("anomaly_timing.py")
        self.paired_cts()
        ssn, conda = self.spineps_fakes(smi="NVIDIA RTX PRO 6000 Blackwell Server Edition, 12.0")
        done = self.timing_job(ssn, conda)
        self.assertEqual(done.returncode, 4, done.stdout + done.stderr)
        self.assertIn("SN_ANOMALY_RC=4", done.stdout)
        report = (self.repo / "grid" / "logs" / "ANOMALY-timing.md").read_text(encoding="utf-8")
        self.assertIn("Blackwell", report)
        self.assertTrue(report.splitlines()[-1].startswith("- exit 4 at "))
        self.assertFalse((self.tmp / "go2432" / "anomaly" / "timing" / "inventory.csv").exists())
        self.assertFalse((self.fake / "conda.log").exists())
        self.assertFalse((self.repo / "grid" / "logs" / "HOLD").exists())

    def test_anomaly_pack_is_refused_until_its_inputs_stand_then_queued_once_as_batch(self):
        self.environments_ready()
        ssn, conda = self.spineps_fakes()
        guard = ssn / "tools" / "spineps_ids.py"
        g3 = self.tmp / "split_final.json"
        selection = self.tmp / "go2432" / "anomaly" / "select" / "selection.csv"
        validation = self.repo / "data" / "splits" / "anomaly-validation.json"
        validation.unlink()
        logs = self.repo / "grid" / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        head = "# anomaly {}: job 101 on n1, commit unknown, 2026-10-26 00:10:00 UTC\n"
        env = dict(SSN=str(ssn), CONDA_SH=str(self.tmp / "no-conda.sh"), G3_SPLIT=str(g3))

        def write_selection():
            selection.parent.mkdir(parents=True, exist_ok=True)
            selection.write_text("person,collection,case,variant,tier,role,fold\n", encoding="utf-8")

        # each want in the order the gate names them: the two reports that ended well, the validation rule, conda,
        # the guard, G3's split and the selection select wrote; nothing is queued before the last stands
        steps = [("logs/ANOMALY-select.md", lambda: (logs / "ANOMALY-select.md").write_text(head.format("select") + "- exit 0 at 2026-10-26 00:20:00 UTC\n", encoding="utf-8")),
                 ("logs/ANOMALY-timing.md", lambda: (logs / "ANOMALY-timing.md").write_text(head.format("timing") + "- exit 0 at 2026-10-26 00:30:00 UTC\n", encoding="utf-8")),
                 ("data/splits/anomaly-validation.json", lambda: shutil.copy(ROOT / "data" / "splits" / "anomaly-validation.json", validation)),
                 ("conda at", lambda: env.update(CONDA_SH=str(conda))),
                 ("spineps_ids.py", lambda: (guard.parent.mkdir(parents=True, exist_ok=True), guard.write_text("", encoding="utf-8"))),
                 ("split_final.json", lambda: g3.write_text("{}", encoding="utf-8")),
                 ("selection.csv", write_selection)]
        for want, provide in steps:
            refused = self.gate("anomaly", "pack", **env)
            self.assertEqual(refused.returncode, 2, f"{want}: {refused.stdout}")
            self.assertIn(want, refused.stdout)
            provide()
        self.assertEqual(self.submitted(), [])
        done = self.gate("anomaly", "pack", **env)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        lines = self.submitted()
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("--class batch --name anomaly_pack", lines[0])
        self.assertIn("--cpus 4 --mem 64G --time 3-00:00:00 --no-requeue", lines[0])
        self.assertIn("STAGE=pack", lines[0])
        self.assertIn("anomaly.sbatch", lines[0])
        job = self.recorded()["anomaly_pack"]
        self.live(job)
        self.assertEqual(self.gate("anomaly", "pack", **env).returncode, 75)
        self.live()
        # the size rule refused the pack before a byte landed: the stage spent nothing, so it is queued again at
        # the same commit, its report kept under its job's number
        report = logs / "ANOMALY-pack.md"
        head = "# anomaly pack: job {} on n1, commit unknown, 2026-10-26 01:00:00 UTC\n- admission: flexray_pack: refused for space\n"
        report.write_text(head.format(job) + "- exit 5 at 2026-10-26 01:00:05 UTC\n", encoding="utf-8")
        done = self.gate("anomaly", "pack", **env)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("the size rule refused the pack: queueing the stage again", done.stdout)
        self.assertFalse(report.exists())
        self.assertIn("- exit 5", (logs / f"ANOMALY-pack-{job}.md").read_text(encoding="utf-8"))
        self.assertEqual(len(self.submitted()), 2)
        # a stage that failed at the same commit is not queued again, and one that ended well never is
        report.write_text(head.format(job) + "- exit 1 at 2026-10-26 01:20:00 UTC\n", encoding="utf-8")
        self.assertEqual(self.gate("anomaly", "pack", **env).returncode, 0)
        self.assertEqual(len(self.submitted()), 2)
        report.write_text(head.format(job) + "- exit 0 at 2026-10-26 01:30:00 UTC\n", encoding="utf-8")
        for _ in range(2):
            done = self.gate("anomaly", "pack", **env)
            self.assertEqual(done.returncode, 0, done.stdout)
            self.assertIn("- exit 0", done.stdout)
        self.assertEqual(len(self.submitted()), 2)

    def test_a_pack_admission_is_settled_by_the_next_word_when_its_job_died(self):
        # the pack's admission lives under the landing flexray_pack, whatever the gate's row for the job says;
        # a job Slurm no longer holds is settled by the next word, as a bank's is
        self.state_line(4242, "anomaly:pack", "anomaly_pack")
        size = self.data / "flexray_pack" / "meta" / "SIZE"
        size.parent.mkdir(parents=True)
        size.write_text("admitted 4242 1000 2600000000000 2026-10-26T01:00:00Z 1000\n", encoding="utf-8")
        self.ceph_fake()
        self.live(4242)
        done = self.gate_with_ceph("status")
        self.assertIn("still to land for 1 running fetch\n", done.stdout)
        self.assertTrue(size.read_text(encoding="utf-8").startswith("admitted 4242 "))
        self.live()
        done = self.gate_with_ceph("status")
        self.assertIn("still to land for 0 running fetches\n", done.stdout)
        self.assertTrue(size.read_text(encoding="utf-8").startswith("settled 4242 1000 "))

    PACK_ROWS = (("verse:verse100", "verse", "verse100", "L6", "read", "train", ""),
                 ("verse:verse200", "verse", "verse200", "normal", "", "train", "1"),
                 ("verse:verse300", "verse", "verse300", "T13", "read", "train", ""),
                 ("cobra:B100", "cobra2026", "B100", "normal", "", "test", ""),
                 ("amos22:0001", "amos22", "amos_0001", "normal", "", "train", ""),
                 ("amos22:0002", "amos22", "amos_0002", "L6", "two-labeller", "train", ""))

    def write_selection(self, rows):
        from tests.test_anomaly_pack import SELECTION_COLUMNS, write_csv
        selection = self.tmp / "go2432" / "anomaly" / "select" / "selection.csv"
        selection.parent.mkdir(parents=True, exist_ok=True)
        write_csv(selection, SELECTION_COLUMNS, [dict(zip(SELECTION_COLUMNS, row)) for row in rows])

    def pack_tree(self):
        """A small selection over the stores the records name, 16x16x8 NIfTIs: three VerSe release masks (an L6, a
        normal with a fold, a T13 that G3 holds on val), a COBRA test case and two harvest cases with SPINEPS masks,
        one of them the guard refuses and the other carrying metal; one holdout person with one scan; the registry
        in the clone; the selection under the route's root. Returns the home the VerSe and ctd stores hang from."""
        from tests.test_anomaly_pack import NORMAL, WITH_L6, WITH_T13, REGISTRY_COLUMNS, ct_file, mask_file, write_csv
        home = self.tmp / "home"
        unified = home / "VerSeFusion" / "data" / "unified"
        for case, ids in (("verse100", WITH_L6), ("verse200", NORMAL), ("verse300", WITH_T13), ("verse401", NORMAL), ("verse500", NORMAL)):
            ct_file(unified / f"scan-{case}" / f"scan-{case}_ct.nii.gz")
            mask_file(unified / f"scan-{case}" / f"scan-{case}_msk.nii.gz", ids)
        cobra = self.data / "cobra2026"
        ct_file(cobra / "lstv" / "nifti" / "B100_ct.nii.gz")
        mask_file(cobra / "lstv" / "seg" / "B100_seg-vert_msk.nii.gz", NORMAL)
        harvest = self.data / "anomaly_harvest" / "amos22"
        for case, ids, plant in (("amos_0001", NORMAL, ()), ("amos_0002", WITH_L6, ((80, 30),))):
            ct_file(self.data / "amos22" / "nifti" / f"{case}_ct.nii.gz")
            mask_file(harvest / "spineps" / f"{case}_seg-vert_msk.nii.gz", ids, plant=plant)
        self.write_selection(self.PACK_ROWS)
        registry = self.tmp / "ssn" / "SchwingNet" / "results" / "transitional_registry"
        registry.mkdir(parents=True, exist_ok=True)
        flags = {"verse:verse100": ("L6", "True"), "verse:verse200": ("none", "True"), "verse:verse300": ("T13", "True"),
                 "verse:verse400": ("L6", "True"), "verse:verse500": ("none", "True"), "cobra:B100": ("none", "True"),
                 "amos22:0001": ("none", "True"), "amos22:0002": ("L6", "True")}
        write_csv(registry / "registry.csv", REGISTRY_COLUMNS,
                  [{"patient_key": key, "subtype": subtype, "junction_ls_in_fov": ls} for key, (subtype, ls) in flags.items()])
        (self.repo / "data" / "splits" / "anomaly-holdout.json").write_text(json.dumps({
            "frozen": "test", "rule": {}, "inputs": {},
            "persons": [{"person": "verse:verse400", "variant": "L6", "release": "2019", "stratum": "L6", "scans": ["verse401"]}],
            "folds": [{"person": "verse:verse200", "fold": 1}], "disputed": []}), encoding="utf-8")
        return home

    def pack_fakes(self):
        """What the pack stage needs on the node, each a stand-in: the spineps conda and its guard, the packager's venv
        whose python records what it saw, and G3's person split holding the T13 person on val."""
        ssn, conda = self.spineps_fakes()
        guard = ssn / "tools" / "spineps_ids.py"
        guard.parent.mkdir(parents=True, exist_ok=True)
        guard.write_text(FAKE_SPINEPS_GUARD, encoding="utf-8")
        venv = self.tmp / "venv"
        (venv / "bin").mkdir(parents=True)
        (venv / "READY").write_text("fake\n", encoding="utf-8")
        (venv / "bin" / "python").write_text(FAKE_PACK_PYTHON, encoding="utf-8")
        (venv / "bin" / "python").chmod(0o755)
        g3 = self.tmp / "split_final.json"
        g3.write_text(json.dumps({"_format": "g3-person-split-v1", "side_of_person": {"verse:verse300": "val", "verse:verse100": "train"},
                                  "group_of": {}, "raw_to_group": {}, "item_side": {}}), encoding="utf-8")
        return ssn, conda, venv, g3

    def pack_job(self, ssn, conda, venv, g3, home, job="781", **extra):
        self.ceph_fake()
        env = self.gate_env()
        env.update(GETFATTR=str(self.fake / "getfattr"), LAB_VOLUME=str(self.tmp), SSN=str(ssn), CONDA_SH=str(conda),
                   SPINEPS_PYTHON=sys.executable, PACK_VENV=str(venv), G3_SPLIT=str(g3), PACK_HOME=str(home),
                   SCHWINGNET_NATIVE="1", STAGE="pack", SLURM_JOB_ID=job, PYDRV=sys.executable, **extra)
        return subprocess.run(["bash", str(self.repo / "grid" / "anomaly.sbatch")], cwd=self.repo / "grid", env=env,
                              capture_output=True, text=True, timeout=120)

    def pack_report(self):
        return (self.repo / "grid" / "logs" / "ANOMALY-pack.md").read_text(encoding="utf-8")

    def test_the_pack_stage_admits_before_it_writes_rewrites_packs_and_reports_counts_only(self):
        # anomaly.sbatch with STAGE=pack: the code copied and run from the copy with no HOLD, the rows, the guard in
        # the spineps environment, the packager's temp folder swept, the admission under the size rule before a
        # byte lands and settled at the end, the masks rewritten under the landing, the splits, the route check,
        # one package packed and the other empty, the projection check; counts and digests only in the report
        self.anomaly_tools_committed("anomaly_pack.py", "nifti_label.py", "anomaly_route.py")
        home = self.pack_tree()
        ssn, conda, venv, g3 = self.pack_fakes()
        landing = self.data / "flexray_pack"
        dead = landing / "schwingnet_spine" / "thunder_dbs" / ".v1.fxr-pack-dead"
        dead.mkdir(parents=True)
        (dead / "x").write_bytes(b"0" * 10)
        done = self.pack_job(ssn, conda, venv, g3, home)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("SN_ANOMALY_RC=0", done.stdout)
        report = self.pack_report()
        self.assertIn("# anomaly pack: job 781", report.splitlines()[0])
        for line in ("- selection: sha256 ", ", 6 rows", "- environment: flexray==1.0.2 h5py thunderpack nibabel",
                     "- test gate after the rows: 0 test/holdout rows unresolved or refused",
                     "- guard: 3 SPINEPS masks checked, 2 listed OK, 1 refused",
                     "- orphans: 1 folders, 10 bytes removed",
                     "- admission: flexray_pack: admitted; it needs 1 gb of its 1 gb by header census of 7 cts float16 image uint8 label and uint8 mask uncompressed and 8845 gb is free under the quota after 0 gb owed to 0 running fetches at ",
                     "- test gate after the masks: 0 test/holdout rows unresolved or refused",
                     "- route check: no held-out or disputed person",
                     "- package schwingnet_spine: packed in ", "- projection schwingnet_spine: ok",
                     "- package schwingnet_spine_partial: no sample, nothing packed",
                     "- pack: schwingnet_spine ", " bytes on disk; seconds: rewrite ",
                     "- rewritten 6 (release 4, spineps 2); kept 0 from an earlier run",
                     "- refused by the guard 1: none; veridah_skipped_name 1 apart",
                     "- dropped ids: 80 in 1 masks (30 voxels)",
                     "- countable 6, complete 6, partial 0, uncountable 0",
                     "- exit 0 at "):
            self.assertIn(line, report)
        self.assertNotIn("FAILED", report)
        self.assertNotIn("NOTE", report)
        for text in ("verse100", "verse401", "B100", "amos_0001", "amos_0002", str(self.tmp)):
            self.assertNotIn(text, report)
        self.assertLess(len(report.splitlines()), 200)
        # what the packager's python saw: no HOLD ever, no byte under the landing before the admission stood
        log = (self.fake / "fakepy.log").read_text(encoding="utf-8").splitlines()
        self.assertEqual(log[0], "c hold=no masks=no admission=none")
        self.assertIn("pack schwingnet_spine hold=no masks=yes admission=admitted", log)
        # the projection check, the last call, runs under the admission, which the stage settles after it
        self.assertEqual(log[-1], "c hold=no masks=yes admission=admitted")
        self.assertNotIn("check schwingnet_spine", log)
        self.assertFalse((self.repo / "grid" / "logs" / "HOLD").exists())
        self.assertTrue((landing / "meta" / "SIZE").read_text(encoding="utf-8").startswith("settled 781 "))
        self.assertFalse(dead.exists())
        self.assertTrue((landing / "schwingnet_spine" / "thunder_dbs" / "v1" / "MANIFEST.json").exists())
        self.assertFalse((landing / "schwingnet_spine_partial" / "thunder_dbs" / "v1").exists())
        self.assertEqual(sorted(path.name for path in (landing / "masks").glob("*.nii.gz")),
                         ["amos22__amos_0002.nii.gz", "cobra2026__B100.nii.gz", "verse__verse100.nii.gz", "verse__verse200.nii.gz",
                          "verse__verse300.nii.gz", "verse__verse401.nii.gz"])
        out = self.tmp / "go2432" / "anomaly" / "pack"
        manifest = out / "manifest-schwingnet_spine.yml"
        self.assertEqual((out / "packed-schwingnet_spine.sha256").read_text(encoding="utf-8").strip(),
                         hashlib.sha256(manifest.read_bytes()).hexdigest()[:16])
        self.assertFalse((out / "manifest-schwingnet_spine_partial.yml").exists())
        self.assertTrue((out / "landing").is_symlink())
        commit = subprocess.run(["git", "-C", str(self.repo), "rev-parse", "--short=7", "HEAD"], capture_output=True, text=True).stdout.strip()
        self.assertTrue((out / f"code-{commit}" / "tools" / "anomaly_pack.py").is_file())
        self.assertIn("conda activate spineps", (self.fake / "conda.log").read_text(encoding="utf-8"))
        splits = (out / "splits.csv").read_text(encoding="utf-8")
        self.assertIn("verse:verse300,verse300,g3_excluded", splits)
        self.assertIn("cobra:B100,B100,test", splits)
        self.assertIn("verse:verse400,verse401,holdout", splits)
        # a second run rewrites no mask and packs nothing: the masks are kept by their sidecars, the package by its digest
        done = self.pack_job(ssn, conda, venv, g3, home, job="782")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        report = self.pack_report()
        self.assertIn("- rewritten 0 (release 0, spineps 0); kept 6 from an earlier run", report)
        self.assertIn("- package schwingnet_spine: kept, manifest sha256 ", report)
        self.assertIn("- orphans: 0 folders, 0 bytes removed", report)
        log = (self.fake / "fakepy.log").read_text(encoding="utf-8").splitlines()
        self.assertEqual(log.count("pack schwingnet_spine hold=no masks=yes admission=admitted"), 1)
        self.assertIn("check schwingnet_spine", log)
        self.assertTrue((landing / "meta" / "SIZE").read_text(encoding="utf-8").startswith("settled 782 "))
        # a selection that grew changes the manifest: the old package is removed, with its bytes reported, and packed again
        self.write_selection(self.PACK_ROWS + (("verse:verse500", "verse", "verse500", "normal", "", "train", ""),))
        done = self.pack_job(ssn, conda, venv, g3, home, job="783")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        report = self.pack_report()
        self.assertIn(", 7 rows", report)
        self.assertIn("- rewritten 1 (release 1, spineps 0); kept 6 from an earlier run", report)
        self.assertIn("- package schwingnet_spine rebuilt: ", report)
        self.assertIn(" bytes removed", report)
        self.assertIn("- package schwingnet_spine: packed in ", report)

    def test_a_missing_test_mask_fails_the_pack_unless_allowed(self):
        # a test or holdout row that resolves to nothing stops the stage before the admission; one the guard refuses
        # stops it after the masks, its admission settled; ALLOW_PARTIAL_TEST=yes lets either go on, counted
        self.anomaly_tools_committed("anomaly_pack.py", "nifti_label.py", "anomaly_route.py")
        home = self.pack_tree()
        ssn, conda, venv, g3 = self.pack_fakes()
        mask = self.data / "cobra2026" / "lstv" / "seg" / "B100_seg-vert_msk.nii.gz"
        kept = mask.read_bytes()
        mask.unlink()
        done = self.pack_job(ssn, conda, venv, g3, home)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        report = self.pack_report()
        self.assertIn("- FAILED: 1 test/holdout rows cannot be packed after the rows (ALLOW_PARTIAL_TEST=yes lets the stage go on without them)", report)
        self.assertTrue(report.splitlines()[-1].startswith("- exit 1 at "))
        self.assertFalse((self.data / "flexray_pack").exists())
        # the packager's python saw the probe and nothing after it
        self.assertEqual((self.fake / "fakepy.log").read_text(encoding="utf-8").splitlines(), ["c hold=no masks=no admission=none"])
        done = self.pack_job(ssn, conda, venv, g3, home, job="782", ALLOW_PARTIAL_TEST="yes")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        report = self.pack_report()
        self.assertIn("- test gate after the rows: 1 test/holdout rows unresolved or refused, allowed (ALLOW_PARTIAL_TEST=yes)", report)
        self.assertIn("- exit 0 at ", report)
        mask.write_bytes(kept)
        (self.fake / "fakepy.log").unlink()
        done = self.pack_job(ssn, conda, venv, g3, home, job="783", FAKE_GUARD_FAIL="B100")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        report = self.pack_report()
        self.assertIn("- guard: 3 SPINEPS masks checked, 2 listed OK, 1 refused", report)
        self.assertIn("- FAILED: 1 test/holdout rows cannot be packed after the masks", report)
        self.assertTrue((self.data / "flexray_pack" / "meta" / "SIZE").read_text(encoding="utf-8").startswith("settled 783 "))
        self.assertNotIn("pack schwingnet_spine", (self.fake / "fakepy.log").read_text(encoding="utf-8"))

    def test_a_moved_checkout_is_a_note_for_a_stage_run_from_its_copy(self):
        # the pack stage runs from its copy of the code, so a checkout that moved under it (the packager's python
        # commits during the pack) is a note on a report that still ends in exit 0, where the other stages fail
        self.anomaly_tools_committed("anomaly_pack.py", "nifti_label.py", "anomaly_route.py")
        home = self.pack_tree()
        ssn, conda, venv, g3 = self.pack_fakes()
        (self.fake / "commit_during_pack").write_text("", encoding="utf-8")
        done = self.pack_job(ssn, conda, venv, g3, home)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        report = self.pack_report()
        self.assertIn("- NOTE: the checkout moved from ", report)
        self.assertIn("which ran from its own copy of the code at ", report)
        self.assertTrue(report.splitlines()[-1].startswith("- exit 0 at "))
        # and a packager that falls over fails the stage at the same commit, its admission settled
        (self.fake / "commit_during_pack").unlink()
        (self.fake / "pack_fails").write_text("", encoding="utf-8")
        self.write_selection(self.PACK_ROWS + (("verse:verse500", "verse", "verse500", "normal", "", "train", ""),))
        done = self.pack_job(ssn, conda, venv, g3, home, job="782")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        report = self.pack_report()
        self.assertIn("- FAILED: pack of schwingnet_spine exited 3 (1 log lines)", report)
        self.assertTrue((self.data / "flexray_pack" / "meta" / "SIZE").read_text(encoding="utf-8").startswith("settled 782 "))

    def bench_job(self, name, **extra):
        env = dict(os.environ, SCHWINGNET=str(self.repo), DATA_ROOT=str(self.data), LAB_VOLUME=str(self.tmp), FAKE=str(self.fake),
                   BENCH=name, SLURM_JOB_ID="778", **extra)
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

    DRR_GAP_PINS = "flexray[train]==1.0.2 nanodrr==0.1.5 scikit-learn==1.9.1 umap-learn==0.5.12 numpy==2.4.6"
    # Lines in the shapes tools/domain_gap.py's summary prints, the replication lines among them;
    # each must reach the report as it is, since the report is the one thing that leaves the grid.
    DRR_GAP_SUMMARY = (
        "drr gap: 3000 images, 17 groups, W&B off",
        "replication flexray_replica vs flexray_reference in flexray (invariant): replicated",
        "group fluxray synthetic skipped, nothing found under its rules",
        " replication flexray_replica vs flexray_reference auc 0.52 [0.48, 0.56] p 0.120 q 0.300 knn 0.51"
        " mmd p 0.400 q 0.500 fd64 1.2 kid64 0.001 prdc 0.90 0.90 1.00 0.90 replicated",
        " replication flexray_drr vs flexray_replica auc 0.71 [0.66, 0.75] p 0.001 q 0.002 knn 0.70"
        " mmd p 0.001 q 0.002 fd64 9.8 kid64 0.031 prdc 0.61 0.58 0.70 0.66 not replicated",
        " replication flexray_reference vs fluxray not tested, nothing found under its rules",
    )

    def drr_gap_inputs(self):
        """Every input bench flexray_drr_gap refuses without, FleXray's bundle, a whole sample index,
        the TotalSegmentator CTs and the ImageNet file, and the SPINEPS and MOOSE mask folders, which
        the study reads where they are there; the index's path comes back."""
        bundle = self.data / "hf_flexray_weights" / "raw"
        bundle.mkdir(parents=True, exist_ok=True)
        (bundle / "ensemble.json").write_text("{}\n", encoding="utf-8")
        run = self.data / "_samples" / "20261022-000000-abcd"
        run.mkdir(parents=True, exist_ok=True)
        (run / "samples.sqlite").write_bytes(b"")
        (self.data / "_samples" / "CURRENT").write_text(run.name + "\n", encoding="utf-8")
        (self.data / "totalsegmentator_v201" / "s0001").mkdir(parents=True, exist_ok=True)
        (self.data / "spineps").mkdir(exist_ok=True)
        (self.data / "moose").mkdir(exist_ok=True)
        self.weights_ready()
        return run / "samples.sqlite"

    DRR_GAP_NAMES = ("bench_flexray_drr_gap", "bench_flexray_drr_gap_shard", "bench_flexray_drr_gap_merge")

    def drr_gap_lines(self):
        """The newest submission of each of the study's three jobs, prepare, the shard array and the merge."""
        lines = self.submitted()
        return [[line for line in lines if f"--name {name} " in line][-1] for name in self.DRR_GAP_NAMES]

    def bench_root(self):
        return self.tmp / "go2432" / "bench"

    def test_bench_flexray_drr_gap_refuses_each_missing_input_then_queues_three_gpu_jobs_on_any_card(self):
        # the DRR domain-gap study (tools/domain_gap.py) is a bench id of its own: refused, naming one
        # input a send, until FleXray's weights, a whole sample index, the TotalSegmentator CTs and the
        # ImageNet file are on the volume; FluXray and both segmenters' masks are optional, each said
        # and never waited for, since a DRR is a projection of the CT alone (the owner's word of
        # 2026-10-27) and the study skips a group whose segmenter's masks are not there; then, by the
        # owner's word of 2026-10-27 17:51 UTC ("cancel and shard requesting h200"), three GPU jobs:
        # prepare, the shard array of 16 tasks afterany it and the merge afterany the array, on any card
        # of the gpu class since the owner's words of 2026-10-28 00:23 UTC ("shard it to more gpus like 16",
        # "drop the requirement for h200 unless its a memory problem")
        refused = self.gate("bench", "flexray_drr_gap")
        self.assertEqual(refused.returncode, 2, refused.stdout)
        self.assertIn("fetch hf_flexray_weights first", refused.stdout)
        bundle = self.data / "hf_flexray_weights" / "raw"
        bundle.mkdir(parents=True)
        (bundle / "ensemble.json").write_text("{}\n", encoding="utf-8")
        refused = self.gate("bench", "flexray_drr_gap")
        self.assertEqual(refused.returncode, 2, refused.stdout)
        self.assertIn("a whole sample index (the gate word samples makes it)", refused.stdout)
        run = self.data / "_samples" / "20261022-000000-abcd"
        run.mkdir(parents=True)
        (run / "samples.sqlite").write_bytes(b"")
        (self.data / "_samples" / "CURRENT").write_text(run.name + "\n", encoding="utf-8")
        refused = self.gate("bench", "flexray_drr_gap")
        self.assertEqual(refused.returncode, 2, refused.stdout)
        self.assertIn("totalsegmentator_v201", refused.stdout)
        (self.data / "totalsegmentator_v201" / "s0001").mkdir(parents=True)
        refused = self.gate("bench", "flexray_drr_gap")
        self.assertEqual(refused.returncode, 2, refused.stdout)
        self.assertIn("resnet18-f37072fd.pth", refused.stdout)
        self.assertNotIn("masks", refused.stdout)
        self.assertEqual(self.submitted(), [])
        self.weights_ready()
        self.environments_ready()
        # with no mask folder at all the word is taken and says each segmenter's masks are not there
        # and that the groups naming it are skipped
        done = self.gate("bench", "flexray_drr_gap")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("FluXray: not on the data root (fetch hf_flexray_data)", done.stdout)
        self.assertIn(f"  the SPINEPS masks: not at {self.data}/spineps; the render groups that name segmenter=spineps"
                      " are skipped with that reason\n", done.stdout)
        self.assertIn(f"  the MOOSE masks: not at {self.data}/moose (bench flexray_drr_seg makes them); the render groups"
                      " that name segmenter=moose are skipped with that reason\n", done.stdout)
        lines = self.submitted()
        self.assertEqual(len(lines), 3, lines)
        prepare, shards, merge = lines
        jobs = self.recorded()
        ids = [jobs[name] for name in self.DRR_GAP_NAMES]
        self.assertEqual(ids, ["101", "102", "103"])
        # each the gpu class with no partition, so whichever of its partitions frees first, never
        # requeued, run by grid/drr-gap.sbatch, the shards afterany prepare and the merge afterany the array
        self.assertTrue(prepare.startswith("--class gpu --name bench_flexray_drr_gap --cpus 16 --mem 64G"
                                           " --time 12:00:00 --no-requeue drr-gap.sbatch | "), prepare)
        self.assertTrue(shards.startswith("--class gpu --name bench_flexray_drr_gap_shard --dependency=afterany:101"
                                          " --kill-on-invalid-dep=yes --array 0-15 --cpus 16 --mem 64G"
                                          " --time 12:00:00 --no-requeue drr-gap.sbatch | "), shards)
        self.assertTrue(merge.startswith("--class gpu --name bench_flexray_drr_gap_merge --dependency=afterany:102"
                                         " --kill-on-invalid-dep=yes --cpus 4 --mem 64G"
                                         " --time 04:00:00 --no-requeue drr-gap.sbatch | "), merge)
        self.assertNotIn("--partition", " ".join(lines))
        index = run / "samples.sqlite"
        for line, step in zip(lines, ("prepare", "shard", "merge")):
            for value in ("BENCH=flexray_drr_gap", f"DATA_ROOT={self.data}", f"INDEX={index}", f"MODELS={self.models}",
                          f"BENCH_ROOT={self.bench_root()}", f"DRR_GAP_OUT={self.bench_root() / self.drr_gap_folder()}",
                          f"STEP={step}"):
                self.assertIn(f" {value} ", line + " ")
            self.assertNotIn("bench.sbatch", line)
        self.assertIn(" PREPARE_JOB= ", prepare + " ")
        self.assertIn(" PREPARE_JOB=101 ", shards + " ")
        self.assertIn(" PREPARE_JOB=101 SHARD_TASKS=16 ", merge + " ")
        self.assertIn("  the study: prepare 101, then the shard array 102 (16 tasks, afterany 101), then the merge 103"
                      " (afterany 102), each on the first card of the gpu class that frees\n", done.stdout)
        # all three under the word's own record, so cancel takes them together
        state = (self.repo / "grid" / "logs" / "GATE_JOBS.txt").read_text(encoding="utf-8").splitlines()
        self.assertEqual([line.split()[:3] for line in state],
                         [[job, "bench:flexray_drr_gap", name] for job, name in zip(ids, self.DRR_GAP_NAMES)])
        # once FluXray is fetched the send says nothing of it, a mask folder that is there is said to
        # be read, and the other bench ids are as they were
        (self.data / "hf_flexray_data" / "raw").mkdir(parents=True)
        (self.data / "spineps").mkdir()
        (self.data / "moose").mkdir()
        done = self.gate("bench", "flexray_drr_gap")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertNotIn("FluXray", done.stdout)
        self.assertIn(f"  the SPINEPS masks: in {self.data}/spineps, {READ_WHERE}\n", done.stdout)
        self.assertIn(f"  the MOOSE masks: in {self.data}/moose, {READ_WHERE}\n", done.stdout)
        self.assertNotIn("skipped", done.stdout)
        self.assertEqual(len(self.submitted()), 6)
        self.assertEqual(self.gate("bench", "fluorosam").returncode, 64)
        refused = self.gate("bench", "flexray_deepfluoro")
        self.assertEqual(refused.returncode, 2, refused.stdout)
        self.assertIn("DeepFluoro's .h5", refused.stdout)

    def test_bench_flexray_drr_gap_waits_for_a_live_segment_job_and_reads_its_masks(self):
        # bench flexray_drr_seg writes the MOOSE masks under the data root's moose and holds the
        # checkout while it runs, so the study's prepare sent meanwhile is queued afterany on it, as on
        # every run that holds the checkout, and reads MOOSE's masks once that job has written them:
        # nothing is left out for it, the shards and the merge wait only on the step before them, and
        # a live fetch changes nothing either
        self.drr_gap_inputs()
        self.environments_ready()
        self.state_line(4242, "bench:flexray_drr_seg", "bench_flexray_drr_seg")
        self.live(4242)
        done = self.gate("bench", "flexray_drr_gap")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn(f"  the SPINEPS masks: in {self.data}/spineps, {READ_WHERE}\n", done.stdout)
        self.assertIn(f"  the MOOSE masks: in {self.data}/moose, {READ_WHERE}\n", done.stdout)
        self.assertNotIn("left out", done.stdout)
        prepare, shards, merge = self.drr_gap_lines()
        self.assertIn("--dependency=afterany:4242 ", prepare)
        self.assertIn("--dependency=afterany:101 ", shards)
        self.assertIn("--dependency=afterany:102 ", merge)
        self.assertNotIn("4242", shards + merge)
        self.assertNotIn("BENCH_SKIP_MASKS", prepare)
        self.state_line(4343, "fetch:moose_weights", "dp_moose_weights")
        self.live(4343)
        done = self.gate("bench", "flexray_drr_gap")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn(f"  the MOOSE masks: in {self.data}/moose, {READ_WHERE}\n", done.stdout)
        self.assertNotIn("left out", done.stdout)

    def test_a_refused_later_step_of_the_study_cancels_the_ones_queued_before_it(self):
        # all three or none, as grid/run-leaks.sh queues its array and join: a prepare whose shards
        # were refused would cut units nobody claims, and shards with no merge would leave no report
        self.drr_gap_inputs()
        self.environments_ready()
        (self.fake / "refuse").write_text("--name bench_flexray_drr_gap_merge ", encoding="utf-8")
        done = self.gate("bench", "flexray_drr_gap")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertEqual(sorted((self.fake / "scancel.log").read_text(encoding="utf-8").split()), ["101", "102"])
        self.assertIn("  cancelled prepare 101 and the shard array 102, since the merge was refused\n", done.stdout)
        (self.fake / "scancel.log").unlink()
        (self.fake / "refuse").write_text("--name bench_flexray_drr_gap_shard ", encoding="utf-8")
        done = self.gate("bench", "flexray_drr_gap")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertEqual((self.fake / "scancel.log").read_text(encoding="utf-8").split(), ["103"])
        self.assertIn("  cancelled prepare 103, since its shard array was refused\n", done.stdout)
        self.assertEqual([line for line in self.submitted() if "bench_flexray_drr_gap_merge" in line], [])
        self.assertNotIn("the study: prepare", done.stdout)

    def drr_gap_folder(self):
        """The study's folder under BENCH_ROOT, the committed DRR_GAP_FOLDER of grid/gate.sh: a run
        in a folder of its own computes everything again, and the folder before it is left as it was."""
        lines = (GRID / "gate.sh").read_text(encoding="utf-8").splitlines()
        return [line.split("=", 1)[1] for line in lines if line.startswith("DRR_GAP_FOLDER=")][0]

    def drr_gap_progress_file(self, lines):
        folder = self.bench_root() / self.drr_gap_folder()
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "PROGRESS.txt").write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")

    def test_bench_flexray_drr_gap_refuses_while_any_of_its_jobs_is_live_and_prints_its_progress(self):
        # the study is still running while any of its three jobs is queued or running, so a send then
        # prints what it has done so far, its PROGRESS.txt masked and cut to 60 lines (the tool's own
        # bound, the run log's newest lines last among them), and refuses
        self.drr_gap_inputs()
        self.environments_ready()
        token = "hf_" + "Ef" * 17
        self.drr_gap_progress_file(["prepare: done, 120 units in 6 heads", f"shard 1: claimed 4 units, token {token}"]
                                   + [f"unit {n:03d} done" for n in range(70)])
        for job, name in zip((501, 502, 503), self.DRR_GAP_NAMES):
            self.state_line(job, "bench:flexray_drr_gap", name)
        for job in (501, 502, 503):
            self.live(job, 99999)
            done = self.gate("bench", "flexray_drr_gap")
            self.assertEqual(done.returncode, 75, done.stdout)
            self.assertIn(f"refusing: the benchmark flexray_drr_gap is still queued or running (jobs {job}); send bench"
                          " flexray_drr_gap again once its merge ends\n", done.stdout)
            self.assertIn(f"## bench {self.drr_gap_folder()}, progress (", done.stdout)
            self.assertIn("  prepare: done, 120 units in 6 heads\n  shard 1: claimed 4 units, token <withheld>\n", done.stdout)
            self.assertIn("  unit 057 done\n", done.stdout)
            self.assertNotIn("unit 058", done.stdout)
            self.assertNotIn(token, done.stdout)
            self.assertLess(done.stdout.index(f"## bench {self.drr_gap_folder()}, progress"), done.stdout.index("refusing:"))
        self.live(501, 503)
        done = self.gate("bench", "flexray_drr_gap")
        self.assertEqual(done.returncode, 75, done.stdout)
        self.assertIn("(jobs 501 503)", done.stdout)
        (self.bench_root() / self.drr_gap_folder() / "PROGRESS.txt").unlink()
        done = self.gate("bench", "flexray_drr_gap")
        self.assertEqual(done.returncode, 75, done.stdout)
        self.assertIn(f"  the study has written no PROGRESS.txt yet in {self.drr_gap_folder()}: prepare starts it once it runs\n",
                      done.stdout)
        self.assertEqual(self.submitted(), [])

    def test_cancel_takes_the_studys_three_jobs_together_and_nothing_else(self):
        self.drr_gap_inputs()
        self.environments_ready()
        # the one job of the study before it was sharded, ended, and another word's live job
        self.state_line(40802322, "bench:flexray_drr_gap", "bench_flexray_drr_gap")
        self.state_line(4242, "bench:flexray_drr_seg", "bench_flexray_drr_seg")
        self.assertEqual(self.gate("bench", "flexray_drr_gap").returncode, 0)
        self.live(101, 102, 103, 4242, 99999)
        done = self.gate("cancel", "102")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertEqual(sorted((self.fake / "scancel.log").read_text(encoding="utf-8").split()), ["101", "102", "103"])
        self.assertIn("cancelled (bench:flexray_drr_gap): 101 102 103", done.stdout)

    def test_status_shows_each_benchmarks_progress_after_the_space_and_before_the_jobs(self):
        # the study's PROGRESS.txt is its live view from outside the grid: status shows it as a
        # section of its own, its first 60 lines masked, handed room at the sweeps' rank
        token = "hf_" + "Gh" * 17
        self.drr_gap_progress_file(["prepare: done, 120 units in 6 heads", f"shard 0: unit 7 failed, token {token}"]
                                   + [f"unit {n:03d} done" for n in range(70)])
        # an earlier run's folder keeps its last PROGRESS.txt, which is no live view
        self.assertNotEqual(self.drr_gap_folder(), "flexray_drr_gap")
        earlier = self.bench_root() / "flexray_drr_gap"
        earlier.mkdir(parents=True)
        (earlier / "PROGRESS.txt").write_text("run 2's last words\n", encoding="utf-8")
        odd = self.bench_root() / "Not-A-Bench"
        odd.mkdir(parents=True)
        (odd / "PROGRESS.txt").write_text("odd folder\n", encoding="utf-8")
        (self.bench_root() / "flexray_carmlspine").mkdir()
        done = self.gate("status")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        out = done.stdout
        shown = f"## bench {self.drr_gap_folder()}, progress"
        self.assertIn(shown + " (", out)
        self.assertNotIn("run 2's last words", out)
        self.assertNotIn("## bench flexray_drr_gap, progress", out)
        self.assertIn("  prepare: done, 120 units in 6 heads\n  shard 0: unit 7 failed, token <withheld>\n", out)
        self.assertIn("  unit 057 done\n", out)
        self.assertNotIn("unit 058", out)
        self.assertNotIn(token, out)
        self.assertNotIn("odd folder", out)
        self.assertNotIn("bench flexray_carmlspine", out)
        self.assertLess(out.index("## space on the lab volume"), out.index(shown))
        self.assertLess(out.index(shown), out.index("no job submitted by the gate yet"))
        self.assertNotIn("not shown, for want of room", out)

    def flow_root(self):
        return self.tmp / "go2432" / "metaflow"

    def flow_run(self, run, lines, kind="sweep", state="running"):
        """A launched flow's progress folder with its PROGRESS.txt as flows/stage_progress.py writes it,
        updated now, as a live run's is."""
        folder = self.flow_root() / "progress" / "SweepFlow" / run
        folder.mkdir(parents=True, exist_ok=True)
        updated = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        head = f"flow SweepFlow/{run} {kind}: {state}, started 2026-10-29 03:00:00 UTC, updated {updated} UTC"
        (folder / "PROGRESS.txt").write_text("\n".join([head, *lines]) + "\n", encoding="utf-8")
        return folder / "PROGRESS.txt"

    def test_status_shows_the_newest_launched_flows_progress_its_quotes_judged_as_a_reports(self):
        # the owner's rule of 2026-10-29: every launched flow keeps a progress page; status shows the
        # newest runs' short lines under a heading tools/progress_page.py reads back into the page
        # each file moved within the last few minutes, so none is judged silent
        moved = int(time.time()) - 200
        for n in range(6):
            progress = self.flow_run(f"17929025852864{n:02d}", ["run: key 68974c7ccabf5595, commit 35a4b6f"])
            os.utime(progress, (moved + n, moved + n))
        # the lines in the order flows/stage_progress.py writes them, how the run ended first; a file
        # longer than FLOW_PROGRESS_LINES, which the writer never makes, is cut there all the same
        newest = self.flow_run("1792902585286499", [
            "run: key 68974c7ccabf5595, commit 35a4b6f, code 0123456789ab, PREREG docs/research/block-smoke/PREREG.md sha256 5779e79a2a7c",
            "verdict: 1",
            "ended: the launcher exited 1, the flow succeeded",
            "reports: 0 of 1 current, 1 not current or not written",
            "report: resnet34-32px-b2928840: NOT CURRENT, why: REPORT.md not what the run gives for Doe_John/IM0007.dcm",
            "step start: done",
            f"task start prepare: done; state {self.smoke}/real/1a2b3c4d-5e6f7a8b, 20 rows first, 2 warm starts after",
            "step first: running; 1 done, 1 failed of 2",
            "task first resnet18-64px-3d291b87: failed; fault, why: SweepFault: block_sweep row exited 2: no frame case134_19650312.png",
            "task first resnet34-32px-b2928840: done; Outcome: ran, matched the check."] + [f"task first row{n}: done" for n in range(60)])
        os.utime(newest, (moved + 100, moved + 100))
        odd = self.flow_root() / "progress" / "SweepFlow" / "not a run"
        odd.mkdir(parents=True)
        (odd / "PROGRESS.txt").write_text("flow SweepFlow/x sweep: running\n", encoding="utf-8")
        os.utime(odd / "PROGRESS.txt", (moved - 100, moved - 100))
        done = self.gate("status")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        out = done.stdout
        self.assertEqual(out.count("## flow sweep "), 4, out)
        self.assertRegex(out, r"## flow sweep 1792902585286499, progress \(\d{4}-\d\d-\d\d \d\d:\d\d UTC\)\n  flow SweepFlow/1792902585286499 sweep: running, ")
        self.assertLess(out.index("## flow sweep 1792902585286499"), out.index("## flow sweep 1792902585286405"))
        self.assertNotIn("## flow sweep 1792902585286401", out)
        self.assertIn("  run: key 68974c7ccabf5595, commit 35a4b6f, code 0123456789ab, PREREG docs/research/block-smoke/PREREG.md sha256 5779e79a2a7c\n", out)
        self.assertIn("  task start prepare: done; state <path>, 20 rows first, 2 warm starts after\n", out)
        self.assertIn("  task first resnet18-64px-3d291b87: failed; fault, why: <reason withheld: it can quote a value; the whole report stays on the grid>\n", out)
        self.assertIn("  report: resnet34-32px-b2928840: NOT CURRENT, why: <reason withheld", out)
        self.assertIn("  verdict: 1\n  ended: the launcher exited 1, the flow succeeded\n  reports: 0 of 1 current, 1 not current or not written\n", out)
        # at most the first FLOW_PROGRESS_LINES lines of the file, 40, its head among them
        self.assertIn("  task first row28: done\n", out)
        self.assertNotIn("row29", out)
        for value in ("case134", "19650312", "Doe_John", "not a run"):
            self.assertNotIn(value, out)
        self.assertLess(out.index("## space on the lab volume"), out.index("## flow sweep"))
        self.assertLess(out.index("## flow sweep"), out.index("no job submitted by the gate yet"))

    def test_status_shows_how_a_whole_plans_run_ended_as_the_flows_own_writer_lays_it_out(self):
        # a smoke plan of 27 rows drawn by flows/stage_progress.py itself: the verdict, how the
        # launcher saw the flow end and the report not current all come inside the lines status keeps
        progress = load_module(ROOT / "flows" / "stage_progress.py", "stage_progress_for_the_gate")
        flow, run = "SweepFlow", "1792902585286456"
        progress.write_head(self.flow_root(), {"flow": flow, "run": run, "kind": "sweep", "key": "0" * 16, "started": progress.utc_now()})
        progress.write_graph(self.flow_root(), flow, run, ["start", "fan_first", "first", "join_first", "middle", "fan_second", "second",
                                                         "join_second", "end"])
        rows = [("first", f"row{n:02d}") for n in range(25)] + [("second", "warm0"), ("second", "warm1")]
        for number, (step, label) in enumerate(rows, 10):
            progress.write_task(self.flow_root(), flow, run, {"step": step, "task": str(number), "label": label, "state": "done",
                                                            "lines": ["Outcome: ran, matched the check."]})
        progress.write_result(self.flow_root(), flow, run, {
            "verdict": 1, "reports": 27, "not_current": 1,
            "lines": ["row03: NOT CURRENT as the run wrote it, so written anew; why: claim.json not what the run gives for Doe_John"]
                     + [f"{label}: current as the run wrote it" for _, label in rows if label != "row03"]})
        progress.write_launch(self.flow_root(), flow, run, {"words": "the launcher exited 1, the flow succeeded"})
        progress.draw(self.flow_root(), flow, run)
        done = self.gate("status")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        section = done.stdout.split(f"## flow sweep {run}, progress (", 1)[1].split("\n## ", 1)[0]
        self.assertIn("\n  verdict: 1\n  ended: the launcher exited 1, the flow succeeded\n"
                      "  reports: 26 of 27 current, 1 not current or not written\n"
                      "  report: row03: NOT CURRENT as the run wrote it, so written anew; why: <reason withheld", section)
        self.assertIn("  step first: done; 25 done of 25\n", section)
        self.assertIn("  step end: waiting\n", section)
        self.assertNotIn("Doe_John", done.stdout)

    def test_status_shows_a_running_run_whose_file_has_not_moved_for_ten_minutes_as_silent(self):
        # a job Slurm killed draws nothing more, so its file still says running: status judges it by
        # the file's age as it prints it, and says so in a line tools/progress_page.py reads back
        long_ago = int(time.time()) - 25 * 60
        dead = self.flow_run("1792902585286401", ["run: key 68974c7ccabf5595"] + [f"task first row{n}: done" for n in range(60)])
        os.utime(dead, (long_ago, long_ago))
        ended = self.flow_run("1792902585286402", ["run: key 68974c7ccabf5595", "verdict: 0"], state="succeeded")
        os.utime(ended, (long_ago - 1, long_ago - 1))
        live = self.flow_run("1792902585286403", ["run: key 68974c7ccabf5595"])
        done = self.gate("status")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        out = done.stdout
        dead_section = out.split("## flow sweep 1792902585286401, progress (", 1)[1].split("\n## ", 1)[0].splitlines()[1:]
        self.assertRegex(dead_section[0], r"^  flow SweepFlow/1792902585286401 sweep: silent, started ")
        self.assertRegex(dead_section[1], r"^  silent: no file of this run has moved for 2[56] minutes by this status; ")
        self.assertEqual(dead_section[2], "  run: key 68974c7ccabf5595")
        self.assertEqual(len(dead_section), 40, "the line status adds keeps the run inside the lines it shows")
        self.assertIn("  flow SweepFlow/1792902585286402 sweep: succeeded, started ", out)
        self.assertIn("  flow SweepFlow/1792902585286403 sweep: running, started ", out)
        self.assertEqual(out.count("  silent: "), 1, out)
        answer, page = self.tmp / "status.txt", self.tmp / "page.html"
        answer.write_text(out, encoding="utf-8")
        drawn = subprocess.run([sys.executable, str(ROOT / "tools" / "progress_page.py"), str(answer), "--run", "1792902585286401",
                                "--out", str(page)], capture_output=True, text=True, timeout=60)
        self.assertEqual(drawn.returncode, 0, drawn.stderr)
        html = page.read_text(encoding="utf-8")
        self.assertIn('<span class="badge silent">silent</span>', html)
        self.assertIn('<p class="silent">no file of this run has moved for ', html)

    def test_the_status_answer_draws_the_flows_page_off_the_grid(self):
        self.flow_run("1792902585286499", ["run: key 68974c7ccabf5595, commit 35a4b6f", "step start: done", "step first: running; 1 done, 1 running of 2",
                                           "task first resnet18-64px-3d291b87: running; Last epoch: epoch 1 of 2."])
        done = self.gate("status")
        answer, page = self.tmp / "status.txt", self.tmp / "page.html"
        answer.write_text(done.stdout, encoding="utf-8")
        drawn = subprocess.run([sys.executable, str(ROOT / "tools" / "progress_page.py"), str(answer), "--out", str(page)],
                               capture_output=True, text=True, timeout=60)
        self.assertEqual(drawn.returncode, 0, drawn.stderr)
        html = page.read_text(encoding="utf-8")
        self.assertIn("SweepFlow 1792902585286499", html)
        self.assertIn("Last epoch: epoch 1 of 2.", html)
        self.assertIn('<span class="badge running">running</span>', html)

    def kind_run(self, flow, kind, run, lines, moved, state="running"):
        """A run of any kind's progress folder, its PROGRESS.txt as flows/stage_progress.py writes it,
        updated and last moved at MOVED, seconds since the epoch."""
        folder = self.flow_root() / "progress" / flow / run
        folder.mkdir(parents=True, exist_ok=True)
        updated = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(moved))
        head = f"flow {flow}/{run} {kind}: {state}, started 2026-10-29 03:00:00 UTC, updated {updated} UTC"
        (folder / "PROGRESS.txt").write_text("\n".join([head, *lines]) + "\n", encoding="utf-8")
        os.utime(folder / "PROGRESS.txt", (moved, moved))
        return folder / "PROGRESS.txt"

    def flow_heads(self, out):
        return [line.split(", progress")[0] for line in out.splitlines() if line.startswith("## flow ") and ", progress (" in line]

    def test_status_keeps_each_kinds_newest_run_beside_the_drr_studys_eighteen(self):
        # one chain of the DRR domain-gap study starts 18 runs (prepare, 16 shard tasks, the merge), all
        # newer than the sweep that ran before it: status shows the newest run of every kind first, then
        # the newest of the rest up to four in all, newest first, so the sweep's run is never pushed out
        moved = int(time.time()) - 300
        self.kind_run("SweepFlow", "sweep", "1792902585286401", ["run: key 68974c7ccabf5595, commit 35a4b6f"], moved - 100)
        for n in range(18):
            self.kind_run("DrrGapFlow", "drr_gap", f"18000000000000{n:02d}", ["task work shard: running; unit 3 of 40"], moved + n)
        done = self.gate("status")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.flow_heads(done.stdout), ["## flow drr_gap 1800000000000017", "## flow drr_gap 1800000000000016",
                                                        "## flow drr_gap 1800000000000015", "## flow sweep 1792902585286401"])
        self.assertIn("  flow DrrGapFlow/1800000000000017 drr_gap: running, ", done.stdout)
        self.assertNotIn("## flow kinds not shown", done.stdout)

    def test_status_shows_four_flow_runs_however_many_kinds_have_run_and_names_the_rest_in_a_line_each(self):
        # every kind that has ever run keeps its folder, so the newest run of each kind is shown only
        # up to four in all, the kinds that moved last first; each further kind is one line, its run,
        # its state and when it last moved, under a heading the page hands room after the job list
        moved = int(time.time()) - 3000
        kinds = ("bank", "catalog", "sweep", "drr_seg", "drr_gap", "v1", "latency")
        for n, kind in enumerate(kinds):
            flow = kind.title().replace("_", "") + "Flow"
            for k in range(3):
                self.kind_run(flow, kind, f"1800000000{n:02d}00{k:02d}", [f"step start: done; run {k}"] + [f"task work row{r}: done" for r in range(60)],
                              moved + 100 * n + k, state="succeeded" if k < 2 else "running")
        done = self.gate("status")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        out = done.stdout
        self.assertEqual(self.flow_heads(out), ["## flow latency 1800000000060002", "## flow v1 1800000000050002",
                                                "## flow drr_gap 1800000000040002", "## flow drr_seg 1800000000030002"])
        section = out.split("## flow kinds not shown, for want of room among the newest 4: ", 1)[1].splitlines()[1:]
        left = section[:next((n for n, line in enumerate(section) if not line.startswith("  ")), len(section))]
        self.assertEqual([line.split(" (")[0] for line in left], ["  sweep 1800000000020002: running", "  catalog 1800000000010002: running",
                                                                 "  bank 1800000000000002: running"])
        for line in left:
            self.assertRegex(line, r"^  .* \(\d{4}-\d\d-\d\d \d\d:\d\d UTC\)$")
        # the job list keeps its room on the page, before the line of each kind left out
        self.assertIn("no job submitted by the gate yet", out)
        self.assertLess(out.index("## flow drr_seg"), out.index("## flow kinds not shown"))
        self.assertNotIn("not shown, for want of room on the page", out)
        # the page drawn off the grid reads the four runs' sections and ends each at the next heading
        answer = self.tmp / "status.txt"
        answer.write_text(out, encoding="utf-8")
        listed = subprocess.run([sys.executable, str(ROOT / "tools" / "progress_page.py"), str(answer), "--list"],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertEqual([line.split(" ")[:2] for line in listed.stdout.splitlines()],
                         [["1800000000060002", "latency"], ["1800000000050002", "v1"], ["1800000000040002", "drr_gap"],
                          ["1800000000030002", "drr_seg"]])

    # flows/launch.py as the stand-in box.sh plays it for the study's two kinds: the call logged with the
    # code it runs from and the checkout, refused where $FAKE/launch_refuse holds a word, a resume whose
    # finished step Metaflow cloned where $FAKE/launch_cloned is there (exit 0, no body), else the job
    # script's body run as DrrGapFlow's or DrrSegFlow's step runs it, with the words the flow gives it,
    # Slurm's TERM passed on, and the launcher's last line; after a body that ended 0, a flow whose end
    # fails with the code $FAKE/launch_after holds, or one still in its end where $FAKE/launch_hang is
    # there, until Slurm's TERM ends it; the flows' own tests run the real ones.
    FAKE_LAUNCHER = (
        'case "$*" in *"flows/launch.py drr_gap "*|*"flows/launch.py drr_seg "*)\n'
        '  said="$*"; said=${said#*flows/launch.py }\n'
        '  echo "$said | code=${SCHWINGNET:-} checkout=${SN_CHECKOUT:-}" >> "$FAKE/launch.log"\n'
        '  kind=${said%% *}\n'
        '  [ ! -f "$FAKE/launch_refuse" ] || { echo "launch: $(cat "$FAKE/launch_refuse")"; echo "${kind^^}_RC=90 0s"; exit 90; }\n'
        '  [ ! -f "$FAKE/launch_cloned" ] || { echo "${kind^^}_RC=0 0s"; exit 0; }\n'
        '  part=""; prep=""; out=""; task=0; tasks=1\n'
        '  while [ $# -gt 0 ]; do case "$1" in --part) part=$2 ;; --prepare-job) prep=$2 ;; --out) out=$2 ;;'
        ' --task) task=$2 ;; --tasks) tasks=$2 ;; esac; shift; done\n'
        '  if [ "$kind" = drr_seg ]; then words=(SCHWINGNET_FLOW_STEP=1); script=drr-seg.sbatch\n'
        '  else words=(SCHWINGNET_FLOW_STEP=1 STEP="$part" PREPARE_JOB="$prep" DRR_GAP_OUT="$out"); script=drr-gap.sbatch\n'
        '    case "$part" in shard) words+=(DRR_GAP_TASK="$task" DRR_GAP_TASK_COUNT="$tasks") ;;\n'
        '      merge) words+=(SHARD_TASKS="$tasks" SN_STUDY_RECORD="$out/runs/$prep") ;; esac\n'
        '  fi\n'
        '  env "${words[@]}" bash "$SCHWINGNET/grid/$script" & body=$!\n'
        '  trap \'kill -TERM "$body" 2>/dev/null\' TERM\n'
        '  while :; do wait "$body"; rc=$?; kill -0 "$body" 2>/dev/null || break; done\n'
        '  if [ "$rc" = 0 ] && [ -f "$FAKE/launch_hang" ]; then\n'
        '    sleep 30 > /dev/null 2>&1 & end=$!\n'
        '    trap \'kill "$end" 2>/dev/null; echo "${kind^^}_RC=143 1s"; exit 143\' TERM\n'
        '    echo hung > "$FAKE/launch_hung"; wait "$end"\n'
        '  fi\n'
        '  [ "$rc" != 0 ] || [ ! -f "$FAKE/launch_after" ] || rc=$(cat "$FAKE/launch_after")\n'
        '  echo "${kind^^}_RC=$rc 1s"; exit "$rc" ;;\n'
        'esac\n')

    def drr_gap_box(self):
        """A stand-in box.sh for the study's steps: every call logged with whether the checkout was held,
        the threads each worker may take and the scratch folder; prepare marks the analysis prepared
        (or fails where $FAKE/fail holds a token) and says a line that names files, a shard says what
        it claimed (or fails where $FAKE/shard_fail holds one), the merge writes the summary (or finds
        units not done where $FAKE/merge_fail is there) and the summary prints what the merge wrote;
        grid/venv.sh's python -m venv makes its folder, so venv_for marks the environment READY."""
        (self.fake / "summary").write_text("\n".join(self.DRR_GAP_SUMMARY) + "\n", encoding="utf-8")
        (self.fake / "gpu").write_text("NVIDIA H200, 143771 MiB, 550.54.15\n", encoding="utf-8")
        (self.fake / "nvidia-smi").write_text('#!/bin/bash\n[ ! -f "$FAKE/gpu" ] || cat "$FAKE/gpu"\n', encoding="utf-8")
        (self.fake / "nvidia-smi").chmod(0o755)
        (self.repo / "grid" / "box.sh").write_text(
            '#!/bin/bash\nhold=no; [ ! -e "${SN_CHECKOUT:-$SCHWINGNET}/grid/logs/HOLD" ] || hold=yes\n'
            'echo "$* | hold=$hold omp=${OMP_NUM_THREADS:-} tmp=${TMPDIR:-}" >> "$FAKE/box.log"\n'
            + self.FAKE_LAUNCHER +
            'case "$*" in *" -m venv "*) mkdir -p "${@: -1}"; exit 0 ;; esac\n'
            'case "$*" in *"domain_gap.py prepare "*) word=prepare ;; *"domain_gap.py shard "*) word=shard ;;\n'
            '  *"domain_gap.py merge "*) word=merge ;; *"domain_gap.py summary "*) word=summary ;;\n'
            '  *"domain_gap.py runlog "*) word=runlog ;; *) exit 0 ;; esac\n'
            'echo "$word ${SN_GIT_HEAD:-} ${SN_GIT_DIRTY:-} ${SN_PINS:-}" >> "$FAKE/record.log"\n'
            '[ -d "${TMPDIR:-/nowhere}" ] || { echo "no scratch folder"; exit 9; }\n'
            'out=""; while [ $# -gt 0 ]; do [ "$1" = --out ] && out=$2; shift; done\n'
            'case "$word" in\n'
            '  prepare)\n'
            '    echo "plan: $out/plan.json names files"\n'
            '    [ ! -f "$FAKE/fail" ] || { echo "drr-gap FAILED: no image decoded, token $(cat "$FAKE/fail")"; exit 2; }\n'
            '    mkdir -p "$out/analysis/runlog" && echo \'{"units": 3}\' > "$out/analysis/PREPARED.json"\n'
            '    kept=""; [ ! -f "$FAKE/kept" ] || kept="; $(cat "$FAKE/kept") of them an earlier chain left done, which count as done"\n'
            '    echo "1.000 prepare: 3 units listed over 2 readings (0 not read), so the array\'s tasks claim them$kept"'
            ' > "$out/analysis/runlog/prepare.txt" ;;\n'
            '  shard)\n'
            '    if [ -f "$FAKE/shard_sleep" ]; then\n'
            '      trap \'echo "the tool saw TERM" >> "$FAKE/term.log"; exit 143\' TERM\n'
            '      echo started > "$FAKE/shard_started"; sleep 30 & wait $!\n'
            '    fi\n'
            '    echo "shard: claimed 1 unit of $out/analysis/units.json"\n'
            '    [ ! -f "$FAKE/shard_fail" ] || { echo "drr-gap FAILED: three units in a row failed, token $(cat "$FAKE/shard_fail")"; exit 3; } ;;\n'
            '  merge)\n'
            '    [ ! -f "$FAKE/merge_fail" ] || { echo "drr-gap FAILED: 1 of 3 units not done"; exit 2; }\n'
            '    cp "$FAKE/summary" "$out/summary.txt" ;;\n'
            '  summary) cat "$out/summary.txt" ;;\n'
            '  runlog) [ ! -f "$FAKE/runlog" ] || cat "$FAKE/runlog" ;;\n'
            'esac\n', encoding="utf-8")

    def drr_gap_repo(self, prereg=b"# PREREG\n\nfrozen 2026-10-27, no further edits\n"):
        """The study's code committed as prepare copies it: the stand-in box.sh, stand-ins for the tool,
        the packages it imports, the launcher and the report's inputs, the groups and the frozen split,
        the job script itself, and PREREG.md frozen with its hash; the commit, whole."""
        self.drr_gap_box()
        self.git_repo()
        (self.repo / "tools" / "domain_gap.py").write_text("# the study's tool; grid/box.sh stands in for it\n", encoding="utf-8")
        (self.repo / "flows").mkdir()
        (self.repo / "flows" / "launch.py").write_text("# the launcher; grid/box.sh stands in for it\n", encoding="utf-8")
        (self.repo / "pixi.toml").write_text("[workspace]\n", encoding="utf-8")
        (self.repo / "data" / "reporting").mkdir(parents=True)
        (self.repo / "data" / "reporting" / "claim.json").write_text("{}\n", encoding="utf-8")
        (self.repo / "data" / "licences.json").write_text("{}\n", encoding="utf-8")
        (self.repo / "src" / "schwingnet").mkdir(parents=True)
        (self.repo / "src" / "schwingnet" / "__init__.py").write_text("", encoding="utf-8")
        (self.repo / "vendor").mkdir()
        (self.repo / "vendor" / "README.md").write_text("vendored\n", encoding="utf-8")
        (self.repo / "data" / "domain_gap").mkdir(parents=True)
        (self.repo / "data" / "domain_gap" / "groups.json").write_text("{}\n", encoding="utf-8")
        self.freeze(prereg)
        return self.commit_all("the study's code")

    def freeze(self, prereg, hashed=None):
        folder = self.repo / "docs" / "research" / "drr-domain-gap"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "PREREG.md").write_bytes(prereg)
        (folder / "PREREG.md.sha256").write_text(f"{hashlib.sha256(hashed or prereg).hexdigest()}  PREREG.md\n", encoding="utf-8")

    def commit_all(self, message):
        git = ["git", "-c", "gc.auto=0", "-c", "maintenance.auto=false", "-c", "user.name=t", "-c", "user.email=t@t",
               "-C", str(self.repo)]
        subprocess.run([*git, "add", "tools", "src", "vendor", "flows", "data", "pixi.toml", "pixi.lock", "grid/box.sh", "grid/venv.sh",
                        "grid/redact.sed", "grid/drr-gap.sbatch", "docs"], check=True)
        subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", message], check=True)
        return subprocess.run([*git, "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()

    def drr_gap_job(self, step, job="501", **extra):
        env = dict(os.environ, PATH=f"{self.fake}:{os.environ['PATH']}", SCHWINGNET=str(self.repo), DATA_ROOT=str(self.data),
                   LAB_VOLUME=str(self.tmp), FAKE=str(self.fake), MODELS=str(self.models), STEP=step, SLURM_JOB_ID=job)
        for name in ("BENCH_ROOT", "INDEX", "PREPARE_JOB", "SHARD_TASKS", "SLURM_ARRAY_JOB_ID", "SLURM_ARRAY_TASK_ID",
                     "SLURM_ARRAY_TASK_COUNT", "SLURM_CPUS_PER_TASK", "WANDB_MODE", "OMP_NUM_THREADS", "TMPDIR"):
            env.pop(name, None)
        env.update(extra)
        return subprocess.run(["bash", str(self.repo / "grid" / "drr-gap.sbatch")], cwd=self.repo / "grid", env=env,
                              capture_output=True, text=True, timeout=60)

    def drr_gap_shard(self, task, **extra):
        return self.drr_gap_job("shard", job=str(601 + task), SLURM_ARRAY_JOB_ID="600", SLURM_ARRAY_TASK_ID=str(task),
                                SLURM_ARRAY_TASK_COUNT="4", **extra)

    def study_calls(self, verb):
        """What the stand-in box.sh was asked for one verb of the study's tool, each call's command alone."""
        return [line.split(" | ")[0] for line in self.boxed() if f"tools/domain_gap.py {verb} " in line]

    def steps(self):
        return self.bench_root() / "flexray_drr_gap" / "analysis" / "steps"

    def test_the_drr_gap_prepare_step_copies_the_code_at_its_commit_checks_the_freeze_and_runs_from_the_copy(self):
        # prepare copies the study's code at the commit it starts on and runs only that copy, so no
        # step holds grid/logs/HOLD; the frozen PREREG.md is checked by its hash in the copy before
        # anything is read (the Lab Recipe's freeze, exit 90 where it moved); the GPU and every input
        # are named in its step file, whose first line names its job and commit as the report's will;
        # its output stays in the run folder, the owner's alone; prepare writes no report itself
        commit = self.drr_gap_repo()
        index = self.drr_gap_inputs()
        out = self.bench_root() / "flexray_drr_gap"
        done = self.drr_gap_job("prepare")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("SN_BENCH_RC=0", done.stdout)
        code = out / f"code-{commit[:7]}"
        for path in ("tools/domain_gap.py", "src/schwingnet/__init__.py", "vendor/README.md", "data/domain_gap/groups.json",
                     "data/splits/test-persons.json", "grid/box.sh", "grid/venv.sh", "grid/redact.sed",
                     "docs/research/drr-domain-gap/PREREG.md", "docs/research/drr-domain-gap/PREREG.md.sha256"):
            self.assertTrue((code / path).is_file(), path)
        # the copy carries what the launcher names the run by: the locked environment, the flows, the
        # registry's PREREG, and COPY.txt, the commit and then every file it holds, as git listed them
        for path in ("pixi.lock", "pixi.toml", "flows/launch.py", "grid/drr-gap.sbatch", "data/reporting/claim.json",
                     "data/licences.json"):
            self.assertTrue((code / path).is_file(), path)
        record = (code / "COPY.txt").read_text(encoding="utf-8").splitlines()
        self.assertEqual(record[0], commit)
        self.assertIn("flows/launch.py", record[1:])
        self.assertIn("docs/research/drr-domain-gap/PREREG.md", record[1:])
        self.assertEqual(sorted(record[1:]), sorted(str(path.relative_to(code)) for path in code.rglob("*")
                                                    if path.is_file() and path.name != "COPY.txt"))
        # one launch, from the copy, of prepare's run under its own job; the body ran from the copy too
        launched = (self.fake / "launch.log").read_text(encoding="utf-8").splitlines()
        self.assertEqual(launched, [f"drr_gap --max-workers 1 -- --part prepare --prepare-job 501 --out {out}"
                                    f" | code={code} checkout={self.repo}"])
        self.assertIn("DRR_GAP_RC=0 1s", done.stdout)
        self.assertEqual((out / "analysis" / "CODE").read_text(encoding="utf-8"), f"{code}\n")
        self.assertEqual((out / "analysis" / "COMMIT").read_text(encoding="utf-8"), f"{commit}\n")
        boxed = self.boxed()
        self.assertTrue([line for line in boxed if line.startswith(f"{self.tmp}/go2432/.cache/bench/venv-")
                         and f"-m pip install --quiet {self.DRR_GAP_PINS} |" in line], boxed)
        prepares = self.study_calls("prepare")
        self.assertEqual(len(prepares), 1, boxed)
        self.assertTrue(prepares[0].endswith(
            f"/bin/python {code}/tools/domain_gap.py prepare --groups {code}/data/domain_gap/groups.json --data-root {self.data}"
            f" --index {index} --weights {self.data / 'hf_flexray_weights' / 'raw'} --imagenet {self.models / 'resnet18-f37072fd.pth'}"
            f" --out {out} --device cuda --workers 16 --frozen {code}/data/splits/test-persons.json"
            f" --spineps {self.data}/spineps --moose {self.data}/moose"), prepares[0])
        # no hold, one thread a worker only in the shards, and scratch of its own under /dev/shm, gone once it ends
        call = [line for line in boxed if "tools/domain_gap.py prepare " in line][0]
        self.assertIn(" | hold=no omp= tmp=/dev/shm/", call)
        scratch = call.split(" tmp=")[1]
        self.assertTrue(scratch.endswith("_drrgap_501_0"), scratch)
        self.assertFalse(Path(scratch).exists())
        self.assertFalse((self.repo / "grid" / "logs" / "HOLD").exists())
        lines = (self.steps() / "prepare.md").read_text(encoding="utf-8").splitlines()
        self.assertRegex(lines[0], rf"^# bench flexray_drr_gap: job 501 on \S+, commit {commit[:7]}, \S+ \S+ UTC$")
        prereg = (code / "docs" / "research" / "drr-domain-gap" / "PREREG.md.sha256").read_text(encoding="utf-8")[:16]
        for line in (f"- code: commit {commit} copied to {code}, which every step runs; no step holds the checkout",
                     f"- PREREG.md: as frozen, sha256 {prereg}",
                     "- GPU: NVIDIA H200, 143771 MiB, 550.54.15",
                     "- FluXray: not on the data root (fetch hf_flexray_data); the study skips its group with that reason",
                     f"- masks: spineps in {self.data}/spineps; moose in {self.data}/moose; a render group whose segmenter's"
                     " masks are not read, or too few CTs have, is skipped with that reason",
                     f"- environment: {self.DRR_GAP_PINS}; index: {index}; weights: {self.data / 'hf_flexray_weights' / 'raw'};"
                     f" imagenet: {self.models / 'resnet18-f37072fd.pth'}",
                     "- prepared: analysis/PREPARED.json written, so the shards claim its units",
                     "- units: 3 listed; 0 kept from an earlier chain in this folder, so this chain computes 3"):
            self.assertIn(line, lines)
        self.assertNotIn("NOTE: not an H200", "\n".join(lines))
        self.assertTrue(lines[-1].startswith("- exit 0 at "), lines)
        # the copy is no checkout, so the run record's commit, clean tree and pins come from the step
        pins = self.DRR_GAP_PINS.replace("==", " ")
        self.assertEqual((self.fake / "record.log").read_text(encoding="utf-8").splitlines(),
                         [f"prepare {commit} no {pins} over the train-gpu torch"])
        self.assertFalse((self.repo / "grid" / "logs" / "BENCH-flexray_drr_gap.md").exists())
        # the tool's own output names files, so it stays in the run folder, the owner's alone
        self.assertNotIn("names files", done.stdout)
        self.assertIn("names files", (out / "prepare.log").read_text(encoding="utf-8"))
        self.assertEqual(out.stat().st_mode & 0o777, 0o700)
        self.assertEqual((out / "prepare.log").stat().st_mode & 0o777, 0o600)
        self.assertNotIn("WANDB_MODE", (self.repo / "grid" / "drr-gap.sbatch").read_text(encoding="utf-8"))
        # a PREREG.md edited after its freeze stops the next prepare in its copy, before the tool runs
        self.freeze(b"# PREREG\n\nedited after the freeze\n", hashed=b"# PREREG\n\nfrozen 2026-10-27, no further edits\n")
        moved = self.commit_all("an edit after the freeze")
        done = self.drr_gap_job("prepare", job="502")
        self.assertEqual(done.returncode, 90, done.stdout + done.stderr)
        self.assertIn("SN_BENCH_RC=90", done.stdout)
        lines = (self.steps() / "prepare.md").read_text(encoding="utf-8").splitlines()
        self.assertIn(f"commit {moved[:7]}, ", lines[0])
        self.assertIn("- STOP: PREREG.md changed since the freeze", lines)
        self.assertTrue(lines[-1].startswith("- exit 90 at "), lines)
        self.assertEqual(len(self.study_calls("prepare")), 1)
        self.assertFalse((out / "analysis" / "PREPARED.json").exists())
        self.assertTrue((out / f"code-{moved[:7]}" / "docs" / "research" / "drr-domain-gap" / "PREREG.md").is_file())

    def test_a_drr_gap_run_in_a_folder_of_its_own_leaves_the_earlier_run_as_it_was_and_counts_what_it_keeps(self):
        # each run of the study has a folder of its own (gate.sh's DRR_GAP_FOLDER, passed as
        # DRR_GAP_OUT), so the third run computes everything again while the second's folder stays as
        # it was (DEVIATIONS.md, item 12); prepare's step file counts the units it lists and those an
        # earlier chain in the same folder left done, which the tool names only where there are some
        self.drr_gap_repo()
        self.drr_gap_inputs()
        earlier = self.bench_root() / "flexray_drr_gap"
        (earlier / "analysis" / "steps").mkdir(parents=True)
        (earlier / "plan.json").write_text("run 2's plan\n", encoding="ascii")
        (earlier / "analysis" / "PREPARED.json").write_text('{"units": 3}\n', encoding="ascii")
        (earlier / "analysis" / "steps" / "prepare.md").write_text("run 2's prepare\n", encoding="ascii")
        (earlier / "RUNLOG.txt").write_text("run 2's run log\n", encoding="ascii")
        def files_of(folder):
            return {str(path.relative_to(folder)): path.read_bytes() for path in folder.rglob("*") if path.is_file()}
        before = files_of(earlier)
        out = self.bench_root() / "flexray_drr_gap_run3"
        done = self.drr_gap_job("prepare", DRR_GAP_OUT=str(out))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        launched = (self.fake / "launch.log").read_text(encoding="utf-8").splitlines()
        self.assertIn(f" --out {out} | ", launched[0])
        self.assertIn(f" --out {out} ", self.study_calls("prepare")[0] + " ")
        lines = (out / "analysis" / "steps" / "prepare.md").read_text(encoding="utf-8").splitlines()
        self.assertIn("- units: 3 listed; 0 kept from an earlier chain in this folder, so this chain computes 3", lines)
        self.assertEqual(out.stat().st_mode & 0o777, 0o700)
        # a second chain of the same run keeps what its first left done, and says how much
        (self.fake / "kept").write_text("1", encoding="ascii")
        done = self.drr_gap_job("prepare", job="502", DRR_GAP_OUT=str(out))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        lines = (out / "analysis" / "steps" / "prepare.md").read_text(encoding="utf-8").splitlines()
        self.assertIn("- units: 3 listed; 1 kept from an earlier chain in this folder, so this chain computes 2", lines)
        # nothing in the second run's folder was read, moved, written or added to
        self.assertEqual(files_of(earlier), before)

    def test_the_drr_gap_prepare_step_refuses_a_missing_input_a_node_with_no_gpu_and_a_failed_tool(self):
        # the masks refuse nothing (the owner's word of 2026-10-27): with neither folder the step says
        # each is absent and passes both as ever; any card is named and run on, an H200 or not (the
        # owner's word of 2026-10-28 00:23 UTC); a node where
        # nvidia-smi names no GPU, a missing input and a tool that fails each stop the step by name,
        # the tool's last line masked
        self.drr_gap_repo()
        self.drr_gap_inputs()
        (self.data / "spineps").rmdir()
        (self.data / "moose").rmdir()
        (self.fake / "gpu").write_text("Tesla V100-SXM2-32GB, 32510 MiB, 550.54.15\n", encoding="utf-8")
        done = self.drr_gap_job("prepare", BENCH_SKIP_MASKS="moose")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        text = (self.steps() / "prepare.md").read_text(encoding="utf-8")
        self.assertIn(f"- masks: spineps absent, no {self.data}/spineps; moose absent, no {self.data}/moose (bench flexray_drr_seg"
                      " makes them); a render group whose segmenter's masks are not read, or too few CTs have, is"
                      " skipped with that reason\n", text)
        self.assertIn("- GPU: Tesla V100-SXM2-32GB, 32510 MiB, 550.54.15\n- FluXray: ", text)
        self.assertNotIn("NOTE", text)
        prepares = self.study_calls("prepare")
        self.assertTrue(prepares[-1].endswith(f" --spineps {self.data}/spineps --moose {self.data}/moose"), prepares[-1])
        self.assertNotIn("--skip-masks", prepares[-1])
        (self.fake / "gpu").unlink()
        done = self.drr_gap_job("prepare")
        self.assertEqual(done.returncode, 4, done.stdout + done.stderr)
        text = (self.steps() / "prepare.md").read_text(encoding="utf-8")
        self.assertIn("- FAILED: nvidia-smi names no GPU on ", text)
        self.assertEqual(text.splitlines()[-1][:9], "- exit 4 ")
        (self.fake / "gpu").write_text("NVIDIA H200, 143771 MiB, 550.54.15\n", encoding="utf-8")
        shutil.rmtree(self.data / "totalsegmentator_v201")
        done = self.drr_gap_job("prepare")
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn(f"- FAILED: no totalsegmentator_v201 under {self.data}, the CTs the render groups draw\n",
                      (self.steps() / "prepare.md").read_text(encoding="utf-8"))
        (self.data / "totalsegmentator_v201" / "s0001").mkdir(parents=True)
        token = "hf_" + "Ab" * 17
        (self.fake / "fail").write_text(token, encoding="utf-8")
        done = self.drr_gap_job("prepare")
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        text = (self.steps() / "prepare.md").read_text(encoding="utf-8")
        self.assertIn("- FAILED: domain_gap.py prepare ended 2 (drr-gap FAILED: no image decoded, token <withheld>)\n", text)
        self.assertNotIn(token, text + done.stdout)
        self.assertEqual(len(self.study_calls("prepare")), 2)
        self.assertEqual(self.drr_gap_job("").returncode, 64)

    def test_a_drr_gap_shard_claims_from_the_copy_only_once_its_chains_prepare_finished(self):
        # rule 9: a task with nothing prepared says so in one line and exits 0, never waiting on its
        # node; with PREPARED.json from its own chain's prepare it runs the copy's shard, one thread a
        # worker, and its step file is one line: task, job, node, GPU and exit, with the log's last
        # line masked where it failed; a PREREG.md that moved in the copy stops it with exit 90
        commit = self.drr_gap_repo()
        self.drr_gap_inputs()
        out = self.bench_root() / "flexray_drr_gap"
        done = self.drr_gap_shard(2, PREPARE_JOB="501")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("nothing to claim, since prepare did not finish", done.stdout)
        self.assertEqual(self.study_calls("shard"), [])
        self.assertEqual(self.drr_gap_job("prepare").returncode, 0)
        # a prepare that is not this chain's, an earlier chain's left when this one's never started
        done = self.drr_gap_shard(2, PREPARE_JOB="499")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("nothing to claim", done.stdout)
        self.assertEqual(self.study_calls("shard"), [])
        done = self.drr_gap_shard(2, PREPARE_JOB="501")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        code = out / f"code-{commit[:7]}"
        shards = self.study_calls("shard")
        self.assertEqual(len(shards), 1, self.boxed())
        self.assertTrue(shards[0].endswith(f"/bin/python {code}/tools/domain_gap.py shard --out {out} --task 2 --tasks 4"
                                           " --workers 16 --device cuda"), shards[0])
        call = [line for line in self.boxed() if "tools/domain_gap.py shard " in line][0]
        self.assertIn(" | hold=no omp=1 tmp=/dev/shm/", call)
        self.assertTrue(call.endswith("_drrgap_603_2"), call)
        lines = (self.steps() / "shard-2.md").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1, lines)
        self.assertRegex(lines[0], r"^- shard 2: job 600_2 on \S+, GPU NVIDIA H200, exit 0 at \S+ \S+ UTC$")
        self.assertIn("claimed 1 unit", (out / "analysis" / "logs" / "shard-2.log").read_text(encoding="utf-8"))
        self.assertNotIn("units.json", done.stdout)
        token = "hf_" + "Cd" * 17
        (self.fake / "shard_fail").write_text(token, encoding="utf-8")
        done = self.drr_gap_shard(3, PREPARE_JOB="501", SLURM_CPUS_PER_TASK="8")
        self.assertEqual(done.returncode, 3, done.stdout + done.stderr)
        line = (self.steps() / "shard-3.md").read_text(encoding="utf-8")
        self.assertRegex(line, r"^- shard 3: job 600_3 on \S+, GPU NVIDIA H200, exit 3 at \S+ \S+ UTC: drr-gap FAILED:"
                               r" three units in a row failed, token <withheld>\n$")
        self.assertNotIn(token, line + done.stdout)
        self.assertIn(" --workers 8 ", self.study_calls("shard")[-1])
        (self.fake / "shard_fail").unlink()
        prereg = code / "docs" / "research" / "drr-domain-gap" / "PREREG.md"
        prereg.write_text("edited in the copy\n", encoding="utf-8")
        done = self.drr_gap_shard(1, PREPARE_JOB="501")
        self.assertEqual(done.returncode, 90, done.stdout + done.stderr)
        self.assertIn(": STOP: PREREG.md changed since the freeze", (self.steps() / "shard-1.md").read_text(encoding="utf-8"))
        self.assertEqual(len(self.study_calls("shard")), 2)
        self.assertFalse((self.repo / "grid" / "logs" / "HOLD").exists())

    def test_a_drr_gap_step_passes_slurm_s_warning_on_to_the_tool(self):
        # job submit asks Slurm for TERM to the batch shell alone two minutes before the time limit
        # (--signal=B:TERM@120); the shell waits on the tool in the background, so its trap runs at
        # once and passes the TERM on, and the tool's own handler writes its line before the shell's
        self.drr_gap_repo()
        self.drr_gap_inputs()
        self.assertEqual(self.drr_gap_job("prepare").returncode, 0)
        (self.fake / "shard_sleep").write_text("x", encoding="utf-8")
        env = dict(os.environ, PATH=f"{self.fake}:{os.environ['PATH']}", SCHWINGNET=str(self.repo), DATA_ROOT=str(self.data),
                   LAB_VOLUME=str(self.tmp), FAKE=str(self.fake), MODELS=str(self.models), STEP="shard", SLURM_JOB_ID="602",
                   SLURM_ARRAY_JOB_ID="600", SLURM_ARRAY_TASK_ID="1", SLURM_ARRAY_TASK_COUNT="4", PREPARE_JOB="501")
        for name in ("BENCH_ROOT", "INDEX", "SHARD_TASKS", "SLURM_CPUS_PER_TASK", "OMP_NUM_THREADS", "TMPDIR"):
            env.pop(name, None)
        started = time.monotonic()
        job = subprocess.Popen(["bash", str(self.repo / "grid" / "drr-gap.sbatch")], cwd=self.repo / "grid", env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            for _ in range(200):
                if (self.fake / "shard_started").exists():
                    break
                time.sleep(0.05)
            self.assertTrue((self.fake / "shard_started").exists(), "the stand-in tool never started")
            os.kill(job.pid, signal.SIGTERM)
            output, _ = job.communicate(timeout=20)
        finally:
            job.kill()
        self.assertEqual(job.returncode, 143, output)
        self.assertLess(time.monotonic() - started, 20)
        self.assertEqual((self.fake / "term.log").read_text(encoding="utf-8"), "the tool saw TERM\n")
        line = (self.steps() / "shard-1.md").read_text(encoding="utf-8")
        self.assertRegex(line, r"^- shard 1: job 600_1 on \S+, GPU NVIDIA H200, exit 143 at \S+ \S+ UTC:"
                               r" Slurm ended the task \(its time, or a cancel\)\n$")

    def test_a_drr_gap_prepare_clears_the_earlier_chain_s_run_log_before_any_check_can_stop_it(self):
        # the tool clears the run log only once it runs, so a prepare that stops at a check before it
        # (here a node with no GPU) must not leave the merge an earlier chain's lines as its own
        self.drr_gap_repo()
        self.drr_gap_inputs()
        self.assertEqual(self.drr_gap_job("prepare").returncode, 0)
        out = self.bench_root() / "flexray_drr_gap"
        (out / "analysis" / "runlog").mkdir(parents=True, exist_ok=True)
        (out / "analysis" / "runlog" / "prepare.txt").write_text("1.0 prepare: started as job 501 on node1\n", encoding="utf-8")
        (out / "RUNLOG.txt").write_text("2026-10-27 22:10:00 prepare: started as job 501 on node1\n", encoding="utf-8")
        (self.fake / "gpu").unlink()
        self.assertEqual(self.drr_gap_job("prepare", job="801").returncode, 4)
        self.assertFalse((out / "analysis" / "runlog").exists())
        self.assertFalse((out / "RUNLOG.txt").exists())

    def test_the_drr_gap_merge_says_why_a_prepare_stopped_at_its_freeze_left_no_run_log(self):
        # a prepare that found the copy's PREREG.md moved reads nothing, and the merge neither reads
        # the run log nor builds for it, and says so
        self.drr_gap_repo(prereg=b"# PREREG\n")
        self.freeze(b"# PREREG\n", hashed=b"another text\n")
        self.commit_all("a freeze that does not match")
        self.drr_gap_inputs()
        self.assertEqual(self.drr_gap_job("prepare").returncode, 90)
        done = self.drr_gap_job("merge", job="700", PREPARE_JOB="501", SHARD_TASKS="4")
        self.assertEqual(done.returncode, 90, done.stdout + done.stderr)
        report = (self.repo / "grid" / "logs" / "BENCH-flexray_drr_gap.md").read_text(encoding="utf-8")
        self.assertIn("- run log: not read, since the copy's PREREG.md is not the one frozen\n- exit 90 at ", report)
        self.assertEqual(self.study_calls("runlog"), [])
        self.assertEqual([line for line in self.boxed() if " -m venv " in line or " -m pip install " in line], [])

    def test_the_drr_gap_merge_writes_the_report_from_every_steps_lines_with_the_summary_last(self):
        # only the merge writes logs/BENCH-flexray_drr_gap.md: prepare's lines first, so the first line
        # names prepare's job and commit as bench_job_of and bench_failed_on_older_code read them, a line
        # per shard task (or one saying the task left none), the merge's own lines, the summary masked
        # and indented, and the exit last; no step holds the checkout, so one that moved is noted and
        # the results stand; the run log the tool prints follows the summary, masked, indented and cut
        # to 50 lines, before the exit (the owner's ask of 2026-10-28 00:23 UTC for real-time logging
        # in the report); a merge that finds units not done reports its last line and no summary
        commit = self.drr_gap_repo()
        self.drr_gap_inputs()
        out = self.bench_root() / "flexray_drr_gap"
        token = "hf_" + "Ij" * 17
        (self.fake / "summary").write_text("\n".join(self.DRR_GAP_SUMMARY) + f"\nW&B token {token}\n", encoding="utf-8")
        logged = [f"2026-10-28 00:{minute:02d}:00 task {minute % 16}: unit physics/null/g{minute} done" for minute in range(60)]
        logged[3] = f"2026-10-28 00:03:00 task 3: unit physics/maps/umap FAILED after 4 s (ValueError; token {token})"
        (self.fake / "runlog").write_text("\n".join(logged) + "\n", encoding="utf-8")
        self.assertEqual(self.drr_gap_job("prepare").returncode, 0)
        for task in (0, 1, 3):
            self.assertEqual(self.drr_gap_shard(task, PREPARE_JOB="501").returncode, 0)
        moved = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "gc.auto=0", "-c", "maintenance.auto=false",
                                "-C", str(self.repo), "commit", "-q", "--allow-empty", "-m", "moved"], capture_output=True)
        self.assertEqual(moved.returncode, 0, moved.stderr)
        done = self.drr_gap_job("merge", job="700", PREPARE_JOB="501", SHARD_TASKS="4")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("SN_BENCH_RC=0", done.stdout)
        code = out / f"code-{commit[:7]}"
        merges = self.study_calls("merge")
        self.assertEqual(len(merges), 1, self.boxed())
        self.assertTrue(merges[0].endswith(f"{code}/tools/domain_gap.py merge --out {out} --groups {code}/data/domain_gap/groups.json"),
                        merges[0])
        self.assertTrue(self.study_calls("summary")[0].endswith(f"{code}/tools/domain_gap.py summary --out {out}"))
        report = self.repo / "grid" / "logs" / "BENCH-flexray_drr_gap.md"
        text = report.read_text(encoding="utf-8")
        lines = text.splitlines()
        prepare = (self.steps() / "prepare.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith(prepare), text)
        self.assertRegex(lines[0], rf"^# bench flexray_drr_gap: job 501 on \S+, commit {commit[:7]}, ")
        after = text[len(prepare):].splitlines()
        self.assertRegex(after[0], r"^- shard 0: job 600_0 on \S+, GPU NVIDIA H200, exit 0 at ")
        self.assertRegex(after[1], r"^- shard 1: job 600_1 on ")
        self.assertEqual(after[2], "- shard 2: left no line (it never started, or Slurm ended it before it could write one)")
        self.assertRegex(after[3], r"^- shard 3: job 600_3 on ")
        self.assertRegex(after[4], r"^- merge: job 700 on \S+$")
        self.assertIn("- NOTE: the checkout is at ", after[5])
        self.assertIn(f"every step ran from the copy at {commit[:7]}, so the results stand", after[5])
        self.assertEqual(after[6], f"- results: {out}")
        self.assertEqual(after[7:7 + len(self.DRR_GAP_SUMMARY)], [f"  {line}" for line in self.DRR_GAP_SUMMARY])
        self.assertEqual(after[7 + len(self.DRR_GAP_SUMMARY)], "  W&B token <withheld>")
        log_at = 8 + len(self.DRR_GAP_SUMMARY)
        self.assertEqual(after[log_at], "- run log, UTC: each step's lines as it wrote them while it ran, with the units' quarter marks")
        self.assertEqual(after[log_at + 1:-1], [f"  {line}" for line in logged[:50]][:3]
                         + ["  2026-10-28 00:03:00 task 3: unit physics/maps/umap FAILED after 4 s (ValueError; token <withheld>)"]
                         + [f"  {line}" for line in logged[4:50]])
        self.assertTrue(self.study_calls("runlog")[0].endswith(f"{code}/tools/domain_gap.py runlog --out {out}"))
        self.assertNotIn(token, text + done.stdout)
        self.assertTrue(lines[-1].startswith("- exit 0 at "), lines)
        self.assertEqual(report.stat().st_mode & 0o777, 0o644)
        self.assertTrue((self.steps() / "merge.md").read_text(encoding="utf-8").splitlines()[-1].startswith("- exit 0 at "))
        self.assertTrue(all(" | hold=no " in line for line in self.boxed()), self.boxed())
        # the merge's run record, where the flow's end writes the study's CLAIM and REFORMS report: the
        # report as BENCH.md and the summary as summary.txt, as a recorded run of the study holds them,
        # each as the gate's word prints them, every line through the masking filter and cut at 200
        record = out / "runs" / "501"
        printed = subprocess.run(["sed", "-r", "-f", str(self.repo / "grid" / "redact.sed")], input=text, capture_output=True,
                                 text=True, check=True).stdout
        bench = (record / "BENCH.md").read_text(encoding="utf-8")
        self.assertEqual(bench, "".join(f"{line[:200]}\n" for line in printed.splitlines()))
        self.assertIn(f"commit {commit}", text)
        self.assertNotIn(commit, bench)
        self.assertIn("- code: commit <hex withheld> copied to ", bench)
        self.assertEqual(bench.splitlines()[0], lines[0])
        self.assertEqual((record / "summary.txt").read_text(encoding="utf-8").splitlines(),
                         [*self.DRR_GAP_SUMMARY, "W&B token <withheld>"])
        self.assertEqual((record / "groups.json").read_text(encoding="utf-8"), "{}\n")
        self.assertEqual((self.fake / "launch.log").read_text(encoding="utf-8").splitlines()[-1],
                         f"drr_gap --max-workers 1 -- --part merge --prepare-job 501 --out {out} --tasks 4 | code={code} checkout={self.repo}")
        self.assertFalse((self.repo / "grid" / "logs" / "HOLD").exists())
        # a merge that finds units not done: its last line, no summary, the exit last, and no record
        # for the flow to report on
        shutil.rmtree(record)
        (self.fake / "merge_fail").write_text("", encoding="utf-8")
        done = self.drr_gap_job("merge", job="701", PREPARE_JOB="501", SHARD_TASKS="4")
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        text = report.read_text(encoding="utf-8")
        self.assertIn("- FAILED: domain_gap.py merge ended 2 (drr-gap FAILED: 1 of 3 units not done)\n", text)
        self.assertNotIn("- results:", text)
        self.assertIn("- run log, UTC: ", text)
        self.assertTrue(text.splitlines()[-1].startswith("- exit 2 at "))
        self.assertEqual(len(self.study_calls("summary")), 1)
        self.assertFalse(record.exists())
        # the gate reads the job and the commit from prepare's line: a failure on older code is queued
        # once more, the report kept under prepare's job
        self.environments_ready()
        done = self.gate("bench", "flexray_drr_gap")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("## BENCH-flexray_drr_gap.md (", done.stdout)
        self.assertIn("  the report above ended in failure on older code: queueing the benchmark again at ", done.stdout)
        self.assertTrue((self.repo / "grid" / "logs" / "BENCH-flexray_drr_gap-501.md").is_file())
        self.assertEqual(len(self.submitted()), 3)

    def test_a_kept_drr_gap_report_of_sixteen_tasks_is_printed_whole(self):
        # the study's report at its largest, a line for each of its 16 shard tasks, a summary of 85
        # lines and a run log of 50, is printed whole by the next send of the word, its exit line
        # last, so the owner reads every task's end and the run log's last lines
        self.drr_gap_repo()
        self.drr_gap_inputs()
        words = " ".join(["the render group and its table"] * 4)
        (self.fake / "summary").write_text("".join(f"line {k} of the summary: {words}\n" for k in range(85)), encoding="utf-8")
        (self.fake / "runlog").write_text("".join(f"2026-10-28 01:{k:02d}:00 task {k % 16}: unit physics/null/g{k} done, {words}\n"
                                                  for k in range(60)), encoding="utf-8")
        self.assertEqual(self.drr_gap_job("prepare").returncode, 0)
        for task in range(16):
            self.assertEqual(self.drr_gap_shard(task, PREPARE_JOB="501").returncode, 0)
        done = self.drr_gap_job("merge", job="700", PREPARE_JOB="501", SHARD_TASKS="16")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        report = (self.repo / "grid" / "logs" / "BENCH-flexray_drr_gap.md").read_text(encoding="utf-8").splitlines()
        self.assertGreater(len(report), 150)
        self.assertEqual(len([line for line in report if line.startswith("- shard ")]), 16)
        self.assertTrue(report[-1].startswith("- exit 0 at "), report[-1])
        self.environments_ready()
        done = self.gate("bench", "flexray_drr_gap")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        printed = done.stdout.splitlines()
        start = printed.index(next(line for line in printed if line.startswith("## BENCH-flexray_drr_gap.md (")))
        shown = printed[start + 1:start + 1 + len(report)]
        # masked as every log the gate prints is, so each line is read by how it starts
        self.assertEqual([line[:8] for line in shown], [line[:8] for line in report])
        self.assertEqual(shown[-1], report[-1])
        self.assertEqual(len(self.submitted()), 0)

    def test_the_drr_gap_merge_reports_a_failed_prepare_without_running_the_tool(self):
        # where prepare did not end in exit 0, the merge composes the report from what prepare said
        # and ends with prepare's code, running nothing of the study; where this chain's prepare never
        # started, it writes no report at all, so the next send of the word queues the study again
        self.drr_gap_repo()
        self.drr_gap_inputs()
        report = self.repo / "grid" / "logs" / "BENCH-flexray_drr_gap.md"
        (self.fake / "fail").write_text("x", encoding="utf-8")
        self.assertEqual(self.drr_gap_job("prepare").returncode, 2)
        for task in range(4):
            self.assertEqual(self.drr_gap_shard(task, PREPARE_JOB="501").returncode, 0)
        done = self.drr_gap_job("merge", job="700", PREPARE_JOB="501", SHARD_TASKS="4")
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("SN_BENCH_RC=2", done.stdout)
        text = report.read_text(encoding="utf-8")
        prepare = (self.steps() / "prepare.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith(prepare))
        self.assertIn("- FAILED: domain_gap.py prepare ended 2 (drr-gap FAILED: no image decoded, token x)\n", text)
        after = text[len(prepare):].splitlines()
        self.assertRegex(after[0], r"^- merge: job 700 on \S+$")
        self.assertEqual(after[1], "- the shards and the merge ran nothing of the study, since prepare did not end in exit 0")
        # the run log says how far prepare got, read with prepare's environment; here the tool wrote none
        self.assertEqual(after[2], "- run log: none, since no step of the tool wrote a line of it")
        self.assertTrue(after[3].startswith("- exit 2 at "))
        self.assertEqual(len(after), 4, after)
        self.assertEqual(self.study_calls("merge") + self.study_calls("summary") + self.study_calls("shard"), [])
        self.assertEqual(len(self.study_calls("runlog")), 1)
        # and the merge built nothing to read it: the one environment is the one prepare made
        built = [line for line in self.boxed() if " -m venv " in line or " -m pip install " in line]
        self.assertEqual(len([line for line in built if " -m venv " in line]), 1, built)
        # where prepare made no environment, the merge builds none and says why there is no run log
        venvs = list((self.tmp / "go2432" / ".cache" / "bench").glob("venv-*/READY"))
        self.assertEqual(len(venvs), 1, venvs)
        venvs[0].unlink()
        done = self.drr_gap_job("merge", job="700", PREPARE_JOB="501", SHARD_TASKS="4")
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("- run log: not read, since prepare made no environment to read it with\n- exit 2 at ",
                      report.read_text(encoding="utf-8"))
        self.assertEqual([line for line in self.boxed() if " -m venv " in line or " -m pip install " in line], built)
        self.assertEqual(len(self.study_calls("runlog")), 1)
        self.assertEqual(self.drr_gap_job("prepare").returncode, 2)
        (self.fake / "runlog").write_text("2026-10-28 00:01:00 prepare: stage features FAILED after 60 s\n", encoding="utf-8")
        done = self.drr_gap_job("merge", job="700", PREPARE_JOB="501", SHARD_TASKS="4")
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("- run log, UTC: each step's lines as it wrote them while it ran, with the units' quarter marks\n"
                      "  2026-10-28 00:01:00 prepare: stage features FAILED after 60 s\n- exit 2 at ", report.read_text(encoding="utf-8"))
        # a prepare that Slurm ended before its exit line: exit 1, said
        (self.fake / "fail").unlink()
        self.assertEqual(self.drr_gap_job("prepare").returncode, 0)
        cut = (self.steps() / "prepare.md").read_text(encoding="utf-8").splitlines()[:-1]
        (self.steps() / "prepare.md").write_text("".join(f"{line}\n" for line in cut), encoding="utf-8")
        done = self.drr_gap_job("merge", job="701", PREPARE_JOB="501", SHARD_TASKS="4")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        text = report.read_text(encoding="utf-8")
        self.assertIn("- prepare left no exit line: Slurm ended it before it finished", text)
        self.assertTrue(text.splitlines()[-1].startswith("- exit 1 at "))
        self.assertEqual(self.study_calls("merge"), [])
        # a PREREG.md that moved in the copy: exit 90 before the tool
        self.assertEqual(self.drr_gap_job("prepare").returncode, 0)
        code = Path((self.bench_root() / "flexray_drr_gap" / "analysis" / "CODE").read_text(encoding="utf-8").strip())
        (code / "docs" / "research" / "drr-domain-gap" / "PREREG.md").write_text("edited in the copy\n", encoding="utf-8")
        done = self.drr_gap_job("merge", job="702", PREPARE_JOB="501", SHARD_TASKS="4")
        self.assertEqual(done.returncode, 90, done.stdout + done.stderr)
        self.assertIn("- STOP: PREREG.md changed since the freeze\n- run log: not read, since the merge stopped before it read the run folder\n",
                      report.read_text(encoding="utf-8"))
        self.assertEqual(self.study_calls("merge"), [])
        # this chain's prepare never started: the step file there is an earlier chain's, so no report
        report.unlink()
        done = self.drr_gap_job("merge", job="703", PREPARE_JOB="777", SHARD_TASKS="4")
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("prepare (job 777) left no step file: it never started", done.stdout)
        self.assertFalse(report.exists())
        self.assertFalse((self.repo / "grid" / "logs" / "HOLD").exists())

    def test_bench_sbatch_refuses_the_study_and_points_to_its_own_script(self):
        done = self.bench_job("flexray_drr_gap")
        self.assertEqual(done.returncode, 64, done.stdout + done.stderr)
        self.assertIn("grid/drr-gap.sbatch", done.stdout)
        self.assertIn("SN_BENCH_RC=64", done.stdout)
        self.assertFalse((self.repo / "grid" / "logs" / "BENCH-flexray_drr_gap.md").exists())
        # MOOSE's masks run on a launched flow of their own too, so bench.sbatch refuses them alike
        done = self.bench_job("flexray_drr_seg")
        self.assertEqual(done.returncode, 64, done.stdout + done.stderr)
        self.assertIn("grid/drr-seg.sbatch", done.stdout)
        self.assertIn("SN_BENCH_RC=64", done.stdout)
        self.assertFalse((self.repo / "grid" / "logs" / "BENCH-flexray_drr_seg.md").exists())
        self.assertEqual(self.boxed(), [])

    def test_a_drr_gap_step_whose_launcher_refuses_says_so_in_its_own_line(self):
        # a launcher that refuses before any flow runs (a PREREG the registry's hash does not match,
        # say) leaves the step's work unrun and no exit line of its own: the driver writes the step's
        # end with the launcher's code, so the merge and the gate read why
        self.drr_gap_repo()
        self.drr_gap_inputs()
        (self.fake / "launch_refuse").write_text("PREREG.md moved", encoding="utf-8")
        done = self.drr_gap_job("prepare")
        self.assertEqual(done.returncode, 90, done.stdout + done.stderr)
        self.assertIn("launch: PREREG.md moved", done.stdout)
        lines = (self.steps() / "prepare.md").read_text(encoding="utf-8").splitlines()
        self.assertIn("- FAILED: the launcher ended 90 and the step's work wrote no exit line (a refusal of the launcher's,"
                      " or a fault of the flow; the job's log says which)", lines)
        self.assertTrue(lines[-1].startswith("- exit 90 at "), lines)
        self.assertEqual(self.study_calls("prepare"), [])
        (self.fake / "launch_refuse").unlink()
        self.assertEqual(self.drr_gap_job("prepare").returncode, 0)
        (self.fake / "launch_refuse").write_text("PREREG.md moved", encoding="utf-8")
        done = self.drr_gap_shard(0, PREPARE_JOB="501")
        self.assertEqual(done.returncode, 90, done.stdout + done.stderr)
        self.assertRegex((self.steps() / "shard-0.md").read_text(encoding="utf-8"),
                         r"^- shard 0: job 600_0 on \S+, GPU NVIDIA H200, exit 90 at \S+ \S+ UTC: FAILED: the launcher ended 90 ")
        done = self.drr_gap_job("merge", job="700", PREPARE_JOB="501", SHARD_TASKS="4")
        self.assertEqual(done.returncode, 90, done.stdout + done.stderr)
        report = (self.repo / "grid" / "logs" / "BENCH-flexray_drr_gap.md").read_text(encoding="utf-8")
        self.assertIn("- FAILED: the launcher ended 90 and the step's work wrote no exit line", report)
        self.assertTrue(report.splitlines()[-1].startswith("- exit 90 at "))
        self.assertEqual(self.study_calls("merge") + self.study_calls("shard"), [])
        self.assertFalse((self.bench_root() / "flexray_drr_gap" / "runs").exists())

    def test_a_drr_gap_step_whose_flow_fails_after_its_work_ends_with_the_launchers_code(self):
        # the work ended 0 and the flow did not (the merge's end found the study's CLAIM and REFORMS
        # report not current, or an end failed): the job ends with the launcher's code, as every
        # launched flow's job does, and the step's file says why beneath the work's own line; a
        # prepare that ended so stops the shards, which claim nothing from it
        self.drr_gap_repo()
        self.drr_gap_inputs()
        (self.fake / "launch_after").write_text("1", encoding="utf-8")
        done = self.drr_gap_job("prepare")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("SN_BENCH_RC=1", done.stdout)
        lines = (self.steps() / "prepare.md").read_text(encoding="utf-8").splitlines()
        self.assertTrue(lines[-3].startswith("- exit 0 at "), lines)
        self.assertEqual(lines[-2], "- FAILED: the step's work ended 0, but its flow ended 1: its end failed after the work"
                                    " (the job's log and the run's page say why)")
        self.assertTrue(lines[-1].startswith("- exit 1 at "), lines)
        (self.fake / "launch_after").unlink()
        done = self.drr_gap_shard(0, PREPARE_JOB="501")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("nothing to claim, since prepare did not finish", done.stdout)
        self.assertEqual(self.study_calls("shard"), [])
        # a shard: its one line names the launcher's code and why
        self.assertEqual(self.drr_gap_job("prepare").returncode, 0)
        (self.fake / "launch_after").write_text("1", encoding="utf-8")
        done = self.drr_gap_shard(0, PREPARE_JOB="501")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertRegex((self.steps() / "shard-0.md").read_text(encoding="utf-8"),
                         r"^- shard 0: job 600_0 on \S+, GPU NVIDIA H200, exit 1 at \S+ \S+ UTC: FAILED: the step's work ended 0,"
                         r" but its flow ended 1: its end failed after the work \(the job's log and the run's page say why\)\n$")
        self.assertEqual(len(self.study_calls("shard")), 1)
        # the merge: the report the work wrote, numbers and all, then why and the launcher's code last,
        # so the gate reads a failure and the report says the numbers stand
        done = self.drr_gap_job("merge", job="700", PREPARE_JOB="501", SHARD_TASKS="4")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("SN_BENCH_RC=1", done.stdout)
        lines = (self.repo / "grid" / "logs" / "BENCH-flexray_drr_gap.md").read_text(encoding="utf-8").splitlines()
        self.assertIn(f"  {self.DRR_GAP_SUMMARY[0]}", lines)
        self.assertTrue(lines[-3].startswith("- exit 0 at "), lines[-4:])
        self.assertEqual(lines[-2], "- FAILED: the step's work ended 0, but its flow ended 1: the study's CLAIM and REFORMS report under"
                                    " runs/501/ is not current, or the flow's end failed before it was checked (the job's log and the"
                                    " run's page say which); the numbers above stand")
        self.assertTrue(lines[-1].startswith("- exit 1 at "), lines[-4:])
        self.assertTrue((self.steps() / "merge.md").read_text(encoding="utf-8").splitlines()[-1].startswith("- exit 1 at "))

    def test_a_drr_gap_step_whose_run_was_resumed_with_its_work_cloned_says_so(self):
        # the launcher resumed a run of the same words whose finished step Metaflow cloned, so this
        # job's work wrote nothing and the flow ended 0: a shard's line says so with exit 0; the merge
        # keeps the report that run wrote where it is that run's whole report, and fails where it is
        # not; a prepare, which cleared what it made before it began, fails and asks for a new chain
        self.drr_gap_repo()
        self.drr_gap_inputs()
        self.assertEqual(self.drr_gap_job("prepare").returncode, 0)
        (self.fake / "launch_cloned").write_text("", encoding="utf-8")
        done = self.drr_gap_shard(0, PREPARE_JOB="501")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertRegex((self.steps() / "shard-0.md").read_text(encoding="utf-8"),
                         r"^- shard 0: job 600_0 on \S+, GPU NVIDIA H200, exit 0 at \S+ \S+ UTC: the flow ended 0 and this job's work"
                         r" wrote no exit line: the launcher resumed a run of these words whose finished step Metaflow cloned,"
                         r" which did this task's units\n$")
        self.assertEqual(self.study_calls("shard"), [])
        (self.fake / "launch_cloned").unlink()
        report = self.repo / "grid" / "logs" / "BENCH-flexray_drr_gap.md"
        self.assertEqual(self.drr_gap_job("merge", job="700", PREPARE_JOB="501", SHARD_TASKS="4").returncode, 0)
        kept = report.read_text(encoding="utf-8")
        (self.fake / "launch_cloned").write_text("", encoding="utf-8")
        done = self.drr_gap_job("merge", job="701", PREPARE_JOB="501", SHARD_TASKS="4")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("whose report stands, its end checking the study's report again in this job", done.stdout)
        self.assertEqual(report.read_text(encoding="utf-8"), kept)
        self.assertEqual(len(self.study_calls("merge")), 1)
        report.unlink()
        done = self.drr_gap_job("merge", job="702", PREPARE_JOB="501", SHARD_TASKS="4")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        lines = report.read_text(encoding="utf-8").splitlines()
        self.assertIn("- FAILED: the flow ended 0 and this job's work wrote no exit line: the launcher resumed a run of these"
                      " words whose finished step Metaflow cloned, but the report in the checkout is not that run's whole report", lines)
        self.assertTrue(lines[-1].startswith("- exit 1 at "), lines)
        done = self.drr_gap_job("prepare", job="503")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        lines = (self.steps() / "prepare.md").read_text(encoding="utf-8").splitlines()
        self.assertIn("- FAILED: the flow ended 0 and this job's work wrote no exit line: the launcher resumed a run of these"
                      " words whose finished step Metaflow cloned, though this prepare cleared analysis/PREPARED.json before"
                      " it began; send the word again for a new chain", lines)
        self.assertTrue(lines[-1].startswith("- exit 1 at "), lines)

    def test_a_drr_gap_merge_cut_after_its_work_ends_143_under_its_report(self):
        # Slurm's TERM after the merge's work ended 0 and while its flow's end checks the study's
        # report: the driver passes it on, the launcher ends, and the report the work wrote says why
        # beneath its exit 0 and ends with 143
        self.drr_gap_repo()
        self.drr_gap_inputs()
        self.assertEqual(self.drr_gap_job("prepare").returncode, 0)
        (self.fake / "launch_hang").write_text("", encoding="utf-8")
        env = dict(os.environ, PATH=f"{self.fake}:{os.environ['PATH']}", SCHWINGNET=str(self.repo), DATA_ROOT=str(self.data),
                   LAB_VOLUME=str(self.tmp), FAKE=str(self.fake), MODELS=str(self.models), STEP="merge", SLURM_JOB_ID="700",
                   PREPARE_JOB="501", SHARD_TASKS="4")
        for name in ("BENCH_ROOT", "INDEX", "SLURM_ARRAY_JOB_ID", "SLURM_ARRAY_TASK_ID", "SLURM_ARRAY_TASK_COUNT",
                     "SLURM_CPUS_PER_TASK", "OMP_NUM_THREADS", "TMPDIR", "SCHWINGNET_FLOW_STEP", "SN_CHECKOUT"):
            env.pop(name, None)
        started = time.monotonic()
        job = subprocess.Popen(["bash", str(self.repo / "grid" / "drr-gap.sbatch")], cwd=self.repo / "grid", env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            for _ in range(400):
                if (self.fake / "launch_hung").exists():
                    break
                time.sleep(0.05)
            self.assertTrue((self.fake / "launch_hung").exists(), "the stand-in flow never reached its end")
            os.kill(job.pid, signal.SIGTERM)
            output, _ = job.communicate(timeout=20)
        finally:
            job.kill()
        self.assertEqual(job.returncode, 143, output)
        self.assertLess(time.monotonic() - started, 20)
        self.assertIn("SN_BENCH_RC=143", output)
        lines = (self.repo / "grid" / "logs" / "BENCH-flexray_drr_gap.md").read_text(encoding="utf-8").splitlines()
        self.assertTrue(lines[-3].startswith("- exit 0 at "), lines[-4:])
        self.assertEqual(lines[-2], "- TERMINATED: Slurm ended the merge (its time, or a cancel), after the step's work ended 0 and"
                                    " before its flow's end wrote and checked the study's CLAIM and REFORMS report")
        self.assertTrue(lines[-1].startswith("- exit 143 at "), lines[-4:])

    def test_bench_flexray_drr_seg_refuses_each_missing_input_then_queues_one_gpu_job(self):
        # MOOSE's masks for the study's CTs are a bench id of their own, sent before flexray_drr_gap:
        # refused, naming one input a send, until the TotalSegmentator CTs, the SPINEPS masks (the
        # choice of CTs is made among them) and every one of the five model zips are on the volume;
        # then one GPU job, never requeued, and a second send while it is live is refused
        refused = self.gate("bench", "flexray_drr_seg")
        self.assertEqual(refused.returncode, 2, refused.stdout)
        self.assertIn("totalsegmentator_v201", refused.stdout)
        (self.data / "totalsegmentator_v201" / "s0001").mkdir(parents=True)
        refused = self.gate("bench", "flexray_drr_seg")
        self.assertEqual(refused.returncode, 2, refused.stdout)
        self.assertIn(f"the SPINEPS masks at {self.data}/spineps", refused.stdout)
        (self.data / "spineps").mkdir()
        zips = self.moose_zips()
        self.assertEqual(len(zips), 5, zips)
        refused = self.gate("bench", "flexray_drr_seg")
        self.assertEqual(refused.returncode, 2, refused.stdout)
        self.assertIn(f"MOOSE's model zip {zips[0]} under {self.data}/moose_weights/raw (fetch moose_weights first)", refused.stdout)
        self.moose_weights_landed(zips[:-1])
        refused = self.gate("bench", "flexray_drr_seg")
        self.assertEqual(refused.returncode, 2, refused.stdout)
        self.assertIn(f"MOOSE's model zip {zips[-1]} under", refused.stdout)
        self.assertEqual(self.submitted(), [])
        # while fetch moose_weights is still queued or running the zips may be landing: refused by
        # its job, as the fetch, explore and unpack words refuse beside a live fetch
        self.state_line(4242, "fetch:moose_weights", "dp_moose_weights")
        self.live(4242)
        self.moose_weights_landed(zips[-1:])
        refused = self.gate("bench", "flexray_drr_seg")
        self.assertEqual(refused.returncode, 2, refused.stdout)
        self.assertIn("needs the fetch of moose_weights to end: it is still queued or running (job 4242)", refused.stdout)
        self.live()
        # a zip there as a part, cut short or still landing under its final name, is no landed zip:
        # named, with the resend that resumes it, since [ -s ] passes it and the unpack would die
        self.moose_weights_landed(zips[-1:], cut=5)
        refused = self.gate("bench", "flexray_drr_seg")
        self.assertEqual(refused.returncode, 2, refused.stdout)
        self.assertIn(f"MOOSE's model zip {zips[-1]} under {self.data}/moose_weights/raw whole: what is there is a part,"
                      " still landing or cut short, which a resend of fetch moose_weights resumes", refused.stdout)
        self.moose_weights_landed(zips[-1:], cut=100)
        self.assertIn(f"MOOSE's model zip {zips[-1]} under {self.data}/moose_weights/raw whole", self.gate("bench", "flexray_drr_seg").stdout)
        self.assertEqual(self.submitted(), [])
        self.moose_weights_landed(zips[-1:])
        self.environments_ready()
        done = self.gate("bench", "flexray_drr_seg")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        lines = self.submitted()
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("--class gpu --name bench_flexray_drr_seg", lines[0])
        self.assertIn("BENCH=flexray_drr_seg", lines[0])
        self.assertIn(f"DATA_ROOT={self.data}", lines[0])
        self.assertIn("--no-requeue", lines[0])
        self.assertIn(" drr-seg.sbatch ", lines[0])
        self.assertNotIn("bench.sbatch", lines[0])
        job = self.recorded()["bench_flexray_drr_seg"]
        self.live(job)
        self.assertEqual(self.gate("bench", "flexray_drr_seg").returncode, 75)
        self.assertEqual(len(self.submitted()), 1)
        # a row the script cannot give back refuses the word rather than queue a job with no weights
        script = self.repo / "grid" / "run-platform-fetch.sh"
        script.write_text(script.read_text(encoding="utf-8").replace("moose_weights|url|", "moose_weights_gone|url|"), encoding="utf-8")
        (self.fake / "queue").write_text("", encoding="utf-8")
        refused = self.gate("bench", "flexray_drr_seg")
        self.assertEqual(refused.returncode, 2, refused.stdout)
        self.assertIn("the row moose_weights of grid/run-platform-fetch.sh was not read", refused.stdout)

    def drr_seg_job(self, **extra):
        """grid/drr-seg.sbatch as Slurm starts it, the driver, which starts the launcher; the stand-in
        box.sh plays the launcher and runs the body as DrrSegFlow's step does."""
        env = dict(os.environ, SCHWINGNET=str(self.repo), DATA_ROOT=str(self.data), LAB_VOLUME=str(self.tmp), FAKE=str(self.fake),
                   SLURM_JOB_ID="778", **extra)
        for name in ("BENCH_ROOT", "SCHWINGNET_FLOW_STEP", "SN_CHECKOUT"):
            env.pop(name, None)
        return subprocess.run(["bash", str(self.repo / "grid" / "drr-seg.sbatch")], cwd=self.repo / "grid", env=env,
                              capture_output=True, text=True, timeout=60)

    # what tools/flexray_render.py segment prints: its plan and its record as JSON, then one plain line
    SEGMENT_SAID = ('  echo "{"; echo \' "models": ["clin_ct_vertebrae"],\'; echo \' "subjects": [{"id": "s0001"}]\'; echo "}"\n'
                    '  echo "{"; echo \' "done": [{"id": "s0001"}]\'; echo "}"\n'
                    '  echo "segment: 2 subjects run, 5 models, 10 files found, 0 not found, written under $out"\n')

    def test_the_drr_seg_job_plans_the_subjects_then_runs_moose_on_them_with_the_fetched_weights(self):
        # grid/drr-seg.sbatch, its body run as DrrSegFlow's step: the moosez pin goes into the throwaway environment,
        # the study's plan subcommand chooses the CTs into the job's own folder (its log stays there
        # under umask 077), and the segment subcommand runs on exactly that file with the fetched zips
        # as its weights, writing under the data root's moose; the report carries the segment's one
        # summary line and not the JSON before it; a zip not there or not whole, or a plan that fails,
        # ends the job by name before any segmenter runs; the body checks the frozen PREREG first
        self.git_repo()
        self.freeze(b"# PREREG\n\nfrozen 2026-10-27, no further edits\n")
        (self.data / "totalsegmentator_v201" / "s0001").mkdir(parents=True)
        (self.data / "spineps").mkdir()
        zips = self.moose_zips()
        self.moose_weights_landed(zips)
        (self.repo / "grid" / "box.sh").write_text(
            '#!/bin/bash\necho "$*" >> "$FAKE/box.log"\n'
            + self.FAKE_LAUNCHER +
            'case "$*" in *" -m venv "*) mkdir -p "${@: -1}"; exit 0 ;; esac\n'
            'case "$*" in *"domain_gap.py plan "*) word=plan ;; *"flexray_render.py segment "*) word=segment ;; *) exit 0 ;; esac\n'
            'out=""; subjects=""; while [ $# -gt 0 ]; do [ "$1" = --out ] && out=$2; [ "$1" = --subjects ] && subjects=$2; shift; done\n'
            'if [ "$word" = plan ]; then\n'
            '  echo "render: totalsegmentator_v201: 2 CTs chosen of 3 with spineps masks, moose to be made"\n'
            '  [ ! -f "$FAKE/plan_fail" ] || { echo "drr-gap FAILED: no CT chosen for totalsegmentator_v201, token $(cat "$FAKE/plan_fail")"; exit 2; }\n'
            '  printf \'{"totalsegmentator_v201": ["s0001", "s0002"]}\\n\' > "$out/render-subjects.json"\n'
            'else\n'
            '  [ -f "$subjects" ] || { echo "no subjects file at $subjects"; exit 2; }\n'
            '  mkdir -p "$out/s0001" && echo mask > "$out/s0001/mask"\n'
            '  [ ! -f "$FAKE/segment_fail" ] || { echo "{"; echo "}"; echo "segment: refused: $(cat "$FAKE/segment_fail")" >&2; exit 2; }\n'
            + self.SEGMENT_SAID +
            'fi\n', encoding="utf-8")
        done = self.drr_seg_job()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        boxed = self.boxed()
        self.assertTrue([line for line in boxed if line.endswith("-m pip install --quiet moosez==3.2.2 flexray==1.0.2 nanodrr==0.1.5")], boxed)
        out = self.tmp / "go2432" / "bench" / "flexray_drr_seg"
        plans = [line for line in boxed if "tools/domain_gap.py plan " in line]
        self.assertEqual(len(plans), 1, boxed)
        self.assertTrue(plans[0].endswith(
            f"tools/domain_gap.py plan --groups data/domain_gap/groups.json --data-root {self.data} --out {out}"
            f" --frozen data/splits/test-persons.json --spineps {self.data}/spineps --moose {self.data}/moose"), plans[0])
        self.assertTrue(boxed[-1].endswith(
            f"tools/flexray_render.py segment --segmenter moose --ct-root {self.data}/totalsegmentator_v201"
            f" --subjects {out}/render-subjects.json --weights {self.data}/moose_weights/raw --out {self.data}/moose"), boxed[-1])
        self.assertLess(boxed.index(plans[0]), len(boxed) - 1)
        self.assertTrue((self.data / "moose" / "s0001" / "mask").is_file())
        # one launch of DrrSegFlow from the checkout, after the environment was made; the body left its
        # exit for the driver, which ended the report with it
        self.assertEqual((self.fake / "launch.log").read_text(encoding="utf-8").splitlines(),
                         [f"drr_seg --max-workers 1 -- --out {out} --masks {self.data}/moose | code={self.repo} checkout="])
        launched = [n for n, line in enumerate(boxed) if "flows/launch.py drr_seg " in line]
        self.assertEqual(len(launched), 1, boxed)
        self.assertLess(max(n for n, line in enumerate(boxed) if " -m pip install " in line), launched[0])
        self.assertLess(launched[0], boxed.index(plans[0]))
        self.assertEqual((out / "SEGMENT_RC").read_text(encoding="utf-8"), "0\n")
        self.assertIn("DRR_SEG_RC=0 1s", done.stdout)
        report = (self.repo / "grid" / "logs" / "BENCH-flexray_drr_seg.md").read_text(encoding="utf-8")
        self.assertIn(f"- environment: moosez==3.2.2 flexray==1.0.2 nanodrr==0.1.5; weights: {self.data}/moose_weights/raw; CTs: {self.data}/totalsegmentator_v201;"
                      f" masks: {self.data}/moose\n", report)
        self.assertIn(f"- results: {out}\n  segment: 2 subjects run, 5 models, 10 files found, 0 not found,"
                      f" written under {self.data}/moose\n- exit 0 at ", report)
        self.assertNotIn("models", report.split("- results:")[1].split("segment:")[0])
        self.assertNotIn('"done"', report)
        self.assertIn('"done": [{"id": "s0001"}]', done.stdout)
        # the plan's log stays in the job's folder, the owner's alone
        self.assertNotIn("CTs chosen", report + done.stdout)
        self.assertIn("2 CTs chosen", (out / "plan.log").read_text(encoding="utf-8"))
        self.assertEqual(out.stat().st_mode & 0o777, 0o700)
        self.assertEqual((out / "plan.log").stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.repo / "grid" / "logs" / "HOLD").exists())
        # a plan that chooses nothing: its last line in the report with a token masked, exit 2, no segmenter run
        token = "hf_" + "Cd" * 17
        (self.fake / "plan_fail").write_text(token, encoding="utf-8")
        done = self.drr_seg_job()
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("SN_BENCH_RC=2", done.stdout)
        report = (self.repo / "grid" / "logs" / "BENCH-flexray_drr_seg.md").read_text(encoding="utf-8")
        self.assertIn("- FAILED: domain_gap.py plan ended 2 (drr-gap FAILED: no CT chosen for totalsegmentator_v201, token <withheld>)", report)
        self.assertNotIn(token, report + done.stdout)
        self.assertEqual(len([line for line in self.boxed() if "flexray_render.py segment" in line]), 1)
        # a segment run that is refused: its last lines in the report, the refusal among them, masked
        (self.fake / "plan_fail").unlink()
        (self.fake / "segment_fail").write_text(f"no whole zip for token {token}", encoding="utf-8")
        done = self.drr_seg_job()
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        report = (self.repo / "grid" / "logs" / "BENCH-flexray_drr_seg.md").read_text(encoding="utf-8")
        self.assertIn("\n  {\n  }\n  segment: refused: no whole zip for token <withheld>\n- exit 2 at ", report)
        self.assertNotIn(token, report + done.stdout)
        (self.fake / "segment_fail").unlink()
        # a launcher that refuses before any flow runs: the segmentation left no exit, so the driver
        # ends the report with the launcher's code, and no segmenter ran
        (self.fake / "launch_refuse").write_text("PREREG.md moved", encoding="utf-8")
        segments = len([line for line in self.boxed() if "flexray_render.py segment" in line])
        done = self.drr_seg_job()
        self.assertEqual(done.returncode, 90, done.stdout + done.stderr)
        report = (self.repo / "grid" / "logs" / "BENCH-flexray_drr_seg.md").read_text(encoding="utf-8")
        self.assertIn("- FAILED: the launcher ended 90 and the segmentation left no exit (a refusal of the launcher's, or a"
                      " fault of the flow; the job's log says which)\n- exit 90 at ", report)
        self.assertEqual(len([line for line in self.boxed() if "flexray_render.py segment" in line]), segments)
        (self.fake / "launch_refuse").unlink()
        # a PREREG.md that moved: the body stops with 90 before the plan, and nothing is segmented
        self.freeze(b"# PREREG\n\nedited\n", hashed=b"# PREREG\n\nfrozen 2026-10-27, no further edits\n")
        plans = len([line for line in self.boxed() if "tools/domain_gap.py plan " in line])
        done = self.drr_seg_job()
        self.assertEqual(done.returncode, 90, done.stdout + done.stderr)
        report = (self.repo / "grid" / "logs" / "BENCH-flexray_drr_seg.md").read_text(encoding="utf-8")
        self.assertIn("- STOP: PREREG.md changed since the freeze\n- exit 90 at ", report)
        self.assertEqual(len([line for line in self.boxed() if "tools/domain_gap.py plan " in line]), plans)
        self.assertEqual(len([line for line in self.boxed() if "flexray_render.py segment" in line]), segments)
        self.freeze(b"# PREREG\n\nfrozen 2026-10-27, no further edits\n")
        # the record an earlier run left beside the masks is kept in this job's folder before the
        # segment subcommand writes its own over it, the owner's alone
        (self.data / "moose" / "SEGMENT.json").write_text('{"done": ["s0001"]}\n', encoding="utf-8")
        done = self.drr_seg_job()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        kept = out / "SEGMENT-before-job-778.json"
        self.assertEqual(kept.read_text(encoding="utf-8"), '{"done": ["s0001"]}\n')
        self.assertEqual(kept.stat().st_mode & 0o777, 0o600)
        report = (self.repo / "grid" / "logs" / "BENCH-flexray_drr_seg.md").read_text(encoding="utf-8")
        self.assertIn(f"- kept: the masks' earlier SEGMENT.json as {kept}, since this run writes its own\n", report)
        # a flow whose end fails after the segmentation ended 0: the launcher's code ends the job, and
        # the report says the masks stand
        (self.fake / "launch_after").write_text("1", encoding="utf-8")
        done = self.drr_seg_job()
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("SN_BENCH_RC=1", done.stdout)
        report = (self.repo / "grid" / "logs" / "BENCH-flexray_drr_seg.md").read_text(encoding="utf-8")
        self.assertIn("- FAILED: the segmentation ended 0, but its flow ended 1: its end failed after the work (the job's log"
                      " and the run's page say why); the masks it wrote stand\n- exit 1 at ", report)
        (self.fake / "launch_after").unlink()
        # a resume whose finished segment step Metaflow cloned: no segmentation in this job, the flow's 0
        segments = len([line for line in self.boxed() if "flexray_render.py segment" in line])
        (self.fake / "launch_cloned").write_text("", encoding="utf-8")
        done = self.drr_seg_job()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        report = (self.repo / "grid" / "logs" / "BENCH-flexray_drr_seg.md").read_text(encoding="utf-8")
        self.assertIn("- segment: the flow ended 0 and this job's segmentation left no exit: the launcher resumed a run whose"
                      " finished segment step Metaflow cloned, so the masks are that run's\n- exit 0 at ", report)
        self.assertEqual(len([line for line in self.boxed() if "flexray_render.py segment" in line]), segments)
        (self.fake / "launch_cloned").unlink()
        # a zip the fetch has not landed: named with its fetch, before the environment or the plan
        (self.data / "moose_weights" / "raw" / zips[2]).unlink()
        before = len(self.boxed())
        done = self.drr_seg_job()
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        report = (self.repo / "grid" / "logs" / "BENCH-flexray_drr_seg.md").read_text(encoding="utf-8")
        self.assertIn(f"- FAILED: no {zips[2]} under {self.data}/moose_weights/raw (fetch moose_weights first)", report)
        self.assertEqual(len(self.boxed()), before)
        self.assertFalse((self.repo / "grid" / "logs" / "HOLD").exists())
        # a zip there as a part, cut short or still landing: named too, with the resend that resumes it,
        # since the gate's check may be hours old by the time the job starts
        self.moose_weights_landed(zips[2:3], cut=7)
        done = self.drr_seg_job()
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        report = (self.repo / "grid" / "logs" / "BENCH-flexray_drr_seg.md").read_text(encoding="utf-8")
        self.assertIn(f"- FAILED: {zips[2]} under {self.data}/moose_weights/raw is not a whole zip (a part still landing or"
                      " cut short, which a resend of fetch moose_weights resumes)", report)
        self.assertEqual(len(self.boxed()), before)
        self.assertFalse((self.repo / "grid" / "logs" / "HOLD").exists())

    @unittest.skipUnless(shutil.which("unzip"), "the node's unzip tests the members; none here")
    def test_the_drr_seg_job_refuses_a_zip_whole_by_its_record_whose_member_unzip_finds_damaged(self):
        # a zip resumed across two uploads of the asset ends in a whole record and [ -s ] and the
        # record's check both pass it, while unzip's test of every member's CRC does not, where the
        # node has unzip: the job names it, and says what a resend would not mend
        self.git_repo()
        (self.data / "totalsegmentator_v201" / "s0001").mkdir(parents=True)
        (self.data / "spineps").mkdir()
        zips = self.moose_zips()
        self.moose_weights_landed(zips)
        damaged = self.data / "moose_weights" / "raw" / zips[1]
        data = bytearray(damaged.read_bytes())
        start = data.index(b"{}\n")
        data[start:start + 3] = b"!!\n"
        damaged.write_bytes(bytes(data))
        self.assertTrue(zipfile.is_zipfile(damaged))
        done = self.drr_seg_job()
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        report = (self.repo / "grid" / "logs" / "BENCH-flexray_drr_seg.md").read_text(encoding="utf-8")
        self.assertIn(f"- FAILED: {zips[1]} under {self.data}/moose_weights/raw is whole by its record but unzip finds a member"
                      " damaged (a download resumed across two uploads of the asset, say): delete it in the grid's shell and"
                      " resend fetch moose_weights, which lands it again", report)
        self.assertEqual(self.boxed(), [])

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

    def test_literature_queues_once_then_prints_and_keeps_its_report(self):
        # a list the checkout does not hold, and a malformed send, are refused and queue nothing
        self.assertEqual(self.gate("literature", "no_such_list").returncode, 64)
        self.assertEqual(self.gate("literature", "a", "b").returncode, 64)
        self.assertEqual(self.gate("literature", "Bad-List").returncode, 64)
        self.assertEqual(self.submitted(), [])
        done = self.gate("literature", "synthetic_spine")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        lines = self.submitted()
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("--class batch --name literature", lines[0])
        self.assertIn("literature.sbatch", lines[0])
        self.assertIn("LIST_ID=synthetic_spine", lines[0])
        self.assertIn(f"DATA_ROOT={self.data}", lines[0])
        job = self.recorded()["literature"]
        # while it is live, a second send is refused
        self.live(job)
        self.assertEqual(self.gate("literature", "synthetic_spine").returncode, 75)
        self.assertEqual(len(self.submitted()), 1)
        # once it has ended, its report is printed once, kept under its job's number, and nothing is queued
        (self.fake / "queue").write_text("", encoding="utf-8")
        logs = self.repo / "grid" / "logs"
        report = logs / "LITERATURE-synthetic_spine.md"
        report.write_text(f"# literature synthetic_spine: job {job} on node1, commit abc1234, 2026-10-28 01:00:00 UTC\n"
                          "- bach2019: not got; Elsevier: not entitled to the full text under the key and insttoken\n"
                          "- exit 0 at 2026-10-28 01:05:00 UTC\n", encoding="utf-8")
        done = self.gate("literature", "synthetic_spine")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("- bach2019: not got; Elsevier: not entitled to the full text under the key and insttoken", done.stdout)
        self.assertEqual(len(self.submitted()), 1)
        self.assertFalse(report.exists())
        self.assertTrue((logs / f"LITERATURE-synthetic_spine-{job}.md").exists())
        # and the send after that fetches again what is still missing
        self.assertEqual(self.gate("literature", "synthetic_spine").returncode, 0)
        self.assertEqual(len(self.submitted()), 2)
        # a job killed before it wrote its exit leaves its report unfinished: printed and kept, nothing queued
        (self.fake / "queue").write_text("", encoding="utf-8")
        part = logs / "LITERATURE-synthetic_spine.md.part"
        part.write_text("# literature synthetic_spine: job 4242 on node1, commit abc1234, 2026-10-28 02:00:00 UTC\n"
                        "- admitted under the size rule: 400000000 bytes at most\n", encoding="utf-8")
        done = self.gate("literature", "synthetic_spine")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("unfinished: the job ended before it wrote its exit", done.stdout)
        self.assertIn("admitted under the size rule", done.stdout)
        self.assertEqual(len(self.submitted()), 2)
        self.assertFalse(part.exists())
        self.assertTrue((logs / "LITERATURE-synthetic_spine-4242-unfinished.md").exists())

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
        self.cover_plans()
        return folder / f"{name}.json"

    def cover_plans(self, *uncovered, by_name=()):
        """The registry's sweep line and the sweep's PREREG frozen as the Lab Recipe says, covering
        every plan under the test's grid/sweeps/ by its bytes, but those uncovered and those it
        covers by name alone, as the word reads them before it queues anything."""
        (self.repo / "flows").mkdir(exist_ok=True)
        shutil.copy(ROOT / "flows" / "registry.txt", self.repo / "flows" / "registry.txt")
        entries = []
        for plan in sorted((self.repo / "grid" / "sweeps").glob("*.json")):
            if plan.stem in by_name:
                entries.append(plan.stem)
            elif plan.stem not in uncovered:
                entries.append(f"{plan.stem}={hashlib.sha256(plan.read_bytes()).hexdigest()}")
        prereg = self.repo / "docs" / "research" / "block-smoke"
        prereg.mkdir(parents=True, exist_ok=True)
        text = f"# The test's design\n\nCovers: {', '.join(entries)}\n"
        (prereg / "PREREG.md").write_text(text, encoding="utf-8")
        (prereg / "PREREG.md.sha256").write_text(f"{hashlib.sha256(text.encode()).hexdigest()}  PREREG.md\n", encoding="ascii")
        return prereg / "PREREG.md"

    def test_sweep_refuses_a_plan_its_frozen_prereg_does_not_cover_before_anything_is_queued(self):
        # the launcher refuses such a plan with exit 90 too, but only once the job holds a GPU and the
        # catalog is built; the word reads the same Covers line first and queues nothing
        self.environments_ready()
        self.plan("synthetic", "synthetic")
        self.plan("trials", "synthetic")
        self.cover_plans("trials")
        done = self.gate("sweep", "trials")
        self.assertEqual(done.returncode, 90, done.stdout)
        self.assertIn("refusing: docs/research/block-smoke/PREREG.md does not cover the plan trials, which waits for a PREREG "
                      "of its own, frozen before it runs; nothing was queued", done.stdout)
        # a plan edited since the freeze, under the same name, is another design
        plan = self.repo / "grid" / "sweeps" / "synthetic.json"
        frozen = hashlib.sha256(plan.read_bytes()).hexdigest()
        plan.write_text(plan.read_text(encoding="utf-8").replace('"epochs": 3', '"epochs": 4'), encoding="utf-8")
        done = self.gate("sweep", "synthetic")
        self.assertEqual(done.returncode, 90, done.stdout)
        self.assertIn(f"covers synthetic as the bytes of sha256 {frozen[:16]}, and grid/sweeps/synthetic.json's are "
                      f"{hashlib.sha256(plan.read_bytes()).hexdigest()[:16]}: a plan changed since the freeze is another design", done.stdout)
        # a PREREG edited since its freeze covers nothing
        prereg = self.cover_plans()
        with prereg.open("a", encoding="utf-8") as text:
            text.write("A hypothesis added after the data were seen.\n")
        done = self.gate("sweep", "synthetic")
        self.assertEqual(done.returncode, 90, done.stdout)
        self.assertIn("refusing: STOP: docs/research/block-smoke/PREREG.md is not frozen as its PREREG.md.sha256 says", done.stdout)
        self.assertEqual(self.submitted(), [])
        # an entry that names the plan alone covers it whatever its bytes, as the launcher reads it
        self.cover_plans(by_name=("synthetic",))
        done = self.gate("sweep", "synthetic")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(len(self.line_of("sweep-driver.sbatch")), 1)

    def test_the_repositorys_own_prereg_covers_its_smoke_plans_and_not_the_trials(self):
        self.environments_ready()
        (self.repo / "flows").mkdir()
        shutil.copy(ROOT / "flows" / "registry.txt", self.repo / "flows" / "registry.txt")
        shutil.copytree(ROOT / "docs" / "research" / "block-smoke", self.repo / "docs" / "research" / "block-smoke")
        done = self.gate("sweep", "trials")
        self.assertEqual(done.returncode, 90, done.stdout)
        self.assertIn("does not cover the plan trials", done.stdout)
        done = self.gate("sweep", "synthetic")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(len(self.line_of("sweep-driver.sbatch")), 1)

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

    def chain_env(self, **extra):
        """The X-ray chain's bank job, 4242, with stand-ins for the bank tool, whose frames' bound is a
        byte, the ingest and the launcher, which notes what it was given and runs nothing."""
        pydrv = self.fake / "step-pydrv"
        pydrv.write_text('#!/bin/bash\ncase "$1" in\n'
                         '  */tools/bank.py) case " $* " in *" --run "*) echo "$*" >> "$FAKE/banked"; echo "{}" ;;'
                         ' *) echo \'{"most_bytes": 1}\' ;; esac ;;\n'
                         '  */tools/ingest.py) echo \'{"shard": "s1", "outcome": "new", "frames_kept": 3, "persons": 2, '
                         '"labels": 0}\' ;;\n'
                         '  */flows/launch.py) printf \'%s\\n\' "$@" > "$FAKE/launched" ;;\n'
                         '  *) exec python3 "$@" ;;\nesac\n', encoding="utf-8")
        pydrv.chmod(0o755)
        env = dict(self.gate_env(), GETFATTR=str(self.fake / "getfattr"), PYDRV=str(pydrv), SLURM_JOB_ID="4242",
                   ONLY="nih_chestxray14", VOLUME=str(self.tmp))
        for name in ("BANK_NEED", "SCHWINGNET_FLOW_STEP", "PART", "SLURM_RESTART_COUNT"):
            env.pop(name, None)
        env.update(extra)
        return env

    def chain_bank_job(self, **extra):
        """The chain's bank job as Slurm starts it: every recipe decided, then the launcher."""
        (self.fake / "launched").unlink(missing_ok=True)
        return subprocess.run(["bash", str(self.repo / "grid" / "02-bank-ingest.sbatch")], cwd=self.repo / "grid",
                              env=self.chain_env(**extra), capture_output=True, text=True, timeout=60)

    def chain_bank_step(self, part, **extra):
        """One step of the X-ray chain's bank job as BankFlow runs it: one recipe and one half."""
        return subprocess.run(["bash", str(self.repo / "grid" / "02-bank-ingest.sbatch")], cwd=self.repo / "grid",
                              env=self.chain_env(SCHWINGNET_FLOW_STEP="1", PART=part, **extra), capture_output=True,
                              text=True, timeout=60)

    def banked(self):
        path = self.fake / "banked"
        return path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    def test_the_chains_bank_job_decides_each_recipe_before_the_launcher_against_its_hold(self):
        # #163: the fetch job left 200 GB held for the set's bank with the chain's bank job, 4242,
        # twice the 100 GB the PNG set landed; the job decides the recipe before the launcher, on
        # the node, the hold set aside for it and every other set still counted, and the step banks
        # it only where the job admitted it
        self.ceph_fake(raw_bytes=100 * 10**9)
        (self.data / "nih_chestxray14" / "raw").mkdir(parents=True)
        (self.data / "nih_chestxray14" / "raw" / "a.png").write_bytes(b"p")
        size = self.data / "nih_chestxray14" / "meta" / "SIZE"
        size.parent.mkdir(parents=True)
        hold = "admitted 4242 200000000000 2600000000000 2026-10-25T21:00:00Z 200000000000 hold\n"
        size.write_text(hold, encoding="utf-8")
        # a fetch admitted since owes 8600 GB of the 8844 GB room: 244 GB left, which the hold
        # would leave 44 of were it counted against its own recipe
        other = self.data / "other_set" / "meta"
        other.mkdir(parents=True)
        (other / "SIZE").write_text("admitted 555 8600000000000 2600000000000 2026-10-25T00:00:00Z 8600000000000\n",
                                    encoding="utf-8")
        self.live(555, 4242)
        report = self.repo / "grid" / "logs" / "02-bank-ingest-STAGE-REPORT.md"
        done = self.chain_bank_job()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("nih_chestxray14: admitted; it needs 200 gb of its 200 gb by the bank and its shard and 245 gb is free",
                      done.stdout)
        self.assertTrue(size.read_text(encoding="utf-8").startswith("admitted 4242 200000000000 2600000000000 "))
        self.assertNotIn("hold", size.read_text(encoding="utf-8"))
        # the launcher is given every recipe the job was sent, and nothing is banked before it
        launched = (self.fake / "launched").read_text(encoding="utf-8").splitlines()
        self.assertEqual(launched[launched.index("--sources") + 1], "nih_chestxray14")
        self.assertEqual(self.banked(), [])
        # the step banks what the job admitted, deciding nothing itself
        done = self.chain_bank_step("bank")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertNotIn("admitted;", done.stdout)
        self.assertEqual(len(self.banked()), 1)
        self.assertTrue(size.read_text(encoding="utf-8").startswith("admitted 4242 200000000000 2600000000000 "))
        # requeued by Slurm, the job keeps what it was given
        done = self.chain_bank_job(SLURM_RESTART_COUNT="1")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("nih_chestxray14: admitted already; job 4242 restarted", done.stdout)
        # the ingest half done, the recipe holds no more room
        done = self.chain_bank_step("ingest")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertTrue(size.read_text(encoding="utf-8").startswith("settled 4242 "))
        self.assertIn("- nih_chestxray14: s1 new 3 frames, 2 persons, 0 labels", report.read_text(encoding="utf-8"))
        # another recipe's hold by the same job counts: 50 GB more leaves 194 GB, and the recipe is
        # refused and frees its hold, while the other hold stands; the step then banks nothing of
        # it and its report line says why
        size.write_text(hold, encoding="utf-8")
        lumos = self.data / "lumos" / "meta"
        lumos.mkdir(parents=True)
        (lumos / "SIZE").write_text("admitted 4242 50000000000 2600000000000 2026-10-25T21:00:00Z 50000000000 hold\n",
                                    encoding="utf-8")
        done = self.chain_bank_job()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("nih_chestxray14: refused for space; it needs 200 gb of its 200 gb by the bank and its shard and only "
                      "194 gb is free", done.stdout)
        self.assertTrue(size.read_text(encoding="utf-8").startswith("settled 4242 "))
        self.assertTrue((lumos / "SIZE").read_text(encoding="utf-8").endswith(" hold\n"))
        done = self.chain_bank_step("bank")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("nih_chestxray14: not banked; the size rule refused its bank for space at 20", done.stdout)
        self.assertIn("- nih_chestxray14: bank refused: the size rule refused its bank for space at 20", report.read_text(encoding="utf-8"))
        self.assertIn("; it needs 200 gb and only 194 gb was free", report.read_text(encoding="utf-8"))
        self.assertEqual(len(self.banked()), 1)
        # a raw copy whose size cannot be read is refused before anything is banked
        size.write_text(hold, encoding="utf-8")
        (self.fake / "raw_bytes").write_text("", encoding="utf-8")
        done = self.chain_bank_job()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("nih_chestxray14: refused; the room its bank needs could not be reckoned from its recipe and raw copy",
                      done.stdout)
        self.assertTrue(size.read_text(encoding="utf-8").startswith("settled 4242 "))
        done = self.chain_bank_step("bank")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("- nih_chestxray14: bank refused: the size rule refused its bank at 20", report.read_text(encoding="utf-8"))
        self.assertEqual(len(self.banked()), 1)
        # a recipe the job never decided, its raw copy fetched after the job started, is banked by no step
        (self.data / "nih_chestxray14" / "meta" / "REFUSED").unlink()
        size.unlink()
        done = self.chain_bank_step("bank")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("- nih_chestxray14: bank refused: the size rule did not decide its bank in this job", report.read_text(encoding="utf-8"))
        self.assertEqual(len(self.banked()), 1)

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
        that file is there; while $FAKE/launch_holds is there it runs until a TERM comes, says it
        came in $FAKE/stopped and ends as the launcher ends then, with 143."""
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
    if [ -f "$FAKE/launch_holds" ]; then
      sleep 60 & flow=$!
      trap 'kill "$flow"; echo TERM >> "$FAKE/stopped"; echo "{\"flow\": \"sweep\", \"run\": \"SweepFlow/12\", \"successful\": false, \"verdict\": null}"; exit 143' TERM
      touch "$FAKE/launch_held"
      wait "$flow"
    fi
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

    def test_job_submits_early_term_reaches_the_launcher_at_once_and_the_report_still_says_how_it_ended(self):
        # job submit sends TERM to the batch shell alone two minutes before the limit; a shell
        # running the launcher in its foreground held it until the launcher ended, so the launcher
        # heard only Slurm's own TERM at the limit
        self.git_repo()
        self.sweep_box()
        self.plan("synthetic", "synthetic")
        catalog = self.synthetic_catalog()
        (self.fake / "launch_holds").write_text("", encoding="utf-8")
        env = dict(os.environ, SCHWINGNET=str(self.repo), DATA_ROOT=str(self.data), SMOKE=str(self.smoke), FAKE=str(self.fake),
                   MODELS=str(self.models), PLAN="synthetic", SLURM_JOB_ID="777", FAKE_CATALOG=str(catalog))
        for name in ("STORE", "WEIGHTS"):
            env.pop(name, None)
        driver = subprocess.Popen(["bash", str(self.repo / "grid" / "sweep-driver.sbatch")], cwd=self.repo / "grid", env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.addCleanup(driver.kill)
        for _ in range(300):
            if (self.fake / "launch_held").exists():
                break
            time.sleep(0.1)
        began = time.monotonic()
        driver.send_signal(signal.SIGTERM)
        out, _ = driver.communicate(timeout=60)
        self.assertLess(time.monotonic() - began, 30, "the TERM reached the launcher before its flow ended on its own")
        self.assertEqual(driver.returncode, 143, out)
        self.assertEqual((self.fake / "stopped").read_text(encoding="utf-8"), "TERM\n")
        self.assertIn("SN_SWEEP_RC=143", out)
        report = (self.repo / "grid" / "logs" / "sweep-synthetic-STAGE-REPORT.md").read_text(encoding="utf-8")
        self.assertIn('- Metaflow: {"flow": "sweep", "run": "SweepFlow/12", "successful": false', report)
        self.assertIn("- launcher exited 143\n", report)
        self.assertFalse((self.repo / "grid" / "logs" / "HOLD").exists())

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
