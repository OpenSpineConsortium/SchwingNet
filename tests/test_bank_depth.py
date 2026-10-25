"""Frames of more than 8 bits in tools/bank.py (#260): a 16-bit PNG and a 16-bit TIFF are windowed
to 8-bit grey as a DICOM film is, never clipped white by the trainer's conversion, while an 8-bit
PNG is still copied byte for byte. These run where numpy and Pillow are installed (the train
environment)."""

import importlib.util
import io
import json
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

try:
    import numpy
    from PIL import Image
except ImportError:
    numpy = None

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(f"{name}_tool", ROOT / "tools" / f"{name}.py")
    tool = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = tool
    spec.loader.exec_module(tool)
    return tool


def chunk(kind, data):
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def png(width, height, depth, colour, sample):
    """A PNG whose sample at (x, y) is sample(x, y), repeated on each channel the colour type has."""
    channels = {0: 1, 2: 3, 4: 2}[colour]
    pack = ">H" if depth == 16 else ">B"
    rows = b"".join(b"\x00" + b"".join(struct.pack(pack, sample(x, y)) * channels for x in range(width))
                    for y in range(height))
    header = struct.pack(">IIBBBBB", width, height, depth, colour, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


def gradient(x, y):
    """A 16-bit film's range: most of it above 255, where Pillow's conversion clips."""
    return 1000 + (x * 997 + y * 131) % 60000


def trainer_view(data):
    """The frame as tools/train.py reads it: Pillow's conversion to 8-bit grey."""
    return numpy.asarray(Image.open(io.BytesIO(data)).convert("L"))


@unittest.skipIf(numpy is None, "numpy and Pillow are in the train environment")
class FramesOfMoreThanEightBits(unittest.TestCase):
    def setUp(self):
        self.bank = load("bank")
        self.ingest_png_size = load("ingest").png_size

    def test_a_16_bit_png_is_windowed_and_no_longer_trains_white(self):
        data = png(64, 48, 16, 0, gradient)
        self.assertEqual(trainer_view(data).min(), 255)  # the fault #260 found: a white frame
        out, width, height = self.bank.as_png(data, "png")
        self.assertEqual((width, height), (64, 48))
        image = Image.open(io.BytesIO(out))
        self.assertEqual(image.mode, "L")
        seen = trainer_view(out)
        self.assertEqual((int(seen.min()), int(seen.max())), (0, 255))
        self.assertGreater(len(numpy.unique(seen)), 200)
        self.assertEqual(out[24], 8)

    def test_the_window_is_the_dicom_paths(self):
        data = png(64, 48, 16, 0, gradient)
        out, _, _ = self.bank.as_png(data, "png")
        pixels = numpy.asarray(Image.open(io.BytesIO(data)), dtype=numpy.float64)
        expected = self.bank.window_8bit(numpy, pixels)
        self.assertTrue(numpy.array_equal(numpy.asarray(Image.open(io.BytesIO(out))), expected))

    def test_a_16_bit_tiff_is_windowed_too(self):
        values = numpy.array([[gradient(x, y) for x in range(40)] for y in range(30)], dtype=numpy.uint16)
        tiff = io.BytesIO()
        Image.fromarray(values).save(tiff, format="TIFF")
        self.assertEqual(Image.open(io.BytesIO(tiff.getvalue())).mode, "I;16")
        out, _, _ = self.bank.as_png(tiff.getvalue(), "tif")
        seen = trainer_view(out)
        self.assertEqual(Image.open(io.BytesIO(out)).mode, "L")
        self.assertEqual((int(seen.min()), int(seen.max())), (0, 255))

    def test_an_8_bit_png_is_copied_byte_for_byte(self):
        for colour in (0, 2):
            data = png(20, 10, 8, colour, lambda x, y: (x * 9 + y) % 256)
            self.assertEqual(self.bank.as_png(data, "png")[0], data)

    def test_sixteen_bits_of_colour_become_8_bit_grey(self):
        data = png(20, 10, 16, 2, gradient)
        out, _, _ = self.bank.as_png(data, "png")
        self.assertEqual(Image.open(io.BytesIO(out)).mode, "L")
        self.assertTrue(numpy.array_equal(trainer_view(out), trainer_view(data)))

    def test_a_flat_16_bit_frame_is_refused(self):
        with self.assertRaisesRegex(self.bank.BankError, "the frame is flat"):
            self.bank.as_png(png(20, 10, 16, 0, lambda x, y: 4000), "png")

    def test_a_banked_16_bit_frame_is_one_the_ingest_takes(self):
        with tempfile.TemporaryDirectory() as folder:
            raw = Path(folder) / "raw" / "images_001" / "images"
            raw.mkdir(parents=True)
            for index, name in enumerate(["00000001_000", "00000002_000"]):
                (raw / f"{name}.png").write_bytes(png(40, 30, 16, 0, lambda x, y, i=index: gradient(x + i, y)))
            recipe = json.loads((ROOT / "grid" / "banks" / "nih_chestxray14.json").read_text(encoding="utf-8"))
            recipe["raw"], recipe["bank"] = str(Path(folder) / "raw"), str(Path(folder) / "bank")
            counts = self.bank.convert(recipe, recipe["raw"], recipe["bank"], True)
            self.assertEqual(counts["written"], 2)
            for frame in sorted((Path(folder) / "bank" / "images").rglob("*.png")):
                data = frame.read_bytes()
                self.assertEqual(self.ingest_png_size(data), (40, 30))
                self.assertEqual((data[24], data[25]), (8, 0))


if __name__ == "__main__":
    unittest.main()
