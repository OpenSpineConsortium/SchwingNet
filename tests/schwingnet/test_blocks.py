"""The trainer's building blocks: the defaults are version 1's, a fault is refused in words."""

import math

import pytest

from schwingnet.blocks import (
    AUGMENT,
    DEFAULT,
    BlockError,
    Blocks,
    as_record,
    balanced_accuracy,
    from_record,
    inverse_frequency,
    lr_factor,
    parse,
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
    ],
)
def test_a_fault_is_refused_whole(words):
    with pytest.raises(BlockError):
        parse(words)


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
