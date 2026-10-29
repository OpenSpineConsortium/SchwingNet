"""JOBS.json for bordercall's holdings.fullspine_complete from SchwingNet's admission.json and facts.

    python3 make_complete_jobs.py ADMISSION.json VERSE_FACTS TS_FACTS SEGMENTER.json SEGOUT MASKS TSDIR OUT.json

A study is a job when its admission row asks for levels (complete) or holds its head end for a look,
and SEGOUT/<id>/ctgrid/ holds SPINEPS's masks on its CT's grid. Its targets are the completion list,
and, where the head end is a border case, C2 and every undrawn name down to the head-most drawn level,
which the field test would ask for were the head end in view."""
import json
import os
import sys

ORDER = (*[f"C{i}" for i in range(1, 8)], *[f"T{i}" for i in range(1, 14)], *[f"L{i}" for i in range(1, 7)], "sacrum")
MIN_VOXELS = 200


def rows(path):
    with open(path, encoding="ascii") as f:
        return {row["id"]: row for row in map(json.loads, f)}


def drawn(row):
    return [n for n in ORDER if n in row["levels"] and row["levels"][n]["voxels"] >= MIN_VOXELS]


def head_targets(row):
    names = [n for n in drawn(row) if n != "sacrum"]
    if not names:
        return []
    top = names[0]
    if top == "C1":
        return ["C2"]
    return [n for n in ORDER[1:ORDER.index(top)] if n not in names]


def release_of(member, row, masks, tsdir):
    if member == "verse":
        (name,) = row["files"]
        return os.path.join(masks, row["release"], name)
    return os.path.join(tsdir, row["id"])


def main(admission, verse_facts, ts_facts, segmenter, segout, masks, tsdir, out):
    facts = {"verse": rows(verse_facts), "totalsegmentator": rows(ts_facts)}
    studies, skipped = [], []
    for s in json.load(open(admission))["studies"]:
        if s["member"] not in facts or not (s["complete"] or s["verdict"] == "look"):
            continue
        row = facts[s["member"]][s["id"]]
        targets = list(s["complete"])
        if s["verdict"] == "look" and s["head"] == "border":
            targets += head_targets(row)
        targets = [n for n in ORDER if n in targets]
        grid = os.path.join(segout, s["id"], "ctgrid")
        if not targets or not os.path.exists(os.path.join(grid, "input.json")):
            skipped.append({"id": s["id"], "why": "no targets" if not targets else "not segmented yet"})
            continue
        studies.append({"id": s["id"], "member": s["member"], "release": release_of(s["member"], row, masks, tsdir),
                        "machine": os.path.join(grid, "vert.nii.gz"), "spine": os.path.join(grid, "spine.nii.gz"),
                        "input": os.path.join(grid, "input.json"),
                        "targets": targets, "verdict": s["verdict"], "head": s["head"], "foot": s["foot"]})
    spec = {"segmenter": json.load(open(segmenter)), "facts": {"verse": verse_facts, "totalsegmentator": ts_facts},
            "studies": studies, "skipped": skipped}
    json.dump(spec, open(out, "w"), indent=1)
    print(len(studies), "jobs;", len(skipped), "skipped:", skipped)


if __name__ == "__main__":
    main(*sys.argv[1:])
