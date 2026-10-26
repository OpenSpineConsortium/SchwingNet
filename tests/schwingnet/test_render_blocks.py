"""The renderer's building blocks: the defaults are FleXray's recipe with the project's segmenter,
the four presets, the segmenter part, a fault refused in words, the crop plan at both overlaps and
the crop weights FleXray's own arithmetic (tests/test_flexray_render.py holds them equal to fxr's
functions where fxr is installed; here the examples its docs and source give), and FluXray's
90-pose grid.

These cases import neither torch nor fxr, so they run in the gate's environment and with
unittest alone:

    PYTHONPATH=src:vendor/beethoven-qa/src python -m unittest tests.schwingnet.test_render_blocks
"""

import unittest
from dataclasses import replace

from icontract import ViolationError

from schwingnet import segmenters
from schwingnet.render_blocks import (
    AXIAL_CROPS,
    CHOICES,
    COUNTS,
    CROP_DEPTH,
    CROP_OVERLAP,
    DEFAULT,
    ENGINES,
    FIELDS,
    FLEXRAY,
    FLUXRAY_RAW,
    GRID_ALPHA_DEG,
    GRID_CHOICES,
    GRID_PIXEL_MM,
    GRID_POSES,
    GRID_SDD_MM,
    GRID_Y_MM,
    GRID_Z_MM,
    PHYSICAL,
    PRESETS,
    RUNTIME_CHOICES,
    RenderBlockError,
    RenderBlocks,
    as_record,
    crop_weights,
    engine_problems,
    from_record,
    grid_pose,
    parse,
    parts,
    plan_crops,
    problems,
    runtime_choices,
    slug,
    words_of,
)


class Parsing(unittest.TestCase):
    def test_no_words_are_flexrays_recipe_with_the_projects_segmenter(self):
        self.assertEqual(parse([]), DEFAULT)
        self.assertEqual(DEFAULT, RenderBlocks())
        self.assertEqual(problems(DEFAULT), [])
        self.assertEqual(DEFAULT.segmenter, "spineps")
        self.assertEqual(DEFAULT.segmenter, segmenters.DEFAULT_SEGMENTER)

    def test_words_choose_each_part_and_round_trip_through_the_record(self):
        blocks = parse(
            ["attenuation=off", "crop=whole", "crop-sampler=uniform", "views=2", "detector=128"]
        )
        self.assertEqual((blocks.attenuation, blocks.crop, blocks.views), ("off", "whole", 2))
        self.assertEqual(from_record(as_record(blocks)), blocks)
        self.assertEqual(from_record(as_record(DEFAULT)), DEFAULT)
        self.assertEqual(parse(["segmenter=moose"]), FLEXRAY)

    def test_a_word_naming_no_block_is_refused_in_words(self):
        with self.assertRaisesRegex(RenderBlockError, "KEY=VALUE"):
            parse(["lighting=soft"])
        with self.assertRaisesRegex(RenderBlockError, "KEY=VALUE"):
            parse(["attenuation"])

    def test_a_choice_that_does_not_exist_is_refused_with_the_choices(self):
        with self.assertRaisesRegex(RenderBlockError, "flexray-lognormal, off"):
            parse(["attenuation=strong"])
        with self.assertRaisesRegex(RenderBlockError, "is not one of flexray-moose, fluxray-grid"):
            parse(["pose=flexray-default"])
        with self.assertRaisesRegex(RenderBlockError, "is not one of spineps, moose"):
            parse(["segmenter=totalsegmentator"])

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

    def test_the_label_weighted_sampler_needs_an_axial_crop_choice(self):
        with self.assertRaisesRegex(RenderBlockError, "goes with crop=flexray-axial"):
            parse(["crop=whole"])
        self.assertEqual(problems(replace(DEFAULT, crop="whole", crop_sampler="uniform")), [])
        self.assertEqual(problems(replace(DEFAULT, crop="flexray-axial-min")), [])

    def test_problems_name_every_fault_at_once(self):
        broken = replace(DEFAULT, pose="orbit", views=0, crop="whole")
        found = problems(broken)
        self.assertEqual(len(found), 3)
        self.assertTrue(any("pose='orbit'" in line for line in found))
        self.assertTrue(any("views is a whole number" in line for line in found))
        self.assertTrue(any("goes with crop=flexray-axial" in line for line in found))


class Segmenter(unittest.TestCase):
    def test_the_segmenter_is_a_part_after_edit_with_the_segmenters_choices(self):
        self.assertEqual(CHOICES["segmenter"], segmenters.SEGMENTERS)
        self.assertEqual(FIELDS.index("segmenter"), FIELDS.index("edit") + 1)
        self.assertEqual(FIELDS.index("segmenter"), FIELDS.index("views") - 1)
        self.assertEqual(set(CHOICES) | set(COUNTS), set(FIELDS))

    def test_the_replication_renders_with_moose_and_production_with_spineps(self):
        self.assertEqual(FLEXRAY, replace(DEFAULT, segmenter="moose"))
        self.assertEqual(FLUXRAY_RAW.segmenter, "moose")
        self.assertEqual(PHYSICAL.segmenter, "spineps")
        self.assertNotEqual(slug(DEFAULT), slug(FLEXRAY))


class Presets(unittest.TestCase):
    def test_the_four_presets_hold_and_are_named(self):
        self.assertEqual(
            PRESETS,
            {
                "default": DEFAULT,
                "flexray": FLEXRAY,
                "physical": PHYSICAL,
                "fluxray-raw": FLUXRAY_RAW,
            },
        )
        for name, preset in PRESETS.items():
            self.assertEqual(problems(preset), [], name)
        self.assertEqual(len({slug(p) for p in PRESETS.values()}), 4)

    def test_physical_is_the_recipe_with_the_attenuation_randomisation_off(self):
        self.assertEqual(PHYSICAL.attenuation, "off")
        self.assertEqual(replace(PHYSICAL, attenuation="flexray-lognormal"), DEFAULT)

    def test_fluxray_raw_is_the_papers_raw_render_stream(self):
        raw = FLUXRAY_RAW
        self.assertEqual(
            (raw.crop, raw.crop_sampler, raw.pose, raw.isocentre),
            ("whole", "uniform", "fluxray-grid", "volume-centre"),
        )
        self.assertEqual((raw.projection, raw.attenuation, raw.scale), ("cone", "off", "minmax"))
        self.assertEqual((raw.views, raw.detector, raw.edit), (4, 1024, "none"))
        self.assertEqual(raw.hu_window, "flexray")

    def test_words_name_only_what_differs_from_the_default(self):
        self.assertEqual(words_of(DEFAULT), [])
        self.assertEqual(words_of(FLEXRAY), ["segmenter=moose"])
        self.assertEqual(words_of(PHYSICAL), ["attenuation=off"])
        for preset in PRESETS.values():
            self.assertEqual(parse(words_of(preset)), preset)


class Engines(unittest.TestCase):
    def test_the_two_engines_run_every_preset(self):
        self.assertEqual(ENGINES, ("blocks", "flexray-runtime"))
        for engine in ENGINES:
            for name, preset in PRESETS.items():
                self.assertEqual(engine_problems(engine, preset), [], f"{engine} {name}")

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

    def test_flexrays_runtime_takes_both_segmenters_and_the_fewest_crops(self):
        for segmenter in segmenters.SEGMENTERS:
            blocks = replace(DEFAULT, segmenter=segmenter, crop="flexray-axial-min")
            self.assertEqual(engine_problems("flexray-runtime", blocks), [])

    def test_the_grid_pose_runs_only_the_raw_streams_parts_in_flexrays_code(self):
        self.assertEqual(runtime_choices(FLUXRAY_RAW), GRID_CHOICES)
        self.assertEqual(runtime_choices(DEFAULT), RUNTIME_CHOICES)
        self.assertEqual(engine_problems("flexray-runtime", FLUXRAY_RAW), [])
        attenuated = replace(FLUXRAY_RAW, attenuation="flexray-lognormal")
        found = engine_problems("flexray-runtime", attenuated)
        self.assertEqual(len(found), 1)
        self.assertIn("attenuation='flexray-lognormal'", found[0])
        self.assertIn("pose=fluxray-grid its explicit-pose path runs only off", found[0])
        self.assertEqual(engine_problems("blocks", attenuated), [])
        cropped = replace(FLUXRAY_RAW, crop="flexray-axial")
        self.assertEqual(len(engine_problems("flexray-runtime", cropped)), 1)
        self.assertEqual(engine_problems("blocks", cropped), [])

    def test_the_runtimes_choices_are_subsets_of_the_choices(self):
        for table, preset in ((RUNTIME_CHOICES, DEFAULT), (GRID_CHOICES, FLUXRAY_RAW)):
            self.assertEqual(set(table), set(CHOICES))
            for name, allowed in table.items():
                self.assertTrue(set(allowed) <= set(CHOICES[name]), name)
                self.assertIn(getattr(preset, name), allowed)
            self.assertEqual(table["segmenter"], segmenters.SEGMENTERS)

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
        self.assertEqual(record["segmenter"], "spineps")

    def test_a_record_naming_a_choice_that_does_not_exist_is_refused(self):
        with self.assertRaises(RenderBlockError):
            from_record({**as_record(DEFAULT), "pose": "flexray-default"})

    def test_a_record_written_before_the_segmenter_part_takes_spineps(self):
        old = {k: v for k, v in as_record(FLEXRAY).items() if k != "segmenter"}
        self.assertEqual(from_record(old), DEFAULT)

    def test_parts_list_every_part_with_its_choices_and_the_default(self):
        rows = parts()
        self.assertEqual([row["part"] for row in rows], list(FIELDS))
        by_part = {row["part"]: row for row in rows}
        for name, allowed in CHOICES.items():
            self.assertEqual(by_part[name]["choices"], ", ".join(allowed))
            self.assertEqual(by_part[name]["default"], getattr(DEFAULT, name))
        for name, (low, high) in COUNTS.items():
            self.assertEqual(by_part[name]["choices"], f"a whole number from {low} to {high}")
        self.assertEqual(by_part["segmenter"]["choices"], "spineps, moose")


class CropPlan(unittest.TestCase):
    def test_the_two_axial_choices_name_the_packs_overlap_and_the_fewest_crops(self):
        self.assertEqual(AXIAL_CROPS, ("flexray-axial", "flexray-axial-min"))
        self.assertEqual(CROP_OVERLAP, {"flexray-axial": 0.5, "flexray-axial-min": 0.0})

    def test_a_short_volume_is_one_crop_padded_on_both_sides(self):
        for overlap in (0.0, 0.5):
            self.assertEqual(plan_crops(100, overlap), ((0, 100, 78, 78),))
            self.assertEqual(plan_crops(101, overlap), ((0, 101, 77, 78),))
            self.assertEqual(plan_crops(1, overlap), ((0, 1, 127, 128),))

    def test_an_exact_volume_is_one_crop_with_no_pad(self):
        self.assertEqual(plan_crops(CROP_DEPTH), ((0, CROP_DEPTH, 0, 0),))
        self.assertEqual(plan_crops(CROP_DEPTH, 0.0), ((0, CROP_DEPTH, 0, 0),))

    def test_a_volume_under_a_step_longer_is_two_crops_touching_both_ends(self):
        # At overlap 0 the step is 256 slices, at 0.5 it is 128.
        self.assertEqual(plan_crops(257, 0.0), ((0, 256, 0, 0), (1, 257, 0, 0)))
        self.assertEqual(plan_crops(300, 0.0), ((0, 256, 0, 0), (44, 300, 0, 0)))
        self.assertEqual(plan_crops(511, 0.0), ((0, 256, 0, 0), (255, 511, 0, 0)))
        self.assertEqual(plan_crops(300), ((0, 256, 0, 0), (44, 300, 0, 0)))
        self.assertEqual(plan_crops(383), ((0, 256, 0, 0), (127, 383, 0, 0)))

    def test_flexrays_700_slice_example_at_both_overlaps(self):
        self.assertEqual([start for start, _, _, _ in plan_crops(700, 0.0)], [0, 222, 444])
        self.assertEqual([start for start, _, _, _ in plan_crops(700)], [0, 111, 222, 333, 444])
        self.assertEqual(plan_crops(700), plan_crops(700, 0.5))

    def test_the_packs_plan_halves_the_step(self):
        self.assertEqual([s for s, _, _, _ in plan_crops(512)], [0, 128, 256])
        self.assertEqual([s for s, _, _, _ in plan_crops(511)], [0, 128, 255])
        self.assertEqual([s for s, _, _, _ in plan_crops(400)], [0, 72, 144])
        self.assertEqual([s for s, _, _, _ in plan_crops(512, 0.0)], [0, 256])

    def test_a_long_volume_at_overlap_0_is_the_fewest_crops_touching_both_ends(self):
        for depth in (512, 513, 1000, 1500, 4096):
            plan = plan_crops(depth, 0.0)
            starts = [start for start, _, _, _ in plan]
            self.assertEqual(starts[0], 0)
            self.assertEqual(starts[-1], depth - CROP_DEPTH)
            self.assertEqual(len(plan), 2 + (depth - CROP_DEPTH - 1) // CROP_DEPTH)
            for earlier, later in zip(starts, starts[1:], strict=False):
                self.assertLessEqual(later - earlier, CROP_DEPTH)
                self.assertGreater(later, earlier)
            for _, _, before, after in plan:
                self.assertEqual((before, after), (0, 0))

    def test_a_long_volume_at_overlap_half_keeps_neighbours_within_half_a_crop(self):
        for depth in (512, 513, 1000, 1500, 4096):
            plan = plan_crops(depth)
            starts = [start for start, _, _, _ in plan]
            self.assertEqual((starts[0], starts[-1]), (0, depth - CROP_DEPTH))
            self.assertEqual(len(plan), 2 + (depth - CROP_DEPTH - 1) // (CROP_DEPTH // 2))
            for earlier, later in zip(starts, starts[1:], strict=False):
                self.assertLessEqual(later - earlier, CROP_DEPTH // 2)
                self.assertGreater(later, earlier)

    def test_an_overlap_of_one_or_more_is_refused(self):
        with self.assertRaises(ViolationError):
            plan_crops(700, 1.0)
        with self.assertRaises(ViolationError):
            plan_crops(700, -0.1)


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
        raw = [1.0, 2**0.5, 4**0.5, 1.0]
        mean = sum(raw) / 4
        for found, expected in zip(crop_weights(classes), raw, strict=True):
            self.assertAlmostEqual(found, expected / mean)

    def test_crop_weights_of_one_class_everywhere_are_equal(self):
        for found in crop_weights([frozenset({5})] * 3):
            self.assertAlmostEqual(found, 1.0)


class Grid(unittest.TestCase):
    def test_the_grid_is_the_papers_90_poses(self):
        self.assertEqual(GRID_POSES, 90)
        self.assertEqual(GRID_Y_MM, (650.0, 900.0, 1150.0))
        self.assertEqual(GRID_Z_MM, (-300.0, -200.0, -100.0, 0.0, 100.0, 200.0))
        self.assertEqual(set(GRID_ALPHA_DEG), {0.0, 45.0, -45.0, 90.0, -90.0})
        self.assertEqual((GRID_SDD_MM, GRID_PIXEL_MM), (1250.0, 0.6))

    def test_every_index_names_a_different_pose_and_all_are_covered(self):
        poses = {grid_pose(i) for i in range(GRID_POSES)}
        self.assertEqual(len(poses), GRID_POSES)
        for alpha in GRID_ALPHA_DEG:
            for y in GRID_Y_MM:
                for z in GRID_Z_MM:
                    self.assertIn((alpha, y, z), poses)

    def test_the_order_is_y_then_z_then_alpha(self):
        self.assertEqual(grid_pose(0), (0.0, 650.0, -300.0))
        self.assertEqual(grid_pose(1), (45.0, 650.0, -300.0))
        self.assertEqual(grid_pose(5), (0.0, 650.0, -200.0))
        self.assertEqual(grid_pose(30), (0.0, 900.0, -300.0))
        self.assertEqual(grid_pose(89), (-90.0, 1150.0, 200.0))

    def test_an_index_outside_the_grid_is_refused(self):
        with self.assertRaises(ViolationError):
            grid_pose(90)
        with self.assertRaises(ViolationError):
            grid_pose(-1)


if __name__ == "__main__":
    unittest.main()
