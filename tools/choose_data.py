"""Choose the datasets for training and a powered fluoroscopy test of normal spines, the same way every time.

Source: the thread "Fit datasets under the 20 TB cap", 2026-10-25, the owner's ask of 04:14 UTC: "what id
like ultimately is an automated process, deterministic if possible, for choosing datasets to use to both
train a network and be able to test it with sufficient power on normal spines, in the fluoroscopic domain"
(#291). The reasoning behind each rule is docs/research/dataset-chooser.md, and the evidence behind the
rules is docs/research/final-dataset-recipe.md.

The inputs are the records under data/sources/, the licence classes in data/licences.json, one recipe
under data/recipes/, the frozen persons in data/splits/test-persons.json and the owner's settings in
data/choice/settings.json. The output, data/choice/CHOICE.json, carries the sha256 of every input, so the
same inputs always give the same file and a changed input is seen.

    python3 tools/choose_data.py write    # write data/choice/CHOICE.json
    python3 tools/choose_data.py check    # the committed file is what the inputs give now
    python3 tools/choose_data.py show     # the choice in a few lines

The test is the held real fluoroscopy whose levels people read, by person: the frozen persons are left
out of it (the transitional stratum and the demo sweeps are tested on their own), each set keeps the
settings' number of persons per device for training, since a device's first ten to twelve frames reach
95 percent of the plateau (state-of-knowledge.md row 4), and the rest is test. The people the test needs
are the least n whose Wilson interval at the expected accuracy is no wider than the half-width. Training
is every other held set whose licence the recipe allows, with the role its record gives it. Standard
library only, so it runs wherever the repository is checked out.
"""
import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from statistics import NormalDist

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "data" / "sources"
LICENCES = ROOT / "data" / "licences.json"
RECIPES = ROOT / "data" / "recipes"
TEST_PERSONS = ROOT / "data" / "splits" / "test-persons.json"
SETTINGS = ROOT / "data" / "choice" / "settings.json"
CHOICE = ROOT / "data" / "choice" / "CHOICE.json"

PEOPLE_KEYS = ("patients", "subjects", "people", "persons", "cases", "specimens")
NO_TRUTH = re.compile(r"^(none|no levels|unknown|counted by|assumed|pseudo|almost never)", re.IGNORECASE)
PARTIAL = re.compile(r"^(partial|same$|whatever)|anchors", re.IGNORECASE)
LEVEL_WORDS = re.compile(r"\b(yes|exact|C[1-7]|T1[0-2]|T[1-9]|L[1-6]|S1|lumbar|thoracic|cervical|levels?|"
                         r"from the (source )?CT)\b", re.IGNORECASE)
REAL_FRAMES = ("fluoro", "video", "projections")
MOST_PEOPLE = 10 ** 6


class ChoiceError(Exception):
    pass


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ChoiceError(f"{path}: {error}") from error


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# Power.

def z_of(confidence):
    if not 0 < confidence < 1:
        raise ChoiceError("confidence is between 0 and 1")
    return NormalDist().inv_cdf((1 + confidence) / 2)


def wilson_half_width(n, p, z):
    """Half the width of the Wilson score interval for n people at an observed accuracy p."""
    return z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)


def people_needed(power):
    """The least n whose Wilson interval at the expected accuracy is no wider than the half-width."""
    p, h, z = power["expected_accuracy"], power["half_width"], z_of(power["confidence"])
    if not (0 <= p <= 1 and 0 < h < 0.5):
        raise ChoiceError("expected_accuracy is between 0 and 1, half_width between 0 and 0.5")
    low, high = 1, MOST_PEOPLE
    if wilson_half_width(high, p, z) > h:
        raise ChoiceError(f"no n up to {MOST_PEOPLE} reaches a half-width of {h}")
    while low < high:
        mid = (low + high) // 2
        if wilson_half_width(mid, p, z) <= h:
            high = mid
        else:
            low = mid + 1
    return low


def reached_half_width(n, power):
    if n <= 0:
        return None
    return round(wilson_half_width(n, power["expected_accuracy"], z_of(power["confidence"])), 4)


# What a record says.

def truth_of(text):
    """read where people named levels, partial where only some or an anchor, none otherwise."""
    text = (text or "").strip()
    if not text or NO_TRUTH.match(text):
        return "none"
    if PARTIAL.search(text):
        return "partial"
    return "read" if LEVEL_WORDS.search(text) else "none"


def people_of(record):
    counts = record.get("counts") if isinstance(record.get("counts"), dict) else {}
    for key in PEOPLE_KEYS:
        value = counts.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    return None


def licence_of(record_id, licences):
    key = licences.get("aliases", {}).get(record_id, record_id)
    return licences.get("sources", {}).get(key) or {"class": "unknown", "reviewed": "none"}


def allowed(entry, recipe):
    if entry["class"] not in recipe["allow"]:
        return False
    return not recipe["reviewed_only"] or str(entry.get("reviewed", "")).startswith("owner")


def frozen_by_source(test_persons):
    frozen = {}
    for entry in test_persons:
        source = str(entry.get("person", "")).split(":", 1)[0]
        frozen.setdefault(source, []).append(entry["person"])
    return frozen


# The choice.

def test_row(record, frozen, settings):
    people = people_of(record)
    out = sorted(frozen.get(record["id"], []))
    normal = None if people is None else max(people - len(out), 0)
    keep = settings["device_training_persons"]
    train = None if normal is None else min(keep, normal)
    return {"id": record["id"], "people": people, "frozen_out": len(out),
            "training_persons": train, "test_persons": None if normal is None else normal - train}


def training_role(record, truth):
    if record["group"] == "ct":
        return "render source: 3D level truth for synthetic frames" if truth != "none" else None
    if truth == "read":
        return "real device frames with levels" if record["group"] in REAL_FRAMES else "real films with levels"
    if truth == "partial":
        return "real frames with some levels or anchors"
    return "appearance: real frames with no levels"


def exclusion(record, entry, recipe, truth, never_train):
    if record.get("reach") != "held":
        return None
    if record["id"] in never_train:
        return f"never trained on: {never_train[record['id']]}"
    if not allowed(entry, recipe):
        if entry["class"] == "unknown":
            return "licence unknown: classify it in data/licences.json first"
        return f"licence class {entry['class']} is outside the recipe {recipe['name']}"
    if training_role(record, truth) is None:
        return "no level truth and no use as a render source"
    return None


def choose(records, licences, recipe, test_persons, settings):
    frozen = frozen_by_source(test_persons)
    needed = people_needed(settings["power"])
    tests, training, excluded, fill = [], [], [], []
    for record in sorted(records, key=lambda r: r["id"]):
        entry, truth = licence_of(record["id"], licences), truth_of(record.get("level_truth"))
        why_not = exclusion(record, entry, recipe, truth, settings.get("never_train", {}))
        held = record.get("reach") == "held"
        if held and why_not:
            excluded.append({"id": record["id"], "group": record["group"], "why": why_not})
            continue
        in_test_domain = record["group"] in settings["test_groups"] and truth == "read"
        if held and in_test_domain:
            row = test_row(record, frozen, settings)
            tests.append(dict(row, group=record["group"], licence=entry["class"]))
            if row["training_persons"] is None or row["training_persons"] > 0:
                training.append(_training_entry(record, entry, truth, row["training_persons"]))
        elif held:
            training.append(_training_entry(record, entry, truth, None))
        elif record["group"] in settings["fill_groups"] and people_of(record):
            fill.append({"id": record["id"], "group": record["group"], "reach": record.get("reach"),
                         "people": people_of(record), "licence": entry["class"],
                         "level_truth": record.get("level_truth", "")})
    total = sum(t["test_persons"] or 0 for t in tests)
    fill.sort(key=lambda f: (-f["people"], f["id"]))
    running = total
    for f in fill:
        running += f["people"]
        f["closes_the_gap"] = running >= needed
    return {
        "power": dict(settings["power"], z=round(z_of(settings["power"]["confidence"]), 6), people_needed=needed,
                      alternatives=alternatives(settings["power"])),
        "test": {"sources": tests, "test_persons": total, "shortfall": max(needed - total, 0),
                 "half_width_reached": reached_half_width(total, settings["power"]),
                 "uncounted": sorted(t["id"] for t in tests if t["people"] is None),
                 "assign": ("within each test source, the training persons are the ones whose sha256 of "
                            "'schwingnet-choice|' + salt + '|' + person sorts lowest, with the salt of "
                            "data/splits/rule.json; the rest are test; a frozen person is never either")},
        "fill": fill,
        "training": training,
        "excluded": excluded,
    }


def _training_entry(record, entry, truth, persons):
    row = {"id": record["id"], "group": record["group"], "level_truth": truth,
           "role": training_role(record, truth), "licence": entry["class"]}
    if persons is not None:
        row["persons"] = persons
    return row


def alternatives(power):
    """The people other expected accuracies and half-widths would need, beside the settings' own."""
    rows = []
    for p in (0.5, 0.9, 0.95):
        for h in (0.03, 0.05):
            rows.append({"expected_accuracy": p, "half_width": h,
                         "people_needed": people_needed(dict(power, expected_accuracy=p, half_width=h))})
    return rows


# Reading the inputs and writing the output.

def load_inputs(root=ROOT):
    root = Path(root)
    settings_path = root / "data" / "choice" / "settings.json"
    settings = read_json(settings_path)
    recipe_path = root / "data" / "recipes" / f"{settings['recipe']}.json"
    paths = {"settings": settings_path, "licences": root / "data" / "licences.json", "recipe": recipe_path,
             "test_persons": root / "data" / "splits" / "test-persons.json",
             "rule": root / "data" / "splits" / "rule.json"}
    record_paths = sorted((root / "data" / "sources").glob("*.json"))
    records = [read_json(path) for path in record_paths]
    digest = hashlib.sha256()
    for path in record_paths:
        digest.update(path.name.encode("utf-8") + b"\0" + Path(path).read_bytes() + b"\0")
    hashes = {name: sha256_of(path) for name, path in paths.items()}
    hashes["sources"] = digest.hexdigest()
    return records, read_json(paths["licences"]), read_json(recipe_path), read_json(paths["test_persons"]), settings, hashes


def build(root=ROOT):
    records, licences, recipe, test_persons, settings, hashes = load_inputs(root)
    result = choose(records, licences, recipe, test_persons, settings)
    return dict({"inputs": hashes, "recipe": settings["recipe"], "records": len(records)}, **result)


def render(choice):
    return json.dumps(choice, indent=1, sort_keys=True, ensure_ascii=True) + "\n"


def summary(choice):
    test, power = choice["test"], choice["power"]
    lines = [f"recipe {choice['recipe']}: {len(choice['training'])} training sets, {len(choice['excluded'])} held sets excluded",
             f"test: {test['test_persons']} normal-spine fluoroscopy persons from "
             f"{', '.join(t['id'] for t in test['sources']) or 'no set'}; {power['people_needed']} needed "
             f"(accuracy {power['expected_accuracy']}, half-width {power['half_width']}, confidence {power['confidence']})"]
    if test["shortfall"]:
        closing = next((f["id"] for f in choice["fill"] if f["closes_the_gap"]), None)
        lines.append(f"short by {test['shortfall']}; the half-width reached is {test['half_width_reached']}; "
                     f"filled in order of people, the gap closes at {closing or 'no listed set'}")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=("write", "check", "show"))
    args = parser.parse_args(argv)
    try:
        text = render(build())
    except (ChoiceError, KeyError) as error:
        print(f"choose_data: {error}", file=sys.stderr)
        return 2
    if args.action == "write":
        CHOICE.write_text(text, encoding="ascii", newline="\n")
    elif args.action == "check":
        if not CHOICE.exists() or CHOICE.read_text(encoding="ascii") != text:
            print("choose_data: data/choice/CHOICE.json is not what the inputs give; run "
                  "python3 tools/choose_data.py write and commit it", file=sys.stderr)
            return 1
    print(summary(json.loads(text)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
