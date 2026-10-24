"""tools/train.py's seed_everything: the deterministic setting holds on the GPU as well (#199).

cuBLAS is deterministic only with CUBLAS_WORKSPACE_CONFIG set before CUDA starts, so the seed sets
it, keeping a value the environment already gives, and leaves cuDNN's benchmark search off. It
needs torch and the package's checkers, so it runs in the train-cpu environment and skips under the
required check's plain python3."""

import importlib.util
import os
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
NEEDED = ("torch", "PIL", "numpy", "beartype", "icontract")
MISSING = [name for name in NEEDED if importlib.util.find_spec(name) is None]


def load_train():
    spec = importlib.util.spec_from_file_location("train_seed_under_test", ROOT / "tools" / "train.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipIf(MISSING, f"needs the train environment ({', '.join(MISSING)} missing)")
class SeedTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.train = load_train()

    def test_the_workspace_is_fixed_and_benchmark_off(self):
        import torch

        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CUBLAS_WORKSPACE_CONFIG", None)
            self.train.seed_everything(3)
            self.assertEqual(os.environ["CUBLAS_WORKSPACE_CONFIG"], self.train.CUBLAS_WORKSPACE)
        self.assertFalse(torch.backends.cudnn.benchmark)
        self.assertTrue(torch.are_deterministic_algorithms_enabled())

    def test_a_value_the_environment_gives_is_kept(self):
        with mock.patch.dict(os.environ, {"CUBLAS_WORKSPACE_CONFIG": ":16:8"}):
            self.train.seed_everything(3)
            self.assertEqual(os.environ["CUBLAS_WORKSPACE_CONFIG"], ":16:8")

    def test_the_same_seed_gives_the_same_draws(self):
        import torch

        self.train.seed_everything(11)
        first = torch.rand(5)
        self.train.seed_everything(11)
        self.assertTrue(torch.equal(first, torch.rand(5)))


if __name__ == "__main__":
    unittest.main()
