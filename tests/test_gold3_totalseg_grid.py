"""tools/gold3_totalseg_grid.py: the studies it asks for, where it looks for their files, the
check of each drawn target against the release's own levels, and the report that leaves the grid.

The check reads masks through nibabel, which this container may not have; where it is missing a
stub that gives an image its data and affine stands in, so the geometry is tested on numpy alone.
numpy itself is needed for those tests and they are skipped without it.
"""
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import gold3_totalseg_grid as tool  # noqa: E402

try:
    import numpy as np
except ImportError:                                             # pragma: no cover
    np = None


class Studies(unittest.TestCase):
    def test_the_committed_admission_asks_for_c2_or_the_sacrum_where_its_completion_lists_them(self):
        asked = tool.studies_asked(ROOT / "data" / "gold3-ct" / "admission.json")
        by_member = {}
        for study in asked:
            by_member[study["member"]] = by_member.get(study["member"], 0) + 1
            self.assertTrue(set(study["targets"]) <= {"C2", "sacrum"}, study)
            self.assertIn(study["verdict"], ("admitted", "look"))
            for target in study["targets"]:
                self.assertIn(target, study["complete"])
        # VerSe never draws the sacrum, so every admitted or held series asks for it; the ten
        # TotalSegmentator subjects and ENHANCE.PET's 1379 ask for what their releases left out.
        self.assertEqual(by_member, {"verse": 27, "totalsegmentator": 10, "enhance_pet": 1}, by_member)
        self.assertEqual([s["id"] for s in asked if s["member"] == "enhance_pet"], ["1379"])
        # each release's own segmenter draws for it (the owner, 2026-10-30 09:33 UTC)
        self.assertEqual({s["member"]: s["segmenter"] for s in asked},
                         {"verse": "TotalSegmentator", "totalsegmentator": "TotalSegmentator", "enhance_pet": "MOOSE"})

    def test_mooses_ids_are_the_buckets_and_the_segmenter_tables_and_the_release_ids_are_each_schemes(self):
        # the ids run cuts MOOSE's multilabel by, and writes ENHANCE.PET's arm files at, are the
        # vertebrae model's in the bucket's labels.json copy (read leniently: the copy carries a
        # trailing comma) and in schwingnet.segmenters' table
        text = (ROOT / "grid" / "enhance-pet-labels.json").read_text(encoding="utf-8")
        bucket = json.loads(re.sub(r",(\s*[}\]])", r"\1", text))["clin_ct_vertebrae"]
        for target, value in tool.MOOSE_IDS.items():
            self.assertEqual(bucket[str(value)], tool.MOOSE_NAMES[target], (target, value))
        sys.path.insert(0, str(ROOT / "src"))
        try:
            from schwingnet import segmenters
        except ImportError:
            segmenters = None
        if segmenters is not None:
            table = segmenters.MOOSEZ_MODELS["clin_ct_vertebrae"]
            for target, value in tool.MOOSE_IDS.items():
                self.assertEqual(table[value], tool.MOOSE_NAMES[target])
            self.assertEqual(segmenters.VERSE_IDS["C2"] if hasattr(segmenters, "VERSE_IDS") else 2, 2)
        self.assertEqual(tool.RELEASE_IDS["verse"], {"C2": 2, "sacrum": 26})
        self.assertEqual(tool.RELEASE_IDS["enhance_pet"], tool.MOOSE_IDS)
        self.assertEqual(tool.RELEASE_IDS["totalsegmentator"], {"C2": 1, "sacrum": 1})

    def test_a_study_that_asks_for_other_levels_alone_or_is_not_admitted_is_left_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "admission.json"
            path.write_text(json.dumps({"studies": [
                {"member": "verse", "id": "a", "verdict": "admitted", "complete": ["L5"]},
                {"member": "verse", "id": "b", "verdict": "not_admitted", "complete": ["sacrum"]},
                {"member": "verse", "id": "c", "verdict": "look", "complete": ["C2", "C3"]},
                {"member": "verse", "id": "d", "verdict": "admitted"},
            ]}), encoding="utf-8")
            asked = tool.studies_asked(path)
        self.assertEqual([(s["id"], s["targets"]) for s in asked], [("c", ["C2"])])


class Locate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        tool._TS_FOLDERS.clear()
        tool._FILES.clear()

    def touch(self, *parts):
        path = self.tmp.joinpath(*parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
        return str(path)

    def test_each_member_is_found_where_its_release_lies_and_refused_with_a_reason_otherwise(self):
        ts_root = self.tmp / "totalsegmentator_v300"
        nested_ct = self.touch("totalsegmentator_v300", "Totalsegmentator_dataset_v201", "s0102", "ct.nii.gz")
        self.touch("totalsegmentator_v300", "Totalsegmentator_dataset_v201", "s0102", "segmentations", "vertebrae_L1.nii.gz")
        self.touch("totalsegmentator_v300", "s0437", "ct.nii.gz")
        verse_ct = self.touch("verse", "scan-verse607_ct.nii.gz")
        verse_masks = self.tmp / "verse_masks_2026_10_29" / "masks"
        self.touch("verse_masks_2026_10_29", "masks", "verse607.nii.gz")
        enhance_ct = self.tmp / "aws_enhance_pet_ct" / "raw"
        enhance_labels = self.tmp / "aws_enhance_pet_labels" / "raw"
        self.touch("aws_enhance_pet_ct", "raw", "autopet", "1379.nii.gz")
        self.touch("aws_enhance_pet_labels", "raw", "autopet", "Ribs", "1379.nii.gz")
        self.touch("aws_enhance_pet_labels", "raw", "autopet", "Vertebrae", "1379.nii.gz")
        args = (str(ts_root), str(enhance_ct), str(enhance_labels), str(verse_masks))
        cts = {"verse607": verse_ct}

        ct, release, why = tool.locate({"member": "totalsegmentator", "id": "s0102"}, cts, *args)
        self.assertIsNone(why)
        self.assertEqual(ct, nested_ct)
        self.assertTrue(release.endswith(os.path.join("s0102", "segmentations")))
        ct, release, why = tool.locate({"member": "totalsegmentator", "id": "s0437"}, cts, *args)
        self.assertIn("no segmentations/ folder", why)
        ct, release, why = tool.locate({"member": "totalsegmentator", "id": "s9999"}, cts, *args)
        self.assertIn("no folder of the subject's name", why)

        ct, release, why = tool.locate({"member": "verse", "id": "verse607"}, cts, *args)
        self.assertIsNone(why)
        self.assertEqual((ct, Path(release).name), (verse_ct, "verse607.nii.gz"))
        ct, release, why = tool.locate({"member": "verse", "id": "verse999"}, cts, *args)
        self.assertIn("no census row", why)
        cts["verse608"] = verse_ct
        ct, release, why = tool.locate({"member": "verse", "id": "verse608"}, cts, *args)
        self.assertIn("no int16 copy", why)

        ct, release, why = tool.locate({"member": "enhance_pet", "id": "1379"}, cts, *args)
        self.assertIsNone(why)
        self.assertEqual(Path(release).parent.name, "Vertebrae")
        ct, release, why = tool.locate({"member": "enhance_pet", "id": "1"}, cts, *args)
        self.assertIn("no CT of the study's id", why)

    def test_enhance_pets_vertebrae_file_is_found_whichever_label_folder_the_walk_lists_first(self):
        # the ground truth is seven folders of label maps, each with a file of the study's name: the
        # first job took the first file of the name alone and left 1379 out
        self.touch("aws_enhance_pet_ct", "raw", "CT", "1379.nii.gz")
        for folder in ("Peripheral-Bones", "Ribs", "Vertebrae"):
            self.touch("aws_enhance_pet_labels", "raw", folder, "1379.nii.gz")
        args = (str(self.tmp / "none"), str(self.tmp / "aws_enhance_pet_ct" / "raw"),
                str(self.tmp / "aws_enhance_pet_labels" / "raw"), str(self.tmp / "none"))
        for reverse in (False, True):
            tool._FILES.clear()
            with mock.patch.object(tool.os, "walk", walk_sorted(reverse)):
                ct, release, why = tool.locate({"member": "enhance_pet", "id": "1379"}, {}, *args)
            self.assertIsNone(why, reverse)
            self.assertEqual((Path(ct).parent.name, Path(release).parent.name), ("CT", "Vertebrae"))
        self.touch("aws_enhance_pet_labels", "raw", "Ribs", "1380.nii.gz")
        self.touch("aws_enhance_pet_ct", "raw", "CT", "1380.nii.gz")
        tool._FILES.clear()
        ct, release, why = tool.locate({"member": "enhance_pet", "id": "1380"}, {}, *args)
        self.assertIn("no Vertebrae mask", why)

    def test_prepare_writes_jobs_json_with_store_names_and_no_data_root_path_in_its_summary(self):
        self.touch("totalsegmentator_v300", "s0102", "ct.nii.gz")
        self.touch("totalsegmentator_v300", "s0102", "segmentations", "vertebrae_L1.nii.gz")
        admission = self.tmp / "admission.json"
        admission.write_text(json.dumps({"studies": [
            {"member": "totalsegmentator", "id": "s0102", "verdict": "admitted", "complete": ["C2", "sacrum"]},
            {"member": "totalsegmentator", "id": "s0437", "verdict": "look", "complete": ["sacrum"]},
        ]}), encoding="utf-8")
        out = self.tmp / "out"
        args = types.SimpleNamespace(admission=str(admission), tiers="", ts_root=str(self.tmp / "totalsegmentator_v300"),
                                     enhance_ct=str(self.tmp / "none"), enhance_labels=str(self.tmp / "none"),
                                     verse_masks=str(self.tmp / "verse_masks_2026_10_29" / "masks"), out=str(out))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(tool.prepare(args), 0)
        jobs = json.loads((out / "jobs.json").read_text(encoding="utf-8"))
        self.assertEqual((jobs["asked"], jobs["prepared"], jobs["not_prepared"]), (2, 1, 1))
        self.assertEqual(jobs["studies"][0]["ct_store"], "totalsegmentator_v300")
        self.assertEqual(jobs["studies"][0]["targets"], ["C2", "sacrum"])
        self.assertEqual(jobs["left_out"][0]["id"], "s0437")
        self.assertEqual(jobs["segmenter"], "TotalSegmentator")
        self.assertEqual(jobs["task"]["roi_subset"], ["vertebrae_C2", "sacrum", "vertebrae_S1"])
        self.assertEqual(jobs["studies"][0]["segmenter"], "TotalSegmentator")
        # the report, with nothing run yet, lists the prepared study as not run and names no path
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(tool.report(types.SimpleNamespace(out=str(out))), 0)
        text = (out / "REPORT.md").read_text(encoding="utf-8")
        self.assertIn("studies asked: 2 (totalsegmentator 2); prepared: 1; not prepared: 1", text)
        self.assertIn("| s0102 | totalsegmentator | TotalSegmentator | totalsegmentator_v300 | C2 sacrum | - | - | not run |", text)
        self.assertIn("| s0437 | totalsegmentator | TotalSegmentator | - | sacrum | - | - | not prepared |", text)
        self.assertIn("- s0437 (totalsegmentator): no folder of the subject's name", text)
        self.assertNotIn(str(self.tmp), text)


def walk_sorted(reverse):
    """os.walk with each folder's subfolders visited in name order, or in its reverse."""
    walk = os.walk

    def ordered(top, *rest, **words):
        for folder, dirs, files in walk(top, *rest, **words):
            dirs.sort(reverse=reverse)
            yield folder, dirs, files
    return ordered


def study(sid, root):
    return {"member": "totalsegmentator", "id": sid, "verdict": "admitted", "targets": ["C2", "sacrum"], "complete": ["C2", "sacrum"],
            "segmenter": "TotalSegmentator", "ct": str(root / sid / "ct.nii.gz"), "release": str(root / sid / "segmentations"),
            "ct_store": "totalsegmentator_v300", "release_store": "totalsegmentator_v300"}


class Run(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))

    def record(self, sid, text):
        folder = self.tmp / "ts" / sid
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "run.json").write_text(text, encoding="utf-8")

    def test_a_study_whose_run_failed_is_run_again_and_one_that_ended_0_is_not(self):
        # the first job's 37 failed run.json files must not stop the rerun from drawing them
        ids = ("s0102", "s0437", "s0621", "s0931")
        (self.tmp / "jobs.json").write_text(json.dumps({"studies": [study(sid, self.tmp) for sid in ids], "left_out": []}),
                                            encoding="utf-8")
        self.record("s0102", json.dumps({"id": "s0102", "exit": 0}))
        self.record("s0437", json.dumps({"id": "s0437", "exit": 1, "error": "AttributeError: module 'profile' has no attribute 'run'"}))
        self.record("s0931", "not json")
        drawn = []

        def draw(found, folder, args):
            drawn.append(found["id"])
            for name in tool.TASK["roi_subset"]:
                Path(folder, name + ".nii.gz").write_bytes(b"x")
            return {}

        args = types.SimpleNamespace(out=str(self.tmp), weights="", device="cpu", threads=1)
        with mock.patch.object(tool, "run_totalseg", draw), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(tool.run(args), 0)
        self.assertEqual(drawn, ["s0437", "s0621", "s0931"])
        for sid in drawn:
            ran = json.loads((self.tmp / "ts" / sid / "run.json").read_text(encoding="utf-8"))
            self.assertEqual((ran["exit"], ran["files"]), (0, ["sacrum.nii.gz", "vertebrae_C2.nii.gz", "vertebrae_S1.nii.gz"]), ran)
            self.assertNotIn("error", ran)
        self.assertEqual(json.loads((self.tmp / "ts" / "s0102" / "run.json").read_text(encoding="utf-8")), {"id": "s0102", "exit": 0})

    def test_run_as_the_job_runs_it_the_segmenters_imports_reach_the_standard_librarys_profile(self):
        # the first job (40882547) failed on every study it ran: started as a script, the tool had tools/
        # first on sys.path, so the cProfile that the segmenter's imports reach found tools/profile.py
        site = self.tmp / "site" / "totalsegmentator"
        site.mkdir(parents=True)
        (site / "__init__.py").write_text("", encoding="utf-8")
        (site / "python_api.py").write_text(
            "import cProfile  # as torch's imports reach it\n"
            "import os\n\n\n"
            "def download_pretrained_weights(part):  # bound here as 2.18.0 binds it\n"
            "    raise RuntimeError('downloaded')\n\n\n"
            "def totalsegmentator(ct, folder, **words):\n"
            "    for name in words['roi_subset']:\n"
            "        open(os.path.join(folder, name + '.nii.gz'), 'wb').close()\n", encoding="utf-8")
        (self.tmp / "jobs.json").write_text(json.dumps({"studies": [study("s0102", self.tmp)], "left_out": []}), encoding="utf-8")
        env = dict(os.environ, PYTHONPATH=str(self.tmp / "site"), PYTHONNOUSERSITE="1")
        said = subprocess.run([sys.executable, str(ROOT / "tools" / "gold3_totalseg_grid.py"), "run", "--out", str(self.tmp), "--device", "cpu"],
                              capture_output=True, text=True, env=env, cwd=str(ROOT), timeout=120)
        ran = json.loads((self.tmp / "ts" / "s0102" / "run.json").read_text(encoding="utf-8"))
        self.assertEqual(said.returncode, 0, said.stdout + said.stderr)
        self.assertEqual((ran["exit"], ran["files"]), (0, ["sacrum.nii.gz", "vertebrae_C2.nii.gz", "vertebrae_S1.nii.gz"]), ran)


class Weights(unittest.TestCase):
    """TotalSegmentator 2.18.0 asks for every part of the total task before it applies roi_subset; the
    job holds 292 and 298 alone, so the guard must pass over 291, 293, 294 and 295 and refuse the rest."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.weights = self.tmp / "weights"
        for name in ("Dataset292_TotalSegmentator_part2_vertebrae_1559subj", "Dataset298_TotalSegmentator_total_6mm_1559subj"):
            (self.weights / name).mkdir(parents=True)
        self.downloaded = []
        api = types.ModuleType("totalsegmentator.python_api")
        exec("def download_pretrained_weights(part):\n    DOWNLOADED.append(part)\n\n"
             "def totalsegmentator(ct, folder, **words):\n"
             "    for part in (291, 292, 293, 294, 295, *PARTS):\n"
             "        download_pretrained_weights(part)\n", api.__dict__)
        api.DOWNLOADED, api.PARTS = self.downloaded, []
        self.api = api
        package = types.ModuleType("totalsegmentator")
        package.python_api = api
        patched = mock.patch.dict(sys.modules, {"totalsegmentator": package, "totalsegmentator.python_api": api})
        patched.start()
        self.addCleanup(patched.stop)

    def draw(self):
        args = types.SimpleNamespace(weights=str(self.weights), device="gpu", threads=1)
        return tool.run_totalseg({"ct": "ct.nii.gz"}, str(self.tmp), args)

    def test_the_parts_this_roi_subset_never_computes_are_passed_over_and_nothing_is_downloaded(self):
        held = self.api.download_pretrained_weights
        self.assertEqual(self.draw(), {})
        self.assertEqual(self.downloaded, [])
        self.assertIs(self.api.download_pretrained_weights, held, "the guard is taken off after the run")
        guard = tool.weights_guard(str(self.weights))
        self.assertIsNone(guard(task_id=293))
        with self.assertRaisesRegex(RuntimeError, "weight part 297"):
            guard(task_id=297)

    def test_a_part_the_folder_lacks_that_the_run_needs_is_refused(self):
        __import__("shutil").rmtree(self.weights / "Dataset292_TotalSegmentator_part2_vertebrae_1559subj")
        with self.assertRaisesRegex(RuntimeError, "weight part 292"):
            self.draw()
        self.api.PARTS.append(297)
        (self.weights / "Dataset292_x").mkdir()
        with self.assertRaisesRegex(RuntimeError, "weight part 297"):
            self.draw()
        self.assertEqual(self.downloaded, [])


class MooseOne(unittest.TestCase):
    """moose-one inside MOOSE's environment, with moosez and the render tool's helpers stubbed."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        (self.tmp / "zips").mkdir()
        (self.tmp / "zips" / "vertebrae.zip").write_bytes(b"z")
        (self.tmp / "ct.nii.gz").write_bytes(b"ct")
        self.devices = []
        fr = types.ModuleType("flexray_render")
        fr.moosez_metadata = lambda: {tool.MOOSE_MODEL: ("Dataset_vertebrae", "https://x/vertebrae.zip")}
        fr.zip_of = lambda url: url.rsplit("/", 1)[-1]
        fr.moosez_disagreements = lambda metadata: []
        fr.models_directory = lambda: str(self.tmp / "models")
        fr.unpack_weights = lambda weights, metadata, models: []
        fr.check_labels = lambda models, metadata: {}
        fr.dataset_labels = lambda models, folder: ({2: "vertebra_C2", 28: "sacrum"}, None)
        moosez = types.ModuleType("moosez")

        def moose(ct, models, out, device):
            import torch_stand_in
            torch_stand_in.device(device)
            self.devices.append(device)
            written = Path(out) / "moosez-out" / "CT_vertebrae_multilabel.nii.gz"
            written.parent.mkdir(exist_ok=True)
            written.write_bytes(b"m")
        moosez.moose = moose
        torch = types.ModuleType("torch_stand_in")

        def device(word):
            if word.split(":")[0] not in ("cpu", "cuda", "mps"):
                raise RuntimeError(f"Expected one of cpu, cuda, ... device type at start of device string: {word}")
        torch.device = device
        patched = mock.patch.dict(sys.modules, {"flexray_render": fr, "moosez": moosez, "torch_stand_in": torch})
        patched.start()
        self.addCleanup(patched.stop)
        self.held_path = list(sys.path)
        self.addCleanup(lambda: sys.path.__setitem__(slice(None), self.held_path))

    def one(self, device):
        args = types.SimpleNamespace(ct=str(self.tmp / "ct.nii.gz"), folder=str(self.tmp / "ts" / "1379"),
                                     weights=str(self.tmp / "zips"), device=device)
        said = io.StringIO()
        with contextlib.redirect_stdout(said):
            self.assertEqual(tool.moose_one(args), 0)
        return json.loads(said.getvalue().splitlines()[-1])

    def test_the_gpu_word_reaches_moose_as_cuda_and_moose_ones_own_default_is_cuda(self):
        self.one("gpu")
        self.one("gpu:1")
        self.assertEqual(self.devices, ["cuda", "cuda:1"])
        parser_default = [line for line in Path(tool.__file__).read_text(encoding="utf-8").splitlines()
                          if '"--device", default="cuda"' in line]
        self.assertEqual(len(parser_default), 1)
        self.assertEqual(tool.torch_device("cpu"), "cpu")

    def test_a_study_whose_earlier_attempt_wrote_the_multilabel_file_is_drawn_again(self):
        first = self.one("gpu")
        # the outer run cuts its targets beside it, then a later fault fails the study, and it runs again
        Path(self.tmp / "ts" / "1379" / "vertebrae_C2.nii.gz").write_bytes(b"cut")
        again = self.one("gpu")
        self.assertEqual(first["multilabel"], again["multilabel"])
        self.assertTrue(again["multilabel"].endswith("CT_vertebrae_multilabel.nii.gz"))
        self.assertEqual(len(self.devices), 2)


class FakeImage:
    def __init__(self, data, affine):
        self.dataobj = data
        self.affine = affine


def stub_nibabel(images):
    """A nibabel whose load gives the image a test placed under the path."""
    module = types.ModuleType("nibabel")
    module.load = lambda path: images[str(path)]
    return module


@unittest.skipIf(np is None, "numpy is needed to draw the masks")
class Check(unittest.TestCase):
    """The release's levels are stacked along the world's vertical: labels 1..3 at z 0 to 30 mm
    (index k 0 to 29, 1 mm voxels), so a C2 drawn above and a sacrum drawn below are kept."""

    def setUp(self):
        self.had = sys.modules.get("nibabel")
        self.images = {}
        if self.had is None:
            sys.modules["nibabel"] = stub_nibabel(self.images)
        else:                                                   # pragma: no cover
            self.skipTest("nibabel is installed; these tests exercise the stub path on numpy alone")
        self.addCleanup(self.restore)
        self.affine = np.eye(4)
        self.release = np.zeros((4, 4, 60), dtype=np.int16)
        self.release[:, :, 0:10] = 3
        self.release[:, :, 10:20] = 2
        self.release[:, :, 20:30] = 1
        self.images["release"] = FakeImage(self.release, self.affine)

    def restore(self):
        if self.had is None:
            sys.modules.pop("nibabel", None)

    def mask(self, name, lo, hi, affine=None, shape=(4, 4, 60)):
        data = np.zeros(shape, dtype=np.uint8)
        data[:, :, lo:hi] = 1
        self.images[name] = FakeImage(data, self.affine if affine is None else affine)
        return name

    def test_a_c2_above_the_topmost_level_and_a_sacrum_below_the_lowest_are_kept_with_their_gaps(self):
        levels, affine = tool.release_levels("release")
        self.assertEqual([n for n, _ in levels], ["label 1", "label 2", "label 3"])
        c2 = tool.check_target("C2", self.mask("c2", 34, 50), levels, affine, ["C2", "C3", "sacrum"])
        self.assertTrue(c2["kept"], c2)
        self.assertEqual((c2["nearest_release_level"], c2["gap_mm"], c2["undrawn_between"]), ("label 1", 5.0, ["C3"]))
        self.assertEqual(c2["voxels"], 16 * 16)
        sacrum = tool.check_target("sacrum", self.mask("sacrum", 0, 0), levels, affine, ["sacrum"])
        self.assertFalse(sacrum["kept"])
        self.assertIn("under 200", sacrum["reason"])

    def test_a_target_on_the_releases_own_levels_or_on_the_wrong_side_is_refused(self):
        levels, affine = tool.release_levels("release")
        over = tool.check_target("sacrum", self.mask("over", 5, 25), levels, affine, ["sacrum"])
        self.assertFalse(over["kept"])
        self.assertIn("lie on the release's own levels", over["reason"])
        # a sacrum drawn clear of the levels but above them all is on the wrong side
        above = tool.check_target("sacrum", self.mask("above", 40, 55), levels, affine, ["sacrum"])
        self.assertFalse(above["kept"])
        self.assertIn("wrong side", above["reason"])
        self.assertIn("lowest", above["reason"])
        # the sacrum's side reads from the affine, not the index: flipped, index 40..55 lies below
        flipped = np.diag([1.0, 1.0, -1.0, 1.0])
        levels_flipped = [(n, m) for n, m in levels]
        below = tool.check_target("sacrum", self.mask("below", 40, 55, affine=flipped), levels_flipped, flipped, ["sacrum"])
        self.assertTrue(below["kept"], below)

    def test_a_mask_off_the_releases_grid_is_refused_before_any_overlap_is_read(self):
        levels, affine = tool.release_levels("release")
        other = tool.check_target("C2", self.mask("other", 34, 50, shape=(4, 4, 61)), levels, affine, ["C2"])
        self.assertFalse(other["kept"])
        self.assertIn("not the release masks' grid", other["reason"])
        moved = np.eye(4)
        moved[0, 3] = 2.0
        shifted = tool.check_target("C2", self.mask("shifted", 34, 50, affine=moved), levels, affine, ["C2"])
        self.assertIn("not the release masks' grid", shifted["reason"])


    def test_a_sacrum_is_totalsegmentators_sacrum_and_s1_together(self):
        # one full sacrum mask, never a separate S1 class (the owner, 22:58 UTC; DEVIATIONS.md item 2)
        flipped = np.diag([1.0, 1.0, -1.0, 1.0])
        levels, _ = tool.release_levels("release")
        sacrum, s1 = self.mask("sac", 48, 55, affine=flipped), self.mask("s1", 40, 47, affine=flipped)
        alone = tool.check_target("sacrum", sacrum, levels, flipped, ["sacrum"])
        self.assertFalse(alone["kept"])
        self.assertIn("112 voxels", alone["reason"])
        both = tool.check_target("sacrum", [sacrum, s1], levels, flipped, ["sacrum"])
        self.assertTrue(both["kept"], both)
        self.assertEqual(both["voxels"], 224)
        self.mask("s1_off", 40, 47, affine=np.eye(4))
        with self.assertRaisesRegex(ValueError, "not on"):
            tool.read_union([sacrum, "s1_off"])

    def test_every_sacrum_totalsegmentator_draws_takes_its_s1(self):
        names = lambda *a: [os.path.basename(p) for p in tool.target_files("f", *a)]  # noqa: E731
        self.assertEqual(names("sacrum", "verse", "TotalSegmentator"), ["sacrum.nii.gz", "vertebrae_S1.nii.gz"])
        self.assertEqual(names("sacrum", "totalsegmentator", "TotalSegmentator"), ["sacrum.nii.gz", "vertebrae_S1.nii.gz"])
        self.assertEqual(names("sacrum", "enhance_pet", "MOOSE"), ["sacrum.nii.gz"])
        self.assertEqual(names("C2", "verse", "TotalSegmentator"), ["vertebrae_C2.nii.gz"])

    def test_a_totalsegmentator_releases_s1_is_read_as_part_of_its_sacrum(self):
        with tempfile.TemporaryDirectory() as folder:
            for name, lo, hi in (("vertebrae_L5", 20, 30), ("vertebrae_S1", 10, 20), ("sacrum", 0, 10), ("vertebrae_L4", 0, 0)):
                Path(folder, name + ".nii.gz").write_bytes(b"")
                self.mask(os.path.join(folder, name + ".nii.gz"), lo, hi)
            levels, _ = tool.release_levels(folder)
        names = dict(levels)
        self.assertEqual(sorted(names), ["sacrum", "vertebrae_L5"])
        self.assertEqual(int(names["sacrum"].sum()), 16 * 20)

    def test_a_refusal_names_the_segmenter_that_drew_the_target(self):
        levels, affine = tool.release_levels("release")
        few = tool.check_target("C2", self.mask("few", 0, 0), levels, affine, ["C2"], "MOOSE")
        self.assertIn("MOOSE drew 0 voxels", few["reason"])
        self.assertNotIn("TotalSegmentator", few["reason"])


class Report(unittest.TestCase):
    def test_the_report_counts_kept_and_refused_targets_and_cuts_every_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "jobs.json").write_text(json.dumps({
                "asked": 3, "prepared": 2, "not_prepared": 1,
                "studies": [{"member": "verse", "id": "verse607", "verdict": "admitted", "targets": ["sacrum"], "complete": ["sacrum"],
                             "segmenter": "TotalSegmentator", "ct": "/x", "release": "/y", "ct_store": "versefusion", "release_store": "verse_masks_2026_10_29"},
                            {"member": "totalsegmentator", "id": "s0102", "verdict": "look", "targets": ["C2", "sacrum"], "segmenter": "TotalSegmentator",
                             "complete": ["C2", "sacrum"], "ct": "/x", "release": "/y", "ct_store": "totalsegmentator_v300",
                             "release_store": "totalsegmentator_v300"},
                            {"member": "enhance_pet", "id": "1380", "verdict": "admitted", "targets": ["C2"], "segmenter": "MOOSE",
                             "complete": ["C2"], "ct": "/x", "release": "/y", "ct_store": "aws_enhance_pet_ct", "release_store": "aws_enhance_pet_labels"}],
                "left_out": [{"member": "enhance_pet", "id": "1379", "targets": ["C2"], "reason": "no CT of the study's id under aws_enhance_pet_ct"}],
            }), encoding="utf-8")
            records = [
                {"id": "verse607", "member": "verse", "ct_store": "versefusion", "version": "2.18.0", "segmenter": "TotalSegmentator", "label_scheme": "VerSe label ids",
                 "targets": {"sacrum": {"kept": True, "voxels": 5000, "gap_mm": 3.2, "nearest_release_level": "label 24", "label_value": 26,
                                        "undrawn_between": [], "file": "verse607_totalsegmentator_sacrum_abc123def456.nii.gz"}}},
                {"id": "s0102", "member": "totalsegmentator", "ct_store": "totalsegmentator_v300", "version": "2.18.0", "segmenter": "TotalSegmentator",
                 "targets": {"C2": {"kept": False, "reason": "x" * 300}, "sacrum": {"kept": False, "reason": "TotalSegmentator wrote no file for it"}}},
                {"id": "1380", "member": "enhance_pet", "ct_store": "aws_enhance_pet_ct", "version": "3.2.2", "segmenter": "MOOSE",
                 "error": "moose-one ended 1: no zip"},
            ]
            (out / "records.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(tool.report(types.SimpleNamespace(out=str(out))), 0)
            text = (out / "REPORT.md").read_text(encoding="utf-8")
        self.assertIn("studies asked: 3 (enhance_pet 2, totalsegmentator 1, verse 1); prepared: 2; not prepared: 1", text)
        self.assertIn("segmenters: TotalSegmentator 2.18.0 (task total, roi_subset vertebrae_C2 sacrum vertebrae_S1) for verse, totalsegmentator; MOOSE 3.2.2 (clin_ct_vertebrae) for enhance_pet", text)
        self.assertIn("targets kept: 1 (0 C2, 1 sacrum) in 1 studies; targets refused: 2; studies in error: 1", text)
        self.assertIn("| verse607 | verse | TotalSegmentator | versefusion | sacrum | - | kept | verse607_totalsegmentator_sacrum_abc123def456.nii.gz |", text)
        self.assertIn("| s0102 | totalsegmentator | TotalSegmentator | totalsegmentator_v300 | C2 sacrum | refused | refused | - |", text)
        self.assertIn("| 1380 | enhance_pet | MOOSE | aws_enhance_pet_ct | - | - | - | error |", text)
        self.assertIn("- verse607 sacrum: 5000 voxels, gap 3.2 mm to label 24, undrawn between: none; written at id 26 (VerSe label ids)", text)
        self.assertIn("- 1380: moose-one ended 1: no zip", text)
        self.assertIn("- s0102 C2: " + "x" * 157 + "...", text)
        self.assertIn("- 1379 (enhance_pet): no CT of the study's id", text)
        self.assertNotIn("/x", text)


if __name__ == "__main__":
    unittest.main()
