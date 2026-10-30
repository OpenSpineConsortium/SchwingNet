"""The owner's evidence tiers, read from the imported columns, person by person.

The owner's words of 27 October 2026, 03:06 UTC, as SchwingNet's corpus-tiers page records
them (docs/research/corpus-tiers/README.md, section 2, on its branch claude/project-thread-cdwl0r):

- gold: one study of the person shows the whole spine, so a level named in it can be checked
  by counting from C2; silver: it shows less;
- 1: a CT and a real X-ray of the same person, with a person's annotation on at least one;
- 2: the same pair, with no person's annotation on either;
- 3: a CT or an X-ray alone, with a person's annotation;
- 4: a CT or an X-ray alone, with none.

and the rules that page applies, which this file applies to the imports:

- the unit is the person (the studies' subject_id); a person counts once, at the best tier any
  of their studies reaches, gold 1 to 4 and then silver 1 to 4;
- whole spine means the count from C2 holds on the labels themselves and the sacrum is in them
  (column.facts_from_levels: C2 present, no body missing below it, the sacrum present);
- a pair is gold only when both its studies are whole; a whole CT with a partial film is gold 3
  or 4 alone and silver 1 or 2 as a pair, and both are reported;
- an X-ray is a real radiograph or real fluoroscopy: a DRR or any synthetic image (modality
  drr or synthetic) is not, and never makes a pair;
- a person's annotation is one a person drew, checked or refined; a machine's labels
  (annotation "machine": SPINEPS, VERIDAH, TotalSegmentator, MOOSE, a model's pseudo-labels)
  never raise a tier.

Nothing here decides who is the same person: the caller gives each study a subject_id, and two
studies are a pair only when the ids are equal.
"""
from __future__ import annotations

import csv
import os
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Tuple

from .column import Column

CT = ("ct",)
XRAY = ("film", "xr", "xray", "x-ray", "x_ray", "radiograph", "radiography", "plain film", "cr", "dx", "rf",
        "fluoro", "fluoroscopy", "c-arm", "carm")
SYNTHETIC = ("drr", "synthetic")
ORDER = ["gold 1", "gold 2", "gold 3", "gold 4", "silver 1", "silver 2", "silver 3", "silver 4"]


def kind_of(study: dict) -> str:
    m = str(study.get("modality", "")).lower()
    if m in CT:
        return "ct"
    if m in XRAY:
        return "xray"
    if m in SYNTHETIC:
        return "synthetic"
    return "other"


def whole(study: dict) -> bool:
    return bool(study.get("countable")) and bool(study.get("has_sacrum"))


def human(study: dict) -> bool:
    return study.get("annotation") == "human"


def study_tier(study: dict) -> Tuple[str, str]:
    """A study's tier alone, as if the person had nothing else."""
    grade = "gold" if whole(study) else "silver"
    if kind_of(study) not in ("ct", "xray"):
        return "none", "a %s image is not a CT or a real X-ray" % study.get("modality")
    n = 3 if human(study) else 4
    return "%s %d" % (grade, n), "%s alone, %s annotation" % (kind_of(study), "a person's" if n == 3 else "no person's")


def rank(t: str) -> int:
    return ORDER.index(t) if t in ORDER else len(ORDER)


def person_tiers(columns: Iterable[Column]) -> List[Dict[str, object]]:
    """One row per person: the best tier alone, the best as a pair, and the best of the two."""
    by_subject: Dict[str, List[dict]] = defaultdict(list)
    for c in columns:
        by_subject[str(c.study.get("subject_id") or c.study["study_id"])].append(c.study)
    rows = []
    for subject, studies in sorted(by_subject.items()):
        alone = min((study_tier(s)[0] for s in studies), key=rank)
        cts = [s for s in studies if kind_of(s) == "ct"]
        xrs = [s for s in studies if kind_of(s) == "xray"]
        pair = "none"
        for a in cts:
            for b in xrs:
                grade = "gold" if whole(a) and whole(b) else "silver"
                n = 1 if human(a) or human(b) else 2
                t = "%s %d" % (grade, n)
                if rank(t) < rank(pair):
                    pair = t
        best = min((alone, pair), key=rank)
        rows.append({"subject_id": subject, "studies": len(studies), "tier": best, "tier_alone": alone,
                     "tier_as_pair": pair, "sources": "+".join(sorted({str(s.get("source")) for s in studies})),
                     "phenotypes": "+".join(sorted({str(s.get("phenotype")) for s in studies}))})
    return rows


def annotate(columns: List[Column]) -> None:
    """Write each study's own grade and tier into its record, for studies.csv."""
    for c in columns:
        t, why = study_tier(c.study)
        c.study["grade"] = t.split()[0]
        c.study["tier"] = t
        c.study["tier_reason"] = why


def write(directory: str, rows: List[Dict[str, object]]) -> Dict[str, int]:
    path = os.path.join(directory, "tiers.csv")
    fields = ["subject_id", "studies", "tier", "tier_alone", "tier_as_pair", "sources", "phenotypes"]
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    counts = Counter(r["tier"] for r in rows)
    return {t: counts.get(t, 0) for t in ORDER + ["none"]}
