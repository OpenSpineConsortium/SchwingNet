"""tools/train.py's crop loading: one decode per frame gives the same pixels as one decode per body.

load_crops decodes a frame once for a run of its bodies, since read_crops orders the crops by
frame; this test holds it to the per-body crop_pixels exactly, on frames in order and shuffled,
so the change can never move a number. It needs torch, Pillow and the package's checkers, so it
runs in the train-cpu environment (`pixi run -e train-cpu python -m unittest
tests.test_train_crops`) and skips under the required check's plain python3."""

import importlib.util
import random
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEEDED = ("torch", "PIL", "numpy", "beartype", "icontract")
MISSING = [name for name in NEEDED if importlib.util.find_spec(name) is None]


def load_train():
    spec = importlib.util.spec_from_file_location("train_under_test", ROOT / "tools" / "train.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipIf(MISSING, f"needs the train environment ({', '.join(MISSING)} missing)")
class LoadCropsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import numpy as np
        from PIL import Image

        cls.train = load_train()
        cls.tmp = Path(tempfile.mkdtemp())
        noise = np.random.default_rng(5)
        cls.crops = []
        for n in range(4):
            frame = cls.tmp / f"frame-{n}.png"
            Image.fromarray(noise.integers(0, 256, (90 + 7 * n, 120), dtype=np.uint8)).save(frame)
            for k, level in enumerate(("L1", "L2", "L3")):
                box = (0.1 + 0.05 * k, 0.1 + 0.2 * k, 0.6 + 0.1 * k, 0.3 + 0.2 * k)
                cls.crops.append({"level": level, "box": box, "frame": str(frame)})

    def per_body(self, crops, size):
        import numpy as np

        return np.stack([self.train.crop_pixels(c["frame"], c["box"], size) for c in crops])

    def test_frames_in_order_match_per_body_crops(self):
        counts = {}
        inputs, targets = self.train.load_crops(self.crops, 32, counts)
        self.assertEqual(tuple(inputs.shape), (12, 3, 32, 32))
        for channel in range(3):
            self.assertTrue((inputs[:, channel].numpy() == self.per_body(self.crops, 32)).all())
        self.assertEqual(targets.tolist(), [self.train.LEVELS.index(c["level"]) for c in self.crops])
        self.assertEqual((counts["opened"], counts["decoded"]), (12, 4))

    def test_shuffled_crops_still_match(self):
        shuffled = list(self.crops)
        random.Random(2).shuffle(shuffled)
        counts = {}
        inputs, _ = self.train.load_crops(shuffled, 24, counts)
        self.assertTrue((inputs[:, 0].numpy() == self.per_body(shuffled, 24)).all())
        self.assertLessEqual(counts["decoded"], 12)


if __name__ == "__main__":
    unittest.main()
