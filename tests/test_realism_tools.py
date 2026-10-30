"""tools/realism.py's file side on synthetic arrays (the Flux realism programme,
docs/research/flux-realism/README.md): FluXray's samples checked against the paper's pose grid,
ENHANCE.PET's labels mapped onto MOOSE's dense ids by name, the 256-pixel canvas, the two-sample
tests reading identical sets as chance and shifted sets as separable, Benjamini-Hochberg over the
feature spaces, the paired filter per pose group, the PNG round trip, the trainer's pairs and
configuration, the subject split and the seeded draws of CTs and poses, the neighbours of the
classifier test taken from other subjects only, the labels shuffled within the strata (by sample
where two sets hold the same samples, so a small paired shift is seen and a null is not piled at
1), the principal components each comparison read recorded, the seed arms judged apart, the inputs
refused before any GPU work where too few subjects have the plan's poses on the grid, the stats
stage's environment record, a render or an edit cut short redone and never skipped, and the
endplate angle read from a tilted rectangle at 1024 and at 256. It needs numpy and the package's
checkers (beartype, icontract), so it runs in the train environment and skips under a plain
python3."""

import ast
import contextlib
import importlib.util
import io
import json
import math
import subprocess
import sys
import tempfile
import types
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
        _, _, ga, gb = self.two_sets(0.0, seed=2)
        like = self.tool.mmd_test(a, b, ga, gb, 0, permutations=40)
        apart = self.tool.mmd_test(a, b + 3.0, ga, gb, 0, permutations=40)
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
                    "b_split_half": {"c2st": {"low": null_high - 0.1, "high": null_high}}}

        spaces = {"physics": space(0.45, 0.55, 0.04, 0.56), "flexray": space(0.5, 0.58, 0.9, 0.55), "imagenet": space(0.7, 0.8, 0.001, 0.5)}
        words = self.tool.judge_spaces(spaces)
        # 0.04 becomes q 0.06 over three spaces, so physics is matched, not undecided
        self.assertEqual(spaces["physics"]["a_vs_b"]["mmd"]["q"], 0.06)
        self.assertEqual(words, ["matched", "indistinguishable", "separable"])
        self.assertEqual(self.tool.worst(words), "separable")
        self.assertEqual(self.tool.worst([]), "undecided")

    def test_soft_dice_is_flexrays_over_the_channels_with_truth_and_channel_0_is_the_background(self):
        import numpy as np

        truth = np.zeros((3, 4, 4), dtype=bool)
        truth[1, :2, :] = True
        probabilities = np.zeros((3, 4, 4), dtype=np.float32)
        # nothing claimed: channel 1 scores 0 and so does the background, true on the 8 pixels no channel
        # claims; channel 2, with no truth, is left out
        self.assertAlmostEqual(self.tool.soft_dice(probabilities, truth), 0.0, places=5)
        # the background claimed whole: 2 x 8 / (16 + 8) on it, 0 on channel 1
        probabilities[0] = 1.0
        self.assertAlmostEqual(self.tool.soft_dice(probabilities, truth), (0.0 + 2 * 8 / (16 + 8)) / 2, places=5)
        probabilities[0], probabilities[1] = ~truth[1], truth[1]
        self.assertAlmostEqual(self.tool.soft_dice(probabilities, truth), 1.0, places=5)
        # the truth's own channel 0 is read as what no other channel claims, whatever the render left in it
        truth[0] = True
        self.assertAlmostEqual(self.tool.soft_dice(probabilities, truth), 1.0, places=5)

    def test_the_render_projects_hard_masks_at_flexrays_training_threshold(self):
        import inspect

        self.assertIn("seg_threshold=0.0", inspect.getsource(self.tool.render_one))

    def test_a_records_subject_is_read_from_its_metadata_and_never_from_the_sample_key(self):
        self.assertEqual(self.tool.record_subject(types.SimpleNamespace(data_id="s1", subject_id="s1", metadata={"subject": "0007"})), "0007")
        self.assertEqual(self.tool.record_subject(types.SimpleNamespace(data_id="s1", subject_id="s1", metadata={})), "")
        self.assertEqual(self.tool.record_subject(types.SimpleNamespace(subject_id="s1", metadata={"subject_id": 12, "subject": "x"})), "12")
        self.assertEqual(self.tool.record_subject(types.SimpleNamespace(subject_id="s1", metadata=None)), "")

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

    def test_the_split_is_by_subject_and_the_subjects_and_poses_are_drawn_by_the_seed(self):
        subjects = [f"{i:04d}" for i in range(10)]
        taken, train, evaluation = self.tool.split_subjects(subjects, 0, 7)
        self.assertEqual(taken, subjects)
        self.assertEqual((len(train), len(evaluation)), (7, 3))
        self.assertEqual(sorted(train + evaluation), subjects)
        self.assertEqual(self.tool.split_subjects(subjects, 0, 7), (taken, train, evaluation))
        self.assertNotEqual(self.tool.split_subjects(subjects, 0, 8)[1], train)
        # four drawn by the seed, not the first four by name, and the same four whatever else landed
        drawn = self.tool.split_subjects(subjects, 4, 7)[0]
        self.assertEqual(drawn, self.realism.draw(subjects, 4, 7, "subject"))
        self.assertNotEqual(sorted(drawn), subjects[:4])
        fewer = [s for s in subjects if s not in drawn[2:]]
        self.assertEqual(self.tool.split_subjects(fewer, 2, 7)[0], drawn[:2])
        with self.assertRaises(self.tool.Refused):
            self.tool.split_subjects(["0001"], 0, 7)
        self.assertEqual(self.tool.shards_of(drawn, 3), [drawn[:3], drawn[3:]])
        poses = {"samples": [{"sample_id": f"{s}_{p}", "subject_id": s, "grid_pose": p} for s in ("0001", "0002") for p in range(9)]}
        chosen = self.tool.drawn_samples(poses, ["0001", "0002"], 3, 7)
        self.assertEqual([len(chosen[s]) for s in ("0001", "0002")], [3, 3])
        self.assertEqual(chosen, self.tool.drawn_samples(poses, ["0001", "0002"], 3, 7))
        self.assertNotEqual({r["grid_pose"] for r in chosen["0001"]}, {r["grid_pose"] for r in chosen["0002"]})
        self.assertEqual(self.tool.drawn_samples(poses, ["0001"], 3, 7)["0001"], chosen["0001"])
        self.assertEqual(len(self.tool.drawn_samples(poses, ["0001"], 0, 7)["0001"]), 9)
        listing = self.tmp / "only.csv"
        listing.write_text("subject_id,split\n0001,train\n0003,train\n", encoding="utf-8")
        self.assertEqual(self.tool.subject_filter(str(listing)), {"0001", "0003"})
        self.assertIsNone(self.tool.subject_filter(""))

    def test_no_neighbour_is_of_the_same_subject_in_either_set(self):
        import numpy as np

        rng = np.random.default_rng(5)
        offsets = rng.normal(scale=20.0, size=(8, 4))
        subjects = np.array([f"s{i % 8}" for i in range(32)])
        features = offsets[[i % 8 for i in range(32)]] + rng.normal(scale=0.1, size=(32, 4))
        nearest = self.tool.nearest_elsewhere(features, subjects, k=5)
        self.assertEqual(nearest.shape, (32, 5))
        self.assertFalse(np.any(subjects[nearest] == subjects[:, None]))

    def test_a_pair_of_sets_of_the_same_cts_reads_as_chance_and_not_below_it(self):
        import numpy as np

        # each CT's image in set a and in set b sit together, far from every other CT's: a neighbour
        # of the same CT in the other set would push the AUC to 0, and left out it is chance
        rng = np.random.default_rng(6)
        offsets = rng.normal(scale=20.0, size=(16, 5))
        groups = np.array([f"s{i // 3}" for i in range(48)])
        a = offsets[[i // 3 for i in range(48)]] + rng.normal(scale=0.1, size=(48, 5))
        b = offsets[[i // 3 for i in range(48)]] + rng.normal(scale=0.1, size=(48, 5))
        result = self.tool.c2st(a, b, groups, groups, 0, bootstraps=30, permutations=60)
        self.assertGreater(result["auc"], 0.3)
        self.assertLess(result["auc"], 0.7)
        self.assertGreater(result["p"], 0.05)
        moved = self.tool.c2st(a, b + 40.0, groups, groups, 0, bootstraps=30, permutations=60)
        self.assertGreater(moved["auc"], 0.9)
        self.assertLessEqual(moved["p"], 0.05)

    def test_labels_shuffle_within_a_shared_subject_and_whole_subjects_otherwise(self):
        import numpy as np

        labels = np.array([0, 0, 1, 1, 1, 0, 0, 1, 1])
        subjects = np.array(["m", "m", "m", "m", "m", "x", "x", "y", "y"])
        layers = self.tool.strata(labels, subjects)
        rng = np.random.default_rng(0)
        for _ in range(20):
            permuted = self.tool.permuted_labels(labels, layers, rng)
            self.assertEqual(int(permuted[:5].sum()), 3)
            self.assertEqual(len(set(permuted[5:7])), 1)
            self.assertEqual(len(set(permuted[7:9])), 1)
            self.assertEqual(sorted([permuted[5], permuted[7]]), [0, 1])

    def test_the_mmd_from_one_kernel_is_the_unbiased_mmd_of_the_two_sets(self):
        import numpy as np

        rng = np.random.default_rng(7)
        a, b = rng.normal(size=(7, 3)), rng.normal(size=(5, 3)) + 0.5
        pooled = np.concatenate([a, b])
        squared = ((pooled[:, None, :] - pooled[None, :, :]) ** 2).sum(axis=2)
        kernel = np.exp(-squared / 2.0)
        labels = np.array([0] * 7 + [1] * 5)
        kaa, kbb, kab = kernel[:7, :7], kernel[7:, 7:], kernel[:7, 7:]
        explicit = (kaa.sum() - 7) / 42 + (kbb.sum() - 5) / 20 - 2 * kab.mean()
        self.assertAlmostEqual(self.tool.mmd_of_kernel(kernel, labels), explicit, places=10)

    def test_an_edits_name_carries_its_sample_and_arm(self):
        self.assertEqual(self.tool.edit_name("0001_17", 1), "0001_17__a1")
        self.assertEqual((self.tool.arm_of("0001_17__a1"), self.tool.sample_of("0001_17__a1")), (1, "0001_17"))
        self.assertEqual((self.tool.arm_of("0001_17"), self.tool.sample_of("0001_17")), (None, "0001_17"))
        self.assertIsNone(self.tool.arm_of("__a1"))
        self.assertIsNone(self.tool.arm_of("0001__ax"))

    def test_a_space_whose_seed_arms_disagree_is_undecided(self):
        def entry(low, high, p):
            return {"c2st": {"auc": (low + high) / 2, "low": low, "high": high, "p": 0.5}, "mmd": {"p": p}}

        spaces = {"physics": {"a_vs_b": entry(0.45, 0.55, 0.5), "b_split_half": {"c2st": {"low": 0.44, "high": 0.56}},
                              "arms": {"a0": entry(0.45, 0.55, 0.5), "a1": entry(0.65, 0.75, 0.5)}},
                  "flexray": {"a_vs_b": entry(0.45, 0.55, 0.5), "b_split_half": {"c2st": {"low": 0.44, "high": 0.56}},
                              "arms": {"a0": entry(0.45, 0.55, 0.5), "a1": entry(0.45, 0.55, 0.5)}}}
        self.assertEqual(self.tool.judge_spaces(spaces), ["undecided", "matched"])
        self.assertEqual(spaces["physics"]["a_vs_b"]["verdict"], "matched")
        self.assertEqual(spaces["physics"]["arms"]["a1"]["verdict"], "separable")

    def test_a_space_whose_null_tells_a_set_from_itself_is_undecided_and_says_so(self):
        def entry(low, high, p):
            return {"c2st": {"auc": (low + high) / 2, "low": low, "high": high, "p": 0.5}, "mmd": {"p": p}}

        spaces = {"physics": {"a_vs_b": entry(0.45, 0.55, 0.5), "b_split_half": entry(0.62, 0.7, 0.5)},
                  "flexray": {"a_vs_b": entry(0.45, 0.55, 0.5), "b_split_half": entry(0.44, 0.56, 0.5),
                              "arms": {"a0": entry(0.45, 0.55, 0.5), "a1": entry(0.45, 0.55, 0.5)},
                              "arm_null": entry(0.65, 0.75, 0.5)},
                  "imagenet": {"a_vs_b": entry(0.45, 0.55, 0.5), "b_split_half": entry(0.44, 0.56, 0.5)}}
        self.assertEqual(self.tool.judge_spaces(spaces), ["undecided", "undecided", "matched"])
        self.assertEqual([spaces[s]["nulls_separable"] for s in spaces], [True, True, False])

    def write_set(self, folder, names, rng, shift=0.0):
        import numpy as np

        folder.mkdir(parents=True, exist_ok=True)
        for name in names:
            image = np.clip(rng.random((64, 64), dtype=np.float32) * 0.5 + 0.25 + shift, 0, 1)
            np.save(folder / f"{name}.npy", image.astype(np.float16))

    def test_stats_reads_subjects_by_the_index_and_reports_each_arm_and_the_pairs(self):
        import numpy as np

        rng = np.random.default_rng(8)
        samples = [f"{1000 + s}-{p}" for s in range(6) for p in range(2)]
        render = self.tmp / "render"
        render.mkdir()
        (render / "manifest.jsonl").write_text("".join(json.dumps({"sample_id": s, "subject_id": f"subj{s.split('-')[0]}", "grid_pose": 0}) + "\n"
                                                       for s in samples), encoding="utf-8")
        self.write_set(self.tmp / "kept", [self.tool.edit_name(s, arm) for s in samples for arm in (0, 1)], rng)
        self.write_set(self.tmp / "fluxray", samples, rng)
        out = self.tmp / "stats"
        self.assertEqual(self.tool.main(["stats", "--a", str(self.tmp / "kept"), "--b", str(self.tmp / "fluxray"), "--out", str(out),
                                         "--index", str(render), "--size", "64", "--require-spaces", "physics"]), 0)
        report = json.loads((out / "stats.json").read_text(encoding="utf-8"))
        self.assertEqual(report["sets"]["a"], {"n": 24, "subjects": 6})
        self.assertEqual(report["seed"], self.realism.REPLICATION.stats_seed)
        self.assertEqual(sorted(report["spaces"]["physics"]["arms"]), ["a0", "a1"])
        self.assertIn("arm_null", report["spaces"]["physics"])
        self.assertEqual(report["paired"]["pairs"], 24)
        self.assertIn(report["verdict"], self.realism.VERDICTS)
        self.assertIn("| physics |", (out / "stats.md").read_text(encoding="utf-8"))
        # 36 images of 57 physics features: k is what the data gives, recorded and said, never a bare 64
        physics = report["spaces"]["physics"]
        self.assertEqual(physics["a_vs_b"]["components"], 36)
        self.assertEqual(physics["b_split_half"]["components"], 12)
        self.assertEqual(physics["arm_null"]["components"], 24)
        self.assertIn("k here: physics 36", report["rules"]["distances"])
        self.assertIn("k here: physics 36", report["rules"]["mmd"])
        self.assertIn("each sample", report["rules"]["permutation"])
        # the edits and FluXray's images share their samples, the split halves share none
        self.assertEqual(physics["a_vs_b"]["c2st"]["strata"], "sample")
        self.assertEqual(physics["a_vs_b"]["mmd"]["strata"], "sample")
        self.assertEqual({entry["mmd"]["strata"] for entry in physics["arms"].values()}, {"sample"})
        self.assertEqual(physics["arm_null"]["c2st"]["strata"], "sample")
        self.assertEqual(physics["b_split_half"]["c2st"]["strata"], "subject")
        page = (out / "stats.md").read_text(encoding="utf-8")
        self.assertNotIn("FD64", page)
        self.assertIn("| k |", page)
        self.assertIn("physics 36", page)
        self.assertIn("sample for a against b and each arm, subject for b's split halves, sample for the arm null", page)
        self.assertEqual(self.tool.main(["stats", "--a", str(self.tmp / "kept"), "--b", str(self.tmp / "fluxray"), "--out", str(out),
                                         "--index", str(render), "--size", "64", "--require-spaces", "physics,imagenet"]), 2)
        np.save(self.tmp / "fluxray" / "stray.npy", np.zeros((64, 64), dtype=np.float16))
        self.assertEqual(self.tool.main(["stats", "--a", str(self.tmp / "kept"), "--b", str(self.tmp / "fluxray"), "--out", str(out),
                                         "--index", str(render), "--size", "64"]), 2)

    def test_keep_filters_every_shards_scores_at_once_and_links_the_kept_edits(self):
        import numpy as np

        edited = self.tmp / "zero-shot" / "edited"
        edited.mkdir(parents=True)
        rows = []
        for i, flux in enumerate([0.5, 0.51, 0.49, 0.0, 0.52, 0.5]):
            name = self.tool.edit_name(f"0001_{i}", 0)
            np.save(edited / f"{name}.npy", np.zeros((4, 4), dtype=np.float16))
            rows.append({"sample_id": name, "subject_id": f"000{i % 2}", "pose_id": 3, "raw_soft_dice": 0.5, "flux_soft_dice": flux})
        scores = self.tmp / "scores"
        self.tool.write_rows(scores / "000.csv", rows[:3], self.tool.SCORE_COLUMNS)
        self.tool.write_rows(scores / "001.csv", rows[3:], self.tool.SCORE_COLUMNS)
        out = self.tmp / "filter"
        self.assertEqual(self.tool.main(["keep", "--scores", str(scores), "--edited", str(self.tmp / "zero-shot"), "--out", str(out)]), 0)
        kept = sorted(path.stem for path in (out / "kept").iterdir())
        self.assertEqual(len(kept), 5)
        self.assertNotIn(self.tool.edit_name("0001_3", 0), kept)
        self.assertEqual(len(self.tool.read_rows(out / "filter_dropped.csv")), 1)

    def test_volumes_and_truth_are_found_however_deep_the_fetch_landed_them(self):
        (self.tmp / "ct" / "imaging-data" / "images" / "CT").mkdir(parents=True)
        (self.tmp / "ct" / "imaging-data" / "images" / "CT" / "0001.nii.gz").write_bytes(b"x")
        (self.tmp / "truth" / "ground-truth" / "Vertebrae").mkdir(parents=True)
        (self.tmp / "truth" / "ground-truth" / "Vertebrae" / "0001.nii.gz").write_bytes(b"x")
        (self.tmp / "truth" / "ground-truth" / "Body-Composition").mkdir(parents=True)
        (self.tmp / "truth" / "ground-truth" / "Body-Composition" / "0001.nii.gz").write_bytes(b"x")
        self.assertEqual(list(self.tool.volumes_under(self.tmp / "ct")), ["0001"])
        self.assertEqual(list(self.tool.truth_under(self.tmp / "truth")), [("Vertebrae", "0001")])
        self.assertEqual(self.tool.eligible_subjects([{"subject_id": "0001"}, {"subject_id": "0002"}],
                                                     self.tool.volumes_under(self.tmp / "ct"), self.tool.truth_under(self.tmp / "truth")), ["0001"])
        (self.tmp / "ct" / "again").mkdir()
        (self.tmp / "ct" / "again" / "0001.nii.gz").write_bytes(b"x")
        with self.assertRaises(self.tool.Refused):
            self.tool.volumes_under(self.tmp / "ct")

    def test_inputs_refuse_a_missing_klein_and_too_few_subjects_before_any_gpu_work(self):
        klein, bundle = self.tmp / "klein", self.tmp / "bundle"
        klein.mkdir()
        bundle.mkdir()
        (bundle / "ensemble.json").write_text("{}", encoding="utf-8")
        (self.tmp / "resnet.pth").write_bytes(b"w")
        (self.tmp / "db").mkdir()
        (self.tmp / "db" / "data.mdb").write_bytes(b"d")
        samples = self.tmp / "samples.csv"
        rows = [self.sample(f"0001_{p}", "0001", p, *self.realism.pose_of(p)) for p in range(4)]
        self.tool.write_rows(samples, rows, list(rows[0]))
        (self.tmp / "ct").mkdir()
        (self.tmp / "ct" / "0001.nii.gz").write_bytes(b"c")
        (self.tmp / "truth" / "Vertebrae").mkdir(parents=True)
        (self.tmp / "truth" / "Vertebrae" / "0001.nii.gz").write_bytes(b"t")
        original = self.tool.thunder_ids
        self.tool.thunder_ids = lambda root: {row["sample_id"]: {"subject_id": "0001", "split": "test"} for row in rows}
        self.addCleanup(setattr, self.tool, "thunder_ids", original)
        words = ["inputs", "--samples", str(samples), "--db", str(self.tmp / "db"), "--ct", str(self.tmp / "ct"),
                 "--truth", str(self.tmp / "truth"), "--klein", str(klein), "--bundle", str(bundle),
                 "--imagenet", str(self.tmp / "resnet.pth"), "--out", str(self.tmp / "inputs.json"), "--no-pins"]
        self.assertEqual(self.tool.main(words), 2)
        (klein / "model_index.json").write_text("{}", encoding="utf-8")
        self.assertEqual(self.tool.main(words), 2)
        self.assertFalse((self.tmp / "inputs.json").exists())
        plan = self.tool.PLAN
        self.addCleanup(setattr, self.tool, "PLAN", plan)
        original_plan = self.realism.REPLICATION
        self.realism.REPLICATION = self.realism.ReplicationPlan(subjects=1)
        self.addCleanup(setattr, self.realism, "REPLICATION", original_plan)
        self.assertEqual(self.tool.main(words), 0)
        record = json.loads((self.tmp / "inputs.json").read_text(encoding="utf-8"))
        self.assertEqual(record["eligible"], ["0001"])
        self.assertEqual(record["model"], "klein-9b")
        self.assertEqual(len(record["klein_sha256"]), 64)
        self.assertTrue(record["pins_differ"])
        self.assertEqual(self.tool.main(words[:-1]), 2)

    def test_eligibility_counts_the_plans_poses_on_the_grid_and_the_draw_refuses_a_short_sample(self):
        # 0001 has four grid poses; 0002 three and one off the grid; 0003 four but one off axis;
        # 0004 four and no CT. Only 0001 can give the plan's four poses and be rendered.
        rows = [self.sample(f"0001_{p}", "0001", p, *self.realism.pose_of(p)) for p in range(4)]
        rows += [self.sample(f"0002_{p}", "0002", p, *self.realism.pose_of(p)) for p in range(3)]
        rows += [self.sample("0002_9", "0002", 9, 700, -300, 0)]
        rows += [self.sample(f"0003_{p}", "0003", p, *self.realism.pose_of(p), **({"beta_deg": 2.0} if p == 0 else {}))
                 for p in range(4)]
        rows += [self.sample(f"0004_{p}", "0004", p, *self.realism.pose_of(p)) for p in range(4)]
        (self.tmp / "ct").mkdir()
        (self.tmp / "truth" / "Vertebrae").mkdir(parents=True)
        for subject in ("0001", "0002", "0003"):
            (self.tmp / "ct" / f"{subject}.nii.gz").write_bytes(b"c")
            (self.tmp / "truth" / "Vertebrae" / f"{subject}.nii.gz").write_bytes(b"t")
        volumes, truth = self.tool.volumes_under(self.tmp / "ct"), self.tool.truth_under(self.tmp / "truth")
        self.assertEqual(self.tool.subjects_with_poses(rows, 4), {"0001", "0004"})
        # a sample samples.csv names twice counts once, as the draw counts it
        twice = [self.sample(f"0005_{p}", "0005", p, *self.realism.pose_of(p)) for p in (0, 1, 2, 2)]
        self.assertEqual(self.tool.subjects_with_poses(twice, 4), set())
        self.assertEqual(self.tool.eligible_for_draw(rows, volumes, truth, 4), ["0001"])
        self.assertEqual(self.tool.eligible_for_draw(rows, volumes, truth, 3), ["0001", "0002", "0003"])
        # the split refuses a limit it cannot fill, from the same set inputs counts
        with self.assertRaises(self.tool.Refused):
            self.tool.split_subjects(["0001", "0002", "0003"], 4, 7)
        self.assertEqual(len(self.tool.split_subjects(["0001", "0002", "0003"], 3, 7)[0]), 3)
        poses = self.tmp / "poses.json"
        self.tool.write_json(poses, self.tool.poses_from_samples(rows))
        inputs = self.tmp / "inputs.json"
        self.tool.write_json(inputs, {"eligible": ["0001", "0002", "0003"]})
        words = ["split", "--poses", str(poses), "--eligible", str(inputs), "--out", str(self.tmp / "split"), "--seed", "7"]
        self.assertEqual(self.tool.main([*words, "--limit", "4"]), 2)
        self.assertFalse((self.tmp / "split" / "split.json").exists())
        self.assertEqual(self.tool.main([*words, "--limit", "3"]), 0)
        self.assertEqual(json.loads((self.tmp / "split" / "split.json").read_text(encoding="utf-8"))["from"], 3)
        # a drawn subject with fewer samples than the plan draws is refused, never drawn short
        found = json.loads(poses.read_text(encoding="utf-8"))
        self.assertEqual(len(self.tool.drawn_samples(found, ["0001"], 4, 7)["0001"]), 4)
        with self.assertRaises(self.tool.Refused):
            self.tool.drawn_samples(found, ["0001", "0002"], 4, 7)
        with self.assertRaises(self.tool.Refused):
            self.tool.drawn_samples(found, ["0009"], 4, 7)

    def test_inputs_refuse_where_too_few_subjects_have_the_plans_poses_on_the_grid(self):
        klein, bundle = self.tmp / "klein", self.tmp / "bundle"
        klein.mkdir()
        (klein / "model_index.json").write_text("{}", encoding="utf-8")
        bundle.mkdir()
        (bundle / "ensemble.json").write_text("{}", encoding="utf-8")
        (self.tmp / "resnet.pth").write_bytes(b"w")
        (self.tmp / "db").mkdir()
        (self.tmp / "db" / "data.mdb").write_bytes(b"d")
        # both subjects have a CT and truth, but 0002 has only three samples at the grid's poses
        rows = [self.sample(f"0001_{p}", "0001", p, *self.realism.pose_of(p)) for p in range(4)]
        rows += [self.sample(f"0002_{p}", "0002", p, *self.realism.pose_of(p)) for p in range(3)]
        rows += [self.sample("0002_3", "0002", 3, 650, -300, 0, x=4.0)]
        samples = self.tmp / "samples.csv"
        self.tool.write_rows(samples, rows, list(rows[0]))
        (self.tmp / "ct").mkdir()
        (self.tmp / "truth" / "Vertebrae").mkdir(parents=True)
        for subject in ("0001", "0002"):
            (self.tmp / "ct" / f"{subject}.nii.gz").write_bytes(b"c")
            (self.tmp / "truth" / "Vertebrae" / f"{subject}.nii.gz").write_bytes(b"t")
        original = self.tool.thunder_ids
        self.tool.thunder_ids = lambda root: {row["sample_id"]: {"subject_id": row["subject_id"], "split": "test"} for row in rows}
        self.addCleanup(setattr, self.tool, "thunder_ids", original)
        original_plan = self.realism.REPLICATION
        self.addCleanup(setattr, self.realism, "REPLICATION", original_plan)
        words = ["inputs", "--samples", str(samples), "--db", str(self.tmp / "db"), "--ct", str(self.tmp / "ct"),
                 "--truth", str(self.tmp / "truth"), "--klein", str(klein), "--bundle", str(bundle),
                 "--imagenet", str(self.tmp / "resnet.pth"), "--out", str(self.tmp / "inputs.json"), "--no-pins"]
        self.realism.REPLICATION = self.realism.ReplicationPlan(subjects=2)
        self.assertEqual(self.tool.main(words), 2)
        self.assertFalse((self.tmp / "inputs.json").exists())
        self.realism.REPLICATION = self.realism.ReplicationPlan(subjects=1)
        self.assertEqual(self.tool.main(words), 0)
        self.assertEqual(json.loads((self.tmp / "inputs.json").read_text(encoding="utf-8"))["eligible"], ["0001"])
        # a samples.csv with no pose columns cannot be checked against the grid, so it is refused
        bare = self.tmp / "bare.csv"
        self.tool.write_rows(bare, [{"sample_id": r["sample_id"], "subject_id": r["subject_id"]} for r in rows],
                             ["sample_id", "subject_id"])
        self.assertEqual(self.tool.main(["inputs", "--samples", str(bare), *words[3:]]), 2)

    def test_the_environment_record_names_the_pins_and_the_weights_by_sha256(self):
        bundle = self.tmp / "bundle"
        (bundle / "members" / "flux000").mkdir(parents=True)
        (bundle / "ensemble.json").write_text("{}", encoding="utf-8")
        (bundle / "members" / "flux000" / "model.safetensors").write_bytes(b"weights")
        imagenet = self.tmp / "resnet18-f37072fd.pth"
        imagenet.write_bytes(b"resnet")
        out = self.tmp / "stats" / "environment.json"
        original = self.tool.environment_record
        self.addCleanup(setattr, self.tool, "environment_record", original)
        self.tool.environment_record = lambda: ({"diffusers": "absent", "torch": "2.9.0", "gpu": "none"},
                                                ["diffusers absent, pinned 0.42.0"])
        words = ["environment", "--bundle", str(bundle), "--imagenet", str(imagenet), "--out", str(out)]
        self.assertEqual(self.tool.main(words), 2)
        self.assertFalse(out.exists())
        self.assertEqual(self.tool.main([*words, "--no-pins"]), 0)
        record = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(record["environment"]["torch"], "2.9.0")
        self.assertEqual(record["pins_differ"], ["diffusers absent, pinned 0.42.0"])
        self.assertEqual((record["bundle"], record["imagenet"]), (str(bundle), str(imagenet)))
        self.assertEqual(record["bundle_sha256"], self.tool.folder_digest(self.tool.folder_files(bundle)))
        self.assertEqual(record["imagenet_sha256"], self.tool.file_sha256(imagenet))
        self.tool.environment_record = lambda: ({"diffusers": "0.42.0", "gpu": "none"}, [])
        self.assertEqual(self.tool.main(words), 0)
        self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["pins_differ"], [])
        (bundle / "ensemble.json").unlink()
        self.assertEqual(self.tool.main(words), 2)
        (bundle / "ensemble.json").write_text("{}", encoding="utf-8")
        imagenet.unlink()
        self.assertEqual(self.tool.main(words), 2)

    def test_an_import_that_fails_is_said_by_what_is_missing_with_no_dot_or_quote(self):
        folder = self.tmp / "modules"
        folder.mkdir()
        (folder / "needs_absent.py").write_text("import absent_package_of_the_test\n", encoding="utf-8")
        (folder / "breaks.py").write_text("raise RuntimeError('a value')\n", encoding="utf-8")
        (folder / "holder").mkdir()
        (folder / "holder" / "__init__.py").write_text("thing = 1\n", encoding="utf-8")
        (folder / "holder" / "configs").mkdir()
        sys.path.insert(0, str(folder))
        self.addCleanup(sys.path.remove, str(folder))
        problem = self.tool.import_problem
        self.assertIsNone(problem("json"))
        self.assertIsNone(problem("json:loads"))
        self.assertIsNone(problem("holder:thing"))
        # a name that is a folder with no __init__.py, as FleXray's configs/datasets is
        self.assertIsNone(problem("holder:configs"))
        self.assertEqual(problem("needs_absent"), "needs_absent cannot be imported, missing absent_package_of_the_test")
        self.assertEqual(problem("absent_package_of_the_test.sub:thing"),
                         "absent_package_of_the_test sub thing cannot be imported, missing absent_package_of_the_test")
        self.assertEqual(problem("holder:Segmenter"), "holder Segmenter cannot be imported, the installed release has no Segmenter there")
        self.assertEqual(problem("breaks"), "breaks cannot be imported, RuntimeError")

    def fake_torch(self, available=True, gib=16.0, capability=(7, 0), name="Tesla V100-SXM2-16GB"):
        """A torch whose card is described by the arguments, put where import torch finds it."""
        properties = types.SimpleNamespace(total_memory=int(gib * 2**30))
        cuda = types.SimpleNamespace(is_available=lambda: available, get_device_properties=lambda index: properties,
                                     get_device_capability=lambda index: capability, get_device_name=lambda index: name)
        original = sys.modules.get("torch")
        sys.modules["torch"] = types.SimpleNamespace(cuda=cuda, __version__="0.0")
        self.addCleanup(lambda: sys.modules.__setitem__("torch", original) if original else sys.modules.pop("torch", None))

    def test_the_card_check_refuses_a_card_that_cannot_hold_klein_9b_in_bfloat16(self):
        self.fake_torch(gib=15.77)
        self.assertEqual(self.tool.card_problem(), "the card Tesla V100-SXM2-16GB holds 16 GiB and computes no bfloat16, "
                                                   "where klein-9B in bfloat16 needs 42 GiB or more and bfloat16")
        self.fake_torch(gib=44.4, capability=(8, 9), name="NVIDIA L40S")
        self.assertIsNone(self.tool.card_problem())
        self.fake_torch(gib=22.0, capability=(8, 6), name="NVIDIA A10")
        self.assertEqual(self.tool.card_problem(), "the card NVIDIA A10 holds 22 GiB, where klein-9B in bfloat16 needs 42 GiB or more and bfloat16")
        self.fake_torch(available=False)
        self.assertEqual(self.tool.card_problem(), "no CUDA card is visible")

    def test_the_edit_refuses_a_missing_extra_or_a_small_card_and_the_stats_checks_no_card(self):
        original_record, original_card = self.tool.environment_record, self.tool.card_problem
        self.addCleanup(setattr, self.tool, "environment_record", original_record)
        self.addCleanup(setattr, self.tool, "card_problem", original_card)
        self.tool.environment_record = lambda: ({"thunderpack": "absent"}, ["thunderpack absent, pinned 0.0.2"])
        self.tool.card_problem = lambda: "no CUDA card is visible"
        with self.assertRaises(self.tool.Refused) as refused:
            self.tool.pinned_environment(False, card=True)
        self.assertEqual(str(refused.exception), "the environment differs from the pins: thunderpack absent, pinned 0.0.2; "
                                                 "no CUDA card is visible")
        environment, wrong = self.tool.pinned_environment(True, card=True)
        self.assertEqual((environment["card_ok"], len(wrong)), (False, 2))
        self.tool.environment_record = lambda: ({"thunderpack": "0.0.2"}, [])
        environment, wrong = self.tool.pinned_environment(False)
        self.assertNotIn("card_ok", environment)
        self.assertEqual(wrong, [])
        self.tool.card_problem = lambda: None
        self.assertTrue(self.tool.pinned_environment(False, card=True)[0]["card_ok"])

    def test_the_environment_record_holds_the_extra_pins_and_every_flexray_import(self):
        found, wrong = self.tool.environment_record()
        for pin in (*self.realism.PINS, *self.realism.EXTRA_PINS):
            self.assertIn(pin.partition("==")[0], found)
        self.assertTrue(set(self.realism.EXTRA_PINS).isdisjoint(self.realism.PINS))
        self.assertTrue(any(line.startswith("numpy==") for line in found["installed"]), found["installed"][:5])
        # outside the realism environment FleXray is absent, and each import it lacks is named
        if importlib.util.find_spec("fxr") is None:
            self.assertIn("fxr inference FleXraySegmenter cannot be imported, missing fxr", wrong)

    def test_a_name_is_said_by_its_shape_and_a_set_of_names_by_its_commonest_shapes(self):
        self.assertEqual(self.tool.id_shape("enhance_0001"), "a7_d4")
        self.assertEqual(self.tool.id_shape("0001"), "d4")
        self.assertEqual(self.tool.id_shape("PSMA-2.a"), "a4-d1?a1")
        self.assertEqual(self.tool.id_shape(""), "empty")
        self.assertEqual(self.tool.shapes_of(["0001", "0002", "s_1"]), "d4 (2), a1_d1 (1)")
        self.assertEqual(self.tool.shapes_of([]), "none")

    def test_a_refusal_for_too_few_subjects_counts_where_they_were_lost(self):
        rows = [self.sample(f"0001_{p}", "0001", p, *self.realism.pose_of(p)) for p in range(4)]
        rows += [self.sample(f"0002_{p}", "0002", p, *self.realism.pose_of(p)) for p in range(4)]
        rows += [self.sample("0003_0", "0003", 0, *self.realism.pose_of(0))]
        in_db = rows[:8]
        volumes = {"PSMA_0001": Path("a"), "0002": Path("b")}
        truth = {("Vertebrae", "0002"), ("Ribs", "0001")}
        said = self.tool.eligibility_counts(rows, in_db, volumes, truth, 4)
        self.assertEqual(said, "of 3 subjects in the samples table 2 have samples in the ThunderDB, 2 have 4 at poses on the grid, "
                               "1 of those a CT and 1 a CT and a vertebra truth; the subjects are shaped d4 (3), the CT names "
                               "a4_d4 (1), d4 (1) and the vertebra truth names d4 (1)")

    def test_every_refusal_of_the_input_check_passes_the_status_shape_check(self):
        rows = [self.sample(f"0001_{p}", "0001", p, *self.realism.pose_of(p)) for p in range(4)]
        reasons = [
            "the environment differs from the pins: thunderpack absent, pinned 0.0.2; fxr datasets _thunderdb open_thunderdb "
            "cannot be imported, missing thunderpack; the card Tesla V100-SXM2-16GB holds 16 GiB and computes no bfloat16, "
            "where klein-9B in bfloat16 needs 42 GiB or more and bfloat16",
            self.tool.eligibility_counts(rows, rows, {"0001": Path("a")}, set(), 4),
            "no model index in the klein folder: klein-9b of the recipe has not landed, and no other klein stands in",
            f"no sample of the samples table is in the ThunderDB (the table names samples shaped {self.tool.shapes_of(['0001_0'])}, "
            f"the ThunderDB {self.tool.shapes_of(['enhance-0001-a'])}), so the FluXray image of a drawn sample could not be read",
        ]
        grid = ROOT / "grid"
        lines = "".join(f"- FAILED: RealismFault: the realism tool step inputs exited 2: refused: {reason}\n" for reason in reasons)
        shaped = subprocess.run(["awk", "-v", "data=/data", "-v", "runs=/runs", "-v", "models=/models", "-v", "repo=/repo",
                                 "-f", str(grid / "shape-words.awk"), "-f", str(grid / "report-shapes.awk")],
                                input=lines, capture_output=True, text=True, timeout=60, check=True).stdout
        self.assertNotIn("withheld", shaped)
        self.assertEqual(shaped, lines)

    def test_a_refusal_prints_its_detail_before_its_words(self):
        bundle = self.tmp / "bundle"
        bundle.mkdir()
        original = self.tool.environment_record
        self.addCleanup(setattr, self.tool, "environment_record", original)
        self.tool.environment_record = lambda: ({}, [])
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = self.tool.main(["environment", "--bundle", str(bundle), "--imagenet", str(self.tmp / "absent.pth"),
                                   "--out", str(self.tmp / "environment.json")])
        self.assertEqual(code, 2)
        self.assertEqual(err.getvalue().splitlines(), [f"detail: no {bundle / 'ensemble.json'}",
                                                      "refused: no ensemble record in the FleXray bundle"])

    # --- the paired permutation ---------------------------------------------------------------------

    def paired_sets(self, seed, shift, subjects=16, poses=4, dims=6, pose_spread=3.0):
        """Set a two edits of each sample, set b one image of it, every sample a subject's view with
        its own anatomy (a pose far from the subject's other poses) and noise on each image."""
        import numpy as np

        rng = np.random.default_rng(seed)
        anatomy = (rng.normal(size=(subjects, 1, dims)) + pose_spread * rng.normal(size=(subjects, poses, dims))).reshape(-1, dims)
        names = np.array([f"s{s}_{p}" for s in range(subjects) for p in range(poses)])
        groups = np.array([f"s{s}" for s in range(subjects) for _ in range(poses)])
        a = np.concatenate([anatomy + rng.normal(size=anatomy.shape) + shift for _ in range(2)])
        b = anatomy + rng.normal(size=anatomy.shape)
        return a, b, np.concatenate([groups, groups]), groups, np.concatenate([names, names]), names

    def test_paired_sets_shuffle_labels_only_among_each_samples_images(self):
        import numpy as np

        # samples p and q in both sets, r in set a only, t in set b only
        labels = np.array([0, 0, 0, 0, 1, 1, 1])
        samples = np.array(["p", "p", "q", "r", "p", "q", "t"])
        subjects = np.array(["m", "m", "m", "m", "m", "m", "m"])
        layers, by = self.tool.permutation_strata(labels, subjects, samples)
        self.assertEqual(by, "sample")
        rng = np.random.default_rng(0)
        seen = set()
        for _ in range(40):
            permuted = self.tool.permuted_labels(labels, layers, rng)
            self.assertEqual(int(permuted[[0, 1, 4]].sum()), 1)
            self.assertEqual(int(permuted[[2, 5]].sum()), 1)
            self.assertEqual((permuted[3], permuted[6]), (0, 1))
            seen.add(tuple(permuted))
        self.assertGreater(len(seen), 1)
        # sets that share no sample, as FluXray's split halves, move whole subjects as before
        disjoint = np.array(["p", "p", "q", "r", "u", "v", "t"])
        self.assertEqual(self.tool.permutation_strata(labels, subjects, disjoint)[1], "subject")
        self.assertEqual(self.tool.permutation_strata(labels, subjects)[1], "subject")
        self.assertIsNone(self.tool.pooled_names(["p"], None))

    def test_a_small_paired_shift_is_detected_and_a_paired_null_is_not_piled_at_one(self):
        import numpy as np

        # a shuffle across a subject's poses adds anatomy to the null and to no observed statistic:
        # by subject, a true null reads p = 1 and a small shift reads nothing; by sample it is a null
        nulls, by_subject = [], []
        for seed in range(8):
            a, b, ga, gb, na, nb = self.paired_sets(seed, 0.0)
            paired = self.tool.mmd_test(a, b, ga, gb, 0, permutations=60, samples_a=na, samples_b=nb)
            self.assertEqual(paired["strata"], "sample")
            nulls.append(paired["p"])
            by_subject.append(self.tool.mmd_test(a, b, ga, gb, 0, permutations=60)["p"])
        self.assertGreater(min(by_subject), 0.95)
        self.assertLess(float(np.median(nulls)), 0.9)
        self.assertGreater(float(np.median(nulls)), 0.1)
        self.assertLessEqual(sum(p >= 0.95 for p in nulls), 2)
        a, b, ga, gb, na, nb = self.paired_sets(3, 0.5)
        self.assertLessEqual(self.tool.mmd_test(a, b, ga, gb, 0, permutations=60, samples_a=na, samples_b=nb)["p"], 0.05)
        self.assertGreater(self.tool.mmd_test(a, b, ga, gb, 0, permutations=60)["p"], 0.2)
        # the classifier's p uses the same strata, and its paired null is not piled at 1 either
        c_nulls = []
        for seed in range(8):
            a, b, ga, gb, na, nb = self.paired_sets(seed, 0.0)
            result = self.tool.c2st(a, b, ga, gb, 0, bootstraps=10, permutations=60, samples_a=na, samples_b=nb)
            self.assertEqual(result["strata"], "sample")
            c_nulls.append(result["p"])
        self.assertLess(float(np.median(c_nulls)), 0.9)
        self.assertLessEqual(sum(p >= 0.95 for p in c_nulls), 2)

    def test_compare_records_the_components_and_strata_it_read(self):
        a, b, ga, gb = self.two_sets(0.5, dims=6)
        entry = self.tool.compare(a, b, ga, gb, 0)
        self.assertEqual(entry["components"], 6)
        self.assertEqual(entry["c2st"]["strata"], "subject")
        self.assertIn("frechet64", entry)
        self.assertIn("kid64", entry)
        null = self.tool.split_half(b, gb, 0)
        self.assertEqual((null["components"], null["mmd"]["strata"]), (6, "subject"))
        a, b, ga, gb, na, nb = self.paired_sets(0, 0.0, dims=70)
        wide = self.tool.compare(a, b, ga, gb, 0, na, nb)
        self.assertEqual(wide["components"], self.tool.PCA_COMPONENTS)
        self.assertEqual((wide["c2st"]["strata"], wide["mmd"]["strata"]), ("sample", "sample"))

    # --- resuming a cut run ---------------------------------------------------------------------

    def test_a_whole_write_leaves_no_half_file_and_a_torn_log_line_is_passed_over(self):
        import numpy as np

        path = self.tmp / "raw" / "s1.npy"
        self.tool.save_npy(path, np.ones((4, 4), dtype=np.float16))
        self.assertEqual(sorted(p.name for p in path.parent.iterdir()), ["s1.npy"])
        self.assertEqual(float(np.load(path).sum()), 16.0)
        log = self.tmp / "manifest.jsonl"
        log.write_text(json.dumps({"sample_id": "s0"}) + "\n" + '{"sample_id": "s1", "subj', encoding="utf-8")
        self.assertEqual([r["sample_id"] for r in self.tool.json_lines(log)], ["s0"])
        with self.tool.open_log(log) as handle:
            handle.write(json.dumps({"sample_id": "s1"}) + "\n")
        self.assertEqual([r["sample_id"] for r in self.tool.json_lines(log)], ["s0", "s1"])
        self.assertEqual(sorted(self.tool.manifest_rows(self.tmp)), ["s0", "s1"])

    def render_folder(self, done=(), orphans=(), truncated=(), parts=()):
        """A render folder as a cut leaves it: whole samples with their row, raw files with no row,
        a mask cut off midway, a temporary file left behind."""
        import numpy as np

        out = self.tmp / "render"
        (out / "raw").mkdir(parents=True, exist_ok=True)
        (out / "masks").mkdir(exist_ok=True)
        with open(out / "manifest.jsonl", "a", encoding="utf-8") as manifest:
            for name in done:
                np.save(out / "raw" / f"{name}.npy", np.full((8, 8), 0.5, dtype=np.float16))
                np.save(out / "masks" / f"{name}.npy", np.packbits(np.ones((2, 8, 8), dtype=bool), axis=-1))
                manifest.write(json.dumps({"sample_id": name, "subject_id": name.split("_")[0], "grid_pose": 0}) + "\n")
        for name in orphans:
            np.save(out / "raw" / f"{name}.npy", np.full((8, 8), 0.5, dtype=np.float16))
        for name in truncated:
            (out / "raw" / f"{name}.npy").write_bytes(b"\x93NUMPY\x01\x00v\x00{'descr': '<f2'")
            (out / "masks" / f"{name}.npy").write_bytes(b"\x93NUM")
        for name in parts:
            (out / "masks" / f"{name}.npy.part").write_bytes(b"half")
        return out

    def test_a_render_cut_short_is_redone_and_never_skipped(self):
        import numpy as np

        out = self.render_folder(done=["0001_0"], orphans=["0001_1"], truncated=["0001_2"], parts=["0001_3"])
        samples = [{"sample_id": f"0001_{p}", "subject_id": "0001", "grid_pose": p} for p in range(4)]
        done = self.tool.manifest_rows(out)
        self.assertTrue(self.tool.rendered(out, done, "0001_0"))
        self.assertFalse(self.tool.rendered(out, done, "0001_1"))
        todo = self.tool.renders_to_do(out, done, samples)
        self.assertEqual([s["sample_id"] for s in todo], ["0001_1", "0001_2", "0001_3"])
        # only the cut samples' own files went; the whole sample is untouched
        self.assertEqual(sorted(p.name for p in (out / "raw").iterdir()), ["0001_0.npy"])
        self.assertEqual(sorted(p.name for p in (out / "masks").iterdir()), ["0001_0.npy"])
        # a cut between the masks and the raw image leaves no row, so the sample is done again
        original = self.tool.save_npy
        self.addCleanup(setattr, self.tool, "save_npy", original)

        def cut_at_raw(path, array):
            if Path(path).parent.name == "raw" and Path(path).stem == "0001_2":
                raise KeyboardInterrupt("the job's time is up")
            original(path, array)

        self.tool.save_npy = cut_at_raw
        masks = np.packbits(np.ones((2, 8, 8), dtype=bool), axis=-1)
        image = np.full((8, 8), 0.25, dtype=np.float16)
        with self.assertRaises(KeyboardInterrupt):
            with self.tool.open_log(out / "manifest.jsonl") as manifest:
                for sample in todo:
                    self.tool.write_render(out, manifest, dict(sample), image, masks)
        self.tool.save_npy = original
        done = self.tool.manifest_rows(out)
        self.assertEqual(sorted(done), ["0001_0", "0001_1"])
        again = self.tool.renders_to_do(out, done, samples)
        self.assertEqual([s["sample_id"] for s in again], ["0001_2", "0001_3"])
        self.assertFalse((out / "masks" / "0001_2.npy").exists())
        with self.tool.open_log(out / "manifest.jsonl") as manifest:
            for sample in again:
                self.tool.write_render(out, manifest, dict(sample), image, masks)
        done = self.tool.manifest_rows(out)
        self.assertTrue(all(self.tool.rendered(out, done, s["sample_id"]) for s in samples))
        self.assertEqual(self.tool.renders_to_do(out, done, samples), [])
        for folder in ("raw", "masks"):
            for path in (out / folder).iterdir():
                self.assertEqual(path.suffix, ".npy")
                np.load(path)

    @unittest.skipIf(importlib.util.find_spec("torch") is None or importlib.util.find_spec("PIL") is None,
                     "the edit's stand-in pipeline needs torch and Pillow")
    def test_an_edit_cut_short_is_redone_and_never_skipped(self):
        import sys
        import types

        import numpy as np

        render = self.render_folder(done=["0001_0", "0001_1"])
        out = self.tmp / "edit"
        (out / "edited").mkdir(parents=True)
        whole = self.tool.edit_name("0001_0", 0)
        np.save(out / "edited" / f"{whole}.npy", np.zeros((8, 8), dtype=np.float16))
        # one edit whole with its row; one cut off midway; one whole with no row; one temporary file
        (out / "edited" / f"{self.tool.edit_name('0001_0', 1)}.npy").write_bytes(b"\x93NUMPY\x01")
        np.save(out / "edited" / f"{self.tool.edit_name('0001_1', 0)}.npy", np.zeros((8, 8), dtype=np.float16))
        (out / "edited" / f"{self.tool.edit_name('0001_1', 1)}.npy.part").write_bytes(b"half")
        (out / "edits.jsonl").write_text(json.dumps({"sample_id": "0001_0", "arm": 0}) + "\n" + '{"sample_id": "0001_0", "ar',
                                         encoding="utf-8")
        calls = []

        class Pipe:
            def to(self, device):
                return self

            def __call__(self, image, **settings):
                calls.append(settings["generator"].initial_seed())
                return types.SimpleNamespace(images=[image])

        # the stand-in goes into sys.modules alone: a snapshot of sys.modules put back afterwards
        # would drop torch had it first been imported here, and a second import of torch crashes
        fake = types.ModuleType("diffusers")
        fake.Flux2KleinPipeline = types.SimpleNamespace(from_pretrained=lambda *args, **kwargs: Pipe())
        previous = sys.modules.get("diffusers")
        sys.modules["diffusers"] = fake
        self.addCleanup(lambda: sys.modules.pop("diffusers") if previous is None else sys.modules.update(diffusers=previous))
        words = ["edit", "--raw", str(render), "--weights", str(self.tmp / "klein"), "--out", str(out), "--arms", "2",
                 "--device", "cpu"]
        self.assertEqual(self.tool.main(words), 0)
        self.assertEqual(len(calls), 3)
        done = self.tool.edit_rows(out)
        self.assertEqual(done, {(s, arm) for s in ("0001_0", "0001_1") for arm in (0, 1)})
        for path in (out / "edited").iterdir():
            self.assertEqual(path.suffix, ".npy")
            self.assertEqual(np.load(path).shape, (8, 8))
        self.assertEqual(self.tool.main(words), 0)
        self.assertEqual(len(calls), 3)

    def test_the_kept_folder_holds_exactly_this_filters_kept_edits(self):
        import numpy as np

        edited = self.tmp / "edited"
        edited.mkdir()
        for name in ("a__a0", "b__a0", "c__a0"):
            np.save(edited / f"{name}.npy", np.zeros((2, 2), dtype=np.float16))
        kept = self.tmp / "filter" / "kept"
        self.tool.link_kept(kept, {"a__a0": edited / "a__a0.npy", "b__a0": edited / "b__a0.npy"})
        self.tool.link_kept(kept, {"b__a0": edited / "b__a0.npy", "c__a0": edited / "c__a0.npy"})
        self.assertEqual(sorted(path.name for path in kept.iterdir()), ["b__a0.npy", "c__a0.npy"])
        self.assertTrue(all(path.is_symlink() for path in kept.iterdir()))
        self.assertEqual(sorted(path.name for path in edited.iterdir()), ["a__a0.npy", "b__a0.npy", "c__a0.npy"])

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


class FlexrayImportsTest(unittest.TestCase):
    """Read as files, so it runs under any python: every name tools/realism.py imports from FleXray,
    diffusers or the extra pins is one realism.FLEXRAY_IMPORTS tries at the start of a run, so a
    release that lacks one refuses the run before any GPU work, as the first edit's did not."""

    def test_every_import_the_stages_take_from_flexray_is_checked_at_the_start(self):
        tree = ast.parse((ROOT / "src" / "schwingnet" / "realism.py").read_text(encoding="utf-8"))
        checked = next(ast.literal_eval(node.value) for node in ast.walk(tree) if isinstance(node, ast.Assign)
                       and any(getattr(target, "id", "") == "FLEXRAY_IMPORTS" for target in node.targets))
        roots = {"fxr", "diffusers", "thunderpack", "nanodrr", "kornia"}
        taken = set()
        for node in ast.walk(ast.parse((ROOT / "tools" / "realism.py").read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in roots:
                taken |= {f"{node.module}:{alias.name}" for alias in node.names}
            elif isinstance(node, ast.Import):
                taken |= {alias.name for alias in node.names if alias.name.split(".")[0] in roots}
        self.assertTrue(taken)
        self.assertEqual(sorted(taken - set(checked)), [])
