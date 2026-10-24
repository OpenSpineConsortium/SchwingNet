"""tools/train.py's --init: a run that starts from a parent checkpoint instead of ImageNet, the
incremental run of docs/research/retraining-plan.md, section 3.4. The child starts from the
parent's weights exactly, records which parent it came from, says so on its card, and is refused
in words where the parent was trained to see its input differently.

It needs the train environment, as tests/test_train_blocks.py does, and skips under the required
check's plain python3."""

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
NEEDED = ("torch", "onnx", "onnxruntime", "PIL", "beartype", "icontract", "pydantic")
MISSING = [name for name in NEEDED if importlib.util.find_spec(name) is None]


def load(name):
    spec = importlib.util.spec_from_file_location(f"{name}_init_under_test", ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def new_run(folder, run_id):
    folder.mkdir(parents=True)
    record = {"run_id": run_id, "code_commit": "0" * 40, "catalog_sha256": "0" * 64, "catalog_version": 1, "clean_tree": True}
    (folder / "RUN.json").write_text(json.dumps(record), encoding="utf-8")
    return folder


@unittest.skipIf(MISSING, f"needs the train environment ({', '.join(MISSING)} missing)")
class InitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_train_blocks import RunWithEveryBlockTest

        cls.tmp = Path(tempfile.mkdtemp())
        cls.catalog = RunWithEveryBlockTest.make_catalog(cls.tmp)
        cls.parent = new_run(cls.tmp / "parent", "parentrun000")
        cls.rc = cls.train(cls.parent)

    @classmethod
    def train(cls, folder, *extra):
        args = ["--catalog", str(cls.catalog), "--out", str(folder), "--epochs", "1", "--seed", "1", "--size", "32",
                "--device", "cpu", "--witness", "2", "--keep-epochs", "0", *extra]
        with mock.patch.dict(os.environ, {"SCHWINGNET_WANDB": "off"}):
            return load("train").main(args)

    def best(self):
        return self.parent / "train" / "best.pt"

    def test_the_child_starts_from_the_parents_weights_exactly(self):
        import torch

        train = load("train")
        self.assertEqual(self.rc, 0)
        model = train.build_model(None, "cpu")
        parent = train.parent_of(self.best())
        train.warm_start(model, self.best(), parent, train.from_record(None), 32)
        saved = torch.load(self.best(), map_location="cpu", weights_only=True)
        self.assertTrue(all(torch.equal(saved[k], v) for k, v in model.state_dict().items()))
        self.assertEqual(parent["run_id"], "parentrun000")

    def test_the_child_records_its_parent_and_says_so(self):
        train = load("train")
        child = new_run(self.tmp / "child", "childrun0000")
        self.assertEqual(self.train(child, "--init", str(self.best())), 0)
        facts = json.loads((child / "train" / "checkpoint.json").read_text(encoding="utf-8"))
        self.assertEqual(facts["parent"], {"file": "best.pt", "sha256": train.sha256_of(self.best()), "run_id": "parentrun000"})
        card = (child / "train" / "MODEL.md").read_text(encoding="utf-8")
        self.assertIn("an incremental run", card)
        self.assertIn("run parentrun000", card)

    def test_a_run_from_imagenet_or_scratch_records_no_parent(self):
        facts = json.loads((self.parent / "train" / "checkpoint.json").read_text(encoding="utf-8"))
        self.assertIsNone(facts["parent"])
        self.assertIn("a rebase", (self.parent / "train" / "MODEL.md").read_text(encoding="utf-8"))

    def test_a_parent_that_saw_its_input_differently_is_refused(self):
        child = new_run(self.tmp / "scaled", "scaledrun000")
        self.assertEqual(self.train(child, "--init", str(self.best()), "--block", "normalise=imagenet"), 1)
        resized = new_run(self.tmp / "resized", "resizedrun00")
        args = ["--catalog", str(self.catalog), "--out", str(resized), "--epochs", "1", "--seed", "1", "--size", "48",
                "--device", "cpu", "--witness", "2", "--keep-epochs", "0", "--init", str(self.best())]
        with mock.patch.dict(os.environ, {"SCHWINGNET_WANDB": "off"}):
            self.assertEqual(load("train").main(args), 1)

    def test_imagenet_and_a_parent_together_or_a_missing_parent_are_refused(self):
        both = new_run(self.tmp / "both", "bothrun00000")
        self.assertEqual(self.train(both, "--init", str(self.best()), "--weights", str(self.best())), 1)
        missing = new_run(self.tmp / "missing", "missingrun00")
        self.assertEqual(self.train(missing, "--init", str(self.tmp / "nowhere.pt")), 1)


if __name__ == "__main__":
    unittest.main()
