"""The auto-anatomist's search as pure logic: a plan is read one way or refused in words, the
split is the rule's hash, the halving keeps by score, the reward counts what was measured, the
controller is one REINFORCE step with a floor, and the ledger is checked whole."""

import copy
import hashlib
import json
import math
from typing import Any

import pytest
from beartype.roar import BeartypeCallHintParamViolation
from icontract import ViolationError

from schwingnet.autoanatomist_search import (
    LEDGER_KEYS,
    LEDGER_VERSION,
    NO_COVERAGE,
    NO_DISTANCE,
    NO_NAMING,
    PARTS,
    PLAN_KEYS,
    Controller,
    Measures,
    Objective,
    Plan,
    Split,
    as_record,
    best_trial,
    hash_value,
    kept,
    last_rewards,
    ledger_fits,
    ledger_problems,
    manifest_of,
    manifest_problems,
    measure_notes,
    measures_of,
    new_ledger,
    nominal_coverage_of,
    part_ids,
    part_of,
    plan_of,
    plan_problems,
    policy_fits,
    probabilities,
    reward,
    round_configurations,
    rung_steps,
    sample,
    stepped,
    summary_lines,
    trial_id,
    trial_words,
    uniform_policy,
    updated,
    words_digest,
)

SPACE = {"lr": ["0.001", "0.003"], "optimiser": ["adamw", "sgd"], "schedule": ["joint", "fixed"]}


def phantom_row(n: int) -> dict[str, Any]:
    return {
        "kind": "phantom",
        "id": f"ph{n:02d}",
        "phenotype": "typical",
        "start": "L1",
        "count": 3,
        "seed": n,
        "spacing": 2.0,
        "sub": 1,
        "noise": 20.0,
    }


def plan_record() -> dict[str, Any]:
    return {
        "search": "phantom_smoke",
        "class": "batch",
        "rows": [phantom_row(n) for n in range(12)],
        "split": {"salt": "autoanatomist-2026-10-29", "validation_share": 0.25, "test_share": 0.15},
        "space": copy.deepcopy(SPACE),
        "fixed": ["calibrate=quantile", "anneal=300"],
        "seeds": [{"lr": "0.001", "optimiser": "adamw", "schedule": "joint"}],
        "rungs": [10, 30, 90],
        "keep": 0.5,
        "trials": 4,
        "controller": {"lr": 0.5, "baseline_decay": 0.8, "entropy_floor": 0.1, "seed": 7},
        "objective": {"w_distance": 0.05, "w_coverage": 1.0},
        "latency_crops": 20,
        "wandb_project": "SchwingNet",
    }


def a_plan() -> Plan:
    return plan_of(plan_record())


def changed(**fields: Any) -> dict[str, Any]:
    record = plan_record()
    record.update(fields)
    return record


def with_row(row: Any, at: int = 1) -> dict[str, Any]:
    record = plan_record()
    record["rows"][at] = row
    return record


def test_a_plan_that_holds_is_read_whole_and_typed():
    record = plan_record()
    assert plan_problems(record) == []
    plan = plan_of(record)
    assert plan.search == "phantom_smoke" and plan.job_class == "batch"
    assert len(plan.rows) == 12 and plan.rows[3]["id"] == "ph03"
    assert plan.split == Split("autoanatomist-2026-10-29", 0.25, 0.15)
    assert plan.space == {k: tuple(v) for k, v in SPACE.items()}
    assert plan.fixed == ("calibrate=quantile", "anneal=300")
    assert plan.seeds == (("lr=0.001", "optimiser=adamw", "schedule=joint"),)
    assert plan.rungs == (10, 30, 90) and plan.keep == 0.5 and plan.trials == 4
    assert plan.controller == Controller(0.5, 0.8, 0.1, 7)
    assert plan.objective == Objective(0.05, 1.0)
    assert plan.latency_crops == 20 and plan.wandb_project == "SchwingNet"
    assert as_record(plan)["search"] == "phantom_smoke"
    assert as_record(plan)["controller"] == {
        "lr": 0.5,
        "baseline_decay": 0.8,
        "entropy_floor": 0.1,
        "seed": 7,
    }


@pytest.mark.parametrize(
    "record, said",
    [
        ("plan", "a plan is a JSON object"),
        ({k: v for k, v in plan_record().items() if k != "rungs"}, "missing rungs, unknown none"),
        ({**plan_record(), "extra": 1}, "missing none, unknown extra"),
        (changed(search="Smoke"), "search: lower-case letters"),
        (changed(**{"class": "cpu"}), "class: one of batch, gpu"),
        (changed(rows=[phantom_row(0), phantom_row(1)]), "rows: at least three rows"),
        (with_row("ph01"), "is not a row"),
        (with_row({**phantom_row(1), "kind": "volume"}), "a row's kind is one of phantom"),
        (with_row({**phantom_row(1), "id": "PH 1"}), "a row's id is lower-case letters"),
        (with_row(phantom_row(0)), "the id ph00 is listed twice"),
        (with_row({**phantom_row(1), "count": [3]}), "ph01 holds a value that is no string"),
        (changed(split={"salt": "s", "validation_share": 0.2}), "split: salt, validation_share"),
        (changed(split={"salt": "", "validation_share": 0.2, "test_share": 0.1}), "the salt is"),
        (
            changed(split={"salt": "s", "validation_share": 1.5, "test_share": 0.1}),
            "validation_share is a share",
        ),
        (
            changed(split={"salt": "s", "validation_share": 0.6, "test_share": 0.4}),
            "nothing to train on",
        ),
        (changed(space={}), "space: at least one block"),
        (changed(space={"Lr": ["a", "b"]}, fixed=[], seeds=[]), "a block's name is lower-case"),
        (changed(space={"lr": ["a"]}, fixed=[], seeds=[]), "needs at least two values"),
        (changed(space={"lr": ["a b", "c"]}, fixed=[], seeds=[]), "words without spaces or ="),
        (changed(space={"lr": ["a", "a"]}, fixed=[], seeds=[]), "lists a value twice"),
        (changed(fixed="calibrate=quantile"), "fixed: a list of KEY=VALUE words"),
        (changed(fixed=["calibrate"]), "is not a KEY=VALUE word"),
        (changed(fixed=["lr=0.1"]), "lr is a block of the space, which the controller chooses"),
        (changed(fixed=["anneal=1", "anneal=2"]), "fixed: a block is named twice"),
        (changed(seeds={"lr": "0.001"}), "seeds: a list of configurations"),
        (
            changed(seeds=[{"lr": "0.001"}]),
            "each seed names every block of the space (lr, optimiser, schedule)",
        ),
        (
            changed(seeds=[{"lr": "9", "optimiser": "adamw", "schedule": "joint"}]),
            "lr='9' is not a value",
        ),
        (changed(rungs=[]), "rungs: 1 to 3 step counts"),
        (changed(rungs=[1, 2, 3, 4]), "rungs: 1 to 3 step counts"),
        (changed(rungs=[10, 10]), "each above the one before"),
        (changed(rungs=[0]), "whole numbers of at least 1"),
        (
            changed(controller={"lr": 0.5}),
            "controller: lr, baseline_decay, entropy_floor, seed, and nothing else",
        ),
        (
            changed(controller={"lr": 0, "baseline_decay": 0.8, "entropy_floor": 0.1, "seed": 7}),
            "lr is a number above 0",
        ),
        (
            changed(
                controller={"lr": 2000, "baseline_decay": 0.8, "entropy_floor": 0.1, "seed": 7}
            ),
            "at most 1000",
        ),
        (
            changed(controller={"lr": 0.5, "baseline_decay": 1, "entropy_floor": 0.1, "seed": 7}),
            "baseline_decay",
        ),
        (
            changed(controller={"lr": 0.5, "baseline_decay": 0.8, "entropy_floor": 0.5, "seed": 7}),
            "entropy_floor",
        ),
        (
            changed(
                controller={"lr": 0.5, "baseline_decay": 0.8, "entropy_floor": 0.1, "seed": -1}
            ),
            "the seed",
        ),
        (
            changed(objective={"w_distance": 1}),
            "objective: w_distance, w_coverage, and nothing else",
        ),
        (changed(objective={"w_distance": -1, "w_coverage": 1}), "the weights are numbers from 0"),
        (changed(keep=1), "keep: the share"),
        (changed(trials=1), "trials: at least 2"),
        (
            changed(
                trials=2, seeds=[{"lr": "0.001", "optimiser": "adamw", "schedule": "joint"}] * 3
            ),
            "no more seeds than trials",
        ),
        (changed(latency_crops=0), "latency_crops"),
        (changed(wandb_project=""), "wandb_project"),
    ],
)
def test_every_fault_of_a_plan_is_said_in_words(record, said):
    found = plan_problems(record)
    assert len(found) == 1 and said in found[0], found
    with pytest.raises((ViolationError, BeartypeCallHintParamViolation)):
        plan_of(record)


def test_the_split_is_the_rules_hash_and_a_row_lands_in_one_part_whatever_the_other_rows():
    text = b"schwingnet-split|autoanatomist-2026-10-29|ph03"
    assert hash_value("autoanatomist-2026-10-29", "ph03") == int.from_bytes(
        hashlib.sha256(text).digest()[:8], "big"
    )
    plan = a_plan()
    manifest = manifest_of(plan.rows, plan.split)
    assert [row["id"] for row in manifest] == [f"ph{n:02d}" for n in range(12)]
    assert {row["part"] for row in manifest} <= set(PARTS)
    assert manifest_of(plan.rows[2:5], plan.split) == manifest[2:5]
    for row in manifest:
        assert part_of(plan.split, row["id"]) == row["part"]
    assert sorted(
        part_ids(manifest, "train") + part_ids(manifest, "validation") + part_ids(manifest, "test")
    ) == sorted(row["id"] for row in manifest)
    wide = Split("autoanatomist-2026-10-29", 0.98, 0.01)
    assert {row["part"] for row in manifest_of(plan.rows, wide)} == {"validation"}
    assert manifest_problems(manifest_of(plan.rows, wide)) == [
        "the train part holds no row: more rows, or other shares, before any trial trains"
    ]
    assert manifest_problems(manifest) == []
    with pytest.raises(ViolationError):
        manifest_of([{"kind": "phantom"}], plan.split)


def test_the_halving_keeps_the_best_share_rounded_up_at_least_one_ties_by_id():
    assert kept({"a": 1.0, "b": 2.0, "c": 3.0, "d": 2.5}, 0.5) == ["c", "d"]
    assert kept({"a": 1.0, "b": 2.0, "c": 3.0}, 0.5) == ["b", "c"]
    assert kept({"b": 1.0, "a": 1.0, "c": 1.0}, 0.34) == ["a", "b"]
    assert kept({"only": -4.0}, 0.1) == ["only"]
    assert kept({}, 0.5) == []
    with pytest.raises(ViolationError):
        kept({"a": 1.0}, 1.0)
    with pytest.raises(ViolationError):
        kept({"a": math.nan}, 0.5)


def test_the_reward_counts_what_was_measured_and_notes_what_was_not():
    whole = measures_of({"distance_mm": 2.0, "named_right": 0.75, "coverage_at_1": 0.7, "step": 30})
    assert whole == Measures(0.75, 2.0, 0.7)
    objective = Objective(0.05, 1.0)
    assert reward(whole, objective, 0.68) == pytest.approx(0.75 - 0.1 - 0.02)
    assert measure_notes(whole) == []
    bare = measures_of({"distance_mm": 2, "named_right": None, "coverage_at_1": math.nan})
    assert bare == Measures(None, 2.0, None)
    assert measure_notes(bare) == [NO_NAMING, NO_COVERAGE]
    assert reward(bare, objective, 0.68) == pytest.approx(-0.1 - 0.68)
    none = measures_of({"named_right": 0.5})
    assert none.distance_mm is None and measure_notes(none)[0] == NO_DISTANCE
    with pytest.raises(ViolationError):
        reward(none, objective, 0.68)
    with pytest.raises(ViolationError):
        reward(Measures(None, 1e7, None), objective, 0.68)
    with pytest.raises(ViolationError):
        reward(whole, objective, 1.0)
    assert nominal_coverage_of(["calibrate=quantile", "coverage=0.9"]) == 0.9
    assert nominal_coverage_of(["calibrate=quantile"]) == 0.68
    assert nominal_coverage_of(["coverage=abc"]) == 0.68
    assert nominal_coverage_of(["coverage=1.5"], default=0.5) == 0.5
    with pytest.raises(ViolationError):
        nominal_coverage_of(["coverage"])


def test_the_policy_is_a_distribution_with_a_floor_under_every_value():
    assert uniform_policy(SPACE) == {
        "lr": [0.0, 0.0],
        "optimiser": [0.0, 0.0],
        "schedule": [0.0, 0.0],
    }
    assert probabilities([0.0, 0.0], 0.1) == [0.5, 0.5]
    skewed = probabilities([10.0, 0.0], 0.2)
    assert sum(skewed) == pytest.approx(1.0) and skewed[1] >= 0.1 and skewed[0] > skewed[1]
    assert probabilities([5.0], 0.0) == [1.0]
    with pytest.raises(ViolationError):
        probabilities([0.0, 0.0], 0.5)
    with pytest.raises(ViolationError):
        probabilities([], 0.1)
    assert policy_fits(uniform_policy(SPACE), SPACE)
    assert not policy_fits({"lr": [0.0, 0.0]}, SPACE)
    assert not policy_fits({**uniform_policy(SPACE), "lr": [0.0]}, SPACE)
    assert not policy_fits({**uniform_policy(SPACE), "lr": [0.0, math.inf]}, SPACE)


def test_a_round_drawn_twice_is_the_same_round_and_round_zero_begins_with_the_seeds():
    plan = a_plan()
    policy = uniform_policy(plan.space)
    drawn = sample(policy, plan, 3, 11)
    assert drawn == sample(policy, plan, 3, 11) and len(drawn) == 3
    assert all(
        [w.split("=")[0] for w in words] == ["lr", "optimiser", "schedule"] for words in drawn
    )
    assert all(w.split("=")[1] in plan.space[w.split("=")[0]] for words in drawn for w in words)
    assert sample(policy, plan, 0, 1) == []
    first = round_configurations(plan, policy, 0)
    assert len(first) == 4 and first[0] == ("lr=0.001", "optimiser=adamw", "schedule=joint")
    assert round_configurations(plan, policy, 0) == first
    later = round_configurations(plan, policy, 1)
    assert len(later) == 4 and later != first
    certain = {"lr": [0.0, 40.0], "optimiser": [40.0, 0.0], "schedule": [40.0, 0.0]}
    wanted = ("lr=0.003", "optimiser=adamw", "schedule=joint")
    draws = sample(certain, plan, 20, 3)
    assert 12 <= sum(words == wanted for words in draws) < 20, draws
    with pytest.raises(ViolationError):
        sample({"lr": [0.0, 0.0]}, plan, 1, 1)
    with pytest.raises(ViolationError):
        round_configurations(plan, policy, -1)


def test_a_reinforce_step_raises_the_chosen_value_and_lowers_the_rest_by_the_same_amount():
    plan = a_plan()
    policy = uniform_policy(plan.space)
    up = stepped(policy, plan, ["lr=0.003", "optimiser=adamw"], 2.0)
    assert up["lr"][1] > 0 > up["lr"][0] and up["lr"][1] == pytest.approx(-up["lr"][0])
    assert up["optimiser"][0] > 0 > up["optimiser"][1]
    assert up["schedule"] == [0.0, 0.0]
    assert up["lr"][1] == pytest.approx(0.5 * 2.0 * (1 - 0.5))
    down = stepped(policy, plan, ["lr=0.003"], -2.0)
    assert down["lr"][1] < 0 < down["lr"][0]
    assert stepped(policy, plan, ["lr=9", "noise"], 1.0) == policy
    with pytest.raises(ViolationError):
        stepped({"lr": [0.0, 0.0]}, plan, ["lr=0.003"], 1.0)


def test_the_controller_moves_the_baseline_toward_the_mean_and_the_first_round_sets_it():
    plan = a_plan()
    policy = uniform_policy(plan.space)
    pairs = [
        (("lr=0.003", "optimiser=sgd", "schedule=joint"), 1.0),
        (("lr=0.001", "optimiser=adamw", "schedule=fixed"), 0.0),
    ]
    first, baseline = updated(policy, plan, pairs, None)
    assert baseline == 0.5
    assert first["lr"][1] > first["lr"][0] and first["optimiser"][1] > first["optimiser"][0]
    second, moved = updated(first, plan, pairs, baseline)
    assert moved == pytest.approx(0.8 * 0.5 + 0.2 * 0.5)
    assert second["lr"][1] > first["lr"][1]
    assert updated(policy, plan, [], 0.3) == (policy, 0.3)
    with pytest.raises(ViolationError):
        updated(policy, plan, [(("lr=0.003",), 1e7)], None)


def test_a_trial_is_named_by_its_words_and_trains_the_rungs_differences():
    words = ["optimiser=sgd", "lr=0.003"]
    assert words_digest(words) == hashlib.sha256(b"lr=0.003\noptimiser=sgd\n").hexdigest()
    assert words_digest(words) == words_digest(list(reversed(words)))
    name = trial_id(0, 3, words)
    assert name == "r00t03_" + words_digest(words)[:8]
    assert trial_id(12, 0, words) != name
    with pytest.raises(ViolationError):
        trial_id(-1, 0, words)
    plan = a_plan()
    assert rung_steps(plan) == [10, 20, 60]
    assert trial_words(plan, words) == [
        "calibrate=quantile",
        "anneal=300",
        "optimiser=sgd",
        "lr=0.003",
    ]


def ledger_for(plan: Plan) -> dict[str, Any]:
    manifest = manifest_of(plan.rows, plan.split)
    return new_ledger(plan, "a" * 64, manifest)


def test_the_ledger_begins_empty_holds_and_is_written_sorted():
    plan = a_plan()
    ledger = ledger_for(plan)
    assert ledger_problems(ledger) == []
    assert set(ledger) == set(LEDGER_KEYS) and ledger["version"] == LEDGER_VERSION
    assert ledger["policy"] == uniform_policy(plan.space) and ledger["baseline"] is None
    assert ledger["trials"] == {} and ledger["rounds"] == [] and ledger["best"] is None
    assert json.loads(json.dumps(ledger)) == ledger
    assert ledger_fits(ledger, plan, "a" * 64) == []
    assert ledger_fits(ledger, plan, "b" * 64) == [
        "the ledger was begun under the plan of sha256 aaaaaaaaaaaaaaaa, "
        "and this plan's is bbbbbbbbbbbbbbbb"
    ]
    other = plan_of(changed(search="other", space={"lr": ["a", "b"]}, fixed=[], seeds=[]))
    assert ledger_fits(ledger, other, "a" * 64) == [
        "the ledger is the search phantom_smoke's, and the plan is other",
        "the ledger's policy is over other blocks or values than the plan's space",
    ]


@pytest.mark.parametrize(
    "change, said",
    [
        (lambda led: "ledger", "a ledger is a JSON object"),
        (lambda led: {**led, "version": 2}, "the ledger's version is 2; this code reads 1"),
        (lambda led: {k: v for k, v in led.items() if k != "runs"}, "the ledger lacks runs"),
        (lambda led: {**led, "search": "No"}, "the ledger's search is no id"),
        (lambda led: {**led, "plan_sha256": 1}, "its plan's sha256 no string"),
        (
            lambda led: {**led, "manifest": [{"id": "x", "part": "spare"}]},
            "the ledger's manifest is a list of rows",
        ),
        (
            lambda led: {**led, "policy": {"lr": [0.0, "x"]}},
            "the ledger's policy is one list of finite logits",
        ),
        (lambda led: {**led, "baseline": math.nan}, "the ledger's baseline is a finite number"),
        (lambda led: {**led, "trials": []}, "the ledger's trials are a mapping by id"),
        (lambda led: {**led, "rounds": "none"}, "its rounds and runs lists"),
        (lambda led: {**led, "best": "r00t00"}, "the ledger's best is a record"),
    ],
)
def test_every_fault_of_a_ledger_is_said_in_words(change, said):
    plan = a_plan()
    broken = change(ledger_for(plan))
    found = ledger_problems(broken)
    assert len(found) == 1 and said in found[0], found
    if isinstance(broken, dict):
        assert len(summary_lines(broken)) >= 2


def rung(steps: int, value: float) -> dict[str, Any]:
    return {
        "steps": steps,
        "reward": value,
        "distance_mm": 2.0,
        "named_right": 0.5,
        "coverage_at_1": 0.7,
        "sigma_mm": 1.0,
    }


def trial(words: list[str], rungs: list[dict[str, Any]]) -> dict[str, Any]:
    return {"words": words, "round": 0, "rungs": rungs, "latency_ms": 3.5, "seconds": 12.0}


def test_the_best_trial_is_the_highest_last_rung_reward_ties_by_id_and_the_summary_reads():
    trials = {
        "r00t02_x": trial(["lr=0.003"], [rung(10, 0.1), rung(30, 0.9)]),
        "r00t01_y": trial(["lr=0.001"], [rung(10, 0.9)]),
        "r00t03_z": trial(["lr=0.001"], []),
    }
    assert last_rewards(trials) == {"r00t02_x": 0.9, "r00t01_y": 0.9}
    assert best_trial(last_rewards(trials)) == "r00t01_y"
    assert best_trial(last_rewards({"r00t03_z": trial([], [])})) is None
    assert best_trial({}) is None
    with pytest.raises(ViolationError):
        best_trial({"a": math.nan})
    assert ledger_fits({"search": "phantom_smoke"}, a_plan(), "a" * 64) == [
        "the ledger was begun under the plan of sha256 None, and this plan's is aaaaaaaaaaaaaaaa",
        "the ledger's policy is over other blocks or values than the plan's space",
    ]
    plan = a_plan()
    ledger = ledger_for(plan)
    assert (
        summary_lines(ledger)[0] == "search phantom_smoke: 0 rounds, 0 trials, 0 with a rung scored"
    )
    assert summary_lines(ledger)[1].startswith("parts: train ")
    ledger["trials"] = trials
    ledger["rounds"] = [
        {"number": 0, "run": "r1", "trials": sorted(trials), "kept": [], "mean_reward": 0.5}
    ]
    ledger["best"] = {
        "id": "r00t02_x",
        "reward": 0.9,
        "words": ["lr=0.003"],
        "test": {"distance_mm": 1.5, "named_right": None, "coverage_at_1": 0.66},
        "test_rows": 2,
        "run": "r1",
    }
    lines = summary_lines(ledger)
    assert lines[0] == "search phantom_smoke: 1 rounds, 3 trials, 2 with a rung scored"
    assert lines[2] == "best r00t02_x: validation reward 0.9000, blocks lr=0.003"
    assert lines[3] == "test (2 rows): coverage_at_1 0.660, distance_mm 1.500, named_right none"
    ledger["best"]["test"] = None
    assert (
        summary_lines(ledger)[3]
        == "test: no row in the test part, so nothing was read for r00t02_x"
    )
    assert ledger_problems(ledger) == []
    assert summary_lines({"search": 3, "best": {"reward": "x", "test": "y"}}) == [
        "search 3: 0 rounds, 0 trials, 0 with a rung scored",
        "parts: train 0, validation 0, test 0",
        "best None: validation reward 'x', blocks none",
    ]


def test_the_plan_keys_are_the_ones_the_file_lists():
    assert set(PLAN_KEYS) == set(plan_record())
