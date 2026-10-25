"""tools/domain_gap.py, the DRR domain-gap study's one job, run on made-up corpora: the plan takes
each group's files from a sample index or a folder by its rules (formats, modalities, sizes, globs,
masks left out, persons by rule with the frozen test persons dropped), the images come out as
256 x 256 windows of the centre square whatever their depth or shape, and a whole run over three
small corpora of different textures, with only the physics space, writes a summary of at most 80
lines that survive the grid's redaction, tells the textured corpora apart and finds nothing in its
split-half nulls.

It needs numpy, Pillow, torch, scikit-learn and the package's contracts, which the job's
environment holds and the required check's python does not, so each case runs where they import
and is skipped elsewhere.

    <venv>/bin/python -m unittest tests/test_domain_gap_run.py
"""

import importlib.util
import json
import re
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ("numpy", "PIL", "pydantic", "icontract", "beartype")
WHOLE = BASE + ("torch", "sklearn", "scipy", "matplotlib")
MISSING_BASE = [name for name in BASE if importlib.util.find_spec(name) is None]
MISSING_WHOLE = [name for name in WHOLE if importlib.util.find_spec(name) is None]


def load_tool():
    spec = importlib.util.spec_from_file_location("domain_gap_tool", ROOT / "tools" / "domain_gap.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def texture(rng, kind, side):
    """A grey image whose texture says its corpus: smooth blobs, fine noise or stripes."""
    import numpy as np

    if kind == "blobs":
        coarse = rng.normal(0, 1, (side // 16 + 1, side // 16 + 1))
        image = np.kron(coarse, np.ones((16, 16)))[:side, :side]
    elif kind == "noise":
        image = rng.normal(0, 1, (side, side))
    else:
        rows = np.arange(side)[:, None] * np.ones((1, side))
        image = np.sin(rows / 3.0) + 0.3 * rng.normal(0, 1, (side, side))
    return (image - image.min()) / (np.ptp(image) + 1e-9)


def save_png(path, unit, bits=8):
    import numpy as np
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    if bits == 16:
        Image.fromarray((unit * 65535).astype(np.uint16)).save(path)
    else:
        Image.fromarray((unit * 255).astype(np.uint8)).save(path)


SCHEMA = ("CREATE TABLE sample (path TEXT, rel TEXT, format TEXT, width TEXT, height TEXT, depth TEXT,"
          " modality TEXT, patient_id TEXT, study_uid TEXT, role TEXT, error TEXT, sources TEXT)")


def index_of(folder, rows):
    """A sample index with the columns the plan reads, one row per (path, rel, format, width,
    height, depth, modality, patient, study, role, error, sources)."""
    path = folder / "samples.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute(SCHEMA)
        connection.executemany("INSERT INTO sample VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    return path


def table(folder, groups):
    path = folder / "groups.json"
    path.write_text(json.dumps({"version": 1, "salt": "test-salt", "groups": groups}), encoding="utf-8")
    return path


def args_for(tool, folder, groups, index="", frozen="", weights=""):
    return tool.parse(["run", "--groups", str(groups), "--data-root", str(folder / "data"),
                       "--index", str(index), "--out", str(folder / "out"), "--device", "cpu",
                       "--workers", "1", "--wandb", "off", "--frozen", str(frozen),
                       "--weights", weights])


@unittest.skipIf(MISSING_BASE, f"needs {', '.join(MISSING_BASE)}")
class PlanTest(unittest.TestCase):
    def setUp(self):
        self.tool = load_tool()
        self.temporary = tempfile.TemporaryDirectory()
        self.folder = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def index_rows(self):
        rows = []
        for case in range(6):
            for view in ("ap", "lat"):
                rel = f"carmlspine/images/train/case{case}_{view}.png"
                rows.append((f"/x/{rel}", rel, "png", "1024", "1024", None, None, None, None, "image", None,
                             "unmapped:realxray"))
        rows.append(("/x/carmlspine/masks/case1_mask.png", "carmlspine/masks/case1_mask.png", "png", "1024",
                     "1024", None, None, None, None, "image", None, "unmapped:realxray"))
        rows.append(("/x/carmlspine/small.png", "carmlspine/small.png", "png", "100", "100", None, None, None,
                     None, "image", None, "unmapped:realxray"))
        rows.append(("/x/other/case9_ap.png", "other/case9_ap.png", "png", "1024", "1024", None, None, None,
                     None, "image", None, "unmapped:realxray"))
        for i in range(4):
            rows.append((f"/v/{i}.dicom", f"{i}.dicom", "dicom", "2000", "2000", None, "DX", "", f"study{i % 2}",
                         "image", None, "vindr_spinexr"))
        rows.append(("/v/ct.dcm", "ct.dcm", "dicom", "512", "512", None, "CT", "", "study9", "image", None,
                     "vindr_spinexr"))
        rows.append(("/v/broken.dcm", "broken.dcm", "dicom", "2000", "2000", None, "DX", "", "s", "image",
                     "unreadable", "vindr_spinexr"))
        return rows

    def groups(self):
        return [
            {"id": "carmlspine_spots", "label": "spots", "family": "fluoroscopy", "source": "index",
             "index_sources": ["realxray"], "globs": ["carmlspine/*"], "formats": ["png"],
             "person": "regex:(?P<person>case[0-9]+)", "cap": 100, "per_person": 1},
            {"id": "vindr_spinexr", "label": "vindr", "family": "film", "source": "index",
             "index_sources": ["vindr_spinexr"], "formats": ["dicom"], "person": "dicom:patient",
             "cap": 100, "per_person": 4},
            {"id": "nothing_here", "label": "absent", "family": "synthetic", "source": "walk",
             "folder": "absent", "cap": 10, "per_person": 1}]

    def test_the_plan_keeps_the_groups_files_by_their_rules(self):
        index = index_of(self.folder, self.index_rows())
        frozen = self.folder / "frozen.json"
        frozen.write_text(json.dumps([{"person": "carmlspine:case2", "why": "test"}]), encoding="utf-8")
        args = args_for(self.tool, self.folder, table(self.folder, self.groups()), index, frozen)
        Path(args.out).mkdir(parents=True)
        plan = self.tool.stage_plan(args, self.tool.read_table(args.groups))
        spots, vindr, absent = plan["groups"]
        self.assertEqual(spots["found"], 12)          # the mask, the small image and other/ are left out
        self.assertEqual(spots["frozen_dropped"], 2)  # case2's two views
        self.assertEqual(len(spots["chosen"]), 5)     # one view of each of the five other cases
        self.assertEqual({p for _, p in spots["chosen"]},
                         {f"carmlspine_spots:case{c}" for c in (0, 1, 3, 4, 5)})
        self.assertEqual(vindr["found"], 4)           # the CT slice and the unreadable file are not films
        self.assertEqual(vindr["person_rule"], "dicom:study")
        self.assertEqual(vindr["persons_found"], 2)
        self.assertIn("absent", absent["skipped"])
        self.assertEqual(absent["chosen"], [])

    def test_the_plan_is_kept_for_the_same_inputs_and_made_again_for_new_ones(self):
        index = index_of(self.folder, self.index_rows())
        groups = table(self.folder, self.groups())
        args = args_for(self.tool, self.folder, groups, index)
        Path(args.out).mkdir(parents=True)
        first = self.tool.stage_plan(args, self.tool.read_table(groups))
        self.assertEqual(self.tool.stage_plan(args, self.tool.read_table(groups)), first)
        changed = self.groups()
        changed[0]["per_person"] = 2
        table(self.folder, changed)
        again = self.tool.stage_plan(args, self.tool.read_table(groups))
        self.assertEqual(len(again["groups"][0]["chosen"]), 12)

    def test_a_patient_id_on_most_files_falls_back_to_the_study(self):
        group = self.tool.read_table(table(self.folder, self.groups())).groups[1]
        same = [("f1", "r1", "SITE", "a"), ("f2", "r2", "SITE", "b"), ("f3", "r3", "p3", "c")]
        varied = [("f1", "r1", "p1", "a"), ("f2", "r2", "p2", "b"), ("f3", "r3", "anonymous", "c")]
        self.assertEqual(self.tool.dicom_person_rule(group, same), "dicom:study")
        self.assertEqual(self.tool.dicom_person_rule(group, varied), "dicom:patient")

    def test_a_walk_takes_image_files_and_leaves_masks_out(self):
        data = self.folder / "data" / "lumos" / "bank"
        for name in ("images/train/lumos_x_001_1.png", "images/train/lumos_x_001_2.png",
                     "images/train/lumos_x_002_1.png", "images/train/lumos_x_002_1_mask.png", "meta/x.json"):
            (data / name).parent.mkdir(parents=True, exist_ok=True)
            (data / name).write_bytes(b"")
        groups = [{"id": "lumos", "label": "lumos", "family": "film", "source": "walk", "folder": "lumos/bank",
                   "globs": ["images/*"], "formats": ["png"],
                   "person": "regex:lumos_x_(?P<person>[0-9]{3})_[0-9]+[.]png$", "cap": 10, "per_person": 1},
                  self.groups()[0]]
        args = args_for(self.tool, self.folder, table(self.folder, groups), index_of(self.folder, []))
        Path(args.out).mkdir(parents=True)
        row = self.tool.stage_plan(args, self.tool.read_table(args.groups))["groups"][0]
        self.assertEqual(row["found"], 3)
        self.assertEqual(sorted(p for _, p in row["chosen"]), ["lumos:001", "lumos:002"])


@unittest.skipIf(MISSING_BASE, f"needs {', '.join(MISSING_BASE)}")
class ImageTest(unittest.TestCase):
    def setUp(self):
        self.tool = load_tool()

    def test_the_canonical_image_is_the_windowed_centre_square(self):
        import numpy as np

        wide = np.zeros((400, 1000))
        wide[:, 300:700] = np.linspace(0, 1, 400)[:, None]
        image = self.tool.canonical(wide)
        self.assertEqual(image.shape, (256, 256))
        self.assertGreaterEqual(float(image.min()), 0.0)
        self.assertLessEqual(float(image.max()), 1.0)
        self.assertLess(abs(float(image.mean()) - 0.5), 0.05)  # the flat sides are cut away

    def test_sixteen_bit_and_eight_bit_copies_of_one_film_agree(self):
        import numpy as np

        rng = np.random.default_rng(3)
        unit = texture(rng, "blobs", 300)
        with tempfile.TemporaryDirectory() as temporary:
            eight, sixteen = Path(temporary) / "a.png", Path(temporary) / "b.png"
            save_png(eight, unit, 8)
            save_png(sixteen, unit, 16)
            a, _ = self.tool.decode_one(str(eight))
            b, _ = self.tool.decode_one(str(sixteen))
        self.assertLess(float(np.abs(a.astype(float) - b.astype(float)).mean()), 0.01)

    def test_a_broken_file_gives_the_kind_of_error_and_never_its_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            broken = Path(temporary) / "secret_name.png"
            broken.write_bytes(b"not an image")
            image, why = self.tool.decode_one(str(broken))
        self.assertIsNone(image)
        self.assertNotIn("secret_name", why)

    def test_physics_features_are_finite_and_the_same_every_time(self):
        import numpy as np

        unit = texture(np.random.default_rng(1), "noise", 256).astype(np.float32)
        first, second = self.tool.physics_features(unit), self.tool.physics_features(unit)
        self.assertTrue(np.isfinite(first).all())
        self.assertTrue(np.array_equal(first, second))


@unittest.skipIf(MISSING_WHOLE, f"needs {', '.join(MISSING_WHOLE)}")
class WholeRunTest(unittest.TestCase):
    def test_a_run_over_three_textured_corpora(self):
        tool = load_tool()
        tool.PERMUTATIONS_C2ST, tool.PERMUTATIONS_MMD, tool.BOOTSTRAP = 5, 50, 50
        tool.SPLIT_PERSONS = 12
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            args = self.corpora(tool, folder)
            self.assertEqual(tool.run(args), 0)
            lines = (Path(args.out) / "summary.txt").read_text(encoding="ascii").splitlines()
            results = json.loads((Path(args.out) / "results.json").read_text(encoding="utf-8"))
        self.assertLessEqual(len(lines), 80)
        for line in lines:
            self.assertLessEqual(len(line), 200)
            self.assertIsNone(re.search(r"[A-Za-z0-9_+=-]{32,}", line))
            self.assertIsNone(re.search(r"\b[0-9]{8}\b", line))
        physics = results["spaces"]["physics"]
        cross = physics["vs_family"]["blobs"]["film"]
        self.assertGreater(cross["auc_logistic"]["auc"], 0.9)
        self.assertIn("p", cross["auc_logistic"])
        self.assertLess(physics["calibration"]["auc_median"], 0.75)
        self.assertEqual(results["spaces"]["flexray"]["invalid"], "no FleXray bundle (ensemble.json)")
        self.assertTrue(any(line.startswith(" blobs vs film auc") for line in lines))

    def corpora(self, tool, folder):
        import numpy as np

        rng = np.random.default_rng(11)
        groups = []
        for name, family, kind in (("blobs", "synthetic", "blobs"), ("noisy", "fluoroscopy", "noise"),
                                   ("striped", "film", "stripes")):
            for person in range(24):
                for view in range(2):
                    save_png(folder / "data" / name / f"p{person:02d}_{view}.png", texture(rng, kind, 280))
            groups.append({"id": name, "label": name, "family": family, "source": "walk", "folder": name,
                           "person": "regex:(?P<person>p[0-9]+)_", "cap": 100, "per_person": 2})
        return args_for(tool, folder, table(folder, groups), index_of(folder, []))


if __name__ == "__main__":
    sys.exit(unittest.main())
