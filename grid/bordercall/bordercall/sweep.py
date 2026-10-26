"""Which border does the shape name most robustly, in normal AND anomalous spines?

    python run.py sweep --levels levels.csv --phenotype phenotype.csv

`border` answers one border at a time and `breakout` splits one border by phenotype. Neither
answers the question that decides where this method is worth using: across the candidate
junctions, which one holds up when the spine is NOT typical.

HOW A BORDER IS RANKED, AND WHY NOT BY ACCURACY. Ranking on the corpus figure picks the
border with the most typical spines in it, which is the opposite of the question. A border is
ranked here by its WORST-SCORING anomalous phenotype that has enough cases to score
(--min-class, default 10), because a method that names the border in 97 % of ordinary columns
and 29 % of the ones a surgeon would get wrong is not robust, it is merely accurate. The
corpus figure and the typical-column figure are both printed beside it, so the gap is visible
rather than hidden.

ONLY COUNTABLE RECORDS ARE SCORED. A verified vertebral name comes from counting down from
C2. A record without C2 cannot supply one, so its "ground truth" is a reader's call and a
disagreement with it means nothing. `phenotype` records `countable` per case, and this command
scores only those records and says how many it set aside. --allow-uncountable overrides it,
and then every number printed carries that caveat, which the output states.
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import phenotype as PH
from border import Border, Corpus, out_of_fold

# the junctions worth asking about, cranial first. A pair is skipped when either level is
# not in the measured corpus, so this same list serves a lumbar-only and a whole-spine run.
CANDIDATES = [("C6", "C7"), ("C7", "T1"), ("T1", "T2"),
              ("T11", "T12"), ("T12", "L1"), ("L1", "L2"), ("L5", "L6")]


def evaluate(corpus, phen, above, below, folds, seed, min_class, countable_only):
    """-> dict for one border, or None when the border is not measurable here."""
    b = Border(above, below)
    try:
        upper, _ = b.split(corpus.levels)
    except SystemExit:
        return None
    X, groups, lv, _ = corpus.features()
    if countable_only:
        keep = np.array([bool(phen.get(g, {}).get("countable")) for g in groups])
        if keep.sum() == 0:
            return None
        X, groups, lv = X[keep], groups[keep], lv[keep]
    y = np.array([1 if l in upper else 0 for l in lv], int)
    if y.min() == y.max():
        return None
    s = out_of_fold(X, y, groups, folds=folds, seed=seed)
    order = {l: i for i, l in enumerate(corpus.levels)}
    per_case = defaultdict(dict)
    for g, l, p in zip(groups, lv, s >= 0.5):
        per_case[g][l] = bool(p)

    acc = defaultdict(lambda: [0, 0])
    for g, d in per_case.items():
        if above not in d or below not in d:
            continue
        k = phen.get(g, {}).get("phenotype", "typical")
        present = sorted(d, key=lambda l: order[l])
        seq = [d[l] for l in present]
        n = sum(seq)
        acc[k][0] += 1
        ok = (seq[:n] == [True] * n and not any(seq[n:])
              and n - sum(1 for l in present if l in upper) == 0)
        acc[k][1] += int(ok)
    if not acc:
        return None

    tot_n = sum(v[0] for v in acc.values())
    tot_k = sum(v[1] for v in acc.values())
    anomalous = {k: v for k, v in acc.items() if k != "typical" and v[0] >= min_class}
    worst, worst_class = None, None
    for k, (n, ko) in anomalous.items():
        r = ko / n
        if worst is None or r < worst:
            worst, worst_class = r, k
    typ = acc.get("typical", [0, 0])
    return {"border": "%s/%s" % (above, below), "n": tot_n,
            "overall": tot_k / tot_n if tot_n else float("nan"),
            "typical": (typ[1] / typ[0]) if typ[0] else float("nan"),
            "typical_n": typ[0], "worst": worst, "worst_class": worst_class,
            "n_scorable_classes": len(anomalous), "per_class": dict(acc)}


def run(levels_csv, phenotype_csv, case_key="case", folds=5, seed=0, min_class=10,
        countable_only=True, candidates=None):
    corpus = Corpus.from_csv(levels_csv, case_key=case_key)
    phen = PH.load(phenotype_csv)
    print("levels measured: %s" % ", ".join(corpus.levels))

    n_total = len(phen)
    n_count = sum(1 for v in phen.values() if v.get("countable"))
    print("records: %d, of which countable (C2 present): %d" % (n_total, n_count))
    if countable_only and n_count == 0:
        print("\nSTOP. No record in this corpus contains C2, so no border name here is a")
        print("verified count -- it is a reader's call, and a disagreement with it means")
        print("nothing. Use a corpus with whole-spine coverage, or pass --allow-uncountable")
        print("and read every number below as provisional.")
        return 1
    if countable_only and n_count < n_total:
        print("  scoring the %d countable records; %d set aside"
              % (n_count, n_total - n_count))
    if not countable_only:
        print("  --allow-uncountable: scoring every record. The ground truth is NOT a")
        print("  verified count on the records without C2, so these numbers are provisional.")

    rows = []
    for above, below in (candidates or CANDIDATES):
        r = evaluate(corpus, phen, above, below, folds, seed, min_class, countable_only)
        if r:
            rows.append(r)
    if not rows:
        print("\nno candidate border is measurable in this corpus")
        return 1

    print("\nRANKED BY THE WORST ANOMALOUS PHENOTYPE, not by the corpus figure")
    print("  %-10s %7s %9s %9s %9s  %s"
          % ("border", "n", "overall", "typical", "worst", "worst class"))
    ranked = sorted(rows, key=lambda r: (-1 if r["worst"] is None else r["worst"]),
                    reverse=True)
    for r in ranked:
        w = "   --   " if r["worst"] is None else "%8.1f%%" % (100 * r["worst"])
        wc = r["worst_class"] or ("no class with >= cases" if r["worst"] is None else "")
        print("  %-10s %7d %8.1f%% %8.1f%% %s  %s"
              % (r["border"], r["n"], 100 * r["overall"], 100 * r["typical"], w,
                 PH.PRETTY.get(wc, wc)))

    scored = [r for r in ranked if r["worst"] is not None]
    if scored:
        best = scored[0]
        print("\n  most robust: %s, worst anomalous phenotype %.1f%% (%s), typical %.1f%%"
              % (best["border"], 100 * best["worst"],
                 PH.PRETTY.get(best["worst_class"], best["worst_class"]),
                 100 * best["typical"]))
        gap = best["typical"] - best["worst"]
        print("  the gap between typical and worst at that border is %.1f points" % (100 * gap))
    else:
        print("\n  NO border has an anomalous phenotype with >= %d cases." % min_class)
        print("  Nothing here can be called robust; the corpus has too few anomalous spines.")

    print("\n  per class, every border")
    for r in ranked:
        parts = []
        for k in PH.CLASS_ORDER:
            if k in r["per_class"]:
                n, ko = r["per_class"][k]
                parts.append("%s %d/%d" % (k, ko, n))
        print("    %-10s %s" % (r["border"], "   ".join(parts)))

    print("\n  A class under %d cases is not scored for the ranking and reads as" % min_class)
    print("  'no failures seen' rather than as an accuracy.")
    return 0
