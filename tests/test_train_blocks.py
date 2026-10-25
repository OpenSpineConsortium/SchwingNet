"""The torch side of the trainer's building blocks (tools/train_blocks.py) and their wiring in
tools/train.py: version 1's epoch is unchanged when no block is named, each block does what its
name says, a run with every block on writes its choices where the evaluator and the latency tool
read them, and the ImageNet scaling inside the model survives the ONNX export.

It needs torch, onnx, onnxruntime, Pillow and the package's checkers, so it runs in the train-cpu
environment (`pixi run -e train-cpu python -m unittest tests.test_train_blocks`) and skips under the
required check's plain python3."""

import base64
import contextlib
import hashlib
import importlib.util
import io
import json
import math
import os
import shutil
import statistics
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


def sha256_of(path):
    """A catalog's sha256, as tools/flow.py writes it into RUN.json, the catalog the trainer then
    reads and no other."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def python(*args):
    done = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, timeout=600)
    if done.returncode != 0:
        raise AssertionError(f"{args}: {done.stdout}\n{done.stderr}")
    return done.stdout


def structured_plane(height, width, seed):
    """A byte image whose tiles CLAHE equalises differently: a diagonal ramp and a bright block
    under a little noise, with a dark row and a dark column next to the bottom and right edges,
    which a pad that mirrors the edge carries into the padding and one that repeats it does not.
    It is made in integers, the noise by a linear congruential draw, so OPENCV_CLAHE, OpenCV's
    output for it, holds on any machine."""
    state, rows = seed, []
    for y in range(height):
        row = []
        for x in range(width):
            state = (1103515245 * state + 12345) % 2**31
            value = 30 + 160 * (x + y) // (height + width) + (state >> 16) % 32
            if width // 4 <= x < width // 2 and height // 3 <= y < 2 * height // 3:
                value += 50
            if y == height - 3 or x == width - 2:
                value = 5
            row.append(min(value, 255))
        rows.append(row)
    return rows


def tile_equaliser(levels, limit, bins=256):
    """One tile's equaliser written out as OpenCV's clahe.cpp computes it, loop by loop: the
    histogram clipped at the limit, the excess spread evenly, the remainder one each from the first
    bin on at a step of bins over the remainder, and the running sum over the tile's pixels."""
    histogram = [0] * bins
    for level in levels:
        histogram[level] += 1
    excess = 0
    for i in range(bins):
        if histogram[i] > limit:
            excess += histogram[i] - limit
            histogram[i] = limit
    histogram = [count + excess // bins for count in histogram]
    remainder = excess % bins
    if remainder:
        step, i = max(bins // remainder, 1), 0
        while i < bins and remainder > 0:
            histogram[i] += 1
            i, remainder = i + step, remainder - 1
    running, out = 0, []
    for count in histogram:
        running += count
        out.append(running / len(levels))
    return out


def reflect_101(place, length):
    """The pixel a place outside a side of length pixels reads under OpenCV's BORDER_REFLECT_101,
    as its borderInterpolate loops to it: mirrored about the edge pixel, which is not repeated."""
    if length == 1:
        return 0
    while not 0 <= place < length:
        place = -place if place < 0 else 2 * length - 2 - place
    return place


def reference_clahe(image, clip, tiles=8, bins=256):
    """CLAHE of one plane, a list of rows of 0..1 values, pixel by pixel in plain python as
    OpenCV's clahe.cpp computes it: the plane padded at the bottom and right to whole tiles by
    BORDER_REFLECT_101, both sides by tiles less their remainder once either side is no multiple,
    OpenCV's clip limit from clip, and each pixel's level mapped by the equalisers of the tiles
    whose centres are on either side of x / tile - 0.5 (CLAHE_Interpolation_Body), the weight
    taken before the tiles are clamped to the outer ones. It keeps the equalisers as fractions,
    where OpenCV rounds them to a byte."""
    height, width = len(image), len(image[0])
    tall, wide = height, width
    if height % tiles or width % tiles:
        tall, wide = height + tiles - height % tiles, width + tiles - width % tiles
    levels = [[round(min(max(image[reflect_101(y, height)][reflect_101(x, width)], 0.0), 1.0) * (bins - 1)) for x in range(wide)]
              for y in range(tall)]
    tile_tall, tile_wide = tall // tiles, wide // tiles
    limit = max(int(clip * tile_tall * tile_wide / bins), 1)
    maps = [[tile_equaliser([levels[y][x] for y in range(r * tile_tall, (r + 1) * tile_tall) for x in range(c * tile_wide, (c + 1) * tile_wide)], limit, bins)
             for c in range(tiles)] for r in range(tiles)]

    def between(position, tile):
        place = position / tile - 0.5
        first = math.floor(place)
        return max(first, 0), min(first + 1, tiles - 1), place - first

    out = []
    for y in range(height):
        top, bottom, down = between(y, tile_tall)
        line = []
        for x in range(width):
            left, right, across = between(x, tile_wide)
            level = levels[y][x]
            upper = (1 - across) * maps[top][left][level] + across * maps[top][right][level]
            lower = (1 - across) * maps[bottom][left][level] + across * maps[bottom][right][level]
            line.append((1 - down) * upper + down * lower)
        out.append(line)
    return out


# OpenCV's own CLAHE of structured_plane(height, width, 100 * height + width), its bytes row by row
# in base64, keyed by (height, width): cv2.createCLAHE(clipLimit, tileGridSize=(8, 8)).apply() of
# OpenCV 4.10.0 (the wheel opencv-python-headless 4.10.0.84 unpacked outside any environment, once,
# never a dependency). A tile here holds at most 16 pixels, so its clip limit is one count for any
# clip under 16 and the bytes are the same whatever clip a crop draws in CLAHE_CLIP. 32 by 32 pads
# nothing; 20 by 20 pads 4 rows and 4 columns; 20 by 24, whose width is a multiple of the tiles
# already, OpenCV pads by 4 rows and a whole tile's 8 columns, as it pads both sides once one is
# no multiple.
OPENCV_CLAHE = {
    (32, 32): (
        "j4BgKKeMMM+oKHBQKFiv00DjIGSoz1AoqK/PUECbII9wv8/jYCiv21iUn884eM97r7dgj9dsMIeoRGBsOIggYBDfIJPXKM9g"
        "SL+Pp3jLcI/P14A016Nw47/LryT31yDfPKfnPbFYNMXRVNdekuEo6mDo88tClLu+oeo89M+jIGSX1yhKx5WgPmS5mL102edw"
        "7+uodp/FQNFEredAUIsg3yBkVKLZpeNJWnBMtq1qfK2Jf0DJw2g88umzhFDTYSDvUJ9w08dQr6eIjI+3QOuAk8dUr4ewu4Dj"
        "57vPz5irIO+vm69fRDivQ46/e8F6mIe5ZlBkedm7RFyfcVTB3Vcgr69IoM+vzaiMZImImnS2oDZAvXBMdFq37eO337/n2yC3"
        "s7+bPVqpgJJ4SZhMmpJwQZpPXJqd4ufGp0azr36QIO+AYHA4qL+/QK+r7+vH24/zOKPPh4Boj0R4o98817cggCC/2zqCa5uj"
        "vdWrspXes/uIYee3uahYX9XYo9/nXiCDiHinpaDLeF7Ls3jbs62Ai2y1SKpATM+MVKNw4c/TIM84fGx0qWrjjrl228WB8Lf8"
        "QLtUe27VfLOtsOPT3YEgn59gv0yXRCA0sJSf23B8n+N4TFCXWKvvw2i3YIdQjCDvk7NIv8+Cq7ecyZ/yVOGnw2Sms9OH1uN6"
        "v47ncFjZIJeXz6dAiKXnfsulz8nD7b+7cCRgQr+zx2DLtdd2w5IgaChYfKFAtlSg0fZQUsuqaI1sssvm6adwS1xxp1SpziBs"
        "MIDPUJBE34fniHC393DP80A4QIvXjHDLz9fvp6/TIO+HWMuSWtzjYaXm+4L9blDPPmzH4lDhi99IY8t+YGUgy2CA33JszVC7"
        "+8Hnv/Pz371MgLeJj8mIbuPRt3KYpyDXRMt4nXiTQGpwPm9Bel9cg2A7o6qx2FTNZueEVOnRIICvYJ/XULOv18d4UFxgo1Cz"
        "OMffYJjXcOe3RO+Tt7Mgjxx0aNWNSHfQk8RsWZBBVIVI0+vOwZWzwNvfv2pa5SCrYDCQfkCdSLHLq7/Dp0JYUHzBWJVcrd/H"
        "r1y3Wmh4IP/Xy7t5n9WjTKVgRF1Uo8ekl1uE5IDDx9fR0Zfcqa0gx0Cf33fnp9/rt7Ofz9eA78OA71C/aOdws1Bs72zviCCP"
        "MPN/UcXQSOehRUxtn9+TYaXJm7qSuZvkZsfP9ninIMtAx4CGy9O/0VDXWJq/bte143rno7/dWLHPr8/f770gpxwcHBwcHBwc"
        "HBwcHBwcHBwcHBwcHBwcHBwcHB0eHyAgUN9g07hwz2Cfy8/niGSP02jfv+/PlK/L58+A63ifIL9wn89351Tvh+encOd4dIDr"
        "qLdwe/ejYNfnw3DbgMsg/w=="
    ),
    (20, 20): (
        "HDl2Y0xHjpfVqrOzVSXVRnbVHJxxxtC4y45jf/qAY2PUXl6cR1ocy0uS3IbV4GGdrknvutuN49Ch7R+p1ICOqtyQnHu7auVY"
        "R8RLzrPEJKGh0Ot419eOqdvz6I7c1/Lz1/Ioz2icxrhb4KOsKG1uitdvQExTsSqgVf/gY2rS8ajL+KG/nKPqctmoKsEler3B"
        "deeJhbzzeKw9uJfcqcYq1JdMZtCPxvbPc8QouYnB8exv6Sivjri/v3ms6ufz6jJ2qtz41FdoJJX/6LnJPsPnsXjzfq87R32X"
        "pPIf6DRMoo6s4pX3iLEYO3FUkpXVqBzLVcbVqrjqsfP//0UxMpzbRs7ZHNx2XqC9pa6qI16He9Ro5a9a7LYcpL313b182XZF"
        "rHSotXuX729Z4SHo8dRlY1xaaraOuOO9nNnj1Xj4K8iz6IOluMPqf+aZ+oWOv/PQ1+Y02DQ0NDQ0NDQ0NDQ0NDQ0NDQ0NTc4"
        "gNTEuMmho+Wo42PgnInq/5mxMrp645DZ57J/jdvcmXbO16bztLct2g=="
    ),
    (20, 24): (
        "qlUVJWqVKko1Rb9QYJpAumB/v5VV3yqFQGqV1Z+latqK6pW0aqpq5LXPQNDUfyqqyrR16ViO0JehVcqrz7BOvjqfTu/teyqY"
        "yjVVtGCVgJBleKB1WvrA1Tq3gIKKeirfdeaKzbak6ruH1JzSnaJgQ2fi6obaaSqK6kqHfHOv45GnkbF0r7O/dtPO8XHvnSrD"
        "wIBq2srP9L/En5Tnmq1g5N+C6t9gtSqF28o4yH+ip7i4uJXyJ5S4T8ifuJL94iqWX5jxZ5dTtO3WavGyYUbVbkHq9LWK4yqr"
        "dd+qkpCKqufEcIDvcLfqoso66krkZSqaeLHbUExS/5aAeO3XI51L8bF9xpzk/yrbv1xcap97ws2liPzBR0fme+w29FzsiCqQ"
        "n6rKxECY1PTvyrT/SoWqr5CfoJpw3yr3TjWxVjyHkqNBZZFDWYNY32x429TG5CrkVeOSs5ZFrsNPf0COtLZmsqXGn+eleSr5"
        "qmq/Yt9ayp1wr2C6xGC05Y+i1Oyw5yqlUoDYkF55joq84byDtIHYda+G2Jqj0irtJiYmJiYmJiYmJiYmJiYmJiYmJicoKSoq"
        "n3Wq2t+Fv4K60mrSetqglbTPivTvpSq0tWfG3WfcioqV6qO8zN+t4K/gyqzY/yqd"
    ),
}


def reference_pool(plane, kind, kernel):
    """One plane, a list of rows, pooled cell by cell in plain python: kernel by kernel cells from
    the top left, the last row and column repeated to fill the last cells, and each cell's mean,
    maximum, minimum or median (statistics.median, the mean of the middle two of an even count)
    given to its pixels."""
    height, width = len(plane), len(plane[0])
    reduce = (statistics.fmean, max, min, statistics.median)[kind]
    out = [[0.0] * width for _ in range(height)]
    for top in range(0, height, kernel):
        for left in range(0, width, kernel):
            value = reduce([plane[min(y, height - 1)][min(x, width - 1)] for y in range(top, top + kernel) for x in range(left, left + kernel)])
            for y in range(top, min(top + kernel, height)):
                for x in range(left, min(left + kernel, width)):
                    out[y][x] = value
    return out


def pooled_kernel(crop):
    """The widest kernel, 4, 3 or 2 pixels, over whose cells from the top left a pooled crop is
    constant, or 0 where there is none."""
    import torch
    from torch.nn import functional as F

    for kernel in (4, 3, 2):
        highest = F.max_pool2d(crop[None], kernel, ceil_mode=True)
        lowest = -F.max_pool2d(-crop[None], kernel, ceil_mode=True)
        if torch.equal(highest, lowest):
            return kernel
    return 0


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
        self.assertEqual(set(self.blocks.FEATURES), set(blocks.ARCHITECTURE))
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

    def test_the_prior_head_reads_every_architectures_feature_map_and_leaves_the_model_alone(self):
        import torch
        from schwingnet import blocks

        maps = torch.full((6, 32, 32), self.blocks.IGNORED, dtype=torch.long)
        maps[1:, 8:20, 8:20] = 5
        for name in blocks.ARCHITECTURE:
            with self.subTest(architecture=name):
                model = self.train.build_model(None, "cpu", architecture=name)
                keys = list(model.state_dict())
                wide = self.blocks.PriorHead(model, name, 64, 28)
                wide.handle.remove()
                self.assertGreaterEqual(min(wide.cells), self.blocks.CELLS, "eight cells across a 64-pixel crop")
                self.assertIn(wide.stage, self.blocks.FEATURES[name][1:], "not the last map, which is 2 by 2 at 64")
                head = self.blocks.PriorHead(model, name, 32, 28)
                self.assertTrue(model.training, "the dry forward leaves the model as it found it")
                self.assertEqual(head.cells, (8, 8))
                self.assertIn(head.stage, self.blocks.FEATURES[name])
                model(self.batch())
                self.assertEqual(head.conv.in_channels, head.features.shape[1])
                self.assertEqual(tuple(head.features.shape[2:]), (8, 8))
                self.assertEqual(tuple(head.logits().shape), (6, 28, 32, 32))
                nothing = head.loss(torch.full_like(maps, self.blocks.IGNORED))
                self.assertEqual(float(nothing), 0.0)
                self.assertIsNone(head.mean_and_reset())
                loss = head.loss(maps)
                self.assertTrue(bool(torch.isfinite(loss)) and float(loss) > 0.0)
                loss.backward()
                self.assertIsNotNone(head.conv.weight.grad)
                self.assertAlmostEqual(head.mean_and_reset(), float(loss))
                self.assertEqual(list(model.state_dict()), keys, "the head is not in the model")
                chosen = blocks.parse([f"architecture={name}", "backbone_lr_scale=0.5"])
                groups = self.blocks.OPTIMISERS["adam"](model, 1e-3, chosen, head.parameters()).param_groups
                self.assertEqual(len(groups), 2)
                self.assertTrue(any(p is head.conv.weight for p in groups[1]["params"]))
                self.assertFalse(any(p is head.conv.weight for p in groups[0]["params"]))

    def test_the_prior_head_refuses_a_crop_too_small_for_its_cells_and_learns_where_a_body_is(self):
        import torch

        model = self.train.build_model(None, "cpu", architecture="resnet18")
        with self.assertRaises(self.blocks.ArchitectureError) as refused:
            self.blocks.PriorHead(model, "resnet18", 16, 28)
        self.assertIn("no stage of resnet18 keeps 8 cells across the crop", str(refused.exception))
        self.assertIn("layer1, gives 4 by 4", str(refused.exception))
        self.assertFalse(any(m._forward_hooks for m in model.modules()), "the dry forward's hooks are gone")
        dense = self.train.build_model(None, "cpu", architecture="densenet121")
        with self.assertRaises(self.blocks.ArchitectureError) as failed:
            self.blocks.PriorHead(dense, "densenet121", 16, 28)
        self.assertIn("densenet121 cannot forward a 16-pixel crop", str(failed.exception))
        self.assertFalse(any(m._forward_hooks for m in dense.modules()), "the hooks go even when the forward fails")
        self.assertTrue(dense.training, "and the model is as it was")
        # One batch of a bright body on a dark field, overfitted: the head names the body's pixels
        # and the field's apart, which a head collapsed to background never does.
        torch.manual_seed(0)
        maps = torch.zeros(6, 32, 32, dtype=torch.long)
        maps[:, 8:20, 8:20] = 5
        batch = (maps > 0).float().unsqueeze(1).repeat(1, 3, 1, 1)
        head = self.blocks.PriorHead(model, "resnet18", 32, 28)
        self.assertEqual((head.stage, head.cells), ("layer1", (8, 8)))
        optimiser = torch.optim.Adam(list(model.parameters()) + list(head.parameters()), lr=1e-2)
        model.train()
        for _ in range(60):
            optimiser.zero_grad()
            model(batch)
            head.loss(maps).backward()
            optimiser.step()
        model.eval()
        with torch.no_grad():
            model(batch)
            guess = head.logits().argmax(dim=1)
        body = maps > 0
        self.assertGreater(float((guess[body] == 5).float().mean()), 0.9, "the body's pixels are named")
        self.assertGreater(float((guess[~body] == 0).float().mean()), 0.9, "and the field's")

    def test_the_jitter_moves_a_map_with_its_crop_and_draws_as_without_one(self):
        import torch

        maps = torch.zeros(6, 32, 32, dtype=torch.long)
        maps[1:, 8:20, 10:22] = 5
        maps[0] = self.blocks.IGNORED
        batch = (maps == 5).float().unsqueeze(1).repeat(1, 3, 1, 1)
        names = ("box-jitter", "intensity")
        moved, moved_maps = self.blocks.augment_with_maps(batch, maps, names, torch.Generator().manual_seed(4))
        alone = self.blocks.augment(batch, names, torch.Generator().manual_seed(4))
        self.assertTrue(torch.equal(moved, alone), "the crops come out as without maps")
        self.assertEqual(moved_maps.dtype, torch.long)
        self.assertTrue(torch.equal(moved_maps[0], torch.full((32, 32), self.blocks.IGNORED)))
        self.assertEqual(set(moved_maps[1:].unique().tolist()), {0, 5})
        self.assertFalse(torch.equal(moved_maps[1:], maps[1:]))
        # The image is its own map's body, so where the moved map says body the moved crop is the
        # bright level and not elsewhere, up to the edge pixels the two samplings round apart.
        body = moved_maps[1:] == 5
        bright = moved[1:, 0] > moved[1:, 0].mean(dim=(1, 2), keepdim=True)
        self.assertGreater(float((body == bright).float().mean()), 0.9)
        same, same_maps = self.blocks.augment_with_maps(batch, maps, ("intensity",), torch.Generator().manual_seed(4))
        self.assertTrue(torch.equal(same_maps, maps), "a change of intensity alone leaves the maps")

    def grey(self, count, size, seed=0):
        import torch

        crops = torch.rand(count, 1, size, size, generator=torch.Generator().manual_seed(seed))
        return crops.repeat(1, 3, 1, 1)

    def test_each_strong_transform_keeps_a_grey_crop_grey_in_range_and_seeded(self):
        import torch

        self.assertEqual(self.blocks.STRONG_ORDER, tuple(self.blocks.STRONG))
        self.assertEqual(len(self.blocks.STRONG), 16)
        self.assertLessEqual(set(self.blocks.STRONG_WARPS), set(self.blocks.STRONG))
        # 37 pixels is no multiple of CLAHE's eight tiles, nor of any pooling kernel from 2 to 4.
        for size in (32, 37, 64):
            crops = self.grey(6, size)
            for name, change in self.blocks.STRONG.items():
                with self.subTest(name=name, size=size):
                    first = change(crops, torch.Generator().manual_seed(4))
                    again = change(crops, torch.Generator().manual_seed(4))
                    self.assertEqual(tuple(first.shape), (6, 3, size, size))
                    self.assertTrue(torch.equal(first, again), "the same seed draws the same change")
                    self.assertTrue(torch.equal(first[:, 0], first[:, 1]) and torch.equal(first[:, 0], first[:, 2]))
                    self.assertGreaterEqual(float(first.min()), 0.0)
                    self.assertLessEqual(float(first.max()), 1.0)
                    self.assertFalse(torch.equal(first, crops), "it changes the crops")
                    self.assertTrue(torch.equal(crops, self.grey(6, size)), "and leaves its input as it was")

    def test_the_strong_transforms_do_what_their_names_say(self):
        import torch

        def seeded():
            return torch.Generator().manual_seed(4)

        crops = self.grey(6, 32)
        self.assertTrue(torch.allclose(self.blocks.invert(crops, seeded()), 1.0 - crops))
        for name in ("dropout", "impulse-noise"):
            out = self.blocks.STRONG[name](crops, seeded())
            changed = out != crops
            self.assertTrue(bool(changed.any()), name)
            self.assertTrue(set(out[changed].unique().tolist()) <= {0.0, 1.0}, f"{name} sets pixels to black or white")
        hit = float((self.blocks.impulse_noise(crops, seeded()) != crops).float().mean())
        self.assertAlmostEqual(hit, self.blocks.IMPULSE_SHARE, delta=0.02)
        for name in ("gaussian-blur", "average-blur"):
            self.assertLess(float(self.blocks.STRONG[name](crops, seeded()).var()), float(crops.var()), f"{name} smooths")
        stretched = self.blocks.gaussian_contrast(crops, seeded())
        self.assertTrue(torch.allclose(stretched.amin(dim=(1, 2, 3)), torch.zeros(6), atol=1e-6))
        self.assertTrue(torch.allclose(stretched.amax(dim=(1, 2, 3)), torch.ones(6), atol=1e-6))
        flat = torch.full((6, 3, 32, 32), 0.4)
        self.assertTrue(bool((self.blocks.emboss(flat, seeded()) >= flat).all()), "the emboss is added, not blended")
        for name in self.blocks.STRONG_WARPS:
            self.assertTrue(torch.allclose(self.blocks.STRONG[name](flat, seeded()), flat, atol=1e-6), f"{name} moves, not shades")

    def test_pooling_draws_a_kernel_of_two_to_four_pixels_per_crop_as_synthex_says(self):
        import torch

        # SyntheX's Methods: "All of the pooling kernel sizes were between 2 x 2 and 4 x 4."
        for size in (32, 37):
            pooled = self.blocks.pooling(self.grey(24, size, seed=size), torch.Generator().manual_seed(4))
            kernels = [pooled_kernel(crop) for crop in pooled]
            self.assertEqual(set(kernels), {2, 3, 4}, f"each crop pooled over one kernel of 2 to 4 at {size} pixels: {kernels}")
        plane = self.grey(1, 7, seed=7).double()
        for kind in range(4):
            for kernel in (2, 3, 4):
                with self.subTest(kind=kind, kernel=kernel):
                    expected = torch.tensor(reference_pool(plane[0, 0].tolist(), kind, kernel), dtype=torch.float64)
                    got = self.blocks._pool(plane, kind, kernel)
                    self.assertEqual(tuple(got.shape), (1, 3, 7, 7))
                    self.assertTrue(torch.allclose(got[0, 0], expected, rtol=0, atol=1e-12))

    def test_multiply_takes_the_crop_or_each_pixel_by_half_to_one_and_a_half_as_synthex_does(self):
        import torch

        # SyntheX's Methods: "either changed brightness or multiplied x element wise with 50-150% of
        # the original value", which its code writes as imgaug's Multiply((0.5, 1.5)), "Change
        # brightness of images (50-150% of original value)", or MultiplyElementwise((0.5, 1.5)).
        ramp = torch.linspace(0.1, 0.6, 32 * 32).view(1, 1, 32, 32).repeat(12, 3, 1, 1)
        factor = self.blocks.multiply(ramp, torch.Generator().manual_seed(4)) / ramp
        self.assertTrue(bool(((factor >= 0.5 - 1e-6) & (factor <= 1.5 + 1e-6)).all()), "every pixel 50 to 150 percent of itself")
        spread = factor.amax(dim=(1, 2, 3)) - factor.amin(dim=(1, 2, 3))
        whole = spread < 1e-5
        self.assertTrue(bool(whole.any()), "some crops take one factor, a change of brightness")
        self.assertTrue(bool((~whole).any()), "and some a factor per pixel, element wise")
        self.assertTrue(bool((spread[~whole] > 0.9).all()), "each pixel's factor drawn on its own over the range")

    def test_clahe_is_opencvs_to_within_the_byte_opencv_rounds_to(self):
        import torch

        for (height, width), encoded in OPENCV_CLAHE.items():
            with self.subTest(height=height, width=width):
                plane = torch.tensor(structured_plane(height, width, 100 * height + width), dtype=torch.float64) / 255
                out = self.blocks.clahe(plane.view(1, 1, height, width).repeat(2, 3, 1, 1), torch.Generator().manual_seed(4))
                opencv = torch.tensor(list(base64.b64decode(encoded)), dtype=torch.float64).view(height, width)
                gap = (out * 255 - opencv).abs()
                # OpenCV rounds each tile's equaliser and then its result to a byte, where the block
                # keeps both as fractions, so the two differ by a grey level at most.
                self.assertLessEqual(float(gap.max()), 1.0 + 1e-3)
                self.assertLess(float(gap.mean()), 0.5)

    def test_clahe_clips_and_spreads_each_tiles_histogram_as_opencv_does_and_blends_between_tiles(self):
        import torch

        # A tile's clip limit is one count at 32 and 37 pixels, and two or three at 128.
        for size in (32, 37, 128):
            crops = (self.grey(3, size, seed=size) ** 2).double()
            clips = self.blocks._uniform(torch.Generator().manual_seed(4), 3, *self.blocks.CLAHE_CLIP).tolist()
            out = self.blocks.clahe(crops, torch.Generator().manual_seed(4))
            for n in range(3):
                with self.subTest(size=size, crop=n):
                    expected = torch.tensor(reference_clahe(crops[n, 0].tolist(), clips[n]), dtype=torch.float64)
                    self.assertTrue(torch.allclose(out[n, 0], expected, rtol=0, atol=1e-12))
        flat = torch.full((2, 3, 32, 32), 0.3)
        out = self.blocks.clahe(flat, torch.Generator().manual_seed(4))
        self.assertTrue(torch.allclose(out, out[:, :, :1, :1].expand_as(out), rtol=0, atol=1e-6), "a flat crop stays flat")

    def test_strong_takes_none_one_or_two_different_transforms_per_crop_uniformly(self):
        from collections import Counter

        import torch

        picks = self.blocks.strong_picks(3000, torch.Generator().manual_seed(1))
        self.assertEqual(picks, self.blocks.strong_picks(3000, torch.Generator().manual_seed(1)))
        how_many = Counter(len(pick) for pick in picks)
        self.assertEqual(set(how_many), {0, 1, 2})
        self.assertTrue(all(900 < n < 1100 for n in how_many.values()), how_many)
        self.assertTrue(all(len(set(pick)) == len(pick) for pick in picks), "without replacement")
        taken = Counter(name for pick in picks for name in pick)
        self.assertEqual(set(taken), set(self.blocks.STRONG))
        # 3000 crops take 3000 transforms in all, about 187 of each of the sixteen.
        self.assertTrue(all(130 < n < 250 for n in taken.values()), taken)

    def test_the_strong_warps_move_a_map_with_its_crop_and_the_rest_leave_it(self):
        import torch

        maps = torch.zeros(6, 32, 32, dtype=torch.long)
        maps[1:, 8:20, 10:22] = 5
        maps[0] = self.blocks.IGNORED
        batch = (maps == 5).float().unsqueeze(1).repeat(1, 3, 1, 1)
        for name, with_maps in self.blocks.STRONG_WARPS.items():
            with self.subTest(name=name):
                moved, moved_maps = with_maps(batch, maps, torch.Generator().manual_seed(4))
                alone = self.blocks.STRONG[name](batch, torch.Generator().manual_seed(4))
                self.assertTrue(torch.equal(moved, alone), "the crops come out as without maps")
                self.assertEqual(moved_maps.dtype, torch.long)
                self.assertTrue(torch.equal(moved_maps[0], torch.full((32, 32), self.blocks.IGNORED)))
                self.assertEqual(set(moved_maps[1:].unique().tolist()), {0, 5})
                self.assertFalse(torch.equal(moved_maps[1:], maps[1:]))
                body = moved_maps[1:] == 5
                bright = moved[1:, 0] > moved[1:, 0].mean(dim=(1, 2), keepdim=True)
                self.assertGreater(float((body == bright).float().mean()), 0.9)
        # The block as a whole: the crops come out as without maps, and only the crops whose picks
        # hold a warp have their maps moved.
        many = torch.zeros(40, 32, 32, dtype=torch.long)
        many[:, 8:20, 10:22] = 5
        crops = (many == 5).float().unsqueeze(1).repeat(1, 3, 1, 1)
        picks = self.blocks.strong_picks(40, torch.Generator().manual_seed(6))
        out, out_maps = self.blocks.augment_with_maps(crops, many, ("strong",), torch.Generator().manual_seed(6))
        self.assertTrue(torch.equal(out, self.blocks.augment(crops, ("strong",), torch.Generator().manual_seed(6))))
        warped = [n for n, pick in enumerate(picks) if set(pick) & set(self.blocks.STRONG_WARPS)]
        self.assertTrue(0 < len(warped) < 40, picks)
        self.assertTrue(all(torch.equal(out_maps[n], many[n]) for n in range(40) if n not in warped))
        self.assertTrue(any(not torch.equal(out_maps[n], many[n]) for n in warped))

    def test_strong_comes_last_so_the_other_changes_draw_as_before(self):
        import torch

        others = ("box-jitter", "intensity", "blur", "noise")
        generator = torch.Generator().manual_seed(4)
        expected = self.blocks.strong(self.blocks.augment(self.batch(), others, generator), generator)
        got = self.blocks.augment(self.batch(), ("strong", *others), torch.Generator().manual_seed(4))
        self.assertTrue(torch.equal(got, expected))
        self.assertEqual(self.blocks.AUGMENT_ORDER[-1], "strong")

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
        record = {"run_id": "blocksrun000", "code_commit": "0" * 40, "catalog_sha256": sha256_of(cls.catalog), "catalog_version": 1, "clean_tree": True}
        (cls.run_dir / "RUN.json").write_text(json.dumps(record), encoding="utf-8")
        words = ["normalise=imagenet", "augment=box-jitter,intensity,blur,noise", "optimiser=adamw", "weight_decay=0.01",
                 "schedule=cosine", "warmup_epochs=1", "backbone_lr_scale=0.5", "sampler=balanced",
                 "loss_weights=inverse-frequency", "select=balanced-accuracy", "prior=level-map", "prior_weight=0.5"]
        args = ["--catalog", str(cls.catalog), "--out", str(cls.run_dir), "--epochs", "3", "--seed", "1", "--size", "32",
                "--device", "cpu", "--witness", "2", "--keep-epochs", "0"]
        for word in words:
            args += ["--block", word]
        with mock.patch.dict(os.environ, {"SCHWINGNET_WANDB": "off"}):
            cls.rc = load("train").main(args)

    @classmethod
    def make_catalog(cls, tmp, map_share=None):
        share = [] if map_share is None else ["--map-share", str(map_share)]
        python(ROOT / "tools" / "synthetic_bank.py", tmp / "bank-train", "--frames", "60", "--cases", "8", "--seed", "3", *share)
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

    def test_the_prior_block_learns_the_map_and_stays_out_of_the_checkpoint(self):
        import torch

        self.assertEqual(self.rc, 0)
        facts = json.loads((self.run_dir / "train" / "checkpoint.json").read_text(encoding="utf-8"))
        self.assertEqual((facts["blocks"]["prior"], facts["blocks"]["prior_weight"]), ("level-map", 0.5))
        self.assertGreater(facts["counts"]["train_with_map"], 0)
        self.assertLess(facts["counts"]["train_with_map"], facts["counts"]["train"], "crops without a map train beside them")
        lines = [json.loads(line) for line in (self.run_dir / "train" / "metrics.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertIsNone(lines[0]["train_prior_loss"])
        self.assertTrue(all(line["train_prior_loss"] > 0 for line in lines[1:]))
        self.assertTrue(all(0.0 <= line["validation_map_pixel_accuracy"] <= 1.0 for line in lines))
        self.assertTrue(all(0.0 <= line["validation_map_body_accuracy"] <= 1.0 for line in lines))
        self.assertEqual((facts["prior_stage"], facts["prior_cells"]), ("layer1", [8, 8]), "eight cells of a 32-pixel crop")
        head = self.run_dir / "train" / "prior_head.pt"
        self.assertEqual(hashlib.sha256(head.read_bytes()).hexdigest(), facts["prior_head_sha256"])
        self.assertEqual(set(torch.load(head, weights_only=True)), {"conv.weight", "conv.bias"})
        best = torch.load(self.run_dir / "train" / "best.pt", weights_only=True)
        self.assertFalse(any(k.startswith("conv.") for k in best))
        card = (self.run_dir / "train" / "MODEL.md").read_text(encoding="utf-8")
        self.assertIn("- Prior: level-map head on layer1 (8 by 8 cells of the 32-pixel crop, 28 classes at every pixel, weight 0.5)", card)
        self.assertIn("prior level-map; prior_weight 0.5", card)

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
        record = {"run_id": "capped000000", "code_commit": "0" * 40, "catalog_sha256": sha256_of(cls.catalog), "catalog_version": 1, "clean_tree": True}
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

    def test_a_prior_on_a_catalog_whose_train_part_has_no_map_is_refused_in_words(self):
        tmp = Path(tempfile.mkdtemp())
        catalog = RunWithEveryBlockTest.make_catalog(tmp, map_share=0)
        run_dir = tmp / "run"
        run_dir.mkdir()
        record = {"run_id": "nomaps000000", "code_commit": "0" * 40, "catalog_sha256": sha256_of(catalog), "catalog_version": 1, "clean_tree": True}
        (run_dir / "RUN.json").write_text(json.dumps(record), encoding="utf-8")
        args = ["--catalog", str(catalog), "--out", str(run_dir), "--epochs", "1", "--seed", "1", "--size", "32", "--device", "cpu"]
        err = io.StringIO()
        with contextlib.redirect_stderr(err), mock.patch.dict(os.environ, {"SCHWINGNET_WANDB": "off"}):
            self.assertEqual(load("train").main(args + ["--block", "prior=level-map", "--block", "prior_weight=1"]), 1)
            self.assertEqual(load("train").main(args + ["--block", "prior=level-map"]), 1)
        self.assertIn("no training crop comes from a frame with a level map", err.getvalue())
        self.assertIn("prior_weight above 0 goes with prior=level-map", err.getvalue())
        self.assertFalse((run_dir / "train" / "best.pt").exists())
        crops = load("train").read_crops(catalog, ("train", "validation"))
        self.assertTrue(crops and all(crop["map"] is None for crop in crops))

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
        record = {"run_id": "monai0000000", "code_commit": "0" * 40, "catalog_sha256": sha256_of(cls.catalog), "catalog_version": 1, "clean_tree": True}
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


@unittest.skipIf(MISSING, f"needs the train environment ({', '.join(MISSING)} missing)")
class RunWithTheStrongBlockTest(unittest.TestCase):
    """One epoch with the strong block, SyntheX's and FluoroSAM's randomisation, at the two crop
    sizes the plans start from: at 32 pixels with the prior block on, so its two warps move the
    level maps the head is scored against inside the trainer, and at 64 pixels with it alone."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.catalog = RunWithEveryBlockTest.make_catalog(cls.tmp)

    def run_with(self, name, size, words):
        run_dir = self.tmp / name
        run_dir.mkdir()
        record = {"run_id": f"{name}-000", "code_commit": "0" * 40, "catalog_sha256": sha256_of(self.catalog), "catalog_version": 1, "clean_tree": True}
        (run_dir / "RUN.json").write_text(json.dumps(record), encoding="utf-8")
        args = ["--catalog", str(self.catalog), "--out", str(run_dir), "--epochs", "1", "--seed", "1", "--size", str(size),
                "--device", "cpu", "--witness", "2", "--keep-epochs", "0"]
        for word in words:
            args += ["--block", word]
        with mock.patch.dict(os.environ, {"SCHWINGNET_WANDB": "off"}):
            self.assertEqual(load("train").main(args), 0)
        facts = json.loads((run_dir / "train" / "checkpoint.json").read_text(encoding="utf-8"))
        lines = [json.loads(line) for line in (run_dir / "train" / "metrics.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(facts["blocks"]["augment"], ["strong"])
        self.assertEqual(facts["size"], size)
        self.assertEqual([line["epoch"] for line in lines], [0, 1])
        self.assertTrue(lines[1]["train_loss"] > 0 and lines[1]["train_loss"] < float("inf"))
        self.assertIn("augment strong", (run_dir / "train" / "MODEL.md").read_text(encoding="utf-8"))
        return lines

    def test_one_epoch_at_32_pixels_with_the_prior_trains(self):
        lines = self.run_with("strong-32", 32, ["augment=strong", "prior=level-map", "prior_weight=0.5"])
        self.assertGreater(lines[1]["train_prior_loss"], 0)

    def test_one_epoch_at_64_pixels_trains(self):
        self.run_with("strong-64", 64, ["augment=strong"])


@unittest.skipIf([n for n in FLOW_NEEDS if importlib.util.find_spec(n) is None], "needs the package's checkers")
class FlowBlocksTest(unittest.TestCase):
    """tools/flow.py passes the blocks to the trainer and refuses a wrong one before any step."""

    def test_blocks_pass_through_and_a_fault_stops_the_plan(self):
        flow = load("flow")
        self.assertEqual(flow.block_words([]), "")
        # augment's changes are passed in schwingnet.blocks' order, whatever order they were typed.
        self.assertEqual(flow.block_words(["normalise=imagenet", "augment=noise,blur"]),
                         " --block normalise=imagenet --block augment=blur,noise")
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
