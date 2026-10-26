"""tools/chain_stats.py and tools/chain_eval.py end to end (docs/research/ct-priors-for-2d-detection.md,
item 1): segmented CTs in both layouts become a prior whose spacing and column odds are the scans',
readers' column calls from CT outrank the count a cut segmentation gives, and the evaluator scores
the classifier and the column decoder on a synthetic catalog with settings chosen on validation.

It needs numpy and, for the evaluator, torch and Pillow, so it runs in the train-cpu environment
(`pixi run -e train-cpu python -m unittest tests.test_chain_tools`) and skips under the required
check's plain python3."""

import gzip
import importlib.util
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEEDED = ("numpy", "torch", "PIL", "beartype", "pydantic")
MISSING = [name for name in NEEDED if importlib.util.find_spec(name) is None]


def python(*args):
    done = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, timeout=900)
    if done.returncode != 0:
        raise AssertionError(f"{args}: {done.stdout}\n{done.stderr}")
    return done.stdout


def write_nifti(path, data, spacing=(1.0, 1.0, 1.0)):
    """A minimal NIfTI-1 file, gzipped, with a scaling sform, as the grid's masks are written."""
    import numpy as np

    header = bytearray(352)
    struct.pack_into("<i", header, 0, 348)
    struct.pack_into("<8h", header, 40, 3, *data.shape, 1, 1, 1, 1)
    struct.pack_into("<h", header, 70, 4)
    struct.pack_into("<h", header, 72, 16)
    struct.pack_into("<8f", header, 76, 1.0, *spacing, 0, 0, 0, 0)
    struct.pack_into("<f", header, 108, 352.0)
    struct.pack_into("<h", header, 254, 1)
    for k in range(3):
        row = [0.0, 0.0, 0.0, 0.0]
        row[k] = spacing[k]
        struct.pack_into("<4f", header, 280 + 16 * k, *row)
    header[344:348] = b"n+1\x00"
    body = np.asarray(data, dtype="<i2").tobytes(order="F")
    path.write_bytes(gzip.compress(bytes(header) + body))


def spine(levels, height=10, gap=3):
    """A label column along z: each level a block of height slices with gap slices between."""
    import numpy as np

    depth = len(levels) * (height + gap) + gap
    volume = np.zeros((6, 6, depth), dtype=np.int16)
    for i, value in enumerate(levels):
        start = gap + i * (height + gap)
        volume[1:5, 1:5, start : start + height] = value
    return volume


def load_chain_stats():
    """tools/chain_stats.py as a module, by path, since tools/ is never on sys.path."""
    spec = importlib.util.spec_from_file_location("chain_stats_tool", ROOT / "tools" / "chain_stats.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipIf(MISSING, f"needs the train environment ({', '.join(MISSING)} missing)")
class ChainStatsTest(unittest.TestCase):
    def test_the_verse_alphabet_is_the_segmenters_in_short_names(self):
        """The values the counts read are schwingnet.segmenters' VerSe alphabet, which the render
        blocks' label volumes read too, in this tool's short names."""
        verse = load_chain_stats().VERSE
        self.assertEqual(verse, {**{i: f"C{i}" for i in range(1, 8)}, **{7 + i: f"T{i}" for i in range(1, 13)},
                                 **{19 + i: f"L{i}" for i in range(1, 6)}, 25: "L6", 26: "sacrum", 28: "T13"})
        self.assertNotIn(27, verse, "the coccyx is no level")

    def test_a_prior_from_both_layouts_and_readers_calls(self):
        tmp = Path(tempfile.mkdtemp())
        whole = list(range(8, 20)) + list(range(20, 25)) + [26]
        (tmp / "verse").mkdir()
        for n in range(6):
            write_nifti(tmp / "verse" / f"sub-{n}_seg-vert_msk.nii.gz", spine(whole))
        cut = list(range(20, 25)) + [25, 26]
        write_nifti(tmp / "verse" / "sub-l6_seg-vert_msk.nii.gz", spine(cut))
        seg = tmp / "ts" / "s0001" / "segmentations"
        seg.mkdir(parents=True)
        import numpy as np

        column = spine([1, 2])
        write_nifti(seg / "vertebrae_L5.nii.gz", (column == 1).astype(np.int16))
        write_nifti(seg / "sacrum.nii.gz", (column == 2).astype(np.int16))
        calls = tmp / "calls.csv"
        calls.write_text("scan,column,reader\nsub-l6,T12L6,owner\nunsegmented,T13L5,owner\nbad,other,owner\n", encoding="utf-8")
        out = tmp / "prior.json"
        python(ROOT / "tools" / "chain_stats.py", "--verse", tmp / "verse", "--totalseg", tmp / "ts",
               "--columns", calls, "--out", out, "--records", tmp / "records.jsonl")
        prior = json.loads(out.read_text(encoding="ascii"))
        self.assertEqual(prior["scans"], 9)
        self.assertEqual(prior["whole_columns"], {"T12L5": 6, "T12L6": 1, "T13L5": 1})
        self.assertGreater(prior["columns"]["T12L5"], prior["columns"]["T12L6"])
        self.assertIn("T12|L1", prior["spacing"])
        law = prior["spacing"]["L1|L2"]
        self.assertAlmostEqual(law["mu"], __import__("math").log(13 / 9), delta=0.05)
        self.assertEqual(prior["pairs_measured"]["L6|sacrum"], 1)
        self.assertEqual(prior["pairs_measured"]["L5|sacrum"], 7)


@unittest.skipIf(MISSING, f"needs the train environment ({', '.join(MISSING)} missing)")
class ChainEvalTest(unittest.TestCase):
    def test_both_answers_are_scored_with_validation_settings(self):
        tmp = Path(tempfile.mkdtemp())
        spec = importlib.util.spec_from_file_location("latency_test", ROOT / "tests" / "test_latency_tools.py")
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        catalog = helper.LatencyToolsTest.make_catalog(tmp)
        run = helper.LatencyToolsTest.make_run(tmp / "run")
        record = json.loads((run / "RUN.json").read_text(encoding="utf-8"))
        record.update({"run_id": "0123456789ab", "clean_tree": True, "catalog_sha256": "0" * 64})
        (run / "RUN.json").write_text(json.dumps(record), encoding="utf-8")
        prior = tmp / "prior.json"
        names = [f"T{t}L{n}" for t in (11, 12, 13) for n in (4, 5, 6)]
        prior.write_text(json.dumps({"spacing": {}, "fallback": {"mu": 0.3, "sigma": 0.15},
                                     "columns": {n: (0.9 if n == "T12L5" else 0.0125) for n in names}}), encoding="utf-8")
        printed = python(ROOT / "tools" / "chain_eval.py", "--catalog", catalog, "--run", run, "--prior", prior)
        self.assertIn("Settings from validation only", printed)
        summary = json.loads((run / "evaluate" / "chain.json").read_text(encoding="ascii"))
        measures = {r["measure"] for r in summary["rows"]}
        self.assertEqual(measures, {"accuracy, each crop alone", "accuracy, one column"})
        self.assertTrue((run / "evaluate" / "chain.md").is_file())


if __name__ == "__main__":
    unittest.main()
