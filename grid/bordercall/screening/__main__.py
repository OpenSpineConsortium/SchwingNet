"""The commands of the screening package: the wiring, where files, JSON and workers live.

    python -m screening facts --masks DIR --scheme SCHEME --out facts.jsonl [--member NAME]
        [--persons MAP.json] [--label-map MAP.json] [--workers N] [--ids FILE]
    python -m screening whole --facts facts.jsonl --out verdicts.csv [--tables T.json | --measure-tables]
        [--ages MAP.json] [--s1-view MM] [--write-tables OUT.json]
    python -m screening truth-from-riedel GRADES.csv --out truth.csv [--persons MAP.json]
    python -m screening join --rows rows.csv --truth truth.csv [--facts facts.jsonl] [--persons MAP.json] --out joined.csv
    python -m screening detect --joined joined.csv --out aggregates.json [--cut 0.8] [--boot 2000] [--seed 20261029]
    python -m screening neighbours --joined joined.csv --out neighbours.csv
    python -m screening int16 --labels PATH --scheme SCHEME --out OUT.nii.gz [--manifest OUT.json]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from typing import List, Optional

from . import convert, facts, truth, whole


def read_ids(path: Optional[str]) -> Optional[set]:
    if not path:
        return None
    with open(path) as f:
        return {line.strip() for line in f if line.strip()}


def read_map(path: Optional[str]) -> dict:
    if not path:
        return {}
    with open(path) as f:
        return json.load(f)


def cmd_facts(a) -> int:
    persons = truth.read_persons(a.persons)
    label_map = {int(k): v for k, v in read_map(a.label_map).items()} or None
    wanted = read_ids(a.ids)
    jobs = [(sid, path, a.scheme, a.member, persons.get(sid), label_map)
            for sid, path in facts.studies_in(a.masks, a.scheme) if wanted is None or sid in wanted]
    n = facts.run(jobs, a.out, a.workers)
    print("%d rows in %s" % (n, a.out))
    return 0


def cmd_whole(a) -> int:
    ages = read_map(a.ages)
    studies, unread = [], []
    with open(a.facts, encoding="ascii") as f:
        for line in f:
            row = json.loads(line)
            if "error" in row:
                unread.append(row)
                continue
            studies.append(whole.study_from_row(row, ages.get(row["id"])))
    table = whole.tables(studies) if a.measure_tables else (read_map(a.tables)["tables"] if a.tables else whole.default_tables())
    if a.write_tables:
        with open(a.write_tables, "w") as f:
            json.dump({"tables": table}, f, indent=1, sort_keys=True)
    rows = [whole.verdict_row(s, table, a.s1_view) for s in studies]
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(whole.VERDICT_FIELDS), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(json.dumps({"studies": len(rows), "unread": len(unread), "verdict": whole.counts(rows, "verdict"),
                      "count_class": whole.counts(rows, "count_class")}, sort_keys=True))
    return 0


def cmd_truth_from_riedel(a) -> int:
    with open(a.grades, encoding="utf-8") as f:
        cells = truth.riedel_cells(f.read())
    persons = truth.read_persons(a.persons)
    rows, not_grades = truth.truth_rows(cells)
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(truth.TRUTH_FIELDS), lineterminator="\n")
        w.writeheader()
        for row in rows:
            w.writerow({**row, "person": row["person"] or persons.get(row["study"], "")})
    print(json.dumps({"cells": len(cells), "cells_graded": len(rows), "cells_not_a_grade": sum(not_grades.values()),
                      "codes_not_a_grade": dict(not_grades)}, sort_keys=True))
    return 0


def cmd_join(a) -> int:
    truths = truth.read_truth(a.truth)
    measures = truth.read_measures(a.rows)
    joined, counts = truth.join(truths, measures, truth.read_persons(a.persons), truth.read_facts_levels(a.facts))
    truth.write_joined(joined, a.out)
    print(json.dumps(counts, sort_keys=True))
    return 0


def cmd_detect(a) -> int:
    joined = truth.read_joined(a.joined)
    persons = len({row["person"] for row in joined if row["smaller_ratio"] is not None})
    picks = truth.picks_from_numpy(a.seed, persons, a.boot)
    counts = {"vertebrae": len(joined), "persons": len({row["person"] for row in joined}),
              "duplicates_dropped": sum(len(row["duplicates"]) for row in joined), "boot": a.boot, "seed": a.seed}
    out = truth.aggregates(joined, counts, picks, a.cut)
    with open(a.out, "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    print(json.dumps({k: out[k] for k in ("counts", "agreement", "no_reading")}, sort_keys=True))
    for d in out["detection"]:
        print(json.dumps(d, sort_keys=True))
    return 0


def cmd_neighbours(a) -> int:
    rows = truth.neighbour_rows(truth.read_joined(a.joined))
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["truth"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    for row in rows:
        print(json.dumps(row, sort_keys=True))
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="screening", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="command", required=True)
    f = sub.add_parser("facts", help="each study's masks read once into one row of facts, in level names")
    f.add_argument("--masks", required=True)
    f.add_argument("--scheme", required=True)
    f.add_argument("--out", required=True)
    f.add_argument("--member", default="")
    f.add_argument("--persons")
    f.add_argument("--label-map", dest="label_map")
    f.add_argument("--workers", type=int, default=facts.WORKERS)
    f.add_argument("--ids")
    f.set_defaults(run=cmd_facts)
    w = sub.add_parser("whole", help="the whole-spine verdicts by the masks and by the field")
    w.add_argument("--facts", required=True)
    w.add_argument("--out", required=True)
    w.add_argument("--tables")
    w.add_argument("--measure-tables", dest="measure_tables", action="store_true")
    w.add_argument("--write-tables", dest="write_tables")
    w.add_argument("--ages")
    w.add_argument("--s1-view", dest="s1_view", type=float, default=whole.S1_VIEW_MM)
    w.set_defaults(run=cmd_whole)
    r = sub.add_parser("truth-from-riedel", help="Riedel's VerSe table into the truth form")
    r.add_argument("grades")
    r.add_argument("--out", required=True)
    r.add_argument("--persons")
    r.set_defaults(run=cmd_truth_from_riedel)
    j = sub.add_parser("join", help="one reading per person's level, the truth beside the measures")
    j.add_argument("--rows", required=True)
    j.add_argument("--truth", required=True)
    j.add_argument("--facts")
    j.add_argument("--persons")
    j.add_argument("--out", required=True)
    j.set_defaults(run=cmd_join)
    d = sub.add_parser("detect", help="what the smaller ratio screens, with a bootstrap over persons")
    d.add_argument("--joined", required=True)
    d.add_argument("--out", required=True)
    d.add_argument("--cut", type=float, default=truth.CUT)
    d.add_argument("--boot", type=int, default=truth.BOOT)
    d.add_argument("--seed", type=int, default=truth.SEED)
    d.set_defaults(run=cmd_detect)
    n = sub.add_parser("neighbours", help="each vertebra's posterior height against its sound neighbours'")
    n.add_argument("--joined", required=True)
    n.add_argument("--out", required=True)
    n.set_defaults(run=cmd_neighbours)
    convert.command(sub)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    a = parser().parse_args(argv)
    return a.run(a)


if __name__ == "__main__":
    sys.exit(main())
