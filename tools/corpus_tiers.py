"""The owner's gold and silver tiers, case by case, for every CT the grid holds a SPINEPS mask of.

    python3 tools/corpus_tiers.py census --tiers DIR --out DIR [--workers N] [--scan N]
    python3 tools/corpus_tiers.py report --out DIR
    python3 tools/corpus_tiers.py table [--sources FILE]
    python3 tools/corpus_tiers.py power [--sources FILE]

Why this exists. The owner sorted his evidence into tiers on 2026-10-27: a case is gold when one
study of the person shows the whole spine, so the level count from C2 can be checked, and silver
when it shows less; within each, 1 is a full CT paired with a real X-ray of the same person with
a person's annotation of the vertebrae on at least one of the two, 2 the same pair with none, 3
the CT or the X-ray alone with a person's annotation, and 4 alone with none. The records under
data/sources/ say what each source is, but not which of its CTs reach from C2 to the sacrum: that
is a fact of each mask, and only the grid holds the masks. This tool reads every mask the
transitional census lists (tier1.tsv and tier2.tsv under $RS/ruleclass/tiers, a different "tier"
from the owner's: the census's is a mask's quality), with the same reading the bordercall corpus
uses (tools/bordercall_corpus.py: the centroid file's C2, no more than one body above it, no gap a
missed body would leave), and adds the sacrum: a case is full when it is countable from C2 and its
sacrum is in the mask. Nothing is segmented again and nothing trains.

Annotation and pairing come from the committed table, data/corpus-tiers/sources.json, which says
for each census collection whether a person drew or checked the vertebrae, and whether the
collection's CTs have a real full-spine X-ray of the same person. A machine's masks (SPINEPS,
VERIDAH, an automatic segmenter) are never a person's annotation. The census's real_frames column
says a person also has real C-arm frames; those are a partial X-ray, so they pair the case only
as silver. Each person counts once, at the best tier any of their CTs reaches, in the owner's
order gold 1 to 4, then silver 1 to 4: gold first, since only a full spine verifies the count.

What leaves the grid is the report, counts by collection and tier with their denominators; the
per-case file stays on the lab volume, since its case ids are the release's own.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import bordercall_corpus as BC                                    # noqa: E402

SOURCES = ROOT / "data" / "corpus-tiers" / "sources.json"
TIERS = ("gold1", "gold2", "gold3", "gold4", "silver1", "silver2", "silver3", "silver4")
SPANS = ("gold", "silver")
CASE_FIELDS = ["case", "collection", "case_id", "person_key", "status", "reason", "has_c2",
               "has_sacrum", "countable", "coverage", "real_frames", "human", "xr_full",
               "untrusted", "tier", "pair_tier"]


# ---- the tiers ----------------------------------------------------------------------------------

def tier_name(span, paired, human):
    """The owner's tier for one span (gold or silver), paired or alone, annotated or not."""
    if span not in SPANS:
        raise ValueError("a span is gold or silver, not %r" % (span,))
    return "%s%d" % (span, (1 if human else 2) if paired else (3 if human else 4))


def better(a, b):
    """The better of two tiers in the owner's order, either of them possibly empty."""
    if not a:
        return b
    if not b:
        return a
    return a if TIERS.index(a) <= TIERS.index(b) else b


def case_tiers(ct_full, human, xr_kind):
    """(tier, pair_tier) for one CT. xr_kind is "full" for a real full-spine X-ray of the same
    person, "partial" for real frames or films that show less, and "" for none. The CT alone always
    gives a tier; a pair gives one too, gold only when both images show the whole spine."""
    alone = tier_name("gold" if ct_full else "silver", False, human)
    pair = ""
    if xr_kind in ("full", "partial"):
        span = "gold" if ct_full and xr_kind == "full" else "silver"
        pair = tier_name(span, True, human)
    elif xr_kind:
        raise ValueError("an X-ray is full, partial or none, not %r" % (xr_kind,))
    return better(alone, pair), pair


def coverage_of(rec):
    """full, partial or unknown, from the bordercall reading of one mask."""
    if rec.get("status") == "error" or rec.get("reason") == "mask file missing":
        return "unknown"
    if str(rec.get("countable")) == "1" and str(rec.get("has_sacrum")) == "1":
        return "full"
    return "partial"


def load_sources(path=SOURCES):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def collection_facts(sources, collection):
    """The census collection's facts as a dict: human (every CT carries a person's vertebral
    annotation), xr ("full", "partial" or "" for the real X-ray its persons have held and linked),
    untrusted (the owner's rule keeps it out of ground truth) and listed. An unlisted collection is
    read as none of these, the conservative reading, and the report counts it."""
    facts = sources.get("census_collections", {}).get(collection)
    if not facts:
        return {"human": False, "xr": "", "untrusted": False, "listed": False}
    xr = "full" if facts.get("xr_full") else ("partial" if facts.get("xr_partial") else "")
    return {"human": facts.get("human") == "yes", "xr": xr,
            "untrusted": bool(facts.get("untrusted")), "listed": True}


# ---- the census on the grid -------------------------------------------------------------------------

def read_one(row):
    """One census row -> its case record, from the bordercall reading with no label written."""
    rec = BC.one((row, "", "", False))
    return {k: rec.get(k, "") for k in ("case", "collection", "case_id", "person_key", "status",
                                        "reason", "has_c2", "has_sacrum", "countable", "real_frames")}


def place(rec, sources):
    """Set a case's coverage, annotation and tiers. An untrusted collection never counts as whole,
    since the owner does not take its names as truth; a case's own real frames pair it as partial."""
    facts = collection_facts(sources, rec["collection"])
    cov = coverage_of(rec)
    if cov == "full" and facts["untrusted"]:
        cov = "partial"
    rec["coverage"] = cov
    rec["human"] = int(facts["human"])
    rec["xr_full"] = int(facts["xr"] == "full")
    rec["untrusted"] = int(facts["untrusted"])
    if cov == "unknown":
        rec["tier"], rec["pair_tier"] = "", ""
        return rec
    xr_kind = facts["xr"] or ("partial" if str(rec.get("real_frames")) == "1" else "")
    rec["tier"], rec["pair_tier"] = case_tiers(cov == "full", facts["human"], xr_kind)
    return rec


def best_by_person(records):
    """{person_key: best tier}, a person with no key standing for themself."""
    best = {}
    for r in records:
        key = r.get("person_key") or r["case"]
        best[key] = better(best.get(key, ""), r.get("tier", ""))
    return best


def cmd_census(a):
    sources = load_sources(a.sources)
    rows = BC.read_tiers(a.tiers)
    rows = rows[: a.scan] if a.scan else rows
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    print("%d census rows with a SPINEPS mask" % len(rows), flush=True)
    records = []
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for i, rec in enumerate(ex.map(read_one, rows, chunksize=4), 1):
            records.append(place(rec, sources))
            if i % 500 == 0:
                print("  %d read" % i, flush=True)
    records.sort(key=lambda r: r["case"])
    with open(out / "cases.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CASE_FIELDS, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(records)
    print(summary(records, sources))
    return 0


def summary(records, sources):
    """The report: counts with their denominators, by collection and tier, persons once each."""
    lines = []
    cov = Counter(r["coverage"] for r in records)
    lines.append("CTs read %d: full %d, partial %d, unknown %d (full = countable from C2 with the sacrum in the mask)"
                 % (len(records), cov["full"], cov["partial"], cov["unknown"]))
    why = Counter(r["reason"].split(" (")[0].split(":")[0] for r in records
                  if r["coverage"] == "partial" and r["reason"])
    for reason, k in why.most_common(8):
        lines.append("  partial, %s: %d" % (re.sub(r"(?<![A-Za-z])\d+(\.\d+)?", "N", reason), k))
    lines.append("  partial, countable from C2 but no sacrum: %d"
                 % sum(1 for r in records if r["coverage"] == "partial" and str(r["countable"]) == "1"))
    best = best_by_person(records)
    persons = Counter(best.values())
    lines.append("persons %d, each at the best tier of their CTs:" % len(best))
    for t in TIERS:
        lines.append("  %-8s %6d" % (t, persons[t]))
    lines.append("  %-8s %6d" % ("unknown", persons[""]))
    pairs = Counter(r["pair_tier"] for r in records if r["pair_tier"])
    if pairs:
        lines.append("CTs that also form a pair with a real X-ray: " + ", ".join("%s %d" % t for t in sorted(pairs.items())))
    lines.append("by collection (CTs, full, persons, then persons per tier gold1..silver4):")
    per = defaultdict(list)
    for r in records:
        per[r["collection"]].append(r)
    for coll in sorted(per, key=lambda c: -len(per[c])):
        rs = per[coll]
        b = Counter(best_by_person(rs).values())
        listed = collection_facts(sources, coll)["listed"]
        lines.append("  %-26s %6d %6d %6d  %s%s" % (coll, len(rs), sum(1 for r in rs if r["coverage"] == "full"),
                                                  sum(b.values()), " ".join("%d" % b[t] for t in TIERS),
                                                  "" if listed else "  (not in sources.json: read as no annotation)"))
    return "\n".join(lines)


def cmd_report(a):
    sources = load_sources(a.sources)
    with open(Path(a.out) / "cases.csv", encoding="utf-8", newline="") as fh:
        records = list(csv.DictReader(fh))
    print(summary(records, sources))
    return 0


# ---- the committed table and the power it gives -----------------------------------------------------------

def wilson(k, n, z=1.96):
    """The Wilson score interval of k successes in n, as (low, high)."""
    if n <= 0:
        return 0.0, 1.0
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def half_width(p, n):
    """The Wilson half-width at an expected proportion p over n persons."""
    lo, hi = wilson(round(p * n), n)
    return (hi - lo) / 2


def zero_error_bound(n):
    """The one-sided 95 percent upper bound on an error rate when none is seen in n: the exact
    binomial bound, which the rule of three (3/n) approximates."""
    return 1.0 if n <= 0 else 1 - 0.05 ** (1 / n)


def persons_needed(width, p=0.9, limit=10 ** 6):
    """The least n whose Wilson half-width at p is no more than width."""
    n = 1
    while n < limit and half_width(p, n) > width:
        n = n * 2
    lo, hi = n // 2, n
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if half_width(p, mid) <= width:
            hi = mid
        else:
            lo = mid
    return hi


def table_rows(sources):
    return sorted(sources.get("sources", []), key=lambda s: (s.get("status") != "held", s.get("id", "")))


def cmd_table(a):
    sources = load_sources(a.sources)
    head = "| source | status | persons | coverage | paired | human | " + " | ".join(TIERS) + " | basis |"
    print(head)
    print("|" + "---|" * (head.count("|") - 1))
    for s in table_rows(sources):
        t = s.get("tiers", {})
        print("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
            s["id"], s.get("status", ""), s.get("n_persons") or "", s.get("coverage", ""), s.get("paired", ""),
            s.get("human_vertebral_annotation", ""), " | ".join(str(t.get(k, 0)) for k in TIERS),
            s.get("tier_basis", "") + ("; counted in %s" % s["counted_in"] if s.get("counted_in") else "")))
    return 0


def cmd_power(a):
    sources = load_sources(a.sources)
    totals = Counter()
    for s in sources.get("sources", []):
        if s.get("status") == "held" and not s.get("counted_in"):
            for k in TIERS:
                totals[k] += int(s.get("tiers", {}).get(k, 0) or 0)
    print("| tier | held persons | 95% half-width at 90% accuracy | upper bound on errors when none is seen |")
    print("|---|---|---|---|")
    for k in TIERS:
        n = totals[k]
        print("| %s | %d | %s | %s |" % (k, n, "%.1f points" % (100 * half_width(0.9, n)) if n else "-",
                                        "%.2f %%" % (100 * zero_error_bound(n)) if n else "-"))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("census")
    p.add_argument("--tiers", required=True, help="the folder holding the census's tier1.tsv and tier2.tsv")
    p.add_argument("--out", required=True)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--scan", type=int, default=0, help="read at most this many rows")
    p.set_defaults(fn=cmd_census)
    p = sub.add_parser("report")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_report)
    for name, fn in (("table", cmd_table), ("power", cmd_power)):
        p = sub.add_parser(name)
        p.set_defaults(fn=fn)
    for p in sub.choices.values():
        p.add_argument("--sources", default=str(SOURCES), help="the committed tier table")
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
