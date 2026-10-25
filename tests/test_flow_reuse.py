"""tools/flow.py names a run by what it computes and carries a cut-short run on in its own folder.

The run id is the hash of the digest of the code the run executes (tools/run_code.py), the
catalog and the run's configuration (CONFIGURATION.json), so the same configuration names the same
folder, on a later commit that changed none of that code too, and started again the flow runs
only what that folder still needs: nothing once it wrote FINISHED.json, its last file; the last push, the ledger
row (once) and the report where it was cut after its evaluation; the evaluation where training
wrote its checkpoint.json and the best.pt it names, training again, with --resume where it left
train/last.pt, where it did not (issue #252). A sweep's row
names its folder with --slug, and a folder holding another run is refused and left as it was. A
start cut while it writes its record or witness list, or before its record, is started again,
and a start while another start holds the folder is refused and runs nothing. In slurm mode,
against tests/fakes/hpcworker and a fake sacct, a job is in RUN.json from the moment it is
submitted, so a start cut while the job waits leaves it for the next start to wait on.

The flow runs in-process against a real synthetic catalog built by the tools, with a fake `pixi`
on PATH standing in for the trainer, the evaluator and the W&B sync: it writes the files the flow
reads after each step and logs what it was asked, so the test sees which steps ran and with what.
The flow refuses a dirty tree, and the working copy under test may hold uncommitted changes, so
tree_state is replaced in-process by a clean tree at a fixed commit, and code_state, where a test
says, by a fixed digest; that refusal itself is tested
in tests/schwingnet/test_flow.py. flow.py imports the package, so the test skips where pydantic,
beartype or icontract is missing, as under the required check's plain python3.
"""

import contextlib
import errno
import hashlib
import importlib.util
import io
import json
import multiprocessing
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
NEEDED = ("pydantic", "beartype", "icontract")
MISSING = [name for name in NEEDED if importlib.util.find_spec(name) is None]
COMMIT = "0123456789abcdef0123456789abcdef01234567"
LATER = "89abcdef0123456789abcdef0123456789abcdef"
LEGACY_RUN = ROOT / "docs" / "research" / "v1-demo" / "runs" / "a767a466f5c1"
V1_DRIVER_SED = r's/.*"run_dir": "\([^"]*\)".*/\1/p'

# The fake pixi: `pixi run --locked -e ENV python tools/NAME.py ARGS` writes what the real step
# writes that the flow reads, and logs one JSON line per call. FAKE_TRAIN=cut leaves train/last.pt
# and exits as a killed job does; FAKE_EVALUATE=fail exits before writing results.
FAKE_PIXI = r'''#!{python}
import hashlib, json, os, sys
from pathlib import Path

words = sys.argv[1:]
assert words[0] == "run", words
rest = words[1:]
env = "default"
while rest and rest[0] in ("--locked", "-e"):
    if rest[0] == "-e":
        env = rest[1]
        rest = rest[2:]
    else:
        rest = rest[1:]
assert rest[0] == "python", rest
tool, args = Path(rest[1]).stem, rest[2:]
with open(os.environ["FAKE_PIXI_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps({{"env": env, "tool": tool, "args": args}}) + "\n")


def value(flag):
    return args[args.index(flag) + 1]


if tool == "train":
    train = Path(value("--out")) / "train"
    train.mkdir(parents=True, exist_ok=True)
    if "--resume" in args and not (train / "last.pt").is_file():
        print("train: --resume needs train/last.pt")
        raise SystemExit(1)
    if os.environ.get("FAKE_TRAIN") == "cut":
        (train / "last.pt").write_bytes(b"epoch 1")
        print("epoch 1 done, then the job was killed")
        raise SystemExit(137)
    (train / "best.pt").write_bytes(b"the weights of epoch 2")
    named = hashlib.sha256(b"the weights of epoch 2").hexdigest()
    (train / "checkpoint.json").write_text(json.dumps({{"best": {{"epoch": 2, "validation_accuracy": 0.5}}, "checkpoint_sha256": named}}), encoding="utf-8")
    (train / "last.pt").unlink(missing_ok=True)
    print("trained" + (" on from train/last.pt" if "--resume" in args else ""))
elif tool == "evaluate":
    if os.environ.get("FAKE_EVALUATE") == "fail":
        print("the evaluation failed")
        raise SystemExit(1)
    evaluate = Path(value("--run")) / "evaluate"
    evaluate.mkdir(parents=True, exist_ok=True)
    (evaluate / "results.json").write_text(json.dumps({{"headline": {{"correct": 1, "total": 2}}}}), encoding="utf-8")
    (evaluate / "results.md").write_text("| accuracy | 1/2 |\n", encoding="utf-8")
elif tool == "wandb_log":
    print("W&B offline only, nothing to push (fake)")
else:
    raise SystemExit(f"the fake pixi knows no tool {{tool}}")
'''


# sacct as the flow asks it, `sacct -j ID -n -P -X --format=State,Elapsed,ExitCode`: the line the
# test wrote for the job under FAKE_SACCT, PENDING where it wrote none.
FAKE_SACCT = r'''#!/bin/bash
if [ -f "$FAKE_SACCT/$2" ]; then cat "$FAKE_SACCT/$2"; else echo "PENDING|00:00:00|0:0"; fi
'''


def python(*args):
    done = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, timeout=600)
    if done.returncode != 0:
        raise AssertionError(f"{args}: {done.stdout}\n{done.stderr}")
    return done.stdout


def make_catalog(tmp):
    """A small synthetic catalog, built by the tools as tests/test_train_blocks.py builds one."""
    python(ROOT / "tools" / "synthetic_bank.py", tmp / "bank", "--frames", "30", "--cases", "6", "--seed", "3")
    python(ROOT / "tools" / "ingest.py", "run", "--bank", tmp / "bank", "--source", "carmlspine", "--kind", "train",
           "--date", "2026-10-24", "--code-commit", "0" * 40, "--grid-root", tmp / "carmlspine")
    manifests = []
    for manifest in sorted((tmp / "carmlspine").rglob("MANIFEST.json")):
        manifests += ["--manifest", manifest]
    built = json.loads(python(ROOT / "tools" / "catalog.py", "build", "--store", tmp / "store", *manifests, "--root", tmp))
    return tmp / "store" / "versions" / built["file"]


def load_flow():
    # tools/flow.py puts src on the path; beethoven_qa comes from the vendored copy, as the pixi
    # environment's activation puts it there.
    for path in (ROOT / "vendor" / "beethoven-qa" / "src", ROOT / "src"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    spec = importlib.util.spec_from_file_location("flow_reuse_under_test", ROOT / "tools" / "flow.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Killed(Exception):
    """What a patched write raises, as a job killed at that write would stop."""


def write_cut_short(names, at, error=None):
    """Path.write_text made to write half its text to a file of these names and stop, at the
    at-th write to them, as a full volume or a kill mid-write leaves a file, raising error where
    one is given and Killed otherwise; every other write is the real one."""
    real, seen = Path.write_text, []

    def write_half(path, text, *args, **kwargs):
        if path.name in names:
            seen.append(path.name)
            if len(seen) == at:
                real(path, text[: len(text) // 2], *args, **kwargs)
                raise error or Killed(f"cut while writing {path.name}")
        return real(path, text, *args, **kwargs)

    return mock.patch.object(Path, "write_text", write_half)


def legacy_record(rules, started_at):
    """A run record named by its start, as the records written before configurations were named
    are, which needs no catalog or code to make: a ledger row's facts and nothing else."""
    return rules.RunRecord(run_id=rules.run_id(COMMIT, "a" * 64, started_at), code_commit=COMMIT, clean_tree=True,
                           catalog_version=1, catalog_sha256="a" * 64, split_disjoint=True, stage=rules.Stage.LEVEL,
                           seed=1, epochs=1, started_at=started_at, mode="local")


def write_rows(flow, ledger, records, barrier):
    """One writer's rows, started with the other writer's at the barrier, as the rows of a sweep
    run side by side finish into one ledger; the flow's own call, the one finish makes."""
    barrier.wait()
    for record in records:
        flow.add_ledger_row(ledger, record, "a row of a sweep", "by the test")


def snapshot(folder):
    """Every file under a folder with its bytes and modification time, to see that nothing moved."""
    return {str(p.relative_to(folder)): (p.read_bytes(), p.stat().st_mtime_ns) for p in sorted(folder.rglob("*")) if p.is_file()}


@unittest.skipIf(MISSING, f"needs the package's dependencies ({', '.join(MISSING)} missing)")
class FlowReuseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.catalog = make_catalog(cls.tmp / "catalog")
        cls.flow = load_flow()
        from schwingnet import flow as rules

        cls.rules = rules
        cls.bin = cls.tmp / "bin"
        cls.bin.mkdir()
        (cls.bin / "pixi").write_text(FAKE_PIXI.format(python=sys.executable), encoding="utf-8")
        (cls.bin / "pixi").chmod(0o755)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(dir=self.tmp))
        self.out = self.work / "runs"
        self.log = self.work / "pixi.jsonl"

    def run_flow(self, *extra, fake=None, commit=COMMIT, code=None):
        """tools/flow.py run in local mode on the catalog, on the commit and, where one is given,
        the code digest; its exit code, stdout lines and stderr."""
        argv = ["run", "--catalog", str(self.catalog), "--out", str(self.out), "--mode", "local",
                "--epochs", "2", "--seed", "1", "--size", "32", *extra]
        environ = {"PATH": f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}", "FAKE_PIXI_LOG": str(self.log),
                   "SCHWINGNET_WANDB": "off", "FAKE_TRAIN": "", "FAKE_EVALUATE": "", **(fake or {})}
        stdout, stderr = io.StringIO(), io.StringIO()
        code_state = (lambda: code) if code else self.flow.code_state
        with mock.patch.dict(os.environ, environ), mock.patch.object(self.flow, "tree_state", lambda: (commit, True)), \
                mock.patch.object(self.flow, "code_state", code_state), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            rc = self.flow.main(argv)
        return rc, stdout.getvalue().splitlines(), stderr.getvalue()

    def calls(self):
        """What the fake pixi was asked, in order, as (tool, args)."""
        if not self.log.is_file():
            return []
        return [(c["tool"], c["args"]) for c in map(json.loads, self.log.read_text(encoding="utf-8").splitlines())]

    def tools_called(self):
        return [tool for tool, _ in self.calls()]

    def said(self, lines):
        """The flow's line naming the run, which the v1 driver and the sweep read."""
        named = [json.loads(line) for line in lines if line.startswith("{") and '"run_dir"' in line]
        self.assertEqual(len(named), 1, lines)
        return named[0]

    def record(self, run_dir):
        return json.loads((run_dir / "RUN.json").read_text(encoding="utf-8"))

    def ledger_rows(self):
        ledger = self.out / "LEDGER.md"
        return ledger.read_text(encoding="utf-8").splitlines()[2:] if ledger.is_file() else []

    def test_the_same_configuration_names_the_same_folder_and_the_second_call_does_nothing(self):
        rc, lines, err = self.run_flow()
        self.assertEqual(rc, 0, err)
        first = self.said(lines)
        run_dir = Path(first["run_dir"])
        self.assertEqual((run_dir.parent, run_dir.name), (self.out, first["run_id"]))
        self.assertNotIn("reused", first)
        self.assertEqual(self.tools_called(), ["train", "wandb_log", "evaluate", "wandb_log", "wandb_log"])
        self.assertEqual(len(self.ledger_rows()), 1)
        before = snapshot(self.out)
        rc, lines, err = self.run_flow()
        self.assertEqual(rc, 0, err)
        again = self.said(lines)
        self.assertEqual((again["run_id"], again["run_dir"], again["reused"]), (first["run_id"], first["run_dir"], "finished"))
        self.assertEqual(len(self.calls()), 5, "nothing ran the second time")
        self.assertEqual(snapshot(self.out), before, "nothing was written the second time, no ledger row among it")
        # The v1 driver reads the run's folder from the first line that names one, finished or not.
        found = subprocess.run(["sed", "-n", V1_DRIVER_SED], input="\n".join(lines) + "\n", capture_output=True, text=True, check=True)
        self.assertEqual(found.stdout.splitlines()[0], first["run_dir"])

    def test_the_configuration_is_written_and_its_hash_names_the_run(self):
        rc, lines, err = self.run_flow("--block", "optimiser=adamw", "--block", "weight_decay=0.01", "--max-frames", "9")
        self.assertEqual(rc, 0, err)
        run_dir = Path(self.said(lines)["run_dir"])
        text = (run_dir / "CONFIGURATION.json").read_text(encoding="utf-8")
        configuration = json.loads(text)
        self.assertEqual(text, json.dumps(configuration, indent=1, sort_keys=True) + "\n")
        self.assertEqual(sorted(configuration), ["blocks", "environment", "epochs", "init_sha256", "max_frames", "recipe", "seed", "size", "stage", "weights_sha256"])
        self.assertEqual((configuration["epochs"], configuration["seed"], configuration["size"], configuration["max_frames"]), (2, 1, 32, 9))
        self.assertEqual((configuration["stage"], configuration["environment"], configuration["recipe"]), ("level", "train-cpu", None))
        self.assertEqual((configuration["blocks"]["optimiser"], configuration["blocks"]["weight_decay"]), ("adamw", 0.01))
        self.assertIsNone(configuration["weights_sha256"])
        digest = hashlib.sha256(json.dumps(configuration, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        record = self.record(run_dir)
        self.assertEqual(record["configuration_sha256"], digest)
        catalog_sha256 = hashlib.sha256(self.catalog.read_bytes()).hexdigest()
        self.assertEqual(record["code_sha256"], self.flow._run_code.digest("row"))
        self.assertEqual(record["code_commit"], COMMIT)
        self.assertEqual(record["run_id"], self.rules.configured_run_id(record["code_sha256"], catalog_sha256, digest))
        self.assertEqual(self.rules.RunRecord.model_validate(record).run_id, record["run_id"])
        train_args = dict(self.calls())["train"]
        self.assertEqual(train_args[train_args.index("--out") + 1], str(run_dir))
        self.assertIn("optimiser=adamw", train_args)
        self.assertNotIn("--resume", train_args)

    def test_a_changed_block_names_another_run_and_only_what_is_computed_names_one(self):
        def named(*extra):
            args = self.flow.parse(["run", "--catalog", str(self.catalog), "--out", str(self.out), "--epochs", "2", *extra])
            with mock.patch.object(self.flow, "tree_state", lambda: (COMMIT, True)):
                return self.flow.start_record(args)[0].run_id

        plain = named()
        self.assertNotEqual(named("--block", "schedule=cosine"), plain)
        self.assertNotEqual(named("--seed", "2"), plain)
        self.assertNotEqual(named("--size", "96"), plain)
        self.assertNotEqual(named("--environment", "train-gpu"), plain)
        self.assertEqual(named("--block", "schedule=cosine", "--block", "warmup_epochs=1"),
                         named("--block", "warmup_epochs=1", "--block", "schedule=cosine"), "the blocks are keyed, not ordered")
        # Where and how long a run runs is no part of what it computes.
        self.assertEqual(named("--hours", "9", "--cpus", "16", "--memory-gb", "64"), plain)
        self.assertEqual(named("--mode", "slurm", "--environment", "train-cpu", "--partition", "gmsap"), plain)
        # A file it starts from is named by its bytes, not by where it lies.
        weights = self.work / "a" / "weights.pt"
        weights.parent.mkdir()
        weights.write_bytes(b"imagenet")
        moved = self.work / "b.pt"
        moved.write_bytes(b"imagenet")
        self.assertEqual(named("--weights", str(weights)), named("--weights", str(moved)))
        self.assertNotEqual(named("--weights", str(weights)), plain)
        self.assertNotEqual(named("--init", str(weights)), named("--weights", str(weights)))
        moved.write_bytes(b"other weights")
        self.assertNotEqual(named("--weights", str(weights)), named("--weights", str(moved)))
        rc, _, err = self.run_flow("--weights", str(self.work / "none.pt"))
        self.assertEqual(rc, 1)
        self.assertIn("flow: --weights", err)
        self.assertIn("no file there", err)
        rc, _, err = self.run_flow("--init", str(self.work / "parent" / "train" / "best.pt"))
        self.assertEqual(rc, 1)
        self.assertIn("flow: --init", err)
        self.assertIn("no parent checkpoint there", err)
        self.assertFalse(self.out.exists())

    def test_the_order_the_changes_or_sources_are_named_in_names_no_other_run(self):
        # The trainer applies augment in its own fixed order and keeps a crop by whether its source
        # is named, so the two orders train alike and must name one run.
        def named(*blocks):
            words = [w for block in blocks for w in ("--block", block)]
            args = self.flow.parse(["run", "--catalog", str(self.catalog), "--out", str(self.out), "--epochs", "2", *words])
            with mock.patch.object(self.flow, "tree_state", lambda: (COMMIT, True)):
                return self.flow.start_record(args)[0].run_id

        self.assertEqual(named("augment=noise,blur"), named("augment=blur,noise"))
        self.assertEqual(named("samples=drop-sources", "sources=b,a"), named("sources=a,b", "samples=drop-sources"))
        self.assertNotEqual(named("augment=blur"), named("augment=blur,noise"))
        self.assertNotEqual(named("samples=drop-sources", "sources=a"), named("samples=drop-sources", "sources=a,b"))
        rc, lines, _ = self.run_flow("--block", "augment=noise,blur", fake={"FAKE_TRAIN": "cut"})
        run_dir = Path(self.said(lines)["run_dir"])
        first = dict(self.calls())["train"]
        self.log.unlink()
        rc, lines, err = self.run_flow("--block", "augment=blur,noise")
        self.assertEqual((rc, self.said(lines)["run_dir"], self.said(lines)["reused"]), (0, str(run_dir), "resumed"), err)
        again = dict(self.calls())["train"]
        self.assertEqual(again, [*first, "--resume"], "the trainer is handed the same blocks whichever order was typed")
        self.assertIn("augment=blur,noise", first)
        configuration = json.loads((run_dir / "CONFIGURATION.json").read_text(encoding="utf-8"))
        self.assertEqual(configuration["blocks"]["augment"], ["blur", "noise"])

    def test_a_folder_that_finished_training_runs_the_evaluation_only(self):
        rc, lines, err = self.run_flow(fake={"FAKE_EVALUATE": "fail"})
        self.assertEqual(rc, 1)
        self.assertIn("flow: evaluate exited 1", err)
        run_dir = Path(self.said(lines)["run_dir"])
        first = self.record(run_dir)
        witness = (run_dir / "witness.json").read_bytes()
        self.assertEqual(self.ledger_rows(), [])
        self.log.unlink()
        rc, lines, err = self.run_flow()
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.said(lines)["reused"], "trained")
        self.assertEqual(self.tools_called(), ["evaluate", "wandb_log", "wandb_log"], "training is not run again")
        record = self.record(run_dir)
        self.assertEqual(record["started_at"], first["started_at"])
        self.assertEqual(record["jobs"][:len(first["jobs"])], first["jobs"], "the earlier jobs are kept")
        self.assertEqual([job["step"] for job in record["jobs"]], ["split-check", "train", "evaluate", "split-check", "evaluate"])
        self.assertEqual(record["jobs"][-1]["exit_code"], 0)
        self.assertEqual((run_dir / "witness.json").read_bytes(), witness, "both steps draw the same frames")
        self.assertIn('"witness": "kept"', "\n".join(lines))
        self.assertEqual(len(self.ledger_rows()), 1, "one ledger row for the run, once it finished")
        self.assertTrue((run_dir / "PROVENANCE.json").is_file() and (run_dir / "split-check.json").is_file())

    def test_a_checkpoint_json_that_is_no_record_of_its_best_pt_trains_again(self):
        # A node that died, or a disk that spoiled a file, can leave checkpoint.json short, or
        # beside other weights than the ones it names; taken for the end of training, it sent
        # every start to an evaluation that refuses it. Training runs again, on from last.pt
        # where the trainer left one.
        def emptied(train):
            (train / "checkpoint.json").write_bytes(b"")

        def unnamed(train):
            (train / "checkpoint.json").write_text('{"best": {"epoch": 2}}', encoding="utf-8")

        def replaced(train):
            (train / "best.pt").write_bytes(b"other weights")

        def gone(train):
            (train / "best.pt").unlink()

        def replaced_beside_last(train):
            replaced(train)
            (train / "last.pt").write_bytes(b"epoch 2")

        spoils = ((emptied, "restarted"), (unnamed, "restarted"), (replaced, "restarted"), (gone, "restarted"), (replaced_beside_last, "resumed"))
        for seed, (spoil, reused) in enumerate(spoils, start=11):
            with self.subTest(spoil.__name__):
                rc, lines, _ = self.run_flow("--seed", str(seed), fake={"FAKE_EVALUATE": "fail"})
                self.assertEqual(rc, 1)
                run_dir = Path(self.said(lines)["run_dir"])
                spoil(run_dir / "train")
                self.log.unlink()
                rc, lines, err = self.run_flow("--seed", str(seed))
                self.assertEqual(rc, 0, err)
                self.assertEqual(self.said(lines)["reused"], reused)
                self.assertEqual(self.tools_called(), ["train", "wandb_log", "evaluate", "wandb_log", "wandb_log"])
                self.assertEqual("--resume" in dict(self.calls())["train"], reused == "resumed")

    def slurm(self):
        """What a start in slurm mode runs with: tests/fakes/hpcworker, which queues nothing and
        logs each job it is asked to queue, numbered from 101, and the fake sacct, which answers
        for each job what the test wrote for it, both first on the path."""
        states, tools = self.work / "sacct", self.work / "slurm-bin"
        states.mkdir()
        tools.mkdir()
        (tools / "sacct").write_text(FAKE_SACCT, encoding="utf-8")
        (tools / "sacct").chmod(0o755)
        queued = self.work / "hpcw.log"
        environment = {"HPCWORKER": str(ROOT / "tests" / "fakes" / "hpcworker"), "HPCW_LOG": str(queued), "FAKE_SACCT": str(states),
                       "PATH": f"{tools}{os.pathsep}{self.bin}{os.pathsep}{os.environ.get('PATH', '')}"}
        return environment, states, queued

    def test_a_slurm_start_cut_while_its_job_waits_leaves_the_job_for_the_next_start_to_wait_on(self):
        # A person's login shell that dies while the train job waits in the queue: the job runs on,
        # and a start that knew nothing of it would submit a second, which trains over the first's
        # finished folder on another GPU allocation, the first one's cost counted nowhere.
        environment, states, queued = self.slurm()
        run_dir = self.out / "row-a"

        def shell_died(seconds):
            raise Killed("the login shell died while the job waited")

        def scheduler(seconds):
            # The flow's sleep before each sacct read, made to run each job queued and not yet run,
            # as the grid would while the flow waits: training leaves checkpoint.json and the
            # best.pt it names, an evaluation its results, and sacct then calls the job COMPLETED.
            for number, line in enumerate(queued.read_text(encoding="utf-8").splitlines(), start=101):
                if (states / str(number)).exists():
                    continue
                if "--name flow_train " in line:
                    (run_dir / "train").mkdir(exist_ok=True)
                    (run_dir / "train" / "best.pt").write_bytes(b"the weights of job 101")
                    named = hashlib.sha256(b"the weights of job 101").hexdigest()
                    (run_dir / "train" / "checkpoint.json").write_text(json.dumps({"checkpoint_sha256": named}), encoding="utf-8")
                else:
                    (run_dir / "evaluate").mkdir(exist_ok=True)
                    (run_dir / "evaluate" / "results.json").write_text(json.dumps({"headline": {"correct": 1, "total": 2}}), encoding="utf-8")
                    (run_dir / "evaluate" / "results.md").write_text("| accuracy | 1/2 |\n", encoding="utf-8")
                (states / str(number)).write_text("COMPLETED|00:10:00|0:0\n", encoding="utf-8")

        with mock.patch.object(self.flow.time, "sleep", shell_died), self.assertRaises(Killed):
            self.run_flow("--mode", "slurm", "--slug", "row-a", fake=environment)
        jobs = self.record(run_dir)["jobs"]
        self.assertEqual([(job["step"], job["job_id"], job["exit_code"]) for job in jobs[1:]], [("train", "101", None)],
                         "the job is in the record before the flow waits on it")
        with mock.patch.object(self.flow.time, "sleep", scheduler):
            rc, lines, err = self.run_flow("--mode", "slurm", "--slug", "row-a", fake=environment)
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.said(lines)["reused"], "trained", "the job it waited on finished training")
        names = [line.split()[3] for line in queued.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(names, ["flow_train", "flow_evaluate"], "one train job, waited on by the second start")
        jobs = self.record(run_dir)["jobs"]
        self.assertEqual([(job["step"], job["job_id"], job["exit_code"]) for job in jobs if job["step"] != "split-check"],
                         [("train", "101", 0), ("evaluate", "102", 0)])
        self.assertEqual(jobs[1]["seconds_used"], 600, "the first job's time is counted")
        self.assertTrue((run_dir / "FINISHED.json").is_file())

    def test_sacct_that_cannot_be_run_is_refused_in_words(self):
        # A start that finds a job it must wait on and no sacct to ask, as on a machine off the grid.
        def no_sacct(*args, **kwargs):
            raise FileNotFoundError(2, "No such file or directory", "sacct")

        with mock.patch.object(self.flow.subprocess, "run", no_sacct), self.assertRaisesRegex(self.flow.FlowError, r"sacct cannot be run here \(\[Errno 2\] No such file or directory: 'sacct'\), so whether job 101 has finished cannot be told"):
            self.flow.sacct("101")

    def test_a_folder_with_a_last_epoch_carries_training_on_with_resume(self):
        rc, lines, err = self.run_flow(fake={"FAKE_TRAIN": "cut"})
        self.assertEqual(rc, 1)
        self.assertIn("flow: train exited 137", err)
        run_dir = Path(self.said(lines)["run_dir"])
        self.assertTrue((run_dir / "train" / "last.pt").is_file())
        first = self.record(run_dir)
        self.log.unlink()
        rc, lines, err = self.run_flow()
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.said(lines)["reused"], "resumed")
        self.assertEqual(self.tools_called(), ["train", "wandb_log", "evaluate", "wandb_log", "wandb_log"])
        train_args = dict(self.calls())["train"]
        self.assertEqual(train_args[-1], "--resume")
        self.assertFalse((run_dir / "train" / "last.pt").exists())
        record = self.record(run_dir)
        self.assertEqual(record["started_at"], first["started_at"])
        self.assertEqual([job["step"] for job in record["jobs"]], ["split-check", "train", "split-check", "train", "evaluate"])
        self.assertEqual([job["exit_code"] for job in record["jobs"]], [0, 137, 0, 0, 0])
        log = (run_dir / "train.log").read_text(encoding="utf-8")
        self.assertLess(log.index("then the job was killed"), log.index("run again"))
        self.assertLess(log.index("run again"), log.index("trained on from train/last.pt"))
        self.assertEqual(len(self.ledger_rows()), 1)
        self.log.unlink()
        rc, lines, err = self.run_flow()
        self.assertEqual((rc, self.said(lines)["reused"], self.calls()), (0, "finished", []))

    def test_a_start_on_a_later_commit_of_the_same_code_carries_the_run_on_and_other_code_names_another(self):
        # The gate brings main in before every word, so a run cut short is started again on a later
        # commit; one that changed none of the code the run executes names the same run.
        rc, lines, err = self.run_flow(fake={"FAKE_TRAIN": "cut"})
        self.assertEqual(rc, 1)
        run_dir = Path(self.said(lines)["run_dir"])
        first = self.record(run_dir)
        self.log.unlink()
        rc, lines, err = self.run_flow(commit=LATER)
        self.assertEqual(rc, 0, err)
        self.assertEqual((self.said(lines)["run_dir"], self.said(lines)["reused"]), (str(run_dir), "resumed"))
        self.assertEqual(dict(self.calls())["train"][-1], "--resume")
        record = self.record(run_dir)
        self.assertEqual((record["code_commit"], record["code_sha256"]), (COMMIT, first["code_sha256"]),
                         "the record keeps the commit it started on, whose code is the code that ran")
        # Another code is another run, in a folder of its own, from the start.
        self.log.unlink()
        rc, lines, err = self.run_flow(commit=LATER, code="f" * 64)
        self.assertEqual(rc, 0, err)
        other = self.said(lines)
        self.assertNotEqual(other["run_id"], first["run_id"])
        self.assertNotIn("reused", other)
        self.assertNotIn("--resume", dict(self.calls())["train"])
        self.assertEqual(self.record(Path(other["run_dir"]))["code_commit"], LATER)

    def test_a_run_cut_after_its_evaluation_is_finished_by_the_next_start_once(self):
        # Cut at the push right after the evaluation, as a Slurm limit or SIGTERM cuts the driver:
        # the record says the evaluation ended, and nothing after it was done.
        real, pushes = self.flow.push_wandb, []

        def push_then_cut(*args):
            pushes.append(args)
            if len(pushes) == 2:
                raise Killed("cut during the push after the evaluation")
            return real(*args)

        with mock.patch.object(self.flow, "push_wandb", push_then_cut), self.assertRaises(Killed):
            self.run_flow("--slug", "row-a")
        run_dir = self.out / "row-a"
        self.assertEqual([job["step"] for job in self.record(run_dir)["jobs"]], ["split-check", "train", "evaluate"])
        self.assertEqual((self.ledger_rows(), (run_dir / "REPORT.md").exists()), ([], False))
        self.log.unlink()
        rc, lines, err = self.run_flow("--slug", "row-a")
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.said(lines)["reused"], "evaluated")
        self.assertEqual(self.tools_called(), ["wandb_log"], "only the last push: nothing is trained or evaluated again")
        self.assertEqual([job["step"] for job in self.record(run_dir)["jobs"]], ["split-check", "train", "evaluate"])
        self.assertEqual(len(self.ledger_rows()), 1)
        self.assertTrue((run_dir / "REPORT.md").is_file())
        self.assertEqual(json.loads((run_dir / "FINISHED.json").read_text(encoding="utf-8"))["run_id"], self.said(lines)["run_id"])
        self.log.unlink()
        rc, lines, _ = self.run_flow("--slug", "row-a")
        self.assertEqual((rc, self.said(lines)["reused"], self.calls()), (0, "finished", []))
        # Cut after its ledger row and before its report: the row is not written twice.
        with mock.patch.object(self.flow, "write_report", side_effect=Killed("cut before the report")), self.assertRaises(Killed):
            self.run_flow("--slug", "row-b", "--seed", "2")
        self.assertEqual(len(self.ledger_rows()), 2)
        rc, lines, err = self.run_flow("--slug", "row-b", "--seed", "2")
        self.assertEqual((rc, self.said(lines)["reused"]), (0, "evaluated"), err)
        self.assertEqual(len(self.ledger_rows()), 2, "one ledger row a run")
        self.assertTrue((self.out / "row-b" / "REPORT.md").is_file() and (self.out / "row-b" / "FINISHED.json").is_file())

    def test_a_ledger_write_cut_by_a_full_volume_keeps_the_rows_before_it_and_the_next_start_writes_its_row(self):
        rc, lines, err = self.run_flow("--slug", "row-a")
        self.assertEqual(rc, 0, err)
        first = self.said(lines)["run_id"]
        ledger = self.out / "LEDGER.md"
        before = ledger.read_text(encoding="utf-8")
        full = OSError(errno.EDQUOT, "Disk quota exceeded")
        with write_cut_short(("LEDGER.md", "LEDGER.md.tmp"), 1, full):
            rc, lines, err = self.run_flow("--slug", "row-b", "--seed", "2")
        self.assertEqual(rc, 1)
        self.assertIn(f"flow: {ledger}: the run's row could not be written ([Errno {errno.EDQUOT}] Disk quota exceeded)", err)
        self.assertEqual(ledger.read_text(encoding="utf-8"), before, "the header and the rows before it are kept")
        self.assertFalse((self.out / "row-b" / "FINISHED.json").exists())
        rc, lines, err = self.run_flow("--slug", "row-b", "--seed", "2")
        self.assertEqual((rc, self.said(lines)["reused"]), (0, "evaluated"), err)
        text = ledger.read_text(encoding="utf-8")
        self.assertTrue(text.startswith(self.flow.LEDGER_HEADER + "\n"))
        self.assertEqual([row.split(" | ")[1] for row in self.ledger_rows()], [first, self.said(lines)["run_id"]])

    def test_two_runs_that_finish_together_keep_every_row_and_the_header(self):
        # The rows of a sweep's state share <state>/LEDGER.md, and flows/launch.py sweep runs rows
        # side by side under --max-workers; each writer reads the ledger and writes it again.
        context = multiprocessing.get_context("fork")
        barrier, ledger, each = context.Barrier(2), self.work / "LEDGER.md", 150
        rows = [[legacy_record(self.rules, f"2026-10-25T{hour:02d}:{n // 60:02d}:{n % 60:02d}Z") for n in range(each)] for hour in (1, 2)]
        writers = [context.Process(target=write_rows, args=(self.flow, ledger, records, barrier)) for records in rows]
        for writer in writers:
            writer.start()
        for writer in writers:
            writer.join(timeout=300)
        self.assertEqual([writer.exitcode for writer in writers], [0, 0])
        lines = ledger.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[:2], self.flow.LEDGER_HEADER.splitlines())
        self.assertEqual(sorted(line.split(" | ")[1] for line in lines[2:]), sorted(r.run_id for records in rows for r in records))

    def test_a_start_while_another_start_holds_the_folder_is_refused_and_runs_nothing(self):
        # The v1 driver's start and an experiment asking for version 1's training, whose --hours
        # names no other run, meet in one folder; the second must not train beside the first.
        import fcntl

        rc, lines, _ = self.run_flow(fake={"FAKE_TRAIN": "cut"})
        run_dir = Path(self.said(lines)["run_dir"])
        self.log.unlink()

        def refused_while_held(folder, *extra):
            with (folder / ".lock").open("a+", encoding="utf-8") as live:
                fcntl.flock(live, fcntl.LOCK_EX | fcntl.LOCK_NB)
                live.truncate(0)
                live.write("pid 4242 on login-1, since 2026-10-25T03:00:00Z\n")
                live.flush()
                before = snapshot(self.out)
                rc, lines, err = self.run_flow(*extra)
                self.assertEqual(snapshot(self.out), before, "nothing is written while another start holds the folder")
            self.assertEqual((rc, lines), (1, []))
            self.assertIn(f"flow: {folder} is in progress: another start of this run holds {folder / '.lock'}"
                          " (pid 4242 on login-1, since 2026-10-25T03:00:00Z)", err)
            self.assertEqual(self.calls(), [])

        refused_while_held(run_dir, "--hours", "6")
        rc, lines, err = self.run_flow("--hours", "6")
        self.assertEqual((rc, self.said(lines)["reused"]), (0, "resumed"), err)
        # A new run's folder, held by a start that has not yet written its record.
        args = self.flow.parse(["run", "--catalog", str(self.catalog), "--out", str(self.out), "--epochs", "2", "--size", "32", "--seed", "3"])
        with mock.patch.object(self.flow, "tree_state", lambda: (COMMIT, True)):
            fresh = self.out / self.flow.start_record(args)[0].run_id
        fresh.mkdir()
        self.log.unlink()
        refused_while_held(fresh, "--seed", "3")
        self.assertEqual(sorted(p.name for p in fresh.iterdir()), [".lock"])

    def test_a_folder_holding_another_run_is_refused_and_left_as_it_was(self):
        rc, lines, err = self.run_flow("--slug", "row-a")
        self.assertEqual(rc, 0, err)
        held = self.said(lines)["run_id"]
        before = snapshot(self.out)
        self.log.unlink()
        rc, lines, err = self.run_flow("--slug", "row-a", "--block", "sampler=balanced")
        self.assertEqual(rc, 1)
        self.assertRegex(err, rf"^flow: {re.escape(str(self.out / 'row-a'))} holds run {held}, and this configuration of this code on this catalog names run [0-9a-f]{{12}}; nothing is touched")
        self.assertNotIn(f"names run {held}", err)
        self.assertEqual(snapshot(self.out), before)
        self.assertEqual(self.calls(), [])
        # A run recorded before configurations were named is another run as well.
        legacy = self.out / "row-b"
        legacy.mkdir()
        shutil.copyfile(LEGACY_RUN / "RUN.json", legacy / "RUN.json")
        rc, _, err = self.run_flow("--slug", "row-b")
        self.assertEqual(rc, 1)
        self.assertIn(f"holds run {LEGACY_RUN.name}", err)
        self.assertEqual(sorted(p.name for p in legacy.iterdir()), ["RUN.json"])
        # A folder with files and no record is no run of the flow's.
        stray = self.out / "row-c"
        stray.mkdir()
        (stray / "notes.txt").write_text("mine\n", encoding="utf-8")
        rc, _, err = self.run_flow("--slug", "row-c")
        self.assertEqual(rc, 1)
        self.assertIn("holds notes.txt and no RUN.json", err)
        self.assertEqual(sorted(p.name for p in stray.iterdir()), ["notes.txt"])
        self.assertEqual(self.calls(), [])

    def test_a_start_cut_between_its_configuration_and_its_record_starts_again(self):
        with mock.patch.object(self.flow, "write_record", side_effect=Killed("cut before RUN.json")), self.assertRaises(Killed):
            self.run_flow("--slug", "row-a")
        self.assertEqual(sorted(p.name for p in (self.out / "row-a").iterdir() if p.name != ".lock"), ["CONFIGURATION.json", "split-check.json"])
        rc, lines, err = self.run_flow("--slug", "row-a")
        self.assertEqual(rc, 0, err)
        self.assertNotIn("reused", self.said(lines))
        self.assertEqual(self.tools_called(), ["train", "wandb_log", "evaluate", "wandb_log", "wandb_log"])
        # One the start of another configuration left is not this run's and is refused.
        (self.out / "row-b").mkdir()
        shutil.copyfile(self.out / "row-a" / "CONFIGURATION.json", self.out / "row-b" / "CONFIGURATION.json")
        self.log.unlink()
        rc, _, err = self.run_flow("--slug", "row-b", "--seed", "2")
        self.assertEqual(rc, 1)
        self.assertIn("holds CONFIGURATION.json of another configuration and no RUN.json", err)
        self.assertEqual(self.calls(), [])

    def test_a_record_or_witness_list_cut_while_written_leaves_the_one_before(self):
        # RUN.json is rewritten after the training step; a cut there must leave the first one.
        with write_cut_short(("RUN.json", "RUN.json.tmp"), 2), self.assertRaises(Killed):
            self.run_flow("--slug", "row-a")
        json.loads((self.out / "row-a" / "RUN.json").read_text(encoding="utf-8"))
        self.log.unlink()
        rc, lines, err = self.run_flow("--slug", "row-a")
        self.assertEqual(rc, 0, err)
        self.assertEqual((self.said(lines)["reused"], self.tools_called()), ("trained", ["evaluate", "wandb_log", "wandb_log"]))
        with write_cut_short(("witness.json", "witness.json.tmp"), 1), self.assertRaises(Killed):
            self.run_flow("--slug", "row-b")
        rc, lines, err = self.run_flow("--slug", "row-b")
        self.assertEqual(rc, 0, err)
        json.loads((self.out / "row-b" / "witness.json").read_text(encoding="utf-8"))

    def test_the_slug_places_the_folder_and_a_bad_slug_is_refused(self):
        rc, lines, err = self.run_flow("--slug", "resnet18-64px-0123abcd")
        self.assertEqual(rc, 0, err)
        said = self.said(lines)
        self.assertEqual(said["run_dir"], str(self.out / "resnet18-64px-0123abcd"))
        self.assertEqual(self.record(self.out / "resnet18-64px-0123abcd")["run_id"], said["run_id"])
        self.assertTrue((self.out / "resnet18-64px-0123abcd" / "evaluate" / "results.json").is_file())
        rc, lines, _ = self.run_flow("--slug", "resnet18-64px-0123abcd")
        self.assertEqual((rc, self.said(lines)["reused"]), (0, "finished"))
        shutil.rmtree(self.out)
        self.log.unlink()
        for bad in ("", "Resnet", "-row", ".row", "row/a", "../row", "row_a", "row a", "r" * 81):
            rc, _, err = self.run_flow(f"--slug={bad}")
            self.assertEqual(rc, 1, bad)
            self.assertIn("flow: --slug", err)
        self.assertEqual(self.run_flow("--slug", "r" * 80)[0], 0)
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), ["LEDGER.md", "LEDGER.md.lock", "r" * 80])

    def test_a_record_written_before_configurations_were_named_still_validates_in_record(self):
        run = self.work / "old"
        (run / "train").mkdir(parents=True)
        for name in ("RUN.json", "split-check.json", "train/checkpoint.json"):
            shutil.copyfile(LEGACY_RUN / name, run / name)
        self.assertNotIn("configuration_sha256", self.record(run))
        into = self.work / "docs" / "runs"
        with contextlib.redirect_stdout(io.StringIO()):
            rc = self.flow.main(["record", "--run", str(run), "--into", str(into), "--activity", "the dry run", "--verified", "by hand"])
        self.assertEqual(rc, 0)
        self.assertEqual(sorted(str(p.relative_to(into)) for p in into.rglob("*") if p.is_file()),
                         [f"{LEGACY_RUN.name}/RUN.json", f"{LEGACY_RUN.name}/split-check.json", f"{LEGACY_RUN.name}/train/checkpoint.json"])
        self.assertIn(LEGACY_RUN.name, (self.work / "docs" / "LEDGER.md").read_text(encoding="utf-8"))
        self.assertIn("CONFIGURATION.json", self.flow.KEPT)


if __name__ == "__main__":
    unittest.main()
