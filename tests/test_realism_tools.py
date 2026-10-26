"""tools/realism.py's file side on synthetic arrays (the Flux realism programme,
docs/research/flux-realism/README.md): FluXray's samples checked against the paper's pose grid,
ENHANCE.PET's labels mapped onto MOOSE's dense ids by name, the 256-pixel canvas, the two-sample
tests reading identical sets as chance and shifted sets as separable, Benjamini-Hochberg over the
feature spaces, the paired filter per pose group, the PNG round trip, the trainer's pairs and
configuration, the subject split, and the endplate angle read from a tilted rectangle at 1024 and
at 256. It needs numpy and the package's checkers (beartype, icontract), so it runs in the train
environment and skips under a plain python3."""

import importlib.util
import json
import math
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEEDED = ("numpy", "beartype", "icontract")
MISSING = [name for name in NEEDED if importlib.util.find_spec(name) is None]


def load():
    spec = importlib.util.spec_from_file_location("realism_tool_under_test", ROOT / "tools" / "realism.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tilted_rectangle(side, degrees, left=None, width=None, top=None, height=None):
    """A body whose superior edge rises by `degrees` from left to right, as a boolean mask."""
    import numpy as np

    left = side // 4 if left is None else left
    width = side // 2 if width is None else width
    top = side // 2 if top is None else top
    height = side // 8 if height is None else height
    mask = np.zeros((side, side), dtype=bool)
    slope = math.tan(math.radians(degrees))
    for column in range(left, left + width):
        start = int(round(top + slope * (column - left)))
        mask[start:start + height, column] = True
    return mask


@unittest.skipIf(MISSING, f"needs the train environment ({', '.join(MISSING)} missing)")
class RealismToolTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tool = load()
        cls.realism = cls.tool.realism

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(__import__("shutil").rmtree, self.tmp, ignore_errors=True)

    def sample(self, sample_id, subject, pose_id, y, z, alpha, **extra):
        row = {"sample_id": sample_id, "subject_id": subject, "pose_id": pose_id, "y": y, "z": z, "alpha_deg": alpha,
               "x": 0.0, "beta_deg": 0.0, "gamma_deg": 0.0}
        row.update(extra)
        return row

    def test_the_pose_check_keeps_grid_poses_and_reports_the_rest(self):
        rows = [self.sample("0001_0", "0001", 0, 650, -300, 0), self.sample("0001_7", "0001", 7, 650.0, -200.0, 90.0),
                self.sample("0002_3", "0002", 3, 700, -300, 0), self.sample("0002_4", "0002", 4, 650, -300, 0, x=5.0)]
        found = self.tool.poses_from_samples(rows)
        self.assertEqual([s["sample_id"] for s in found["samples"]], ["0001_0", "0001_7"])
        self.assertEqual(found["samples"][0]["grid_pose"], 0)
        self.assertEqual((found["samples"][1]["y"], found["samples"][1]["z"], found["samples"][1]["alpha"]), (650, -200, 90))
        self.assertEqual(found["subjects"], ["0001"])
        self.assertEqual(found["mismatches"], ["0002_3", "0002_4"])

    def test_enhance_labels_map_onto_moose_dense_ids_by_name(self):
        enhance = {"clin_ct_vertebrae": {"1": "vertebra_C1", "25": "vertebra_L6", "28": "sacrum", "26": "hip_left"},
                   "clin_ct_peripheral_bones": {"3": "fingers_left"}, "clin_ct_ribs": {"27": "sternum", "1": "rib_left_1"},
                   "clin_ct_cardiac": {"1": "heart_myocardium"}}
        stored = {"59": "vertebra_c1", "83": "vertebra_l6", "86": "sacrum", "3": "phalange_left", "58": "sternum", "32": "rib_left_1"}
        mapping = self.tool.moose_dense_ids(enhance, stored)
        self.assertEqual(mapping[("Vertebrae", 1)], 59)
        self.assertEqual(mapping[("Vertebrae", 25)], 83)
        self.assertEqual(mapping[("Vertebrae", 28)], 86)
        self.assertEqual(mapping[("Peripheral-Bones", 3)], 3)
        self.assertEqual(mapping[("Ribs", 27)], 58)
        self.assertNotIn(("Vertebrae", 26), mapping)
        self.assertEqual(len(mapping), 6)
        # the committed copy of the bucket's labels.json reads, trailing commas and all
        labels = self.tool.load_labels_json(self.tool.ENHANCE_LABELS)
        self.assertEqual(labels["clin_ct_vertebrae"]["28"], "sacrum")
        self.assertEqual(len(labels["clin_ct_vertebrae"]), 28)
        self.assertEqual(len(labels["clin_ct_peripheral_bones"]), 31)
        self.assertEqual(labels["clin_ct_ribs"]["27"], "sternum")

    def test_channel_targets_follow_aliases_and_drops(self):
        stored = {"1": "a", "2": "rib_left_9", "3": "vertebra_l6", "4": "b"}
        targets = self.tool.channel_targets(stored, ["a", "rib_9", "b"], {"rib_left_9": "rib_9"}, {"vertebra_l6"})
        self.assertEqual(targets, [1, 2, 0, 3])

    def test_the_canvas_pads_to_a_square_and_resizes_a_block_image(self):
        import numpy as np

        tall = np.ones((64, 32), dtype=np.float32)
        square = self.tool.pad_to_square(tall)
        self.assertEqual(square.shape, (64, 64))
        self.assertEqual(float(square[:, :16].sum()), 0.0)
        self.assertEqual(float(square[:, 16:48].sum()), 64 * 32)
        halves = np.zeros((1024, 1024), dtype=np.float32)
        halves[:, :512] = 1.0
        small = self.tool.resize(halves, 256)
        self.assertEqual(small.shape, (256, 256))
        self.assertTrue(np.all(small[:, :120] > 0.99))
        self.assertTrue(np.all(small[:, 136:] < 0.01))
        on_canvas = self.tool.canvas(halves, 256)
        self.assertEqual(on_canvas.shape, (256, 256))
        self.assertTrue(0.0 <= float(on_canvas.min()) and float(on_canvas.max()) <= 1.0)
        mask = np.zeros((8, 8), dtype=bool)
        mask[:2, :2] = True
        mask[2, 2] = True
        coarse = self.tool.block_majority(mask, 2)
        self.assertEqual(coarse.shape, (4, 4))
        self.assertTrue(bool(coarse[0, 0]))
        self.assertFalse(bool(coarse[3, 3]))

    def test_physics_features_are_fixed_length_and_deterministic(self):
        import numpy as np

        rng = np.random.default_rng(0)
        image = rng.random((256, 256), dtype=np.float32)
        first, second = self.tool.physics_features(image), self.tool.physics_features(image.copy())
        self.assertEqual(first.shape, second.shape)
        self.assertGreater(len(first), 20)
        self.assertTrue(np.allclose(first, second))
        self.assertTrue(np.all(np.isfinite(first)))
        other = self.tool.physics_features(np.clip(image * 0.3 + 0.2, 0, 1))
        self.assertFalse(np.allclose(first, other))

    def two_sets(self, shift, seed=1, subjects=12, each=4, dims=6):
        import numpy as np

        rng = np.random.default_rng(seed)
        a = rng.normal(size=(subjects * each, dims))
        b = rng.normal(size=(subjects * each, dims)) + shift
        groups_a = np.array([f"a{i // each}" for i in range(subjects * each)])
        groups_b = np.array([f"b{i // each}" for i in range(subjects * each)])
        return a, b, groups_a, groups_b

    def test_the_classifier_test_reads_like_sets_as_chance_and_shifted_sets_as_separable(self):
        a, b, ga, gb = self.two_sets(0.0)
        same = self.tool.c2st(a, b, ga, gb, 0, bootstraps=30, permutations=30)
        self.assertLess(same["auc"], 0.7)
        self.assertLessEqual(same["low"], same["auc"])
        self.assertLessEqual(same["auc"], same["high"])
        a, b, ga, gb = self.two_sets(3.0)
        apart = self.tool.c2st(a, b, ga, gb, 0, bootstraps=30, permutations=30)
        self.assertGreater(apart["auc"], 0.9)
        self.assertGreater(apart["low"], 0.6)
        self.assertLessEqual(apart["p"], 0.05)

    def test_mmd_frechet_and_kid_vanish_for_like_sets_and_grow_with_a_shift(self):
        import numpy as np

        a, b, _, _ = self.two_sets(0.0, seed=2)
        self.assertLess(self.tool.frechet(a, a.copy()), 1e-9)
        like = self.tool.mmd_test(a, b, 0, permutations=40)
        apart = self.tool.mmd_test(a, b + 3.0, 0, permutations=40)
        self.assertGreater(apart["mmd2"], like["mmd2"])
        self.assertLessEqual(apart["p"], 0.05)
        self.assertGreater(like["p"], 0.05)
        self.assertGreater(self.tool.frechet(a, b + 3.0), self.tool.frechet(a, b))
        self.assertGreater(self.tool.kid(a, b + 3.0, 0, subset=20, repeats=3), self.tool.kid(a, b, 0, subset=20, repeats=3))
        self.assertTrue(np.isfinite(self.tool.kid(a, a, 0, subset=20, repeats=3)))

    def test_benjamini_hochberg_steps_up_from_the_largest_and_never_passes_one(self):
        # 0.03 at rank 2 of 3 would be 0.045, but q never exceeds the q of the larger p above it
        qs = self.tool.benjamini_hochberg([0.01, 0.04, 0.03])
        self.assertAlmostEqual(qs[0], 0.03)
        self.assertAlmostEqual(qs[1], 0.04)
        self.assertAlmostEqual(qs[2], 0.04)
        self.assertEqual(self.tool.benjamini_hochberg([0.5, 0.9]), [0.9, 0.9])
        self.assertEqual(self.tool.benjamini_hochberg([1.0]), [1.0])

    def test_judge_spaces_reads_mmd_at_its_q_and_writes_each_verdict(self):
        def space(low, high, p, null_high):
            return {"a_vs_b": {"c2st": {"auc": (low + high) / 2, "low": low, "high": high, "p": 0.5}, "mmd": {"p": p}},
                    "b_split_half": {"c2st": {"high": null_high}}}

        spaces = {"physics": space(0.45, 0.55, 0.04, 0.56), "flexray": space(0.5, 0.58, 0.9, 0.55), "imagenet": space(0.7, 0.8, 0.001, 0.5)}
        words = self.tool.judge_spaces(spaces)
        # 0.04 becomes q 0.06 over three spaces, so physics is matched, not undecided
        self.assertEqual(spaces["physics"]["a_vs_b"]["mmd"]["q"], 0.06)
        self.assertEqual(words, ["matched", "indistinguishable", "separable"])
        self.assertEqual(self.tool.worst(words), "separable")
        self.assertEqual(self.tool.worst([]), "undecided")

    def test_soft_dice_averages_the_present_channels_and_the_background(self):
        import numpy as np

        truth = np.zeros((2, 4, 4), dtype=bool)
        truth[0, :2, :] = True
        probabilities = np.zeros((2, 4, 4), dtype=np.float32)
        # nothing claimed: the present channel scores 0, the background is claimed whole and true on 8 of 16
        empty = self.tool.soft_dice(probabilities, truth)
        self.assertAlmostEqual(empty, (0.0 + 2 * 8 / (16 + 8)) / 2, places=5)
        probabilities[0] = truth[0]
        self.assertAlmostEqual(self.tool.soft_dice(probabilities, truth), 1.0, places=5)

    def test_the_filter_works_per_pose_group_and_keeps_each_groups_best(self):
        scores = [{"sample_id": f"s{i}", "pose_id": pose, "raw_soft_dice": 0.5, "flux_soft_dice": flux}
                  for i, (pose, flux) in enumerate([(0, 0.5), (0, 0.51), (0, 0.49), (0, 0.0), (1, 0.6), (1, 0.2)])]
        rows = self.tool.filter_rows(scores)
        by_id = {r["sample_id"]: r for r in rows}
        self.assertEqual(len(rows), 6)
        self.assertTrue(by_id["s1"]["kept"] and by_id["s4"]["kept"])
        self.assertFalse(by_id["s3"]["kept"])
        self.assertEqual(by_id["s0"]["bound"], by_id["s2"]["bound"])
        self.assertNotEqual(by_id["s0"]["bound"], by_id["s4"]["bound"])
        self.assertAlmostEqual(by_id["s4"]["delta"], 0.1)

    def test_a_png_round_trips_and_a_folder_lists_images_by_stem(self):
        import numpy as np

        rng = np.random.default_rng(3)
        image = rng.random((8, 8), dtype=np.float32)
        path = self.tmp / "pic.png"
        self.tool.write_png(path, image)
        back = self.tool.read_png(path)
        self.assertEqual(back.shape, (8, 8))
        # the trainer's PNGs are 8-bit, so a value comes back within half a grey level
        self.assertLess(float(np.abs(back - image).max()), 1 / 255)
        np.save(self.tmp / "0001_3.npy", image.astype(np.float16))
        found = self.tool.images_in(self.tmp)
        self.assertEqual(set(found), {"pic", "0001_3"})
        self.assertEqual(self.tool.subject_of("0001_3"), "0001")
        self.assertLess(float(np.abs(self.tool.read_grey(found["0001_3"]) - image).max()), 1e-2)

    def test_pairs_and_the_trainers_configuration_follow_the_target_size(self):
        import numpy as np

        control, target = self.tmp / "render" / "raw", self.tmp / "fluxray" / "img"
        control.mkdir(parents=True)
        target.mkdir(parents=True)
        rng = np.random.default_rng(4)
        # a 512-pixel render against FluXray's 256-pixel images: the pairs take the target's size
        for stem in ("0001_0", "0001_5", "0002_0"):
            np.save(control / f"{stem}.npy", rng.random((512, 512), dtype=np.float32))
        for stem in ("0001_0", "0002_0", "0003_0"):
            np.save(target / f"{stem}.npy", rng.random((256, 256), dtype=np.float32).astype(np.float16))
        (self.tmp / "train.txt").write_text("subject\n0001\n", encoding="utf-8")
        pairs = self.tmp / "pairs"
        self.assertEqual(self.tool.main(["pairs", "--control", str(self.tmp / "render"), "--target", str(self.tmp / "fluxray"),
                                         "--out", str(pairs), "--only", str(self.tmp / "train.txt")]), 0)
        manifest = json.loads((pairs / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual((manifest["pairs"], manifest["pixels"]), (1, 256))
        self.assertTrue((pairs / "control" / "0001_0.png").exists() and (pairs / "target" / "0001_0.png").exists())
        self.assertEqual((pairs / "target" / "0001_0.txt").read_text(encoding="utf-8"), self.realism.PROMPT + "\n")
        self.assertEqual(self.tool.read_png(pairs / "control" / "0001_0.png").shape, (256, 256))
        config_path = self.tmp / "config.json"
        self.assertEqual(self.tool.main(["lora-config", "--pairs", str(pairs), "--out", str(config_path), "--training-folder", str(self.tmp / "train")]), 0)
        config = json.loads(config_path.read_text(encoding="utf-8"))
        process = config["config"]["process"][0]
        self.assertEqual(process["datasets"][0]["resolution"], [256])
        self.assertEqual(process["model"]["arch"], "flux2_klein_4b")
        self.assertEqual(self.tool.main(["lora-config", "--pairs", str(pairs), "--out", str(config_path), "--rank", "0"]), 2)

    def test_the_split_is_by_subject_fixed_by_the_seed_and_evenly_spread_poses_span_the_grid(self):
        subjects = [f"{i:04d}" for i in range(10)]
        taken, train, evaluation = self.tool.split_subjects(subjects, 0, 7)
        self.assertEqual(taken, subjects)
        self.assertEqual((len(train), len(evaluation)), (7, 3))
        self.assertEqual(sorted(train + evaluation), subjects)
        self.assertEqual(self.tool.split_subjects(subjects, 0, 7), (taken, train, evaluation))
        self.assertNotEqual(self.tool.split_subjects(subjects, 0, 8)[1], train)
        self.assertEqual(self.tool.split_subjects(subjects, 4, 7)[0], subjects[:4])
        with self.assertRaises(self.tool.Refused):
            self.tool.split_subjects(["0001"], 0, 7)
        self.assertEqual(self.tool.spread(list(range(10)), 4), [0, 2, 5, 7])
        self.assertEqual(self.tool.spread(list(range(3)), 0), [0, 1, 2])
        self.assertEqual(self.tool.spread(list(range(3)), 9), [0, 1, 2])
        listing = self.tmp / "only.csv"
        listing.write_text("subject_id,split\n0001,train\n0003,train\n", encoding="utf-8")
        self.assertEqual(self.tool.subject_filter(str(listing)), {"0001", "0003"})
        self.assertIsNone(self.tool.subject_filter(""))

    def test_the_endplate_angle_reads_a_tilted_body_at_1024_and_at_256(self):
        import numpy as np

        mask = tilted_rectangle(1024, 5.0)
        fine = self.tool.endplate_angle_deg(mask)
        self.assertAlmostEqual(fine, 5.0, delta=0.3)
        coarse = self.tool.endplate_angle_deg(self.tool.block_majority(mask, 4))
        self.assertAlmostEqual(coarse, 5.0, delta=1.0)
        self.assertIsNone(self.tool.endplate_angle_deg(np.zeros((16, 16), dtype=bool)))
        masks = self.tmp / "masks"
        masks.mkdir()
        channels = np.stack([mask, np.zeros_like(mask)])
        np.save(masks / "0001_0.npy", np.packbits(channels, axis=-1))
        rows = self.tool.measure_rows(masks, ["vertebra_l1", "sacrum"])
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["sample_id"], rows[0]["level"]), ("0001_0", "vertebra_l1"))
        self.assertAlmostEqual(rows[0]["angle_1024"], 5.0, delta=0.3)
        self.assertLess(rows[0]["difference"], 1.5)
        table = self.realism.measurement_rows()
        self.assertEqual(len(table), 6)
        self.assertGreater(min(r["angle_quantum_deg"] for r in table if r["pixels"] == 256), 1.0)
        summary = {"bodies": 1, "difference_median_deg": 0.5, "difference_p90_deg": 0.5, "table": table}
        page = self.tool.measure_markdown(summary)
        self.assertIn("## realism measure: 1 lumbar endplates", page)
        self.assertEqual(page.count("\n| "), 2 + len(table))


if __name__ == "__main__":
    unittest.main()
