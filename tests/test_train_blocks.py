"""The torch side of the trainer's building blocks (tools/train_blocks.py) and their wiring in
tools/train.py: version 1's epoch is unchanged when no block is named, each block does what its
name says, a run with every block on writes its choices where the evaluator and the latency tool
read them, and the ImageNet scaling inside the model survives the ONNX export.

It needs torch, onnx, onnxruntime, Pillow and the package's checkers, so it runs in the train-cpu
environment (`pixi run -e train-cpu python -m unittest tests.test_train_blocks`) and skips under the
required check's plain python3."""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
NEEDED = ("torch", "onnx", "onnxruntime", "PIL", "beartype", "icontract", "pydantic")
MISSING = [name for name in NEEDED if importlib.util.find_spec(name) is None]


def load(name):
    spec = importlib.util.spec_from_file_location(f"{name}_blocks_under_test", ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def python(*args):
    done = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, timeout=600)
    if done.returncode != 0:
        raise AssertionError(f"{args}: {done.stdout}\n{done.stderr}")
    return done.stdout


@unittest.skipIf(MISSING, f"needs the train environment ({', '.join(MISSING)} missing)")
class BlocksTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.train = load("train")
        cls.blocks = cls.train.BLOCKS

    def batch(self, seed=0):
        import torch

        grey = torch.rand(6, 1, 32, 32, generator=torch.Generator().manual_seed(seed))
        return grey.repeat(1, 3, 1, 1)

    def test_every_name_has_its_function(self):
        from schwingnet import blocks

        self.assertEqual(set(self.blocks.NORMALISERS), set(blocks.NORMALISE))
        self.assertEqual(set(self.blocks.AUGMENTERS), set(blocks.AUGMENT))
        self.assertEqual(tuple(self.blocks.AUGMENT_ORDER), tuple(blocks.AUGMENT))
        self.assertEqual(set(self.blocks.OPTIMISERS), set(blocks.OPTIMISER))
        self.assertEqual(set(self.blocks.SAMPLERS), set(blocks.SAMPLER))

    def test_each_change_keeps_a_grey_crop_grey_in_range_and_seeded(self):
        import torch

        for name in self.blocks.AUGMENT_ORDER:
            with self.subTest(name=name):
                first = self.blocks.augment(self.batch(), (name,), torch.Generator().manual_seed(4))
                again = self.blocks.augment(self.batch(), (name,), torch.Generator().manual_seed(4))
                self.assertEqual(tuple(first.shape), (6, 3, 32, 32))
                self.assertTrue(torch.equal(first, again))
                self.assertTrue(torch.equal(first[:, 0], first[:, 1]) and torch.equal(first[:, 0], first[:, 2]))
                self.assertGreaterEqual(float(first.min()), -1e-6)
                self.assertLessEqual(float(first.max()), 1.0 + 1e-6)
        moved = self.blocks.augment(self.batch(), ("box-jitter",), torch.Generator().manual_seed(4))
        self.assertFalse(torch.equal(moved, self.batch()))

    def test_imagenet_scaling_keeps_the_weights_names(self):
        import torch

        plain = self.train.build_model(None, "cpu")
        scaled = self.train.build_model(None, "cpu", "imagenet")
        self.assertEqual(list(plain.state_dict()), list(scaled.state_dict()))
        scaled.load_state_dict(plain.state_dict())
        plain.eval(), scaled.eval()
        with torch.no_grad():
            self.assertFalse(torch.allclose(plain(self.batch()), scaled(self.batch())))
        facts = {"blocks": {"normalise": "imagenet"}}
        self.assertTrue(self.train.model_for(facts, "cpu")._forward_pre_hooks)
        self.assertFalse(self.train.model_for({}, "cpu")._forward_pre_hooks)

    def test_the_balanced_sampler_draws_a_rare_level_as_often_as_a_common_one(self):
        import torch

        targets = torch.tensor([0] * 95 + [1] * 5)
        order = self.blocks.balanced_order(targets, torch.Generator().manual_seed(2))
        self.assertEqual(len(order), 100)
        rare = int((targets[order] == 1).sum())
        self.assertGreater(rare, 30)
        self.assertTrue(torch.equal(self.blocks.uniform_order(targets, torch.Generator().manual_seed(2)),
                                    torch.randperm(100, generator=torch.Generator().manual_seed(2))))

    def test_inverse_frequency_weights_the_loss(self):
        import torch
        from schwingnet.blocks import parse

        targets = torch.tensor([0, 0, 0, 1])
        weighted = self.blocks.loss_function(parse(["loss_weights=inverse-frequency"]), targets, ["A", "B", "C"])
        self.assertEqual(weighted.weight.tolist(), [0.5, 1.5, 0.0])
        self.assertIsNone(self.blocks.loss_function(parse([]), targets, ["A", "B", "C"]).weight)

    def test_a_smaller_backbone_rate_splits_the_groups(self):
        from schwingnet.blocks import parse

        model = self.train.build_model(None, "cpu")
        one = self.blocks.OPTIMISERS["adam"](model, 1e-3, parse([]))
        self.assertEqual(len(one.param_groups), 1)
        two = self.blocks.OPTIMISERS["adamw"](model, 1e-3, parse(["optimiser=adamw", "weight_decay=0.01", "backbone_lr_scale=0.1"]))
        self.assertEqual([g["lr"] for g in two.param_groups], [1e-4, 1e-3])
        self.assertEqual(len(two.param_groups[1]["params"]), 2)

    def test_no_block_trains_version_1s_epoch_to_the_bit(self):
        import torch
        from torch import nn

        inputs, targets = self.batch(1).repeat(4, 1, 1, 1), torch.arange(24) % 27

        def legacy(model):
            optimiser = torch.optim.Adam(model.parameters(), lr=1e-3)
            generator = torch.Generator().manual_seed(5)
            model.train()
            order = torch.randperm(len(inputs), generator=generator)
            for start in range(0, len(order), 8):
                index = order[start : start + 8]
                optimiser.zero_grad()
                nn.CrossEntropyLoss()(model(inputs[index]), targets[index]).backward()
                optimiser.step()
            return model.state_dict()

        def current(model):
            optimiser = self.blocks.OPTIMISERS["adam"](model, 1e-3, self.train.from_record(None))
            self.train.set_rate(optimiser, [g["lr"] for g in optimiser.param_groups], 1.0)
            self.train.train_epoch(model, optimiser, inputs, targets, "cpu", 8, torch.Generator().manual_seed(5))
            return model.state_dict()

        torch.manual_seed(9)
        before = self.train.build_model(None, "cpu").state_dict()
        old, new = self.train.build_model(None, "cpu"), self.train.build_model(None, "cpu")
        old.load_state_dict(before), new.load_state_dict(before)
        old_state, new_state = legacy(old), current(new)
        self.assertTrue(all(torch.equal(old_state[k], new_state[k]) for k in old_state))


@unittest.skipIf(MISSING, f"needs the train environment ({', '.join(MISSING)} missing)")
class RunWithEveryBlockTest(unittest.TestCase):
    """One short run on a synthetic catalog with every block on: what it writes, and what reads it."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.catalog = cls.make_catalog(cls.tmp)
        cls.run_dir = cls.tmp / "run"
        cls.run_dir.mkdir()
        record = {"run_id": "blocksrun000", "code_commit": "0" * 40, "catalog_sha256": "0" * 64, "catalog_version": 1, "clean_tree": True}
        (cls.run_dir / "RUN.json").write_text(json.dumps(record), encoding="utf-8")
        words = ["normalise=imagenet", "augment=box-jitter,intensity,blur,noise", "optimiser=adamw", "weight_decay=0.01",
                 "schedule=cosine", "warmup_epochs=1", "backbone_lr_scale=0.5", "sampler=balanced",
                 "loss_weights=inverse-frequency", "select=balanced-accuracy"]
        args = ["--catalog", str(cls.catalog), "--out", str(cls.run_dir), "--epochs", "3", "--seed", "1", "--size", "32",
                "--device", "cpu", "--witness", "2", "--keep-epochs", "0"]
        for word in words:
            args += ["--block", word]
        with mock.patch.dict(os.environ, {"SCHWINGNET_WANDB": "off"}):
            cls.rc = load("train").main(args)

    @classmethod
    def make_catalog(cls, tmp):
        python(ROOT / "tools" / "synthetic_bank.py", tmp / "bank-train", "--frames", "60", "--cases", "8", "--seed", "3")
        seen = set()
        for image in sorted((tmp / "bank-train" / "images").rglob("*.png")):
            digest = hashlib.sha256(image.read_bytes()).hexdigest()
            if digest in seen:
                image.unlink()
                (tmp / "bank-train" / "meta" / f"{image.stem}.json").unlink()
            seen.add(digest)
        python(ROOT / "tools" / "ingest.py", "run", "--bank", tmp / "bank-train", "--source", "carmlspine", "--kind", "train",
               "--date", "2026-10-24", "--code-commit", "0" * 40, "--grid-root", tmp / "carmlspine")
        manifests = []
        for manifest in sorted((tmp / "carmlspine").rglob("MANIFEST.json")):
            manifests += ["--manifest", manifest]
        built = json.loads(python(ROOT / "tools" / "catalog.py", "build", "--store", tmp / "store", *manifests, "--root", tmp))
        return tmp / "store" / "versions" / built["file"]

    def test_the_run_records_its_blocks_and_the_schedule(self):
        self.assertEqual(self.rc, 0)
        facts = json.loads((self.run_dir / "train" / "checkpoint.json").read_text(encoding="utf-8"))
        self.assertEqual(facts["blocks"]["normalise"], "imagenet")
        self.assertEqual(facts["blocks"]["augment"], ["box-jitter", "intensity", "blur", "noise"])
        lines = [json.loads(line) for line in (self.run_dir / "train" / "metrics.jsonl").read_text(encoding="utf-8").splitlines()]
        rates = [line["learning_rate"] for line in lines]
        self.assertIsNone(rates[0])
        self.assertAlmostEqual(rates[1], 0.5e-3)
        self.assertAlmostEqual(rates[2], 1e-3)
        self.assertLess(rates[3], rates[2])
        self.assertTrue(all("validation_balanced_accuracy" in line for line in lines))
        self.assertIn("- Blocks: normalise imagenet", (self.run_dir / "train" / "MODEL.md").read_text(encoding="utf-8"))

    def test_the_latency_tool_loads_the_scaled_model_and_onnx_keeps_the_scaling(self):
        latency = load("latency")
        model, _ = latency.load_torch_model(self.run_dir, "cpu")
        self.assertTrue(model._forward_pre_hooks)
        latency.export(self.run_dir)
        verdict = latency.parity(self.run_dir, self.catalog, "validation", 8, "onnxruntime", "cpu", 1)
        self.assertTrue(verdict["passed"], verdict)

    def test_compare_ranks_the_run_by_validation_and_names_its_blocks(self):
        sweep_tool = load("block_sweep")
        rows = sweep_tool.compare([self.run_dir], "balanced-accuracy")
        self.assertEqual(len(rows), 1)
        self.assertIn("normalise=imagenet", rows[0]["blocks"])
        self.assertIn("| blocksrun000 |".replace("blocksrun000", self.run_dir.name), sweep_tool.table(rows))

    def test_a_block_that_does_not_exist_stops_the_run_in_words(self):
        args = ["--catalog", str(self.catalog), "--out", str(self.run_dir), "--epochs", "1", "--seed", "1", "--block", "normalise=zscore"]
        self.assertEqual(load("train").main(args), 1)



FLOW_NEEDS = ("beartype", "icontract", "pydantic")


@unittest.skipIf([n for n in FLOW_NEEDS if importlib.util.find_spec(n) is None], "needs the package's checkers")
class FlowBlocksTest(unittest.TestCase):
    """tools/flow.py passes the blocks to the trainer and refuses a wrong one before any step."""

    def test_blocks_pass_through_and_a_fault_stops_the_plan(self):
        flow = load("flow")
        self.assertEqual(flow.block_words([]), "")
        self.assertEqual(flow.block_words(["normalise=imagenet", "augment=noise,blur"]),
                         " --block normalise=imagenet --block augment=noise,blur")
        for words in (["normalise=zscore"], ["augment=noise, blur"], ["sampler=balanced", "sampler=uniform"]):
            with self.subTest(words=words), self.assertRaises(flow.FlowError):
                flow.block_words(words)

    def test_a_sweep_plan_counts_its_runs_and_starts_nothing(self):
        sweep_tool = load("block_sweep")
        args = sweep_tool.parse_args(["plan", "--catalog", "c.sqlite", "--out", "runs", "--epochs", "20", "--hours", "4",
                                      "--base", "normalise=imagenet", "--vary", "augment=none/box-jitter,intensity",
                                      "--vary", "sampler=uniform/balanced"])
        planned = sweep_tool.plan(args)
        self.assertEqual((planned["runs"], planned["jobs"], planned["gpu_hours_requested"]), (4, 8, 20.0))
        self.assertTrue(all(c.startswith("python3 tools/flow.py run") for c in planned["commands"]))
        self.assertIn("--block augment=box-jitter,intensity --block sampler=balanced", planned["commands"][3])
        self.assertEqual(sweep_tool.main(["plan", "--catalog", "c", "--out", "r", "--epochs", "1", "--vary", "colour=red"]), 1)


if __name__ == "__main__":
    unittest.main()
