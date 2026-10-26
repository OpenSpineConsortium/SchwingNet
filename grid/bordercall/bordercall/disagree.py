"""Where the shape disagrees with the name: the count, the ribs, and the circular arm for scale.

    python run.py disagree --levels levels.csv --phenotype phenotype.csv --above T12 --below L1

The model's calls are out of fold against the count-based names (the truth bordercall scores
against: every level named by counting down from C2). A disagreement is a case whose border
the model placed somewhere else. Three things are then reported, and the difference between
them is the point:

  the count    accuracy against the count names, and of the disagreements, how many fall in a
               counted anomaly (a column with four or six lumbar identifiers, a thirteenth
               rib-bearing body, no rib on the twelfth), which is the owner's question
  the ribs     the names shifted by an INDEPENDENT reading, the lowest rib-bearing body of the
               census's rib table set to T12 (or the first set to T1), the model refitted out
               of fold on those names and scored against them; where the ribs side with the
               shape, the "disagreement" was the count's naming convention, not an error
  circular     the disagreeing cases relabelled to the model's own call, refitted and scored:
               the number a reader would get by trusting the model about itself. It is
               reported beside the rib arm so the rib arm can be read against it, and it
               proves nothing (the owner's instruction of 2026-10-25: never relabel to the
               model's own prediction and call the result an accuracy)

Only cases with the border in view and, for the rib arm, with ribs read are counted, and every
table carries its denominator.
"""
from __future__ import annotations

import csv
import os
import sys
from collections import Counter, defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import phenotype as PH                       # noqa: E402
import scheme as S                           # noqa: E402
from border import Border, Corpus, out_of_fold   # noqa: E402

ANOMALOUS = [k for k in PH.CLASS_ORDER if k != "typical"]
# the count's order of names: the scheme's, less T13, which a count from C2 never names (a
# thirteenth rib-bearing body is L1 with a rib)
COUNT_ORDER = [l for l in S.ORDER if l != "T13"]


def calls(corpus, labels_of_case, folds, seed):
    """{case: {level: called above}} out of fold, trained on the labels given."""
    X, groups, lv, _ = corpus.features()
    y = np.array([labels_of_case(g, l) for g, l in zip(groups, lv)], int)
    s = out_of_fold(X, y, groups, folds=folds, seed=seed)
    per_case = defaultdict(dict)
    for g, l, p in zip(groups, lv, s >= 0.5):
        per_case[g][l] = bool(p)
    return per_case


def cut_of(seq):
    """The number of levels called above, when the calls are one clean run; None when ragged."""
    n = sum(seq)
    if seq[:n] != [True] * n or any(seq[n:]):
        return None
    return n


def truth_cut(present, upper):
    return sum(1 for l in present if l in upper)


def rib_shift(row, above, below):
    """How many levels the rib reading moves this border from the count's name; None without ribs."""
    if not row.get("phenotype_known") or row.get("phenotype_known") in ("0", 0):
        return None
    if below == "L1":
        name = row.get("lowest_rib_bearing") or ""
        anchor = "T12"
    elif below == "T1":
        name = row.get("first_rib_bearing") or ""
        anchor = "T1"
    else:
        return None
    if name not in COUNT_ORDER or anchor not in COUNT_ORDER:
        return None
    return COUNT_ORDER.index(name) - COUNT_ORDER.index(anchor)


def read_rows(phenotype_csv):
    with open(phenotype_csv, encoding="utf-8", newline="") as fh:
        return {r["case"]: r for r in csv.DictReader(fh)}


def run(levels_csv, phenotype_csv, above="T12", below="L1", folds=5, seed=0, case_key="case"):
    corpus = Corpus.from_csv(levels_csv, case_key=case_key)
    rows = read_rows(phenotype_csv)
    corpus.rows = [r for r in corpus.rows if rows.get(r[case_key], {}).get("countable") == "1"]
    if not corpus.rows:
        raise SystemExit("no countable case in %s" % phenotype_csv)
    b = Border(above, below)
    upper, _ = b.split(corpus.levels)
    order = {l: i for i, l in enumerate(corpus.levels)}

    # arm 1: the count
    per_case = calls(corpus, lambda g, l: 1 if l in upper else 0, folds, seed)
    in_view = {g: d for g, d in per_case.items() if above in d and below in d}
    n = len(in_view)
    verdict, model_cut = {}, {}
    for g, d in in_view.items():
        present = sorted(d, key=lambda l: order[l])
        c = cut_of([d[l] for l in present])
        model_cut[g] = (present, c)
        verdict[g] = (c is not None and c == truth_cut(present, upper))
    right = sum(verdict.values())
    disagree = [g for g, ok in verdict.items() if not ok]
    by_class = Counter(rows[g].get("phenotype") or "unknown" for g in disagree)
    class_n = Counter(rows[g].get("phenotype") or "unknown" for g in in_view)
    print("border %s/%s against the count names: %d of %d cases placed exactly (%.1f%%)"
          % (above, below, right, n, 100.0 * right / n if n else float("nan")))
    print("  disagreements %d, of which in a counted anomaly: %d; by class (disagreements / cases):"
          % (len(disagree), sum(v for k, v in by_class.items() if k in ANOMALOUS)))
    for k in PH.CLASS_ORDER + ["unknown"]:
        if class_n[k]:
            print("    %-30s %4d / %4d" % (PH.PRETTY.get(k, "No rib reading"), by_class[k], class_n[k]))

    # arm 2: the ribs, an independent naming
    shifts = {g: rib_shift(rows[g], above, below) for g in in_view}
    ribbed = {g: s for g, s in shifts.items() if s is not None}
    if ribbed:
        def rib_label(g, l):
            s = shifts.get(g)
            k = order[l] - (s or 0)
            return 1 if 0 <= k < len(corpus.levels) and corpus.levels[k] in upper else 0
        ribbed_corpus = Corpus(rows=[r for r in corpus.rows if r[case_key] in ribbed],
                               levels=corpus.levels, case_key=case_key)
        rib_calls = calls(ribbed_corpus, rib_label, folds, seed)
        rib_right = rib_n = sided = 0
        for g, d in rib_calls.items():
            if above not in d or below not in d:
                continue
            rib_n += 1
            present = sorted(d, key=lambda l: order[l])
            c = cut_of([d[l] for l in present])
            truth = truth_cut(present, upper) + shifts[g]
            rib_right += int(c is not None and c == truth)
            # of the count's disagreements, the ones where the ribs name the border where the model did
            _, c0 = model_cut.get(g, (None, None))
            if g in disagree and c0 is not None and c0 == truth:
                sided += 1
        moved = sum(1 for s in ribbed.values() if s)
        print("  the ribs (independent): names shifted in %d of %d ribbed cases; refitted and scored "
              "against the rib names: %d of %d placed exactly (%.1f%%); of the count's disagreements "
              "the ribs side with the shape in %d" % (moved, len(ribbed), rib_right, rib_n,
                                                      100.0 * rib_right / rib_n if rib_n else float("nan"), sided))
    else:
        print("  the ribs: no case with a rib reading, so the independent arm is empty")

    # arm 3: circular, for scale only
    def circular_label(g, l):
        present, c = model_cut.get(g, (None, None))
        if g in verdict and not verdict[g] and c is not None:
            return 1 if order[l] < order[present[0]] + c else 0
        return 1 if l in upper else 0
    circ = calls(corpus, circular_label, folds, seed)
    circ_right = circ_n = 0
    for g, d in circ.items():
        if above not in d or below not in d:
            continue
        circ_n += 1
        present = sorted(d, key=lambda l: order[l])
        c = cut_of([d[l] for l in present])
        present0, c0 = model_cut.get(g, (None, None))
        truth = c0 if (g in disagree and c0 is not None) else truth_cut(present, upper)
        circ_right += int(c is not None and c == truth)
    print("  circular (for scale, proves nothing): disagreements relabelled to the model's own call, "
          "refitted and scored: %d of %d placed exactly (%.1f%%)"
          % (circ_right, circ_n, 100.0 * circ_right / circ_n if circ_n else float("nan")))
    return {"n": n, "right": right, "disagreements": len(disagree), "by_class": dict(by_class)}
