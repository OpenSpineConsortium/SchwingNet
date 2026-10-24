"""The trainer's building blocks: the defaults are version 1's, a fault is refused in words."""

import math

import pytest

from schwingnet.blocks import (
    AUGMENT,
    CHOICES,
    DEFAULT,
    FIELDS,
    SETTINGS,
    BlockError,
    Blocks,
    as_record,
    balanced_accuracy,
    from_record,
    inverse_frequency,
    kept,
    lr_factor,
    parse,
    parts,
    sweep,
    words_of,
)


def test_no_words_are_version_1s_training():
    assert parse([]) == DEFAULT == Blocks()
    assert from_record(None) == DEFAULT
    assert from_record({}) == DEFAULT


def test_words_choose_each_part_and_round_trip_through_the_record():
    blocks = parse(["normalise=imagenet", "augment=box-jitter,noise", "optimiser=adamw", "weight-decay=0.05",
                    "schedule=cosine", "warmup_epochs=2", "backbone_lr_scale=0.1", "sampler=balanced",
                    "loss_weights=inverse-frequency", "select=balanced-accuracy"])
    assert blocks.augment == ("box-jitter", "noise")
    assert blocks.weight_decay == 0.05 and blocks.warmup_epochs == 2
    assert from_record(as_record(blocks)) == blocks
    more = parse(["samples=drop-sources", "sources=vindr,lumos", "architecture=mobilenet-v3-small",
                  "denoise=median"])
    assert more.sources == ("vindr", "lumos") and more.per_person == 0
    assert as_record(more)["sources"] == ["vindr", "lumos"]
    assert from_record(as_record(more)) == more
    assert words_of(more) == ["samples=drop-sources", "sources=vindr,lumos",
                              "architecture=mobilenet-v3-small", "denoise=median"]
    capped = parse(["samples=cap-per-person", "per-person=3"])
    assert capped.per_person == 3 and from_record(as_record(capped)) == capped
    pasted = parse(["samples=only-sources", "sources=carmlspine, vindr"])
    assert pasted.sources == ("carmlspine", "vindr")


@pytest.mark.parametrize(
    "words",
    [
        ["normalise=zscore"],
        ["augment=flip"],
        ["augment=noise,noise"],
        ["optimiser=sgd"],
        ["weight_decay=-1"],
        ["weight_decay=nan"],
        ["optimiser=adam", "weight_decay=0.1"],
        ["warmup_epochs=two"],
        ["backbone_lr_scale=0"],
        ["backbone_lr_scale=2"],
        ["sampler=x"],
        ["select=loss"],
        ["colour=red"],
        ["normalise"],
        ["schedule=cosine", "schedule=constant"],
        ["samples=some"],
        ["samples=only-sources"],
        ["sources=vindr"],
        ["samples=drop-sources", "sources=vindr,vindr"],
        ["samples=cap-per-person"],
        ["samples=cap-per-person", "per_person=0"],
        ["per_person=2"],
        ["samples=only-sources", "sources=vindr", "per_person=2"],
        ["samples=cap-per-person", "per_person=1234567"],
        ["architecture=resnet19"],
        ["denoise=wavelet"],
    ],
)
def test_a_fault_is_refused_whole(words):
    with pytest.raises(BlockError):
        parse(words)


def test_kept_keeps_everything_by_default_and_cuts_by_source_or_by_person():
    sources = ["a", "b", "a", "b", "a"]
    persons = ["p1", "p1", "p2", "p1", "p2"]
    assert kept(DEFAULT, sources, persons) == [True] * 5
    assert kept(parse(["samples=only-sources", "sources=a"]), sources, persons) == [
        True, False, True, False, True]
    assert kept(parse(["samples=drop-sources", "sources=a"]), sources, persons) == [
        False, True, False, True, False]
    assert kept(parse(["samples=cap-per-person", "per_person=1"]), sources, persons) == [
        True, False, True, False, False]
    assert kept(parse(["samples=cap-per-person", "per_person=2"]), sources, persons) == [
        True, True, True, False, True]
    assert kept(DEFAULT, [], []) == []


def test_parts_lists_every_field_once_with_its_choices_and_version_1():
    rows = parts()
    assert [row["part"] for row in rows] == list(FIELDS)
    by_part = {row["part"]: row for row in rows}
    for name, allowed in CHOICES.items():
        assert by_part[name]["choices"] == ", ".join(allowed)
        assert by_part[name]["default"] in allowed
    for name, words in SETTINGS.items():
        assert by_part[name]["choices"] == words
    assert by_part["augment"]["default"] == "none"
    assert by_part["architecture"]["default"] == "resnet18"
    assert by_part["per_person"]["default"] == "0"
    assert set(CHOICES) | set(SETTINGS) == set(FIELDS)


def test_augment_none_names_nothing():
    assert parse(["augment=none"]).augment == ()
    assert set(AUGMENT) == {"box-jitter", "intensity", "blur", "noise"}


def test_the_schedule_warms_up_then_holds_or_decays_above_zero():
    assert [lr_factor(e, 5, 0, "constant") for e in range(1, 6)] == [1.0] * 5
    warm = [lr_factor(e, 6, 2, "cosine") for e in range(1, 7)]
    assert warm[0] == pytest.approx(1 / 3) and warm[1] == pytest.approx(2 / 3)
    assert warm[2] == pytest.approx(1.0)
    assert all(a > b for a, b in zip(warm[2:], warm[3:]))
    assert warm[-1] > 0.0
    assert lr_factor(1, 1, 0, "cosine") == 1.0


def test_inverse_frequency_averages_one_over_present_levels():
    weights = inverse_frequency({"L1": 10, "L2": 30, "L6": 0})
    assert weights["L6"] == 0.0
    assert (weights["L1"] + weights["L2"]) / 2 == pytest.approx(1.0)
    assert weights["L1"] == pytest.approx(3 * weights["L2"])


def test_balanced_accuracy_weighs_each_level_alike():
    assert balanced_accuracy({"L1": (90, 100), "L6": (0, 2), "T13": (0, 0)}) == pytest.approx(0.45)
    assert balanced_accuracy({}) == 0.0
    assert math.isclose(balanced_accuracy({"L1": (1, 1)}), 1.0)


def test_a_sweep_plans_every_combination_in_a_fixed_order():
    runs = sweep(["normalise=imagenet"], {"sampler": ["uniform", "balanced"], "augment": ["none", "box-jitter,noise"]})
    assert len(runs) == 4
    assert all(r.normalise == "imagenet" for r in runs)
    assert [(r.augment, r.sampler) for r in runs] == [((), "uniform"), ((), "balanced"),
                                                     (("box-jitter", "noise"), "uniform"), (("box-jitter", "noise"), "balanced")]
    assert words_of(runs[3]) == ["normalise=imagenet", "augment=box-jitter,noise", "sampler=balanced"]
    assert words_of(DEFAULT) == []


@pytest.mark.parametrize(
    "base, vary",
    [
        ([], {"optimiser": ["adam"], "weight_decay": ["0.1"]}),
        (["sampler=balanced"], {"sampler": ["uniform"]}),
        ([], {"select": []}),
        ([], {"warmup_epochs": [str(n) for n in range(9)], "weight_decay": [str(n) for n in range(9)]}),
    ],
)
def test_a_sweep_that_cannot_run_whole_is_refused(base, vary):
    with pytest.raises(BlockError):
        sweep(base, vary)
