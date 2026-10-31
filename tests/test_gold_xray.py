"""tools/gold_xray.py, the QA loop's gold arm (docs/research/qa-loop-gold/PREREG.md): which cases each
tier reads and why the rest are left out, a person kept whole under a tier's cap and out of the other
tier, the case list a chain freezes at its first round, and a record that names no path; and, where
scipy and nibabel are installed beside numpy, the radiograph's geometry against the projection the
landmarks take, a stand-in read whole, a gold CT read from its files with each level's bone in the
shadow its landmarks project to, the cache, the fingerprint's runs and the presence read on the
radiographs, and the spine-only copy the network's reading cuts its crops from. CI's python3 holds
none of them, so the file is skipped there; run it with any python that has them:

    python3 -m unittest tests.test_gold_xray -v
"""

import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
VENDORED = str(ROOT / "grid" / "autoanatomist")
MISSING = [name for name in ("numpy",) if importlib.util.find_spec(name) is None]
MISSING_READ = MISSING + [name for name in ("scipy", "nibabel") if importlib.util.find_spec(name) is None]
LEVELS = ["T12", "L1", "L2", "L3", "L4", "L5"]
IDS3 = {"T12": 19, "L1": 20, "L2": 21, "L3": 22, "L4": 23, "L5": 24, "sacrum": 28}
IDS4 = dict(IDS3, sacrum=26)
# A small plan's gold settings: one field and one radiograph a view, so a case is read in seconds.
SMALL = {"size": 128, "fields_mm": [230], "frames_per_view": 2, "drr_per_view": 1, "k_max": 5, "noise_px": 2.0}
LOADED = {}

if not MISSING:
    import numpy as np


def round_tool():
    """The round tool, loaded once, and with it the gold module it loads by name (its X); both put
    their own folders on the path as they load, so the test's path is put back after."""
    if "round" not in LOADED:
        kept = list(sys.path)
        try:
            spec = importlib.util.spec_from_file_location("qaloop_round_gold_under_test", ROOT / "tools" / "qaloop_round.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        finally:
            sys.path[:] = kept
        LOADED["round"] = module
    return LOADED["round"]


def touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


def screen_row(item, part):
    return {"item": item, "person": item, "part": part, "source": "fake"}


def gold3_spec(folder, rows):
    """Gold tier 3's block over rows written to a file of their own; rows_of is absolute, which the
    module's ROOT / rows_of keeps as it is."""
    path = Path(folder) / "screen.json"
    path.write_text(json.dumps({"rows": rows}))
    return {"rows_of": str(path), "ct": "ct", "labels": "labels", "labels_folder": "Vertebrae", "ids": dict(IDS3)}


def gold4_spec(**more):
    return dict({"records": "records.jsonl", "kinds": ["concordant"], "ids": dict(IDS4)}, **more)


def gold4_record(n, person, ct, **more):
    return dict({"id": f"u{n}", "person_key": person, "status": "segmented", "kind": "concordant", "held_out": False,
                 "ct": str(ct), "labels": f"labels/u{n}.nii.gz"}, **more)


def write_records(folder, records, tail=""):
    (Path(folder) / "records.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records) + tail)


@unittest.skipIf(MISSING, f"needs numpy ({', '.join(MISSING)} missing)")
class CasesTest(unittest.TestCase):
    """Which cases each tier reads, why the rest are left out, the caps and the frozen case list."""

    def setUp(self):
        self.R = round_tool()
        self.X = self.R.X
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_gold3_reads_each_row_whose_ct_and_bone_map_are_found_once(self):
        rows = [screen_row(f"fake:000{n}", part) for n, part in
                ((1, "train"), (2, "validation"), (3, "train"), (4, "train"), (5, "test"), (6, "train"))]
        spec = gold3_spec(self.root, rows)
        data = self.root / "data"
        for n in (1, 2, 4, 5, 6):
            touch(data / "ct" / "site" / f"000{n}.nii.gz")
            touch(data / "labels" / "site" / "Vertebrae" / f"000{n}.nii.gz")
        touch(data / "labels" / "site" / "Organs" / "0001.nii.gz")    # another folder's map is not the bones'
        touch(data / "ct" / "again" / "0006.nii.gz")                  # a CT found twice is not taken
        cases, left = self.X.gold3_cases(spec, data, {"fake:0004"})
        self.assertEqual([(c["item"], c["part"]) for c in cases], [("fake:0001", "training"), ("fake:0002", "validation")])
        self.assertEqual(dict(left), {"CT or label map not found once": 2, "test list": 1, "no part": 1})
        first = cases[0]
        self.assertEqual((first["tier"], first["type"], first["stand_in"], first["ids"]), ("gold3", "typical", False, IDS3))
        self.assertEqual(Path(first["labels"]).parent.name, "Vertebrae")
        self.assertEqual(self.X.gold3_cases(spec, None, set())[0], [])

    def test_gold4_reads_only_segmented_units_whose_maps_agree_of_persons_no_list_or_other_tier_holds(self):
        g4 = self.root / "gold4"
        ct = touch(self.root / "cts" / "u.nii.gz")
        for n in range(9):
            touch(g4 / "labels" / f"u{n}.nii.gz")
        records = [gold4_record(0, "fake:a", ct), gold4_record(1, "fake:b", ct, kind="name_shift"),
                   gold4_record(2, "fake:c", ct, status="failed"), gold4_record(3, "fake:d", ct, held_out=True),
                   gold4_record(4, "", ct), gold4_record(5, "fake:test", ct), gold4_record(6, "fake:g3", ct),
                   gold4_record(7, "fake:e", self.root / "cts" / "gone.nii.gz"),
                   gold4_record(8, "fake:f", ct, labels="labels/none.nii.gz")]
        write_records(g4, records, tail="{not json\n")
        rule, _ = self.X.S.split_rule()
        cases, left = self.X.gold4_cases(gold4_spec(), g4, {"fake:test"}, rule, frozenset({"fake:g3"}))
        self.assertEqual([c["person"] for c in cases], ["fake:a"])
        self.assertEqual(cases[0]["part"], self.X.S.split_part("fake:a", rule, {"fake:test"}))
        self.assertEqual((cases[0]["labels"], cases[0]["ids"]), (str(g4 / "labels" / "u0.nii.gz"), IDS4))
        self.assertEqual(dict(left), {"kind name_shift": 1, "not segmented": 1, "held out": 1, "no person key": 1,
                                      "test list": 1, "a gold tier 3 person": 1, "CT or label map not on disk": 2,
                                      "unreadable line": 1})

    def test_gold4_without_its_records_says_so(self):
        self.assertEqual(self.X.gold4_cases(gold4_spec(), None, set(), {}), ([], {"no records.jsonl": 1}))
        self.assertEqual(self.X.gold4_cases(gold4_spec(), self.root, set(), {})[1], {"no records.jsonl": 1})

    def test_a_cap_keeps_whole_persons_in_an_order_drawn_from_each_person_alone(self):
        persons = [f"fake:{p}" for p in "abcdef"]
        cases = [{"person": p, "part": "training"} for p in persons] + [{"person": "fake:a", "part": "training"}]
        cases += [{"person": f"fake:v{n}", "part": "validation"} for n in range(3)]
        order = sorted(persons, key=lambda p: hashlib.sha256(f"schwingnet-qaloop-gold|{p}".encode()).hexdigest())
        kept, left = self.X.capped(cases, {"training": 2})
        self.assertEqual({c["person"] for c in kept if c["part"] == "training"}, set(order[:2]))
        self.assertEqual(sum(c["person"] == "fake:a" for c in kept), 2 if "fake:a" in order[:2] else 0)
        self.assertEqual(sum(c["part"] == "validation" for c in kept), 3)
        self.assertEqual(dict(left), {"over the training cap": sum(c["person"] in order[2:] for c in cases)})
        # a person left out of the pool moves no other person in or out
        fewer = [c for c in cases if c["person"] != order[-1]]
        self.assertEqual({c["person"] for c in self.X.capped(fewer, {"training": 2})[0]},
                         {c["person"] for c in kept})
        self.assertEqual(self.X.capped(cases, None), (cases, {}))

    def test_the_tiers_keep_apart_and_their_record_holds_counts_and_reasons_and_no_path(self):
        rows = [screen_row("fake:0001", "train"), screen_row("fake:0002", "validation")]
        data = self.root / "data"
        for n in (1, 2):
            touch(data / "ct" / "s" / f"000{n}.nii.gz")
            touch(data / "labels" / "s" / "Vertebrae" / f"000{n}.nii.gz")
        g4 = self.root / "gold4"
        ct = touch(self.root / "cts" / "u.nii.gz")
        for n in range(3):
            touch(g4 / "labels" / f"u{n}.nii.gz")
        write_records(g4, [gold4_record(0, "fake:0001", ct), gold4_record(1, "fake:x", ct), gold4_record(2, "fake:t", ct)])
        spec = {"gold3": gold3_spec(self.root, rows), "gold4": gold4_spec()}
        with mock.patch.object(self.X, "test_persons", return_value={"fake:t"}):
            cases, record = self.X.cases_for(spec, str(data), str(g4))
        self.assertEqual(sorted(cases), ["gold3", "gold4"])
        self.assertEqual(record["gold3"], {"cases": 2, "persons": {"training": 1, "validation": 1}, "left_out": {}})
        self.assertEqual([c["person"] for c in cases["gold4"]], ["fake:x"])
        self.assertEqual(record["gold4"]["left_out"], {"a gold tier 3 person": 1, "test list": 1})
        text = json.dumps(record)
        self.assertNotIn(str(self.root), text)
        self.assertNotIn("nii", text)

    def test_a_chain_reads_its_case_list_once_and_holds_it_while_the_records_grow(self):
        g4, cache = self.root / "gold4", self.root / "cache"
        cache.mkdir()
        ct = touch(self.root / "cts" / "u.nii.gz")
        for n in range(2):
            touch(g4 / "labels" / f"u{n}.nii.gz")
        write_records(g4, [gold4_record(0, "fake:x", ct)])
        spec, said = {"gold4": gold4_spec()}, []
        with mock.patch.object(self.X, "test_persons", return_value=set()):
            first, record = self.R.frozen_cases(spec, "", str(g4), cache, said.append)
            write_records(g4, [gold4_record(0, "fake:x", ct), gold4_record(1, "fake:y", ct)])
            self.assertEqual(self.R.frozen_cases(spec, "", str(g4), cache, said.append), (first, record))
            self.assertEqual(len(first["gold4"]), 1)
            self.assertTrue(any("the case list of the chain's first round" in s for s in said), said)
            # another plan's block is another chain's list, read anew
            other = {"gold4": gold4_spec(max_persons={"training": 9})}
            self.assertEqual(len(self.R.frozen_cases(other, "", str(g4), cache, said.append)[0]["gold4"]), 2)
            # a list that cannot be read back is read anew, never taken as an empty one
            held = sorted(cache.glob("cases-*.json"))
            self.assertEqual(len(held), 2)
            for path in held:
                path.write_text("{")
            self.assertEqual(len(self.R.frozen_cases(spec, "", str(g4), cache, said.append)[0]["gold4"]), 2)
        self.assertEqual(sorted(p.suffix for p in cache.iterdir()), [".json", ".json"])

    def test_the_screen_rows_gold_tier_3_reads_hold_no_person_of_a_test_list_and_each_person_in_one_part(self):
        for name in ("qa_gold_smoke", "qa_gold"):
            plan = json.loads((ROOT / "grid" / "qaloop" / f"{name}.json").read_text(encoding="utf-8"))
            rows = self.X.gold3_rows(plan["gold"]["gold3"])
            self.assertFalse({r["person"] for r in rows} & self.X.test_persons())
            self.assertTrue(all(r["part"] in self.X.PARTS for r in rows))
            parts = {}
            for r in rows:
                parts.setdefault(r["person"], set()).add(r["part"])
            self.assertTrue(all(len(p) == 1 for p in parts.values()))


@unittest.skipIf(MISSING_READ, f"needs numpy, scipy and nibabel ({', '.join(MISSING_READ)} missing)")
class RadiographTest(unittest.TestCase):
    """The radiograph's geometry, against the projection the landmarks take, and the CT's
    attenuation brought down by blocks with the world kept where it was."""

    def setUp(self):
        self.X = round_tool().X

    def test_a_ball_casts_its_shadow_where_its_centre_projects_and_as_deep_as_it_is_wide(self):
        X, G = self.X, self.X.G
        shape = (90, 80, 60)
        A = np.diag([0.8, 1.1, 1.6, 1.0])
        turn = np.radians(20.0)
        A[:3, :3] = np.array([[np.cos(turn), -np.sin(turn), 0], [np.sin(turn), np.cos(turn), 0], [0, 0, 1]]) @ A[:3, :3]
        A[:3, 3] = [-30.0, -45.0, -45.0]
        ijk = np.stack(np.meshgrid(*[np.arange(k) for k in shape], indexing="ij"), -1).reshape(-1, 3)
        world = ijk @ A[:3, :3].T + A[:3, 3]
        centre = np.array([12.0, -9.0, 7.0])
        mu = (np.linalg.norm(world - centre, axis=1) <= 8.0).astype(np.float32).reshape(shape)
        self.assertAlmostEqual(float(mu.sum()) * 0.8 * 1.1 * 1.6, 4 / 3 * np.pi * 8.0 ** 3, delta=100.0)  # whole on the grid
        for view in ("ap", "lat"):
            K, R, t = G.carm_camera(np.array([6.0, -4.0, 3.0]), (1, 0, 0), (0, 1, 0), (0, 0, 1), view, 7, -5, 12, 650.0,
                                    1150.0, 0.5, 128)
            P = G.projection_matrix(K, R, t)
            image = X.drr(mu, A, P, 128, step_mm=0.5)
            v, u = np.nonzero(image > 0)
            weight = image[v, u]
            centroid = np.array([(u + 0.5) @ weight, (v + 0.5) @ weight]) / weight.sum()
            np.testing.assert_allclose(centroid, G.project(P, centre[None])[0], atol=0.5)
            self.assertAlmostEqual(float(image.max()), 16.0, delta=1.0)

    def test_a_block_sits_at_the_mean_of_its_voxels(self):
        # Each world coordinate is linear in the voxel, so a block's mean of it is the coordinate of the
        # block's centre, which the coarse affine must give.
        A = np.diag([0.7, 0.9, 1.3, 1.0])
        A[:3, :3] = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]) @ A[:3, :3]
        A[:3, 3] = [3.0, -4.0, 5.0]
        ijk = np.stack(np.meshgrid(*[np.arange(k) for k in (25, 31, 17)], indexing="ij"), -1)
        world = ijk @ A[:3, :3].T + A[:3, 3]
        for axis in range(3):
            mu, B = self.X.coarse(world[..., axis].astype(np.float32), A)
            self.assertEqual(mu.shape, (25 // 3, 31 // 2, 17 // 2))
            blocks = np.stack(np.meshgrid(*[np.arange(k) for k in mu.shape], indexing="ij"), -1)
            np.testing.assert_allclose(mu, (blocks @ B[:3, :3].T + B[:3, 3])[..., axis], atol=1e-4)
        rng = np.random.default_rng(3)
        volume = rng.random((25, 31, 17)).astype(np.float32)
        mu, _ = self.X.coarse(volume, A)
        self.assertAlmostEqual(float(mu.sum(dtype=float)) * 12, float(volume[:24, :30, :16].sum(dtype=float)), delta=1e-2)

    def test_a_stored_ct_is_read_by_slabs_as_it_would_be_whole(self):
        import nibabel as nib

        rng = np.random.default_rng(4)
        stored = rng.integers(0, 2500, size=(20, 18, 23)).astype(np.int16)
        A = np.diag([0.7, 0.9, 1.3, 1.0])
        A[:3, 3] = [3.0, -4.0, 5.0]
        with tempfile.TemporaryDirectory() as folder:
            image = nib.Nifti1Image(stored, A)
            image.header.set_slope_inter(1.0, -1024.0)
            nib.save(image, Path(folder) / "ct.nii.gz")
            mu, B = self.X.coarse_attenuation(nib.load(Path(folder) / "ct.nii.gz"), slab=3)
        want, want_affine = self.X.coarse(self.X.attenuation(stored.astype(np.float32) - 1024.0), A)
        np.testing.assert_allclose(mu, want, rtol=1e-5, atol=1e-6)
        np.testing.assert_allclose(B, want_affine)
        np.testing.assert_array_equal(self.X.attenuation([-2000.0, -1000.0, 0.0, 1000.0]), [0.0, 0.0, 1.0, 2.0])

    def test_the_field_is_the_frames_circle_less_its_margin(self):
        mask = self.X.field_mask(64)
        self.assertTrue(mask[32, 32] and not mask[0, 0] and not mask[0, 63])
        inside = self.X.in_field(np.array([[32.0, 32.0], [32.0, 1.0], [32.0, 30.0 - 32.0 + 64.0], [np.nan, 32.0]]), 64)
        self.assertEqual(inside.tolist(), [True, False, False, False])


@unittest.skipIf(MISSING_READ, f"needs numpy, scipy and nibabel ({', '.join(MISSING_READ)} missing)")
class StandInTest(unittest.TestCase):
    """A stand-in read whole: a typical phantom from T12 to L5, its landmarks, axes and sacrum, its
    radiographs, the runs and the presence the round reads of it, and its cache file."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, VENDORED)
        cls.X = round_tool().X
        cls.case = cls.X.stand_in_case(8_000_000, "gold3", "validation", SMALL)

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(VENDORED)

    def test_the_column_is_read_whole_and_upright_with_its_sacrum_below_its_last_level(self):
        case = self.case
        self.assertEqual(case["levels"], LEVELS)
        self.assertEqual(case["landmarks"].shape, (6, 18, 3))
        self.assertTrue(np.isfinite(case["landmarks"]).all())
        axes = case["axes"]
        np.testing.assert_allclose(axes.T @ axes, np.eye(3), atol=1e-9)
        self.assertAlmostEqual(float(np.linalg.det(axes)), 1.0, places=9)
        heights = self.X.level_centres(case["landmarks"]) @ axes[:, 2]
        self.assertTrue((np.diff(heights) < 0).all(), heights)      # T12 at the top, each level below the last
        below = heights[-1] - float(case["sacrum"] @ axes[:, 2])
        self.assertTrue(15.0 < below < 60.0, below)
        self.assertTrue(case["stand_in"])

    def test_each_radiograph_is_dark_outside_the_field_and_its_bodies_project_into_it(self):
        frames, X = self.case["frames"], self.X
        self.assertEqual([(f["view"], f["field"]) for f in frames], [("ap", 230.0), ("lat", 230.0)])
        mask = X.field_mask(SMALL["size"])
        centres = X.level_centres(self.case["landmarks"])
        for frame in frames:
            image = frame["image"]
            self.assertEqual((image.shape, image.dtype), ((128, 128), np.float32))
            self.assertTrue(np.isfinite(image).all())
            self.assertEqual(float(np.abs(image[~mask]).max()), 0.0)
            self.assertGreater(float(image[mask].max()), 0.0)
            self.assertTrue(X.in_field(X.G.project(frame["P"], centres), SMALL["size"]).any())

    def test_the_runs_carry_the_tier_and_a_person_draws_the_same_frames_every_round(self):
        X = self.X
        runs = X.case_samples(self.case, SMALL)
        self.assertTrue(runs)
        for run in runs:
            self.assertIn(run["view"], ("ap_gold3", "lat_gold3"))
            self.assertEqual((run["type"], run["person"]), ("typical", self.case["person"]))
            at = [LEVELS.index(n) for n in run["names"]]
            self.assertEqual(at, list(range(at[0], at[0] + len(at))))
            self.assertTrue(2 <= len(at) <= SMALL["k_max"])
            self.assertIn(run["anchor"], ("none", "bottom"))
            if run["anchor"] == "bottom":
                self.assertEqual(run["names"][-1], "L5")
        again = X.case_samples(self.case, SMALL)
        self.assertEqual([r["names"] for r in again], [r["names"] for r in runs])
        for a, b in zip(again, runs):
            np.testing.assert_array_equal(a["points"], b["points"])
        other = X.case_samples(dict(self.case, person="standin:gold3:other"), SMALL)
        self.assertFalse(len(other) == len(runs) and all(
            a["points"].shape == b["points"].shape and np.allclose(a["points"], b["points"], equal_nan=True)
            for a, b in zip(other, runs)))
        self.assertEqual({r["anchor"] for r in X.case_samples(self.case, SMALL, ("none",))}, {"none"})

    def test_presence_is_read_on_each_radiograph_and_the_pixels_then_dropped(self):
        presence = self.X.case_presence(self.case, {}, SMALL["size"])
        self.assertEqual(presence.shape, (2, 18))
        read = presence[np.isfinite(presence)]
        self.assertTrue(read.size and ((read >= 0) & (read <= 1)).all())
        dropped = self.X.without_images(self.case)
        self.assertTrue(all("image" not in f and "P" in f for f in dropped["frames"]))
        self.assertIn("image", self.case["frames"][0])

    def test_the_cache_gives_back_the_case_it_was_made_from(self):
        X = self.X
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "case.npz")
            X.save_case(path, self.case)
            self.assertEqual(os.listdir(folder), ["case.npz"])
            back = X.load_case(path, {"tier": "gold3", "person": self.case["person"], "part": "validation"})
        self.assertEqual((back["levels"], back["stand_in"], back["part"]), (LEVELS, True, "validation"))
        np.testing.assert_array_equal(back["landmarks"], self.case["landmarks"])
        np.testing.assert_array_equal(back["sacrum"], self.case["sacrum"])
        np.testing.assert_array_equal(back["axes"], self.case["axes"])
        for a, b in zip(back["frames"], self.case["frames"], strict=True):
            self.assertEqual((a["view"], a["field"]), (b["view"], b["field"]))
            np.testing.assert_array_equal(a["P"], b["P"])
            np.testing.assert_allclose(a["image"], b["image"], rtol=2e-3, atol=1e-3)

    def test_a_case_is_kept_under_its_inputs_and_the_radiographs_settings_alone(self):
        X = self.X
        case = {"tier": "gold3", "item": "standin:gold3:1", "person": "standin:gold3:1", "part": "training",
                "type": "typical", "seed": 1, "stand_in": True}
        key = X.case_key(case, SMALL)
        self.assertEqual(key, X.case_key(dict(case), dict(SMALL, frames_per_view=8, k_max=6, noise_px=1.0)))
        for changed in (dict(SMALL, size=256), dict(SMALL, fields_mm=[300]), dict(SMALL, drr_per_view=2),
                        dict(SMALL, pose={"yaw": 5.0})):
            self.assertNotEqual(key, X.case_key(case, changed))
        self.assertNotEqual(key, X.case_key(dict(case, seed=2), SMALL))

    def test_a_case_job_reads_once_and_refuses_in_words_that_name_no_file(self):
        X = self.X
        case = {"tier": "gold3", "item": "standin:gold3:1", "person": "standin:gold3:1", "part": "training",
                "type": "typical", "seed": 1, "stand_in": True}
        other = dict(case, seed=3, item="standin:gold3:3", person="standin:gold3:3")
        with tempfile.TemporaryDirectory() as cache, mock.patch.dict(os.environ):
            with mock.patch.object(X, "stand_in_case", return_value=self.case) as made:
                path, why = X.case_job((case, SMALL, cache))
                self.assertIsNone(why)
                self.assertEqual(X.case_job((case, SMALL, cache)), (path, None))
                self.assertEqual(made.call_count, 1)            # the cache file answers the second time
            refused = X.CaseRefused("the oracle read no level of the column")
            with mock.patch.object(X, "stand_in_case", side_effect=refused):
                self.assertEqual(X.case_job((other, SMALL, cache)), (None, "the oracle read no level of the column"))
            with mock.patch.object(X, "stand_in_case", side_effect=OSError("/data/fake/0001.nii.gz: no such file")):
                self.assertEqual(X.case_job((other, SMALL, cache)), (None, "OSError"))
            self.assertEqual(os.environ.get("JAX_PLATFORMS"), "cpu")
            self.assertEqual(os.listdir(cache), [os.path.basename(path)])


def write_gold_ct(folder, X, seed):
    """A phantom's CT and bone map written as a gold tier's files: the CT stored as whole numbers with
    a slope and an intercept, as scanners store it; the map with a sacrum (28) drawn as a box below L5
    and a label of another bone (30) in a corner; and the same map with no sacrum. Returns the map as
    written, the affine its file holds, the box's voxel bounds and the three paths."""
    import nibabel as nib
    from autoanatomist import phantom

    rng = np.random.default_rng(seed)
    levels = X.S.column_of("typical", seed)
    tilt = (tuple(float(v) for v in rng.normal(size=3)), float(rng.uniform(0.0, 10.0)))
    ph = phantom.render(levels, spacing=(1.5,) * 3, tilt=tilt, sub=1, noise_hu=0.0, seed=seed, margin=40.0)
    labels = ph.labels.astype(np.int16)
    inv = np.linalg.inv(ph.affine)
    below = np.argwhere(labels == IDS3["L5"]).mean(axis=0) - (inv[:3, :3] @ ph.rotations[-1][:, 2]) * 40.0
    lo = np.maximum(np.round(below - 10).astype(int), 0)
    hi = np.minimum(np.round(below + 10).astype(int), np.array(labels.shape) - 1)
    box = labels[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]]
    box[box == 0] = IDS3["sacrum"]
    corner = labels[:4, :4, :4]
    corner[corner == 0] = 30
    stored = np.round(ph.hu + 1024.0).astype(np.int16)
    ct = nib.Nifti1Image(stored, ph.affine)
    ct.header.set_slope_inter(1.0, -1024.0)
    paths = [Path(folder) / name for name in ("ct.nii.gz", "labels.nii.gz", "bare.nii.gz")]
    nib.save(ct, paths[0])
    nib.save(nib.Nifti1Image(labels, ph.affine), paths[1])
    nib.save(nib.Nifti1Image(np.where(labels == IDS3["sacrum"], 0, labels).astype(np.int16), ph.affine), paths[2])
    # The header keeps the affine as float32, and the oracle's landmarks move by a few tenths of a
    # millimetre with that rounding, so the map is read back under the affine the file holds.
    return labels, np.asarray(nib.load(paths[1]).affine, float), (lo, hi), [str(p) for p in paths]


@unittest.skipIf(MISSING_READ, f"needs numpy, scipy and nibabel ({', '.join(MISSING_READ)} missing)")
class GoldCtTest(unittest.TestCase):
    """A gold CT read from its files as the grid holds them, its landmarks read from its bone map
    and each level's bone in the radiographs where its landmarks project."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, VENDORED)
        cls.X = round_tool().X
        cls.tmp = tempfile.TemporaryDirectory()
        cls.labels, cls.affine, cls.box, (ct, labels, bare) = write_gold_ct(cls.tmp.name, cls.X, 500)
        cls.case = {"tier": "gold3", "item": "fake:0500", "person": "fake:0500", "part": "validation", "type": "typical",
                    "ct": ct, "labels": labels, "ids": dict(IDS3), "stand_in": False}
        cls.bare = dict(cls.case, labels=bare)
        cls.read = cls.X.read_case(cls.case, SMALL)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        sys.path.remove(VENDORED)

    def test_the_landmarks_are_the_maps_and_the_sacrum_its_box(self):
        read = self.read
        self.assertEqual(read["levels"], LEVELS)
        self.assertTrue(np.isfinite(read["landmarks"]).all())
        marks, _ = self.X.read_column(self.labels, self.affine, IDS3, LEVELS)
        np.testing.assert_allclose(read["landmarks"], marks, atol=1e-6)
        at = np.linalg.inv(self.affine) @ np.append(read["sacrum"], 1.0)
        lo, hi = self.box
        self.assertTrue(((at[:3] >= lo - 1) & (at[:3] <= hi + 1)).all(), (at, lo, hi))
        self.assertFalse(read["stand_in"])

    def test_each_level_lies_in_its_own_shadow_and_two_levels_off_in_none(self):
        X, G = self.X, self.X.G
        centres = X.level_centres(self.read["landmarks"])
        self.assertEqual(len(self.read["frames"]), 2)
        for frame in self.read["frames"]:
            uv = G.project(frame["P"], centres)
            seen = np.flatnonzero(X.in_field(uv, SMALL["size"]))
            self.assertGreaterEqual(len(seen), 2)
            for i in seen:
                shadow = X.drr(*X.coarse((self.labels == IDS3[LEVELS[i]]).astype(np.float32), self.affine), frame["P"],
                               SMALL["size"])
                u, v = (int(x) for x in uv[i])
                self.assertGreater(float(shadow[v, u]), 10.0, (frame["view"], LEVELS[i]))
                for j in seen:
                    if abs(int(j) - int(i)) >= 2:
                        u, v = (int(x) for x in uv[j])
                        self.assertLess(float(shadow[v, u]), 0.5, (frame["view"], LEVELS[i], LEVELS[j]))

    def test_a_map_that_draws_no_sacrum_is_refused_in_words(self):
        with tempfile.TemporaryDirectory() as cache, mock.patch.dict(os.environ):
            self.assertEqual(self.X.case_job((self.bare, SMALL, cache)), (None, "the label map draws no sacrum"))
            self.assertEqual(os.listdir(cache), [])


@unittest.skipIf(MISSING_READ, f"needs numpy, scipy and nibabel ({', '.join(MISSING_READ)} missing)")
class NetworkRowTest(unittest.TestCase):
    """The network's reading of a held-out case: its row, and the spine-only copy of its bone map."""

    def setUp(self):
        self.X = round_tool().X

    def test_a_held_out_ct_is_one_volume_row_and_a_stand_in_one_phantom_row(self):
        case = {"tier": "gold4", "item": "u7", "ct": "/data/u7.nii.gz", "labels": "/run/labels/u7.nii.gz",
                "ids": dict(IDS4), "levels": LEVELS, "stand_in": False}
        row = self.X.network_row(case, "/work/gold")
        self.assertEqual((row["kind"], row["id"], row["ct"], row["frame"]), ("volume", "gold4:u7", "/data/u7.nii.gz", "oracle"))
        self.assertEqual(row["names"], {str(IDS4[lv]): lv for lv in LEVELS})
        self.assertEqual(row["seed"], self.X.row_seed("gold4:u7"))
        self.assertTrue(row["labels"].startswith("/work/gold/labels/gold4-") and row["labels"].endswith(".nii.gz"))
        self.assertNotEqual(row["labels"], self.X.network_row(dict(case, tier="gold3"), "/work/gold")["labels"])
        stand = self.X.network_row({"stand_in": True, "person": "standin:gold3:8000000", "seed": 8_000_000}, "/work")
        self.assertEqual((stand["kind"], stand["seed"], stand["start"], stand["count"]), ("phantom", 8_000_000, "T12", 6))

    def test_the_spine_only_copy_keeps_the_named_vertebrae_alone_on_the_same_grid(self):
        import nibabel as nib

        stored = np.zeros((12, 10, 8), np.float32)
        for i, value in enumerate((19, 20, 21, 22, 23, 24, 28, 26, 30)):
            stored[i] = value + (1e-4 if value == 21 else 0.0)            # one stored as a float a hair off
        affine = np.diag([0.8, 0.8, 2.5, 1.0])
        affine[:3, 3] = [-5.0, 7.0, 11.0]
        case = {"tier": "gold3", "item": "fake:0001", "ct": "", "labels": "", "ids": dict(IDS3), "levels": LEVELS,
                "stand_in": False}
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "map.nii.gz"
            nib.save(nib.Nifti1Image(stored, affine), source)
            row = self.X.network_row(dict(case, labels=str(source)), folder)
            self.X.spine_only_copy(str(source), row["labels"], [int(v) for v in row["names"]])
            image = nib.load(row["labels"])
            kept = np.asarray(image.dataobj)
            self.assertEqual(kept.dtype, np.int16)
            np.testing.assert_allclose(image.affine, affine)
            self.assertEqual(sorted(np.unique(kept).tolist()), [0, 19, 20, 21, 22, 23, 24])
            self.assertEqual(os.listdir(Path(row["labels"]).parent), [Path(row["labels"]).name])


if __name__ == "__main__":
    unittest.main()
