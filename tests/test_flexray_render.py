"""tools/flexray_render.py and tools/render_blocks.py on a made-up CT corpus: two subjects of
soft tissue with two bone cubes each, labelled vertebrae_L1 and vertebrae_L2 as TotalSegmentator
writes them, and one with no supervised structure, rendered on the CPU at a 32-pixel detector
and 64 ray samples by the blocks engine and, where FleXray's runtime imports, by FleXray's own
code, so the layout, the reuse, the seeds shared between render groups and the arithmetic held
equal to FleXray's (the crop plan, the crop weights, the crop draw, the crop records, the
scaling) are checked where fxr is installed; tests/schwingnet/test_render_blocks.py holds the
pure rules without it.

It needs numpy, torch, nibabel, Pillow, fxr (flexray from pip) and the package's contract
libraries, which the job's environment holds and the required check's python does not, so each
case runs where they import and is skipped elsewhere; the cases of FleXray's own runtime need
kornia too, which fxr.models.camera imports for its label smoothing, and are skipped without it.

    <venv>/bin/python -m unittest tests.test_flexray_render
"""

import importlib
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
NEEDED = ("numpy", "torch", "nibabel", "PIL", "fxr", "beartype", "icontract", "pydantic")
MISSING = [name for name in NEEDED if importlib.util.find_spec(name) is None]
SALT = "c"  # under this salt two of the four views open FleXray's attenuation gate
SMALL = ["views=2", "detector=32", "ray_samples=64"]
TOOLS = {}


def load_tool(name):
    """A tool loaded by path, once, under a name of its own (tools/ is never on sys.path)."""
    if name not in TOOLS:
        path = ROOT / "tools" / f"{name}.py"
        spec = importlib.util.spec_from_file_location(f"{name}_under_test", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        TOOLS[name] = module
    return TOOLS[name]


def runtime_missing():
    """Why FleXray's runtime cannot run here, or None: its camera package imports kornia."""
    try:
        importlib.import_module("fxr.models.camera.runtime")
        importlib.import_module("fxr.experiment.label_projection")
    except ImportError as error:
        return f"FleXray's runtime does not import here: {error}"
    return None


def write_nifti(path, array, affine):
    import nibabel

    nibabel.save(nibabel.Nifti1Image(array, affine), str(path))


def make_subject(folder, depth, cubes):
    """A CT of 64 x 64 x depth voxels, 3 mm in plane and 1.5 mm along the slices, soft tissue
    throughout so that every ray through it adds up, with one bone cube per structure named,
    each written as its TotalSegmentator mask; an empty mask for vertebrae_L3, as
    TotalSegmentator writes one for a structure it did not find."""
    import numpy as np

    shape = (64, 64, depth)
    affine = np.diag([3.0, 3.0, 1.5, 1.0])
    affine[:3, 3] = [-96.0, -96.0, -0.75 * depth]
    ct = np.full(shape, 40.0, dtype=np.float32)
    (folder / "segmentations").mkdir(parents=True)
    for structure, (first, last) in cubes.items():
        mask = np.zeros(shape, dtype=np.uint8)
        mask[24:40, 24:40, first:last] = 1
        ct[mask > 0] = 800.0
        write_nifti(folder / "segmentations" / f"{structure}.nii.gz", mask, affine)
    write_nifti(folder / "segmentations" / "vertebrae_L3.nii.gz", np.zeros(shape, np.uint8), affine)
    write_nifti(folder / "ct.nii.gz", ct, affine)


def make_corpus(root):
    """Three subjects, one nested: 300 slices (two crops), 200 slices (one padded crop) and one
    with no supervised structure."""
    make_subject(root / "s0001", 300, {"vertebrae_L1": (60, 90), "vertebrae_L2": (200, 230)})
    make_subject(root / "batch" / "s0002", 200,
                 {"vertebrae_L1": (50, 80), "vertebrae_L2": (120, 150)})
    make_subject(root / "s0003", 120, {})


def rows_by_file(out):
    """The manifest's rows by file, without the seconds a render took, which no run repeats."""
    manifest = json.loads((Path(out) / "manifest.json").read_text(encoding="utf-8"))
    return {row["file"]: {k: v for k, v in row.items() if k != "seconds"}
            for row in manifest["views"]}


def render(renderer, root, out, words, engine="blocks", subjects=3):
    blocks = renderer.rules().parse(SMALL + words)
    return renderer.render_subjects(root, out, subjects, SALT, "cpu", blocks=blocks, engine=engine)


def label_volume(shape, cubes):
    """A label volume of the cubes make_subject writes, by MOOSE id, for the crop record cases."""
    import numpy as np

    label = np.zeros(shape, dtype=np.uint8)
    for moose_id, (first, last) in cubes.items():
        label[24:40, 24:40, first:last] = moose_id
    return label


@unittest.skipIf(MISSING, f"needs {', '.join(MISSING)}")
class Tables(unittest.TestCase):
    def test_the_torch_table_names_every_choice_of_the_rules(self):
        parts = load_tool("render_blocks")
        self.assertEqual(tuple(parts.NAMES), tuple(parts.rules.CHOICES))
        for name, allowed in parts.rules.CHOICES.items():
            self.assertEqual(tuple(parts.NAMES[name]), allowed, name)
            for choice, function in parts.NAMES[name].items():
                self.assertTrue(callable(function), f"{name}={choice}")
                self.assertIn("fxr/", function.__doc__ or "",
                              f"{name}={choice} says where FleXray does it")

    def test_every_structure_written_is_one_the_protocol_supervises(self):
        renderer = load_tool("flexray_render")
        names = renderer.moose_labels()
        ids = {name: i for i, name in names.items()}
        lut = renderer.label_lut()
        supervised = renderer.supervised_ids(lut)
        self.assertEqual(len(lut), len(names))
        for structure, name in renderer.TOTALSEG_TO_MOOSE.items():
            self.assertIn(name, ids, structure)
            self.assertIn(ids[name], supervised, f"{structure} -> {name}")
        self.assertNotIn(ids["vertebra_l6"], supervised)

    def test_the_label_table_reads_as_flexrays_projection(self):
        reason = runtime_missing()
        if reason:
            self.skipTest(reason)
        from fxr.experiment.label_projection import TrainingLabelProjection

        renderer = load_tool("flexray_render")
        projection = TrainingLabelProjection.from_label_remap(renderer.label_remap())
        lut = renderer.label_lut()
        self.assertEqual(tuple(lut), projection.label_lut)
        self.assertEqual(renderer.supervised_ids(lut), projection.native_foreground_label_ids())


@unittest.skipIf(MISSING, f"needs {', '.join(MISSING)}")
class FleXraysArithmetic(unittest.TestCase):
    def test_plan_crops_is_plan_z_crops(self):
        from fxr.datasets.ct_crops import plan_z_crops

        rules = load_tool("render_blocks").rules
        for depth in (1, 100, 101, 255, 256, 257, 300, 511, 512, 513, 700, 1000, 1500, 4096):
            planned = plan_z_crops(depth, rules.CROP_DEPTH)
            self.assertEqual(
                rules.plan_crops(depth),
                tuple((s.z_start, s.z_stop, s.z_pad_before, s.z_pad_after) for s in planned), depth)
            for spec in planned:
                self.assertEqual(spec.z_offset, spec.z_start - spec.z_pad_before)
        self.assertEqual([s.z_start for s in plan_z_crops(700, 256)], [0, 222, 444])

    def test_crop_weights_are_inverse_label_frequency_weights(self):
        import torch
        from fxr.datasets.sampling import inverse_label_frequency_weights

        parts = load_tool("render_blocks")
        lut = [0, 1, 2, 2, 0, 3, -1, 4, 4, 5]  # two native ids to one class, a drop, an undeclared
        for sets in (
            [[1], [1, 2], [3], [4, 5]],
            [[1, 2, 3], [1], [2, 3], [1, 2, 3], [4, 5, 7, 8]],
            [[9], [9], [9]],
            [[1, 4], [4], [7, 8, 9]],
        ):
            crops = [{"ids": ids} for ids in sets]
            found = parts.crop_sampler_inverse_label_frequency(crops, lut)
            expected = inverse_label_frequency_weights(sets, lut, tau=0.5, class_aggregation="max")
            self.assertTrue(torch.allclose(found, expected.double(), atol=1e-12),
                            (sets, found, expected))
            self.assertAlmostEqual(float(found.mean()), 1.0)

    def test_the_crop_draw_is_the_weighted_random_samplers(self):
        import torch
        from torch.utils.data import WeightedRandomSampler

        parts = load_tool("render_blocks")
        for weights in ([1.0, 1.0], [0.2, 1.6, 1.2], [2.0, 0.0, 1.0, 1.0]):
            for seed in range(20):
                torch.manual_seed(seed)
                theirs = next(iter(WeightedRandomSampler(weights, num_samples=1, replacement=True)))
                torch.manual_seed(seed)
                ours = parts.draw_crop(torch.tensor(weights, dtype=torch.float64))
                self.assertEqual(ours, theirs, (weights, seed))

    def test_crop_content_records_what_crop_metadata_records(self):
        import numpy as np
        from fxr.datasets.ct_crops import crop_metadata, crop_z, offset_affine, plan_z_crops

        parts = load_tool("render_blocks")
        volumes = ((300, {78: (60, 90), 79: (200, 230)}), (200, {78: (50, 80), 79: (120, 150)}),
                   (300, {78: (10, 40)}), (700, {59: (0, 30), 60: (300, 340), 61: (690, 700)}))
        for depth, cubes in volumes:
            label = label_volume((64, 64, depth), cubes)
            affine = np.diag([3.0, 3.0, 1.5, 1.0])
            affine[:3, 3] = [-96.0, -96.0, -0.75 * depth]
            content = parts.crop_content(label, parts.rules.plan_crops(depth))
            ours = {c["z_start"]: c for c in content}
            theirs = {}
            for spec in plan_z_crops(depth, 256):
                label_crop = crop_z(label, spec, fill_value=0)
                if not np.any(label_crop != 0):
                    continue
                meta = crop_metadata(spec, label_crop, subject_id="s", source_sample_id="s")
                theirs[spec.z_start] = (spec, meta, label_crop)
            self.assertEqual(set(ours), set(theirs), depth)
            for start, (spec, meta, label_crop) in theirs.items():
                crop = ours[start]
                self.assertEqual(crop["ids"], meta["crop_foreground_label_ids"])
                for i, centroid in zip(crop["ids"], meta["fg_centroids_ijk"], strict=True):
                    np.testing.assert_allclose(crop["centroids"][i], centroid, atol=1e-9)
                np.testing.assert_array_equal(parts.cut(label, crop, 0), label_crop)
                np.testing.assert_allclose(parts.crop_affine(affine, crop),
                                           offset_affine(affine, spec))

    def test_scale_minmax_is_scale_rendered_images(self):
        reason = runtime_missing()
        if reason:
            self.skipTest(reason)
        import torch
        from fxr.models.camera.runtime import scale_rendered_images

        parts = load_tool("render_blocks")
        torch.manual_seed(0)
        images = torch.rand(3, 1, 8, 8) * 5 - 1
        images[1, 0, 2, 3] = float("nan")
        images[2] = 0.5
        self.assertTrue(torch.equal(parts.scale_minmax(images), scale_rendered_images(images)))


@unittest.skipIf(MISSING, f"needs {', '.join(MISSING)}")
class Rendering(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Path(tempfile.mkdtemp(prefix="flexray-render-"))
        cls.root = cls.base / "ct"
        make_corpus(cls.root)
        cls.renderer = load_tool("flexray_render")
        cls.done = render(cls.renderer, cls.root, cls.base / "default", [])
        cls.physical = render(cls.renderer, cls.root, cls.base / "physical", ["attenuation=off"])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base, ignore_errors=True)

    def test_find_subjects_walks_the_nested_layout(self):
        self.assertEqual(self.renderer.find_subjects(self.root), ["batch/s0002", "s0001", "s0003"])

    def test_two_subjects_are_kept_and_the_empty_one_passed_over_with_its_reason(self):
        self.assertEqual(self.done["rendered"], 4)
        self.assertEqual((self.done["rendered_now"], self.done["reused"]), (4, 0))
        self.assertEqual(sorted(self.done["subjects"]), ["batch/s0002", "s0001"])
        self.assertEqual(self.done["skipped"], ["s0003: no supervised structure in its masks"])

    def test_each_view_is_a_16_bit_png_at_the_detector_size(self):
        import numpy as np
        from PIL import Image

        rows = rows_by_file(self.base / "default")
        self.assertEqual(sorted(rows), ["images/batch-s0002_v00.png", "images/batch-s0002_v01.png",
                                        "images/s0001_v00.png", "images/s0001_v01.png"])
        levels = []
        for file in rows:
            with Image.open(self.base / "default" / file) as image:
                self.assertEqual((image.mode, image.size), ("I;16", (32, 32)), file)
                levels.append(len(np.unique(np.asarray(image))))
        self.assertGreater(max(levels), 1, "the renderer saw the volume in at least one view")

    def test_the_manifest_and_the_record_say_what_was_rendered(self):
        rules = self.renderer.rules()
        manifest = json.loads((self.base / "default" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["blocks"], rules.as_record(rules.parse(SMALL)))
        self.assertEqual(manifest["engine"], "blocks")
        self.assertEqual(manifest["flexray"], self.renderer.versions()["flexray"])
        for row in manifest["views"]:
            self.assertEqual(set(row), {"file", "subject", "view", "seed", "crop", "isocentre",
                                        "pose", "attenuation", "seconds"})
            seed = self.renderer.view_seed(SALT, row["subject"], row["view"])
            self.assertEqual(row["seed"], seed)
            self.assertEqual(set(row["crop"]), {"z_start", "z_stop", "pad_before", "pad_after"})
            self.assertIn(row["isocentre"]["label"], (78, 79))
            names = {78: "vertebra_l1", 79: "vertebra_l2"}
            self.assertEqual(row["isocentre"]["name"], names[row["isocentre"]["label"]])
            self.assertEqual(len(row["isocentre"]["point_mm"]), 3)
            self.assertEqual(set(row["pose"]), {"rot_deg", "xyz_mm", "orthographic", "sdd", "delx"})
            self.assertTrue(1150.0 <= row["pose"]["sdd"] <= 1250.0)
            self.assertTrue(1.25 <= row["pose"]["delx"] <= 2.25)
        record = json.loads((self.base / "default" / "RENDER.json").read_text(encoding="utf-8"))
        self.assertEqual((record["version"], record["status"]), (2, "done"))
        self.assertEqual(record["settings"]["engine"], "blocks")
        self.assertEqual(record["counts"]["subjects_kept"], 2)
        self.assertEqual(record["skipped"], self.done["skipped"])

    def test_a_second_call_under_the_same_settings_reuses_every_view(self):
        out = self.base / "default"
        before = {p.name: p.read_bytes() for p in (out / "images").glob("*.png")}
        rows = rows_by_file(out)
        again = render(self.renderer, self.root, out, [])
        self.assertEqual((again["rendered"], again["rendered_now"], again["reused"]), (4, 0, 4))
        self.assertEqual(again["subjects"], self.done["subjects"])
        self.assertEqual({p.name: p.read_bytes() for p in (out / "images").glob("*.png")}, before)
        self.assertEqual(rows_by_file(out), rows)

    def test_other_settings_render_anew_into_the_same_folder(self):
        out = self.base / "default"
        other = render(self.renderer, self.root, out, ["crop_sampler=uniform"])
        self.assertEqual((other["rendered_now"], other["reused"]), (4, 0))
        record = json.loads((out / "RENDER.json").read_text(encoding="utf-8"))
        self.assertEqual(record["settings"]["blocks"]["crop_sampler"], "uniform")
        back = render(self.renderer, self.root, out, [])
        self.assertEqual((back["rendered_now"], back["reused"]), (4, 0))

    def test_groups_that_differ_only_by_attenuation_share_crop_isocentre_and_pose(self):
        default = rows_by_file(self.base / "default")
        physical = rows_by_file(self.base / "physical")
        self.assertEqual(set(default), set(physical))
        for file, row in default.items():
            other = physical[file]
            self.assertEqual(row["crop"], other["crop"], file)
            self.assertEqual(row["isocentre"], other["isocentre"], file)
            self.assertEqual(row["pose"], other["pose"], file)
            self.assertEqual(row["seed"], other["seed"], file)
            self.assertIsNone(other["attenuation"], file)
        opened = [row for row in default.values() if row["attenuation"] is not None]
        self.assertGreaterEqual(len(opened), 1, "the salt opens the gate at least once")
        for row in opened:
            held = {78, 79} & set(int(i) for i in row["attenuation"])
            self.assertTrue(held, row["file"])
            for factor in row["attenuation"].values():
                self.assertTrue(0.1 <= factor <= 4.0)

    def test_the_factors_recorded_are_the_ones_render_drr_drew(self):
        import fxr.drr.subjects as subjects

        drawn = []
        original = subjects.sample_attenuation

        def recording(bounds, n, *args, **kwargs):
            factors = original(bounds, n, *args, **kwargs)
            drawn.append((int(n), [float(f) for f in factors.tolist()]))
            return factors

        with mock.patch.object(subjects, "sample_attenuation", recording):
            done = render(self.renderer, self.root, self.base / "recorded", [])
        rows = rows_by_file(self.base / "recorded")
        supervised = self.renderer.supervised_ids(self.renderer.label_lut())
        self.assertEqual(rows, rows_by_file(self.base / "default"))
        for subject in done["subjects"]:
            for view in range(2):
                row = rows[self.renderer.render_file(subject, view)]
                count, factors = drawn.pop(0)
                if row["attenuation"] is None:
                    self.assertEqual(count, 1, "a shut gate draws one factor of 1")
                    continue
                self.assertEqual(count, len(supervised))
                for i, factor in row["attenuation"].items():
                    self.assertAlmostEqual(factor, factors[supervised.index(int(i))], places=6)
        self.assertEqual(drawn, [])

    def test_the_runtime_engine_refuses_a_choice_in_words_before_writing(self):
        rules = self.renderer.rules()
        out = self.base / "refused"
        refused = "FleXray's runtime cannot honour crop='whole'"
        with self.assertRaisesRegex(rules.RenderBlockError, refused):
            render(self.renderer, self.root, out, ["crop=whole", "crop_sampler=uniform"],
                   engine="flexray-runtime")
        self.assertFalse(out.exists())
        with self.assertRaisesRegex(rules.RenderBlockError, "engine 'flux' is not one of"):
            render(self.renderer, self.root, out, [], engine="flux")
        with self.assertRaises(ValueError):
            render(self.renderer, self.root, out, [], subjects=0)
        self.assertFalse(out.exists())

    def test_named_subjects_are_rendered_in_their_order_and_a_missing_one_is_passed_over(self):
        blocks = self.renderer.rules().parse(SMALL + ["attenuation=off"])
        done = self.renderer.render_subjects(self.root, self.base / "named", 5, SALT, "cpu",
                                             blocks=blocks,
                                             subject_ids=("s0001", "nowhere", "s0003"))
        self.assertEqual(done["subjects"], ["s0001"])
        self.assertEqual(done["skipped"], ["nowhere: not found under the CT folder",
                                           "s0003: no supervised structure in its masks"])
        self.assertEqual(rows_by_file(self.base / "named")["images/s0001_v00.png"],
                         rows_by_file(self.base / "physical")["images/s0001_v00.png"])

    def test_the_command_line_renders_one_subject(self):
        out = self.base / "cli"
        code = self.renderer.main([
            "--ct-root", str(self.root), "--out", str(out), "--subjects", "1", "--salt", SALT,
            "--blocks", "views=1", "--blocks", "detector=32", "--blocks", "ray_samples=64",
            "--blocks", "attenuation=off"])
        self.assertEqual(code, 0)
        self.assertEqual(len(rows_by_file(out)), 1)
        record = json.loads((out / "RENDER.json").read_text(encoding="utf-8"))
        self.assertEqual(record["arguments"]["engine"], "blocks")
        self.assertEqual(record["settings"]["blocks"]["views"], 1)


@unittest.skipIf(MISSING, f"needs {', '.join(MISSING)}")
class FleXraysRuntime(unittest.TestCase):
    """FleXray's own code rendering the same corpus from the same seeds: with the draws in the
    same order, the blocks engine's crop, isocentre, pose and factors are its own."""

    @classmethod
    def setUpClass(cls):
        cls.reason = runtime_missing()
        if cls.reason:
            return
        cls.base = Path(tempfile.mkdtemp(prefix="flexray-runtime-"))
        cls.root = cls.base / "ct"
        make_corpus(cls.root)
        cls.renderer = load_tool("flexray_render")
        cls.blocks = render(cls.renderer, cls.root, cls.base / "blocks", [])
        cls.runtime = render(cls.renderer, cls.root, cls.base / "runtime", [],
                             engine="flexray-runtime")

    @classmethod
    def tearDownClass(cls):
        if not cls.reason:
            shutil.rmtree(cls.base, ignore_errors=True)

    def setUp(self):
        if self.reason:
            self.skipTest(self.reason)

    def test_the_runtime_writes_the_same_layout(self):
        from PIL import Image

        self.assertEqual(self.runtime["subjects"], self.blocks["subjects"])
        self.assertEqual(self.runtime["skipped"], self.blocks["skipped"])
        rows = rows_by_file(self.base / "runtime")
        self.assertEqual(set(rows), set(rows_by_file(self.base / "blocks")))
        for file in rows:
            with Image.open(self.base / "runtime" / file) as image:
                self.assertEqual((image.mode, image.size), ("I;16", (32, 32)), file)
        record = json.loads((self.base / "runtime" / "RENDER.json").read_text(encoding="utf-8"))
        self.assertEqual(record["settings"]["engine"], "flexray-runtime")
        self.assertEqual(record["profile"]["effective_profile"]["num_views"], 1)
        self.assertEqual(record["profile"]["effective_profile"]["intrinsics_cfg"]["height"], 32)

    def test_the_blocks_engine_draws_what_flexrays_runtime_draws(self):
        import numpy as np

        ours = rows_by_file(self.base / "blocks")
        theirs = rows_by_file(self.base / "runtime")
        for file, row in ours.items():
            other = theirs[file]
            self.assertEqual(row["crop"], other["crop"], file)
            self.assertEqual(row["isocentre"]["label"], other["isocentre"]["label"], file)
            np.testing.assert_allclose(row["isocentre"]["point_mm"],
                                       other["isocentre"]["point_mm"], atol=1e-3)
            np.testing.assert_allclose(row["pose"]["rot_deg"], other["pose"]["rot_deg"], atol=1e-3)
            np.testing.assert_allclose(row["pose"]["xyz_mm"], other["pose"]["xyz_mm"], atol=1e-3)
            self.assertEqual(row["pose"]["orthographic"], other["pose"]["orthographic"], file)
            self.assertAlmostEqual(row["pose"]["sdd"], other["pose"]["sdd"], places=4)
            self.assertAlmostEqual(row["pose"]["delx"], other["pose"]["delx"], places=6)
            if row["attenuation"] is None:
                self.assertIsNone(other["attenuation"], file)
                continue
            self.assertEqual(set(row["attenuation"]), set(other["attenuation"]), file)
            for i, factor in row["attenuation"].items():
                self.assertAlmostEqual(factor, other["attenuation"][i], places=5)

    def test_the_runtimes_images_are_the_blocks_engines(self):
        import numpy as np
        from PIL import Image

        for file in rows_by_file(self.base / "blocks"):
            with Image.open(self.base / "blocks" / file) as ours:
                mine = np.asarray(ours, dtype=np.int64)
            with Image.open(self.base / "runtime" / file) as theirs:
                gap = np.abs(mine - np.asarray(theirs, dtype=np.int64))
            self.assertLessEqual(int(gap.max()), 2, file)

    def test_the_factors_recorded_are_the_ones_flexrays_render_drr_drew(self):
        import fxr.drr.subjects as subjects

        drawn = []
        original = subjects.sample_attenuation

        def recording(bounds, n, *args, **kwargs):
            factors = original(bounds, n, *args, **kwargs)
            drawn.append((int(n), [float(f) for f in factors.tolist()]))
            return factors

        with mock.patch.object(subjects, "sample_attenuation", recording):
            done = render(self.renderer, self.root, self.base / "recorded", [],
                          engine="flexray-runtime")
        rows = rows_by_file(self.base / "recorded")
        supervised = self.renderer.supervised_ids(self.renderer.label_lut())
        self.assertEqual(rows, rows_by_file(self.base / "runtime"))
        for subject in done["subjects"]:
            for view in range(2):
                row = rows[self.renderer.render_file(subject, view)]
                count, factors = drawn.pop(0)
                if row["attenuation"] is None:
                    self.assertEqual(count, 1)
                    continue
                self.assertEqual(count, len(supervised))
                for i, factor in row["attenuation"].items():
                    self.assertAlmostEqual(factor, factors[supervised.index(int(i))], places=6)
        self.assertEqual(drawn, [])


if __name__ == "__main__":
    unittest.main()
