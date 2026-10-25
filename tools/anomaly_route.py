"""The SPINEPS to FleXray anomaly route's clerk (#398): the frozen holdout, the CT finder's score, the selection.

Usage (standard library only; the grid runs it inside the container through grid/anomaly.sbatch):
    python tools/anomaly_route.py freeze --screen <verse screened.csv> --table <verse_suppl_table1.csv> --out data/splits/anomaly-holdout.json
    python tools/anomaly_route.py score --screen <verse screened.csv> [--holdout data/splits/anomaly-holdout.json]
    python tools/anomaly_route.py select --registry <registry.csv> --harvest <anomaly_harvest root> --holdout <file> --out <dir>
    python tools/anomaly_route.py check --holdout <file> --list <csv with a patient_key column>

docs/research/spineps-anomaly-route.md is the plan. The finder is two labellers agreeing on a CT:
SPINEPS with VERIDAH's names (labeller A) and TotalSegmentator's geometry (labeller B), as the
anomaly harvest wrote them (spinesurg-ct-nnunet tools/acquisition_screen.py and the VerSe census).
A lumbar count stands when A's count and B's rib-contact count are the same, a thoracic count when
A's count and B's rib-contact count from T1 are the same; a variant is called only from a count
both stand behind. VERIDAH alone is scored beside it, because the record shows it over-calls.

The truth is the readers' table (Loeffler 2021, Supplementary Table 1), as the screen file carries
it in read_structure, C/T/L/S. A scan whose review note says the release mask or labeller A
contradicts the read, that the release mask carries an L6 against a normal read (verse707), or
that the mask's ids are out of order, is disputed: it is neither scored nor held out nor trained.

The holdout is drawn by rank, the first 8 bytes of sha256 over 'schwingnet-anomaly-holdout|' +
SALT + '|' + person, lowest first, so the same inputs give the same list on any machine. A few
of each variant are held, as the owner asked, and enough of the rest are left to train on.
"""

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

SALT = "2026-10-25"
HOLD = {"T13": 2, "L6": 10, "four_lumbar": 1, "normal": 20}
CTSP_READER_L6 = ("0005", "0097", "0208", "0234", "0244", "0268", "0302", "0366",
                  "0376", "0486", "0565", "0831", "0950", "0960", "0999", "1053")
CTSP_DISPUTED = ("0008", "0021", "0033", "0049", "0176", "0179", "0196")
CTSP_HOLD_L6 = 5
DISPUTED_REVIEW = ("contradicts the published read", "release mask carries an L6", "release mask id order broken")
VARIANTS = ("L6", "T13", "four_lumbar", "eleven")
# The real-frame persons are test only (the harvest directive): their projections test a model and never train one.
TEST_ONLY_SOURCES = {"cobra2026", "carmlspine", "deepfluoro", "geneva", "spinesac", "ljubljana"}
TARGET_VARIANT_SHARE = 0.30
CROP_BYTES = 512 * 512 * 256 * 2 + 512 * 512 * 256  # FleXray's ct-seg crop as float16, with its uint8 labels


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rank(person):
    """A person's place in every draw: the first 8 bytes of a salted sha256, as rule.json ranks a split."""
    digest = hashlib.sha256(f"schwingnet-anomaly-holdout|{SALT}|{person}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def count_of(text):
    return int(text) if text and text.isdigit() else None


def truth_of(structure):
    """The readers' variant from C/T/L/S: L6, T13, four_lumbar, eleven or normal; None where unread."""
    parts = structure.split("/") if structure else []
    if len(parts) != 4:
        return None
    thoracic, lumbar = parts[1], count_of(parts[2])
    if lumbar == 6:
        return "L6"
    if not thoracic.isdigit():
        return None
    if int(thoracic) == 13:
        return "T13"
    if lumbar == 4:
        return "four_lumbar"
    if int(thoracic) == 11:
        return "eleven"
    return "normal" if (int(thoracic), lumbar) == (12, 5) else None


def call_of(lumbar, thoracic):
    """The variant two counts name, or no_count where neither counts."""
    if lumbar == 6:
        return "L6"
    if thoracic == 13:
        return "T13"
    if lumbar == 4:
        return "four_lumbar"
    if thoracic == 11:
        return "eleven"
    if lumbar == 5 and thoracic in (12, None):
        return "normal"
    return "no_count" if lumbar is None and thoracic is None else "other"


def b_thoracic(row):
    """Labeller B's thoracic count by rib contact where its text gives one, else its count from T1."""
    found = re.search(r"by rib contact nT=(\d+)", row.get("labeller_b", ""))
    return int(found.group(1)) if found else count_of(row.get("b_nT", ""))


def agreed(a, b):
    """('ok', count) where both labellers count the same, ('discordant', None) where they differ, else one or none."""
    if a is not None and b is not None:
        return ("ok", a) if a == b else ("discordant", None)
    return ("single", None) if (a is not None or b is not None) else ("none", None)


def two_labeller_call(row):
    lumbar = agreed(count_of(row.get("a_nL", "")), count_of(row.get("b_nL_contact", "")))
    thoracic = agreed(count_of(row.get("a_nT", "")), b_thoracic(row))
    if "discordant" in (lumbar[0], thoracic[0]):
        return "discordant"
    call = call_of(lumbar[1], thoracic[1])
    return "single" if call == "no_count" and "single" in (lumbar[0], thoracic[0]) else call


def veridah_call(row):
    return call_of(count_of(row.get("a_nL", "")), count_of(row.get("a_nT", "")))


def disputed(row):
    return any(words in row.get("review", "") for words in DISPUTED_REVIEW)


def verse_number(case):
    found = re.fullmatch(r"verse(\d+)", case)
    return int(found.group(1)) if found else None


def releases(table_rows):
    """VerSe subject number to its release: 2019 where the table says it was in VerSe'19, else 2020."""
    out = {}
    for row in table_rows:
        number = count_of(row.get("verse_id", "").strip())
        if number is not None:
            out[number] = "2019" if row.get("in_verse2019", "").strip() == "1" else "2020"
    return out


def persons_of(screen_rows):
    """Each read person once: its first scan by case id, its truth, and whether any of its scans is disputed."""
    by_person = defaultdict(list)
    for row in screen_rows:
        if truth_of(row.get("read_structure", "")):
            by_person[row["patient_key"]].append(row)
    out = {}
    for person, rows in by_person.items():
        rows.sort(key=lambda row: row["case"])
        truths = {truth_of(row["read_structure"]) for row in rows}
        agreed_truth = next(iter(truths)) if len(truths) == 1 else None
        out[person] = {"rows": rows, "first": rows[0], "truth": agreed_truth,
                       "disputed": agreed_truth is None or any(disputed(row) for row in rows)}
    return out


def both_junctions_in_field(rows):
    return all(row.get("junction_tl_in_fov") == "True" and row.get("junction_ls_in_fov") == "True" for row in rows)


def shares(total, weights):
    """total split over weights in proportion, by largest remainder, so the parts sum to total."""
    whole = sum(weights.values())
    if whole == 0:
        return {key: 0 for key in weights}
    exact = {key: total * value / whole for key, value in weights.items()}
    parts = {key: int(value) for key, value in exact.items()}
    for key in sorted(exact, key=lambda key: (parts[key] - exact[key], key))[: total - sum(parts.values())]:
        parts[key] += 1
    return parts


def draw(candidates, count, release_of, weights=None):
    """count persons, lowest rank first, split over the releases in proportion to weights (else to the candidates)."""
    by_release = defaultdict(list)
    for person in candidates:
        by_release[release_of(person)].append(person)
    total = min(count, len(candidates))
    wanted = shares(total, weights or {key: len(value) for key, value in by_release.items()})
    taken = []
    for release, people in sorted(by_release.items()):
        taken += sorted(people, key=rank)[: wanted.get(release, 0)]
    # A release with too few candidates for its share leaves the rest to the others, lowest rank first.
    rest = sorted(set(candidates) - set(taken), key=rank)
    return sorted(taken + rest[: total - len(taken)], key=rank)


def stratum_of_variant(person_info):
    """An L6's stratum: whether the release mask names its sixth lumbar body as id 25 (the easier case) or not."""
    if person_info["truth"] != "L6":
        return person_info["truth"]
    named = any(row.get("mask_has_L6") == "True" for row in person_info["rows"])
    return "L6, id 25 in the release mask" if named else "L6, no id 25 in the release mask"


def stratum_of(person_info):
    """A normal count's reported stratum: the read's own subtype, Castellvi II to IV and lumbar ribs apart."""
    return person_info["first"].get("read_subtype", "") or "normal"


def freeze(screen, table):
    screen_rows, table_rows = read_csv(screen), read_csv(table)
    persons, release_by_number = persons_of(screen_rows), releases(table_rows)

    def release_of(person):
        return release_by_number.get(verse_number(person.split(":", 1)[-1]), "unknown")

    clean = {person: info for person, info in persons.items() if not info["disputed"]}
    held = []
    positives = Counter()
    for variant in ("T13", "L6", "four_lumbar"):
        chosen = draw([p for p, info in clean.items() if info["truth"] == variant], HOLD[variant], release_of)
        positives.update(release_of(person) for person in chosen)
        held += [{"person": person, "variant": variant, "release": release_of(person), "stratum": stratum_of_variant(clean[person]),
                  "scans": [row["case"] for row in clean[person]["rows"]]} for person in chosen]
    normals = [p for p, info in clean.items() if info["truth"] == "normal" and both_junctions_in_field(info["rows"])]
    for person in draw(normals, HOLD["normal"], release_of, weights=dict(positives)):
        held.append({"person": person, "variant": "normal", "release": release_of(person),
                     "stratum": stratum_of(clean[person]), "scans": [row["case"] for row in clean[person]["rows"]]})
    ctsp = [f"ctsp:{record}" for record in CTSP_READER_L6 if record not in CTSP_DISPUTED]
    for person in sorted(ctsp, key=rank)[:CTSP_HOLD_L6]:
        held.append({"person": person, "variant": "L6", "release": "ctspinopelvic1k", "stratum": "reader-confirmed L6",
                     "scans": [person.split(":", 1)[1]]})
    return {
        "frozen": SALT,
        "why": "the SPINEPS to FleXray anomaly route (docs/research/spineps-anomaly-route.md, #398): no checkpoint of the "
               "route's lineage may see these persons, and the selection, the pack's training list and the fine-tune refuse them",
        "rule": {
            "rank": "first 8 bytes, big-endian, of sha256 over the UTF-8 of 'schwingnet-anomaly-holdout|' + salt + '|' + person; lowest first",
            "salt": SALT,
            "verse": f"read persons of the VerSe screen, none disputed; {HOLD['T13']} T13, {HOLD['L6']} L6 and {HOLD['four_lumbar']} "
                     f"four-lumbar, each split over the VerSe releases in proportion to its candidates; {HOLD['normal']} normal counts "
                     "with both junctions in the field of every scan, any Castellvi grade or lumbar rib, split over the releases "
                     "in proportion to the positives held",
            "disputed": "a scan whose screen review says: " + "; ".join(DISPUTED_REVIEW),
            "ctspinopelvic1k": f"{CTSP_HOLD_L6} of the 16 reader-confirmed L6 records, none of the seven disputed "
                               f"({', '.join(CTSP_DISPUTED)}); its normals are drawn by the same rank by the select stage "
                               "and added here by pull request before any render reads this file",
        },
        "inputs": {"screen": {"name": Path(screen).name, "sha256": sha256_of(screen)},
                   "table": {"name": Path(table).name, "sha256": sha256_of(table)}},
        "persons": held,
        "disputed": sorted({person for person, info in persons.items() if info["disputed"]}
                           | {f"ctsp:{record}" for record in CTSP_DISPUTED}),
    }


def wilson(hits, total, z=1.959964):
    """The 95 percent Wilson interval of hits out of total, in percent."""
    if total == 0:
        return (float("nan"), float("nan"))
    p = hits / total
    centre, spread, scale = p + z * z / (2 * total), z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)), 1 + z * z / total
    return (100 * (centre - spread) / scale, 100 * (centre + spread) / scale)


def interval(hits, total):
    low, high = wilson(hits, total)
    return f"{hits} of {total} ({100 * hits / total:.1f} %, {low:.1f} to {high:.1f})" if total else "none"


def tally(counts):
    return ", ".join(f"{call} {n}" for call, n in counts.most_common()) or "none"


def score_lines(persons, finder, name):
    lines = [f"### {name}", "", "| | found | every call it made |", "|---|---|---|"]
    for variant in ("L6", "T13", "four_lumbar"):
        truth = [info for info in persons.values() if info["truth"] == variant]
        found = sum(finder(info["first"]) == variant for info in truth)
        calls = Counter(finder(info["first"]) for info in truth)
        lines.append(f"| {variant}: sensitivity | {interval(found, len(truth))} | {tally(calls)} |")
    normal = [info for info in persons.values() if info["truth"] == "normal"]
    false = sum(finder(info["first"]) in ("L6", "T13") for info in normal)
    called = Counter(finder(info["first"]) for info in normal)
    lines.append(f"| normal count: no L6 or T13 called (specificity) | {interval(len(normal) - false, len(normal))} | {tally(called)} |")
    lines.append(f"| normal count: called normal (coverage) | {interval(called['normal'], len(normal))} | |")
    for variant in ("L6", "T13", "four_lumbar"):
        made = [info for info in persons.values() if finder(info["first"]) == variant]
        right = sum(info["truth"] == variant for info in made)
        lines.append(f"| {variant} calls that are right (precision) | {interval(right, len(made))} | "
                     f"wrong: {tally(Counter(info['truth'] for info in made if info['truth'] != variant))} |")
    return lines + [""]


def score(screen, holdout=None):
    persons = persons_of(read_csv(screen))
    scored = {person: info for person, info in persons.items() if not info["disputed"]}
    held = {entry["person"] for entry in json.loads(Path(holdout).read_text(encoding="utf-8"))["persons"]} if holdout else set()
    lines = [f"## The CT finder against the VerSe readers (screen {sha256_of(screen)[:12]})", "",
             f"Read persons {len(persons)}; disputed and left out {len(persons) - len(scored)}; scored {len(scored)}, "
             f"each by its first scan. Intervals are Wilson at 95 percent. A no_count, single or discordant on a "
             f"variant is a miss, and on a normal count it is no normal call.", ""]
    lines += score_lines(scored, two_labeller_call, "Two labellers agreeing (the finder)")
    lines += score_lines(scored, veridah_call, "VERIDAH alone")
    if held:
        lines += score_lines({p: i for p, i in scored.items() if p in held}, two_labeller_call, "The finder on the frozen holdout alone")
    return "\n".join(lines)


def harvest_rows(harvest):
    """Every rows.csv the anomaly harvest wrote, one folder a collection, with the folder as the collection."""
    for path in sorted(Path(harvest).glob("*/rows.csv")):
        for row in read_csv(path):
            yield path.parent.name, row


# Subtypes the registry gives a spine whose count is normal: a Castellvi grade, a fused or
# sacralised L5 and a lumbar rib all keep twelve thoracic and five lumbar bodies, and are the
# hardest negatives a count finder meets, so they are negatives here, not left out.
NORMAL_COUNT_SUBTYPES = ("none", "ordinary", "castellvi_I_II", "sacralised_L5_fused", "lumbar_rib")


def variant_of(row):
    subtype, tier = row.get("subtype", ""), row.get("truth_tier", "")
    if tier not in ("read", "two-labeller"):
        return None
    if subtype in ("L6", "T13", "both_L6_T13"):
        return subtype
    # Two labellers agreeing on four lumbar bodies were right on 2 of 12 VerSe persons (score), so
    # only a read four-lumbar spine trains the class.
    if subtype == "unassigned" and row.get("four_lumbar") == "True":
        return "four_lumbar" if tier == "read" else None
    return "normal" if subtype in NORMAL_COUNT_SUBTYPES else None


def whole_count_in_field(row):
    """Both junctions in the field, so a normal call is a count of the whole thoracolumbar column."""
    return row.get("junction_tl_in_fov") == "True" and row.get("junction_ls_in_fov") == "True"


def test_only(row, collection):
    return collection in TEST_ONLY_SOURCES or row.get("real_frames") == "True" or row.get("frames_role", "CT-only") not in ("", "CT-only")


def candidates(registry, harvest):
    """One row per person, the registry's first and each harvest collection's after it."""
    seen = {}
    for row in read_csv(registry):
        seen.setdefault(row["patient_key"], (row.get("winning_source", ""), row.get("winning_case", ""), row))
    for collection, row in harvest_rows(harvest):
        seen.setdefault(row.get("patient_key") or f"{collection}:{row.get('case', '')}", (collection, row.get("case", ""), row))
    return seen


def refused_people(holdout):
    """The held-out persons and the disputed ones, which no list of the route may carry."""
    frozen = json.loads(Path(holdout).read_text(encoding="utf-8"))
    return {entry["person"] for entry in frozen["persons"]}, set(frozen.get("disputed", []))


def select(registry, harvest, holdout):
    held, disputed_people = refused_people(holdout)
    chosen, left_out = [], Counter()
    negatives = defaultdict(list)
    for person, (collection, case, row) in candidates(registry, harvest).items():
        variant = variant_of(row)
        if person in held or person in disputed_people:
            left_out["held out or disputed"] += 1
        elif variant is None:
            left_out[f"no read or two-labeller call ({row.get('subtype', '') or 'blank'}, {row.get('truth_tier', '') or 'no tier'})"] += 1
        elif test_only(row, collection):
            chosen.append({"person": person, "collection": collection, "case": case, "variant": variant, "role": "test"})
        elif variant == "normal" and not whole_count_in_field(row):
            left_out["a normal count with a junction outside the field"] += 1
        elif variant == "normal":
            negatives[collection].append((person, case))
        else:
            chosen.append({"person": person, "collection": collection, "case": case, "variant": variant,
                           "tier": row.get("truth_tier", ""), "role": "train"})
    train_positives = sum(entry["role"] == "train" for entry in chosen)
    wanted = round(train_positives * (1 - TARGET_VARIANT_SHARE) / TARGET_VARIANT_SHARE)
    parts = shares(min(wanted, sum(map(len, negatives.values()))), {key: len(value) for key, value in negatives.items()})
    for collection, people in sorted(negatives.items()):
        for person, case in sorted(people, key=lambda item: rank(item[0]))[: parts[collection]]:
            chosen.append({"person": person, "collection": collection, "case": case, "variant": "normal", "tier": "", "role": "train"})
    overlap = sorted((held | disputed_people) & {entry["person"] for entry in chosen})
    if overlap:
        raise SystemExit(f"refusing: the selection holds {len(overlap)} held-out or disputed persons")
    return chosen, left_out


def selection_lines(chosen, left_out):
    table = Counter((entry["role"], entry["variant"], entry["collection"]) for entry in chosen)
    train = [entry for entry in chosen if entry["role"] == "train"]
    share = sum(entry["variant"] != "normal" for entry in train) / len(train) if train else 0.0
    lines = ["## The selection", "", f"Train CTs {len(train)}, of them variants {100 * share:.1f} percent; test-only paired CTs "
             f"{sum(entry['role'] == 'test' for entry in chosen)}. The pack's bound: {len(chosen)} crops of at most "
             f"{CROP_BYTES / 2**20:.0f} MiB, {len(chosen) * CROP_BYTES / 2**30:.1f} GiB.", "",
             "| role | variant | collection | CTs |", "|---|---|---|---|"]
    lines += [f"| {role} | {variant} | {collection} | {count} |" for (role, variant, collection), count in sorted(table.items())]
    lines += ["", "Left out:", ""] + [f"- {why}: {count}" for why, count in left_out.most_common()]
    return lines + [""]


def check(holdout, listed):
    held, disputed_people = refused_people(holdout)
    return sorted((held | disputed_people) & {row.get("patient_key", "") or row.get("person", "") for row in read_csv(listed)})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("freeze")
    one.add_argument("--screen", required=True)
    one.add_argument("--table", required=True)
    one.add_argument("--out", required=True)
    one = sub.add_parser("score")
    one.add_argument("--screen", required=True)
    one.add_argument("--holdout")
    one = sub.add_parser("select")
    one.add_argument("--registry", required=True)
    one.add_argument("--harvest", required=True)
    one.add_argument("--holdout", required=True)
    one.add_argument("--out", required=True)
    one = sub.add_parser("check")
    one.add_argument("--holdout", required=True)
    one.add_argument("--list", required=True)
    args = parser.parse_args(argv)
    if args.command == "freeze":
        Path(args.out).write_text(json.dumps(freeze(args.screen, args.table), indent=1) + "\n", encoding="utf-8")
    elif args.command == "score":
        print(score(args.screen, args.holdout))
    elif args.command == "select":
        chosen, left_out = select(args.registry, args.harvest, args.holdout)
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        with open(out / "selection.csv", "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["person", "collection", "case", "variant", "tier", "role"], extrasaction="ignore")
            writer.writeheader()
            writer.writerows(chosen)
        print("\n".join(selection_lines(chosen, left_out)))
    else:
        found = check(args.holdout, args.list)
        if found:
            print(f"refusing: {len(found)} held-out or disputed persons in {args.list}: {', '.join(found[:10])}")
            return 1
        print(f"no held-out or disputed person in {args.list}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
