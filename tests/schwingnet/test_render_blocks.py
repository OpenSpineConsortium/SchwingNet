"""The renderer's building blocks: the defaults are FleXray's recipe, a fault refused in words."""

from dataclasses import replace

import pytest

from schwingnet.render_blocks import (
    CHOICES,
    COUNTS,
    CROP_DEPTH,
    DEFAULT,
    FIELDS,
    PHYSICAL,
    RenderBlockError,
    RenderBlocks,
    as_record,
    crop_weights,
    from_record,
    parse,
    parts,
    plan_crops,
    problems,
    slug,
)


def test_no_words_are_flexrays_recipe():
    assert parse([]) == DEFAULT == RenderBlocks()
    assert not problems(DEFAULT)
    assert (
        PHYSICAL.attenuation == "off"
        and replace(PHYSICAL, attenuation="flexray-lognormal") == DEFAULT
    )


def test_words_choose_each_part_and_round_trip_through_the_record():
    blocks = parse(
        ["attenuation=off", "crop=whole", "crop-sampler=uniform", "views=2", "detector=128"]
    )
    assert blocks.attenuation == "off" and blocks.crop == "whole" and blocks.views == 2
    assert from_record(as_record(blocks)) == blocks
    assert from_record(as_record(DEFAULT)) == DEFAULT


def test_a_word_naming_no_block_is_refused_in_words():
    with pytest.raises(RenderBlockError, match="KEY=VALUE"):
        parse(["lighting=soft"])
    with pytest.raises(RenderBlockError, match="KEY=VALUE"):
        parse(["attenuation"])


def test_a_choice_that_does_not_exist_is_refused_with_the_choices():
    with pytest.raises(RenderBlockError, match="flexray-lognormal, off"):
        parse(["attenuation=strong"])


def test_a_block_named_twice_is_refused():
    with pytest.raises(RenderBlockError, match="named twice"):
        parse(["views=2", "views=3"])


def test_counts_are_held_to_their_ranges():
    with pytest.raises(RenderBlockError, match="views is a whole number from 1 to 100"):
        parse(["views=0"])
    with pytest.raises(RenderBlockError, match="not a whole number"):
        parse(["detector=-5"])
    with pytest.raises(RenderBlockError, match="not a whole number"):
        parse(["ray_samples=12345"])


def test_the_label_weighted_sampler_needs_flexrays_crops():
    with pytest.raises(RenderBlockError, match="goes with crop=flexray-axial"):
        parse(["crop=whole"])
    assert problems(replace(DEFAULT, crop="whole", crop_sampler="uniform")) == []


def test_the_slug_names_the_configuration_alone():
    assert slug(DEFAULT) == slug(RenderBlocks())
    assert slug(DEFAULT) != slug(PHYSICAL)
    assert len(slug(DEFAULT)) == 12


def test_parts_list_every_part_with_its_choices_and_flexrays_default():
    rows = parts()
    assert [row["part"] for row in rows] == list(FIELDS)
    by_part = {row["part"]: row for row in rows}
    for name, allowed in CHOICES.items():
        assert by_part[name]["choices"] == ", ".join(allowed)
        assert by_part[name]["default"] == getattr(DEFAULT, name)
    for name, (low, high) in COUNTS.items():
        assert by_part[name]["choices"] == f"a whole number from {low} to {high}"


def test_a_short_volume_is_one_crop_padded_on_both_sides():
    assert plan_crops(100) == ((0, 100, 78, 78),)
    assert plan_crops(101) == ((0, 101, 77, 78),)
    assert plan_crops(CROP_DEPTH) == ((0, CROP_DEPTH, 0, 0),)


def test_a_long_volume_is_the_fewest_crops_touching_both_ends():
    assert plan_crops(300) == ((0, 256, 0, 0), (44, 300, 0, 0))
    plan = plan_crops(1000)
    starts = [start for start, _, _, _ in plan]
    assert starts[0] == 0 and starts[-1] == 1000 - CROP_DEPTH
    assert len(plan) == 4
    assert all(
        later - earlier <= CROP_DEPTH for earlier, later in zip(starts, starts[1:], strict=False)
    )


def test_crop_weights_favour_crops_holding_rare_classes():
    weights = crop_weights([frozenset({1}), frozenset({1}), frozenset({1, 2}), frozenset()])
    assert weights[3] == 0.0
    assert weights[2] > weights[0] == weights[1]
    assert sum(weights) / len(weights) == pytest.approx(1.0)


def test_crop_weights_of_one_class_everywhere_are_equal():
    assert crop_weights([frozenset({5})] * 3) == pytest.approx((1.0, 1.0, 1.0))
