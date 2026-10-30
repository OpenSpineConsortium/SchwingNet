#!/usr/bin/env python3
"""Write and check the auto-anatomist screen's plans under grid/screens/ from the gold 3 store
(docs/research/autoanatomist-screen/README.md).

    python3 tools/autoanatomist_plan.py write [--export FILE]
    python3 tools/autoanatomist_plan.py check

write takes the store's training rows (`tools/gold3_ct.py export --tier gold3 --training-only`, or
the file --export names), keeps ENHANCE.PET's rows of the normal class whose masks confirmed the
call, with no holdout and no CT still to fetch, leaves out every person on a test list
(schwingnet.autoanatomist_screen.TEST_LISTS) and every study of a unit of probable repeat scans
(UNIT_LISTS) whose own part is not the part of its unit's key, so no unit straddles training and
validation, checks each row's part against data/splits/rule.json, orders the persons by a hash of
their own under SUBSET_SALT and keeps the first of each part, so the smoke's rows are the screen's
first rows and a person's place never depends on the other rows. One label scheme for every row:
ENHANCE.PET's C3 to L6 masks, labels 3 to 25, named as the vendored name head names them. The
plans are frozen by docs/research/autoanatomist-screen/PREREG.md's Covers lines, so write is run
before the freeze and never after.

check reads the committed plans and fails where one does not hold (plan_problems), where a row
has left the frozen split or stands on a test list (rows_problems), or where a row sits outside its
unit's part (unit_problems), so a test list or a unit that grows to take a planned person stops the
check rather than the run. scripts/check.sh runs it where pixi
is, since it imports the package's contracts, and the gate lane runs it on every pull request
(tests/schwingnet/test_autoanatomist_screen.py).
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# As in tools/realism.py: this folder leaves the path, and the package and the pinned beethoven-qa
# its contracts come from join it.
sys.path[0] = str(ROOT / "src")
if str(ROOT / "vendor" / "beethoven-qa" / "src") not in sys.path:
    sys.path.insert(1, str(ROOT / "vendor" / "beethoven-qa" / "src"))

from schwingnet.autoanatomist_screen import (  # noqa: E402
    NAMES,
    TEST_LISTS,
    UNIT_LISTS,
    SplitRule,
    plan_problems,
    rows_problems,
    rule_part,
    unit_problems,
)
from schwingnet.autoanatomist_search import hash_value  # noqa: E402

RULE = "data/splits/rule.json"
SCREENS = "grid/screens"
SOURCE = "scidb_enhance_pet_1_6k"
DATA_KEY = "enhance_pet"
SUBSET_SALT = "schwingnet-autoanatomist-subset-2026-10-30"
ENHANCE_DATA = {
    "ct": "aws_enhance_pet_ct/raw",
    "labels": "aws_enhance_pet_labels/raw",
    "labels_folder": "Vertebrae",
    # ENHANCE.PET's scheme (tools/gold3_ct.py): C1 to C7 are 1 to 7, T1 to T12 8 to 19, L1 to L6 20
    # to 25; C1, C2, the hips and the sacrum are not names the name head knows, so they are left out.
    "names": {
        **{str(i): f"C{i}" for i in range(3, 8)},
        **{str(7 + i): f"T{i}" for i in range(1, 13)},
        **{str(19 + i): f"L{i}" for i in range(1, 7)},
    },
}
FIXED = ["objective=mask", "naming=off"]
SCHEDULES = {
    "lambda_then_w": ["schedule=lambda-then-w"],
    "joint": ["schedule=joint"],
    "w_first": ["schedule=w-first"],
    # The null is the CT branch alone. At w 0 the mask encoder takes no gradient and stays at its
    # random start, so the feature term would pull the CT encoder towards a random network's
    # features, a weight only the null would carry; w_feature=0 takes it out.
    "null": ["schedule=fixed", "lam_fixed=1", "w_fixed=0", "w_feature=0"],
}
PLANS = {
    "gold3_latent_smoke": {
        "purpose": (
            "The screen's code path on the grid, end to end on four CTs: two short trials in series on one "
            "card, an anneal and the null, then the join, timing the seconds a crop takes on a GPU for the "
            "screen's and the latent shape priors' costs. Nothing it measures is read as a result."
        ),
        "layout": "series",
        "train": 3,
        "validation": 1,
        "arms": ("lambda_then_w", "null"),
        "seeds": [1],
        "epochs": 150,
        "evaluate_every": 10,
    },
    "gold3_latent_screen": {
        "purpose": (
            "Whether the anneal helps the fully latent network name and outline real vertebrae: three anneal "
            "schedules against the null that never anneals and reads the CT alone from the first step, two "
            "seeds each, 50 epochs on 96 training CTs, read on 24 validation CTs by the mean surface distance."
        ),
        "layout": "array",
        "train": 96,
        "validation": 24,
        "arms": ("lambda_then_w", "joint", "w_first", "null"),
        "seeds": [1, 2],
        "epochs": 50,
        "evaluate_every": 5,
    },
}


def read_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def split_inputs():
    """The frozen rule with every person on a test list, and every unit of probable repeat scans,
    its key to its persons."""
    rule = read_json(RULE)
    persons = {entry["person"] for path in TEST_LISTS for entry in read_json(path)}
    entries = [entry for path in UNIT_LISTS for entry in read_json(path)]
    units = {entry["unit"]: tuple(entry["persons"]) for entry in entries}
    if len(units) != len(entries):
        # A key standing twice would leave the first unit's persons to the rule alone.
        raise SystemExit("autoanatomist_plan: a unit's key stands twice in " + ", ".join(UNIT_LISTS))
    return SplitRule(rule["salt"], float(rule["validation_share"]), frozenset(persons)), units


def unit_parts(rule, units):
    """Each study of a unit, to the part the rule gives its unit's key."""
    return {person: rule_part(rule, key) for key, persons in units.items() for person in persons}


def export_rows(export):
    """The store's gold 3 training rows, from the file named or from the store itself."""
    if export:
        text = Path(export).read_text(encoding="utf-8")
    else:
        command = [sys.executable, str(ROOT / "tools/gold3_ct.py"), "export", "--tier", "gold3",
                   "--training-only", "--format", "json"]
        text = subprocess.run(command, check=True, capture_output=True, text=True, cwd=ROOT).stdout
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def eligible(row, rule, unit_part):
    """A row the screen may take: ENHANCE.PET, normal, confirmed by its masks, trainable, no
    holdout, its CT in hand, off every test list, in the part the rule gives its person and, for a
    study of a unit of probable repeat scans, in its unit's part too."""
    keep = (row["source"] == SOURCE and row["tier"] == "gold3" and row["class"] == "normal"
            and row["status"] == "confirmed_by_masks" and row["training_allowed"] == 1
            and row["holdout"] == 0 and row["needs_ct"] == 0 and row["part"] in ("train", "validation"))
    part = rule_part(rule, row["person"])
    return (keep and row["person"] not in rule.test_persons and part == row["part"]
            and unit_part.get(row["person"], part) == part)


def chosen(rows, part, count):
    """The first count persons of a part by their own hash, one row a person."""
    order = sorted((r for r in rows if r["part"] == part), key=lambda r: (hash_value(SUBSET_SALT, r["person"]), r["item"]))
    picked, persons = [], set()
    for row in order:
        if row["person"] not in persons:
            picked.append(row)
            persons.add(row["person"])
        if len(picked) == count:
            return picked
    raise SystemExit(f"only {len(picked)} {part} persons are eligible, and the plan asks {count}")


def plan_record(screen, spec, rows, rule):
    taken = chosen(rows, "train", spec["train"]) + chosen(rows, "validation", spec["validation"])
    return {
        "screen": screen,
        "purpose": spec["purpose"],
        "class": "gpu",
        "layout": spec["layout"],
        "data": {DATA_KEY: ENHANCE_DATA},
        "rows": [{"item": r["item"], "person": r["person"], "part": r["part"], "source": DATA_KEY} for r in taken],
        "split": {"salt": rule.salt, "validation_share": rule.validation_share},
        "test": "off",
        "fixed": FIXED,
        "arms": {arm: SCHEDULES[arm] for arm in spec["arms"]},
        "null": "null",
        "seeds": spec["seeds"],
        "epochs": spec["epochs"],
        "evaluate_every": spec["evaluate_every"],
        "batch": 2,
        "measure": "distance_mm",
    }


def plan_text(record):
    return json.dumps(record, indent=2, ensure_ascii=True) + "\n"


def problems_of(record, rule, units):
    return plan_problems(record) or rows_problems(record, rule) or unit_problems(record["rows"], units, rule)


def command_write(args):
    rule, units = split_inputs()
    unit_part = unit_parts(rule, units)
    exported = export_rows(args.export)
    rows = [r for r in exported if eligible(r, rule, unit_part)]
    split_off = [r for r in exported if eligible(r, rule, {}) and r not in rows]
    print(f"{len(rows)} eligible rows ({sum(r['part'] == 'train' for r in rows)} train); {len(split_off)} left out "
          f"since their unit's part is not their own")
    assert set(ENHANCE_DATA["names"].values()) <= set(NAMES)
    for screen, spec in PLANS.items():
        record = plan_record(screen, spec, rows, rule)
        found = problems_of(record, rule, units)
        if found:
            raise SystemExit(f"{screen}: {found[0]}")
        path = ROOT / SCREENS / f"{screen}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(plan_text(record), encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}: {len(record['rows'])} rows of {len(rows)} eligible")
    return 0


def command_check(args):
    rule, units = split_inputs()
    failed = 0
    for screen in PLANS:
        path = ROOT / SCREENS / f"{screen}.json"
        if not path.is_file():
            print(f"autoanatomist_plan: {path.relative_to(ROOT)} is missing")
            failed += 1
            continue
        found = problems_of(json.loads(path.read_text(encoding="utf-8")), rule, units)
        for line in found:
            print(f"autoanatomist_plan: {path.relative_to(ROOT)}: {line}")
        failed += bool(found)
    return 1 if failed else 0


def main(argv=None):
    top = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = top.add_subparsers(dest="command", required=True)
    write = sub.add_parser("write", help="write the plans from the gold 3 store's training rows")
    write.add_argument("--export", help="a file of the store's export, JSON lines, in place of running it")
    sub.add_parser("check", help="exit 1 where a committed plan does not hold or leaves the frozen split")
    args = top.parse_args(argv)
    return {"write": command_write, "check": command_check}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
