"""tools/domain_gap.py, the DRR domain-gap study's one job, run on made-up corpora: the plan takes
each group's files from a sample index or a folder by its rules (formats, modalities, sizes, globs,
masks left out, persons by rule with the frozen test persons dropped), the images come out as
256 x 256 windows of the centre square whatever their depth or shape, and a whole run over three
small corpora of different textures and the study's seven render groups drawn by a fake renderer,
with only the physics space, writes a summary of five record lines and at most 80 more that survive the grid's
redaction, tells the textured corpora apart, finds nothing in its split-half nulls, renders the
seven render groups from one choice of CTs under one salt, drawn among the CTs with masks under
both segmenters they name and passed the mask roots, and reads the six replication pairs with the
pre-registered word beside the two engine pairs; the groups on segmenter none render from the CT
alone, so where a segmenter's masks are not read, no folder of them or --skip-masks naming it,
the CTs are chosen without them, the groups naming that segmenter are skipped with the reason and
the others render; twin renders, one CT's view under two engines,
are read as the paired sample they are, so identical twins read an AUC of one half and a gamma
curve between them reads "not replicated", where twins keyed as persons of their own read neither;
a second run after a mask lands makes the plan, the rows and the features again; a render group
that kept no CT is out of the shared set and its plan row says so; the verdict and replication
lines carry the persons and rows they rest on within the report's line; and the plan subcommand
writes that choice alone, without the masks the segment job makes, for that job to read.

It needs numpy, Pillow, torch, scikit-learn and the package's contracts, which the job's
environment holds and the required check's python does not, so each case runs where they import
and is skipped elsewhere.

    <venv>/bin/python -m unittest tests/test_domain_gap_run.py
"""

import contextlib
import importlib.util
import io
import json
import re
import shutil
import sqlite3
import sys
import tempfile
import unittest
import unittest.mock
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

    def test_an_index_rebuilt_at_the_same_path_makes_the_plan_again(self):
        """The plan's stamp reads the sample index by its size and modification time, not its
        path alone, so a samples.sqlite rebuilt where the old one stood (more files indexed
        after a failed job) is planned again rather than read from the old plan's file list."""
        index = index_of(self.folder, self.index_rows())
        groups = table(self.folder, self.groups())
        args = args_for(self.tool, self.folder, groups, index)
        Path(args.out).mkdir(parents=True)
        first = self.tool.stage_plan(args, self.tool.read_table(groups))
        self.assertEqual(first["groups"][0]["found"], 12)
        more = [(f"/x/carmlspine/images/train/case7_{v}.png", f"carmlspine/images/train/case7_{v}.png", "png",
                 "1024", "1024", None, None, None, None, "image", None, "unmapped:realxray") for v in ("ap", "lat")]
        with sqlite3.connect(index) as connection:
            connection.executemany("INSERT INTO sample VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", more)
        again = self.tool.stage_plan(args, self.tool.read_table(groups))
        self.assertEqual(again["groups"][0]["found"], 14)
        self.assertNotEqual(again["stamp"]["index"], first["stamp"]["index"])
        self.assertTrue(again["stamp"]["index"].startswith(str(index)))
        self.assertEqual(self.tool.index_stamp(""), "")
        self.assertEqual(self.tool.index_stamp(str(self.folder / "absent.sqlite")), str(self.folder / "absent.sqlite"))

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
    which subjects, salt, blocks, engine and roots each render group got. passes says how many of
    the leading subjects each group (by its folder's name) passes over, as the renderer passes
    over a CT whose SPINEPS mask holds one L6 alone: one for flexray_spineps unless told
    otherwise, so the run's shared-subjects rule is exercised. With twins, a subject's view is one
    image under every group, drawn from the subject and the view alone, as two engines render
    one CT from one seed; shifts raises a group's images to the named gamma, a brightness curve
    the other engine lacks, a real difference between twins."""

    def __init__(self, rng, kind, *, passes=None, twins=False, shifts=None, seed=12):
        self.rng, self.kind, self.calls, self.finds = rng, kind, [], []
        self.passes = {"flexray_spineps": 1} if passes is None else passes
        self.twins, self.shifts, self.seed = twins, shifts or {}, seed

    def find_subjects(self, ct_root, segmenter=None, roots=None):
        self.finds.append((segmenter, roots))
        found = sorted(p.name for p in Path(ct_root).iterdir() if p.is_dir())
        if segmenter is None:
            return found
        root = (roots or {}).get(segmenter)
        return [s for s in found if root is not None and (Path(root) / f"{s}.nii.gz").is_file()]

    def image(self, group, subject, view):
        """One view's image: the stream's next texture, or with twins the texture of the subject
        and the view, under every group the same, raised to the group's gamma where it has one."""
        import numpy as np

        rng = np.random.default_rng((self.seed, int(subject[1:]), view)) if self.twins else self.rng
        return np.clip(texture(rng, self.kind, 280), 0.0, 1.0) ** self.shifts.get(group, 1.0)

    def render_subjects(self, ct_root, out, subjects, salt, device, *, blocks, engine="blocks", subject_ids=None,
                        roots=None):
        group = Path(out).name
        self.calls.append({"group": group, "subjects": subjects, "salt": salt, "device": device,
                           "blocks": blocks, "engine": engine, "subject_ids": subject_ids, "roots": roots})
        passed = list(subject_ids[:self.passes.get(group, 0)])
        kept = [s for s in subject_ids if s not in passed]
        rows = []
        for subject in kept:
            for view in range(blocks.views):
                name = f"{subject}_v{view}.png"
                save_png(Path(out) / name, self.image(group, subject, view), 16)
                rows.append({"file": name, "subject": subject, "view": view})
        Path(out).mkdir(parents=True, exist_ok=True)
        (Path(out) / "manifest.json").write_text(json.dumps({"engine": engine, "views": rows}), encoding="utf-8")
        return {"rendered": len(rows), "subjects": kept,
                "skipped": [f"{s}: no structure FleXray supervises in its masks" for s in passed]}


CT_FOLDER = "totalsegmentator_v201"
SUBJECTS = [f"s{n:04d}" for n in range(30)]
# The fake masks: SPINEPS's for every CT but the last three, MOOSE's for every CT but s0001 and
# the last two, so 26 CTs have both and the choice of 24 is made among them.
SPINEPS_MASKED = SUBJECTS[:27]
MOOSE_MASKED = [s for s in SUBJECTS[:28] if s != "s0001"]
FLUXRAY_RAW = ["segmenter=none", "crop=whole", "crop_sampler=uniform", "pose=fluxray-grid", "isocentre=volume-centre",
               "projection=cone", "attenuation=off", "scale=minmax", "detector=1024"]
PHYSICAL_CT = ["segmenter=none", "crop_sampler=uniform", "isocentre=volume-centre", "attenuation=off"]
# The study's seven render groups at two views a CT: (id, blocks, engine, subjects_from).
RENDER_GROUPS = (("flexray_drr", ["segmenter=moose", "attenuation=off", "views=2"], "blocks", ""),
                 ("flexray_drr_ct", PHYSICAL_CT + ["views=2"], "blocks", "flexray_drr"),
                 ("flexray_replica", ["segmenter=moose", "views=2"], "blocks", "flexray_drr"),
                 ("flexray_reference", ["segmenter=moose", "views=2"], "flexray-runtime", "flexray_drr"),
                 ("flexray_spineps", ["views=2"], "blocks", "flexray_drr"),
                 ("fluxray_raw", FLUXRAY_RAW + ["views=2"], "blocks", "flexray_drr"),
                 ("fluxray_raw_reference", FLUXRAY_RAW + ["views=2"], "flexray-runtime", "flexray_drr"))
PAIRS = ("flexray_replica|flexray_reference", "fluxray_raw|fluxray_raw_reference", "flexray_drr_ct|flexray_drr",
         "flexray_drr|flexray_replica", "flexray_spineps|flexray_replica", "fluxray_raw_reference|fluxray")
# The render groups that read no mask, and those that read MOOSE's.
MASK_FREE = ("flexray_drr_ct", "fluxray_raw", "fluxray_raw_reference")
MOOSE_GROUPS = ("flexray_drr", "flexray_replica", "flexray_reference")
# The gamma the twin test raises flexray_reference's images to: a curve the physics features see
# as a shift under the paired reading and the keying before the fix reads as none (measured
# 2026-10-26 on this fixture, 24 CTs x 2 views: paired AUC 0.60 and MMD p at its floor, the other
# keying AUC 0.45 and MMD p 0.45).
GAMMA = 1.2


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
    def test_a_run_over_three_textured_corpora_and_seven_render_groups(self):
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
        """The seven render groups were rendered from one choice of CTs, the first 24 in the salted
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
                         ["moose", "none", "moose", "moose", "spineps", "none", "none"])
        self.assertEqual([c["blocks"].attenuation for c in renderer.calls],
                         ["off", "off", "flexray-lognormal", "flexray-lognormal", "flexray-lognormal", "off", "off"])
        self.assertEqual([c["blocks"].pose for c in renderer.calls[5:]], ["fluxray-grid", "fluxray-grid"])
        self.assertEqual([c["engine"] for c in renderer.calls],
                         ["blocks", "blocks", "blocks", "flexray-runtime", "blocks", "blocks", "flexray-runtime"])
        # The masks were looked for under each root once, for the folder.
        self.assertEqual([(s, r) for s, r in renderer.finds if s], [("moose", roots), ("spineps", roots)])
        rows = {g["id"]: g for g in plan["groups"]}
        records = [rows[g]["render"] for g, _, _, _ in RENDER_GROUPS]
        self.assertEqual({tuple(r["subjects"]) for r in records}, {tuple(expected)})
        self.assertEqual([r["blocks"]["segmenter"] for r in records],
                         ["moose", "none", "moose", "moose", "spineps", "none", "none"])
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
            "subjects": expected, "segmenters": ["moose", "spineps"], "pending": [], "thin": {},
            "roots": {"moose": "found", "spineps": "found"}, "ct": 30, "masks": {"moose": 27, "spineps": 27},
            "every": 26, "count": 24, "shared": shared}})

    def replication_is_tested_and_summarised(self, tool, results, lines):
        """The replication section holds the six pairs, the two engine pairs with the
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
        for pair in PAIRS[2:5]:
            self.assertNotIn("word", replication[pair])
            self.assertIn("auc_logistic", replication[pair])
        self.assertIn("fluxray: not in the table", replication["fluxray_raw_reference|fluxray"]["skipped"])
        verdict = results["replication"]
        self.assertIsNone(verdict["word"])
        self.assertIn("space flexray not run", verdict["reason"])
        self.assertEqual(set(verdict["pairs"]), set(PAIRS[:2]))
        self.assertEqual(results["renders"][CT_FOLDER]["every"], 26)
        # the header, then the run's record in five lines the CLAIM report reads, then the verdicts
        # the record first, which the study's report reads from the top, then the header and the verdicts
        self.assertEqual([line.split(" ")[1] for line in lines[0:5]], ["study", "jobs", "units", "seconds", "environment"])
        self.assertTrue(all(line.startswith("record: ") for line in lines[0:5]))
        self.assertTrue(lines[1].startswith("record: jobs run local; GPUs cpu x1"), lines[1])
        self.assertNotIn("units 0 (summed)", lines[3])
        self.assertTrue(lines[5].startswith("drr gap: "), lines[5])
        self.assertTrue(lines[6].startswith("replication flexray_replica vs flexray_reference: no verdict"))
        self.assertTrue(lines[7].startswith("replication fluxray_raw vs fluxray_raw_reference: no verdict"))
        self.assertEqual(lines[8], f"render {CT_FOLDER}: 24 CTs chosen of 26 with every mask of 30 CTs "
                                   "(moose 27, spineps 27); 23 kept by every group")
        self.assertIn("groups counted as flexray_drr: flexray_drr_ct flexray_replica flexray_reference flexray_spineps"
                      " fluxray_raw fluxray_raw_reference", lines)
        self.assertEqual(sum(1 for line in lines if line.startswith("group ")), 4)
        self.replication_lines_carry_the_counts(replication, lines)

    def replication_lines_carry_the_counts(self, replication, lines):
        """Each engine pair, a paired sample of the folder's 23 shared CTs, has one replication
        line opening with its persons and rows a side and ending with its word; the untested
        FluXray pair's line says so."""
        for pair in PAIRS[:2]:
            a, b = pair.split("|")
            head = f" replication {a} vs {b} persons 23/23 n 46/46 auc"
            pair_lines = [line for line in lines if line.startswith(head)]
            self.assertEqual(len(pair_lines), 1)
            self.assertTrue(pair_lines[0].endswith(" replicated"))
            self.assertTrue(replication[pair]["paired"])
        self.assertTrue(any(line.startswith(" replication flexray_spineps vs flexray_replica persons 23/23 n 46/46")
                            for line in lines))
        self.assertTrue(any(line.startswith(" replication fluxray_raw_reference vs fluxray not tested") for line in lines))

    def test_twin_renders_read_replicated_and_a_gamma_between_them_not_replicated(self):
        """Two engines rendering one CT from one seed give twins: identical views read an AUC of
        one half, a degenerate interval and "replicated" because a twin pair is a paired sample,
        every CT's rows in one fold on both sides and its two sides moved together by the
        interval and the permutations (contrast); analysed as persons of their own, the keying
        before the fix, the classifier learns each CT from the other side, the AUC falls far
        below one half and the free permutation's MMD p sits at one, which the pre-registered
        rule reads as "replicated" whatever the engines differ by. A gamma curve on the reference
        alone reads "not replicated" under the paired reading and "replicated" under the other.
        The MMD takes the study's own 1,000 permutations: its q is read over the space's contrasts
        and its split-half nulls (PREREG.md section 3, DEVIATIONS.md item 11), here 12 p-values,
        and 200 permutations floor a p at 0.005, which those 12 lift to a q of 0.06, over the bar
        however far the gamma moves the reference."""
        tool = load_tool()
        tool.PERMUTATIONS_C2ST, tool.PERMUTATIONS_MMD, tool.BOOTSTRAP = 5, 1000, 50
        tool.SPLIT_PERSONS = 12
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            renderer = FakeRenderer(None, "blobs", passes={}, twins=True, shifts={"flexray_reference": GAMMA})
            args = self.render_corpora(tool, folder, renderer)
            self.assertEqual(tool.run(args), 0)
            lines = (Path(args.out) / "summary.txt").read_text(encoding="ascii").splitlines()
            results = json.loads((Path(args.out) / "results.json").read_text(encoding="utf-8"))
            before = {pair: self.contrast_as_before(tool, Path(args.out), pair) for pair in PAIRS[:2]}
        replication = results["spaces"]["physics"]["replication"]
        shifted, same = replication[PAIRS[0]], replication[PAIRS[1]]
        for found in (shifted, same):
            self.assertTrue(found["paired"])
            self.assertEqual((found["persons"], found["n"]), ([24, 24], [48, 48]))
        self.assertEqual(same["word"], "replicated")
        auc = same["auc_logistic"]
        self.assertEqual((auc["auc"], auc["lo"], auc["hi"], same["auc_knn"]["auc"]), (0.5, 0.5, 0.5, 0.5))
        self.assertEqual(shifted["word"], "not replicated")
        self.assertLess(shifted["mmd"]["q"], 0.05)
        self.assertLessEqual(shifted["mmd"]["q_without_nulls"], shifted["mmd"]["q"])
        self.assert_worded_lines(lines)
        self.assert_read_as_before(tool, before, shifted)

    def assert_worded_lines(self, lines):
        """Each twin pair's replication line opens with its counts and ends with its word."""
        for pair, word in ((PAIRS[1], " replicated"), (PAIRS[0], " not replicated")):
            a, b = pair.split("|")
            head = f" replication {a} vs {b} persons 24/24 n 48/48 auc"
            self.assertTrue(any(line.startswith(head) and line.endswith(word) for line in lines), pair)

    def assert_read_as_before(self, tool, before, shifted):
        """Keyed as persons of their own, twins read a shift as none and no shift as a shift: the
        identical pair's AUC falls far below one half, and the shifted pair's MMD, the same
        statistic as the paired reading's, sits inside the free permutation's null."""
        import numpy as np

        for pair, found in before.items():
            self.assertFalse(found["paired"], pair)
            word = tool.rules().replication_word(found["auc_logistic"]["lo"], found["mmd"]["p"])
            self.assertEqual(word, "replicated", pair)
        self.assertLess(before[PAIRS[1]]["auc_logistic"]["auc"], 0.25)
        self.assertTrue(np.isclose(before[PAIRS[0]]["mmd"]["mmd2"], shifted["mmd"]["mmd2"]))

    def contrast_as_before(self, tool, out, pair):
        """The pair's contrast on the run's physics features with every render's person keyed by
        its group, the keying before the review of 2026-10-26 (F22): each CT two persons."""
        import numpy as np

        rows = json.loads((out / "rows.json").read_text(encoding="utf-8"))
        plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
        data = np.load(out / "features" / "physics.npz")
        for row in rows["rows"]:
            row["person"] = f"{row['group']}:{row['person']}"
        frame = tool.Frame((data["stored"] + data["inverse"]) / 2.0, rows["rows"], plan)
        s = tool.stats()
        z = s.standardise(frame.x)
        z64, _ = s.pca(z, min(64, z.shape[1], len(z) - 1), seed=0)
        a, b = pair.split("|")
        return tool.contrast(frame, z64, frame.rows_of(a), frame.rows_of(b), 0)

    def test_a_second_run_after_a_mask_lands_makes_the_plan_the_rows_and_the_features_again(self):
        """The stages are kept for the same inputs and made again for new ones: s0001 has no MOOSE
        mask in the fixture and ranks among the first 24 CTs in the salted order, so once its mask
        lands (a segment job finishing what a cut one left) the choice of CTs changes, and the
        plan, rows.json and the physics features follow; a third pass changes nothing."""
        import numpy as np

        tool = load_tool()
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            args = self.render_corpora(tool, folder, FakeRenderer(np.random.default_rng(5), "blobs"))
            table = tool.read_table(args.groups)
            first = self.stages(tool, args, table)
            (folder / "data" / "moose" / "s0001.nii.gz").write_bytes(b"")
            second = self.stages(tool, args, table)
            third = self.stages(tool, args, table)
        self.assertNotIn("s0001", first["subjects"])
        self.assertIn("s0001", second["subjects"])
        self.assertEqual(first["masks"], {"moose": 27, "spineps": 27})
        self.assertEqual(second["masks"], {"moose": 28, "spineps": 27})
        self.assertNotEqual(first["plan"], second["plan"])
        self.assertNotIn(f"{CT_FOLDER}:s0001", first["persons"])
        self.assertIn(f"{CT_FOLDER}:s0001", second["persons"])
        self.assertEqual(first["features"], first["plan"])
        self.assertEqual(second["features"], second["plan"])
        self.assertEqual(third, second)

    def stages(self, tool, args, table):
        """The render, plan, image and feature stages once, and what they left: the folder's choice
        and mask counts, the plan digest the rows carry, the rows' persons, the plan the physics
        features carry and the three files' modification times."""
        import numpy as np

        renders, folders = tool.stage_render(args, table)
        plan = tool.stage_plan(args, table, renders, folders)
        rows, images = tool.stage_images(args, plan)
        tool.stage_features(args, images, rows)
        out = Path(args.out)
        return {"subjects": folders[CT_FOLDER]["subjects"], "masks": folders[CT_FOLDER]["masks"], "plan": rows["plan"],
                "persons": sorted({r["person"] for r in rows["rows"]}),
                "features": str(np.load(out / "features" / "physics.npz")["plan"]),
                "written": [(out / name).stat().st_mtime_ns
                            for name in ("plan.json", "rows.json", "features/physics.npz")]}

    def render_corpora(self, tool, folder, renderer, cap=48):
        """The seven render groups alone, with a film group whose folder is absent (a table sets
        two families beside each other), the mask roots at their defaults under the data root and
        the fake renderer in the tool's place."""
        make_cts(folder, {folder / "data" / "spineps": SPINEPS_MASKED, folder / "data" / "moose": MOOSE_MASKED})
        films = {"id": "films", "label": "films", "family": "film", "source": "walk", "folder": "films", "cap": 10,
                 "per_person": 1}
        original = tool.tool
        tool.tool = lambda name: renderer if name == "flexray_render" else original(name)
        args = args_for(tool, folder, table(folder, render_rows(cap) + [films]), index_of(folder, []))
        Path(args.out).mkdir(parents=True, exist_ok=True)
        return args

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
class RenderPlanTest(unittest.TestCase):
    """The render stage and the plan on the fake renderer alone, with no feature space: what the
    shared set holds when a group keeps no CT."""

    def test_a_group_that_kept_no_ct_is_out_of_the_shared_set_and_its_row_says_so(self):
        """A render group that passed every CT over takes no part in the intersection, so the
        other groups on the folder still share every CT they kept, and its plan row says it kept
        none rather than that nothing was found under its rules; a group whose shared set is
        empty says that too."""
        tool = load_tool()
        renderer = FakeRenderer(None, "blobs", passes={"flexray_spineps": len(SUBJECTS)}, twins=True)
        with tempfile.TemporaryDirectory() as temporary:
            args, table_, renders, folders, plan = self.render_and_plan(tool, Path(temporary), renderer)
        expected = ranked(tool, sorted(set(SPINEPS_MASKED) & set(MOOSE_MASKED)))[:24]
        self.assertEqual(renders["flexray_spineps"]["kept"], [])
        self.assertNotIn("shared", renders["flexray_spineps"])
        self.assertEqual(folders[CT_FOLDER]["shared"], expected)
        rows = {g["id"]: g for g in plan["groups"]}
        self.assertEqual(rows["flexray_spineps"]["skipped"], "it kept no CT, 24 passed over")
        self.assertEqual(rows["flexray_spineps"]["chosen"], [])
        for group in ("flexray_drr", "flexray_drr_ct", "flexray_replica", "flexray_reference", "fluxray_raw",
                      "fluxray_raw_reference"):
            self.assertEqual(renders[group]["shared"], expected, group)
            self.assertEqual(len(rows[group]["chosen"]), 48, group)
        with self.assertRaises(tool.StageError) as refused:
            tool.candidate_rows(table_.groups[1], args, {table_.groups[1].id: {"kept": ["s0001"], "shared": []}})
        self.assertEqual(str(refused.exception), "no CT kept by every render group on its folder")

    def render_and_plan(self, tool, folder, renderer):
        """The render stage and the plan over the seven render groups and an absent walk group,
        on the fake renderer: the arguments, the table, the render and folder records, the plan."""
        make_cts(folder, {folder / "data" / "spineps": SPINEPS_MASKED, folder / "data" / "moose": MOOSE_MASKED})
        films = {"id": "films", "label": "films", "family": "film", "source": "walk", "folder": "films", "cap": 10,
                 "per_person": 1}
        original = tool.tool
        tool.tool = lambda name: renderer if name == "flexray_render" else original(name)
        args = args_for(tool, folder, table(folder, render_rows() + [films]), index_of(folder, []))
        Path(args.out).mkdir(parents=True)
        table_ = tool.read_table(args.groups)
        renders, folders = tool.stage_render(args, table_)
        return args, table_, renders, folders, tool.stage_plan(args, table_, renders, folders)


@unittest.skipIf(MISSING_BASE, f"needs {', '.join(MISSING_BASE)}")
class MaskFreeRenderTest(unittest.TestCase):
    """A DRR's pixels are a projection of the CT alone, so the study runs without segmentation
    (the owner's word of 2026-10-27): where a segmenter's masks are not read, for want of their
    folder, of any CT's masks in it or by --skip-masks, the folder's CTs are chosen among those with the masks still read,
    or among every CT where none is, the groups on segmenter none render them, and each group
    that names the unread segmenter is skipped with the reason, in its record, its plan row and
    the summary, while the others render."""

    def setUp(self):
        self.tool = load_tool()
        self.temporary = tempfile.TemporaryDirectory()
        self.folder = Path(self.temporary.name)
        self.renderer = FakeRenderer(None, "blobs", twins=True)
        original = self.tool.tool
        self.tool.tool = lambda name: self.renderer if name == "flexray_render" else original(name)

    def tearDown(self):
        self.temporary.cleanup()

    def render(self, masks, *flags):
        """The render stage and the plan over the seven render groups, the mask folders given made
        under the data root, the flags added to the run's."""
        data = self.folder / "data"
        make_cts(self.folder, {data / name: subjects for name, subjects in masks.items()})
        groups = table(self.folder, render_rows() + [self.films()])
        args = self.tool.parse(["run", "--groups", str(groups), "--data-root", str(data), "--out",
                                str(self.folder / "out"), "--device", "cpu", *flags])
        Path(args.out).mkdir(parents=True)
        table_ = self.tool.read_table(args.groups)
        renders, folders = self.tool.stage_render(args, table_)
        return renders, folders[CT_FOLDER], self.tool.stage_plan(args, table_, renders, folders)

    def rendered(self):
        return [call["group"] for call in self.renderer.calls]

    def assert_skipped(self, renders, plan, groups, reason):
        rows = {g["id"]: g for g in plan["groups"]}
        for group in groups:
            self.assertEqual(renders[group], {"skipped": reason}, group)
            self.assertEqual(rows[group]["skipped"], reason, group)
            self.assertEqual(rows[group]["chosen"], [], group)

    def test_without_the_moose_folder_the_moose_groups_alone_are_skipped(self):
        renders, folder, plan = self.render({"spineps": SPINEPS_MASKED})
        expected = ranked(self.tool, SPINEPS_MASKED)[:24]
        self.assertEqual(folder["subjects"], expected)
        self.assertEqual((folder["roots"], folder["masks"], folder["every"]),
                         ({"moose": "no folder", "spineps": "found"}, {"spineps": 27}, 27))
        self.assertEqual(self.rendered(), ["flexray_drr_ct", "flexray_spineps", "fluxray_raw", "fluxray_raw_reference"])
        for call in self.renderer.calls:
            self.assertEqual(list(call["subject_ids"]), expected)
            self.assertEqual(call["roots"], {"spineps": self.folder / "data" / "spineps"})
        self.assert_skipped(renders, plan, MOOSE_GROUPS, "its segmenter moose's masks are not read (no folder)")
        # The CT that flexray_spineps passed over is out of every group's rows, as ever.
        self.assertEqual(folder["shared"], expected[1:])
        self.assertEqual(self.tool.render_summary({CT_FOLDER: folder}),
                         [f"render {CT_FOLDER}: 24 CTs chosen of 27 with every mask of 30 CTs (spineps 27),"
                          " moose not read (no folder); 23 kept by every group"])

    def assert_too_few_read_as_none(self, moose, state):
        """A segment job that stopped on one of its first CTs leaves the moose folder with too few
        CTs' masks to test a group; required, they would leave every group on the folder those
        few CTs, the groups that read no mask among them."""
        renders, folder, plan = self.render({"spineps": SPINEPS_MASKED, "moose": moose})
        expected = ranked(self.tool, SPINEPS_MASKED)[:24]
        self.assertEqual(folder["subjects"], expected)
        self.assertEqual((folder["roots"], folder["masks"], folder["every"]),
                         ({"moose": state, "spineps": "found"}, {"spineps": 27}, 27))
        self.assertEqual(self.rendered(), ["flexray_drr_ct", "flexray_spineps", "fluxray_raw", "fluxray_raw_reference"])
        for call in self.renderer.calls:
            self.assertEqual(list(call["subject_ids"]), expected)
        self.assert_skipped(renders, plan, MOOSE_GROUPS, f"its segmenter moose's masks are not read ({state})")
        self.assertEqual(self.tool.render_summary({CT_FOLDER: folder}),
                         [f"render {CT_FOLDER}: 24 CTs chosen of 27 with every mask of 30 CTs (spineps 27),"
                          f" moose not read ({state}); 23 kept by every group"])

    def test_a_moose_folder_that_holds_no_ct_s_masks_is_read_as_none(self):
        self.assert_too_few_read_as_none([], "no CT here has them")

    def test_a_moose_folder_with_fewer_cts_than_a_test_needs_is_read_as_none(self):
        self.assert_too_few_read_as_none(MOOSE_MASKED[:4], "only 4 CTs have them, under 5")

    def test_a_moose_folder_of_five_cts_is_read_and_holds_every_group_to_them(self):
        # The limit the research note states: past the cutoff the folder is read, and every render
        # group on it is held to the CTs it covers, less those a group passed over, which is why the
        # study word waits for the segment job's report.
        renders, folder, _ = self.render({"spineps": SPINEPS_MASKED, "moose": MOOSE_MASKED[:5]})
        both = [s for s in MOOSE_MASKED[:5] if s in SPINEPS_MASKED]
        self.assertEqual(folder["subjects"], ranked(self.tool, both))
        self.assertEqual((folder["roots"], folder["masks"]), ({"moose": "found", "spineps": "found"},
                                                             {"moose": 5, "spineps": 27}))
        self.assertEqual(sorted(self.rendered()), sorted(g for g, *_ in RENDER_GROUPS))
        self.assertEqual(len(folder["shared"]), 4)
        for group in MASK_FREE:
            self.assertEqual(renders[group]["shared"], folder["shared"], group)

    def test_skip_masks_leaves_a_folder_that_is_there_out(self):
        renders, folder, plan = self.render({"spineps": SPINEPS_MASKED, "moose": MOOSE_MASKED}, "--skip-masks", "moose")
        self.assertEqual(folder["subjects"], ranked(self.tool, SPINEPS_MASKED)[:24])
        self.assertEqual(folder["roots"], {"moose": "left out by --skip-masks", "spineps": "found"})
        self.assertNotIn("moose", [segmenter for segmenter, _ in self.renderer.finds])
        self.assert_skipped(renders, plan, MOOSE_GROUPS, "its segmenter moose's masks are not read (left out by"
                                                         " --skip-masks)")
        self.assertEqual(self.rendered(), ["flexray_drr_ct", "flexray_spineps", "fluxray_raw", "fluxray_raw_reference"])

    def test_with_no_mask_folder_the_mask_free_groups_render_every_ct_they_draw(self):
        renders, folder, plan = self.render({})
        expected = ranked(self.tool, SUBJECTS)[:24]
        self.assertEqual(folder["subjects"], expected)
        self.assertEqual((folder["roots"], folder["masks"], folder["every"]),
                         ({"moose": "no folder", "spineps": "no folder"}, {}, 30))
        self.assertEqual(self.rendered(), list(MASK_FREE))
        for call in self.renderer.calls:
            self.assertEqual(list(call["subject_ids"]), expected)
            self.assertEqual(call["roots"], {})
        self.assert_skipped(renders, plan, MOOSE_GROUPS, "its segmenter moose's masks are not read (no folder)")
        self.assert_skipped(renders, plan, ["flexray_spineps"], "its segmenter spineps's masks are not read (no folder)")
        rows = {g["id"]: g for g in plan["groups"]}
        for group in MASK_FREE:
            self.assertEqual(renders[group]["shared"], expected, group)
            self.assertEqual(len(rows[group]["chosen"]), 48, group)
        self.assertEqual(self.tool.render_summary({CT_FOLDER: folder}),
                         [f"render {CT_FOLDER}: 24 CTs chosen of 30 with every mask of 30 CTs, moose not read (no folder),"
                          " spineps not read (no folder); 24 kept by every group"])

    def test_skip_masks_takes_the_two_segmenters_and_nothing_else(self):
        common = ["run", "--data-root", "d", "--out", "o"]
        self.assertEqual(self.tool.parse(common).skip_masks, [])
        both = self.tool.parse(common + ["--skip-masks", "moose", "--skip-masks", "spineps"])
        self.assertEqual(both.skip_masks, ["moose", "spineps"])
        self.assertEqual(self.tool.parse(["plan", *common[1:], "--skip-masks", "spineps"]).skip_masks, ["spineps"])
        for name in ("none", "totalsegmentator"):
            with self.assertRaises(SystemExit):
                self.tool.parse(common + ["--skip-masks", name])

    def test_the_plan_chooses_as_it_did_before_the_mask_free_groups_were_added(self):
        """The segment job's choice of CTs (the plan subcommand) is the one it made over the six
        render groups it served, the FluXray raw groups on MOOSE's labels and no group from the CT
        alone, since the groups on segmenter none require no masks."""
        spineps, moose = self.folder / "masks" / "spineps", self.folder / "masks" / "moose"
        make_cts(self.folder, {spineps: SPINEPS_MASKED})
        before = [dict(row, blocks=[w.replace("segmenter=none", "segmenter=moose") for w in row["blocks"]])
                  for row in render_rows() if row["id"] != "flexray_drr_ct"]
        chosen = {}
        for name, groups in (("before", before), ("now", render_rows())):
            out = self.folder / name
            self.assertEqual(self.tool.main(["plan", "--groups", str(table(self.folder, groups + [self.films()])),
                                             "--data-root", str(self.folder / "data"), "--out", str(out),
                                             "--spineps", str(spineps), "--moose", str(moose)]), 0)
            chosen[name] = json.loads((out / "render-subjects.json").read_text(encoding="utf-8"))
        self.assertEqual(chosen["now"], chosen["before"])
        self.assertEqual(chosen["now"], {CT_FOLDER: ranked(self.tool, SPINEPS_MASKED)[:24]})

    def films(self):
        return {"id": "films", "label": "films", "family": "film", "source": "walk", "folder": "films", "cap": 10,
                "per_person": 1}


def full_contrast(word=None):
    """A contrast in the shape the analysis writes, at the widest numbers the lines carry."""
    found = {"persons": [250, 250], "n": [1000, 1000], "paired": False,
             "auc_logistic": {"auc": 0.91, "lo": 0.88, "hi": 0.94, "p": 0.001}, "auc_knn": {"auc": 0.9},
             "mmd": {"mmd2": 0.1, "p": 0.001, "q": 0.002}, "fd64": 1234.5, "fd_rows": 250, "kid64": {"kid": 0.012},
             "prdc": {"precision": 0.5, "recall": 0.5, "density": 1.34, "coverage": 0.5}}
    return dict(found, word=word) if word else found


def full_space(tool, synthetic, real):
    """One space's record with every group full: every contrast the analysis makes, its pairs
    worded where the study words them."""
    worded = {"|".join(pair) for pair in tool.REPLICATION_WORDED}
    pairs = ["|".join(p) for p in tool.REPLICATION_PAIRS if all(g in synthetic for g in p)]
    families = ("fluoroscopy", "film")
    return {"dim": 61, "rows": 23000, "feature_spread": 0.5, "pca64_explained": 0.9,
            "calibration": {"auc_median": 0.5, "auc_range": [0.45, 0.55], "groups": {g: {} for g in synthetic + real},
                            "flagged": [], "auc_above": []},
            "replication": {p: full_contrast("replicated" if p in worded else None) for p in pairs},
            "vs_family": {sg: {f: full_contrast() for f in families} for sg in synthetic},
            "ratios": {sg: {f: {"fd_ratio": 1.5, "word": "separable"} for f in families} for sg in synthetic},
            "real_real": {f"{a}|{b}": full_contrast() for i, a in enumerate(real) for b in real[i + 1:]},
            "fluoroscopy_vs_film": full_contrast(),
            "structure": {"silhouette": {"overall": 0.2},
                          "nearest_real": {sg: {rg: 1 / len(real) for rg in real} for sg in synthetic}},
            "vs_group": {sg: {rg: full_contrast() for rg in real} for sg in synthetic},
            "maps": {"centres": {"tsne": {g: [1.0, 2.0, 3.0, 4.0] for g in synthetic + real}}}}


def full_results(tool, groups):
    """A results record for the groups given, every group full and every space run, the render
    groups with the equal counts a run's shared CTs give them."""
    synthetic = [g["id"] for g in groups if g["family"] == "synthetic"]
    real = [g["id"] for g in groups if g["family"] != "synthetic"]
    rows = [{"id": g["id"], "family": g["family"], "source": g["source"], "skipped": "", "decoded": 992,
             "person_fallback": 0, "chosen": 992, "failures": {}, "persons": 248,
             "found": 992 if g["source"] == "render" else 1000 + i} for i, g in enumerate(groups)]
    worded = {"|".join(p): {"word": "replicated", "persons": [248, 248], "n": [992, 992], "reason": ""}
              for p in tool.REPLICATION_WORDED}
    first = "|".join(tool.REPLICATION_PAIRS[0])
    renders = {CT_FOLDER: {"subjects": ["s"] * 250, "segmenters": ["moose", "spineps"], "pending": [],
                           "roots": {"moose": "found", "spineps": "found"}, "ct": 1228,
                           "masks": {"moose": 1000, "spineps": 1100}, "every": 990, "count": 250, "shared": ["s"] * 248}}
    spaces = {key: full_space(tool, synthetic, real) for key in ("flexray", "flexray_as_stored", "imagenet", "physics")}
    return {"groups": rows, "spaces": spaces, "renders": renders,
            "replication": {"space": "flexray", "reading": "invariant", "pair": first, **worded[first], "pairs": worded}}


@unittest.skipIf(MISSING_BASE, f"needs {', '.join(MISSING_BASE)}")
class CalibrationLineTest(unittest.TestCase):
    """The split-half nulls' counts come first and every flagged group is named, on lines of their
    own within the report's limit, however many are flagged (DEVIATIONS.md, item 8)."""

    def test_every_flagged_group_is_named_and_no_count_is_cut(self):
        tool = load_tool()
        groups = [g["id"] for g in json.loads((ROOT / "data" / "domain_gap" / "groups.json").read_text(encoding="utf-8"))["groups"]]
        for flagged in (0, 1, 8, len(groups)):
            cal = {"auc_median": 0.51, "auc_range": [0.42, 0.61], "groups": {g: {} for g in groups},
                   "flagged": groups[:flagged], "auc_above": groups[:2]}
            lines = tool.calibration_summary({"calibration": cal})
            self.assertTrue(lines[0].endswith(f"over {len(groups)}, mmd flagged {flagged}, auc interval above half 2"), lines[0])
            named = [name for line in lines[1:] for name in line[len(" calibration flagged "):].split()]
            self.assertEqual(named, groups[:flagged])
            for line in lines:
                self.assertEqual(tool.rules().safe_line(line), line)
                self.assertLessEqual(len(line), tool.rules().LINE_LIMIT)
            self.assertEqual(study_report().flagged_of({"lines": lines}), (groups[:flagged], flagged))


def study_report():
    """tools/report.py, whose study mode reads the record lines at the head of summary.txt."""
    spec = importlib.util.spec_from_file_location("study_report", ROOT / "tools" / "report.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipIf(MISSING_BASE, f"needs {', '.join(MISSING_BASE)}")
class SummaryBudgetTest(unittest.TestCase):
    """The study's own 23-group table with every group full and every space run fits the 80 lines
    the bench report carries below the record's five, which the study's report reads, with the
    three spaces' tables whole: the header and the verdicts, every group's line (the render groups' equal counts on one), and in each space its line, its
    calibration and every family contrast of the groups that face the real corpora, the primary
    space's replication pairs and real-real lines too, with FluXray fetched or not."""

    def test_the_full_table_keeps_the_three_spaces_tables_whole(self):
        tool = load_tool()
        groups = json.loads((ROOT / "data" / "domain_gap" / "groups.json").read_text(encoding="utf-8"))["groups"]
        self.assertEqual(len(groups), 23)
        for present in (True, False):
            kept = [g for g in groups if present or g["id"] != "fluxray"]
            results = full_results(tool, kept)
            # the record every run writes, five lines above the findings' 80 (finish_results)
            results["plan"] = "d" * 64
            results["_run"] = {"git_head": "0" * 40, "git_dirty": False, "seed": 0, "inputs": {"groups.json": "a" * 64},
                               "prereg_sha256": "b" * 64, "code_digest": "c" * 64}
            results["_record"] = {"jobs": {"prepare": "1", "array": "2", "tasks": 4, "merge": "3"}, "gpus": {"NVIDIA H200": 5},
                                  "units": {"total": 9, "done": 9, "failed": 0}, "mmd": "torch-cuda", "units_seconds": 9}
            lines = tool.summary_lines(results, "off")
            self.assertLessEqual(len(lines), tool.LINE_BUDGET + tool.RECORD_LINES, present)
            self.assertEqual([line.split(" ")[1] for line in lines[:5]], ["study", "jobs", "units", "seconds", "environment"])
            _, problems, unknown, body = study_report().record_of(lines, "drr-domain-gap")
            self.assertEqual((problems, unknown, body[0]), ({}, [], lines[5]))
            self.assertEqual(lines[6:8], tool.verdict_lines(results["replication"]))
            for line in tool.render_summary(results["renders"]) + tool.group_summary(results["groups"]):
                self.assertIn(line, lines)
            self.assertEqual(sum(1 for line in lines if line.startswith("groups counted as flexray_drr: ")), 1)
            facing = [g["id"] for g in kept if g["family"] == "synthetic" and g["id"] not in tool.REPLICATION_ONLY]
            self.assertIn("flexray_drr_ct", facing)
            for key in ("flexray", "imagenet", "physics"):
                space = results["spaces"][key]
                self.assertTrue(any(line.startswith(f"space {key} dim ") for line in lines), key)
                for sg in facing:
                    for family in ("fluoroscopy", "film"):
                        self.assertIn(tool.family_line(space, sg, family, space["vs_family"][sg][family]), lines)
            primary = results["spaces"]["flexray"]
            for pair in primary["replication"]:
                self.assertIn(tool.replication_line(pair, primary["replication"][pair]), lines, pair)
            self.assertTrue(any(line.startswith(" real-real auc median ") for line in lines))


@unittest.skipIf(MISSING_BASE, f"needs {', '.join(MISSING_BASE)}")
class FamilyTest(unittest.TestCase):
    """The MMD's Benjamini-Hochberg family is every MMD p of the space, the split-half nulls'
    among them, as PREREG.md section 3 says; each contrast keeps its q over the contrasts alone
    beside it, the family the first sharded run read (DEVIATIONS.md, item 11). The nulls move a
    contrast's q either way, and the C2ST's family, which no null enters, does not move."""

    def setUp(self):
        self.tool = load_tool()

    def space(self, contrasts, nulls):
        """A space's result with the contrasts' MMD p-values on its family contrasts and the
        nulls' on its calibration; a null given as None was not tested."""
        def contrast(p):
            return {"mmd": {"p": p}, "auc_logistic": {"p": p}}
        return {"vs_group": {}, "real_real": {}, "replication": {},
                "vs_family": {"synthetic": {f"family{i}": contrast(p) for i, p in enumerate(contrasts)}},
                "calibration": {"groups": {f"null{i}": {"mmd": {} if p is None else {"p": p}} for i, p in enumerate(nulls)}}}

    def q_values(self, result, key):
        return [c["mmd"][key] for c in result["vs_family"]["synthetic"].values()]

    def test_the_nulls_raise_a_q_over_the_bar_where_they_lie_above_its_p(self):
        result = self.space((0.001, 0.03, 0.2), (0.6, 0.9))
        self.tool.adjust(result)
        for found, expected in zip(self.q_values(result, "q"), (0.005, 0.075, 1 / 3)):
            self.assertAlmostEqual(found, expected)
        for found, expected in zip(self.q_values(result, "q_without_nulls"), (0.003, 0.045, 0.2)):
            self.assertAlmostEqual(found, expected)
        pure = self.tool.rules()
        self.assertEqual(self.q_values(result, "q"), list(pure.benjamini_hochberg((0.001, 0.03, 0.2, 0.6, 0.9))[:3]))
        self.assertEqual([c["auc_logistic"]["q"] for c in result["vs_family"]["synthetic"].values()],
                         list(pure.benjamini_hochberg((0.001, 0.03, 0.2))))

    def test_the_nulls_lower_a_q_where_they_lie_below_its_p(self):
        result = self.space((0.04, 0.3), (0.001, 0.002))
        self.tool.adjust(result)
        self.assertAlmostEqual(self.q_values(result, "q")[0], 0.04 * 4 / 3)
        self.assertAlmostEqual(self.q_values(result, "q_without_nulls")[0], 0.08)

    def test_a_null_not_tested_and_a_space_with_no_null_leave_the_family_to_the_contrasts(self):
        for nulls in ((), (None,)):
            result = self.space((0.001, 0.03, 0.2), nulls)
            self.tool.adjust(result)
            self.assertEqual(self.q_values(result, "q"), self.q_values(result, "q_without_nulls"))
        result = self.space((0.001,), (0.5,))
        self.tool.adjust(result)
        self.assertEqual(result["calibration"]["groups"]["null0"]["mmd"], {"p": 0.5})  # a null's flag is flagged_nulls'

    def test_the_replication_line_shows_both_q_values_and_keeps_the_word(self):
        found = {"persons": [26, 26], "n": [52, 52], "word": "replicated", "paired": True,
                 "auc_logistic": {"auc": 0.5, "lo": 0.5, "hi": 0.5, "p": 1.0}, "auc_knn": {"auc": 0.5},
                 "mmd": {"mmd2": 0.0, "p": 0.047, "q": 0.052, "q_without_nulls": 0.048}, "fd64": 0.0,
                 "kid64": {"kid": -0.467}, "prdc": {"precision": 1.0, "recall": 1.0, "density": 1.0, "coverage": 1.0}}
        line = self.tool.replication_line("flexray_replica|flexray_reference", found)
        self.assertIn(" mmd p 0.047 q 0.052 (0.048 without nulls) fd64 ", line)
        self.assertTrue(line.endswith(" replicated"))
        self.assertLessEqual(len(line), self.tool.rules().LINE_LIMIT)
        self.assertEqual(self.tool.rules().safe_line(line), line)
        self.assertTrue(study_report().MEASURES[4][1].search(line))
        del found["mmd"]["q_without_nulls"]
        self.assertIn(" mmd p 0.047 q 0.052 fd64 ", self.tool.replication_line("flexray_replica|flexray_reference", found))

    def test_the_claim_report_names_the_family_its_lines_show(self):
        report = study_report()
        before = " replication a vs b persons 26/26 n 52/52 auc 0.50 [0.50, 0.50] p 1.000 knn 0.50 mmd p 0.047 q 0.048 fd64 0.0"
        after = before.replace("q 0.048", "q 0.052 (0.048 without nulls)")
        self.assertIn("over its contrasts alone, the split-half nulls adjusted among themselves", report.mmd_family([before]))
        self.assertIn("over its contrasts and its split-half nulls as PREREG.md section 3 says", report.mmd_family([after]))
        self.assertEqual(report.mmd_family([" flexray_drr vs film auc 1.00 [1.00, 1.00] p 0.167 knn 1.00 fd64 323.1"]), "")


@unittest.skipIf(MISSING_BASE, f"needs {', '.join(MISSING_BASE)}")
class SummaryLineTest(unittest.TestCase):
    """The verdict and replication lines: each carries the persons and rows a side the word rests
    on, since the word is a non-rejection rule a small sample satisfies for want of power, and each
    stays within the report's 200 characters at the widest numbers, the last numbers left off
    whole rather than the word cut (the review of 2026-10-26, F23 and F26)."""

    PAIR = "fluxray_raw|fluxray_raw_reference"  # the longest pair name

    def setUp(self):
        self.tool = load_tool()

    def contrast(self, **changes):
        found = {"persons": [250, 250], "n": [1000, 1000], "word": "not replicated", "paired": True,
                 "auc_logistic": {"auc": 0.5, "lo": 0.42, "hi": 0.57, "p": 0.5, "q": 0.5}, "auc_knn": {"auc": 0.5},
                 "mmd": {"mmd2": 0.0, "p": 0.5, "q": 0.5}, "fd64": 1234.5, "fd_rows": 250, "kid64": {"kid": 0.012},
                 "prdc": {"precision": 0.5, "recall": 0.5, "density": 1.34, "coverage": 0.5}}
        found.update(changes)
        return found

    def test_the_verdict_line_carries_the_counts_and_a_reason_is_cut_to_the_line(self):
        verdict = {"space": "flexray", "reading": "invariant"}
        line = self.tool.verdict_line(self.PAIR, self.contrast(persons=[1000, 1000]), verdict)
        self.assertEqual(line, "replication fluxray_raw vs fluxray_raw_reference in flexray (invariant): not replicated"
                               " (persons 1000/1000 n 1000/1000)")
        self.assertEqual(self.tool.rules().safe_line(line), line)
        reason = "fluxray_raw_reference: " + "the render failed " * 20
        cut = self.tool.verdict_line(self.PAIR, {"word": None, "reason": reason}, verdict)
        self.assertEqual(len(cut), 200)
        self.assertTrue(cut.startswith("replication fluxray_raw vs fluxray_raw_reference: no verdict,"
                                       " fluxray_raw_reference: the render failed"))
        results = {"spaces": {"flexray": {"replication": {self.PAIR: self.contrast()}}}}
        self.assertEqual(self.tool.pair_verdict(results, self.PAIR),
                         {"word": "not replicated", "reason": "", "persons": [250, 250], "n": [1000, 1000]})

    def test_the_replication_line_carries_the_counts_and_keeps_the_word_within_the_limit(self):
        line = self.tool.replication_line(self.PAIR, self.contrast())
        self.assertEqual(line, " replication fluxray_raw vs fluxray_raw_reference persons 250/250 n 1000/1000"
                               " auc 0.50 [0.42, 0.57] p 0.500 knn 0.50 mmd p 0.500 q 0.500 fd64 1234.5 kid64 0.012"
                               " prdc 0.50 0.50 1.34 0.50 not replicated")
        self.assertEqual(len(line), 200)
        self.assertEqual(self.tool.rules().safe_line(line), line)
        wide = self.tool.replication_line(self.PAIR, self.contrast(persons=[1000, 999], n=[1000, 996], fd64=12345.6,
                                                                   kid64={"kid": -0.012}))
        self.assertTrue(wide.startswith(" replication fluxray_raw vs fluxray_raw_reference"
                                        " persons 1000/999 n 1000/996 auc 0.50 [0.42, 0.57] p 0.500 knn"))
        self.assertTrue(wide.endswith(" fd64 12345.6 kid64 -0.012 not replicated"))  # prdc left off whole
        self.assertLessEqual(len(wide), 200)
        unworded = self.tool.replication_line(self.PAIR, self.contrast(word=None))
        self.assertTrue(unworded.endswith(" prdc 0.50 0.50 1.34 0.50"))
        self.assertEqual(self.tool.replication_line(self.PAIR, {"skipped": "x" * 300}),
                         " replication fluxray_raw vs fluxray_raw_reference not tested, " + "x" * 130)


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
        # The masks the plan reads are ones the data root already holds, so a folder of them
        # holding too few is refused with its reason, where the run would read it as none.
        spineps, moose = self.folder / "masks" / "spineps", self.folder / "masks" / "moose"
        for held in ([], SPINEPS_MASKED[:4]):
            with self.subTest(held=len(held)):
                shutil.rmtree(self.folder, ignore_errors=True)
                make_cts(self.folder, {spineps: held})
                printed = io.StringIO()
                with contextlib.redirect_stdout(printed), contextlib.redirect_stderr(printed):
                    self.assertEqual(self.plan(render_rows(), spineps, moose), 2)
                written = json.loads((self.folder / "out" / "render-subjects.json").read_text(encoding="utf-8"))
                self.assertEqual(written, {CT_FOLDER: []})
                self.assertIn(f"render {CT_FOLDER}: 0 CTs chosen of 0 with every mask of 30 CTs", printed.getvalue())
                self.assertIn(f"no CT chosen for {CT_FOLDER} (too few CTs with the masks the data root should"
                              f" already hold: spineps {len(held)})", printed.getvalue())


def fake_fxr(splits):
    """Stand-ins for FleXray's ThunderDB opener and split reader, holding LMDB's rule that one
    environment opens once a process: a second open of a root still open raises a class named
    Error from a module named lmdb, as py-lmdb 2.0 and later do. Each split's records are its
    samples, two to a subject, and a sample's image is a gradient whose level names its split."""
    import types

    import numpy as np

    lmdb = types.ModuleType("lmdb")
    lmdb.Error = type("Error", (Exception,), {"__module__": "lmdb"})
    opened, live = [], set()

    class Database:
        def __init__(self, root):
            self.root = root

        def __getitem__(self, key):
            if key != "_splits":
                raise KeyError(key)
            return {name: {} for name in splits}

        def close(self):
            live.discard(self.root)

    def open_thunderdb(root):
        root = str(root)
        if root in live:
            raise lmdb.Error(f"The environment '{root}' is already open in this process.")
        live.add(root)
        opened.append(root)
        return Database(root)

    class Record:
        def __init__(self, data_id, subject_id):
            self.data_id, self.subject_id = data_id, subject_id

    class Backend:
        def __init__(self, db, *, split, owns_database=True, **_):
            if not isinstance(db, Database):
                db = open_thunderdb(db)  # FleXray's reader opens a path itself
            self.db, self.split = db, split
            self.records = [Record(f"{split}-{i}", f"{split}-s{i // 2}") for i in range(splits[split])]

        def load(self, record, key):
            level = sorted(splits).index(self.split) + 1
            return np.linspace(0, level, 64 * 64).reshape(1, 64, 64)

    modules = {"lmdb": lmdb}
    for name in ("fxr", "fxr.datasets", "fxr.datasets._thunderdb", "fxr.datasets.storage"):
        modules[name] = types.ModuleType(name)
    modules["fxr.datasets._thunderdb"].open_thunderdb = open_thunderdb
    modules["fxr.datasets.storage"].SplitThunderDBStorageBackend = Backend
    return modules, opened


@unittest.skipIf(MISSING_BASE, f"needs {', '.join(MISSING_BASE)}")
class ThunderTest(unittest.TestCase):
    """FluXray's ThunderDB is opened once a process and every split's reader borrows it, since
    LMDB refuses a second open of one environment in one process; the first sharded run gave each
    split's reader the root's path, so each reader opened the environment itself and kept it open,
    the second split's reader was refused, and FluXray was skipped as "(Error)" (DEVIATIONS.md,
    item 10)."""

    def setUp(self):
        self.tool = load_tool()
        self.temporary = tempfile.TemporaryDirectory()
        self.folder = Path(self.temporary.name)
        database = self.folder / "data" / "hf_flexray_data" / "raw" / "FluXray" / "thunder_dbs" / "1.0"
        database.mkdir(parents=True)
        (database / "data.mdb").write_bytes(b"")
        group = {"id": "fluxray", "label": "FluXray", "family": "synthetic", "source": "thunderdb",
                 "folder": "hf_flexray_data/raw", "cap": 100, "per_person": 4}
        self.group = self.tool.read_table(table(self.folder, [group, PlanTest.groups(None)[0]])).groups[0]

    def tearDown(self):
        self.temporary.cleanup()

    def test_every_split_is_listed_and_read_through_one_open(self):
        splits = {"train": 6, "val": 4, "test": 2}
        modules, opened = fake_fxr(splits)
        with unittest.mock.patch.dict(sys.modules, modules):
            rows = self.tool.thunder_candidates(self.group, self.folder / "data")
            self.assertEqual(len(rows), 12)
            self.assertEqual(sorted({r[0].split("|")[1] for r in rows}), sorted(splits))
            self.assertEqual(len({r[2] for r in rows}), 6)
            levels = {r[0].split("|")[1]: float(self.tool.grey_of(r[0]).max()) for r in rows}
            self.assertEqual(levels, {"test": 1.0, "train": 2.0, "val": 3.0})
        self.assertEqual(len(opened), 1)

    def test_a_reader_that_opened_the_root_again_is_the_error_the_first_run_had(self):
        modules, _ = fake_fxr({"train": 2, "val": 2})
        with unittest.mock.patch.dict(sys.modules, modules):
            db = self.tool.thunder_db(next(self.folder.rglob("data.mdb")).parent)
            backend = modules["fxr.datasets.storage"].SplitThunderDBStorageBackend
            with self.assertRaises(modules["lmdb"].Error) as raised:
                backend(str(db.root), split="train")
            self.assertEqual(self.tool.error_kind(raised.exception), "lmdb.Error")

    def test_the_skip_names_the_error_by_module_and_errno_and_never_its_text(self):
        import errno
        import types

        lmdb = types.ModuleType("lmdb")
        lmdb.Error = type("Error", (Exception,), {"__module__": "lmdb"})
        locked = lmdb.Error("/rs/secret/path: No locks available")
        locked.errno = errno.ENOLCK
        self.assertEqual(self.tool.error_kind(locked), "lmdb.Error ENOLCK")
        self.assertEqual(self.tool.error_kind(KeyError("/rs/secret/path")), "KeyError")
        self.assertEqual(self.tool.error_kind(OSError(errno.ESTALE, "stale", "/rs/secret")), "OSError ESTALE")
        odd = type("Odd<x>", (Exception,), {"__module__": "a b"})("text")
        self.assertEqual(self.tool.error_kind(odd), "ab.Oddx")
        missing = lmdb.Error("/rs/secret: No such file")  # py-lmdb sets code, never errno
        missing.code = errno.ENOENT
        self.assertEqual(self.tool.error_kind(missing), "lmdb.Error ENOENT")
        for code in (0, True, -30792, "x", 10 ** 30):
            other = lmdb.Error("/rs/secret")
            other.code = code
            self.assertEqual(self.tool.error_kind(other), "lmdb.Error")
        long = type("C" * 80, (Exception,), {"__module__": "m" * 80})()
        long.code = errno.ENOLCK
        line = self.tool.group_line({"id": "fluxray_raw_reference", "family": "synthetic", "decoded": 0,
                                     "skipped": f"its files could not be listed ({self.tool.error_kind(long)})"})
        self.assertTrue(line.endswith(" ENOLCK)"), line)
        for error in (locked, KeyError("/rs/secret/path"), odd):
            self.assertNotIn("secret", self.tool.error_kind(error))
        args = args_for(self.tool, self.folder, table(self.folder, [{
            "id": "fluxray", "label": "FluXray", "family": "synthetic", "source": "thunderdb",
            "folder": "hf_flexray_data/raw", "cap": 100, "per_person": 4}, PlanTest.groups(None)[0]]))
        Path(args.out).mkdir(parents=True)

        def refuse(group, data_root):
            raise locked

        with unittest.mock.patch.object(self.tool, "thunder_candidates", refuse), \
                contextlib.redirect_stderr(io.StringIO()):
            row = self.tool.stage_plan(args, self.tool.read_table(args.groups))["groups"][0]
        self.assertEqual(row["skipped"], "its files could not be listed (lmdb.Error ENOLCK)")


@unittest.skipIf(MISSING_BASE, f"needs {', '.join(MISSING_BASE)}")
class PlanCodeTest(unittest.TestCase):
    """The plan is made again when the study's code changes, since the first sharded run read a
    plan.json the cancelled V100 job had written under older code, so a group that code could not
    list stayed skipped (DEVIATIONS.md, item 10); a plan made again with the same content keeps its
    digest, so the images and features keyed by it are kept."""

    def setUp(self):
        self.tool = load_tool()
        self.temporary = tempfile.TemporaryDirectory()
        self.folder = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_new_code_makes_the_plan_again_and_the_same_content_keeps_its_digest(self):
        rows = PlanTest.index_rows(None)
        index = index_of(self.folder, rows)
        groups = table(self.folder, PlanTest.groups(None)[:2])
        args = args_for(self.tool, self.folder, groups, index)
        Path(args.out).mkdir(parents=True)
        first = self.tool.stage_plan(args, self.tool.read_table(groups))
        self.assertEqual(first["stamp"]["code"], self.tool.code_digest())
        made = []
        real = self.tool.plan_group

        def counted(*a, **k):
            made.append(1)
            return real(*a, **k)

        with unittest.mock.patch.object(self.tool, "plan_group", counted):
            self.tool.stage_plan(args, self.tool.read_table(groups))
            self.assertEqual(made, [])
            with unittest.mock.patch.object(self.tool, "code_digest", lambda: "0" * 64):
                again = self.tool.stage_plan(args, self.tool.read_table(groups))
            self.assertEqual(len(made), 2)  # each of the two groups planned again
        self.assertEqual(again["stamp"]["code"], "0" * 64)
        self.assertEqual(self.tool.plan_digest(again), self.tool.plan_digest(first))

    def test_a_group_the_index_lists_and_refuses_says_which_rule_refused_it(self):
        rows = [(f"/v/{i}.dicom", f"{i}.dicom", "dicom", "2000", "2000", None, "", "", f"study{i}", "image", None,
                 "vindr_spinexr") for i in range(3)]
        rows.append(("/v/x.png", "x.png", "png", "2000", "2000", None, None, "", "", "image", None, "vindr_spinexr"))
        index = index_of(self.folder, rows)
        vindr, absent = PlanTest.groups(None)[1:]
        args = args_for(self.tool, self.folder, table(self.folder, [vindr, absent]), index)
        Path(args.out).mkdir(parents=True)
        row = self.tool.stage_plan(args, self.tool.read_table(args.groups))["groups"][0]
        self.assertEqual(row["skipped"], "4 index rows, none kept: format 1, modality 3")
        self.assertEqual(self.tool.rules().safe_line(row["skipped"]), row["skipped"])
        many = "1046600 index rows, none kept: " + ", ".join(f"{r} 209320" for r in self.tool.REFUSALS)
        line = self.tool.group_line({"id": "vindr_spinexr", "family": "film", "decoded": 0, "skipped": many})
        self.assertTrue(line.endswith(many), line)  # the summary keeps every count
        (self.folder / "empty").mkdir()
        args = args_for(self.tool, self.folder, table(self.folder, [vindr, absent]), index_of(self.folder / "empty", []))
        row = self.tool.stage_plan(args, self.tool.read_table(args.groups))["groups"][0]
        self.assertEqual(row["skipped"], "the index lists no image row under its sources")


    def test_a_kept_plan_where_a_group_could_not_be_listed_is_made_again(self):
        """A group whose folder was not there, or whose reader failed, is listed again on the next
        run at the same code, since nothing in the stamp says the data has come since."""
        groups = [{"id": "lumos", "label": "lumos", "family": "film", "source": "walk", "folder": "lumos/bank",
                   "formats": ["png"], "person": "regex:lumos_x_(?P<person>[0-9]{3})_[0-9]+[.]png$", "cap": 10,
                   "per_person": 1}, PlanTest.groups(None)[0]]
        args = args_for(self.tool, self.folder, table(self.folder, groups), index_of(self.folder, []))
        Path(args.out).mkdir(parents=True)
        first = self.tool.stage_plan(args, self.tool.read_table(args.groups))["groups"][0]
        self.assertIn("no folder lumos/bank", first["skipped"])
        bank = self.folder / "data" / "lumos" / "bank"
        bank.mkdir(parents=True)
        (bank / "lumos_x_001_1.png").write_bytes(b"")
        again = self.tool.stage_plan(args, self.tool.read_table(args.groups))["groups"][0]
        self.assertEqual((again["found"], again["skipped"]), (1, ""))

    def test_images_and_features_are_made_again_for_new_code(self):
        import numpy as np

        image = self.folder / "film" / "a.png"
        save_png(image, np.linspace(0, 1, 300 * 300).reshape(300, 300))
        plan = {"groups": [{"id": "film", "family": "film", "chosen": [[str(image), "film:a"]]}]}
        args = args_for(self.tool, self.folder, table(self.folder, PlanTest.groups(None)[:2]))
        Path(args.out).mkdir(parents=True)
        calls = []
        real = self.tool.decode_all

        def counted(references, workers):
            calls.append(len(references))
            return real(references, workers)

        with unittest.mock.patch.object(self.tool, "decode_all", counted):
            rows, _ = self.tool.stage_images(args, plan)
            self.tool.stage_images(args, plan)
            self.assertEqual(calls, [1])
            with unittest.mock.patch.object(self.tool, "code_digest", lambda: "0" * 64):
                again, _ = self.tool.stage_images(args, plan)
            self.assertEqual(calls, [1, 1])
        self.assertEqual((rows["code"], again["code"]), (self.tool.code_digest(), "0" * 64))
        features = self.folder / "f.npz"
        np.savez(features, stored=np.zeros(1), inverse=np.zeros(1), plan=rows["plan"], code=rows["code"])
        self.assertTrue(self.tool.features_kept(features, rows["plan"], rows["code"]))
        self.assertFalse(self.tool.features_kept(features, rows["plan"], "0" * 64))
        np.savez(features, stored=np.zeros(1), inverse=np.zeros(1), plan=rows["plan"])  # an older code's file
        self.assertFalse(self.tool.features_kept(features, rows["plan"], rows["code"]))


if __name__ == "__main__":
    sys.exit(unittest.main())
