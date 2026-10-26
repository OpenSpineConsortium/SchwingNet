"""tools/domain_gap.py, the DRR domain-gap study's one job, run on made-up corpora: the plan takes
each group's files from a sample index or a folder by its rules (formats, modalities, sizes, globs,
masks left out, persons by rule with the frozen test persons dropped), the images come out as
256 x 256 windows of the centre square whatever their depth or shape, and a whole run over three
small corpora of different textures and the study's six render groups drawn by a fake renderer,
with only the physics space, writes a summary of at most 80 lines that survive the grid's
redaction, tells the textured corpora apart, finds nothing in its split-half nulls, renders the
six render groups from one choice of CTs under one salt, drawn among the CTs with masks under both
segmenters they name and passed the mask roots, and reads the five replication pairs with the
pre-registered word beside the two engine pairs; and the plan subcommand writes that choice alone,
without the masks the segment job makes, for that job to read.

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


class FakeRenderer:
    """tools/flexray_render as the run sees it (brief3's signatures): find_subjects lists the fake
    CT folders, and with a segmenter named only those with a mask file <subject>.nii.gz under
    roots[segmenter]; render_subjects writes one textured 16-bit PNG a view for the subject ids it
    is given, with a manifest in the renderer's shape, recording every call, so the test reads
    which subjects, salt, blocks, engine and roots each render group got; under spineps it passes
    the first subject over, as the renderer passes over a CT whose SPINEPS mask holds one L6
    alone, so the run's shared-subjects rule is exercised."""

    def __init__(self, rng, kind):
        self.rng, self.kind, self.calls, self.finds = rng, kind, [], []

    def find_subjects(self, ct_root, segmenter=None, roots=None):
        self.finds.append((segmenter, roots))
        found = sorted(p.name for p in Path(ct_root).iterdir() if p.is_dir())
        if segmenter is None:
            return found
        root = (roots or {}).get(segmenter)
        return [s for s in found if root is not None and (Path(root) / f"{s}.nii.gz").is_file()]

    def render_subjects(self, ct_root, out, subjects, salt, device, *, blocks, engine="blocks", subject_ids=None,
                        roots=None):
        self.calls.append({"group": Path(out).name, "subjects": subjects, "salt": salt, "device": device,
                           "blocks": blocks, "engine": engine, "subject_ids": subject_ids, "roots": roots})
        passed = list(subject_ids[:1]) if blocks.segmenter == "spineps" else []
        kept = [s for s in subject_ids if s not in passed]
        rows = []
        for subject in kept:
            for view in range(blocks.views):
                name = f"{subject}_v{view}.png"
                save_png(Path(out) / name, texture(self.rng, self.kind, 280), 16)
                rows.append({"file": name, "subject": subject, "view": view})
        (Path(out) / "manifest.json").write_text(json.dumps({"engine": engine, "views": rows}), encoding="utf-8")
        return {"rendered": len(rows), "subjects": kept,
                "skipped": [f"{s}: no structure FleXray supervises in its masks" for s in passed]}


CT_FOLDER = "totalsegmentator_v201"
SUBJECTS = [f"s{n:04d}" for n in range(30)]
# The fake masks: SPINEPS's for every CT but the last three, MOOSE's for every CT but s0001 and
# the last two, so 26 CTs have both and the choice of 24 is made among them.
SPINEPS_MASKED = SUBJECTS[:27]
MOOSE_MASKED = [s for s in SUBJECTS[:28] if s != "s0001"]
FLUXRAY_RAW = ["segmenter=moose", "crop=whole", "crop_sampler=uniform", "pose=fluxray-grid", "isocentre=volume-centre",
               "projection=cone", "attenuation=off", "scale=minmax", "detector=1024"]
# The study's six render groups at two views a CT: (id, blocks, engine, subjects_from).
RENDER_GROUPS = (("flexray_drr", ["segmenter=moose", "attenuation=off", "views=2"], "blocks", ""),
                 ("flexray_replica", ["segmenter=moose", "views=2"], "blocks", "flexray_drr"),
                 ("flexray_reference", ["segmenter=moose", "views=2"], "flexray-runtime", "flexray_drr"),
                 ("flexray_spineps", ["views=2"], "blocks", "flexray_drr"),
                 ("fluxray_raw", FLUXRAY_RAW + ["views=2"], "blocks", "flexray_drr"),
                 ("fluxray_raw_reference", FLUXRAY_RAW + ["views=2"], "flexray-runtime", "flexray_drr"))
PAIRS = ("flexray_replica|flexray_reference", "fluxray_raw|fluxray_raw_reference", "flexray_drr|flexray_replica",
         "flexray_spineps|flexray_replica", "fluxray_raw_reference|fluxray")


def ranked(tool, subjects, salt="test-salt"):
    """The subjects in the order the study chooses them: by rank_key("<salt>:subjects", id)."""
    pure = tool.rules()
    return sorted(subjects, key=lambda s: (pure.rank_key(f"{salt}:subjects", s), s))


def make_cts(folder, masks):
    """The fake CT folders under the data root and a mask file a subject under each root given,
    {root: [subjects]}."""
    for subject in SUBJECTS:
        (folder / "data" / CT_FOLDER / subject).mkdir(parents=True, exist_ok=True)
    for root, subjects in masks.items():
        root.mkdir(parents=True, exist_ok=True)
        for subject in subjects:
            (root / f"{subject}.nii.gz").write_bytes(b"")


def render_rows(cap=48, per_person=2):
    return [{"id": name, "label": name, "family": "synthetic", "source": "render", "folder": CT_FOLDER,
             "cap": cap, "per_person": per_person, "blocks": blocks, "engine": engine, "subjects_from": subjects_from}
            for name, blocks, engine, subjects_from in RENDER_GROUPS]


@unittest.skipIf(MISSING_WHOLE, f"needs {', '.join(MISSING_WHOLE)}")
class WholeRunTest(unittest.TestCase):
    def test_a_run_over_three_textured_corpora_and_six_render_groups(self):
        tool = load_tool()
        tool.PERMUTATIONS_C2ST, tool.PERMUTATIONS_MMD, tool.BOOTSTRAP = 5, 50, 50
        tool.SPLIT_PERSONS = 12
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            args, renderer = self.corpora(tool, folder)
            self.assertEqual(tool.run(args), 0)
            lines = (Path(args.out) / "summary.txt").read_text(encoding="ascii").splitlines()
            results = json.loads((Path(args.out) / "results.json").read_text(encoding="utf-8"))
            plan = json.loads((Path(args.out) / "plan.json").read_text(encoding="utf-8"))
            subjects_file = json.loads((Path(args.out) / "render-subjects.json").read_text(encoding="utf-8"))
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
        self.renders_share_their_subjects(tool, renderer, plan, subjects_file, folder)
        self.replication_is_tested_and_summarised(tool, results, lines)

    def renders_share_their_subjects(self, tool, renderer, plan, subjects_file, folder):
        """The six render groups were rendered from one choice of CTs, the first 24 in the salted
        order of the 26 that have masks under both segmenters the folder's groups name, under the
        folder's salt, each with its own blocks, engine and segmenter, the mask roots passed
        through; the plan and render-subjects.json record the choice and its counts."""
        self.assertEqual([c["group"] for c in renderer.calls], [g for g, _, _, _ in RENDER_GROUPS])
        both = sorted(set(SPINEPS_MASKED) & set(MOOSE_MASKED))
        self.assertEqual(len(both), 26)
        expected = ranked(tool, both)[:24]
        first = renderer.calls[0]
        self.assertEqual(list(first["subject_ids"]), expected)
        self.assertEqual(first["subjects"], 24)
        self.assertEqual(first["salt"], f"test-salt:{CT_FOLDER}")
        roots = {"spineps": folder / "data" / "spineps", "moose": folder / "data" / "moose"}
        for call in renderer.calls:
            self.assertEqual(list(call["subject_ids"]), expected)
            self.assertEqual(call["salt"], first["salt"])
            self.assertEqual(call["device"], "cpu")
            self.assertEqual(call["roots"], roots)
        self.assertEqual([c["blocks"].segmenter for c in renderer.calls],
                         ["moose", "moose", "moose", "spineps", "moose", "moose"])
        self.assertEqual([c["blocks"].attenuation for c in renderer.calls],
                         ["off", "flexray-lognormal", "flexray-lognormal", "flexray-lognormal", "off", "off"])
        self.assertEqual([c["blocks"].pose for c in renderer.calls[4:]], ["fluxray-grid", "fluxray-grid"])
        self.assertEqual([c["engine"] for c in renderer.calls],
                         ["blocks", "blocks", "flexray-runtime", "blocks", "blocks", "flexray-runtime"])
        # The masks were looked for under each root once, for the folder.
        self.assertEqual([(s, r) for s, r in renderer.finds if s], [("moose", roots), ("spineps", roots)])
        rows = {g["id"]: g for g in plan["groups"]}
        records = [rows[g]["render"] for g, _, _, _ in RENDER_GROUPS]
        self.assertEqual({tuple(r["subjects"]) for r in records}, {tuple(expected)})
        self.assertEqual([r["blocks"]["segmenter"] for r in records],
                         ["moose", "moose", "moose", "spineps", "moose", "moose"])
        self.assertEqual(records[0]["rendered"], 48)
        self.assertEqual(subjects_file, {CT_FOLDER: expected})
        # The subject flexray_spineps passed over is in no group's rows: every group's shared list
        # is the other 23, flexray_drr kept it outside that set, and the plan says so.
        first, shared = expected[0], expected[1:]
        spineps = rows["flexray_spineps"]["render"]
        self.assertEqual((spineps["kept"], spineps["unshared"]), (shared, []))
        self.assertEqual(spineps["passed_over"], [f"{first}: no structure FleXray supervises in its masks"])
        self.assertEqual({tuple(r["shared"]) for r in records}, {tuple(shared)})
        self.assertEqual((records[0]["kept"], records[0]["unshared"]), (expected, [first]))
        for group, _, _, _ in RENDER_GROUPS:
            self.assertEqual(len(rows[group]["chosen"]), 46, group)
            self.assertFalse(any(p.endswith(f":{first}") for _, p in rows[group]["chosen"]), group)
        self.assertEqual(plan["renders"], {CT_FOLDER: {
            "subjects": expected, "segmenters": ["moose", "spineps"], "pending": [],
            "roots": {"moose": "found", "spineps": "found"}, "ct": 30, "masks": {"moose": 27, "spineps": 27},
            "every": 26, "count": 24, "shared": shared}})

    def replication_is_tested_and_summarised(self, tool, results, lines):
        """The replication section holds the five pairs, the two engine pairs with the
        pre-registered word from their own numbers, the FluXray pair with its reason; the verdict
        names the space that did not run; and the summary carries the lines, the folder's mask
        counts among them, with the render groups' equal counts folded."""
        pure = tool.rules()
        replication = results["spaces"]["physics"]["replication"]
        self.assertEqual(set(replication), set(PAIRS))
        for pair in PAIRS[:2]:
            found = replication[pair]
            for key in ("auc_logistic", "auc_knn", "mmd", "fd64", "kid64", "prdc"):
                self.assertIn(key, found)
            self.assertIn("p", found["auc_logistic"])
            self.assertIn("q", found["mmd"])
            self.assertEqual(found["word"], pure.replication_word(found["auc_logistic"]["lo"], found["mmd"]["q"]))
            self.assertEqual(found["word"], "replicated")  # draws of one texture law
        for pair in PAIRS[2:4]:
            self.assertNotIn("word", replication[pair])
            self.assertIn("auc_logistic", replication[pair])
        self.assertIn("fluxray: not in the table", replication["fluxray_raw_reference|fluxray"]["skipped"])
        verdict = results["replication"]
        self.assertIsNone(verdict["word"])
        self.assertIn("space flexray not run", verdict["reason"])
        self.assertEqual(set(verdict["pairs"]), set(PAIRS[:2]))
        self.assertEqual(results["renders"][CT_FOLDER]["every"], 26)
        self.assertTrue(lines[1].startswith("replication flexray_replica vs flexray_reference: no verdict"))
        self.assertTrue(lines[2].startswith("replication fluxray_raw vs fluxray_raw_reference: no verdict"))
        self.assertEqual(lines[3], f"render {CT_FOLDER}: 24 CTs chosen of 26 with every mask of 30 CTs "
                                   "(moose 27, spineps 27); 23 kept by every group")
        self.assertIn("group flexray_replica synthetic counts as flexray_drr", lines)
        self.assertEqual(sum(1 for line in lines if line.startswith("group ")), 9)
        for pair in PAIRS[:2]:
            a, b = pair.split("|")
            pair_lines = [line for line in lines if line.startswith(f" replication {a} vs {b} auc")]
            self.assertEqual(len(pair_lines), 1)
            self.assertTrue(pair_lines[0].endswith(" replicated"))
        self.assertTrue(any(line.startswith(" replication flexray_spineps vs flexray_replica auc") for line in lines))
        self.assertTrue(any(line.startswith(" replication fluxray_raw_reference vs fluxray not tested") for line in lines))

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
        # The mask roots at their defaults under the data root.
        make_cts(folder, {folder / "data" / "spineps": SPINEPS_MASKED, folder / "data" / "moose": MOOSE_MASKED})
        groups += render_rows()
        renderer = FakeRenderer(np.random.default_rng(12), "blobs")
        original = tool.tool
        tool.tool = lambda name: renderer if name == "flexray_render" else original(name)
        return args_for(tool, folder, table(folder, groups), index_of(folder, [])), renderer


@unittest.skipIf(MISSING_BASE, f"needs {', '.join(MISSING_BASE)}")
class PlanSubcommandTest(unittest.TestCase):
    """The plan subcommand chooses the CTs as the run does, less the masks the segment job makes
    (MOOSE's), and writes render-subjects.json alone: the grid's segment job reads it before any
    MOOSE mask exists."""

    def setUp(self):
        self.tool = load_tool()
        self.temporary = tempfile.TemporaryDirectory()
        self.folder = Path(self.temporary.name)
        self.renderer = FakeRenderer(None, "blobs")
        original = self.tool.tool
        self.tool.tool = lambda name: self.renderer if name == "flexray_render" else original(name)

    def tearDown(self):
        self.temporary.cleanup()

    def plan(self, groups, spineps, moose):
        film = {"id": "films", "label": "films", "family": "film", "source": "walk", "folder": "films", "cap": 10,
                "per_person": 1}
        return self.tool.main(["plan", "--groups", str(table(self.folder, groups + [film])), "--data-root",
                               str(self.folder / "data"), "--out", str(self.folder / "out"),
                               "--spineps", str(spineps), "--moose", str(moose)])

    def test_the_plan_chooses_without_the_masks_the_segment_job_makes(self):
        spineps, moose = self.folder / "masks" / "spineps", self.folder / "masks" / "moose"
        make_cts(self.folder, {spineps: SPINEPS_MASKED})  # no MOOSE mask exists yet
        self.assertEqual(self.plan(render_rows(), spineps, moose), 0)
        out = self.folder / "out"
        written = json.loads((out / "render-subjects.json").read_text(encoding="utf-8"))
        self.assertEqual(written, {CT_FOLDER: ranked(self.tool, SPINEPS_MASKED)[:24]})
        self.assertEqual(sorted(p.name for p in out.iterdir()), ["render-subjects.json"])
        self.assertEqual(self.renderer.calls, [])
        self.assertEqual([s for s, _ in self.renderer.finds], [None, "spineps"])
        # Once the segment job has made MOOSE's masks for those CTs, the run's choice, over both
        # segmenters, is the same list.
        make_cts(self.folder, {moose: written[CT_FOLDER]})
        roots = self.tool.mask_roots(self.tool.parse(["run", "--data-root", str(self.folder / "data"), "--out",
                                                      str(out), "--spineps", str(spineps), "--moose", str(moose)]))
        folders = self.tool.render_folders(
            self.tool.parse(["run", "--data-root", str(self.folder / "data"), "--out", str(out)]),
            self.tool.read_table(self.folder / "groups.json"), self.renderer, roots)
        self.assertEqual(folders[CT_FOLDER]["subjects"], written[CT_FOLDER])
        self.assertEqual((folders[CT_FOLDER]["masks"], folders[CT_FOLDER]["every"]), ({"moose": 24, "spineps": 27}, 24))

    def test_groups_naming_moose_alone_are_planned_over_every_ct(self):
        spineps, moose = self.folder / "masks" / "spineps", self.folder / "masks" / "moose"
        make_cts(self.folder, {})
        groups = [g for g in render_rows() if g["id"] != "flexray_spineps"]
        self.assertEqual(self.plan(groups, spineps, moose), 0)
        written = json.loads((self.folder / "out" / "render-subjects.json").read_text(encoding="utf-8"))
        self.assertEqual(written, {CT_FOLDER: ranked(self.tool, SUBJECTS)[:24]})

    def test_a_folder_with_no_ct_to_choose_fails_the_plan(self):
        spineps, moose = self.folder / "masks" / "spineps", self.folder / "masks" / "moose"
        make_cts(self.folder, {spineps: []})
        self.assertEqual(self.plan(render_rows(), spineps, moose), 2)
        written = json.loads((self.folder / "out" / "render-subjects.json").read_text(encoding="utf-8"))
        self.assertEqual(written, {CT_FOLDER: []})


if __name__ == "__main__":
    sys.exit(unittest.main())
