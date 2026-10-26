"""tools/flexray_render.py and tools/render_blocks.py on a made-up CT corpus of seven subjects,
one nested: CTs of soft tissue with bone cubes, each labelled as SPINEPS writes its masks (one
*_seg-vert_msk.nii.gz in the VerSe alphabet, in a sibling spineps folder, a mask of another
shape, one of the CT's shape placed elsewhere and a decoy among them) and as moosez's command line
writes its outputs (one multilabel file a model under a stamped moosez-* folder's segmentations/
below moose/<subject>/), rendered on the CPU at a 32-pixel detector and 64 ray samples by the
blocks engine and, where FleXray's runtime imports, by FleXray's own code. It checks both
locators, both label volumes (L6 present and recorded as dropped, T13 and the coccyx unsupervised
under SPINEPS, rib 13 dropped and the trachea unsupervised under MOOSE), both engines under each
segmenter, the raw FluXray recipe's fixed poses, the layout, the reuse, the seeds shared between
render groups, the refusals, and the segment subcommand's plan, its refusals (a zip missing or a
part, a model whose dataset.json names a label otherwise), its runs with moosez kept out or stood
in for in the layout its library entry writes (clin_CT_<region>_segmentation_CT_<id>.nii.gz
beside the CT link) and in its command line's, and the one line a run ends with; and the
arithmetic held equal to FleXray's (the crop plan at both overlaps, the crop weights, the crop
draw, the crop records, the scaling, the label table) where fxr is installed.
tests/schwingnet/test_render_blocks.py and test_segmenters.py hold the pure rules without it.

It needs numpy, torch, nibabel, Pillow, fxr (flexray from pip) and the package's contract
libraries, which the job's environment holds and the required check's python does not, so each
case runs where they import and is skipped elsewhere; the cases of FleXray's own runtime need
kornia too, which fxr.models.camera imports for its label smoothing, and are skipped without it.
Nothing else skips: moosez is never needed, since the grid's job environment is the only one that
holds it.

    <venv>/bin/python -m unittest tests.test_flexray_render
"""

import importlib
import importlib.machinery
import importlib.util
import io
import itertools
import json
import shutil
import sys
import tempfile
import types
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
NEEDED = ("numpy", "torch", "nibabel", "PIL", "fxr", "beartype", "icontract", "pydantic")
MISSING = [name for name in NEEDED if importlib.util.find_spec(name) is None]
SALT = "c"  # under this salt two of the six views open FleXray's attenuation gate
SMALL = ["views=2", "detector=32", "ray_samples=64"]
# The subjects the render cases name, in this order; s0006 is left to the locator cases.
ALL = ("s0001", "batch/s0002", "s0003", "s0004", "s0005")
SIDE = 64
MAIN = (slice(24, 40), slice(24, 40))
SIDE_COLUMN = (slice(8, 20), slice(8, 20))
OTHER_GRID = (32, 32, 150)
TOOLS = {}

# What the label records of s0001 must say under each scheme (tools/render_blocks.py,
# label_record): MOOSE's stored ids, FleXray's dropped names, the values left out, the names the
# files could have carried and did not (absent), and the order the files were written in.
SPINEPS_S0001 = {
    "scheme": "spineps", "files": {"spineps": "s0001_seg-vert_msk.nii.gz"},
    "precedence": ["spineps"], "skipped": [],
    "labels": {"81": "vertebra_l4", "82": "vertebra_l5", "83": "vertebra_l6", "86": "sacrum"},
    "dropped": ["vertebra_l6"],
    "absent": [f"vertebra_c{n}" for n in range(1, 8)] + [f"vertebra_t{n}" for n in range(1, 13)]
              + ["vertebra_l1", "vertebra_l2", "vertebra_l3"],
    "unsupervised": {"27": "coccyx", "28": "vertebra_t13"}, "models_missing": [], "unplaced": [],
}
MODELS = ("clin_ct_organs", "clin_ct_cardiac", "clin_ct_peripheral_bones", "clin_ct_ribs",
          "clin_ct_vertebrae")
MOOSE_FILES = {model: f"clin_CT_{model.split('_', 2)[2]}_CT_s0001.nii.gz" for model in MODELS}
# A model's configuration folder, trainer__planner__resolution, the one moosez reads dataset.json
# and plans.json from (moosez/models.py, Model.__get_configuration_folders).
CONFIG = "nnUNetTrainer__nnUNetPlans__3d_fullres"
RESEND = "resend fetch moose_weights, which resumes it"
MOOSE_S0001 = {
    "scheme": "moose", "files": MOOSE_FILES, "precedence": list(MODELS), "skipped": [],
    "labels": {"32": "rib_left_1", "44": "rib_left_13", "81": "vertebra_l4", "82": "vertebra_l5",
               "83": "vertebra_l6", "86": "sacrum", "94": "liver"},
    "dropped": ["rib_left_13", "vertebra_l6"],
    "absent": None,  # moose_s0001() fills it from the tables; the Tables case pins what it holds
    "unsupervised": {"clin_ct_organs:19": "trachea"},
    "models_missing": [], "unplaced": [],
}


def moose_absent(present_ids):
    """The absent list of a record read from all five models: every name their tables land on,
    less the ids present and the names FleXray drops, in MOOSE's id order."""
    segmenters = load_tool("render_blocks").segmenters
    reachable = {i for m in MODELS for i in segmenters.moosez_to_moose_ids(m).values()}
    return [segmenters.MOOSE_STORED[i] for i in sorted(reachable - set(present_ids))
            if segmenters.MOOSE_STORED[i] not in segmenters.MOOSE_DROPPED]


def moose_s0001():
    return {**MOOSE_S0001, "absent": moose_absent(int(i) for i in MOOSE_S0001["labels"])}


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


# --- the corpus -----------------------------------------------------------------------------------

def affine_for(depth):
    """3 mm in plane and 1.5 mm along the slices, the volume centred on the origin."""
    import numpy as np

    affine = np.diag([3.0, 3.0, 1.5, 1.0])
    affine[:3, 3] = [-96.0, -96.0, -0.75 * depth]
    return affine


def shifted_affine(depth):
    """The same voxel grid placed 10 mm to one side: another grid though the shape is the CT's."""
    affine = affine_for(depth)
    affine[0, 3] += 10.0
    return affine


def grid_for(depth):
    """The CT's grid as the locators and the label builders take it: its shape and its affine."""
    return (SIDE, SIDE, depth), affine_for(depth)


def write_nifti(path, array, affine):
    import nibabel

    path.parent.mkdir(parents=True, exist_ok=True)
    nibabel.save(nibabel.Nifti1Image(array, affine), str(path))


def cubes_volume(depth, cubes, shape=None):
    """A volume of the cubes, each (value, first slice, last slice, column) written in order,
    int16 as the segmenters write their masks."""
    import numpy as np

    volume = np.zeros(shape or (SIDE, SIDE, depth), dtype=np.int16)
    for value, first, last, column in cubes:
        volume[column[0], column[1], first:last] = value
    return volume


def write_mask(path, depth, cubes, shape=None, affine=None):
    """One mask of the cubes on the CT's grid, or on another grid when a shape or an affine is
    given."""
    write_nifti(path, cubes_volume(depth, cubes, shape),
                affine_for(depth) if affine is None else affine)


def write_ct(folder, depth, cubes):
    """A CT of 64 x 64 x depth voxels, soft tissue throughout so that every ray through it adds
    up, bone where the cubes are."""
    import numpy as np

    ct = np.full((SIDE, SIDE, depth), 40.0, dtype=np.float32)
    for _, first, last, column in cubes:
        ct[column[0], column[1], first:last] = 800.0
    write_nifti(folder / "ct.nii.gz", ct, affine_for(depth))


def moose_file(root, subject, model, stamp="20260101", suffix=""):
    """Where moosez writes a model's multilabel file for a subject, by its output folder
    moosez-<model>-<stamp>/segmentations/ and a file name carrying the model's region."""
    name = subject.rsplit("/", 1)[-1]
    region = model.split("_", 2)[2]
    return (root / subject / f"moosez-{model}-{stamp}" / "segmentations"
            / f"clin_CT_{region}_CT_{name}{suffix}.nii.gz")


def make_s0001(ct, spineps, moose):
    """300 slices (two crops at overlap 0, five at 0.5): L4, L5, L6 and the sacrum in both
    schemes; T13 and the coccyx under SPINEPS where moosez's ribs model has rib 1 and rib 13; a
    liver cube over L4's top and a trachea cube under moosez's organs model; the cardiac and
    peripheral bones models' files empty, as a CT of the lumbar spine leaves them."""
    bones = [(23, 60, 90, MAIN), (24, 200, 230, MAIN), (25, 232, 250, MAIN), (26, 255, 275, MAIN)]
    extra = [(28, 10, 30, SIDE_COLUMN), (27, 280, 295, SIDE_COLUMN)]
    soft = [(8, 50, 75, MAIN), (19, 100, 120, SIDE_COLUMN)]
    write_ct(ct / "s0001", 300, bones + extra + soft)
    write_mask(spineps / "s0001_seg-vert_msk.nii.gz", 300, bones + extra)
    # The sacrum is 28 in moosez's vertebrae model and 26 in the VerSe alphabet.
    write_mask(moose_file(moose, "s0001", "clin_ct_vertebrae"), 300,
               bones[:3] + [(28, 255, 275, MAIN)])
    write_mask(moose_file(moose, "s0001", "clin_ct_ribs"), 300,
               [(1, 10, 30, SIDE_COLUMN), (13, 280, 295, SIDE_COLUMN)])
    write_mask(moose_file(moose, "s0001", "clin_ct_organs"), 300, soft)
    for model in ("clin_ct_cardiac", "clin_ct_peripheral_bones"):
        write_mask(moose_file(moose, "s0001", model), 300, [])


def empty_models(moose, subject, depth, stamp="20260101"):
    """The four models' files beside a vertebrae file, each empty, so the subject has every
    model's file as the segment job leaves a CT."""
    for model in MODELS[:-1]:
        write_mask(moose_file(moose, subject, model, stamp), depth, [])


def make_others(ct, spineps, moose):
    """batch/s0002, 200 slices (one padded crop), L4 and L5, the SPINEPS mask under sub-<id>,
    every model's file under MOOSE; s0003, only the coccyx under SPINEPS and only L6 under
    MOOSE's vertebrae model, its one file; s0004, a CT with no mask; s0005, a first mask on
    another grid in each scheme, then one on the CT's, the other models' files beside it, and a
    decoy for s00050; s0006, a mask of another shape alone in each scheme; s0010, a mask of the
    CT's shape placed elsewhere, another affine, alone in each scheme."""
    two = [(23, 50, 80, MAIN), (24, 120, 150, MAIN)]
    write_ct(ct / "batch" / "s0002", 200, two)
    write_mask(spineps / "sub-s0002_seg-vert_msk.nii.gz", 200, two)
    write_mask(moose_file(moose, "batch/s0002", "clin_ct_vertebrae"), 200, two)
    empty_models(moose, "batch/s0002", 200)
    write_ct(ct / "s0003", 120, [(27, 40, 60, MAIN)])
    write_mask(spineps / "s0003_seg-vert_msk.nii.gz", 120, [(27, 40, 60, MAIN)])
    write_mask(moose_file(moose, "s0003", "clin_ct_vertebrae"), 120, [(25, 40, 60, MAIN)])
    write_ct(ct / "s0004", 120, [(23, 40, 60, MAIN)])
    five = [(24, 40, 70, MAIN)]
    write_ct(ct / "s0005", 150, five)
    write_mask(spineps / "s0005_seg-vert_msk.nii.gz", 150, five, OTHER_GRID)
    write_mask(spineps / "sub-s0005_seg-vert_msk.nii.gz", 150, five)
    write_mask(spineps / "s00050_seg-vert_msk.nii.gz", 150, [(1, 40, 70, MAIN)])
    write_mask(moose_file(moose, "s0005", "clin_ct_vertebrae", "a", "_old"), 150, five, OTHER_GRID)
    write_mask(moose_file(moose, "s0005", "clin_ct_vertebrae", "b"), 150, five)
    empty_models(moose, "s0005", 150, "b")
    write_ct(ct / "s0006", 120, five)
    write_mask(spineps / "s0006_seg-vert_msk.nii.gz", 120, five, OTHER_GRID)
    write_mask(moose_file(moose, "s0006", "clin_ct_vertebrae"), 120, five, OTHER_GRID)
    write_ct(ct / "s0010", 120, five)
    write_mask(spineps / "s0010_seg-vert_msk.nii.gz", 120, five, affine=shifted_affine(120))
    write_mask(moose_file(moose, "s0010", "clin_ct_vertebrae"), 120, five,
               affine=shifted_affine(120))


def make_corpus(base):
    """The corpus under base: the CTs under ct/, the masks under spineps/ and moose/."""
    ct, spineps, moose = base / "ct", base / "spineps", base / "moose"
    make_s0001(ct, spineps, moose)
    make_others(ct, spineps, moose)
    return ct, spineps, moose


def label_volume(shape, cubes):
    """A label volume by MOOSE id in the main column, for the crop record cases."""
    import numpy as np

    label = np.zeros(shape, dtype=np.uint8)
    for moose_id, (first, last) in cubes.items():
        label[24:40, 24:40, first:last] = moose_id
    return label


# --- the runs -------------------------------------------------------------------------------------

def read_file(out, name):
    return json.loads((Path(out) / name).read_text(encoding="utf-8"))


def rows_by_file(out):
    """The manifest's rows by file, without the seconds a render took, which no run repeats."""
    return {row["file"]: {k: v for k, v in row.items() if k != "seconds"}
            for row in read_file(out, "manifest.json")["views"]}


def render(renderer, root, out, words, roots, engine="blocks", subjects=5, ids=ALL):
    blocks = renderer.rules().parse(SMALL + words)
    return renderer.render_subjects(root, out, subjects, SALT, "cpu", blocks=blocks, engine=engine,
                                    subject_ids=ids, roots=roots)


def grid_words(renderer):
    """The raw FluXray recipe's words, its 1024-pixel detector left to SMALL's 32."""
    rules = renderer.rules()
    return [w for w in rules.words_of(rules.FLUXRAY_RAW) if not w.startswith("detector=")]


def with_segmenter(words, name):
    return [w for w in words if not w.startswith("segmenter=")] + [f"segmenter={name}"]


def image_gap(ours, theirs):
    """The largest difference in grey levels between two 16-bit PNGs."""
    import numpy as np
    from PIL import Image

    with Image.open(ours) as a, Image.open(theirs) as b:
        return int(np.abs(np.asarray(a, dtype=np.int64) - np.asarray(b, dtype=np.int64)).max())


def recording_factors(drawn):
    """fxr.drr.subjects.sample_attenuation wrapped to record each call's count and factors."""
    import fxr.drr.subjects as subjects

    original = subjects.sample_attenuation

    def recording(bounds, n, *args, **kwargs):
        factors = original(bounds, n, *args, **kwargs)
        drawn.append((int(n), [float(f) for f in factors.tolist()]))
        return factors

    return mock.patch.object(subjects, "sample_attenuation", recording)


def check_factors(test, renderer, done, rows, drawn):
    """Each recorded factor is the one render_drr drew for its id, view by view; a shut gate drew
    one factor of 1."""
    supervised = renderer.supervised_ids(renderer.label_lut())
    for subject in done["subjects"]:
        for view in range(2):
            row = rows[renderer.render_file(subject, view)]
            count, factors = drawn.pop(0)
            if row["attenuation"] is None:
                test.assertEqual(count, 1, "a shut gate draws one factor of 1")
                continue
            test.assertEqual(count, len(supervised))
            for i, factor in row["attenuation"].items():
                test.assertAlmostEqual(factor, factors[supervised.index(int(i))], places=6)
    test.assertEqual(drawn, [])


# --- the segment subcommand's stand-ins -----------------------------------------------------------

def write_zip(path, members):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for name, text in members.items():
            archive.writestr(name, text)


def dataset_json(labels, values_as=str):
    """A model's dataset.json as nnU-Net writes it and moosez reads it: "labels" of name to
    value, background at 0, the values strings as moosez's `value != "0"` expects, or ints."""
    names = {"background": values_as(0)}
    names.update({name: values_as(value) for value, name in labels.items()})
    return json.dumps({"labels": names, "numTraining": 1})


def model_zip_members(folder, labels, values_as=str):
    """What a model's release zip unpacks to: the model's folder, its one configuration folder
    with plans.json and dataset.json naming the labels given."""
    return {f"{folder}/{CONFIG}/plans.json": "{}",
            f"{folder}/{CONFIG}/dataset.json": dataset_json(labels, values_as)}


def write_model_zips(renderer, zips, labels_of=None):
    """The five model zips under zips, each with the labels of this tool's table unless
    labels_of gives a model other labels (or a values type)."""
    segmenters = renderer.schemes()
    for model, (folder, zip_name) in renderer.MOOSEZ_WEIGHTS.items():
        labels, values_as = segmenters.MOOSEZ_MODELS[model], str
        if labels_of and model in labels_of:
            labels, values_as = labels_of[model]
        write_zip(zips / zip_name, model_zip_members(folder, labels, values_as))


def json_documents(text):
    """The JSON documents printed one after another."""
    decoder = json.JSONDecoder()
    found, position = [], 0
    while position < len(text):
        document, end = decoder.raw_decode(text, position)
        found.append(document)
        position = end
        while position < len(text) and text[position].isspace():
            position += 1
    return found


def segment(renderer, *words):
    """main's segment subcommand with its output caught: the exit code, the JSON documents it
    printed, what it wrote to stderr, and the one plain line a run ends with ("" when none),
    the only line of stdout that is not JSON."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = renderer.main(["segment", *words])
    lines = out.getvalue().splitlines(keepends=True)
    summary = [line for line in lines if line.startswith("segment: ")]
    documents = json_documents("".join(line for line in lines if not line.startswith("segment: ")))
    return code, documents, err.getvalue(), "".join(summary).rstrip("\n")


def untouchable_moosez():
    """A moosez that is importable and refuses every attribute, so a plan that touches it fails
    here instead of downloading on the grid."""
    class Untouchable(types.ModuleType):
        def __getattr__(self, name):
            raise AssertionError(f"the plan touched moosez.{name}")

    module = Untouchable("moosez")
    module.__spec__ = importlib.machinery.ModuleSpec("moosez", None)
    return module


def moosez_output(output_dir, model, stem, layout):
    """Where moosez writes a model's multilabel file for an input of that stem (its name before
    .nii): its library entry straight into output_dir as <prefix>segmentation_<stem>.nii.gz,
    the prefix clin_CT_<region>_ (moosez/__init__.py, moose; models.py, Model.multilabel_prefix;
    file_utilities.get_nifti_file_stem); its command line the same name under a stamped
    moosez-<date>/segmentations/ (moose_subject, file_utilities.moose_folder_structure)."""
    region = model.split("_", 2)[2]
    name = f"clin_CT_{region}_segmentation_{stem}.nii.gz"
    if layout == "cli":
        return Path(output_dir) / "moosez-2026-01-01-00-00-00" / "segmentations" / name
    return Path(output_dir) / name


def stand_in_moose(calls, layout="library"):
    """moosez's library entry stood in for: it records its call, reads the input by its path as
    moosez does (through the link, as through any file) and writes one mask a model on the
    input's grid, in the layout the library entry writes or, under "cli", the command line's."""
    def moose(input_path, names, output_dir, accelerator):
        import nibabel

        calls.append((Path(input_path).name, list(names), accelerator))
        image = nibabel.load(input_path)
        stem = Path(input_path).name.split(".gz")[0].split(".nii")[0]
        for model in names:
            path = moosez_output(output_dir, model, stem, layout)
            write_nifti(path, cubes_volume(image.shape[2], [(1, 0, 1, MAIN)]), image.affine)

    return moose


def stand_in_moosez(metadata, models_dir, calls, layout="library"):
    """The modules of moosez the segment run imports, stood in for: system with the models
    directory, constants and models with the metadata given, and the package with moose()."""
    system = types.ModuleType("moosez.system")
    system.MODELS_DIRECTORY_PATH = str(models_dir)
    constants = types.ModuleType("moosez.constants")
    constants.KEY_FOLDER_NAME, constants.KEY_URL = "directory", "url"
    models = types.ModuleType("moosez.models")
    models.MODEL_METADATA = {m: {"directory": f, "url": u} for m, (f, u) in metadata.items()}
    package = types.ModuleType("moosez")
    package.__spec__ = importlib.machinery.ModuleSpec("moosez", None, is_package=True)
    package.__path__ = []
    package.moose = stand_in_moose(calls, layout)
    package.system, package.constants, package.models = system, constants, models
    return {"moosez": package, "moosez.system": system, "moosez.constants": constants,
            "moosez.models": models}


# --- the cases ------------------------------------------------------------------------------------

@unittest.skipIf(MISSING, f"needs {', '.join(MISSING)}")
class Tables(unittest.TestCase):
    def test_the_torch_table_names_every_choice_of_the_rules(self):
        parts = load_tool("render_blocks")
        self.assertEqual(tuple(parts.NAMES), tuple(parts.rules.CHOICES))
        self.assertEqual(tuple(parts.NAMES["segmenter"]), parts.segmenters.SEGMENTERS)
        for name, allowed in parts.rules.CHOICES.items():
            self.assertEqual(tuple(parts.NAMES[name]), allowed, name)
            for choice, function in parts.NAMES[name].items():
                self.assertTrue(callable(function), f"{name}={choice}")
                self.assertIn("fxr/", function.__doc__ or "",
                              f"{name}={choice} says where FleXray does it")

    def test_every_relabel_table_lands_on_an_id_flexrays_protocol_declares(self):
        renderer = load_tool("flexray_render")
        schemes = renderer.schemes()
        lut = renderer.label_lut()
        supervised = renderer.supervised_ids(lut)
        self.assertEqual((len(lut), max(lut), len(supervised)), (118, 60, 97))
        self.assertNotIn(-1, lut, "every stored id is declared")
        tables = [schemes.to_moose_ids(scheme) for scheme in schemes.SEGMENTERS]
        tables += [schemes.moosez_to_moose_ids(model) for model in schemes.MOOSEZ_MODELS]
        for table in tables:
            for moose_id in table.values():
                name = schemes.MOOSE_STORED[moose_id]
                self.assertEqual(moose_id in supervised, schemes.supervised_by_flexray(name), name)
        for name in schemes.MOOSE_DROPPED:
            self.assertEqual(lut[schemes.MOOSE_IDS[name]], 0, f"{name} is dropped, not undeclared")
        self.assertEqual(schemes.to_moose_ids("spineps")[25], schemes.MOOSE_IDS["vertebra_l6"])
        self.assertNotIn(28, schemes.to_moose_ids("spineps"), "T13 has no MOOSE id")
        self.assertNotIn(19, schemes.moosez_to_moose_ids("clin_ct_organs"), "nor the trachea")

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

    def test_the_moosez_weights_copied_are_the_fetch_rows_zips(self):
        renderer = load_tool("flexray_render")
        text = (ROOT / "grid" / "run-platform-fetch.sh").read_text(encoding="utf-8")
        row = next(line for line in text.splitlines() if line.startswith("moose_weights|"))
        urls = {word for word in row.replace("|", " ").split() if word.startswith("https://")}
        metadata = renderer.moosez_metadata()
        self.assertEqual(tuple(metadata), renderer.segment_models())
        self.assertEqual(len(metadata), 5, "the five models whose labels MOOSE stores")
        for model, (folder, url) in metadata.items():
            self.assertIn(url, urls, f"{model}: the fetch row lands the zip the segment run reads")
            self.assertTrue(url.startswith(renderer.MOOSEZ_RELEASE), model)
            self.assertEqual(renderer.zip_of(url), renderer.MOOSEZ_WEIGHTS[model][1])
            self.assertTrue(folder.startswith("Dataset"), model)


@unittest.skipIf(MISSING, f"needs {', '.join(MISSING)}")
class FleXraysArithmetic(unittest.TestCase):
    def test_plan_crops_is_plan_z_crops_at_both_overlaps(self):
        from fxr.datasets.ct_crops import plan_z_crops

        parts = load_tool("render_blocks")
        rules = parts.rules
        self.assertEqual(rules.CROP_OVERLAP, {"flexray-axial": 0.5, "flexray-axial-min": 0.0})
        for depth in (1, 100, 101, 255, 256, 257, 300, 511, 512, 513, 700, 1000, 1500, 4096):
            for choice, overlap in rules.CROP_OVERLAP.items():
                planned = plan_z_crops(depth, rules.CROP_DEPTH, max_overlap=overlap)
                theirs = tuple((s.z_start, s.z_stop, s.z_pad_before, s.z_pad_after)
                               for s in planned)
                self.assertEqual(rules.plan_crops(depth, overlap), theirs, (depth, overlap))
                self.assertEqual(parts.NAMES["crop"][choice](depth), theirs, (depth, choice))
                for spec in planned:
                    self.assertEqual(spec.z_offset, spec.z_start - spec.z_pad_before)
            self.assertEqual(parts.NAMES["crop"]["whole"](depth), ((0, depth, 0, 0),))
        self.assertEqual([s.z_start for s in plan_z_crops(700, 256)], [0, 222, 444])
        self.assertEqual([s.z_start for s in plan_z_crops(700, 256, max_overlap=0.5)],
                         [0, 111, 222, 333, 444])

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
            self.assertTrue(torch.equal(parts.crop_sampler_uniform(crops, lut),
                                        torch.ones(len(crops), dtype=torch.float64)))

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
        from fxr.datasets.ct_crops import offset_affine

        parts = load_tool("render_blocks")
        volumes = ((300, {78: (60, 90), 79: (200, 230)}), (200, {78: (50, 80), 79: (120, 150)}),
                   (300, {78: (10, 40)}), (700, {59: (0, 30), 60: (300, 340), 61: (690, 700)}))
        for (depth, cubes), overlap in itertools.product(volumes, (0.0, 0.5)):
            label = label_volume((64, 64, depth), cubes)
            content = parts.crop_content(label, parts.rules.plan_crops(depth, overlap))
            ours = {c["z_start"]: c for c in content}
            theirs = packer_crops(label, depth, overlap)
            self.assertEqual(set(ours), set(theirs), (depth, overlap))
            for start, (spec, meta, label_crop) in theirs.items():
                crop = ours[start]
                self.assertEqual(crop["ids"], meta["crop_foreground_label_ids"])
                for i, centroid in zip(crop["ids"], meta["fg_centroids_ijk"], strict=True):
                    np.testing.assert_allclose(crop["centroids"][i], centroid, atol=1e-9)
                np.testing.assert_array_equal(parts.cut(label, crop, 0), label_crop)
                np.testing.assert_allclose(parts.crop_affine(affine_for(depth), crop),
                                           offset_affine(affine_for(depth), spec))

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

    def test_the_grid_pose_is_one_randint_over_fluxrays_90_poses(self):
        import torch

        parts = load_tool("render_blocks")
        rules = parts.rules
        seen = set()
        for seed in range(2000):
            torch.manual_seed(seed)
            pose = parts.pose_fluxray_grid(None)
            torch.manual_seed(seed)
            index = int(torch.randint(rules.GRID_POSES, (1,)).item())
            alpha, y, z = rules.grid_pose(index)
            self.assertEqual(pose["grid"], index)
            self.assertEqual(pose["rot"].tolist(), [[alpha, 0.0, 0.0]])
            self.assertEqual(pose["xyz"].tolist(), [[0.0, y, z]])
            self.assertEqual((pose["sdd"], pose["delx"]), (1250.0, 0.6))
            seen.add(index)
        self.assertEqual((rules.GRID_POSES, len(seen)), (90, 90))
        raw = rules.FLUXRAY_RAW
        self.assertEqual((raw.pose, raw.isocentre), ("fluxray-grid", "volume-centre"))
        self.assertEqual((raw.detector, raw.attenuation, raw.crop), (1024, "off", "whole"))
        self.assertEqual(raw.segmenter, "moose")


def packer_crops(label, depth, overlap):
    """FleXray's packer's crops of a label volume that hold a structure, by z_start: the spec,
    its metadata and the label crop."""
    import numpy as np
    from fxr.datasets.ct_crops import crop_metadata, crop_z, plan_z_crops

    theirs = {}
    for spec in plan_z_crops(depth, 256, max_overlap=overlap):
        label_crop = crop_z(label, spec, fill_value=0)
        if np.any(label_crop != 0):
            meta = crop_metadata(spec, label_crop, subject_id="s", source_sample_id="s")
            theirs[spec.z_start] = (spec, meta, label_crop)
    return theirs


@unittest.skipIf(MISSING, f"needs {', '.join(MISSING)}")
class Locators(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Path(tempfile.mkdtemp(prefix="flexray-locate-"))
        cls.ct, cls.spineps, cls.moose = make_corpus(cls.base)
        cls.roots = {"spineps": cls.spineps, "moose": cls.moose}
        cls.flat = cls.base / "flat"
        for name in ("s0007_vertebrae", "ribs_s0007", "s00070_vertebrae", "s0009_ribs_vertebrae",
                     "ribs_case1_vertebrae"):
            write_mask(cls.flat / f"{name}.nii.gz", 120, [(23, 40, 60, MAIN)])
        cls.renderer = load_tool("flexray_render")
        cls.parts = load_tool("render_blocks")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base, ignore_errors=True)

    def test_find_subjects_walks_the_nested_layout_and_lists_by_segmenter(self):
        import numpy as np

        find = self.renderer.find_subjects
        self.assertEqual(find(self.ct),
                         ["batch/s0002", "s0001", "s0003", "s0004", "s0005", "s0006", "s0010"])
        # On the CT's grid, so s0006's masks (another shape) and s0010's (another affine) count
        # for nothing; under moose every model's file, which s0003 lacks.
        self.assertEqual(find(self.ct, segmenter="spineps", roots=self.roots),
                         ["batch/s0002", "s0001", "s0003", "s0005"])
        self.assertEqual(find(self.ct, segmenter="moose", roots=self.roots),
                         ["batch/s0002", "s0001", "s0005"])
        shape, affine = self.renderer.header_grid(self.ct, "s0005")
        self.assertEqual(shape, (SIDE, SIDE, 150))
        self.assertTrue(np.allclose(affine, affine_for(150)))
        self.assertIsNone(self.renderer.header_grid(self.ct, "nowhere"))
        with self.assertRaisesRegex(ValueError, "segmenter 'totalsegmentator' is not one of"):
            find(self.ct, segmenter="totalsegmentator", roots=self.roots)
        with self.assertRaisesRegex(ValueError, "segmenter=moose: no masks folder given"):
            find(self.ct, segmenter="moose", roots={"spineps": self.spineps})
        with self.assertRaisesRegex(ValueError, "segmenter=spineps: no masks folder given"):
            find(self.ct, segmenter="spineps")

    def test_names_subject_reads_the_id_between_separators(self):
        names = self.parts.names_subject
        for stem in ("s0005", "sub-s0005", "s0005_ct", "CT_s0005", "a-s0005_b"):
            self.assertTrue(names(stem, "s0005"), stem)
            self.assertTrue(names(stem, "batch/s0005"), stem)
        for stem in ("s00050", "xs0005", "s0005x", "s000", "sub-s00050_ct", "batch"):
            self.assertFalse(names(stem, "s0005"), stem)

    def test_locate_spineps_takes_the_first_mask_naming_the_subject_on_the_cts_grid(self):
        locate = self.parts.locate_spineps
        self.assertEqual(locate("s0001", self.spineps).name, "s0001_seg-vert_msk.nii.gz")
        self.assertEqual(locate("batch/s0002", self.spineps).name, "sub-s0002_seg-vert_msk.nii.gz")
        self.assertIsNone(locate("s0004", self.spineps))
        self.assertIsNone(locate("s0001", None))
        # s0005: the first name in sorted order lies on another grid, the next on the CT's; the
        # decoy s00050 never names s0005.
        self.assertEqual(locate("s0005", self.spineps).name, "s0005_seg-vert_msk.nii.gz")
        self.assertEqual(locate("s0005", self.spineps, grid_for(150)).name,
                         "sub-s0005_seg-vert_msk.nii.gz")
        self.assertEqual(locate("s0005", self.spineps, (OTHER_GRID, affine_for(150))).name,
                         "s0005_seg-vert_msk.nii.gz")
        self.assertEqual(locate("s00050", self.spineps).name, "s00050_seg-vert_msk.nii.gz")
        self.assertEqual([p.name for p in self.parts.spineps_matches("s0005", self.spineps)],
                         ["s0005_seg-vert_msk.nii.gz", "sub-s0005_seg-vert_msk.nii.gz"])
        self.assertIsNone(locate("s0006", self.spineps, grid_for(120)))
        self.assertEqual(locate("s0006", self.spineps).name, "s0006_seg-vert_msk.nii.gz")
        # The CT's shape placed elsewhere is another grid too, told by the affine alone.
        self.assertIsNone(locate("s0010", self.spineps, grid_for(120)))
        self.assertEqual(locate("s0010", self.spineps).name, "s0010_seg-vert_msk.nii.gz")
        elsewhere = ((SIDE, SIDE, 120), shifted_affine(120))
        self.assertEqual(locate("s0010", self.spineps, elsewhere).name,
                         "s0010_seg-vert_msk.nii.gz")
        self.assertEqual(self.parts.on_grid(self.parts.spineps_matches("s0010", self.spineps),
                                            grid_for(120)),
                         ([], ["s0010_seg-vert_msk.nii.gz: another affine"]))
        # Within the tolerance a float32 header keeps, the affine is the CT's.
        close = affine_for(120)
        close[1, 3] += 0.5 * self.parts.AFFINE_TOLERANCE_MM
        self.assertEqual(locate("s0006", self.spineps, (OTHER_GRID, close)).name,
                         "s0006_seg-vert_msk.nii.gz")

    def test_locate_moose_reads_each_models_file_by_its_region_below_the_subjects_folder(self):
        locate = self.parts.locate_moose
        found = locate("s0001", self.moose)
        self.assertEqual({m: p.name for m, p in found.items()}, MOOSE_S0001["files"])
        self.assertEqual(list(found), list(MODELS), "in the order the volume is written")
        self.assertEqual(list(locate("batch/s0002", self.moose)), list(MODELS))
        self.assertEqual(list(locate("s0003", self.moose)), ["clin_ct_vertebrae"])
        self.assertEqual(locate("s0004", self.moose), {})
        self.assertEqual(locate("s0001", None), {})
        self.assertEqual(locate("s0005", self.moose)["clin_ct_vertebrae"].name,
                         "clin_CT_vertebrae_CT_s0005_old.nii.gz")
        self.assertEqual(locate("s0005", self.moose, grid_for(150))["clin_ct_vertebrae"].name,
                         "clin_CT_vertebrae_CT_s0005.nii.gz")
        self.assertEqual(locate("s0006", self.moose, grid_for(120)), {})
        self.assertEqual(locate("s0010", self.moose, grid_for(120)), {})
        self.assertEqual(list(locate("s0010", self.moose)), ["clin_ct_vertebrae"])
        # With no folder of its own, a subject's files are the ones under the root naming it.
        self.assertEqual({m: p.name for m, p in locate("s0007", self.flat).items()},
                         {"clin_ct_vertebrae": "s0007_vertebrae.nii.gz",
                          "clin_ct_ribs": "ribs_s0007.nii.gz"})
        self.assertEqual(locate("s0008", self.flat), {})
        # A file naming two regions is placed with no model and recorded; a subject whose own id
        # holds a region word still names one model.
        parts = self.parts
        found, skipped, unplaced = parts.by_region(parts.moose_candidates("s0009", self.flat),
                                                   None, "s0009")
        self.assertEqual((found, skipped, unplaced), ({}, [], ["s0009_ribs_vertebrae.nii.gz"]))
        self.assertEqual({m: p.name for m, p in locate("ribs_case1", self.flat).items()},
                         {"clin_ct_vertebrae": "ribs_case1_vertebrae.nii.gz"})
        # The CT link the segment subcommand leaves, and any symlink, is never a candidate, so
        # it is never recorded as an unplaced moosez output; a real file of the link's name
        # neither.
        home = self.moose / "s0001"
        (home / "CT_s0001.nii.gz").symlink_to(self.ct / "s0001" / "ct.nii.gz")
        (home / "other_link.nii.gz").symlink_to(self.ct / "s0001" / "ct.nii.gz")
        shutil.copy(self.ct / "s0001" / "ct.nii.gz", self.flat / "CT_s0007.nii.gz")
        parts.moose_index.cache_clear()
        try:
            names = [p.name for p, _ in parts.moose_candidates("s0001", self.moose)]
            self.assertEqual(sorted(names), sorted(MOOSE_FILES.values()))
            _, _, unplaced = parts.by_region(parts.moose_candidates("s0001", self.moose),
                                             None, "s0001")
            self.assertEqual(unplaced, [])
            self.assertEqual({m: p.name for m, p in locate("s0007", self.flat).items()},
                             {"clin_ct_vertebrae": "s0007_vertebrae.nii.gz",
                              "clin_ct_ribs": "ribs_s0007.nii.gz"})
            self.assertNotIn("CT_s0007.nii.gz",
                             [p.name for p, _ in parts.moose_candidates("s0007", self.flat)])
        finally:
            (home / "CT_s0001.nii.gz").unlink()
            (home / "other_link.nii.gz").unlink()
            (self.flat / "CT_s0007.nii.gz").unlink()
            parts.moose_index.cache_clear()
        # moosez's CLI names its output folder after every model of one run; the file's name
        # decides there.
        self.assertEqual(parts.model_of(Path("moosez-clin_ct_ribs-clin_ct_vertebrae-20260101")
                                        / "segmentations" / "clin_CT_ribs_segmentation_CT_x.nii.gz",
                                        "x"), "clin_ct_ribs")
        self.assertIsNone(parts.model_of(Path("moosez-clin_ct_ribs-clin_ct_vertebrae-1") / "segmentations"
                                         / "segmentation_CT_x.nii.gz", "x"))


@unittest.skipIf(MISSING, f"needs {', '.join(MISSING)}")
class LabelVolumes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Path(tempfile.mkdtemp(prefix="flexray-labels-"))
        cls.ct, spineps, moose = make_corpus(cls.base)
        cls.roots = {"spineps": spineps, "moose": moose}
        cls.parts = load_tool("render_blocks")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base, ignore_errors=True)

    def test_label_spineps_relabels_the_verse_alphabet_into_moose_ids(self):
        import numpy as np

        label, record = self.parts.label_spineps("s0001", grid_for(300), self.roots)
        self.assertEqual((label.dtype, label.shape), (np.int16, (SIDE, SIDE, 300)))
        self.assertEqual(np.unique(label).tolist(), [0, 81, 82, 83, 86])
        column = label[MAIN]
        self.assertTrue((column[..., 60:90] == 81).all() and (column[..., 232:250] == 83).all())
        self.assertTrue((column[..., 200:230] == 82).all() and (column[..., 255:275] == 86).all())
        self.assertFalse(label[SIDE_COLUMN].any(), "T13 and the coccyx have no MOOSE id")
        self.assertEqual(record, SPINEPS_S0001)
        label, record = self.parts.label_spineps("batch/s0002", grid_for(200), self.roots)
        self.assertEqual(np.unique(label).tolist(), [0, 81, 82])
        self.assertEqual(record["files"], {"spineps": "sub-s0002_seg-vert_msk.nii.gz"})
        self.assertEqual((record["dropped"], record["unsupervised"]), ([], {}))

    def test_label_moose_merges_the_models_with_the_vertebrae_last(self):
        import numpy as np

        label, record = self.parts.label_moose("s0001", grid_for(300), self.roots)
        self.assertEqual(label.dtype, np.int16)
        self.assertEqual(np.unique(label).tolist(), [0, 32, 44, 81, 82, 83, 86, 94])
        column = label[MAIN]
        self.assertTrue((column[..., 50:60] == 94).all(), "the liver where no vertebra is")
        self.assertTrue((column[..., 60:90] == 81).all(), "L4 wins over the liver")
        self.assertTrue((column[..., 255:275] == 86).all(), "moosez's 28 is the sacrum")
        side = label[SIDE_COLUMN]
        self.assertTrue((side[..., 10:30] == 32).all() and (side[..., 280:295] == 44).all())
        self.assertFalse(side[..., 100:120].any(), "the trachea has no MOOSE id")
        self.assertEqual(record, moose_s0001())
        label, record = self.parts.label_moose("s0003", grid_for(120), self.roots)
        self.assertEqual(np.unique(label).tolist(), [0, 83])
        self.assertEqual((record["labels"], record["dropped"]),
                         ({"83": "vertebra_l6"}, ["vertebra_l6"]))
        self.assertEqual((record["models_missing"], record["precedence"]),
                         (list(MODELS[:-1]), ["clin_ct_vertebrae"]))
        # One model read: its absent names are the vertebrae model's alone, the sacrum among them.
        vertebrae = self.parts.segmenters.moosez_to_moose_ids("clin_ct_vertebrae").values()
        self.assertEqual(record["absent"], [self.parts.segmenters.MOOSE_STORED[i]
                                            for i in sorted(set(vertebrae) - {83})])
        self.assertIn("sacrum", record["absent"])
        self.assertNotIn("liver", record["absent"])

    def test_absent_lists_the_supervised_names_the_files_could_have_carried(self):
        import numpy as np

        _, record = self.parts.label_moose("s0001", grid_for(300), self.roots)
        absent = record["absent"]
        # Absent: a vertebra the mask lacks, a cardiac name whose file is empty; not absent: a
        # name present, the names FleXray drops (L6, rib 13, the aorta), a name MOOSE lacks.
        for name in ("vertebra_l1", "heart_myocardium", "liver", "vertebra_l6", "rib_left_13",
                     "aorta", "trachea", "vertebra_t13", "background"):
            self.assertEqual(name in absent, name in ("vertebra_l1", "heart_myocardium"), name)
        self.assertEqual(len(absent), len(set(absent)))
        ids = [self.parts.segmenters.MOOSE_IDS[name] for name in absent]
        self.assertEqual(ids, sorted(ids), "in MOOSE's id order")
        # A negative value is outside every table and recorded, never written.
        label = np.zeros((2, 2, 2), dtype=np.int16)
        values = np.array([[[-1, 0], [23, 99]], [[0, 0], [0, 0]]], dtype=np.int32)
        outside = self.parts.relabel(values, self.parts.segmenters.to_moose_ids("spineps"), label)
        self.assertEqual((outside, np.unique(label).tolist()), ([-1, 99], [0, 81]))

    def test_a_mask_on_another_grid_is_skipped_with_its_reason_or_refused_when_alone(self):
        parts = self.parts
        _, record = parts.label_spineps("s0005", grid_for(150), self.roots)
        self.assertEqual(record["files"], {"spineps": "sub-s0005_seg-vert_msk.nii.gz"})
        self.assertEqual(record["skipped"], ["s0005_seg-vert_msk.nii.gz: another shape"])
        _, record = parts.label_moose("s0005", grid_for(150), self.roots)
        self.assertEqual(record["files"]["clin_ct_vertebrae"], "clin_CT_vertebrae_CT_s0005.nii.gz")
        self.assertEqual((list(record["files"]), record["models_missing"]), (list(MODELS), []))
        self.assertEqual(record["skipped"],
                         ["clin_CT_vertebrae_CT_s0005_old.nii.gz: another shape"])
        with self.assertRaises(parts.MaskProblem) as found:
            parts.label_spineps("s0006", grid_for(120), self.roots)
        self.assertEqual(str(found.exception), "no SPINEPS mask found under its folder on the "
                         "CT's grid (s0006_seg-vert_msk.nii.gz: another shape)")
        with self.assertRaises(parts.MaskProblem) as found:
            parts.label_moose("s0006", grid_for(120), self.roots)
        self.assertEqual(str(found.exception), "no MOOSE masks found under its folder on the "
                         "CT's grid (clin_CT_vertebrae_CT_s0006.nii.gz: another shape)")
        # The CT's shape placed elsewhere: told by the affine, skipped with that reason.
        with self.assertRaises(parts.MaskProblem) as found:
            parts.label_spineps("s0010", grid_for(120), self.roots)
        self.assertEqual(str(found.exception), "no SPINEPS mask found under its folder on the "
                         "CT's grid (s0010_seg-vert_msk.nii.gz: another affine)")
        with self.assertRaises(parts.MaskProblem) as found:
            parts.label_moose("s0010", grid_for(120), self.roots)
        self.assertEqual(str(found.exception), "no MOOSE masks found under its folder on the "
                         "CT's grid (clin_CT_vertebrae_CT_s0010.nii.gz: another affine)")
        other = self.roots["spineps"] / "s0005_seg-vert_msk.nii.gz"
        with self.assertRaisesRegex(parts.MaskProblem,
                                    r"is on another grid than the CT \(another shape\)"):
            parts.read_values(other, grid_for(150))
        elsewhere = self.roots["spineps"] / "s0010_seg-vert_msk.nii.gz"
        with self.assertRaisesRegex(parts.MaskProblem,
                                    r"is on another grid than the CT \(another affine\)"):
            parts.read_values(elsewhere, grid_for(120))
        values = parts.read_values(elsewhere, ((SIDE, SIDE, 120), shifted_affine(120)))
        self.assertEqual(values.shape, (SIDE, SIDE, 120))
        self.assertEqual(parts.grid_problem(parts.mask_grid(elsewhere), grid_for(120)),
                         "another affine")
        self.assertIsNone(parts.grid_problem(parts.mask_grid(other),
                                             (OTHER_GRID, affine_for(150))))

    def test_no_mask_and_no_folder_are_refused_in_words(self):
        parts = self.parts
        cases = ((parts.label_spineps, "SPINEPS mask"), (parts.label_moose, "MOOSE masks"))
        for build, scheme in cases:
            with self.assertRaises(parts.MaskProblem) as found:
                build("s0004", grid_for(120), self.roots)
            self.assertEqual(str(found.exception), f"no {scheme} found under its folder")
            with self.assertRaises(parts.MaskProblem):
                build("s0001", grid_for(300), {})

    def test_flexrays_projection_accepts_both_volumes(self):
        reason = runtime_missing()
        if reason:
            self.skipTest(reason)
        import numpy as np
        import torch
        from fxr.experiment.label_projection import TrainingLabelProjection

        renderer = load_tool("flexray_render")
        projection = TrainingLabelProjection.from_label_remap(renderer.label_remap())
        for build in (self.parts.label_spineps, self.parts.label_moose):
            label, _ = build("s0001", grid_for(300), self.roots)
            native = projection.validated_native_ids(
                torch.from_numpy(label.astype(np.int64))[None, None], source="s0001",
                require_mapped=True)
            self.assertEqual(sorted(set(native.flatten().tolist())), np.unique(label).tolist())


@unittest.skipIf(MISSING, f"needs {', '.join(MISSING)}")
class Rendering(unittest.TestCase):
    """The blocks engine on the five named subjects under each segmenter, the physical variant
    of each and the raw FluXray recipe under both."""

    @classmethod
    def setUpClass(cls):
        cls.base = Path(tempfile.mkdtemp(prefix="flexray-render-"))
        cls.root, spineps, moose = make_corpus(cls.base)
        cls.roots = {"spineps": spineps, "moose": moose}
        cls.renderer = load_tool("flexray_render")
        grid = grid_words(cls.renderer)
        cls.runs = {}
        for name, words in (("default", []), ("physical", ["attenuation=off"]),
                            ("moose", ["segmenter=moose"]),
                            ("physical-moose", ["attenuation=off", "segmenter=moose"])):
            cls.runs[name] = render(cls.renderer, cls.root, cls.base / name, words, cls.roots)
        for name, words in (("grid", grid), ("grid-spineps", with_segmenter(grid, "spineps"))):
            cls.runs[name] = render(cls.renderer, cls.root, cls.base / name, words, cls.roots,
                                    subjects=2)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base, ignore_errors=True)

    def test_three_subjects_are_kept_and_the_others_passed_over_with_their_reasons(self):
        done = self.runs["default"]
        self.assertEqual((done["rendered"], done["rendered_now"], done["reused"]), (6, 6, 0))
        self.assertEqual(done["subjects"], ["s0001", "batch/s0002", "s0005"])
        self.assertEqual(done["skipped"], ["s0003: no structure in its masks",
                                           "s0004: no SPINEPS mask found under its folder"])
        moose = self.runs["moose"]
        self.assertEqual(moose["subjects"], done["subjects"])
        self.assertEqual(moose["skipped"], ["s0003: no structure FleXray supervises in its masks",
                                            "s0004: no MOOSE masks found under its folder"])
        salted = render(self.renderer, self.root, self.base / "salted", ["attenuation=off"],
                        self.roots, subjects=6, ids=None)
        self.assertEqual(sorted(salted["subjects"]), ["batch/s0002", "s0001", "s0005"])
        self.assertIn("s0006: no SPINEPS mask found under its folder on the CT's grid "
                      "(s0006_seg-vert_msk.nii.gz: another shape)", salted["skipped"])
        self.assertIn("s0010: no SPINEPS mask found under its folder on the CT's grid "
                      "(s0010_seg-vert_msk.nii.gz: another affine)", salted["skipped"])
        self.assertEqual(len(salted["skipped"]), 4)

    def test_each_view_is_a_16_bit_png_at_the_detector_size(self):
        import numpy as np
        from PIL import Image

        rows = rows_by_file(self.base / "default")
        self.assertEqual(sorted(rows), ["images/batch-s0002_v00.png", "images/batch-s0002_v01.png",
                                        "images/s0001_v00.png", "images/s0001_v01.png",
                                        "images/s0005_v00.png", "images/s0005_v01.png"])
        levels = []
        for file in rows:
            with Image.open(self.base / "default" / file) as image:
                self.assertEqual((image.mode, image.size), ("I;16", (32, 32)), file)
                levels.append(len(np.unique(np.asarray(image))))
        self.assertGreater(max(levels), 1, "the renderer saw the volume in at least one view")

    def test_the_manifest_says_what_was_rendered(self):
        rules = self.renderer.rules()
        names = self.renderer.moose_names()
        manifest = read_file(self.base / "default", "manifest.json")
        self.assertEqual(manifest["blocks"], rules.as_record(rules.parse(SMALL)))
        self.assertEqual((manifest["engine"], manifest["segmenter"]), ("blocks", "spineps"))
        self.assertEqual(manifest["flexray"], self.renderer.versions()["flexray"])
        self.assertEqual(manifest["labels"]["s0001"], SPINEPS_S0001)
        self.assertEqual(sorted(manifest["labels"]), ["batch/s0002", "s0001", "s0005"])
        for row in manifest["views"]:
            self.assertEqual(set(row), {"file", "subject", "view", "seed", "crop", "isocentre",
                                        "pose", "attenuation", "seconds"})
            seed = self.renderer.view_seed(SALT, row["subject"], row["view"])
            self.assertEqual(row["seed"], seed)
            self.assertEqual(set(row["crop"]), {"z_start", "z_stop", "pad_before", "pad_after"})
            self.assertIn(row["isocentre"]["label"], (81, 82, 86), "a supervised structure, not L6")
            self.assertEqual(row["isocentre"]["name"], names[row["isocentre"]["label"]])
            self.assertEqual(len(row["isocentre"]["point_mm"]), 3)
            self.assertEqual(set(row["pose"]),
                             {"rot_deg", "xyz_mm", "orthographic", "sdd", "delx", "grid"})
            self.assertIsNone(row["pose"]["grid"])
            self.assertTrue(1150.0 <= row["pose"]["sdd"] <= 1250.0)
            self.assertTrue(1.25 <= row["pose"]["delx"] <= 2.25)

    def test_the_record_says_what_was_rendered(self):
        record = read_file(self.base / "default", "RENDER.json")
        self.assertEqual((record["version"], record["status"]), (3, "done"))
        self.assertEqual(record["settings"]["engine"], "blocks")
        self.assertEqual(record["settings"]["blocks"]["segmenter"], "spineps")
        self.assertEqual(record["arguments"]["subject_ids"], list(ALL))
        self.assertEqual(sorted(record["arguments"]["roots"]), ["moose", "spineps"])
        self.assertEqual(record["counts"]["subjects_kept"], 3)
        self.assertEqual((record["counts"]["subjects_found"], record["counts"]["renders"]), (7, 6))
        self.assertEqual(record["subjects"], self.runs["default"]["subjects"])
        self.assertEqual(record["skipped"], self.runs["default"]["skipped"])
        self.assertEqual(record["profile"]["crop_overlap"], 0.5)
        self.assertEqual(record["profile"]["grid"], self.renderer.grid_record())

    def test_the_moose_manifest_records_the_models_read_and_the_dropped_names(self):
        manifest = read_file(self.base / "moose", "manifest.json")
        self.assertEqual(manifest["segmenter"], "moose")
        self.assertEqual(manifest["blocks"]["segmenter"], "moose")
        self.assertEqual(manifest["labels"]["s0001"], moose_s0001())
        two = manifest["labels"]["batch/s0002"]
        self.assertEqual(two["files"]["clin_ct_vertebrae"], "clin_CT_vertebrae_CT_s0002.nii.gz")
        self.assertEqual((sorted(two["files"]), two["models_missing"]), (sorted(MODELS), []))
        self.assertEqual(two["precedence"], list(MODELS), "the order written, kept as a list")
        self.assertEqual(manifest["labels"]["s0005"]["skipped"],
                         ["clin_CT_vertebrae_CT_s0005_old.nii.gz: another shape"])
        # The same label volume under either scheme draws the same views.
        ours, theirs = rows_by_file(self.base / "default"), rows_by_file(self.base / "moose")
        for file in ("images/batch-s0002_v00.png", "images/batch-s0002_v01.png",
                     "images/s0005_v00.png", "images/s0005_v01.png"):
            self.assertEqual(ours[file], theirs[file], file)
        # A dropped name is in the volume and never among the attenuated ids.
        for row in theirs.values():
            if row["attenuation"] is not None:
                self.assertFalse({"44", "83"} & set(row["attenuation"]), row["file"])

    def test_a_second_call_under_the_same_settings_reuses_every_view(self):
        out = self.base / "default"
        before = {p.name: p.read_bytes() for p in (out / "images").glob("*.png")}
        rows = rows_by_file(out)
        again = render(self.renderer, self.root, out, [], self.roots)
        self.assertEqual((again["rendered"], again["rendered_now"], again["reused"]), (6, 0, 6))
        self.assertEqual(again["subjects"], self.runs["default"]["subjects"])
        self.assertEqual({p.name: p.read_bytes() for p in (out / "images").glob("*.png")}, before)
        self.assertEqual(rows_by_file(out), rows)
        self.assertEqual(read_file(out, "manifest.json")["labels"]["s0001"], SPINEPS_S0001)

    def test_other_settings_render_anew_into_the_same_folder(self):
        out = self.base / "default"
        other = render(self.renderer, self.root, out, ["crop_sampler=uniform"], self.roots)
        self.assertEqual((other["rendered_now"], other["reused"]), (6, 0))
        record = read_file(out, "RENDER.json")
        self.assertEqual(record["settings"]["blocks"]["crop_sampler"], "uniform")
        back = render(self.renderer, self.root, out, [], self.roots)
        self.assertEqual((back["rendered_now"], back["reused"]), (6, 0))

    def test_groups_that_differ_only_by_attenuation_share_crop_isocentre_and_pose(self):
        for pair in (("default", "physical"), ("moose", "physical-moose")):
            default, physical = (rows_by_file(self.base / name) for name in pair)
            self.assertEqual(set(default), set(physical))
            for file, row in default.items():
                other = physical[file]
                for key in ("crop", "isocentre", "pose", "seed"):
                    self.assertEqual(row[key], other[key], (pair, file, key))
                self.assertIsNone(other["attenuation"], file)
            opened = [row for row in default.values() if row["attenuation"] is not None]
            self.assertGreaterEqual(len(opened), 1, "the salt opens the gate at least once")
            for row in opened:
                self.assertTrue({81, 82, 86} & {int(i) for i in row["attenuation"]}, row["file"])
                for factor in row["attenuation"].values():
                    self.assertTrue(0.1 <= factor <= 4.0)

    def test_the_factors_recorded_are_the_ones_render_drr_drew(self):
        drawn = []
        with recording_factors(drawn):
            done = render(self.renderer, self.root, self.base / "recorded", [], self.roots)
        rows = rows_by_file(self.base / "recorded")
        self.assertEqual(rows, rows_by_file(self.base / "default"))
        check_factors(self, self.renderer, done, rows, drawn)

    def test_a_fault_is_refused_in_words_before_anything_is_written(self):
        rules = self.renderer.rules()
        out = self.base / "refused"
        with self.assertRaisesRegex(rules.RenderBlockError, "runtime cannot honour crop='whole'"):
            render(self.renderer, self.root, out, ["crop=whole", "crop_sampler=uniform"],
                   self.roots, engine="flexray-runtime")
        with self.assertRaisesRegex(rules.RenderBlockError, "engine 'flux' is not one of"):
            render(self.renderer, self.root, out, [], self.roots, engine="flux")
        with self.assertRaisesRegex(rules.RenderBlockError, "segmenter='totalsegmentator' is not"):
            render(self.renderer, self.root, out, ["segmenter=totalsegmentator"], self.roots)
        bad = replace(rules.parse(SMALL), segmenter="totalsegmentator")
        with self.assertRaisesRegex(rules.RenderBlockError, "segmenter='totalsegmentator' is not"):
            self.renderer.render_subjects(self.root, out, 1, SALT, "cpu", blocks=bad,
                                          roots=self.roots)
        with self.assertRaisesRegex(ValueError, "subjects must be at least 1"):
            render(self.renderer, self.root, out, [], self.roots, subjects=0)
        with self.assertRaisesRegex(ValueError, "segmenter=spineps: no masks folder given"):
            render(self.renderer, self.root, out, [], {})
        with self.assertRaisesRegex(ValueError, "segmenter=moose: no masks folder given"):
            render(self.renderer, self.root, out, ["segmenter=moose"],
                   {"spineps": self.roots["spineps"]})
        with self.assertRaisesRegex(ValueError, "segmenter=spineps: its masks folder is not"):
            render(self.renderer, self.root, out, [], {"spineps": self.base / "nowhere"})
        self.assertFalse(out.exists())

    def test_named_subjects_are_rendered_in_their_order_and_a_missing_one_is_passed_over(self):
        done = render(self.renderer, self.root, self.base / "named", ["attenuation=off"],
                      self.roots, ids=("s0001", "nowhere", "s0003"))
        self.assertEqual(done["subjects"], ["s0001"])
        self.assertEqual(done["skipped"], ["nowhere: not found under the CT folder",
                                           "s0003: no structure in its masks"])
        self.assertEqual(rows_by_file(self.base / "named")["images/s0001_v00.png"],
                         rows_by_file(self.base / "physical")["images/s0001_v00.png"])

    def test_the_command_line_renders_one_subject_and_needs_the_segmenters_folder(self):
        out = self.base / "cli"
        common = ["--ct-root", str(self.root), "--out", str(out), "--salt", SALT,
                  "--blocks", "views=1", "--blocks", "detector=32", "--blocks", "ray_samples=64",
                  "--blocks", "attenuation=off"]
        with self.assertRaisesRegex(ValueError, "--spineps on the command line"):
            self.renderer.main(common + ["--subject", "s0001"])
        self.assertFalse(out.exists())
        spineps = str(self.roots["spineps"])
        code = self.renderer.main(common + ["--subject", "s0001", "--spineps", spineps])
        self.assertEqual(code, 0)
        self.assertEqual(list(rows_by_file(out)), ["images/s0001_v00.png"])
        record = read_file(out, "RENDER.json")
        self.assertEqual(record["arguments"]["engine"], "blocks")
        self.assertEqual(record["arguments"]["roots"], {"spineps": spineps})
        self.assertEqual(record["settings"]["blocks"]["views"], 1)
        code = self.renderer.main(["render"] + common + ["--subject", "s0004", "--blocks",
                                  "segmenter=moose", "--moose", str(self.roots["moose"])])
        self.assertEqual(code, 1, "no subject kept")
        self.assertEqual(read_file(out, "RENDER.json")["skipped"],
                         ["s0004: no MOOSE masks found under its folder"])

    def test_the_grid_pose_rows_are_fluxrays_fixed_poses_at_the_volumes_centre(self):
        rules = self.renderer.rules()
        rows = rows_by_file(self.base / "grid")
        self.assertEqual(sorted(rows), ["images/batch-s0002_v00.png", "images/batch-s0002_v01.png",
                                        "images/s0001_v00.png", "images/s0001_v01.png"])
        depths = {"s0001": 300, "batch/s0002": 200}
        for row in rows.values():
            pose = row["pose"]
            self.assertTrue(0 <= pose["grid"] < rules.GRID_POSES)
            alpha, y, z = rules.grid_pose(pose["grid"])
            self.assertEqual((pose["rot_deg"], pose["xyz_mm"]), ([alpha, 0.0, 0.0], [0.0, y, z]))
            self.assertEqual((pose["sdd"], pose["delx"]), (1250.0, 0.6))
            self.assertFalse(pose["orthographic"])
            self.assertEqual(row["isocentre"],
                             {"label": None, "name": None, "point_mm": [-1.5, -1.5, -0.75]})
            self.assertEqual(row["crop"], {"z_start": 0, "z_stop": depths[row["subject"]],
                                           "pad_before": 0, "pad_after": 0})
            self.assertIsNone(row["attenuation"])
        self.assertGreater(len({row["pose"]["grid"] for row in rows.values()}), 1)
        record = read_file(self.base / "grid", "RENDER.json")
        self.assertEqual(record["profile"]["grid"], self.renderer.grid_record())
        self.assertEqual(record["settings"]["blocks"]["pose"], "fluxray-grid")
        self.assertEqual((record["counts"]["subjects_kept"], record["skipped"]), (2, []))

    def test_the_raw_recipe_renders_the_same_under_either_segmenter(self):
        ours = rows_by_file(self.base / "grid")
        self.assertEqual(ours, rows_by_file(self.base / "grid-spineps"))
        for file in ours:
            self.assertEqual((self.base / "grid" / file).read_bytes(),
                             (self.base / "grid-spineps" / file).read_bytes(), file)
        self.assertEqual(read_file(self.base / "grid", "manifest.json")["segmenter"], "moose")
        manifest = read_file(self.base / "grid-spineps", "manifest.json")
        self.assertEqual(manifest["segmenter"], "spineps")
        self.assertEqual(manifest["labels"]["s0001"], SPINEPS_S0001)


@unittest.skipIf(MISSING, f"needs {', '.join(MISSING)}")
class FleXraysRuntime(unittest.TestCase):
    """FleXray's own code rendering the same corpus from the same seeds under each segmenter and
    under the raw FluXray recipe: with the draws in the same order, the blocks engine's crop,
    isocentre, pose and factors are its own."""

    @classmethod
    def setUpClass(cls):
        cls.reason = runtime_missing()
        if cls.reason:
            return
        cls.base = Path(tempfile.mkdtemp(prefix="flexray-runtime-"))
        cls.root, spineps, moose = make_corpus(cls.base)
        cls.roots = {"spineps": spineps, "moose": moose}
        cls.renderer = load_tool("flexray_render")
        cls.words = {"default": [], "moose": ["segmenter=moose"], "grid": grid_words(cls.renderer)}
        cls.runs = {}
        for name, words in cls.words.items():
            for engine in ("blocks", "flexray-runtime"):
                cls.runs[name, engine] = render(
                    cls.renderer, cls.root, cls.base / f"{name}-{engine}", words, cls.roots,
                    engine=engine, subjects=2 if name == "grid" else 5)

    @classmethod
    def tearDownClass(cls):
        if not cls.reason:
            shutil.rmtree(cls.base, ignore_errors=True)

    def setUp(self):
        if self.reason:
            self.skipTest(self.reason)

    def test_the_runtime_writes_the_same_layout(self):
        from PIL import Image

        for name in self.words:
            ours, theirs = self.runs[name, "blocks"], self.runs[name, "flexray-runtime"]
            self.assertEqual((theirs["subjects"], theirs["skipped"]),
                             (ours["subjects"], ours["skipped"]), name)
            rows = rows_by_file(self.base / f"{name}-flexray-runtime")
            self.assertEqual(set(rows), set(rows_by_file(self.base / f"{name}-blocks")), name)
            for file in rows:
                with Image.open(self.base / f"{name}-flexray-runtime" / file) as image:
                    self.assertEqual((image.mode, image.size), ("I;16", (32, 32)), file)
        record = read_file(self.base / "default-flexray-runtime", "RENDER.json")
        self.assertEqual(record["settings"]["engine"], "flexray-runtime")
        self.assertEqual(record["profile"]["effective_profile"]["num_views"], 1)
        self.assertEqual(record["profile"]["effective_profile"]["intrinsics_cfg"]["height"], 32)
        grid = read_file(self.base / "grid-flexray-runtime", "RENDER.json")
        self.assertIsNone(grid["profile"]["effective_profile"])
        self.assertEqual(grid["profile"]["grid"], self.renderer.grid_record())

    def test_the_blocks_engine_draws_what_flexrays_runtime_draws(self):
        for name in ("default", "moose"):
            ours = rows_by_file(self.base / f"{name}-blocks")
            theirs = rows_by_file(self.base / f"{name}-flexray-runtime")
            for file, row in ours.items():
                self.assert_same_draws(row, theirs[file], (name, file))

    def assert_same_draws(self, row, other, where):
        import numpy as np

        self.assertEqual(row["crop"], other["crop"], where)
        self.assertEqual(row["isocentre"]["label"], other["isocentre"]["label"], where)
        np.testing.assert_allclose(row["isocentre"]["point_mm"], other["isocentre"]["point_mm"],
                                   atol=1e-3)
        np.testing.assert_allclose(row["pose"]["rot_deg"], other["pose"]["rot_deg"], atol=1e-3)
        np.testing.assert_allclose(row["pose"]["xyz_mm"], other["pose"]["xyz_mm"], atol=1e-3)
        self.assertEqual(row["pose"]["orthographic"], other["pose"]["orthographic"], where)
        self.assertEqual(row["pose"]["grid"], other["pose"]["grid"], where)
        self.assertAlmostEqual(row["pose"]["sdd"], other["pose"]["sdd"], places=4)
        self.assertAlmostEqual(row["pose"]["delx"], other["pose"]["delx"], places=6)
        if row["attenuation"] is None:
            self.assertIsNone(other["attenuation"], where)
            return
        self.assertEqual(set(row["attenuation"]), set(other["attenuation"]), where)
        for i, factor in row["attenuation"].items():
            self.assertAlmostEqual(factor, other["attenuation"][i], places=5)

    def test_the_runtimes_images_are_the_blocks_engines(self):
        for name in self.words:
            for file in rows_by_file(self.base / f"{name}-blocks"):
                gap = image_gap(self.base / f"{name}-blocks" / file,
                                self.base / f"{name}-flexray-runtime" / file)
                self.assertLessEqual(gap, 2, (name, file))

    def test_the_grid_run_is_the_same_through_both_engines(self):
        ours = rows_by_file(self.base / "grid-blocks")
        self.assertEqual(ours, rows_by_file(self.base / "grid-flexray-runtime"))
        for row in ours.values():
            self.assertEqual((row["pose"]["sdd"], row["pose"]["delx"]), (1250.0, 0.6))
            self.assertEqual(row["isocentre"]["label"], None)
            self.assertEqual(row["isocentre"]["point_mm"], [-1.5, -1.5, -0.75])

    def test_under_moose_the_runtime_attenuates_no_name_flexray_drops(self):
        manifest = read_file(self.base / "moose-flexray-runtime", "manifest.json")
        self.assertEqual(manifest["labels"]["s0001"], moose_s0001())
        supervised = {str(i) for i in self.renderer.supervised_ids(self.renderer.label_lut())}
        opened = [row for row in manifest["views"] if row["attenuation"] is not None]
        self.assertGreaterEqual(len(opened), 1)
        for row in opened:
            self.assertFalse({"44", "83"} & set(row["attenuation"]), row["file"])
            self.assertTrue(set(row["attenuation"]) <= supervised, row["file"])
        held = {i for row in opened if row["subject"] == "s0001" for i in row["attenuation"]}
        self.assertTrue(held & {"32", "94"}, "the rib and the liver moosez labelled are attenuated")

    def test_the_factors_recorded_are_the_ones_flexrays_render_drr_drew(self):
        drawn = []
        with recording_factors(drawn):
            done = render(self.renderer, self.root, self.base / "recorded", [], self.roots,
                          engine="flexray-runtime")
        rows = rows_by_file(self.base / "recorded")
        self.assertEqual(rows, rows_by_file(self.base / "default-flexray-runtime"))
        check_factors(self, self.renderer, done, rows, drawn)


@unittest.skipIf(MISSING, f"needs {', '.join(MISSING)}")
class Segment(unittest.TestCase):
    """The segment subcommand with moosez kept out or stood in for: its plan from the corpus, its
    refusals (a zip missing, a part of one, a model whose dataset.json names a label otherwise),
    the subject list, the unpacking of a model zip, one run in the layout moosez's library entry
    writes and one in its command line's, and the line each run ends with."""

    @classmethod
    def setUpClass(cls):
        cls.base = Path(tempfile.mkdtemp(prefix="flexray-segment-"))
        cls.ct, _, cls.moose = make_corpus(cls.base)
        cls.renderer = load_tool("flexray_render")
        for model in cls.renderer.segment_models():
            write_mask(moose_file(cls.moose, "s0004", model), 120, [(1, 40, 60, MAIN)])
        cls.subjects = cls.base / "render-subjects.json"
        cls.subjects.write_text(json.dumps(
            {"ct": ["s0001", "batch/s0002", "s0003", "s0004", "nowhere"]}), encoding="utf-8")
        cls.empty = cls.base / "empty"
        cls.empty.mkdir()
        cls.zips = cls.base / "zips"
        write_model_zips(cls.renderer, cls.zips)
        cls.common = ["--segmenter", "moose", "--ct-root", str(cls.ct),
                      "--subjects", str(cls.subjects), "--out", str(cls.moose)]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base, ignore_errors=True)

    def run_words(self, out, zips):
        """The words of a run into out with the zips given, on the CPU."""
        return [*self.common[:-2], "--out", str(out), "--weights", str(zips), "--device", "cpu"]

    def test_the_plan_says_what_each_subject_lacks_and_touches_nothing_of_moosez(self):
        with mock.patch.dict(sys.modules, {"moosez": untouchable_moosez()}):
            code, (plan,), err, summary = segment(self.renderer, *self.common,
                                                  "--weights", str(self.empty), "--plan")
        self.assertEqual((code, err, summary, plan["moosez"]), (0, "", "", "importable"))
        self.assertEqual(plan["models"], list(self.renderer.segment_models()))
        by_id = {s["id"]: s for s in plan["subjects"]}
        self.assertEqual(list(by_id), ["s0001", "batch/s0002", "s0003", "s0004", "nowhere"])
        every = sorted(self.renderer.segment_models())
        self.assertEqual((by_id["s0001"]["action"], by_id["s0001"]["found"]), ("done", every))
        self.assertEqual(by_id["s0001"]["missing"], [])
        self.assertEqual(by_id["batch/s0002"]["found"], every)
        self.assertEqual((by_id["s0003"]["action"], by_id["s0003"]["found"]),
                         ("run", ["clin_ct_vertebrae"]))
        self.assertEqual(by_id["s0003"]["missing"], list(MODELS[:-1]))
        self.assertEqual((by_id["s0004"]["action"], by_id["s0004"]["missing"]), ("done", []))
        self.assertEqual((by_id["nowhere"]["action"], by_id["nowhere"]["ct"]), ("no CT", False))
        self.assertEqual(plan["to_run"], 1)
        self.assertEqual(len(plan["refusals"]), 5)
        self.assertIn("MOOSE's model zip clin_ct_organs_ras_07052025.zip (clin_ct_organs) is not "
                      "under --weights (fetch moose_weights first); never downloaded here",
                      plan["refusals"])
        self.assertEqual({w["present"] for w in plan["weights_found"].values()}, {False})
        self.assertEqual({w["whole"] for w in plan["weights_found"].values()}, {False})
        self.assertEqual(plan["weights_found"]["clin_ct_vertebrae"]["folder"],
                         "Dataset111_Vertebrae")
        self.assertIn("moosez.system.MODELS_DIRECTORY_PATH", plan["models_directory"])
        self.assertFalse((self.moose / "SEGMENT.json").exists())

    def test_the_run_is_refused_without_a_zip_and_without_moosez(self):
        with mock.patch.dict(sys.modules, {"moosez": None}):
            code, (plan,), err, summary = segment(self.renderer, *self.common,
                                                  "--weights", str(self.empty))
            self.assertEqual((code, plan["moosez"], summary), (2, "absent", ""))
            self.assertTrue(err.startswith(
                "segment: refused: MOOSE's model zip clin_ct_organs_ras_07052025.zip "
                "(clin_ct_organs) is not under --weights"), err)
            code, (plan,), err, _ = segment(self.renderer, *self.common,
                                            "--weights", str(self.zips))
            self.assertEqual((code, plan["refusals"]), (2, []))
            self.assertEqual(err, "segment: refused: moosez is not installed here; the plan above "
                                  "says what it would do\n")
            self.assertEqual({w["present"] for w in plan["weights_found"].values()}, {True})
            self.assertEqual({w["whole"] for w in plan["weights_found"].values()}, {True})
            self.assertTrue(all(w["bytes"] > 0 for w in plan["weights_found"].values()))
        self.assertFalse((self.moose / "SEGMENT.json").exists())
        self.assertFalse((self.moose / "s0001" / "CT_s0001.nii.gz").exists())

    def test_a_part_of_a_zip_is_refused_before_any_model_is_unpacked(self):
        """The fetch lands a zip under its final name while it downloads, so a part passes a
        size test; zipfile.is_zipfile rejects it, the plan says so, and the run is refused
        naming the resend that resumes it, with no model unpacked and moosez untouched."""
        renderer, calls = self.renderer, []
        parts = self.base / "parts"
        write_model_zips(renderer, parts)
        folder, url = renderer.moosez_metadata()["clin_ct_ribs"]
        (parts / renderer.zip_of(url)).write_bytes(b"PK\x03")
        with mock.patch.dict(sys.modules, {"moosez": untouchable_moosez()}):
            code, (plan,), err, _ = segment(renderer, *self.common, "--weights", str(parts),
                                            "--plan")
        self.assertEqual((code, err), (0, ""))
        ribs = plan["weights_found"]["clin_ct_ribs"]
        self.assertEqual((ribs["present"], ribs["whole"], ribs["bytes"]), (True, False, 3))
        self.assertEqual(sum(w["whole"] for w in plan["weights_found"].values()), 4)
        self.assertEqual(plan["refusals"], [
            "MOOSE's model zip clin_ct_ribs_ras_08052025.zip (clin_ct_ribs) under --weights is "
            f"not a whole zip (3 bytes, a part the fetch left): {RESEND}; never downloaded here"])
        out, models_dir = self.base / "moose-part", self.base / "models-part"
        modules = stand_in_moosez(renderer.moosez_metadata(), models_dir, calls)
        with mock.patch.dict(sys.modules, modules):
            code, (plan,), err, summary = segment(renderer, *self.run_words(out, parts))
        self.assertEqual((code, calls, summary), (2, [], ""))
        self.assertEqual(err, f"segment: refused: {plan['refusals'][0]}\n")
        self.assertFalse(out.exists())
        self.assertFalse(models_dir.exists(), "no model is unpacked beside a part")

    def test_spineps_and_a_third_segmenter_are_refused_with_the_reason(self):
        rest = [*self.common[2:], "--weights", str(self.zips), "--plan"]
        code, documents, err, _ = segment(self.renderer, "--segmenter", "spineps", *rest)
        self.assertEqual((code, documents), (2, []))
        self.assertEqual(err, f"segment: refused: {self.renderer.SPINEPS_REFUSAL}\n")
        self.assertIn("production array is not approved", err)
        code, documents, err, _ = segment(self.renderer, "--segmenter", "totalsegmentator", *rest)
        self.assertEqual((code, documents), (2, []))
        self.assertEqual(err, "segment: refused: segmenter 'totalsegmentator' is not one of "
                              "spineps, moose\n")

    def test_the_subject_list_is_read_at_the_ct_folders_name_or_as_a_plain_list(self):
        read_list = self.renderer.read_subject_list
        path = self.base / "list.json"
        for data, expected in ((["a", "b"], ["a", "b"]), ({"ct": ["a"]}, ["a"]),
                               ({"other": ["b"]}, ["b"]), ({"ct": ["a"], "other": ["b"]}, ["a"])):
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(read_list(path, self.ct), expected, data)
        for data in ({}, "words", 3):
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(self.renderer.SegmentError, "is not render-subjects.json"):
                read_list(path, self.ct)
        path.write_text(json.dumps({"a": [], "b": []}), encoding="utf-8")
        with self.assertRaisesRegex(self.renderer.SegmentError, "names the folders a, b and none"):
            read_list(path, self.ct)

    def test_a_model_zip_is_unpacked_once_into_the_folder_moosez_looks_in(self):
        renderer = self.renderer
        models = self.base / "models"
        folder, url = renderer.moosez_metadata()["clin_ct_vertebrae"]
        zip_path = self.zips / renderer.zip_of(url)
        self.assertEqual(renderer.unpack_model(zip_path, models, folder, url), "unpacked")
        self.assertTrue((models / folder / CONFIG / "plans.json").is_file())
        self.assertTrue((models / folder / CONFIG / "dataset.json").is_file())
        self.assertEqual(renderer.read_json(models / folder / "model_version.json"), {"url": url})
        self.assertEqual(renderer.unpack_model(zip_path, models, folder, url), "kept")
        self.assertEqual(renderer.unpack_model(zip_path, models, folder, url + "x"), "unpacked")
        evil = self.base / "evil.zip"
        write_zip(evil, {"../escaped.txt": "no"})
        with self.assertRaisesRegex(renderer.SegmentError, "outside its folder"):
            renderer.unpack_model(evil, models, "Dataset999", "u")
        self.assertFalse((self.base / "escaped.txt").exists())
        other = self.base / "other.zip"
        write_zip(other, {"Elsewhere/plans.json": "{}"})
        with self.assertRaisesRegex(renderer.SegmentError, "did not unpack to Dataset999"):
            renderer.unpack_model(other, models, "Dataset999", "u")

    def test_a_zip_that_is_not_whole_is_refused_in_words_not_a_traceback(self):
        """A part the fetch left, and a zip whose central directory is whole but whose member
        is not (what a download cut and resumed out of step leaves), each raise SegmentError
        naming the zip and the resend, where zipfile raised BadZipFile."""
        renderer = self.renderer
        models = self.base / "models-bad"
        part = self.base / "part.zip"
        part.write_bytes(b"PK\x03")
        with self.assertRaises(renderer.SegmentError) as found:
            renderer.unpack_model(part, models, "Dataset999", "u")
        self.assertTrue(str(found.exception).startswith("part.zip is not a whole zip ("))
        self.assertTrue(str(found.exception).endswith(f"): {RESEND}"))
        torn = self.base / "torn.zip"
        write_zip(torn, {"Dataset999/plans.json": "{}"})
        data = bytearray(torn.read_bytes())
        data[0:4] = b"XXXX"  # the member's local header, which extractall reads
        torn.write_bytes(bytes(data))
        self.assertTrue(zipfile.is_zipfile(torn), "the central directory still reads")
        with self.assertRaises(renderer.SegmentError) as found:
            renderer.unpack_model(torn, models, "Dataset999", "u")
        self.assertIn("torn.zip is not a whole zip (Bad magic number", str(found.exception))
        self.assertIn(RESEND, str(found.exception))
        self.assertFalse((models / "Dataset999" / "model_version.json").exists())

    def test_a_run_with_a_stand_in_moosez_links_the_ct_unpacks_the_zips_and_records(self):
        renderer, calls = self.renderer, []
        out, models_dir = self.base / "moose-run", self.base / "moosez-models"
        words = self.run_words(out, self.zips)
        modules = stand_in_moosez(renderer.moosez_metadata(), models_dir, calls)
        with mock.patch.dict(sys.modules, modules):
            code, (plan, done), err, summary = segment(renderer, *words)
        self.assertEqual((code, err, plan["to_run"]), (0, "", 4))
        every = list(renderer.segment_models())
        self.assertEqual(calls, [(f"CT_{name}.nii.gz", every, "cpu")
                                 for name in ("s0001", "s0002", "s0003", "s0004")])
        self.assertEqual(summary, "segment: 4 subjects run, 5 models, 20 files found, "
                                  f"0 not found, written under {out}")
        self.check_segment_record(out, models_dir, plan, done, "library")
        with mock.patch.dict(sys.modules, modules):
            code, (plan, done), err, summary = segment(renderer, *words)
        self.assertEqual((code, plan["to_run"], done, calls[4:]), (0, 0, {"done": []}, []))
        self.assertEqual(summary, "segment: 0 subjects run, 5 models, 0 files found, "
                                  f"0 not found, written under {out}")
        self.assertEqual(renderer.read_json(out / "SEGMENT.json")["weights"],
                         dict.fromkeys(every, "kept"))

    def test_a_run_whose_moosez_writes_the_command_lines_layout_is_read_the_same(self):
        renderer, calls = self.renderer, []
        out, models_dir = self.base / "moose-cli", self.base / "moosez-models-cli"
        modules = stand_in_moosez(renderer.moosez_metadata(), models_dir, calls, layout="cli")
        with mock.patch.dict(sys.modules, modules):
            code, (plan, done), err, summary = segment(renderer, *self.run_words(out, self.zips))
        self.assertEqual((code, err, len(calls)), (0, "", 4))
        self.assertEqual(summary, "segment: 4 subjects run, 5 models, 20 files found, "
                                  f"0 not found, written under {out}")
        self.check_segment_record(out, models_dir, plan, done, "cli")

    def check_segment_record(self, out, models_dir, plan, done, layout):
        """After the first run: the CT linked into the subject's folder and never read as a
        moosez output, SEGMENT.json with the plan, every zip unpacked where moosez looks and its
        labels checked, and every model's file found by the name moosez's source writes."""
        import numpy as np

        renderer, parts = self.renderer, load_tool("render_blocks")
        every = list(renderer.segment_models())
        link = out / "batch" / "s0002" / "CT_s0002.nii.gz"
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), (self.ct / "batch" / "s0002" / "ct.nii.gz").resolve())
        record = renderer.read_json(out / "SEGMENT.json")
        self.assertEqual((record["plan"], record["done"]), (plan, done["done"]))
        self.assertEqual(record["weights"], dict.fromkeys(every, "unpacked"))
        self.assertEqual(record["labels"], {
            m: {"dataset_json": f"{f}/{CONFIG}/dataset.json", "agrees": True,
                "values": len(renderer.schemes().MOOSEZ_MODELS[m])}
            for m, (f, _) in renderer.moosez_metadata().items()})
        self.assertEqual([d["id"] for d in record["done"]],
                         ["s0001", "batch/s0002", "s0003", "s0004"])
        for entry in record["done"]:
            self.assertEqual((entry["found"], entry["not_found"]), (sorted(every), []))
        for folder, _ in renderer.moosez_metadata().values():
            self.assertTrue((models_dir / folder / "model_version.json").is_file(), folder)
        # The files by the names moosez writes, the link beside them no candidate and not
        # recorded as unplaced, so the record's unplaced names moosez's own files alone.
        label, labels = parts.label_moose("s0001", grid_for(300), {"moose": out})
        self.assertEqual(labels["files"], {
            m: moosez_output(out, m, "CT_s0001", layout).name for m in every})
        self.assertEqual((labels["unplaced"], labels["models_missing"], labels["skipped"]),
                         ([], [], []))
        # Every model's file holds value 1 at one cube; the vertebrae model is merged last, so
        # the cube is its 1, vertebra_c1, MOOSE's 59.
        self.assertEqual(np.unique(label).tolist(), [0, 59])
        self.assertEqual(int((label == 59).sum()), 16 * 16 * 1)
        self.assertNotIn("CT_s0001.nii.gz",
                         [p.name for p, _ in parts.moose_candidates("s0001", out)])
        self.assertEqual(renderer.find_subjects(self.ct, segmenter="moose", roots={"moose": out}),
                         ["batch/s0002", "s0001", "s0003", "s0004"])

    def test_a_moosez_whose_metadata_differs_is_refused_before_anything_runs(self):
        renderer, calls = self.renderer, []
        metadata = dict(renderer.moosez_metadata())
        folder, url = metadata["clin_ct_ribs"]
        metadata["clin_ct_ribs"] = (folder, url.replace("3.1.3", "3.9.9"))
        out, models_dir = self.base / "moose-differs", self.base / "models-differs"
        modules = stand_in_moosez(metadata, models_dir, calls)
        with mock.patch.dict(sys.modules, modules):
            code, (plan,), err, _ = segment(renderer, *self.run_words(out, self.zips))
        self.assertEqual((code, calls, plan["moosez"]), (2, [], "importable"))
        self.assertIn("segment: refused: moosez's own metadata differs from this tool's copy, so "
                      "it would download: clin_ct_ribs: moosez names Dataset444_Ribs at", err)
        self.assertFalse(out.exists())
        self.assertFalse(models_dir.exists())

    def test_a_models_dataset_json_that_names_a_label_otherwise_is_refused(self):
        """moosez reads each model's labels from its unpacked dataset.json; this tool's table
        is the README's, so a drift between them is refused before any CT runs, while the
        README's spelling of the four renamed bones and MOOSE.yml's read as one name and a
        value written as an int reads as a string does."""
        renderer, calls = self.renderer, []
        segmenters = renderer.schemes()
        vertebrae = dict(segmenters.MOOSEZ_MODELS["clin_ct_vertebrae"])
        vertebrae[28] = "sacrum_bone"
        del vertebrae[1]
        bones = {v: segmenters.MOOSEZ_RENAMED.get(n, n).upper()
                 for v, n in segmenters.MOOSEZ_MODELS["clin_ct_peripheral_bones"].items()}
        zips = self.base / "zips-labels"
        write_model_zips(renderer, zips, {"clin_ct_vertebrae": (vertebrae, str),
                                          "clin_ct_peripheral_bones": (bones, int)})
        out, models_dir = self.base / "moose-labels", self.base / "models-labels"
        modules = stand_in_moosez(renderer.moosez_metadata(), models_dir, calls)
        with mock.patch.dict(sys.modules, modules):
            code, (plan,), err, summary = segment(renderer, *self.run_words(out, zips))
        self.assertEqual((code, calls, summary), (2, [], ""))
        self.assertEqual(err, (
            "segment: refused: a model's dataset.json names its labels otherwise than this "
            "tool's table (schwingnet.segmenters.MOOSEZ_MODELS), so the relabel tables would "
            "land on the wrong structures: clin_ct_vertebrae: value 1 is absent in its "
            "dataset.json and vertebra_c1 in this tool's table; clin_ct_vertebrae: value 28 is "
            "sacrum_bone in its dataset.json and sacrum in this tool's table\n"))
        self.assertNotIn("peripheral", err, "MOOSE.yml's spelling in capitals and ints agrees")
        self.assertFalse(out.exists())
        self.assertTrue((models_dir / "Dataset111_Vertebrae" / "model_version.json").is_file(),
                        "the zips are unpacked before the labels can be read")
        # The same zips less the drift run, into a fresh models directory, since a model already
        # unpacked under its URL is kept with the dataset.json it has: the record says each
        # model's labels agree.
        write_model_zips(renderer, zips, {"clin_ct_peripheral_bones": (bones, int)})
        modules = stand_in_moosez(renderer.moosez_metadata(), self.base / "models-labels-2", calls)
        with mock.patch.dict(sys.modules, modules):
            code, (plan, done), err, _ = segment(renderer, *self.run_words(out, zips))
        self.assertEqual((code, err, len(calls)), (0, "", 4))
        labels = renderer.read_json(out / "SEGMENT.json")["labels"]
        self.assertEqual({m: l["agrees"] for m, l in labels.items()},
                         dict.fromkeys(renderer.segment_models(), True))
        self.assertEqual(labels["clin_ct_peripheral_bones"]["values"], 31)

    def test_label_disagreements_read_both_spellings_as_one_name(self):
        renderer = self.renderer
        segmenters = renderer.schemes()
        for model, table in segmenters.MOOSEZ_MODELS.items():
            self.assertEqual(renderer.label_disagreements(model, table), [], model)
            renamed = {v: segmenters.MOOSEZ_RENAMED.get(n, n) for v, n in table.items()}
            self.assertEqual(renderer.label_disagreements(model, renamed), [], model)
        self.assertEqual(renderer.label_disagreements("clin_ct_ribs", {1: "rib_left_1", 2: "x"}),
                         ["clin_ct_ribs: value 2 is x in its dataset.json and rib_left_2 in "
                          "this tool's table"]
                         + [f"clin_ct_ribs: value {v} is absent in its dataset.json and {n} in "
                            "this tool's table"
                            for v, n in segmenters.MOOSEZ_MODELS["clin_ct_ribs"].items()
                            if v > 2])
        extra = {**segmenters.MOOSEZ_MODELS["clin_ct_cardiac"], 14: "aorta_arch"}
        self.assertEqual(renderer.label_disagreements("clin_ct_cardiac", extra),
                         ["clin_ct_cardiac: value 14 is aorta_arch in its dataset.json and "
                          "absent in this tool's table"])
        with self.assertRaisesRegex(renderer.SegmentError, "holds no configuration folder"):
            renderer.dataset_labels(self.base, "empty")
        bare = self.base / "bare" / CONFIG
        bare.mkdir(parents=True)
        (bare / "dataset.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(renderer.SegmentError, "has no labels for moosez to read"):
            renderer.dataset_labels(self.base, "bare")


if __name__ == "__main__":
    unittest.main()
