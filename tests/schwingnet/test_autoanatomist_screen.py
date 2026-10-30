"""The auto-anatomist's screen as pure logic: a plan is read one way or refused in words, its rows
keep to the frozen split and never hold a test person, an epoch is the training columns over the
batch rounded up, the trials are every arm at every seed in one order, an entry is checked whole,
and an arm beats the null only when every one of its seeds ends below every one of the null's."""

import collections
import copy
import dataclasses
import hashlib
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from beartype.roar import BeartypeCallHintParamViolation
from icontract import ViolationError

from schwingnet.autoanatomist_screen import (
    ENTRY_KEYS,
    ENTRY_VERSION,
    NAMES,
    PINS,
    SCREEN_KEYS,
    TEST_LISTS,
    UNIT_LISTS,
    Plan,
    decide,
    entry_problems,
    evaluation_epochs,
    plan_of,
    plan_problems,
    rows_problems,
    rule_part,
    steps_per_epoch,
    task_problems,
    total_steps,
    train_count,
    trial_id,
    trials,
    unit_problems,
)

ROOT = Path(__file__).resolve().parents[2]
RULE = json.loads((ROOT / "data/splits/rule.json").read_text(encoding="utf-8"))
SALT, SHARE = RULE["salt"], RULE["validation_share"]
NO_TEST: frozenset[str] = frozenset()


def rule_hash_part(person: str) -> str:
    """The rule file's own words, computed here apart from the module: the first 8 bytes,
    big-endian, of sha256 over 'schwingnet-split|' + salt + '|' + person."""
    digest = hashlib.sha256(f"schwingnet-split|{SALT}|{person}".encode()).digest()
    return "validation" if int.from_bytes(digest[:8], "big") < SHARE * 2**64 else "train"


def persons_in(part: str, count: int) -> list[str]:
    """The first persons of the form enhance_pet:NNNN the rule puts in a part."""
    found = []
    for number in range(1, 10000):
        person = f"enhance_pet:{number:04d}"
        if rule_hash_part(person) == part:
            found.append(person)
        if len(found) == count:
            return found
    raise AssertionError(f"fewer than {count} persons in {part}")


TRAIN = persons_in("train", 5)
VALIDATION = persons_in("validation", 2)


def good_plan() -> dict[str, Any]:
    rows = [{"item": p, "person": p, "part": "train", "source": "enhance"} for p in TRAIN]
    rows += [
        {"item": p, "person": p, "part": "validation", "source": "enhance"} for p in VALIDATION
    ]
    names = {str(label): name for label, name in zip(range(3, 26), NAMES[:23], strict=True)}
    return {
        "screen": "gold3_test_screen",
        "purpose": "Whether an anneal beats none.",
        "class": "gpu",
        "layout": "array",
        "data": {
            "enhance": {
                "ct": "aws_enhance_pet_ct/raw",
                "labels": "aws_enhance_pet_labels/raw",
                "labels_folder": "Vertebrae",
                "names": names,
            }
        },
        "rows": rows,
        "split": {"salt": SALT, "validation_share": SHARE},
        "test": "off",
        "fixed": ["objective=mask", "naming=off"],
        "arms": {
            "joint": ["schedule=joint"],
            "lambda_then_w": ["schedule=lambda-then-w"],
            "null": ["schedule=fixed", "lam_fixed=1", "w_fixed=0"],
        },
        "null": "null",
        "seeds": [2, 1],
        "epochs": 3,
        "evaluate_every": 2,
        "batch": 2,
        "measure": "distance_mm",
    }


def changed(path: tuple[Any, ...], value: Any) -> dict[str, Any]:
    record = good_plan()
    target: Any = record
    for key in path[:-1]:
        target = target[key]
    if value is DELETE:
        del target[path[-1]]
    else:
        target[path[-1]] = value
    return record


DELETE = object()


def test_a_plan_that_holds_is_read_whole_and_typed() -> None:
    record = good_plan()
    assert plan_problems(record) == []
    plan = plan_of(record)
    assert isinstance(plan, Plan)
    assert plan.screen == "gold3_test_screen" and plan.job_class == "gpu" and plan.layout == "array"
    assert (
        plan.seeds == (2, 1) and plan.epochs == 3 and plan.batch == 2 and plan.evaluate_every == 2
    )
    assert plan.arms["null"] == ("schedule=fixed", "lam_fixed=1", "w_fixed=0")
    assert len(plan.rows) == 7 and train_count(plan) == 5
    assert rows_problems(record, SALT, SHARE, NO_TEST) == []


FAULTS = [
    ([], "a plan is a JSON object"),
    (changed(("screen",), DELETE), "missing screen"),
    (dict(good_plan(), extra=1), "unknown extra"),
    (changed(("screen",), "Gold-3"), "screen:"),
    (changed(("purpose",), "  "), "purpose:"),
    (changed(("class",), "cpu"), "class:"),
    (changed(("layout",), "grid"), "layout:"),
    (changed(("test",), "on"), "never the test part"),
    (changed(("measure",), "dice"), "measure:"),
    (changed(("data",), {}), "data: one entry a source"),
    (changed(("data", "enhance", "ct"), "/rs/data"), "a folder under the data root"),
    (changed(("data", "enhance", "labels"), "a/../b"), "a folder under the data root"),
    (changed(("data", "enhance", "labels_folder"), "a/b"), "one folder's name"),
    (changed(("data", "enhance", "names"), {}), "names map each label"),
    (changed(("data", "enhance", "names"), {"03": "C3"}), "whole numbers from 1"),
    (changed(("data", "enhance", "names"), {"2": "C2"}), "the name head lacks"),
    (changed(("data", "enhance", "names"), {"3": "C3", "4": "C3"}), "one level name to two labels"),
    (changed(("data", "enhance", "extra"), 1), "and nothing else"),
    (changed(("rows",), []), "rows: from 2"),
    (changed(("rows", 0, "extra"), 1), "a row holds"),
    (changed(("rows", 0, "item"), "Not An Item"), "as the gold 3 store spells them"),
    (changed(("rows", 1, "item"), TRAIN[0]), "listed twice"),
    (changed(("rows", 0, "part"), "test"), "a screen holds no test row"),
    (changed(("rows", 0, "source"), "verse"), "has no entry under data"),
    (changed(("split",), {"salt": SALT}), "split:"),
    (changed(("split", "salt"), ""), "salt is a string"),
    (changed(("split", "validation_share"), 1), "validation_share"),
    (changed(("fixed",), "objective=mask"), "fixed: a list"),
    (changed(("fixed",), ["objective mask"]), "no KEY=VALUE word"),
    (changed(("fixed",), ["seed=3"]), "set by the plan itself"),
    (changed(("fixed",), ["naming=off", "naming=on"]), "a key is given twice"),
    (changed(("arms",), {"null": ["schedule=fixed"]}), "arms: from 2"),
    (changed(("arms", "Joint"), ["schedule=w-first"]), "an arm's name"),
    (changed(("arms", "joint"), ["anneal=10"]), "set by the plan itself"),
    (
        changed(("arms", "joint"), ["schedule=joint", "objective=landmarks"]),
        "which the fixed words set already",
    ),
    (changed(("arms", "joint"), ["schedule=lambda-then-w"]), "two arms train under the same words"),
    (changed(("null",), "none"), "null:"),
    (changed(("seeds",), []), "seeds: from 1"),
    (changed(("seeds",), [1, 1]), "distinct whole numbers"),
    (changed(("seeds",), [-1]), "distinct whole numbers"),
    (changed(("seeds",), [True]), "distinct whole numbers"),
    (changed(("epochs",), 0), "epochs:"),
    (changed(("epochs",), 1001), "epochs:"),
    (changed(("evaluate_every",), DELETE), "missing evaluate_every"),
    (changed(("evaluate_every",), 0), "evaluate_every:"),
    (changed(("evaluate_every",), 4), "evaluate_every:"),
    (changed(("evaluate_every",), True), "evaluate_every:"),
    (changed(("batch",), 0), "batch:"),
]


def only_train_rows() -> dict[str, Any]:
    record = good_plan()
    record["rows"] = [row for row in record["rows"] if row["part"] == "train"]
    return record


@pytest.mark.parametrize("record,said", FAULTS + [(only_train_rows(), "one validation row")])
def test_every_fault_of_a_plan_is_said_in_words(record: Any, said: str) -> None:
    found = plan_problems(record)
    assert found and said in found[0], found


def test_the_split_is_the_rule_files_hash_and_the_test_list_wins() -> None:
    for person in TRAIN + VALIDATION + [f"verse:{n}" for n in range(50)]:
        assert rule_part(SALT, SHARE, NO_TEST, person) == rule_hash_part(person)
    assert rule_part(SALT, SHARE, frozenset({TRAIN[0]}), TRAIN[0]) == "test"


def test_a_row_off_the_frozen_split_or_on_the_test_list_is_refused() -> None:
    record = good_plan()
    assert "on a test list" in rows_problems(record, SALT, SHARE, frozenset({VALIDATION[1]}))[0]
    moved = copy.deepcopy(record)
    moved["rows"][0]["part"] = "validation"
    assert "the rule puts" in rows_problems(moved, SALT, SHARE, NO_TEST)[0]
    assert "the rule" in rows_problems(record, "another-salt", SHARE, NO_TEST)[0]
    assert "the rule" in rows_problems(record, SALT, 0.2, NO_TEST)[0]
    # the trial reads a row's files by its item, so an item on a test list is refused under any person
    swapped = copy.deepcopy(record)
    swapped["rows"][0]["item"] = "enhance_pet:7777"
    found = rows_problems(swapped, SALT, SHARE, frozenset({"enhance_pet:7777"}))
    assert found == ["rows: enhance_pet:7777 is itself on a test list, whatever person the row names"]


def test_a_study_outside_its_units_part_is_refused_and_one_inside_or_in_no_unit_is_not() -> None:
    record = good_plan()
    rows = record["rows"]
    trained = rows[0]["person"]
    assert rows[0]["part"] == "train"
    # a unit keyed by a training person keeps its studies in training
    units = {TRAIN[4]: (TRAIN[4], trained)}
    assert unit_problems(rows, units, SALT, SHARE, NO_TEST) == []
    # keyed by a validation person, the same study sits outside its unit's part
    units = {VALIDATION[0]: (VALIDATION[0], trained)}
    found = unit_problems(rows, units, SALT, SHARE, NO_TEST)
    assert found and f"{trained} is in the unit {VALIDATION[0]}, whose part is validation" in found[0]
    # a row in no unit is the rule's alone
    assert unit_problems(rows, {"enhance_pet:9999": ("enhance_pet:9999",)}, SALT, SHARE, NO_TEST) == []
    # units that do not hold together leave a person's part to whichever came last, so they are refused first
    found = unit_problems(rows, {TRAIN[4]: (TRAIN[3], trained)}, SALT, SHARE, NO_TEST)
    assert found == [f"units: the unit {TRAIN[4]} does not hold its own key"]
    found = unit_problems(rows, {TRAIN[4]: (TRAIN[4], trained), VALIDATION[0]: (VALIDATION[0], trained)}, SALT, SHARE, NO_TEST)
    assert found == [f"units: {trained} is in two units, {TRAIN[4]} and {VALIDATION[0]}"]
    # a unit holding a held-back study beside others would let its repeat scans train
    listed = frozenset({"enhance_pet:9999"})
    found = unit_problems(rows, {TRAIN[4]: (TRAIN[4], "enhance_pet:9999")}, SALT, SHARE, listed)
    assert found == [f"units: the unit {TRAIN[4]} holds enhance_pet:9999 of a test list beside studies of none"]
    assert unit_problems(rows, {"enhance_pet:9999": ("enhance_pet:9999",)}, SALT, SHARE, listed) == []
    with pytest.raises(ViolationError):
        unit_problems(rows, {}, SALT, 1.0, NO_TEST)


def test_the_unit_lists_hold_disjoint_units_each_keyed_by_one_of_its_studies() -> None:
    seen: set[str] = set()
    for path in UNIT_LISTS:
        units = json.loads((ROOT / path).read_text(encoding="utf-8"))
        assert isinstance(units, list) and units
        for unit in units:
            assert {"unit", "persons", "outside_export", "why"} <= set(unit)
            assert unit["unit"] in unit["persons"] and len(unit["persons"]) >= 2
            assert not seen & set(unit["persons"]), unit["unit"]
            seen |= set(unit["persons"])


def test_an_epoch_is_the_training_columns_over_the_batch_rounded_up() -> None:
    assert [steps_per_epoch(n, 2) for n in (0, 1, 2, 3, 96)] == [0, 1, 1, 2, 48]
    plan = plan_of(good_plan())
    assert total_steps(plan) == 3 * 3


def test_the_trials_are_every_arm_at_every_seed_in_one_order_with_the_anneal_spanning_the_run() -> (
    None
):
    plan = plan_of(good_plan())
    found = trials(plan)
    assert [t.id for t in found] == [
        "joint_s1",
        "joint_s2",
        "lambda_then_w_s1",
        "lambda_then_w_s2",
        "null_s1",
        "null_s2",
    ]
    first = found[0]
    assert first.id == trial_id("joint", 1) and first.arm == "joint" and first.seed == 1
    assert first.words == (
        "objective=mask",
        "naming=off",
        "schedule=joint",
        "seed=1",
        "batch=2",
        "anneal=9",
    )
    assert task_problems(plan, 0, 6) == [] and task_problems(plan, 5, 6) == []
    assert "6 trials" in task_problems(plan, 0, 8)[0]
    assert "outside" in task_problems(plan, 6, 6)[0]


def reading(epoch: int, distance: float | None) -> dict[str, Any]:
    """One evaluation point as a trial writes it: three steps an epoch for five training rows at
    two a step."""
    return {
        "epoch": epoch,
        "steps": 3 * epoch,
        "loss": 1.0 / epoch,
        "dice": 0.5,
        "distance_mm": distance,
        "surface_missing": 1,
        "centroid_mm": 2.5,
        "name_accuracy": None,
    }


def good_entry(trial: Any, distance: float | None = 5.0) -> dict[str, Any]:
    points = [reading(e, distance) for e in (2, 3)]
    return {
        "version": ENTRY_VERSION,
        "screen": "gold3_test_screen",
        "trial": trial.id,
        "arm": trial.arm,
        "seed": trial.seed,
        "words": list(trial.words),
        "steps": 9,
        "epochs": points,
        "final": {key: points[-1][key] for key in FINAL},
        "seconds": 12.5,
        "seconds_per_crop": 0.01,
        "train_rows": 5,
        "validation_rows": 2,
    }


FINAL = ("dice", "distance_mm", "surface_missing", "centroid_mm", "name_accuracy")
ENTRY_FAULTS = {
    "an entry holds": lambda e: e.pop("final"),
    "of version": lambda e: e.update(version=2),
    "the trial 'null_s1'": lambda e: e.update(trial="null_s1"),
    "other words": lambda e: e.update(words=["objective=mask"]),
    "steps is the plan's 9": lambda e: e.update(steps=8),
    "other rows than the plan's": lambda e: e.update(train_rows=4),
    "seconds is": lambda e: e.update(seconds=-1.0),
    "a reading after each of epochs 2, 3": lambda e: e["epochs"].pop(0),
    "names epoch 5 at 6 steps": lambda e: e["epochs"][0].update(epoch=5),
    "not epoch 3 at 9": lambda e: e["epochs"][1].update(steps=8),
    "no number and no null": lambda e: e["epochs"][0].update(dice=math.nan),
    "loss of epoch 2 is not a finite number, so the trial diverged": lambda e: e["epochs"][0].update(loss=None),
    "measure no number": lambda e: e["epochs"][1].update(surface_missing=-1),
    "holds epoch, steps": lambda e: e["epochs"][1].pop("centroid_mm"),
    "not the reading after the last epoch": lambda e: e["final"].update(dice=0.75),
    "final holds": lambda e: e["final"].pop("dice"),
}


@pytest.mark.parametrize("said,change", list(ENTRY_FAULTS.items()))
def test_every_fault_of_an_entry_is_said_in_words(said: str, change: Any) -> None:
    plan = plan_of(good_plan())
    trial = trials(plan)[0]
    entry = good_entry(trial)
    change(entry)
    found = entry_problems(entry, trial, plan)
    assert found and said in found[0], (said, found)


def test_an_entry_that_holds_is_read_and_one_of_another_screen_is_not() -> None:
    plan = plan_of(good_plan())
    trial = trials(plan)[0]
    assert entry_problems(good_entry(trial), trial, plan) == []
    assert set(good_entry(trial)) == set(ENTRY_KEYS)
    other = plan_of(changed(("screen",), "another"))
    assert "for the screen another" in entry_problems(good_entry(trial), trial, other)[0]


def test_an_entry_is_taken_only_in_the_plain_types_json_gives() -> None:
    plan = plan_of(good_plan())
    trial = trials(plan)[0]
    ordered = collections.OrderedDict(good_entry(trial))
    assert "an entry holds" in entry_problems(ordered, trial, plan)[0]
    entry = good_entry(trial)
    entry["epochs"] = tuple(entry["epochs"])
    assert "a reading after each of epochs" in entry_problems(entry, trial, plan)[0]
    entry = good_entry(trial)
    entry["final"] = collections.OrderedDict(entry["final"])
    assert "final holds" in entry_problems(entry, trial, plan)[0]


def test_a_trial_reads_every_few_epochs_and_always_after_the_last() -> None:
    assert evaluation_epochs(plan_of(good_plan())) == [2, 3]
    assert evaluation_epochs(plan_of(changed(("evaluate_every",), 1))) == [1, 2, 3]
    assert evaluation_epochs(plan_of(changed(("evaluate_every",), 3))) == [3]
    long_plan = good_plan()
    long_plan.update(epochs=50, evaluate_every=5)
    assert evaluation_epochs(plan_of(long_plan)) == list(range(5, 51, 5))
    long_plan.update(evaluate_every=7)
    assert evaluation_epochs(plan_of(long_plan)) == [7, 14, 21, 28, 35, 42, 49, 50]


def entries_with(values: dict[str, float | None]) -> dict[str, Any]:
    plan = plan_of(good_plan())
    return {t.id: good_entry(t, values[t.id]) for t in trials(plan) if t.id in values}


def test_an_arm_beats_the_null_only_when_every_seed_ends_below_every_null_seed() -> None:
    plan = plan_of(good_plan())
    values: dict[str, float | None] = {
        "joint_s1": 3.0,
        "joint_s2": 3.9,
        "lambda_then_w_s1": 2.0,
        "lambda_then_w_s2": 4.0,
        "null_s1": 4.0,
        "null_s2": 4.5,
    }
    decision = decide(plan, entries_with(values))
    arms: Any = decision["arms"]
    assert set(arms) == {"joint", "lambda_then_w"}
    assert arms["joint"]["beats_null"] is True
    assert arms["lambda_then_w"]["beats_null"] is False  # 4.0 is not below 4.0
    assert decision["null_finals"] == [4.0, 4.5] and decision["seeds"] == [1, 2]
    reordered = dict(reversed(list(entries_with(values).items())))
    assert decide(plan, reordered) == decision


def test_a_failed_trial_decides_nothing_for_its_arm_or_against_the_null() -> None:
    plan = plan_of(good_plan())
    values: dict[str, float | None] = {
        "joint_s1": 3.0,
        "lambda_then_w_s1": 2.0,
        "lambda_then_w_s2": 2.5,
        "null_s1": 4.0,
        "null_s2": 4.5,
    }
    arms: Any = decide(plan, entries_with(values))["arms"]
    assert arms["joint"]["beats_null"] is None and "nothing is decided" in arms["joint"]["why"]
    assert arms["lambda_then_w"]["beats_null"] is True
    values["null_s2"] = None
    arms = decide(plan, entries_with(values))["arms"]
    assert arms["lambda_then_w"]["beats_null"] is None


def test_the_contracts_refuse_a_plan_that_does_not_hold_and_a_value_of_the_wrong_type() -> None:
    with pytest.raises(ViolationError):
        plan_of(changed(("null",), "none"))
    text: Any = "3"
    with pytest.raises(BeartypeCallHintParamViolation):
        steps_per_epoch(text, 2)
    with pytest.raises(ViolationError):
        steps_per_epoch(-1, 2)
    with pytest.raises(ViolationError):
        steps_per_epoch(3, 0)
    # a seed twice would name its trials twice; plan_problems refuses such a plan before it is one
    twice = dataclasses.replace(plan_of(good_plan()), seeds=(1, 1))
    with pytest.raises(ViolationError):
        trials(twice)
    with pytest.raises(ViolationError):
        decide(twice, {})


def test_the_plan_keys_and_the_names_are_the_ones_the_module_lists() -> None:
    assert set(good_plan()) == set(SCREEN_KEYS)
    assert NAMES[:5] == ("C3", "C4", "C5", "C6", "C7") and NAMES[-3:] == ("L5", "L6", "T13")
    assert len(NAMES) == 24


def test_the_pins_name_one_version_each_and_the_test_lists_are_the_repositorys() -> None:
    names = [pin.split("==")[0].split("[")[0] for pin in PINS]
    assert all(pin.count("==") == 1 and pin.split("==")[1] for pin in PINS)
    assert len(set(names)) == len(names) and {"jax", "flax", "optax", "nibabel"} <= set(names)
    assert "data/splits/latent-prior-test-reserve.json" in TEST_LISTS
    for path in TEST_LISTS:
        persons = json.loads((ROOT / path).read_text(encoding="utf-8"))
        assert isinstance(persons, list) and all("person" in entry for entry in persons)


# --- the committed plans (tools/autoanatomist_plan.py check) -----------------------------------


def plan_check(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(root / "tools" / "autoanatomist_plan.py"), "check"],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def test_the_committed_plans_hold_and_stay_inside_the_frozen_split() -> None:
    done = plan_check(ROOT)
    assert done.returncode == 0, done.stdout + done.stderr


def test_a_planned_person_put_on_a_test_list_fails_the_plan_check(tmp_path: Path) -> None:
    (tmp_path / "tools").mkdir()
    shutil.copy(ROOT / "tools" / "autoanatomist_plan.py", tmp_path / "tools")
    # The package and its contracts are read where they are; the split and the plans are copies.
    for name in ("src", "vendor"):
        (tmp_path / name).symlink_to(ROOT / name, target_is_directory=True)
    for name in ("data/splits", "grid/screens"):
        shutil.copytree(ROOT / name, tmp_path / name)
    assert plan_check(tmp_path).returncode == 0
    smoke = tmp_path / "grid" / "screens" / "gold3_latent_smoke.json"
    person = json.loads(smoke.read_text(encoding="utf-8"))["rows"][0]["person"]
    listed = tmp_path / "data" / "splits" / "test-persons.json"
    entries = json.loads(listed.read_text(encoding="utf-8"))
    entries.append({"person": person, "why": "a test of the check"})
    listed.write_text(json.dumps(entries, indent=1) + "\n", encoding="utf-8")
    done = plan_check(tmp_path)
    assert done.returncode == 1, done.stdout + done.stderr
    assert "grid/screens/gold3_latent_smoke.json" in done.stdout
    assert "grid/screens/gold3_latent_screen.json" in done.stdout


def test_a_planned_study_put_in_a_unit_of_the_other_part_fails_the_plan_check(tmp_path: Path) -> None:
    (tmp_path / "tools").mkdir()
    shutil.copy(ROOT / "tools" / "autoanatomist_plan.py", tmp_path / "tools")
    for name in ("src", "vendor"):
        (tmp_path / name).symlink_to(ROOT / name, target_is_directory=True)
    for name in ("data/splits", "grid/screens"):
        shutil.copytree(ROOT / name, tmp_path / name)
    groups = tmp_path / UNIT_LISTS[0]
    units = json.loads(groups.read_text(encoding="utf-8"))
    in_units = {person for unit in units for person in unit["persons"]}
    tested = {entry["person"] for path in TEST_LISTS for entry in json.loads((ROOT / path).read_text(encoding="utf-8"))}
    smoke = tmp_path / "grid" / "screens" / "gold3_latent_smoke.json"
    # a smoke row in no unit yet, whose part the new unit's key, a person of the other part in no unit
    # and on no test list, contradicts; the smoke's rows are the screen's first, so it stands in both plans
    row = next(r for r in json.loads(smoke.read_text(encoding="utf-8"))["rows"] if r["person"] not in in_units)
    key = next(p for p in persons_in("validation" if row["part"] == "train" else "train", 40)
               if p not in in_units and p not in tested)
    units.append({"unit": key, "persons": [key, row["person"]], "outside_export": [], "why": "a test"})
    groups.write_text(json.dumps(units, indent=1) + "\n", encoding="utf-8")
    done = plan_check(tmp_path)
    assert done.returncode == 1, done.stdout + done.stderr
    assert f"is in the unit {key}" in done.stdout
    assert "grid/screens/gold3_latent_smoke.json" in done.stdout
    assert "grid/screens/gold3_latent_screen.json" in done.stdout
