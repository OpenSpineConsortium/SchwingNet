"""Set the first reading of ENHANCE.PET's masks beside the count's own outputs, study by study.

holdings/enhance_facts.py (the first reading) reuses the count's rules, so on every study it must
give what holdings/count_enhance_pet.py's extents and ribs steps gave from the same masks: the voxels
of every vertebra label, each label's head-foot extent, the grid, the voxels of every rib label
(the sternum, label 27 of the rib masks, is kept apart in the facts), the lowest rib on each side,
and that rib's contact tally, lead and tie. A study where they differ is a fault in one of the two,
found before any fact is used. Where a repair record's touch.json is given, the 3-D distances it
holds are set beside the facts' too, since the count measures no distance.

    python -m holdings.enhance_facts_cross FACTS.jsonl EXTENTS.json RIBS.json OUT.json [--touch TOUCH.json]

EXTENTS.json is the count's `extents` output and RIBS.json its `ribs ... all` output. OUT.json
holds, for each check, how many studies it covered and which failed; the command exits 1 when any
check failed, so a job can stop on it. Standard library only: it reads JSON, never a mask.
Confidential, like the rest of this repository.
"""
import argparse
import json
import sys

RIB_MIN_VOXELS = 50  # the count's RIB_MIN_VOXELS: a rib label under it is a speck, not a rib
RIBS_PER_SIDE = 13
SIDES = (("left", 0), ("right", RIBS_PER_SIDE))
STERNUM = "27"
# The count keeps slice centres to 0.001 mm and the facts to 0.1 mm, each rounded once from the
# same float, so the two agree to half a tenth and the count's own half of a thousandth.
EXTENT_TOLERANCE_MM = 0.051
# touch.json writes each distance to 0.1 mm, as the facts do.
DISTANCE_KEYS = (("L4_sacrum", "23-28"), ("L5_sacrum", "24-28"), ("L4_L5", "23-24"))
FIRST_FAILURES_SHOWN = 20


def rows_of(path: str) -> dict:
    with open(path) as handle:
        return {row["id"]: row for row in map(json.loads, filter(str.strip, handle))}


def load(path: str):
    with open(path) as handle:
        return json.load(handle)


def published(rows: dict) -> dict:
    """The rows read from the published masks; a repaired row has no count to be set beside."""
    return {sid: row for sid, row in rows.items() if "repaired_from" not in row}


def lowest_rib(row: dict, base: int):
    have = [k for k in range(1, RIBS_PER_SIDE + 1)
            if row["ribs"].get(str(base + k), {}).get("voxels", 0) >= RIB_MIN_VOXELS]
    return max(have) if have else None


def vertebra_voxels_differ(row: dict, count: dict) -> bool:
    mine = {label: fact["voxels"] for label, fact in row["labels"].items()}
    return mine != count["voxels"] or row["outside_scheme_voxels"]["vertebrae"] != count["outside_scheme_voxels"]


def extents_differ(row: dict, count: dict) -> list:
    """The labels whose head-foot extent differs, and "grid" where the shape or type does."""
    out = []
    seed = count["extent_mm"]
    for label, fact in sorted(row["labels"].items()):
        low, high = seed.get(label, (None, None))[:2]
        if low is None or abs(fact["bottom_mm"] - low) > EXTENT_TOLERANCE_MM \
                or abs(fact["top_mm"] - high) > EXTENT_TOLERANCE_MM:
            out.append(label)
    if row["mask"]["shape"] != count["shape"] or row["mask"]["dtype"] != count["dtype"]:
        out.append("grid")
    return out


def rib_voxels_differ(row: dict, count: dict) -> bool:
    mine = {label: fact["voxels"] for label, fact in row["ribs"].items()}
    if row["sternum_voxels"]:
        mine[STERNUM] = row["sternum_voxels"]
    return mine != count["voxels"] or row["outside_scheme_voxels"]["ribs"] != count["outside_scheme_voxels"]


def lowest_ribs_differ(row: dict, count: dict) -> list:
    """The sides whose lowest rib, or that rib's tally, lead or tie, differ from the count's."""
    out = []
    for side, base in SIDES:
        mine = lowest_rib(row, base)
        if mine != count["lowest"][side]:
            out.append(side)
            continue
        seed = count.get("contacts", {}).get(side)
        if seed is None:
            continue
        fact = row["ribs"][str(base + seed["lowest_rib"])]
        if (fact["contacts"], fact["lead"], fact["tie"]) != (seed["contacts"], seed["meets"], seed["tie"]):
            out.append(side)
    return out


def distances_differ(row: dict, touch: dict) -> list:
    return [key for touch_key, key in DISTANCE_KEYS
            if touch_key in touch and row["distances_mm"].get(key) != touch[touch_key]]


def verdict(failures: list, covered: int) -> dict:
    return {"studies": covered, "failed": len(failures), "first_failures": failures[:FIRST_FAILURES_SHOWN]}


def missing_studies(rows: dict, extents: dict, ribs: dict) -> list:
    return sorted(set(rows) ^ set(extents)) + sorted(set(rows) ^ set(ribs))


def cross(rows: dict, extents: dict, ribs: dict, touch=None) -> dict:
    """Each check's verdict over the published rows; missing names studies one side lacks."""
    rows = published(rows)
    shared = sorted(set(rows) & set(extents) & set(ribs))
    checks = {
        "vertebra_voxels": verdict([s for s in shared if vertebra_voxels_differ(rows[s], extents[s])], len(shared)),
        "extents_and_grid": verdict(["%s:%s" % (s, ",".join(d)) for s in shared
                                     if (d := extents_differ(rows[s], extents[s]))], len(shared)),
        "rib_voxels": verdict([s for s in shared if rib_voxels_differ(rows[s], ribs[s])], len(shared)),
        "lowest_ribs": verdict(["%s:%s" % (s, ",".join(d)) for s in shared
                                if (d := lowest_ribs_differ(rows[s], ribs[s]))], len(shared)),
    }
    if touch is not None:
        near = sorted(set(touch) & set(rows))
        checks["touch_distances"] = verdict(["%s:%s" % (s, ",".join(d)) for s in near
                                             if (d := distances_differ(rows[s], touch[s]))], len(near))
    missing = missing_studies(rows, extents, ribs)
    return {"checks": checks, "missing": missing,
            "agree": not missing and all(c["failed"] == 0 for c in checks.values())}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("facts")
    parser.add_argument("extents", help="the count's extents output")
    parser.add_argument("ribs", help="the count's ribs output, read with the ids `all`")
    parser.add_argument("out")
    parser.add_argument("--touch", help="a repair record's touch.json, for the 3-D distances")
    args = parser.parse_args(argv)
    touch = load(args.touch) if args.touch else None
    result = cross(rows_of(args.facts), load(args.extents)["studies"], load(args.ribs)["studies"], touch)
    with open(args.out, "w", newline="\n") as handle:
        json.dump(result, handle, indent=1, sort_keys=True)
        handle.write("\n")
    for name, check in sorted(result["checks"].items()):
        print("%s %s: %d of %d agree" % ("PASS" if not check["failed"] else "FAIL", name,
                                        check["studies"] - check["failed"], check["studies"]))
    if result["missing"]:
        print("FAIL studies on one side only: %s" % result["missing"][:FIRST_FAILURES_SHOWN])
    return 0 if result["agree"] else 1


if __name__ == "__main__":
    sys.exit(main())
