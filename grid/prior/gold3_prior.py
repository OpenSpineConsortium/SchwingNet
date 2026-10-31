"""The gold tier 3 correlation prior: how one person's body and end-plate measures move together
across levels and across measures, fitted per population from the morphometry rows on the grid.

greg's direction of 2026-10-30 (thread "Train on randomized spine phantoms"): the gold tier gives
the population structure the published tables cannot, the correlation between levels and between
measures, and the generator draws with it (bordercall schwingcheck/correlation.py, vendored beside
this file at the commit grid/prior/VENDORED names). The word `morphometry prior` in grid/gate.sh
runs this as one CPU job (grid/morphometry-prior.sbatch).

Read: the rows of grid/morphometry.sbatch under ROOT (enhance/rows.csv, verse/rows.csv,
verse/totalseg/rows.csv), the admission (data/gold3-ct/admission.json), VerSe's series to patients
(data/gold3-ct/verse/series.json), and the latent-prior evaluation's frozen test reserve and repeat
groups (data/splits/). Kept out before any fit:
- every study the admission does not admit;
- every person in the test reserve, so the evaluation's test persons stay unread here;
- every study whose rows name an L6 or a T13, or no L5, since this prior is the normal spine's;
  rib anomalies are not visible in the rows and stay in (the reserve holds most of them).
The rest are cut into a fit part and a held-out part by unit (a repeat group is one unit) with a
hash of the unit key, a fifth held out. Each population is fitted alone (enhance_pet, verse,
totalsegmentator), never pooled (the populations rule of 2026-10-29), over two level sets, C3 to L5
and T1 to L5, on the five measures whose steps pass the literature bounds (SchwingNet issue memory
gold3-on-bounds-card): endplate, endplate_depth, endplate_lower, endplate_lower_depth, h_post.

Written: under OUT, prior-<population>-<levels>.json for each fit (aggregates only, two correlation
matrices and counts), and report.lines, the lines the job's report carries: the counts, the held-out
log likelihood gain over the generator's assumed structure in nats per spine with its standard error,
the share of held-out spines the fit scores better, and each prior's matrices rounded to three places.
No line holds a path, a study id or a person key.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import numpy as np                                  # noqa: E402

from schwingcheck import correlation as CORR       # noqa: E402

MEASURES = ["endplate", "endplate_depth", "endplate_lower", "endplate_lower_depth", "h_post"]
LEVEL_SETS = {"C3..L5": CORR.expand_levels("C3..L5"), "T1..L5": CORR.expand_levels("T1..L5")}
HELD_SHARE = 0.2
SHRINK = 0.05
POPULATIONS = (("enhance_pet", "enhance/rows.csv"), ("verse", "verse/rows.csv"),
               ("totalsegmentator", "verse/totalseg/rows.csv"))
VERSE_SERIES = re.compile(r"(verse\d+|gl\d+)", re.IGNORECASE)
TOTALSEG_SUBJECT = re.compile(r"s\d{4}")
ADMISSION_MEMBER = {"enhance_pet": "enhance_pet", "verse": "verse", "totalsegmentator": "totalsegmentator"}


def study_id(population: str, raw: str) -> str:
    """The admission's id of a rows file's study, as tools/gold3_covariates.py reads it."""
    if population == "enhance_pet":
        return raw.zfill(4) if raw.isdigit() else raw
    pattern = VERSE_SERIES if population == "verse" else TOTALSEG_SUBJECT
    found = pattern.search(raw)
    if not found:
        return raw
    return found.group(1).lower() if population == "verse" else found.group(0)


def person_of(population: str, sid: str, verse_patients: dict) -> str:
    if population == "verse":
        return "verse:" + verse_patients.get(sid, sid)
    return "%s:%s" % (population, sid)


def admitted(records: Path, member: str) -> set:
    data = json.loads((records / "gold3-ct" / "admission.json").read_text())
    return {s["id"] for s in data["studies"] if s["member"] == member and s["verdict"] == "admitted"}


def verse_patients(records: Path) -> dict:
    data = json.loads((records / "gold3-ct" / "verse" / "series.json").read_text())
    return {s["series"].lower(): s["patient"] for s in data["series"]}


def reserve_persons(records: Path) -> set:
    return {p["person"] for p in json.loads((records / "splits" / "latent-prior-test-reserve.json").read_text())}


def unit_map(records: Path) -> dict:
    units = {}
    for g in json.loads((records / "splits" / "latent-prior-repeat-groups.json").read_text()):
        for p in g["persons"]:
            units[p] = g["unit"]
    return units


def held_out(unit: str) -> bool:
    h = int(hashlib.sha256(("gold3-prior:" + unit).encode()).hexdigest()[:8], 16)
    return h / 0xFFFFFFFF < HELD_SHARE


def anomalous_studies(path: Path) -> tuple:
    """(studies whose rows name L6 or T13, studies with an L5 row) of one rows file, by the raw id."""
    import csv
    odd, with_l5 = set(), set()
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if row["level"] in ("L6", "T13"):
                odd.add(row["study"])
            elif row["level"] == "L5":
                with_l5.add(row["study"])
    return odd, with_l5


def population_parts(population: str, rows: Path, records: Path, tally: dict) -> dict:
    """{level set: (fit values, held values)} of one population."""
    allowed = admitted(records, ADMISSION_MEMBER[population])
    patients = verse_patients(records) if population == "verse" else {}
    reserve, units = reserve_persons(records), unit_map(records)
    odd, with_l5 = anomalous_studies(rows)
    out = {}
    for name, levels in LEVEL_SETS.items():
        values, raw_ids = CORR.read_rows(str(rows), levels, MEASURES)
        keep_fit, keep_held = [], []
        counts = dict(read=len(raw_ids), not_admitted=0, reserved=0, anomalous=0)
        for i, raw in enumerate(raw_ids):
            sid = study_id(population, raw)
            person = person_of(population, sid, patients)
            if sid not in allowed:
                counts["not_admitted"] += 1
            elif person in reserve:
                counts["reserved"] += 1
            elif raw in odd or raw not in with_l5:
                counts["anomalous"] += 1
            elif held_out(units.get(person, person)):
                keep_held.append(i)
            else:
                keep_fit.append(i)
        tally[(population, name)] = counts
        out[name] = (values[keep_fit], values[keep_held])
    return out


def fmt(xs) -> str:
    return " ".join("%.3f" % x for x in xs)


def lag_profile(r: np.ndarray) -> list:
    return [float(np.mean(np.diag(r, k))) for k in range(1, min(6, len(r)))]


def run(root: Path, records: Path, out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    lines, failed = [], 0
    lines.append("measures: " + ", ".join(MEASURES) + "; shrink %.2f toward the identity; a fifth of units held out" % SHRINK)
    assumed = CORR.assumed_cov(2, 1, 0.5, 0.0)[0, 1]
    lines.append("the generator's assumed structure: two levels of one measure at %.2f, two measures at 0.00" % assumed)
    for population, rel in POPULATIONS:
        rows = root / rel
        if not rows.is_file():
            lines.append("FAILED: no rows for %s" % population)
            failed += 1
            continue
        tally = {}
        parts = population_parts(population, rows, records, tally)
        for name, (fit_values, held_values) in parts.items():
            c = tally[(population, name)]
            head = "%s %s:" % (population, name)
            lines.append("%s studies %d, not admitted %d, test reserve %d, L6 or T13 or no L5 %d, fit %d, held %d"
                         % (head, c["read"], c["not_admitted"], c["reserved"], c["anomalous"], len(fit_values), len(held_values)))
            try:
                p = CORR.fit(fit_values, LEVEL_SETS[name], MEASURES, SHRINK, note="gold3 %s %s" % (population, name))
            except ValueError:
                lines.append("%s not fitted: too few whole spines for the level set" % head)
                continue
            (out / ("prior-%s-%s.json" % (population, name.replace("..", "-")))).write_text(json.dumps(p.to_json(), indent=1) + "\n")
            lines.append("%s fitted on %d whole spines" % (head, p.n))
            if len(CORR.complete(held_values)) >= 2:
                r = CORR.compare(fit_values, held_values, p)
                lines.append("%s held out %d whole spines: gain %.2f nats a spine (SE %.2f), %.4f a cell, better on %.0f per cent"
                             % (head, r["n_test"], r["gain_per_spine"], r["gain_se"], r["gain_per_cell"], 100 * r["share_better"]))
            else:
                lines.append("%s held out: fewer than two whole spines, not scored" % head)
            lines.append("%s level correlation by lag 1 to 5: %s" % (head, fmt(lag_profile(p.r_level))))
            for m, row in zip(MEASURES, p.r_measure):
                lines.append("%s r_measure %s: %s" % (head, m, fmt(row)))
            for l, row in zip(p.levels, p.r_level):
                lines.append("%s r_level %s: %s" % (head, l, fmt(row)))
    (out / "report.lines").write_text("\n".join(lines) + "\n")
    return 3 if failed else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="gold3_prior.py")
    ap.add_argument("--morphometry", required=True, help="the folder holding the sets' rows")
    ap.add_argument("--records", required=True, help="the copy of data/ the job runs from")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    return run(Path(a.morphometry), Path(a.records), Path(a.out))


if __name__ == "__main__":
    sys.exit(main())
