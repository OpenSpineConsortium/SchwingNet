"""Name a vertebral border from shape alone, on any corpus, at any border.

This is the CTSpinoPelvic1K thoracolumbar experiment with the corpus and the border taken
out as parameters. Nothing here knows about T12 or L1 except as defaults.

    from border import Corpus, Border
    c = Corpus.from_csv("levels.csv")           # the wide table measure_levels.py writes
    r = Border("T12", "L1").evaluate(c)
    print(r.auc_whole, r.auc_adjacent, r.junction_accuracy)

WHAT THE MODEL IS, AND THE ONE THING THAT MAKES IT A SHAPE MODEL. Every measure is divided
by THAT CASE'S OWN MEDIAN across its measured levels, plus ratios between measures, which
carry no size at all. Patient size is removed, and so is the thing that would otherwise make
this trivial: lumbar vertebrae are simply bigger than thoracic ones, and a classifier given
raw millimetres learns that instead of shape, then fails at the border where the two
neighbours are nearly the same size. Strip the normalisation and the reported numbers stop
meaning what they say.

FOLDS ARE GROUPED BY CASE. Two vertebrae from one patient are not independent observations
and a random split leaks. Every score here is out of fold.

THE MODEL IS DELIBERATELY A LOGISTIC REGRESSION. The question is whether the shape carries
the border at all; if hand-built features on a linear model separate it, a network will do
better. A black box would answer the question less usefully and could not be read.
"""
from __future__ import annotations

import csv
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np

# the five measures the wide table carries per level, as column templates
BASE = ["endplate_width_{}_mm", "body_height_{}_mm", "body_height_post_{}_mm",
        "canal_width_{}_mm", "tp_span_{}_mm"]

VERSE_ORDER = (["C%d" % i for i in range(1, 8)]
               + ["T%d" % i for i in range(1, 13)] + ["T13"]
               + ["L%d" % i for i in range(1, 7)])


def _num(r, k):
    try:
        v = float(r[k])
    except (TypeError, ValueError, KeyError):
        return None
    return v if v > 0 else None


@dataclass
class Corpus:
    """One wide row per case: case, then <measure>_<level>_mm columns."""
    rows: List[dict]
    levels: List[str]
    case_key: str = "case"

    @classmethod
    def from_csv(cls, path: str, case_key: str = "case",
                 levels: Optional[Sequence[str]] = None) -> "Corpus":
        with open(path, encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        if not rows:
            raise SystemExit("%s has no rows" % path)
        if levels is None:
            # discover the levels actually present, in anatomical order
            found = set()
            for col in rows[0]:
                for lv in VERSE_ORDER:
                    if any(col == b.format(lv) for b in BASE):
                        found.add(lv)
            levels = [lv for lv in VERSE_ORDER if lv in found]
        if not levels:
            raise SystemExit(
                "no <measure>_<level>_mm columns found in %s. Expected columns like %r"
                % (path, BASE[0].format("L1")))
        return cls(rows=rows, levels=list(levels), case_key=case_key)

    def features(self, levels: Optional[Sequence[str]] = None):
        """X, groups, level per row, and the feature names."""
        levels = list(levels or self.levels)
        X, groups, lv, names = [], [], [], None
        for r in self.rows:
            med = {}
            for b in BASE:
                v = [_num(r, b.format(l)) for l in levels]
                v = [x for x in v if x is not None]
                if len(v) >= 3:
                    med[b] = float(np.median(v))
            if len(med) < len(BASE):
                continue                      # too little of this case to normalise by
            for l in levels:
                vals = {b: _num(r, b.format(l)) for b in BASE}
                if any(v is None for v in vals.values()):
                    continue
                f, nm = [], []
                for b in BASE:
                    f.append(vals[b] / med[b])
                    nm.append(b.format("").replace("__", "_").strip("_") + "/case_median")
                ew, bh = vals["endplate_width_{}_mm"], vals["body_height_{}_mm"]
                bhp, cw = vals["body_height_post_{}_mm"], vals["canal_width_{}_mm"]
                tp = vals["tp_span_{}_mm"]
                for val, n2 in ((tp / ew, "tp_span / endplate_width"),
                                (cw / ew, "canal_width / endplate_width"),
                                (bh / ew, "body_height / endplate_width"),
                                (bh / bhp, "anterior / posterior height"),
                                (tp / bh, "tp_span / body_height"),
                                (cw / bh, "canal_width / body_height")):
                    f.append(val)
                    nm.append(n2)
                X.append(f)
                groups.append(r[self.case_key])
                lv.append(l)
                names = nm
        if not X:
            raise SystemExit("no vertebra had all %d measures; nothing to fit" % len(BASE))
        return (np.asarray(X, float), np.asarray(groups), np.asarray(lv), names)


def fit_logreg(X, y, iters=400, lr=0.5, l2=1e-3):
    w = np.zeros(X.shape[1] + 1)
    A = np.hstack([X, np.ones((len(X), 1))])
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-A @ w))
        g = A.T @ (p - y) / len(y) + l2 * np.r_[w[:-1], 0.0]
        w -= lr * g
    return w


def auc(y, s):
    y = np.asarray(y, int)
    o = np.argsort(s)
    r = np.empty(len(s), float)
    r[o] = np.arange(1, len(s) + 1)
    npos, nneg = int(y.sum()), int((1 - y).sum())
    if npos == 0 or nneg == 0:
        return float("nan")
    return (r[y == 1].sum() - npos * (npos + 1) / 2) / (npos * nneg)


def out_of_fold(X, y, groups, folds=5, seed=0):
    cases = np.unique(groups)
    rng = np.random.default_rng(seed)
    rng.shuffle(cases)
    assign = {c: i % folds for i, c in enumerate(cases)}
    fold = np.array([assign[g] for g in groups])
    s = np.zeros(len(y), float)
    for k in range(folds):
        tr, te = fold != k, fold == k
        if not tr.any() or not te.any():
            continue
        mu, sd = X[tr].mean(0), X[tr].std(0)
        sd[sd == 0] = 1.0
        w = fit_logreg((X[tr] - mu) / sd, y[tr])
        A = np.hstack([(X[te] - mu) / sd, np.ones((int(te.sum()), 1))])
        s[te] = 1.0 / (1.0 + np.exp(-A @ w))
    return s


@dataclass
class Result:
    border: str
    n_vertebrae: int
    n_cases: int
    auc_whole: float
    auc_adjacent: float
    n_adjacent: int
    junction_accuracy: float
    n_junction: int
    offsets: Dict[int, int] = field(default_factory=dict)
    per_level_called_above: Dict[str, float] = field(default_factory=dict)

    def report(self) -> str:
        out = ["border %s" % self.border,
               "  %d vertebrae from %d cases" % (self.n_vertebrae, self.n_cases),
               "  AUC whole span      %.4f" % self.auc_whole,
               "  AUC adjacent pair   %.4f   (n=%d)" % (self.auc_adjacent, self.n_adjacent),
               "  junction placed correctly %.1f%%  (%d cases with the border in view)"
               % (100.0 * self.junction_accuracy, self.n_junction),
               "  offsets:"]
        # "ragged" sits among the integer offsets, so sort by str or this raises
        for k in sorted(self.offsets, key=lambda x: (isinstance(x, str), x)):
            tag = ("at the border" if k == 0 else
                   ("not a clean run" if isinstance(k, str) else "%+d level(s)" % k))
            out.append("    %-16s %4d" % (tag, self.offsets[k]))
        out.append("  share called ABOVE the border, per level:")
        for l, v in self.per_level_called_above.items():
            out.append("    %-5s %5.1f%%" % (l, 100.0 * v))
        return "\n".join(out)


@dataclass
class Border:
    """The border between two named levels: `above` is the caudal-most level above it."""
    above: str = "T12"
    below: str = "L1"

    def split(self, levels: Sequence[str]):
        order = {l: i for i, l in enumerate(levels)}
        if self.above not in order or self.below not in order:
            raise SystemExit("border %s/%s is not in the measured levels %s"
                             % (self.above, self.below, list(levels)))
        if order[self.below] != order[self.above] + 1:
            raise SystemExit("%s and %s are not adjacent in %s"
                             % (self.above, self.below, list(levels)))
        cut = order[self.below]
        return set(levels[:cut]), set(levels[cut:])

    def evaluate(self, corpus: Corpus, folds: int = 5, seed: int = 0,
                 levels: Optional[Sequence[str]] = None,
                 labels: Optional[Dict[tuple, int]] = None) -> Result:
        levels = list(levels or corpus.levels)
        upper, _ = self.split(levels)
        X, groups, lv, _ = corpus.features(levels)
        if labels is None:
            y = np.array([1 if l in upper else 0 for l in lv], int)
        else:
            y = np.array([labels[(g, l)] for g, l in zip(groups, lv)], int)
        s = out_of_fold(X, y, groups, folds=folds, seed=seed)
        adj = np.isin(lv, [self.above, self.below])

        order = {l: i for i, l in enumerate(levels)}
        pred = s >= 0.5
        per_case = defaultdict(dict)
        for g, l, p in zip(groups, lv, pred):
            per_case[g][l] = bool(p)
        offs, ok, n_j = {}, 0, 0
        for g, d in per_case.items():
            if self.above not in d or self.below not in d:
                continue
            n_j += 1
            present = sorted(d, key=lambda l: order[l])
            seq = [d[l] for l in present]
            n = sum(seq)
            if seq[:n] != [True] * n or any(seq[n:]):
                offs["ragged"] = offs.get("ragged", 0) + 1
                continue
            true_n = sum(1 for l in present if l in upper)
            o = n - true_n
            offs[o] = offs.get(o, 0) + 1
            ok += int(o == 0)
        per_level = {}
        for l in levels:
            m = lv == l
            if m.any():
                per_level[l] = float(pred[m].mean())
        return Result(border="%s/%s" % (self.above, self.below),
                      n_vertebrae=len(y), n_cases=len(np.unique(groups)),
                      auc_whole=auc(y, s), auc_adjacent=auc(y[adj], s[adj]),
                      n_adjacent=int(adj.sum()),
                      junction_accuracy=(ok / n_j) if n_j else float("nan"),
                      n_junction=n_j, offsets=offs, per_level_called_above=per_level)
