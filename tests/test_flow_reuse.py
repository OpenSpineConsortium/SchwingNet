"""tools/flow.py names a run by what it computes and carries a cut-short run on in its own folder.

The run id is the hash of the commit, the catalog and the run's configuration (CONFIGURATION.json),
so the same configuration names the same folder, and started again the flow runs only what that
folder still needs: nothing once the evaluation finished, the evaluation where training wrote its
checkpoint.json, training with --resume where it left train/last.pt (issue #252). A sweep's row
names its folder with --slug, and a folder holding another run is refused and left as it was. A
start cut while it writes its record or witness list, or before its record, is started again.

The flow runs in-process against a real synthetic catalog built by the tools, with a fake `pixi`
on PATH standing in for the trainer, the evaluator and the W&B sync: it writes the files the flow
reads after each step and logs what it was asked, so the test sees which steps ran and with what.
The flow refuses a dirty tree, and the working copy under test may hold uncommitted changes, so
tree_state is replaced in-process by a clean tree at a fixed commit; that refusal itself is tested
in tests/schwingnet/test_flow.py. flow.py imports the package, so the test skips where pydantic,
beartype or icontract is missing, as under the required check's plain python3.
"""

import contextlib
import hashlib
import importlib.util
import io
import json
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
LEGACY_RUN = ROOT / "docs" / "research" / "v1-demo" / "runs" / "a767a466f5c1"
V1_DRIVER_SED = r's/.*"run_dir": "\([^"]*\)".*/\1/p'

# The fake pixi: `pixi run --locked -e ENV python tools/NAME.py ARGS` writes what the real step
# writes that the flow reads, and logs one JSON line per call. FAKE_TRAIN=cut leaves train/last.pt
# and exits as a killed job does; FAKE_EVALUATE=fail exits before writing results.
FAKE_PIXI = r'''#!{python}
import json, os, sys
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
    (train / "checkpoint.json").write_text(json.dumps({{"best": {{"epoch": 2, "validation_accuracy": 0.5}}}}), encoding="utf-8")
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


def write_cut_short(names, at):
    """Path.write_text made to write half its text to a file of these names and stop, at the
    at-th write to them, as a full volume or a kill mid-write leaves a file; every other write is
    the real one."""
    real, seen = Path.write_text, []

    def write_half(path, text, *args, **kwargs):
        if path.name in names:
            seen.append(path.name)
            if len(seen) == at:
                real(path, text[: len(text) // 2], *args, **kwargs)
                raise Killed(f"cut while writing {path.name}")
        return real(path, text, *args, **kwargs)

    return mock.patch.object(Path, "write_text", write_half)


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

    def run_flow(self, *extra, fake=None):
        """tools/flow.py run in local mode on the catalog; its exit code, stdout lines and stderr."""
        argv = ["run", "--catalog", str(self.catalog), "--out", str(self.out), "--mode", "local",
                "--epochs", "2", "--seed", "1", "--size", "32", *extra]
        environ = {"PATH": f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}", "FAKE_PIXI_LOG": str(self.log),
                   "SCHWINGNET_WANDB": "off", "FAKE_TRAIN": "", "FAKE_EVALUATE": "", **(fake or {})}
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, environ), mock.patch.object(self.flow, "tree_state", lambda: (COMMIT, True)), \
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
        self.assertEqual(record["run_id"], self.rules.configured_run_id(COMMIT, catalog_sha256, digest))
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

    def test_a_folder_holding_another_run_is_refused_and_left_as_it_was(self):
        rc, lines, err = self.run_flow("--slug", "row-a")
        self.assertEqual(rc, 0, err)
        held = self.said(lines)["run_id"]
        before = snapshot(self.out)
        self.log.unlink()
        rc, lines, err = self.run_flow("--slug", "row-a", "--block", "sampler=balanced")
        self.assertEqual(rc, 1)
        self.assertRegex(err, rf"^flow: {re.escape(str(self.out / 'row-a'))} holds run {held}, and this configuration on this commit and catalog names run [0-9a-f]{{12}}; nothing is touched")
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
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), ["LEDGER.md", "r" * 80])

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
