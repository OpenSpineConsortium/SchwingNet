"""tools/latency.py and tools/sweep.py end to end on a tiny synthetic catalog and an untrained level
stage (issue #13): the ONNX export passes parity, ONNX Runtime is refused before parity and after the
file changes, both runtimes are timed and the headline names the faster, the frame path's crop is the
trainer's crop to the pixel, and a sweep writes its overlay, its log, its summary and its video.

It needs torch, onnx, onnxruntime, Pillow and the package's checkers, so it runs in the train-cpu
environment (`pixi run -e train-cpu python -m unittest tests.test_latency_tools`) and skips under the
required check's plain python3, which has none of them."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEEDED = ("torch", "onnx", "onnxruntime", "PIL", "beartype", "pydantic")
MISSING = [name for name in NEEDED if importlib.util.find_spec(name) is None]


def load(name):
    spec = importlib.util.spec_from_file_location(f"{name}_under_test", ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def python(*args):
    done = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, timeout=600)
    if done.returncode != 0:
        raise AssertionError(f"{args}: {done.stdout}\n{done.stderr}")
    return done.stdout


@unittest.skipIf(MISSING, f"needs the train environment ({', '.join(MISSING)} missing)")
class LatencyToolsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.catalog = cls.make_catalog(cls.tmp)
        cls.run_dir = cls.make_run(cls.tmp / "run")
        cls.latency = load("latency")

    @classmethod
    def make_catalog(cls, tmp):
        python(ROOT / "tools" / "synthetic_bank.py", tmp / "bank-train", "--frames", "120", "--cases", "12", "--seed", "3")
        python(ROOT / "tools" / "synthetic_bank.py", tmp / "bank-test", "--frames", "20", "--cases", "2", "--seed", "4", "--test-cases", "case134,case39")
        cls.drop_duplicates(tmp)
        for kind in ("train", "test"):
            python(ROOT / "tools" / "ingest.py", "run", "--bank", tmp / f"bank-{kind}", "--source", "carmlspine", "--kind", kind,
                   "--date", "2026-10-21", "--code-commit", "0" * 40, "--grid-root", tmp / "carmlspine")
        manifests = []
        for manifest in sorted((tmp / "carmlspine").rglob("MANIFEST.json")):
            manifests += ["--manifest", manifest]
        built = json.loads(python(ROOT / "tools" / "catalog.py", "build", "--store", tmp / "store", *manifests, "--root", tmp))
        return tmp / "store" / "versions" / built["file"]

    @staticmethod
    def drop_duplicates(tmp):
        """The synthetic bank repeats a few frames under another person, which the ingest refuses."""
        import hashlib

        for bank in ("bank-train", "bank-test"):
            seen = set()
            for image in sorted((tmp / bank / "images").rglob("*.png")):
                digest = hashlib.sha256(image.read_bytes()).hexdigest()
                if digest in seen:
                    image.unlink()
                    (tmp / bank / "meta" / f"{image.stem}.json").unlink()
                seen.add(digest)

    @staticmethod
    def make_run(run):
        """A run directory as tools/flow.py and tools/train.py leave it, with untrained weights."""
        import torch

        train = load("train")
        from schwingnet.catalog import LEVELS

        (run / "train").mkdir(parents=True)
        (run / "RUN.json").write_text(json.dumps({"run_id": "testrun00000", "code_commit": "0" * 40}), encoding="utf-8")
        torch.manual_seed(1)
        torch.save(train.build_model(None, "cpu").state_dict(), run / "train" / "best.pt")
        (run / "train" / "checkpoint.json").write_text(json.dumps({"size": 32, "levels": list(LEVELS)}), encoding="utf-8")
        return run

    def test_1_onnx_runtime_is_refused_before_parity(self):
        with self.assertRaises(self.latency.LatencyError):
            self.latency.FramePath(self.run_dir, "onnxruntime", "cpu", 1)

    def test_2_the_export_passes_parity(self):
        exported = self.latency.export(self.run_dir)
        verdict = self.latency.parity(self.run_dir, self.catalog, "validation", 32, "onnxruntime", "cpu", 2)
        self.assertTrue(verdict["passed"], verdict)
        self.assertTrue((self.run_dir / "onnx" / "parity-onnxruntime-cpu.json").is_file())
        self.assertEqual(verdict["onnx_sha256"], exported["onnx_sha256"])
        self.assertTrue(verdict["labels_equal"])
        self.assertLess(verdict["max_abs_probability_difference"], 1e-5)

    def test_3_both_runtimes_are_timed_and_the_headline_is_the_faster(self):
        arms = [self.latency.measure(self.run_dir, self.catalog, runtime, "cpu", 2, 12, 2, "test") for runtime in ("torch", "onnxruntime")]
        headline = json.loads((self.run_dir / "evaluate" / "latency.json").read_text(encoding="utf-8"))
        for key in ("ms_per_frame_median", "ms_per_frame_p95", "frames", "device", "batch"):
            self.assertIn(key, headline)
        self.assertEqual(headline["batch"], 1)
        self.assertEqual(headline["frames"], 12)
        self.assertEqual(headline["ms_per_frame_p95"], min(a["ms_per_frame_p95"] for a in arms))
        self.assertEqual(sorted(headline["arms"]), ["onnxruntime-cpu-2t", "torch-cpu-2t"])

    def test_4_the_frame_path_crops_as_the_trainer_does(self):
        import numpy as np
        from PIL import Image

        train = load("train")
        frame, boxes = self.latency.frames_of(self.catalog, "test")[0]
        image = Image.open(frame).convert("L")
        for box in boxes:
            self.assertTrue(np.array_equal(self.latency.crop_from_image(image, box, 32), train.crop_pixels(frame, box, 32)))

    def test_5_a_sweep_records_its_overlay(self):
        sweep = load("sweep")
        folder = self.tmp / "sweep-case134"
        self.assertEqual(sweep.main(["synthetic", "--catalog", str(self.catalog), "--person", "carmlspine:case134", "--out", str(folder)]), 0)
        out = self.tmp / "recorded"
        self.assertEqual(sweep.main(["run", "--run", str(self.run_dir), "--frames", str(folder / "frames"), "--boxes", str(folder / "boxes.jsonl"),
                                     "--name", "case134", "--threads", "2", "--warmup", "2", "--out", str(out)]), 0)
        summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
        frames = len(list((folder / "frames").iterdir()))
        self.assertEqual(summary["frames"], frames)
        self.assertEqual(len(list((out / "overlay").glob("*.png"))), frames)
        self.assertEqual(len((out / "sweep.jsonl").read_text(encoding="utf-8").splitlines()), frames)
        self.assertIn("all frames", summary["accuracy"])
        self.assertIn("all frames, frame alone (no tracker)", summary["accuracy"])
        self.assertTrue(Path(summary["video"]).is_file())
        self.assertTrue((out / "contact.png").is_file())
        # a second run into the same folder with fewer frames leaves none of the first run's behind
        short = self.tmp / "sweep-short"
        (short / "frames").mkdir(parents=True)
        first_two = sorted((folder / "frames").iterdir())[:2]
        for path in first_two:
            (short / "frames" / path.name).write_bytes(path.read_bytes())
        (short / "boxes.jsonl").write_text("".join((folder / "boxes.jsonl").read_text(encoding="utf-8").splitlines(keepends=True)[:2]), encoding="utf-8")
        self.assertEqual(sweep.main(["run", "--run", str(self.run_dir), "--frames", str(short / "frames"), "--boxes", str(short / "boxes.jsonl"),
                                     "--name", "case134", "--threads", "1", "--warmup", "1", "--out", str(out)]), 0)
        self.assertEqual(len(list((out / "overlay").glob("*.png"))), 2)

    def test_6b_a_bank_becomes_a_sweep_with_its_boxes_in_pixels(self):
        sweep = load("sweep")
        folder = self.tmp / "from-bank"
        self.assertEqual(sweep.main(["from-bank", "--bank", str(self.tmp / "bank-test"), "--case", "case134", "--out", str(folder)]), 0)
        lines = [json.loads(l) for l in (folder / "boxes.jsonl").read_text(encoding="utf-8").splitlines()]
        frames = sorted((folder / "frames").iterdir())
        self.assertEqual(len(lines), len(frames))
        self.assertTrue(lines and all("boxes_px" in l and len(l["levels"]) == len(l["boxes_px"]) for l in lines))
        out = self.tmp / "from-bank-recorded"
        self.assertEqual(sweep.main(["run", "--run", str(self.run_dir), "--frames", str(folder / "frames"), "--boxes", str(folder / "boxes.jsonl"),
                                     "--name", "case134", "--threads", "1", "--warmup", "1", "--out", str(out)]), 0)
        self.assertEqual(json.loads((out / "summary.json").read_text(encoding="utf-8"))["frames"], len(frames))

    def test_6c_a_box_past_the_edge_is_clipped_and_one_outside_is_dropped_with_its_level(self):
        sweep = load("sweep")
        line = {"frame": "x", "boxes_px": [[-10, 10, 50, 60], [300, 10, 320, 60], [10, 10, 40, 40]], "levels": ["L1", "L2", "L3"]}
        boxes, kept = sweep.unit_boxes(line, 256, 192)
        self.assertEqual(kept, [0, 2])
        self.assertEqual(boxes[0][0], 0.0)

    def test_6_a_changed_onnx_file_loses_its_parity(self):
        onnx_file = self.run_dir / "onnx" / "level.onnx"
        original = onnx_file.read_bytes()
        try:
            onnx_file.write_bytes(original + b"\0")
            with self.assertRaises(self.latency.LatencyError):
                self.latency.require_parity(self.run_dir, "onnxruntime", "cpu")
        finally:
            onnx_file.write_bytes(original)

    def test_7_parity_on_one_device_is_no_parity_on_another(self):
        with self.assertRaises(self.latency.LatencyError):
            self.latency.require_parity(self.run_dir, "onnxruntime", "cuda")

    def test_8_a_failed_parity_takes_the_arm_out_of_the_headline(self):
        verdict_file = self.run_dir / "onnx" / "parity-onnxruntime-cpu.json"
        original = verdict_file.read_text(encoding="utf-8")
        try:
            verdict_file.write_text(json.dumps(dict(json.loads(original), passed=False)), encoding="utf-8")
            headline = self.latency.write_headline(self.run_dir)
            self.assertEqual(headline["arm"], "torch-cpu-2t")
        finally:
            verdict_file.write_text(original, encoding="utf-8")
            self.latency.write_headline(self.run_dir)

    def test_9_frames_run_in_number_order_and_a_misnamed_line_is_refused(self):
        sweep = load("sweep")
        folder = self.tmp / "order"
        (folder / "frames").mkdir(parents=True)
        frame, _ = self.latency.frames_of(self.catalog, "test")[0]
        for name in ("img_10.png", "img_2.png", "img_1.png"):
            (folder / "frames" / name).write_bytes(Path(frame).read_bytes())
        names = [name for name, _ in sweep.frame_sources(folder / "frames")]
        self.assertEqual(names, ["img_1.png", "img_2.png", "img_10.png"])
        lines = [{"frame": n, "boxes": []} for n in ("img_1.png", "img_10.png", "img_2.png")]
        (folder / "boxes.jsonl").write_text("".join(json.dumps(l) + "\n" for l in lines), encoding="utf-8")
        with self.assertRaises(sweep.SweepError):
            sweep.read_boxes(folder / "boxes.jsonl", names)

    def test_9b_a_sixteen_bit_frame_is_refused_not_clipped(self):
        import numpy as np
        from PIL import Image

        sweep = load("sweep")
        path = self.tmp / "deep.png"
        Image.fromarray(np.full((8, 8), 4000, dtype=np.uint16)).save(path)
        with self.assertRaises(sweep.SweepError):
            sweep.decode(path)


if __name__ == "__main__":
    unittest.main()
