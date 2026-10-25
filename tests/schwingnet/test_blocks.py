"""The trainer's building blocks: the defaults are version 1's, a fault is refused in words."""

import hashlib
import json
import math
from dataclasses import replace
from itertools import combinations

import pytest

from schwingnet.blocks import (
    ARCHITECTURE,
    AUGMENT,
    CHOICES,
    DEFAULT,
    FIELDS,
    FIRST_LABELLED,
    LABELLED,
    PRIOR,
    SETTINGS,
    UNLABELLED,
    BlockError,
    Blocks,
    as_record,
    balanced_accuracy,
    cover,
    from_record,
    inverse_frequency,
    kept,
    lr_factor,
    parse,
    parts,
    problems,
    sweep,
    trials,
    words_of,
)


def test_no_words_are_version_1s_training():
    assert parse([]) == DEFAULT == Blocks()
    assert from_record(None) == DEFAULT
    assert from_record({}) == DEFAULT


def test_words_choose_each_part_and_round_trip_through_the_record():
    blocks = parse(
        [
            "normalise=imagenet",
            "augment=box-jitter,noise",
            "optimiser=adamw",
            "weight-decay=0.05",
            "schedule=cosine",
            "warmup_epochs=2",
            "backbone_lr_scale=0.1",
            "sampler=balanced",
            "loss_weights=inverse-frequency",
            "select=balanced-accuracy",
        ]
    )
    assert blocks.augment == ("box-jitter", "noise")
    assert blocks.weight_decay == 0.05 and blocks.warmup_epochs == 2
    assert from_record(as_record(blocks)) == blocks
    more = parse(
        [
            "samples=drop-sources",
            "sources=vindr,lumos",
            "architecture=mobilenet-v3-small",
            "denoise=median",
        ]
    )
    assert more.sources == ("vindr", "lumos") and more.per_person == 0
    assert as_record(more)["sources"] == ["vindr", "lumos"]
    assert from_record(as_record(more)) == more
    assert words_of(more) == [
        "samples=drop-sources",
        "sources=vindr,lumos",
        "architecture=mobilenet-v3-small",
        "denoise=median",
    ]
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
        ["prior=anchors"],
        ["prior=level-map"],
        ["prior_weight=0.5"],
        ["prior=level-map", "prior_weight=0"],
        ["prior=level-map", "prior_weight=-1"],
        ["prior=level-map", "prior_weight=inf"],
        ["prior=none", "prior_weight=1"],
    ],
)
def test_a_fault_is_refused_whole(words):
    with pytest.raises(BlockError):
        parse(words)


def test_the_prior_goes_with_its_weight_and_is_off_by_default():
    assert (DEFAULT.prior, DEFAULT.prior_weight) == ("none", 0.0)
    chosen = parse(["prior=level-map", "prior_weight=0.5"])
    assert (chosen.prior, chosen.prior_weight) == ("level-map", 0.5)
    assert as_record(chosen)["prior_weight"] == 0.5
    assert from_record(as_record(chosen)) == chosen
    assert "prior" in CHOICES and "prior_weight" in SETTINGS


def test_kept_keeps_everything_by_default_and_cuts_by_source_or_by_person():
    sources = ["a", "b", "a", "b", "a"]
    persons = ["p1", "p1", "p2", "p1", "p2"]
    assert kept(DEFAULT, sources, persons) == [True] * 5
    assert kept(parse(["samples=only-sources", "sources=a"]), sources, persons) == [
        True,
        False,
        True,
        False,
        True,
    ]
    assert kept(parse(["samples=drop-sources", "sources=a"]), sources, persons) == [
        False,
        True,
        False,
        True,
        False,
    ]
    assert kept(parse(["samples=cap-per-person", "per_person=1"]), sources, persons) == [
        True,
        False,
        True,
        False,
        False,
    ]
    assert kept(parse(["samples=cap-per-person", "per_person=2"]), sources, persons) == [
        True,
        True,
        True,
        False,
        True,
    ]
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
    assert AUGMENT == ("box-jitter", "intensity", "blur", "noise", "strong")
    assert parse(["augment=strong"]).augment == ("strong",)


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
    runs = sweep(
        ["normalise=imagenet"],
        {"sampler": ["uniform", "balanced"], "augment": ["none", "box-jitter,noise"]},
    )
    assert len(runs) == 4
    assert all(r.normalise == "imagenet" for r in runs)
    assert [(r.augment, r.sampler) for r in runs] == [
        ((), "uniform"),
        ((), "balanced"),
        (("box-jitter", "noise"), "uniform"),
        (("box-jitter", "noise"), "balanced"),
    ]
    assert words_of(runs[3]) == [
        "normalise=imagenet",
        "augment=box-jitter,noise",
        "sampler=balanced",
    ]
    assert words_of(DEFAULT) == []


@pytest.mark.parametrize(
    "base, vary",
    [
        ([], {"optimiser": ["adam"], "weight_decay": ["0.1"]}),
        (["sampler=balanced"], {"sampler": ["uniform"]}),
        ([], {"select": []}),
        (
            [],
            {
                "warmup_epochs": [str(n) for n in range(9)],
                "weight_decay": [str(n) for n in range(9)],
            },
        ),
    ],
)
def test_a_sweep_that_cannot_run_whole_is_refused(base, vary):
    with pytest.raises(BlockError):
        sweep(base, vary)


# The values each factor of the cover takes, as tests/test_block_sweep.py reads them from a plan:
# the size beside the blocks, each augment name on or off, every other part by its own name.
FACTORS = {
    "architecture": ARCHITECTURE,
    "size": (64, 32, 96, 128),
    "denoise": CHOICES["denoise"],
    "normalise": CHOICES["normalise"],
    "samples": ("all", "only-sources", "cap-per-person"),
    "optimiser": CHOICES["optimiser"],
    "schedule": CHOICES["schedule"],
    "warmup_epochs": (0, 1),
    "backbone_lr_scale": (1.0, 0.1),
    "sampler": CHOICES["sampler"],
    "loss_weights": CHOICES["loss_weights"],
    "select": CHOICES["select"],
    **{f"augment:{name}": (False, True) for name in AUGMENT},
}
PAIRS = [
    ("denoise", "normalise"),
    ("sampler", "loss_weights"),
    ("optimiser", "schedule"),
    ("schedule", "warmup_epochs"),
]


def value(row, name):
    if name == "size":
        return row["size"]
    if name.startswith("augment:"):
        return name.removeprefix("augment:") in row["blocks"].augment
    return getattr(row["blocks"], name)


def holds_every_value_and_pair(rows, factors, pairs):
    seen = [{name: value(row, name) for name in factors} for row in rows]
    singles = all(
        any(cells[name] == v for cells in seen) for name, values in factors.items() for v in values
    )
    met = all(
        any(cells[a] == x and cells[b] == y for cells in seen)
        for a, b in pairs
        for x in factors[a]
        for y in factors[b]
    )
    return singles and met


def slug_of(row):
    record = {
        "blocks": as_record(row["blocks"]),
        "size": row["size"],
        "weights": row["weights"],
        "init": row["init"],
    }
    digest = hashlib.sha256(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()
    prefix = "" if row["role"] == "cover" else f"{row['role']}-"
    return f"{prefix}{row['blocks'].architecture}-{row['size']}px-{digest[:8]}"


def cuts_one_labelled(row):
    return row["blocks"].sources == (FIRST_LABELLED,)


def test_the_cover_is_two_halves_of_ten_then_seven_routes():
    rows = cover()
    assert len(rows) == 27
    assert [row["role"] for row in rows] == ["cover"] * 20 + [
        "imagenet",
        "init",
        "init",
        "refuse",
        "refuse",
        "refuse",
        "refuse",
    ]
    assert [row["blocks"].prior for row in rows[:20]] == ["none"] * 10 + ["level-map"] * 10
    assert all(row["blocks"].prior_weight == 0.5 for row in rows[10:20])
    assert all(not problems(row["blocks"]) for row in rows)
    assert len({row["slug"] for row in rows}) == 27
    assert all(row["slug"] == slug_of(row) for row in rows)
    assert cover() == rows


def test_each_half_runs_every_option_and_every_pair_asked_for():
    # The array rows train on every catalog with labelled crops; the two rows that cut to one
    # labelled source of several train on a strict part of the labelled crops wherever the
    # catalog holds two labelled sources, as the synthetic one does, and run nothing else.
    rows = cover()
    for half in (rows[:10], rows[10:20]):
        everywhere = [row for row in half if not cuts_one_labelled(row)]
        cuts = [row for row in half if cuts_one_labelled(row)]
        assert len(everywhere) == 8
        assert all(row["blocks"].samples != "drop-sources" for row in everywhere)
        assert holds_every_value_and_pair(everywhere, FACTORS, PAIRS)
        assert [(r["blocks"].samples, r["size"]) for r in cuts] == [
            ("only-sources", 64),
            ("drop-sources", 64),
        ]
        prior = half[0]["blocks"].prior
        assert all(
            replace(r["blocks"], samples="all", sources=())
            == replace(DEFAULT, prior=prior, prior_weight=r["blocks"].prior_weight)
            for r in cuts
        )
        assert {row["blocks"].architecture for row in half} == set(ARCHITECTURE)


def test_the_source_cuts_take_the_placeholders_and_the_settings_their_canonical_values():
    for row in cover():
        blocks = row["blocks"]
        if blocks.samples == "only-sources" and row["role"] == "cover":
            assert blocks.sources in ((LABELLED,), (FIRST_LABELLED,))
        if blocks.samples == "drop-sources" and row["role"] == "cover":
            assert blocks.sources == (FIRST_LABELLED,)
        if blocks.samples == "cap-per-person":
            assert blocks.per_person == 1
        if blocks.optimiser == "adamw":
            assert blocks.weight_decay == 0.01


def test_the_routes_start_from_the_first_row_and_refuse_what_the_check_predicts():
    rows = cover()
    parent = rows[0]
    assert (parent["blocks"], parent["size"]) == (DEFAULT, 64)
    imagenet, same, prior, drops, onlys, across, both = rows[20:]
    assert (imagenet["blocks"].normalise, imagenet["size"]) == ("imagenet", 64)
    assert (imagenet["weights"], imagenet["init"]) == ("resnet18", None)
    assert (same["blocks"], same["size"], same["init"]) == (DEFAULT, 64, parent["slug"])
    assert (prior["blocks"].prior, prior["blocks"].prior_weight) == ("level-map", 0.5)
    assert prior["init"] == parent["slug"]
    assert (drops["blocks"].samples, drops["blocks"].sources) == ("drop-sources", (LABELLED,))
    assert (onlys["blocks"].samples, onlys["blocks"].sources) == ("only-sources", (UNLABELLED,))
    assert across["init"] == parent["slug"] and across["blocks"].architecture != "resnet18"
    assert (both["weights"], both["init"]) == ("resnet18", parent["slug"])
    assert all(row["slug"].startswith(f"{row['role']}-") for row in rows[20:])


def test_the_strict_cover_holds_every_pair_of_every_two_factors_the_prior_among_them():
    rows = cover(strict=True)
    cover_rows = [row for row in rows if row["role"] == "cover"]
    assert len(cover_rows) == 36 and len(rows) == 43
    everywhere = [row for row in cover_rows if not cuts_one_labelled(row)]
    factors = {**FACTORS, "prior": PRIOR}
    assert len(everywhere) == 32
    assert holds_every_value_and_pair(everywhere, factors, list(combinations(factors, 2)))
    cuts = [
        (row["blocks"].samples, row["blocks"].prior) for row in cover_rows if cuts_one_labelled(row)
    ]
    assert cuts == [(cut, prior) for prior in PRIOR for cut in ("only-sources", "drop-sources")]


def test_the_trials_are_six_resnet18_arms_from_imagenet_the_first_version_1s():
    rows = trials()
    assert [row["size"] for row in rows] == [64, 64, 64, 96, 64, 64]
    assert all(row["role"] == "trial" and row["weights"] == "resnet18" for row in rows)
    assert all(row["init"] is None and row["slug"] == slug_of(row) for row in rows)
    control, strong, tuned, wide, balanced, both = (row["blocks"] for row in rows)
    assert control == DEFAULT
    assert (strong.normalise, strong.augment) == ("imagenet", AUGMENT)
    assert (tuned.optimiser, tuned.weight_decay, tuned.warmup_epochs) == ("adamw", 0.01, 1)
    assert (tuned.schedule, tuned.backbone_lr_scale) == ("cosine", 0.1)
    assert wide == strong
    assert (balanced.sampler, balanced.select) == ("balanced", "balanced-accuracy")
    assert balanced.optimiser == "adam"
    assert (both.sampler, both.select, both.optimiser) == ("balanced", "balanced-accuracy", "adamw")
