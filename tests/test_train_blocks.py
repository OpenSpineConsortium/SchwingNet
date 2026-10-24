"""The torch side of the trainer's building blocks (tools/train_blocks.py) and their wiring in
tools/train.py: version 1's epoch is unchanged when no block is named, each block does what its
name says, a run with every block on writes its choices where the evaluator and the latency tool
read them, and the ImageNet scaling inside the model survives the ONNX export.

It needs torch, onnx, onnxruntime, Pillow and the package's checkers, so it runs in the train-cpu
environment (`pixi run -e train-cpu python -m unittest tests.test_train_blocks`) and skips under the
required check's plain python3."""

import contextlib
import hashlib
import importlib.util
import json
import os
import shutil
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
        self.assertEqual(set(self.blocks.ARCHITECTURES), set(blocks.ARCHITECTURE))
        self.assertEqual(set(self.blocks.HEADS), set(blocks.ARCHITECTURE))
        self.assertEqual(set(self.blocks.LIBRARIES), set(blocks.ARCHITECTURE))
        self.assertEqual(self.blocks.architecture_words("resnet18"), "torchvision resnet18")
        self.assertEqual(self.blocks.architecture_words("se-resnet50"), "MONAI se-resnet50")
        self.assertEqual(set(self.blocks.DENOISERS), set(blocks.DENOISE))

    def test_every_architecture_builds_a_27_way_head_that_the_imagenet_file_leaves_alone(self):
        import torch
        from schwingnet.blocks import ARCHITECTURE
        from schwingnet.catalog import LEVELS

        for name in ARCHITECTURE:
            with self.subTest(name=name):
                model = self.train.build_model(None, "cpu", architecture=name)
                model.eval()
                with torch.no_grad():
                    self.assertEqual(tuple(model(self.batch()).shape), (6, len(LEVELS)))
                prefix = self.blocks.HEADS[name]
                head = [n for n, _ in model.named_parameters() if n.startswith(prefix)]
                self.assertEqual(len(head), 2, prefix)
                # An ImageNet file of this architecture: the untrained network's own state with
                # its 1000-way head, which the loader must drop and the rest of which must fit.
                pretrained = self.blocks.ARCHITECTURES[name](1000, None).state_dict()
                file = Path(tempfile.mkdtemp()) / "imagenet.pt"
                torch.save(pretrained, file)
                loaded = self.train.build_model(str(file), "cpu", architecture=name)
                body = next(k for k in pretrained if not k.startswith(prefix))
                self.assertTrue(torch.equal(loaded.state_dict()[body], pretrained[body]))
                other = next(n for n in ARCHITECTURE if n != name)
                with self.assertRaises(self.train.TrainError):
                    self.train.build_model(str(file), "cpu", architecture=other)

    def test_torchvisions_densenet_file_loads_into_monais_in_either_spelling_and_monai_loads_lazily(self):
        import re
        import torch
        from torchvision import models

        folder = Path(tempfile.mkdtemp())
        saved = models.densenet121(weights=None).state_dict()
        # The published file's spelling (download.pytorch.org): "norm.1" where a saved state_dict says "norm1",
        # and no num_batches_tracked, which the file predates and BatchNorm fills in when it is missing.
        published = {re.sub(r"\.(norm|relu|conv)([12])\.", r".\1.\2.", k) if "denselayer" in k else k: v
                     for k, v in saved.items() if not k.endswith("num_batches_tracked")}
        self.assertNotEqual(set(saved), set(published))
        for spelling, state in (("saved", saved), ("published", published)):
            with self.subTest(spelling=spelling):
                file = folder / f"{spelling}.pt"
                torch.save(state, file)
                model = self.train.build_model(str(file), "cpu", architecture="densenet121")
                loaded = model.state_dict()
                self.assertTrue(torch.equal(loaded["features.denseblock1.denselayer1.layers.conv1.weight"], saved["features.denseblock1.denselayer1.conv1.weight"]))
                self.assertTrue(torch.equal(loaded["features.norm5.weight"], saved["features.norm5.weight"]))
                self.assertEqual(tuple(loaded["class_layers.out.weight"].shape), (27, 1024))
                with self.assertRaises(self.train.TrainError):
                    self.train.build_model(str(file), "cpu", architecture="se-resnet50")
        # A run of a torchvision name never imports monai: the three MONAI names import it when built.
        code = ("import importlib.util, sys; spec = importlib.util.spec_from_file_location('tb', sys.argv[1]); "
                "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); m.ARCHITECTURES['resnet18'](27, None); "
                "print('monai' in sys.modules); m.ARCHITECTURES['se-resnext50'](27, None); print('monai' in sys.modules)")
        self.assertEqual(python("-c", code, ROOT / "tools" / "train_blocks.py").split(), ["False", "True"])

    def test_each_denoise_keeps_shape_and_range_and_smooths_noise(self):
        import torch
        from schwingnet.blocks import DENOISE

        flat = torch.full((2, 3, 16, 16), 0.5)
        speckled = flat.clone()
        speckled[:, :, 5, 7] = 1.0
        for name in DENOISE:
            with self.subTest(name=name):
                model = self.train.build_model(None, "cpu", denoise=name)
                hooks = list(model._forward_pre_hooks.values())
                self.assertEqual(len(hooks), 0 if name == "none" else 1)
                if not hooks:
                    continue
                (out,) = hooks[0](model, (speckled,))
                self.assertEqual(tuple(out.shape), (2, 3, 16, 16))
                self.assertTrue(torch.allclose(hooks[0](model, (flat,))[0], flat))
                self.assertLess(float(out[0, 0, 5, 7]), 1.0)
                self.assertGreaterEqual(float(out.min()), 0.5 - 1e-6)
                self.assertLessEqual(float(out.max()), 1.0 + 1e-6)
        median = self.train.build_model(None, "cpu", denoise="median")
        (out,) = list(median._forward_pre_hooks.values())[0](median, (speckled,))
        self.assertTrue(torch.equal(out, flat))

    def test_denoise_then_scaling_survive_the_onnx_export_for_every_architecture(self):
        import numpy as np
        import onnxruntime as ort
        import torch
        from schwingnet.blocks import ARCHITECTURE, DENOISE

        latency = load("latency")
        cases = [("resnet18", name) for name in DENOISE] + [(name, "median") for name in ARCHITECTURE if name != "resnet18"]
        folder = Path(tempfile.mkdtemp())
        for architecture, denoise in cases:
            with self.subTest(architecture=architecture, denoise=denoise):
                torch.manual_seed(1)
                model = self.train.build_model(None, "cpu", "imagenet", architecture, denoise).eval()
                path = folder / f"{architecture}-{denoise}.onnx"
                torch.onnx.export(model, (torch.zeros(1, 3, 32, 32),), str(path), input_names=["crops"], output_names=["logits"],
                                  dynamic_axes={"crops": {0: "boxes"}, "logits": {0: "boxes"}}, opset_version=latency.OPSET, dynamo=False)
                batch = self.batch(2)
                with torch.no_grad():
                    expected = model(batch).numpy()
                session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
                (got,) = session.run(None, {"crops": batch.numpy()})
                np.testing.assert_allclose(got, expected, rtol=1e-3, atol=1e-4)

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


@unittest.skipIf(MISSING, f"needs the train environment ({', '.join(MISSING)} missing)")
class RunWithSamplesArchitectureAndDenoiseTest(unittest.TestCase):
    """One short run with the three parts of #207 on: the crops it saw are recorded against the
    crops offered, every reader builds the same model from the record, the ONNX parity holds with
    the median filter inside the model, and the ledger finds the run under its folder."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.catalog = RunWithEveryBlockTest.make_catalog(cls.tmp)
        cls.run_dir = cls.tmp / "runs" / "2026" / "capped"
        cls.run_dir.mkdir(parents=True)
        record = {"run_id": "capped000000", "code_commit": "0" * 40, "catalog_sha256": "0" * 64, "catalog_version": 1, "clean_tree": True}
        (cls.run_dir / "RUN.json").write_text(json.dumps(record), encoding="utf-8")
        cls.words = ["samples=cap-per-person", "per_person=2", "architecture=mobilenet-v3-small", "denoise=median"]
        args = ["--catalog", str(cls.catalog), "--out", str(cls.run_dir), "--epochs", "1", "--seed", "1", "--size", "32",
                "--device", "cpu", "--witness", "2", "--keep-epochs", "0"]
        for word in cls.words:
            args += ["--block", word]
        with mock.patch.dict(os.environ, {"SCHWINGNET_WANDB": "off"}):
            cls.rc = load("train").main(args)

    def test_the_record_says_what_the_run_saw_of_what_it_was_offered(self):
        self.assertEqual(self.rc, 0)
        facts = json.loads((self.run_dir / "train" / "checkpoint.json").read_text(encoding="utf-8"))
        self.assertEqual(facts["blocks"]["samples"], "cap-per-person")
        self.assertEqual(facts["blocks"]["architecture"], "mobilenet-v3-small")
        counts = facts["counts"]
        self.assertLess(counts["train"], counts["train_offered"])
        self.assertLessEqual(counts["train"], 2 * counts["train_persons"])
        self.assertEqual((counts["train_seen"], counts["validation_offered"]), (counts["train"], counts["validation"]))
        card = (self.run_dir / "train" / "MODEL.md").read_text(encoding="utf-8")
        self.assertIn("torchvision mobilenet-v3-small", card)
        self.assertIn(f"Training crops {counts['train']} of the {counts['train_offered']}", card)
        self.assertIn(f"validation crops {counts['validation']}, the whole part", card)

    def test_a_source_the_train_part_lacks_is_refused_and_a_cap_is_told_apart_from_the_block(self):
        train = load("train")
        crops = train.read_crops(self.catalog, train.TRAIN_PARTS)
        with self.assertRaises(train.TrainError) as refused:
            train.training_crops(crops, train.parse_blocks(["samples=drop-sources", "sources=carmlspine,vindr"]))
        self.assertIn("sources=vindr: not in the catalog's train part", str(refused.exception))
        counts = {"train": 3, "train_seen": 7, "train_offered": 176, "train_persons": 2,
                  "validation": 3, "validation_offered": 29, "validation_persons": 1}
        capped = train.from_record({"samples": "cap-per-person", "per_person": 1})
        self.assertEqual(train.seen_words(counts, capped),
                         "7 of the 176 the catalog's train part holds (samples cap-per-person), capped to 3 by --max-frames, from 2 persons")
        self.assertEqual(train.validation_words(counts), "3, of the 29 the part holds, capped by --max-frames, from 1 persons")
        sweep_tool = load("block_sweep")
        self.assertEqual(sweep_tool.crops_text({"train_crops": 3, "train_seen": 7, "train_offered": 176}), "7 of 176, capped to 3")
        self.assertEqual(sweep_tool.crops_text({"train_crops": 10, "train_seen": None, "train_offered": None}), "10")
        self.assertEqual(sweep_tool.parent_text({"file": "best.pt", "sha256": "ab" * 32, "run_id": None}), "file best.pt (sha256 abababababab)")

    def test_every_reader_builds_the_recorded_model_and_the_onnx_parity_holds(self):
        latency = load("latency")
        model, facts = latency.load_torch_model(self.run_dir, "cpu")
        self.assertEqual(len(model._forward_pre_hooks), 1)
        self.assertEqual(type(model).__name__, "MobileNetV3")
        latency.export(self.run_dir)
        verdict = latency.parity(self.run_dir, self.catalog, "validation", 8, "onnxruntime", "cpu", 1)
        self.assertTrue(verdict["passed"], verdict)

    def test_the_ledger_finds_the_run_under_its_folder_and_parts_lists_the_new_parts(self):
        sweep_tool = load("block_sweep")
        rows = sweep_tool.ledger(self.tmp / "runs", "accuracy")
        self.assertEqual([row["run"] for row in rows], ["capped"])
        self.assertEqual(rows[0]["blocks"], " ".join(self.words))
        self.assertEqual(rows[0]["parent"], "none")
        self.assertEqual(rows[0]["latency"], "not measured")
        self.assertIn(f"| {rows[0]['train_crops']} of {rows[0]['train_offered']} |", sweep_tool.table(rows))
        self.assertIn("| architecture | resnet18, resnet34, resnet50, mobilenet-v3-small, efficientnet-b0, densenet121, se-resnet50, se-resnext50 | resnet18 |",
                      sweep_tool.parts_table())
        with self.assertRaises(sweep_tool.BlockError):
            sweep_tool.ledger(self.tmp / "nowhere", "accuracy")
        linked = self.tmp / "linked"
        linked.mkdir()
        (linked / "to-runs").symlink_to(self.tmp / "runs")
        (linked / "again").symlink_to(self.tmp / "runs")
        (linked / "back").symlink_to(self.tmp)
        self.assertEqual([row["run"] for row in sweep_tool.ledger(linked, "accuracy")], ["capped"])
        with contextlib.chdir(self.run_dir):
            self.assertEqual(sweep_tool.compare(["."], "accuracy")[0]["run"], "capped")
        broken = self.tmp / "broken" / "halfway" / "train"
        broken.mkdir(parents=True)
        shutil.copy(self.run_dir / "train" / "checkpoint.json", broken / "checkpoint.json")
        (broken / "metrics.jsonl").write_text('{"epoch": 0}\n', encoding="utf-8")
        with self.assertRaises(sweep_tool.BlockError) as refused:
            sweep_tool.ledger(self.tmp / "broken", "accuracy")
        self.assertIn("halfway", str(refused.exception))
        self.assertIn("holds no epoch 1", str(refused.exception))
        (broken / "checkpoint.json").write_text('{"epoch": 1, "blocks": {"architecture": null}}', encoding="utf-8")
        (broken / "metrics.jsonl").write_text('{"epoch": 1}\n', encoding="utf-8")
        self.assertEqual(sweep_tool.main(["ledger", str(self.tmp / "broken")]), 1)

    def test_a_samples_block_that_leaves_nothing_stops_the_run_in_words(self):
        out = self.tmp / "runs" / "empty"
        out.mkdir()
        (out / "RUN.json").write_text((self.run_dir / "RUN.json").read_text(encoding="utf-8"), encoding="utf-8")
        args = ["--catalog", str(self.catalog), "--out", str(out), "--epochs", "1", "--seed", "1", "--block", "samples=only-sources", "--block", "sources=nowhere"]
        self.assertEqual(load("train").main(args), 1)

    def test_a_warm_start_from_another_architecture_is_refused(self):
        train = load("train")
        out = self.tmp / "runs" / "child"
        out.mkdir()
        (out / "RUN.json").write_text((self.run_dir / "RUN.json").read_text(encoding="utf-8"), encoding="utf-8")
        args = ["--catalog", str(self.catalog), "--out", str(out), "--epochs", "1", "--seed", "1", "--init", str(self.run_dir / "train" / "best.pt")]
        self.assertEqual(train.main(args), 1)
        parent = train.parent_of(self.run_dir / "train" / "best.pt")
        with self.assertRaises(train.TrainError) as refused:
            train.warm_start(train.build_model(None, "cpu"), self.run_dir / "train" / "best.pt", parent, train.from_record(None), 32)
        self.assertIn("architecture=mobilenet-v3-small", str(refused.exception))



FLOW_NEEDS = ("beartype", "icontract", "pydantic")


@unittest.skipIf(MISSING, f"needs the train environment ({', '.join(MISSING)} missing)")
class RunWithAMonaiArchitectureTest(unittest.TestCase):
    """One short run with a MONAI network (#211), densenet121, the smallest of the three: the card
    names the library, every reader builds MONAI's class from the record, and the ONNX parity
    holds, so a MONAI name goes end to end as a torchvision name does and not only through
    build_model."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.catalog = RunWithEveryBlockTest.make_catalog(cls.tmp)
        cls.run_dir = cls.tmp / "runs" / "2026" / "monai"
        cls.run_dir.mkdir(parents=True)
        record = {"run_id": "monai0000000", "code_commit": "0" * 40, "catalog_sha256": "0" * 64, "catalog_version": 1, "clean_tree": True}
        (cls.run_dir / "RUN.json").write_text(json.dumps(record), encoding="utf-8")
        args = ["--catalog", str(cls.catalog), "--out", str(cls.run_dir), "--epochs", "1", "--seed", "1", "--size", "32",
                "--device", "cpu", "--witness", "2", "--keep-epochs", "0", "--block", "architecture=densenet121"]
        with mock.patch.dict(os.environ, {"SCHWINGNET_WANDB": "off"}):
            cls.rc = load("train").main(args)

    def test_the_card_and_the_record_name_monais_network(self):
        self.assertEqual(self.rc, 0)
        facts = json.loads((self.run_dir / "train" / "checkpoint.json").read_text(encoding="utf-8"))
        self.assertEqual(facts["blocks"]["architecture"], "densenet121")
        card = (self.run_dir / "train" / "MODEL.md").read_text(encoding="utf-8")
        self.assertIn("- Architecture: MONAI densenet121, 27-way head", card)
        self.assertNotIn("torchvision densenet121", card)

    def test_every_reader_builds_monais_class_and_the_onnx_parity_holds(self):
        latency = load("latency")
        model, facts = latency.load_torch_model(self.run_dir, "cpu")
        self.assertEqual(type(model).__name__, "DenseNet121")
        self.assertEqual(type(model).__module__.split(".")[0], "monai")
        latency.export(self.run_dir)
        verdict = latency.parity(self.run_dir, self.catalog, "validation", 8, "onnxruntime", "cpu", 1)
        self.assertTrue(verdict["passed"], verdict)


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

    def test_a_sweep_over_architectures_takes_one_imagenet_file_each_or_none(self):
        sweep_tool = load("block_sweep")
        head = ["plan", "--catalog", "c", "--out", "r", "--epochs", "1", "--vary", "architecture=resnet18/mobilenet-v3-small"]
        with self.assertRaises(sweep_tool.BlockError):
            sweep_tool.plan(sweep_tool.parse_args([*head, "--weights", "r18.pth"]))
        commands = sweep_tool.plan(sweep_tool.parse_args([*head, "--weights", "r18.pth", "--weights", "mobilenet-v3-small=mnv3.pth"]))["commands"]
        self.assertTrue(commands[0].endswith("--weights r18.pth"), commands[0])
        self.assertTrue(commands[1].endswith("--weights mnv3.pth --block architecture=mobilenet-v3-small"), commands[1])
        self.assertEqual(sweep_tool.plan(sweep_tool.parse_args(head))["commands"][1].count("--weights"), 0)
        for words in (["resnet19=x.pth"], ["r18.pth", "resnet18=again.pth"], ["mobilenet-v3-small="]):
            with self.subTest(words=words), self.assertRaises(sweep_tool.BlockError):
                sweep_tool.weights_files(words)
        self.assertEqual(sweep_tool.weights_files(["/models/a=b/r18.pth"]), {"resnet18": "/models/a=b/r18.pth"})


if __name__ == "__main__":
    unittest.main()
