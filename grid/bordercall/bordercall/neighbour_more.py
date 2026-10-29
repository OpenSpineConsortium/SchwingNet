"""The series continued: the field of view decoded as a whole, a nonlinear classifier, and the
size of the fit. The owner's words of 2026-10-26 06:26 and 06:31 UTC, "how can you improve it?"
and "please permit the body of the vertebra im trying to identify be measurable as well".

    python run.py neighbour-more --outdir ../records/neighbour-2026-10-26

So from here the main arm is the field with the target in it, and the neighbour-only arms of
neighbour.py are kept as the obscured case: a body that cannot itself be measured.

Solution G, the field decoded jointly. The bodies in a field of view carry consecutive names,
so one unknown, the name of the field's first body, fixes every name in it. Each visible body
gives a posterior over the 22 names from its own shape alone (a softmax on its seven log
measures, fitted on typical columns, or the published means with nothing fitted and one
log-size per field profiled out), and the field's score for a candidate name of the target is
the product of the visible bodies' posteriors at the names the candidate implies for them. A
candidate whose implied names run off the table (a body below L5) is not offered. Nothing in
the feature says where the field sits in the column: the test moves it. The half-width is
swept from 0 (the target alone) to 4 (nine bodies); the obscured variant withholds the target.

Beside G, solution C is refitted on the whole field's features (C_field): the direct linear
rule on every visible body at once, which can use what G's product cannot, that one patient's
bodies share a size and an offset. For a field of five bodies it is neighbour.py's with_target
arm; the wider fields are new.

Solution H, a nonlinear classifier on the same features as solution C: one hidden layer of
tanh units, trained by Adam with weight decay, the width chosen on the selection seed and
scored on the scoring seed. It says whether the linear rule of neighbour.py leaves anything
on the table.

The size of the fit: solution C and solution G refitted on 100 to 2,000 typical columns and
scored on the same scoring columns, so the reader knows whether the numbers are fit-limited.

Every number is about synthetic columns drawn from Panjabi's tables.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import panjabi as P                                                  # noqa: E402
import covariance as CV                                              # noqa: E402
import neighbour as NB                                               # noqa: E402

HALVES = (0, 1, 2, 3, 4)
HIDDEN = (32, 64, 128)
FIT_SIZES = (100, 300, 1000, 2000)
MLP_STEPS = 1500
K = NB.K


# ---- one body's own shape ------------------------------------------------------------------------

def self_features(values: Dict[str, np.ndarray], i: int, measures: Sequence[str],
                  constant: Dict[str, float]) -> List[float]:
    """The log of a body's own measures over the external constant; i looks the body up."""
    return [math.log(values[m][i] / constant[m]) for m in measures]


def self_rows(columns: Sequence[P.Column], measures: Sequence[str], constant) -> NB.Rows:
    X, y, rib, grp, ph = [], [], [], [], []
    for g, col in enumerate(columns):
        ro = NB.rib_ordinals(col)
        for i in range(len(col)):
            X.append(self_features(col.values, i, measures, constant))
            y.append(i)
            rib.append(-1 if ro[i] is None else ro[i])
            grp.append(g)
            ph.append(col.phenotype)
    return NB.Rows(X=np.asarray(X, float), y=np.asarray(y, int), rib=np.asarray(rib, int),
                   group=np.asarray(grp, int), phenotype=np.asarray(ph), n_columns=len(columns),
                   names=["log %s(0)" % m for m in measures])


def train_self(rows: NB.Rows, measures: Sequence[str], l2: float = 1e-3) -> NB.Softmax:
    """A body's name from its own shape, the posterior solution G multiplies along the field."""
    t0 = time.perf_counter()
    mu, sd = rows.X.mean(0), rows.X.std(0)
    sd[sd == 0] = 1.0
    W = NB.fit_softmax((rows.X - mu) / sd, rows.y, k=K, l2=l2)
    return NB.Softmax(arm="self", measures=tuple(measures), norm="external", mu=mu, sd=sd, W=W,
                      n_rows=len(rows.y), fit_seconds=time.perf_counter() - t0)


@dataclass
class PublishedSelf:
    """The table's expected log measures of each level and the pooled relative variances, the
    pieces of neighbour.Published for one body; solution G profiles the size over the field."""
    expect: np.ndarray        # (K, p)
    var: np.ndarray           # (p,)


def build_published_self(ref, measures: Sequence[str], constant, noise_mm: float = NB.SYNTH["noise_mm"]) -> PublishedSelf:
    pooled = [float(np.mean([(ref[m][lv][1] / ref[m][lv][0]) ** 2 + (noise_mm / ref[m][lv][0]) ** 2
                             for lv in P.LEVELS])) for m in measures]
    E = [[math.log(ref[m][lv][0] / constant[m]) for m in measures] for lv in NB.CLASSES]
    return PublishedSelf(expect=np.asarray(E, float), var=np.asarray(pooled, float))


# ---- the field -----------------------------------------------------------------------------------

def field_offsets(half: int, with_target: bool = True) -> Tuple[int, ...]:
    """The offsets of the bodies a field of half-width `half` shows around the target."""
    return tuple(d for d in range(-half, half + 1) if d != 0 or with_target)


def field_targets(n: int, offs: Sequence[int]) -> List[int]:
    return [i for i in range(n) if all(0 <= i + d < n for d in offs)]


def field_features(values, i: int, offs: Sequence[int], measures: Sequence[str], constant) -> List[float]:
    out: List[float] = []
    for d in offs:
        out += self_features(values, i + d, measures, constant)
    return out


def field_rows(columns: Sequence[P.Column], offs: Sequence[int], measures: Sequence[str], constant) -> NB.Rows:
    X, y, rib, grp, ph = [], [], [], [], []
    for g, col in enumerate(columns):
        ro = NB.rib_ordinals(col)
        for i in field_targets(len(col), offs):
            X.append(field_features(col.values, i, offs, measures, constant))
            y.append(i)
            rib.append(-1 if ro[i] is None else ro[i])
            grp.append(g)
            ph.append(col.phenotype)
    return NB.Rows(X=np.asarray(X, float), y=np.asarray(y, int), rib=np.asarray(rib, int),
                   group=np.asarray(grp, int), phenotype=np.asarray(ph), n_columns=len(columns),
                   names=["log %s(%+d)" % (m, d) for d in offs for m in measures])


def candidates(offs: Sequence[int]) -> np.ndarray:
    """The names the target may take: those whose implied names for every visible body are in
    the table. A field never names a body below L5 or above C3."""
    return np.asarray([c for c in range(K) if all(0 <= c + d < K for d in offs)], int)


@dataclass
class Field:
    """Solution G. The product of the visible bodies' posteriors along the field, at the names a
    candidate implies; either from the fitted self model or from the published means."""
    offs: Tuple[int, ...]
    p: int
    self_model: Optional[NB.Softmax] = None
    published: Optional[PublishedSelf] = None

    def log_scores(self, X: np.ndarray) -> np.ndarray:
        n = len(X)
        D = len(self.offs)
        Xb = X.reshape(n, D, self.p)
        cands = candidates(self.offs)
        S = np.full((n, K), -np.inf)
        if self.self_model is not None:
            S[:, cands] = 0.0
            for j, d in enumerate(self.offs):
                logP = np.log(self.self_model.probabilities(Xb[:, j, :]) + 1e-300)
                S[:, cands] += logP[:, cands + d]
        else:
            pub = self.published
            w = 1.0 / pub.var                                   # (p,)
            for c in cands:
                E = pub.expect[[c + d for d in self.offs]]      # (D, p)
                R = Xb - E[None, :, :]
                s_hat = (R * w).sum((1, 2)) / (D * w.sum())     # one log-size per field
                R = R - s_hat[:, None, None]
                S[:, c] = -0.5 * (R * R * w).sum((1, 2))
        return S

    def probabilities(self, X: np.ndarray) -> np.ndarray:
        return NB.softmax(self.log_scores(X))

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.log_scores(X).argmax(1)


def field_shuffle_invariance(ref, offs: Sequence[int], measures: Sequence[str], model, constant,
                             seed: int = 5, trials: int = 50) -> dict:
    """The position-leak test for the field: the same bodies at another position of a column
    whose other bodies are shuffled give the same features and the same call."""
    rng = np.random.default_rng(seed)
    reach = max([abs(d) for d in offs] + [0])
    same = 0
    for _ in range(trials):
        col = P.synthesize(ref, "typical", rng, measures=list(measures), **NB.SYNTH)
        n = len(col)
        i = int(rng.integers(reach, n - reach))
        f0 = field_features(col.values, i, offs, measures, constant)
        p0 = model.predict(np.asarray([f0]))[0]
        block = list(range(i - reach, i + reach + 1))
        others = [j for j in range(n) if j not in block]
        rng.shuffle(others)
        split = int(rng.integers(0, len(others) + 1))
        order = others[:split] + block + others[split:]
        values = {m: col.values[m][order] for m in measures}
        f1 = field_features(values, split + reach, offs, measures, constant)
        p1 = model.predict(np.asarray([f1]))[0]
        same += int(np.allclose(f0, f1) and p0 == p1)
    return {"trials": trials, "identical": same, "offsets": list(offs)}


def exact_by_level_by_phenotype(pred: np.ndarray, rows: NB.Rows) -> Dict[str, Dict[str, float]]:
    """The exact rate at each true level, per phenotype, so that a level a fit never names
    (the last body of a longer column) shows as zero where it is, not as a shift."""
    out: Dict[str, Dict[str, float]] = {}
    for ph in sorted(set(rows.phenotype.tolist())):
        m = rows.phenotype == ph
        levels: Dict[str, float] = {}
        for yv in sorted(set(rows.y[m].tolist())):
            mm = m & (rows.y == yv)
            levels[NB.COUNT_NAMES[yv]] = float((pred[mm] == yv).mean())
        out[ph] = levels
    return out


def _scored(pred: np.ndarray, rows: NB.Rows) -> dict:
    per = NB.score(pred, rows)
    return {"per_phenotype": per, "worst": NB.worst_of(per),
            "worst_within_one": NB.worst_of(per, "within_one_rate"),
            "by_level_typical": NB.by_level(pred, rows),
            "exact_by_level": exact_by_level_by_phenotype(pred, rows)}


def field_cell(ref, regime: str, half: int, fit_cols, sco_cols, constant, self_model=None) -> Tuple[dict, NB.Softmax]:
    """One regime x half-width: the field with the target (the main arm) and without it (the
    obscured case), by the fitted self model (G) and by the published means (G_B)."""
    measures = NB.REGIMES[regime]
    if self_model is None:
        self_model = train_self(self_rows(fit_cols, measures, constant), measures)
    pub = build_published_self(ref, measures, constant)
    p = len(measures)
    cell = {"regime": regime, "half": half, "self_fit_seconds": self_model.fit_seconds, "arms": {}}
    for arm, with_target in (("with_target", True), ("obscured", False)):
        offs = field_offsets(half, with_target)
        if not offs:
            continue
        rows = field_rows(sco_cols, offs, measures, constant)
        G = Field(offs=offs, p=p, self_model=self_model)
        GB = Field(offs=offs, p=p, published=pub)
        fit_rows = field_rows(fit_cols, offs, measures, constant)
        C = NB.train_softmax(fit_rows, "field", measures)
        entry = {"offsets": list(offs), "visible_bodies": len(offs), "n_score_rows": len(rows.y),
                 "n_fit_rows": len(fit_rows.y), "chance": NB.chance(rows),
                 "G": _scored(G.predict(rows.X), rows), "G_B": _scored(GB.predict(rows.X), rows),
                 "C_field": _scored(C.predict(rows.X), rows),
                 "shuffle": field_shuffle_invariance(ref, offs, measures, G, constant),
                 "shuffle_C_field": field_shuffle_invariance(ref, offs, measures, C, constant)}
        entry["C_field"]["fit_seconds"] = C.fit_seconds
        for name, model in (("G", G), ("C_field", C)):
            hit = (model.predict(rows.X) == rows.y).astype(float)
            entry[name]["exact_all_phenotypes"] = float(hit.mean())
            entry[name]["se_cluster_all"] = NB.clustered_se(hit, rows.group)
        cell["arms"][arm] = entry
    return cell, self_model


# ---- solution H: one hidden layer ------------------------------------------------------------------

@dataclass
class MLP:
    """Solution H: standardised features, one tanh layer, a softmax over the names."""
    arm: str
    measures: Tuple[str, ...]
    mu: np.ndarray
    sd: np.ndarray
    W1: np.ndarray
    b1: np.ndarray
    W2: np.ndarray
    b2: np.ndarray
    hidden: int = 0
    steps: int = 0
    fit_seconds: float = 0.0

    def probabilities(self, X: np.ndarray) -> np.ndarray:
        A = (X - self.mu) / self.sd
        H = np.tanh(A @ self.W1 + self.b1)
        return NB.softmax(H @ self.W2 + self.b2)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.probabilities(X).argmax(1)


def train_mlp(rows: NB.Rows, arm: str, measures: Sequence[str], hidden: int = 64, steps: int = MLP_STEPS,
              lr: float = 0.01, l2: float = 1e-4, seed: int = 0) -> MLP:
    """Full-batch Adam on the cross-entropy with weight decay; deterministic from the seed."""
    t0 = time.perf_counter()
    rng = np.random.default_rng(seed)
    mu, sd = rows.X.mean(0), rows.X.std(0)
    sd[sd == 0] = 1.0
    X = (rows.X - mu) / sd
    n, p = X.shape
    k = max(K, int(rows.y.max()) + 1)
    Y = np.zeros((n, k))
    Y[np.arange(n), rows.y] = 1.0
    params = [rng.normal(0, 1.0 / math.sqrt(p), (p, hidden)), np.zeros(hidden),
              rng.normal(0, 1.0 / math.sqrt(hidden), (hidden, k)), np.zeros(k)]
    m1 = [np.zeros_like(q) for q in params]
    m2 = [np.zeros_like(q) for q in params]
    b1_, b2_, eps = 0.9, 0.999, 1e-8
    for t in range(1, steps + 1):
        W1, b1, W2, b2 = params
        H = np.tanh(X @ W1 + b1)
        Pr = NB.softmax(H @ W2 + b2)
        dZ = (Pr - Y) / n
        grads = [None] * 4
        grads[2] = H.T @ dZ + l2 * W2
        grads[3] = dZ.sum(0)
        dH = (dZ @ W2.T) * (1.0 - H * H)
        grads[0] = X.T @ dH + l2 * W1
        grads[1] = dH.sum(0)
        for j in range(4):
            m1[j] = b1_ * m1[j] + (1 - b1_) * grads[j]
            m2[j] = b2_ * m2[j] + (1 - b2_) * grads[j] * grads[j]
            mh = m1[j] / (1 - b1_ ** t)
            vh = m2[j] / (1 - b2_ ** t)
            params[j] = params[j] - lr * mh / (np.sqrt(vh) + eps)
    W1, b1, W2, b2 = params
    return MLP(arm=arm, measures=tuple(measures), mu=mu, sd=sd, W1=W1, b1=b1, W2=W2, b2=b2,
               hidden=hidden, steps=steps, fit_seconds=time.perf_counter() - t0)


def mlp_cell(ref, arm: str, regime: str, fit_cols, sel_cols, sco_cols, constant) -> dict:
    """Solution H on one arm x regime, the width chosen on the selection seed; solution C on the
    same rows beside it."""
    measures = NB.REGIMES[regime]
    fit = NB.rows_of(fit_cols, arm, measures, "external", constant)
    sel = NB.rows_of(sel_cols, arm, measures, "external", constant)
    sco = NB.rows_of(sco_cols, arm, measures, "external", constant)
    selection, models = {}, {}
    for h in HIDDEN:
        m = train_mlp(fit, arm, measures, hidden=h)
        selection[str(h)] = NB.worst_of(NB.score(m.predict(sel.X), sel))["exact_rate"]
        models[h] = m
    best = max(HIDDEN, key=lambda h: selection[str(h)])
    m = models[best]
    out = {"arm": arm, "regime": regime, "hidden_chosen": best, "selection_worst_by_hidden": selection,
           "fit_seconds_by_hidden": {str(h): models[h].fit_seconds for h in HIDDEN},
           "H": _scored(m.predict(sco.X), sco),
           "shuffle": NB.shuffle_invariance(ref, arm, measures, m, "external", constant)}
    out["H"]["fit_seconds"] = m.fit_seconds
    c = NB.train_softmax(fit, arm, measures)
    out["C_same_rows"] = _scored(c.predict(sco.X), sco)
    return out


# ---- the size of the fit -----------------------------------------------------------------------------

def fit_size_sweep(ref, sco_cols, constant, sizes=FIT_SIZES, half: int = 2) -> List[dict]:
    measures = NB.REGIMES["both"]
    offs = field_offsets(half, True)
    sco_c = NB.rows_of(sco_cols, "with_target", measures, "external", constant)
    sco_g = field_rows(sco_cols, offs, measures, constant)
    out = []
    for n in sizes:
        cols = NB.draw_columns(ref, ("typical",), NB.FIT_SEED, n, measures)
        fit = NB.rows_of(cols, "with_target", measures, "external", constant)
        c = NB.train_softmax(fit, "with_target", measures)
        pc = NB.score(c.predict(sco_c.X), sco_c)
        self_model = train_self(self_rows(cols, measures, constant), measures)
        g = Field(offs=offs, p=len(measures), self_model=self_model)
        pg = NB.score(g.predict(sco_g.X), sco_g)
        out.append({"n_fit_columns": n, "n_fit_rows_C": len(fit.y),
                    "C_with_target": {"typical": pc["typical"]["exact_rate"], "worst": NB.worst_of(pc),
                                      "se_typical": pc["typical"]["se_cluster"], "fit_seconds": c.fit_seconds},
                    "G_half_%d" % half: {"typical": pg["typical"]["exact_rate"], "worst": NB.worst_of(pg),
                                         "se_typical": pg["typical"]["se_cluster"], "fit_seconds": self_model.fit_seconds}})
    return out


# ---- the r sweep of the field --------------------------------------------------------------------

def field_r_sweep(ref, constant, n_fit: int, n_score: int, grid: Sequence[float], halves=HALVES) -> dict:
    """Solution G with the target in the field, three regimes, every half-width, the
    unidentified r swept; identified sets and the sign of every between-regime difference."""
    measures7 = list(CV.SPINEPS_7)
    sweep = {sol: {str(h): {regime: [] for regime in NB.REGIMES} for h in halves} for sol in ("G", "C_field")}
    for r in grid:
        fc = NB.draw_columns(ref, ("typical",), NB.FIT_SEED, n_fit, measures7, r_between=r)
        sc = NB.draw_columns(ref, P.PHENOTYPES, NB.SCORE_SEED, n_score * len(P.PHENOTYPES), measures7, r_between=r)
        for regime, measures in NB.REGIMES.items():
            self_model = train_self(self_rows(fc, measures, constant), measures)
            for h in halves:
                offs = field_offsets(h, True)
                rows = field_rows(sc, offs, measures, constant)
                models = {"G": Field(offs=offs, p=len(measures), self_model=self_model),
                          "C_field": NB.train_softmax(field_rows(fc, offs, measures, constant), "field", measures)}
                for sol, model in models.items():
                    pred = model.predict(rows.X)
                    per = NB.score(pred, rows)
                    hit = (pred == rows.y).astype(float)
                    sweep[sol][str(h)][regime].append({"r": r, "acc": float(hit.mean()), "se": NB.clustered_se(hit, rows.group),
                                                       "n": len(hit), "worst": NB.worst_of(per),
                                                       "per_phenotype": {ph: per[ph]["exact_rate"] for ph in per}})
    out = {"sweep": sweep, "identified": {}, "sign": {}, "profile_in_r": {}}
    for sol in sweep:
        out["identified"][sol], out["profile_in_r"][sol], out["sign"][sol] = {}, {}, {}
        for h in halves:
            hs = str(h)
            out["identified"][sol][hs] = {regime: CV.identified_set(sweep[sol][hs][regime]) for regime in NB.REGIMES}
            out["profile_in_r"][sol][hs] = {regime: CV.profile_in_r(sweep[sol][hs][regime]) for regime in NB.REGIMES}
            out["sign"][sol][hs] = {}
            for a, b in (("both", "lateral"), ("both", "ap"), ("ap", "lateral")):
                out["sign"][sol][hs]["%s_minus_%s" % (a, b)] = CV.sign_invariance(sweep[sol][hs][a], sweep[sol][hs][b])
    return out


# ---- latency --------------------------------------------------------------------------------------------

def field_latency(ref, self_model: NB.Softmax, fit_cols, measures, constant, halves=HALVES, repeats: int = 1000) -> dict:
    rng = np.random.default_rng(1)
    col = P.synthesize(ref, "typical", rng, measures=list(measures), **NB.SYNTH)
    out = {}
    for h in halves:
        offs = field_offsets(h, True)
        models = {"G": Field(offs=offs, p=len(measures), self_model=self_model),
                  "C_field": NB.train_softmax(field_rows(fit_cols, offs, measures, constant), "field", measures)}
        i = field_targets(len(col), offs)[len(col) // 2 - h]
        for sol, model in models.items():
            t0 = time.perf_counter()
            for _ in range(repeats):
                f = field_features(col.values, i, offs, measures, constant)
                model.predict(np.asarray([f]))
            out["%s_half_%d_ms_per_field" % (sol, h)] = 1000.0 * (time.perf_counter() - t0) / repeats
        out["C_field_half_%d_fit_seconds" % h] = models["C_field"].fit_seconds
    return out


# ---- the run ------------------------------------------------------------------------------------------

def run(outdir: Optional[str] = None, n_fit: int = NB.N_FIT, n_select: int = NB.N_SELECT, n_score: int = NB.N_SCORE,
        r_grid: Optional[Sequence[float]] = None, quick: bool = False) -> dict:
    t_start = time.perf_counter()
    measures7 = list(CV.SPINEPS_7)
    ref = P.load_reference(measures=measures7)
    constant = NB.external_constant(ref, measures7)
    halves = list(HALVES)
    if quick:
        n_fit, n_select, n_score = min(n_fit, 60), min(n_select, 30), min(n_score, 40)
        halves = halves[:3]
    fit_cols = NB.draw_columns(ref, ("typical",), NB.FIT_SEED, n_fit, measures7)
    sel_cols = NB.draw_columns(ref, P.PHENOTYPES, NB.SELECT_SEED, n_select * len(P.PHENOTYPES), measures7)
    sco_cols = NB.draw_columns(ref, P.PHENOTYPES, NB.SCORE_SEED, n_score * len(P.PHENOTYPES), measures7)
    rec = {"study": "neighbour-identity, continued: the field decoded, a nonlinear classifier, the size of the fit",
           "synth": dict(NB.SYNTH, r_between=0.0),
           "seeds": {"fit": NB.FIT_SEED, "select": NB.SELECT_SEED, "score": NB.SCORE_SEED},
           "n_columns": {"fit_typical": n_fit, "select_per_phenotype": n_select, "score_per_phenotype": n_score},
           "halves": halves, "hidden": list(HIDDEN), "fit_sizes": list(FIT_SIZES), "classes": NB.CLASSES,
           "external_constant": constant, "field": [], "mlp": [], "fit_size": [], "latency": {},
           "python": sys.version.split()[0], "numpy": np.__version__}
    print("neighbour-identity, continued: %d fit columns, %d selection and %d scoring columns per phenotype"
          % (n_fit, n_select, n_score))
    self_models = {}
    for regime in NB.REGIMES:
        for h in halves:
            cell, self_models[regime] = field_cell(ref, regime, h, fit_cols, sco_cols, constant,
                                                  self_model=self_models.get(regime))
            rec["field"].append(cell)
            w = cell["arms"]["with_target"]
            line = "  field half %d %-8s with target: C %.3f worst %.3f (%s)  G %.3f / %.3f  G_B %.3f  shuffle %d/%d" % (
                h, regime, w["C_field"]["per_phenotype"]["typical"]["exact_rate"], w["C_field"]["worst"]["exact_rate"],
                w["C_field"]["worst"]["phenotype"], w["G"]["per_phenotype"]["typical"]["exact_rate"],
                w["G"]["worst"]["exact_rate"], w["G_B"]["worst"]["exact_rate"],
                w["shuffle_C_field"]["identical"], w["shuffle_C_field"]["trials"])
            if "obscured" in cell["arms"]:
                o = cell["arms"]["obscured"]["C_field"]
                line += "  obscured C: %.3f worst %.3f" % (o["per_phenotype"]["typical"]["exact_rate"], o["worst"]["exact_rate"])
            print(line)
    for arm in ("with_target", "flank"):
        for regime in NB.REGIMES:
            cell = mlp_cell(ref, arm, regime, fit_cols, sel_cols, sco_cols, constant)
            rec["mlp"].append(cell)
            print("  H %-12s %-8s hidden %3d: typical %.3f worst %.3f (%s); C on the same rows %.3f / %.3f; shuffle %d/%d"
                  % (arm, regime, cell["hidden_chosen"], cell["H"]["per_phenotype"]["typical"]["exact_rate"],
                     cell["H"]["worst"]["exact_rate"], cell["H"]["worst"]["phenotype"],
                     cell["C_same_rows"]["per_phenotype"]["typical"]["exact_rate"], cell["C_same_rows"]["worst"]["exact_rate"],
                     cell["shuffle"]["identical"], cell["shuffle"]["trials"]))
    sizes = [s for s in FIT_SIZES if not quick or s <= 300]
    rec["fit_size"] = fit_size_sweep(ref, sco_cols, constant, sizes=sizes)
    for row in rec["fit_size"]:
        print("  fit on %4d columns: C with target %.3f / worst %.3f; G half 2 %.3f / worst %.3f"
              % (row["n_fit_columns"], row["C_with_target"]["typical"], row["C_with_target"]["worst"]["exact_rate"],
                 row["G_half_2"]["typical"], row["G_half_2"]["worst"]["exact_rate"]))
    grid = list(CV.R_GRID) if r_grid is None else list(r_grid)
    if quick:
        grid = grid[:2]
    rec["field_r"] = field_r_sweep(ref, constant, n_fit, n_score, grid, halves=halves)
    for sol in ("C_field", "G"):
        for h in halves:
            s = rec["field_r"]["sign"][sol][str(h)]["both_minus_ap"]
            print("  %s half %d: both minus ap over r [%+.3f, %+.3f], IM [%+.3f, %+.3f], sign constant %s, %.1f se"
                  % (sol, h, s["set"]["lo"], s["set"]["hi"], s["set"]["ci_lo"], s["set"]["ci_hi"], s["sign_constant"], s["margin_in_se"]))
    rec["latency"] = field_latency(ref, self_models["both"], fit_cols, measures7, constant, halves=halves)
    rec["latency"]["machine"] = {"platform": sys.platform, "cpus": os.cpu_count()}
    rec["seconds_total"] = time.perf_counter() - t_start
    rec["latency"]["study_seconds"] = rec["seconds_total"]
    print("  latency: " + ", ".join("half %d C %.3f ms G %.3f ms" % (h, rec["latency"]["C_field_half_%d_ms_per_field" % h],
                                                                      rec["latency"]["G_half_%d_ms_per_field" % h]) for h in halves)
          + "; %.0f s in all" % rec["seconds_total"])
    if outdir:
        os.makedirs(outdir, exist_ok=True)
        path = os.path.join(outdir, "neighbour_more.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rec, fh, indent=1, sort_keys=True, default=NB._jsonable)
            fh.write("\n")
        print("wrote %s" % path)
    return rec
