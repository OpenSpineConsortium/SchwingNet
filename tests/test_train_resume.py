"""tools/train.py's --resume and its last batch of one crop (#252).

A run cut mid-way, as a Slurm timeout or a preemption cuts it, goes on from train/last.pt and
ends, on the CPU, on the same lines, best.pt, prior head and checkpoint.json as a run that went
through, the seconds apart; the cut is made here by the trainer's own save function raising
after its second write, patched in this process, so the trainer carries no hook for tests. A
--resume with nothing to resume, or with other arguments than the run was started with, is
refused in words, and last.pt is gone once a run has finished. W&B's run goes on under the same
id. And at 32 pixels, where batch norm cannot train on one crop, a training part of 65 crops,
whose last batch of 64 would hold one, still trains, while at 64 pixels the batches are as they
always were.

The trainer's tests need the train environment, as tests/test_train_blocks.py does, and skip
under the required check's plain python3; the W&B test needs nothing but the standard library."""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

# By the module, not its classes, so this file runs none of that file's tests; imported now, since
# loading tools/train.py takes this folder's parent off the path.
import tests.test_train_blocks as blocks_tests

ROOT = Path(__file__).resolve().parent.parent
NEEDED = ("torch", "PIL", "numpy", "beartype", "icontract", "pydantic")
MISSING = [name for name in NEEDED if importlib.util.find_spec(name) is None]
# The blocks that draw from the run's generator and hold state of their own, the prior head's
# among them, so the resumed run has every state to take back.
EVERY_BLOCK = ["normalise=imagenet", "augment=box-jitter,intensity,blur,noise", "optimiser=adamw", "weight_decay=0.01",
               "schedule=cosine", "warmup_epochs=1", "backbone_lr_scale=0.5", "sampler=balanced",
               "loss_weights=inverse-frequency", "select=balanced-accuracy", "prior=level-map", "prior_weight=0.5"]


def load(name):
    spec = importlib.util.spec_from_file_location(f"{name}_resume_under_test", ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def new_run(folder, run_id, witness=None):
    folder.mkdir(parents=True)
    record = {"run_id": run_id, "code_commit": "0" * 40, "catalog_sha256": "0" * 64, "catalog_version": 1, "clean_tree": True}
    (folder / "RUN.json").write_text(json.dumps(record), encoding="utf-8")
    if witness is not None:
        (folder / "witness.json").write_text(json.dumps(witness), encoding="utf-8")
    return folder


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def untimed(line):
    """An epoch's line or the checkpoint's facts without the wall time, the one field a cut moves."""
    return {k: v for k, v in line.items() if k != "seconds"}


def lines_of(folder):
    return [json.loads(line) for line in (folder / "train" / "metrics.jsonl").read_text(encoding="utf-8").splitlines()]


def facts_of(folder):
    return json.loads((folder / "train" / "checkpoint.json").read_text(encoding="utf-8"))


class Killed(Exception):
    """What the patched save raises, as a job cut after its write would stop."""


def cut_after(module, writes):
    """The trainer's save of last.pt, made to stop the run once it has written writes of them."""
    real, done = module.save_last, []

    def save_then_stop(folder, state):
        real(folder, state)
        done.append(state["epoch"])
        if len(done) == writes:
            raise Killed(f"cut after write {writes} of last.pt (epoch {state['epoch']})")

    return mock.patch.object(module, "save_last", save_then_stop)


def train(catalog, folder, *extra, module=None):
    """The trainer's main on a short CPU run, its output kept; returns the exit code, stdout and stderr."""
    args = ["--catalog", str(catalog), "--out", str(folder), "--seed", "1", "--device", "cpu", "--witness", "2",
            "--keep-epochs", "0", *extra]
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.dict(os.environ, {"SCHWINGNET_WANDB": "off"}), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = (module or load("train")).main(args)
    return rc, out.getvalue(), err.getvalue()


class ResumeCase:
    """Three runs of one configuration: through, cut after the second last.pt (epoch 1), and the
    cut one resumed; each subclass names the architecture and the blocks."""

    words = ()
    tmp = catalog = None

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.catalog = blocks_tests.RunWithEveryBlockTest.make_catalog(cls.tmp)
        witness = load("witness").freeze(cls.catalog, "0" * 64)
        cls.config = ["--epochs", "3", "--size", "32", *(w for word in cls.words for w in ("--block", word))]
        cls.through = new_run(cls.tmp / "through", "throughrun00", witness)
        cls.through_rc = train(cls.catalog, cls.through, *cls.config)[0]
        cls.cut = new_run(cls.tmp / "cut", "cutrun000000", witness)
        module = load("train")
        with cut_after(module, 2):
            try:
                train(cls.catalog, cls.cut, *cls.config, module=module)
                cls.cut_stopped = False
            except Killed:
                cls.cut_stopped = True
        cls.after_cut = {name: (cls.cut / "train" / name).exists() for name in ("last.pt", "checkpoint.json", "best.pt")}
        cls.last_digest = digest(cls.cut / "train" / "last.pt")
        cls.mismatch = train(cls.catalog, cls.cut, *[w if w != "3" else "4" for w in cls.config], "--resume")
        cls.mismatch_left = digest(cls.cut / "train" / "last.pt")
        cls.resumed_rc, cls.resumed_out, _ = train(cls.catalog, cls.cut, *cls.config, "--resume")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_the_cut_stopped_after_epoch_1_with_last_pt_and_no_checkpoint(self):
        self.assertEqual(self.through_rc, 0)
        self.assertTrue(self.cut_stopped)
        self.assertEqual(self.after_cut, {"last.pt": True, "checkpoint.json": False, "best.pt": False}, "epoch 1's best waits under pending/ until last.pt records it")
        self.assertIn('"resumed_after_epoch": 1', self.resumed_out)

    def test_a_resumed_run_ends_as_one_that_went_through(self):
        self.assertEqual(self.resumed_rc, 0)
        self.assertEqual([untimed(line) for line in lines_of(self.cut)], [untimed(line) for line in lines_of(self.through)])
        self.assertEqual(len(lines_of(self.cut)), 4)
        self.assertEqual(digest(self.cut / "train" / "best.pt"), digest(self.through / "train" / "best.pt"))
        self.assertEqual(untimed(facts_of(self.cut)), untimed(facts_of(self.through)))
        self.assertEqual(facts_of(self.cut)["checkpoint_sha256"], digest(self.cut / "train" / "best.pt"))

    def test_every_picture_of_the_resumed_run_is_the_uncut_runs(self):
        def pictures(folder):
            root = folder / "train"
            return {str(p.relative_to(root)): digest(p) for p in sorted(root.rglob("*")) if p.is_file() and p.suffix in (".png", ".jpg", ".gif")}

        mine, theirs = pictures(self.cut), pictures(self.through)
        self.assertEqual(mine, theirs)
        sheets = sorted(name for name in mine if "sheet-epoch-" in name)
        self.assertEqual(sheets, ["witness/frames/sheet-epoch-00.jpg", "witness/frames/sheet-epoch-03.jpg"], "the witness epochs before the cut are taken back")

    def test_last_pt_is_gone_after_a_finished_run(self):
        for folder in (self.through, self.cut):
            self.assertFalse((folder / "train" / "last.pt").exists())
            self.assertFalse((folder / "train" / "last.pt.tmp").exists())
            self.assertFalse((folder / "train" / "pending").exists())

    def test_a_resume_with_other_arguments_is_refused_in_words_and_touches_nothing(self):
        rc, _, err = self.mismatch
        self.assertEqual(rc, 1)
        self.assertIn("train: --resume:", err)
        self.assertIn("epochs was 3, now 4", err)
        self.assertEqual(self.mismatch_left, self.last_digest)

    def test_the_card_says_where_the_run_was_resumed(self):
        card = (self.cut / "train" / "MODEL.md").read_text(encoding="utf-8")
        self.assertIn("- Resumed after epoch 1: continued from train/last.pt", card)
        self.assertNotIn("- Resumed", (self.through / "train" / "MODEL.md").read_text(encoding="utf-8"))


@unittest.skipIf(MISSING, f"needs the train environment ({', '.join(MISSING)} missing)")
class ResumeWithEveryBlockTest(ResumeCase, unittest.TestCase):
    """resnet18 with every block on: the run's generator, the optimiser's moments and schedule
    and the prior head are what the resumed run must take back."""

    words = tuple(EVERY_BLOCK)

    def test_the_prior_head_of_the_resumed_run_is_the_uncut_runs(self):
        self.assertEqual(digest(self.cut / "train" / "prior_head.pt"), digest(self.through / "train" / "prior_head.pt"))
        self.assertEqual(facts_of(self.cut)["prior_head_sha256"], digest(self.cut / "train" / "prior_head.pt"))


@unittest.skipIf(MISSING, f"needs the train environment ({', '.join(MISSING)} missing)")
class ResumeWithDropoutTest(ResumeCase, unittest.TestCase):
    """mobilenet-v3-small, whose dropout draws from torch's global generator, which the resumed run
    must take back too (tools/train_blocks.py's module docstring)."""

    words = ("architecture=mobilenet-v3-small",)


@unittest.skipIf(MISSING, f"needs the train environment ({', '.join(MISSING)} missing)")
class ResumeRefusalsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.train = load("train")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_a_resume_with_no_last_pt_is_refused_in_words(self):
        folder = new_run(self.tmp / "nothing", "nothingrun00")
        rc, _, err = train(self.tmp / "no-catalog.sqlite", folder, "--epochs", "1", "--resume", module=self.train)
        self.assertEqual(rc, 1)
        self.assertIn("nothing to resume", err)
        self.assertFalse((folder / "train" / "metrics.jsonl").exists())

    def test_a_staged_best_moves_in_only_where_the_record_names_it(self):
        folder = self.tmp / "settle" / "train"
        (folder / "pending").mkdir(parents=True)
        (folder / "pending" / "best.pt").write_bytes(b"recorded")
        (folder / "pending" / "prior_head.pt").write_bytes(b"not recorded")
        self.train.settle(folder, {"checkpoint_sha256": hashlib.sha256(b"recorded").hexdigest(), "prior_head_sha256": "0" * 64})
        self.assertEqual((folder / "best.pt").read_bytes(), b"recorded")
        self.assertFalse((folder / "prior_head.pt").exists())
        self.assertEqual(list((folder / "pending").iterdir()), [])
        (folder / "pending" / "best.pt").write_bytes(b"an epoch the cut never recorded")
        self.train.settle(folder, None)
        self.assertEqual((folder / "best.pt").read_bytes(), b"recorded")
        self.assertFalse((folder / "pending" / "best.pt").exists())

    def test_a_best_pt_the_record_does_not_name_stops_the_resume_in_words(self):
        folder = self.tmp / "unnamed" / "train"
        folder.mkdir(parents=True)
        named = {"checkpoint_sha256": hashlib.sha256(b"the recorded weights").hexdigest()}
        with self.assertRaisesRegex(self.train.TrainError, "is not the checkpoint"):
            self.train.check_best(folder, named)
        (folder / "best.pt").write_bytes(b"other weights")
        with self.assertRaisesRegex(self.train.TrainError, "is not the checkpoint"):
            self.train.check_best(folder, named)
        (folder / "best.pt").write_bytes(b"the recorded weights")
        self.train.check_best(folder, named)
        self.train.check_best(self.tmp / "nowhere", None)


@unittest.skipIf(MISSING, f"needs the train environment ({', '.join(MISSING)} missing)")
class SingleCropBatchTest(unittest.TestCase):
    """65 training crops in batches of 64 end each epoch on a batch of one crop."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.catalog = blocks_tests.RunWithEveryBlockTest.make_catalog(cls.tmp)
        cls.train = load("train")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_65(self, name, architecture, size):
        folder = new_run(self.tmp / name, f"{name}run".ljust(12, "0")[:12])
        rc, _, err = train(self.catalog, folder, "--epochs", "1", "--size", str(size), "--max-frames", "65",
                           "--block", f"architecture={architecture}", module=self.train)
        self.assertEqual(rc, 0, err)
        facts = facts_of(folder)
        self.assertEqual(facts["counts"]["train"], 65)
        return facts, (folder / "train" / "MODEL.md").read_text(encoding="utf-8")

    def test_at_32_pixels_resnet18_and_densenet121_train_on_65_crops(self):
        for architecture in ("resnet18", "densenet121"):
            with self.subTest(architecture=architecture):
                facts, card = self.run_65(f"joined-{architecture}", architecture, 32)
                self.assertEqual(facts["single_crop_batch"], "joined")
                self.assertIn(f"- Batches: {architecture} cannot train on one 32-pixel crop", card)
                self.assertIn("which then held 65", card)

    def test_at_64_pixels_the_probe_says_it_can_and_nothing_joins(self):
        import torch

        for architecture in ("resnet18", "densenet121"):
            with self.subTest(architecture=architecture):
                model = self.train.build_model(None, "cpu", architecture=architecture)
                self.assertTrue(self.train.trains_on_one_crop(model, 64))
                before = torch.get_rng_state()
                self.assertFalse(self.train.trains_on_one_crop(model, 32))
                self.assertTrue(torch.equal(before, torch.get_rng_state()), "the probe moves no random state")
                self.assertTrue(model.training, "the probe asks a copy and leaves the model as it was")
        facts, card = self.run_65("whole-resnet18", "resnet18", 64)
        self.assertNotIn("single_crop_batch", facts)
        self.assertNotIn("- Batches:", card)

    def test_the_batches_are_version_1s_unless_one_crop_is_left_over(self):
        def legacy(count, batch):
            return [(start, min(count, start + batch)) for start in range(0, count, batch)]

        for count in (0, 1, 2, 63, 64, 65, 66, 128, 129, 176):
            with self.subTest(count=count):
                self.assertEqual(self.train.batch_bounds(count, 64), legacy(count, 64))
                joined = self.train.batch_bounds(count, 64, join_single=True)
                if count in (65, 129):
                    self.assertEqual(joined, [*legacy(count, 64)[:-2], (legacy(count, 64)[-2][0], count)])
                else:
                    self.assertEqual(joined, legacy(count, 64))

    def test_a_join_that_finds_no_crop_left_over_trains_to_the_same_weights(self):
        import torch

        inputs = torch.rand(24, 1, 32, 32, generator=torch.Generator().manual_seed(2)).repeat(1, 3, 1, 1)
        targets = torch.arange(24) % 27
        states = []
        for join in (False, True):
            torch.manual_seed(9)
            model = self.train.build_model(None, "cpu")
            optimiser = torch.optim.Adam(model.parameters(), lr=1e-3)
            self.train.train_epoch(model, optimiser, inputs, targets, "cpu", 8, torch.Generator().manual_seed(5), join_single=join)
            states.append(model.state_dict())
        self.assertTrue(all(torch.equal(states[0][k], states[1][k]) for k in states[0]))

    def test_one_training_crop_that_cannot_train_on_one_is_refused_in_words(self):
        folder = new_run(self.tmp / "one", "onecroprun00")
        rc, _, err = train(self.catalog, folder, "--epochs", "1", "--size", "32", "--max-frames", "1", module=self.train)
        self.assertEqual(rc, 1)
        self.assertIn("train: one training crop: resnet18 cannot take a training step", err)
        self.assertFalse((folder / "train" / "metrics.jsonl").exists())


class FakeWandb(types.ModuleType):
    """wandb as Telemetry calls it, keeping each init's keywords; online starts fail where asked."""

    def __init__(self, fail_online):
        super().__init__("wandb")
        self.starts, self.fail_online = [], fail_online

    def Settings(self, **settings):  # noqa: N802 - wandb's own name
        return settings

    def init(self, **options):
        self.starts.append(options)
        if options["mode"] == "online" and self.fail_online:
            raise RuntimeError("no route to W&B")
        return types.SimpleNamespace(url="https://wandb.ai/example/run", log=lambda *a, **k: None, finish=lambda: None)

    def teardown(self):
        pass


class TelemetryResumeTest(unittest.TestCase):
    """A resumed step's W&B run goes on under its id: resume="allow" on whichever start it makes."""

    record = {"run_id": "telemetry000", "code_commit": "0" * 40, "catalog_sha256": "0" * 64, "catalog_version": 1, "clean_tree": True}

    def starts(self, key, fail_online, resume):
        tool = load("wandb_log")
        fake = FakeWandb(fail_online)
        with tempfile.TemporaryDirectory() as run_dir, mock.patch.dict(sys.modules, {"wandb": fake}), \
                mock.patch.dict(os.environ, {"SCHWINGNET_WANDB": "on", "SCHWINGNET_WANDB_MODE": "online"}), \
                mock.patch.object(tool, "key_source", return_value=key):
            telemetry = tool.Telemetry(run_dir, self.record, "train", {}, resume=resume) if resume else tool.Telemetry(run_dir, self.record, "train", {})
            self.assertIsNotNone(telemetry.run)
        return fake.starts

    def test_a_resumed_step_starts_online_and_offline_with_resume_allow(self):
        online = self.starts("env", fail_online=False, resume=True)
        self.assertEqual([(s["mode"], s["id"], s["resume"]) for s in online], [("online", "telemetry000-train", "allow")])
        fallen = self.starts("env", fail_online=True, resume=True)
        self.assertEqual([(s["mode"], s.get("resume")) for s in fallen], [("online", "allow"), ("offline", "allow")])
        offline = self.starts("none", fail_online=False, resume=True)
        self.assertEqual([(s["mode"], s["id"], s["resume"]) for s in offline], [("offline", "telemetry000-train", "allow")])

    def test_a_fresh_step_passes_no_resume(self):
        for key, fail in (("env", False), ("env", True), ("none", False)):
            with self.subTest(key=key, fail=fail):
                self.assertTrue(all("resume" not in s for s in self.starts(key, fail, resume=False)))


if __name__ == "__main__":
    unittest.main()
