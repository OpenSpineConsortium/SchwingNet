"""Name the cervicothoracic and the thoracolumbar junction from Panjabi's tables alone, and
show that an anomaly at the lumbosacral junction cannot move either call.

    python run.py panjabi            # train on synthetic columns, score every phenotype
    python run.py panjabi-corpus --levels levels.csv --phenotype phenotype.csv
                                     # the same models on a corpus counted from C2

WHAT IS BUILT. Two logistic regressions, one per junction, trained on columns drawn from
Panjabi's published means and standard deviations (panjabi.py) and never on a CT. Each
vertebra is classified "below the junction" from how its measures compare with its
neighbours, and the junction is placed where the calls flip, by the cut that makes the
whole window most likely. The model is a linear rule over a handful of named ratios, so
every call can be read off the weights (Model.explain), which is what "explainable" means
here.

WHY THE FEATURES ARE LOCAL, SIZE-FREE AND CONVENTION-FREE. A feature is a log ratio between
one vertebra and a neighbour at most two levels away, per measure. Patient size divides out
of a ratio. A constant offset between how a cadaver was measured in 1991 and how a CT mask
is measured today multiplies every level's value by the same factor, which also divides
out, so a model fitted to the table can be run on a mask without a single number from the
mask going into the fit. And a ratio two levels wide cannot see a sixth lumbar vertebra or a
missing fifth: the lumbosacral anomaly changes the column four levels below the
thoracolumbar junction and never reaches the features the call is made from. That is the
claim the slides make, and twin_invariance checks it on columns that share every draw but
the anomaly.

The within-vertebra ratios (end-plate over posterior height, canal over end-plate) are
size-free too but carry one convention constant per pair, so they are off by default and
the real-data check reports them with the constant it needed. The profile features (a level
over its window's median) are convention-free but see the whole window, so a long window
that takes in the anomaly moves them a little; they are off by default for the same reason.

THE THORACOLUMBAR TRANSITIONAL BODY IS THE HARD CASE. A body that is half thoracic and half
lumbar in shape (a rudimentary rib on L1, a rib-less T12, a true T13) sits on the junction
itself, so the shape alone cannot say which side of the border it is on; blend_sweep shows
how the call degrades as the body moves from one shape to the other, and the margin the
decoder reports is what a caller should abstain on.
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import panjabi as P                                                # noqa: E402
from border import fit_logreg                                      # noqa: E402

JUNCTIONS = ("ct", "tl")
PRETTY_JUNCTION = {"ct": "C7/T1 (cervicothoracic)", "tl": "T12/L1 (thoracolumbar)"}
# a level is "below" the junction when its region is one of these
BELOW = {"ct": ("T", "L"), "tl": ("L",)}
OFFSETS = (-2, -1, 1, 2)
# the three measures a CT mask gives in Panjabi's own definitions (end-plate width, posterior
# body height, transverse canal width); canal_ap and pedicle exist in the table but not in
# the CTSpinoPelvic1K measurement, so they are opt-in
DEFAULT_MEASURES = ("endplate", "h_post", "canal_w")
WITHIN = (("endplate", "h_post"), ("canal_w", "endplate"))
EPS = 1e-6


# ---- features ------------------------------------------------------------------------------

def feature_names(measures: Sequence[str], within: bool = False, profile: bool = False) -> List[str]:
    names = []
    for m in measures:
        for d in OFFSETS:
            names.append("log %s(%+d) / %s(0)" % (m, d, m))
    for d in OFFSETS:
        names.append("no level at %+d" % d)
    if within:
        for a, b in WITHIN:
            names.append("log %s / %s" % (a, b))
    if profile:
        for m in measures:
            names.append("log %s / window median" % m)
    return names


def features(values: Dict[str, np.ndarray], i: int, measures: Sequence[str],
             within: bool = False, profile: bool = False) -> List[float]:
    """The feature vector of level i in a window whose measures are arrays in cranio-caudal order."""
    n = len(values[measures[0]])
    f: List[float] = []
    for m in measures:
        v = values[m]
        for d in OFFSETS:
            j = i + d
            f.append(math.log(v[j] / v[i]) if 0 <= j < n else 0.0)
    for d in OFFSETS:
        j = i + d
        f.append(0.0 if 0 <= j < n else 1.0)
    if within:
        for a, b in WITHIN:
            f.append(math.log(values[a][i] / values[b][i]))
    if profile:
        for m in measures:
            f.append(math.log(values[m][i] / float(np.median(values[m]))))
    return f


def window_matrix(values: Dict[str, np.ndarray], measures, within, profile) -> np.ndarray:
    n = len(values[measures[0]])
    return np.asarray([features(values, i, measures, within, profile) for i in range(n)], float)


# ---- the decoder ---------------------------------------------------------------------------

@dataclass
class Placement:
    """cut: levels [0, cut) are above the junction and [cut, n) below; 0 means every level is
    below it, n that every level is above it. margin: the log-likelihood the best cut has
    over the runner-up, which is what a caller abstains on."""
    cut: int
    margin: float
    loglik: np.ndarray
    p: np.ndarray

    @property
    def n(self) -> int:
        return len(self.p)

    @property
    def in_view(self) -> bool:
        return 0 < self.cut < self.n


def decode(p: np.ndarray) -> Placement:
    """The cut that makes the window most likely under the per-level calls."""
    p = np.clip(np.asarray(p, float), EPS, 1 - EPS)
    above = np.concatenate([[0.0], np.cumsum(np.log(1 - p))])      # sum over i < k of log(1-p_i)
    below = np.concatenate([np.cumsum(np.log(p)[::-1])[::-1], [0.0]])   # sum over i >= k of log p_i
    ll = above + below
    order = np.argsort(-ll)
    best = int(order[0])
    margin = float(ll[best] - ll[order[1]]) if len(ll) > 1 else float("inf")
    return Placement(cut=best, margin=margin, loglik=ll, p=p)


# ---- the model -----------------------------------------------------------------------------

@dataclass
class Model:
    junction: str
    measures: Tuple[str, ...]
    within: bool
    profile: bool
    mu: np.ndarray
    sd: np.ndarray
    w: np.ndarray
    n_rows: int = 0
    n_columns: int = 0
    # the share of training levels that lay below the junction: the class prior the fit
    # learnt, taken back out before decoding (probabilities)
    prior: float = 0.5

    @property
    def names(self) -> List[str]:
        return feature_names(self.measures, self.within, self.profile)

    def probabilities(self, values: Dict[str, np.ndarray]) -> np.ndarray:
        """Per level, the evidence that it lies below the junction, as a probability with the
        training prior divided out: a level the shape says nothing about scores 0.5, so it
        pulls the cut neither way. Left in, the prior (a fifth of a column is lumbar) would
        read every uninformative level as 'above' and push the cut to the window's end, which
        is what happened on full columns before this was taken out."""
        X = window_matrix(values, self.measures, self.within, self.profile)
        A = np.hstack([(X - self.mu) / self.sd, np.ones((len(X), 1))])
        prior = min(max(self.prior, EPS), 1 - EPS)
        logit = A @ self.w - math.log(prior / (1 - prior))
        return 1.0 / (1.0 + np.exp(-logit))

    def place(self, values: Dict[str, np.ndarray]) -> Placement:
        return decode(self.probabilities(values))

    def explain(self) -> List[Tuple[str, float]]:
        """Standardised weights, largest first: one standard deviation of the feature moves the
        log-odds of 'below the junction' by this much."""
        pairs = list(zip(self.names, self.w[:-1]))
        return sorted(pairs, key=lambda t: -abs(t[1]))

    def to_json(self) -> dict:
        return {"junction": self.junction, "measures": list(self.measures), "within": self.within,
                "profile": self.profile, "mu": self.mu.tolist(), "sd": self.sd.tolist(),
                "w": self.w.tolist(), "n_rows": self.n_rows, "n_columns": self.n_columns,
                "prior": self.prior, "features": self.names}

    @classmethod
    def from_json(cls, d: dict) -> "Model":
        return cls(junction=d["junction"], measures=tuple(d["measures"]), within=d["within"],
                   profile=d["profile"], mu=np.asarray(d["mu"]), sd=np.asarray(d["sd"]),
                   w=np.asarray(d["w"]), n_rows=d.get("n_rows", 0), n_columns=d.get("n_columns", 0),
                   prior=float(d.get("prior", 0.5)))


# ---- the profile model -------------------------------------------------------------------

STRUCTURES = tuple((nt, nl) for nt in (11, 12, 13) for nl in (4, 5, 6))


def structure_levels(n_thoracic: int, n_lumbar: int) -> List[str]:
    """C3 to the last lumbar body of a column with that many thoracic and lumbar levels."""
    return (list(P.CERVICAL) + ["T%d" % i for i in range(1, n_thoracic + 1)]
            + ["L%d" % i for i in range(1, n_lumbar + 1)])


def cuts_of(names: Sequence[str]) -> Dict[str, int]:
    regs = [P.region_of(n) for n in names]
    return {"ct": sum(1 for r in regs if r == "C"), "tl": sum(1 for r in regs if r in ("C", "T"))}


class Template:
    """Panjabi's column as a template the window is slid along.

    Every way of naming the window's levels that a column with 11 to 13 thoracic and 4 to 6
    lumbar bodies allows is scored by how well the window's log values match the table's
    profile, with one free offset per measure (patient size and measurement convention
    together), weighted by the table's spread. The junction's posterior is the sum over the
    namings that put it in one place. Nothing is fitted: the model is the table.

    The count anomalies are hypotheses of the same model, not exceptions to it, which is why a
    sixth lumbar body or a thirteenth rib-bearing one cannot move the call by surprise: the
    naming with the extra level is simply one of the candidates, scored like the rest."""

    def __init__(self, junction: str, ref, measures: Sequence[str] = DEFAULT_MEASURES,
                 noise_mm: float = 1.0, structures: Sequence[Tuple[int, int]] = STRUCTURES):
        self.junction = junction
        self.measures = tuple(measures)
        self.structures = tuple(structures)
        self.mu: Dict[str, Dict[str, float]] = {}
        self.sd: Dict[str, Dict[str, float]] = {}
        for m in self.measures:
            table = dict(ref[m])
            m4, m5 = table["L4"], table["L5"]
            table["L6"] = (m5[0] + 0.5 * (m5[0] - m4[0]), m5[1])     # the lumbar trend carried on
            table["T13"] = table["T12"]                              # a thirteenth thoracic body
            self.mu[m] = {lv: math.log(mean) for lv, (mean, _) in table.items()}
            self.sd[m] = {lv: math.sqrt((sd / mean) ** 2 + (noise_mm / mean) ** 2)
                          for lv, (mean, sd) in table.items()}
        self._cache: Dict[int, List[Tuple[Tuple[str, ...], Dict[str, int]]]] = {}

    @property
    def names(self) -> List[str]:
        return ["profile match of %s" % m for m in self.measures]

    def namings(self, n: int) -> List[Tuple[Tuple[str, ...], Dict[str, int]]]:
        """Every distinct way of naming n consecutive levels, with the cuts it implies."""
        if n not in self._cache:
            seen = {}
            for nt, nl in self.structures:
                levels = structure_levels(nt, nl)
                for start in range(0, len(levels) - n + 1):
                    names = tuple(levels[start:start + n])
                    seen.setdefault(names, cuts_of(names))
            self._cache[n] = list(seen.items())
        return self._cache[n]

    def loglik(self, values: Dict[str, np.ndarray], names: Sequence[str]) -> Dict[str, float]:
        """Per measure, the log-likelihood of the window under one naming, the offset
        profiled out by its precision-weighted mean."""
        out = {}
        for m in self.measures:
            x = np.log(np.asarray(values[m], float))
            mu = np.asarray([self.mu[m][nm] for nm in names])
            sd = np.asarray([self.sd[m][nm] for nm in names])
            w = 1.0 / (sd * sd)
            r = x - mu
            a = float((w * r).sum() / w.sum())
            out[m] = float(-0.5 * (w * (r - a) ** 2).sum() - np.log(sd).sum())
        return out

    def posterior(self, values: Dict[str, np.ndarray]) -> Tuple[np.ndarray, List[dict]]:
        """(log posterior per cut 0..n, the scored namings)."""
        n = len(values[self.measures[0]])
        rows = []
        for names, cuts in self.namings(n):
            parts = self.loglik(values, names)
            rows.append({"names": names, "cut": cuts[self.junction], "parts": parts,
                         "ll": sum(parts.values())})
        ll = np.full(n + 1, -np.inf)
        for r in rows:
            k = r["cut"]
            ll[k] = np.logaddexp(ll[k], r["ll"])
        return ll, rows

    def place(self, values: Dict[str, np.ndarray]) -> Placement:
        ll, _ = self.posterior(values)
        n = len(ll) - 1
        finite = np.isfinite(ll)
        top = np.max(ll[finite])
        post = np.where(finite, np.exp(ll - top), 0.0)
        post /= post.sum()
        order = np.argsort(-ll)
        best = int(order[0])
        margin = float(ll[best] - ll[order[1]]) if n >= 1 and np.isfinite(ll[order[1]]) else float("inf")
        # the chance that level i lies below the junction: every cut at or above i
        p = np.cumsum(post)[:n]
        return Placement(cut=best, margin=margin, loglik=ll, p=p)

    def explain(self, values: Dict[str, np.ndarray]) -> dict:
        """Why the best cut beat the runner-up: the log-likelihood gap by measure, between the
        best naming of each, and the residuals under the best naming."""
        ll, rows = self.posterior(values)
        order = np.argsort(-ll)
        best_cut, second_cut = int(order[0]), int(order[1])
        best = max((r for r in rows if r["cut"] == best_cut), key=lambda r: r["ll"])
        second = max((r for r in rows if r["cut"] == second_cut), key=lambda r: r["ll"])
        gap = {m: best["parts"][m] - second["parts"][m] for m in self.measures}
        return {"best_names": best["names"], "runner_up_names": second["names"],
                "gap_by_measure": gap, "margin": float(ll[best_cut] - ll[second_cut])}


def models_for(ref, junction: str, measures: Sequence[str] = DEFAULT_MEASURES, seed: int = 0,
               n_columns: int = 2000, within: bool = False, profile: bool = False,
               **synth) -> Dict[str, object]:
    """The two arms: the local logistic rule and the whole-profile template."""
    return {"local": train(ref, junction, seed=seed, n_columns=n_columns, measures=measures,
                           within=within, profile=profile, **synth),
            "profile": Template(junction, ref, measures=measures,
                                noise_mm=synth.get("noise_mm", 1.0))}


def labels_of(column: P.Column, junction: str) -> np.ndarray:
    return np.asarray([1 if r in BELOW[junction] else 0 for r in column.regions], int)


def random_window(column: P.Column, rng: np.random.Generator, width: Tuple[int, int],
                  junction: Optional[str] = None) -> Tuple[int, int]:
    """[start, stop) of a window of a random width; with a junction named, one that holds it
    with at least one level on each side."""
    n = len(column)
    lo, hi = width
    w = int(rng.integers(lo, min(hi, n) + 1))
    if junction is None:
        start = int(rng.integers(0, n - w + 1))
        return start, start + w
    cut = column.cut(junction)
    # start in [cut - w + 1, cut - 1] so that the cut is strictly inside
    a, b = max(0, cut - w + 1), min(cut - 1, n - w)
    if b < a:
        a = b = max(0, min(cut - 1, n - w))
    start = int(rng.integers(a, b + 1))
    return start, start + w


def train(ref, junction: str, seed: int = 0, n_columns: int = 2000, windows_per_column: int = 2,
          width: Tuple[int, int] = (5, 12), measures: Sequence[str] = DEFAULT_MEASURES,
          within: bool = False, profile: bool = False, phenotypes: Sequence[str] = ("typical",),
          **synth) -> Model:
    """Fit one junction's classifier on synthetic columns. Windows are drawn anywhere, so the
    model also learns what a window with no junction in it looks like."""
    rng = np.random.default_rng(seed)
    rows, ys = [], []
    for k in range(n_columns):
        col = P.synthesize(ref, phenotypes[k % len(phenotypes)], rng, measures=list(measures), **synth)
        y = labels_of(col, junction)
        for _ in range(windows_per_column):
            start, stop = random_window(col, rng, width)
            sub = col.window(start, stop)
            rows.extend(features(sub.values, i, measures, within, profile) for i in range(len(sub)))
            ys.extend(y[start:stop].tolist())
    X, y = np.asarray(rows, float), np.asarray(ys, int)
    mu, sd = X.mean(0), X.std(0)
    sd[sd == 0] = 1.0
    w = fit_logreg((X - mu) / sd, y)
    return Model(junction=junction, measures=tuple(measures), within=within, profile=profile,
                 mu=mu, sd=sd, w=w, n_rows=len(y), n_columns=n_columns, prior=float(y.mean()))


# ---- evaluation on synthetic columns -------------------------------------------------------

@dataclass
class Score:
    """How one junction was placed over n windows that held it."""
    n: int = 0
    exact: int = 0
    within_one: int = 0
    abstained: int = 0
    offsets: Counter = field(default_factory=Counter)
    margins: List[float] = field(default_factory=list)

    def add(self, placement: Placement, truth: int, margin: float):
        self.n += 1
        if placement.margin < margin:
            self.abstained += 1
            self.offsets["abstained"] += 1
            return
        off = placement.cut - truth
        self.offsets[off] += 1
        self.margins.append(placement.margin)
        if off == 0:
            self.exact += 1
        if abs(off) <= 1:
            self.within_one += 1

    @property
    def called(self) -> int:
        return self.n - self.abstained

    def rate(self, k: int) -> float:
        return k / self.called if self.called else float("nan")

    def row(self) -> dict:
        return {"n": self.n, "called": self.called, "exact": self.exact,
                "exact_rate": self.rate(self.exact), "within_one": self.within_one,
                "within_one_rate": self.rate(self.within_one), "abstained": self.abstained,
                "median_margin": float(np.median(self.margins)) if self.margins else float("nan")}


def wilson(k: int, n: int, z: float = 1.959964) -> Tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def evaluate(model: Model, ref, phenotype: str, seed: int = 1, n: int = 500,
             width: Tuple[int, int] = (5, 12), margin: float = 0.0, **synth) -> Score:
    """Place the junction in n random windows of columns of one phenotype."""
    rng = np.random.default_rng(seed)
    score = Score()
    for _ in range(n):
        col = P.synthesize(ref, phenotype, rng, measures=list(model.measures), **synth)
        start, stop = random_window(col, rng, width, model.junction)
        sub = col.window(start, stop)
        score.add(model.place(sub.values), col.cut(model.junction) - start, margin)
    return score


def evaluate_by_width(model: Model, ref, phenotype: str, widths: Iterable[int], seed: int = 2,
                      n: int = 300, margin: float = 0.0, **synth) -> Dict[int, Score]:
    return {w: evaluate(model, ref, phenotype, seed=seed + w, n=n, width=(w, w), margin=margin,
                        **synth) for w in widths}


def twin_invariance(models: Dict[str, Model], ref, seed: int = 3, n: int = 500,
                    phenotypes: Sequence[str] = P.LUMBOSACRAL, **synth) -> Dict[str, dict]:
    """Columns that share every draw but the lumbosacral anomaly: does either call move?

    Each twin is read in a window from C3 to its own last level, so the anomalous twin's window
    is one level longer or shorter at the bottom and identical above. A call is the same when
    the vertebra named as the first below the junction has the same name in both twins."""
    rng = np.random.default_rng(seed)
    out = {}
    for ph in phenotypes:
        agree = {j: 0 for j in models}
        pmax = {j: 0.0 for j in models}
        both_right = {j: 0 for j in models}
        for _ in range(n):
            pair = P.twins(ref, rng, ["typical", ph], measures=list(next(iter(models.values())).measures), **synth)
            a, b = pair["typical"], pair[ph]
            for j, m in models.items():
                pa, pb = m.place(a.values), m.place(b.values)
                name_a = a.levels[pa.cut] if pa.in_view else "none"
                name_b = b.levels[pb.cut] if pb.in_view else "none"
                if name_a == name_b:
                    agree[j] += 1
                if pa.cut == a.cut(j) and pb.cut == b.cut(j):
                    both_right[j] += 1
                # the per-level calls above L3 should be bit-identical for a local model
                k = min(len(a), len(b)) - 3
                pmax[j] = max(pmax[j], float(np.max(np.abs(pa.p[:k] - pb.p[:k]))))
        out[ph] = {j: {"n": n, "same_call": agree[j], "same_call_rate": agree[j] / n,
                       "both_right": both_right[j], "max_shift_above_L3": pmax[j]}
                   for j in models}
    return out


def blend_sweep(model: Model, ref, blends: Sequence[float], seed: int = 4, n: int = 300,
                phenotypes: Sequence[str] = P.THORACOLUMBAR, width: Tuple[int, int] = (5, 12),
                margin: float = 0.0, **synth) -> List[dict]:
    """How the thoracolumbar call degrades as the transitional body moves from one shape to
    the other: blend 0 is the body in its named region's shape, 1 wholly the other region's."""
    rows = []
    for ph in phenotypes:
        for b in blends:
            s = evaluate(model, ref, ph, seed=seed, n=n, width=width, margin=margin, blend=b, **synth)
            r = s.row()
            r.update(phenotype=ph, blend=b)
            rows.append(r)
    return rows


# ---- the real columns ----------------------------------------------------------------------

REAL_COLUMNS = {"endplate": "endplate_width_{}_mm", "h_post": "body_height_post_{}_mm",
                "canal_w": "canal_width_{}_mm", "canal_ap": "canal_ap_{}_mm"}
# C3 to L6: the levels Panjabi's table has an upper end-plate for, in a column counted from C2
REAL_LEVELS = P.CERVICAL + P.THORACIC + P.LUMBAR + ["L6"]


def _num(r, k):
    try:
        v = float(r[k])
    except (TypeError, ValueError, KeyError):
        return None
    return v if v > 0 else None


def real_windows(levels_csv: str, levels: Sequence[str] = REAL_LEVELS,
                 measures: Sequence[str] = DEFAULT_MEASURES, case_key: str = "case"):
    """{case: (names, values)} for every case whose measured levels run unbroken from its first
    measured level to its last, so a window is a true stretch of column."""
    out = {}
    with open(levels_csv, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        have = []
        for lv in levels:
            vals = {m: _num(r, REAL_COLUMNS[m].format(lv)) for m in measures}
            have.append(vals if all(v is not None for v in vals.values()) else None)
        # the longest unbroken run
        best, cur = (0, 0), None
        for i, h in enumerate(have + [None]):
            if h is not None and cur is None:
                cur = i
            if h is None and cur is not None:
                if i - cur > best[1] - best[0]:
                    best = (cur, i)
                cur = None
        a, b = best
        if b - a < 3:
            continue
        names = list(levels[a:b])
        out[r[case_key]] = (names, {m: np.asarray([have[i][m] for i in range(a, b)], float)
                                    for m in measures})
    return out


def convention_offsets(windows, ref, measures: Sequence[str] = DEFAULT_MEASURES) -> Dict[str, float]:
    """One constant per measure: the median over levels of log(CT median / Panjabi mean). The
    neighbour features never need it; the within-vertebra ratios do, and the figure is reported
    so the reader can see how far the two conventions sit apart."""
    out = {}
    for m in measures:
        per_level = defaultdict(list)
        for names, vals in windows.values():
            for nm, v in zip(names, vals[m]):
                per_level[nm].append(v)
        logs = [math.log(float(np.median(v)) / ref[m][nm][0]) for nm, v in per_level.items()
                if nm in ref[m] and len(v) >= 20]
        out[m] = float(np.median(logs)) if logs else 0.0
    return out


def real_check(model, windows, phenotypes: Dict[str, str], margin: float = 0.0,
               offsets: Optional[Dict[str, float]] = None) -> Dict[str, Score]:
    """Place the junction in each real column; score per phenotype class. offsets, when given,
    divide each measure by exp(offset) first, which changes only the within-vertebra ratios.
    A column is scored when the junction is in view with a level on each side."""
    scores: Dict[str, Score] = defaultdict(Score)
    above_name, below_name = {"tl": ("T12", "L1"), "ct": ("C7", "T1")}[model.junction]
    for case, (names, vals) in windows.items():
        if below_name not in names or above_name not in names:
            continue
        truth = names.index(below_name)
        v = {m: vals[m] / math.exp(offsets.get(m, 0.0)) for m in vals} if offsets else vals
        pl = model.place(v)
        ph = phenotypes.get(case, "unknown")
        scores[ph].add(pl, truth, margin)
        scores["all"].add(pl, truth, margin)
    return dict(scores)


# ---- reporting -----------------------------------------------------------------------------

def fmt_rate(k, n) -> str:
    if not n:
        return "   -   "
    lo, hi = wilson(k, n)
    return "%5.1f%% (%d/%d; %.0f-%.0f)" % (100.0 * k / n, k, n, 100 * lo, 100 * hi)


def score_table(scores: Dict[str, Score], pretty: Dict[str, str], order: Sequence[str]) -> List[str]:
    lines = ["  %-32s %-28s %-28s %s" % ("class", "junction exact", "within one level", "abstained")]
    for k in list(order) + [x for x in scores if x not in order]:
        if k not in scores:
            continue
        s = scores[k]
        lines.append("  %-32s %-28s %-28s %d of %d" % (pretty.get(k, k), fmt_rate(s.exact, s.called),
                                                      fmt_rate(s.within_one, s.called), s.abstained, s.n))
    return lines


def explain_lines(model: Model, top: int = 8) -> List[str]:
    lines = ["  %s: the %d largest standardised weights toward 'below the junction'"
             % (PRETTY_JUNCTION[model.junction], top)]
    for name, w in model.explain()[:top]:
        lines.append("    %+6.2f  %s" % (w, name))
    return lines


def run_synthetic(outdir: Optional[str] = None, n_columns: int = 2000, n_eval: int = 500,
                  measures: Sequence[str] = DEFAULT_MEASURES, within: bool = False,
                  profile: bool = False, margin: float = 0.0, seed: int = 0,
                  widths: Sequence[int] = (4, 5, 6, 8, 10, 12, 16),
                  blends: Sequence[float] = (0.0, 0.25, 0.5, 0.75, 1.0),
                  arms: Sequence[str] = ("local", "profile"), **synth) -> dict:
    """Both arms on both junctions: every table printed, and written as JSON under outdir."""
    ref = P.load_reference(measures=list(measures))
    models = {j: {a: m for a, m in models_for(ref, j, measures=measures, seed=seed,
                                              n_columns=n_columns, within=within, profile=profile,
                                              **synth).items() if a in arms}
              for j in JUNCTIONS}
    result = {"measures": list(measures), "within": within, "profile": profile, "margin": margin,
              "n_columns": n_columns, "n_eval": n_eval, "synth": synth, "arms": list(arms)}
    print("Panjabi junction models on synthetic columns: measures %s; the local rule fitted on %d "
          "columns (within-vertebra ratios %s, profile features %s); the profile template fitted "
          "on nothing" % (", ".join(measures), n_columns, "on" if within else "off",
                          "on" if profile else "off"))
    for j in JUNCTIONS:
        if "local" in models[j]:
            print("\n".join(explain_lines(models[j]["local"])))
    result["local_models"] = {j: m["local"].to_json() for j, m in models.items() if "local" in m}

    print("\nJunction placed in random windows of 5 to 12 levels that hold it, by phenotype "
          "(Wilson 95%% intervals; abstention margin %.2f):" % margin)
    by_ph = {}
    for j in JUNCTIONS:
        for a, m in models[j].items():
            scores = {ph: evaluate(m, ref, ph, seed=seed + 1, n=n_eval, margin=margin, **synth)
                      for ph in P.PHENOTYPES}
            by_ph["%s/%s" % (j, a)] = {ph: s.row() for ph, s in scores.items()}
            print("\n%s, %s arm" % (PRETTY_JUNCTION[j], a))
            print("\n".join(score_table(scores, P.PRETTY, P.PHENOTYPES)))
    result["by_phenotype"] = by_ph

    print("\nTypical columns by window width (levels in view), junction placed exactly:")
    by_w = {}
    for j in JUNCTIONS:
        for a, m in models[j].items():
            ws = evaluate_by_width(m, ref, "typical", widths, seed=seed + 2, n=max(100, n_eval // 2),
                                   margin=margin, **synth)
            by_w["%s/%s" % (j, a)] = {w: s.row() for w, s in ws.items()}
            print("  %s, %s arm: " % (PRETTY_JUNCTION[j], a)
                  + "; ".join("%d: %s" % (w, fmt_rate(s.exact, s.called)) for w, s in ws.items()))
    result["by_width"] = by_w

    print("\nTwins that share every draw but the lumbosacral anomaly (whole column in view):")
    tw_all = {}
    for a in arms:
        tw = twin_invariance({j: models[j][a] for j in JUNCTIONS}, ref, seed=seed + 3, n=n_eval, **synth)
        tw_all[a] = tw
        for ph, d in tw.items():
            for j, r in d.items():
                print("  %-8s %-26s %-26s same call %s; both twins right %d of %d; largest shift "
                      "in a call above L3 %.2e" % (a, P.PRETTY[ph], PRETTY_JUNCTION[j],
                                                   fmt_rate(r["same_call"], r["n"]), r["both_right"],
                                                   r["n"], r["max_shift_above_L3"]))
    result["twins"] = tw_all

    print("\nThe transitional body at the thoracolumbar junction, as its shape moves from its own "
          "region's to the other's (blend 0 to 1), junction placed exactly:")
    bs_all = {}
    for a in arms:
        bs = blend_sweep(models["tl"][a], ref, blends, seed=seed + 4, n=max(100, n_eval // 2),
                         margin=margin, **synth)
        bs_all[a] = bs
        for ph in P.THORACOLUMBAR:
            print("  %-8s %-26s " % (a, P.PRETTY[ph])
                  + "; ".join("%.2f: %s" % (r["blend"], fmt_rate(r["exact"], r["called"]))
                              for r in bs if r["phenotype"] == ph))
    result["blend_sweep"] = bs_all

    if outdir:
        os.makedirs(outdir, exist_ok=True)
        path = os.path.join(outdir, "panjabi_junction.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=1, sort_keys=True)
        print("\nwrote %s" % path)
    return result


def run_corpus(levels_csv: str, phenotype_csv: str, outdir: Optional[str] = None,
               n_columns: int = 2000, margin: float = 0.0, seed: int = 0,
               measures: Sequence[str] = DEFAULT_MEASURES, **synth) -> dict:
    """The Panjabi models on a measured corpus whose names come from a count from C2, both
    junctions, by phenotype: the profile template fitted on nothing, the local rule as the
    ablation, and bordercall's own model fitted on the corpus out of fold as the ceiling."""
    from border import Border, Corpus
    import phenotype as PH

    measures = [m for m in measures if m in REAL_COLUMNS]
    ref = P.load_reference(measures=list(measures))
    windows = real_windows(levels_csv, measures=measures)
    phen_rows = PH.load(phenotype_csv)
    phen = {k: v.get("phenotype") or "unknown" for k, v in phen_rows.items()}
    windows = {k: v for k, v in windows.items() if phen_rows.get(k, {}).get("countable")}
    print("%d countable columns with an unbroken run of 3 or more measured levels; measures %s"
          % (len(windows), ", ".join(measures)))
    offsets = convention_offsets(windows, ref, measures)
    print("convention offsets, log(corpus median / Panjabi mean): "
          + ", ".join("%s %+.3f (x%.2f)" % (m, o, math.exp(o)) for m, o in offsets.items()))
    result = {"n_columns": len(windows), "measures": measures, "offsets": offsets, "junctions": {}}
    order = PH.CLASS_ORDER + ["unknown", "all"]
    for j in JUNCTIONS:
        arms = [("profile template, fitted on nothing",
                 Template(j, ref, measures=measures, noise_mm=synth.get("noise_mm", 1.0)), None),
                ("local rule, neighbours only",
                 train(ref, j, seed=seed, n_columns=n_columns, measures=measures, **synth), None)]
        out = {}
        for title, m, off in arms:
            scores = real_check(m, windows, phen, margin=margin, offsets=off)
            print("\n%s, %s" % (PRETTY_JUNCTION[j], title))
            print("\n".join(score_table(scores, PH.PRETTY, order)))
            out[title] = {k: s.row() for k, s in scores.items()}
        above, below = {"tl": ("T12", "L1"), "ct": ("C7", "T1")}[j]
        try:
            c = Corpus.from_csv(levels_csv)
            c.rows = [r for r in c.rows if phen_rows.get(r[c.case_key], {}).get("countable")]
            r = Border(above, below).evaluate(c)
            print("\n%s, fitted on the corpus itself, out of fold (border.py): junction placed "
                  "correctly %.1f%% of %d cases, AUC adjacent pair %.3f"
                  % (PRETTY_JUNCTION[j], 100 * r.junction_accuracy, r.n_junction, r.auc_adjacent))
            out["fitted_on_corpus"] = {"junction_accuracy": r.junction_accuracy, "n": r.n_junction,
                                       "auc_adjacent": r.auc_adjacent}
        except SystemExit as exc:
            print("\n%s: border.py could not fit the corpus: %s" % (PRETTY_JUNCTION[j], exc))
        result["junctions"][j] = out
    if outdir:
        os.makedirs(outdir, exist_ok=True)
        path = os.path.join(outdir, "panjabi_corpus.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=1, sort_keys=True)
        print("\nwrote %s" % path)
    return result
