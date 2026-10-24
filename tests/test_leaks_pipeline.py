"""The leak checks end to end, decoding real PNG frames (issue #9): two shards cut by tools/ingest.py
from synthetic banks, one holding a byte copy and a resized, brightened copy of frames of the
other under new persons, run off the grid through grid/run-leaks.sh with OUTSIDE_SLURM=1. The
fingerprint step needs numpy and Pillow and the ingest pydantic, which the train-cpu environment
holds and the required check's python does not, so the case runs where they import and is
skipped elsewhere; tests/schwingnet/test_leaks.py holds the rules and the join in the gate lane.

    .pixi/envs/train-cpu/bin/python -m unittest tests/test_leaks_pipeline.py
"""

import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEEDED = ("numpy", "PIL", "pydantic", "icontract", "beartype")
MISSING = [name for name in NEEDED if importlib.util.find_spec(name) is None]


def load(name):
    spec = importlib.util.spec_from_file_location(f"{name}_pipeline", ROOT / "tools" / f"{name}.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


def plant_copies(bank_a, bank_b):
    """Into bank B, a byte copy of A's eleventh frame and a 3/4-size, brighter copy of its
    twenty-first, each under a case of B's own."""
    from PIL import Image

    frames = sorted((bank_a / "images").rglob("*.png"))
    for source, stem, case, change in ((frames[10], "copy_exact", "case7001", False),
                                       (frames[20], "copy_near", "case7002", True)):
        data = source.read_bytes()
        meta = json.loads((bank_a / "meta" / f"{source.stem}.json").read_text(encoding="utf-8"))
        meta["case"] = case
        # The copy is another bank's frame: the map the source's meta names is a path in bank A,
        # and in B it would reach another frame's map or none (the synthetic bank maps about three
        # frames in four since #228), so the copy carries no map.
        meta.pop("level_map", None)
        meta.pop("level_map_from", None)
        if change:
            image = Image.open(io.BytesIO(data))
            image = image.resize((image.width * 3 // 4, image.height * 3 // 4), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            image.point(lambda v: min(255, v + 25)).save(buffer, "PNG")
            data = buffer.getvalue()
            for box in meta["boxes"]:
                box["box"] = [v * 3 / 4 for v in box["box"]]
        (bank_b / "images" / "train" / f"{stem}.png").write_bytes(data)
        (bank_b / "meta" / f"{stem}.json").write_text(json.dumps(meta), encoding="utf-8")


@unittest.skipIf(MISSING, f"needs {', '.join(MISSING)}: run it with the train-cpu environment's python")
class LeakPipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="leaks-pipeline-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.data = self.tmp / "data"
        bank = load("synthetic_bank")
        # Fifty frames, fewer than the 51 at which the synthetic bank repeats a frame's bytes.
        bank.main([str(self.tmp / "a"), "--frames", "50", "--cases", "10", "--seed", "5"])
        bank.main([str(self.tmp / "b"), "--frames", "30", "--cases", "6", "--seed", "9"])
        plant_copies(self.tmp / "a", self.tmp / "b")
        ingest = load("ingest")
        for bank_name, source in (("a", "carmlspine"), ("b", "carmlspine_sweeps")):
            argv = ["run", "--bank", str(self.tmp / bank_name), "--source", source, "--kind", "train",
                    "--date", "2026-10-21", "--code-commit", "abcdef1", "--grid-root", str(self.data / source)]
            self.assertEqual(ingest.main(argv), 0)

    def run_leaks(self):
        env = {**os.environ, "SCHWINGNET": str(ROOT), "DATA_ROOT": str(self.data), "PYDRV": sys.executable,
               "OUTSIDE_SLURM": "1", "LEAKS_OUT": str(self.tmp / "_leaks")}
        return subprocess.run(["bash", str(ROOT / "grid" / "run-leaks.sh")], env=env,
                              capture_output=True, text=True, timeout=600)

    def test_both_copies_are_caught_and_a_second_run_fingerprints_nothing_again(self):
        done = self.run_leaks()
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        (result_file,) = (self.tmp / "_leaks" / "runs").glob("*/LEAKS.json")
        result = json.loads(result_file.read_text(encoding="utf-8"))
        self.assertEqual(result["counts"], {"CHK-6": 1, "CHK-7": 1, "UNKNOWN": 0, "input_problems": 0})
        reasons = sorted(row["reason"] for row in result["rows"])
        self.assertEqual(reasons, ["near-duplicate under two persons",
                                   "undeclared alias: one key under two persons (store_key)"])
        prints = sorted((self.tmp / "_leaks" / "fingerprints").glob("*.jsonl"))
        before = [p.read_bytes() for p in prints]
        again = self.run_leaks()
        self.assertEqual(again.stdout.count('"outcome": "already there"'), 2, again.stdout)
        self.assertEqual([p.read_bytes() for p in prints], before)

    def test_a_frame_whose_bytes_changed_fails_the_check(self):
        (folder,) = sorted((self.data / "carmlspine" / "shards").iterdir())
        # A frame of the manifest's, since the shard holds the level maps at content addresses of
        # their own (#228) and the fingerprint reads the frames alone.
        manifest = json.loads((folder / "MANIFEST.json").read_text(encoding="utf-8"))
        frame = folder / manifest["items"][0]["path"]
        os.chmod(frame, 0o644)
        frame.write_bytes(frame.read_bytes() + b"\0")
        done = self.run_leaks()
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("XR_LEAKPRINT_RC=2", done.stdout)
        (result_file,) = (self.tmp / "_leaks" / "runs").glob("*/LEAKS.json")
        result = json.loads(result_file.read_text(encoding="utf-8"))
        self.assertEqual(result["counts"]["UNKNOWN"], 1)


if __name__ == "__main__":
    unittest.main()
