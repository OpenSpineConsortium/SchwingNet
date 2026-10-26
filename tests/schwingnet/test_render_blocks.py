"""The renderer's building blocks: the defaults are FleXray's recipe, a fault refused in words, the
crop plan and the crop weights FleXray's own arithmetic (tests/test_flexray_render.py holds them
equal to fxr's functions where fxr is installed; here the examples its docs and source give).

These cases import neither torch nor fxr, so they run in the gate's environment and with
unittest alone:

    PYTHONPATH=src:vendor/beethoven-qa/src python -m unittest tests.schwingnet.test_render_blocks
"""

import unittest
from dataclasses import replace

from schwingnet.render_blocks import (
    CHOICES,
    COUNTS,
    CROP_DEPTH,
    DEFAULT,
    ENGINES,
    FIELDS,
    PHYSICAL,
    RUNTIME_CHOICES,
    RenderBlockError,
    RenderBlocks,
    as_record,
    crop_weights,
    engine_problems,
    from_record,
    parse,
    parts,
    plan_crops,
    problems,
    slug,
)


class Parsing(unittest.TestCase):
    def test_no_words_are_flexrays_recipe(self):
        self.assertEqual(parse([]), DEFAULT)
        self.assertEqual(DEFAULT, RenderBlocks())
        self.assertEqual(problems(DEFAULT), [])
        self.assertEqual(PHYSICAL.attenuation, "off")
        self.assertEqual(replace(PHYSICAL, attenuation="flexray-lognormal"), DEFAULT)

    def test_words_choose_each_part_and_round_trip_through_the_record(self):
        blocks = parse(
            ["attenuation=off", "crop=whole", "crop-sampler=uniform", "views=2", "detector=128"]
        )
        self.assertEqual((blocks.attenuation, blocks.crop, blocks.views), ("off", "whole", 2))
        self.assertEqual(from_record(as_record(blocks)), blocks)
        self.assertEqual(from_record(as_record(DEFAULT)), DEFAULT)

    def test_a_word_naming_no_block_is_refused_in_words(self):
        with self.assertRaisesRegex(RenderBlockError, "KEY=VALUE"):
            parse(["lighting=soft"])
        with self.assertRaisesRegex(RenderBlockError, "KEY=VALUE"):
            parse(["attenuation"])

    def test_a_choice_that_does_not_exist_is_refused_with_the_choices(self):
        with self.assertRaisesRegex(RenderBlockError, "flexray-lognormal, off"):
            parse(["attenuation=strong"])
        with self.assertRaisesRegex(RenderBlockError, "is not one of flexray-moose"):
            parse(["pose=flexray-default"])

    def test_a_block_named_twice_is_refused(self):
        with self.assertRaisesRegex(RenderBlockError, "named twice"):
            parse(["views=2", "views=3"])

    def test_counts_are_held_to_their_ranges(self):
        with self.assertRaisesRegex(RenderBlockError, "views is a whole number from 1 to 100"):
            parse(["views=0"])
        with self.assertRaisesRegex(RenderBlockError, "not a whole number"):
            parse(["detector=-5"])
        with self.assertRaisesRegex(RenderBlockError, "not a whole number"):
            parse(["ray_samples=12345"])

    def test_the_label_weighted_sampler_needs_flexrays_crops(self):
        with self.assertRaisesRegex(RenderBlockError, "goes with crop=flexray-axial"):
            parse(["crop=whole"])
        self.assertEqual(problems(replace(DEFAULT, crop="whole", crop_sampler="uniform")), [])

    def test_problems_name_every_fault_at_once(self):
        broken = replace(DEFAULT, pose="orbit", views=0, crop="whole")
        found = problems(broken)
        self.assertEqual(len(found), 3)
        self.assertTrue(any("pose='orbit'" in line for line in found))
        self.assertTrue(any("views is a whole number" in line for line in found))
        self.assertTrue(any("goes with crop=flexray-axial" in line for line in found))


class Engines(unittest.TestCase):
    def test_the_two_engines_run_flexrays_recipe_and_the_physical_render(self):
        self.assertEqual(ENGINES, ("blocks", "flexray-runtime"))
        for engine in ENGINES:
            self.assertEqual(engine_problems(engine, DEFAULT), [])
            self.assertEqual(engine_problems(engine, PHYSICAL), [])

    def test_the_blocks_engine_runs_every_configuration_that_holds(self):
        words = ["crop=whole", "crop-sampler=uniform", "isocentre=vertebra", "projection=cone"]
        blocks = parse(words)
        self.assertEqual(engine_problems("blocks", blocks), [])
        broken = replace(DEFAULT, scale="log")
        self.assertEqual(engine_problems("blocks", broken), problems(broken))

    def test_flexrays_runtime_refuses_a_choice_its_code_does_not_make(self):
        blocks = parse(["crop=whole", "crop-sampler=uniform", "isocentre=vertebra"])
        found = engine_problems("flexray-runtime", blocks)
        self.assertEqual(len(found), 3)
        for line in found:
            self.assertIn("FleXray's runtime cannot honour", line)
        self.assertTrue(any("crop='whole'" in line and "flexray-axial" in line for line in found))
        self.assertTrue(any("isocentre='vertebra'" in line for line in found))

    def test_runtime_choices_are_a_subset_of_the_choices(self):
        self.assertEqual(set(RUNTIME_CHOICES), set(CHOICES))
        for name, allowed in RUNTIME_CHOICES.items():
            self.assertTrue(set(allowed) <= set(CHOICES[name]), name)
            self.assertIn(getattr(DEFAULT, name), allowed)

    def test_an_engine_that_does_not_exist_is_named(self):
        found = engine_problems("flux", DEFAULT)
        self.assertEqual(found, ["engine 'flux' is not one of blocks, flexray-runtime"])
        # The choices' own faults come first, then the engine's.
        found = engine_problems("flux", replace(DEFAULT, edit="flux"))
        self.assertEqual(len(found), 2)
        self.assertIn("edit='flux'", found[0])


class Records(unittest.TestCase):
    def test_the_slug_names_the_configuration_alone(self):
        self.assertEqual(slug(DEFAULT), slug(RenderBlocks()))
        self.assertNotEqual(slug(DEFAULT), slug(PHYSICAL))
        self.assertEqual(len(slug(DEFAULT)), 12)

    def test_the_record_holds_every_field(self):
        record = as_record(DEFAULT)
        self.assertEqual(tuple(record), FIELDS)
        self.assertEqual(record["views"], 4)
        self.assertEqual(record["pose"], "flexray-moose")

    def test_a_record_naming_a_choice_that_does_not_exist_is_refused(self):
        with self.assertRaises(RenderBlockError):
            from_record({**as_record(DEFAULT), "pose": "flexray-default"})

    def test_parts_list_every_part_with_its_choices_and_flexrays_default(self):
        rows = parts()
        self.assertEqual([row["part"] for row in rows], list(FIELDS))
        by_part = {row["part"]: row for row in rows}
        for name, allowed in CHOICES.items():
            self.assertEqual(by_part[name]["choices"], ", ".join(allowed))
            self.assertEqual(by_part[name]["default"], getattr(DEFAULT, name))
        for name, (low, high) in COUNTS.items():
            self.assertEqual(by_part[name]["choices"], f"a whole number from {low} to {high}")


class CropPlan(unittest.TestCase):
    def test_a_short_volume_is_one_crop_padded_on_both_sides(self):
        self.assertEqual(plan_crops(100), ((0, 100, 78, 78),))
        self.assertEqual(plan_crops(101), ((0, 101, 77, 78),))
        self.assertEqual(plan_crops(1), ((0, 1, 127, 128),))

    def test_an_exact_volume_is_one_crop_with_no_pad(self):
        self.assertEqual(plan_crops(CROP_DEPTH), ((0, CROP_DEPTH, 0, 0),))

    def test_a_volume_under_two_crops_is_two_crops_touching_both_ends(self):
        self.assertEqual(plan_crops(257), ((0, 256, 0, 0), (1, 257, 0, 0)))
        self.assertEqual(plan_crops(300), ((0, 256, 0, 0), (44, 300, 0, 0)))
        self.assertEqual(plan_crops(511), ((0, 256, 0, 0), (255, 511, 0, 0)))

    def test_flexrays_700_slice_example_starts_at_0_222_and_444(self):
        self.assertEqual([start for start, _, _, _ in plan_crops(700)], [0, 222, 444])

    def test_a_long_volume_is_the_fewest_crops_touching_both_ends(self):
        for depth in (512, 513, 1000, 1500, 4096):
            plan = plan_crops(depth)
            starts = [start for start, _, _, _ in plan]
            self.assertEqual(starts[0], 0)
            self.assertEqual(starts[-1], depth - CROP_DEPTH)
            self.assertEqual(len(plan), 2 + (depth - CROP_DEPTH - 1) // CROP_DEPTH)
            for earlier, later in zip(starts, starts[1:], strict=False):
                self.assertLessEqual(later - earlier, CROP_DEPTH)
                self.assertGreater(later, earlier)
            for _, _, before, after in plan:
                self.assertEqual((before, after), (0, 0))


class CropWeights(unittest.TestCase):
    def test_crop_weights_favour_crops_holding_rare_classes(self):
        weights = crop_weights([frozenset({1}), frozenset({1}), frozenset({1, 2}), frozenset()])
        self.assertEqual(weights[3], 0.0)
        self.assertGreater(weights[2], weights[0])
        self.assertEqual(weights[0], weights[1])
        self.assertAlmostEqual(sum(weights) / len(weights), 1.0)

    def test_crop_weights_are_flexrays_arithmetic(self):
        # Four crops; class 1 in all, class 2 in one, class 3 in two: (N / n_c) ** 0.5, the crop
        # taking the largest, then scaled to average 1.
        classes = [frozenset({1}), frozenset({1, 3}), frozenset({1, 2, 3}), frozenset({1})]
        raw = [1.0, 2 ** 0.5, 4 ** 0.5, 1.0]
        mean = sum(raw) / 4
        for found, expected in zip(crop_weights(classes), raw, strict=True):
            self.assertAlmostEqual(found, expected / mean)

    def test_crop_weights_of_one_class_everywhere_are_equal(self):
        for found in crop_weights([frozenset({5})] * 3):
            self.assertAlmostEqual(found, 1.0)


if __name__ == "__main__":
    unittest.main()
